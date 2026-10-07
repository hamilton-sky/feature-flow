"""The state machine that tells an interactive session what to do next.

It sets the limits, retries and review rounds. It judges every phase from the repo, never from the
caller, and prints exactly one line per command.
"""

import os
import re
import secrets
import shutil
from pathlib import Path

from feature_flow import checks, codehash, floorguard, git, prompts, state, suggest, tickets


VERDICT = re.compile(r"^REVIEW: (PASS|FAIL)[ \t\r\f\v]*$")


class Stop(Exception):
    """A problem the session must report. Printed as `STOP <reason>`, exit 1."""


class NoPhase(Exception):
    """`prompt` or `verdict` with nothing for it pending: nothing changes, exit 2."""


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
        self.per_session = _env_int("FLOW_TICKETS_PER_SESSION", 4)
        self.relay = os.environ.get("FLOW_RELAY", "0") == "1"
        self.invoke = os.environ.get("FLOW_INVOKE") or "/feature-flow"
        top = git.toplevel()
        if top is None:
            raise Stop("not inside a git worktree")
        try:
            folder = state.state_dir(top)
            state.migrate(git.git_dir(), folder, feature)
        except OSError as err:
            raise Stop("cannot write the flow state in %s: %s. this session must be allowed to write there"
                       % (top / state.STATE_DIR, err.strerror or err))
        self.draft_root = state.STATE_DIR / "draft"
        self.draft = self.draft_root / feature
        self.brief_file = state.STATE_DIR / ("brief-%s.md" % feature)
        self.state_file = state.state_path(folder, feature)
        self.log_file = state.log_path(folder, feature)
        self.findings_file = state.file_path(folder, feature, "findings")
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
        self.st["relay_handoff"] = "1" if self.relay else ""
        self.save()
        return self.emit("BUILD %s %s %s" % (self.ticket(), self.get("num"), self.get("base")))

    def hand_out_review(self):
        self.count_run()
        self.st["phase"] = "review"
        self.st["review_attempt"] = self.num("review_attempt") + 1
        self.st["review_sha"] = git.head()
        self.st["relay_handoff"] = "1" if self.relay else ""
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
        if not git.commit_file(self.ticket(), "chore(%s): %s review findings, round %d"
                               % (self.feature, self.get("num"), round_no)):
            raise Stop("cannot commit the %s findings to %s. this session must be allowed to run git commit"
                       % (source, self.ticket_name()))
        self.st["attempt"] = 0
        self.st["review_attempt"] = 0
        return self.hand_out_build()

    def pick_ticket(self):
        """Hand out the next ready ticket, or finish."""
        check = checks.flow_status(self.scripts, self.feature, "--check")
        if not check.ok:
            raise Stop("ticket check failed, fix the tickets first")
        dirty = git.changes()
        if dirty:
            raise Stop("working tree is not clean, commit or stash first: %s%s"
                       % (" ".join(dirty[:5]), " and %d more" % (len(dirty) - 5) if len(dirty) > 5 else ""))
        nxt = checks.flow_status(self.scripts, self.feature, "--next")
        if nxt.code == 10:
            done = self.num("done")
            self.st["phase"] = ""
            self.st["owner"] = ""
            self.save()
            return self.emit("DONE %s is complete: %d ticket(s) resolved in this run" % (self.feature, done))
        if nxt.code == 11:
            raise Stop("stuck: unfinished tickets remain but none is ready. run: python3 scripts/flow-status.py %s"
                       % self.feature)
        if nxt.code != 0:
            raise Stop("flow-status.py failed with exit code %d" % nxt.code)
        if self.per_session > 0 and self.num("session_done") >= self.per_session:
            return self.handoff()
        path = nxt.out.strip().splitlines()[-1]
        self.st.update({"ticket": path, "num": tickets.number(path), "base": git.head(), "phase": "",
                        "attempt": 0, "review_attempt": 0, "round": 0, "review_sha": ""})
        self.snapshot_code()
        self.run_smoke()
        return self.hand_out_build()

    def snapshot_code(self):
        whole, each = codehash.flow_code(self.scripts)
        self.st["code_sha"] = whole
        self.st["code_files"] = codehash.dump(each)

    def check_code(self, allowed=False):
        """Stop when the files the conductor runs from changed since the ticket was picked."""
        whole, each = codehash.flow_code(self.scripts)
        if whole == self.get("code_sha"):
            return
        if allowed:
            self.snapshot_code()
            return
        names = codehash.changed(codehash.load(self.get("code_files")), each)
        raise Stop("flow code changed while building %s: %s. if intended, the ticket needs a line: "
                   "Floor: allow flow-edit" % (self.ticket_name(), ", ".join(names)))

    def flow_edit_allowed(self):
        try:
            source = git._git("show", "%s:%s" % (self.get("base"), Path(self.ticket()).as_posix()), check=False)
        except OSError:
            return False
        if source.returncode != 0:
            return False
        return b"flow-edit" in floorguard.allow_line(source.stdout.encode("utf-8")).split()

    def judge_build(self):
        self.check_code(self.flow_edit_allowed())
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

    def handoff(self):
        """Release the owner; the user continues in a new session with the printed line."""
        self.st["owner"] = ""
        self.st["relay_handoff"] = ""
        self.save()
        return self.emit("HANDOFF %s %s" % (self.invoke, self.feature))

    def check_owner(self):
        """While a session owns the feature, every call must carry its token. Checked before any change."""
        owner = self.get("owner")
        if owner and os.environ.get("FLOW_SESSION", "") != owner:
            raise Stop("%s is owned by another session (%s). pass its token as FLOW_SESSION, or start this session "
                       "with FLOW_TAKEOVER=1 once you are sure the other one is closed" % (self.feature, owner))

    def start(self):
        if not self.plan.is_dir():
            return self.emit("PLAN")
        owner = self.get("owner")
        takeover = bool(owner)
        if owner and os.environ.get("FLOW_TAKEOVER", "0") != "1":
            raise Stop("%s is owned by session %s. if that session is closed or dead, run start with FLOW_TAKEOVER=1"
                       % (self.feature, owner))
        token = secrets.token_hex(8)
        self.st["owner"] = token
        self.st["session_done"] = 0
        self.save()
        self.log("TAKEOVER" if takeover else "START")
        return "OK %s" % token

    def next(self):
        self.check_owner()
        if not self.plan.is_dir():
            raise Stop("no plan folder %s" % self.plan)
        if self.get("relay_handoff") == "1":
            return self.handoff()
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

    def reset(self, num=None):
        """Put the feature back to a clean start: reopen a half-built ticket (or ticket num), commit that,
        and forget the run. The tickets stay the truth; only the conductor's note and counters go."""
        if not self.plan.is_dir():
            hint = suggest.hint(self.feature, suggest.features(self.root)).strip()
            raise Stop("no plan folder %s%s" % (self.plan, ". " + hint if hint else ""))
        owner = self.get("owner")
        if owner and os.environ.get("FLOW_TAKEOVER", "0") != "1":
            raise Stop("%s is owned by session %s. if that session is closed or dead, run reset with FLOW_TAKEOVER=1"
                       % (self.feature, owner))
        paths = tickets.ticket_files(str(self.plan / (os.environ.get("FLOW_TICKETS") or "tasks")))
        if num is not None:
            chosen = [p for p in paths if tickets.number(p) == num.zfill(2)]
            if not chosen:
                raise Stop("no ticket %s in %s" % (num, self.plan))
        else:
            chosen = [p for p in paths if tickets.status(p) in tickets.RESET]
        reopened = []
        for path in chosen:
            if tickets.status(path) != "open":
                tickets.set_open(path)
                reopened.append(path)
        if reopened:
            nums = ", ".join(tickets.number(p) for p in reopened)
            if not git.commit_paths(reopened, "chore(%s): reset %s to open" % (self.feature, nums)):
                raise Stop("reopened %s but could not commit it. this session must be allowed to run git commit"
                           % nums)
        had_run = self.state_file.is_file()
        for path in (self.state_file, self.findings_file):
            if path.is_file():
                path.unlink()
        if not reopened and not had_run:
            return "OK nothing to reset for %s. run %s %s" % (self.feature, self.invoke, self.feature)
        self.st = {}
        self.log("RESET")
        done = ["cleared the run state"] if had_run else []
        done += ["reopened %s" % tickets.name(p) for p in reopened]
        return "OK %s. run %s %s" % (", ".join(done), self.invoke, self.feature)

    def judge_review(self):
        self.check_code()
        if not git.tracked_clean() or git.head() != self.get("review_sha"):
            raise Stop("the reviewer changed tracked files, which a reviewer must never do")
        verdict = self.get("verdict")
        self.st["verdict"] = ""
        if verdict == "pass":
            self.st["phase"] = ""
            self.st["done"] = self.num("done") + 1
            self.st["session_done"] = self.num("session_done") + 1
            self.save()
            return self.pick_ticket()
        if verdict == "fail":
            findings = self.findings_file.read_text(encoding="utf-8") if self.findings_file.is_file() else ""
            return self.send_back("independent review", findings)
        if self.num("review_attempt") >= self.max_retries:
            raise Stop("no review verdict for %s after %d attempt(s)" % (self.ticket_name(), self.max_retries))
        return self.hand_out_review()

    def prompt(self):
        """The full prompt for the BUILD or REVIEW that `next` handed out. Exit 2 (NoPhase) when none is."""
        self.check_owner()
        phase = self.get("phase")
        if phase not in ("build", "review"):
            raise NoPhase("no BUILD or REVIEW is pending for %s" % self.feature)
        try:
            return prompts.build(phase, self.scripts, self.feature, self.ticket(), self.get("num"), self.get("base"))
        except FileNotFoundError as err:
            raise Stop(str(err))

    def verdict(self, reply):
        """Record the reviewer's reply. Exit 2 (NoPhase) unless a review is pending."""
        self.check_owner()
        if self.get("phase") != "review":
            raise NoPhase("no review is pending for %s" % self.feature)
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

    # ---- planning: stateless, the brief and the draft are all there is --

    def no_plan_yet(self):
        if self.plan.is_dir():
            raise Stop("%s already exists. pick another name: a plan is never overwritten" % self.plan.as_posix())

    def draft_text(self):
        return self.draft.as_posix() + "/"

    def read_text(self, path, what):
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as err:
            raise Stop("cannot read the %s %s: %s" % (what, path, err.strerror))

    def plan_prompt(self, brief, findings=None):
        """The feature-planner's prompt. Saves the brief; a first round (no findings) starts an empty draft."""
        self.no_plan_yet()
        text = self.read_text(brief, "brief")
        notes = self.read_text(findings, "review findings") if findings else ""
        if not text.strip():
            raise Stop("the brief %s is empty" % brief)
        if Path(brief).resolve() != self.brief_file.resolve():
            self.brief_file.write_text(text, encoding="utf-8")
        if not findings and self.draft.is_dir():
            if self.draft.resolve().parent != self.draft_root.resolve():
                raise Stop("the draft folder %s is outside %s" % (self.draft_text(), self.draft_root.as_posix()))
            shutil.rmtree(str(self.draft))
        (self.draft / (os.environ.get("FLOW_TICKETS") or "tasks")).mkdir(parents=True, exist_ok=True)
        self.log("PLAN-PROMPT")
        try:
            return prompts.plan("plan", self.scripts, self.feature, self.draft_text(), text, notes)
        except FileNotFoundError as err:
            raise Stop(str(err))

    def plan_review_prompt(self):
        """The plan-reviewer's prompt: the saved brief and the draft, nothing from the planner."""
        self.no_plan_yet()
        if not self.brief_file.is_file():
            raise Stop("no brief for %s. run plan-prompt first" % self.feature)
        if not self.draft.is_dir():
            raise Stop("no draft plan in %s. run the planner first" % self.draft_text())
        self.log("PLAN-REVIEW-PROMPT")
        try:
            return prompts.plan("plan-review", self.scripts, self.feature, self.draft_text(),
                                self.read_text(self.brief_file, "brief"))
        except FileNotFoundError as err:
            raise Stop(str(err))

    def plan_accept(self):
        """Copy a draft that passes the check into the plan folder. Never overwrites, never commits."""
        self.no_plan_yet()
        if not self.draft.is_dir():
            raise Stop("no draft plan in %s. run the planner first" % self.draft_text())
        check = checks.flow_status(self.scripts, self.feature, "--check", root=self.draft_root)
        if not check.ok:
            raise Stop("the draft fails the plan check, fix it first: %s"
                       % " ".join(check.out.split())[:400])
        self.plan.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(self.draft), str(self.plan))
        check = checks.flow_status(self.scripts, self.feature, "--check")
        if not check.ok:
            raise Stop("the accepted plan in %s fails the plan check: %s"
                       % (self.plan.as_posix(), " ".join(check.out.split())[:400]))
        self.log("PLAN-ACCEPT")
        return "OK %s" % self.plan.as_posix()
