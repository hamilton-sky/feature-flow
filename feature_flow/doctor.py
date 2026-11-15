"""feature-flow doctor <feature> [--trust <digest>]: where a run stands, and the safe next command. Read-only.

It reads the run state, the log, the plan, git and the flow's own files, and changes none of them: no state folder
is made, no index refreshed (git runs with --no-optional-locks), nothing committed. It says "cannot determine" where
the saved evidence does not support a conclusion, and then offers no continuation for that part.

usage: feature-flow doctor <feature> [--trust <digest>]
       python3 scripts/flow-status.py <feature> --doctor [--trust <digest>]   (the repo's own conductor copy)
"""

import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import feature_flow
from feature_flow.conductor import codehash
from feature_flow.plan import tickets
from feature_flow.infra import git, state

USAGE = "usage: feature-flow doctor <feature> [--trust <digest>]"
MOVED_NOT = ("STOP",)  # log events that are not a step of the run (nor are failed checks: -FAIL, -BLOCKED, -SAME)


def _git(top, *args):
    out = subprocess.run(["git", "--no-optional-locks"] + list(args), cwd=str(top), stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, universal_newlines=True)
    return out.stdout.strip() if out.returncode == 0 else None


def _ancestor(top, older, newer):
    return subprocess.run(["git", "--no-optional-locks", "merge-base", "--is-ancestor", older, newer], cwd=str(top),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0


def _ago(stamp):
    try:
        when = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return stamp
    minutes = int((datetime.now(timezone.utc) - when).total_seconds() // 60)
    if minutes < 90:
        return "%s (%d min ago)" % (stamp, minutes)
    return "%s (%.1f h ago)" % (stamp, minutes / 60.0)


def log_rows(path):
    """[(time, ticket, event, detail)] of the run log, oldest first."""
    rows = []
    text = state.read_text(path) if Path(path).is_file() else None
    for line in (text or "").splitlines():
        parts = line.split(",", 2)
        if len(parts) == 3 and parts[2].strip():
            event, _, detail = parts[2].strip().partition(" ")
            rows.append((parts[0], parts[1], event, detail))
    return rows


def scripts_folder(top):
    """The scripts folder the run uses: the repo's own, else the personal install's."""
    if (top / "scripts" / "flow.py").is_file():
        return top / "scripts"
    return Path(os.environ.get("FEATURE_FLOW_HOME") or os.environ.get("HOME", "") + "/.feature-flow") / "scripts"


def code_check(run, scripts, top):
    """(kind, text): kind `same`, `changed` or `unknown`, for the flow code against the run's snapshot."""
    if not run.get("code_sha"):
        return "unknown", "cannot determine: the run has no snapshot of the flow code (no ticket picked yet)"
    saved = codehash.load(run.get("code_files", ""))
    try:
        whole, each = codehash.flow_code(str(scripts), cwd=str(top))
    except OSError as err:
        return "unknown", "cannot determine: %s" % err
    if whole == run["code_sha"]:
        return "same", "unchanged since the ticket was picked"
    marker = codehash._name(Path(feature_flow.__file__).resolve().parent / "__init__.py", top.resolve())
    if not saved or marker not in saved:
        return "unknown", ("cannot determine: this doctor reads feature-flow from %s, and the run's snapshot names "
                           "other files (the run uses its own copy). run `python3 scripts/flow-status.py <feature> "
                           "--doctor` for the run's own copy" % Path(feature_flow.__file__).resolve().parent)
    names = codehash.changed(saved, each)
    return "changed", "changed since the ticket was picked: %s" % ", ".join(names[:8]) + (
        " and %d more" % (len(names) - 8) if len(names) > 8 else "")


def trust_check(top, scripts, feature, digest):
    """(kind, text) from flow-trust.py --diagnose, or ("unknown", why) when it cannot run."""
    runner = scripts / "flow-trust.py"
    if not runner.is_file():
        return "unknown", "cannot determine: no %s" % runner
    env = {k: v for k, v in os.environ.items() if k != "FLOW_TRUST"}
    if digest:
        env["FLOW_TRUST"] = digest
    out = subprocess.run([sys.executable, "-I", str(runner), feature, "--diagnose"], cwd=str(top), env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    line = next((l for l in out.stdout.splitlines() if l.startswith("TRUST-DIAGNOSIS ")), "")
    if not line:
        return "unknown", "cannot determine: flow-trust.py said %s" % (" ".join((out.stdout + out.stderr).split())[:200]
                                                                      or "nothing")
    _, kind, text = (line.split(" ", 2) + [""])[:3]
    return kind, text


def diagnose(feature, top, digest=None, root=None):
    """The doctor's lines for feature in the worktree top: [(label, text)], the last one `next`."""
    os.environ["GIT_OPTIONAL_LOCKS"] = "0"  # read-only: git status must not refresh the index
    top = Path(top)
    root = Path(root or os.environ.get("FLOW_DIR") or "plans")
    plan = top / root / feature
    folder = top / state.STATE_DIR
    run = state.load(folder / ("flow-%s.state" % feature)) if (folder / ("flow-%s.state" % feature)).is_file() else {}
    rows = log_rows(folder / ("flow-%s.log" % feature))
    scripts = scripts_folder(top)
    out = []
    nexts = []  # (the command, why), most urgent first

    if not plan.is_dir():
        out.append(("plan", "missing: no %s/%s" % (root.as_posix(), feature)))
        nexts.append(("/feature-flow %s" % feature, "plan it first"))
    paths = tickets.ticket_files(str(plan / (os.environ.get("FLOW_TICKETS") or "tasks"))) if plan.is_dir() else []
    if plan.is_dir():
        counts = {}
        for p in paths:
            counts[tickets.status(p)] = counts.get(tickets.status(p), 0) + 1
        out.append(("plan", "%s/%s: %d ticket(s), %s" % (root.as_posix(), feature, len(paths), ", ".join(
            "%d %s" % (n, s) for s, n in sorted(counts.items())) or "none")))

    phase, num = run.get("phase", ""), run.get("num", "")
    ticket = run.get("ticket", "")
    if not run:
        out.append(("run", "no run state (never started, or reset)"))
    else:
        where = "phase %s, ticket %s (%s, %s)" % (phase, num, ticket, tickets.status(str(top / ticket))
                                                  if ticket and (top / ticket).is_file() else "file missing") \
            if phase else "between tickets"
        lanes = run.get("lanes", "")
        out.append(("run", where + (", %s lanes" % lanes if lanes and lanes != "1" else "")))
    owner = run.get("owner", "")
    last = rows[-1][0] if rows else ""
    if owner:
        out.append(("owner", "session %s holds it; its last conductor step was %s. the doctor cannot tell whether "
                    "that session is still alive" % (owner[:8], _ago(last) if last else "never logged")))
    elif run:
        out.append(("owner", "none: the next session starts it"))

    moved = [r for r in rows if r[2] not in MOVED_NOT and not r[2].endswith(("-FAIL", "-BLOCKED", "-SAME"))]
    if moved:
        t, n, event, detail = moved[-1]
        out.append(("last step", "%s: %s%s%s" % (_ago(t), event, " " + detail if detail else "",
                                                 " (ticket %s)" % n if n not in ("", "-") else "")))
    stops = [r for r in rows if r[2] == "STOP"]
    if stops and (not moved or rows.index(stops[-1]) > rows.index(moved[-1])):
        out.append(("last stop", "%s: %s" % (_ago(stops[-1][0]), stops[-1][3])))

    base = run.get("base", "")
    if phase and base:
        head = _git(top, "rev-parse", "HEAD") or ""
        exists = _git(top, "rev-parse", "--verify", "-q", base + "^{commit}")
        if not exists:
            out.append(("start", "ticket %s starts at %s, which is not a commit here: cannot determine" % (num, base[:10])))
            nexts.append(("feature-flow resume %s %s --from <commit> --dry-run" % (feature, num),
                          "the ticket's start is gone; the user names the commit just before its first one"))
        else:
            own = _git(top, "rev-list", "--count", "--first-parent", "%s..HEAD" % base) or "0"
            test = _git(top, "log", "-1", "--format=%H", "--fixed-strings",
                        "--grep=test(%s): %s failing test" % (feature, num), "HEAD")
            line = "ticket %s starts at %s, %s commit(s) since" % (num, base[:10], own)
            if test:
                if _ancestor(top, test, base):
                    line += "; its failing test commit %s is at or before the start, so test first cannot see it" \
                            % test[:10]
                    nexts.append(("feature-flow resume %s %s --dry-run" % (feature, num),
                                  "the start moved past the failing test commit; resume puts it back"))
                else:
                    line += "; its failing test commit %s is after the start" % test[:10]
            if head and not _ancestor(top, base, head):
                line += "; the start is not an ancestor of HEAD (history was rewritten): cannot determine"
            out.append(("start", line))
    if run.get("plan_sha"):
        out.append(("plan revision", "the ticket reads the plan at %s (a repair or resume kept its start)"
                    % run["plan_sha"][:10]))
    if run.get("repair_sha"):
        head = _git(top, "rev-parse", "HEAD") or ""
        tree = run.get("repair_plan", "")
        now = _git(top, "rev-parse", "--verify", "-q", "%s:%s" % (run["repair_sha"], (root / feature).as_posix()))
        base_note = ("baseline tree %s" % tree[:12] if tree and now == tree else
                     "baseline cannot be determined (recorded %s, found %s)" % ((tree or "nothing")[:12],
                                                                              (now or "nothing")[:12]))
        if head == run["repair_sha"]:
            out.append(("repair", "handed out at %s, nothing committed yet; %s" % (run["repair_sha"][:10], base_note)))
            nexts.append(("repair-check, then commit `plan(%s): repair the plan` on the user's yes, then next" % feature,
                          "a plan repair is pending: check the planner's draft against its baseline first"))
        else:
            out.append(("repair", "started at %s, committed since; %s. the next `next` checks it and builds the "
                        "ticket again" % (run["repair_sha"][:10], base_note)))
            nexts.append(("next", "it checks the committed repair against its baseline first; `python3 "
                          "scripts/flow-status.py %s --lint --baseline %s` shows what it will find"
                          % (feature, run["repair_sha"][:12])))
    for key, what in (("starts", "remembered start"), ("reset_starts", "start a reset dropped")):
        for item in run.get(key, "").split():
            n, _, sha = item.partition(":")
            out.append(("start", "ticket %s has a %s at %s" % (n, what, sha[:10])))
            if key == "reset_starts":
                nexts.append(("feature-flow resume %s %s --dry-run" % (feature, n),
                              "a reset dropped ticket %s's start; resume keeps its commits" % n))

    findings = folder / ("flow-%s.findings" % feature)
    pending = []
    if findings.is_file():
        pending.append("a reviewer's findings wait in %s" % findings.relative_to(top).as_posix())
    if ticket and (top / ticket).is_file():
        rounds = re.findall(r"^## Review findings \(round (\d+), ([^)]*)\)", (top / ticket).read_text(
            encoding="utf-8", errors="replace"), re.MULTILINE)
        if rounds:
            pending.append("%s has %d findings section(s), the last round %s (%s)" % (
                tickets.name(ticket), len(rounds), rounds[-1][0], rounds[-1][1]))
    out.append(("findings", "; ".join(pending) or "none pending"))

    try:
        dirty = git.changes(cwd=str(top))  # the conductor's own view: its install and bytecode do not count
    except (OSError, RuntimeError, subprocess.CalledProcessError):
        dirty = None
    if dirty is None:
        out.append(("uncommitted", "cannot determine: git status failed"))
    else:
        out.append(("uncommitted", ", ".join(dirty[:8]) + (" and %d more" % (len(dirty) - 8) if len(dirty) > 8 else "")
                    if dirty else "none"))
        if dirty:
            nexts.insert(0, ("git status", "commit or stash the uncommitted changes first: resume and next never "
                             "discard them, and stop on them"))

    if run.get("code_sha"):
        kind, text = code_check(run, scripts, top)
        out.append(("flow code", text))
        if kind == "changed":
            nexts.append(("feature-flow resume %s --dry-run, then --accept-code on the user's yes" % feature,
                          "the flow code changed; resume shows exactly what it accepts"))
    kind, text = trust_check(top, scripts, feature, digest)
    out.append(("trust", "%s: %s (by %s, a copy the skill's pin does not check)" % (kind, text, scripts / "flow-trust.py")))
    if kind == "stale":
        nexts.insert(0, ("the digest from the last TRUST line", "the digest passed was an older one; if it is lost, "
                         "the same command with FLOW_TRUST_ACCEPT=saved-state on the user's yes"))
    elif kind == "changed":
        nexts.insert(0, ("show the user", "flow files really changed since that digest: find out what changed them "
                         "before anything runs"))
    elif kind == "unknown" and digest:
        nexts.insert(0, ("show the user", "the trust check cannot tell why the digest does not match: do not carry on"))

    if not nexts and plan.is_dir():
        if owner:
            nexts.append(("next, from the session that holds it", "the run is in order" +
                          ("; if that session is closed, start again with FLOW_TAKEOVER=1 on the user's yes")))
        else:
            nexts.append(("start, then next", "the run is in order"))
    first, why = nexts[0]
    out.append(("next", "%s (%s)" % (first, why)))
    for command, why in nexts[1:4]:
        out.append(("then", "%s (%s)" % (command, why)))
    return out


def render(feature, found):
    width = max(len(label) for label, _ in found)
    lines = ["doctor for %s (read-only: nothing was changed)" % feature]
    lines += ["  %s  %s" % (label.ljust(width), text) for label, text in found]
    return "\n".join(lines) + "\n"


def main(argv, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    args = list(argv)
    digest = None
    if "--trust" in args:
        at = args.index("--trust")
        if at + 1 >= len(args):
            err.write(USAGE + "\n")
            return 2
        digest = args[at + 1]
        args = args[:at] + args[at + 2:]
    if len(args) != 1 or not args[0] or args[0].startswith("-") or any(c in args[0] for c in "/\\:"):
        err.write(USAGE + "\n")
        return 2
    top = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if not top:
        err.write("not inside a git worktree\n")
        return 2
    out.write(render(args[0], diagnose(args[0], Path(top), digest or os.environ.get("FLOW_TRUST") or None)))
    return 0
