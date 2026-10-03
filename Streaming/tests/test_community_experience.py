"""Creation, privacy, recommendation and camera regression tests using isolated databases."""
import json,time,unittest
from unittest.mock import patch,MagicMock
import test_community as baseline
import test_community_social as social
import test_jump as jump

class ExperienceTests(unittest.TestCase):
    setUp=baseline.CommunityTests.setUp
    tearDown=baseline.CommunityTests.tearDown
    call=baseline.CommunityTests.call
    user=baseline.CommunityTests.user
    post=baseline.CommunityTests.post
    room=baseline.CommunityTests.room
    upload=social.SocialTests.upload
    def create(self,**extra):
        r=self.call(self.a,'/community/posts',dict(kind='movie',title='Cinema da comunidade',body='Uma sinopse',genre='Drama',poster='https://example.com/poster.jpg',url='https://example.com/filme.mp4',**extra));self.assertEqual(r.status_code,201,r.json);return r.json['id']
    def test_creator_and_history_direct_routes(self):
        for path in ['/comunidade/criar','/comunidade/criar/post','/comunidade/criar/movie','/comunidade/criar/series','/comunidade/criar/reel','/comunidade/criar/story','/historico']:
            response=self.a.get(path);self.assertEqual(response.status_code,200,path);self.assertEqual(response.headers['X-Robots-Tag'],'noindex, nofollow')
        self.assertEqual(self.a.get('/comunidade/criar/invalid').status_code,404)
    def test_catalog_episode_validation_and_ownership(self):
        d=dict(kind='series',title='Série de teste',body='Uma sinopse',genre='Comédia',poster='https://example.com/poster.jpg',episodes=[dict(season=2,number=1,title='Uma nova fase',url='https://example.com/3.mp4'),dict(season=1,number=1,title='O começo',url='https://example.com/1.mp4')])
        r=self.call(self.a,'/community/posts',d);self.assertEqual(r.status_code,201,r.json);pid=r.json['id'];p=self.b.get('/api/community/posts/'+pid).json['post'];self.assertEqual(p['genre'],'Comédia');self.assertEqual([e['season'] for e in p['episodes']],[1,2]);self.assertEqual(p['url'],'https://example.com/1.mp4')
        d['episodes']=p['episodes']+[dict(season=2,number=2,title='A continuação',url='https://example.com/4.mp4')];self.assertEqual(self.call(self.a,'/community/posts/'+pid,d,'PATCH').status_code,200)
        self.assertEqual(self.a.get('/api/community/posts/'+pid).json['post']['episodes'][0]['id'],p['episodes'][0]['id'])
        self.assertEqual(self.call(self.b,'/community/posts',d).status_code,403)
        d['episodes']=[dict(season=1,number=1,title='Repetido',url='https://example.com/1.mp4')]*2;self.assertEqual(self.call(self.a,'/community/posts',d).status_code,400)
        for url in ['https://example.com/page','https://example.com/live.m3u8','http://example.com/movie.mp4']:
            self.assertEqual(self.call(self.a,'/community/posts',dict(kind='movie',title='Teste',genre='Drama',url=url)).status_code,400)
    def test_private_archive_controls_and_asset_reuse(self):
        image=self.upload().json['url'];pid=self.create();path='/community/posts/'+pid
        self.db.execute('UPDATE community_posts SET poster=? WHERE id=?',(image,pid));self.db.commit()
        self.assertEqual(self.call(self.b,path+'/controls',{'status':'private'},'PATCH').status_code,403)
        self.call(self.a,path+'/controls',{'status':'private'},'PATCH')
        self.assertEqual(self.b.get('/api'+path).status_code,404);self.assertEqual(self.a.get('/api'+path).status_code,200);self.assertEqual(self.admin.get('/api'+path).status_code,200)
        self.assertEqual(self.b.get(image).status_code,404)
        self.assertEqual(self.call(self.b,'/community/posts',{'kind':'discussion','title':'Reusar indevidamente','poster':image}).status_code,404)
        self.assertEqual(self.b.get('/api/community/feed').json['posts'],[])
        mine=self.a.get('/api/community/feed?mine=1&status=private').json['posts'];self.assertEqual([x['id'] for x in mine],[pid])
        self.call(self.a,path+'/controls',{'status':'archived'},'PATCH');self.assertEqual(self.a.get('/api/community/feed?mine=1&status=archived').json['posts'][0]['id'],pid)
        self.call(self.a,path+'/controls',{'status':'published'},'PATCH');r=self.b.get(image);self.assertEqual(r.status_code,200);r.close()
        self.call(self.admin,'/admin/community/posts/'+pid,{'action':'hide'},'PATCH');self.assertEqual(self.call(self.a,path+'/controls',{'status':'published'},'PATCH').status_code,403)
    def test_comments_latest_mentions_edit_hide_and_disable(self):
        pid=self.post();path='/community/posts/'+pid
        self.call(self.b,'/social/friends',{'username':'carol'});self.call(self.c,'/social/friends/'+self.ub['id'],m='PATCH')
        self.call(self.b,path+'/comments',{'body':'Primeiro'});self.call(self.b,path+'/comments',{'body':'Novo comentário @carol <script>x</script>'})
        p=self.a.get('/api'+path).json;cid=p['comments'][0]['id'];self.assertEqual(p['post']['latest_comment']['id'],cid)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM hub_notifications WHERE user_id=? AND dedupe LIKE 'comment-mention:%'",(self.uc['id'],)).fetchone()[0],1)
        cpath='/community/comments/'+str(cid)
        self.assertEqual(self.call(self.c,cpath,{'body':'Invadir'},'PATCH').status_code,403)
        self.assertEqual(self.call(self.b,cpath,{'body':'Editado @carol'},'PATCH').status_code,200)
        self.assertIsNotNone(self.b.get('/api'+path).json['comments'][0]['edited_at'])
        self.assertEqual(self.call(self.a,cpath,{'hidden':True},'PATCH').status_code,200)
        self.assertNotIn(cid,[c['id'] for c in self.c.get('/api'+path).json['comments']]);self.assertEqual(self.b.get('/api'+path).json['comments'][0]['id'],cid)
        self.call(self.a,path+'/controls',{'hide_comments':True,'hide_likes':True,'comments_disabled':True},'PATCH')
        p=self.b.get('/api'+path).json;self.assertEqual(p['comments'],[]);self.assertIsNone(p['post']['latest_comment']);self.assertIsNone(p['post']['likes']);self.assertEqual(p['post']['reactions']['counts'],{})
        self.assertEqual(self.call(self.b,path+'/comments',{'body':'Mais um'}).status_code,403)
        self.assertEqual(self.call(self.b,cpath,{'body':'Editar bloqueado'},'PATCH').status_code,403)
        self.assertEqual(self.call(self.a,cpath,m='DELETE').status_code,200)
    def test_reel_story_composition_validation_and_retention(self):
        image=self.upload().json['url'];comp={'layout':'grid','items':[{'url':image,'type':'image','duration':5}], 'layers':[{'type':'link','text':'Saiba mais','url':'https://example.com/news','x':40,'y':65}], 'music':{'url':'https://youtu.be/abcdefghijk','title':'Minha faixa'}}
        r=self.call(self.a,'/community/posts',{'kind':'reel','title':'Reel completo','composition':comp});self.assertEqual(r.status_code,201,r.json);pid=r.json['id']
        p=self.b.get('/api/community/posts/'+pid).json['post'];self.assertEqual(p['media_type'],'composition');self.assertEqual(p['composition']['duration'],5);self.assertEqual(p['composition']['music']['type'],'youtube')
        self.call(self.a,'/community/posts/'+pid+'/controls',{'status':'archived'},'PATCH')
        r=self.call(self.a,'/community/stories',{'body':'Meu story','composition':comp});self.assertEqual(r.status_code,201,r.json);sid=r.json['id']
        self.assertIsNone(self.db.execute('SELECT expires_at FROM community_assets WHERE id=?',(image.rsplit('/',1)[-1],)).fetchone()[0]);self.assertEqual(self.b.get('/api/community/stories/'+sid).json['story']['composition']['layers'][0]['x'],40)
        self.assertEqual(self.call(self.b,'/community/stories',{'composition':comp}).status_code,404)
        for bad in [{'layers':[{'type':'text','text':'a','x':float('inf')}]},{'layers':[{'type':'link','text':'A','url':'javascript:alert(1)'}]},{'items':[{'url':image,'type':'image','duration':100}]*2}]:
            self.assertEqual(self.call(self.a,'/community/stories',{'composition':bad}).status_code,400)
    def test_recommendation_affinity_stable_pages_and_hidden_posts(self):
        self.call(self.b,'/community/profile',{'name':'Bruno','favorite_genres':'Drama'},'PATCH')
        drama=self.create();other=self.post(kind='news',url='https://example.com/news')
        order=lambda:[p['id'] for p in self.b.get('/api/community/feed').json['posts']]
        first=order();self.assertEqual(first[0],drama);self.assertEqual(order(),first)
        self.call(self.b,'/community/feed/feedback',{'ids':[drama],'hidden':True});self.assertNotIn(drama,order());self.assertIn(other,order())
        self.call(self.a,'/community/posts/'+other+'/controls',{'status':'private'},'PATCH');self.assertNotIn(other,order())
        # Deterministic cache keeps consecutive pages disjoint and diverse.
        now=time.time()
        for i in range(45):self.db.execute("INSERT INTO community_posts(id,user_id,kind,title,created_at,updated_at) VALUES(?,?,'discussion',?,?,?)",('feed'+str(i),self.ua['id'] if i%2 else self.uc['id'],'Publicação '+str(i),now-i,now))
        self.db.execute('DELETE FROM community_feed_order');self.db.commit()
        a=self.b.get('/api/community/feed').json;b=self.b.get('/api/community/feed?offset=20').json
        self.assertEqual(len(a['posts']),20);self.assertEqual(len(b['posts']),20);self.assertTrue(a['more']);self.assertFalse(set(p['id'] for p in a['posts']) & set(p['id'] for p in b['posts']))
    def test_legacy_youtube_key_is_not_used_for_music_search(self):
        r=self.call(self.admin,'/admin/settings',{'brand':'Flix','mode':'test','youtube_api_key':'legacy-private-key'},'PUT');self.assertEqual(r.status_code,200)
        self.assertNotIn('legacy-private-key',self.admin.get('/api/admin/settings').text)
        with patch('community_experience.urlopen') as old_provider:
            r=self.a.get('/api/community/music/search?q=Jazz');self.assertFalse(r.json['configured']);self.assertEqual(r.json['provider'],'soundcloud');old_provider.assert_not_called()
        self.assertEqual(self.c.get('/api/admin/settings').status_code,403)
    def test_watch_cameras_four_limit_and_audience_signaling(self):
        path=self.room(approval=False);self.call(self.b,path+'/join');self.call(self.c,path+'/join')
        d,ud=self.user('dora');e,ue=self.user('enzo');self.call(d,path+'/join');self.call(e,path+'/join')
        for client in (self.a,self.b,self.c,d):self.assertEqual(self.call(client,path+'/camera',{'enabled':True},'PATCH').status_code,200)
        self.assertEqual(self.call(e,path+'/camera',{'enabled':True},'PATCH').status_code,409)
        stale=self.call(self.a,path+'/poll',{'camera':False}).json['room'];self.assertEqual(next(u['camera'] for u in stale['members'] if u['id']==self.ua['id']),1)
        self.assertEqual(self.call(self.b,path+'/signals',{'recipient':self.uc['id'],'payload':{'type':'offer','sdp':'camera'}}).status_code,200)
        self.call(self.b,path+'/camera',{'enabled':False},'PATCH');self.assertEqual(self.call(e,path+'/camera',{'enabled':True},'PATCH').status_code,200)
        room=self.call(self.c,path+'/poll',{'camera':True}).json['room'];self.assertEqual(sum(u['camera'] for u in room['members']),4)

class JumpCameras(unittest.TestCase):
    setUp=jump.JumpTests.setUp
    tearDown=jump.JumpTests.tearDown
    call=jump.JumpTests.call
    user=jump.JumpTests.user
    room=jump.JumpTests.room
    admit=jump.JumpTests.admit
    def test_private_jump_cameras_reserve_release_and_admission(self):
        r=self.room();path='/jump/rooms/'+r['id'];self.assertEqual(self.call(self.b,path+'/camera',{'enabled':True},'PATCH').status_code,403)
        self.admit(self.b,path);self.admit(self.c,path);d,ud=self.user('dora');e,ue=self.user('enzo');self.admit(d,path);self.admit(e,path)
        for client in (self.a,self.b,self.c,d):self.assertEqual(self.call(client,path+'/camera',{'enabled':True},'PATCH').status_code,200)
        self.assertEqual(self.call(e,path+'/camera',{'enabled':True},'PATCH').status_code,409)
        self.call(self.b,path+'/leave');self.assertEqual(self.call(e,path+'/camera',{'enabled':True},'PATCH').status_code,200)

if __name__=='__main__':unittest.main()
