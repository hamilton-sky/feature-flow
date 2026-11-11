"""Run the unit tests in tests/py in shards: one shard (as CI's parallel jobs do), or every shard at once here.

usage: python tests/shard.py <k> <n> [-v]    run shard k of n
       python tests/shard.py all [n] [-v]    run all n shards (default 4) side by side, each in its own process
                                             and its own temp folder; exit 1 when any shard fails

The test files are dealt into n shards by size (largest first, each to the lightest shard so far), so the shards
take about the same time. Every file lands in exactly one shard, and the same files always land in the same shard,
so `all 4` runs exactly the tests CI's four jobs run.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent / "py"
DEFAULT_SHARDS = 4
TICK = 30  # seconds between the "still running" lines of `all`
TAIL = 60


def shards(n):
    files = sorted(HERE.glob("test_*.py"), key=lambda p: (-p.stat().st_size, p.name))
    out = [[] for _ in range(n)]
    weight = [0] * n
    for path in files:
        k = weight.index(min(weight))
        out[k].append(path.stem)
        weight[k] += path.stat().st_size
    return out


def clock(seconds):
    seconds = int(round(seconds))
    return "%dm%02ds" % (seconds // 60, seconds % 60) if seconds >= 60 else "%ds" % seconds


def one(k, n, verbose):
    names = shards(n)[k - 1]
    print("shard %s of %s: %s" % (k, n, " ".join(names)), flush=True)
    sys.path.insert(0, str(HERE))
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(verbosity=2 if verbose else 1).run(suite)
    return 0 if result.wasSuccessful() else 1


def shard_command(k, n, verbose):
    return [sys.executable, str(Path(__file__).resolve()), str(k), str(n)] + (["-v"] if verbose else [])


def every(n, verbose, say=print, tick=TICK, command=shard_command):
    """Start all n shards at once, each in its own process with its own temp folder (TMPDIR, TMP and TEMP), so no
    two shards share a scratch path. Print each shard's result as it ends, with the whole output of a failed one
    (its last TAIL lines unless verbose). command(k, n, verbose) is the argv of shard k. Returns 0 when every shard
    passed, else 1."""
    scratch = Path(tempfile.mkdtemp(prefix="flow-shards-"))
    started = time.monotonic()
    running = {}
    try:
        for k in range(1, n + 1):
            tmp = scratch / ("tmp%d" % k)
            tmp.mkdir()
            env = dict(os.environ, TMPDIR=str(tmp), TMP=str(tmp), TEMP=str(tmp))
            log = open(str(scratch / ("shard%d.log" % k)), "w+b")
            running[k] = (subprocess.Popen(command(k, n, verbose), stdout=log, stderr=subprocess.STDOUT, env=env), log, time.monotonic())
        say("shards: %d started side by side, logs in %s" % (n, scratch))
        failed, last = [], started
        while running:
            time.sleep(0.2)
            for k in sorted(running):
                proc, log, began = running[k]
                if proc.poll() is None:
                    continue
                del running[k]
                log.seek(0)
                text = log.read().decode("utf-8", "replace")
                log.close()
                verdict = "passed" if proc.returncode == 0 else "FAILED"
                say("shard %d of %d %s in %s" % (k, n, verdict, clock(time.monotonic() - began)))
                if proc.returncode != 0:
                    failed.append(k)
                    lines = text.rstrip("\n").split("\n")
                    say("\n".join(lines if verbose else lines[-TAIL:]))
            if running and time.monotonic() - last >= tick:
                last = time.monotonic()
                say("shards: %s running, %s so far" % (", ".join(str(k) for k in sorted(running)),
                                                       clock(last - started)))
        took = clock(time.monotonic() - started)
        if failed:
            say("shards: %s of %d failed (%s) in %s" % (len(failed), n, ", ".join(map(str, failed)), took))
            return 1
        say("shards: all %d passed in %s" % (n, took))
        return 0
    finally:
        for proc, log, _ in running.values():  # only on an interrupt: end what is still running
            proc.kill()
            proc.wait()
            log.close()
        shutil.rmtree(str(scratch), ignore_errors=True)


def main(argv):
    verbose = "-v" in argv
    args = [a for a in argv if a != "-v"]
    if args[:1] == ["all"]:
        if len(args) > 2 or (len(args) == 2 and not (args[1].isdigit() and int(args[1]) >= 1)):
            print("usage: python tests/shard.py all [n]  (n >= 1)", file=sys.stderr)
            return 2
        return every(int(args[1]) if len(args) == 2 else DEFAULT_SHARDS, verbose,
                     say=lambda text: print(text, flush=True))
    if len(args) < 2 or not args[0].isdigit() or not args[1].isdigit() or not 1 <= int(args[0]) <= int(args[1]):
        print("usage: python tests/shard.py <k> <n>  (1 <= k <= n), or python tests/shard.py all [n]",
              file=sys.stderr)
        return 2
    return one(int(args[0]), int(args[1]), verbose)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
