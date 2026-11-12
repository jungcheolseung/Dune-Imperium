"""Placing an Agent through the server's two posts (stage B1, OQ-111).

An Agent turn is a card pick (``choose_agent_card``) and then a space pick
(``place_agent``). A server test that used to post one ``agent_turn`` row now
posts two: the card pick's row, then the picked card's space row. The legal
actions payload names each placement the old way in its display-only
``agent_placements`` key (``index`` is the card pick's row, ``arguments`` the
placement's card, graft choice, space, cost option, discount and infiltration
post), so a test finds a placement by those arguments as before.

Import with the same ``sys.path`` line ``ko_text`` uses (tests/support is
not a package pytest or mypy resolve from a dotted import)::

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))
    from server_placement import place_agent  # type: ignore[import-not-found]
"""

from collections.abc import Callable
from typing import Any

from dune_imperium.server.sessions import GameSessionManager, JsonObject

type Arguments = dict[str, Any]

# The placement arguments the card pick holds; the space pick has the rest.
_CARD_PICK_ARGUMENTS = ("card_id", "graft")


def _int(value: object) -> int:
    assert isinstance(value, int) and not isinstance(value, bool)
    return value


def _rows(value: object) -> list[dict[str, Any]]:
    assert isinstance(value, list)
    rows: list[dict[str, Any]] = []
    for item in value:
        assert isinstance(item, dict)
        rows.append(item)
    return rows


def placements_of(payload: JsonObject) -> list[dict[str, Any]]:
    """The payload's placements, each ``{"index", "arguments"}``; empty when
    the decision holds no card pick."""

    entries = payload["agent_placements"]
    return [] if entries is None else _rows(entries)


def find_placement(
    payload: JsonObject, matches: Callable[[Arguments], bool]
) -> dict[str, Any] | None:
    """The first placement whose arguments satisfy ``matches``, or None."""

    for entry in placements_of(payload):
        if matches(entry["arguments"]):
            return dict(entry)
    return None


def space_arguments(arguments: Arguments) -> Arguments:
    """A placement's arguments without the card pick's."""

    return {
        key: value
        for key, value in arguments.items()
        if key not in _CARD_PICK_ARGUMENTS
    }


def pick_card(
    manager: GameSessionManager,
    game_id: str,
    seat: int,
    matches: Callable[[Arguments], bool],
) -> tuple[dict[str, Any], JsonObject]:
    """Post the card pick of the first placement ``matches`` accepts; return
    that placement and the summary."""

    payload = manager.legal_actions(game_id, seat)
    entry = find_placement(payload, matches)
    assert entry is not None, "no Agent placement satisfies the predicate"
    summary = manager.apply_action(
        game_id,
        seat=seat,
        revision=_int(payload["revision"]),
        index=_int(entry["index"]),
    )
    return entry, summary


def place_space(
    manager: GameSessionManager,
    game_id: str,
    seat: int,
    placement: dict[str, Any],
) -> JsonObject:
    """Post the space pick that completes ``placement`` (its card is picked
    already); return the summary."""

    payload = manager.legal_actions(game_id, seat)
    wanted = space_arguments(placement["arguments"])
    row = next(
        row
        for row in _rows(payload["actions"])
        if row["action_id"] == "place_agent" and row["arguments"] == wanted
    )
    return manager.apply_action(
        game_id,
        seat=seat,
        revision=_int(payload["revision"]),
        index=_int(row["index"]),
    )


def place_agent(
    manager: GameSessionManager,
    game_id: str,
    seat: int,
    matches: Callable[[Arguments], bool],
) -> JsonObject:
    """Place an Agent as the page does: post the card pick, then the space
    pick, of the first placement ``matches`` accepts; return the summary."""

    placement, _ = pick_card(manager, game_id, seat, matches)
    return place_space(manager, game_id, seat, placement)
