"""Declared differences of stage P4a's Rise of Ix state fields and
observation v39 (docs/base-game-and-ix-plan.md 17.8) against ``7b4c65be``
(codec v156, observation v38).

Only new fields at their "absent" values, which no game without the
``rise_of_ix`` option leaves (``simulation.invariants``):

- ``PlayerState`` gains the dreadnoughts in the supply, garrison and
  Conflict, the Freighter's space, the Negotiators, Tessia Vernius' Snooper
  tokens, Ilesa Ecaz's set-aside card, its return this turn, the turns
  finished this round and the Intrigue cards the seat knows; ``GameState``
  gains the dreadnoughts on Control spaces. All are left out of the canonical
  state hash at their defaults (saves and records keep their hashes), but the
  tool digests the state field by field, so they are declared added.
- Every seat's ``PublicPlayerView`` gains the public ones (the set-aside card
  as a flag), each ``PrivatePlayerView`` the observer's own set-aside card,
  known Intrigue places and open Rise of Ix decision, and the ``PlayerView``
  the Rise of Ix flag and the dreadnoughts on Control spaces. The views gain
  them at their defaults.

Nothing else a player, an agent or a save sees changes: the legal rows, the
pages, the events and their payloads stay as they were (the observation's
old columns too, ``tests/adapters/test_observation_encoding.py``). Checked
with ``engine_equivalence.py check --differences
scripts/ab/differences/rise_of_ix_v39.py``.
"""

from typing import Any

from equivalence_rules import Rule, Step

# The fields the views gain, at their values in a game without Rise of Ix.
_SEAT_FIELDS: tuple[tuple[str, Any], ...] = (
    ("dreadnoughts_supply", 0),
    ("dreadnoughts_garrison", 0),
    ("dreadnoughts_conflict", 0),
    ("freighter_space", 0),
    ("negotiators", 0),
    ("snooper_faction_ids", []),
    ("has_set_aside_card", False),
    ("set_aside_returned_turn", False),
    ("turns_finished_round", 0),
)
_PRIVATE_FIELDS: tuple[tuple[str, Any], ...] = (
    ("set_aside_card_id", ""),
    ("known_intrigue_top", ""),
    ("known_intrigue_bottom", []),
    ("known_intrigue_held", []),
    (
        "ix_pending",
        {
            "shipping_rewards": [],
            "tech_discount": 0,
            "tech_payment": "",
            "negotiators_returnable": 0,
        },
    ),
)
_VIEW_FIELDS: tuple[tuple[str, Any], ...] = (
    ("rise_of_ix", False),
    ("dreadnought_control", []),
)


def _fresh(value: Any) -> Any:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return {key: _fresh(item) for key, item in value.items()}
    return value


def _add(target: dict[str, Any], fields: tuple[tuple[str, Any], ...]) -> bool:
    added = False
    for name, default in fields:
        if name not in target:
            target[name] = _fresh(default)
            added = True
    return added


def _add_new_fields(step: Step) -> bool:
    """Show the base's views the new fields at their defaults; whether any
    view was missing one."""

    shown = False
    for view in step.views:
        shown |= _add(view, _VIEW_FIELDS)
        if isinstance(view.get("private"), dict):
            shown |= _add(view["private"], _PRIVATE_FIELDS)
        for seat in view["players"]:
            shown |= _add(seat, _SEAT_FIELDS)
    return shown


VIEWS_SHOW_RISE_OF_IX = Rule(
    name="views_show_rise_of_ix",
    why="plan 17.8: observation v39 reads Rise of Ix's fields from the views",
    old=_add_new_fields,
)

STATE_HOLDS_RISE_OF_IX = Rule(
    name="state_holds_rise_of_ix",
    why="plan 17.8: stage P4a adds Rise of Ix's state fields at their defaults",
    state_fields=frozenset(
        {
            "PlayerState.dreadnoughts_supply",
            "PlayerState.dreadnoughts_garrison",
            "PlayerState.dreadnoughts_conflict",
            "PlayerState.freighter_space",
            "PlayerState.negotiators",
            "PlayerState.snooper_faction_ids",
            "PlayerState.set_aside_card_id",
            "PlayerState.set_aside_returned_turn",
            "PlayerState.turns_finished_round",
            "PlayerState.known_intrigue_ids",
            "GameState.dreadnought_control",
        }
    ),
)

RULES = (STATE_HOLDS_RISE_OF_IX, VIEWS_SHOW_RISE_OF_IX)
