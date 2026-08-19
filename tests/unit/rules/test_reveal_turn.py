"""Tests for the basic Reveal-turn transition."""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.rules.reveal_turn import (
    begin_reveal_turn,
    finish_reveal_turn,
    legal_finish_reveal_actions,
    legal_reveal_actions,
)


def _instance(card_id: str, copy: int = 0) -> str:
    return tuple(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )[copy]


def _imperium_instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if f":{card_id}:" in instance_id
    )


def _state(player: PlayerState) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(player, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def test_reveal_is_available_even_with_agents_remaining() -> None:
    state = _state(PlayerState(player_id=0))

    assert legal_reveal_actions(state, 0) == (
        DomainAction(action_id="reveal_turn", actor=0),
    )
    assert legal_reveal_actions(state, 1) == ()


def test_reveal_moves_hand_to_in_play_and_totals_persuasion() -> None:
    argument = _instance("convincing_argument")
    diplomacy = _instance("diplomacy")
    state = _state(PlayerState(player_id=0, hand=(argument, diplomacy)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    owner = result.state.players[0]
    context = dict(result.state.decision_stack[-1].context)

    assert owner.hand == ()
    assert owner.in_play == (argument, diplomacy)
    assert context["persuasion"] == 3
    assert context["revealed_card_count"] == 2
    assert context["revealed_card_000"] == argument
    assert context["revealed_card_001"] == diplomacy


def test_high_council_and_assembly_hall_add_reveal_persuasion() -> None:
    state = _state(
        PlayerState(
            player_id=0,
            high_council=True,
            agents_available=1,
            agent_locations=("assembly_hall",),
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 3


def test_reveal_strength_requires_a_unit_in_conflict() -> None:
    dagger = _instance("dagger")
    without_unit = _state(PlayerState(player_id=0, hand=(dagger,)))

    no_unit_result = begin_reveal_turn(
        without_unit,
        legal_reveal_actions(without_unit, 0)[0],
    )
    assert no_unit_result.state.players[0].combat_strength == 0

    with_unit = _state(
        PlayerState(
            player_id=0,
            hand=(dagger,),
            troops_supply=8,
            troops_conflict=1,
        )
    )
    unit_result = begin_reveal_turn(
        with_unit,
        legal_reveal_actions(with_unit, 0)[0],
    )
    assert unit_result.state.players[0].combat_strength == 3


def test_reserve_cards_contribute_their_printed_reveal_values() -> None:
    prepare = "reserve:prepare_the_way:7"
    spice = "reserve:the_spice_must_flow:9"
    state = _state(
        PlayerState(
            player_id=0,
            hand=(prepare, spice),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 2
    assert context["strength"] == 3


def test_transcribed_imperium_cards_contribute_reveal_values() -> None:
    maula = _imperium_instance("maula_pistol")
    truthtrance = _imperium_instance("truthtrance")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(maula, truthtrance),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 2
    assert context["strength"] == 3


def test_sardaukar_soldier_contributes_reveal_values() -> None:
    sardaukar = _imperium_instance("sardaukar_soldier")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(sardaukar,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 1
    assert context["strength"] == 3


def test_hidden_missive_contributes_reveal_values() -> None:
    hidden_missive = _imperium_instance("hidden_missive")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(hidden_missive,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 1
    assert context["strength"] == 3


def test_desert_survival_contributes_reveal_values() -> None:
    desert_survival = _imperium_instance("desert_survival")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(desert_survival,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 1
    assert context["strength"] == 3


def test_smugglers_harvester_contributes_reveal_persuasion() -> None:
    harvester = _imperium_instance("smuggler_s_harvester")
    state = _state(PlayerState(player_id=0, hand=(harvester,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1


def test_reveal_preserves_agent_cards_already_in_play() -> None:
    played = _instance("dagger", 0)
    revealed = _instance("dagger", 1)
    state = _state(PlayerState(player_id=0, hand=(revealed,), in_play=(played,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert result.state.players[0].in_play == (played, revealed)


def test_reveal_cleanup_discards_in_play_but_preserves_late_drawn_hand() -> None:
    revealed = _instance("diplomacy")
    retained = _instance("dagger")
    state = _state(PlayerState(player_id=0, hand=(revealed,)))
    state = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    owner = replace(state.players[0], hand=(retained,))
    state = replace(state, players=(owner, *state.players[1:]))

    result = finish_reveal_turn(state, legal_finish_reveal_actions(state, 0)[0])
    owner = result.state.players[0]

    assert owner.has_revealed is True
    assert result.state.reveal_order == (0,)
    assert owner.in_play == ()
    assert owner.discard_pile == (revealed,)
    assert owner.hand == (retained,)


def test_reveal_cleanup_skips_players_who_already_revealed() -> None:
    state = _state(PlayerState(player_id=0))
    state = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    players = (
        state.players[0],
        replace(state.players[1], has_revealed=True),
        state.players[2],
        replace(state.players[3], has_revealed=True),
    )
    state = replace(state, players=players)

    result = finish_reveal_turn(state, legal_finish_reveal_actions(state, 0)[0])

    decision = result.state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 2


def test_last_reveal_cleanup_enters_combat_without_pending_decision() -> None:
    state = _state(PlayerState(player_id=0))
    state = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    players = (
        state.players[0],
        *(replace(player, has_revealed=True) for player in state.players[1:]),
    )
    state = replace(state, players=players)

    result = finish_reveal_turn(state, legal_finish_reveal_actions(state, 0)[0])

    assert result.state.phase is GamePhase.COMBAT
    assert result.state.decision_stack == ()
    assert all(player.has_revealed for player in result.state.players)


def test_four_empty_reveal_turns_follow_seat_order_into_combat() -> None:
    state = _state(PlayerState(player_id=0))
    state = replace(
        state,
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:2",
                decision=PlayerDecision(owner=2, prompt="Choose a turn"),
            ),
        ),
    )

    visited: list[int] = []
    for player in (2, 3, 0, 1):
        decision = state.decision_stack[-1].decision
        assert isinstance(decision, PlayerDecision)
        visited.append(decision.owner)
        state = begin_reveal_turn(
            state,
            legal_reveal_actions(state, player)[0],
        ).state
        state = finish_reveal_turn(
            state,
            legal_finish_reveal_actions(state, player)[0],
        ).state

    assert visited == [2, 3, 0, 1]
    assert state.reveal_order == (2, 3, 0, 1)
    assert state.phase is GamePhase.COMBAT
    assert state.decision_stack == ()
