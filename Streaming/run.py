"""Run with Python 3.11+; local dependencies are supported."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / '.packages'))
from app import create_app
from waitress import serve
import os

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', '8000'))
    print(f'VYRA disponível em http://localhost:{port}', flush=True)
    print('Primeiro acesso administrativo: data/initial-admin.txt', flush=True)
    serve(app, host=os.getenv('HOST', '127.0.0.1'), port=port, threads=8)
