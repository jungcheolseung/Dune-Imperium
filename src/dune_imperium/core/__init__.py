"""Library-independent engine primitives."""

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import (
    ChanceOutcome,
    ChanceReplayError,
    ChanceResolver,
)
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import (
    IllegalActionError,
    RuleResult,
    RulesEngine,
    Transition,
)
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import (
    PlayerView,
    PrivatePlayerView,
    PublicPlayerView,
    observe_state,
)
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.replay import (
    GameReplay,
    ReplayMismatchError,
    replay_game,
)
from dune_imperium.core.state import GamePhase, GameState, canonical_state_hash

__all__ = [
    "ChanceDecision",
    "ChanceOutcome",
    "ChanceReplayError",
    "ChanceResolver",
    "DecisionFrame",
    "DomainAction",
    "GameEvent",
    "GamePhase",
    "GameReplay",
    "GameState",
    "IllegalActionError",
    "Influence",
    "PlayerDecision",
    "PlayerState",
    "PlayerView",
    "PrivatePlayerView",
    "PublicPlayerView",
    "RuleResult",
    "RulesEngine",
    "Resources",
    "ReplayMismatchError",
    "Transition",
    "canonical_state_hash",
    "observe_state",
    "replay_game",
]
