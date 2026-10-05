"""Real single-media story editing/publication in a mobile viewport; no provider stubs."""
import json,sqlite3,sys,tempfile,threading
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
 server=make_server('127.0.0.1',8152,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8152'
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
   ctx=browser.new_context(**pw.devices['iPhone 13'],permissions=['camera','microphone']);p=ctx.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
   assert ctx.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'}).ok
   try:
    p.goto(url+'/comunidade/criar/story');expect(p.locator('.fse-select')).to_be_visible();assert not p.locator('#fse-gallery').get_attribute('multiple');expect(p.locator('.fse-tools')).not_to_be_visible();expect(p.locator('.cx-clips')).to_have_count(0);p.screenshot(path=str(OUT/'story-studio-select-mobile.png'))
    p.locator('#fse-gallery').set_input_files(str(ROOT/'static/assets/montanha.jpg'));expect(p.locator('.fse-tools')).to_be_visible();expect(p.locator('.fse-status')).not_to_be_visible(timeout=15000)
    expect(p.locator('.fse-tools>button')).to_have_count(6);expect(p.locator('.fse-publish>button')).to_have_count(3);assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
    p.locator('[data-story=text]').click();expect(p.locator('.fse-text-edit textarea')).to_be_focused();p.locator('.fse-text-edit textarea').fill('Sua história aqui');p.locator('[data-story=text-done]').click();expect(p.locator('.fse-layer.text')).to_contain_text('Sua história aqui')
    # Pointer drag persists actual layer position; no coordinate sliders on the main screen.
    layer=p.locator('.fse-layer.text');r=layer.bounding_box();p.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2);p.mouse.down();p.mouse.move(r['x']+r['width']/2-25,r['y']+r['height']/2+85,steps=12);p.mouse.up();assert not p.locator('[data-adjust]').count()
    p.locator('[data-story=draw]').click();p.mouse.move(125,415);p.mouse.down();p.mouse.move(240,420,steps=14);p.mouse.up();p.locator('[data-story=draw-done]').click();expect(p.locator('.fse-drawing polyline')).to_have_count(1)
    p.screenshot(path=str(OUT/'story-studio-reference-mobile.png'))
    p.locator('[data-story=link]').click();p.locator('[data-story-form=link] [name=url]').fill('https://example.com/filme');p.locator('[data-story-form=link] [name=text]').fill('Saiba mais');p.locator('[data-story-form=link] [type=submit]').click();expect(p.locator('.fse-layer.link')).to_contain_text('Saiba mais')
    p.locator('[data-story=stickers]').click();p.locator('[data-kind=poll]').click();p.locator('[data-story-form=sticker] [name=text]').fill('Vamos assistir?');p.locator('[data-story-form=sticker] [type=submit]').click();expect(p.locator('.fse-layer.poll')).to_contain_text('Vamos assistir?')
    p.locator('[data-story=adjust]').click();p.locator('[data-adjust=saturation]').fill('1.4');p.locator('[data-sheet=adjust] [data-story=sheet-close]').last.click();p.locator('[data-story=publish]').click();p.wait_for_url(url+'/comunidade',timeout=20000)
    story=ctx.request.get(url+'/api/community/stories').json()['stories'][0];detail=ctx.request.get(url+'/api/community/stories/'+story['id']).json()['story'];c=detail['composition'];assert len(c['items'])==1 and c['items'][0]['saturation']==1.4;assert c['layers'][0]['y']>38;assert len(c['drawings'])==1
    p.goto(url+'/comunidade?story='+story['id']);expect(p.locator('#modal .fse-scene')).to_be_visible();expect(p.locator('#modal a.fse-layer.link')).to_have_attribute('href','https://example.com/filme');p.locator('#modal .fse-layer.poll').click();expect(p.locator('.fse-response')).to_be_visible();p.locator('.fse-response [data-choice="0"]').click();expect(p.locator('.fse-answer-status')).to_contain_text('Voto registrado');paused=p.locator('#cx-view-seek').input_value();p.wait_for_timeout(1600);assert p.locator('#cx-view-seek').input_value()==paused;p.locator('.fse-response-close').click();p.wait_for_function('()=>Number(document.querySelector("#cx-view-seek")?.value)>'+paused)
    p.goto(url+'/comunidade/criar/story');p.locator('#fse-gallery').set_input_files(str(ROOT/'static/assets/sintel-trailer.mp4'));expect(p.locator('[data-sheet=trim]')).to_be_visible(timeout=15000);expect(p.locator('[data-sheet=trim]')).to_contain_text('52 segundos');p.locator('[data-story-form=trim] [name=start]').fill('12');p.locator('[data-story-form=trim] [name=end]').fill('22');p.locator('[data-story-form=trim] [type=submit]').click();expect(p.locator('.fse-sheet')).to_have_count(0);p.wait_for_function("()=>{const v=document.querySelector('.fse-source');return v?.currentTime>=12&&!v.paused}");p.screenshot(path=str(OUT/'story-studio-video-mobile.png'));expect(p.locator('.fse-status')).not_to_be_visible(timeout=15000);p.locator('[data-story=publish]').click();p.wait_for_url(url+'/comunidade',timeout=20000)
    newest=ctx.request.get(url+'/api/community/stories').json()['stories'][0];comp=ctx.request.get(url+'/api/community/stories/'+newest['id']).json()['story']['composition'];assert comp['items'][0]['start']==12 and comp['items'][0]['duration']==10
    # Camera access, taking an actual frame, and cleanup on navigation.
    p.goto(url+'/comunidade/criar/story');p.locator('[data-story=camera]').click();p.wait_for_function("()=>document.querySelector('.fse-camera-preview')?.videoWidth>0");p.evaluate("window.capturedStream=document.querySelector('.fse-camera-preview').srcObject");p.locator('[data-story=capture]').click();expect(p.locator('.fse-source')).to_be_visible();expect(p.locator('.fse-status')).not_to_be_visible(timeout=15000);assert p.evaluate("capturedStream.getTracks().every(t=>t.readyState==='ended')")
    p.goto(url+'/comunidade');assert not p.evaluate("document.body.classList.contains('fse-active')");assert not errors,errors
    print(json.dumps({'single_media':True,'reference_composition':True,'inline_text_focus':True,'pointer_drag':True,'drawing':True,'link_persists':True,'poll_response':True,'video_auto_trim':True,'video_excerpt_playback':True,'camera_photo':True,'camera_cleanup':True,'page_errors':errors}))
   except Exception:
    print('ERRORS',errors);print(p.locator('body').inner_text()[-3000:]);p.screenshot(path=str(OUT/'story-studio-failure.png'),full_page=True);raise
   finally:browser.close()
 finally:server.shutdown()
