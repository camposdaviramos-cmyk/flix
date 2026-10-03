"""Check actual remote playback and persistence with a disposable database."""
import sys,json,sqlite3,tempfile,time,threading
from pathlib import Path
sys.path[:0]=['/opt/flix/Streaming','/opt/flix/demo']
from app import create_app
from import_catalog import import_into
from werkzeug.security import generate_password_hash
from waitress import create_server
from playwright.sync_api import sync_playwright
entries=json.loads(Path('/opt/flix/demo/catalog.json').read_text());result=[]
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True);dbpath=Path(folder)/'vyra.sqlite3';import_into(dbpath,entries)
 db=sqlite3.connect(dbpath);db.execute("INSERT INTO users(id,name,email,password,role,status,plan_id,expires_at,created_at) VALUES('demo-media-user','Demonstração','demo-media@example.com',?,'user','active','premium',?,?)",(generate_password_hash('Demo-media-123'),time.time()+86400,time.time()));db.commit();db.close()
 server=create_server(app,host='127.0.0.1',port=8003,threads=8);threading.Thread(target=server.run,daemon=True).start()
 with sync_playwright() as pw:
  browser=pw.chromium.launch(args=['--no-sandbox','--autoplay-policy=no-user-gesture-required'])
  ctx=browser.new_context(viewport={'width':1280,'height':800});response=ctx.request.post('http://127.0.0.1:8003/api/auth/login',data={'email':'demo-media@example.com','password':'Demo-media-123'},headers={'X-Requested-With':'VYRA'});assert response.ok
  page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto('http://127.0.0.1:8003/');page.wait_for_selector('.member-home')
  for entry in entries:
   media=entry.get('episodes') or [{}]
   for n,ep in enumerate(media,1):
    eid=entry['id']+'-part-'+str(n) if entry['kind']=='series' else ''
    report={'id':entry['id'],'title':entry['title'],'episode':ep.get('title'),'status':'pending'}
    try:
     page.evaluate('([id,ep])=>play(id,ep)',[entry['id'],eid]);page.wait_for_selector('#video-player')
     page.wait_for_function('()=>{const v=document.querySelector("#video-player");return v&&v.readyState>=2&&v.currentTime>0&&!v.paused;}',timeout=45000)
     report.update(status='ok',video=page.locator('#video-player').evaluate('(v)=>({currentTime:v.currentTime,duration:Number.isFinite(v.duration)?v.duration:null,width:v.videoWidth,height:v.videoHeight})'))
     if entry['kind']!='channel':
      duration=report['video']['duration'];ep['duration']=f'{int(duration//60)}min {int(duration%60)}s';entry['duration']=ep['duration'] if entry['kind']=='movie' else f"{len(entry['episodes'])} partes"
     # Check exact saved position for a movie and for the first series episode.
     if (entry['id']=='demo-big-buck-bunny') or (entry['id']=='demo-caminandes' and n==1):
      page.locator('#video-player').evaluate('(v)=>{v.pause();v.currentTime=11.25;}');page.wait_for_function('()=>Math.abs(document.querySelector("#video-player").currentTime-11.25)<.1');page.evaluate('saveProgress()')
      page.wait_for_function('()=>!Object.keys(localStorage).some(k=>k.startsWith("vyra-progress:"))',timeout=15000)
      page.evaluate('closeModal()');page.reload();page.wait_for_selector('.member-home')
      with page.expect_response(lambda r:'/api/play/'+entry['id'] in r.url) as res:page.evaluate('([id,ep])=>play(id,ep)',[entry['id'],eid])
      assert abs(res.value.json()['position']-11.25)<.01,res.value.json()
      page.wait_for_function('()=>{const v=document.querySelector("#video-player");return v&&v.readyState>=2&&v.currentTime>=11.2;}',timeout=30000)
      report['resume']='11.25s persisted and resumed after reload'
     if entry['id'] in ['demo-tv-camara','demo-caminandes'] and n==1:page.screenshot(path='/opt/flix/Streaming/test-results/'+entry['id']+'-player.png')
    except Exception as err:
     report.update(status='failed',error=str(err)[:800],player_message=page.locator('.player-status').inner_text() if page.locator('.player-status').count() else '')
    finally:
     page.evaluate('closeModal()');result.append(report);print(json.dumps(report,ensure_ascii=False),flush=True)
  browser.close()
 server.close()
Path('/opt/flix/demo/media-check.json').write_text(json.dumps({'results':result,'page_errors':errors},ensure_ascii=False,indent=2))
Path('/opt/flix/demo/catalog.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2))
if any(r['status']!='ok' for r in result) or errors:sys.exit(1)
