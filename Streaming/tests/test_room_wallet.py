import io
import json
import secrets
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import test_community as fixtures
import flix_wallet


class RoomWalletTests(unittest.TestCase):
    setUp=fixtures.CommunityTests.setUp
    tearDown=fixtures.CommunityTests.tearDown
    call=fixtures.CommunityTests.call
    user=fixtures.CommunityTests.user
    room=fixtures.CommunityTests.room
    admit=fixtures.CommunityTests.admit

    def credit(self,uid,amount=100):
        flix_wallet.entry(self.db,uid,amount,'Teste','test:'+secrets.token_hex(8));self.db.commit()

    def test_welcome_only_new_accounts_and_admin_permissions(self):
        self.assertEqual(self.call(self.a,'/admin/economy',{'welcome':50},'PUT').status_code,403)
        for n in [-1,1.5,True,100001]:self.assertEqual(self.call(self.admin,'/admin/economy',{'welcome':n},'PUT').status_code,400)
        self.assertEqual(self.call(self.admin,'/admin/economy',{'welcome':50},'PUT').status_code,200)
        c,u=self.user('welcome')
        for _ in range(2):self.assertEqual(c.get('/api/wallet').json['balance'],50)
        self.assertEqual(self.a.get('/api/wallet').json['balance'],0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM coin_ledger WHERE user_id=?',(u['id'],)).fetchone()[0],1)

    def test_gift_balance_deduplication_and_profile_collection(self):
        self.credit(self.ua['id'],25)
        d={'request_id':secrets.token_hex(16),'recipient':self.ub['id'],'gift_id':'heart','confirm_coins':25}
        for _ in range(2):self.assertIn(self.call(self.a,'/wallet/gifts',d).status_code,(200,201))
        self.assertEqual(self.a.get('/api/wallet').json['balance'],0)
        p=self.a.get('/api/community/profiles/bruno').json['profile'];self.assertEqual(p['gifts'][0]['count'],1)
        self.assertEqual(self.call(self.a,'/wallet/gifts',{**d,'request_id':secrets.token_hex(16)}).status_code,402)
        self.assertEqual(self.call(self.a,'/wallet/gifts',{**d,'recipient':self.uc['id']}).status_code,409)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM hub_notifications WHERE category='social' AND dedupe LIKE 'gift:%'").fetchone()[0],1)

    def test_checkout_credit_verified_once_refund_debt_and_plan_unchanged(self):
        self.call(self.admin,'/admin/settings',{'brand':'Flix','public_url':'https://stream.example','mode':'test','access_token':'TEST-token','webhook_secret':'webhook-secret'},'PUT')
        self.call(self.admin,'/admin/economy/packages/initial',{'name':'100 moedas','coins':100,'price':500,'active':True},'PUT')
        self.assertEqual(self.call(self.a,'/checkout',{'package_id':'initial','confirm_price':1,'confirm_coins':100}).status_code,409)
        with patch('app.urlrequest.urlopen',return_value=io.BytesIO(json.dumps({'id':'pref-coins','sandbox_init_point':'https://sandbox.mercadopago.com/checkout'}).encode())) as mock:
            r=self.call(self.a,'/checkout',{'package_id':'initial','confirm_price':500,'confirm_coins':100});self.assertEqual(r.status_code,200,r.json)
            payload=json.loads(mock.call_args.args[0].data);self.assertEqual(payload['items'][0]['unit_price'],5)
            self.assertIn('/carteira?',payload['back_urls']['success'])
        oid=r.json['order_id'];payment={'external_reference':oid,'transaction_amount':5,'currency_id':'BRL','status':'approved','live_mode':False}
        def sync(p,c=None):
            with patch('app.urlrequest.urlopen',return_value=io.BytesIO(json.dumps(p).encode())):return self.call(c or self.a,'/payments/sync',{'payment_id':'234'})
        self.assertEqual(sync(payment,self.b).status_code,404)
        self.assertEqual(sync({**payment,'transaction_amount':1}).status_code,400)
        self.assertEqual(sync({**payment,'live_mode':True}).status_code,400)
        before=dict(self.db.execute('SELECT plan_id,expires_at FROM users WHERE id=?',(self.ua['id'],)).fetchone())
        self.assertEqual(sync(payment).status_code,200);self.assertEqual(sync(payment).status_code,200)
        self.assertEqual(self.a.get('/api/wallet').json['balance'],100)
        self.credit(self.ua['id'],-25)
        for _ in range(2):self.assertEqual(sync({**payment,'status':'refunded'}).status_code,200)
        self.assertEqual(self.a.get('/api/wallet').json['balance'],-25)
        sync(payment);self.assertEqual(self.a.get('/api/wallet').json['balance'],-25)
        self.assertEqual(before,dict(self.db.execute('SELECT plan_id,expires_at FROM users WHERE id=?',(self.ua['id'],)).fetchone()))

    def test_private_directory_password_and_live_mode_transition(self):
        p=self.room(privacy='private',approval=False)
        self.assertNotIn(p.split('/')[-1],[r['id'] for r in self.b.get('/api/community/rooms').json['rooms']])
        self.admit(p)
        result=self.call(self.a,p,{'title':'Privada','description':'Com senha','privacy':'password','password':'9876','approval':False,'activity':'live'},'PATCH')
        self.assertEqual(result.status_code,200,result.json);r=result.json['room'];self.assertEqual(r['kind'],'live');self.assertEqual(r['url'],'');self.assertNotIn('password_hash',r)
        self.assertEqual(self.call(self.c,p+'/join',{'password':'wrong'}).status_code,403)
        self.assertEqual(self.call(self.c,p+'/join',{'password':'9876'}).status_code,200)
        self.assertNotIn('password_hash',self.c.get('/api'+p).json['room'])
        self.assertEqual(self.call(self.b,p,{'title':'Hacked','activity':'games'},'PATCH').status_code,403)

    def test_password_attempt_limit_and_existing_member(self):
        p=self.room(privacy='password',password='1234',approval=False)
        for _ in range(10):self.assertEqual(self.call(self.b,p+'/join',{'password':'nope'}).status_code,403)
        self.assertEqual(self.call(self.b,p+'/join',{'password':'1234'}).status_code,429)
        self.assertEqual(self.call(self.a,p+'/join').status_code,200)

    def test_independent_music_queue_poll_and_reactions(self):
        p=self.room(approval=False);self.call(self.b,p+'/join')
        self.assertEqual(self.call(self.b,p+'/experience/queue',{'lane':'music','title':'Música da turma','url':'https://youtu.be/abcdefghijk'}).status_code,201)
        exp=self.a.get('/api'+p+'/experience').json;q=exp['audio']['queue'][0]
        self.assertEqual(self.call(self.b,p+'/soundtrack',{'action':'play','id':q['id']},'PATCH').status_code,403)
        self.assertEqual(self.call(self.a,p+'/soundtrack',{'action':'play','id':q['id']},'PATCH').status_code,200)
        self.assertEqual(self.call(self.a,p+'/poll').json['room']['url'],'https://example.com/movie.mp4')
        self.call(self.a,p+'/polls',{'question':'Qual filme hoje?','options':['Ação','Comédia']})
        poll=self.b.get('/api'+p+'/experience').json['polls'][0]
        for choice in [0,1,1]:self.assertEqual(self.call(self.b,p+'/polls/'+poll['id'],{'choice':choice},'PATCH').status_code,200)
        self.assertEqual(self.a.get('/api'+p+'/experience').json['polls'][0]['counts'],[0,1])
        self.call(self.a,p+'/polls/'+poll['id'],{'close':True},'PATCH');self.assertEqual(self.call(self.b,p+'/polls/'+poll['id'],{'choice':0},'PATCH').status_code,409)
        self.assertEqual(self.c.get('/api'+p+'/experience').status_code,403)

    def test_paid_builtin_join_once_and_cancel_refund(self):
        self.credit(self.ua['id']);self.credit(self.ub['id'])
        r=self.call(self.admin,'/admin/economy/plugins/colors',{'name':'Cores','coins':20,'active':True,'kind':'game'},'PUT');self.assertEqual(r.status_code,200,r.json)
        p=self.room(approval=False);self.call(self.b,p+'/join')
        g=self.call(self.a,p+'/game',{'action':'create','kind':'colors'}).json['game'];self.assertEqual(g['entry_coins'],20);self.assertEqual(g['players'],[])
        def join(c,cost=None):return self.call(c,p+'/game',{'action':'join','game_id':g['id'],'confirm_coins':cost})
        self.assertEqual(join(self.b).status_code,409)
        for c in (self.a,self.b,self.b):self.assertEqual(join(c,20).status_code,200)
        self.assertEqual(self.b.get('/api/wallet').json['balance'],80)
        latest=self.a.get('/api'+p+'/game').json['game'];r=self.call(self.a,p+'/game',{'action':'cancel','game_id':g['id'],'revision':latest['revision']});self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(self.b.get('/api/wallet').json['balance'],100)

    def test_plugin_admission_state_and_events_authority(self):
        self.credit(self.ub['id'])
        p=self.room(approval=False);self.call(self.b,p+'/join')
        config={'name':'Novo jogo','coins':15,'active':True,'kind':'game','url':'https://games.example.com/play'}
        self.assertEqual(self.call(self.a,'/admin/economy/plugins/novo',config,'PUT').status_code,403)
        self.assertEqual(self.call(self.admin,'/admin/economy/plugins/novo',config,'PUT').status_code,200)
        self.call(self.a,p+'/plugin',{'plugin_id':'novo'});ps=self.b.get('/api'+p+'/experience').json['plugin'];self.assertNotIn('url',ps)
        self.assertEqual(self.call(self.b,p+'/plugin/events',{'session_id':ps['id'],'payload':{'move':1}}).status_code,403)
        self.call(self.b,p+'/plugin/join',{'session_id':ps['id'],'confirm_coins':15})
        self.assertEqual(self.b.get('/api/wallet').json['balance'],85)
        self.assertEqual(self.call(self.b,p+'/plugin/events',{'session_id':ps['id'],'payload':{'move':1}}).status_code,200)
        self.assertEqual(self.call(self.b,p+'/plugin',{'session_id':ps['id'],'revision':1,'state':{'score':99}},'PATCH').status_code,403)
        self.assertEqual(self.call(self.a,p+'/plugin',{'session_id':ps['id'],'revision':1,'state':{'round':2}},'PATCH').status_code,200)
        exp=self.b.get('/api'+p+'/experience').json['plugin'];self.assertEqual(exp['state'],{'round':2});self.assertEqual(exp['events'][0]['payload'],{'move':1})
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM community_game_results').fetchone()[0],0)

    def test_profile_music_and_hearts(self):
        now=time.time();self.db.execute("INSERT INTO music_tracks(id,provider,title,artist,url,created_at,updated_at) VALUES('song','link','Nossa música','Artista','https://example.com/song.mp3',?,?)",(now,now))
        self.db.execute("INSERT INTO music_play_events(id,user_id,track_id,created_at,last_at,listened) VALUES('session',?,'song',?,?,5)",(self.ua['id'],now,now));self.db.commit()
        p=self.b.get('/api/community/profiles/alice').json['profile'];self.assertEqual(p['recent_music']['id'],'song')
        for _ in range(2):self.assertEqual(self.call(self.b,'/community/profiles/alice/music-heart',{'track_id':'song'},'PUT').status_code,200)
        p=self.b.get('/api/community/profiles/alice').json['profile'];self.assertEqual(p['recent_music']['hearts'],1);self.assertTrue(p['recent_music']['liked'])

    def test_concurrent_gifts_cannot_overspend(self):
        self.credit(self.ua['id'],25)
        token=self.a.get_cookie('vyra_session').value
        def spend(_):
            c=self.app.test_client();c.set_cookie('vyra_session',token)
            return self.call(c,'/wallet/gifts',{'recipient':self.ub['id'],'gift_id':'heart','confirm_coins':25,'request_id':secrets.token_hex(16)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(spend,range(2)))
        self.assertEqual(sorted(codes),[201,402]);self.assertEqual(self.a.get('/api/wallet').json['balance'],0)

    def test_official_provider_validation_and_room_close_refund(self):
        p=self.room(approval=False)
        for url in ['https://evil.example/playlist/abcdefghijklmnopqrstuv','https://open.spotify.com:bad/playlist/abcdefghijklmnopqrstuv','javascript:alert(1)']:
            self.assertEqual(self.call(self.a,p+'/provider',{'provider':'spotify','url':url}).status_code,400)
        r=self.call(self.a,p+'/provider',{'provider':'spotify','url':'https://open.spotify.com/playlist/abcdefghijklmnopqrstuv'});self.assertEqual(r.status_code,200,r.json)
        widget=self.a.get('/api'+p+'/experience').json['plugin'];self.assertIn('https://open.spotify.com/embed/playlist/',widget['url'])
        self.assertNotIn(widget['plugin_id'],[r['id'] for r in self.a.get('/api/community/room-plugins').json['plugins']])
        self.call(self.a,p+'/plugin',m='DELETE')
        self.credit(self.ua['id'],30);self.call(self.admin,'/admin/economy/plugins/colors',{'name':'Cores','coins':20,'active':True,'kind':'game'},'PUT')
        g=self.call(self.a,p+'/game',{'action':'create','kind':'colors'}).json['game']
        self.call(self.a,p+'/game',{'action':'join','game_id':g['id'],'confirm_coins':20})
        self.assertEqual(self.a.get('/api/wallet').json['balance'],10)
        self.call(self.a,p,m='DELETE');self.assertEqual(self.a.get('/api/wallet').json['balance'],30)
