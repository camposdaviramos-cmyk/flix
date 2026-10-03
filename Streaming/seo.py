"""Server-rendered search and social metadata from the published catalog."""
import json
import re
from html import escape
from urllib.parse import quote, urljoin, urlparse
from xml.etree.ElementTree import Element, SubElement, tostring
from flask import Response

PAGES = {'': 'Filmes, séries e TV ao vivo', 'planos': 'Planos', 'catalogo': 'Catálogo', 'filmes': 'Filmes', 'series': 'Séries', 'tv': 'TV ao vivo', 'termos': 'Termos de uso', 'privacidade': 'Privacidade'}

def content_path(item):
    return '/titulo/' + quote(item['id'], safe='')

def absolute(base, value):
    url = urljoin(base + '/', value or '/static/assets/hero.png')
    return url if urlparse(url).scheme in ('https', 'http') else base + '/static/assets/hero.png'

def metadata(db, setting, path):
    base = setting('public_url', 'https://flix.devspacey.com').rstrip('/')
    brand = setting('brand', 'Flix')
    items = [dict(row) for row in db.execute('SELECT * FROM content WHERE published=1 ORDER BY created_at DESC,id DESC')]
    item = next((i for i in items if path == content_path(i).lstrip('/')), None)
    public = path in PAGES or item is not None
    title = f"{item['title']} | {brand}" if item else f"{PAGES.get(path, 'Área da conta')} | {brand}"
    if item:
        description = item['description'] or f"Conheça {item['title']} na {brand}."
    else:
        kind = {'filmes': 'movie', 'series': 'series', 'tv': 'channel'}.get(path)
        selected = [i for i in items if not kind or i['kind'] == kind]
        names = ', '.join(i['title'] for i in selected[:3])
        description = f"Descubra filmes, séries e TV ao vivo na {brand}." + (f" No catálogo: {names}." if names and path in ('', 'catalogo', 'filmes', 'series', 'tv') else '')
    if path=='comunidade' or path.startswith('comunidade/'):
        title = f'Comunidade | {brand}'
        description = 'Compartilhe filmes, séries e músicas, encontre amigos e participe de sessões juntos.'
    if path=='historico':
        title=f'Assistidos recentemente | {brand}'
        description='Seus últimos filmes, séries e canais no Flix.'
    if re.fullmatch(r'sala/[A-Za-z0-9_-]{12}',path):
        title = f'Convite FlixJump | {brand}'
        description = 'Assista junto com seus amigos. Entre na conta e aguarde a aprovação do anfitrião.'
    description = re.sub(r'\s+', ' ', description).strip()[:200]
    url = base + ('/' + path if path else '/')
    image = absolute(base, (item.get('backdrop') or item.get('poster')) if item else None)
    schema = {'@context': 'https://schema.org', '@type': 'WebSite', 'name': brand, 'url': base + '/', 'inLanguage': 'pt-BR'}
    if item:
        schema.update({'@type': {'movie': 'Movie', 'series': 'TVSeries', 'channel': 'CreativeWork'}.get(item['kind'], 'CreativeWork'), 'name': item['title'], 'url': url, 'description': description, 'image': image, 'genre': item['genre']})
    elif path in ('catalogo', 'filmes', 'series', 'tv'):
        schema = {'@context': 'https://schema.org', '@type': 'ItemList', 'name': title, 'itemListElement': [{'@type': 'ListItem', 'position': n, 'name': i['title'], 'url': base + content_path(i)} for n, i in enumerate(selected, 1)]}
    return dict(title=title, description=description, url=url, image=image, brand=brand, public=public, schema=schema, item=item, items=items, base=base)

def head(meta):
    esc = lambda v: escape(str(v), quote=True)
    tags = [f'<title data-seo>{esc(meta["title"])}</title>', f'<link data-seo rel="canonical" href="{esc(meta["url"])}">']
    values = {'description': meta['description'], 'robots': 'index,follow,max-image-preview:large' if meta['public'] else 'noindex,nofollow', 'twitter:card': 'summary_large_image', 'twitter:title': meta['title'], 'twitter:description': meta['description'], 'twitter:image': meta['image'], 'twitter:image:alt': meta['title']}
    for name, value in values.items():
        tags.append(f'<meta data-seo name="{name}" content="{esc(value)}">')
    for name, value in {'og:type': 'website', 'og:locale': 'pt_BR', 'og:site_name': meta['brand'], 'og:title': meta['title'], 'og:description': meta['description'], 'og:url': meta['url'], 'og:image': meta['image'], 'og:image:alt': meta['title']}.items():
        tags.append(f'<meta data-seo property="{name}" content="{esc(value)}">')
    data = json.dumps(meta['schema'], ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    tags.append(f'<script data-seo type="application/ld+json">{data}</script>')
    return '\n'.join(tags)

def fallback(meta):
    esc = lambda v: escape(str(v), quote=True)
    item = meta['item']
    items = [item] if item else meta['items'] if meta['public'] else []
    kind = {'/filmes': 'movie', '/series': 'series', '/tv': 'channel'}.get(urlparse(meta['url']).path)
    if kind:
        items = [i for i in items if i['kind'] == kind]
    body = f'<main id="main" class="page container"><h1>{esc(meta["title"])}</h1><p>{esc(meta["description"])}</p>'
    for i in items:
        body += f'<article><h2><a href="{esc(content_path(i))}">{esc(i["title"])}</a></h2><p>{esc(i["description"])}</p></article>'
    return body + '</main>'

def sitemap(db, setting):
    base = setting('public_url', 'https://flix.devspacey.com').rstrip('/')
    root = Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    paths = ['/' + p for p in PAGES]
    paths += [content_path(dict(i)) for i in db.execute('SELECT id FROM content WHERE published=1 ORDER BY id')]
    for path in paths:
        SubElement(SubElement(root, 'url'), 'loc').text = base + path
    return Response(tostring(root, encoding='utf-8', xml_declaration=True), content_type='application/xml; charset=utf-8', headers={'Cache-Control': 'no-cache'})
