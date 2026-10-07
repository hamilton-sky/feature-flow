"""The conductor's own proof of a ticket: the check block in its Done when."""

import re
from dataclasses import dataclass

FENCE = "```"
OPEN = FENCE + "check"


@dataclass(frozen=True)
class Check:
    """One `$ <command>`: exit is an int or "nonzero"; prints holds the substrings the output must contain."""
    command: str
    exit: object = 0
    prints: tuple = ()


class ParseError(ValueError):
    """A check block the parser cannot read. The message quotes the line."""


def _done_when(text):
    """The lines from the `## Done when` line up to the next line starting with `## `."""
    lines = [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]
    out = None
    for line in lines:
        if out is None:
            if line.startswith("## Done when"):
                out = []
            continue
        if line.startswith("## "):
            break
        out.append(line)
    return out or []


def checks_in(text):
    """The checks of every ```check block in the ticket's Done when, in order."""
    checks = []
    fence = None  # None outside a fence, else the line that opened it
    current = None  # [command, exit, prints, exit_seen] of the check being read

    def finish():
        if current is not None:
            checks.append(Check(current[0], current[1], tuple(current[2])))

    for line in _done_when(text):
        if fence is None:
            if line.startswith(FENCE):
                fence = line
            continue
        if line == FENCE:
            if fence == OPEN:
                finish()
                current = None
            fence = None
            continue
        if fence != OPEN:
            continue
        if line.strip() == "" or line.startswith("#"):
            continue
        if line.startswith("$ ") and line[2:].strip():
            finish()
            current = [line[2:].strip(), 0, [], False]
            continue
        word = line.split(" ", 1)[0]
        if word in ("exit", "prints") and current is None:
            raise ParseError("check block: %r comes before the first `$ <command>` line" % line)
        if word == "exit":
            value = line[len("exit "):].strip() if line.startswith("exit ") else ""
            if current[3]:
                raise ParseError("check block: %r is a second exit line for %r" % (line, current[0]))
            if value == "nonzero":
                current[1] = "nonzero"
            elif re.fullmatch(r"[0-9]+", value):
                current[1] = int(value)
            else:
                raise ParseError("check block: %r needs a whole number or `nonzero`" % line)
            current[3] = True
            continue
        if word == "prints" and line.startswith("prints ") and line[len("prints "):]:
            current[2].append(line[len("prints "):])
            continue
        raise ParseError("check block: cannot read %r (expected `$ <command>`, `exit <N>`, "
                         "`exit nonzero`, `prints <text>`, `#` or a blank line)" % line)
    if fence == OPEN:
        raise ParseError("check block: %r is never closed by a %s line" % (fence, FENCE))
    return checks
