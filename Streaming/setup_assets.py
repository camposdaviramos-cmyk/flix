"""Download pinned player code and locally cache showcase photography."""
from pathlib import Path
from urllib.request import urlopen, Request
from concurrent.futures import ThreadPoolExecutor
import sys
from seed import catalog

ROOT = Path(__file__).parent

def download(job):
    url, target = job
    target.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(Request(url, headers={'User-Agent':'VYRA-Development/1.0'}), timeout=45) as response:
        target.write_bytes(response.read())
    print('Saved:', target.name)

if __name__ == '__main__':
    jobs=[('https://media.w3.org/2010/05/sintel/trailer.mp4', ROOT/'static/assets/sintel-trailer.mp4'),('https://raw.githubusercontent.com/video-dev/hls.js/v1.6.13/LICENSE', ROOT/'static/vendor/HLS-LICENSE.txt')]
    if '--media-only' not in sys.argv:
        jobs.append(('https://cdn.jsdelivr.net/npm/hls.js@1.6.13/dist/hls.min.js', ROOT/'static/vendor/hls.min.js'))
        for item in catalog():
            if item['poster'].startswith('https:'):
                jobs.append((item['poster'].replace('w=600','w=800'),ROOT/'static/assets'/f"{item['id']}.jpg"))
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(download,jobs))
