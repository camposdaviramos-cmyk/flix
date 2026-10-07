"""Brand migration preserves account and integration compatibility."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app


class WorkTVTests(unittest.TestCase):
    def test_brand_metadata_and_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            client = create_app(folder, testing=True).test_client()
            self.assertEqual(client.get('/api/bootstrap').json['brand'], 'WorkTV')
            home = client.get('/').text
            self.assertIn('og:site_name" content="WorkTV"', home)
            with client.get('/manifest.webmanifest') as response:
                manifest = json.loads(response.text)
            self.assertEqual(manifest['short_name'], 'WorkTV')
            for icon in manifest['icons']:
                with client.get(icon['src']) as response:
                    self.assertEqual(response.status_code, 200)

    def test_legacy_brand_migration_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            create_app(folder, testing=True)
            with sqlite3.connect(Path(folder) / 'vyra.sqlite3') as db:
                db.execute("UPDATE settings SET value='Flix' WHERE key='brand'")
                db.execute("INSERT OR REPLACE INTO settings VALUES('support_email','support@example.com')")
                accounts = db.execute('SELECT id,email FROM users').fetchall()
                db.execute('DROP TRIGGER hub_jump_request')
                db.execute("CREATE TRIGGER hub_jump_request AFTER INSERT ON jump_requests BEGIN SELECT 'FlixJump'; END")
            client = create_app(folder, testing=True).test_client()
            self.assertEqual(client.get('/api/bootstrap').json['brand'], 'WorkTV')
            self.assertEqual(client.get('/api/bootstrap').json['support_email'], 'support@example.com')
            with sqlite3.connect(Path(folder) / 'vyra.sqlite3') as db:
                self.assertEqual(db.execute('SELECT id,email FROM users').fetchall(), accounts)
                trigger = db.execute("SELECT sql FROM sqlite_master WHERE name='hub_jump_request'").fetchone()[0]
                self.assertIn('WorkTV Juntos', trigger)
                self.assertNotIn('FlixJump', trigger)
                db.execute("UPDATE settings SET value='Marca personalizada' WHERE key='brand'")
            client = create_app(folder, testing=True).test_client()
            self.assertEqual(client.get('/api/bootstrap').json['brand'], 'Marca personalizada')


if __name__ == '__main__':
    unittest.main()
