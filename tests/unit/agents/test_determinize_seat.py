"""``determinize`` for one seat: a world that seat cannot tell apart.

The search and rollout seats play out from such worlds, so a world must
depend only on what the observing seat knows. Twins of a state that differ
only in what the observer cannot see must give the same world for the same
random numbers: the observation-leak sweep's scrambler
(``_scramble_hidden_information``) moves everything one seat cannot see while
keeping that seat's view, and hand-made swaps move what it leaves alone
(which Navigation cards Steersman Y'rkoon slotted, which tile Kota Odax's
Secret Project is, which Twisted cards Piter De Vries drew, which stack a
face-down Tech tile is in). Before 2026-11-08 the seat path kept those real
and kept the orders of the Tleilaxu deck, the Skill stack and the Twisted
decks, so the playouts knew them.
"""

import random
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from functools import cache

import pytest
from tests.unit.agents.test_determinize_public import CONFIG, LEADERS, _states

from dune_imperium.agents.determinize import determinize
from dune_imperium.agents.registry import make_agent
from dune_imperium.content.registry.intrigue import is_twisted_intrigue
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.observation import observe_state
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.simulation.invariants import _scramble_hidden_information
from dune_imperium.simulation.runner import run_policy_game

# The seats of the sampled games (``test_determinize_public.LEADERS``).
YRKOON, KOTA, PITER = 0, 1, 2


def _context_ids(frame: DecisionFrame, key: str) -> tuple[str, ...]:
    value = dict(frame.context)[key]
    assert isinstance(value, str)
    return tuple(value.split(","))


def _owner(decision: object) -> int:
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _world(state: GameState, observer: int, seed: int) -> GameState:
    return determinize(state, observer, random.Random(seed))


def _same_worlds(twin: GameState, state: GameState, observer: int) -> None:
    # The twin is one the observer cannot tell apart, and it gets the very
    # same worlds.
    assert observe_state(twin, observer) == observe_state(state, observer)
    for seed in (0, 1):
        assert _world(twin, observer, seed) == _world(state, observer, seed)


def _others_know_intrigue(state: GameState, observer: int) -> bool:
    return any(
        player.known_intrigue_ids
        for seat, player in enumerate(state.players)
        if seat != observer
    )


@cache
def _draft_states() -> tuple[GameState, ...]:
    """States of a Leader draft, while the Twisted and Navigation decks
    wait in their stocks."""

    config = replace(CONFIG, leader_draft=True)
    kept: list[GameState] = []

    def hook(state: GameState) -> None:
        if state.twisted_deck_stock and state.navigation_stock and len(kept) < 8:
            kept.append(state)

    agents = [make_agent("heuristic", 40 + seat, config) for seat in range(4)]
    run_policy_game(UprisingRulesEngine(), config, 53, agents, on_state=hook)
    return tuple(kept)


def test_the_samples_reach_every_zone_the_twins_move() -> None:
    states = _states()
    assert any(s.players[YRKOON].navigation_slots for s in states)
    assert any(s.players[KOTA].secret_project_tech_id for s in states)
    assert any(
        s.players[PITER].twisted_deck
        and any(is_twisted_intrigue(c) for c in s.players[PITER].intrigue_cards)
        for s in states
    )
    assert any(len(s.tleilaxu_deck) > 1 for s in states)
    assert any(len(s.skill_stack) > 1 for s in states)
    assert any(sum(len(t) > 2 for t in s.tech_stacks) > 1 for s in states)
    assert sum(1 for s in states if _others_know_intrigue(s, 0)) >= 3
    assert _draft_states()


@pytest.mark.parametrize("observer", range(4))
def test_a_seat_world_ignores_what_the_seat_cannot_see(observer: int) -> None:
    # The scramble reverses every hidden order (decks, hands, Intrigue, the
    # Tleilaxu deck, the Skill stack, the Twisted decks, the Tech stacks below
    # their tops, the Navigation boxes and another seat's slots) and moves
    # the other seats' secret picks, bids and Rise of Ix tiles. It leaves
    # another seat's known Intrigue cards (OQ-149) naming the old cards, whose
    # places the table follows: such states have their own twins below.
    checked = 0
    for state in (*_states(), *_draft_states()):
        if _others_know_intrigue(state, observer):
            continue
        _same_worlds(_scramble_hidden_information(state, observer), state, observer)
        checked += 1
    assert checked > 50


def _swap(a: str, b: str) -> Callable[[tuple[str, ...]], tuple[str, ...]]:
    def swapped(cards: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(b if card == a else a if card == b else card for card in cards)

    return swapped


@pytest.mark.parametrize("observer", [seat for seat in range(4) if seat != YRKOON])
def test_a_seat_world_ignores_which_navigation_cards_another_seat_slotted(
    observer: int,
) -> None:
    # Only Steersman Y'rkoon may look at his face-down slots [Bloodlines p.
    # 12]; a twin trades a slotted card with one in his box.
    checked = 0
    for state in _states():
        yrkoon = state.players[YRKOON]
        if not yrkoon.navigation_slots or not yrkoon.navigation_box:
            continue
        swap = _swap(yrkoon.navigation_slots[0], yrkoon.navigation_box[0])
        players = list(state.players)
        players[YRKOON] = replace(
            yrkoon,
            navigation_slots=swap(yrkoon.navigation_slots),
            navigation_box=swap(yrkoon.navigation_box),
        )
        _same_worlds(replace(state, players=tuple(players)), state, observer)
        checked += 1
    assert checked > 10


@pytest.mark.parametrize("observer", [seat for seat in range(4) if seat != KOTA])
def test_a_seat_world_ignores_which_tile_another_seats_secret_project_is(
    observer: int,
) -> None:
    # Kota Odax's Secret Project lies face down on his Leader card [Kota Odax
    # of Ix card]; a twin trades it with a tile below a stack's top.
    checked = 0
    for state in _states():
        kota = state.players[KOTA]
        index = next(
            (i for i, stack in enumerate(state.tech_stacks) if len(stack) > 1), None
        )
        if not kota.secret_project_tech_id or index is None:
            continue
        stack = state.tech_stacks[index]
        stacks = list(state.tech_stacks)
        stacks[index] = (*stack[:-1], kota.secret_project_tech_id)
        players = list(state.players)
        players[KOTA] = replace(kota, secret_project_tech_id=stack[-1])
        twin = replace(state, players=tuple(players), tech_stacks=tuple(stacks))
        _same_worlds(twin, state, observer)
        checked += 1
    assert checked > 10


@pytest.mark.parametrize("observer", [seat for seat in range(4) if seat != PITER])
def test_a_seat_world_ignores_which_twisted_cards_another_seat_drew(
    observer: int,
) -> None:
    # Piter De Vries' Twisted deck is face down and only its size is public
    # [Piter De Vries card]; a twin trades a held Twisted card with one still
    # in his deck.
    checked = 0
    for state in _states():
        piter = state.players[PITER]
        # A Twisted card being played is public: "보유한 Intrigue card는 …
        # opponent에게는 play할 때만 공개한다. [Main p. 7]" (docs/rules/
        # information-visibility.md), so it is no hidden card to trade (the
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
        swap = _swap(held[0], piter.twisted_deck[0])
        players = list(state.players)
        players[PITER] = replace(
            piter,
            intrigue_cards=swap(piter.intrigue_cards),
            twisted_deck=swap(piter.twisted_deck),
        )
        _same_worlds(replace(state, players=tuple(players)), state, observer)
        checked += 1
    assert checked > 3


@pytest.mark.parametrize("observer", range(4))
def test_a_seat_world_ignores_which_stack_a_face_down_tile_is_in(
    observer: int,
) -> None:
    # The Tech tiles are shuffled face down into the three stacks [Bloodlines
    # p. 6]; a twin trades the deepest tiles of two stacks. An open Secret
    # Project pick names the bottoms: those states stay out here (``_setup_
    # states`` below).
    checked = 0
    for state in _states():
        deep = [i for i, stack in enumerate(state.tech_stacks) if len(stack) > 2]
        if len(deep) < 2 or any(
            frame.kind == FrameKind.TECH_SECRET_PROJECT
            for frame in state.decision_stack
        ):
            continue
        first, second = (state.tech_stacks[i] for i in deep[:2])
        stacks = list(state.tech_stacks)
        stacks[deep[0]] = (*first[:-1], second[-1])
        stacks[deep[1]] = (*second[:-1], first[-1])
        twin = replace(state, tech_stacks=tuple(stacks))
        _same_worlds(twin, state, observer)
        checked += 1
    assert checked > 20


def _drawn(state: GameState, holder: int, hand: tuple[str, ...]) -> GameState:
    """``state`` with ``holder`` holding ``hand``, the Intrigue deck's top card
    among it."""

    players = list(state.players)
    players[holder] = replace(players[holder], intrigue_cards=hand)
    return replace(state, players=tuple(players), intrigue_deck=state.intrigue_deck[1:])


def test_a_seat_world_ignores_the_order_of_a_hand_another_seat_knows_in() -> None:
    # Imperium Ceremony (OQ-149): another seat knows a card it put back on the
    # Intrigue deck, also once a third seat draws it. The table can follow
    # where it went, but not where it lies in that hand. The sampled games
    # reach a known card in a one-card hand: give that hand the deck's next
    # card as well, and let a twin hold the two the other way round.
    checked = 0
    for state in _states():
        for knower, player in enumerate(state.players):
            for known in player.known_intrigue_ids:
                holder = next(
                    (
                        seat
                        for seat, other in enumerate(state.players)
                        if seat != knower and known in other.intrigue_cards
                    ),
                    None,
                )
                if holder is None or not state.intrigue_deck:
                    continue
                hand = (*state.players[holder].intrigue_cards, state.intrigue_deck[0])
                drawn = _drawn(state, holder, hand)
                twin = _drawn(state, holder, tuple(reversed(hand)))
                for observer in range(4):
                    if observer in (knower, holder):
                        continue
                    _same_worlds(twin, drawn, observer)
                    world = _world(drawn, observer, 0)
                    # The knower knows one of the cards dealt to that hand.
                    (knows,) = world.players[knower].known_intrigue_ids
                    assert knows in world.players[holder].intrigue_cards
                    checked += 1
    assert checked >= 2


def test_a_seat_world_ignores_which_card_another_seat_knows() -> None:
    # A twin trades a card another seat knows with a deck card nobody knows
    # and moves the knowledge with it: the knower knows a card at the same
    # place, which one the observer cannot tell.
    checked = 0
    for state in _states():
        for observer in range(4):
            mine = set(state.players[observer].known_intrigue_ids)
            knower = next(
                (
                    player
                    for seat, player in enumerate(state.players)
                    if seat != observer and set(player.known_intrigue_ids) - mine
                ),
                None,
            )
            if knower is None:
                continue
            known = next(c for c in knower.known_intrigue_ids if c not in mine)
            everyone = {c for p in state.players for c in p.known_intrigue_ids}
            unknown = [c for c in state.intrigue_deck if c not in everyone]
            if not unknown or known in state.players[observer].intrigue_cards:
                continue
            swap = _swap(known, unknown[-1])
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
            _same_worlds(twin, state, observer)
            checked += 1
    assert checked >= 6


def _cards(state: GameState) -> Counter[str]:
    """Every card and tile in a hidden or public zone a world re-deals."""

    cards: Counter[str] = Counter(
        (
            *state.imperium_deck,
            *state.intrigue_deck,
            *state.contract_bank,
            *state.contract_box,
            *state.conflict_deck,
            *state.unused_conflict_ids,
            *state.twisted_deck_stock,
            *state.navigation_stock,
            *state.tleilaxu_deck,
            *state.skill_stack,
            *(tile for stack in state.tech_stacks for tile in stack),
            *(row[2] for row in state.scouts_goods_cards),
        )
    )
    for player in state.players:
        cards.update(
            (
                *player.hand,
                *player.deck,
                *player.intrigue_cards,
                *player.twisted_deck,
                *player.navigation_slots,
                *player.navigation_box,
                *player.starting_contract_ids,
            )
        )
        for card in (player.secret_project_tech_id, player.set_aside_card_id):
            if card:
                cards[card] += 1
    for frame in state.decision_stack:
        if frame.kind == FrameKind.NAVIGATION_SETUP:
            # The five cards an open setup pick shows Steersman Y'rkoon.
            cards.update(_context_ids(frame, "hand"))
    return cards


@pytest.mark.parametrize("observer", range(4))
def test_a_seat_world_keeps_the_seats_view_its_secrets_and_every_card(
    observer: int,
) -> None:
    for state in (*_states(), *_draft_states(), *_setup_states()):
        world = _world(state, observer, 2)
        assert observe_state(world, observer) == observe_state(state, observer)
        assert _cards(world) == _cards(state)
        mine, real = world.players[observer], state.players[observer]
        assert mine.navigation_slots == real.navigation_slots
        assert mine.secret_project_tech_id == real.secret_project_tech_id
        assert mine.intrigue_cards == real.intrigue_cards
        # Piter can count his own Twisted deck; its order is hidden.
        assert sorted(mine.twisted_deck) == sorted(real.twisted_deck)
        tops = [(s[:1], len(s)) for s in state.tech_stacks]
        assert [(s[:1], len(s)) for s in world.tech_stacks] == tops


def test_a_seat_world_deals_the_hidden_zones_again() -> None:
    # Over a few worlds each zone takes other contents or another order than
    # the real one.
    moved: dict[str, bool] = dict.fromkeys(
        (
            "navigation slots",
            "secret project",
            "held twisted",
            "own twisted order",
            "tleilaxu order",
            "skill order",
            "tech membership",
            "twisted stock order",
            "navigation stock order",
        ),
        False,
    )
    for state in (*_states(), *_draft_states()):
        for seed in range(3):
            observer = 3
            world = _world(state, observer, seed)
            real, dealt = state.players, world.players
            moved["navigation slots"] |= sorted(real[YRKOON].navigation_slots) != (
                sorted(dealt[YRKOON].navigation_slots)
            )
            moved["secret project"] |= (
                real[KOTA].secret_project_tech_id != dealt[KOTA].secret_project_tech_id
            )
            moved["held twisted"] |= {
                c for c in real[PITER].intrigue_cards if is_twisted_intrigue(c)
            } != {c for c in dealt[PITER].intrigue_cards if is_twisted_intrigue(c)}
            moved["tleilaxu order"] |= state.tleilaxu_deck != world.tleilaxu_deck
            moved["skill order"] |= state.skill_stack != world.skill_stack
            moved["tech membership"] |= [sorted(s) for s in state.tech_stacks] != [
                sorted(s) for s in world.tech_stacks
            ]
            moved["twisted stock order"] |= (
                state.twisted_deck_stock != world.twisted_deck_stock
            )
            moved["navigation stock order"] |= (
                state.navigation_stock != world.navigation_stock
            )
            own = _world(state, PITER, seed).players[PITER].twisted_deck
            moved["own twisted order"] |= own != real[PITER].twisted_deck
    assert all(moved.values()), moved


@pytest.mark.parametrize("observer", range(4))
def test_a_seat_world_ignores_the_order_of_the_boxed_conflicts(observer: int) -> None:
    # The unused Conflict cards go to the box unseen [Main p. 4]; once the
    # deck holds one tier only, the order the tiers are met in followed the
    # boxed cards (Codex review 2026-11-08, spectator worlds).
    checked = 0
    for state in _states():
        if len(state.unused_conflict_ids) < 2:
            continue
        twin = replace(
            state, unused_conflict_ids=tuple(reversed(state.unused_conflict_ids))
        )
        _same_worlds(twin, state, observer)
        checked += 1
    assert checked > 10


def _setup_hand(state: GameState) -> tuple[str, ...]:
    (frame,) = (f for f in state.decision_stack if f.kind == FrameKind.NAVIGATION_SETUP)
    return _context_ids(frame, "hand")


def test_a_seat_world_ignores_the_navigation_cards_another_seat_is_choosing_from() -> (
    None
):
    # At setup Kota Odax picks his Secret Project on top of Steersman Y'rkoon's
    # open pick of four of five Navigation cards (``rules.navigation``); those
    # five are Y'rkoon's alone, as hidden as his box. A twin trades one with
    # a boxed card.
    engine = UprisingRulesEngine(leader_ids=LEADERS)
    for seed in range(3):
        state = engine.reset(CONFIG, seed)
        assert _owner(engine.current_decision(state)) == KOTA
        hand, box = _setup_hand(state), state.players[YRKOON].navigation_box
        swap = _swap(hand[0], box[0])
        frames = tuple(
            replace(
                frame,
                context=tuple(
                    (key, ",".join(swap(hand)) if key == "hand" else value)
                    for key, value in frame.context
                ),
            )
            if frame.kind == FrameKind.NAVIGATION_SETUP
            else frame
            for frame in state.decision_stack
        )
        players = list(state.players)
        players[YRKOON] = replace(players[YRKOON], navigation_box=swap(box))
        twin = replace(state, players=tuple(players), decision_stack=frames)
        _same_worlds(twin, state, KOTA)
        dealt = set()
        for world_seed in range(4):
            world = _world(state, KOTA, world_seed)
            in_world = (*_setup_hand(world), *world.players[YRKOON].navigation_box)
            assert sorted(in_world) == sorted((*hand, *box))
            dealt.add(_setup_hand(world))
            # Kota picks, then Y'rkoon can still make his pick in the world.
            for seat in (KOTA, YRKOON, YRKOON, YRKOON, YRKOON):
                assert _owner(engine.current_decision(world)) == seat
                (action, *_) = engine.legal_actions(world, seat)
                world = engine.apply(world, action).state
            assert len(world.players[YRKOON].navigation_slots) == 4
        assert len(dealt) > 1


def test_a_seat_world_keeps_a_navigation_card_being_played_in_its_slot() -> None:
    # A played Navigation card is face up while it resolves and leaves its
    # slot when done (``rules.intrigue``, by identity): another seat's world
    # keeps it there and deals the other slots again.
    state = next(s for s in _states() if len(s.players[YRKOON].navigation_slots) > 2)
    playing = state.players[YRKOON].navigation_slots[0]
    frame = DecisionFrame(
        kind=FrameKind.INTRIGUE_CHOICE,
        frame_id="test:navigation:choice",
        decision=PlayerDecision(owner=YRKOON, prompt="Resolve the Navigation choice"),
        context=(("card_id", playing),),
    )
    resolving = replace(state, decision_stack=(*state.decision_stack, frame))
    others = set()
    for seed in range(6):
        slots = _world(resolving, 3, seed).players[YRKOON].navigation_slots
        assert slots[0] == playing
        others.add(slots[1:])
    assert len(others) > 1


# Uprising with Rise of Ix and the CHOAM Module: at setup every seat's
# starting Contract pick sits on Kota Odax's open Secret Project pick, which
# sits on Steersman Y'rkoon's open Navigation pick.
IX_CONFIG = replace(CONFIG, rise_of_ix=True)


@cache
def _setup_states() -> tuple[GameState, ...]:
    engine = UprisingRulesEngine(leader_ids=LEADERS)
    states = []
    for seed in range(3):
        state = engine.reset(IX_CONFIG, seed)
        kinds = [frame.kind for frame in state.decision_stack]
        assert kinds == [
            FrameKind.NAVIGATION_SETUP,
            FrameKind.TECH_SECRET_PROJECT,
            FrameKind.STARTING_CONTRACT,
        ]
        states.append(state)
    return tuple(states)


def _play_setup(world: GameState) -> GameState:
    """Every seat answers its setup picks with its first legal action."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    chance = ChanceResolver(seed=0)
    for _ in range(40):
        if world.phase is not GamePhase.SETUP:
            break
        decision = engine.current_decision(world)
        if isinstance(decision, ChanceDecision):
            world = engine.apply(world, chance.resolve(decision)).state
            continue
        (action, *_) = engine.legal_actions(world, _owner(decision))
        world = engine.apply(world, action).state
    assert world.phase is not GamePhase.SETUP
    return world


@pytest.mark.parametrize("observer", range(4))
def test_a_seat_world_keeps_every_open_setup_pick_playable(observer: int) -> None:
    # Review 2026-11-08: a world re-dealt the stack bottoms under Kota's open
    # pick, which still named the old ones, and applying it raised "a Tech
    # tile cannot occupy two zones" (also before the change).
    for state in _setup_states():
        for seed in range(3):
            world = _world(state, observer, seed)
            if observer == KOTA:
                # He looks at the bottoms (``secret_project_candidates``).
                assert [s[-1] for s in world.tech_stacks] == [
                    s[-1] for s in state.tech_stacks
                ]
            played = _play_setup(world)
            assert played.players[KOTA].secret_project_tech_id
            assert len(played.players[YRKOON].navigation_slots) == 4


@pytest.mark.parametrize("observer", [seat for seat in range(4) if seat != KOTA])
def test_a_seat_world_ignores_which_tiles_another_seats_open_pick_shows(
    observer: int,
) -> None:
    # Kota's open pick shows him the bottom of each stack (``rules.tech.
    # assign_secret_project``); a twin trades a bottom with a deeper tile of
    # its stack, and his pick names the new bottom.
    for state in _setup_states():
        stack = state.tech_stacks[0]
        swap = _swap(stack[-1], stack[1])
        frames = tuple(
            _with_candidates(frame, swap)
            if frame.kind == FrameKind.TECH_SECRET_PROJECT
            else frame
            for frame in state.decision_stack
        )
        twin = replace(
            state,
            tech_stacks=(swap(stack), *state.tech_stacks[1:]),
            decision_stack=frames,
        )
        _same_worlds(twin, state, observer)


def _with_candidates(
    frame: DecisionFrame, swap: Callable[[tuple[str, ...]], tuple[str, ...]]
) -> DecisionFrame:
    context = dict(frame.context)
    context["candidates"] = ",".join(swap(_context_ids(frame, "candidates")))
    return replace(frame, context=tuple(sorted(context.items())))


def test_a_seat_world_names_another_seats_next_navigation_card_anew() -> None:
    # Steersman Y'rkoon's choice of how to play his next Navigation card names
    # it before it is played (``rules.navigation.begin_navigation_play``); a
    # world deals his slots again and names the card now in his first slot.
    # (In play that frame is on top, so only he decides above it.)
    state = next(s for s in _states() if len(s.players[YRKOON].navigation_slots) > 2)
    slots = state.players[YRKOON].navigation_slots

    def choosing(card: str, base: GameState = state) -> GameState:
        frame = DecisionFrame(
            kind=FrameKind.NAVIGATION_CHOICE,
            frame_id="test:navigation:choice",
            decision=PlayerDecision(owner=YRKOON, prompt="Play the Navigation card"),
            context=(("card_id", card), ("faction", "emperor"), ("source", "test")),
        )
        return replace(base, decision_stack=(*base.decision_stack, frame))

    open_choice = choosing(slots[0])
    box = state.players[YRKOON].navigation_box
    swap = _swap(slots[0], box[0])
    players = list(state.players)
    players[YRKOON] = replace(
        players[YRKOON], navigation_slots=swap(slots), navigation_box=swap(box)
    )
    twin = choosing(box[0], replace(state, players=tuple(players)))
    _same_worlds(twin, open_choice, 3)
    named = set()
    for seed in range(4):
        world = _world(open_choice, 3, seed)
        card = dict(world.decision_stack[-1].context)["card_id"]
        assert card == world.players[YRKOON].navigation_slots[0]
        named.add(card)
    assert len(named) > 1
