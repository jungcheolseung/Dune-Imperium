"""Rise of Ix's hidden information in the reads (stage P4a, plan 17.8).

docs/rules/rise-of-ix.md 13: Ilesa Ecaz's set-aside card is hers alone, and
the seat that put Intrigue cards on the deck's bottom (Court Intrigue, Sonic
Snoopers) or saw its top (Viscount Hundro Moritani) knows them there and,
once drawn, who holds them. Stage P4a wires the reads -- ``known_card_seats``,
the determinizer and the privacy scramble -- before any rule sets the
fields, so stages P4c and P4e only fill the state: a sampled world keeps what
the observer knows in place and re-deals the rest, and the observer's view
never changes with what it does not know.
"""

import random
from copy import replace

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.determinize import determinize
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    GamePhase,
    GameState,
    PlayerDecision,
)
from dune_imperium.core.observation import known_card_seats, observe_state
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation.invariants import (
    CardCensus,
    _scramble_hidden_information,
    check_observation_privacy,
    check_state_invariants,
)


def _opening() -> GameState:
    """An original game's first turn under the Rise of Ix option, with
    Intrigue cards in two hands (its setup is a later stage's)."""

    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(base_game=BaseGame.IMPERIUM), 5)
    chance = ChanceResolver(seed=5)
    while state.phase is not GamePhase.PLAYER_TURNS:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        action = engine.legal_actions(state, decision.owner)[0]
        state = engine.apply(state, action).state
    deck = state.intrigue_deck
    players = list(state.players)
    players[2] = replace(players[2], intrigue_cards=deck[:2])
    players[3] = replace(players[3], intrigue_cards=deck[2:4])
    return replace(
        state,
        config=replace(state.config, rise_of_ix=True),
        players=tuple(players),
        intrigue_deck=deck[4:],
    )


def _knowing(state: GameState) -> GameState:
    """Seat 0 knows the deck's top card, its two bottom cards and one card
    seat 2 holds; seat 1 knows the card above them; seat 3 has a card set
    aside."""

    deck = state.intrigue_deck
    players = list(state.players)
    players[0] = replace(
        players[0],
        known_intrigue_ids=(deck[0], deck[-1], deck[-2], players[2].intrigue_cards[0]),
    )
    players[1] = replace(players[1], known_intrigue_ids=(deck[-3],))
    three = players[3]
    players[3] = replace(three, hand=three.hand[1:], set_aside_card_id=three.hand[0])
    return replace(state, players=tuple(players))


def test_the_set_aside_card_is_its_owners_and_known_cards_their_knowers() -> None:
    state = _knowing(_opening())
    known = known_card_seats(state)
    deck = state.intrigue_deck
    assert known[state.players[3].set_aside_card_id] == frozenset({3})
    assert known[deck[0]] == known[deck[-1]] == known[deck[-2]] == frozenset({0})
    assert known[deck[-3]] == frozenset({1})
    assert known[deck[5]] == frozenset()
    held = state.players[2].intrigue_cards
    assert known[held[0]] == frozenset({0, 2})
    assert known[held[1]] == frozenset({2})
    view = observe_state(state, 3)
    assert view.private is not None and view.private.set_aside_card_id
    for seat in range(3):
        private = observe_state(state, seat).private
        assert private is not None and not private.set_aside_card_id
        assert observe_state(state, seat).players[3].has_set_aside_card


def test_a_sampled_world_keeps_what_the_observer_knows_in_place() -> None:
    state = _knowing(_opening())
    check_state_invariants(state, CardCensus.from_state(state))
    deck = state.intrigue_deck
    held = state.players[2].intrigue_cards[0]
    view = observe_state(state, 0)
    moved_deck = moved_aside = False
    for seed in range(12):
        world = determinize(state, 0, random.Random(seed))
        sampled = world.intrigue_deck
        assert (sampled[0], sampled[-2], sampled[-1]) == (deck[0], deck[-2], deck[-1])
        assert held in world.players[2].intrigue_cards
        assert observe_state(world, 0) == view
        # Seat 1 knows the card in its place, whichever card the sample put
        # there; the world stays one the sweep accepts.
        assert world.players[1].known_intrigue_ids == (sampled[-3],)
        check_state_invariants(world, CardCensus.from_state(state))
        three, real = world.players[3], state.players[3]
        assert sorted((*three.hand, *three.deck, three.set_aside_card_id)) == sorted(
            (*real.hand, *real.deck, real.set_aside_card_id)
        )
        moved_deck = moved_deck or sampled[1:-3] != deck[1:-3]
        moved_aside = moved_aside or three.set_aside_card_id != real.set_aside_card_id
    assert moved_deck and moved_aside
    # Its own set-aside card is what the owner put there.
    for seed in range(4):
        world = determinize(state, 3, random.Random(seed))
        assert world.players[3].set_aside_card_id == state.players[3].set_aside_card_id
        assert observe_state(world, 3) == observe_state(state, 3)


def test_no_view_depends_on_what_its_seat_does_not_know() -> None:
    state = _knowing(_opening())
    check_observation_privacy(state)
    scrambled = _scramble_hidden_information(state, 0)
    deck, held = state.intrigue_deck, state.players[2].intrigue_cards[0]
    assert scrambled.intrigue_deck[0] == deck[0]
    assert scrambled.intrigue_deck[-2:] == deck[-2:]
    assert scrambled.intrigue_deck[1:-3] != deck[1:-3]
    assert held in scrambled.players[2].intrigue_cards
    # Seat 3's face-down card trades places with its hidden hand and deck.
    assert (
        scrambled.players[3].set_aside_card_id != state.players[3].set_aside_card_id
    )
    assert observe_state(scrambled, 0) == observe_state(state, 0)
