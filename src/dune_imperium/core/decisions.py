"""Serializable decision points and nested decision frames."""

from dataclasses import dataclass

from dune_imperium.core.actions import ActionValue


@dataclass(frozen=True, slots=True)
class PlayerDecision:
    """A decision that must be answered by one player."""

    owner: int
    prompt: str

    def __post_init__(self) -> None:
        if self.owner < 0:
            raise ValueError("decision owner must not be negative")
        if not self.prompt:
            raise ValueError("decision prompt must not be empty")


@dataclass(frozen=True, slots=True)
class ChanceDecision:
    """A decision resolved by the engine's chance stream."""

    prompt: str

    def __post_init__(self) -> None:
        if not self.prompt:
            raise ValueError("decision prompt must not be empty")


type Decision = PlayerDecision | ChanceDecision


@dataclass(frozen=True, slots=True)
class DecisionFrame:
    """One resumable frame in a nested decision stack."""

    frame_id: str
    decision: Decision
    context: tuple[tuple[str, ActionValue], ...] = ()

    def __post_init__(self) -> None:
        if not self.frame_id:
            raise ValueError("frame_id must not be empty")

        keys = tuple(key for key, _ in self.context)
        if len(keys) != len(set(keys)):
            raise ValueError("decision context names must be unique")
        if keys != tuple(sorted(keys)):
            raise ValueError("decision context must be sorted by name")
