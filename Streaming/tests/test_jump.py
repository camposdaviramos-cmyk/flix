import math
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from werkzeug.security import generate_password_hash


class JumpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=create_app(self.tmp.name,testing=True)
        self.db=sqlite3.connect(Path(self.tmp.name)/'vyra.sqlite3')
        self.db.row_factory=sqlite3.Row
        self.db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Admin-test-123'),))
        self.db.commit()
        self.admin=self.app.test_client()
        self.headers={'X-Requested-With':'VYRA'}
        self.call(self.admin,'/auth/login',{'email':'admin@vyra.local','password':'Admin-test-123'})
        self.a,self.ua=self.user('alice')
        self.b,self.ub=self.user('bruno')
        self.c,self.uc=self.user('carol')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def call(self,c,path,body=None,method='POST'):
        return c.open('/api'+path,method=method,json=body or {},headers=self.headers)

    def user(self,name):
        r=self.call(self.admin,'/admin/users',{'name':name.title(),'username':name,'email':name+'@example.com','password':'Customer-test-123','plan_id':'premium'})
        self.assertEqual(r.status_code,201,r.json)
        c=self.app.test_client()
        u=self.call(c,'/auth/login',{'email':name+'@example.com','password':'Customer-test-123'}).json['user']
        return c,u

    def room(self,c=None,cid='horizonte',eid=''):
        r=self.call(c or self.a,'/jump/rooms',{'content_id':cid,'episode_id':eid,'position':12.5,'paused':True})
        self.assertEqual(r.status_code,201,r.json)
        return r.json['room']

    def admit(self,client,path,host=None):
        uid=client.get('/api/bootstrap').json['user']['id']
        r=self.call(client,path+'/join')
        self.assertEqual(r.status_code,202,r.json)
        r=self.call(host or self.a,path+'/requests/'+uid,{'decision':'approve'},'PATCH')
        self.assertEqual(r.status_code,200,r.json)
        r=self.call(client,path+'/join')
        self.assertEqual(r.status_code,200,r.json)
        return r

    def test_admin_create_and_unique_username(self):
        self.assertTrue(self.ua['subscribed'])
        self.assertAlmostEqual(self.ua['expires_at']-time.time(),30*86400,delta=10)
        self.assertEqual(self.admin.get('/api/bootstrap').json['user']['role'],'admin')
        self.assertEqual(self.call(self.a,'/admin/users',{}).status_code,403)
        d={'name':'Novo Cliente','username':'ALICE','email':'new@example.com','password':'Password-test-123','plan_id':'premium'}
        self.assertEqual(self.call(self.admin,'/admin/users',d).status_code,409)
        d['username']='novo';d['plan_id']='missing'
        self.assertEqual(self.call(self.admin,'/admin/users',d).status_code,400)
        d['plan_id']='';d['expires_at']=time.time()+100
        self.assertEqual(self.call(self.admin,'/admin/users',d).status_code,400)
        d['expires_at']=0
        r=self.call(self.admin,'/admin/users',d)
        self.assertEqual(r.status_code,201,r.json)
        self.assertFalse(r.json['user']['subscribed'])

    def test_friend_acceptance_privacy_and_invite(self):
        self.assertEqual(self.call(self.a,'/social/friends',{'username':'@BRUNO'}).status_code,201)
        self.assertEqual(self.call(self.a,'/social/friends/'+self.ub['id'],{},'PATCH').status_code,404)
        pending=self.b.get('/api/social').json['friends'][0]
        self.assertNotIn('email',pending)
        self.assertEqual(pending['status'],'pending')
        self.assertEqual(self.call(self.b,'/social/friends/'+self.ua['id'],{},'PATCH').status_code,200)
        room=self.room()
        rid=room['id']
        self.assertEqual(self.call(self.a,f'/jump/rooms/{rid}/invite',{'user_id':self.uc['id']}).status_code,403)
        self.assertEqual(self.call(self.a,f'/jump/rooms/{rid}/invite',{'user_id':self.ub['id']}).status_code,200)
        self.assertEqual(self.b.get('/api/social').json['invites'][0]['id'],rid)
        self.assertEqual(self.c.get('/api/social').json['invites'],[])
        self.assertEqual(self.call(self.b,'/social/friends/'+self.ua['id'],{},'DELETE').status_code,200)
        self.assertEqual(self.a.get('/api/social').json['friends'],[])

    def test_room_authorization_revision_and_sync(self):
        r=self.room();path='/jump/rooms/'+r['id']
        self.assertEqual(self.call(self.b,path+'/poll').status_code,403)
        self.assertEqual(self.call(self.b,path+'/messages',{'body':'test'}).status_code,403)
        self.admit(self.b,path)
        body={'position':80.25,'paused':False,'revision':r['revision']}
        self.assertEqual(self.call(self.b,path+'/playback',body,'PATCH').status_code,403)
        self.assertEqual(self.call(self.a,path+'/playback',body,'PATCH').status_code,200)
        self.assertEqual(self.call(self.a,path+'/playback',body,'PATCH').status_code,409)
        snap=self.call(self.b,path+'/poll').json['room']
        self.assertEqual(snap['position'],80.25)
        self.assertFalse(snap['paused'])
        self.assertNotIn('email',snap['members'][0])
        self.assertEqual(self.call(self.a,path+'/playback',{'position':float('nan'),'paused':False,'revision':snap['revision']},'PATCH').status_code,400)
        self.assertEqual(self.call(self.b,path,{},'DELETE').status_code,403)
        self.assertEqual(self.call(self.a,path,{},'DELETE').status_code,200)
        self.assertEqual(self.call(self.b,path+'/poll').status_code,404)

    def test_chat_limits_and_signaling_isolation(self):
        r=self.room();path='/jump/rooms/'+r['id']
        self.admit(self.b,path);self.admit(self.c,path)
        self.assertEqual(self.call(self.a,path+'/messages',{'body':'  '}).status_code,400)
        self.assertEqual(self.call(self.a,path+'/messages',{'body':'x'*1001}).status_code,400)
        for _ in range(12):self.assertEqual(self.call(self.a,path+'/messages',{'body':'<script>alert(1)</script>'}).status_code,201)
        self.assertEqual(self.call(self.a,path+'/messages',{'body':'flood'}).status_code,429)
        messages=self.call(self.b,path+'/poll').json['room']['messages']
        self.assertEqual(len(messages),12)
        signal={'recipient':self.ub['id'],'payload':{'type':'offer','sdp':'test'}}
        self.assertEqual(self.call(self.a,path+'/signals',signal).status_code,200)
        self.assertEqual(self.call(self.c,path+'/poll').json['signals'],[])
        events=self.call(self.b,path+'/poll').json['signals']
        self.assertEqual(len(events),1)
        self.assertEqual(self.call(self.b,path+'/poll',{'cursor':events[-1]['id']}).json['signals'],[])
        self.call(self.c,path+'/leave')
        signal['recipient']=self.uc['id']
        self.assertEqual(self.call(self.a,path+'/signals',signal).status_code,404)

    def test_host_transfer_expiry_and_cleanup(self):
        r=self.room();path='/jump/rooms/'+r['id']
        self.admit(self.b,path)
        self.call(self.a,path+'/leave')
        self.assertEqual(self.call(self.b,path+'/poll').json['room']['host_id'],self.ub['id'])
        self.db.execute('UPDATE jump_members SET seen_at=?',(time.time()-46,));self.db.commit()
        self.assertEqual(self.call(self.b,path+'/poll').status_code,404)
        # An expired subscription must not retain access to a room or chat.
        self.db.execute('UPDATE users SET expires_at=0 WHERE id=?',(self.ua['id'],));self.db.commit()
        self.assertEqual(self.call(self.a,'/jump/rooms',{'content_id':'horizonte'}).status_code,402)

    def test_permanent_room_survives_departure_and_host_can_return(self):
        r=self.room();path='/jump/rooms/'+r['id'];self.admit(self.b,path)
        self.assertEqual(self.call(self.b,path+'/settings',{'permanent':True},'PATCH').status_code,403)
        self.assertEqual(self.call(self.a,path+'/settings',{'permanent':True},'PATCH').status_code,200)
        self.call(self.a,path+'/leave')
        r=self.call(self.b,path+'/poll').json['room'];self.assertEqual(r['host_id'],self.ua['id']);self.assertTrue(r['permanent'])
        self.call(self.b,path+'/leave');self.assertIsNotNone(self.db.execute('SELECT id FROM jump_rooms WHERE id=?',(r['id'],)).fetchone())
        self.assertEqual(self.call(self.a,path+'/join').status_code,200)
        self.assertEqual(self.call(self.a,path+'/settings',{'permanent':False},'PATCH').status_code,200)
        self.call(self.a,path+'/leave');self.assertIsNone(self.db.execute('SELECT id FROM jump_rooms WHERE id=?',(r['id'],)).fetchone())

    def test_room_limit_and_content_access(self):
        r=self.room();path='/jump/rooms/'+r['id']
        for n in range(7):
            c,u=self.user('member'+str(n));self.admit(c,path)
        self.assertEqual(self.call(self.b,path+'/join').status_code,409)
        self.assertEqual(self.call(self.a,path+'/join').status_code,200)
        self.assertEqual(self.call(self.a,'/jump/rooms',{'content_id':'neon'}).status_code,404)
        eid=self.db.execute("SELECT id FROM episodes WHERE content_id='neon' LIMIT 1").fetchone()[0]
        self.room(cid='neon',eid=eid)
        self.db.execute("UPDATE content SET published=0 WHERE id='horizonte'");self.db.commit()
        self.assertEqual(self.call(self.a,path+'/poll').status_code,404)

    def test_live_wall_clock_and_microphone_policy(self):
        self.db.execute("INSERT INTO content(id,title,kind,video_url,published,created_at) VALUES('test-live','Live','channel','https://example.com/live.m3u8',1,?)",(time.time(),));self.db.commit()
        r=self.room(cid='test-live');path='/jump/rooms/'+r['id']
        self.assertEqual(self.call(self.a,path+'/playback',{'position':time.time()-10,'paused':False,'revision':r['revision']},'PATCH').status_code,200)
        self.assertEqual(self.call(self.a,path+'/mic',{'enabled':True},'PATCH').status_code,200)
        self.assertEqual(self.call(self.a,path+'/poll').json['room']['members'][0]['mic'],1)
        self.assertIn('microphone=(self)',self.a.get('/').headers['Permissions-Policy'])

    def test_pending_cannot_read_room_and_only_host_can_review(self):
        path='/jump/rooms/'+self.room()['id']
        for _ in range(2):
            r=self.call(self.b,path+'/join')
            self.assertEqual(r.status_code,202)
            self.assertEqual(r.json,{'status':'pending'})
        self.assertEqual(self.call(self.b,path+'/poll').status_code,403)
        self.assertEqual(self.call(self.b,path+'/messages',{'body':'intrusão'}).status_code,403)
        self.assertEqual(self.call(self.b,path+'/signals',{'recipient':self.ua['id'],'payload':{'type':'offer','sdp':'test'}}).status_code,403)
        reqs=self.call(self.a,path+'/poll').json['room']['requests']
        self.assertEqual(len(reqs),1)
        self.assertNotIn('email',reqs[0])
        self.assertEqual(reqs[0]['username'],'bruno')
        review=path+'/requests/'+self.ub['id']
        self.assertEqual(self.call(self.c,review,{'decision':'approve'},'PATCH').status_code,403)
        self.admit(self.c,path)
        self.assertEqual(self.call(self.c,path+'/poll').json['room']['requests'],[])
        self.assertEqual(self.call(self.c,review,{'decision':'approve'},'PATCH').status_code,403)
        self.assertEqual(self.call(self.a,review,{'decision':'approve'},'PATCH').status_code,200)
        self.assertEqual(self.call(self.b,path+'/join').status_code,200)
        self.assertEqual(self.call(self.a,review,{'decision':'approve'},'PATCH').status_code,409)

    def test_rejection_cannot_be_bypassed_and_cancellation(self):
        path='/jump/rooms/'+self.room()['id']
        self.call(self.b,path+'/join')
        self.assertEqual(self.call(self.a,path+'/requests/'+self.ub['id'],{'decision':'reject'},'PATCH').status_code,200)
        for body in [{},{'approved':True},{'source':'invite'}]:
            self.assertEqual(self.call(self.b,path+'/join',body).json,{'status':'rejected'})
        self.call(self.b,path+'/join',{},'DELETE')
        self.assertEqual(self.call(self.b,path+'/join').json,{'status':'rejected'})
        self.call(self.c,path+'/join')
        self.call(self.c,path+'/join',{},'DELETE')
        self.assertEqual(self.call(self.a,path+'/poll').json['room']['requests'],[])
        self.assertEqual(self.call(self.a,path+'/requests/'+self.uc['id'],{'decision':'approve'},'PATCH').status_code,409)
        self.assertEqual(self.call(self.c,path+'/join').status_code,202)

    def test_reserved_capacity_and_expired_requests(self):
        path='/jump/rooms/'+self.room()['id']
        clients=[]
        for n in range(8):
            c,u=self.user('waiting'+str(n));clients.append((c,u))
            self.assertEqual(self.call(c,path+'/join').status_code,202)
        for c,u in clients[:7]:
            self.assertEqual(self.call(self.a,path+'/requests/'+u['id'],{'decision':'approve'},'PATCH').status_code,200)
        last_c,last_u=clients[-1]
        self.assertEqual(self.call(self.a,path+'/requests/'+last_u['id'],{'decision':'approve'},'PATCH').status_code,409)
        self.call(clients[0][0],path+'/join',{},'DELETE')
        self.assertEqual(self.call(self.a,path+'/requests/'+last_u['id'],{'decision':'approve'},'PATCH').status_code,200)
        self.assertEqual(self.call(last_c,path+'/join').status_code,200)
        self.db.execute("UPDATE jump_requests SET seen_at=? WHERE status='approved'",(time.time()-121,));self.db.commit()
        self.assertEqual(self.call(clients[1][0],path+'/join').status_code,202)
        self.db.execute('UPDATE users SET expires_at=0 WHERE id=?',(clients[1][1]['id'],));self.db.commit()
        self.assertEqual(self.call(self.a,path+'/poll').json['room']['requests'],[])

    def test_request_follows_host_and_closes_with_room(self):
        path='/jump/rooms/'+self.room()['id']
        self.admit(self.b,path)
        self.call(self.c,path+'/join')
        self.call(self.a,path+'/leave')
        self.assertEqual(self.call(self.b,path+'/poll').json['room']['requests'][0]['id'],self.uc['id'])
        self.assertEqual(self.call(self.a,path+'/requests/'+self.uc['id'],{'decision':'approve'},'PATCH').status_code,403)
        self.assertEqual(self.call(self.b,path+'/requests/'+self.uc['id'],{'decision':'approve'},'PATCH').status_code,200)
        self.call(self.b,path,{},'DELETE')
        self.assertEqual(self.call(self.c,path+'/join').status_code,404)
        self.assertEqual(self.db.execute('SELECT count(*) FROM jump_requests').fetchone()[0],0)

    def test_room_links_render_privately(self):
        rid=self.room()['id']
        page=self.app.test_client().get('/sala/'+rid)
        self.assertEqual(page.status_code,200)
        self.assertEqual(page.headers['X-Robots-Tag'],'noindex, nofollow')
        self.assertIn('Convite FlixJump',page.text)
        self.assertNotIn('/sala/'+rid,self.a.get('/sitemap.xml').text)
        self.assertEqual(self.a.get('/sala/notvalid').status_code,404)

    def test_migration_keeps_existing_accounts(self):
        create_app(self.tmp.name,testing=True)
        row=self.db.execute('SELECT username,email FROM users WHERE id=?',(self.ua['id'],)).fetchone()
        self.assertEqual(row['username'],'alice')
        self.assertEqual(row['email'],'alice@example.com')
        self.assertEqual(self.call(self.b,'/social/profile',{'username':'Alice'},'PATCH').status_code,409)
        self.assertEqual(self.call(self.b,'/social/profile',{'username':'bruno_novo'},'PATCH').status_code,200)
        self.assertEqual(self.b.get('/api/bootstrap').json['user']['username'],'bruno_novo')

if __name__=='__main__':unittest.main(verbosity=2)
