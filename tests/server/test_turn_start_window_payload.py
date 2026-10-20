"""The ``turn_start`` tag on a seat's own turn-start rows (display only).

"At the start of your turn: Put this card into play -> Draw a card and pass
your turn." [Litany Against Fear card]; "At the start of your turn: Pass
your turn." [Withdrawn card]: either is only the turn's first action
(OQ-095 (6), user ruling 2026-10-04), and the engine offers it among the
turn's usual actions until the seat acts otherwise. The page asks for such
a play first and alone, in a window of the seat's own page that sends
nothing when it is put aside (static/turn.js, user decision 2026-10-14);
the server only marks the rows it is about (``sessions._serialize_action``).
The engine, the codec and the legal list are untouched: these tests check
that the mark sits on exactly those rows of the owner's own payload, and
that no other seat's snapshot changes with the card in the owner's hand.

The state is injected the way tests/server/test_turn_end.py
``_turn_pass_game`` does; the cards are only a vehicle here (their rules are
tests/unit/rules/test_bloodlines_cards.py and test_twisted_intrigue.py).
"""

import json
from collections.abc import Mapping
from typing import Final

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.server.sessions import GameSessionManager

TWO_HUMANS: Final = (
    "human",
    "human",
    "heuristic_uprising_table",
    "heuristic_uprising_table",
)
_STARTERS: Final = starting_deck_instance_ids(0)
_DAGGER: Final = next(card for card in _STARTERS if ":dagger:" in card)
_LITANY: Final = "imperium:litany_against_fear:0"
_WITHDRAWN: Final = "intrigue:twisted_withdrawn:0"
_PLOT: Final = "intrigue:contingency_plan:0"


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _game(owner: PlayerState) -> tuple[GameSessionManager, str]:
    """Seat 0's fresh turn (no step taken yet), human seat 1 next."""

    state = GameState(
        config=RulesetConfig(bloodlines=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:3],
        players=(
            owner,
            PlayerState(
                player_id=1, hand=(_DAGGER.replace("player:0:", "player:1:"),)
            ),
            PlayerState(player_id=2, has_revealed=True),
            PlayerState(player_id=3, has_revealed=True),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    manager = GameSessionManager()
    summary = manager.create_game(TWO_HUMANS, game_seed=0, bloodlines=True)
    game_id = str(summary["game_id"])
    manager._get(game_id).state = state
    return manager, game_id


def _owner(
    *,
    hand: tuple[str, ...],
    intrigue: tuple[str, ...],
    deck: tuple[str, ...] = _STARTERS[4:8],  # not the Dagger a hand may hold
) -> PlayerState:
    return PlayerState(
        player_id=0,
        leader_id="piter_de_vries",
        hand=hand,
        deck=deck,
        intrigue_cards=intrigue,
    )


def _tagged(rows: list[dict[str, object]]) -> list[tuple[str, str]]:
    return [
        (str(row["action_id"]), str(_obj(row["arguments"])["card_id"]))
        for row in rows
        if "turn_start" in row
    ]


def test_only_the_owners_turn_start_plays_carry_the_tag() -> None:
    manager, game_id = _game(
        _owner(hand=(_LITANY, _DAGGER), intrigue=(_WITHDRAWN, _PLOT))
    )
    rows = _rows(manager.legal_actions(game_id, 0)["actions"])

    assert sorted(_tagged(rows)) == [
        ("play_intrigue", _WITHDRAWN),
        ("play_turn_start_card", _LITANY),
    ]
    assert all(row["turn_start"] is True for row in rows if "turn_start" in row)
    # Every other row of the turn goes untagged: the Agent turns (their card
    # picks, stage B1), the Reveal and the ordinary Plot.
    others = {str(row["action_id"]) for row in rows if "turn_start" not in row}
    assert {"choose_agent_card", "reveal_turn", "play_intrigue"} <= others
    assert all(
        _obj(row["arguments"]).get("card_id") != _WITHDRAWN
        for row in rows
        if "turn_start" not in row and row["action_id"] == "play_intrigue"
    )
    # The snapshot serves the same rows.
    snapshot = manager.snapshot(game_id, 0)
    assert _tagged(_rows(_obj(snapshot["actions"])["actions"])) == _tagged(rows)


def test_no_row_is_tagged_once_the_seat_acted() -> None:
    # A Plot is the seat's first other action: the start of the turn is
    # over and neither play is offered (OQ-095 (6)), so nothing is tagged.
    manager, game_id = _game(_owner(hand=(_LITANY,), intrigue=(_WITHDRAWN, _PLOT)))
    rows = _rows(manager.legal_actions(game_id, 0)["actions"])
    plot = next(
        row
        for row in rows
        if row["action_id"] == "play_intrigue"
        and _obj(row["arguments"])["card_id"] == _PLOT
    )
    summary = manager.apply_action(game_id, 0, 0, _int(plot["index"]))
    decision = _obj(summary["decision"])
    assert decision["kind"] == "turn" and decision["owner"] == 0

    after = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert after and _tagged(after) == []
    assert "play_turn_start_card" not in {row["action_id"] for row in after}


def test_a_seat_without_such_a_card_has_no_tagged_row() -> None:
    manager, game_id = _game(_owner(hand=(_DAGGER,), intrigue=(_PLOT,)))
    rows = _rows(manager.legal_actions(game_id, 0)["actions"])
    assert rows and _tagged(rows) == []


def _public(snapshot: Mapping[str, object], game_id: str) -> str:
    """The snapshot without what differs between two games by itself: the
    game's id and the play clock's readings."""

    copy = dict(snapshot)
    copy.pop("clock_age_ms", None)
    summary = dict(_obj(copy["summary"]))
    summary.pop("clock", None)
    copy["summary"] = summary
    return json.dumps(copy, sort_keys=True).replace(game_id, "<game>")


def test_another_seat_sees_the_same_table_with_or_without_the_card() -> None:
    # The window is the owner's page alone: seat 1's snapshot holds no
    # actions, no tag and no trace of the card, the same whether seat 0
    # holds Litany Against Fear and Withdrawn or an ordinary card and Plot.
    # The two seats own the same cards (a deck's contents are public), the
    # Litany in the deck instead of the hand.
    rest = _STARTERS[4:7]
    holding, holding_id = _game(
        _owner(hand=(_LITANY,), intrigue=(_WITHDRAWN,), deck=(_DAGGER, *rest))
    )
    plain, plain_id = _game(
        _owner(hand=(_DAGGER,), intrigue=(_PLOT,), deck=(_LITANY, *rest))
    )
    assert _tagged(_rows(holding.legal_actions(holding_id, 0)["actions"]))

    seen = holding.snapshot(holding_id, 1)
    assert seen["actions"] is None
    assert "turn_start" not in json.dumps(seen["log"])
    assert _public(seen, holding_id) == _public(plain.snapshot(plain_id, 1), plain_id)
    # A browser without a seat (the lobby, a spectator) gets the summary
    # only, and the same one.
    assert _public(holding.snapshot(holding_id), holding_id) == _public(
        plain.snapshot(plain_id), plain_id
    )
