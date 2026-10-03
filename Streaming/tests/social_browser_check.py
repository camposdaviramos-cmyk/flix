"""Social timeline and two real browser sessions: uploads, messages, games and moderation."""
import json,re,sqlite3,sys,tempfile,threading,time
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler
H={'X-Requested-With':'VYRA'};out=ROOT/'test-results'
with tempfile.TemporaryDirectory() as folder:
    app=create_app(folder,testing=True)
    with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Admin-browser-123'),))
    server=make_server('127.0.0.1',8135,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8135'
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
        hc=browser.new_context(viewport={'width':1440,'height':1000});gc=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
        hc.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'})
        aid=hc.request.get(url+'/api/bootstrap').json()['user']['id']
        u=hc.request.post(url+'/api/admin/users',headers=H,data={'name':'Luna Martins','username':'luna','email':'luna@example.com','password':'Community-123'}).json()['user'];gid=u['id']
        gc.request.post(url+'/api/auth/login',headers=H,data={'email':'luna@example.com','password':'Community-123'})
        host=hc.new_page();guest=gc.new_page();errors=[]
        for p in (host,guest):p.on('pageerror',lambda e:errors.append(str(e)))
        # Real data is created in a disposable test database only.
        poster='https://images.example.test/hero.png'
        for c in (hc,gc):c.route('https://images.example.test/**',lambda r:r.fulfill(path=str(ROOT/'static/assets/hero.png'),content_type='image/png'))
        gc.request.post(url+'/api/community/posts',headers=H,data={'kind':'movie','title':'Qual filme mudou seu jeito de ver o mundo?','body':'Hoje é noite de rever aquela história que fica com a gente depois dos créditos. Qual é a sua indicação? 🍿','url':'https://example.com/video.mp4','poster':poster})
        hc.request.post(url+'/api/community/posts',headers=H,data={'kind':'news','title':'O cinema também acontece nas conversas.','body':'Compartilhe as notícias, estreias e descobertas da semana com a sua turma.','url':'https://example.com/news'})
        gc.request.post(url+'/api/community/stories',headers=H,data={'body':'Noite de cinema com a turma 🍿','background':'#4a395a'})
        hc.request.post(url+'/api/community/rooms',headers=H,data={'kind':'voice','title':'Clube do cinema · conversa sem spoilers','approval':False})
        host.goto(url+'/comunidade');host.get_by_role('heading',name='Página inicial',exact=True).wait_for();assert not errors,errors
        host.screenshot(path=str(out/'social-feed-desktop.png'),full_page=True)
        guest.goto(url+'/comunidade');guest.get_by_role('heading',name='Página inicial',exact=True).wait_for();guest.screenshot(path=str(out/'social-feed-mobile.png'),full_page=True)
        assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth'),guest.evaluate('document.documentElement.scrollWidth')
        host.locator('.sx-sidebar [data-cm=new-post]').click();host.get_by_label('Título',exact=True).fill('Nossa primeira conversa');host.get_by_label('Conte para a comunidade').fill('Vamos jogar depois do filme?');host.locator('[data-cs=publish]').click();host.wait_for_url('**/comunidade/post/*');host.get_by_role('heading',name='Nossa primeira conversa',exact=True).wait_for();post=host.url.split('/')[-1]
        guest.goto(url+'/comunidade/post/'+post);guest.locator('[data-sx=react][data-value=heart]').click();expect(guest.locator('[data-sx=react][data-value=heart]')).to_have_attribute('aria-pressed','true')
        guest.get_by_label('Seu comentário').fill('Eu topo!');guest.get_by_role('button',name='Comentar',exact=True).click();guest.get_by_text('Eu topo!',exact=True).wait_for()
        host.goto(url+'/comunidade');host.locator('.sx-top [data-sx=story-new]').click();host.get_by_label('O que está acontecendo?',exact=True).fill('Story com foto enviada');host.locator('[data-sx-upload=media_url]').set_input_files(str(ROOT/'static/assets/hero.png'));expect(host.locator('#sx-story-form [name=media_url]')).to_have_value(re.compile('/api/community/assets/'),timeout=15000);host.get_by_role('button',name='Publicar story').click();host.get_by_role('heading',name='Página inicial',exact=True).wait_for()
        guest.goto(url+'/comunidade');guest.locator('[data-sx=story-view]').first.click();expect(guest.locator('.sx-story-view img')).to_be_visible();guest.locator('#modal [data-action=close]').click()
        host.goto(url+'/comunidade?tab=reels');host.get_by_role('button',name='Publicar reel',exact=True).click();host.get_by_label('Título',exact=True).fill('Sintel · reel da turma');host.locator('[data-cs-file]').set_input_files(str(ROOT/'static/assets/sintel-trailer.mp4'));expect(host.locator('.cs-media-block video')).to_be_visible(timeout=20000);host.locator('[data-cs=publish]').click();host.wait_for_url('**/comunidade/post/*');host.get_by_role('heading',name='Sintel · reel da turma').wait_for()
        guest.goto(url+'/comunidade?tab=reels');expect(guest.locator('.sx-reel video')).to_be_visible();guest.locator('.sx-reel video').evaluate('(v)=>v.play()');assert guest.locator('.sx-reel video').evaluate('(v)=>v.readyState')>=2
        guest.goto(url+'/comunidade/perfil/luna');guest.get_by_role('button',name='Editar perfil').click();guest.locator('[data-sx-upload=cover]').set_input_files(str(ROOT/'static/assets/hero.png'));expect(guest.locator('#cm-profile [name=cover]')).to_have_value(re.compile('/api/community/assets/'));guest.get_by_role('button',name='Salvar perfil').click();guest.get_by_role('heading',name='Luna Martins',exact=True).wait_for();expect(guest.locator('.cm-profile-cover')).to_have_attribute('style',re.compile('/api/community/assets/'));guest.screenshot(path=str(out/'social-profile-mobile.png'),full_page=True)
        hc.request.post(url+'/api/social/friends',headers=H,data={'username':'luna'});gc.request.patch(url+'/api/social/friends/'+aid,headers=H,data={})
        host.goto(url+'/comunidade?tab=friends&dm='+gid);guest.goto(url+'/comunidade?tab=friends&dm='+aid)
        guest.locator('#fh-message .sx-picker summary').click();guest.get_by_role('button',name='Figurinha Bora assistir!',exact=True).click();guest.get_by_role('button',name='Enviar mensagem',exact=True).click();expect(host.locator('#fh-messages .sx-sticker')).to_be_visible(timeout=10000);expect(host.locator('#fh-presence')).to_contain_text('Online',timeout=10000)
        # Share a room in the private conversation, then approve the invited friend.
        room=hc.request.post(url+'/api/community/rooms',headers=H,data={'kind':'voice','title':'Vem jogar com a turma','approval':True}).json()['room'];rid=room['id'];roomurl=url+'/comunidade/sala/'+rid
        hc.request.post(url+'/api/hub/dm/'+gid,headers=H,data={'share':{'kind':'room','id':rid}})
        host.goto(roomurl);host.locator('#sx-room-games').wait_for()
        guest.locator('#fh-messages .fh-shared').click();guest.get_by_text('Aguardando o anfitrião aceitar sua entrada…',exact=True).wait_for();host.locator('#cm-room-requests').get_by_role('button',name='Aceitar',exact=True).click();guest.locator('#sx-room-games').wait_for()
        host.locator('[data-game=create][data-kind=colors]').click();guest.get_by_role('button',name='Aceitar e jogar',exact=True).click();expect(host.locator('.fg-player')).to_have_count(2);host.get_by_role('button',name='Iniciar partida',exact=True).click();expect(guest.locator('.fg-hand .fg-card')).to_have_count(7)
        host.locator('.fg-turn-actions [data-game=draw]').click()
        if hc.request.get(url+f'/api/community/rooms/{rid}/game').json()['game']['can_pass']:host.locator('[data-game=pass]').click()
        expect(guest.locator('.fg-turn-actions [data-game=draw]')).to_be_enabled();guest.locator('.fg-turn-actions [data-game=draw]').click()
        expect(host.locator('.fg-hand .fg-card')).to_have_count(8)
        host.locator('[data-game=cancel]').click();host.get_by_role('button',name='Confirmar encerramento',exact=True).click();host.locator('[data-game=create][data-kind=draw]').click();guest.get_by_role('button',name='Aceitar e jogar',exact=True).click();expect(host.locator('.fg-player')).to_have_count(2);host.get_by_role('button',name='Iniciar partida',exact=True).click();host.locator('#sx-drawing-canvas').wait_for();guest.locator('#sx-guess').wait_for()
        word=hc.request.get(url+f'/api/community/rooms/{rid}/game').json()['game']['word'];assert 'word' not in gc.request.get(url+f'/api/community/rooms/{rid}/game').json()['game']
        box=host.locator('#sx-drawing-canvas').bounding_box();host.mouse.move(box['x']+40,box['y']+40);host.mouse.down();host.mouse.move(box['x']+100,box['y']+100,steps=8);host.mouse.up()
        for _ in range(30):
            if gc.request.get(url+f'/api/community/rooms/{rid}/game').json()['game']['strokes']:break
            time.sleep(.15)
        assert gc.request.get(url+f'/api/community/rooms/{rid}/game').json()['game']['strokes']
        guest.get_by_label('Qual é a palavra?',exact=True).fill(word);guest.locator('#sx-game-guess').get_by_role('button',name='Enviar',exact=True).click();expect(host.locator('.fg-guesses')).to_contain_text('Acertou!',timeout=10000)
        guest.screenshot(path=str(out/'social-game-mobile.png'),full_page=True);assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth')
        # All navigation destinations render at phone sizes under production CSP.
        for path,title in [('games','Central de jogos'),('news','Notícias'),('catalog','Explorar o catálogo'),('ranking','Ranking da comunidade'),('rooms','Salas e lives')]:
            guest.goto(url+'/comunidade?tab='+path);guest.get_by_role('heading',name=title,exact=True).wait_for();assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth'),path
        host.goto(url+'/admin?tab=community-social');host.get_by_role('heading',name='Stories, mídia e jogos.').wait_for();host.screenshot(path=str(out/'social-admin-desktop.png'),full_page=True)
        # Automatic focus zoom is avoided without disabling accessibility pinch zoom.
        fresh=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True);p=fresh.new_page();p.goto(url+'/comunidade');p.get_by_role('button',name='Já tenho conta',exact=True).click();inp=p.get_by_label('E-mail',exact=True);expect(inp).to_be_visible();assert float(inp.evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)'))>=16;assert 'user-scalable=no' not in p.locator('meta[name=viewport]').get_attribute('content')
        assert not errors,errors
        print(json.dumps({'social_timeline':True,'mobile_no_overflow':True,'stories_and_video_uploads':True,'reel_playback':True,'cover_upload':True,'live_inbox_and_stickers':True,'room_voice_invite':True,'two_browser_card_game':True,'two_browser_drawing_game':True,'mobile_inputs_16px':True,'browser_errors':errors}));browser.close()
    finally:server.shutdown()
