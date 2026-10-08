"""The prompts a session hands to its builder and reviewer, built from the role files and the guides.

The text is runtime neutral: any agent that can read a prompt can follow it.
"""

from pathlib import Path

ROLES = {"build": "ticket-builder.md", "review": "ticket-reviewer.md", "review-quality": "ticket-reviewer.md",
         "plan": "feature-planner.md", "plan-review": "plan-reviewer.md"}
GUIDES = {"build": "build.md", "review": "review.md", "review-quality": "review-quality.md", "plan": "plan.md", "plan-review": "plan-review.md"}


def find_file(scripts, folder, name):
    """folder/name beside the scripts folder (a checkout), else in .feature-flow/ (an install).

    A candidate counts only when it holds the file, so an unrelated guides/ or agents/ folder
    in the user's repo does not hide the installed one.
    """
    for root in (Path(scripts).parent, Path(".feature-flow")):
        path = root / folder / name
        if path.is_file():
            return path
    raise FileNotFoundError("cannot find %s/%s beside scripts/ or in .feature-flow/" % (folder, name))


def _body(path):
    text = Path(path).read_text(encoding="utf-8")
    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)
        if len(parts) == 2:
            text = parts[1]
    return text.strip("\n")


def _runner(text, scripts):
    """Point `python3 scripts/` at the scripts folder that is running, unless it is the repo's own."""
    folder = Path(scripts).absolute()
    if folder == Path.cwd() / "scripts":
        return text
    path = folder.as_posix()
    if " " in path:
        path = '"%s"' % path
    return text.replace("python3 scripts/", "python3 %s/" % path)


def build(phase, scripts, feature, ticket, num, sha, notes=(), retry=False):
    role = _runner(_body(find_file(scripts, "agents", ROLES[phase])), scripts)
    guide = _runner(_body(find_file(scripts, "guides", GUIDES[phase])), scripts)
    for placeholder, value in (("<feature>", feature), ("<NN>", num), ("<ticket>", ticket), ("<sha>", sha),
                               ("<base>", sha), ("<base-commit>", sha), ("<start-commit>", sha)):
        guide = guide.replace(placeholder, value)
    fresh = ("Run `git log` and `git status` yourself before you start: a git snapshot taken when your "
             "session began can be stale.")
    if phase == "build":
        task = ("Your task: build ticket %s of the feature `%s`, in auto mode (`%s auto %s`). The ticket is `%s`. "
                "The work starts at commit `%s`.\n%s\nWhen you are done, reply with what you built and the "
                "commit. Do not review your own work." % (num, feature, feature, num, ticket, sha, fresh))
        intro = "The build guide follows. Follow it exactly."
    else:
        task = ("Your task: review ticket %s of the feature `%s` (`%s %s %s`) (%s pass). The ticket is `%s`, and the "
                "work started at commit `%s`.\n%s\nDo not edit any file or create a commit. Your final reply must end "
                "with exactly `REVIEW: PASS` or `REVIEW: FAIL`."
                % (num, feature, feature, num, sha, "quality" if phase == "review-quality" else "spec", ticket, sha,
                   fresh))
        for note in notes:
            task += "\nThe conductor notes: %s" % note
        intro = "The review guide follows. Follow it exactly."
    parts = [role, "---", intro, guide, "---", task]
    if retry and phase == "build":
        parts += ["The debugging guide follows. Follow it before you change any code.",
                  _body(find_file(scripts, "guides", "debug.md"))]
    return "\n\n".join(parts) + "\n"


def plan(phase, scripts, feature, draft, brief, findings=""):
    """The prompt for the feature-planner (phase "plan") or the plan-reviewer ("plan-review").

    Both get the approved brief and the draft folder, never the conversation or each other's reasoning.
    """
    role = _runner(_body(find_file(scripts, "agents", ROLES[phase])), scripts)
    guide = _runner(_body(find_file(scripts, "guides", GUIDES[phase])), scripts)
    guide = guide.replace("<feature>", feature).replace("<draft>", draft)
    if phase == "plan":
        task = ("Your task: plan the feature `%s` from the approved brief below. Write the draft only inside "
                "`%s`, laid out as the plan guide says. Do not write anywhere else and do not commit. Your final "
                "reply must end with exactly `PLAN: READY` or `PLAN: QUESTIONS`." % (feature, draft))
        intro = "The plan guide follows. Follow it exactly."
    else:
        task = ("Your task: review the draft plan for the feature `%s` in `%s` against the approved brief below. "
                "Do not edit any file or create a commit. Your final reply must end with exactly "
                "`PLAN-REVIEW: PASS` or `PLAN-REVIEW: FAIL`." % (feature, draft))
        intro = "The plan review guide follows. Follow it exactly."
    parts = [role, "---", intro, guide, "---", task, "## The brief", brief.strip("\n")]
    if findings.strip():
        parts += ["## Review findings from the last round", "The draft is already in `%s`. Fix each finding in it, "
                  "or say in your reply why it stays." % draft, findings.strip("\n")]
    return "\n\n".join(parts) + "\n"
