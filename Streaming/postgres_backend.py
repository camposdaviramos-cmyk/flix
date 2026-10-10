"""PostgreSQL driver boundary for the existing qmark SQL repositories.
Queries stay parameterized. The bounded compatibility layer preserves legacy
transaction semantics while repositories are moved to explicit row locks.
"""
import functools
import re
import sqlite3
from decimal import Decimal
from psycopg import IntegrityError, OperationalError
from psycopg_pool import ConnectionPool

QUOTED = re.compile(r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\")")
IDENTITY_TABLES = {'coin_ledger','community_comments','community_dm','community_reports','community_audit','community_messages','community_signals','community_queue','hub_notifications','hub_call_signals','jump_messages','jump_signals','room_audio_queue','room_plugin_events'}
REPLACE_KEYS = {'settings': ('key', ['key','value']), 'music_api_cache': ('key',['key','payload','created_at']), 'community_games': ('room_id',['room_id','id','kind','status','state','revision','created_at'])}

def outside(sql, transform):
    return ''.join(part if index % 2 else transform(part) for index, part in enumerate(QUOTED.split(sql)))

@functools.lru_cache(maxsize=2048)
def translate(sql):
    sql = sql.strip().rstrip(';')
    # PostgreSQL makes unqualified RHS columns ambiguous in upserts.
    insert = re.match(r'INSERT(?: OR (?:IGNORE|REPLACE))? INTO\s+(\w+)', sql, re.I)
    if insert:
        table = insert[1]
        replace = bool(re.match(r'INSERT OR REPLACE',sql,re.I))
        ignore = bool(re.match(r'INSERT OR IGNORE',sql,re.I))
        sql = re.sub(r'^INSERT OR (?:IGNORE|REPLACE)', 'INSERT', sql, flags=re.I)
        if replace:
            key, columns = REPLACE_KEYS[table]
            sql += ' ON CONFLICT ('+key+') DO UPDATE SET '+','.join(c+'=excluded.'+c for c in columns if c!=key)
        elif ignore:
            sql += ' ON CONFLICT DO NOTHING'
        match = re.search(r'\bDO UPDATE SET\b', sql,re.I)
        if match:
            head,tail = sql[:match.end()],sql[match.end():]
            # Only legacy scalar MAX/MIN need old-column qualification; SET targets stay unqualified.
            tail = outside(tail,lambda p:re.sub(r'\b(MAX|MIN)\(\s*([a-zA-Z_]\w*)\s*,',lambda m:m[1]+'('+table+'.'+m[2]+',',p,flags=re.I))
            sql=head+tail
    # SQLite accepts numeric predicates. No rewrite of literals or values.
    sql=outside(sql,lambda p:re.sub(r'\b(WHERE|AND|OR)\s+1(?=\s*(?:AND|OR|ORDER|GROUP|LIMIT|$))',r'\1 TRUE',p,flags=re.I))
    sql=outside(sql,lambda p:re.sub(r'\bLIMIT\s+-1\b','LIMIT ALL',p,flags=re.I))
    return outside(sql,lambda p:re.sub(r"\bREAL\b","DOUBLE PRECISION",p,flags=re.I))

def parameterized(sql):
    return outside(sql.replace('%','%%'),lambda p:p.replace('?', '%s'))

class Row:
    def __init__(self,names,values):
        self._names=names
        self._values=tuple(int(v) if isinstance(v,Decimal) and v==v.to_integral_value() else float(v) if isinstance(v,Decimal) else v for v in values)
    def keys(self):return self._names
    def __getitem__(self,key):return self._values[self._names.index(key)] if isinstance(key,str) else self._values[key]
    def __iter__(self):return iter(self._values)
    def __len__(self):return len(self._values)

class Cursor:
    def __init__(self,cursor,lastrowid=None):self.cursor=cursor;self.lastrowid=lastrowid
    @property
    def rowcount(self):return self.cursor.rowcount
    def _row(self,value):return None if value is None else Row(tuple(c.name for c in self.cursor.description),value)
    def fetchone(self):return self._row(self.cursor.fetchone())
    def fetchall(self):return [self._row(r) for r in self.cursor.fetchall()]
    def __iter__(self):
        for row in self.cursor:yield self._row(row)

class Connection:
    dialect='postgresql'
    def __init__(self,raw,release):self.raw=raw;self.release=release;self.closed=False
    @property
    def in_transaction(self):return self.raw.info.transaction_status.value!=0
    def execute(self,sql,params=()):
        statement=sql.strip()
        if statement.upper().startswith('PRAGMA'):
            raise RuntimeError('SQLite migration SQL cannot run against PostgreSQL; use migrate_postgres.py')
        if statement.upper() in ('BEGIN IMMEDIATE','BEGIN'):
            if self.in_transaction:raise sqlite3.OperationalError('transaction already active')
            self.raw.execute('BEGIN')
            # Preserve atomic legacy multi-resource read-modify-write operations.
            # Ordinary progress writes use row locking, not this compatibility lock.
            return Cursor(self.raw.execute('SELECT pg_advisory_xact_lock(812301, 1)'))
        compiled=translate(statement)
        mutation=bool(re.match(r'(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)',compiled,re.I))
        if mutation and not self.in_transaction:self.raw.execute('BEGIN')
        insert=re.match(r'INSERT INTO\s+(\w+)',compiled,re.I)
        returning=insert and insert[1] in IDENTITY_TABLES and not re.search(r'\bRETURNING\b',compiled,re.I)
        if returning:compiled+=' RETURNING id'
        try:
            cursor=self.raw.execute(parameterized(compiled),tuple(int(p) if isinstance(p,bool) else p for p in params))
            last=cursor.fetchone()[0] if returning and cursor.rowcount else None
            return Cursor(cursor,last)
        except IntegrityError as error:
            # Existing routes catch this portable boundary exception and roll back in teardown.
            raise sqlite3.IntegrityError('Database constraint violation') from error
    def executemany(self,sql,parameters):
        result=None
        for params in parameters:result=self.execute(sql,params)
        return result
    def executescript(self,script):
        raise RuntimeError('Use the versioned PostgreSQL migration runner')
    def commit(self):
        if self.in_transaction:self.raw.execute('COMMIT')
    def rollback(self):
        if self.in_transaction:self.raw.execute('ROLLBACK')
    def close(self):
        if not self.closed:
            self.rollback();self.closed=True;self.release(self.raw)
    def __enter__(self):return self
    def __exit__(self,kind,value,tb):
        try:self.rollback() if kind else self.commit()
        finally:self.close()

class Database:
    def __init__(self,url,min_size=1,max_size=12):
        self.pool=ConnectionPool(url,min_size=min_size,max_size=max_size,timeout=5,max_waiting=64,
            kwargs={'autocommit':True},configure=self.configure,open=True)
        self.pool.wait(timeout=10)
    @staticmethod
    def configure(connection):
        connection.execute("SET statement_timeout='10s'")
        connection.execute("SET lock_timeout='5s'")
        connection.execute("SET idle_in_transaction_session_timeout='15s'")
    def connect(self):return Connection(self.pool.getconn(),self.pool.putconn)
    def close(self):self.pool.close()
