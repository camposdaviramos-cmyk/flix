"""Run existing API regression fixtures against isolated PostgreSQL schemas.
Every test gets its own migrated database schema, preserving existing SQLite
fixtures while exercising real PostgreSQL SQL, transactions and triggers.
"""
import argparse,contextlib,hashlib,os,sqlite3,sys,unittest,uuid
from pathlib import Path
import psycopg
from psycopg.conninfo import make_conninfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import app as application
from migrate_postgres import migrate
original_create=application.create_app;original_connect=sqlite3.connect
registry={};resources=[];preparing=False
DSN=os.environ['WORKTV_TEST_DATABASE_URL']

def connect(path,*args,**kwargs):
    key=str(Path(path).resolve()) if isinstance(path,(str,Path)) and not str(path).startswith('file:') else str(path)
    if not preparing and key in registry:return registry[key].connect()
    return original_connect(path,*args,**kwargs)

def create(data_dir=None,testing=False,**kwargs):
    global preparing
    if not testing:return original_create(data_dir,testing,**kwargs)
    schema='test_'+uuid.uuid4().hex
    with psycopg.connect(DSN,autocommit=True) as connection:connection.execute('CREATE SCHEMA '+schema)
    dsn=make_conninfo(DSN,options='-c search_path='+schema)
    preparing=True
    try:
        original_create(data_dir,testing=True)
        migrate(Path(data_dir)/'vyra.sqlite3',dsn,Path(data_dir)/'pg-report.json')
    finally:preparing=False
    result=original_create(data_dir,testing=True,database_url=dsn)
    registry[str((Path(data_dir)/'vyra.sqlite3').resolve())]=result.extensions['database']
    resources.append((schema,result.extensions['database']))
    return result

def cleanup():
    registry.clear()
    while resources:
        schema,database=resources.pop();database.close()
        with psycopg.connect(DSN,autocommit=True) as connection:connection.execute('DROP SCHEMA '+schema+' CASCADE')

def walk(suite):
    for test in suite:
        if isinstance(test,unittest.TestSuite):yield from walk(test)
        else:yield test

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--pattern',default='test_*.py');a=parser.parse_args()
    application.create_app=create;sqlite3.connect=connect
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=a.pattern)
    for test in walk(suite):
        if test._testMethodName in {'test_legacy_brand_migration_preserves_other_settings','test_music_admin_and_legacy_room_migration_is_idempotent','test_catalog_queries_do_not_grow_with_titles_and_do_not_leak_sources'}:
            def sqlite_only():raise unittest.SkipTest('SQLite-specific migration/trace; source backend suite covers it; PostgreSQL migration has separate digest/trigger checks')
            setattr(test,test._testMethodName,sqlite_only)
        previous=test.tearDown
        def teardown(previous=previous):
            try:previous()
            finally:cleanup()
        test.tearDown=teardown
    try:result=unittest.TextTestRunner(verbosity=2).run(suite)
    finally:cleanup()
    sys.exit(not result.wasSuccessful())
