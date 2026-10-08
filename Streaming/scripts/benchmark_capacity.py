"""Bounded localhost-only API baseline. Not a 25,000-user certification.
Creates its own disposable database; does not connect to the production service.
"""
import argparse,concurrent.futures,json,sqlite3,statistics,sys,tempfile,threading,time,urllib.request
from pathlib import Path
from waitress import create_server
p=argparse.ArgumentParser();p.add_argument('--app-root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--requests',type=int,default=120);p.add_argument('--concurrency',type=int,default=8);p.add_argument('--titles',type=int,default=200);p.add_argument('--output',type=Path);a=p.parse_args()
if not 1<=a.concurrency<=32 or not 1<=a.requests<=1000 or not 1<=a.titles<=5000:p.error('Bounded test limits exceeded')
def memory():
 return {line.split(':')[0]:line.split(':')[1].strip() for line in Path('/proc/self/status').read_text().splitlines() if line.startswith(('VmRSS:', 'VmHWM:'))}
phases={'before_import':memory()}
sys.path.insert(0,str(a.app_root));from app import create_app
phases['after_import']=memory()
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True)
 phases['after_init']=memory()
 with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:
  db.executemany('INSERT INTO content(id,title,kind,genre,published,video_url,created_at) VALUES(?,?,?,?,?,?,?)',[(f'bench-{n}',f'Benchmark {n}','series','Teste',1,'https://example.invalid/video',1) for n in range(a.titles)])
  db.executemany('INSERT INTO episodes(id,content_id,season,number,title,duration,video_url) VALUES(?,?,?,?,?,?,?)',[(f'be-{n}',f'bench-{n}',1,1,'Episódio','10min','https://example.invalid/episode') for n in range(a.titles)])
 db.close()
 server=create_server(app,host='127.0.0.1',port=8025,threads=8);threading.Thread(target=server.run,daemon=True).start()
 def request(_):
  start=time.perf_counter()
  with urllib.request.urlopen('http://127.0.0.1:8025/api/catalog',timeout=20) as response:body=response.read();status=response.status
  return (time.perf_counter()-start)*1000,status,len(body)
 try:
  request(0);start=time.perf_counter()
  with concurrent.futures.ThreadPoolExecutor(max_workers=a.concurrency) as pool:results=list(pool.map(request,range(a.requests)))
  elapsed=time.perf_counter()-start;latencies=sorted(r[0] for r in results)
  report={'scenario':'isolated localhost GET /api/catalog, synthetic series; not simultaneous user capacity','extra_titles':a.titles,'requests':a.requests,'concurrency':a.concurrency,'threads':8,'seconds':round(elapsed,3),'requests_per_second':round(a.requests/elapsed,2),'latency_ms':{'median':round(statistics.median(latencies),2),'p95':round(latencies[int(.95*(len(latencies)-1))],2)},'memory_phases':dict(phases,after_requests=memory()),'peak_process_rss_mib':round(int(memory()['VmHWM'].split()[0])/1024,2),'errors':sum(r[1]!=200 for r in results),'response_bytes':results[0][2]}
  if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2))
  print(json.dumps(report,indent=2))
 finally:server.close()
