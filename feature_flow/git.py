"""The few git calls the conductor needs, each one an argument list, never a shell string."""

import hashlib
import subprocess
from pathlib import Path


def _git(*args, check=True):
    result = subprocess.run(["git"] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True)
    if check and result.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), result.stderr.strip()))
    return result


def git_dir():
    result = _git("rev-parse", "--absolute-git-dir", check=False)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def toplevel():
    result = _git("rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip())


def head():
    return _git("rev-parse", "HEAD").stdout.strip()


# the installer's record of what it wrote: the paths, and the sha256 of each as it wrote it
INSTALLED = Path(".feature-flow") / "installed.txt"
HASHES = Path(".feature-flow") / "installed.sha256"


def _read_lines(path):
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []


def changes():
    """Every changed path, untracked files included, as `git status --porcelain` sees them, except
    feature-flow's own install: a file still exactly as the installer wrote it, an untracked file it
    lists (an install from before it kept hashes), and its two record files, which every install rewrites."""
    listed, hashes = set(), {}
    top = toplevel()
    if top is not None:
        listed = set(_read_lines(top / INSTALLED))
        for line in _read_lines(top / HASHES):
            digest, _, name = line.partition("  ")
            hashes[name] = digest
    entries = _git("status", "--porcelain", "-z", "-uall").stdout.split("\0")
    found = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if code[0] in "RC":
            i += 1  # the rename's source path follows
        if path in (INSTALLED.as_posix(), HASHES.as_posix()) or (code == "??" and path in listed):
            continue
        if path in hashes and top is not None and _sha256(top / path) == hashes[path]:
            continue
        found.append(path)
    return found


def _sha256(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def is_clean():
    return not changes()


def tracked_clean():
    """No change to a tracked file, in the worktree or the index."""
    return (_git("diff", "--quiet", check=False).returncode == 0
            and _git("diff", "--cached", "--quiet", check=False).returncode == 0)


def commit_file(path, message):
    if _git("add", "--", str(path), check=False).returncode != 0:
        return False
    return _git("commit", "-q", "-m", message, check=False).returncode == 0
