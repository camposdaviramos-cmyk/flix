import concurrent.futures
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from werkzeug.security import generate_password_hash
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import create_app


class CouponTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=create_app(self.tmp.name,testing=True)
        self.db=sqlite3.connect(Path(self.tmp.name)/'vyra.sqlite3')
        self.db.row_factory=sqlite3.Row
        self.db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Admin-test-123'),));self.db.commit()
        self.admin=self.app.test_client();self.client=self.app.test_client()
        self.headers={'X-Requested-With':'VYRA'}
        self.post(self.admin,'/auth/login',{'email':'admin@vyra.local','password':'Admin-test-123'})
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def post(self,client,path,body=None,method='POST'):
        return client.open('/api'+path,method=method,json=body or {},headers=self.headers)
    def coupon(self,**kwargs):
        d={'code':'TESTE6H','trial_hours':6,'plan_id':'premium','max_uses':0,'expires_at':0,'active':True,**kwargs}
        r=self.post(self.admin,'/admin/coupons',d)
        self.assertEqual(r.status_code,201,r.json)
        return r.json['id'],d
    def register(self,code='',client=None,email='user@example.com',**kwargs):
        return self.post(client or self.client,'/auth/register',{'name':'Cliente Teste','email':email,'password':'Customer-test-123','plan_id':'premium','coupon_code':code,**kwargs})

    def test_trial_signup_grants_access_without_checkout_or_payment(self):
        self.coupon()
        with patch('app.urlrequest.urlopen') as payment:
            r=self.register(' teste6h ',trial_hours=8760,expires_at=time.time()+99999999,role='admin')
            self.assertEqual(r.status_code,200,r.json)
            self.assertFalse(r.json['checkout_required'])
            self.assertEqual(r.json['coupon_applied'],'TESTE6H')
            self.assertEqual(r.json['user']['role'],'user')
            self.assertTrue(r.json['user']['subscribed'])
            self.assertAlmostEqual(r.json['user']['expires_at']-time.time(),6*3600,delta=3)
            self.assertEqual(self.client.get('/api/play/horizonte').status_code,200)
            payment.assert_not_called()
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM orders').fetchone()[0],0)
        redemption=self.db.execute('SELECT * FROM coupon_redemptions').fetchone()
        self.assertEqual(redemption['user_id'],r.json['user']['id'])
        self.assertEqual(redemption['trial_hours'],6)
        self.assertEqual(self.admin.get('/api/admin/coupons').json['coupons'][0]['used_count'],1)

    def test_no_coupon_keeps_normal_payment_flow(self):
        r=self.register()
        self.assertEqual(r.status_code,200,r.json)
        self.assertTrue(r.json['checkout_required'])
        self.assertIsNone(r.json['coupon_applied'])
        self.assertFalse(r.json['user']['subscribed'])
        self.assertEqual(self.client.get('/api/play/horizonte').status_code,402)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM coupon_redemptions').fetchone()[0],0)

    def test_invalid_expired_disabled_wrong_plan_do_not_create_account(self):
        self.coupon(code='EXPIRED',expires_at=time.time()-60)
        self.coupon(code='DISABLED',active=False)
        self.coupon(code='WRONGPLAN',plan_id='essencial')
        for code in ['MISSING','EXPIRED','DISABLED','WRONGPLAN']:
            r=self.register(code,email=code.lower()+'@example.com')
            self.assertEqual(r.status_code,400,r.json)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0],0)
        self.assertIsNone(self.client.get('/api/bootstrap').json['user'])

    def test_usage_limit_and_failed_signup_rollback(self):
        self.coupon(max_uses=1)
        self.assertEqual(self.register('',email='taken@example.com').status_code,200)
        self.assertEqual(self.register('TESTE6H',email='taken@example.com').status_code,409)
        self.assertEqual(self.admin.get('/api/admin/coupons').json['coupons'][0]['used_count'],0)
        self.assertEqual(self.register('TESTE6H',email='new@example.com').status_code,200)
        self.assertEqual(self.register('TESTE6H',email='extra@example.com').status_code,400)
        self.assertFalse(self.db.execute("SELECT 1 FROM users WHERE email='extra@example.com'").fetchone())
        self.assertEqual(self.admin.get('/api/admin/coupons').json['coupons'][0]['used_count'],1)

    def test_last_coupon_use_is_atomic_under_concurrent_signups(self):
        self.coupon(max_uses=1)
        barrier=threading.Barrier(2)
        def signup(n):
            client=self.app.test_client();barrier.wait()
            return self.register('TESTE6H',client=client,email=f'concurrent{n}@example.com').status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(signup,[1,2]))
        self.assertEqual(sorted(statuses),[200,400])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM coupon_redemptions').fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM users WHERE email LIKE 'concurrent%' ").fetchone()[0],1)

    def test_preview_does_not_reserve_or_grant_access(self):
        self.coupon(max_uses=1)
        r=self.post(self.client,'/coupons/validate',{'code':'teste6h','plan_id':'premium'})
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(r.json['coupon']['trial_hours'],6)
        self.assertNotIn('used_count',r.json['coupon'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM coupon_redemptions').fetchone()[0],0)
        self.assertIsNone(self.client.get('/api/bootstrap').json['user'])
        self.assertEqual(self.post(self.client,'/coupons/validate',{'code':'teste6h','plan_id':'essencial'}).status_code,400)
        self.assertEqual(self.client.post('/api/coupons/validate',json={'code':'teste6h','plan_id':'premium'}).status_code,403)

    def test_admin_authorization_edit_and_trial_survives_deactivation(self):
        cid,d=self.coupon()
        self.assertEqual(self.client.get('/api/admin/coupons').status_code,401)
        r=self.register('TESTE6H')
        expiry=r.json['user']['expires_at']
        self.assertEqual(self.client.get('/api/admin/coupons').status_code,403)
        self.assertEqual(self.post(self.client,'/admin/coupons',d).status_code,403)
        self.assertEqual(self.post(self.client,'/admin/coupons/'+cid,{'active':False},'PATCH').status_code,403)
        self.assertEqual(self.post(self.admin,'/admin/coupons/'+cid,{**d,'trial_hours':72},'PUT').status_code,200)
        self.assertEqual(self.post(self.admin,'/admin/coupons/'+cid,{'active':False},'PATCH').status_code,200)
        self.assertEqual(self.client.get('/api/bootstrap').json['user']['expires_at'],expiry)
        self.assertEqual(self.client.get('/api/play/horizonte').status_code,200)
        self.assertEqual(self.register('TESTE6H',email='later@example.com').status_code,400)
        self.assertEqual(self.post(self.admin,'/admin/coupons/'+cid,{'active':True},'PATCH').status_code,200)
        r=self.register('TESTE6H',email='later@example.com')
        self.assertAlmostEqual(r.json['user']['expires_at']-time.time(),72*3600,delta=3)

    def test_coupon_limits_validation_and_case_uniqueness(self):
        _,d=self.coupon()
        self.assertEqual(self.post(self.admin,'/admin/coupons',{**d,'code':'teste6h'}).status_code,409)
        for change in [{'trial_hours':0},{'trial_hours':8761},{'trial_hours':1.5},{'trial_hours':True},{'expires_at':float('nan')},{'expires_at':[1]},{'expires_at':{'bad':1}},{'plan_id':['premium']},{'code':'bad code'},{'plan_id':'missing'},{'max_uses':-1},{'active':'yes'},{'kind':'anything'}]:
            r=self.post(self.admin,'/admin/coupons',{**d,'code':'ANOTHER',**change})
            self.assertEqual(r.status_code,400,(change,r.json))

    def test_all_plans_coupon_and_expired_access(self):
        self.coupon(plan_id=None)
        r=self.register('TESTE6H',plan_id='essencial')
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(r.json['user']['plan_id'],'essencial')
        self.db.execute('UPDATE users SET expires_at=? WHERE id=?',(time.time()-1,r.json['user']['id']));self.db.commit()
        self.assertEqual(self.client.get('/api/play/horizonte').status_code,402)
        self.assertFalse(self.client.get('/api/bootstrap').json['user']['subscribed'])
        self.assertEqual(self.register('TESTE6H').status_code,409)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM coupon_redemptions').fetchone()[0],1)

if __name__=='__main__':unittest.main(verbosity=2)
