"""scripts/flow-status.py: reads the plan (feature_flow/plan/status.py) or hands a command its own job.

usage: see feature_flow/plan/status.py
"""

import sys

from feature_flow.plan.status import _Bytes, run


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) > 1 and argv[1] == "--eval":  # the run's record, written by feature_flow/commands/evaluate.py
        from feature_flow.commands import evaluate
        return evaluate.main(argv[:1] + argv[2:])
    if len(argv) > 1 and argv[1] in ("--brainstorm-page", "--page"):  # the brainstorm as a review page, feature_flow/pages/brainstorm_page.py
        from feature_flow.pages import brainstorm_page
        return brainstorm_page.main(argv[:1] + argv[2:])
    if len(argv) > 1 and argv[1] == "--clean":  # the brainstorm's spent files, feature_flow/commands/clean.py
        from feature_flow.commands import clean
        return clean.main(argv[:1] + argv[2:], sys.stdout, sys.stderr)
    if len(argv) > 2 and argv[1] == "--import":  # start the plan from a Spec Kit or OpenSpec task list
        from feature_flow.commands import importer
        return importer.main(argv[2:] + argv[:1])
    if len(argv) > 2 and argv[1] == "--fix":  # a one-ticket plan from the session's diagnosis, guides/fix.md
        from feature_flow.commands import fixer
        return fixer.main(argv[2:] + argv[:1])
    sys.stdout.flush()
    if len(argv) > 1 and argv[0] != "" and argv[1] == "--doctor":  # why a run stopped, feature_flow/commands/doctor.py
        from feature_flow.commands import doctor
        return doctor.main(argv[:1] + argv[2:], _Bytes(sys.stdout.buffer), _Bytes(sys.stderr.buffer))
    return run(argv, _Bytes(sys.stdout.buffer), _Bytes(sys.stderr.buffer))
