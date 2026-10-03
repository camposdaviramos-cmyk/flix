"""Chat, recording, calling, rooms and PWA in isolated desktop/mobile sessions."""
import json,sqlite3,sys,tempfile,threading,time
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler
H={'X-Requested-With':'Flix'};OUT=ROOT/'test-results';OUT.mkdir(exist_ok=True)
def until(p,fn,seconds=25):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if p.evaluate(fn):return
        p.wait_for_timeout(180)
    raise AssertionError(fn)
with tempfile.TemporaryDirectory() as folder:
    app=create_app(folder,testing=True)
    with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=?,name='Theo Almeida' WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
    server=make_server('127.0.0.1',8138,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8138'
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
        hc=browser.new_context(viewport={'width':1440,'height':1000},permissions=['microphone','camera','notifications']);gc=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,permissions=['microphone','camera','notifications'])
        assert hc.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'}).ok
        aid=hc.request.get(url+'/api/bootstrap').json()['user']['id'];r=hc.request.post(url+'/api/admin/users',headers=H,data={'name':'Luna Martins','username':'luna','email':'luna@example.com','password':'Community-123'});assert r.ok,r.text();gid=r.json()['user']['id']
        assert gc.request.post(url+'/api/auth/login',headers=H,data={'email':'luna@example.com','password':'Community-123'}).ok
        hc.request.post(url+'/api/social/friends',headers=H,data={'username':'luna'});gc.request.patch(url+'/api/social/friends/'+aid,headers=H,data={})
        host=hc.new_page();guest=gc.new_page();errors=[]
        for page in (host,guest):
          page.on('pageerror',lambda e:errors.append(str(e)))
          page.add_init_script('''(()=>{window.deviceStreams=[];window.deviceRequests=0;window.peers=[];const media=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async c=>{window.deviceRequests++;const s=await media(c);window.deviceStreams.push(s);return s;};const PC=RTCPeerConnection;window.RTCPeerConnection=class extends PC{constructor(...a){super(...a);window.peers.push(this)}};})()''')
        try:
          host.goto(url+'/comunidade?tab=friends');guest.goto(url+'/comunidade?tab=friends')
          host.locator(f'[data-hub=dm][data-id="{gid}"]').click();guest.locator(f'[data-hub=dm][data-id="{aid}"]').click()
          host.get_by_label('Mensagem',exact=True).fill('Bora para uma sessão? 🍿');host.get_by_role('button',name='Enviar mensagem',exact=True).click()
          expect(guest.locator('#fh-messages')).to_contain_text('Bora para uma sessão?',timeout=15000)
          guest.get_by_label('Mensagem',exact=True).fill('Vamos!');guest.get_by_role('button',name='Enviar mensagem',exact=True).click();expect(host.locator('#fh-messages')).to_contain_text('Vamos!',timeout=15000)
          host.locator('#fh-message summary').click();host.get_by_role('button',name='Figurinha Bora assistir!',exact=True).click();host.get_by_role('button',name='Enviar mensagem',exact=True).click();expect(guest.locator('#fh-messages .sx-sticker')).to_be_visible(timeout=15000)
          host.get_by_role('button',name='Gravar áudio',exact=True).click();expect(host.locator('#fh-record-preview')).to_contain_text('Gravando');host.wait_for_timeout(900);host.get_by_role('button',name='Concluir',exact=True).click();expect(host.locator('#fh-record-preview audio')).to_be_visible();host.get_by_role('button',name='Enviar áudio',exact=True).click();expect(guest.locator('#fh-messages audio')).to_be_visible(timeout=15000)
          guest.locator('#fh-messages audio').evaluate('(a)=>a.play()');until(guest,"() => document.querySelector('#fh-messages audio').currentTime>.2");guest.locator('#fh-messages audio').evaluate('(a)=>a.pause()')
          until(host,'() => window.deviceStreams.every(s=>s.getTracks().every(t=>t.readyState===\'ended\'))')
          assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth')
          host.screenshot(path=str(OUT/'hub-chat-desktop.png'));guest.screenshot(path=str(OUT/'hub-chat-mobile.png'))
          # In-site video calls ring first; the recipient's camera opens only on accept.
          guest.evaluate("() => Community.modal('Enquanto você assiste', '<p>O player pode estar aberto durante uma chamada.</p>')")
          before=guest.evaluate('window.deviceRequests');host.get_by_role('button',name='Ligar por vídeo',exact=True).click();expect(guest.get_by_role('button',name='Atender',exact=True)).to_be_visible(timeout=15000);assert guest.evaluate('window.deviceRequests')==before
          assert guest.locator('#modal #fh-call').count()==1
          guest.get_by_role('button',name='Atender',exact=True).click();expect(host.locator('#fh-call-status')).to_have_text('Conectado',timeout=30000)
          until(guest,"() => document.querySelector('#fh-call-remote')?.videoWidth>0")
          assert guest.locator('#fh-call').evaluate('(e)=>{const r=e.getBoundingClientRect();return Math.abs(r.width-innerWidth)<2&&Math.abs(r.height-innerHeight)<2&&r.top===0}')
          until(host,"async () => {for(const p of window.peers){if(p.connectionState==='connected'){const s=[...(await p.getStats()).values()];if(s.some(x=>x.type==='inbound-rtp'&&x.kind==='audio'&&x.packetsReceived>0)&&s.some(x=>x.type==='inbound-rtp'&&x.kind==='video'&&x.framesDecoded>0))return true;}}return false;}")
          host.get_by_role('button',name='Silenciar microfone',exact=True).click();expect(host.get_by_role('button',name='Silenciar microfone',exact=True)).to_have_attribute('aria-pressed','true')
          host.locator('[data-hub=call-minimize]').click();host.locator('[data-hub=call-minimize]').click();expect(host.get_by_role('button',name='Silenciar microfone',exact=True)).to_have_attribute('aria-pressed','true')
          guest.evaluate('() => closeModal()');expect(guest.locator('body > #fh-call')).to_be_visible();expect(guest.locator('#fh-call-status')).to_have_text('Conectado')
          host.screenshot(path=str(OUT/'hub-video-call-desktop.png'));guest.screenshot(path=str(OUT/'hub-video-call-mobile.png'))
          guest.get_by_role('button',name='Encerrar',exact=True).click();expect(host.locator('#fh-call')).to_be_hidden(timeout=10000)
          for page in (host,guest):until(page,"() => window.deviceStreams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
          # Decline never activates the recipient's microphone.
          before=guest.evaluate('window.deviceRequests');host.get_by_role('button',name='Ligar por voz',exact=True).click();expect(guest.get_by_role('button',name='Recusar',exact=True)).to_be_visible(timeout=15000);guest.get_by_role('button',name='Recusar',exact=True).click();expect(host.locator('#fh-call')).to_be_hidden(timeout=10000);assert guest.evaluate('window.deviceRequests')==before
          # The profile can opt into activity while keeping invisible presence.
          guest.evaluate("() => navigate('/comunidade/perfil/luna')");guest.get_by_role('button',name='Editar perfil',exact=True).click();guest.get_by_label('Status',exact=True).fill('Cinema e boa companhia');guest.get_by_label('Disponibilidade',exact=True).select_option('busy');guest.locator('#cm-profile [name=show_activity]').check();guest.get_by_role('button',name='Salvar perfil',exact=True).click();expect(guest.locator('.fh-profile-status')).to_have_text('Cinema e boa companhia');expect(guest.locator('.fh-profile-activity')).to_be_visible()
          host.get_by_role('button',name='Notificações',exact=True).click();host.locator('#fh-notifications [data-hub=preferences]').click();host.locator('#fh-preferences [name=sounds]').uncheck();host.get_by_role('button',name='Salvar preferências',exact=True).click();expect(host.locator('#fh-preferences')).not_to_be_visible();assert hc.request.get(url+'/api/hub/preferences').json()['preferences']['sounds'] is False
          host.locator('[data-hub=notices-close]').click()
          # Floating chat survives ordinary site navigation.
          host.evaluate("() => navigate('/filmes')");expect(host.locator('#fh-messenger:not(.inline)')).to_be_visible();expect(host.locator('#fh-messages')).to_contain_text('Vamos!')
          host.get_by_role('button',name='Minimizar conversa',exact=True).click();host.evaluate("() => navigate('/comunidade')")
          host.get_by_label('Mais formatos',exact=True).click();host.locator('[data-sx=live-new]').first.click();host.get_by_label('Nome da sala',exact=True).fill('Quatro vozes, uma comunidade');host.locator('#cs-room [name=approval]').uncheck();host.locator('#cs-room [name=permanent]').check();host.get_by_role('button',name='Criar live',exact=True).click();host.wait_for_url('**/comunidade/sala/*');rid=host.url.rsplit('/',1)[-1];roomurl=host.url
          guest.goto(roomurl);expect(guest.get_by_role('button',name='Pedir para participar',exact=True)).to_be_visible();expect(guest.locator('#cm-seats>.cm-seat')).to_have_count(4)
          before=guest.evaluate('window.deviceRequests');guest.get_by_role('button',name='Pedir para participar',exact=True).click();expect(host.get_by_role('button',name='Aceitar na live',exact=True)).to_be_visible(timeout=10000);host.get_by_role('button',name='Aceitar na live',exact=True).click();expect(guest.locator('[data-cm=room-camera]')).to_be_enabled(timeout=10000);assert guest.evaluate('window.deviceRequests')==before
          host.locator(f'[data-seat="{gid}"] [data-cm=room-demote]').click();expect(guest.locator('[data-cm=room-camera]')).to_be_disabled()
          host.locator(f'[data-audience="{gid}"] [data-cm=room-promote]').click();expect(guest.get_by_role('button',name='Aceitar convite',exact=True)).to_be_visible(timeout=10000);guest.get_by_role('button',name='Aceitar convite',exact=True).click();expect(guest.locator('[data-cm=room-camera]')).to_be_enabled();assert guest.evaluate('window.deviceRequests')==before
          host.get_by_role('button',name='Iniciar transmissão',exact=True).click();guest.get_by_role('button',name='Ativar câmera',exact=True).click();until(host,"() => document.querySelectorAll('#cm-camera-stage video').length===2");host.screenshot(path=str(OUT/'hub-live-guests-desktop.png'));guest.screenshot(path=str(OUT/'hub-live-guests-mobile.png'))
          # Sharing a permanent room sends a structured card to a friend.
          host.get_by_role('button',name='Compartilhar',exact=True).click();host.locator(f'[data-hub=share-to][data-id="{gid}"]').click();expect(host.locator('#modal')).not_to_be_visible()
          host.get_by_role('link',name='Todas as salas',exact=True).click();expect(guest.locator('#cm-room-status')).to_contain_text('anfitrião está fora',timeout=10000)
          room=gc.request.post(url+f'/api/community/rooms/{rid}/poll',headers=H,data={}).json()['room'];assert room['host_id']==aid and room['permanent']
          guest.goto(url+'/comunidade?tab=friends&dm='+aid);expect(guest.locator('.fh-shared')).to_contain_text('Quatro vozes',timeout=15000)
          # Temporary room: earliest member takes all host controls, final exit closes.
          r=hc.request.post(url+'/api/community/rooms',headers=H,data={'kind':'voice','title':'Sala de passagem','approval':False});assert r.status==201,r.text();temp=r.json()['room']['id'];tempurl=url+'/comunidade/sala/'+temp
          host.goto(tempurl);guest.goto(tempurl);expect(guest.locator('#cm-seat-count')).to_be_visible();host.get_by_role('link',name='Todas as salas',exact=True).click();expect(guest.get_by_role('button',name='Ajustes',exact=True)).to_be_visible(timeout=15000);expect(guest.locator('[data-cm=room-mic]')).to_be_enabled();guest.get_by_role('link',name='Todas as salas',exact=True).click();guest.wait_for_timeout(1000);assert gc.request.get(url+'/api/community/rooms/'+temp).status==404
          guest.get_by_role('button',name='Notificações',exact=True).click();expect(guest.locator('#fh-notifications')).to_contain_text('Você é o novo anfitrião');guest.screenshot(path=str(OUT/'hub-notifications-mobile.png'))
          # PWA has a controlling worker and a real offline fallback, no private API cache.
          until(host,'() => !!navigator.serviceWorker.controller')
          assert hc.request.get(url+'/manifest.webmanifest').json()['name'].startswith('Flix')
          awaitable=host.evaluate('''async () => {const keys=await caches.keys();const requests=await Promise.all(keys.filter(k=>k.startsWith('flix-')).map(async k=>(await (await caches.open(k)).keys()).map(r=>r.url)));return requests.flat();}''');assert all('/api/' not in x for x in awaitable)
          hc.set_offline(True);host.goto(url+'/comunidade');expect(host.get_by_role('heading',name='Sua conexão fez uma pausa.')).to_be_visible();hc.set_offline(False)
          assert not errors,errors
          print(json.dumps({'chat_text_stickers_audio':True,'private_call_audio_video':True,'recipient_consent':True,'floating_chat':True,'live_requests_invites':True,'four_live_seats':True,'room_share':True,'permanent_host_retained':True,'temporary_handoff_and_close':True,'notifications':True,'mobile_no_overflow':True,'pwa_offline':True,'page_errors':errors}))
        except Exception:
          for name,page in [('host',host),('guest',guest)]:
            try:page.screenshot(path=str(OUT/f'hub-failure-{name}.png'),full_page=True)
            except Exception:pass
          raise
        finally:browser.close()
    finally:server.shutdown()
