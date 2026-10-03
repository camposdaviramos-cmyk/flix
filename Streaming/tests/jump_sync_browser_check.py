"""Real media sync with autoplay restrictions, slow voice config, and voice ducking."""
import json
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler


def run():
    with tempfile.TemporaryDirectory() as folder:
        app=create_app(folder,testing=True)
        with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:
            db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
            # Deterministic local episode; exercise the actual series path, not a mock player.
            db.execute("UPDATE episodes SET video_url='/static/assets/sintel-trailer.mp4' WHERE content_id='neon'")
        server=make_server('127.0.0.1',8131,app,threaded=True,request_handler=QuietHandler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        url='http://localhost:8131';headers={'X-Requested-With':'VYRA'};output=ROOT/'test-results'
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--autoplay-policy=document-user-activation-required'])
                host_ctx=browser.new_context(bypass_csp=True,viewport={'width':1440,'height':1000})
                host_ctx.request.post(url+'/api/auth/login',data={'email':'admin@vyra.local','password':'Admin-browser-123'},headers=headers)
                r=host_ctx.request.post(url+'/api/admin/users',data={'name':'Convidado Sync','username':'syncguest','email':'sync@example.com','password':'Customer-test-123','plan_id':'premium'},headers=headers)
                assert r.status==201,r.text()
                uid=r.json()['user']['id']
                guest_ctx=browser.new_context(bypass_csp=True,viewport={'width':390,'height':844})
                guest_ctx.request.post(url+'/api/auth/login',data={'email':'sync@example.com','password':'Customer-test-123'},headers=headers)
                # Playwright's evaluations can themselves grant browser activation.
                # Inject the browser's NotAllowedError until a real trusted button click
                # to exercise the blocked-autoplay path deterministically.
                guest_ctx.add_init_script("""(() => {
                    const nativePlay=HTMLMediaElement.prototype.play;let allowed=false;
                    document.addEventListener('click',e=>{if(e.isTrusted&&e.target.closest('[data-jump="enable-playback"],[data-jump="toggle"]'))allowed=true;},true);
                    HTMLMediaElement.prototype.play=function(){
                        if(this.id==='video-player'&&!allowed)return Promise.reject(new DOMException('User gesture required','NotAllowedError'));
                        return nativePlay.call(this);
                    };
                })();""")
                host=host_ctx.new_page();guest=guest_ctx.new_page();errors=[]
                for tab in [host,guest]:tab.on('pageerror',lambda e:errors.append(str(e)))
                # Hold config forever until explicitly released: playback must still work.
                held=[]
                guest.route('**/api/jump/config',lambda route:held.append(route))
                host.goto(url)
                host.get_by_role('button',name='FlixJump e amigos').wait_for()
                host.evaluate("play('neon')")
                host.wait_for_function('player?.ready')
                host.evaluate('player.video.pause();player.video.currentTime=20')
                host.wait_for_function('!player.video.seeking')
                host.get_by_role('button',name='Criar sala FlixJump',exact=True).click()
                host.get_by_label('Link de convite da sala',exact=True).wait_for()
                rid=host.evaluate('player.jump.id')
                host.get_by_role('button',name='Fechar painel',exact=True).click()
                # Unrelated saved progress must not override the room's episode position.
                eid=host.evaluate('player.episode')
                guest_ctx.request.put(url+'/api/progress/neon',data={'episode_id':eid,'position':3,'duration':52,'client_time':time.time()*1000},headers=headers)
                guest.goto(url+'/sala/'+rid)
                guest.get_by_text('Aguardando o anfitrião',exact=True).wait_for()
                host.locator('.fj-entry-notice').get_by_role('button',name='Aceitar',exact=True).click()
                guest.wait_for_function('player?.ready && player.video.paused && Math.abs(player.video.currentTime-20)<.15')
                assert held,'Voice config should be held during sync checks'
                assert guest.evaluate('player.episode')==eid
                # The first host play is delivered without waiting for voice initialization.
                host.get_by_role('button',name='Reproduzir',exact=True).click()
                guest.get_by_role('button',name='Acompanhar sala',exact=True).wait_for()
                guest.screenshot(path=str(output/'flixjump-sync-authorize-mobile.png'))
                host.wait_for_function('player.video.currentTime>21')
                guest.get_by_role('button',name='Acompanhar sala',exact=True).click()
                guest.wait_for_function('!player.video.paused && player.video.currentTime>21')
                drift=abs(host.evaluate('player.video.currentTime')-guest.evaluate('player.video.currentTime'))
                assert drift<.65,drift
                # Pause and seek must land at the same frame even after an earlier block.
                host.evaluate('player.video.pause();player.video.currentTime=32.25')
                guest.wait_for_function('player.video.paused && Math.abs(player.video.currentTime-32.25)<.08')
                host.get_by_role('button',name='Reproduzir',exact=True).click()
                guest.wait_for_function('!player.video.paused && player.video.currentTime>32.3')
                assert guest.locator('.fj-playback-gate').is_hidden()
                host.evaluate('player.video.pause();player.video.currentTime=10')
                guest.wait_for_function('player.video.paused && Math.abs(player.video.currentTime-10)<.08')
                # A stale host revision must refresh from the server and retry the latest
                # command, instead of replaying a conflict forever.
                with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:
                    db.execute('UPDATE jump_rooms SET revision=revision+1 WHERE id=?',(rid,))
                host.evaluate('player.video.currentTime=12.5')
                guest.wait_for_function('player.video.paused && Math.abs(player.video.currentTime-12.5)<.08')
                host.evaluate('player.video.currentTime=10')
                guest.wait_for_function('player.video.paused && Math.abs(player.video.currentTime-10)<.08')
                # Opening panels must not reset the clock snapshot or send guests backwards.
                guest.get_by_role('button',name='Fechar painel',exact=True).click()
                guest.get_by_role('button',name='FlixJump · Assistir com amigos',exact=True).click()
                assert abs(guest.evaluate('player.video.currentTime')-10)<.08
                guest.get_by_role('button',name='Fechar painel',exact=True).click()
                for route in held:route.fulfill(status=200,content_type='application/json',body=json.dumps({'ice_servers':[],'max_members':8}))
                guest.unroute('**/api/jump/config')
                host.wait_for_function("[...player.peers.values()].some(p=>p.pc.connectionState==='connected')",timeout=30000)
                # Use an actual audio source transmitted over WebRTC; silence is controlled
                # at source, so mic-on alone cannot satisfy the ducking assertions.
                host.evaluate('''async()=>{
                    window.testVoiceContext=new AudioContext();await testVoiceContext.resume();
                    window.testTone=testVoiceContext.createOscillator();testTone.frequency.value=220;
                    window.testLevel=testVoiceContext.createGain();testLevel.gain.value=0;
                    window.testDestination=testVoiceContext.createMediaStreamDestination();
                    testTone.connect(testLevel);testLevel.connect(testDestination);testTone.start();
                    await [...player.peers.values()][0].sender.replaceTrack(testDestination.stream.getAudioTracks()[0]);
                }''')
                guest.wait_for_function("[...player.peers.values()].some(p=>p.audio.srcObject?.getAudioTracks().length)")
                guest.locator('.fj-volume-range').evaluate("e=>{e.value=.8;e.dispatchEvent(new Event('input',{bubbles:true}));}")
                # Click synchronously resumes the suspended analyser on browsers requiring it.
                guest.get_by_role('button',name='Sincronizar com a sala',exact=True).click()
                guest.wait_for_function("player.voiceContext?.state==='running'")
                assert guest.evaluate('player.ducking') is False
                host.evaluate('testLevel.gain.value=.35')
                guest.wait_for_function('player.ducking && Math.abs(player.video.volume-.144)<.01',timeout=10000)
                assert guest.evaluate('[...player.peers.values()][0].audio.volume')==1
                guest.locator('.fj-volume-range').evaluate("e=>{e.value=.5;e.dispatchEvent(new Event('input',{bubbles:true}));}")
                guest.wait_for_function('Math.abs(player.video.volume-.09)<.01')
                guest.screenshot(path=str(output/'flixjump-voice-priority-mobile.png'))
                host.evaluate('testLevel.gain.value=0')
                guest.wait_for_function('!player.ducking && Math.abs(player.video.volume-.5)<.01',timeout=5000)
                guest.get_by_role('button',name='Silenciar vídeo',exact=True).click()
                host.evaluate('testLevel.gain.value=.35')
                guest.wait_for_function('player.ducking')
                host.evaluate('testLevel.gain.value=0')
                guest.wait_for_function('!player.ducking')
                assert guest.evaluate('player.video.muted') is True
                # A second play after voice activity is still synchronized.
                host.get_by_role('button',name='Reproduzir',exact=True).click()
                guest.wait_for_function('!player.video.paused && player.video.currentTime>10.3')
                drift=abs(host.evaluate('player.video.currentTime')-guest.evaluate('player.video.currentTime'))
                assert drift<.65,drift
                host.evaluate('testLevel.gain.value=.35')
                guest.wait_for_function('player.ducking')
                guest.get_by_role('button',name='FlixJump · Assistir com amigos',exact=True).click()
                guest.get_by_role('button',name='Sair da sala',exact=True).click()
                guest.wait_for_function('!player.jump && !player.ducking && !player.voiceContext && player.peers.size===0')
                assert abs(guest.evaluate('player.video.volume')-.5)<.01
                assert guest.evaluate('player.video.muted') is True
                # Rejoining a running episode starts at the host, never the saved/local
                # position (the previous play promise and analyser have been disposed).
                guest.get_by_role('button',name='Fechar',exact=True).click()
                host.evaluate('player.video.pause();player.video.currentTime=18')
                host.wait_for_function('!player.video.seeking')
                host.get_by_role('button',name='Reproduzir',exact=True).click()
                guest.goto(url+'/sala/'+rid)
                host.locator('.fj-entry-notice').get_by_role('button',name='Aceitar',exact=True).click()
                guest.get_by_role('button',name='Acompanhar sala',exact=True).wait_for()
                guest.get_by_role('button',name='Acompanhar sala',exact=True).click()
                guest.wait_for_function('!player.video.paused && player.video.currentTime>18')
                late_drift=abs(host.evaluate('player.video.currentTime')-guest.evaluate('player.video.currentTime'))
                assert late_drift<.65,late_drift
                assert not errors,errors
                print(json.dumps({'ok':True,'drift_seconds':round(drift,3),'checks':['series join at host position instead of saved progress','sync independent of blocked voice setup','simulated autoplay rejection and real-click recovery','host pause seek resume','revision conflict recovery','rejoin during playback','voice received via WebRTC reduces movie to 18%','silence restores user volume','mute preserved','room exit cleans audio resources']},ensure_ascii=False))
                browser.close()
        finally:server.shutdown()

if __name__=='__main__':run()
