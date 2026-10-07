"""The checks the conductor runs, in process.

Each call lives in one function so plans/interactive-flow-python can swap it for an
in-process call without touching the conductor.
"""

import os
import tempfile
from pathlib import Path

from feature_flow import proc
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


def flow_status(scripts, feature, mode, root=None):
    """The ticket graph reader with --next, --counts or --check, in process. stderr is folded into the output.
    root, when given, stands in for FLOW_DIR for this one call (the planner's draft folder)."""
    out = _Collect()
    saved = os.environ.get("FLOW_DIR")
    if root is not None:
        os.environ["FLOW_DIR"] = str(root)
    try:
        code = status.run([feature, mode], out, out)
    finally:
        if root is not None:
            if saved is None:
                del os.environ["FLOW_DIR"]
            else:
                os.environ["FLOW_DIR"] = saved
    return Result(code, out.text())


def gate(scripts, feature, timeout=None):
    """The gate, run in process. stderr is folded into the output as the subprocess call did.
    timeout is minutes, None for FLOW_GATE_TIMEOUT."""
    chunks = []
    code = gate_module.run(str(feature), chunks.append, chunks.append, timeout)
    out = "".join(chunks).encode("utf-8", "surrogateescape").decode("utf-8", "replace")
    out = out.replace("\r\n", "\n").replace("\r", "\n")
    return Result(code, out)


def floor_guard(scripts, feature, num, base):
    """feature_flow.floorguard in-process; stdout and stderr are folded together in order."""
    chunks = []
    code = floorguard.run([str(feature), str(num), str(base)], chunks.append, chunks.append)
    out = "".join(chunks).encode("utf-8", "surrogateescape").decode("utf-8", "replace")
    return Result(code, out)


def smoke(command, timeout=None):
    """The smoke command. timeout is minutes, 0 or None for none. Result.timed_out is set when it ran out."""
    args, use_shell = gate_module.shell(command)
    with tempfile.TemporaryFile() as log:
        code, timed_out = proc.run(args, use_shell, log, timeout)
        log.seek(0)
        out = log.read().decode("utf-8", "replace").replace("\r\n", "\n")
    result = Result(1 if timed_out else code, out)
    result.timed_out = timed_out
    return result
