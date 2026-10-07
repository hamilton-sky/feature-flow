"""The installer, ported from install.sh with the same report and exit codes.

usage: python3 install.py [target-repo] [--agent claude|codex|all] [--user] [--force] [--dry-run]
copies the feature-flow skill, its roles, scripts and guides into a repo so the flow works there.
a file that already exists and differs is kept and reported, unless --force is given or nobody
edited it since an earlier feature-flow install wrote it (then it is updated).
nothing is ever deleted. CLAUDE_HOME overrides ~/.claude and AGENTS_HOME overrides ~/.agents for --user.

Files are compared and written as bytes, and the two text transforms (the Codex skill header and
a role file without its frontmatter) follow the awk programs of the bash version line for line,
so the installed tree is the same byte for byte. Files are listed in byte order, as `sort` does
with LC_ALL=C.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys

from feature_flow.released import RELEASED

# the help text
USAGE = """\
usage: python3 install.py [target-repo] [--agent claude|codex|all] [--user] [--force] [--dry-run]
copies the feature-flow skill, its roles, scripts and guides into a repo so the flow works there.
  --agent claude (default)
    skills  go to <target>/.claude/skills/   (or ~/.claude/skills/ with --user)
    agents  go to <target>/.claude/agents/   (or ~/.claude/agents/ with --user)
  --agent codex: the Codex skill from adapters/codex/, the other skills with a Codex header
    skills  go to <target>/.agents/skills/   (or ~/.agents/skills/ with --user)
    roles   go to <target>/.agents/flow-roles/ (always: the skill reads them from the repo)
  --agent all does both.
  scripts go to <target>/scripts/ and guides, roles and the Python package to <target>/.feature-flow/
    (always: the skill and scripts/flow.py read them from the repo)
a file that already exists and differs is kept and reported, unless --force is given or it is
  still exactly what an earlier feature-flow install wrote (then it is updated).
nothing is ever deleted. CLAUDE_HOME overrides ~/.claude and AGENTS_HOME overrides ~/.agents for --user.
"""

# inside an installed package the skills, roles, guides and scripts sit in this folder of feature_flow
BUNDLE = "_bundle"

# the skills this installs
SKILLS = ("feature-flow", "architect-review", "automation-design")
# the in-repo files an install wrote, one path per line, relative to the target. The conductor does not
# count them as a dirty tree while they are untracked, and `git add --pathspec-from-file` commits them.
INSTALLED = ".feature-flow/installed.txt"
# the sha256 of each of those files as the install wrote it, `<sha256>  <path>` per line. A later install
# replaces a file that still has its recorded bytes: nobody edited it, so it is not the user's version.
HASHES = ".feature-flow/installed.sha256"
# the same record for a --user install, in ~/.claude and ~/.agents, paths relative to that folder
USER_HASHES = "feature-flow.sha256"


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


# an old skill that runs the ticket script (the bash one or the Python one) or ends a review with a verdict
LEFTOVER = re.compile(rb"scripts/flow-status\.(?:sh|py)|REVIEW: PASS")


class Usage(Exception):
    """A usage error: the message, and whether the help text follows it."""

    def __init__(self, message, help_too=False):
        Exception.__init__(self, message)
        self.help_too = help_too


def _lines(data):
    """The records awk reads: split on newlines, a last line without one still counts."""
    if not data:
        return []
    lines = data.split(b"\n")
    if data.endswith(b"\n"):
        lines.pop()
    return lines


def codex_header(data):
    """A Codex skill header holds only the name and a quoted description; the body is left as it is."""
    out = []
    fm = False
    for nr, line in enumerate(_lines(data), 1):
        if nr == 1 and line == b"---":
            fm = True
            out.append(line)
        elif fm and line == b"---":
            fm = False
            out.append(line)
        elif fm and line.startswith(b"name:"):
            out.append(line)
        elif fm and line.startswith(b"description:"):
            d = re.sub(rb"[ \t]+$", b"", re.sub(rb"^[ \t]+", b"", line[12:], count=1), count=1)
            e = d.replace(b"\\", b"\\\\").replace(b'"', b'\\"')
            out.append(b'description: "' + e + b'"')
        elif fm:
            continue
        else:
            out.append(line)
    return b"".join(line + b"\n" for line in out)


def role_body(data):
    """A role file without its frontmatter (and the blank lines after it), to go in front of a prompt."""
    out = []
    fm = skip = False
    for nr, line in enumerate(_lines(data), 1):
        if nr == 1 and line == b"---":
            fm = True
        elif fm and line == b"---":
            fm = False
            skip = True
        elif fm:
            continue
        elif skip and line == b"":
            continue
        else:
            skip = False
            out.append(line)
    return b"".join(line + b"\n" for line in out)


def _files(src, skip_python=True):
    """`find src -type f ! -name .DS_Store [! -name '*.pyc' ! -path '*/__pycache__/*'] | sort`."""
    found = []
    for top, _dirs, names in os.walk(src):
        rel = os.path.relpath(top, src).replace(os.sep, "/")
        prefix = src + "/" if rel == "." else src + "/" + rel + "/"
        for name in names:
            path = prefix + name
            if os.path.islink(path) or not os.path.isfile(path) or name == ".DS_Store":
                continue
            if skip_python and (name.endswith(".pyc") or "/__pycache__/" in path):
                continue
            found.append(path)
    return sorted(found, key=os.fsencode)


def source_root():
    """Where the skills, roles, guides and scripts are: the copy inside an installed package, else the checkout."""
    package = os.path.dirname(os.path.abspath(__file__))
    bundle = os.path.join(package, BUNDLE)
    return bundle if os.path.isdir(bundle) else os.path.dirname(package)


def _read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def _logical_cwd():
    """The directory bash's pwd prints: $PWD when it names the current directory, else the real one."""
    pwd = os.environ.get("PWD", "")
    try:
        if os.path.isabs(pwd) and os.path.samefile(pwd, "."):
            return os.path.normpath(pwd)
    except OSError:
        pass
    return os.getcwd()


class Installer:
    def __init__(self, here, target, agent, user_level, force, dry, out):
        self.here = here
        self.target = target
        self.agent = agent
        self.force = force
        self.dry = dry
        self.out = out
        if user_level:
            home = os.environ.get("HOME", "")
            self.claude_dir = os.environ.get("CLAUDE_HOME") or home + "/.claude"
            self.agents_dir = os.environ.get("AGENTS_HOME") or home + "/.agents"
        else:
            self.claude_dir = target + "/.claude"
            self.agents_dir = target + "/.agents"
        # the Python package: the checkout's, else (inside an installed package) this one
        package = here + "/feature_flow"
        if not os.path.isfile(package + "/__init__.py"):
            package = os.path.dirname(os.path.abspath(__file__))
        self.package = package
        self.added = self.updated = self.same = self.kept = 0
        self.written = {}
        # each folder this installs into, with its hash record; the target's own comes first
        self.records = [(target, HASHES)]
        if user_level and agent in ("claude", "all"):
            self.records.append((self.claude_dir, USER_HASHES))
        if user_level and agent in ("codex", "all"):
            self.records.append((self.agents_dir, USER_HASHES))
        self.recorded = dict((root, self._read_hashes(root + "/" + record)) for root, record in self.records)

    def place(self, file, dest, data=None):
        """One file: add it, replace it (--force), leave it alone (same) or keep the user's version.
        data is a transformed copy of file, written with mode 644."""
        new = _read(file) if data is None else data
        if not os.path.exists(dest):
            self.out("  add     " + dest)
            self.added += 1
            self.written[dest] = new
            if not self.dry:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                self._copy(file, dest, data)
        elif new is not None and _read(dest) == new:
            self.same += 1
            self.written[dest] = new
        elif self.force or self.untouched(dest):
            self.out("  update  " + dest)
            self.updated += 1
            self.written[dest] = new
            if not self.dry:
                self._copy(file, dest, data)
        else:
            self.out("  kept    " + dest + " (differs from this version, use --force to replace it)")
            self.kept += 1

    def locate(self, dest):
        """The install folder dest is in and dest relative to it, or (None, None)."""
        for root, _ in sorted(self.records, key=lambda r: -len(r[0])):
            if dest.startswith(root + "/"):
                return root, dest[len(root) + 1:]
        return None, None

    @staticmethod
    def _read_hashes(path):
        recorded = {}
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    digest, _, name = line.rstrip("\n").partition("  ")
                    if name:
                        recorded[name] = digest
        except (OSError, UnicodeDecodeError):
            pass
        return recorded

    def untouched(self, dest):
        """dest still holds the bytes an earlier feature-flow install wrote there. Never a symlink:
        writing through it would change the file it points to."""
        if os.path.islink(dest):
            return False
        old = _read(dest)
        if old is None:
            return False
        digest = _sha256(old)
        root, rel = self.locate(dest)
        return digest in RELEASED or self.recorded.get(root, {}).get(rel) == digest

    @staticmethod
    def _copy(file, dest, data):
        """cp -p: contents, mode and times."""
        if data is None:
            shutil.copy2(file, dest)
            return
        with open(dest, "wb") as f:
            f.write(data)
        os.chmod(dest, 0o644)

    def copy_tree(self, src, dest, skip=None):
        """Every file under src, except those under src/skip."""
        if not os.path.isdir(src):
            return
        for file in _files(src):
            rel = file[len(src) + 1:]
            if skip and rel.startswith(skip + "/"):
                continue
            self.place(file, dest + "/" + rel)

    def install_codex(self):
        here = self.here
        self.copy_tree(here + "/adapters/codex/feature-flow", self.agents_dir + "/skills/feature-flow")
        for name in SKILLS:
            if name == "feature-flow":
                continue
            skill = here + "/skills/" + name
            for file in _files(skill, skip_python=False) if os.path.isdir(skill) else []:
                if file == skill + "/SKILL.md":
                    data = _read(file)
                    self.place(file, self.agents_dir + "/skills/" + name + "/SKILL.md",
                               codex_header(data if data is not None else b""))
                else:
                    self.place(file, self.agents_dir + "/skills/" + name + "/" + file[len(skill) + 1:])
        agents = here + "/agents"
        names = sorted(os.listdir(agents), key=os.fsencode) if os.path.isdir(agents) else []
        for name in names:
            file = agents + "/" + name
            if name.startswith(".") or not name.endswith(".md") or not os.path.isfile(file):
                continue
            data = _read(file)
            self.place(file, self.target + "/.agents/flow-roles/" + name,
                       role_body(data if data is not None else b""))

    def write_installed(self):
        """Add this run's in-repo files to the list, and every file's hash to its folder's record, keeping
        the earlier runs' entries for files that still exist. True when the target's list or record changed."""
        names = set()
        try:
            with open(self.target + "/" + INSTALLED, encoding="utf-8") as old:
                names.update(line.strip() for line in old)
        except OSError:
            pass
        hashes = dict((root, dict(self.recorded[root])) for root, _ in self.records)
        for dest, data in self.written.items():
            root, rel = self.locate(dest)
            if root == self.target:
                names.add(rel)
            if root is not None and data is not None:
                hashes[root][rel] = _sha256(data)
        names.update((INSTALLED, HASHES))
        names = sorted(n for n in names
                       if n in (INSTALLED, HASHES) or (n and os.path.isfile(self.target + "/" + n)))
        changed = self._write(self.target + "/" + INSTALLED, "".join(n + "\n" for n in names))
        for root, record in self.records:
            kept = names if root == self.target else sorted(
                n for n in hashes[root] if os.path.isfile(root + "/" + n))
            text = "".join("%s  %s\n" % (hashes[root][n], n) for n in kept if n in hashes[root])
            if self._write(root + "/" + record, text) and root == self.target:
                changed = True
        return changed

    @staticmethod
    def _write(path, text):
        try:
            with open(path, encoding="utf-8", newline="") as f:
                if f.read() == text:
                    return False
        except (OSError, UnicodeDecodeError):
            pass
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return True

    def report_leftovers(self, dirs):
        """A skill folder this installer does not own but that drives the flow (it runs the ticket
        scripts or ends a review with a verdict) is left from an earlier version: named once, never deleted."""
        found = ""
        for d in dirs:
            names = sorted(os.listdir(d), key=os.fsencode) if os.path.isdir(d) else []
            for name in names:
                path = d + "/" + name + "/SKILL.md"
                if name.startswith(".") or not os.path.isfile(path) or name in SKILLS:
                    continue
                data = _read(path)
                if data is not None and LEFTOVER.search(data):
                    found += " " + name
        if found:
            self.out("note: left from an earlier feature-flow, no longer installed:" + found
                     + ". delete them, /feature-flow replaces them")

    def run(self):
        here, agent = self.here, self.agent
        if self.dry:
            self.out("dry run: nothing will be written")
        self.out("installing into " + self.target + ("" if agent == "claude" else " (%s)" % agent))
        left = []
        if agent in ("claude", "all"):
            for name in SKILLS:
                self.copy_tree(here + "/skills/" + name, self.claude_dir + "/skills/" + name)
            self.copy_tree(here + "/agents", self.claude_dir + "/agents")
            left.append(self.claude_dir + "/skills")
        if agent in ("codex", "all"):
            self.install_codex()
            left.append(self.agents_dir + "/skills")
        self.copy_tree(here + "/scripts", self.target + "/scripts")
        self.copy_tree(here + "/guides", self.target + "/.feature-flow/guides")
        self.copy_tree(here + "/agents", self.target + "/.feature-flow/agents")
        self.copy_tree(self.package, self.target + "/.feature-flow/feature_flow", skip=BUNDLE)
        listed = not self.dry and self.write_installed()

        self.out("")
        verb = "would add" if self.dry else "added"
        self.out("%s %d, updated %d, already current %d, kept %d"
                 % (verb, self.added, self.updated, self.same, self.kept))
        self.report_leftovers(left)

        if not self.dry:
            try:
                git = subprocess.run(["git", "-C", self.target, "rev-parse", "--git-dir"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
            except OSError:
                git = 127
            if git != 0:
                self.out("note: %s is not a git repository, and the flow needs one" % self.target)
            elif self.added or self.updated or listed:
                git_c = ""
                if os.path.realpath(self.target) != os.path.realpath(os.getcwd()):
                    git_c = '-C "%s" ' % self.target if " " in self.target else "-C %s " % self.target
                self.out('next: commit the installed files: git %sadd --pathspec-from-file=%s'
                         ' && git %scommit -m "chore: install feature-flow"' % (git_c, INSTALLED, git_c))
            if not shutil.which("python3"):
                self.out("note: install python3 (3.9 or later): scripts/flow.py needs it")
            if agent in ("claude", "all"):
                self.out("next: /feature-flow <feature-name> in Claude Code")
            if agent in ("codex", "all"):
                self.out("next: $feature-flow <feature-name> in Codex")
        return 0


def parse(argv):
    """The options, read in order like the bash case statement. Returns a dict, or None for --help."""
    opts = {"target": "", "agent": "claude", "user": False, "force": False, "dry": False}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--agent":
            if i + 1 >= len(argv):
                raise Usage("--agent needs a value: claude, codex or all", help_too=True)
            i += 1
            opts["agent"] = argv[i]
        elif a.startswith("--agent="):
            opts["agent"] = a[len("--agent="):]
        elif a == "--user":
            opts["user"] = True
        elif a == "--force":
            opts["force"] = True
        elif a == "--dry-run":
            opts["dry"] = True
        elif a in ("-h", "--help"):
            return None
        elif a.startswith("-"):
            raise Usage("unknown option: " + a, help_too=True)
        else:
            opts["target"] = a
        i += 1
    if opts["agent"] not in ("claude", "codex", "all"):
        raise Usage("unknown agent: %s (use claude, codex or all)" % opts["agent"])
    return opts


def run(argv, here, out, err):
    """Run the installer. out and err take one line of text each. Returns the exit code."""
    try:
        opts = parse(argv)
    except Usage as e:
        err(str(e))
        if e.help_too:
            err(USAGE[:-1])
        return 2
    if opts is None:
        out(USAGE[:-1])
        return 0
    target = opts["target"] or "."
    if not os.path.isdir(target):
        err("no such directory: " + target)
        return 2
    target = os.path.normpath(os.path.join(_logical_cwd(), target))
    installer = Installer(os.path.abspath(str(here)), target, opts["agent"], opts["user"],
                          opts["force"], opts["dry"], out)
    return installer.run()


def main(here, argv=None):
    """The command line: writes each line as bytes, flushed, so stdout and stderr keep their order."""
    argv = sys.argv[1:] if argv is None else argv

    def writer(stream):
        def write(line):
            stream.buffer.write(os.fsencode(line) + b"\n")
            stream.buffer.flush()
        return write

    sys.stdout.flush()
    try:
        return run(argv, here, writer(sys.stdout), writer(sys.stderr))
    except OSError as e:  # cp or mkdir failed: the bash installer stopped there too (set -e)
        writer(sys.stderr)("install.py: %s" % e)
        return 1
