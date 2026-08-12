"""Replayable events emitted by game transitions."""

from dataclasses import dataclass

from dune_imperium.core.actions import ActionValue


@dataclass(frozen=True, slots=True)
class GameEvent:
    """A structured event with an explicit visibility boundary.

    ``visible_to=None`` means public.  A tuple limits the event to the listed
    players and must never be empty.
    """

    event_id: str
    kind: str
    payload: tuple[tuple[str, ActionValue], ...] = ()
    visible_to: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id must not be empty")
        if not self.kind:
            raise ValueError("event kind must not be empty")
        if self.visible_to == ():
            raise ValueError("visible_to must be None or contain at least one player")
        if self.visible_to is not None and len(self.visible_to) != len(
            set(self.visible_to)
        ):
            raise ValueError("visible_to players must be unique")

        keys = tuple(key for key, _ in self.payload)
        if len(keys) != len(set(keys)):
            raise ValueError("event payload names must be unique")
        if keys != tuple(sorted(keys)):
            raise ValueError("event payload must be sorted by name")
