"""Focused mobile gesture diagnostics, with actual Chrome touch events."""
import sys, json, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.packages'), str(ROOT / 'tests')]
from playwright.sync_api import sync_playwright
from motion_check import swipe

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
    page = browser.new_page(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,reduced_motion='no-preference')
    page.set_default_timeout(10000)
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://localhost:8000',wait_until='networkidle')
    page.wait_for_timeout(1800)
    print('Loaded mobile',flush=True)
    session=page.context.new_cdp_session(page)
    session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':320,'y':470}]})
    print('Touch down sent',flush=True)
    page.wait_for_timeout(200)
    print('Hero transform',page.locator('.hero-art').evaluate('(e)=>e.style.getPropertyValue("--vx-hx")'),flush=True)
    session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    print('Touch up sent',flush=True)
    page.locator('#home-posters').scroll_into_view_if_needed()
    print('Scrolled to posters',flush=True)
    page.wait_for_timeout(1000)
    r=page.locator('#home-posters').bounding_box()
    swipe(session,300,r['y']+120,-190)
    page.wait_for_timeout(600)
    print('Poster offset',page.locator('#home-posters').evaluate('(e)=>e.scrollLeft'),flush=True)
    top=page.locator('.vx-story').evaluate('(e)=>e.getBoundingClientRect().top+scrollY')
    page.evaluate('(top)=>scrollTo({top,behavior:"instant"})',top)
    page.wait_for_timeout(900)
    page.get_by_role('tab',name='Séries',exact=True).tap()
    page.wait_for_timeout(600)
    print('Scene selected',page.evaluate('VyraMotion.getStatus()'),flush=True)
    r=page.locator('.vx-stage').bounding_box()
    swipe(session,290,r['y']+100,-170)
    page.wait_for_timeout(800)
    assert page.get_by_role('tab',name='Ao vivo',exact=True).get_attribute('aria-selected')=='true'
    page.screenshot(path=str(ROOT/'test-results/motion-mobile-stage.png'))
    print('Scene swipe passed',flush=True)
    page.locator('.vx-device-lab').scroll_into_view_if_needed()
    page.wait_for_timeout(1200)
    page.get_by_role('button',name='Tablet',exact=True).tap()
    page.wait_for_timeout(1000)
    r=page.locator('.vx-device-scene').bounding_box()
    swipe(session,280,r['y']+110,-150)
    page.wait_for_timeout(1200)
    assert page.locator('.vx-device-lab').get_attribute('data-screen')=='phone'
    page.screenshot(path=str(ROOT/'test-results/motion-mobile-devices.png'))
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors, errors
    print('Device swipe and layout passed',flush=True)
    browser.close()
