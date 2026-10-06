"""The state machine that tells an interactive session what to do next.

It copies the policy of the old headless loop (scripts/auto-flow.sh): the same limits,
retries, review rounds and messages. It judges every phase from the repo, never from the
caller, and prints exactly one line per command.
"""

import os
import re
from pathlib import Path

from feature_flow import checks, git, state, tickets


VERDICT = re.compile(r"^REVIEW: (PASS|FAIL)[ \t\r\f\v]*$")


class Stop(Exception):
    """A problem the session must report. Printed as `STOP <reason>`, exit 1."""


class NoReview(Exception):
    """`verdict` with no review pending: nothing changes, exit 2."""


def _env_int(name, default):
    value = os.environ.get(name, "")
    try:
        return int(value) if value.strip() else default
    except ValueError:
        raise Stop("%s must be a whole number, not %s" % (name, value))


class Conductor:
    def __init__(self, feature, scripts):
        self.feature = feature
        self.scripts = Path(scripts)
        self.root = Path(os.environ.get("FLOW_DIR") or "plans")
        self.plan = self.root / feature
        self.commands = self.plan / "commands.md"
        self.max_retries = _env_int("FLOW_MAX_RETRIES", 2)
        self.max_rounds = _env_int("FLOW_MAX_REVIEW_ROUNDS", 3)
        self.gate_on = os.environ.get("FLOW_GATE", "on") != "off"
        gdir = git.git_dir()
        if gdir is None:
            raise Stop("not inside a git repository")
        self.state_file = state.state_path(gdir, feature)
        self.log_file = state.log_path(gdir, feature)
        self.findings_file = Path(gdir) / ("flow-%s.findings" % feature)
        self.st = state.load(self.state_file)

    # ---- small helpers -------------------------------------------------

    def get(self, key, default=""):
        return self.st.get(key, default)

    def num(self, key):
        try:
            return int(self.st.get(key, "0") or 0)
        except ValueError:
            raise Stop("the state file %s is damaged: %s is not a number" % (self.state_file, key))

    def save(self):
        state.save(self.state_file, self.st)

    def log(self, event):
        state.log(self.log_file, self.get("num"), event)

    def emit(self, line):
        self.log(line.split(" ", 1)[0])
        return line

    def ticket(self):
        return self.get("ticket")

    def ticket_name(self):
        return tickets.name(self.ticket())

    # ---- the checks ----------------------------------------------------

    def smoke_command(self):
        cmd = os.environ.get("FLOW_SMOKE", "")
        if not cmd:
            cmd = tickets.commands_value(self.commands, "Smoke")
        return "" if cmd.startswith("<") else cmd

    def run_smoke(self):
        cmd = self.smoke_command()
        if not cmd:
            return
        result = checks.smoke(cmd)
        if not result.ok:
            raise Stop("smoke test failed before %s: the base is already broken. fix it first. command: %s"
                       % (self.ticket_name(), cmd))

    def run_limit(self):
        result = checks.flow_status(self.scripts, self.feature, "--counts")
        total = 0
        for word in result.out.split():
            if word.startswith("total="):
                total = int(word[len("total="):])
        return total * 2 * self.max_retries * (self.max_rounds + 1) + 1

    def count_run(self):
        runs = self.num("runs") + 1
        limit = self.num("limit")
        if runs > limit:
            raise Stop("run limit of %d sessions reached, stopping" % limit)
        self.st["runs"] = runs

    # ---- phases --------------------------------------------------------

    def hand_out_build(self):
        self.count_run()
        self.st["phase"] = "build"
        self.st["attempt"] = self.num("attempt") + 1
        self.save()
        return self.emit("BUILD %s %s %s" % (self.ticket(), self.get("num"), self.get("base")))

    def hand_out_review(self):
        self.count_run()
        self.st["phase"] = "review"
        self.st["review_attempt"] = self.num("review_attempt") + 1
        self.st["review_sha"] = git.head()
        self.save()
        return self.emit("REVIEW %s %s %s" % (self.ticket(), self.get("num"), self.get("base")))

    def send_back(self, source, findings):
        """Write the findings into the ticket, reopen it, commit, and build again."""
        round_no = self.num("round") + 1
        if round_no > self.max_rounds:
            raise Stop("%s still fails the %s after %d round(s)" % (self.ticket_name(), source, self.max_rounds))
        self.st["round"] = round_no
        tickets.append_findings(self.ticket(), round_no, source, findings)
        tickets.set_open(self.ticket())
        git.commit_file(self.ticket(), "chore(%s): %s review findings, round %d"
                        % (self.feature, self.get("num"), round_no))
        self.st["attempt"] = 0
        self.st["review_attempt"] = 0
        return self.hand_out_build()

    def pick_ticket(self):
        """Hand out the next ready ticket, or finish."""
        check = checks.flow_status(self.scripts, self.feature, "--check")
        if not check.ok:
            raise Stop("ticket check failed, fix the tickets first")
        if not git.is_clean():
            raise Stop("working tree is not clean, commit or stash first")
        nxt = checks.flow_status(self.scripts, self.feature, "--next")
        if nxt.code == 10:
            done = self.num("done")
            self.st["phase"] = ""
            self.save()
            return self.emit("DONE %s is complete: %d ticket(s) resolved in this run" % (self.feature, done))
        if nxt.code == 11:
            raise Stop("stuck: unfinished tickets remain but none is ready. run: bash scripts/flow-status.sh %s"
                       % self.feature)
        if nxt.code != 0:
            raise Stop("flow-status.sh failed with exit code %d" % nxt.code)
        path = nxt.out.strip().splitlines()[-1]
        self.st.update({"ticket": path, "num": tickets.number(path), "base": git.head(), "phase": "",
                        "attempt": 0, "review_attempt": 0, "round": 0, "review_sha": ""})
        self.run_smoke()
        return self.hand_out_build()

    def judge_build(self):
        status = tickets.status(self.ticket())
        if status not in tickets.DONE:
            if status in tickets.RESET:
                tickets.set_open(self.ticket())
            if self.num("attempt") >= self.max_retries:
                raise Stop("%s is still unresolved after %d attempt(s)" % (self.ticket_name(), self.max_retries))
            return self.hand_out_build()
        if not git.is_clean():
            raise Stop("working tree is dirty after %s, it should have been committed" % self.ticket_name())
        if self.gate_on:
            result = checks.gate(self.scripts, self.feature)
            self.log("GATE-PASS" if result.ok else "GATE-FAIL")
            if not result.ok:
                return self.send_back("gate", result.out)
        result = checks.floor_guard(self.scripts, self.feature, self.get("num"), self.get("base"))
        self.log("GUARD-PASS" if result.ok else "GUARD-FAIL")
        if not result.ok:
            return self.send_back("floor guard", result.out)
        return self.hand_out_review()

    # ---- commands ------------------------------------------------------

    def next(self):
        if not self.plan.is_dir():
            raise Stop("no plan folder %s" % self.plan)
        if "limit" not in self.st:
            self.st["limit"] = self.run_limit()
            self.st.setdefault("runs", 0)
            self.st.setdefault("done", 0)
        phase = self.get("phase")
        if phase == "build":
            return self.judge_build()
        if phase == "review":
            return self.judge_review()
        return self.pick_ticket()

    def judge_review(self):
        if not git.tracked_clean() or git.head() != self.get("review_sha"):
            raise Stop("the reviewer changed tracked files, which a reviewer must never do")
        verdict = self.get("verdict")
        self.st["verdict"] = ""
        if verdict == "pass":
            self.st["phase"] = ""
            self.st["done"] = self.num("done") + 1
            self.save()
            return self.pick_ticket()
        if verdict == "fail":
            findings = self.findings_file.read_text(encoding="utf-8") if self.findings_file.is_file() else ""
            return self.send_back("independent review", findings)
        if self.num("review_attempt") >= self.max_retries:
            raise Stop("no review verdict for %s after %d attempt(s)" % (self.ticket_name(), self.max_retries))
        return self.hand_out_review()

    def verdict(self, reply):
        """Record the reviewer's reply. Exit 2 (NoReview) unless a review is pending."""
        if self.get("phase") != "review":
            raise NoReview("no review is pending for %s" % self.feature)
        try:
            text = Path(reply).read_text(encoding="utf-8", errors="replace")
        except OSError as err:
            raise Stop("cannot read the review reply %s: %s" % (reply, err.strerror))
        found = ""
        for line in text.splitlines():
            match = VERDICT.match(line)
            if match:
                found = match.group(1).lower()
        if found == "fail":
            self.findings_file.write_text("\n".join(text.splitlines()[:120]) + "\n", encoding="utf-8")
        self.st["verdict"] = found or "none"
        self.save()
        self.log("VERDICT-%s" % (found or "none").upper())
        return "OK" if found else "RETRY no review verdict"
