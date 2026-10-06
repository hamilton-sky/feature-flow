#!/usr/bin/env python3
"""The feature-flow installer. usage: python3 install.py [target-repo] [--agent claude|codex|all] [--user] [--force] [--dry-run]"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never leave __pycache__ in the user's tree
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
from feature_flow.install import main

sys.exit(main(here))
