"""Integer coin ledger. Credits and spending share the caller's SQLite transaction."""
import json
import re
import secrets
import time
from flask import g, jsonify, request


def migrate(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS coin_config(id INTEGER PRIMARY KEY CHECK(id=1),welcome INTEGER NOT NULL DEFAULT 0);
    INSERT OR IGNORE INTO coin_config VALUES(1,0);
    CREATE TABLE IF NOT EXISTS coin_ledger(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT NOT NULL REFERENCES users(id),amount INTEGER NOT NULL,reason TEXT NOT NULL,reference TEXT NOT NULL UNIQUE,created_at REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS coin_user_ledger ON coin_ledger(user_id,id DESC);
    CREATE TABLE IF NOT EXISTS coin_packages(id TEXT PRIMARY KEY,name TEXT NOT NULL,coins INTEGER NOT NULL,price INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS coin_gifts(id TEXT PRIMARY KEY,name TEXT NOT NULL,symbol TEXT NOT NULL,coins INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS coin_received(id TEXT PRIMARY KEY,sender TEXT NOT NULL REFERENCES users(id),recipient TEXT NOT NULL REFERENCES users(id),gift_id TEXT NOT NULL REFERENCES coin_gifts(id),name TEXT NOT NULL,symbol TEXT NOT NULL,coins INTEGER NOT NULL,room_id TEXT,created_at REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS coin_received_profile ON coin_received(recipient,created_at DESC);
    CREATE TABLE IF NOT EXISTS room_plugins(id TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',kind TEXT NOT NULL,engine TEXT NOT NULL DEFAULT 'embed',url TEXT NOT NULL DEFAULT '',cover TEXT NOT NULL DEFAULT '',coins INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,revision INTEGER NOT NULL DEFAULT 1);
    CREATE TRIGGER IF NOT EXISTS coin_welcome AFTER INSERT ON users WHEN (SELECT welcome FROM coin_config WHERE id=1)>0 BEGIN
      INSERT OR IGNORE INTO coin_ledger(user_id,amount,reason,reference,created_at) SELECT NEW.id,welcome,'Boas-vindas','welcome:'||NEW.id,NEW.created_at FROM coin_config WHERE id=1;
    END;
    ''')
    for gift in [('popcorn','Pipoca','🍿',10),('heart','Coração','💖',25),('star','Estrela','🌟',50),('trophy','Troféu','🏆',100)]:
        db.execute('INSERT OR IGNORE INTO coin_gifts(id,name,symbol,coins) VALUES(?,?,?,?)',gift)
    for plugin in [('colors','Cores','Cartas, estratégia e um último UNO!','game','colors'),('draw','Traço','Desenhe e descubra com a turma.','game','draw')]:
        db.execute('INSERT OR IGNORE INTO room_plugins(id,name,description,kind,engine) VALUES(?,?,?,?,?)',plugin)
    db.executescript('''
    CREATE TRIGGER IF NOT EXISTS coin_cancel_lobby AFTER UPDATE OF status ON community_games WHEN OLD.status='lobby' AND NEW.status='cancelled' BEGIN
      INSERT OR IGNORE INTO coin_ledger(user_id,amount,reason,reference,created_at)
      SELECT user_id,-amount,'Partida cancelada antes de iniciar','refund:'||reference,unixepoch() FROM coin_ledger WHERE reference LIKE 'game:'||OLD.id||':%' AND amount<0;
    END;
    CREATE TRIGGER IF NOT EXISTS coin_close_room AFTER UPDATE OF status ON community_rooms WHEN OLD.status='open' AND NEW.status='closed' BEGIN
      INSERT OR IGNORE INTO coin_ledger(user_id,amount,reason,reference,created_at)
      SELECT l.user_id,-l.amount,'Partida cancelada antes de iniciar','refund:'||l.reference,unixepoch() FROM coin_ledger l JOIN community_games cg ON cg.room_id=OLD.id AND cg.status='lobby' WHERE l.reference LIKE 'game:'||cg.id||':%' AND l.amount<0;
    END;
    ''')
    cols={r[1] for r in db.execute('PRAGMA table_info(orders)')}
    for name,definition in {'kind':"TEXT NOT NULL DEFAULT 'subscription'",'coins':'INTEGER NOT NULL DEFAULT 0','label':"TEXT NOT NULL DEFAULT ''"}.items():
        if name not in cols:db.execute(f'ALTER TABLE orders ADD COLUMN {name} {definition}')


def integer(value,lo,hi,error):
    if isinstance(value,bool) or not re.fullmatch(r'\d+',str(value)) or not lo<=int(value)<=hi:raise error(f'Informe um número inteiro entre {lo} e {hi}.')
    return int(value)


def balance(db,uid):
    return db.execute('SELECT COALESCE(SUM(amount),0) FROM coin_ledger WHERE user_id=?',(uid,)).fetchone()[0]


def entry(db,uid,amount,reason,reference,error=None):
    old=db.execute('SELECT * FROM coin_ledger WHERE reference=?',(reference,)).fetchone()
    if old:
        if old['user_id']!=uid or old['amount']!=amount:raise ValueError('Conflicting ledger reference')
        return False
    if amount<0 and error and balance(db,uid)<-amount:raise error('Saldo insuficiente. Adicione moedas à sua carteira.',402)
    db.execute('INSERT INTO coin_ledger(user_id,amount,reason,reference,created_at) VALUES(?,?,?,?,?)',(uid,amount,reason,reference,time.time()))
    return True


def payment(db,order,status):
    # The provider has already been authenticated and amount/currency checked by app.reconcile.
    ref='purchase:'+order['id']
    if status=='approved' and not db.execute('SELECT 1 FROM coin_ledger WHERE reference=?',('reversal:'+order['id'],)).fetchone():
        entry(db,order['user_id'],order['coins'],order['label'] or 'Compra de moedas',ref)
    if status in ('refunded','charged_back') and db.execute('SELECT 1 FROM coin_ledger WHERE reference=?',(ref,)).fetchone():
        # A provider reversal can produce debt if coins were spent; future spending is blocked.
        entry(db,order['user_id'],-order['coins'],'Estorno da compra','reversal:'+order['id'])


def join_game(db,game_id,uid,cost,confirmation,error):
    if cost and (type(confirmation)!=int or confirmation!=cost):raise error(f'Confirme a entrada por {cost} moedas.',409)
    if cost:entry(db,uid,-cost,'Entrada em jogo','game:'+game_id+':'+uid,error)


def refund_game(db,game_id):
    for r in db.execute("SELECT * FROM coin_ledger WHERE reference LIKE ? AND amount<0",('game:'+game_id+':%',)).fetchall():
        entry(db,r['user_id'],-r['amount'],'Partida cancelada antes de iniciar','refund:'+r['reference'])


def profile(db,uid,viewer):
    gifts=[dict(r) for r in db.execute('SELECT gift_id,name,symbol,COUNT(*) count,SUM(coins) coins FROM coin_received WHERE recipient=? GROUP BY gift_id,name,symbol ORDER BY MAX(created_at) DESC LIMIT 30',(uid,))]
    song=db.execute('SELECT t.* FROM music_play_events e JOIN music_tracks t ON t.id=e.track_id WHERE e.user_id=? AND e.listened>=3 ORDER BY e.last_at DESC LIMIT 1',(uid,)).fetchone()
    music=dict(song) if song else None
    if music:
        music['hearts']=db.execute('SELECT COUNT(*) FROM room_music_hearts WHERE user_id=? AND track_id=?',(uid,music['id'])).fetchone()[0]
        music['liked']=bool(db.execute('SELECT 1 FROM room_music_hearts WHERE user_id=? AND track_id=? AND reactor=?',(uid,music['id'],viewer)).fetchone())
    return {'gifts':gifts,'recent_music':music}


def register(app,db,auth,data,error):
    def uid():return g.user['id']

    @app.get('/api/wallet')
    @auth()
    def wallet():
        return jsonify(balance=balance(db(),uid()),packages=[dict(r) for r in db().execute('SELECT * FROM coin_packages WHERE active=1 ORDER BY price')],gifts=[dict(r) for r in db().execute('SELECT * FROM coin_gifts WHERE active=1 ORDER BY coins')],ledger=[dict(r) for r in db().execute('SELECT amount,reason,created_at FROM coin_ledger WHERE user_id=? ORDER BY id DESC LIMIT 80',(uid(),))])

    @app.post('/api/wallet/gifts')
    @auth()
    def send_gift():
        d=data();recipient=d.get('recipient');key=str(d.get('request_id',''))
        if not re.fullmatch(r'[A-Za-z0-9_-]{12,80}',key):raise error('Atualize e confirme o presente novamente.')
        if recipient==uid() or not db().execute("SELECT 1 FROM users WHERE id=? AND status='active'",(recipient,)).fetchone():raise error('Destinatário indisponível.')
        db().execute('BEGIN IMMEDIATE')
        rid=uid()+':'+key
        old=db().execute('SELECT * FROM coin_received WHERE id=?',(rid,)).fetchone()
        if old:
            if old['recipient']!=recipient or old['gift_id']!=d.get('gift_id'):raise error('Esta confirmação já foi utilizada.',409)
            return jsonify(ok=True,balance=balance(db(),uid()))
        gift=db().execute('SELECT * FROM coin_gifts WHERE id=? AND active=1',(d.get('gift_id'),)).fetchone()
        if not gift:raise error('Presente indisponível.',404)
        if d.get('confirm_coins')!=gift['coins']:raise error('O valor mudou. Confira o presente e confirme novamente.',409)
        room=d.get('room_id') or None
        if room:
            for who in (uid(),recipient):
                if not db().execute("SELECT 1 FROM community_members WHERE room_id=? AND user_id=? AND status='joined' AND seen_at>?",(room,who,time.time()-45)).fetchone():raise error('A pessoa precisa estar na sala.',409)
        entry(db(),uid(),-gift['coins'],'Presente: '+gift['name'],'gift:'+rid,error)
        db().execute('INSERT INTO coin_received VALUES(?,?,?,?,?,?,?,?,?)',(rid,uid(),recipient,gift['id'],gift['name'],gift['symbol'],gift['coins'],room,time.time()))
        from social_spaces import notify
        notify(db(),recipient,uid(),'Você recebeu '+gift['name'],g.user['name']+' enviou um presente para você.','/comunidade/perfil/'+g.user['username'],'gift:'+rid)
        db().commit();return jsonify(ok=True,balance=balance(db(),uid())),201

    @app.route('/api/admin/economy',methods=['GET','PUT'])
    @auth(admin=True)
    def admin_economy():
        if request.method=='PUT':
            n=integer(data().get('welcome'),0,100000,error)
            db().execute('UPDATE coin_config SET welcome=? WHERE id=1',(n,))
            db().execute('INSERT INTO community_audit(admin_id,action,target,created_at) VALUES(?,?,?,?)',(uid(),'economy:welcome',str(n),time.time()));db().commit()
        return jsonify(welcome=db().execute('SELECT welcome FROM coin_config').fetchone()[0],packages=[dict(r) for r in db().execute('SELECT * FROM coin_packages ORDER BY price')],gifts=[dict(r) for r in db().execute('SELECT * FROM coin_gifts ORDER BY coins')],plugins=[dict(r) for r in db().execute('SELECT * FROM room_plugins ORDER BY name')])

    @app.put('/api/admin/economy/<kind>/<item>')
    @auth(admin=True)
    def admin_economy_item(kind,item):
        if kind not in ('packages','gifts','plugins') or not re.fullmatch(r'[a-z0-9_-]{2,40}',item):raise error('Cadastro inválido.')
        d=data();name=str(d.get('name','')).strip();active=int(d.get('active') is True)
        if not 2<=len(name)<=80:raise error('Informe um nome de 2 a 80 caracteres.')
        coins=integer(d.get('coins',0),0 if kind=='plugins' else 1,1000000,error)
        if kind=='packages':
            price=integer(d.get('price'),100,10000000,error)
            db().execute('INSERT INTO coin_packages VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,coins=excluded.coins,price=excluded.price,active=excluded.active',(item,name,coins,price,active))
        elif kind=='gifts':
            symbol=str(d.get('symbol','🎁'))[:16]
            db().execute('INSERT INTO coin_gifts VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,symbol=excluded.symbol,coins=excluded.coins,active=excluded.active',(item,name,symbol,coins,active))
        else:
            from community import external_url
            typ=d.get('kind','game');engine=item if item in ('colors','draw') else 'embed'
            if typ not in ('game','widget'):raise error('Tipo de plugin inválido.')
            if engine!='embed':typ='game'
            url,_=external_url(d.get('url',''),error,optional=engine!='embed')
            if url:
                from urllib.parse import urlsplit
                if urlsplit(url).hostname==request.host.split(':')[0]:raise error('Hospede o plugin em um domínio separado da plataforma.')
            cover,_=external_url(d.get('cover',''),error,optional=True)
            if typ=='widget' and coins:raise error('Widgets são gratuitos. Cobrança disponível para jogos.')
            db().execute('INSERT INTO room_plugins(id,name,description,kind,engine,url,cover,coins,active) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,description=excluded.description,kind=excluded.kind,url=excluded.url,cover=excluded.cover,coins=excluded.coins,active=excluded.active,revision=revision+1',(item,name,str(d.get('description',''))[:500],typ,engine,url,cover,coins,active))
        db().execute('INSERT INTO community_audit(admin_id,action,target,created_at) VALUES(?,?,?,?)',(uid(),'economy:'+kind,item,time.time()));db().commit();return jsonify(ok=True)
