"""Explicit/temporary playback traces, without signed URLs, bodies or cookies."""
import hashlib
import json
import math
import re
import time
from urllib.parse import urlsplit

from flask import g, jsonify, request


EVENTS = {'source', 'native-error', 'fallback', 'hls-error', 'manifest', 'level',
          'fragment', 'codecs', 'play-error', 'timeout', 'loadedmetadata',
          'canplay', 'playing', 'waiting', 'stalled', 'pause', 'progress', 'closed',
          'source-probe', 'direct-open'}
NUMBERS = {'at': 3600000, 'mediaCode': 4, 'readyState': 4, 'networkState': 3,
           'position': 1e12, 'httpStatus': 599, 'width': 20000, 'height': 20000,
           'buffered': 1000}
FLAGS = {'paused', 'fatal', 'supported', 'remotePlaybackDisabled', 'reachable'}
WORDS = {'detail', 'errorType', 'errorName', 'videoCodec', 'audioCodec', 'mime'}


def automatic_diagnostics(db, user, content_id):
    """Time-limited investigation of one title, only for signed-in admins."""
    if not user or user['role'] != 'admin':
        return False
    row = db.execute("SELECT value FROM settings WHERE key='player_diagnostic_window'").fetchone()
    if not row:
        return False
    try:
        window = json.loads(row['value'])
        until = window.get('until')
        return (window.get('content_id') == content_id and type(until) in (int, float)
                and math.isfinite(until) and time.time() < until)
    except (ValueError, TypeError, AttributeError):
        return False


def clean_trace(value):
    if not isinstance(value, dict) or not isinstance(value.get('events'), list):
        raise ValueError('Diagnóstico inválido.')
    events = []
    for event in value['events'][-40:]:
        if not isinstance(event, dict) or event.get('event') not in EVENTS:
            continue
        row = {'event': event['event']}
        if event.get('probeMode') in ('cors', 'no-cors'):
            row['probeMode'] = event['probeMode']
        if event.get('responseType') in ('opaque', 'cors', 'basic', 'opaqueredirect', 'error'):
            row['responseType'] = event['responseType']
        if event.get('mode') in ('native', 'native-hls', 'hlsjs'):
            row['mode'] = event['mode']
        for key, maximum in NUMBERS.items():
            number = event.get(key)
            if type(number) in (int, float) and math.isfinite(number) and 0 <= number <= maximum:
                row[key] = round(number, 3)
        for key in FLAGS:
            if type(event.get(key)) is bool:
                row[key] = event[key]
        for key in WORDS:
            word = event.get(key)
            if isinstance(word, str) and re.fullmatch(r'[A-Za-z0-9_.+/-]{1,80}', word):
                row[key] = word
        events.append(row)
    capabilities = value.get('capabilities', {})
    if not isinstance(capabilities, dict):
        capabilities = {}
    build = value.get('build', 'diagnostic1')
    return {'build': build if build in ('diagnostic1', 'diagnostic3') else 'unknown', 'events': events, 'capabilities': {
        k: capabilities[k] for k in ('nativeHls', 'mse', 'mms', 'hlsSupported', 'secureContext')
        if type(capabilities.get(k)) is bool}}


def register_playback_diagnostics(app, db, auth, data, APIError, playback_item):
    with app.app_context():
        db().executescript('''
            CREATE TABLE IF NOT EXISTS playback_diagnostics(
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, content_id TEXT NOT NULL,
                episode_id TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
                revisions INTEGER NOT NULL, device TEXT NOT NULL, source_host TEXT NOT NULL,
                source_ref TEXT NOT NULL, trace TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_playback_diagnostics_user
                ON playback_diagnostics(user_id, created_at);
        ''')
        db().commit()

    @app.post('/api/player/diagnostics')
    @auth(paid=True)
    def save_diagnostic():
        if request.content_length and request.content_length > 20000:
            raise APIError('Diagnóstico muito grande.', 413)
        payload = data()
        rid = payload.get('id', '')
        if not isinstance(rid, str) or not re.fullmatch(r'[a-f0-9]{32}', rid):
            raise APIError('Identificador de diagnóstico inválido.')
        cid, eid = payload.get('content_id', ''), payload.get('episode_id', '')
        if not isinstance(cid, str) or not isinstance(eid, str) or max(len(cid), len(eid)) > 80:
            raise APIError('Conteúdo inválido.')
        _, url = playback_item(cid, eid)
        trace = clean_trace(payload.get('trace'))
        now = time.time()
        existing = db().execute('SELECT * FROM playback_diagnostics WHERE id=?', (rid,)).fetchone()
        if existing and (existing['user_id'] != g.user['id'] or existing['content_id'] != cid or existing['episode_id'] != eid):
            raise APIError('Diagnóstico inválido.', 403)
        if existing and (existing['revisions'] >= 32 or now - existing['updated_at'] < .3):
            raise APIError('Aguarde antes de enviar outro diagnóstico.', 429)
        if not existing and db().execute('SELECT COUNT(*) FROM playback_diagnostics WHERE user_id=? AND created_at>?',
                                         (g.user['id'], now - 3600)).fetchone()[0] >= 12:
            raise APIError('Limite de diagnósticos atingido. Tente mais tarde.', 429)
        # Keep only platform/version information, not the full user-agent or IP.
        ua = request.headers.get('User-Agent', '')
        family = next((p for p in ('iPhone', 'iPad', 'Android', 'Windows', 'Macintosh', 'Linux') if p in ua), 'Outro')
        versions = re.findall(r'(?:Version|Chrome|Firefox|OS)[/ ]([0-9._]{1,20})', ua)
        device = family + ' ' + ' / '.join(versions[:3])
        db().execute('''INSERT INTO playback_diagnostics VALUES(?,?,?,?,?,?,1,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,
                revisions=playback_diagnostics.revisions+1, trace=excluded.trace''',
                     (rid, g.user['id'], cid, eid, now, now, device,
                      urlsplit(url).hostname or 'local', hashlib.sha256(url.encode()).hexdigest()[:16], json.dumps(trace)))
        db().execute('DELETE FROM playback_diagnostics WHERE updated_at<?', (now - 7 * 86400,))
        db().execute('DELETE FROM playback_diagnostics WHERE id IN (SELECT id FROM playback_diagnostics ORDER BY updated_at DESC LIMIT -1 OFFSET 300)')
        db().commit()
        return jsonify(id=rid)

    @app.get('/api/admin/player-diagnostics')
    @auth(admin=True)
    def list_diagnostics():
        items = []
        for row in db().execute('''SELECT d.*, c.title FROM playback_diagnostics d
                                  LEFT JOIN content c ON c.id=d.content_id ORDER BY d.updated_at DESC LIMIT 30'''):
            item = dict(row)
            item['trace'] = json.loads(item['trace'])
            items.append(item)
        return jsonify(items=items)
