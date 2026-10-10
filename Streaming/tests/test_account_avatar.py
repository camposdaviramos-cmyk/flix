import base64,sqlite3,struct,sys,tempfile,unittest,zlib
from pathlib import Path
from werkzeug.security import generate_password_hash
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app

def sample_png():
 def chunk(kind,body):return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body))
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',2,2,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\x00'+b'\x00\x80\xff\xff'*2)*2))+chunk(b'IEND',b'')
class AccountAvatarTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.app=create_app(self.temp.name,testing=True);self.c=self.app.test_client();self.h={'X-Requested-With':'Flix'}
  self.db=sqlite3.connect(Path(self.temp.name)/'vyra.sqlite3');self.db.row_factory=sqlite3.Row
  self.db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('avatar-test-password'),));self.db.commit()
  self.uid=self.c.post('/api/auth/login',json={'email':'admin@vyra.local','password':'avatar-test-password'},headers=self.h).json['user']['id']
  self.c.put('/api/admin/modules/community',json={'enabled':False},headers=self.h)
 def tearDown(self):self.db.close();self.temp.cleanup()
 def upload(self,blob):return self.c.put('/api/account/avatar',json={'avatar':'data:image/png;base64,'+base64.b64encode(blob).decode()},headers=self.h)
 def test_upload_read_remove_independent_of_community(self):
  blob=sample_png();self.assertEqual(self.upload(blob).status_code,200)
  avatar=self.c.get('/api/bootstrap').json['user']['avatar'];self.assertTrue(avatar.startswith('/api/account/avatar?v='))
  image=self.c.get(avatar);self.assertEqual(image.data,blob);self.assertEqual(image.mimetype,'image/png');self.assertEqual(image.headers['Cache-Control'],'no-store')
  self.assertEqual(self.c.get('/api/community/avatars/'+self.uid).status_code,503)
  self.assertEqual(self.c.delete('/api/account/avatar',headers=self.h).status_code,200)
  self.assertEqual(self.c.get('/api/bootstrap').json['user']['avatar'],'');self.assertEqual(self.c.get('/api/account/avatar').status_code,404)
 def test_existing_photo_survives_module_disable_and_other_fields_preserved(self):
  self.db.execute('INSERT INTO community_profiles(user_id,avatar,avatar_png,bio,updated_at) VALUES(?,?,?,?,?)',(self.uid,'/api/community/avatars/'+self.uid+'?v=1',sample_png(),'Preserve bio',1));self.db.commit()
  self.assertEqual(self.c.get(self.c.get('/api/bootstrap').json['user']['avatar']).status_code,200)
  self.upload(sample_png());self.assertEqual(self.db.execute('SELECT bio FROM community_profiles WHERE user_id=?',(self.uid,)).fetchone()[0],'Preserve bio')
 def test_invalid_images_and_unauthorized_access(self):
  for blob in [b'',b'<svg/>',sample_png()[:-2],sample_png()+b'junk',b'\x89PNG\r\n\x1a\n'+b'x'*300001]:self.assertEqual(self.upload(blob).status_code,400)
  self.assertEqual(self.c.put('/api/account/avatar',json={'avatar':None},headers=self.h).status_code,400)
  self.assertEqual(self.c.delete('/api/account/avatar').status_code,403)
  guest=self.app.test_client()
  for method in ['GET','PUT','DELETE']:self.assertEqual(guest.open('/api/account/avatar',method=method,json={},headers=self.h).status_code,401)
  self.upload(sample_png());other=self.app.test_client();self.assertEqual(other.post('/api/auth/register',json={'name':'Another Subscriber','email':'avatar-other@example.test','password':'Another-password-2026','plan_id':'essencial'},headers=self.h).status_code,200)
  self.assertEqual(other.get('/api/account/avatar').status_code,404)
  self.assertEqual(other.get('/api/account/avatar?user='+self.uid).status_code,404)
  self.assertEqual(other.put('/api/account/avatar',json={'avatar':'data:image/png;base64,'+base64.b64encode(sample_png()).decode()},headers=self.h).status_code,200)
  account=next(u for u in self.c.get('/api/admin/users').json['users'] if u['email']=='avatar-other@example.test')
  self.assertFalse(account['avatar'].startswith('/api/account/avatar?'))
if __name__=='__main__':unittest.main()
