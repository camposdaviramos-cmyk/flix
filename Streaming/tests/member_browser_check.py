"""Verify member flows with an isolated database, leaving production untouched."""
import sys,tempfile,sqlite3,time,threading,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from waitress import create_server
from playwright.sync_api import sync_playwright
from werkzeug.security import generate_password_hash
out=Path('/opt/flix/Streaming/test-results');out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True)
 db=sqlite3.connect(Path(folder)/'vyra.sqlite3')
 admin=db.execute("SELECT id FROM users WHERE role='admin'").fetchone()[0]
 db.execute("INSERT INTO users(id,name,email,password,role,status,plan_id,expires_at,created_at) VALUES('member-test','Ana Teste','member@example.com',?,'user','active','premium',?,?)",(generate_password_hash('Member-test-123'),time.time()+86400,time.time()))
 movie=db.execute("SELECT id FROM content WHERE kind='movie' LIMIT 1").fetchone()[0]
 series=db.execute("SELECT id FROM content WHERE kind='series' LIMIT 1").fetchone()[0]
 episode=db.execute('SELECT id FROM episodes WHERE content_id=? ORDER BY season,number',(series,)).fetchone()[0]
 for cid,eid,pos in [(movie,'',18),(series,episode,23)]:db.execute('INSERT INTO progress VALUES(?,?,?,?,?,?,?)',('member-test',cid,eid,pos,150,time.time(),time.time()*1000))
 db.execute("INSERT INTO content(id,title,kind,genre,description,poster,video_url,featured,published,created_at) VALUES('channel-browser','Canal Cinema','channel','Cinema','Canal de teste','/static/assets/neon.jpg','/static/assets/sintel-trailer.mp4',1,1,?)",(time.time(),))
 db.execute("INSERT INTO watch_history VALUES('member-test','channel-browser',?)",(time.time(),));db.execute('INSERT INTO watch_history VALUES(?,?,?)',('member-test',movie,time.time()));db.commit();db.close()
 server=create_server(app,host='127.0.0.1',port=8001,threads=4);threading.Thread(target=server.run,daemon=True).start()
 with sync_playwright() as pw:
  browser=pw.chromium.launch(args=['--no-sandbox'])
  context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce');page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:8001');page.wait_for_selector('.hero');assert page.locator('.member-home').count()==0
  page.get_by_role('button',name='Entrar',exact=True).click();page.locator('#auth-email').fill('member@example.com');page.locator('#auth-password').fill('Member-test-123');page.locator('#auth-form button[type=submit]').click();page.wait_for_selector('.member-home')
  assert page.locator('.hero').count()==0;assert page.locator('.resume-card').count()==2;assert page.locator('.channel-story').count()==2
  assert page.locator('.member-welcome').inner_text().startswith('Olá, Ana.')
  sections=['Continue assistindo','Seus canais recentes','Filmes em destaque','Séries em destaque','Top filmes','Top séries','Novidades no catálogo','Minha lista','Canais principais']
  for name in sections:assert page.get_by_role('heading',name=name,exact=True).count()==1,name
  page.screenshot(path=str(out/'member-home-desktop.png'),full_page=True)
  links=page.locator('.member-shelves .member-more').evaluate_all('(els)=>els.map(e=>({text:e.closest("section").querySelector("h2").textContent,href:e.getAttribute("href")}))')
  for link in links:
   page.goto('http://127.0.0.1:8001'+link['href']);page.wait_for_selector('#app main');page.wait_for_function('!document.querySelector("#app .boot")');assert page.locator('#app h1').count(),link
   if link['href']=='/continuar':assert page.locator('.resume-card').count()==2
   if link['href']=='/tv?view=recent':assert page.locator('.channel-card').count()==1
   if '?view=featured' in link['href']:assert page.locator('.poster-badge').count()==page.locator('.movie-card').count()
  page.goto('http://127.0.0.1:8001/');page.wait_for_selector('.member-home');old=page.locator('.member-hero h1').inner_text();page.get_by_role('button',name='Próximo destaque').click();page.wait_for_function('(old)=>document.querySelector(".member-hero h1").textContent!==old',arg=old)
  with page.expect_response(lambda r:'/api/play/'+series in r.url) as playback:
   page.locator(f'.resume-image[data-id="{series}"]').click()
  assert 'episode='+episode in playback.value.url;assert playback.value.json()['position']==23
  page.wait_for_selector('#video-player');page.locator('.modal-close').click();page.wait_for_selector('.member-home')
  page.goto('http://127.0.0.1:8001/planos');page.wait_for_selector('.plan-grid');assert page.locator('.plan-card').count()==3
  page.goto('http://127.0.0.1:8001/');page.wait_for_selector('.member-home');page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(out/'member-home-mobile.png'),full_page=True)
  assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'), 'Horizontal page overflow'
  # Mobile stories and resume buttons remain reachable.
  assert page.locator('.resume-image').first.is_visible();page.locator('.channel-story').first.click();page.wait_for_selector('#video-player');page.locator('.modal-close').click()
  page.goto('http://127.0.0.1:8001/conta');page.get_by_role('button',name='Sair da conta').click();page.wait_for_selector('.hero');assert page.locator('.member-home').count()==0
  assert not errors,errors
  print(json.dumps({'status':'ok','destinations':links,'desktop':'member-home-desktop.png','mobile':'member-home-mobile.png','page_errors':errors},ensure_ascii=False))
  browser.close()
 server.close()
