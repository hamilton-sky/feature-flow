# Learnings: conductor-rebuild

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (01) A golden mismatch prints the scenario, the first differing line, its section (calls, log events, state keys) and a diff; run one scenario with `python3 -m unittest test_golden.Golden.test_lanes` from tests/py (about 4 s each, all 14 in about 35 s).
- (03) The system python3 has no `build` module: `python3 -m venv <scratch>/venv && <scratch>/venv/bin/pip install build`, then run `<scratch>/venv/bin/python tests/package_smoke.py` (prints `all passed`).
- (04) 3 tests in acceptance/test_rebuild_modes.py fail already at f10963b: twins compares state code_files, which list the package files instead of conductor.py. Check a failure there against the base commit (git worktree add --detach <scratch>/base <sha>) before chasing it.
- (05) Acceptance has 25 failures already at f9d716a (not just the 3 from 04): compare the failing test names with the base commit's, do not expect zero.
- (06) run.sh counts the whole unittest discovery as one passing line, so its total (466) does not grow when you add a test file; check your own file with the discover -p command.
- (07) The checks need only a small conductor fake (see tests/py/test_buildchecks.py `Handle`) plus `os.chdir` into a helpers.Repo with FLOW_* cleared: gate.py and floorguard.py read `plans/` relative to the working folder. `bash tests/run.sh` takes over 10 minutes here, so run it in the background.
- (08) To watch the state machine in process, patch `store.RunState.save` (every phase change is saved) and run `cli.main` with os.chdir into a helpers.Repo, as tests/py/test_phases.py `Session` does. A level 2 ticket gets one single review unless it has `Review: full`.
- (09) A full test set can error once with `git commit ... exit status 128` inside a fixture repo, and pass on an identical rerun; rerun once before chasing it.
- (10) `Merge` must never go through `hand_out`: tests/py/test_phases.py Session records every REGISTRY hand_out, and the lane walk expects only build and review. To test dispatch without worktrees, patch LaneScheduler.lease/integrate with autospec recorders (test_schedulers.LaneDispatch).
- (11) test_guards.py imports Run from test_schedulers; never import a TestCase class (e.g. LaneDispatch) into another test module's namespace: discovery would run its tests twice.
- (12) The Conductor is the main Workspace (subclass); a lane Workspace forwards missing names to it, so a per-ticket method put on Conductor instead of workspace.py silently reads the main view in a lane.
- (12) codehash.flow_code reads roles/guides relative to the working folder; in a lane call ws.flow_code() (hashes from the main top), never codehash.flow_code directly.
- (13) A cwd= test needs no chdir per call: chdir once into one helpers.Repo and pass cwd= the other (tests/py/test_cwd.py); status.run maps g.path back to relative paths when cwd is given.
- (13) A test that needs a floor-guard finding must not write a skip/noqa line itself (the guard flags the test file); edit another ticket in the throwaway repo and expect ticket-edit, as test_buildchecks.py does.
