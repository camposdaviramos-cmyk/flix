"""Social access boundaries, idempotent ranking and authoritative multiplayer state."""
import base64, io, json, time, unittest
import test_community as baseline

class SocialTests(unittest.TestCase):
    setUp=baseline.CommunityTests.setUp
    tearDown=baseline.CommunityTests.tearDown
    call=baseline.CommunityTests.call
    user=baseline.CommunityTests.user
    room=baseline.CommunityTests.room
    admit=baseline.CommunityTests.admit
    post=baseline.CommunityTests.post
    def upload(self,client=None,content=None):
        content=content or base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZkAAAAASUVORK5CYII=')
        return (client or self.a).post('/api/community/assets',data={'file':(io.BytesIO(content),'image.png')},headers=self.headers)
    def game(self,c,path,action=None,**kwargs):
        if action is None:return c.get('/api'+path+'/game')
        return self.call(c,path+'/game',{'action':action,**kwargs})
    def start_game(self,kind):
        path=self.room(approval=False);self.call(self.b,path+'/join')
        r=self.game(self.a,path,'create',kind=kind);self.assertEqual(r.status_code,200,r.json)
        r=self.game(self.b,path,'join',revision=r.json['game']['revision']);self.assertEqual(r.status_code,200,r.json)
        r=self.game(self.a,path,'start',revision=r.json['game']['revision']);self.assertEqual(r.status_code,200,r.json)
        return path,r.json['game']
    def alter(self,path,fn):
        row=self.db.execute('SELECT * FROM community_games WHERE room_id=?',(path.split('/')[-1],)).fetchone();state=json.loads(row['state']);fn(state)
        self.db.execute('UPDATE community_games SET state=? WHERE room_id=?',(json.dumps(state),row['room_id']));self.db.commit()
    def test_story_expiration_views_reactions_and_reports(self):
        r=self.call(self.a,'/community/stories',{'body':'Noite de cinema 🎬','background':'#765432','media_url':self.upload().json['url']});self.assertEqual(r.status_code,201,r.json);sid=r.json['id']
        self.assertEqual(self.app.test_client().get('/api/community/stories').status_code,401)
        for _ in range(2):self.call(self.b,'/community/stories/'+sid+'/view')
        stories=self.a.get('/api/community/stories').json['stories'];self.assertEqual(stories[0]['views'],1)
        self.assertEqual(self.call(self.b,'/community/stories/'+sid,m='DELETE').status_code,403)
        self.assertEqual(self.call(self.b,'/community/reports',{'target_type':'story','target_id':sid,'reason':'Teste de moderação'}).status_code,201)
        for _ in range(2):self.call(self.b,'/community/reactions/story/'+sid,{'reaction':'heart'},'PUT')
        self.assertEqual(self.a.get('/api/community/stories/'+sid).json['reactions']['counts'],{'heart':1})
        self.db.execute('UPDATE community_stories SET expires_at=?',(time.time()-1,));self.db.commit()
        self.assertEqual(self.a.get('/api/community/stories').json['stories'],[])
        self.assertEqual(self.a.get('/api/community/stories/'+sid).status_code,404)
        self.assertEqual(self.call(self.b,'/community/reactions/story/'+sid,{'reaction':'fire'},'PUT').status_code,404)
    def test_assets_validation_owner_moderation_and_expiry(self):
        self.assertEqual(self.upload(content=b'\x89PNG\r\n\x1a\nxxxxIHDR').status_code,400)
        self.assertEqual(self.upload(content=b'<svg onload="alert(1)">').status_code,400)
        r=self.upload();self.assertEqual(r.status_code,201,r.json);url=r.json['url']
        response=self.b.get(url);self.assertEqual(response.mimetype,'image/png');response.close();self.assertEqual(self.app.test_client().get(url).status_code,401)
        self.assertEqual(self.b.delete(url,headers=self.headers).status_code,403)
        self.assertEqual(self.call(self.b,'/community/stories',{'media_url':url}).status_code,404)
        sid=self.call(self.a,'/community/stories',{'media_url':url}).json['id']
        self.db.execute('UPDATE community_assets SET expires_at=?',(time.time()-1,));self.db.commit()
        self.assertEqual(self.a.get(url).status_code,404)
        self.assertEqual(self.a.get('/api/community/assets').json['assets'],[])
        url=self.upload().json['url'];aid=url.rsplit('/',1)[-1]
        self.assertEqual(self.call(self.b,'/admin/community/social/assets/'+aid,{},'PATCH').status_code,403)
        self.assertEqual(self.call(self.admin,'/admin/community/social/assets/'+aid,{},'PATCH').status_code,200)
        self.assertEqual(self.a.get(url).status_code,404)
    def test_reel_upload_range_permanent_cover_and_story(self):
        content=b'\x00\x00\x00\x20ftypisom'+b'\x00'*300
        r=self.upload(content=content);self.assertEqual(r.status_code,201,r.json);url=r.json['url']
        partial=self.a.get(url,headers={'Range':'bytes=0-31'});self.assertEqual(partial.status_code,206);self.assertEqual(len(partial.data),32);partial.close()
        pid=self.call(self.a,'/community/posts',{'kind':'reel','title':'Reel','composition':{'items':[{'url':url,'type':'video','duration':10}]}}).json['id'];self.assertEqual(self.a.get('/api/community/feed?kind=reel').json['posts'][0]['id'],pid)
        image=self.upload().json['url']
        self.assertEqual(self.call(self.a,'/community/profile',{'name':'Alice','cover':image},'PATCH').status_code,200)
        self.assertEqual(self.call(self.a,'/community/stories',{'media_url':image}).status_code,201)
        self.assertIsNone(self.db.execute('SELECT expires_at FROM community_assets WHERE id=?',(image.rsplit('/',1)[-1],)).fetchone()[0])
        self.assertEqual(self.call(self.a,'/community/posts',{'kind':'reel','title':'Bad image','url':image}).status_code,400)
    def test_reactions_unique_access_and_rank(self):
        pid=self.post();route='/community/reactions/post/'+pid
        for _ in range(3):self.call(self.b,route,{'reaction':'heart'},'PUT')
        self.call(self.b,route,{'reaction':'fire'},'PUT');self.call(self.a,route,{'reaction':'heart'},'PUT')
        self.assertEqual(self.a.get('/api'+route).json['reactions']['counts'],{'heart':1,'fire':1})
        score=next(p['score'] for p in self.b.get('/api/community/discover').json['people'] if p['id']==self.ua['id']);self.assertEqual(score,2)
        self.call(self.b,route,m='DELETE');self.assertEqual(self.a.get('/api'+route).json['reactions']['counts'],{'heart':1})
        path=self.room();self.call(self.a,path+'/messages',{'body':'Hello'});mid=self.call(self.a,path+'/poll').json['room']['messages'][0]['id']
        self.assertEqual(self.call(self.b,'/community/reactions/message/'+str(mid),{'reaction':'heart'},'PUT').status_code,403)
        self.admit(path);self.assertEqual(self.call(self.b,'/community/reactions/message/'+str(mid),{'reaction':'heart'},'PUT').status_code,200)
    def test_inbox_presence_typing_read_and_friend_access(self):
        self.assertEqual(self.call(self.a,'/community/presence',{'typing_to':self.ub['id']}).status_code,403)
        self.call(self.a,'/social/friends',{'username':'bruno'});self.call(self.b,'/social/friends/'+self.ua['id'],m='PATCH')
        self.call(self.b,'/community/presence',{'typing_to':self.ua['id']})
        self.call(self.b,'/community/dm/'+self.ua['id'],{'body':'[sticker:popcorn]'})
        u=self.a.get('/api/community/inbox').json['friends'][0];self.assertTrue(u['online']);self.assertTrue(u['typing']);self.assertEqual(u['unread'],1)
        self.call(self.a,'/community/dm/'+self.ub['id']+'/read');self.assertEqual(self.a.get('/api/community/inbox').json['friends'][0]['unread'],0)
        self.assertEqual(self.c.get('/api/community/inbox').json['friends'],[])
        self.db.execute('UPDATE community_online SET seen_at=?,typing_at=?',(time.time()-65,time.time()-8));self.db.commit()
        u=self.a.get('/api/community/inbox').json['friends'][0];self.assertFalse(u['online']);self.assertFalse(u['typing'])
    def test_card_game_turns_hidden_hands_revision_and_awards(self):
        path,g=self.start_game('colors');a,b=self.ua['id'],self.ub['id']
        gb=self.game(self.b,path).json['game'];self.assertEqual(len(g['hand']),7);self.assertEqual(len(gb['hand']),7);self.assertNotIn('hands',gb);self.assertNotIn('deck',gb)
        self.assertEqual(self.game(self.c,path).status_code,403)
        self.assertEqual(self.game(self.b,path,'draw',revision=g['revision']).status_code,409)
        self.assertEqual(self.game(self.a,path,'draw',revision=g['revision']-1).status_code,409)
        self.assertEqual(self.game(self.a,path,'play',revision=g['revision'],card='red:NOTREAL').status_code,400)
        self.alter(path,lambda s:s.update(hands={a:['red:3'],b:['blue:7']},discard=['red:5'],color='red'))
        r=self.game(self.a,path,'play',revision=g['revision'],card='red:3');self.assertEqual(r.status_code,200,r.json);self.assertEqual(r.json['game']['status'],'finished')
        for _ in range(3):self.game(self.a,path)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM community_game_results').fetchone()[0],2)
        p=self.b.get('/api/community/profiles/alice').json['profile'];self.assertEqual(p['wins'],1);self.assertEqual(p['game_points'],30);self.assertIn('primeira-vitoria',[x['id'] for x in p['badges']])
        self.assertEqual(self.game(self.a,path,'cancel',revision=r.json['game']['revision']).status_code,409)
    def test_reward_cap_and_deleted_badge_do_not_break_completion(self):
        path,g=self.start_game('colors');a,b=self.ua['id'],self.ub['id']
        self.db.execute('DELETE FROM community_badges WHERE id=?',('primeira-vitoria',))
        self.db.execute('INSERT INTO community_game_results VALUES(?,?,?,?,?,?)',('earlier',a,'colors',195,0,time.time()));self.db.commit()
        self.alter(path,lambda s:s.update(hands={a:['red:3'],b:['blue:7']},discard=['red:5'],color='red'))
        r=self.game(self.a,path,'play',revision=g['revision'],card='red:3');self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(self.db.execute('SELECT points FROM community_game_results WHERE game_id=? AND user_id=?',(g['id'],a)).fetchone()[0],5)
        self.assertEqual(self.b.get('/api/community/profiles/alice').json['profile']['game_points'],200)

    def test_drawing_secret_strokes_guess_and_round_scoring(self):
        path,g=self.start_game('draw');self.assertIn('word',g);b=self.game(self.b,path).json['game'];self.assertNotIn('word',b)
        payload={'points':[[.1,.2],[.4,.6]],'width':6,'color':'#fafafa','round':g['round']}
        self.assertEqual(self.game(self.b,path,'stroke',**payload).status_code,403)
        self.assertEqual(self.game(self.a,path,'stroke',**{**payload,'points':[[0,0],[2,1]]}).status_code,400)
        self.assertEqual(self.game(self.a,path,'stroke',**payload).status_code,200)
        self.assertEqual(len(self.game(self.b,path).json['game']['strokes']),1)
        r=self.game(self.b,path,'guess',round=g['round'],text=g['word']);self.assertEqual(r.status_code,200,r.json);self.assertEqual(r.json['game']['phase'],'reveal');self.assertEqual(r.json['game']['guesses'][-1]['text'],'Acertou!')
        self.alter(path,lambda s:s.update(deadline=time.time()-1));self.game(self.a,path)
        b=self.game(self.b,path).json['game'];self.assertEqual(b['round'],2);self.assertIn('word',b);self.assertNotIn('word',self.game(self.a,path).json['game'])
        self.game(self.a,path,'guess',round=b['round'],text=b['word']);self.alter(path,lambda s:s.update(deadline=time.time()-1))
        self.assertEqual(self.game(self.a,path).json['game']['status'],'finished');self.assertEqual(self.db.execute('SELECT COUNT(*) FROM community_game_results').fetchone()[0],2)
    def test_admin_social_can_preview_and_moderate_without_game_secrets(self):
        path,g=self.start_game('draw');story=self.call(self.a,'/community/stories',{'body':'Story a moderar','media_url':self.upload().json['url']}).json['id'];self.upload()
        self.assertEqual(self.b.get('/api/admin/community/social').status_code,403)
        response=self.admin.get('/api/admin/community/social');self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(len(response.json['games']),1);self.assertNotIn('state',response.json['games'][0]);self.assertNotIn('word',response.json['games'][0])
        self.assertEqual(self.call(self.admin,'/admin/community/social/stories/'+story,{},'PATCH').status_code,200)
        self.assertEqual(self.b.get('/api/community/stories/'+story).status_code,404)
        self.assertEqual(self.call(self.admin,'/admin/community/social/games/'+g['id'],{},'PATCH').status_code,200)
        self.assertEqual(self.game(self.b,path).json['game']['status'],'cancelled')

    def test_game_timeout_and_cancel_do_not_award(self):
        path,g=self.start_game('colors');self.alter(path,lambda s:s.update(deadline=time.time()-1))
        r=self.game(self.b,path).json['game'];self.assertEqual(r['counts'][self.ua['id']],8);self.assertEqual(r['turn'],self.ub['id'])
        self.assertEqual(self.game(self.b,path,'cancel',revision=r['revision']).status_code,403)
        r=self.game(self.a,path,'cancel',revision=r['revision']);self.assertEqual(r.status_code,200)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM community_game_results').fetchone()[0],0)

if __name__=='__main__':unittest.main()
