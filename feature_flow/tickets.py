"""Reading and changing ticket files the way scripts/auto-flow.sh did."""

import re
from pathlib import Path

DONE = ("resolved", "done", "closed")
RESET = ("claimed", "in-progress")


def name(path):
    return Path(path).stem


def number(path):
    return name(path).split("-", 1)[0]


def _lines(path):
    return Path(path).read_text(encoding="utf-8").splitlines(True)


def status(path):
    """The first word of the Status line in the first 20 lines, lower case."""
    for line in _lines(path)[:20]:
        if line.startswith("Status:"):
            value = line[len("Status:"):].strip().lower()
            return value.split()[0] if value else ""
    return ""


def set_open(path):
    lines = _lines(path)
    for i, line in enumerate(lines[:20]):
        if line.startswith("Status:"):
            lines[i] = "Status: open\n"
            break
    Path(path).write_text("".join(lines), encoding="utf-8")


def append_findings(path, round_no, source, findings):
    text = "\n## Review findings (round %d, %s)\n\n%s\n" % (round_no, source, findings.rstrip("\n"))
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)


def commands_value(path, key):
    """A command from commands.md, or "" when it is missing or a placeholder in angle brackets."""
    path = Path(path)
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^%s:" % re.escape(key), line):
            value = re.sub(r"^%s:[ \t]*" % re.escape(key), "", line).replace("`", "")
            return "" if value.startswith("<") else value
    return ""
