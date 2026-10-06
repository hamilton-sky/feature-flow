"""A throwaway git repo with a four-ticket plan, like newrepo in tests/run.sh."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def ticket_text(title, status, blocked):
    return ("# %s\n\nType: task\nStatus: %s\nBlocked by: %s\nTest first: no\n\n\nbody\n\n"
            "## Done when\n\n- x\n\n## Answer\n" % (title, status, blocked))


class Repo:
    def __init__(self, tickets=(("01-a", "A", "—"), ("02-b", "B", "01"))):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "scripts").mkdir()
        for script in (ROOT / "scripts").glob("*.sh"):
            shutil.copy(script, self.dir / "scripts")
        shutil.copy(ROOT / "scripts" / "flow.py", self.dir / "scripts")
        shutil.copytree(ROOT / "feature_flow", self.dir / "feature_flow",
                        ignore=shutil.ignore_patterns("__pycache__"))
        tasks = self.dir / "plans" / "f" / "tasks"
        tasks.mkdir(parents=True)
        for slug, title, blocked in tickets:
            (tasks / ("%s.md" % slug)).write_text(ticket_text(title, "open", blocked))
        plan = self.dir / "plans" / "f"
        (plan / "map.md").write_text("# Map: f\n\n## Decisions so far\n\n<One line per resolved ticket.>\n")
        (plan / "learnings.md").write_text("# Learnings: f\n\n- (NN) <what you found>\n")
        (plan / "commands.md").write_text("# Commands: f\n\nBuild: `<command>`\nSmoke: `<the quickest command>`\n")
        (plan / "spec.md").write_text("# Spec\n")
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        self.commit("init")

    def close(self):
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
        full.update(env)
        result = subprocess.run([sys.executable, "scripts/flow.py", "f"] + list(args), cwd=str(self.dir),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                                env=full)
        return result.returncode, result.stdout.strip()

    def path(self, rel):
        return self.dir / rel

    def set_status(self, rel, status):
        path = self.path(rel)
        lines = path.read_text().splitlines(True)
        for i, line in enumerate(lines):
            if line.startswith("Status:"):
                lines[i] = "Status: %s\n" % status
                break
        path.write_text("".join(lines))

    def resolve(self, rel, message="feat: work"):
        name = Path(rel).stem
        self.path("work-%s.txt" % name).write_text("work\n")
        self.set_status(rel, "resolved")
        self.commit(message)

    def state(self):
        text = self.path(".git/flow-f.state").read_text()
        return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)

    def log(self):
        path = self.path(".git/flow-f.log")
        return path.read_text() if path.exists() else ""
