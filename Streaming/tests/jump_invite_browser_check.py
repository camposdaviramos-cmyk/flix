"""Invitation link, login continuation and host approval in isolated browsers."""
import json
import sqlite3
import sys
import tempfile
import threading
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
        server=make_server('127.0.0.1',8128,app,threaded=True,request_handler=QuietHandler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        url='http://localhost:8128';headers={'X-Requested-With':'VYRA'};output=ROOT/'test-results'
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--autoplay-policy=no-user-gesture-required'])
                ctx=browser.new_context(viewport={'width':1440,'height':1000},bypass_csp=True,permissions=['clipboard-read','clipboard-write'])
                ctx.request.post(url+'/api/auth/login',data={'email':'admin@vyra.local','password':'Admin-browser-123'},headers=headers)
                for name in ['bruno','carol']:
                    r=ctx.request.post(url+'/api/admin/users',data={'name':name.title(),'username':name,'email':name+'@example.com','password':'Customer-test-123','plan_id':'premium'},headers=headers)
                    assert r.status==201,r.text()
                host=ctx.new_page();errors=[];host.on('pageerror',lambda e:errors.append(str(e)))
                host.goto(url);host.get_by_role('button',name='FlixJump e amigos').wait_for()
                host.evaluate("play('horizonte')")
                host.wait_for_function('player?.ready')
                host.evaluate('player.video.pause()')
                host.get_by_role('button',name='Criar sala FlixJump',exact=True).click()
                host.get_by_label('Link de convite da sala',exact=True).wait_for()
                link=host.get_by_label('Link de convite da sala',exact=True).input_value()
                assert link.startswith(url+'/sala/')
                host.get_by_role('button',name='Copiar link',exact=True).click()
                assert host.evaluate('navigator.clipboard.readText()')==link
                host.screenshot(path=str(output/'flixjump-room-link.png'))
                host.get_by_role('button',name='Fechar painel',exact=True).click()
                guest_ctx=browser.new_context(viewport={'width':1100,'height':800},bypass_csp=True)
                guest=guest_ctx.new_page();guest.on('pageerror',lambda e:errors.append(str(e)))
                response=guest.goto(link)
                assert response.status==200
                guest.get_by_role('button',name='Entrar e solicitar acesso',exact=True).click()
                guest.locator('#auth-email').fill('bruno@example.com')
                guest.locator('#auth-password').fill('Customer-test-123')
                guest.get_by_role('button',name='Entrar na minha conta',exact=True).click()
                guest.get_by_text('Aguardando o anfitrião',exact=True).wait_for()
                assert guest.url==link
                assert guest.locator('#video-player').count()==0
                rid=link.rsplit('/',1)[1]
                assert guest_ctx.request.post(url+'/api/jump/rooms/'+rid+'/poll',data={},headers=headers).status==403
                host.locator('.fj-entry-notice').get_by_text('Bruno',exact=True).wait_for()
                host.screenshot(path=str(output/'flixjump-approve-desktop.png'))
                host.set_viewport_size({'width':390,'height':844})
                host.screenshot(path=str(output/'flixjump-approve-mobile.png'))
                rect=host.locator('.fj-entry-notice').bounding_box()
                assert rect['x']>=0 and rect['x']+rect['width']<=390,rect
                host.locator('.fj-entry-notice').get_by_role('button',name='Aceitar',exact=True).click()
                guest.wait_for_function('player?.jump?.members.length===2')
                host.wait_for_function('player?.jump?.members.length===2')
                assert not host.locator('.fj-entry-notice').is_visible()
                host.set_viewport_size({'width':1440,'height':1000})
                other_ctx=browser.new_context(bypass_csp=True)
                other_ctx.request.post(url+'/api/auth/login',data={'email':'carol@example.com','password':'Customer-test-123'},headers=headers)
                other=other_ctx.new_page();other.on('pageerror',lambda e:errors.append(str(e)))
                other.goto(link)
                other.get_by_text('Aguardando o anfitrião',exact=True).wait_for()
                host.locator('.fj-entry-notice').get_by_text('Carol',exact=True).wait_for()
                other.get_by_role('button',name='Cancelar e voltar ao catálogo',exact=True).click()
                host.locator('.fj-entry-notice').wait_for(state='hidden')
                other.goto(link)
                host.locator('.fj-entry-notice').get_by_text('Carol',exact=True).wait_for()
                host.locator('.fj-entry-notice').get_by_role('button',name='Recusar',exact=True).click()
                other.get_by_text('Sua entrada não foi aceita',exact=True).wait_for()
                other.reload()
                other.get_by_text('Sua entrada não foi aceita',exact=True).wait_for()
                assert other.locator('#video-player').count()==0
                assert not host.locator('.fj-entry-notice').is_visible()
                assert guest.evaluate('player.jump.requests.length')==0
                host.get_by_role('button',name='Minha sala FlixJump',exact=True).click()
                host.get_by_role('button',name='Encerrar para todos',exact=True).click()
                host.get_by_role('button',name='Encerrar sala',exact=True).click()
                other.reload()
                other.get_by_text('Esta sala foi encerrada ou o código é inválido.',exact=True).wait_for()
                assert not errors,errors
                browser.close()
                print(json.dumps({'ok':True,'checks':['visible create button','copy invitation link','anonymous link and login return','pending entry without chat access','host notification on desktop and mobile','approval opens player','cancel removes request','rejection survives reload','closed room error']},ensure_ascii=False))
        finally:server.shutdown()

if __name__=='__main__':run()
