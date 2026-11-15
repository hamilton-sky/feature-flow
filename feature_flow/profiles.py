"""Modes: one word that says what kind of work a run is, and sets several FLOW_ settings at once.

The word comes from FLOW_MODE, else FLOW_PROFILE, else a `Mode:` line in the plan's commands.md, else a
`Profile:` line (approved with the plan, and frozen like the rest of it). Each mode stands on one of the
profiles below, which hold the settings: `fix` on normal, `small` on fast, `feature` and `explore` on
standard, `careful` on careful. The old profile names are still read (fast is small, standard is feature).
A mode only fills settings that are not set: a FLOW_ variable given on the command line always wins, though
the ones in RETIRED print a warning, as the mode is to set them alone from 0.44.0.
"""

PROFILES = {
    "careful": {  # every ticket gets the full gate and its own two reviewers, shorter sessions
        "FLOW_GATE_FULL": "1",
        "FLOW_REVIEWERS": "2",
        "FLOW_ROUND_REVIEW": "on",
        "FLOW_BASE_GATE": "on",
        "FLOW_FAST": "0",
        "FLOW_SMALL_LINES": "0",
        "FLOW_TICKETS_PER_SESSION": "3",
    },
    "normal": {},
    "standard": {  # a quality and a ticket reviewer side by side on each ticket, one review of the whole round
        "FLOW_REVIEWERS": "2",
        "FLOW_ROUND_REVIEW": "on",
        "FLOW_BASE_GATE": "on",
    },
    "fast": {  # reviews below level 3 deferred to one feature review, no scouts, longer sessions
        "FLOW_FAST": "1",
        "FLOW_SCOUTS": "off",
        "FLOW_TICKETS_PER_SESSION": "6",
    },
}

MODES = {  # the mode -> the profile that holds its settings
    "fix": "normal",  # one bug with one cause: one ticket from the diagnosis, one reviewer
    "small": "fast",  # a clear change: no brainstorm, one review of the whole feature at the end
    "feature": "standard",  # most work, the default for a new plan
    "careful": "careful",  # auth, tokens, money, data loss, shared core code
    "explore": "standard",  # a brainstorm first; the build runs as feature unless the plan says careful
}
ORDER = ("fix", "small", "feature", "careful", "explore")
OLD_NAMES = {"fast": "small", "standard": "feature", "careful": "careful", "normal": ""}  # a profile -> its mode

# settings the mode is to set alone: from 0.44.0 they are not read from the environment
RETIRED = ("FLOW_FAST", "FLOW_REVIEWERS", "FLOW_ROUND_REVIEW", "FLOW_BASE_GATE", "FLOW_GATE_FULL", "FLOW_BATCH",
           "FLOW_MAX_RETRIES", "FLOW_MAX_REVIEW_ROUNDS")


class UnknownProfile(ValueError):
    pass


def _word(value):
    return (value or "").strip().strip("`").strip().lower()


def resolve(environ, commands_mode="", commands_profile=""):
    """(mode, profile) of a run: the mode's name ("" for an old `Profile: normal`, or for none) and the name of
    the profile that holds its settings ("" for none)."""
    for value in (environ.get("FLOW_MODE"), environ.get("FLOW_PROFILE"), commands_mode, commands_profile):
        name = _word(value)
        if not name:
            continue
        if name in MODES:
            return name, MODES[name]
        if name in PROFILES:
            return OLD_NAMES[name], name
        raise UnknownProfile("the mode must be %s, not %s" % (", ".join(ORDER), name))
    return "", ""


def pick(environ, commands_profile):
    """The profile's name, or "" for none: commands_profile may be a mode or a profile name."""
    return resolve(environ, commands_profile)[1]


def env_profile(environ):
    """The profile FLOW_MODE or FLOW_PROFILE names, "" for none or an unknown name."""
    try:
        return resolve({"FLOW_MODE": environ.get("FLOW_MODE"), "FLOW_PROFILE": environ.get("FLOW_PROFILE")})[1]
    except UnknownProfile:
        return ""


def apply(environ, name):
    """Fill the profile's settings into environ where they are not set; the keys it filled."""
    filled = []
    for key, value in PROFILES.get(name, {}).items():
        if not environ.get(key):
            environ[key] = value
            filled.append(key)
    return filled


def warnings(environ, filled):
    """One line per retired setting set by hand (not filled by the mode), and for FLOW_PROFILE and FLOW_GATE=off."""
    out = ["feature-flow: %s is set; from 0.44.0 only the mode sets it (Mode: in commands.md, or FLOW_MODE). "
           "See docs/modes.md" % key for key in RETIRED if environ.get(key) and key not in filled]
    if environ.get("FLOW_PROFILE") and not environ.get("FLOW_MODE"):
        out.append("feature-flow: FLOW_PROFILE is now FLOW_MODE (fast is small, standard is feature)")
    if environ.get("FLOW_GATE") == "off":
        out.append("feature-flow: FLOW_GATE=off is read for the last time in this release; from 0.44.0 only "
                   "`Gate: off unsafe` in the approved commands.md turns the gate off")
    return out
