"""The build of a ticket: handed to a builder, then judged by the check pipeline and the review policy."""

from feature_flow import git, lanes, prompts, proof, scouts, tickets
from feature_flow.conductor import buildchecks
from feature_flow.conductor.errors import Stop
from feature_flow.conductor.phases import ask as ask_phase
from feature_flow.conductor.phases import review as review_phase
from feature_flow.conductor.phases.base import Outcome, Phase, ticket_prompt
from feature_flow.conductor.policy import review
from feature_flow.conductor.store import NOTE_SEP


class Build(Phase):
    name = "build"

    @classmethod
    def hand_out(cls, ws):
        ws.count_run()
        ws.st["phase"] = "build"
        ws.st["attempt"] = ws.num("attempt") + 1
        ws.st["relay_handoff"] = "1" if ws.relay else ""
        ws.save()
        return ws.emit("BUILD %s %s %s%s" % (ws.ticket(), ws.get("num"), ws.get("base"), ws.lane_word()))

    @classmethod
    def judge(cls, ws):
        ws.check_code(ws.flow_edit_allowed())
        if ws.get("batch"):
            return Outcome(ws.scheduler().judge_batch())
        status = tickets.status(ws.ticket())
        if status not in tickets.DONE:
            if status in tickets.RESET:
                tickets.set_open(ws.ticket())
            role, question = ask_phase.Ask.open_ask(ws)
            if role:
                return Outcome(ask_phase.Ask.hand_out(ws, "build", role, question))
            if ws.num("attempt") >= ws.max_retries:
                raise Stop("%s is still unresolved after %d attempt(s)" % (ws.ticket_name(), ws.max_retries))
            return Outcome(cls.hand_out(ws))
        if not git.is_clean():
            raise Stop("working tree is dirty after %s, it should have been committed" % ws.ticket_name())
        source, report, notes = buildchecks.run(ws, buildchecks.pipeline(ws))
        if source:
            return Outcome(ws.send_back(source, report))
        level = ws.measure_level()
        decision, review_pass, more, events = review.after_checks(
            level, ws.fast(), ws.gate_on, ws.checks_ran, ws.small_note() if level == 0 else "",
            proof.review_mode(ws.ticket_at_base()), ws.get("spec_ok"), ws.num("round"), ws.get("level_note"))
        if decision == "defer":
            return Outcome(ws.defer_review(), True)
        ws.st["review_pass"] = review_pass
        for event in events:
            if event == "REVIEW-SINGLE":
                ws.st["level_raised"] = ""
            ws.log(event)
        ws.st["review_notes"] = NOTE_SEP.join(notes + more)
        return Outcome(review_phase.Review.hand_out(ws))

    @classmethod
    def prompt(cls, ws):
        if ws.get("batch"):
            try:
                return prompts.build("build", ws.scripts, ws.feature, ws.ticket(), ws.get("num"), ws.get("base"),
                                     ) + "\n" + ws.scheduler().batch_note() + "\n" + ws.scout_findings()
            except FileNotFoundError as err:
                raise Stop(str(err))
        return ticket_prompt(ws, "build")

    @classmethod
    def scout_questions(cls, ws):
        """A build's first attempt above level 1 (or with no level), never in a later round or after a question."""
        if not ws.scouts_on or ws.num("round") or ws.num("asks") or ws.num("attempt") != 1:
            return []
        return scouts.build(proof.repo_relative(ws.ticket()), ws.get("base"), lanes.touches(ws.ticket_at_base()) or [],
                            ws.num("level"))
