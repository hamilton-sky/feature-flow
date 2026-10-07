"""The few git calls the conductor needs, each one an argument list, never a shell string."""

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


def is_clean():
    """No change at all, untracked files included, as `git status --porcelain` sees it."""
    return _git("status", "--porcelain").stdout.strip() == ""


def tracked_clean():
    """No change to a tracked file, in the worktree or the index."""
    return (_git("diff", "--quiet", check=False).returncode == 0
            and _git("diff", "--cached", "--quiet", check=False).returncode == 0)


def commit_file(path, message):
    if _git("add", "--", str(path), check=False).returncode != 0:
        return False
    return _git("commit", "-q", "-m", message, check=False).returncode == 0
