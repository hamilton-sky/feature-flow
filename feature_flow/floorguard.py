"""The floor guard, ported from the bash script with the same output and exit codes.

usage: python3 scripts/floor-guard.py <feature> <NN> [base-commit]
looks at the diff from base-commit (default HEAD~1) to HEAD for ways of weakening the bar
instead of meeting it: skipped tests, silenced checks, empty catches, deleted tests,
lowered thresholds, edited lint or test config.
it also protects the plan from the worker: only the ticket's own Status line and Answer,
appended lines in map.md and learnings.md may change, and nothing else under the plans folder.
a ticket can allow categories with a line "Floor: allow skip, suppress" (skip, suppress,
empty-catch, test-delete, threshold, config, ticket-edit, commands-edit). the line is
read from the ticket as it was at base-commit, so a worker cannot excuse itself.
run it from the repo root. exit 0 clean, 1 findings, 2 usage error.

The bash version ran its pattern matching in awk (mawk on Ubuntu, a byte-oriented awk), so the
diff is handled here as bytes too: the patterns, the 100 byte cut and the lower-casing behave
like mawk's. Text is decoded with surrogateescape so any byte comes back out unchanged.
"""

import os
import re
import subprocess
import sys

USAGE = "usage: python3 scripts/floor-guard.py <feature> <NN> [base-commit]"

SKIP = re.compile(rb"@pytest\.mark\.(skip|xfail)|pytest\.skip\(|(^|[^A-Za-z_])(it|test|describe)\.(skip|todo)\("
                  rb"|(^|[^A-Za-z_])(xit|xdescribe|xtest)\(|@Disabled|t\.Skip\(|#\[ignore\]|unittest\.skip"
                  rb"|self\.skipTest\(|pytest\.importorskip|@unittest\.expectedFailure|t\.Skipf\(|t\.SkipNow\(|#\[ignore = ")
FOCUSED = re.compile(rb"\.only\(|(?<!def )(?<![A-Za-z0-9_.])(fit|fdescribe)\(")
SUPPRESS = re.compile(rb"# noqa|# type: ignore|# pylint: disable|# pragma: no cover|# fmt: off|# ruff: noqa"
                      rb"|eslint-disable|@ts-ignore|@ts-expect-error|// nolint|#\[allow\(|--no-verify")
EMPTY_CATCH = re.compile(rb"except[^:]*:[ \t]*pass[ \t]*$|catch[ \t]*(\([^)]*\))?[ \t]*\{[ \t]*\}")
THRESHOLD = re.compile(rb"fail_under|fail-under|coverageThreshold|cov-fail-under")
DELETED_TEST = re.compile(r"(^|/)(test_[^/]*\.py|[^/]*_test\.[a-z]+|[^/]*\.(test|spec)\.[a-z]+|tests?/|__tests__/)")
CONFIG = re.compile(r"(^|/)(\.eslintrc[^/]*|eslint\.config\.[a-z]+|ruff\.toml|\.ruff\.toml|mypy\.ini|pytest\.ini"
                    r"|tox\.ini|tsconfig[^/]*\.json|jest\.config\.[a-z]+|vitest\.config\.[a-z]+"
                    r"|\.pre-commit-config\.yaml|\.github/workflows/[^/]*|\.azure/.*)$")
ASSERT_REMOVED = re.compile(rb"^-.*(assert|expect\()")
ASSERT_ADDED = re.compile(rb"^\+.*(assert|expect\()")
FIELDS = re.compile(rb"[ \t\n]+")
SPACE_CHARS = " \t\n\v\f\r"
HEX = b"0123456789abcdefABCDEF"


def _text(data):
    return data.decode("utf-8", "surrogateescape")


def _bytes(text):
    return text.encode("utf-8", "surrogateescape")


def _records(data):
    """awk records: split on newline, a last line without one still counts."""
    if not data:
        return []
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    return lines


def _strip_newlines(data):
    """What $(...) does to a command's output."""
    return data.rstrip(b"\n")


def _ascii_lower(data):
    return bytes(c + 32 if 65 <= c <= 90 else c for c in data)


def _awk_assign(value):
    """Escape processing mawk applies to `awk -v name=value`."""
    simple = {ord('"'): b'"', ord("\\"): b"\\", ord("a"): b"\a", ord("b"): b"\b", ord("f"): b"\f",
              ord("n"): b"\n", ord("r"): b"\r", ord("t"): b"\t", ord("v"): b"\v"}
    out = bytearray()
    i = 0
    while i < len(value):
        c = value[i]
        if c != 0x5C or i + 1 >= len(value):
            out.append(c)
            i += 1
            continue
        nxt = value[i + 1]
        if nxt in simple:
            out += simple[nxt]
            i += 2
        elif 0x30 <= nxt <= 0x37:
            j = i + 1
            while j < len(value) and j < i + 4 and 0x30 <= value[j] <= 0x37:
                j += 1
            out.append(int(value[i + 1:j], 8) & 0xFF)
            i = j
        elif nxt == ord("x") and value[i + 2:i + 3] and value[i + 2:i + 3] in HEX:
            j = i + 2
            while j < len(value) and j < i + 4 and value[j:j + 1] in HEX:
                j += 1
            out.append(int(value[i + 2:j], 16))
            i = j
        else:
            out.append(c)
            i += 1
    return bytes(out)


def allow_line(source):
    """The categories named on the first `Floor:` line in the first 20 lines, lower case."""
    for n, line in enumerate(_records(source), 1):
        if n > 20:
            break
        if line.startswith(b"Floor:"):
            v = re.sub(rb"^floor:[ \t]*allow[ \t]*", b"", _ascii_lower(line), count=1)
            return v.replace(b",", b" ")
    return b""


def diff_findings(diff, allow):
    """The awk pass over added lines: skip, suppress, empty-catch and threshold."""
    allow = b" " + _awk_assign(allow) + b" "
    out = []
    file = b""

    def report(cat, text):
        if (b" " + cat + b" ") in allow:
            return
        text = re.sub(rb"^[ \t]+", b"", text, count=1)
        out.append(cat + b": " + file + b": " + text[:100] + b"\n")

    for record in _records(diff):
        if record.startswith(b"+++ "):
            fields = FIELDS.split(record.strip(b" \t\n"))
            file = fields[1] if len(fields) > 1 else b""
            if file.startswith(b"b/"):
                file = file[2:]
            continue
        if record.startswith(b"+"):
            line = record[1:]
            if SKIP.search(line) or (FOCUSED.search(line) and DELETED_TEST.search(_text(file))):
                report(b"skip", line)
            if SUPPRESS.search(line):
                report(b"suppress", line)
            if EMPTY_CATCH.search(line):
                report(b"empty-catch", line)
            if THRESHOLD.search(line):
                report(b"threshold", line)
    return b"".join(out)


def frozen(data):
    """The ticket without its first Status line and from its Answer or Review findings on."""
    out = []
    seen = False
    for n, line in enumerate(_records(data), 1):
        if n <= 20 and not seen and line.startswith(b"Status:"):
            seen = True
            continue
        if re.match(rb"## (Answer|Review findings)", line):
            break
        out.append(line + b"\n")
    return b"".join(out)


def count_removed_real_lines(diff):
    n = 0
    for line in _records(diff):
        if line.startswith(b"---"):
            continue
        if line.startswith(b"-"):
            text = line[1:].strip(b" \t")
            if text != b"" and not re.match(rb"(- )?<", text):
                n += 1
    return n


def count_matching(diff, pattern):
    return sum(1 for line in _records(diff) if pattern.search(line))


def _find_ticket(dir_, num):
    """The first match of the glob "$DIR"/"$NUM"-*.md, or None."""
    prefix = dir_ + "/" + num + "-"
    folder, start = os.path.split(prefix)
    try:
        names = os.listdir(folder or ".")
    except OSError:
        return None
    hits = sorted(name for name in names
                  if name.startswith(start) and name.endswith(".md") and len(name) >= len(start) + 3
                  and (start.startswith(".") or not name.startswith(".")))
    return prefix + hits[0][len(start):] if hits else None


class _Guard:
    def __init__(self, err):
        self.err = err

    def git(self, *args, quiet=False):
        result = subprocess.run(["git"] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.stderr and not quiet:
            self.err(_text(result.stderr))
        return result.returncode, result.stdout


def run(argv, out, err, environ=None):
    """Run the guard. out and err take text; returns the exit code."""
    environ = os.environ if environ is None else environ
    feature = argv[0] if len(argv) > 0 else ""
    num = argv[1] if len(argv) > 1 else ""
    base = argv[2] if len(argv) > 2 and argv[2] else "HEAD~1"
    if not feature or not num:
        err(USAGE + "\n")
        return 2

    root = environ.get("FLOW_DIR") or "plans"
    dir_ = "%s/%s/%s" % (root, feature, environ.get("FLOW_TICKETS") or "tasks")
    ticket = _find_ticket(dir_, num)
    if ticket is None or not os.path.exists(ticket):
        err("no ticket %s in %s\n" % (num, dir_))
        return 2

    g = _Guard(err)
    if g.git("cat-file", "-e", "%s:./%s" % (base, ticket), quiet=True)[0] == 0:
        source = _strip_newlines(g.git("show", "%s:./%s" % (base, ticket), quiet=True)[1])
    else:
        try:
            with open(ticket, "rb") as f:
                source = _strip_newlines(f.read())
        except OSError as e:
            err("cat: %s: %s\n" % (ticket, e.strerror))
            return 1
    allow = allow_line(source)
    allow_words = " %s " % _text(allow)

    def allows(cat):
        return (" %s " % cat) in allow_words

    outside = ["--", ".", ":(exclude)%s" % root]
    rc, diff = g.git("diff", "--no-color", "--unified=0", base, "HEAD", *outside)
    if rc != 0:
        return rc
    findings = _text(_strip_newlines(diff_findings(diff, allow)))

    deleted = _git_lines(g, DELETED_TEST, "diff", "--name-only", "--diff-filter=D", base, "HEAD", *outside)
    if deleted and not allows("test-delete"):
        findings += "\n" + "\n".join("test-delete: " + p for p in deleted)

    touched = _git_lines(g, CONFIG, "diff", "--name-only", base, "HEAD", *outside)
    if touched and not allows("config"):
        findings += "\n" + "\n".join("config: " + p for p in touched)

    def rel(path):
        p = _records(g.git("ls-files", "--full-name", "--", path, quiet=True)[1])
        if p and p[0]:
            return _text(p[0])
        return path[2:] if path.startswith("./") else path

    def show(rev, path):
        return g.git("show", "%s:./%s" % (rev, path), quiet=True)[1]

    t_rel = rel(ticket)
    m_rel = rel("%s/%s/map.md" % (root, feature))
    c_rel = rel("%s/%s/commands.md" % (root, feature))
    l_rel = rel("%s/%s/learnings.md" % (root, feature))

    added = []

    def add_finding(cat, path, text):
        added.append("%s: %s: %s" % (cat, path, text))

    for st, path in _name_status(g.git("diff", "--name-status", "--no-renames", base, "HEAD", "--", root)[1]):
        if path == t_rel:
            if allows("ticket-edit"):
                continue
            if st != "M":
                add_finding("ticket-edit", path, "the ticket was added or deleted")
            elif frozen(show(base, path)) != frozen(show("HEAD", path)):
                add_finding("ticket-edit", path, "text outside the Status line and the Answer was changed")
        elif path in (m_rel, l_rel):
            if allows("ticket-edit"):
                continue
            if st == "D":
                add_finding("ticket-edit", path, "the file was deleted")
            elif st == "M" and count_removed_real_lines(
                    g.git("diff", "--no-color", "--unified=0", base, "HEAD", "--", path)[1]) > 0:
                add_finding("ticket-edit", path, "existing lines were removed or rewritten (append only)")
        elif path == c_rel:
            if not allows("commands-edit"):
                add_finding("commands-edit", path, "the frozen commands file was changed")
        else:
            if not allows("ticket-edit"):
                add_finding("ticket-edit", path, "only your own ticket, map.md and learnings.md may change")
    for line in added:
        findings += "\n" + line

    findings = "\n".join(line for line in findings.split("\n") if line.strip(SPACE_CHARS))

    diff = g.git("diff", "--no-color", "--unified=0", base, "HEAD", *outside)[1]
    removed_asserts = count_matching(diff, ASSERT_REMOVED)
    diff = g.git("diff", "--no-color", "--unified=0", base, "HEAD", *outside)[1]
    added_asserts = count_matching(diff, ASSERT_ADDED)
    if removed_asserts > added_asserts:
        out("warning: %d assertion line(s) removed, %d added. check that no test got weaker.\n"
            % (removed_asserts, added_asserts))

    if findings:
        out("floor guard: the diff weakens the bar instead of meeting it\n")
        out(findings + "\n")
        out("if a finding is intended, the ticket needs a line like: Floor: allow <category>\n")
        return 1
    out("floor guard: clean\n")
    return 0


def _git_lines(g, pattern, *args):
    """git ... | grep -E pattern, as a list of lines."""
    return [line for line in (_text(r) for r in _records(g.git(*args)[1])) if pattern.search(line)]


def _name_status(data):
    """`while IFS=$'\\t' read -r st path`: the first field and the rest, outer tabs trimmed."""
    rows = []
    for record in _records(data):
        line = _text(record).strip("\t")
        st, _, path = line.partition("\t")
        path = path.lstrip("\t")
        if path:
            rows.append((st, path))
    return rows


def main(argv=None):
    """The command line: writes the exact bytes to stdout and stderr."""
    argv = sys.argv[1:] if argv is None else argv

    def writer(stream):
        def write(text):
            stream.buffer.write(_bytes(text))
            stream.buffer.flush()
        return write

    sys.stdout.flush()
    return run(argv, writer(sys.stdout), writer(sys.stderr))
