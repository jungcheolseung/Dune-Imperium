"""``determinize`` with no observer: a world a spectator cannot tell apart.

The win odds (``evaluation.win_odds``) read every seat's value from such
worlds and show the numbers to the whole table, so a world's seat views must
depend on public information alone. The reference for what is hidden is the
observation-leak sweep's scrambler (``_scramble_hidden_information``): it
moves everything one seat cannot see while keeping that seat's view. Two
states that differ only by such a scramble must give the same world's views
for every seat, and a world must keep every seat's public view.
"""

import random
from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.determinize import determinize
from dune_imperium.agents.registry import make_agent
from dune_imperium.content.registry.intrigue import is_twisted_intrigue
from dune_imperium.core.observation import (
    PlayerView,
    observe_state,
    revealed_contract_ids,
)
from dune_imperium.core.state import GameState
from dune_imperium.evaluation.win_odds import opens_round, private_choice_open
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation.invariants import _scramble_hidden_information
from dune_imperium.simulation.runner import run_policy_game

# Every Uprising option the win odds show, with Leaders whose secrets the
# seat path does not re-deal: Steersman Y'rkoon's Navigation slots and Kota
# Odax's Secret Project tile; Piter De Vries' Twisted Intrigue as well.
CONFIG = RulesetConfig(
    choam_module=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
)
LEADERS = ("steersman_y_rkoon", "kota_odax_of_ix", "piter_de_vries", "lady_jessica")


def _sample(seed: int) -> list[GameState]:
    """The round openings and every 40th state of one heuristic game."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    kept: list[GameState] = []
    reached = [0]
    count = [0]

    rare = {"bids": 0, "known": 0, "public_top": 0}

    def hook(state: GameState) -> None:
        count[0] += 1
        if opens_round(state, reached[0]):
            reached[0] = state.round_number
            kept.append(state)
        elif count[0] % 40 == 0:
            kept.append(state)
        # States the 40th-state sample all but misses (review 2026-11-08):
        # a sealed Scouts auction, a known Intrigue card (OQ-149), a card
        # put face up on a deck (OQ-145).
        elif state.scouts_bids and rare["bids"] < 6:
            rare["bids"] += 1
            kept.append(state)
        elif any(p.known_intrigue_ids for p in state.players) and rare["known"] < 6:
            rare["known"] += 1
            kept.append(state)
        elif any(p.deck_public_top for p in state.players) and rare["public_top"] < 3:
            rare["public_top"] += 1
            kept.append(state)

    agents = [make_agent("heuristic", seed * 4 + seat, CONFIG) for seat in range(4)]
    run_policy_game(engine, CONFIG, seed, agents, on_state=hook)
    return kept


@cache
def _states() -> tuple[GameState, ...]:
    return (*_sample(51), *_sample(52))


def _views(state: GameState, seed: int) -> tuple[PlayerView, ...]:
    world = determinize(state, None, random.Random(seed))
    return tuple(observe_state(world, seat) for seat in range(4))


def _public(view: PlayerView) -> PlayerView:
    return replace(view, private=None)


def test_the_games_reach_the_secrets_the_seat_path_keeps() -> None:
    states = _states()
    assert any(state.players[0].navigation_slots for state in states)
    assert any(state.players[1].secret_project_tech_id for state in states)
    assert any(state.players[2].twisted_deck for state in states)
    assert sum(1 for state in states if state.scouts_bids) >= 3
    assert sum(1 for s in states if any(p.known_intrigue_ids for p in s.players)) >= 3
    assert any(any(p.deck_public_top for p in s.players) for s in states)


@pytest.mark.parametrize("observer", range(4))
def test_a_spectator_world_ignores_what_a_seat_alone_knows(observer: int) -> None:
    # The scramble keeps ``observer``'s view and moves everything else no
    # seat but its owner sees: the other seats' hands, Intrigue cards,
    # Navigation slots, sealed picks and bids, and every hidden deck. It
    # leaves another seat's known Intrigue cards (OQ-149) naming the old
    # cards; a spectator world forgets them, so those states count too.
    checked = 0
    for state in _states():
        twin = _scramble_hidden_information(state, observer)
        for seed in (0, 1):
            assert _views(twin, seed) == _views(state, seed)
        checked += 1
    assert checked > 20


def test_a_spectator_world_ignores_which_card_a_seat_knows() -> None:
    # Imperium Ceremony (OQ-149): a seat that put a card back on top of the
    # Intrigue deck knows it, also once another seat draws it. The table
    # knows that much; which card it is, it does not. A twin swaps the known
    # card with a face-down deck card and moves the knowledge with it.
    checked = 0
    for state in _states():
        knower = next((p for p in state.players if p.known_intrigue_ids), None)
        if knower is None:
            continue
        known = knower.known_intrigue_ids[0]
        unknown = [c for c in state.intrigue_deck if c not in knower.known_intrigue_ids]
        if not unknown:
            continue
        other = unknown[0]

        def swap(
            cards: tuple[str, ...], a: str = known, b: str = other
        ) -> tuple[str, ...]:
            return tuple(b if card == a else a if card == b else card for card in cards)

        twin = replace(
            state,
            intrigue_deck=swap(state.intrigue_deck),
            players=tuple(
                replace(
                    player,
                    intrigue_cards=swap(player.intrigue_cards),
                    known_intrigue_ids=swap(player.known_intrigue_ids),
                )
                for player in state.players
            ),
        )
        for seed in (0, 1):
            assert _views(twin, seed) == _views(state, seed)
        checked += 1
    assert checked


def test_a_spectator_world_ignores_where_a_known_card_lies() -> None:
    # Codex review 2026-11-08: the worlds carried a known card to the card
    # dealt to its place in the real hand's order, which is hidden too. A
    # twin reverses every seat's held Intrigue cards and the deck.
    checked = 0
    for state in _states():
        if not any(p.known_intrigue_ids for p in state.players):
            continue
        twin = replace(
            state,
            intrigue_deck=tuple(reversed(state.intrigue_deck)),
            players=tuple(
                replace(player, intrigue_cards=tuple(reversed(player.intrigue_cards)))
                for player in state.players
            ),
        )
        for seed in (0, 1):
            assert _views(twin, seed) == _views(state, seed)
            world = determinize(state, None, random.Random(seed))
            assert not any(p.known_intrigue_ids for p in world.players)
        checked += 1
    assert checked


def test_a_spectator_world_ignores_which_twisted_cards_were_drawn() -> None:
    # Codex review 2026-11-08: Piter De Vries' Twisted deck is face down
    # [Piter De Vries card]; only its size is public. A twin swaps a held
    # Twisted card with one still in that deck.
    checked = 0
    for state in _states():
        piter = state.players[2]
        # A Twisted card being played is public: "보유한 Intrigue card는 …
        # opponent에게는 play할 때만 공개한다. [Main p. 7]" (docs/rules/
        # information-visibility.md), so it is no hidden card to swap (the
        # seeded walk first met one when Spice Agony's rewards became steps
        # of their own, audit F-2, 2026-11-09).
        playing = {
            dict(frame.context).get("card_id")
            for frame in state.decision_stack
            if frame.kind == "intrigue_choice"
        }
        held = [
            card
            for card in piter.intrigue_cards
            if is_twisted_intrigue(card) and card not in playing
        ]
        if not held or not piter.twisted_deck:
            continue
        a, b = held[0], piter.twisted_deck[0]
        players = list(state.players)
        players[2] = replace(
            piter,
            intrigue_cards=tuple(b if c == a else c for c in piter.intrigue_cards),
            twisted_deck=(a, *piter.twisted_deck[1:]),
        )
        twin = replace(state, players=tuple(players))
        assert _public(observe_state(twin, 0)) == _public(observe_state(state, 0))
        for seed in (0, 1):
            assert _views(twin, seed) == _views(state, seed)
        checked += 1
    assert checked


def test_a_spectator_world_ignores_the_order_of_the_boxed_conflicts() -> None:
    # Codex review 2026-11-08: the tiers were shuffled in the order they were
    # met, which follows the boxed cards once the deck holds one tier only;
    # a different shuffle size then moved every later draw.
    checked = 0
    for state in _states():
        if len(state.unused_conflict_ids) < 2:
            continue
        twin = replace(
            state, unused_conflict_ids=tuple(reversed(state.unused_conflict_ids))
        )
        for seed in (0, 1):
            assert _views(twin, seed) == _views(state, seed)
        checked += 1
    assert checked > 10


def _reverse_hidden_orders(state: GameState) -> GameState:
    """``state`` with every order no seat's view shows reversed: hands'
    face-down draws, decks below their public top cards, held Intrigue,
    the Twisted decks, the Navigation slots and boxes, and every face-down
    shared deck, stock and box. The cards stay where they are."""

    players = []
    for player in state.players:
        secret = [c for c in player.hand if c not in player.hand_public]
        top = len(player.deck_public_top)
        players.append(
            replace(
                player,
                hand=(*player.hand_public, *reversed(secret)),
                deck=(*player.deck[:top], *reversed(player.deck[top:])),
                intrigue_cards=tuple(reversed(player.intrigue_cards)),
                twisted_deck=tuple(reversed(player.twisted_deck)),
                navigation_slots=tuple(reversed(player.navigation_slots)),
                navigation_box=tuple(reversed(player.navigation_box)),
            )
        )
    shown = len(revealed_contract_ids(state))
    return replace(
        state,
        players=tuple(players),
        intrigue_deck=tuple(reversed(state.intrigue_deck)),
        imperium_deck=tuple(reversed(state.imperium_deck)),
        contract_bank=(
            *state.contract_bank[:shown],
            *reversed(state.contract_bank[shown:]),
        ),
        contract_box=tuple(reversed(state.contract_box)),
        unused_conflict_ids=tuple(reversed(state.unused_conflict_ids)),
        tech_stacks=tuple((*s[:1], *reversed(s[1:])) for s in state.tech_stacks),
        navigation_stock=tuple(reversed(state.navigation_stock)),
        twisted_deck_stock=tuple(reversed(state.twisted_deck_stock)),
        tleilaxu_deck=tuple(reversed(state.tleilaxu_deck)),
        skill_stack=tuple(reversed(state.skill_stack)),
    )


def test_a_spectator_world_ignores_every_hidden_order() -> None:
    # Codex reviews 2026-11-08 found two dependences on a hidden order (a
    # known card's place in a hand, the boxed Conflicts' order); this twin
    # reverses every order no view shows at once. A state whose open frame
    # names a card by place is left out: no win odds are read there.
    checked = 0
    for state in _states():
        if private_choice_open(state):
            continue
        twin = _reverse_hidden_orders(state)
        assert observe_state(twin, 0).players == observe_state(state, 0).players
        for seed in (0, 1, 2):
            assert _views(twin, seed) == _views(state, seed)
        checked += 1
    assert checked > 20


def test_a_spectator_world_ignores_which_tile_the_secret_project_is() -> None:
    # The sweep's scramble leaves Kota Odax's Secret Project in place; swap
    # it with a face-down tile below a stack's top by hand.
    checked = 0
    for state in _states():
        kota = state.players[1]
        stack = next((s for s in state.tech_stacks if len(s) > 1), None)
        if not kota.secret_project_tech_id or stack is None:
            continue
        hidden = stack[-1]
        stacks = tuple(
            (*s[:-1], kota.secret_project_tech_id) if s is stack else s
            for s in state.tech_stacks
        )
        players = list(state.players)
        players[1] = replace(kota, secret_project_tech_id=hidden)
        twin = replace(state, players=tuple(players), tech_stacks=stacks)
        assert observe_state(twin, 0) == observe_state(state, 0)
        assert _views(twin, 3) == _views(state, 3)
        checked += 1
    assert checked


def test_a_spectator_world_keeps_every_public_view() -> None:
    for state in _states():
        for seed in (0, 1):
            world_views = _views(state, seed)
            for seat in range(4):
                assert _public(world_views[seat]) == _public(observe_state(state, seat))


def test_a_spectator_world_deals_the_secrets_again() -> None:
    # Over a few worlds each secret takes other values than the real one.
    moved = {"hand": False, "navigation": False, "secret_project": False}
    for state in _states():
        for seed in range(4):
            world = determinize(state, None, random.Random(seed))
            for real, dealt in zip(state.players, world.players, strict=True):
                moved["hand"] |= sorted(real.hand) != sorted(dealt.hand)
                moved["navigation"] |= real.navigation_slots != dealt.navigation_slots
                moved["secret_project"] |= (
                    real.secret_project_tech_id != dealt.secret_project_tech_id
                )
    assert all(moved.values()), moved


def test_a_seat_number_out_of_range_is_still_refused() -> None:
    with pytest.raises(ValueError, match="observer"):
        determinize(_states()[0], 4, random.Random(0))
