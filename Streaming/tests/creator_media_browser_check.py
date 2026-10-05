"""Actual trimmed video and uploaded soundtrack playback in the composition runtime."""
import json,sqlite3,sys,tempfile,threading,wave
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler
H={'X-Requested-With':'Flix'}
with tempfile.TemporaryDirectory() as folder:
    app=create_app(folder,testing=True)
    with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
    sound=Path(folder)/'sound.wav'
    with wave.open(str(sound),'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*16000*8)
    server=make_server('127.0.0.1',8141,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8141'
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox'])
        c=browser.new_context(viewport={'width':1440,'height':1000});assert c.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'}).ok
        p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)));p.add_init_script("window.sounds=[];const AudioBase=Audio;window.Audio=class extends AudioBase{constructor(...a){super(...a);sounds.push(this)}};")
        try:
            p.goto(url+'/comunidade/criar/reel');p.locator('#fse-gallery').set_input_files(str(ROOT/'static/assets/sintel-trailer.mp4'));expect(p.locator('.fre-stage')).to_be_visible(timeout=20000)
            p.locator('[data-reel=trim]').click();p.locator('[name=trim_start]').fill('12');p.locator('[name=trim_end]').fill('16');p.locator('[data-reel=trim-confirm]').click()
            p.locator('[data-reel=music]').click();p.locator('#fre-audio-file').set_input_files(str(sound));p.locator('[data-reel=music-confirm]').click()
            p.wait_for_function("()=>{const v=document.querySelector('.fse-source');return v&&!v.paused&&v.currentTime>=12&&v.currentTime<16}");p.wait_for_function('()=>sounds.some(s=>!s.paused&&s.currentTime>.5)')
            p.locator('.fre-timeline-play').click();assert p.evaluate('sounds.every(s=>s.paused)')
            p.locator('[data-reel=next]').click();p.locator('[data-reel-input=description]').fill('Cena com corte e trilha própria');p.locator('[data-reel=publish]').click();p.wait_for_url('**/comunidade/post/*')
            post=c.request.get(url+'/api/community/feed?kind=reel').json()['posts'][0];comp=post['composition'];assert comp['items'][0]['start']==12 and comp['items'][0]['duration']==4;assert comp['music']['type']=='audio'
            p.goto(url+'/comunidade?tab=reels');p.locator('[data-cx=reel-play]').click();p.wait_for_function("()=>{const v=document.querySelector('.cx-inline-reel video');return v&&!v.paused&&v.currentTime>=12&&v.currentTime<16}")
            p.goto(url+'/comunidade');assert p.evaluate('sounds.every(s=>s.paused)');assert not errors,errors
            print(json.dumps({'actual_video_trim_playback':True,'own_audio_soundtrack':True,'persisted_composition_playback':True,'media_cleanup':True,'page_errors':errors}))
        finally:browser.close()
    finally:server.shutdown()
