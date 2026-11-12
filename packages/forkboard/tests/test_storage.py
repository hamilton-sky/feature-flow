"""Managed state transactions and persisted operation contracts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import helpers
from forkboard import live, storage


class Transactions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'state.json'
        self.doc = helpers.fixture('sketch')
        storage.transaction(self.path, lambda old: live.state(self.doc, old), create=True)

    def test_legacy_identity_round_and_retry_survive_regeneration(self):
        st = storage.read(self.path)
        rev = storage.revision(st)
        envelope = {'id': 'question-1', 'change': {'ask': {'text': 'Why?', 'figure': '1'}}}
        result = storage.change(self.path, envelope, rev)
        self.assertEqual(len(result['asks']), 1)
        self.assertEqual(result['asks'][0]['id'], 'question-1')
        self.assertEqual(result['asks'][0]['source'], st['figures']['1']['source'])
        self.assertEqual(result['asks'][0]['graph'], st['figures']['1']['original'])
        storage.transaction(self.path, lambda old: live.answer(old, 1, 'Because.'))
        storage.transaction(self.path, lambda old: live.state(self.doc, old))
        again = storage.change(self.path, envelope, rev)
        self.assertEqual(len(again['asks']), 1)
        self.assertEqual(again['asks'][0]['answer'], 'Because.')
        self.assertEqual(again['identity'], result['identity'])
        self.assertEqual(again['round'], 2)
        with self.assertRaises(storage.Conflict):
            storage.change(self.path, {'id': 'q2', 'change': {'ask': {'text': 'stale'}}}, rev)
        with self.assertRaises(ValueError):
            storage.change(self.path, {'id': 'question-1', 'change': {'ask': {'text': 'different'}}}, storage.revision(again))

    def test_corruption_and_interrupted_replace_preserve_committed_bytes(self):
        before = self.path.read_bytes()
        with patch.object(storage.os, 'replace', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                storage.transaction(self.path, lambda old: dict(old, round=99))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(list(self.path.parent.glob('*.tmp')))
        for raw in ('{broken', '[]', '{"asks": "invalid"}'):
            self.path.write_text(raw)
            with self.assertRaisesRegex(ValueError, 'state|repair|restore'):
                storage.transaction(self.path, lambda old: live.state(self.doc, old), create=True)
            self.assertEqual(self.path.read_text(), raw)

    def test_lock_contention_is_bounded_and_never_removes_ambiguous_lock(self):
        lock = self.path.with_name('state.json.lock')
        lock.mkdir()
        with self.assertRaisesRegex(ValueError, 'lock.*recover|lock.*remove'):
            storage.transaction(self.path, lambda old: old, timeout=0.05)
        self.assertTrue(lock.is_dir())
        lock.rmdir()
        self.assertEqual(storage.read(self.path)['round'], 1)

    def test_subprocess_writers_serialize_and_preserve_answers_and_regeneration(self):
        code = '''import sys,time,json
from pathlib import Path
from forkboard import storage,live
p=Path(sys.argv[1]); mode=sys.argv[2]
def update(st):
 time.sleep(.02)
 if mode=='answer': return live.answer(st,1,'agent reply')
 if mode=='regen': return live.state(json.loads(sys.argv[3]),st)
 st['picks'][mode]={'value':mode}; return st
storage.transaction(p,update)
'''
        storage.change(self.path, {'id': 'q', 'change': {'ask': {'text': 'help'}}}, storage.revision(storage.read(self.path)))
        env = dict(os.environ, PYTHONPATH=str(helpers.PACKAGE))
        processes = [subprocess.Popen([sys.executable, '-c', code, str(self.path), mode, json.dumps(self.doc)], env=env,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE) for mode in ['answer', 'regen', 'save1', 'save2']]
        for proc in processes:
            _, err = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 0, err.decode())
        st = storage.read(self.path)
        self.assertEqual(st['asks'][0]['answer'], 'agent reply')
        self.assertEqual(st['round'], 2)
        self.assertEqual(set(st['picks']), {'save1', 'save2'})

    def test_graph_proposal_uses_request_snapshot_and_never_replaces_versions(self):
        st = storage.read(self.path)
        graph = st['figures']['1']['original']
        st = storage.change(self.path, {'id': 'diagram', 'change': {'ask': {'kind': 'diagram', 'figure': '1', 'text': 'Change it', 'source': st['figures']['1']['source'], 'graph': graph}}}, storage.revision(st))
        source = st['asks'][0]['source']
        storage.transaction(self.path, lambda old: live.state(self.doc, old))
        st = storage.transaction(self.path, lambda old: live.answer_graph(old, 1, graph))
        self.assertEqual(st['asks'][0]['result'], graph)
        self.assertEqual(st['asks'][0]['source'], source)
        self.assertEqual(st['figures']['1']['versions'], {})
        self.assertIn('their version', live.asks(dict(st, asks=[dict(st['asks'][0], answer='')])) )
        with self.assertRaises(ValueError):
            storage.transaction(self.path, lambda old: live.answer_graph(old, 1, {'nodes': []}))


class Validation(unittest.TestCase):
    setUp = Transactions.setUp

    def test_version_preserves_source_and_rejects_unsafe_graphs_and_positions(self):
        st = storage.read(self.path)
        figure = st['figures']['1']
        change = {'version': {'figure': '1', 'source': figure['source'], 'entry': {
            'graph': figure['original'], 'pos': {figure['original']['nodes'][0]['id']: {'x': 1, 'y': 2}}, 'via': ['hand']}}}
        saved = storage.change(self.path, {'id': 'version1', 'change': change}, storage.revision(st))
        version, source = live.version(saved, '1', saved['identity']['id'])
        self.assertEqual(source, figure['source'])
        self.assertEqual(version, figure['original'])
        altered = helpers.fixture('sketch')
        altered['sections'][0]['markdown'] = altered['sections'][0]['markdown'].replace('Tasks table', 'New source')
        again = storage.transaction(self.path, lambda old: live.state(altered, old))
        self.assertNotEqual(again['figures']['1']['source'], source)
        self.assertEqual(live.version(again, '1', again['identity']['id'])[1], source)
        before = self.path.read_bytes()
        with self.assertRaises(storage.Conflict):
            storage.change(self.path, {'id': 'version2', 'change': change}, storage.revision(again))
        for invalid in [dict(figure['original'], nodes=[]), dict(figure['original'], nodes=[{'id':'x','label':'x','shape':{}}]),
                        dict(figure['original'], edges=[{'from':'missing','to':'missing'}]),
                        dict(figure['original'], nodes=[{'id':'x','label':'x'}]*501)]:
            with self.assertRaises(ValueError):
                storage.graph(invalid)
        self.assertEqual(self.path.read_bytes(), before)

    def test_version_requires_explicit_matching_source_even_with_fresh_revision(self):
        original = storage.read(self.path)['figures']['1']
        altered = helpers.fixture('sketch')
        altered['sections'][0]['markdown'] = altered['sections'][0]['markdown'].replace('Tasks table', 'New source')
        current = storage.transaction(self.path, lambda old: live.state(altered, old))
        source = current['figures']['1']['source']
        before = self.path.read_bytes()
        for index, fields in enumerate(({}, {'source': None}, {'source': ''}, {'source': 12},
                                        {'source': original['source']})):
            with self.subTest(fields=fields):
                payload = dict(figure='1', entry={'graph': original['original']}, **fields)
                with self.assertRaises(ValueError):
                    storage.change(self.path, {'id': 'unsafe-%d' % index, 'change': {'version': payload}}, storage.revision(current))
                self.assertEqual(self.path.read_bytes(), before)
        for index, payload in enumerate((
                {'figure': '1', 'source': source, 'entry': {'graph': original['original']}},
                {'figure': '1', 'entry': {'graph': original['original'], 'source': source}},
                {'figure': '1', 'source': source, 'entry': {'graph': original['original'], 'source': source}})):
            current = storage.change(self.path, {'id': 'safe-%d' % index, 'change': {'version': payload}}, storage.revision(current))
            self.assertEqual(live.version(current, '1', current['identity']['id'])[1], source)
        for payload in (
                {'figure': '1', 'source': source, 'entry': {'graph': original['original'], 'source': original['source']}},
                {'figure': '1', 'source': original['source'], 'entry': {'graph': original['original'], 'source': source}}):
            before = self.path.read_bytes()
            with self.assertRaises(storage.Conflict):
                storage.change(self.path, {'id': 'mismatch', 'change': {'version': payload}}, storage.revision(current))
            self.assertEqual(self.path.read_bytes(), before)

    def test_ask_graph_requires_matching_source_and_rejects_stale_saved_versions(self):
        original = storage.read(self.path)['figures']['1']
        storage.transaction(self.path, lambda old: dict(old, figures=dict(old['figures'], **{
            '1': dict(old['figures']['1'], versions={'saved': {'graph': original['original'], 'source': original['source']}})})))
        altered = helpers.fixture('sketch')
        altered['sections'][0]['markdown'] = altered['sections'][0]['markdown'].replace('Tasks table', 'New source')
        current = storage.transaction(self.path, lambda old: live.state(altered, old))
        source = current['figures']['1']['source']
        before = self.path.read_bytes()
        payloads = [dict(figure='1', text='Change', graph=original['original'], **fields)
                    for fields in ({}, {'source': None}, {'source': ''}, {'source': 12}, {'source': original['source']})]
        payloads += [dict(figure='1', text='Change saved', version='saved', **fields)
                     for fields in ({}, {'source': source})]
        for index, payload in enumerate(payloads):
            self.path.write_bytes(before)
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    storage.change(self.path, {'id': 'unsafe-ask-%d' % index, 'change': {'ask': payload}}, storage.revision(current))
                self.assertEqual(self.path.read_bytes(), before)
        current = storage.change(self.path, {'id': 'safe-ask', 'change': {'ask': {
            'figure': '1', 'text': 'Change current', 'source': source, 'graph': current['figures']['1']['original']}}}, storage.revision(current))
        self.assertEqual(current['asks'][0]['source'], source)
        self.assertEqual(current['asks'][0]['graph'], current['figures']['1']['original'])

    def test_process_death_before_replace_retains_previous_commit_and_lock(self):
        before = self.path.read_bytes()
        code = """import os,sys
from pathlib import Path
from forkboard import storage
storage.os.replace=lambda *args: os._exit(42)
storage.transaction(Path(sys.argv[1]), lambda old: dict(old, round=200))
"""
        result = subprocess.run([sys.executable, '-c', code, str(self.path)],
                                env=dict(os.environ, PYTHONPATH=str(helpers.PACKAGE)), timeout=5)
        self.assertEqual(result.returncode, 42)
        self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'lock'):
            storage.transaction(self.path, lambda old: old, timeout=.03)
        self.path.with_name('state.json.lock').rmdir()  # the writer is confirmed dead
        self.assertEqual(storage.transaction(self.path, lambda old: old)['round'], 1)


class Approvals(unittest.TestCase):
    setUp = Transactions.setUp

    def stepped(self):
        return storage.transaction(self.path, lambda old: live.state(helpers.fixture('steps'), old))

    def approval(self):
        return {'picks': [{'key': 'lens', 'entry': {'value': ['ux', 'security']}}],
                'approve': {'step': 'Team'}, 'ask': {'step': 'Team', 'approve': True, 'text': 'Approved Team'}}

    def test_atomic_approval_reopen_identity_and_retry(self):
        st = self.stepped()
        env = {'id': 'approve', 'change': self.approval()}
        st = storage.change(self.path, env, storage.revision(st))
        self.assertEqual(st['picks']['lens']['value'], ['ux', 'security'])
        self.assertEqual(st['approved']['Team']['by'], st['identity']['id'])
        self.assertTrue(st['asks'][-1]['approve'])
        self.assertNotEqual(st['asks'][-1]['at'], 'forged')
        again = storage.change(self.path, env, 'stale')
        self.assertEqual(len(again['asks']), 1)
        st = storage.change(self.path, {'id': 'reopen', 'change': {'unapprove': ['Style', 'Team', 'Options', 'Plan', 'Build'],
              'ask': {'step': 'Style', 'text': 'Change Style'}}}, storage.revision(st))
        self.assertEqual(st['approved'], {})
        self.assertEqual(st['asks'][-1]['step'], 'Style')

    def test_invalid_compounds_and_frozen_controls_never_mutate(self):
        st = self.stepped()
        bad = self.approval(); bad['picks'][0]['entry']['value'] = ['unknown']
        for change in (bad, {'pick': {'key': 'lens', 'entry': {'value': ['ux']}}},
                       {'approve': {'step': 'Build'}}, {'unapprove': ['Style'], 'ask': {'step': 'Style', 'text': 'partial'}}):
            before = self.path.read_bytes()
            with self.assertRaises(ValueError):
                storage.change(self.path, {'id': 'bad', 'change': change}, storage.revision(st))
            self.assertEqual(self.path.read_bytes(), before)
        doc = helpers.fixture('steps'); doc['phase'] = 'accepted'
        st = storage.transaction(self.path, lambda old: live.state(doc, old))
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            storage.change(self.path, {'id': 'frozen', 'change': self.approval()}, storage.revision(st))
        self.assertEqual(self.path.read_bytes(), before)

    def test_about_context_is_retained(self):
        st = storage.read(self.path)
        st = storage.change(self.path, {'id': 'about', 'change': {'ask': {'text': 'Why?', 'about': '02 CSV writer'}}}, storage.revision(st))
        self.assertEqual(st['asks'][0]['about'], '02 CSV writer')
