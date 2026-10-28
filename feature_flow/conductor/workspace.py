"""The Workspace a phase works in: the main worktree, lane k, or the integration worktree that `integrate`
merges in. It holds the folder, the state view (the run's keys plain, a lane's keys as `L<k>.<key>`), the lane
number (0 outside lanes) and the repo top, and the per-ticket steps that read them. Phases, schedulers, guards
and build checks read the state, the lane and the lane word from the Workspace they are handed.

The Conductor is the main worktree's Workspace: one ticket at a time, the run-wide phases and the facade's own
commands work on it. A lane's or the integration worktree's Workspace is its own object over the Conductor:
what it does not hold itself (the settings, the paths, the scheduler, the whole run state) comes from there.
"""

import contextlib
import os
from pathlib import Path

from feature_flow import codehash, floorguard, git, proof, scouts, state, tickets
from feature_flow.conductor import budget as time_budget
from feature_flow.conductor.errors import NoPhase, Stop
from feature_flow.conductor.phases import REGISTRY, Phase
from feature_flow.conductor.phases.build import Build
from feature_flow.conductor.policy import levels, limits
from feature_flow.conductor.policy.levels import CONVERT
from feature_flow.conductor.policy.review import FINDING
from feature_flow.conductor.store import NOTE_SEP, TicketState

MAIN, LANE, INTEGRATION = "main", "lane", "integration"


class Workspace:
    def __init__(self, c, kind=MAIN, lane=0, folder=None):
        self.c = c
        self.kind = kind
        self.lane = lane  # 0 outside lanes
        self.top = c.top  # the main worktree's top
        self.folder = Path(folder) if folder is not None else None  # None: the working folder, never changed
        self.st = TicketState(c.all, lane)  # the run's keys plain, a lane's as L<k>.<key>
        # where prompts look for an install's .feature-flow/: as before, the working folder in the main worktree,
        # the main worktree's top elsewhere, so the guides and roles are never a lane's copies
        self.prompts_top = "." if kind == MAIN else str(c.top)

    def __getattr__(self, name):
        """What a lane's or the integration Workspace does not hold itself comes from the Conductor."""
        c = self.__dict__.get("c")
        if c is None or c is self:
            raise AttributeError(name)
        return getattr(c, name)

    @contextlib.contextmanager
    def entered(self):
        """Work in this Workspace's folder, and come back to the top of the repo. Until the helpers take cwd=,
        this is the one place the conductor changes the working folder."""
        if self.folder is None:
            yield self
            return
        os.chdir(str(self.folder))
        try:
            yield self
        finally:
            os.chdir(str(self.top))

    # ---- the state view ------------------------------------------------

    def get(self, key, default=""):
        return self.st.get(key, default)

    def num(self, key):
        return self.st.num(key)

    def save(self):
        self.all.save()

    def log(self, event):
        state.log(self.log_file, self.get("num"), event)

    def emit(self, line):
        self.log(line.split(" ", 1)[0])
        return line

    def ticket(self):
        return self.get("ticket")

    def ticket_name(self):
        return tickets.name(self.ticket())

    def lane_word(self):
        return " %d" % self.lane if self.lane else ""

    def scout_slot(self):
        return "L%d" % self.lane if self.lane else ""

    def count_run(self):
        runs = self.num("runs") + 1
        limit = self.num("limit")
        if runs > limit:
            raise Stop("run limit of %d phases reached, stopping" % limit)
        self.st["runs"] = runs

    # ---- the pending phase ---------------------------------------------

    def pending(self):
        """The class of the phase pending in this view of the state: Phase, whose defaults do nothing, for none."""
        return REGISTRY.get(self.get("phase"), Phase)

    def prompt_text(self):
        phase = self.pending()
        if not phase.lane_scoped:
            raise NoPhase("no BUILD or REVIEW is pending for %s" % self.feature)
        return phase.prompt(self)

    def phase_key(self):
        """Names the phase handed out last, so scout replies saved for one phase never reach another."""
        return self.pending().key(self)

    def scout_questions(self):
        """[(agent, role, question)] for the phase handed out last: a build's first attempt above level 1 (or with
        no level), a level 3 ticket's first review, and the first round of the feature review."""
        return self.pending().scout_questions(self)

    def scout_findings(self):
        """The scout replies saved for the phase handed out last, as a section for its prompt, or ""."""
        if self.get("scout_key") != self.phase_key():
            return ""
        return scouts.section(self.state_file.parent, self.feature, self.scout_slot(), self.num("scout_n"))

    # ---- the ticket's outcome ------------------------------------------

    def round_cap(self):
        """The send-back rounds this ticket may have: 1 at level 1, else FLOW_MAX_REVIEW_ROUNDS."""
        return limits.round_cap(self.num("level"), self.max_rounds)

    def send_back(self, source, findings):
        """Write the findings into the ticket, reopen it, commit, and build again."""
        round_no = self.num("round") + 1
        cap = self.round_cap()
        if round_no > cap:
            level = self.num("level")
            raise Stop("%s still fails the %s after %d round(s)%s" % (
                self.ticket_name(), source, cap,
                " at level %d. the user decides what happens next" % level if level else ""))
        self.st["round"] = round_no
        self.st["due_minors"] = ""  # the next round's reviews list them again if they are still there
        tickets.append_findings(self.ticket(), round_no, source, findings)
        tickets.set_open(self.ticket())
        if not git.commit_file(self.ticket(), "chore(%s): %s review findings, round %d"
                               % (self.feature, self.get("num"), round_no)):
            raise Stop("cannot commit the %s findings to %s. this session must be allowed to run git commit"
                       % (source, self.ticket_name()))
        self.st["attempt"] = 0
        self.st["review_attempt"] = 0
        self.st["review_pass"] = "spec"
        return Build.hand_out(self)

    def add_due(self, key, items):
        """Remember follow-ups for when the ticket passes: tab separated in the state, one per item."""
        items = [" ".join(item.split()) for item in items if item.strip()]
        self.st[key] = NOTE_SEP.join([n for n in self.get(key).split(NOTE_SEP) if n] + items)

    def write_due(self, title):
        """Write the follow-ups remembered for this ticket (or the feature review) and forget them."""
        items = [n for key in ("due_checks", "due_minors") for n in self.get(key).split(NOTE_SEP) if n]
        self.st["due_checks"] = self.st["due_minors"] = ""
        if items:
            self.write_followups(title, items, "chore(%s): %s follow-ups" % (self.feature, self.get("num")))
            self.log("FOLLOWUPS %d" % len(items))

    def pass_ticket(self):
        self.write_due("%s (left for later)" % self.ticket_name())
        time_budget.note_slowest(self)
        return self.scheduler().on_passed(self)

    def pass_with_followups(self, source, findings):
        """A level 2 ticket past its full rounds whose review found no blocker: append the findings to the
        plan's followups.md, commit it, and pass the ticket."""
        found = [line.strip() for line in findings.splitlines() if FINDING.match(line)]
        self.write_followups("%s (round %d, %s)" % (self.ticket_name(), self.num("round") + 1, source), found,
                             "chore(%s): %s follow-ups from the %s" % (self.feature, self.get("num"), source))
        self.st["followups"] = self.num("followups") + 1
        self.log("PASS-FOLLOWUPS")
        return self.pass_ticket()

    def defer_review(self):
        """Fast mode: the ticket passed the gate, the floor guard and its checks, so it passes now and the
        feature review at the end covers it."""
        items = [i for i in self.all.get("deferred", "").split() if not i.startswith(self.get("num") + ":")]
        self.all["deferred"] = " ".join(items + ["%s:%s" % (self.get("num"), self.get("base"))])
        self.log("REVIEW-DEFERRED")
        return self.pass_ticket()

    # ---- the code snapshot, the level and the ticket at base -------------

    def snapshot_code(self):
        whole, each = codehash.flow_code(self.scripts)
        self.st["code_sha"] = whole
        self.st["code_files"] = codehash.dump(each)

    def check_code(self, allowed=False, final=False):
        """The Conductor's check_code on this Workspace's state, looked up on its class at each call."""
        return type(self.c).check_code(self, allowed, final)

    def flow_edit_allowed(self):
        try:
            source = git._git("show", "%s:%s" % (self.get("base"), Path(self.ticket()).as_posix()), check=False)
        except OSError:
            return False
        if source.returncode != 0:
            return False
        return "flow-edit" in floorguard.allow_line(source.stdout).split()

    def base_level(self):
        """The level known before the build, from the ticket at base: its `Level:` line, raised to 3 by
        `Review: full`, `Type: convert` or `Floor: allow flow-edit`. 0 when none of these is there."""
        level, why = levels.declared(self.ticket_at_base(), self.flow_edit_allowed())
        self.st["level_note"] = levels.describe(level, why) if level else ""
        return level

    def commands_at_base(self):
        """commands.md as it was at the base commit, or "" when it was not there."""
        rel = proof.repo_relative(self.commands)
        try:
            return git.show_text("%s:%s" % (self.get("base"), rel))
        except RuntimeError:
            return ""

    def measure_level(self):
        """Raise the ticket's level from the built diff, never lower it: a path on commands.md's
        `Sensitive:` line makes it 3, and a level 1 diff over the small limits makes it 2."""
        level = self.num("level")
        hit = []
        patterns = tickets.sensitive_patterns(self.commands_at_base())
        if patterns and level < 3:
            hit = [p for p in git.diff_names(self.get("base"), "HEAD", self.plan.as_posix())
                   if tickets.matches_sensitive(p, patterns)]
        files, lines, binary = 0, 0, False
        if level == 1 and not hit:  # the size only matters to a level 1 diff that no Sensitive path raised
            files, lines, binary = git.diff_size(self.get("base"), "HEAD", self.plan.as_posix())
        level, why = levels.measured(level, hit, files, lines, binary, self.small_files, self.small_lines)
        if why:
            self.st["level_note"] = levels.describe(level, why)
        self.st["level"] = level
        if level:
            self.log("LEVEL-%d" % level)
        return level

    def small_note(self):
        """The note for the reviewer when the built diff is small enough for one review, else ""."""
        base = self.ticket_at_base()
        if proof.review_mode(base) != "auto" or self.small_lines <= 0:
            return ""
        if CONVERT.search(base.split("\n## ", 1)[0]):
            return ""
        files, lines, binary = git.diff_size(self.get("base"), "HEAD", self.plan.as_posix())
        if binary or files > self.small_files or lines > self.small_lines:
            return ""
        return ("the conductor judged this ticket small (%d files, %d lines): one review covers the spec and "
                "quality passes" % (files, lines))

    def ticket_at_base(self):
        """The ticket text as it was at the base commit, so a builder cannot change what is checked."""
        rel = proof.repo_relative(self.ticket())
        listed = git._git("ls-tree", "--name-only", self.get("base"), "--", rel, check=False)
        if listed.returncode != 0:
            raise Stop("cannot read %s at the base commit: %s" % (rel, listed.stderr.strip()))
        if listed.stdout.strip():
            return git.show_text("%s:%s" % (self.get("base"), rel))
        text = Path(self.ticket()).read_text(encoding="utf-8")
        return text.split("\n## Answer", 1)[0]

    # ---- a read only agent that changed files ----------------------------

    def undo_edit(self, sha, who, rule):
        """A read only agent changed tracked files. A commit stops the run; an edit is saved as a patch in the
        state folder and put back, and the note for the next attempt comes back ("" when nothing changed)."""
        if git.head() != sha:
            raise Stop("the %s changed tracked files, which %s must never do. a commit landed after it was handed "
                       "out (`git log --oneline %s..HEAD`), so the conductor cannot undo it. if the session made that "
                       "commit (never commit between a %s and its next), take it out with `git reset --soft %s` and "
                       "`git stash`, run next, and commit it again once the run is done"
                       % (who, rule, sha[:12], "question" if rule == "a consultant" else "review", sha[:12]))
        if git.tracked_clean():
            return ""
        patch = self.state_file.parent / ("edit-%s-%s%s.patch" % (self.feature, self.get("num") or "plan",
                                                                    "-L%d" % self.lane if self.lane else ""))
        try:
            names = git.undo_tracked(patch)
        except (OSError, RuntimeError) as err:
            raise Stop("the %s changed tracked files, which %s must never do, and the conductor could not put them "
                       "back: %s" % (who, rule, err))
        self.log("EDIT-UNDONE")
        shown = ", ".join(names[:5]) + (" and %d more" % (len(names) - 5) if len(names) > 5 else "")
        return ("the last %s changed %s, which %s must never do. the conductor put the files back and threw its "
                "answer away (its changes are in %s). change no file: report what you would change instead"
                % (who, shown, rule, patch.as_posix()))

    def edit_retry(self, note, attempts, what):
        """After undo_edit put a read only agent's edit back: the note for the next attempt, or a stop."""
        if attempts >= self.max_retries:
            raise Stop("%s after %d attempt(s): %s" % (what, attempts, note.split(". the conductor", 1)[0]
                       + ". the conductor put the files back"))
        self.st["verdict"] = ""
        self.st["edit_note"] = note
