"""The run settings, read once from the environment, the profile and commands.md, and MODE_RULES, the one
table of which modes may run together.

Validation stays lazy: Settings reads only what `Conductor.__init__` always read, in the same order, and
each mode rule is asked where its check ran before (`start`, `lane_next`, `batch_for`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple

from feature_flow import profiles, tickets
from feature_flow.conductor.errors import Stop


MAX_LANES = 4
MAX_BATCH = 5  # most tickets one builder takes at once in fast mode


def _env_int(name, default, environ=None):
    environ = os.environ if environ is None else environ
    value = environ.get(name, "")
    try:
        return int(value) if value.strip() else default
    except ValueError:
        raise Stop("%s must be a whole number, not %s" % (name, value))


def _reviewers(environ):
    value = _env_int("FLOW_REVIEWERS", 1, environ)
    if value not in (1, 2):
        raise Stop("FLOW_REVIEWERS must be 1 or 2, not %d" % value)
    return value


@dataclass(frozen=True)
class Settings:
    root: Path
    profile: str
    filled: Tuple[str, ...]  # the keys the profile filled into the environment
    max_retries: int
    max_rounds: int
    gate_timeout: int
    gate_on: bool
    per_session: int  # FLOW_TICKETS_PER_SESSION as read; session_limit applies the agent-driver rule
    per_session_given: bool  # FLOW_TICKETS_PER_SESSION was set, and not by the profile
    small_files: int
    small_lines: int
    batch_size: int
    scouts_on: bool
    relay: bool
    invoke: str
    reviewers: int = 1  # 2: a quality and a ticket reviewer side by side, where one review would run
    round_review: bool = False  # one review of the whole round at the end, after every ticket's own
    base_gate: bool = False  # the whole gate once at the base, before the first ticket

    @classmethod
    def load(cls, feature, environ=None):
        """The settings of feature's run. Stops on the first bad value, in the order the conductor always
        checked them: the profile, then the whole numbers. Fills the profile's settings into environ."""
        environ = os.environ if environ is None else environ
        root = Path(environ.get("FLOW_DIR") or "plans")
        try:
            profile = profiles.pick(environ, tickets.commands_value(root / feature / "commands.md", "Profile"))
        except profiles.UnknownProfile as err:
            raise Stop(str(err))
        filled = profiles.apply(environ, profile)
        return cls(
            root=root,
            profile=profile,
            filled=tuple(filled),
            max_retries=_env_int("FLOW_MAX_RETRIES", 2, environ),
            max_rounds=_env_int("FLOW_MAX_REVIEW_ROUNDS", 3, environ),
            gate_timeout=_env_int("FLOW_GATE_TIMEOUT", 30, environ),
            gate_on=environ.get("FLOW_GATE", "on") != "off",
            per_session=_env_int("FLOW_TICKETS_PER_SESSION", 4, environ),
            per_session_given=bool(environ.get("FLOW_TICKETS_PER_SESSION"))
            and "FLOW_TICKETS_PER_SESSION" not in filled,
            small_files=_env_int("FLOW_SMALL_FILES", 3, environ),
            small_lines=_env_int("FLOW_SMALL_LINES", 60, environ),
            batch_size=min(_env_int("FLOW_BATCH", MAX_BATCH, environ), MAX_BATCH),
            scouts_on=environ.get("FLOW_SCOUTS", "on") != "off",
            relay=environ.get("FLOW_RELAY", "0") == "1",
            invoke=environ.get("FLOW_INVOKE") or "/feature-flow",
            reviewers=_reviewers(environ),
            round_review=environ.get("FLOW_ROUND_REVIEW", "off") == "on",
            base_gate=environ.get("FLOW_BASE_GATE", "off") == "on",
        )

    def session_limit(self, driver):
        """Tickets per session for this driver: an agent has no context to refresh between sessions, so it
        gets no handoffs (0) unless FLOW_TICKETS_PER_SESSION was given for the run itself."""
        if driver == "agent" and not self.per_session_given:
            return 0
        return self.per_session


@dataclass(frozen=True)
class ModeRule:
    name: str
    broken: Callable[[dict], bool]  # the facts -> True when the modes may not run together
    stop: Optional[str]  # the STOP text, filled from the facts, or None when the mode is quietly skipped


MODE_RULES = (
    ModeRule("lanes_range", lambda f: not 1 <= f["lanes"] <= MAX_LANES,
             "FLOW_LANES must be 1 to %d, not %%(lanes)d" % MAX_LANES),
    ModeRule("lanes_relay", lambda f: f["lanes"] > 1 and f["relay"],
             "FLOW_RELAY hands off after every phase, which lanes cannot do. drop one of them"),
    ModeRule("lanes_top", lambda f: f["lanes"] > 1 and f["cwd"] != f["top"],
             "run the conductor from the top of the repo (%(top)s) to use lanes"),
    ModeRule("driver", lambda f: f["driver"] not in ("", "person", "agent"),
             "FLOW_DRIVER must be person or agent, not %(driver)s"),
    ModeRule("fast", lambda f: f["fast"] not in ("", "0", "1"),
             "FLOW_FAST must be 1 or 0, not %(fast)s"),
    ModeRule("batch", lambda f: (f["size"] < 2 or not f["fast_mode"] or not f["gate_on"] or f["relay"]
                                 or f["lanes"] > 1),
             None),
)


def mode_ok(name, **facts):
    """True when rule name holds for facts; when it is broken, raise its STOP, or return False if it has none."""
    rule = {rule.name: rule for rule in MODE_RULES}[name]
    if not rule.broken(facts):
        return True
    if rule.stop is None:
        return False
    raise Stop(rule.stop % facts)
