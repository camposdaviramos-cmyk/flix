import base64
import json
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from werkzeug.security import generate_password_hash

class CommunityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=create_app(self.tmp.name,testing=True)
        self.db=sqlite3.connect(Path(self.tmp.name)/'vyra.sqlite3');self.db.row_factory=sqlite3.Row
        self.db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Admin-test-123'),));self.db.commit()
        self.headers={'X-Requested-With':'VYRA'};self.admin=self.app.test_client()
        self.call(self.admin,'/auth/login',{'email':'admin@vyra.local','password':'Admin-test-123'})
        self.a,self.ua=self.user('alice');self.b,self.ub=self.user('bruno');self.c,self.uc=self.user('carol')
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def call(self,c,p,d=None,m='POST'):return c.open('/api'+p,method=m,json=d or {},headers=self.headers)
    def user(self,name):
        r=self.call(self.admin,'/admin/users',{'name':name,'username':name,'email':name+'@example.com','password':'Customer-test-123'})
        self.assertEqual(r.status_code,201,r.json);c=self.app.test_client();self.call(c,'/auth/login',{'email':name+'@example.com','password':'Customer-test-123'});return c,r.json['user']
    def post(self,kind='movie',url='https://example.com/movie.mp4'):
        r=self.call(self.a,'/community/posts',{'kind':kind,'title':'Uma boa história','body':'Vamos conversar?','url':url});self.assertEqual(r.status_code,201,r.json);return r.json['id']
    def room(self,**extra):
        r=self.call(self.a,'/community/rooms',dict(title='Sala de teste',kind='watch',url='https://example.com/movie.mp4',**extra));self.assertEqual(r.status_code,201,r.json);return '/community/rooms/'+r.json['room']['id']
    def admit(self,path):
        self.assertEqual(self.call(self.b,path+'/join').status_code,202)
        self.assertEqual(self.call(self.a,path+'/members/'+self.ub['id'],{'decision':'approve'},'PATCH').status_code,200)
        self.assertEqual(self.call(self.b,path+'/join').status_code,200)
    def test_posts_privacy_likes_views_and_comments(self):
        pid=self.post();p='/community/posts/'+pid
        self.assertEqual(self.call(self.a,p+'/like').status_code,400)
        for _ in range(3):self.assertEqual(self.call(self.b,p+'/like').status_code,200)
        for _ in range(3):self.assertEqual(self.call(self.b,p+'/view').status_code,200)
        self.call(self.b,p+'/comments',{'body':'<script>bad</script>'})
        d=self.a.get('/api'+p).json;self.assertEqual(d['post']['likes'],1);self.assertEqual(d['post']['views'],1)
        self.assertEqual(d['comments'][0]['body'],'<script>bad</script>');self.assertNotIn('email',d['post'])
        cid=d['comments'][0]['id'];self.assertEqual(self.call(self.c,'/community/comments/'+str(cid),m='DELETE').status_code,403);self.assertEqual(self.call(self.a,'/community/comments/'+str(cid),m='DELETE').status_code,200)
        self.assertEqual(self.call(self.b,p,{'kind':'news','title':'bad'},'PATCH').status_code,403)
        self.assertEqual(self.call(self.b,p,m='DELETE').status_code,403)
        self.assertEqual(self.call(self.a,p,m='DELETE').status_code,200)
        self.assertEqual(self.b.get('/api'+p).status_code,404)
        self.assertEqual(self.b.get('/api/community/discover').json['top'],[])
    def test_media_url_validation_and_youtube(self):
        for url in ['javascript:alert(1)','http://example.com/v.mp4','https://localhost/v.mp4','https://127.0.0.1/v.mp4','https://example.com:8443/v.mp4','https://user:pass@example.com/v.mp4','https://youtube.com/watch?v=invalid','https://example.com/page']:
            self.assertEqual(self.call(self.a,'/community/posts',{'title':'Test','kind':'movie','url':url}).status_code,400,url)
        pid=self.post(url='https://youtu.be/abcdefghijk?t=30')
        self.assertEqual(self.a.get('/api/community/posts/'+pid).json['post']['media_type'],'youtube')
        self.post(kind='news',url='https://example.com/news');self.post(kind='discussion',url='')
    def test_profiles_follows_badges_and_avatar(self):
        # Browser canvas produces a normalized PNG; a valid 1px PNG here.
        png='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZkAAAAASUVORK5CYII='
        d={'name':'Alice Cinema','bio':'Amo filmes','avatar':'data:image/png;base64,'+png,'favorite_genres':'Drama','website':'https://example.com'}
        self.assertEqual(self.call(self.a,'/community/profile',d,'PATCH').status_code,200)
        self.assertEqual(self.a.get('/api/community/avatars/'+self.ua['id']).mimetype,'image/png')
        self.assertEqual(self.call(self.a,'/community/profile',{**d,'avatar':'data:image/svg+xml,bad'},'PATCH').status_code,400)
        for _ in range(2):self.call(self.b,'/community/follow/'+self.ua['id'])
        p=self.b.get('/api/community/profiles/alice').json['profile'];self.assertEqual(p['followers'],1);self.assertTrue(p['is_following']);self.assertNotIn('email',p);self.assertNotIn('avatar_png',p)
        self.assertEqual(self.call(self.b,'/admin/community/awards',{'username':'alice','badge_id':'curador'}).status_code,403)
        self.assertEqual(self.call(self.admin,'/admin/community/awards',{'username':'alice','badge_id':'curador'}).status_code,200)
        self.assertEqual(self.b.get('/api/community/profiles/alice').json['profile']['badges'][0]['id'],'curador')
        self.call(self.admin,'/admin/community/awards',{'username':'alice','badge_id':'curador'},'DELETE')
        self.assertEqual(self.b.get('/api/community/profiles/alice').json['profile']['badges'],[])
    def test_dm_only_friends(self):
        path='/community/dm/'+self.ub['id'];self.assertEqual(self.a.get('/api'+path).status_code,403)
        self.call(self.a,'/social/friends',{'username':'bruno'});self.call(self.b,'/social/friends/'+self.ua['id'],m='PATCH')
        self.call(self.a,path,{'body':'Olá!'});self.assertEqual(self.b.get('/api/community/dm/'+self.ua['id']).json['messages'][0]['body'],'Olá!')
        self.assertEqual(self.c.get('/api'+path).status_code,403)
        self.call(self.a,'/social/friends/'+self.ub['id'],m='DELETE');self.assertEqual(self.a.get('/api'+path).status_code,403)
    def test_room_admission_sync_rejection_and_queue(self):
        path=self.room();self.assertEqual(self.call(self.b,path+'/poll').status_code,403)
        self.assertEqual(self.call(self.b,path+'/messages',{'body':'intrusão'}).status_code,403)
        self.admit(path);self.assertEqual(self.call(self.b,path+'/playback',{'position':60,'paused':False,'revision':1},'PATCH').status_code,403)
        self.assertEqual(self.call(self.a,path+'/playback',{'position':60,'paused':False,'revision':1},'PATCH').status_code,200)
        self.assertEqual(self.call(self.a,path+'/playback',{'position':0,'paused':True,'revision':1},'PATCH').status_code,409)
        r=self.call(self.b,path+'/poll').json['room'];self.assertEqual(r['position'],60);self.assertEqual(r['paused'],0)
        self.call(self.c,path+'/join');self.call(self.a,path+'/members/'+self.uc['id'],{'decision':'reject'},'PATCH')
        self.call(self.c,path+'/leave');self.assertEqual(self.call(self.c,path+'/join').status_code,403)
        self.assertEqual(self.call(self.b,path+'/queue',{'title':'Próximo','url':'https://example.com/audio.mp3'}).status_code,403)
        self.call(self.a,path+'/queue',{'title':'Próximo','url':'https://example.com/audio.mp3'})
        q=self.call(self.a,path+'/poll').json['room']['queue'][0]
        self.call(self.a,path+'/queue/'+str(q['id']))
        r=self.call(self.b,path+'/poll').json['room'];self.assertEqual(r['position'],0);self.assertEqual(r['media_type'],'audio');self.assertEqual(r['paused'],1)
        self.call(self.a,path+'/members/'+self.ub['id'],{'decision':'remove'},'PATCH');self.assertEqual(self.call(self.b,path+'/poll').status_code,403)
    def test_room_no_fixed_seat_limit_and_signals(self):
        path=self.room(approval=False);rid=path.split('/')[-1]
        for n in range(35):
            uid='seat'+str(n);self.db.execute("INSERT INTO users(id,name,username,email,password,created_at) VALUES(?,?,?,?,?,?)",(uid,uid,uid,uid+'@example.com','unused',time.time()));self.db.execute("INSERT INTO community_members(room_id,user_id,status,joined_at,seen_at) VALUES(?,?,'joined',?,?)",(rid,uid,time.time(),time.time()))
        self.db.commit();self.assertEqual(self.call(self.b,path+'/join').status_code,200)
        self.assertEqual(len(self.call(self.a,path+'/poll').json['room']['members']),37)
        self.call(self.a,path+'/signals',{'recipient':self.ub['id'],'payload':{'type':'offer','sdp':'test'}})
        self.assertEqual(len(self.call(self.b,path+'/poll').json['signals']),1)
        self.assertEqual(self.call(self.c,path+'/poll').status_code,403)
        self.call(self.a,path,m='DELETE');self.assertEqual(self.call(self.b,path+'/poll').status_code,404)
    def test_moderation_permissions_and_audit(self):
        pid=self.post();self.call(self.b,'/community/reports',{'target_type':'post','target_id':pid,'reason':'Revisar este conteúdo'})
        self.assertEqual(self.a.get('/api/admin/community').status_code,403)
        self.call(self.admin,'/admin/community/posts/'+pid,{'action':'hide'},'PATCH')
        self.assertEqual(self.a.get('/api/community/posts/'+pid).status_code,404)
        d=self.admin.get('/api/admin/community').json;self.assertEqual(d['counts']['open_reports'],1);self.assertEqual(len(d['audit']),1)
        report=d['reports'][0]['id'];self.call(self.admin,'/admin/community/reports/'+str(report),{'action':'resolve'},'PATCH')
        self.assertEqual(self.admin.get('/api/admin/community').json['counts']['open_reports'],0)
        self.call(self.admin,'/admin/community/posts/'+pid,{'action':'publish'},'PATCH');self.assertEqual(self.a.get('/api/community/posts/'+pid).status_code,200)
    def test_host_offline_pauses_and_moderation_removes_source(self):
        pid=self.post();path=self.room(post_id=pid,approval=False,permanent=True);self.call(self.b,path+'/join')
        self.call(self.a,path+'/playback',{'position':25,'paused':False,'revision':1},'PATCH')
        self.call(self.a,path+'/leave')
        r=self.call(self.b,path+'/poll').json['room'];self.assertEqual(r['paused'],1);self.assertFalse(r['host_online'])
        self.assertGreaterEqual(r['position'],25)
        self.call(self.admin,'/admin/community/posts/'+pid,{'action':'hide'},'PATCH')
        self.assertEqual(self.call(self.b,path+'/poll').status_code,404)
        self.assertEqual(self.b.get('/api/community/rooms').json['rooms'],[])

    def test_live_viewers_cannot_publish_or_signal_each_other(self):
        r=self.call(self.a,'/community/rooms',{'title':'Live de teste','kind':'live','approval':False})
        self.assertEqual(r.status_code,201,r.json);path='/community/rooms/'+r.json['room']['id']
        self.call(self.b,path+'/join');self.call(self.c,path+'/join')
        r=self.call(self.b,path+'/poll',{'mic':True,'camera':True}).json['room']
        guest=next(u for u in r['members'] if u['id']==self.ub['id'])
        self.assertEqual(guest['mic'],0);self.assertEqual(guest['camera'],0)
        self.assertEqual(self.call(self.b,path+'/signals',{'recipient':self.uc['id'],'payload':{'type':'offer','sdp':'x'}}).status_code,403)
        self.assertEqual(self.call(self.b,path,{'title':'Intrusão','description':''},'PATCH').status_code,403)
        self.assertEqual(self.call(self.a,path,{'title':'Novo título','description':'Nova descrição','approval':True},'PATCH').status_code,200)

    def test_username_change_is_atomic_with_profile(self):
        r=self.call(self.a,'/community/profile',{'name':'Alteração parcial','username':'bruno','bio':'test'},'PATCH')
        self.assertEqual(r.status_code,409)
        p=self.a.get('/api/community/profiles/alice').json['profile']
        self.assertEqual(p['name'],'alice');self.assertEqual(p['bio'],'')
        self.assertEqual(self.a.get('/api/community/people?q=bruno').json['people'][0]['id'],self.ub['id'])

    def test_blocked_account_and_routes(self):
        path=self.room(approval=False);self.call(self.b,path+'/join');self.db.execute("UPDATE users SET status='blocked' WHERE id=?",(self.ub['id'],));self.db.commit()
        self.assertEqual(self.call(self.b,path+'/poll').status_code,401)
        self.assertEqual(len(self.call(self.a,path+'/poll').json['room']['members']),1)
        for url in ['/comunidade','/comunidade/perfil/alice','/comunidade/sala/'+path.split('/')[-1]]:self.assertEqual(self.a.get(url).status_code,200)
        self.assertIn('camera=(self)',self.a.get('/').headers['Permissions-Policy'])
        self.assertIn('frame-src https://www.youtube.com',self.a.get('/').headers['Content-Security-Policy'])
        create_app(self.tmp.name,testing=True);self.assertEqual(self.a.get('/api/community/rooms').status_code,200)

    def test_stage_permissions_and_forced_mute(self):
        path=self.room(approval=False);self.call(self.b,path+'/join')
        poll=self.call(self.b,path+'/poll',{'mic':True,'camera':True}).json['room']
        me=next(u for u in poll['members'] if u['id']==self.ub['id'])
        self.assertIsNone(me['seat']);self.assertEqual(me['mic'],0);self.assertEqual(poll['seat_limit'],8)
        action=path+'/members/'+self.ub['id']
        self.assertEqual(self.call(self.b,action,{'decision':'promote'},'PATCH').status_code,403)
        self.assertEqual(self.call(self.a,action,{'decision':'promote'},'PATCH').status_code,200)
        me=next(u for u in self.call(self.b,path+'/poll',{'mic':True}).json['room']['members'] if u['id']==self.ub['id'])
        self.assertEqual(me['seat'],2);self.assertEqual(me['mic'],1)
        self.call(self.a,action,{'decision':'mute'},'PATCH')
        me=next(u for u in self.call(self.b,path+'/poll',{'mic':True,'mic_blocked':False,'seat':2}).json['room']['members'] if u['id']==self.ub['id'])
        self.assertEqual(me['mic'],0);self.assertEqual(me['mic_blocked'],1)
        self.call(self.a,action,{'decision':'allow_mic'},'PATCH')
        me=next(u for u in self.call(self.b,path+'/poll').json['room']['members'] if u['id']==self.ub['id'])
        self.assertEqual(me['mic'],0);self.assertEqual(me['mic_blocked'],0)
        self.call(self.a,action,{'decision':'demote'},'PATCH')
        me=next(u for u in self.call(self.b,path+'/poll',{'mic':True}).json['room']['members'] if u['id']==self.ub['id'])
        self.assertIsNone(me['seat']);self.assertEqual(me['mic'],0)
        self.assertEqual(self.call(self.a,action,{'decision':'promote'},'PATCH').status_code,200)
        self.call(self.b,path+'/leave');self.call(self.b,path+'/join')
        me=next(u for u in self.call(self.b,path+'/poll').json['room']['members'] if u['id']==self.ub['id'])
        self.assertIsNone(me['seat'])

    def test_eight_seats_concurrent_promotion_and_migration(self):
        from concurrent.futures import ThreadPoolExecutor
        path=self.room(approval=False);rid=path.split('/')[-1];ids=[]
        for n in range(12):
            user='stage'+str(n);ids.append(user)
            self.db.execute("INSERT INTO users(id,name,username,email,password,created_at) VALUES(?,?,?,?,?,?)",(user,user,user,user+'@example.com','unused',time.time()))
            self.db.execute("INSERT INTO community_members(room_id,user_id,status,joined_at,seen_at) VALUES(?,?,'joined',?,?)",(rid,user,time.time(),time.time()))
        self.db.commit();cookie=self.a.get_cookie('vyra_session').value
        def promote(user):
            client=self.app.test_client();client.set_cookie('vyra_session',cookie)
            return self.call(client,path+'/members/'+user,{'decision':'promote'},'PATCH').status_code
        with ThreadPoolExecutor(max_workers=8) as pool:statuses=list(pool.map(promote,ids))
        self.assertEqual(statuses.count(200),7);self.assertEqual(statuses.count(409),5)
        r=self.call(self.a,path+'/poll').json['room'];self.assertEqual(len(r['members']),13)
        self.assertEqual(sorted(u['seat'] for u in r['members'] if u['seat']),list(range(1,9)))
        create_app(self.tmp.name,testing=True)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM community_members WHERE room_id=? AND seat IS NOT NULL',(rid,)).fetchone()[0],8)
        stale=next(u['id'] for u in r['members'] if u['seat']==2)
        self.db.execute('UPDATE community_members SET seen_at=? WHERE room_id=? AND user_id=?',(time.time()-46,rid,stale));self.db.commit()
        audience=next(u['id'] for u in r['members'] if not u['seat'])
        self.assertEqual(promote(audience),200)

    def test_free_signup_catalog_and_ratings(self):
        client=self.app.test_client();r=self.call(client,'/auth/register',{'account_type':'community','name':'Nova Pessoa','username':'novapessoa','email':'new@example.com','password':'Community-test-123','plan_id':'premium','expires_at':9999999999})
        self.assertEqual(r.status_code,200,r.json);self.assertFalse(r.json['checkout_required']);self.assertFalse(r.json['user']['subscribed']);self.assertIsNone(r.json['user']['plan_id'])
        for cid in ['horizonte','neon','anychannel']:
            self.assertEqual(client.get('/api/play/'+cid).status_code,402)
        self.assertEqual(self.call(client,'/jump/rooms',{'content_id':'horizonte'}).status_code,402)
        for kind in ['movie','series','channel','news']:
            pid=self.post(kind=kind);d=client.get('/api/community/feed?kind='+kind).json
            self.assertIn(pid,[p['id'] for p in d['posts']]);self.assertTrue(all(p['kind']==kind for p in d['posts']))
            self.assertEqual(d['posts'][0]['username'],'alice');self.assertNotIn('email',d['posts'][0])
            self.assertEqual(self.call(client,'/community/posts/'+pid+'/rating',{'score':4},'PUT').status_code,200)
            r=self.call(client,'/community/posts/'+pid+'/rating',{'score':5},'PUT');self.assertEqual(r.json['post']['rating'],5);self.assertEqual(r.json['post']['rating_count'],1)
            self.assertEqual(self.call(self.a,'/community/posts/'+pid+'/rating',{'score':5},'PUT').status_code,400)
        for score in [0,6,True,2.5,'5']:
            self.assertEqual(self.call(client,'/community/posts/'+pid+'/rating',{'score':score},'PUT').status_code,400)
        self.assertEqual(client.get('/api/community/profiles/alice').json['profile']['rating'],5)
        self.call(client,'/community/follow/'+self.ua['id'])
        self.assertTrue(client.get('/api/community/feed').json['posts'][0]['is_following'])
        room=self.call(client,'/community/rooms',{'title':'TV gratuita','kind':'watch','post_id':self.post('channel')})
        self.assertEqual(room.status_code,201,room.json)
        self.assertNotIn(pid,[p['id'] for p in client.get('/api/catalog').json['items']])
        self.assertEqual(self.call(client,'/community/posts/'+pid+'/rating',m='DELETE').status_code,200)

if __name__=='__main__':unittest.main()
