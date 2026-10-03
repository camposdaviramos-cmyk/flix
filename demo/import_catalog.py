"""Idempotent demo import. Does not replace an administrator's existing records."""
import json,sqlite3,time,urllib.request,html,concurrent.futures
from pathlib import Path
BASE=Path('/opt/flix/demo');ROOT=Path('/opt/flix/Streaming')
def import_into(db_path, catalog=None):
 entries=catalog or json.loads((BASE/'catalog.json').read_text());db=sqlite3.connect(db_path);db.execute('PRAGMA foreign_keys=ON');added=0
 with db:
  for e in entries:
   if db.execute('SELECT 1 FROM content WHERE id=?',(e['id'],)).fetchone():continue
   credit=e['summary']+'\n\nCréditos: '+e['credit']+'\nFonte: '+e['source']+('\nLicença: '+e['license'] if e.get('license') else '')
   duration=e.get('duration') or (f"{len(e['episodes'])} partes" if e['kind']=='series' else 'Filme completo')
   db.execute('INSERT INTO content(id,title,kind,genre,year,rating,description,poster,backdrop,duration,video_url,featured,published,sample,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(e['id'],e['title'],e['kind'],e['genre'],e['year'],'L' if e['rating']=='Livre' else '—',credit,e['poster'],e['poster'],duration,e.get('video_url',''),1,1,0,time.time()))
   for n,ep in enumerate(e.get('episodes',[]),1):
    db.execute('INSERT INTO episodes VALUES(?,?,?,?,?,?,?)',(e['id']+'-part-'+str(n),e['id'],1,n,ep['title'],ep['video_url'],ep.get('duration','')))
   added+=1
 db.close();return added
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('database');a=p.parse_args();print('Conteúdos adicionados:',import_into(a.database))
