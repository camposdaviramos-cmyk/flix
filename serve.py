from app import create_app
from waitress import serve

# Only Nginx on loopback may supply the one sanitized forwarding hop.
serve(create_app(), host='127.0.0.1', port=8000, threads=8,
      trusted_proxy='127.0.0.1', trusted_proxy_count=1,
      trusted_proxy_headers={'x-forwarded-for', 'x-forwarded-proto'})
