"""Serialize managed plan acceptance with live-page changes for one feature."""
from contextlib import contextmanager
import hashlib
from pathlib import Path
import time


@contextmanager
def lock(top, feature, timeout=10):
    folder = Path(top) / '.feature-flow' / 'state'
    folder.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(feature.encode('utf-8')).hexdigest()[:24]
    path = folder / ('plan-accept-' + key + '.lock')
    deadline = time.monotonic() + timeout
    while True:
        try:
            path.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError('plan acceptance lock %s is busy; remove it only after confirming no writer is active' % path)
            time.sleep(.02)
    try:
        yield
    finally:
        path.rmdir()
