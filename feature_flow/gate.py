"""The gate.

usage: python3 scripts/gate.py <feature>
runs the Build, Test and Lint commands from plans/<feature>/commands.md in that order and
stops at the first one that fails. empty values and placeholders in angle brackets are skipped.
the commands run from the current directory and must exit non zero on failure.
exit 0 everything passed or nothing to run, 1 a command failed, 2 usage error.

Text is str (UTF-8 with errors="surrogateescape", so any byte comes back out unchanged).
"""

import os
import sys
import tempfile
from pathlib import Path

from feature_flow import proc

KEYS = ("Build", "Test", "Lint")
TAIL = 40
DEFAULT_TIMEOUT = 30


def shell(cmd):
    """How to run a command from commands.md: bash -c on Linux and macOS, the system shell (cmd.exe)
    on Windows, where `bash` on PATH may be the Windows Subsystem for Linux stub and git-bash is not
    a requirement. Returns (args, use_shell) for subprocess."""
    if sys.platform == "win32":
        return cmd, True
    return ["bash", "-c", cmd], False


def command(path, key):
    """The value of the first `<key>:` line of commands.md, without backticks, or ""."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return ""
    for line in text.split("\n"):
        if line.startswith(key + ":"):
            return line[len(key) + 1:].lstrip(" \t").rstrip("\r").replace("`", "")
    return ""


def tail(text, n=TAIL):
    """The last n lines of text (a last line without a newline counts)."""
    if not text:
        return ""
    if text.endswith("\n"):
        return "\n".join(text[:-1].split("\n")[-n:]) + "\n"
    return "\n".join(text.split("\n")[-n:])


def timeout_minutes():
    """FLOW_GATE_TIMEOUT in minutes (default 30, 0 for none). Raises ValueError naming the variable."""
    value = os.environ.get("FLOW_GATE_TIMEOUT", "")
    try:
        return int(value) if value.strip() else DEFAULT_TIMEOUT
    except ValueError:
        raise ValueError("FLOW_GATE_TIMEOUT must be a whole number, not %s" % value)


def run(feature, out, err, timeout=None):
    """Run the gate for feature. out and err take text. timeout is minutes (a float is fine), 0 for none;
    None reads FLOW_GATE_TIMEOUT. Returns the exit code."""
    if not feature:
        err("usage: python3 scripts/gate.py <feature>\n")
        return 2
    if timeout is None:
        try:
            timeout = timeout_minutes()
        except ValueError as problem:
            err("gate: %s\n" % problem)
            return 2
    path = Path(os.environ.get("FLOW_DIR") or "plans") / feature / "commands.md"
    if not path.is_file():
        out("gate: no commands.md for " + feature + ", nothing to run\n")
        return 0
    ran = 0
    for key in KEYS:
        cmd = command(path, key)
        if cmd == "" or cmd.startswith("<"):
            continue
        ran += 1
        out("gate: " + key + ": " + cmd + "\n")
        with tempfile.TemporaryFile() as log:
            args, use_shell = shell(cmd)
            code, timed_out = proc.run(args, use_shell, log, timeout)
            if timed_out:
                out("gate: %s timed out after %s minutes, stopped: %s\n" % (key, format(timeout, "g"), cmd))
                return 1
            if code != 0:
                log.seek(0)
                out("gate: " + key + " failed. the last lines of its output:\n")
                out(tail(log.read().decode("utf-8", "surrogateescape")))
                return 1
    if ran > 0:
        out("gate: %d command(s) passed\n" % ran)
    else:
        out("gate: no commands defined, nothing to run\n")
    return 0


def _writer(stream):
    def write(text):
        stream.buffer.write(text.encode("utf-8", "surrogateescape"))
        stream.buffer.flush()
    return write


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    sys.stdout.flush()
    sys.stderr.flush()
    return run(argv[0] if argv else "", _writer(sys.stdout), _writer(sys.stderr))
