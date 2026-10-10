"""Verification, social spaces and groups using the existing users, posts and DM store."""
import re,secrets,time
from flask import g,request,jsonify
import community_social
import social_hub

def migrate(db):
    for table,cols in {'users':{'verified':'INTEGER NOT NULL DEFAULT 0'},'community_posts':{'space_id':'TEXT REFERENCES social_spaces(id)'},'community_dm':{'group_id':'TEXT REFERENCES hub_groups(id)'}}.items():
        existing={r[1] for r in db.execute('PRAGMA table_info('+table+')')}
        for name,definition in cols.items():
            if name not in existing:db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS verification_requests(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,status TEXT NOT NULL,reason TEXT NOT NULL,links TEXT NOT NULL,created_at REAL NOT NULL,reviewed_at REAL,reviewed_by TEXT REFERENCES users(id),note TEXT NOT NULL DEFAULT '');
    CREATE TABLE IF NOT EXISTS social_spaces(id TEXT PRIMARY KEY,kind TEXT NOT NULL,owner_id TEXT REFERENCES users(id),name TEXT NOT NULL,username TEXT UNIQUE NOT NULL,description TEXT NOT NULL DEFAULT '',avatar TEXT NOT NULL DEFAULT '',cover TEXT NOT NULL DEFAULT '',privacy TEXT NOT NULL DEFAULT 'public',status TEXT NOT NULL DEFAULT 'active',created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS social_space_members(space_id TEXT REFERENCES social_spaces(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,role TEXT NOT NULL,created_at REAL NOT NULL,PRIMARY KEY(space_id,user_id));
    CREATE TABLE IF NOT EXISTS hub_groups(id TEXT PRIMARY KEY,creator_id TEXT REFERENCES users(id),name TEXT NOT NULL,avatar TEXT NOT NULL DEFAULT '',created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS hub_group_members(group_id TEXT REFERENCES hub_groups(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,role TEXT NOT NULL,joined_at REAL NOT NULL,PRIMARY KEY(group_id,user_id));
    CREATE INDEX IF NOT EXISTS hub_group_messages ON community_dm(group_id,id);
    CREATE INDEX IF NOT EXISTS social_space_posts ON community_posts(space_id,created_at);
    ''')
    db.execute('DROP TRIGGER IF EXISTS hub_call_missed')
    db.executescript("""CREATE TRIGGER hub_call_missed AFTER UPDATE ON hub_calls WHEN OLD.status='ringing' AND NEW.status='missed' BEGIN
      INSERT OR IGNORE INTO hub_notifications(user_id,actor_id,category,title,body,href,created_at,dedupe) SELECT NEW.callee,NEW.caller,'calls','Chamada perdida','Uma chamada não foi atendida.','/comunidade?tab=friends&dm='||NEW.caller,NEW.updated_at,'call-missed:'||NEW.id;
    END;
    CREATE TRIGGER IF NOT EXISTS hub_call_ended AFTER UPDATE ON hub_calls WHEN OLD.status IN ('ringing','accepted') AND NEW.status IN ('ended','declined','cancelled') BEGIN
      UPDATE hub_notifications SET read_at=NEW.updated_at WHERE dedupe='call:'||NEW.id;
      INSERT OR IGNORE INTO hub_notifications(user_id,actor_id,category,title,body,href,created_at,dedupe) SELECT NEW.callee,NEW.caller,'calls','Chamada encerrada','Confira sua conversa.','/comunidade?tab=friends&dm='||NEW.caller,NEW.updated_at,'call-ended:'||NEW.id;
    END;""")
    # Group messages share the DM table but must never enter private-message triggers.
    for name in ('hub_dm','hub_streak'):
        row=db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",(name,)).fetchone()
        if row and 'WHEN NEW.recipient IS NOT NULL' not in row[0]:
            sql=row[0].replace(' WHEN 1 BEGIN',' WHEN NEW.recipient IS NOT NULL BEGIN',1) if ' WHEN 1 BEGIN' in row[0] else row[0].replace(' BEGIN',' WHEN NEW.recipient IS NOT NULL BEGIN',1);db.execute('DROP TRIGGER '+name);db.execute(sql)
    db.executescript('''CREATE TRIGGER IF NOT EXISTS hub_group_message AFTER INSERT ON community_dm WHEN NEW.group_id IS NOT NULL BEGIN
      INSERT OR IGNORE INTO hub_notifications(user_id,actor_id,category,title,body,href,created_at,dedupe)
      SELECT m.user_id,NEW.sender,'messages',gr.name,(SELECT name FROM users WHERE id=NEW.sender)||': '||substr(NEW.body,1,180),'/comunidade?tab=friends&group='||NEW.group_id,NEW.created_at,'group-message:'||NEW.id FROM hub_group_members m JOIN hub_groups gr ON gr.id=m.group_id WHERE m.group_id=NEW.group_id AND m.user_id!=NEW.sender;
    END;''')
    # Private publications must never announce their titles to non-members.
    visibility="(NEW.space_id IS NULL OR EXISTS(SELECT 1 FROM social_spaces s WHERE s.id=NEW.space_id AND s.status='active' AND (s.privacy='public' OR EXISTS(SELECT 1 FROM social_space_members sm WHERE sm.space_id=s.id AND sm.user_id=f.follower))))"
    db.execute('DROP TRIGGER IF EXISTS hub_publication')
    db.executescript("""CREATE TRIGGER hub_publication AFTER INSERT ON community_posts WHEN NEW.status='published' BEGIN
      INSERT OR IGNORE INTO hub_notifications(user_id,actor_id,category,title,body,href,created_at,dedupe)
      SELECT f.follower,NEW.user_id,'social','Nova publicação',(SELECT name FROM users WHERE id=NEW.user_id)||' publicou '||NEW.title,'/comunidade/post/'||NEW.id,NEW.created_at,'post:'||NEW.id FROM community_follows f WHERE f.following=NEW.user_id AND """+visibility+""";
      INSERT OR IGNORE INTO hub_notifications(user_id,actor_id,category,title,body,href,created_at,dedupe)
      SELECT m.user_id,NEW.user_id,'social',s.name,NEW.title,'/comunidade/post/'||NEW.id,NEW.created_at,'post:'||NEW.id FROM social_space_members m JOIN social_spaces s ON s.id=m.space_id WHERE s.id=NEW.space_id AND s.kind='page' AND m.user_id!=NEW.user_id;
    END;""")
    for name in ('hub_mention_insert','hub_mention_update'):
        row=db.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",(name,)).fetchone()
        if row and 'social_space_members' not in row[0]:
            sql=row[0].replace('WHERE j.value!=p.user_id',"WHERE j.value!=p.user_id AND (p.space_id IS NULL OR EXISTS(SELECT 1 FROM social_spaces ss WHERE ss.id=p.space_id AND (ss.privacy='public' OR EXISTS(SELECT 1 FROM social_space_members sm WHERE sm.space_id=ss.id AND sm.user_id=j.value))))")
            db.execute('DROP TRIGGER '+name);db.execute(sql)

def notify(db,user,actor,title,body,href,dedupe=None,category='social'):
    db.execute('INSERT OR IGNORE INTO hub_notifications(user_id,actor_id,category,title,body,href,created_at,dedupe) VALUES(?,?,?,?,?,?,?,?)',(user,actor,category,title,body,href,time.time(),dedupe))

def space_role(db,sid,uid):
    r=db.execute("SELECT role FROM social_space_members WHERE space_id=? AND user_id=?",(sid,uid)).fetchone();return r[0] if r else None

def post_permission(db,sid,uid,error):
    s=db.execute("SELECT * FROM social_spaces WHERE id=? AND status='active'",(sid,)).fetchone();role=space_role(db,sid,uid)
    if not s or not role or (s['kind']=='page' and role not in ('owner','admin')):raise error('Você não tem permissão para publicar neste espaço.',403)
    return s

def enrich(db,p):
    if p.get('space_id'):
        s=db.execute('SELECT id,kind,name,username,avatar FROM social_spaces WHERE id=?',(p['space_id'],)).fetchone();p['space']=dict(s) if s else None

def groups(db,uid):
    return [dict(r) for r in db.execute('''SELECT * FROM (SELECT gr.*,m.role,(SELECT COUNT(*) FROM hub_group_members WHERE group_id=gr.id) members,
    (SELECT body FROM community_dm WHERE group_id=gr.id AND created_at>=m.joined_at ORDER BY id DESC LIMIT 1) last_message,
    (SELECT MAX(created_at) FROM community_dm WHERE group_id=gr.id AND created_at>=m.joined_at) last_at,
    (SELECT COUNT(*) FROM community_dm WHERE group_id=gr.id AND created_at>=m.joined_at AND sender!=? AND id>COALESCE((SELECT message_id FROM community_dm_reads WHERE user_id=? AND other_id='group:'||gr.id),0)) unread
    FROM hub_groups gr JOIN hub_group_members m ON m.group_id=gr.id AND m.user_id=?) group_inbox ORDER BY COALESCE(last_at,created_at) DESC''',(uid,uid,uid))]

def group_audio_access(db,aid,uid):
    return db.execute('''SELECT 1 FROM hub_dm_meta x JOIN community_dm d ON d.id=x.message_id JOIN hub_group_members m ON m.group_id=d.group_id AND m.user_id=? WHERE x.attachment_id=? AND d.created_at>=m.joined_at''',(uid,aid)).fetchone()

def register(app,db,auth,data,error):
    def uid():return g.user['id']
    def text(d,key,lo=0,hi=160):
        v=d.get(key,'')
        if not isinstance(v,str) or not lo<=len(v.strip())<=hi:raise error(f'Confira o campo {key} ({lo}–{hi} caracteres).')
        return v.strip()
    def picture(v):
        if not v:return ''
        asset=community_social.local_asset(v,db(),error,owner=uid())
        if not asset or asset[1]!='image':raise error('Envie uma imagem do dispositivo.')
        community_social.retain_assets(db(),v);return v
    def friend(other):
        if not db().execute("SELECT 1 FROM jump_friends WHERE status='accepted' AND ((sender=? AND recipient=?) OR (sender=? AND recipient=?))",(uid(),other,other,uid())).fetchone():raise error('Adicione esta pessoa aos amigos antes de convidar.',403)
    def group(gid,admin=False):
        r=db().execute('SELECT gr.*,m.role,m.joined_at FROM hub_groups gr JOIN hub_group_members m ON m.group_id=gr.id WHERE gr.id=? AND m.user_id=?',(gid,uid())).fetchone()
        if not r:raise error('Grupo indisponível.',404)
        if admin and r['role']!='admin':raise error('Apenas administradores do grupo.',403)
        return r
    def space(sid,manage=False):
        r=db().execute("SELECT * FROM social_spaces WHERE (id=? OR username=?) AND status='active'",(sid,sid)).fetchone()
        if not r:raise error('Espaço indisponível.',404)
        role=space_role(db(),r['id'],uid())
        if (manage and role not in ('owner','admin')) or (r['privacy']=='private' and not role):raise error('Acesso reservado aos membros.',403)
        return dict(r),role

    @app.route('/api/community/verification',methods=['GET','POST'])
    @auth()
    def verification():
        row=db().execute('SELECT * FROM verification_requests WHERE user_id=?',(uid(),)).fetchone()
        if request.method=='POST':
            d=data()
            if g.user['verified'] or (row and row['status']=='pending'):raise error('Sua conta já está verificada ou aguarda análise.',409)
            if row and row['reviewed_at'] and row['reviewed_at']>time.time()-7*86400:raise error('Você pode enviar uma nova solicitação após 7 dias.',429)
            reason=text(d,'reason',20,2000);links=text(d,'links',0,1500)
            db().execute("INSERT INTO verification_requests(user_id,status,reason,links,created_at) VALUES(?,'pending',?,?,?) ON CONFLICT(user_id) DO UPDATE SET status='pending',reason=excluded.reason,links=excluded.links,created_at=excluded.created_at,reviewed_at=NULL,reviewed_by=NULL,note=''",(uid(),reason,links,time.time()))
            for u in db().execute("SELECT id FROM users WHERE role='admin' AND status='active'"):notify(db(),u[0],uid(),'Solicitação de verificação',g.user['name']+' pediu o selo azul.','/admin?tab=verifications',category='account')
            db().commit();row=db().execute('SELECT * FROM verification_requests WHERE user_id=?',(uid(),)).fetchone()
        return jsonify(verified=bool(g.user['verified']),request=dict(row) if row else None)

    @app.get('/api/admin/verifications')
    @auth(admin=True)
    def admin_verifications():
        return jsonify(requests=[dict(r) for r in db().execute("SELECT v.*,u.name,u.username,u.verified FROM verification_requests v JOIN users u ON u.id=v.user_id ORDER BY v.status='pending' DESC,v.created_at DESC LIMIT 200")],verified=[dict(r) for r in db().execute('SELECT id,name,username FROM users WHERE verified=1 ORDER BY name LIMIT 200')])

    @app.patch('/api/admin/verifications/<user>')
    @auth(admin=True)
    def review(user):
        d=data();action=d.get('action');note=text(d,'note',0,500)
        if action not in ('approve','reject','remove'):raise error('Decisão inválida.')
        db().execute('BEGIN IMMEDIATE');row=db().execute('SELECT * FROM verification_requests WHERE user_id=?',(user,)).fetchone()
        if action!='remove' and (not row or row['status']!='pending'):raise error('Solicitação já analisada ou inexistente.',409)
        if not db().execute('SELECT 1 FROM users WHERE id=?',(user,)).fetchone():raise error('Usuário indisponível.',404)
        status={'approve':'approved','reject':'rejected','remove':'revoked'}[action]
        db().execute('UPDATE users SET verified=? WHERE id=?',(action=='approve',user));db().execute('UPDATE verification_requests SET status=?,note=?,reviewed_at=?,reviewed_by=? WHERE user_id=?',(status,note,time.time(),uid(),user))
        notify(db(),user,uid(),'Verificação '+{'approve':'aprovada','reject':'recusada','remove':'removida'}[action],note or ('Seu selo azul já está disponível.' if action=='approve' else 'Confira sua solicitação nas configurações.'),'/conta',category='account')
        db().execute('INSERT INTO community_audit(admin_id,action,target,created_at) VALUES(?,?,?,?)',(uid(),'verification:'+action,user,time.time()));db().commit();return jsonify(ok=True)

    @app.get('/api/admin/spaces')
    @auth(admin=True)
    def admin_spaces():
        return jsonify(spaces=[dict(r) for r in db().execute("SELECT s.*,u.username owner,(SELECT COUNT(*) FROM social_space_members m WHERE m.space_id=s.id) members FROM social_spaces s JOIN users u ON u.id=s.owner_id ORDER BY s.created_at DESC LIMIT 200")])

    @app.patch('/api/admin/spaces/<sid>')
    @auth(admin=True)
    def admin_space_review(sid):
        status=data().get('status')
        if status not in ('active','hidden'):raise error('Estado inválido.')
        if not db().execute('UPDATE social_spaces SET status=? WHERE id=?',(status,sid)).rowcount:raise error('Espaço não encontrado.',404)
        db().execute('DELETE FROM community_feed_order');db().execute('INSERT INTO community_audit(admin_id,action,target,created_at) VALUES(?,?,?,?)',(uid(),'space:'+status,sid,time.time()));db().commit();return jsonify(ok=True)

    @app.route('/api/community/spaces',methods=['GET','POST'])
    @auth()
    def spaces():
        if request.method=='GET':
            kind=request.args.get('kind','community');q='%'+request.args.get('q','')[:80]+'%'
            rows=db().execute("SELECT s.*,(SELECT COUNT(*) FROM social_space_members WHERE space_id=s.id) members,(SELECT role FROM social_space_members WHERE space_id=s.id AND user_id=?) my_role FROM social_spaces s WHERE s.kind=? AND s.status='active' AND (name LIKE ? OR username LIKE ?) ORDER BY members DESC,created_at DESC LIMIT 100",(uid(),kind,q,q))
            return jsonify(spaces=[dict(r) for r in rows])
        d=data();kind=d.get('kind','community');name=text(d,'name',2,80);username=text(d,'username',3,30).lower().lstrip('@')
        if kind not in ('community','page') or not re.fullmatch('[a-z0-9_]{3,30}',username):raise error('Use um @usuário com letras, números e sublinhado.')
        db().execute('BEGIN IMMEDIATE')
        if db().execute('SELECT 1 FROM social_spaces WHERE username=?',(username,)).fetchone():raise error('Este endereço já está em uso.',409)
        if db().execute('SELECT COUNT(*) FROM social_spaces WHERE owner_id=?',(uid(),)).fetchone()[0]>=20:raise error('Limite de 20 espaços por conta.',429)
        sid=secrets.token_urlsafe(9);now=time.time();privacy=d.get('privacy','public')
        if privacy not in ('public','private') or (kind=='page' and privacy!='public'):raise error('Privacidade inválida.')
        db().execute('INSERT INTO social_spaces(id,kind,owner_id,name,username,description,avatar,cover,privacy,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,kind,uid(),name,username,text(d,'description',0,1500),picture(d.get('avatar','')),picture(d.get('cover','')),privacy,now))
        db().execute("INSERT INTO social_space_members VALUES(?,?,'owner',?)",(sid,uid(),now));db().commit();return jsonify(id=sid,username=username),201

    @app.route('/api/community/spaces/<sid>',methods=['GET','PATCH'])
    @auth()
    def space_detail(sid):
        s,role=space(sid,request.method=='PATCH');sid=s['id']
        if request.method=='PATCH':
            d=data();values={k:text(d,k,2 if k=='name' else 0,80 if k=='name' else 1500) for k in ('name','description') if k in d}
            for k in ('avatar','cover'):
                if k in d:values[k]=picture(d[k])
            if values:db().execute('UPDATE social_spaces SET '+','.join(k+'=?' for k in values)+' WHERE id=?',(*values.values(),sid));db().commit()
            s,role=space(sid)
        s['my_role']=role;s['members']=[dict(r) for r in db().execute("SELECT u.id,u.name,u.username,u.verified,COALESCE(p.avatar,'') avatar,m.role FROM social_space_members m JOIN users u ON u.id=m.user_id LEFT JOIN community_profiles p ON p.user_id=u.id WHERE m.space_id=? ORDER BY m.created_at LIMIT 200",(sid,))]
        return jsonify(space=s)

    @app.route('/api/community/spaces/<sid>/members/<other>',methods=['PUT','DELETE'])
    @auth()
    def space_member(sid,other):
        # Public spaces allow self-entry; private entry requires an administrator invitation.
        s=db().execute("SELECT * FROM social_spaces WHERE id=? AND status='active'",(sid,)).fetchone()
        if not s:raise error('Espaço indisponível.',404)
        role=space_role(db(),sid,uid());target=space_role(db(),sid,other)
        if other==s['owner_id']:raise error('O criador permanece responsável pelo espaço.',403)
        if other!=uid() and role not in ('owner','admin'):raise error('Apenas administradores podem gerenciar membros.',403)
        if target=='admin' and role!='owner' and other!=uid():raise error('Apenas o criador pode alterar administradores.',403)
        if request.method=='DELETE':db().execute('DELETE FROM social_space_members WHERE space_id=? AND user_id=?',(sid,other))
        else:
            d=data();new=d.get('role','follower' if s['kind']=='page' else 'member')
            if new not in ('follower','member','moderator','admin'):raise error('Cargo inválido.')
            if new in ('admin','moderator') and role!='owner':raise error('Apenas o criador pode conceder este cargo.',403)
            if other==uid() and not role and s['privacy']=='private':raise error('Peça um convite à administração.',403)
            if not db().execute("SELECT 1 FROM users WHERE id=? AND status='active'",(other,)).fetchone():raise error('Usuário indisponível.',404)
            db().execute('INSERT INTO social_space_members VALUES(?,?,?,?) ON CONFLICT(space_id,user_id) DO UPDATE SET role=excluded.role',(sid,other,new,time.time()))
            if other!=uid():notify(db(),other,uid(),'Convite para '+s['name'],'Você agora participa deste espaço.','/comunidade/espaco/'+s['username'])
        db().execute('DELETE FROM community_feed_order WHERE user_id=?',(other,));db().commit();return jsonify(ok=True)

    @app.patch('/api/community/spaces/<sid>/posts/<pid>')
    @auth()
    def moderate_space_post(sid,pid):
        s,role=space(sid)
        if role not in ('owner','admin','moderator'):raise error('Apenas a equipe pode moderar.',403)
        row=db().execute("UPDATE community_posts SET status='hidden' WHERE id=? AND space_id=?",(pid,s['id']))
        if not row.rowcount:raise error('Publicação indisponível.',404)
        db().commit();return jsonify(ok=True)

    @app.route('/api/hub/groups',methods=['GET','POST'])
    @auth()
    def group_list():
        if request.method=='GET':return jsonify(groups=groups(db(),uid()))
        d=data();name=text(d,'name',2,80);members=d.get('members',[])
        if not isinstance(members,list) or len(members)>99 or any(not isinstance(m,str) for m in members):raise error('Escolha até 99 amigos.')
        db().execute('BEGIN IMMEDIATE')
        if db().execute('SELECT COUNT(*) FROM hub_groups WHERE creator_id=?',(uid(),)).fetchone()[0]>=30:raise error('Limite de grupos atingido.',429)
        gid=secrets.token_urlsafe(9);now=time.time();db().execute('INSERT INTO hub_groups VALUES(?,?,?,?,?)',(gid,uid(),name,picture(d.get('avatar','')),now));db().execute("INSERT INTO hub_group_members VALUES(?,?,'admin',?)",(gid,uid(),now))
        for other in set(members)-{uid()}:
            friend(other);db().execute("INSERT INTO hub_group_members VALUES(?,?,'member',?)",(gid,other,now));notify(db(),other,uid(),'Novo grupo: '+name,g.user['name']+' adicionou você.','/comunidade?tab=friends&group='+gid,category='messages')
        db().commit();return jsonify(id=gid),201

    @app.route('/api/hub/groups/<gid>',methods=['GET','PATCH'])
    @auth()
    def group_detail(gid):
        r=group(gid,request.method=='PATCH')
        if request.method=='PATCH':
            d=data();db().execute('UPDATE hub_groups SET name=?,avatar=? WHERE id=?',(text(d,'name',2,80) if 'name' in d else r['name'],picture(d['avatar']) if 'avatar' in d else r['avatar'],gid));db().commit();r=group(gid)
        members=[dict(m) for m in db().execute("SELECT u.id,u.name,u.username,u.verified,COALESCE(p.avatar,'') avatar,m.role,COALESCE(o.seen_at,0)>? online FROM hub_group_members m JOIN users u ON u.id=m.user_id LEFT JOIN community_profiles p ON p.user_id=u.id LEFT JOIN community_online o ON o.user_id=u.id WHERE m.group_id=? ORDER BY m.joined_at",(time.time()-60,gid))]
        for member in members:
            if social_hub.preferences(db(),member['id'])['presence']=='invisible':member['online']=False
        return jsonify(group=dict(r),members=members)

    @app.route('/api/hub/groups/<gid>/members/<other>',methods=['PUT','DELETE'])
    @auth()
    def group_member(gid,other):
        db().execute('BEGIN IMMEDIATE');r=group(gid,other!=uid())
        old=db().execute('SELECT * FROM hub_group_members WHERE group_id=? AND user_id=?',(gid,other)).fetchone()
        if request.method=='DELETE':
            if old and old['role']=='admin' and db().execute("SELECT COUNT(*) FROM hub_group_members WHERE group_id=? AND role='admin'",(gid,)).fetchone()[0]==1:
                successor=db().execute('SELECT user_id FROM hub_group_members WHERE group_id=? AND user_id!=? ORDER BY joined_at LIMIT 1',(gid,other)).fetchone()
                if successor:db().execute("UPDATE hub_group_members SET role='admin' WHERE group_id=? AND user_id=?",(gid,successor[0]))
            db().execute('DELETE FROM hub_group_members WHERE group_id=? AND user_id=?',(gid,other));db().execute("UPDATE hub_notifications SET read_at=? WHERE user_id=? AND href=?",(time.time(),other,'/comunidade?tab=friends&group='+gid))
        else:
            group(gid,True);role=data().get('role','member')
            if role not in ('admin','member'):raise error('Cargo inválido.')
            if old and old['role']=='admin' and role=='member' and db().execute("SELECT COUNT(*) FROM hub_group_members WHERE group_id=? AND role='admin'",(gid,)).fetchone()[0]==1:raise error('Mantenha ao menos um administrador.',409)
            if not old:
                friend(other)
                if db().execute('SELECT COUNT(*) FROM hub_group_members WHERE group_id=?',(gid,)).fetchone()[0]>=100:raise error('O grupo aceita até 100 pessoas.',409)
            db().execute('INSERT INTO hub_group_members VALUES(?,?,?,?) ON CONFLICT(group_id,user_id) DO UPDATE SET role=excluded.role',(gid,other,role,time.time()))
            if not old:notify(db(),other,uid(),'Convite para grupo',r['name'],'/comunidade?tab=friends&group='+gid,category='messages')
        db().commit();return jsonify(ok=True)

    @app.route('/api/hub/groups/<gid>/messages',methods=['GET','POST'])
    @auth()
    def group_messages(gid):
        r=group(gid)
        if request.method=='POST':
            d=data();body=text(d,'body',0,1500);aid=d.get('audio');share=d.get('share');client=d.get('client_id')
            if not body and not aid and not share:raise error('Escreva uma mensagem ou adicione uma mídia.')
            if not isinstance(client,str) or not re.fullmatch('[a-zA-Z0-9_-]{8,80}',client):raise error('Identificador inválido.')
            db().execute('BEGIN IMMEDIATE');r=group(gid);key=uid()+':'+client;old=db().execute('SELECT d.group_id FROM hub_dm_meta m JOIN community_dm d ON d.id=m.message_id WHERE m.client_id=?',(key,)).fetchone()
            if old and old[0]!=gid:raise error('Identificador já utilizado.',409)
            if not old:
                if db().execute('SELECT COUNT(*) FROM community_dm WHERE sender=? AND created_at>?',(uid(),time.time()-60)).fetchone()[0]>=30:raise error('Aguarde antes de enviar mais mensagens.',429)
                if aid and not db().execute('SELECT 1 FROM hub_dm_media WHERE id=? AND user_id=?',(str(aid),uid())).fetchone():raise error('Áudio indisponível.',404)
                kind=target=None
                if share:
                    if not isinstance(share,dict):raise error('Compartilhamento inválido.')
                    kind,target=share.get('kind'),str(share.get('id',''))
                    if not social_hub.share_preview(db(),kind,target):raise error('Conteúdo indisponível.',404)
                mid=db().execute('INSERT INTO community_dm(sender,recipient,body,created_at,group_id) VALUES(?,NULL,?,?,?)',(uid(),body or ('🎙️ Mensagem de áudio' if aid else 'Compartilhou uma descoberta'),time.time(),gid)).lastrowid
                db().execute('INSERT INTO hub_dm_meta VALUES(?,?,?,?,?)',(mid,aid,kind,target,key))
            db().commit()
        before=max(0,int(request.args.get('before',0)));after=max(0,int(request.args.get('after',0)))
        rows=db().execute('''SELECT d.*,u.name,u.username,u.verified,COALESCE(p.avatar,'') avatar,x.attachment_id,x.share_kind,x.share_id FROM community_dm d JOIN users u ON u.id=d.sender LEFT JOIN community_profiles p ON p.user_id=u.id LEFT JOIN hub_dm_meta x ON x.message_id=d.id WHERE d.group_id=? AND d.created_at>=? AND (?=0 OR d.id<?) AND d.id>? ORDER BY d.id DESC LIMIT 60''',(gid,r['joined_at'],before,before,after)).fetchall();out=[]
        for row in reversed(rows):
            v=dict(row)
            if v['attachment_id']:v['audio']={'url':'/api/hub/media/'+v['attachment_id']}
            if v['share_kind']:v['share']=social_hub.share_preview(db(),v['share_kind'],v['share_id']) or {'unavailable':True,'title':'Conteúdo indisponível'}
            out.append(v)
        return jsonify(messages=out,group=dict(r))

    @app.post('/api/hub/groups/<gid>/read')
    @auth()
    def group_read(gid):
        group(gid);mid=db().execute('SELECT COALESCE(MAX(id),0) FROM community_dm WHERE group_id=?',(gid,)).fetchone()[0]
        db().execute('INSERT INTO community_dm_reads VALUES(?,?,?) ON CONFLICT(user_id,other_id) DO UPDATE SET message_id=excluded.message_id',(uid(),'group:'+gid,mid));db().execute("UPDATE hub_notifications SET read_at=? WHERE user_id=? AND href=? AND category='messages'",(time.time(),uid(),'/comunidade?tab=friends&group='+gid));db().commit();return jsonify(ok=True)
