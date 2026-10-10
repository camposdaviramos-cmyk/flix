"""End-to-end QR approval, three profiles and MFA in independent browser contexts."""
import json,os,sys,tempfile,threading,sqlite3,uuid
from pathlib import Path
import pyotp
from playwright.sync_api import sync_playwright
from waitress import create_server
from werkzeug.security import generate_password_hash
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from app import create_app
from migrate_postgres import migrate
OUT=ROOT/'test-results/account-access';OUT.mkdir(parents=True,exist_ok=True)
base='http://127.0.0.1:8028';password='Browser-Access-2026-only';headers={'X-Requested-With':'Flix'}
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True)
 with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash(password),))
 schema=None;dsn=os.getenv('WORKTV_TEST_DATABASE_URL')
 if dsn:
  import psycopg
  from psycopg.conninfo import make_conninfo
  schema='browser_'+uuid.uuid4().hex
  with psycopg.connect(dsn,autocommit=True) as db:db.execute('CREATE SCHEMA '+schema)
  scoped=make_conninfo(dsn,options='-c search_path='+schema);migrate(Path(folder)/'vyra.sqlite3',scoped,Path(folder)/'migration.json');app=create_app(folder,testing=True,database_url=scoped)
 app.config['ADMIN_MFA_REQUIRED']=True
 server=create_server(app,host='127.0.0.1',port=8028,threads=8);threading.Thread(target=server.run,daemon=True).start()
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(args=['--no-sandbox','--enable-unsafe-swiftshader']);errors=[]
   tv=browser.new_context(viewport={'width':1920,'height':1080},reduced_motion='reduce');phone=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,reduced_motion='reduce')
   t=tv.new_page();p=phone.new_page()
   for page in [t,p]:page.on('pageerror',lambda e:errors.append(str(e)))
   # Administrator enrolls MFA before authorizing a TV.
   result=phone.request.post(base+'/api/auth/login',data={'email':'admin@vyra.local','password':password},headers=headers);assert result.status==200
   p.goto(base+'/conta');p.wait_for_selector('[data-react-page=account]');p.get_by_role('button',name='Ativar proteção',exact=True).click();p.locator('#mfa-password').fill(password);p.locator('.security-settings').get_by_role('button',name='Continuar',exact=True).click();p.locator('.mfa-secret').wait_for();secret=p.locator('.mfa-secret').inner_text();p.locator('#mfa-code').fill(pyotp.TOTP(secret).now());p.get_by_role('button',name='Confirmar ativação',exact=True).click();p.locator('.recovery-codes').wait_for();codes=p.locator('.recovery-codes').inner_text().splitlines();assert len(codes)==10;p.get_by_role('button',name='Guardei os códigos').click()
   t.goto(base+'/');t.wait_for_selector('[data-react-page=home]');
   with t.expect_response('**/api/auth/device/start') as pending:t.locator('.header [data-action=login]').click()
   grant=pending.value.json();t.locator('.login-qr').wait_for();t.screenshot(path=str(OUT/'tv-qr.png'))
   p.goto(grant['activation_url']);p.get_by_role('button',name='Confirmar entrada').wait_for();assert p.locator('.device-match').inner_text()==grant['code'];assert '#' not in p.url
   assert not tv.request.get(base+'/api/bootstrap').json()['user'];p.screenshot(path=str(OUT/'phone-approve.png'));p.get_by_role('button',name='Confirmar entrada').click();t.wait_for_selector('[data-react-page=member-home]',timeout=15000)
   assert tv.request.get(base+'/api/bootstrap').json()['user']['role']=='admin'
   t.evaluate("navigate('/perfis')");t.wait_for_selector('[data-react-page=profiles]');t.locator('.profile-card').wait_for()
   for name in ['Cinema','Família']:
    t.get_by_role('button',name='Adicionar perfil').click();t.locator('#profile-name').fill(name);t.get_by_role('button',name='Salvar perfil').click();t.get_by_role('button',name='Salvar perfil').wait_for(state='hidden')
   assert t.locator('.profile-card').count()==3;assert t.get_by_role('button',name='Adicionar perfil').count()==0
   t.locator('.profile-card').filter(has_text='Administrador').get_by_role('button',name='Editar',exact=True).click();assert t.locator('#profile-name').input_value()=='Administrador'
   t.locator('.profile-card').filter(has_text='Cinema').get_by_role('button',name='Editar',exact=True).click();assert t.locator('#profile-name').input_value()=='Cinema';t.get_by_role('button',name='Cancelar',exact=True).click()
   t.screenshot(path=str(OUT/'profiles-tv.png'));t.locator('.profile-select').filter(has_text='Cinema').click();t.wait_for_selector('[data-react-page=member-home]');assert tv.request.get(base+'/api/bootstrap').json()['profile']['name']=='Cinema'
   p.goto(base+'/perfis');p.wait_for_selector('.profile-card');assert p.evaluate('document.documentElement.scrollWidth<=innerWidth');p.screenshot(path=str(OUT/'profiles-mobile.png'))
   # Password alone must not authenticate; a recovery code completes React login.
   tv.request.post(base+'/api/auth/logout',data={},headers=headers);t.goto(base+'/');t.wait_for_selector('[data-react-page=home]');t.locator('.header [data-action=login]').click();t.locator('#auth-email').fill('admin@vyra.local');t.locator('#auth-password').fill(password);t.get_by_role('button',name='Entrar na minha conta',exact=True).click();t.locator('input[name=code]').wait_for();assert not tv.request.get(base+'/api/bootstrap').json()['user'];t.locator('input[name=code]').fill(codes[0]);t.get_by_role('button',name='Entrar na minha conta',exact=True).click();t.wait_for_selector('[data-react-page=member-home]')
   assert not errors,errors
   result={'status':'PASS','backend':'postgresql' if dsn else 'sqlite','qr_phone_to_tv':True,'mfa_login':True,'profiles_three':True,'mobile_overflow':False,'page_errors':errors};(OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));browser.close()
 finally:
  server.close()
  if schema:
   app.extensions['database'].close()
   with psycopg.connect(dsn,autocommit=True) as db:db.execute('DROP SCHEMA '+schema+' CASCADE')
