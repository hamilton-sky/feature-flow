"""The plan check and lint behind `flow-status.py --check` and `--lint`: errors and warnings for a plan's
tickets and commands.md."""

import os
import re
import shlex
import shutil

from feature_flow.plan import builders, tickets


def _env(name, default):
    return os.environ.get(name) or default


def _under(cwd, path):
    """path read from cwd: the path itself when cwd is None or the path is absolute."""
    return path if cwd is None else os.path.join(cwd, path)


def lint(g, plan_dir, cwd=None):
    """(errors, warnings) the stricter plan lint adds to --check: every ticket carries a check block or
    says `Check: none <why>`, and commands.md names a Test command that can be found. Paths are read under
    cwd when given."""
    errors, warnings = [], []
    for t in g.order:
        lab = g.lab[t]
        if g.typ.get(t) == "settle":
            continue
        if t not in g.haslevel:
            warnings.append("%s: no `Level:` line. set 1, 2 or 3 (plan guide, ticket rule 8a); without it the "
                            "ticket gets the review rules of 0.8.0" % lab)
        lines = tickets.records(_under(cwd, g.path[t]))
        has_block = any(line.startswith("```check") for line in lines)
        none = next((line for line in lines[:20] if line.startswith("Check:")), None)
        if none is not None:
            reason = none[len("Check:"):].strip()
            if not reason.lower().startswith("none") or not reason[4:].strip(" \t:-"):
                errors.append(lab + ": `Check:` must read `Check: none <why>`")
        elif not has_block:
            errors.append(lab + ": no check block. add one under Done when, or `Check: none <why>` in the header")
        for line in lines:
            if line.strip().startswith("##"):
                continue
            for ref in re.findall(r"`([A-Za-z0-9_./-]+/[A-Za-z0-9_.-]+\.[A-Za-z0-9]+)`", line):
                if "new" not in line.lower() and "plans/" not in ref and not os.path.exists(_under(cwd, ref)):
                    warnings.append("%s: names `%s`, which does not exist here (say `new` if it will be created)" % (lab, ref))
    commands = "%s/commands.md" % plan_dir
    test = tickets.commands_value(_under(cwd, commands), "Test")
    if not os.path.isfile(_under(cwd, commands)):
        errors.append("commands.md is missing")
    elif not test:
        errors.append("commands.md has no Test command (a placeholder in angle brackets does not count)")
    else:
        try:
            first = shlex.split(test, posix=(os.name != "nt"))[0].strip("\"'")
        except (ValueError, IndexError):
            first = test.split()[0]
        if "=" not in first and shutil.which(first) is None and first not in ("cd", "set", "export"):
            warnings.append("commands.md Test starts with `%s`, which is not on PATH here" % first)
    return errors, list(dict.fromkeys(warnings))


def _check(g, ready, nready, unfinished, out, extra=([], [])):
    errors, warnings = problems(g, nready, unfinished, extra)
    for w in warnings:
        out.write("warning: " + w + "\n")
    if errors:
        for e in errors:
            out.write(e + "\n")
        return 1
    out.write("OK: %d tickets, %d ready now\n" % (len(g.order), nready))
    return 0


def readiness(g):
    """(ready {ticket: bool}, how many are ready, how many are not resolved or parked)."""
    ready = {}
    for t in g.order:
        ready[t] = g.stat[t] == "open" and all(d in g.seen and g.stat[d] == "resolved" for d in g.blk[t])
    unfinished = sum(1 for t in g.order if g.stat[t] not in ("resolved", "parked"))
    return ready, sum(1 for t in g.order if ready[t]), unfinished


def plan_problems(plan_dir, cwd=None, strict=True):
    """(errors, warnings) of `--lint` (strict) or `--check` for the plan in plan_dir, as lists, in the order the
    command prints them; files the tickets name are looked up under cwd (None: the working folder)."""
    folder = os.path.join(plan_dir, _env("FLOW_TICKETS", "tasks"))
    paths = tickets.ticket_files(_under(cwd, folder)) if os.path.isdir(_under(cwd, folder)) else []
    if not paths:
        return ["no tickets in %s" % folder], []
    first = []
    learnings = os.path.join(plan_dir, "learnings.md")
    if os.path.isfile(_under(cwd, learnings)):
        lines = sum(1 for line in tickets.records(_under(cwd, learnings)) if line.strip(" \t\n\v\f\r") != "")
        if lines > 40:
            first.append("learnings.md has %d lines. every session reads it, so a human should prune it" % lines)
    g = tickets.Graph(paths)
    ready, nready, unfinished = readiness(g)
    extra = lint(g, plan_dir, cwd) if strict else ([], [])
    errors, warnings = problems(g, nready, unfinished, extra)
    return errors, first + warnings


def problems(g, nready, unfinished, extra=([], [])):
    """(errors, warnings) of the plan check, with the lint's extra (errors, warnings) added."""
    errors = list(extra[0])
    warnings = []
    for t in g.order:
        lab = g.lab[t]
        if t in g.dup:
            errors.append(lab + ": two tickets share this number")
        if not g.hasstatus[t]:
            errors.append(lab + ": no Status line in the first 20 lines")
        elif g.stat[t] == "unknown":
            errors.append(lab + ": unrecognised Status value")
        if not g.hasdone[t]:
            errors.append(lab + ": no ## Done when section")
        if t in g.hastf and g.tf[t] not in ("yes", "no"):
            errors.append(lab + ": Test first must be yes or no")
        if t in g.hasreview and g.review[t] not in ("full", "auto"):
            errors.append(lab + ": Review must be full or auto")
        if t in g.hasbuilder and g.builder[t] not in builders.NAMES:
            errors.append(lab + ": Builder must be %s" % ", ".join(builders.NAMES))
        if t in g.haslevel and g.level[t] not in ("1", "2", "3"):
            errors.append(lab + ": Level must be 1, 2 or 3")
        if t in g.hastouches and not g.touches[t]:
            errors.append(lab + ": Touches must name at least one path")
        for d in g.blk[t]:
            if d == t:
                errors.append(lab + ": blocked by itself")
            elif d not in g.seen:
                errors.append("%s: blocked by %d, which does not exist" % (lab, d))

    placed = set()
    progress = True
    left = len(g.order)
    while progress and left > 0:
        progress = False
        for t in g.order:
            if t in placed:
                continue
            if all(not (d in g.seen and d != t and d not in placed) for d in g.blk[t]):
                placed.add(t)
                progress = True
                left -= 1
    if left > 0:
        errors.extend(g.lab[t] + ": part of a dependency cycle" for t in g.order if t not in placed)
    if nready == 0 and unfinished > 0:
        errors.append("no ticket is ready to start")

    reach = set()
    for _ in range(len(g.order)):
        changed = False
        for t in g.order:
            for d in g.blk[t]:
                if d not in g.seen:
                    continue
                if (t, d) not in reach:
                    reach.add((t, d))
                    changed = True
                for x in g.order:
                    if (d, x) in reach and (t, x) not in reach:
                        reach.add((t, x))
                        changed = True
        if not changed:
            break
    for t in g.order:
        for m in g.mentions.get(t, []):
            if m == t or m not in g.seen or (t, m) in reach or (m, t) in reach:
                continue
            warnings.append("%s: mentions ticket %s but is not ordered against it. add it to Blocked by, or reword"
                            % (g.lab[t], g.lab[m]))
    return errors, warnings + list(extra[1])
