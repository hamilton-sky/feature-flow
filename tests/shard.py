"""Run one shard of the unit tests in tests/py, so CI can run them as parallel jobs.

usage: python tests/shard.py <k> <n> [unittest args]

The test files are dealt into n shards by size (largest first, each to the lightest shard so far), so the shards
take about the same time. Every file lands in exactly one shard, and the same files always land in the same shard.
"""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent / "py"


def shards(n):
    files = sorted(HERE.glob("test_*.py"), key=lambda p: (-p.stat().st_size, p.name))
    out = [[] for _ in range(n)]
    weight = [0] * n
    for path in files:
        k = weight.index(min(weight))
        out[k].append(path.stem)
        weight[k] += path.stat().st_size
    return out


def main(argv):
    if len(argv) < 2 or not argv[0].isdigit() or not argv[1].isdigit() or not 1 <= int(argv[0]) <= int(argv[1]):
        print("usage: python tests/shard.py <k> <n>  (1 <= k <= n)", file=sys.stderr)
        return 2
    names = shards(int(argv[1]))[int(argv[0]) - 1]
    print("shard %s of %s: %s" % (argv[0], argv[1], " ".join(names)), flush=True)
    sys.path.insert(0, str(HERE))
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    verbosity = 2 if "-v" in argv[2:] else 1
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
