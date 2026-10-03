from app import create_app
from waitress import serve
serve(create_app(), host='127.0.0.1', port=8000, threads=8)
