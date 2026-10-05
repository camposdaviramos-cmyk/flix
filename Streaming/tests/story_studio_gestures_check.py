"""Touch gestures, audiences, soundtrack and real camera recording in Chromium mobile."""
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
 server=make_server('127.0.0.1',8153,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8153'
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
   ctx=browser.new_context(**pw.devices['iPhone 13'],permissions=['camera','microphone']);p=ctx.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
   p.add_init_script("window.sounds=[];const OriginalAudio=Audio;window.Audio=class extends OriginalAudio{constructor(...a){super(...a);sounds.push(this)}}")
   login=ctx.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'});assert login.ok;admin=login.json()['user']
   friend=ctx.request.post(url+'/api/admin/users',headers=H,data={'name':'Amiga Story','username':'amiga','email':'amiga@example.com','password':'Amiga-test-123'}).json()['user']
   guest=browser.new_context();assert guest.request.post(url+'/api/auth/login',headers=H,data={'email':'amiga@example.com','password':'Amiga-test-123'}).ok
   assert ctx.request.post(url+'/api/social/friends',headers=H,data={'username':'amiga'}).ok
   assert guest.request.patch(url+'/api/social/friends/'+admin['id'],headers=H,data={}).ok
   cdp=ctx.new_cdp_session(p)
   def touch(kind,pts):
    cdp.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[{'x':x,'y':y,'id':i+1,'radiusX':3,'radiusY':3,'force':1} for i,(x,y) in enumerate(pts)]});p.wait_for_timeout(35)
   def photo():
    p.goto(url+'/comunidade/criar/story');p.locator('#fse-gallery').set_input_files(str(ROOT/'static/assets/montanha.jpg'));expect(p.locator('.fse-tools')).to_be_visible();expect(p.locator('.fse-status')).not_to_be_visible(timeout=15000)
   try:
    photo()
    # Real browser touch events, two fingers: enlarge/reframe the base without empty margins.
    touch('touchStart',[(100,510),(220,510)]);touch('touchMove',[(60,490),(265,535)]);touch('touchEnd',[])
    assert p.locator('.fse-source').evaluate("el=>!el.style.transform.endsWith('scale(1)')")
    touch('touchStart',[(130,530)]);touch('touchMove',[(310,600)]);touch('touchEnd',[])
    assert p.locator('.fse-source').evaluate("el=>{const a=el.getBoundingClientRect(),b=el.closest('.fse-scene').getBoundingClientRect();return a.left<=b.left+.1&&a.top<=b.top+.1&&a.right>=b.right-.1&&a.bottom>=b.bottom-.1}")
    p.locator('[data-story=text]').click();p.locator('.fse-text-edit textarea').fill('Cinema');p.locator('[data-story=text-done]').click()
    r=p.locator('.fse-layer.text').bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']/2
    touch('touchStart',[(x-25,y),(x+25,y)]);touch('touchMove',[(x-42,y-24),(x+42,y+24)]);touch('touchEnd',[])
    transform=p.locator('.fse-layer.text').get_attribute('style');assert 'rotate(0deg)' not in transform and 'scale(1)' not in transform,transform
    # Double touch edits in place; an emoji can be dragged into the actual trash zone.
    p.locator('.fse-layer.text').dblclick();expect(p.locator('.fse-text-edit textarea')).to_be_focused();p.locator('.fse-text-edit textarea').fill('Cinema com amigos');p.locator('[data-story=text-done]').click()
    p.locator('[data-story=stickers]').click();p.locator('[data-story=emoji]').first.click();r=p.locator('.fse-layer.emoji').bounding_box();x=r['x']+r['width']/2;y=r['y']+r['height']/2
    touch('touchStart',[(x,y)]);touch('touchMove',[(x,y+30)]);r=p.locator('.fse-trash').bounding_box();touch('touchMove',[(r['x']+r['width']/2,r['y']+r['height']/2)]);touch('touchEnd',[]);expect(p.locator('.fse-layer.emoji')).to_have_count(0)
    # Uploaded audio plays from its selected excerpt and uses its selected volume.
    p.locator('[data-story=music]').click();p.locator('#fse-audio').set_input_files(str(sound));expect(p.locator('.fse-music-selected')).to_contain_text('trilha.wav');p.locator('[data-music=start]').fill('3');p.locator('[data-music=volume]').fill('0.3');p.locator('[data-story=music-preview]').click();p.wait_for_function('()=>sounds.some(s=>!s.paused&&s.currentTime>=3.2&&s.volume===.3)');p.locator('[data-sheet=music] [data-story=sheet-close]').last.click()
    # Empty close friends list opens selection and publishes only for that selected friend.
    p.locator('[data-story=close-friends]').click();expect(p.locator('[data-sheet=people]')).to_be_visible();p.locator('[name=person]').check();p.locator('[data-story-form=people] [type=submit]').click();p.wait_for_url(url+'/comunidade',timeout=20000)
    story=ctx.request.get(url+'/api/community/stories').json()['stories'][0];detail=ctx.request.get(url+'/api/community/stories/'+story['id']).json()['story'];comp=detail['composition'];assert comp['items'][0]['zoom']>1;assert abs(comp['layers'][0]['rotation'])>10;assert comp['layers'][0]['scale']>1.5;assert comp['music']['start']==3 and comp['music']['volume']==.3
    assert guest.request.get(url+'/api/community/stories/'+story['id']).ok
    with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:assert db.execute('SELECT audience FROM community_stories WHERE id=?',(story['id'],)).fetchone()[0]=='close'
    photo();p.locator('[data-story=send]').click();p.locator('[name=person]').check();p.locator('[data-story-form=people] [type=submit]').click();p.wait_for_url(url+'/comunidade',timeout=20000)
    messages=guest.request.get(url+'/api/hub/dm/'+admin['id']).json()['messages'];assert any(m.get('share',{}).get('kind')=='story' for m in messages)
    # Record for the full limit with a real MediaRecorder; stop happens without clicking.
    p.goto(url+'/comunidade/criar/story');p.locator('[data-story=camera]').click();p.wait_for_function("()=>document.querySelector('.fse-camera-preview')?.videoWidth>0");p.locator('[data-mode=video]').click();p.locator('[data-story=capture]').click();expect(p.locator('[aria-label="Parar gravação"]')).to_be_visible();p.wait_for_function("()=>document.querySelector('.fse-record-time')?.textContent.startsWith('00:01')",timeout=5000);p.screenshot(path=str(OUT/'story-studio-camera-mobile.png'))
    expect(p.locator('.fse-source')).to_be_visible(timeout=40000);expect(p.locator('.fse-status')).not_to_be_visible(timeout=15000)
    if p.locator('[data-sheet=trim]').count():p.locator('[data-story-form=trim] [type=submit]').click()
    p.wait_for_function("()=>document.querySelector('.fse-source')?.currentTime>.1");p.locator('[data-story=publish]').click();p.wait_for_url(url+'/comunidade',timeout=20000)
    newest=ctx.request.get(url+'/api/community/stories').json()['stories'][0];comp=ctx.request.get(url+'/api/community/stories/'+newest['id']).json()['story']['composition'];assert 29<=comp['duration']<=30;assert comp['items'][0]['type']=='video'
    assert not errors,errors
    print(json.dumps({'touch_pinch_rotate':True,'base_cover_bounds':True,'double_tap_edit':True,'drag_to_trash':True,'soundtrack_excerpt_and_volume':True,'close_friends_ui':True,'direct_share_ui':True,'camera_auto_stop_30s':True,'recorded_video_publication':True,'errors':errors}))
   except Exception:
    print('ERRORS',errors);print(p.locator('body').inner_text()[-2000:]);p.screenshot(path=str(OUT/'story-studio-gestures-failure.png'),full_page=True);raise
   finally:browser.close()
 finally:server.shutdown()
