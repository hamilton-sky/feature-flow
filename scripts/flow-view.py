#!/usr/bin/env python3
"""The graph page writer. usage: python3 scripts/flow-view.py <feature> [--watch] [--no-open] [--out FILE]"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never leave __pycache__ in the user's tree
here = Path(__file__).resolve().parent
for root in (here.parent, here.parent / ".feature-flow"):
    if (root / "feature_flow" / "__init__.py").is_file():
        sys.path.insert(0, str(root))
        break
from feature_flow.view import main

sys.exit(main())
