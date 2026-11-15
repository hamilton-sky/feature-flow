import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow.pages import brainstorm_page


class PortablePage(unittest.TestCase):
    def test_plan_without_brainstorm_can_launch_and_answer(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            draft = root / '.feature-flow/state/draft/demo'
            (draft / 'tasks').mkdir(parents=True)
            (draft / 'commands.md').write_text('Profile: standard\n')
            (draft / 'tasks/01-test.md').write_text('# Test\n\nStatus: open\nBlocked by: none\n')
            folder = root / 'live'
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(brainstorm_page.git, 'toplevel', return_value=str(root)):
                result = brainstorm_page.main(['demo', '--live', str(folder), '--provider', 'local'], out, err)
            self.assertEqual(result, 0, err.getvalue())
            self.assertTrue((folder / 'state.json').exists())
            self.assertIn('not used', (folder / 'index.html').read_text().lower())
            self.assertFalse((root / 'plans/demo/brainstorm.md').exists())

    def test_plan_picks_and_accepted_freeze_without_brainstorm(self):
        import json
        from feature_flow.pages import studio
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            draft = root / '.feature-flow/state/draft/demo'
            (draft / 'tasks').mkdir(parents=True)
            (draft / 'commands.md').write_text('Profile: standard\n')
            (draft / 'tasks/01-test.md').write_text('# Test\n\nStatus: open\nBlocked by: none\n')
            folder = root / 'live'
            with mock.patch.object(brainstorm_page.git, 'toplevel', return_value=str(root)):
                self.assertEqual(brainstorm_page.main(['demo', '--live', str(folder)], io.StringIO(), io.StringIO()), 0)
                fb = studio.load()
                state = fb.storage.read(folder / 'state.json')
                state['picks'] = {'profile': {'value': 'careful'}, 'full_review': {'value': ['01']}}
                fb.storage.transaction(folder / 'state.json', lambda old: state)
                self.assertEqual(brainstorm_page.main(['demo', '--picks', str(folder)], io.StringIO(), io.StringIO()), 0)
                self.assertIn('careful', (draft / 'commands.md').read_text())
                plan = root / 'plans/demo'
                plan.parent.mkdir(parents=True)
                import shutil
                shutil.copytree(draft, plan)
                before = (plan / 'commands.md').read_text()
                state['picks']['profile']['value'] = 'fast'
                fb.storage.transaction(folder / 'state.json', lambda old: state)
                self.assertEqual(brainstorm_page.main(['demo', '--picks', str(folder)], io.StringIO(), io.StringIO()), 0)
                self.assertEqual((plan / 'commands.md').read_text(), before)
                self.assertEqual(brainstorm_page.main(['demo', '--live', str(folder)], io.StringIO(), io.StringIO()), 0)
                self.assertTrue(fb.storage.read(folder / 'state.json')['_document']['frozen'])
                err = io.StringIO()
                self.assertEqual(brainstorm_page.main(['demo', '--apply', str(folder), '1', 'original'], io.StringIO(), err), 1)
                self.assertIn('no brainstorm source', err.getvalue())

    def test_answer_preserves_latest_state_without_source(self):
        from feature_flow.pages import studio
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'live'
            folder.mkdir()
            fb = studio.load()
            state = fb.live.state({'id': 'demo', 'sections': []})
            state['asks'] = [{'text': 'Why?', 'about': '01 Test', 'step': 'Plan'}]
            import importlib
            importlib.import_module('forkboard.storage')
            fb.storage.transaction(folder / 'state.json', lambda old: state, create=True)
            with mock.patch.object(brainstorm_page.git, 'toplevel', return_value=root):
                self.assertEqual(brainstorm_page.main(['demo', '--answer', str(folder), '1', 'Because'], io.StringIO(), io.StringIO()), 0)
            ask = fb.storage.read(folder / 'state.json')['asks'][0]
            self.assertEqual((ask['answer'], ask['about'], ask['step']), ('Because', '01 Test', 'Plan'))

    def test_subprocess_answer_and_regeneration_share_lock(self):
        import subprocess
        import sys
        from feature_flow.pages import studio
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / 'plans/demo/brainstorm.md'
            source.parent.mkdir(parents=True)
            source.write_text('# Demo\n\n## Idea\n\nA review.\n')
            folder = root / 'live'
            env = dict(os.environ, PYTHONPATH=str(helpers.ROOT))
            cmd = [sys.executable, '-m', 'feature_flow', 'brainstorm-page', 'demo']
            subprocess.run(cmd + ['--live', str(folder)], cwd=root, env=env, check=True, capture_output=True)
            fb = studio.load()
            def add_asks(st):
                st['asks'] = [{'text': 'Question %d' % i} for i in range(8)]
                return st
            fb.storage.transaction(folder / 'state.json', add_asks)
            writers = [subprocess.Popen(cmd + ['--answer', str(folder), str(i), 'Answer %d' % i], cwd=root, env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(1, 9)]
            writers += [subprocess.Popen(cmd + ['--live', str(folder)], cwd=root, env=env,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(3)]
            for proc in writers:
                out, err = proc.communicate(timeout=15)
                self.assertEqual(proc.returncode, 0, (out, err))
            state = fb.storage.read(folder / 'state.json')
            self.assertEqual([a['answer'] for a in state['asks']], ['Answer %d' % i for i in range(1, 9)])

    def test_refresh_tracks_each_phase_with_and_without_brainstorm(self):
        from feature_flow.pages import studio
        for with_brainstorm in (False, True):
            with self.subTest(with_brainstorm=with_brainstorm), tempfile.TemporaryDirectory() as root:
                root = Path(root)
                if with_brainstorm:
                    source = root / '.feature-flow/state/brainstorm-demo.md'
                    source.parent.mkdir(parents=True)
                    source.write_text('# Demo\n\n## Idea\n\nHello.\n')
                draft = root / '.feature-flow/state/draft/demo'
                (draft / 'tasks').mkdir(parents=True)
                (draft / 'commands.md').write_text('Profile: standard\n')
                ticket = draft / 'tasks/01-test.md'
                ticket.write_text('# Test\n\nStatus: open\nBlocked by: none\n')
                folder = root / 'live'
                fb = studio.load()
                import importlib
                importlib.import_module('forkboard.server')
                callbacks = []
                def serve(folder, port, out, refresh, prepare, guard):
                    callbacks.append(refresh)
                with mock.patch.object(brainstorm_page.git, 'toplevel', return_value=str(root)), mock.patch.object(fb.server, 'serve', side_effect=serve):
                    self.assertEqual(brainstorm_page.main(['demo', '--serve', str(folder)], io.StringIO(), io.StringIO()), 0)
                    read = lambda: fb.storage.read(folder / 'state.json')
                    self.assertEqual(read()['phase'], 'draft')
                    import shutil
                    plan = root / 'plans/demo'
                    plan.parent.mkdir(parents=True)
                    shutil.copytree(draft, plan)
                    callbacks[0]()
                    self.assertEqual(read()['phase'], 'build')
                    (plan / 'tasks/01-test.md').write_text('# Test\n\nStatus: resolved\nBlocked by: none\n')
                    callbacks[0]()
                    self.assertEqual(read()['phase'], 'complete')
                    self.assertTrue(read()['_document']['frozen'])
                    self.assertEqual(source.exists() if with_brainstorm else (plan / 'brainstorm.md').exists(), with_brainstorm)

    def test_accepted_plan_is_refreshed_before_http_post_without_poll(self):
        import json
        import shutil
        import threading
        import urllib.error
        import urllib.request
        import importlib
        from feature_flow.pages import studio
        fb = studio.load()
        importlib.import_module('forkboard.server')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / '.feature-flow/state/draft/demo'
            (draft / 'tasks').mkdir(parents=True)
            (draft / 'commands.md').write_text('Profile: standard\n')
            (draft / 'tasks/01-test.md').write_text('# Test\n\nStatus: open\nBlocked by: none\n')
            folder = root / 'live'
            def serve(folder, port, out, refresh, prepare, guard):
                before = fb.storage.read(Path(folder) / 'state.json')
                original_state = (Path(folder) / 'state.json').read_bytes()
                original_page = (Path(folder) / 'index.html').read_bytes()
                plan = root / 'plans/demo'
                plan.parent.mkdir(parents=True)
                shutil.copytree(draft, plan)
                server = fb.server.create(folder, 0, refresh, prepare, guard)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    origin = 'http://127.0.0.1:%d' % server.server_port
                    invalid = json.dumps({'id': 'invalid', 'change': {'ask': {'text': ''}}}).encode()
                    invalid_request = urllib.request.Request(origin + '/api/change', data=invalid, headers={'Origin': origin,
                        'Content-Type': 'application/json', 'If-Match': fb.storage.revision(before)}, method='POST')
                    with self.assertRaises(urllib.error.HTTPError) as bad:
                        urllib.request.urlopen(invalid_request)
                    self.assertIn(bad.exception.code, (400, 412))
                    bad.exception.close()
                    self.assertEqual((Path(folder) / 'state.json').read_bytes(), original_state)
                    self.assertEqual((Path(folder) / 'index.html').read_bytes(), original_page)
                    body = json.dumps({'id': 'late', 'change': {'pick': {'key': 'profile', 'entry': {'value': 'careful'}}}}).encode()
                    request = urllib.request.Request(origin + '/api/change', data=body, headers={'Origin': origin,
                        'Content-Type': 'application/json', 'If-Match': fb.storage.revision(before)}, method='POST')
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(request)
                    self.assertEqual(caught.exception.code, 412)
                    caught.exception.close()
                    self.assertEqual((Path(folder) / 'state.json').read_bytes(), original_state)
                    self.assertEqual((Path(folder) / 'index.html').read_bytes(), original_page)
                    refresh()
                    after = fb.storage.read(Path(folder) / 'state.json')
                    self.assertTrue(after['_document']['frozen'])
                    self.assertNotIn('late', after.get('_operations', {}))
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join()
            with mock.patch.object(brainstorm_page.git, 'toplevel', return_value=str(root)), mock.patch.object(fb.server, 'serve', side_effect=serve):
                self.assertEqual(brainstorm_page.main(['demo', '--serve', str(folder)], io.StringIO(), io.StringIO()), 0)

    def test_plan_accept_and_post_serialize_across_feature_lock(self):
        import importlib
        import json
        import shutil
        import threading
        import urllib.error
        import urllib.request
        from types import SimpleNamespace
        from feature_flow.pages import studio
        from feature_flow.conductor import planning
        fb = studio.load()
        importlib.import_module('forkboard.server')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / '.feature-flow/state/draft/demo'
            (draft / 'tasks').mkdir(parents=True)
            (draft / 'commands.md').write_text('Profile: standard\n')
            (draft / 'tasks/01-test.md').write_text('# Test\n\nStatus: open\nBlocked by: none\n')
            plan = root / 'plans/demo'
            folder = root / 'live'
            copied, release, post_done = threading.Event(), threading.Event(), threading.Event()
            results, errors = [], []
            planner = planning.Planner.__new__(planning.Planner)
            planner.feature, planner.plan, planner.draft = 'demo', plan, draft
            planner.scripts, planner.draft_root, planner.log = 'scripts', draft.parent, lambda *args: None
            def serve(folder, port, out, refresh, prepare, guard):
                before = fb.storage.read(Path(folder) / 'state.json')
                server = fb.server.create(folder, 0, refresh, prepare, guard)
                server_thread = threading.Thread(target=server.serve_forever, daemon=True)
                server_thread.start()
                def accept():
                    try:
                        planner.plan_accept()
                    except Exception as error:
                        errors.append(error)
                def post():
                    origin = 'http://127.0.0.1:%d' % server.server_port
                    body = json.dumps({'id': 'late', 'change': {'pick': {'key': 'profile', 'entry': {'value': 'careful'}}}}).encode()
                    request = urllib.request.Request(origin + '/api/change', data=body, headers={'Origin': origin,
                        'Content-Type': 'application/json', 'If-Match': fb.storage.revision(before)}, method='POST')
                    try:
                        with urllib.request.urlopen(request) as response:
                            results.append(response.status)
                    except urllib.error.HTTPError as error:
                        results.append(error.code)
                        error.close()
                    finally:
                        post_done.set()
                try:
                    check = SimpleNamespace(ok=True, out='OK')
                    with mock.patch.object(planning.git, 'toplevel', return_value=str(root)), \
                            mock.patch.object(planning.checks, 'flow_status', return_value=check), \
                            mock.patch.object(planning, 'shutil', SimpleNamespace(copytree=paused_copy)):
                        accept_thread = threading.Thread(target=accept)
                        accept_thread.start()
                        self.assertTrue(copied.wait(5))
                        post_thread = threading.Thread(target=post)
                        post_thread.start()
                        self.assertFalse(post_done.wait(.15), 'POST passed while acceptance held the feature lock')
                        release.set()
                        accept_thread.join(5)
                        post_thread.join(5)
                    self.assertFalse(errors)
                    self.assertEqual(results, [412])
                    refresh()
                    self.assertTrue(fb.storage.read(Path(folder) / 'state.json')['_document']['frozen'])
                finally:
                    release.set()
                    server.shutdown()
                    server.server_close()
                    server_thread.join()
            # Capture the original before patching the shared shutil module.
            real_copy = shutil.copytree
            def paused_copy(src, dst):
                result = real_copy(src, dst)
                copied.set()
                if not release.wait(5):
                    raise RuntimeError('acceptance was not released')
                return result
            with mock.patch.object(brainstorm_page.git, 'toplevel', return_value=str(root)), mock.patch.object(fb.server, 'serve', side_effect=serve):
                self.assertEqual(brainstorm_page.main(['demo', '--serve', str(folder)], io.StringIO(), io.StringIO()), 0)

    def test_invalid_plan_pick_does_not_write(self):
        from feature_flow.pages import studio
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            draft = root / '.feature-flow/state/draft/demo'
            (draft / 'tasks').mkdir(parents=True)
            commands = draft / 'commands.md'
            commands.write_text('Profile: standard\n')
            (draft / 'tasks/01-test.md').write_text('# Test\n\nStatus: open\nBlocked by: none\n')
            folder = root / 'live'
            with mock.patch.object(brainstorm_page.git, 'toplevel', return_value=str(root)):
                self.assertEqual(brainstorm_page.main(['demo', '--live', str(folder)], io.StringIO(), io.StringIO()), 0)
                fb = studio.load()
                def pick(st):
                    st['picks'] = {'gate': {'value': 'off unsafe'}}
                    return st
                fb.storage.transaction(folder / 'state.json', pick)
                err = io.StringIO()
                self.assertEqual(brainstorm_page.main(['demo', '--picks', str(folder)], io.StringIO(), err), 1)
                self.assertEqual(commands.read_text(), 'Profile: standard\n')
                self.assertIn('gate', err.getvalue())

    def test_picks_wait_for_acceptance_then_leave_both_plans_unchanged(self):
        import shutil
        import threading
        from feature_flow.pages import studio
        from feature_flow.infra import plan_lock
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / '.feature-flow/state/draft/demo'
            (draft / 'tasks').mkdir(parents=True)
            commands = draft / 'commands.md'
            commands.write_text('Profile: standard\n')
            (draft / 'tasks/01-test.md').write_text('# Test\n\nStatus: open\nBlocked by: none\n')
            folder = root / 'live'
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(brainstorm_page.git, 'toplevel', return_value=str(root)):
                self.assertEqual(brainstorm_page.main(['demo', '--live', str(folder)], io.StringIO(), io.StringIO()), 0)
                fb = studio.load()
                def stage(st):
                    st['picks'] = {'profile': {'value': 'careful'}}
                    return st
                fb.storage.transaction(folder / 'state.json', stage)
                done, started, result = threading.Event(), threading.Event(), []
                def apply_picks():
                    started.set()
                    try:
                        result.append(brainstorm_page.main(['demo', '--picks', str(folder)], out, err))
                    finally:
                        done.set()
                plan = root / 'plans/demo'
                with plan_lock.lock(root, 'demo'):
                    worker = threading.Thread(target=apply_picks)
                    worker.start()
                    self.assertTrue(started.wait(2))
                    self.assertFalse(done.wait(.15), 'picks passed while acceptance held the feature lock')
                    plan.parent.mkdir(parents=True)
                    shutil.copytree(draft, plan)
                worker.join(5)
                self.assertTrue(done.is_set())
                self.assertEqual(result, [0], err.getvalue())
                self.assertIn('plan is accepted', out.getvalue())
                self.assertEqual(commands.read_text(), 'Profile: standard\n')
                self.assertEqual((plan / 'commands.md').read_text(), 'Profile: standard\n')
