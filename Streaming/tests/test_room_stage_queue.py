"""Stage requests and idempotent, host-controlled continuation of both room queues."""
import time
import unittest
import test_community as fixtures
import test_social_evolution as evolution

class RoomStageQueueTests(unittest.TestCase):
 setUp=fixtures.CommunityTests.setUp
 tearDown=fixtures.CommunityTests.tearDown
 call=fixtures.CommunityTests.call
 user=fixtures.CommunityTests.user
 music=evolution.EvolutionTests.music
 def create(self,kind='video',**extra):
  r=self.call(self.a,'/community/rooms',{'kind':kind,'title':'Sessão em sequência','approval':False,**({'url':'https://example.com/first.mp4'} if kind=='watch' else {}),**extra})
  self.assertEqual(r.status_code,201,r.json)
  self.path='/community/rooms/'+r.json['room']['id'];self.rid=r.json['room']['id']
  return r.json['room']
 def poll(self,client=None):return self.call(client or self.a,self.path+'/poll').json['room']
 def member(self,room,uid):return next(u for u in room['members'] if u['id']==uid)
 def enqueue(self,url='https://example.com/episode.mp4',**extra):
  r=self.call(self.a,self.path+'/experience/queue',{'url':url,'lane':'video',**extra});self.assertEqual(r.status_code,201,r.json);return r.json['id']
 def advance(self,room,client=None):return self.call(client or self.a,self.path+'/queue/advance',{'media_epoch':room['media_epoch']})
 def test_requests_from_chat_need_host_acceptance(self):
  self.create();self.call(self.b,self.path+'/join')
  r=self.call(self.b,self.path+'/stage',{'action':'request'});self.assertEqual(r.status_code,200,r.json)
  me=self.member(r.json['room'],self.ub['id']);self.assertIsNone(me['seat']);self.assertEqual(me['stage_request'],'requested')
  self.assertEqual(self.call(self.b,self.path+'/stage',{'action':'accept'}).status_code,409)
  self.assertEqual(self.call(self.b,self.path+'/members/'+self.ub['id'],{'decision':'promote'},'PATCH').status_code,403)
  r=self.call(self.a,self.path+'/members/'+self.ub['id'],{'decision':'promote'},'PATCH');self.assertEqual(r.status_code,200,r.json)
  me=self.member(r.json['room'],self.ub['id']);self.assertEqual(me['seat'],2);self.assertFalse(me['camera']);self.assertFalse(me['mic']);self.assertEqual(me['stage_request'],'')
  self.call(self.b,self.path+'/poll',{'mic':True,'camera':True});self.assertTrue(self.member(self.poll(),self.ub['id'])['mic'])
  self.call(self.b,self.path+'/stage',{'action':'leave'});me=self.member(self.poll(),self.ub['id']);self.assertIsNone(me['seat']);self.assertFalse(me['mic']);self.assertFalse(me['camera'])
 def test_requests_supported_for_voice_watch_and_live_and_can_be_cancelled(self):
  for kind in ('voice','watch','live','music'):
   with self.subTest(kind=kind):
    self.create(kind);self.call(self.b,self.path+'/join')
    r=self.call(self.b,self.path+'/stage',{'action':'request'});self.assertEqual(r.status_code,200,r.json)
    self.assertEqual(r.json['room']['seat_limit'],4 if kind=='live' else 8)
    self.call(self.b,self.path+'/stage',{'action':'cancel'});self.assertEqual(self.member(self.poll(),self.ub['id'])['stage_request'],'')
    self.assertEqual(self.call(self.b,self.path+'/stage',{'action':'request'}).status_code,429)
    self.assertEqual(self.call(self.a,self.path+'/stage',{'action':'request'}).status_code,400)
 def test_full_stage_rejects_without_losing_pending_request(self):
  self.create();self.call(self.b,self.path+'/join');self.call(self.b,self.path+'/stage',{'action':'request'})
  for n in range(2,9):
   uid='seated'+str(n);self.db.execute('INSERT INTO users(id,name,username,email,password,created_at) VALUES(?,?,?,?,?,?)',(uid,uid,uid,uid+'@example.com','unused',time.time()));self.db.execute("INSERT INTO community_members(room_id,user_id,status,joined_at,seen_at,seat) VALUES(?,?,'joined',?,?,?)",(self.rid,uid,time.time(),time.time(),n))
  self.db.commit();r=self.call(self.a,self.path+'/members/'+self.ub['id'],{'decision':'promote'},'PATCH');self.assertEqual(r.status_code,409,r.json)
  self.assertEqual(self.member(self.poll(),self.ub['id'])['stage_request'],'requested')
  self.call(self.a,self.path+'/members/'+self.ub['id'],{'decision':'reject_stage'},'PATCH');self.assertEqual(self.member(self.poll(),self.ub['id'])['stage_request'],'')
 def test_auto_next_is_fifo_and_duplicate_finish_cannot_skip_even_identical_url(self):
  self.create();self.enqueue(start_now=True);second=self.enqueue();third=self.enqueue('https://example.com/third.mp4');s=self.poll()
  # A regular playback heartbeat must not invalidate the token for this episode.
  self.call(self.a,self.path+'/playback',{'position':110,'paused':False,'revision':s['revision']},'PATCH')
  r=self.advance(s);self.assertEqual(r.status_code,200,r.json);self.assertTrue(r.json['advanced']);n=r.json['room']
  self.assertGreater(n['media_epoch'],s['media_epoch']);self.assertEqual(n['url'],s['url']);self.assertFalse(n['paused']);self.assertEqual(n['position'],0);self.assertEqual([q['id'] for q in n['queue']],[third])
  duplicate=self.advance(s);self.assertFalse(duplicate.json['advanced']);self.assertEqual([q['id'] for q in duplicate.json['room']['queue']],[third])
  r=self.advance(n);self.assertTrue(r.json['advanced']);self.assertEqual(r.json['room']['url'],'https://example.com/third.mp4')
  r=self.advance(r.json['room']);self.assertFalse(r.json['advanced']);self.assertTrue(r.json['room']['paused']);self.assertEqual(r.json['room']['position'],0)
 def test_guests_cannot_advance_and_empty_room_does_not_consume_queue(self):
  self.create();self.call(self.b,self.path+'/join');qid=self.enqueue();s=self.poll()
  self.assertEqual(self.advance(s,self.b).status_code,403)
  for value in (True,None,'1',1.0):self.assertEqual(self.call(self.a,self.path+'/queue/advance',{'media_epoch':value}).status_code,400)
  r=self.advance(s);self.assertFalse(r.json['advanced']);self.assertEqual(r.json['room']['media_epoch'],s['media_epoch']);self.assertEqual(r.json['room']['queue'][0]['id'],qid)
 def test_music_playlist_continues_then_stops_and_repeat_modes_work(self):
  t=self.music();u=self.music(2);s=self.create('music',track_id=t['id']);state='/music/rooms/'+self.rid+'/state'
  r=self.call(self.a,state,{'action':'add','track_id':u['id'],'revision':s['revision']},'PATCH');self.assertEqual(r.status_code,200,r.json)
  s=self.poll();r=self.advance(s);self.assertTrue(r.json['advanced']);n=r.json['room'];self.assertNotEqual(n['music_current'],s['music_current']);self.assertFalse(n['paused'])
  r=self.advance(n);self.assertFalse(r.json['advanced']);self.assertTrue(r.json['room']['paused'])
  s=self.a.get('/api'+state).json['room'];s=self.call(self.a,state,{'action':'mode','repeat':'all','revision':s['revision']},'PATCH').json['room']
  r=self.advance(s);self.assertTrue(r.json['advanced']);self.assertEqual(r.json['room']['music_current'],s['queue'][0]['id'])
  s=self.a.get('/api'+state).json['room'];s=self.call(self.a,state,{'action':'mode','repeat':'one','revision':s['revision']},'PATCH').json['room']
  r=self.advance(s);self.assertTrue(r.json['advanced']);self.assertEqual(r.json['room']['music_current'],s['music_current']);self.assertGreater(r.json['room']['media_epoch'],s['media_epoch'])
  r=self.call(self.a,state,{'action':'ended','media_epoch':s['media_epoch'],'revision':r.json['room']['revision']},'PATCH');self.assertEqual(r.status_code,409)
 def test_independent_soundtrack_finish_matches_current_item(self):
  self.create();self.call(self.b,self.path+'/join')
  first=self.enqueue('https://example.com/one.mp3',lane='music',start_now=True);second=self.enqueue('https://example.com/two.mp3',lane='music');third=self.enqueue('https://example.com/three.mp3',lane='music')
  def audio():return self.a.get('/api'+self.path+'/experience').json['audio']
  s=audio();d={'action':'ended','current_id':first,'revision':s['revision']}
  self.assertEqual(self.call(self.b,self.path+'/soundtrack',d,'PATCH').status_code,403)
  self.assertEqual(self.call(self.a,self.path+'/soundtrack',d,'PATCH').status_code,200);self.assertEqual(audio()['current_id'],second)
  d['revision']=audio()['revision'];self.assertFalse(self.call(self.a,self.path+'/soundtrack',d,'PATCH').json['advanced']);self.assertEqual(audio()['current_id'],second)
  self.call(self.a,self.path+'/soundtrack',{'action':'ended','current_id':second},'PATCH');self.assertEqual(audio()['current_id'],third)
  self.call(self.a,self.path+'/soundtrack',{'action':'ended','current_id':third},'PATCH');self.assertIsNone(audio()['current_id']);self.assertTrue(audio()['paused'])
if __name__=='__main__':unittest.main()
