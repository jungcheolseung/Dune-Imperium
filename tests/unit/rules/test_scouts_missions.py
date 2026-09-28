"""Arrakeen Scouts: missions (slices 6a and 6b).

docs/rules/arrakeen-scouts.md 5: "임무로 놓인 조각은 라운드가 끝나도 남는다.
보상은 받을 때까지 유효하다." [Scouts help]; each seat decides in turn order
whether to take part (OQ-071, OQ-088); parked troops are the seat's own and
count toward its 12 (OQ-077); face-down board cards are hidden to all.
"""

from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.determinize import determinize
from dune_imperium.content.arrakeen_scouts import MISSIONS_BY_ID
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.observation import known_card_seats
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.rules.frames import FrameKind

ENGINE = UprisingRulesEngine()
CHOAM = RulesetConfig(arrakeen_scouts=True, choam_module=True)
IMMORTALITY = RulesetConfig(arrakeen_scouts=True, immortality=True)
STARTERS = starting_deck_instance_ids(0)
CARD_FOR = {
    "deliver_supplies": "player:0:starter:diplomacy:0",
    "sardaukar": "player:0:starter:diplomacy:0",
    "desert_tactics": "player:0:starter:diplomacy:0",
    "espionage": "player:0:starter:seek_allies:0",
    "imperial_privilege": "player:0:starter:dagger:0",
    "gather_support": "player:0:starter:dagger:0",
    "research_station": "player:0:starter:reconnaissance:0",
    "sietch_tabr": "player:0:starter:reconnaissance:0",
    "hagga_basin": "player:0:starter:dune_the_desert_planet:0",
}


def _base(config: RulesetConfig = CHOAM, round_number: int = 3) -> GameState:
    """A Scouts step about to reveal a mission; seat 0 is First Player."""

    state = ENGINE.reset(config, 31)
    resolver = ChanceResolver(seed=31)
    while isinstance(ENGINE.current_decision(state), ChanceDecision):
        decision = ENGINE.current_decision(state)
        assert isinstance(decision, ChanceDecision)
        state = ENGINE.apply(state, resolver.resolve(decision)).state
    players = tuple(
        replace(
            player,
            resources=Resources(solari=6, spice=6, water=2),
            influence=Influence(2, 2, 2, 2),
            hand=STARTERS if player.player_id == 0 else player.hand,
            deck=() if player.player_id == 0 else player.deck,
        )
        for player in state.players
    )
    return replace(
        state,
        round_number=round_number,
        first_player=0,
        players=players,
        decision_stack=(),
        scouts_opening=True,
        # Round 3's single mission slot is the only one left to fill.
        scouts_mission_rounds=(2, 2, 3),
        scouts_revealed=((2, "imperial_reserve"), (2, "weirding_warfare")),
    )


def _reveal(state: GameState, mission_id: str, **fields: Any) -> GameState:
    """Reveal ``mission_id`` as the round-3 mission.

    [Scouts schedule]: the last mission differs in type from the one before,
    so the two earlier missions are picked of the other type.
    """

    earlier = (
        ((2, "weirding_warfare"), (2, "send_for_aid"))
        if MISSIONS_BY_ID[mission_id].mission_type == 0
        else ((2, "imperial_reserve"), (2, "security_detail"))
    )
    fields.setdefault("scouts_revealed", earlier)
    state = replace(state, **fields)
    advanced = _advance_automatic(RuleResult(state=state)).state
    frame = advanced.decision_stack[-1]
    assert frame.kind == FrameKind.SCOUTS_DRAW
    decision = frame.decision
    assert isinstance(decision, ChanceDecision)
    assert mission_id in decision.options, decision.options
    return ENGINE.apply(
        advanced, ChanceOutcome(decision_id=decision.decision_id, values=(mission_id,))
    ).state


def _owner(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _act(state: GameState, action_id: str, **arguments: Any) -> GameState:
    seat = _owner(state)
    action = DomainAction(
        action_id=action_id, actor=seat, arguments=tuple(sorted(arguments.items()))
    )
    legal = ENGINE.legal_actions(state, seat)
    assert action in legal, (action, legal)
    return ENGINE.apply(state, action, legal_actions=legal).state


def _answer(state: GameState, joins: dict[int, str]) -> GameState:
    """Answer every participation frame: join with ``joins[seat]`` or pass."""

    while state.decision_stack[-1].kind == FrameKind.SCOUTS_MISSION:
        seat = _owner(state)
        if seat in joins:
            state = _act(state, "scouts_join_mission", target=joins[seat])
        else:
            state = _act(state, "scouts_decline_mission")
    return state


def _turn_for(state: GameState, seat: int = 0) -> GameState:
    """Give ``seat`` the turn (the Scouts step is over)."""

    return replace(
        state,
        scouts_opening=False,
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id=f"round:{state.round_number}:turn:{seat}",
                decision=PlayerDecision(owner=seat, prompt="Choose a turn"),
            ),
        ),
    )


def _send_agent(state: GameState, space_id: str) -> GameState:
    placement = next(
        a
        for a in ENGINE.legal_actions(state, 0)
        if a.action_id == "agent_turn"
        and dict(a.arguments)["space_id"] == space_id
        and dict(a.arguments)["card_id"] == CARD_FOR[space_id]
    )
    return ENGINE.apply(state, placement).state


def _visit(state: GameState, space_id: str, **choice: str) -> GameState:
    """Seat 0 sends an Agent to ``space_id`` and collects its mission pieces."""

    state = _send_agent(state, space_id)
    offered = [
        a
        for a in ENGINE.legal_actions(state, 0)
        if a.action_id == "scouts_collect_mission"
    ]
    assert offered, ENGINE.legal_actions(state, 0)
    wanted = choice.get("choice", "")
    action = next(a for a in offered if dict(a.arguments)["choice"] == wanted)
    return ENGINE.apply(state, action).state


def _taken(state: GameState) -> list[tuple[str, int]]:
    return [
        (str(dict(e.payload)["resource"]), int(str(dict(e.payload)["amount"])))
        for e in state.event_log
        if e.kind == "scouts_mission_goods_taken"
    ]


def _no_mission_icon(state: GameState) -> bool:
    return not any(
        a.action_id == "scouts_collect_mission"
        for a in ENGINE.legal_actions(state, _owner(state))
    )


def test_security_detail_parks_a_troop_that_joins_the_conflict_on_a_visit() -> None:
    state = _reveal(_base(), "security_detail")
    supply = state.players[0].troops_supply
    state = _answer(state, {0: ""})
    owner = state.players[0]
    assert (owner.troops_supply, owner.troops_parked) == (supply - 1, 1)
    assert state.scouts_parked == (("security_detail", 0, "deliver_supplies", 1),)
    state = _visit(_turn_for(state), "deliver_supplies")
    owner = state.players[0]
    assert owner.troops_parked == 0
    assert owner.troops_conflict == 1
    assert state.scouts_parked == ()


def test_a_seat_that_cannot_take_part_is_not_asked() -> None:
    base = _base()
    empty = replace(base.players[1], troops_supply=0, troops_garrison=12)
    state = _reveal(
        replace(base, players=(base.players[0], empty, *base.players[2:])),
        "security_detail",
    )
    asked = []
    while state.decision_stack[-1].kind == FrameKind.SCOUTS_MISSION:
        asked.append(_owner(state))
        state = _act(state, "scouts_decline_mission")
    assert asked == [0, 2, 3]


def test_imperial_reserve_gives_one_of_its_two_goods_per_visit() -> None:
    state = _reveal(_base(), "imperial_reserve")
    assert sorted(row[2:4] for row in state.scouts_goods) == [
        ("solari", 2),
        ("spice", 1),
    ]
    state = _visit(_turn_for(state), "imperial_privilege", choice="solari")
    # The mission paid 2 Solari and left the spice for the next visitor
    # (OQ-078); the space's own icons are separate effects of the visit.
    assert [row[2] for row in state.scouts_goods] == ["spice"]
    assert _taken(state) == [("solari", 2)]


def test_choam_research_hides_two_contracts_and_hands_one_per_visit() -> None:
    base = _base()
    bank = base.contract_bank
    state = _reveal(base, "choam_research")
    board = tuple(card for _, _, card in state.scouts_goods_cards)
    assert board == bank[:2]
    assert state.contract_bank == bank[2:]
    known = known_card_seats(state)
    assert all(known[card] == frozenset() for card in board)
    state = _visit(_turn_for(state), "research_station")
    assert board[0] in (
        *state.players[0].active_contract_ids,
        *state.players[0].completed_contract_ids,
    )
    assert tuple(card for _, _, card in state.scouts_goods_cards) == board[1:]


def test_emperors_schemes_hands_one_hidden_intrigue_per_visit() -> None:
    base = _base()
    deck = base.intrigue_deck
    state = _reveal(base, "emperors_schemes")
    assert tuple(card for _, _, card in state.scouts_goods_cards) == deck[:2]
    held = len(state.players[0].intrigue_cards)
    state = _visit(_turn_for(state), "sardaukar")
    assert state.players[0].intrigue_cards[-1] == deck[0]
    assert len(state.players[0].intrigue_cards) == held + 1


def test_determinize_redeals_the_board_cards_from_the_hidden_pools() -> None:
    import random

    state = _reveal(_base(), "emperors_schemes")
    sampled = determinize(state, 0, random.Random(4))
    assert len(sampled.scouts_goods_cards) == 2
    before = sorted(
        (*state.intrigue_deck, *(c for _, _, c in state.scouts_goods_cards))
    )
    after = sorted(
        (*sampled.intrigue_deck, *(c for _, _, c in sampled.scouts_goods_cards))
    )
    assert before == after


def test_prison_planet_trades_a_garrison_troop_for_a_marker_and_spice() -> None:
    config = CHOAM
    state = _reveal(_base(config), "prison_planet")
    garrison = state.players[0].troops_garrison
    state = _answer(state, {0: ""})
    assert state.players[0].troops_garrison == garrison - 1
    mine = sorted(row[2:] for row in state.scouts_goods if row[4] == 0)
    assert mine == [("marker", 1, 0), ("spice", 2, 0)]
    state = _visit(_turn_for(state), "sardaukar")
    assert not [row for row in state.scouts_goods if row[4] == 0]
    assert _taken(state) == [("spice", 2)]
    assert any(e.kind == "scouts_marker_returned" for e in state.event_log)


def test_prison_planet_needs_a_free_control_marker() -> None:
    base = _base()
    three = replace(
        base.players[0],
        control_space_ids=("arrakeen", "spice_refinery", "imperial_basin"),
    )
    state = _reveal(replace(base, players=(three, *base.players[1:])), "prison_planet")
    assert _owner(state) == 1


def test_fedaykin_assistance_recruits_its_troops_on_a_visit() -> None:
    state = _reveal(_base(), "fedaykin_assistance")
    spice = state.players[0].resources.spice
    state = _answer(state, {0: ""})
    assert state.players[0].resources.spice == spice - 1
    assert state.players[0].troops_parked == 2
    garrison = state.players[0].troops_garrison
    state = _visit(_turn_for(state), "desert_tactics")
    assert state.players[0].troops_garrison == garrison + 2
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.AGENT_EFFECTS
    # Recruited this turn: Desert Tactics is a Combat space [Main p. 10].
    recruited = dict(frame.context)["troops_recruited"]
    assert isinstance(recruited, int) and recruited >= 2


def test_weirding_warfare_sends_its_troops_to_the_conflict() -> None:
    state = _reveal(_base(), "weirding_warfare")
    solari = state.players[0].resources.solari
    state = _answer(state, {0: ""})
    assert state.players[0].resources.solari == solari - 2
    state = _visit(_turn_for(state), "espionage")
    assert state.players[0].troops_conflict == 2
    assert state.players[0].troops_parked == 0


def test_send_for_aid_moves_a_garrison_troop_and_its_water() -> None:
    state = _reveal(_base(), "send_for_aid")
    garrison = state.players[0].troops_garrison
    state = _answer(state, {0: ""})
    assert state.players[0].troops_garrison == garrison - 1
    water = state.players[0].resources.water
    state = _visit(_turn_for(state), "gather_support")
    assert state.players[0].troops_conflict == 1
    assert state.players[0].resources.water == water + 1


def test_coordinate_with_the_emperor_parks_a_specimen() -> None:
    base = _base(IMMORTALITY)
    seat = replace(
        base.players[0], specimens=1, troops_supply=base.players[0].troops_supply - 1
    )
    state = _reveal(
        replace(base, players=(seat, *base.players[1:])),
        "coordinate_with_the_emperor",
    )
    state = _answer(state, {0: ""})
    assert (state.players[0].specimens, state.players[0].troops_parked) == (0, 1)
    garrison = state.players[0].troops_garrison
    state = _visit(_turn_for(state), "sardaukar")
    assert state.players[0].troops_garrison == garrison + 1
    assert _taken(state) == [("solari", 2)]


def test_choam_escort_recruits_or_loads_a_face_up_contract() -> None:
    base = _base()
    contract = base.contract_bank[0]
    seat = replace(base.players[0], active_contract_ids=(contract,))
    state = _reveal(
        replace(
            base,
            players=(seat, *base.players[1:]),
            contract_bank=base.contract_bank[1:],
        ),
        "choam_escort",
    )
    offered = {dict(a.arguments).get("target") for a in ENGINE.legal_actions(state, 0)}
    assert offered == {None, "recruit", contract}
    state = _act(state, "scouts_join_mission", target=contract)
    assert sorted(row[1:] for row in state.scouts_goods) == [
        (f"contract:{contract}", "solari", 1, 0),
        (f"contract:{contract}", "spice", 1, 0),
    ]


def test_parked_troops_count_toward_the_twelve() -> None:
    base = _base()
    with pytest.raises(ValueError, match="12 troops"):
        replace(base.players[0], troops_parked=1)
    with pytest.raises(ValueError, match="parked troops"):
        replace(
            base,
            players=(
                replace(
                    base.players[0],
                    troops_parked=1,
                    troops_supply=base.players[0].troops_supply - 1,
                ),
                *base.players[1:],
            ),
        )


def test_no_mission_icon_without_pieces_for_the_seat() -> None:
    state = _reveal(_base(), "security_detail")
    state = _answer(state, {1: ""})  # seat 1's troop, not seat 0's
    state = _send_agent(_turn_for(state), "deliver_supplies")
    assert _no_mission_icon(state)


def test_prison_planet_marker_is_taken_back_for_a_third_control() -> None:
    """[Scouts help]: 세 번째 칸을 지배하게 될 때 마커가 모자라면 이 마커를
    가져다 쓰고 임무는 spice 없이 끝난다 (docs/rules/arrakeen-scouts.md 5)."""

    from dune_imperium.core.state import GamePhase
    from dune_imperium.rules.combat import resolve_combat_rewards

    state = _answer(_reveal(_base(), "prison_planet"), {0: ""})
    players = [
        replace(
            player,
            combat_strength=strength,
            control_space_ids=(
                ("spice_refinery", "imperial_basin") if player.player_id == 0 else ()
            ),
        )
        for player, strength in zip(state.players, (8, 6, 4, 0), strict=True)
    ]
    state = replace(
        state,
        players=tuple(players),
        phase=GamePhase.COMBAT,
        scouts_opening=False,
        decision_stack=(),
        conflict_deck=tuple(c for c in state.conflict_deck if c != "siege_of_arrakeen"),
        current_conflict_ids=("siege_of_arrakeen",),
        combat_intrigue_complete=True,
    )
    result = resolve_combat_rewards(state)
    after = result.state
    assert after.players[0].control_space_ids[-1] == "arrakeen"
    assert not [row for row in after.scouts_goods if row[4] == 0]
    taken = [e for e in result.events if e.kind == "scouts_prison_marker_taken"]
    assert [dict(e.payload) for e in taken] == [{"player": 0, "spice_returned": 2}]


def test_choam_research_skips_the_immediate_without_an_intrigue_card() -> None:
    """[Bloodlines p. 2]: the Immediate cannot be taken without an Intrigue
    card to trash; the visitor takes the next face-down card (OQ-090)."""

    config = RulesetConfig(arrakeen_scouts=True, choam_module=True, bloodlines=True)
    base = _base(config)
    immediate = "contract:bloodlines_immediate"
    assert immediate in base.contract_bank
    other = next(c for c in base.contract_bank if c != immediate)
    rest = tuple(c for c in base.contract_bank if c not in (immediate, other))
    empty_handed = replace(base.players[0], intrigue_cards=())
    state = _reveal(
        replace(
            base,
            contract_bank=(immediate, other, *rest),
            players=(empty_handed, *base.players[1:]),
        ),
        "choam_research",
    )
    state = _visit(_turn_for(state), "research_station")
    assert other in state.players[0].active_contract_ids + (
        state.players[0].completed_contract_ids
    )
    assert [card for _, _, card in state.scouts_goods_cards] == [immediate]
    # Only the Immediate is left: no mission icon for a seat without Intrigue.
    state = _send_agent(
        replace(_turn_for(state), players=(empty_handed, *state.players[1:])),
        "research_station",
    )
    assert _no_mission_icon(state)


def _apply(state: GameState, action_id: str, **arguments: Any) -> GameState:
    return _act(state, action_id, **arguments)


def test_desert_riding_trades_hagga_basin_spice_for_the_maker_hooks() -> None:
    """docs/rules/arrakeen-scouts.md 5 (Desert Riding): "방문자는 칸의 기본
    spice 2 대신 그 토큰을 가질 수 있다(Maker 보너스 spice는 그대로)" (OQ-079)."""

    state = _reveal(_base(), "desert_riding")
    assert [row[2] for row in state.scouts_goods] == ["maker_hooks"]
    seat = replace(state.players[0], maker_hooks=False)
    state = replace(
        state,
        players=(seat, *state.players[1:]),
        maker_bonus_spice=tuple(
            (space, 1 if space == "hagga_basin" else amount)
            for space, amount in state.maker_bonus_spice
        ),
    )
    state = _send_agent(_turn_for(state), "hagga_basin")
    spice = state.players[0].resources.spice
    legal = ENGINE.legal_actions(state, 0)
    # The printed row's one choice: spice, or the token; no sandworm (d).
    assert {a.action_id for a in legal} >= {
        "harvest_maker_spice",
        "take_desert_riding_hooks",
    }
    assert "summon_maker_sandworms" not in {a.action_id for a in legal}
    state = _apply(state, "take_desert_riding_hooks", space_id="hagga_basin")
    assert state.players[0].maker_hooks
    assert state.players[0].resources.spice == spice + 1
    assert state.scouts_goods == ()
    assert _taken(state) == [("maker_hooks", 1)]


def test_desert_riding_token_is_not_for_a_seat_with_maker_hooks() -> None:
    state = _reveal(_base(), "desert_riding")
    seat = replace(state.players[0], maker_hooks=True)
    state = _send_agent(
        _turn_for(replace(state, players=(seat, *state.players[1:]))),
        "hagga_basin",
    )
    assert "take_desert_riding_hooks" not in {
        a.action_id for a in ENGINE.legal_actions(state, 0)
    }


def test_sietch_tabr_takes_the_desert_riding_token_when_it_is_the_last() -> None:
    """OQ-079 (e): the token is one of the four Maker Hooks [Main p. 3]."""

    state = _reveal(_base(), "desert_riding")
    players = tuple(
        replace(player, maker_hooks=player.player_id != 0) for player in state.players
    )
    state = _send_agent(_turn_for(replace(state, players=players)), "sietch_tabr")
    state = _apply(state, "take_sietch_tabr_supplies")
    assert state.players[0].maker_hooks
    assert state.scouts_goods == ()


def test_valued_informants_pays_the_seat_placing_a_spy_on_the_post() -> None:
    """docs/rules/arrakeen-scouts.md 5 (Valued Informants): "그 관측소에 Spy를
    놓는 좌석이 그 Solari를 가진다(OQ-080)"; Planetary Exploration's spice
    likewise."""

    state = _reveal(_base(), "planetary_exploration")
    assert sorted(row[1] for row in state.scouts_goods) == [
        "post:arrakis-deep-desert",
        "post:arrakis-hagga-basin",
        "post:arrakis-imperial-basin",
    ]
    state = _send_agent(_turn_for(state), "espionage")
    spice = state.players[0].resources.spice
    state = _apply(state, "resolve_espionage_place_spy", post_id="arrakis-hagga-basin")
    assert state.players[0].resources.spice == spice + 1
    assert "post:arrakis-hagga-basin" not in {row[1] for row in state.scouts_goods}
    assert len(state.scouts_goods) == 2


def test_urban_surveillance_skips_occupied_posts() -> None:
    base = _base()
    spy = replace(
        base.players[1],
        spies_supply=base.players[1].spies_supply - 1,
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
    )
    state = _reveal(
        replace(base, players=(base.players[0], spy, *base.players[2:])),
        "urban_surveillance",
    )
    assert sorted(row[1] for row in state.scouts_goods) == [
        "post:arrakis-research-station-sietch-tabr",
        "post:arrakis-research-station-spice-refinery",
    ]


def _escort_state(contract: str) -> GameState:
    base = _base()
    seat = replace(base.players[0], active_contract_ids=(contract,))
    return replace(
        base,
        players=(seat, *base.players[1:]),
        contract_bank=tuple(c for c in base.contract_bank if c != contract),
        face_up_contract_ids=tuple(
            c for c in base.face_up_contract_ids if c != contract
        ),
    )


def test_choam_escort_pays_its_goods_when_the_contract_completes() -> None:
    """docs/rules/arrakeen-scouts.md 5 (CHOAM Escort): "자기 앞면 Contract 하나
    위에 Solari 1 + spice 1을 올려 두고 그 Contract를 완료할 때 함께 받는다"."""

    contract = "contract:deliver_supplies"
    state = _answer(_reveal(_escort_state(contract), "choam_escort"), {0: contract})
    assert len(state.scouts_goods) == 2
    state = _send_agent(_turn_for(state), "deliver_supplies")
    before = state.players[0].resources
    state = _apply(state, "complete_contract", instance_id=contract)
    after = state.players[0].resources
    assert state.scouts_goods == ()
    assert after.spice == before.spice + 1
    assert sorted(_taken(state)) == [("solari", 1), ("spice", 1)]


def test_choam_escort_goods_return_when_the_contract_leaves_uncompleted() -> None:
    contract = "contract:deliver_supplies"
    state = _answer(_reveal(_escort_state(contract), "choam_escort"), {0: contract})
    gone = replace(state.players[0], active_contract_ids=())
    state = _advance_automatic(
        RuleResult(state=replace(state, players=(gone, *state.players[1:])))
    ).state
    assert state.scouts_goods == ()
    assert _taken(state) == []


def _immortality_state() -> GameState:
    return _base(IMMORTALITY, round_number=2)


def test_sponsored_research_goes_to_the_next_seat_reaching_the_helix() -> None:
    """docs/rules/arrakeen-scouts.md 5 (Sponsored Research): "다음에 Helix에
    닿는 좌석이 가진다"; the Helix is the first genetic marker
    [Immortality p. 6] (OQ-089 (b))."""

    from dune_imperium.content.immortality.board import (
        FIRST_GENETIC_MARKER_COLUMN,
        RESEARCH_SPACES,
        research_next_space_ids,
    )
    from dune_imperium.rules.immortality import move_research_token

    state = replace(
        _immortality_state(),
        scouts_goods=(("sponsored_research", "helix", "spice", 2, -1),),
    )
    before = next(
        s
        for s in RESEARCH_SPACES
        if s.column == FIRST_GENETIC_MARKER_COLUMN - 1
        and research_next_space_ids(s.space_id)
    )
    after = research_next_space_ids(before.space_id)[0]
    seat = replace(state.players[1], research_space=before.space_id)
    state = replace(state, players=(state.players[0], seat, *state.players[2:]))
    spice = seat.resources.spice
    moved = move_research_token(state, 1, after, source="test").state
    assert moved.scouts_goods == ()
    assert moved.players[1].resources.spice >= spice + 2
    # A seat already past the Helix does not reach it again.
    past = replace(state.players[1], research_space=after)
    state = replace(state, players=(state.players[0], past, *state.players[2:]))
    beyond = research_next_space_ids(after)[0]
    assert move_research_token(state, 1, beyond, source="test").state.scouts_goods


def test_back_room_deal_pays_the_next_reclaimed_forces_acquisition() -> None:
    """docs/rules/arrakeen-scouts.md 5 (Back Room Deal): "다음에 Reclaimed
    Forces를 "획득"하는 좌석이 가진다"."""

    from dune_imperium.rules.tleilaxu_row import _apply_reclaimed_forces

    state = replace(
        _immortality_state(),
        scouts_goods=(("back_room_deal", "reclaimed_forces", "solari", 2, -1),),
    )
    seat = state.players[0]
    seat = replace(seat, specimens=3, troops_supply=seat.troops_supply - 3)
    state = replace(state, players=(seat, *state.players[1:]))
    solari = seat.resources.solari
    result = _apply_reclaimed_forces(state, 0, "tleilaxu", "test")
    assert result.state.scouts_goods == ()
    assert result.state.players[0].resources.solari == solari + 2


def test_tleilaxu_offering_turns_parked_troops_into_specimens() -> None:
    """docs/rules/arrakeen-scouts.md 5 (Tleilaxu Offering): "자기 Tleilaxu 토큰이
    그 칸에 닿으면 그 troop 2를 specimen으로 Axolotl tanks에 넣는다"
    (OQ-089 (a): the third space is index 3)."""

    from dune_imperium.rules.immortality import advance_tleilaxu
    from dune_imperium.rules.scouts_missions import offer_mission_join

    state = replace(_immortality_state(), decision_stack=())
    seat = replace(state.players[0], tleilaxu_space=1)
    state = replace(state, players=(seat, *state.players[1:]))
    state = offer_mission_join(state, 0, "tleilaxu_offering", source="test").state
    supply = state.players[0].troops_supply
    state = _act(state, "scouts_join_mission", target="")
    assert state.players[0].troops_supply == supply - 2
    assert state.players[0].troops_parked == 2
    specimens = state.players[0].specimens
    state = advance_tleilaxu(state, 0, 1, source="test").state
    assert state.players[0].troops_parked == 2
    state = advance_tleilaxu(state, 0, 1, source="test").state
    assert state.players[0].tleilaxu_space == 3
    assert state.players[0].troops_parked == 0
    assert state.players[0].specimens == specimens + 2
    assert state.scouts_parked == ()


def test_tleilaxu_offering_skips_a_seat_already_past_the_third_space() -> None:
    from dune_imperium.rules.scouts_missions import offer_mission_join

    state = replace(_immortality_state(), decision_stack=())
    seat = replace(state.players[0], tleilaxu_space=3)
    state = replace(state, players=(seat, *state.players[1:]))
    assert offer_mission_join(state, 0, "tleilaxu_offering", source="t").state == state
