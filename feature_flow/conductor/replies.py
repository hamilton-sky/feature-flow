"""Reading an agent's reply: its verdict or answer line, and the text under a heading."""

import re

VERDICT = re.compile(r"^REVIEW: (PASS|FAIL|ASK (?:architect|designer|po|user))[ \t\r\f\v]*$")
ANSWER = re.compile(r"^ANSWER: (GIVEN|USER)[ \t\r\f\v]*$")  # the last line of a consultant's reply


def section_after(text, heading):
    """The text under the last line that is exactly heading, up to the next `## ` heading or a verdict line."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == heading]
    if not starts:
        return ""
    out = []
    for line in lines[starts[-1] + 1:]:
        if line.startswith("## ") or VERDICT.match(line) or ANSWER.match(line):
            break
        out.append(line)
    return "\n".join(out).strip("\n")


def demote(text):
    """text with its `## ` headings made `### `, so it cannot open a section of the ticket it is written into."""
    return re.sub(r"(?m)^## ", "### ", text)
