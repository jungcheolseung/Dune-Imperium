"""Uprising rule transitions."""

from dune_imperium.rules.endgame import (
    FinalStanding,
    can_finish_endgame_automatically,
    final_standings,
    finish_endgame_without_pending_effects,
)
from dune_imperium.rules.engine import DEFAULT_LEADER_IDS, UprisingRulesEngine

__all__ = [
    "DEFAULT_LEADER_IDS",
    "FinalStanding",
    "UprisingRulesEngine",
    "can_finish_endgame_automatically",
    "final_standings",
    "finish_endgame_without_pending_effects",
]
