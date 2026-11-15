"""Build Forkboard, install the wheel in a fresh virtual environment and run the installed command.

usage: python packages/forkboard/tests/package_smoke.py   (needs the build module)
Checks that the wheel carries the page's assets and themes, and that `forkboard` renders a page from them.
"""

import os
import json
import urllib.request
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
        need = ["forkboard/assets/editor.js", "forkboard/assets/live.js", "forkboard/assets/providers.js", "forkboard/server.py", "forkboard/storage.py", "forkboard/themes/route.css", "forkboard/page.py"]
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
        live_dir = tmp / "live"
        run([command, "live", PACKAGE / "tests" / "fixtures" / "csv.json", live_dir,
             "--provider", "local"], cwd=str(tmp), env=env)
        if "providers" not in (live_dir / "index.html").read_text(encoding="utf-8").lower():
            sys.exit("installed local page lacks its provider adapter")
        proc = subprocess.Popen([str(command), "serve", str(live_dir), "--port", "0"], cwd=str(tmp), env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        try:
            line = proc.stdout.readline()
            if not line.startswith("serving http://127.0.0.1:"):
                sys.exit("installed local server failed: " + line)
            url = line.split()[1]
            with urllib.request.urlopen(url + "state.json", timeout=5) as response:
                revision = response.headers["ETag"]
            request = urllib.request.Request(url + "api/change",
                data=json.dumps({"id": "installed-smoke", "change": {"ask": {"text": "Installed request?"}}}).encode(),
                headers={"Content-Type": "application/json", "Origin": url.rstrip("/"), "If-Match": revision})
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status != 200:
                    sys.exit("installed local request was not accepted")
            if "Installed request?" not in run([command, "asks", live_dir], cwd=str(tmp), env=env):
                sys.exit("installed asks did not find the local request")
            run([command, "answer", live_dir, "1", "Installed answer"], cwd=str(tmp), env=env)
        finally:
            proc.terminate()
            proc.wait(timeout=10)
        print("all passed")


if __name__ == "__main__":
    main()
