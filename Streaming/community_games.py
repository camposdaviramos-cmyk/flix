"""Room games. All moves, hidden information and rewards are server authoritative."""
import json
import math
import random
import secrets
import time
import unicodedata
from flask import g, jsonify, request

RNG = random.SystemRandom()
COLORS = ('red', 'blue', 'green', 'yellow')
WORDS = ('pipoca', 'cinema', 'astronauta', 'castelo', 'dragão', 'praia', 'robô', 'sorvete',
         'bicicleta', 'guitarra', 'dinossauro', 'foguete', 'girassol', 'chuva', 'cachorro',
         'montanha', 'pinguim', 'câmera', 'palhaço', 'tubarão', 'helicóptero', 'pizza')


def migrate(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS community_games(room_id TEXT PRIMARY KEY REFERENCES community_rooms(id) ON DELETE CASCADE,
        id TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,state TEXT NOT NULL,revision INTEGER NOT NULL,created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS community_game_results(game_id TEXT,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
        kind TEXT,points INTEGER,won INTEGER,created_at REAL,PRIMARY KEY(game_id,user_id));
    CREATE INDEX IF NOT EXISTS game_user_score ON community_game_results(user_id,created_at);
    ''')
    for b in [('primeira-vitoria','Primeira vitória','Venceu uma partida multiplayer','shield','#f4c46b'),
              ('mesa-amiga','Mesa amiga','Concluiu 5 partidas com a comunidade','users','#63dcb4'),
              ('mestre-traco','Mestre do traço','Venceu 3 partidas de Traço','spark','#ba9bff')]:
        db.execute('INSERT OR IGNORE INTO community_badges VALUES(?,?,?,?,?)', b)


def create_lobby(db,rid,uid,kind):
    game={'id':secrets.token_urlsafe(12),'kind':kind,'status':'lobby','revision':1};state={'players':[uid]}
    db.execute('INSERT OR REPLACE INTO community_games VALUES(?,?,?,?,?,?,?)',(rid,game['id'],kind,'lobby',json.dumps(state),1,time.time()))
    return game,state


def normal(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c)).strip()


def draw_cards(s, uid, count):
    for _ in range(count):
        if not s['deck'] and len(s['discard']) > 1:
            s['deck'], s['discard'] = s['discard'][:-1], s['discard'][-1:]
            RNG.shuffle(s['deck'])
        if s['deck']:
            s['hands'][uid].append(s['deck'].pop())


def event(s,kind,uid=None,**extra):
    s['event_seq']=s.get('event_seq',0)+1
    entry={'id':s['event_seq'],'kind':kind,'user_id':uid,'at':time.time(),**extra}
    s.setdefault('events',[]).append(entry);s['events']=s['events'][-24:]


def playable(s,uid,card):
    color,value=card.split(':')
    if card=='wild:+4':return not any(c.split(':')[0]==s['color'] for c in s['hands'][uid])
    return color=='wild' or color==s['color'] or value==s['discard'][-1].split(':')[1]


def next_turn(s, steps=1):
    s['turn'] = (s['turn'] + steps * s['direction']) % len(s['players'])
    s['deadline'] = time.time() + 60
    s.pop('drawn',None);s.pop('uno_armed',None)


def begin_drawing(s):
    s.update(word=RNG.choice(WORDS), strokes=[], guesses=[], solved=[], deadline=time.time()+75, phase='drawing')


def register(app, db, auth, data, error, room):
    def member(rid):
        r=room(rid, member=True)
        if not db().execute("SELECT 1 FROM community_members WHERE room_id=? AND user_id=? AND seen_at>?", (rid,g.user['id'],time.time()-45)).fetchone():
            raise error('Reconecte à sala para jogar.',403)
        return r

    def save(rid, game, s):
        db().execute('UPDATE community_games SET status=?,state=?,revision=revision+1 WHERE room_id=?', (game['status'],json.dumps(s),rid))
        game['revision']+=1

    def finish(game,s,winners):
        if game['status']=='finished':return
        game['status']='finished';s['winners']=winners;s['finished_at']=time.time()
        for uid in s['players']:
            used=db().execute('SELECT COALESCE(SUM(points),0) FROM community_game_results WHERE user_id=? AND created_at>?',(uid,time.time()-86400)).fetchone()[0]
            points=min(max(0,200-used),5+(25 if uid in winners else 0)+min(50,s.get('scores',{}).get(uid,0)))
            db().execute('INSERT OR IGNORE INTO community_game_results VALUES(?,?,?,?,?,?)',(game['id'],uid,game['kind'],points,int(uid in winners),time.time()))
            games,wins,draw_wins=db().execute("SELECT COUNT(*),COALESCE(SUM(won),0),COALESCE(SUM(CASE WHEN kind='draw' THEN won ELSE 0 END),0) FROM community_game_results WHERE user_id=?",(uid,)).fetchone()
            for badge,eligible in [('primeira-vitoria',wins>=1),('mesa-amiga',games>=5),('mestre-traco',draw_wins>=3)]:
                if eligible:db().execute('INSERT OR IGNORE INTO community_awards(user_id,badge_id,awarded_by,created_at) SELECT ?,id,NULL,? FROM community_badges WHERE id=?',(uid,time.time(),badge))

    def advance_round(game,s):
        s['round']+=1
        if s['round']>=len(s['players']):
            best=max(s['scores'].values())
            finish(game,s,[u for u in s['players'] if s['scores'][u]==best] if best else [])
        else:begin_drawing(s)

    def tick(game,s):
        if game['status']!='playing':return False
        if time.time()-s['started_at']>1800:
            game['status']='cancelled';s['notice']='A partida expirou sem distribuir pontos.';return True
        if time.time()<s['deadline']:return False
        if game['kind']=='colors':
            late=s['players'][s['turn']];already_bought=bool(s.get('drawn'));before=len(s['hands'][late])
            if not already_bought:draw_cards(s,late,1)
            s.pop('uno_pending',None);event(s,'pass' if already_bought else 'draw',late,count=len(s['hands'][late])-before,reason='timeout');next_turn(s);s['notice']='Tempo esgotado: vez passada.' if already_bought else 'Tempo esgotado: uma carta comprada e vez passada.'
        elif s['phase']=='drawing':s.update(phase='reveal',deadline=time.time()+5)
        else:advance_round(game,s)
        return True

    def visible(game,s):
        uid=g.user['id'];out={k:game[k] for k in ('id','kind','status','revision')}
        out.update(players=[dict(db().execute("SELECT u.id,u.name,u.username,COALESCE(p.avatar,'') avatar FROM users u LEFT JOIN community_profiles p ON p.user_id=u.id WHERE u.id=?",(u,)).fetchone()) for u in s['players']],server_time=time.time(),notice=s.get('notice',''),winners=s.get('winners',[]),events=s.get('events',[]),rules_version=s.get('rules_version',1))
        if game['status'] in ('playing','finished'):
            out['deadline']=s['deadline']
            if game['kind']=='colors':
                out.update(hand=s['hands'].get(uid,[]),counts={u:len(h) for u,h in s['hands'].items()},top=s['discard'][-1],color=s['color'],turn=s['players'][s['turn']],direction=s['direction'],playable=[c for c in s['hands'].get(uid,[]) if (not s.get('drawn') or s['drawn']['card']==c) and playable(s,uid,c)],can_pass=s.get('drawn',{}).get('user_id')==uid,uno_pending=s.get('uno_pending'),uno_armed=s.get('uno_armed'),uno_called=s.get('uno_called',[]))
            else:
                drawer=s['players'][min(s['round'],len(s['players'])-1)]
                out.update(drawer=drawer,round=min(s['round']+1,len(s['players'])),rounds=len(s['players']),phase=s['phase'],strokes=s['strokes'],guesses=s['guesses'][-30:],scores=s['scores'],solved=s['solved'],hint=' '.join('_' if c!=' ' else ' ' for c in s['word']))
                if uid==drawer or s['phase']=='reveal' or game['status']=='finished':out['word']=s['word']
        return out

    @app.route('/api/community/rooms/<rid>/game',methods=['GET','POST'])
    @auth()
    def game_api(rid):
        db().execute('BEGIN IMMEDIATE');r=member(rid);uid=g.user['id']
        row=db().execute('SELECT * FROM community_games WHERE room_id=?',(rid,)).fetchone()
        game=dict(row) if row else None;s=json.loads(game['state']) if game else None
        changed=tick(game,s) if game else False
        if changed:save(rid,game,s)
        if request.method=='GET':
            result=visible(game,s) if game else None;db().commit();return jsonify(game=result)
        d=data();action=d.get('action')
        if action=='create':
            if uid!=r['host_id']:raise error('Somente o anfitrião pode adicionar um jogo.',403)
            if game and game['status'] in ('lobby','playing'):raise error('Finalize ou encerre a partida atual.',409)
            if d.get('kind') not in ('colors','draw'):raise error('Jogo inválido.')
            game,s=create_lobby(db(),rid,uid,d['kind'])
        else:
            if not game:raise error('Nenhum jogo nesta sala.',404)
            if d.get('game_id') and d['game_id']!=game['id']:raise error('Outra partida foi iniciada. Atualize a mesa.',409)
            if action not in ('stroke','guess','uno','catch','join') and d.get('revision')!=game['revision']:
                db().commit();raise error('A partida mudou. Tente novamente.',409)
            if action=='cancel':
                if uid!=r['host_id']:raise error('Somente o anfitrião pode encerrar.',403)
                if game['status'] not in ('lobby','playing'):raise error('Esta partida já terminou.',409)
                game['status']='cancelled';s['notice']='Partida encerrada pelo anfitrião. Nenhum ponto concedido.'
            elif action in ('join','leave'):
                if game['status']!='lobby':raise error('A partida já começou.',409)
                if action=='join' and uid not in s['players']:
                    if len(s['players'])>=8:raise error('Esta partida tem 8 jogadores. Você pode acompanhar a mesa.')
                    s['players'].append(uid)
                if action=='leave' and uid in s['players']:s['players'].remove(uid)
            elif action=='start':
                if uid!=r['host_id']:raise error('Somente o anfitrião pode iniciar.',403)
                if game['status']!='lobby':raise error('Esta partida já começou.',409)
                connected={row[0] for row in db().execute("SELECT m.user_id FROM community_members m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.status='joined' AND m.seen_at>? AND u.status='active'",(rid,time.time()-45))}
                s['players']=[u for u in s['players'] if u in connected]
                if len(s['players'])<2:raise error('São necessários pelo menos 2 jogadores conectados.')
                game['status']='playing';s['started_at']=time.time();s['notice']='';s['rules_version']=2;event(s,'start',uid)
                if game['kind']=='colors':
                    deck=[f'{c}:{v}' for c in COLORS for v in list(range(10))+list(range(1,10))+['skip','reverse','+2']*2]+['wild:*']*4+['wild:+4']*4
                    RNG.shuffle(deck);s.update(deck=deck,discard=[],hands={u:[] for u in s['players']},turn=0,direction=1,deadline=time.time()+60)
                    for u in s['players']:draw_cards(s,u,7)
                    top=next(c for c in s['deck'] if c.split(':')[1].isdigit());s['deck'].remove(top);s['discard']=[top];s['color']=top.split(':')[0]
                else:s.update(round=0,scores={u:0 for u in s['players']});begin_drawing(s)
            else:
                if game['status']!='playing' or uid not in s['players']:raise error('Você não está jogando esta partida.',403)
                if game['kind']=='colors':
                    current=s['players'][s['turn']]
                    if action=='uno':
                        if len(s['hands'][uid])==2 and current==uid:
                            s['uno_armed']=uid;s['notice']='UNO preparado para a próxima carta.'
                        elif len(s['hands'][uid])==1 and s.get('uno_pending')==uid:
                            s.pop('uno_pending',None);s.setdefault('uno_called',[]).append(uid);event(s,'uno',uid);s['notice']='UNO!'
                        else:raise error('Use UNO com duas cartas na sua vez ou logo após ficar com uma.')
                    elif action=='catch':
                        target=s.get('uno_pending')
                        if not target or target==uid or len(s['hands'][target])!=1:raise error('Ninguém esqueceu de anunciar UNO.',409)
                        draw_cards(s,target,2);s.pop('uno_pending',None);event(s,'catch',uid,target=target,count=2);s['notice']='UNO não anunciado: duas cartas de penalidade.'
                    else:
                        if current!=uid:raise error('Aguarde sua vez.',409)
                        if action=='draw':
                            if s.get('drawn'):raise error('Jogue a carta comprada ou passe a vez.',409)
                            s.pop('uno_pending',None);before=len(s['hands'][uid]);draw_cards(s,uid,1);event(s,'draw',uid,count=len(s['hands'][uid])-before)
                            if len(s['hands'][uid])>before and playable(s,uid,s['hands'][uid][-1]):
                                s['drawn']={'user_id':uid,'card':s['hands'][uid][-1]};s['notice']='Você pode jogar a carta comprada ou passar.'
                            else:next_turn(s);s['notice']='Carta comprada. A vez passou.'
                        elif action=='pass':
                            if s.get('drawn',{}).get('user_id')!=uid:raise error('Compre uma carta antes de passar.')
                            s.pop('uno_pending',None);event(s,'pass',uid);next_turn(s);s['notice']='Vez passada.'
                        elif action=='play':
                            card=d.get('card')
                            if card not in s['hands'][uid]:raise error('Você não tem essa carta.')
                            if s.get('drawn') and s['drawn']['card']!=card:raise error('Nesta vez você só pode jogar a carta que acabou de comprar.')
                            if not playable(s,uid,card):raise error('Combine cor ou símbolo. +4 só é permitido sem cartas da cor atual.')
                            color,value=card.split(':');chosen=d.get('color') if color=='wild' else color
                            if chosen not in COLORS:raise error('Escolha uma cor para o coringa.')
                            s.pop('uno_pending',None);armed=s.get('uno_armed')==uid
                            s['hands'][uid].remove(card);s['discard'].append(card);s['color']=chosen;s['notice']=''
                            s['uno_called']=[u for u in s.get('uno_called',[]) if u!=uid]
                            event(s,'play',uid,card=card,color=chosen)
                            if len(s['hands'][uid])==1:
                                if armed:s.setdefault('uno_called',[]).append(uid);event(s,'uno',uid);s['notice']='UNO!'
                                else:s['uno_pending']=uid;s['notice']='Uma carta! Anuncie UNO antes da próxima jogada.'
                            if value=='reverse':s['direction']*=-1
                            next_turn(s)
                            if value in ('+2','+4'):
                                target=s['players'][s['turn']];draw_cards(s,target,int(value[1]));event(s,'penalty',uid,target=target,count=int(value[1]));next_turn(s)
                            elif value=='skip' or (value=='reverse' and len(s['players'])==2):next_turn(s)
                            if not s['hands'][uid]:s.pop('uno_pending',None);event(s,'win',uid);finish(game,s,[uid])
                        else:raise error('Jogada inválida.')
                else:
                    drawer=s['players'][s['round']]
                    if s['phase']!='drawing' or d.get('round')!=s['round']+1:raise error('A rodada mudou.',409)
                    if action in ('stroke','clear'):
                        if uid!=drawer:raise error('Somente quem desenha pode usar a lousa.',403)
                        if action=='clear':s['strokes']=[]
                        else:
                            points=d.get('points');color=d.get('color','#fafafa');width=d.get('width',4)
                            if not isinstance(points,list) or not 2<=len(points)<=160 or len(s['strokes'])>=400:raise error('Traço inválido ou lousa cheia.')
                            if color not in ('#fafafa','#15151f','#f16d85','#ffd36d','#5ed6ab','#7eacff','#c59aff') or type(width) not in (int,float) or width not in (3,6,12):raise error('Pincel inválido.')
                            if any(not isinstance(p,list) or len(p)!=2 or any(type(n) not in (int,float) or not math.isfinite(n) or not 0<=n<=1 for n in p) for p in points):raise error('Coordenadas inválidas.')
                            s['strokes'].append({'points':points,'color':color,'width':width})
                    elif action=='guess':
                        if uid==drawer or uid in s['solved']:raise error('Aguarde a próxima rodada.')
                        guess=str(d.get('text','')).strip()[:80]
                        if not guess:raise error('Escreva seu palpite.')
                        now=time.time();last=s.get('last_guess',{}).get(uid,0)
                        if now-last<.7:raise error('Aguarde um instante.',429)
                        s.setdefault('last_guess',{})[uid]=now
                        correct=normal(guess)==normal(s['word'])
                        s['guesses'].append({'user_id':uid,'text':'Acertou!' if correct else guess,'correct':correct})
                        if correct:
                            event(s,'correct',uid)
                            s['solved'].append(uid);s['scores'][uid]+=max(10,int((s['deadline']-now)/3));s['scores'][drawer]+=10
                            if len(s['solved'])==len(s['players'])-1:s.update(phase='reveal',deadline=now+5)
                    else:raise error('Jogada inválida.')
            save(rid,game,s)
        result=visible(game,s);db().commit();return jsonify(game=result)
