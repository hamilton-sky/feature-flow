"""The checks around a ticket. BEFORE_TICKET: what both schedulers run before a ticket starts, in order, the first
that stops or hands off winning (the session handoff, the re-plan check, the budget; then, once start_ticket has
snapshotted the code, the smoke test). AFTER_PHASE: the relay, a handoff after each phase handed out, checked by
next before it judges anything. Also the owner check every command makes, the handoff, and the re-plan prompt."""

import hashlib
import os
import re
from pathlib import Path

from feature_flow import checks, gate, git, prompts, tickets
from feature_flow.conductor import budget, planning
from feature_flow.conductor.errors import Stop
from feature_flow.conductor.settings import _env_int, mode_ok


OLD_OWNER = re.compile(r"^[0-9a-f]{16}$")  # a raw token, stored by a run started before 0.5.0


def owner_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def check_owner(c):
    """While a session owns the feature, every call must carry its token. Checked before any change."""
    owner = c.get("owner")
    token = os.environ.get("FLOW_SESSION", "")
    if not owner or owner_hash(token) == owner:
        return
    if OLD_OWNER.match(owner) and token == owner:
        c.all["owner"] = owner_hash(token)  # stored as the hash on the next save
        return
    raise Stop("%s is owned by another session (%s). pass its token as FLOW_SESSION, or start this session "
               "with FLOW_TAKEOVER=1 once you are sure the other one is closed" % (c.feature, owner[:8]))


def before_start(c):
    """start's checks before it takes the feature: the owner (FLOW_TAKEOVER), the lanes, the driver. Returns
    (takeover, the FLOW_LANES wanted, FLOW_DRIVER)."""
    owner = c.get("owner")
    takeover = bool(owner)
    if owner and os.environ.get("FLOW_TAKEOVER", "0") != "1":
        raise Stop("%s is owned by session %s. if that session is closed or dead, run start with FLOW_TAKEOVER=1"
                   % (c.feature, owner[:8]))
    wanted = _env_int("FLOW_LANES", 1)
    mode_ok("lanes_range", lanes=wanted)
    mode_ok("lanes_relay", lanes=wanted, relay=c.relay)
    mode_ok("lanes_top", lanes=wanted, cwd=Path.cwd().resolve(), top=c.top)
    busy = c.lane_sched().busy_lanes()
    if busy and wanted != c.num("lanes"):
        raise Stop("lane(s) %s still hold tickets from the last session, which ran with FLOW_LANES=%d. start with "
                   "that, or reset to drop them" % (",".join(map(str, busy)), c.num("lanes")))
    driver = os.environ.get("FLOW_DRIVER", "")
    mode_ok("driver", driver=driver)
    return takeover, wanted, driver


def handoff(c):
    """Release the owner; the user continues in a new session with the printed line."""
    c.all["owner"] = ""
    c.all["relay_handoff"] = ""
    c.save()
    return c.emit("HANDOFF %s %s" % (c.invoke, c.feature))


def replan_prompt(c):
    """The feature-planner's prompt to fold the open tickets into fewer. Only between tickets."""
    c.check_owner()
    if not c.plan.is_dir():
        raise Stop("no plan folder %s" % c.plan)
    if c.all.get("phase") or c.lane_sched().busy_lanes():
        raise Stop("a ticket is in progress. run replan-prompt between tickets, when next would start a new one")
    folder = c.plan / (os.environ.get("FLOW_TICKETS") or "tasks")
    paths = tickets.ticket_files(str(folder))
    open_ones = [p for p in paths if tickets.status(p) not in tickets.DONE + ("parked", "wontfix")]
    if len(open_ones) < 2:
        raise Stop("%d open ticket(s) left, nothing to fold together" % len(open_ones))
    c.all["replan_sha"] = git.head()
    c.save()
    c.log("REPLAN-PROMPT")
    try:
        return prompts.replan(c.scripts, c.feature, c.plan.as_posix(),
                              [Path(p).as_posix() for p in open_ones], (c.plan / planning.BRAINSTORM).is_file())
    except FileNotFoundError as err:
        raise Stop(str(err))


def check_replan(c):
    """After a re-plan was handed out: the resolved tickets must be as they were, and the plan committed."""
    sha = c.all.get("replan_sha")
    if not sha:
        return
    folder = (c.plan / (os.environ.get("FLOW_TICKETS") or "tasks")).as_posix()
    changed = git._git("diff", "--name-only", sha, "HEAD", "--", folder, check=False).stdout.split()
    for path in changed:
        try:
            before = git.show_text("%s:%s" % (sha, path))
        except RuntimeError:
            continue  # a new ticket
        if re.search(r"^Status:[ \t]*(resolved|done|closed)\b", before, re.MULTILINE | re.IGNORECASE):
            raise Stop("the re-plan changed %s, which was resolved before it. put it back with `git checkout %s "
                       "-- %s` and commit" % (path, sha[:12], path))
    c.all["replan_sha"] = ""
    if changed:
        c.log("REPLAN")


def smoke_command(c):
    cmd = os.environ.get("FLOW_SMOKE", "")
    if not cmd:
        cmd = tickets.commands_value(c.at(c.commands), "Smoke")
    return "" if cmd.startswith("<") else cmd


def run_smoke(c):
    cmd = smoke_command(c)
    if not cmd:
        return
    result = checks.smoke(cmd, c.gate_timeout, cwd=c.folder)
    if not result.ok:
        log = c.state_file.with_name("%s.smoke.log" % c.feature)
        text = result.out
        if result.timed_out:
            text += "\nsmoke test timed out after %d minutes\n" % c.gate_timeout
        log.write_text(gate.tail(text), encoding="utf-8")
        raise Stop("smoke test %s before %s: the base is already broken. fix it first. command: %s. "
                   "the last %d lines are in %s"
                   % ("timed out after %d minutes" % c.gate_timeout if result.timed_out else "failed",
                      c.ticket_name(), cmd, gate.TAIL, log))


class Guard:
    """run(c, busy) is None to go on, or the line to print instead of starting a ticket; a Stop stops the run.
    busy lists the lanes that hold a ticket (always empty one ticket at a time). stage says when it runs: "pick"
    before the scheduler picks the ticket, "start" once start_ticket has set the ticket up."""

    name = ""
    stage = "pick"

    def run(self, c, busy):
        raise NotImplementedError


class SessionHandoff(Guard):
    """FLOW_TICKETS_PER_SESSION reached (busy lanes count): hand off, or with lanes still busy, wait for them."""

    name = "session"

    def run(self, c, busy):
        if c.per_session > 0 and c.num("session_done") + len(busy) >= c.per_session:
            return c.emit("WAIT %s" % ",".join(map(str, busy))) if busy else c.handoff()
        return None


class Replan(Guard):
    """The re-plan check, only with no lane busy."""

    name = "replan"

    def run(self, c, busy):
        if not busy:
            check_replan(c)
        return None


class Budget(Guard):
    """The time budget; its re-plan offer only with no lane busy, as a stop while lanes work would strand them."""

    name = "budget"

    def run(self, c, busy):
        budget.check_budget(c, offer=not busy)
        return None


class Smoke(Guard):
    """The smoke test, after the code snapshot of start_ticket."""

    name = "smoke"
    stage = "start"

    def run(self, c, busy):
        run_smoke(c)
        return None


BEFORE_TICKET = (SessionHandoff(), Replan(), Budget(), Smoke())


def before_ticket(c, busy=(), stage="pick", only=None):
    """Run the guards of stage (those named in only, when given) in BEFORE_TICKET's order: the first line one
    returns, else None."""
    busy = list(busy)
    for guard in BEFORE_TICKET:
        if guard.stage != stage or (only is not None and guard.name not in only):
            continue
        line = guard.run(c, busy)
        if line is not None:
            return line
    return None


def mark_relay(c, view):
    """A phase is handed out: with FLOW_RELAY=1, the next call hands off before it judges it."""
    view["relay_handoff"] = "1" if c.relay else ""


class Relay:
    """FLOW_RELAY=1: a handoff after each phase handed out."""

    name = "relay"

    def run(self, c):
        return c.handoff() if c.get("relay_handoff") == "1" else None


AFTER_PHASE = (Relay(),)


def after_phase(c):
    """Before next judges the phase handed out: the first line an AFTER_PHASE guard returns, else None."""
    for guard in AFTER_PHASE:
        line = guard.run(c)
        if line is not None:
            return line
    return None
