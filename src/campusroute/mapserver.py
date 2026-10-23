import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import urlsplit


class MapServer:
    def __init__(self, routes):
        assets = files('campusroute').joinpath('web')
        self.update_routes(routes)
        resources = {}

        def collect(directory, prefix=''):
            for child in directory.iterdir():
                name = prefix + child.name
                if child.is_dir():
                    collect(child, name + '/')
                else:
                    resources['/' + name] = child

        collect(assets)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urlsplit(self.path).path
                if path == '/routes.json':
                    body, content_type = owner.payload, 'application/json; charset=utf-8'
                else:
                    path = '/index.html' if path == '/' else path
                    if path not in resources:
                        self.send_error(404)
                        return
                    body = resources[path].read_bytes()
                    content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
                self.send_header(
                    'Content-Security-Policy',
                    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data: https://tile.openstreetmap.org; "
                    "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
                )
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                return

        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.http.server_port}/'

    def update_routes(self, routes):
        self.payload = json.dumps(
            {'type': 'FeatureCollection', 'features': [route.feature() for route in routes]},
            ensure_ascii=False,
        ).encode('utf-8')

    def close(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError('本地地图服务未能退出。')
