import concurrent.futures,json,sqlite3,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from public_cache import PublicCatalogCache
from proxy_security import LocalProxyHeaders
from werkzeug.security import generate_password_hash
from werkzeug.test import Client
from werkzeug.wrappers import Response,Request
class CacheTests(unittest.TestCase):
 def test_single_flight_expiry_invalidation_and_bound(self):
  cache=PublicCatalogCache(ttl=.03,max_bytes=10);calls=[]
  def build():calls.append(1);time.sleep(.01);return b'catalog'
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:self.assertEqual(set(pool.map(lambda _:cache.get(build),range(8))),{b'catalog'})
  self.assertEqual(len(calls),1);cache.invalidate();cache.get(build);self.assertEqual(len(calls),2);time.sleep(.04);cache.get(build);self.assertEqual(len(calls),3)
  cache.invalidate();cache.get(lambda:b'x'*11);self.assertIsNone(cache._value)
class SecurityTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.app=create_app(self.temp.name,testing=True);self.client=self.app.test_client();self.headers={'X-Requested-With':'VYRA'}
  with sqlite3.connect(Path(self.temp.name)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Test-security-only-2026'),))
  db.close()
 def tearDown(self):self.temp.cleanup()
 def login(self,**kwargs):return self.client.post('/api/auth/login',json={'email':'admin@vyra.local','password':'Test-security-only-2026'},headers={**self.headers,**kwargs})
 def test_https_cookie_and_hsts(self):
  r=self.login(**{'X-Forwarded-Proto':'https','X-Forwarded-For':'203.0.113.2'});self.assertEqual(r.status_code,200);self.assertIn('Secure',r.headers['Set-Cookie']);self.assertIn('HttpOnly',r.headers['Set-Cookie']);self.assertIn('SameSite=Lax',r.headers['Set-Cookie']);self.assertEqual(r.headers['Strict-Transport-Security'],'max-age=31536000')
 def test_cross_site_write_rejected(self):
  self.assertEqual(self.login(**{'Sec-Fetch-Site':'cross-site'}).status_code,403)
 def test_proxy_headers_only_from_loopback(self):
  @Request.application
  def endpoint(request):return Response(json.dumps({'peer':request.remote_addr,'scheme':request.scheme}))
  client=Client(LocalProxyHeaders(endpoint));headers={'X-Forwarded-For':'198.51.100.9','X-Forwarded-Proto':'https'}
  direct=json.loads(client.get('/',headers=headers,environ_overrides={'REMOTE_ADDR':'203.0.113.10'}).text);self.assertEqual(direct,{'peer':'203.0.113.10','scheme':'http'})
  proxied=json.loads(client.get('/',headers=headers,environ_overrides={'REMOTE_ADDR':'127.0.0.1'}).text);self.assertEqual(proxied,{'peer':'198.51.100.9','scheme':'https'})
 def test_login_buckets_are_isolated_and_atomic(self):
  def attempt(_):
   with self.app.test_client() as client:return client.post('/api/auth/login',json={'email':'missing@example.test','password':'wrong'},headers={**self.headers,'X-Forwarded-For':'203.0.113.2'}).status_code
  with patch('app.check_password_hash',return_value=False):
   with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:codes=list(pool.map(attempt,range(20)))
   self.assertEqual(codes.count(401),15);self.assertEqual(codes.count(429),5)
   other=self.client.post('/api/auth/login',json={'email':'missing@example.test','password':'wrong'},headers={**self.headers,'X-Forwarded-For':'203.0.113.3'});self.assertEqual(other.status_code,401)
  self.assertEqual(self.login(**{'X-Forwarded-For':'203.0.113.2'}).status_code,200)
 def test_catalog_cache_has_no_identity_and_invalidates_on_admin_write(self):
  first=self.client.get('/api/catalog');self.assertEqual(first.headers['Cache-Control'],'no-store')
  self.login();second=self.client.get('/api/catalog');self.assertEqual(first.data,second.data);self.assertNotIn(b'admin@',second.data)
  cid=first.json['items'][0]['id'];r=self.client.delete('/api/admin/content/'+cid,headers=self.headers);self.assertEqual(r.status_code,200);self.assertNotIn(cid,{item['id'] for item in self.client.get('/api/catalog').json['items']})
 def test_missing_user_still_checks_password(self):
  with patch('app.check_password_hash',return_value=False) as check:
   response=self.client.post('/api/auth/login',json={'email':'missing@example.test','password':'wrong'},headers=self.headers);self.assertEqual(response.status_code,401);check.assert_called_once()
if __name__=='__main__':unittest.main()
