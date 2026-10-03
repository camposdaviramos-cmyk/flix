import sys,tempfile,sqlite3,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from werkzeug.security import generate_password_hash
class MemberTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.app=create_app(self.tmp.name,testing=True);self.c=self.app.test_client();self.db=sqlite3.connect(Path(self.tmp.name)/'vyra.sqlite3')
  self.db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Test-password-123'),));self.db.execute("INSERT INTO content(id,title,kind,video_url,published,created_at) VALUES('channel-test','Canal de teste','channel','https://example.com/live.m3u8',1,?)",(time.time(),));self.db.commit();self.headers={'X-Requested-With':'VYRA'}
 def tearDown(self):self.db.close();self.tmp.cleanup()
 def login(self):
  r=self.c.post('/api/auth/login',json={'email':'admin@vyra.local','password':'Test-password-123'},headers=self.headers);self.assertEqual(r.status_code,200)
 def test_history_requires_authorized_play(self):
  self.assertEqual(self.c.get('/api/play/channel-test').status_code,401);self.assertEqual(self.c.get('/api/library').status_code,401);self.assertEqual(self.db.execute('SELECT COUNT(*) FROM watch_history').fetchone()[0],0)
 def test_recent_channels_are_private_and_deduplicated(self):
  self.login()
  for _ in range(3):self.assertEqual(self.c.get('/api/play/channel-test').status_code,200)
  library=self.c.get('/api/library').json;self.assertEqual([c['content_id'] for c in library['recent_channels']],['channel-test'])
  channel=next(i for i in self.c.get('/api/catalog').json['items'] if i['id']=='channel-test');self.assertEqual(channel['viewers'],1);self.assertNotIn('video_url',channel)
  other=self.app.test_client();r=other.post('/api/auth/register',json={'name':'Outro usuário','email':'other@example.com','password':'Other-password-123','plan_id':'premium'},headers=self.headers);self.assertEqual(r.status_code,200);self.assertEqual(other.get('/api/library').json['recent_channels'],[])
  self.assertEqual(other.get('/api/play/channel-test').status_code,402);self.assertEqual(self.db.execute('SELECT COUNT(*) FROM watch_history').fetchone()[0],1)
 def test_drafts_are_not_in_history_or_catalog(self):
  self.login();self.c.get('/api/play/channel-test');self.db.execute("UPDATE content SET published=0 WHERE id='channel-test'");self.db.commit()
  self.assertEqual(self.c.get('/api/library').json['recent_channels'],[]);self.assertEqual(self.c.get('/api/play/channel-test').status_code,404);self.assertNotIn('channel-test',[i['id'] for i in self.c.get('/api/catalog').json['items']])
 def test_progress_and_destinations(self):
  self.login();movie=self.db.execute("SELECT id FROM content WHERE kind='movie' LIMIT 1").fetchone()[0]
  self.c.get('/api/play/'+movie);r=self.c.put('/api/progress/'+movie,json={'position':18.5,'duration':150,'client_time':time.time()*1000},headers=self.headers);self.assertEqual(r.status_code,200)
  self.assertEqual(self.c.get('/api/library').json['progress'][0]['position'],18.5)
  recent=self.c.get('/api/library').json['recent_watched'];self.assertEqual(recent[0]['content_id'],movie);self.c.get('/api/play/channel-test');self.assertEqual([x['content_id'] for x in self.c.get('/api/library').json['recent_watched']],[ 'channel-test',movie])
  for path in ['/continuar','/planos','/filmes?view=featured','/series?view=top','/tv?view=recent']:self.assertEqual(self.c.get(path).status_code,200,path)
  self.assertEqual(self.c.get('/continuar').headers['X-Robots-Tag'],'noindex, nofollow')
if __name__=='__main__':unittest.main()
