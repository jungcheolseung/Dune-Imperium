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
    """A uniform sample resolved by a chance stream.

    Options are stable instance IDs rather than hidden Python object references.
    An ordered sample without replacement also represents a shuffle.
    """

    decision_id: str
    prompt: str
    options: tuple[str, ...]
    count: int = 1
    with_replacement: bool = False

    def __post_init__(self) -> None:
        if not self.decision_id:
            raise ValueError("chance decision_id must not be empty")
        if not self.prompt:
            raise ValueError("decision prompt must not be empty")
        if not self.options:
            raise ValueError("chance decision options must not be empty")
        if len(self.options) != len(set(self.options)):
            raise ValueError("chance decision options must be unique")
        if self.count < 1:
            raise ValueError("chance decision count must be positive")
        if not self.with_replacement and self.count > len(self.options):
            raise ValueError("chance decision count exceeds available options")


type Decision = PlayerDecision | ChanceDecision


@dataclass(frozen=True, slots=True)
class DecisionFrame:
    """One resumable frame in a nested decision stack.

    ``kind`` names the rule boundary that owns the frame so dispatch never has
    to parse ``frame_id``. ``frame_id`` stays a unique, human-readable label.
    """

    kind: str
    frame_id: str
    decision: Decision
    context: tuple[tuple[str, ActionValue], ...] = ()

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("frame kind must not be empty")
        if not self.frame_id:
            raise ValueError("frame_id must not be empty")

        keys = tuple(key for key, _ in self.context)
        if len(keys) != len(set(keys)):
            raise ValueError("decision context names must be unique")
        if keys != tuple(sorted(keys)):
            raise ValueError("decision context must be sorted by name")
