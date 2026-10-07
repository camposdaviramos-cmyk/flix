"""Real Chromium keyboard/player/PWA tests; isolated DB, never production accounts.
UA emulation is NOT a Samsung/LG engine certification.
"""
import json,sys,tempfile,threading,sqlite3,time
from pathlib import Path
from playwright.sync_api import sync_playwright
from waitress import create_server
from werkzeug.security import generate_password_hash
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
OUT=ROOT/'test-results/tv';OUT.mkdir(parents=True,exist_ok=True)
def poll(p,expression,timeout=15000):
 end=time.monotonic()+timeout/1000
 while time.monotonic()<end:
  if p.evaluate(expression):return
  p.wait_for_timeout(100)
 raise AssertionError(expression)
def remote(p,code):p.evaluate('(code)=>document.activeElement.dispatchEvent(new KeyboardEvent("keydown",{keyCode:code,bubbles:true,cancelable:true}))',code)
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True)
 with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=? WHERE email='admin@vyra.local'",(generate_password_hash('Test-TV-only-2026'),))
 server=create_server(app,host='127.0.0.1',port=8023,threads=12);threading.Thread(target=server.run,daemon=True).start()
 try:
  with sync_playwright() as pw:
   b=pw.chromium.launch(args=['--no-sandbox','--enable-unsafe-swiftshader'])
   c=b.new_context(viewport={'width':1280,'height':720});p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
   p.goto('http://127.0.0.1:8023/?tv=1',wait_until='domcontentloaded');p.wait_for_selector('.wt-hero')
   poll(p,'document.activeElement.matches(".header nav a")')
   assert p.evaluate('window.WorkTVPlatform.tv');assert p.locator('.vx-motion-toggle').count()==0
   p.keyboard.press('ArrowRight');assert p.evaluate('document.activeElement.getAttribute("href")')=='/filmes'
   p.keyboard.press('Enter');p.wait_for_url('**/filmes');p.wait_for_selector('.catalog-grid')
   poll(p,'document.activeElement.matches(".header nav a.active")')
   # Reach the catalog using only directional navigation.
   for _ in range(12):
    p.keyboard.press('ArrowDown')
    if p.evaluate('document.activeElement.matches(".poster-button")'):break
   assert p.evaluate('document.activeElement.matches(".poster-button")'),p.evaluate('document.activeElement.outerHTML')
   first=p.evaluate('document.activeElement.dataset.id');p.keyboard.press('ArrowRight');assert p.evaluate('document.activeElement.dataset.id')!=first
   remembered=p.evaluate('document.activeElement.dataset.id');p.keyboard.press('Enter');p.wait_for_url('**/titulo/*');p.wait_for_selector('main .detail-body')
   remote(p,10009);p.wait_for_url('**/filmes');poll(p,'document.activeElement.matches(".poster-button")')
   assert p.evaluate('document.activeElement.dataset.id')==remembered
   print('PASS remote navigation and Samsung Back restores card focus',flush=True)
   # Login modal, no trapped input, LG Back restores the initiating button.
   p.locator('[data-action=login]').first.focus();p.keyboard.press('Enter');p.wait_for_selector('#auth-email')
   poll(p,'document.activeElement.id==="auth-email"')
   p.keyboard.type('admin@vyra.local');p.keyboard.press('ArrowDown');assert p.evaluate('document.activeElement.id')=='auth-password'
   p.keyboard.type('Test-TV-only-2026');remote(p,461);p.wait_for_selector('#modal',state='hidden');assert p.evaluate('document.activeElement.dataset.action')=='login'
   p.keyboard.press('Enter');p.locator('#auth-email').fill('admin@vyra.local');p.keyboard.press('ArrowDown');p.keyboard.type('Test-TV-only-2026');p.keyboard.press('ArrowDown');p.keyboard.press('Enter');p.wait_for_selector('#modal',state='hidden')
   poll(p,'!!state.user')
   print('PASS login with remote and LG Back',flush=True)
   p.locator('.header [data-hub=chat]').focus();p.keyboard.press('Enter');p.wait_for_selector('#fh-messenger:not([hidden])')
   poll(p,'!!document.activeElement.closest("#fh-messenger")')
   for _ in range(8):
    p.keyboard.press('Tab');assert p.evaluate('!!document.activeElement.closest("#fh-messenger")')
   remote(p,461);p.wait_for_selector('#fh-messenger',state='hidden')
   p.locator('[data-pwa-install]').focus();p.keyboard.press('Enter');p.wait_for_selector('.wt-install-help')
   remote(p,10009);p.wait_for_selector('#modal',state='hidden')
   print('PASS social panel focus containment, Back and installation guidance',flush=True)
   # Local H.264 video through the actual application playback/progress path.
   p.goto('http://127.0.0.1:8023/titulo/horizonte');p.wait_for_selector('[data-action=play]');p.locator('[data-action=play]').first.focus();p.keyboard.press('Enter')
   p.wait_for_selector('#video-player');poll(p,'document.querySelector("#video-player").readyState>=2',30000)
   p.wait_for_selector('.wt-tv-player-controls');remote(p,19);assert p.locator('#video-player').evaluate('(v)=>v.paused')
   remote(p,415);poll(p,'!document.querySelector("#video-player").paused')
   poll(p,'document.querySelector("#video-player").currentTime>0')
   remote(p,19);before=p.locator('#video-player').evaluate('(v)=>v.currentTime');remote(p,417);poll(p,f'document.querySelector("#video-player").currentTime>{before+8}')
   p.locator('[data-tv-play=toggle]').focus();p.keyboard.press('ArrowRight');
   assert p.evaluate('document.activeElement.dataset.tvPlay')=='forward'
   assert p.locator('.wt-tv-player-controls').bounding_box()['y']+p.locator('.wt-tv-player-controls').bounding_box()['height']<=720
   p.screenshot(path=str(OUT/'player-720.png'))
   # A remote must not bypass a shared session's playback policy.
   p.evaluate('window.savedTVSeek=FlixJump.canSeekPlayback;FlixJump.canSeekPlayback=()=>false')
   before=p.locator('#video-player').evaluate('(v)=>v.currentTime');remote(p,417)
   assert abs(p.locator('#video-player').evaluate('(v)=>v.currentTime')-before)<.1
   p.evaluate('FlixJump.canSeekPlayback=window.savedTVSeek')
   p.locator('[data-tv-play=fullscreen]').focus();p.keyboard.press('Enter');poll(p,'!!document.fullscreenElement')
   remote(p,461);poll(p,'!document.fullscreenElement');assert p.locator('#modal').is_visible()
   remote(p,461);p.wait_for_selector('#modal',state='hidden');assert p.locator('video').count()==0
   print('PASS real MP4 playback, media keys, seek, close',flush=True)
   # Ensure layouts at real logical TV sizes and UHD. No UA pretence about engines.
   for width,height in [(960,540),(1280,720),(1920,1080),(3840,2160)]:
    p.set_viewport_size({'width':width,'height':height})
    p.goto('http://127.0.0.1:8023/filmes');p.wait_for_selector('.catalog-grid');p.wait_for_timeout(300)
    assert p.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
    assert p.locator('.header nav').is_visible()
    assert p.locator('.header nav').evaluate('(e)=>e.getBoundingClientRect().bottom<=e.closest("header").getBoundingClientRect().bottom')
    p.locator('.poster-button').first.focus();p.screenshot(path=str(OUT/f'catalog-{width}.png'))
   print('PASS 540p, 720p, 1080p, 4K layouts',flush=True)
   # SW controls visitors too and never stores a private API response or movie.
   guest=b.new_context(viewport={'width':1280,'height':720});g=guest.new_page();g.on('pageerror',lambda e:errors.append(str(e)))
   g.goto('http://127.0.0.1:8023/filmes?tv=1');g.wait_for_selector('.catalog-grid');poll(g,'!!navigator.serviceWorker.controller')
   g.reload();g.wait_for_selector('.catalog-grid');g.evaluate('fetch("/api/bootstrap").then(r=>r.json())')
   keys=g.evaluate('async()=>{const out=[];for(const name of await caches.keys()){const c=await caches.open(name);out.push(...(await c.keys()).map(r=>r.url));}return out;}')
   assert not any('/api/' in key or '.mp4' in key for key in keys),keys
   guest.set_offline(True);g.goto('http://127.0.0.1:8023/series?tv=1');g.get_by_role('heading',name='Sua conexão fez uma pausa.').wait_for()
   assert g.evaluate('document.activeElement.id')=='retry';assert '/series?tv=1' in g.locator('#retry').get_attribute('href')
   g.screenshot(path=str(OUT/'offline-tv.png'));guest.set_offline(False);g.wait_for_selector('.catalog-grid',timeout=30000)
   assert '/series' in g.url
   print('PASS guest PWA, private cache exclusion, offline remote and reconnect',flush=True)
   # TV UA activation + explicit opt-out. Modern Chromium only, not the vendor runtime.
   for ua in ['Mozilla/5.0 (SMART-TV; Linux; Tizen 7.0) Chrome/94.0.0.0 TV Safari/537.36','Mozilla/5.0 (Web0S; Linux/SmartTV) Chrome/108.0.0.0 Safari/537.36','Mozilla/5.0 (Linux; Android 11; AFTMM) Chrome/110.0.0.0 Safari/537.36']:
    context=b.new_context(user_agent=ua,viewport={'width':1280,'height':720});q=context.new_page();q.goto('http://127.0.0.1:8023/filmes');q.wait_for_selector('.catalog-grid');assert q.evaluate('window.WorkTVPlatform.tv');q.goto('http://127.0.0.1:8023/filmes?tv=0');q.wait_for_selector('.catalog-grid');assert not q.evaluate('window.WorkTVPlatform.tv');context.close()
   for width,height in [(390,844),(1440,950)]:
    context=b.new_context(viewport={'width':width,'height':height});q=context.new_page();q.goto('http://127.0.0.1:8023/filmes');q.wait_for_selector('.catalog-grid');assert not q.evaluate('window.WorkTVPlatform.tv');assert q.evaluate('document.documentElement.scrollWidth<=innerWidth');context.close()
   assert not errors,errors
   (OUT/'result.json').write_text(json.dumps({'status':'PASS','engine':'Chromium (not vendor SDK)','viewports':['960x540','1280x720','1920x1080','3840x2160'],'remote':['arrows','OK','Samsung 10009','LG 461','media controls'],'pwa_offline':True,'real_mp4':True,'errors':errors},indent=2))
   print('PASS desktop/mobile preserved; detection and opt-out; no JavaScript errors',flush=True)
   b.close()
 finally:server.close()
