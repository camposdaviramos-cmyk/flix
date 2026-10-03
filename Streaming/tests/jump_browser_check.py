"""Isolated two-browser FlixJump integration test; no production data is changed."""
import json
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server, WSGIRequestHandler
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import create_app

class QuietHandler(WSGIRequestHandler):
    def log_request(self,*args,**kwargs):pass


def run():
    with tempfile.TemporaryDirectory() as folder:
        app=create_app(folder,testing=True)
        with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:
            db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
        server=make_server('127.0.0.1',8127,app,threaded=True,request_handler=QuietHandler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        url='http://localhost:8127'
        headers={'X-Requested-With':'VYRA'}
        output=ROOT/'test-results';output.mkdir(exist_ok=True)
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--autoplay-policy=no-user-gesture-required'])
                ctx=browser.new_context(viewport={'width':1440,'height':1000},permissions=['microphone'],bypass_csp=True)
                page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                ctx.request.post(url+'/api/auth/login',data={'email':'admin@vyra.local','password':'Admin-browser-123'},headers=headers)
                page.goto(url+'/admin?tab=users')
                page.get_by_role('button',name='Cadastrar usuário',exact=True).click()
                page.locator('#f-name').fill('Alice Cinema')
                page.locator('#f-username').fill('alice')
                page.locator('#f-email').fill('alice@example.com')
                page.locator('#f-password').fill('Customer-test-123')
                page.locator('#f-plan_id').select_option('premium')
                page.locator('#new-user-form [type=submit]').click()
                page.locator('#modal').wait_for(state='hidden')
                page.get_by_text('Alice Cinema',exact=True).wait_for()
                page.screenshot(path=str(output/'flixjump-admin.png'),full_page=True)
                r=ctx.request.post(url+'/api/admin/users',data={'name':'Bruno Filmes','username':'bruno','email':'bruno@example.com','password':'Customer-test-123','plan_id':'premium'},headers=headers)
                assert r.status==201,r.text()
                bruno=r.json()['user']
                ctx.request.post(url+'/api/auth/login',data={'email':'alice@example.com','password':'Customer-test-123'},headers=headers)
                guest_ctx=browser.new_context(viewport={'width':1280,'height':900},permissions=['microphone'],bypass_csp=True)
                guest_ctx.request.post(url+'/api/auth/login',data={'email':'bruno@example.com','password':'Customer-test-123'},headers=headers)
                guest=guest_ctx.new_page();guest.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(url);guest.goto(url)
                page.get_by_role('button',name='FlixJump e amigos').click()
                page.locator('[data-jump-form=friend] input').fill('@bruno')
                page.locator('[data-jump-form=friend] [type=submit]').click()
                page.get_by_text('@bruno · Pendente',exact=True).wait_for()
                guest.get_by_role('button',name='FlixJump e amigos').click()
                guest.get_by_role('button',name='Aceitar solicitação').click()
                guest.get_by_text('@alice',exact=True).wait_for()
                guest.get_by_role('button',name='Fechar',exact=True).click()
                page.get_by_role('button',name='Fechar',exact=True).click()
                page.evaluate("play('horizonte')")
                page.wait_for_function('player?.ready && player.video.currentTime > 0')
                page.get_by_role('button',name='Criar sala FlixJump',exact=True).click()
                page.get_by_text('Sua sala de cinema',exact=True).wait_for()
                room=page.evaluate('player.jump.id')
                page.get_by_role('button',name='Convidar amigos',exact=True).click()
                page.get_by_role('button',name='Convidar para a sala').click()
                guest.get_by_role('button',name='FlixJump e amigos').click()
                guest.locator('[data-jump=join-invite]').click()
                guest.get_by_text('Aguardando o anfitrião',exact=True).wait_for()
                page.locator('.fj-entry-notice').get_by_role('button',name='Aceitar',exact=True).click()
                guest.wait_for_function('player?.jump?.members.length === 2')
                page.wait_for_function('player?.jump?.members.length === 2')
                page.get_by_role('button',name='Fechar painel').click()
                guest.get_by_role('button',name='Fechar painel').click()
                page.evaluate('player.video.pause();player.video.currentTime=25')
                guest.wait_for_function('player.video.paused && Math.abs(player.video.currentTime-25)<1.5')
                assert guest.locator('.fj-timeline').is_disabled()
                page.get_by_role('button',name='Abrir chat da sala',exact=True).click()
                page.locator('#fj-message').fill('Essa cena ficou incrível! <img src=x onerror=alert(1)>')
                page.get_by_role('button',name='Enviar mensagem').click()
                guest.locator('.fj-bubble').wait_for()
                assert guest.locator('.fj-bubble img').count()==0
                guest.locator('.fj-bubble').click()
                guest.locator('.fj-message').wait_for()
                guest.locator('#fj-message').fill('Vamos dar play juntos 🎬')
                guest.get_by_role('button',name='Enviar mensagem').click()
                page.get_by_text('Vamos dar play juntos 🎬',exact=True).first.wait_for()
                page.wait_for_function("[...player.peers.values()].some(p=>p.pc.connectionState==='connected')",timeout=30000)
                page.get_by_role('button',name='Ativar microfone',exact=True).click()
                page.wait_for_function("player.localStream?.getAudioTracks()[0].readyState==='live'")
                try:
                    guest.wait_for_function("[...player.peers.values()].some(p=>p.audio.srcObject?.getAudioTracks().length)",timeout=10000)
                except Exception:
                    for label,tab in [('host',page),('guest',guest)]:
                        print(label,tab.evaluate("({status:document.querySelector('.player-status').textContent,peers:[...player.peers.values()].map(p=>({state:p.pc.connectionState,signal:p.pc.signalingState,local:p.pc.localDescription?.sdp,remote:p.pc.remoteDescription?.sdp,audio:!!p.audio.srcObject,transceivers:p.pc.getTransceivers().map(t=>({direction:t.direction,current:t.currentDirection,track:t.sender.track?.readyState}))}))})"),flush=True)
                    print('Errors:',errors,flush=True)
                    raise
                guest.wait_for_function("async()=>{const peers=[...player.peers.values()];for(const p of peers){const stats=await p.pc.getStats();for(const s of stats.values())if(s.type==='inbound-rtp'&&s.kind==='audio'&&s.bytesReceived>0)return true;}return false;}",timeout=15000)
                guest.get_by_role('button',name='Ativar microfone',exact=True).click()
                page.wait_for_function("async()=>{for(const p of player.peers.values()){const stats=await p.pc.getStats();for(const s of stats.values())if(s.type==='inbound-rtp'&&s.kind==='audio'&&s.bytesReceived>0)return true;}return false;}",timeout=15000)
                guest.get_by_role('button',name='Desativar microfone',exact=True).click()
                page.screenshot(path=str(output/'flixjump-player-desktop.png'))
                page.get_by_role('button',name='Desativar microfone',exact=True).click()
                page.wait_for_function('!player.localStream')
                page.get_by_role('button',name='Tela cheia',exact=True).click()
                page.wait_for_function('!!document.fullscreenElement')
                assert page.locator('.fj-panel').is_visible()
                page.get_by_role('button',name='Tela cheia',exact=True).click()
                page.get_by_role('button',name='Pausar',exact=True).count()
                page.get_by_role('button',name='Reproduzir',exact=True).click()
                guest.wait_for_function('!player.video.paused && Math.abs(player.video.currentTime-25)>1')
                guest.set_viewport_size({'width':390,'height':844})
                guest.screenshot(path=str(output/'flixjump-player-mobile.png'))
                panel=guest.locator('.fj-panel').bounding_box()
                assert panel['x']>=0 and panel['x']+panel['width']<=390,panel
                assert guest.locator('#modal').evaluate('(el)=>el.scrollWidth<=el.clientWidth'),guest.locator('#modal').evaluate('(el)=>({width:el.clientWidth,scroll:el.scrollWidth})')
                assert guest.locator('.fj-chat-form').is_visible()
                page.get_by_role('button',name='Fechar',exact=True).click()
                guest.wait_for_function('player.jump.host_id===state.user.id')
                guest.get_by_role('button',name='FlixJump · Assistir com amigos').click()
                guest.get_by_role('button',name='Encerrar para todos',exact=True).click()
                guest.get_by_role('button',name='Encerrar sala',exact=True).click()
                guest.wait_for_function('!player.jump && player.peers.size===0 && !player.localStream')
                assert not errors,errors
                print(json.dumps({'ok':True,'checks':['admin registration and plan','friend request and acceptance','room invitation','two-browser playback pause/seek/play','chat with XSS escaping and bubbles','WebRTC audio packets','microphone off','fullscreen overlays','mobile layout','host transfer and room cleanup'],'screenshots':['flixjump-admin.png','flixjump-player-desktop.png','flixjump-player-mobile.png']},ensure_ascii=False))
                browser.close()
        finally:server.shutdown()

if __name__=='__main__':run()
