"""The state machine that tells an interactive session what to do next.

It sets the limits, retries and review rounds. It judges every phase from the repo, never from the
caller, and prints exactly one line per command.
"""

import contextlib
import hashlib
import os
import re
import secrets
import time
from pathlib import Path

from feature_flow import checks, codehash, floorguard, gate, git, lanes, prompts, proof, scouts, state, suggest, tickets
from feature_flow.conductor.errors import NoPhase, Stop
from feature_flow.conductor.phases import REGISTRY, Phase
from feature_flow.conductor.phases.build import Build
from feature_flow.conductor.phases.review import Review
from feature_flow.conductor.phases.test import Test
from feature_flow.conductor.planning import BRAINSTORM, Planner
from feature_flow.conductor.policy import levels, limits
from feature_flow.conductor.policy.levels import CONVERT
from feature_flow.conductor.policy.review import FINDING, FULL_ROUNDS, followups_only
from feature_flow.conductor.replies import demote, section_after  # the package exports them
from feature_flow.conductor.schedulers import BatchScheduler, FacadeLanes
from feature_flow.conductor.settings import MAX_LANES, Settings, _env_int, mode_ok
from feature_flow.conductor.store import NOTE_SEP, RunState, TicketState


OLD_OWNER = re.compile(r"^[0-9a-f]{16}$")  # a raw token, stored by a run started before 0.5.0
GAP = 3600  # most seconds one step adds to the time spent: a longer pause is the user away, not work


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
        self.sched = None  # the scheduler, picked once per call by scheduler()

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
        return Build.hand_out(self)

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
        return self.scheduler().on_passed(self)

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
        wide = self.run_wide("next", lane)
        if wide is not None:
            if not self.plan.is_dir():
                raise Stop("no plan folder %s" % self.plan)
            if self.get("relay_handoff") == "1":
                return self.handoff()
            return wide.judge(self).line
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
        phase = REGISTRY.get(self.get("phase"))
        if phase is not None:
            return phase.judge(self).line
        return self.scheduler().next(lane)

    def scheduler(self):
        """The scheduler of this call, picked once: lanes, else one ticket at a time (a batch when it may be)."""
        if self.sched is None:
            self.sched = FacadeLanes(self) if self.num_all("lanes") > 1 else BatchScheduler(self)
        return self.sched

    def pending(self):
        """The class of the phase pending in this view of the state: Phase, whose defaults do nothing, for none."""
        return REGISTRY.get(self.get("phase"), Phase)

    def run_wide(self, command, lane):
        """The class of the run-wide phase (the tester, the feature review) pending, else None. It has no lane."""
        phase = REGISTRY.get(self.all.get("phase"))
        if phase is None or phase.lane_scoped:
            return None
        if lane is not None:
            raise Stop("%s %s: the %s has no lane. run %s without one" % (command, lane, phase.who, command))
        return phase

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

    def prompt(self, lane=None):
        """The full prompt for the BUILD or REVIEW that `next` handed out. Exit 2 (NoPhase) when none is."""
        self.check_owner()
        wide = self.run_wide("prompt", lane)
        if wide is not None:
            return wide.prompt(self)
        if self.num("lanes") > 1 or lane is not None:
            with self.in_lane(self.lane_number(lane, "prompt")):
                return self.prompt_text()
        return self.prompt_text()

    def prompt_text(self):
        phase = self.pending()
        if not phase.lane_scoped:
            raise NoPhase("no BUILD or REVIEW is pending for %s" % self.feature)
        return phase.prompt(self)

    def consult_prompt(self, role, question_file):
        """A consultant's prompt for a question the planner raised. Stateless, like the other plan commands."""
        return Planner(self).consult_prompt(role, question_file)

    def brainstorm_prompt(self, helper, question_file):
        """A brainstorm helper's prompt. The script counts the helpers per brainstorm and refuses past the limit."""
        return Planner(self).brainstorm_prompt(helper, question_file)

    # ---- scouts: cheap read only helpers the session spawns before a role starts --

    def phase_key(self):
        """Names the phase handed out last, so scout replies saved for one phase never reach another."""
        return self.pending().key(self)

    def scout_slot(self):
        return "L%d" % self.lane if self.lane else ""

    def scout_questions(self):
        """[(agent, role, question)] for the phase handed out last: a build's first attempt above level 1 (or with
        no level), a level 3 ticket's first review, and the first round of the feature review."""
        return self.pending().scout_questions(self)

    def pending_phase(self, command, lane):
        """A context for the pending phase's state: the feature review's, the lane's, or the run's."""
        if self.run_wide(command, lane) is not None:
            return contextlib.nullcontext()
        if self.num("lanes") > 1 or lane is not None:
            return self.in_lane(self.lane_number(lane, command))
        return contextlib.nullcontext()

    def scouts(self, lane=None):
        """`SCOUT <k> <agent> <reply file>` lines for the phase handed out last, or NONE. Clears old replies."""
        self.check_owner()
        with self.pending_phase("scouts", lane):
            if self.get("phase") not in REGISTRY:
                raise NoPhase("no BUILD or REVIEW is pending for %s" % self.feature)
            found = self.scout_questions()  # the tester's raises NoPhase: it gets no scouts
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

    def verdict(self, reply, lane=None):
        """Record the reviewer's reply. Exit 2 (NoPhase) unless a review is pending."""
        self.check_owner()
        reply = Path(reply).resolve()
        wide = REGISTRY.get(self.all.get("phase"))
        if wide is not None and not wide.lane_scoped:
            if wide.takes_verdict:
                if lane is not None:
                    raise Stop("verdict for lane %s: the %s has no lane. run verdict without one" % (lane, wide.who))
                self.all["findings_for"] = ""
            return wide.record(self, reply)
        if self.num("lanes") > 1 or lane is not None:
            k = self.lane_number(lane, "verdict")
            with self.in_lane(k):
                line = self.pending().record(self, reply)
            self.all["findings_for"] = str(k)
            self.save()
            return line
        return self.pending().record(self, reply)

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
            if phase in ("build", "review", "ask"):
                line = REGISTRY[phase].judge(self).line
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
        if not busy and self.scheduler().end.tests_due():
            return Test.hand_out(self)
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
            return self.scheduler().end.finish()
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
            self.scheduler().start_ticket(path)
            self.log("LEASE-%d" % k)
            return Build.hand_out(self)

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
                return Review.hand_out(self)
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
            self.scheduler().start_ticket(path)
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
            return Build.hand_out(self)

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
