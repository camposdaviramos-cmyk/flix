"""One contextual notification representation for the inbox and Web Push."""
import time
from social_text import normalize

def available(db,n):
    n=dict(n);key=n.get('dedupe') or '';user=n['user_id']
    if key.startswith('group-message:'):
        return bool(db.execute('SELECT 1 FROM community_dm d JOIN hub_group_members m ON m.group_id=d.group_id AND m.user_id=? WHERE d.id=? AND d.created_at>=m.joined_at',(user,key.split(':')[-1])).fetchone())
    href=n.get('href','')
    if href.startswith('/comunidade/post/'):
        pid=href.split('/')[3].split('?')[0];p=db.execute('SELECT p.status,p.user_id,p.space_id,s.privacy,s.status space_status FROM community_posts p LEFT JOIN social_spaces s ON s.id=p.space_id WHERE p.id=?',(pid,)).fetchone()
        if not p or p['status'] not in ('published','private','archived') or (p['status']!='published' and p['user_id']!=user):return False
        if p['space_id'] and (p['space_status']!='active' or (p['privacy']=='private' and not db.execute('SELECT 1 FROM social_space_members WHERE space_id=? AND user_id=?',(p['space_id'],user)).fetchone())):return False
    return True

def build(db,n,prefs=None):
    n=dict(n);prefs=prefs or {};key=n.get('dedupe') or '';actor=db.execute("SELECT u.id,u.name,u.username,COALESCE(p.avatar,'') avatar FROM users u LEFT JOIN community_profiles p ON p.user_id=u.id WHERE u.id=?",(n.get('actor_id'),)).fetchone()
    actor=dict(actor) if actor else {};typ='system';body=normalize(n.get('body',''),stickers=True);title=normalize(n['title'],stickers=True)
    d={'id':n['id'],'title':title,'body':body,'url':n['href'],'type':typ,'tag':'flix-'+str(n['id']),'senderId':actor.get('id'),'senderName':actor.get('name'),'senderAvatar':actor.get('avatar') or '/static/assets/flix-icon-192.png','icon':actor.get('avatar') or '/static/assets/flix-icon-192.png','actions':[]}
    if not available(db,n):
        d.update(title='Conteúdo indisponível',body='Este conteúdo foi removido ou seu acesso mudou.',url='/comunidade',actions=[{'action':'open','title':'Abrir Flix'}]);return d
    if key.startswith(('dm:','group-message:')):
        mid=key.split(':')[-1];m=db.execute('SELECT d.*,x.attachment_id,x.share_kind FROM community_dm d LEFT JOIN hub_dm_meta x ON x.message_id=d.id WHERE d.id=?',(mid,)).fetchone()
        if m:
            preview=normalize(m['body'],stickers=True)[:180] if prefs.get('message_preview',True) else 'Enviou uma mensagem.'
            mtype='audio' if m['attachment_id'] else 'share' if m['share_kind'] else 'sticker' if m['body'].startswith('[sticker:') else 'text'
            if mtype=='audio':preview='🎙️ Mensagem de áudio'
            group=db.execute('SELECT name FROM hub_groups WHERE id=?',(m['group_id'],)).fetchone() if m['group_id'] else None
            d.update(type='group_message' if group else 'message',title=(actor.get('name','Mensagem')+' · '+group['name']) if group else actor.get('name','Mensagem'),body=preview,messagePreview=preview,messageType=mtype,conversationId=('group:'+m['group_id']) if group else actor.get('id'),groupId=m['group_id'],actions=[{'action':'open','title':'Abrir conversa'}])
    elif key.startswith(('call:','call-missed:','call-ended:')):
        cid=key.split(':')[1];c=db.execute('SELECT * FROM hub_calls WHERE id=?',(cid,)).fetchone()
        if c:
            incoming=key.startswith('call:') and c['status']=='ringing' and c['created_at']>time.time()-45
            typ='call_incoming' if incoming else 'call_missed' if c['status']=='missed' else 'call_ended'
            kind='vídeo' if c['kind']=='video' else 'voz';symbol='📹' if c['kind']=='video' else '📞'
            label='recebida' if incoming else {'missed':'perdida','cancelled':'cancelada','declined':'recusada','accepted':'atendida','ended':'encerrada'}.get(c['status'],'encerrada')
            d.update(type=typ,title=actor.get('name','Flix'),body=f'{symbol} Chamada de {kind} {label}',callType=c['kind'],callId=cid,callerId=c['caller'],callerName=actor.get('name'),callerAvatar=actor.get('avatar'),conversationId=actor.get('id'),callState='rejected' if c['status']=='declined' else c['status'],tag='flix-call-'+cid,call=incoming,expires=int(c['created_at']+45) if incoming else None,actions=[{'action':'answer','title':'Atender'},{'action':'decline','title':'Recusar'}] if incoming else [{'action':'open','title':'Abrir conversa'}])
    else:
        mapping={'follow:':'follow','comment:':'comment','comment-mention:':'mention','composition-mention:':'mention','mention:':'mention','like:':'like','reaction:':'like','story-reaction:':'story','post:':'post','music:':'music','music-room:':'music_room','verification:':'verification'}
        for prefix,value in mapping.items():
            if key.startswith(prefix):d['type']=value;break
        if title.startswith('Verificação') or 'verificação' in title.lower():d['type']='verification'
        if key.startswith('post:'):
            post=db.execute('SELECT kind,title,poster FROM community_posts WHERE id=?',(key[5:],)).fetchone()
            if post:
                kind={'reel':'reel','music':'music'}.get(post['kind'],'post');d.update(type=kind,contentType=post['kind'],body=f"{actor.get('name','Alguém')} publicou { {'movie':'um filme','series':'uma série','reel':'um reel','music':'uma música','news':'uma notícia'}.get(post['kind'],'uma publicação')}: {post['title']}")
        if d['type']=='system' and n.get('category')=='rooms':d['type']='room'
        if d['type']=='system' and key.startswith(('friend:','friend-accepted:')):d['type']='friend'
        d['actions']=[{'action':'open','title':'Ver no Flix'}]
    return d
