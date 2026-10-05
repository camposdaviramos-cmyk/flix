"""Real mobile Reels editing, frames, drafts, settings and publication."""
import json,sqlite3,sys,tempfile,threading,wave
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler
H={'X-Requested-With':'Flix'};OUT=ROOT/'test-results'
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True)
 with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=?,username='admin' WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
 sound=Path(folder)/'trilha.wav'
 with wave.open(str(sound),'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*16000*15)
 server=make_server('127.0.0.1',8155,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8155'
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
   ctx=browser.new_context(**pw.devices['iPhone 13'],permissions=['camera','microphone']);p=ctx.new_page();errors=[];p.on('pageerror',lambda e:errors.append(e.stack));p.add_init_script("window.sounds=[];const OriginalAudio=Audio;window.Audio=class extends OriginalAudio{constructor(...a){super(...a);sounds.push(this)}}")
   assert ctx.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'}).ok
   cdp=ctx.new_cdp_session(p)
   def touch(kind,pts):
    cdp.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[{'x':x,'y':y,'id':i+1,'radiusX':3,'radiusY':3,'force':1} for i,(x,y) in enumerate(pts)]});p.wait_for_timeout(35)
   try:
    p.goto(url+'/comunidade/criar/reel');p.locator('[data-reel=camera]').click();p.wait_for_function("()=>document.querySelector('.fre-camera video')?.videoWidth>0")
    p.evaluate("window.capturedStream=document.querySelector('.fre-camera video').srcObject")
    p.locator('[data-reel=record]').click();p.wait_for_function("()=>document.querySelector('.fre-record-time')?.textContent.startsWith('00:01')",timeout=5000);p.screenshot(path=str(OUT/'reel-camera-mobile.png'))
    expect(p.locator('.fre-stage')).to_be_visible(timeout=65000)
    if p.locator('.fre-trim').is_visible():p.locator('[data-reel=trim-confirm]').click()
    p.wait_for_function("()=>document.querySelector('.fse-source')?.currentTime>.1")
    assert p.evaluate("capturedStream.getTracks().every(t=>t.readyState==='ended')")
    assert p.evaluate("FlixStory.toolkit().state.c.items[0].duration>=59&&FlixStory.toolkit().state.c.items[0].duration<=60")
    p.locator('[data-story=text]').click();p.locator('.fse-text-edit textarea').fill('Cinema');p.locator('[data-story=text-done]').click()
    r=p.locator('.fse-layer.text').bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']/2
    touch('touchStart',[(x-25,y),(x+25,y)]);touch('touchMove',[(x-42,y-24),(x+42,y+24)]);touch('touchEnd',[])
    transform=p.locator('.fse-layer.text').get_attribute('style');assert 'rotate(0deg)' not in transform and 'scale(1)' not in transform,transform
    p.locator('.fse-layer.text').dblclick();expect(p.locator('.fse-text-edit textarea')).to_be_focused();p.locator('.fse-text-edit textarea').fill('Um minuto de Flix');p.locator('[data-story=text-done]').click()
    p.locator('[data-story=stickers]').click();p.locator('[data-story=emoji]').first.click();r=p.locator('.fse-layer.emoji').bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']/2
    touch('touchStart',[(x,y)]);touch('touchMove',[(x,y+30)]);r=p.locator('.fse-trash').bounding_box();touch('touchMove',[(r['x']+r['width']/2,r['y']+r['height']/2)]);touch('touchEnd',[]);expect(p.locator('.fse-layer.emoji')).to_have_count(0)
    for width,height in [(320,568),(390,844),(768,1024),(1440,1000)]:
     p.set_viewport_size({'width':width,'height':height});assert p.locator('[data-reel=next]').evaluate('(e)=>e.getBoundingClientRect().bottom<=innerHeight');assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
    p.set_viewport_size({'width':390,'height':844});p.locator('[data-reel=next]').click();p.locator('[data-reel=publish]').click();p.wait_for_url('**/comunidade/post/*',timeout=25000)
    post=ctx.request.get(url+'/api/community/posts/'+p.url.split('/')[-1]).json()['post'];assert 59<=post['composition']['duration']<=60
    p.goto(url+'/comunidade/criar/reel');p.locator('#fse-gallery').set_input_files(str(ROOT/'static/assets/sintel-trailer.mp4'));expect(p.locator('.fre-stage')).to_be_visible(timeout=15000);p.locator('[data-reel=trim]').click();p.locator('[name=trim_start]').fill('12');p.locator('[name=trim_end]').fill('15');p.locator('[data-reel=trim-confirm]').click()
    p.locator('[data-reel=next]').click();p.locator('[data-reel=more]').click();p.locator('[data-reel=quality]').click();p.locator('[data-reel=option-pick][data-value=standard]').click();p.locator('.fre-panel [data-reel=back]').click();p.locator('[data-reel=publish]').click();p.wait_for_url('**/comunidade/post/*',timeout=30000)
    post=ctx.request.get(url+'/api/community/posts/'+p.url.split('/')[-1]).json()['post'];m=post['composition']['items'][0];assert m['start']==0 and m['speed']==1 and m['duration']==3;assert post['reel_options']['quality']=='standard'
    p.locator('[data-cm=solo-watch]').first.click();expect(p.locator('#cx-play-composition video')).to_be_visible();p.locator('[data-cx=view-play]').click();p.wait_for_function("()=>{const v=document.querySelector('#cx-play-composition video');return v&&!v.paused&&v.currentTime>.2&&v.videoWidth<=1280}")
    assert not errors,errors
    print(json.dumps({'camera_auto_stop_60s':True,'camera_cleanup':True,'recorded_publication':True,'touch_pinch_rotate':True,'double_tap_edit':True,'drag_to_trash':True,'responsive_320_to_1440':True,'standard_quality_conversion_playback':True,'errors':errors}))
   except Exception:
    print('ERRORS',errors);print(p.locator('body').inner_text()[-4000:]);p.screenshot(path=str(OUT/'reel-camera-failure.png'),full_page=True);raise
   finally:browser.close()
 finally:server.shutdown()
