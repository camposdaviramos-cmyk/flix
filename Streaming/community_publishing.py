"""Structured community documents, private drafts, mentions and game discovery."""
import json
import re
import secrets
import time
from flask import g, jsonify, request
import community_social

KINDS=('discussion','movie','series','channel','news','music','reel')


def migrate(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS community_post_meta(
      post_id TEXT PRIMARY KEY REFERENCES community_posts(id) ON DELETE CASCADE,
      document TEXT NOT NULL DEFAULT '[]',people TEXT NOT NULL DEFAULT '[]',titles TEXT NOT NULL DEFAULT '[]',room_id TEXT);
    CREATE TABLE IF NOT EXISTS community_drafts(
      id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      payload TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,updated_at REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS community_draft_owner ON community_drafts(user_id,updated_at);
    ''')
    cols={r[1] for r in db.execute('PRAGMA table_info(community_rooms)')}
    if 'cover' not in cols:db.execute("ALTER TABLE community_rooms ADD COLUMN cover TEXT NOT NULL DEFAULT ''")


def checked_url(value,db,error,external_url,image=False,optional=False):
    result=community_social.local_asset(value,db,error)
    if result:
        if image and result[1]!='image':raise error('Escolha uma imagem para a capa.')
        return result
    url,kind=external_url(value,error,optional=optional)
    if image and url and kind not in ('link','image'):raise error('Escolha uma imagem para a capa.')
    return url, 'image' if image and url else kind


def validate(payload,db,error,external_url,partial=False):
    document=payload.get('document',[])
    if not isinstance(document,list) or len(document)>32:raise error('Use até 32 blocos na publicação.')
    media_count=0;char_count=0;urls=[];out=[]
    def plain(value,limit):
        if not isinstance(value,str) or len(value)>limit:raise error('Texto do bloco inválido ou muito longo.')
        return value
    def runs(value):
        nonlocal char_count
        if not isinstance(value,list) or len(value)>160:raise error('Formatação inválida.')
        result=[]
        for r in value:
            if not isinstance(r,dict):raise error('Texto inválido.')
            text=plain(r.get('text',''),6000);char_count+=len(text)
            if char_count>20000:raise error('Use até 20.000 caracteres no documento.')
            marks=r.get('marks',[])
            if not isinstance(marks,list) or any(m not in ('bold','italic') for m in marks):raise error('Formatação não permitida.')
            item={'text':text,'marks':list(dict.fromkeys(marks))}
            if r.get('href'):
                href=plain(r['href'],2000)
                if re.fullmatch(r'/(?:comunidade/(?:post|sala)/[A-Za-z0-9_-]{12}|comunidade/perfil/[A-Za-z0-9_]{3,24}|titulo/[A-Za-z0-9_-]{1,100})',href):item['href']=href
                else:item['href']=external_url(href,error)[0]
            if text:result.append(item)
        return result
    for b in document:
        if not isinstance(b,dict):raise error('Bloco inválido.')
        typ=b.get('type');item={'type':typ}
        if typ in ('paragraph','heading','quote','list'):
            item['content']=runs(b.get('content',[]))
        elif typ=='divider':pass
        elif typ in ('image','video','audio'):
            media_count+=1
            if media_count>8:raise error('Use até 8 anexos por publicação.')
            value=plain(b.get('url',''),2000)
            if not value and partial:continue
            url,kind=checked_url(value,db,error,external_url,image=typ=='image')
            if typ=='video' and kind not in ('video','youtube','hls'):raise error('Use MP4, WebM, YouTube ou M3U8 para o vídeo.')
            if typ=='audio' and kind!='audio':raise error('Use MP3, M4A, OGG ou WAV para áudio e música.')
            item.update(url=url,media_type=kind,caption=plain(b.get('caption',''),240))
            urls.append(url)
        else:raise error('Tipo de bloco não permitido.')
        out.append(item)
    people=payload.get('people',[]);titles=payload.get('titles',[])
    if not isinstance(people,list) or not isinstance(titles,list) or len(people)>10 or len(titles)>10:raise error('Marque até 10 pessoas e 10 títulos.')
    people_out=[];titles_out=[]
    for pid in people:
        if not isinstance(pid,str) or not db.execute("SELECT 1 FROM users WHERE id=? AND status='active'",(pid,)).fetchone():raise error('Pessoa marcada indisponível.')
        if pid not in people_out:people_out.append(pid)
    for ref in titles:
        if not isinstance(ref,dict) or not isinstance(ref.get('id'),str):raise error('Título marcado inválido.')
        source=ref.get('source');tid=ref['id']
        if source=='catalog':row=db.execute("SELECT 1 FROM content WHERE id=? AND published=1 AND kind IN ('movie','series','channel')",(tid,)).fetchone()
        elif source=='community':row=db.execute("SELECT 1 FROM community_posts p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.status='published' AND u.status='active' AND (p.space_id IS NULL OR EXISTS(SELECT 1 FROM social_spaces ss WHERE ss.id=p.space_id AND ss.privacy='public' AND ss.status='active')) AND p.kind IN ('movie','series','channel')",(tid,)).fetchone()
        else:row=None
        if not row:raise error('Título marcado indisponível.')
        value={'source':source,'id':tid}
        if value not in titles_out:titles_out.append(value)
    return {'document':out,'people':people_out,'titles':titles_out},urls


def resolved_references(db,people,titles):
    p={'people':[],'titles':[]}
    for uid in people:
        u=db.execute("SELECT u.id,u.name,u.username,u.verified,COALESCE(pr.avatar,'') avatar FROM users u LEFT JOIN community_profiles pr ON pr.user_id=u.id WHERE u.id=? AND u.status='active'",(uid,)).fetchone()
        if u:p['people'].append(dict(u))
    for ref in titles:
        if ref['source']=='catalog':r=db.execute("SELECT id,title,kind,poster FROM content WHERE id=? AND published=1",(ref['id'],)).fetchone()
        else:r=db.execute("SELECT p.id,p.title,p.kind,p.poster FROM community_posts p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.status='published' AND u.status='active'",(ref['id'],)).fetchone()
        if r:p['titles'].append({**dict(r),'source':ref['source']})
    return p


def enrich(db,p):
    row=db.execute('SELECT * FROM community_post_meta WHERE post_id=?',(p['id'],)).fetchone()
    p.update(document=[],people=[],titles=[],room=None)
    if not row:return p
    p['document']=json.loads(row['document'])
    p.update(resolved_references(db,json.loads(row['people']),json.loads(row['titles'])))
    if row['room_id']:
        r=db.execute('SELECT id,title,kind,status,cover FROM community_rooms WHERE id=?',(row['room_id'],)).fetchone()
        if r:p['room']=dict(r)
    return p


def save(db,pid,meta,urls):
    db.execute('INSERT INTO community_post_meta(post_id,document,people,titles) VALUES(?,?,?,?) ON CONFLICT(post_id) DO UPDATE SET document=excluded.document,people=excluded.people,titles=excluded.titles',
               (pid,json.dumps(meta['document']),json.dumps(meta['people']),json.dumps(meta['titles'])))
    community_social.retain_assets(db,*urls)


def game_rank(db,uid,kind='all'):
    if kind not in ('all','colors','draw'):kind='all'
    query='''SELECT u.id,u.name,u.username,u.verified,COALESCE(p.avatar,'') avatar,
      SUM(r.points) points,SUM(r.won) wins,COUNT(*) games
      FROM community_game_results r JOIN users u ON u.id=r.user_id
      LEFT JOIN community_profiles p ON p.user_id=u.id
      WHERE u.status='active' AND (?='all' OR r.kind=?)
      GROUP BY u.id ORDER BY points DESC,wins DESC,games DESC,u.username ASC'''
    ranked=[dict(r) for r in db.execute(query,(kind,kind))]
    for i,u in enumerate(ranked):u['position']=i+1
    return {'leaders':ranked[:5],'me':next((u for u in ranked if u['id']==uid),None),'kind':kind,'total':len(ranked)}


def register(app,db,auth,data,error,external_url):
    @app.get('/api/community/publishing/search')
    @auth()
    def publishing_search():
        q='%'+request.args.get('q','')[:100].strip().lstrip('@')+'%';kind=request.args.get('kind','people')
        if kind=='people':items=[dict(r) for r in db().execute("SELECT u.id,u.name,u.username,u.verified,COALESCE(p.avatar,'') avatar FROM users u LEFT JOIN community_profiles p ON p.user_id=u.id WHERE u.status='active' AND (u.username LIKE ? OR u.name LIKE ?) ORDER BY u.name LIMIT 10",(q,q))]
        elif kind=='titles':
            items=[{**dict(r),'source':'catalog'} for r in db().execute("SELECT id,title,kind,poster FROM content WHERE published=1 AND kind IN ('movie','series','channel') AND title LIKE ? ORDER BY title LIMIT 8",(q,))]
            items += [{**dict(r),'source':'community'} for r in db().execute("SELECT p.id,p.title,p.kind,p.poster,u.username FROM community_posts p JOIN users u ON u.id=p.user_id WHERE p.status='published' AND u.status='active' AND (p.space_id IS NULL OR EXISTS(SELECT 1 FROM social_spaces ss WHERE ss.id=p.space_id AND ss.privacy='public' AND ss.status='active')) AND p.kind IN ('movie','series','channel') AND p.title LIKE ? ORDER BY p.created_at DESC LIMIT 8",(q,))]
        else:raise error('Busca inválida.')
        return jsonify(items=items)

    @app.get('/api/community/games/ranking')
    @auth()
    def ranking():return jsonify(game_rank(db(),g.user['id'],request.args.get('kind','all')))

    @app.route('/api/community/drafts',methods=['GET','POST'])
    @app.route('/api/community/drafts/<did>',methods=['GET','PUT','DELETE'])
    @auth()
    def drafts(did=None):
        uid=g.user['id']
        if request.method=='GET' and not did:
            return jsonify(drafts=[{'id':r['id'],'revision':r['revision'],'updated_at':r['updated_at'],'title':json.loads(r['payload']).get('title','')} for r in db().execute('SELECT * FROM community_drafts WHERE user_id=? ORDER BY updated_at DESC',(uid,))])
        db().execute('BEGIN IMMEDIATE')
        old=db().execute('SELECT * FROM community_drafts WHERE id=? AND user_id=?',(did,uid)).fetchone() if did else None
        if did and not old:raise error('Rascunho não encontrado.',404)
        if request.method=='GET':
            draft=json.loads(old['payload']);draft.update(resolved_references(db(),draft['people'],draft['titles']));db().commit()
            return jsonify(draft={**draft,'draft_id':did,'revision':old['revision']})
        if request.method=='DELETE':db().execute('DELETE FROM community_drafts WHERE id=?',(did,));db().commit();return jsonify(ok=True)
        d=data()
        if old and d.get('revision')!=old['revision']:raise error('O rascunho mudou em outra aba. Reabra antes de editar.',409)
        if not old and db().execute('SELECT COUNT(*) FROM community_drafts WHERE user_id=?',(uid,)).fetchone()[0]>=20:raise error('Você tem 20 rascunhos. Publique ou exclua um antes de continuar.')
        meta,urls=validate(d,db(),error,external_url,partial=True)
        if d.get('kind') not in KINDS:raise error('Formato inválido.')
        title=d.get('title','');body=d.get('body','')
        if not isinstance(title,str) or len(title)>160 or not isinstance(body,str) or len(body)>6000:raise error('Título ou texto muito longo.')
        url,_=checked_url(d.get('url',''),db(),error,external_url,optional=True)
        poster,_=checked_url(d.get('poster',''),db(),error,external_url,image=True,optional=True)
        payload={**meta,'title':title,'body':body,'url':url,'poster':poster,'kind':d['kind']}
        if d.get('id'):
            p=db().execute("SELECT user_id FROM community_posts WHERE id=?",(str(d['id']),)).fetchone()
            if not p or (p[0]!=uid and g.user['role']!='admin'):raise error('Publicação indisponível.',403)
            payload['id']=d['id']
        did=did or secrets.token_urlsafe(9);revision=(old['revision']+1) if old else 1
        db().execute('INSERT INTO community_drafts VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,revision=excluded.revision,updated_at=excluded.updated_at',(did,uid,json.dumps(payload),revision,time.time()))
        community_social.retain_assets(db(),*urls,url,poster);db().commit()
        return jsonify(id=did,revision=revision),200 if old else 201
