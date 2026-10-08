import sys,tempfile,sqlite3,unittest,re
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
class MigrationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.app=create_app(self.tmp.name,testing=True);self.client=self.app.test_client()
 def tearDown(self):self.tmp.cleanup()
 def test_initial_text_is_noscript_and_react_is_local(self):
  response=self.client.get('/');html=response.text
  noscript=re.search(r'<noscript>(.*?)</noscript>',html,re.S).group(1)
  self.assertIn('Filmes, séries e TV ao vivo',noscript)
  main_html=html.replace('<noscript>'+noscript+'</noscript>','')
  self.assertNotIn('<article><h2>',main_html)
  self.assertIn('aria-label="Carregando WorkTV"',main_html)
  self.assertRegex(html,r'data-worktv-react src="/static/worktv-react-[a-f0-9]+.js')
 def test_catalog_queries_do_not_grow_with_titles_and_do_not_leak_sources(self):
  original=sqlite3.connect
  with original(Path(self.tmp.name)/'vyra.sqlite3') as db:
   db.executemany('INSERT INTO content(id,title,kind,published,video_url,created_at) VALUES(?,?,?,?,?,?)',[(f'scale-{n}',f'Title {n}','series',1,'https://private.example/video',1) for n in range(200)])
   db.executemany('INSERT INTO episodes(id,content_id,season,number,title,video_url) VALUES(?,?,?,?,?,?)',[(f'ep-{n}',f'scale-{n}',1,1,'Episode','https://private.example/episode') for n in range(200)])
  db.close()
  statements=[]
  def traced(*args,**kwargs):
   db=original(*args,**kwargs);db.set_trace_callback(statements.append);return db
  with patch('app.sqlite3.connect',side_effect=traced):response=self.client.get('/api/catalog')
  self.assertEqual(response.status_code,200)
  self.assertEqual(len([q for q in statements if 'FROM episodes' in q]),1)
  self.assertNotIn('private.example',response.text)
  item=next(i for i in response.json['items'] if i['id']=='scale-100')
  self.assertEqual(item['episodes'][0]['id'],'ep-100')
  self.assertEqual(response.headers['Cache-Control'],'no-store')
 def test_lightweight_metadata_matches_initial_metadata(self):
  response=self.client.get('/api/seo?path=/filmes');self.assertEqual(response.status_code,200)
  self.assertEqual(set(response.json),{'head'});self.assertIn('<title data-seo>Filmes | WorkTV</title>',response.json['head'])
  self.assertNotIn('video_url',response.text)
  self.assertEqual(self.client.get('/api/seo?path='+('a'*600)).status_code,400)
if __name__=='__main__':unittest.main()
