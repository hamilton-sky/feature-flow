"""The feature review: every ticket is resolved but some skipped their own review, so the whole feature is
reviewed once. It is no ticket's phase and has no lane; a failure becomes a fix ticket."""

import os

from feature_flow import git, prompts, scouts, state, tickets
from feature_flow.conductor import guards
from feature_flow.conductor.errors import Stop
from feature_flow.conductor.phases.base import Outcome, Phase
from feature_flow.conductor.phases.review import record_verdict, take_verdict


class Final(Phase):
    name = "final"
    lane_scoped = False
    who = "feature review"

    @classmethod
    def feature_base(cls, ws):
        """The oldest base of the deferred tickets: the feature review covers from there to HEAD."""
        bases = sorted({base for _, base in ws.deferred()})
        if len(bases) == 1:
            return bases[0]
        result = git._git("merge-base", "--octopus", *bases, check=False)
        if result.returncode != 0 or not result.stdout.strip():
            raise Stop("cannot find where the deferred tickets started: %s" % result.stderr.strip())
        return result.stdout.strip()

    @classmethod
    def hand_out(cls, ws, retry=False):
        """Every ticket is resolved but some skipped their own review: review the whole feature once."""
        ws.count_run()
        ws.all.update({"phase": "final", "num": "all", "ticket": ""})  # the log names the feature review `all`
        ws.all["final_base"] = cls.feature_base(ws)
        ws.snapshot_code()  # what check_code holds the feature review to; with lanes, no ticket's snapshot is here
        ws.all["review_attempt"] = (ws.num("review_attempt") if retry else 0) + 1  # not the last ticket's count
        ws.all["review_sha"] = git.head()
        ws.all["verdict"] = ""
        guards.mark_relay(ws, ws.all)
        ws.save()
        return ws.emit("REVIEW %s all %s" % (ws.plan.as_posix(), ws.all["final_base"]))

    @classmethod
    def judge(cls, ws):
        ws.check_code(final=True)
        note = ws.undo_edit(ws.all.get("review_sha", ""), "reviewer", "a reviewer")
        if note:
            ws.edit_retry(note, ws.num("review_attempt"), "the feature reviewer of %s kept changing files" % ws.feature)
            return Outcome(cls.hand_out(ws, retry=True))
        ws.all["edit_note"] = ""
        verdict = take_verdict(ws, ws.feature)
        if verdict == "pass":
            ws.write_due("feature review (left for later)")
            for key in ("phase", "deferred", "final_base", "final_round", "review_attempt", "review_sha", "scout_key"):
                ws.all[key] = ""
            ws.save()
            ws.log("FEATURE-PASS")
            return Outcome(ws.scheduler().resume())
        if verdict == "fail":
            round_no = ws.num("final_round") + 1
            if round_no > ws.max_rounds:
                raise Stop("the feature review of %s still fails after %d round(s). the user decides what happens next"
                           % (ws.feature, ws.max_rounds))
            path = cls.fix_ticket(ws, round_no, state.read_text(ws.findings_file, "findings") or "")
            if not git.commit_file(path, "chore(%s): fixes from the feature review, round %d" % (ws.feature, round_no)):
                raise Stop("cannot commit %s. this session must be allowed to run git commit" % path.as_posix())
            ws.all.update({"phase": "", "final_round": round_no, "review_attempt": 0, "review_sha": ""})
            ws.save()
            ws.log("FEATURE-FAIL")
            return Outcome(ws.scheduler().resume())
        if ws.num("review_attempt") >= ws.max_retries:
            raise Stop("no verdict from the feature review of %s after %d attempt(s)" % (ws.feature, ws.max_retries))
        return Outcome(cls.hand_out(ws, retry=True))

    @classmethod
    def fix_ticket(cls, ws, round_no, findings):
        """Write the feature review's findings as a new open ticket, numbered after the last one."""
        folder = ws.plan / (os.environ.get("FLOW_TICKETS") or "tasks")
        nums = [int(tickets.number(p)) for p in tickets.ticket_files(str(folder)) if tickets.number(p).isdigit()]
        num = "%02d" % (max(nums or [0]) + 1)
        path = folder / ("%s-feature-review-fixes-%d.md" % (num, round_no))
        quoted = "\n".join("> " + line if line else ">" for line in findings.strip("\n").splitlines()) or "> (none)"
        path.write_text(
            "# Fix the findings of the feature review, round %d\n\n"
            "Type: task\nStatus: open\nBlocked by: —\nTest first: no\nLevel: 2\n"
            "Check: none the feature review that follows checks these fixes\n\n"
            "The review of the whole feature (from commit %s) failed. Fix each finding below that is a blocker or a "
            "major, in the files it names. A minor is optional. If a finding is wrong, say why in the Answer instead.\n\n"
            "## Not in this ticket\n\n- Anything the findings do not name.\n\n"
            "## Done when\n\n- Every blocker and major finding below is fixed, or the Answer says why it stays.\n"
            "- commands.md's Test command passes.\n\n"
            "## Findings\n\n%s\n\n## Answer\n" % (round_no, ws.all.get("final_base", ""), quoted),
            encoding="utf-8")
        return path

    @classmethod
    def prompt(cls, ws):
        nums = [num for num, _ in ws.deferred()]
        try:
            return prompts.feature_review(ws.scripts, ws.feature, ws.plan.as_posix(), ws.all["final_base"], nums,
                                          [n for n in [cls.final_note(ws), ws.all.get("edit_note", "")] if n],
                                          os.environ.get("FLOW_TICKETS") or "tasks") + ws.scout_findings()
        except FileNotFoundError as err:
            raise Stop(str(err))

    @classmethod
    def final_note(cls, ws):
        round_no = ws.num("final_round")
        if not round_no:
            return ""
        return ("this is round %d of the feature review: the last round's findings are in the newest "
                "feature-review-fixes ticket. check that each blocker and major is fixed" % (round_no + 1))

    @classmethod
    def record(cls, ws, reply):
        return record_verdict(ws, reply, final=True)

    @classmethod
    def scout_questions(cls, ws):
        """The first round of the feature review."""
        if not ws.scouts_on:
            return []
        first = ws.num("review_attempt") == 1 and not ws.num("final_round")
        tasks = "%s/%s" % (ws.plan.as_posix(), os.environ.get("FLOW_TICKETS") or "tasks")
        return scouts.review(ws.get("final_base"), tasks) if first else []

    @classmethod
    def key(cls, ws):
        return "final:%s:%s:%s" % (ws.get("final_base"), ws.num("final_round"), ws.num("review_attempt"))
