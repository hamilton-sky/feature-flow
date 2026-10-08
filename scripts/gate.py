#!/usr/bin/env python3
"""The feature-flow gate. usage: python3 scripts/gate.py <feature>"""
import sys

if not (sys.flags.isolated or getattr(sys.flags, "safe_path", 0)):
    del sys.path[0]  # our own folder: nothing in scripts/ may shadow a module
sys.dont_write_bytecode = True  # never leave __pycache__ in the user's tree
import importlib.util
from pathlib import Path

here = Path(__file__).resolve().parent
for root in (here.parent, here.parent / ".feature-flow"):
    if (root / "feature_flow" / "__init__.py").is_file():
        break
else:
    sys.exit("feature_flow package not found beside %s" % here)
pkg = root / "feature_flow"  # loaded by path, so no folder joins sys.path
spec = importlib.util.spec_from_file_location(
    "feature_flow", pkg / "__init__.py", submodule_search_locations=[str(pkg)])
sys.modules["feature_flow"] = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sys.modules["feature_flow"])
from feature_flow.gate import main

sys.exit(main())
