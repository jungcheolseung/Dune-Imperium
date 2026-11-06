"""Hidden information with the original cards in an Uprising game (P7e).

docs/rules/imperium-base.md 14 lists who knows what for the original cards
and Leaders: Paul Atreides' Prescience shows his seat its deck's top card,
the Baron's two Factions are his until revealed, Poison Snooper's look is
its player's, and the Intrigue, Imperium and Conflict decks are nobody's
("Uprising과 같다"). With ``imperium_cards`` they share Uprising's decks
(13.4, OQ-155), so every seat's view must still depend on nothing hidden
from it (``simulation.invariants.check_observation_privacy``).
"""

from copy import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation import run_checked_game
from dune_imperium.simulation.invariants import check_observation_privacy

CONFIG = RulesetConfig(imperium_cards=True, promo_cards=True)
LEADERS = (
    "paul_atreides",
    "baron_vladimir_harkonnen",
    "helena_richese",
    "muad_dib",
)


def _opening(seed: int = 4) -> tuple[UprisingRulesEngine, GameState]:
    """Round 1's first turn: Paul at seat 0, the Baron at seat 1 with Emperor
    and Fremen chosen, and every seat holding two cards of the mixed Intrigue
    deck."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, seed)
    chance = ChanceResolver(seed=seed)
    while state.phase is not GamePhase.PLAYER_TURNS:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert decision is not None
        for faction in ("emperor", "fremen"):
            state = engine.apply(
                state,
                DomainAction(
                    "choose_masterstroke_faction", 1, (("faction", faction),)
                ),
            ).state
    deck = state.intrigue_deck
    players = tuple(
        replace(seat, intrigue_cards=deck[2 * index : 2 * index + 2])
        for index, seat in enumerate(state.players)
    )
    return engine, replace(state, players=players, intrigue_deck=deck[8:])


def test_the_mixed_decks_show_no_seat_what_it_may_not_know() -> None:
    engine, state = _opening()
    # Original cards are in the hands and decks being checked.
    original = tuple(
        f"intrigue:{entry.card.card_id}:" for entry in IMPERIUM_INTRIGUE_CARDS
    )
    held = [card for seat in state.players for card in seat.intrigue_cards]
    assert any(card.startswith(original) for card in (*held, *state.intrigue_deck))
    check_observation_privacy(state)
    # Prescience: Paul sees his deck's top card, and no other seat sees it.
    private = engine.observe(state, 0).private
    assert private is not None and private.peeked_card_id == state.players[0].deck[0]
    deck = state.players[0].deck
    paul = replace(state.players[0], deck=(*deck[1:], deck[0]))
    turned = replace(state, players=(paul, *state.players[1:]))
    for seat in range(1, 4):
        assert engine.observe(state, seat) == engine.observe(turned, seat)
    # The Baron's two Factions are his alone (imperium-base.md 14).
    baron = engine.observe(state, 1).private
    assert baron is not None
    assert baron.masterstroke_factions == ("emperor", "fremen")
    other_picks = replace(
        state.players[1], masterstroke_factions=("spacing_guild", "bene_gesserit")
    )
    other = replace(
        state, players=(state.players[0], other_picks, *state.players[2:])
    )
    for seat in (0, 2, 3):
        assert engine.observe(state, seat) == engine.observe(other, seat)


@pytest.mark.parametrize("policy", ["random", "heuristic"])
def test_a_mixed_game_keeps_every_view_private_to_the_end(policy: str) -> None:
    # The sweep's check at every fifth decision of a whole game, with the
    # original Leaders seated and the original promos in the deck.
    report = run_checked_game(
        CONFIG,
        21,
        700_021,
        privacy_interval=5,
        soundness_interval=50,
        policy=policy,
        engine=UprisingRulesEngine(leader_ids=LEADERS),
    )
    assert report.ruleset == "uprising-4p-base+imperium-cards+promo"
