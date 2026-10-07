"""Back up and atomically replace only this presentation's static assets."""
from pathlib import Path
import datetime,json,shutil

source=Path(__file__).parent
info=json.loads((source/'preview.json').read_text())
target=Path(info['path'])
assert target.parent==Path('/opt/flix/Streaming/static/previews')
assert target.name==info['folder'] and target.is_dir()
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')
backup=source/'backups'/stamp;backup.mkdir(parents=True)
for name in ['astronauta.glb','preview.css','preview.js','index.html']:
    shutil.copyfile(target/name,backup/name)
    staging=target/(name+'.tmp')
    shutil.copyfile(source/name,staging)
    staging.replace(target/name)
print(json.dumps(dict(url=info['url']+'?v=3',backup=str(backup)),indent=2))
