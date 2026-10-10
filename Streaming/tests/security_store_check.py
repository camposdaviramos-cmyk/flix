"""Real Redis atomic counters, expiry and namespace isolation; no production keys."""
import concurrent.futures,sys,time,uuid,os,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from security_store import SecurityStore
store=SecurityStore(os.environ.get('WORKTV_TEST_REDIS_URL','redis://127.0.0.1:6379/15'),'worktv:test:'+uuid.uuid4().hex)
try:
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
  results=list(pool.map(lambda n:store.allow('login',[('ip',300),('account',15)],900),range(80)))
 assert sum(results)==15,results
 assert store.allow('expiry',[('value',1)],1)
 assert not store.allow('expiry',[('value',1)],1)
 time.sleep(1.1)
 assert store.allow('expiry',[('value',1)],1)
 print('PASS Redis: 80 concurrent attempts, exactly 15 accepted; independent TTL expiry.')
finally:
 for category,raw in [('login','ip'),('login','account'),('expiry','value')]:store.client.delete(store.namespace+':limit:'+category+':'+hashlib.sha256(raw.encode()).hexdigest())
 store.client.close()
