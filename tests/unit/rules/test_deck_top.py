"""Cards put face up on top of a deck are public (OQ-145).

docs/rules/open-questions.md OQ-145, user ruling 2026-10-28: a card put face
up on top of a deck -- the original game's Bypass Protocol and Recruitment
Mission and Immortality's Tleilaxu deck-top placement -- is known to every
seat until it is drawn or the deck is shuffled; cards placed one after
another stack in that order (the last placed on top); a card drawn into the
hand stays public there until it leaves it (``PlayerState.hand_public``,
OQ-010 ruling 1). ``rules.deck_top`` places, settles and clears the record;
the engine settles every seat after every transition.
"""

import json
import random
from dataclasses import replace

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
    ChanceResolver,
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.observation import known_card_seats, observe_state
from dune_imperium.core.state import _canonicalize, canonical_state_hash
from dune_imperium.rules.card_draw import (
    apply_personal_draw_reshuffle,
    draw_or_request_personal_cards,
    shuffle_discard_into_deck,
)
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.deck_top import (
    clear_deck_top,
    place_on_deck_top,
    settle_deck_top,
    settle_public_deck_tops,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.reveal_turn import begin_reveal_turn
from dune_imperium.rules.tleilaxu_row import (
    apply_tleilaxu_acquisition,
    legal_tleilaxu_acquisitions,
)
from dune_imperium.simulation.invariants import (
    CardCensus,
    InvariantViolation,
    check_observation_privacy,
    check_state_invariants,
)

IMMORTALITY = RulesetConfig(immortality=True)
ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
CONTAMINATOR = "tleilaxu:contaminator:0"
SUBJECT = "tleilaxu:subject_x_137:0"


def _owner(**changes: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": 0,
        "deck": ("a", "b", "c", "d"),
        "discard_pile": ("x", "y"),
    }
    values.update(changes)
    return PlayerState(**values)  # type: ignore[arg-type]


def _state(owner: PlayerState) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )


def _settled(state: GameState) -> PlayerState:
    return settle_public_deck_tops(state).players[0]


# --- the record ------------------------------------------------------------


def test_two_placements_stack_with_the_last_placed_on_top() -> None:
    owner = place_on_deck_top(place_on_deck_top(_owner(), "first"), "second")

    assert owner.deck == ("second", "first", "a", "b", "c", "d")
    assert owner.deck_public_top == ("second", "first")
    assert owner.hand_public == ()


def test_a_placement_settles_what_was_drawn_before_it() -> None:
    # The record is settled first: a public card drawn earlier in the same
    # transition is already public in the hand, and the new card stacks on
    # the cards that really are on top.
    owner = _owner(deck=("a", "b", "c"), deck_public_top=("a", "b"))
    drawn = replace(owner, deck=("b", "c"), hand=("a",))

    placed = place_on_deck_top(drawn, "new")

    assert placed.deck == ("new", "b", "c")
    assert placed.deck_public_top == ("new", "b")
    assert placed.hand_public == ("a",)


def test_a_draw_pops_the_top_and_marks_the_card_public_in_the_hand() -> None:
    state = _state(_owner(deck_public_top=("a", "b")))

    drawn = draw_or_request_personal_cards(state, 0, 1, source="test:draw").state
    assert drawn.players[0].deck_public_top == ("a", "b")  # not settled yet
    owner = _settled(drawn)

    assert owner.hand == ("a",)
    assert owner.deck == ("b", "c", "d")
    assert owner.deck_public_top == ("b",)
    assert owner.hand_public == ("a",)
    # A second draw takes the rest of the record into the hand.
    again = _settled(
        draw_or_request_personal_cards(
            replace(state, players=(owner, *state.players[1:])),
            0,
            2,
            source="test:draw",
        ).state
    )
    assert again.hand == ("a", "b", "c")
    assert again.deck_public_top == ()
    assert again.hand_public == ("a", "b")  # "c" was a plain draw


def test_a_public_card_drawn_below_the_record_stays_hidden() -> None:
    owner = _owner(hand=("h",), deck_public_top=("a",))
    drawn = replace(owner, deck=("c", "d"), hand=("h", "a", "b"))

    settled = settle_deck_top(drawn)

    assert settled.deck_public_top == ()
    assert settled.hand_public == ("a",)  # "b" below the record stays hidden


def test_trashing_or_discarding_the_top_drops_it_from_the_record() -> None:
    state = _state(_owner(deck_public_top=("a", "b")))

    trashed = trash_personal_card(state, 0, "a", source="test:trash", allow_deck=True)
    owner = _settled(trashed.state)
    assert owner.deck == ("b", "c", "d")
    assert owner.deck_public_top == ("b",)
    assert owner.hand_public == ()  # nothing went to the hand

    # A discard from the deck (Controlled's) likewise.
    owner = _owner(deck_public_top=("a",))
    discarded = replace(
        owner,
        deck=owner.deck[1:],
        discard_pile=(*owner.discard_pile, "a"),
    )
    settled = settle_deck_top(discarded)
    assert settled.deck_public_top == ()
    assert settled.hand_public == ()


def test_a_settled_record_is_returned_as_it_was() -> None:
    owner = _owner(deck_public_top=("a", "b"))
    assert settle_deck_top(owner) is owner
    plain = _owner()
    assert settle_deck_top(plain) is plain
    for state in (_state(owner), _state(plain)):
        assert settle_public_deck_tops(state) is state


def test_a_card_that_leaves_the_hand_stops_being_public() -> None:
    # OQ-010: a public hand card is public until it leaves the hand, so a card
    # drawn from the top, played and drawn again later is hidden once more.
    owner = _settled(
        draw_or_request_personal_cards(
            _state(_owner(deck_public_top=("a",))), 0, 1, source="test:draw"
        ).state
    )
    assert owner.hand_public == ("a",)
    played = replace(owner, hand=(), in_play=("a",))
    assert played.hand_public == ()
    redrawn = replace(played, hand=("a",), in_play=())
    assert redrawn.hand_public == ()


def test_refocus_clears_the_record_even_when_the_shuffle_keeps_the_top() -> None:
    # Refocus shuffles the discard pile into the deck: no card of the new
    # deck is known on top. The permutation below puts the old public top
    # first, which a settle alone would keep.
    state = _state(_owner(deck_public_top=("a", "b")))
    pending = shuffle_discard_into_deck(state, 0, 1, source="test:refocus").state
    decision = pending.decision_stack[-1].decision
    assert isinstance(decision, ChanceDecision)
    assert set(decision.options) == {"a", "b", "c", "d", "x", "y"}

    shuffled = apply_personal_draw_reshuffle(
        pending, ChanceOutcome(decision.decision_id, ("b", "a", "x", "c", "d", "y"))
    ).state
    owner = _settled(shuffled)

    assert owner.deck_public_top == ()
    # One draw followed the shuffle: "b" from the top, a plain draw.
    assert owner.hand == ("b",)
    assert owner.hand_public == ()
    assert owner.deck == ("a", "x", "c", "d", "y")


def test_a_draws_own_reshuffle_keeps_the_public_cards_it_draws_first() -> None:
    # A short draw puts the shuffled discard pile beneath the cards the deck
    # still holds, so the public top is drawn first and stays public in hand.
    state = _state(_owner(deck=("a", "b"), deck_public_top=("a", "b")))
    pending = draw_or_request_personal_cards(state, 0, 3, source="test:draw").state
    decision = pending.decision_stack[-1].decision
    assert isinstance(decision, ChanceDecision)

    result = apply_personal_draw_reshuffle(
        pending, ChanceOutcome(decision.decision_id, ("y", "x"))
    ).state
    assert result.players[0].deck_public_top == ("a", "b")  # beneath: untouched
    owner = _settled(result)

    assert owner.hand == ("a", "b", "y")
    assert owner.deck == ("x",)
    assert owner.deck_public_top == ()
    assert owner.hand_public == ("a", "b")


def test_clearing_a_seat_without_a_record_changes_nothing() -> None:
    owner = _owner()
    assert clear_deck_top(owner) is owner
    assert clear_deck_top(_owner(deck_public_top=("a",))).deck_public_top == ()


def test_the_record_must_be_the_top_of_the_deck_between_transitions() -> None:
    state = _state(_owner(deck_public_top=("a", "b")))
    census = CardCensus.from_state(state)
    check_state_invariants(state, census)

    stale = _state(_owner(deck=("b", "c", "d"), deck_public_top=("a", "b")))
    with pytest.raises(InvariantViolation, match="public deck top"):
        check_state_invariants(stale, CardCensus.from_state(stale))
    with pytest.raises(ValueError, match="publicly known twice"):
        _owner(deck_public_top=("a", "a"))


def test_a_state_without_a_public_top_hashes_as_before() -> None:
    plain = _state(_owner())
    marked = _state(_owner(deck_public_top=("a",)))

    assert "deck_public_top" in PlayerState.HASH_OMITTED_AT_DEFAULT
    assert canonical_state_hash(plain) != canonical_state_hash(marked)
    # At its default the field is left out, so every older hash holds.
    assert '"deck_public_top"' not in json.dumps(_canonicalize(plain))


# --- who knows ---------------------------------------------------------------


def test_the_record_is_public_to_every_seat_and_names_the_cards() -> None:
    owner = _owner(deck_public_top=("a", "b"))
    state = _state(owner)
    known = known_card_seats(state)

    assert "a" not in known and "b" not in known
    assert known["c"] == frozenset() and known["d"] == frozenset()
    for seat in range(4):
        view = observe_state(state, seat)
        assert view.players[0].deck_public_top == ("a", "b")
        assert view.players[1].deck_public_top == ()
        # The pool and the sizes are what they were.
        assert view.players[0].deck_size == 4


# --- an Uprising + Immortality Tleilaxu placement -----------------------------


def _reveal_state(owner: PlayerState) -> GameState:
    imperium = imperium_deck_instance_ids(False)
    state = GameState(
        config=IMMORTALITY,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        tleilaxu_row=(CONTAMINATOR, SUBJECT),
        tleilaxu_deck=(),
        tleilaxu_track_spice=2,
        players=(
            owner,
            *(
                PlayerState(
                    player_id=seat,
                    research_space=RESEARCH_START_ID,
                    family_atomics=True,
                )
                for seat in range(1, 4)
            ),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    reveal = DomainAction(action_id="reveal_turn", actor=0)
    return begin_reveal_turn(state, reveal).state


def test_a_tleilaxu_card_put_on_the_deck_is_public_to_every_seat() -> None:
    deck = starting_deck_instance_ids(0, immortality=True)
    owner = PlayerState(
        player_id=0,
        hand=deck[:5],
        deck=deck[5:],
        resources=Resources(solari=4, spice=2, water=2),
        research_space="c4r4",  # the first genetic marker
        family_atomics=True,
        specimens=3,
        troops_supply=6,
    )
    state = _reveal_state(owner)

    first = apply_tleilaxu_acquisition(state, _top_row(state, CONTAMINATOR)).state
    second = apply_tleilaxu_acquisition(first, _top_row(first, SUBJECT)).state

    owner = second.players[0]
    assert owner.deck[:2] == (SUBJECT, CONTAMINATOR)
    assert owner.deck_public_top == (SUBJECT, CONTAMINATOR)
    assert not {SUBJECT, CONTAMINATOR} & set(known_card_seats(second))
    for seat in range(4):
        view = observe_state(second, seat)
        assert view.players[0].deck_public_top == (SUBJECT, CONTAMINATOR)
    # Nothing below the public cards is known to anyone but ... nobody.
    assert known_card_seats(second)[owner.deck[2]] == frozenset()
    check_observation_privacy(second)


def _top_row(state: GameState, instance_id: str) -> DomainAction:
    """The deck-top twin of the Tleilaxu Row acquisition of ``instance_id``."""

    return next(
        action
        for action in legal_tleilaxu_acquisitions(state, 0)
        if dict(action.arguments).get("instance_id") == instance_id
        and dict(action.arguments).get("to_deck_top") is True
    )


# --- the engine settles after every transition ---------------------------------


def _play_until_round(
    config: RulesetConfig, seed: int, watched: int, rounds: int
) -> tuple[list[str], int]:
    """Play seat 0 from its first turn with ``watched`` of its deck's top cards
    public, up to ``rounds`` rounds in, checking every step; returns the
    watched cards and how many steps found one public in the hand."""

    leaders = (
        (
            "glossu_rabban",
            "count_ilban_richese",
            "earl_memnon_thorvald",
            "countess_ariana_thorvald",
        )
        if config.base_game is BaseGame.IMPERIUM
        else None
    )
    engine = UprisingRulesEngine(leader_ids=leaders)
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    owner = state.players[0]
    cards = list(owner.deck[:watched])
    players = (replace(owner, deck_public_top=tuple(cards)), *state.players[1:])
    state = replace(state, players=players)
    census = CardCensus.from_state(state)
    rng = random.Random(seed)
    seen = 0
    # A card that left the deck and the hand (played, discarded) may be shuffled
    # in and drawn again, hidden: only a card still on its way from the top is
    # watched.
    alive = set(cards)
    while state.round_number < rounds and state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
        else:
            assert isinstance(decision, PlayerDecision)
            action = rng.choice(engine.legal_actions(state, decision.owner))
            state = engine.apply(state, action).state
        check_state_invariants(state, census)
        mine = state.players[0]
        for card in sorted(alive):
            if card in mine.hand:
                assert card in mine.hand_public, card
                seen += 1
            elif card not in mine.deck:
                alive.discard(card)
    return cards, seen


@pytest.mark.parametrize("config", [ORIGINAL, RulesetConfig()])
def test_every_transition_settles_a_public_top_that_was_drawn(
    config: RulesetConfig,
) -> None:
    cards, seen = _play_until_round(config, seed=5, watched=3, rounds=3)

    # The cards were drawn at the second round's start at the latest.
    assert seen > 0, cards


def test_a_round_start_shuffle_keeps_the_public_cards_the_deck_still_holds() -> None:
    # The Round Start reshuffle appends the shuffled discard pile beneath the
    # cards the deck still holds: they are drawn first, and public in hand.
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), 4)
    chance = ChanceResolver(seed=4)
    rng = random.Random(4)
    while True:
        decision = engine.current_decision(state)
        assert state.phase is not GamePhase.FINISHED
        if isinstance(decision, ChanceDecision):
            frame = state.decision_stack[-1]
            if frame.kind == FrameKind.ROUND_START_RESHUFFLE:
                break
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        state = engine.apply(
            state, rng.choice(engine.legal_actions(state, decision.owner))
        ).state
    seat = dict(frame.context)["player"]
    assert isinstance(seat, int)
    owner = state.players[seat]
    # Let the seat hold two cards in the deck that are public.
    moved = owner.discard_pile[:2]
    crafted = replace(
        owner,
        deck=(*moved, *owner.deck),
        discard_pile=owner.discard_pile[2:],
        deck_public_top=moved,
    )
    options = tuple(crafted.discard_pile)
    pending = frame.decision
    assert isinstance(pending, ChanceDecision)
    redone = replace(
        state,
        players=tuple(
            crafted if player.player_id == seat else player for player in state.players
        ),
        decision_stack=(
            *state.decision_stack[:-1],
            replace(
                frame,
                decision=replace(pending, options=options, count=len(options)),
            ),
        ),
    )
    outcome = ChanceOutcome(pending.decision_id, tuple(reversed(options)))

    # Other seats may need a shuffle too; the round's draw follows the last.
    after = engine.apply(redone, outcome).state
    while isinstance(decision := engine.current_decision(after), ChanceDecision):
        after = engine.apply(after, chance.resolve(decision)).state

    mine = after.players[seat]
    assert set(moved) <= set(mine.hand)
    assert set(moved) <= set(mine.hand_public)
    assert mine.deck_public_top == ()
    assert not set(moved) & set(known_card_seats(after))
