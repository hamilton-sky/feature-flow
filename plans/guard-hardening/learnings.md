# Learnings: guard-hardening

Append one line per lesson: `- (NN) what you found`. Never rewrite existing lines.
- (01) A new tests/py fixture that needs the installed layout: delete feature_flow/ and scripts/ from helpers.Repo, run install.py [--private] into it; use `git commit --allow-empty` since a private install adds nothing to commit.
- (02) lookbehind in floorguard regexes is fine now (no mawk); 'pytest.importorskip' is matched as a prefix, so don't use it as a look-alike.
