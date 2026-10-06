"""The gate: a port of the bash gate in scripts/.

usage: python3 scripts/gate.py <feature>
runs the Build, Test and Lint commands from plans/<feature>/commands.md in that order and
stops at the first one that fails. empty values and placeholders in angle brackets are skipped.
the commands run from the current directory and must exit non zero on failure.
exit 0 everything passed or nothing to run, 1 a command failed, 2 usage error.

The file is read and the output written as bytes, so the text matches the bash version byte for
byte (awk keeps a trailing carriage return, and tail prints a command's output unchanged).
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

KEYS = ("Build", "Test", "Lint")
TAIL = 40


def command(path, key):
    """The first `<key>:` line of commands.md, as the awk line in the bash gate reads it, or b""."""
    key = key.encode()
    try:
        data = Path(path).read_bytes()
    except OSError:  # awk prints its own error to stderr and the value is empty
        return b""
    for line in data.split(b"\n"):
        if line.startswith(key + b":"):
            value = re.sub(b"^" + re.escape(key) + b":[ \t]*", b"", line, count=1)
            return value.replace(b"`", b"")
    return b""


def tail(data, n=TAIL):
    """The last n lines of data, as tail -n prints them (a last line without a newline counts)."""
    if not data:
        return b""
    if data.endswith(b"\n"):
        return b"\n".join(data[:-1].split(b"\n")[-n:]) + b"\n"
    return b"\n".join(data.split(b"\n")[-n:])


def run(feature, out, err):
    """Run the gate for feature. out and err take bytes. Returns the exit code."""
    if not feature:
        # the bash gate's usage line, word for word (parity); ticket 07 switches it to gate.py
        err(b"usage: bash scripts/gate.sh <feature>\n")
        return 2
    name = os.fsencode(feature)
    path = Path(os.environ.get("FLOW_DIR") or "plans") / feature / "commands.md"
    if not path.is_file():
        out(b"gate: no commands.md for " + name + b", nothing to run\n")
        return 0
    ran = 0
    for key in KEYS:
        cmd = command(path, key)
        if cmd == b"" or cmd.startswith(b"<"):
            continue
        ran += 1
        out(b"gate: " + key.encode() + b": " + cmd + b"\n")
        with tempfile.TemporaryFile() as log:
            code = subprocess.call(["bash", "-c", os.fsdecode(cmd)], stdout=log, stderr=subprocess.STDOUT)
            if code != 0:
                log.seek(0)
                out(b"gate: " + key.encode() + b" failed. the last lines of its output:\n")
                out(tail(log.read()))
                return 1
    if ran > 0:
        out(b"gate: %d command(s) passed\n" % ran)
    else:
        out(b"gate: no commands defined, nothing to run\n")
    return 0


def _writer(stream):
    def write(data):
        stream.buffer.write(data)
        stream.buffer.flush()
    return write


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    sys.stdout.flush()
    sys.stderr.flush()
    return run(argv[0] if argv else "", _writer(sys.stdout), _writer(sys.stderr))
