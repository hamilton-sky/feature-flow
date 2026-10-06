"""Build the package, install it in a fresh virtual environment and check the installed command.

usage: python tests/package_smoke.py [dist-dir]
With a dist dir (holding the wheel and the sdist `python -m build` made), uses those; else builds
them first, which needs the build module. Checks, in a throwaway folder:
  - the wheel and the sdist hold the bundled skills, roles, guides and scripts, and no tests or plans
  - `feature-flow --version` and `python -m feature_flow --version` print the version
  - `feature-flow install` puts the same files in a repo as `python install.py` from this checkout
  - the installed scripts/flow.py and the `feature-flow status` command both read a plan there
Network: pip installs the wheel with --no-deps --no-index, so nothing is downloaded.
"""

import filecmp
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from feature_flow import __version__  # noqa: E402

BUNDLED = [
    "feature_flow/_bundle/skills/feature-flow/SKILL.md",
    "feature_flow/_bundle/skills/architect-review/SKILL.md",
    "feature_flow/_bundle/skills/automation-design/SKILL.md",
    "feature_flow/_bundle/agents/ticket-builder.md",
    "feature_flow/_bundle/agents/ticket-reviewer.md",
    "feature_flow/_bundle/guides/build.md",
    "feature_flow/_bundle/guides/templates/ticket.md",
    "feature_flow/_bundle/adapters/codex/feature-flow/SKILL.md",
    "feature_flow/_bundle/scripts/flow.py",
    "feature_flow/_bundle/scripts/flow-view.html",
    "feature_flow/install.py",
    "feature_flow/command.py",
]
FAILED = []


def check(name, ok, detail=""):
    print("%s %s%s" % ("ok  " if ok else "FAIL", name, (": " + detail) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def run(args, cwd=None, env=None):
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, universal_newlines=True)
    return result.returncode, result.stdout


def tree(top):
    """Every file under top, as / paths, without byte-compiled files."""
    found = set()
    for d, _dirs, names in os.walk(top):
        for name in names:
            rel = os.path.relpath(os.path.join(d, name), top).replace(os.sep, "/")
            if "__pycache__" not in rel and not rel.endswith(".pyc"):
                found.add(rel)
    return found


def new_repo(path):
    path.mkdir(parents=True)
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        run(["git"] + args, cwd=path)
    tasks = path / "plans" / "f" / "tasks"
    tasks.mkdir(parents=True)
    (tasks / "01-a.md").write_text("# A\n\nType: task\nStatus: open\nBlocked by: —\nTest first: no\n\n"
                                   "body\n\n## Done when\n\n- x\n\n## Answer\n", encoding="utf-8")


def main(argv):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if argv:
            dist = Path(argv[0]).resolve()
        else:
            dist = tmp / "dist"
            code, out = run([sys.executable, "-m", "build", "--outdir", dist, ROOT])
            check("python -m build", code == 0, out[-2000:])
        wheels = sorted(dist.glob("*.whl"))
        sdists = sorted(dist.glob("*.tar.gz"))
        check("one wheel and one sdist were built", len(wheels) == 1 and len(sdists) == 1,
              "found %s" % sorted(p.name for p in dist.iterdir()))
        if FAILED:
            return 1
        wheel, sdist = wheels[0], sdists[0]

        names = set(zipfile.ZipFile(str(wheel)).namelist())
        missing = [n for n in BUNDLED if n not in names]
        check("the wheel bundles the skills, roles, guides and scripts", not missing, "missing %s" % missing)
        stray = sorted(n for n in names if n.startswith(("tests/", "plans/", "examples/")) or "/tests/" in n)
        check("the wheel holds no tests, plans or examples", not stray, "%s" % stray[:5])
        with tarfile.open(str(sdist)) as tar:
            members = [m.name.split("/", 1)[-1] for m in tar.getmembers()]
        need = ["skills/feature-flow/SKILL.md", "guides/build.md", "agents/ticket-builder.md",
                "adapters/codex/feature-flow/SKILL.md", "scripts/flow-view.html", "feature_flow/install.py"]
        missing = [n for n in need if n not in members]
        check("the sdist holds the files the wheel bundles", not missing, "missing %s" % missing)

        env_dir = tmp / "venv"
        venv.create(str(env_dir), with_pip=True)
        bindir = env_dir / ("Scripts" if os.name == "nt" else "bin")
        python = bindir / ("python.exe" if os.name == "nt" else "python")
        command = bindir / ("feature-flow.exe" if os.name == "nt" else "feature-flow")
        code, out = run([python, "-m", "pip", "install", "-q", "--no-deps", "--no-index", wheel])
        check("the wheel installs in a fresh virtual environment", code == 0, out)
        if FAILED:
            return 1

        # run from an empty folder, so nothing from this checkout is on the path
        work = tmp / "work"
        work.mkdir()
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        code, out = run([command, "--version"], cwd=work, env=env)
        check("feature-flow --version", code == 0 and out.strip() == "feature-flow " + __version__, out)
        code, out = run([python, "-m", "feature_flow", "--version"], cwd=work, env=env)
        check("python -m feature_flow --version", code == 0 and __version__ in out, out)
        code, out = run([python, "-c", "import feature_flow, os; print(os.path.dirname(feature_flow.__file__))"],
                        cwd=work, env=env)
        check("the package is imported from the virtual environment, not the checkout",
              code == 0 and str(ROOT) not in out and str(env_dir.resolve()) in str(Path(out.strip()).resolve()), out)

        from_pkg, from_checkout = tmp / "from-pkg", tmp / "from-checkout"
        new_repo(from_pkg)
        new_repo(from_checkout)
        code, out = run([command, "install", from_pkg, "--agent", "all"], cwd=work, env=env)
        check("feature-flow install --agent all", code == 0 and "added " in out, out)
        code, out = run([sys.executable, ROOT / "install.py", from_checkout, "--agent", "all"], cwd=work, env=env)
        check("python install.py --agent all (the checkout)", code == 0, out)

        a, b = tree(from_pkg), tree(from_checkout)
        check("both installs put the same files in place", a == b,
              "only from the package: %s; only from the checkout: %s" % (sorted(a - b)[:10], sorted(b - a)[:10]))
        differ = sorted(f for f in a & b if not filecmp.cmp(str(from_pkg / f), str(from_checkout / f), shallow=False))
        check("and the same bytes", not differ, "%s" % differ[:10])
        check("no _bundle folder is installed", not any("_bundle" in f for f in a))

        code, out = run([command, "install", from_pkg, "--agent", "all"], cwd=work, env=env)
        check("installing twice changes nothing", code == 0 and "added 0, updated 0" in out, out)

        code, out = run([sys.executable, "scripts/flow-status.py", "f", "--next"], cwd=from_pkg, env=env)
        check("the installed scripts/flow-status.py reads the plan", code == 0 and out.strip().endswith("01-a.md"), out)
        code, out = run([command, "status", "f", "--next"], cwd=from_pkg, env=env)
        check("feature-flow status reads the plan", code == 0 and out.strip().endswith("01-a.md"), out)
        page = tmp / "page.html"
        code, out = run([command, "view", "f", "--no-open", "--out", page], cwd=from_pkg, env=env)
        check("feature-flow view writes the page", code == 0 and page.is_file(), out)
        code, out = run([command, "nonsense"], cwd=work, env=env)
        check("an unknown command is a usage error", code == 2 and "usage:" in out, out)

    print("%d failed" % len(FAILED) if FAILED else "all passed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
