"""Ilesa Ecaz, a Rise of Ix Leader (stage P4e).

docs/rules/rise-of-ix.md 10: "Ilesa Ecaz (3) | One Step Ahead: Round Start에 손의
카드 하나를 따로 둔다. 라운드의 둘째 turn을 시작할 때 공개해 손으로 되돌린다. 그 turn에
그 카드로 Agent를 보내면 Agent 아이콘이 정확히 하나면 spice 1, 아니면 1 Solari |
Guild Contacts: 1 Solari → Foldspace 획득 | `[Rise of Ix p. 10]` `[FAQ p. 2]`; Agent
없는 pass와 Weirding Way 추가 turn 모두 센다(OQ-119 사용자 확정)"; 4 (OQ-122): "Holtzman
Engine·Shuttle Fleet → Ilesa의 따로 두기(Holtzman Engine으로 뽑은 카드까지 든 손에서) →
첫 turn"; 13: "Ilesa Ecaz의 따로 둔 카드 | Ilesa 좌석 | 둘째 turn에 공개". Played
through ``UprisingRulesEngine`` in an original game with Rise of Ix, Ilesa at
seat 0; every offered row round-trips through ``ActionCodec``, and the
observations are checked for hidden information where it changes.
"""

from dataclasses import replace
from functools import cache

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents import HeuristicAgent
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    Resources,
    RuleResult,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.acquisition import next_reserve_instance_id
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.effects import open_next_turn
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.one_step_ahead import (
    ONE_STEP_AHEAD_CARD_KEY,
    return_set_aside_card,
)
from dune_imperium.simulation.invariants import check_observation_privacy

ILESA = "ilesa_ecaz"
CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (ILESA, "glossu_rabban", "count_ilban_richese", "earl_memnon_thorvald")


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


def _opened() -> tuple[_Engine, GameState]:
    """Round 1 once the Round Start draws are made: Ilesa's set-aside waits."""

    engine = _Engine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    return engine, state


def _set_aside(engine: _Engine, state: GameState, index: int = 0) -> GameState:
    engine.legal_actions(state, 0)
    rows = [
        row
        for row in engine.whole_actions(state, 0)
        if row.action_id == "set_aside_leader_card"
    ]
    return apply_whole(engine, state, rows[index]).state


def _seat(state: GameState, seat: int = 0, /, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def test_ilesa_sets_a_hand_card_aside_before_the_first_turn() -> None:
    """ "Round Start에 손의 카드 하나를 따로 둔다" (rise-of-ix.md 10), after the
    five cards and before the first turn (OQ-122): her choice waits right
    above the First Player's turn frame, one row per hand card, and the card
    leaves her hand face down."""

    assert ILESA in {leader.leader_id for leader in content_for(CONFIG).leaders}
    engine, state = _opened()
    assert state.phase is GamePhase.PLAYER_TURNS
    assert [frame.kind for frame in state.decision_stack] == [
        FrameKind.TURN,
        FrameKind.ROUND_START_SET_ASIDE,
    ]
    hand = state.players[0].hand
    engine.legal_actions(state, 0)
    offered = {
        str(dict(row.arguments)["card_id"])
        for row in engine.whole_actions(state, 0)
        if row.action_id == "set_aside_leader_card"
    }
    assert offered == set(hand)
    aside = _set_aside(engine, state)
    owner = aside.players[0]
    assert owner.set_aside_card_id in hand
    assert owner.set_aside_card_id not in owner.hand
    assert len(owner.hand) == len(hand) - 1
    assert [frame.kind for frame in aside.decision_stack] == [FrameKind.TURN]


def test_the_set_aside_card_is_hers_alone_to_know() -> None:
    """13: "Ilesa Ecaz의 따로 둔 카드 | Ilesa 좌석"; every seat still counts it
    in her deck pool (plan 17.8 review 1). Every observation is checked
    against the hidden cards while she chooses and once the card is aside."""

    engine, state = _opened()
    check_observation_privacy(state)
    aside = _set_aside(engine, state)
    check_observation_privacy(aside)
    private = engine.observe(aside, 0).private
    assert private is not None
    assert private.set_aside_card_id == aside.players[0].set_aside_card_id
    for seat in (1, 2, 3):
        other = engine.observe(aside, seat).private
        assert other is not None and not other.set_aside_card_id


def test_a_public_hand_card_set_aside_tells_the_others_nothing() -> None:
    """13: the set-aside card is Ilesa's alone to know. A hand card the table
    knew (OQ-010) is no longer known to be in her hand once a card is set
    aside face down, so the other seats see the same whichever card she
    set aside."""

    engine, state = _opened()
    hand = state.players[0].hand
    known = _seat(state, hand_public=(hand[0],))
    views = []
    for index in (0, 1):
        aside = _set_aside(engine, known, index)
        assert aside.players[0].set_aside_card_id == hand[index]
        assert aside.players[0].hand_public == ()
        check_observation_privacy(aside)
        views.append(tuple(engine.observe(aside, seat).players for seat in (1, 2, 3)))
    assert views[0] == views[1]


def _drive_to_second_turn(engine: _Engine, state: GameState) -> tuple[GameState, str]:
    """Play every seat with the heuristic until Ilesa's second turn opens."""

    agents = {seat: HeuristicAgent(seed=seat + 1) for seat in range(4)}
    chance = ChanceResolver(seed=7)
    card = ""
    for _ in range(600):
        if state.players[0].set_aside_card_id:
            card = state.players[0].set_aside_card_id
        top = state.decision_stack[-1] if state.decision_stack else None
        if (
            top is not None
            and top.kind == FrameKind.TURN
            and isinstance(top.decision, PlayerDecision)
            and top.decision.owner == 0
            and state.players[0].turns_finished_round == 1
        ):
            return state, card
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        seat = decision.owner
        rows = engine.legal_actions(state, seat)
        pick = agents[seat].choose_action_with_state(
            state, engine.observe(state, seat), rows
        )
        state = engine.apply(state, pick).state
    raise AssertionError("Ilesa's second turn never opened")


def test_her_second_turn_opens_with_the_card_back_in_her_hand() -> None:
    """ "라운드의 둘째 turn을 시작할 때 공개해 손으로 되돌린다" (rise-of-ix.md 10):
    her turns are counted as they end, and the second one opens with the card
    revealed to all and back in her hand, the turn naming it for its bonus."""

    engine, state = _opened()
    second, card = _drive_to_second_turn(engine, state)
    owner = second.players[0]
    assert card
    assert owner.set_aside_card_id == ""
    assert card in owner.hand and card in owner.hand_public
    assert owner.set_aside_returned_turn is True
    assert dict(second.decision_stack[-1].context)[ONE_STEP_AHEAD_CARD_KEY] == card
    check_observation_privacy(second)


def test_a_pass_is_one_of_her_turns() -> None:
    """OQ-119 (user ruling 2026-10-22): "패스한 차례와 추가 차례 모두 센다" -- a
    turn passed without an Agent is her first turn, so the next is her
    second and returns the card."""

    engine, state = _opened()
    aside = _set_aside(engine, state)
    card = aside.players[0].set_aside_card_id
    passed = open_next_turn(aside, 0)
    assert passed.players[0].turns_finished_round == 1
    assert passed.players[0].set_aside_card_id == card
    # Seats 2 and 3 have revealed: seat 1 passing opens her turn next.
    back = replace(
        passed,
        players=tuple(
            replace(seat, has_revealed=seat.player_id in (2, 3))
            for seat in passed.players
        ),
    )
    reopened = open_next_turn(back, 1)
    returned = return_set_aside_card(RuleResult(state=reopened)).state
    assert returned.players[0].set_aside_card_id == ""
    assert card in returned.players[0].hand


def _returned(engine: _Engine, card_id: str, **changes: object) -> GameState:
    """Her second turn opened with ``card_id`` (a starting card) back in her
    hand."""

    _, state = _opened()
    state = _set_aside(engine, state)
    owner = state.players[0]
    instance = next(
        card
        for card in (*owner.hand, *owner.deck, owner.set_aside_card_id)
        if f":{card_id}:" in card
    )
    hand = tuple(card for card in owner.hand if card != instance)
    deck = tuple(card for card in owner.deck if card != instance)
    if owner.set_aside_card_id != instance:
        deck = (*deck, owner.set_aside_card_id)
    state = _seat(
        state,
        hand=hand,
        deck=deck,
        set_aside_card_id=instance,
        turns_finished_round=1,
        **changes,
    )
    returned = return_set_aside_card(RuleResult(state=state)).state
    assert instance in returned.players[0].hand
    return returned


def _send(engine: _Engine, state: GameState, card_id: str, space_id: str) -> GameState:
    engine.legal_actions(state, 0)
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == space_id
        and f":{card_id}:" in str(dict(placement.arguments)["card_id"])
    )
    placed = apply_placement(engine, state, placement).state
    engine.legal_actions(placed, 0)
    return placed


def test_an_agent_sent_with_a_one_icon_card_gains_a_spice() -> None:
    """ "그 turn에 그 카드로 Agent를 보내면 Agent 아이콘이 정확히 하나면 spice 1"
    (rise-of-ix.md 10): Dagger prints the Landsraad icon alone."""

    engine = _Engine(leader_ids=LEADERS)
    state = _returned(engine, "dagger", resources=Resources())
    placed = _send(engine, state, "dagger", "tech_negotiation")
    owner = placed.players[0]
    assert owner.resources.spice == 1
    assert owner.resources.solari == 0
    assert owner.set_aside_returned_turn is False


def test_an_agent_sent_with_any_other_count_gains_a_solari() -> None:
    """ "아니면 1 Solari": the Signet Ring prints three icons; and Dispatch an
    Envoy's four icons, granted before the Agent is sent, make a one-icon
    card one of five (designer ruling, rise-of-ix.md 9.3; OQ-055)."""

    engine = _Engine(leader_ids=LEADERS)
    state = _returned(engine, "signet_ring", resources=Resources())
    placed = _send(engine, state, "signet_ring", "arrakeen")
    assert placed.players[0].resources.solari == 1
    assert placed.players[0].resources.spice == 0

    envoy = _returned(
        engine,
        "dagger",
        resources=Resources(),
        granted_agent_icon_turn="emperor,spacing_guild,bene_gesserit,fremen",
    )
    sent = _send(engine, envoy, "dagger", "tech_negotiation")
    assert sent.players[0].resources.solari == 1
    assert sent.players[0].resources.spice == 0


def test_another_card_gains_nothing() -> None:
    """ "그 카드를 쓰지 않으면 아무것도 없음" [FAQ p. 2] (rise-of-ix.md 9.2): an
    Agent sent with another card leaves the bonus waiting, unpaid."""

    engine = _Engine(leader_ids=LEADERS)
    state = _returned(engine, "dagger", resources=Resources())
    owner = state.players[0]
    if not any(":signet_ring:" in card for card in owner.hand):
        signet = next(card for card in owner.deck if ":signet_ring:" in card)
        state = _seat(
            state,
            hand=(*owner.hand, signet),
            deck=tuple(card for card in owner.deck if card != signet),
        )
    placed = _send(engine, state, "signet_ring", "arrakeen")
    assert placed.players[0].resources == Resources()
    assert placed.players[0].set_aside_returned_turn is True


def test_a_first_turn_reveal_reveals_the_set_aside_card_without_a_bonus() -> None:
    """ "라운드 첫 turn에 Reveal을 하면 따로 둔 카드를 공개 카드에 더한다; 그때
    spice·Solari는 없다" [Rise of Ix p. 10] (rise-of-ix.md 9.1)."""

    engine, state = _opened()
    aside = _set_aside(engine, state)
    card = aside.players[0].set_aside_card_id
    resources = aside.players[0].resources
    engine.legal_actions(aside, 0)
    row = next(
        row for row in engine.whole_actions(aside, 0) if row.action_id == "reveal_turn"
    )
    revealed = apply_whole(engine, aside, row).state
    owner = revealed.players[0]
    assert owner.set_aside_card_id == ""
    assert card in owner.in_play
    assert owner.resources.spice == resources.spice


# --- Guild Contacts ----------------------------------------------------------------


def _signet(engine: _Engine, state: GameState, **changes: object) -> GameState:
    state = _seat(state, **changes)
    owner = state.players[0]
    if not any(":signet_ring:" in card for card in owner.hand):
        pool = (*owner.deck, owner.set_aside_card_id)
        instance = next(card for card in pool if ":signet_ring:" in card)
        state = _seat(
            state,
            hand=(*owner.hand, instance),
            deck=tuple(card for card in owner.deck if card != instance),
            set_aside_card_id=(
                "" if owner.set_aside_card_id == instance else owner.set_aside_card_id
            ),
        )
        if owner.set_aside_card_id == instance:
            spare = state.players[0].hand[0]
            state = _seat(
                state,
                hand=state.players[0].hand[1:],
                set_aside_card_id=spare,
            )
    return _send(engine, state, "signet_ring", "arrakeen")


def _guild_rows(engine: _Engine, state: GameState) -> set[tuple[str, bool]]:
    engine.legal_actions(state, 0)
    return {
        (
            str(dict(row.arguments)["card_id"]),
            dict(row.arguments).get("to_deck_top") is True,
        )
        for row in engine.whole_actions(state, 0)
        if row.action_id == "acquire_leader_reserve"
    }


def test_guild_contacts_buys_a_foldspace_for_a_solari() -> None:
    """ "Guild Contacts: 1 Solari → Foldspace 획득" (rise-of-ix.md 10): an arrow
    paid once, the Foldspace to her discard pile; without a Solari nothing is
    offered."""

    engine, state = _opened()
    aside = _set_aside(engine, state)
    broke = _signet(engine, aside, resources=Resources())
    assert _guild_rows(engine, broke) == set()
    placed = _signet(engine, aside, resources=Resources(solari=1))
    assert _guild_rows(engine, placed) == {("foldspace_card", False)}
    engine.legal_actions(placed, 0)
    row = next(
        row
        for row in engine.whole_actions(placed, 0)
        if row.action_id == "acquire_leader_reserve"
    )
    bought = apply_whole(engine, placed, row).state
    owner = bought.players[0]
    assert owner.resources.solari == 0
    assert any("foldspace_card" in card for card in owner.discard_pile)
    assert dict(bought.reserve_stacks)["foldspace_card"] == (
        dict(placed.reserve_stacks)["foldspace_card"] - 1
    )


def test_guild_contacts_puts_the_foldspace_on_the_deck_with_spaceport() -> None:
    """Spaceport: "얻는 카드를 덱 위에 놓을 수 있다" (rise-of-ix.md 4)."""

    engine, state = _opened()
    aside = _set_aside(engine, state)
    stacks = tuple(
        tuple(tile for tile in stack if tile != "spaceport")
        for stack in aside.tech_stacks
    )
    aside = _seat(replace(aside, tech_stacks=stacks), tech_ids=("spaceport",))
    placed = _signet(engine, aside, resources=Resources(solari=1))
    assert _guild_rows(engine, placed) == {
        ("foldspace_card", False),
        ("foldspace_card", True),
    }


def test_a_set_aside_reserve_card_keeps_its_instance_to_itself() -> None:
    """The set-aside card is still hers (rise-of-ix.md 13: every seat counts
    it in her deck pool), so the next copy of its Reserve stack another seat
    acquires takes another instance id (the 2026-10-30 random sweep found two
    Arrakis Liaison copies sharing one)."""

    _, state = _opened()
    count = dict(state.reserve_stacks)["arrakis_liaison"]
    taken = next_reserve_instance_id(state, "arrakis_liaison")
    aside = _seat(
        replace(
            state,
            reserve_stacks=tuple(
                (card_id, copies - 1 if card_id == "arrakis_liaison" else copies)
                for card_id, copies in state.reserve_stacks
            ),
        ),
        set_aside_card_id=taken,
    )
    assert dict(aside.reserve_stacks)["arrakis_liaison"] == count - 1
    assert next_reserve_instance_id(aside, "arrakis_liaison") != taken


BINDU = "intrigue:bindu_suspension:0"


def test_a_first_player_ilesa_keeps_her_first_turns_start_after_the_set_aside() -> None:
    """ "Round Start 순서 ... → Ilesa의 따로 두기(Holtzman Engine으로 뽑은 카드까지
    든 손에서) → 첫 turn" (rise-of-ix.md 4, OQ-122): the set-aside is a Round
    Start step, no action of the first turn, so a First Player Ilesa may still
    open that turn with Bindu Suspension, "Agent·Reveal을 시작하기 전 차례
    시작의 첫 행동으로만" (OQ-117); her first real action of the turn closes
    its start."""

    engine, state = _opened()
    assert state.first_player == 0
    state = replace(
        _seat(state, intrigue_cards=(BINDU,)),
        intrigue_deck=tuple(card for card in state.intrigue_deck if card != BINDU),
    )
    bindu = DomainAction("play_intrigue", 0, (("card_id", BINDU), ("option", 0)))
    aside = _set_aside(engine, state)
    assert aside.decision_stack[-1].kind == FrameKind.TURN
    engine.legal_actions(aside, 0)
    assert bindu in engine.whole_actions(aside, 0)
    pick = next(
        row
        for row in engine.whole_actions(aside, 0)
        if row.action_id == "choose_agent_card"
    )
    picked = apply_whole(engine, aside, pick).state
    assert bindu not in engine.whole_actions(picked, 0)
