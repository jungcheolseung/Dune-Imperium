"""The one resource-gain event, and its mirror for payments (leaf: core
imports only).

Composed-effects cleanup-2c, rule decision 3 (user decision 2026-10-17,
docs/composed-effects-plan.md 5 "정한 규칙 판단" 3): a resource gain leaves the
same kind of event wherever it comes from -- an acquisition box, a research
bonus, a Reveal gain or choice, an Intrigue or Arrakeen Scouts line -- naming
its source, its seat and what it gained. Decision 4: Victory Points a line
gains ride on the same event as the key ``victory_points`` (VP is a payload
key of the event of the thing that scored, as on ``combat_reward_gained`` or
``tleilaxu_advanced``).

The id is ``<source>:resources`` and the payload holds ``player``, ``source``
(the same source string, which the play screen reads as the card or space
behind the gain) and only the keys gained, never a zero.
"""

from typing import Final

from dune_imperium.core.events import GameEvent

RESOURCES_GAINED: Final = "resources_gained"


def resources_gained_event(
    source: str,
    player: int,
    *,
    solari: int = 0,
    spice: int = 0,
    water: int = 0,
    victory_points: int = 0,
) -> GameEvent:
    """The event of ``player`` gaining the given amounts from ``source``."""

    gained = {
        "solari": solari,
        "spice": spice,
        "victory_points": victory_points,
        "water": water,
    }
    if any(amount < 0 for amount in gained.values()):
        raise ValueError("a gain cannot be negative")
    if not any(gained.values()):
        raise ValueError("a gain event must gain something")
    return GameEvent(
        event_id=f"{source}:resources",
        kind="resources_gained",
        payload=tuple(
            sorted(
                (
                    ("player", player),
                    ("source", source),
                    *((key, amount) for key, amount in gained.items() if amount),
                )
            )
        ),
    )


def resources_paid_event(
    source: str,
    player: int,
    *,
    solari: int = 0,
    spice: int = 0,
    water: int = 0,
    specimens: int = 0,
) -> GameEvent:
    """The event of ``player`` paying the given amounts for ``source``
    (cleanup-2c-6, the mirror of ``resources_gained_event``): id
    ``<source>:paid``, payload ``player``, ``source`` and only the keys
    paid, never a zero."""

    paid = {"solari": solari, "specimens": specimens, "spice": spice, "water": water}
    if any(amount < 0 for amount in paid.values()):
        raise ValueError("a payment cannot be negative")
    if not any(paid.values()):
        raise ValueError("a payment event must pay something")
    return GameEvent(
        event_id=f"{source}:paid",
        kind="resources_paid",
        payload=tuple(
            sorted(
                (
                    ("player", player),
                    ("source", source),
                    *((key, amount) for key, amount in paid.items() if amount),
                )
            )
        ),
    )
