import copy,json,unittest
import test_community as base
import test_community_social as social
class ReelStudioTests(unittest.TestCase):
 setUp=base.CommunityTests.setUp;tearDown=base.CommunityTests.tearDown;call=base.CommunityTests.call;user=base.CommunityTests.user;upload=social.SocialTests.upload
 def composition(self):return {'items':[{'url':self.upload(content=b'\x00\x00\x00\x20ftypisom'+b'\0'*28).json['url'],'type':'video','start':10,'duration':20,'filter':'cinema','filterIntensity':.5,'exposure':.2,'sharpness':.5}],'layers':[{'type':'text','text':'Cinema','scale':1.5,'rotation':30}]}
 def publish(self,options=None,**extra):
  d={'kind':'reel','title':'Reel de teste','body':'Descrição','composition':self.composition(),'reel_options':options or {},**extra};r=self.call(self.a,'/community/posts',d);self.assertEqual(r.status_code,201,r.json);return r.json['id'],d
 def friends(self):self.call(self.a,'/social/friends',{'username':'bruno'});self.call(self.b,'/social/friends/'+self.ua['id'],m='PATCH')
 def test_one_video_sixty_seconds_and_effects(self):
  c=self.composition()
  for comp in [None,{'items':[]},{**c,'items':c['items']*2},{**c,'layout':'grid'}]:self.assertEqual(self.call(self.a,'/community/posts',{'kind':'reel','title':'Inválido','composition':comp}).status_code,400)
  c['items'][0]['duration']=60.1;self.assertEqual(self.call(self.a,'/community/posts',{'kind':'reel','title':'Longo','composition':c}).status_code,400)
  c['items'][0]['duration']=60;self.assertEqual(self.call(self.a,'/community/posts',{'kind':'reel','title':'Um minuto','composition':c}).status_code,201)
  pid,d=self.publish();stored=self.b.get('/api/community/posts/'+pid).json['post']['composition'];self.assertEqual(stored['format'],'reel');self.assertEqual(stored['items'][0]['filter'],'cinema');self.assertEqual(stored['items'][0]['sharpness'],.5)
 def test_audience_protects_feed_detail_assets_mentions_and_shares(self):
  self.friends();self.call(self.c,'/community/follow/'+self.ua['id']);pid,d=self.publish({'audience':'friends','people':[self.uc['id']]})
  self.assertEqual(self.b.get('/api/community/posts/'+pid).status_code,200);self.assertEqual(self.c.get('/api/community/posts/'+pid).status_code,404)
  self.assertNotIn(pid,[p['id'] for p in self.c.get('/api/community/feed?kind=reel').json['posts']]);self.assertEqual(self.c.get(d['composition']['items'][0]['url']).status_code,404)
  self.assertFalse(any(pid in n['href'] for n in self.c.get('/api/hub/notifications').json['notifications']))
  pid,d=self.publish({'audience':'private'});self.assertEqual(self.b.get('/api/community/posts/'+pid).status_code,404);self.assertEqual(self.a.get('/api/community/posts/'+pid).status_code,200)
 def test_comments_and_feed_reuse(self):
  self.friends();pid,_=self.publish({'comments':'friends','reuse_feed':False});self.assertEqual(self.call(self.c,'/community/posts/'+pid+'/comments',{'body':'Não autorizado'}).status_code,403);self.assertEqual(self.call(self.b,'/community/posts/'+pid+'/comments',{'body':'Vamos ver'}).status_code,201)
  self.assertNotIn(pid,[p['id'] for p in self.b.get('/api/community/feed').json['posts']]);self.assertIn(pid,[p['id'] for p in self.b.get('/api/community/feed?kind=reel').json['posts']]);self.assertFalse(self.c.get('/api/community/posts/'+pid).json['post']['can_comment'])
 def test_metadata_playlists_permissions_and_owner(self):
  r=self.call(self.a,'/community/reel-playlists',{'name':'Cinema'});playlist=r.json['playlists'][0]['id'];opts={'playlist':playlist,'ai_label':True,'brand':'Marca A','location':'Recife','topics':['Cinema','Drama'],'alt':'Cena à beira-mar','remix':False,'download':False,'dubbing':False}
  pid,_=self.publish(opts);post=self.b.get('/api/community/posts/'+pid).json['post'];self.assertEqual(post['reel_options']['brand'],'Marca A');self.assertEqual(self.b.get('/api/community/reel-playlists/'+playlist).json['posts'][0]['id'],pid)
  for kind in ['remix','download','dubbing']:self.assertEqual(self.b.get('/api/community/reels/'+pid+'/permissions/'+kind).status_code,403)
  self.assertEqual(self.a.get('/api/community/reels/'+pid+'/permissions/download').status_code,200)
  self.assertEqual(self.call(self.b,'/community/posts',{'kind':'reel','title':'Roubo','composition':{'items':[{'url':'https://example.com/v.mp4','type':'video','duration':10}]},'reel_options':opts}).status_code,403)
 def test_idempotent_publication_and_description_limit(self):
  pid,d=self.publish(reel_request_id='a'*32);self.assertEqual(self.call(self.a,'/community/posts',d).json['id'],pid);self.assertEqual(self.db.execute('SELECT COUNT(*) FROM community_posts WHERE user_id=?',(self.ua['id'],)).fetchone()[0],1)
  d.pop('reel_request_id');d['body']='x'*2201;self.assertEqual(self.call(self.a,'/community/posts',d).status_code,400)
 def test_tags_and_controls_stay_consistent(self):
  self.friends();pid,_=self.publish({'audience':'friends','people':[self.ub['id'],self.uc['id']],'comments':'off'})
  self.assertTrue(any(pid in n['href'] for n in self.b.get('/api/hub/notifications').json['notifications']))
  self.assertFalse(any(pid in n['href'] for n in self.c.get('/api/hub/notifications').json['notifications']))
  self.assertEqual(self.call(self.a,'/community/posts/'+pid+'/controls',{'comments_disabled':False},'PATCH').status_code,200)
  self.assertEqual(self.call(self.b,'/community/posts/'+pid+'/comments',{'body':'Liberado'}).status_code,201)
  self.call(self.a,'/community/posts/'+pid+'/controls',{'status':'private'},'PATCH');self.assertEqual(self.b.get('/api/community/posts/'+pid).status_code,404)
  self.call(self.a,'/community/posts/'+pid+'/controls',{'status':'published'},'PATCH');self.assertEqual(self.c.get('/api/community/posts/'+pid).status_code,200)
 def test_interactive_sticker(self):
  c=self.composition();c['layers']=[{'id':'poll','type':'poll','text':'Assistiria?','options':['Sim','Não']}];pid,_=self.publish(composition=c);path='/community/reels/'+pid+'/stickers/poll';self.assertEqual(self.call(self.b,path,{'value':0}).json['counts'],[1,0]);self.assertEqual(self.call(self.b,path,{'value':1}).json['counts'],[0,1]);self.assertEqual(self.call(self.c,path,{'value':False}).status_code,400)
if __name__=='__main__':unittest.main()
