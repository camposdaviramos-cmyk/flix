"""Social media, ephemeral stories, reactions and live presence."""
import json
import re
import secrets
import struct
import time
from pathlib import Path
from flask import g, jsonify, request, send_file

REACTIONS = ('heart','laugh','wow','fire','clap','sad')
STICKERS = {'popcorn':('🍿','Bora assistir!'),'hype':('🚀','É cinema!'),'love':('💜','Amei demais'),
            'gg':('🏆','Boa partida!'),'hello':('👋','Cheguei!'),'plot':('😱','Que plot!'),'dance':('🪩','Só vem!'),'sleep':('😴','Só mais um episódio')}


def migrate(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS community_assets(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
        mime TEXT,bytes INTEGER,created_at REAL,expires_at REAL,status TEXT DEFAULT 'active');
    CREATE TABLE IF NOT EXISTS community_stories(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
        body TEXT,media_url TEXT,media_type TEXT,background TEXT,created_at REAL,expires_at REAL,status TEXT DEFAULT 'published');
    CREATE INDEX IF NOT EXISTS story_expiry ON community_stories(status,expires_at);
    CREATE TABLE IF NOT EXISTS community_story_views(story_id TEXT REFERENCES community_stories(id) ON DELETE CASCADE,
        user_id TEXT REFERENCES users(id) ON DELETE CASCADE,created_at REAL,PRIMARY KEY(story_id,user_id));
    CREATE TABLE IF NOT EXISTS community_reactions(target_type TEXT,target_id TEXT,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
        reaction TEXT,created_at REAL,PRIMARY KEY(target_type,target_id,user_id));
    CREATE TABLE IF NOT EXISTS community_online(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        seen_at REAL,typing_to TEXT,typing_at REAL);
    CREATE TABLE IF NOT EXISTS community_dm_reads(user_id TEXT,other_id TEXT,message_id INTEGER,PRIMARY KEY(user_id,other_id));
    ''')


def local_asset(value,db,error,owner=None):
    if not isinstance(value,str) or not value.startswith('/api/community/assets/'):return None
    aid=value.removeprefix('/api/community/assets/')
    if not re.fullmatch(r'[a-f0-9]{32}',aid):raise error('Arquivo inválido.')
    row=db.execute("SELECT a.* FROM community_assets a JOIN users u ON u.id=a.user_id WHERE a.id=? AND a.status='active' AND u.status='active' AND (a.expires_at IS NULL OR a.expires_at>?)",(aid,time.time())).fetchone()
    if not row or (owner and row['user_id']!=owner):raise error('Arquivo não encontrado ou indisponível.',404)
    if not owner and g.get('user') and row['user_id']!=g.user['id'] and g.user['role']!='admin' and private_asset(db,value):raise error('Arquivo indisponível.',404)
    return value, row['mime'].split('/')[0]


def private_asset(db,url):
    joins="FROM community_posts p LEFT JOIN social_spaces ss ON ss.id=p.space_id LEFT JOIN community_post_meta m ON m.post_id=p.id LEFT JOIN community_compositions c ON c.target_type='post' AND c.target_id=p.id"
    refs="(p.url=? OR p.poster=? OR instr(m.document,?)>0 OR instr(c.payload,?)>0)"
    args=(url,)*4
    viewer=g.user['id'] if g.get('user') else ''
    restricted="(p.status IN ('private','archived','hidden','removed') OR ss.status='hidden' OR (ss.privacy='private' AND NOT EXISTS(SELECT 1 FROM social_space_members sm WHERE sm.space_id=ss.id AND sm.user_id=?)))"
    if not db.execute('SELECT 1 '+joins+' WHERE '+restricted+' AND '+refs,(viewer,*args)).fetchone():return False
    if db.execute("SELECT 1 "+joins+" WHERE p.status='published' AND (p.space_id IS NULL OR (ss.status='active' AND (ss.privacy='public' OR EXISTS(SELECT 1 FROM social_space_members sm WHERE sm.space_id=ss.id AND sm.user_id=?)))) AND "+refs,(viewer,*args)).fetchone():return False
    if db.execute('SELECT 1 FROM music_tracks WHERE url=? OR image=?',(url,url)).fetchone():return False
    if db.execute("SELECT 1 FROM music_playlists WHERE cover=? AND (public=1 OR user_id=?)",(url,viewer)).fetchone():return False
    if db.execute("SELECT 1 FROM social_spaces WHERE status='active' AND (avatar=? OR cover=?)",(url,url)).fetchone():return False
    if db.execute('SELECT 1 FROM hub_groups gr JOIN hub_group_members m ON m.group_id=gr.id WHERE gr.avatar=? AND m.user_id=?',(url,viewer)).fetchone():return False
    if db.execute('SELECT 1 FROM community_profiles WHERE avatar=? OR cover=?',(url,url)).fetchone():return False
    if db.execute("SELECT 1 FROM community_stories s LEFT JOIN community_compositions c ON c.target_type='story' AND c.target_id=s.id WHERE s.status='published' AND s.expires_at>? AND (s.media_url=? OR s.thumbnail=? OR instr(c.payload,?)>0)",(time.time(),url,url,url)).fetchone():return False
    if db.execute("SELECT 1 FROM community_rooms WHERE status='open' AND (url=? OR cover=?)",(url,url)).fetchone():return False
    return True


def retain_assets(db, *urls):
    # Permanent publications/profile/room links must outlive a 24-hour story.
    for url in urls:
        if isinstance(url,str) and re.fullmatch(r'/api/community/assets/[a-f0-9]{32}',url):
            db.execute('UPDATE community_assets SET expires_at=NULL WHERE id=?',(url.rsplit('/',1)[-1],))


def permanent_asset(db,url):
    return any(db.execute(sql,args).fetchone() for sql,args in [
        ("SELECT 1 FROM community_posts WHERE status IN ('published','private','archived') AND (url=? OR poster=?)",(url,url)),
        ("SELECT 1 FROM community_profiles WHERE avatar=? OR cover=? OR website=?",(url,url,url)),
        ("SELECT 1 FROM community_rooms WHERE status='open' AND (url=? OR cover=?)",(url,url)),
        ("SELECT 1 FROM community_queue WHERE url=?",(url,)),
        ("SELECT 1 FROM community_post_meta m JOIN community_posts p ON p.id=m.post_id WHERE p.status IN ('published','private','archived') AND instr(m.document,?)>0",(url,)),
        ("SELECT 1 FROM community_compositions c JOIN community_posts p ON p.id=c.target_id WHERE c.target_type='post' AND p.status IN ('published','private','archived') AND instr(c.payload,?)>0",(url,)),
        ("SELECT 1 FROM community_drafts WHERE instr(payload,?)>0",(url,)),
        ("SELECT 1 FROM music_tracks WHERE url=? OR image=?",(url,url)),
        ("SELECT 1 FROM music_playlists WHERE cover=?",(url,)),
        ("SELECT 1 FROM social_spaces WHERE avatar=? OR cover=?",(url,url)),
        ("SELECT 1 FROM hub_groups WHERE avatar=?",(url,))])


def reaction_state(db,typ,target,uid):
    rows=db.execute('SELECT reaction,COUNT(*) total FROM community_reactions WHERE target_type=? AND target_id=? GROUP BY reaction',(typ,target)).fetchall()
    own=db.execute('SELECT reaction FROM community_reactions WHERE target_type=? AND target_id=? AND user_id=?',(typ,target,uid)).fetchone()
    return {'counts':{r['reaction']:r['total'] for r in rows},'mine':own[0] if own else None}


def register(app,db,auth,data,error,external_url,room,post):
    directory=Path(app.config['DATA_DIR'])/'social-media';directory.mkdir(exist_ok=True)
    def uid():return g.user['id']
    def friend(other):
        if not db().execute("SELECT 1 FROM jump_friends f JOIN users u ON u.id=? AND u.status='active' WHERE f.status='accepted' AND ((sender=? AND recipient=?) OR (sender=? AND recipient=?))",(other,uid(),other,other,uid())).fetchone():raise error('Adicione esta pessoa aos amigos para conversar.',403)
    def asset(value,owner=True):
        return local_asset(value,db(),error,uid() if owner else None) or external_url(value,error,optional=True)
    def story(sid):
        r=db().execute("SELECT s.*,u.name,u.username,u.verified,COALESCE(p.avatar,'') avatar FROM community_stories s JOIN users u ON u.id=s.user_id LEFT JOIN community_profiles p ON p.user_id=u.id WHERE s.id=? AND s.status='published' AND s.expires_at>? AND u.status='active'",(sid,time.time())).fetchone()
        if not r:raise error('Este story expirou ou foi removido.',404)
        return r

    def cleanup_expired():
        expired=db().execute("SELECT id FROM community_assets WHERE user_id=? AND status='active' AND expires_at IS NOT NULL AND expires_at<=?",(uid(),time.time())).fetchall()
        for r in expired:
            db().execute("UPDATE community_assets SET status='expired' WHERE id=?",(r['id'],))
            (directory/r['id']).unlink(missing_ok=True)

    @app.get('/api/community/assets')
    @auth()
    def my_assets():
        cleanup_expired();db().commit()
        return jsonify(assets=[dict(r) for r in db().execute("SELECT id,mime,bytes,created_at FROM community_assets WHERE user_id=? AND status='active' ORDER BY created_at DESC",(uid(),))])

    @app.delete('/api/community/assets/<aid>')
    @auth()
    def remove_asset(aid):
        if not re.fullmatch(r'[a-f0-9]{32}',aid):raise error('Arquivo inválido.',404)
        r=db().execute('SELECT user_id FROM community_assets WHERE id=?',(aid,)).fetchone()
        if not r:raise error('Arquivo não encontrado.',404)
        if r['user_id']!=uid():raise error('Você só pode remover seus arquivos.',403)
        db().execute("UPDATE community_assets SET status='removed' WHERE id=?",(aid,));db().commit()
        (directory/aid).unlink(missing_ok=True)
        return jsonify(ok=True)

    @app.post('/api/community/assets')
    @auth()
    def upload():
        f=request.files.get('file')
        if not f:raise error('Escolha uma imagem, vídeo ou áudio.')
        content=f.read(25*1024*1024+1)
        if not content or len(content)>25*1024*1024:raise error('O arquivo deve ter até 25 MB.',413)
        if len(content)>=32 and content.startswith(b'\x89PNG\r\n\x1a\n') and content[12:16]==b'IHDR':
            w,h=struct.unpack('>II',content[16:24]);mime='image/png'
            if min(w,h)<1 or max(w,h)>4096 or len(content)>4*1024*1024 or content[-8:]!=b'IEND\xaeB`\x82':raise error('Imagem inválida. Use até 4096 px e 4 MB.')
        elif len(content)>16 and content[4:8]==b'ftyp':mime='audio/mp4' if (content[8:12] in (b'M4A ',b'M4B ') or f.mimetype in ('audio/mp4','audio/x-m4a')) else 'video/mp4'
        elif len(content)>44 and content.startswith(b'RIFF') and content[8:12]==b'WAVE':mime='audio/wav'
        elif len(content)>32 and content.startswith(b'OggS') and (b'OpusHead' in content[:256] or b'vorbis' in content[:256]):mime='audio/ogg'
        elif len(content)>16 and (content.startswith(b'ID3') or (content[0]==255 and (content[1]&0xe0)==0xe0 and (content[1]&6)!=0)):mime='audio/mpeg'
        elif content.startswith(b'\x1aE\xdf\xa3') and b'webm' in content[:128]:mime='video/webm'
        else:raise error('Use PNG, MP4, WebM ou áudio MP3, M4A, OGG ou WAV.')
        db().execute('BEGIN IMMEDIATE')
        cleanup_expired()
        size,count=db().execute("SELECT COALESCE(SUM(bytes),0),COUNT(*) FROM community_assets WHERE user_id=? AND status='active'",(uid(),)).fetchone()
        if size+len(content)>250*1024*1024 or count>=300:raise error('Seu limite de mídia foi atingido. Remova arquivos antigos antes de enviar mais.',413)
        recent=db().execute('SELECT COUNT(*) FROM community_assets WHERE user_id=? AND created_at>?',(uid(),time.time()-3600)).fetchone()[0]
        if recent>=30:raise error('Aguarde antes de enviar mais arquivos.',429)
        aid=secrets.token_hex(16);path=directory/aid
        try:
            path.write_bytes(content)
            db().execute('INSERT INTO community_assets VALUES(?,?,?,?,?,NULL,?)',(aid,uid(),mime,len(content),time.time(),'active'));db().commit()
        except Exception:
            path.unlink(missing_ok=True);raise
        return jsonify(url='/api/community/assets/'+aid,media_type=mime.split('/')[0]),201

    @app.get('/api/community/assets/<aid>')
    @auth()
    def read_asset(aid):
        local_asset('/api/community/assets/'+aid,db(),error)
        row=db().execute('SELECT mime,user_id FROM community_assets WHERE id=?',(aid,)).fetchone()
        path=directory/aid
        if not path.exists():raise error('Arquivo indisponível.',404)
        response=send_file(path,mimetype=row['mime'],conditional=True,max_age=0)
        response.headers['Cache-Control']='private, no-store'
        return response

    @app.route('/api/community/stories',methods=['GET','POST'])
    @auth()
    def stories():
        if request.method=='GET':
            rows=db().execute("""SELECT s.*,u.name,u.username,u.verified,COALESCE(p.avatar,'') avatar,
              EXISTS(SELECT 1 FROM community_story_views v WHERE v.story_id=s.id AND v.user_id=?) viewed,
              (SELECT COUNT(*) FROM community_story_views v WHERE v.story_id=s.id) views
              FROM community_stories s JOIN users u ON u.id=s.user_id LEFT JOIN community_profiles p ON p.user_id=u.id
              WHERE s.status='published' AND s.expires_at>? AND u.status='active' ORDER BY s.created_at DESC LIMIT 100""",(uid(),time.time())).fetchall()
            return jsonify(stories=[dict(r) for r in rows])
        d=data();body=str(d.get('body','')).strip();background=d.get('background','#6246a8')
        import community_experience
        comp=community_experience.composition(db(),d['composition'],error,external_url,uid()) if d.get('composition') is not None else None
        if len(body)>700 or not re.fullmatch(r'#[0-9a-fA-F]{6}',str(background)):raise error('Texto ou cor inválida.')
        url,kind=asset(d.get('media_url',''))
        if not body and not url and not comp:raise error('Adicione texto, foto ou vídeo.')
        if url and kind not in ('image','video'):raise error('Stories aceitam imagem enviada ou vídeo MP4/WebM.')
        db().execute('BEGIN IMMEDIATE')
        if db().execute('SELECT COUNT(*) FROM community_stories WHERE user_id=? AND created_at>?',(uid(),time.time()-86400)).fetchone()[0]>=30:raise error('Você pode publicar até 30 stories por dia.',429)
        sid=secrets.token_urlsafe(9);now=time.time()
        thumbnail,thumb_kind=asset(d.get('thumbnail',''))
        if thumbnail and thumb_kind!='image':raise error('A capa deve ser uma imagem.')
        db().execute('INSERT INTO community_stories(id,user_id,body,media_url,media_type,background,created_at,expires_at,status,thumbnail) VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,uid(),body,url,kind,background,now,now+86400,'published',thumbnail))
        if thumbnail.startswith('/api/community/assets/') and not permanent_asset(db(),thumbnail):db().execute('UPDATE community_assets SET expires_at=? WHERE id=?',(now+86400,thumbnail.rsplit('/',1)[-1]))
        if comp is not None:community_experience.save_composition(db(),'story',sid,comp,now+86400)
        if url.startswith('/api/community/assets/') and not permanent_asset(db(),url):
            db().execute('UPDATE community_assets SET expires_at=? WHERE id=?',(now+86400,url.rsplit('/',1)[-1]))
        db().commit();return jsonify(id=sid),201

    @app.route('/api/community/stories/<sid>',methods=['GET','DELETE'])
    @auth()
    def story_detail(sid):
        s=story(sid)
        if request.method=='DELETE':
            if s['user_id']!=uid() and g.user['role']!='admin':raise error('Você só pode remover seu story.',403)
            db().execute("UPDATE community_stories SET status='removed' WHERE id=?",(sid,));db().commit();return jsonify(ok=True)
        detail=dict(s);row=db().execute("SELECT payload FROM community_compositions WHERE target_type='story' AND target_id=?",(sid,)).fetchone();detail['composition']=json.loads(row[0]) if row else None
        detail['views']=db().execute('SELECT COUNT(*) FROM community_story_views WHERE story_id=?',(sid,)).fetchone()[0]
        return jsonify(story=detail,reactions=reaction_state(db(),'story',sid,uid()))

    @app.post('/api/community/stories/<sid>/view')
    @auth()
    def story_view(sid):
        story(sid);db().execute('INSERT OR IGNORE INTO community_story_views VALUES(?,?,?)',(sid,uid(),time.time()));db().commit();return jsonify(ok=True)

    @app.route('/api/community/reactions/<typ>/<target>',methods=['GET','PUT','DELETE'])
    @auth()
    def reactions(typ,target):
        if typ=='post':p=post(target)
        elif typ=='story':p=story(target)
        elif typ=='message':
            p=db().execute('SELECT * FROM community_messages WHERE id=?',(target,)).fetchone()
            if not p:raise error('Mensagem indisponível.',404)
            room(p['room_id'],member=True)
        else:raise error('Reação inválida.')
        if request.method!='GET':
            db().execute('BEGIN IMMEDIATE')
            if request.method=='DELETE':db().execute('DELETE FROM community_reactions WHERE target_type=? AND target_id=? AND user_id=?',(typ,target,uid()))
            else:
                reaction=data().get('reaction')
                if reaction not in REACTIONS:raise error('Escolha uma reação válida.')
                db().execute('INSERT INTO community_reactions VALUES(?,?,?,?,?) ON CONFLICT(target_type,target_id,user_id) DO UPDATE SET reaction=excluded.reaction',(typ,target,uid(),reaction,time.time()))
            db().commit()
        value=reaction_state(db(),typ,target,uid())
        if typ=='post' and p['hide_likes']:value['counts']={}
        return jsonify(reactions=value)

    @app.post('/api/community/presence')
    @auth()
    def presence():
        d=data();other=str(d.get('typing_to',''))[:64]
        if other:friend(other)
        now=time.time();db().execute('INSERT INTO community_online VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET seen_at=excluded.seen_at,typing_to=excluded.typing_to,typing_at=excluded.typing_at',(uid(),now,other,now if other else 0))
        db().commit();return jsonify(ok=True)

    @app.get('/api/community/inbox')
    @auth()
    def inbox():
        friends=db().execute("""SELECT u.id,u.name,u.username,u.verified,COALESCE(p.avatar,'') avatar,
          COALESCE(o.seen_at,0)>? online, (o.typing_to=? AND o.typing_at>?) typing,
          (SELECT body FROM community_dm WHERE (sender=u.id AND recipient=?) OR (sender=? AND recipient=u.id) ORDER BY id DESC LIMIT 1) last_message,
          (SELECT COUNT(*) FROM community_dm d WHERE d.sender=u.id AND d.recipient=? AND d.id>COALESCE((SELECT message_id FROM community_dm_reads WHERE user_id=? AND other_id=u.id),0)) unread
          FROM jump_friends f JOIN users u ON u.id=CASE WHEN f.sender=? THEN f.recipient ELSE f.sender END
          LEFT JOIN community_profiles p ON p.user_id=u.id LEFT JOIN community_online o ON o.user_id=u.id
          WHERE f.status='accepted' AND (f.sender=? OR f.recipient=?) AND u.status='active' ORDER BY unread DESC,online DESC,u.name""",(time.time()-60,uid(),time.time()-5,uid(),uid(),uid(),uid(),uid(),uid(),uid())).fetchall()
        import social_hub
        values=[dict(f) for f in friends]
        for f in values:
            if social_hub.preferences(db(),f['id'])['presence']=='invisible':f['online']=False;f['typing']=False
        return jsonify(friends=values,stickers=STICKERS)

    @app.post('/api/community/dm/<other>/read')
    @auth()
    def read_dm(other):
        friend(other);last=db().execute('SELECT COALESCE(MAX(id),0) FROM community_dm WHERE sender=? AND recipient=?',(other,uid())).fetchone()[0]
        db().execute('INSERT INTO community_dm_reads VALUES(?,?,?) ON CONFLICT(user_id,other_id) DO UPDATE SET message_id=MAX(message_id,excluded.message_id)',(uid(),other,last))
        db().execute("UPDATE hub_notifications SET read_at=? WHERE user_id=? AND category='messages' AND actor_id=? AND dedupe LIKE 'dm:%' AND read_at IS NULL",(time.time(),uid(),other))
        db().commit();return jsonify(ok=True)

    @app.get('/api/admin/community/social')
    @auth(admin=True)
    def admin_social():
        return jsonify(stories=[dict(r) for r in db().execute('SELECT s.*,u.username FROM community_stories s JOIN users u ON u.id=s.user_id ORDER BY s.created_at DESC LIMIT 80')],assets=[dict(r) for r in db().execute('SELECT a.*,u.username FROM community_assets a JOIN users u ON u.id=a.user_id ORDER BY a.created_at DESC LIMIT 80')],games=[dict(r) for r in db().execute('SELECT g.id,g.room_id,g.kind,g.status,g.created_at,r.title FROM community_games g JOIN community_rooms r ON r.id=g.room_id ORDER BY g.created_at DESC LIMIT 50')])

    @app.patch('/api/admin/community/social/<kind>/<target>')
    @auth(admin=True)
    def moderate_social(kind,target):
        if kind=='stories':cur=db().execute("UPDATE community_stories SET status='removed' WHERE id=?",(target,))
        elif kind=='assets':cur=db().execute("UPDATE community_assets SET status='removed' WHERE id=?",(target,))
        elif kind=='games':cur=db().execute("UPDATE community_games SET status='cancelled',revision=revision+1 WHERE id=? AND status IN ('lobby','playing')",(target,))
        else:raise error('Ação inválida.')
        if not cur.rowcount:raise error('Registro não encontrado.',404)
        db().execute('INSERT INTO community_audit(admin_id,action,target,created_at) VALUES(?,?,?,?)',(uid(),'social:'+kind+':remove',target,time.time()));db().commit();return jsonify(ok=True)
