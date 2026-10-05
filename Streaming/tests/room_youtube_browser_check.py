"""Reference room when empty; mobile share URL, first-play, queue and visible YouTube errors."""
import json,sqlite3,sys,tempfile,threading,time
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler
H={'X-Requested-With':'Flix'};OUT=ROOT/'test-results';LINK='https://youtu.be/ROYmf8KSXdE?si=KW6tOaHIWgt9V5nZ'
# Simulate the official API lifecycle, including delayed iframe readiness and a provider error.
# Playback availability of the actual external video is probed separately, never inferred from this fixture.
YT_FIXTURE="""window.youtubePlayers=[];window.YT={Player:class{
 constructor(target,c){this.c=c;this.state=-1;this.pos=0;this.f=document.createElement('iframe');this.f.title='Player YouTube';this.f.src='https://www.youtube.com/embed/'+c.videoId;this.f.style='width:100%;height:100%;border:0';(typeof target==='string'?document.getElementById(target):target).replaceWith(this.f);youtubePlayers.push(this);setTimeout(()=>{if(!this.dead){this.ready=true;c.events.onReady?.({target:this})}},80)}
 getIframe(){return this.f}getDuration(){return 300}getCurrentTime(){return this.pos}getPlayerState(){return this.state}setVolume(v){}seekTo(t){this.pos=t}playVideo(){if(this.state!==1){this.state=1;this.c.events.onStateChange?.({data:1})}}pauseVideo(){if(this.state!==2){this.state=2;this.c.events.onStateChange?.({data:2})}}destroy(){this.dead=true;this.f.remove()}
}};setTimeout(()=>window.onYouTubeIframeAPIReady?.(),0);"""
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True)
 with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
 server=make_server('127.0.0.1',8150,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8150'
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox'])
   c=browser.new_context(**pw.devices['iPhone 13']);p=c.new_page();errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
   assert c.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'}).ok
   p.route('https://www.youtube.com/iframe_api',lambda r:r.fulfill(content_type='text/javascript',body=YT_FIXTURE));p.route('https://www.youtube.com/embed/**',lambda r:r.fulfill(content_type='text/html',body='<body style="background:#16111b;color:#d3b7c7;font:14px sans-serif;display:grid;place-content:center;height:90vh">Player de teste do YouTube</body>'))
   response=c.request.post(url+'/api/community/rooms',headers=H,data={'kind':'video','title':'Teste','approval':False,'permanent':True});assert response.ok;rid=response.json()['room']['id'];path=url+'/api/community/rooms/'+rid
   try:
    p.goto(url+'/comunidade/sala/'+rid);expect(p.locator('.rm-stage-empty')).to_be_visible();expect(p.locator('.rm-avatar-strip')).to_be_visible();expect(p.locator('.rm-conversation-start')).to_be_visible();expect(p.locator('.rm-tabs [data-tab=chat]')).to_have_attribute('aria-current','page');p.screenshot(path=str(OUT/'rooms-empty-fixed-mobile.png'))
    def compose():
     p.locator('.rm-idle-content [data-rm=add]').click();p.locator('#rm-queue-form [name=url]').fill(LINK);assert p.locator('#rm-queue-form [name=start_now]').is_checked();assert not p.locator('#rm-queue-form [name=title]').get_attribute('required')
    compose();p.locator('#rm-queue-form [type=submit]').click();expect(p.locator('#modal')).not_to_be_visible();expect(p.locator('#cm-media-holder iframe')).to_be_visible(timeout=10000)
    expect(p.locator('.rm-tabs [data-tab=chat]')).to_have_attribute('aria-current','page');expect(p.locator('.rm-avatar-strip')).to_be_visible();p.wait_for_function("()=>youtubePlayers.at(-1)?.state===1")
    assert p.evaluate("youtubePlayers.at(-1).c.videoId==='ROYmf8KSXdE'");assert p.evaluate("youtubePlayers.at(-1).c.playerVars.playsinline===1");expect(p.locator('#cm-media-holder iframe')).to_have_attribute('referrerpolicy','strict-origin-when-cross-origin')
    p.locator('.rm-tabs [data-tab=media]').click();p.locator('[data-rm=youtube]').click();p.locator('#rm-queue-form [name=url]').fill(LINK);assert not p.locator('#rm-queue-form [name=start_now]').is_checked();p.locator('#rm-queue-form [type=submit]').click();expect(p.locator('.rm-queue')).to_contain_text('Vídeo do YouTube');players=p.evaluate('youtubePlayers.length');p.locator('[data-rm=queue-play]').click();expect(p.locator('.rm-tabs [data-tab=chat]')).to_have_attribute('aria-current','page')
    p.wait_for_function("n=>youtubePlayers.length>n&&youtubePlayers.at(-1)?.ready",arg=players)
    # The official ended event advances once even if the provider repeats the callback.
    for link in (LINK,'https://youtu.be/abcdefghijk'):
     r=c.request.post(path+'/experience/queue',headers=H,data={'url':link,'lane':'video'});assert r.ok,r.text()
    players=p.evaluate('youtubePlayers.length');p.evaluate("()=>{window.finishedYoutube=youtubePlayers.at(-1);finishedYoutube.state=0;finishedYoutube.c.events.onStateChange({data:0});finishedYoutube.c.events.onStateChange({data:0})}")
    p.wait_for_function("n=>youtubePlayers.length>n&&youtubePlayers.at(-1)?.ready&&youtubePlayers.at(-1).state===1",arg=players)
    p.evaluate('finishedYoutube.c.events.onStateChange({data:0})');r=c.request.post(path+'/poll',headers=H,data={});assert len(r.json()['room']['queue'])==1
    p.evaluate('youtubePlayers.at(-1).c.events.onError({data:153})');expect(p.locator('.rm-media-notice')).to_be_visible();expect(p.locator('.rm-media-notice')).to_contain_text('153');expect(p.locator('.rm-media-notice a')).to_have_attribute('href','https://www.youtube.com/watch?v=ROYmf8KSXdE');p.screenshot(path=str(OUT/'rooms-youtube-error-mobile.png'))
    p.locator('[data-rm=retry-media]').click();p.wait_for_function("()=>youtubePlayers.length>=2");expect(p.locator('.rm-media-notice')).not_to_be_visible()
    # Turning the phone does not fall back to the desktop room on re-entry.
    p.set_viewport_size({'width':844,'height':390});p.reload();expect(p.locator('.rm-tabs')).to_be_visible();expect(p.locator('.rm-tabs [data-tab=chat]')).to_have_attribute('aria-current','page');assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors
    print(json.dumps({'empty_stage_and_people_visible':True,'shared_youtube_link':True,'title_optional':True,'first_media_opens_on_chat':True,'queue_preserved':True,'youtube_ended_advances_once':True,'player_errors_visible':True,'retry':True,'landscape_mobile':True,'playback_fixture':True,'page_errors':errors}))
   except Exception:
    p.screenshot(path=str(OUT/'room-youtube-failure.png'),full_page=True);print('ERRORS',errors);print(p.locator('body').inner_text()[-1800:]);raise
   finally:browser.close()
 finally:server.shutdown()
