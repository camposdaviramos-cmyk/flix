"""Every community activity opens the reference chat screen on mobile and installed PWA."""
import json, sqlite3, sys, tempfile, threading
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler
H={'X-Requested-With':'Flix'}
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True)
 with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:
  db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
 server=make_server('127.0.0.1',8148,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8148'
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox'])
   mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
   pwa=browser.new_context(viewport={'width':1024,'height':900})
   pwa.add_init_script("const realMatch=window.matchMedia.bind(window);window.matchMedia=q=>{const r=realMatch(q);if(q==='(display-mode: standalone)')Object.defineProperty(r,'matches',{value:true});return r;}")
   for context in (mobile,pwa):assert context.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'}).ok
   pages=[mobile.new_page(),pwa.new_page()];errors=[]
   for p in pages:
    p.on('pageerror',lambda e:errors.append(str(e)))
    p.route('https://media.example.test/**',lambda r:r.fulfill(path=str(ROOT/'static/assets/sintel-trailer.mp4'),content_type='video/mp4'))
   checked=[]
   def check(p):
    expect(p.locator('.rm-tabs [data-tab=chat]')).to_have_attribute('aria-current','page',timeout=15000)
    expect(p.locator('#cm-room-chat')).to_be_visible()
    expect(p.locator('.rm-avatar-strip')).to_be_visible()
    expect(p.locator('.rm-visual')).to_be_visible()
    expect(p.locator('.rm-panel-screen')).not_to_be_visible()
    assert not p.evaluate('document.activeElement.matches("input,textarea")')
    assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
    rect=p.locator('.rm-tabs').bounding_box();assert rect['y']+rect['height']<=p.viewport_size['height']+1
   for activity in ('watch','movie','series','tv','music','voice','video','live','games'):
    kind='watch' if activity in ('movie','series','tv') else 'voice' if activity=='games' else activity
    d={'title':'Sala '+activity,'kind':kind,'activity':activity,'approval':False,'permanent':True}
    if kind in ('watch','music'):d['url']='https://media.example.test/trailer.mp4'
    if activity=='games':d['game_kind']='colors'
    response=mobile.request.post(url+'/api/community/rooms',headers=H,data=d);assert response.ok,response.text();rid=response.json()['room']['id']
    for p in pages:
     p.goto(url+'/comunidade/sala/'+rid);check(p)
     p.locator('.rm-tabs [data-tab=media]').click();expect(p.locator('.rm-tool-tabs')).to_be_visible()
     p.reload();check(p)
    checked.append(activity)
   # Back/forward navigation also remounts the reference screen, without keeping the settings tab.
   p=pages[0];p.locator('.rm-tabs [data-tab=more]').click();p.goto(url+'/comunidade');p.go_back();check(p)
   assert not errors,errors
   print(json.dumps({'default_chat_activities':checked,'mobile':True,'standalone_pwa':True,'reload':True,'history':True,'no_keyboard_autofocus':True,'errors':errors}))
   browser.close()
 finally:server.shutdown()
