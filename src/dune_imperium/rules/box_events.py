"""The Agent box's own event (leaf: core imports only).

Composed-effects cleanup-2c-2 (docs/composed-effects-plan.md 5, "정리-2c 사건
문법", 2c-2): an Agent box -- or one icon of a box resolved icon by icon, or
one line of a box whose lines are judged apart -- that ends leaves exactly
one event saying how it ended, after everything else the ending action did
for it. Its id is ``<box>:<outcome>`` (``<box>:<icon>:<outcome>`` for an icon
or a line), its kind ``agent_card_effect_<outcome>``, its payload the card and
the seat (and the icon or line as ``effect``), nothing else: what the box
gained, trashed or paid has events of its own.

``BoxNeedsRows`` is what resolving a box as one action raises when the box
resolves only through its own rows (a payment, a discard, a choice still
being made); the dry run that asks whether a waiting box could only fizzle
(``agent_effects.agent_card_effect_is_unavailable``) reads it as "it can be
resolved".
"""

from enum import StrEnum

from dune_imperium.core.events import GameEvent


class BoxOutcome(StrEnum):
    """How an Agent box (or one of its icons or lines) ended."""

    # Its effect was used, if only in part.
    RESOLVED = "resolved"
    # The owner refused it with a refusal row.
    DECLINED = "declined"
    # A printed condition or target was missing: nothing happened (a
    # mandatory box fizzling at the turn's end, OQ-057 (1)).
    UNAVAILABLE = "unavailable"
    # An optional box left unused when the turn ended (OQ-095 (2)).
    LAPSED = "lapsed"
    # Its card left play before the box was used (OQ-022).
    EXPIRED = "expired"


class BoxNeedsRows(Exception):
    """The box resolves only through its own rows, not as one action."""


def agent_box_event(
    box: str,
    card_id: str,
    player: int,
    outcome: BoxOutcome,
    *,
    effect: str | None = None,
) -> GameEvent:
    """The event of ``box`` (``effects.agent_card_source``) ending as
    ``outcome``; ``effect`` names the icon or line that ended."""

    match outcome:
        case BoxOutcome.RESOLVED:
            kind = "agent_card_effect_resolved"
        case BoxOutcome.DECLINED:
            kind = "agent_card_effect_declined"
        case BoxOutcome.UNAVAILABLE:
            kind = "agent_card_effect_unavailable"
        case BoxOutcome.LAPSED:
            kind = "agent_card_effect_lapsed"
        case BoxOutcome.EXPIRED:
            kind = "agent_card_effect_expired"
    unit = box if effect is None else f"{box}:{effect}"
    return GameEvent(
        event_id=f"{unit}:{outcome.value}",
        kind=kind,
        payload=(
            ("card_id", card_id),
            *((("effect", effect),) if effect is not None else ()),
            ("player", player),
        ),
    )
