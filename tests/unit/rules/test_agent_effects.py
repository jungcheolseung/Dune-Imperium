"""Tests for Agent-card, Faction, and effect-frame completion."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
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
)
from dune_imperium.rules.agent_effects import (
    apply_agent_card_trash,
    legal_agent_card_trash_actions,
    resolve_agent_card_effect,
    resolve_faction_influence,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import resolve_board_effect


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
