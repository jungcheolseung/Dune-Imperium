"""Tests for automatic top-level phase transitions."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    canonical_state_hash,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.phases import (
    apply_control_defense_action,
    apply_round_start_reshuffle,
    begin_round,
    draw_round_hands,
    legal_control_defense_actions,
    prepare_round_start,
    resolve_makers,
    resolve_recall_or_endgame,
)
from dune_imperium.rules.setup import create_initial_state

SELECTED_LEADERS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)


def _setup_state(seed: int = 71) -> GameState:
    return create_initial_state(
        RulesetConfig(),
        seed=seed,
        leader_ids=SELECTED_LEADERS,
    ).state


def test_round_start_reveals_conflict_draws_five_and_opens_first_turn() -> None:
    state = replace(_setup_state(), reveal_order=(1, 3, 0, 2))
    first_conflict = state.conflict_deck[0]
    original_decks = tuple(player.deck for player in state.players)

    result = begin_round(state)
    started = result.state

    assert started.phase is GamePhase.PLAYER_TURNS
    assert started.round_number == 1
    assert started.reveal_order == ()
    assert started.current_conflict_ids == (first_conflict,)
    assert started.conflict_deck == state.conflict_deck[1:]
    for player, original_deck in zip(started.players, original_decks, strict=True):
        assert player.hand == original_deck[:5]
        assert player.deck == original_deck[5:]

    decision = started.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == state.first_player


def test_round_start_forgets_the_spy_recalls_of_the_previous_round() -> None:
    # "If you recalled a Spy this turn:" [Imperial Spymaster card] reads the
    # seat's per-turn recall count (OQ-044 (d)). The round's first turn opens
    # without the per-turn reset, so a recall made on a seat's last Reveal
    # turn must be cleared at Round Start, or it would reach the next turn.
    state = _setup_state()
    recalled = replace(state.players[state.first_player or 0], spies_recalled_turn=1)
    state = replace(
        state,
        players=tuple(
            recalled if player.player_id == recalled.player_id else player
            for player in state.players
        ),
    )

    started = begin_round(state).state

    assert all(player.spies_recalled_turn == 0 for player in started.players)


def test_round_start_adds_five_cards_instead_of_refilling_hand_to_five() -> None:
    state = _setup_state()
    first = replace(state.players[0], hand=("retained_card",))
    state = replace(state, players=(first, *state.players[1:]))

    started = begin_round(state).state

    assert len(started.players[0].hand) == 6
    assert started.players[0].hand[0] == "retained_card"


def test_round_start_emits_public_conflict_and_draw_count_events() -> None:
    state = _setup_state()

    events = begin_round(state).events

    assert len(events) == 5
    assert events[0].kind == "conflict_revealed"
    assert events[0].visible_to is None
    # Draw counts are public (OQ-010: zone sizes are visible at the table)
    # and the payload never names the drawn cards.
    assert all(event.kind == "cards_drawn" for event in events[1:])
    assert all(event.visible_to is None for event in events[1:])
    assert [dict(event.payload)["player"] for event in events[1:]] == [0, 1, 2, 3]
    assert all("card_id" not in dict(event.payload) for event in events[1:])


def _controlled_round_start(
    *,
    troops_supply: int = 9,
    config: RulesetConfig | None = None,
    twisted_deck: tuple[str, ...] = (),
) -> GameState:
    players = tuple(
        PlayerState(
            player_id=player,
            deck=tuple(f"player:{player}:card:{index}" for index in range(5)),
            troops_supply=troops_supply if player == 2 else 9,
            troops_garrison=12 - troops_supply if player == 2 else 3,
            control_space_ids=("arrakeen",) if player == 2 else (),
            twisted_deck=twisted_deck if player == 2 else (),
        )
        for player in range(4)
    )
    return GameState(
        config=RulesetConfig() if config is None else config,
        seed=1,
        phase=GamePhase.ROUND_START,
        first_player=0,
        players=players,
        conflict_deck=("siege_of_arrakeen",),
    )


def test_controlled_conflict_opens_defense_before_first_turn() -> None:
    state = begin_round(_controlled_round_start()).state
    decision = state.decision_stack[-1].decision

    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 2
    assert tuple(
        action.action_id for action in legal_control_defense_actions(state, 2)
    ) == ("decline_control_defense", "deploy_control_defense")


def test_control_defense_deploys_one_troop_then_opens_first_turn() -> None:
    state = begin_round(_controlled_round_start()).state
    deploy = legal_control_defense_actions(state, 2)[1]

    result = apply_control_defense_action(state, deploy)
    owner = result.state.players[2]
    decision = result.state.decision_stack[-1].decision

    assert owner.troops_supply == 8
    assert owner.troops_conflict == 1
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 0
    assert result.events[0].kind == "control_defense_deployed"


def test_control_defense_can_be_declined_and_skips_when_supply_is_empty() -> None:
    state = begin_round(_controlled_round_start()).state
    decline = legal_control_defense_actions(state, 2)[0]

    declined = apply_control_defense_action(state, decline)
    decision = declined.state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 0
    assert declined.state.players[2].troops_conflict == 0

    no_supply = begin_round(_controlled_round_start(troops_supply=0)).state
    no_supply_decision = no_supply.decision_stack[-1].decision
    assert isinstance(no_supply_decision, PlayerDecision)
    assert no_supply_decision.owner == 0


# Round Start order. "Each round begins by revealing a new Conflict card ...
# Next, each player draws five cards from their own deck, forming their hand
# for the round." [Main p. 8]. "When a Conflict card is revealed for a space
# that you already control, you receive a defensive bonus: you may deploy one
# troop from your supply to the Conflict." [Main p. 10] [Main p. 20]. The
# defense answers the reveal, so it sits between the reveal and the draw
# (docs/rules/setup-and-game-flow.md section 5; user ruling 2026-09-29).


def test_the_control_defense_is_asked_after_the_reveal_and_before_the_draw() -> None:
    start = _controlled_round_start()

    result = begin_round(start)
    state = result.state

    assert state.phase is GamePhase.ROUND_START
    assert state.round_number == 1
    assert state.current_conflict_ids == ("siege_of_arrakeen",)
    assert state.conflict_deck == ()
    assert [event.kind for event in result.events] == ["conflict_revealed"]
    for player, before in zip(state.players, start.players, strict=True):
        assert player.hand == ()
        assert player.deck == before.deck
    (frame,) = state.decision_stack
    assert frame.kind == FrameKind.CONTROL_DEFENSE
    assert dict(frame.context) == {"space_id": "arrakeen"}
    # Round Start is Phase 1 [Main p. 8]: no turn is open yet, so the
    # frame names no turn owner.
    assert "turn_owner" not in dict(frame.context)


def test_a_defender_whose_supply_emptied_meanwhile_may_only_decline() -> None:
    """The defense "may deploy one troop from your supply" [Main p. 10]; an
    effect of the same step (an Earn Any Alliance completion) can empty that
    supply while the frame is open, and then only declining is left."""
    state = begin_round(_controlled_round_start()).state
    (frame,) = state.decision_stack
    assert isinstance(frame.decision, PlayerDecision)
    defender = frame.decision.owner
    emptied = replace(
        state.players[defender],
        troops_garrison=state.players[defender].troops_garrison
        + state.players[defender].troops_supply,
        troops_supply=0,
    )
    players = tuple(
        emptied if player.player_id == defender else player
        for player in state.players
    )
    state = replace(state, players=players)
    assert [a.action_id for a in legal_control_defense_actions(state, defender)] == [
        "decline_control_defense"
    ]


@pytest.mark.parametrize(
    ("action_id", "event_kind", "troops_conflict"),
    (
        ("deploy_control_defense", "control_defense_deployed", 1),
        ("decline_control_defense", "control_defense_declined", 0),
    ),
)
def test_the_round_start_draw_follows_the_control_defense(
    action_id: str, event_kind: str, troops_conflict: int
) -> None:
    start = _controlled_round_start()
    state = begin_round(start).state

    result = apply_control_defense_action(
        state, DomainAction(action_id=action_id, actor=2)
    )

    drawn = result.events[1:]
    assert [event.kind for event in result.events] == [event_kind, *["cards_drawn"] * 4]
    assert [dict(event.payload)["player"] for event in drawn] == [0, 1, 2, 3]
    assert result.state.phase is GamePhase.PLAYER_TURNS
    assert result.state.round_number == 1
    assert result.state.current_conflict_ids == ("siege_of_arrakeen",)
    assert result.state.players[2].troops_conflict == troops_conflict
    for player, before in zip(result.state.players, start.players, strict=True):
        assert player.hand == before.deck
        assert player.deck == ()
    (frame,) = result.state.decision_stack
    assert frame.kind == FrameKind.TURN
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == 0


def test_a_conflict_nobody_can_defend_reveals_and_draws_in_one_step() -> None:
    # Without a troop in the controller's supply there is nothing to ask, so
    # the reveal and the draw stay one transition, exactly as before.
    start = _controlled_round_start(troops_supply=0)

    result = begin_round(start)
    revealed = replace(
        start,
        round_number=1,
        conflict_deck=(),
        current_conflict_ids=("siege_of_arrakeen",),
    )

    assert [event.kind for event in result.events] == [
        "conflict_revealed",
        *["cards_drawn"] * 4,
    ]
    assert result.state.phase is GamePhase.PLAYER_TURNS
    assert result.state == draw_round_hands(revealed).state
    assert result.events[1:] == draw_round_hands(revealed).events


def test_a_round_start_with_a_reshuffle_and_a_defender_keeps_the_rules_order() -> None:
    start = _controlled_round_start()
    short = replace(
        start.players[1],
        deck=start.players[1].deck[:2],
        discard_pile=start.players[1].deck[2:],
    )
    start = replace(start, players=(start.players[0], short, *start.players[2:]))

    # 1. The discard shuffle chance comes first; nothing is revealed yet.
    prepared = prepare_round_start(start)
    chance = prepared.state
    decision = chance.decision_stack[-1].decision
    assert isinstance(decision, ChanceDecision)
    assert prepared.events == ()
    assert chance.phase is GamePhase.ROUND_START
    assert chance.round_number == 0
    assert chance.current_conflict_ids == ()

    # 2. The reshuffle, then the reveal, which stops on the defense.
    outcome = ChanceOutcome(decision.decision_id, tuple(reversed(decision.options)))
    revealed = apply_round_start_reshuffle(chance, outcome)
    assert [event.kind for event in revealed.events] == [
        "personal_discard_shuffled",
        "conflict_revealed",
    ]
    assert revealed.state.phase is GamePhase.ROUND_START
    assert revealed.state.decision_stack[-1].kind == FrameKind.CONTROL_DEFENSE
    assert all(player.hand == () for player in revealed.state.players)
    shuffled = (*short.deck, *reversed(short.discard_pile))
    assert revealed.state.players[1].deck == shuffled

    # 3. The defense, then the draw.
    deploy = legal_control_defense_actions(revealed.state, 2)[1]
    drawn = apply_control_defense_action(revealed.state, deploy)
    assert [event.kind for event in drawn.events] == [
        "control_defense_deployed",
        *["cards_drawn"] * 4,
    ]
    assert drawn.state.players[1].hand == shuffled
    assert drawn.state.phase is GamePhase.PLAYER_TURNS


def test_the_engine_reveals_once_and_draws_after_the_defense() -> None:
    # Through the engine's automatic advance: the Round Start with an empty
    # stack reveals, stops on the defense, and the defense's own draw opens
    # the first turn without a second reveal.
    engine = UprisingRulesEngine(SELECTED_LEADERS)
    setup = _setup_state()
    controller = replace(setup.players[2], control_space_ids=("arrakeen",))
    setup = replace(
        setup,
        players=(*setup.players[:2], controller, setup.players[3]),
        conflict_deck=(
            "siege_of_arrakeen",
            *(card for card in setup.conflict_deck if card != "siege_of_arrakeen"),
        ),
    )
    state = prepare_round_start(setup).state
    assert state.phase is GamePhase.ROUND_START
    assert all(player.hand == () for player in state.players)

    transition = engine.apply(state, engine.legal_actions(state, 2)[0])

    assert [event.kind for event in transition.events][:2] == [
        "control_defense_declined",
        "cards_drawn",
    ]
    assert "conflict_revealed" not in [event.kind for event in transition.events]
    assert transition.state.round_number == 1
    assert transition.state.current_conflict_ids == ("siege_of_arrakeen",)
    assert transition.state.phase is GamePhase.PLAYER_TURNS
    assert all(len(player.hand) == 5 for player in transition.state.players)
    top = transition.state.decision_stack[-1]
    assert top.kind == FrameKind.TURN
    assert isinstance(top.decision, PlayerDecision)
    assert top.decision.owner == setup.first_player


def test_the_scouts_step_waits_for_the_draw_after_the_control_defense() -> None:
    # Arrakeen Scouts: the step follows the whole Round Start (OQ-072), so
    # the draw after the defense leaves it pending instead of a turn.
    state = begin_round(
        _controlled_round_start(config=RulesetConfig(arrakeen_scouts=True))
    ).state
    assert state.phase is GamePhase.ROUND_START
    assert not state.scouts_opening

    decline = legal_control_defense_actions(state, 2)[0]
    result = apply_control_defense_action(state, decline)

    assert result.state.phase is GamePhase.PLAYER_TURNS
    assert result.state.scouts_opening
    assert result.state.decision_stack == ()
    assert all(len(player.hand) == 5 for player in result.state.players)


def test_a_defending_twisted_genius_draws_its_twisted_intrigue_with_the_hand() -> None:
    # Twisted Genius: "Round Start: Draw a Twisted Intrigue card" [Piter De
    # Vries card]. The rules do not order it against the defensive bonus;
    # by project convention it comes with the hand, after the defense
    # (OQ-072), so the defense is decided on what the seat held at the reveal.
    twisted = ("intrigue:twisted_a", "intrigue:twisted_b")
    state = begin_round(_controlled_round_start(twisted_deck=twisted)).state
    assert state.players[2].intrigue_cards == ()
    assert state.players[2].twisted_deck == twisted

    deploy = legal_control_defense_actions(state, 2)[1]
    result = apply_control_defense_action(state, deploy)

    assert result.state.players[2].intrigue_cards == ("intrigue:twisted_a",)
    assert result.state.players[2].twisted_deck == ("intrigue:twisted_b",)
    assert [event.kind for event in result.events] == [
        "control_defense_deployed",
        *["cards_drawn"] * 4,
        "intrigue_card_drawn",
    ]


@pytest.mark.parametrize(
    ("tech_cards_owed", "hungry_for_spice_owed", "source"),
    (
        # Planetary Array / CHOAM Transports (``tech.draw_owed_tech_cards``).
        (1, False, "tech_draw"),
        # Hungry for Spice (``leader_abilities.grant_hungry_for_spice``).
        (0, True, "hungry_for_spice"),
    ),
)
def test_an_owed_card_draw_waits_for_the_round_start_draw(
    tech_cards_owed: int, hungry_for_spice_owed: bool, source: str
) -> None:
    # An owed draw waits behind the Round Start reshuffle; once that is
    # resolved the reveal stops on the defense, before "each player draws
    # five cards from their own deck" [Main p. 8] [Main p. 20]. Drawing the
    # owed card there took it out of the round's hand and left the deck
    # short, so the defense's own draw raised (OQ-072). It now waits for the
    # draw and comes after the hand, as when reveal and draw were one step.
    start = _controlled_round_start(
        config=RulesetConfig(bloodlines=True, tech_module=True)
    )
    owing = replace(
        start.players[1],
        discard_pile=tuple(f"player:1:disc:{index}" for index in range(3)),
        tech_cards_owed=tech_cards_owed,
        hungry_for_spice_owed=hungry_for_spice_owed,
    )
    short = replace(
        start.players[3],
        deck=start.players[3].deck[:2],
        discard_pile=tuple(f"player:3:disc:{index}" for index in range(3)),
    )
    start = replace(start, players=(start.players[0], owing, start.players[2], short))
    engine = UprisingRulesEngine()

    # Seat 3's Round Start reshuffle, then the reveal stops on the defense
    # with the owed draw still waiting.
    prepared = prepare_round_start(start).state
    shuffle = engine.current_decision(prepared)
    assert isinstance(shuffle, ChanceDecision)
    revealed = engine.apply(
        prepared, ChanceOutcome(shuffle.decision_id, shuffle.options)
    ).state
    assert revealed.phase is GamePhase.ROUND_START
    assert revealed.decision_stack[-1].kind == FrameKind.CONTROL_DEFENSE
    assert revealed.players[1].deck == owing.deck
    assert revealed.players[1].hand == ()
    assert revealed.players[1].tech_cards_owed == owing.tech_cards_owed
    assert revealed.players[1].hungry_for_spice_owed == owing.hungry_for_spice_owed

    # The defense answer draws the hands; the owed card follows, from seat
    # 1's discard pile once it is reshuffled.
    answered = engine.apply(
        revealed, DomainAction(action_id="decline_control_defense", actor=2)
    )
    kinds = [event.kind for event in answered.events]
    assert kinds[:5] == ["control_defense_declined", *["cards_drawn"] * 4]
    drawn = answered.state
    assert drawn.phase is GamePhase.PLAYER_TURNS
    assert drawn.players[1].hand == owing.deck
    assert drawn.players[1].tech_cards_owed == 0
    assert not drawn.players[1].hungry_for_spice_owed
    reshuffle = engine.current_decision(drawn)
    assert isinstance(reshuffle, ChanceDecision)
    assert reshuffle.decision_id == f"round:1:player:1:{source}:discard_shuffle"

    order = tuple(reversed(reshuffle.options))
    final = engine.apply(drawn, ChanceOutcome(reshuffle.decision_id, order)).state
    assert final.players[1].hand == (*owing.deck, order[0])
    assert final.players[1].deck == order[1:]
    assert all(
        len(player.hand) == 5 for player in final.players if player.player_id != 1
    )
    top = final.decision_stack[-1]
    assert top.kind == FrameKind.TURN
    assert isinstance(top.decision, PlayerDecision)
    assert top.decision.owner == 0


def test_round_start_is_pure_and_rejects_wrong_phase() -> None:
    state = _setup_state()
    before = canonical_state_hash(state)

    assert begin_round(state) == begin_round(state)
    assert canonical_state_hash(state) == before
    with pytest.raises(ValueError, match="Round Start phase"):
        begin_round(replace(state, phase=GamePhase.PLAYER_TURNS))


def test_round_start_requests_and_applies_recorded_discard_reshuffle() -> None:
    state = _setup_state()
    original = state.players[0]
    first = replace(
        original,
        deck=original.deck[:2],
        discard_pile=original.deck[2:6],
    )
    state = replace(state, players=(first, *state.players[1:]))

    prepared = prepare_round_start(state).state
    decision = prepared.decision_stack[-1].decision

    assert isinstance(decision, ChanceDecision)
    assert decision.options == first.discard_pile
    outcome = ChanceOutcome(decision.decision_id, tuple(reversed(decision.options)))
    result = apply_round_start_reshuffle(prepared, outcome)

    assert result.state.phase is GamePhase.PLAYER_TURNS
    assert result.state.players[0].hand == (
        *first.deck,
        *tuple(reversed(first.discard_pile))[:3],
    )
    assert result.state.players[0].discard_pile == ()
    assert result.events[0].kind == "personal_discard_shuffled"


def test_round_start_draws_all_available_cards_when_total_is_below_five() -> None:
    state = _setup_state()
    first = replace(state.players[0], deck=state.players[0].deck[:3])
    state = replace(state, players=(first, *state.players[1:]))

    result = prepare_round_start(state)

    assert len(result.state.players[0].hand) == 3
    draw_event = next(
        event
        for event in result.events
        if event.kind == "cards_drawn" and dict(event.payload)["player"] == 0
    )
    assert dict(draw_event.payload)["count"] == 3


def test_makers_add_spice_only_to_unoccupied_spaces() -> None:
    state = _setup_state()
    first = replace(
        state.players[0],
        agents_available=1,
        agent_locations=("hagga_basin",),
    )
    state = replace(
        state,
        phase=GamePhase.MAKERS,
        players=(first, *state.players[1:]),
        maker_bonus_spice=(
            ("deep_desert", 2),
            ("hagga_basin", 3),
            ("imperial_basin", 0),
        ),
    )

    result = resolve_makers(state)

    assert result.state.phase is GamePhase.RECALL_OR_ENDGAME
    assert result.state.maker_bonus_spice == (
        ("deep_desert", 3),
        ("hagga_basin", 3),
        ("imperial_basin", 1),
    )
    assert tuple(dict(event.payload)["space_id"] for event in result.events) == (
        "deep_desert",
        "imperial_basin",
    )


def test_recall_returns_agents_rotates_first_player_and_resets_reveal() -> None:
    state = _setup_state()
    players = tuple(
        replace(
            player,
            agents_available=1,
            agent_locations=(f"space_{player.player_id}",),
            has_revealed=True,
        )
        for player in state.players
    )
    state = replace(
        state,
        phase=GamePhase.RECALL_OR_ENDGAME,
        first_player=3,
        players=players,
    )

    result = resolve_recall_or_endgame(state)

    assert result.state.phase is GamePhase.ROUND_START
    assert result.state.first_player == 0
    assert all(player.agents_available == 2 for player in result.state.players)
    assert all(player.agent_locations == () for player in result.state.players)
    assert all(player.has_revealed is False for player in result.state.players)


@pytest.mark.parametrize(("victory_points", "endgame"), ((9, False), (10, True)))
def test_go_to_11_still_enters_endgame_at_ten(
    victory_points: int, endgame: bool
) -> None:
    # The variant only moves the start: "start at 0 and play to 10"
    # [Immortality p. 12]; the trigger stays 10 or more at round end
    # [Main p. 15], whatever the variant's name says.
    config = RulesetConfig(immortality=True, go_to_11=True)
    state = create_initial_state(
        config, seed=71, leader_ids=SELECTED_LEADERS
    ).state
    leader = replace(state.players[2], victory_points=victory_points)
    state = replace(
        state,
        phase=GamePhase.RECALL_OR_ENDGAME,
        players=(*state.players[:2], leader, state.players[3]),
    )

    result = resolve_recall_or_endgame(state)

    assert (result.state.phase is GamePhase.ENDGAME) is endgame


@pytest.mark.parametrize("reason", ("victory_points", "conflict_deck"))
def test_recall_enters_endgame_at_either_end_condition(reason: str) -> None:
    state = replace(_setup_state(), phase=GamePhase.RECALL_OR_ENDGAME)
    if reason == "victory_points":
        winner = replace(state.players[2], victory_points=10)
        state = replace(state, players=(*state.players[:2], winner, state.players[3]))
    else:
        state = replace(state, conflict_deck=())

    result = resolve_recall_or_endgame(state)

    assert result.state.phase is GamePhase.ENDGAME
    assert result.events[0].kind == "endgame_started"
