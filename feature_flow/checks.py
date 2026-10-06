"""The checks the conductor runs: the bash scripts it still calls, and the ported ones in process.

Each call lives in one function so plans/interactive-flow-python can swap it for an
in-process call without touching the conductor.
"""

import subprocess
from pathlib import Path

from feature_flow import status
from feature_flow import gate as gate_module
from feature_flow import floorguard


class Result:
    def __init__(self, code, out):
        self.code = code
        self.out = out

    @property
    def ok(self):
        return self.code == 0


class _Collect:
    """stdout and stderr of an in-process port, folded together in the order they were written."""

    def __init__(self):
        self.parts = []

    def write(self, text):
        self.parts.append(text)

    def text(self):
        return "".join(self.parts)


def _bash(script, *args):
    result = subprocess.run(["bash", str(script)] + [str(a) for a in args],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    return Result(result.returncode, result.stdout)


def flow_status(scripts, feature, mode):
    """The ticket graph reader with --next, --counts or --check, in process. stderr is folded into the output."""
    out = _Collect()
    code = status.run([feature, mode], out, out)
    return Result(code, out.text())


def gate(scripts, feature):
    """The gate, run in process. stderr is folded into the output as the subprocess call did."""
    chunks = []
    code = gate_module.run(str(feature), chunks.append, chunks.append)
    out = b"".join(chunks).decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    return Result(code, out)


def floor_guard(scripts, feature, num, base):
    """feature_flow.floorguard in-process; stdout and stderr are folded together in order."""
    chunks = []
    code = floorguard.run([str(feature), str(num), str(base)], chunks.append, chunks.append)
    out = "".join(chunks).encode("utf-8", "surrogateescape").decode("utf-8", "replace")
    return Result(code, out)


def smoke(command):
    result = subprocess.run(["bash", "-c", command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True)
    return Result(result.returncode, result.stdout)
