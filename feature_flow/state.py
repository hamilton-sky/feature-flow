"""The conductor's state and log, kept under .git so the working tree stays clean.

The state file is key=value lines. It is parsed as plain text, never run as code.
"""

import time
from pathlib import Path


def state_path(git_dir, feature):
    return Path(git_dir) / ("flow-%s.state" % feature)


def log_path(git_dir, feature):
    return Path(git_dir) / ("flow-%s.log" % feature)


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
