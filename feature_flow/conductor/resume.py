"""`resume [NN] [--from <commit>]`: carry on after an upgrade, a change to the flow's code, or a reset, without
losing where the ticket started.

A ticket's base (the commit its work starts after) is what the test-first check, the footprint, the floor guard
and the review all measure from. A reset forgets it and the next start takes HEAD, so the ticket's own earlier
commits stop counting, and its failing test commit can no longer be seen. resume puts the base back: the commit
the user names, else the one the run (or the last reset) remembered, else the parent of the ticket's
`test(<feature>): NN failing test` commit. Nothing is skipped: the next `next` runs every check from there.
"""

import os
import re

from feature_flow import codehash, git, proof, suggest, tickets
from feature_flow.conductor.errors import Stop

STARTS = "starts"  # run state key: `NN:<sha>` items, where a ticket starts the next time it is picked
FORGOT = "reset_starts"  # run state key: `NN:<sha>` items, where a ticket had started before a reset dropped it


def starts(c, key=STARTS):
    """{NN: sha} of the tickets whose start is remembered for their next pick (or, with FORGOT, that a reset
    dropped)."""
    return dict(item.split(":", 1) for item in c.all.get(key, "").split() if ":" in item)


def remember(c, num, sha, key=STARTS):
    """Remember sha as where ticket num starts the next time it is picked (or, with FORGOT, where it had)."""
    items = starts(c, key)
    items[num] = sha
    c.all[key] = " ".join("%s:%s" % (k, v) for k, v in sorted(items.items()))


def take(c, num):
    """The remembered start of ticket num, forgotten once taken; None when there is none or it is no longer an
    ancestor of HEAD (the history was rewritten)."""
    items = starts(c)
    if num not in items:
        return None
    sha = items.pop(num)
    c.all[STARTS] = " ".join("%s:%s" % (k, v) for k, v in sorted(items.items()))
    if sha and git.commit_sha(sha) and git.is_ancestor(sha, "HEAD"):
        return sha
    return None


def ticket_bases(c):
    """{NN: base} of every ticket the run is building: the main one and each lane's."""
    found = {}
    for key, value in c.all.items():
        match = re.fullmatch(r"(L\d+\.)?num", key)
        base = c.all.get((match.group(1) or "") + "base", "") if match else ""
        if match and re.fullmatch(r"\d+", value or "") and base:
            found[value] = base
    return found


def own_commits(base, plan=None):
    """`<short sha> <subject>` of the commits base..HEAD (first parent, oldest first); with plan, only those that
    change something outside that folder (a ticket's status or findings is no work)."""
    where = ["--", ".", ":(exclude)%s" % proof.repo_relative(plan)] if plan is not None else []
    out = git._git("log", "--first-parent", "--reverse", "--format=%h %s", "%s..HEAD" % base, *where).stdout
    return [line for line in out.splitlines() if line.strip()]


def _pick_ticket(c, paths, num):
    if num is not None:
        chosen = [p for p in paths if tickets.number(p) == num.zfill(2)]
        if not chosen:
            raise Stop("no ticket %s in %s" % (num, c.plan))
        return chosen[0]
    if re.fullmatch(r"\d+", c.get("num") or "") and c.ticket() and c.get("phase"):
        return c.ticket()
    busy = [p for p in paths if tickets.status(p) in tickets.RESET]
    if len(busy) == 1:
        return busy[0]
    kept = [p for p in paths if tickets.number(p) in starts(c) or tickets.number(p) in starts(c, FORGOT)]
    if len(kept) == 1 and not busy:
        return kept[0]
    return None


def _start(c, num, current, chosen):
    """(sha, why) of where ticket num starts. Raises Stop when nothing says."""
    if chosen:
        sha = git.commit_sha(chosen)
        if sha is None:
            raise Stop("--from %s names no commit" % chosen)
        if not git.is_ancestor(sha, "HEAD"):
            raise Stop("--from %s is not an ancestor of HEAD, so the ticket's work cannot be after it" % chosen)
        return sha, "the commit you named"
    test = proof.test_commit(c.feature, num)
    remembered = starts(c).get(num) or starts(c, FORGOT).get(num)
    for sha, why in ((current, "where the run had it"), (remembered, "where it was before the reset")):
        if not sha or not git.commit_sha(sha) or not git.is_ancestor(sha, "HEAD"):
            continue
        if test is None or (sha != test and git.is_ancestor(sha, test)):
            return sha, why
    if test:
        parent = git.commit_sha(test + "^")
        if parent:
            return parent, "just before its failing test commit %s" % test[:10]
    raise Stop("cannot tell where ticket %s started: the run does not remember it and no commit says "
               "`test(%s): %s failing test`. run `feature-flow resume %s %s --from <commit>` with the commit just "
               "before the ticket's first commit" % (num, c.feature, num, c.feature, num))


def resume(c, num=None, chosen=None):
    """Accept the flow code as it is now and put the ticket's start back. Returns the OK line."""
    if not c.plan.is_dir():
        hint = suggest.hint(c.feature, suggest.features(c.root)).strip()
        raise Stop("no plan folder %s%s" % (c.plan, ". " + hint if hint else ""))
    if c.num_all("lanes") > 1:
        raise Stop("resume works on one ticket at a time, and this run has lanes. run `feature-flow reset %s` "
                   "first (it remembers where each ticket started), then resume" % c.feature)
    dirty = git.changes()
    if dirty:
        raise Stop("working tree is not clean, commit or stash first: %s%s"
                   % (" ".join(dirty[:5]), " and %d more" % (len(dirty) - 5) if len(dirty) > 5 else ""))
    whole, each = c.flow_code()
    changed = []
    if c.get("code_sha") and whole != c.get("code_sha"):
        changed = codehash.changed(codehash.load(c.get("code_files")), each)
    paths = tickets.ticket_files(str(c.plan / (os.environ.get("FLOW_TICKETS") or "tasks")))
    path = _pick_ticket(c, paths, num)
    done = []
    if changed:
        done.append("accepted the flow code as it is now (changed: %s)" % ", ".join(changed[:5]))
    if path is None:
        if num is None and not changed:
            raise Stop("no ticket is in progress for %s. say which one: `feature-flow resume %s NN`"
                       % (c.feature, c.feature))
        if c.all:
            c.snapshot_code()
            c.save()
        c.log("RESUME")
        return "OK %s. run %s %s" % (", ".join(done) or "nothing to resume", c.invoke, c.feature)
    num = tickets.number(path)
    current = c.get("base") if c.get("num") == num and c.get("phase") else ""
    if not current and tickets.status(path) in ("resolved", "done", "closed", "wontfix", "parked"):
        raise Stop("ticket %s is %s. `feature-flow reset %s %s` reopens it" % (num, tickets.status(path),
                                                                               c.feature, num))
    if c.get("num") and c.get("num") != num and c.get("phase"):
        raise Stop("ticket %s is in progress, not %s. finish it, or run `feature-flow reset %s` first"
                   % (c.get("num"), num, c.feature))
    sha, why = _start(c, num, current, chosen)
    commits = own_commits(sha, c.plan)
    if current:  # the ticket is in progress: it carries on from its phase, with fresh attempts
        c.st["base"] = sha
        c.st["attempt"] = 0
        c.st["check_rounds"] = 0
        c.snapshot_code()
        what = "ticket %s carries on" % num
    else:  # picked again by the next `next`, from this start
        if tickets.status(path) != "open":
            tickets.set_open(path)
            if not git.commit_paths([path], "chore(%s): %s open again to resume" % (c.feature, num)):
                raise Stop("reopened %s but could not commit it. this session must be allowed to run git commit"
                           % num)
        remember(c, num, sha)
        items = starts(c, FORGOT)
        if items.pop(num, None):
            c.all[FORGOT] = " ".join("%s:%s" % (k, v) for k, v in sorted(items.items()))
        what = "ticket %s starts again when it is picked" % num
    c.save()
    c.log("RESUME %s %s" % (num, sha[:12]))
    done.append("%s from %s (%s)" % (what, sha[:10], why))
    if commits:
        shown = "; ".join(commits[:8]) + (" and %d more" % (len(commits) - 8) if len(commits) > 8 else "")
        done.append("its %d commit(s) since then count for it: %s" % (len(commits), shown))
    done.append("every check runs again from there, test first included")
    return "OK %s. run %s %s" % (", ".join(done), c.invoke, c.feature)
