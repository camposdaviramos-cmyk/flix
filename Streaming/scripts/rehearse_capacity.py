"""Small k6 rehearsal with disposable sessions/database and localhost only.
Not a production load generator. Requires an independently installed k6 binary.
"""
import argparse, hashlib, json, os, secrets, sqlite3, subprocess, sys, tempfile, threading, time
from pathlib import Path
from waitress import create_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import create_app

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--k6', default='k6')
parser.add_argument('--users', type=int, default=8)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if not 4 <= args.users <= 32:
    parser.error('Local rehearsal is limited to 4..32 users.')
args.output = args.output.resolve()
args.output.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='worktv-load-') as folder:
    app = create_app(folder, testing=True)
    identity = secrets.token_urlsafe(24)
    @app.get('/__loadtest__/identity')
    def load_identity():
        return identity
    now = time.time()
    accounts = []
    with sqlite3.connect(Path(folder) / 'vyra.sqlite3') as db:
        db.execute('INSERT INTO content(id,title,kind,published,video_url,created_at) VALUES(?,?,?,?,?,?)',
                   ('load-only-film', 'Disposable load fixture', 'movie', 1, 'https://example.invalid/not-downloaded.mp4', now))
        for n in range(args.users):
            uid, token = secrets.token_hex(16), secrets.token_urlsafe(32)
            db.execute('INSERT INTO users(id,name,email,password,expires_at,created_at,username) VALUES(?,?,?,?,?,?,?)',
                       (uid, f'Load {n}', f'load{n}@example.invalid', '!login-disabled', now + 3600, now, f'load{n}'))
            db.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), uid, now + 3600))
            accounts.append({'token': token, 'content_id': 'load-only-film'})
    fixture = Path(folder) / 'sessions.json'
    fixture.write_text(json.dumps({'identity': identity, 'accounts': accounts}))
    fixture.chmod(0o600)
    server = create_server(app, host='127.0.0.1', port=0, threads=8)
    threading.Thread(target=server.run, daemon=True).start()
    try:
        env = {**os.environ, 'BASE_URL': f'http://127.0.0.1:{server.effective_port}',
               'FIXTURE_FILE': str(fixture), 'VUS': str(args.users), 'RAMP': '3s', 'HOLD': '16s'}
        result = subprocess.run([args.k6, 'run', '--quiet', '--summary-export', str(args.output),
                                 str(ROOT / 'tests/load/capacity.js')], env=env, timeout=90)
    finally:
        server.close()
sys.exit(result.returncode)
