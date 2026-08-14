"""Uprising rule transitions."""

from dune_imperium.rules.endgame import (
    FinalStanding,
    apply_endgame_wild_action,
    begin_endgame_wild_choice,
    can_finish_endgame_automatically,
    final_standings,
    finish_endgame_without_pending_effects,
    legal_endgame_wild_actions,
    unambiguous_endgame_wild_match,
)
from dune_imperium.rules.engine import DEFAULT_LEADER_IDS, UprisingRulesEngine

__all__ = [
    "DEFAULT_LEADER_IDS",
    "FinalStanding",
    "UprisingRulesEngine",
    "apply_endgame_wild_action",
    "begin_endgame_wild_choice",
    "can_finish_endgame_automatically",
    "final_standings",
    "finish_endgame_without_pending_effects",
    "legal_endgame_wild_actions",
    "unambiguous_endgame_wild_match",
]
