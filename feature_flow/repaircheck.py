"""A plan repair measured against the plan it started from: which problems it inherited, which it added, and how it
moved the tickets' footprints.

A repair runs while some tickets are resolved, and a resolved ticket is never edited. So a warning the plan already had
before the repair (in a resolved ticket, say) cannot be fixed by it, and must not block it: it stays visible, as
inherited. Only a problem the repair added blocks. The baseline is the plan folder at one commit, the commit the repair
started from, so it is always the same text; nothing about it is remembered apart from that commit and its tree.

usage: python3 scripts/flow-status.py <feature> --lint --baseline <commit>
"""

import os
import shutil
import subprocess
import tempfile

from feature_flow import status, tickets


class BaselineError(Exception):
    """The plan at the baseline commit cannot be read."""


def _git(*args, cwd=None):
    return subprocess.run(["git"] + list(args), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def plan_tree(rev, plan_rel, cwd=None):
    """The git tree id of the plan folder at rev, or None when rev has no such folder."""
    out = _git("rev-parse", "--verify", "-q", "%s:%s" % (rev, plan_rel.rstrip("/")), cwd=cwd)
    return out.stdout.decode("ascii", "replace").strip() or None if out.returncode == 0 else None


def export(rev, plan_rel, into, cwd=None):
    """Write the plan folder as it is at rev under into/<plan_rel>. Raises BaselineError when it is not there."""
    out = _git("ls-tree", "-r", "-z", "--name-only", rev, "--", plan_rel.rstrip("/") + "/", cwd=cwd)
    if out.returncode != 0:
        raise BaselineError("cannot list %s at %s: %s" % (plan_rel, rev, out.stderr.decode("utf-8", "replace").strip()))
    names = [n for n in out.stdout.decode("utf-8", "surrogateescape").split("\0") if n]
    if not names:
        raise BaselineError("%s has no plan folder %s" % (rev[:12], plan_rel))
    for rel in names:
        blob = _git("--no-replace-objects", "show", "%s:%s" % (rev, rel), cwd=cwd)
        if blob.returncode != 0:
            raise BaselineError("cannot read %s at %s" % (rel, rev[:12]))
        path = os.path.join(into, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(blob.stdout)


def footprints(plan_dir):
    """{label: (status, [Touches paths])} of the plan's tickets."""
    folder = os.path.join(plan_dir, os.environ.get("FLOW_TICKETS") or "tasks")
    if not os.path.isdir(folder):
        return {}
    g = tickets.Graph(tickets.ticket_files(folder))
    return {g.lab[t]: (g.stat[t], list(g.touches.get(t) or [])) for t in g.order}


def footprint_changes(before, now):
    """[line] of how each ticket's Touches: moved: `03: + a, + b, - c`, `05 (new): touches a, b`."""
    lines = []
    for lab in sorted(set(before) | set(now)):
        if lab not in before:
            lines.append("%s (new ticket): touches %s" % (lab, ", ".join(now[lab][1]) or "nothing named"))
            continue
        if lab not in now:
            lines.append("%s: removed" % lab)
            continue
        old, new = before[lab][1], now[lab][1]
        moved = ["+ %s" % p for p in new if p not in old] + ["- %s" % p for p in old if p not in new]
        if moved:
            lines.append("%s: %s" % (lab, ", ".join(moved)))
    return lines


def compare(plan_rel, rev, cwd=None):
    """The repair of the plan folder plan_rel (as the working tree has it) against the plan at rev: a dict with
    `inherited` and `new` (errors, warnings) and `footprint` lines. The files the tickets name are looked up in the
    working tree for both, so a warning means the same in each."""
    temp = tempfile.mkdtemp(prefix="flow-baseline-")
    try:
        export(rev, plan_rel, temp, cwd=cwd)
        base_dir = os.path.join(temp, plan_rel)
        here = os.path.abspath(cwd or os.getcwd())
        old = _problems(base_dir, here)
        new = _problems(os.path.join(here, plan_rel), here)
        before = footprints(base_dir)
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    now = footprints(os.path.join(cwd or os.getcwd(), plan_rel))
    return {
        "inherited": (split(new[0], old[0])[0], split(new[1], old[1])[0]),
        "new": (split(new[0], old[0])[1], split(new[1], old[1])[1]),
        "footprint": footprint_changes(before, now),
    }


def split(now, before):
    """(inherited, new) of the problems now, counted as a multiset: a third copy of a message the baseline had twice
    is new."""
    left = {}
    for item in before:
        left[item] = left.get(item, 0) + 1
    inherited, added = [], []
    for item in now:
        if left.get(item, 0) > 0:
            left[item] -= 1
            inherited.append(item)
        else:
            added.append(item)
    return inherited, added


def _problems(plan_dir, top):
    """The lint's (errors, warnings) of plan_dir (absolute), the files its tickets name read under top."""
    return status.plan_problems(os.path.abspath(plan_dir), cwd=top)


def lines(found, rev, tree=None, extra=()):
    """The report of compare(), one finding per line, and whether the repair is clean (adds no problem); extra:
    blocking lines found elsewhere (a resolved ticket the repair changed)."""
    out = ["baseline: the plan at %s%s" % (rev[:12], " (tree %s)" % tree[:12] if tree else "")]
    out += ["footprint: %s" % line for line in found["footprint"]] or ["footprint: unchanged"]
    for kind, (errors, warnings) in (("inherited", found["inherited"]), ("new", found["new"])):
        out += ["%s error: %s" % (kind, e) for e in errors]
        out += ["%s warning: %s" % (kind, w) for w in warnings]
    out += list(extra)
    added = len(found["new"][0]) + len(found["new"][1]) + len(extra)
    kept = len(found["inherited"][0]) + len(found["inherited"][1])
    if added:
        out.append("BLOCKED: the repair adds %d problem(s). fix those; the %d inherited one(s) stay as they are"
                   % (added, kept))
    else:
        out.append("OK: the repair adds no problem (%d inherited, shown above, do not block it)" % kept)
    return out, not added


def main(feature, rev, out, err, root="plans"):
    """flow-status.py <feature> --lint --baseline <rev>: exit 0 when the repair adds no problem, 1 when it does, 2
    when the baseline cannot be read."""
    plan_rel = "%s/%s" % (root, feature)
    top = _git("rev-parse", "--show-toplevel").stdout.decode("utf-8", "replace").strip()
    if not top:
        err.write("not inside a git worktree\n")
        return 2
    prefix = _git("rev-parse", "--show-prefix").stdout.decode("utf-8", "replace").strip()
    plan_rel = (prefix + plan_rel).replace(os.sep, "/")
    try:
        found = compare(plan_rel, rev, cwd=top)
    except BaselineError as error:
        err.write("cannot read the baseline: %s\n" % error)
        return 2
    report, clean = lines(found, rev, plan_tree(rev, plan_rel, cwd=top))
    out.write("\n".join(report) + "\n")
    return 0 if clean else 1
