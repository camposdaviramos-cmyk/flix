"""Install only isolated static files; never changes server/application configuration."""
import json, secrets, shutil, urllib.request
from pathlib import Path
base=Path('/opt/flix/Streaming/static/previews')
manifest=Path(__file__).with_name('preview.json')
if manifest.exists():
    folder=base/json.loads(manifest.read_text())['folder']
else:
    folder=base/('astronauta-'+secrets.token_hex(12))
folder.mkdir(parents=True,exist_ok=True)
vendor=folder/'vendor'; vendor.mkdir(exist_ok=True)
files={
 'three.module.js':'build/three.module.js',
 'three.core.js':'build/three.core.js',
 'GLTFLoader.js':'examples/jsm/loaders/GLTFLoader.js',
 'OrbitControls.js':'examples/jsm/controls/OrbitControls.js',
 'BufferGeometryUtils.js':'examples/jsm/utils/BufferGeometryUtils.js',
 'RoomEnvironment.js':'examples/jsm/environments/RoomEnvironment.js',
 'LICENSE':'LICENSE',
}
for name,remote in files.items():
    data=urllib.request.urlopen('https://unpkg.com/three@0.180.0/'+remote,timeout=30).read()
    if name.endswith('.js'):
        data=data.decode().replace("from 'three'", "from './three.module.js'").replace("from '../utils/BufferGeometryUtils.js'", "from './BufferGeometryUtils.js'").encode()
    (vendor/name).write_bytes(data)
for filename in ['index.html','preview.css','preview.js']:
    shutil.copyfile(Path(__file__).with_name(filename),folder/filename)
shutil.copyfile(Path(__file__).with_name('astronauta.glb'),folder/'astronauta.glb')
result=dict(folder=folder.name,path=str(folder),url='https://flix.devspacey.com/static/previews/'+folder.name+'/index.html')
manifest.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
