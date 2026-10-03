import json
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import create_app
from playback_diagnostics import clean_trace


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(self.tmp.name, testing=True)
        self.client = self.app.test_client()
        self.db = sqlite3.connect(Path(self.tmp.name) / 'vyra.sqlite3')
        self.db.execute("UPDATE users SET password=? WHERE role='admin'", (generate_password_hash('Test-password-123'),))
        self.db.commit()
        self.headers = {'X-Requested-With': 'VYRA', 'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7) Version/27.0 Safari/604.1'}
        self.payload = {'id': 'a' * 32, 'content_id': 'horizonte', 'episode_id': '', 'trace': {
            'capabilities': {'mms': True, 'nativeHls': True},
            'events': [{'event': 'hls-error', 'httpStatus': 403, 'detail': 'manifestLoadError', 'mode': 'hlsjs'}]}}

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def login(self):
        return self.client.post('/api/auth/login', json={'email': 'admin@vyra.local', 'password': 'Test-password-123'}, headers=self.headers)

    def send(self, payload=None):
        return self.client.post('/api/player/diagnostics', json=payload or self.payload, headers=self.headers)

    def test_requires_authorized_account_and_valid_content(self):
        self.assertEqual(self.send().status_code, 401)
        self.assertEqual(self.client.get('/api/admin/player-diagnostics').status_code, 401)
        self.login()
        self.assertEqual(self.client.post('/api/player/diagnostics', json=self.payload).status_code, 403)
        self.assertEqual(self.send({**self.payload, 'content_id': 'missing'}).status_code, 404)
        self.assertEqual(self.send({**self.payload, 'id': 'invalid'}).status_code, 400)

    def test_trace_is_retrievable_and_bounded(self):
        self.login()
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.send().status_code, 429)
        item = self.client.get('/api/admin/player-diagnostics').json['items'][0]
        self.assertEqual(item['trace']['events'][0]['httpStatus'], 403)
        self.assertEqual(item['device'], 'iPhone 18_7 / 27.0')
        self.assertNotIn('url', item)
        self.db.execute('UPDATE playback_diagnostics SET updated_at=0,revisions=31')
        self.db.commit()
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.send().status_code, 429)

    def test_rejects_cross_user_updates_and_nonadmin_reading(self):
        self.login()
        self.send()
        other = self.app.test_client()
        r = other.post('/api/auth/register', json={'name': 'Teste Dois', 'username': 'diagtest',
                        'email': 'test@example.com', 'password': 'Test-password-123', 'account_type': 'community'}, headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(other.get('/api/admin/player-diagnostics').status_code, 403)
        self.assertEqual(other.post('/api/player/diagnostics', json=self.payload, headers=self.headers).status_code, 402)
        self.db.execute('UPDATE users SET expires_at=9999999999 WHERE email=?', ('test@example.com',))
        self.db.commit()
        self.assertEqual(other.post('/api/player/diagnostics', json=self.payload, headers=self.headers).status_code, 403)

    def test_discards_urls_bodies_secrets_and_nonfinite_numbers(self):
        raw = {'events': [{'event': 'native-error', 'mediaCode': 4, 'position': float('nan'),
                          'url': 'https://example.com/file?t=secret', 'body': 'secret',
                          'detail': 'https://example.com/file?t=secret', 'mime': 'text/html'}] * 45,
               'capabilities': {'mms': True, 'token': 'secret'}, 'url': 'secret'}
        clean = clean_trace(raw)
        self.assertEqual(len(clean['events']), 40)
        self.assertNotIn('secret', json.dumps(clean))
        self.assertNotIn('position', clean['events'][0])
        self.assertEqual(clean['events'][0]['mime'], 'text/html')

    def test_temporary_diagnostics_without_query_parameter(self):
        self.login()
        self.assertFalse(self.client.get('/api/play/horizonte').json['diagnostic'])
        self.db.execute('INSERT INTO settings VALUES(?,?)', ('player_diagnostic_window',
                        json.dumps({'content_id': 'horizonte', 'until': time.time() + 3600})))
        self.db.commit()
        self.assertTrue(self.client.get('/api/play/horizonte').json['diagnostic'])
        other = self.db.execute("SELECT id FROM content WHERE id!='horizonte' AND kind='movie' LIMIT 1").fetchone()[0]
        self.assertFalse(self.client.get('/api/play/' + other).json['diagnostic'])
        for value in ['invalid', 'null', '[]', json.dumps({'content_id': 'horizonte', 'until': 1})]:
            self.db.execute("UPDATE settings SET value=? WHERE key='player_diagnostic_window'", (value,))
            self.db.commit()
            self.assertFalse(self.client.get('/api/play/horizonte').json['diagnostic'])

    def test_network_probe_retains_only_safe_fields(self):
        clean = clean_trace({'build': 'diagnostic3', 'events': [{'event': 'source-probe',
                            'probeMode': 'no-cors', 'reachable': True, 'responseType': 'opaque',
                            'httpStatus': 0, 'url': 'https://source.test/secret?t=token'}]})
        self.assertEqual(clean['build'], 'diagnostic3')
        self.assertEqual(clean['events'][0], {'event': 'source-probe', 'probeMode': 'no-cors',
                        'reachable': True, 'responseType': 'opaque', 'httpStatus': 0})

    def test_temporary_diagnostics_do_not_collect_from_customers(self):
        self.client.post('/api/auth/register', json={'name': 'Teste Cliente', 'username': 'diagcustomer',
                         'email': 'customer@example.com', 'password': 'Test-password-123', 'account_type': 'community'}, headers=self.headers)
        self.db.execute('UPDATE users SET expires_at=9999999999 WHERE email=?', ('customer@example.com',))
        self.db.execute('INSERT INTO settings VALUES(?,?)', ('player_diagnostic_window',
                        json.dumps({'content_id': 'horizonte', 'until': time.time() + 3600})))
        self.db.commit()
        self.assertFalse(self.client.get('/api/play/horizonte').json['diagnostic'])


if __name__ == '__main__':
    unittest.main()
