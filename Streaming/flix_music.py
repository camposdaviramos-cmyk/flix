"""SoundCloud discovery and one music catalog/queue integrated with community rooms."""
import base64,hashlib,json,re,secrets,threading,time
from urllib.parse import urlencode,urlsplit,quote
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from flask import g,request,jsonify
import community_social,social_hub,room_lifecycle
from social_spaces import notify
TOKEN_LOCK=threading.Lock()

def migrate(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS music_tracks(id TEXT PRIMARY KEY,provider TEXT NOT NULL,provider_id TEXT NOT NULL DEFAULT '',title TEXT NOT NULL,artist TEXT NOT NULL,artist_id TEXT NOT NULL DEFAULT '',album TEXT NOT NULL DEFAULT '',album_id TEXT NOT NULL DEFAULT '',genre TEXT NOT NULL DEFAULT '',url TEXT UNIQUE NOT NULL,image TEXT NOT NULL DEFAULT '',duration REAL NOT NULL DEFAULT 0,released_at TEXT NOT NULL DEFAULT '',created_at REAL NOT NULL,updated_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS music_playlists(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,cover TEXT NOT NULL DEFAULT '',public INTEGER NOT NULL DEFAULT 1,created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS music_playlist_tracks(playlist_id TEXT REFERENCES music_playlists(id) ON DELETE CASCADE,track_id TEXT REFERENCES music_tracks(id) ON DELETE CASCADE,position INTEGER NOT NULL,PRIMARY KEY(playlist_id,track_id));
    CREATE TABLE IF NOT EXISTS music_saved(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,track_id TEXT REFERENCES music_tracks(id) ON DELETE CASCADE,created_at REAL NOT NULL,PRIMARY KEY(user_id,track_id));
    CREATE TABLE IF NOT EXISTS music_queues(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,payload TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS music_play_events(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,track_id TEXT REFERENCES music_tracks(id) ON DELETE CASCADE,created_at REAL NOT NULL,last_at REAL NOT NULL,position REAL NOT NULL DEFAULT 0,listened REAL NOT NULL DEFAULT 0,counted INTEGER NOT NULL DEFAULT 0);
    CREATE INDEX IF NOT EXISTS music_real_plays ON music_play_events(track_id,counted,created_at);
    CREATE TABLE IF NOT EXISTS music_api_cache(key TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at REAL NOT NULL);
    ''')
    for table,cols in {'music_tracks':{'featured':'INTEGER NOT NULL DEFAULT 0'},'community_queue':{'track_id':'TEXT REFERENCES music_tracks(id)','added_by':'TEXT REFERENCES users(id)','position':'INTEGER NOT NULL DEFAULT 0'},'community_rooms':{'music_current':'INTEGER','music_repeat':"TEXT NOT NULL DEFAULT 'off'",'music_shuffle':'INTEGER NOT NULL DEFAULT 0'},'community_posts':{'music_id':'TEXT REFERENCES music_tracks(id)'}}.items():
        existing={r[1] for r in db.execute('PRAGMA table_info('+table+')')}
        for name,definition in cols.items():
            if name not in existing:db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
    # Preserve existing audio/SoundCloud rooms without fetching or replacing their sources.
    for r in db.execute("SELECT * FROM community_rooms WHERE kind='music' AND status='open' AND music_current IS NULL AND url!='' AND media_type IN ('audio','soundcloud')").fetchall():
        ensure_room_tracks(db,r)

def ensure_room_tracks(db,r):
    rows=db.execute('SELECT * FROM community_queue WHERE room_id=? ORDER BY position,id',(r['id'],)).fetchall()
    if not r['music_current'] and r['url'] and r['media_type'] in ('audio','soundcloud'):
        db.execute('INSERT INTO community_queue(room_id,title,url,media_type,created_at,position,added_by) VALUES(?,?,?,?,?,-1,?)',(r['id'],r['title'],r['url'],r['media_type'],time.time(),r['host_id']))
        rows=db.execute('SELECT * FROM community_queue WHERE room_id=? ORDER BY position,id',(r['id'],)).fetchall()
    for q in rows:
        if q['track_id'] or q['media_type'] not in ('audio','soundcloud'):continue
        tid='legacy_'+hashlib.sha256(q['url'].encode()).hexdigest()[:24]
        db.execute('INSERT OR IGNORE INTO music_tracks(id,provider,title,artist,url,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(tid,'soundcloud' if q['media_type']=='soundcloud' else 'upload' if q['url'].startswith('/api/community/assets/') else 'link',q['title'],'Comunidade WorkTV',q['url'],time.time(),time.time()))
        tid=db.execute('SELECT id FROM music_tracks WHERE url=?',(q['url'],)).fetchone()[0]
        db.execute('UPDATE community_queue SET track_id=?,added_by=COALESCE(added_by,?) WHERE id=?',(tid,r['host_id'],q['id']))
    if not r['music_current']:
        first=db.execute('SELECT id FROM community_queue WHERE room_id=? AND track_id IS NOT NULL ORDER BY position,id LIMIT 1',(r['id'],)).fetchone()
        if first:db.execute('UPDATE community_rooms SET music_current=? WHERE id=?',(first[0],r['id']))

def sc_url(value):
    try:
        u=urlsplit(value)
        return u.scheme=='https' and u.hostname in ('soundcloud.com','www.soundcloud.com') and not u.username and not u.password and u.port in (None,443) and len(u.path.split('/'))>=3 and len(value)<=2000
    except (ValueError,TypeError):return False

def public_track(row):return dict(row) if row else None

def save_track(db,raw):
    user=raw.get('user') or {};url=raw.get('permalink_url','')
    if not sc_url(url) or raw.get('sharing','public')!='public' or raw.get('access')=='blocked':return None
    pid=str(raw.get('urn') or raw.get('id') or '');tid='sc_'+hashlib.sha256(url.encode()).hexdigest()[:24]
    t={'id':tid,'provider':'soundcloud','provider_id':pid,'title':str(raw.get('title') or 'Faixa')[:160],'artist':str(raw.get('metadata_artist') or user.get('username') or raw.get('author_name') or 'Artista')[:160],'artist_id':str(user.get('urn') or user.get('id') or ''),'album':str((raw.get('publisher_metadata') or {}).get('album_title') or '')[:160],'album_id':'','genre':str(raw.get('genre') or '')[:80],'url':url,'image':str(raw.get('artwork_url') or raw.get('thumbnail_url') or user.get('avatar_url') or '')[:2000],'duration':max(0,min(86400,float(raw.get('duration') or 0)/1000)),'released_at':str(raw.get('release_date') or raw.get('created_at') or '')[:40],'created_at':time.time(),'updated_at':time.time()}
    db.execute('INSERT INTO music_tracks('+','.join(t)+') VALUES('+','.join('?' for _ in t)+') ON CONFLICT(url) DO UPDATE SET title=excluded.title,artist=excluded.artist,image=excluded.image,duration=MAX(duration,excluded.duration),provider_id=CASE WHEN excluded.provider_id!=\'\' THEN excluded.provider_id ELSE music_tracks.provider_id END,updated_at=excluded.updated_at',tuple(t.values()))
    return public_track(db.execute('SELECT * FROM music_tracks WHERE url=?',(url,)).fetchone())

def track_for_post(db,p):
    if p.get('music_id'):return public_track(db.execute('SELECT * FROM music_tracks WHERE id=?',(p['music_id'],)).fetchone())
    return public_track(db.execute('SELECT * FROM music_tracks WHERE url=?',(p.get('url',''),)).fetchone()) if p.get('kind')=='music' else None

def advance_finished(db,r,now):
    rows=db.execute('SELECT * FROM community_queue WHERE room_id=? AND track_id IS NOT NULL ORDER BY position,id',(r['id'],)).fetchall()
    current=r['music_current'];index=next((i for i,q in enumerate(rows) if q['id']==current),-1)
    if index<0:return False
    if r['music_repeat']=='one':target=index
    elif r['music_shuffle'] and len(rows)>1:target=secrets.choice([i for i in range(len(rows)) if i!=index])
    else:target=index+1
    playing=target<len(rows) or r['music_repeat']=='all'
    q=rows[target%len(rows)] if playing else rows[index]
    db.execute('UPDATE community_rooms SET music_current=?,url=?,media_type=?,position=0,paused=?,media_epoch=media_epoch+1,revision=revision+1,updated_at=? WHERE id=?',(q['id'],q['url'],q['media_type'],int(not playing),now,r['id']))
    return playing


def room_snapshot(db,rid):
    row=db.execute('SELECT * FROM community_rooms WHERE id=?',(rid,)).fetchone();r=dict(row);r.pop('password_hash',None)
    r['queue']=[{**dict(q),'track':public_track(db.execute('SELECT * FROM music_tracks WHERE id=?',(q['track_id'],)).fetchone())} for q in db.execute("SELECT q.*,COALESCE(u.name,'Anfitrião') added_name FROM community_queue q LEFT JOIN users u ON u.id=q.added_by WHERE q.room_id=? AND q.track_id IS NOT NULL ORDER BY q.position,q.id",(rid,))]
    r['track']=next((q['track'] for q in r['queue'] if q['id']==r['music_current']),None)
    r['server_time']=time.time();r['current_position']=r['position']+(0 if r['paused'] else max(0,r['server_time']-r['updated_at']))
    if r['track'] and r['track']['duration']>0:r['current_position']=min(r['current_position'],r['track']['duration'])
    r['members']=[{**dict(u),**{'online':True}} for u in db.execute("SELECT u.id,u.name,u.username,u.verified,COALESCE(p.avatar,'') avatar FROM community_members m JOIN users u ON u.id=m.user_id AND u.status='active' LEFT JOIN community_profiles p ON p.user_id=u.id WHERE m.room_id=? AND m.status='joined' AND m.seen_at>? ORDER BY m.joined_at",(rid,time.time()-45))]
    return r

def register(app,db,auth,data,error,setting,save_setting):
    def uid():return g.user['id']
    def configured():return bool(setting('soundcloud_client_id') and setting('soundcloud_client_secret'))
    def fetch_json(url,headers=None,body=None):
        try:
            with urlopen(Request(url,data=body,headers={'Accept':'application/json',**(headers or {})}),timeout=10) as r:return json.loads(r.read(2_000_000))
        except (HTTPError,URLError,TimeoutError,ValueError):raise error('SoundCloud indisponível. Confira a integração no painel ou tente outra faixa.',502)
    def token():
        if not configured():raise error('O administrador precisa conectar o SoundCloud nas configurações.',503)
        with TOKEN_LOCK:
            cached=json.loads(setting('soundcloud_token','{}'))
            if cached.get('expires',0)>time.time()+60:return cached['access_token']
            cid=setting('soundcloud_client_id');secret=setting('soundcloud_client_secret')
            if cached.get('refresh_token'):
                args={'grant_type':'refresh_token','refresh_token':cached['refresh_token'],'client_id':cid,'client_secret':secret};headers={}
            else:args={'grant_type':'client_credentials'};headers={'Authorization':'Basic '+base64.b64encode((cid+':'+secret).encode()).decode()}
            value=fetch_json('https://secure.soundcloud.com/oauth/token',{**headers,'Content-Type':'application/x-www-form-urlencoded'},urlencode(args).encode())
            if not value.get('access_token'):raise error('Credenciais do SoundCloud inválidas.',502)
            save_setting('soundcloud_token',json.dumps({'access_token':value['access_token'],'refresh_token':value.get('refresh_token'),'expires':time.time()+int(value.get('expires_in',3600))}));db().commit();return value['access_token']
    def sc(path,params=None):return fetch_json('https://api.soundcloud.com'+path+('?' +urlencode(params) if params else ''),{'Authorization':'OAuth '+token()})
    def get_track(tid):
        r=db().execute('SELECT * FROM music_tracks WHERE id=?',(tid,)).fetchone()
        if not r:raise error('Música indisponível.',404)
        if r['provider']=='upload':community_social.local_asset(r['url'],db(),error)
        return dict(r)
    def ids(value):
        if not isinstance(value,list) or len(value)>200 or any(not isinstance(x,str) for x in value):raise error('Use até 200 faixas.')
        for tid in set(value):get_track(tid)
        return value
    def playlist(pid,owner=False):
        r=db().execute('SELECT * FROM music_playlists WHERE id=?',(pid,)).fetchone()
        if not r or (owner and r['user_id']!=uid()) or (not r['public'] and r['user_id']!=uid()):raise error('Playlist indisponível.',404)
        return dict(r)
    def room(rid,host=False):
        r=db().execute("SELECT r.* FROM community_rooms r JOIN community_members m ON m.room_id=r.id WHERE r.id=? AND r.kind='music' AND r.status='open' AND m.user_id=? AND m.status='joined'",(rid,uid())).fetchone()
        if not r:raise error('Entre na sala para ouvir com a turma.',403)
        if host and r['host_id']!=uid():raise error('Apenas o anfitrião controla a música e a fila.',403)
        return r

    @app.get('/api/admin/music')
    @auth(admin=True)
    def admin_music_catalog():
        return jsonify(tracks=[dict(t) for t in db().execute('SELECT t.*,(SELECT COUNT(*) FROM music_play_events e WHERE e.track_id=t.id AND e.counted=1) plays FROM music_tracks t ORDER BY featured DESC,created_at DESC LIMIT 200')])

    @app.patch('/api/admin/music/<tid>')
    @auth(admin=True)
    def admin_music_update(tid):
        get_track(tid);d=data()
        if 'featured' in d:
            if type(d['featured']) is not bool:raise error('Destaque inválido.')
            db().execute('UPDATE music_tracks SET featured=? WHERE id=?',(int(d['featured']),tid))
        for field in ('title','artist','genre','album'):
            if field in d:
                value=d[field]
                if not isinstance(value,str) or len(value)>160 or (field in ('title','artist') and not value.strip()):raise error('Metadado inválido.')
                db().execute('UPDATE music_tracks SET '+field+'=? WHERE id=?',(value.strip(),tid))
        db().execute('INSERT INTO community_audit(admin_id,action,target,created_at) VALUES(?,?,?,?)',(uid(),'music:edit',tid,time.time()));db().commit();return jsonify(ok=True)

    @app.get('/api/music/config')
    @auth()
    def music_config():return jsonify(configured=configured(),provider='soundcloud')

    @app.get('/api/music/search')
    @app.get('/api/community/music/search')
    @auth()
    def music_search():
        q=request.args.get('q','').strip()[:100];kind=request.args.get('kind','tracks')
        if kind not in ('tracks','artists','albums'):raise error('Busca inválida.')
        if len(q)<2:return jsonify(items=[],configured=configured(),provider='soundcloud')
        if not configured():return jsonify(items=[],configured=False,provider='soundcloud',message='A busca aguarda a conexão do SoundCloud pelo administrador. Você pode adicionar um link público ou enviar seu áudio.')
        key=kind+':'+q.casefold();cached=db().execute('SELECT payload FROM music_api_cache WHERE key=? AND created_at>?',(key,time.time()-900)).fetchone()
        if cached:return jsonify(items=json.loads(cached[0]),configured=True,provider='soundcloud')
        db().execute('DELETE FROM community_music_searches WHERE created_at<?',(time.time()-3600,))
        if db().execute('SELECT COUNT(*) FROM community_music_searches WHERE user_id=?',(uid(),)).fetchone()[0]>=30:raise error('Aguarde antes de pesquisar mais músicas.',429)
        db().execute('INSERT INTO community_music_searches VALUES(?,?)',(uid(),time.time()));db().commit()
        params={'q':q,'limit':20,'linked_partitioning':'true'}
        if kind=='tracks':params['access']='playable'
        result=sc('/'+{'tracks':'tracks','artists':'users','albums':'playlists'}[kind],params);items=[]
        for item in (result.get('collection',[]) if isinstance(result,dict) else result):
            if kind=='tracks':
                t=save_track(db(),item)
                if t:items.append(t)
            else:
                url=item.get('permalink_url','');parsed=urlsplit(url)
                if parsed.scheme!='https' or parsed.hostname not in ('soundcloud.com','www.soundcloud.com'):continue
                items.append({'id':str(item.get('urn') or item.get('id')),'type':kind,'title':str(item.get('title') or item.get('username') or '')[:160],'artist':str((item.get('user') or {}).get('username') or '')[:160],'url':url,'image':item.get('artwork_url') or item.get('avatar_url') or '', 'is_album':bool(item.get('is_album'))})
        db().execute('INSERT OR REPLACE INTO music_api_cache VALUES(?,?,?)',(key,json.dumps(items),time.time()));db().execute('DELETE FROM music_api_cache WHERE created_at<?',(time.time()-86400,));db().commit();return jsonify(items=items,configured=True,provider='soundcloud')

    @app.get('/api/music/discover/<kind>/<path:provider_id>')
    @auth()
    def music_discover_tracks(kind,provider_id):
        if kind not in ('artists','albums') or not re.fullmatch(r'(?:soundcloud:(?:users|playlists):)?[0-9]+',provider_id):raise error('Item inválido.')
        value=sc('/users/'+quote(provider_id,safe='')+'/tracks',{'limit':50,'linked_partitioning':'true','access':'playable'}) if kind=='artists' else sc('/playlists/'+quote(provider_id,safe=''))
        rows=value.get('collection',value.get('tracks',[])) if isinstance(value,dict) else value;items=[]
        for raw in rows:
            t=save_track(db(),raw)
            if t:
                if kind=='albums':db().execute('UPDATE music_tracks SET album=?,album_id=? WHERE id=?',(str(value.get('title',''))[:160],provider_id,t['id']));t['album']=value.get('title','');t['album_id']=provider_id
                items.append(t)
        db().commit();return jsonify(items=items)

    @app.post('/api/music/import')
    @auth()
    def music_import_track():
        d=data();url=d.get('url','');existing=db().execute('SELECT * FROM music_tracks WHERE url=?',(url,)).fetchone()
        if existing:return jsonify(track=get_track(existing['id']))
        if db().execute('SELECT COUNT(*) FROM community_music_searches WHERE user_id=? AND created_at>?',(uid(),time.time()-3600)).fetchone()[0]>=30:raise error('Aguarde antes de adicionar mais músicas.',429)
        db().execute('INSERT INTO community_music_searches VALUES(?,?)',(uid(),time.time()));db().commit()
        if sc_url(url):
            if configured():raw=sc('/resolve',{'url':url})
            else:
                value=fetch_json('https://soundcloud.com/oembed?'+urlencode({'format':'json','url':url}));raw={**value,'permalink_url':url,'user':{'username':value.get('author_name','Artista')}}
            if raw.get('kind') not in (None,'track'):raise error('Use o link de uma música. Álbuns e artistas estão na busca.')
            t=save_track(db(),raw)
            if not t:raise error('Esta faixa não está disponível para reprodução.',400)
        else:
            asset=community_social.local_asset(url,db(),error,owner=uid())
            if not asset or asset[1]!='audio':raise error('Use um link do SoundCloud ou um áudio enviado por você.')
            title=str(d.get('title','')).strip();artist=str(d.get('artist') or g.user['name']).strip()
            if not 2<=len(title)<=160 or not 1<=len(artist)<=160:raise error('Informe título e artista.')
            tid='up_'+secrets.token_hex(12);now=time.time();community_social.retain_assets(db(),url)
            db().execute('INSERT INTO music_tracks(id,provider,title,artist,url,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(tid,'upload',title,artist,url,now,now));t=get_track(tid)
        db().commit();return jsonify(track=t),201

    @app.get('/api/music/catalog')
    @auth()
    def music_catalog():
        genre=request.args.get('genre','');sort=request.args.get('sort','popular');query=request.args.get('q','')[:100]
        order='t.released_at DESC,t.created_at DESC' if sort=='new' else 'recent_plays DESC,plays DESC,t.created_at DESC' if sort=='trending' else 'plays DESC,t.created_at DESC'
        rows=db().execute(f'''SELECT t.*,(SELECT COUNT(*) FROM music_play_events e WHERE e.track_id=t.id AND e.counted=1) plays,(SELECT COUNT(*) FROM music_play_events e WHERE e.track_id=t.id AND e.counted=1 AND e.created_at>?) recent_plays,EXISTS(SELECT 1 FROM music_saved s WHERE s.track_id=t.id AND s.user_id=?) saved FROM music_tracks t WHERE (?='' OR t.genre=?) AND (?='' OR t.title LIKE ? OR t.artist LIKE ? OR t.album LIKE ?) ORDER BY t.featured DESC,{order} LIMIT 100''',(time.time()-7*86400,uid(),genre,genre,query,'%'+query+'%','%'+query+'%','%'+query+'%')).fetchall()
        ranks={}
        for key in ('artist','album'):
            ranks[key+'s']=[dict(r) for r in db().execute(f"SELECT t.{key} name,COUNT(*) plays FROM music_play_events e JOIN music_tracks t ON t.id=e.track_id WHERE e.counted=1 AND t.{key}!='' GROUP BY t.{key} ORDER BY plays DESC LIMIT 10")]
        return jsonify(tracks=[dict(r) for r in rows],genres=[r[0] for r in db().execute("SELECT DISTINCT genre FROM music_tracks WHERE genre!='' ORDER BY genre")],rankings=ranks,configured=configured())

    @app.route('/api/music/tracks/<tid>/save',methods=['PUT','DELETE'])
    @auth()
    def music_save(tid):
        get_track(tid)
        if request.method=='PUT':db().execute('INSERT OR IGNORE INTO music_saved VALUES(?,?,?)',(uid(),tid,time.time()))
        else:db().execute('DELETE FROM music_saved WHERE user_id=? AND track_id=?',(uid(),tid))
        db().commit();return jsonify(ok=True)

    @app.get('/api/music/tracks/<tid>')
    @auth()
    def music_track_detail(tid):return jsonify(track=get_track(tid))

    @app.post('/api/music/tracks/<tid>/plays')
    @auth()
    def music_track_play(tid):
        track=get_track(tid);d=data();client=d.get('session');pos=d.get('position',0);playing=d.get('playing') is True
        if not isinstance(client,str) or not re.fullmatch('[a-zA-Z0-9_-]{8,80}',client) or not isinstance(pos,(int,float)) or not 0<=pos<=86400:raise error('Reprodução inválida.')
        eid=uid()+':'+client;now=time.time();db().execute('BEGIN IMMEDIATE');old=db().execute('SELECT * FROM music_play_events WHERE id=?',(eid,)).fetchone()
        if old and old['track_id']!=tid:raise error('Sessão de reprodução já utilizada.',409)
        if not old:
            if db().execute('SELECT COUNT(*) FROM music_play_events WHERE user_id=? AND created_at>?',(uid(),now-3600)).fetchone()[0]>=120:raise error('Limite de reproduções por hora atingido.',429)
            db().execute('INSERT INTO music_play_events(id,user_id,track_id,created_at,last_at,position) VALUES(?,?,?,?,?,?)',(eid,uid(),tid,now,now,pos));counted=False
        else:
            dt=now-old['last_at'];delta=pos-old['position'];added=min(dt,delta,8) if playing and 0<dt<=12 and 0<delta<=dt*1.8+1 else 0;listened=old['listened']+max(0,added)
            minimum=min(30,max(10,track['duration']/2)) if track['duration'] else 30
            recent=db().execute('SELECT 1 FROM music_play_events WHERE user_id=? AND track_id=? AND counted=1 AND created_at>? AND id!=?',(uid(),tid,now-600,eid)).fetchone()
            counted=bool(old['counted'] or (listened>=minimum and not recent))
            db().execute('UPDATE music_play_events SET last_at=?,position=?,listened=?,counted=? WHERE id=?',(now,pos,listened,int(counted),eid))
        db().commit();return jsonify(counted=counted)

    @app.route('/api/music/queue',methods=['GET','PUT'])
    @auth()
    def music_queue():
        r=db().execute('SELECT * FROM music_queues WHERE user_id=?',(uid(),)).fetchone();value=json.loads(r['payload']) if r else {'tracks':[],'index':0,'repeat':'off','shuffle':False,'position':0}
        revision=r['revision'] if r else 0
        if request.method=='PUT':
            d=data();ids(d.get('tracks',[]));index=d.get('index',0);repeat=d.get('repeat','off');position=d.get('position',0)
            if not isinstance(index,int) or not 0<=index<max(1,len(d.get('tracks',[]))) or repeat not in ('off','one','all') or not isinstance(position,(int,float)) or not 0<=position<=86400:raise error('Fila inválida.')
            db().execute('BEGIN IMMEDIATE');r=db().execute('SELECT revision FROM music_queues WHERE user_id=?',(uid(),)).fetchone();revision=r[0] if r else 0
            if d.get('revision')!=revision:raise error('Sua fila foi atualizada em outro dispositivo. Recarregue a fila.',409)
            value={'tracks':d.get('tracks',[]),'index':index,'repeat':repeat,'shuffle':d.get('shuffle') is True,'position':position};revision+=1;db().execute('INSERT INTO music_queues VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET payload=excluded.payload,revision=excluded.revision',(uid(),json.dumps(value),revision));db().commit()
        return jsonify(queue=value,tracks=[get_track(tid) for tid in value['tracks']],revision=revision)

    @app.route('/api/music/playlists',methods=['GET','POST'])
    @auth()
    def music_playlists():
        if request.method=='GET':
            user=request.args.get('user',uid());return jsonify(playlists=[dict(p) for p in db().execute('SELECT p.*,u.name,u.username,(SELECT COUNT(*) FROM music_playlist_tracks WHERE playlist_id=p.id) tracks FROM music_playlists p JOIN users u ON u.id=p.user_id WHERE p.user_id=? AND (p.public=1 OR p.user_id=?) ORDER BY created_at DESC LIMIT 100',(user,uid()))],saved=[dict(t) for t in db().execute('SELECT t.* FROM music_saved s JOIN music_tracks t ON t.id=s.track_id WHERE user_id=? ORDER BY s.created_at DESC LIMIT 200',(uid(),))])
        d=data();name=str(d.get('name','')).strip();cover=d.get('cover','')
        if not 2<=len(name)<=100:raise error('Use um nome de 2 a 100 caracteres.')
        if cover:
            asset=community_social.local_asset(cover,db(),error,owner=uid())
            if not asset or asset[1]!='image':raise error('Envie uma capa do dispositivo.')
            community_social.retain_assets(db(),cover)
        if db().execute('SELECT COUNT(*) FROM music_playlists WHERE user_id=?',(uid(),)).fetchone()[0]>=100:raise error('Limite de playlists atingido.',429)
        pid=secrets.token_urlsafe(9);db().execute('INSERT INTO music_playlists VALUES(?,?,?,?,?,?)',(pid,uid(),name,cover,int(d.get('public') is not False),time.time()));db().commit();return jsonify(id=pid),201

    @app.route('/api/music/playlists/<pid>',methods=['GET','PUT','DELETE'])
    @auth()
    def music_playlist_detail(pid):
        p=playlist(pid,request.method!='GET')
        if request.method=='DELETE':db().execute('DELETE FROM music_playlists WHERE id=?',(pid,));db().commit();return jsonify(ok=True)
        if request.method=='PUT':
            d=data();tracks=ids(d.get('tracks',[]))
            if len(set(tracks))!=len(tracks):raise error('A playlist já contém esta faixa.')
            db().execute('BEGIN IMMEDIATE');playlist(pid,True);db().execute('DELETE FROM music_playlist_tracks WHERE playlist_id=?',(pid,));db().executemany('INSERT INTO music_playlist_tracks VALUES(?,?,?)',[(pid,tid,i) for i,tid in enumerate(tracks)])
            if 'name' in d:
                name=str(d['name']).strip()
                if not 2<=len(name)<=100:raise error('Nome inválido.')
                db().execute('UPDATE music_playlists SET name=? WHERE id=?',(name,pid))
            if 'public' in d:db().execute('UPDATE music_playlists SET public=? WHERE id=?',(int(d['public'] is True),pid))
            db().commit();p=playlist(pid)
        p['tracks']=[dict(t) for t in db().execute('SELECT t.* FROM music_playlist_tracks p JOIN music_tracks t ON t.id=p.track_id WHERE p.playlist_id=? ORDER BY p.position',(pid,))];return jsonify(playlist=p)

    @app.route('/api/music/rooms/<rid>/state',methods=['GET','PATCH'])
    @auth()
    def music_room_state(rid):
        db().execute('BEGIN IMMEDIATE');room_lifecycle.repair(db(),rid);r=room(rid,request.method=='PATCH');ensure_room_tracks(db(),r);r=room(rid,request.method=='PATCH');now=time.time()
        db().execute("UPDATE community_members SET seen_at=?,mic=0,camera=0 WHERE room_id=? AND user_id=?",(now,rid,uid()))
        if request.method=='PATCH':
            d=data()
            if d.get('revision')!=r['revision']:raise error('O estado mudou. Sincronizando a sala.',409)
            action=d.get('action');rows=db().execute('SELECT * FROM community_queue WHERE room_id=? AND track_id IS NOT NULL ORDER BY position,id',(rid,)).fetchall();current=r['music_current'];pos=r['position']+(0 if r['paused'] else now-r['updated_at']);paused=r['paused']
            if action=='add':
                if len(rows)>=200:raise error('A fila aceita até 200 faixas.')
                track=get_track(d.get('track_id'));qid=db().execute('INSERT INTO community_queue(room_id,title,url,media_type,created_at,track_id,added_by,position) VALUES(?,?,?,?,?,?,?,?)',(rid,track['title'],track['url'],'soundcloud' if track['provider']=='soundcloud' else 'audio',now,track['id'],uid(),max([q['position'] for q in rows] or [-1])+1)).lastrowid
                if not current:current=qid;pos=0;paused=1
            elif action=='remove':
                qid=d.get('id');db().execute('DELETE FROM community_queue WHERE room_id=? AND id=?',(rid,qid))
                if qid==current:current=next((q['id'] for q in rows if q['id']!=qid),None);pos=0;paused=1
            elif action=='reorder':
                order=d.get('order',[])
                if not isinstance(order,list) or any(type(i) is not int for i in order) or len(order)!=len(rows) or len(set(order))!=len(order) or set(order)!={q['id'] for q in rows}:raise error('Ordem inválida.')
                db().executemany('UPDATE community_queue SET position=? WHERE room_id=? AND id=?',[(i,rid,q) for i,q in enumerate(order)])
            elif action=='ended':
                if d.get('media_epoch',r['media_epoch'])!=r['media_epoch']:raise error('A reprodução já avançou.',409)
                advance_finished(db(),r,now);value=room_snapshot(db(),rid);db().commit();return jsonify(room=value)
            elif action in ('next','previous','select'):
                if not rows:raise error('Adicione uma faixa à fila.')
                index=next((i for i,q in enumerate(rows) if q['id']==current),0)
                if action=='select':
                    if not any(q['id']==d.get('id') for q in rows):raise error('Faixa indisponível.')
                    current=d['id']
                elif r['music_shuffle'] and len(rows)>1:current=secrets.choice([q['id'] for q in rows if q['id']!=current])
                else:
                    target=index+(-1 if action=='previous' else 1)
                    current=rows[target%len(rows)]['id']
                pos=0
                paused=0
            elif action in ('play','pause','seek'):
                if not current:raise error('Adicione uma faixa à fila.')
                if action in ('play','pause'):paused=int(action=='pause')
                if 'position' in d:
                    pos=d['position']
                    if not isinstance(pos,(int,float)) or not 0<=pos<=86400:raise error('Posição inválida.')
            elif action=='mode':
                repeat=d.get('repeat',r['music_repeat'])
                if repeat not in ('off','one','all'):raise error('Modo inválido.')
                db().execute('UPDATE community_rooms SET music_repeat=?,music_shuffle=? WHERE id=?',(repeat,int(d.get('shuffle',bool(r['music_shuffle'])) is True),rid))
            elif action=='clear':db().execute('DELETE FROM community_queue WHERE room_id=?',(rid,));current=None;pos=0;paused=1
            else:raise error('Ação inválida.')
            q=db().execute('SELECT url,media_type FROM community_queue WHERE room_id=? AND id=?',(rid,current)).fetchone()
            db().execute('UPDATE community_rooms SET music_current=?,position=?,paused=?,updated_at=?,revision=revision+1,media_epoch=media_epoch+?,url=?,media_type=? WHERE id=?',(current,pos,paused,now,int(current!=r['music_current'] or action in ('next','previous','select','clear')),q['url'] if q else '',q['media_type'] if q else '',rid))
        value=room_snapshot(db(),rid);value['requests']=[dict(u) for u in db().execute("SELECT u.id,u.name,u.username,COALESCE(p.avatar,'') avatar FROM community_members m JOIN users u ON u.id=m.user_id LEFT JOIN community_profiles p ON p.user_id=u.id WHERE m.room_id=? AND m.status='pending' AND m.seen_at>?",(rid,now-120))] if value['host_id']==uid() else []
        after=max(0,int(request.args.get('after',0)));value['messages']=[dict(m) for m in db().execute('SELECT m.id,m.user_id,m.body,m.created_at,u.name,u.username,u.verified FROM community_messages m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.id>? ORDER BY m.id DESC LIMIT 60',(rid,after))][::-1];db().commit();return jsonify(room=value)

    @app.post('/api/music/rooms/<rid>/invite')
    @auth()
    def music_invite(rid):
        r=room(rid);other=data().get('user_id')
        if not db().execute("SELECT 1 FROM jump_friends WHERE status='accepted' AND ((sender=? AND recipient=?) OR (sender=? AND recipient=?))",(uid(),other,other,uid())).fetchone():raise error('Convide um amigo.',403)
        notify(db(),other,uid(),'Vamos ouvir juntos?',g.user['name']+' convidou você para '+r['title'],'/comunidade/sala/'+rid,'music-room:'+rid+':'+other,category='rooms');db().commit();return jsonify(ok=True)
