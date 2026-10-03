import sys, tempfile, sqlite3, unittest, json
from pathlib import Path
from html.parser import HTMLParser
from xml.etree import ElementTree
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
class HeadParser(HTMLParser):
    def __init__(self): super().__init__(); self.metas={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='meta': self.metas[a.get('property',a.get('name'))]=a.get('content')
class SeoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=create_app(self.tmp.name,testing=True);self.c=self.app.test_client();self.db=sqlite3.connect(Path(self.tmp.name)/'vyra.sqlite3')
        self.db.execute("INSERT OR REPLACE INTO settings VALUES('public_url','https://flix.devspacey.com')");self.db.commit()
    def tearDown(self): self.db.close();self.tmp.cleanup()
    def test_metadata_and_social_image(self):
        r=self.c.get('/'); p=HeadParser();p.feed(r.text)
        self.assertEqual(p.metas['og:url'],'https://flix.devspacey.com/');self.assertTrue(p.metas['og:image'].startswith('https://'));self.assertEqual(p.metas['twitter:card'],'summary_large_image');self.assertIn('application/ld+json',r.text);self.assertIn('/titulo/',r.text)
    def test_publication_updates_without_rebuild(self):
        self.db.execute("INSERT INTO content(id,title,kind,description,poster,published,created_at) VALUES(?,?,?,?,?,?,?)",('seo-test','Novo filme <especial>','movie','Sinopse & detalhes','/static/assets/hero.png',0,9999999999));self.db.commit()
        self.assertNotIn('/titulo/seo-test',self.c.get('/sitemap.xml').text);self.assertEqual(self.c.get('/titulo/seo-test').status_code,404)
        self.db.execute("UPDATE content SET published=1 WHERE id='seo-test'");self.db.commit()
        self.assertIn('/titulo/seo-test',self.c.get('/sitemap.xml').text);r=self.c.get('/titulo/seo-test');self.assertEqual(r.status_code,200);self.assertIn('Novo filme &lt;especial&gt;',r.text);self.assertIn('Novo filme &lt;especial&gt;',self.c.get('/').text)
        self.db.execute("DELETE FROM content WHERE id='seo-test'");self.db.commit();self.assertEqual(self.c.get('/titulo/seo-test').status_code,404)
    def test_sitemap_and_private_routes(self):
        xml=ElementTree.fromstring(self.c.get('/sitemap.xml').data);urls=[n.text for n in xml.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        self.assertTrue(urls);self.assertNotIn('https://flix.devspacey.com/admin',urls);self.assertIn('Sitemap: https://flix.devspacey.com/sitemap.xml',self.c.get('/robots.txt').text)
        self.assertEqual(self.c.get('/admin').headers['X-Robots-Tag'],'noindex, nofollow');self.assertEqual(self.c.get('/does-not-exist').status_code,404)
if __name__=='__main__': unittest.main()
