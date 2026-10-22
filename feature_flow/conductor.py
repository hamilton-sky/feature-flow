"""The state machine that tells an interactive session what to do next.

It sets the limits, retries and review rounds. It judges every phase from the repo, never from the
caller, and prints exactly one line per command.
"""

import contextlib
import hashlib
import os
import re
import secrets
import shutil
from pathlib import Path

from feature_flow import checks, codehash, floorguard, gate, git, lanes, prompts, proof, state, suggest, tickets


NOTE_SEP = "\t"  # the state file keeps one line per key, so the review notes are tab separated
VERDICT = re.compile(r"^REVIEW: (PASS|FAIL)[ \t\r\f\v]*$")
OLD_OWNER = re.compile(r"^[0-9a-f]{16}$")  # a raw token, stored by a run started before 0.5.0
LEVEL_LINE = re.compile(r"^LEVEL: ([123])[ \t\r\f\v]*$")  # a reviewer raising the ticket's level
FINDING = re.compile(r"^[ \t]*[0-9]+\.[ \t]+(blocker|major|minor)\b", re.IGNORECASE)
CONVERT = re.compile(r"^Type:[ \t]*convert\b", re.IGNORECASE | re.MULTILINE)
LEVEL_NAMES = {1: "light", 2: "standard", 3: "boundary"}
FULL_ROUNDS = 2  # a level 2 ticket's rounds in which a major finding still sends it back
MAX_LANES = 4


def followups_only(findings):
    """True when a FAIL reply's only reasons are major or minor findings: no blocker, no NOT MET bullet,
    no missing test first and no scope problem. Such a level 2 ticket may pass with follow-ups."""
    severities = []
    for line in findings.splitlines():
        match = FINDING.match(line)
        if match:
            severities.append(match.group(1).lower())
        if "NOT MET" in line or re.match(r"^[ \t]*-[ \t]*test first:[ \t]*MISSING", line, re.IGNORECASE):
            return False
        scope = re.match(r"^[ \t]*-[ \t]*scope:[ \t]*(.*)$", line, re.IGNORECASE)
        if scope and scope.group(1).strip().upper() != "OK":
            return False
    return bool(severities) and "blocker" not in severities


def owner_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Stop(Exception):
    """A problem the session must report. Printed as `STOP <reason>`, exit 1."""


class NoPhase(Exception):
    """`prompt` or `verdict` with nothing for it pending: nothing changes, exit 2."""


def _env_int(name, default):
    value = os.environ.get(name, "")
    try:
        return int(value) if value.strip() else default
    except ValueError:
        raise Stop("%s must be a whole number, not %s" % (name, value))


class Conductor:
    def __init__(self, feature, scripts):
        self.feature = feature
        self.scripts = Path(scripts)
        self.root = Path(os.environ.get("FLOW_DIR") or "plans")
        self.plan = self.root / feature
        self.commands = self.plan / "commands.md"
        self.max_retries = _env_int("FLOW_MAX_RETRIES", 2)
        self.max_rounds = _env_int("FLOW_MAX_REVIEW_ROUNDS", 3)
        self.gate_timeout = _env_int("FLOW_GATE_TIMEOUT", 30)
        self.gate_on = os.environ.get("FLOW_GATE", "on") != "off"
        self.per_session = _env_int("FLOW_TICKETS_PER_SESSION", 4)
        self.small_files = _env_int("FLOW_SMALL_FILES", 3)
        self.small_lines = _env_int("FLOW_SMALL_LINES", 60)
        self.checks_ran = False
        self.relay = os.environ.get("FLOW_RELAY", "0") == "1"
        self.invoke = os.environ.get("FLOW_INVOKE") or "/feature-flow"
        top = git.toplevel()
        if top is None:
            raise Stop("not inside a git worktree")
        self.top = top.resolve()
        self.lane = 0  # the lane whose ticket the per-ticket code works on, 0 outside lanes
        try:
            folder = state.state_dir(top)
            state.migrate(git.git_dir(), folder, feature)
        except OSError as err:
            raise Stop("cannot write the flow state in %s: %s. this session must be allowed to write there"
                       % (top / state.STATE_DIR, err.strerror or err))
        self.draft_root = state.STATE_DIR / "draft"
        self.draft = self.draft_root / feature
        self.brief_file = state.STATE_DIR / ("brief-%s.md" % feature)
        self.state_file = state.state_path(folder, feature)
        self.log_file = state.log_path(folder, feature)
        self.findings_file = state.file_path(folder, feature, "findings")
        state.read_bytes(self.findings_file, "findings")  # so a call that never touches it still reports it
        try:
            self.st = state.load(self.state_file, "state")
        except UnicodeDecodeError:
            raise Stop("the state file %s is damaged: it is not UTF-8 text" % self.state_file)
        self.all = self.st  # the whole run state; self.st is one lane's view of it while a lane works

    # ---- small helpers -------------------------------------------------

    def get(self, key, default=""):
        return self.st.get(key, default)

    def num(self, key):
        try:
            return int(self.st.get(key, "0") or 0)
        except ValueError:
            raise Stop("the state file %s is damaged: %s is not a number" % (self.state_file, key))

    def save(self):
        state.save(self.state_file, self.all, "state")

    def log(self, event):
        state.log(self.log_file, self.get("num"), event)

    def emit(self, line):
        self.log(line.split(" ", 1)[0])
        return line

    def ticket(self):
        return self.get("ticket")

    def ticket_name(self):
        return tickets.name(self.ticket())

    # ---- the checks ----------------------------------------------------

    def smoke_command(self):
        cmd = os.environ.get("FLOW_SMOKE", "")
        if not cmd:
            cmd = tickets.commands_value(self.commands, "Smoke")
        return "" if cmd.startswith("<") else cmd

    def run_smoke(self):
        cmd = self.smoke_command()
        if not cmd:
            return
        result = checks.smoke(cmd, self.gate_timeout)
        if not result.ok:
            log = self.state_file.with_name("%s.smoke.log" % self.feature)
            text = result.out
            if result.timed_out:
                text += "\nsmoke test timed out after %d minutes\n" % self.gate_timeout
            log.write_text(gate.tail(text), encoding="utf-8")
            raise Stop("smoke test %s before %s: the base is already broken. fix it first. command: %s. "
                       "the last %d lines are in %s"
                       % ("timed out after %d minutes" % self.gate_timeout if result.timed_out else "failed",
                          self.ticket_name(), cmd, gate.TAIL, log))

    def gate_quick(self):
        """True when this ticket's gate may run Quick in place of Test."""
        if os.environ.get("FLOW_GATE_FULL") == "1":
            return False
        if not tickets.commands_value(self.commands, "Quick"):
            return False
        if self.per_session > 0 and self.num("session_done") + 1 >= self.per_session:
            return False
        counts = {}
        for word in checks.flow_status(self.scripts, self.feature, "--counts").out.split():
            key, _, value = word.partition("=")
            if value.isdigit():
                counts[key] = int(value)
        return sum(counts.get(k, 0) for k in ("open", "claimed", "waiting", "unknown")) > 0

    def run_limit(self):
        result = checks.flow_status(self.scripts, self.feature, "--counts")
        total = 0
        for word in result.out.split():
            if word.startswith("total="):
                total = int(word[len("total="):])
        return total * 3 * self.max_retries * (self.max_rounds + 1) + 1

    def count_run(self):
        runs = self.num("runs") + 1
        limit = self.num("limit")
        if runs > limit:
            raise Stop("run limit of %d phases reached, stopping" % limit)
        self.st["runs"] = runs

    # ---- phases --------------------------------------------------------

    def hand_out_build(self):
        self.count_run()
        self.st["phase"] = "build"
        self.st["attempt"] = self.num("attempt") + 1
        self.st["relay_handoff"] = "1" if self.relay else ""
        self.save()
        return self.emit("BUILD %s %s %s%s" % (self.ticket(), self.get("num"), self.get("base"), self.lane_word()))

    def hand_out_review(self):
        self.count_run()
        self.st["phase"] = "review"
        self.st["review_pass"] = self.get("review_pass") or "spec"
        self.st["review_attempt"] = self.num("review_attempt") + 1
        self.st["review_sha"] = git.head()
        self.st["relay_handoff"] = "1" if self.relay else ""
        self.save()
        return self.emit("REVIEW %s %s %s%s" % (self.ticket(), self.get("num"), self.get("base"), self.lane_word()))

    def round_cap(self):
        """The send-back rounds this ticket may have: 1 at level 1, else FLOW_MAX_REVIEW_ROUNDS."""
        return min(1, self.max_rounds) if self.num("level") == 1 else self.max_rounds

    def send_back(self, source, findings):
        """Write the findings into the ticket, reopen it, commit, and build again."""
        round_no = self.num("round") + 1
        cap = self.round_cap()
        if round_no > cap:
            level = self.num("level")
            raise Stop("%s still fails the %s after %d round(s)%s" % (
                self.ticket_name(), source, cap,
                " at level %d. the user decides what happens next" % level if level else ""))
        self.st["round"] = round_no
        tickets.append_findings(self.ticket(), round_no, source, findings)
        tickets.set_open(self.ticket())
        if not git.commit_file(self.ticket(), "chore(%s): %s review findings, round %d"
                               % (self.feature, self.get("num"), round_no)):
            raise Stop("cannot commit the %s findings to %s. this session must be allowed to run git commit"
                       % (source, self.ticket_name()))
        self.st["attempt"] = 0
        self.st["review_attempt"] = 0
        self.st["review_pass"] = "spec"
        return self.hand_out_build()

    def pass_ticket(self):
        if self.lane:  # counted once its merge lands; None tells lane_next to merge it
            self.st["phase"] = "merge"
            self.save()
            return None
        self.st["phase"] = ""
        self.st["done"] = self.num("done") + 1
        self.st["session_done"] = self.num("session_done") + 1
        self.save()
        return self.pick_ticket()

    def pass_with_followups(self, source, findings):
        """A level 2 ticket past its full rounds whose review found no blocker: append the findings to the
        plan's followups.md, commit it, and pass the ticket."""
        path = self.plan / "followups.md"
        found = [line.strip() for line in findings.splitlines() if FINDING.match(line)]
        text = "" if path.is_file() else (
            "# Follow-ups: %s\n\nFindings a level 2 ticket passed with after %d review rounds. Each is a candidate "
            "for a cleanup ticket.\n" % (self.feature, FULL_ROUNDS))
        text += "\n## %s (round %d, %s)\n\n%s\n" % (self.ticket_name(), self.num("round") + 1, source,
                                                    "\n".join("- " + line for line in found))
        with open(str(path), "a", encoding="utf-8") as handle:
            handle.write(text)
        if not git.commit_file(path, "chore(%s): %s follow-ups from the %s" % (self.feature, self.get("num"), source)):
            raise Stop("cannot commit %s. this session must be allowed to run git commit" % path.as_posix())
        self.st["followups"] = self.num("followups") + 1
        self.log("PASS-FOLLOWUPS")
        return self.pass_ticket()

    # ---- the fast path: reviews deferred to one review of the whole feature --

    def fast(self):
        return self.all.get("fast") == "1"

    def deferred(self):
        """[(NN, base)] of the tickets that passed their checks in fast mode without a review of their own."""
        return [tuple(item.split(":", 1)) for item in self.all.get("deferred", "").split() if ":" in item]

    def defer_review(self):
        """Fast mode: the ticket passed the gate, the floor guard and its checks, so it passes now and the
        feature review at the end covers it."""
        items = [i for i in self.all.get("deferred", "").split() if not i.startswith(self.get("num") + ":")]
        self.all["deferred"] = " ".join(items + ["%s:%s" % (self.get("num"), self.get("base"))])
        self.log("REVIEW-DEFERRED")
        return self.pass_ticket()

    def feature_base(self):
        """The oldest base of the deferred tickets: the feature review covers from there to HEAD."""
        bases = sorted({base for _, base in self.deferred()})
        if len(bases) == 1:
            return bases[0]
        result = git._git("merge-base", "--octopus", *bases, check=False)
        if result.returncode != 0 or not result.stdout.strip():
            raise Stop("cannot find where the deferred tickets started: %s" % result.stderr.strip())
        return result.stdout.strip()

    def hand_out_final(self, retry=False):
        """Every ticket is resolved but some skipped their own review: review the whole feature once."""
        self.count_run()
        self.all["phase"] = "final"
        self.all["final_base"] = self.feature_base()
        self.snapshot_code()  # what check_code holds the feature review to; with lanes, no ticket's snapshot is here
        self.all["review_attempt"] = (self.num("review_attempt") if retry else 0) + 1  # not the last ticket's count
        self.all["review_sha"] = git.head()
        self.all["verdict"] = ""
        self.save()
        return self.emit("REVIEW %s all %s" % (self.plan.as_posix(), self.all["final_base"]))

    def judge_final(self):
        self.check_code()
        if not git.tracked_clean() or git.head() != self.all.get("review_sha"):
            raise Stop("the reviewer changed tracked files, which a reviewer must never do")
        verdict = self.all.get("verdict", "")
        self.all["verdict"] = ""
        if verdict == "pass":
            for key in ("phase", "deferred", "final_base", "final_round", "review_attempt", "review_sha"):
                self.all[key] = ""
            self.save()
            self.log("FEATURE-PASS")
            return self.dispatch() if self.num("lanes") > 1 else self.pick_ticket()
        if verdict == "fail":
            round_no = self.num("final_round") + 1
            if round_no > self.max_rounds:
                raise Stop("the feature review of %s still fails after %d round(s). the user decides what happens next"
                           % (self.feature, self.max_rounds))
            path = self.fix_ticket(round_no, state.read_text(self.findings_file, "findings") or "")
            if not git.commit_file(path, "chore(%s): fixes from the feature review, round %d" % (self.feature, round_no)):
                raise Stop("cannot commit %s. this session must be allowed to run git commit" % path.as_posix())
            self.all.update({"phase": "", "final_round": round_no, "review_attempt": 0, "review_sha": ""})
            self.save()
            self.log("FEATURE-FAIL")
            return self.dispatch() if self.num("lanes") > 1 else self.pick_ticket()
        if self.num("review_attempt") >= self.max_retries:
            raise Stop("no verdict from the feature review of %s after %d attempt(s)" % (self.feature, self.max_retries))
        return self.hand_out_final(retry=True)

    def fix_ticket(self, round_no, findings):
        """Write the feature review's findings as a new open ticket, numbered after the last one."""
        folder = self.plan / (os.environ.get("FLOW_TICKETS") or "tasks")
        nums = [int(tickets.number(p)) for p in tickets.ticket_files(str(folder)) if tickets.number(p).isdigit()]
        num = "%02d" % (max(nums or [0]) + 1)
        path = folder / ("%s-feature-review-fixes-%d.md" % (num, round_no))
        quoted = "\n".join("> " + line if line else ">" for line in findings.strip("\n").splitlines()) or "> (none)"
        path.write_text(
            "# Fix the findings of the feature review, round %d\n\n"
            "Type: task\nStatus: open\nBlocked by: —\nTest first: no\nLevel: 2\n"
            "Check: none the feature review that follows checks these fixes\n\n"
            "The review of the whole feature (from commit %s) failed. Fix each finding below that is a blocker or a "
            "major, in the files it names. A minor is optional. If a finding is wrong, say why in the Answer instead.\n\n"
            "## Not in this ticket\n\n- Anything the findings do not name.\n\n"
            "## Done when\n\n- Every blocker and major finding below is fixed, or the Answer says why it stays.\n"
            "- commands.md's Test command passes.\n\n"
            "## Findings\n\n%s\n\n## Answer\n" % (round_no, self.all.get("final_base", ""), quoted),
            encoding="utf-8")
        return path

    def fast_switch(self, value):
        """`fast on|off` between phases: from the next ticket on, level 1 and 2 tickets skip or get their own
        review. Tickets already deferred keep the feature review at the end."""
        self.check_owner()
        if value not in ("on", "off"):
            raise Stop("fast takes on or off, not %s" % value)
        self.all["fast"] = "1" if value == "on" else ""
        self.save()
        self.log("FAST-%s" % value.upper())
        return "OK fast %s%s" % (value, "" if value == "on" or not self.deferred() else
                                 ". %d ticket(s) already deferred still get the feature review at the end"
                                 % len(self.deferred()))

    def pick_ticket(self):
        """Hand out the next ready ticket, or finish."""
        check = checks.flow_status(self.scripts, self.feature, "--check")
        if not check.ok:
            raise Stop("ticket check failed, fix the tickets first")
        dirty = git.changes()
        if dirty:
            raise Stop("working tree is not clean, commit or stash first: %s%s"
                       % (" ".join(dirty[:5]), " and %d more" % (len(dirty) - 5) if len(dirty) > 5 else ""))
        nxt = checks.flow_status(self.scripts, self.feature, "--next")
        if nxt.code == 10:
            if self.deferred():
                return self.hand_out_final()
            done = self.num("done")
            followups = self.num("followups")
            self.st["phase"] = ""
            self.st["owner"] = ""
            self.save()
            return self.emit("DONE %s is complete: %d ticket(s) resolved in this run%s" % (
                self.feature, done, "; %d passed with follow-ups in %s" % (followups, (self.plan / "followups.md").as_posix())
                if followups else ""))
        if nxt.code == 11:
            raise Stop("stuck: unfinished tickets remain but none is ready. run: python3 scripts/flow-status.py %s"
                       % self.feature)
        if nxt.code != 0:
            raise Stop("flow-status.py failed with exit code %d" % nxt.code)
        if self.per_session > 0 and self.num("session_done") >= self.per_session:
            return self.handoff()
        self.start_ticket(nxt.out.strip().splitlines()[-1])
        return self.hand_out_build()

    def start_ticket(self, path):
        """Fresh per-ticket state for the ticket at path, based at HEAD, then the smoke test."""
        self.st["limit"] = self.run_limit()
        self.st.update({"ticket": path, "num": tickets.number(path), "base": git.head(), "phase": "",
                        "attempt": 0, "review_attempt": 0, "round": 0, "review_sha": "", "review_notes": "", "review_pass": "spec",
                        "spec_ok": "", "level_note": ""})
        self.st["level"] = self.base_level()
        self.snapshot_code()
        self.run_smoke()

    def snapshot_code(self):
        whole, each = codehash.flow_code(self.scripts)
        self.st["code_sha"] = whole
        self.st["code_files"] = codehash.dump(each)

    def check_code(self, allowed=False):
        """Stop when the files the conductor runs from changed since the ticket was picked."""
        whole, each = codehash.flow_code(self.scripts)
        if whole == self.get("code_sha"):
            return
        if allowed:
            self.snapshot_code()
            return
        names = codehash.changed(codehash.load(self.get("code_files")), each)
        raise Stop("flow code changed while building %s: %s. if intended, the ticket needs a line: "
                   "Floor: allow flow-edit" % (self.ticket_name(), ", ".join(names)))

    def flow_edit_allowed(self):
        try:
            source = git._git("show", "%s:%s" % (self.get("base"), Path(self.ticket()).as_posix()), check=False)
        except OSError:
            return False
        if source.returncode != 0:
            return False
        return "flow-edit" in floorguard.allow_line(source.stdout).split()

    def judge_build(self):
        self.check_code(self.flow_edit_allowed())
        status = tickets.status(self.ticket())
        if status not in tickets.DONE:
            if status in tickets.RESET:
                tickets.set_open(self.ticket())
            if self.num("attempt") >= self.max_retries:
                raise Stop("%s is still unresolved after %d attempt(s)" % (self.ticket_name(), self.max_retries))
            return self.hand_out_build()
        if not git.is_clean():
            raise Stop("working tree is dirty after %s, it should have been committed" % self.ticket_name())
        if self.gate_on:
            quick = self.gate_quick()
            result = checks.gate(self.scripts, self.feature, self.gate_timeout, quick=quick)
            self.log("GATE-QUICK" if quick else "GATE-FULL")
            self.log("GATE-PASS" if result.ok else "GATE-FAIL")
            if not result.ok:
                return self.send_back("gate (quick)" if quick else "gate (full)", result.out)
        result = checks.floor_guard(self.scripts, self.feature, self.get("num"), self.get("base"))
        self.log("GUARD-PASS" if result.ok else "GUARD-FAIL")
        if not result.ok:
            return self.send_back("floor guard", result.out)
        warnings = [l for l in result.out.splitlines() if l.startswith("warning:")]
        report = self.footprint_report()
        if report:
            return self.send_back("footprint check", report)
        notes = warnings[:1]
        if self.gate_on:
            report, note = self.run_done_when()
            if report is not None:
                return self.send_back("done when", report)
            notes.append(note)
            report, note = self.run_test_first()
            if report is not None:
                return self.send_back("test first", report)
            if note:
                notes.append(note)
        level = self.measure_level()
        if self.fast() and level < 3:
            return self.defer_review()
        self.st["review_pass"] = "spec"
        if level == 0:
            if self.gate_on and self.checks_ran:
                small = self.small_note()
                if small:
                    self.st["review_pass"] = "single"
                    self.log("REVIEW-SMALL")
                    notes.append(small)
        else:
            notes.append(self.get("level_note"))
            if level < 3:
                self.st["review_pass"] = "single"
                self.log("REVIEW-SINGLE")
                notes.append("one review covers the spec and quality passes: do the spec checklist first")
        if self.st["review_pass"] == "spec" and self.get("spec_ok"):
            self.st["review_pass"] = "quality"
            notes.append("the spec review passed in an earlier round, so this round has the quality review only")
        if level == 2 and self.num("round") >= FULL_ROUNDS:
            notes.append("this is round %d: from now on only a blocker finding sends the ticket back. majors and "
                         "minors go to the plan's followups.md and the ticket passes" % (self.num("round") + 1))
        self.st["review_notes"] = NOTE_SEP.join(notes)
        return self.hand_out_review()

    def footprint_report(self):
        """The paths the build changed outside the ticket's `Touches:` line (read at base), as a report for the
        builder, or "" when they are all inside it or the ticket has no such line."""
        patterns = lanes.touches(self.ticket_at_base())
        if patterns is None:
            return ""
        changed = git.diff_names(self.get("base"), "HEAD", self.plan.as_posix())
        outside = [p for p in changed if not tickets.matches_sensitive(p, patterns)]
        self.log("FOOTPRINT-FAIL" if outside else "FOOTPRINT-PASS")
        if not outside:
            return ""
        return ("the build changed paths outside the ticket's `Touches:` line (%s): %s. tickets run side by side "
                "because their Touches do not overlap, so change only what Touches names. if the ticket cannot be done "
                "inside it, say so in the Answer and stop: the plan has to change, not the footprint"
                % (" ".join(patterns) or "empty", ", ".join(outside[:20])))

    def base_level(self):
        """The level known before the build, from the ticket at base: its `Level:` line, raised to 3 by
        `Review: full`, `Type: convert` or `Floor: allow flow-edit`. 0 when none of these is there."""
        text = self.ticket_at_base()
        level = proof.declared_level(text)
        why = ""
        if level < 3:
            if proof.review_mode(text) == "full":
                why = "the ticket says Review: full"
            elif CONVERT.search(text.split("\n## ", 1)[0]):
                why = "the ticket is Type: convert"
            elif self.flow_edit_allowed():
                why = "the ticket edits the flow's own code (Floor: allow flow-edit)"
        if why:
            level = 3
        self.st["level_note"] = self.describe_level(level, why) if level else ""
        return level

    def describe_level(self, level, why=""):
        return "this ticket is level %d (%s)%s" % (level, LEVEL_NAMES[level], ", raised because " + why if why else "")

    def commands_at_base(self):
        """commands.md as it was at the base commit, or "" when it was not there."""
        rel = proof.repo_relative(self.commands)
        try:
            return git.show_text("%s:%s" % (self.get("base"), rel))
        except RuntimeError:
            return ""

    def measure_level(self):
        """Raise the ticket's level from the built diff, never lower it: a path on commands.md's
        `Sensitive:` line makes it 3, and a level 1 diff over the small limits makes it 2."""
        level = self.num("level")
        why = ""
        patterns = tickets.sensitive_patterns(self.commands_at_base())
        if patterns and level < 3:
            hit = [p for p in git.diff_names(self.get("base"), "HEAD", self.plan.as_posix())
                   if tickets.matches_sensitive(p, patterns)]
            if hit:
                level, why = 3, "the diff touches a Sensitive path in commands.md: %s" % ", ".join(hit[:3])
        if level == 1:
            files, lines, binary = git.diff_size(self.get("base"), "HEAD", self.plan.as_posix())
            if binary or files > self.small_files or lines > self.small_lines:
                level, why = 2, "the diff (%d files, %d lines%s) is over the small limits" % (
                    files, lines, ", a binary file" if binary else "")
        if why:
            self.st["level_note"] = self.describe_level(level, why)
        self.st["level"] = level
        if level:
            self.log("LEVEL-%d" % level)
        return level

    def small_note(self):
        """The note for the reviewer when the built diff is small enough for one review, else ""."""
        base = self.ticket_at_base()
        if proof.review_mode(base) != "auto" or self.small_lines <= 0:
            return ""
        if CONVERT.search(base.split("\n## ", 1)[0]):
            return ""
        files, lines, binary = git.diff_size(self.get("base"), "HEAD", self.plan.as_posix())
        if binary or files > self.small_files or lines > self.small_lines:
            return ""
        return ("the conductor judged this ticket small (%d files, %d lines): one review covers the spec and "
                "quality passes" % (files, lines))

    def ticket_at_base(self):
        """The ticket text as it was at the base commit, so a builder cannot change what is checked."""
        rel = proof.repo_relative(self.ticket())
        listed = git._git("ls-tree", "--name-only", self.get("base"), "--", rel, check=False)
        if listed.returncode != 0:
            raise Stop("cannot read %s at the base commit: %s" % (rel, listed.stderr.strip()))
        if listed.stdout.strip():
            return git.show_text("%s:%s" % (self.get("base"), rel))
        text = Path(self.ticket()).read_text(encoding="utf-8")
        return text.split("\n## Answer", 1)[0]

    def run_done_when(self):
        """Run the ticket's check block. Returns (failure report or None, note for the reviewer)."""
        try:
            found = proof.checks_in(self.ticket_at_base())
        except proof.ParseError as err:
            raise Stop("%s has a check block the conductor cannot read: %s" % (self.ticket_name(), err))
        self.checks_ran = bool(found)
        if not found:
            self.log("DONEWHEN-SKIP")
            return None, "the conductor ran no Done when checks: the ticket has no check block"
        ok, report = proof.run_checks(found, self.gate_timeout)
        dirty = git.changes()
        if dirty:
            raise Stop("a Done when check of %s changed the working tree: %s. a check command must not change it"
                       % (self.ticket_name(), " ".join(dirty[:5])))
        self.log("DONEWHEN-PASS" if ok else "DONEWHEN-FAIL")
        if not ok:
            return report, ""
        return None, "the conductor ran %d Done when check(s) and all passed" % len(found)

    def run_test_first(self):
        """For a `Test first: yes` ticket, prove a test-only commit failed the Test command.
        Returns (failure report or None, note for the reviewer or "")."""
        if not proof.wants_test_first(self.ticket_at_base()):
            return None, ""
        test = tickets.commands_value(self.commands, "Test")
        if not test:
            self.log("TESTFIRST-SKIP")
            return None, "the conductor did not check test first: commands.md has no Test command"

        def remember(value):
            self.st["restore"] = value
            self.save()
        try:
            ok, text = proof.test_first(self.get("base"), test, self.plan, self.gate_timeout, remember)
        except proof.GitError as err:
            raise Stop("test first check of %s: %s" % (self.ticket_name(), err))
        self.log("TESTFIRST-PASS" if ok else "TESTFIRST-FAIL")
        return (None, text) if ok else (text, "")

    # ---- commands ------------------------------------------------------

    def handoff(self):
        """Release the owner; the user continues in a new session with the printed line."""
        self.st["owner"] = ""
        self.st["relay_handoff"] = ""
        self.save()
        return self.emit("HANDOFF %s %s" % (self.invoke, self.feature))

    def check_owner(self):
        """While a session owns the feature, every call must carry its token. Checked before any change."""
        owner = self.get("owner")
        token = os.environ.get("FLOW_SESSION", "")
        if not owner or owner_hash(token) == owner:
            return
        if OLD_OWNER.match(owner) and token == owner:
            self.st["owner"] = owner_hash(token)  # stored as the hash on the next save
            return
        raise Stop("%s is owned by another session (%s). pass its token as FLOW_SESSION, or start this session "
                   "with FLOW_TAKEOVER=1 once you are sure the other one is closed" % (self.feature, owner[:8]))

    def start(self):
        if not self.plan.is_dir():
            return self.emit("PLAN")
        owner = self.get("owner")
        takeover = bool(owner)
        if owner and os.environ.get("FLOW_TAKEOVER", "0") != "1":
            raise Stop("%s is owned by session %s. if that session is closed or dead, run start with FLOW_TAKEOVER=1"
                       % (self.feature, owner[:8]))
        wanted = _env_int("FLOW_LANES", 1)
        if not 1 <= wanted <= MAX_LANES:
            raise Stop("FLOW_LANES must be 1 to %d, not %d" % (MAX_LANES, wanted))
        if wanted > 1 and self.relay:
            raise Stop("FLOW_RELAY hands off after every phase, which lanes cannot do. drop one of them")
        if wanted > 1 and Path.cwd().resolve() != self.top:
            raise Stop("run the conductor from the top of the repo (%s) to use lanes" % self.top)
        busy = self.busy_lanes()
        if busy and wanted != self.num("lanes"):
            raise Stop("lane(s) %s still hold tickets from the last session, which ran with FLOW_LANES=%d. start with "
                       "that, or reset to drop them" % (",".join(map(str, busy)), self.num("lanes")))
        token = secrets.token_hex(8)
        self.st["owner"] = owner_hash(token)
        self.st["session_done"] = 0
        self.st["lanes"] = wanted if wanted > 1 else ""
        fast = os.environ.get("FLOW_FAST", "")
        if fast not in ("", "0", "1"):
            raise Stop("FLOW_FAST must be 1 or 0, not %s" % fast)
        if fast:
            self.st["fast"] = "1" if fast == "1" else ""
        self.save()
        self.log("TAKEOVER" if takeover else "START")
        return "OK %s" % token

    def next(self, lane=None):
        self.check_owner()
        if self.all.get("phase") == "final":
            if lane is not None:
                raise Stop("next %s: the feature review has no lane. run next without one" % lane)
            if not self.plan.is_dir():
                raise Stop("no plan folder %s" % self.plan)
            return self.judge_final()
        if self.num("lanes") > 1:
            return self.lane_next(lane)
        if lane is not None:
            raise Stop("next %s: this run has no lanes (start it with FLOW_LANES=2 or more for lanes)" % lane)
        if self.get("restore"):
            try:
                git._git("checkout", "-q", self.get("restore"))
            except RuntimeError as err:
                raise Stop("cannot put the working copy back after the test first check: %s. run `git checkout %s` "
                           "by hand" % (err, self.get("restore")))
            self.st["restore"] = ""
            self.save()
        if not self.plan.is_dir():
            raise Stop("no plan folder %s" % self.plan)
        if self.get("relay_handoff") == "1":
            return self.handoff()
        if "limit" not in self.st:
            self.st["limit"] = self.run_limit()
            self.st.setdefault("runs", 0)
            self.st.setdefault("done", 0)
        phase = self.get("phase")
        if phase == "build":
            return self.judge_build()
        if phase == "review":
            return self.judge_review()
        return self.pick_ticket()

    def reset(self, num=None):
        """Put the feature back to a clean start: reopen a half-built ticket (or ticket num), commit that,
        and forget the run. The tickets stay the truth; only the conductor's note and counters go."""
        if not self.plan.is_dir():
            hint = suggest.hint(self.feature, suggest.features(self.root)).strip()
            raise Stop("no plan folder %s%s" % (self.plan, ". " + hint if hint else ""))
        owner = self.get("owner")
        if owner and os.environ.get("FLOW_TAKEOVER", "0") != "1":
            raise Stop("%s is owned by session %s. if that session is closed or dead, run reset with FLOW_TAKEOVER=1"
                       % (self.feature, owner[:8]))
        paths = tickets.ticket_files(str(self.plan / (os.environ.get("FLOW_TICKETS") or "tasks")))
        if num is not None:
            chosen = [p for p in paths if tickets.number(p) == num.zfill(2)]
            if not chosen:
                raise Stop("no ticket %s in %s" % (num, self.plan))
        else:
            chosen = [p for p in paths if tickets.status(p) in tickets.RESET]
        reopened = []
        for path in chosen:
            if tickets.status(path) != "open":
                tickets.set_open(path)
                reopened.append(path)
        if reopened:
            nums = ", ".join(tickets.number(p) for p in reopened)
            if not git.commit_paths(reopened, "chore(%s): reset %s to open" % (self.feature, nums)):
                raise Stop("reopened %s but could not commit it. this session must be allowed to run git commit"
                           % nums)
        dropped = self.drop_lanes()
        had_run = self.state_file.is_file()
        for path, kind in ((self.state_file, "state"), (self.findings_file, "findings")):
            state.remove(path, kind)
        if not reopened and not had_run and not dropped:
            return "OK nothing to reset for %s. run %s %s" % (self.feature, self.invoke, self.feature)
        self.st = self.all = {}
        self.log("RESET")
        done = ["cleared the run state"] if had_run else []
        done += dropped
        done += ["reopened %s" % tickets.name(p) for p in reopened]
        return "OK %s. run %s %s" % (", ".join(done), self.invoke, self.feature)

    def judge_review(self):
        self.check_code()
        if not git.tracked_clean() or git.head() != self.get("review_sha"):
            raise Stop("the reviewer changed tracked files, which a reviewer must never do")
        verdict = self.get("verdict")
        self.st["verdict"] = ""
        review_pass = self.get("review_pass", "spec")
        raised = review_pass == "single" and self.num("level") == 3  # a reviewer raised it in this pass
        if verdict == "pass" and (review_pass == "spec" or raised):
            self.st["review_pass"] = "quality"
            self.st["review_attempt"] = 0
            self.st["spec_ok"] = "1"
            return self.hand_out_review()
        if verdict == "pass":
            return self.pass_ticket()
        if verdict == "fail":
            if self.lane and self.get("findings_for") != str(self.lane):
                raise Stop("the review findings on file are not lane %d's: run verdict for this lane, then next %d"
                           % (self.lane, self.lane))
            findings = state.read_text(self.findings_file, "findings") or ""
            source = {"quality": "quality review", "single": "single review"}.get(review_pass, "spec review")
            if (self.num("level") == 2 and self.num("round") >= FULL_ROUNDS and review_pass != "spec"
                    and followups_only(findings)):
                return self.pass_with_followups(source, findings)
            return self.send_back(source, findings)
        if self.num("review_attempt") >= self.max_retries:
            raise Stop("no review verdict for %s after %d attempt(s)" % (self.ticket_name(), self.max_retries))
        return self.hand_out_review()

    def prompt(self, lane=None):
        """The full prompt for the BUILD or REVIEW that `next` handed out. Exit 2 (NoPhase) when none is."""
        self.check_owner()
        if self.all.get("phase") == "final":
            if lane is not None:
                raise Stop("prompt %s: the feature review has no lane. run prompt without one" % lane)
            return self.final_prompt()
        if self.num("lanes") > 1 or lane is not None:
            with self.in_lane(self.lane_number(lane, "prompt")):
                return self.prompt_text()
        return self.prompt_text()

    def prompt_text(self):
        phase = self.get("phase")
        if phase not in ("build", "review"):
            raise NoPhase("no BUILD or REVIEW is pending for %s" % self.feature)
        try:
            if phase == "review" and self.get("review_pass") in ("quality", "single"):
                phase = "review-" + self.get("review_pass")
            return prompts.build(phase, self.scripts, self.feature, self.ticket(), self.get("num"), self.get("base"),
                                 [n for n in self.get("review_notes").split(NOTE_SEP) if n] if phase != "build" else (),
                                 retry=self.num("round") > 0,
                                 workdir=(str(Path.cwd()), lanes.branch(self.feature, self.get("num"))) if self.lane else None)
        except FileNotFoundError as err:
            raise Stop(str(err))

    def final_prompt(self):
        nums = [num for num, _ in self.deferred()]
        try:
            return prompts.feature_review(self.scripts, self.feature, self.plan.as_posix(), self.all["final_base"], nums,
                                          [n for n in [self.final_note()] if n])
        except FileNotFoundError as err:
            raise Stop(str(err))

    def final_note(self):
        round_no = self.num("final_round")
        if not round_no:
            return ""
        return ("this is round %d of the feature review: the last round's findings are in the newest "
                "feature-review-fixes ticket. check that each blocker and major is fixed" % (round_no + 1))

    def verdict(self, reply, lane=None):
        """Record the reviewer's reply. Exit 2 (NoPhase) unless a review is pending."""
        self.check_owner()
        reply = Path(reply).resolve()
        if self.all.get("phase") == "final":
            if lane is not None:
                raise Stop("verdict for lane %s: the feature review has no lane. run verdict without one" % lane)
            self.all["findings_for"] = ""
            return self.record_verdict(reply)
        if self.num("lanes") > 1 or lane is not None:
            k = self.lane_number(lane, "verdict")
            with self.in_lane(k):
                line = self.record_verdict(reply)
            self.all["findings_for"] = str(k)
            self.save()
            return line
        return self.record_verdict(reply)

    def record_verdict(self, reply):
        if self.get("phase") not in ("review", "final"):
            raise NoPhase("no review is pending for %s" % self.feature)
        try:
            text = Path(reply).read_text(encoding="utf-8", errors="replace")
        except OSError as err:
            raise Stop("cannot read the review reply %s: %s" % (reply, err.strerror))
        found = ""
        asked = 0
        for line in text.splitlines():
            match = VERDICT.match(line)
            if match:
                found = match.group(1).lower()
            match = LEVEL_LINE.match(line)
            if match:
                asked = max(asked, int(match.group(1)))
        level = self.num("level")
        if self.get("phase") == "final":
            asked = 0  # the feature review has no ticket level to raise
        if asked > (level or 2):  # a ticket without a Level line already gets level 2 reviews or more
            self.st["level"] = asked
            self.st["level_note"] = self.describe_level(asked, "a reviewer raised it")
            notes = [n for n in self.get("review_notes").split(NOTE_SEP) if n and not n.startswith("this ticket is level")]
            self.st["review_notes"] = NOTE_SEP.join([self.st["level_note"]] + notes)
            self.log("LEVEL-RAISE")
        if found == "fail":
            state.write_text(self.findings_file, "\n".join(text.splitlines()[:120]) + "\n", "findings")
        self.st["verdict"] = found or "none"
        self.save()
        self.log("VERDICT-%s" % (found or "none").upper())
        return "OK" if found else "RETRY no review verdict"


    # ---- lanes: tickets side by side in their own worktrees ---------------

    def lane_word(self):
        return " %d" % self.lane if self.lane else ""

    def lane_dir(self, lane):
        return lanes.lane_path(self.top, self.feature, lane)

    def lane_number(self, lane, command):
        if lane is None:
            raise Stop("%s needs the lane: this run has %d lanes. pass the lane from the BUILD or REVIEW line"
                       % (command, self.num("lanes")))
        if not lane.isdigit() or not 1 <= int(lane) <= self.num("lanes"):
            raise Stop("no lane %s: this run has lanes 1 to %d" % (lane, self.num("lanes")))
        return int(lane)

    def lane_key(self, lane, key):
        return self.all.get("L%d.%s" % (lane, key), "")

    def busy_lanes(self):
        """The lanes that hold a ticket: built, in review, or passed and waiting for their merge."""
        return [k for k in range(1, MAX_LANES + 1) if self.lane_key(k, "phase") in ("build", "review", "merge")]

    @contextlib.contextmanager
    def in_lane(self, lane):
        """Run the per-ticket code on lane's state, in its worktree, and come back to the top of the repo."""
        path = self.lane_dir(lane)
        if not lanes.is_worktree(self.top, path):
            raise Stop("lane %d (%s) is gone. run reset to drop the lanes and start again" % (lane, path))
        saved = self.st, self.lane
        self.st, self.lane = lanes.Scoped(self.all, lane), lane
        prompts.REPO = str(self.top)  # the guides and roles stay the main worktree's, never the lane's copies
        os.chdir(str(path))
        try:
            yield
        finally:
            os.chdir(str(self.top))
            prompts.REPO = "."
            self.st, self.lane = saved

    def lane_next(self, lane):
        """`next` with lanes. With a lane: judge the phase that lane just finished. Then, or without a lane,
        merge what passed, lease ready tickets to free lanes, and hand out the next phase."""
        if self.relay:
            raise Stop("FLOW_RELAY hands off after every phase, which lanes cannot do. drop one of them")
        if not self.plan.is_dir():
            raise Stop("no plan folder %s" % self.plan)
        if "limit" not in self.all:
            self.all["limit"] = self.run_limit()
            self.all.setdefault("runs", 0)
            self.all.setdefault("done", 0)
        if lane is None:
            return self.dispatch()
        k = self.lane_number(lane, "next")
        line = None
        with self.in_lane(k):
            if self.get("restore"):
                try:
                    git._git("checkout", "-q", self.get("restore"))
                except RuntimeError as err:
                    raise Stop("cannot put lane %d back after the test first check: %s. run `git checkout %s` in %s "
                               "by hand" % (k, err, self.get("restore"), Path.cwd()))
                self.st["restore"] = ""
                self.save()
            phase = self.get("phase")
            if phase in ("build", "review"):
                name = lanes.branch(self.feature, self.get("num"))
                on = git._git("symbolic-ref", "-q", "--short", "HEAD", check=False).stdout.strip()
                if on != name:
                    raise Stop("lane %d is on %s, not on its ticket's branch %s. a builder or reviewer must not switch "
                               "it. run reset to drop the lanes" % (k, on or "a detached HEAD", name))
            if phase == "build":
                line = self.judge_build()
            elif phase == "review":
                line = self.judge_review()
        return line if line is not None else self.dispatch()

    def dispatch(self):
        """Merge a passed ticket, else lease the next ticket that may run beside the busy ones, else say what to
        wait for, hand off, or finish."""
        for k in self.busy_lanes():
            if self.lane_key(k, "phase") == "merge":
                return self.integrate(k)
        dirty = git.changes()
        if dirty:
            raise Stop("the main worktree is not clean, and only merges may change it while lanes run: %s"
                       % " ".join(dirty[:5]))
        busy = self.busy_lanes()
        check = checks.flow_status(self.scripts, self.feature, "--check")
        if not check.ok:
            raise Stop("ticket check failed, fix the tickets first")
        ready = checks.flow_status(self.scripts, self.feature, "--ready")
        if ready.code not in (0, 10, 11):
            raise Stop("flow-status.py failed with exit code %d" % ready.code)
        if self.per_session > 0 and self.num("session_done") + len(busy) >= self.per_session:
            return self.emit("WAIT %s" % ",".join(map(str, busy))) if busy else self.handoff()
        leased = {self.lane_key(k, "ticket") for k in busy}
        running = [self.footprint(self.lane_key(k, "ticket")) for k in busy]
        shared = lanes.touches("Touches: " + tickets.commands_text_value(self.show_head(self.commands), "Shared")) or []
        free = [k for k in range(1, self.num("lanes") + 1) if k not in busy]
        if ready.code == 0 and free:
            for path in ready.out.strip().splitlines():
                if path in leased:
                    continue
                if lanes.side_by_side(self.footprint(path), running, shared):
                    return self.lease(free[0], path)
        if busy:
            return self.emit("WAIT %s" % ",".join(map(str, busy)))
        if ready.code == 10:
            return self.finish()
        raise Stop("stuck: unfinished tickets remain but none is ready. run: python3 scripts/flow-status.py %s"
                   % self.feature)

    def show_head(self, path):
        """path's text at HEAD of the main worktree, or "" when it is not there."""
        try:
            return git.show_text("HEAD:%s" % Path(path).as_posix())
        except RuntimeError:
            return ""

    def footprint(self, path):
        """(Touches patterns or None, level) of the ticket at path, read at HEAD of the main worktree: what
        decides whether it may run beside another. The level is raised to 3 as base_level raises it."""
        text = self.show_head(path)
        level = proof.declared_level(text)
        floor = floorguard.allow_line(text).split()
        if proof.review_mode(text) == "full" or CONVERT.search(text.split("\n## ", 1)[0]) or "flow-edit" in floor:
            level = 3
        return lanes.touches(text), level

    def lease(self, k, path):
        """Give the ticket at path to lane k on a fresh branch from the feature head, and hand out its build."""
        head = git.head()
        self.make_worktree(self.lane_dir(k), "lane-%d" % k)
        with self.in_lane(k):
            self.st.clear()
            dirty = git.changes()
            if dirty:
                raise Stop("lane %d is not clean: %s. run reset to drop the lanes" % (k, " ".join(dirty[:5])))
            try:
                lanes.git_in(".", "checkout", "-q", "-B", lanes.branch(self.feature, tickets.number(path)), head)
            except RuntimeError as err:
                raise Stop("cannot put lane %d on a branch for %s: %s" % (k, tickets.name(path), err))
            self.start_ticket(path)
            self.log("LEASE-%d" % k)
            return self.hand_out_build()

    def make_worktree(self, path, name):
        """Create the worktree at path when it is not there, and run commands.md's Setup in it once."""
        try:
            lanes.ensure(self.top, path)
        except RuntimeError as err:
            raise Stop("cannot create the %s worktree: %s" % (name, err))
        marker = path.with_name(path.name + ".ready")
        if marker.is_file():
            return
        cmd = tickets.commands_value(self.commands, "Setup")
        if cmd:
            os.chdir(str(path))
            try:
                result = checks.smoke(cmd, self.gate_timeout)
            finally:
                os.chdir(str(self.top))
            if not result.ok:
                raise Stop("Setup failed in the %s worktree (%s): %s. the last lines: %s"
                           % (name, path, cmd, " ".join(gate.tail(result.out, 5).split())[:300]))
        marker.write_text("set up\n", encoding="utf-8")

    def integrate(self, k):
        """Merge lane k's passed ticket into the feature head in the integration worktree, gate the merge, and
        fast-forward the feature branch to it. A conflict or a red gate rebuilds the ticket on the new head."""
        head = git.head()
        num, path = self.lane_key(k, "num"), self.lane_key(k, "ticket")
        name = lanes.branch(self.feature, num)
        if str(self.lane_key(k, "level")) == "3" and self.lane_key(k, "base") != head:
            return self.refresh(k, head)
        where = lanes.integrate_path(self.top, self.feature)
        self.make_worktree(where, "integration")
        os.chdir(str(where))
        try:
            problem, report = self.merge_in_place(name, head, "merge(%s): %s %s" % (
                self.feature, num, tickets.title(path) or tickets.name(path)))
            merged = git.head()
            if problem is None and self.gate_on:
                quick = self.gate_quick()
                result = checks.gate(self.scripts, self.feature, self.gate_timeout, quick=quick)
                self.log("MERGE-GATE-%s-%s" % ("QUICK" if quick else "FULL", "PASS" if result.ok else "FAIL"))
                if not result.ok:
                    problem, report = "the gate on its merge failed", result.out
        finally:
            os.chdir(str(self.top))
        if problem is not None:
            return self.rebuild(k, problem, report)
        try:
            git._git("merge", "-q", "--ff-only", merged)
            lanes.git_in(self.lane_dir(k), "checkout", "-q", "--detach")
            git._git("branch", "-q", "-d", name)
        except RuntimeError as err:
            raise Stop("cannot move the feature branch to the merge of %s: %s" % (tickets.name(path), err))
        for key in [key for key in self.all if key.startswith("L%d." % k)]:
            del self.all[key]
        self.all["done"] = self.num("done") + 1
        self.all["session_done"] = self.num("session_done") + 1
        self.save()
        state.log(self.log_file, num, "MERGED-%d" % k)
        return self.dispatch()

    def merge_in_place(self, name, head, message):
        """Merge branch name into head in the current worktree, resolving only appends to the plan's append-only
        files. Returns (None, "") on success, else (what went wrong, a report), with the merge undone."""
        git._git("merge", "--abort", check=False)
        git._git("reset", "-q", "--hard", check=False)
        try:
            git._git("checkout", "-q", "--detach", head)
        except RuntimeError as err:
            raise Stop("cannot reset the %s worktree: %s" % (Path.cwd(), err))
        dirty = git.changes()
        if dirty:
            raise Stop("the worktree %s is not clean after a reset: %s. something left files there; remove them or "
                       "run reset" % (Path.cwd(), " ".join(dirty[:5])))
        result = git._git("merge", "--no-ff", "--no-edit", "-m", message, name, check=False)
        if result.returncode == 0:
            return None, ""
        left = lanes.resolve_appends(".", self.plan.as_posix()) if lanes.unmerged(".") else ["(git merge failed)"]
        if not left and git._git("commit", "-q", "--no-edit", check=False).returncode == 0:
            self.log("MERGE-APPENDS")
            return None, ""
        git._git("merge", "--abort", check=False)
        return "it conflicted with the feature branch", (
            "git merge reported conflicts in: %s\n%s" % (", ".join(left), (result.stdout + result.stderr).strip()))

    def refresh(self, k, head):
        """A level 3 ticket whose base is behind the feature head: merge the feature head into its branch, gate it
        in the lane, and review it again on top of the code its reviewer never saw."""
        with self.in_lane(k):
            name = lanes.branch(self.feature, self.get("num"))
            problem, report = self.merge_in_place(name, head, "merge(%s): %s onto the feature branch for its review"
                                                  % (self.feature, self.get("num")))
            if problem is None:
                lanes.git_in(".", "checkout", "-q", "-B", name, "HEAD")
                if self.gate_on:
                    quick = self.gate_quick()
                    result = checks.gate(self.scripts, self.feature, self.gate_timeout, quick=quick)
                    self.log("REFRESH-GATE-%s-%s" % ("QUICK" if quick else "FULL", "PASS" if result.ok else "FAIL"))
                    if not result.ok:
                        problem, report = "the gate failed on top of the feature branch", result.out
            if problem is None:
                moved = self.get("base")
                self.st["base"] = head
                self.st["review_pass"] = "quality"
                self.st["review_attempt"] = 0
                self.st["review_notes"] = NOTE_SEP.join([n for n in (
                    self.get("level_note"),
                    "the feature branch moved since this level 3 ticket was built (from %s to %s), so it is reviewed "
                    "again on top of it. the diff from the base below to HEAD is this ticket's change on the feature "
                    "branch as it is now: probe it against what the other tickets added" % (moved[:12], head[:12]))
                    if n])
                self.log("REFRESH")
                return self.hand_out_review()
        return self.rebuild(k, problem, report)

    def rebuild(self, k, problem, report):
        """Build lane k's ticket again from the feature head, with what went wrong in the ticket. Once only."""
        head = git.head()
        with self.in_lane(k):
            path, num = self.ticket(), self.get("num")
            if self.num("rebuilds") >= 1:
                raise Stop("%s passed its review but %s, and it was rebuilt once already. its Touches line is likely "
                           "wrong: fix the plan, then run reset %s" % (self.ticket_name(), problem, num))
            name = lanes.branch(self.feature, num)
            tip = lanes.git_in(".", "rev-parse", name).stdout.strip()
            base = self.get("base")
            git._git("merge", "--abort", check=False)
            git._git("reset", "-q", "--hard", check=False)
            try:
                lanes.git_in(".", "checkout", "-q", "-B", name, head)
            except RuntimeError as err:
                raise Stop("cannot reset lane %d for the rebuild of %s: %s" % (k, self.ticket_name(), err))
            self.st.clear()
            self.start_ticket(path)
            self.st["rebuilds"] = 1
            tickets.append_section(path, "Rebuild (%s)" % problem, (
                "This ticket was built and passed its review in a lane, but %s. It is built again from the feature "
                "branch as it is now. The earlier build is commit %s (its base was %s): reuse what still fits, "
                "for example with `git diff %s %s`.\n\n%s" % (problem, tip, base, base, tip, gate.tail(report, 60))))
            tickets.set_open(path)
            if not git.commit_file(path, "chore(%s): %s rebuild after its merge" % (self.feature, num)):
                raise Stop("cannot commit the rebuild note to %s. this session must be allowed to run git commit"
                           % self.ticket_name())
            self.log("REBUILD")
            return self.hand_out_build()

    def finish(self):
        """Every ticket is merged: remove the lanes and report, as pick_ticket does without lanes."""
        if self.deferred():
            return self.hand_out_final()
        lanes.remove_all(self.top, self.feature)
        done = self.num("done")
        followups = self.num("followups")
        self.all["owner"] = ""
        self.save()
        return self.emit("DONE %s is complete: %d ticket(s) resolved in this run%s" % (
            self.feature, done, "; %d passed with follow-ups in %s" % (followups, (self.plan / "followups.md").as_posix())
            if followups else ""))

    def drop_lanes(self):
        """For reset: remove the feature's lane worktrees and delete its ticket branches. Returns what it did."""
        done = []
        gone = lanes.remove_all(self.top, self.feature)
        if gone:
            done.append("removed the worktrees %s" % ", ".join(gone))
        names = lanes.branches(self.top, self.feature)
        for name in names:
            git._git("branch", "-q", "-D", name, check=False)
        if names:
            done.append("deleted the branches %s" % ", ".join(names))
        return done

    # ---- planning: stateless, the brief and the draft are all there is --

    def no_plan_yet(self):
        if self.plan.is_dir():
            raise Stop("%s already exists. pick another name: a plan is never overwritten" % self.plan.as_posix())

    def draft_text(self):
        return self.draft.as_posix() + "/"

    def read_text(self, path, what):
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as err:
            raise Stop("cannot read the %s %s: %s" % (what, path, err.strerror))

    def plan_prompt(self, brief, findings=None):
        """The feature-planner's prompt. Saves the brief; a first round (no findings) starts an empty draft."""
        self.no_plan_yet()
        text = self.read_text(brief, "brief")
        notes = self.read_text(findings, "review findings") if findings else ""
        if not text.strip():
            raise Stop("the brief %s is empty" % brief)
        if Path(brief).resolve() != self.brief_file.resolve():
            self.brief_file.write_text(text, encoding="utf-8")
        if not findings and self.draft.is_dir():
            if self.draft.resolve().parent != self.draft_root.resolve():
                raise Stop("the draft folder %s is outside %s" % (self.draft_text(), self.draft_root.as_posix()))
            shutil.rmtree(str(self.draft))
        (self.draft / (os.environ.get("FLOW_TICKETS") or "tasks")).mkdir(parents=True, exist_ok=True)
        self.log("PLAN-PROMPT")
        try:
            return prompts.plan("plan", self.scripts, self.feature, self.draft_text(), text, notes)
        except FileNotFoundError as err:
            raise Stop(str(err))

    def plan_review_prompt(self):
        """The plan-reviewer's prompt: the saved brief and the draft, nothing from the planner."""
        self.no_plan_yet()
        if not self.brief_file.is_file():
            raise Stop("no brief for %s. run plan-prompt first" % self.feature)
        if not self.draft.is_dir():
            raise Stop("no draft plan in %s. run the planner first" % self.draft_text())
        self.log("PLAN-REVIEW-PROMPT")
        try:
            return prompts.plan("plan-review", self.scripts, self.feature, self.draft_text(),
                                self.read_text(self.brief_file, "brief"))
        except FileNotFoundError as err:
            raise Stop(str(err))

    def plan_accept(self):
        """Copy a draft that passes the check into the plan folder. Never overwrites, never commits."""
        self.no_plan_yet()
        if not self.draft.is_dir():
            raise Stop("no draft plan in %s. run the planner first" % self.draft_text())
        check = checks.flow_status(self.scripts, self.feature, "--lint", root=self.draft_root)
        if not check.ok:
            raise Stop("the draft fails the plan check, fix it first: %s"
                       % " ".join(check.out.split())[:400])
        self.plan.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(self.draft), str(self.plan))
        check = checks.flow_status(self.scripts, self.feature, "--check")
        if not check.ok:
            raise Stop("the accepted plan in %s fails the plan check: %s"
                       % (self.plan.as_posix(), " ".join(check.out.split())[:400]))
        self.log("PLAN-ACCEPT")
        return "OK %s" % self.plan.as_posix()
