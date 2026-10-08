"""Bounded cold-browser profile on localhost, disposable database, software GPU."""
import argparse,json,sys,tempfile,threading,time
from pathlib import Path
from waitress import create_server
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('--app-root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.path.insert(0,str(a.app_root));from app import create_app
with tempfile.TemporaryDirectory() as folder:
 server=create_server(create_app(folder,testing=True),host='127.0.0.1',port=8027,threads=8);threading.Thread(target=server.run,daemon=True).start()
 try:
  with sync_playwright() as pw:
   b=pw.chromium.launch(args=['--no-sandbox','--enable-unsafe-swiftshader']);page=b.new_page(viewport={'width':1440,'height':950});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.add_init_script('''window.profile={longTasks:[],frames:[],paints:[]};new PerformanceObserver(l=>profile.longTasks.push(...l.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:true});new PerformanceObserver(l=>profile.paints.push(...l.getEntries().map(e=>({name:e.name,start:e.startTime})))).observe({type:'paint',buffered:true});let previous;function frame(t){if(previous)profile.frames.push(t-previous);previous=t;requestAnimationFrame(frame)}requestAnimationFrame(frame);''')
   start=time.monotonic();page.goto('http://127.0.0.1:8027/',wait_until='domcontentloaded');page.wait_for_selector('[data-react-page=home]');home=(time.monotonic()-start)*1000
   page.wait_for_selector('.wt-scene[data-ready=true]',timeout=90000);astro=(time.monotonic()-start)*1000;page.wait_for_timeout(6000)
   data=page.evaluate('({profile,resources:performance.getEntriesByType("resource").map(e=>({name:new URL(e.name).pathname,bytes:e.decodedBodySize,duration:e.duration})),timing:performance.getEntriesByType("navigation")[0].toJSON()})');frames=sorted(data['profile']['frames']);tasks=data['profile']['longTasks'];report={'environment':'isolated localhost Chromium, software GPU; one cold visit, not real-device SLA','home_ms':round(home),'astro_ready_ms':round(astro),'resource_bytes':sum(r['bytes'] for r in data['resources']),'js_bytes':sum(r['bytes'] for r in data['resources'] if r['name'].endswith('.js')),'glb_bytes':sum(r['bytes'] for r in data['resources'] if r['name'].endswith('.glb')),'long_tasks':len(tasks),'blocking_ms':round(sum(max(0,t['duration']-50) for t in tasks)),'frame_p95_ms':round(frames[int(len(frames)*.95)],1),'errors':errors,'details':data};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='details'},indent=2));page.screenshot(path=str(a.output.with_suffix('.png')));b.close()
 finally:server.close()
