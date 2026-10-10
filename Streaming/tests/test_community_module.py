"""The module boundary must hold even when clients bypass the navigation."""
import sqlite3,sys,tempfile,unittest,re
from pathlib import Path
from unittest.mock import Mock
from werkzeug.security import generate_password_hash
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
import community_module,flix_push

class CommunityModuleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.app=create_app(self.temp.name,testing=True)
  self.db=sqlite3.connect(Path(self.temp.name)/'vyra.sqlite3');self.db.row_factory=sqlite3.Row
  self.password='Module-test-password-2026';self.h={'X-Requested-With':'Flix'}
  self.db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash(self.password),));self.db.commit()
  self.admin=self.app.test_client();self.guest=self.app.test_client()
  self.assertEqual(self.admin.post('/api/auth/login',json={'email':'admin@vyra.local','password':self.password},headers=self.h).status_code,200)
 def tearDown(self):self.db.close();self.temp.cleanup()
 def switch(self,value):return self.admin.put('/api/admin/modules/community',json={'enabled':value},headers=self.h)
 def test_default_persistence_restore_and_preserved_data(self):
  self.assertTrue(self.guest.get('/api/bootstrap').json['modules']['community'])
  counts={name:self.db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in ['users','community_posts','community_rooms','content']}
  self.assertEqual(self.switch(False).status_code,200)
  self.assertFalse(self.admin.get('/api/admin/modules/community').json['enabled'])
  if getattr(self.db,'dialect','sqlite')=='postgresql':
   with self.app.extensions['connect_db']() as fresh:self.assertFalse(community_module.enabled(fresh))
  else:
   restarted=create_app(self.temp.name,testing=True).test_client()
   self.assertFalse(restarted.get('/api/bootstrap').json['modules']['community'])
  self.assertEqual(counts,{name:self.db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in counts})
  self.assertEqual(self.switch(True).status_code,200)
  self.assertTrue(self.guest.get('/api/client-version').json['modules']['community'])
  self.assertEqual(self.guest.get('/comunidade').status_code,200)
  self.assertEqual(self.admin.get('/api/community/feed').status_code,200)
 def test_all_registered_social_routes_and_direct_pages_blocked(self):
  self.switch(False);tested=0
  for rule in self.app.url_map.iter_rules():
   if not community_module.matches(rule.rule,community_module.API_ROOTS):continue
   path=re.sub(r'<(?:[^:>]+:)?[^>]+>','123456789012',rule.rule)
   for method in rule.methods-{'HEAD','OPTIONS'}:
    response=self.admin.open(path,method=method,json={},headers=self.h)
    self.assertEqual(response.status_code,503,(method,path,response.data))
    self.assertEqual(response.json['code'],'community_disabled');tested+=1
  self.assertGreater(tested,100)
  for path in ['/comunidade','/comunidade/perfil/admin','/comunidade/sala/123456789012','/sala/123456789012','/carteira']:
   response=self.guest.get(path);self.assertEqual(response.status_code,503)
   self.assertIn('no-store',response.headers['Cache-Control']);self.assertIn(b'Voltar',response.data)
 def test_authorization_csrf_validation_and_admin_mfa(self):
  self.assertEqual(self.guest.put('/api/admin/modules/community',json={'enabled':False},headers=self.h).status_code,401)
  user=self.app.test_client();self.assertEqual(user.post('/api/auth/register',json={'name':'Member Test','email':'member@example.test','password':self.password,'account_type':'community'},headers=self.h).status_code,200)
  self.assertEqual(user.put('/api/admin/modules/community',json={'enabled':False},headers=self.h).status_code,403)
  self.assertEqual(self.admin.put('/api/admin/modules/community',json={'enabled':False}).status_code,403)
  self.assertEqual(self.admin.put('/api/admin/modules/community',json={'enabled':False},headers={**self.h,'Origin':'https://attacker.invalid'}).status_code,403)
  for value in ['false',0,1,None,[],{}]:self.assertEqual(self.switch(value).status_code,400)
  self.assertTrue(self.guest.get('/api/bootstrap').json['modules']['community'])
  self.app.config['ADMIN_MFA_REQUIRED']=True;self.assertEqual(self.switch(False).status_code,403)
 def test_streaming_access_remains_available_and_social_purchase_blocked(self):
  self.switch(False)
  for path in ['/','/catalogo','/conta','/perfis','/escanear','/admin?tab=modules','/api/catalog','/api/library','/api/profiles','/api/orders','/api/play/horizonte']:
   self.assertEqual(self.admin.get(path).status_code,200,path)
  self.assertEqual(self.guest.post('/api/auth/device/start',json={},headers=self.h).status_code,200)
  self.assertEqual(self.guest.post('/api/auth/register',json={'name':'Another Member','email':'another@example.test','password':self.password,'account_type':'community'},headers=self.h).status_code,503)
  self.assertEqual(self.admin.post('/api/checkout',json={'package_id':'any'},headers=self.h).json['code'],'community_disabled')
  self.assertEqual(self.guest.post('/api/auth/register',json={'name':'Subscriber','email':'subscriber@example.test','password':self.password,'plan_id':'essencial'},headers=self.h).status_code,200)
 def test_push_delivery_paused(self):
  self.switch(False);send=Mock();flix_push.deliver(self.db,Path(self.temp.name),send=send);send.assert_not_called()

if __name__=='__main__':unittest.main()
