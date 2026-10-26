"""feature-flow eval <feature>: record what a run cost and what it caught, for a field run.

usage: feature-flow eval <feature> [--later] [--out DIR] [--claude-home DIR]
Reads the run log and state in .feature-flow/state/, the plan's tickets, and, when it finds them, the
Claude Code session transcripts of this repo (for tokens). Writes <out>/eval.json, and the first time
<out>/eval-verdict.md, a short form you fill in: was the plan right, what did you fix by hand, and was
each catch real or a false alarm. Run it again after filling the form and eval.json carries your answers.
--later also looks at the commits made after the run for fixes and reverts on the files each ticket
touched: run it a week or two after the feature is done. <out> is plans/<feature>/ unless --out is given,
so the record is committed with the plan and survives a cloud session. Nothing is sent anywhere.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from feature_flow import __version__, git, lanes, report, state, suggest, tickets

USAGE = "usage: feature-flow eval <feature> [--later] [--out DIR] [--claude-home DIR]"
CATCHES = report.FAILS + ("FOOTPRINT-FAIL", "FEATURE-FAIL")
VERDICT_FILE = "eval-verdict.md"
PLAN_ANSWERS = ("right", "partly", "wrong")
FIX_WORDS = re.compile(r"\b(fix(es|ed)?|revert(s|ed)?|bug|hotfix|regression)\b", re.I)


# ---- the log ---------------------------------------------------------------

def parse_time(text):
    """A log time as a UTC datetime, or None: logs before 0.15.0 hold only HH:MM:SS, with no date."""
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def timed(text):
    """[(datetime or None, ticket, event, detail)] for each well formed log line."""
    rows = []
    for line in text.splitlines():
        parts = line.split(",", 2)
        if len(parts) != 3 or not parts[2].strip():
            continue
        event, _, detail = parts[2].strip().partition(" ")
        rows.append((parse_time(parts[0]), parts[1].strip(), event, detail.strip()))
    return rows


def catch_ids(rows):
    """['03 GUARD-FAIL 1', ...]: each failed check, numbered per ticket and check, in log order."""
    seen, ids = {}, []
    for _, num, event, _ in rows:
        if event in CATCHES:
            key = (num, event)
            seen[key] = seen.get(key, 0) + 1
            ids.append("%s %s %d" % (num, event, seen[key]))
    return ids


def run_summary(rows):
    plain = [(num, event, detail) for _, num, event, detail in rows]
    per, run, stops = report.summarize(plain)
    out = {}
    for num, row in per.items():
        out[num] = {
            "level": max([n for n in (1, 2, 3) if row.get("LEVEL-%d" % n)] or [0]) or None,
            "builds": row.get("BUILD", 0),
            "reviews": row.get("REVIEW", 0),
            "deferred_review": bool(row.get("REVIEW-DEFERRED")),
            "questions": row.get("ASK", 0),
            "catches": {name: row[name] for name in CATCHES if row.get(name)},
        }
    by_check = {}
    for row in out.values():
        for name, count in row["catches"].items():
            by_check[name] = by_check.get(name, 0) + count
    user_questions = sum(1 for _, _, event, _ in rows if event.startswith("ASK-") and event.endswith("-USER"))
    times = [t for t, _, _, _ in rows if t is not None]
    return out, {
        "tickets": len(out),
        "builds": sum(r["builds"] for r in out.values()),
        "reviews": sum(r["reviews"] for r in out.values()),
        "reworked": sorted(n for n, r in out.items() if r["builds"] > 1),
        "catches": sum(by_check.values()),
        "catches_by_check": by_check,
        "lanes": any(event.startswith("LEASE-") for _, _, event, _ in rows),
        "deferred_checks": sum(int(detail or 1) for _, _, event, detail in rows if event == "DONEWHEN-DEFERRED"
                               and (detail or "1").isdigit()),
        "fast": any(event in ("REVIEW-DEFERRED", "BUDGET-FAST") for _, _, event, _ in rows),
    }, {
        "stops": [{"ticket": n, "reason": r} for n, r in stops],
        "handoffs": run["HANDOFF"],
        "resets": run["RESET"],
        "takeovers": run["TAKEOVER"],
        "questions_to_user": user_questions,
    }, (min(times), max(times)) if times else None


def driver(rows, run_state):
    """Who drove the run: "agent" or "person", from the log's DRIVER- lines (the last start wins), else the state."""
    found = [event[len("DRIVER-"):].lower() for _, _, event, _ in rows if event.startswith("DRIVER-")]
    return found[-1] if found else (run_state.get("driver") or "person")


def settled_at_plan(plan_dir, built):
    """The tickets resolved without ever being built in a run: settled when the plan was approved."""
    found = []
    for path in tickets.ticket_files(str(plan_dir / (os.environ.get("FLOW_TICKETS") or "tasks"))):
        num = tickets.number(path)
        if num not in built and tickets.status(path) in tickets.DONE + ("wontfix",):
            found.append(num)
    return found


def followups(plan_dir):
    """The items in the plan's followups.md: its `- ` lines."""
    text = state.read_text(plan_dir / "followups.md") or ""
    return sum(1 for line in text.splitlines() if line.startswith("- "))


# ---- tokens, from Claude Code's session transcripts ------------------------------

def claude_home(explicit=None):
    if explicit:
        return Path(explicit)
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def _inside(cwd, top):
    try:
        Path(cwd).resolve().relative_to(top)
        return True
    except (ValueError, OSError):
        return False


def tokens(home, top, window, rows):
    """Token use of the Claude Code sessions (and their subagents) that worked in this repo during the
    run, summed from the transcripts' usage records, each message counted once. Split per ticket by
    time slice: a record goes to the ticket of the last log line before it (approximate; with lanes
    the slices overlap, so no split is given). None when there is nothing to read."""
    projects = Path(home) / "projects"
    if window is None or not projects.is_dir():
        return None
    start, end = window
    since = start.timestamp() - 60
    top = Path(top).resolve()
    marks = sorted((t, num) for t, num, _, _ in rows if t is not None)
    seen, total, models, per = set(), {}, {}, {}
    files = 0
    for path in projects.rglob("*.jsonl"):
        try:
            if path.stat().st_mtime < since:
                continue
            handle = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        used = False
        with handle:
            for line in handle:
                if '"usage"' not in line:
                    continue
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                message = item.get("message") if isinstance(item, dict) else None
                usage = message.get("usage") if isinstance(message, dict) else None
                if not isinstance(usage, dict) or not _inside(item.get("cwd") or "", top):
                    continue
                when = parse_iso(item.get("timestamp"))
                if when is None or when < start or when > end:
                    continue
                key = (message.get("id"), item.get("requestId"))
                if key != (None, None):
                    if key in seen:
                        continue
                    seen.add(key)
                used = True
                counts = {
                    "input": int(usage.get("input_tokens") or 0),
                    "output": int(usage.get("output_tokens") or 0),
                    "cache_read": int(usage.get("cache_read_input_tokens") or 0),
                    "cache_write": int(usage.get("cache_creation_input_tokens") or 0),
                }
                add(total, counts)
                add(models.setdefault(message.get("model") or "unknown", {}), counts)
                num = "-"
                for t, n in marks:
                    if t > when:
                        break
                    num = n
                add(per.setdefault(num, {}), counts)
        files += used
    if not total:
        return None
    return {"source": "claude-code transcripts", "files": files, "total": total, "by_model": models,
            "by_ticket": per, "by_ticket_note": "approximate: split by the time between log lines"}


def parse_iso(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def add(into, counts):
    for key, value in counts.items():
        into[key] = into.get(key, 0) + value


# ---- the human verdict ---------------------------------------------------------------

def verdict_template(feature, catches, driven_by="person"):
    minutes = ("minutes-of-your-time: (roughly, answering questions and reviewing)" if driven_by != "agent" else
               "minutes-of-your-time: (an agent drove this run: only the minutes you spent yourself, 0 if none)")
    lines = [
        "# Eval verdict: %s" % feature,
        "",
        "Fill in after the run, then run `feature-flow eval %s` again. One answer after each colon." % feature,
        "",
        "plan: (right | partly | wrong: did the tickets build what you wanted?)",
        "hand-fixes: (how many changes you made by hand after DONE, 0 if none)",
        "would-use-again: (yes | no)",
        minutes,
        "note: ",
        "",
        "## Catches",
        "",
        "Each check that sent work back. Answer real (a true problem) or false (a false alarm).",
        "",
    ]
    lines += ["%s: " % c for c in catches] or ["(none in this run)"]
    return "\n".join(lines) + "\n"


def read_verdict(path):
    """The filled-in answers, or None when the form is missing or untouched."""
    text = state.read_text(path)
    if text is None:
        return None
    answers, catches = {}, {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        value = value.strip()
        if not sep or not value or value.startswith("("):
            continue
        key = key.strip()
        if re.match(r"^\S+ [A-Z-]+ \d+$", key):
            word = re.match(r"[a-z]*", value.lower()).group(0)
            if word in ("real", "false"):
                catches[key] = word
        elif key in ("plan", "hand-fixes", "would-use-again", "minutes-of-your-time", "note"):
            answers[key.replace("-", "_")] = value
    if "plan" in answers and answers["plan"].split()[0].lower() not in PLAN_ANSWERS:
        answers["plan_unrecognised"] = answers.pop("plan")
    if not answers and not catches:
        return None
    if catches:
        answers["catches"] = catches
        answers["false_alarms"] = sum(1 for v in catches.values() if v == "false")
        answers["real_catches"] = sum(1 for v in catches.values() if v == "real")
    return answers


# ---- defects found later -----------------------------------------------------------

def later(plan_dir, end):
    """Commits after the run that look like fixes or reverts, on the paths each ticket touched."""
    if end is None:
        return None
    since = end.strftime("%Y-%m-%dT%H:%M:%SZ")
    found = {}
    for path in tickets.ticket_files(plan_dir / "tasks"):
        patterns = lanes.touches(Path(path).read_text(encoding="utf-8", errors="replace")) or []
        paths = [":(glob)" + (p + "**" if p.endswith("/") else p) for p in patterns]
        if not paths:
            continue
        result = git._git("log", "--since=" + since, "--format=%h %s", "--", *paths, check=False)
        hits = [l for l in result.stdout.splitlines() if FIX_WORDS.search(l.split(" ", 1)[-1])]
        if hits:
            found[tickets.number(path)] = hits[:20]
    return {"since": since, "fix_commits": found,
            "note": "commit subjects with fix, revert, bug or regression on each ticket's Touches paths"}


# ---- the command -----------------------------------------------------------------------

def build(feature, top, out_dir, home, with_later):
    folder = Path(top) / state.STATE_DIR
    text = state.read_text(state.log_path(folder, feature))
    if text is None:
        return None
    rows = timed(text)
    per, totals, human, window = run_summary(rows)
    run_state = state.load(state.state_path(folder, feature))
    spent = run_state.get("spent", "")
    plan_dir = Path(top) / os.environ.get("FLOW_DIR", "plans") / feature
    driven_by = driver(rows, run_state)
    totals["settled_at_plan"] = settled_at_plan(plan_dir, per)
    totals["followups"] = followups(plan_dir)
    record = {
        "feature": feature,
        "feature_flow": __version__,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "window": [w.strftime("%Y-%m-%dT%H:%M:%SZ") for w in window] if window else None,
        "active_minutes": int(spent) // 60 if spent.isdigit() else None,
        "totals": totals,
        "tickets": per,
        "driver": driven_by,
        "you": human,
        "tokens": tokens(home, top, window, rows),
        "verdict": read_verdict(out_dir / VERDICT_FILE),
    }
    if record["tokens"] and totals["lanes"]:
        record["tokens"].pop("by_ticket")
        record["tokens"]["by_ticket_note"] = "not split: lanes ran tickets at the same time"
    if with_later:
        record["later"] = later(plan_dir, window[1] if window else None)
    return record, catch_ids(rows)


def render(record, out_dir, wrote_form):
    t = record["totals"]
    lines = ["eval for %s: %d ticket(s), %d build(s), %d review(s), %d catch(es)"
             % (record["feature"], t["tickets"], t["builds"], t["reviews"], t["catches"])]
    if t["catches_by_check"]:
        lines.append("  caught by: " + ", ".join("%s x%d" % kv for kv in sorted(t["catches_by_check"].items())))
    lines.append("  reworked: %s" % (", ".join(t["reworked"]) or "none"))
    if t.get("settled_at_plan"):
        lines.append("  settled at plan approval (never built): %s" % ", ".join(t["settled_at_plan"]))
    lines.append("  follow-ups: %d in followups.md%s" % (t.get("followups", 0), ", %d deferred check(s)"
                                                         % t["deferred_checks"] if t.get("deferred_checks") else ""))
    lines.append("  active minutes: %s" % (record["active_minutes"] if record["active_minutes"] is not None else "unknown"))
    tok = record["tokens"]
    if tok:
        total = tok["total"]
        lines.append("  tokens: %d input, %d output, %d cache read, %d cache write (from %d transcript file(s))"
                     % (total.get("input", 0), total.get("output", 0), total.get("cache_read", 0),
                        total.get("cache_write", 0), tok["files"]))
    else:
        lines.append("  tokens: not found (no Claude Code transcripts for this repo in the run window,"
                     " or a log from before 0.15.0)")
    you = record["you"]
    lines.append("  %s: %d stop(s), %d question(s), %d handoff(s), %d reset(s)"
                 % ("needed the driving agent (not you)" if record.get("driver") == "agent" else "needed you",
                    len(you["stops"]), you["questions_to_user"], you["handoffs"], you["resets"]))
    verdict = record["verdict"]
    if verdict:
        lines.append("  your verdict: plan %s, %s hand fix(es), %s real catch(es), %s false alarm(s)"
                     % (verdict.get("plan", "?"), verdict.get("hand_fixes", "?"),
                        verdict.get("real_catches", "?"), verdict.get("false_alarms", "?")))
    elif wrote_form:
        lines.append("  fill in %s, then run eval again" % (out_dir / VERDICT_FILE))
    else:
        lines.append("  your verdict: not filled in yet (%s)" % (out_dir / VERDICT_FILE))
    if "later" in record:
        later_part = record["later"]
        hits = later_part["fix_commits"] if later_part else {}
        lines.append("  fixes since the run: %s" % (", ".join("%s x%d" % (n, len(h)) for n, h in sorted(hits.items())) or "none"))
    lines.append("wrote %s" % (out_dir / "eval.json"))
    return "\n".join(lines) + "\n"


def main(argv, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    args, out_dir, home, with_later = [], None, None, False
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg == "--later":
            with_later = True
        elif arg in ("--out", "--claude-home") and rest:
            value = rest.pop(0)
            if arg == "--out":
                out_dir = value
            else:
                home = value
        elif arg.startswith("-"):
            err.write(USAGE + "\n")
            return 2
        else:
            args.append(arg)
    if len(args) != 1:
        err.write(USAGE + "\n")
        return 2
    feature = args[0]
    top = git.toplevel()
    if top is None:
        err.write("not inside a git repo\n")
        return 2
    out_dir = Path(out_dir) if out_dir else Path(top) / os.environ.get("FLOW_DIR", "plans") / feature
    built = build(feature, top, out_dir, claude_home(home), with_later)
    if built is None:
        path = state.log_path(Path(top) / state.STATE_DIR, feature)
        err.write("no run log for %s (%s)\n" % (feature, path))
        err.write(suggest.hint(feature, [p.name[5:-4] for p in path.parent.glob("flow-*.log")]))
        return 2
    record, catches = built
    out_dir.mkdir(parents=True, exist_ok=True)
    form = out_dir / VERDICT_FILE
    wrote_form = not form.exists()
    if wrote_form:
        form.write_text(verdict_template(feature, catches, record["driver"]), encoding="utf-8")
    (out_dir / "eval.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out.write(render(record, out_dir, wrote_form))
    return 0
