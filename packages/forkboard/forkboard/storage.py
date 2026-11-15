"""Bounded JSON transactions shared by the browser and agent-side writers."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import tempfile
import time
from contextlib import contextmanager

from . import live
from .graph import BRACKETS, COLOURS, OPS

MAX_STATE = 8 * 1024 * 1024
MAX_BODY = 1024 * 1024
MAX_TEXT = 20000


class Conflict(ValueError):
    """The caller must reload the latest state before trying its operation again."""


def _text(value, name, limit=MAX_TEXT, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise ValueError('%s must be text of 1..%d characters' % (name, limit))
    return value


def _fields(obj, allowed, required=()):
    if not isinstance(obj, dict) or set(obj) - set(allowed) or set(required) - set(obj):
        raise ValueError('unknown or missing fields; expected %s' % ', '.join(allowed))


def graph(value):
    """Validate the editor's graph model before accepting an untrusted proposal."""
    _fields(value, ('dir', 'nodes', 'edges'), ('dir', 'nodes', 'edges'))
    if value['dir'] not in ('LR', 'RL', 'TD', 'TB', 'BT'):
        raise ValueError('invalid graph direction')
    nodes, edges = value['nodes'], value['edges']
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 500 or not isinstance(edges, list) or len(edges) > 1000:
        raise ValueError('graph requires 1..500 nodes and at most 1000 edges')
    ids = set()
    for node in nodes:
        _fields(node, ('id', 'label', 'shape', 'colour'), ('id', 'label'))
        ident = _text(node['id'], 'node id', 100)
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]*', ident) or ident in ids:
            raise ValueError('invalid or duplicate graph node id')
        ids.add(ident)
        _text(node['label'], 'node label', 1000, empty=True)
        if (not isinstance(node.get('shape', 'rect'), str) or node.get('shape', 'rect') not in BRACKETS
                or node.get('colour', '') not in ('',) + tuple(c[0] for c in COLOURS)):
            raise ValueError('invalid graph shape or colour')
    for edge in edges:
        _fields(edge, ('from', 'to', 'label', 'style'), ('from', 'to'))
        if not isinstance(edge['from'], str) or not isinstance(edge['to'], str) or edge['from'] not in ids or edge['to'] not in ids:
            raise ValueError('graph edge references an unknown node')
        _text(edge.get('label', ''), 'edge label', 1000, empty=True)
        if not isinstance(edge.get('style', 'arrow'), str) or edge.get('style', 'arrow') not in OPS:
            raise ValueError('invalid graph edge style')
    return value


def _safe(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('refusing symlink at %s' % path)
    return path


def _validate(st):
    if (not isinstance(st, dict) or not isinstance(st.get('feature'), str)
            or type(st.get('round')) is not int or st['round'] < 0
            or not isinstance(st.get('figures'), dict) or not isinstance(st.get('asks'), list)
            or not isinstance(st.get('picks', {}), dict)):
        raise ValueError('invalid page state; repair or restore state.json before retrying')
    for fig in st['figures'].values():
        if not isinstance(fig, dict) or not isinstance(fig.get('original'), dict) or not isinstance(fig.get('versions'), dict):
            raise ValueError('invalid figure in page state; repair or restore state.json')
        graph(fig['original'])
        for version in fig['versions'].values():
            if not isinstance(version, dict) or 'graph' not in version:
                raise ValueError('invalid saved version in page state; repair or restore state.json')
            graph(version['graph'])
    if any(not isinstance(a, dict) or not isinstance(a.get('text'), str) for a in st['asks']):
        raise ValueError('invalid asks in page state; repair or restore state.json')
    if 'identity' in st:
        _fields(st['identity'], ('id', 'label'), ('id', 'label'))
        _text(st['identity']['id'], 'identity id', 100)
        _text(st['identity']['label'], 'identity label', 200)
    if not isinstance(st.get('_operations', {}), dict):
        raise ValueError('invalid operations in page state; repair or restore state.json')
    return st


def _constant(value):
    raise ValueError('non-finite JSON number: %s' % value)


def _read(path, missing=False):
    path = _safe(path)
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_STATE + 1)
    except FileNotFoundError:
        if missing:
            return None
        raise ValueError('no page state at %s; generate a live page first' % path)
    if len(raw) > MAX_STATE:
        raise ValueError('page state exceeds the 8 MiB limit; archive old work before retrying')
    try:
        return _validate(json.loads(raw, parse_constant=_constant))
    except (ValueError, UnicodeError, TypeError, RecursionError, OverflowError) as e:
        raise ValueError('cannot read page state %s; repair or restore it (file kept intact): %s' % (path, e)) from e


def read(path, missing=False):
    with lock(path):
        return _read(path, missing)


def revision(st):
    return '"' + hashlib.sha256(live.dump(st).encode('utf-8')).hexdigest() + '"'


@contextmanager
def lock(path, timeout=2):
    lockpath = Path(path).with_name(Path(path).name + '.lock')
    deadline = time.monotonic() + timeout
    while True:
        try:
            lockpath.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError('state lock %s is busy; stop all writers and remove it only after confirming none is active to recover' % lockpath)
            time.sleep(0.02)
    try:
        _recover(path)
        yield
    finally:
        lockpath.rmdir()


def replace(path, text):
    """Leave the previous commit readable if writing or replacing is interrupted."""
    path = _safe(path)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=str(path.parent), prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            name = stream.name
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name is not None and os.path.exists(name):
            os.unlink(name)


def _journal(path):
    return Path(path).with_name(Path(path).name + '.publication')


def _recover(path):
    journal = _safe(_journal(path))
    if not journal.exists():
        return
    with journal.open('rb') as stream:
        raw = stream.read(12 * MAX_STATE + 1024)
    if len(raw) >= 12 * MAX_STATE + 1024:
        raise ValueError('publication journal is too large; repair it before continuing')
    try:
        pending = json.loads(raw)
        _fields(pending, ('state', 'page'), ('state', 'page'))
        if not isinstance(pending['state'], str) or not isinstance(pending['page'], str):
            raise ValueError('invalid publication journal')
        if len(pending['state'].encode()) > MAX_STATE or len(pending['page'].encode()) > MAX_STATE:
            raise ValueError('publication exceeds size limit')
        _validate(json.loads(pending['state'], parse_constant=_constant))
    except (ValueError, TypeError, UnicodeError) as e:
        raise ValueError('invalid publication journal; repair or restore it: %s' % e) from e
    _safe(path)
    _safe(Path(path).parent / 'index.html')
    replace(Path(path).parent / 'index.html', pending['page'])
    replace(path, pending['state'])
    journal.unlink()


def publish(path, data, page):
    """Publish a recoverable state/page pair while holding the state lock."""
    path = _safe(path)
    _safe(path.parent / 'index.html')
    if len(page.encode('utf-8')) > MAX_STATE:
        raise ValueError('page exceeds the 8 MiB limit')
    replace(_journal(path), json.dumps({'state': data, 'page': page}, ensure_ascii=False))
    _recover(path)


def transaction(path, mutate, create=False, timeout=2, page=None, prepare=None):
    """Lock, reload, mutate, validate, replace. Callbacks never see a stale snapshot."""
    path = _safe(path)
    with lock(path, timeout):
        before = _read(path, missing=create)
        candidate = before
        prepared_page = None
        if prepare is not None:
            candidate, prepared_page = prepare(before)
        st = _validate(mutate(candidate))
        st.setdefault('identity', {'id': 'local_' + secrets.token_hex(12), 'label': 'You'})
        data = live.dump(st)
        if len(data.encode('utf-8')) > MAX_STATE:
            raise ValueError('page state exceeds the 8 MiB limit; archive old work before retrying')
        if page is not None or prepared_page is not None:
            publish(path, data, page if page is not None else prepared_page)
        elif before is None or not path.exists() or path.read_text(encoding='utf-8') != data:
            replace(path, data)
        return st


def _identity(st, payload):
    if 'by' in payload and payload['by'] != st['identity']['id']:
        raise ValueError('browser identity must match the persistent local reviewer')


def _figure(st, payload):
    number = str(payload.get('figure') or '')
    fig = st['figures'].get(number)
    if not fig:
        raise ValueError('unknown figure; reload the page')
    if 'source' in payload and payload['source'] != fig['source']:
        raise Conflict('figure source changed; keep your edits and reload the page')
    return number, fig


def _position(pos, model):
    if not isinstance(pos, dict) or len(pos) > 500:
        raise ValueError('invalid graph positions')
    ids = {n['id'] for n in model['nodes']}
    for ident, xy in pos.items():
        if ident not in ids or not isinstance(xy, dict) or set(xy) != {'x', 'y'}:
            raise ValueError('invalid node position')
        if any(type(n) not in (int, float) or not math.isfinite(n) or abs(n) > 1000000 for n in xy.values()):
            raise ValueError('node positions must be bounded finite numbers')
    return pos


def change(path, envelope, expected, prepare=None):
    _fields(envelope, ('id', 'change'), ('id', 'change'))
    ident = _text(envelope['id'], 'operation id', 200)
    operation = envelope['change']
    if not isinstance(operation, dict) or set(operation) not in (
            {'version'}, {'ask'}, {'pick'}, {'picks', 'approve', 'ask'}, {'unapprove', 'ask'}):
        raise ValueError('expected version, ask, pick, compound approval or reopen')
    digest = hashlib.sha256(json.dumps(operation, sort_keys=True, allow_nan=False).encode()).hexdigest()

    def apply(st):
        current = revision(st)
        operations = st.setdefault('_operations', {})
        if ident in operations:
            if operations[ident] != digest:
                raise ValueError('operation id was already used for different work')
            return st
        if expected != current:
            raise Conflict('state changed; reload state.json and retry your pending operation')
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        document = st.get('_document') or {}
        steps = document.get('steps') or []
        choices = document.get('choices') or {}
        if any(k in operation for k in ('pick', 'picks', 'approve', 'unapprove')) and document.get('frozen'):
            raise ValueError('accepted settings are frozen; request an approved re-plan')
        def pick(payload, step=None):
            _fields(payload, ('key', 'entry'), ('key', 'entry'))
            key = _text(payload['key'], 'pick key', 200)
            entry = payload['entry']
            _fields(entry, ('by', 'at', 'value'), ('value',))
            _identity(st, entry)
            value = entry['value']
            choice = choices.get(key)
            if choice:
                if choice.get('step') != step:
                    raise ValueError('stepped choices require their atomic approval')
                values = [str(o['value']) for o in choice['options']]
                if choice.get('kind') == 'some':
                    if (not isinstance(value, list) or any(not isinstance(v, str) or v not in values for v in value)
                            or len(set(value)) != len(value) or len(value) > choice.get('max', len(values))):
                        raise ValueError('invalid list choice')
                elif value not in values:
                    raise ValueError('invalid choice value')
            elif '_document' in st or step:
                raise ValueError('unknown choice')
            elif not isinstance(value, (str, bool, int)) or len(str(value)) > 2000:
                raise ValueError('pick value must be bounded text, boolean or integer')
            st.setdefault('picks', {})[key] = {'by': st['identity']['id'], 'at': now, 'value': value}
        if 'ask' in operation and not isinstance(operation['ask'], dict):
            raise ValueError('ask must be an object')
        if 'approve' in operation:
            approval = operation['approve']
            _fields(approval, ('step', 'by', 'at'), ('step',))
            _identity(st, approval)
            step = approval['step']
            if not any(s['name'] == step and s.get('state') == 'current' for s in steps):
                raise ValueError('only the current step can be approved')
            items = operation['picks']
            expected_keys = {k for k, c in choices.items() if c.get('step') == step}
            if (not isinstance(items, list) or not expected_keys or len(items) != len(expected_keys)
                    or any(not isinstance(p, dict) for p in items) or any(not isinstance(p.get('key'), str) for p in items) or {p.get('key') for p in items} != expected_keys):
                raise ValueError('approval must include every choice in this step exactly once')
            if operation['ask'].get('step') != step or operation['ask'].get('approve') is not True:
                raise ValueError('approval requires its step approval ask')
            for item in items:
                pick(item, step)
            st.setdefault('approved', {})[step] = {'by': st['identity']['id'], 'at': now}
        if 'unapprove' in operation:
            names = [s['name'] for s in steps]
            step = operation['ask'].get('step')
            if (step not in names or operation['unapprove'] != names[names.index(step):]
                    or not any(s['name'] == step and (s.get('state') == 'done' or step in st.get('approved', {})) for s in steps)
                    or operation['ask'].get('approve')):
                raise ValueError('reopen must name the completed step and every following step')
            for name in operation['unapprove']:
                st.setdefault('approved', {}).pop(name, None)
        kind = 'ask' if 'ask' in operation else next(iter(operation))
        payload = operation[kind]
        if kind == 'ask':
            _fields(payload, ('by', 'at', 'text', 'figure', 'version', 'step', 'kind', 'source', 'graph', 'about', 'approve'), ('text',))
            _identity(st, payload)
            ask = {'id': ident, 'by': st['identity']['id'], 'at': now, 'text': _text(payload['text'], 'ask text'),
                   'figure': None, 'version': None, 'kind': payload.get('kind') or ('step' if payload.get('step') else 'question')}
            if ask['kind'] not in ('question', 'diagram', 'step'):
                raise ValueError('invalid request kind')
            if 'approve' in payload:
                if 'approve' not in operation or payload['approve'] is not True:
                    raise ValueError('approval asks require an atomic approval')
                ask['approve'] = True
            if payload.get('about'):
                ask['about'] = _text(payload['about'], 'about', 2000)
            if payload.get('step'):
                if not any(s['name'] == payload['step'] for s in steps):
                    raise ValueError('unknown step')
                ask['step'] = _text(payload['step'], 'step', 200)
            if payload.get('figure'):
                number, fig = _figure(st, payload)
                version = payload.get('version')
                if version is not None and version != 'original' and version not in fig['versions']:
                    raise ValueError('unknown requested diagram version')
                if 'graph' in payload and (not isinstance(payload.get('source'), str) or not payload['source']):
                    raise ValueError('diagram snapshot requires a source fingerprint')
                saved = fig['versions'].get(version) if version != 'original' else None
                if saved and saved.get('source', fig['source']) != fig['source']:
                    raise Conflict('requested diagram version source changed; keep your edits and reload')
                model = payload['graph'] if 'graph' in payload else (saved or {}).get('graph') or fig['original']
                ask.update(figure=number, version=version, source=fig['source'], graph=graph(model), title=fig.get('title', ''))
            elif ask['kind'] == 'diagram' or 'graph' in payload or 'source' in payload or payload.get('version'):
                raise ValueError('diagram context requires a figure')
            st['asks'].append(ask)
        elif kind == 'version':
            _fields(payload, ('figure', 'by', 'entry', 'source'), ('figure', 'entry'))
            _identity(st, payload)
            _, fig = _figure(st, payload)
            entry = payload['entry']
            _fields(entry, ('graph', 'pos', 'at', 'via', 'source'), ('graph',))
            if not any(isinstance(item.get('source'), str) and item['source'] for item in (payload, entry)):
                raise ValueError('version requires a source fingerprint')
            if 'source' in entry and entry['source'] != fig['source']:
                raise Conflict('figure source changed; keep your edits and reload')
            model = graph(entry['graph'])
            via = entry.get('via') or ['hand']
            if not isinstance(via, list) or len(via) > 20:
                raise ValueError('invalid diagram provenance')
            for item in via:
                _text(item, 'diagram provenance', 100)
            fig['versions'][st['identity']['id']] = {'graph': model, 'pos': _position(entry.get('pos') or {}, model),
                                                    'at': now, 'via': via, 'source': fig['source']}
        else:
            pick(payload)
        operations[ident] = digest
        return st

    return transaction(path, apply, prepare=prepare)
