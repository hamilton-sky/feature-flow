#!/usr/bin/env python3
"""The ticket graph reader. usage: python3 scripts/flow-status.py <feature> [--next | --counts | --check | --mermaid [plain] | --json]"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never leave __pycache__ in the user's tree
here = Path(__file__).resolve().parent
for root in (here.parent, here.parent / ".feature-flow"):
    if (root / "feature_flow" / "__init__.py").is_file():
        sys.path.insert(0, str(root))
        break
from feature_flow.status import main

sys.exit(main())
