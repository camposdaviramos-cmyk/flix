"""Single-video Reels, publication controls, audience and curated playlists."""
import json,re,secrets,time
from flask import g,jsonify,request

DEFAULTS={'audience':'public','comments':'all','remix':True,'reuse_feed':True,'ai_label':False,'brand':'','quality':'high','download':False,'dubbing':True,'playlist':'','location':'','topics':[],'people':[],'alt':'','share_external':False}

def visibility(alias='p',viewer='?'):
    return f"({alias}.user_id={viewer} OR {alias}.reel_audience='public' OR ({alias}.reel_audience='friends' AND EXISTS(SELECT 1 FROM jump_friends rf WHERE rf.status='accepted' AND ((rf.sender={alias}.user_id AND rf.recipient={viewer}) OR (rf.recipient={alias}.user_id AND rf.sender={viewer})))))"

def migrate(db):
    cols={r[1] for r in db.execute('PRAGMA table_info(community_posts)')}
    for key,value in {'reel_audience':"TEXT NOT NULL DEFAULT 'public'",'reel_feed':'INTEGER NOT NULL DEFAULT 1'}.items():
        if key not in cols:db.execute('ALTER TABLE community_posts ADD COLUMN '+key+' '+value)
    db.executescript('''
    CREATE TABLE IF NOT EXISTS reel_settings(post_id TEXT PRIMARY KEY REFERENCES community_posts(id) ON DELETE CASCADE,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS reel_playlists(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS reel_playlist_items(playlist_id TEXT REFERENCES reel_playlists(id) ON DELETE CASCADE,post_id TEXT REFERENCES community_posts(id) ON DELETE CASCADE,PRIMARY KEY(playlist_id,post_id));
    CREATE TABLE IF NOT EXISTS reel_answers(post_id TEXT REFERENCES community_posts(id) ON DELETE CASCADE,layer_id TEXT,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,value TEXT,created_at REAL,PRIMARY KEY(post_id,layer_id,user_id));
    CREATE TABLE IF NOT EXISTS reel_publish_keys(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,request_id TEXT,post_id TEXT REFERENCES community_posts(id) ON DELETE CASCADE,PRIMARY KEY(user_id,request_id));
    ''')
    # Keep existing notification triggers and their space restrictions; add audience checks.
    for name,needle,extra in [
        ('hub_publication','WHERE f.following=NEW.user_id',visibility('NEW','f.follower')),
        ('hub_mention_insert','WHERE j.value!=p.user_id',"p.status='published' AND "+visibility('p','j.value')),
        ('hub_mention_update','WHERE j.value!=p.user_id',"p.status='published' AND "+visibility('p','j.value')),
    ]:
        row=db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",(name,)).fetchone()
        if row and 'reel_audience' not in row[0]:
            sql=row[0].replace(needle,needle+' AND '+extra);db.execute('DROP TRIGGER '+name);db.execute(sql)

def visible(db,pid,user):
    return bool(db.execute('SELECT 1 FROM community_posts p WHERE p.id=? AND '+visibility(),(pid,user,user,user)).fetchone())

def options(db,payload,user,error):
    if not isinstance(payload,dict):raise error('Configurações do Reel inválidas.')
    out={**DEFAULTS,**{k:v for k,v in payload.items() if k in DEFAULTS}}
    for key in ['remix','reuse_feed','ai_label','download','dubbing','share_external']:
        if type(out[key]) is not bool:raise error('Opção do Reel inválida.')
    for key,values in [('audience',('public','friends','private')),('comments',('all','friends','off')),('quality',('high','standard'))]:
        if out[key] not in values:raise error('Configuração do Reel inválida.')
    for key,limit in [('location',100),('brand',100),('playlist',64),('alt',1000)]:
        if not isinstance(out[key],str) or len(out[key])>limit:raise error('Texto da publicação muito longo.')
        out[key]=out[key].strip()
    if not isinstance(out['topics'],list) or len(out['topics'])>5 or any(not isinstance(t,str) or not 1<=len(t.strip())<=40 for t in out['topics']):raise error('Escolha até 5 temas, com até 40 caracteres cada.')
    out['topics']=list(dict.fromkeys(t.strip().lstrip('#') for t in out['topics']))
    if not isinstance(out['people'],list) or len(out['people'])>20 or any(not isinstance(t,str) for t in out['people']):raise error('Marque até 20 pessoas.')
    out['people']=list(dict.fromkeys(out['people']))
    for person in out['people']:
        if not db.execute("SELECT 1 FROM users WHERE id=? AND status='active'",(person,)).fetchone():raise error('Pessoa não encontrada.')
    if out['playlist'] and not db.execute('SELECT 1 FROM reel_playlists WHERE id=? AND user_id=?',(out['playlist'],user)).fetchone():raise error('Escolha uma playlist sua.',403)
    return out

def validate(comp,body,error):
    if not comp or len(comp['items'])!=1 or comp['items'][0]['type']!='video' or comp['layout']!='sequence':raise error('Cada Reel precisa de um único vídeo. Abra o editor para selecionar ou gravar.')
    if comp['duration']>60:raise error('O Reel pode ter no máximo 60 segundos. Escolha um trecho menor.')
    if len(body)>2200:raise error('A descrição pode ter até 2.200 caracteres.')
    comp.update(version=2,format='reel');comp['items'][0]['fit']='cover';comp['items'][0]['transition']='none'

def save(db,pid,opts,user):
    db.execute('INSERT INTO reel_settings VALUES(?,?) ON CONFLICT(post_id) DO UPDATE SET payload=excluded.payload',(pid,json.dumps(opts)))
    db.execute('UPDATE community_posts SET reel_audience=?,reel_feed=?,comments_disabled=? WHERE id=?',(opts['audience'],int(opts['reuse_feed']),int(opts['comments']=='off'),pid))
    db.execute('DELETE FROM reel_playlist_items WHERE post_id=?',(pid,))
    if opts['playlist']:db.execute('INSERT INTO reel_playlist_items VALUES(?,?)',(opts['playlist'],pid))

def notify_people(db,pid):
    p=db.execute("SELECT p.*,u.name FROM community_posts p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.status='published'",(pid,)).fetchone()
    if not p:return
    for person in get_options(db,pid)['people']:
        if person==p['user_id'] or not visible(db,pid,person):continue
        if p['space_id'] and not db.execute("SELECT 1 FROM social_spaces s WHERE s.id=? AND s.status='active' AND (s.privacy='public' OR EXISTS(SELECT 1 FROM social_space_members m WHERE m.space_id=s.id AND m.user_id=?))",(p['space_id'],person)).fetchone():continue
        db.execute("INSERT OR IGNORE INTO hub_notifications(user_id,actor_id,category,title,body,href,created_at,dedupe) VALUES(?,?,'social','Você foi marcado',?,?,?,?)",(person,p['user_id'],p['name']+' marcou você em um Reel.','/comunidade/post/'+pid,time.time(),'reel-tag:'+pid))

def get_options(db,pid):
    row=db.execute('SELECT payload FROM reel_settings WHERE post_id=?',(pid,)).fetchone()
    return {**DEFAULTS,**(json.loads(row[0]) if row else {})}

def can_comment(db,p,user):
    if p['comments_disabled']:return False
    if p['kind']!='reel' or p['user_id']==user:return True
    mode=get_options(db,p['id'])['comments']
    return mode=='all' or (mode=='friends' and bool(db.execute("SELECT 1 FROM jump_friends WHERE status='accepted' AND ((sender=? AND recipient=?) OR (recipient=? AND sender=?))",(p['user_id'],user,p['user_id'],user)).fetchone()))

def enrich(db,p,user):
    if p['kind']=='reel':
        p['reel_options']=get_options(db,p['id']);p['can_comment']=can_comment(db,p,user)
        p['reel_people']=[dict(r) for r in db.execute("SELECT id,name,username FROM users WHERE id IN (SELECT value FROM json_each(?)) AND status='active'",(json.dumps(p['reel_options']['people']),))]

def register(app,db,auth,data,error,post,post_list):
    @app.route('/api/community/reel-playlists',methods=['GET','POST'])
    @auth()
    def playlists():
        if request.method=='POST':
            name=data().get('name','')
            if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise error('Dê um nome à playlist, com até 80 caracteres.')
            if db().execute('SELECT COUNT(*) FROM reel_playlists WHERE user_id=?',(g.user['id'],)).fetchone()[0]>=50:raise error('Use até 50 playlists.')
            pid=secrets.token_urlsafe(9);db().execute('INSERT INTO reel_playlists VALUES(?,?,?,?)',(pid,g.user['id'],name.strip(),time.time()));db().commit()
        return jsonify(playlists=[dict(r) for r in db().execute('SELECT p.*,(SELECT COUNT(*) FROM reel_playlist_items i WHERE i.playlist_id=p.id) reels FROM reel_playlists p WHERE user_id=? ORDER BY created_at DESC',(g.user['id'],))])

    @app.get('/api/community/reel-playlists/<pid>')
    @auth()
    def playlist(pid):
        row=db().execute('SELECT * FROM reel_playlists WHERE id=?',(pid,)).fetchone()
        if not row:raise error('Playlist não encontrada.',404)
        return jsonify(playlist=dict(row),posts=post_list('p.id IN (SELECT post_id FROM reel_playlist_items WHERE playlist_id=?)',(pid,),include_own=True))

    @app.get('/api/community/reels/<pid>/permissions/<action>')
    @auth()
    def permission(pid,action):
        p=post(pid);opts=get_options(db(),pid)
        if p['kind']!='reel' or action not in ('remix','download','dubbing'):raise error('Opção indisponível.',404)
        if p['user_id']!=g.user['id'] and not opts[action]:raise error('O autor não permite esta ação neste Reel.',403)
        row=db().execute("SELECT payload FROM community_compositions WHERE target_type='post' AND target_id=?",(pid,)).fetchone()
        return jsonify(allowed=True,composition=json.loads(row[0]) if row else None,url=p['url'])

    @app.route('/api/community/reels/<pid>/stickers/<lid>',methods=['GET','POST'])
    @auth()
    def sticker(pid,lid):
        p=post(pid);row=db().execute("SELECT payload FROM community_compositions WHERE target_type='post' AND target_id=?",(pid,)).fetchone()
        layer=next((l for l in json.loads(row[0])['layers'] if l.get('id')==lid and l['type'] in ('poll','question')),None) if row else None
        if not layer:raise error('Figurinha indisponível.',404)
        if request.method=='POST':
            value=data().get('value')
            if layer['type']=='poll':
                if type(value) is not int or not 0<=value<len(layer['options']):raise error('Escolha uma opção válida.')
            elif not isinstance(value,str) or not 1<=len(value.strip())<=240:raise error('Use uma resposta de até 240 caracteres.')
            else:value=value.strip()
            db().execute('INSERT INTO reel_answers VALUES(?,?,?,?,?) ON CONFLICT(post_id,layer_id,user_id) DO UPDATE SET value=excluded.value,created_at=excluded.created_at',(pid,lid,g.user['id'],json.dumps(value),time.time()));db().commit()
        mine=db().execute('SELECT value FROM reel_answers WHERE post_id=? AND layer_id=? AND user_id=?',(pid,lid,g.user['id'])).fetchone();result={'mine':json.loads(mine[0]) if mine else None}
        if layer['type']=='poll':result['counts']=[db().execute('SELECT COUNT(*) FROM reel_answers WHERE post_id=? AND layer_id=? AND value=?',(pid,lid,json.dumps(i))).fetchone()[0] for i in range(len(layer['options']))]
        elif p['user_id']==g.user['id']:result['answers']=[dict(r) for r in db().execute('SELECT a.value,u.username FROM reel_answers a JOIN users u ON u.id=a.user_id WHERE a.post_id=? AND a.layer_id=?',(pid,lid))]
        return jsonify(result)
