"""Uprising with the original game's cards through the play server (stage
P7e of docs/base-game-and-ix-plan.md, 19.4 P7-2).

``imperium_cards`` shuffles the original Imperium and Intrigue cards (all but
Calculated Hire) into Uprising's decks and adds its eight Leaders to the
choices ("COMBINING WITH BASE DUNE: IMPERIUM" [Main p. 18],
docs/rules/imperium-base.md 13.4). The server takes it on a new game, names
it in the summary, and keeps it in a save; a whole game serializes every
snapshot to its end, and the Baron's two Factions reach his own seat only
("Baron의 두 진영은 공개 전까지 그의 것", imperium-base.md 14).
"""

import json
from typing import Any

import pytest

from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.content.registry.imperium import IMPERIUM_CARDS
from dune_imperium.content.registry.intrigue import INTRIGUE_CARDS
from dune_imperium.server.persistence import parse_save_document
from dune_imperium.server.sessions import GameSessionManager, SessionError

_ORIGINAL_CARDS = frozenset(
    entry.card.card_id for entry in (*IMPERIUM_BASE_CARDS, *IMPERIUM_INTRIGUE_CARDS)
) - frozenset(entry.card.card_id for entry in (*IMPERIUM_CARDS, *INTRIGUE_CARDS))


def _card_ids(view: dict[str, Any]) -> set[str]:
    """The card ids a seat's view names in the Imperium Row and its hands
    (instance ids such as ``imperium:<card>:<copy>``)."""

    private = view.get("private") or {}
    shown = (*view["imperium_row"], *private["hand"], *private["intrigue_cards"])
    return {str(instance).split(":")[-2] for instance in shown}


def _play(**options: Any) -> tuple[int, dict[str, Any], set[str]]:
    manager = GameSessionManager()
    summary: dict[str, Any] = manager.create_game(
        ("human", "heuristic", "heuristic", "heuristic"),
        imperium_cards=True,
        **options,
    )
    game_id = str(summary["game_id"])
    steps = 0
    seen: set[str] = set()
    while not summary["finished"] and steps < 2000:
        snapshot: Any = manager.snapshot(game_id, 0)
        json.dumps(snapshot)
        seen |= _card_ids(snapshot["view"])
        if summary["confirmation"] is not None:
            summary = manager.confirm_turn(
                game_id, 0, summary["revision"], undo_count=summary["undo_count"]
            )
        else:
            listed: Any = manager.legal_actions(game_id, 0)
            rows: list[dict[str, Any]] = listed["actions"]
            assert rows
            # A varied row, never a troop withdrawal: it only undoes a
            # deployment (test_imperium_game).
            picks = [
                row for row in rows if row["action_id"] != "withdraw_troops"
            ] or rows
            row = picks[(steps * 7) % len(picks)]
            summary = manager.apply_action(
                game_id,
                0,
                summary["revision"],
                row["index"],
                undo_count=summary["undo_count"],
            )
        steps += 1
    return steps, summary, seen


@pytest.mark.parametrize(
    "options",
    [
        {"game_seed": 31},
        # The human seat drafts its Leader, the original eight among the
        # choices, and the original promos join the deck.
        {"game_seed": 5, "leader_draft": True, "promo_cards": True},
    ],
    ids=["fixed-leaders", "draft-promo"],
)
def test_an_uprising_game_with_the_original_cards_serializes_to_its_end(
    options: dict[str, Any],
) -> None:
    steps, summary, seen = _play(**options)
    assert summary["finished"], (steps, summary["round_number"])
    assert summary["base_game"] == "uprising"
    assert summary["imperium_cards"] is True
    # The original cards were dealt and shown, not only listed.
    assert seen & _ORIGINAL_CARDS, sorted(seen)


def test_the_original_game_refuses_its_own_cards_as_an_option() -> None:
    # rules.setup refuses imperium_cards on the original game, whose cards
    # they are: a SessionError (HTTP 400), never a server error.
    manager = GameSessionManager()
    with pytest.raises(SessionError, match="imperium_cards"):
        manager.create_game(("human",) * 4, base_game="imperium", imperium_cards=True)
    plain = manager.create_game(("human",) * 4, game_seed=3)
    assert plain["imperium_cards"] is False


def test_a_save_keeps_the_original_cards() -> None:
    manager = GameSessionManager()
    summary: Any = manager.create_game(
        ("human",) * 4, imperium_cards=True, promo_cards=True, game_seed=8
    )
    game_id = str(summary["game_id"])
    document: Any = json.loads(json.dumps(manager.save_document(game_id)))
    assert document["ruleset"]["imperium_cards"] is True
    assert parse_save_document(document).replay.ruleset.imperium_cards is True
    restored: Any = manager.restore_game(document)
    assert restored["imperium_cards"] is True
    assert (
        manager.snapshot(str(restored["game_id"]), 0)["view"]
        == manager.snapshot(game_id, 0)["view"]
    )
    # A save written before the option is a game without it.
    legacy = {key: value for key, value in document["ruleset"].items()}
    del legacy["imperium_cards"]
    parsed = parse_save_document({**document, "ruleset": legacy}, check_versions=False)
    assert parsed.replay.ruleset.imperium_cards is False


def _baron_at_seat_zero(factions: tuple[str, str]) -> tuple[GameSessionManager, str]:
    """Seed 2's Leader draft with four human seats: seat 0 drafts Baron
    Harkonnen and picks ``factions`` for Masterstroke before round 1; every
    other seat takes its first row."""

    manager = GameSessionManager()
    summary: Any = manager.create_game(
        ("human",) * 4, imperium_cards=True, leader_draft=True, game_seed=2
    )
    game_id = str(summary["game_id"])
    picks = list(factions)
    for _ in range(40):
        if summary["phase"] == "player_turns" and not picks:
            return manager, game_id
        held = summary["confirmation"]
        if held is not None:
            summary = manager.confirm_turn(
                game_id, held, summary["revision"], undo_count=summary["undo_count"]
            )
            continue
        # The one seat with rows to take.
        rows: list[dict[str, Any]] = []
        for seat in range(4):
            listed: Any = manager.legal_actions(game_id, seat)
            rows = listed["actions"]
            if rows:
                break
        ids = {row["action_id"] for row in rows}
        if seat == 0 and "pick_leader" in ids:
            want: dict[str, Any] = {"leader_id": "baron_vladimir_harkonnen"}
        elif seat == 0 and "choose_masterstroke_faction" in ids:
            want = {"faction": picks.pop(0)}
        else:
            want = rows[0]["arguments"]
        row = next(row for row in rows if (row["arguments"] or {}) == want)
        summary = manager.apply_action(
            game_id,
            seat,
            summary["revision"],
            row["index"],
            undo_count=summary["undo_count"],
        )
    raise AssertionError("the draft did not reach round 1")


def test_the_barons_factions_reach_his_seat_alone() -> None:
    first = _baron_at_seat_zero(("emperor", "fremen"))
    second = _baron_at_seat_zero(("spacing_guild", "bene_gesserit"))
    for seat in range(4):
        one: Any = first[0].snapshot(first[1], seat)
        two: Any = second[0].snapshot(second[1], seat)
        assert one["view"]["players"][0]["leader_id"] == "baron_vladimir_harkonnen"
        assert one["view"]["players"][0]["masterstroke_secret"] is True
        assert one["view"]["players"][0]["masterstroke_revealed_factions"] == []
        # The turn's counts behind his Masterstroke (sandworms left out,
        # stage P7e) stay in the engine: no view or row names them.
        text = json.dumps(one)
        assert "masterstroke_sandworms_turn" not in text
        assert "masterstroke_revealed_turn" not in text
        if seat == 0:
            assert one["view"]["private"]["masterstroke_factions"] == [
                "emperor",
                "fremen",
            ]
            continue
        # Every other seat reads the same whichever two he chose.
        assert one["view"] == two["view"]
        assert one["log"] == two["log"]
        # The seat to act has rows (None for the others), named by game.
        rows = [snapshot["actions"] for snapshot in (one, two)]
        assert [row and {**row, "game_id": None} for row in rows] == [
            rows[0] and {**rows[0], "game_id": None}
        ] * 2
