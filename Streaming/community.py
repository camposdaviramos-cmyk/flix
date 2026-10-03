"""Community publishing, profiles, moderation and persistent external-media rooms."""
import base64
import ipaddress
import json
import math
import os
import re
import secrets
import struct
import time
from urllib.parse import urlsplit, parse_qs
from flask import g, jsonify, request, Response
from jump import username_for
import community_games
import community_social
import community_publishing
import room_lifecycle
import social_hub


def migrate(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS community_profiles(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,bio TEXT DEFAULT '',avatar TEXT DEFAULT '',avatar_png BLOB,cover TEXT DEFAULT '',favorite_genres TEXT DEFAULT '',location TEXT DEFAULT '',website TEXT DEFAULT '',updated_at REAL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS community_follows(follower TEXT REFERENCES users(id) ON DELETE CASCADE,following TEXT REFERENCES users(id) ON DELETE CASCADE,created_at REAL,PRIMARY KEY(follower,following),CHECK(follower<>following));
    CREATE INDEX IF NOT EXISTS community_following ON community_follows(following);
    CREATE TABLE IF NOT EXISTS community_posts(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,kind TEXT,title TEXT,body TEXT,url TEXT,media_type TEXT,poster TEXT,status TEXT DEFAULT 'published',featured INTEGER DEFAULT 0,created_at REAL,updated_at REAL);
    CREATE INDEX IF NOT EXISTS community_post_feed ON community_posts(status,created_at DESC);
    CREATE TABLE IF NOT EXISTS community_likes(post_id TEXT REFERENCES community_posts(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,created_at REAL,PRIMARY KEY(post_id,user_id));
    CREATE TABLE IF NOT EXISTS community_views(post_id TEXT REFERENCES community_posts(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,created_at REAL,PRIMARY KEY(post_id,user_id));
    CREATE TABLE IF NOT EXISTS community_comments(id INTEGER PRIMARY KEY AUTOINCREMENT,post_id TEXT REFERENCES community_posts(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,body TEXT,created_at REAL);
    CREATE INDEX IF NOT EXISTS community_comment_post ON community_comments(post_id,id);
    CREATE TABLE IF NOT EXISTS community_badges(id TEXT PRIMARY KEY,name TEXT,description TEXT,symbol TEXT,color TEXT);
    CREATE TABLE IF NOT EXISTS community_awards(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,badge_id TEXT REFERENCES community_badges(id) ON DELETE CASCADE,awarded_by TEXT REFERENCES users(id),created_at REAL,PRIMARY KEY(user_id,badge_id));
    CREATE TABLE IF NOT EXISTS community_dm(id INTEGER PRIMARY KEY AUTOINCREMENT,sender TEXT REFERENCES users(id) ON DELETE CASCADE,recipient TEXT REFERENCES users(id) ON DELETE CASCADE,body TEXT,created_at REAL);
    CREATE INDEX IF NOT EXISTS community_dm_pair ON community_dm(sender,recipient,id);
    CREATE TABLE IF NOT EXISTS community_reports(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT REFERENCES users(id),target_type TEXT,target_id TEXT,reason TEXT,status TEXT DEFAULT 'open',created_at REAL,UNIQUE(user_id,target_type,target_id));
    CREATE TABLE IF NOT EXISTS community_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,admin_id TEXT REFERENCES users(id),action TEXT,target TEXT,created_at REAL);
    CREATE TABLE IF NOT EXISTS community_rooms(id TEXT PRIMARY KEY,host_id TEXT REFERENCES users(id) ON DELETE CASCADE,title TEXT,description TEXT,kind TEXT,url TEXT,media_type TEXT,post_id TEXT REFERENCES community_posts(id) ON DELETE SET NULL,approval INTEGER DEFAULT 1,status TEXT DEFAULT 'open',position REAL DEFAULT 0,paused INTEGER DEFAULT 1,revision INTEGER DEFAULT 1,updated_at REAL,created_at REAL);
    CREATE TABLE IF NOT EXISTS community_members(room_id TEXT REFERENCES community_rooms(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,status TEXT DEFAULT 'pending',joined_at REAL,seen_at REAL,mic INTEGER DEFAULT 0,camera INTEGER DEFAULT 0,PRIMARY KEY(room_id,user_id));
    CREATE INDEX IF NOT EXISTS community_presence ON community_members(room_id,status,seen_at);
    CREATE TABLE IF NOT EXISTS community_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,room_id TEXT REFERENCES community_rooms(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,body TEXT,created_at REAL);
    CREATE INDEX IF NOT EXISTS community_message_room ON community_messages(room_id,id);
    CREATE TABLE IF NOT EXISTS community_signals(id INTEGER PRIMARY KEY AUTOINCREMENT,room_id TEXT REFERENCES community_rooms(id) ON DELETE CASCADE,sender TEXT REFERENCES users(id) ON DELETE CASCADE,recipient TEXT REFERENCES users(id) ON DELETE CASCADE,payload TEXT,created_at REAL);
    CREATE INDEX IF NOT EXISTS community_signal_room ON community_signals(room_id,recipient,id);
    CREATE TABLE IF NOT EXISTS community_queue(id INTEGER PRIMARY KEY AUTOINCREMENT,room_id TEXT REFERENCES community_rooms(id) ON DELETE CASCADE,title TEXT,url TEXT,media_type TEXT,created_at REAL);
    ''')
    columns={r[1] for r in db.execute('PRAGMA table_info(community_members)')}
    if 'seat' not in columns:
        db.execute('ALTER TABLE community_members ADD COLUMN seat INTEGER CHECK(seat BETWEEN 1 AND 8)')
        db.execute("UPDATE community_members SET seat=1 WHERE user_id=(SELECT host_id FROM community_rooms WHERE id=room_id)")
    if 'mic_blocked' not in columns:
        db.execute('ALTER TABLE community_members ADD COLUMN mic_blocked INTEGER NOT NULL DEFAULT 0')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS community_unique_seat ON community_members(room_id,seat) WHERE seat IS NOT NULL')
    db.executescript("""
    CREATE TABLE IF NOT EXISTS community_ratings(post_id TEXT REFERENCES community_posts(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),created_at REAL NOT NULL,PRIMARY KEY(post_id,user_id));
    """)
    for b in [('cinefilo','Cinéfilo','Olhar apaixonado por cinema','film','#e75a74'),('curador','Curador','Grandes indicações para a comunidade','spark','#b393ff'),('anfitriao','Anfitrião','Conecta pessoas em boas sessões','users','#4ed6b0')]:
        db.execute('INSERT OR IGNORE INTO community_badges VALUES(?,?,?,?,?)',b)
    community_games.migrate(db)
    community_social.migrate(db)
    community_publishing.migrate(db)
    room_lifecycle.migrate(db)
    social_hub.migrate(db)


def external_url(value, error, media=False, optional=False):
    value=str(value or '').strip()
    if not value and optional:
        return '', ''
    try:
        p=urlsplit(value)
        host=(p.hostname or '').lower()
        if p.scheme!='https' or not host or p.username or p.password or p.port not in (None,443) or len(value)>2000 or any(ord(c)<33 for c in value):
            raise ValueError()
        if host in ('localhost','localhost.localdomain') or '.' not in host or host.endswith(('.local','.internal','.localhost')):
            raise ValueError()
        try:
            if not ipaddress.ip_address(host).is_global:
                raise ValueError('private')
        except ValueError as e:
            if str(e)=='private':
                raise
    except ValueError:
        raise error('Use um link HTTPS público válido.')
    if host in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be'):
        vid=p.path.strip('/').split('/')[-1] if host=='youtu.be' or p.path.startswith(('/embed/','/shorts/','/live/')) else parse_qs(p.query).get('v',[''])[0]
        if not re.fullmatch(r'[a-zA-Z0-9_-]{11}',vid):
            raise error('Informe o link de um vídeo do YouTube.')
        return 'https://www.youtube.com/watch?v='+vid,'youtube'
    ext=p.path.lower().rsplit('.',1)[-1]
    kind={'m3u8':'hls','mp4':'video','webm':'video','mp3':'audio','ogg':'audio','m4a':'audio','wav':'audio'}.get(ext,'link')
    if media and kind=='link':
        raise error('Use YouTube, M3U8, MP4, WebM ou um arquivo de áudio (MP3, OGG, M4A, WAV).')
    return value,kind


def register_community(app, db, auth, data, error):
    @app.before_request
    def maintain_rooms():
        if not getattr(g,'user',None) or not request.path.startswith('/api/community/rooms'):return
        parts=request.path.split('/')
        db().execute('BEGIN IMMEDIATE')
        if len(parts)>4:room_lifecycle.repair(db(),parts[4])
        elif request.method=='GET':room_lifecycle.sweep(db())
        db().commit()

    def content_url(value, error, media=False, optional=False):
        result=community_social.local_asset(value,db(),error)
        if result:
            if media and result[1]=='image':raise error('Use um vídeo ou áudio para esta publicação.')
            return result
        return external_url(value,error,media=media,optional=optional)

    def text(d,key,maximum,minimum=0):
        v=str(d.get(key,'')).strip()
        if not minimum<=len(v)<=maximum:
            raise error(f'O campo {key} deve ter entre {minimum} e {maximum} caracteres.')
        return v

    def tx():
        db().execute('BEGIN IMMEDIATE')

    def uid():
        return g.user['id']

    def rows(sql,args=()):
        return [dict(r) for r in db().execute(sql,args)]

    def limit(table,where,args,n,seconds):
        if db().execute(f'SELECT COUNT(*) FROM {table} WHERE {where} AND created_at>?',(*args,time.time()-seconds)).fetchone()[0]>=n:
            raise error('Muitas solicitações. Aguarde um momento.',429)

    def audit(action,target):
        db().execute('INSERT INTO community_audit(admin_id,action,target,created_at) VALUES(?,?,?,?)',(uid(),action,target,time.time()))

    def person(user):
        return db().execute("SELECT u.id,u.name,u.username,u.created_at,COALESCE(p.avatar,'') avatar,COALESCE(p.bio,'') bio,COALESCE(p.cover,'') cover,COALESCE(p.favorite_genres,'') favorite_genres,COALESCE(p.location,'') location,COALESCE(p.website,'') website FROM users u LEFT JOIN community_profiles p ON p.user_id=u.id WHERE u.id=? AND u.status='active'",(user,)).fetchone()

    def post(pid,owner=False):
        r=db().execute("SELECT p.* FROM community_posts p JOIN users u ON u.id=p.user_id WHERE p.id=? AND u.status='active'",(pid,)).fetchone()
        if not r or (r['status']!='published' and not(owner and (r['user_id']==uid() or g.user['role']=='admin'))):
            raise error('Publicação não encontrada.',404)
        return r

    def post_list(where='1',args=(),offset=0):
        result=rows(f"""SELECT p.*,u.name,u.username,COALESCE(pr.avatar,'') avatar,
        (SELECT COUNT(*) FROM community_likes l WHERE l.post_id=p.id) likes,
        (SELECT COUNT(*) FROM community_views v WHERE v.post_id=p.id) views,
        (SELECT COUNT(*) FROM community_comments c WHERE c.post_id=p.id) comments,
        (SELECT ROUND(AVG(score),1) FROM community_ratings r JOIN users ru ON ru.id=r.user_id WHERE r.post_id=p.id AND ru.status='active') rating,
        (SELECT COUNT(*) FROM community_ratings r JOIN users ru ON ru.id=r.user_id WHERE r.post_id=p.id AND ru.status='active') rating_count,
        (SELECT score FROM community_ratings WHERE post_id=p.id AND user_id=?) my_rating,
        EXISTS(SELECT 1 FROM community_follows WHERE following=p.user_id AND follower=?) is_following,
        EXISTS(SELECT 1 FROM community_likes l WHERE l.post_id=p.id AND l.user_id=?) liked
        FROM community_posts p JOIN users u ON u.id=p.user_id LEFT JOIN community_profiles pr ON pr.user_id=u.id
        WHERE p.status='published' AND u.status='active' AND ({where}) ORDER BY p.featured DESC,p.created_at DESC,p.id LIMIT 21 OFFSET ?""",(uid(),uid(),uid(),*args,offset))
        for p in result:
            p['reactions']=community_social.reaction_state(db(),'post',p['id'],uid())
            community_publishing.enrich(db(),p)
        return result

    def room(rid,member=False,host=False):
        r=db().execute("SELECT r.* FROM community_rooms r JOIN users u ON u.id=r.host_id WHERE r.id=? AND r.status='open' AND u.status='active' AND (r.post_id IS NULL OR EXISTS (SELECT 1 FROM community_posts cp JOIN users pu ON pu.id=cp.user_id WHERE cp.id=r.post_id AND cp.status='published' AND pu.status='active'))",(rid,)).fetchone()
        if not r:
            raise error('Esta sala foi encerrada ou não existe.',404)
        if host and r['host_id']!=uid():
            raise error('Somente o anfitrião pode fazer isso.',403)
        if member and not db().execute("SELECT 1 FROM community_members WHERE room_id=? AND user_id=? AND status='joined'",(rid,uid())).fetchone():
            raise error('Aguarde a aprovação do anfitrião.',403)
        return r

    def clean_seats(rid):
        # Keep the host's seat reserved; release disconnected guests atomically.
        db().execute("UPDATE community_members SET seat=NULL,mic=0,camera=0 WHERE room_id=? AND user_id!=(SELECT host_id FROM community_rooms WHERE id=?) AND (status!='joined' OR seen_at<? OR user_id IN (SELECT id FROM users WHERE status!='active'))",(rid,rid,time.time()-45))

    def snapshot(rid):
        clean_seats(rid)
        r=dict(room(rid,True))
        r['server_time']=time.time();r['seat_limit']=4 if r['kind']=='live' else 8
        host_member=db().execute("SELECT seen_at,status FROM community_members WHERE room_id=? AND user_id=?",(rid,r['host_id'])).fetchone()
        r['host_online']=bool(host_member and host_member['status']=='joined' and host_member['seen_at']>time.time()-45)
        if not r['host_online'] and not r['paused']:
            end=min(time.time(),host_member['seen_at']+45) if host_member else time.time()
            r['position']+=max(0,end-r['updated_at']);r['paused']=1;r['updated_at']=time.time();r['revision']+=1
            db().execute('UPDATE community_rooms SET position=?,paused=1,updated_at=?,revision=? WHERE id=?',(r['position'],r['updated_at'],r['revision'],rid))
        r['members']=rows("SELECT u.id,u.name,u.username,COALESCE(p.avatar,'') avatar,m.mic,m.camera,m.seat,m.mic_blocked,m.stage_request,m.stage_at FROM community_members m JOIN users u ON u.id=m.user_id LEFT JOIN community_profiles p ON p.user_id=u.id WHERE m.room_id=? AND m.status='joined' AND m.seen_at>? AND u.status='active' ORDER BY m.joined_at,u.id",(rid,time.time()-45))
        r['requests']=rows("SELECT u.id,u.name,u.username FROM community_members m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.status='pending' AND m.seen_at>? AND u.status='active' ORDER BY m.joined_at",(rid,time.time()-120)) if r['host_id']==uid() else []
        r['messages']=rows('SELECT m.id,m.user_id,u.name,u.username,m.body,m.created_at FROM community_messages m JOIN users u ON u.id=m.user_id WHERE room_id=? ORDER BY m.id DESC LIMIT 60',(rid,))[::-1]
        r['queue']=rows('SELECT * FROM community_queue WHERE room_id=? ORDER BY id LIMIT 100',(rid,))
        return r

    @app.get('/api/community/feed')
    @auth()
    def community_feed():
        kind=request.args.get('kind','all');q=request.args.get('q','')[:100];offset=max(0,min(10000,int(request.args.get('offset',0))))
        where=['1'];args=[]
        if kind=='following':
            where.append('p.user_id IN (SELECT following FROM community_follows WHERE follower=?)');args.append(uid())
        elif kind!='all':
            where.append('p.kind=?');args.append(kind)
        if q:
            where.append('(p.title LIKE ? OR p.body LIKE ? OR u.username LIKE ?)');args += ['%'+q+'%']*3
        if request.args.get('user'):
            where.append('u.username=?');args.append(request.args['user'])
        result=post_list(' AND '.join(where),args,offset)
        return jsonify(posts=result[:20],more=len(result)>20)

    @app.route('/api/community/posts',methods=['POST'])
    @app.route('/api/community/posts/<pid>',methods=['PATCH','DELETE','GET'])
    @auth()
    def community_post(pid=None):
        if request.method=='GET':
            post(pid);return jsonify(post=post_list('p.id=?',(pid,))[0],comments=rows("SELECT c.*,u.name,u.username,COALESCE(p.avatar,'') avatar FROM community_comments c JOIN users u ON u.id=c.user_id LEFT JOIN community_profiles p ON p.user_id=u.id WHERE post_id=? ORDER BY c.id DESC LIMIT 100",(pid,))[::-1])
        tx()
        old=post(pid,True) if pid else None
        if old and old['user_id']!=uid() and g.user['role']!='admin':
            raise error('Você só pode editar suas publicações.',403)
        if request.method=='DELETE':
            db().execute("UPDATE community_posts SET status='removed' WHERE id=?",(pid,))
        else:
            d=data();kind=d.get('kind')
            if kind not in ('movie','series','channel','news','discussion','music','reel'):
                raise error('Tipo de publicação inválido.')
            title,body=text(d,'title',160,2),text(d,'body',6000)
            meta,assets=community_publishing.validate(d,db(),error,external_url) if 'document' in d else (None,[])
            source=d.get('url') or next((b['url'] for b in (meta or {}).get('document',[]) if b['type'] in ('video','audio')),'')
            url,media=content_url(source,error,media=kind in ('movie','series','channel','music','reel'),optional=kind in ('news','discussion'))
            if kind=='reel' and media not in ('video','youtube'):raise error('Reels aceitam vídeo enviado, MP4, WebM ou YouTube.')
            poster,_=content_url(d.get('poster'),error,optional=True)
            community_social.retain_assets(db(),url,poster)
            if old:
                db().execute('UPDATE community_posts SET title=?,body=?,kind=?,url=?,media_type=?,poster=?,updated_at=? WHERE id=?',(title,body,kind,url,media,poster,time.time(),pid))
            else:
                limit('community_posts','user_id=?',(uid(),),15,3600)
                pid=secrets.token_urlsafe(9)
                db().execute('INSERT INTO community_posts(id,user_id,kind,title,body,url,media_type,poster,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,uid(),kind,title,body,url,media,poster,time.time(),time.time()))
            if meta is not None:community_publishing.save(db(),pid,meta,assets)
            if d.get('draft_id'):db().execute('DELETE FROM community_drafts WHERE id=? AND user_id=?',(str(d['draft_id']),uid()))
        db().commit();return jsonify(id=pid,ok=True),201 if not old else 200

    @app.route('/api/community/posts/<pid>/like',methods=['POST','DELETE'])
    @auth()
    def community_like(pid):
        tx();p=post(pid)
        if p['user_id']==uid():
            raise error('Curta as indicações de outras pessoas.')
        if request.method=='POST':
            db().execute('INSERT OR IGNORE INTO community_likes VALUES(?,?,?)',(pid,uid(),time.time()))
        else:
            db().execute('DELETE FROM community_likes WHERE post_id=? AND user_id=?',(pid,uid()))
        db().commit();return jsonify(ok=True)

    @app.route('/api/community/posts/<pid>/rating',methods=['PUT','DELETE'])
    @auth()
    def community_rating(pid):
        tx();p=post(pid)
        if p['user_id']==uid():raise error('Avalie publicações de outros membros.')
        if request.method=='DELETE':
            db().execute('DELETE FROM community_ratings WHERE post_id=? AND user_id=?',(pid,uid()))
        else:
            score=data().get('score')
            if type(score) is not int or not 1<=score<=5:raise error('Escolha uma nota de 1 a 5 estrelas.')
            db().execute('INSERT INTO community_ratings VALUES(?,?,?,?) ON CONFLICT(post_id,user_id) DO UPDATE SET score=excluded.score',(pid,uid(),score,time.time()))
        result=post_list('p.id=?',(pid,))[0];db().commit();return jsonify(post=result)

    @app.post('/api/community/posts/<pid>/view')
    @auth()
    def community_view(pid):
        tx();p=post(pid)
        if p['media_type'] not in ('youtube','hls','video','audio'):
            raise error('Esta publicação não contém mídia.')
        db().execute('INSERT OR IGNORE INTO community_views VALUES(?,?,?)',(pid,uid(),time.time()));db().commit()
        return jsonify(ok=True)

    @app.post('/api/community/posts/<pid>/comments')
    @auth()
    def community_comment(pid):
        body=text(data(),'body',1500,1);tx();post(pid)
        limit('community_comments','user_id=?',(uid(),),12,60)
        db().execute('INSERT INTO community_comments(post_id,user_id,body,created_at) VALUES(?,?,?,?)',(pid,uid(),body,time.time()));db().commit()
        return jsonify(ok=True),201

    @app.delete('/api/community/comments/<int:cid>')
    @auth()
    def community_comment_delete(cid):
        tx();c=db().execute('SELECT * FROM community_comments WHERE id=?',(cid,)).fetchone()
        if not c:raise error('Comentário não encontrado.',404)
        if c['user_id']!=uid() and g.user['role']!='admin':raise error('Acesso restrito.',403)
        db().execute('DELETE FROM community_comments WHERE id=?',(cid,));db().commit();return jsonify(ok=True)

    @app.get('/api/community/profiles/<username>')
    @auth()
    def community_profile(username):
        u=db().execute("SELECT id FROM users WHERE username=? AND status='active'",(username,)).fetchone()
        if not u:raise error('Perfil não encontrado.',404)
        p=dict(person(u['id']));oid=u['id']
        p['badges']=rows('SELECT b.*,a.created_at FROM community_awards a JOIN community_badges b ON b.id=a.badge_id WHERE a.user_id=?',(oid,))
        p['rating']=db().execute("SELECT ROUND(AVG(r.score),1) FROM community_ratings r JOIN community_posts p ON p.id=r.post_id JOIN users u ON u.id=r.user_id WHERE p.user_id=? AND p.status='published' AND u.status='active'",(oid,)).fetchone()[0]
        p['followers']=db().execute('SELECT COUNT(*) FROM community_follows WHERE following=?',(oid,)).fetchone()[0]
        p['following']=db().execute('SELECT COUNT(*) FROM community_follows WHERE follower=?',(oid,)).fetchone()[0]
        p['posts']=db().execute("SELECT COUNT(*) FROM community_posts WHERE user_id=? AND status='published'",(oid,)).fetchone()[0]
        p['is_following']=bool(db().execute('SELECT 1 FROM community_follows WHERE follower=? AND following=?',(uid(),oid)).fetchone())
        f=db().execute('SELECT sender,status FROM jump_friends WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?)',(uid(),oid,oid,uid())).fetchone()
        p['friend']=dict(f) if f else None
        seen=db().execute('SELECT seen_at FROM community_online WHERE user_id=?',(oid,)).fetchone()
        p.update(social_hub.profile_activity(db(),oid,uid()))
        p['game_points'],p['games_played'],p['wins']=db().execute('SELECT COALESCE(SUM(points),0),COUNT(*),COALESCE(SUM(won),0) FROM community_game_results WHERE user_id=?',(oid,)).fetchone()
        return jsonify(profile=p)

    @app.patch('/api/community/profile')
    @auth()
    def community_profile_update():
        d=data();name=text(d,'name',100,2);bio=text(d,'bio',1000);genres=text(d,'favorite_genres',160);location=text(d,'location',80)
        website,_=content_url(d.get('website'),error,optional=True);cover,_=content_url(d.get('cover'),error,optional=True)
        avatar=d.get('avatar','');blob=None
        if str(avatar).startswith('data:image/png;base64,'):
            try:
                blob=base64.b64decode(avatar.split(',',1)[1],validate=True)
                if len(blob)>300000 or blob[:8]!=b'\x89PNG\r\n\x1a\n' or blob[12:16]!=b'IHDR':raise ValueError()
                w,h=struct.unpack('>II',blob[16:24])
                if not 1<=w<=512 or not 1<=h<=512 or blob[-8:]!=b'IEND\xaeB`\x82':raise ValueError()
            except (ValueError,struct.error):raise error('Envie uma imagem PNG válida de até 512 px e 300 KB.')
            avatar='/api/community/avatars/'+uid()+'?v='+str(int(time.time()*1000))
        elif not str(avatar).startswith('/api/community/avatars/'+uid()+'?v='):
            avatar,_=content_url(avatar,error,optional=True)
        tx()
        community_social.retain_assets(db(),cover,avatar,website)
        username=g.user['username']
        if 'username' in d and str(d['username']).strip().lower().lstrip('@')!=username:
            username=username_for(db(),d['username'],name,error)
        db().execute('UPDATE users SET name=?,username=? WHERE id=?',(name,username,uid()))
        db().execute('INSERT INTO community_profiles(user_id,bio,avatar,avatar_png,cover,favorite_genres,location,website,updated_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET bio=excluded.bio,avatar=excluded.avatar,avatar_png=COALESCE(excluded.avatar_png,community_profiles.avatar_png),cover=excluded.cover,favorite_genres=excluded.favorite_genres,location=excluded.location,website=excluded.website,updated_at=excluded.updated_at',(uid(),bio,avatar,blob,cover,genres,location,website,time.time()))
        db().commit();return jsonify(ok=True)

    @app.get('/api/community/avatars/<user>')
    def community_avatar(user):
        p=db().execute('SELECT avatar_png FROM community_profiles WHERE user_id=?',(user,)).fetchone()
        if not p or not p[0]:raise error('Avatar não encontrado.',404)
        return Response(p[0],mimetype='image/png')

    @app.route('/api/community/follow/<other>',methods=['POST','DELETE'])
    @auth()
    def community_follow(other):
        if other==uid() or not person(other):raise error('Perfil inválido.',404)
        tx()
        if request.method=='POST':db().execute('INSERT OR IGNORE INTO community_follows VALUES(?,?,?)',(uid(),other,time.time()))
        else:db().execute('DELETE FROM community_follows WHERE follower=? AND following=?',(uid(),other))
        db().commit();return jsonify(ok=True)

    @app.get('/api/community/people')
    @auth()
    def community_people():
        query='%'+request.args.get('q','')[:100].strip().lstrip('@')+'%'
        return jsonify(people=rows("SELECT u.id,u.name,u.username,COALESCE(p.avatar,'') avatar FROM users u LEFT JOIN community_profiles p ON p.user_id=u.id WHERE u.status='active' AND (u.username LIKE ? OR u.name LIKE ?) ORDER BY u.name LIMIT 30",(query,query)))

    @app.get('/api/community/discover')
    @auth()
    def community_discover():
        people=rows("""SELECT u.id,u.name,u.username,COALESCE(pr.avatar,'') avatar,
        (SELECT COUNT(*) FROM community_likes l JOIN community_posts p ON p.id=l.post_id WHERE p.user_id=u.id AND p.status='published')*5+
        (SELECT COUNT(*) FROM community_views v JOIN community_posts p ON p.id=v.post_id WHERE p.user_id=u.id AND p.status='published' AND v.user_id!=u.id)*2+
        (SELECT COUNT(*) FROM community_follows f WHERE f.following=u.id)+
        (SELECT COUNT(*) FROM community_reactions r JOIN community_posts p ON p.id=r.target_id WHERE r.target_type='post' AND p.user_id=u.id AND r.user_id!=u.id AND p.status='published')*2+
        (SELECT COALESCE(SUM(points),0) FROM community_game_results WHERE user_id=u.id) score
        FROM users u LEFT JOIN community_profiles pr ON pr.user_id=u.id WHERE u.status='active' ORDER BY score DESC,u.created_at LIMIT 30""")
        top=rows("SELECT p.id,p.title,p.poster,p.kind,u.username,COUNT(v.user_id) views FROM community_posts p JOIN users u ON u.id=p.user_id JOIN community_views v ON v.post_id=p.id WHERE p.status='published' AND u.status='active' AND p.kind IN ('movie','series','channel') GROUP BY p.id ORDER BY views DESC,p.created_at DESC LIMIT 10")
        return jsonify(people=people,top=top,games=community_publishing.game_rank(db(),uid()))

    @app.route('/api/community/dm/<other>',methods=['GET','POST'])
    @auth()
    def community_dm(other):
        if not person(other) or not db().execute("SELECT 1 FROM jump_friends WHERE status='accepted' AND ((sender=? AND recipient=?) OR (sender=? AND recipient=?))",(uid(),other,other,uid())).fetchone():
            raise error('Adicione esta pessoa aos amigos para conversar.',403)
        if request.method=='POST':
            body=text(data(),'body',1500,1);tx();limit('community_dm','sender=?',(uid(),),20,60)
            db().execute('INSERT INTO community_dm(sender,recipient,body,created_at) VALUES(?,?,?,?)',(uid(),other,body,time.time()));db().commit()
        return jsonify(messages=rows('SELECT id,sender,body,created_at FROM community_dm WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?) ORDER BY id DESC LIMIT 80',(uid(),other,other,uid()))[::-1])

    @app.post('/api/community/reports')
    @auth()
    def community_report():
        d=data();typ=d.get('target_type');target=text(d,'target_id',100,1);reason=text(d,'reason',1000,3)
        if typ not in ('post','comment','room','profile','message','story'):raise error('Tipo de denúncia inválido.')
        tx();limit('community_reports','user_id=?',(uid(),),10,3600)
        db().execute('INSERT OR IGNORE INTO community_reports(user_id,target_type,target_id,reason,created_at) VALUES(?,?,?,?,?)',(uid(),typ,target,reason,time.time()));db().commit();return jsonify(ok=True),201

    @app.get('/api/community/config')
    @auth()
    def community_config():
        return jsonify(ice_servers=json.loads(os.getenv('FLIXJUMP_ICE_SERVERS','[{"urls":"stun:stun.l.google.com:19302"}]')),max_members=None)

    @app.route('/api/community/rooms',methods=['GET','POST'])
    @auth()
    def community_rooms():
        if request.method=='GET':
            offset=max(0,min(10000,int(request.args.get('offset',0))))
            rs=rows("SELECT r.id,r.title,r.description,r.kind,r.host_id,r.approval,r.created_at,r.cover,r.permanent,(SELECT kind FROM community_games cg WHERE cg.room_id=r.id AND cg.status IN ('lobby','playing')) game_kind,u.name,u.username,(SELECT COUNT(*) FROM community_members m JOIN users mu ON mu.id=m.user_id WHERE m.room_id=r.id AND m.status='joined' AND m.seen_at>? AND mu.status='active') members FROM community_rooms r JOIN users u ON u.id=r.host_id WHERE r.status='open' AND u.status='active' AND (r.post_id IS NULL OR EXISTS (SELECT 1 FROM community_posts cp JOIN users pu ON pu.id=cp.user_id WHERE cp.id=r.post_id AND cp.status='published' AND pu.status='active')) ORDER BY members DESC,r.created_at DESC LIMIT 31 OFFSET ?",(time.time()-45,offset))
            return jsonify(rooms=rs[:30],more=len(rs)>30)
        d=data();kind=d.get('kind')
        if kind not in ('watch','voice','video','live','music'):raise error('Tipo de sala inválido.')
        title,description=text(d,'title',120,2),text(d,'description',1000)
        tx();pid=d.get('post_id') or None
        source=post(pid)['url'] if pid else d.get('url')
        url,media=content_url(source,error,media=True,optional=kind in ('voice','video','live'))
        if kind in ('voice','video') and url:raise error('Escolha uma sala JumpFlix, música ou live para compartilhar mídia.')
        limit('community_rooms','host_id=?',(uid(),),12,3600)
        community_social.retain_assets(db(),url)
        cover,_=community_publishing.checked_url(d.get('cover',''),db(),error,external_url,image=True,optional=True)
        game_kind=d.get('game_kind')
        if game_kind and game_kind not in ('colors','draw'):raise error('Jogo inválido.')
        if game_kind and kind!='voice':raise error('Crie uma sala de jogos com voz.')
        community_social.retain_assets(db(),cover)
        rid=secrets.token_urlsafe(9);now=time.time()
        db().execute('INSERT INTO community_rooms(id,host_id,title,description,kind,url,media_type,post_id,approval,updated_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(rid,uid(),title,description,kind,url,media,pid,int(d.get('approval',True) is not False),now,now))
        db().execute('UPDATE community_rooms SET cover=?,permanent=? WHERE id=?',(cover,int(d.get('permanent') is True),rid))
        if game_kind:community_games.create_lobby(db(),rid,uid(),game_kind)
        if d.get('publish_to_feed') is True:
            limit('community_posts','user_id=?',(uid(),),15,3600)
            announcement=secrets.token_urlsafe(9)
            db().execute("INSERT INTO community_posts(id,user_id,kind,title,body,url,media_type,poster,created_at,updated_at) VALUES(?,?,'discussion',?,?,'','',?,?,?)",(announcement,uid(),title,description,cover,now,now))
            db().execute('INSERT INTO community_post_meta(post_id,room_id) VALUES(?,?)',(announcement,rid))
        db().execute("INSERT INTO community_members(room_id,user_id,status,joined_at,seen_at,seat) VALUES(?,?,'joined',?,?,1)",(rid,uid(),now,now));result=snapshot(rid);db().commit()
        return jsonify(room=result),201

    @app.get('/api/community/rooms/<rid>')
    @auth()
    def community_room_preview(rid):
        r=room(rid)
        host=person(r['host_id']);m=db().execute('SELECT status FROM community_members WHERE room_id=? AND user_id=?',(rid,uid())).fetchone()
        return jsonify(room={k:r[k] for k in ('id','title','description','kind','host_id','approval','cover','permanent')},host=dict(host),status=m[0] if m else 'new')

    @app.post('/api/community/rooms/<rid>/join')
    @auth()
    def community_join(rid):
        tx();r=room(rid);clean_seats(rid);m=db().execute('SELECT status FROM community_members WHERE room_id=? AND user_id=?',(rid,uid())).fetchone()
        status=m[0] if m else ('pending' if r['approval'] and r['host_id']!=uid() else 'joined')
        if status=='left':status='pending' if r['approval'] and r['host_id']!=uid() else 'joined'
        if status in ('rejected','banned'):raise error('O anfitrião recusou ou removeu seu acesso a esta sala.',403)
        now=time.time()
        db().execute("INSERT INTO community_members(room_id,user_id,status,joined_at,seen_at) VALUES(?,?,?,?,?) ON CONFLICT(room_id,user_id) DO UPDATE SET joined_at=CASE WHEN community_members.status='left' THEN excluded.joined_at ELSE community_members.joined_at END,status=excluded.status,seen_at=excluded.seen_at",(rid,uid(),status,now,now))
        result={'room':snapshot(rid)} if status=='joined' else {'status':'pending'}
        db().commit();return jsonify(result),200 if status=='joined' else 202

    @app.patch('/api/community/rooms/<rid>/members/<other>')
    @auth()
    def community_member(rid,other):
        d=data();decision=d.get('decision');tx();r=room(rid,host=True);clean_seats(rid)
        if other==uid():raise error('Você é o anfitrião.')
        member=db().execute("SELECT m.* FROM community_members m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.user_id=? AND u.status='active'",(rid,other)).fetchone()
        if not member:raise error('Participante não encontrado.',404)
        statuses={'approve':'joined','reject':'rejected','remove':'banned'}
        if decision in statuses:
            if decision in ('approve','reject') and member['status']!='pending':raise error('Solicitação não encontrada.',404)
            db().execute('UPDATE community_members SET status=?,seat=NULL,mic=0,camera=0 WHERE room_id=? AND user_id=?',(statuses[decision],rid,other))
        elif decision in ('promote','demote','mute','allow_mic','reject_stage'):
            if member['status']!='joined' or member['seen_at']<=time.time()-45:raise error('O participante precisa estar conectado.',409)
            if decision=='promote':
                if r['kind']=='live' and member['stage_request']!='requested':
                    db().execute("UPDATE community_members SET stage_request='invited',stage_at=? WHERE room_id=? AND user_id=? AND seat IS NULL",(time.time(),rid,other))
                    result=snapshot(rid);db().commit();return jsonify(room=result)
                if member['seat'] is None:
                    occupied={r[0] for r in db().execute('SELECT seat FROM community_members WHERE room_id=? AND seat IS NOT NULL',(rid,))}
                    maximum=4 if r['kind']=='live' else 8
                    seat=next((n for n in range(2,maximum+1) if n not in occupied),None)
                    if seat is None:raise error(f'Os {maximum} assentos estão ocupados. Retorne alguém à plateia primeiro.',409)
                    db().execute("UPDATE community_members SET seat=?,mic=0,camera=0,stage_request='' WHERE room_id=? AND user_id=?",(seat,rid,other))
            elif decision=='reject_stage':db().execute("UPDATE community_members SET stage_request='' WHERE room_id=? AND user_id=?",(rid,other))
            elif decision=='demote':db().execute('UPDATE community_members SET seat=NULL,mic=0,camera=0 WHERE room_id=? AND user_id=?',(rid,other))
            else:db().execute('UPDATE community_members SET mic_blocked=?,mic=0 WHERE room_id=? AND user_id=?',(int(decision=='mute'),rid,other))
        else:raise error('Decisão inválida.')
        result=snapshot(rid);db().commit();return jsonify(room=result)

    @app.post('/api/community/rooms/<rid>/stage')
    @auth()
    def live_stage(rid):
        d=data();tx();r=room(rid,True);clean_seats(rid)
        if r['kind']!='live' or r['host_id']==uid():raise error('Esta ação é para convidados de uma live.')
        me=db().execute('SELECT * FROM community_members WHERE room_id=? AND user_id=?',(rid,uid())).fetchone()
        if me['seen_at']<time.time()-45:raise error('Entre novamente na sala.',409)
        action=d.get('action')
        if action=='request':
            if not me['seat'] and me['stage_request']!='requested':
                if me['stage_at']>time.time()-10:raise error('Aguarde antes de pedir novamente.',429)
                db().execute("UPDATE community_members SET stage_request='requested',stage_at=? WHERE room_id=? AND user_id=?",(time.time(),rid,uid()))
        elif action=='accept':
            if me['stage_request']!='invited':raise error('O convite não está mais disponível.',409)
            occupied={v[0] for v in db().execute('SELECT seat FROM community_members WHERE room_id=? AND seat IS NOT NULL',(rid,))}
            seat=next((n for n in range(2,5) if n not in occupied),None)
            if seat is None:raise error('A live já tem 4 participantes. Aguarde uma vaga.',409)
            db().execute("UPDATE community_members SET seat=?,stage_request='',mic=0,camera=0,seen_at=? WHERE room_id=? AND user_id=?",(seat,time.time(),rid,uid()))
        elif action in ('cancel','decline','leave'):
            db().execute("UPDATE community_members SET stage_request='',seat=NULL,mic=0,camera=0 WHERE room_id=? AND user_id=?",(rid,uid()))
        else:raise error('Ação inválida.')
        result=snapshot(rid);db().commit();return jsonify(room=result)

    @app.post('/api/community/rooms/<rid>/poll')
    @auth()
    def community_poll(rid):
        d=data();cursor=max(0,int(d.get('cursor',0)));tx();r=room(rid,True)
        mic=d.get('mic',False) is True;camera=d.get('camera',False) is True
        clean_seats(rid)
        permissions=db().execute('SELECT seat,mic_blocked FROM community_members WHERE room_id=? AND user_id=?',(rid,uid())).fetchone()
        if permissions['seat'] is None:mic=camera=False
        if permissions['mic_blocked']:mic=False
        if r['kind'] not in ('video','live'):camera=False
        db().execute('UPDATE community_members SET seen_at=?,mic=?,camera=? WHERE room_id=? AND user_id=?',(time.time(),int(mic),int(camera),rid,uid()))
        db().execute('DELETE FROM community_signals WHERE created_at<?',(time.time()-90,))
        signals=rows('SELECT id,sender,payload FROM community_signals WHERE room_id=? AND recipient=? AND id>? ORDER BY id LIMIT 200',(rid,uid(),cursor))
        for s in signals:s['payload']=json.loads(s['payload'])
        result=snapshot(rid);db().commit();return jsonify(room=result,signals=signals)

    @app.patch('/api/community/rooms/<rid>/playback')
    @auth()
    def community_playback(rid):
        d=data();pos=float(d.get('position',0));tx();r=room(rid,True,True)
        if int(d.get('revision',-1))!=r['revision']:raise error('A sala mudou. Atualize e tente novamente.',409)
        if not math.isfinite(pos) or not 0<=pos<=time.time()+300 or not isinstance(d.get('paused'),bool):raise error('Posição inválida.')
        db().execute('UPDATE community_rooms SET position=?,paused=?,revision=revision+1,updated_at=? WHERE id=?',(pos,int(d['paused']),time.time(),rid));result=snapshot(rid);db().commit();return jsonify(room=result)

    @app.post('/api/community/rooms/<rid>/messages')
    @auth()
    def community_room_message(rid):
        body=text(data(),'body',1000,1);tx();room(rid,True);limit('community_messages','user_id=?',(uid(),),12,10)
        db().execute('INSERT INTO community_messages(room_id,user_id,body,created_at) VALUES(?,?,?,?)',(rid,uid(),body,time.time()))
        db().execute('DELETE FROM community_messages WHERE room_id=? AND id NOT IN (SELECT id FROM community_messages WHERE room_id=? ORDER BY id DESC LIMIT 200)',(rid,rid));db().commit();return jsonify(ok=True),201

    @app.post('/api/community/rooms/<rid>/signals')
    @auth()
    def community_signal(rid):
        d=data();other=str(d.get('recipient',''));payload=d.get('payload');tx();r=room(rid,True)
        if not isinstance(payload,dict) or payload.get('type') not in ('offer','answer','candidate') or len(json.dumps(payload))>25000:raise error('Sinal inválido.')
        if not db().execute("SELECT 1 FROM community_members m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.user_id=? AND m.status='joined' AND m.seen_at>? AND u.status='active'",(rid,other,time.time()-45)).fetchone():raise error('Participante indisponível.',404)
        clean_seats(rid)
        if not db().execute('SELECT 1 FROM community_members WHERE room_id=? AND user_id IN (?,?) AND seat IS NOT NULL',(rid,uid(),other)).fetchone():raise error('A plateia só pode conectar áudio e vídeo com os assentos.',403)
        limit('community_signals','sender=?',(uid(),),3000,60)
        db().execute('INSERT INTO community_signals(room_id,sender,recipient,payload,created_at) VALUES(?,?,?,?,?)',(rid,uid(),other,json.dumps(payload),time.time()));db().commit();return jsonify(ok=True)

    @app.post('/api/community/rooms/<rid>/leave')
    @auth()
    def community_leave(rid):
        tx()
        db().execute("UPDATE community_members SET status='left',seat=CASE WHEN user_id=(SELECT host_id FROM community_rooms WHERE id=room_id) THEN 1 ELSE NULL END,mic=0,camera=0,stage_request='' WHERE room_id=? AND user_id=? AND status IN ('joined','pending')",(rid,uid()))
        room_lifecycle.repair(db(),rid);db().commit();return jsonify(ok=True)

    @app.patch('/api/community/rooms/<rid>')
    @auth()
    def community_room_settings(rid):
        d=data();title=text(d,'title',120,2);description=text(d,'description',1000);tx();r=room(rid,host=True)
        db().execute('UPDATE community_rooms SET title=?,description=?,approval=?,permanent=? WHERE id=?',(title,description,int(d.get('approval',True) is not False),int(d.get('permanent',bool(r['permanent'])) is True),rid))
        db().commit();return jsonify(ok=True)

    @app.delete('/api/community/rooms/<rid>')
    @auth()
    def community_close(rid):
        tx();room(rid,host=True);db().execute("UPDATE community_rooms SET status='closed' WHERE id=?",(rid,));db().commit();return jsonify(ok=True)

    @app.post('/api/community/rooms/<rid>/queue')
    @auth()
    def community_enqueue(rid):
        d=data();title=text(d,'title',160,2);url,media=content_url(d.get('url'),error,media=True);tx();room(rid,True,True)
        if db().execute('SELECT COUNT(*) FROM community_queue WHERE room_id=?',(rid,)).fetchone()[0]>=100:raise error('A fila tem 100 itens. Reproduza ou remova um para adicionar outro.')
        community_social.retain_assets(db(),url)
        db().execute('INSERT INTO community_queue(room_id,title,url,media_type,created_at) VALUES(?,?,?,?,?)',(rid,title,url,media,time.time()));db().commit();return jsonify(ok=True),201

    @app.route('/api/community/rooms/<rid>/queue/<int:item>',methods=['POST','DELETE'])
    @auth()
    def community_queue(rid,item):
        tx();r=room(rid,True,True);q=db().execute('SELECT * FROM community_queue WHERE id=? AND room_id=?',(item,rid)).fetchone()
        if not q:raise error('Item não encontrado.',404)
        if request.method=='POST':db().execute('UPDATE community_rooms SET url=?,media_type=?,post_id=NULL,position=0,paused=1,revision=revision+1,updated_at=? WHERE id=?',(q['url'],q['media_type'],time.time(),rid))
        db().execute('DELETE FROM community_queue WHERE id=?',(item,));db().commit();return jsonify(ok=True)

    @app.get('/api/admin/community')
    @auth(admin=True)
    def community_admin():
        q='%'+request.args.get('q','')[:100]+'%';offset=max(0,min(10000,int(request.args.get('offset',0))))
        counts={t:db().execute(f'SELECT COUNT(*) FROM community_{t}').fetchone()[0] for t in ('posts','rooms','reports','badges')}
        counts['online']=db().execute("SELECT COUNT(DISTINCT user_id) FROM community_members WHERE status='joined' AND seen_at>?",(time.time()-45,)).fetchone()[0]
        counts['open_reports']=db().execute("SELECT COUNT(*) FROM community_reports WHERE status='open'").fetchone()[0]
        return jsonify(counts=counts,posts=[community_publishing.enrich(db(),p) for p in rows('SELECT p.*,u.username FROM community_posts p JOIN users u ON u.id=p.user_id WHERE p.title LIKE ? OR u.username LIKE ? ORDER BY p.created_at DESC LIMIT 50 OFFSET ?',(q,q,offset))],rooms=rows('SELECT r.*,u.username FROM community_rooms r JOIN users u ON u.id=r.host_id WHERE r.title LIKE ? OR u.username LIKE ? ORDER BY r.created_at DESC LIMIT 50 OFFSET ?',(q,q,offset)),reports=rows('SELECT r.*,u.username FROM community_reports r LEFT JOIN users u ON u.id=r.user_id ORDER BY r.status,r.created_at DESC LIMIT 50 OFFSET ?',(offset,)),badges=rows('SELECT * FROM community_badges ORDER BY name'),awards=rows('SELECT a.*,u.username,b.name FROM community_awards a JOIN users u ON u.id=a.user_id JOIN community_badges b ON b.id=a.badge_id ORDER BY a.created_at DESC LIMIT 100'),audit=rows('SELECT a.*,u.username FROM community_audit a LEFT JOIN users u ON u.id=a.admin_id ORDER BY a.id DESC LIMIT 50'),comments=rows('SELECT c.*,u.username FROM community_comments c JOIN users u ON u.id=c.user_id WHERE c.body LIKE ? OR u.username LIKE ? ORDER BY c.id DESC LIMIT 50 OFFSET ?',(q,q,offset)),messages=rows('SELECT c.*,u.username FROM community_messages c JOIN users u ON u.id=c.user_id WHERE c.body LIKE ? OR u.username LIKE ? ORDER BY c.id DESC LIMIT 50 OFFSET ?',(q,q,offset)))

    @app.patch('/api/admin/community/<kind>/<target>')
    @auth(admin=True)
    def community_moderate(kind,target):
        d=data();tx();action=d.get('action')
        if kind=='posts' and action in ('publish','hide','feature','unfeature'):
            if action in ('feature','unfeature'):cur=db().execute('UPDATE community_posts SET featured=? WHERE id=?',(int(action=='feature'),target))
            else:cur=db().execute('UPDATE community_posts SET status=? WHERE id=?',('published' if action=='publish' else 'hidden',target))
        elif kind=='rooms' and action=='edit':
            title=text(d,'title',120,2);description=text(d,'description',1000)
            cur=db().execute('UPDATE community_rooms SET title=?,description=?,approval=? WHERE id=?',(title,description,int(d.get('approval',True) is not False),target))
        elif kind=='rooms' and action in ('close','reopen'):
            cur=db().execute('UPDATE community_rooms SET status=? WHERE id=?',('open' if action=='reopen' else 'closed',target))
            if action=='close':db().execute("UPDATE community_members SET status='left',seat=CASE WHEN user_id=(SELECT host_id FROM community_rooms WHERE id=room_id) THEN 1 ELSE NULL END,mic=0,camera=0 WHERE room_id=? AND status IN ('joined','pending')",(target,))
        elif kind=='reports' and action in ('resolve','reopen'):
            cur=db().execute('UPDATE community_reports SET status=? WHERE id=?',('resolved' if action=='resolve' else 'open',target))
        elif kind in ('comments','messages') and action=='delete':cur=db().execute(f'DELETE FROM community_{kind} WHERE id=?',(target,))
        elif kind=='profiles' and action=='reset':cur=db().execute("UPDATE community_profiles SET bio='',avatar='',avatar_png=NULL,cover='',location='',website='',favorite_genres='' WHERE user_id=?",(target,))
        else:raise error('Ação inválida.')
        if not cur.rowcount:raise error('Registro não encontrado.',404)
        audit(kind+':'+action,target);db().commit();return jsonify(ok=True)

    @app.route('/api/admin/community/badges',methods=['POST'])
    @app.route('/api/admin/community/badges/<bid>',methods=['DELETE','PUT'])
    @auth(admin=True)
    def community_badge(bid=None):
        tx()
        if request.method=='DELETE':db().execute('DELETE FROM community_badges WHERE id=?',(bid,))
        else:
            d=data();name=text(d,'name',60,2);description=text(d,'description',240);symbol=d.get('symbol','spark');color=d.get('color','#b393ff')
            if symbol not in ('spark','film','users','shield','heart','tv','globe') or not re.fullmatch(r'#[0-9a-fA-F]{6}',str(color)):raise error('Símbolo ou cor inválidos.')
            bid=bid or secrets.token_urlsafe(9)
            db().execute('INSERT INTO community_badges VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,description=excluded.description,symbol=excluded.symbol,color=excluded.color',(bid,name,description,symbol,color))
        audit('badge:'+request.method,bid);db().commit();return jsonify(ok=True,id=bid)

    @app.route('/api/admin/community/awards',methods=['POST','DELETE'])
    @auth(admin=True)
    def community_award():
        d=data();user=db().execute('SELECT id FROM users WHERE username=?',(str(d.get('username','')).lstrip('@'),)).fetchone();bid=d.get('badge_id')
        if not user or not db().execute('SELECT 1 FROM community_badges WHERE id=?',(bid,)).fetchone():raise error('Usuário ou emblema não encontrado.',404)
        tx()
        if request.method=='POST':db().execute('INSERT OR IGNORE INTO community_awards VALUES(?,?,?,?)',(user[0],bid,uid(),time.time()))
        else:db().execute('DELETE FROM community_awards WHERE user_id=? AND badge_id=?',(user[0],bid))
        audit('award:'+request.method,user[0]+':'+bid);db().commit();return jsonify(ok=True)

    community_publishing.register(app, db, auth, data, error, external_url)
    community_games.register(app, db, auth, data, error, room)
    social_hub.register(app,db,auth,data,error)
    community_social.register(app, db, auth, data, error, external_url, room, post)
