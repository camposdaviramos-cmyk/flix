"""Paused dialogs and free trial registration, using an isolated temporary database."""
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
        server=make_server('127.0.0.1',8130,app,threaded=True,request_handler=QuietHandler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        url='http://localhost:8130';headers={'X-Requested-With':'VYRA'};output=ROOT/'test-results'
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox'])
                ctx=browser.new_context(viewport={'width':1440,'height':1000},bypass_csp=True,reduced_motion='reduce')
                ctx.add_init_script("localStorage.setItem('vyra-motion-paused','true')")
                ctx.request.post(url+'/api/auth/login',data={'email':'admin@vyra.local','password':'Admin-browser-123'},headers=headers)
                page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(url+'/admin?tab=users')
                page.get_by_role('button',name='Cadastrar usuário',exact=True).click()
                assert page.locator('#modal').evaluate('(e)=>getComputedStyle(e).opacity')=='1'
                assert page.locator('#modal').evaluate('(e)=>getComputedStyle(e).filter')=='none'
                page.locator('#f-name').fill('Cadastro Visível')
                page.locator('#f-username').fill('visivel')
                page.locator('#f-email').fill('visivel@example.com')
                page.locator('#f-password').fill('Customer-test-123')
                page.locator('#f-plan_id').select_option('premium')
                page.screenshot(path=str(output/'admin-create-user-fixed.png'))
                page.locator('#new-user-form [type=submit]').click()
                page.locator('#modal').wait_for(state='hidden')
                page.get_by_text('Cadastro Visível',exact=True).wait_for()
                # OS reduced motion and background-tab pause must also keep dialogs usable.
                page.emulate_media(reduced_motion='reduce')
                page.get_by_role('button',name='Cadastrar usuário',exact=True).click()
                assert page.locator('#modal').evaluate('(e)=>getComputedStyle(e).opacity')=='1'
                page.locator('#f-name').fill('Acessível')
                page.get_by_role('button',name='Cancelar',exact=True).click()
                page.emulate_media(reduced_motion='no-preference')
                page.evaluate("document.documentElement.classList.add('vx-hidden-tab')")
                page.get_by_role('button',name='Cadastrar usuário',exact=True).click()
                assert page.locator('#modal').evaluate('(e)=>getComputedStyle(e).opacity')=='1'
                page.get_by_role('button',name='Cancelar',exact=True).click()
                page.evaluate("document.documentElement.classList.remove('vx-hidden-tab')")
                page.get_by_role('link',name='Cupons',exact=True).click()
                page.get_by_role('button',name='Criar cupom',exact=True).click()
                page.locator('#f-code').fill('TESTE6H')
                page.locator('#f-coupon-plan').select_option('premium')
                page.locator('#f-trial-unit').select_option('hours')
                page.locator('#f-trial_duration').fill('6')
                page.locator('#f-max_uses').fill('2')
                page.get_by_role('button',name='Salvar cupom',exact=True).click()
                page.locator('#modal').wait_for(state='hidden')
                page.get_by_text('TESTE6H',exact=True).wait_for()
                page.get_by_role('button',name='Desativar cupom TESTE6H',exact=True).click()
                page.get_by_role('button',name='Ativar cupom TESTE6H',exact=True).click()
                page.get_by_role('button',name='Desativar cupom TESTE6H',exact=True).wait_for()
                page.screenshot(path=str(output/'admin-coupons.png'))
                guest_ctx=browser.new_context(viewport={'width':1100,'height':900},bypass_csp=True,reduced_motion='reduce')
                guest_ctx.add_init_script("localStorage.setItem('vyra-motion-paused','true')")
                guest=guest_ctx.new_page();guest.on('pageerror',lambda e:errors.append(str(e)))
                checkout_requests=[]
                guest.on('request',lambda r:checkout_requests.append(r.url) if '/api/checkout' in r.url or '/api/payments/' in r.url or 'mercadopago.com/checkout' in r.url else None)
                guest.goto(url+'/planos')
                guest.locator('[data-action=subscribe][data-id=premium]').click()
                guest.locator('#auth-name').fill('Cliente do Teste')
                guest.locator('#auth-username').fill('cliente_teste')
                guest.locator('#auth-email').fill('trial@example.com')
                guest.locator('#auth-password').fill('Customer-test-123')
                guest.locator('[name=terms]').check()
                guest.locator('#auth-coupon').fill('INVALIDO')
                guest.get_by_role('button',name='Aplicar',exact=True).click()
                guest.locator('#coupon-feedback').get_by_text('Cupom inválido ou desativado.',exact=True).wait_for()
                guest.locator('#auth-form [type=submit]').click()
                guest.locator('#auth-form .form-error').get_by_text('Cupom inválido ou desativado.',exact=True).wait_for()
                assert guest_ctx.request.get(url+'/api/bootstrap').json()['user'] is None
                guest.locator('#auth-coupon').fill('teste6h')
                guest.get_by_role('button',name='Aplicar',exact=True).click()
                guest.get_by_role('button',name='Começar teste grátis',exact=True).wait_for()
                guest.set_viewport_size({'width':390,'height':844})
                guest.locator('#auth-coupon').scroll_into_view_if_needed()
                guest.screenshot(path=str(output/'signup-free-trial-mobile.png'))
                assert guest.locator('#modal').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
                guest.get_by_role('button',name='Começar teste grátis',exact=True).click()
                guest.locator('#modal').wait_for(state='hidden')
                guest.wait_for_function('state.user?.subscribed===true')
                boot=guest_ctx.request.get(url+'/api/bootstrap').json()
                assert abs(boot['user']['expires_at']-time.time()-6*3600)<10,boot['user']['expires_at']
                assert guest_ctx.request.get(url+'/api/play/horizonte').status==200
                assert not checkout_requests,checkout_requests
                page.reload()
                page.get_by_text('1 / 2',exact=True).wait_for()
                page.get_by_role('button',name='Editar cupom TESTE6H',exact=True).click()
                page.locator('#f-trial_duration').fill('12')
                page.get_by_role('button',name='Salvar cupom',exact=True).click()
                page.locator('#modal').wait_for(state='hidden')
                page.get_by_text('12 horas',exact=True).wait_for()
                assert guest_ctx.request.get(url+'/api/bootstrap').json()['user']['expires_at']==boot['user']['expires_at']
                # Without a coupon, registration still shows the paid checkout confirmation.
                normal_ctx=browser.new_context(bypass_csp=True,reduced_motion='reduce')
                normal=normal_ctx.new_page();normal.on('pageerror',lambda e:errors.append(str(e)))
                normal.goto(url+'/planos')
                normal.locator('[data-action=subscribe][data-id=premium]').click()
                normal.locator('#auth-name').fill('Cliente Regular')
                normal.locator('#auth-username').fill('cliente_regular')
                normal.locator('#auth-email').fill('regular@example.com')
                normal.locator('#auth-password').fill('Customer-test-123')
                normal.locator('[name=terms]').check()
                normal.locator('#auth-form [type=submit]').click()
                normal.get_by_role('heading',name='Falta só um passo.',exact=True).wait_for()
                normal.get_by_role('button',name='Ir para o pagamento',exact=True).wait_for()
                assert not normal_ctx.request.get(url+'/api/bootstrap').json()['user']['subscribed']
                assert not errors,errors
                browser.close()
                print(json.dumps({'ok':True,'checks':['paused admin dialog visible and submits','reduced-motion dialog','hidden-tab animation fallback','coupon create edit deactivate reactivate','invalid coupon leaves account uncreated','coupon preview','mobile registration','immediate trial access without checkout','existing trial preserved after edit','normal signup payment confirmation']},ensure_ascii=False))
        finally:server.shutdown()

if __name__=='__main__':run()
