"""What every phase shares: the Outcome of judging it, and the defaults of the phase protocol.

Until ticket 12 the `ws` a phase gets is the Conductor itself; phases call back into it for check_code,
count_run, save, log and emit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from feature_flow import lanes, prompts
from feature_flow.conductor.errors import NoPhase, Stop
from feature_flow.conductor.store import NOTE_SEP


@dataclass(frozen=True)
class Outcome:
    """What judging a phase gave: the next line (None when a lane ticket waits for its merge), and whether the
    judgement passed the ticket."""
    line: Optional[str]
    passed: bool = False


class Phase:
    """The phase protocol, with the defaults of a phase that has nothing to do. The registry maps the phase word
    to a subclass; a phase word missing from it (none) gets these defaults."""
    name = ""
    lane_scoped = True  # False for the run-wide phases, which have no lane
    who = ""  # what the "has no lane" STOPs call a run-wide phase
    takes_verdict = True  # False when `verdict` has nothing to record for the phase

    @classmethod
    def hand_out(cls, ws):
        raise NotImplementedError

    @classmethod
    def judge(cls, ws):
        raise NotImplementedError

    @classmethod
    def prompt(cls, ws):
        raise NoPhase("no BUILD or REVIEW is pending for %s" % ws.feature)

    @classmethod
    def record(cls, ws, reply):
        raise NoPhase("no review is pending for %s" % ws.feature)

    @classmethod
    def scout_questions(cls, ws):
        return []

    @classmethod
    def key(cls, ws):
        """Names the phase handed out last, so scout replies saved for one phase never reach another."""
        return "%s:%s:%s:%s:%s:%s:%s:%s" % (ws.get("phase"), ws.get("num"), ws.num("round"), ws.num("attempt"),
                                            ws.get("review_pass"), ws.num("review_attempt"), ws.num("asks"),
                                            ws.num("ask_attempt"))


def read_reply(reply):
    try:
        return Path(reply).read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        raise Stop("cannot read the review reply %s: %s" % (reply, err.strerror))


def ticket_prompt(ws, word, notes=()):
    """The build or review prompt of the ticket: word is build, review, review-quality or review-single."""
    try:
        return prompts.build(word, ws.scripts, ws.feature, ws.ticket(), ws.get("num"), ws.get("base"),
                             notes,
                             retry=ws.num("round") > 0,
                             workdir=(str(Path.cwd()), lanes.branch(ws.feature, ws.get("num"))) if ws.lane else None
                             ) + ws.scout_findings()
    except FileNotFoundError as err:
        raise Stop(str(err))


def review_notes(ws):
    return [n for n in ws.get("review_notes").split(NOTE_SEP) + [ws.get("edit_note")] if n]
