"""The state machine that tells an interactive session what to do next.

It sets the limits, retries and review rounds. It judges every phase from the repo, never from the
caller, and prints exactly one line per command.
"""

import hashlib
import os
import re
import secrets
import shutil
import time
from pathlib import Path

from feature_flow import checks, codehash, floorguard, gate, git, prompts, proof, report, state, suggest, tickets


NOTE_SEP = "\t"  # the state file keeps one line per key, so the review notes are tab separated
VERDICT = re.compile(r"^REVIEW: (PASS|FAIL)[ \t\r\f\v]*$")
AREAS = ("correctness", "security", "performance")  # the phase review's lenses, guides/review-phase.md
# what a handed-out subagent adds to the session's context besides its prompt (its reply, the conductor's lines)
PHASE_COST = 4000
OLD_OWNER = re.compile(r"^[0-9a-f]{16}$")  # a raw token, stored by a run started before 0.5.0


def owner_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
        self.gate_timeout = _env_int("FLOW_GATE_TIMEOUT", 30)
        self.gate_on = os.environ.get("FLOW_GATE", "on") != "off"
        # FLOW_TICKETS_PER_SESSION, when set, hands off after that many tickets (0 never). Unset, the session hands
        # off once the text it was handed passes FLOW_SESSION_BUDGET bytes (0 never), so a session whose subagents
        # read their prompts from files goes on much longer than one that copies every prompt
        self.per_session = _env_int("FLOW_TICKETS_PER_SESSION", 0)
        counted = os.environ.get("FLOW_TICKETS_PER_SESSION", "").strip() != ""
        self.session_budget = 0 if counted else _env_int("FLOW_SESSION_BUDGET", 250000)
        self.budget_minutes = _env_int("FLOW_BUDGET_MINUTES", 0)
        self.budget_tokens = _env_int("FLOW_BUDGET_TOKENS", 0)
        self.small_files = _env_int("FLOW_SMALL_FILES", 3)
        self.small_lines = _env_int("FLOW_SMALL_LINES", 60)
        self.gate_review_lines = _env_int("FLOW_REVIEW_GATE_LINES", 400)
        self.phase_on = os.environ.get("FLOW_PHASE_REVIEW", "on") != "off"
        self.areas = [a.strip() for a in (os.environ.get("FLOW_PHASE_AREAS") or ",".join(AREAS)).split(",") if a.strip()]
        if not self.areas or len(self.areas) > 3 or any(a not in AREAS for a in self.areas):
            raise Stop("FLOW_PHASE_AREAS must name one to three of %s, not %s"
                       % (", ".join(AREAS), os.environ.get("FLOW_PHASE_AREAS")))
        self.track_plan = os.environ.get("FLOW_TRACK_PLAN", "").strip().lower() or "auto"
        if self.track_plan not in ("auto", "yes"):
            raise Stop("FLOW_TRACK_PLAN must be auto or yes, not %s" % os.environ.get("FLOW_TRACK_PLAN"))
        self.checks_ran = False
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
        self.copy_file = state.file_path(folder, feature, "ticket")
        state.read_bytes(self.findings_file, "findings")  # so a call that never touches it still reports it
        try:
            self.st = state.load(self.state_file, "state")
        except UnicodeDecodeError:
            raise Stop("the state file %s is damaged: it is not UTF-8 text" % self.state_file)

    # ---- small helpers -------------------------------------------------

    def get(self, key, default=""):
        return self.st.get(key, default)

    def num(self, key):
        try:
            return int(self.st.get(key, "0") or 0)
        except ValueError:
            raise Stop("the state file %s is damaged: %s is not a number" % (self.state_file, key))

    def save(self):
        state.save(self.state_file, self.st, "state")

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
        result = checks.smoke(cmd, self.gate_timeout)
        if not result.ok:
            log = self.state_file.with_name("%s.smoke.log" % self.feature)
            text = result.out
            if result.timed_out:
                text += "\nsmoke test timed out after %d minutes\n" % self.gate_timeout
            log.write_text(gate.tail(text), encoding="utf-8")
            raise Stop("smoke test %s before %s: the base is already broken. fix it first. command: %s. "
                       "the last %d lines are in %s"
                       % ("timed out after %d minutes" % self.gate_timeout if result.timed_out else "failed",
                          self.ticket_name(), cmd, gate.TAIL, log))

    def gate_quick(self):
        """True when this ticket's gate may run Quick in place of Test."""
        if os.environ.get("FLOW_GATE_FULL") == "1":
            return False
        if not tickets.commands_value(self.commands, "Quick"):
            return False
        if proof.gate_mode(self.ticket_at_base()) == "full":
            return False
        if self.per_session > 0 and self.num("session_done") + 1 >= self.per_session:
            return False
        counts = {}
        for word in checks.flow_status(self.scripts, self.feature, "--counts").out.split():
            key, _, value = word.partition("=")
            if value.isdigit():
                counts[key] = int(value)
        return sum(counts.get(k, 0) for k in ("open", "claimed", "waiting", "unknown")) > 0

    def run_limit(self):
        result = checks.flow_status(self.scripts, self.feature, "--counts")
        total = 0
        for word in result.out.split():
            if word.startswith("total="):
                total = int(word[len("total="):])
        return total * 3 * self.max_retries * (self.max_rounds + 1) + 1

    def charge(self, size):
        """Add size bytes to what this session's context holds, for the adaptive handoff."""
        self.st["session_load"] = self.num("session_load") + size

    def spent(self):
        """Log FLOW_TOKENS, the tokens the session's last subagent used, against the current ticket."""
        value = os.environ.get("FLOW_TOKENS", "").strip()
        if not value:
            return
        if not value.isdigit():
            raise Stop("FLOW_TOKENS must be a whole number, not %s" % value)
        self.log("SPENT %s" % value)

    def over_budget(self):
        """What is over FLOW_BUDGET_MINUTES or FLOW_BUDGET_TOKENS in this run, or "" when nothing is."""
        if self.budget_minutes <= 0 and self.budget_tokens <= 0:
            return ""
        minutes, tokens = report.usage(report.timed(state.read_text(self.log_file) or ""))
        over = []
        if 0 < self.budget_minutes <= minutes:
            over.append("%d of %d minutes" % (minutes, self.budget_minutes))
        if 0 < self.budget_tokens <= tokens:
            over.append("%d of %d tokens" % (tokens, self.budget_tokens))
        return " and ".join(over)

    def count_run(self):
        runs = self.num("runs") + 1
        limit = self.num("limit")
        if runs > limit:
            raise Stop("run limit of %d phases reached, stopping" % limit)
        self.st["runs"] = runs

    # ---- phases --------------------------------------------------------

    def hand_out_build(self):
        self.count_run()
        self.st["phase"] = "build"
        self.st["attempt"] = self.num("attempt") + 1
        self.st["relay_handoff"] = "1" if self.relay else ""
        self.charge(PHASE_COST)
        self.save()
        return self.emit("BUILD %s %s %s" % (self.ticket(), self.get("num"), self.get("base")))

    def hand_out_review(self):
        self.count_run()
        self.st["phase"] = "review"
        self.st["review_pass"] = self.get("review_pass") or "spec"
        self.st["review_attempt"] = self.num("review_attempt") + 1
        self.st["review_sha"] = git.head()
        self.st["relay_handoff"] = "1" if self.relay else ""
        self.st["must_review"] = "1"  # once a reviewer has seen it, every rebuild is reviewed too
        self.charge(PHASE_COST)
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
        if not self.commit_plan([self.ticket()], "chore(%s): %s review findings, round %d"
                                % (self.feature, self.get("num"), round_no)):
            raise Stop("cannot commit the %s findings to %s. this session must be allowed to run git commit"
                       % (source, self.ticket_name()))
        self.st["attempt"] = 0
        self.st["review_attempt"] = 0
        self.st["review_pass"] = "spec"
        return self.hand_out_build()

    def commit_plan(self, paths, message):
        """Commit the plan files git does not ignore, or all of them with FLOW_TRACK_PLAN=yes (added with -f).
        An ignored file keeps the change in the working copy only. True when that worked."""
        force = self.track_plan == "yes"
        keep = [p for p in paths if force or not git.ignored(p)]
        return not keep or git.commit_paths(keep, message, force)

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
        over = self.over_budget()
        if over:
            raise Stop("budget reached: %s spent in this run. ask the user whether to go on; to go on, raise "
                       "FLOW_BUDGET_MINUTES or FLOW_BUDGET_TOKENS" % over)
        if self.per_session > 0 and self.num("session_done") >= self.per_session:
            return self.handoff()
        if (self.session_budget > 0 and self.num("session_done") > 0
                and self.num("session_load") >= self.session_budget):
            return self.handoff()
        path = nxt.out.strip().splitlines()[-1]
        self.st["limit"] = self.run_limit()
        self.phase_base()
        if self.phase_review_due(path):
            return self.hand_out_phase(path, self.areas)
        fix = path == self.get("phase_fix")
        self.st.update({"ticket": path, "num": tickets.number(path), "base": git.head(), "phase": "", "phase_fix": "",
                        "attempt": 0, "review_attempt": 0, "round": 1 if fix else 0, "review_sha": "", "review_notes": "",
                        "review_pass": "spec", "must_review": "1" if fix else ""})
        self.snapshot_code()
        self.snapshot_ticket()
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
        return "flow-edit" in floorguard.allow_line(source.stdout).split()

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
            quick = self.gate_quick()
            started = time.monotonic()
            result = checks.gate(self.scripts, self.feature, self.gate_timeout, quick=quick, base=self.get("base"))
            self.log("GATE-QUICK" if quick else "GATE-FULL")
            self.log("%s %ds" % ("GATE-PASS" if result.ok else "GATE-FAIL", time.monotonic() - started))
            if not result.ok:
                return self.send_back("gate (quick)" if quick else "gate (full)", result.out)
        result = checks.floor_guard(self.scripts, self.feature, self.get("num"), self.get("base"))
        edit = self.untracked_ticket_edit() if result.ok else ""
        self.log("GUARD-PASS" if result.ok and not edit else "GUARD-FAIL")
        if not result.ok:
            return self.send_back("floor guard", result.out)
        if edit:
            return self.send_back("floor guard", edit)
        warnings = [l for l in result.out.splitlines() if l.startswith("warning:")]
        notes = warnings[:1]
        if self.gate_on:
            report, note = self.run_done_when()
            if report is not None:
                return self.send_back("done when", report)
            notes.append(note)
            report, note = self.run_test_first()
            if report is not None:
                return self.send_back("test first", report)
            if note:
                notes.append(note)
        self.st["review_pass"] = "spec"
        if self.gate_only():
            self.log("REVIEW-SKIP")
            return self.pass_ticket()
        if self.gate_on and self.checks_ran:
            small = self.small_note()
            if small:
                self.st["review_pass"] = "single"
                self.log("REVIEW-SMALL")
                notes.append(small)
        self.st["review_notes"] = NOTE_SEP.join(notes)
        return self.hand_out_review()

    def gate_only(self):
        """True when a `Review: gate` ticket needs no fresh reviewer: its check block ran and passed, it is not
        a convert ticket, and its diff is at most FLOW_REVIEW_GATE_LINES changed lines (a bigger one gets reviewed).
        A ticket a reviewer already saw, or one carrying the phase review's fixes, is always reviewed."""
        if not (self.gate_on and self.checks_ran) or self.gate_review_lines <= 0 or self.get("must_review") == "1":
            return False
        base = self.ticket_at_base()
        if proof.review_mode(base) != "gate" or proof.header(base, "Type") == "convert":
            return False
        files, lines, binary = git.diff_size(self.get("base"), "HEAD", self.plan.as_posix())
        return not binary and lines <= self.gate_review_lines

    def pass_ticket(self):
        """The ticket passed: count it and pick the next one."""
        self.st["phase"] = ""
        self.st["done"] = self.num("done") + 1
        self.st["session_done"] = self.num("session_done") + 1
        self.save()
        return self.pick_ticket()

    # ---- the phase review ----------------------------------------------

    def phase_base(self):
        """The commit the phase review's range starts from, kept in the state and the log (a reset keeps the
        log): the commit that added the plan's tickets when git has it, else HEAD when the run began."""
        if self.get("phase_base"):
            return self.get("phase_base")
        base = ""
        for line in (state.read_text(self.log_file) or "").splitlines():
            event = line.split(",", 2)[-1].split()
            if len(event) == 2 and event[0] == "PHASE-BASE":
                base = event[1]
                break
        if not base:
            folder = (self.plan / (os.environ.get("FLOW_TICKETS") or "tasks")).as_posix()
            added = git._git("log", "--diff-filter=A", "--reverse", "--format=%H", "--", folder, check=False)
            base = added.stdout.split()[0] if added.returncode == 0 and added.stdout.split() else git.head()
            self.log("PHASE-BASE %s" % base)
        self.st["phase_base"] = base
        return base

    def phase_review_due(self, path):
        """True when the ready ticket is the plan's `Type: acceptance` ticket, every other ticket is done, and
        this run has not had its phase review yet (FLOW_PHASE_REVIEW=off turns this off)."""
        if not self.phase_on or self.get("phase_done") == "1":
            return False
        if proof.header(Path(path).read_text(encoding="utf-8"), "Type") != "acceptance":
            return False
        g = tickets.Graph(tickets.ticket_files(str(Path(path).parent)))
        return all(g.stat[t] in ("resolved", "parked") or g.path[t] == path for t in g.order)

    def hand_out_phase(self, target, areas):
        """PHASE-REVIEW: two or three fresh reviewers, one per area, read the whole range at once."""
        self.count_run()
        if self.get("phase") != "phase-review":
            self.snapshot_code()
            state.remove(self.findings_file, "findings")
            self.st.update({"phase": "phase-review", "phase_verdicts": "", "phase_attempt": 0,
                            "phase_head": git.head(), "phase_areas": ",".join(areas), "phase_target": target,
                            "num": "phase", "review_notes": ""})
        self.st["phase_attempt"] = self.num("phase_attempt") + 1
        self.st["relay_handoff"] = "1" if self.relay else ""
        self.charge(PHASE_COST * len(areas))
        self.save()
        return self.emit("PHASE-REVIEW %s %s %s %s"
                         % (self.feature, self.phase_base(), self.get("phase_head"), ",".join(areas)))

    def phase_verdicts(self):
        return dict(item.split("=", 1) for item in self.get("phase_verdicts").split(",") if "=" in item)

    def judge_phase(self):
        """After the phase reviewers: hand out the areas still without a verdict, or finish the review. Failed
        areas write their findings into the acceptance ticket, and its build is the one fix pass."""
        self.check_code()
        if not git.tracked_clean() or git.head() != self.get("phase_head"):
            raise Stop("a phase reviewer changed tracked files, which a reviewer must never do")
        areas = [a for a in self.get("phase_areas").split(",") if a]
        verdicts = self.phase_verdicts()
        missing = [a for a in areas if verdicts.get(a) not in ("pass", "fail")]
        if missing:
            if self.num("phase_attempt") >= self.max_retries:
                raise Stop("no phase review verdict from %s after %d attempt(s)" % (", ".join(missing), self.max_retries))
            return self.hand_out_phase(self.get("phase_target"), missing)
        failed = [a for a in areas if verdicts[a] == "fail"]
        target = self.get("phase_target")
        self.st["phase"] = ""
        self.st["phase_done"] = "1"
        self.log("PHASE-FAIL" if failed else "PHASE-PASS")
        if failed:
            findings = state.read_text(self.findings_file, "findings") or ""
            tickets.append_findings(target, 1, "phase review: %s" % ", ".join(failed), findings)
            if tickets.status(target) != "open":
                tickets.set_open(target)
            if not self.commit_plan([target], "chore(%s): phase review findings for %s"
                                    % (self.feature, tickets.number(target))):
                raise Stop("cannot commit the phase review findings to %s. this session must be allowed to run "
                           "git commit" % tickets.name(target))
            self.st["phase_fix"] = target
        self.save()
        return self.pick_ticket()

    def review_phase(self):
        """`review-phase`: the phase review now, between tickets, over everything since the phase base. Its
        findings go to the plan's last ticket, which is reopened when it was already done."""
        self.check_owner()
        if self.get("phase") in ("build", "review", "phase-review"):
            raise Stop("a %s is pending for %s. run review-phase between tickets"
                       % (self.get("phase").replace("-", " "), self.feature))
        if not self.plan.is_dir():
            raise Stop("no plan folder %s" % self.plan)
        dirty = git.changes()
        if dirty:
            raise Stop("working tree is not clean, commit or stash first: %s" % " ".join(dirty[:5]))
        paths = tickets.ticket_files(str(self.plan / (os.environ.get("FLOW_TICKETS") or "tasks")))
        if not paths:
            raise Stop("no tickets in %s" % self.plan)
        self.ensure_run()
        self.phase_base()
        return self.hand_out_phase(paths[-1], self.areas)

    def small_note(self):
        """The note for the reviewer when the built diff is small enough for one review, else ""."""
        base = self.ticket_at_base()
        if proof.review_mode(base) != "auto" or self.small_lines <= 0:
            return ""
        if re.search(r"^Type:[ \t]*convert\b", base.split("\n## ", 1)[0], re.IGNORECASE | re.MULTILINE):
            return ""
        files, lines, binary = git.diff_size(self.get("base"), "HEAD", self.plan.as_posix())
        if binary or files > self.small_files or lines > self.small_lines:
            return ""
        return ("the conductor judged this ticket small (%d files, %d lines): one review covers the spec and "
                "quality passes" % (files, lines))

    def at_base(self):
        """True when git has the ticket at the base commit (False for a plan folder git ignores, or a new ticket)."""
        rel = proof.repo_relative(self.ticket())
        listed = git._git("ls-tree", "--name-only", self.get("base"), "--", rel, check=False)
        if listed.returncode != 0:
            raise Stop("cannot read %s at the base commit: %s" % (rel, listed.stderr.strip()))
        return bool(listed.stdout.strip())

    def snapshot_ticket(self):
        """Git has no copy of a ticket it does not track, so keep the ticket as it is before the work in
        the state folder, with its sha256 in the state file, for the checks and the ticket-edit guard."""
        self.st["ticket_copy"] = ""
        if self.at_base():
            return
        text = Path(self.ticket()).read_text(encoding="utf-8")
        state.write_text(self.copy_file, text)
        self.st["ticket_copy"] = hashlib.sha256(text.encode("utf-8")).hexdigest()

    def ticket_copy(self):
        """The conductor's copy of an untracked ticket from before the work, or None when it kept none."""
        if not self.get("ticket_copy"):
            return None
        text = state.read_text(self.copy_file)
        if text is None or hashlib.sha256(text.encode("utf-8")).hexdigest() != self.get("ticket_copy"):
            raise Stop("the conductor's copy of %s in %s is missing or was changed. run reset"
                       % (self.ticket_name(), self.copy_file))
        return text

    def ticket_at_base(self):
        """The ticket text as it was at the base commit, so a builder cannot change what is checked."""
        rel = proof.repo_relative(self.ticket())
        if self.at_base():
            return git.show_text("%s:%s" % (self.get("base"), rel))
        text = self.ticket_copy()
        if text is None:
            text = Path(self.ticket()).read_text(encoding="utf-8")
        return text.split("\n## Answer", 1)[0]

    def untracked_ticket_edit(self):
        """The floor guard reads the ticket's history from git, which has none for an untracked ticket:
        compare it with the conductor's copy instead. The finding, or "" when the text above the Answer
        (the Status line aside) is unchanged or the ticket allows ticket-edit."""
        before = self.ticket_copy()
        if before is None or "ticket-edit" in floorguard.allow_line(before).split():
            return ""
        now = Path(self.ticket()).read_text(encoding="utf-8")
        if floorguard.frozen(before) == floorguard.frozen(now):
            return ""
        return ("floor guard: the diff weakens the bar instead of meeting it\n"
                "ticket-edit: %s: text outside the Status line and the Answer was changed\n"
                "if a finding is intended, the ticket needs a line like: Floor: allow <category>"
                % proof.repo_relative(self.ticket()))

    def run_done_when(self):
        """Run the ticket's check block. Returns (failure report or None, note for the reviewer)."""
        try:
            found = proof.checks_in(self.ticket_at_base())
        except proof.ParseError as err:
            raise Stop("%s has a check block the conductor cannot read: %s" % (self.ticket_name(), err))
        self.checks_ran = bool(found)
        if not found:
            self.log("DONEWHEN-SKIP")
            return None, "the conductor ran no Done when checks: the ticket has no check block"
        ok, report = proof.run_checks(found, self.gate_timeout)
        dirty = git.changes()
        if dirty:
            raise Stop("a Done when check of %s changed the working tree: %s. a check command must not change it"
                       % (self.ticket_name(), " ".join(dirty[:5])))
        self.log("DONEWHEN-PASS" if ok else "DONEWHEN-FAIL")
        if not ok:
            return report, ""
        return None, "the conductor ran %d Done when check(s) and all passed" % len(found)

    def run_test_first(self):
        """For a `Test first: yes` ticket, prove a test-only commit failed the Test command.
        Returns (failure report or None, note for the reviewer or "")."""
        if not proof.wants_test_first(self.ticket_at_base()):
            return None, ""
        test = tickets.commands_value(self.commands, "Test")
        if not test:
            self.log("TESTFIRST-SKIP")
            return None, "the conductor did not check test first: commands.md has no Test command"

        def remember(value):
            self.st["restore"] = value
            self.save()
        try:
            ok, text = proof.test_first(self.get("base"), test, self.plan, self.gate_timeout, remember)
        except proof.GitError as err:
            raise Stop("test first check of %s: %s" % (self.ticket_name(), err))
        self.log("TESTFIRST-PASS" if ok else "TESTFIRST-FAIL")
        return (None, text) if ok else (text, "")

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
        token = os.environ.get("FLOW_SESSION", "")
        if not owner or owner_hash(token) == owner:
            return
        if OLD_OWNER.match(owner) and token == owner:
            self.st["owner"] = owner_hash(token)  # stored as the hash on the next save
            return
        raise Stop("%s is owned by another session (%s). pass its token as FLOW_SESSION, or start this session "
                   "with FLOW_TAKEOVER=1 once you are sure the other one is closed" % (self.feature, owner[:8]))

    def start(self):
        if not self.plan.is_dir():
            return self.emit("PLAN")
        owner = self.get("owner")
        takeover = bool(owner)
        if owner and os.environ.get("FLOW_TAKEOVER", "0") != "1":
            raise Stop("%s is owned by session %s. if that session is closed or dead, run start with FLOW_TAKEOVER=1"
                       % (self.feature, owner[:8]))
        token = secrets.token_hex(8)
        self.st["owner"] = owner_hash(token)
        self.st["session_done"] = 0
        self.st["session_load"] = 0
        self.save()
        self.log("TAKEOVER" if takeover else "START")
        return "OK %s" % token

    def next(self):
        self.check_owner()
        if self.get("restore"):
            try:
                git._git("checkout", "-q", self.get("restore"))
            except RuntimeError as err:
                raise Stop("cannot put the working copy back after the test first check: %s. run `git checkout %s` "
                           "by hand" % (err, self.get("restore")))
            self.st["restore"] = ""
            self.save()
        if not self.plan.is_dir():
            raise Stop("no plan folder %s" % self.plan)
        if self.get("relay_handoff") == "1":
            return self.handoff()
        self.ensure_run()
        phase = self.get("phase")
        if phase == "build":
            return self.judge_build()
        if phase == "review":
            return self.judge_review()
        if phase == "phase-review":
            return self.judge_phase()
        return self.pick_ticket()

    def ensure_run(self):
        if "limit" not in self.st:
            self.st["limit"] = self.run_limit()
            self.st.setdefault("runs", 0)
            self.st.setdefault("done", 0)

    def reset(self, num=None):
        """Put the feature back to a clean start: reopen a half-built ticket (or ticket num), commit that,
        and forget the run. The tickets stay the truth; only the conductor's note and counters go."""
        if not self.plan.is_dir():
            hint = suggest.hint(self.feature, suggest.features(self.root)).strip()
            raise Stop("no plan folder %s%s" % (self.plan, ". " + hint if hint else ""))
        owner = self.get("owner")
        if owner and os.environ.get("FLOW_TAKEOVER", "0") != "1":
            raise Stop("%s is owned by session %s. if that session is closed or dead, run reset with FLOW_TAKEOVER=1"
                       % (self.feature, owner[:8]))
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
            if not self.commit_plan(reopened, "chore(%s): reset %s to open" % (self.feature, nums)):
                raise Stop("reopened %s but could not commit it. this session must be allowed to run git commit"
                           % nums)
        had_run = self.state_file.is_file()
        for path, kind in ((self.state_file, "state"), (self.findings_file, "findings"), (self.copy_file, None)):
            state.remove(path, kind)
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
        if verdict == "pass" and self.get("review_pass", "spec") == "spec":
            self.st["review_pass"] = "quality"
            self.st["review_attempt"] = 0
            return self.hand_out_review()
        if verdict == "pass":
            return self.pass_ticket()
        if verdict == "fail":
            findings = state.read_text(self.findings_file, "findings") or ""
            return self.send_back({"quality": "quality review", "single": "single review"}.get(
                self.get("review_pass"), "spec review"), findings)
        if self.num("review_attempt") >= self.max_retries:
            raise Stop("no review verdict for %s after %d attempt(s)" % (self.ticket_name(), self.max_retries))
        return self.hand_out_review()

    def prompt(self, area=None, to_file=False):
        """The full prompt for the BUILD, REVIEW or PHASE-REVIEW area that `next` handed out. Exit 2 (NoPhase)
        when none is. to_file writes it to the state folder instead and returns `PROMPT <path>`, so the session
        hands the subagent one short line and the guide never passes through its own context."""
        text = self.prompt_text(area)
        if to_file:
            path = self.copy_file.with_name("prompt-%s%s.md" % (self.feature, "-" + area if area else ""))
            state.write_text(path, text)
            text = "PROMPT %s" % proof.repo_relative(path)
        self.charge(2 * len(text.encode("utf-8")))  # the session reads it, then writes it again to the subagent
        self.save()
        return text

    def prompt_text(self, area):
        self.check_owner()
        phase = self.get("phase")
        if phase == "phase-review":
            areas = [a for a in self.get("phase_areas").split(",") if a]
            if area not in areas:
                raise Stop("name the phase review area: prompt <area>, one of %s" % ", ".join(areas))
            try:
                return prompts.phase(self.scripts, self.feature, self.plan.as_posix(), area, areas,
                                     self.phase_base(), self.get("phase_head"))
            except FileNotFoundError as err:
                raise Stop(str(err))
        if phase not in ("build", "review"):
            raise NoPhase("no BUILD or REVIEW is pending for %s" % self.feature)
        if area is not None:
            raise Stop("only a phase review prompt takes an area")
        try:
            if phase == "review" and self.get("review_pass") in ("quality", "single"):
                phase = "review-" + self.get("review_pass")
            return prompts.build(phase, self.scripts, self.feature, self.ticket(), self.get("num"), self.get("base"),
                                 [n for n in self.get("review_notes").split(NOTE_SEP) if n] if phase != "build" else (),
                                 retry=self.num("round") > 0, class_fix=phase == "build" and self.class_finding())
        except FileNotFoundError as err:
            raise Stop(str(err))

    def class_finding(self):
        """True when a review finding in the ticket names a class of defect (`class: <pattern>`)."""
        if self.num("round") == 0:
            return False
        text = Path(self.ticket()).read_text(encoding="utf-8")
        found = re.search(r"^## Review findings", text, re.MULTILINE)
        return bool(found and re.search(r"\bclass:", text[found.start():], re.IGNORECASE))

    def verdict(self, reply, area=None):
        """Record the reviewer's reply (a phase reviewer's under its area). Exit 2 (NoPhase) unless a review
        is pending."""
        self.check_owner()
        phase = self.get("phase")
        if phase not in ("review", "phase-review"):
            raise NoPhase("no review is pending for %s" % self.feature)
        areas = [a for a in self.get("phase_areas").split(",") if a]
        if phase == "phase-review" and area not in areas:
            raise Stop("name the phase review area: verdict <file> <area>, one of %s" % ", ".join(areas))
        if phase == "review" and area is not None:
            raise Stop("only a phase review verdict takes an area")
        try:
            text = Path(reply).read_text(encoding="utf-8", errors="replace")
        except OSError as err:
            raise Stop("cannot read the review reply %s: %s" % (reply, err.strerror))
        found = ""
        for line in text.splitlines():
            match = VERDICT.match(line)
            if match:
                found = match.group(1).lower()
        if phase == "phase-review":
            verdicts = self.phase_verdicts()
            verdicts[area] = found or "none"
            self.st["phase_verdicts"] = ",".join("%s=%s" % item for item in sorted(verdicts.items()))
            if found == "fail":
                before = state.read_text(self.findings_file, "findings") or ""
                body = "\n".join(text.splitlines()[:120])
                state.write_text(self.findings_file, "%s### %s\n\n%s\n\n" % (before, area, body), "findings")
            self.save()
            self.log("VERDICT-%s %s" % ((found or "none").upper(), area))
            return "OK" if found else "RETRY no review verdict"
        if found == "fail":
            state.write_text(self.findings_file, "\n".join(text.splitlines()[:120]) + "\n", "findings")
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
        count = len(tickets.ticket_files(str(self.draft / (os.environ.get("FLOW_TICKETS") or "tasks"))))
        skip = _env_int("FLOW_PLAN_REVIEW_SKIP", 5)
        if 0 < count <= skip:
            self.log("PLAN-REVIEW-SKIP")
            return ("SKIP plan review: the draft has %d ticket(s), and a plan of %d or fewer goes straight to the "
                    "user's approval (FLOW_PLAN_REVIEW_SKIP)" % (count, skip))
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
        check = checks.flow_status(self.scripts, self.feature, "--lint", root=self.draft_root)
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
