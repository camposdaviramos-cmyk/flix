"""Two mobile clients: initial player/seats, stage consent, devices and actual media completion."""
import io,json,math,sqlite3,struct,sys,tempfile,threading,time,wave
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler
H={'X-Requested-With':'Flix'};OUT=ROOT/'test-results'
sound=io.BytesIO()
with wave.open(sound,'wb') as w:
 w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b''.join(struct.pack('<h',int(500*math.sin(i*2*math.pi*220/8000))) for i in range(8000*40)))
def wait(p,expression,timeout=15000):p.wait_for_function(expression,timeout=timeout)
def media_response(route,body,mime):
 headers={'Accept-Ranges':'bytes','Access-Control-Allow-Origin':'*'};raw=route.request.headers.get('range','')
 if raw.startswith('bytes='):
  start,end=raw[6:].split('-',1);start=int(start or 0);end=min(int(end) if end else len(body)-1,len(body)-1);headers['Content-Range']=f'bytes {start}-{end}/{len(body)}'
  route.fulfill(status=206,body=body[start:end+1],content_type=mime,headers=headers)
 else:route.fulfill(body=body,content_type=mime,headers=headers)
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True)
 with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=?,username='admin' WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
 server=make_server('127.0.0.1',8151,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8151'
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
   hc=browser.new_context(**pw.devices['iPhone 13'],permissions=['microphone','camera']);gc=browser.new_context(**pw.devices['iPhone 13'],permissions=['microphone','camera'])
   assert hc.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'}).ok
   response=hc.request.post(url+'/api/admin/users',headers=H,data={'name':'Luna Costa','username':'luna','email':'luna@example.com','password':'Community-123'});assert response.ok;uid=response.json()['user']['id']
   assert gc.request.post(url+'/api/auth/login',headers=H,data={'email':'luna@example.com','password':'Community-123'}).ok
   r=hc.request.post(url+'/api/community/rooms',headers=H,data={'kind':'video','title':'Cinema com a turma','approval':False,'permanent':True});assert r.ok;rid=r.json()['room']['id'];path=url+'/api/community/rooms/'+rid
   host=hc.new_page();guest=gc.new_page();errors=[]
   for p in (host,guest):
    p.on('pageerror',lambda e:errors.append(str(e)))
    p.route('https://media.example.test/**',lambda r:media_response(r,(ROOT/'static/assets/sintel-trailer.mp4').read_bytes(),'video/mp4'))
    p.route('https://audio.example.test/**',lambda r:media_response(r,sound.getvalue(),'audio/wav'))
   def dbroom():
    with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:
     db.row_factory=sqlite3.Row;return dict(db.execute('SELECT * FROM community_rooms WHERE id=?',(rid,)).fetchone())
   def add(link,start=False,lane='video'):
    r=hc.request.post(path+'/experience/queue',headers=H,data={'url':link,'title':('Trilha da noite' if lane=='music' else 'Próximo episódio'),'lane':lane,'start_now':start});assert r.ok,r.text();return r.json()['id']
   def device(p,name):return p.locator('.rm-chat-controls [data-device="'+name+'"]')
   try:
    host.goto(url+'/comunidade/sala/'+rid)
    expect(host.locator('.rm-idle-player')).to_be_visible();expect(host.locator('.rm-avatar-strip .rm-seat')).to_have_count(8);expect(host.locator('.rm-avatar-strip .vacant')).to_have_count(7)
    expect(device(host,'room-enable')).to_be_visible();expect(device(host,'room-camera')).to_be_visible();expect(device(host,'room-mic')).to_be_visible()
    host.screenshot(path=str(OUT/'rooms-stage-empty-mobile.png'))
    guest.goto(url+'/comunidade/sala/'+rid);expect(guest.locator('.rm-chat-controls [data-rm=request-seat]')).to_be_visible();expect(device(guest,'room-mic')).to_be_disabled();expect(device(guest,'room-camera')).to_be_disabled()
    guest.locator('.rm-chat-controls [data-rm=request-seat]').click();expect(guest.locator('.rm-chat-controls [data-rm=stage-cancel]')).to_be_visible();expect(host.locator('.rm-request-toast')).to_contain_text('quer subir ao palco');host.screenshot(path=str(OUT/'rooms-stage-request-mobile.png'))
    host.locator('.rm-request-toast [data-cm=room-promote]').click();expect(guest.locator('.rm-chat-controls [data-rm=stage-leave]')).to_be_visible();expect(guest.locator('.rm-avatar-strip .occupied')).to_have_count(2)
    expect(device(guest,'room-camera')).to_be_enabled();expect(device(guest,'room-mic')).to_be_enabled();device(guest,'room-camera').click();expect(device(guest,'room-camera')).to_have_attribute('aria-pressed','true',timeout=15000);expect(host.locator('#cm-camera-stage video')).to_have_count(1,timeout=20000)
    device(guest,'room-mic').click();expect(device(guest,'room-mic')).to_have_attribute('aria-pressed','true');host.screenshot(path=str(OUT/'rooms-stage-guest-camera-mobile.png'))
    assert hc.request.patch(path+'/members/'+uid,headers=H,data={'decision':'mute'}).ok;expect(device(guest,'room-mic')).to_be_disabled();expect(device(guest,'room-mic')).to_have_attribute('aria-pressed','false')
    device(guest,'room-camera').click();expect(device(guest,'room-camera')).to_have_attribute('aria-pressed','false');expect(host.locator('#cm-camera-stage video')).to_have_count(0);guest.locator('.rm-chat-controls [data-rm=stage-leave]').click();expect(guest.locator('.rm-chat-controls [data-rm=request-seat]')).to_be_visible()
    for p in (host,guest):device(p,'room-enable').click();expect(device(p,'room-enable')).to_have_attribute('aria-pressed','true')
    # Actual MP4 ended events, including repeated identical URL in the next queue slot.
    first='https://media.example.test/episode.mp4';third='https://media.example.test/finale.mp4'
    add(first,True);add(first);add(third)
    for p in (host,guest):wait(p,"()=>{const v=document.querySelector('#cm-media-holder video');return v?.readyState>=2&&!v.paused}")
    epoch=dbroom()['media_epoch'];host.evaluate("()=>{const v=document.querySelector('#cm-media-holder video');window.previousEpisode=v;v.currentTime=v.duration-.15;}")
    host.wait_for_function("epoch=>Number(document.querySelector('#cm-media-holder video')?.dataset.mediaEpoch)>epoch",arg=epoch);assert host.evaluate("document.querySelector('#cm-media-holder video')===window.previousEpisode")
    wait(host,"()=>{const v=document.querySelector('#cm-media-holder video');return v?.readyState>=2&&!v.paused&&v.currentTime<10}")
    assert dbroom()['media_epoch']==epoch+1,dbroom()
    host.evaluate("previousEpisode.dispatchEvent(new Event('ended'))")
    host.wait_for_timeout(800);assert dbroom()['url']==first
    wait(guest,"()=>{const v=document.querySelector('#cm-media-holder video');return v?.currentTime>0&&!v.paused&&v.currentTime<10}")
    a=host.locator('#cm-media-holder video').evaluate('(v)=>v.currentTime');b=guest.locator('#cm-media-holder video').evaluate('(v)=>v.currentTime');assert abs(a-b)<1.5,(a,b)
    host.evaluate("()=>{const v=document.querySelector('#cm-media-holder video');v.currentTime=v.duration-.15;}")
    wait(host,"()=>document.querySelector('#cm-media-holder video')?.currentSrc.includes('finale.mp4')");wait(guest,"()=>document.querySelector('#cm-media-holder video')?.currentSrc.includes('finale.mp4')")
    host.screenshot(path=str(OUT/'rooms-stage-playing-mobile.png'))
    # Simultaneous soundtrack advances independently without changing the current episode.
    add('https://audio.example.test/one.wav',True,'music');add('https://audio.example.test/two.wav',False,'music')
    for p in (host,guest):
     device(p,'room-enable').click();wait(p,"()=>{const a=document.querySelector('.rm-sound-engine audio');return a?.readyState>=2&&!a.paused}")
    host.evaluate("()=>{const a=document.querySelector('.rm-sound-engine audio');a.currentTime=a.duration-.15;}")
    wait(host,"()=>document.querySelector('.rm-sound-engine audio')?.currentSrc.includes('two.wav')");wait(guest,"()=>document.querySelector('.rm-sound-engine audio')?.currentSrc.includes('two.wav')");assert dbroom()['url']==third
    # Exhausting the episode queue stops playback rather than replaying the last second.
    host.evaluate("()=>{const v=document.querySelector('#cm-media-holder video');v.currentTime=v.duration-.15;}")
    wait(host,"()=>{const v=document.querySelector('#cm-media-holder video');return v?.readyState>=2&&v.paused&&v.currentTime<1}");assert dbroom()['paused']
    # A smaller viewport keeps the composer, controls and seats reachable.
    host.set_viewport_size({'width':360,'height':740});host.screenshot(path=str(OUT/'rooms-stage-small-mobile.png'));assert host.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert host.locator('.rm-tabs').bounding_box()['y']<740
    assert not errors,errors
    print(json.dumps({'initial_player_and_eight_seats':True,'stage_request_and_host_accept':True,'camera_toggle_and_remote_video':True,'mic_host_mute':True,'native_episode_auto_next':True,'duplicate_end_guard':True,'native_player_reused':True,'guest_drift_seconds':abs(a-b),'independent_audio_auto_next':True,'end_of_queue_stops':True,'page_errors':errors}))
   except Exception:
    print('MEDIA',[p.evaluate("(()=>{const v=document.querySelector('#cm-media-holder video');return v&&{src:v.currentSrc,paused:v.paused,time:v.currentTime,duration:v.duration,ended:v.ended,ready:v.readyState,error:v.error?.code}})()") for p in (host,guest)]);print('ERRORS',errors);print('ROOM',{k:dbroom()[k] for k in ['kind','media_type','position','paused','media_epoch']})
    for name,p in [('host',host),('guest',guest)]:
     try:p.screenshot(path=str(OUT/f'room-stage-failure-{name}.png'),full_page=True);print(name,p.locator('body').inner_text()[-1800:])
     except Exception:pass
    raise
   finally:browser.close()
 finally:server.shutdown()
