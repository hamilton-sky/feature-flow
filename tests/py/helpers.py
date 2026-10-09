"""A throwaway git repo with a four-ticket plan, like newrepo in tests/run.sh."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def insert_after_line(data, marker, line):
    """data (bytes) with line added after the line holding marker, using the file's own line end."""
    start = data.index(marker)
    end = data.index(b"\n", start) + 1
    eol = b"\r\n" if data[end - 2:end] == b"\r\n" else b"\n"
    return data[:end] + line + eol + data[end:]


def run_loader(line, runner, args, cwd, env):
    """A skill's loader line run through the platform shell the way the gate runs commands, with
    python3 as this interpreter (the Windows CI job has `python`, not `python3`) and <S>/flow-trust.py
    as runner. Returns the finished process, output as text."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from feature_flow import gate  # the package under test, from this checkout

    if not line.startswith("python3 "):
        raise AssertionError("the loader line does not start with python3: %s" % line)
    cmd = '"%s"' % sys.executable + line[len("python3"):]
    cmd = cmd.replace("<S>/flow-trust.py", '"%s"' % runner) + " " + " ".join(args)
    argv, use_shell = gate.shell(cmd)
    return subprocess.run(argv, shell=use_shell, cwd=str(cwd), env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


def ticket_text(title, status, blocked):
    return ("# %s\n\nType: task\nStatus: %s\nBlocked by: %s\nTest first: no\n\n\nbody\n\n"
            "## Done when\n\n- x\n\n## Answer\n" % (title, status, blocked))


class Repo:
    def __init__(self, tickets=(("01-a", "A", "—"), ("02-b", "B", "01")), local=True):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.script = "scripts/flow.py"
        if local:
            (self.dir / "scripts").mkdir()
            shutil.copy(ROOT / "scripts" / "flow.py", self.dir / "scripts")
            shutil.copytree(ROOT / "feature_flow", self.dir / "feature_flow",
                            ignore=shutil.ignore_patterns("__pycache__"))
        tasks = self.dir / "plans" / "f" / "tasks"
        tasks.mkdir(parents=True)
        for slug, title, blocked in tickets:
            (tasks / ("%s.md" % slug)).write_text(ticket_text(title, "open", blocked), encoding="utf-8")
        plan = self.dir / "plans" / "f"
        (plan / "map.md").write_text("# Map: f\n\n## Decisions so far\n\n<One line per resolved ticket.>\n", encoding="utf-8")
        (plan / "learnings.md").write_text("# Learnings: f\n\n- (NN) <what you found>\n", encoding="utf-8")
        (plan / "commands.md").write_text("# Commands: f\n\nBuild: `<command>`\nSmoke: `<the quickest command>`\n", encoding="utf-8")
        (plan / "spec.md").write_text("# Spec\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        self.git("config", "gc.auto", "0")  # no background git while the folder is removed
        self.git("config", "maintenance.auto", "false")
        self.commit("init")

    def close(self):
        for attempt in range(5):  # a git process that is still finishing can refill .git/objects
            try:
                self.tmp.cleanup()
                return
            except OSError:
                time.sleep(0.2)
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git"] + list(args), cwd=str(self.dir), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, check=True).stdout.strip()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def head(self):
        return self.git("rev-parse", "HEAD")

    def porcelain(self):
        return self.git("status", "--porcelain")

    def flow(self, *args, **env):
        full = dict(os.environ)
        for key in list(full):
            if key.startswith("FLOW_"):
                del full[key]
        full["FLOW_TRUSTED"] = "1"
        full.update(env)
        result = subprocess.run([sys.executable, self.script, "f"] + list(args), cwd=str(self.dir),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                                env=full)
        return result.returncode, result.stdout.strip()

    def path(self, rel):
        return self.dir / rel

    def set_status(self, rel, status):
        path = self.path(rel)
        lines = path.read_text(encoding="utf-8").splitlines(True)
        for i, line in enumerate(lines):
            if line.startswith("Status:"):
                lines[i] = "Status: %s\n" % status
                break
        path.write_text("".join(lines), encoding="utf-8")

    def resolve(self, rel, message="feat: work"):
        name = Path(rel).stem
        self.path("work-%s.txt" % name).write_text("work\n", encoding="utf-8")
        self.set_status(rel, "resolved")
        self.commit(message)

    def state(self):
        text = self.path(".feature-flow/state/flow-f.state").read_text(encoding="utf-8")
        return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)

    def log(self):
        path = self.path(".feature-flow/state/flow-f.log")
        return path.read_text(encoding="utf-8") if path.exists() else ""
