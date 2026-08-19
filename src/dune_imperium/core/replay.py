"""Action-and-chance replay records for deterministic verification."""

from dataclasses import dataclass

from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.engine import RulesEngine
from dune_imperium.core.state import GameState, canonical_state_hash

type ReplayStep = DomainAction | ChanceOutcome


class ReplayMismatchError(ValueError):
    """Raised when a replay does not reproduce its expected state."""


@dataclass(frozen=True, slots=True)
class GameReplay:
    """Minimal versioned record needed to reproduce an engine run."""

    ruleset: RulesetConfig
    seed: int
    steps: tuple[ReplayStep, ...]
    expected_state_hash: str
    ruleset_version: str = "uprising-r0"
    content_version: str = "uprising-content-v0"
    action_codec_version: int = 14

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("replay seed must not be negative")
        if not self.expected_state_hash:
            raise ValueError("expected_state_hash must not be empty")
        if not self.ruleset_version:
            raise ValueError("ruleset_version must not be empty")
        if not self.content_version:
            raise ValueError("content_version must not be empty")
        if self.action_codec_version < 1:
            raise ValueError("action_codec_version must be positive")


def replay_game(engine: RulesEngine, replay: GameReplay) -> GameState:
    """Apply every recorded input and verify the final canonical state."""

    state = engine.reset(replay.ruleset, replay.seed)
    for step in replay.steps:
        state = engine.apply(state, step).state

    actual_hash = canonical_state_hash(state)
    if actual_hash != replay.expected_state_hash:
        message = (
            "replay final state hash differs: "
            f"expected {replay.expected_state_hash}, got {actual_hash}"
        )
        raise ReplayMismatchError(message)
    return state
