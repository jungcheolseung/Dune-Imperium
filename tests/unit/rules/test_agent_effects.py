"""Tests for Agent-card, Faction, and effect-frame completion."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.agent_effects import (
    apply_agent_card_influence,
    apply_agent_card_payment,
    apply_agent_card_spy_action,
    apply_agent_card_trash,
    legal_agent_card_influence_actions,
    legal_agent_card_payment_actions,
    legal_agent_card_spy_actions,
    legal_agent_card_trash_actions,
    resolve_agent_card_effect,
    resolve_faction_influence,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import resolve_board_effect
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.spies import (
    apply_gather_intelligence_action,
    legal_gather_intelligence_actions,
)


def _instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )


def _imperium_instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if f":{card_id}:" in instance_id
    )


def _state(card_id: str, influence: Influence | None = None) -> GameState:
    card = _instance(card_id)
    starting_influence = influence or Influence()
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(player_id=0, hand=(card,), influence=starting_influence),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _action_to(state: GameState, space_id: str) -> DomainAction:
    return next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )


def test_seek_allies_trashes_itself_from_in_play() -> None:
    state = _state("seek_allies")
    card = state.players[0].hand[0]
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    resolved = resolve_agent_card_effect(placed).state

    assert card not in resolved.players[0].in_play
    assert resolved.players[0].trashed == (card,)
    assert dict(resolved.decision_stack[-1].context)["pending_agent_effect"] is False


def test_faction_influence_reaches_friendship_and_awards_vp() -> None:
    state = _state("diplomacy", Influence(emperor=1))
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    resolved = resolve_faction_influence(placed).state

    assert resolved.players[0].influence.emperor == 2
    assert resolved.players[0].victory_points == 2


def test_finishing_all_effect_groups_opens_clockwise_players_turn() -> None:
    state = _state("seek_allies")
    state = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    state = resolve_agent_card_effect(state).state
    state = resolve_faction_influence(state).state
    state = resolve_board_effect(state).state

    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 1
    assert state.decision_stack[-1].context == (("round", 1), ("turn_owner", 1))


def test_influence_four_grants_emperor_bonus_and_alliance() -> None:
    state = _state("diplomacy", Influence(emperor=3))
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    resolved = resolve_faction_influence(placed).state

    owner = resolved.players[0]
    assert owner.influence.emperor == 4
    assert owner.troops_supply == 7
    assert owner.troops_garrison == 5
    assert owner.alliance_faction_ids == ("emperor",)
    assert owner.victory_points == 2


def test_rising_above_an_opponent_transfers_the_alliance_vp() -> None:
    state = _state("diplomacy", Influence(emperor=4))
    challenger = replace(state.players[0], victory_points=2)
    holder = replace(
        state.players[1],
        influence=Influence(emperor=4),
        alliance_faction_ids=("emperor",),
        victory_points=2,
    )
    state = replace(state, players=(challenger, holder, *state.players[2:]))
    placed = apply_agent_action(state, _action_to(state, "dutiful_service")).state

    resolved = resolve_faction_influence(placed).state

    assert resolved.players[0].influence.emperor == 5
    assert resolved.players[0].alliance_faction_ids == ("emperor",)
    assert resolved.players[0].victory_points == 3
    assert resolved.players[1].alliance_faction_ids == ()
    assert resolved.players[1].victory_points == 1


def test_signet_effect_waits_for_leader_implementations() -> None:
    state = _state("signet_ring")
    placed = apply_agent_action(state, _action_to(state, "spice_refinery")).state

    with pytest.raises(NotImplementedError, match="signet_ring"):
        resolve_agent_card_effect(placed)


def test_prepare_the_way_draws_with_two_bene_gesserit_influence() -> None:
    prepare = "reserve:prepare_the_way:7"
    drawn = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        hand=(prepare,),
        deck=(drawn,),
        influence=Influence(bene_gesserit=2),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    resolved = resolve_agent_card_effect(placed)

    assert resolved.state.players[0].hand == (drawn,)
    assert resolved.state.players[0].deck == ()
    assert resolved.events[0].kind == "agent_card_effect_resolved"


def test_prepare_the_way_has_no_agent_effect_below_required_influence() -> None:
    prepare = "reserve:prepare_the_way:7"
    owner = PlayerState(
        player_id=0,
        hand=(prepare,),
        influence=Influence(bene_gesserit=1),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_maula_pistol_agent_effect_draws_one_personal_card() -> None:
    maula = _imperium_instance("maula_pistol")
    drawn = _instance("dagger")
    owner = PlayerState(player_id=0, hand=(maula,), deck=(drawn,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    resolved = resolve_agent_card_effect(placed)

    assert resolved.state.players[0].hand == (drawn,)
    assert resolved.state.players[0].deck == ()
    assert resolved.events[0].kind == "agent_card_effect_resolved"


def test_hidden_missive_recruits_and_draws_with_required_influence() -> None:
    hidden_missive = _imperium_instance("hidden_missive")
    drawn = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        hand=(hidden_missive,),
        deck=(drawn,),
        influence=Influence(bene_gesserit=2),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "gather_support")).state

    resolved = resolve_agent_card_effect(placed)
    context = dict(resolved.state.decision_stack[-1].context)

    assert resolved.state.players[0].troops_supply == 8
    assert resolved.state.players[0].troops_garrison == 4
    assert resolved.state.players[0].hand == (drawn,)
    assert resolved.state.players[0].deck == ()
    assert context["troops_recruited"] == 1
    assert resolved.events[0].kind == "agent_card_effect_resolved"


def test_hidden_missive_has_no_agent_effect_below_required_influence() -> None:
    hidden_missive = _imperium_instance("hidden_missive")
    owner = PlayerState(
        player_id=0,
        hand=(hidden_missive,),
        influence=Influence(bene_gesserit=1),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    placed = apply_agent_action(state, _action_to(state, "gather_support")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_desert_survival_may_trash_from_any_eligible_zone() -> None:
    desert_survival = _imperium_instance("desert_survival")
    hand_card = _instance("dagger")
    discarded_card = _instance("convincing_argument")
    owner = PlayerState(
        player_id=0,
        hand=(desert_survival, hand_card),
        discard_pile=(discarded_card,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state

    actions = legal_agent_card_trash_actions(placed, 0)
    trash_ids = {
        dict(action.arguments)["card_id"]
        for action in actions
        if action.action_id == "trash_agent_card"
    }

    assert {hand_card, discarded_card, desert_survival} == trash_ids

    action = next(
        action
        for action in actions
        if dict(action.arguments).get("card_id") == discarded_card
    )
    result = apply_agent_card_trash(placed, action)

    assert result.state.players[0].discard_pile == ()
    assert result.state.players[0].trashed == (discarded_card,)
    assert result.state.players[0].in_play == (desert_survival,)
    assert result.events[0].kind == "card_trashed"
    context = dict(result.state.decision_stack[-1].context)
    assert context["pending_agent_effect"] is False


def test_desert_survival_trash_may_be_declined() -> None:
    desert_survival = _imperium_instance("desert_survival")
    owner = PlayerState(player_id=0, hand=(desert_survival,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state
    action = next(
        action
        for action in legal_agent_card_trash_actions(placed, 0)
        if action.action_id == "decline_agent_card_trash"
    )

    result = apply_agent_card_trash(placed, action)

    assert result.state.players[0].in_play == (desert_survival,)
    assert result.state.players[0].trashed == ()
    assert result.events[0].kind == "agent_card_trash_declined"


def test_smugglers_harvester_gains_spice_at_a_maker_space() -> None:
    harvester = _imperium_instance("smuggler_s_harvester")
    owner = PlayerState(player_id=0, hand=(harvester,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "hagga_basin")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.spice == 1
    assert result.events[0].kind == "agent_card_effect_resolved"


def test_smugglers_harvester_has_no_agent_effect_away_from_maker_spaces() -> None:
    harvester = _imperium_instance("smuggler_s_harvester")
    owner = PlayerState(player_id=0, hand=(harvester,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_fedaykin_stilltent_recruits_a_deployable_troop_at_a_maker_space() -> None:
    stilltent = _imperium_instance("fedaykin_stilltent")
    owner = PlayerState(player_id=0, hand=(stilltent,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "imperial_basin")).state

    result = resolve_agent_card_effect(placed)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].troops_supply == 8
    assert result.state.players[0].troops_garrison == 4
    assert context["troops_recruited"] == 1


def test_fedaykin_stilltent_has_no_agent_effect_away_from_maker_spaces() -> None:
    stilltent = _imperium_instance("fedaykin_stilltent")
    owner = PlayerState(player_id=0, hand=(stilltent,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    placed = apply_agent_action(state, _action_to(state, "accept_contract")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_northern_watermaster_gains_water_on_its_agent_turn() -> None:
    watermaster = _imperium_instance("northern_watermaster")
    owner = PlayerState(player_id=0, hand=(watermaster,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.water == 2
    assert result.events[0].kind == "agent_card_effect_resolved"


def test_maker_keeper_gains_each_reward_for_its_matching_influence() -> None:
    maker_keeper = _imperium_instance("maker_keeper")
    owner = PlayerState(
        player_id=0,
        hand=(maker_keeper,),
        influence=Influence(bene_gesserit=2, fremen=2),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.spice == 1
    assert result.state.players[0].resources.water == 2


@pytest.mark.parametrize(
    ("influence", "expected_spice", "expected_water"),
    (
        (Influence(bene_gesserit=2), 0, 2),
        (Influence(fremen=2), 1, 1),
    ),
)
def test_maker_keeper_rewards_are_independent(
    influence: Influence,
    expected_spice: int,
    expected_water: int,
) -> None:
    maker_keeper = _imperium_instance("maker_keeper")
    owner = PlayerState(
        player_id=0,
        hand=(maker_keeper,),
        influence=influence,
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.spice == expected_spice
    assert result.state.players[0].resources.water == expected_water


def test_maker_keeper_has_no_agent_effect_without_matching_influence() -> None:
    maker_keeper = _imperium_instance("maker_keeper")
    owner = PlayerState(player_id=0, hand=(maker_keeper,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_southern_elders_recruits_with_bene_gesserit_bond() -> None:
    southern_elders = _imperium_instance("southern_elders")
    truthtrance = _imperium_instance("truthtrance")
    owner = PlayerState(
        player_id=0,
        hand=(southern_elders,),
        in_play=(truthtrance,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "secrets")).state

    result = resolve_agent_card_effect(placed)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].troops_supply == 7
    assert result.state.players[0].troops_garrison == 5
    assert context["troops_recruited"] == 2


def test_southern_elders_has_no_agent_effect_without_bene_gesserit_bond() -> None:
    southern_elders = _imperium_instance("southern_elders")
    owner = PlayerState(player_id=0, hand=(southern_elders,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    placed = apply_agent_action(state, _action_to(state, "secrets")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_weirding_woman_returns_to_hand_with_bene_gesserit_bond() -> None:
    weirding_woman = _imperium_instance("weirding_woman")
    truthtrance = _imperium_instance("truthtrance")
    owner = PlayerState(
        player_id=0,
        hand=(weirding_woman,),
        in_play=(truthtrance,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].hand == (weirding_woman,)
    assert result.state.players[0].in_play == (truthtrance,)


def test_weirding_woman_has_no_agent_effect_without_bene_gesserit_bond() -> None:
    weirding_woman = _imperium_instance("weirding_woman")
    owner = PlayerState(player_id=0, hand=(weirding_woman,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_ecological_testing_station_may_pay_water_to_draw_two() -> None:
    station = _imperium_instance("ecological_testing_station")
    first = _instance("dagger")
    second = _instance("convincing_argument")
    owner = PlayerState(
        player_id=0,
        hand=(station,),
        deck=(first, second),
        resources=Resources(water=2),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "fremkit")).state
    action = next(
        action
        for action in legal_agent_card_payment_actions(placed, 0)
        if action.action_id == "pay_agent_card_water"
    )

    result = apply_agent_card_payment(placed, action)

    assert result.state.players[0].resources.water == 0
    assert result.state.players[0].hand == (first, second)
    assert result.state.players[0].deck == ()
    assert result.events[0].kind == "agent_card_payment_resolved"


def test_ecological_testing_station_payment_may_be_declined() -> None:
    station = _imperium_instance("ecological_testing_station")
    owner = PlayerState(
        player_id=0,
        hand=(station,),
        resources=Resources(water=2),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "fremkit")).state
    action = next(
        action
        for action in legal_agent_card_payment_actions(placed, 0)
        if action.action_id == "decline_agent_card_payment"
    )

    result = apply_agent_card_payment(placed, action)

    assert result.state.players[0].resources.water == 2
    assert result.events[0].kind == "agent_card_payment_declined"


def test_ecological_testing_station_has_no_payment_without_two_water() -> None:
    station = _imperium_instance("ecological_testing_station")
    owner = PlayerState(player_id=0, hand=(station,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    placed = apply_agent_action(state, _action_to(state, "fremkit")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_paracompass_gains_two_solari_on_its_agent_turn() -> None:
    paracompass = _imperium_instance("paracompass")
    owner = PlayerState(player_id=0, hand=(paracompass,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.solari == 2


def test_overthrow_gains_extra_influence_with_the_visited_faction() -> None:
    overthrow = _imperium_instance("overthrow")
    owner = PlayerState(player_id=0, hand=(overthrow,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "secrets")).state

    result = resolve_agent_card_effect(placed)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].influence.bene_gesserit == 1
    assert context["pending_faction_influence"] is True


def test_bene_gesserit_operative_places_a_spy_on_an_empty_post() -> None:
    operative = _imperium_instance("bene_gesserit_operative")
    owner = PlayerState(player_id=0, hand=(operative,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed_agent = apply_agent_action(state, _action_to(state, "secrets")).state
    engine = UprisingRulesEngine()
    choices = engine.legal_actions(placed_agent, 0)

    result = engine.apply(placed_agent, choices[0])
    post_id = dict(choices[0].arguments)["post_id"]

    assert result.state.players[0].spies_supply == 2
    assert result.state.players[0].spy_post_ids == (post_id,)
    assert result.events[0].kind == "spy_placed"
    assert (
        dict(result.state.decision_stack[-1].context)["pending_agent_effect"] is False
    )


def test_bene_gesserit_operative_recalls_before_placing_when_supply_is_empty() -> None:
    operative = _imperium_instance("bene_gesserit_operative")
    posts = tuple(post.post_id for post in OBSERVATION_POSTS[:3])
    owner = PlayerState(
        player_id=0,
        hand=(operative,),
        spies_supply=0,
        spy_post_ids=posts,
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed_agent = apply_agent_action(state, _action_to(state, "secrets")).state
    recall_action = legal_agent_card_spy_actions(placed_agent, 0)[0]

    recalled = apply_agent_card_spy_action(placed_agent, recall_action)
    recalled_post = dict(recall_action.arguments)["post_id"]
    placement = next(
        action
        for action in legal_agent_card_spy_actions(recalled.state, 0)
        if dict(action.arguments)["post_id"] == recalled_post
    )
    replaced = apply_agent_card_spy_action(recalled.state, placement)

    assert recalled.events[0].kind == "spy_recalled"
    assert replaced.state.players[0].spies_supply == 0
    assert set(replaced.state.players[0].spy_post_ids) == set(posts)


def test_reliable_informant_limits_spy_placement_to_three_faction_posts() -> None:
    informant = _imperium_instance("reliable_informant")
    owner = PlayerState(player_id=0, hand=(informant,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed_agent = apply_agent_action(
        state,
        _action_to(state, "deliver_supplies"),
    ).state

    post_ids = {
        dict(action.arguments)["post_id"]
        for action in legal_agent_card_spy_actions(placed_agent, 0)
    }

    assert post_ids == {
        "emperor-sardaukar-dutiful-service",
        "spacing-guild-heighliner-deliver-supplies",
        "bene-gesserit-espionage-secrets",
    }


def test_reliable_informant_can_only_recall_a_spy_that_opens_a_target_post() -> None:
    informant = _imperium_instance("reliable_informant")
    target_posts = (
        "emperor-sardaukar-dutiful-service",
        "spacing-guild-heighliner-deliver-supplies",
        "bene-gesserit-espionage-secrets",
    )
    owner = PlayerState(
        player_id=0,
        hand=(informant,),
        spies_supply=0,
        spy_post_ids=(target_posts[0], "arrakis-hagga-basin", "arrakis-deep-desert"),
    )
    opponents = (
        PlayerState(player_id=1, spies_supply=2, spy_post_ids=(target_posts[1],)),
        PlayerState(player_id=2, spies_supply=2, spy_post_ids=(target_posts[2],)),
        PlayerState(player_id=3),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *opponents),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed_agent = apply_agent_action(
        state,
        _action_to(state, "deliver_supplies"),
    ).state

    actions = legal_agent_card_spy_actions(placed_agent, 0)

    assert tuple(dict(action.arguments)["post_id"] for action in actions) == (
        target_posts[0],
    )


def test_reliable_informant_finishes_when_every_target_post_is_unavailable() -> None:
    informant = _imperium_instance("reliable_informant")
    target_posts = (
        "emperor-sardaukar-dutiful-service",
        "spacing-guild-heighliner-deliver-supplies",
        "bene-gesserit-espionage-secrets",
    )
    owner = PlayerState(player_id=0, hand=(informant,))
    opponents = tuple(
        PlayerState(player_id=seat, spies_supply=2, spy_post_ids=(post_id,))
        for seat, post_id in enumerate(target_posts, start=1)
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *opponents),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed_agent = apply_agent_action(
        state,
        _action_to(state, "deliver_supplies"),
    ).state
    engine = UprisingRulesEngine()
    unavailable = next(
        action
        for action in engine.legal_actions(placed_agent, 0)
        if action.action_id == "resolve_agent_card_effect"
    )

    result = engine.apply(placed_agent, unavailable)

    assert result.events[0].kind == "agent_card_effect_unavailable"
    assert (
        dict(result.state.decision_stack[-1].context)["pending_agent_effect"] is False
    )


def test_strike_fleet_recruits_three_after_gathering_intelligence() -> None:
    strike_fleet = _imperium_instance("strike_fleet")
    drawn = _instance("dagger")
    post_id = "arrakis-spice-refinery-arrakeen"
    owner = PlayerState(
        player_id=0,
        hand=(strike_fleet,),
        deck=(drawn,),
        spies_supply=2,
        spy_post_ids=(post_id,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed_agent = apply_agent_action(state, _action_to(state, "arrakeen")).state
    gather = next(
        action
        for action in legal_gather_intelligence_actions(placed_agent, 0)
        if action.action_id == "gather_intelligence"
    )

    gathered = apply_gather_intelligence_action(placed_agent, gather)
    result = resolve_agent_card_effect(gathered.state)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].spy_post_ids == ()
    assert result.state.players[0].hand == (drawn,)
    assert result.state.players[0].troops_supply == 6
    assert result.state.players[0].troops_garrison == 6
    assert context["troops_recruited"] == 3


def test_imperial_spymaster_draws_intrigue_after_gathering_intelligence() -> None:
    spymaster = _imperium_instance("imperial_spymaster")
    drawn = _instance("dagger")
    post_id = "arrakis-spice-refinery-arrakeen"
    owner = PlayerState(
        player_id=0,
        hand=(spymaster,),
        deck=(drawn,),
        spies_supply=2,
        spy_post_ids=(post_id,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=("intrigue:test:0",),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed_agent = apply_agent_action(state, _action_to(state, "arrakeen")).state
    gather = next(
        action
        for action in legal_gather_intelligence_actions(placed_agent, 0)
        if action.action_id == "gather_intelligence"
    )

    gathered = apply_gather_intelligence_action(placed_agent, gather)
    result = resolve_agent_card_effect(gathered.state)

    assert result.state.players[0].intrigue_cards == ("intrigue:test:0",)
    assert result.state.intrigue_deck == ()
    assert tuple(event.kind for event in result.events) == (
        "agent_card_effect_resolved",
        "intrigue_card_drawn",
    )


def test_in_high_places_gains_water_with_bene_gesserit_bond() -> None:
    in_high_places = _imperium_instance("in_high_places")
    truthtrance = _imperium_instance("truthtrance")
    owner = PlayerState(
        player_id=0,
        hand=(in_high_places,),
        in_play=(truthtrance,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "secrets")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.water == 2


def test_rebel_supplier_recruits_two_after_gathering_intelligence() -> None:
    supplier = _imperium_instance("rebel_supplier")
    drawn = _instance("dagger")
    post_id = "arrakis-spice-refinery-arrakeen"
    owner = PlayerState(
        player_id=0,
        hand=(supplier,),
        deck=(drawn,),
        spies_supply=2,
        spy_post_ids=(post_id,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed_agent = apply_agent_action(state, _action_to(state, "arrakeen")).state
    gather = next(
        action
        for action in legal_gather_intelligence_actions(placed_agent, 0)
        if action.action_id == "gather_intelligence"
    )

    gathered = apply_gather_intelligence_action(placed_agent, gather)
    result = resolve_agent_card_effect(gathered.state)

    assert result.state.players[0].troops_supply == 7
    assert result.state.players[0].troops_garrison == 5
    assert dict(result.state.decision_stack[-1].context)["troops_recruited"] == 2


def test_dangerous_rhetoric_trashes_itself_for_chosen_influence() -> None:
    rhetoric = _imperium_instance("dangerous_rhetoric")
    owner = PlayerState(player_id=0, hand=(rhetoric,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "assembly_hall")).state
    choices = legal_agent_card_influence_actions(placed, 0)
    action = next(
        action
        for action in choices
        if dict(action.arguments)["faction"] == "fremen"
    )

    result = apply_agent_card_influence(placed, action)
    resolved_owner = result.state.players[0]

    assert len(choices) == 4
    assert rhetoric not in resolved_owner.in_play
    assert resolved_owner.trashed == (rhetoric,)
    assert resolved_owner.influence.fremen == 1
    assert dict(result.state.decision_stack[-1].context)[
        "pending_agent_effect"
    ] is False
    assert tuple(event.kind for event in result.events) == (
        "card_trashed",
        "influence_gained",
    )


def test_public_spectacle_gains_chosen_influence_after_spy_recall() -> None:
    spectacle = _imperium_instance("public_spectacle")
    drawn = _instance("dagger")
    post_id = "arrakis-spice-refinery-arrakeen"
    owner = PlayerState(
        player_id=0,
        hand=(spectacle,),
        deck=(drawn,),
        spies_supply=2,
        spy_post_ids=(post_id,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    gather = next(
        action
        for action in legal_gather_intelligence_actions(placed, 0)
        if action.action_id == "gather_intelligence"
    )
    gathered = apply_gather_intelligence_action(placed, gather).state
    engine = UprisingRulesEngine()
    choice = next(
        action
        for action in engine.legal_actions(gathered, 0)
        if dict(action.arguments).get("faction") == "spacing_guild"
    )

    result = engine.apply(gathered, choice)

    assert result.state.players[0].influence.spacing_guild == 1
    assert result.state.players[0].in_play == (spectacle,)
    assert result.events[0].kind == "influence_gained"


def test_public_spectacle_influence_is_unavailable_without_spy_recall() -> None:
    spectacle = _imperium_instance("public_spectacle")
    post_id = "arrakis-spice-refinery-arrakeen"
    owner = PlayerState(
        player_id=0,
        hand=(spectacle,),
        spies_supply=2,
        spy_post_ids=(post_id,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].influence == Influence()
    assert result.events[0].kind == "agent_card_effect_unavailable"


@pytest.mark.parametrize(
    ("influence", "expected_solari", "expected_spice"),
    (
        (Influence(emperor=2), 2, 0),
        (Influence(spacing_guild=2), 0, 1),
        (Influence(emperor=2, spacing_guild=2), 2, 1),
    ),
)
def test_wheels_within_wheels_rewards_are_independent(
    influence: Influence,
    expected_solari: int,
    expected_spice: int,
) -> None:
    wheels = _imperium_instance("wheels_within_wheels")
    owner = PlayerState(
        player_id=0,
        hand=(wheels,),
        influence=influence,
        spies_supply=2,
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].resources.solari == expected_solari
    assert result.state.players[0].resources.spice == expected_spice


def test_wheels_within_wheels_has_no_agent_effect_below_both_thresholds() -> None:
    wheels = _imperium_instance("wheels_within_wheels")
    owner = PlayerState(
        player_id=0,
        hand=(wheels,),
        spies_supply=2,
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_stilgar_recruits_two_deployable_troops() -> None:
    stilgar = _imperium_instance("stilgar_the_devoted")
    owner = PlayerState(player_id=0, hand=(stilgar,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].troops_supply == 7
    assert result.state.players[0].troops_garrison == 5
    assert dict(result.state.decision_stack[-1].context)["troops_recruited"] == 2


def test_leadership_draws_one_card_per_sandworm_in_conflict() -> None:
    leadership = _imperium_instance("leadership")
    first = _instance("dagger")
    second = _instance("convincing_argument")
    owner = PlayerState(
        player_id=0,
        hand=(leadership,),
        deck=(first, second),
        sandworms_conflict=2,
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "hagga_basin")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].hand == (first, second)
    assert result.state.players[0].deck == ()
    assert tuple(event.kind for event in result.events) == (
        "agent_card_effect_resolved",
    )


def test_leadership_has_no_agent_effect_without_a_sandworm() -> None:
    leadership = _imperium_instance("leadership")
    owner = PlayerState(player_id=0, hand=(leadership,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    placed = apply_agent_action(state, _action_to(state, "hagga_basin")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False


def test_shishakli_may_trash_a_personal_card_to_draw_one() -> None:
    shishakli = _imperium_instance("shishakli")
    trashed_card = _instance("dagger")
    drawn_card = _instance("convincing_argument")
    owner = PlayerState(
        player_id=0,
        hand=(shishakli, trashed_card),
        deck=(drawn_card,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    action = next(
        action
        for action in legal_agent_card_trash_actions(placed, 0)
        if dict(action.arguments).get("card_id") == trashed_card
    )

    result = apply_agent_card_trash(placed, action)

    assert result.state.players[0].trashed == (trashed_card,)
    assert result.state.players[0].hand == (drawn_card,)
    assert result.state.players[0].deck == ()
    assert result.events[0].kind == "card_trashed"


def test_shishakli_trash_draw_may_be_declined() -> None:
    shishakli = _imperium_instance("shishakli")
    drawn_card = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        hand=(shishakli,),
        deck=(drawn_card,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    decline = next(
        action
        for action in legal_agent_card_trash_actions(placed, 0)
        if action.action_id == "decline_agent_card_trash"
    )

    result = apply_agent_card_trash(placed, decline)

    assert result.state.players[0].hand == ()
    assert result.state.players[0].deck == (drawn_card,)
    assert result.state.players[0].trashed == ()


def test_tread_in_darkness_may_trash_and_draw_with_bene_gesserit_bond() -> None:
    tread = _imperium_instance("tread_in_darkness")
    bond_card = _imperium_instance("truthtrance")
    trashed_card = _instance("dagger")
    drawn_card = _instance("convincing_argument")
    owner = PlayerState(
        player_id=0,
        hand=(tread, trashed_card),
        deck=(drawn_card,),
        in_play=(bond_card,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state
    action = next(
        action
        for action in legal_agent_card_trash_actions(placed, 0)
        if dict(action.arguments).get("card_id") == trashed_card
    )

    result = apply_agent_card_trash(placed, action)

    assert result.state.players[0].trashed == (trashed_card,)
    assert result.state.players[0].hand == (drawn_card,)
    assert result.state.players[0].in_play == (bond_card, tread)


def test_tread_in_darkness_has_no_agent_effect_without_bond() -> None:
    tread = _imperium_instance("tread_in_darkness")
    owner = PlayerState(player_id=0, hand=(tread,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )

    placed = apply_agent_action(state, _action_to(state, "arrakeen")).state

    assert dict(placed.decision_stack[-1].context)["pending_agent_effect"] is False
