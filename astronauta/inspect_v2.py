import asyncio, functools, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    handler=functools.partial(SimpleHTTPRequestHandler,directory=str(Path(__file__).parent))
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1280,'height':1100},reduced_motion='reduce')
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(f'http://127.0.0.1:{server.server_port}/index.html',wait_until='networkidle')
        await page.wait_for_selector('#viewport[data-ready="true"]',timeout=60000)
        await page.get_by_role('button',name='Pose T',exact=True).click()
        await page.locator('.stage').screenshot(path=str(Path(__file__).with_name('v3-front.png')))
        for view in ['Lateral','Vista em três quartos','Costas']:
            await page.get_by_role('button',name=view,exact=True).click()
            await page.wait_for_timeout(500)
            await page.locator('.stage').screenshot(path=str(Path(__file__).with_name('v3-'+view.lower().replace(' ','-')+'.png')))
        assert not errors,errors
        print('Local front/side/back render: PASS',flush=True)
        await browser.close()
    server.shutdown();server.server_close()

asyncio.run(main())
