"""Tests for the CHOAM Module's public Contract market."""

from dataclasses import replace

import pytest
from tests.support.reward_windows import answer_reward_windows, settle_reward_window

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.agents.engine_order import engine_order_answer
from dune_imperium.content.schema import CardDefinition
from dune_imperium.content.uprising.abilities import Ability, AbilityTiming
from dune_imperium.content.uprising.contracts import (
    CONTRACT_SOURCES,
    CONTRACTS_BY_ID,
    ContractDefinition,
)
from dune_imperium.content.uprising.effect_dsl import (
    AtBoardSpace,
    EffectSection,
    GainResources,
    TakeContract,
)
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
    canonical_state_hash,
)
from dune_imperium.core.events import GameEvent
from dune_imperium.rules import UprisingRulesEngine, turn_rows
from dune_imperium.rules.acquisition import (
    apply_reserve_acquisition,
    legal_reserve_acquisitions,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.contracts import (
    apply_contract_action,
    apply_contract_reward_icon,
    begin_contract_gain,
    contract_recall_targets,
    legacy_contract_icon_row,
    legal_contract_actions,
    legal_contract_completion_actions,
    legal_contract_icon_row_actions,
)
from dune_imperium.rules.frames import FrameKind


def _state(
    *,
    market: tuple[str, ...] = (
        "contract:arrakeen_i",
        "contract:high_council_ii",
    ),
    bank: tuple[str, ...] = ("contract:research_station_i",),
) -> GameState:
    return GameState(
        config=RulesetConfig(choam_module=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=tuple(PlayerState(player_id=seat) for seat in range(4)),
        contract_bank=bank,
        face_up_contract_ids=market,
    )


def _agent_contract_state(
    card_id: str,
    *contract_ids: str,
    resources: Resources | None = None,
    spy_post_ids: tuple[str, ...] = (),
    deck: tuple[str, ...] = (),
) -> GameState:
    resources = resources or Resources(solari=10, spice=10, water=10)
    owner = PlayerState(
        player_id=0,
        resources=resources,
        # The turn opened holding this spice (``reset_turn_counters``).
        spice_at_turn_start=resources.spice,
        deck=deck,
        hand=(card_id,),
        spies_supply=3 - len(spy_post_ids),
        spy_post_ids=spy_post_ids,
        active_contract_ids=contract_ids,
    )
    return GameState(
        config=RulesetConfig(choam_module=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _imperium_instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(True)
        if f":{card_id}:" in instance_id
    )


def _place_agent(state: GameState, space_id: str) -> GameState:
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )
    return apply_agent_action(state, action).state


def test_contract_choice_takes_selected_tile_and_refills_the_same_position() -> None:
    state = begin_contract_gain(
        _state(),
        0,
        1,
        source="round:1:test",
    ).state
    actions = legal_contract_actions(state, 0)

    assert tuple(dict(action.arguments)["instance_id"] for action in actions) == (
        "contract:arrakeen_i",
        "contract:high_council_ii",
    )

    result = apply_contract_action(state, actions[0])

    assert result.state.players[0].active_contract_ids == ("contract:arrakeen_i",)
    assert result.state.face_up_contract_ids == (
        "contract:research_station_i",
        "contract:high_council_ii",
    )
    assert result.state.contract_bank == ()
    assert result.state.decision_stack == ()
    assert result.events[0].kind == "contract_taken"


def test_contract_market_shrinks_after_the_bank_is_empty() -> None:
    state = begin_contract_gain(
        _state(bank=()),
        2,
        1,
        source="round:1:test",
    ).state
    action = legal_contract_actions(state, 2)[1]

    result = apply_contract_action(state, action)

    assert result.state.face_up_contract_ids == ("contract:arrakeen_i",)
    assert result.state.players[2].active_contract_ids == ("contract:high_council_ii",)


def test_empty_market_converts_each_contract_icon_to_two_solari() -> None:
    result = begin_contract_gain(
        _state(market=(), bank=()),
        1,
        2,
        source="round:1:test",
    )

    assert result.state.players[1].resources.solari == 4
    assert result.state.decision_stack == ()
    assert result.events[0].kind == "contract_icons_converted_to_solari"


def test_immediate_contract_completes_and_grants_two_solari_when_taken() -> None:
    state = begin_contract_gain(
        _state(market=("contract:immediate",), bank=()),
        3,
        1,
        source="round:1:test",
    ).state

    result = apply_contract_action(state, legal_contract_actions(state, 3)[0])
    owner = result.state.players[3]

    assert owner.active_contract_ids == ()
    assert owner.completed_contract_ids == ("contract:immediate",)
    assert [event.kind for event in result.events] == [
        "contract_taken",
        "contract_completed",
    ]
    # The reward waits in its window (stage B2, OQ-112); its row pays it.
    assert result.state.decision_stack[-1].kind == "contract_reward_icons"
    assert owner.resources.solari == 0
    assert settle_reward_window(result.state).players[3].resources.solari == 2


def test_engine_converts_a_second_icon_after_the_last_contract_is_taken() -> None:
    engine = UprisingRulesEngine()
    state = begin_contract_gain(
        _state(market=("contract:arrakeen_i",), bank=()),
        0,
        2,
        source="round:1:test",
    ).state
    action = legal_contract_actions(state, 0)[0]

    transition = apply_whole(engine, state, action)

    assert transition.state.players[0].active_contract_ids == ("contract:arrakeen_i",)
    assert transition.state.players[0].resources.solari == 2
    assert transition.state.decision_stack == ()
    assert [event.kind for event in transition.events] == [
        "contract_taken",
        "contract_icons_converted_to_solari",
    ]


def test_contract_zones_reject_duplicates_and_module_off_state() -> None:
    state = _state()
    owner = replace(
        state.players[0],
        active_contract_ids=("contract:arrakeen_i",),
    )
    with pytest.raises(ValueError, match="two zones"):
        replace(state, players=(owner, *state.players[1:]))

    with pytest.raises(ValueError, match="CHOAM Module"):
        GameState(
            config=RulesetConfig(),
            seed=1,
            face_up_contract_ids=("contract:arrakeen_i",),
        )


def test_matching_space_contracts_are_mandatory_orderable_agent_effects() -> None:
    state = _agent_contract_state(
        "reserve:prepare_the_way:7",
        "contract:arrakeen_i",
        "contract:arrakeen_ii",
    )
    placed = _place_agent(state, "arrakeen")
    engine = UprisingRulesEngine()

    legal = engine.whole_actions(placed, 0)
    completion_ids = {
        dict(action.arguments)["instance_id"]
        for action in legal
        if action.action_id == "complete_contract"
    }

    assert completion_ids == {"contract:arrakeen_i", "contract:arrakeen_ii"}
    assert any(action.action_id == "resolve_board_effect" for action in legal)

    first_action = next(
        action
        for action in legal
        if dict(action.arguments).get("instance_id") == "contract:arrakeen_i"
    )
    first = apply_whole(engine, placed, first_action).state
    # The first Contract's reward window is on top until its rows are paid.
    first = answer_reward_windows(engine, first)
    second_action = next(
        action
        for action in engine.whole_actions(first, 0)
        if dict(action.arguments).get("instance_id") == "contract:arrakeen_ii"
    )
    second = apply_whole(engine, first, second_action).state
    second = answer_reward_windows(engine, second)
    owner = second.players[0]

    assert owner.active_contract_ids == ()
    assert owner.completed_contract_ids == (
        "contract:arrakeen_i",
        "contract:arrakeen_ii",
    )
    assert owner.resources.water == 11
    assert owner.troops_garrison == 4
    assert {action.action_id for action in engine.whole_actions(second, 0)} == {
        "place_contract_spy"
    }
    placed_spy = apply_whole(engine, 
        second,
        engine.whole_actions(second, 0)[0],
    ).state
    assert placed_spy.players[0].spies_supply == 2
    assert len(placed_spy.players[0].spy_post_ids) == 1


def _complete(
    engine: UprisingRulesEngine, state: GameState, instance_id: str
) -> GameState:
    action = next(
        action
        for action in engine.whole_actions(state, 0)
        if action.action_id == "complete_contract"
        and dict(action.arguments)["instance_id"] == instance_id
    )
    return apply_whole(engine, state, action).state


def _icon_row(instance_id: str, icon: str) -> DomainAction:
    return DomainAction(
        action_id="resolve_contract_reward_icon",
        actor=0,
        arguments=(("contract_id", instance_id), ("effect", icon)),
    )


def test_an_in_turn_contract_reward_waits_as_rows_of_the_agent_turn() -> None:
    # OQ-112 (4), user decision 2026-10-19 B3-4 ("차례 안에서 완수한 계약의
    # 보상은 차례의 줄이다"): a Contract completed in its owner's own turn
    # leaves an icon each as rows of that turn, beside its other effects and
    # in any order, each row named by the Contract.
    state = _agent_contract_state(
        "reserve:prepare_the_way:7",
        "contract:arrakeen_i",
        "contract:arrakeen_ii",
    )
    engine = UprisingRulesEngine()
    placed = _place_agent(state, "arrakeen")
    first = _complete(engine, placed, "contract:arrakeen_ii")

    assert first.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    wholes = engine.whole_actions(first, 0)
    assert [a for a in wholes if a.action_id == "resolve_contract_reward_icon"] == [
        _icon_row("contract:arrakeen_ii", "troops"),
        _icon_row("contract:arrakeen_ii", "spy"),
    ]
    # Beside the turn's other effects: the board space's and the other
    # Contract's completion.
    assert {"resolve_board_effect", "complete_contract"} <= {
        a.action_id for a in wholes
    }
    # The frame offers each as an effect row naming the Contract (OQ-111).
    assert DomainAction(
        action_id="recruit",
        actor=0,
        arguments=(
            ("icon", "troops"),
            ("printed", "contract:arrakeen_ii"),
            ("source", "contract"),
        ),
    ) in engine.legal_actions(first, 0)

    # The other Contract first; then the rows in another order than printed.
    second = _complete(engine, first, "contract:arrakeen_i")
    assert [
        a for a in engine.whole_actions(second, 0)
        if a.action_id == "resolve_contract_reward_icon"
    ] == [
        _icon_row("contract:arrakeen_ii", "troops"),
        _icon_row("contract:arrakeen_ii", "spy"),
        _icon_row("contract:arrakeen_i", "resources"),
    ]
    paid = apply_whole(
        engine, second, _icon_row("contract:arrakeen_i", "resources")
    ).state
    paid = apply_whole(engine, paid, _icon_row("contract:arrakeen_ii", "troops")).state
    owner = paid.players[0]
    assert owner.resources.water == 11
    assert owner.troops_garrison == 4
    spy = apply_whole(engine, paid, _icon_row("contract:arrakeen_ii", "spy")).state
    assert {a.action_id for a in engine.whole_actions(spy, 0)} == {
        "place_contract_spy"
    }
    placed_spy = apply_whole(engine, spy, engine.whole_actions(spy, 0)[0]).state
    assert placed_spy.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert len(placed_spy.players[0].spy_post_ids) == 1
    assert not legal_contract_icon_row_actions(placed_spy, 0)


def test_in_turn_contract_rows_hold_the_end_of_the_turn() -> None:
    # Every icon is mandatory: the turn ends only once the rows are taken
    # (``turn_rows.holds_the_end``, OQ-112 (4)), on the server's mirror too.
    state = _agent_contract_state(
        _imperium_instance("truthtrance"),
        "contract:heighliner_ii",
    )
    engine = UprisingRulesEngine()
    placed = _place_agent(state, "heighliner")
    # The space's own effects first, so only the Contract's rows are left.
    for _ in range(8):
        space = [
            a
            for a in engine.whole_actions(placed, 0)
            if a.action_id in ("resolve_board_effect", "resolve_faction_influence")
        ]
        if not space:
            break
        placed = apply_whole(engine, placed, space[0]).state
    completed = _complete(engine, placed, "contract:heighliner_ii")
    finish = DomainAction(action_id="finish_agent_turn", actor=0)

    assert turn_rows.holds_the_end(completed, 0)
    assert finish not in engine.whole_actions(completed, 0)
    paid = apply_whole(
        engine, completed, _icon_row("contract:heighliner_ii", "troops")
    ).state
    assert not turn_rows.holds_the_end(paid, 0)
    assert finish in engine.whole_actions(paid, 0)


@pytest.mark.parametrize("first", ("contract:immediate", "contract:arrakeen_i"))
def test_a_scouts_line_run_in_the_turn_keeps_its_contract_windows(first: str) -> None:
    # A Scouts line run inside the owner's turn keeps the module's own
    # windows (cleanup-2b, OQ-095 (2): "turn 안의 Scouts 줄"에서는 창), also
    # under a frame the line opened: CHOAM Management's two Contracts. The
    # Immediate tile's reward is its window whichever pick it is.
    from dune_imperium.rules.contracts import contract_choice_frame
    from dune_imperium.rules.scouts_effects import push_scouts_effect

    state = replace(
        _agent_contract_state("reserve:prepare_the_way:7"),
        config=RulesetConfig(choam_module=True, arrakeen_scouts=True),
        face_up_contract_ids=("contract:immediate", "contract:arrakeen_i"),
        contract_bank=("contract:heighliner_i", "contract:heighliner_ii"),
    )
    state = push_scouts_effect(state, 0, "choam_management", 0, source="round:1:x")
    state = state.push_decision(contract_choice_frame(0, 2, source="round:1:x:c"))
    for pick in (first, None):
        take = next(
            action
            for action in legal_contract_actions(state, 0)
            if action.action_id == "take_contract"
            and pick in (None, dict(action.arguments)["instance_id"])
        )
        state = apply_contract_action(state, take).state
        if state.decision_stack[-1].kind == FrameKind.CONTRACT_REWARD_ICONS:
            break
    kinds = [frame.kind for frame in state.decision_stack]
    assert kinds[1] == FrameKind.SCOUTS_EFFECT
    assert kinds[-1] == FrameKind.CONTRACT_REWARD_ICONS
    assert not turn_rows.pending(state.decision_stack[0])
    assert not turn_rows.waits_on_turn(state, 0)


def test_the_older_order_answers_in_turn_contract_rows_first() -> None:
    # The heuristic, the app AI and older records keep the order the engine
    # paid a reward in before the rows (``agents.engine_order``): right after
    # the completion, the oldest Contract first, its icons in the window's
    # older order -- as the frame's effect row toward that whole action.
    state = _agent_contract_state(
        "reserve:prepare_the_way:7",
        "contract:arrakeen_i",
        "contract:arrakeen_ii",
    )
    engine = UprisingRulesEngine()
    placed = _place_agent(state, "arrakeen")
    second = _complete(engine, _complete(engine, placed, "contract:arrakeen_ii"), (
        "contract:arrakeen_i"
    ))

    assert legacy_contract_icon_row(second, 0) == _icon_row(
        "contract:arrakeen_ii", "troops"
    )
    answer = engine_order_answer(second, 0, engine.legal_actions(second, 0))
    assert answer is not None and answer.action_id == "recruit"
    assert dict(answer.arguments)["printed"] == "contract:arrakeen_ii"
    assert engine_order_answer(second, 0, engine.whole_actions(second, 0)) == (
        _icon_row("contract:arrakeen_ii", "troops")
    )


# Three posts connected to neither Arrakeen nor the Research Station, so no
# Gather Intelligence window opens at those spaces.
_REMOTE_POSTS = (
    "emperor-sardaukar-dutiful-service",
    "arrakis-hagga-basin",
    "arrakis-deep-desert",
)


@pytest.mark.parametrize(
    ("contract_id", "space_id"),
    (
        ("contract:arrakeen_ii", "arrakeen"),
        ("contract:research_station_i", "research_station"),
    ),
)
def test_contract_spy_without_supply_may_pass_up_the_recall_first(
    contract_id: str, space_id: str
) -> None:
    # Arrakeen II prints a troop and a Spy, Research Station I 2 Solari and
    # a Spy [Arrakeen II card] [Research Station I card]. "If you have no
    # Spies in your supply, you may first recall one of your Spies for no
    # effect" [Main pp. 11, 20]; docs/rules/uprising-systems.md: "supply가
    # 비었을 때의 선행 recall ... 은 그대로 선택이므로, 그때는 배치하지 않고
    # 넘어갈 수 있다" (OQ-057 (14)). The Contract frame used to force it.
    engine = UprisingRulesEngine()
    placed = _place_agent(
        _agent_contract_state(
            "reserve:prepare_the_way:7", contract_id, spy_post_ids=_REMOTE_POSTS
        ),
        space_id,
    )
    completion = next(
        action
        for action in engine.whole_actions(placed, 0)
        if action.action_id == "complete_contract"
    )
    completed = answer_reward_windows(engine, apply_whole(
        engine, placed, completion
    ).state)
    assert completed.decision_stack[-1].kind == "contract_reward_spy"
    actions = engine.whole_actions(completed, 0)
    assert [action.action_id for action in actions] == [
        "decline_contract_spy",
        "recall_spy_for_contract",
        "recall_spy_for_contract",
        "recall_spy_for_contract",
    ]

    declined = apply_whole(engine, completed, actions[0])
    assert declined.state.decision_stack[-1].kind == "agent_effects"
    assert declined.state.players[0].spy_post_ids == _REMOTE_POSTS
    assert declined.state.players[0].spies_recalled_turn == 0
    assert "spy_placement_unavailable" in {event.kind for event in declined.events}

    # Once recalled, the Spy is in the supply and has to be placed; the post
    # it left is open again.
    recall = next(
        action
        for action in actions
        if dict(action.arguments).get("post_id") == "arrakis-hagga-basin"
    )
    recalled = apply_whole(engine, completed, recall).state
    after = engine.whole_actions(recalled, 0)
    assert {action.action_id for action in after} == {"place_contract_spy"}
    assert "arrakis-hagga-basin" in {
        dict(action.arguments)["post_id"] for action in after
    }


def test_gather_intelligence_window_precedes_contract_completion() -> None:
    state = _agent_contract_state(
        "reserve:prepare_the_way:7",
        "contract:arrakeen_i",
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
    )
    placed = _place_agent(state, "arrakeen")
    engine = UprisingRulesEngine()

    # The window is open and the Contract cannot be completed yet. The
    # recall is offered even with the deck and discard pile both empty
    # (OQ-099, user ruling 2026-10-07, "허용 (앱처럼)").
    assert {
        action.action_id for action in engine.whole_actions(placed, 0)
    } == {"decline_gather_intelligence", "gather_intelligence"}

    declined = apply_whole(engine, 
        placed,
        next(
            action
            for action in engine.whole_actions(placed, 0)
            if action.action_id == "decline_gather_intelligence"
        ),
    ).state

    assert legal_contract_completion_actions(declined, 0)


def test_harvest_contracts_sum_maker_and_agent_card_spice() -> None:
    state = _agent_contract_state(
        _imperium_instance("desert_power"),
        "contract:harvest_3",
        "contract:harvest_4",
        resources=Resources(),
    )
    placed = _place_agent(state, "hagga_basin")
    engine = UprisingRulesEngine()

    assert not legal_contract_completion_actions(placed, 0)
    card_resolved = apply_whole(engine, 
        placed,
        next(
            action
            for action in engine.whole_actions(placed, 0)
            if action.action_id == "resolve_agent_card_effect"
        ),
    ).state
    assert card_resolved.players[0].resources.spice == 2
    assert not legal_contract_completion_actions(card_resolved, 0)

    harvested = apply_whole(engine, 
        card_resolved,
        next(
            action
            for action in engine.whole_actions(card_resolved, 0)
            if action.action_id == "harvest_maker_spice"
        ),
    ).state

    assert harvested.players[0].resources.spice == 4
    assert {
        dict(action.arguments)["instance_id"]
        for action in legal_contract_completion_actions(harvested, 0)
    } == {"contract:harvest_3", "contract:harvest_4"}

    first = apply_whole(engine, 
        harvested,
        next(
            action
            for action in legal_contract_completion_actions(harvested, 0)
            if dict(action.arguments)["instance_id"] == "contract:harvest_3"
        ),
    ).state
    # The first completion's reward window is paid before the next Contract.
    first = answer_reward_windows(engine, first)
    second = apply_whole(engine, 
        first,
        legal_contract_completion_actions(first, 0)[0],
    ).state
    second = answer_reward_windows(engine, second)

    assert second.players[0].resources.solari == 7


def test_harvest_total_survives_spice_spent_later_in_the_agent_turn() -> None:
    state = _agent_contract_state(
        _imperium_instance("smuggler_s_haven"),
        "contract:harvest_4",
        resources=Resources(spice=4),
    )
    state = replace(
        state,
        maker_bonus_spice=(
            ("deep_desert", 0),
            ("hagga_basin", 2),
            ("imperial_basin", 0),
        ),
    )
    placed = _place_agent(state, "hagga_basin")
    engine = UprisingRulesEngine()
    harvested = apply_whole(engine, 
        placed,
        next(
            action
            for action in engine.whole_actions(placed, 0)
            if action.action_id == "harvest_maker_spice"
        ),
    ).state
    paid = apply_whole(engine, 
        harvested,
        next(
            action
            for action in engine.whole_actions(harvested, 0)
            if action.action_id == "pay_agent_card_spice"
        ),
    ).state

    assert paid.players[0].resources.spice == 4
    assert legal_contract_completion_actions(paid, 0)


_DESERT_PLANET = (
    "player:0:starter:dune_the_desert_planet:0",
    "player:0:starter:dune_the_desert_planet:1",
)
_CRYSKNIFE = "intrigue:crysknife:0"


def _plot_spice_turn_state() -> GameState:
    """Seat 0's turn holding both Harvest Contracts, a +1 spice Plot
    (Crysknife), and two Spice Trade starters; every other seat has
    revealed, so closing this turn opens seat 0's next one."""

    state = _agent_contract_state(
        _DESERT_PLANET[0],
        "contract:harvest_3",
        "contract:harvest_4",
        resources=Resources(water=1),
    )
    owner = replace(
        state.players[0], hand=_DESERT_PLANET, intrigue_cards=(_CRYSKNIFE,)
    )
    others = tuple(replace(seat, has_revealed=True) for seat in state.players[1:])
    return replace(state, players=(owner, *others))


def _play_crysknife_plot(state: GameState) -> GameState:
    engine = UprisingRulesEngine()
    played = apply_whole(engine, 
        state,
        DomainAction(
            action_id="play_intrigue",
            actor=0,
            arguments=(("card_id", _CRYSKNIFE), ("option", 0)),
        ),
    ).state
    assert played.players[0].resources.spice == state.players[0].resources.spice + 1
    return played


def _harvest(state: GameState) -> GameState:
    engine = UprisingRulesEngine()
    return apply_whole(engine, 
        state,
        next(
            action
            for action in engine.whole_actions(state, 0)
            if action.action_id == "harvest_maker_spice"
        ),
    ).state


def _agent_to(state: GameState, card_id: str, space_id: str) -> GameState:
    return apply_agent_action(
        state,
        next(
            action
            for action in legal_agent_actions(state, 0)
            if dict(action.arguments) == {"card_id": card_id, "space_id": space_id}
        ),
    ).state


def test_harvest_counts_plot_spice_gained_before_the_placement() -> None:
    """ "Harvest contract는 Maker space에 Agent를 보내고, 그 turn에 모든 출처를
    합쳐 contract에 표시된 양의 spice를 얻으면 완료한다." [Main p. 16]
    (docs/rules/choam-module.md:26). A Plot played on the turn frame before
    the placement (OQ-015 (a)) is that turn's spice: +1 from Crysknife and
    +2 from Hagga Basin complete Harvest 3+ (the Steam app agrees), and the
    exact total of 3 leaves Harvest 4+ waiting."""

    plotted = _play_crysknife_plot(_plot_spice_turn_state())
    placed = _agent_to(plotted, _DESERT_PLANET[0], "hagga_basin")
    assert not legal_contract_completion_actions(placed, 0)

    harvested = _harvest(placed)

    assert harvested.players[0].resources.spice == 3
    assert [
        dict(action.arguments)["instance_id"]
        for action in legal_contract_completion_actions(harvested, 0)
    ] == ["contract:harvest_3"]


def test_harvest_ignores_spice_gained_on_an_earlier_turn_of_the_round() -> None:
    """The total is "그 turn에" [Main p. 16] (docs/rules/choam-module.md:26):
    the owner's earlier turn of the same round does not count. Turn one
    gains 2 (Crysknife, Imperial Basin) without reaching Harvest 3+; turn
    two's Hagga Basin brings the seat to 4 spice but gains only 2 itself."""

    engine = UprisingRulesEngine()
    plotted = _play_crysknife_plot(_plot_spice_turn_state())
    first = _harvest(_agent_to(plotted, _DESERT_PLANET[0], "imperial_basin"))
    assert first.players[0].resources.spice == 2
    assert not legal_contract_completion_actions(first, 0)
    closed = apply_whole(engine, first, DomainAction("finish_agent_turn", 0)).state
    assert closed.decision_stack[-1].kind == "turn"
    assert dict(closed.decision_stack[-1].context)["turn_owner"] == 0

    second = _harvest(_agent_to(closed, _DESERT_PLANET[1], "hagga_basin"))

    assert second.players[0].resources.spice == 4
    assert not legal_contract_completion_actions(second, 0)


def test_acquiring_the_spice_must_flow_completes_acquire_contract() -> None:
    owner = PlayerState(
        player_id=0,
        active_contract_ids=("contract:acquire",),
    )
    state = GameState(
        config=RulesetConfig(choam_module=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        reserve_stacks=(("the_spice_must_flow", 1),),
        decision_stack=(
            DecisionFrame(
                kind="reveal",
                frame_id="round:1:player:0:reveal",
                decision=PlayerDecision(owner=0, prompt="Resolve Reveal"),
                context=(
                    ("persuasion", 9),
                    ("revealed_card_count", 0),
                    ("strength", 0),
                    ("turn_owner", 0),
                ),
            ),
        ),
    )

    result = apply_reserve_acquisition(
        state,
        legal_reserve_acquisitions(state, 0)[0],
    )
    owner = result.state.players[0]

    assert owner.active_contract_ids == ()
    assert owner.completed_contract_ids == ("contract:acquire",)
    # The completion's own event comes last (cleanup-2c-3); in its owner's
    # Reveal its reward waits on that turn as rows (stage B3b, OQ-112 (4))
    # that pay it and hold the Reveal's end.
    assert [event.kind for event in result.events][-1] == "contract_completed"
    assert result.state.decision_stack[-1].kind == "reveal"
    assert turn_rows.holds_the_end(result.state, 0)
    assert owner.resources.solari == 0
    state = result.state
    reward_events: list[GameEvent] = []
    while (row := legacy_contract_icon_row(state, 0)) is not None:
        step = apply_contract_reward_icon(state, row)
        state = step.state
        reward_events.extend(step.events)
    owner = state.players[0]

    assert owner.resources.solari == 3
    assert owner.influence.spacing_guild == 1
    assert owner.victory_points == 2
    assert [event.kind for event in reward_events] == [
        "resources_gained",
        "contract_reward_icon_resolved",
        "influence_gained",
        "contract_reward_icon_resolved",
    ]


def test_contract_reward_can_take_a_new_contract_without_retroactive_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No tile in play prints "+1 Contract": that reward is the Rise of Ix
    # tiles' jumpstart [Main p. 16], out of scope. A Contract record holds
    # it, so a tile of that shape is patched in to keep its path tested.
    jumpstart = ContractDefinition(
        card=CardDefinition(
            card_id="test_jumpstart",
            name="Espionage (1 Solari, Contract)",
            sources=CONTRACT_SOURCES,
        ),
        terms=Ability(
            timing=AbilityTiming.CONTRACT,
            sections=(
                EffectSection(rewards=(GainResources(solari=1), TakeContract(1))),
            ),
            requirement=AtBoardSpace("espionage"),
        ),
    )
    monkeypatch.setitem(CONTRACTS_BY_ID, "test_jumpstart", jumpstart)
    state = _agent_contract_state(
        "player:0:starter:diplomacy:0",
        "contract:test_jumpstart",
    )
    state = replace(
        state,
        face_up_contract_ids=("contract:high_council_i",),
        contract_bank=("contract:deliver_supplies",),
    )
    placed = _place_agent(state, "espionage")
    engine = UprisingRulesEngine()
    completed = answer_reward_windows(
        engine,
        apply_whole(engine, 
            placed,
            legal_contract_completion_actions(placed, 0)[0],
        ).state,
    )

    assert [
        dict(action.arguments)["instance_id"]
        for action in engine.whole_actions(completed, 0)
    ] == ["contract:high_council_i"]

    taken = apply_whole(engine, 
        completed,
        engine.whole_actions(completed, 0)[0],
    ).state
    owner = taken.players[0]

    assert owner.completed_contract_ids == ("contract:test_jumpstart",)
    assert owner.active_contract_ids == ("contract:high_council_i",)
    assert not legal_contract_completion_actions(taken, 0)


def test_sardaukar_contract_draws_two_personal_cards() -> None:
    deck = starting_deck_instance_ids(0)[:2]
    state = _agent_contract_state(
        _imperium_instance("truthtrance"),
        "contract:sardaukar_i",
        deck=deck,
    )
    placed = _place_agent(state, "sardaukar")
    engine = UprisingRulesEngine()
    completed = answer_reward_windows(
        engine,
        apply_whole(engine, 
            placed,
            legal_contract_completion_actions(placed, 0)[0],
        ).state,
    )

    assert completed.players[0].hand == deck
    assert completed.players[0].deck == ()


def test_sardaukar_ii_contract_recalls_another_placed_agent() -> None:
    state = _agent_contract_state(
        _imperium_instance("truthtrance"),
        "contract:sardaukar_ii",
    )
    owner = replace(
        state.players[0],
        agents_available=1,
        agent_locations=("arrakeen",),
    )
    state = replace(state, players=(owner, *state.players[1:]))
    placed = _place_agent(state, "sardaukar")
    engine = UprisingRulesEngine()
    completed = answer_reward_windows(
        engine,
        apply_whole(engine, 
            placed,
            legal_contract_completion_actions(placed, 0)[0],
        ).state,
    )

    # The printed reward recalls one of your Agents, and the just-sent Agent
    # is not a valid target [Main p. 20]; with a target there is no confirm.
    assert contract_recall_targets(completed, 0) == ("arrakeen",)
    recall_actions = engine.whole_actions(completed, 0)
    assert [action.action_id for action in recall_actions] == [
        "recall_agent_for_contract"
    ]
    assert [
        dict(action.arguments)["space_id"] for action in recall_actions
    ] == ["arrakeen"]

    recalled = apply_whole(engine, completed, recall_actions[0]).state
    resolved = recalled.players[0]

    assert resolved.agents_available == 1
    assert resolved.agent_locations == ("sardaukar",)
    assert resolved.completed_contract_ids == ("contract:sardaukar_ii",)


def test_sardaukar_ii_recall_does_nothing_without_another_agent() -> None:
    # The designer's Sardaukar II ruling (OQ-057, designer-rulings-audit.md):
    # with no other Agent "the reward simply fizzles". User ruling
    # 2026-09-30 ("결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을
    # 연다"): the recall window opens anyway, offering only the confirm,
    # and the fizzle comes from that press.
    state = _agent_contract_state(
        _imperium_instance("truthtrance"),
        "contract:sardaukar_ii",
    )
    placed = _place_agent(state, "sardaukar")
    engine = UprisingRulesEngine()
    completion = apply_whole(engine, 
        placed,
        legal_contract_completion_actions(placed, 0)[0],
    )
    # The Recall Agent icon is the reward's one row, waiting on the Agent
    # turn (stage B3b, OQ-112 (4)); its press opens the recall window.
    assert completion.state.decision_stack[-1].kind == "agent_effects"
    transition = apply_whole(
        engine,
        completion.state,
        _icon_row("contract:sardaukar_ii", "recall_agent"),
    )

    frame = transition.state.decision_stack[-1]
    assert frame.kind == "contract_reward_recall"
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.prompt == "No other Agent to recall"
    assert not any(
        event.kind == "contract_recall_unavailable"
        for event in (*completion.events, *transition.events)
    )
    confirm = DomainAction(action_id="resolve_contract_without_recall", actor=0)
    assert contract_recall_targets(transition.state, 0) == ()
    assert contract_recall_targets(transition.state, 1) is None
    assert engine.whole_actions(transition.state, 0) == (confirm,)

    fizzled = apply_whole(engine, transition.state, confirm)

    assert [event.kind for event in fizzled.events] == ["contract_recall_unavailable"]
    assert fizzled.state.decision_stack[-1].kind == "agent_effects"
    assert fizzled.state.players[0].agent_locations == ("sardaukar",)
    assert fizzled.state.players[0].completed_contract_ids == (
        "contract:sardaukar_ii",
    )


def test_contract_troops_increase_combat_deployment_limit() -> None:
    state = _agent_contract_state(
        _imperium_instance("truthtrance"),
        "contract:heighliner_ii",
    )
    placed = _place_agent(state, "heighliner")
    engine = UprisingRulesEngine()
    completed = answer_reward_windows(
        engine,
        apply_whole(engine, 
            placed,
            legal_contract_completion_actions(placed, 0)[0],
        ).state,
    )
    deployment_counts = {
        dict(action.arguments)["count"]
        for action in engine.whole_actions(completed, 0)
        if action.action_id == "deploy_troops"
    }

    assert completed.players[0].troops_garrison == 5
    # Deploying nothing is now the explicit turn end (OQ-029).
    assert deployment_counts == {1, 2, 3, 4}


def test_contract_completion_actions_replay_from_the_same_state() -> None:
    initial = _agent_contract_state(
        "reserve:prepare_the_way:7",
        "contract:high_council_ii",
    )
    placement = next(
        action
        for action in legal_agent_actions(initial, 0)
        if dict(action.arguments)["space_id"] == "high_council"
    )
    steps = (
        placement,
        DomainAction(
            action_id="complete_contract",
            actor=0,
            arguments=(("instance_id", "contract:high_council_ii"),),
        ),
    )
    engine = UprisingRulesEngine()

    def play() -> GameState:
        state = initial
        for step in steps:
            if step is placement:
                # A whole placement: the Agent turn's two steps (stage B1).
                state = apply_placement(engine, state, step).state
            else:
                state = apply_whole(engine, state, step).state
        return state

    first = play()
    second = play()

    assert canonical_state_hash(first) == canonical_state_hash(second)
    assert first == second
