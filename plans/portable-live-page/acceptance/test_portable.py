"""Independent black-box acceptance tests for spec.md's CLI and HTTP interfaces."""
import concurrent.futures
import http.client
import json
import os
from pathlib import Path
import queue
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'packages/forkboard'
FIXTURES = PACKAGE / 'tests/fixtures'


class Portable(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.live = self.dir / 'live'
        self.doc = self.dir / 'doc.json'
        shutil.copyfile(FIXTURES / 'steps.json', self.doc)
        self.env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT), str(PACKAGE)]))

    def cli(self, *args, module='forkboard', cwd=None):
        return subprocess.run(['python3', '-m', module, *map(str, args)], cwd=cwd or ROOT,
                              env=self.env, capture_output=True, text=True, timeout=30)

    def render(self, provider='local', label=None):
        args = ['live', self.doc, self.live, '--provider', provider]
        if label is not None:
            args += ['--agent-label', label]
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, 'Spec renderer provider entry point: ' + result.stderr)

    def serve(self, port=0, module='forkboard', cwd=None):
        args = ['serve', str(self.live), '--port', str(port)] if module == 'forkboard' else [
            'brainstorm-page', 'sample', '--serve', str(self.live), '--port', str(port)]
        process = subprocess.Popen(['python3', '-u', '-m', module, *args], cwd=cwd or ROOT,
                                   env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True)
        def stop():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
            process.stdout.close()
        self.addCleanup(stop)
        lines = queue.Queue()
        def read():
            for line in process.stdout:
                lines.put(line)
        threading.Thread(target=read, daemon=True).start()
        output, deadline = '', time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                output += lines.get(timeout=.1)
            except queue.Empty:
                if process.poll() is not None:
                    break
            match = re.search(r'http://127\.0\.0\.1:\d+/?', output)
            if match and str(self.live) in output:
                self.url = match.group().rstrip('/')
                self.assertIn(str(self.live), output, 'Startup must print state folder')
                return process
        self.fail('Spec serve entry point must print loopback URL and state folder: ' + output)

    def request(self, method='GET', path='/state.json', body=None, headers=None):
        u = urlsplit(self.url)
        connection = http.client.HTTPConnection(u.hostname, u.port, timeout=8)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def state(self):
        status, headers, body = self.request()
        self.assertEqual(status, 200)
        revision = next((v for k, v in headers.items() if k.lower() == 'etag'), '')
        self.assertRegex(revision, r'^"[^"\s]+"$', 'Strong ETag required')
        return json.loads(body), revision

    def change(self, payload, revision):
        return self.request('POST', '/api/change', json.dumps(payload), {
            'Origin': self.url, 'Content-Type': 'application/json', 'If-Match': revision})

    def browser(self, mode):
        result = subprocess.run(['node', str(Path(__file__).with_name('browser.cjs')),
                                 self.url, mode, str(self.live), str(ROOT)], env=self.env,
                                text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lines = [line for line in result.stdout.splitlines() if line.startswith('PAYLOAD ')]
        return json.loads(lines[-1][8:]) if lines else None

    # Claude still obtains artifact, user and optional sample capabilities, publishes with its existing SHA precondition, respects read-only and capability-denied behavior, and supports native diagram generation.
    def test_claude_compatibility_and_explicit_provider(self):
        self.render('claude')
        result = subprocess.run(['npm', '--prefix', str(PACKAGE / 'tests/browser'), 'test'],
                                env=self.env, text=True, capture_output=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Claude', (self.live / 'index.html').read_text())

    # A local page works without `window.claude`, saves a diagram version and layout, compares it with the original, persists across a backend restart, and displays the configured agent label (Codex by default locally; Claude by default natively).
    def test_local_diagram_version_layout_compare_restart_and_label(self):
        self.render(); server = self.serve()
        self.browser('save')
        before, _ = self.state()
        versions = before['figures']['1']['versions']
        self.assertTrue(versions)
        version = next(iter(versions.values()))
        self.assertTrue(version['pos'])
        self.assertIn('Acceptance node', json.dumps(version['graph']))
        server.terminate(); server.wait(timeout=5)
        self.serve()
        self.assertEqual(self.state()[0], before)
        self.browser('saved')
        self.render(label='Review agent')
        self.browser('label')

    # A stale revision never overwrites a newer save, answer or regenerated round. After a conflict the latest state is fetched and the pending operation is replayed once against it; a second conflict or unavailable storage visibly retains pending work for retry. An ask is not duplicated by retries.
    def test_stale_revision_idempotency_and_conflict_retry(self):
        self.render(); self.serve()
        _, old = self.state()
        payload = self.browser('ask')
        current, revision = self.state()
        # Retransmitting an already committed operation is idempotent even with
        # its original revision; a distinct stale operation must be rejected.
        stale = {'id': 'distinct-stale-operation', 'change': payload['change']}
        self.assertEqual(self.change(stale, old)[0], 412)
        self.assertEqual(self.state()[0], current)
        self.assertEqual(self.change(payload, old)[0], 200)
        self.assertEqual(len(self.state()[0]['asks']), 1)
        self.browser('conflict')
        self.assertEqual(sum(a['text'] == 'Conflict question' for a in self.state()[0]['asks']), 1)

    # Questions, completed-step Change requests and local diagram-change requests appear in the agent's existing asks output, including the diagram and source context where relevant. They remain queued across disconnect/restart until explicitly answered.
    def test_questions_step_and_diagram_requests_survive_restart(self):
        self.render(); server = self.serve()
        self.browser('requests')
        before, _ = self.state()
        self.assertGreaterEqual(len(before['asks']), 3)
        self.assertTrue(any(a.get('step') for a in before['asks']))
        self.assertTrue(any(a.get('figure') and a.get('kind') == 'diagram' for a in before['asks']))
        server.terminate(); server.wait(timeout=5); self.serve()
        result = self.cli('asks', self.live)
        self.assertEqual(result.returncode, 0, result.stderr)
        for text in ['Acceptance question', 'Change', 'Acceptance diagram request']:
            self.assertIn(text, result.stdout)
        self.assertIn(before['figures']['1']['title'], result.stdout)
        self.assertRegex(result.stdout, r'flowchart|Admin|Export endpoint')
        self.assertEqual(self.state()[0]['asks'], before['asks'])

    # Text replies and optional validated diagram proposals become visible after refresh; a proposed diagram is previewed without silently replacing the reviewer's unsaved graph. Save as my version is explicit, and applying to Markdown still checks its source fingerprint.
    def test_answers_and_validated_graph_proposals_are_explicit(self):
        self.render(); self.serve(); self.browser('ask')
        result = self.cli('answer', self.live, '1', 'Acceptance answer')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.browser('answer')
        graph = self.state()[0]['figures']['1']['original']
        proposal = self.dir / 'graph.json'; proposal.write_text(json.dumps(graph))
        # A question is not a diagram request and must not acquire a graph proposal.
        result = self.cli('answer-graph', self.live, '1', proposal)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state()[0]['asks'][0]['answer'], 'Acceptance answer')
        self.browser('requests')
        asks = self.state()[0]['asks']
        number = next(i for i, a in enumerate(asks, 1) if a.get('figure') and a.get('kind') == 'diagram')
        result = self.cli('answer-graph', self.live, number, proposal)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.browser('proposal')
        before = self.state()[0]
        proposal.write_text(json.dumps({'nodes': [], 'edges': 'invalid'}))
        result = self.cli('answer-graph', self.live, number, proposal)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state()[0], before)
        repo, _ = self.feature()
        self.live = self.dir / 'apply-live'
        rendered = self.cli('brainstorm-page', 'sample', '--live', self.live, '--provider', 'local', module='feature_flow', cwd=repo)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        self.serve()
        self.browser('save')
        state, _ = self.state()
        version = next(iter(state['figures']['1']['versions']))
        source = repo / '.feature-flow/state/brainstorm-sample.md'
        source.write_text(source.read_text().replace('A --> B', 'A --> C'))
        unchanged = source.read_bytes()
        apply = self.cli('brainstorm-page', 'sample', '--apply', self.live, '1', version, module='feature_flow', cwd=repo)
        self.assertNotEqual(apply.returncode, 0)
        self.assertRegex(apply.stderr.lower(), r'changed|fingerprint|stale|source')
        self.assertEqual(source.read_bytes(), unchanged)

    # Setup and draft Plan picks are persisted as proposals, applied only through existing agent-side validation. A browser action cannot approve a plan, disable a gate, invoke shell/build commands, or modify accepted commands or tickets. Re-plan remains the way to change approved build settings.
    def test_picks_are_proposals_and_authoritative_writes_are_rejected(self):
        self.render(); self.serve(); self.browser('pick')
        result = self.cli('picks', self.live)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('security', json.loads(result.stdout)['lens'])
        before, revision = self.state()
        for change in [{'answer': {'text': 'forged'}}, {'round': 99}, {'approve': True},
                       {'command': 'touch owned'}]:
            with self.subTest(change=change):
                status, _, body = self.change({'id': 'forbidden', 'change': change}, revision)
                self.assertTrue(400 <= status < 500, body)
                self.assertEqual(self.state()[0], before)
        self.assertFalse((self.live / 'owned').exists())
        repo, folder = self.feature()
        self.live = self.dir / 'feature-live'
        snapshot = {p.relative_to(folder): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
        self.serve(module='feature_flow', cwd=repo)
        self.browser('plan-pick')
        self.assertEqual({p.relative_to(folder): p.read_bytes() for p in folder.rglob('*') if p.is_file()}, snapshot)
        applied = self.cli('brainstorm-page', 'sample', '--picks', self.live, module='feature_flow', cwd=repo)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertIn('careful', (folder / 'commands.md').read_text())
        self.assertFalse((repo / 'plans/sample').exists(), 'Applying proposals cannot approve a plan')

    def feature(self, brainstorm=True, draft=True):
        repo = self.dir / 'repo'; repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        folder = repo / ('.feature-flow/state/draft/sample' if draft else 'plans/sample')
        (folder / 'tasks').mkdir(parents=True)
        (folder / 'spec.md').write_text('# Example\n\n## Goal\n\nAcceptance feature.\n')
        (folder / 'map.md').write_text('# Map\n\n## Destination\n\nAcceptance feature.\n')
        (folder / 'commands.md').write_text('Test: `true`\nProfile: `standard`\nLanes: `auto`\n')
        (folder / 'tasks/01-example.md').write_text('# 01: Acceptance ticket\n\nStatus: open\nDepends on: none\nLevel: 1\nTouches: app.py\n\n## Ask\n\nAcceptance task.\n')
        if brainstorm:
            state = repo / '.feature-flow/state'; state.mkdir(parents=True, exist_ok=True)
            (state / 'brainstorm-sample.md').write_text('# Brainstorm: sample\n\nType: standard\n\n## Idea\n\nExample.\n\n## Options\n\n### A. First\n\n```mermaid\nflowchart LR\nA --> B\n```\n\n## Chosen\n\nA. First\n')
        return repo, folder

    # Brainstorm shows existing Setup and Options controls and later Plan/Build steps. Draft plans show tickets, dependencies, build controls and checks. Accepted plans show frozen choices and active ticket statuses; completion shows all tickets done.
    def test_same_page_advances_draft_active_and_completed_build(self):
        repo, folder = self.feature()
        self.serve(module='feature_flow', cwd=repo)
        self.browser('draft')
        accepted = repo / 'plans/sample'; accepted.parent.mkdir(); shutil.move(str(folder), accepted)
        ticket = accepted / 'tasks/01-example.md'
        ticket.write_text(ticket.read_text().replace('Status: open', 'Status: claimed'))
        self.assertEqual(self.request(path='/api/page')[0], 200)
        self.browser('building')
        ticket.write_text(ticket.read_text().replace('Status: claimed', 'Status: resolved'))
        self.assertEqual(self.request(path='/api/page')[0], 200)
        self.browser('done')

    # A feature with draft or accepted tasks but no brainstorm.md can launch, render and process questions/plan picks. Setup/Options explicitly say they were not used; no synthetic brainstorm file is written. Brainstorm diagram apply reports unavailable when there is no source.
    def test_plan_without_brainstorm_launches_and_processes_state(self):
        repo, folder = self.feature(brainstorm=False)
        self.serve(module='feature_flow', cwd=repo)
        self.browser('no-brainstorm'); self.browser('ask')
        result = self.cli('brainstorm-page', 'sample', '--asks', self.live, module='feature_flow', cwd=repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Acceptance question', result.stdout)
        self.browser('plan-pick')
        result = self.cli('brainstorm-page', 'sample', '--picks', self.live, module='feature_flow', cwd=repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('careful', (folder / 'commands.md').read_text())
        result = self.cli('brainstorm-page', 'sample', '--apply', self.live, '1', 'original', module='feature_flow', cwd=repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr.lower(), r'no .*brainstorm|unavailable|no .*source')
        self.assertFalse(list(repo.rglob('brainstorm*.md')))

    # The local page notices answers, page regeneration and external ticket-status changes within five seconds while connected. No agent wakeup or manual server restart is needed to read status. A disconnected page shows its status and reconnects without losing edits.
    def test_polling_answers_and_disconnect_preserve_edits(self):
        self.render(); self.serve(); self.browser('polling')

    # Refresh does not discard dirty diagram edits, typed questions, pending saves or selected versions. Content changes that cannot merge safely show an update-available control and preserve work before replacement; a changed figure source blocks blind replay.
    def test_refresh_preserves_dirty_graph_question_and_version(self):
        self.render(); self.serve(); self.browser('refresh')

    # Local startup prints the actual loopback URL and state folder, supports port 0 for tests and an explicit port, and fails clearly on a busy port or absent feature instead of exposing another interface.
    def test_loopback_startup_explicit_busy_port_and_absent_feature(self):
        self.render()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        self.serve(port)
        self.assertEqual(urlsplit(self.url).port, port)
        busy = self.cli('serve', self.live, '--port', port)
        self.assertNotEqual(busy.returncode, 0)
        self.assertRegex(busy.stderr.lower(), r'busy|in use|bind')
        repo = self.dir / 'missing'; repo.mkdir(); subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        absent = self.cli('brainstorm-page', 'absent', '--serve', self.dir / 'absent-live', module='feature_flow', cwd=repo)
        self.assertNotEqual(absent.returncode, 0)
        self.assertNotIn('http://', absent.stdout)
        self.assertRegex(absent.stderr.lower(), r'absent|not found|no .*feature|no .*plan')

    # Only the page and narrow API resources are served. Traversal, symlinks escaping the live folder, foreign Host/Origin, unsupported methods, oversized or malformed bodies and invalid operations fail without any state/file mutation. No directory listing, arbitrary file read/write or command execution route exists.
    def test_http_security_rejects_unsafe_requests_without_mutation(self):
        self.render(); self.serve()
        self.assertEqual(self.request(path='/')[0], 200)
        status, _, metadata = self.request(path='/api/page')
        self.assertEqual(status, 200)
        metadata = json.loads(metadata)
        self.assertTrue({'revision', 'round', 'phase'} <= set(metadata))
        self.assertTrue(metadata['revision'])
        self.assertIsInstance(metadata['phase'], str)
        secret = self.dir / 'secret'; secret.write_text('PRIVATE ACCEPTANCE SECRET')
        (self.live / 'escape').symlink_to(secret)
        (self.live / 'private.txt').write_text('PRIVATE ACCEPTANCE SECRET')
        before = {p.name: p.read_bytes() for p in self.live.iterdir() if p.is_file()}
        _, revision = self.state()
        cases = [('GET', '/private.txt', None, {}), ('GET', '/escape', None, {}),
                 ('GET', '/../secret', None, {}), ('GET', '/%2e%2e/secret', None, {}),
                 ('GET', '/state.json', None, {'Host': 'attacker.invalid'}),
                 ('POST', '/api/change', '{}', {'Origin': 'http://attacker.invalid'}),
                 ('DELETE', '/state.json', None, {}), ('PUT', '/state.json', '{}', {}),
                 ('POST', '/api/change', '{', {'Origin': self.url, 'If-Match': revision}),
                 ('POST', '/api/change', '[]', {'Origin': self.url, 'If-Match': revision}),
                 ('POST', '/api/change', json.dumps({'id': 'extra', 'change': {}, 'state': {}}), {'Origin': self.url, 'If-Match': revision}),
                 ('POST', '/api/run', '{}', {'Origin': self.url, 'If-Match': revision}),
                 ('POST', '/api/change', '{}', {'Origin': self.url}),
                 ('POST', '/api/change', '', {'Origin': self.url, 'If-Match': revision, 'Content-Length': str(2 ** 10000)}),
                 ('POST', '/api/change', json.dumps({'id': 'bad', 'change': {'unknown': True}}), {'Origin': self.url, 'If-Match': revision})]
        for method, path, body, headers in cases:
            with self.subTest(method=method, path=path, headers=headers):
                try:
                    status, _, data = self.request(method, path, body, headers)
                except (BrokenPipeError, ConnectionResetError):
                    # Early rejection of an oversized body may close the connection before it is sent.
                    self.assertGreater(len(body or ''), 1024 * 1024)
                else:
                    # BaseHTTPRequestHandler rejects unsupported methods with 501.
                    self.assertTrue(400 <= status < 500 or (method in ('DELETE', 'PUT') and status == 501), (status, data[:200]))
                    self.assertNotIn(b'PRIVATE ACCEPTANCE SECRET', data)
                self.assertEqual({p.name: p.read_bytes() for p in self.live.iterdir() if p.is_file()}, before)

    # Concurrent agent answers, local browser operations and page regeneration use the same cross-process transaction mechanism. Existing valid state is preserved, corrupted state produces an actionable error without being reset, and interrupted writes leave the prior committed state readable.
    def test_concurrent_writers_and_corrupt_state_are_not_reset(self):
        self.render(); self.serve(); self.browser('ask')
        def answer(i):
            return self.cli('answer', self.live, '1', 'Concurrent answer %d' % i)
        def regenerate(i):
            return self.cli('live', self.doc, self.live, '--provider', 'local')
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda i: answer(i) if i % 2 else regenerate(i), range(16)))
        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        state, _ = self.state()
        self.assertEqual(len(state['asks']), 1)
        self.assertIn('Concurrent answer', state['asks'][0]['answer'])
        self.assertEqual(state['round'], 9)
        writer = subprocess.Popen(['python3', '-m', 'forkboard', 'live', str(self.doc),
                                   str(self.live), '--provider', 'local'], env=self.env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        writer.terminate(); writer.wait(timeout=5)
        committed = json.loads((self.live / 'state.json').read_text())
        self.assertEqual(committed['asks'], state['asks'])
        self.assertEqual(committed['figures'], state['figures'])
        broken = b'{"feature": "never reset"'
        (self.live / 'state.json').write_bytes(broken)
        result = regenerate(0)
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr.lower(), r'corrupt|invalid|recover|json')
        self.assertEqual((self.live / 'state.json').read_bytes(), broken)
