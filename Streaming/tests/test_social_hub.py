"""Room ownership, live consent, private media, calls and notification regressions."""
import base64,datetime,io,json,sqlite3,time,unittest,wave
from unittest.mock import patch
import test_community as base
import room_lifecycle,social_hub,flix_push
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

class HubTests(unittest.TestCase):
    setUp=base.CommunityTests.setUp;tearDown=base.CommunityTests.tearDown;call=base.CommunityTests.call;user=base.CommunityTests.user;room=base.CommunityTests.room;post=base.CommunityTests.post
    def friends(self):
        self.call(self.a,'/social/friends',{'username':'bruno'});self.call(self.b,'/social/friends/'+self.ua['id'],m='PATCH')
    def live(self,**kw):
        r=self.call(self.a,'/community/rooms',{'title':'Cinema ao vivo','kind':'live','approval':False,**kw});self.assertEqual(r.status_code,201,r.json);return '/community/rooms/'+r.json['room']['id']
    def notices(self,c):return c.get('/api/hub/notifications').json['notifications']
    def test_temporary_handoff_order_and_empty_close(self):
        path=self.room(approval=False);rid=path.rsplit('/',1)[-1]
        self.call(self.b,path+'/join');self.call(self.c,path+'/join');self.call(self.a,path+'/leave')
        r=self.call(self.b,path+'/poll').json['room'];self.assertEqual(r['host_id'],self.ub['id']);self.assertEqual(next(u['seat'] for u in r['members'] if u['id']==self.ub['id']),1);self.assertTrue(r['host_online'])
        self.assertEqual(self.call(self.a,path,{'title':'Ataque'},'PATCH').status_code,403)
        self.call(self.b,path+'/leave');self.assertEqual(self.call(self.c,path+'/poll').json['room']['host_id'],self.uc['id'])
        self.call(self.c,path+'/leave');self.assertEqual(self.c.get('/api'+path).status_code,404)
        self.assertEqual(self.db.execute('SELECT status FROM community_rooms WHERE id=?',(rid,)).fetchone()[0],'closed')
    def test_expired_host_elected_atomically_and_permanent_survives(self):
        path=self.room(approval=False);rid=path.rsplit('/',1)[-1];self.call(self.b,path+'/join')
        self.db.execute('UPDATE community_members SET seen_at=? WHERE user_id=?',(time.time()-90,self.ua['id']));self.db.commit()
        self.assertEqual(self.call(self.b,path+'/poll').json['room']['host_id'],self.ub['id'])
        path2=self.room(approval=False,permanent=True);self.call(self.b,path2+'/join');self.call(self.a,path2+'/leave')
        r=self.call(self.b,path2+'/poll').json['room'];self.assertEqual(r['host_id'],self.ua['id']);self.assertFalse(r['host_online']);self.assertTrue(r['permanent'])
        self.call(self.b,path2+'/leave');self.assertEqual(self.a.get('/api'+path2).status_code,200)
        self.assertEqual(self.call(self.a,path2+'/join').status_code,200)
    def test_temporary_closes_after_timeout_and_game_cancelled(self):
        path=self.live();rid=path.rsplit('/',1)[-1]
        self.db.execute('UPDATE community_members SET seen_at=? WHERE room_id=?',(time.time()-90,rid));self.db.commit()
        self.a.get('/api/community/rooms');self.assertEqual(self.a.get('/api'+path).status_code,404)
        path=self.room(approval=True);self.call(self.b,path+'/join');self.call(self.a,path+'/leave');self.assertEqual(self.call(self.b,path+'/join').status_code,404)
    def test_live_requests_and_invites_require_consent_and_four_total(self):
        path=self.live();self.call(self.b,path+'/join');self.call(self.c,path+'/join');self.call(self.admin,path+'/join')
        self.assertEqual(self.call(self.b,path+'/stage',{'action':'accept'}).status_code,409)
        self.assertEqual(self.call(self.b,path+'/stage',{'action':'request'}).status_code,200)
        r=self.call(self.a,path+'/members/'+self.ub['id'],{'decision':'promote'},'PATCH');self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(next(u['seat'] for u in r.json['room']['members'] if u['id']==self.ub['id']),2)
        for c,uid in [(self.c,self.uc['id']),(self.admin,self.admin.get('/api/bootstrap').json['user']['id'])]:
            r=self.call(self.a,path+'/members/'+uid,{'decision':'promote'},'PATCH');u=next(u for u in r.json['room']['members'] if u['id']==uid);self.assertIsNone(u['seat']);self.assertEqual(u['stage_request'],'invited')
            self.assertEqual(self.call(c,path+'/stage',{'action':'accept'}).status_code,200)
        other,uo=self.user('daniel');self.call(other,path+'/join');self.call(other,path+'/stage',{'action':'request'})
        self.assertEqual(self.call(self.a,path+'/members/'+uo['id'],{'decision':'promote'},'PATCH').status_code,409)
        r=self.call(other,path+'/poll',{'mic':True,'camera':True}).json['room'];self.assertEqual(r['seat_limit'],4);u=next(x for x in r['members'] if x['id']==uo['id']);self.assertEqual((u['mic'],u['camera']),(0,0))
        self.call(self.b,path+'/stage',{'action':'leave'});self.assertEqual(self.call(self.a,path+'/members/'+uo['id'],{'decision':'promote'},'PATCH').status_code,200)
    def test_notifications_are_owned_and_transactional(self):
        self.friends();n=self.notices(self.b);self.assertTrue(any(v['title']=='Pedido de amizade' for v in n));self.assertTrue(any(v['title']=='Amizade aceita' for v in self.notices(self.a)))
        foreign=n[0]['id'];self.call(self.c,'/hub/notifications/read',{'ids':[foreign]});self.assertIsNone(next(n for n in self.notices(self.b) if n['id']==foreign)['read_at'])
        self.call(self.b,'/hub/notifications/read',{'through':foreign});self.assertIsNotNone(next(n for n in self.notices(self.b) if n['id']==foreign)['read_at'])
        before=len(self.notices(self.b));self.db.execute('INSERT INTO community_dm(sender,recipient,body,created_at) VALUES(?,?,?,?)',(self.ua['id'],self.ub['id'],'rollback',time.time()));self.db.rollback();self.assertEqual(len(self.notices(self.b)),before)
        self.assertEqual(self.call(self.c,'/hub/dm/'+self.ub['id'],{'body':'No'}).status_code,403)
    def test_private_audio_share_and_message_retry(self):
        self.friends();buf=io.BytesIO()
        with wave.open(buf,'wb') as f:f.setparams((1,2,8000,0,'NONE','not compressed'));f.writeframes(b'\0\0'*800)
        r=self.a.post('/api/hub/audio',headers=self.headers,data={'file':(io.BytesIO(buf.getvalue()),'note.wav')});self.assertEqual(r.status_code,201,r.json);audio=r.json
        self.assertEqual(self.b.get(audio['url']).status_code,404)
        path='/hub/dm/'+self.ub['id'];rid=self.live().rsplit('/',1)[-1]
        d={'audio':audio['id'],'share':{'kind':'room','id':rid},'client_id':'client-test-123'}
        self.assertEqual(self.call(self.a,path,d).status_code,200);self.assertEqual(self.call(self.a,path,d).status_code,200)
        messages=self.a.get('/api'+path).json['messages'];self.assertEqual(len(messages),1);self.assertEqual(messages[0]['share']['title'],'Cinema ao vivo')
        response=self.b.get(audio['url'],headers={'Range':'bytes=0-31'});self.assertEqual(response.status_code,206);response.close()
        self.assertEqual(self.c.get(audio['url']).status_code,404)
        self.assertEqual(self.call(self.b,'/hub/dm/'+self.ua['id'],{'audio':audio['id']}).status_code,404)
        self.assertEqual(self.call(self.a,path,{'share':{'kind':'post','id':'missing'}}).status_code,404)
    def test_streak_requires_both_people_and_consecutive_brazilian_days(self):
        self.friends();a,b=self.ua['id'],self.ub['id'];now=time.time()
        for stamp in [now-86400,now]:
            self.db.execute('INSERT INTO community_dm(sender,recipient,body,created_at) VALUES(?,?,?,?)',(a,b,'hi',stamp))
        self.db.commit();self.assertEqual(social_hub.streak(self.db,a,b,now)['days'],0)
        for stamp in [now-86400,now]:self.db.execute('INSERT INTO community_dm(sender,recipient,body,created_at) VALUES(?,?,?,?)',(b,a,'hello',stamp))
        self.db.commit();self.assertEqual(social_hub.streak(self.db,a,b,now)['days'],2)
        self.assertEqual(social_hub.streak(self.db,a,b,now+3*86400)['days'],0)
    def test_profile_activity_opt_in_and_invisible(self):
        uid=self.ua['id'];self.db.execute('INSERT INTO watch_history VALUES(?,?,?)',(uid,'horizonte',time.time()));self.db.commit()
        self.call(self.a,'/community/presence');self.call(self.a,'/hub/activity',{'source':'catalog','id':'horizonte','playing':True})
        own=self.a.get('/api/community/profiles/alice').json['profile'];self.assertEqual(own['recently_watched'][0]['id'],'horizonte')
        p=self.b.get('/api/community/profiles/alice').json['profile'];self.assertEqual(p['recently_watched'],[]);self.assertIsNone(p['watching_now'])
        self.call(self.a,'/hub/preferences',{'show_activity':True,'status_text':'Maratonando!'},'PATCH')
        p=self.b.get('/api/community/profiles/alice').json['profile'];self.assertEqual(p['status_text'],'Maratonando!');self.assertEqual(p['watching_now']['id'],'horizonte');self.assertNotIn('video_url',p['watching_now'])
        self.call(self.a,'/hub/preferences',{'presence':'invisible'},'PATCH');p=self.b.get('/api/community/profiles/alice').json['profile'];self.assertFalse(p['online']);self.assertIsNone(p['watching_now'])
        self.assertEqual(self.call(self.a,'/hub/activity',{'source':'catalog','id':'missing','playing':True}).status_code,404)
    def test_call_consent_signal_permissions_and_timeout(self):
        self.friends();r=self.call(self.a,'/hub/calls',{'recipient':self.ub['id'],'kind':'video'});self.assertEqual(r.status_code,201,r.json);cid=r.json['call']['id'];path='/hub/calls/'+cid
        self.assertEqual(self.call(self.a,path+'/signals',{'payload':{'type':'offer','sdp':'test'}}).status_code,409)
        self.assertEqual(self.c.get('/api'+path).status_code,404)
        self.assertEqual(self.call(self.a,path,{'action':'accept'},'PATCH').status_code,409)
        self.assertEqual(self.call(self.b,path,{'action':'accept'},'PATCH').status_code,200)
        self.assertEqual(self.call(self.a,path+'/signals',{'payload':{'type':'offer','sdp':'test'}}).status_code,200)
        self.assertEqual(self.b.get('/api'+path).json['signals'][0]['payload']['sdp'],'test')
        self.assertEqual(self.call(self.b,path+'/signals',{'payload':{'type':'offer','sdp':'test'}}).status_code,403)
        self.assertEqual(self.call(self.a,'/hub/calls',{'recipient':self.ub['id']}).status_code,409)
        self.call(self.b,path,{'action':'end'},'PATCH');self.assertEqual(self.a.get('/api'+path).json['call']['status'],'ended')
        cid=self.call(self.a,'/hub/calls',{'recipient':self.ub['id']}).json['call']['id'];self.db.execute('UPDATE hub_calls SET created_at=? WHERE id=?',(time.time()-50,cid));self.db.commit();self.b.get('/api/hub/calls');self.assertEqual(self.a.get('/api/hub/calls/'+cid).json['call']['status'],'missed')
    def subscription(self):
        k=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
        return {'endpoint':'https://fcm.googleapis.com/fcm/send/test-token','keys':{'p256dh':base64.urlsafe_b64encode(k).decode().rstrip('='),'auth':base64.urlsafe_b64encode(b'a'*16).decode().rstrip('=')}}
    def test_webpush_outbox_preferences_retry_cleanup_and_ssrf(self):
        self.friends();sub=self.subscription();self.assertEqual(self.call(self.b,'/hub/push/subscriptions',sub).status_code,200)
        self.assertEqual(self.call(self.b,'/hub/push/subscriptions',{**sub,'endpoint':'https://127.0.0.1/internal'}).status_code,400)
        self.assertEqual(self.call(self.b,'/hub/push/subscriptions',{**sub,'endpoint':'https://fcm.googleapis.com.evil.test/send'}).status_code,400)
        self.call(self.a,'/hub/dm/'+self.ub['id'],{'body':'Test push'});jobs=[]
        with sqlite3.connect(self.db.execute('PRAGMA database_list').fetchone()[2]) as conn:
            conn.row_factory=sqlite3.Row;conn.execute('PRAGMA foreign_keys=ON');flix_push.deliver(conn,self.tmp.name,lambda **kw:jobs.append(kw))
        self.assertEqual(len(jobs),1);self.assertEqual(json.loads(jobs[0]['data'])['title'],'alice');self.assertEqual(json.loads(jobs[0]['data'])['body'],'Test push');self.assertEqual(jobs[0]['timeout'],8)
        self.call(self.b,'/hub/preferences',{'message_preview':False},'PATCH');self.call(self.a,'/hub/dm/'+self.ub['id'],{'body':'Keep private'});flix_push.deliver(self.db,self.tmp.name,lambda **kw:jobs.append(kw));self.assertEqual(len(jobs),2);self.assertNotIn('Keep private',jobs[-1]['data'])
        self.call(self.b,'/hub/preferences',{'messages':False},'PATCH');self.call(self.a,'/hub/dm/'+self.ub['id'],{'body':'Muted push'});flix_push.deliver(self.db,self.tmp.name,lambda **kw:jobs.append(kw));self.assertEqual(len(jobs),2)
        self.assertTrue(self.b.get('/api/hub/push/config').json['public_key'])
    def test_real_webpush_encryption_and_expired_subscription(self):
        import http_ece,requests
        from unittest.mock import Mock
        self.friends();private=ec.generate_private_key(ec.SECP256R1());pub=private.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
        sub=self.subscription();sub['keys']['p256dh']=base64.urlsafe_b64encode(pub).decode().rstrip('=')
        self.call(self.b,'/hub/push/subscriptions',sub);self.call(self.a,'/hub/dm/'+self.ub['id'],{'body':'Confidential message'})
        response=Mock(status_code=201,text='',headers={})
        with patch('requests.post',return_value=response) as send:
            flix_push.deliver(self.db,self.tmp.name)
        self.assertEqual(send.call_count,1)
        sent=send.call_args.kwargs;self.assertIn('vapid',sent['headers']['authorization']);self.assertEqual(sent['headers']['content-encoding'],'aes128gcm')
        plain=http_ece.decrypt(sent['data'],private_key=private,auth_secret=b'a'*16,version='aes128gcm');self.assertEqual(json.loads(plain)['title'],'alice');self.assertEqual(json.loads(plain)['body'],'Confidential message')
        self.call(self.a,'/hub/dm/'+self.ub['id'],{'body':'Second'})
        with patch('requests.post',return_value=Mock(status_code=410,text='Gone',headers={})):
            flix_push.deliver(self.db,self.tmp.name)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM hub_push').fetchone()[0],0)

    def test_pwa_and_brand(self):
        self.assertEqual(self.a.get('/api/bootstrap').json['brand'],'WorkTV');r=self.a.get('/manifest.webmanifest');self.assertEqual(r.status_code,200);self.assertEqual(r.json['display'],'standalone');r.close()
        r=self.a.get('/sw.js');self.assertEqual(r.status_code,200);self.assertEqual(r.headers['Service-Worker-Allowed'],'/');self.assertIn("u.pathname.startsWith('/api/')",r.text);r.close()

if __name__=='__main__':unittest.main()
