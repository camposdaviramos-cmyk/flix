"""Creation formats, publication controls and explainable community recommendations."""
import hashlib
import html
import json
import math
import re
import secrets
import time
from collections import Counter
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from flask import g, jsonify, request
import community_social


def migrate(db):
    for table,columns in {
        'community_posts':{'genre':"TEXT NOT NULL DEFAULT ''",'hide_likes':'INTEGER NOT NULL DEFAULT 0','hide_comments':'INTEGER NOT NULL DEFAULT 0','comments_disabled':'INTEGER NOT NULL DEFAULT 0'},
        'community_stories':{'thumbnail':"TEXT NOT NULL DEFAULT ''"},
        'community_comments':{'hidden':'INTEGER NOT NULL DEFAULT 0','edited_at':'REAL'},
    }.items():
        existing={r[1] for r in db.execute('PRAGMA table_info('+table+')')}
        for name,definition in columns.items():
            if name not in existing:db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS community_episodes(id TEXT PRIMARY KEY,post_id TEXT NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,season INTEGER NOT NULL,number INTEGER NOT NULL,title TEXT NOT NULL,url TEXT NOT NULL,UNIQUE(post_id,season,number));
    CREATE TABLE IF NOT EXISTS community_compositions(target_type TEXT NOT NULL,target_id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(target_type,target_id));
    CREATE TABLE IF NOT EXISTS community_feed_seen(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,post_id TEXT REFERENCES community_posts(id) ON DELETE CASCADE,seen_at REAL NOT NULL,hidden INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(user_id,post_id));
    CREATE TABLE IF NOT EXISTS community_feed_order(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,payload TEXT NOT NULL,created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS community_music_cache(query TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS community_music_searches(user_id TEXT,created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS community_comment_mentions(comment_id INTEGER REFERENCES community_comments(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,PRIMARY KEY(comment_id,user_id));
    ''')


def plain(value,maxlen,error,minimum=0):
    if not isinstance(value,str) or not minimum<=len(value.strip())<=maxlen:raise error('Preencha os textos dentro do limite indicado.')
    return value.strip()


def number(value,lo,hi,error):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:raise error('Ajuste de edição inválido.')
    return value


def validate_catalog(db,d,error,external):
    genre=plain(d.get('genre',''),80,error,1)
    episodes=d.get('episodes',[])
    def mp4(v):
        url,kind=external(v,error,media=True)
        if not urlsplit(url).path.lower().endswith('.mp4'):raise error('Use um link direto para um arquivo MP4.')
        return url
    if d['kind']=='movie':return genre,mp4(d.get('url','')),[]
    if not isinstance(episodes,list) or not 1<=len(episodes)<=200:raise error('Adicione de 1 a 200 episódios à série.')
    output=[];pairs=set();ids=set()
    for e in episodes:
        if not isinstance(e,dict):raise error('Episódio inválido.')
        season=e.get('season',1);num=e.get('number')
        if type(season) is not int or type(num) is not int or not 1<=season<=100 or not 1<=num<=1000 or (season,num) in pairs:raise error('Confira a temporada e o número de cada episódio, sem repetições.')
        pairs.add((season,num));eid=e.get('id') or secrets.token_hex(12)
        if not isinstance(eid,str) or not re.fullmatch('[a-zA-Z0-9_-]{1,64}',eid) or eid in ids:raise error('Identificador de episódio inválido.')
        ids.add(eid);old=db.execute('SELECT post_id FROM community_episodes WHERE id=?',(eid,)).fetchone()
        if old and old[0]!=d.get('id'):raise error('Episódio de outra publicação.',403)
        output.append({'id':eid,'season':season,'number':num,'title':plain(e.get('title') or f'Episódio {num}',160,error,1),'url':mp4(e.get('url',''))})
    output.sort(key=lambda e:(e['season'],e['number']))
    return genre,output[0]['url'],output


def composition(db,value,error,external,user):
    if not isinstance(value,dict):raise error('Edição inválida.')
    items=value.get('items',[]);layers=value.get('layers',[]);layout=value.get('layout','sequence')
    if not isinstance(items,list) or len(items)>8 or not isinstance(layers,list) or len(layers)>20 or layout not in ('sequence','grid','split'):raise error('Use até 8 mídias e 20 elementos na edição.')
    out={'version':1,'layout':layout,'items':[],'layers':[],'background':value.get('background','#201927'),'music':None}
    if not re.fullmatch('#[0-9a-fA-F]{6}',str(out['background'])):raise error('Cor inválida.')
    for item in items:
        if not isinstance(item,dict):raise error('Mídia inválida.')
        url=item.get('url','');kind=item.get('type')
        resolved=community_social.local_asset(url,db,error,owner=user) or external(url,error)
        if kind not in ('image','video') or (kind=='video' and resolved[1]!='video') or (kind=='image' and resolved[1] not in ('image','link')):raise error('Use fotos ou vídeos MP4/WebM na edição.')
        start=number(item.get('start',0),0,36000,error);duration=number(item.get('duration',5),1,180,error)
        out['items'].append({'url':resolved[0],'type':kind,'start':start,'duration':duration,'fit':item.get('fit') if item.get('fit') in ('cover','contain') else 'cover','x':number(item.get('x',50),0,100,error),'y':number(item.get('y',50),0,100,error),'zoom':number(item.get('zoom',1),1,3,error),'volume':number(item.get('volume',1),0,1,error),'speed':number(item.get('speed',1),.25,3,error),'brightness':number(item.get('brightness',1),.5,1.5,error),'contrast':number(item.get('contrast',1),.5,1.5,error),'transition':item.get('transition') if item.get('transition') in ('none','fade','slide') else 'none','filter':item.get('filter') if item.get('filter') in ('none','warm','cool','mono','vivid') else 'none'})
    for layer in layers:
        if not isinstance(layer,dict) or layer.get('type') not in ('text','link','emoji','mention'):raise error('Elemento inválido.')
        typ=layer['type'];text=plain(layer.get('text',''),240,error,1);color=layer.get('color','#ffffff');bg=layer.get('background','#141016')
        if not re.fullmatch('#[0-9a-fA-F]{6}',str(color)) or not re.fullmatch('#[0-9a-fA-F]{6}',str(bg)):raise error('Cor inválida.')
        obj={'type':typ,'text':text,'x':number(layer.get('x',50),0,100,error),'y':number(layer.get('y',50),0,100,error),'size':number(layer.get('size',28),14,72,error),'rotation':number(layer.get('rotation',0),-180,180,error),'color':color,'background':bg,'start':number(layer.get('start',0),0,1440,error),'end':number(layer.get('end',1440),0,1440,error)}
        if obj['end']<=obj['start']:raise error('O fim do elemento deve ser depois do início.')
        if typ=='link':obj['url']=external(layer.get('url',''),error)[0]
        if typ=='mention':
            person=db.execute("SELECT id,username FROM users WHERE id=? AND status='active'",(layer.get('user_id'),)).fetchone()
            if not person:raise error('Pessoa indisponível para mencionar.')
            obj.update(user_id=person['id'],text='@'+person['username'],url='/comunidade/perfil/'+person['username'])
        out['layers'].append(obj)
    drawings=value.get('drawings',[])
    if not isinstance(drawings,list) or len(drawings)>40:raise error('Use até 40 traços no desenho.')
    out['drawings']=[];total=0
    for line in drawings:
        if not isinstance(line,dict):raise error('Traço inválido.')
        pts=line.get('points',[]);color=line.get('color','#ffffff');total+=len(pts) if isinstance(pts,list) else 0
        if not isinstance(pts,list) or not 2<=len(pts)<=500 or total>5000 or not re.fullmatch('#[0-9a-fA-F]{6}',str(color)):raise error('Desenho inválido ou muito extenso.')
        if any(not isinstance(p,list) or len(p)!=2 for p in pts):raise error('Ponto inválido.')
        out['drawings'].append({'color':color,'width':number(line.get('width',1),.3,4,error),'points':[[number(p[0],0,100,error),number(p[1],0,100,error)] for p in pts]})
    music=value.get('music')
    if music:
        if not isinstance(music,dict):raise error('Música inválida.')
        url=music.get('url','');resolved=community_social.local_asset(url,db,error,owner=user) or external(url,error)
        if resolved[1] not in ('youtube','audio','soundcloud'):raise error('Escolha uma música do SoundCloud ou um arquivo de áudio.')
        out['music']={'url':resolved[0],'type':resolved[1],'title':plain(music.get('title','Música'),160,error,1),'start':number(music.get('start',0),0,36000,error),'volume':number(music.get('volume',.6),0,1,error)}
    if not out['items'] and not out['layers'] and not out['drawings']:raise error('Adicione uma foto, vídeo ou texto.')
    out['duration']=sum(i['duration'] for i in out['items']) if layout=='sequence' else max([i['duration'] for i in out['items']] or [15])
    if not out['duration']:out['duration']=15
    if out['duration']>180:raise error('A edição pode ter até 3 minutos. Reduza a duração das cenas.')
    return out


def save_composition(db,typ,target,value,expires=None):
    db.execute('INSERT INTO community_compositions VALUES(?,?,?) ON CONFLICT(target_type,target_id) DO UPDATE SET payload=excluded.payload',(typ,target,json.dumps(value)))
    for layer in value['layers']:
        if layer['type']!='mention':continue
        if typ=='post':
            p=db.execute('SELECT p.*,u.name FROM community_posts p JOIN users u ON u.id=p.user_id WHERE p.id=?',(target,)).fetchone()
            visible=not p['space_id'] or db.execute("SELECT 1 FROM social_spaces s WHERE s.id=? AND (s.privacy='public' OR EXISTS(SELECT 1 FROM social_space_members m WHERE m.space_id=s.id AND m.user_id=?))",(p['space_id'],layer['user_id'])).fetchone()
            href='/comunidade/post/'+target
        else:
            p=db.execute('SELECT s.*,u.name FROM community_stories s JOIN users u ON u.id=s.user_id WHERE s.id=?',(target,)).fetchone();visible=True;href='/comunidade?story='+target
        if p and visible and p['user_id']!=layer['user_id']:
            db.execute("INSERT OR IGNORE INTO hub_notifications(user_id,actor_id,category,title,body,href,created_at,dedupe) VALUES(?,?,'social','Você foi mencionado',?,?,?,?)",(layer['user_id'],p['user_id'],p['name']+' mencionou você em um '+('story' if typ=='story' else 'reel'),href,time.time(),'composition-mention:'+typ+':'+target))
    urls=[i['url'] for i in value['items']]+([value['music']['url']] if value['music'] else [])
    for url in urls:
        if url.startswith('/api/community/assets/'):
            if expires and not community_social.permanent_asset(db,url):db.execute('UPDATE community_assets SET expires_at=? WHERE id=?',(expires,url.rsplit('/',1)[-1]))
            elif not expires:community_social.retain_assets(db,url)


def enrich(db,p,viewer):
    p['episodes']=[dict(r) for r in db.execute('SELECT * FROM community_episodes WHERE post_id=? ORDER BY season,number',(p['id'],))]
    row=db.execute("SELECT payload FROM community_compositions WHERE target_type='post' AND target_id=?",(p['id'],)).fetchone();p['composition']=json.loads(row[0]) if row else None
    comments=visible_comments(db,p,viewer,limit=1);p['latest_comment']=comments[0] if comments else None
    if p['hide_likes']:p['likes']=None;p['reactions']['counts']={}
    if p['hide_comments'] and p['user_id']!=viewer:p['comments']=None;p['latest_comment']=None
    return p


def visible_comments(db,p,user,limit=100):
    if p['hide_comments'] and p['user_id']!=user:return []
    return [dict(r) for r in db.execute('''SELECT c.*,u.name,u.username,u.verified,COALESCE(pr.avatar,'') avatar FROM community_comments c JOIN users u ON u.id=c.user_id LEFT JOIN community_profiles pr ON pr.user_id=u.id WHERE c.post_id=? AND u.status='active' AND (c.hidden=0 OR ?=? OR c.user_id=?) ORDER BY c.id DESC LIMIT ?''',(p['id'],user,p['user_id'],user,limit))]


def notify_mentions(db,cid,p,body,actor):
    usernames=list(dict.fromkeys(re.findall(r'(?<![\w@])@([a-zA-Z0-9_]{3,24})',body)))[:10]
    for username in usernames:
        r=db.execute("SELECT u.id FROM users u JOIN jump_friends f ON (f.sender=? AND f.recipient=u.id) OR (f.recipient=? AND f.sender=u.id) WHERE u.username=? COLLATE NOCASE AND u.status='active' AND f.status='accepted'",(actor,actor,username)).fetchone()
        if not r or r[0]==actor:continue
        if p['space_id'] and not db.execute("SELECT 1 FROM social_spaces ss WHERE ss.id=? AND (ss.privacy='public' OR EXISTS(SELECT 1 FROM social_space_members sm WHERE sm.space_id=ss.id AND sm.user_id=?))",(p['space_id'],r[0])).fetchone():continue
        new=db.execute('INSERT OR IGNORE INTO community_comment_mentions VALUES(?,?)',(cid,r[0]))
        if new.rowcount and p['status']=='published' and not p['hide_comments']:
            db.execute("INSERT OR IGNORE INTO hub_notifications(user_id,actor_id,category,title,body,href,created_at,dedupe) VALUES(?,?,'social','Você foi mencionado',?,'/comunidade/post/'||?,?,'comment-mention:'||?)",(r[0],actor,'Uma conversa em '+p['title']+' mencionou você.',p['id'],time.time(),str(cid)))


def recommendation_order(db,user):
    now=time.time();cached=db.execute('SELECT * FROM community_feed_order WHERE user_id=?',(user,)).fetchone()
    if cached and cached['created_at']>now-900:return json.loads(cached['payload'])
    items=[dict(r) for r in db.execute("""SELECT p.id,p.kind,p.genre,p.user_id,p.created_at,p.featured,
      (SELECT COUNT(*) FROM community_likes WHERE post_id=p.id) likes,
      (SELECT COUNT(*) FROM community_comments WHERE post_id=p.id AND hidden=0) comments,
      (SELECT COUNT(*) FROM community_views WHERE post_id=p.id) views
      FROM community_posts p JOIN users u ON u.id=p.user_id WHERE p.status='published' AND u.status='active' AND (p.space_id IS NULL OR EXISTS(SELECT 1 FROM social_spaces ss WHERE ss.id=p.space_id AND ss.status='active' AND (ss.privacy='public' OR EXISTS(SELECT 1 FROM social_space_members sm WHERE sm.space_id=ss.id AND sm.user_id=?)))) ORDER BY p.created_at DESC LIMIT 600""",(user,))]
    following={r[0] for r in db.execute('SELECT following FROM community_follows WHERE follower=?',(user,))}
    seen={r['post_id']:dict(r) for r in db.execute('SELECT * FROM community_feed_seen WHERE user_id=?',(user,))}
    interests=Counter();genres=Counter();profile=db.execute('SELECT favorite_genres FROM community_profiles WHERE user_id=?',(user,)).fetchone()
    for genre in re.split(r'[,;/]',profile[0] if profile else ''):
        if genre.strip():genres[genre.strip().casefold()]+=5
    history=db.execute('''SELECT p.kind,p.genre FROM community_posts p WHERE p.id IN (SELECT post_id FROM community_likes WHERE user_id=? UNION SELECT post_id FROM community_views WHERE user_id=? UNION SELECT post_id FROM community_comments WHERE user_id=? UNION SELECT target_id FROM hub_watch WHERE user_id=? AND source='community') ORDER BY p.created_at DESC LIMIT 100''',(user,user,user,user))
    for r in history:
        interests[r['kind']]+=1
        for genre in re.split(r'[,;/]',r['genre']):
            if genre.strip():genres[genre.strip().casefold()]+=1
    for r in db.execute('SELECT c.genre FROM watch_history h JOIN content c ON c.id=h.content_id WHERE h.user_id=? ORDER BY h.watched_at DESC LIMIT 50',(user,)):
        for genre in re.split(r'[,;/]',r[0] or ''):
            if genre.strip():genres[genre.strip().casefold()]+=1
    def score(p):
        age=max(0,(now-p['created_at'])/3600);engagement=min(8,math.log1p(p['likes']*2+p['comments']*2+p['views']*.25))
        interest=min(4,math.log1p(interests[p['kind']]))+min(5,sum(math.log1p(genres[g.strip().casefold()]) for g in re.split(r'[,;/]',p['genre'])))
        fresh=5/(1+age/36);novel=1.8 if p['id'] not in seen else -.8
        explore=int(hashlib.sha256((user+p['id']+str(int(now/86400))).encode()).hexdigest()[:4],16)/65535
        return fresh+engagement/(1+age/168)+interest+(3 if p['user_id'] in following else 0)+novel+explore+(0.5 if p['featured'] else 0)
    pool=sorted((p for p in items if not seen.get(p['id'],{}).get('hidden')),key=lambda p:(-score(p),p['id']))
    output=[];authors=[]
    while pool:
        index=next((i for i,p in enumerate(pool) if authors[-5:].count(p['user_id'])<2),0)
        p=pool.pop(index);output.append(p['id']);authors.append(p['user_id'])
    db.execute('INSERT INTO community_feed_order VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET payload=excluded.payload,created_at=excluded.created_at',(user,json.dumps(output),now));db.commit()
    return output


def register(app,db,auth,data,error,post):
    @app.patch('/api/community/posts/<pid>/controls')
    @auth()
    def publication_controls(pid):
        db().execute('BEGIN IMMEDIATE');p=post(pid,True)
        if p['user_id']!=g.user['id']:raise error('Somente o autor pode alterar estas preferências.',403)
        d=data()
        if 'status' in d:
            if d['status'] not in ('published','private','archived'):raise error('Visibilidade inválida.')
            if p['status'] not in ('published','private','archived'):raise error('Uma publicação removida pela moderação não pode ser restaurada.',403)
            db().execute('UPDATE community_posts SET status=?,updated_at=? WHERE id=?',(d['status'],time.time(),pid))
            if d['status']!='published':
                db().execute("UPDATE community_rooms SET status='closed',paused=1,revision=revision+1 WHERE post_id=? AND status='open'",(pid,))
                db().execute("DELETE FROM hub_notifications WHERE href=?",('/comunidade/post/'+pid,))
        for key in ('hide_likes','hide_comments','comments_disabled'):
            if key in d:
                if type(d[key]) is not bool:raise error('Preferência inválida.')
                db().execute(f'UPDATE community_posts SET {key}=? WHERE id=?',(int(d[key]),pid))
        db().commit();return jsonify(ok=True)

    @app.patch('/api/community/comments/<int:cid>')
    @auth()
    def edit_comment(cid):
        db().execute('BEGIN IMMEDIATE');c=db().execute('SELECT * FROM community_comments WHERE id=?',(cid,)).fetchone()
        if not c:raise error('Comentário indisponível.',404)
        p=post(c['post_id'],True);d=data();me=g.user['id']
        if 'body' in d:
            if c['user_id']!=me:raise error('Você só pode editar seus comentários.',403)
            if p['comments_disabled']:raise error('Os comentários desta publicação foram desativados.',403)
            body=plain(d['body'],1500,error,1);db().execute('UPDATE community_comments SET body=?,edited_at=? WHERE id=?',(body,time.time(),cid));notify_mentions(db(),cid,p,body,me)
        if 'hidden' in d:
            if p['user_id']!=me:raise error('Somente o dono da publicação pode ocultar comentários.',403)
            if type(d['hidden']) is not bool:raise error('Preferência inválida.')
            db().execute('UPDATE community_comments SET hidden=? WHERE id=?',(int(d['hidden']),cid))
        db().commit();return jsonify(ok=True)

    @app.post('/api/community/feed/feedback')
    @auth()
    def feed_feedback():
        d=data();ids=d.get('ids',[]);hidden=d.get('hidden',False)
        if not isinstance(ids,list) or len(ids)>20 or any(not isinstance(i,str) or len(i)>64 for i in ids) or type(hidden) is not bool:raise error('Feedback inválido.')
        for pid in ids:
            if db().execute("SELECT 1 FROM community_posts WHERE id=? AND status='published'",(pid,)).fetchone():
                db().execute('INSERT INTO community_feed_seen VALUES(?,?,?,?) ON CONFLICT(user_id,post_id) DO UPDATE SET seen_at=excluded.seen_at,hidden=MAX(hidden,excluded.hidden)',(g.user['id'],pid,time.time(),int(hidden)))
        if hidden:db().execute('DELETE FROM community_feed_order WHERE user_id=?',(g.user['id'],))
        db().commit();return jsonify(ok=True)


def register_music(app,db,auth,error,setting):
    @app.get('/api/community/music/search')
    @auth()
    def music_search():
        q=request.args.get('q','').strip()[:100]
        if len(q)<2:return jsonify(items=[])
        key=setting('youtube_api_key')
        if not key:return jsonify(items=[],configured=False,message='A busca de músicas será liberada quando o administrador conectar o YouTube. Você já pode colar um link ou enviar um áudio.')
        cached=db().execute('SELECT * FROM community_music_cache WHERE query=? AND created_at>?',(q.casefold(),time.time()-3600)).fetchone()
        if cached:return jsonify(items=json.loads(cached['payload']),configured=True)
        db().execute('BEGIN IMMEDIATE');db().execute('DELETE FROM community_music_searches WHERE created_at<?',(time.time()-3600,))
        if db().execute('SELECT COUNT(*) FROM community_music_searches WHERE user_id=?',(g.user['id'],)).fetchone()[0]>=20:raise error('Aguarde antes de pesquisar mais músicas.',429)
        db().execute('INSERT INTO community_music_searches VALUES(?,?)',(g.user['id'],time.time()));db().commit()
        query=urlencode({'part':'snippet','q':q,'type':'video','videoCategoryId':'10','videoEmbeddable':'true','safeSearch':'moderate','maxResults':8,'key':key})
        try:
            with urlopen(Request('https://www.googleapis.com/youtube/v3/search?'+query,headers={'Accept':'application/json'}),timeout=8) as response:payload=json.loads(response.read(200000))
        except (HTTPError,URLError,TimeoutError,ValueError):raise error('A busca do YouTube está indisponível. Confira a chave e a cota da integração no painel.',502)
        items=[]
        for item in payload.get('items',[]):
            vid=item.get('id',{}).get('videoId','');snippet=item.get('snippet',{})
            if re.fullmatch(r'[a-zA-Z0-9_-]{11}',vid):items.append({'id':vid,'url':'https://www.youtube.com/watch?v='+vid,'title':html.unescape(snippet.get('title','Música'))[:160],'artist':html.unescape(snippet.get('channelTitle',''))[:160],'image':'https://i.ytimg.com/vi/'+vid+'/mqdefault.jpg'})
        db().execute('INSERT INTO community_music_cache VALUES(?,?,?) ON CONFLICT(query) DO UPDATE SET payload=excluded.payload,created_at=excluded.created_at',(q.casefold(),json.dumps(items),time.time()));db().execute('DELETE FROM community_music_cache WHERE created_at<?',(time.time()-86400,));db().commit()
        return jsonify(items=items,configured=True)
