import concurrent.futures,json,urllib.request,urllib.parse,re
from pathlib import Path
BASE=Path('/opt/flix/demo')
entries=[
 dict(id='demo-big-buck-bunny',title='Big Buck Bunny',kind='movie',genre='Animação',year=2008,rating='Livre',archive='BigBuckBunny_124',file='Content/big_buck_bunny_720p_surround.mp4',summary='Um coelho tranquilo enfrenta três pequenos animais que perturbam seu dia. Curta-metragem completo, em demonstração.',credit='Blender Foundation — Big Buck Bunny (2008). Licença CC BY 3.0. Vídeo preservado com os créditos finais.',license='https://creativecommons.org/licenses/by/3.0/'),
 dict(id='demo-sintel',title='Sintel',kind='movie',genre='Fantasia',year=2010,rating='Não classificado',archive='sintel_202604',file='Sintel.ia.mp4',summary='Uma jovem atravessa terras distantes à procura de um pequeno dragão. Filme completo de demonstração; pode conter violência.',credit='Blender Foundation — Sintel (2010). Licença original CC BY 3.0, conforme durian.blender.org/sharing/. Vídeo mantido com seus créditos.',license='https://creativecommons.org/licenses/by/3.0/'),
 dict(id='demo-tears-of-steel',title='Tears of Steel',kind='movie',genre='Ficção científica',year=2012,rating='Não classificado',archive='tears-of-steel_202601',file='Tears of Steel.mp4',summary='Um grupo tenta reconstruir um evento do passado para enfrentar uma ameaça robótica. Curta completo de demonstração, com legendas em inglês.',credit='Blender Institute / Ian Hubert — Tears of Steel (2012). Obra original CC BY 3.0; esta cópia com legendas está identificada no acervo como CC BY-ND 4.0 e é reproduzida sem alterações.',license='https://creativecommons.org/licenses/by-nd/4.0/'),
 dict(id='demo-caminandes',title='Caminandes',kind='series',genre='Animação',year=2013,rating='Livre',archive='Caminandes2GranDillama',summary='As aventuras de Koro, uma lhama da Patagônia. Série de três curtas completos para demonstrar reprodução e retomada por episódio.',credit='Pablo Vázquez e Blender Foundation — Caminandes. CC BY 3.0. Vídeos preservados com os créditos.',license='https://creativecommons.org/licenses/by/3.0/',episodes=[dict(title='Llama Drama',archive='Caminandes1LlamaDrama',file='01_llama_drama_1080p.mp4'),dict(title='Gran Dillama',archive='Caminandes2GranDillama',file='02_gran_dillama_1080p.mp4'),dict(title='Llamigos',archive='CaminandesLlamigos',file='Caminandes_ Llamigos-1080p.mp4')]),
 dict(id='demo-tih-minh',title='Tih-Minh',kind='series',genre='Cinema clássico',year=1918,rating='Não classificado',archive='Tih-Minh',summary='Serial mudo de aventura e espionagem de Louis Feuillade (1918). A versão do acervo reúne os capítulos originais em sete partes de arquivo; a lista abaixo segue essa divisão, não a numeração original dos 12 capítulos.',credit='Louis Feuillade / Gaumont — Tih-Minh (1918). Acervo Internet Archive identificado como CC0 1.0. Cinema mudo; intertítulos em francês/neerlandês.',license='https://creativecommons.org/publicdomain/zero/1.0/',episodes=[dict(title=f'Parte {n} do acervo',archive='Tih-Minh',file=f'Tih-Minh.{n:02d}.mp4') for n in range(1,8)])]
channels=[
 ('demo-tv-camara','TV Câmara','Português','https://stream3.camara.gov.br/tv1/manifest.m3u8','https://www.camara.leg.br/tv/aovivo','https://www2.camara.leg.br/camaranoticias/tv/institucional.html'),
 ('demo-france24-en','France 24 — English','Inglês','https://live.france24.com/hls/live/2037179-b/F24_FR_HI_HLS/master_5000.m3u8','https://www.france24.com/en/live',''),
 ('demo-france24-fr','France 24 — Français','Francês','https://live.france24.com/hls/live/2037179-b/F24_FR_HI_HLS/master_5000.m3u8','https://www.france24.com/fr/direct',''),
 ('demo-france24-es','France 24 — Español','Espanhol','https://live.france24.com/hls/live/2037220-b/F24_ES_HI_HLS/master_5000.m3u8','https://www.france24.com/es/en-vivo',''),
 ('demo-dw-en','DW — English','Inglês','https://dwamdstream103.akamaized.net/hls/live/2015526/dwstream103/master.m3u8','https://www.dw.com/en/live-tv/channel-english',''),
 ('demo-euronews-pt','Euronews — Português','Português','https://6e52fb8b.wurl.com/master/f36d25e7e52f1ba8d7e56eb859c636563214f541/UmxheHhUVi1ldV9FdXJvbmV3c1BvcnR1Z3Vlc19ITFM/playlist.m3u8','https://pt.euronews.com/live','')]
# English uses the publisher's English feed, distinct from French.
channels[1]=tuple(list(channels[1][:3])+['https://live.france24.com/hls/live/2037218/F24_EN_HI_HLS/master_5000.m3u8']+list(channels[1][4:]))
def request(url,headers=None):return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0',**(headers or {})}),timeout=20)
def verify_mp4(e):
 url='https://archive.org/download/'+e['archive']+'/'+urllib.parse.quote(e['file'],safe='/')
 with request(url,{'Range':'bytes=0-1023'}) as r:
  if r.status!=206 or 'video' not in r.headers.get('Content-Type',''):raise ValueError('No seekable video: '+url)
  e['video_url']=url;e['resolved_url']=r.url;e['content_range']=r.headers['Content-Range']
 return e
jobs=[]
for e in entries:
 if e['kind']=='movie':jobs.append(e)
 else:jobs.extend(e['episodes'])
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:list(ex.map(verify_mp4,jobs))
valid=[]
for cid,title,lang,url,source,license_url in channels:
 try:
  with request(url) as r:
   manifest=r.read().decode();assert manifest.startswith('#EXTM3U');assert r.headers.get('Access-Control-Allow-Origin')=='*'
  variants=[l for l in manifest.splitlines() if l and not l.startswith('#')]
  media_url=urllib.parse.urljoin(url,variants[0]) if '#EXT-X-STREAM-INF:' in manifest else url
  with request(media_url) as r:
   media=r.read().decode();assert media.startswith('#EXTM3U');assert r.headers.get('Access-Control-Allow-Origin')=='*'
  segments=[l for l in media.splitlines() if l and not l.startswith('#')];seg=urllib.parse.urljoin(media_url,segments[-1])
  with request(seg,{'Range':'bytes=0-1023'}) as r:assert r.status in (200,206)
  valid.append(dict(id=cid,title=title,kind='channel',genre='Notícias e cidadania',year=2026,rating='Não classificado',duration='Ao vivo',summary=f'Transmissão pública em {lang}, usada nesta demonstração. Fonte e programação da própria emissora; disponibilidade depende do sinal oficial.',credit=title+' — emissora original. Sinal reproduzido sem alteração.',license=license_url,source=source,video_url=url,lang=lang))
  print('Canal válido:',title)
 except Exception as error:print('Canal excluído:',title,str(error))
for e in entries:e['source']='https://archive.org/details/'+e['archive']
(BASE/'catalog.json').write_text(json.dumps(entries+valid,ensure_ascii=False,indent=2))
print('Catálogo preparado:',len(entries),'filmes/séries e',len(valid),'canais')
