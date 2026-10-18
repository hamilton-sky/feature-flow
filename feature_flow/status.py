"""The ticket graph reader, ported from the bash script of the same name.

usage: python3 scripts/flow-status.py <feature> [--next | --counts | --check | --lint | --estimate | --mermaid [plain] | --json]
Exit codes for --next: 0 a ready ticket path is printed, 10 all done, 11 unfinished but nothing ready.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys

from feature_flow import suggest, tickets

USAGE = ("usage: python3 scripts/flow-status.py <feature> [--next | --counts | --check | --lint | --estimate | "
         "--mermaid [plain] | --json]")


def _env(name, default):
    return os.environ.get(name) or default


def jstr(s):
    out = ['"']
    for c in s:
        if c == "\\":
            out.append("\\\\")
        elif c == '"':
            out.append('\\"')
        elif c == "\t":
            out.append("\\t")
        elif c == "\001":
            out.append("\\n")
        elif c < " ":
            pass
        else:
            out.append(c)
    out.append('"')
    return "".join(out)


def run(argv, out, err):
    """Write what the bash script would to out and err, and return its exit code."""
    feature = argv[0] if len(argv) > 0 else ""
    mode = argv[1] if len(argv) > 1 and argv[1] != "" else "table"
    opt = argv[2] if len(argv) > 2 else ""
    if feature == "":
        err.write(USAGE + "\n")
        return 2
    root = _env("FLOW_DIR", "plans")
    folder = "%s/%s/%s" % (root, feature, _env("FLOW_TICKETS", "tasks"))
    if not os.path.isdir(folder):
        err.write("no ticket folder: %s\n" % folder)
        err.write(suggest.hint(feature, suggest.features(root)))
        return 2
    paths = tickets.ticket_files(folder)
    if not paths:
        err.write("no tickets in %s\n" % folder)
        return 2

    if mode in ("--check", "--lint"):
        learnings = "%s/%s/learnings.md" % (root, feature)
        if os.path.isfile(learnings):
            lines = sum(1 for line in tickets.records(learnings) if line.strip(" \t\n\v\f\r") != "")
            if lines > 40:
                out.write("warning: learnings.md has %d lines. every session reads it, so a human should prune it\n"
                          % lines)

    g = tickets.Graph(paths)
    return _report(g, mode, opt, feature, out, err, root)


def _report(g, mode, opt, feature, out, err, root="plans"):
    n = len(g.order)
    count = {"resolved": 0, "open": 0, "claimed": 0, "waiting": 0, "parked": 0, "unknown": 0}
    ready = {}
    first = None
    unfinished = 0
    for t in g.order:
        ready[t] = False
        count[g.stat[t]] += 1
        if g.stat[t] == "open":
            if all(d in g.seen and g.stat[d] == "resolved" for d in g.blk[t]):
                ready[t] = True
                if first is None:
                    first = t
        if g.stat[t] not in ("resolved", "parked"):
            unfinished += 1
    nready = sum(1 for t in g.order if ready[t])

    if mode == "--next":
        if first is not None:
            out.write(g.path[first] + "\n")
            return 0
        if unfinished == 0:
            err.write("COMPLETE\n")
            return 10
        err.write("stuck: %d claimed, %d waiting, %d open but blocked, %d unknown status\n"
                  % (count["claimed"], count["waiting"], count["open"], count["unknown"]))
        return 11

    counts = (n, count["resolved"], count["open"], count["claimed"], count["waiting"], count["parked"],
              count["unknown"], nready)

    if mode == "--counts":
        out.write("total=%d resolved=%d open=%d claimed=%d waiting=%d parked=%d unknown=%d ready=%d\n" % counts)
        return 0

    if mode == "--json":
        parts = []
        for t in g.order:
            bl = ",".join(jstr(g.lab[d] if d in g.seen else "%02d" % d) for d in g.blk[t])
            parts.append('{"id":%d,"label":%s,"title":%s,"status":%s,"type":%s,"test_first":%s,"blocked_by":[%s],'
                         '"ready":%s,"file":%s}'
                         % (t, jstr(g.lab[t]), jstr(g.title[t]), jstr(g.stat[t]), jstr(g.typ.get(t) or "task"),
                            jstr(g.tf.get(t, "")), bl, "true" if ready[t] else "false", jstr(g.path[t])))
        out.write('{"feature":%s,"tickets":[%s],"counts":{"total":%d,"resolved":%d,"open":%d,"claimed":%d,'
                  '"waiting":%d,"parked":%d,"unknown":%d,"ready":%d}}\n' % ((jstr(feature), ",".join(parts)) + counts))
        return 0

    if mode == "--mermaid":
        out.write("flowchart TD\n")
        for t in g.order:
            cls = g.stat[t]
            if cls == "open":
                cls = "ready" if ready[t] else "open"
            if cls == "unknown":
                cls = "open"
            suffix = "" if opt == "plain" else ":::" + cls
            out.write('  T%s["%s %s"]%s\n' % (g.lab[t], g.lab[t], g.title[t].replace('"', "'"), suffix))
        for t in g.order:
            for d in g.blk[t]:
                if d in g.seen:
                    out.write("  T%s --> T%s\n" % (g.lab[d], g.lab[t]))
        if opt != "plain":
            out.write("  classDef resolved fill:#d4edda,stroke:#2e7d32\n"
                      "  classDef ready fill:#fff3cd,stroke:#b8860b\n"
                      "  classDef open fill:#f5f5f5,stroke:#999999\n"
                      "  classDef claimed fill:#cfe2ff,stroke:#1d4ed8\n"
                      "  classDef waiting fill:#fde2e2,stroke:#b91c1c\n"
                      "  classDef parked fill:#eeeeee,stroke:#bbbbbb,stroke-dasharray:4 3\n")
        return 0

    if mode in ("--check", "--lint"):
        extra = lint(g, "%s/%s" % (root, feature)) if mode == "--lint" else ([], [])
        return _check(g, ready, nready, unfinished, out, extra)

    if mode == "--estimate":
        return estimate(g, out)

    for t in g.order:
        bl = ",".join("%02d" % d for d in g.blk[t])
        out.write("%s  %-9s %-6s %-12s %s\n" % (g.lab[t], g.stat[t], "READY" if ready[t] else "-",
                                                 "after " + bl if bl else "", g.title[t]))
    return 0


PATH_REF = re.compile(r"`([A-Za-z0-9_./-]+/[A-Za-z0-9_.-]+\.[A-Za-z0-9]+)`")
NAME_REF = re.compile(r"`([A-Za-z_][A-Za-z0-9_]{3,}(?:\(\))?)`")
CREATES = re.compile(r"\b(new|adds?|creates?|introduces?|defines?)\b", re.IGNORECASE)
# a Done when bullet must pass or fail; these let it do neither
ESCAPE = re.compile(r"\b(or explain|explain why|if possible|where possible|if feasible|where feasible|if practical|"
                    r"as far as possible|ideally|unless|otherwise (?:explain|note|document|say)|"
                    r"or (?:document|note|say|describe) (?:why|the reason))\b|"
                    r"\bif\b[^.]*\b(?:differ|differs|mismatch|do not match|don't match)\b[^.]*\b(?:explain|note|say|document)\b",
                    re.IGNORECASE)
# what a test runner or checker prints, for the commands whose output is only a summary
RUNNERS = (
    (re.compile(r"\bpytest\b"), ("passed", "failed", "error", "skipped", "deselected", "xfail", "no tests ran",
                                  "warning", "test", "::")),
    (re.compile(r"-m\s+unittest\b"), ("ok", "ran ", "failed", "error", "skipped", "test")),
    (re.compile(r"\bmypy\b"), ("success", "no issues", "error", "note", "found")),
    (re.compile(r"\bgo\s+test\b"), ("ok", "pass", "fail", "test", "---", "no test files")),
    (re.compile(r"\bcargo\s+test\b"), ("test result", "ok", "passed", "failed", "test")),
    (re.compile(r"\b(jest|vitest)\b"), ("tests:", "test suites", "passed", "failed", "pass", "fail", "test")),
    (re.compile(r"\b(ruff|flake8|eslint)\b"), ("all checks passed", "found", "error", "warning", "problem")),
)
QUIET_WORDS = ("test", "[", "true", "false", ":")


def _sections(lines):
    """[(section heading or "", line)] for the ticket's lines up to its Answer, review findings or Attempt note."""
    out, heading = [], ""
    for line in lines:
        if re.match(r"^## (Answer|Review findings|Attempt note)", line):
            break
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            continue
        out.append((heading, line))
    return out


def _quiet(command):
    """True when the command can print nothing: a test, a quiet grep or git, or all output thrown away."""
    if re.search(r"(&>\s*/dev/null|>\s*/dev/null\s+2>(&1|\s*/dev/null))\s*$", command):
        return True
    last = re.split(r"(?<!\|)\|(?!\|)", command)[-1].strip()
    words = last.split()
    if not words:
        return False
    if words[0] in QUIET_WORDS or (words[0] == "tsc" and "--noEmit" in words):
        return True
    if words[0] in ("grep", "egrep", "fgrep", "rg") and any(
            w in ("--quiet", "--silent") or re.fullmatch(r"-[A-Za-z]*q[A-Za-z]*", w) for w in words[1:]):
        return True
    return words[0] == "git" and "--quiet" in words


def _cannot_print(lab, check):
    """A warning when a check expects output its command cannot print, else None."""
    for text in check.prints:
        if _quiet(check.command):
            return ("%s: check `$ %s` expects `%s`, but the command prints nothing (a quiet flag, or the output is "
                    "thrown away). drop the prints line or the quiet flag" % (lab, check.command, text))
        if re.search(r"(^|\s)(-s|--capture=no)(\s|$)", check.command):
            continue
        for runner, words in RUNNERS:
            if runner.search(check.command) and not any(w in text.lower() for w in words):
                return ("%s: check `$ %s` expects `%s`, which that command does not print: it prints its own summary "
                        "(%s). name text the command really prints" % (lab, check.command, text,
                                                                        ", ".join(words[:3])))
    return None


def _exists_in_repo(name):
    """True when git finds the name as a word in a tracked file; None when git cannot tell."""
    try:
        found = subprocess.run(["git", "grep", "-q", "-F", "-w", "--", name.rstrip("()")],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return None
    return {0: True, 1: False}.get(found.returncode)


def _reach(g):
    """{ticket: every ticket it waits for, directly or not}."""
    before = {t: set(d for d in g.blk[t] if d in g.seen and d != t) for t in g.order}
    changed = True
    while changed:
        changed = False
        for t in g.order:
            more = set().union(*(before[d] for d in before[t])) if before[t] else set()
            if not more <= before[t]:
                before[t] |= more
                changed = True
    return before


def estimate(g, out):
    """The fresh subagents the tickets still to build will take on the first try, by the conductor's rules:
    one builder each; no reviewer for `Review: gate` with a check block (unless its diff turns out big), one
    or two for `auto` (one when the diff is small and the check block passes), two for `full`, `Type: convert`
    or no check block; and the phase reviewers before a `Type: acceptance` ticket."""
    areas = [a for a in (os.environ.get("FLOW_PHASE_AREAS") or "correctness,security,performance").split(",")
             if a.strip()]
    builders = low = high = phase = 0
    for t in g.order:
        if g.stat[t] in ("resolved", "parked"):
            continue
        checked = any(line.startswith("```check") for line in tickets.records(g.path[t]))
        mode, kind = g.review.get(t, "auto"), g.typ.get(t) or "task"
        if kind == "convert" or mode == "full" or not checked:
            span = (2, 2)
        elif mode == "gate":
            span = (0, 0)
        else:
            span = (1, 2)
        if kind == "acceptance" and os.environ.get("FLOW_PHASE_REVIEW", "on") != "off":
            phase = len(areas)
        builders += 1
        low, high = low + span[0], high + span[1]
        out.write("%s  builder 1  reviewers %s  Review: %s%s\n"
                  % (g.lab[t], span[0] if span[0] == span[1] else "%d-%d" % span, mode,
                     "" if checked else ", no check block"))
    total = "%d" % (builders + low + phase) if low == high else "%d-%d" % (builders + low + phase,
                                                                        builders + high + phase)
    out.write("estimate: %d ticket(s) to build: %d builder(s), %s ticket reviewer(s), %d phase reviewer(s): %s fresh "
              "subagents on the first try. each send-back adds a builder and its reviewers\n"
              % (builders, builders, low if low == high else "%d-%d" % (low, high), phase, total))
    return 0


def lint(g, plan_dir):
    """(errors, warnings) the stricter plan lint adds to --check: every ticket carries a check block or
    says `Check: none <why>`, and commands.md names a Test command that can be found. It warns about a
    Done when with an escape clause, a check that expects output its command cannot print, and a ticket
    that uses a file or name another ticket creates without being blocked by it."""
    from feature_flow import proof  # proof imports the gate and git; only the lint needs it

    errors, warnings = [], []
    creates, uses = {}, {}  # a file or name -> the tickets whose lines create or use it
    for t in g.order:
        lab = g.lab[t]
        lines = tickets.records(g.path[t])
        body = _sections(lines)
        for heading, line in body:
            if line.strip().startswith("##"):
                continue
            create = CREATES.search(line) is not None
            for ref in PATH_REF.findall(line):
                if "plans/" not in ref and not os.path.exists(ref):
                    (creates if create else uses).setdefault(ref, set()).add(t)
            for name in NAME_REF.findall(line):
                if "_" in name or name.endswith("()") or re.search(r"[a-z][A-Z]", name):
                    (creates if create else uses).setdefault(name, set()).add(t)
        if g.typ.get(t) == "settle":
            continue
        has_block = any(line.startswith("```check") for line in lines)
        none = next((line for line in lines[:20] if line.startswith("Check:")), None)
        if none is not None:
            reason = none[len("Check:"):].strip()
            if not reason.lower().startswith("none") or not reason[4:].strip(" \t:-"):
                errors.append(lab + ": `Check:` must read `Check: none <why>`")
        elif not has_block:
            errors.append(lab + ": no check block. add one under Done when, or `Check: none <why>` in the header")
        fence = False
        for heading, line in body:
            if line.startswith("```"):
                fence = not fence
            if heading == "done when" and not fence:
                escape = ESCAPE.search(line)
                if escape:
                    warnings.append("%s: Done when has an escape clause (`%s`). a bullet must pass or fail; it never asks "
                                    "for an explanation instead" % (lab, escape.group(0)))
        try:
            found = proof.checks_in("\n".join(lines))
        except proof.ParseError as err:
            errors.append("%s: %s" % (lab, err))
            found = []
        for check in found:
            problem = _cannot_print(lab, check)
            if problem:
                warnings.append(problem)
    reach = _reach(g)
    for ref in sorted(set(creates) | set(uses)):
        makers = creates.get(ref, set())
        if PATH_REF.fullmatch("`%s`" % ref) and not makers:
            for t in sorted(uses[ref]):
                warnings.append("%s: names `%s`, which does not exist here (say `new` if it will be created)"
                                % (g.lab[t], ref))
            continue
        users = uses.get(ref, set()) - makers
        if not makers or not users or (not PATH_REF.fullmatch("`%s`" % ref) and _exists_in_repo(ref) is not False):
            continue
        for t in sorted(users):
            if not any(m in reach[t] for m in makers):
                warnings.append("%s: uses `%s`, which ticket %s creates, but is not blocked by it. add it to Blocked by"
                                % (g.lab[t], ref, ", ".join(g.lab[m] for m in sorted(makers))))
    commands = "%s/commands.md" % plan_dir
    test = tickets.commands_value(commands, "Test")
    if not os.path.isfile(commands):
        errors.append("commands.md is missing")
    elif not test:
        errors.append("commands.md has no Test command (a placeholder in angle brackets does not count)")
    else:
        try:
            first = shlex.split(test, posix=(os.name != "nt"))[0].strip("\"'")
        except (ValueError, IndexError):
            first = test.split()[0]
        if "=" not in first and shutil.which(first) is None and first not in ("cd", "set", "export"):
            warnings.append("commands.md Test starts with `%s`, which is not on PATH here" % first)
    return errors, list(dict.fromkeys(warnings))


def package(path):
    """The folder a path or glob names, at most two levels deep: `src/api/**` and `src/api/x.py` give
    `src/api`, `feature_flow/gate.py` gives `feature_flow`, a file at the top gives `.`."""
    parts = path.replace("\\", "/").strip("/").split("/")
    kept = []
    for part in parts:
        if any(c in part for c in "*?["):
            break
        kept.append(part)
    if len(kept) == len(parts) and kept and "." in kept[-1]:
        kept.pop()  # a file: its folder is the package
    return "/".join(kept[:2]) or "."


TEST_PATH = re.compile(r"(^|/)tests?(/|$)|(^|/)test_[^/]*$|_test\.[^/]+$|\.(test|spec)\.[^/]+$")


def packages(g, t):
    """The packages ticket t changes: from its `Touches:` line, else from the files its description names.
    Test files are left out: every ticket brings its own tests."""
    if g.touches.get(t):
        refs = g.touches[t]
    else:
        refs = [ref for heading, line in _sections(tickets.records(g.path[t]))
                if heading == "" and not line.startswith("#") for ref in PATH_REF.findall(line)]
    return {package(ref) for ref in refs if not TEST_PATH.search(ref.replace("\\", "/"))}


def same_package_chains(g):
    """[(tickets, package)]: each run of three or more unresolved tickets with numbers one after another, each
    blocked by the one before, that all change the same package. Such a run usually belongs in fewer tickets."""
    todo = [t for t in g.order if g.stat[t] != "resolved" and g.typ.get(t) not in ("settle", "acceptance")]
    found, run, common = [], [], set()

    def close():
        if len(run) >= 3:
            found.append((list(run), sorted(common)[0]))

    for t in todo:
        mine = packages(g, t)
        if run and t == run[-1] + 1 and run[-1] in g.blk[t] and common & mine:
            run.append(t)
            common &= mine
            continue
        close()
        run, common = [t], set(mine)
    close()
    return found


def _check(g, ready, nready, unfinished, out, extra=([], [])):
    errors = list(extra[0])
    for t in g.order:
        lab = g.lab[t]
        if t in g.dup:
            errors.append(lab + ": two tickets share this number")
        if not g.hasstatus[t]:
            errors.append(lab + ": no Status line in the first 20 lines")
        elif g.stat[t] == "unknown":
            errors.append(lab + ": unrecognised Status value")
        if not g.hasdone[t]:
            errors.append(lab + ": no ## Done when section")
        if t in g.hastf and g.tf[t] not in ("yes", "no"):
            errors.append(lab + ": Test first must be yes or no")
        if t in g.hasreview and g.review[t] not in ("gate", "auto", "full"):
            errors.append(lab + ": Review must be gate, auto or full")
        if t in g.hasgate and g.gate[t] not in ("quick", "full"):
            errors.append(lab + ": Gate must be quick or full")
        for d in g.blk[t]:
            if d == t:
                errors.append(lab + ": blocked by itself")
            elif d not in g.seen:
                errors.append("%s: blocked by %d, which does not exist" % (lab, d))

    placed = set()
    progress = True
    left = len(g.order)
    while progress and left > 0:
        progress = False
        for t in g.order:
            if t in placed:
                continue
            if all(not (d in g.seen and d != t and d not in placed) for d in g.blk[t]):
                placed.add(t)
                progress = True
                left -= 1
    if left > 0:
        errors.extend(g.lab[t] + ": part of a dependency cycle" for t in g.order if t not in placed)
    if nready == 0 and unfinished > 0:
        errors.append("no ticket is ready to start")

    reach = set()
    for _ in range(len(g.order)):
        changed = False
        for t in g.order:
            for d in g.blk[t]:
                if d not in g.seen:
                    continue
                if (t, d) not in reach:
                    reach.add((t, d))
                    changed = True
                for x in g.order:
                    if (d, x) in reach and (t, x) not in reach:
                        reach.add((t, x))
                        changed = True
        if not changed:
            break
    for t in g.order:
        for m in g.mentions.get(t, []):
            if m == t or m not in g.seen or (t, m) in reach or (m, t) in reach:
                continue
            out.write("warning: %s: mentions ticket %s but is not ordered against it. add it to Blocked by, or reword\n"
                      % (g.lab[t], g.lab[m]))
    todo = sum(1 for t in g.order if g.stat[t] != "resolved")
    if todo > 8:
        out.write("warning: %d tickets to build in one plan. aim for 4 to 6: merge chained tickets that touch the same "
                  "files, or plan the rest as a second round\n" % todo)
    for chain, pkg in same_package_chains(g):
        out.write("warning: %s are chained one after another and all change `%s`. merge them into fewer tickets "
                  "unless each needs its own review\n" % (", ".join(g.lab[t] for t in chain), pkg))
    for w in extra[1]:
        out.write("warning: " + w + "\n")
    if errors:
        for e in errors:
            out.write(e + "\n")
        return 1
    out.write("OK: %d tickets, %d ready now\n" % (len(g.order), nready))
    return 0


class _Bytes:
    """Writes text to a byte stream, keeping the bytes awk would have passed through untouched."""

    def __init__(self, stream):
        self.stream = stream

    def write(self, text):
        self.stream.write(text.encode("utf-8", "surrogateescape"))
        self.stream.flush()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.flush()
    return run(argv, _Bytes(sys.stdout.buffer), _Bytes(sys.stderr.buffer))
