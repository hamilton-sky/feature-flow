"""feature-flow config [<feature>] [--all]: the mode, then every setting a run will use, its value and where it came from.

Read-only. It reads the settings the conductor reads (conductor.settings.Settings.load), on a copy of the
environment, so the two cannot disagree. Without a feature it shows what a new plan gets from the template.
"""

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from feature_flow import install, profiles, tickets
from feature_flow.conductor.errors import Stop
from feature_flow.conductor.settings import GATE_DEFAULTS, MAX_LANES, Settings

USAGE = "usage: feature-flow config [<feature>] [--all]\n"
PLAN_LINES = ("Build", "Test", "Quick", "Lint", "Typecheck", "Security", "Smoke", "Run", "Setup", "Shared", "Sensitive",
              "Acceptance", "Floor")
LANE_CAPS = {"careful": 2}  # as conductor.guards.LANE_CAPS


def _mode_source(environ, commands):
    for key in ("FLOW_MODE", "FLOW_PROFILE"):
        if environ.get(key):
            return "%s=%s (env)" % (key, environ[key])
    for key in ("Mode", "Profile"):
        value = tickets.commands_value(commands, key)
        if value:
            return "commands.md (%s: %s)" % (key, value)
    return "none: this plan predates modes and runs as it always did"


def _source(key, user, s):
    """Where one FLOW_ setting's value came from: the shell, else the mode for a setting the mode governs."""
    if user.get(key) and key not in s.filled and not (key in profiles.RETIRED and s.ignored):
        return "%s=%s (env)" % (key, user[key])
    if key in s.filled or (s.profile and key in profiles.RETIRED):
        return "mode %s" % (s.mode or s.profile)
    return "built-in"


def rows(user, s, commands, everything=False, loaded=None):
    """[(setting, value, from)] for the settings s holds, read with the environment user; loaded is the environment
    after Settings.load filled the mode in, for the settings the conductor reads from it as it runs."""
    mode_from = "mode %s" % (s.mode or s.profile) if s.profile else "built-in"
    out = []
    if s.profile == "fast":
        reviews = "one review of the whole feature at the end"
    else:
        reviews = "two side by side" if s.reviewers == 2 else "one"
    out.append(("reviews per ticket", reviews, _source("FLOW_REVIEWERS", user, s)))
    out.append(("round review", "on" if s.round_review else "off", _source("FLOW_ROUND_REVIEW", user, s)))
    gate_line = tickets.commands_value(commands, "Gate")
    if not s.gate_on:
        gate, gate_from = "off (unsafe)", "commands.md (Gate: %s)" % gate_line if gate_line else "FLOW_GATE=off (env)"
    else:
        gate = "each ticket" if s.gate_every == 1 else "at the end" if s.gate_every == 0 else "every %d tickets" \
            % s.gate_every
        gate_from = ("commands.md (Gate: %s)" % gate_line if gate_line
                     else mode_from if s.profile in GATE_DEFAULTS else "built-in")
    out.append(("full gate and review", gate, gate_from))
    out.append(("gate at the base", "on" if s.base_gate else "off", _source("FLOW_BASE_GATE", user, s)))
    lanes_line = tickets.commands_value(commands, "Lanes")
    if user.get("FLOW_LANES"):
        lanes, lanes_from = user["FLOW_LANES"], "FLOW_LANES=%s (env)" % user["FLOW_LANES"]
    elif lanes_line.strip().lower() == "auto":
        lanes = ("1, small tickets in batches of %d" % s.batch_size if s.profile == "fast"
                 else "auto, the plan's width, at most %d" % LANE_CAPS.get(s.profile, MAX_LANES))
        lanes_from = "commands.md (Lanes: auto)"
    elif lanes_line:
        lanes, lanes_from = lanes_line.strip(), "commands.md (Lanes: %s)" % lanes_line.strip()
    else:
        lanes, lanes_from = "1", "built-in"
    out.append(("lanes", lanes, lanes_from))
    scouts = "off" if not s.scouts_on else "code %s, web %s" % (s.scout_code, s.scout_web)
    if user.get("FLOW_SCOUTS"):
        scouts_from = "FLOW_SCOUTS=%s (env)" % user["FLOW_SCOUTS"]
    elif s.brainstorm_type:
        scouts_from = "brainstorm.md (Type: %s)" % s.brainstorm_type
    else:
        scouts_from = _source("FLOW_SCOUTS", user, s)
    out.append(("scouts", scouts, scouts_from))
    codeintel = user.get("FLOW_CODEINTEL") or "auto"
    out.append(("codeintel", "off" if codeintel == "off" else "auto, when codeintel doctor passes",
                "FLOW_CODEINTEL=%s (env)" % codeintel if user.get("FLOW_CODEINTEL") else "built-in"))
    out.append(("tickets per session", str(s.per_session) if s.per_session else "no handoffs",
                _source("FLOW_TICKETS_PER_SESSION", user, s)))
    out.append(("gate timeout", "%d min" % s.gate_timeout if s.gate_timeout else "no limit",
                _source("FLOW_GATE_TIMEOUT", user, s)))
    budget = user.get("FLOW_BUDGET", "")
    out.append(("time budget", "%s min" % budget if budget and budget != "off" else "none",
                "FLOW_BUDGET=%s (env)" % budget if budget else "built-in"))
    if everything:
        out += [("full gate after every ticket", "on" if (loaded or {}).get("FLOW_GATE_FULL") == "1" else "off", _source("FLOW_GATE_FULL", user, s)),
                ("most builds or reviews per step", str(s.max_retries), _source("FLOW_MAX_RETRIES", user, s)),
                ("most send-backs per ticket", str(s.max_rounds), _source("FLOW_MAX_REVIEW_ROUNDS", user, s)),
                ("batch size (small)", str(s.batch_size), _source("FLOW_BATCH", user, s)),
                ("single review limit, files", str(s.small_files), _source("FLOW_SMALL_FILES", user, s)),
                ("single review limit, lines", str(s.small_lines), _source("FLOW_SMALL_LINES", user, s)),
                ("hand off after every phase", "on" if s.relay else "off", _source("FLOW_RELAY", user, s)),
                ("plans folder", user.get("FLOW_DIR") or "plans", _source("FLOW_DIR", user, s)),
                ("tickets folder", user.get("FLOW_TICKETS") or "tasks", _source("FLOW_TICKETS", user, s))]
    return out


def render(feature, user, s, commands, everything=False, loaded=None):
    mode = s.mode or ("fix" if s.profile == "normal" else "")
    lines = ["%s%-12s %s" % ("Mode: ", mode or "none", _mode_source(user, commands)), ""]
    table = [("setting", "value", "from")] + rows(user, s, commands, everything, loaded)
    w1 = max(len(r[0]) for r in table)
    w2 = max(len(r[1]) for r in table)
    lines += ["%-*s  %-*s  %s" % (w1, a, w2, b, c) for a, b, c in table]
    present = []
    text = commands.read_text(encoding="utf-8") if commands.is_file() else ""
    for key in PLAN_LINES:
        if tickets.commands_text_value(text, key):
            present.append(key)
    present += sorted(set(re.findall(r"^(Check [^:<]+):", text, re.M)))
    lines += ["", "Plan lines: %s" % (", ".join(present) or "none")]
    if s.ignored:
        lines.append("Ignored: %s (since 0.44.0 the mode sets these; see docs/modes.md)" % ", ".join(s.ignored))
    if user.get("FLOW_PROFILE") and not user.get("FLOW_MODE"):
        lines.append("Note: FLOW_PROFILE is now FLOW_MODE")
    return "\n".join(lines) + "\n"


def main(argv, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    args = list(argv)
    everything = "--all" in args
    args = [a for a in args if a != "--all"]
    if len(args) > 1 or (args and (args[0].startswith("-") or any(c in args[0] for c in "/\\:"))):
        err.write(USAGE)
        return 2
    user = dict(os.environ)
    env = dict(user)
    scratch = None
    try:
        if args:
            feature = args[0]
            plan = Path(env.get("FLOW_DIR") or "plans") / feature
            if not plan.is_dir():
                err.write("no plan %s here; run feature-flow config without a feature to see what a new plan gets\n"
                          % plan.as_posix())
                return 1
            out.write("Feature: %s\n" % feature)
        else:
            feature = "new-plan"
            scratch = Path(tempfile.mkdtemp(prefix="flow-config-"))
            (scratch / feature).mkdir()
            shutil.copyfile(str(Path(install.source_root()) / "guides" / "templates" / "commands.md"), str(scratch / feature / "commands.md"))
            env["FLOW_DIR"] = str(scratch)
            out.write("A new plan (from the commands.md template)\n")
        s = Settings.load(feature, env)
        out.write(render(feature, user, s, s.root / feature / "commands.md", everything, env))
        return 0
    except Stop as stop:
        err.write("feature-flow config: %s\n" % stop)
        return 1
    finally:
        if scratch is not None:
            shutil.rmtree(str(scratch), ignore_errors=True)
