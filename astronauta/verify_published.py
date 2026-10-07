import asyncio,hashlib,json
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    source=Path(__file__).parent
    info=json.loads((source/'preview.json').read_text())
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1280,'height':1100},reduced_motion='reduce')
        messages=[]
        page.on('console',lambda msg: messages.append({'type':msg.type,'text':msg.text}) if msg.type in ['error','warning'] else None)
        await page.goto(info['url']+'?v=3',wait_until='networkidle')
        await page.wait_for_selector('#viewport[data-ready="true"][data-version="3"]',timeout=60000)
        digest=await page.evaluate('''async()=>{
          const response=await fetch('./astronauta.glb?v=3');
          if(!response.ok)throw Error('GLB HTTP '+response.status);
          const digest=await crypto.subtle.digest('SHA-256',await response.arrayBuffer());
          return Array.from(new Uint8Array(digest)).map(x=>x.toString(16).padStart(2,'0')).join('');
        }''')
        assert digest==hashlib.sha256((source/'astronauta.glb').read_bytes()).hexdigest()
        assert await page.locator('#viewport').get_attribute('data-textures')=='4'
        errors=[m for m in messages if m['type']=='error' and 'static.cloudflareinsights.com' not in m['text']]
        assert not errors,errors
        print('Four embedded textures loaded; no astronaut resource errors: PASS',flush=True)
        await page.get_by_role('button',name='Pose T',exact=True).click()
        await page.screenshot(path=str(source/'updated-desktop.png'),full_page=True)
        for name in ['Lateral','Vista em três quartos']:
            await page.get_by_role('button',name=name,exact=True).click()
            await page.locator('.stage').screenshot(path=str(source/('published-v3-'+name.replace(' ','-')+'.png')))
        print('Published GLB matches final local asset; final desktop render: PASS',flush=True)
        await browser.close()

asyncio.run(main())
