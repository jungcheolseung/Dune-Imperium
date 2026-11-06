"""The Imperium Row's redeal event (leaf: core imports only).

Composed-effects cleanup-2c-5: Family Atomics [Immortality p. 12] and
Arrakeen Scouts' Clear the Market remove the Imperium Row and deal a new one
(OQ-051, OQ-083) -- the same effect, so the same event, named after
whatever cleared the Row.
"""

from dune_imperium.core.events import GameEvent


def imperium_row_cleared_event(
    source: str,
    removed: tuple[str, ...],
    dealt: tuple[str, ...],
    *,
    player: int | None = None,
) -> GameEvent:
    """The Imperium Row removed and dealt anew, ``<source>:imperium_row_cleared``
    (the seat that cleared it, when one did)."""

    return GameEvent(
        event_id=f"{source}:imperium_row_cleared",
        kind="imperium_row_cleared",
        payload=(
            ("dealt", tuple(dealt)),
            *((("player", player),) if player is not None else ()),
            ("removed", tuple(removed)),
        ),
    )
