"""Rise of Ix's state fields, at their defaults (stage P4a, plan 17.8).

Stage P4a adds the seat and game fields observation v39 reads -- the
dreadnoughts (docs/rules/rise-of-ix.md 6), the Freighter and the Negotiators
(4, 5), Tessia Vernius' Snooper tokens, Ilesa Ecaz's set-aside card and her
turn count (10), and the Intrigue cards a seat knows (13) -- each at an
"absent" default that no game without the ``rise_of_ix`` option leaves. Left
out of the canonical state hash at those defaults, they keep every existing
game's hashes, saves and records; stages P4b, P4c and P4e set them.
"""

import json
from copy import replace
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.core import GameState, PlayerState
from dune_imperium.core.state import _canonicalize, canonical_state_hash
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation.invariants import (
    CardCensus,
    InvariantViolation,
    check_state_invariants,
)

ENGINE = UprisingRulesEngine()
ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM)

# Every Rise of Ix seat field with a value other than its default.
SEAT_VALUES: dict[str, Any] = {
    "dreadnoughts_supply": 1,
    "dreadnoughts_garrison": 1,
    "dreadnoughts_conflict": 0,
    "freighter_space": 2,
    "negotiators": 1,
    "snooper_faction_ids": ("emperor", "fremen"),
    "set_aside_card_id": "",
    "set_aside_returned_turn": True,
    "turns_finished_round": 1,
    "known_intrigue_ids": (),
}
IX_SEAT_FIELDS = frozenset(SEAT_VALUES)


def _original() -> GameState:
    return ENGINE.reset(ORIGINAL, 3)


def _ix() -> GameState:
    """An original game's opening state under the Rise of Ix option (stage
    P4c-5's setup: two dreadnoughts in each supply, the Freighter at the
    bottom)."""

    return ENGINE.reset(replace(ORIGINAL, rise_of_ix=True), 3)


def _seat(state: GameState, seat: int, **changes: Any) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)
    return replace(state, players=tuple(players))


def test_every_field_defaults_to_absent_and_is_left_out_of_the_hash() -> None:
    player = PlayerState(player_id=0)
    for name in IX_SEAT_FIELDS:
        assert name in PlayerState.HASH_OMITTED_AT_DEFAULT, name
    assert (
        player.dreadnoughts_supply,
        player.dreadnoughts_garrison,
        player.dreadnoughts_conflict,
        player.freighter_space,
        player.negotiators,
        player.snooper_faction_ids,
        player.set_aside_card_id,
        player.set_aside_returned_turn,
        player.turns_finished_round,
        player.known_intrigue_ids,
    ) == (0, 0, 0, 0, 0, (), "", False, 0, ())
    assert "dreadnought_control" in GameState.HASH_OMITTED_AT_DEFAULT
    state = _original()
    assert state.dreadnought_control == ()
    canonical = json.dumps(_canonicalize(state))
    for name in (*IX_SEAT_FIELDS, "dreadnought_control"):
        # At its default the field is left out, so every older hash holds.
        assert f'"{name}"' not in canonical, name


@pytest.mark.parametrize("name", sorted(IX_SEAT_FIELDS - {"set_aside_card_id"}))
def test_a_field_off_its_default_moves_the_hash(name: str) -> None:
    state = _ix()
    value = SEAT_VALUES[name]
    if name == "known_intrigue_ids":
        value = state.intrigue_deck[:1]
    if name == "dreadnoughts_conflict":
        value = 1
    changes: dict[str, Any] = {name: value}
    if name in ("dreadnoughts_garrison", "dreadnoughts_conflict"):
        # Setup holds both dreadnoughts in the supply; one moves out of it.
        changes["dreadnoughts_supply"] = 1
    if name == "negotiators":
        changes["troops_supply"] = state.players[1].troops_supply - 1
    moved = _seat(state, 1, **changes)
    assert canonical_state_hash(moved) != canonical_state_hash(state)
    assert f'"{name}"' in json.dumps(_canonicalize(moved))


def test_the_dreadnought_supply_starts_with_two_only_in_rise_of_ix() -> None:
    # Rise of Ix's setup puts two dreadnoughts in each supply [Rise of Ix
    # p. 3] (docs/rules/rise-of-ix.md 3 item 5); the field's default is the
    # absent 0 so that no other game holds any.
    for player in _original().players:
        assert player.dreadnoughts_supply == 0
    for player in ENGINE.reset(RulesetConfig(), 3).players:
        assert player.dreadnoughts_supply == 0
    for player in _ix().players:
        assert player.dreadnoughts_supply == 2


def test_a_seat_holds_two_dreadnoughts_and_three_shipping_spaces() -> None:
    PlayerState(player_id=0, dreadnoughts_supply=1, dreadnoughts_conflict=1)
    with pytest.raises(ValueError, match="only two dreadnoughts"):
        PlayerState(player_id=0, dreadnoughts_supply=2, dreadnoughts_garrison=1)
    with pytest.raises(ValueError, match="must not be negative"):
        PlayerState(player_id=0, dreadnoughts_garrison=-1)
    PlayerState(player_id=0, freighter_space=3)
    with pytest.raises(ValueError, match="third"):
        PlayerState(player_id=0, freighter_space=4)
    with pytest.raises(ValueError, match="must not be negative"):
        PlayerState(player_id=0, turns_finished_round=-1)


def test_negotiators_are_troops_from_the_supply() -> None:
    # "take a troop from your supply and place it ... as a Negotiator"
    # [Rise of Ix p. 4] (docs/rules/rise-of-ix.md 4): one of the 12.
    PlayerState(player_id=0, troops_supply=8, negotiators=1)
    with pytest.raises(ValueError, match="all 12 troops"):
        PlayerState(player_id=0, negotiators=1)


def test_a_seat_records_each_token_and_each_known_card_once() -> None:
    with pytest.raises(ValueError, match="one Snooper token"):
        PlayerState(player_id=0, snooper_faction_ids=("emperor", "emperor"))
    with pytest.raises(ValueError, match="known once"):
        PlayerState(player_id=0, known_intrigue_ids=("i:a:0", "i:a:0"))
    with pytest.raises(ValueError, match="two zones"):
        PlayerState(player_id=0, deck=("a", "b"), set_aside_card_id="a")


def test_dreadnoughts_on_control_spaces_need_rise_of_ix() -> None:
    state = _original()
    with pytest.raises(ValueError, match="require Rise of Ix"):
        replace(state, dreadnought_control=(("carthag", 0, False),))
    ix = _ix()
    placed = replace(
        ix, dreadnought_control=(("carthag", 0, False), ("arrakeen", 2, True))
    )
    assert placed.dreadnought_control[1] == ("arrakeen", 2, True)
    with pytest.raises(ValueError, match="one dreadnought"):
        replace(ix, dreadnought_control=(("carthag", 0, False), ("carthag", 1, True)))
    # The original board's Control spaces: Arrakeen, Carthag, Imperial Basin
    # [DI p. 10] (Spice Refinery is Uprising's).
    with pytest.raises(ValueError, match="controls a Control space"):
        replace(ix, dreadnought_control=(("spice_refinery", 0, False),))
    with pytest.raises(ValueError, match="configured owner"):
        replace(ix, dreadnought_control=(("carthag", 4, False),))


def test_the_sweep_keeps_every_field_absent_outside_rise_of_ix() -> None:
    state = _original()
    census = CardCensus.from_state(state)
    check_state_invariants(state, census)
    for name, value in SEAT_VALUES.items():
        if not value:
            continue
        changes: dict[str, Any] = {name: value}
        if name == "negotiators":
            changes["troops_supply"] = state.players[2].troops_supply - 1
        marked = _seat(state, 2, **changes)
        with pytest.raises(InvariantViolation, match="outside a Rise of Ix game"):
            check_state_invariants(marked, census)
    ix = _ix()
    check_state_invariants(_seat(ix, 2, freighter_space=1), CardCensus.from_state(ix))


def test_the_sweep_counts_a_dreadnought_on_a_control_space_among_the_two() -> None:
    ix = _ix()
    census = CardCensus.from_state(ix)
    two = replace(
        _seat(ix, 0, dreadnoughts_supply=1),
        dreadnought_control=(("carthag", 0, True),),
    )
    check_state_invariants(two, census)
    three = replace(
        _seat(ix, 0, dreadnoughts_supply=2),
        dreadnought_control=(("carthag", 0, True),),
    )
    with pytest.raises(InvariantViolation, match="owns 3 dreadnoughts"):
        check_state_invariants(three, census)
    # Setup gives each seat its two [Rise of Ix p. 3] and none is ever lost.
    one = _seat(ix, 0, dreadnoughts_supply=1)
    with pytest.raises(InvariantViolation, match="owns 1 dreadnoughts"):
        check_state_invariants(one, census)


def test_a_known_intrigue_card_is_in_the_deck_or_another_seats_hand() -> None:
    ix = _ix()
    census = CardCensus.from_state(ix)
    top, bottom = ix.intrigue_deck[0], ix.intrigue_deck[-1]
    check_state_invariants(_seat(ix, 0, known_intrigue_ids=(top, bottom)), census)
    held = ix.players[1].intrigue_cards + ix.intrigue_deck[:1]
    drawn = replace(
        _seat(ix, 1, intrigue_cards=held), intrigue_deck=ix.intrigue_deck[1:]
    )
    check_state_invariants(_seat(drawn, 0, known_intrigue_ids=(top,)), census)
    # Once in the knower's own hand (or a public zone) it leaves the record.
    own = replace(
        _seat(ix, 0, intrigue_cards=ix.players[0].intrigue_cards + (top,)),
        intrigue_deck=ix.intrigue_deck[1:],
    )
    with pytest.raises(InvariantViolation, match="known Intrigue"):
        check_state_invariants(_seat(own, 0, known_intrigue_ids=(top,)), census)


def test_the_set_aside_card_stays_in_the_census() -> None:
    # Ilesa Ecaz's face-down card is one of her cards, out of the hand.
    ix = _ix()
    census = CardCensus.from_state(ix)
    owner = ix.players[0]
    card = owner.deck[0]
    aside = _seat(ix, 0, deck=owner.deck[1:], set_aside_card_id=card)
    check_state_invariants(aside, census)
    gone = _seat(ix, 0, deck=owner.deck[1:])
    with pytest.raises(InvariantViolation, match="missing"):
        check_state_invariants(gone, census)
