"""Immutable actions exchanged with the rules engine."""

from dataclasses import dataclass

from dune_imperium.core.dataclass_copy import slot_initializer

type ActionValue = bool | int | str


@slot_initializer
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

        arguments = self.arguments
        if len(arguments) < 2:
            # Most actions carry one argument or none, which are unique and
            # sorted by themselves; unpacking still refuses a malformed pair.
            for _key, _value in arguments:
                pass
            return
        keys = tuple(key for key, _ in arguments)
        if len(keys) != len(set(keys)):
            raise ValueError("action argument names must be unique")
        if keys != tuple(sorted(keys)):
            raise ValueError("action arguments must be sorted by name")
