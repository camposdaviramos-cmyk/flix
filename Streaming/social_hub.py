import reel_studio
"""Private messaging, activity, calls and transactional notification inbox."""
import base64
import datetime
import json
import re
import secrets
import notification_payload
import time
from pathlib import Path
from flask import g, jsonify, request, send_file
from cryptography.hazmat.primitives.asymmetric import ec

PREFS={'presence':'available','status_text':'','show_activity':False,'messages':True,'social':True,'rooms':True,'account':True,'calls':True,'sounds':True,'message_preview':True}

def migrate(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS hub_preferences(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,payload TEXT NOT NULL DEFAULT '{}');
    CREATE TABLE IF NOT EXISTS hub_notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,actor_id TEXT,category TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL DEFAULT '',href TEXT NOT NULL,created_at REAL NOT NULL,read_at REAL,dedupe TEXT,UNIQUE(user_id,dedupe));
    CREATE INDEX IF NOT EXISTS hub_notification_owner ON hub_notifications(user_id,id DESC);
    CREATE TABLE IF NOT EXISTS hub_push(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,endpoint TEXT UNIQUE NOT NULL,p256dh TEXT NOT NULL,auth TEXT NOT NULL,created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS hub_deliveries(notification_id INTEGER REFERENCES hub_notifications(id) ON DELETE CASCADE,subscription_id TEXT REFERENCES hub_push(id) ON DELETE CASCADE,attempts INTEGER NOT NULL DEFAULT 0,retry_at REAL NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'pending',PRIMARY KEY(notification_id,subscription_id));
    CREATE TABLE IF NOT EXISTS hub_dm_media(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,mime TEXT NOT NULL,bytes INTEGER NOT NULL,created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS hub_dm_meta(message_id INTEGER PRIMARY KEY REFERENCES community_dm(id) ON DELETE CASCADE,attachment_id TEXT REFERENCES hub_dm_media(id),share_kind TEXT,share_id TEXT,client_id TEXT);
    CREATE UNIQUE INDEX IF NOT EXISTS hub_dm_client ON hub_dm_meta(client_id) WHERE client_id IS NOT NULL;
    CREATE TABLE IF NOT EXISTS hub_streak_days(first_id TEXT REFERENCES users(id) ON DELETE CASCADE,second_id TEXT REFERENCES users(id) ON DELETE CASCADE,day TEXT NOT NULL,first_sent INTEGER NOT NULL DEFAULT 0,second_sent INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(first_id,second_id,day));
    CREATE TABLE IF NOT EXISTS hub_activity(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,source TEXT NOT NULL,target_id TEXT NOT NULL,updated_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS hub_watch(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,source TEXT NOT NULL,target_id TEXT NOT NULL,watched_at REAL NOT NULL,PRIMARY KEY(user_id,source,target_id));
    CREATE TABLE IF NOT EXISTS hub_calls(id TEXT PRIMARY KEY,caller TEXT REFERENCES users(id) ON DELETE CASCADE,callee TEXT REFERENCES users(id) ON DELETE CASCADE,kind TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'ringing',created_at REAL NOT NULL,updated_at REAL NOT NULL,caller_seen REAL NOT NULL,callee_seen REAL NOT NULL DEFAULT 0,answered_at REAL);
    CREATE INDEX IF NOT EXISTS hub_call_members ON hub_calls(caller,callee,status);
    CREATE TABLE IF NOT EXISTS hub_call_signals(id INTEGER PRIMARY KEY AUTOINCREMENT,call_id TEXT REFERENCES hub_calls(id) ON DELETE CASCADE,sender TEXT REFERENCES users(id) ON DELETE CASCADE,payload TEXT NOT NULL,created_at REAL NOT NULL);
    ''')
    # Triggers run in the originating transaction, so rolled-back actions never notify.
    now="CAST(strftime('%s','now') AS REAL)"
    def trigger(name,table,event,select,condition='1'):
        db.execute(f'CREATE TRIGGER IF NOT EXISTS hub_{name} AFTER {event} ON {table} WHEN {condition} BEGIN INSERT OR IGNORE INTO hub_notifications(user_id,actor_id,category,title,body,href,created_at,dedupe) {select}; END')
    actor="COALESCE((SELECT name FROM users WHERE id=NEW.user_id),'Alguém')"
    trigger('friend_request','jump_friends','INSERT',f"SELECT NEW.recipient,NEW.sender,'social','Pedido de amizade',(SELECT name FROM users WHERE id=NEW.sender)||' quer adicionar você.','/comunidade?tab=friends',{now},'friend:'||NEW.sender||':'||NEW.created_at", "NEW.status='pending'")
    trigger('friend_accept','jump_friends','UPDATE',f"SELECT NEW.sender,NEW.recipient,'social','Amizade aceita',(SELECT name FROM users WHERE id=NEW.recipient)||' aceitou seu pedido.','/comunidade?tab=friends&dm='||NEW.recipient,{now},'friend-accepted:'||NEW.recipient||':'||NEW.created_at", "NEW.status='accepted' AND OLD.status!='accepted'")
    trigger('jump_invite','jump_invites','INSERT',f"SELECT NEW.user_id,r.host_id,'rooms','Convite para assistir',c.title,'/sala/'||r.id,{now},'jump-invite:'||r.id FROM jump_rooms r JOIN content c ON c.id=r.content_id WHERE r.id=NEW.room_id")
    trigger('jump_request','jump_requests','INSERT',f"SELECT r.host_id,NEW.user_id,'rooms','Pedido para entrar no FlixJump',{actor}||' quer assistir com você.','/sala/'||r.id,{now},'jump-request:'||r.id||':'||NEW.user_id||':'||NEW.created_at FROM jump_rooms r WHERE r.id=NEW.room_id", "NEW.status='pending'")
    trigger('jump_decision','jump_requests','UPDATE',f"SELECT NEW.user_id,r.host_id,'rooms',CASE WHEN NEW.status='approved' THEN 'Entrada no FlixJump aceita' ELSE 'Pedido recusado' END,c.title,'/sala/'||r.id,{now},'jump-decision:'||r.id||':'||NEW.created_at FROM jump_rooms r JOIN content c ON c.id=r.content_id WHERE r.id=NEW.room_id", "NEW.status IN ('approved','rejected') AND OLD.status='pending'")
    trigger('jump_host','jump_rooms','UPDATE',f"SELECT NEW.host_id,OLD.host_id,'rooms','Você é o anfitrião do FlixJump','Os controles do player estão com você.','/sala/'||NEW.id,{now},'jump-host:'||NEW.id||':'||NEW.revision", "NEW.host_id!=OLD.host_id")
    trigger('dm','community_dm','INSERT',f"SELECT NEW.recipient,NEW.sender,'messages','Nova mensagem',(SELECT name FROM users WHERE id=NEW.sender)||' enviou uma mensagem.','/comunidade?tab=friends&dm='||NEW.sender,NEW.created_at,'dm:'||NEW.id")
    db.executescript('''CREATE TRIGGER IF NOT EXISTS hub_streak AFTER INSERT ON community_dm BEGIN
      INSERT INTO hub_streak_days(first_id,second_id,day,first_sent,second_sent) VALUES(MIN(NEW.sender,NEW.recipient),MAX(NEW.sender,NEW.recipient),date(NEW.created_at,'unixepoch','-3 hours'),NEW.sender<NEW.recipient,NEW.sender>NEW.recipient)
      ON CONFLICT(first_id,second_id,day) DO UPDATE SET first_sent=MAX(first_sent,excluded.first_sent),second_sent=MAX(second_sent,excluded.second_sent); END;''')
    trigger('follow','community_follows','INSERT',f"SELECT NEW.following,NEW.follower,'social','Novo seguidor',(SELECT name FROM users WHERE id=NEW.follower)||' começou a seguir você.','/comunidade/perfil/'||(SELECT username FROM users WHERE id=NEW.follower),NEW.created_at,'follow:'||NEW.follower")
    trigger('comment','community_comments','INSERT',f"SELECT p.user_id,NEW.user_id,'social','Novo comentário',{actor}||' comentou em '||p.title,'/comunidade/post/'||p.id,NEW.created_at,'comment:'||NEW.id FROM community_posts p WHERE p.id=NEW.post_id AND p.user_id!=NEW.user_id")
    trigger('like','community_likes','INSERT',f"SELECT p.user_id,NEW.user_id,'social','Curtiram sua publicação',{actor}||' curtiu '||p.title,'/comunidade/post/'||p.id,NEW.created_at,'like:'||p.id||':'||NEW.user_id FROM community_posts p WHERE p.id=NEW.post_id AND p.user_id!=NEW.user_id")
    trigger('reaction','community_reactions','INSERT',f"SELECT p.user_id,NEW.user_id,'social','Nova reação',{actor}||' reagiu a '||p.title,'/comunidade/post/'||p.id,NEW.created_at,'reaction:'||p.id||':'||NEW.user_id FROM community_posts p WHERE NEW.target_type='post' AND p.id=NEW.target_id AND p.user_id!=NEW.user_id")
    trigger('story_reaction','community_reactions','INSERT',f"SELECT s.user_id,NEW.user_id,'social','Reagiram ao seu story',{actor}||' reagiu ao seu story.','/comunidade',NEW.created_at,'story-reaction:'||s.id||':'||NEW.user_id FROM community_stories s WHERE NEW.target_type='story' AND s.id=NEW.target_id AND s.user_id!=NEW.user_id")
    trigger('publication','community_posts','INSERT',f"SELECT f.follower,NEW.user_id,'social','Nova publicação',{actor}||' publicou '||NEW.title,'/comunidade/post/'||NEW.id,NEW.created_at,'post:'||NEW.id FROM community_follows f WHERE f.following=NEW.user_id", "NEW.status='published'")
    for event in ('INSERT','UPDATE'):
        extra=" AND j.value NOT IN (SELECT value FROM json_each(OLD.people))" if event=='UPDATE' else ''
        trigger('mention_'+event.lower(),'community_post_meta',event,f"SELECT j.value,p.user_id,'social','Você foi marcado',u.name||' marcou você em '||p.title,'/comunidade/post/'||p.id,{now},'mention:'||p.id FROM json_each(NEW.people) j JOIN users target ON target.id=j.value AND target.status='active' JOIN community_posts p ON p.id=NEW.post_id JOIN users u ON u.id=p.user_id WHERE j.value!=p.user_id{extra}")
    trigger('badge','community_awards','INSERT',f"SELECT NEW.user_id,NEW.awarded_by,'social','Novo emblema','Você recebeu: '||(SELECT name FROM community_badges WHERE id=NEW.badge_id),'/comunidade/perfil/'||(SELECT username FROM users WHERE id=NEW.user_id),NEW.created_at,'badge:'||NEW.badge_id||':'||NEW.created_at")
    trigger('game_result','community_game_results','INSERT',"SELECT NEW.user_id,NULL,'rooms','Resultado da partida','Você ganhou '||NEW.points||' pontos.','/comunidade?tab=ranking',NEW.created_at,'game-result:'||NEW.game_id")
    trigger('room_request','community_members','INSERT',f"SELECT r.host_id,NEW.user_id,'rooms','Pedido para entrar na sala',{actor}||' quer entrar em '||r.title,'/comunidade/sala/'||r.id,{now},'room-request:'||r.id||':'||NEW.user_id||':'||NEW.joined_at FROM community_rooms r WHERE r.id=NEW.room_id", "NEW.status='pending'")
    trigger('room_request_again','community_members','UPDATE',f"SELECT r.host_id,NEW.user_id,'rooms','Pedido para entrar na sala',{actor}||' quer entrar em '||r.title,'/comunidade/sala/'||r.id,{now},'room-request:'||r.id||':'||NEW.user_id||':'||NEW.seen_at FROM community_rooms r WHERE r.id=NEW.room_id", "NEW.status='pending' AND OLD.status!='pending'")
    trigger('room_decision','community_members','UPDATE',f"SELECT NEW.user_id,r.host_id,'rooms',CASE WHEN NEW.status='joined' THEN 'Entrada aceita' ELSE 'Solicitação recusada' END,r.title,'/comunidade/sala/'||r.id,{now},'room-decision:'||r.id||':'||NEW.user_id||':'||NEW.joined_at FROM community_rooms r WHERE r.id=NEW.room_id", "OLD.status='pending' AND NEW.status IN ('joined','rejected')")
    trigger('stage_request','community_members','UPDATE',f"SELECT r.host_id,NEW.user_id,'rooms','Pedido para participar da live',{actor}||' quer entrar na transmissão.','/comunidade/sala/'||r.id,{now},'stage-request:'||r.id||':'||NEW.user_id||':'||NEW.stage_at FROM community_rooms r WHERE r.id=NEW.room_id", "NEW.stage_request='requested' AND OLD.stage_request!='requested'")
    trigger('stage_invite','community_members','UPDATE',f"SELECT NEW.user_id,r.host_id,'rooms','Convite para participar da live',r.title,'/comunidade/sala/'||r.id,{now},'stage-invite:'||r.id||':'||NEW.stage_at FROM community_rooms r WHERE r.id=NEW.room_id", "NEW.stage_request='invited' AND OLD.stage_request!='invited'")
    trigger('stage_accept','community_members','UPDATE',f"SELECT NEW.user_id,r.host_id,'rooms','Você está no palco',r.title||' — ative sua câmera ou microfone quando estiver pronto.','/comunidade/sala/'||r.id,{now},'stage-accept:'||r.id||':'||NEW.stage_at FROM community_rooms r WHERE r.id=NEW.room_id", "OLD.seat IS NULL AND NEW.seat IS NOT NULL AND NEW.seat!=1")
    trigger('host_change','community_rooms','UPDATE',f"SELECT NEW.host_id,OLD.host_id,'rooms','Você é o novo anfitrião',NEW.title,'/comunidade/sala/'||NEW.id,{now},'host:'||NEW.id||':'||NEW.revision", 'NEW.host_id!=OLD.host_id')
    trigger('room_closed','community_rooms','UPDATE',f"SELECT m.user_id,NEW.host_id,'rooms','Sala encerrada',NEW.title,'/comunidade?tab=rooms',{now},'closed:'||NEW.id FROM community_members m WHERE m.room_id=NEW.id AND m.status IN ('joined','pending') AND m.user_id!=NEW.host_id", "OLD.status='open' AND NEW.status='closed'")
    trigger('room_message','community_messages','INSERT',f"SELECT m.user_id,NEW.user_id,'rooms','Mensagem na sala',r.title||' — '||{actor},'/comunidade/sala/'||r.id,NEW.created_at,'room-message:'||NEW.id FROM community_members m JOIN community_rooms r ON r.id=m.room_id WHERE m.room_id=NEW.room_id AND m.status='joined' AND m.user_id!=NEW.user_id AND m.seen_at>{now}-45")
    trigger('game_invite','community_games','INSERT',f"SELECT m.user_id,r.host_id,'rooms','Vamos jogar?',r.title||' abriu uma partida.','/comunidade/sala/'||r.id,{now},'game-invite:'||NEW.id FROM community_members m JOIN community_rooms r ON r.id=m.room_id WHERE m.room_id=NEW.room_id AND m.status='joined' AND m.user_id!=r.host_id")
    trigger('call','hub_calls','INSERT',"SELECT NEW.callee,NEW.caller,'calls','Chamada recebida',(SELECT name FROM users WHERE id=NEW.caller)||' está chamando você.','/comunidade?call='||NEW.id,NEW.created_at,'call:'||NEW.id")
    trigger('call_missed','hub_calls','UPDATE',f"SELECT NEW.callee,NEW.caller,'calls','Chamada perdida',(SELECT name FROM users WHERE id=NEW.caller)||' tentou ligar.','/comunidade?tab=friends&dm='||NEW.caller,{now},'call-missed:'||NEW.id", "OLD.status='ringing' AND NEW.status IN ('missed','cancelled')")
    trigger('plan','users','UPDATE',f"SELECT NEW.id,NULL,'account','Seu plano foi atualizado','Confira o acesso e a validade da sua conta.','/conta',{now},NULL", "COALESCE(OLD.plan_id,'')!=COALESCE(NEW.plan_id,'') OR COALESCE(OLD.expires_at,0)!=COALESCE(NEW.expires_at,0)")
    trigger('order','orders','UPDATE',f"SELECT NEW.user_id,NULL,'account','Pagamento atualizado',CASE WHEN NEW.status='paid' THEN 'Pagamento aprovado. Seu acesso está liberado.' ELSE 'Consulte a situação do pagamento na sua conta.' END,'/conta',{now},'order:'||NEW.id||':'||NEW.status", 'NEW.status!=OLD.status')
    trigger('signup','users','INSERT',f"SELECT u.id,NEW.id,'account','Novo usuário',NEW.name||' criou uma conta.','/admin?tab=users',{now},'signup:'||NEW.id FROM users u WHERE u.role='admin' AND u.id!=NEW.id")
    trigger('report','community_reports','INSERT',f"SELECT u.id,NEW.user_id,'account','Nova denúncia','Uma denúncia aguarda revisão.','/admin?tab=community-reports',{now},'report:'||NEW.id FROM users u WHERE u.role='admin'")
    # Queue only subscriptions that existed when the event happened.
    db.executescript('''CREATE TRIGGER IF NOT EXISTS hub_queue_push AFTER INSERT ON hub_notifications BEGIN
      INSERT OR IGNORE INTO hub_deliveries(notification_id,subscription_id,retry_at) SELECT NEW.id,s.id,NEW.created_at FROM hub_push s WHERE s.user_id=NEW.user_id; END;''')

def preferences(db,user):
    row=db.execute('SELECT payload FROM hub_preferences WHERE user_id=?',(user,)).fetchone()
    return {**PREFS,**(json.loads(row[0]) if row else {})}

def streak(db,a,b,now=None):
    # One shared daily streak: both friends must interact on each Brazilian calendar day.
    today=datetime.datetime.fromtimestamp(now or time.time(),datetime.timezone(datetime.timedelta(hours=-3))).date()
    days={r[0] for r in db.execute('SELECT day FROM hub_streak_days WHERE first_id=? AND second_id=? AND first_sent=1 AND second_sent=1 ORDER BY day DESC LIMIT 3660',tuple(sorted((a,b))))}
    start=today if today.isoformat() in days else today-datetime.timedelta(days=1)
    count=0
    while (start-datetime.timedelta(days=count)).isoformat() in days:count+=1
    return {'days':count if count>=2 else 0,'today_complete':today.isoformat() in days,'timezone':'America/Sao_Paulo'}

def profile_activity(db,user,viewer):
    pref=preferences(db,user);own=user==viewer
    seen=db.execute('SELECT seen_at FROM community_online WHERE user_id=?',(user,)).fetchone()
    online=bool(seen and seen[0]>time.time()-60 and pref['presence']!='invisible')
    value={'online':online,'presence':pref['presence'] if online or own else 'offline','status_text':pref['status_text'],'show_activity':pref['show_activity'],'recently_watched':[],'watching_now':None}
    if not (own or pref['show_activity']):return value
    def resolve(source,target):
        if source=='catalog':r=db.execute("SELECT id,title,poster,kind FROM content WHERE id=? AND published=1",(target,)).fetchone()
        else:r=db.execute("SELECT p.id,p.title,p.poster,p.kind FROM community_posts p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.status='published' AND u.status='active' AND (p.space_id IS NULL OR EXISTS(SELECT 1 FROM social_spaces ss WHERE ss.id=p.space_id AND ss.status='active' AND ss.privacy='public'))",(target,)).fetchone()
        return {**dict(r),'source':source,'href':('/titulo/' if source=='catalog' else '/comunidade/post/')+r['id']} if r else None
    recent=db.execute("SELECT source,target_id,MAX(watched_at) watched_at FROM (SELECT 'catalog' source,content_id target_id,watched_at FROM watch_history WHERE user_id=? UNION ALL SELECT source,target_id,watched_at FROM hub_watch WHERE user_id=?) GROUP BY source,target_id ORDER BY watched_at DESC LIMIT 12",(user,user)).fetchall()
    value['recently_watched']=[{**item,'watched_at':r['watched_at']} for r in recent if (item:=resolve(r['source'],r['target_id']))]
    current=db.execute('SELECT * FROM hub_activity WHERE user_id=? AND updated_at>?',(user,time.time()-45)).fetchone()
    if current and online:value['watching_now']=resolve(current['source'],current['target_id'])
    return value

def share_preview(db,kind,target):
    if kind=='story':
        import story_studio
        user=g.user['id'] if g.get('user') else ''
        r=db.execute("SELECT s.*,u.name FROM community_stories s JOIN users u ON u.id=s.user_id WHERE s.id=? AND s.status='published' AND s.expires_at>? AND u.status='active'",(target,time.time())).fetchone()
        if not r or not story_studio.visible(db,target,user):return None
        return {'kind':'story','id':target,'title':'Story de '+r['name'],'image':r['thumbnail'],'href':'/comunidade?story='+target}
    if kind in ('room','game'):
        r=db.execute("SELECT id,title,cover,kind FROM community_rooms WHERE id=? AND status='open'",(target,)).fetchone()
        return {'kind':kind,'id':target,'title':r['title'],'image':r['cover'],'href':'/comunidade/sala/'+target} if r else None
    if kind in ('music','playlist'):
        table='music_tracks' if kind=='music' else 'music_playlists'
        r=db.execute(('SELECT id,title,image FROM music_tracks WHERE id=?' if kind=='music' else 'SELECT id,name title,cover image FROM music_playlists WHERE id=? AND public=1'),(target,)).fetchone()
        return {**dict(r),'kind':kind,'href':'/comunidade?tab=music&'+('track' if kind=='music' else 'playlist')+'='+target} if r else None
    if kind in ('post','reel'):
        if not reel_studio.visible(db,target,g.user['id'] if g.get('user') else ''):return None
        r=db.execute("SELECT p.id,p.title,p.poster FROM community_posts p JOIN users u ON u.id=p.user_id WHERE p.id=? AND p.status='published' AND u.status='active' AND (p.space_id IS NULL OR EXISTS(SELECT 1 FROM social_spaces ss WHERE ss.id=p.space_id AND ss.status='active' AND ss.privacy='public'))",(target,)).fetchone()
        return {'kind':kind,'id':target,'title':r['title'],'image':r['poster'],'href':'/comunidade/post/'+target} if r else None
    return None

def messages(db,me,other,before=0):
    rs=db.execute('''SELECT d.*,m.attachment_id,m.share_kind,m.share_id,a.mime FROM community_dm d LEFT JOIN hub_dm_meta m ON m.message_id=d.id LEFT JOIN hub_dm_media a ON a.id=m.attachment_id WHERE ((sender=? AND recipient=?) OR (sender=? AND recipient=?)) AND (?=0 OR d.id<?) ORDER BY d.id DESC LIMIT 60''',(me,other,other,me,before,before)).fetchall()
    out=[]
    for r in reversed(rs):
        v={k:r[k] for k in ('id','sender','recipient','body','created_at')}
        if r['attachment_id']:v['audio']={'url':'/api/hub/media/'+r['attachment_id'],'mime':r['mime']}
        if r['share_kind']:v['share']=share_preview(db,r['share_kind'],r['share_id']) or {'unavailable':True,'title':'Conteúdo indisponível'}
        out.append(v)
    return out

def expire_calls(db):
    now=time.time()
    db.execute("UPDATE hub_calls SET status='missed',updated_at=? WHERE status='ringing' AND created_at<?",(now,now-45))
    db.execute("UPDATE hub_calls SET status='ended',updated_at=? WHERE status='accepted' AND (caller_seen<? OR callee_seen<?)",(now,now-60,now-60))
    db.execute('DELETE FROM hub_call_signals WHERE created_at<?',(now-120,))

def register(app,db,auth,data,error):
    directory=Path(app.config['DATA_DIR'])/'private-audio';directory.mkdir(exist_ok=True)
    def uid():return g.user['id']
    def friend(other):
        if other==uid() or not db().execute("SELECT 1 FROM jump_friends f JOIN users u ON u.id=? AND u.status='active' WHERE f.status='accepted' AND ((f.sender=? AND f.recipient=?) OR (f.sender=? AND f.recipient=?))",(other,uid(),other,other,uid())).fetchone():raise error('Adicione esta pessoa aos amigos para conversar.',403)
    def limited(table,field,n,seconds):
        if db().execute(f'SELECT COUNT(*) FROM {table} WHERE {field}=? AND created_at>?',(uid(),time.time()-seconds)).fetchone()[0]>=n:raise error('Muitas solicitações. Aguarde um momento.',429)
    def call_record(cid):
        expire_calls(db())
        r=db().execute("SELECT c.*,u.name caller_name,v.name callee_name,COALESCE(p.avatar,'') caller_avatar,COALESCE(q.avatar,'') callee_avatar FROM hub_calls c JOIN users u ON u.id=c.caller AND u.status='active' JOIN users v ON v.id=c.callee AND v.status='active' LEFT JOIN community_profiles p ON p.user_id=u.id LEFT JOIN community_profiles q ON q.user_id=v.id WHERE c.id=? AND (c.caller=? OR c.callee=?)",(cid,uid(),uid())).fetchone()
        if not r:raise error('Chamada não encontrada.',404)
        return dict(r)

    @app.route('/api/hub/preferences',methods=['GET','PATCH'])
    @auth()
    def hub_prefs():
        value=preferences(db(),uid())
        if request.method=='PATCH':
            d=data()
            for k in PREFS:
                if k not in d:continue
                if k=='presence':
                    if d[k] not in ('available','busy','invisible'):raise error('Status inválido.')
                elif k=='status_text':
                    if not isinstance(d[k],str) or len(d[k])>100:raise error('Use até 100 caracteres no status.')
                elif not isinstance(d[k],bool):raise error('Preferência inválida.')
                value[k]=d[k]
            db().execute('INSERT INTO hub_preferences VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET payload=excluded.payload',(uid(),json.dumps(value)));db().commit()
        return jsonify(preferences=value)

    @app.get('/api/hub/notifications')
    @auth()
    def hub_notifications():
        after=max(0,int(request.args.get('after',0)));before=max(0,int(request.args.get('before',0)))
        rows=[dict(r) for r in db().execute('SELECT id,user_id,actor_id,dedupe,category,title,body,href,created_at,read_at FROM hub_notifications WHERE user_id=? AND id>? AND (?=0 OR id<?) ORDER BY id DESC LIMIT 60',(uid(),after,before,before))]
        unread=db().execute('SELECT COUNT(*) FROM hub_notifications WHERE user_id=? AND read_at IS NULL',(uid(),)).fetchone()[0]
        return jsonify(notifications=[{**n,**notification_payload.build(db(),n,preferences(db(),uid()))} for n in rows],unread=unread,preferences=preferences(db(),uid()))

    @app.post('/api/hub/notifications/read')
    @auth()
    def hub_read_notifications():
        d=data();through=max(0,int(d.get('through',0)));ids=d.get('ids',[])
        if not isinstance(ids,list) or len(ids)>100 or any(not isinstance(x,int) for x in ids):raise error('Notificações inválidas.')
        if through:db().execute('UPDATE hub_notifications SET read_at=? WHERE user_id=? AND id<=? AND read_at IS NULL',(time.time(),uid(),through))
        elif ids:db().execute('UPDATE hub_notifications SET read_at=? WHERE user_id=? AND id IN ('+','.join('?' for _ in ids)+')',(time.time(),uid(),*ids))
        db().commit();return jsonify(ok=True)

    @app.get('/api/hub/inbox')
    @auth()
    def hub_inbox():
        rs=db().execute("""SELECT u.id,u.name,u.username,u.verified,COALESCE(p.avatar,'') avatar,COALESCE(o.seen_at,0) seen_at,(o.typing_to=? AND o.typing_at>?) typing,
          (SELECT body FROM community_dm d WHERE (d.sender=u.id AND d.recipient=?) OR (d.sender=? AND d.recipient=u.id) ORDER BY id DESC LIMIT 1) last_message,
          (SELECT MAX(created_at) FROM community_dm d WHERE (d.sender=u.id AND d.recipient=?) OR (d.sender=? AND d.recipient=u.id)) last_at,
          (SELECT COUNT(*) FROM community_dm d WHERE d.sender=u.id AND d.recipient=? AND d.id>COALESCE((SELECT message_id FROM community_dm_reads WHERE user_id=? AND other_id=u.id),0)) unread
          FROM jump_friends f JOIN users u ON u.id=CASE WHEN f.sender=? THEN f.recipient ELSE f.sender END LEFT JOIN community_profiles p ON p.user_id=u.id LEFT JOIN community_online o ON o.user_id=u.id WHERE f.status='accepted' AND (f.sender=? OR f.recipient=?) AND u.status='active' ORDER BY last_at DESC,u.name""",(uid(),time.time()-5,uid(),uid(),uid(),uid(),uid(),uid(),uid(),uid(),uid())).fetchall()
        friends=[]
        for r in rs:
            v=dict(r);p=preferences(db(),v['id']);v['online']=v.pop('seen_at')>time.time()-60 and p['presence']!='invisible';v['presence']=p['presence'] if v['online'] else 'offline';v['typing']=bool(v['typing'] and v['online']);v['status_text']=p['status_text'];v['streak']=streak(db(),uid(),v['id']);friends.append(v)
        import social_spaces
        return jsonify(friends=friends,groups=social_spaces.groups(db(),uid()))

    @app.route('/api/hub/dm/<other>',methods=['GET','POST'])
    @auth()
    def hub_dm(other):
        friend(other)
        if request.method=='POST':
            d=data();body=str(d.get('body','')).strip();aid=d.get('audio');share=d.get('share');client=d.get('client_id')
            if len(body)>1500 or (not body and not aid and not share):raise error('Escreva uma mensagem, grave um áudio ou compartilhe algo.')
            if aid and (not isinstance(aid,str) or not re.fullmatch('[a-f0-9]{32}',aid)):raise error('Áudio inválido.')
            if client and (not isinstance(client,str) or not re.fullmatch('[a-zA-Z0-9_-]{8,80}',client)):raise error('Identificador de mensagem inválido.')
            db().execute('BEGIN IMMEDIATE');friend(other)
            key=uid()+':'+client if client else None
            old=db().execute('SELECT d.recipient FROM hub_dm_meta m JOIN community_dm d ON d.id=m.message_id WHERE m.client_id=?',(key,)).fetchone() if key else None
            if old and old['recipient']!=other:raise error('Identificador já utilizado.',409)
            if not old:
                limited('community_dm','sender',30,60)
                if aid and not db().execute('SELECT 1 FROM hub_dm_media WHERE id=? AND user_id=?',(str(aid),uid())).fetchone():raise error('Áudio indisponível.',404)
                kind=target=None
                if share:
                    if not isinstance(share,dict):raise error('Compartilhamento inválido.')
                    kind,target=share.get('kind'),str(share.get('id',''))
                    if not share_preview(db(),kind,target):raise error('Conteúdo indisponível.',404)
                    if kind in ('post','reel') and not reel_studio.visible(db(),target,other):raise error('Este Reel não está disponível para esse amigo.',403)
                    if kind=='story':
                        import story_studio
                        if not story_studio.visible(db(),target,other):raise error('Este story não está disponível para esse amigo.',403)
                body=body or ('🎙️ Mensagem de áudio' if aid else 'Compartilhou '+share_preview(db(),kind,target)['title'])
                mid=db().execute('INSERT INTO community_dm(sender,recipient,body,created_at) VALUES(?,?,?,?)',(uid(),other,body,time.time())).lastrowid
                db().execute('INSERT INTO hub_dm_meta VALUES(?,?,?,?,?)',(mid,aid,kind,target,key))
            db().commit()
        before=max(0,int(request.args.get('before',0)))
        return jsonify(messages=messages(db(),uid(),other,before),streak=streak(db(),uid(),other))

    @app.post('/api/hub/audio')
    @auth()
    def hub_audio_upload():
        f=request.files.get('file')
        if not f:raise error('Escolha um áudio.')
        content=f.read(8*1024*1024+1)
        if len(content)<32 or len(content)>8*1024*1024:raise error('Envie um áudio de até 8 MB.',413)
        if content.startswith(b'\x1aE\xdf\xa3') and b'webm' in content[:128] and f.mimetype.startswith('audio/'):mime='audio/webm'
        elif content[4:8]==b'ftyp':mime='audio/mp4'
        elif content.startswith(b'OggS') and (b'OpusHead' in content[:512] or b'vorbis' in content[:512]):mime='audio/ogg'
        elif content.startswith(b'RIFF') and content[8:12]==b'WAVE':mime='audio/wav'
        elif content.startswith(b'ID3'):mime='audio/mpeg'
        else:raise error('Formato de áudio não reconhecido.')
        db().execute('BEGIN IMMEDIATE');limited('hub_dm_media','user_id',30,3600)
        if db().execute('SELECT COALESCE(SUM(bytes),0) FROM hub_dm_media WHERE user_id=?',(uid(),)).fetchone()[0]+len(content)>200*1024*1024:raise error('Seu limite de áudios foi atingido.',413)
        aid=secrets.token_hex(16);path=directory/aid
        try:path.write_bytes(content);db().execute('INSERT INTO hub_dm_media VALUES(?,?,?,?,?)',(aid,uid(),mime,len(content),time.time()));db().commit()
        except Exception:path.unlink(missing_ok=True);raise
        return jsonify(id=aid,url='/api/hub/media/'+aid,mime=mime),201

    @app.get('/api/hub/media/<aid>')
    @auth()
    def hub_audio_read(aid):
        if not re.fullmatch('[a-f0-9]{32}',aid):raise error('Áudio não encontrado.',404)
        r=db().execute('SELECT * FROM hub_dm_media WHERE id=?',(aid,)).fetchone()
        import social_spaces
        if not r or (r['user_id']!=uid() and not social_spaces.group_audio_access(db(),aid,uid()) and not db().execute('SELECT 1 FROM hub_dm_meta m JOIN community_dm d ON d.id=m.message_id WHERE m.attachment_id=? AND (d.sender=? OR d.recipient=?)',(aid,uid(),uid())).fetchone()):raise error('Áudio não encontrado.',404)
        if not (directory/aid).exists():raise error('Áudio indisponível.',404)
        return send_file(directory/aid,mimetype=r['mime'],conditional=True,max_age=0)

    @app.post('/api/hub/activity')
    @auth()
    def hub_activity():
        d=data();source=d.get('source');target=str(d.get('id',''))
        if source not in ('catalog','community') or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',target) or not isinstance(d.get('playing'),bool):raise error('Atividade inválida.')
        if not d.get('playing'):
            db().execute('DELETE FROM hub_activity WHERE user_id=? AND source=? AND target_id=?',(uid(),source,target))
        else:
            if source=='catalog':exists=db().execute('SELECT 1 FROM watch_history h JOIN content c ON c.id=h.content_id WHERE h.user_id=? AND h.content_id=? AND c.published=1',(uid(),target)).fetchone()
            elif source=='community':exists=share_preview(db(),'post',target)
            else:exists=False
            if not exists:raise error('Conteúdo indisponível.',404)
            now=time.time();db().execute('INSERT INTO hub_activity VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET source=excluded.source,target_id=excluded.target_id,updated_at=excluded.updated_at',(uid(),source,target,now))
            db().execute('INSERT INTO hub_watch VALUES(?,?,?,?) ON CONFLICT(user_id,source,target_id) DO UPDATE SET watched_at=excluded.watched_at',(uid(),source,target,now))
        db().commit();return jsonify(ok=True)

    @app.route('/api/hub/calls',methods=['GET','POST'])
    @auth()
    def hub_calls():
        db().execute('BEGIN IMMEDIATE');expire_calls(db())
        if request.method=='POST':
            d=data();other=str(d.get('recipient',''));friend(other);kind=d.get('kind','audio')
            if kind not in ('audio','video'):raise error('Tipo de chamada inválido.')
            if not preferences(db(),other)['calls']:raise error('Esta pessoa desativou chamadas.',403)
            limited('hub_calls','caller',10,3600)
            if db().execute("SELECT 1 FROM hub_calls WHERE status IN ('ringing','accepted') AND (caller IN (?,?) OR callee IN (?,?))",(uid(),other,uid(),other)).fetchone():raise error('Uma das pessoas já está em uma chamada.',409)
            now=time.time();cid=secrets.token_urlsafe(12)
            db().execute('INSERT INTO hub_calls(id,caller,callee,kind,created_at,updated_at,caller_seen) VALUES(?,?,?,?,?,?,?)',(cid,uid(),other,kind,now,now,now))
            value=call_record(cid);db().commit();return jsonify(call=value),201
        ids=db().execute("SELECT id FROM hub_calls WHERE (caller=? OR callee=?) AND status IN ('ringing','accepted') ORDER BY created_at DESC LIMIT 1",(uid(),uid())).fetchall()
        values=[call_record(r['id']) for r in ids];db().commit();return jsonify(calls=values)

    @app.route('/api/hub/calls/<cid>',methods=['GET','PATCH'])
    @auth()
    def hub_change_call(cid):
        db().execute('BEGIN IMMEDIATE');r=call_record(cid)
        if request.method=='PATCH':
            action=data().get('action');now=time.time()
            if action=='accept':
                if uid()!=r['callee'] or r['status']!='ringing':raise error('Esta chamada não pode ser aceita.',409)
                friend(r['caller']);db().execute("UPDATE hub_calls SET status='accepted',answered_at=?,updated_at=?,callee_seen=?,caller_seen=? WHERE id=?",(now,now,now,now,cid))
                db().execute("UPDATE hub_notifications SET read_at=? WHERE user_id=? AND dedupe=?",(now,uid(),'call:'+cid))
            elif action=='decline':
                if uid()!=r['callee'] or r['status']!='ringing':raise error('Chamada indisponível.',409)
                db().execute("UPDATE hub_calls SET status='declined',updated_at=? WHERE id=?",(now,cid))
            elif action=='end':
                db().execute("UPDATE hub_calls SET status=CASE WHEN status='ringing' THEN 'cancelled' ELSE 'ended' END,updated_at=? WHERE id=? AND status IN ('ringing','accepted')",(now,cid))
            else:raise error('Ação inválida.')
            r=call_record(cid)
        if r['status'] not in ('ringing','accepted'):
            db().execute("UPDATE hub_notifications SET read_at=? WHERE dedupe=? AND read_at IS NULL",(time.time(),'call:'+cid))
        if r['status'] in ('ringing','accepted'):
            field='caller_seen' if uid()==r['caller'] else 'callee_seen';db().execute(f'UPDATE hub_calls SET {field}=? WHERE id=?',(time.time(),cid))
        cursor=max(0,int(request.args.get('cursor',0)))
        signals=[{**dict(s),'payload':json.loads(s['payload'])} for s in db().execute('SELECT id,sender,payload FROM hub_call_signals WHERE call_id=? AND sender!=? AND id>? ORDER BY id LIMIT 200',(cid,uid(),cursor))]
        db().commit();return jsonify(call=r,signals=signals)

    @app.post('/api/hub/calls/<cid>/signals')
    @auth()
    def hub_signal_call(cid):
        db().execute('BEGIN IMMEDIATE');r=call_record(cid);friend(r['callee'] if r['caller']==uid() else r['caller'])
        if r['status']!='accepted':raise error('A chamada não está ativa.',409)
        v=data().get('payload')
        if not isinstance(v,dict) or v.get('type') not in ('offer','answer','candidate') or len(json.dumps(v))>25000:raise error('Sinal inválido.')
        if v['type']=='offer' and r['caller']!=uid():raise error('Somente quem ligou pode iniciar a conexão.',403)
        if v['type']=='answer' and r['callee']!=uid():raise error('Resposta inválida.',403)
        limited('hub_call_signals','sender',600,60)
        db().execute('INSERT INTO hub_call_signals(call_id,sender,payload,created_at) VALUES(?,?,?,?)',(cid,uid(),json.dumps(v),time.time()));db().commit();return jsonify(ok=True)

    @app.get('/api/hub/push/config')
    @auth()
    def hub_push_config():
        from flix_push import public_key
        return jsonify(public_key=public_key(app.config['DATA_DIR']),enabled=True)

    @app.route('/api/hub/push/subscriptions',methods=['POST','DELETE'])
    @auth()
    def hub_subscriptions():
        d=data();endpoint=str(d.get('endpoint',''))
        if request.method=='DELETE':db().execute('DELETE FROM hub_push WHERE endpoint=? AND user_id=?',(endpoint,uid()));db().commit();return jsonify(ok=True)
        from urllib.parse import urlsplit
        try:
            p=urlsplit(endpoint);port=p.port
        except ValueError:raise error('Serviço de notificações inválido.')
        allowed=('fcm.googleapis.com','updates.push.services.mozilla.com','push.services.mozilla.com','web.push.apple.com','notify.windows.com','wns.windows.com')
        if p.scheme!='https' or not p.hostname or not any(p.hostname==x or p.hostname.endswith('.'+x) for x in allowed) or p.username or p.password or port not in (None,443) or len(endpoint)>3000:raise error('Serviço de notificações inválido.')
        keys=d.get('keys',{})
        try:
            pub=base64.urlsafe_b64decode(keys['p256dh']+'='*((-len(keys['p256dh']))%4));secret=base64.urlsafe_b64decode(keys['auth']+'='*((-len(keys['auth']))%4))
            if len(secret)!=16 or len(pub)!=65:raise ValueError()
            ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),pub)
        except (KeyError,ValueError,TypeError):raise error('Chave de notificações inválida.')
        db().execute('BEGIN IMMEDIATE')
        if db().execute('SELECT COUNT(*) FROM hub_push WHERE user_id=? AND endpoint!=?',(uid(),endpoint)).fetchone()[0]>=10:raise error('Limite de dispositivos atingido.',409)
        # Delete old deliveries if a shared browser changes account.
        old=db().execute('SELECT id,user_id FROM hub_push WHERE endpoint=?',(endpoint,)).fetchone()
        if old and old['user_id']!=uid():db().execute('DELETE FROM hub_push WHERE id=?',(old['id'],))
        db().execute('INSERT INTO hub_push VALUES(?,?,?,?,?,?) ON CONFLICT(endpoint) DO UPDATE SET p256dh=excluded.p256dh,auth=excluded.auth',(secrets.token_hex(16),uid(),endpoint,keys['p256dh'],keys['auth'],time.time()));db().commit();return jsonify(ok=True)

    @app.post('/api/hub/push/test')
    @auth()
    def hub_test_push():
        if not db().execute('SELECT 1 FROM hub_push WHERE user_id=?',(uid(),)).fetchone():raise error('Ative as notificações neste dispositivo primeiro.')
        if db().execute("SELECT COUNT(*) FROM hub_notifications WHERE user_id=? AND dedupe LIKE 'push-test:%' AND created_at>?",(uid(),time.time()-60)).fetchone()[0]>=3:raise error('Aguarde antes de testar novamente.',429)
        db().execute("INSERT INTO hub_notifications(user_id,category,title,body,href,created_at,dedupe) VALUES(?,'account','Flix está com você','As notificações deste dispositivo estão prontas.','/comunidade',?,?)",(uid(),time.time(),'push-test:'+secrets.token_hex(8)));db().commit();return jsonify(ok=True)
