"""Free account, community catalogs and host-controlled stage across two browsers."""
import json,sqlite3,sys,tempfile,threading
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler
with tempfile.TemporaryDirectory() as folder:
    app=create_app(folder,testing=True)
    with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
    server=make_server('127.0.0.1',8134,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start()
    url='http://localhost:8134';headers={'X-Requested-With':'VYRA'};out=ROOT/'test-results'
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--autoplay-policy=no-user-gesture-required'])
            hc=browser.new_context(bypass_csp=True,viewport={'width':1440,'height':1000},permissions=['microphone','camera']);gc=browser.new_context(bypass_csp=True,viewport={'width':390,'height':844},permissions=['microphone','camera'])
            hc.request.post(url+'/api/auth/login',data={'email':'admin@vyra.local','password':'Admin-browser-123'},headers=headers)
            host=hc.new_page();guest=gc.new_page();errors=[]
            for page in [host,guest]:page.on('pageerror',lambda e:errors.append(str(e)))
            guest.goto(url+'/comunidade');guest.get_by_role('button',name='Criar conta grátis',exact=True).click()
            guest.get_by_label('Seu nome',exact=True).fill('Marina Luz');guest.get_by_label('Nome de usuário',exact=True).fill('marinaluz');guest.get_by_label('E-mail',exact=True).fill('marina@example.com');guest.get_by_label('Senha',exact=True).fill('Community-test-123');guest.locator('#cm-free-register input[type=checkbox]').check();guest.locator('#cm-free-register').get_by_role('button',name='Criar conta grátis',exact=True).click()
            guest.get_by_role('heading',name='Página inicial').wait_for();u=gc.request.get(url+'/api/bootstrap').json()['user'];assert u['plan_id'] is None and not u['subscribed'];gid=u['id']
            assert gc.request.get(url+'/api/play/horizonte').status==402
            pid=None
            for kind,title in [('movie','Cinema livre'),('series','Série da turma'),('channel','TV dos membros'),('news','Novidades do cinema')]:
                r=hc.request.post(url+'/api/community/posts',data={'kind':kind,'title':title,'body':'Compartilhado pela comunidade','url':'https://media.example.test/video.mp4'},headers=headers);assert r.status==201,r.text()
                if kind=='channel':pid=r.json()['id']
            gc.route('https://media.example.test/**',lambda route:route.fulfill(path=str(ROOT/'static/assets/sintel-trailer.mp4'),content_type='video/mp4',headers={'Access-Control-Allow-Origin':'*'}))
            guest.goto(url+'/comunidade?tab=catalog&kind=channel');guest.get_by_role('heading',name='TV da comunidade · ao vivo').wait_for();guest.get_by_role('button',name='Assistir grátis',exact=True).click();guest.wait_for_function("document.querySelector('#cm-solo-media video')?.currentTime>0");assert guest.locator('#cm-solo-media video').is_visible();guest.locator('#modal [data-action=close]').click()
            guest.get_by_role('button',name='Avaliar',exact=True).click();guest.get_by_label('Sua avaliação',exact=True).select_option('5');guest.get_by_role('button',name='Salvar avaliação',exact=True).click();expect(guest.locator('.cm-catalog-card .cm-stars')).to_contain_text('5.0 / 5')
            guest.get_by_role('button',name='Seguir',exact=True).click();guest.get_by_role('button',name='Seguindo',exact=True).wait_for();guest.evaluate('document.activeElement?.blur();window.scrollTo(0,0)');guest.screenshot(path=str(out/'community-free-catalog-mobile.png'),full_page=True)
            host.goto(url+'/comunidade?tab=catalog&kind=channel');host.get_by_role('heading',name='TV da comunidade · ao vivo').wait_for();host.screenshot(path=str(out/'community-free-catalog-desktop.png'),full_page=True)
            r=hc.request.post(url+'/api/community/rooms',data={'kind':'voice','title':'Clube do cinema · assentos de voz','approval':False},headers=headers);assert r.status==201,r.text();rid=r.json()['room']['id'];roomurl=url+'/comunidade/sala/'+rid
            host.goto(roomurl);guest.goto(roomurl);guest.locator('#cm-seat-count').wait_for();expect(guest.locator('#cm-seats>.cm-seat')).to_have_count(8);expect(guest.locator('[data-cm=room-mic]')).to_be_disabled()
            guest.evaluate('''() => {window.deviceRequests=0;const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async c=>{window.deviceRequests++;const stream=await original(c);window.lastMic=stream.getAudioTracks()[0];return stream;};}''')
            host.locator(f'[data-audience="{gid}"] [data-cm=room-promote]').click();expect(guest.locator('[data-cm=room-mic]')).to_be_enabled();assert guest.evaluate('window.deviceRequests')==0
            guest.get_by_role('button',name='Microfone desligado',exact=True).click();expect(guest.locator('[data-cm=room-mic]')).to_have_attribute('aria-pressed','true');host.wait_for_function("[...document.querySelectorAll('audio')].some(a=>a.srcObject?.getAudioTracks().length)",timeout=20000)
            host.locator(f'[data-seat="{gid}"] [data-cm=room-mute]').click();expect(guest.locator('[data-cm=room-mic]')).to_be_disabled();guest.wait_for_function("window.lastMic?.readyState==='ended'");host.wait_for_function("[...document.querySelectorAll('audio')].every(a=>a.muted||!a.srcObject)")
            me=next(m for m in gc.request.post(url+f'/api/community/rooms/{rid}/poll',headers=headers,data={'mic':True}).json()['room']['members'] if m['id']==gid);assert me['mic']==0 and me['mic_blocked']==1
            host.locator(f'[data-seat="{gid}"] [data-cm=room-allow-mic]').click();expect(guest.locator('[data-cm=room-mic]')).to_be_enabled();assert guest.evaluate('window.deviceRequests')==1;assert guest.evaluate('window.lastMic.readyState')=='ended'
            guest.get_by_role('button',name='Microfone desligado',exact=True).click();expect(guest.locator('[data-cm=room-mic]')).to_have_attribute('aria-pressed','true')
            host.locator(f'[data-seat="{gid}"] [data-cm=room-demote]').click();expect(guest.locator('[data-cm=room-mic]')).to_be_disabled();guest.wait_for_function("window.lastMic.readyState==='ended'")
            host.locator(f'[data-audience="{gid}"] [data-cm=room-promote]').click();expect(guest.locator('[data-cm=room-mic]')).to_be_enabled();assert guest.evaluate('window.deviceRequests')==2
            host.evaluate('document.activeElement?.blur();window.scrollTo(0,0)');guest.evaluate('document.activeElement?.blur();window.scrollTo(0,0)');host.screenshot(path=str(out/'community-stage-desktop.png'),full_page=True);guest.screenshot(path=str(out/'community-stage-mobile.png'),full_page=True)
            assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth');assert not errors,errors
            print(json.dumps({'free_registration':True,'premium_protected':True,'free_tv_playback':True,'ratings_and_follow':True,'eight_seats':True,'forced_mute_stops_track':True,'promotion_never_opens_mic':True,'page_errors':errors}));browser.close()
    finally:server.shutdown()
