"""Single-media stories, audience boundaries and interactive stickers."""
import json
import re
import time
from flask import g, jsonify, request


def migrate(db):
    columns={r[1] for r in db.execute('PRAGMA table_info(community_stories)')}
    if 'audience' not in columns:db.execute("ALTER TABLE community_stories ADD COLUMN audience TEXT NOT NULL DEFAULT 'public'")
    db.executescript('''
    CREATE TABLE IF NOT EXISTS story_close_friends(owner_id TEXT REFERENCES users(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,PRIMARY KEY(owner_id,user_id));
    CREATE TABLE IF NOT EXISTS story_recipients(story_id TEXT REFERENCES community_stories(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,PRIMARY KEY(story_id,user_id));
    CREATE TABLE IF NOT EXISTS story_answers(story_id TEXT REFERENCES community_stories(id) ON DELETE CASCADE,layer_id TEXT NOT NULL,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,value TEXT NOT NULL,created_at REAL NOT NULL,PRIMARY KEY(story_id,layer_id,user_id));
    ''')


def visibility(alias='s'):
    return f"({alias}.user_id=? OR {alias}.audience='public' OR ({alias}.audience='close' AND EXISTS(SELECT 1 FROM story_close_friends cf WHERE cf.owner_id={alias}.user_id AND cf.user_id=?)) OR ({alias}.audience='selected' AND EXISTS(SELECT 1 FROM story_recipients sr WHERE sr.story_id={alias}.id AND sr.user_id=?)))"


def visible(db,story,user):
    return bool(db.execute('SELECT 1 FROM community_stories s WHERE s.id=? AND '+visibility(),(story,user,user,user)).fetchone())


def friends(db,user):
    return [dict(r) for r in db.execute("""SELECT u.id,u.name,u.username,u.verified,COALESCE(p.avatar,'') avatar,EXISTS(SELECT 1 FROM story_close_friends cf WHERE cf.owner_id=? AND cf.user_id=u.id) close FROM users u JOIN jump_friends f ON (f.sender=? AND f.recipient=u.id) OR (f.recipient=? AND f.sender=u.id) LEFT JOIN community_profiles p ON p.user_id=u.id WHERE f.status='accepted' AND u.status='active' ORDER BY u.name""",(user,user,user))]


def recipients(db,value,user,error):
    if not isinstance(value,list) or len(value)>100 or any(not isinstance(v,str) for v in value):raise error('Selecione até 100 amigos.')
    valid={u['id'] for u in friends(db,user)}
    if any(v not in valid for v in value):raise error('Selecione pessoas da sua lista de amigos.',403)
    return list(dict.fromkeys(value))


def validate(db,d,comp,error,external,user):
    import community_experience
    if comp is None:
        url=d.get('media_url')
        if not url:raise error('Escolha uma foto ou um vídeo para o story.')
        # New videos always go through the editor, where duration and trim are explicit.
        import community_social
        item=community_social.local_asset(url,db,error,owner=user)
        if not item or item[1]!='image':raise error('Abra o editor para escolher e recortar o vídeo de até 30 segundos.')
        comp=community_experience.composition(db,{'items':[{'url':url,'type':'image','duration':5}]},error,external,user)
    if len(comp['items'])!=1 or comp['layout']!='sequence':raise error('Cada story aceita somente uma foto ou um vídeo.')
    if d.get('media_url') and d['media_url']!=comp['items'][0]['url']:raise error('Use somente uma mídia por story.')
    if comp['duration']>30:raise error('O story pode ter no máximo 30 segundos. Escolha um trecho menor.')
    comp.update(version=2,format='story');comp['items'][0]['fit']='cover';comp['items'][0]['transition']='none'
    audience=d.get('audience','public')
    if audience not in ('public','close','selected'):raise error('Público do story inválido.')
    people=recipients(db,d.get('recipients',[]),user,error) if audience=='selected' else []
    if audience=='selected' and not people:raise error('Selecione pelo menos um amigo.')
    if audience=='close' and not db.execute('SELECT 1 FROM story_close_friends WHERE owner_id=?',(user,)).fetchone():raise error('Escolha seus amigos próximos antes de publicar.')
    return comp,audience,people


def save_audience(db,sid,audience,people,user):
    db.execute('UPDATE community_stories SET audience=? WHERE id=?',(audience,sid))
    db.executemany('INSERT INTO story_recipients VALUES(?,?)',[(sid,p) for p in people])
    # These are actual shares initiated by the author in "Enviar para".
    for person in people:
        mid=db.execute('INSERT INTO community_dm(sender,recipient,body,created_at) VALUES(?,?,?,?)',(user,person,'Compartilhou um story com você',time.time())).lastrowid
        db.execute('INSERT INTO hub_dm_meta(message_id,share_kind,share_id,client_id) VALUES(?,?,?,?)',(mid,'story',sid,'story:'+sid+':'+person))


def answers(db,sid,layer,user,owner):
    rows=db.execute('SELECT value,COUNT(*) count FROM story_answers WHERE story_id=? AND layer_id=? GROUP BY value',(sid,layer['id'])).fetchall()
    mine=db.execute('SELECT value FROM story_answers WHERE story_id=? AND layer_id=? AND user_id=?',(sid,layer['id'],user)).fetchone()
    value={'mine':json.loads(mine[0]) if mine else None}
    if layer['type']=='poll':value['counts']=[sum(r['count'] for r in rows if json.loads(r['value'])==i) for i in range(len(layer['options']))]
    elif owner:value['answers']=[dict(r) for r in db.execute('SELECT a.user_id,u.name,u.username,a.value,a.created_at FROM story_answers a JOIN users u ON u.id=a.user_id WHERE a.story_id=? AND a.layer_id=? ORDER BY a.created_at DESC LIMIT 100',(sid,layer['id']))]
    return value


def register(app,db,auth,data,error,story):
    @app.route('/api/community/story-audience',methods=['GET','PUT'])
    @auth()
    def audience():
        user=g.user['id']
        if request.method=='PUT':
            ids=recipients(db(),data().get('users'),user,error);db().execute('BEGIN IMMEDIATE');db().execute('DELETE FROM story_close_friends WHERE owner_id=?',(user,));db().executemany('INSERT INTO story_close_friends VALUES(?,?)',[(user,u) for u in ids]);db().commit()
        return jsonify(friends=friends(db(),user))

    @app.route('/api/community/stories/<sid>/stickers/<layer_id>',methods=['GET','POST'])
    @auth()
    def interact(sid,layer_id):
        s=story(sid);row=db().execute("SELECT payload FROM community_compositions WHERE target_type='story' AND target_id=?",(sid,)).fetchone()
        layer=next((l for l in json.loads(row[0])['layers'] if l.get('id')==layer_id and l['type'] in ('poll','question')),None) if row else None
        if not layer:raise error('Figurinha indisponível.',404)
        if request.method=='POST':
            value=data().get('value')
            if layer['type']=='poll':
                if type(value) is not int or not 0<=value<len(layer['options']):raise error('Escolha uma opção válida.')
            elif not isinstance(value,str) or not 1<=len(value.strip())<=240:raise error('Escreva uma resposta de até 240 caracteres.')
            else:value=value.strip()
            db().execute('INSERT INTO story_answers VALUES(?,?,?,?,?) ON CONFLICT(story_id,layer_id,user_id) DO UPDATE SET value=excluded.value,created_at=excluded.created_at',(sid,layer_id,g.user['id'],json.dumps(value),time.time()));db().commit()
        return jsonify(answers(db(),sid,layer,g.user['id'],s['user_id']==g.user['id']))
