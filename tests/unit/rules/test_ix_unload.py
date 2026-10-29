"""Rise of Ix's Unload: a Reveal box gained when its card is discarded or trashed.

Rules: docs/rules/rise-of-ix.md 7 [Rise of Ix p. 7] [FAQ p. 2] and its
designer ruling ("비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지
해결한 뒤 오른쪽으로 간다"), OQ-120. The mechanism tests mark Ix cards that are
already in the deck as Unload cards with a "1 water" box (``_unload``); the
cards that print Unload are tested with their own data.
"""

import random
from collections.abc import Iterator
from dataclasses import replace

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec, action_codec
from dune_imperium.agents.agent_turn_steps import steps_after
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GameState,
    PlayerDecision,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase
from dune_imperium.rules import UprisingRulesEngine, unload
from dune_imperium.rules.effect_steps import first_step
from dune_imperium.rules.frames import FrameKind

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)
TRUTHSAYER = "imperium:truthsayer:0"
JAMIS = "imperium:jamis:0"
MOHIAM = "imperium:reverend_mother_mohiam:0"
INITIATE = "imperium:bene_gesserit_initiate:0"
# Marked as Unload cards with a "1 water" box for the mechanism tests.
MARKED = ("imperium:sayyadina:0", "imperium:truthsayer:1")
UNLOAD_ROW = "resolve_unload_icon"


@pytest.fixture
def marked(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """``MARKED`` give one water when discarded or trashed; the catalog is
    rebuilt with their rows, and rebuilt again without them afterwards."""

    def icons(card_id: str) -> tuple[tuple[str, int], ...]:
        return (("water", 1),) if card_id in MARKED else ()

    monkeypatch.setattr(unload, "unload_icons", icons)
    monkeypatch.setattr(action_codec, "unload_icons", icons)
    action_codec._catalog_of.cache_clear()
    yield
    action_codec._catalog_of.cache_clear()


def _rows(state: GameState, seat: int = 0) -> tuple[DomainAction, ...]:
    codec = ActionCodec(IX)
    rows = ENGINE.legal_actions(state, seat)
    for row in rows:
        assert codec.decode(codec.encode(row), seat) == row
    return rows


def _give(state: GameState, seat: int, **zones: tuple[str, ...]) -> GameState:
    """Put the named cards in ``seat``'s zones, taking them out of the
    Imperium deck and Row and of every seat's zones first (seeded decks)."""

    named = {card for cards in zones.values() for card in cards}
    players = []
    for player in state.players:
        cleaned = replace(
            player,
            deck=tuple(c for c in player.deck if c not in named),
            hand=tuple(c for c in player.hand if c not in named),
            discard_pile=tuple(c for c in player.discard_pile if c not in named),
            in_play=tuple(c for c in player.in_play if c not in named),
        )
        if player.player_id == seat:
            cleaned = replace(cleaned, **zones)  # type: ignore[arg-type]
        players.append(cleaned)
    return replace(
        state,
        players=tuple(players),
        imperium_deck=tuple(c for c in state.imperium_deck if c not in named),
        imperium_row=tuple(c for c in state.imperium_row if c not in named),
    )


def _start(seed: int = 3) -> GameState:
    state = ENGINE.reset(IX, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    return state


def _do(
    state: GameState, action_id: str, seat: int = 0, **arguments: object
) -> RuleResult:
    whole = next(
        row
        for row in ENGINE.whole_actions(state, seat)
        if row.action_id == action_id
        and all(
            dict(row.arguments).get(key) == value for key, value in arguments.items()
        )
    )
    events: list[GameEvent] = []
    while True:
        rows = _rows(state, seat)
        left = 0 if whole in rows else steps_after(state, whole)
        row = whole if whole in rows else first_step(state, whole)
        assert row in rows
        result = ENGINE.apply(state, row)
        events.extend(result.events)
        state = result.state
        if left == 0:
            return RuleResult(state=state, events=tuple(events))


def _offered(state: GameState, action_id: str, seat: int = 0) -> bool:
    _rows(state, seat)
    return any(row.action_id == action_id for row in ENGINE.whole_actions(state, seat))


def _kinds(events: tuple[GameEvent, ...]) -> list[str]:
    return [event.kind for event in events]


@pytest.mark.usefixtures("marked")
def test_a_discard_cost_pays_the_unload_box_before_the_arrows_reward() -> None:
    """ "비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한 뒤
    오른쪽으로 간다" (designer ruling, rise-of-ix.md 7); Truthsayer: "Discard
    -> draw a card"."""
    state = _start()
    unloaded, kept = MARKED[0], state.players[0].hand[0]
    state = _give(state, 0, hand=(TRUTHSAYER, unloaded, kept))
    state = _do(state, "choose_agent_card", card_id=TRUTHSAYER).state
    state = _do(state, "place_agent", space_id="wealth").state
    water = state.players[0].resources.water
    top = state.players[0].deck[0]
    result = _do(state, "discard_agent_card", card_id=unloaded)
    owner = result.state.players[0]
    assert owner.resources.water == water + 1
    assert owner.hand == (kept, top)
    kinds = _kinds(result.events)
    unload_gain = next(
        index
        for index, event in enumerate(result.events)
        if event.kind == "resources_gained" and ":unload:" in event.event_id
    )
    # The box's own event closes it once its draw is paid.
    assert (
        kinds.index("card_discarded")
        < kinds.index("card_unloaded")
        < unload_gain
        < kinds.index("agent_card_effect_resolved")
    )
    assert not _offered(result.state, UNLOAD_ROW)


@pytest.mark.usefixtures("marked")
def test_a_trash_effect_in_the_owners_turn_waits_as_a_row_of_the_turn() -> None:
    """ "trash할 때 얻는다" [Rise of Ix p. 7]; Jamis: "Trash a card". In the
    owner's own turn each icon is a row of the turn, and a gain holds the
    turn's end until it is taken."""
    state = _start()
    unloaded = MARKED[0]
    state = _give(state, 0, hand=(JAMIS, unloaded))
    state = _do(state, "choose_agent_card", card_id=JAMIS).state
    state = _do(state, "place_agent", space_id="stillsuits").state
    water = state.players[0].resources.water
    trashed = _do(state, "trash_agent_card", card_id=unloaded)
    assert unloaded in trashed.state.players[0].trashed
    assert "card_unloaded" in _kinds(trashed.events)
    state = trashed.state
    assert state.players[0].resources.water == water
    state = _do(state, "resolve_board_effect", effect="resources").state
    state = _do(state, "resolve_faction_influence").state
    assert not _offered(state, "finish_agent_turn")
    taken = _do(state, UNLOAD_ROW, card_id=unloaded, effect="water")
    assert (
        taken.state.players[0].resources.water == state.players[0].resources.water + 1
    )
    assert not _offered(taken.state, UNLOAD_ROW)
    assert _offered(taken.state, "finish_agent_turn")


@pytest.mark.usefixtures("marked")
def test_an_opponents_discard_opens_the_unload_window() -> None:
    """ "남의 효과로 버려져도 된다(룰북 예: 상대의 Reverend Mother Mohiam)"
    (rise-of-ix.md 7): outside its owner's turn the box is a window of its
    own, answered before the opponent's discard goes on."""
    state = _start()
    unloaded, other = MARKED[0], state.players[1].hand[0]
    state = _give(state, 0, hand=(MOHIAM,), in_play=(INITIATE,))
    state = _give(state, 1, hand=(unloaded, other))
    state = _do(state, "choose_agent_card", card_id=MOHIAM).state
    state = _do(state, "place_agent", space_id="secrets").state
    state = _do(state, "resolve_agent_card_effect").state
    assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD
    water = state.players[1].resources.water
    state = _do(state, "discard_opponent_card", seat=1, card_id=unloaded).state
    top = state.decision_stack[-1]
    assert top.kind is FrameKind.UNLOAD_ICONS
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1
    assert [row.action_id for row in _rows(state, 1)] == [UNLOAD_ROW]
    state = _do(state, UNLOAD_ROW, seat=1, card_id=unloaded, effect="water").state
    assert state.players[1].resources.water == water + 1
    top = state.decision_stack[-1]
    assert top.kind is FrameKind.OPPONENT_CARD_DISCARD
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1


@pytest.mark.usefixtures("marked")
def test_clean_up_moves_an_unload_card_without_unloading_it() -> None:
    """ "Clean Up에서 in play 카드를 discard pile로 옮기는 것은 discard가 아니다"
    (rise-of-ix.md 7, [FAQ p. 2]; OQ-120)."""
    state = _give(_start(), 0, in_play=(MARKED[0],))
    chance = ChanceResolver(seed=3)
    rng = random.Random(3)
    unloaded: list[GameEvent] = []
    while state.round_number == 1 and state.phase is not GamePhase.FINISHED:
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            result = ENGINE.apply(state, chance.resolve(decision))
        else:
            assert isinstance(decision, PlayerDecision)
            result = ENGINE.apply(
                state, rng.choice(ENGINE.legal_actions(state, decision.owner))
            )
        unloaded.extend(e for e in result.events if e.kind == "card_unloaded")
        state = result.state
    assert state.round_number == 2
    assert MARKED[0] in state.players[0].discard_pile
    assert unloaded == []
