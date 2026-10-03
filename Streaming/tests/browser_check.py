import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.packages'))
from playwright.sync_api import sync_playwright

def run():
    results=[]
    output=ROOT/'test-results'
    output.mkdir(exist_ok=True)
    creds=(ROOT/'data/initial-admin.txt').read_text(encoding='utf-8')
    password=next(line.split(': ',1)[1] for line in creds.splitlines() if line.startswith('Senha:'))
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--no-first-run','--no-default-browser-check'])
        page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('requestfailed',lambda r:print('Media request failed:',r.url,r.failure,flush=True) if '.mp4' in r.url else None)
        page.goto('http://localhost:8000',wait_until='networkidle')
        page.get_by_role('heading',name='Histórias que ficam com você.').wait_for()
        page.emulate_media(reduced_motion='reduce')
        page.screenshot(path=str(output/'homepage-desktop.png'),full_page=True)
        page.screenshot(path=str(output/'homepage-viewport.png'))
        assert page.locator('.poster-button').count()>=6
        results.append('Home desktop e catálogo')
        page.get_by_role('button',name='Entrar',exact=True).click()
        page.locator('#auth-email').fill('admin@vyra.local')
        page.locator('#auth-password').fill(password)
        page.get_by_role('button',name='Entrar na minha conta',exact=True).click()
        page.get_by_role('link',name='Painel admin').wait_for()
        page.get_by_role('link',name='Painel admin').click()
        page.get_by_role('heading',name='Tudo sob seu controle.').wait_for()
        page.screenshot(path=str(output/'admin-desktop.png'),full_page=True)
        results.append('Login e dashboard')
        page.get_by_role('link',name='Conteúdos',exact=True).click()
        page.get_by_role('button',name='Adicionar conteúdo',exact=True).click()
        page.locator('#f-title').fill('Teste E2E')
        page.locator('#f-genre').fill('Teste')
        page.locator('#f-video_url').fill('https://storage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4')
        page.get_by_role('button',name='Salvar conteúdo',exact=True).click()
        page.locator('#modal').wait_for(state='hidden')
        page.get_by_role('button',name='Editar Teste E2E',exact=True).wait_for()
        page.get_by_role('button',name='Excluir Teste E2E',exact=True).click()
        page.get_by_role('button',name='Excluir',exact=True).click()
        page.locator('#modal').wait_for(state='hidden')
        results.append('Criar e excluir filme')
        page.get_by_role('link',name='Canais de TV',exact=True).click()
        page.get_by_role('button',name='Importar lista',exact=True).click()
        page.locator('#playlist-text').fill('#EXTM3U\n#EXTINF:-1 group-title="Teste",Canal E2E\nhttps://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8')
        page.get_by_role('button',name='Importar canais',exact=True).click()
        page.locator('#modal').wait_for(state='hidden')
        page.get_by_role('button',name='Editar Canal E2E',exact=True).wait_for()
        page.get_by_role('button',name='Excluir Canal E2E',exact=True).click()
        page.get_by_role('button',name='Excluir',exact=True).click()
        page.locator('#modal').wait_for(state='hidden')
        results.append('Importar M3U')
        page.get_by_role('link',name='Configurações',exact=True).click()
        page.get_by_label('Access Token',exact=True).wait_for()
        assert page.get_by_label('Access Token',exact=True).input_value()==''
        page.screenshot(path=str(output/'settings-desktop.png'),full_page=True)
        results.append('Configurações do checkout')
        page.goto('http://localhost:8000/catalogo',wait_until='networkidle')
        page.locator('#catalog-search').fill('horizonte')
        assert page.locator('#catalog-items .movie-card').count()==1
        page.get_by_role('button',name='Ver Além do Horizonte',exact=True).click()
        page.get_by_role('button',name='Assistir agora',exact=True).click()
        page.locator('#video-player').wait_for()
        try:
            page.wait_for_function('() => document.querySelector("#video-player").readyState >= 1',timeout=30000)
        except Exception:
            print(page.locator('#video-player').evaluate('(v)=>({ready:v.readyState,network:v.networkState,error:v.error?.message,source:v.currentSrc})'),flush=True)
            raise
        page.evaluate('const v=document.querySelector("#video-player");v.pause();v.currentTime=42.625')
        page.wait_for_function('() => Math.abs(document.querySelector("#video-player").currentTime - 42.625) < 0.1 && !document.querySelector("#video-player").seeking')
        with page.expect_response(lambda r:'/api/progress/horizonte' in r.url and r.status==200):
            page.evaluate('document.querySelector("#video-player").dispatchEvent(new Event("pause"))')
        page.screenshot(path=str(output/'player-desktop.png'),full_page=True)
        page.get_by_role('button',name='Fechar',exact=True).click()
        page.get_by_role('button',name='Ver Além do Horizonte',exact=True).click()
        page.locator('.detail-actions [data-action="play"]').click()
        page.wait_for_function('() => document.querySelector("#video-player")?.currentTime >= 42.5',timeout=45000)
        assert page.locator('#video-player').evaluate('(v)=>v.currentTime')<48
        page.get_by_role('button',name='Fechar',exact=True).click()
        results.append('Reprodução real e retomada em 42.625 segundos')
        mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
        mobile.on('pageerror',lambda e:errors.append(str(e)))
        mobile.goto('http://localhost:8000',wait_until='networkidle')
        mobile.get_by_role('heading',name='Histórias que ficam com você.').wait_for()
        mobile.emulate_media(reduced_motion='reduce')
        assert mobile.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Overflow no mobile'
        mobile.screenshot(path=str(output/'homepage-mobile.png'),full_page=True)
        mobile.get_by_role('button',name='Abrir menu',exact=True).click()
        mobile.get_by_role('link',name='Séries',exact=True).click()
        mobile.get_by_role('heading',name='Só mais um episódio.').wait_for()
        assert mobile.locator('.movie-card').count()>0
        results.append('Mobile e navegação sem overflow')
        assert not errors,errors
        print(json.dumps({'checks':results,'javascript_errors':errors},ensure_ascii=True,indent=2))
        browser.close()
if __name__=='__main__':run()
