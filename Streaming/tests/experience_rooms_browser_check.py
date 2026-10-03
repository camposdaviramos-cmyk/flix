"""Four WebRTC cameras, player geometry and room controls inside the game."""
import json,sqlite3,sys,tempfile,threading,time
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler
H={'X-Requested-With':'Flix'};OUT=ROOT/'test-results'
def until(p,expression,timeout=30000):
    end=time.monotonic()+timeout/1000
    while time.monotonic()<end:
        if p.evaluate('() => ('+expression+')'):return
        p.wait_for_timeout(200)
    raise AssertionError(expression)
with tempfile.TemporaryDirectory() as folder:
    app=create_app(folder,testing=True)
    with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:
        db.execute("UPDATE users SET password=?,name='Theo Almeida' WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
        db.execute("UPDATE content SET video_url='/static/assets/sintel-trailer.mp4' WHERE id='horizonte'")
    server=make_server('127.0.0.1',8140,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8140'
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
        contexts=[];pages=[];uids=[];errors=[]
        for i in range(4):
            c=browser.new_context(viewport={'width':1440 if i==0 else 390,'height':1000 if i==0 else 844},permissions=['microphone','camera']);contexts.append(c)
            if i==0:
                assert c.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'}).ok
                uids.append(c.request.get(url+'/api/bootstrap').json()['user']['id'])
            else:
                user={'name':'Pessoa '+str(i),'username':'pessoa'+str(i),'email':'pessoa'+str(i)+'@example.com','password':'Community-123','plan_id':'premium'};r=contexts[0].request.post(url+'/api/admin/users',headers=H,data=user);assert r.ok,r.text();uids.append(r.json()['user']['id']);assert c.request.post(url+'/api/auth/login',headers=H,data={'email':user['email'],'password':user['password']}).ok
            p=c.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.add_init_script("window.streams=[];window.rtc=[];const NativePC=RTCPeerConnection;window.RTCPeerConnection=class extends NativePC{constructor(...a){super(...a);rtc.push(this)}};const nativeMedia=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async c=>{const s=await nativeMedia(c);streams.push(s);return s;}");pages.append(p)
        host,guest,third,fourth=pages
        try:
            r=contexts[0].request.post(url+'/api/jump/rooms',headers=H,data={'content_id':'horizonte','position':8,'paused':True});assert r.ok,r.text();rid=r.json()['room']['id'];path=url+'/api/jump/rooms/'+rid
            for i in range(1,4):
                contexts[i].request.post(path+'/join',headers=H,data={});contexts[0].request.patch(path+'/requests/'+uids[i],headers=H,data={'decision':'approve'});assert contexts[i].request.post(path+'/join',headers=H,data={}).ok
            for p in pages:p.goto(url+'/sala/'+rid);until(p,'player?.ready && player.voiceReady');p.get_by_role('button',name='Fechar painel',exact=True).click();p.locator('[data-jump=camera]').click()
            for p in pages:
                until(p,"document.querySelectorAll('.fj-camera-rail video').length===4 && [...document.querySelectorAll('.fj-camera-rail video')].every(v=>v.videoWidth>0)",timeout=40000)
                assert p.evaluate("Math.abs(document.querySelector('.fj-camera-rail').getBoundingClientRect().height-document.querySelector('.video-wrap').getBoundingClientRect().height)<3")
                assert p.evaluate("document.querySelector('.fj-camera-rail').getBoundingClientRect().bottom<=document.querySelector('.video-wrap').getBoundingClientRect().bottom+1")
            host.screenshot(path=str(OUT/'experience-jump-four-cameras-desktop.png'));guest.screenshot(path=str(OUT/'experience-jump-four-cameras-mobile.png'))
            fourth.locator('[data-jump=camera]').click();expect(host.locator('.fj-camera-rail video')).to_have_count(3,timeout=15000)
            for p in pages:p.goto(url+'/comunidade');until(p,"streams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
            r=contexts[0].request.post(url+'/api/community/rooms',headers=H,data={'kind':'watch','title':'Sessão em grupo','url':'https://media.example.test/video.mp4','approval':False});assert r.ok,r.text();rid=r.json()['room']['id'];roompath=url+'/api/community/rooms/'+rid
            for p in pages[:3]:
                p.route('https://media.example.test/**',lambda route:route.fulfill(path=str(ROOT/'static/assets/sintel-trailer.mp4'),content_type='video/mp4',headers={'Access-Control-Allow-Origin':'*'}));p.goto(url+'/comunidade/sala/'+rid);p.get_by_role('button',name='Ativar câmera',exact=True).click()
            for p in pages[:3]:until(p,"document.querySelectorAll('#cm-camera-stage video').length===3&&[...document.querySelectorAll('#cm-camera-stage video')].every(v=>v.videoWidth>0)",timeout=40000)
            host.screenshot(path=str(OUT/'experience-community-cameras-desktop.png'));guest.screenshot(path=str(OUT/'experience-community-cameras-mobile.png'))
            # The two audience members exchange camera tracks directly without receiving a microphone seat.
            members=contexts[1].request.post(roompath+'/poll',headers=H,data={'camera':True}).json()['room']['members'];assert next(m for m in members if m['id']==uids[1])['seat'] is None
            for p in pages[:3]:p.get_by_role('button',name='Desligar câmera',exact=True).click()
            host.locator('[data-game=create][data-kind=colors]').click();guest.get_by_role('button',name='Aceitar e jogar',exact=True).click();expect(host.locator('.fg-player')).to_have_count(2);host.get_by_role('button',name='Iniciar partida',exact=False).click();expect(host.locator('.fg-hand .fg-card')).to_have_count(7)
            expect(host.locator('.cm-room-heading')).not_to_be_visible();expect(host.locator('.cx-room-widget>summary')).to_be_visible();host.locator('.cx-room-widget>summary').click();expect(host.locator('.cx-room-widget #cm-seats')).to_be_visible();host.locator(f'[data-audience="{uids[1]}"] [data-cm=room-promote]').click();expect(guest.locator('[data-game=mic]')).to_be_enabled(timeout=15000);host.locator('[data-cm=room-widget-close]').click()
            # A request opens the compact widget without leaving the game.
            contexts[0].request.patch(roompath,headers=H,data={'title':'Sessão em grupo','description':'','approval':True});fourth.goto(url+'/comunidade/sala/'+rid);expect(fourth.locator('#cm-admission-status')).to_contain_text('Aguardando o anfitrião');expect(host.locator('.cx-room-widget')).to_have_attribute('open','',timeout=15000);expect(host.locator('.cx-room-widget [data-cm=room-approve]')).to_be_visible();host.locator('.cx-room-widget [data-cm=room-approve]').click();host.locator('[data-cm=room-widget-close]').click()
            guest.get_by_role('button',name='Chat dentro do jogo',exact=True).click();guest.get_by_label('Mensagem no jogo',exact=True).fill('Todo mundo junto 🎮');guest.get_by_role('button',name='Enviar mensagem no jogo',exact=True).click();expect(host.locator('.fg-bubble')).to_contain_text('Todo mundo junto',timeout=15000)
            host.screenshot(path=str(OUT/'experience-game-widget-desktop.png'));guest.screenshot(path=str(OUT/'experience-game-widget-mobile.png'));assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert not errors,errors
            print(json.dumps({'four_real_jump_cameras':True,'full_height_camera_rail':True,'camera_cleanup':True,'community_audience_cameras':True,'game_seats_widget':True,'game_requests_widget':True,'game_chat':True,'page_errors':errors}))
        except Exception:
            for i,p in enumerate(pages):
                try:
                    print('camera-debug',i,p.evaluate("async () => ({status:document.querySelector('#cm-room-status')?.textContent, stage:document.querySelector('#cm-stage')?.getBoundingClientRect().toJSON(), rail:document.querySelector('#cm-camera-stage')?.getBoundingClientRect().toJSON(), videos:[...document.querySelectorAll('#cm-camera-stage video')].map(v=>({w:v.videoWidth,paused:v.paused,tracks:v.srcObject?.getTracks().map(t=>({kind:t.kind,ready:t.readyState,muted:t.muted}))})), peers:await Promise.all(rtc.map(async pc=>({state:pc.connectionState,signal:pc.signalingState,senders:pc.getSenders().map(s=>({kind:s.track?.kind})),stats:pc.connectionState==='connected'?[...(await pc.getStats()).values()].filter(s=>s.type==='inbound-rtp').map(s=>({kind:s.kind,frames:s.framesDecoded})):[]})))})"))
                    p.screenshot(path=str(OUT/f'experience-rooms-failure-{i}.png'),full_page=True)
                except Exception:pass
            raise
        finally:browser.close()
    finally:server.shutdown()
