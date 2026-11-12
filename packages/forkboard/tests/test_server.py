"""Actual loopback HTTP boundary, stale browsers and restart behavior."""
import http.client
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

import helpers
from forkboard import live, server, storage


def announced(proc, timeout=8):
    """Bounded pipe reading also works on Windows, where select only accepts sockets."""
    lines = []
    reader = threading.Thread(target=lambda: lines.append(proc.stdout.readline()), daemon=True)
    reader.start()
    reader.join(timeout)
    if reader.is_alive():
        proc.kill()
        reader.join(5)
        raise AssertionError('server or writer did not announce readiness')
    return lines[0]


class HTTP(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.path = self.folder / 'state.json'
        storage.transaction(self.path, lambda old: live.state(helpers.fixture('sketch'), old), create=True)
        (self.folder / 'index.html').write_text('<h1>Review</h1>')
        (self.folder / 'secret.md').write_text('secret')
        self.httpd = server.create(self.folder)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)
        self.origin = 'http://127.0.0.1:%d' % self.httpd.server_port

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()

    def request(self, path='/state.json', method='GET', body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
        try:
            conn.request(method, path, body, headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def post(self, envelope, revision, **headers):
        return self.request('/api/change', 'POST', json.dumps(envelope), dict({'Content-Type': 'application/json',
                            'Origin': self.origin, 'If-Match': revision}, **headers))

    def test_two_browsers_stale_answer_and_retry(self):
        status, headers, body = self.request()
        self.assertEqual(status, 200)
        st = json.loads(body)
        rev = headers['ETag']
        self.assertTrue(rev.startswith('"') and rev.endswith('"'))
        question = {'id': 'q1', 'change': {'ask': {'text': 'Why?', 'by': st['identity']['id']}}}
        status, headers, body = self.post(question, rev)
        self.assertEqual(status, 200, body)
        storage.transaction(self.path, lambda old: live.answer(old, 1, 'Yes'))
        save = {'id': 'p1', 'change': {'pick': {'key': 'profile', 'entry': {'value': 'standard'}}}}
        before = self.path.read_bytes()
        self.assertEqual(self.post(save, rev)[0], 412)
        self.assertEqual(self.path.read_bytes(), before)
        _, headers, _ = self.request()
        status, _, body = self.post(save, headers['ETag'])
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)['asks'][0]['answer'], 'Yes')
        self.assertEqual(self.post(question, rev)[0], 200)
        self.assertEqual(len(storage.read(self.path)['asks']), 1)
        self.assertEqual(self.request('/')[2], b'<h1>Review</h1>')
        status, _, body = self.request('/api/page')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['round'], 1)

    def test_host_origin_routes_methods_and_hostile_operations_do_not_mutate(self):
        _, headers, body = self.request()
        rev = headers['ETag']
        before = self.path.read_bytes()
        for path in ['/secret.md', '/index.html', '/../secret.md', '/%2e%2e/secret.md', '/state.json?x=1', '/api/approve']:
            self.assertGreaterEqual(self.request(path)[0], 400, path)
        self.assertEqual(self.request(headers={'Host': 'evil.example'})[0], 403)
        for origin in ['null', 'http://evil.example', self.origin + '/', '']:
            self.assertEqual(self.post({'id':'x','change':{'ask':{'text':'bad'}}}, rev, Origin=origin)[0], 403)
        for method in ['PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD', 'TRACE']:
            self.assertGreaterEqual(self.request('/api/change', method)[0], 400)
        invalid = [ {'id':'x','change':{'answer': {'text':'fake'}}},
                    {'id':'x','change':{'ask':{'text':'bad','answer':'fake'}}},
                    {'id':'x','change':{'ask':{'text':'x'*20001}}},
                    {'id':'x','change':{'pick':{'key':'x','entry':{'value':'x','by':'agent'}}}},
                    {'id':'x','change':{'version':{'figure':'1','source':'fake','entry':{'graph':{}}}}},
                    {'id':'x','change':{'round':9}}, {'id':'x','change':{},'unexpected':True} ]
        for envelope in invalid:
            self.assertGreaterEqual(self.post(envelope, rev)[0], 400, envelope)
        for data, extra in [('not json', {}), ('{}', {'Content-Type':'text/plain'}), ('{}', {'Content-Length':'999999999'}),
                            ('{}', {'Transfer-Encoding':'chunked'}), ('{}', {'If-Match':'*'})]:
            hdr = {'Origin': self.origin, 'If-Match':rev, 'Content-Type':'application/json'}
            hdr.update(extra)
            self.assertGreaterEqual(self.request('/api/change','POST',data,hdr)[0], 400)
        self.assertEqual(self.path.read_bytes(), before)

    def test_symlink_and_corrupt_state_fail_closed(self):
        (self.folder / 'index.html').unlink()
        (self.folder / 'index.html').symlink_to(self.folder / 'secret.md')
        self.assertGreaterEqual(self.request('/')[0], 400)
        self.path.write_text('{corrupt')
        self.assertGreaterEqual(self.request()[0], 400)
        self.assertEqual(self.path.read_text(), '{corrupt')

    def test_trusted_refresh_callback_has_no_request_arguments(self):
        calls = []
        self.httpd.refresh = lambda: calls.append(True)
        self.assertEqual(self.request('/api/page')[0], 200)
        self.assertEqual(calls, [True])
        self.assertGreaterEqual(self.request('/api/page?callback=evil')[0], 400)
        self.assertEqual(calls, [True])

    def test_cli_server_prints_url_restarts_and_rejects_busy_port(self):
        env = dict(os.environ, PYTHONPATH=str(helpers.PACKAGE), PYTHONUNBUFFERED='1')
        def start(*extra):
            proc = subprocess.Popen([sys.executable, '-m', 'forkboard', 'serve', str(self.folder), *extra], env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.addCleanup(lambda: proc.poll() is None and proc.kill())
            return proc
        for _ in range(2):
            proc = start('--port', '0')
            line = announced(proc)
            self.assertIn('http://127.0.0.1:', line)
            self.assertIn(str(self.path), line)
            proc.terminate()
            proc.communicate(timeout=5)
            self.assertEqual(storage.read(self.path)['round'], 1)
        proc = start('--port', str(self.httpd.server_port))
        _, err = proc.communicate(timeout=5)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('cannot serve', err)


class AgentRaces(unittest.TestCase):
    setUp = HTTP.setUp
    close = HTTP.close
    request = HTTP.request
    post = HTTP.post

    def test_http_save_waits_for_agent_then_rejects_stale_context(self):
        st = storage.read(self.path)
        storage.change(self.path, {'id': 'request', 'change': {'ask': {'text': 'why', 'figure': '1'}}}, storage.revision(st))
        code = """import json,sys,time
from pathlib import Path
from forkboard import storage,live
path=Path(sys.argv[1]); mode=sys.argv[2]
def update(st):
 print('locked',flush=True)
 while not path.with_name('release').exists(): time.sleep(.01)
 if mode=='answer': return live.answer(st,1,'Concurrent answer')
 doc=json.loads(sys.argv[3]); doc['sections'][0]['markdown']=doc['sections'][0]['markdown'].replace('Tasks table','Changed source')
 return live.state(doc,st)
storage.transaction(path,update)
"""
        for mode in ['answer', 'regenerate']:
            _, headers, raw = self.request()
            old = json.loads(raw)
            fig = old['figures']['1']
            envelope = {'id': mode, 'change': {'version': {'figure':'1','source':fig['source'],'entry':{'graph':fig['original']}}}}
            proc = subprocess.Popen([sys.executable, '-c', code, str(self.path), mode, json.dumps(helpers.fixture('sketch'))],
                                    env=dict(os.environ, PYTHONPATH=str(helpers.PACKAGE)), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(announced(proc).strip(), 'locked')
                responses = []
                worker = threading.Thread(target=lambda: responses.append(self.post(envelope, headers['ETag'])))
                worker.start()
                (self.folder / 'release').touch()
                _, err = proc.communicate(timeout=5)
                self.assertEqual(proc.returncode, 0, err)
                worker.join(5)
                self.assertFalse(worker.is_alive())
                self.assertEqual(responses[0][0], 412)
                current = storage.read(self.path)
                self.assertEqual(current['asks'][0]['answer'], 'Concurrent answer')
                if mode == 'answer':
                    self.assertEqual(self.post(envelope, storage.revision(current))[0], 200)
                else:
                    self.assertEqual(current['round'], 2)
                    self.assertEqual(self.post(envelope, storage.revision(current))[0], 412)
                    self.assertEqual(current['asks'][0]['source'], old['asks'][0]['source'])
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()
                (self.folder / 'release').unlink(missing_ok=True)
