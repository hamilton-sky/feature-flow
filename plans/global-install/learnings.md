# Learnings: global-install

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (NN) <what you found, and what to do about it>
- (01) Tests use the temp target as the temp root, so a home folder under it shows up in `target.iterdir()`; check names, not emptiness. `bash tests/run.sh` takes ~2 min: run it in the background.
