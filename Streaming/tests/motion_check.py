"""Exercise actual motion, scroll choreography, lifecycle and reduced-motion behavior."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.packages'))
from playwright.sync_api import sync_playwright

def swipe(session, x, y, dx, dy=0):
    session.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
    for i in range(1,13):
        session.send('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'x':x+dx*i/12,'y':y+dy*i/12}]})
        time.sleep(.018)
    session.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})

def run():
    output = ROOT / 'test-results'
    output.mkdir(exist_ok=True)
    checks, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            headless=True, args=['--no-first-run', '--no-default-browser-check', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows'])
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='no-preference')
        page = context.new_page()
        page.set_default_timeout(12000)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto('http://localhost:8000', wait_until='networkidle')
        page.wait_for_function('() => window.VyraMotion?.getStatus().mounted')
        page.wait_for_timeout(1700)
        assert not page.evaluate('window.VyraMotion.getStatus().paused')
        assert page.locator('.vx-starfield').count() == 1
        assert page.evaluate('window.VyraMotion.getStatus().particles') >= 50
        assert page.evaluate('Array.from(document.querySelector(".vx-starfield").getContext("2d").getImageData(0,0,250,250).data).some((v,i)=>i%4===3 && v>0)')
        checks.append('Canvas renders particles; cinematic entrance completes')
        page.screenshot(path=str(output / 'motion-hero.png'))

        page.mouse.move(120, 230)
        page.wait_for_timeout(350)
        left = page.locator('.hero-art').evaluate('(e)=>getComputedStyle(e).transform')
        page.mouse.move(1280, 450)
        page.wait_for_timeout(500)
        right = page.locator('.hero-art').evaluate('(e)=>getComputedStyle(e).transform')
        assert left != right
        cta = page.get_by_role('link', name='Quero fazer parte', exact=True)
        rect = cta.bounding_box()
        page.mouse.move(rect['x'] + rect['width'] * .75, rect['y'] + rect['height'] * .4)
        page.wait_for_timeout(400)
        assert cta.evaluate('(e)=>e.style.transform.includes("matrix") || e.style.transform.includes("perspective")')
        checks.append('Pointer parallax and magnetic CTA respond to cursor')

        page.locator('#descobrir').scroll_into_view_if_needed()
        page.wait_for_timeout(1300)
        poster = page.locator('.poster-button').first
        r = poster.bounding_box()
        page.mouse.move(r['x'] + r['width'] * .8, r['y'] + r['height'] * .35)
        page.wait_for_timeout(400)
        assert poster.evaluate('(e)=>e.style.transform.includes("rotateY")')
        assert poster.evaluate('(e)=>e.style.getPropertyValue("--vx-glare")') == '1'
        page.screenshot(path=str(output / 'motion-cards.png'))
        row = page.locator('#home-posters')
        r = row.bounding_box()
        page.mouse.move(r['x'] + r['width'] * .8, r['y'] + 130)
        page.mouse.down()
        page.mouse.move(r['x'] + r['width'] * .35, r['y'] + 130, steps=18)
        page.mouse.up()
        page.wait_for_timeout(650)
        assert row.evaluate('(e)=>e.scrollLeft') > 80
        assert not page.locator('#modal').evaluate('(e)=>e.open')
        checks.append('3D tilt, tracked reflection and inertial drag without accidental opening')

        bounds = page.locator('.vx-story').evaluate('(e)=>({top:e.getBoundingClientRect().top+scrollY,height:e.offsetHeight,pin:e.querySelector(".vx-story-pin").offsetHeight})')
        page.evaluate('(y)=>scrollTo({top:y,behavior:"instant"})', bounds['top'])
        page.wait_for_timeout(800)
        first = page.locator('.vx-scene-card').first.evaluate('(e)=>e.style.transform')
        page.evaluate('(y)=>scrollTo({top:y,behavior:"instant"})', bounds['top'] + (bounds['height'] - bounds['pin']) * .93)
        page.wait_for_timeout(1100)
        last = page.locator('.vx-scene-card').first.evaluate('(e)=>e.style.transform')
        assert first != last
        assert page.evaluate('window.VyraMotion.getStatus().scene') == 2
        page.get_by_role('tab', name='Séries', exact=True).click()
        page.wait_for_timeout(600)
        assert page.get_by_role('tab', name='Séries', exact=True).get_attribute('aria-selected') == 'true'
        assert page.locator('.vx-scene-link').get_attribute('href') == '/series'
        page.screenshot(path=str(output / 'motion-scroll-stage.png'))
        page.get_by_role('tab', name='Séries', exact=True).press('ArrowRight')
        assert page.get_by_role('tab', name='Ao vivo', exact=True).get_attribute('aria-selected') == 'true'
        checks.append('Pinned 3D stage scrubs with scroll; tabs and keyboard control all three scenes')

        page.locator('.vx-device-lab').scroll_into_view_if_needed()
        page.wait_for_timeout(1200)
        before_phone = page.locator('.vx-device-phone').evaluate('(e)=>getComputedStyle(e).transform')
        page.get_by_role('button', name='Celular', exact=True).click()
        page.wait_for_timeout(1250)
        assert page.locator('.vx-device-lab').get_attribute('data-screen') == 'phone'
        assert page.locator('.vx-device-phone').evaluate('(e)=>getComputedStyle(e).transform') != before_phone
        page.screenshot(path=str(output / 'motion-devices.png'))
        checks.append('Interactive device scene changes focus with synchronized preview timelines')
        print('Interactive desktop scenes passed', flush=True)

        page.get_by_role('button', name='Pausar animações', exact=True).click()
        page.wait_for_timeout(250)
        assert page.evaluate('window.VyraMotion.getStatus().paused')
        assert page.locator('.vx-ticker-track').evaluate('(e)=>getComputedStyle(e).animationPlayState') == 'paused'
        assert page.locator('.vx-story-pin').evaluate('(e)=>getComputedStyle(e).position') == 'relative'
        page.get_by_role('button', name='Ativar animações', exact=True).click()
        page.wait_for_timeout(350)
        assert not page.evaluate('window.VyraMotion.getStatus().paused')
        page.emulate_media(reduced_motion='reduce')
        page.wait_for_timeout(250)
        assert page.evaluate('window.VyraMotion.getStatus().paused')
        assert page.locator('.vx-story-pin').evaluate('(e)=>getComputedStyle(e).position') == 'relative'
        assert page.locator('.vx-pending').count() == 0
        page.emulate_media(reduced_motion='no-preference')
        checks.append('User pause and live OS reduced-motion preference leave all content accessible')
        print('Pause and reduced motion passed', flush=True)

        # Route changes run through the actual SPA, including cleanup of observers/listeners.
        for route in ['/filmes', '/series', '/catalogo', '/']:
            page.evaluate('(url)=>navigate(url)', route)
            page.wait_for_timeout(1600)
            assert page.evaluate('window.VyraMotion.getStatus().mounted')
            assert page.locator('.vx-motion-toggle').count() == 1
            page.wait_for_function('() => document.querySelectorAll(".vx-transition").length === 0',timeout=6000)
        assert page.locator('.vx-starfield').count() == 1
        assert page.locator('.vx-story').count() == 1
        page.wait_for_function('() => window.VyraMotion.getStatus().animationCount === 0', timeout=5000)
        page.get_by_role('button', name='Entrar', exact=True).click()
        page.get_by_label('E-mail', exact=True).fill('preview@example.com')
        assert page.locator('#modal').evaluate('(e)=>e.open')
        page.get_by_role('button', name='Fechar', exact=True).click()
        checks.append('Repeated navigation cleans up scenes and transitions; login modal remains usable')
        print('Navigation lifecycle and login passed', flush=True)

        page.bring_to_front()
        frames = page.evaluate('''() => new Promise(resolve=>{const deltas=[];let last=0,done=false;const end=()=>{done=true;resolve(deltas)};setTimeout(end,4500);function step(t){if(done)return;if(last)deltas.push(t-last);last=t;if(deltas.length<90)requestAnimationFrame(step);else end()}requestAnimationFrame(step)})''')
        ordered = sorted(frames)
        perf = {'samples':len(ordered),'median_frame_ms': round(ordered[len(ordered)//2], 2) if ordered else None, 'p95_frame_ms': round(ordered[int(len(ordered)*.95)], 2) if ordered else None}
        print(json.dumps({'desktop_checks':checks,'desktop_frame_sample':perf},ensure_ascii=True),flush=True)
        context.close()

        mobile = browser.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=1,
                                  is_mobile=True, has_touch=True, reduced_motion='no-preference')
        mobile.on('pageerror', lambda e: errors.append(str(e)))
        mobile.set_default_timeout(12000)
        mobile.goto('http://localhost:8000', wait_until='networkidle')
        mobile.bring_to_front()
        mobile.wait_for_timeout(1600)
        touch_session = mobile.context.new_cdp_session(mobile)
        assert mobile.evaluate('window.VyraMotion.getStatus().particles') == 54
        assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
        mobile.screenshot(path=str(output / 'motion-mobile-hero.png'))
        touch_session.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':320,'y':470}]})
        mobile.wait_for_timeout(250)
        assert mobile.locator('.hero-art').evaluate('(e)=>Math.abs(parseFloat(e.style.getPropertyValue("--vx-hx"))) > .1')
        touch_session.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
        mobile.locator('#home-posters').scroll_into_view_if_needed()
        mobile.wait_for_timeout(1100)
        r = mobile.locator('#home-posters').bounding_box()
        swipe(touch_session,300,r['y']+120,-190)
        mobile.wait_for_timeout(500)
        assert mobile.locator('#home-posters').evaluate('(e)=>e.scrollLeft') > 30
        assert not mobile.locator('#modal').evaluate('(e)=>e.open')
        mb = mobile.locator('.vx-story').evaluate('(e)=>e.getBoundingClientRect().top+scrollY')
        mobile.evaluate('(top)=>scrollTo({top,behavior:"instant"})', mb)
        mobile.wait_for_timeout(800)
        mobile.get_by_role('tab', name='Séries', exact=True).tap()
        mobile.wait_for_timeout(600)
        assert mobile.get_by_role('tab', name='Séries', exact=True).get_attribute('aria-selected') == 'true'
        assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
        mobile.screenshot(path=str(output / 'motion-mobile-stage.png'))
        r = mobile.locator('.vx-stage').bounding_box()
        swipe(touch_session,290,r['y']+100,-170)
        mobile.wait_for_timeout(850)
        assert mobile.get_by_role('tab', name='Ao vivo', exact=True).get_attribute('aria-selected') == 'true'
        swipe(touch_session,85,r['y']+100,170)
        mobile.wait_for_timeout(850)
        assert mobile.get_by_role('tab', name='Séries', exact=True).get_attribute('aria-selected') == 'true'
        mobile.locator('.vx-device-lab').scroll_into_view_if_needed()
        mobile.wait_for_timeout(1200)
        mobile.get_by_role('button', name='Tablet', exact=True).tap()
        mobile.wait_for_timeout(1100)
        assert mobile.locator('.vx-device-lab').get_attribute('data-screen') == 'tablet'
        r = mobile.locator('.vx-device-scene').bounding_box()
        swipe(touch_session,280,r['y']+110,-150)
        mobile.wait_for_timeout(1300)
        assert mobile.locator('.vx-device-lab').get_attribute('data-screen') == 'phone'
        assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
        mobile.screenshot(path=str(output / 'motion-mobile-devices.png'))
        mobile.get_by_role('button', name='Abrir menu', exact=True).tap()
        mobile.get_by_role('link', name='Filmes', exact=True).tap()
        mobile.get_by_role('heading', name='A noite pede um bom filme.', exact=True).wait_for()
        checks.append('Mobile: touch-reactive hero, native carousel swipe, 3D stage swipes, device swipes, menu and no overflow')

        assert not errors, errors
        result = {'checks': checks, 'javascript_errors': errors, 'desktop_frame_sample': perf}
        (output / 'motion-results.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
        print(json.dumps(result, indent=2, ensure_ascii=True))
        browser.close()

if __name__ == '__main__':
    run()
