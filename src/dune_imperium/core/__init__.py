"""Library-independent engine primitives."""

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import (
    IllegalActionError,
    RuleResult,
    RulesEngine,
    Transition,
)
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GamePhase, GameState, canonical_state_hash

__all__ = [
    "ChanceDecision",
    "DecisionFrame",
    "DomainAction",
    "GameEvent",
    "GamePhase",
    "GameState",
    "IllegalActionError",
    "PlayerDecision",
    "PlayerView",
    "RuleResult",
    "RulesEngine",
    "Transition",
    "canonical_state_hash",
]
