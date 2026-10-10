"""At most three streaming profiles per account. Billing and social identity stay account-wide."""
import secrets,time
from flask import g,jsonify,request

SCHEMA=[
'''CREATE TABLE IF NOT EXISTS account_profiles(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,avatar TEXT NOT NULL DEFAULT 'blue',slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 3),created_at REAL NOT NULL,UNIQUE(user_id,slot))''',
'''CREATE TABLE IF NOT EXISTS session_profiles(token TEXT PRIMARY KEY REFERENCES sessions(token) ON DELETE CASCADE,profile_id TEXT REFERENCES account_profiles(id) ON DELETE SET NULL)''',
'''CREATE TABLE IF NOT EXISTS profile_progress(profile_id TEXT REFERENCES account_profiles(id) ON DELETE CASCADE,content_id TEXT REFERENCES content(id) ON DELETE CASCADE,episode_id TEXT DEFAULT '',position REAL NOT NULL,duration REAL NOT NULL,updated_at REAL NOT NULL,client_time REAL NOT NULL,PRIMARY KEY(profile_id,content_id,episode_id))''',
'''CREATE TABLE IF NOT EXISTS profile_history(profile_id TEXT REFERENCES account_profiles(id) ON DELETE CASCADE,content_id TEXT REFERENCES content(id) ON DELETE CASCADE,watched_at REAL NOT NULL,PRIMARY KEY(profile_id,content_id))''',
'''CREATE TABLE IF NOT EXISTS profile_favorites(profile_id TEXT REFERENCES account_profiles(id) ON DELETE CASCADE,content_id TEXT REFERENCES content(id) ON DELETE CASCADE,PRIMARY KEY(profile_id,content_id))''',
'''CREATE INDEX IF NOT EXISTS idx_profile_history_content ON profile_history(content_id)''',
]

def migrate(db):
    for statement in SCHEMA:db.execute(statement)
    db.execute("INSERT INTO account_profiles(id,user_id,name,slot,created_at) SELECT id,id,SUBSTR(name,1,40),1,created_at FROM users WHERE 1 ON CONFLICT(id) DO NOTHING")
    db.execute('INSERT INTO profile_progress SELECT user_id,content_id,episode_id,position,duration,updated_at,client_time FROM progress WHERE 1 ON CONFLICT(profile_id,content_id,episode_id) DO NOTHING')
    db.execute('INSERT INTO profile_history SELECT user_id,content_id,watched_at FROM watch_history WHERE 1 ON CONFLICT(profile_id,content_id) DO NOTHING')
    db.execute('INSERT INTO profile_favorites SELECT user_id,content_id FROM favorites WHERE 1 ON CONFLICT(profile_id,content_id) DO NOTHING')
    db.commit()

def ensure(db,user):
    found=db.execute('SELECT id FROM account_profiles WHERE user_id=? ORDER BY slot LIMIT 1',(user['id'],)).fetchone()
    if found:return found[0]
    db.execute('INSERT INTO account_profiles(id,user_id,name,slot,created_at) VALUES(?,?,?,1,?) ON CONFLICT(user_id,slot) DO NOTHING',(user['id'],user['id'],user['name'][:40],time.time()))
    return db.execute('SELECT id FROM account_profiles WHERE user_id=? ORDER BY slot LIMIT 1',(user['id'],)).fetchone()[0]

def selected(db,uid,token):
    row=db.execute('SELECT p.* FROM account_profiles p JOIN session_profiles s ON s.profile_id=p.id WHERE p.user_id=? AND s.token=?',(uid,token)).fetchone()
    if not row:row=db.execute('SELECT * FROM account_profiles WHERE user_id=? ORDER BY slot LIMIT 1',(uid,)).fetchone()
    return dict(row) if row else None

def bind(db,token,profile_id):
    db.execute('INSERT INTO session_profiles VALUES(?,?) ON CONFLICT(token) DO UPDATE SET profile_id=excluded.profile_id',(token,profile_id))

def register(app,db,auth,data,error):
    def listing():return [dict(r) for r in db().execute('SELECT id,name,avatar,slot FROM account_profiles WHERE user_id=? ORDER BY slot',(g.user['id'],))]
    def values(d):
        name=str(d.get('name','')).strip();avatar=d.get('avatar','blue')
        if not 1<=len(name)<=40 or avatar not in ('blue','purple','green','orange','pink','cyan'):raise error('Use um nome de até 40 caracteres e escolha um avatar válido.')
        return name,avatar
    def owned(pid):
        row=db().execute('SELECT * FROM account_profiles WHERE id=? AND user_id=?',(pid,g.user['id'])).fetchone()
        if not row:raise error('Perfil não encontrado.',404)
        return row
    @app.get('/api/profiles')
    @auth()
    def account_profile_profiles():return jsonify(profiles=listing(),current_profile=g.profile,max_profiles=3)
    @app.post('/api/profiles')
    @auth()
    def account_profile_create():
        name,avatar=values(data());db().execute('BEGIN IMMEDIATE')
        used={r['slot'] for r in listing()}
        if len(used)>=3:raise error('Sua conta já tem três perfis. Edite ou remova um deles.',409)
        pid=secrets.token_hex(16);slot=next(n for n in range(1,4) if n not in used)
        db().execute('INSERT INTO account_profiles VALUES(?,?,?,?,?,?)',(pid,g.user['id'],name,avatar,slot,time.time()));db().commit()
        return jsonify(profile={'id':pid,'name':name,'avatar':avatar,'slot':slot}),201
    @app.patch('/api/profiles/<pid>')
    @auth()
    def account_profile_edit(pid):
        name,avatar=values(data());owned(pid)
        db().execute('UPDATE account_profiles SET name=?,avatar=? WHERE id=? AND user_id=?',(name,avatar,pid,g.user['id']));db().commit();return jsonify(ok=True)
    @app.delete('/api/profiles/<pid>')
    @auth()
    def account_profile_remove(pid):
        db().execute('BEGIN IMMEDIATE');owned(pid)
        if len(listing())<=1:raise error('Mantenha pelo menos um perfil na conta.',409)
        db().execute('DELETE FROM account_profiles WHERE id=? AND user_id=?',(pid,g.user['id']));db().commit();return jsonify(ok=True)
    @app.post('/api/profiles/<pid>/select')
    @auth()
    def account_profile_choose(pid):
        profile=owned(pid);bind(db(),g.session_token,pid);db().commit();return jsonify(profile=dict(profile))
