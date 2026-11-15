"""Repair mode: a plan repair measured against the plan it started from (its baseline: the plan folder at repair_sha,
whose tree replan-prompt recorded as repair_plan), the `repair-check` command, and consults on the existing plan while a
repair is pending. The comparison itself is feature_flow/repaircheck.py."""

import os
import re

from feature_flow import git, proof, repaircheck
from feature_flow.conductor.errors import Stop
from feature_flow.conductor.planning import Planner


def plan_rel(c):
    """The plan folder relative to the top of the repo, POSIX."""
    return proof.repo_relative(c.plan).rstrip("/")


def repair_problems(c):
    """(the report lines, clean) of the pending repair against the plan it started from (the repair's baseline:
    the plan at repair_sha, whose tree replan-prompt recorded). Stops when the baseline cannot be told."""
    sha, tree = c.all.get("repair_sha"), c.all.get("repair_plan")
    if not sha:
        raise Stop("no plan repair is pending for %s. run replan-prompt repair first" % c.feature)
    now = repaircheck.plan_tree(sha, plan_rel(c))
    if not tree or now != tree:
        raise Stop("cannot tell the repair's baseline: the plan at %s is %s, and the repair recorded %s. run "
                   "replan-prompt repair again to start the repair from the plan as it is"
                   % (sha[:12], (now or "missing")[:12], (tree or "nothing")[:12]))
    try:
        found = repaircheck.compare(plan_rel(c), sha, cwd=str(c.top))
    except repaircheck.BaselineError as err:
        raise Stop("cannot read the repair's baseline: %s" % err)
    return found, repaircheck.lines(found, sha, tree)


def repair_check(c):
    """`repair-check`: the repaired plan against its baseline, before the session shows it to the user and commits
    it: the footprint each ticket gains or loses, the problems the plan already had (shown, never blocking) and the
    ones the repair adds (blocking), and whether a resolved ticket changed. Changes nothing."""
    c.check_owner()
    found, (report, clean) = repair_problems(c)
    resolved = resolved_changed(c, c.all["repair_sha"], worktree=True)
    if resolved:
        report.insert(-1, "resolved ticket changed: %s (put it back: git checkout %s -- %s)"
                      % (resolved, c.all["repair_sha"][:12], resolved))
        clean = False
    c.log("REPAIR-CHECK-%s" % ("OK" if clean else "BLOCKED"))
    head = "OK repair check of %s" % c.feature if clean else "BLOCKED repair check of %s" % c.feature
    return "\n".join([head] + report)


def resolved_changed(c, sha, worktree=False):
    """The first ticket file that was resolved at sha and differs now (in HEAD, or with worktree the working tree),
    or None."""
    folder = (c.plan / (os.environ.get("FLOW_TICKETS") or "tasks")).as_posix()
    args = ("diff", "--name-only", sha) + (() if worktree else ("HEAD",)) + ("--", folder)
    for path in git._git(*args, check=False).stdout.split():
        try:
            before = git.show_text("%s:%s" % (sha, path))
        except RuntimeError:
            continue  # a new ticket
        if re.search(r"^Status:[ \t]*(resolved|done|closed)\b", before, re.MULTILINE | re.IGNORECASE):
            return path
    return None


def committed(c):
    """After the repaired plan is committed: stop while it adds problems the baseline did not have (repair_sha stays,
    so the next `next` checks again), else log each ticket's footprint move and how many problems it inherited."""
    sha = c.all["repair_sha"]
    found, (report, clean) = repair_problems(c)
    if not clean:
        c.log("REPAIR-BLOCKED")
        raise Stop("the plan repair adds problems the plan did not have: %s. fix them in a new commit (the "
                   "inherited ones stay as they are); `python3 scripts/flow-status.py %s --lint --baseline %s` "
                   "lists both" % ("; ".join(found["new"][0] + found["new"][1])[:600], c.feature, sha[:12]))
    for line in found["footprint"]:
        c.log("REPAIR-FOOTPRINT " + " ".join(line.split())[:200])
    kept = len(found["inherited"][0]) + len(found["inherited"][1])
    if kept:
        c.log("REPAIR-INHERITED %d" % kept)


def consult_prompt(c, role, question_file):
    """A consultant's prompt on the plan that exists, while a repair is pending; before that, what to run first."""
    c.check_owner()
    if not c.all.get("repair_sha"):
        raise Stop("%s exists, and a consult on an existing plan is for repairing it: run replan-prompt repair "
                   "first, then consult-prompt with the planner's question" % c.plan.as_posix())
    return Planner(c).consult_prompt(role, question_file, repair=c.ticket() if c.all.get("phase") else "")
