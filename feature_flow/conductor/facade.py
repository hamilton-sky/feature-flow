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

from feature_flow import checks, codehash, git, prompts, scouts, state, suggest, tickets
from feature_flow.conductor import budget as time_budget
from feature_flow.conductor import guards
from feature_flow.conductor.errors import NoPhase, Stop
from feature_flow.conductor.phases import REGISTRY
from feature_flow.conductor.planning import BRAINSTORM, Planner
from feature_flow.conductor.policy.review import FULL_ROUNDS, followups_only
from feature_flow.conductor.replies import demote, section_after  # the package exports them
from feature_flow.conductor.schedulers import BatchScheduler, LaneScheduler
from feature_flow.conductor.settings import Settings, _env_int, mode_ok
from feature_flow.conductor.store import RunState
from feature_flow.conductor.workspace import Workspace


OLD_OWNER = re.compile(r"^[0-9a-f]{16}$")  # a raw token, stored by a run started before 0.5.0


def owner_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Conductor(Workspace):
    """The facade of the CLI commands, and the main worktree's Workspace."""

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
        Workspace.__init__(self, self)  # the main worktree: the run's state view, no lane
        self.per_session = settings.session_limit(self.driver())  # an agent driver: no handoffs
        self.sched = None  # the scheduler, picked once per call by scheduler()

    # ---- small helpers -------------------------------------------------

    def driver(self):
        """Who drives the run: "agent" (an orchestrating agent, FLOW_DRIVER=agent on start) or "person"."""
        return os.environ.get("FLOW_DRIVER") or self.all.get("driver") or "person"

    # ---- the checks ----------------------------------------------------

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

    # ---- phases --------------------------------------------------------

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

    # ---- the fast path: reviews deferred to one review of the whole feature --

    def fast(self):
        return self.all.get("fast") == "1"

    def deferred(self):
        """[(NN, base)] of the tickets that passed their checks in fast mode without a review of their own."""
        return [tuple(item.split(":", 1)) for item in self.all.get("deferred", "").split() if ":" in item]

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

    # ---- commands ------------------------------------------------------

    def handoff(self):
        """Release the owner; the user continues in a new session with the printed line."""
        self.all["owner"] = ""
        self.all["relay_handoff"] = ""
        self.save()
        return self.emit("HANDOFF %s %s" % (self.invoke, self.feature))

    def check_owner(self):
        """While a session owns the feature, every call must carry its token. Checked before any change."""
        owner = self.get("owner")
        token = os.environ.get("FLOW_SESSION", "")
        if not owner or owner_hash(token) == owner:
            return
        if OLD_OWNER.match(owner) and token == owner:
            self.all["owner"] = owner_hash(token)  # stored as the hash on the next save
            return
        raise Stop("%s is owned by another session (%s). pass its token as FLOW_SESSION, or start this session "
                   "with FLOW_TAKEOVER=1 once you are sure the other one is closed" % (self.feature, owner[:8]))

    # ---- the time budget: fast mode when over, then a re-plan the user says yes to --

    def num_all(self, key):
        return self.all.num(key)

    def budget_cmd(self, value=None):
        """`budget` reports; `budget <minutes>|+<minutes>|off` sets it between phases."""
        return time_budget.budget_cmd(self, value)

    def replan_prompt(self):
        """The feature-planner's prompt to fold the open tickets into fewer. Only between tickets."""
        self.check_owner()
        if not self.plan.is_dir():
            raise Stop("no plan folder %s" % self.plan)
        if self.all.get("phase") or self.lane_sched().busy_lanes():
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
        busy = self.lane_sched().busy_lanes()
        if busy and wanted != self.num("lanes"):
            raise Stop("lane(s) %s still hold tickets from the last session, which ran with FLOW_LANES=%d. start with "
                       "that, or reset to drop them" % (",".join(map(str, busy)), self.num("lanes")))
        driver = os.environ.get("FLOW_DRIVER", "")
        mode_ok("driver", driver=driver)
        token = secrets.token_hex(8)
        if driver:
            self.all["driver"] = driver
        self.all["owner"] = owner_hash(token)
        self.all["session_done"] = 0
        self.all["lanes"] = wanted if wanted > 1 else ""
        fast = os.environ.get("FLOW_FAST", "")
        mode_ok("fast", fast=fast)
        if fast:
            self.all["fast"] = "1" if fast == "1" else ""
        budget = os.environ.get("FLOW_BUDGET", "")
        if budget:
            time_budget.set_budget(self, budget)
        self.all["seen"] = int(time.time())  # the time between sessions is not spent on the feature
        self.save()
        self.log("TAKEOVER" if takeover else "START")
        self.log("DRIVER-%s" % self.driver().upper())
        if self.profile:
            self.log("PROFILE-%s" % self.profile.upper())
        return "OK %s" % token

    def next(self, lane=None):
        self.check_owner()
        time_budget.tick(self)
        wide = self.run_wide("next", lane)
        if wide is not None:
            if not self.plan.is_dir():
                raise Stop("no plan folder %s" % self.plan)
            line = guards.after_phase(self)
            if line is not None:
                return line
            return wide.judge(self).line
        if self.scheduler().lanes:
            return self.scheduler().next(lane)
        if lane is not None:
            raise Stop("next %s: this run has no lanes (start it with FLOW_LANES=2 or more for lanes)" % lane)
        if self.get("restore"):
            try:
                git._git("checkout", "-q", self.get("restore"))
            except RuntimeError as err:
                raise Stop("cannot put the working copy back after the test first check: %s. run `git checkout %s` "
                           "by hand" % (err, self.get("restore")))
            self.all["restore"] = ""
            self.save()
        if self.get("batch_restore"):
            try:
                git._git("checkout", "-q", self.get("batch_restore"))
            except RuntimeError as err:
                raise Stop("cannot go back to %s after judging a batch: %s. run `git checkout %s` by hand"
                           % (self.get("batch_restore"), err, self.get("batch_restore")))
            self.all["batch_restore"] = ""
            self.save()
        if not self.plan.is_dir():
            raise Stop("no plan folder %s" % self.plan)
        line = guards.after_phase(self)
        if line is not None:
            return line
        if "limit" not in self.all:
            self.all["limit"] = self.run_limit()
            self.all.setdefault("runs", 0)
            self.all.setdefault("done", 0)
        phase = REGISTRY.get(self.get("phase"))
        if phase is not None:
            return phase.judge(self).line
        return self.scheduler().next(lane)

    def scheduler(self):
        """The scheduler of this call, picked once: lanes, else one ticket at a time (a batch when it may be)."""
        if self.sched is None:
            self.sched = LaneScheduler(self) if self.num_all("lanes") > 1 else BatchScheduler(self)
        return self.sched

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
        dropped = self.lane_sched().drop_lanes()
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
        Workspace.__init__(self, self)
        if kept:
            self.save()
        self.log("RESET")
        done = ["cleared the run state"] if had_run else []
        if kept.get("deferred"):
            done.append("kept %d ticket(s) built in fast mode for the feature review" % len(self.deferred()))
        done += dropped
        done += ["reopened %s" % tickets.name(p) for p in reopened]
        return "OK %s. run %s %s" % (", ".join(done), self.invoke, self.feature)

    def prompt(self, lane=None):
        """The full prompt for the BUILD or REVIEW that `next` handed out. Exit 2 (NoPhase) when none is."""
        self.check_owner()
        wide = self.run_wide("prompt", lane)
        if wide is not None:
            return wide.prompt(self)
        with self.pending_phase("prompt", lane) as ws:
            return ws.prompt_text()

    def consult_prompt(self, role, question_file):
        """A consultant's prompt for a question the planner raised. Stateless, like the other plan commands."""
        return Planner(self).consult_prompt(role, question_file)

    def brainstorm_prompt(self, helper, question_file):
        """A brainstorm helper's prompt. The script counts the helpers per brainstorm and refuses past the limit."""
        return Planner(self).brainstorm_prompt(helper, question_file)

    # ---- scouts: cheap read only helpers the session spawns before a role starts --

    def pending_phase(self, command, lane):
        """A context with the Workspace of the pending phase: the run's (the feature review's too), or the lane's."""
        if self.run_wide(command, lane) is not None:
            return contextlib.nullcontext(self)
        if self.scheduler().lanes or lane is not None:
            sched = self.lane_sched()
            return sched.workspace(sched.lane_number(lane, command)).entered()
        return contextlib.nullcontext(self)

    def scouts(self, lane=None):
        """`SCOUT <k> <agent> <reply file>` lines for the phase handed out last, or NONE. Clears old replies."""
        self.check_owner()
        with self.pending_phase("scouts", lane) as ws:
            if ws.get("phase") not in REGISTRY:
                raise NoPhase("no BUILD or REVIEW is pending for %s" % self.feature)
            found = ws.scout_questions()  # the tester's raises NoPhase: it gets no scouts
            folder = self.state_file.parent
            scouts.clear(folder, self.feature, ws.scout_slot())
            ws.st["scout_key"] = ws.phase_key()
            ws.st["scout_n"] = len(found)
            ws.save()
            if found:
                ws.log("SCOUTS-%d" % len(found))
            return scouts.listing(folder, self.feature, ws.scout_slot(), found)

    def scout_prompt(self, k, lane=None):
        """The whole prompt of scout k for the phase handed out last."""
        self.check_owner()
        with self.pending_phase("scout-prompt", lane) as ws:
            if ws.get("scout_key") != ws.phase_key():
                raise NoPhase("run scouts first: no scouts are listed for the phase pending for %s" % self.feature)
            return self.one_scout(ws.scout_questions(), k, str(Path.cwd()) if ws.lane else None, ws.prompts_top)

    def one_scout(self, found, k, workdir=None, top="."):
        if not k.isdigit() or not 1 <= int(k) <= len(found):
            raise Stop("no scout %s: there are %d" % (k, len(found)))
        agent, role, question = found[int(k) - 1]
        try:
            role_text = prompts.role(self.scripts, agent + ".md", top)
        except FileNotFoundError as err:
            raise Stop(str(err))
        return scouts.prompt(role_text, role, question, workdir)

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
        if self.scheduler().lanes or lane is not None:
            sched = self.lane_sched()
            k = sched.lane_number(lane, "verdict")
            with sched.workspace(k).entered() as ws:
                line = ws.pending().record(ws, reply)
            self.all["findings_for"] = str(k)
            self.save()
            return line
        return self.pending().record(self, reply)

    # ---- lanes: tickets side by side in their own worktrees ---------------

    def lane_sched(self):
        """The lane scheduler: this call's in a lane run, else one for the lane checks, start and reset."""
        sched = self.scheduler()
        return sched if sched.lanes else LaneScheduler(self)

    def show_head(self, path):
        """path's text at HEAD of the main worktree, or "" when it is not there."""
        try:
            return git.show_text("HEAD:%s" % Path(path).as_posix())
        except RuntimeError:
            return ""

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
