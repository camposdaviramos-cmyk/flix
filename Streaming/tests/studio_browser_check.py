"""Studio editor and host/guest gameplay using isolated data and real browser media."""
import io,json,math,os,sqlite3,struct,sys,tempfile,threading,time,wave
from pathlib import Path
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import create_app
from jump_browser_check import QuietHandler
H={'X-Requested-With':'VYRA'};out=ROOT/'test-results';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    app=create_app(folder,testing=True);dbpath=Path(folder)/'vyra.sqlite3'
    with sqlite3.connect(dbpath) as db:db.execute("UPDATE users SET id=?,password=?,name='Theo Almeida' WHERE role='admin'",(('z' if os.environ.get('STUDIO_OFFERER','guest')=='guest' else '0')*24,generate_password_hash('Admin-browser-123')))
    audio=Path(folder)/'voice.wav'
    with wave.open(str(audio),'wb') as f:
        f.setparams((1,2,48000,0,'NONE','not compressed'));f.writeframes(b''.join(struct.pack('<h',int(6500*math.sin(i*2*math.pi*330/48000))) for i in range(48000*3)))
    server=make_server('127.0.0.1',8136,app,threaded=True,request_handler=QuietHandler);threading.Thread(target=server.serve_forever,daemon=True).start();url='http://localhost:8136'
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome',headless=True,args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
        hc=browser.new_context(viewport={'width':1440,'height':1000},permissions=['microphone','camera']);gc=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,permissions=['microphone','camera'])
        hc.request.post(url+'/api/auth/login',headers=H,data={'email':'admin@vyra.local','password':'Admin-browser-123'})
        aid=hc.request.get(url+'/api/bootstrap').json()['user']['id']
        gid=hc.request.post(url+'/api/admin/users',headers=H,data={'name':'Luna Martins','username':'luna','email':'luna@example.com','password':'Community-123'}).json()['user']['id']
        gc.request.post(url+'/api/auth/login',headers=H,data={'email':'luna@example.com','password':'Community-123'})
        host=hc.new_page();guest=gc.new_page();errors=[]
        for p in (host,guest):p.on('pageerror',lambda e:errors.append(str(e)))
        try:
          host.goto(url+'/comunidade');host.locator('.sx-sidebar [data-cm=new-post]').click();expect(host.locator('#cs-post')).to_be_visible()
          host.get_by_label('Título',exact=True).fill('Cinema, música e boas companhias')
          body=host.get_by_label('Conte para a comunidade');body.fill('Uma história fica ainda melhor quando a gente compartilha. 🎬')
          body.evaluate('(el)=>{const range=document.createRange();range.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(range);}')
          host.get_by_role('button',name='Negrito',exact=True).click();expect(body.locator('strong')).to_contain_text('Uma história')
          host.locator('[data-cs-cover]').set_input_files(str(ROOT/'static/assets/hero.png'));expect(host.locator('.cs-cover-editor')).to_have_class(__import__('re').compile('has-cover'))
          host.locator('[data-cs=add-block][data-kind=audio]').click();host.locator('[data-cs-file]').last.set_input_files(str(audio));expect(host.locator('.cs-media-block audio')).to_be_visible()
          host.locator('[data-cs=add-block][data-kind=video]').click();host.locator('[data-cs-file]').last.set_input_files(str(ROOT/'static/assets/sintel-trailer.mp4'));expect(host.locator('.cs-media-block video')).to_be_visible(timeout=20000)
          host.get_by_label('Buscar pessoas para marcar').fill('luna');host.locator('#cs-results-people [data-cs=tag]').click();expect(host.locator('#cs-tags-people')).to_contain_text('@luna')
          host.get_by_label('Buscar filmes e séries para marcar').fill('Horizonte');host.locator('#cs-results-titles [data-cs=tag]').first.click();expect(host.locator('#cs-tags-titles')).to_contain_text('Horizonte')
          host.locator('.cs-editor-main').evaluate('(e)=>e.scrollTop=0');host.screenshot(path=str(out/'studio-editor-desktop.png'))
          host.get_by_role('button',name='Salvar',exact=True).click();expect(host.locator('#cs-save-state')).to_contain_text('Rascunho salvo',timeout=10000)
          drafts=hc.request.get(url+'/api/community/drafts').json()['drafts'];assert len(drafts)==1,drafts;did=drafts[0]['id'];assert gc.request.get(url+'/api/community/drafts/'+did).status==404
          host.locator('#modal [data-action=close]').click();host.locator('.sx-sidebar [data-cm=new-post]').click();expect(host.get_by_label('Título',exact=True)).to_have_value('Cinema, música e boas companhias');host.locator('[data-cs=drafts]').click();host.locator('[data-cs=open-draft]').click();expect(host.locator('#cs-tags-people')).to_contain_text('@luna')
          host.get_by_role('button',name='Prévia',exact=False).click()
          expect(host.locator('#cs-post-preview audio')).to_be_visible();expect(host.locator('#cs-post-preview video')).to_be_visible()
          host.locator('[data-cs=publish]').click();host.wait_for_url('**/comunidade/post/*');host.get_by_role('heading',name='Cinema, música e boas companhias',exact=True).wait_for();pid=host.url.split('/')[-1]
          expect(host.locator('.cs-document strong').first).to_contain_text('Uma história');expect(host.locator('.cs-mention')).to_contain_text('@luna');assert hc.request.get(url+'/api/community/drafts').json()['drafts']==[]
          guest.goto(url+'/comunidade/post/'+pid);expect(guest.locator('.cs-document audio')).to_be_visible();guest.locator('.cs-document video').evaluate('(v)=>{v.muted=true;return v.play()}');expect(guest.locator('.cs-document video')).to_have_js_property('paused',False);guest.locator('.cs-document video').evaluate('(v)=>v.pause()');assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth');guest.screenshot(path=str(out/'studio-post-mobile.png'),full_page=True)
          guest.goto(url+'/comunidade');guest.locator('.sx-compose [data-cm=new-post]').first.click();expect(guest.locator('#cs-post')).to_be_visible();guest.get_by_label('Título',exact=True).fill('Rascunho no celular');guest.get_by_label('Conte para a comunidade').fill('Boas histórias cabem em qualquer tela.');guest.wait_for_timeout(250);guest.screenshot(path=str(out/'studio-editor-mobile.png'));assert guest.locator('#modal').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1');assert guest.get_by_label('Conte para a comunidade').evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)')>=16;guest.locator('#modal [data-action=close]').click()
          host.goto(url+'/comunidade?tab=games');expect(host.locator('.cs-game-card')).to_have_count(2);host.screenshot(path=str(out/'studio-games-desktop.png'),full_page=True)
          host.locator('[data-cs=game-room][data-kind=colors]').click();expect(host.locator('#cs-room')).to_be_visible();host.get_by_label('Nome da sala').fill('Clube do cinema · mesa de sábado');host.get_by_label('Sobre o encontro').fill('Uma rodada, bons amigos e muitas histórias.');host.get_by_label('Aprovar quem entra',exact=False).uncheck();host.screenshot(path=str(out/'studio-room-desktop.png'));host.locator('#cs-room [type=submit]').click();host.locator('.fg-lobby').wait_for();rid=host.url.split('/')[-1]
          assert hc.request.get(url+'/api/community/feed').json()['posts'][0]['room']['id']==rid
          guest.goto(host.url);expect(guest.get_by_role('dialog',name='Convite para jogar')).to_be_visible();guest.screenshot(path=str(out/'studio-invitation-mobile.png'));guest.get_by_role('button',name='Aceitar e jogar',exact=True).click();expect(host.locator('.fg-player')).to_have_count(2);host.get_by_role('button',name='Iniciar partida',exact=False).click();expect(guest.locator('.fg-hand .fg-card')).to_have_count(7)
          host.evaluate('document.activeElement?.blur()');host.locator('#sx-room-games').screenshot(path=str(out/'studio-cards-desktop.png'));guest.evaluate('document.activeElement?.blur()');guest.locator('#sx-room-games').screenshot(path=str(out/'studio-cards-mobile.png'));assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth')
          guest.locator('#sx-room-games').evaluate('(el)=>el.requestFullscreen=undefined');guest.get_by_role('button',name='Expandir jogo',exact=True).click();expect(guest.locator('#sx-room-games')).to_have_class(__import__('re').compile('fg-expanded'));guest.get_by_role('button',name='Reduzir jogo',exact=True).click()
          guest.get_by_role('button',name='Chat dentro do jogo',exact=True).click();guest.get_by_label('Mensagem no jogo',exact=True).fill('Essa mesa ficou boa demais! 🎉');guest.get_by_role('button',name='Enviar mensagem no jogo',exact=True).click();expect(host.locator('.fg-bubble')).to_contain_text('Essa mesa ficou boa demais!',timeout=10000)
          guest.get_by_role('button',name='Fechar chat do jogo',exact=True).click();guest.get_by_role('button',name='Emojis do jogo',exact=True).click();guest.get_by_role('button',name='Enviar 🔥',exact=True).click();expect(host.locator('.fg-bubble').last).to_contain_text('🔥',timeout=10000)
          expect(guest.get_by_role('button',name='Ativar microfone no jogo',exact=True)).to_be_disabled()
          host.locator(f'[data-audience="{gid}"] [data-cm=room-promote]').click();expect(guest.get_by_role('button',name='Ativar microfone no jogo',exact=True)).to_be_enabled();guest.evaluate('''()=>{const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async constraints=>{if(constraints.audio&&!constraints.video){const ctx=new AudioContext();await ctx.resume();const osc=ctx.createOscillator(),gain=ctx.createGain(),dest=ctx.createMediaStreamDestination();osc.frequency.value=330;gain.gain.value=.2;osc.connect(gain).connect(dest);osc.start();window.studioTone={ctx,osc,gain};return dest.stream;}return original(constraints);}}''');guest.route('**/api/community/rooms/*/poll',lambda route:route.continue_(post_data=json.dumps({**route.request.post_data_json,'mic':False})));guest.get_by_role('button',name='Ativar microfone no jogo',exact=True).click();guest.wait_for_timeout(1100);guest.unroute('**/api/community/rooms/*/poll');expect(guest.locator('[data-game=mic]')).to_have_attribute('aria-pressed','true');host.get_by_role('button',name='Ouvir a sala',exact=True).click();expect(host.locator('.fg-voice-bubble')).to_contain_text('Luna Martins',timeout=20000)
          host.locator('#sx-room-games').screenshot(path=str(out/'studio-game-voice-chat.png'));guest.evaluate('studioTone.gain.gain.value=0');expect(host.locator('.fg-voice-bubble')).to_have_count(0,timeout=10000);guest.evaluate('studioTone.gain.gain.value=.2');expect(host.locator('.fg-voice-bubble')).to_contain_text('Luna Martins',timeout=10000);host.locator(f'[data-seat="{gid}"] [data-cm=room-mute]').click();expect(guest.locator('[data-game=mic]')).to_be_disabled();expect(guest.locator('[data-game=mic]')).to_have_attribute('aria-pressed','false')
          # Deterministic endgame on the isolated server: verifies UNO, visual actions and rank.
          with sqlite3.connect(dbpath) as db:
              row=db.execute('SELECT state FROM community_games WHERE room_id=?',(rid,)).fetchone();s=json.loads(row[0]);s.update(hands={aid:['red:3','red:7'],gid:['red:1','blue:4']},discard=['red:5'],color='red',turn=0,deadline=time.time()+60);db.execute('UPDATE community_games SET state=?,revision=revision+1 WHERE room_id=?',(json.dumps(s),rid))
          expect(host.locator('.fg-hand .fg-card')).to_have_count(2);host.get_by_role('button',name='UNO!',exact=True).click();expect(host.get_by_role('button',name='UNO! preparado',exact=True)).to_be_visible()
          host.evaluate("window.gameEffects=[];new MutationObserver(rs=>rs.forEach(r=>r.addedNodes.forEach(n=>{if(n.className)window.gameEffects.push(n.className)}))).observe(document.querySelector('.fg-effects'),{childList:true})")
          host.get_by_role('button',name='Jogar Vermelho 3',exact=True).click();expect(guest.locator('.fg-event.uno')).to_contain_text('UNO!',timeout=10000);assert host.evaluate("window.gameEffects.some(x=>x.includes('fg-flying'))")
          guest.get_by_role('button',name='Jogar Vermelho 1',exact=True).click();expect(host.get_by_role('button',name='Jogar Vermelho 7',exact=True)).to_be_enabled();host.get_by_role('button',name='Jogar Vermelho 7',exact=True).click();expect(guest.locator('.fg-result')).to_contain_text('Theo Almeida venceu!',timeout=10000)
          rank=hc.request.get(url+'/api/community/games/ranking').json();assert rank['leaders'][0]['id']==aid and rank['leaders'][0]['points']==30,rank
          # New match invites again; a hidden word is never present in the other player's response.
          host.locator('[data-game=create]').click();guest.get_by_role('button',name='Aceitar e jogar',exact=True).click();host.locator('[data-game=cancel]').click();host.get_by_role('button',name='Confirmar encerramento',exact=True).click();host.locator('[data-game=create][data-kind=draw]').click();guest.get_by_role('button',name='Aceitar e jogar',exact=True).click();expect(host.locator('.fg-player')).to_have_count(2);host.get_by_role('button',name='Iniciar partida',exact=False).click();host.locator('#sx-drawing-canvas').wait_for();guest.locator('#sx-guess').wait_for()
          word=hc.request.get(url+f'/api/community/rooms/{rid}/game').json()['game']['word'];assert 'word' not in gc.request.get(url+f'/api/community/rooms/{rid}/game').json()['game']
          box=host.locator('#sx-drawing-canvas').bounding_box();host.mouse.move(box['x']+40,box['y']+40);host.mouse.down();host.mouse.move(box['x']+100,box['y']+100,steps=8);host.mouse.up()
          guest.get_by_label('Qual é a palavra?',exact=True).fill('Meu palpite');guest.wait_for_timeout(1500);expect(guest.get_by_label('Qual é a palavra?',exact=True)).to_have_value('Meu palpite')
          assert gc.request.get(url+f'/api/community/rooms/{rid}/game').json()['game']['strokes']
          host.locator('#sx-room-games').screenshot(path=str(out/'studio-drawing-desktop.png'));guest.locator('#sx-room-games').screenshot(path=str(out/'studio-drawing-mobile.png'))
          guest.get_by_label('Qual é a palavra?',exact=True).fill(word);guest.locator('#sx-game-guess').get_by_role('button',name='Enviar',exact=False).click();expect(host.locator('.fg-guesses')).to_contain_text('Acertou!',timeout=10000)
          guest.goto(url+'/comunidade');expect(guest.get_by_role('region',name='Ranking dos jogos')).to_be_visible();expect(guest.locator('.cs-feed-rank')).to_contain_text('Theo Almeida');guest.screenshot(path=str(out/'studio-feed-rank-mobile.png'),full_page=True);assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth')
          assert not errors,errors
          print(json.dumps({'rich_editor':True,'audio_video_upload':True,'draft_private_restore':True,'mentions':True,'room_feed_invite':True,'game_popup':True,'uno_and_rules':True,'card_animation':True,'chat_emoji_bubbles':True,'actual_voice_indicator':True,'host_mute':True,'hidden_drawing_word':True,'ranking_in_mobile_feed':True,'mobile_no_overflow':True,'browser_errors':errors}))
        except Exception:
          for name,p in [('host',host),('guest',guest)]:
            p.screenshot(path=str(out/f'studio-failure-{name}.png'),full_page=True)
            print(name,p.url,p.locator('.cs-error,.sx-game-error').all_text_contents(),errors)
          raise
        finally:browser.close()
    finally:server.shutdown()
