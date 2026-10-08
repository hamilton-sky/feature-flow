#!/usr/bin/env python3
"""The trusted check in front of every conductor call.

usage: FLOW_TRUST=<last TRUST digest | new> python3 -I scripts/flow-trust.py [--after-build <ticket> <sha>] <feature> <command> [args...]

It hashes the flow's own files (the conductor, its package, guides, roles, skills and the run
state), refuses to call the conductor when they differ from the digest the session passed in
FLOW_TRUST, runs the conductor, and prints `TRUST <digest>` for the session to pass next time.

It imports nothing from the repo, on purpose: it is the code that decides whether the flow's
files on disk were changed, so it must not run any of them. The skill's loader checks this
file's sha256 against the hash pinned in the skill and runs those same bytes with `exec`, so
nothing a subagent can write decides the check. Standard library only, Python 3.9+.
"""
import sys

if not (sys.flags.isolated or getattr(sys.flags, "safe_path", 0)):
    del sys.path[0]  # the script's folder (or the working folder for -c): nothing there may shadow a module
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

USAGE = ("usage: FLOW_TRUST=<last TRUST digest | new> python3 -I scripts/flow-trust.py "
         "[--after-build <ticket> <sha>] <feature> <command> [args...]")
NO_TRUST = "STOP pass FLOW_TRUST: the last TRUST digest, or new on this session's first call"
CHANGED = "STOP flow files changed since the last step: %s"
KILLED = "STOP the conductor was killed by signal %d"
SCRIPTS = ("flow.py", "flow-status.py", "gate.py", "floor-guard.py", "flow-view.py", "flow-trust.py")
GUIDES = ("build.md", "review.md", "review-quality.md", "plan.md", "plan-review.md", "debug.md")  # prompts.GUIDES + debug.md
ROLES = ("ticket-builder.md", "ticket-reviewer.md", "feature-planner.md", "plan-reviewer.md")  # prompts.ROLES
OWNED = (".feature-flow/feature_flow", ".feature-flow/guides", ".feature-flow/agents",
         ".claude/skills/feature-flow", ".agents/skills/feature-flow", ".agents/flow-roles")
STATE_DIR = Path(".feature-flow") / "state"
STATE_KINDS = ("state", "findings")


def started():
    """(the folder this file is in, its own arguments), for both ways it can be started:
    directly (`__file__` set) or as `exec` of its bytes by the skill's loader, where
    sys.argv is ['-c', <this file>, <pinned sha>, args...]."""
    if "__file__" in globals():
        return Path(__file__).resolve().parent, sys.argv[1:]
    return Path(sys.argv[1]).resolve().parent, sys.argv[3:]


def parse(args):
    """(feature, command, the conductor's other args), or None on a usage error.
    --after-build <ticket> <sha> is accepted and ignored for now."""
    if args[:1] == ["--after-build"]:
        if len(args) < 3:
            return None
        args = args[3:]
    if len(args) < 2:
        return None
    feature = args[0]
    if not feature or feature.startswith("-") or feature in (".", "..") or any(c in feature for c in "/\\:"):
        return None
    return feature, args[1], args[2:]


def toplevel():
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, universal_newlines=True)
    except OSError:
        out = None
    if out is not None and out.returncode == 0 and out.stdout.strip():
        return Path(out.stdout.strip()).resolve()
    return Path(os.getcwd()).resolve()


def home(variable, name):
    """$variable, else $HOME/name with an unset HOME read as empty, as the installer does."""
    return Path(os.environ.get(variable) or os.environ.get("HOME", "") + "/" + name).resolve()


def tree(folder, chain=frozenset()):
    """Every file under folder, skipping __pycache__/ and *.pyc. Linked folders are followed,
    since Python imports through them, and listed themselves so adding one changes the hash;
    one that loops back to a folder on its own path is listed but not entered again."""
    real = os.path.realpath(str(folder))
    if real in chain:
        return []
    try:
        names = sorted(os.listdir(str(folder)))
    except OSError:
        return []
    found = []
    for entry in names:
        path = folder / entry
        if path.is_symlink() and path.is_dir():
            found.append(path)
        if path.is_dir():
            if entry != "__pycache__":
                found += tree(path, chain | {real})
        elif not entry.endswith(".pyc"):
            found.append(path)
    return found


def code_files(here, top):
    """The flow's code files, as spec.md § Design "What is hashed" lists them (missing ones are skipped later)."""
    parent = here.parent
    found = [here / name for name in SCRIPTS] + tree(parent / "feature_flow")
    found += [parent / "guides" / name for name in GUIDES] + [parent / "agents" / name for name in ROLES]
    for rel in OWNED:
        found += tree(top / rel)
    found += [top / ".claude" / "agents" / name for name in ROLES]
    claude = home("CLAUDE_HOME", ".claude")
    found += tree(claude / "skills" / "feature-flow") + [claude / "agents" / name for name in ROLES]
    found += tree(home("AGENTS_HOME", ".agents") / "skills" / "feature-flow")
    found += tree(home("FEATURE_FLOW_HOME", ".feature-flow"))
    return [path for path in found if not under(path, top / STATE_DIR)]


def state_files(top, feature):
    return [top / STATE_DIR / ("flow-%s.%s" % (feature, kind)) for kind in STATE_KINDS]


def under(path, folder):
    try:
        path.relative_to(folder)
        return True
    except ValueError:
        return False


def name(path, top):
    """In-repo paths relative and POSIX, others absolute POSIX."""
    return path.relative_to(top).as_posix() if under(path, top) else path.as_posix()


def hash_files(paths, top):
    """{name: sha256 of the file} for the paths that are files; a linked folder hashes as
    the sha256 of `link <its real path>`."""
    each = {}
    for path in paths:
        if path.is_dir():
            target = "link " + os.path.realpath(str(path))
            each[name(path, top)] = hashlib.sha256(target.encode("utf-8", "surrogateescape")).hexdigest()
        elif path.is_file():
            try:
                each[name(path, top)] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                each[name(path, top)] = "unreadable"
    return each


def snapshot(here, top, feature):
    """(code {name: sha256}, state {name: sha256})."""
    return hash_files(code_files(here, top), top), hash_files(state_files(top, feature), top)


def part(each):
    whole = hashlib.sha256()
    for key in sorted(each):
        whole.update(key.encode("utf-8") + b"\0" + each[key].encode("ascii") + b"\0")
    return whole.hexdigest()[:16]


def digest(code, state):
    return "%s.%s" % (part(code), part(state))


def trust_path(top, feature):
    return top / STATE_DIR / ("flow-%s.trust" % feature)


def named_changes(top, feature, now):
    """The paths that differ from the per-file list the last call wrote. That list is untrusted:
    it only names paths once the digest has already decided to stop."""
    try:
        before = json.loads(trust_path(top, feature).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        before = None
    if not isinstance(before, dict):
        return "(no earlier list to name them)"
    names = sorted(key for key in set(before) | set(now) if before.get(key) != now.get(key))
    return ", ".join(names) if names else "(the earlier list names none of them)"


def write_list(top, feature, each):
    folder = top / STATE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    ignore = folder / ".gitignore"
    if not ignore.is_file():
        ignore.write_text("*\n", encoding="utf-8")
    trust_path(top, feature).write_text(json.dumps(each, sort_keys=True, indent=1) + "\n", encoding="utf-8")


def run_conductor(here, feature, command, rest):
    """Run flow.py isolated, with a fresh empty pycache_prefix so no planted .pyc is loaded."""
    cache = tempfile.mkdtemp(prefix="flow-trust-pycache-")
    try:
        args = [sys.executable, "-I", "-X", "pycache_prefix=" + cache, str(here / "flow.py"), feature, command] + rest
        return subprocess.run(args, env=dict(os.environ, FLOW_TRUSTED="1"),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        shutil.rmtree(cache, ignore_errors=True)


def split_report(err):
    """(stderr without the conductor's final `flow-state` line, that line or None)."""
    lines = err.splitlines(True)
    if lines and lines[-1].startswith(b"flow-state "):
        return b"".join(lines[:-1]), lines[-1].strip().decode("ascii", "replace")
    return err, None


def main():
    here, args = started()
    parsed = parse(args)
    if parsed is None:
        print(USAGE, file=sys.stderr)
        return 2
    feature, command, rest = parsed
    trust = os.environ.get("FLOW_TRUST", "")
    if not trust:
        print(NO_TRUST)
        return 1
    top = toplevel()
    if trust != "new":
        code, state = snapshot(here, top, feature)
        if digest(code, state) != trust:
            print(CHANGED % named_changes(top, feature, dict(code, **state)))
            return 1
    result = run_conductor(here, feature, command, rest)
    code, state = snapshot(here, top, feature)
    write_list(top, feature, dict(code, **state))
    err, _report = split_report(result.stderr)
    sys.stdout.write("TRUST %s\n" % digest(code, state))
    sys.stdout.flush()
    sys.stdout.buffer.write(result.stdout)
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(err)
    sys.stderr.buffer.flush()
    if result.returncode < 0:
        print(KILLED % -result.returncode)
        return 1
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
