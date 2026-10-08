"""Honor one sanitized forwarding hop, only when the WSGI peer is loopback.
Production Waitress also validates the Nginx hop before constructing WSGI environ.
"""
from werkzeug.middleware.proxy_fix import ProxyFix

class LocalProxyHeaders:
    def __init__(self, app):
        self.app = app
        self.forwarded = ProxyFix(app, x_for=1, x_proto=1)

    def __call__(self, environ, start_response):
        if environ.get('REMOTE_ADDR') in ('127.0.0.1', '::1'):
            return self.forwarded(environ, start_response)
        return self.app(environ, start_response)
