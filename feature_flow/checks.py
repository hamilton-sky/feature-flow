"""The bash scripts the conductor still calls.

Each call lives in one function so plans/interactive-flow-python can swap it for an
in-process call without touching the conductor.
"""

import subprocess
from pathlib import Path


class Result:
    def __init__(self, code, out):
        self.code = code
        self.out = out

    @property
    def ok(self):
        return self.code == 0


def _bash(script, *args):
    result = subprocess.run(["bash", str(script)] + [str(a) for a in args],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    return Result(result.returncode, result.stdout)


def flow_status(scripts, feature, mode):
    """flow-status.sh with --next, --counts or --check. stderr is folded into the output."""
    return _bash(Path(scripts) / "flow-status.sh", feature, mode)


def gate(scripts, feature):
    return _bash(Path(scripts) / "gate.sh", feature)


def floor_guard(scripts, feature, num, base):
    return _bash(Path(scripts) / "floor-guard.sh", feature, num, base)


def smoke(command):
    result = subprocess.run(["bash", "-c", command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True)
    return Result(result.returncode, result.stdout)
