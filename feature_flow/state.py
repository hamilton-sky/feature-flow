"""The conductor's state and log, kept in .feature-flow/state/ at the top of the worktree.

Not under .git: a normal Codex session cannot write there, and an unattended Claude session is
refused there. The folder ignores itself (its .gitignore is `*`), so it never dirties the tree.
The state file is key=value lines. It is parsed as plain text, never run as code.
"""

import shutil
import time
from pathlib import Path

STATE_DIR = Path(".feature-flow") / "state"
KINDS = ("state", "log", "findings")


def state_dir(top):
    """The state folder under the worktree top, created with its ignore rule on first use."""
    path = Path(top) / STATE_DIR
    path.mkdir(parents=True, exist_ok=True)
    ignore = path / ".gitignore"
    if not ignore.is_file():
        ignore.write_text("*\n", encoding="utf-8")
    return path


def file_path(folder, feature, kind):
    return Path(folder) / ("flow-%s.%s" % (feature, kind))


def state_path(folder, feature):
    return file_path(folder, feature, "state")


def log_path(folder, feature):
    return file_path(folder, feature, "log")


def migrate(old_folder, new_folder, feature):
    """Carry a run an earlier version kept under .git into the new folder, owner included, so the
    owning session keeps its token. Only when the new folder has no state for the feature yet.
    The state file is copied last, so a half-done copy is retried. The old files are left alone."""
    if old_folder is None or state_path(new_folder, feature).is_file():
        return False
    if not state_path(old_folder, feature).is_file():
        return False
    for kind in reversed(KINDS):
        old = file_path(old_folder, feature, kind)
        if old.is_file():
            shutil.copyfile(str(old), str(file_path(new_folder, feature, kind)))
    return True


def load(path):
    data = {}
    path = Path(path)
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip():
            data[key.strip()] = value
    return data


def save(path, data):
    path = Path(path)
    lines = ["%s=%s" % (key, str(value).replace("\n", " ")) for key, value in data.items()]
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)


def log(path, num, event):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("%s,%s,%s\n" % (time.strftime("%H:%M:%S"), num or "-", event))
