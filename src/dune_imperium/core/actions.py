"""Immutable actions exchanged with the rules engine."""

from dataclasses import dataclass

type ActionValue = bool | int | str


@dataclass(frozen=True, slots=True)
class DomainAction:
    """A stable action ID plus small, serializable values."""

    action_id: str
    actor: int
    arguments: tuple[tuple[str, ActionValue], ...] = ()

    def __post_init__(self) -> None:
        if not self.action_id:
            raise ValueError("action_id must not be empty")
        if self.actor < 0:
            raise ValueError("actor must not be negative")

        keys = tuple(key for key, _ in self.arguments)
        if len(keys) != len(set(keys)):
            raise ValueError("action argument names must be unique")
        if keys != tuple(sorted(keys)):
            raise ValueError("action arguments must be sorted by name")
