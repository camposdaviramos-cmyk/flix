"""Room privacy, independent soundtrack, polls and administrator-installed plugins."""
import json
import math
import secrets
import time
import re
import hashlib
from urllib.parse import urlsplit, urlencode
from flask import g, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
import flix_wallet


def migrate(db):
    cols={r[1] for r in db.execute('PRAGMA table_info(community_rooms)')}
    for name,definition in {'privacy':"TEXT NOT NULL DEFAULT 'public'",'password_hash':"TEXT NOT NULL DEFAULT ''",'activity':"TEXT NOT NULL DEFAULT ''",'layout_revision':'INTEGER NOT NULL DEFAULT 1','media_epoch':'INTEGER NOT NULL DEFAULT 1'}.items():
        if name not in cols:db.execute(f'ALTER TABLE community_rooms ADD COLUMN {name} {definition}')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS room_password_attempts(room_id TEXT,user_id TEXT,at REAL);
    CREATE INDEX IF NOT EXISTS room_password_limit ON room_password_attempts(room_id,user_id,at);
    CREATE TABLE IF NOT EXISTS room_audio(room_id TEXT PRIMARY KEY REFERENCES community_rooms(id) ON DELETE CASCADE,current_id INTEGER,position REAL NOT NULL DEFAULT 0,paused INTEGER NOT NULL DEFAULT 1,revision INTEGER NOT NULL DEFAULT 1,updated_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS room_audio_queue(id INTEGER PRIMARY KEY AUTOINCREMENT,room_id TEXT NOT NULL REFERENCES community_rooms(id) ON DELETE CASCADE,user_id TEXT NOT NULL REFERENCES users(id),title TEXT NOT NULL,url TEXT NOT NULL,media_type TEXT NOT NULL,created_at REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS room_audio_items ON room_audio_queue(room_id,id);
    CREATE TABLE IF NOT EXISTS room_polls(id TEXT PRIMARY KEY,room_id TEXT NOT NULL REFERENCES community_rooms(id) ON DELETE CASCADE,question TEXT NOT NULL,options TEXT NOT NULL,closed INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS room_votes(poll_id TEXT NOT NULL REFERENCES room_polls(id) ON DELETE CASCADE,user_id TEXT NOT NULL REFERENCES users(id),choice INTEGER NOT NULL,PRIMARY KEY(poll_id,user_id));
    CREATE TABLE IF NOT EXISTS room_plugin_sessions(room_id TEXT PRIMARY KEY REFERENCES community_rooms(id) ON DELETE CASCADE,id TEXT NOT NULL UNIQUE,plugin_id TEXT NOT NULL REFERENCES room_plugins(id),coins INTEGER NOT NULL,revision INTEGER NOT NULL DEFAULT 1,state TEXT NOT NULL DEFAULT '{}',created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS room_plugin_players(session_id TEXT NOT NULL REFERENCES room_plugin_sessions(id) ON DELETE CASCADE,user_id TEXT NOT NULL REFERENCES users(id),joined_at REAL NOT NULL,PRIMARY KEY(session_id,user_id));
    CREATE TABLE IF NOT EXISTS room_plugin_events(id INTEGER PRIMARY KEY AUTOINCREMENT,session_id TEXT NOT NULL REFERENCES room_plugin_sessions(id) ON DELETE CASCADE,user_id TEXT NOT NULL REFERENCES users(id),payload TEXT NOT NULL,created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS room_music_hearts(user_id TEXT REFERENCES users(id),track_id TEXT REFERENCES music_tracks(id),reactor TEXT REFERENCES users(id),PRIMARY KEY(user_id,track_id,reactor));
    ''')
    if 'track_id' not in {r[1] for r in db.execute('PRAGMA table_info(room_audio_queue)')}:
        db.execute('ALTER TABLE room_audio_queue ADD COLUMN track_id TEXT REFERENCES music_tracks(id)')


def options(db,rid,d,error,creating=False):
    r=db.execute('SELECT * FROM community_rooms WHERE id=?',(rid,)).fetchone()
    privacy=d.get('privacy',r['privacy'])
    if privacy not in ('public','private','password'):raise error('Escolha sala pública, privada ou com senha.')
    password=str(d.get('password',''));hashed=r['password_hash']
    if password:
        if not 4<=len(password)<=128:raise error('A senha da sala deve ter entre 4 e 128 caracteres.')
        hashed=generate_password_hash(password)
    if privacy=='password' and not hashed:raise error('Defina uma senha para esta sala.')
    if privacy!='password':hashed=''
    activity=d.get('activity') or (r['activity'] if not creating else '') or r['kind']
    modes={'movie':'watch','series':'watch','tv':'watch','watch':'watch','games':'voice','voice':'voice','video':'video','live':'live','music':'music'}
    if activity not in modes:raise error('Atividade de sala inválida.')
    kind=modes[activity];changed=kind!=r['kind'] or activity!=r['activity']
    db.execute('UPDATE community_rooms SET privacy=?,password_hash=?,activity=?,kind=?,approval=CASE WHEN ?=\'private\' THEN 1 ELSE approval END,layout_revision=layout_revision+? WHERE id=?',(privacy,hashed,activity,kind,privacy,int(changed),rid))
    if changed and not creating:
        db.execute("UPDATE community_rooms SET url='',media_type='',post_id=NULL,position=0,paused=1,music_current=NULL,media_epoch=media_epoch+1,revision=revision+1,updated_at=? WHERE id=?",(time.time(),rid))
        if kind=='live':db.execute("UPDATE community_members SET seat=NULL,camera=0,mic=0,stage_request='' WHERE room_id=? AND user_id!=?",(rid,r['host_id']))
        if kind not in ('live','video','watch'):db.execute('UPDATE community_members SET camera=0 WHERE room_id=?',(rid,))
        db.execute('DELETE FROM community_signals WHERE room_id=?',(rid,))


def admission(db,r,uid,password,error):
    m=db.execute('SELECT status FROM community_members WHERE room_id=? AND user_id=?',(r['id'],uid)).fetchone()
    if r['host_id']==uid or (m and m['status'] in ('joined','pending')):return
    if r['privacy']=='password':
        now=time.time();db.execute('DELETE FROM room_password_attempts WHERE at<?',(now-900,))
        if db.execute('SELECT COUNT(*) FROM room_password_attempts WHERE room_id=? AND user_id=?',(r['id'],uid)).fetchone()[0]>=10:raise error('Muitas tentativas. Aguarde 15 minutos.',429)
        if not check_password_hash(r['password_hash'],str(password or '')[:128]):
            db.execute('INSERT INTO room_password_attempts VALUES(?,?,?)',(r['id'],uid,now));db.commit();raise error('Informe a senha correta para entrar.',403)


def public(r):
    value=dict(r);value.pop('password_hash',None);return value


def snapshot(db,rid,uid):
    audio=db.execute('SELECT * FROM room_audio WHERE room_id=?',(rid,)).fetchone()
    a=dict(audio) if audio else {'current_id':None,'position':0,'paused':1,'revision':0,'updated_at':time.time()}
    a['queue']=[dict(r) for r in db.execute('SELECT * FROM room_audio_queue WHERE room_id=? ORDER BY id LIMIT 100',(rid,))];a['server_time']=time.time()
    polls=[]
    for p in db.execute('SELECT * FROM room_polls WHERE room_id=? ORDER BY created_at DESC LIMIT 5',(rid,)):
        p=dict(p);p['options']=json.loads(p['options']);p['counts']=[db.execute('SELECT COUNT(*) FROM room_votes WHERE poll_id=? AND choice=?',(p['id'],i)).fetchone()[0] for i in range(len(p['options']))]
        own=db.execute('SELECT choice FROM room_votes WHERE poll_id=? AND user_id=?',(p['id'],uid)).fetchone();p['choice']=own[0] if own else None;polls.append(p)
    ps=db.execute('SELECT s.*,p.name,p.description,p.url,p.cover,p.kind,p.engine,p.active FROM room_plugin_sessions s JOIN room_plugins p ON p.id=s.plugin_id WHERE s.room_id=? AND p.active=1',(rid,)).fetchone()
    plugin=None
    if ps:
        plugin=dict(ps);joined=bool(db.execute('SELECT 1 FROM room_plugin_players WHERE session_id=? AND user_id=?',(ps['id'],uid)).fetchone());plugin['joined']=joined
        plugin['players']=[dict(r) for r in db.execute('SELECT u.id,u.name,u.username FROM room_plugin_players p JOIN community_members m ON m.room_id=? AND m.user_id=p.user_id AND m.status=\'joined\' AND m.seen_at>? JOIN users u ON u.id=p.user_id WHERE p.session_id=?',(rid,time.time()-45,ps['id']))]
        if joined:
            plugin['state']=json.loads(plugin['state']);plugin['events']=[{**dict(e),'payload':json.loads(e['payload'])} for e in db.execute('SELECT id,user_id,payload FROM room_plugin_events WHERE session_id=? ORDER BY id DESC LIMIT 50',(ps['id'],))][::-1]
        else:plugin.pop('url',None);plugin.pop('state',None);plugin['events']=[]
    return {'audio':a,'polls':polls,'plugin':plugin}


def register(app,db,auth,data,error,room,content_url):
    def uid():return g.user['id']
    def tx(rid,host=False):
        db().execute('BEGIN IMMEDIATE');return room(rid,member=True,host=host)
    def bounded(value,maximum=160):
        v=str(value or '').strip()
        if not 2<=len(v)<=maximum:raise error(f'Use entre 2 e {maximum} caracteres.')
        return v
    def payload_json(value,limit):
        try:
            if not isinstance(value,dict):raise ValueError()
            encoded=json.dumps(value,allow_nan=False)
            if len(encoded)>limit:raise ValueError()
            return encoded
        except (ValueError,TypeError):raise error('Conteúdo do plugin inválido.')

    @app.get('/api/community/room-plugins')
    @auth()
    def plugins():return jsonify(plugins=[dict(r) for r in db().execute("SELECT id,name,description,kind,engine,cover,coins,revision FROM room_plugins WHERE active=1 AND engine!='provider' ORDER BY name")])

    @app.post('/api/community/rooms/<rid>/provider')
    @auth()
    def provider(rid):
        d=data();tx(rid,True);source=str(d.get('url',''));provider=d.get('provider')
        try:
            p=urlsplit(source)
            if len(source)>2000 or p.scheme!='https' or p.username or p.password or p.port not in (None,443):raise ValueError()
        except ValueError:raise error('Use um link HTTPS oficial.')
        if provider=='spotify' and p.hostname=='open.spotify.com':
            path=re.sub(r'^/intl-[a-z]+/','/',p.path)
            if not re.fullmatch(r'/(track|album|playlist|episode|show|artist)/[A-Za-z0-9]{22}',path):raise error('Use o link completo de uma faixa, álbum ou playlist do Spotify.')
            url='https://open.spotify.com/embed'+path;name='Spotify'
        elif provider=='twitch' and p.hostname in ('twitch.tv','www.twitch.tv'):
            channel=p.path.strip('/')
            if not re.fullmatch(r'[a-zA-Z0-9_]{3,25}',channel):raise error('Use o link de um canal Twitch.')
            url='https://player.twitch.tv/?'+urlencode({'channel':channel,'parent':request.host.split(':')[0],'autoplay':'false'});name='Twitch · '+channel
        else:raise error('Use um link do provedor selecionado.')
        if db().execute('SELECT 1 FROM room_plugin_sessions WHERE room_id=?',(rid,)).fetchone():raise error('Desative o widget atual antes de trocar.',409)
        pid='provider_'+hashlib.sha256(url.encode()).hexdigest()[:24]
        db().execute("INSERT OR IGNORE INTO room_plugins(id,name,description,kind,engine,url) VALUES(?,?,?,'widget','provider',?)",(pid,name,'Player oficial · controles do provedor',url))
        active=db().execute('SELECT active FROM room_plugins WHERE id=?',(pid,)).fetchone()[0]
        if not active:raise error('Este widget foi desativado pelo administrador.',403)
        sid=secrets.token_urlsafe(16);db().execute('INSERT INTO room_plugin_sessions(room_id,id,plugin_id,coins,created_at) VALUES(?,?,?,0,?)',(rid,sid,pid,time.time()))
        db().execute('INSERT INTO room_plugin_players VALUES(?,?,?)',(sid,uid(),time.time()));db().commit();return jsonify(ok=True)

    @app.get('/api/community/rooms/<rid>/experience')
    @auth()
    def experience(rid):
        room(rid,member=True);return jsonify(snapshot(db(),rid,uid()))

    @app.post('/api/community/rooms/<rid>/experience/queue')
    @auth()
    def enqueue(rid):
        d=data();r=tx(rid);lane=d.get('lane','video');url,typ=content_url(d.get('url'),error,media=True)
        title=bounded(d.get('title') or ('Vídeo do YouTube' if typ=='youtube' else 'Música da sala' if lane=='music' else 'Vídeo da sala'))
        start=d.get('start_now') is True
        if start and r['host_id']!=uid():raise error('Somente o anfitrião pode iniciar a reprodução.',403)
        table='room_audio_queue' if lane=='music' else 'community_queue'
        if lane not in ('music','video'):raise error('Fila inválida.')
        if lane=='music' and typ not in ('youtube','audio','soundcloud'):raise error('Use uma música do YouTube, SoundCloud ou um arquivo de áudio.')
        if db().execute('SELECT COUNT(*) FROM '+table+' WHERE room_id=?',(rid,)).fetchone()[0]>=100:raise error('A fila atingiu 100 itens.')
        if lane=='music':
            tid='room_'+hashlib.sha256(url.encode()).hexdigest()[:24]
            provider='youtube' if typ=='youtube' else 'soundcloud' if typ=='soundcloud' else 'upload' if url.startswith('/api/community/assets/') else 'link'
            db().execute('INSERT OR IGNORE INTO music_tracks(id,provider,title,artist,url,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(tid,provider,title,'Comunidade WorkTV',url,time.time(),time.time()))
            tid=db().execute('SELECT id FROM music_tracks WHERE url=?',(url,)).fetchone()[0]
            item=db().execute('INSERT INTO room_audio_queue(room_id,user_id,title,url,media_type,created_at,track_id) VALUES(?,?,?,?,?,?,?)',(rid,uid(),title,url,typ,time.time(),tid)).lastrowid
            if start:
                now=time.time();db().execute('INSERT OR IGNORE INTO room_audio(room_id,updated_at) VALUES(?,?)',(rid,now))
                db().execute('UPDATE room_audio SET current_id=?,position=0,paused=0,revision=revision+1,updated_at=? WHERE room_id=?',(item,now,rid))
        else:
            if r['kind']=='music' and r['music_current']:raise error('Use a fila de músicas desta sala.',409)
            item=db().execute('INSERT INTO community_queue(room_id,title,url,media_type,created_at,added_by) VALUES(?,?,?,?,?,?)',(rid,title,url,typ,time.time(),uid())).lastrowid
            if start:
                db().execute('UPDATE community_rooms SET url=?,media_type=?,post_id=NULL,music_current=NULL,position=0,paused=0,media_epoch=media_epoch+1,revision=revision+1,updated_at=? WHERE id=?',(url,typ,time.time(),rid))
                db().execute('DELETE FROM community_queue WHERE id=?',(item,))
        import community_social
        community_social.retain_assets(db(),url);db().commit();return jsonify(ok=True,id=item,started=start,lane=lane),201

    @app.patch('/api/community/rooms/<rid>/soundtrack')
    @auth()
    def soundtrack(rid):
        d=data();tx(rid,True);now=time.time()
        db().execute('INSERT OR IGNORE INTO room_audio(room_id,updated_at) VALUES(?,?)',(rid,now));r=db().execute('SELECT * FROM room_audio WHERE room_id=?',(rid,)).fetchone()
        if d.get('revision',r['revision'])!=r['revision']:raise error('A fila foi atualizada. Tente novamente.',409)
        action=d.get('action');current=r['current_id'];position=r['position']+(0 if r['paused'] else now-r['updated_at']);paused=r['paused']
        if action=='play':
            q=db().execute('SELECT id FROM room_audio_queue WHERE room_id=? AND id=?',(rid,d.get('id'))).fetchone()
            if not q:raise error('Música não encontrada.',404)
            current=q[0];position=0;paused=0
        elif action in ('next','ended'):
            if action=='ended' and (type(d.get('current_id')) is not int or d['current_id']!=current):
                db().commit();return jsonify(ok=True,advanced=False)
            q=db().execute('SELECT id FROM room_audio_queue WHERE room_id=? AND id>? ORDER BY id LIMIT 1',(rid,current or 0)).fetchone();current=q[0] if q else None;position=0;paused=0 if q else 1
        elif action=='stop':current=None;position=0;paused=1
        elif action=='pause':paused=1
        elif action=='resume':
            if not current:raise error('Selecione uma música.')
            paused=0
        elif action=='sync':
            position=d.get('position');paused=int(d.get('paused') is not False)
            if type(position) not in (float,int) or not math.isfinite(position) or not 0<=position<=86400:raise error('Posição inválida.')
        else:raise error('Controle inválido.')
        db().execute('UPDATE room_audio SET current_id=?,position=?,paused=?,revision=revision+1,updated_at=? WHERE room_id=?',(current,position,paused,now,rid));db().commit();return jsonify(ok=True)

    @app.delete('/api/community/rooms/<rid>/soundtrack/<int:item>')
    @auth()
    def soundtrack_delete(rid,item):
        r=tx(rid);q=db().execute('SELECT user_id FROM room_audio_queue WHERE id=? AND room_id=?',(item,rid)).fetchone()
        if not q or (uid()!=r['host_id'] and uid()!=q[0]):raise error('Somente o autor ou anfitrião pode remover.',403)
        db().execute('DELETE FROM room_audio_queue WHERE id=?',(item,));db().execute('UPDATE room_audio SET current_id=NULL,paused=1,revision=revision+1,updated_at=? WHERE room_id=? AND current_id=?',(time.time(),rid,item));db().commit();return jsonify(ok=True)

    @app.post('/api/community/rooms/<rid>/polls')
    @auth()
    def create_poll(rid):
        d=data();tx(rid,True);opts=d.get('options')
        if not isinstance(opts,list) or not 2<=len(opts)<=6:raise error('Use entre 2 e 6 alternativas.')
        opts=[bounded(x,100) for x in opts]
        if len(set(opts))!=len(opts):raise error('Use alternativas diferentes.')
        if db().execute('SELECT COUNT(*) FROM room_polls WHERE room_id=? AND closed=0',(rid,)).fetchone()[0]>=3:raise error('Encerre uma enquete antes de criar outra.')
        db().execute('INSERT INTO room_polls(id,room_id,question,options,created_at) VALUES(?,?,?,?,?)',(secrets.token_urlsafe(9),rid,bounded(d.get('question'),200),json.dumps(opts),time.time()));db().commit();return jsonify(ok=True),201

    @app.patch('/api/community/rooms/<rid>/polls/<pid>')
    @auth()
    def vote(rid,pid):
        d=data();r=tx(rid);p=db().execute('SELECT * FROM room_polls WHERE id=? AND room_id=?',(pid,rid)).fetchone()
        if not p:raise error('Enquete não encontrada.',404)
        if d.get('close'):
            if uid()!=r['host_id']:raise error('Somente o anfitrião pode encerrar.',403)
            db().execute('UPDATE room_polls SET closed=1 WHERE id=?',(pid,))
        else:
            if p['closed']:raise error('Enquete encerrada.',409)
            choice=d.get('choice')
            if type(choice)!=int or not 0<=choice<len(json.loads(p['options'])):raise error('Escolha uma alternativa.')
            db().execute('INSERT INTO room_votes VALUES(?,?,?) ON CONFLICT(poll_id,user_id) DO UPDATE SET choice=excluded.choice',(pid,uid(),choice))
        db().commit();return jsonify(ok=True)

    @app.route('/api/community/rooms/<rid>/plugin',methods=['POST','DELETE','PATCH'])
    @auth()
    def plugin(rid):
        d=data();r=tx(rid,True)
        if request.method=='DELETE':db().execute('DELETE FROM room_plugin_sessions WHERE room_id=?',(rid,))
        elif request.method=='POST':
            p=db().execute('SELECT * FROM room_plugins WHERE id=? AND active=1 AND engine=\'embed\'',(d.get('plugin_id'),)).fetchone()
            if not p:raise error('Plugin indisponível.',404)
            old=db().execute('SELECT plugin_id FROM room_plugin_sessions WHERE room_id=?',(rid,)).fetchone()
            if old:raise error('Desative o plugin atual antes de trocar.',409)
            db().execute('INSERT INTO room_plugin_sessions(room_id,id,plugin_id,coins,created_at) VALUES(?,?,?,?,?)',(rid,secrets.token_urlsafe(16),p['id'],p['coins'],time.time()))
        else:
            ps=db().execute('SELECT * FROM room_plugin_sessions WHERE room_id=?',(rid,)).fetchone()
            if not ps or d.get('session_id')!=ps['id'] or d.get('revision')!=ps['revision']:raise error('O plugin foi atualizado.',409)
            state=d.get('state',{});value=payload_json(state,32000)
            db().execute('UPDATE room_plugin_sessions SET state=?,revision=revision+1 WHERE room_id=?',(value,rid))
        db().commit();return jsonify(ok=True)

    @app.post('/api/community/rooms/<rid>/plugin/join')
    @auth()
    def plugin_join(rid):
        d=data();tx(rid);p=db().execute('SELECT s.* FROM room_plugin_sessions s JOIN room_plugins p ON p.id=s.plugin_id AND p.active=1 WHERE s.room_id=?',(rid,)).fetchone()
        if not p or d.get('session_id')!=p['id']:raise error('O plugin mudou. Abra novamente.',409)
        flix_wallet.join_game(db(),p['id'],uid(),p['coins'],d.get('confirm_coins'),error)
        db().execute('INSERT OR IGNORE INTO room_plugin_players VALUES(?,?,?)',(p['id'],uid(),time.time()));db().commit();return jsonify(ok=True)

    @app.post('/api/community/rooms/<rid>/plugin/events')
    @auth()
    def plugin_event(rid):
        d=data();tx(rid);s=db().execute('SELECT s.id FROM room_plugin_sessions s JOIN room_plugin_players p ON p.session_id=s.id AND p.user_id=? JOIN room_plugins rp ON rp.id=s.plugin_id AND rp.active=1 WHERE s.room_id=?',(uid(),rid)).fetchone()
        if not s or d.get('session_id')!=s['id']:raise error('Entre no plugin para participar.',403)
        payload=d.get('payload');value=payload_json(payload,4000)
        if db().execute('SELECT COUNT(*) FROM room_plugin_events WHERE user_id=? AND created_at>?',(uid(),time.time()-1)).fetchone()[0]>=15:raise error('Aguarde um instante.',429)
        db().execute('INSERT INTO room_plugin_events(session_id,user_id,payload,created_at) VALUES(?,?,?,?)',(s['id'],uid(),value,time.time()));db().execute('DELETE FROM room_plugin_events WHERE session_id=? AND id NOT IN (SELECT id FROM room_plugin_events WHERE session_id=? ORDER BY id DESC LIMIT 200)',(s['id'],s['id']));db().commit();return jsonify(ok=True)

    @app.route('/api/community/profiles/<username>/music-heart',methods=['PUT','DELETE'])
    @auth()
    def music_heart(username):
        u=db().execute("SELECT id FROM users WHERE username=? AND status='active'",(username,)).fetchone()
        if not u:raise error('Perfil indisponível.',404)
        p=flix_wallet.profile(db(),u['id'],uid());song=p['recent_music']
        if not song or song['id']!=data().get('track_id'):raise error('A música do perfil mudou.',409)
        if request.method=='PUT':db().execute('INSERT OR IGNORE INTO room_music_hearts VALUES(?,?,?)',(u['id'],song['id'],uid()))
        else:db().execute('DELETE FROM room_music_hearts WHERE user_id=? AND track_id=? AND reactor=?',(u['id'],song['id'],uid()))
        db().commit();return jsonify(ok=True)
