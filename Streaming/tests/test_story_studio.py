"""Story single-media limits, audience access and interactive sticker persistence."""
import copy,json,time,unittest
import test_community as base
import test_community_social as social
class StoryStudioTests(unittest.TestCase):
 setUp=base.CommunityTests.setUp;tearDown=base.CommunityTests.tearDown;call=base.CommunityTests.call;user=base.CommunityTests.user;upload=social.SocialTests.upload
 def compose(self):return {'items':[{'url':self.upload().json['url'],'type':'image','duration':5}], 'layers':[]}
 def friends(self):
  self.call(self.a,'/social/friends',{'username':'bruno'});self.call(self.b,'/social/friends/'+self.ua['id'],m='PATCH')
 def publish(self,composition=None,**extra):
  c=composition or self.compose();r=self.call(self.a,'/community/stories',{'composition':c,**extra});self.assertEqual(r.status_code,201,r.json);return r.json['id'],c
 def test_one_media_thirty_seconds_and_no_text_only_or_grid(self):
  c=self.compose()
  for bad in [{**c,'items':c['items']*2},{**c,'items':[]},{**c,'layout':'grid'},{**c,'layout':'split'}]:self.assertEqual(self.call(self.a,'/community/stories',{'composition':bad}).status_code,400)
  self.assertEqual(self.call(self.a,'/community/stories',{'body':'Só texto'}).status_code,400)
  c['items'][0]['duration']=30.1;self.assertEqual(self.call(self.a,'/community/stories',{'composition':c}).status_code,400)
  c['items'][0]['duration']=30;sid,_=self.publish(c);r=self.b.get('/api/community/stories/'+sid);self.assertEqual(r.json['story']['composition']['duration'],30);self.assertEqual(r.json['story']['composition']['format'],'story')
  c['items'][0].update(type='video',url='https://example.com/video.mp4',start=22,duration=30,speed=1);sid,_=self.publish(c);self.assertEqual(self.b.get('/api/community/stories/'+sid).json['story']['composition']['items'][0]['start'],22)
 def test_close_friends_enforced_for_feed_detail_assets_views_and_reactions(self):
  self.friends();self.assertEqual(self.call(self.a,'/community/story-audience',{'users':[self.ub['id']]},'PUT').status_code,200)
  sid,c=self.publish(audience='close');asset=c['items'][0]['url']
  self.assertEqual(self.b.get('/api/community/stories/'+sid).status_code,200);self.assertEqual(self.c.get('/api/community/stories/'+sid).status_code,404)
  self.assertNotIn(sid,[s['id'] for s in self.c.get('/api/community/stories').json['stories']]);self.assertIn(sid,[s['id'] for s in self.b.get('/api/community/stories').json['stories']])
  self.assertEqual(self.c.get(asset).status_code,404);r=self.b.get(asset);self.assertEqual(r.status_code,200);r.close()
  self.assertEqual(self.call(self.c,'/community/stories/'+sid+'/view').status_code,404);self.assertEqual(self.call(self.c,'/community/reactions/story/'+sid,{'reaction':'heart'},'PUT').status_code,404)
  self.call(self.a,'/community/story-audience',{'users':[]},'PUT');self.assertEqual(self.b.get('/api/community/stories/'+sid).status_code,404);self.assertEqual(self.b.get(asset).status_code,404)
 def test_selected_share_is_private_and_creates_one_chat_share_per_recipient(self):
  self.friends();sid,c=self.publish(audience='selected',recipients=[self.ub['id'],self.ub['id']])
  self.assertEqual(self.c.get('/api/community/stories/'+sid).status_code,404);self.assertEqual(self.c.get(c['items'][0]['url']).status_code,404)
  msgs=self.b.get('/api/hub/dm/'+self.ua['id']).json['messages'];self.assertEqual(len(msgs),1);self.assertEqual(msgs[0]['share']['kind'],'story');self.assertEqual(msgs[0]['share']['href'],'/comunidade?story='+sid)
  self.assertEqual(self.call(self.a,'/community/stories',{'composition':c,'audience':'selected','recipients':[self.uc['id']]}).status_code,403)
  self.assertEqual(self.call(self.a,'/community/stories',{'composition':c,'audience':'selected','recipients':[]}).status_code,400)
  self.assertEqual(self.call(self.a,'/community/story-audience',{'users':[self.uc['id']]},'PUT').status_code,403)
 def test_private_story_does_not_hide_reused_public_media(self):
  self.friends();c=self.compose();self.publish(c);sid,_=self.publish(c,audience='selected',recipients=[self.ub['id']]);self.assertEqual(self.c.get('/api/community/stories/'+sid).status_code,404)
  r=self.c.get(c['items'][0]['url']);self.assertEqual(r.status_code,200);r.close()
 def test_gestures_style_drawings_and_poll_answer_validation(self):
  c=self.compose();c['items'][0].update(zoom=2,panX=.2,panY=-.1,saturation=1.3)
  c['layers']=[{'id':'poll1','type':'poll','text':'Bora assistir?','options':['Sim','Não'],'scale':1.4,'rotation':35,'font':'serif','align':'left','backgroundOpacity':.7,'animation':'pop'},{'id':'question1','type':'question','text':'Indique um filme'}]
  c['drawings']=[{'mode':'neon','color':'#ff5788','width':1,'points':[[10,20],[30,40]]}]
  sid,_=self.publish(c);stored=self.b.get('/api/community/stories/'+sid).json['story']['composition'];self.assertEqual(stored['layers'][0]['scale'],1.4);self.assertEqual(stored['drawings'][0]['mode'],'neon');self.assertEqual(stored['items'][0]['panX'],.2)
  path='/community/stories/'+sid+'/stickers/poll1';self.assertEqual(self.call(self.b,path,{'value':True}).status_code,400)
  for _ in range(2):self.assertEqual(self.call(self.b,path,{'value':1}).status_code,200)
  self.assertEqual(self.b.get('/api'+path).json['counts'],[0,1]);self.call(self.b,path,{'value':0});self.assertEqual(self.a.get('/api'+path).json['counts'],[1,0])
  path='/community/stories/'+sid+'/stickers/question1';self.call(self.b,path,{'value':'Sintel'});self.assertEqual(self.b.get('/api'+path).json['mine'],'Sintel');self.assertNotIn('answers',self.c.get('/api'+path).json);self.assertEqual(len(self.a.get('/api'+path).json['answers']),1)
  self.assertEqual(self.call(self.b,path,{'value':'x'*241}).status_code,400)
  self.db.execute('UPDATE community_stories SET expires_at=? WHERE id=?',(time.time()-1,sid));self.db.commit();self.assertEqual(self.call(self.b,path,{'value':'Depois'}).status_code,404)
 def test_no_invisible_mentions_from_private_story(self):
  self.friends();c=self.compose();c['layers']=[{'type':'mention','text':'@carol','user_id':self.uc['id']}];self.publish(c,audience='selected',recipients=[self.ub['id']]);rows=self.c.get('/api/hub/notifications').json['notifications'];self.assertFalse(any('mencion' in r['title'] for r in rows))
if __name__=='__main__':unittest.main()
