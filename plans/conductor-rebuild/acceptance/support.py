"""Shared fixtures of the conductor-rebuild acceptance tests (spec.md § Acceptance tests).

They drive the CLI, `python3 scripts/flow.py f <command>` with FLOW_TRUSTED=1, in throwaway git repos made with
tests/py/helpers.py's Repo. "The old code" is the `feature_flow/` tree and `scripts/flow.py` at the first parent of
the commit that removed `feature_flow/conductor.py`; a twin run drives the same session on the old code and on the
current code and compares what a user sees. Not a test module: the runner only loads it through the tests.
"""

import atexit
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "tests" / "py") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests" / "py"))

from helpers import Repo  # noqa: E402  (the project's own throwaway repo)

PYTHON = '"%s"' % sys.executable
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON
ACCEPT_FILE = "plans/f/acceptance/check.py"

_OLD = {}


class NoOldCode(AssertionError):
    pass


def git_root(*args):
    return subprocess.run(["git"] + list(args), cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True).stdout.strip()


def old_code():
    """The folder holding the old code (feature_flow/ and scripts/flow.py), exported once per process.
    Fails, saying why, while feature_flow/conductor.py exists or no commit removed it."""
    if "dir" in _OLD:
        return _OLD["dir"]
    if (ROOT / "feature_flow" / "conductor.py").exists():
        raise NoOldCode("feature_flow/conductor.py still exists, so there is no old code to compare with: the "
                        "rebuild replaces it with the package feature_flow/conductor/")
    sha = git_root("log", "-1", "--format=%H", "--diff-filter=D", "--", "feature_flow/conductor.py")
    if not sha:
        raise NoOldCode("no commit removed feature_flow/conductor.py "
                        "(git log -1 --format=%H --diff-filter=D -- feature_flow/conductor.py is empty)")
    tar = subprocess.run(["git", "archive", "%s^" % sha, "feature_flow", "scripts/flow.py"], cwd=str(ROOT),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if tar.returncode != 0:
        raise NoOldCode("git archive %s^ failed: %s" % (sha, tar.stderr.decode("utf-8", "replace")))
    tmp = tempfile.TemporaryDirectory()
    atexit.register(tmp.cleanup)
    with tarfile.open(fileobj=io.BytesIO(tar.stdout)) as archive:
        if hasattr(tarfile, "data_filter"):
            archive.extractall(tmp.name, filter="data")
        else:
            archive.extractall(tmp.name)
    if not (Path(tmp.name) / "feature_flow" / "conductor.py").is_file():
        raise NoOldCode("the tree before %s has no feature_flow/conductor.py" % sha)
    _OLD["dir"] = Path(tmp.name)
    return _OLD["dir"]


def current_code():
    return ROOT


def put_code(where, code):
    """Replace feature_flow/ and scripts/flow.py in the folder where with those of code."""
    where = Path(where)
    if (where / "feature_flow").exists():
        shutil.rmtree(str(where / "feature_flow"))
    shutil.copytree(str(Path(code) / "feature_flow"), str(where / "feature_flow"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    (where / "scripts").mkdir(exist_ok=True)
    shutil.copy(str(Path(code) / "scripts" / "flow.py"), str(where / "scripts" / "flow.py"))


def ticket_text(index, blocked="—", header=()):
    lines = ["# T%d\n" % index, "Type: task", "Status: open", "Blocked by: %s" % blocked, "Test first: no"]
    lines += list(header)
    return "\n".join(lines) + "\n\nbody\n\n## Done when\n\n- x\n\n" + CHECK + "## Answer\n"


def accept_test(nums):
    """An acceptance test that passes once every ticket of nums has been built."""
    paths = ["t%s/%s.txt" % (n, n) for n in nums]
    return "import os, sys\nsys.exit(0 if all(os.path.exists(p) for p in %r) else 1)\n" % (paths,)


def conductor_files_as_one(value):
    """A code_files value with the conductor's own file names folded into one entry: the old code names
    feature_flow/conductor.py, the current code the files of the package feature_flow/conductor/ (spec.md lines 11,
    17 and 180: codehash hashes every file under feature_flow/, so the names follow the move). The key, its JSON
    format and every other file name stay as they are."""
    try:
        each = json.loads(value)
    except ValueError:
        return value
    if not isinstance(each, dict):
        return value
    folded = {}
    for name, digest in each.items():
        found = re.match(r"^(.*?)feature_flow/conductor(?:\.py$|/)", name.replace("\\", "/"))
        if found and (found.group(1) == "" or found.group(1).endswith("/")):
            folded[found.group(1) + "feature_flow/conductor<the conductor's files>"] = "<SHA>"
        else:
            folded[name] = digest
    return json.dumps(folded, sort_keys=True)


class World:
    """A throwaway repo running the given code, with a plan of tickets [(num, blocked, header lines)]."""

    def __init__(self, test, code, tickets=(("01", "—", ()), ("02", "01", ())), acceptance=False, commands_extra="",
                 env=None):
        self.test = test
        self.repo = Repo(tickets=(), local=False)
        test.addCleanup(self.repo.close)
        self.dir = self.repo.dir
        self.side = tempfile.TemporaryDirectory()  # reply, brief and question files: outside the repo
        test.addCleanup(self.side.cleanup)
        self.side_dir = Path(self.side.name)
        put_code(self.dir, code)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(self.dir / folder))
        commands = "# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\n" % (PYTHON, PYTHON)
        if acceptance:
            commands += "Acceptance: `%s %s`\n" % (PYTHON, ACCEPT_FILE)
        commands += commands_extra
        (self.dir / "plans/f/commands.md").write_text(commands, encoding="utf-8")
        (self.dir / "plans/f/spec.md").write_text("# Spec\n\n## Stories\n\n- [ ] every ticket is built\n",
                                                  encoding="utf-8")
        self.nums = []
        for index, (num, blocked, header) in enumerate(tickets, 1):
            header = list(header) or ["Touches: t%s/" % num]
            (self.dir / ("plans/f/tasks/%s-t.md" % num)).write_text(ticket_text(index, blocked, header),
                                                                     encoding="utf-8")
            self.nums.append(num)
        self.repo.commit("plan")
        self.env = dict(env or {})
        self.lines = []
        self.builds = 0
        self.reviews = 0

    # ---- running the CLI -------------------------------------------------

    def run(self, *args, cwd=None, script=None, prefix=(), **env):
        """Run the CLI; returns (exit code, stdout, stderr without the trusted runner's flow-state line), and
        keeps a normalised record of the call."""
        full = dict(os.environ)
        for key in list(full):
            if key.startswith("FLOW_"):
                del full[key]
        full["FLOW_TRUSTED"] = "1"
        full.update(self.env)
        full.update(env)
        script = script or str(self.dir / "scripts" / "flow.py")
        result = subprocess.run([sys.executable] + list(prefix) + [script, "f"] + list(args),
                                cwd=str(cwd or self.dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, env=full)
        err = "\n".join(l for l in result.stderr.splitlines() if not l.startswith("flow-state "))
        out = result.stdout.strip()
        self.lines.append("$ %s -> %d\n%s\n%s" % (self.norm(" ".join(args)), result.returncode, self.norm(out),
                                                  self.norm(err.strip())))
        return result.returncode, out, err

    def flow(self, *args, **env):
        rc, out, _ = self.run(*args, **env)
        return rc, out

    def python(self, code, **env):
        """Run a Python snippet in the repo (cwd at its top, its feature_flow importable)."""
        full = dict(os.environ)
        for key in list(full):
            if key.startswith("FLOW_"):
                del full[key]
        full["FLOW_TRUSTED"] = "1"
        full.update(self.env)
        full.update(env)
        result = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, '.')\n" + code],
                                cwd=str(self.dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, env=full)
        out = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
        self.lines.append("$ python -> %d\n%s" % (result.returncode, self.norm(out)))
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    def start(self, **env):
        rc, out = self.flow("start", **env)
        if rc == 0 and out.startswith("OK "):
            self.env["FLOW_SESSION"] = out.split()[1]
        return rc, out

    def norm(self, text):
        for folder in (self.dir, self.side_dir):
            for spelling in {str(folder), str(Path(folder).resolve()), Path(folder).resolve().as_posix()}:
                text = text.replace(spelling, "<TMP-%s>" % ("REPO" if folder == self.dir else "SIDE"))
        text = text.replace("\\", "/").replace("\r\n", "\n")
        return re.sub(r"\b[0-9a-f]{7,64}\b", "<SHA>", text)

    # ---- the repo --------------------------------------------------------

    def git(self, *args, cwd=None):
        return subprocess.run(["git"] + list(args), cwd=str(cwd or self.dir), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, check=True).stdout.strip()

    def side_file(self, name, text):
        path = self.side_dir / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def lane_dir(self, lane):
        return self.dir / ".feature-flow" / "lanes" / "f" / ("lane-%s" % lane)

    def resolve(self, ticket, where=None, extra=None, commit=True):
        """A builder's work on ticket (its path in the plan): a file under t<num>/, Status resolved, one commit."""
        where = Path(where or self.dir)
        self.builds += 1
        num = Path(ticket).name.split("-")[0]
        work = where / ("t%s" % num) / ("%s.txt" % num)
        work.parent.mkdir(parents=True, exist_ok=True)
        work.write_text("%s build %d\n" % (num, self.builds), encoding="utf-8")
        path = where / ticket
        path.write_text(re.sub(r"(?m)^Status: .*$", "Status: resolved", path.read_text(encoding="utf-8"), count=1),
                        encoding="utf-8")
        if extra:
            extra(where)
        if commit:
            self.git("add", "-A", cwd=where)
            self.git("commit", "-qm", "feat: %s" % num, cwd=where)

    def write_acceptance(self):
        path = self.dir / ACCEPT_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(accept_test(self.nums), encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-qm", "test(f): acceptance tests")

    # ---- a session, the way the skill drives one -------------------------

    def drive(self, verdict=lambda world, n: "fine\nREVIEW: PASS\n", limit=60, on_build=None, **env):
        """Answer every line the conductor hands out until DONE, STOP or an exit code other than 0:
        BUILD -> build and resolve (each ticket of a batch in turn), REVIEW -> the verdict, TEST -> acceptance
        tests, HANDOFF -> start again, WAIT -> finish the oldest pending lane work. Returns the last line."""
        pending = []
        rc, out = self.flow("next", **env)
        for _ in range(limit):
            if rc != 0 or not out:
                return out
            fields = out.split()
            word = fields[0]
            if word in ("DONE", "STOP", "PLAN", "NONE"):
                return out
            if word == "HANDOFF":
                rc, out = self.start(**env)
                if rc != 0:
                    return out
                rc, out = self.flow("next", **env)
                continue
            if word in ("BUILD", "REVIEW") and len(fields) >= 5:  # a lane's work: finish it later
                pending.append(fields)
                rc, out = self.flow("next", **env)
                continue
            if word == "WAIT":
                if not pending:
                    return out
                fields = pending.pop(0)
                lane = fields[4]
                self.flow("prompt", lane, **env)
                if fields[0] == "BUILD":
                    self.resolve(fields[1], where=self.lane_dir(lane), extra=on_build)
                else:
                    self.reviews += 1
                    reply = self.side_file("reply.txt", verdict(self, self.reviews))
                    self.flow("verdict", reply, lane, **env)
                rc, out = self.flow("next", lane, **env)
                continue
            if word == "BUILD":
                rc, prompt = self.flow("prompt", **env)
                batch = []
                if "This build is a batch of" in prompt:
                    rest = prompt.split("This build is a batch of", 1)[1].split(". Build them", 1)[0]
                    batch = [p for p in re.findall(r"`(plans/f/tasks/[^`]+\.md)`", rest) if p != fields[1]]
                for ticket in [fields[1]] + batch:
                    self.resolve(ticket, extra=on_build)
                rc, out = self.flow("next", **env)
                continue
            if word == "REVIEW":
                self.flow("prompt", **env)
                self.reviews += 1
                reply = self.side_file("reply.txt", verdict(self, self.reviews))
                self.flow("verdict", reply, **env)
                rc, out = self.flow("next", **env)
                continue
            if word == "TEST":
                self.flow("prompt", **env)
                self.write_acceptance()
                rc, out = self.flow("next", **env)
                continue
            return out
        return out

    # ---- what the run left -----------------------------------------------

    def snapshot(self):
        """What a user can see the run left: the state file's key=value lines (sorted, clock values masked), the
        log's events in order, the other state files, every file of the plan, and the commit subjects."""
        state_dir = self.dir / ".feature-flow" / "state"
        out = []
        state_file = state_dir / "flow-f.state"
        if state_file.is_file():
            lines = []
            for line in state_file.read_text(encoding="utf-8", errors="replace").splitlines():
                key, sep, value = line.partition("=")
                if any(word in key for word in ("seen", "spent", "clock", "slow", "time")):
                    value = "<T>"
                if key == "code_files" or key.endswith(".code_files"):
                    value = conductor_files_as_one(value)
                lines.append("%s%s%s" % (key, sep, value))
            out.append("state:\n" + self.norm("\n".join(sorted(lines))))
        log_file = state_dir / "flow-f.log"
        if log_file.is_file():
            events = [",".join(l.split(",")[1:]) for l in log_file.read_text(encoding="utf-8").splitlines()]
            out.append("log:\n" + self.norm("\n".join(events)))
        if state_dir.is_dir():
            for path in sorted(state_dir.rglob("*")):
                if path.is_file() and path not in (state_file, log_file):
                    out.append("%s:\n%s" % (path.relative_to(self.dir).as_posix(),
                                            self.norm(path.read_text(encoding="utf-8", errors="replace"))))
        for path in sorted((self.dir / "plans").rglob("*")):
            if path.is_file():
                out.append("%s:\n%s" % (path.relative_to(self.dir).as_posix(),
                                        self.norm(path.read_text(encoding="utf-8", errors="replace"))))
        if (self.dir / ".git").exists():
            out.append("commits on the branch:\n" + self.norm(self.git("log", "--first-parent", "--format=%s")))
            out.append("all commits:\n" + self.norm("\n".join(sorted(self.git("log", "--format=%s").splitlines()))))
        return out


def twins(test, scenario, **world_args):
    """Run scenario(world) on the old code and on the current code; assert that the calls print the same
    (normalised) lines with the same exit codes and leave the same files. Returns the current code's world."""
    try:
        old_dir, why = old_code(), ""
    except NoOldCode as err:
        old_dir, why = None, str(err)
    if why:
        test.fail(why)
    old = World(test, old_dir, **world_args)
    scenario(old)
    new = World(test, current_code(), **world_args)
    scenario(new)
    test.maxDiff = 20000
    test.assertEqual(new.lines, old.lines, "the CLI printed different lines on the current code than on the old")
    test.assertEqual(new.snapshot(), old.snapshot(), "the run left different files on the current code")
    return new
