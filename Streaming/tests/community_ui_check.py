"""Strict CSP and mobile administration layout smoke checks."""
import sqlite3,sys,tempfile,threading,json
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler
with tempfile.TemporaryDirectory() as folder:
    app=create_app(folder,testing=True)
    with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
    server=make_server('127.0.0.1',8133,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox'])
            ctx=browser.new_context(viewport={'width':390,'height':844});url='http://localhost:8133'
            ctx.request.post(url+'/api/auth/login',data={'email':'admin@vyra.local','password':'Admin-browser-123'},headers={'X-Requested-With':'VYRA'})
            page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.add_init_script("window.cspErrors=[];document.addEventListener('securitypolicyviolation',e=>window.cspErrors.push(e.violatedDirective+':'+e.blockedURI));")
            for path,title in [('/comunidade','Página inicial'),('/comunidade?tab=rooms','Tem lugar para você.'),('/comunidade?tab=ranking','Ranking de membros'),('/admin?tab=community','Comunidade sob seu cuidado.'),('/admin?tab=community-reports','Comunidade sob seu cuidado.'),('/admin?tab=community-social','Stories, mídia e jogos.'),('/admin?tab=community-badges','Comunidade sob seu cuidado.')]:
                page.goto(url+path);page.get_by_role('heading',name=title,exact=True).wait_for();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),path;assert page.evaluate('window.cspErrors')==[],page.evaluate('window.cspErrors');assert not errors,errors
            page.screenshot(path=str(ROOT/'test-results/community-admin-mobile.png'),full_page=True)
            # Verify modal editor remains visible while animations are paused.
            page.get_by_role('button',name='Criar emblema',exact=True).click();assert page.locator('#modal').is_visible();assert page.locator('#cm-admin-badge').is_visible()
            page.get_by_label('Nome',exact=True).fill('Pioneiro');page.get_by_role('button',name='Salvar emblema',exact=True).click();page.locator('.cm-badge').get_by_text('Pioneiro',exact=True).wait_for()
            print(json.dumps({'strict_csp':True,'mobile_admin':True,'page_errors':errors}));browser.close()
    finally:server.shutdown()
