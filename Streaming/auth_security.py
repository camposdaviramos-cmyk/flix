"""TOTP, one-time recovery codes and account security events."""
import hashlib,hmac,json,secrets,time
import pyotp
from flask import g,jsonify,request
from werkzeug.security import check_password_hash

SCHEMA=[
'''CREATE TABLE IF NOT EXISTS account_mfa(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,secret TEXT NOT NULL,last_step INTEGER NOT NULL DEFAULT -1,enabled_at REAL NOT NULL)''',
'''CREATE TABLE IF NOT EXISTS mfa_pending(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,secret TEXT NOT NULL,expires_at REAL NOT NULL)''',
'''CREATE TABLE IF NOT EXISTS mfa_recovery(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,code_hash TEXT NOT NULL,PRIMARY KEY(user_id,code_hash))''',
'''CREATE TABLE IF NOT EXISTS session_assurance(token TEXT PRIMARY KEY REFERENCES sessions(token) ON DELETE CASCADE,mfa_verified INTEGER NOT NULL DEFAULT 0)''',
'''CREATE TABLE IF NOT EXISTS security_events(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,kind TEXT NOT NULL,created_at REAL NOT NULL,ip_hash TEXT NOT NULL)''',
'''CREATE INDEX IF NOT EXISTS idx_security_events_owner ON security_events(user_id,created_at)''',
]
def migrate(db):
    for statement in SCHEMA:db.execute(statement)
    db.commit()
def event(db,uid,kind):
    peer=request.remote_addr or 'unknown'
    db.execute('INSERT INTO security_events VALUES(?,?,?,?,?)',(secrets.token_hex(16),uid,kind,time.time(),hashlib.sha256(peer.encode()).hexdigest()))
def enabled(db,uid):return bool(db.execute('SELECT 1 FROM account_mfa WHERE user_id=?',(uid,)).fetchone())
def verified(db,token):
    row=db.execute('SELECT mfa_verified FROM session_assurance WHERE token=?',(token,)).fetchone();return bool(row and row[0])
def bind(db,token,assured):db.execute('INSERT INTO session_assurance VALUES(?,?) ON CONFLICT(token) DO UPDATE SET mfa_verified=excluded.mfa_verified',(token,int(assured)))
def consume(db,uid,code,cipher):
    value=str(code or '').strip().replace('-','').replace(' ','').upper()
    row=db.execute('SELECT secret,last_step FROM account_mfa WHERE user_id=?',(uid,)).fetchone()
    if not row:return False
    if len(value)==6 and value.isdigit():
        totp=pyotp.TOTP(cipher.decrypt(row['secret'].encode()).decode());now=int(time.time()//30)
        for step in (now,now-1,now+1):
            if step>row['last_step'] and hmac.compare_digest(totp.at(step*30),value):
                result=db.execute('UPDATE account_mfa SET last_step=? WHERE user_id=? AND last_step<?',(step,uid,step))
                return result.rowcount==1
        return False
    if len(value)!=20:return False
    result=db.execute('DELETE FROM mfa_recovery WHERE user_id=? AND code_hash=?',(uid,hashlib.sha256(value.encode()).hexdigest()))
    return result.rowcount==1

def register(app,db,auth,data,error,cipher,rate_limit):
    def password(d):
        value=str(d.get('password',''))
        if len(value)>128 or not check_password_hash(g.user['password'],value):raise error('Senha atual incorreta.',401)
    @app.get('/api/auth/security')
    @auth()
    def account_security_status():
        return jsonify(mfa_enabled=enabled(db(),g.user['id']),mfa_required=bool(app.config.get('ADMIN_MFA_REQUIRED') and g.user['role']=='admin'),recovery_codes=db().execute('SELECT COUNT(*) FROM mfa_recovery WHERE user_id=?',(g.user['id'],)).fetchone()[0],events=[dict(r) for r in db().execute('SELECT kind,created_at FROM security_events WHERE user_id=? ORDER BY created_at DESC LIMIT 20',(g.user['id'],))])
    @app.post('/api/auth/mfa/setup')
    @auth()
    def account_security_setup():
        rate_limit();d=data();password(d);db().execute('BEGIN IMMEDIATE')
        if enabled(db(),g.user['id']) and not consume(db(),g.user['id'],d.get('code'),cipher):raise error('Informe um código válido do autenticador ou de recuperação.',401)
        secret=pyotp.random_base32();encrypted=cipher.encrypt(secret.encode()).decode()
        db().execute('INSERT INTO mfa_pending VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET secret=excluded.secret,expires_at=excluded.expires_at',(g.user['id'],encrypted,time.time()+600));db().commit()
        return jsonify(secret=secret,uri=pyotp.TOTP(secret).provisioning_uri(name=g.user['email'],issuer_name='WorkTV'),expires_in=600)
    @app.post('/api/auth/mfa/enable')
    @auth()
    def account_security_enable():
        rate_limit();d=data();db().execute('BEGIN IMMEDIATE');pending=db().execute('SELECT * FROM mfa_pending WHERE user_id=? AND expires_at>?',(g.user['id'],time.time())).fetchone()
        if not pending:raise error('A configuração expirou. Comece novamente.',410)
        secret=cipher.decrypt(pending['secret'].encode()).decode();code=str(d.get('code','')).strip()
        if not pyotp.TOTP(secret).verify(code,valid_window=1):raise error('Código inválido. Confira o aplicativo autenticador.',400)
        now=time.time();db().execute('INSERT INTO account_mfa VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET secret=excluded.secret,last_step=excluded.last_step,enabled_at=excluded.enabled_at',(g.user['id'],pending['secret'],int(now//30)+int(pyotp.TOTP(secret).at((int(now//30)+1)*30)==code),now))
        codes=[secrets.token_hex(10).upper() for _ in range(10)]
        db().execute('DELETE FROM mfa_recovery WHERE user_id=?',(g.user['id'],));db().executemany('INSERT INTO mfa_recovery VALUES(?,?)',[(g.user['id'],hashlib.sha256(c.encode()).hexdigest()) for c in codes])
        db().execute('DELETE FROM mfa_pending WHERE user_id=?',(g.user['id'],));db().execute('DELETE FROM sessions WHERE user_id=? AND token!=?',(g.user['id'],g.session_token));bind(db(),g.session_token,True);event(db(),g.user['id'],'mfa_enabled');db().commit()
        return jsonify(recovery_codes=['-'.join(c[i:i+5] for i in range(0,20,5)) for c in codes])
    @app.post('/api/auth/mfa/disable')
    @auth()
    def account_security_disable():
        rate_limit();d=data();password(d)
        if app.config.get('ADMIN_MFA_REQUIRED') and g.user['role']=='admin':raise error('Administradores precisam manter a verificação em duas etapas ativa. Use a opção de trocar autenticador.',403)
        db().execute('BEGIN IMMEDIATE')
        if not consume(db(),g.user['id'],d.get('code'),cipher):raise error('Código inválido ou já utilizado.',401)
        db().execute('DELETE FROM mfa_pending WHERE user_id=?',(g.user['id'],));db().execute('DELETE FROM account_mfa WHERE user_id=?',(g.user['id'],));db().execute('DELETE FROM mfa_recovery WHERE user_id=?',(g.user['id'],));db().execute('DELETE FROM sessions WHERE user_id=? AND token!=?',(g.user['id'],g.session_token));bind(db(),g.session_token,False);event(db(),g.user['id'],'mfa_disabled');db().commit();return jsonify(ok=True)
