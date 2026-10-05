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
 # A real playable long fixture: halve MP4 movie/track clocks, doubling its duration.
 raw=bytearray((ROOT/'static/assets/sintel-trailer.mp4').read_bytes())
 def slower(start,end):
  pos=start
  while pos+8<=end:
   size=int.from_bytes(raw[pos:pos+4],'big');kind=raw[pos+4:pos+8]
   if size<8:break
   if kind in (b'moov',b'trak',b'mdia'):slower(pos+8,pos+size)
   elif kind in (b'mvhd',b'mdhd'):
    offset=pos+8+(20 if raw[pos+8] else 12);clock=int.from_bytes(raw[offset:offset+4],'big');raw[offset:offset+4]=(clock//2).to_bytes(4,'big')
   pos+=size
 slower(0,len(raw));long_video=Path(folder)/'long.mp4';long_video.write_bytes(raw)
 sound=Path(folder)/'trilha.wav'
 with wave.open(str(sound),'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*16000*15)
 server=make_server('127.0.0.1',8154,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8154'
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
   ctx=browser.new_context(**pw.devices['iPhone 13'],permissions=['camera','microphone']);p=ctx.new_page();errors=[];p.on('pageerror',lambda e:errors.append(e.stack));p.add_init_script("window.sounds=[];const OriginalAudio=Audio;window.Audio=class extends OriginalAudio{constructor(...a){super(...a);sounds.push(this)}}")
   assert ctx.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'}).ok
   try:
    p.goto(url+'/comunidade/criar/reel');expect(p.locator('.fre-select-cards')).to_be_visible();p.screenshot(path=str(OUT/'reel-select-mobile.png'));assert p.locator('#fse-gallery').get_attribute('accept')=='video/*';assert not p.locator('#fse-gallery').get_attribute('multiple')
    p.locator('#fse-gallery').set_input_files(str(long_video));expect(p.locator('.fre-trim')).to_be_visible(timeout=15000);p.locator('[name=trim_start]').fill('12');p.locator('[name=trim_end]').fill('18');p.screenshot(path=str(OUT/'reel-trim-mobile.png'));p.locator('[data-reel=trim-confirm]').click();expect(p.locator('.fre-stage')).to_be_visible();p.wait_for_function("()=>document.querySelector('.fse-source')?.currentTime>=12");p.wait_for_function("()=>document.querySelectorAll('.fre-bottom .fre-frames img').length>=8");assert not p.locator('#cx-clips').count();assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
    p.locator('[data-story=text]').click();expect(p.locator('.fse-text-edit textarea')).to_be_focused();p.locator('.fse-text-edit textarea').fill('Uma nova história');p.locator('[data-story=text-done]').click();p.locator('[data-reel=filters]').click();p.locator('[data-filter=cinema]').click();p.locator('[data-reel-adjust=filterIntensity]').fill('0.6');p.locator('[data-reel=sheet-done]').click();expect(p.locator('.fse-source')).to_have_attribute('style',__import__('re').compile('contrast\\(1.15\\)'));p.screenshot(path=str(OUT/'reel-editor-mobile.png'));assert p.locator('[data-reel=next]').evaluate('(e)=>e.getBoundingClientRect().bottom<=innerHeight')
    p.locator('[data-reel=cover]').click();p.locator('[data-reel-input=cover]').fill('15');p.wait_for_timeout(500);p.screenshot(path=str(OUT/'reel-cover-mobile.png'));p.locator('[data-reel=cover-confirm]').click();p.locator('[data-reel=cover]').click();p.locator('#fre-cover-file').set_input_files(str(ROOT/'static/assets/montanha.jpg'));expect(p.locator('.cx-crop-dialog')).to_be_visible();p.locator('.cx-crop-dialog input').fill('1.4');p.locator('[data-cx=crop-save]').click();expect(p.locator('.fre-cover-preview img')).to_be_visible();p.locator('[data-reel=cover-confirm]').click();p.locator('[data-reel=music]').click();expect(p.locator('.fre-music nav')).to_be_visible();p.screenshot(path=str(OUT/'reel-music-mobile.png'));p.locator('#fre-audio-file').set_input_files(str(sound));expect(p.locator('[data-sheet=music-excerpt]')).to_be_visible();p.locator('[data-reel-input=song-start]').fill('2');p.locator('[data-reel-input=song-volume]').fill('0.3');p.locator('[data-reel=music-confirm]').click();p.locator('[data-reel=next]').click();expect(p.locator('.fre-publication')).to_be_visible();p.locator('[data-reel-input=description]').fill('Cinema com amigos #Flix');p.screenshot(path=str(OUT/'reel-publish-mobile.png'))
    p.locator('[data-reel=location]').click();p.locator('[data-reel-form=option] [name=value]').fill('Recife');p.locator('[data-reel-form=option] [type=submit]').click();p.locator('[data-reel=comments]').click();p.locator('[data-reel=option-pick][data-value=off]').click();p.locator('[data-reel=more]').click();p.locator('[data-reel-option=ai_label]').check(force=True);p.locator('[data-reel-option=download]').check(force=True);p.screenshot(path=str(OUT/'reel-more-mobile.png'));p.locator('.fre-panel [data-reel=back]').click();p.locator('[data-reel=draft]').click();p.wait_for_url('**tab=reels');expect(p.locator('.fre-draft-banner')).to_be_visible(timeout=10000)
    p.goto(url+'/comunidade/criar/reel');expect(p.locator('[data-reel=resume]')).to_be_visible();p.locator('[data-reel=resume]').click();expect(p.locator('.fse-layer.text')).to_contain_text('Uma nova história');p.locator('[data-reel=next]').click();expect(p.locator('[data-reel-input=description]')).to_have_value('Cinema com amigos #Flix');expect(p.locator('[data-reel=location]')).to_contain_text('Recife');p.locator('[data-reel=publish]').click();p.wait_for_url('**/comunidade/post/*',timeout=25000)
    pid=p.url.split('/')[-1];post=ctx.request.get(url+'/api/community/posts/'+pid).json()['post'];assert post['composition']['format']=='reel';assert len(post['composition']['items'])==1;assert post['composition']['items'][0]['start']==12;assert post['composition']['duration']==6;assert post['composition']['music']['start']==2;assert post['reel_options']['ai_label'] and post['reel_options']['download'];assert post['reel_options']['comments']=='off';assert post['reel_options']['location']=='Recife';assert post['poster'].startswith('/api/community/assets/')
    p.locator('[data-cm=solo-watch]').first.click();expect(p.locator('#cx-play-composition .fse-scene')).to_be_visible();p.locator('[data-cx=view-play]').click();p.wait_for_function("()=>{const v=document.querySelector('#cx-play-composition video');return v&&!v.paused&&v.currentTime>=12}")
    assert not errors,errors
    print(json.dumps({'one_video':True,'auto_trim_over_60':True,'real_frames':True,'text_and_filters':True,'cover_frame':True,'custom_cover_crop':True,'music_excerpt':True,'indexeddb_draft_resume':True,'publication_options':True,'published_playback':True,'errors':errors}))
   except Exception:
    print('ERRORS',errors);print(p.locator('body').inner_text()[-4000:]);p.screenshot(path=str(OUT/'reel-failure-mobile.png'),full_page=True);raise
   finally:browser.close()
 finally:server.shutdown()
