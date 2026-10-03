"""Direct in-site live creation, permissions, real RTC reception and cleanup."""
import json, os, sqlite3, sys, tempfile, threading, time
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler
H={'X-Requested-With':'VYRA'}
OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True)
def until(page, js, timeout=25):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if page.evaluate(js):return
        page.wait_for_timeout(150)
    raise AssertionError('Browser condition not met: '+js)
INSTRUMENT='''() => {
  window.deviceRequests=[];window.deviceStreams=[];window.connections=[];
  const get=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia=async c=>{
    window.deviceRequests.push(c);
    if(window.denyDevices)throw new DOMException('Denied for test','NotAllowedError');
    const s=await get(c);window.deviceStreams.push(s);
    if(window.delayDevices)await new Promise(resolve=>window.finishDevices=resolve);
    return s;
  };
  const Peer=window.RTCPeerConnection;
  window.RTCPeerConnection=class extends Peer{constructor(...a){super(...a);window.connections.push(this);}};
}'''
with tempfile.TemporaryDirectory() as folder:
    app=create_app(folder,testing=True)
    with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:
        db.execute("UPDATE users SET id=?,password=? WHERE role='admin'",(('z' if os.environ.get('LIVE_OFFERER','guest')=='guest' else '0')*24,generate_password_hash('Admin-browser-123')))
    server=make_server('127.0.0.1',8137,app,threaded=True,request_handler=QuietHandler)
    threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8137'
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
        hc=browser.new_context(viewport={'width':1440,'height':1000},permissions=['camera','microphone'])
        gc=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,permissions=['camera','microphone'])
        assert hc.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'}).ok
        aid=hc.request.get(url+'/api/bootstrap').json()['user']['id']
        r=hc.request.post(url+'/api/admin/users',headers=H,data={'name':'Luna Live','username':'lunalive','email':'live@example.com','password':'Community-123'});assert r.ok,r.text()
        assert gc.request.post(url+'/api/auth/login',headers=H,data={'email':'live@example.com','password':'Community-123'}).ok
        host=hc.new_page();guest=gc.new_page();errors=[]
        for page in (host,guest):page.on('pageerror',lambda e:errors.append(str(e)));page.add_init_script('('+INSTRUMENT+')()')
        try:
          host.goto(url+'/comunidade');host.locator('[data-sx=live-new]').first.click()
          expect(host.locator('#cs-room-live-note')).to_be_visible();expect(host.locator('#cs-room-source')).to_be_hidden()
          expect(host.locator('#cs-room [name=url]')).to_be_disabled();expect(host.get_by_role('button',name='Criar live',exact=True)).to_be_visible()
          # Switching from a media post must not smuggle its URL/post_id into a live.
          host.evaluate("() => CommunityStudio.roomEditor({kind:'watch',id:'stale-post',url:'https://example.com/old.mp4'})")
          expect(host.locator('#cs-room-source')).to_be_visible();expect(host.locator('#cs-room [name=url]')).to_have_attribute('required','')
          host.locator('#cs-room [name=intent][value=live]').check();expect(host.locator('#cs-room-source')).to_be_hidden()
          host.get_by_label('Nome da sala',exact=True).fill('Ao vivo com a comunidade')
          host.locator('#cs-room [name=approval]').uncheck()
          with host.expect_response(lambda r:r.url.endswith('/api/community/rooms') and r.request.method=='POST') as creation:
            host.get_by_role('button',name='Criar live',exact=True).click()
          created=creation.value;assert created.status==201,created.text()
          room=created.json()['room'];assert room['kind']=='live' and not room['url'] and not room['post_id'],room
          host.wait_for_url('**/comunidade/sala/*');roomurl=host.url
          expect(host.get_by_role('button',name='Iniciar transmissão',exact=True)).to_be_visible()
          assert host.evaluate('window.deviceRequests.length')==0
          assert host.evaluate("() => document.querySelector('.cm-theater').compareDocumentPosition(document.querySelector('#sx-room-games')) & Node.DOCUMENT_POSITION_FOLLOWING")
          expect(host.locator('[data-cm=room-add-queue]')).to_have_count(0)
          host.evaluate('window.denyDevices=true');host.get_by_role('button',name='Iniciar transmissão',exact=True).click()
          expect(host.locator('#cm-room-status')).to_contain_text('Permita o acesso à câmera e ao microfone')
          expect(host.get_by_role('button',name='Iniciar transmissão',exact=True)).to_be_enabled();expect(host.locator('#cm-live-badge')).to_have_text('PREPARANDO')
          assert host.evaluate('window.deviceStreams.length')==0
          host.evaluate('window.denyDevices=false')
          guest.goto(roomurl);expect(guest.locator('#cm-live-badge')).to_have_text('AGUARDANDO')
          expect(guest.locator('[data-cm=room-live]')).to_have_count(0);expect(guest.locator('[data-cm=room-mic]')).to_be_disabled();expect(guest.locator('[data-cm=room-camera]')).to_be_disabled()
          guest.get_by_role('button',name='Ativar áudio',exact=True).click()
          host.get_by_role('button',name='Iniciar transmissão',exact=True).click()
          expect(host.get_by_role('button',name='Parar transmissão',exact=True)).to_be_enabled()
          expect(host.locator('[data-cm=room-mic]')).to_have_attribute('aria-pressed','true');expect(host.locator('[data-cm=room-camera]')).to_have_attribute('aria-pressed','true')
          expect(host.locator('#cm-live-badge')).to_have_text('AO VIVO');expect(guest.locator('#cm-live-badge')).to_have_text('AO VIVO')
          until(guest,"() => [...document.querySelectorAll('#cm-camera-stage video')].some(v=>v.videoWidth>0 && v.currentTime>0)")
          until(guest,"async () => {for(const p of window.connections){if(p.connectionState!=='connected')continue;const stats=[...(await p.getStats()).values()];if(stats.some(s=>s.type==='inbound-rtp'&&s.kind==='audio'&&s.packetsReceived>0)&&stats.some(s=>s.type==='inbound-rtp'&&s.kind==='video'&&s.framesDecoded>0))return true;}return false;}")
          assert host.evaluate('window.deviceRequests.length')==2
          assert guest.evaluate('window.deviceRequests.length')==0
          assert host.evaluate('window.deviceStreams[0].getTracks().length')==2
          assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth')
          host.locator('.cm-theater').screenshot(path=str(OUT/'live-host-desktop.png'));guest.locator('.cm-theater').screenshot(path=str(OUT/'live-viewer-mobile.png'))
          # Chat remains inside the video stage, without device access for viewers.
          guest.locator('.cm-stage-controls [data-cm=room-chat]').click();guest.locator('#cm-room-message [name=body]').fill('Estamos ao vivo! 🎬');guest.locator('#cm-room-message [type=submit]').click()
          expect(host.locator('#cm-bubbles')).to_contain_text('Estamos ao vivo!')
          host.get_by_role('button',name='Parar transmissão',exact=True).click()
          until(host,"() => window.deviceStreams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
          expect(guest.locator('#cm-camera-stage video')).to_have_count(0);expect(guest.locator('#cm-live-badge')).to_have_text('AGUARDANDO')
          expect(host.get_by_role('button',name='Iniciar transmissão',exact=True)).to_be_visible()
          host.set_viewport_size({'width':390,'height':844})
          host.get_by_role('button',name='Iniciar transmissão',exact=True).click()
          expect(host.get_by_role('button',name='Parar transmissão',exact=True)).to_be_enabled()
          assert host.evaluate('document.documentElement.scrollWidth<=innerWidth')
          host.locator('.cm-theater').screenshot(path=str(OUT/'live-host-mobile.png'))
          until(guest,"() => [...document.querySelectorAll('#cm-camera-stage video')].some(v=>v.videoWidth>0 && v.currentTime>0)")
          host.get_by_role('button',name='Parar transmissão',exact=True).click()
          # A pending permission result must be stopped when its room was left.
          host.evaluate('window.delayDevices=true');host.get_by_role('button',name='Iniciar transmissão',exact=True).click()
          until(host,'() => !!window.finishDevices')
          host.get_by_role('link',name='Todas as salas',exact=True).click();host.wait_for_url('**/comunidade?tab=rooms')
          host.evaluate('window.finishDevices()')
          until(host,"() => window.deviceStreams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
          assert not errors,errors
          print(json.dumps({'create_live_without_url':True,'stale_media_cleared':True,'explicit_device_permission':True,'denial_recoverable':True,'camera_and_audio_received':True,'viewer_publish_disabled':True,'chat':True,'stop_restart':True,'pending_permission_cleanup':True,'mobile_no_overflow':True,'page_errors':errors}))
        except Exception:
          for name,page in [('host',host),('guest',guest)]:
            try:page.screenshot(path=str(OUT/f'live-failure-{name}.png'),full_page=True)
            except Exception:pass
          raise
        finally:browser.close()
    finally:server.shutdown()
