import concurrent.futures,json,sqlite3,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import pyotp
from werkzeug.security import generate_password_hash
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app

class AccountAccessTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.app=create_app(self.temp.name,testing=True);self.phone=self.app.test_client();self.tv=self.app.test_client();self.h={'X-Requested-With':'Flix'};self.password='Test-access-12345'
  self.db=sqlite3.connect(Path(self.temp.name)/'vyra.sqlite3');self.db.row_factory=sqlite3.Row
  self.db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash(self.password),));self.db.commit();self.user=self.login(self.phone).json['user']
 def tearDown(self):self.db.close();self.temp.cleanup()
 def post(self,c,path,body={},method='POST'):return c.open('/api'+path,method=method,json=body,headers=self.h)
 def login(self,c,code=None):return self.post(c,'/auth/login',{'email':'admin@vyra.local','password':self.password,**({'code':code} if code else {})})
 def enroll(self):
  r=self.post(self.phone,'/auth/mfa/setup',{'password':self.password});self.assertEqual(r.status_code,200,r.json);secret=r.json['secret']
  r=self.post(self.phone,'/auth/mfa/enable',{'code':pyotp.TOTP(secret).now()});self.assertEqual(r.status_code,200,r.json);return secret,r.json['recovery_codes']
 def grant(self):
  r=self.post(self.tv,'/auth/device/start',{'kind':'tv'});self.assertEqual(r.status_code,200,r.json);return r.json,r.json['activation_url'].split('#')[1]
 def test_device_requires_authenticated_explicit_approval_and_bound_cookie(self):
  grant,token=self.grant();self.assertTrue(grant['qr'].startswith('data:image/svg+xml;base64,'));self.assertNotIn(token,self.db.execute('SELECT approval_hash FROM device_logins').fetchone()[0])
  stranger=self.app.test_client();self.assertEqual(self.post(stranger,'/auth/device/details',{'token':token}).status_code,401)
  self.assertEqual(self.post(stranger,'/auth/device/poll',{'id':grant['id']}).status_code,410)
  self.assertEqual(self.post(self.tv,'/auth/device/poll',{'id':grant['id']}).json['status'],'pending')
  self.assertEqual(self.post(self.phone,'/auth/device/approve',{'token':token,'code':'invalid','confirmed':True}).status_code,400)
  self.assertEqual(self.post(self.phone,'/auth/device/approve',{'token':token,'code':grant['code'],'confirmed':True}).status_code,200)
  accepted=self.post(self.tv,'/auth/device/poll',{'id':grant['id']});self.assertEqual(accepted.status_code,200,accepted.json);self.assertEqual(accepted.json['user']['id'],self.user['id']);self.assertTrue(self.tv.get_cookie('vyra_session').http_only)
  self.assertEqual(self.post(self.tv,'/auth/device/poll',{'id':grant['id']}).status_code,410)
  self.assertEqual(self.post(self.phone,'/auth/device/approve',{'token':token,'code':grant['code'],'confirmed':True}).status_code,410)
 def test_expiry_denial_and_cross_site_device_creation(self):
  r=self.tv.post('/api/auth/device/start',json={},headers={**self.h,'Sec-Fetch-Site':'cross-site'});self.assertEqual(r.status_code,403)
  grant,token=self.grant();self.assertEqual(self.post(self.phone,'/auth/device/deny',{'token':token}).status_code,200);self.assertEqual(self.post(self.tv,'/auth/device/poll',{'id':grant['id']}).json['status'],'denied')
  grant,token=self.grant();self.db.execute('UPDATE device_logins SET expires_at=0');self.db.commit();self.assertEqual(self.post(self.phone,'/auth/device/details',{'token':token}).status_code,410);self.assertEqual(self.post(self.tv,'/auth/device/poll',{'id':grant['id']}).status_code,410)
 def test_profiles_max_three_even_concurrently(self):
  token=self.phone.get_cookie('vyra_session').value
  def create(n):
   client=self.app.test_client();client.set_cookie('vyra_session',token);return self.post(client,'/profiles',{'name':'Profile '+str(n),'avatar':'blue'}).status_code
  with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:codes=list(executor.map(create,range(6)))
  self.assertEqual(codes.count(201),2);self.assertEqual(codes.count(409),4);self.assertEqual(len(self.phone.get('/api/profiles').json['profiles']),3)
 def test_profile_lists_history_and_progress_are_isolated(self):
  original=self.phone.get('/api/bootstrap').json['profile']['id'];created=self.post(self.phone,'/profiles',{'name':'Segundo','avatar':'purple'}).json['profile']['id']
  self.assertEqual(self.post(self.phone,'/favorites/horizonte').status_code,200)
  self.assertEqual(self.post(self.phone,'/progress/horizonte',{'position':52,'duration':100,'client_time':time.time()*1000},'PUT').status_code,200)
  self.phone.get('/api/play/horizonte')
  self.post(self.phone,'/profiles/'+created+'/select');library=self.phone.get('/api/library').json;self.assertEqual(library['favorites'],[]);self.assertEqual(library['progress'],[]);self.assertEqual(library['recent_watched'],[])
  self.post(self.phone,'/profiles/'+original+'/select');self.assertEqual(self.phone.get('/api/library').json['progress'][0]['position'],52)
  other=self.app.test_client();r=self.post(other,'/auth/register',{'name':'Other Account','username':'other_account','email':'other@example.test','password':self.password,'account_type':'community'});self.assertEqual(r.status_code,200,r.json)
  for path,method,body in [('/profiles/'+original+'/select','POST',{}),('/profiles/'+original,'PATCH',{'name':'Attack','avatar':'blue'}),('/profiles/'+original,'DELETE',{})]:self.assertEqual(self.post(other,path,body,method).status_code,404)
 def test_revoking_approver_session_cancels_unclaimed_grant(self):
  grant,token=self.grant();self.post(self.phone,'/auth/device/approve',{'token':token,'code':grant['code'],'confirmed':True})
  self.post(self.phone,'/auth/logout');self.assertEqual(self.post(self.tv,'/auth/device/poll',{'id':grant['id']}).status_code,410)
 def test_stale_progress_cannot_write_to_new_profile(self):
  original=self.phone.get('/api/bootstrap').json['profile']['id'];created=self.post(self.phone,'/profiles',{'name':'Segundo','avatar':'purple'}).json['profile']['id']
  self.post(self.phone,'/profiles/'+created+'/select')
  self.assertEqual(self.post(self.phone,'/progress/horizonte',{'profile_id':original,'position':52,'duration':100,'client_time':time.time()*1000},'PUT').status_code,409)
  self.assertEqual(self.phone.get('/api/library').json['progress'],[])
 def test_last_profile_cannot_be_deleted(self):
  profile=self.phone.get('/api/bootstrap').json['profile']['id'];self.assertEqual(self.post(self.phone,'/profiles/'+profile,{},'DELETE').status_code,409)
 def test_mfa_setup_requires_password_and_login_never_issues_session_without_factor(self):
  self.assertEqual(self.post(self.phone,'/auth/mfa/setup',{'password':'wrong'}).status_code,401)
  secret,codes=self.enroll();self.assertEqual(len(codes),10);self.assertNotIn(secret,self.db.execute('SELECT secret FROM account_mfa').fetchone()[0])
  r=self.login(self.tv);self.assertTrue(r.json['mfa_required']);self.assertIsNone(self.tv.get_cookie('vyra_session'))
  self.assertEqual(self.login(self.tv,'not-a-code').status_code,401)
  self.assertEqual(self.login(self.tv,codes[0]).status_code,200)
  fresh=self.app.test_client();self.assertEqual(self.login(fresh,codes[0]).status_code,401)
  self.assertEqual(self.phone.get('/api/auth/security').json['recovery_codes'],9)
 def test_totp_replay_and_admin_requirement(self):
  self.app.config['ADMIN_MFA_REQUIRED']=True;self.assertEqual(self.phone.get('/api/admin/users').status_code,403);self.assertEqual(self.phone.get('/api/community/feed').status_code,403);self.assertTrue(self.phone.get('/api/bootstrap').json['admin_setup_required'])
  secret,codes=self.enroll();self.assertEqual(self.phone.get('/api/admin/users').status_code,200)
  future=time.time()+60
  with patch('auth_security.time.time',return_value=future):
   code=pyotp.TOTP(secret).at(future);self.assertEqual(self.login(self.tv,code).status_code,200);self.assertEqual(self.login(self.app.test_client(),code).status_code,401)
  self.assertEqual(self.post(self.phone,'/auth/mfa/disable',{'password':self.password,'code':codes[0]}).status_code,403)
 def test_enabling_mfa_revokes_other_sessions_and_rotation_requires_factor(self):
  self.login(self.tv);self.assertIsNotNone(self.tv.get_cookie('vyra_session'));secret,codes=self.enroll();self.assertIsNone(self.tv.get('/api/bootstrap').json['user'])
  self.assertEqual(self.post(self.phone,'/auth/mfa/setup',{'password':self.password}).status_code,401)
  self.assertEqual(self.post(self.phone,'/auth/mfa/setup',{'password':self.password,'code':codes[0]}).status_code,200)
if __name__=='__main__':unittest.main()
