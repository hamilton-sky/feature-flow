"""Build Forkboard, install the wheel in a fresh virtual environment and run the installed command.

usage: python packages/forkboard/tests/package_smoke.py   (needs the build module)
Checks that the wheel carries the page's assets and themes, and that `forkboard` renders a page from them.
"""

import os
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def run(args, **kw):
    result = subprocess.run([str(a) for a in args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True, **kw)
    if result.returncode:
        sys.exit("failed: %s\n%s" % (" ".join(str(a) for a in args), result.stdout))
    return result.stdout


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        run([sys.executable, "-m", "build", "--outdir", tmp / "dist", PACKAGE])
        wheel = next((tmp / "dist").glob("*.whl"))
        names = set(zipfile.ZipFile(str(wheel)).namelist())
        need = ["forkboard/assets/editor.js", "forkboard/assets/live.js", "forkboard/themes/route.css", "forkboard/page.py"]
        missing = [n for n in need if n not in names]
        if missing or any(n.startswith("tests/") for n in names):
            sys.exit("the wheel is missing %s or holds tests" % missing)
        venv.create(str(tmp / "venv"), with_pip=True)
        bindir = tmp / "venv" / ("Scripts" if os.name == "nt" else "bin")
        run([bindir / ("python.exe" if os.name == "nt" else "python"), "-m", "pip", "install", "-q", "--no-deps",
             "--no-index", wheel])
        command = bindir / ("forkboard.exe" if os.name == "nt" else "forkboard")
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        print(run([command, "--version"], cwd=str(tmp), env=env).strip())
        out = tmp / "page.html"
        run([command, "render", PACKAGE / "tests" / "fixtures" / "csv.json", "--out", out], cwd=str(tmp), env=env)
        if 'class="dg graph"' not in out.read_text(encoding="utf-8"):
            sys.exit("the installed forkboard wrote a page without its editable diagram")
        print("all passed")


if __name__ == "__main__":
    main()
