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
            p.goto(url+'/comunidade/criar/reel');p.locator('[data-cx-upload=clips]').first.set_input_files(str(ROOT/'static/assets/sintel-trailer.mp4'));expect(p.locator('#cx-clips>button')).to_have_count(1,timeout=20000)
            p.locator('[data-cx-item=start]').fill('12');p.locator('[data-cx-item=start]').press('Tab');p.locator('[data-cx-item=duration]').fill('4');p.locator('[data-cx-item=duration]').press('Tab')
            p.locator('[data-cx=music-panel]').click();p.locator('#cx-music-panel summary').click();p.locator('[data-cx-upload=music]').set_input_files(str(sound));expect(p.locator('#cx-music-selected')).to_contain_text('sound.wav');p.locator('[data-cx=preview-toggle]').click()
            p.wait_for_timeout(1800);v=p.locator('#cx-editor-preview video');assert v.evaluate('(v)=>!v.paused&&v.currentTime>=12&&v.currentTime<16'),v.evaluate('(v)=>({time:v.currentTime,paused:v.paused})');assert p.evaluate('sounds.some(s=>!s.paused&&s.currentTime>.5)')
            p.locator('[data-cx=preview-toggle]').click();assert p.evaluate('sounds.every(s=>s.paused)')
            p.locator('.cx-steps [data-step="3"]').click();p.get_by_label('Legenda').fill('Cena com corte e trilha própria');p.get_by_role('button',name='Publicar reel',exact=True).first.click();p.wait_for_url('**tab=reels')
            post=c.request.get(url+'/api/community/feed?kind=reel').json()['posts'][0];comp=post['composition'];assert comp['items'][0]['start']==12 and comp['items'][0]['duration']==4;assert comp['music']['type']=='audio'
            p.locator('[data-cx=reel-play]').click();p.wait_for_timeout(1500);assert p.locator('.cx-inline-reel video').evaluate('(v)=>!v.paused&&v.currentTime>=12&&v.currentTime<16')
            p.goto(url+'/comunidade');assert p.evaluate('sounds.every(s=>s.paused)');assert not errors,errors
            print(json.dumps({'actual_video_trim_playback':True,'own_audio_soundtrack':True,'persisted_composition_playback':True,'media_cleanup':True,'page_errors':errors}))
        finally:browser.close()
    finally:server.shutdown()
