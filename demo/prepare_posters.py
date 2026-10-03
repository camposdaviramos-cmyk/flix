import json,urllib.request,concurrent.futures,html
from pathlib import Path
BASE=Path('/opt/flix/demo');assets=Path('/opt/flix/Streaming/static/assets/demo');assets.mkdir(exist_ok=True)
entries=json.loads((BASE/'catalog.json').read_text())
def prepare(e):
 if e['kind']!='channel':
  url='https://archive.org/services/img/'+e['archive']
  try:
   with urllib.request.urlopen(url,timeout=20) as r: data=r.read(2000000);assert r.headers.get('Content-Type','').startswith('image/')
   p=assets/(e['id']+'.jpg');p.write_bytes(data)
  except Exception as err:print('Poster indisponível:',e['title'],err);e['poster']='/static/assets/hero.png';return
 else:
  # A neutral word card identifies the source without copying a broadcaster's logo.
  p=assets/(e['id']+'.svg');label=e['title'].split(' — ')[0]
  svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600" viewBox="0 0 600 600"><rect width="600" height="600" rx="40" fill="#17101f"/><circle cx="300" cy="250" r="140" fill="#251831" stroke="#b34467" stroke-width="3"/><text x="300" y="230" text-anchor="middle" fill="#faf6ff" font-family="sans-serif" font-size="40" font-weight="bold">{html.escape(label)}</text><text x="300" y="280" text-anchor="middle" fill="#c9b9d5" font-family="sans-serif" font-size="25">{html.escape(e["lang"])}</text><rect x="220" y="340" width="160" height="45" rx="8" fill="#d92448"/><text x="300" y="370" text-anchor="middle" fill="white" font-family="sans-serif" font-size="21" font-weight="bold">AO VIVO</text><text x="300" y="500" text-anchor="middle" fill="#af97ba" font-family="sans-serif" font-size="22">DEMONSTRAÇÃO</text></svg>'
  p.write_text(svg)
 e['poster']='/static/assets/demo/'+p.name
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:list(ex.map(prepare,entries))
(BASE/'catalog.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2))
lines=['#EXTM3U']
for e in entries:
 if e['kind']=='channel':lines += [f'#EXTINF:-1 tvg-logo="https://flix.devspacey.com{e["poster"]}" group-title="Canais públicos - demonstração",{e["title"]}',e['video_url']]
Path('/opt/flix/Streaming/static/demo-tv.m3u').write_text('\n'.join(lines)+'\n')
print('Imagens preparadas:',len(entries))
