"""Admin-managed trial coupons, redeemed atomically with account creation."""
import math
import re
import sqlite3
import time
import uuid
from flask import jsonify


def migrate(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS coupons (
      id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL COLLATE NOCASE,
      kind TEXT NOT NULL DEFAULT 'trial', trial_hours INTEGER NOT NULL,
      plan_id TEXT REFERENCES plans(id), max_uses INTEGER NOT NULL DEFAULT 0,
      expires_at REAL NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
      created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS coupon_redemptions (
      id TEXT PRIMARY KEY, coupon_id TEXT NOT NULL REFERENCES coupons(id),
      user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
      code TEXT NOT NULL, plan_id TEXT NOT NULL REFERENCES plans(id),
      trial_hours INTEGER NOT NULL, expires_at REAL NOT NULL, created_at REAL NOT NULL,
      UNIQUE(coupon_id,user_id));
    CREATE INDEX IF NOT EXISTS idx_coupon_uses ON coupon_redemptions(coupon_id);
    ''')


def normalize_code(value, error):
    if not isinstance(value,str):
        raise error('Informe um código de cupom válido.')
    code=value.strip().upper()
    if not re.fullmatch(r'[A-Z0-9_-]{3,32}',code):
        raise error('O cupom deve ter de 3 a 32 letras, números, hífens ou _.')
    return code


def available_coupon(db, code, plan_id, error):
    code=normalize_code(code,error)
    if not isinstance(plan_id,str) or not plan_id:
        raise error('Selecione um plano disponível.')
    coupon=db.execute('SELECT c.*, (SELECT COUNT(*) FROM coupon_redemptions r WHERE r.coupon_id=c.id) AS used_count FROM coupons c WHERE code=?',(code,)).fetchone()
    if not coupon or not coupon['active']:
        raise error('Cupom inválido ou desativado.')
    if coupon['expires_at'] and coupon['expires_at']<=time.time():
        raise error('Este cupom expirou.')
    if coupon['max_uses'] and coupon['used_count']>=coupon['max_uses']:
        raise error('Este cupom atingiu o limite de utilizações.')
    if coupon['plan_id'] and coupon['plan_id']!=plan_id:
        raise error('Este cupom não é válido para o plano selecionado.')
    if not db.execute('SELECT 1 FROM plans WHERE id=? AND active=1',(plan_id,)).fetchone():
        raise error('Selecione um plano disponível.')
    return coupon


def redeem(db, coupon, uid, plan_id, expires_at):
    # The caller holds BEGIN IMMEDIATE from validation through insertion and commit.
    db.execute('INSERT INTO coupon_redemptions VALUES(?,?,?,?,?,?,?,?)',
               (uuid.uuid4().hex,coupon['id'],uid,coupon['code'],plan_id,coupon['trial_hours'],expires_at,time.time()))


def register_coupons(app, db, auth, data, error, rate_limit):
    def integer(value,label,minimum,maximum):
        if not re.fullmatch(r'[0-9]{1,9}',str(value)):
            raise error(f'{label}: informe um número inteiro.')
        number=int(value)
        if not minimum<=number<=maximum:
            raise error(f'{label}: use um valor entre {minimum} e {maximum}.')
        return number

    def coupon_values(d):
        code=normalize_code(d.get('code',''),error)
        if d.get('kind','trial')!='trial':
            raise error('Tipo de cupom inválido. Selecione teste grátis.')
        hours=integer(d.get('trial_hours',0),'Duração em horas',1,8760)
        maximum=integer(d.get('max_uses') or 0,'Limite de usos',0,1000000)
        plan_id=d.get('plan_id') or None
        if plan_id is not None and not isinstance(plan_id,str):
            raise error('Plano inválido.')
        if plan_id and not db().execute('SELECT 1 FROM plans WHERE id=? AND active=1',(plan_id,)).fetchone():
            raise error('Selecione um plano disponível ou todos os planos.')
        try:
            expires=float(d.get('expires_at') or 0)
        except (ValueError,TypeError):
            raise error('Validade do cupom inválida.')
        if not math.isfinite(expires) or not 0<=expires<=253402300799:
            raise error('Validade do cupom inválida.')
        active=d.get('active',True)
        if not isinstance(active,bool):
            raise error('Estado do cupom inválido.')
        return code,hours,plan_id,maximum,expires,int(active)

    @app.get('/api/admin/coupons')
    @auth(admin=True)
    def list_coupons():
        rows=db().execute('SELECT c.*,p.name AS plan_name,(SELECT COUNT(*) FROM coupon_redemptions r WHERE r.coupon_id=c.id) AS used_count FROM coupons c LEFT JOIN plans p ON p.id=c.plan_id ORDER BY c.created_at DESC').fetchall()
        return jsonify(coupons=[dict(r) for r in rows])

    @app.post('/api/admin/coupons')
    @auth(admin=True)
    def create_coupon():
        d=data()
        db().execute('BEGIN IMMEDIATE')
        values=coupon_values(d)
        cid=uuid.uuid4().hex
        try:
            db().execute('INSERT INTO coupons(id,code,trial_hours,plan_id,max_uses,expires_at,active,created_at) VALUES(?,?,?,?,?,?,?,?)',(cid,*values,time.time()))
        except sqlite3.IntegrityError:
            raise error('Já existe um cupom com este código.',409)
        db().commit()
        return jsonify(id=cid),201

    @app.put('/api/admin/coupons/<cid>')
    @auth(admin=True)
    def edit_coupon(cid):
        d=data()
        db().execute('BEGIN IMMEDIATE')
        if not db().execute('SELECT 1 FROM coupons WHERE id=?',(cid,)).fetchone():
            raise error('Cupom não encontrado.',404)
        values=coupon_values(d)
        used=db().execute('SELECT COUNT(*) FROM coupon_redemptions WHERE coupon_id=?',(cid,)).fetchone()[0]
        if values[3] and values[3]<used:
            raise error('O limite não pode ser menor que os usos já realizados. Para parar novos usos, desative o cupom.')
        try:
            db().execute('UPDATE coupons SET code=?,trial_hours=?,plan_id=?,max_uses=?,expires_at=?,active=? WHERE id=?',(*values,cid))
        except sqlite3.IntegrityError:
            raise error('Já existe um cupom com este código.',409)
        db().commit()
        return jsonify(ok=True)

    @app.patch('/api/admin/coupons/<cid>')
    @auth(admin=True)
    def toggle_coupon(cid):
        active=data().get('active')
        if not isinstance(active,bool):
            raise error('Estado do cupom inválido.')
        if not db().execute('UPDATE coupons SET active=? WHERE id=?',(int(active),cid)).rowcount:
            raise error('Cupom não encontrado.',404)
        db().commit()
        return jsonify(ok=True)

    @app.post('/api/coupons/validate')
    def validate_coupon():
        rate_limit()
        d=data()
        coupon=available_coupon(db(),d.get('code',''),d.get('plan_id',''),error)
        return jsonify(coupon={'code':coupon['code'],'kind':'trial','trial_hours':coupon['trial_hours'],'plan_id':coupon['plan_id']})
