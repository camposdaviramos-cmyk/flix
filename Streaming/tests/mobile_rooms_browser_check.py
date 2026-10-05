"""Mobile reference layout, room tools, admission, live mode, coins and plugins."""
import json,sqlite3,sys,tempfile,threading,time
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler
H={'X-Requested-With':'Flix'};OUT=ROOT/'test-results'
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True)
 with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:
  db.execute("UPDATE users SET password=?,name='Davi Ramos',username='davi' WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
  db.execute('UPDATE coin_config SET welcome=150')
 server=make_server('127.0.0.1',8146,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8146'
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
   hc=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,permissions=['microphone','camera']);gc=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,permissions=['microphone','camera']);dc=browser.new_context(viewport={'width':1440,'height':1000})
   assert hc.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'}).ok
   assert dc.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'}).ok
   r=hc.request.post(url+'/api/admin/users',headers=H,data={'name':'Carol Souza','username':'carol','email':'carol@example.com','password':'Community-123'});assert r.ok,r.text();guest_id=r.json()['user']['id']
   assert gc.request.post(url+'/api/auth/login',headers=H,data={'email':'carol@example.com','password':'Community-123'}).ok
   r=hc.request.post(url+'/api/community/rooms',headers=H,data={'title':'Cinema com a turma','description':'Filmes, jogos e boas conversas.','kind':'watch','url':'https://media.example.test/video.mp4','approval':True,'permanent':True});assert r.ok,r.text();rid=r.json()['room']['id'];path='/api/community/rooms/'+rid
   host=hc.new_page();guest=gc.new_page();desktop=dc.new_page();errors=[]
   for p in (host,guest,desktop):
    p.on('pageerror',lambda e:errors.append(str(e)));p.route('https://media.example.test/**',lambda r:r.fulfill(path=str(ROOT/'static/assets/sintel-trailer.mp4'),content_type='video/mp4',headers={'Access-Control-Allow-Origin':'*'}))
   try:
    host.goto(url+'/comunidade/sala/'+rid);expect(host.locator('.rm-tabs')).to_be_visible(timeout=20000)
    guest.goto(url+'/comunidade/sala/'+rid);expect(host.locator('.rm-request-toast')).to_contain_text('Carol Souza',timeout=15000)
    host.locator('.rm-request-toast [data-cm=room-approve]').click();expect(guest.locator('.rm-tabs')).to_be_visible(timeout=15000)
    for msg in ['Essa sala tá incrível! 🔥','Bora continuar?','Qual é o próximo filme? 🍿']:
     guest.locator('#cm-room-message input[name=body]').fill(msg);guest.locator('#cm-room-message [type=submit]').click();expect(host.locator('#cm-room-messages')).to_contain_text(msg)
    host.locator('#cm-room-media').evaluate('(v)=>v.play()');host.wait_for_function("()=>document.querySelector('#cm-room-media').currentTime>3");host.screenshot(path=str(OUT/'rooms-redesign-mobile-chat.png'))
    assert host.evaluate('document.documentElement.scrollWidth<=innerWidth')
    host.locator('.rm-header [data-rm=people]').click();expect(host.locator('.rm-heading-text')).to_contain_text('Participantes');host.screenshot(path=str(OUT/'rooms-redesign-mobile-people.png'))
    host.locator('.rm-tabs [data-tab=media]').click();expect(host.locator('.rm-tool-tabs')).to_be_visible();host.screenshot(path=str(OUT/'rooms-redesign-mobile-media.png'))
    host.locator('[data-rm=tool][data-tool=polls]').click();host.locator('[data-rm=poll-new]').click();host.locator('#rm-poll-form [name=question]').fill('O que vamos assistir?');host.locator('#rm-poll-form [name=options]').fill('Aventura\nComédia');host.locator('#rm-poll-form [type=submit]').click();expect(host.locator('.rm-poll')).to_contain_text('O que vamos assistir?')
    guest.locator('.rm-tabs [data-tab=media]').click();guest.locator('[data-rm=tool][data-tool=polls]').click();expect(guest.locator('.rm-poll')).to_be_visible();guest.locator('[data-rm=vote][data-choice="1"]').click();expect(host.locator('[data-rm=vote][data-choice="1"] b')).to_have_text('1')
    host.locator('.rm-tabs [data-tab=more]').click();expect(host.locator('.rm-menu')).to_be_visible();host.screenshot(path=str(OUT/'rooms-redesign-mobile-menu.png'))
    host.locator('[data-rm=settings]').click();host.locator('#cm-room-settings [name=activity]').select_option('voice');host.locator('#cm-room-settings [type=submit]').click();host.locator('.rm-tabs [data-tab=chat]').click();expect(host.locator('.rm-stage-empty')).to_be_visible();expect(host.locator('.rm-avatar-strip')).to_be_visible()
    host.locator('.rm-tabs [data-tab=media]').click();host.locator('[data-rm=tool][data-tool=games]').click();host.locator('[data-rm=plugin-activate][data-id=colors]').click();expect(host.locator('#sx-room-games')).to_be_visible(timeout=10000)
    guest.locator('.rm-tabs [data-tab=chat]').click();expect(guest.locator('.fg-invite')).to_be_visible();print('Joining game',flush=True);guest.locator('.fg-invite [data-game=join]').click();print('Joined game',flush=True);expect(host.locator('.fg-player')).to_have_count(2);print('Starting game',flush=True);host.locator('[data-game=start]').click();expect(host.locator('.fg-hand .fg-card')).to_have_count(7);host.screenshot(path=str(OUT/'rooms-redesign-mobile-game.png'))
    guest.locator('.rm-avatar-strip [data-rm=profile]').first.click();expect(guest.locator('.rm-profile-preview')).to_be_visible();guest.locator('[data-rm=follow]').click();expect(guest.locator('[data-rm=follow]')).to_have_text('Seguindo');expect(guest.locator('.rm-tabs')).to_be_visible();guest.locator('[data-rm=gift]').click();guest.locator('[data-wallet=pick-gift][data-id=heart]').click();guest.locator('[data-wallet=send-gift]').click();expect(guest.locator('#modal')).not_to_be_visible();assert gc.request.get(url+'/api/wallet').json()['balance']==125
    desktop.goto(url+'/comunidade/sala/'+rid);expect(desktop.locator('.rm-shell')).to_have_count(0);expect(desktop.locator('.rm-desktop-tools')).to_be_visible();desktop.screenshot(path=str(OUT/'rooms-redesign-desktop-preserved.png'))
    host.goto(url+'/admin?tab=economy');expect(host.locator('#fw-welcome')).to_be_visible();host.screenshot(path=str(OUT/'rooms-redesign-admin.png'))
    guest.goto(url+'/carteira');expect(guest.locator('.fw-balance')).to_contain_text('125');guest.screenshot(path=str(OUT/'rooms-redesign-wallet.png'));assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors
    print(json.dumps({'mobile_screens':4,'admission_float':True,'chat':True,'polls':True,'mode_switch':True,'empty_stage_visible':True,'game':True,'profile_preview':True,'gift_balance':125,'desktop_preserved':True,'errors':errors}))
   except Exception:
    print('PAGE ERRORS',errors)
    for name,p in [('host',host),('guest',guest)]:
     try:p.screenshot(path=str(OUT/f'rooms-redesign-failure-{name}.png'),full_page=True);print(name,p.locator('#cm-room-root').inner_text()[:1200] if p.locator('#cm-room-root').count() else p.locator('body').inner_text()[:1200])
     except Exception:pass
    raise
   finally:browser.close()
 finally:server.shutdown()
