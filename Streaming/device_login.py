"""Device login: scanned token can approve only; the device secret can claim only.
Approval is explicit and authenticated. Both tokens expire and claims are atomic.
"""
import base64,hashlib,io,secrets,time
from urllib.parse import urlsplit
import qrcode
from qrcode.image.svg import SvgPathImage
from flask import g,jsonify,request
import auth_security

SCHEMA=[
'''CREATE TABLE IF NOT EXISTS device_logins(id TEXT PRIMARY KEY,device_hash TEXT NOT NULL UNIQUE,approval_hash TEXT NOT NULL UNIQUE,label TEXT NOT NULL,match_code TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',user_id TEXT REFERENCES users(id) ON DELETE CASCADE,profile_id TEXT REFERENCES account_profiles(id) ON DELETE SET NULL,mfa_verified INTEGER NOT NULL DEFAULT 0,approver_token TEXT REFERENCES sessions(token) ON DELETE CASCADE,created_at REAL NOT NULL,expires_at REAL NOT NULL)''',
'''CREATE INDEX IF NOT EXISTS idx_device_login_expires ON device_logins(expires_at)''',
]
def migrate(db):
    for statement in SCHEMA:db.execute(statement)
    db.commit()
def hashed(value):return hashlib.sha256(str(value).encode()).hexdigest()

def register(app,db,auth,data,error,rate_limit,session_response,setting):
    def cookie(response,value,max_age=300):
        response.set_cookie('worktv_device',value,max_age=max_age,httponly=True,secure=request.is_secure or setting('public_url').startswith('https://'),samesite='Lax',path='/api/auth/device')
        return response
    def target(token):
        value=str(token or '')
        if len(value)!=43:raise error('QR Code inválido ou expirado.',410)
        row=db().execute('SELECT * FROM device_logins WHERE approval_hash=? AND expires_at>?',(hashed(value),time.time())).fetchone()
        if not row or row['status']!='pending':raise error('Este QR Code expirou ou já foi utilizado. Gere outro no aparelho.',410)
        return row
    @app.post('/api/auth/device/start')
    def device_start():
        rate_limit();d=data();label='Smart TV' if d.get('kind')=='tv' else 'Computador ou navegador';device=secrets.token_urlsafe(32);approval=secrets.token_urlsafe(32);rid=secrets.token_hex(16);now=time.time();code=f'{secrets.randbelow(1000000):06d}'
        db().execute('DELETE FROM device_logins WHERE expires_at<?',(now-3600,))
        old=request.cookies.get('worktv_device')
        if old:db().execute('DELETE FROM device_logins WHERE device_hash=?',(hashed(old),))
        db().execute('INSERT INTO device_logins(id,device_hash,approval_hash,label,match_code,created_at,expires_at) VALUES(?,?,?,?,?,?,?)',(rid,hashed(device),hashed(approval),label,code,now,now+300));db().commit()
        origin=setting('public_url').rstrip('/') or request.host_url.rstrip('/')
        if urlsplit(origin).scheme not in ('http','https'):raise error('Endereço da plataforma indisponível.',503)
        url=origin+'/ativar#'+approval
        image=qrcode.make(url,image_factory=SvgPathImage,box_size=6,border=4);buffer=io.BytesIO();image.save(buffer)
        response=jsonify(id=rid,qr='data:image/svg+xml;base64,'+base64.b64encode(buffer.getvalue()).decode(),code=code,expires_in=300,activation_url=url)
        return cookie(response,device)
    @app.post('/api/auth/device/details')
    @auth()
    def device_details():
        row=target(data().get('token'));return jsonify(label=row['label'],code=row['match_code'],expires_at=row['expires_at'])
    @app.post('/api/auth/device/approve')
    @auth()
    def device_approve():
        d=data();db().execute('BEGIN IMMEDIATE');row=target(d.get('token'))
        if d.get('confirmed') is not True or not secrets.compare_digest(str(d.get('code','')),row['match_code']):raise error('Confirme o código exibido no aparelho para autorizar o acesso.',400)
        factor=auth_security.enabled(db(),g.user['id']);assured=auth_security.verified(db(),g.session_token)
        if factor and not assured:raise error('Entre novamente com seu autenticador antes de autorizar outro aparelho.',403)
        if app.config.get('ADMIN_MFA_REQUIRED') and g.user['role']=='admin' and not factor:raise error('Ative a verificação em duas etapas na sua conta antes de autorizar outro aparelho.',403)
        db().execute("UPDATE device_logins SET status='approved',user_id=?,profile_id=?,mfa_verified=?,approver_token=? WHERE id=? AND status='pending'",(g.user['id'],g.profile['id'],int(assured),g.session_token,row['id']));auth_security.event(db(),g.user['id'],'device_approved');db().commit();return jsonify(ok=True)
    @app.post('/api/auth/device/deny')
    @auth()
    def device_deny():
        row=target(data().get('token'));db().execute("UPDATE device_logins SET status='denied' WHERE id=? AND status='pending'",(row['id'],));db().commit();return jsonify(ok=True)
    @app.post('/api/auth/device/poll')
    def device_poll():
        d=data();secret=request.cookies.get('worktv_device','')
        if len(secret)!=43:raise error('O QR Code expirou. Gere outro para entrar.',410)
        store=app.extensions.get('security_store')
        if store:
            from redis.exceptions import RedisError
            try:allowed=store.allow('device-poll',[(secret,30)],60)
            except RedisError:raise error('O login está temporariamente indisponível.',503)
            if not allowed:raise error('Aguarde um instante antes de consultar este QR Code.',429)
        row=db().execute('SELECT * FROM device_logins WHERE id=? AND device_hash=?',(str(d.get('id','')),hashed(secret))).fetchone()
        if not row or row['expires_at']<=time.time():raise error('O QR Code expirou. Gere outro para entrar.',410)
        if row['status']=='pending':return jsonify(status='pending')
        if row['status']!='approved':return cookie(jsonify(status=row['status']),'',0)
        db().execute('BEGIN IMMEDIATE')
        claimed=db().execute("UPDATE device_logins SET status='claimed' WHERE id=? AND device_hash=? AND status='approved' AND expires_at>?",(row['id'],hashed(secret),time.time()))
        if claimed.rowcount!=1:raise error('Este QR Code já foi utilizado.',409)
        user=db().execute("SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE u.id=? AND u.status='active' AND s.token=? AND s.expires_at>?",(row['user_id'],row['approver_token'],time.time())).fetchone()
        if not user:raise error('Esta conta não está disponível.',403)
        # Revocation between approval and claim must also revoke the device grant.
        if auth_security.enabled(db(),user['id']) and not row['mfa_verified']:raise error('Gere outro QR Code após entrar com seu autenticador.',403)
        auth_security.event(db(),user['id'],'device_login')
        response=session_response(user,profile_id=row['profile_id'],mfa_verified=bool(row['mfa_verified']),status='approved')
        return cookie(response,'',0)
