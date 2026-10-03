import http.client
import ipaddress
import re
import socket
import ssl
from urllib.parse import urlparse, urljoin

def valid_url(value, optional=False):
    if not value and optional:
        return ''
    value = str(value).strip()
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or len(value) > 4096:
        raise ValueError('Informe uma URL HTTP ou HTTPS válida.')
    return value

def fetch_playlist(url):
    """Resolve and pin public IPs, including each redirect, preventing SSRF/rebinding."""
    for _ in range(4):
        url = valid_url(url)
        parsed = urlparse(url)
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        if port not in (80, 443, 8080, 8443):
            raise ValueError('A importação por URL aceita portas 80, 443, 8080 e 8443. Para outras portas, envie o arquivo.')
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        ips = [a[4][0] for a in addresses]
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise ValueError('A lista deve estar em um endereço público.')
        sock = socket.create_connection((ips[0], port), timeout=12)
        if parsed.scheme == 'https':
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parsed.hostname)
        conn = http.client.HTTPConnection(parsed.hostname, port, timeout=12)
        conn.sock = sock
        try:
            conn.request('GET', parsed.path + ('?' + parsed.query if parsed.query else ''), headers={'User-Agent': 'VYRA/1.0', 'Accept': 'audio/x-mpegurl, application/vnd.apple.mpegurl, text/plain'})
            result = conn.getresponse()
            if result.status in (301, 302, 303, 307, 308):
                url = urljoin(url, result.getheader('Location', ''))
                continue
            if result.status != 200:
                raise ValueError('Não foi possível baixar a lista. Envie o arquivo ou verifique a URL.')
            data = result.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError('A lista excede o limite de 2 MB.')
            return data.decode('utf-8-sig', errors='replace'), url
        finally:
            conn.close()
    raise ValueError('A URL excedeu o limite de redirecionamentos.')

def parse_playlist(text, base_url=''):
    if len(text.encode('utf-8')) > 2_000_000:
        raise ValueError('A lista excede o limite de 2 MB.')
    if '#EXT-X-' in text:
        raise ValueError('Este arquivo é um stream HLS. Cadastre sua URL diretamente em Adicionar canal.')
    channels, meta, skipped = [], {}, 0
    for line in text.splitlines():
        line = line.strip().lstrip('\ufeff')
        if not line:
            continue
        if line.startswith('#EXTINF:'):
            attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', line))
            meta = {'title': line.rsplit(',', 1)[-1].strip() if ',' in line else attrs.get('tvg-name', 'Canal'), 'genre': attrs.get('group-title', 'TV ao vivo'), 'poster': attrs.get('tvg-logo', '')}
        elif not line.startswith('#'):
            try:
                stream = valid_url(urljoin(base_url, line) if base_url else line)
                logo = valid_url(meta.get('poster', ''), optional=True)
                channels.append(dict(title=meta.get('title', f'Canal {len(channels)+1}')[:160], genre=meta.get('genre', 'TV ao vivo')[:80], poster=logo, video_url=stream))
            except ValueError:
                skipped += 1
            meta = {}
        if len(channels) >= 1000:
            raise ValueError('Importe no máximo 999 canais por vez.')
    if not channels:
        raise ValueError('Nenhum canal HTTP/HTTPS encontrado nesta lista.')
    return channels, skipped
