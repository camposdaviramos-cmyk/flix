"""Real HLS playback after native startup rejection (Chromium, not an iPhone).

Requires ffmpeg on PATH or FFMPEG_BINARY. Media is generated from our local
Sintel sample, so the test does not depend on a third-party stream.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from flask import send_from_directory, request
from playwright.sync_api import sync_playwright
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler


def run():
    ffmpeg = os.environ.get('FFMPEG_BINARY') or shutil.which('ffmpeg')
    assert ffmpeg, 'Set FFMPEG_BINARY to generate the local HLS fixture.'
    with tempfile.TemporaryDirectory() as folder:
        media = Path(folder) / 'media'
        media.mkdir()
        subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-i',
                        str(ROOT / 'static/assets/sintel-trailer.mp4'), '-t', '12',
                        '-c', 'copy', '-hls_time', '2', '-hls_playlist_type', 'vod',
                        str(media / 'index.m3u8')], check=True)
        app = create_app(folder, testing=True)
        app.add_url_rule('/_media-test/<path:name>', 'test_media',
                         lambda name: send_from_directory(media, name))
        source_requests = []
        def denied_source():
            source_requests.append(request.headers.get('Sec-Fetch-Mode'))
            return '<html>Unavailable</html>', 404
        app.add_url_rule('/_media-denied.m3u8', 'denied_source', denied_source)
        with sqlite3.connect(Path(folder) / 'vyra.sqlite3') as db:
            db.execute("UPDATE users SET password=? WHERE role='admin'",
                       (generate_password_hash('Admin-browser-123'),))
            db.execute("UPDATE episodes SET video_url='/_media-test/index.m3u8' WHERE content_id='neon'")
            db.execute('INSERT INTO settings VALUES(?,?)', ('player_diagnostic_window', json.dumps({'content_id':'neon','until':time.time()+3600})))
            eid = db.execute("SELECT id FROM episodes WHERE content_id='neon' ORDER BY season,number LIMIT 1").fetchone()[0]
        server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=QuietHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = 'http://localhost:' + str(server.server_port)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',
                    headless=True, args=['--no-sandbox', '--autoplay-policy=no-user-gesture-required'])
                context = browser.new_context(bypass_csp=True)
                context.request.post(url + '/api/auth/login',
                                     data={'email': 'admin@vyra.local', 'password': 'Admin-browser-123'},
                                     headers={'X-Requested-With': 'VYRA'})
                context.request.put(url + '/api/progress/neon',
                                    data={'episode_id': eid, 'position': 5, 'duration': 52, 'client_time': time.time()*1000},
                                    headers={'X-Requested-With': 'VYRA'})
                # Exercise our Apple-native selection without claiming iOS emulation.
                context.add_init_script("""(() => {
                    Object.defineProperty(navigator, 'vendor', {get: () => 'Apple Computer, Inc.'});
                    const canPlay = HTMLMediaElement.prototype.canPlayType;
                    HTMLMediaElement.prototype.canPlayType = function(type) {
                        return type === 'application/vnd.apple.mpegurl' ? 'maybe' : canPlay.call(this, type);
                    };
                })();""")
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                # Native startup rejects this response. hls.js then fetches the
                # very same URL successfully and transmuxes real MPEG-TS segments.
                attempts = []
                def manifest(route):
                    attempts.append(route.request.resource_type)
                    if len(attempts) == 1:
                        route.fulfill(status=200, content_type='text/html', body='<html>Invalid media response</html>')
                    else:
                        route.continue_()
                page.route('**/_media-test/index.m3u8', manifest)
                page.goto(url + '/titulo/neon')
                assert 'player_debug' not in page.url
                page.wait_for_function('state.user !== null')
                page.evaluate("play('neon')")
                page.wait_for_function("player?.mediaSource?.mode === 'hlsjs' && !player.video.paused && player.video.currentTime > 6")
                assert len(attempts) == 2, attempts
                page.wait_for_function("document.querySelector('#player-diagnostic-status')?.textContent.startsWith('Diagnóstico registrado')")
                reports = context.request.get(url + '/api/admin/player-diagnostics').json()['items']
                assert reports, 'Trace must be received by authenticated endpoint'
                events = [e['event'] for e in reports[0]['trace']['events']]
                assert 'native-error' in events and 'fallback' in events and 'manifest' in events, events
                assert '/_media-test/' not in json.dumps(reports[0]['trace'])
                assert page.locator('.player-status').inner_text() == ''
                page.get_by_role('button', name='Pausar', exact=True).click()
                page.wait_for_function('player.video.paused')
                page.get_by_role('button', name='Reproduzir', exact=True).click()
                page.wait_for_function('!player.video.paused && player.video.currentTime > 2')
                page.evaluate('closeModal()')
                assert page.evaluate('player === null')
                # Source denial must survive the later generic native play error.
                page.unroute('**/_media-test/index.m3u8', manifest)
                page.route('**/_media-test/index.m3u8', lambda r: r.fulfill(status=403, body='Denied'))
                page.evaluate("play('neon')")
                page.wait_for_function("document.querySelector('.player-status')?.textContent.includes('recusou')")
                page.get_by_role('button', name='Reproduzir', exact=True).click()
                page.wait_for_timeout(300)
                assert 'recusou' in page.locator('.player-status').inner_text()
                page.evaluate('closeModal()')
                # Reproduce the iPhone trace: native failure, then an unreadable
                # cross-origin response. Opaque HTTP must not be called playable.
                source_url = url.replace('localhost', '127.0.0.1') + '/_media-denied.m3u8'
                with sqlite3.connect(Path(folder) / 'vyra.sqlite3') as db:
                    db.execute("UPDATE episodes SET video_url=? WHERE content_id='neon'", (source_url,))
                page.evaluate("play('neon')")
                page.wait_for_function("document.querySelector('.player-status')?.textContent.includes('Não foi possível baixar')")
                page.wait_for_timeout(1600)
                reports = context.request.get(url + '/api/admin/player-diagnostics').json()['items']
                probes = [e for e in reports[0]['trace']['events'] if e['event'] == 'source-probe']
                assert len(probes) == 2, reports[0]['trace']
                opaque = next(e for e in probes if e['probeMode'] == 'no-cors')
                assert opaque['reachable'] and opaque['responseType'] == 'opaque' and opaque['httpStatus'] == 0, opaque
                assert not next(e for e in probes if e['probeMode'] == 'cors')['reachable'], probes
                assert len(source_requests) == 4, source_requests  # native, hls.js, two probes
                direct = page.get_by_role('link', name='Abrir fonte diretamente')
                assert direct.get_attribute('href') == source_url
                assert direct.get_attribute('rel') == 'noopener noreferrer'
                assert not errors, errors
                browser.close()
                print(json.dumps({'ok': True, 'real_hls_after_native_failure': True, 'diagnostic_without_query': True,
                                  'manifest_attempts': attempts, 'browser_errors': errors}))
        finally:
            server.shutdown()


if __name__ == '__main__':
    run()
