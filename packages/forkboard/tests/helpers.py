"""Shared by the tests: forkboard from this checkout, and the fixture documents."""

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
sys.path.insert(0, str(PACKAGE))


def fixture(name):
    """A fresh copy of tests/fixtures/<name>.json: csv (options, a Chosen line, unsafe text), sketch (live figures)."""
    return copy.deepcopy(json.loads((HERE / "fixtures" / (name + ".json")).read_text(encoding="utf-8")))
