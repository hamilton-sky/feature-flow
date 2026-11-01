"""Brainstorm types and scout levels: chosen once, written into the brainstorm, and followed by the run.

A type says who the brainstorm is for, and sets how far the code and web scouts look and which helpers the
brainstorm may use. Both are header lines of the brainstorm file, beside `Style:` and `Picked by:`:

    Type: learn
    Scouts: code=light web=deep

The file is `.feature-flow/state/brainstorm-<feature>.md` until the plan exists and then
`plans/<feature>/brainstorm.md`, so the scouts of the plan and the build follow the same choice.
"""

from pathlib import Path

LEVELS = ("off", "light", "normal", "deep")
KINDS = ("code", "web")  # code: flow-scout, web: flow-web
AGENTS = {"flow-scout": "code", "flow-web": "web"}

TYPES = {
    "standard": {"about": "you know the domain and the codebase", "code": "normal", "web": "normal"},
    "learn": {"about": "you are new to the domain: each idea is explained as it comes, with a cited glossary",
              "code": "light", "web": "deep"},
    "map": {"about": "you know the domain but not this code: the scouts map the repository first",
            "code": "deep", "web": "light"},
    "quick": {"about": "you know both and want it short: one look, one or two options, then the brief",
              "code": "light", "web": "light", "consult": 1, "skeptic": 0, "lens": 0},
    "explore": {"about": "you are not sure it is worth building: it ends in a go or no-go, not a brief",
                "code": "light", "web": "normal"},
}

# helpers per brainstorm, by profile; a scout level other than normal replaces the scout and web rows
LIMITS = {"normal": {"scout": 2, "web": 1, "consult": 2, "skeptic": 1, "lens": 2},
          "careful": {"scout": 3, "web": 2, "consult": 3, "skeptic": 1, "lens": 3}}
LEVEL_LIMITS = {"scout": {"off": 0, "light": 1, "deep": 3}, "web": {"off": 0, "light": 1, "deep": 2}}  # deep: the careful row


class BadMode(ValueError):
    pass


def _check(key, value):
    value = value.strip().lower()
    if key == "type" and value not in TYPES:
        raise BadMode("Type: must be %s, not %s" % (", ".join(TYPES), value or "empty"))
    if key in KINDS and value not in LEVELS:
        raise BadMode("Scouts: %s= must be %s, not %s" % (key, ", ".join(LEVELS), value or "empty"))
    return value


def parse(text):
    """{"type"?, "code"?, "web"?} from a brainstorm's header lines (those before the first `## ` heading).
    Raises BadMode on a value it does not know."""
    found = {}
    for line in (text or "").splitlines():
        if line.startswith("## "):
            break
        key, sep, value = line.partition(":")
        if not sep or value.strip().startswith("<"):  # no value, or the template's placeholder
            continue
        if key.strip() == "Type" and value.strip():
            found["type"] = _check("type", value)
        elif key.strip() == "Scouts":
            for word in value.split():
                kind, eq, lvl = word.partition("=")
                if not eq or kind.strip().lower() not in KINDS:
                    raise BadMode("Scouts: takes code=<level> and web=<level>, not %s" % word)
                found[kind.strip().lower()] = _check(kind.strip().lower(), lvl)
    return found


def read(plan_dir, state_dir, feature):
    """The run's brainstorm choice: the plan's brainstorm.md once the plan exists, else the one in the state
    folder, else {}."""
    for path in (Path(plan_dir) / feature / "brainstorm.md", Path(state_dir) / ("brainstorm-%s.md" % feature)):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        return parse(text)
    return {}


def level(kind, environ, filled, mode):
    """One scout level. FLOW_SCOUTS=off set by you wins, then the brainstorm's own `Scouts:` level, then its
    type's, then FLOW_SCOUTS=off filled by a profile (fast fills it), else normal."""
    off = environ.get("FLOW_SCOUTS", "on") == "off"
    if off and "FLOW_SCOUTS" not in filled:
        return "off"
    if mode.get(kind):
        return mode[kind]
    if mode.get("type"):
        return TYPES[mode["type"]][kind]
    return "off" if off else "normal"


def limits(profile, levels, kind):
    """{group: most helpers of that group in one brainstorm} for this profile, these levels and this type."""
    out = dict(LIMITS["careful" if profile == "careful" else "normal"])
    for group, lvl in (("scout", levels["code"]), ("web", levels["web"])):
        out[group] = LEVEL_LIMITS[group].get(lvl, out[group])
    for group in ("consult", "skeptic", "lens"):
        out[group] = TYPES.get(kind or "standard", {}).get(group, out[group])
    return out
