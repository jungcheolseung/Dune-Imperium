"""Arrakeen Scouts: the four round-long rule changes (slice 3b).

docs/rules/arrakeen-scouts.md 6 and 6.1: Unlikely Allies waives board
spaces' Influence requirements; Eyes on Arrakis makes every Faction space a
Combat space; Market Opening takes 2 off the round's first The Spice Must
Flow (OQ-081 (b)); Friends Everywhere lets an Influence 4 bonus be any
Faction's (OQ-081 (a)). Each lasts until the next Round Start.
"""

from dataclasses import replace
from typing import Any

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, Faction
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import Influence, PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.acquisition import reserve_cost
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.scouts_modifiers import discount_used_after, space_is_combat

SCOUTS = RulesetConfig(arrakeen_scouts=True)
STARTERS = starting_deck_instance_ids(0)
UNLIKELY_ALLIES = "ignore_influence_requirements"
EYES_ON_ARRAKIS = "faction_spaces_are_combat"
MARKET_OPENING = "spice_must_flow_discount"
FRIENDS_EVERYWHERE = "any_faction_four_bonus"


def _state(owner: PlayerState, modifier: str = "", **fields: Any) -> GameState:
    values: dict[str, Any] = {
        "config": SCOUTS,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 5,
        "first_player": 0,
        "players": (owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        "scouts_round_modifier": modifier,
        "decision_stack": (
            DecisionFrame(
                kind="turn",
                frame_id="round:5:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    }
    values.update(fields)
    return GameState(**values)


def _owner(**overrides: object) -> PlayerState:
    values: dict[str, object] = {"player_id": 0, "deck": STARTERS[:4]}
    values.update(overrides)
    return PlayerState(**values)  # type: ignore[arg-type]


def _spaces(state: GameState) -> set[str]:
    return {str(dict(a.arguments)["space_id"]) for a in legal_agent_actions(state, 0)}


# --- Unlikely Allies ------------------------------------------------------------


def test_unlikely_allies_waives_influence_requirements_for_the_round() -> None:
    owner = _owner(hand=STARTERS[4:10])
    # Sietch Tabr needs two Fremen Influence [Board Guide p. 1].
    assert "sietch_tabr" not in _spaces(_state(owner))
    assert "sietch_tabr" in _spaces(_state(owner, UNLIKELY_ALLIES))
    # Another round's change does not waive it.
    assert "sietch_tabr" not in _spaces(_state(owner, EYES_ON_ARRAKIS))


# --- Eyes on Arrakis --------------------------------------------------------------


def test_eyes_on_arrakis_makes_faction_spaces_combat_spaces() -> None:
    state = _state(_owner(), EYES_ON_ARRAKIS)
    faction_spaces = [s for s in BOARD_SPACES_BY_ID.values() if s.faction is not None]
    assert len(faction_spaces) == 8
    assert all(space_is_combat(state, space) for space in faction_spaces)
    assert not space_is_combat(state, BOARD_SPACES_BY_ID["high_council"])
    plain = _state(_owner())
    assert not space_is_combat(plain, BOARD_SPACES_BY_ID["secrets"])
    assert space_is_combat(plain, BOARD_SPACES_BY_ID["hagga_basin"])


def _visit_faction_space(modifier: str) -> dict[str, object]:
    state = _state(_owner(hand=STARTERS[4:10]), modifier)
    action = next(
        a
        for a in legal_agent_actions(state, 0)
        if dict(a.arguments)["space_id"] in ("espionage", "secrets", "dutiful_service")
    )
    visited = apply_agent_action(state, action).state
    frame = visited.decision_stack[-1]
    assert frame.kind == FrameKind.AGENT_EFFECTS
    return dict(frame.context)


def test_a_faction_space_under_eyes_on_arrakis_deploys_like_a_combat_space() -> None:
    # A Combat space lets the turn's recruits and up to two garrison troops
    # deploy [Main p. 10].
    combat = _visit_faction_space(EYES_ON_ARRAKIS)
    assert combat["pending_combat_deployment"] is True
    assert combat["existing_troop_deployment_limit"] == 2
    plain = _visit_faction_space("")
    assert plain["pending_combat_deployment"] is False
    assert plain["existing_troop_deployment_limit"] == 0


# --- Market Opening ------------------------------------------------------------------


def test_market_opening_discounts_only_the_rounds_first_spice_must_flow() -> None:
    state = _state(_owner(), MARKET_OPENING)
    assert reserve_cost(state, "the_spice_must_flow") == 9 - 2
    assert reserve_cost(state, "prepare_the_way") == reserve_cost(
        _state(_owner()), "prepare_the_way"
    )
    assert reserve_cost(_state(_owner()), "the_spice_must_flow") == 9
    # Acquiring it uses the discount up for everyone this round.
    assert discount_used_after(state, "the_spice_must_flow")
    assert not discount_used_after(state, "prepare_the_way")
    used = replace(state, scouts_discount_used=True)
    assert reserve_cost(used, "the_spice_must_flow") == 9


def test_the_discount_is_paid_and_used_up_by_a_reveal_acquisition() -> None:
    from dune_imperium.rules.acquisition import (
        apply_reserve_acquisition,
        legal_reserve_acquisitions,
    )
    from dune_imperium.rules.frames import frame_context

    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(arrakeen_scouts=True), 3)
    from dune_imperium.core.chance import ChanceResolver
    from dune_imperium.core.decisions import ChanceDecision

    resolver = ChanceResolver(seed=3)
    while isinstance(engine.current_decision(state), ChanceDecision):
        decision = engine.current_decision(state)
        assert isinstance(decision, ChanceDecision)
        state = engine.apply(state, resolver.resolve(decision)).state
    seat = state.first_player
    assert seat is not None
    state = replace(state, scouts_round_modifier=MARKET_OPENING)
    reveal = next(
        a for a in engine.legal_actions(state, seat) if a.action_id == "reveal_turn"
    )
    state = engine.apply(state, reveal).state
    while state.decision_stack[-1].kind != FrameKind.REVEAL:
        top = state.decision_stack[-1].decision
        assert isinstance(top, PlayerDecision)
        state = engine.apply(state, engine.legal_actions(state, top.owner)[0]).state
    frame = state.decision_stack[-1]
    context = frame_context(frame)
    context["persuasion"] = 7
    state = replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),
        ),
    )
    offered = {
        dict(a.arguments)["card_id"]: a for a in legal_reserve_acquisitions(state, seat)
    }
    assert "the_spice_must_flow" in offered
    bought = apply_reserve_acquisition(state, offered["the_spice_must_flow"]).state
    assert dict(bought.decision_stack[-1].context)["persuasion"] == 0
    assert bought.scouts_discount_used
    assert reserve_cost(bought, "the_spice_must_flow") == 9


# --- Friends Everywhere ---------------------------------------------------------


def _at_three(faction: Faction, modifier: str) -> GameState:
    influence = replace(Influence(), **{faction.value: 3})
    return _state(_owner(influence=influence), modifier, decision_stack=())


def test_without_friends_everywhere_the_reached_tracks_bonus_is_earned() -> None:
    gained = gain_faction_influence(
        _at_three(Faction.FREMEN, ""), 0, Faction.FREMEN, 1, event_prefix="t"
    ).state
    # The Fremen strip prints a water drop at 4 [Main p. 7].
    assert gained.players[0].resources.water == 2
    assert not gained.scouts_four_bonus_choices


def test_friends_everywhere_queues_the_choice_and_takes_the_chosen_bonus() -> None:
    engine = UprisingRulesEngine()
    gained = gain_faction_influence(
        _at_three(Faction.FREMEN, FRIENDS_EVERYWHERE),
        0,
        Faction.FREMEN,
        1,
        event_prefix="t",
    )
    assert gained.state.players[0].resources.water == 1  # not yet
    assert gained.state.scouts_four_bonus_choices == ((0, "fremen", "t:track_bonus:0"),)
    opened = _advance_automatic(gained).state
    frame = opened.decision_stack[-1]
    assert frame.kind == FrameKind.SCOUTS_FOUR_BONUS
    options = engine.legal_actions(opened, 0)
    assert [dict(a.arguments)["faction"] for a in options] == [f.value for f in Faction]
    guild = next(a for a in options if dict(a.arguments)["faction"] == "spacing_guild")
    chosen = engine.apply(opened, guild)
    owner = chosen.state.players[0]
    # The Spacing Guild strip's 3 Solari instead of the Fremen water.
    assert (owner.resources.solari, owner.resources.water) == (3, 1)
    bonus = next(e for e in chosen.events if e.kind == "influence_track_bonus_gained")
    assert dict(bonus.payload)["faction"] == "spacing_guild"
    assert dict(bonus.payload)["reached_faction"] == "fremen"


def test_choosing_the_emperor_bonus_then_places_its_spy() -> None:
    engine = UprisingRulesEngine()
    gained = gain_faction_influence(
        _at_three(Faction.FREMEN, FRIENDS_EVERYWHERE),
        0,
        Faction.FREMEN,
        1,
        event_prefix="t",
    )
    opened = _advance_automatic(gained).state
    emperor = next(
        a
        for a in engine.legal_actions(opened, 0)
        if dict(a.arguments)["faction"] == "emperor"
    )
    chosen = engine.apply(opened, emperor).state
    assert chosen.decision_stack[-1].kind == FrameKind.SPY_PLACEMENT


def test_friends_everywhere_threads_through_conflict_rewards() -> None:
    # The Conflict's fixed Influence reward carries the gain queues by hand
    # (rules/combat.py): Protect the Sietches' first place gains one Fremen
    # Influence, which from 3 reaches 4 and queues the choice.
    from dune_imperium.rules.combat import resolve_combat_rewards

    players = tuple(
        PlayerState(
            player_id=seat,
            combat_strength=strength,
            influence=Influence(fremen=3) if seat == 0 else Influence(),
        )
        for seat, strength in enumerate((8, 6, 4, 0))
    )
    state = GameState(
        config=SCOUTS,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=5,
        first_player=0,
        players=players,
        current_conflict_ids=("protect_the_sietches",),
        combat_intrigue_complete=True,
        intrigue_deck=("intrigue:0", "intrigue:1", "intrigue:2", "intrigue:3"),
        scouts_round_modifier=FRIENDS_EVERYWHERE,
    )
    result = resolve_combat_rewards(state).state
    assert result.players[0].influence.fremen == 4
    assert result.scouts_four_bonus_choices == (
        (0, "fremen", result.scouts_four_bonus_choices[0][2]),
    )
