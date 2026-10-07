"""Astronaut gestures, belly hit area, animated scenery and navigation on an isolated DB."""
import sys,tempfile,threading,json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
from waitress import create_server
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
out=ROOT/'test-results'/'worktv-world';out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
 server=create_server(create_app(folder,testing=True),host='127.0.0.1',port=8022,threads=8);threading.Thread(target=server.run,daemon=True).start()
 try:
  with sync_playwright() as pw:
   b=pw.chromium.launch(args=['--no-sandbox','--enable-unsafe-swiftshader']);p=b.new_page(viewport={'width':1440,'height':950})
   errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
   p.goto('http://127.0.0.1:8022',wait_until='domcontentloaded');p.wait_for_selector('.wt-scene[data-ready=true]',timeout=60000)
   assert 'worktv-world-v1.webp' in p.locator('.hero-art').evaluate('(e)=>getComputedStyle(e).backgroundImage')
   assert p.locator('.vx-atmosphere').is_visible() and p.locator('.vx-starfield').is_visible()
   assert p.locator('.vx-motion-toggle').count()==0
   assert p.locator('.wt-meteor').count()==2
   p.wait_for_selector('.wt-scene[data-reaction=idle]',timeout=20000)
   # Store frame states before triggering; a slow software GPU must not hide short states from the test.
   p.evaluate('''()=>{window.states=[];const el=document.querySelector('.wt-scene');new MutationObserver(()=>{const r=el.dataset.reaction;if(window.states.at(-1)?.r!==r)window.states.push({r,t:performance.now()});}).observe(el,{attributes:true,attributeFilter:['data-reaction']});document.querySelector('.wt-astro-touch').click();}''')
   for attempt in range(50):
    states=p.evaluate('window.states')
    if any(x['r']=='wave' for x in states) and states[-1]['r']=='idle':break
    p.wait_for_timeout(300)
   else:raise AssertionError(states)
   states=p.evaluate('window.states');start=next(x['t'] for x in states if x['r']=='wave');end=states[-1]['t'];assert 5500<end-start<8500,states
   print('Six-second wave:',round((end-start)/1000,2),'seconds',flush=True)
   box=p.locator('.wt-scene').bounding_box();x=box['x']+box['width']*.51;y=box['y']+box['height']*.55
   p.mouse.move(x,y);p.wait_for_selector('.wt-scene[data-reaction=tickle]',timeout=15000)
   assert 'cócegas' in p.locator('.wt-astro-bubble').inner_text()
   print('Belly hover triggers tickle',flush=True)
   p.locator('.wt-scene').screenshot(path=str(out/'tickle.png'),animations='allow')
   p.mouse.move(150,170);p.wait_for_selector('.wt-scene[data-reaction=idle]',timeout=10000)
   p.mouse.move(box['x']+box['width']*.5,box['y']+box['height']*.23);p.wait_for_timeout(300)
   assert p.locator('.wt-scene').get_attribute('data-reaction')=='idle'
   p.mouse.move(100,100)
   # Verify that the restored particle canvas actually changes, not just that it exists.
   a=p.locator('.vx-starfield').evaluate('(c)=>c.toDataURL()');p.wait_for_timeout(400);bb=p.locator('.vx-starfield').evaluate('(c)=>c.toDataURL()');assert a!=bb
   p.screenshot(path=str(out/'world-desktop.png'))
   p.emulate_media(reduced_motion='reduce');p.wait_for_selector('.wt-scene[data-running=false]')
   assert p.locator('.wt-space-haze').evaluate('(e)=>getComputedStyle(e).animationPlayState')=='paused'
   p.screenshot(path=str(out/'world-desktop-paused.png'))
   p.set_viewport_size({'width':390,'height':844});p.evaluate('window.scrollTo(0,0)');assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
   p.screenshot(path=str(out/'world-mobile.png'));p.locator('.wt-astro-touch').scroll_into_view_if_needed();p.screenshot(path=str(out/'world-mobile-character.png'))
   p.emulate_media(reduced_motion='no-preference');p.wait_for_selector('.wt-scene[data-running=true]')
   box=p.locator('.wt-scene').bounding_box()
   p.locator('.wt-astro-touch').dispatch_event('click',{'detail':1,'clientX':box['x']+box['width']*.51,'clientY':box['y']+box['height']*.55})
   p.wait_for_selector('.wt-scene[data-reaction=tickle]',timeout=15000)
   p.mouse.move(5,5);p.wait_for_selector('.wt-scene[data-reaction=idle]',timeout=10000)
   p.set_viewport_size({'width':1440,'height':950});p.evaluate('window.scrollTo(0,0)')
   p.locator('.header nav a[href="/filmes"]').click();p.wait_for_url('**/filmes');p.wait_for_selector('.catalog-grid')
   assert p.locator('.wt-astro,.wt-space-effects').count()==0
   p.locator('.header .brand').click();p.wait_for_selector('.wt-scene[data-ready=true]')
   assert p.locator('.wt-astro').count()==1 and p.locator('.wt-space-effects').count()==1
   assert p.locator('.wt-scene canvas').count()==1
   p.emulate_media(reduced_motion='reduce');p.wait_for_selector('.wt-scene[data-running=false]')
   assert p.locator('.wt-space-haze').evaluate('(e)=>getComputedStyle(e).animationName')=='none'
   assert not errors,errors
   print(json.dumps({'status':'PASS','wave':6,'belly_only':True,'particles_animate':True,'pause':True,'mobile':True,'errors':errors}),flush=True);b.close()
 finally:server.close()
