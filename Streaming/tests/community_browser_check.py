"""Community journeys, real two-browser sync and voice/video smoke test."""
import json
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler

def run():
  with tempfile.TemporaryDirectory() as folder:
    app=create_app(folder,testing=True)
    with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
    server=make_server('127.0.0.1',8132,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start()
    url='http://localhost:8132';headers={'X-Requested-With':'VYRA'};output=ROOT/'test-results';output.mkdir(exist_ok=True)
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--autoplay-policy=no-user-gesture-required'])
        hc=browser.new_context(bypass_csp=True,viewport={'width':1440,'height':1000},permissions=['microphone','camera']);gc=browser.new_context(bypass_csp=True,viewport={'width':390,'height':844},permissions=['microphone','camera'])
        hc.request.post(url+'/api/auth/login',data={'email':'admin@vyra.local','password':'Admin-browser-123'},headers=headers)
        r=hc.request.post(url+'/api/admin/users',data={'name':'Luna Martins','username':'luna','email':'luna@example.com','password':'Customer-test-123'},headers=headers);assert r.status==201,r.text();guest_id=r.json()['user']['id']
        gc.request.post(url+'/api/auth/login',data={'email':'luna@example.com','password':'Customer-test-123'},headers=headers)
        for c in [hc,gc]:
          c.route('https://media.example.test/**',lambda route:route.fulfill(path=str(ROOT/'static/assets/sintel-trailer.mp4'),content_type='video/mp4',headers={'Access-Control-Allow-Origin':'*'}))
        host=hc.new_page();guest=gc.new_page();errors=[]
        for p in [host,guest]:p.on('pageerror',lambda e:errors.append(str(e)))
        host.goto(url+'/comunidade');host.get_by_role('heading',name='Página inicial').wait_for()
        assert not errors,errors
        host.locator('.sx-sidebar [data-cm=new-post]').click();host.get_by_label('Título',exact=True).fill('Sintel · uma história para descobrir juntos');host.get_by_label('Conte para a comunidade').fill('Uma jornada de fantasia e amizade. Quem vem assistir?');host.get_by_label('Link do vídeo, música ou notícia').fill('https://media.example.test/movie.mp4');host.locator('[data-cs=publish]').click();host.wait_for_url('**/comunidade/post/*')
        host.get_by_role('heading',name='Sintel · uma história para descobrir juntos').wait_for();pid=host.url.split('/')[-1]
        guest.goto(url+'/comunidade/post/'+pid);guest.get_by_label('Seu comentário').fill('Eu vou!');guest.get_by_role('button',name='Comentar',exact=True).click();guest.get_by_text('Eu vou!',exact=True).wait_for();guest.locator('[data-sx=react][data-value=heart]').click();guest.locator('[data-sx=react][data-value=heart][aria-pressed=true]').wait_for()
        guest.goto(url+'/comunidade/perfil/luna');guest.get_by_role('button',name='Editar perfil').click();guest.get_by_label('Sua bio').fill('Apaixonada por fantasia, boas trilhas e noites de cinema.');guest.get_by_label('Gêneros favoritos').fill('Fantasia, animação, aventura');guest.get_by_label('Cidade ou região').fill('São Paulo');guest.locator('#cm-avatar-file').set_input_files(str(ROOT/'static/assets/hero.png'));guest.wait_for_function("document.querySelector('[name=avatar]').value.startsWith('data:image/png')");guest.get_by_role('button',name='Salvar perfil').click();guest.get_by_text('Apaixonada por fantasia, boas trilhas e noites de cinema.').wait_for()
        host.goto(url+'/admin?tab=community-badges');host.get_by_label('Nome de usuário',exact=True).fill('luna');host.get_by_label('Emblema',exact=True).select_option('curador');host.get_by_role('button',name='Aplicar emblema').click();host.get_by_role('button',name='Revogar').wait_for()
        guest.reload();guest.locator('.cm-badge').get_by_text('Curador',exact=True).wait_for();guest.screenshot(path=str(output/'community-profile-mobile.png'),full_page=True)
        host.goto(url+'/comunidade/perfil/luna');host.get_by_role('button',name='Adicionar amigo',exact=True).click();host.get_by_text('Pedido enviado',exact=True).wait_for()
        guest.goto(url+'/comunidade?tab=friends');guest.get_by_role('button',name='Aceitar',exact=True).click();guest.locator('.sx-conversation').first.click();guest.get_by_label('Mensagem',exact=True).fill('Vamos para a sala?');guest.get_by_role('button',name='Enviar',exact=True).click();expect(guest.locator('#sx-chat-log')).to_contain_text('Vamos para a sala?')
        host.goto(url+'/comunidade?tab=friends');host.locator('.sx-conversation').first.click();expect(host.locator('#sx-chat-log')).to_contain_text('Vamos para a sala?',timeout=10000)
        host.goto(url+'/comunidade/post/'+pid);host.get_by_role('button',name='Assistir juntos',exact=True).click();host.get_by_label('Nome da sala',exact=True).fill('Sessão de sexta · Sintel');host.locator('#cs-room').get_by_role('button',name='Criar sala',exact=True).click();host.locator('#cm-share-link').wait_for();rid=host.url.split('/')[-1]
        guest.goto(url+'/comunidade/sala/'+rid);guest.get_by_text('Aguardando o anfitrião aceitar sua entrada…',exact=True).wait_for();host.locator('#cm-room-requests').get_by_role('button',name='Aceitar',exact=True).click();guest.locator('#cm-share-link').wait_for()
        host.wait_for_function("document.querySelector('#cm-room-media')?.readyState>=2");guest.wait_for_function("document.querySelector('#cm-room-media')?.readyState>=2")
        host.evaluate("document.querySelector('#cm-room-media').currentTime=18");host.wait_for_timeout(1200)
        host.get_by_role('button',name='Ativar áudio',exact=True).click();guest.get_by_role('button',name='Ativar áudio',exact=True).click();guest.wait_for_function("document.querySelector('#cm-room-media').currentTime>19 && !document.querySelector('#cm-room-media').paused")
        delta=abs(host.locator('#cm-room-media').evaluate('(v)=>v.currentTime')-guest.locator('#cm-room-media').evaluate('(v)=>v.currentTime'));assert delta<1,delta
        host.evaluate("document.querySelector('#cm-room-media').pause()");guest.wait_for_function("document.querySelector('#cm-room-media').paused")
        host.get_by_role('button',name='Abrir chat',exact=True).click();host.get_by_label('Sua mensagem').fill('Boa sessão, turma!');host.locator('#cm-room-message').get_by_role('button',name='Enviar').click();guest.locator('.cm-chat-bubble').get_by_text('Boa sessão, turma!').wait_for()
        guest.get_by_role('button',name='Abrir chat',exact=True).click();guest.locator('#cm-room-messages').get_by_text('Boa sessão, turma!').wait_for();guest.screenshot(path=str(output/'community-room-mobile.png'),full_page=True);host.screenshot(path=str(output/'community-room-desktop.png'),full_page=True)
        host.get_by_role('button',name='Adicionar',exact=True).click();host.get_by_label('Título',exact=True).fill('Próximo vídeo');host.get_by_label('Link do vídeo ou música').fill('https://media.example.test/next.mp4');host.get_by_role('button',name='Adicionar à fila').click();guest.locator('#cm-room-queue').get_by_text('Próximo vídeo',exact=False).wait_for()
        # Real microphone transport plus video session (camera never starts without click).
        host.evaluate('''() => {const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async constraints=>{if(constraints.audio&&!constraints.video){const ctx=new AudioContext();await ctx.resume();const osc=ctx.createOscillator(),gain=ctx.createGain(),dest=ctx.createMediaStreamDestination();osc.frequency.value=330;gain.gain.value=.2;osc.connect(gain).connect(dest);osc.start();window.communityTestTone={ctx,osc,gain};return dest.stream;}return original(constraints);};}''')
        host.get_by_role('button',name='Microfone desligado',exact=True).click();host.wait_for_timeout(2500);guest.wait_for_function("[...document.querySelectorAll('audio')].some(a=>a.srcObject?.getAudioTracks().length)",timeout=15000)
        guest.locator('#cm-voice-indicator').wait_for(state='visible');assert guest.locator('#cm-room-media').evaluate('(v)=>v.volume')<.3
        host.evaluate('communityTestTone.gain.gain.value=0');guest.locator('#cm-voice-indicator').wait_for(state='hidden');assert guest.locator('#cm-room-media').evaluate('(v)=>v.volume')==1
        # Create a video room and check the guest receives the remote camera stream.
        rr=hc.request.post(url+'/api/community/rooms',data={'title':'Encontro de cinéfilos','kind':'video','approval':False},headers=headers);assert rr.status==201,rr.text();vr=rr.json()['room']['id']
        host.goto(url+'/comunidade/sala/'+vr);guest.goto(url+'/comunidade/sala/'+vr);host.get_by_role('button',name='Ativar câmera',exact=True).click();guest.wait_for_function("document.querySelector('#cm-camera-stage video')?.srcObject?.getVideoTracks().length",timeout=15000)
        host.goto(url+'/comunidade');host.get_by_role('heading',name='Página inicial').wait_for();host.screenshot(path=str(output/'community-feed-desktop.png'),full_page=True)
        guest.goto(url+'/comunidade');guest.get_by_role('heading',name='Página inicial').wait_for();guest.screenshot(path=str(output/'community-feed-mobile.png'),full_page=True)
        assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth'), guest.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>[e.tagName,e.className,e.getBoundingClientRect().width]).slice(0,20)")
        host.goto(url+'/admin?tab=community');host.get_by_role('button',name='Ocultar',exact=True).click();host.get_by_role('button',name='Publicar',exact=True).wait_for();host.get_by_role('button',name='Publicar',exact=True).click();host.get_by_role('button',name='Ocultar',exact=True).wait_for();host.screenshot(path=str(output/'community-admin-desktop.png'),full_page=True)
        guest.goto(url+'/comunidade?tab=ranking');guest.get_by_role('heading',name='Ranking de membros').wait_for()
        assert not errors,errors
        print(json.dumps({'ok':True,'sync_delta_seconds':round(delta,3),'browser_errors':errors,'screenshots':str(output)}))
        browser.close()
    except Exception:
      for name,page in [('host',host),('guest',guest)]:
        try:print(name,page.locator('#cm-room-media').evaluate('(v)=>({time:v.currentTime,paused:v.paused,ready:v.readyState,error:v.error?.message})'),page.locator('#cm-room-status').all_text_contents());page.screenshot(path=str(output/('community-failure-'+name+'.png')),full_page=True)
        except Exception:pass
      raise
    finally:server.shutdown()
if __name__=='__main__':run()
