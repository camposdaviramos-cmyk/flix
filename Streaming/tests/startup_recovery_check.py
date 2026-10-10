"""Isolated old-PWA upgrade, React exception and interrupted-bundle recovery."""
import sys,tempfile,threading,time,json
from pathlib import Path
from flask import Response,request
from playwright.sync_api import sync_playwright
from waitress import create_server
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app

def poll(p,expr):
 end=time.monotonic()+20
 while time.monotonic()<end:
  if p.evaluate(expr):return
  p.wait_for_timeout(100)
 raise AssertionError(expr)

with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True);upgrade={'done':False}
 old_sw=(ROOT/'static/sw.js').read_text().replace('flix-shell-worktv-account-v1','flix-shell-worktv-tv-v2')
 @app.after_request
 def old_release(response):
  if not upgrade['done']:
   if request.path=='/sw.js':response.set_data(old_sw)
   elif request.path=='/':response.set_data(response.get_data(as_text=True).replace('account-20261009a','react-20261007a'))
  return response
 server=create_server(app,host='127.0.0.1',port=8026,threads=8);threading.Thread(target=server.run,daemon=True).start()
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(args=['--no-sandbox','--enable-unsafe-swiftshader']);context=browser.new_context(reduced_motion='reduce');p=context.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
   base='http://127.0.0.1:8026';p.goto(base);p.wait_for_selector('[data-react-page=home]');poll(p,'!!navigator.serviceWorker.controller')
   p.evaluate('''async()=>{localStorage.setItem('startup-test-checkpoint','preserve-me');const c=await caches.open('flix-shell-worktv-tv-v2');await c.put('/static/app.js?v=react-20261007a',new Response('throw Error("stale cached application");',{headers:{'Content-Type':'application/javascript'}}));}''')
   upgrade['done']=True;p.reload();p.wait_for_selector('[data-react-page=home]');assert not errors,errors
   poll(p,"caches.keys().then(keys=>keys.includes('flix-shell-worktv-account-v1')&&!keys.includes('flix-shell-worktv-tv-v2'))")
   print('PASS old PWA with stale application upgrades to current interface',flush=True)
   # Force a component render failure: the screen must recover instead of becoming empty.
   def bad_boot(route):
    response=route.fetch();body=response.json();body['plans'][0]['features']=None;route.fulfill(response=response,json=body)
   p.route('**/api/bootstrap',bad_boot);p.reload();p.wait_for_selector('#worktv-recovery');assert p.locator('#worktv-recovery button').is_visible()
   p.unroute('**/api/bootstrap');p.locator('#worktv-recovery button').click();p.wait_for_selector('[data-react-page=home]');assert p.locator('#worktv-recovery').count()==0
   assert p.evaluate("localStorage.getItem('startup-test-checkpoint')")=='preserve-me';assert '_wt_reload' not in p.url
   print('PASS React error has visible recovery; retry restores interface and preserves checkpoints',flush=True)
   p.close()  # Release the previous WebGL renderer before the next recovery scenario.
   blocked=browser.new_context(reduced_motion='reduce',service_workers='block');q=blocked.new_page();q.route('**/static/app.js?*',lambda r:r.abort());q.goto(base);q.wait_for_selector('#worktv-recovery');assert q.get_by_role('button',name='Atualizar e tentar novamente').is_visible()
   print('PASS interrupted app bundle offers recovery instead of blank screen',flush=True)
   q.unroute('**/static/app.js?*');q.get_by_role('button',name='Atualizar e tentar novamente').click();q.wait_for_selector('[data-react-page=home]')
   assert q.locator('#worktv-recovery').count()==0
   blocked.close()
   delayed=context.new_page();pending=[];delayed.route('**/api/bootstrap',lambda r:pending.append(r));delayed.goto(base,wait_until='domcontentloaded')
   delayed.evaluate('WorkTVBoot.fail()');delayed.wait_for_selector('#worktv-recovery')
   assert pending
   for route in pending:route.continue_()
   delayed.wait_for_selector('[data-react-page=home]');delayed.wait_for_selector('#worktv-recovery',state='detached')
   print('PASS late successful bootstrap dismisses recovery automatically',flush=True)
   print(json.dumps({'status':'PASS','old_pwa_upgrade':True,'react_error_recovery':True,'interrupted_bundle_recovery':True,'checkpoint_preserved':True,'no_reload_loop':True}),flush=True);browser.close()
 finally:server.close()
