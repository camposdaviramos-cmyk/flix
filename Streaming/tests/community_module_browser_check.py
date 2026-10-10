"""Toggle through the admin UI and verify live tabs, mobile and direct navigation."""
import json,sqlite3,sys,tempfile,threading
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from waitress import create_server
from werkzeug.security import generate_password_hash
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));from app import create_app
OUT=ROOT/'test-results/community-module';OUT.mkdir(parents=True,exist_ok=True)
base='http://127.0.0.1:8031';h={'X-Requested-With':'Flix'}
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True)
 with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Module-browser-test-2026'),))
 server=create_server(app,host='127.0.0.1',port=8031,threads=8);threading.Thread(target=server.run,daemon=True).start()
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(args=['--no-sandbox']);admin=browser.new_context(reduced_motion='reduce');guest=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,reduced_motion='reduce');errors=[]
   assert admin.request.post(base+'/api/auth/login',data={'email':'admin@vyra.local','password':'Module-browser-test-2026'},headers=h).status==200
   a=admin.new_page();g=guest.new_page()
   for page in [a,g]:page.on('pageerror',lambda e:errors.append(str(e)))
   g.goto(base);g.wait_for_selector('[data-react-page=home]');assert g.locator('#main-nav a[href="/comunidade"]').count()==1
   a.goto(base+'/admin?tab=settings');a.get_by_label('Módulo comunidade',exact=True).wait_for();assert a.get_by_label('Módulo comunidade',exact=True).input_value()=='true'
   a.get_by_label('Módulo comunidade',exact=True).select_option('false');
   with a.expect_navigation(wait_until='load'):
    a.get_by_role('button',name='Salvar comunidade',exact=True).click()
   expect(a.get_by_label('Módulo comunidade',exact=True)).to_have_value('false');a.get_by_label('Módulo comunidade',exact=True).wait_for();assert a.locator('.admin-nav a[href*="community"], .admin-nav a[href*="spaces"], .admin-nav a[href*="music"], .admin-nav a[href*="economy"], .admin-nav a[href*="verifications"]').count()==0;assert a.locator('#settings-form').count()==1;a.screenshot(path=str(OUT/'admin-disabled.png'))
   # Simulate tab returning to foreground: same update check as the 30s timer.
   
   with g.expect_navigation(wait_until='load'):
    g.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
   g.wait_for_selector('[data-react-page=home]');assert g.locator('#main-nav a[href="/comunidade"]').count()==0
   assert g.evaluate('document.documentElement.scrollWidth<=innerWidth')
   a.goto(base+'/conta');a.wait_for_selector('[data-react-page=account]');assert a.locator('[data-hub], [data-jump], a[href^="/comunidade"],a[href="/carteira"]').count()==0
   assert a.get_by_role('link',name='Escanear QR Code',exact=True).count()>0
   assert not a.evaluate("Array.from(document.scripts).some(s=>/\\/(community|social-hub|jump)\\.js/.test(s.src))")
   g.evaluate("navigate('/comunidade')");g.get_by_role('heading',name='Comunidade indisponível',exact=True).wait_for()
   response=g.goto(base+'/comunidade/sala/123456789012');assert response.status==503;g.get_by_role('link',name='Voltar à WorkTV').wait_for()
   a.goto(base+'/admin?tab=settings');a.get_by_label('Módulo comunidade',exact=True).select_option('true');
   with a.expect_navigation(wait_until='load'):
    a.get_by_role('button',name='Salvar comunidade',exact=True).click()
   expect(a.get_by_label('Módulo comunidade',exact=True)).to_have_value('true');a.get_by_label('Módulo comunidade',exact=True).wait_for();assert a.locator('.admin-nav a[href="/admin?tab=community"]').count()==1;a.screenshot(path=str(OUT/'admin-enabled.png'))
   g.goto(base);g.wait_for_selector('[data-react-page=home]');assert g.locator('#main-nav a[href="/comunidade"]').count()==1
   assert not errors,errors
   result={'status':'PASS','admin_toggle':True,'open_tab_update':True,'direct_route_blocked':True,'mobile_navigation_hidden':True,'social_bundles_not_loaded_when_disabled':True,'qr_and_account_available':True,'reenable':True,'page_errors':errors};(OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));browser.close()
 finally:server.close()
