"""A loopback-only page and narrow conditional operation API. No filesystem mapping."""
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import storage


def create(folder, port=0, refresh=None):
    """Build a server; refresh is a trusted no-argument Python callback, never a URL target."""
    folder = Path(folder).resolve()
    if not folder.is_dir() or not (folder / 'index.html').is_file() or (folder / 'index.html').is_symlink():
        raise ValueError('live folder must contain a generated index.html')
    storage.transaction(folder / 'state.json', lambda st: st)
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('port must be a number from 0 to 65535')

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *_):
            pass

        def reply(self, status, body, content='application/json; charset=utf-8', etag=None):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Connection', 'close')
            if etag:
                self.send_header('ETag', etag)
            self.end_headers()
            self.wfile.write(data)
            self.close_connection = True

        def boundary(self, write=False):
            host = '127.0.0.1:%d' % self.server.server_port
            if self.headers.get_all('Host') != [host]:
                self.reply(403, {'error': 'Host must match the listening loopback address'})
                return False
            if write and self.headers.get_all('Origin') != ['http://' + host]:
                self.reply(403, {'error': 'Origin must exactly match the loopback page'})
                return False
            return True

        def do_GET(self):
            if not self.boundary():
                return
            if self.path not in ('/', '/state.json', '/api/page'):
                self.reply(404, {'error': 'only /, /state.json and /api/page are readable'})
                return
            try:
                if self.path == '/':
                    path = folder / 'index.html'
                    if path.is_symlink() or not path.is_file():
                        raise ValueError('page must be a regular file, not a symlink')
                    with path.open('rb') as stream:
                        body = stream.read(storage.MAX_STATE + 1)
                    if len(body) > storage.MAX_STATE:
                        raise ValueError('page exceeds the 8 MiB limit')
                    self.reply(200, body, 'text/html; charset=utf-8')
                else:
                    if self.path == '/api/page' and self.server.refresh is not None:
                        self.server.refresh()
                    st = storage.read(folder / 'state.json')
                    rev = storage.revision(st)
                    if self.path == '/api/page':
                        page = folder / 'index.html'
                        if page.is_symlink():
                            raise ValueError('page must not be a symlink')
                        with page.open('rb') as stream:
                            rendered = stream.read(storage.MAX_STATE + 1)
                        if len(rendered) > storage.MAX_STATE:
                            raise ValueError('page exceeds the 8 MiB limit')
                        body = {'revision': '"' + hashlib.sha256(rendered).hexdigest() + '"',
                                'round': st['round'], 'phase': st.get('phase', 'review')}
                    else:
                        body = st
                    self.reply(200, body, etag=rev)
            except (OSError, ValueError, TypeError) as e:
                self.reply(409, {'error': str(e)})

        def do_POST(self):
            if not self.boundary(write=True):
                return
            if self.path != '/api/change':
                self.reply(404, {'error': 'only POST /api/change is supported'})
                return
            if self.headers.get_all('Content-Type') != ['application/json']:
                self.reply(415, {'error': 'Content-Type must be application/json'})
                return
            expected = self.headers.get_all('If-Match') or []
            if len(expected) != 1 or len(expected[0]) != 66 or not expected[0].startswith('"') or not expected[0].endswith('"'):
                self.reply(428, {'error': 'If-Match must contain the strong ETag from state.json'})
                return
            lengths = self.headers.get_all('Content-Length') or []
            if self.headers.get_all('Transfer-Encoding') or len(lengths) != 1 or len(lengths[0]) > 10 or not lengths[0].isascii() or not lengths[0].isdigit():
                self.reply(400, {'error': 'one bounded Content-Length is required; transfer encoding is unsupported'})
                return
            length = int(lengths[0])
            if not 1 <= length <= storage.MAX_BODY:
                self.reply(413, {'error': 'JSON body must be 1..1048576 bytes'})
                return
            try:
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError('incomplete JSON body')
                envelope = json.loads(raw, parse_constant=storage._constant)
                st = storage.change(folder / 'state.json', envelope, expected[0])
                self.reply(200, st, etag=storage.revision(st))
            except storage.Conflict as e:
                self.reply(412, {'error': str(e)})
            except (OSError, ValueError, TypeError, OverflowError, RecursionError) as e:
                self.reply(400, {'error': str(e)})

    httpd = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    httpd.daemon_threads = True
    httpd.refresh = refresh
    return httpd


def serve(folder, port=0, out=None, refresh=None):
    """Serve until interrupted, printing the actual origin and persisted state location."""
    import sys
    out = out or sys.stdout
    httpd = create(folder, port, refresh)
    try:
        out.write('serving http://127.0.0.1:%d/ state %s\n' % (httpd.server_port, Path(folder).resolve() / 'state.json'))
        out.flush()
        httpd.serve_forever()
    except KeyboardInterrupt:
        return
    finally:
        httpd.server_close()
