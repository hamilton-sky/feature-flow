"""The checks of a build as an ordered pipeline: the gate, the floor guard, the footprint, Done when and test first.

Each check's `run(c)` takes the conductor (for its paths, settings, state and log) and returns
(failure source, report, notes): source is None when it passes, and the notes are for the reviewer.
`run` stops at the first failure. `pipeline` picks the checks of a build as the conductor always has:
the gate only with the gate on (a batch leaves it out: its gate runs once at HEAD), Done when and test
first only with the gate on.
"""

from feature_flow import checks, git, lanes, proof, tickets
from feature_flow.conductor.errors import Stop
from feature_flow.conductor.store import NOTE_SEP


class Gate:
    def run(self, c):
        quick = c.gate_quick()
        result = checks.gate(c.scripts, c.feature, c.gate_timeout, quick=quick)
        c.log("GATE-QUICK" if quick else "GATE-FULL")
        c.log("GATE-PASS" if result.ok else "GATE-FAIL")
        if not result.ok:
            return "gate (quick)" if quick else "gate (full)", result.out, []
        return None, "", []


class FloorGuard:
    def run(self, c):
        result = checks.floor_guard(c.scripts, c.feature, c.get("num"), c.get("base"))
        c.log("GUARD-PASS" if result.ok else "GUARD-FAIL")
        if not result.ok:
            return "floor guard", result.out, []
        warnings = [l for l in result.out.splitlines() if l.startswith("warning:")]
        return None, "", warnings[:1]


class Footprint:
    """The paths the build changed outside the ticket's `Touches:` line (read at base), as a report for the
    builder. Passes when they are all inside it or the ticket has no such line."""

    def run(self, c):
        patterns = lanes.touches(c.ticket_at_base())
        if patterns is None:
            return None, "", []
        changed = git.diff_names(c.get("base"), "HEAD", c.plan.as_posix())
        outside = [p for p in changed if not tickets.matches_sensitive(p, patterns)]
        c.log("FOOTPRINT-FAIL" if outside else "FOOTPRINT-PASS")
        if not outside:
            return None, "", []
        return "footprint check", (
            "the build changed paths outside the ticket's `Touches:` line (%s): %s. tickets run side by side "
            "because their Touches do not overlap, so change only what Touches names. if the ticket cannot be done "
            "inside it, say so in the Answer and stop: the plan has to change, not the footprint"
            % (" ".join(patterns) or "empty", ", ".join(outside[:20]))), []


class DoneWhen:
    """Run the ticket's check block. Sets c.checks_ran, and the due_checks key when checks are deferred."""

    def run(self, c):
        try:
            found = proof.checks_in(c.ticket_at_base())
        except proof.ParseError as err:
            raise Stop("%s has a check block the conductor cannot read: %s" % (c.ticket_name(), err))
        c.checks_ran = bool(found)
        if not found:
            c.log("DONEWHEN-SKIP")
            return None, "", ["the conductor ran no Done when checks: the ticket has no check block"]
        deferred = []
        ok, report = proof.run_checks(found, c.gate_timeout, deferred)
        dirty = git.changes()
        if dirty:
            raise Stop("a Done when check of %s changed the working tree: %s. a check command must not change it"
                       % (c.ticket_name(), " ".join(dirty[:5])))
        c.log("DONEWHEN-PASS" if ok else "DONEWHEN-FAIL")
        if not ok:
            return "done when", report, []
        if not deferred:
            return None, "", ["the conductor ran %d Done when check(s) and all passed" % len(found)]
        c.log("DONEWHEN-DEFERRED %d" % len(deferred))
        c.st["due_checks"] = NOTE_SEP.join("deferred check, needs %s: `%s` (here: %s)" % (d.needs, d.command, got)
                                           for d, got in deferred)
        return None, "", [
            "the conductor ran %d Done when check(s): %d passed, and %d that need what this host lacks did "
            "not pass and are deferred, not met: %s. they go to the plan's followups.md. judge only what "
            "can be checked here, and do not count a deferred check as MET"
            % (len(found), len(found) - len(deferred), len(deferred),
               "; ".join("`%s` (needs %s)" % (d.command, d.needs) for d, _ in deferred))]


class TestFirst:
    """For a `Test first: yes` ticket, prove a test-only commit failed the Test command. The branch to go
    back to is saved under the restore key while HEAD is detached."""

    def run(self, c):
        if not proof.wants_test_first(c.ticket_at_base()):
            return None, "", []
        test = tickets.commands_value(c.commands, "Test")
        if not test:
            c.log("TESTFIRST-SKIP")
            return None, "", ["the conductor did not check test first: commands.md has no Test command"]

        def remember(value):
            c.st["restore"] = value
            c.save()
        try:
            ok, text = proof.test_first(c.get("base"), test, c.plan, c.gate_timeout, remember)
        except proof.GitError as err:
            raise Stop("test first check of %s: %s" % (c.ticket_name(), err))
        c.log("TESTFIRST-PASS" if ok else "TESTFIRST-FAIL")
        if not ok:
            return "test first", text, []
        return None, "", [text] if text else []


def pipeline(c, gate=True):
    """The checks of a build, in order. gate=False leaves the gate out, as a batch does."""
    found = [Gate()] if gate and c.gate_on else []
    found += [FloorGuard(), Footprint()]
    if c.gate_on:
        found += [DoneWhen(), TestFirst()]
    return found


def run(c, found):
    """Run the checks in order: (source, report, []) for the first one that fails, else
    (None, "", the notes for the reviewer)."""
    notes = []
    for check in found:
        source, report, more = check.run(c)
        if source:
            return source, report, []
        notes.extend(more)
    return None, "", notes
