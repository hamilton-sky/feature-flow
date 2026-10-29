"""How much rework a ticket gets. Pure: values in, values out."""

from __future__ import annotations


def round_cap(level, max_rounds):
    """The send-back rounds a ticket of this level may have: 1 at level 1, else max_rounds."""
    return min(1, max_rounds) if level == 1 else max_rounds
