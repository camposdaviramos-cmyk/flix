"""Web Push outbox, PWA routes and bounded background maintenance."""
import base64
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from flask import send_file
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
import room_lifecycle
import social_hub


def key_path(folder):
    path=Path(folder)/'push-private.pem'
    if not path.exists():
        private=ec.generate_private_key(ec.SECP256R1()).private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'wb') as f:f.write(private)
        except FileExistsError:pass
    return path


def public_key(folder):
    key=serialization.load_pem_private_key(key_path(folder).read_bytes(),password=None)
    return base64.urlsafe_b64encode(key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)).decode().rstrip('=')


def deliver(db,folder,send=None):
    if send is None:
        from pywebpush import webpush
        send=webpush
    now=time.time()
    jobs=db.execute("""SELECT d.notification_id,d.subscription_id,d.attempts,n.*,s.endpoint,s.p256dh,s.auth FROM hub_deliveries d JOIN hub_notifications n ON n.id=d.notification_id JOIN hub_push s ON s.id=d.subscription_id JOIN users u ON u.id=s.user_id AND u.status='active' WHERE d.status='pending' AND d.retry_at<=? ORDER BY CASE WHEN n.category='calls' THEN 0 ELSE 1 END,n.id LIMIT 10""",(now,)).fetchall()
    for job in jobs:
        n=dict(job);key=(n['notification_id'],n['subscription_id']);pref=social_hub.preferences(db,n['user_id'])
        pending_call=n['dedupe'].startswith('call:') if n['dedupe'] else False
        call=db.execute('SELECT status,created_at FROM hub_calls WHERE id=?',(n['dedupe'][5:],)).fetchone() if pending_call else None
        expired=pending_call and (not call or call['status']!='ringing' or call['created_at']<time.time()-45)
        if n['read_at'] or expired or not pref.get(n['category'],True) or n['created_at']<time.time()-86400:
            db.execute("UPDATE hub_deliveries SET status='skipped' WHERE notification_id=? AND subscription_id=?",key);db.commit();continue
        row=db.execute("UPDATE hub_deliveries SET status='sending',attempts=attempts+1 WHERE notification_id=? AND subscription_id=? AND status='pending'",key);db.commit()
        if not row.rowcount:continue
        count=db.execute('SELECT COUNT(*) FROM hub_notifications WHERE user_id=? AND read_at IS NULL',(n['user_id'],)).fetchone()[0]
        payload={'title':n['title'],'body':n['body'],'url':n['href'],'tag':'flix-'+str(n['id']),'id':n['id'],'badge':count,'call':pending_call,'silent':not pref['sounds'],'expires':int(n['created_at']+45) if pending_call else None}
        setting=db.execute("SELECT value FROM settings WHERE key='public_url'").fetchone();subject=(setting[0] if setting and setting[0].startswith('https://') else 'https://flix.devspacey.com').rstrip('/')
        try:
            send(subscription_info={'endpoint':n['endpoint'],'keys':{'p256dh':n['p256dh'],'auth':n['auth']}},data=json.dumps(payload),vapid_private_key=str(key_path(folder)),vapid_claims={'sub':subject},ttl=max(1,int(n['created_at']+45-time.time())) if pending_call else 3600,timeout=8)
            db.execute("UPDATE hub_deliveries SET status='sent' WHERE notification_id=? AND subscription_id=?",key)
        except Exception as e:
            response=getattr(e,'response',None);status=getattr(response,'status_code',None)
            if status in (404,410):db.execute('DELETE FROM hub_push WHERE id=?',(n['subscription_id'],))
            else:db.execute('UPDATE hub_deliveries SET status=?,retry_at=? WHERE notification_id=? AND subscription_id=?',('failed' if n['attempts']>=4 else 'pending',time.time()+min(900,15*2**n['attempts']),*key))
        db.commit()


def register(app):
    root=Path(app.static_folder)
    @app.get('/sw.js')
    def worker_script():
        r=send_file(root/'sw.js',mimetype='application/javascript',max_age=0);r.headers['Service-Worker-Allowed']='/';r.headers['Cache-Control']='no-cache';return r
    @app.get('/manifest.webmanifest')
    def manifest():return send_file(root/'manifest.webmanifest',mimetype='application/manifest+json',max_age=300)
    if app.config['TESTING']:return
    folder=Path(app.config['DATA_DIR']);key_path(folder)
    def worker():
        # One delivery worker per database, even with several WSGI processes.
        import fcntl
        lock=(folder/'push-worker.lock').open('a')
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:lock.close();return
        with sqlite3.connect(folder/'vyra.sqlite3',timeout=20) as conn:
            conn.row_factory=sqlite3.Row;conn.execute('PRAGMA foreign_keys=ON')
            conn.execute("UPDATE hub_deliveries SET status='pending' WHERE status='sending'");conn.commit()
            cleanup=0
            while True:
                try:
                    if time.time()-cleanup>15:
                        conn.execute('BEGIN IMMEDIATE');room_lifecycle.sweep(conn);social_hub.expire_calls(conn)
                        conn.execute('DELETE FROM hub_notifications WHERE created_at<?',(time.time()-90*86400,));conn.commit();cleanup=time.time()
                    deliver(conn,folder)
                except Exception as e:
                    conn.rollback();app.logger.warning('Flix background worker: %s',type(e).__name__)
                time.sleep(2)
    threading.Thread(target=worker,name='flix-notifications',daemon=True).start()
