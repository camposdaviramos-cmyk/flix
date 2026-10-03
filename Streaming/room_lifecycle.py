"""Atomic room ownership and disconnection cleanup (caller owns transaction)."""
import time

PRESENCE_SECONDS=45

def migrate(db):
    cols={r[1] for r in db.execute('PRAGMA table_info(community_rooms)')}
    if 'permanent' not in cols:db.execute('ALTER TABLE community_rooms ADD COLUMN permanent INTEGER NOT NULL DEFAULT 0')
    cols={r[1] for r in db.execute('PRAGMA table_info(community_members)')}
    if 'stage_request' not in cols:db.execute("ALTER TABLE community_members ADD COLUMN stage_request TEXT NOT NULL DEFAULT ''")
    if 'stage_at' not in cols:db.execute('ALTER TABLE community_members ADD COLUMN stage_at REAL NOT NULL DEFAULT 0')
    db.execute("UPDATE community_members SET seat=NULL,mic=0,camera=0 WHERE seat>4 AND room_id IN (SELECT id FROM community_rooms WHERE kind='live')")

def repair(db,rid,now=None):
    now=time.time() if now is None else now
    r=db.execute("SELECT * FROM community_rooms WHERE id=? AND status='open'",(rid,)).fetchone()
    if not r or r['permanent']:return
    current=db.execute("SELECT m.seen_at,m.status,u.status account_status FROM community_members m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.user_id=?",(rid,r['host_id'])).fetchone()
    if current and current['status']=='joined' and current['account_status']=='active' and current['seen_at']>now-PRESENCE_SECONDS:return
    next_host=db.execute("SELECT m.user_id FROM community_members m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.status='joined' AND m.seen_at>? AND u.status='active' ORDER BY m.joined_at,m.user_id LIMIT 1",(rid,now-PRESENCE_SECONDS)).fetchone()
    end=min(now,current['seen_at']+PRESENCE_SECONDS) if current else now
    position=r['position']+(max(0,end-r['updated_at']) if not r['paused'] else 0)
    db.execute("UPDATE community_members SET seat=NULL,mic=0,camera=0,stage_request='' WHERE room_id=? AND user_id=?",(rid,r['host_id']))
    if not next_host:
        db.execute("UPDATE community_rooms SET status='closed',paused=1,position=?,revision=revision+1,updated_at=? WHERE id=?",(position,now,rid))
        db.execute("UPDATE community_games SET status='cancelled',revision=revision+1 WHERE room_id=? AND status IN ('lobby','playing')",(rid,))
        db.execute("UPDATE community_members SET mic=0,camera=0,seat=NULL,stage_request='' WHERE room_id=?",(rid,))
        db.execute('DELETE FROM community_signals WHERE room_id=?',(rid,))
    else:
        db.execute("UPDATE community_members SET seat=1,mic_blocked=0,stage_request='' WHERE room_id=? AND user_id=?",(rid,next_host['user_id']))
        db.execute('UPDATE community_rooms SET host_id=?,paused=1,position=?,revision=revision+1,updated_at=? WHERE id=?',(next_host['user_id'],position,now,rid))

def sweep(db):
    ids=[r[0] for r in db.execute("SELECT r.id FROM community_rooms r LEFT JOIN community_members m ON m.room_id=r.id AND m.user_id=r.host_id LEFT JOIN users u ON u.id=r.host_id WHERE r.status='open' AND r.permanent=0 AND (m.user_id IS NULL OR m.status!='joined' OR m.seen_at<=? OR u.status!='active')",(time.time()-PRESENCE_SECONDS,))]
    for rid in ids:repair(db,rid)
