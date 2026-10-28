"""The state machine that tells an interactive session what to do next.

It sets the limits, retries and review rounds. It judges every phase from the repo, never from the
caller, and prints exactly one line per command.
"""

import contextlib
import hashlib
import os
import re
import secrets
import shlex
import time
from pathlib import Path

from feature_flow import checks, codehash, floorguard, gate, git, lanes, prompts, proof, scouts, state, suggest, tickets
from feature_flow.conductor import buildchecks
from feature_flow.conductor.errors import NoPhase, Stop
from feature_flow.conductor.planning import BRAINSTORM, Planner
from feature_flow.conductor.policy import levels, limits, review
from feature_flow.conductor.policy.levels import CONVERT
from feature_flow.conductor.policy.review import FINDING, FULL_ROUNDS, followups_only
from feature_flow.conductor.settings import MAX_LANES, Settings, _env_int, mode_ok
from feature_flow.conductor.store import NOTE_SEP, RunState, TicketState


VERDICT = re.compile(r"^REVIEW: (PASS|FAIL|ASK (?:architect|designer|po|user))[ \t\r\f\v]*$")
ANSWER = re.compile(r"^ANSWER: (GIVEN|USER)[ \t\r\f\v]*$")  # the last line of a consultant's reply
ASK_HEADING = re.compile(r"^## Ask: (architect|designer|po|user)[ \t]*$", re.MULTILINE)  # a builder's question
MAX_ASKS = 2  # questions one ticket may send to a consultant before the next one goes to the user
OLD_OWNER = re.compile(r"^[0-9a-f]{16}$")  # a raw token, stored by a run started before 0.5.0
LEVEL_LINE = re.compile(r"^LEVEL: ([123])[ \t\r\f\v]*$")  # a reviewer raising the ticket's level
RULING = re.compile(r"^RULING: (TEST|CODE) WRONG[ \t\r\f\v]*$")  # the product owner on a disputed acceptance test
GAP = 3600  # most seconds one step adds to the time spent: a longer pause is the user away, not work


def section_after(text, heading):
    """The text under the last line that is exactly heading, up to the next `## ` heading or a verdict line."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == heading]
    if not starts:
        return ""
    out = []
    for line in lines[starts[-1] + 1:]:
        if line.startswith("## ") or VERDICT.match(line) or ANSWER.match(line):
            break
        out.append(line)
    return "\n".join(out).strip("\n")


def demote(text):
    """text with its `## ` headings made `### `, so it cannot open a section of the ticket it is written into."""
    return re.sub(r"(?m)^## ", "### ", text)


def owner_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Conductor:
    def __init__(self, feature, scripts):
        self.feature = feature
        self.scripts = Path(scripts)
        self.settings = settings = Settings.load(feature)
        self.root = settings.root
        self.plan = self.root / feature
        self.commands = self.plan / "commands.md"
        self.profile = settings.profile
        self.max_retries = settings.max_retries
        self.max_rounds = settings.max_rounds
        self.gate_timeout = settings.gate_timeout
        self.gate_on = settings.gate_on
        self.per_session = settings.per_session
        self.small_files = settings.small_files
        self.small_lines = settings.small_lines
        self.batch_size = settings.batch_size
        self.checks_ran = False
        self.scouts_on = settings.scouts_on
        self.relay = settings.relay
        self.invoke = settings.invoke
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
        self.brainstorm_file = state.STATE_DIR / ("brainstorm-%s.md" % feature)
        self.state_file = state.state_path(folder, feature)
        self.log_file = state.log_path(folder, feature)
        self.findings_file = state.file_path(folder, feature, "findings")
        state.read_bytes(self.findings_file, "findings")  # so a call that never touches it still reports it
        self.all = RunState.load(self.state_file)  # the whole run state
        self.st = TicketState(self.all)  # the ticket's view of it, one lane's while a lane works
        self.per_session = settings.session_limit(self.driver())  # an agent driver: no handoffs

    # ---- small helpers -------------------------------------------------

    def driver(self):
        """Who drives the run: "agent" (an orchestrating agent, FLOW_DRIVER=agent on start) or "person"."""
        return os.environ.get("FLOW_DRIVER") or self.all.get("driver") or "person"

    def get(self, key, default=""):
        return self.st.get(key, default)

    def num(self, key):
        return self.st.num(key)

    def save(self):
        self.all.save()

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
        return limits.round_cap(self.num("level"), self.max_rounds)

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
        self.st["due_minors"] = ""  # the next round's reviews list them again if they are still there
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

    def add_due(self, key, items):
        """Remember follow-ups for when the ticket passes: tab separated in the state, one per item."""
        items = [" ".join(item.split()) for item in items if item.strip()]
        self.st[key] = NOTE_SEP.join([n for n in self.get(key).split(NOTE_SEP) if n] + items)

    def write_followups(self, title, items, message):
        """Append items under a heading of the plan's followups.md and commit it."""
        path = self.plan / "followups.md"
        text = "" if path.is_file() else (
            "# Follow-ups: %s\n\nWhat the run left for later: minor findings of passing reviews, the findings a "
            "level 2 ticket passed with after %d review rounds, and Done when checks this host could not pass. "
            "Each is a candidate for a cleanup ticket.\n" % (self.feature, FULL_ROUNDS))
        text += "\n## %s\n\n%s\n" % (title, "\n".join("- " + item for item in items))
        with open(str(path), "a", encoding="utf-8") as handle:
            handle.write(text)
        if not git.commit_file(path, message):
            raise Stop("cannot commit %s. this session must be allowed to run git commit" % path.as_posix())

    def write_due(self, title):
        """Write the follow-ups remembered for this ticket (or the feature review) and forget them."""
        items = [n for key in ("due_checks", "due_minors") for n in self.get(key).split(NOTE_SEP) if n]
        self.st["due_checks"] = self.st["due_minors"] = ""
        if items:
            self.write_followups(title, items, "chore(%s): %s follow-ups" % (self.feature, self.get("num")))
            self.log("FOLLOWUPS %d" % len(items))

    def pass_ticket(self):
        self.write_due("%s (left for later)" % self.ticket_name())
        self.note_slowest()
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
        found = [line.strip() for line in findings.splitlines() if FINDING.match(line)]
        self.write_followups("%s (round %d, %s)" % (self.ticket_name(), self.num("round") + 1, source), found,
                             "chore(%s): %s follow-ups from the %s" % (self.feature, self.get("num"), source))
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
        self.all.update({"phase": "final", "num": "all", "ticket": ""})  # the log names the feature review `all`
        self.all["final_base"] = self.feature_base()
        self.snapshot_code()  # what check_code holds the feature review to; with lanes, no ticket's snapshot is here
        self.all["review_attempt"] = (self.num("review_attempt") if retry else 0) + 1  # not the last ticket's count
        self.all["review_sha"] = git.head()
        self.all["verdict"] = ""
        self.all["relay_handoff"] = "1" if self.relay else ""
        self.save()
        return self.emit("REVIEW %s all %s" % (self.plan.as_posix(), self.all["final_base"]))

    def judge_final(self):
        self.check_code(final=True)
        note = self.undo_edit(self.all.get("review_sha", ""), "reviewer", "a reviewer")
        if note:
            self.edit_retry(note, self.num("review_attempt"), "the feature reviewer of %s kept changing files" % self.feature)
            return self.hand_out_final(retry=True)
        self.all["edit_note"] = ""
        verdict = self.take_verdict()
        if verdict == "pass":
            self.write_due("feature review (left for later)")
            for key in ("phase", "deferred", "final_base", "final_round", "review_attempt", "review_sha", "scout_key"):
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
        if value == "on" and self.fast():
            return ("OK fast is already on. to go faster still, the open tickets can be re-planned into fewer with the "
                    "same bar: with the user's yes, run replan-prompt and give it to the feature-planner")
        self.all["fast"] = "1" if value == "on" else ""
        self.save()
        self.log("FAST-%s" % value.upper())
        return "OK fast %s%s" % (value, "" if value == "on" or not self.deferred() else
                                 ". %d ticket(s) already deferred still get the feature review at the end"
                                 % len(self.deferred()))

    # ---- the tester: acceptance tests written from spec.md before the build, run once every ticket is done --

    def acceptance_command(self):
        """commands.md's Acceptance command as committed, or "" when the plan has none: then there is no tester."""
        return tickets.commands_text_value(self.show_head(self.commands), "Acceptance")

    def acceptance_folder(self):
        """Where the tester's tests live, relative to the repo, with a trailing slash. Inside the plan folder, so
        the floor guard already keeps every builder out of it."""
        return proof.repo_relative(self.plan / "acceptance").rstrip("/") + "/"

    def tests_due(self):
        """True when the plan has an Acceptance command and no acceptance tests are committed yet."""
        if not self.acceptance_command():
            return False
        listed = git._git("ls-tree", "-r", "--name-only", "HEAD", "--", self.acceptance_folder(), check=False)
        return listed.returncode == 0 and not listed.stdout.strip()

    def hand_out_test(self, retry=False):
        """Hand the tester its task: write the acceptance tests, or (with rulings) fix the ones the product owner
        ruled wrong. Like the feature review, it is no ticket's phase and has no lane."""
        self.count_run()
        if not retry:
            self.all.update({"test_base": git.head(), "test_attempt": 0, "test_note": "",
                             "test_mode": "fix" if self.all.get("accept_rulings") else "write"})
        self.all.update({"phase": "test", "num": "accept", "ticket": ""})
        self.all["test_attempt"] = self.num_all("test_attempt") + 1
        self.all["relay_handoff"] = "1" if self.relay else ""
        self.snapshot_code()
        self.save()
        return self.emit("TEST %s %s" % (self.plan.as_posix(), self.all["test_base"]))

    def judge_test(self):
        """The tester's commits may change only the acceptance folder. The Test command must still pass with them
        in place, and newly written tests must fail before anything is built."""
        self.check_code()
        base = self.all.get("test_base", "")
        if not git.is_clean():
            raise Stop("working tree is dirty after the tester of %s: its tests should have been committed" % self.feature)
        folder = self.acceptance_folder()
        changed = [p for p in git._git("diff", "--name-only", "--no-renames", base, "HEAD").stdout.splitlines() if p.strip()]
        outside = [p for p in changed if not p.startswith(folder)]
        if outside:
            raise Stop("the tester of %s changed %s, outside %s, where only its acceptance tests may go. take its "
                       "commits out with `git reset --hard %s` and run next to hand the tests out again"
                       % (self.feature, ", ".join(outside[:5]), folder, base[:12]))
        note = ""
        if not changed:
            note = "the last tester committed nothing under %s" % folder
        elif self.gate_on:
            result = checks.gate(self.scripts, self.feature, self.gate_timeout)
            self.log("TEST-GATE-PASS" if result.ok else "TEST-GATE-FAIL")
            if not result.ok:
                note = ("with the acceptance tests committed, the gate fails. keep them where only the Acceptance "
                        "command runs them, never in what commands.md's Test command runs. the last lines: %s"
                        % " ".join(gate.tail(result.out, 15).split())[:1200])
        if not note and self.all.get("test_mode") != "fix":
            result = self.run_acceptance()
            if result.ok:
                note = ("the acceptance tests pass before anything is built, so they cannot fail. each one must fail "
                        "now, on an assertion about what spec.md promises, and pass once the feature is built")
        if note:
            if self.num_all("test_attempt") >= self.max_retries:
                raise Stop("the tester of %s did not finish after %d attempt(s): %s"
                           % (self.feature, self.num_all("test_attempt"), note))
            self.all["test_note"] = note
            return self.hand_out_test(retry=True)
        self.log("TEST-FIXED" if self.all.get("test_mode") == "fix" else "TEST-WRITTEN")
        for key in ("phase", "test_base", "test_attempt", "test_note", "test_mode", "accept_rulings", "accept_sha"):
            self.all[key] = ""
        self.save()
        return self.dispatch() if self.num("lanes") > 1 else self.pick_ticket()

    def run_acceptance(self):
        """Run the Acceptance command from the top of the repo. It must leave the working tree as it was."""
        self.all["num"] = "accept"
        result = checks.smoke(self.acceptance_command(), self.gate_timeout)
        dirty = git.changes()
        if dirty:
            raise Stop("the Acceptance command of %s changed the working tree: %s. it must not change it"
                       % (self.feature, " ".join(dirty[:5])))
        return result

    def check_acceptance(self):
        """Every ticket is resolved: first the tests the product owner ruled wrong go back to the tester, then the
        acceptance tests run. A failure becomes a fix ticket. Returns the next line, or None when they pass (or the
        plan has no Acceptance command)."""
        if not self.acceptance_command():
            return None
        if self.all.get("accept_rulings"):
            return self.hand_out_test()
        head = git.head()
        if self.all.get("accept_sha") == head:
            return None
        result = self.run_acceptance()
        if result.ok:
            self.log("ACCEPT-PASS")
            self.all["accept_sha"] = head
            self.save()
            return None
        self.log("ACCEPT-FAIL")
        round_no = self.num_all("accept_round") + 1
        if round_no > self.max_rounds:
            raise Stop("the acceptance tests of %s still fail after %d round(s) of fixes. the user decides what happens "
                       "next: the last fix ticket says what failed" % (self.feature, self.max_rounds))
        path = self.acceptance_ticket(round_no, result)
        if not git.commit_file(path, "chore(%s): acceptance test fixes, round %d" % (self.feature, round_no)):
            raise Stop("cannot commit %s. this session must be allowed to run git commit" % path.as_posix())
        self.all.update({"accept_round": round_no, "accept_num": tickets.number(str(path)), "phase": ""})
        self.save()
        return self.dispatch() if self.num("lanes") > 1 else self.pick_ticket()

    def acceptance_ticket(self, round_no, result):
        """Write the failing acceptance run as a new open ticket, numbered after the last one."""
        folder = self.plan / (os.environ.get("FLOW_TICKETS") or "tasks")
        nums = [int(tickets.number(p)) for p in tickets.ticket_files(str(folder)) if tickets.number(p).isdigit()]
        path = folder / ("%02d-acceptance-fixes-%d.md" % (max(nums or [0]) + 1, round_no))
        out = gate.tail(result.out + ("\nthe Acceptance command timed out after %d minutes\n" % self.gate_timeout
                                      if getattr(result, "timed_out", False) else ""), 60)
        quoted = "\n".join("    " + line for line in out.strip("\n").splitlines()) or "    (no output)"
        tests = self.acceptance_folder()
        path.write_text(
            "# Make the acceptance tests pass, round %d\n\n"
            "Type: task\nStatus: open\nBlocked by: —\nTest first: no\nLevel: 2\n"
            "Check: none the conductor runs the acceptance tests again once every ticket is resolved\n\n"
            "Every ticket is resolved, but the acceptance tests fail. The tester wrote them in `%s` from spec.md "
            "before the build, so they check what the product owner asked for, not how it was built. Fix the code "
            "so they pass. You may run them with `%s`.\n\n"
            "If you are sure a test asks for something spec.md does not say, do not work around it, and do not "
            "change the test: the floor guard fails any change under `%s`. Add a `## Ask: po` section to this ticket "
            "that names the test, what it expects and the spec.md line it disagrees with, and stop. The product owner "
            "rules on it. A test it rules wrong is left failing here and goes back to the tester once this ticket is "
            "resolved.\n\n"
            "## Not in this ticket\n\n- Any file under `%s`.\n\n"
            "## Done when\n\n- `%s` passes, apart from tests the product owner ruled wrong in this ticket.\n"
            "- commands.md's Test command passes.\n\n"
            "## The failing run\n\n%s\n\n## Answer\n"
            % (round_no, tests, self.acceptance_command(), tests, tests, self.acceptance_command(), quoted),
            encoding="utf-8")
        return path

    def test_prompt(self):
        rulings = [r for r in self.all.get("accept_rulings", "").split(NOTE_SEP) if r]
        try:
            return prompts.tester(self.scripts, self.feature, self.plan.as_posix(), self.all.get("test_base", ""),
                                  self.acceptance_command(), self.acceptance_folder(),
                                  rulings if self.all.get("test_mode") == "fix" else (),
                                  [n for n in (self.all.get("test_note", ""),) if n])
        except FileNotFoundError as err:
            raise Stop(str(err))

    def pick_ticket(self):
        """Hand out the next ready ticket, or finish."""
        check = checks.flow_status(self.scripts, self.feature, "--check")
        if not check.ok:
            raise Stop("ticket check failed, fix the tickets first")
        dirty = git.changes()
        if dirty:
            raise Stop("working tree is not clean, commit or stash first: %s%s"
                       % (" ".join(dirty[:5]), " and %d more" % (len(dirty) - 5) if len(dirty) > 5 else ""))
        if self.tests_due():
            return self.hand_out_test()
        nxt = checks.flow_status(self.scripts, self.feature, "--next")
        if nxt.code == 10:
            line = self.check_acceptance()
            if line is not None:
                return line
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
        self.check_replan()
        self.check_budget()
        first = nxt.out.strip().splitlines()[-1]
        self.start_ticket(first)
        more = self.batch_for(first)
        if more:
            self.st["batch"] = " ".join(more)
            self.log("BATCH %d" % (len(more) + 1))
        return self.hand_out_build()

    # ---- batches: in fast mode one builder builds a few small tickets, one commit range each --

    def batch_for(self, first):
        """The ready tickets the builder of first also builds, in order, or [] for none. Only in fast mode
        with the gate on, no lanes and no relay. Each one is level 1 or 2 (never raised), has a `Touches:`
        line, and touches nothing another ticket of the batch or a `Sensitive:` path touches."""
        size = self.batch_size
        if self.per_session > 0:
            size = min(size, self.per_session - self.num("session_done"))
        if not mode_ok("batch", size=size, fast_mode=self.fast(), gate_on=self.gate_on, relay=self.relay,
                       lanes=self.num("lanes")):
            return []
        sensitive = tickets.sensitive_patterns(self.show_head(self.commands))
        chosen = []
        alone = self.all.get("no_batch", "").split()
        for path in [first] + [p for p in checks.flow_status(self.scripts, self.feature, "--ready").out.split()
                               if p != first]:
            touched, level = self.footprint(path)
            if (touched is None or level not in (1, 2) or not lanes.disjoint(touched, sensitive)
                    or tickets.number(path) in alone):
                if path == first:
                    return []
                continue
            if all(lanes.disjoint(touched, other) for _, other in chosen):
                chosen.append((path, touched))
            if len(chosen) == size:
                break
        return [path for path, _ in chosen[1:]]

    def batch_note(self):
        """What the builder of a batch is told on top of the build guide for the first ticket."""
        rest = self.get("batch").split()
        return ("This build is a batch of %d small tickets: `%s` (above), then %s. Build them one at a time, in this "
                "order, each exactly as the guide says for one ticket, with that ticket's path and number in place of "
                "the first one's: finish one completely (its commits, its Status set to resolved, its Answer) before "
                "you start the next, and never put two tickets in one commit. The conductor checks each ticket on its "
                "own commits. If one cannot be finished, set it back to open with an Attempt note and stop: do not "
                "start the next. Reply with what you built for each ticket."
                % (len(rest) + 1, self.ticket(), ", ".join("`%s`" % p for p in rest)))

    def ticket_ends(self, paths):
        """[(path, the commit that resolved it, or None)], walking base..HEAD in order: a ticket's commits
        follow the last resolved ticket's."""
        commits = git._git("rev-list", "--reverse", "%s..HEAD" % self.get("base")).stdout.split()
        out, at = [], 0
        for path in paths:
            rel = proof.repo_relative(path)
            end = None
            for i in range(at, len(commits)):
                try:
                    text = git.show_text("%s:%s" % (commits[i], rel))
                except RuntimeError:
                    continue
                if re.search(r"^Status:[ \t]*(%s)\b" % "|".join(tickets.DONE), "\n".join(text.splitlines()[:20]),
                             re.MULTILINE | re.IGNORECASE):
                    end, at = commits[i], i + 1
                    break
            out.append((path, end))
        return out

    def judge_batch(self):
        """Judge every ticket of a batch on its own commits: the gate once at HEAD (each ticket's end only when
        that fails, to find the first that broke it), then the floor guard, the footprint, Done when and test
        first with HEAD detached at the ticket's last commit. A ticket that passes is deferred to the feature
        review; one that fails is reopened with its findings, to be built again alone."""
        paths = [self.ticket()] + self.get("batch").split()
        self.st["batch"] = ""
        if not git.is_clean():
            raise Stop("working tree is dirty after the batch of %s, it should have been committed" % self.ticket_name())
        home = git._git("symbolic-ref", "-q", "--short", "HEAD", check=False).stdout.strip()
        if not home:
            raise Stop("HEAD is detached after the batch of %s. a builder must not switch branches" % self.ticket_name())
        ends = self.ticket_ends(paths)
        built = [(path, end) for path, end in ends if end]
        gate = checks.gate(self.scripts, self.feature, self.gate_timeout, quick=self.gate_quick()) if built else None
        if built:
            self.log("GATE-PASS" if gate.ok else "GATE-FAIL")
        broke = None
        results = []
        start = self.get("base")
        self.st["batch_restore"] = home
        self.save()
        try:
            for path, end in built:
                git._git("checkout", "-q", "--detach", end)
                self.st.update({"ticket": path, "num": tickets.number(path), "base": start, "due_checks": "",
                                "level_note": ""})
                self.st["level"] = self.base_level()
                failure = None
                if not gate.ok and broke is None:
                    result = checks.gate(self.scripts, self.feature, self.gate_timeout, quick=self.gate_quick())
                    if not result.ok:
                        broke, failure = path, ("gate", result.out)
                if failure is None:
                    source, report, _ = buildchecks.run(self, buildchecks.pipeline(self, gate=False))
                    failure = (source, report) if source else None
                if failure is None and self.measure_level() >= 3:
                    failure = ("batch", "%s: a batch cannot defer its review, so build it alone"
                               % self.get("level_note"))
                results.append((path, start, failure, self.get("due_checks")))
                start = end
        finally:
            git._git("checkout", "-q", home)
            self.st["batch_restore"] = ""
            self.save()
        if built and not gate.ok and broke is None:  # it fails at HEAD but at no ticket's end: blame the last one
            path, base, _, due = results[-1]
            results[-1] = (path, base, ("gate", gate.out), due)
        for path, base, failure, due in results:
            self.st.update({"ticket": path, "num": tickets.number(path), "base": base, "due_checks": due,
                            "due_minors": ""})
            if failure:
                self.log("BATCH-FAIL")
                self.all["no_batch"] = " ".join(self.all.get("no_batch", "").split() + [self.get("num")])
                tickets.append_findings(path, 1, failure[0], failure[1])
                tickets.set_open(path)
                if not git.commit_file(path, "chore(%s): %s back to open from its batch" % (self.feature,
                                                                                         self.get("num"))):
                    raise Stop("cannot commit %s. this session must be allowed to run git commit" % path)
                continue
            self.write_due("%s (left for later)" % self.ticket_name())
            items = [i for i in self.all.get("deferred", "").split() if not i.startswith(self.get("num") + ":")]
            self.all["deferred"] = " ".join(items + ["%s:%s" % (self.get("num"), base)])
            self.log("REVIEW-DEFERRED")
            self.st["done"] = self.num("done") + 1
            self.st["session_done"] = self.num("session_done") + 1
        left = [path for path, end in ends if not end]  # the builder stopped before these: each is built alone
        for path in left:
            self.all["no_batch"] = " ".join(self.all.get("no_batch", "").split() + [tickets.number(path)])
            if tickets.status(path) not in ("open", "parked", "wontfix"):
                tickets.set_open(path)
        if left and git.changes():
            git.commit_paths(left, "chore(%s): %s back to open, not built in the batch"
                             % (self.feature, ", ".join(tickets.number(p) for p in left)))
        self.st["phase"] = ""
        self.save()
        return self.pick_ticket()

    def start_ticket(self, path):
        """Fresh per-ticket state for the ticket at path, based at HEAD, then the smoke test."""
        self.st["limit"] = self.run_limit()
        self.st.update({"ticket": path, "num": tickets.number(path), "base": git.head(), "phase": "",
                        "attempt": 0, "review_attempt": 0, "round": 0, "review_sha": "", "review_notes": "", "review_pass": "spec",
                        "spec_ok": "", "level_note": "", "level_raised": "", "edit_note": "", "due_checks": "", "due_minors": "", "asks": 0, "ask_role": "", "ask_from": "",
                        "ticket_clock": self.all.get("spent", 0)})
        self.st["level"] = self.base_level()
        self.snapshot_code()
        self.run_smoke()

    def snapshot_code(self):
        whole, each = codehash.flow_code(self.scripts)
        self.st["code_sha"] = whole
        self.st["code_files"] = codehash.dump(each)

    def check_code(self, allowed=False, final=False):
        """Stop when the files the conductor runs from changed since the ticket was picked."""
        whole, each = codehash.flow_code(self.scripts)
        if whole == self.get("code_sha"):
            return
        if allowed:
            self.snapshot_code()
            return
        names = codehash.changed(codehash.load(self.get("code_files")), each)
        if final:
            raise Stop("flow code changed during the feature review of %s: %s. a reviewer must never change it"
                       % (self.feature, ", ".join(names)))
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
        if self.get("batch"):
            return self.judge_batch()
        status = tickets.status(self.ticket())
        if status not in tickets.DONE:
            if status in tickets.RESET:
                tickets.set_open(self.ticket())
            role, question = self.open_ask()
            if role:
                return self.hand_out_ask("build", role, question)
            if self.num("attempt") >= self.max_retries:
                raise Stop("%s is still unresolved after %d attempt(s)" % (self.ticket_name(), self.max_retries))
            return self.hand_out_build()
        if not git.is_clean():
            raise Stop("working tree is dirty after %s, it should have been committed" % self.ticket_name())
        source, report, notes = buildchecks.run(self, buildchecks.pipeline(self))
        if source:
            return self.send_back(source, report)
        level = self.measure_level()
        decision, review_pass, more, events = review.after_checks(
            level, self.fast(), self.gate_on, self.checks_ran, self.small_note() if level == 0 else "",
            proof.review_mode(self.ticket_at_base()), self.get("spec_ok"), self.num("round"), self.get("level_note"))
        if decision == "defer":
            return self.defer_review()
        self.st["review_pass"] = review_pass
        for event in events:
            if event == "REVIEW-SINGLE":
                self.st["level_raised"] = ""
            self.log(event)
        self.st["review_notes"] = NOTE_SEP.join(notes + more)
        return self.hand_out_review()

    def base_level(self):
        """The level known before the build, from the ticket at base: its `Level:` line, raised to 3 by
        `Review: full`, `Type: convert` or `Floor: allow flow-edit`. 0 when none of these is there."""
        level, why = levels.declared(self.ticket_at_base(), self.flow_edit_allowed())
        self.st["level_note"] = levels.describe(level, why) if level else ""
        return level

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
        hit = []
        patterns = tickets.sensitive_patterns(self.commands_at_base())
        if patterns and level < 3:
            hit = [p for p in git.diff_names(self.get("base"), "HEAD", self.plan.as_posix())
                   if tickets.matches_sensitive(p, patterns)]
        files, lines, binary = 0, 0, False
        if level == 1 and not hit:  # the size only matters to a level 1 diff that no Sensitive path raised
            files, lines, binary = git.diff_size(self.get("base"), "HEAD", self.plan.as_posix())
        level, why = levels.measured(level, hit, files, lines, binary, self.small_files, self.small_lines)
        if why:
            self.st["level_note"] = levels.describe(level, why)
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

    # ---- the time budget: fast mode when over, then a re-plan the user says yes to --

    def set_budget(self, value):
        """FLOW_BUDGET or `budget <value>`: minutes of work (a number, or +N to add), or off."""
        if value in ("off", "0"):
            self.all["budget"] = ""
            return
        add = value.startswith("+")
        try:
            minutes = int(value[1:] if add else value)
        except ValueError:
            minutes = 0
        if minutes <= 0:
            raise Stop("the budget is a number of minutes, +minutes or off, not %s" % value)
        self.all["budget"] = (self.num_all("budget") if add else 0) + minutes
        self.all["budget_offer"] = ""  # a new budget earns a new offer once it runs out

    def num_all(self, key):
        return self.all.num(key)

    def tick(self):
        """Add the time since the last step to the time spent, up to GAP for one step."""
        now = int(time.time())
        seen = self.num_all("seen")
        if seen:
            self.all["spent"] = self.num_all("spent") + min(max(now - seen, 0), GAP)
        self.all["seen"] = now

    def spent_minutes(self):
        return self.num_all("spent") // 60

    def note_slowest(self):
        """Remember the ticket that took longest, to tell a stuck ticket from a slow plan."""
        took = self.num_all("spent") - self.num("ticket_clock")
        slowest = self.all.get("slowest", "").split(":")
        if len(slowest) != 3 or took > int(slowest[1] or 0):
            builds = max(self.num("attempt"), 1) + self.num("round")  # a review round starts the attempts again
            self.all["slowest"] = "%s:%d:%d" % (self.get("num"), took, builds)

    def budget_report(self):
        budget = self.num_all("budget")
        if not budget:
            return "OK no budget. %d active minute(s) spent so far" % self.spent_minutes()
        return "OK budget %d minute(s), %d spent, fast %s%s" % (
            budget, self.spent_minutes(), "on" if self.fast() else "off",
            " (switched on by the budget at minute %s)" % self.all["budget_fast"] if self.all.get("budget_fast") else "")

    def budget_cmd(self, value=None):
        """`budget` reports; `budget <minutes>|+<minutes>|off` sets it between phases."""
        if value is None:
            return self.budget_report()
        self.check_owner()
        self.tick()
        self.set_budget(value)
        self.save()
        self.log("BUDGET-%s" % value.upper())
        return self.budget_report()

    def check_budget(self, offer=True):
        """Before a ticket starts: over the budget, switch to fast mode first. Still over once fast mode has had
        a ticket, stop once and offer a re-plan, which only the user can say yes to. Nothing is cut silently."""
        budget = self.num_all("budget")
        if not budget or self.num_all("spent") < budget * 60:
            return
        if not self.fast():
            self.all["fast"] = "1"
            self.all["budget_fast"] = self.spent_minutes()
            self.all["fast_done"] = self.num_all("done")
            self.save()
            self.log("BUDGET-FAST")
            return
        if self.all.get("budget_offer") or not offer:
            return
        if self.all.get("budget_fast") and self.num_all("done") <= self.num_all("fast_done"):
            return  # fast mode has not finished a ticket yet
        self.all["budget_offer"] = "1"
        self.save()
        self.log("BUDGET-OVER")
        check = checks.flow_status(self.scripts, self.feature, "--counts")
        counts = dict(part.split("=", 1) for part in check.out.split() if "=" in part)
        left = int(counts.get("open", 0) or 0) + int(counts.get("claimed", 0) or 0)
        note = ""
        slowest = self.all.get("slowest", "").split(":")
        if len(slowest) == 3 and int(slowest[1]) * 2 > self.num_all("spent") and int(slowest[2]) > 1:
            note = ("Most of it went to ticket %s (%d minute(s), %s attempts): that ticket is stuck, not the plan, so "
                    "look at it first. " % (slowest[0], int(slowest[1]) // 60, slowest[2]))
        raise Stop("over the time budget for %s: %d of %d active minute(s) spent, %d ticket(s) left, fast mode on. %s"
                   "To finish sooner, the open tickets can be re-planned into fewer with the same bar: with the user's "
                   "yes, run replan-prompt and give it to the feature-planner. To go on as planned, run next, and "
                   "`budget <minutes>` sets a new budget" % (self.feature, self.spent_minutes(), budget, left, note))

    def replan_prompt(self):
        """The feature-planner's prompt to fold the open tickets into fewer. Only between tickets."""
        self.check_owner()
        if not self.plan.is_dir():
            raise Stop("no plan folder %s" % self.plan)
        if self.all.get("phase") or self.busy_lanes():
            raise Stop("a ticket is in progress. run replan-prompt between tickets, when next would start a new one")
        folder = self.plan / (os.environ.get("FLOW_TICKETS") or "tasks")
        paths = tickets.ticket_files(str(folder))
        open_ones = [p for p in paths if tickets.status(p) not in tickets.DONE + ("parked", "wontfix")]
        if len(open_ones) < 2:
            raise Stop("%d open ticket(s) left, nothing to fold together" % len(open_ones))
        self.all["replan_sha"] = git.head()
        self.save()
        self.log("REPLAN-PROMPT")
        try:
            return prompts.replan(self.scripts, self.feature, self.plan.as_posix(),
                                  [Path(p).as_posix() for p in open_ones], (self.plan / BRAINSTORM).is_file())
        except FileNotFoundError as err:
            raise Stop(str(err))

    def check_replan(self):
        """After a re-plan was handed out: the resolved tickets must be as they were, and the plan committed."""
        sha = self.all.get("replan_sha")
        if not sha:
            return
        folder = (self.plan / (os.environ.get("FLOW_TICKETS") or "tasks")).as_posix()
        changed = git._git("diff", "--name-only", sha, "HEAD", "--", folder, check=False).stdout.split()
        for path in changed:
            try:
                before = git.show_text("%s:%s" % (sha, path))
            except RuntimeError:
                continue  # a new ticket
            if re.search(r"^Status:[ \t]*(resolved|done|closed)\b", before, re.MULTILINE | re.IGNORECASE):
                raise Stop("the re-plan changed %s, which was resolved before it. put it back with `git checkout %s "
                           "-- %s` and commit" % (path, sha[:12], path))
        self.all["replan_sha"] = ""
        if changed:
            self.log("REPLAN")

    def start(self):
        if not self.plan.is_dir():
            return self.emit("PLAN")
        owner = self.get("owner")
        takeover = bool(owner)
        if owner and os.environ.get("FLOW_TAKEOVER", "0") != "1":
            raise Stop("%s is owned by session %s. if that session is closed or dead, run start with FLOW_TAKEOVER=1"
                       % (self.feature, owner[:8]))
        wanted = _env_int("FLOW_LANES", 1)
        mode_ok("lanes_range", lanes=wanted)
        mode_ok("lanes_relay", lanes=wanted, relay=self.relay)
        mode_ok("lanes_top", lanes=wanted, cwd=Path.cwd().resolve(), top=self.top)
        busy = self.busy_lanes()
        if busy and wanted != self.num("lanes"):
            raise Stop("lane(s) %s still hold tickets from the last session, which ran with FLOW_LANES=%d. start with "
                       "that, or reset to drop them" % (",".join(map(str, busy)), self.num("lanes")))
        driver = os.environ.get("FLOW_DRIVER", "")
        mode_ok("driver", driver=driver)
        token = secrets.token_hex(8)
        if driver:
            self.st["driver"] = driver
        self.st["owner"] = owner_hash(token)
        self.st["session_done"] = 0
        self.st["lanes"] = wanted if wanted > 1 else ""
        fast = os.environ.get("FLOW_FAST", "")
        mode_ok("fast", fast=fast)
        if fast:
            self.st["fast"] = "1" if fast == "1" else ""
        budget = os.environ.get("FLOW_BUDGET", "")
        if budget:
            self.set_budget(budget)
        self.st["seen"] = int(time.time())  # the time between sessions is not spent on the feature
        self.save()
        self.log("TAKEOVER" if takeover else "START")
        self.log("DRIVER-%s" % self.driver().upper())
        if self.profile:
            self.log("PROFILE-%s" % self.profile.upper())
        return "OK %s" % token

    def next(self, lane=None):
        self.check_owner()
        self.tick()
        if self.all.get("phase") == "final":
            if lane is not None:
                raise Stop("next %s: the feature review has no lane. run next without one" % lane)
            if not self.plan.is_dir():
                raise Stop("no plan folder %s" % self.plan)
            if self.get("relay_handoff") == "1":
                return self.handoff()
            return self.judge_final()
        if self.all.get("phase") == "test":
            if lane is not None:
                raise Stop("next %s: the tester has no lane. run next without one" % lane)
            if not self.plan.is_dir():
                raise Stop("no plan folder %s" % self.plan)
            if self.get("relay_handoff") == "1":
                return self.handoff()
            return self.judge_test()
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
        if self.get("batch_restore"):
            try:
                git._git("checkout", "-q", self.get("batch_restore"))
            except RuntimeError as err:
                raise Stop("cannot go back to %s after judging a batch: %s. run `git checkout %s` by hand"
                           % (self.get("batch_restore"), err, self.get("batch_restore")))
            self.st["batch_restore"] = ""
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
        if phase == "ask":
            return self.judge_ask()
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
        keys = ("deferred", "fast", "accept_round", "accept_num", "accept_rulings") + (("budget", "spent", "budget_offer") if self.all.get("budget") else ())
        kept = {k: self.all[k] for k in keys if self.all.get(k)}  # a deferred ticket still owes its review,
        # and a budget's time stays spent
        for path, kind in ((self.state_file, "state"), (self.findings_file, "findings")):
            state.remove(path, kind)
        for pattern in ("ask-%s.*" % self.feature, "ask-%s-L*" % self.feature, "scout-%s-*" % self.feature,
                        "edit-%s-*" % self.feature):
            for path in self.state_file.parent.glob(pattern):
                path.unlink()
        if not reopened and not had_run and not dropped:
            return "OK nothing to reset for %s. run %s %s" % (self.feature, self.invoke, self.feature)
        self.all = RunState(self.state_file, kept)
        self.st = TicketState(self.all)
        if kept:
            self.save()
        self.log("RESET")
        done = ["cleared the run state"] if had_run else []
        if kept.get("deferred"):
            done.append("kept %d ticket(s) built in fast mode for the feature review" % len(self.deferred()))
        done += dropped
        done += ["reopened %s" % tickets.name(p) for p in reopened]
        return "OK %s. run %s %s" % (", ".join(done), self.invoke, self.feature)

    def undo_edit(self, sha, who, rule):
        """A read only agent changed tracked files. A commit stops the run; an edit is saved as a patch in the
        state folder and put back, and the note for the next attempt comes back ("" when nothing changed)."""
        if git.head() != sha:
            raise Stop("the %s changed tracked files, which %s must never do. a commit landed after it was handed "
                       "out (`git log --oneline %s..HEAD`), so the conductor cannot undo it. if the session made that "
                       "commit (never commit between a %s and its next), take it out with `git reset --soft %s` and "
                       "`git stash`, run next, and commit it again once the run is done"
                       % (who, rule, sha[:12], "question" if rule == "a consultant" else "review", sha[:12]))
        if git.tracked_clean():
            return ""
        patch = self.state_file.parent / ("edit-%s-%s%s.patch" % (self.feature, self.get("num") or "plan",
                                                                    "-L%d" % self.lane if self.lane else ""))
        try:
            names = git.undo_tracked(patch)
        except (OSError, RuntimeError) as err:
            raise Stop("the %s changed tracked files, which %s must never do, and the conductor could not put them "
                       "back: %s" % (who, rule, err))
        self.log("EDIT-UNDONE")
        shown = ", ".join(names[:5]) + (" and %d more" % (len(names) - 5) if len(names) > 5 else "")
        return ("the last %s changed %s, which %s must never do. the conductor put the files back and threw its "
                "answer away (its changes are in %s). change no file: report what you would change instead"
                % (who, shown, rule, patch.as_posix()))

    def edit_retry(self, note, attempts, what):
        """After undo_edit put a read only agent's edit back: the note for the next attempt, or a stop."""
        if attempts >= self.max_retries:
            raise Stop("%s after %d attempt(s): %s" % (what, attempts, note.split(". the conductor", 1)[0]
                       + ". the conductor put the files back"))
        self.st["verdict"] = ""
        self.st["edit_note"] = note

    def take_verdict(self):
        """The verdict `verdict` recorded, cleared; a pass keeps its minor findings for the follow-ups.
        With none recorded, nothing changes: the session must run verdict first."""
        verdict = self.get("verdict")
        if not verdict:
            raise NoPhase("no verdict recorded for the review of %s: save the reviewer's whole reply to a file and "
                          "run verdict <that file>%s, then next" % (self.ticket_name() if self.get("phase") != "final"
                                                                    else self.feature, self.lane_word()))
        if verdict == "pass":
            self.add_due("due_minors", self.get("reply_minors").split(NOTE_SEP))
        self.st["verdict"] = self.st["reply_minors"] = ""
        return verdict

    def judge_review(self):
        self.check_code()
        note = self.undo_edit(self.get("review_sha"), "reviewer", "a reviewer")
        if note:
            self.edit_retry(note, self.num("review_attempt"), "the reviewer of %s kept changing files" % self.ticket_name())
            return self.hand_out_review()
        self.st["edit_note"] = ""
        verdict = self.take_verdict()
        review_pass = self.get("review_pass", "spec")
        raised = review_pass == "single" and self.get("level_raised") == "1"  # a reviewer raised it to 3 in this pass
        self.st["level_raised"] = ""
        if verdict == "pass" and (review_pass == "spec" or raised):
            self.st["review_pass"] = "quality"
            self.st["review_attempt"] = 0
            self.st["spec_ok"] = "1"
            return self.hand_out_review()
        if verdict == "pass":
            return self.pass_ticket()
        if verdict.startswith("ask:"):
            return self.hand_out_ask("review", verdict[4:], state.read_text(self.ask_file("question")) or "")
        if verdict == "fail":
            if self.lane and self.get("findings_for") != str(self.lane):
                raise Stop("the review findings on file are not lane %d's: run verdict for this lane, then next %d"
                           % (self.lane, self.lane))
            findings = state.read_text(self.findings_file, "findings") or ""
            source = {"quality": "quality review", "single": "single review"}.get(review_pass, "spec review")
            if review.on_fail(self.num("level"), self.num("round"), review_pass, findings) == "followups":
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
        if self.all.get("phase") == "test":
            if lane is not None:
                raise Stop("prompt %s: the tester has no lane. run prompt without one" % lane)
            return self.test_prompt()
        if self.num("lanes") > 1 or lane is not None:
            with self.in_lane(self.lane_number(lane, "prompt")):
                return self.prompt_text()
        return self.prompt_text()

    def prompt_text(self):
        phase = self.get("phase")
        if phase == "ask":
            return self.ask_prompt()
        if phase not in ("build", "review"):
            raise NoPhase("no BUILD or REVIEW is pending for %s" % self.feature)
        try:
            if phase == "review" and self.get("review_pass") in ("quality", "single"):
                phase = "review-" + self.get("review_pass")
            if phase == "build" and self.get("batch"):
                return prompts.build(phase, self.scripts, self.feature, self.ticket(), self.get("num"), self.get("base"),
                                     ) + "\n" + self.batch_note() + "\n" + self.scout_findings()
            return prompts.build(phase, self.scripts, self.feature, self.ticket(), self.get("num"), self.get("base"),
                                 [n for n in self.get("review_notes").split(NOTE_SEP) + [self.get("edit_note")] if n]
                                 if phase != "build" else (),
                                 retry=self.num("round") > 0,
                                 workdir=(str(Path.cwd()), lanes.branch(self.feature, self.get("num"))) if self.lane else None
                                 ) + self.scout_findings()
        except FileNotFoundError as err:
            raise Stop(str(err))

    # ---- questions: a builder or reviewer asks the architect, designer or product owner --

    def ask_file(self, kind):
        """The question or answer of the pending ask, in the state folder (one pair per lane)."""
        return self.state_file.parent / ("ask-%s%s.%s" % (self.feature, "-L%d" % self.lane if self.lane else "", kind))

    def open_ask(self):
        """(role, question) of a `## Ask: <role>` section the builder appended to the ticket and nobody answered
        yet (no `## Consulted` section after it), else (None, "")."""
        try:
            text = Path(self.ticket()).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None, ""
        asks = list(ASK_HEADING.finditer(text))
        if not asks:
            return None, ""
        last = asks[-1]
        rest = text[last.end():]
        if re.search(r"^## Consulted\b", rest, re.MULTILINE):
            return None, ""
        return last.group(1), rest.split("\n## ", 1)[0].strip("\n")

    def hand_out_ask(self, source, role, question):
        """Pause the build or review and hand the question to its consultant. It is not a failed attempt. A
        question for the user, or one past MAX_ASKS, goes into the ticket as `## Ask: user` and stops the run."""
        if role == "user" or self.num("asks") >= MAX_ASKS:
            if role != "user":
                question = "(for the %s, but this ticket asked its consultants %d times already)\n\n%s" % (
                    role, MAX_ASKS, question)
            return self.ask_user(source, question)
        if source == "build":
            self.st["attempt"] = self.num("attempt") - 1
        else:
            self.st["review_attempt"] = self.num("review_attempt") - 1
        self.count_run()
        state.write_text(self.ask_file("question"), question.strip("\n") + "\n")
        state.remove(self.ask_file("answer"))
        self.st.update({"phase": "ask", "asks": self.num("asks") + 1, "ask_role": role, "ask_from": source,
                        "ask_attempt": 1, "verdict": "", "ask_sha": git.head()})
        self.save()
        return self.emit_ask()

    def disputes_tests(self):
        """True for a question from the builder of an acceptance fix ticket: it may dispute a tester's test."""
        return (self.get("ask_from") == "build" and bool(self.all.get("accept_num"))
                and self.get("num") == self.all.get("accept_num"))

    def emit_ask(self):
        return self.emit("ASK %s %s %s %s%s" % (self.get("ask_role"), self.ticket(), self.get("num"), self.get("base"),
                                                self.lane_word()))

    def ask_user(self, source, question):
        """Stop for the user. The question goes into the ticket as `## Ask: user` (once), which keeps the run
        stopped until the user answers under `## Consulted (user)`; the ticket is then built again."""
        role, _ = self.open_ask()
        if role != "user":
            tickets.append_section(self.ticket(), "Ask: user", demote(question))
            if source == "review":
                tickets.set_open(self.ticket())
            if not git.commit_file(self.ticket(), "chore(%s): %s question for the user" % (self.feature, self.get("num"))):
                raise Stop("cannot commit the question to %s. this session must be allowed to run git commit"
                           % self.ticket_name())
        self.st.update({"phase": "build", "attempt": min(self.num("attempt"), self.max_retries - 1)})
        self.save()
        where = " (in the lane folder %s)" % Path.cwd() if self.lane else ""
        raise Stop("%s asks you: %s. answer it at the end of %s%s under `## Consulted (user)`, commit, and run next%s"
                   % (self.ticket_name(), " ".join(question.split())[:600], proof.repo_relative(self.ticket()), where,
                      " %d" % self.lane if self.lane else ""))

    def record_answer(self, text):
        found = ""
        ruling = ""
        for line in text.splitlines():
            match = ANSWER.match(line)
            if match:
                found = match.group(1).lower()
            match = RULING.match(line)
            if match:
                ruling = match.group(1).lower()
        self.st["ruling"] = ruling
        if found:
            answer = section_after(text, "## Answer") or "\n".join(l for l in text.splitlines() if not ANSWER.match(l))
            lines = [l for l in demote(answer).strip("\n").splitlines() if not RULING.match(l)]
            state.write_text(self.ask_file("answer"), "\n".join(lines[:60]) + "\n")
        self.st["verdict"] = found or "none"
        self.save()
        self.log("ANSWER-%s" % (found or "none").upper())
        return "OK" if found else "RETRY no answer"

    def judge_ask(self):
        self.check_code()
        role = self.get("ask_role")
        note = self.undo_edit(self.get("ask_sha"), role, "a consultant")
        if note:
            self.edit_retry(note, self.num("ask_attempt"), "the %s for %s kept changing files" % (role, self.ticket_name()))
            verdict = "none"
        else:
            self.st["edit_note"] = ""
            verdict = self.get("verdict")
            if not verdict:
                raise NoPhase("no answer recorded from the %s for %s: save its whole reply to a file and run verdict "
                              "<that file>%s, then next" % (role, self.ticket_name(), self.lane_word()))
        self.st["verdict"] = ""
        if verdict not in ("given", "user"):
            if self.num("ask_attempt") >= self.max_retries:
                raise Stop("no answer from the %s for %s after %d attempt(s)" % (role, self.ticket_name(), self.max_retries))
            self.st["ask_attempt"] = self.num("ask_attempt") + 1
            self.count_run()
            self.save()
            return self.emit_ask()
        question = (state.read_text(self.ask_file("question")) or "").strip("\n")
        answer = (state.read_text(self.ask_file("answer")) or "").strip("\n")
        source = self.get("ask_from")
        self.log("ASK-%s-%s" % (role.upper(), verdict.upper()))
        if verdict == "user":
            return self.ask_user(source, "%s\n\nThe %s says only you can decide. Its options:\n\n%s" % (question, role, answer))
        if source == "review":
            self.st["phase"] = "review"
            notes = [n for n in self.get("review_notes").split(NOTE_SEP) if n]
            notes.append("you asked the %s: %s. the answer: %s" % (role, " ".join(question.split())[:400],
                                                                  " ".join(answer.split())[:1500]))
            self.st["review_notes"] = NOTE_SEP.join(notes)
            return self.hand_out_review()
        ruling = self.get("ruling")
        self.st["ruling"] = ""
        if ruling and self.disputes_tests():
            self.log("RULING-%s" % ruling.upper())
            if ruling == "test":
                self.all["accept_rulings"] = NOTE_SEP.join(
                    [r for r in self.all.get("accept_rulings", "").split(NOTE_SEP) if r]
                    + [" ".join(("%s THE PRODUCT OWNER: %s" % (question, answer)).split())[:2000]])
                answer += ("\n\nThe product owner ruled the test wrong: leave it failing and finish the rest. The tester "
                           "changes it once this ticket is resolved.")
        tickets.append_section(self.ticket(), "Consulted (%s)" % role,
                               "**Question:**\n\n%s\n\n**Answer:**\n\n%s" % (demote(question), answer))
        if not git.commit_file(self.ticket(), "chore(%s): %s answer from the %s" % (self.feature, self.get("num"), role)):
            raise Stop("cannot commit the %s's answer to %s. this session must be allowed to run git commit"
                       % (role, self.ticket_name()))
        self.st["phase"] = "build"
        return self.hand_out_build()

    def ask_prompt(self):
        role = self.get("ask_role")
        question = (state.read_text(self.ask_file("question")) or "").strip("\n")
        rel = proof.repo_relative(self.ticket())
        asker = {"build": "builder", "review": "reviewer"}.get(self.get("ask_from"), "builder")
        task = ("Your question comes from the %s of ticket %s of the feature `%s`. Read the plan in `%s` (`spec.md`, "
                "`map.md`, and the mock-ups if there are any) and the ticket as it was planned, with `git show %s:%s`. "
                "The work started at commit `%s`.\n\nThe question:\n\n%s\n\nDo not edit any file or create a "
                "commit. Your final reply must end with exactly `ANSWER: GIVEN` or `ANSWER: USER`."
                % (asker, self.get("num"), self.feature, self.plan.as_posix(), self.get("base"), rel, self.get("base"),
                   question))
        if role == "po" and self.disputes_tests():
            task += ("\n\nThe builder disputes an acceptance test. The tester wrote it from spec.md before the build, "
                     "without seeing the code. Rule on it from spec.md alone, not from what was built: put the line "
                     "`RULING: TEST WRONG` (the test asks for what spec.md does not say, and the tester changes it) or "
                     "`RULING: CODE WRONG` (the code must change to pass it) above your ANSWER line, and quote the "
                     "spec.md line you ruled by.")
        if self.get("edit_note"):
            task += "\n\nThe conductor notes: %s" % self.get("edit_note")
        if self.lane:
            task = ("Work in the folder `%s` (`cd %s` first): the worktree of this ticket. Every path here is relative "
                    "to it.\n\n%s" % (Path.cwd(), shlex.quote(str(Path.cwd())), task))
        try:
            role_text = prompts.role(self.scripts, prompts.ROLES["ask-" + role])
        except FileNotFoundError as err:
            raise Stop(str(err))
        return "%s\n\n---\n\n%s\n" % (role_text, task) + self.scout_findings()

    def consult_prompt(self, role, question_file):
        """A consultant's prompt for a question the planner raised. Stateless, like the other plan commands."""
        return Planner(self).consult_prompt(role, question_file)

    def brainstorm_prompt(self, helper, question_file):
        """A brainstorm helper's prompt. The script counts the helpers per brainstorm and refuses past the limit."""
        return Planner(self).brainstorm_prompt(helper, question_file)

    # ---- scouts: cheap read only helpers the session spawns before a role starts --

    def phase_key(self):
        """Names the phase handed out last, so scout replies saved for one phase never reach another."""
        if self.get("phase") == "final":
            return "final:%s:%s:%s" % (self.get("final_base"), self.num("final_round"), self.num("review_attempt"))
        return "%s:%s:%s:%s:%s:%s:%s:%s" % (self.get("phase"), self.get("num"), self.num("round"), self.num("attempt"),
                                            self.get("review_pass"), self.num("review_attempt"), self.num("asks"),
                                            self.num("ask_attempt"))

    def scout_slot(self):
        return "L%d" % self.lane if self.lane else ""

    def scout_questions(self):
        """[(agent, role, question)] for the phase handed out last: a build's first attempt above level 1 (or with
        no level), a level 3 ticket's first review, and the first round of the feature review."""
        if not self.scouts_on:
            return []
        phase = self.get("phase")
        tasks = "%s/%s" % (self.plan.as_posix(), os.environ.get("FLOW_TICKETS") or "tasks")
        if phase == "ask":
            question = (state.read_text(self.ask_file("question")) or "").strip("\n")
            return scouts.consult(self.get("ask_role"), question) if self.num("ask_attempt") == 1 else []
        if phase == "final":
            first = self.num("review_attempt") == 1 and not self.num("final_round")
            return scouts.review(self.get("final_base"), tasks) if first else []
        if self.num("round"):
            return []
        if self.num("asks"):  # resuming after a question: the first hand-out was scouted already
            return []
        if phase == "build" and self.num("attempt") == 1:
            return scouts.build(proof.repo_relative(self.ticket()), self.get("base"), lanes.touches(self.ticket_at_base()) or [],
                                self.num("level"))
        if (phase == "review" and self.num("level") == 3 and self.get("review_pass") in ("spec", "single")
                and self.num("review_attempt") == 1):
            return scouts.review(self.get("base"), tasks)
        return []

    def pending_phase(self, command, lane):
        """A context for the pending phase's state: the feature review's, the lane's, or the run's."""
        if self.all.get("phase") in ("final", "test"):
            if lane is not None:
                raise Stop("%s %s: the %s has no lane. run %s without one" % (
                    command, lane, "tester" if self.all.get("phase") == "test" else "feature review", command))
            return contextlib.nullcontext()
        if self.num("lanes") > 1 or lane is not None:
            return self.in_lane(self.lane_number(lane, command))
        return contextlib.nullcontext()

    def scouts(self, lane=None):
        """`SCOUT <k> <agent> <reply file>` lines for the phase handed out last, or NONE. Clears old replies."""
        self.check_owner()
        with self.pending_phase("scouts", lane):
            if self.get("phase") not in ("build", "review", "final", "ask"):
                raise NoPhase("no BUILD or REVIEW is pending for %s" % self.feature)
            found = self.scout_questions()
            folder = self.state_file.parent
            scouts.clear(folder, self.feature, self.scout_slot())
            self.st["scout_key"] = self.phase_key()
            self.st["scout_n"] = len(found)
            self.save()
            if found:
                self.log("SCOUTS-%d" % len(found))
            return scouts.listing(folder, self.feature, self.scout_slot(), found)

    def scout_prompt(self, k, lane=None):
        """The whole prompt of scout k for the phase handed out last."""
        self.check_owner()
        with self.pending_phase("scout-prompt", lane):
            if self.get("scout_key") != self.phase_key():
                raise NoPhase("run scouts first: no scouts are listed for the phase pending for %s" % self.feature)
            return self.one_scout(self.scout_questions(), k, str(Path.cwd()) if self.lane else None)

    def one_scout(self, found, k, workdir=None):
        if not k.isdigit() or not 1 <= int(k) <= len(found):
            raise Stop("no scout %s: there are %d" % (k, len(found)))
        agent, role, question = found[int(k) - 1]
        try:
            role_text = prompts.role(self.scripts, agent + ".md")
        except FileNotFoundError as err:
            raise Stop(str(err))
        return scouts.prompt(role_text, role, question, workdir)

    def scout_findings(self):
        """The scout replies saved for the phase handed out last, as a section for its prompt, or ""."""
        if self.get("scout_key") != self.phase_key():
            return ""
        return scouts.section(self.state_file.parent, self.feature, self.scout_slot(), self.num("scout_n"))

    def plan_scouts(self, brief):
        """The scouts before planning: saves the brief and lists `SCOUT` lines as `scouts` does."""
        return Planner(self).plan_scouts(brief)

    def plan_scout_prompt(self, k):
        return Planner(self).plan_scout_prompt(k)

    def final_prompt(self):
        nums = [num for num, _ in self.deferred()]
        try:
            return prompts.feature_review(self.scripts, self.feature, self.plan.as_posix(), self.all["final_base"], nums,
                                          [n for n in [self.final_note(), self.all.get("edit_note", "")] if n],
                                          os.environ.get("FLOW_TICKETS") or "tasks") + self.scout_findings()
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
        if self.all.get("phase") == "test":
            raise NoPhase("the tester has no verdict: the conductor judges its tests itself. run next")
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
        if self.get("phase") not in ("review", "final", "ask"):
            raise NoPhase("no review is pending for %s" % self.feature)
        try:
            text = Path(reply).read_text(encoding="utf-8", errors="replace")
        except OSError as err:
            raise Stop("cannot read the review reply %s: %s" % (reply, err.strerror))
        if self.get("phase") == "ask":
            return self.record_answer(text)
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
            self.st["level_note"] = levels.describe(asked, "a reviewer raised it")
            self.st["level_raised"] = "1" if asked == 3 else ""
            notes = [n for n in self.get("review_notes").split(NOTE_SEP) if n and not n.startswith("this ticket is level")]
            self.st["review_notes"] = NOTE_SEP.join([self.st["level_note"]] + notes)
            self.log("LEVEL-RAISE")
        if found.startswith("ask"):
            role = found.split()[1]
            question = section_after(text, "## Question") or "\n".join(text.splitlines()[-40:])
            if self.get("phase") == "final":  # no ticket to pause: the fix ticket's builder asks
                found = "fail"
                text = ("The feature reviewer could not judge this without an answer from the %s:\n\n%s\n\nAsk it in "
                        "this ticket with `## Ask: %s`." % (role, question, role))
            else:
                state.write_text(self.ask_file("question"), question + "\n")
                found = "ask:" + role
        if found == "fail":
            state.write_text(self.findings_file, "\n".join(text.splitlines()[:120]) + "\n", "findings")
        if found == "pass":
            source = "feature review" if self.get("phase") == "final" else "%s review" % self.get("review_pass", "spec")
            self.st["reply_minors"] = NOTE_SEP.join("%s (%s)" % (" ".join(line.split()), source)
                                                    for line in text.splitlines() if FINDING.match(line))
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
        return [k for k in range(1, MAX_LANES + 1) if self.lane_key(k, "phase") in ("build", "review", "ask", "merge")]

    @contextlib.contextmanager
    def in_lane(self, lane):
        """Run the per-ticket code on lane's state, in its worktree, and come back to the top of the repo."""
        path = self.lane_dir(lane)
        if not lanes.is_worktree(self.top, path):
            raise Stop("lane %d (%s) is gone. run reset to drop the lanes and start again" % (lane, path))
        saved = self.st, self.lane
        self.st, self.lane = TicketState(self.all, lane), lane
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
        mode_ok("lanes_relay", lanes=self.num("lanes"), relay=self.relay)
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
            if phase in ("build", "review", "ask"):
                name = lanes.branch(self.feature, self.get("num"))
                on = git._git("symbolic-ref", "-q", "--short", "HEAD", check=False).stdout.strip()
                if on != name:
                    raise Stop("lane %d is on %s, not on its ticket's branch %s. a builder or reviewer must not switch "
                               "it. run reset to drop the lanes" % (k, on or "a detached HEAD", name))
            if phase == "build":
                line = self.judge_build()
            elif phase == "review":
                line = self.judge_review()
            elif phase == "ask":
                line = self.judge_ask()
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
        if not busy and self.tests_due():
            return self.hand_out_test()
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
            if not busy:
                self.check_replan()
            self.check_budget(offer=not busy)  # a stop while lanes work would strand them
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
        level, _ = levels.declared(text, "flow-edit" in floorguard.allow_line(text).split())
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
        line = self.check_acceptance()
        if line is not None:
            return line
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

    def plan_prompt(self, brief, findings=None):
        """The feature-planner's prompt. Saves the brief; a first round (no findings) starts an empty draft."""
        return Planner(self).plan_prompt(brief, findings)

    def plan_review_prompt(self):
        """The plan-reviewer's prompt: the saved brief and the draft, nothing from the planner."""
        return Planner(self).plan_review_prompt()

    def plan_accept(self):
        """Copy a draft that passes the check into the plan folder. Never overwrites, never commits."""
        return Planner(self).plan_accept()
