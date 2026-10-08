"""Real React routes and lifecycle with an isolated account and local video."""
import json,sys,tempfile,threading,sqlite3,time
from pathlib import Path
from playwright.sync_api import sync_playwright
from waitress import create_server
from werkzeug.security import generate_password_hash
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
OUT=ROOT/'test-results/react';OUT.mkdir(parents=True,exist_ok=True)
def poll(p,expr,timeout=20000):
 end=time.monotonic()+timeout/1000
 while time.monotonic()<end:
  if p.evaluate(expr):return
  p.wait_for_timeout(100)
 raise AssertionError(expr)
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True)
 with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:
  db.execute("UPDATE users SET password=? WHERE email='admin@vyra.local'",(generate_password_hash('Local-React-2026-only'),))
 server=create_server(app,host='127.0.0.1',port=8024,threads=8);threading.Thread(target=server.run,daemon=True).start()
 try:
  with sync_playwright() as pw:
   b=pw.chromium.launch(args=['--no-sandbox','--enable-unsafe-swiftshader']);p=b.new_page(viewport={'width':1440,'height':950},reduced_motion='reduce');errors=[];requests=[]
   p.on('pageerror',lambda e:errors.append(str(e)));p.on('request',lambda r:requests.append(r.url))
   blocked=[];p.route('**/api/bootstrap',lambda route:blocked.append(route))
   p.goto('http://127.0.0.1:8024/',wait_until='domcontentloaded');p.wait_for_selector('.boot');p.screenshot(path=str(OUT/'slow-network-first-paint.png'))
   assert p.locator('#app .page').count()==0
   assert p.locator('noscript').count()==1
   assert not p.get_by_text('Filmes, séries e TV ao vivo | WorkTV',exact=True).is_visible()
   poll(p,'!!window.WorkTVUI');assert blocked;blocked.pop().continue_();p.unroute('**/api/bootstrap');p.wait_for_selector('[data-react-page=home]')
   assert len([u for u in requests if u=='http://127.0.0.1:8024/'])==1
   assert not any('/api/seo' in u for u in requests)
   assert not any('/static/admin.js' in u or '/static/community-studio.js' in u or '/static/vendor/hls.min.js' in u for u in requests),requests
   assert not any('fonts.googleapis.com' in u for u in requests)
   p.screenshot(path=str(OUT/'home-react.png'));print('PASS no textual flash under delayed bootstrap; React home; one initial document',flush=True)
   p.locator('.header nav a[href="/filmes"]').click();p.wait_for_selector('[data-react-page=catalog]');poll(p,'document.title.includes("Filmes |")')
   p.locator('#catalog-search').fill('horizonte');poll(p,'document.querySelectorAll("#catalog-items .movie-card").length===1')
   assert p.locator('#catalog-items').inner_text().find('ALÉM DO HORIZONTE')>=0
   p.locator('#catalog-search').fill('');p.get_by_role('button',name='Aventura',exact=True).click();assert 'active' in p.get_by_role('button',name='Aventura',exact=True).get_attribute('class')
   p.get_by_role('button',name='Todos',exact=True).click();p.get_by_role('button',name='Ver Além do Horizonte',exact=True).click();p.wait_for_selector('[data-react-page=title]')
   p.get_by_role('button',name='Assistir agora',exact=True).click();p.wait_for_selector('#react-modal #auth-form')
   seo_pending=[];p.route('**/api/seo?*',lambda route:seo_pending.append(route))
   p.locator('#auth-email').fill('admin@vyra.local');p.locator('#auth-password').fill('Local-React-2026-only');p.get_by_role('button',name='Entrar na minha conta',exact=True).click();p.wait_for_selector('[data-react-page=member-home]');p.wait_for_selector('#modal',state='hidden')
   # After login controls must mount even while the route's metadata is pending.
   p.locator('.header [data-hub=notices]').click();p.wait_for_selector('#fh-notifications:not([hidden])')
   p.locator('[data-hub=notices-close]').click()
   assert seo_pending
   for route in seo_pending:route.continue_()
   p.unroute('**/api/seo?*')
   print('PASS React search, genre filter, title, login and member home',flush=True)
   p.get_by_role('button',name='Próximo destaque',exact=True).click();p.wait_for_timeout(500);assert p.locator('[data-react-page=member-home]').count()==1
   p.evaluate("navigate('/titulo/horizonte')");p.wait_for_selector('[data-react-page=title]');p.get_by_role('button',name='Minha lista',exact=True).click();p.get_by_role('button',name='Na minha lista',exact=True).wait_for()
   p.get_by_role('button',name='Assistir agora',exact=True).click();p.wait_for_selector('#react-modal #video-player');poll(p,'document.querySelector("#video-player").readyState>=2',30000)
   p.evaluate('document.querySelector("#video-player").pause();document.querySelector("#video-player").currentTime=8')
   poll(p,'document.querySelector("#video-player").currentTime>=8');p.get_by_role('button',name='Fechar',exact=True).click();p.wait_for_selector('#modal',state='hidden')
   for url,page in [('/lista','catalog'),('/continuar','continue'),('/historico','history'),('/conta','account'),('/planos','plans'),('/termos','legal'),('/privacidade','legal'),('/tv','catalog'),('/series','catalog')]:
    p.evaluate('(url)=>navigate(url)',url);p.wait_for_selector(f'[data-react-page={page}]');assert p.evaluate('document.documentElement.scrollWidth<=innerWidth'),url
   # Switch between React roots and existing community/admin modules, including repeated cleanup.
   for url in ['/comunidade','/filmes','/admin','/series','/comunidade','/']:
    p.evaluate('(url)=>navigate(url)',url);p.wait_for_timeout(800);assert p.locator('#main, .admin-layout').count()>0,url
   p.wait_for_selector('[data-react-page=member-home]');assert p.locator('.header').count()==1
   # The wallet and purchase confirmation now have React ownership too.
   response=p.request.put('http://127.0.0.1:8024/api/admin/economy/packages/react-test',data={'name':'Pacote React','coins':123,'price':1990,'active':True},headers={'X-Requested-With':'VYRA'})
   assert response.status==200,response.text()
   p.evaluate("navigate('/carteira')");p.wait_for_selector('[data-react-page=wallet] .fw-balance')
   p.locator('.fw-packages article').filter(has_text='Pacote React').get_by_role('button').click();p.wait_for_selector('#react-modal .fw-purchase')
   checkout=[]
   def unavailable(route):
    checkout.append(route.request.post_data_json);route.fulfill(status=503,content_type='application/json',body='{"error":"Teste isolado: checkout indisponível"}')
   p.route('**/api/checkout',unavailable);p.get_by_role('button',name='Continuar para o pagamento').click();p.get_by_role('alert').filter(has_text='Teste isolado').wait_for()
   assert checkout==[{'package_id':'react-test','confirm_price':1990,'confirm_coins':123}],checkout
   p.get_by_role('button',name='Fechar',exact=True).click();p.unroute('**/api/checkout')
   print('PASS favorites, local video, account/library/routes and React-legacy transitions',flush=True)
   mobile=b.new_page(viewport={'width':390,'height':844},reduced_motion='reduce');mobile.on('pageerror',lambda e:errors.append(str(e)))
   mobile.goto('http://127.0.0.1:8024/');mobile.wait_for_selector('[data-react-page=home]');assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth')
   mobile.get_by_role('button',name='Abrir menu',exact=True).click();mobile.locator('.header nav a[href="/series"]').click();mobile.wait_for_selector('[data-react-page=catalog]');assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth');mobile.screenshot(path=str(OUT/'mobile-react.png'))
   # The human-readable fallback remains available when scripting is disabled.
   nojs=b.new_page(java_script_enabled=False);nojs.goto('http://127.0.0.1:8024/');assert nojs.locator('main h1').is_visible();assert not nojs.locator('.boot').is_visible()
   assert not errors,errors
   result={'status':'PASS','slow_network_no_flash':True,'react_routes':13,'react_auth_player':True,'legacy_transitions':True,'mobile':True,'nojs_fallback':True,'errors':errors};(OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True);b.close()
 finally:server.close()
