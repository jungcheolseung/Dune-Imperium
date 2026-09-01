"""Integration coverage for the concrete Uprising rules dispatcher."""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
    ChanceResolver,
    DecisionFrame,
    GamePhase,
    GameReplay,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
    canonical_state_hash,
    replay_game,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.replay import ReplayStep
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.simulation import run_random_round


def test_agent_effect_resolution_cannot_start_a_second_agent_turn() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    first_player = decision.owner
    agent_action = next(
        action
        for action in engine.legal_actions(state, first_player)
        if action.action_id == "agent_turn"
    )

    state = engine.apply(state, agent_action).state
    effect_action_ids = {
        action.action_id for action in engine.legal_actions(state, first_player)
    }

    assert "agent_turn" not in effect_action_ids
    assert "reveal_turn" not in effect_action_ids
    assert state.players[first_player].agents_available == 1


def test_automatic_endgame_finishes_only_when_no_intrigue_is_held() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    players = tuple(
        replace(
            player,
            hand=(),
            deck=(),
            discard_pile=(),
            intrigue_cards=(),
            has_revealed=True,
        )
        for player in state.players
    )
    state = replace(
        state,
        phase=GamePhase.RECALL_OR_ENDGAME,
        players=players,
        conflict_deck=(),
        reveal_order=(0, 1, 2, 3),
        decision_stack=(),
    )

    result = _advance_automatic(RuleResult(state=state))

    assert result.state.phase is GamePhase.FINISHED
    assert tuple(event.kind for event in result.events) == (
        "endgame_started",
        "game_finished",
    )


def test_engine_opens_wild_match_then_finishes_after_player_choice() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    holder = replace(
        state.players[0],
        objective_ids=("objective_crysknife_1",),
        won_conflict_ids=("propaganda",),
    )
    players = (
        holder,
        *(
            replace(
                player,
                objective_ids=tuple(
                    card_id
                    for card_id in player.objective_ids
                    if card_id != "objective_crysknife_1"
                ),
            )
            for player in state.players[1:]
        ),
    )
    state = replace(
        state,
        phase=GamePhase.ENDGAME,
        players=players,
        reveal_order=(0, 1, 2, 3),
        current_conflict_ids=(),
        conflict_deck=(),
        unused_conflict_ids=tuple(
            conflict_id
            for conflict_id in state.unused_conflict_ids
            if conflict_id != "propaganda"
        ),
        decision_stack=(),
    )
    opened = _advance_automatic(RuleResult(state=state)).state
    assert opened.decision_stack[-1].kind == "endgame_intrigue"

    working = opened
    kinds: list[str] = []
    matched = False
    for _ in range(12):
        if working.phase is GamePhase.FINISHED:
            break
        frame = working.decision_stack[-1]
        assert isinstance(frame.decision, PlayerDecision)
        owner = frame.decision.owner
        actions = engine.legal_actions(working, owner)
        match = next(
            (a for a in actions if a.action_id == "match_endgame_wild_icon"),
            None,
        )
        step = (
            match
            if match is not None and not matched
            else next(a for a in actions if a.action_id == "pass_endgame_intrigue")
        )
        matched = matched or step is match
        result = engine.apply(working, step)
        kinds.extend(event.kind for event in result.events)
        working = result.state

    assert matched
    assert working.phase is GamePhase.FINISHED
    assert working.players[0].victory_points == state.players[0].victory_points + 1
    assert "endgame_wild_matched" in kinds
    assert kinds[-1] == "game_finished"


def test_engine_exposes_and_applies_infiltrate_agent_destination() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    player = decision.owner
    owner = state.players[player]
    dagger = next(
        card_id
        for card_id in (*owner.deck, *owner.hand, *owner.discard_pile)
        if ":dagger:" in card_id
    )
    post_id = "landsraad-assembly-hall-gather-support"
    owner = replace(
        owner,
        deck=(),
        hand=(dagger,),
        discard_pile=(),
        spies_supply=2,
        spy_post_ids=(post_id,),
    )
    opponent_id = (player + 1) % state.config.players
    opponent = replace(
        state.players[opponent_id],
        agents_available=1,
        agent_locations=("assembly_hall",),
    )
    state = replace(
        state,
        players=tuple(
            owner
            if candidate.player_id == player
            else opponent
            if candidate.player_id == opponent_id
            else candidate
            for candidate in state.players
        ),
    )

    infiltrate = next(
        action
        for action in engine.legal_actions(state, player)
        if dict(action.arguments).get("infiltrate_post_id") == post_id
    )
    transition = engine.apply(state, infiltrate)

    assert "assembly_hall" in transition.state.players[player].agent_locations
    assert transition.state.players[player].spy_post_ids == ()
    assert any(
        event.kind == "spy_recalled_for_infiltrate" for event in transition.events
    )


def test_reveal_resolution_cannot_start_another_turn() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    reveal = next(
        action
        for action in engine.legal_actions(state, decision.owner)
        if action.action_id == "reveal_turn"
    )

    state = engine.apply(state, reveal).state
    reveal_action_ids = {
        action.action_id for action in engine.legal_actions(state, decision.owner)
    }

    assert "agent_turn" not in reveal_action_ids
    assert "reveal_turn" not in reveal_action_ids
    assert "finish_reveal" in reveal_action_ids


def test_assembly_hall_is_playable_and_draws_intrigue() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    assembly_hall = next(
        action
        for action in engine.legal_actions(state, decision.owner)
        if dict(action.arguments).get("space_id") == "assembly_hall"
    )
    intrigue_card = state.intrigue_deck[0]

    state = engine.apply(state, assembly_hall).state
    resolve = engine.legal_actions(state, decision.owner)
    assert tuple(action.action_id for action in resolve) == ("resolve_board_effect",)
    state = engine.apply(state, resolve[0]).state

    assert intrigue_card in state.players[decision.owner].intrigue_cards


def test_espionage_uses_explicit_spy_choices_instead_of_generic_resolution() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    player = decision.owner
    owner = state.players[player]
    cards = (*owner.deck, *owner.hand, *owner.discard_pile)
    diplomacy = next(card for card in cards if ":diplomacy:" in card)
    drawn = next(card for card in cards if card != diplomacy)
    owner = replace(
        owner,
        resources=Resources(spice=1),
        deck=(drawn,),
        hand=(diplomacy,),
        discard_pile=(),
    )
    state = replace(
        state,
        players=tuple(
            owner if candidate.player_id == player else candidate
            for candidate in state.players
        ),
    )
    espionage = next(
        action
        for action in engine.legal_actions(state, player)
        if dict(action.arguments).get("space_id") == "espionage"
    )

    state = engine.apply(state, espionage).state
    choices = engine.legal_actions(state, player)

    assert "resolve_board_effect" not in {action.action_id for action in choices}
    assert "resolve_espionage_without_spy" in {action.action_id for action in choices}
    placement = next(
        action
        for action in choices
        if action.action_id == "resolve_espionage_place_spy"
    )
    state = engine.apply(state, placement).state

    assert drawn in state.players[player].hand
    assert state.players[player].spies_supply == 2


def test_four_seeded_random_players_finish_one_round() -> None:
    result = run_random_round(
        UprisingRulesEngine(),
        RulesetConfig(),
        game_seed=0,
        policy_seed=1000,
    )
    state = result.state

    assert state.phase is GamePhase.PLAYER_TURNS
    assert state.round_number == 2
    assert isinstance(state.decision_stack[-1].decision, PlayerDecision)
    assert all(not player.has_revealed for player in state.players)
    assert all(player.agents_available == 2 for player in state.players)
    assert all(player.combat_strength == 0 for player in state.players)
    event_kinds = {event.kind for event in state.event_log}
    assert {
        "agent_placed",
        "reveal_finished",
        "combat_cleaned_up",
        "agents_recalled",
    } <= event_kinds


def test_same_game_and_policy_seeds_reproduce_the_round() -> None:
    engine = UprisingRulesEngine()
    first = run_random_round(engine, RulesetConfig(), 7, 2007)
    second = run_random_round(engine, RulesetConfig(), 7, 2007)

    assert canonical_state_hash(first.state) == canonical_state_hash(second.state)
    assert first.replay.steps == second.replay.steps
    assert replay_game(engine, first.replay) == first.state


def test_two_rounds_replay_through_third_round_discard_shuffles() -> None:
    engine = UprisingRulesEngine()
    config = RulesetConfig()
    state = engine.reset(config, seed=11)
    resolver = ChanceResolver(seed=9011)
    steps: list[ReplayStep] = []

    for _ in range(100):
        if state.round_number == 3:
            break
        decision = engine.current_decision(state)
        step: ReplayStep
        if isinstance(decision, ChanceDecision):
            step = resolver.resolve(decision)
        elif isinstance(decision, PlayerDecision):
            actions = engine.legal_actions(state, decision.owner)
            step = next(
                action
                for action in actions
                if action.action_id in ("reveal_turn", "finish_reveal")
            )
        else:
            raise AssertionError("multi-round replay reached no decision")
        state = engine.apply(state, step).state
        steps.append(step)
    else:
        raise AssertionError("two rounds exceeded the transition limit")

    chance_steps = tuple(step for step in steps if isinstance(step, ChanceOutcome))
    assert state.phase is GamePhase.PLAYER_TURNS
    assert state.round_number == 3
    assert len(chance_steps) == 4
    assert all(player.discard_pile == () for player in state.players)

    replay = GameReplay(
        ruleset=config,
        seed=11,
        steps=tuple(steps),
        expected_state_hash=canonical_state_hash(state),
    )
    assert replay_game(engine, replay) == state


def test_every_advertised_action_stays_in_the_supported_vertical_slice() -> None:
    for game_seed in range(4):
        result = run_random_round(
            UprisingRulesEngine(),
            RulesetConfig(),
            game_seed,
            policy_seed=3000 + game_seed,
        )
        assert result.state.phase is GamePhase.PLAYER_TURNS
        assert result.state.round_number == 2


def _turn_state(hand: tuple[str, ...]) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(player_id=0, hand=hand, resources=Resources(spice=4)),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def test_engine_advertises_every_implemented_agent_card_effect() -> None:
    haven = next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if ":smuggler_s_haven:" in instance_id
    )
    state = _turn_state((haven,))

    destinations = {
        dict(action.arguments)["space_id"]
        for action in UprisingRulesEngine().legal_actions(state, 0)
        if action.action_id == "agent_turn"
    }

    # Smuggler's Haven's Agent effect is implemented, so the dispatcher must
    # advertise its placements instead of silently hiding the card.
    assert "deliver_supplies" in destinations


def test_engine_withholds_agent_actions_it_cannot_execute() -> None:
    signet_ring = next(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if ":signet_ring:" in instance_id
    )
    diplomacy = next(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if ":diplomacy:" in instance_id
    )
    state = _turn_state((signet_ring, diplomacy))

    actions = UprisingRulesEngine().legal_actions(state, 0)
    agent_actions = [action for action in actions if action.action_id == "agent_turn"]

    # Leader abilities are not implemented, so Signet Ring stays in hand.
    assert all(dict(a.arguments)["card_id"] != signet_ring for a in agent_actions)
    # Intrigue-driven board effects are not implemented, so those spaces are hidden
    # from the dispatcher even though the rules module enumerates them.
    destinations = {dict(a.arguments)["space_id"] for a in agent_actions}
    assert "dutiful_service" in destinations
    assert "secrets" not in destinations
    assert any(action.action_id == "reveal_turn" for action in actions)
