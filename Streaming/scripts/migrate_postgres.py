"""Offline SQLite -> PostgreSQL migration with counts, row digests and triggers.
Requires an empty destination schema. Source is opened read-only; no credentials
or row contents are written to the report. Stop writers before the final cutover.
"""
import argparse, base64, hashlib, json, os, re, sqlite3, sys
from pathlib import Path
import psycopg
from psycopg import sql
import sqlglot
from sqlglot import exp
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from postgres_backend import translate, outside

COMPAT = """
CREATE COLLATION IF NOT EXISTS nocase (provider=icu,locale='und-u-ks-level2',deterministic=false);
CREATE FUNCTION max(anycompatible,anycompatible) RETURNS anycompatible LANGUAGE SQL IMMUTABLE AS 'SELECT GREATEST($1,$2)';
CREATE FUNCTION min(anycompatible,anycompatible) RETURNS anycompatible LANGUAGE SQL IMMUTABLE AS 'SELECT LEAST($1,$2)';
CREATE FUNCTION instr(text,text) RETURNS integer LANGUAGE SQL IMMUTABLE AS 'SELECT strpos($1,$2)';
CREATE FUNCTION unixepoch() RETURNS bigint LANGUAGE SQL VOLATILE AS 'SELECT floor(extract(epoch from clock_timestamp()))::bigint';
CREATE FUNCTION strftime(fmt text, value text) RETURNS text LANGUAGE plpgsql VOLATILE AS $$
BEGIN IF fmt='%s' AND value='now' THEN RETURN unixepoch()::text; END IF;
RAISE EXCEPTION 'unsupported legacy date format'; END $$;
CREATE FUNCTION date(value double precision, mode text, shift text DEFAULT '') RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN IF mode!='unixepoch' OR shift NOT IN ('','-3 hours') THEN RAISE EXCEPTION 'unsupported legacy date'; END IF;
RETURN to_char(to_timestamp(value) AT TIME ZONE 'UTC' + CASE WHEN shift='' THEN interval '0 hours' ELSE interval '-3 hours' END,'YYYY-MM-DD'); END $$;
CREATE FUNCTION json_each(value text) RETURNS TABLE(value text) LANGUAGE SQL IMMUTABLE AS 'SELECT jsonb_array_elements_text($1::jsonb)';
"""
def q(value):return '"'+value.replace('"','""')+'"'
def normalized(value):
    if isinstance(value,(bytes,bytearray,memoryview)):return {'$binary':base64.b64encode(bytes(value)).decode('ascii')}
    if isinstance(value,float) and value.is_integer():return int(value)
    return value

def digest(rows):
    values=[]
    for row in rows:
        encoded=json.dumps([normalized(v) for v in row],ensure_ascii=False,separators=(',',':')).encode()
        values.append(hashlib.sha256(encoded).digest())
    return hashlib.sha256(b''.join(sorted(values))).hexdigest()

def statements(source):
    text=''
    for char in source:
        text+=char
        if char==';' and sqlite3.complete_statement(text):yield text.strip().rstrip(';');text=''
    if text.strip():yield text.strip().rstrip(';')

def trigger_sql(source):
    m=re.fullmatch(r'CREATE TRIGGER(?: IF NOT EXISTS)?\s+(\w+)\s+AFTER\s+(.*?)\s+ON\s+(\w+)\s+(?:WHEN\s+(.*?)\s+)?BEGIN\s+(.*?)\s*END\s*;?',source,re.I|re.S)
    if not m:raise ValueError('Unsupported trigger declaration')
    name,event,table,condition,body=m.groups();condition='TRUE' if not condition or condition.strip()=='1' else condition
    compiled=[]
    for statement in statements(body):
        s=translate(statement)
        s=outside(s,lambda p:re.sub(r'\bAS REAL\b','AS DOUBLE PRECISION',p,flags=re.I))
        if name=='hub_streak':
            s=s.replace('NEW.sender<NEW.recipient','(NEW.sender<NEW.recipient)::integer').replace('NEW.sender>NEW.recipient','(NEW.sender>NEW.recipient)::integer')
        compiled.append(s+';')
    function='trigger_'+name
    return f'CREATE FUNCTION {q(function)}() RETURNS trigger LANGUAGE plpgsql SET search_path=public,pg_temp AS $worktv$ BEGIN IF {condition} THEN '+''.join(compiled)+f' END IF; RETURN NEW; END $worktv$; CREATE TRIGGER {q(name)} AFTER {event} ON {q(table)} FOR EACH ROW EXECUTE FUNCTION {q(function)}();'

def migrate(source,dsn,report):
    source=Path(source).resolve()
    db=sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True)
    violations=db.execute('PRAGMA foreign_key_check').fetchall()
    if violations:raise RuntimeError('Source has foreign-key violations; migration aborted (no rows exported).')
    objects=[dict(zip(['type','name','table','sql'],r)) for r in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    tables=[o for o in objects if o['type']=='table'];result={'tables':[],'source_integrity':db.execute('PRAGMA integrity_check').fetchone()[0]}
    if result['source_integrity']!='ok':raise RuntimeError('Source integrity check failed')
    with psycopg.connect(dsn) as pg:
        if pg.execute("SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() LIMIT 1").fetchone():raise RuntimeError('Destination is not empty; refusing destructive migration')
        pg.execute(COMPAT)
        constraints=[];indexes=[];identities=[]
        for table in tables:
            name=table['name'];cols=db.execute('PRAGMA table_info('+q(name)+')').fetchall();parts=[]
            for cid,col,typ,required,default,pk in cols:
                kind='double precision' if typ.upper() in ('REAL','FLOAT','DOUBLE') else 'bigint' if 'INT' in typ.upper() else 'bytea' if typ.upper()=='BLOB' else 'text'
                definition=q(col)+' '+kind
                if 'AUTOINCREMENT' in table['sql'].upper() and pk:
                    definition+=' GENERATED BY DEFAULT AS IDENTITY';identities.append((name,col))
                if kind=='text' and re.search(r'\b'+re.escape(col)+r'\s+TEXT\b[^,)]*\bCOLLATE\s+NOCASE',table['sql'],re.I):definition+=' COLLATE nocase'
                if required or pk:definition+=' NOT NULL'
                if default is not None:definition+=' DEFAULT '+default
                parts.append(definition)
            primary=[c[1] for c in sorted(cols,key=lambda c:c[5]) if c[5]]
            if primary:parts.append('PRIMARY KEY ('+','.join(map(q,primary))+')')
            parsed=sqlglot.parse_one(table['sql'],read='sqlite')
            for check in parsed.find_all(exp.CheckColumnConstraint):parts.append('CHECK ('+check.this.sql(dialect='postgres')+')')
            pg.execute('CREATE TABLE '+q(name)+' ('+','.join(parts)+')')
            foreign={}
            for row in db.execute('PRAGMA foreign_key_list('+q(name)+')'):foreign.setdefault(row[0],[]).append(row)
            for rows in foreign.values():
                rows.sort(key=lambda r:r[1]);first=rows[0]
                constraints.append('ALTER TABLE '+q(name)+' ADD FOREIGN KEY ('+','.join(q(r[3]) for r in rows)+') REFERENCES '+q(first[2])+' ('+','.join(q(r[4]) for r in rows)+') ON UPDATE '+first[5]+' ON DELETE '+first[6]+' DEFERRABLE INITIALLY IMMEDIATE')
            for idx in db.execute('PRAGMA index_list('+q(name)+')'):
                if idx[3]=='pk':continue
                original=db.execute('SELECT sql FROM sqlite_master WHERE name=?',(idx[1],)).fetchone()[0]
                if original:indexes.append(original)
                else:
                    names=[r[2] for r in db.execute('PRAGMA index_info('+q(idx[1])+')')]
                    indexes.append('CREATE UNIQUE INDEX '+q(idx[1])+' ON '+q(name)+' ('+','.join(map(q,names))+')')
            columns=[c[1] for c in cols];rows=db.execute('SELECT * FROM '+q(name)).fetchall()
            with pg.cursor().copy('COPY '+q(name)+' ('+','.join(map(q,columns))+') FROM STDIN') as copy:
                for row in rows:copy.write_row(row)
            loaded=pg.execute('SELECT '+','.join(map(q,columns))+' FROM '+q(name)).fetchall()
            if len(rows)!=len(loaded) or digest(rows)!=digest(loaded):raise RuntimeError('Row comparison failed for '+name)
            result['tables'].append({'name':name,'rows':len(rows),'digest':digest(rows),'verified':True})
        for index in indexes:pg.execute(index)
        for constraint in constraints:pg.execute(constraint)
        for name,col in identities:
            maximum=pg.execute('SELECT MAX('+q(col)+') FROM '+q(name)).fetchone()[0]
            sequence=pg.execute('SELECT pg_get_serial_sequence(%s,%s)',(name,col)).fetchone()[0]
            pg.execute('SELECT setval(%s,%s,%s)',(sequence,maximum or 1,maximum is not None))
        for obj in objects:
            if obj['type']=='trigger':pg.execute(trigger_sql(obj['sql']).replace('search_path=public,pg_temp','search_path='+q(pg.execute('SELECT current_schema()').fetchone()[0])+',pg_temp'))
        pg.execute('CREATE TABLE worktv_schema_version(version bigint PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())')
        pg.execute('INSERT INTO worktv_schema_version(version) VALUES(1)')
        result.update(table_count=len(tables),trigger_count=sum(o['type']=='trigger' for o in objects),row_count=sum(t['rows'] for t in result['tables']))
    db.close();Path(report).write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    value=migrate(a.source,os.environ['WORKTV_MIGRATION_DATABASE_URL'],a.report)
    print(json.dumps({k:v for k,v in value.items() if k!='tables'}))
