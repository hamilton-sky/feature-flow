"""Golden runs of the conductor: whole sessions played through the CLI, recorded once and compared on every run.

Each scenario builds a throwaway repo (helpers.Repo), writes a small plan, commands.md and fixture role and guide
files, and plays a session the way the skill does. Per call it records the command, its exit code and its stdout;
at the end the run log's events (without the timestamp column) and the sorted keys of the state file. Commit shas,
session tokens, the temp repo path, the lane worktree paths and the interpreter path are replaced with placeholders
first, so a recording holds only what a user or a caller can rely on.

`python3 tests/py/test_golden.py --record` rewrites the recordings in tests/py/golden/; any other run compares.
"""

import difflib
import hashlib
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

from helpers import Repo

GOLDEN = Path(__file__).resolve().parent / "golden"
RECORD = False  # set by --record on the command line
PYTHON = '"%s"' % sys.executable
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON
LOG_MARK = "=== log events ==="
KEYS_MARK = "=== state keys ==="
SHA = re.compile(r"\b[0-9a-f]{40}\b")
QUOTED = re.compile(r"'(<(?:repo|python)>[^'\s]*)'")  # shlex.quote of a Windows path; a POSIX one has none

# Fixture roles and guides: small, so a later edit of the real agents/ and guides/ never changes a recording, yet
# each placeholder the conductor fills in and each `python3 scripts/` line it rewrites is still in the prompt.
ROLES = ("ticket-builder", "ticket-reviewer", "flow-scout", "flow-web", "flow-architect", "flow-designer", "flow-po",
         "flow-tester", "feature-planner", "plan-reviewer", "flow-skeptic", "flow-lens")
GUIDES = ("build", "review", "review-quality", "review-single", "review-feature", "test", "debug", "plan",
          "plan-review", "replan")


def role_text(name):
    return ("---\nname: %s\ndescription: fixture role\n---\n\nYou are the %s (fixture role).\n"
            "Status: `python3 scripts/flow-status.py <feature>`.\n" % (name, name))


def guide_text(name):
    return ("# Guide %s (fixture)\n\nFeature <feature>, ticket <NN> at <ticket>, sha <sha>, base <base>, "
            "base commit <base-commit>, start <start-commit>, plan <plan>, tasks <tasks>, folder <folder>, "
            "acceptance <acceptance>.\nRun `python3 scripts/flow-status.py <feature> --next`.\n" % name)


def ticket(title, blocked, header, check=True):
    lines = ["# %s\n" % title, "Type: task", "Status: open", "Blocked by: %s" % blocked, "Test first: no"] + header
    return "\n".join(lines) + "\n\nbody\n\n## Done when\n\n- x\n\n" + (CHECK if check else "") + "## Answer\n"


def git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, check=True).stdout.strip()


def compare(name, expected, actual):
    """None when the two recordings match, else a message naming the scenario, the first differing line and both
    versions. Compared line by line, so a line ending never matters."""
    want, got = expected.splitlines(), actual.splitlines()
    if want == got:
        return None
    index = next((i for i, (a, b) in enumerate(zip(want, got)) if a != b), min(len(want), len(got)))
    section = "calls"
    for line in want[:index + 1]:  # where the recorded line was, or the end of the recording
        if line == LOG_MARK:
            section = "log events"
        elif line == KEYS_MARK:
            section = "state keys"
    show = lambda lines: lines[index] if index < len(lines) else "(no line: the recording ends here)"
    diff = "\n".join(difflib.unified_diff(want, got, "recorded", "now", lineterm="", n=2))
    return ("golden %s differs from its recording at line %d (%s)\nrecorded: %s\nnow:      %s\n"
            "rewrite it only with `python3 tests/py/test_golden.py --record`, and only before the code moves\n%s"
            % (name, index + 1, section, show(want), show(got), diff))


class Session:
    """One scenario: a repo, the calls made in it, and what they printed."""

    def __init__(self, test, plan, commands="", spec=None, **env):
        """plan: [(slug, title, blocked, header lines)]; commands: lines added to commands.md."""
        self.test = test
        self.repo = Repo(tickets=())
        test.addCleanup(self.repo.close)
        # run in the real path, as the scripts folder is: on Windows the temp folder can be a short (8.3) name
        self.repo.dir = self.repo.dir.resolve()
        self.dir = self.repo.dir
        for name in ROLES:
            self.write("agents/%s.md" % name, role_text(name))
        for name in GUIDES:
            self.write("guides/%s.md" % name, guide_text(name))
        self.write("plans/f/commands.md", "# Commands: f\n\nSetup: `%s -c \"pass\"`\nSmoke: `%s -c \"pass\"`\n"
                   "Test: `%s -c \"pass\"`\n%s" % (PYTHON, PYTHON, PYTHON, commands))
        if spec:
            self.write("plans/f/spec.md", spec)
        for slug, title, blocked, header in plan:
            self.write("plans/f/tasks/%s.md" % slug, ticket(title, blocked, header))
        self.repo.commit("plan")
        self.reply = Path(str(self.dir) + "-reply.txt")
        test.addCleanup(lambda: self.reply.unlink() if self.reply.exists() else None)
        self.env = dict(env)
        self.tokens = []
        self.lines = ["# scenario %s" % test._testMethodName,
                      " ".join(["# env"] + ["%s=%s" % kv for kv in sorted(env.items())])]
        self.paths = self.known_paths()

    def known_paths(self):
        found = {str(self.dir), self.repo.tmp.name, os.path.realpath(str(self.dir)),
                 git(self.dir, "rev-parse", "--show-toplevel")}
        out = set()
        for path in found:
            out |= {path, path.replace("\\", "/"), path.replace("/", "\\")}
        return sorted(out, key=len, reverse=True)

    def write(self, rel, text):
        path = self.repo.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def note(self, text):
        self.lines.append("# %s" % text)

    def clean(self, text):
        for path in self.paths:
            text = text.replace(path, "<repo>")
        for python in sorted({sys.executable, sys.executable.replace("\\", "/")}, key=len, reverse=True):
            text = text.replace(python, "<python>")
        text = SHA.sub("<sha>", text)  # first, so a token or owner below never cuts into a sha
        for token in self.tokens:
            owner = hashlib.sha256(token.encode("utf-8")).hexdigest()
            text = text.replace(token, "<token>").replace(owner, "<owner>").replace(owner[:8], "<owner>")
        text = text.replace("\\", "/")
        return QUOTED.sub(r"\1", text)

    def record(self, args, extra, rc, out):
        shown = " ".join(["%s=%s" % (k, self.clean(v)) for k, v in sorted(extra.items())] + [self.clean(a) for a in args])
        self.lines.append("$ %s" % shown)
        self.lines.append("exit %d" % rc)
        self.lines.extend(self.clean(out).splitlines())

    def call(self, *args, **extra):
        rc, out = self.repo.flow(*args, **dict(self.env, **extra))
        if args[0] == "start" and rc == 0 and out.startswith("OK "):
            self.tokens.append(out.split()[1])
            self.env["FLOW_SESSION"] = out.split()[1]
        self.record(args, extra, rc, out)
        return rc, out

    def call_in(self, folder, *args, **extra):
        """A call run from folder (not the repo top), with the repo's own scripts/flow.py."""
        full = dict((k, v) for k, v in os.environ.items() if not k.startswith("FLOW_"))
        full.update(dict(self.env, FLOW_TRUSTED="1", **extra))
        result = subprocess.run([sys.executable, str(self.dir / "scripts" / "flow.py"), "f"] + list(args),
                                cwd=str(folder), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, env=full)
        rc, out = result.returncode, result.stdout.strip()
        self.note("from the folder %s" % self.clean(str(folder)))
        self.record(args, extra, rc, out)
        return rc, out

    def start(self, **extra):
        self.env.pop("FLOW_SESSION", None)
        rc, out = self.call("start", **extra)
        self.test.assertEqual(rc, 0, out)
        return out

    def lane_dir(self, lane):
        return self.repo.path(".feature-flow/lanes/f/lane-%s" % lane)

    def build(self, rel, files=None, lane=None, status="resolved"):
        """The builder writes files (path: text), sets the ticket's Status and commits, in the lane if given."""
        where = self.lane_dir(lane) if lane else self.dir
        name = Path(rel).stem
        for path, text in (files or {"work-%s.txt" % name: "work\n"}).items():
            (where / path).parent.mkdir(parents=True, exist_ok=True)
            (where / path).write_text(text, encoding="utf-8")
        path = where / rel
        path.write_text(re.sub(r"(?m)^Status: .*$", "Status: %s" % status, path.read_text(encoding="utf-8"), count=1),
                        encoding="utf-8")
        git(where, "add", "-A")
        git(where, "commit", "-qm", "feat: %s" % name)
        self.note("built %s%s" % (rel, " in lane %s" % lane if lane else ""))

    def append(self, rel, text, lane=None, message="ask"):
        where = self.lane_dir(lane) if lane else self.dir
        with open(str(where / rel), "a", encoding="utf-8") as handle:
            handle.write(text)
        git(where, "add", "-A")
        git(where, "commit", "-qm", message)
        self.note("appended to %s%s: %s" % (rel, " in lane %s" % lane if lane else "", text.strip().splitlines()[0]))

    def verdict(self, text, *lane):
        self.reply.write_text(text, encoding="utf-8")
        self.note("reply: %s" % " | ".join(text.strip().splitlines()))
        return self.call("verdict", str(self.reply), *lane)

    def scouts(self, *lane):
        """`scouts`, then every scout's prompt, and a reply saved for each."""
        rc, out = self.call("scouts", *lane)
        if out.startswith("SCOUT"):
            for line in out.splitlines():
                k, reply = line.split()[1], line.split(" ", 3)[3]
                self.call("scout-prompt", k, *lane)
                Path(reply).write_text("scout %s found the code in src/\n" % k, encoding="utf-8")
                self.note("scout %s replied" % k)
        return rc, out

    def show(self, rel):
        """Record a file the conductor wrote, such as a ticket with its findings."""
        self.note("file %s:" % rel)
        self.lines.extend(self.clean(self.repo.path(rel).read_text(encoding="utf-8")).splitlines())
        self.note("end of %s" % rel)

    def spend(self, minutes):
        """Write the minutes spent into the state, as real work would leave them (see test_budget_drive)."""
        values = {"spent": minutes * 60, "seen": int(time.time())}
        file = self.repo.path(".feature-flow/state/flow-f.state")
        lines = [line for line in file.read_text(encoding="utf-8").splitlines() if line.split("=", 1)[0] not in values]
        file.write_text("\n".join(lines + ["%s=%s" % kv for kv in values.items()]) + "\n", encoding="utf-8")
        self.note("spent %d minute(s)" % minutes)

    def text(self):
        events = [self.clean(line.split(",", 1)[1]) for line in self.repo.log().splitlines() if "," in line]
        path = self.repo.path(".feature-flow/state/flow-f.state")
        keys = []
        if path.is_file():
            keys = sorted({line.split("=", 1)[0] for line in path.read_text(encoding="utf-8").splitlines() if "=" in line})
        return "\n".join(self.lines + [LOG_MARK] + events + [KEYS_MARK] + keys) + "\n"

    def check(self):
        """Write the recording (--record) or compare with it."""
        name = self.test._testMethodName
        path = GOLDEN / ("%s.txt" % name)
        actual = self.text()
        if RECORD:
            GOLDEN.mkdir(exist_ok=True)
            with open(str(path), "w", encoding="utf-8", newline="\n") as handle:
                handle.write(actual)
            return
        self.test.assertTrue(path.is_file(), "no recording %s: run python3 tests/py/test_golden.py --record" % path)
        with open(str(path), encoding="utf-8") as handle:  # universal newlines: a CRLF checkout reads the same
            expected = handle.read()
        problem = compare(name, expected, actual)
        if problem:
            self.test.fail(problem)


T1, T2, T3 = "plans/f/tasks/01-a.md", "plans/f/tasks/02-b.md", "plans/f/tasks/03-c.md"
PASS = "fine\nREVIEW: PASS\n"
FAIL = "SPEC\n\n1. blocker work-01-a.txt: the work is wrong - write it again\n\nREVIEW: FAIL\n"
FEATURE_FAIL = "FEATURE\n1. major x.py (ticket 01): wrong - fix it\n\nREVIEW: FAIL\n"
ACCEPT = "plans/f/acceptance/check.py"
PASSES_WHEN_BUILT = ("import sys\ntry:\n    text = open('feature.txt').read().strip()\nexcept OSError:\n"
                     "    text = ''\nsys.exit(0 if text == 'done' else 1)\n")
SPEC = "# Spec\n\n## Stories\n\n- [ ] feature.txt says done\n"


class Golden(unittest.TestCase):
    def test_serial(self):
        s = Session(self, (("01-a", "A", "—", ["Level: 2"]), ("02-b", "B", "01", ["Level: 3", "Review: full"])),
                    FLOW_TICKETS_PER_SESSION="1")
        s.start()
        s.call("next")
        s.scouts()
        s.call("prompt")
        s.build(T1)
        s.call("next")
        s.scouts()
        s.call("prompt")
        s.verdict(FAIL)
        s.call("next")  # sent back
        s.show(T1)
        s.call("prompt")
        s.build(T1)
        s.call("next")
        s.verdict(PASS)
        s.call("next")  # one ticket per session: the handoff
        s.start()
        s.call("next")
        s.scouts()
        s.call("prompt")
        s.build(T2)
        s.call("next")
        s.scouts()
        s.call("prompt")
        s.verdict(PASS)
        s.call("next")  # the quality pass
        s.call("prompt")
        s.verdict(PASS)
        s.call("next")
        s.check()

    def test_relay(self):
        s = Session(self, (("01-a", "A", "—", ["Level: 2"]),), FLOW_RELAY="1", FLOW_TICKETS_PER_SESSION="99")
        s.start()
        s.call("next")
        s.build(T1)
        s.call("next")
        s.start()
        s.call("next")
        s.verdict(PASS)
        s.call("next")
        s.start()
        s.call("next")
        s.check()

    def test_fast(self):
        s = Session(self, (("01-a", "A", "—", ["Level: 1"]), ("02-b", "B", "01", ["Level: 2"])),
                    FLOW_TICKETS_PER_SESSION="99")
        s.start(FLOW_FAST="1")
        s.call("next")
        s.build(T1)
        s.call("next")
        s.build(T2)
        s.call("next")
        s.scouts()
        s.call("prompt")
        s.verdict(PASS)
        s.call("next")
        s.check()

    def test_fast_batch(self):
        s = Session(self, (("01-a", "A", "—", ["Level: 1", "Touches: a/"]), ("02-b", "B", "—", ["Level: 1", "Touches: b/"])),
                    FLOW_TICKETS_PER_SESSION="99")
        s.start(FLOW_FAST="1")
        s.call("next")
        s.call("prompt")
        s.build(T1, {"a/x.txt": "x\n"})
        s.build(T2, {"b/y.txt": "y\n"})
        s.call("next")
        s.verdict(PASS)
        s.call("next")
        s.check()

    def lanes_plan(self):
        return (("01-a", "A", "—", ["Level: 2", "Touches: a/"]), ("02-b", "B", "—", ["Level: 2", "Touches: b/"]),
                ("03-c", "C", "01", ["Level: 2", "Touches: a/"]))

    def test_lanes(self):
        s = Session(self, self.lanes_plan(), FLOW_TICKETS_PER_SESSION="99", FLOW_LANES="2")
        s.start()
        s.call("next")
        s.call("next")
        s.call("next")
        s.scouts("1")
        s.call("prompt", "1")
        s.build(T2, {"b/y.txt": "y\n"}, lane=2)
        s.call("next", "2")
        s.build(T1, {"a/x.txt": "x\n"}, lane=1)
        s.call("next", "1")
        s.call("prompt", "2")
        s.verdict(PASS, "2")
        s.call("next", "2")
        s.verdict(PASS, "1")
        s.call("next", "1")
        s.call("next")
        s.build(T3, {"a/z.txt": "z\n"}, lane=1)
        s.call("next", "1")
        s.verdict(PASS, "1")
        s.call("next", "1")
        s.note("lane branches left: %d" % len(git(s.dir, "branch", "--list", "ff/*").split()))
        s.check()

    def test_fast_lanes(self):
        s = Session(self, self.lanes_plan()[:2], FLOW_TICKETS_PER_SESSION="99", FLOW_LANES="2")
        s.start(FLOW_FAST="1")
        s.call("next")
        s.call("next")
        s.call("next")
        s.build(T1, {"a/x.txt": "a\n"}, lane=1)
        s.call("next", "1")
        s.build(T2, {"b/y.txt": "b\n"}, lane=2)
        s.call("next", "2")
        s.call("next", "1")  # the feature review has no lane
        s.call("prompt")
        s.verdict(PASS)
        s.call("next")
        s.check()

    def write_tests(self, s, text=PASSES_WHEN_BUILT):
        s.write(ACCEPT, text)
        s.repo.commit("test(f): acceptance tests")
        s.note("the tester wrote %s" % ACCEPT)

    def test_acceptance(self):
        s = Session(self, (("01-a", "A", "—", ["Level: 2"]),), commands="Acceptance: `%s %s`\n" % (PYTHON, ACCEPT),
                    spec=SPEC, FLOW_TICKETS_PER_SESSION="99", FLOW_SCOUTS="off")
        s.start()
        s.call("next")
        s.call("prompt")
        self.write_tests(s)
        s.call("next")
        s.build(T1, {"feature.txt": "done\n"})
        s.call("next")
        s.verdict(PASS)
        s.call("next")
        s.check()

    def test_lanes_acceptance(self):
        plan = (("01-a", "A", "—", ["Level: 2", "Touches: a/"]), ("02-b", "B", "—", ["Level: 2", "Touches: b/, feature.txt"]))
        s = Session(self, plan, commands="Acceptance: `%s %s`\n" % (PYTHON, ACCEPT), spec=SPEC,
                    FLOW_TICKETS_PER_SESSION="99", FLOW_SCOUTS="off", FLOW_LANES="2")
        s.start()
        s.call("next")
        s.call("prompt", "1")  # the tester has no lane
        s.call("prompt")
        self.write_tests(s)
        s.call("next")
        s.call("next")
        s.call("next")
        s.build(T1, {"a/x.txt": "x\n"}, lane=1)
        s.call("next", "1")
        s.verdict(PASS, "1")
        s.call("next", "1")
        s.build(T2, {"b/y.txt": "y\n", "feature.txt": "done\n"}, lane=2)
        s.call("next", "2")
        s.verdict(PASS, "2")
        s.call("next", "2")
        s.check()

    def test_agent(self):
        s = Session(self, (("01-a", "A", "—", ["Level: 2"]), ("02-b", "B", "01", ["Level: 2"])), FLOW_SCOUTS="off")
        s.start(FLOW_DRIVER="agent")
        for rel in (T1, T2):
            s.call("next")
            s.build(rel)
            s.call("next")
            s.verdict(PASS)
        s.call("next")
        s.check()

    def test_agent_budget(self):
        s = Session(self, tuple(("0%d-t" % i, "T%d" % i, "—" if i == 1 else "0%d" % (i - 1), ["Level: 2"])
                                for i in (1, 2, 3)), FLOW_SCOUTS="off")
        s.start(FLOW_DRIVER="agent", FLOW_BUDGET="30")
        s.call("next")
        s.build("plans/f/tasks/01-t.md")
        s.call("next")
        s.spend(31)
        s.verdict(PASS)
        s.call("next")  # over the budget: fast mode on
        s.build("plans/f/tasks/02-t.md")
        s.call("next")  # fast mode passed a ticket: the re-plan offer
        s.call("budget")
        s.call("next")
        s.build("plans/f/tasks/03-t.md")
        s.call("next")
        s.verdict(PASS)
        s.call("next")
        s.check()

    def test_ask_in_a_lane(self):
        s = Session(self, self.lanes_plan()[:2], FLOW_TICKETS_PER_SESSION="99", FLOW_LANES="2")
        s.start()
        s.call("next")
        s.call("next")
        s.call("next")
        s.append(T1, "\n## Ask: architect\n\nShould the cache live in a/ or b/?\n", lane=1)
        s.call("next", "1")
        s.scouts("1")
        s.call("prompt", "1")
        s.verdict("## Answer\n\nIn a/.\n\nANSWER: GIVEN\n", "1")
        s.call("next", "1")
        s.call("prompt", "1")
        s.build(T1, {"a/x.txt": "x\n"}, lane=1)
        s.call("next", "1")
        s.verdict(PASS, "1")
        s.call("next", "1")
        s.build(T2, {"b/y.txt": "y\n"}, lane=2)
        s.call("next", "2")
        s.verdict(PASS, "2")
        s.call("next", "2")
        s.check()

    def test_failing_feature_review(self):
        s = Session(self, (("01-a", "A", "—", ["Level: 1"]), ("02-b", "B", "01", ["Level: 2"])),
                    FLOW_TICKETS_PER_SESSION="99", FLOW_SCOUTS="off")
        s.start(FLOW_FAST="1")
        s.call("next")
        s.build(T1)
        s.call("next")
        s.build(T2)
        s.call("next")
        s.verdict(FEATURE_FAIL)
        s.call("next")  # the fix ticket
        s.show("plans/f/tasks/03-feature-review-fixes-1.md")
        s.call("prompt")
        s.build("plans/f/tasks/03-feature-review-fixes-1.md")
        s.call("next")
        s.call("prompt")
        s.verdict(PASS)
        s.call("next")
        s.check()

    def test_mode_errors(self):
        s = Session(self, (("01-a", "A", "—", ["Level: 2"]),))
        s.call("start", FLOW_LANES="2", FLOW_RELAY="1")
        s.call("start", FLOW_LANES="9")
        s.call("start", FLOW_LANES="x")
        s.call("start", FLOW_DRIVER="robot")
        s.call("start", FLOW_FAST="2")
        s.repo.path("sub").mkdir()
        s.call_in(s.repo.path("sub"), "start", FLOW_LANES="2", FLOW_DIR=str(s.dir / "plans"))
        s.start()  # nothing was kept from the refused starts
        s.check()


class Comparison(unittest.TestCase):
    """The comparison catches a changed output line, a missing log event and an extra state key."""

    def test_the_comparison_catches_each_kind_of_change(self):
        path = GOLDEN / "test_serial.txt"
        self.assertTrue(path.is_file(), "no recording %s" % path)
        with open(str(path), encoding="utf-8") as handle:
            text = handle.read()
        lines = text.splitlines()
        self.assertIsNone(compare("test_serial", text, text.replace("\n", "\r\n")))
        out = next(i for i, line in enumerate(lines) if line.startswith("BUILD "))
        changed = lines[:out] + ["BUILD something else"] + lines[out + 1:]
        message = compare("test_serial", text, "\n".join(changed) + "\n")
        self.assertIn("test_serial", message)
        self.assertIn("line %d (calls)" % (out + 1), message)
        self.assertIn("recorded: %s" % lines[out], message)
        self.assertIn("now:      BUILD something else", message)
        log = lines.index(LOG_MARK)
        self.assertNotEqual(lines[log + 1], KEYS_MARK)
        missing = lines[:log + 1] + lines[log + 2:]
        message = compare("test_serial", text, "\n".join(missing) + "\n")
        self.assertIn("(log events)", message)
        self.assertIn("recorded: %s" % lines[log + 1], message)
        extra = lines + ["zz_new_key"]
        message = compare("test_serial", text, "\n".join(extra) + "\n")
        self.assertIn("(state keys)", message)
        self.assertIn("now:      zz_new_key", message)


if __name__ == "__main__":
    if "--record" in sys.argv:
        sys.argv.remove("--record")
        RECORD = True
    unittest.main()
