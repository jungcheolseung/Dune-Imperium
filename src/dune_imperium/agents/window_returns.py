"""A specimen's return in the windows the engine offers it since 2026-11-09,
which the AI seats leave alone.

The engine offers a specimen's return in its owner's Conflict reward window
and in the owner's windows outside its own turn where troops can be
recruited, so a human can return one right before a recruit (OQ-050, user
decisions 2026-11-09; "You may return any of your specimens to your supply
at any time" [Immortality p. 8]; ``immortality.SPECIMEN_RETURN_WINDOWS``).
No AI seat has met it there: a network's logit for it is noise, a search
seat would weigh it on a window's single row, and the heuristic and app_ai
seats answer a window with one row without a draw (a Scouts line's collect
click, ``heuristic_agent``), which an extra row would turn into one. So every
AI seat is given those windows' legal rows without it and keeps the windows
it learnt (inside its own turn none of them offers it).
"""

from typing import Final

from dune_imperium.core.actions import DomainAction
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.immortality import SPECIMEN_RETURN_WINDOWS

RETURN_WINDOWS: Final = frozenset(
    {str(FrameKind.COMBAT_REWARD_ICONS)}
    | {str(kind) for kind in SPECIMEN_RETURN_WINDOWS}
)
_SPECIMEN_RETURN: Final = "return_specimen"


def without_window_specimen_return(
    legal_actions: tuple[DomainAction, ...], decision_kind: str | None
) -> tuple[DomainAction, ...]:
    """Drop a specimen's return from a decision of the windows above
    (``decision_kind``, the pending frame's kind), unless nothing else is
    legal."""

    if decision_kind not in RETURN_WINDOWS:
        return legal_actions
    kept = tuple(
        action for action in legal_actions if action.action_id != _SPECIMEN_RETURN
    )
    return kept or legal_actions
