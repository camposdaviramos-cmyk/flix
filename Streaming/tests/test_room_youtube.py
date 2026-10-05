"""Mobile share URLs and atomically opening the first media in a room."""
import unittest
import test_community as fixtures

class RoomYoutubeTests(unittest.TestCase):
 setUp=fixtures.CommunityTests.setUp
 tearDown=fixtures.CommunityTests.tearDown
 call=fixtures.CommunityTests.call
 user=fixtures.CommunityTests.user
 def create(self):
  r=self.call(self.a,'/community/rooms',{'kind':'video','title':'Teste','approval':False})
  self.assertEqual(r.status_code,201,r.json)
  return '/community/rooms/'+r.json['room']['id']
 def test_mobile_share_variants_are_playable_sources(self):
  path=self.create()
  links=['https://youtu.be/ROYmf8KSXdE?si=KW6tOaHIWgt9V5nZ','https://m.youtube.com/watch?v=ROYmf8KSXdE&feature=shared','https://www.youtube.com/shorts/ROYmf8KSXdE?si=abc','https://www.youtube.com/live/ROYmf8KSXdE?feature=share']
  for link in links:
   r=self.call(self.a,path+'/experience/queue',{'url':link,'lane':'video','start_now':True})
   self.assertEqual(r.status_code,201,r.json);self.assertTrue(r.json['started'])
   room=self.call(self.a,path+'/poll').json['room']
   self.assertEqual(room['url'],'https://www.youtube.com/watch?v=ROYmf8KSXdE');self.assertEqual(room['media_type'],'youtube');self.assertFalse(room['paused']);self.assertEqual(room['queue'],[])
 def test_queue_only_and_guest_cannot_replace_media(self):
  path=self.create();self.call(self.b,path+'/join')
  data={'url':'https://youtu.be/ROYmf8KSXdE?si=KW6tOaHIWgt9V5nZ','lane':'video'}
  r=self.call(self.b,path+'/experience/queue',{**data,'start_now':True});self.assertEqual(r.status_code,403)
  r=self.call(self.b,path+'/experience/queue',data);self.assertEqual(r.status_code,201,r.json);self.assertFalse(r.json['started'])
  room=self.call(self.a,path+'/poll').json['room'];self.assertEqual(room['url'],'');self.assertEqual(len(room['queue']),1)
  for link in ['https://youtu.be/short?si=abc','https://youtube.com.evil.test/watch?v=ROYmf8KSXdE']:
   self.assertEqual(self.call(self.a,path+'/experience/queue',{**data,'url':link,'start_now':True}).status_code,400)
  self.assertEqual(len(self.call(self.a,path+'/poll').json['room']['queue']),1)
 def test_youtube_soundtrack_independent_start(self):
  path=self.create();self.call(self.b,path+'/join');link='https://youtu.be/ROYmf8KSXdE?si=KW6tOaHIWgt9V5nZ'
  r=self.call(self.a,path+'/experience/queue',{'url':link,'lane':'music','start_now':True});self.assertEqual(r.status_code,201,r.json)
  audio=self.a.get('/api'+path+'/experience').json['audio'];self.assertEqual(audio['current_id'],r.json['id']);self.assertFalse(audio['paused']);self.assertEqual(audio['queue'][0]['media_type'],'youtube')
  self.assertEqual(self.call(self.a,path+'/poll').json['room']['url'],'')
  self.assertEqual(self.call(self.b,path+'/experience/queue',{'url':link,'lane':'music','start_now':True}).status_code,403)
if __name__=='__main__':unittest.main()
