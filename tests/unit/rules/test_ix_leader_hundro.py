"""Viscount Hundro Moritani, a Rise of Ix Leader (stage P4e).

docs/rules/rise-of-ix.md 10: "Viscount Hundro Moritani (1) | Intelligence:
게임 시작에 Intrigue 덱 위 두 장을 보고 하나를 갖고 하나를 위에 되돌린다 | Couriers:
spice 1 → Freighter | Signet 아이콘이 Freighter인 근거: Rival 문장 "spend 1 spice …
for the Freighter icon" `[Rise of Ix p. 8]`"; 3: "순서: Baron(원판)의 진영 고르기와
같이 "모든 setup 뒤, 첫 라운드 전"에 둔다"; 13: "Hundro 좌석이 Intrigue 덱 맨 위
카드 | 공개 영역이나 Hundro의 손에 들어갈 때까지 ... 섞이면 지운다 — OQ-149 (가)".
Played through ``UprisingRulesEngine`` in an original game with Rise of Ix;
every offered row round-trips through ``ActionCodec``, and the observations
are checked for hidden information where it changes.
"""

from dataclasses import replace
from functools import cache

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Resources,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.setup import create_draft_initial_state
from dune_imperium.simulation.invariants import check_observation_privacy

HUNDRO = "viscount_hundro_moritani"
BARON = "baron_vladimir_harkonnen"
CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (HUNDRO, "glossu_rabban", "count_ilban_richese", "earl_memnon_thorvald")


@cache
def _codec(config: RulesetConfig) -> ActionCodec:
    return ActionCodec(config)


class _Engine(UprisingRulesEngine):
    """Check every offered row, including the intermediate card/space/effect
    choices consumed by apply_whole."""

    def legal_actions(self, state: GameState, player: int) -> tuple[DomainAction, ...]:
        rows = super().legal_actions(state, player)
        codec = _codec(state.config)
        for row in rows:
            assert codec.decode(codec.encode(row), player) == row
        return rows


def _settle(engine: _Engine, state: GameState, seed: int = 3) -> GameState:
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    return state


def _keep_rows(engine: _Engine, state: GameState, seat: int) -> list[DomainAction]:
    """The keep-one choices (whole actions; the frame offers each as the
    card's step first)."""

    engine.legal_actions(state, seat)
    return [
        row
        for row in engine.whole_actions(state, seat)
        if row.action_id == "keep_peeked_intrigue"
    ]


def _keep(engine: _Engine, state: GameState, row: DomainAction) -> GameState:
    return apply_whole(engine, state, row).state


# --- Intelligence ---------------------------------------------------------------


def test_intelligence_looks_at_the_top_two_before_the_first_round() -> None:
    """ "게임 시작에 Intrigue 덱 위 두 장을 보고 하나를 갖고 하나를 위에 되돌린다"
    (rise-of-ix.md 10), "모든 setup 뒤, 첫 라운드 전" (3): the game waits in
    SETUP on his keep-one choice of the deck's top two; the kept card joins
    his Intrigue cards, the other goes back on top, and the first round then
    begins."""

    assert HUNDRO in {leader.leader_id for leader in content_for(CONFIG).leaders}
    engine = _Engine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, 3)
    assert state.phase is GamePhase.SETUP
    assert state.decision_stack[-1].kind == FrameKind.INTRIGUE_PEEK
    top = state.intrigue_deck[:2]
    rows = _keep_rows(engine, state, 0)
    assert [str(dict(row.arguments)["instance_id"]) for row in rows] == list(top)
    held = state.players[0].intrigue_cards
    kept = _keep(engine, state, rows[1])
    owner = kept.players[0]
    assert owner.intrigue_cards == (*held, top[1])
    assert kept.intrigue_deck[0] == top[0]
    assert len(kept.intrigue_deck) == len(state.intrigue_deck) - 1
    started = _settle(engine, kept)
    assert started.phase is GamePhase.PLAYER_TURNS


def test_intelligence_s_cards_are_his_alone_to_know() -> None:
    """13: "갖는 카드는 손(숨김)" and the card put back is his to know until it
    reaches a public zone or his hand (OQ-149 (가), 2026-10-29 사용자 "(가) 둘
    다 기록"); the other seats see that two were looked at and one kept, not
    which. Every observation is checked against the hidden cards while he
    looks, after he keeps one, and once the round begins."""

    engine = _Engine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, 3)
    check_observation_privacy(state)
    top = state.intrigue_deck[:2]
    private = engine.observe(state, 0).private
    assert private is not None
    assert tuple(private.peeked_intrigue_ids) == top
    for seat in (1, 2, 3):
        other = engine.observe(state, seat).private
        assert other is not None and not other.peeked_intrigue_ids
    kept = _keep(engine, state, _keep_rows(engine, state, 0)[0])
    check_observation_privacy(kept)
    assert kept.players[0].known_intrigue_ids == (top[1],)
    assert all(not seat.known_intrigue_ids for seat in kept.players[1:])
    started = _settle(engine, kept)
    check_observation_privacy(started)
    assert started.players[0].known_intrigue_ids == (top[1],)


def test_intelligence_and_masterstroke_both_happen_before_the_first_round() -> None:
    """The Baron's choice and Hundro's look both come "모든 setup 뒤, 첫 라운드
    전" (rise-of-ix.md 3, [FAQ p. 1]); the round begins once both are done,
    whichever seat answers first."""

    engine = _Engine(leader_ids=(HUNDRO, BARON, "glossu_rabban", "count_ilban_richese"))
    state = engine.reset(CONFIG, 3)
    assert [frame.kind for frame in state.decision_stack] == [
        FrameKind.MASTERSTROKE_SETUP,
        FrameKind.INTRIGUE_PEEK,
    ]
    state = _keep(engine, state, _keep_rows(engine, state, 0)[0])
    assert state.phase is GamePhase.SETUP
    for faction in ("emperor", "fremen"):
        state = engine.apply(
            state,
            DomainAction("choose_masterstroke_faction", 1, (("faction", faction),)),
        ).state
    assert _settle(engine, state).phase is GamePhase.PLAYER_TURNS


def _drafted(seed: int) -> GameState:
    """A draft resolved with ``seed``, every seat taking Hundro when he is
    offered, up to the end of SETUP or his look."""

    config = replace(CONFIG, leader_draft=True)
    engine = _Engine()
    state = create_draft_initial_state(config, seed).state
    chance = ChanceResolver(seed=seed)
    for _ in range(400):
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        if state.phase is not GamePhase.SETUP:
            break
        if state.decision_stack[-1].kind == FrameKind.INTRIGUE_PEEK:
            break
        assert decision is not None
        rows = engine.legal_actions(state, decision.owner)
        pick = next(
            (row for row in rows if dict(row.arguments).get("leader_id") == HUNDRO),
            rows[0],
        )
        state = engine.apply(state, pick).state
    return state


def test_intelligence_follows_the_leader_draft() -> None:
    """A drafted Hundro looks once the draft and every other setup step are
    done (rise-of-ix.md 3, lessons 2026-10-05: the private decision is not
    bound to the Leader pick); a draft without him starts the round."""

    engine = _Engine()
    seen = set()
    for seed in range(1, 40):
        state = _drafted(seed)
        hundro = next(
            (seat for seat in state.players if seat.leader_id == HUNDRO), None
        )
        seen.add(hundro is not None)
        if hundro is None:
            assert state.phase is not GamePhase.SETUP
            continue
        assert state.phase is GamePhase.SETUP
        assert state.decision_stack[-1].kind == FrameKind.INTRIGUE_PEEK
        assert _keep_rows(engine, state, hundro.player_id)
        check_observation_privacy(state)
        if seen == {True, False}:
            break
    assert seen == {True, False}


# --- Couriers -------------------------------------------------------------------


def _start() -> tuple[_Engine, GameState]:
    engine = _Engine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, 3)
    state = _keep(engine, state, _keep_rows(engine, state, 0)[0])
    state = _settle(engine, state)
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _signet(engine: _Engine, state: GameState, **changes: object) -> GameState:
    """Seat 0 sends the Signet Ring to Arrakeen."""

    owner = replace(state.players[0], **changes)  # type: ignore[arg-type]
    if not any(":signet_ring:" in card for card in owner.hand):
        instance = next(card for card in owner.deck if ":signet_ring:" in card)
        owner = replace(
            owner,
            hand=(*owner.hand, instance),
            deck=tuple(card for card in owner.deck if card != instance),
        )
    state = replace(state, players=(owner, *state.players[1:]))
    engine.legal_actions(state, 0)
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == "arrakeen"
        and ":signet_ring:" in str(dict(placement.arguments)["card_id"])
    )
    placed = apply_placement(engine, state, placement).state
    engine.legal_actions(placed, 0)
    return placed


_MOVES = {"advance_leader_freighter", "recall_leader_freighter"}


def _offered(engine: _Engine, state: GameState) -> set[str]:
    engine.legal_actions(state, 0)
    return {row.action_id for row in engine.whole_actions(state, 0)} & _MOVES


def test_couriers_pays_a_spice_to_move_the_freighter_up() -> None:
    """ "Couriers: spice 1 → Freighter" (rise-of-ix.md 10); the Freighter icon
    moves it "한 칸 위로(맨 위면 불가) 또는 맨 아래로 회수" (5): from the bottom
    only up."""

    engine, state = _start()
    placed = _signet(engine, state, resources=Resources(spice=1))
    assert _offered(engine, placed) == {"advance_leader_freighter"}
    row = next(
        row
        for row in engine.whole_actions(placed, 0)
        if row.action_id == "advance_leader_freighter"
    )
    moved = apply_whole(engine, placed, row).state
    assert moved.players[0].freighter_space == 1
    assert moved.players[0].resources.spice == 0
    assert _offered(engine, moved) == set()


def test_couriers_recalls_the_freighter_for_its_rewards() -> None:
    """A recall owes the rewards of the space it left and every space below
    it, taken in any order (rise-of-ix.md 5); at the top only the recall is
    offered."""

    engine, state = _start()
    placed = _signet(engine, state, resources=Resources(spice=2), freighter_space=3)
    assert _offered(engine, placed) == {"recall_leader_freighter"}
    row = next(
        row
        for row in engine.whole_actions(placed, 0)
        if row.action_id == "recall_leader_freighter"
    )
    recalled = apply_whole(engine, placed, row).state
    assert recalled.players[0].freighter_space == 0
    assert recalled.players[0].resources.spice == 1
    rewards = {
        dict(row.arguments).get("effect")
        for row in engine.legal_actions(recalled, 0)
        if row.action_id == "resolve_shipping_reward"
    }
    assert {"dividends", "spice", "recruit", "tech"} <= rewards


def test_couriers_without_spice_offers_nothing() -> None:
    """The arrow's spice must be paid (rise-of-ix.md 10): without one neither
    move is offered."""

    engine, state = _start()
    placed = _signet(engine, state, resources=Resources(), freighter_space=1)
    assert _offered(engine, placed) == set()
