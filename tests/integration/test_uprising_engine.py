"""Integration coverage for the concrete Uprising rules dispatcher."""

from dataclasses import replace
from typing import cast

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
    ChanceResolver,
    DecisionFrame,
    DomainAction,
    GameEvent,
    GamePhase,
    GameReplay,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
    canonical_state_hash,
    replay_game,
)
from dune_imperium.core.chance import FIXED_OUTCOME_SUFFIX
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.replay import ReplayStep
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.simulation import run_random_round


def test_agent_effect_resolution_cannot_start_a_second_agent_turn() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    first_player = decision.owner
    agent_action = next(iter(executable_placements(state, first_player)))

    state = apply_placement(engine, state, agent_action).state
    effect_action_ids = {
        action.action_id for action in engine.whole_actions(state, first_player)
    }

    # An Agent turn is a card pick and a space pick (stage B1); neither step
    # is offered again inside the Agent-effect frame.
    assert "agent_turn" not in effect_action_ids
    assert "choose_agent_card" not in effect_action_ids
    assert "place_agent" not in effect_action_ids
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
        actions = engine.whole_actions(working, owner)
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
        result = apply_whole(engine, working, step)
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
        for action in executable_placements(state, player)
        if dict(action.arguments).get("infiltrate_post_id") == post_id
    )
    transition = apply_placement(engine, state, infiltrate)

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
        for action in engine.whole_actions(state, decision.owner)
        if action.action_id == "reveal_turn"
    )

    state = apply_whole(engine, state, reveal).state
    reveal_action_ids = {
        action.action_id for action in engine.whole_actions(state, decision.owner)
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
        for action in executable_placements(state, decision.owner)
        if dict(action.arguments).get("space_id") == "assembly_hall"
    )
    intrigue_card = state.intrigue_deck[0]

    state = apply_placement(engine, state, assembly_hall).state
    resolve = engine.whole_actions(state, decision.owner)
    assert tuple(action.action_id for action in resolve) == ("resolve_board_effect",)
    assert dict(resolve[0].arguments) == {"effect": "intrigue"}
    state = apply_whole(engine, state, resolve[0]).state

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
        for action in executable_placements(state, player)
        if dict(action.arguments).get("space_id") == "espionage"
    )

    state = apply_placement(engine, state, espionage).state
    choices = engine.whole_actions(state, player)

    # The Spy icon resolves only through its explicit choices; the printed
    # card draw is the space's other icon and keeps the generic action
    # (OQ-027).
    assert [
        dict(action.arguments)["effect"]
        for action in choices
        if action.action_id == "resolve_board_effect"
    ] == ["cards"]
    # With a Spy in the supply the placement is mandatory (the designer's
    # erratum to [Main p. 11], OQ-057), so skipping it is not offered.
    assert "resolve_espionage_without_spy" not in {
        action.action_id for action in choices
    }
    placement = next(
        action
        for action in choices
        if action.action_id == "resolve_espionage_place_spy"
    )
    state = apply_whole(engine, state, placement).state
    assert state.players[player].spies_supply == 2
    assert drawn not in state.players[player].hand

    draw = next(
        action
        for action in engine.whole_actions(state, player)
        if action.action_id == "resolve_board_effect"
    )
    state = apply_whole(engine, state, draw).state
    assert drawn in state.players[player].hand


def test_reaching_emperor_influence_four_owes_the_tracks_spy_inside_the_turn() -> None:
    # "When you reach 4 Influence, you earn the bonus shown on that space of
    # the track." [Main p. 7] The Emperor strip prints the Spy icon. User
    # ruling 2026-10-04 (overriding the designer ruling OQ-057 (15)): "엄연히
    # agent턴 내에 순서를 정해서 할 수 있는 의무 행동으로 보는거지" -- the
    # placement waits in the owner's turn, other actions may come first, and
    # the turn cannot end before it; with a Spy in the supply the placement
    # itself is mandatory (erratum to p. 11).
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    player = decision.owner
    owner = state.players[player]
    cards = (*owner.deck, *owner.hand, *owner.discard_pile)
    diplomacy = next(card for card in cards if ":diplomacy:" in card)
    owner = replace(
        owner,
        influence=replace(owner.influence, emperor=3),
        deck=tuple(card for card in cards if card != diplomacy),
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
    visit = next(
        action
        for action in executable_placements(state, player)
        if dict(action.arguments).get("space_id") == "dutiful_service"
    )
    state = apply_placement(engine, state, visit).state
    step = next(
        action
        for action in engine.whole_actions(state, player)
        if action.action_id == "resolve_faction_influence"
    )

    result = apply_whole(engine, state, step)
    state = result.state

    assert state.players[player].influence.emperor == 4
    assert state.players[player].troops_garrison == owner.troops_garrison
    bonus = next(
        dict(event.payload)
        for event in result.events
        if event.kind == "influence_track_bonus_gained"
    )
    assert bonus == {"faction": "emperor", "player": player, "spy": 1}
    # The Spy waits in the turn: the effect frame stays on top and offers
    # the placement beside the space's own effect, but not the turn end.
    assert [seat for seat, _ in state.pending_track_spies] == [player]
    assert state.decision_stack[-1].kind == "agent_effects"
    offered = {action.action_id for action in engine.whole_actions(state, player)}
    assert {"place_track_spy", "resolve_board_effect"} <= offered
    assert "finish_agent_turn" not in offered

    # Another action first: the space's own effect.
    board = next(
        action
        for action in engine.whole_actions(state, player)
        if action.action_id == "resolve_board_effect"
    )
    state = apply_whole(engine, state, board).state
    assert [action.action_id for action in engine.whole_actions(state, player)] == [
        "place_track_spy"
    ]

    state = apply_whole(engine, state, DomainAction("place_track_spy", player)).state

    assert state.pending_track_spies == ()
    frame = state.decision_stack[-1]
    assert frame.kind == "spy_placement"
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == player
    offered_posts = engine.whole_actions(state, player)
    assert {action.action_id for action in offered_posts} == {"place_spy_on_space"}
    assert len(offered_posts) == 13

    state = apply_whole(engine, state, offered_posts[0]).state

    assert state.players[player].spies_supply == 2
    assert state.players[player].spy_post_ids == (
        dict(offered_posts[0].arguments)["post_id"],
    )
    # Back in the turn, which may now end.
    assert state.decision_stack[-1].kind == "agent_effects"
    assert {action.action_id for action in engine.whole_actions(state, player)} == {
        "finish_agent_turn"
    }


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


def test_report_only_events_reach_the_transition_but_never_the_state() -> None:
    # combat_standing (rules/combat.py) and cards_revealed (rules/
    # reveal_turn.py) restate for the tables what the state holds: the
    # Combat's standing as the rewards begin, a Reveal's hand. They reach
    # the session log through the transition, but the state, whose
    # canonical hash every save records, stays as it was before they
    # existed, so saves written earlier still load (2026-10-08).
    engine = UprisingRulesEngine()
    assert engine.report_only_event_kinds == {"combat_standing", "cards_revealed"}
    # Policy seed 1001, not 1000: the random policy draws over the legal list,
    # which an Agent turn's two steps (stage B1) changed, and the round of
    # policy seed 1000 no longer reaches a Combat standing.
    first = run_random_round(engine, RulesetConfig(), 0, 1001)
    state = engine.reset(RulesetConfig(), 0)
    reported: list[GameEvent] = []
    for step in first.replay.steps:
        before = state
        transition = apply_whole(engine, state, step)
        shown = [
            event
            for event in transition.events
            if event.kind in engine.report_only_event_kinds
        ]
        for event in shown:
            if event.kind == "cards_revealed":
                payload = dict(event.payload)
                player = before.players[cast(int, payload["player"])]
                assert payload["card_ids"] == player.hand
        reported.extend(shown)
        state = transition.state
        assert not any(
            event.kind in engine.report_only_event_kinds for event in state.event_log
        )

    assert {event.kind for event in reported} == {"combat_standing", "cards_revealed"}
    assert state == first.state


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
            actions = engine.whole_actions(state, decision.owner)
            step = next(
                action
                for action in actions
                if action.action_id in ("reveal_turn", "finish_reveal")
            )
        else:
            raise AssertionError("multi-round replay reached no decision")
        state = apply_whole(engine, state, step).state
        steps.append(step)
    else:
        raise AssertionError("two rounds exceeded the transition limit")

    chance_steps = tuple(step for step in steps if isinstance(step, ChanceOutcome))
    pauses = tuple(
        step for step in chance_steps if step.decision_id.endswith(FIXED_OUTCOME_SUFFIX)
    )
    assert state.phase is GamePhase.PLAYER_TURNS
    assert state.round_number == 3
    # Four discard reshuffles, and the pause before rounds 2 and 3
    # (rules/pauses.py), which the resolver answers without a draw.
    assert len(chance_steps) - len(pauses) == 4
    assert [step.decision_id for step in pauses] == [
        "round:2:round_start:pause",
        "round:3:round_start:pause",
    ]
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

    engine = UprisingRulesEngine()
    picks = [
        action
        for action in engine.whole_actions(state, 0)
        if action.action_id == "choose_agent_card"
    ]
    # Smuggler's Haven's Agent effect is implemented, so the dispatcher must
    # advertise the card (its card pick) instead of silently hiding it, and
    # its placements (the space picks that follow).
    assert [dict(pick.arguments)["card_id"] for pick in picks] == [haven]
    picked = apply_whole(engine, state, picks[0]).state
    destinations = {
        dict(action.arguments)["space_id"]
        for action in engine.whole_actions(picked, 0)
        if action.action_id == "place_agent"
    }
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

    engine = UprisingRulesEngine()
    actions = engine.whole_actions(state, 0)
    picks = [action for action in actions if action.action_id == "choose_agent_card"]

    # Leader abilities are not implemented, so Signet Ring stays in hand: its
    # card is not offered (the Agent turn's card picks, stage B1).
    assert all(dict(a.arguments)["card_id"] != signet_ring for a in picks)
    # Every board-space effect is implemented, so Diplomacy's Faction-icon
    # destinations are all advertised even though Signet Ring above is not.
    (diplomacy_pick,) = [
        pick for pick in picks if dict(pick.arguments)["card_id"] == diplomacy
    ]
    picked = apply_whole(engine, state, diplomacy_pick).state
    destinations = {
        dict(a.arguments)["space_id"]
        for a in engine.whole_actions(picked, 0)
        if a.action_id == "place_agent"
    }
    assert "dutiful_service" in destinations
    assert "secrets" in destinations
    assert any(action.action_id == "reveal_turn" for action in actions)
