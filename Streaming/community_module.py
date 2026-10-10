"""Persistent community module switch, shared by HTTP and push workers."""
from flask import Response, jsonify

API_ROOTS = ('/api/community', '/api/social', '/api/jump', '/api/hub', '/api/music', '/api/wallet', '/api/admin/community', '/api/admin/music', '/api/admin/spaces', '/api/admin/verifications', '/api/admin/economy')
PAGE_ROOTS = ('/comunidade', '/sala', '/carteira')

def matches(path, roots):
    return any(path == root or path.startswith(root + '/') for root in roots)

def enabled(db):
    row = db.execute("SELECT value FROM settings WHERE key='community_enabled'").fetchone()
    return row is None or row['value'] == 'true'

def unavailable(api=True):
    if api:
        response = jsonify(error='A comunidade está desativada.', code='community_disabled')
    else:
        response = Response('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Comunidade indisponível | WorkTV</title><style>body{background:#081323;color:#fff;font:18px system-ui;padding:10vh 8vw}a{color:#64c7ff}</style><main><h1>Comunidade indisponível</h1><p>O módulo comunidade está desativado no momento.</p><a href="/">Voltar à WorkTV</a></main></html>', mimetype='text/html')
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    response.status_code = 503
    response.headers['X-WorkTV-Module'] = 'community-disabled'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['CDN-Cache-Control'] = 'no-store'
    return response
