import hashlib, hmac, io, json, sqlite3, sys, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.packages'),str(ROOT)]
from app import create_app
from media import parse_playlist,fetch_playlist
from werkzeug.security import generate_password_hash

class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=create_app(self.tmp.name,testing=True)
        self.client=self.app.test_client()
        self.headers={'X-Requested-With':'VYRA'}
        self.conn=sqlite3.connect(Path(self.tmp.name)/'vyra.sqlite3')
        self.conn.row_factory=sqlite3.Row
        self.conn.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Admin-password-123'),))
        self.conn.commit()
    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()
    def post(self,path,data,method='POST'):
        return self.client.open('/api'+path,method=method,json=data,headers=self.headers)
    def admin(self):
        r=self.post('/auth/login',{'email':'admin@vyra.local','password':'Admin-password-123'})
        self.assertEqual(r.status_code,200,r.json)
        return r.json['user']
    def register(self):
        r=self.post('/auth/register',{'name':'Cliente Teste','email':'user@example.com','password':'Customer-password-123','plan_id':'premium'})
        self.assertEqual(r.status_code,200,r.json)
        return r.json['user']
    def test_catalog_hides_streams(self):
        for item in self.client.get('/api/catalog').json['items']:
            self.assertNotIn('video_url',item)
            for ep in item['episodes']:self.assertNotIn('video_url',ep)
    def test_authorization(self):
        self.assertEqual(self.client.get('/api/admin/users').status_code,401)
        self.register()
        self.assertEqual(self.client.get('/api/admin/users').status_code,403)
        self.assertEqual(self.client.get('/api/play/horizonte').status_code,402)
        self.assertEqual(self.post('/checkout',{'plan_id':'premium','price':1}).status_code,503)
        self.assertFalse(self.client.get('/api/bootstrap').json['user']['subscribed'])
    def test_csrf_and_logout(self):
        self.admin()
        self.assertEqual(self.client.post('/api/auth/logout',json={}).status_code,403)
        self.assertEqual(self.client.post('/api/auth/logout',json={},headers={**self.headers,'Origin':'https://evil.example'}).status_code,403)
        self.assertTrue(self.client.get_cookie('vyra_session').http_only)
        self.post('/auth/logout',{})
        self.assertEqual(self.client.get('/api/admin/users').status_code,401)
    def test_exact_progress_episode_isolation_and_stale_writes(self):
        self.admin()
        episodes=next(i for i in self.client.get('/api/catalog').json['items'] if i['id']=='neon')['episodes']
        now=time.time()*1000
        for ep,pos in [(episodes[0],45.625),(episodes[1],91.125)]:
            self.assertEqual(self.post('/progress/neon',{'episode_id':ep['id'],'position':pos,'duration':600.8,'client_time':now},'PUT').status_code,200)
        self.post('/progress/neon',{'episode_id':episodes[0]['id'],'position':1,'duration':600.8,'client_time':now-100},'PUT')
        self.assertEqual(self.client.get('/api/play/neon?episode='+episodes[0]['id']).json['position'],45.625)
        self.assertEqual(self.client.get('/api/play/neon?episode='+episodes[1]['id']).json['position'],91.125)
        self.post('/auth/logout',{})
        u=self.register()
        self.conn.execute('UPDATE users SET expires_at=? WHERE id=?',(time.time()+3600,u['id']))
        self.conn.commit()
        self.assertEqual(self.client.get('/api/play/neon?episode='+episodes[0]['id']).json['position'],0)
    def test_invalid_progress(self):
        self.admin()
        for pos,duration in [(-1,30),(100,20),(1,0),(float('nan'),30)]:
            self.assertEqual(self.post('/progress/horizonte',{'position':pos,'duration':duration,'client_time':time.time()*1000},'PUT').status_code,400)
    def test_playlist_import_duplicates_and_hls(self):
        text='#EXTM3U\n#EXTINF:-1 tvg-logo="https://example.com/logo.png" group-title="Notícias",Canal A\nhttps://example.com/live.m3u8\n#EXTINF:-1,Canal B\nhttps://example.com/b.m3u8\n'
        parsed,_=parse_playlist(text)
        self.assertEqual(parsed[0]['genre'],'Notícias')
        with self.assertRaises(ValueError):parse_playlist('#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXTINF:10,\n1.ts')
        self.admin()
        self.assertEqual(self.post('/admin/import',{'text':text}).json['imported'],2)
        self.assertEqual(self.post('/admin/import',{'text':text}).json['skipped'],2)
    def test_playlist_ssrf(self):
        with self.assertRaises(ValueError):fetch_playlist('http://127.0.0.1/secret')
        with self.assertRaises(ValueError):fetch_playlist('file:///etc/passwd')
    def test_series_edits_keep_progress(self):
        self.admin()
        d={'title':'Nova série','kind':'series','published':True,'episodes':[{'season':1,'number':1,'title':'Piloto','video_url':'https://example.com/video.mp4'}]}
        cid=self.post('/admin/content',d).json['id']
        item=next(i for i in self.client.get('/api/admin/content').json['items'] if i['id']==cid)
        eid=item['episodes'][0]['id']
        self.post('/progress/'+cid,{'episode_id':eid,'position':8.5,'duration':80,'client_time':time.time()*1000},'PUT')
        item['episodes'][0]['title']='Piloto atualizado'
        r=self.post('/admin/content/'+cid,item,'PUT')
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(self.client.get('/api/play/'+cid+'?episode='+eid).json['position'],8.5)
        self.post('/admin/content/'+cid,{},'DELETE')
        self.assertEqual(self.client.get('/api/play/'+cid+'?episode='+eid).status_code,404)
    def configure_payment(self):
        self.admin()
        self.post('/admin/settings',{'brand':'VYRA','public_url':'https://stream.example','mode':'test','access_token':'TEST-secret-token','webhook_secret':'webhook-secret'},'PUT')
    def test_secrets_are_encrypted_and_not_returned(self):
        self.configure_payment()
        r=self.client.get('/api/admin/settings').json
        self.assertNotIn('access_token',r)
        self.assertTrue(r['access_token_configured'])
        self.assertNotIn('TEST-secret-token',self.conn.execute("SELECT value FROM settings WHERE key='access_token'").fetchone()[0])
    def test_checkout_uses_database_price(self):
        self.configure_payment()
        self.post('/auth/logout',{})
        self.register()
        pref={'id':'pref-123','sandbox_init_point':'https://sandbox.mercadopago.com/checkout'}
        with patch('app.urlrequest.urlopen',return_value=io.BytesIO(json.dumps(pref).encode())) as mock:
            r=self.post('/checkout',{'plan_id':'premium','amount':1})
            self.assertEqual(r.status_code,200,r.json)
            self.assertEqual(json.loads(mock.call_args.args[0].data)['items'][0]['unit_price'],29.9)
    def test_webhook_signature_price_idempotency_and_refund(self):
        self.configure_payment()
        self.post('/auth/logout',{})
        u=self.register()
        self.conn.execute('INSERT INTO orders(id,user_id,plan_id,amount,days,created_at) VALUES(?,?,?,?,?,?)',('order123',u['id'],'premium',2990,30,time.time()))
        self.conn.commit()
        payment={'external_reference':'order123','transaction_amount':29.9,'currency_id':'BRL','status':'approved','live_mode':False}
        self.assertEqual(self.client.post('/api/payments/webhook?data.id=123',json={'type':'payment'}).status_code,401)
        ts=str(int(time.time()*1000))
        sig=hmac.new(b'webhook-secret',f'id:123;request-id:request123;ts:{ts};'.encode(),hashlib.sha256).hexdigest()
        headers={'x-request-id':'request123','x-signature':f'ts={ts},v1={sig}'}
        def send(p):
            with patch('app.urlrequest.urlopen',return_value=io.BytesIO(json.dumps(p).encode())):
                return self.client.post('/api/payments/webhook?data.id=123',json={'type':'payment'},headers=headers)
        self.assertEqual(send({**payment,'transaction_amount':0.01}).status_code,400)
        self.assertFalse(self.client.get('/api/bootstrap').json['user']['subscribed'])
        r=send(payment)
        self.assertEqual(r.status_code,200,r.json)
        expiry=self.client.get('/api/bootstrap').json['user']['expires_at']
        self.assertTrue(self.client.get('/api/bootstrap').json['user']['subscribed'])
        self.assertEqual(send(payment).status_code,200)
        self.assertEqual(self.client.get('/api/bootstrap').json['user']['expires_at'],expiry)
        self.assertEqual(send({**payment,'status':'refunded'}).status_code,200)
        self.assertFalse(self.client.get('/api/bootstrap').json['user']['subscribed'])
    def test_admin_self_protection_and_favorites(self):
        u=self.admin()
        self.assertEqual(self.post('/admin/users/'+u['id'],{'status':'blocked'},'PATCH').status_code,400)
        self.assertTrue(self.post('/favorites/horizonte',{}).json['saved'])
        self.assertIn('horizonte',self.client.get('/api/library').json['favorites'])
        self.assertFalse(self.post('/favorites/horizonte',{}).json['saved'])
    def test_plan_price_edit_and_deactivation(self):
        self.admin()
        plans=self.client.get('/api/admin/plans').json['plans']
        premium=next(p for p in plans if p['id']=='premium')
        premium.update(price=3490,active=False)
        self.assertEqual(self.post('/admin/plans/premium',premium,'PUT').status_code,200)
        self.assertNotIn('premium',[p['id'] for p in self.client.get('/api/bootstrap').json['plans']])
        self.post('/auth/logout',{})
        self.assertEqual(self.post('/auth/register',{'name':'Cliente','email':'new@example.com','password':'valid-password-123','plan_id':'premium'}).status_code,400)

if __name__=='__main__':unittest.main(verbosity=2)
