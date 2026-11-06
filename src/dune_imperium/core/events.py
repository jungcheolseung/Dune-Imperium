"""Replayable events emitted by game transitions."""

from dataclasses import dataclass

from dune_imperium.core.actions import ActionValue

# An event payload value: an action value, or a list of ids or of seat or
# round numbers (cleanup-2c-7, user decision 2026-10-18: "목록으로 바꾸자.
# 깔끔하게." -- once comma-joined strings). Action arguments keep
# ``ActionValue``.
type EventValue = ActionValue | tuple[str, ...] | tuple[int, ...]


@dataclass(frozen=True, slots=True)
class GameEvent:
    """A structured event with an explicit visibility boundary.

    ``visible_to=None`` means public.  A tuple limits the event to the listed
    players and must never be empty.
    """

    event_id: str
    kind: str
    payload: tuple[tuple[str, EventValue], ...] = ()
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

        for key, value in self.payload:
            if isinstance(value, tuple) and not (
                all(isinstance(item, str) for item in value)
                or all(
                    isinstance(item, int) and not isinstance(item, bool)
                    for item in value
                )
            ):
                raise ValueError(f"event payload list {key!r} mixes its kinds")
        keys = tuple(key for key, _ in self.payload)
        if len(keys) != len(set(keys)):
            raise ValueError("event payload names must be unique")
        if keys != tuple(sorted(keys)):
            raise ValueError("event payload must be sorted by name")
