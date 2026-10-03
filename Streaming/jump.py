"""FlixJump: persistent rooms, friendship requests and WebRTC signaling."""
import json
import math
import os
import re
import secrets
import sqlite3
import time
import uuid
from flask import g, jsonify, request
from werkzeug.security import generate_password_hash

PRESENCE = 45
ROOM_LIMIT = 8
REQUEST_TTL = 120


def username_for(db, value, name, error):
    if value is not None:
        value = str(value).strip().lower().lstrip('@')
        if not re.fullmatch(r'[a-z0-9_]{3,24}', value):
            raise error('Use um usuário de 3 a 24 caracteres: letras, números ou _.')
    else:
        stem = re.sub('[^a-z0-9_]', '', name.lower())[:16] or 'user'
        value = stem + '_' + secrets.token_hex(3)
    if db.execute('SELECT 1 FROM users WHERE username=?', (value,)).fetchone():
        raise error('Este nome de usuário já está em uso.', 409)
    return value


def migrate(db):
    if 'username' not in [r[1] for r in db.execute('PRAGMA table_info(users)')]:
        db.execute('ALTER TABLE users ADD COLUMN username TEXT COLLATE NOCASE')
    for row in db.execute('SELECT id,name FROM users WHERE username IS NULL').fetchall():
        db.execute('UPDATE users SET username=? WHERE id=?',
                   (username_for(db, None, row['name'], ValueError), row['id']))
    db.executescript('''
    CREATE UNIQUE INDEX IF NOT EXISTS idx_username ON users(username COLLATE NOCASE);
    CREATE TABLE IF NOT EXISTS jump_friends (
      sender TEXT REFERENCES users(id) ON DELETE CASCADE,
      recipient TEXT REFERENCES users(id) ON DELETE CASCADE,
      status TEXT NOT NULL DEFAULT 'pending', created_at REAL NOT NULL,
      PRIMARY KEY(sender,recipient), CHECK(sender <> recipient));
    CREATE TABLE IF NOT EXISTS jump_rooms (
      id TEXT PRIMARY KEY, host_id TEXT REFERENCES users(id) ON DELETE CASCADE,
      content_id TEXT REFERENCES content(id) ON DELETE CASCADE,
      episode_id TEXT NOT NULL DEFAULT '', position REAL NOT NULL DEFAULT 0,
      paused INTEGER NOT NULL DEFAULT 1, updated_at REAL NOT NULL,
      revision INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS jump_members (
      room_id TEXT REFERENCES jump_rooms(id) ON DELETE CASCADE,
      user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
      joined_at REAL NOT NULL, seen_at REAL NOT NULL, mic INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(room_id,user_id));
    CREATE TABLE IF NOT EXISTS jump_messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      room_id TEXT REFERENCES jump_rooms(id) ON DELETE CASCADE,
      user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
      body TEXT NOT NULL, created_at REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_jump_messages ON jump_messages(room_id,id);
    CREATE INDEX IF NOT EXISTS idx_jump_members_seen ON jump_members(seen_at);
    CREATE TABLE IF NOT EXISTS jump_invites (
      room_id TEXT REFERENCES jump_rooms(id) ON DELETE CASCADE,
      user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
      PRIMARY KEY(room_id,user_id));
    CREATE TABLE IF NOT EXISTS jump_requests (
      room_id TEXT REFERENCES jump_rooms(id) ON DELETE CASCADE,
      user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
      status TEXT NOT NULL DEFAULT 'pending', created_at REAL NOT NULL,
      seen_at REAL NOT NULL, PRIMARY KEY(room_id,user_id));
    CREATE INDEX IF NOT EXISTS idx_jump_requests ON jump_requests(room_id,status,seen_at);
    CREATE TABLE IF NOT EXISTS jump_signals (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      room_id TEXT REFERENCES jump_rooms(id) ON DELETE CASCADE,
      sender TEXT REFERENCES users(id) ON DELETE CASCADE,
      recipient TEXT REFERENCES users(id) ON DELETE CASCADE,
      payload TEXT NOT NULL, created_at REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_jump_signals ON jump_signals(room_id,recipient,id);
    CREATE INDEX IF NOT EXISTS idx_jump_signals_created ON jump_signals(created_at);
    ''')

    if 'camera' not in {r[1] for r in db.execute('PRAGMA table_info(jump_members)')}:db.execute('ALTER TABLE jump_members ADD COLUMN camera INTEGER NOT NULL DEFAULT 0')
    columns={r[1] for r in db.execute('PRAGMA table_info(jump_rooms)')}
    if 'permanent' not in columns:db.execute('ALTER TABLE jump_rooms ADD COLUMN permanent INTEGER NOT NULL DEFAULT 0')


def register_jump(app, db, auth, data, error, playback_item, public_user):
    def transaction():
        # Serialize read/check/write operations, including capacity and host elections.
        db().execute('BEGIN IMMEDIATE')

    def cleanup():
        now = time.time()
        for r in db().execute("SELECT r.*,m.seen_at FROM jump_rooms r LEFT JOIN jump_members m ON m.room_id=r.id AND m.user_id=r.host_id WHERE r.permanent=1 AND r.paused=0 AND (m.user_id IS NULL OR m.seen_at<?)",(now-PRESENCE,)).fetchall():
            end=min(now,r['seen_at']+PRESENCE) if r['seen_at'] else now
            db().execute('UPDATE jump_rooms SET paused=1,position=?,revision=revision+1,updated_at=? WHERE id=?',(r['position']+max(0,end-r['updated_at']),now,r['id']))
        db().execute('DELETE FROM jump_members WHERE seen_at<? OR user_id IN (SELECT id FROM users WHERE status!=\'active\' OR (role!=\'admin\' AND expires_at<=?))', (now-PRESENCE, now))
        db().execute('DELETE FROM jump_rooms WHERE permanent=0 AND NOT EXISTS (SELECT 1 FROM jump_members m WHERE m.room_id=jump_rooms.id)')
        db().execute('DELETE FROM jump_signals WHERE created_at<?', (now-90,))
        db().execute("UPDATE jump_requests SET status='expired' WHERE status IN ('pending','approved') AND (seen_at<? OR user_id IN (SELECT id FROM users WHERE status!='active' OR (role!='admin' AND expires_at<=?)))", (now-REQUEST_TTL,now))
        for room in db().execute('SELECT * FROM jump_rooms WHERE permanent=0 AND NOT EXISTS (SELECT 1 FROM jump_members m WHERE m.room_id=jump_rooms.id AND m.user_id=jump_rooms.host_id)').fetchall():
            host = db().execute('SELECT user_id FROM jump_members WHERE room_id=? ORDER BY joined_at,user_id LIMIT 1', (room['id'],)).fetchone()
            if host:
                db().execute('UPDATE jump_rooms SET host_id=?,revision=revision+1 WHERE id=?', (host[0], room['id']))

    def room_for(rid, member=True):
        room = db().execute('SELECT * FROM jump_rooms WHERE id=?', (rid,)).fetchone()
        if not room:
            raise error('Esta sala foi encerrada ou o código é inválido.', 404)
        if member and not db().execute('SELECT 1 FROM jump_members WHERE room_id=? AND user_id=?', (rid,g.user['id'])).fetchone():
            raise error('Entre na sala para participar.', 403)
        playback_item(room['content_id'], room['episode_id'])
        return room

    def snapshot(rid):
        room = dict(room_for(rid))
        room['server_time'] = time.time()
        room['requests'] = [dict(r) for r in db().execute("SELECT u.id,u.name,u.username,q.created_at FROM jump_requests q JOIN users u ON u.id=q.user_id WHERE q.room_id=? AND q.status='pending' ORDER BY q.created_at,u.id", (rid,))] if room['host_id']==g.user['id'] else []
        room['members'] = [dict(r) for r in db().execute('SELECT u.id,u.name,u.username,m.mic,m.camera FROM jump_members m JOIN users u ON u.id=m.user_id WHERE m.room_id=? ORDER BY m.joined_at,u.id', (rid,))]
        room['messages'] = [dict(r) for r in db().execute('SELECT m.id,m.user_id,u.name,u.username,m.body,m.created_at FROM jump_messages m JOIN users u ON u.id=m.user_id WHERE room_id=? ORDER BY m.id DESC LIMIT 60', (rid,))][::-1]
        return room

    def limited(table, where, args, maximum, seconds):
        count = db().execute(f'SELECT COUNT(*) FROM {table} WHERE {where} AND created_at>?', (*args,time.time()-seconds)).fetchone()[0]
        if count >= maximum:
            raise error('Muitas solicitações. Aguarde um momento.', 429)

    @app.post('/api/admin/users')
    @auth(admin=True)
    def create_user():
        d = data()
        name, email, password = str(d.get('name','')).strip(), str(d.get('email','')).strip().lower(), str(d.get('password',''))
        if not 2 <= len(name) <= 100 or len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise error('Preencha seu nome e um e-mail válido.')
        if not 10 <= len(password) <= 128:
            raise error('Use uma senha entre 10 e 128 caracteres.')
        transaction()
        username = username_for(db(), d.get('username'), name, error)
        plan_id = d.get('plan_id') or None
        plan = db().execute('SELECT * FROM plans WHERE id=? AND active=1', (plan_id,)).fetchone() if plan_id else None
        if plan_id and not plan:
            raise error('Selecione um plano disponível.')
        expires = float(d.get('expires_at') or (time.time()+plan['days']*86400 if plan else 0))
        if not math.isfinite(expires) or expires < 0 or (expires and not plan):
            raise error('Informe um plano para definir a validade do acesso.')
        uid = uuid.uuid4().hex
        try:
            db().execute('INSERT INTO users(id,name,username,email,password,plan_id,expires_at,created_at) VALUES(?,?,?,?,?,?,?,?)', (uid,name,username,email,generate_password_hash(password),plan_id,expires,time.time()))
        except sqlite3.IntegrityError:
            raise error('E-mail ou nome de usuário já cadastrado.',409)
        db().commit()
        return jsonify(user=public_user(db().execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())),201

    @app.patch('/api/social/profile')
    @auth()
    def profile():
        d = data()
        if str(d.get('username','')).strip().lower().lstrip('@') == g.user['username']:
            return jsonify(username=g.user['username'])
        transaction()
        value = username_for(db(), d.get('username',''), g.user['name'], error)
        db().execute('UPDATE users SET username=? WHERE id=?', (value,g.user['id']))
        db().commit()
        return jsonify(username=value)

    @app.get('/api/social')
    @auth()
    def social():
        transaction()
        cleanup()
        uid = g.user['id']
        friends = [dict(r) for r in db().execute('SELECT u.id,u.name,u.username,f.sender,f.status FROM jump_friends f JOIN users u ON u.id=CASE WHEN f.sender=? THEN f.recipient ELSE f.sender END WHERE (f.sender=? OR f.recipient=?) AND u.status=\'active\' ORDER BY u.name', (uid,uid,uid))]
        invites = [dict(r) for r in db().execute('SELECT r.id,c.title,u.name AS host_name FROM jump_invites i JOIN jump_rooms r ON r.id=i.room_id JOIN content c ON c.id=r.content_id JOIN users u ON u.id=r.host_id WHERE i.user_id=? AND c.published=1',(uid,))]
        db().commit()
        return jsonify(friends=friends,invites=invites)

    @app.post('/api/social/friends')
    @auth()
    def add_friend():
        value = str(data().get('username','')).strip().lower().lstrip('@')
        transaction()
        other = db().execute('SELECT id FROM users WHERE username=? AND status=\'active\'', (value,)).fetchone()
        if not other or other['id']==g.user['id']:
            raise error('Informe o nome de usuário de outra pessoa.',404)
        uid, oid = g.user['id'],other['id']
        if db().execute('SELECT 1 FROM jump_friends WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?)',(uid,oid,oid,uid)).fetchone():
            raise error('Já existe uma amizade ou solicitação entre vocês.',409)
        limited('jump_friends','sender=?',(uid,),30,3600)
        db().execute('INSERT INTO jump_friends VALUES(?,?,\'pending\',?)',(uid,oid,time.time()))
        db().commit()
        return jsonify(ok=True),201

    @app.route('/api/social/friends/<uid>',methods=['PATCH','DELETE'])
    @auth()
    def change_friend(uid):
        transaction()
        me=g.user['id']
        if request.method=='DELETE':
            db().execute('DELETE FROM jump_friends WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?)',(me,uid,uid,me))
        elif not db().execute('UPDATE jump_friends SET status=\'accepted\' WHERE sender=? AND recipient=? AND status=\'pending\'',(uid,me)).rowcount:
            raise error('Solicitação não encontrada.',404)
        db().commit()
        return jsonify(ok=True)

    @app.get('/api/jump/config')
    @auth(paid=True)
    def config():
        # Optional STUN/TURN configuration is supplied by the deployment, never by a room.
        return jsonify(ice_servers=json.loads(os.getenv('FLIXJUMP_ICE_SERVERS','[{"urls":"stun:stun.l.google.com:19302"}]')),max_members=ROOM_LIMIT)

    @app.post('/api/jump/rooms')
    @auth(paid=True)
    def create_room():
        d=data()
        cid,eid=str(d.get('content_id','')),str(d.get('episode_id',''))
        _,video=playback_item(cid,eid)
        if not video:
            raise error('Este conteúdo ainda não tem vídeo disponível.',404)
        pos=float(d.get('position',0))
        if not math.isfinite(pos) or not 0<=pos<=604800:
            raise error('Posição inválida.')
        transaction()
        cleanup()
        if db().execute('SELECT COUNT(*) FROM jump_rooms WHERE host_id=?',(g.user['id'],)).fetchone()[0]>=3:
            raise error('Encerre uma de suas salas antes de criar outra.',429)
        rid=secrets.token_urlsafe(9)
        now=time.time()
        db().execute('INSERT INTO jump_rooms(id,host_id,content_id,episode_id,position,paused,updated_at,created_at) VALUES(?,?,?,?,?,?,?,?)',(rid,g.user['id'],cid,eid,pos,int(bool(d.get('paused',True))),now,now))
        db().execute('UPDATE jump_rooms SET permanent=? WHERE id=?',(int(d.get('permanent') is True),rid))
        db().execute('INSERT INTO jump_members(room_id,user_id,joined_at,seen_at,mic) VALUES(?,?,?,?,0)',(rid,g.user['id'],now,now))
        result=snapshot(rid)
        db().commit()
        return jsonify(room=result),201

    @app.post('/api/jump/rooms/<rid>/join')
    @auth(paid=True)
    def join(rid):
        transaction()
        cleanup()
        r=room_for(rid,False)
        uid,now=g.user['id'],time.time()
        exists=db().execute('SELECT 1 FROM jump_members WHERE room_id=? AND user_id=?',(rid,uid)).fetchone()
        if exists:
            db().execute('UPDATE jump_members SET seen_at=? WHERE room_id=? AND user_id=?',(now,rid,uid))
            result=snapshot(rid)
            db().commit()
            return jsonify(room=result)
        entry=db().execute('SELECT * FROM jump_requests WHERE room_id=? AND user_id=?',(rid,uid)).fetchone()
        if entry and entry['status']=='rejected':
            db().commit()
            return jsonify(status='rejected')
        if db().execute('SELECT COUNT(*) FROM jump_members WHERE room_id=?',(rid,)).fetchone()[0]>=ROOM_LIMIT:
            raise error('Esta sala está cheia (até 8 pessoas).',409)
        if r['host_id']==uid or (entry and entry['status']=='approved'):
            db().execute('INSERT INTO jump_members(room_id,user_id,joined_at,seen_at,mic) VALUES(?,?,?,?,0)',(rid,uid,now,now))
            db().execute("UPDATE jump_requests SET status='joined',seen_at=? WHERE room_id=? AND user_id=?",(now,rid,uid))
            result=snapshot(rid)
            db().commit()
            return jsonify(room=result)
        if not entry or entry['status']!='pending':
            if db().execute("SELECT COUNT(*) FROM jump_requests WHERE room_id=? AND status='pending'",(rid,)).fetchone()[0]>=32:
                raise error('Há muitas solicitações nesta sala. Tente novamente em instantes.',429)
            if not entry:
                limited('jump_requests','user_id=?',(uid,),30,3600)
            db().execute("INSERT INTO jump_requests VALUES(?,?,'pending',?,?) ON CONFLICT(room_id,user_id) DO UPDATE SET status='pending',created_at=excluded.created_at,seen_at=excluded.seen_at",(rid,uid,now,now))
        else:
            db().execute('UPDATE jump_requests SET seen_at=? WHERE room_id=? AND user_id=?',(now,rid,uid))
        db().commit()
        # No room state, messages or peer information is exposed before acceptance.
        return jsonify(status='pending'),202

    @app.delete('/api/jump/rooms/<rid>/join')
    @auth()
    def cancel_entry(rid):
        db().execute("UPDATE jump_requests SET status='cancelled' WHERE room_id=? AND user_id=? AND status IN ('pending','approved')",(rid,g.user['id']))
        db().commit()
        return jsonify(ok=True)

    @app.patch('/api/jump/rooms/<rid>/requests/<uid>')
    @auth(paid=True)
    def review_entry(rid,uid):
        decision=data().get('decision')
        if decision not in ('approve','reject'):
            raise error('Escolha aceitar ou recusar a solicitação.')
        transaction()
        cleanup()
        if room_for(rid)['host_id']!=g.user['id']:
            raise error('Somente o anfitrião pode aceitar ou recusar participantes.',403)
        entry=db().execute("SELECT 1 FROM jump_requests WHERE room_id=? AND user_id=? AND status='pending'",(rid,uid)).fetchone()
        if not entry:
            raise error('Esta solicitação não está mais pendente.',409)
        if decision=='approve':
            members=db().execute('SELECT COUNT(*) FROM jump_members WHERE room_id=?',(rid,)).fetchone()[0]
            reserved=db().execute("SELECT COUNT(*) FROM jump_requests WHERE room_id=? AND status='approved'",(rid,)).fetchone()[0]
            if members+reserved>=ROOM_LIMIT:
                raise error('Esta sala está cheia ou suas vagas já foram reservadas.',409)
        db().execute('UPDATE jump_requests SET status=? WHERE room_id=? AND user_id=?',('approved' if decision=='approve' else 'rejected',rid,uid))
        result=snapshot(rid)
        db().commit()
        return jsonify(room=result)

    @app.post('/api/jump/rooms/<rid>/poll')
    @auth(paid=True)
    def poll(rid):
        d=data()
        cursor=max(0,int(d.get('cursor',0)))
        transaction()
        cleanup()
        room_for(rid)
        db().execute('UPDATE jump_members SET seen_at=? WHERE room_id=? AND user_id=?',(time.time(),rid,g.user['id']))
        if isinstance(d.get('mic'),bool):
            db().execute('UPDATE jump_members SET mic=? WHERE room_id=? AND user_id=?',(int(d['mic']),rid,g.user['id']))
        result=snapshot(rid)
        signals=[dict(r) for r in db().execute('SELECT id,sender,payload FROM jump_signals WHERE room_id=? AND recipient=? AND id>? ORDER BY id LIMIT 100',(rid,g.user['id'],cursor))]
        for s in signals:
            s['payload']=json.loads(s['payload'])
        db().commit()
        return jsonify(room=result,signals=signals)

    @app.patch('/api/jump/rooms/<rid>/playback')
    @auth(paid=True)
    def playback(rid):
        d=data()
        transaction()
        cleanup()
        room=room_for(rid)
        if room['host_id']!=g.user['id']:
            raise error('Somente o anfitrião controla a reprodução.',403)
        if int(d.get('revision',-1))!=room['revision']:
            raise error('O estado da sala mudou. Sincronizando novamente.',409)
        pos=float(d.get('position',0))
        live=db().execute('SELECT kind FROM content WHERE id=?',(room['content_id'],)).fetchone()[0]=='channel'
        limit=time.time()+300 if live else 604800
        if not math.isfinite(pos) or not 0<=pos<=limit or not isinstance(d.get('paused'),bool):
            raise error('Estado de reprodução inválido.')
        db().execute('UPDATE jump_rooms SET position=?,paused=?,updated_at=?,revision=revision+1 WHERE id=?',(pos,int(d['paused']),time.time(),rid))
        result=snapshot(rid)
        db().commit()
        return jsonify(room=result)

    @app.post('/api/jump/rooms/<rid>/messages')
    @auth(paid=True)
    def message(rid):
        body=str(data().get('body','')).strip()
        if not 1<=len(body)<=1000:
            raise error('Escreva uma mensagem de até 1.000 caracteres.')
        transaction()
        cleanup()
        room_for(rid)
        limited('jump_messages','user_id=?',(g.user['id'],),12,10)
        db().execute('INSERT INTO jump_messages(room_id,user_id,body,created_at) VALUES(?,?,?,?)',(rid,g.user['id'],body,time.time()))
        db().execute('DELETE FROM jump_messages WHERE room_id=? AND id NOT IN (SELECT id FROM jump_messages WHERE room_id=? ORDER BY id DESC LIMIT 200)',(rid,rid))
        db().commit()
        return jsonify(ok=True),201

    @app.post('/api/jump/rooms/<rid>/invite')
    @auth(paid=True)
    def invite(rid):
        uid=str(data().get('user_id',''))
        transaction()
        cleanup()
        room_for(rid)
        me=g.user['id']
        if not db().execute('SELECT 1 FROM jump_friends WHERE status=\'accepted\' AND ((sender=? AND recipient=?) OR (sender=? AND recipient=?))',(me,uid,uid,me)).fetchone():
            raise error('Adicione esta pessoa aos amigos primeiro.',403)
        db().execute('INSERT OR IGNORE INTO jump_invites VALUES(?,?)',(rid,uid))
        db().commit()
        return jsonify(ok=True)

    @app.patch('/api/jump/rooms/<rid>/mic')
    @auth(paid=True)
    def mic(rid):
        enabled=data().get('enabled')
        if not isinstance(enabled,bool):
            raise error('Estado do microfone inválido.')
        transaction()
        cleanup()
        room_for(rid)
        db().execute('UPDATE jump_members SET mic=? WHERE room_id=? AND user_id=?',(int(enabled),rid,g.user['id']))
        db().commit()
        return jsonify(ok=True)

    @app.patch('/api/jump/rooms/<rid>/camera')
    @auth(paid=True)
    def camera(rid):
        enabled=data().get('enabled')
        if type(enabled) is not bool:raise error('Estado de câmera inválido.')
        transaction();cleanup();room_for(rid)
        if enabled and db().execute('SELECT COUNT(*) FROM jump_members WHERE room_id=? AND camera=1 AND user_id!=?',(rid,g.user['id'])).fetchone()[0]>=4:raise error('Esta sessão já tem quatro câmeras ligadas.',409)
        db().execute('UPDATE jump_members SET camera=?,seen_at=? WHERE room_id=? AND user_id=?',(int(enabled),time.time(),rid,g.user['id']));result=snapshot(rid);db().commit();return jsonify(room=result)

    @app.post('/api/jump/rooms/<rid>/signals')
    @auth(paid=True)
    def signal(rid):
        d=data()
        payload=d.get('payload')
        if not isinstance(payload,dict) or payload.get('type') not in ('offer','answer','candidate') or len(json.dumps(payload))>20000:
            raise error('Sinal de voz inválido.')
        transaction()
        cleanup()
        room_for(rid)
        recipient=str(d.get('recipient',''))
        if recipient==g.user['id'] or not db().execute('SELECT 1 FROM jump_members WHERE room_id=? AND user_id=?',(rid,recipient)).fetchone():
            raise error('Participante não encontrado.',404)
        limited('jump_signals','sender=?',(g.user['id'],),500,60)
        db().execute('INSERT INTO jump_signals(room_id,sender,recipient,payload,created_at) VALUES(?,?,?,?,?)',(rid,g.user['id'],recipient,json.dumps(payload),time.time()))
        db().commit()
        return jsonify(ok=True)

    @app.post('/api/jump/rooms/<rid>/leave')
    @auth()
    def leave(rid):
        transaction()
        db().execute('DELETE FROM jump_members WHERE room_id=? AND user_id=?',(rid,g.user['id']))
        db().execute('DELETE FROM jump_signals WHERE room_id=? AND (sender=? OR recipient=?)',(rid,g.user['id'],g.user['id']))
        cleanup()
        db().commit()
        return jsonify(ok=True)

    @app.patch('/api/jump/rooms/<rid>/settings')
    @auth(paid=True)
    def jump_settings(rid):
        d=data();transaction();cleanup();r=room_for(rid)
        if r['host_id']!=g.user['id']:raise error('Somente o anfitrião pode alterar a sala.',403)
        if not isinstance(d.get('permanent'),bool):raise error('Escolha a duração da sala.')
        db().execute('UPDATE jump_rooms SET permanent=?,revision=revision+1 WHERE id=?',(int(d['permanent']),rid));result=snapshot(rid);db().commit();return jsonify(room=result)

    @app.delete('/api/jump/rooms/<rid>')
    @auth(paid=True)
    def close_room(rid):
        transaction()
        if room_for(rid)['host_id']!=g.user['id']:
            raise error('Somente o anfitrião pode encerrar a sala.',403)
        db().execute('DELETE FROM jump_rooms WHERE id=?',(rid,))
        db().commit()
        return jsonify(ok=True)
