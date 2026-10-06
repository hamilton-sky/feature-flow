"""The prompts a session hands to its builder and reviewer, built from the role files and the guides.

The text is runtime neutral: any agent that can read a prompt can follow it.
"""

from pathlib import Path

ROLES = {"build": "ticket-builder.md", "review": "ticket-reviewer.md"}
GUIDES = {"build": "build.md", "review": "review.md"}


def find_dir(scripts, name):
    """guides/ or agents/ beside the scripts folder (a checkout), else .feature-flow/<name> (an install)."""
    for folder in (Path(scripts).parent / name, Path(".feature-flow") / name):
        if folder.is_dir():
            return folder
    return None


def _body(path):
    text = Path(path).read_text(encoding="utf-8")
    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)
        if len(parts) == 2:
            text = parts[1]
    return text.strip("\n")


def build(phase, scripts, feature, ticket, num, sha):
    agents = find_dir(scripts, "agents")
    guides = find_dir(scripts, "guides")
    if agents is None or guides is None:
        raise FileNotFoundError("cannot find agents/ and guides/ beside scripts/ or in .feature-flow/")
    role = _body(agents / ROLES[phase])
    guide = _body(guides / GUIDES[phase])
    for placeholder, value in (("<feature>", feature), ("<NN>", num), ("<ticket>", ticket), ("<sha>", sha),
                               ("<base>", sha), ("<base-commit>", sha), ("<start-commit>", sha)):
        guide = guide.replace(placeholder, value)
    fresh = ("Run `git log` and `git status` yourself before you start: a git snapshot taken when your "
             "session began can be stale.")
    if phase == "build":
        task = ("Your task: build ticket %s of the feature `%s`, in auto mode (`%s auto %s`). The ticket is `%s`. "
                "The work starts at commit `%s`.\n%s\nWhen you are done, reply with what you built and the "
                "commit. Do not review your own work." % (num, feature, feature, num, ticket, sha, fresh))
        intro = "The build guide follows. It is the text the role above calls the next-phase skill; follow it exactly."
    else:
        task = ("Your task: review ticket %s of the feature `%s` (`%s %s %s`). The ticket is `%s`, and the work "
                "started at commit `%s`.\n%s\nDo not edit any file or create a commit. Your final reply must end "
                "with exactly `REVIEW: PASS` or `REVIEW: FAIL`." % (num, feature, feature, num, sha, ticket, sha, fresh))
        intro = "The review guide follows. It is the text the role above calls the review-ticket skill; follow it exactly."
    return "\n\n".join([role, "---", intro, guide, "---", task]) + "\n"
