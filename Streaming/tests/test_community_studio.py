"""Publication ownership, media constraints and multiplayer rule regressions."""
import io, json, time, unittest, wave
import test_community_social as social

class StudioTests(unittest.TestCase):
    setUp=social.SocialTests.setUp
    tearDown=social.SocialTests.tearDown
    call=social.SocialTests.call
    user=social.SocialTests.user
    room=social.SocialTests.room
    admit=social.SocialTests.admit
    post=social.SocialTests.post
    upload=social.SocialTests.upload
    game=social.SocialTests.game
    start_game=social.SocialTests.start_game
    alter=social.SocialTests.alter

    def payload(self,**extra):
        return {'kind':'discussion','title':'Uma noite de cinema','body':'História da comunidade','document':[{'type':'heading','content':[{'text':'Uma ótima história','marks':['bold']}]},{'type':'paragraph','content':[{'text':'Veja a descoberta','marks':['italic'],'href':'https://example.com/news'}]}],'people':[self.ub['id']],'titles':[],**extra}
    def move(self,c,path,action,**kw):
        g=self.game(c,path).json['game']
        r=self.game(c,path,action,revision=g['revision'],game_id=g['id'],**kw)
        self.assertEqual(r.status_code,200,r.json)
        return r.json['game']
    def test_structured_post_mentions_and_premium_metadata(self):
        pid=self.post();payload=self.payload(titles=[{'source':'community','id':pid},{'source':'catalog','id':'horizonte'}])
        r=self.call(self.a,'/community/posts',payload);self.assertEqual(r.status_code,201,r.json);pid=r.json['id']
        p=self.b.get('/api/community/posts/'+pid).json['post'];self.assertEqual(p['document'],payload['document']);self.assertEqual(p['people'][0]['username'],'bruno');self.assertEqual(len(p['titles']),2)
        self.assertNotIn('url',p['titles'][1]);self.assertEqual(self.b.get('/api/play/horizonte').status_code,402)
        self.assertEqual(self.call(self.b,'/community/posts/'+pid,payload,'PATCH').status_code,403)
        admin=self.admin.get('/api/admin/community').json['posts'];self.assertTrue(next(x for x in admin if x['id']==pid)['document'])
        self.db.execute("UPDATE users SET status='blocked' WHERE id=?",(self.ub['id'],));self.db.commit()
        self.assertEqual(self.a.get('/api/community/posts/'+pid).json['post']['people'],[])
    def test_untrusted_document_links_types_and_sizes(self):
        for document in [[{'type':'script','content':[]}],[{'type':'paragraph','content':[{'text':'click','href':'javascript:alert(1)'}]}],[{'type':'video','url':'https://example.com/music.mp3'}],[{'type':'paragraph','content':[{'text':'a'*6001}]}],[{'type':'audio','url':'https://example.com/image.png'}]]:
            self.assertEqual(self.call(self.a,'/community/posts',self.payload(document=document)).status_code,400)
        self.assertEqual(self.call(self.a,'/community/posts',self.payload(people=['missing-user'])).status_code,400)
        self.assertEqual(self.call(self.a,'/community/posts',self.payload(document=[{'type':'image','url':'https://example.com/cover.png'}]*9)).status_code,400)
    def test_audio_upload_retention_and_post_ownership(self):
        buffer=io.BytesIO()
        with wave.open(buffer,'wb') as f:f.setparams((1,2,8000,0,'NONE','not compressed'));f.writeframes(b'\x00\x00'*800)
        r=self.a.post('/api/community/assets',headers=self.headers,data={'file':(io.BytesIO(buffer.getvalue()),'music.wav')});self.assertEqual(r.status_code,201,r.json);url=r.json['url'];self.assertEqual(r.json['media_type'],'audio')
        r=self.call(self.a,'/community/posts',self.payload(document=[{'type':'audio','url':url,'caption':'Minha trilha'}]));self.assertEqual(r.status_code,201,r.json)
        p=self.b.get('/api/community/posts/'+r.json['id']).json['post'];self.assertEqual(p['media_type'],'audio');self.assertEqual(p['document'][0]['media_type'],'audio')
        self.assertIsNone(self.db.execute('SELECT expires_at FROM community_assets WHERE id=?',(url.split('/')[-1],)).fetchone()[0])
        self.assertEqual(self.b.delete(url,headers=self.headers).status_code,403)
        # Public community media may be shared by URL; deleting the upload remains owner-only.
        self.assertEqual(self.call(self.b,'/community/posts',self.payload(document=[{'type':'audio','url':url}])).status_code,201)
        partial=self.b.get(url,headers={'Range':'bytes=0-31'});self.assertEqual(partial.status_code,206);partial.close()
    def test_drafts_private_revision_publish_and_cleanup(self):
        r=self.call(self.a,'/community/drafts',self.payload(title=''));self.assertEqual(r.status_code,201,r.json);did=r.json['id'];revision=r.json['revision']
        self.assertEqual(self.b.get('/api/community/drafts/'+did).status_code,404)
        self.assertEqual(self.call(self.b,'/community/drafts/'+did,m='DELETE').status_code,404)
        self.assertEqual(self.call(self.a,'/community/drafts/'+did,self.payload(revision=0),'PUT').status_code,409)
        r=self.call(self.a,'/community/drafts/'+did,self.payload(revision=revision),'PUT');self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(self.a.get('/api/community/drafts').json['drafts'][0]['title'],'Uma noite de cinema')
        self.assertEqual(self.a.get('/api/community/drafts/'+did).json['draft']['people'][0]['username'],'bruno')
        r=self.call(self.a,'/community/posts',self.payload(draft_id=did));self.assertEqual(r.status_code,201,r.json);self.assertEqual(self.a.get('/api/community/drafts').json['drafts'],[])
    def test_create_game_room_feed_invitation_and_approval(self):
        r=self.call(self.a,'/community/rooms',{'kind':'voice','game_kind':'colors','title':'Mesa do cinema','approval':True,'publish_to_feed':True});self.assertEqual(r.status_code,201,r.json);rid=r.json['room']['id'];path='/community/rooms/'+rid
        g=self.game(self.a,path).json['game'];self.assertEqual(g['status'],'lobby');self.assertEqual(g['kind'],'colors');self.assertEqual(len(g['players']),1)
        p=self.a.get('/api/community/feed').json['posts'][0];self.assertEqual(p['room']['id'],rid);self.assertEqual(p['room']['status'],'open')
        self.assertEqual(self.call(self.b,path+'/join').json['status'],'pending');self.assertEqual(self.game(self.b,path,'join',revision=1).status_code,403)
        self.admit(path);self.move(self.b,path,'join');self.assertEqual(len(self.game(self.a,path).json['game']['players']),2)
        self.assertEqual(self.call(self.a,'/community/rooms',{'kind':'watch','game_kind':'draw','title':'Bad room','url':'https://example.com/video.mp4'}).status_code,400)
    def test_uno_announcing_and_catching_before_next_action(self):
        path,g=self.start_game('colors');a,b=self.ua['id'],self.ub['id']
        self.alter(path,lambda s:s.update(hands={a:['red:3','blue:8'],b:['red:6','green:3']},color='red',discard=['red:5'],deck=['yellow:4','green:9','blue:5']))
        g=self.move(self.a,path,'play',card='red:3');self.assertEqual(g['uno_pending'],a)
        g=self.move(self.b,path,'catch');self.assertEqual(g['counts'][a],3);self.assertIsNone(g['uno_pending']);self.assertEqual(g['turn'],b)
        self.assertEqual(g['events'][-1]['kind'],'catch')
        self.alter(path,lambda s:s.update(hands={a:['red:2','red:1'],b:['blue:3']},turn=0,discard=['red:8'],color='red'))
        self.move(self.a,path,'uno');g=self.move(self.a,path,'play',card='red:2');self.assertIsNone(g['uno_pending']);self.assertIn(a,g['uno_called'])
        self.assertEqual(self.game(self.b,path,'catch',revision=1).status_code,409)
        self.assertNotIn('hands',g);self.assertNotIn('deck',g)
    def test_uno_after_play_and_window_closes_on_next_play(self):
        path,g=self.start_game('colors');a,b=self.ua['id'],self.ub['id']
        self.alter(path,lambda s:s.update(hands={a:['red:3','blue:8'],b:['red:6','green:3']},color='red',discard=['red:5']))
        self.move(self.a,path,'play',card='red:3');g=self.move(self.a,path,'uno');self.assertIsNone(g['uno_pending']);self.assertEqual(g['events'][-1]['kind'],'uno')
        self.alter(path,lambda s:s.update(uno_pending=a))
        self.move(self.b,path,'play',card='red:6')
        self.assertEqual(self.game(self.b,path,'catch',revision=1).status_code,409)
    def test_purchase_can_play_only_new_card_or_pass_and_timeout_does_not_redraw(self):
        path,g=self.start_game('colors');a,b=self.ua['id'],self.ub['id']
        self.alter(path,lambda s:s.update(hands={a:['red:1','blue:8'],b:['blue:6']},color='red',discard=['red:5'],deck=['blue:9','red:7']))
        g=self.move(self.a,path,'draw');self.assertTrue(g['can_pass']);self.assertEqual(g['turn'],a);self.assertEqual(g['playable'],['red:7']);self.assertNotIn('card',g['events'][-1])
        self.assertEqual(self.game(self.a,path,'draw',revision=g['revision']).status_code,409)
        self.assertEqual(self.game(self.a,path,'play',revision=g['revision'],card='red:1').status_code,400)
        self.alter(path,lambda s:s.update(deadline=time.time()-1));g=self.game(self.a,path).json['game'];self.assertEqual(g['counts'][a],3);self.assertEqual(g['turn'],b)
        self.alter(path,lambda s:s.update(turn=0,deck=['red:4']))
        self.move(self.a,path,'draw');g=self.move(self.a,path,'pass');self.assertEqual(g['turn'],b)
    def test_wild_four_restriction_and_final_penalty_and_reverse(self):
        path,g=self.start_game('colors');a,b=self.ua['id'],self.ub['id']
        self.alter(path,lambda s:s.update(hands={a:['wild:+4','red:1'],b:['blue:8']},color='red',discard=['red:5']))
        self.assertEqual(self.game(self.a,path,'play',revision=g['revision'],card='wild:+4',color='blue').status_code,400)
        self.alter(path,lambda s:s.update(hands={a:['red:reverse','red:+2'],b:['blue:8']}))
        g=self.move(self.a,path,'play',card='red:reverse');self.assertEqual(g['turn'],a);self.assertEqual(g['direction'],-1)
        g=self.move(self.a,path,'play',card='red:+2');self.assertEqual(g['status'],'finished');self.assertEqual(g['counts'][b],3)
        rank=self.b.get('/api/community/games/ranking?kind=colors').json;self.assertEqual(rank['leaders'][0]['id'],a);self.assertEqual(rank['me']['position'],2)
        self.assertEqual(self.a.get('/api/community/discover').json['games']['leaders'][0]['points'],30)
        self.assertEqual(self.a.get('/api/community/games/ranking?kind=draw').json['leaders'],[])
        self.game(self.a,path);self.assertEqual(self.db.execute('SELECT COUNT(*) FROM community_game_results').fetchone()[0],2)

if __name__=='__main__':unittest.main()
