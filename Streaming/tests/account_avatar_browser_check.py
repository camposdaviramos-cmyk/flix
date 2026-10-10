import json,sqlite3,sys,tempfile,threading
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from waitress import create_server
from werkzeug.security import generate_password_hash
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));from app import create_app
from test_account_avatar import sample_png
OUT=ROOT/'test-results/account-avatar';OUT.mkdir(parents=True,exist_ok=True);base='http://127.0.0.1:8032';h={'X-Requested-With':'Flix'}
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True)
 with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:
  db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Avatar-browser-test-2026'),))
  db.execute("INSERT INTO settings(key,value) VALUES('community_enabled','false')")
  uid=db.execute("SELECT id FROM users WHERE role='admin'").fetchone()[0]
  db.execute('INSERT INTO community_profiles(user_id,avatar,avatar_png,updated_at) VALUES(?,?,?,?)',(uid,'/api/community/avatars/'+uid+'?v=1',sample_png(),1))
 server=create_server(app,host='127.0.0.1',port=8032,threads=8);threading.Thread(target=server.run,daemon=True).start()
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(args=['--no-sandbox']);context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce');assert context.request.post(base+'/api/auth/login',data={'email':'admin@vyra.local','password':'Avatar-browser-test-2026'},headers=h).status==200
   page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(base+'/conta');page.wait_for_selector('[data-react-page=account]');page.locator('.wt-account-menu img').evaluate('(i)=>i.decode()')
   assert page.locator('script[src*="social-spaces.js"]').count()==0
   for width in [1440,390]:
    page.set_viewport_size({'width':width,'height':1000});menu=page.locator('.wt-account-menu');summary=menu.locator('summary');before=page.locator('.header').bounding_box()['height'];summary.click();expect(menu).to_have_attribute('open','')
    panel=menu.locator(':scope > div');box=panel.bounding_box();assert box and box['x']>=0 and box['x']+box['width']<=width
    assert abs(page.locator('.header').bounding_box()['height']-before)<2
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert menu.locator('a[href^="/comunidade"]').count()==0
    page.screenshot(path=str(OUT/f'menu-{width}.png'));page.keyboard.press('Escape');expect(menu).not_to_have_attribute('open','');expect(summary).to_be_focused()
    summary.click();page.get_by_role('heading',name='Foto da conta',exact=True).click();expect(menu).not_to_have_attribute('open','')
   page.get_by_label('Escolher foto',exact=True).set_input_files({'name':'avatar.png','mimeType':'image/png','buffer':sample_png()});page.get_by_alt_text('Prévia do novo avatar').wait_for();page.get_by_role('button',name='Salvar avatar',exact=True).click();expect(page.get_by_alt_text('Prévia do novo avatar')).to_have_count(0)
   page.locator('.wt-account-menu img').evaluate('(i)=>i.decode()');assert page.locator('.wt-account-menu img').get_attribute('src').startswith('/api/account/avatar?')
   page.reload();page.wait_for_selector('[data-react-page=account]');page.locator('.wt-account-menu img').evaluate('(i)=>i.decode()');page.screenshot(path=str(OUT/'avatar-mobile.png'))
   page.get_by_role('button',name='Remover foto',exact=True).click();expect(page.locator('.wt-account-menu img')).to_have_count(0);expect(page.locator('.wt-account-menu summary')).to_have_text('A')
   # Enable community: the same core menu must work with social styles loaded too.
   assert context.request.put(base+'/api/admin/modules/community',data={'enabled':True},headers=h).status==200
   page.reload();page.wait_for_selector('[data-react-page=account]');page.locator('.wt-account-menu summary').click();assert page.locator('.wt-account-menu a[href^="/comunidade"]').is_visible();box=page.locator('.wt-account-menu > div').bounding_box();assert box['x']>=0 and box['x']+box['width']<=390
   assert not errors,errors
   result={'status':'PASS','existing_avatar_visible_when_disabled':True,'desktop_and_mobile_menu':True,'escape_and_outside_close':True,'header_no_layout_shift':True,'upload_preview_save_persist_remove':True,'community_on_and_off':True,'page_errors':errors};(OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));browser.close()
 finally:server.close()
