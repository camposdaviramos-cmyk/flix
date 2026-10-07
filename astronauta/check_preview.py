import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    url=json.loads(Path(__file__).with_name('preview.json').read_text())['url']+'?v=3'
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--enable-unsafe-swiftshader'])
        for label,size in [('desktop',{'width':1440,'height':1100}),('mobile',{'width':390,'height':844})]:
            page=await browser.new_page(viewport=size,device_scale_factor=1,reduced_motion='reduce')
            errors=[];bad=[];requests=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('response',lambda r:bad.append((r.status,r.url)) if r.status>=400 else None)
            page.on('request',lambda r:requests.append(r.url))
            response=await page.goto(url,wait_until='networkidle',timeout=60000)
            assert response.status==200
            await page.wait_for_selector('#viewport[data-ready="true"]',timeout=30000)
            assert await page.locator('#viewport').get_attribute('data-bones')=='52'
            assert await page.locator('#viewport').get_attribute('data-version')=='3'
            assert await page.locator('#viewport').get_attribute('data-textures')=='4'
            assert await page.locator('canvas').count()==1
            await page.screenshot(path=str(Path(__file__).with_name('preview-'+label+'.png')),full_page=True)
            for name,clip in [('Acenar','Wave'),('Caminhar','WalkInPlace'),('Pose T','pose'),('Flutuar','Float')]:
                await page.get_by_role('button',name=name,exact=True).click()
                assert await page.locator('#viewport').get_attribute('data-animation')==clip
                await page.wait_for_timeout(50)
            await page.get_by_role('button',name='Ver esqueleto',exact=True).click()
            assert await page.get_by_role('button',name='Ocultar esqueleto',exact=True).get_attribute('aria-pressed')=='true'
            await page.get_by_role('button',name='Ocultar esqueleto',exact=True).click()
            await page.get_by_role('button',name='Continuar',exact=True).click()
            await page.get_by_role('button',name='Pausar',exact=True).click()
            assert await page.get_by_role('button',name='Continuar',exact=True).get_attribute('aria-pressed')=='true'
            await page.get_by_role('button',name='Continuar',exact=True).click()
            await page.get_by_role('button',name='Pausar',exact=True).click()
            await page.locator('#speed').select_option('1.5')
            for view in ['Lateral','Vista em três quartos','Costas','Frente']:
                await page.get_by_role('button',name=view,exact=True).click()
                assert await page.get_by_role('button',name=view,exact=True).get_attribute('aria-pressed')=='true'
            await page.get_by_role('button',name='↺ Recentrar',exact=True).click()
            box=await page.locator('canvas').bounding_box()
            await page.mouse.move(box['x']+box['width']*.5,box['y']+box['height']*.5)
            await page.mouse.down()
            await page.mouse.move(box['x']+box['width']*.6,box['y']+box['height']*.5,steps=4)
            await page.mouse.up()
            assert await page.locator('#viewport').get_attribute('data-view')=='free'
            assert await page.locator('button[data-view][aria-pressed="true"]').count()==0
            await page.get_by_role('button',name='↺ Recentrar',exact=True).click()
            assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            asset=await page.request.get(url.replace('index.html','astronauta.glb'))
            assert asset.status==200 and (await asset.body())[:4]==b'glTF'
            assert not errors,errors
            assert not bad,bad
            # Cloudflare may inject its existing site analytics at the edge.
            assert all(r.startswith(('https://flix.devspacey.com/','blob:https://flix.devspacey.com/','https://static.cloudflareinsights.com/','https://cloudflareinsights.com/','data:')) for r in requests),requests
            print(json.dumps(dict(view=label,status=response.status,errors=errors,bones=52,controls='PASS',assets='PASS',requests=len(requests))),flush=True)
            await page.close()
        page=await browser.new_page()
        home=await page.goto('https://flix.devspacey.com/',wait_until='domcontentloaded')
        assert home.status==200
        print('Existing home page: HTTP 200')
        await browser.close()

asyncio.run(main())
