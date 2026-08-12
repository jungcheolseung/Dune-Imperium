"""Authoritative game state and deterministic state hashing."""

import dataclasses
import hashlib
import json
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from dune_imperium.config import RulesetConfig
from dune_imperium.core.decisions import DecisionFrame
from dune_imperium.core.events import GameEvent


class GamePhase(StrEnum):
    """Top-level Uprising round phases."""

    SETUP = "setup"
    ROUND_START = "round_start"
    PLAYER_TURNS = "player_turns"
    COMBAT = "combat"
    MAKERS = "makers"
    RECALL_OR_ENDGAME = "recall_or_endgame"
    ENDGAME = "endgame"
    FINISHED = "finished"


@dataclass(frozen=True, slots=True)
class GameState:
    """Minimal authoritative state shared by all later rule modules."""

    config: RulesetConfig
    seed: int
    phase: GamePhase = GamePhase.SETUP
    revision: int = 0
    decision_stack: tuple[DecisionFrame, ...] = ()
    event_log: tuple[GameEvent, ...] = ()

    def push_decision(self, frame: DecisionFrame) -> GameState:
        """Return a state with ``frame`` at the top of the stack."""

        return replace(self, decision_stack=(*self.decision_stack, frame))

    def pop_decision(self) -> GameState:
        """Return a state without the current decision frame."""

        if not self.decision_stack:
            raise IndexError("cannot pop an empty decision stack")
        return replace(self, decision_stack=self.decision_stack[:-1])


def canonical_state_hash(state: GameState) -> str:
    """Hash state using a canonical representation independent of object identity."""

    encoded = json.dumps(
        _canonicalize(state),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _canonicalize(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _canonicalize(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_canonicalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if value is None or isinstance(value, bool | int | float | str):
        return value
    message = f"state contains unsupported canonical value: {type(value).__name__}"
    raise TypeError(message)
