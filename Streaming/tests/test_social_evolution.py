"""Integrated permission, text, music and notification regression tests."""
import io,json,time,unittest
from unittest.mock import patch,MagicMock
import test_community as base
from social_text import normalize
import notification_payload

class EvolutionTests(unittest.TestCase):
    setUp=base.CommunityTests.setUp;tearDown=base.CommunityTests.tearDown;call=base.CommunityTests.call;user=base.CommunityTests.user
    def friends(self):self.call(self.a,'/social/friends',{'username':'bruno'});self.call(self.b,'/social/friends/'+self.ua['id'],m='PATCH')
    def music(self,n=1):
        import flix_music
        t=flix_music.save_track(self.db,{'id':n,'title':'Faixa '+str(n),'permalink_url':'https://soundcloud.com/artist/track-'+str(n),'user':{'username':'Artista'},'duration':90000,'genre':'Ambient','release_date':'2026-10-01'});self.db.commit();return t
    def test_unicode_text_round_trip_does_not_decode_markup_or_change_passwords(self):
        raw=r':heart: &#128525; &#x1f602; \uD83D\uDD25 \u{1F3B5}'
        self.assertEqual(normalize(raw),'❤️ 😍 😂 🔥 🎵');self.assertEqual(normalize('&lt;script&gt; &#60;script&#62;'),'&lt;script&gt; &#60;script&#62;')
        r=self.call(self.a,'/community/posts',{'kind':'discussion','title':'Meu momento :heart:','body':raw});self.assertEqual(r.status_code,201,r.json);pid=r.json['id']
        self.assertEqual(self.b.get('/api/community/posts/'+pid).json['post']['body'],'❤️ 😍 😂 🔥 🎵');self.assertEqual(self.db.execute('SELECT body FROM community_posts WHERE id=?',(pid,)).fetchone()[0],'❤️ 😍 😂 🔥 🎵')
        self.friends();self.call(self.a,'/hub/dm/'+self.ub['id'],{'body':raw});self.assertEqual(self.b.get('/api/hub/dm/'+self.ua['id']).json['messages'][0]['body'],'❤️ 😍 😂 🔥 🎵')
    def test_verification_admin_only_and_revoke(self):
        path='/community/verification';r=self.call(self.a,path,{'reason':'Criadora de conteúdo com atuação pública na comunidade.','links':'https://example.com/alice'});self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(self.call(self.a,path,{'reason':'Outro pedido de verificação para a mesma conta.'}).status_code,409)
        admin='/admin/verifications/'+self.ua['id'];self.assertEqual(self.call(self.b,admin,{'action':'approve'},'PATCH').status_code,403)
        self.assertEqual(self.call(self.admin,admin,{'action':'approve'},'PATCH').status_code,200)
        self.assertTrue(self.a.get('/api/bootstrap').json['user']['verified']);self.assertTrue(self.b.get('/api/community/profiles/alice').json['profile']['verified'])
        self.call(self.a,'/community/profile',{'name':'alice','username':'alice','verified':False},'PATCH');self.assertTrue(self.a.get('/api/bootstrap').json['user']['verified'])
        self.call(self.admin,admin,{'action':'remove','note':'Revisão administrativa'},'PATCH');self.assertFalse(self.a.get('/api/bootstrap').json['user']['verified'])
    def test_spaces_membership_private_feed_and_page_publishing(self):
        r=self.call(self.a,'/community/spaces',{'kind':'community','name':'Clube privado','username':'clube','privacy':'private'});self.assertEqual(r.status_code,201,r.json);sid=r.json['id'];path='/community/spaces/'+sid
        self.assertEqual(self.call(self.b,path+'/members/'+self.ub['id'],{'role':'member'},'PUT').status_code,403)
        self.assertEqual(self.call(self.a,path+'/members/'+self.ub['id'],{'role':'member'},'PUT').status_code,200)
        r=self.call(self.b,'/community/posts',{'kind':'discussion','title':'Uma conversa privada','body':'Só para membros','space_id':sid});self.assertEqual(r.status_code,201,r.json);pid=r.json['id']
        self.assertEqual(self.c.get('/api/community/posts/'+pid).status_code,404);self.assertNotIn(pid,[p['id'] for p in self.c.get('/api/community/feed').json['posts']]);self.assertEqual(self.a.get('/api/community/posts/'+pid).status_code,200)
        self.assertEqual(self.call(self.b,path+'/members/'+self.ub['id'],{'role':'admin'},'PUT').status_code,403)
        self.call(self.a,path+'/members/'+self.ub['id'],m='DELETE');self.assertEqual(self.b.get('/api/community/posts/'+pid).status_code,404)
        page=self.call(self.a,'/community/spaces',{'kind':'page','name':'Curadoria','username':'curadoria'}).json['id'];self.call(self.b,'/community/spaces/'+page+'/members/'+self.ub['id'],{'role':'follower'},'PUT')
        self.assertEqual(self.call(self.b,'/community/posts',{'kind':'discussion','title':'Post falso','space_id':page}).status_code,403)
        self.call(self.a,'/community/spaces/'+page+'/members/'+self.ub['id'],{'role':'admin'},'PUT');r=self.call(self.b,'/community/posts',{'kind':'discussion','title':'Post da página','space_id':page});self.assertEqual(r.status_code,201,r.json);self.assertEqual(self.c.get('/api/community/posts/'+r.json['id']).json['post']['space']['name'],'Curadoria')
    def test_group_messages_reuse_dm_permissions_idempotency_and_handoff(self):
        self.friends();r=self.call(self.a,'/hub/groups',{'name':'Turma do cinema','members':[self.ub['id']]});self.assertEqual(r.status_code,201,r.json);gid=r.json['id'];path='/hub/groups/'+gid
        self.assertEqual(self.c.get('/api'+path).status_code,404)
        msg={'body':'Bora :heart:','client_id':'dedupe-group-message'}
        self.assertEqual(self.call(self.a,path+'/messages',msg).status_code,200);self.assertEqual(self.call(self.a,path+'/messages',msg).status_code,200)
        self.assertEqual(len(self.b.get('/api'+path+'/messages').json['messages']),1);self.assertEqual(self.b.get('/api/hub/dm/'+self.ua['id']).json['messages'],[])
        notices=self.b.get('/api/hub/notifications').json['notifications'];n=next(n for n in notices if n['type']=='group_message');self.assertEqual(n['body'],'Bora ❤️');self.assertEqual(n['conversationId'],'group:'+gid)
        self.assertEqual(self.call(self.b,path+'/members/'+self.ub['id'],{'role':'admin'},'PUT').status_code,403)
        self.call(self.b,path+'/read');self.assertEqual(self.b.get('/api/hub/inbox').json['groups'][0]['unread'],0)
        self.call(self.a,path+'/members/'+self.ua['id'],m='DELETE');self.assertEqual(self.b.get('/api'+path).json['group']['role'],'admin');self.assertEqual(self.a.get('/api'+path+'/messages').status_code,404)
    def test_music_queue_playlist_and_real_play_deduplication(self):
        t=self.music();u=self.music(2)
        r=self.call(self.a,'/music/queue',{'tracks':[t['id'],u['id']],'index':0,'revision':0},'PUT');self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(self.call(self.a,'/music/queue',{'tracks':[],'revision':0},'PUT').status_code,409)
        p=self.call(self.a,'/music/playlists',{'name':'Minha trilha','public':False}).json['id'];self.assertEqual(self.call(self.a,'/music/playlists/'+p,{'tracks':[u['id'],t['id']]},'PUT').status_code,200)
        self.assertEqual(self.b.get('/api/music/playlists/'+p).status_code,404);self.assertEqual(self.call(self.b,'/music/playlists/'+p,{'tracks':[]},'PUT').status_code,404)
        self.assertEqual([x['id'] for x in self.a.get('/api/music/playlists/'+p).json['playlist']['tracks']],[u['id'],t['id']])
        path='/music/tracks/'+t['id']+'/plays';session='real-play-session';self.call(self.a,path,{'session':session,'position':0,'playing':True})
        for _ in range(8):self.call(self.a,path,{'session':session,'position':60,'playing':True})
        self.assertEqual(self.db.execute('SELECT SUM(counted) FROM music_play_events').fetchone()[0],0)
        self.db.execute('UPDATE music_play_events SET position=0');self.db.commit()
        for n in range(1,8):
            self.db.execute('UPDATE music_play_events SET last_at=?',(time.time()-5,));self.db.commit();self.call(self.a,path,{'session':session,'position':n*5,'playing':True})
        self.assertEqual(self.db.execute('SELECT SUM(counted) FROM music_play_events').fetchone()[0],1)
        for _ in range(3):self.call(self.a,path,{'session':session,'position':35,'playing':True})
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM music_play_events').fetchone()[0],1);self.assertEqual(self.a.get('/api/music/catalog').json['tracks'][0]['plays'],1)
    def test_music_room_server_clock_host_permissions_and_text_only(self):
        t=self.music();u=self.music(2);r=self.call(self.a,'/community/rooms',{'kind':'music','title':'Som da turma','track_id':t['id'],'approval':False});self.assertEqual(r.status_code,201,r.json);rid=r.json['room']['id'];path='/music/rooms/'+rid+'/state';self.call(self.b,'/community/rooms/'+rid+'/join')
        s=self.a.get('/api'+path).json['room'];self.assertEqual(s['track']['id'],t['id'])
        self.assertEqual(self.call(self.b,path,{'action':'play','revision':s['revision']},'PATCH').status_code,403)
        self.call(self.a,path,{'action':'play','position':21,'revision':s['revision']},'PATCH');s=self.b.get('/api'+path).json['room'];self.assertGreaterEqual(s['current_position'],21);self.assertLess(s['current_position'],23)
        self.assertEqual(self.call(self.a,'/community/rooms/'+rid+'/signals',{'recipient':self.ub['id'],'payload':{'type':'offer','sdp':'test'}}).status_code,403)
        self.call(self.a,path,{'action':'add','track_id':u['id'],'revision':s['revision']},'PATCH');s=self.a.get('/api'+path).json['room'];order=[q['id'] for q in reversed(s['queue'])];self.call(self.a,path,{'action':'reorder','order':order,'revision':s['revision']},'PATCH');s=self.a.get('/api'+path).json['room'];self.assertEqual([q['id'] for q in s['queue']],order)
        self.call(self.a,'/community/rooms/'+rid+'/leave');self.assertEqual(self.b.get('/api'+path).json['room']['host_id'],self.ub['id'])
    def test_soundcloud_config_secret_cache_and_music_normalization(self):
        r=self.a.get('/api/community/music/search?q=ambient');self.assertFalse(r.json['configured']);self.assertEqual(r.json['provider'],'soundcloud')
        self.call(self.admin,'/admin/settings',{'brand':'Flix','mode':'test','soundcloud_client_id':'client-secret-id','soundcloud_client_secret':'very-secret-password'},'PUT')
        self.assertNotIn('client-secret-id',self.admin.get('/api/admin/settings').get_data(as_text=True));self.assertNotIn('very-secret-password',self.db.execute("SELECT value FROM settings WHERE key='soundcloud_client_secret'").fetchone()[0])
        responses=[{'access_token':'private-access-token','refresh_token':'private-refresh','expires_in':3600},{'collection':[{'id':23,'title':'Ambient','duration':120000,'permalink_url':'https://soundcloud.com/artist/ambient','user':{'username':'Artista'},'access':'playable'}]}]
        def response(*a,**k):
            ctx=MagicMock();ctx.__enter__.return_value.read.return_value=json.dumps(responses.pop(0)).encode();return ctx
        with patch('flix_music.urlopen',side_effect=response) as fetch:
            r=self.a.get('/api/community/music/search?q=ambient');self.assertEqual(r.status_code,200,r.json);self.assertEqual(r.json['items'][0]['artist'],'Artista');self.assertNotIn('private-access-token',r.get_data(as_text=True));self.assertEqual(fetch.call_count,2)
            self.b.get('/api/community/music/search?q=ambient');self.assertEqual(fetch.call_count,2)
    def test_contextual_calls_actions_and_stale_calls(self):
        self.friends();r=self.call(self.a,'/hub/calls',{'recipient':self.ub['id'],'kind':'video'});cid=r.json['call']['id'];n=next(n for n in self.b.get('/api/hub/notifications').json['notifications'] if n['type']=='call_incoming');self.assertEqual(n['callType'],'video');self.assertEqual(n['callerName'],'alice');self.assertEqual([a['action'] for a in n['actions']],['answer','decline'])
        self.call(self.a,'/hub/calls/'+cid,{'action':'end'},'PATCH');ns=self.b.get('/api/hub/notifications').json['notifications'];self.assertFalse(any(n['type']=='call_incoming' for n in ns));self.assertTrue(any(n.get('callState')=='cancelled' for n in ns));self.assertFalse(any(n['type']=='call_missed' for n in ns))

    def test_private_space_never_leaks_to_notifications_discovery_or_shares(self):
        self.call(self.c,'/community/follow/'+self.ua['id'])
        sid=self.call(self.a,'/community/spaces',{'kind':'community','name':'Clube secreto','username':'secreto','privacy':'private'}).json['id']
        r=self.call(self.a,'/community/posts',{'kind':'movie','title':'Título reservado','url':'https://example.com/private.mp4','space_id':sid});self.assertEqual(r.status_code,201,r.json);pid=r.json['id']
        self.assertNotIn('Título reservado',self.c.get('/api/hub/notifications').text)
        self.assertEqual(self.c.get('/api/community/publishing/search?kind=titles&q=reservado').json['items'],[])
        with self.app.app_context():
            import social_hub
            self.assertIsNone(social_hub.share_preview(self.db,'post',pid))
        self.assertEqual(self.admin.get('/api/community/posts/'+pid).status_code,200)
        self.assertEqual(self.call(self.c,'/admin/spaces/'+sid,{'status':'hidden'},'PATCH').status_code,403)
        self.assertEqual(self.call(self.admin,'/admin/spaces/'+sid,{'status':'hidden'},'PATCH').status_code,200)
        self.assertEqual(self.a.get('/api/community/posts/'+pid).status_code,404)
        self.call(self.admin,'/admin/spaces/'+sid,{'status':'active'},'PATCH');self.assertEqual(self.a.get('/api/community/posts/'+pid).status_code,200)

    def test_editor_drawings_mentions_validation_and_expiration(self):
        c={'layers':[{'type':'mention','user_id':self.ub['id'],'text':'@bruno'}],'drawings':[{'points':[[2,2],[40,70]],'color':'#ff5781','width':1}]}
        r=self.call(self.a,'/community/stories',{'body':'Nosso cinema','composition':c});self.assertEqual(r.status_code,201,r.json);sid=r.json['id']
        story=self.b.get('/api/community/stories/'+sid).json['story'];self.assertEqual(story['composition']['drawings'][0]['points'],[[2,2],[40,70]]);self.assertEqual(story['composition']['layers'][0]['url'],'/comunidade/perfil/bruno')
        self.assertTrue(any(n['type']=='mention' for n in self.b.get('/api/hub/notifications').json['notifications']))
        c['drawings'][0]['points']=[[0,0],[101,2]];self.assertEqual(self.call(self.a,'/community/stories',{'body':'Fora dos limites','composition':c}).status_code,400)
        self.db.execute('UPDATE community_stories SET expires_at=? WHERE id=?',(time.time()-1,sid));self.db.commit();self.assertEqual(self.b.get('/api/community/stories/'+sid).status_code,404)

    def test_music_admin_and_legacy_room_migration_is_idempotent(self):
        import flix_music
        tid=self.music()['id'];self.assertEqual(self.call(self.b,'/admin/music/'+tid,{'featured':True},'PATCH').status_code,403)
        self.assertEqual(self.call(self.admin,'/admin/music/'+tid,{'featured':True,'genre':'Jazz'},'PATCH').status_code,200)
        self.assertEqual(self.a.get('/api/music/catalog').json['tracks'][0]['genre'],'Jazz')
        r=self.call(self.a,'/community/rooms',{'title':'Rádio anterior','kind':'music','url':'https://example.com/legacy.mp3','approval':False});rid=r.json['room']['id']
        flix_music.migrate(self.db);self.db.commit();flix_music.migrate(self.db);self.db.commit()
        value=self.a.get('/api/music/rooms/'+rid+'/state').json['room'];self.assertEqual(value['track']['url'],'https://example.com/legacy.mp3');self.assertEqual(len(value['queue']),1)
        self.assertEqual(self.call(self.a,'/community/rooms/'+rid+'/queue',{'title':'Bypass','url':'https://example.com/another.mp3'}).status_code,409)
        self.assertEqual(self.call(self.a,'/music/rooms/'+rid+'/state',{'action':'reorder','order':[{}],'revision':value['revision']},'PATCH').status_code,400)
        self.assertEqual(self.db.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertFalse(self.db.execute('PRAGMA foreign_key_check').fetchall())

if __name__=='__main__':unittest.main()
