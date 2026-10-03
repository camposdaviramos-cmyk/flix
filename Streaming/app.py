import functools
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import time
import uuid
from decimal import Decimal
from pathlib import Path
from urllib import request as urlrequest, error as urlerror
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from flask import Flask, g, request, jsonify, send_from_directory, Response
from social_text import SocialJSONProvider, payload as text_payload
from seo import metadata, head as seo_head, fallback as seo_fallback, sitemap as seo_sitemap
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
from media import valid_url, fetch_playlist, parse_playlist
from playback_diagnostics import register_playback_diagnostics, automatic_diagnostics
from seed import catalog, SAMPLE
import flix_wallet
from community import migrate as migrate_community, register_community
from jump import migrate as migrate_jump, register_jump, username_for
from coupons import migrate as migrate_coupons, register_coupons, available_coupon, redeem as redeem_coupon

ROOT = Path(__file__).parent

SCHEMA = '''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT DEFAULT 'user',status TEXT DEFAULT 'active',plan_id TEXT,expires_at REAL DEFAULT 0,created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY,name TEXT NOT NULL,price INTEGER NOT NULL,days INTEGER DEFAULT 30,quality TEXT,devices INTEGER DEFAULT 1,features TEXT,active INTEGER DEFAULT 1,featured INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS content(id TEXT PRIMARY KEY,title TEXT NOT NULL,kind TEXT NOT NULL,genre TEXT,year INTEGER,rating TEXT,description TEXT,poster TEXT,backdrop TEXT,duration TEXT,video_url TEXT,featured INTEGER DEFAULT 0,published INTEGER DEFAULT 1,sample INTEGER DEFAULT 0,created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS episodes(id TEXT PRIMARY KEY,content_id TEXT REFERENCES content(id) ON DELETE CASCADE,season INTEGER NOT NULL,number INTEGER NOT NULL,title TEXT NOT NULL,video_url TEXT NOT NULL,duration TEXT,UNIQUE(content_id,season,number));
CREATE TABLE IF NOT EXISTS progress(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,content_id TEXT REFERENCES content(id) ON DELETE CASCADE,episode_id TEXT DEFAULT '',position REAL NOT NULL,duration REAL NOT NULL,updated_at REAL NOT NULL,client_time REAL NOT NULL,PRIMARY KEY(user_id,content_id,episode_id));
CREATE TABLE IF NOT EXISTS watch_history(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,content_id TEXT REFERENCES content(id) ON DELETE CASCADE,watched_at REAL NOT NULL,PRIMARY KEY(user_id,content_id));
CREATE INDEX IF NOT EXISTS idx_watch_content ON watch_history(content_id);
CREATE TABLE IF NOT EXISTS favorites(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,content_id TEXT REFERENCES content(id) ON DELETE CASCADE,PRIMARY KEY(user_id,content_id));
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),plan_id TEXT,amount INTEGER,days INTEGER,status TEXT DEFAULT 'pending',payment_id TEXT UNIQUE,preference_id TEXT,created_at REAL NOT NULL,paid_at REAL,expires_at REAL);
CREATE TABLE IF NOT EXISTS attempts(ip TEXT,time REAL);
CREATE INDEX IF NOT EXISTS idx_attempts ON attempts(ip,time);
'''

class APIError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status

def create_app(data_dir=None, testing=False):
    app = Flask(__name__, static_folder='static')
    folder = Path(data_dir or os.getenv('VYRA_DATA_DIR', ROOT / 'data'))
    folder.mkdir(parents=True, exist_ok=True)
    keyfile = folder / 'secret.key'
    if not keyfile.exists():
        keyfile.write_bytes(Fernet.generate_key())
    cipher = Fernet(keyfile.read_bytes())
    app.config.update(TESTING=testing, MAX_CONTENT_LENGTH=2_100_000, DATA_DIR=folder)

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(folder / 'vyra.sqlite3', timeout=20)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys=ON')
        return g.db

    @app.teardown_appcontext
    def close_db(_):
        if 'db' in g:
            g.db.close()

    def setting(key, default=''):
        row = db().execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        if not row:
            return default
        return cipher.decrypt(row['value'].encode()).decode() if key in ('access_token', 'webhook_secret','youtube_api_key','soundcloud_client_id','soundcloud_client_secret','soundcloud_token') else row['value']

    def save_setting(key, value):
        value = cipher.encrypt(value.encode()).decode() if key in ('access_token', 'webhook_secret','youtube_api_key','soundcloud_client_id','soundcloud_client_secret','soundcloud_token') else value
        db().execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, value))

    with app.app_context():
        db().executescript(SCHEMA)
        if not db().execute('SELECT 1 FROM plans LIMIT 1').fetchone():
            for p in [('essencial','Essencial',1990,30,'Full HD',1,['Filmes e séries','TV ao vivo','Continue de onde parou'],0),('premium','Premium',2990,30,'4K Ultra HD',2,['Todo o catálogo','TV ao vivo','Continue de onde parou','Até 2 sessões de acesso'],1),('familia','Família',3990,30,'4K Ultra HD',4,['Todo o catálogo','TV ao vivo','Continue de onde parou','Até 4 sessões de acesso'],0)]:
                db().execute('INSERT INTO plans(id,name,price,days,quality,devices,features,featured) VALUES(?,?,?,?,?,?,?,?)', (*p[:6],json.dumps(p[6]),p[7]))
            for c in catalog():
                insert_content(db(), c)
                if c['kind'] == 'series':
                    for n, title in enumerate(['O começo de tudo', 'Além das aparências', 'Um novo caminho'], 1):
                        db().execute('INSERT INTO episodes VALUES(?,?,?,?,?,?,?)', (uuid.uuid4().hex,c['id'],1,n,title,SAMPLE,'14min'))
            db().execute('INSERT INTO settings VALUES(?,?)', ('brand','Flix'))
            db().execute('INSERT INTO settings VALUES(?,?)', ('mode','test'))
        if not db().execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
            password = secrets.token_urlsafe(15)
            db().execute('INSERT INTO users(id,name,email,password,role,created_at) VALUES(?,?,?,?,?,?)', (uuid.uuid4().hex,'Administrador','admin@vyra.local',generate_password_hash(password),'admin',time.time()))
            if not testing:
                (folder / 'initial-admin.txt').write_text(f'URL: http://localhost:8000/admin\nE-mail: admin@vyra.local\nSenha: {password}\n\nAltere a senha na sua conta depois do primeiro acesso.\n', encoding='utf-8')
        for item in catalog():
            if (ROOT / 'static' / 'assets' / (item['id'] + '.jpg')).exists():
                local = '/static/assets/' + item['id'] + '.jpg'
                db().execute('UPDATE content SET poster=?,backdrop=? WHERE id=? AND poster=?',(local,local,item['id'],item['poster']))
        old_sample = 'https://storage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4'
        db().execute('UPDATE content SET video_url=? WHERE sample=1 AND video_url=?',(SAMPLE,old_sample))
        db().execute('UPDATE episodes SET video_url=? WHERE video_url=? AND content_id IN (SELECT id FROM content WHERE sample=1)',(SAMPLE,old_sample))
        migrate_jump(db())
        migrate_coupons(db())
        migrate_community(db())
        db().execute("UPDATE settings SET value='Flix' WHERE key='brand' AND UPPER(value)='VYRA'")
        db().commit()

    @app.before_request
    def protect():
        if request.path in ('/api/community/assets','/api/hub/audio') and request.method=='POST':
            request.max_content_length=26*1024*1024
        g.user = None
        token = request.cookies.get('vyra_session', '')
        if token:
            g.user = db().execute("SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=? AND s.expires_at>? AND u.status='active'", (hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        if request.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS') and request.path != '/api/payments/webhook':
            origin = request.headers.get('Origin')
            if origin and origin != request.host_url.rstrip('/') and origin != setting('public_url'):
                raise APIError('Origem da solicitação não permitida.',403)
            if request.headers.get('X-Requested-With') not in ('VYRA','Flix'):
                raise APIError('Solicitação inválida. Recarregue a página.',403)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Permissions-Policy'] = 'camera=(self), microphone=(self), geolocation=()'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://www.youtube.com https://s.ytimg.com https://w.soundcloud.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob: https: http:; media-src 'self' blob: https: http:; connect-src 'self' https: http:; worker-src 'self' blob:; frame-src https://www.youtube.com https://www.youtube-nocookie.com https://w.soundcloud.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(APIError)
    @app.errorhandler(ValueError)
    def expected_error(error):
        return jsonify(error=getattr(error,'message',str(error))), getattr(error,'status',400)

    @app.errorhandler(Exception)
    def unexpected_error(error):
        if isinstance(error, HTTPException):
            return jsonify(error=error.description), error.code
        app.logger.exception('Erro ao processar solicitação')
        return jsonify(error='Não foi possível concluir. Tente novamente.'), 500

    def auth(admin=False, paid=False):
        def decorator(fn):
            @functools.wraps(fn)
            def wrapped(*args, **kwargs):
                if g.user is None:
                    raise APIError('Entre na sua conta para continuar.',401)
                if admin and g.user['role'] != 'admin':
                    raise APIError('Acesso restrito à administração.',403)
                if paid and g.user['role'] != 'admin' and g.user['expires_at'] <= time.time():
                    raise APIError('Escolha um plano para começar a assistir.',402)
                return fn(*args, **kwargs)
            return wrapped
        return decorator

    app.json = SocialJSONProvider(app)

    def data():
        result = request.get_json(silent=True)
        if not isinstance(result, dict):
            raise APIError('Envie os dados em formato JSON.')
        return text_payload(result)

    def public_user(user):
        if not user:
            return None
        value = {k:user[k] for k in ('id','name','username','email','role','status','plan_id','expires_at','created_at','verified')}
        profile = db().execute('SELECT avatar FROM community_profiles WHERE user_id=?',(user['id'],)).fetchone()
        value['avatar'] = profile['avatar'] if profile else ''
        value['subscribed'] = user['role']=='admin' or user['expires_at']>time.time()
        return value

    def session_response(user, **extra):
        token = secrets.token_urlsafe(40)
        db().execute('DELETE FROM sessions WHERE expires_at<?',(time.time(),))
        if user['role'] != 'admin':
            plan = db().execute('SELECT devices FROM plans WHERE id=?',(user['plan_id'],)).fetchone()
            limit = plan['devices'] if plan else 1
            old = db().execute('SELECT token FROM sessions WHERE user_id=? ORDER BY expires_at DESC',(user['id'],)).fetchall()
            for row in old[max(0,limit-1):]:
                db().execute('DELETE FROM sessions WHERE token=?',(row['token'],))
        db().execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],time.time()+30*86400))
        db().commit()
        response = jsonify(user=public_user(user), **extra)
        response.set_cookie('vyra_session',token,httponly=True,secure=setting('public_url').startswith('https://'),samesite='Lax',max_age=30*86400)
        return response

    def rate_limit():
        ip = hashlib.sha256(request.remote_addr.encode()).hexdigest()
        now=time.time()
        db().execute('DELETE FROM attempts WHERE time<?',(now-900,))
        count=db().execute('SELECT count(*) FROM attempts WHERE ip=?',(ip,)).fetchone()[0]
        if count >= 15:
            raise APIError('Muitas tentativas. Aguarde 15 minutos.',429)
        db().execute('INSERT INTO attempts VALUES(?,?)',(ip,now))
        db().commit()

    @app.get('/api/bootstrap')
    def bootstrap():
        plans=[dict(p) for p in db().execute('SELECT * FROM plans WHERE active=1 ORDER BY price')]
        for p in plans:
            p['features']=json.loads(p['features'])
        return jsonify(brand=setting('brand','Flix'),plans=plans,user=public_user(g.user),checkout_ready=bool(setting('access_token') and setting('webhook_secret') and setting('public_url')),support_email=setting('support_email',''))

    @app.post('/api/auth/register')
    def register():
        rate_limit()
        d=data()
        name=str(d.get('name','')).strip()
        email=str(d.get('email','')).strip().lower()
        password=str(d.get('password',''))
        if not 2<=len(name)<=100 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254:
            raise APIError('Preencha seu nome e um e-mail válido.')
        if not 10<=len(password)<=128:
            raise APIError('Use uma senha entre 10 e 128 caracteres.')
        community_account=d.get('account_type')=='community'
        plan_id=None if community_account else d.get('plan_id')
        if not community_account and not db().execute('SELECT 1 FROM plans WHERE id=? AND active=1',(plan_id,)).fetchone():
            raise APIError('Selecione um plano disponível.')
        password_hash=generate_password_hash(password)
        db().execute('BEGIN IMMEDIATE')
        uid=uuid.uuid4().hex
        username=username_for(db(), d.get('username'), name, APIError)
        code=d.get('coupon_code','')
        if isinstance(code,str):
            code=code.strip()
        if community_account and code:raise APIError('Para usar um cupom de assinatura, selecione um plano no cadastro de assinantes.')
        coupon=available_coupon(db(),code,plan_id,APIError) if code else None
        now=time.time()
        expires=now+coupon['trial_hours']*3600 if coupon else 0
        try:
            db().execute('INSERT INTO users(id,name,username,email,password,plan_id,expires_at,created_at) VALUES(?,?,?,?,?,?,?,?)',(uid,name,username,email,password_hash,plan_id,expires,now))
            if coupon:
                redeem_coupon(db(),coupon,uid,plan_id,expires)
            db().commit()
        except sqlite3.IntegrityError:
            db().rollback()
            raise APIError('Este e-mail ou nome de usuário já está cadastrado. Entre na sua conta.',409)
        return session_response(db().execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone(),checkout_required=not community_account and not bool(coupon),coupon_applied=coupon['code'] if coupon else None)

    @app.post('/api/auth/login')
    def login():
        rate_limit()
        d=data()
        user=db().execute('SELECT * FROM users WHERE email=?',(str(d.get('email','')).strip().lower(),)).fetchone()
        if not user or not check_password_hash(user['password'],str(d.get('password',''))) or user['status']!='active':
            raise APIError('E-mail ou senha inválidos, ou conta bloqueada.',401)
        return session_response(user)

    @app.post('/api/auth/logout')
    def logout():
        db().execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(request.cookies.get('vyra_session','').encode()).hexdigest(),))
        db().commit()
        response=jsonify(ok=True)
        response.delete_cookie('vyra_session')
        return response

    @app.patch('/api/account')
    @auth()
    def account():
        d=data()
        if not check_password_hash(g.user['password'],str(d.get('current_password',''))):
            raise APIError('Sua senha atual está incorreta.')
        password=str(d.get('new_password',''))
        if not 10<=len(password)<=128:
            raise APIError('A nova senha deve ter entre 10 e 128 caracteres.')
        db().execute('UPDATE users SET password=? WHERE id=?',(generate_password_hash(password),g.user['id']))
        db().execute('DELETE FROM sessions WHERE user_id=?',(g.user['id'],))
        db().commit()
        return session_response(g.user)

    @app.get('/api/catalog')
    def get_catalog():
        items=[dict(row) for row in db().execute('SELECT c.*, (SELECT COUNT(*) FROM watch_history h WHERE h.content_id=c.id) AS viewers FROM content c WHERE c.published=1 ORDER BY c.featured DESC,c.created_at')]
        for item in items:
            item.pop('video_url',None)
            item['episodes']=[dict(r) for r in db().execute('SELECT id,season,number,title,duration FROM episodes WHERE content_id=? ORDER BY season,number',(item['id'],))]
        return jsonify(items=items)

    @app.get('/api/library')
    @auth()
    def library():
        return jsonify(recent_watched=[dict(p) for p in db().execute("SELECT h.content_id,h.watched_at,c.kind FROM watch_history h JOIN content c ON c.id=h.content_id WHERE h.user_id=? AND c.published=1 ORDER BY h.watched_at DESC LIMIT 100",(g.user['id'],))],progress=[dict(p) for p in db().execute('SELECT * FROM progress WHERE user_id=? ORDER BY updated_at DESC',(g.user['id'],))],favorites=[p[0] for p in db().execute('SELECT content_id FROM favorites WHERE user_id=?',(g.user['id'],))],recent_channels=[dict(p) for p in db().execute("SELECT h.content_id,h.watched_at FROM watch_history h JOIN content c ON c.id=h.content_id WHERE h.user_id=? AND c.kind='channel' AND c.published=1 ORDER BY h.watched_at DESC",(g.user['id'],))])

    @app.post('/api/favorites/<cid>')
    @auth()
    def favorite(cid):
        if not db().execute('SELECT 1 FROM content WHERE id=? AND published=1',(cid,)).fetchone():
            raise APIError('Título não encontrado.',404)
        exists=db().execute('SELECT 1 FROM favorites WHERE user_id=? AND content_id=?',(g.user['id'],cid)).fetchone()
        if exists:
            db().execute('DELETE FROM favorites WHERE user_id=? AND content_id=?',(g.user['id'],cid))
        else:
            db().execute('INSERT INTO favorites VALUES(?,?)',(g.user['id'],cid))
        db().commit()
        return jsonify(saved=not bool(exists))

    def playback_item(cid, eid=''):
        item=db().execute('SELECT * FROM content WHERE id=? AND published=1',(cid,)).fetchone()
        if not item:
            raise APIError('Título não encontrado.',404)
        video=item['video_url']
        if item['kind']=='series':
            episode=db().execute('SELECT * FROM episodes WHERE id=? AND content_id=?',(eid,cid)).fetchone()
            if not episode:
                raise APIError('Selecione um episódio disponível.',404)
            video=episode['video_url']
        elif eid:
            raise APIError('Episódio inválido.')
        return item, video

    @app.get('/api/play/<cid>')
    @auth(paid=True)
    def play(cid):
        eid=request.args.get('episode','')
        item,video=playback_item(cid,eid)
        if not video:
            raise APIError('Este conteúdo ainda não tem vídeo disponível.',404)
        progress=db().execute('SELECT position,duration FROM progress WHERE user_id=? AND content_id=? AND episode_id=?',(g.user['id'],cid,eid)).fetchone()
        if item['sample'] and video == SAMPLE and (ROOT / 'static/assets/sintel-trailer.mp4').exists():
            video = '/static/assets/sintel-trailer.mp4'
        db().execute('INSERT INTO watch_history VALUES(?,?,?) ON CONFLICT(user_id,content_id) DO UPDATE SET watched_at=excluded.watched_at',(g.user['id'],cid,time.time()))
        db().commit()
        return jsonify(url=video,position=progress['position'] if progress else 0,duration=progress['duration'] if progress else 0,live=item['kind']=='channel',sample=bool(item['sample']),diagnostic=automatic_diagnostics(db(),g.user,cid),viewers=db().execute('SELECT COUNT(*) FROM watch_history WHERE content_id=?',(cid,)).fetchone()[0])

    @app.put('/api/progress/<cid>')
    @auth(paid=True)
    def progress(cid):
        d=data()
        eid=str(d.get('episode_id',''))
        item,_=playback_item(cid,eid)
        if item['kind']=='channel':
            return jsonify(ok=True)
        pos,duration,client=float(d.get('position',0)),float(d.get('duration',0)),float(d.get('client_time',0))
        if not all(math.isfinite(x) for x in (pos,duration,client)) or duration<=0 or pos<0 or pos>duration+1 or duration>604800 or client>time.time()*1000+300000:
            raise APIError('Posição de reprodução inválida.')
        db().execute('INSERT INTO progress VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id,content_id,episode_id) DO UPDATE SET position=excluded.position,duration=excluded.duration,updated_at=excluded.updated_at,client_time=excluded.client_time WHERE excluded.client_time>=progress.client_time',(g.user['id'],cid,eid,pos,duration,time.time(),client))
        db().commit()
        return jsonify(ok=True)

    def mp_request(path, payload=None, idempotency=None):
        token=setting('access_token')
        if not token:
            raise APIError('O checkout está sendo preparado. Tente novamente em breve.',503)
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','User-Agent':'VYRA/1.0'}
        if idempotency:
            headers['X-Idempotency-Key']=idempotency
        req=urlrequest.Request('https://api.mercadopago.com'+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
        try:
            with urlrequest.urlopen(req,timeout=20) as resp:
                return json.load(resp)
        except (urlerror.URLError,TimeoutError):
            raise APIError('O Mercado Pago não respondeu. Verifique as credenciais ou tente novamente.',502)

    @app.post('/api/checkout')
    @auth()
    def checkout():
        d=data()
        coins=0;kind='subscription';plan_id=None;days=0
        if d.get('package_id'):
            pack=db().execute('SELECT * FROM coin_packages WHERE id=? AND active=1',(d['package_id'],)).fetchone()
            if not pack:raise APIError('Pacote de moedas indisponível.')
            if d.get('confirm_price')!=pack['price'] or d.get('confirm_coins')!=pack['coins']:raise APIError('O pacote mudou. Confira os valores e confirme novamente.',409)
            coins=pack['coins'];amount=pack['price'];kind='coins';label=pack['name'];item_id=pack['id'];back='/carteira'
        else:
            plan=db().execute('SELECT * FROM plans WHERE id=? AND active=1',(d.get('plan_id',''),)).fetchone()
            if not plan:raise APIError('Plano indisponível.')
            plan_id=plan['id'];days=plan['days'];amount=plan['price'];label=plan['name'];item_id=plan['id'];back='/conta'
        base=setting('public_url').rstrip('/')
        if not base.startswith('https://') or not setting('webhook_secret'):
            raise APIError('O checkout está sendo preparado. Tente novamente em breve.',503)
        oid=uuid.uuid4().hex
        db().execute('INSERT INTO orders(id,user_id,plan_id,amount,days,kind,coins,label,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(oid,g.user['id'],plan_id,amount,days,kind,coins,label,time.time()))
        db().commit()
        pref=mp_request('/checkout/preferences',{'items':[{'id':item_id,'title':f"{setting('brand','Flix')} · {label}",'quantity':1,'currency_id':'BRL','unit_price':amount/100}],'payer':{'email':g.user['email']},'external_reference':oid,'back_urls':{s:base+back+'?payment='+s+'&order='+oid for s in ('success','failure','pending')},'notification_url':base+'/api/payments/webhook','auto_return':'approved','metadata':{'order_id':oid}},oid)
        db().execute('UPDATE orders SET preference_id=? WHERE id=?',(pref['id'],oid))
        db().commit()
        target=pref.get('sandbox_init_point') if setting('mode','test')=='test' else pref.get('init_point')
        if not target:
            raise APIError('O Mercado Pago não retornou o endereço do checkout.',502)
        return jsonify(url=target,order_id=oid)

    def reconcile(payment_id, expected_user=None):
        if not re.fullmatch(r'[0-9]{1,30}',str(payment_id)):
            raise APIError('Pagamento inválido.')
        p=mp_request('/v1/payments/'+str(payment_id))
        order=db().execute('SELECT * FROM orders WHERE id=?',(p.get('external_reference',''),)).fetchone()
        if not order or (expected_user and order['user_id']!=expected_user):
            raise APIError('Pedido não encontrado.',404)
        if p.get('currency_id')!='BRL' or Decimal(str(p.get('transaction_amount',0)))*100!=order['amount']:
            raise APIError('O valor do pagamento não corresponde ao pedido.',400)
        live = p.get('live_mode')
        if live is not None and bool(live)!=(setting('mode','test')=='production'):
            raise APIError('O ambiente do pagamento não corresponde à configuração.',400)
        status=p.get('status','pending')
        db().execute('BEGIN IMMEDIATE')
        try:
            order=db().execute('SELECT * FROM orders WHERE id=?',(order['id'],)).fetchone()
            if order['payment_id'] and order['payment_id']!=str(payment_id) and order['paid_at']:
                db().rollback()
                return 'approved'
            if order['kind']=='coins':
                flix_wallet.payment(db(),order,status)
                if status=='approved' and not order['paid_at']:db().execute('UPDATE orders SET paid_at=? WHERE id=?',(time.time(),order['id']))
            if order['kind']=='subscription' and status=='approved' and not order['paid_at']:
                user=db().execute('SELECT * FROM users WHERE id=?',(order['user_id'],)).fetchone()
                expires=max(time.time(),user['expires_at'])+order['days']*86400
                db().execute('UPDATE users SET plan_id=?,expires_at=? WHERE id=?',(order['plan_id'],expires,user['id']))
                db().execute('UPDATE orders SET paid_at=?,expires_at=? WHERE id=?',(time.time(),expires,order['id']))
            db().execute('UPDATE orders SET status=?,payment_id=? WHERE id=?',(status,str(payment_id),order['id']))
            if order['kind']=='subscription' and status in ('refunded','charged_back') and order['paid_at']:
                latest=db().execute("SELECT expires_at,plan_id FROM orders WHERE user_id=? AND kind='subscription' AND status='approved' ORDER BY expires_at DESC LIMIT 1",(order['user_id'],)).fetchone()
                db().execute('UPDATE users SET expires_at=?,plan_id=? WHERE id=?',(latest['expires_at'] if latest else 0,latest['plan_id'] if latest else None,order['user_id']))
            db().commit()
        except Exception:
            db().rollback()
            raise
        return status

    @app.post('/api/payments/webhook')
    def webhook():
        secret=setting('webhook_secret')
        if not secret:
            raise APIError('Webhook não configurado.',503)
        pid=request.args.get('data.id','').lower()
        rid=request.headers.get('x-request-id','')
        parts=dict(piece.strip().split('=',1) for piece in request.headers.get('x-signature','').split(',') if '=' in piece)
        ts=parts.get('ts','')
        manifest=f'id:{pid};request-id:{rid};ts:{ts};'
        signature=hmac.new(secret.encode(),manifest.encode(),hashlib.sha256).hexdigest()
        if not pid or not rid or not ts.isdigit() or not hmac.compare_digest(signature,parts.get('v1','')):
            raise APIError('Assinatura inválida.',401)
        body=request.get_json(silent=True) or {}
        if body.get('type','payment')!='payment':
            return jsonify(ok=True)
        return jsonify(ok=True,status=reconcile(pid))

    @app.post('/api/payments/sync')
    @auth()
    def sync_payment():
        return jsonify(status=reconcile(data().get('payment_id',''),g.user['id']))

    @app.get('/api/orders')
    @auth()
    def my_orders():
        return jsonify(orders=[dict(r) for r in db().execute('SELECT o.id,o.amount,o.status,o.created_at,o.expires_at,p.name FROM orders o LEFT JOIN plans p ON p.id=o.plan_id WHERE user_id=? ORDER BY o.created_at DESC',(g.user['id'],))])

    @app.get('/api/admin/overview')
    @auth(admin=True)
    def overview():
        return jsonify(users=db().execute("SELECT count(*) FROM users WHERE role='user'").fetchone()[0],subscribers=db().execute("SELECT count(*) FROM users WHERE role='user' AND expires_at>? AND status='active'",(time.time(),)).fetchone()[0],revenue=db().execute("SELECT coalesce(sum(amount),0) FROM orders WHERE status='approved'").fetchone()[0],content=db().execute('SELECT count(*) FROM content').fetchone()[0],orders=[dict(r) for r in db().execute('SELECT o.*,u.name,u.email,p.name as plan_name FROM orders o JOIN users u ON u.id=o.user_id LEFT JOIN plans p ON p.id=o.plan_id ORDER BY o.created_at DESC LIMIT 100')])

    @app.get('/api/admin/content')
    @auth(admin=True)
    def admin_content():
        items=[dict(r) for r in db().execute('SELECT * FROM content ORDER BY created_at DESC')]
        for item in items:
            item['episodes']=[dict(e) for e in db().execute('SELECT * FROM episodes WHERE content_id=? ORDER BY season,number',(item['id'],))]
        return jsonify(items=items)

    @app.route('/api/admin/content',methods=['POST'])
    @app.route('/api/admin/content/<cid>',methods=['PUT','DELETE'])
    @auth(admin=True)
    def edit_content(cid=None):
        if cid and not db().execute('SELECT 1 FROM content WHERE id=?',(cid,)).fetchone():
            raise APIError('Conteúdo não encontrado.',404)
        if request.method=='DELETE':
            db().execute('DELETE FROM content WHERE id=?',(cid,))
            db().commit()
            return jsonify(ok=True)
        d=data()
        title=str(d.get('title','')).strip()
        if not title or len(title)>160 or d.get('kind') not in ('movie','series','channel'):
            raise APIError('Informe o título e o tipo de conteúdo.')
        item={k:str(d.get(k,''))[:6000] for k in ('genre','rating','description','duration')}
        item.update(id=cid or uuid.uuid4().hex,title=title,kind=d['kind'],year=int(d.get('year') or 2026),featured=int(bool(d.get('featured'))),published=int(bool(d.get('published'))),sample=int(bool(d.get('sample'))))
        for key in ('poster','backdrop'):
            value=str(d.get(key,''))
            item[key]=value if value.startswith('/static/assets/') else valid_url(value,optional=True)
        item['video_url']=valid_url(d.get('video_url',''),optional=d['kind']=='series')
        episodes=d.get('episodes',[])
        if not isinstance(episodes,list) or len(episodes)>1000:
            raise APIError('Lista de episódios inválida.')
        seen=set()
        for e in episodes:
            e['season'],e['number']=int(e.get('season',1)),int(e.get('number',1))
            if min(e['season'],e['number'])<1 or (e['season'],e['number']) in seen or not str(e.get('title','')).strip():
                raise APIError('Confira os títulos e a numeração dos episódios.')
            seen.add((e['season'],e['number']))
            e['video_url']=valid_url(e.get('video_url',''))
        if cid:
            db().execute('UPDATE content SET '+','.join(k+'=?' for k in item if k!='id')+' WHERE id=?',(*[v for k,v in item.items() if k!='id'],cid))
        else:
            insert_content(db(),item)
        current={e['id'] for e in db().execute('SELECT id FROM episodes WHERE content_id=?',(item['id'],))}
        keep=set()
        if item['kind']=='series':
            # Temporarily move indices to avoid collisions when episodes are reordered.
            db().execute('UPDATE episodes SET season=-season WHERE content_id=?',(item['id'],))
            for e in episodes:
                eid=e.get('id') if e.get('id') in current else uuid.uuid4().hex
                keep.add(eid)
                db().execute('INSERT INTO episodes VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET season=excluded.season,number=excluded.number,title=excluded.title,video_url=excluded.video_url,duration=excluded.duration',(eid,item['id'],e['season'],e['number'],str(e['title'])[:160],e['video_url'],str(e.get('duration',''))[:40]))
        for eid in current-keep:
            db().execute('DELETE FROM episodes WHERE id=?',(eid,))
            db().execute('DELETE FROM progress WHERE episode_id=?',(eid,))
        db().commit()
        return jsonify(ok=True,id=item['id'])

    @app.post('/api/admin/import')
    @auth(admin=True)
    def import_channels():
        d=data()
        text=str(d.get('text',''))
        base=''
        if d.get('url'):
            text,base=fetch_playlist(d['url'])
        channels,skipped=parse_playlist(text,base)
        existing={r[0] for r in db().execute("SELECT video_url FROM content WHERE kind='channel'")}
        imported=0
        for channel in channels:
            if channel['video_url'] in existing:
                skipped+=1
                continue
            existing.add(channel['video_url'])
            insert_content(db(),dict(id=uuid.uuid4().hex,kind='channel',description='Transmissão ao vivo',year=2026,rating='L',backdrop=channel['poster'],duration='Ao vivo',featured=0,published=1,sample=0,**channel))
            imported+=1
        db().commit()
        return jsonify(imported=imported,skipped=skipped)

    @app.get('/api/admin/users')
    @auth(admin=True)
    def users():
        return jsonify(users=[public_user(u) for u in db().execute('SELECT * FROM users ORDER BY created_at DESC')])

    @app.patch('/api/admin/users/<uid>')
    @auth(admin=True)
    def edit_user(uid):
        d=data()
        user=db().execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if not user:
            raise APIError('Usuário não encontrado.',404)
        status=d.get('status',user['status'])
        role=d.get('role',user['role'])
        if status not in ('active','blocked') or role not in ('user','admin'):
            raise APIError('Status inválido.')
        if uid==g.user['id'] and (status!='active' or role!='admin'):
            raise APIError('Você não pode remover o próprio acesso administrativo.')
        plan=d.get('plan_id') or None
        if plan and not db().execute('SELECT 1 FROM plans WHERE id=?',(plan,)).fetchone():
            raise APIError('Plano inválido.')
        expires=float(d.get('expires_at',user['expires_at']))
        if not math.isfinite(expires) or expires<0:
            raise APIError('Data inválida.')
        db().execute('UPDATE users SET name=?,status=?,role=?,plan_id=?,expires_at=? WHERE id=?',(str(d.get('name',user['name']))[:100],status,role,plan,expires,uid))
        if status=='blocked':
            db().execute('DELETE FROM sessions WHERE user_id=?',(uid,))
        db().commit()
        return jsonify(ok=True)

    @app.get('/api/admin/plans')
    @auth(admin=True)
    def admin_plans():
        items=[dict(r) for r in db().execute('SELECT * FROM plans ORDER BY price')]
        for item in items:
            item['features']=json.loads(item['features'])
        return jsonify(plans=items)

    @app.route('/api/admin/plans',methods=['POST'])
    @app.route('/api/admin/plans/<pid>',methods=['PUT'])
    @auth(admin=True)
    def edit_plan(pid=None):
        d=data()
        if pid and not db().execute('SELECT 1 FROM plans WHERE id=?',(pid,)).fetchone():
            raise APIError('Plano não encontrado.',404)
        name=str(d.get('name','')).strip()
        price,days,devices=int(d.get('price',0)),int(d.get('days',30)),int(d.get('devices',1))
        if not name or len(name)>80 or not 100<=price<=10000000 or not 1<=days<=366 or not 1<=devices<=20:
            raise APIError('Confira nome, preço, duração e número de acessos do plano.')
        features=d.get('features',[])
        if not isinstance(features,list) or len(features)>20:
            raise APIError('Benefícios inválidos.')
        values=(name,price,days,str(d.get('quality','Full HD'))[:30],devices,json.dumps([str(f)[:150] for f in features]),int(bool(d.get('active',True))),int(bool(d.get('featured',False))))
        if pid:
            db().execute('UPDATE plans SET name=?,price=?,days=?,quality=?,devices=?,features=?,active=?,featured=? WHERE id=?',(*values,pid))
        else:
            pid=uuid.uuid4().hex
            db().execute('INSERT INTO plans VALUES(?,?,?,?,?,?,?,?,?)',(pid,*values))
        db().commit()
        return jsonify(ok=True)

    @app.route('/api/admin/settings',methods=['GET','PUT'])
    @auth(admin=True)
    def settings():
        if request.method=='PUT':
            d=data()
            public=str(d.get('public_url','')).rstrip('/')
            if public:
                valid_url(public)
                if not public.startswith('https://') or urlparse(public).path:
                    raise APIError('Informe o domínio público HTTPS, sem caminho final.')
            mode=d.get('mode','test')
            if mode not in ('test','production'):
                raise APIError('Ambiente inválido.')
            for key in ('brand','support_email','public_url','mode'):
                save_setting(key,str(d.get(key,'')).strip()[:300])
            for key in ('access_token','webhook_secret','youtube_api_key','soundcloud_client_id','soundcloud_client_secret'):
                if d.get(key):
                    save_setting(key,str(d[key]).strip())
            if d.get('soundcloud_client_id') or d.get('soundcloud_client_secret'):save_setting('soundcloud_token','{}')
            db().commit()
        return jsonify(**{k:setting(k) for k in ('brand','support_email','public_url','mode')},access_token_configured=bool(setting('access_token')),webhook_secret_configured=bool(setting('webhook_secret')),youtube_api_key_configured=bool(setting('youtube_api_key')),soundcloud_configured=bool(setting('soundcloud_client_id') and setting('soundcloud_client_secret')))

    @app.post('/api/admin/settings/test')
    @auth(admin=True)
    def test_mp():
        merchant=mp_request('/users/me')
        return jsonify(ok=True,account=merchant.get('nickname','Conta conectada'))

    @app.get('/sitemap.xml')
    def sitemap_xml():
        return seo_sitemap(db(), setting)

    @app.get('/robots.txt')
    def robots_txt():
        base = setting('public_url', 'https://flix.devspacey.com').rstrip('/')
        return Response('User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /admin\nDisallow: /conta\nDisallow: /lista\nDisallow: /data/\nSitemap: ' + base + '/sitemap.xml\n', content_type='text/plain; charset=utf-8')

    @app.get('/')
    @app.get('/<path:path>')
    def index(path=''):
        if path.startswith(('api/','data/','.')):
            raise APIError('Página não encontrada.',404)
        meta = metadata(db(), setting, path)
        html = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8')
        html = re.sub(r'<meta name="description"[^>]*>|<title>.*?</title>', '', html)
        html = html.replace('</head>', seo_head(meta) + '\n</head>')
        html = re.sub(r'<div id="app">.*?</div></div>', lambda _: '<div id="app">' + seo_fallback(meta) + '</div>', html, count=1)
        response = Response(html, status=200 if meta['public'] or path in ('conta','carteira','lista','continuar','historico') or path.startswith('admin') or path=='comunidade' or re.fullmatch(r'comunidade/espaco/[a-zA-Z0-9_]{3,30}',path) or re.fullmatch(r'comunidade/criar(?:/(?:post|reel|story|movie|series))?',path) or re.fullmatch(r'comunidade/(?:perfil/[a-zA-Z0-9_]{3,24}|(?:sala|post)/[A-Za-z0-9_-]{12})',path) or re.fullmatch(r'sala/[A-Za-z0-9_-]{12}',path) else 404, content_type='text/html; charset=utf-8')
        response.headers['Cache-Control'] = 'no-cache'
        if not meta['public']:
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    register_jump(app, db, auth, data, APIError, playback_item, public_user)
    register_community(app, db, auth, data, APIError)
    import community_experience
    import flix_music
    flix_music.register(app,db,auth,data,APIError,setting,save_setting)
    register_coupons(app, db, auth, data, APIError, rate_limit)
    register_playback_diagnostics(app, db, auth, data, APIError, playback_item)
    import flix_push
    flix_push.register(app)
    return app

def insert_content(db,item):
    keys=('id','title','kind','genre','year','rating','description','poster','backdrop','duration','video_url','featured','published','sample')
    db.execute('INSERT INTO content('+','.join(keys)+',created_at) VALUES('+','.join('?' for _ in range(len(keys)+1))+')',(*[item.get(k,'') for k in keys],time.time()))
