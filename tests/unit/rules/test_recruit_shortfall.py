"""Tests for the public ``troops_recruit_short`` event.

When a troop recruit cannot be fully served because the player's supply is
short, the engine still moves ``min(supply, count)`` troops [Main p. 10]
(``docs/rules/player-turns.md`` line 123), but it now also emits a public
``troops_recruit_short`` event so the shortfall is visible in the action log.
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import Faction
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
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.rules.agent_effects import resolve_agent_card_effect
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    legal_board_effect_actions,
    resolve_board_effect,
)
from dune_imperium.rules.combat import resolve_combat_rewards
from dune_imperium.rules.combat_deployment import legal_combat_deployments
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.reveal_turn import begin_reveal_turn


def _instance(card_id: str, copy: int = 0) -> str:
    matches = tuple(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )
    return matches[copy]


def _imperium_instance(card_id: str, copy: int = 0) -> str:
    matches = tuple(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if f":{card_id}:" in instance_id
    )
    return matches[copy]


def _turn_frame(owner: int = 0) -> DecisionFrame:
    return DecisionFrame(
        kind="turn",
        frame_id=f"round:1:turn:{owner}",
        decision=PlayerDecision(owner=owner, prompt="Choose a turn"),
    )


def _agent_action_to(state: GameState, space_id: str) -> DomainAction:
    return next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )


def _shortfall_events(events: tuple[GameEvent, ...]) -> tuple[GameEvent, ...]:
    return tuple(event for event in events if event.kind == "troops_recruit_short")


def _with_troops_supply(state: GameState, player: int, supply: int) -> GameState:
    """Move supply troops into the Conflict so the 12-troop total still holds."""

    owner = state.players[player]
    moved = owner.troops_supply - supply
    return replace(
        state,
        players=tuple(
            replace(
                candidate,
                troops_supply=supply,
                troops_conflict=candidate.troops_conflict + moved,
            )
            if candidate.player_id == player
            else candidate
            for candidate in state.players
        ),
    )


def _resolve_troops_icon(state: GameState) -> RuleResult:
    troops_action = next(
        action
        for action in legal_board_effect_actions(state, 0)
        if dict(action.arguments)["effect"] == "troops"
    )
    return resolve_board_effect(state, troops_action)


# ---------- board icon (Research Station: RecruitTroopsEffect(2)) ----------


def _research_station_state() -> GameState:
    reconnaissance = _instance("reconnaissance")
    deck = (_instance("dagger", 0), _instance("dagger", 1))
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            PlayerState(
                player_id=0,
                hand=(reconnaissance,),
                deck=deck,
                resources=Resources(water=2),
            ),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(_turn_frame(),),
    )


def test_research_station_troop_icons_with_empty_supply_report_a_shortfall() -> None:
    state = _with_troops_supply(_research_station_state(), 0, 0)
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state

    result = _resolve_troops_icon(state)

    shortfalls = _shortfall_events(result.events)
    assert len(shortfalls) == 1
    assert dict(shortfalls[0].payload) == {
        "player": 0,
        "recruited": 0,
        "requested": 2,
        "short": 2,
    }
    assert result.state.players[0].troops_garrison == 3
    context = dict(result.state.decision_stack[-1].context)
    assert context["troops_recruited"] == 0

    # Every event id emitted by this step must be unique.
    event_ids = [event.event_id for event in result.events]
    assert len(event_ids) == len(set(event_ids))

    # With nothing recruited, only the two garrison troops may deploy.
    counts = tuple(
        dict(action.arguments)["count"]
        for action in legal_combat_deployments(result.state, 0)
    )
    assert counts == (1, 2)


def test_research_station_troop_icons_with_partial_supply_report_the_shortfall() -> (
    None
):
    state = _with_troops_supply(_research_station_state(), 0, 1)
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state

    result = _resolve_troops_icon(state)

    shortfalls = _shortfall_events(result.events)
    assert len(shortfalls) == 1
    assert dict(shortfalls[0].payload) == {
        "player": 0,
        "recruited": 1,
        "requested": 2,
        "short": 1,
    }


def test_research_station_troop_icons_with_full_supply_report_no_shortfall() -> None:
    state = _research_station_state()
    assert state.players[0].troops_supply == 9
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state

    result = _resolve_troops_icon(state)

    assert _shortfall_events(result.events) == ()


# ---------- Reveal start (Junction Headquarters: recruit_troops=1) ----------


def test_reveal_start_troop_recruit_with_empty_supply_reports_a_shortfall() -> None:
    junction = _imperium_instance("junction_headquarters")
    owner = PlayerState(player_id=0, hand=(junction,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(_turn_frame(),),
    )
    state = _with_troops_supply(state, 0, 0)

    result = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))

    updated = result.state.players[0]
    assert updated.troops_supply == 0
    assert updated.troops_garrison == 3
    shortfalls = _shortfall_events(result.events)
    assert len(shortfalls) == 1
    assert dict(shortfalls[0].payload) == {
        "player": 0,
        "recruited": 0,
        "requested": 1,
        "short": 1,
    }


# ---------- Combat reward (Protect the Sietches: first place gets 1 troop) ----------


def _players(
    strengths: tuple[int, int, int, int],
) -> tuple[PlayerState, ...]:
    return tuple(
        PlayerState(player_id=player, combat_strength=strength)
        for player, strength in enumerate(strengths)
    )


def _reward_state(conflict_id: str) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=_players((8, 6, 4, 0)),
        current_conflict_ids=(conflict_id,),
        combat_intrigue_complete=True,
        intrigue_deck=("intrigue:0", "intrigue:1", "intrigue:2", "intrigue:3"),
    )


def test_combat_reward_troops_with_empty_supply_reports_a_shortfall() -> None:
    state = _reward_state("protect_the_sietches")
    state = _with_troops_supply(state, 0, 0)

    result = resolve_combat_rewards(state)

    assert result.state.players[0].troops_supply == 0
    assert result.state.players[0].troops_garrison == 3
    shortfalls = _shortfall_events(result.events)
    assert len(shortfalls) == 1
    assert dict(shortfalls[0].payload) == {
        "player": 0,
        "recruited": 0,
        "requested": 1,
        "short": 1,
    }


# ---------- Emperor Influence track bonus (recruit 2) ----------


def test_emperor_influence_track_bonus_with_empty_supply_reports_a_shortfall() -> None:
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        players=(
            PlayerState(player_id=0, influence=Influence(emperor=3)),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
    )
    state = _with_troops_supply(state, 0, 0)

    result = gain_faction_influence(
        state,
        0,
        Faction.EMPEROR,
        1,
        event_prefix="test:influence",
    )

    assert result.state.players[0].troops_supply == 0
    assert result.state.players[0].troops_garrison == 3
    shortfalls = _shortfall_events(result.events)
    assert len(shortfalls) == 1
    assert dict(shortfalls[0].payload) == {
        "player": 0,
        "recruited": 0,
        "requested": 2,
        "short": 2,
    }


# ---------- Agent-card effect (Stilgar the Devoted: RECRUIT_TWO_TROOPS) ----------


def test_stilgar_recruit_two_troops_with_empty_supply_reports_a_shortfall() -> None:
    stilgar = _imperium_instance("stilgar_the_devoted")
    owner = PlayerState(player_id=0, hand=(stilgar,))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(_turn_frame(),),
    )
    state = _with_troops_supply(state, 0, 0)
    placed = apply_agent_action(state, _agent_action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].troops_supply == 0
    assert result.state.players[0].troops_garrison == 3
    shortfalls = _shortfall_events(result.events)
    assert len(shortfalls) == 1
    assert dict(shortfalls[0].payload) == {
        "player": 0,
        "recruited": 0,
        "requested": 2,
        "short": 2,
    }


# ---------- OQ-030: no retroactive recruit once the supply grows later ----------


def test_a_later_supply_increase_does_not_revive_the_lost_recruit() -> None:
    # OQ-030 (docs/rules/player-turns.md, project convention 2026-09-06): the
    # shortfall expires when the icon resolves; a troop that returns to the
    # supply later in the same turn is not recruited retroactively.
    state = _with_troops_supply(_research_station_state(), 0, 0)
    state = apply_agent_action(
        state,
        _agent_action_to(state, "research_station"),
    ).state
    resolved = _resolve_troops_icon(state).state
    assert dict(resolved.decision_stack[-1].context)["troops_recruited"] == 0

    # A troop comes back to the supply (as an expansion "lose a troop" effect
    # would do) while the Agent turn is still open.
    owner = resolved.players[0]
    replenished = replace(
        resolved,
        players=(
            replace(
                owner,
                troops_supply=owner.troops_supply + 1,
                troops_conflict=owner.troops_conflict - 1,
            ),
            *resolved.players[1:],
        ),
    )

    assert replenished.players[0].troops_garrison == 3
    assert dict(replenished.decision_stack[-1].context)["troops_recruited"] == 0
    assert all(
        dict(action.arguments)["effect"] != "troops"
        for action in legal_board_effect_actions(replenished, 0)
    )
    counts = tuple(
        dict(action.arguments)["count"]
        for action in legal_combat_deployments(replenished, 0)
    )
    assert counts == (1, 2)
