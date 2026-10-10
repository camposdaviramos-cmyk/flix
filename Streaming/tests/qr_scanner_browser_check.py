"""Read actual generated QR pixels, approve in another context, and stop camera tracks."""
import json,sqlite3,sys,tempfile,threading,time
from pathlib import Path
from playwright.sync_api import sync_playwright
from waitress import create_server
from werkzeug.security import generate_password_hash
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));from app import create_app
OUT=ROOT/'test-results/qr-scanner';OUT.mkdir(parents=True,exist_ok=True);base='http://127.0.0.1:8029';headers={'X-Requested-With':'Flix'}
with tempfile.TemporaryDirectory() as folder:
 app=create_app(folder,testing=True)
 with sqlite3.connect(Path(folder)/'vyra.sqlite3') as db:db.execute("UPDATE users SET password=? WHERE role='admin'",(generate_password_hash('Qr-browser-test-2026'),))
 server=create_server(app,host='127.0.0.1',port=8029,threads=8);threading.Thread(target=server.run,daemon=True).start()
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(args=['--no-sandbox','--enable-unsafe-swiftshader']);tv=browser.new_context(viewport={'width':1280,'height':720},reduced_motion='reduce');phone=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,reduced_motion='reduce');t=tv.new_page();p=phone.new_page();errors=[]
   for page in [t,p]:page.on('pageerror',lambda e:errors.append(str(e)))
   t.goto(base,wait_until='domcontentloaded');t.wait_for_selector('[data-react-page=home]');t.locator('.header [data-action=login]').click()
   t.locator('.login-qr').wait_for();assert t.locator('#auth-email').is_visible();assert t.locator('.login-qr').is_visible();qr=t.locator('.login-qr').get_attribute('src');t.screenshot(path=str(OUT/'login-desktop.png'))
   assert t.locator('.modal-heading .brand-logo').get_attribute('src').endswith('worktv-logo-official-v1.png')
   assert phone.request.post(base+'/api/auth/login',data={'email':'admin@vyra.local','password':'Qr-browser-test-2026'},headers=headers).status==200
   p.goto(base+'/conta',wait_until='domcontentloaded');p.get_by_role('link',name='Escanear QR Code',exact=True).last.click();p.wait_for_selector('[data-react-page=scanner]');assert p.locator('.scanner-video').is_hidden()
   # Same-origin invalid QR must never navigate or authorize anything.
   await_script="""async (src)=>{const image=new Image();image.src=src;await image.decode();const canvas=document.createElement('canvas');canvas.width=640;canvas.height=640;const ctx=canvas.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,640,640);ctx.drawImage(image,20,20,600,600);window.testQRStream=canvas.captureStream(5);window.testCanvas=canvas;Object.defineProperty(navigator.mediaDevices,'getUserMedia',{configurable:true,value:async()=>window.testQRStream});} """
   p.evaluate(await_script,qr);p.get_by_role('button',name='Abrir câmera',exact=True).click();p.get_by_role('button',name='Confirmar entrada',exact=True).wait_for(timeout=20000)
   assert p.evaluate('testQRStream.getTracks().every(t=>t.readyState==="ended")');assert not tv.request.get(base+'/api/bootstrap').json()['user']
   p.screenshot(path=str(OUT/'phone-confirm.png'));p.get_by_role('button',name='Confirmar entrada',exact=True).click();t.wait_for_selector('[data-react-page=member-home]',timeout=15000)
   p.evaluate("navigate('/escanear')");p.wait_for_selector('[data-react-page=scanner]');p.evaluate("Object.defineProperty(navigator.mediaDevices,'getUserMedia',{configurable:true,value:async()=>{throw new DOMException('denied','NotAllowedError')}})");p.get_by_role('button',name='Abrir câmera',exact=True).click();p.get_by_role('alert').filter(has_text='A câmera não foi autorizada').wait_for();assert p.get_by_label('Escolher imagem do QR Code',exact=True).is_enabled();assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
   p.screenshot(path=str(OUT/'phone-scanner.png'))
   # Decode from a chosen image using the exact same reader without uploading it.
   fresh=tv.request.post(base+'/api/auth/device/start',data={},headers=headers).json();svg=fresh['qr']
   imagebytes=p.evaluate("async src=>{const i=new Image();i.src=src;await i.decode();const c=document.createElement('canvas');c.width=600;c.height=600;const x=c.getContext('2d');x.fillStyle='white';x.fillRect(0,0,600,600);x.drawImage(i,0,0,600,600);return c.toDataURL('image/png').split(',')[1]}",svg)
   import base64
   p.get_by_label('Escolher imagem do QR Code',exact=True).set_input_files({'name':'qr.png','mimeType':'image/png','buffer':base64.b64decode(imagebytes)});p.get_by_role('button',name='Confirmar entrada',exact=True).wait_for()
   assert not errors,errors
   result={'status':'PASS','qr_visible_without_extra_click':True,'password_visible':True,'official_logo':True,'actual_pixel_camera_decode':True,'camera_tracks_stopped':True,'phone_approval_tv_login':True,'permission_denial_handled':True,'image_decode':True,'mobile_overflow':False,'page_errors':errors};(OUT/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));browser.close()
 finally:server.close()
