"""Tests for the Tech Module's Ixian Embassy and Tech tile acquisition.

Rule source: ``docs/rules/bloodlines.md`` section 5 [Bloodlines pp. 6-7, 12]
and the eighteen Tech tile faces transcribed on 2026-09-07.
"""

import sys
from dataclasses import replace
from pathlib import Path

import pytest
from tests.support.pauses import pause_outcome

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.adapters.observation_encoding import (
    OBSERVATION_SIZE,
    encode_player_view,
)
from dune_imperium.content.bloodlines.tech import (
    TECH_IDS,
    TECH_TILES,
    TECH_TILES_BY_ID,
    TechAbility,
    tech_tiles_for,
)
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.effect_dsl import AcquireTech
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS_BY_ID,
    intrigue_deck_instance_ids,
)
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    ChanceOutcome,
    DecisionFrame,
    DomainAction,
    GameEvent,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
    observe_state,
)
from dune_imperium.core.decisions import ChanceDecision
from dune_imperium.core.engine import RuleResult, Transition
from dune_imperium.rules import turn_rows
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    legal_board_effect_actions,
    resolve_board_effect,
)
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import TECH_ACQUIRE_PENDING_KEY, FrameKind, with_context
from dune_imperium.rules.leader_abilities import IMPLEMENTED_ABILITY_LEADER_IDS
from dune_imperium.rules.optional_trash import (
    apply_optional_trash,
    legal_optional_trash_actions,
)
from dune_imperium.rules.setup import create_draft_initial_state, create_initial_state
from dune_imperium.rules.spy_moves import (
    apply_spy_placement,
    legal_spy_placement_actions,
)
from dune_imperium.rules.strength import units_strength
from dune_imperium.rules.tech import (
    apply_tech_acquire_effect,
    apply_tech_acquisition,
    apply_tech_influence_without_faction,
    legal_tech_acquire_effect_actions,
    legal_tech_acquisition_actions,
    push_tech_acquisition,
    tech_cost,
)
from dune_imperium.simulation.invariants import check_observation_privacy
from dune_imperium.simulation.sweep import run_checked_game

# tests/support isn't a package pytest or mypy resolve from a dotted import
# (see tests/support/turn_end.py's module docstring).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "support"))
from turn_end import (  # type: ignore[import-not-found]  # noqa: E402
    finish_agent_turn,
    finish_agent_turn_result,
)

TECH = RulesetConfig(bloodlines=True, tech_module=True)
TECH_CHOAM = RulesetConfig(bloodlines=True, tech_module=True, choam_module=True)
LEADERS = (
    "feyd_rautha_harkonnen",
    "gurney_halleck",
    "lady_amber_metulli",
    "lady_jessica",
)
LANDSRAAD_POST = "landsraad-assembly-hall-gather-support"
SIETCH_POST = "arrakis-research-station-sietch-tabr"
STACKS = (
    ("glowglobes", "training_depot", "panopticon"),
    ("gene_locked_vault", "delivery_bay", "servo_receivers"),
    ("advanced_data_analysis", "plasteel_blades", "spy_drones"),
)


def _turn_state(
    owner: PlayerState,
    *,
    stacks: tuple[tuple[str, ...], ...] = STACKS,
    config: RulesetConfig = TECH,
    **overrides: object,
) -> GameState:
    values: dict[str, object] = {
        "config": config,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 1,
        "current_conflict_ids": (CONFLICTS[0].card.card_id,),
        "intrigue_deck": intrigue_deck_instance_ids(False)[:4],
        "players": (owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        "tech_stacks": stacks,
        "decision_stack": (
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    }
    values.update(overrides)
    return GameState(**values)  # type: ignore[arg-type]


def _owner(**overrides: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": 0,
        "hand": starting_deck_instance_ids(0)[:5],
        "deck": starting_deck_instance_ids(0)[5:],
        "resources": Resources(solari=4, spice=6, water=2),
    }
    values.update(overrides)
    return PlayerState(**values)  # type: ignore[arg-type]


def _visit(state: GameState, space_id: str) -> GameState:
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )
    state = apply_agent_action(state, action).state
    for board_action in legal_board_effect_actions(state, 0):
        state = resolve_board_effect(state, board_action).state
    return state


def _tech_actions(state: GameState) -> dict[str, DomainAction]:
    actions: dict[str, DomainAction] = {}
    for action in legal_tech_acquisition_actions(state, 0):
        arguments = dict(action.arguments)
        key = str(arguments.get("tech_id", action.action_id))
        extra = tuple(
            f"{name}={value}"
            for name, value in sorted(arguments.items())
            if name != "tech_id"
        )
        actions[":".join((key, *extra)) if extra else key] = action
    return actions


def _purchase_and_resolve(state: GameState, action: DomainAction) -> RuleResult:
    """Buy, then explicitly resolve the queued icons for reward tests."""

    result = apply_tech_acquisition(state, action)
    events = list(result.events)
    while actions := legal_tech_acquire_effect_actions(result.state, 0):
        resolved = apply_tech_acquire_effect(result.state, actions[0])
        events.extend(resolved.events)
        result = resolved
    return RuleResult(state=result.state, events=tuple(events))


def _resolve_acquired(state: GameState, **choices: object) -> GameState:
    """Take queued rewards before testing their downstream interactions."""

    while actions := legal_tech_acquire_effect_actions(state, 0):
        action = next(
            action
            for action in actions
            if all(dict(action.arguments).get(k, v) == v for k, v in choices.items())
        )
        state = apply_tech_acquire_effect(state, action).state
    return state


def _acquire(state: GameState, key: str) -> GameState:
    tech_id, *options = key.split(":")
    choices: dict[str, object] = {
        k: v for k, v in (option.split("=") for option in options)
    }
    if choices.get("destroy_shield_wall") == "True":
        choices["destroy_shield_wall"] = True
    purchase = next(
        action
        for action in legal_tech_acquisition_actions(state, 0)
        if dict(action.arguments).get("tech_id") == tech_id
        and (
            "post_id" not in choices
            or dict(action.arguments).get("post_id") == choices["post_id"]
        )
    )
    bought = apply_tech_acquisition(state, purchase).state
    return _resolve_acquired(bought, **choices)

# --- content -----------------------------------------------------------------


def test_eighteen_tiles_are_transcribed_and_choam_transports_is_choam_only() -> None:
    assert len(TECH_TILES) == 18
    assert len(set(TECH_IDS)) == 18
    assert [tile.tech_id for tile in TECH_TILES if tile.choam_only] == [
        "choam_transports"
    ]
    assert len(tech_tiles_for(False)) == 17
    assert len(tech_tiles_for(True)) == 18
    # The Rival markers (solo only) sit on eleven tiles.
    assert sum(tile.rival for tile in TECH_TILES) == 11
    assert [tile.tech_id for tile in TECH_TILES if tile.flips] == [
        "advanced_data_analysis",
        "rapid_dropships",
        "spy_drones",
    ]
    assert TECH_TILES_BY_ID["sardaukar_high_command"].cost == 7
    assert TECH_TILES_BY_ID["training_depot"].cost == 1


# --- setup -------------------------------------------------------------------


def test_setup_deals_three_face_down_stacks_of_six() -> None:
    state = create_initial_state(TECH_CHOAM, seed=3, leader_ids=LEADERS).state

    assert tuple(len(stack) for stack in state.tech_stacks) == (6, 6, 6)
    dealt = [tech_id for stack in state.tech_stacks for tech_id in stack]
    assert sorted(dealt) == sorted(TECH_IDS)
    assert state.tech_trash == ()
    assert all(player.tech_ids == () for player in state.players)


def test_setup_without_choam_excludes_choam_transports_and_splits_six_six_five() -> (
    None
):
    state = create_initial_state(TECH, seed=3, leader_ids=LEADERS).state

    assert tuple(len(stack) for stack in state.tech_stacks) == (6, 6, 5)
    assert "choam_transports" not in [t for stack in state.tech_stacks for t in stack]


def test_setup_without_the_tech_module_has_no_tiles() -> None:
    bloodlines_only = create_initial_state(
        RulesetConfig(bloodlines=True), seed=3, leader_ids=LEADERS
    ).state
    assert bloodlines_only.tech_stacks == ()
    with pytest.raises(ValueError, match="require the Tech Module"):
        replace(bloodlines_only, tech_trash=("glowglobes",))
    with pytest.raises(ValueError, match="Tech Module"):
        RulesetConfig(tech_module=True)


def test_draft_setup_deals_the_stacks_too() -> None:
    state = create_draft_initial_state(
        RulesetConfig(bloodlines=True, tech_module=True, leader_draft=True), seed=5
    ).state
    assert tuple(len(stack) for stack in state.tech_stacks) == (6, 6, 5)


def test_a_tile_cannot_occupy_two_zones() -> None:
    state = _turn_state(_owner())
    with pytest.raises(ValueError, match="two zones"):
        replace(state, tech_trash=("glowglobes",))
    with pytest.raises(ValueError, match="held tiles"):
        PlayerState(player_id=0, tech_flipped=("glowglobes",))


# --- acquiring from a Landsraad visit ---------------------------------------


def test_paying_spice_for_a_tile_does_not_undo_spice_gained_this_turn() -> None:
    # Leverage: "If you gained spice this turn:" [Leverage card]; spending
    # it later does not un-gain it (designer ruling, designer-rulings-audit
    # "Leverage는 실제 spice 획득 필요"), and Harvest Contracts count every
    # gain of the turn [Main p. 16]. The Tech price was taken from the Spice
    # without being recorded as spent, so it hid the turn's gains.
    from dune_imperium.content.uprising.effect_dsl import GainedSpiceThisTurn
    from dune_imperium.rules.effect_interpreter import condition_holds
    from dune_imperium.rules.effects import spice_gained_this_turn

    owner = _owner(
        resources=Resources(solari=4, spice=6, water=2), spice_at_turn_start=4
    )
    state = _visit(_turn_state(owner, config=TECH_CHOAM), "assembly_hall")
    assert spice_gained_this_turn(state.players[0]) == 2

    bought = _acquire(state, "glowglobes:faction=fremen")
    seat = bought.players[0]
    assert seat.resources.spice == 4
    assert seat.spice_spent_turn == 2
    assert spice_gained_this_turn(seat) == 2
    # Leverage's own condition; the Agent turn has closed, so it is checked
    # directly rather than through the Plot window.
    assert condition_holds(bought, 0, GainedSpiceThisTurn(1))


def test_a_tile_bought_mid_placement_still_counts_toward_a_harvest_contract() -> None:
    # A Harvest contract is met by "sending an Agent to a Maker board space
    # and gaining the amount of spice shown during that turn (in total,
    # including from sources other than the space itself)" [Main p. 16]
    # (docs/rules/choam-module.md). The gain is the Spice now, less the Spice
    # at the turn's start, plus what was spent during it; a Tech tile bought
    # through Rapid Engineering's frame on top of the Agent turn must be
    # recorded as spent (``spice_spent_turn``), or its price hides gains.
    from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
    from dune_imperium.rules.contracts import legal_contract_completion_actions

    def card(card_id: str) -> str:
        return next(
            instance
            for instance in imperium_deck_instance_ids(True)
            if f":{card_id}:" in instance
        )

    desert_power = card("desert_power")
    owner = PlayerState(
        player_id=0,
        hand=(desert_power, card("smuggler_s_haven")),
        deck=(card("smuggler_s_harvester"),),
        intrigue_cards=("intrigue:rapid_engineering:0",),
        active_contract_ids=("contract:harvest_4",),
        resources=Resources(water=1),
    )
    state = _turn_state(
        owner,
        stacks=(("gene_locked_vault",), ("glowglobes",), ("plasteel_blades",)),
        config=TECH_CHOAM,
    )
    engine = UprisingRulesEngine()

    def take(current: GameState, action_id: str, **arguments: object) -> GameState:
        action = next(
            action
            for action in engine.legal_actions(current, 0)
            if action.action_id == action_id
            and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
        )
        return engine.apply(current, action).state

    placed = take(state, "agent_turn", card_id=desert_power, space_id="hagga_basin")
    gained = take(placed, "resolve_agent_card_effect")  # Desert Power: +2 spice
    plotted = take(take(gained, "play_intrigue"), "choose_intrigue_discard")
    bought = take(plotted, "acquire_tech", tech_id="gene_locked_vault")
    bought = take(bought, "resolve_tech_acquire_effect", choice="card")

    assert bought.decision_stack[-1].kind == "agent_effects"
    assert bought.players[0].spice_spent_turn == 1
    harvested = take(bought, "harvest_maker_spice")
    # 2 + 2 Spice gained this turn, 3 left after the tile.
    assert harvested.players[0].resources.spice == 3
    assert [
        dict(action.arguments)["instance_id"]
        for action in legal_contract_completion_actions(harvested, 0)
    ] == ["contract:harvest_4"]


def test_a_landsraad_visit_offers_the_face_up_tiles_the_owner_can_afford() -> None:
    state = _visit(_turn_state(_owner(resources=Resources(spice=2))), "assembly_hall")

    offered = _tech_actions(state)
    # Reward choices wait until after purchase (OQ-098). Advanced Data
    # Analysis still needs a placed Spy as part of its purchase cost. The
    # visit's "may acquire" offers no refusal: left unused it lapses at the
    # turn end (OQ-095 (2), user ruling 2026-10-14; codec v146).
    assert "decline_tech" not in offered
    assert "glowglobes" in offered
    assert "gene_locked_vault" in offered
    assert not any(key.startswith("advanced_data_analysis") for key in offered)


def test_a_non_landsraad_visit_offers_no_tile() -> None:
    from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
    from dune_imperium.content.uprising.types import AgentIcon

    state = _turn_state(_owner(hand=starting_deck_instance_ids(0), deck=()))
    space_id = next(
        str(dict(action.arguments)["space_id"])
        for action in legal_agent_actions(state, 0)
        if BOARD_SPACES_BY_ID[str(dict(action.arguments)["space_id"])].agent_icon
        is not AgentIcon.LANDSRAAD
    )
    state = _visit(state, space_id)
    assert legal_tech_acquisition_actions(state, 0) == ()


@pytest.mark.parametrize(
    ("space_id", "printed_key"),
    [
        ("high_council", "high_council"),
        # The optional Intrigue trade, the recall and its own card draw (user
        # rulings 2026-10-10, OQ-027 (d), and 2026-10-14, OQ-095 (2)).
        (
            "imperial_privilege",
            "imperial_privilege_intrigue,imperial_privilege,cards",
        ),
        ("swordmaster", "swordmaster"),
    ],
)
def test_every_landsraad_visit_offers_acquire_tech(
    space_id: str, printed_key: str
) -> None:
    # "The Ixian Embassy board gives you this option each time you send an
    # Agent to a [Landsraad] board space" [Bloodlines p. 12]; the spaces
    # whose printed effect is a special key (a first High Council seat,
    # Imperial Privilege's Intrigue slot and recall beside its card draw,
    # the Swordmaster) are Landsraad spaces too.
    owner = _owner(
        resources=Resources(solari=10, spice=6, water=2),
        influence=Influence(emperor=2),
    )
    placed = apply_agent_action(
        _turn_state(owner),
        next(
            action
            for action in legal_agent_actions(_turn_state(owner), 0)
            if dict(action.arguments)["space_id"] == space_id
        ),
    ).state
    icons = dict(placed.decision_stack[-1].context)["pending_board_icons"]
    assert icons == f"{printed_key},tech"
    offered = _tech_actions(placed)
    assert "decline_tech" not in offered  # OQ-095 (2), user ruling 2026-10-14
    assert "glowglobes" in offered


def test_a_first_high_council_visit_buys_tech_at_the_new_seat_discount() -> None:
    # "It's Brennen's Agent turn, and he sends an Agent to High Council ...
    # He places his Councilor token on a Council seat. High Council is a
    # [Landsraad] board space, so Brennen can use the Ixian Embassy to
    # acquire a Tech tile. Because he now has a High Council seat, the Tech
    # tile costs him 1 less Spice. He pays 1 spice to acquire Glowglobes"
    # [Bloodlines p. 7].
    owner = _owner(resources=Resources(solari=5, spice=1, water=2))
    state = _visit(_turn_state(owner), "high_council")
    assert state.players[0].high_council
    bought = _acquire(state, "glowglobes:faction=fremen")
    seat = bought.players[0]
    assert seat.tech_ids == ("glowglobes",)
    assert seat.resources.spice == 0
    assert seat.influence.fremen == 1


def test_acquiring_pays_spice_reveals_the_next_tile_and_pays_the_acquire_effect() -> (
    None
):
    state = _visit(_turn_state(_owner()), "assembly_hall")

    bought = _acquire(state, "glowglobes:faction=fremen")
    owner = bought.players[0]
    assert owner.resources.spice == 6 - 2
    assert owner.tech_ids == ("glowglobes",)
    assert owner.influence.fremen == 1
    assert bought.tech_stacks[0] == ("training_depot", "panopticon")
    # The offer is spent: a second acquisition needs another Landsraad visit.
    assert legal_tech_acquisition_actions(bought, 0) == ()


def test_a_high_council_seat_discounts_every_tile_by_one_spice() -> None:
    owner = _owner(high_council=True, resources=Resources(spice=1))
    state = _visit(_turn_state(owner), "assembly_hall")

    offered = _tech_actions(state)
    assert "gene_locked_vault" in offered
    assert tech_cost(owner, TECH_TILES_BY_ID["training_depot"]) == 0
    bought = _acquire(state, "gene_locked_vault:choice=card")
    seat = bought.players[0]
    assert seat.resources.spice == 0
    assert len(seat.hand) == 4 + 1  # one card played, one drawn


def test_an_unused_offer_keeps_the_stacks_and_lapses_at_the_turn_end() -> None:
    # The visit's Acquire Tech is optional [Bloodlines p. 7]: since the user
    # ruling of 2026-10-14 (OQ-095 (2)) it offers no ``decline_tech`` row,
    # holds no turn end back, and the owner's press lapses it.
    state = _visit(_turn_state(_owner()), "assembly_hall")
    engine = UprisingRulesEngine()
    assert DomainAction("finish_agent_turn", 0) in engine.legal_actions(state, 0)
    finished = finish_agent_turn_result(state)
    lapsed = [
        dict(event.payload)
        for event in finished.events
        if event.kind == "board_effect_lapsed"
    ]
    assert lapsed == [{"effect": "tech", "player": 0, "space_id": "assembly_hall"}]
    assert "tech_declined" not in {event.kind for event in finished.events}
    assert finished.state.tech_stacks == STACKS
    assert finished.state.players[0].tech_ids == ()
    assert legal_tech_acquisition_actions(finished.state, 0) == ()


def test_an_emptied_stack_simply_offers_fewer_choices() -> None:
    state = _visit(
        _turn_state(_owner(), stacks=(("training_depot",), (), ("plasteel_blades",))),
        "assembly_hall",
    )
    bought = _acquire(state, "training_depot")
    assert bought.tech_stacks == ((), (), ("plasteel_blades",))
    assert observe_state(bought, 1).tech_face_up == ("", "", "plasteel_blades")


# --- acquire effects -----------------------------------------------------------


def test_advanced_data_analysis_trashes_a_placed_spy_to_the_box() -> None:
    owner = _owner(spies_supply=1, spy_post_ids=(LANDSRAAD_POST, SIETCH_POST))
    state = _visit(
        _turn_state(owner, stacks=(("advanced_data_analysis",), (), ())),
        "assembly_hall",
    )
    offered = _tech_actions(state)
    assert set(offered) == {
        f"advanced_data_analysis:post_id={LANDSRAAD_POST}",
        f"advanced_data_analysis:post_id={SIETCH_POST}",
    }
    bought = _acquire(state, f"advanced_data_analysis:post_id={SIETCH_POST}")
    seat = bought.players[0]
    assert seat.spy_post_ids == (LANDSRAAD_POST,)
    assert seat.spies_supply == 1
    assert seat.spies_boxed == 1
    assert seat.tech_ids == ("advanced_data_analysis",)


def test_forbidden_weapons_recruits_a_deployable_troop_and_may_drop_the_wall() -> None:
    # A Combat icon gained before the placement (Adaptive Tactics) keeps the
    # deployment window open, so the tile's troop shows up as recruited.
    state = _visit(
        _turn_state(
            _owner(combat_icon_turn=True), stacks=(("forbidden_weapons",), (), ())
        ),
        "assembly_hall",
    )
    offered = _tech_actions(state)
    assert "forbidden_weapons" in offered
    kept = _acquire(state, "forbidden_weapons")
    assert kept.shield_wall_present
    assert kept.players[0].troops_garrison == 3 + 1
    # The troop counts as recruited this turn [Bloodlines p. 7] [FAQ p. 4].
    assert dict(kept.decision_stack[-1].context).get("troops_recruited") == 1

    bought = apply_tech_acquisition(state, offered["forbidden_weapons"]).state
    destroy = next(
        action for action in legal_tech_acquire_effect_actions(bought, 0)
        if dict(action.arguments).get("destroy_shield_wall") is True
    )
    destroyed = apply_tech_acquire_effect(bought, destroy)
    assert not destroyed.state.shield_wall_present
    assert any(event.kind == "shield_wall_destroyed" for event in destroyed.events)



def test_a_plot_tiles_troops_join_the_turn_before_the_placement() -> None:
    # "그 turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에 deploy할 수
    # 있다" [Main p. 10] [FAQ p. 4] (docs/rules/player-turns.md). Rapid
    # Engineering (a Plot) buys Rapid Dropships ("troop 2", bloodlines.md
    # Tech table) before the Agent goes out; the two troops used to reach
    # the garrison without counting as this turn's recruits.
    from dune_imperium.rules.combat_deployment import legal_combat_deployments
    from dune_imperium.rules.intrigue import (
        apply_intrigue_choice,
        apply_intrigue_play,
        legal_intrigue_choice_actions,
        legal_intrigue_play_actions,
    )

    card = "intrigue:rapid_engineering:0"
    state = _turn_state(
        _owner(intrigue_cards=(card,)), stacks=(("rapid_dropships",), (), ())
    )
    played = apply_intrigue_play(state, legal_intrigue_play_actions(state, 0)[0])
    chosen = apply_intrigue_choice(
        played.state, legal_intrigue_choice_actions(played.state, 0)[0]
    ).state
    bought = _acquire(chosen, "rapid_dropships")
    turn = bought.decision_stack[-1]
    assert turn.kind == "turn"
    assert bought.players[0].troops_garrison == 3 + 2
    assert dict(turn.context)["troops_recruited"] == 2

    placement = next(
        action
        for action in legal_agent_actions(bought, 0)
        if dict(action.arguments)["space_id"] == "desert_tactics"
    )
    placed = apply_agent_action(bought, placement).state
    counts = {
        dict(action.arguments)["count"]
        for action in legal_combat_deployments(placed, 0)
    }
    # Two recruited plus up to two more from the garrison [Main p. 10].
    assert counts == {1, 2, 3, 4}


def test_without_the_wall_the_detonation_variant_disappears() -> None:
    # Forbidden Weapons prints the Shield Wall detonation icon; Servo-
    # Receivers (which this test used before) prints the Signet Ring icon
    # instead [Servo-Receivers Tech tile].
    state = _visit(
        _turn_state(
            _owner(), stacks=(("forbidden_weapons",), (), ()), shield_wall_present=False
        ),
        "assembly_hall",
    )
    assert set(_tech_actions(state)) == {"forbidden_weapons"}


# --- Servo-Receivers: the Signet Ring icon ------------------------------------
#
# The acquire box prints the brown-gold Signet Ring icon: "you use the
# Signet Ring ability (with the corresponding icon) on your Leader"
# [Main p. 20] [Servo-Receivers Tech tile]. It is not the Shield Wall
# detonation icon Forbidden Weapons prints.

SERVO_STACKS = (("servo_receivers",), (), ())


def _decider(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _end_open_agent_turn(state: GameState) -> GameState:
    # Every Agent turn ends only through its owner's "턴 종료", even with
    # nothing left to resolve (OQ-095 (1)): the owner's Agent-turn frame
    # stays on top with the end offered, and pressing it opens the next
    # unrevealed seat's turn.
    # A draw a trigger earned in the turn (Steersman Y'rkoon's Hungry for
    # Spice on a seat built with spice and no turn-start snapshot) is taken
    # first: it waits as the owner's own step (user ruling 2026-10-10,
    # OQ-106).
    assert state.decision_stack[-1].kind == "agent_effects"
    owner = _decider(state)
    engine = UprisingRulesEngine()
    while draws := [
        action
        for action in engine.legal_actions(state, owner)
        if action.action_id in ("draw_owed_card", "draw_owed_intrigue")
    ]:
        state = engine.apply(state, draws[0]).state
    assert DomainAction("finish_agent_turn", owner) in (
        engine.legal_actions(state, owner)
    )
    ended: GameState = finish_agent_turn(state)
    return ended


def _servo_visit(leader_id: str, **overrides: object) -> GameState:
    return _visit(
        _turn_state(_owner(leader_id=leader_id, **overrides), stacks=SERVO_STACKS),
        "assembly_hall",
    )


def test_servo_receivers_uses_the_leaders_signet_ring_ability() -> None:
    state = _servo_visit("gurney_halleck")
    # No Shield Wall variant, though the wall stands.
    assert state.shield_wall_present
    assert set(_tech_actions(state)) == {"servo_receivers"}
    result = _purchase_and_resolve(state, _tech_actions(state)["servo_receivers"])
    seat = result.state.players[0]
    # Warmaster: recruit one troop [Gurney Halleck card].
    assert seat.troops_garrison == state.players[0].troops_garrison + 1
    assert result.state.shield_wall_present
    assert [event.kind for event in result.events][-2:] == [
        "leader_signet_started",
        "leader_signet_resolved",
    ]
    # The tile is named by its tech_id like tech_acquired, so the log shows
    # its name rather than an engine id (scripts/e2e/log_words.py).
    assert dict(result.events[-2].payload) == {
        "player": 0,
        "tech_id": "servo_receivers",
    }
    # The ability's own event names the tile the same way, not the Signet
    # frame's internal card id.
    assert dict(result.events[-1].payload) == {
        "player": 0,
        "tech_id": "servo_receivers",
        "troops": 1,
    }
    # Nothing else was pending at Assembly Hall: the owner's turn stays open
    # until its end is pressed, which then moves on (OQ-095).
    assert _decider(result.state) == 0
    ended = _end_open_agent_turn(result.state)
    assert ended.decision_stack[-1].kind == "turn"
    assert _decider(ended) == 1

    drawn = _purchase_and_resolve(
        _servo_visit("muad_dib"), _tech_actions(state)["servo_receivers"]
    ).state
    # Lead the Way: draw one card [Muad'Dib card].
    assert len(drawn.players[0].hand) == len(state.players[0].hand) + 1


def test_servo_receivers_opens_a_signet_choice_frame() -> None:
    engine = UprisingRulesEngine()
    state = _servo_visit("princess_irulan")
    opened = _resolve_acquired(
        engine.apply(state, _tech_actions(state)["servo_receivers"]).state
    )
    frame = opened.decision_stack[-1]
    assert frame.kind == "leader_signet"
    offered = {action.action_id for action in engine.legal_actions(opened, 0)}
    # Chronicler's Insight: acquire a one-cost card, trash a hand card, or
    # neither [Princess Irulan card]; the turn waits for the choice.
    assert offered == {"decline_leader_signet_payment", "trash_leader_card"}
    trash = next(
        action
        for action in engine.legal_actions(opened, 0)
        if action.action_id == "trash_leader_card"
    )
    done = engine.apply(opened, trash).state
    assert dict(trash.arguments)["card_id"] in done.players[0].trashed
    assert all(frame.kind != "leader_signet" for frame in done.decision_stack)
    # Back in the owner's open Agent turn; its end hands over (OQ-095).
    assert _decider(done) == 0
    assert _decider(_end_open_agent_turn(done)) == 1


def test_servo_receivers_signet_reads_the_agent_turns_space() -> None:
    # Judge of the Change: "If you sent an Agent this turn to... [Landsraad]:
    # [Emperor] 2 Influence: [water]" [Liet Kynes card].
    liet = _servo_visit("liet_kynes", influence=Influence(emperor=2))
    bought = _purchase_and_resolve(liet, _tech_actions(liet)["servo_receivers"])
    assert bought.state.players[0].resources.water == 2 + 1


def test_servo_receivers_lets_duncan_send_a_second_agent_into_the_fray() -> None:
    # Into the Fray: "You may take the Agent you sent this turn and deploy
    # it to the Conflict as a 2 strength unit that can't be retreated"
    # [Duncan Idaho card]. Servo-Receivers uses that ability again on a
    # later Agent turn [Main p. 20] [Servo-Receivers Tech tile], and the
    # Agent sent on that turn is a different one: it joins the first
    # (OQ-037(e)). Before, the engine kept the one-Agent counter at 1 and
    # lost this Agent (checked sweep: bloodlines+tech+draft seed 1003).
    engine = UprisingRulesEngine()
    state = _servo_visit("duncan_idaho", agent_in_conflict=1, agents_available=1)
    opened = _resolve_acquired(
        engine.apply(state, _tech_actions(state)["servo_receivers"]).state
    )
    assert opened.decision_stack[-1].kind == "leader_signet"
    deploy = next(
        action
        for action in engine.legal_actions(opened, 0)
        if action.action_id == "deploy_leader_agent"
    )
    fighting = engine.apply(opened, deploy).state
    seat = fighting.players[0]
    assert seat.agent_in_conflict == 2
    assert seat.agent_locations == ()
    assert seat.agents_available == 0
    assert seat.units_in_conflict == 2
    assert units_strength(seat) == 2 + 2
    assert all(frame.kind != "leader_signet" for frame in fighting.decision_stack)


def test_servo_into_the_fray_agent_is_not_imperial_privileges_other_agent() -> None:
    # Imperial Privilege: "Recall one of your other Agents from the board,
    # and draw a card." [Board Guide p. 2]; docs/rules/board-spaces.md:
    # "이번 turn에 보낸 Agent가 아닌 자신의 다른 Agent 1개를 recall", and an
    # Into the Fray Agent may be recalled "뒤의 turn에" (on a later turn,
    # OQ-037 (d)). The Ixian Embassy icon on the space lets Duncan buy
    # Servo-Receivers and move this turn's Agent into the Conflict before
    # the recall; that Agent used to be the only (forced) recall target.
    engine = UprisingRulesEngine()
    state = _visit(
        _turn_state(
            _owner(
                leader_id="duncan_idaho",
                influence=Influence(emperor=2),
                resources=Resources(solari=4, spice=6, water=2),
            ),
            stacks=SERVO_STACKS,
        ),
        "imperial_privilege",
    )
    opened = _resolve_acquired(
        engine.apply(state, _tech_actions(state)["servo_receivers"]).state
    )
    assert opened.decision_stack[-1].kind == "leader_signet"
    deploy = next(
        action
        for action in engine.legal_actions(opened, 0)
        if action.action_id == "deploy_leader_agent"
    )
    deployed = engine.apply(opened, deploy)
    fighting = deployed.state
    assert fighting.players[0].agent_in_conflict == 1
    hand_before = len(fighting.players[0].hand)

    # The optional Intrigue trade no longer gates the recall (OQ-095 (2),
    # user ruling 2026-10-14), so the recall step is offered at once.
    legal = {action.action_id for action in engine.legal_actions(fighting, 0)}
    assert "recall_conflict_agent_for_imperial_privilege" not in legal
    # With no other Agent the owner confirms the skipped recall (user ruling
    # 2026-09-30); the card is still drawn (OQ-023), by the space's own icon
    # since the user ruling of 2026-10-10 (OQ-027 (d)), which ``_visit``
    # resolved with the visit's other automatic icons, so the confirm draws
    # nothing more.
    assert "resolve_imperial_privilege_without_recall" in legal
    confirmed = engine.apply(
        fighting,
        DomainAction(action_id="resolve_imperial_privilege_without_recall", actor=0),
    )

    seat = confirmed.state.players[0]
    assert seat.agent_in_conflict == 1
    assert seat.agents_available == 1
    assert len(seat.hand) == hand_before
    assert "imperial_privilege_recall_skipped" in {
        event.kind for event in confirmed.events
    }
    assert "resolve_board_effect" not in {
        action.action_id for action in engine.legal_actions(confirmed.state, 0)
    }


def test_steersman_recall_never_offers_its_own_into_the_fray_agent() -> None:
    # Review round 1 major finding: Steersman's own Agent can reach the
    # Conflict this very turn too, when Servo-Receivers' Signet Ring icon
    # outside the printed card (OQ-037 (e), OQ-062) sends it Into the Fray
    # while Steersman's own Recall Agent icon [Main p. 20] is still pending.
    # With nothing else recallable the icon must offer nothing, never this
    # turn's own Agent (2026-09-26 user ruling, OQ-068); with an earlier
    # turn's Conflict Agent also present, exactly that one comes back.
    from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids

    steersman = next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if ":steersman:" in instance_id
    )
    engine = UprisingRulesEngine()

    def _fray(agent_in_conflict: int, agents_available: int) -> GameState:
        owner = _owner(
            leader_id="duncan_idaho",
            hand=(steersman,),
            agent_in_conflict=agent_in_conflict,
            agents_available=agents_available,
        )
        state = _turn_state(owner, stacks=SERVO_STACKS)
        placement = next(
            action
            for action in engine.legal_actions(state, 0)
            if dict(action.arguments).get("space_id") == "assembly_hall"
        )
        placed = engine.apply(state, placement).state
        acquire = next(
            action
            for action in engine.legal_actions(placed, 0)
            if action.action_id == "acquire_tech"
        )
        opened = _resolve_acquired(engine.apply(placed, acquire).state)
        deploy = next(
            action
            for action in engine.legal_actions(opened, 0)
            if action.action_id == "deploy_leader_agent"
        )
        return engine.apply(opened, deploy).state

    alone = _fray(agent_in_conflict=0, agents_available=2)
    assert alone.players[0].agent_in_conflict == 1
    assert alone.players[0].agent_locations == ()
    assert "recall_conflict_agent_for_agent_card" not in {
        action.action_id for action in engine.legal_actions(alone, 0)
    }

    fighting = _fray(agent_in_conflict=1, agents_available=1)
    assert fighting.players[0].agent_in_conflict == 2
    recall = next(
        action
        for action in engine.legal_actions(fighting, 0)
        if action.action_id == "recall_conflict_agent_for_agent_card"
    )
    result = engine.apply(fighting, recall).state
    assert result.players[0].agent_in_conflict == 1
    assert result.players[0].agents_available == 1


def test_choam_demands_recall_reward_fizzles_after_its_own_into_the_fray() -> None:
    # Review round 1 major finding: CHOAM Demands' "Complete one of your
    # contracts." [CHOAM Demands card] Agent-box completion resolves
    # (apply_agent_card_contract_completion in agent_effects.py) through a
    # turn-Agent-in-Conflict computation separate from a board-space
    # completion (apply_contract_completion in contracts.py). Buying
    # Servo-Receivers from the same Assembly Hall visit sends CHOAM Demands'
    # own Agent Into the Fray before its box resolves; with no earlier
    # turn's Conflict Agent and no board Agent, Sardaukar II's "recall one of
    # your Agents" [Main p. 20] reward must still fizzle, never targeting
    # this turn's own Agent (OQ-037 (d), extended to every Recall Agent
    # effect by the 2026-09-26 user ruling, OQ-068).
    from dune_imperium.rules.agent_effects import (
        apply_agent_card_contract_completion,
        legal_agent_card_contract_completion_actions,
    )
    from dune_imperium.rules.contracts import (
        apply_contract_recall_action,
        legal_contract_recall_actions,
    )

    choam_demands = "imperium:choam_demands:0"
    engine = UprisingRulesEngine()
    owner = PlayerState(
        player_id=0,
        leader_id="duncan_idaho",
        hand=(choam_demands,),
        resources=Resources(solari=4, spice=6, water=2),
        agent_in_conflict=0,
        agents_available=2,
        active_contract_ids=("contract:sardaukar_ii",),
    )
    state = _turn_state(owner, stacks=SERVO_STACKS, config=TECH_CHOAM)
    placement = next(
        action
        for action in engine.legal_actions(state, 0)
        if dict(action.arguments).get("space_id") == "assembly_hall"
    )
    placed = engine.apply(state, placement).state
    acquire = next(
        action
        for action in engine.legal_actions(placed, 0)
        if action.action_id == "acquire_tech"
    )
    opened = _resolve_acquired(engine.apply(placed, acquire).state)
    deploy = next(
        action
        for action in engine.legal_actions(opened, 0)
        if action.action_id == "deploy_leader_agent"
    )
    fighting = engine.apply(opened, deploy).state
    assert fighting.players[0].agent_locations == ()
    assert fighting.players[0].agent_in_conflict == 1

    completion = legal_agent_card_contract_completion_actions(fighting, 0)[0]
    completed = apply_agent_card_contract_completion(fighting, completion)

    # The reward's recall window opens with only the confirm (user ruling
    # 2026-09-30); confirming fizzles it.
    confirm = DomainAction(action_id="resolve_contract_without_recall", actor=0)
    assert completed.state.decision_stack[-1].kind == "contract_reward_recall"
    assert legal_contract_recall_actions(completed.state, 0) == (confirm,)
    fizzled = apply_contract_recall_action(completed.state, confirm)
    assert any(
        event.kind == "contract_recall_unavailable" for event in fizzled.events
    )
    assert fizzled.state.decision_stack[-1].kind == "agent_effects"
    assert fizzled.state.players[0].agent_in_conflict == 1


def test_steersman_y_rkoon_has_no_signet_ring_ability_to_use() -> None:
    # Plot Course sits where a Signet Ring ability would be but prints none
    # [Steersman Y'rkoon card] (OQ-062). The spice held at the turn's start
    # is no gain: no Hungry for Spice card waits in the turn (OQ-106).
    state = _servo_visit("steersman_y_rkoon", spice_at_turn_start=6)
    result = _purchase_and_resolve(state, _tech_actions(state)["servo_receivers"])
    assert "servo_receivers" in result.state.players[0].tech_ids
    assert result.events[-1].kind == "leader_signet_unavailable"
    assert _decider(result.state) == 0
    assert _decider(_end_open_agent_turn(result.state)) == 1


def test_servo_receivers_signet_outside_an_agent_turn() -> None:
    # A card-granted Acquire Tech in the Reveal turn (Rapid Engineering) or
    # in Combat (Battlefield Research) uses the ability with no Agent sent
    # this turn (OQ-062): Warmaster's troop joins the Reveal's recruits.
    owner = _owner(leader_id="gurney_halleck")
    state = _turn_state(owner, stacks=SERVO_STACKS)
    revealed = _reveal(state).state
    opened = push_tech_acquisition(revealed, 0, discount=1, source="test").state
    bought = _purchase_and_resolve(
        opened, _tech_actions(opened)["servo_receivers"]
    ).state
    assert bought.decision_stack[-1].kind == "reveal"
    assert bought.players[0].troops_garrison == owner.troops_garrison + 1
    assert dict(bought.decision_stack[-1].context)["reveal_troops_recruited"] == 1

    liet = _turn_state(
        _owner(leader_id="liet_kynes", influence=Influence(emperor=2)),
        stacks=SERVO_STACKS,
    )
    liet_opened = push_tech_acquisition(
        _reveal(liet).state, 0, discount=1, source="t"
    ).state
    liet_bought = _purchase_and_resolve(
        liet_opened, _tech_actions(liet_opened)["servo_receivers"]
    ).state
    assert liet_bought.players[0].resources.water == 2


_SERVO_SPY_SETUPS: dict[str, dict[str, object]] = {
    "spies_in_supply": {"spies_supply": 3},
    # Every Spy already out: the Spy-placing Signets (Feyd, Fenring, Staban,
    # Margot) must resolve through their recall-first or no-Spy branches.
    "spies_on_posts": {
        "spies_supply": 0,
        "spy_post_ids": (
            "arrakis-deep-desert",
            "fremen-desert-tactics-fremkit",
            "emperor-sardaukar-dutiful-service",
        ),
    },
}


@pytest.mark.parametrize("spies", sorted(_SERVO_SPY_SETUPS))
@pytest.mark.parametrize("host", ["landsraad", "reveal"])
@pytest.mark.parametrize("leader_id", sorted(IMPLEMENTED_ABILITY_LEADER_IDS))
def test_every_servo_receivers_signet_choice_closes_its_own_frame(
    leader_id: str, host: str, spies: str
) -> None:
    # Servo-Receivers uses the Leader's Signet Ring ability [Main p. 20]
    # [Servo-Receivers Tech tile] in its own leader_signet frame (OQ-062).
    # Every choice path must close that frame and hand control back to the
    # host: the owner's open Agent turn after the Landsraad visit (whose
    # end, pressed by the owner, opens the next seat's turn: OQ-095), or the
    # owner's open Reveal turn. A Signet handler that writes through the
    # Agent box (advance_after_effect / current_agent_effect_context) instead of
    # _store_signet / _signet_context breaks this (merge guard for Signet
    # handler changes on other branches).
    engine = UprisingRulesEngine()
    codec = ActionCodec(TECH)
    owner = _owner(
        leader_id=leader_id,
        influence=Influence(emperor=2, fremen=2),
        troops_conflict=2,
        troops_supply=7,
        **_SERVO_SPY_SETUPS[spies],
    )
    if host == "landsraad":
        state = _visit(_turn_state(owner, stacks=SERVO_STACKS), "assembly_hall")
        expected = ("agent_effects", 0)
    else:
        revealed = _reveal(_turn_state(owner, stacks=SERVO_STACKS)).state
        state = push_tech_acquisition(revealed, 0, discount=1, source="t").state
        expected = ("reveal", 0)
    pending = [_resolve_acquired(
        engine.apply(state, _tech_actions(state)["servo_receivers"]).state
    )]
    leaves = 0
    while pending:
        current = pending.pop()
        if all(frame.kind != "leader_signet" for frame in current.decision_stack):
            leaves += 1
            assert (current.decision_stack[-1].kind, _decider(current)) == expected
            if host == "landsraad":
                ended = _end_open_agent_turn(current)
                assert (ended.decision_stack[-1].kind, _decider(ended)) == ("turn", 1)
            continue
        actions = engine.legal_actions(current, _decider(current))
        assert actions, "a leader_signet frame must offer a choice"
        for action in actions:
            assert codec.decode(codec.encode(action), action.actor) == action
            pending.append(engine.apply(current, action).state)
        assert leaves + len(pending) < 400, "Signet choices must terminate"
    assert leaves >= 1


@pytest.mark.parametrize(
    ("tech_id", "check"),
    [
        ("plasteel_blades", lambda seat: seat.resources.solari == 4 + 4),
        # Assembly Hall's own Intrigue draw plus the tile's two.
        ("self_destroying_messages", lambda seat: len(seat.intrigue_cards) == 1 + 2),
        (
            "sardaukar_high_command",
            lambda seat: seat.victory_points == 2 and seat.resources.spice == 12 - 7,
        ),
        ("delivery_bay", lambda seat: len(seat.hand) == 4 + 1),
        ("rapid_dropships", lambda seat: seat.troops_garrison == 3 + 2),
    ],
)
def test_resolved_acquire_effects(tech_id: str, check: object) -> None:
    owner = _owner(resources=Resources(solari=4, spice=12))
    state = _visit(_turn_state(owner, stacks=((tech_id,), (), ())), "assembly_hall")
    bought = _acquire(state, tech_id)
    assert check(bought.players[0])  # type: ignore[operator]
    assert bought.players[0].tech_ids == (tech_id,)


def test_planetary_array_queues_an_optional_trash_after_the_visit() -> None:
    # The tile's black trash icon is optional [FAQ p. 3]: in the owner's own
    # Agent turn it waits on the turn as rows, with no refusal (user decision
    # 2026-10-17, cleanup-2b; OQ-095 (2)).
    state = _visit(
        _turn_state(_owner(), stacks=(("planetary_array",), (), ())), "assembly_hall"
    )
    bought = _acquire(state, "planetary_array")
    top = bought.decision_stack[-1]
    assert top.kind == "agent_effects"
    assert [kind for kind, _source, _value in turn_rows.pending(top)] == [
        turn_rows.OPTIONAL_TRASH
    ]
    actions = legal_optional_trash_actions(bought, 0)
    assert {a.action_id for a in actions} == {"trash_optional_card"}
    assert len(actions) == 4 + 1  # hand (Dagger played) + played card
    # It holds no end: the press lapses it.
    assert not turn_rows.holds_the_end(bought, 0)


def test_planetary_array_last_effect_trash_credits_this_turn() -> None:
    # Planetary Array bought as the Agent turn's very last effect, with
    # every other seat revealed (2026-09-26 review round 4 added this
    # scenario). The turn no longer closes with that effect: it stays open
    # until its owner presses the end, and a follow-up the last effect left
    # behind resolves inside it, so what it recruits counts for this turn
    # (user ruling OQ-095 (1), (3), docs/rules/open-questions.md). "그
    # turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에 deploy할 수
    # 있다." [Main p. 10] [FAQ p. 4] (docs/rules/player-turns.md:137):
    # Eliminate Allies' trash troops join this turn's recruits. The end then
    # reopens this same seat's next turn with a fresh count.
    eliminate_allies = "imperium:eliminate_allies:0"
    owner = _owner(hand=(*starting_deck_instance_ids(0)[:5], eliminate_allies))
    state = _turn_state(
        owner,
        stacks=(("planetary_array",), (), ()),
        players=(
            owner,
            PlayerState(player_id=1, has_revealed=True),
            PlayerState(player_id=2, has_revealed=True),
            PlayerState(player_id=3, has_revealed=True),
        ),
    )
    visited = _visit(state, "assembly_hall")
    bought = _acquire(visited, "planetary_array")
    # The trash offer waits on the owner's still-open Agent turn.
    waiting = bought.decision_stack[-1]
    assert waiting.kind == "agent_effects"
    assert isinstance(waiting.decision, PlayerDecision)
    assert waiting.decision.owner == 0
    assert [kind for kind, _source, _value in turn_rows.pending(waiting)] == [
        turn_rows.OPTIONAL_TRASH
    ]

    trash = next(
        a
        for a in legal_optional_trash_actions(bought, 0)
        if dict(a.arguments).get("card_id") == eliminate_allies
    )
    trashed = apply_optional_trash(bought, trash).state

    assert trashed.players[0].troops_garrison == 3 + 2
    assert _decider(trashed) == 0
    assert dict(trashed.decision_stack[-1].context)["troops_recruited"] == 2

    ended = _end_open_agent_turn(trashed)
    top = ended.decision_stack[-1]
    assert top.kind == "turn"
    assert dict(top.context)["turn_owner"] == 0
    assert dict(top.context).get("troops_recruited") in (None, 0)


def test_spy_drones_place_two_spies_with_deep_cover() -> None:
    others = tuple(
        replace(
            PlayerState(player_id=seat), spy_post_ids=(LANDSRAAD_POST,), spies_supply=2
        )
        if seat == 1
        else PlayerState(player_id=seat)
        for seat in range(1, 4)
    )
    state = _turn_state(_owner(), stacks=(("spy_drones",), (), ()))
    state = replace(state, players=(state.players[0], *others))
    state = _visit(state, "assembly_hall")
    bought = _acquire(state, "spy_drones")
    assert bought.decision_stack[-1].kind == "spy_placement"
    first = legal_spy_placement_actions(bought, 0)
    posts = {dict(action.arguments)["post_id"] for action in first}
    # Deep Cover ignores the opponent's Spy on the Landsraad post.
    assert LANDSRAAD_POST in posts and len(posts) == 13
    placed = apply_spy_placement(
        bought,
        next(a for a in first if dict(a.arguments)["post_id"] == LANDSRAAD_POST),
    ).state
    placed = _resolve_acquired(placed)
    second = legal_spy_placement_actions(placed, 0)
    assert LANDSRAAD_POST not in {dict(a.arguments)["post_id"] for a in second}
    done = apply_spy_placement(placed, second[0]).state
    assert done.players[0].spies_supply == 1
    # Both Spies placed, the owner's Agent turn is still open (OQ-095).
    assert _decider(done) == 0
    assert _end_open_agent_turn(done).decision_stack[-1].kind == "turn"


def test_a_spy_drones_recall_as_the_last_effect_counts_for_this_turn() -> None:
    # Spy Drones' acquire column prints two Spy with Deep Cover icons, and
    # its own flip reads "If you recalled a Spy this turn:" [Spy Drones Tech
    # tile]; with an empty supply "you may first recall one of your Spies
    # for no effect" [Main pp. 11, 20]. OQ-044 (d) counts "이번 Agent 또는
    # Reveal turn에 자신의 Spy를 supply로 되돌린 모든 경로", the recall-first
    # included. Bought as the turn's last effect by the last seat to
    # reveal, the tile no longer closes the turn: its Spies are placed on
    # the owner's still-open Agent turn, so the recall-first counts for this
    # turn (user ruling OQ-095 (3), docs/rules/open-questions.md), and the
    # end the owner presses reopens this seat's next turn with the counter
    # back at zero.
    posts = (
        "emperor-sardaukar-dutiful-service",
        "arrakis-hagga-basin",
        "arrakis-deep-desert",
    )
    state = _turn_state(
        _owner(spies_supply=0, spy_post_ids=posts),
        stacks=(("spy_drones",), (), ()),
    )
    state = replace(
        state,
        players=(
            state.players[0],
            *(replace(seat, has_revealed=True) for seat in state.players[1:]),
        ),
    )
    bought = _acquire(_visit(state, "assembly_hall"), "spy_drones")
    assert bought.decision_stack[-1].kind == "spy_placement"
    open_turn = bought.decision_stack[-2]
    assert open_turn.kind == "agent_effects"
    assert isinstance(open_turn.decision, PlayerDecision)
    assert open_turn.decision.owner == 0

    recall = next(
        action
        for action in legal_spy_placement_actions(bought, 0)
        if action.action_id == "recall_spy_for_placement"
    )
    recalled = apply_spy_placement(bought, recall).state
    placed = apply_spy_placement(
        recalled, legal_spy_placement_actions(recalled, 0)[0]
    ).state
    placed = _resolve_acquired(placed)
    decline = next(
        action
        for action in legal_spy_placement_actions(placed, 0)
        if action.action_id == "decline_spy_placement"
    )
    done = apply_spy_placement(placed, decline).state
    assert _decider(done) == 0
    assert done.players[0].spies_recalled_turn == 1
    ended = _end_open_agent_turn(done)
    assert ended.decision_stack[-1].kind == "turn"
    assert _decider(ended) == 0
    assert ended.players[0].spies_recalled_turn == 0

    # Bought through a Tech frame opened in the seat's own turn (a Plot, no
    # Agent-turn context), the recall-first is that turn's and still counts.
    opened = push_tech_acquisition(
        _turn_state(
            _owner(spies_supply=0, spy_post_ids=posts),
            stacks=(("spy_drones",), (), ()),
        ),
        0,
        discount=0,
        source="test",
    ).state
    plotted = _acquire(opened, "spy_drones")
    own_recall = next(
        action
        for action in legal_spy_placement_actions(plotted, 0)
        if action.action_id == "recall_spy_for_placement"
    )
    assert apply_spy_placement(plotted, own_recall).state.players[
        0
    ].spies_recalled_turn == 1


def test_ornithopter_fleet_matches_every_face_up_battle_card_at_once() -> None:
    owner = _owner(
        objective_ids=("propaganda",),
        won_conflict_ids=("skirmish_ornithopter", "storms_in_the_south"),
        face_down_battle_card_ids=(),
    )
    state = _visit(
        _turn_state(owner, stacks=(("ornithopter_fleet",), (), ())), "assembly_hall"
    )
    result = _purchase_and_resolve(state, _tech_actions(state)["ornithopter_fleet"])
    seat = result.state.players[0]
    assert seat.troops_garrison == 3 + 2
    # Three face-up cards pair once; the third stays for the next match.
    assert seat.face_down_battle_card_ids == ("propaganda", "skirmish_ornithopter")
    assert seat.victory_points == 1 + 1
    assert [e.kind for e in result.events].count("battle_icons_matched") == 1


# --- card-granted acquisition ----------------------------------------------------


def test_a_tech_discount_icon_opens_its_own_frame_with_one_spice_off() -> None:
    state = _turn_state(_owner(resources=Resources(spice=1)))
    opened = push_tech_acquisition(state, 0, discount=1, source="test")
    assert opened.state.decision_stack[-1].kind == "tech_acquisition"
    offered = _tech_actions(opened.state)
    assert "gene_locked_vault" in offered  # 2 - 1 = 1 spice
    assert not any(key.startswith("training_depot") for key in offered)
    bought = _acquire(opened.state, "gene_locked_vault:choice=intrigue")
    assert bought.players[0].resources.spice == 0
    assert len(bought.players[0].intrigue_cards) == 1
    assert bought.decision_stack[-1].kind == "turn"


def test_a_tech_discount_icon_over_empty_stacks_opens_with_only_the_refusal() -> None:
    # User ruling 2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도 모두 결정
    # 창을 연다" (docs/unavailable-options-plan.md section 5): a card's
    # Acquire Tech with every stack empty and no Secret Project still opens,
    # offering only decline_tech (OQ-057 (9) "살 수 없으면 거절만"). It used
    # to emit tech_acquisition_unavailable without asking.
    state = _turn_state(_owner(), stacks=((), (), ()))
    opened = push_tech_acquisition(state, 0, discount=1, source="test")
    assert opened.events == ()
    assert opened.state.decision_stack[-1].kind == "tech_acquisition"
    legal = UprisingRulesEngine().legal_actions(opened.state, 0)
    assert legal == (DomainAction(action_id="decline_tech", actor=0),)
    declined = _purchase_and_resolve(opened.state, legal[0])
    assert declined.state.decision_stack == state.decision_stack
    assert declined.state.players == state.players

    # A Secret Project is still a tile to take with every stack empty.
    secret = _turn_state(
        _owner(secret_project_tech_id="training_depot"), stacks=((), (), ())
    )
    offered = push_tech_acquisition(secret, 0, discount=1, source="test").state
    assert "training_depot" in _tech_actions(offered)


# --- observation, codec, soundness -------------------------------------------


def test_observation_shows_the_tops_and_hides_the_order_below() -> None:
    state = create_initial_state(TECH_CHOAM, seed=3, leader_ids=LEADERS).state
    view = observe_state(state, 0)

    assert view.tech_face_up == tuple(stack[0] for stack in state.tech_stacks)
    assert view.tech_stack_sizes == (6, 6, 6)
    assert not hasattr(view, "tech_stacks")
    assert len(encode_player_view(view)) == OBSERVATION_SIZE
    check_observation_privacy(state)


def test_tech_actions_round_trip_only_in_the_tech_catalog() -> None:
    bloodlines = ActionCodec(RulesetConfig(bloodlines=True))
    codec = ActionCodec(TECH)
    assert codec.size > bloodlines.size

    actions = (
        DomainAction("decline_tech", 1),
        DomainAction("acquire_tech", 0, (("tech_id", "training_depot"),)),
        DomainAction(
            "resolve_tech_acquire_effect",
            2,
            (
                ("effect", "influence"),
                ("faction", "fremen"),
                ("tech_id", "navigation_chamber"),
            ),
        ),
        DomainAction(
            "resolve_tech_acquire_effect",
            3,
            (
                ("choice", "card"),
                ("effect", "intrigue_or_card"),
                ("tech_id", "gene_locked_vault"),
            ),
        ),
        DomainAction(
            "acquire_tech",
            0,
            (("post_id", SIETCH_POST), ("tech_id", "advanced_data_analysis")),
        ),
        DomainAction(
            "resolve_tech_acquire_effect",
            0,
            (
                ("destroy_shield_wall", True),
                ("effect", "shield_wall"),
                ("tech_id", "forbidden_weapons"),
            ),
        ),
    )
    for action in actions:
        assert codec.decode(codec.encode(action), action.actor) == action
        with pytest.raises(ValueError):
            bloodlines.encode(action)

@pytest.mark.parametrize("game_seed", [31, 32])
def test_random_tech_games_finish_under_every_check(game_seed: int) -> None:
    report = run_checked_game(
        TECH_CHOAM if game_seed % 2 else TECH,
        game_seed=game_seed,
        policy_seed=900_000 + game_seed,
        privacy_interval=10,
        soundness_interval=10,
        engine=UprisingRulesEngine(leader_ids=LEADERS),
    )
    assert report.rounds >= 1 and 0 <= report.winner < 4


def test_heuristic_tech_game_finishes() -> None:
    report = run_checked_game(
        TECH_CHOAM,
        game_seed=41,
        policy_seed=900_041,
        privacy_interval=0,
        policy="heuristic",
        engine=UprisingRulesEngine(leader_ids=LEADERS),
    )
    assert report.ruleset == "uprising-4p-choam+bloodlines+tech"
    assert report.rounds >= 1


def test_has_tech_helper_reads_abilities() -> None:
    from dune_imperium.content.bloodlines.tech import has_tech

    assert has_tech(("glowglobes",), TechAbility.PEEK_TOP_CARD)
    assert not has_tech(("glowglobes",), TechAbility.SPACE_DISCOUNT)
    assert Influence().fremen == 0


# --- abilities (slice 6b) -------------------------------------------------------


def _tech_owner(*tech_ids: str, **overrides: object) -> PlayerState:
    return _owner(tech_ids=tech_ids, **overrides)


def _reveal(state: GameState) -> RuleResult:
    from dune_imperium.rules.reveal_turn import begin_reveal_turn

    return begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))


def _gains(state: GameState) -> GameState:
    """Take every pending Reveal gain (OQ-045)."""

    from dune_imperium.rules.reveal_turn import (
        apply_reveal_gain,
        legal_reveal_gain_actions,
    )

    while actions := legal_reveal_gain_actions(state, 0):
        state = apply_reveal_gain(state, actions[0]).state
    return state


def test_navigation_chamber_offers_a_spice_or_solari_discount_on_placements() -> None:
    owner = _tech_owner(
        "navigation_chamber",
        hand=starting_deck_instance_ids(0),
        deck=(),
        resources=Resources(solari=1, spice=0, water=1),
    )
    state = _turn_state(owner)
    high_council = [
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "high_council"
    ]
    # Five Solari are out of reach; four with the discount are not.
    assert high_council == []
    richer = replace(
        state,
        players=(
            replace(owner, resources=Resources(solari=4, water=1)),
            *state.players[1:],
        ),
    )
    discounted = [
        action
        for action in legal_agent_actions(richer, 0)
        if dict(action.arguments)["space_id"] == "high_council"
    ]
    assert {dict(a.arguments).get("discount") for a in discounted} == {"solari"}
    placed = apply_agent_action(richer, discounted[0]).state
    assert placed.players[0].resources.solari == 0
    assert placed.players[0].agent_locations == ("high_council",)


def test_navigation_chamber_cut_is_mandatory_on_every_costed_space() -> None:
    """The cut always applies; the full price is never offered (OQ-104).

    Tile face: "Board spaces cost you [1 spice] or [1 Solari] less." -- no
    "may", no Flip icon, no once-per-round mark. docs/rules/bloodlines.md:
    "| Navigation Chamber | 5 | Influence 1 선택 | board space 비용이 spice 1
    또는 Solari 1 줄어든다 |" [Tech tile faces] [Bloodlines p. 7], applied
    without a choice like the rulebook's "the Tech tile costs him 1 less
    Spice" [Bloodlines p. 7]; docs/rules/README.md: "원문이 선택 여부를
    명시하지 않으면 이 문서가 임의로 선택 여부를 만들지 않는다." The FAQ's
    "Most effects from a board space or card you play are mandatory"
    [FAQ p. 3] supports this only by analogy (a Tech tile is neither).
    Spice Refinery's and Gather Support's arrow payments are costs
    ("cost로 0 또는 1 spice 선택", "cost로 0 또는 2 Solari 선택"
    [Board Guide pp. 1-2], board-spaces.md), so the cut reaches their
    option 1; their free option 0 and water costs carry no cut.
    """

    owner = _tech_owner(
        "navigation_chamber",
        hand=starting_deck_instance_ids(0),
        deck=(),
        resources=Resources(solari=9, spice=9, water=9),
        influence=Influence(emperor=3, spacing_guild=3, bene_gesserit=3, fremen=3),
    )
    state = _turn_state(owner)
    placements = [
        dict(action.arguments)
        for action in legal_agent_actions(state, 0)
        if action.action_id == "agent_turn"
    ]
    costed = {
        "sardaukar": "spice",
        "heighliner": "spice",
        "espionage": "spice",
        "shipping": "spice",
        "high_council": "solari",
        "imperial_privilege": "solari",
        "swordmaster": "solari",
    }
    cost_options = {"spice_refinery": "spice", "gather_support": "solari"}
    water = {"desert_tactics", "research_station", "deep_desert", "hagga_basin"}
    seen = {str(arguments["space_id"]) for arguments in placements}
    assert set(costed) | set(cost_options) | water <= seen
    for arguments in placements:
        space_id = str(arguments["space_id"])
        discount = arguments.get("discount")
        if space_id in costed:
            assert discount == costed[space_id], arguments
        elif space_id in cost_options:
            option = arguments["cost_option"]
            assert discount == (cost_options[space_id] if option == 1 else None), (
                arguments
            )
        else:
            assert discount is None, arguments

    def placement(space_id: str, **extra: str | int) -> DomainAction:
        return next(
            action
            for action in legal_agent_actions(state, 0)
            if dict(action.arguments)["space_id"] == space_id
            and all(dict(action.arguments).get(k) == v for k, v in extra.items())
        )

    council = placement("high_council")
    full_price = DomainAction(
        action_id="agent_turn",
        actor=0,
        arguments=tuple(item for item in council.arguments if item[0] != "discount"),
    )
    with pytest.raises(ValueError, match="not a legal Agent turn"):
        apply_agent_action(state, full_price)
    paid = apply_agent_action(state, council).state.players[0]
    assert paid.resources.solari == 9 - 4

    refinery = placement("spice_refinery", cost_option=1)
    traded = apply_agent_action(state, refinery).state
    assert traded.players[0].resources.spice == 9
    assert traded.players[0].spice_spent_turn == 0
    for board_action in legal_board_effect_actions(traded, 0):
        traded = resolve_board_effect(traded, board_action).state
    assert traded.players[0].resources.spice == 9
    assert traded.players[0].resources.solari == 9 + 4


def test_navigation_chamber_offers_both_cuts_on_a_cost_of_spice_and_solari() -> None:
    """OQ-104 (b), project reading: the printed "or" of "Board spaces cost
    you [1 spice] or [1 Solari] less." [Tech tile face] is a choice only on a
    cost holding both resources, where the owner picks which to cut; the full
    price is still never offered. No 4-player space costs both, so the space
    here is High Council with a made-up spice-and-Solari cost.
    """

    from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, ResourceCost
    from dune_imperium.rules.agent_turn import _actions_for_affordable_costs

    space = replace(
        BOARD_SPACES_BY_ID["high_council"],
        cost_options=(ResourceCost(spice=1, solari=5),),
    )
    card = starting_deck_instance_ids(0)[0]

    def discounts(*tech_ids: str, resources: Resources) -> list[object]:
        owner = _tech_owner(
            *tech_ids,
            hand=starting_deck_instance_ids(0),
            deck=(),
            resources=resources,
        )
        state = _turn_state(owner)
        return [
            dict(action.arguments).get("discount")
            for action in _actions_for_affordable_costs(
                0, card, space, state.players[0], state
            )
        ]

    plenty = Resources(solari=9, spice=9)
    assert discounts("navigation_chamber", resources=plenty) == ["spice", "solari"]
    assert discounts(resources=plenty) == [None]
    # Only the spice cut is affordable: the Solari cut is not offered, and
    # neither is the full price.
    assert discounts("navigation_chamber", resources=Resources(solari=5)) == ["spice"]


def test_servo_receivers_give_the_signet_ring_the_faction_icons() -> None:
    signet = "player:0:starter:signet_ring:0"
    owner = _tech_owner("servo_receivers", hand=(signet,), deck=())
    state = _turn_state(owner, stacks=((), (), ()))
    spaces = {
        str(dict(action.arguments)["space_id"])
        for action in legal_agent_actions(state, 0)
    }
    faction_spaces = {"sardaukar", "heighliner", "espionage", "desert_tactics"}
    assert faction_spaces <= spaces
    without = replace(state, players=(replace(owner, tech_ids=()), *state.players[1:]))
    plain = {
        str(dict(action.arguments)["space_id"])
        for action in legal_agent_actions(without, 0)
    }
    # The printed Signet Ring reaches no Faction space on its own.
    assert not (faction_spaces & plain)


def test_sardaukar_high_command_takes_one_solari_off_every_commander() -> None:
    from dune_imperium.rules.sardaukar import commander_cost

    assert commander_cost(_tech_owner("sardaukar_high_command")) == 1
    assert (
        commander_cost(_tech_owner("sardaukar_high_command", commander_discount_turn=1))
        == 0
    )
    assert commander_cost(_owner()) == 2


def test_plasteel_blades_offers_an_extra_skill_after_a_commander_recruit() -> None:
    from dune_imperium.content.bloodlines.sardaukar import skill_tile_instance_ids
    from dune_imperium.rules.sardaukar import (
        apply_commander_recruit,
        apply_skill_choice,
        begin_skill_choice,
        legal_skill_choice_actions,
    )

    skills = skill_tile_instance_ids()
    owner = _tech_owner(
        "plasteel_blades", commanders_supply=1, resources=Resources(solari=2)
    )
    state = replace(
        _turn_state(owner, stacks=((), (), ())),
        skill_face_up=skills[:4],
        skill_stack=skills[4:],
        sardaukar_commanders_bank=1,
    )
    state = _visit(state, "assembly_hall")
    recruited = apply_commander_recruit(
        state, DomainAction(action_id="recruit_sardaukar_commander", actor=0)
    ).state
    assert recruited.pending_skill_choices[0][1] == "tech:plasteel_blades"
    opened = begin_skill_choice(recruited).state
    assert opened.decision_stack[-1].kind == "skill_choice"
    actions = legal_skill_choice_actions(opened, 0)
    assert actions[0].action_id == "decline_skill"
    kept = apply_skill_choice(opened, actions[0]).state
    assert kept.players[0].tech_ids == ("plasteel_blades",)
    taken = apply_skill_choice(opened, actions[1]).state
    seat = taken.players[0]
    assert seat.tech_ids == ()
    assert taken.tech_trash == ("plasteel_blades",)
    assert len(seat.skill_ids) == 1
    assert seat.commanders_garrison == 1  # no second Commander


def test_plasteel_blades_with_no_skill_to_gain_asks_with_only_the_keep() -> None:
    """Plasteel Blades' extra Skill with every face-up Skill already held:
    the window opens anyway with only ``decline_skill`` (user ruling
    2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을 연다";
    the trash cannot be paid when its effect cannot happen, OQ-071), and the
    held Skills show greyed out. It used to drop without a trace. Nothing
    opens when the tile has left play: its trigger source is gone."""
    from dune_imperium.content.bloodlines.sardaukar import skill_tile_instance_ids
    from dune_imperium.display.unavailable import unavailable_choices
    from dune_imperium.rules.sardaukar import (
        apply_commander_recruit,
        apply_skill_choice,
        begin_skill_choice,
    )

    skills = skill_tile_instance_ids()
    owner = _tech_owner(
        "plasteel_blades",
        commanders_supply=1,
        resources=Resources(solari=2),
        skill_ids=(skills[0], skills[2]),
    )
    state = replace(
        _turn_state(owner, stacks=((), (), ())),
        skill_face_up=(skills[1], skills[3]),
        skill_stack=skills[4:],
        sardaukar_commanders_bank=1,
    )
    state = _visit(state, "assembly_hall")
    recruited = apply_commander_recruit(
        state, DomainAction(action_id="recruit_sardaukar_commander", actor=0)
    ).state
    opened = begin_skill_choice(recruited)
    assert opened.events == ()
    assert opened.state.decision_stack[-1].kind == "skill_choice"
    keep = DomainAction(action_id="decline_skill", actor=0)
    assert UprisingRulesEngine().legal_actions(opened.state, 0) == (keep,)
    found = unavailable_choices(opened.state, 0, (keep,))
    assert found is not None
    rows = found["rows"]
    assert isinstance(rows, list)
    assert {
        (row["surface"], row["action"]["action_id"], row["code"]) for row in rows
    } == {("choice", "choose_skill", "held")}
    assert len(rows) == 2  # two face-up identities, both held
    kept = apply_skill_choice(opened.state, keep)
    assert kept.state.players[0].tech_ids == ("plasteel_blades",)
    assert [event.kind for event in kept.events] == ["tech_trash_declined"]

    # The tile left play before the choice opened: nothing to ask.
    gone = replace(
        recruited,
        players=(replace(recruited.players[0], tech_ids=()), *recruited.players[1:]),
    )
    dropped = begin_skill_choice(gone)
    assert dropped.events == ()
    assert dropped.state.pending_skill_choices == ()
    assert dropped.state.decision_stack == gone.decision_stack


def test_gene_locked_vault_raises_the_secrets_threshold_to_five() -> None:
    from dune_imperium.rules.board_effects import _secrets_victims

    victim = replace(
        PlayerState(player_id=1),
        intrigue_cards=tuple(f"intrigue:test:{i}" for i in range(4)),
        tech_ids=("gene_locked_vault",),
    )
    state = _turn_state(_owner(), stacks=((), (), ()))
    state = replace(state, players=(state.players[0], victim, *state.players[2:]))
    assert _secrets_victims(state, 0) == ()
    five = replace(victim, intrigue_cards=(*victim.intrigue_cards, "intrigue:test:4"))
    assert _secrets_victims(
        replace(state, players=(state.players[0], five, *state.players[2:])), 0
    ) == (1,)


def test_glowglobes_shows_only_the_owner_the_top_card() -> None:
    owner = _tech_owner("glowglobes")
    state = _turn_state(owner, stacks=((), (), ()))
    mine = observe_state(state, 0).private
    theirs = observe_state(state, 1).private
    assert mine is not None and theirs is not None
    assert mine.peeked_card_id == owner.deck[0]
    assert theirs.peeked_card_id == ""
    check_observation_privacy(state)


def test_ornithopter_fleet_matches_a_won_conflict_with_any_face_up_card() -> None:
    from dune_imperium.rules.combat import finish_combat, offer_conflict_end_triggers

    owner = _tech_owner(
        "ornithopter_fleet",
        objective_ids=("propaganda",),
        troops_supply=11,
        troops_garrison=0,
        troops_conflict=1,
        combat_strength=2,
        has_revealed=True,
        hand=(),
        deck=(),
    )
    state = replace(
        _turn_state(owner, stacks=((), (), ())),
        phase=GamePhase.COMBAT,
        first_player=0,
        current_conflict_ids=("skirmish_wild",),
        combat_intrigue_complete=True,
        combat_rewards_resolved=True,
        decision_stack=(),
        players=(
            owner,
            *(
                replace(seat, has_revealed=True)
                for seat in _turn_state(owner).players[1:]
            ),
        ),
    )
    # The Conflict card is awarded, and matched with any face-up card, as the
    # Conflict-end step opens, the troop going back to the supply after it
    # (OQ-108, user decision 2026-10-18); the cleanup after the windows
    # changes neither.
    offered = offer_conflict_end_triggers(state).state
    assert offered.players[0].face_down_battle_card_ids == (
        "propaganda",
        "skirmish_wild",
    )
    assert offered.players[0].troops_conflict == 0
    winner = finish_combat(offered).state.players[0]
    assert winner.face_down_battle_card_ids == ("propaganda", "skirmish_wild")
    assert winner.victory_points == 2


def test_ornithopter_fleet_blocks_crysknife_flips_but_frees_ornithopter_ones() -> None:
    from dune_imperium.content.uprising.types import BattleIcon
    from dune_imperium.rules.effect_interpreter import flippable_battle_card_ids

    seat = _tech_owner("ornithopter_fleet", won_conflict_ids=("skirmish_wild",))
    assert flippable_battle_card_ids(seat, BattleIcon.CRYSKNIFE) == ()
    assert flippable_battle_card_ids(seat, BattleIcon.ORNITHOPTER) == ("skirmish_wild",)


def test_planetary_array_owes_a_card_the_engine_draws_after_the_win() -> None:
    from dune_imperium.rules.combat import offer_conflict_end_triggers
    from dune_imperium.rules.tech import draw_owed_tech_cards

    owner = _tech_owner(
        "planetary_array",
        troops_supply=11,
        troops_garrison=0,
        troops_conflict=1,
        combat_strength=2,
        has_revealed=True,
        hand=(),
    )
    state = replace(
        _turn_state(owner, stacks=((), (), ())),
        phase=GamePhase.COMBAT,
        first_player=0,
        combat_intrigue_complete=True,
        combat_rewards_resolved=True,
        decision_stack=(),
        players=(
            owner,
            *(
                replace(seat, has_revealed=True)
                for seat in _turn_state(owner).players[1:]
            ),
        ),
    )
    # The card is owed as the Conflict card is awarded (OQ-108, user decision
    # 2026-10-18), and drawn once that step settles.
    offered = offer_conflict_end_triggers(state)
    assert offered.state.players[0].tech_cards_owed == 1
    drawn = draw_owed_tech_cards(offered).state
    assert drawn.players[0].tech_cards_owed == 0
    assert len(drawn.players[0].hand) == 1


def _planetary_array_conflict_end(
    deck: tuple[str, ...], discard: tuple[str, ...]
) -> tuple[UprisingRulesEngine, Transition]:
    """A Combat the Planetary Array owner wins, through the engine up to the
    transition that offers the Conflict-end windows (Immortality, so the
    owner's loss of three and its Intrigue card open one)."""

    engine = UprisingRulesEngine()
    owner = _tech_owner(
        "planetary_array",
        troops_supply=9,
        troops_garrison=0,
        troops_conflict=3,
        combat_strength=6,
        has_revealed=True,
        intrigue_cards=("intrigue:backed_by_choam:0",),
        hand=(),
        deck=deck,
        discard_pile=discard,
    )
    state = replace(
        _turn_state(
            owner,
            stacks=((), (), ()),
            config=RulesetConfig(bloodlines=True, tech_module=True, immortality=True),
            decision_stack=(),
            first_player=0,
            reveal_order=(0, 1, 2, 3),
        ),
        phase=GamePhase.COMBAT,
        players=(
            owner,
            *(PlayerState(player_id=seat, has_revealed=True) for seat in (1, 2, 3)),
        ),
    )
    state = begin_combat_intrigue(state).state
    while True:
        frame = state.decision_stack[-1]
        if frame.kind == FrameKind.PAUSE:
            transition = engine.apply(state, pause_outcome(state))
        else:
            assert isinstance(frame.decision, PlayerDecision)
            actions = engine.legal_actions(state, frame.decision.owner)
            passing = next(
                (a for a in actions if a.action_id.startswith("pass_")), actions[0]
            )
            transition = engine.apply(state, passing)
        if transition.state.combat_end_triggers_offered:
            return engine, transition
        state = transition.state


def test_planetary_array_s_card_is_in_hand_before_any_conflict_end_window() -> None:
    # "When you win a Conflict: draw a card" [Planetary Array Tech tile].
    # The winner takes the Conflict card right after the rewards [Main p. 14]
    # (OQ-108, user decision 2026-10-18), so the card is owed there and drawn
    # as that step settles: the Conflict-end window it opens finds the card
    # already in the hand, before any window is answered.
    deck = starting_deck_instance_ids(0)[5:8]
    engine, offered = _planetary_array_conflict_end(deck, ())

    seat = offered.state.players[0]
    assert seat.hand == (deck[0],)
    assert seat.deck == deck[1:]
    assert seat.tech_cards_owed == 0
    top = offered.state.decision_stack[-1]
    assert top.kind == FrameKind.CONFLICT_END_TRIGGER
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 0
    kinds = [event.kind for event in offered.events]
    assert kinds.index("conflict_won") < kinds.index("conflict_end_trigger_offered")
    # The window is still unanswered: it only declines (no Harvest Cells).
    assert engine.legal_actions(offered.state, 0) == (
        DomainAction(action_id="decline_conflict_end_intrigue", actor=0),
    )
    declined = engine.apply(
        offered.state,
        DomainAction(action_id="decline_conflict_end_intrigue", actor=0),
    ).state
    assert deck[0] in declined.players[0].hand
    assert declined.players[0].tech_cards_owed == 0


def test_planetary_array_s_empty_deck_reshuffles_before_the_window() -> None:
    # The same draw with an empty deck: the discard pile is shuffled first
    # (a ``...:tech_draw:discard_shuffle`` chance on top of the unanswered
    # window), then the card is drawn and the window is the decision again.
    discard = starting_deck_instance_ids(0)[5:8]
    engine, offered = _planetary_array_conflict_end((), discard)

    seat = offered.state.players[0]
    assert seat.hand == () and seat.tech_cards_owed == 0
    top = offered.state.decision_stack[-1]
    assert top.kind == FrameKind.PERSONAL_DRAW_RESHUFFLE
    assert isinstance(top.decision, ChanceDecision)
    assert top.decision.decision_id == "round:1:player:0:tech_draw:discard_shuffle"
    assert tuple(sorted(top.decision.options)) == tuple(sorted(discard))
    # The Conflict-end window waits underneath, unanswered.
    assert offered.state.decision_stack[-2].kind == FrameKind.CONFLICT_END_TRIGGER
    assert [event.kind for event in offered.events].count("conflict_won") == 1

    shuffled = tuple(reversed(discard))
    answered = engine.apply(
        offered.state, ChanceOutcome(top.decision.decision_id, shuffled)
    )

    assert answered.state.players[0].hand == (shuffled[0],)
    assert answered.state.players[0].deck == shuffled[1:]
    assert [event.kind for event in answered.events] == ["personal_discard_shuffled"]
    window = answered.state.decision_stack[-1]
    assert window.kind == FrameKind.CONFLICT_END_TRIGGER
    assert isinstance(window.decision, PlayerDecision) and window.decision.owner == 0


def _planetary_array_win_without_windows(
    deck: tuple[str, ...], discard: tuple[str, ...]
) -> tuple[UprisingRulesEngine, GameState]:
    """A Combat the Planetary Array owner wins with no Conflict-end window
    (Immortality off), through the engine to the first decision past the
    Conflict-end pause: the Round Start pause, or a reshuffle on the way."""

    engine = UprisingRulesEngine()
    owner = _tech_owner(
        "planetary_array",
        troops_supply=9,
        troops_garrison=0,
        troops_conflict=3,
        combat_strength=6,
        has_revealed=True,
        intrigue_cards=(),
        hand=(),
        deck=deck,
        discard_pile=discard,
    )
    state = replace(
        _turn_state(
            owner,
            stacks=((), (), ()),
            config=RulesetConfig(bloodlines=True, tech_module=True),
            decision_stack=(),
            first_player=0,
            reveal_order=(0, 1, 2, 3),
            # Conflicts left, so the round ends into a Round Start.
            conflict_deck=tuple(conflict.card.card_id for conflict in CONFLICTS[1:4]),
        ),
        phase=GamePhase.COMBAT,
        players=(
            owner,
            *(PlayerState(player_id=seat, has_revealed=True) for seat in (1, 2, 3)),
        ),
    )
    state = begin_combat_intrigue(state).state
    while True:
        frame = state.decision_stack[-1]
        if frame.kind == FrameKind.PAUSE:
            if dict(frame.context).get("point") == "round_start":
                return engine, state
            state = engine.apply(state, pause_outcome(state)).state
        elif isinstance(frame.decision, ChanceDecision):
            return engine, state
        else:
            assert isinstance(frame.decision, PlayerDecision)
            actions = engine.legal_actions(state, frame.decision.owner)
            passing = next(
                (a for a in actions if a.action_id.startswith("pass_")), actions[0]
            )
            state = engine.apply(state, passing).state


def test_planetary_array_s_card_comes_at_the_win_with_no_window() -> None:
    # OQ-108 (B), user decision 2026-10-18: "When you win a Conflict: draw a
    # card" [Planetary Array Tech tile] at the Conflict card's award, right
    # after the rewards [Main p. 14] -- also when no Conflict-end window
    # opens, where the cleanup runs on into the next round in one step (the
    # card used to come after the next round's hand there).
    deck = starting_deck_instance_ids(0)[5:10]
    _engine, paused = _planetary_array_win_without_windows(deck, ())

    assert paused.phase is GamePhase.ROUND_START
    seat = paused.players[0]
    assert seat.hand == (deck[0],)
    assert seat.deck == deck[1:]
    assert seat.tech_cards_owed == 0


def test_planetary_array_s_empty_deck_reshuffles_in_combat_with_no_window() -> None:
    discard = starting_deck_instance_ids(0)[5:8]
    engine, asked = _planetary_array_win_without_windows((), discard)

    assert asked.phase is GamePhase.COMBAT
    top = asked.decision_stack[-1]
    assert top.kind == FrameKind.PERSONAL_DRAW_RESHUFFLE
    assert isinstance(top.decision, ChanceDecision)
    assert top.decision.decision_id == "round:1:player:0:tech_draw:discard_shuffle"
    shuffled = tuple(reversed(discard))
    answered = engine.apply(asked, ChanceOutcome(top.decision.decision_id, shuffled))
    seat = answered.state.players[0]
    assert seat.hand == (shuffled[0],)
    assert seat.tech_cards_owed == 0
    assert answered.state.phase is GamePhase.ROUND_START


def test_suspensor_suits_deploys_a_troop_per_intrigue_gained_in_the_owners_turn() -> (
    None
):
    from dune_imperium.rules.intrigue_deck import draw_intrigue_cards
    from dune_imperium.rules.tech import deploy_suspensor_troops

    state = _turn_state(_tech_owner("suspensor_suits"), stacks=((), (), ()))
    drawn = draw_intrigue_cards(state, 0, 2, source="test")
    assert drawn.state.players[0].suspensor_owed == 2
    deployed = deploy_suspensor_troops(drawn).state
    seat = deployed.players[0]
    assert seat.suspensor_owed == 0
    assert seat.troops_conflict == 2 and seat.troops_supply == 9 - 2
    # Another seat's turn: no deployment.
    other = replace(
        state,
        players=(
            replace(state.players[0], tech_ids=()),
            replace(state.players[1], tech_ids=("suspensor_suits",)),
            *state.players[2:],
        ),
    )
    quiet = draw_intrigue_cards(other, 1, 1, source="test")
    assert quiet.state.players[1].suspensor_owed == 0


def test_suspensor_suits_logs_the_troops_the_supply_cannot_cover() -> None:
    # OQ-042 (b): what the supply cannot cover is lost, never paid later.
    # Nothing is left to choose, so no window opens, but the troops left
    # over are logged, a partial shortfall included (user ruling 2026-10-02,
    # L2-Q4: "로그 + 클릭 전 경고").
    from dune_imperium.rules.intrigue_deck import draw_intrigue_cards
    from dune_imperium.rules.tech import deploy_suspensor_troops

    def shortfalls(result: RuleResult) -> list[dict[str, object]]:
        return [
            dict(event.payload)
            for event in result.events
            if event.kind == "suspensor_deployment_unavailable"
        ]

    partial = _turn_state(
        _tech_owner("suspensor_suits", troops_supply=1, troops_garrison=11),
        stacks=((), (), ()),
    )
    paid = deploy_suspensor_troops(draw_intrigue_cards(partial, 0, 2, source="t"))
    seat = paid.state.players[0]
    assert seat.suspensor_owed == 0
    assert seat.troops_conflict == 1 and seat.troops_supply == 0
    assert shortfalls(paid) == [{"deployed": 1, "player": 0, "troops": 1}]
    deployed = [event for event in paid.events if event.kind == "troops_deployed"]
    assert [dict(event.payload)["count"] for event in deployed] == [1]

    empty = replace(
        partial,
        players=(
            replace(partial.players[0], troops_supply=0, troops_garrison=12),
            *partial.players[1:],
        ),
    )
    lost = deploy_suspensor_troops(draw_intrigue_cards(empty, 0, 2, source="t"))
    assert lost.state.players[0].troops_conflict == 0
    assert shortfalls(lost) == [{"deployed": 0, "player": 0, "troops": 2}]
    assert "troops_deployed" not in [event.kind for event in lost.events]

    # A full supply: nothing to log.
    full = deploy_suspensor_troops(
        draw_intrigue_cards(
            _turn_state(_tech_owner("suspensor_suits"), stacks=((), (), ())),
            0,
            2,
            source="t",
        )
    )
    assert shortfalls(full) == []


def _owed_and_deployed(state: GameState, player: int = 0) -> tuple[int, int]:
    from dune_imperium.rules.tech import deploy_suspensor_troops

    owed = state.players[player].suspensor_owed
    deployed = deploy_suspensor_troops(RuleResult(state=state)).state
    return owed, deployed.players[player].troops_conflict


def _owed_taken(state: GameState, player: int = 0) -> GameState:
    """Take every triggered draw waiting as the seat's own step (OQ-106)."""

    from dune_imperium.rules.owed_draws import apply_owed_draw

    while state.players[player].owed_draws:
        state = apply_owed_draw(
            state, DomainAction(action_id="draw_owed_intrigue", actor=player)
        ).state
    return state


def test_suspensor_suits_counts_every_direct_intrigue_draw_in_the_turn() -> None:
    # "For each Intrigue card you draw or steal during your turn: [troop]
    # Deploy it to the Conflict" [Suspensor Suits Tech tile]; the face limits
    # only the turn (OQ-042 (a)), not which effect draws. Draws that took a
    # card straight off the Intrigue deck skipped the troop. A triggered draw
    # waits as the seat's own step in its turn (user ruling 2026-10-10,
    # OQ-106) and counts when it is taken.
    from dune_imperium.content.uprising.board import Faction
    from dune_imperium.rules.acquisition import acquire_imperium_for_intrigue
    from dune_imperium.rules.card_trash import trash_personal_card
    from dune_imperium.rules.influence import gain_faction_influence
    from dune_imperium.rules.reveal_turn import (
        apply_reveal_spy_action,
        legal_reveal_spy_actions,
    )

    stacks: tuple[tuple[str, ...], ...] = ((), (), ())
    # The Bene Gesserit track's Influence 4 bonus [Main p. 7].
    bene_gesserit = _turn_state(
        _tech_owner("suspensor_suits", influence=Influence(bene_gesserit=3)),
        stacks=stacks,
    )
    gained = gain_faction_influence(
        bene_gesserit, 0, Faction.BENE_GESSERIT, 1, event_prefix="test"
    ).state
    assert _owed_and_deployed(gained) == (0, 0)
    gained = _owed_taken(gained)
    assert len(gained.players[0].intrigue_cards) == 1
    assert _owed_and_deployed(gained) == (1, 1)

    # Imperial Birthright on reaching two Emperor Influence [Princess
    # Irulan card].
    irulan = _turn_state(
        _tech_owner(
            "suspensor_suits",
            leader_id="princess_irulan",
            influence=Influence(emperor=1),
        ),
        stacks=stacks,
    )
    gained = gain_faction_influence(
        irulan, 0, Faction.EMPEROR, 1, event_prefix="test"
    ).state
    assert _owed_and_deployed(_owed_taken(gained)) == (1, 1)

    # Sardaukar Soldier: "When this card is trashed: [Intrigue]".
    soldier = "imperium:sardaukar_soldier:0"
    trashing = _turn_state(
        _tech_owner("suspensor_suits", hand=(*_owner().hand, soldier)),
        stacks=stacks,
    )
    trashed = trash_personal_card(trashing, 0, soldier, source="test").state
    assert _owed_and_deployed(_owed_taken(trashed)) == (1, 1)

    # Overthrow's acquire box draws an Intrigue card.
    overthrow = "imperium:overthrow:0"
    acquiring = _turn_state(
        _tech_owner("suspensor_suits"),
        stacks=stacks,
        imperium_row=(overthrow,),
        imperium_deck=(),
    )
    acquired = acquire_imperium_for_intrigue(
        acquiring, 0, overthrow, to_hand=False, source="test"
    ).result.state
    assert _owed_and_deployed(_owed_taken(acquired)) == (1, 1)

    # Spy Network's Reveal: recall one of two placed Spies to draw.
    network = "imperium:spy_network:0"
    revealing = _turn_state(
        _tech_owner(
            "suspensor_suits",
            hand=(network,),
            deck=_owner().hand + _owner().deck,
            spies_supply=1,
            spy_post_ids=(LANDSRAAD_POST, SIETCH_POST),
        ),
        stacks=stacks,
    )
    revealed = _reveal(revealing).state
    recall = next(
        action
        for action in legal_reveal_spy_actions(revealed, 0)
        if action.action_id == "recall_spy_for_reveal"
    )
    drew = apply_reveal_spy_action(revealed, recall).state
    assert len(drew.players[0].intrigue_cards) == 1
    assert drew.players[0].suspensor_owed == 1


def test_suspensor_suits_ignores_direct_draws_outside_the_owners_turn() -> None:
    # OQ-042 (a): only the owner's own Agent or Reveal turn counts; the Bene
    # Gesserit bonus reached on another seat's turn owes nothing.
    from dune_imperium.content.uprising.board import Faction
    from dune_imperium.rules.influence import gain_faction_influence

    state = _turn_state(_owner(), stacks=((), (), ()))
    others = replace(
        state,
        players=(
            state.players[0],
            replace(
                state.players[1],
                tech_ids=("suspensor_suits",),
                influence=Influence(bene_gesserit=3),
            ),
            *state.players[2:],
        ),
    )
    gained = gain_faction_influence(
        others, 1, Faction.BENE_GESSERIT, 1, event_prefix="test"
    ).state
    assert len(gained.players[1].intrigue_cards) == 1
    assert gained.players[1].suspensor_owed == 0


def test_flip_tiles_are_offered_once_per_round_and_return_at_round_start() -> None:
    from dune_imperium.rules.phases import begin_round
    from dune_imperium.rules.tech import apply_tech_flip, legal_tech_flip_actions

    owner = _tech_owner("advanced_data_analysis", "spy_drones", "rapid_dropships")
    state = _turn_state(owner, stacks=((), (), ()))
    offered = {
        str(dict(a.arguments)["tech_id"]) for a in legal_tech_flip_actions(state, 0)
    }
    # Rapid Dropships prints "Agent Turn": only after the placement.
    assert offered == {"advanced_data_analysis", "spy_drones"}
    flipped = apply_tech_flip(
        state, DomainAction("flip_tech", 0, (("tech_id", "advanced_data_analysis"),))
    ).state
    assert flipped.players[0].tech_flipped == ("advanced_data_analysis",)
    assert len(flipped.players[0].intrigue_cards) == 1
    assert "advanced_data_analysis" not in {
        str(dict(a.arguments)["tech_id"]) for a in legal_tech_flip_actions(flipped, 0)
    }
    # Spy Drones: one Solari, and a trash only after a Spy recall this turn.
    drones = apply_tech_flip(
        flipped, DomainAction("flip_tech", 0, (("tech_id", "spy_drones"),))
    )
    assert drones.state.players[0].resources.solari == 4 + 1
    assert drones.state.decision_stack[-1].kind == "turn"
    recalled = replace(
        flipped,
        players=(
            replace(flipped.players[0], spies_recalled_turn=1),
            *flipped.players[1:],
        ),
    )
    drones = apply_tech_flip(
        recalled, DomainAction("flip_tech", 0, (("tech_id", "spy_drones"),))
    )
    # The trash waits on the owner's turn as a row with no refusal (cleanup-2b).
    waiting = drones.state.decision_stack[-1]
    assert waiting.kind == "turn"
    assert [kind for kind, _source, _value in turn_rows.pending(waiting)] == [
        turn_rows.OPTIONAL_TRASH
    ]
    assert "decline_optional_trash" not in {
        a.action_id for a in legal_optional_trash_actions(drones.state, 0)
    }

    # Round Start turns every flipped tile face up again.
    fresh = create_initial_state(TECH, seed=3, leader_ids=LEADERS).state
    stacks = tuple(
        tuple(t for t in stack if t != "spy_drones") for stack in fresh.tech_stacks
    )
    seat = replace(
        fresh.players[0], tech_ids=("spy_drones",), tech_flipped=("spy_drones",)
    )
    fresh = replace(fresh, tech_stacks=stacks, players=(seat, *fresh.players[1:]))
    assert begin_round(fresh).state.players[0].tech_flipped == ()


def test_rapid_dropships_flip_opens_the_combat_deployment_after_the_placement() -> None:
    from dune_imperium.rules.combat_deployment import legal_combat_deployments
    from dune_imperium.rules.tech import apply_tech_flip, legal_tech_flip_actions

    state = _visit(
        _turn_state(_tech_owner("rapid_dropships"), stacks=((), (), ())),
        "assembly_hall",
    )
    assert legal_combat_deployments(state, 0) == ()
    (flip,) = legal_tech_flip_actions(state, 0)
    opened = apply_tech_flip(state, flip).state
    assert [
        dict(a.arguments)["count"] for a in legal_combat_deployments(opened, 0)
    ] == [1, 2]


def test_command_tiles_pay_when_the_reveal_generates_six_persuasion() -> None:
    owner = _tech_owner(
        "delivery_bay",
        "training_depot",
        "self_destroying_messages",
        hand=starting_deck_instance_ids(0)[:5],
        high_council=True,
        troops_conflict=1,
        troops_supply=8,
    )
    result = _reveal(_turn_state(owner, stacks=((), (), ())))
    context = dict(result.state.decision_stack[0].context)
    persuasion = context["persuasion"]
    assert isinstance(persuasion, int) and persuasion >= 6
    # Delivery Bay's Solari is a Reveal gain the owner takes (OQ-045).
    seat = _gains(result.state).players[0]
    assert seat.resources.solari == 4 + 2
    assert context["tech_granted"] == "delivery_bay,training_depot"
    plain = _reveal(
        _turn_state(
            replace(owner, tech_ids=("training_depot",), high_council=False),
            stacks=((), (), ()),
        )
    )
    plain_context = dict(plain.state.decision_stack[0].context)
    plain_persuasion = plain_context["persuasion"]
    plain_swords = plain_context["sword_strength"]
    assert isinstance(plain_persuasion, int) and isinstance(plain_swords, int)
    assert plain_persuasion < 6
    assert plain_context["tech_granted"] == ""
    assert context["sword_strength"] == plain_swords + 2


def test_a_command_tile_pays_late_when_persuasion_reaches_six() -> None:
    from dune_imperium.rules.reveal_turn import (
        add_reveal_persuasion,
        grant_late_reveal_effects,
    )

    owner = _tech_owner("delivery_bay", hand=starting_deck_instance_ids(0)[:5])
    result = _reveal(_turn_state(owner, stacks=((), (), ())))
    assert dict(result.state.decision_stack[0].context)["tech_granted"] == ""
    bumped = replace(
        result.state,
        decision_stack=add_reveal_persuasion(result.state.decision_stack, 6),
    )
    late = grant_late_reveal_effects(RuleResult(state=bumped))
    assert _gains(late.state).players[0].resources.solari == 4 + 2
    assert dict(late.state.decision_stack[0].context)["tech_granted"] == "delivery_bay"
    # A second pass does not pay again.
    again = grant_late_reveal_effects(RuleResult(state=_gains(late.state)))
    assert again.state.players[0].resources.solari == 4 + 2


def test_training_depot_counts_persuasion_spent_before_the_sixth() -> None:
    # Training Depot: "Reveal Turn: Command (6+): [2 swords]" [Training Depot
    # tile]; Command is "a Reveal turn in which you generate 6 Persuasion or
    # more" [Bloodlines p. 12] [Bloodlines p. 5]. Spending on a purchase does
    # not un-generate Persuasion, so the late grant (OQ-033) pays the same
    # swords whether the purchase came before the sixth Persuasion or after.
    from dune_imperium.rules.acquisition import apply_reserve_acquisition
    from dune_imperium.rules.reveal_turn import (
        add_reveal_persuasion,
        grant_late_reveal_effects,
    )

    owner = _tech_owner(
        "training_depot",
        hand=starting_deck_instance_ids(0)[:5],
        troops_conflict=1,
        troops_supply=8,
        combat_strength=2,
    )
    state = _turn_state(
        owner,
        stacks=((), (), ()),
        reserve_stacks=(("prepare_the_way", 7), ("the_spice_must_flow", 10)),
    )
    revealed = _reveal(state).state
    context = dict(revealed.decision_stack[0].context)
    persuasion = context["persuasion"]
    swords = context["sword_strength"]
    assert isinstance(persuasion, int) and isinstance(swords, int)
    assert 2 <= persuasion < 6
    assert context["tech_granted"] == ""
    bought = apply_reserve_acquisition(
        revealed,
        DomainAction("acquire_reserve", 0, (("card_id", "prepare_the_way"),)),
    ).state
    bumped = replace(
        bought,
        decision_stack=add_reveal_persuasion(bought.decision_stack, 6 - persuasion),
    )
    late = grant_late_reveal_effects(RuleResult(state=bumped)).state
    late_context = dict(late.decision_stack[0].context)
    assert late_context["persuasion"] == 6 - 2
    assert late_context["tech_granted"] == "training_depot"
    assert late_context["sword_strength"] == swords + 2


def test_desert_power_command_tile_pays_only_after_the_persuasion_branch() -> None:
    # OQ-069 (user ruling 2026-09-26): "[2 Persuasion] -OR- [water] ->
    # [sandworm]" [Desert Power card] [Main pp. 10, 20]; with Maker Hooks the
    # sandworm branch stays open, so Training Depot's "Reveal Turn:
    # Command (6+): [2 swords]" [Training Depot tile] [Bloodlines p. 5] does
    # not pay until the owner picks the Persuasion branch.
    from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
    from dune_imperium.rules.reveal_turn import legal_reveal_sandworm_actions

    desert_power = next(
        instance
        for instance in imperium_deck_instance_ids(False, bloodlines=True)
        if ":desert_power:" in instance
    )
    diplomacy = next(
        instance
        for instance in starting_deck_instance_ids(0)
        if ":diplomacy:" in instance
    )
    dune_the_desert_planet = next(
        instance
        for instance in starting_deck_instance_ids(0)
        if ":dune_the_desert_planet:" in instance
    )
    owner = _tech_owner(
        "training_depot",
        hand=(desert_power, diplomacy, dune_the_desert_planet),
        deck=(),
        high_council=True,
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = _turn_state(owner, stacks=((), (), ()))
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, DomainAction(action_id="reveal_turn", actor=0)).state
    context = dict(revealed.decision_stack[0].context)
    assert context["persuasion_generated"] == 4
    assert context["tech_granted"] == ""
    swords = context["sword_strength"]
    assert isinstance(swords, int)

    decline = DomainAction(action_id="decline_reveal_sandworm", actor=0)
    assert decline in legal_reveal_sandworm_actions(revealed, 0)
    declined = engine.apply(revealed, decline).state
    late_context = dict(declined.decision_stack[0].context)
    assert late_context["persuasion_generated"] == 6
    assert late_context["tech_granted"] == "training_depot"
    # The 2 swords must actually reach the Reveal frame's sword strength, not
    # just the tile's recorded name (Training Depot tile "[2 swords]"
    # [Bloodlines p. 5]).
    assert late_context["sword_strength"] == swords + 2


def test_desert_power_command_tile_does_not_pay_on_the_sandworm_branch() -> None:
    # OQ-069 (user ruling 2026-09-26) counterpart: paying water for the
    # sandworm instead of picking the Persuasion branch never generates the
    # 2 Persuasion, so Training Depot's Command (6+) line
    # [Training Depot tile] [Bloodlines p. 5] must not pay either.
    from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
    from dune_imperium.rules.reveal_turn import legal_reveal_sandworm_actions

    desert_power = next(
        instance
        for instance in imperium_deck_instance_ids(False, bloodlines=True)
        if ":desert_power:" in instance
    )
    diplomacy = next(
        instance
        for instance in starting_deck_instance_ids(0)
        if ":diplomacy:" in instance
    )
    dune_the_desert_planet = next(
        instance
        for instance in starting_deck_instance_ids(0)
        if ":dune_the_desert_planet:" in instance
    )
    owner = _tech_owner(
        "training_depot",
        hand=(desert_power, diplomacy, dune_the_desert_planet),
        deck=(),
        high_council=True,
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = _turn_state(owner, stacks=((), (), ()))
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, DomainAction(action_id="reveal_turn", actor=0)).state
    context = dict(revealed.decision_stack[0].context)
    assert context["persuasion_generated"] == 4
    swords = context["sword_strength"]
    assert isinstance(swords, int)

    pay_water = DomainAction(action_id="pay_reveal_water_for_sandworm", actor=0)
    assert pay_water in legal_reveal_sandworm_actions(revealed, 0)
    paid = engine.apply(revealed, pay_water).state
    reveal_frame = next(
        frame for frame in paid.decision_stack if frame.kind == "reveal"
    )
    paid_context = dict(reveal_frame.context)
    assert paid_context["persuasion_generated"] == 4
    assert paid_context["tech_granted"] == ""
    assert paid_context["sword_strength"] == swords


def test_forbidden_weapons_demands_its_choice_in_the_owners_order() -> None:
    from dune_imperium.rules.reveal_turn import legal_finish_reveal_actions
    from dune_imperium.rules.tech import apply_tech_choice, legal_tech_reveal_actions

    owner = _tech_owner(
        "forbidden_weapons",
        hand=starting_deck_instance_ids(0)[:5],
        influence=Influence(emperor=1, fremen=2),
        troops_conflict=1,
        troops_supply=8,
        combat_strength=2,
    )
    result = _reveal(_turn_state(owner, stacks=((), (), ())))
    state = result.state
    # The choice waits on the Reveal frame [Main p. 12] but blocks the finish.
    assert state.decision_stack[-1].kind == "reveal"
    assert legal_finish_reveal_actions(state, 0) == ()
    actions = legal_tech_reveal_actions(state, 0)
    assert [a.action_id for a in actions] == [
        "choose_tech_strength",
        "choose_tech_strength",
        "choose_tech_trash",
    ]
    assert {dict(a.arguments).get("faction") for a in actions[:2]} == {
        "emperor",
        "fremen",
    }
    strength_before = state.players[0].combat_strength
    swords = apply_tech_choice(state, actions[1]).state
    assert swords.players[0].combat_strength == strength_before + 3
    assert swords.players[0].influence.fremen == 1
    assert legal_tech_reveal_actions(swords, 0) == ()
    assert legal_finish_reveal_actions(swords, 0) != ()
    trashed = apply_tech_choice(state, actions[2]).state
    assert trashed.players[0].resources.spice == 0
    assert trashed.players[0].tech_ids == ()
    assert trashed.tech_trash == ("forbidden_weapons",)


def test_forbidden_weapons_trash_may_wait_until_the_spice_is_spent() -> None:
    from dune_imperium.rules.acquisition import legal_reserve_acquisitions
    from dune_imperium.rules.tech import apply_tech_choice, legal_tech_reveal_actions

    owner = _tech_owner(
        "forbidden_weapons",
        hand=starting_deck_instance_ids(0)[:5],
        resources=Resources(spice=3),
    )
    state = _reveal(
        _turn_state(
            owner,
            stacks=((), (), ()),
            reserve_stacks=(("prepare_the_way", 8), ("the_spice_must_flow", 10)),
        )
    ).state
    # Reveal effects resolve in any order: buy with the spice first...
    purchases = legal_reserve_acquisitions(state, 0)
    assert purchases, "the revealed hand should afford a Reserve card"
    bought = state
    for action in purchases[:1]:
        from dune_imperium.rules.acquisition import apply_reserve_acquisition

        bought = apply_reserve_acquisition(state, action).state
    assert bought.players[0].resources.spice <= 3
    # ...then lose "all your spice" — whatever is left.
    trash = next(
        a
        for a in legal_tech_reveal_actions(bought, 0)
        if a.action_id == "choose_tech_trash"
    )
    after = apply_tech_choice(bought, trash).state
    assert after.players[0].resources.spice == 0
    assert after.tech_trash == ("forbidden_weapons",)


def test_panopticon_places_its_spy_when_the_owner_chooses_during_the_reveal() -> None:
    from dune_imperium.rules.reveal_turn import (
        apply_reveal_gain,
        finish_reveal_turn,
        legal_finish_reveal_actions,
        legal_reveal_gain_actions,
    )
    from dune_imperium.rules.tech import apply_place_tech_spy, legal_tech_reveal_actions

    owner = _tech_owner("panopticon", hand=starting_deck_instance_ids(0)[:5])
    result = _reveal(_turn_state(owner, stacks=((), (), ())))
    state = result.state
    # The troop is a Reveal action of its own (OQ-045), the Spy another.
    (gain,) = legal_reveal_gain_actions(state, 0)
    assert gain.action_id == "recruit_reveal_troops"
    state = apply_reveal_gain(state, gain).state
    assert state.players[0].troops_garrison == 3 + 1
    assert state.decision_stack[-1].kind == "reveal"
    (place,) = legal_tech_reveal_actions(state, 0)
    assert place.action_id == "place_tech_spy"
    # Mandatory while a Spy can reach a post.
    assert legal_finish_reveal_actions(state, 0) == ()
    opened = apply_place_tech_spy(state, place).state
    assert opened.decision_stack[-1].kind == "spy_placement"
    placed = apply_spy_placement(
        opened, legal_spy_placement_actions(opened, 0)[0]
    ).state
    assert placed.players[0].spies_supply == 2
    assert placed.decision_stack[-1].kind == "reveal"
    assert legal_tech_reveal_actions(placed, 0) == ()
    assert legal_finish_reveal_actions(placed, 0) != ()

    # Without any Spy left (all boxed) the Spy is still offered and its
    # placement window offers only the decline (OQ-057 (14)), so its owner
    # answers it rather than it lapsing unasked at the finish (user ruling
    # 2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을
    # 연다"). Synthetic: Advanced Data Analysis boxes at most one Spy.
    boxed = _tech_owner(
        "panopticon",
        hand=starting_deck_instance_ids(0)[:5],
        spies_supply=0,
        spies_boxed=3,
    )
    empty = _reveal(_turn_state(boxed, stacks=((), (), ()))).state
    empty = apply_reveal_gain(empty, legal_reveal_gain_actions(empty, 0)[0]).state
    (place,) = legal_tech_reveal_actions(empty, 0)
    assert place.action_id == "place_tech_spy"
    assert legal_finish_reveal_actions(empty, 0) == ()
    opened = apply_place_tech_spy(empty, place).state
    assert opened.decision_stack[-1].kind == "spy_placement"
    decline = DomainAction(action_id="decline_spy_placement", actor=0)
    assert legal_spy_placement_actions(opened, 0) == (decline,)
    declined = apply_spy_placement(opened, decline)
    assert [event.kind for event in declined.events] == ["spy_placement_unavailable"]
    assert declined.state.decision_stack[-1].kind == "reveal"
    assert legal_tech_reveal_actions(declined.state, 0) == ()
    (finish,) = legal_finish_reveal_actions(declined.state, 0)
    finished = finish_reveal_turn(declined.state, finish)
    assert not any("unavailable" in event.kind for event in finished.events)


def test_choam_transports_draws_on_completion_and_scores_at_the_endgame() -> None:
    # "When you complete a contract: draw a card"; "Endgame: worth 1 VP if
    # you have completed four or more contracts" [CHOAM Transports Tech
    # tile]. Panopticon rides along: "Endgame: gain 1 Influence with each
    # Faction where you have 1 or less Influence" [Panopticon Tech tile].
    from dune_imperium.content.uprising.contracts import contract_instance_ids
    from dune_imperium.rules.contract_tiles import receive_contract
    from dune_imperium.rules.phases import resolve_recall_or_endgame
    from dune_imperium.rules.tech import draw_owed_tech_cards

    owner = _tech_owner("choam_transports", "panopticon")
    # The Immediate tile completes as it is taken [Main p. 16]. Outside the
    # owner's own turn (here a Conflict reward) the card is owed to the
    # engine's post-step draw.
    turn = _turn_state(owner, stacks=((), (), ()), config=TECH_CHOAM)
    combat = replace(turn, phase=GamePhase.COMBAT, decision_stack=())
    completed = receive_contract(combat, owner, "contract:immediate")
    assert completed.completed_contract_ids == ("contract:immediate",)
    assert completed.tech_cards_owed == 1
    assert completed.owed_draws == ()
    state = replace(combat, players=(completed, *combat.players[1:]))
    drawn = draw_owed_tech_cards(RuleResult(state=state)).state
    assert len(drawn.players[0].hand) == 5 + 1
    assert drawn.players[0].tech_cards_owed == 0
    # Inside the owner's own turn it is the owner's own step right after
    # the completion ("can't be deferred", Message from designer; user
    # decision 2026-10-10, OQ-106), tests/unit/rules/test_owed_draws.py.
    held = receive_contract(turn, owner, "contract:immediate")
    assert held.tech_cards_owed == 0
    assert [entry[:2] for entry in held.owed_draws] == [("card", "choam_transports")]

    def endgame(contracts: int) -> RuleResult:
        seat = replace(
            owner,
            completed_contract_ids=contract_instance_ids()[:contracts],
            influence=Influence(emperor=2, spacing_guild=1),
            hand=(),
            deck=(),
        )
        return resolve_recall_or_endgame(
            replace(
                _turn_state(seat, stacks=((), (), ()), config=TECH_CHOAM),
                phase=GamePhase.RECALL_OR_ENDGAME,
                first_player=0,
                conflict_deck=(),
                decision_stack=(),
                reveal_order=(0, 1, 2, 3),
            )
        )

    def choam_vp_events(result: RuleResult) -> list[GameEvent]:
        return [
            event
            for event in result.events
            if event.event_id.endswith(":endgame_tech:choam_transports")
        ]

    three, four = endgame(3), endgame(4)
    for result in (three, four):
        seat = result.state.players[0]
        assert result.state.phase is GamePhase.ENDGAME
        # Panopticon: Guild 1 -> 2, BG 0 -> 1, Fremen 0 -> 1; Emperor stays
        # at 2.
        assert (seat.influence.emperor, seat.influence.spacing_guild) == (2, 2)
        assert (seat.influence.bene_gesserit, seat.influence.fremen) == (1, 1)
    # Three contracts fall short: only Panopticon's Guild 2 point is scored.
    assert choam_vp_events(three) == []
    assert three.state.players[0].victory_points == owner.victory_points + 1
    # Four contracts add CHOAM Transports' point.
    (scored,) = choam_vp_events(four)
    assert scored.kind == "victory_points_gained"
    assert dict(scored.payload) == {"amount": 1, "player": 0, "source": "tech"}
    assert four.state.players[0].victory_points == owner.victory_points + 2


def test_ability_actions_round_trip_in_the_tech_catalog() -> None:
    codec = ActionCodec(TECH)
    actions = (
        DomainAction("flip_tech", 0, (("tech_id", "spy_drones"),)),
        DomainAction("choose_tech_strength", 1),
        DomainAction("choose_tech_strength", 1, (("faction", "emperor"),)),
        DomainAction(
            "choose_tech_strength",
            2,
            (("alliance_recipient", 0), ("faction", "fremen")),
        ),
        DomainAction("choose_tech_trash", 3),
        DomainAction("decline_skill", 0),
        DomainAction(
            "agent_turn",
            0,
            (
                ("card_id", "player:0:starter:dagger:0"),
                ("discount", "solari"),
                ("space_id", "high_council"),
            ),
        ),
    )
    for action in actions:
        assert codec.decode(codec.encode(action), action.actor) == action


# --- Tech-only cards and Kota Odax of Ix (slices 6c-6d) --------------------------


def test_ixian_ambassador_gains_spice_and_influence_with_two_tiles() -> None:
    from dune_imperium.rules.agent_effects import resolve_agent_card_effect
    from dune_imperium.rules.reveal_turn import (
        apply_reveal_influence_gain,
        legal_reveal_influence_gain_actions,
        pending_reveal_choices,
    )

    card = "imperium:ixian_ambassador:0"
    owner = _tech_owner("glowglobes", "training_depot", hand=(card,), deck=())
    state = _turn_state(owner, stacks=((), (), ()))
    placed = _visit(state, "assembly_hall")
    assert placed.players[0].resources.spice == 6
    resolved = resolve_agent_card_effect(placed).state
    assert resolved.players[0].resources.spice == 6 + 1

    # Reveal: two tiles make the Influence choice a row of the Reveal frame; with
    # one tile it waits as a pending entry that offers nothing (and so does not
    # hold the end of the Reveal) until a second tile makes its condition true.
    revealed = _reveal(_turn_state(replace(owner, hand=(card,)), stacks=((), (), ())))
    frame = revealed.state.decision_stack[-1]
    assert frame.kind == "reveal"
    assert pending_reveal_choices(dict(frame.context)) == (
        (card, "gain_chosen_influence_if_two_tech"),
    )
    choices = legal_reveal_influence_gain_actions(revealed.state, 0)
    assert len(choices) == 4
    assert set(choices) <= set(UprisingRulesEngine().legal_actions(revealed.state, 0))
    gained = apply_reveal_influence_gain(revealed.state, choices[3]).state
    assert gained.players[0].influence.fremen == 1
    assert pending_reveal_choices(dict(gained.decision_stack[-1].context)) == ()
    single = _reveal(
        _turn_state(
            replace(owner, hand=(card,), tech_ids=("glowglobes",)), stacks=((), (), ())
        )
    )
    assert single.state.decision_stack[-1].kind == "reveal"
    assert legal_reveal_influence_gain_actions(single.state, 0) == ()
    single_actions = UprisingRulesEngine().legal_actions(single.state, 0)
    assert "gain_reveal_influence" not in {a.action_id for a in single_actions}
    # A second tile arriving later makes the waiting choice offer its rows.
    second = replace(
        single.state,
        players=(
            replace(single.state.players[0], tech_ids=("glowglobes", "training_depot")),
            *single.state.players[1:],
        ),
    )
    assert len(legal_reveal_influence_gain_actions(second, 0)) == 4


def test_rapid_engineering_discards_for_a_discounted_tile_or_two_influence() -> None:
    from dune_imperium.rules.intrigue import (
        apply_intrigue_choice,
        apply_intrigue_play,
        legal_intrigue_choice_actions,
        legal_intrigue_play_actions,
    )

    card = "intrigue:rapid_engineering:0"
    owner = _owner(intrigue_cards=(card,), resources=Resources(spice=1))
    state = _turn_state(owner)
    plays = legal_intrigue_play_actions(state, 0)
    # Without three tiles only the discard option is playable.
    assert [dict(a.arguments)["option"] for a in plays] == [0]
    played = apply_intrigue_play(state, plays[0]).state
    discards = legal_intrigue_choice_actions(played, 0)
    chosen = apply_intrigue_choice(played, discards[0]).state
    assert chosen.decision_stack[-1].kind == "tech_acquisition"
    assert dict(chosen.decision_stack[-1].context)["discount"] == 1
    # Gene-Locked Vault costs 2, one spice with the icon's discount.
    bought = _acquire(chosen, "gene_locked_vault:choice=card")
    assert bought.players[0].resources.spice == 0
    assert bought.players[0].tech_ids == ("gene_locked_vault",)

    # A tile left to buy keeps the discard line playable beside the
    # Influence line (user ruling 2026-10-06: an option needs an effect that
    # can change something).
    rich = _turn_state(
        _tech_owner(
            "glowglobes", "training_depot", "panopticon", intrigue_cards=(card,)
        ),
        stacks=(("plasteel_blades",), (), ()),
    )
    options = [
        dict(a.arguments)["option"] for a in legal_intrigue_play_actions(rich, 0)
    ]
    assert options == [0, 1]
    influence = apply_intrigue_play(
        rich, DomainAction("play_intrigue", 0, (("card_id", card), ("option", 1)))
    ).state
    first = legal_intrigue_choice_actions(influence, 0)
    after_first = apply_intrigue_choice(influence, first[0]).state
    # "Choose two": both Factions are named before either Influence moves
    # (designer ruling, OQ-057).
    seat = after_first.players[0]
    assert (
        seat.influence.emperor
        + seat.influence.spacing_guild
        + seat.influence.bene_gesserit
        + seat.influence.fremen
    ) == 0
    second = legal_intrigue_choice_actions(after_first, 0)
    # The second pick excludes the first Faction.
    assert len(second) == 3
    done = apply_intrigue_choice(after_first, second[0]).state
    seat = done.players[0]
    assert (
        sum(
            (
                seat.influence.emperor,
                seat.influence.spacing_guild,
                seat.influence.bene_gesserit,
                seat.influence.fremen,
            )
        )
        == 2
    )



def test_a_cards_tech_discount_must_be_used_when_a_tile_is_affordable() -> None:
    # Designer ruling (Message from designer, OQ-057): Battlefield Research
    # and Rapid Engineering must acquire a tile once played; only an
    # unaffordable offer may be declined. The Landsraad visit's own Acquire
    # Tech stays a "may" [Bloodlines p. 7], which since the user ruling of
    # 2026-10-14 (OQ-095 (2)) lapses at the turn end instead of being
    # declined.
    from dune_imperium.rules.intrigue import (
        apply_intrigue_choice,
        apply_intrigue_play,
        legal_intrigue_choice_actions,
        legal_intrigue_play_actions,
    )

    card = "intrigue:rapid_engineering:0"

    def opened(spice: int, stacks: tuple[tuple[str, ...], ...] = STACKS) -> GameState:
        owner = _owner(intrigue_cards=(card,), resources=Resources(spice=spice))
        state = _turn_state(owner, stacks=stacks)
        played = apply_intrigue_play(state, legal_intrigue_play_actions(state, 0)[0])
        return apply_intrigue_choice(
            played.state, legal_intrigue_choice_actions(played.state, 0)[0]
        ).state

    # Gene-Locked Vault costs 2, one spice with the icon's discount.
    affordable = opened(1)
    assert "decline_tech" not in _tech_actions(affordable)
    assert "gene_locked_vault" in _tech_actions(affordable)

    # Plasteel Blades (3), Panopticon (5), Spy Drones (5): nothing for one
    # spice, so the card is not offered at all (user ruling 2026-10-06); the
    # decline-only frame stays as a safety net (OQ-057 (9)).
    unaffordable = (("plasteel_blades",), ("panopticon",), ("spy_drones",))
    poor = _turn_state(
        _owner(intrigue_cards=(card,), resources=Resources(spice=1)),
        stacks=unaffordable,
    )
    assert legal_intrigue_play_actions(poor, 0) == ()
    broke = push_tech_acquisition(poor, 0, discount=1, source="test").state
    assert list(_tech_actions(broke)) == ["decline_tech"]

    # The visit's own offer needs no refusal either: left unused it lapses
    # at the turn end (OQ-095 (2), user ruling 2026-10-14).
    visit = _visit(_turn_state(_owner()), "assembly_hall")
    assert "decline_tech" not in _tech_actions(visit)
    assert DomainAction("finish_agent_turn", 0) in UprisingRulesEngine().legal_actions(
        visit, 0
    )

def test_battlefield_research_retreats_for_a_tile_or_scores_with_three() -> None:
    from dune_imperium.rules.combat import begin_combat_intrigue
    from dune_imperium.rules.intrigue import (
        apply_intrigue_choice,
        apply_intrigue_play,
        legal_intrigue_choice_actions,
        legal_intrigue_play_actions,
    )

    card = "intrigue:battlefield_research:0"
    owner = _tech_owner(
        "glowglobes",
        "training_depot",
        "panopticon",
        intrigue_cards=(card,),
        troops_supply=8,
        troops_garrison=1,
        troops_conflict=3,
        combat_strength=6,
        has_revealed=True,
        hand=(),
        resources=Resources(spice=2),
    )
    state = replace(
        _turn_state(
            owner,
            stacks=(("plasteel_blades",), ("delivery_bay",), ("servo_receivers",)),
        ),
        phase=GamePhase.COMBAT,
        first_player=0,
        decision_stack=(),
        players=(
            owner,
            *(
                replace(PlayerState(player_id=seat), has_revealed=True)
                for seat in range(1, 4)
            ),
        ),
    )
    combat = begin_combat_intrigue(state).state
    plays = legal_intrigue_play_actions(combat, 0)
    # The VP band is dark green, the Endgame colour, and only the red retreat
    # band is Combat ("COMBAT / ENDGAME" footer) [card face; Main p. 7: "You
    # may play an Endgame Intrigue card only at the end of the game"]. The
    # VP used to be offered in Combat too.
    assert [dict(a.arguments)["option"] for a in plays] == [0]

    retreat = apply_intrigue_play(combat, plays[0]).state
    counts = sorted(
        dict(a.arguments)["count"] for a in legal_intrigue_choice_actions(retreat, 0)
    )
    assert counts == [1, 2]
    picked = apply_intrigue_choice(
        retreat, legal_intrigue_choice_actions(retreat, 0)[0]
    ).state
    assert picked.players[0].troops_conflict in (1, 2)
    assert picked.decision_stack[-1].kind == "tech_acquisition"
    # Plasteel Blades costs 3; the icon's discount brings it to the two spice held.
    assert "plasteel_blades" in _tech_actions(picked)
    bought = _acquire(picked, "plasteel_blades")
    assert bought.players[0].resources.spice == 0
    assert "plasteel_blades" in bought.players[0].tech_ids
    assert bought.decision_stack[-1].kind == "combat_intrigue"



# "To play an Intrigue card, you must meet its conditions and pay its costs."
# [FAQ p. 2] (docs/rules/player-turns.md), and the user's ruling of
# 2026-10-06 that an Intrigue option needs an effect that can change
# something now: an Acquire Tech with no tile the owner can buy changes
# nothing (``tech.tech_acquisition_possible``).


def test_battlefield_research_is_not_offered_without_an_acquirable_tile() -> None:
    from dune_imperium.rules.combat import begin_combat_intrigue
    from dune_imperium.rules.effect_interpreter import option_unplayable_reason
    from dune_imperium.rules.intrigue import legal_intrigue_play_actions

    card = "intrigue:battlefield_research:0"
    option = INTRIGUE_CARDS_BY_ID["battlefield_research"].options[0]

    def combat(spice: int) -> GameState:
        owner = _owner(
            intrigue_cards=(card,),
            troops_supply=8,
            troops_garrison=1,
            troops_conflict=3,
            combat_strength=6,
            has_revealed=True,
            hand=(),
            resources=Resources(spice=spice),
        )
        state = replace(
            _turn_state(
                owner,
                stacks=(("plasteel_blades",), ("panopticon",), ("spy_drones",)),
            ),
            phase=GamePhase.COMBAT,
            first_player=0,
            decision_stack=(),
            players=(
                owner,
                *(
                    replace(PlayerState(player_id=seat), has_revealed=True)
                    for seat in range(1, 4)
                ),
            ),
        )
        return begin_combat_intrigue(state).state

    # Plasteel Blades costs 3, two with the icon's discount.
    poor = combat(1)
    assert legal_intrigue_play_actions(poor, 0) == ()
    assert option_unplayable_reason(poor, 0, option) == AcquireTech(discount=1)
    assert [
        dict(action.arguments)["option"]
        for action in legal_intrigue_play_actions(combat(2), 0)
    ] == [0]


def test_rapid_engineering_tech_line_is_not_offered_without_an_acquirable_tile() -> (
    None
):
    from dune_imperium.rules.effect_interpreter import option_unplayable_reason
    from dune_imperium.rules.intrigue import legal_intrigue_play_actions

    card = "intrigue:rapid_engineering:0"
    option = INTRIGUE_CARDS_BY_ID["rapid_engineering"].options[0]

    def plot(
        spice: int, stacks: tuple[tuple[str, ...], ...] = STACKS, **extra: object
    ) -> GameState:
        owner = _owner(
            intrigue_cards=(card,), resources=Resources(spice=spice), **extra
        )
        return _turn_state(owner, stacks=stacks)

    # The cheapest tops (Glowglobes, Gene-Locked Vault) cost 2, one with the
    # discount; every stack empty with no Secret Project; or only Advanced
    # Data Analysis with no Spy of the owner's on the board to trash.
    lone_analysis = (("advanced_data_analysis",), (), ())
    for state in (
        plot(0),
        plot(6, ((), (), ())),
        plot(6, lone_analysis),
    ):
        assert legal_intrigue_play_actions(state, 0) == ()
        assert option_unplayable_reason(state, 0, option) == AcquireTech(discount=1)
    # One spice, a High Council seat (one spice off [Bloodlines p. 7]), a
    # Secret Project, or a Spy to trash each make it playable.
    for state in (
        plot(1),
        plot(0, high_council=True),
        plot(0, ((), (), ()), secret_project_tech_id="training_depot"),
        plot(
            6,
            lone_analysis,
            spies_supply=2,
            spy_post_ids=(LANDSRAAD_POST,),
        ),
    ):
        assert [
            dict(action.arguments)["option"]
            for action in legal_intrigue_play_actions(state, 0)
        ] == [0]


def test_rapid_engineering_influence_line_needs_a_faction_below_six() -> None:
    from dune_imperium.display.unavailable import intrigue_option_reason
    from dune_imperium.rules.effect_interpreter import option_unplayable_reason
    from dune_imperium.rules.intrigue import (
        apply_intrigue_choice,
        apply_intrigue_play,
        legal_intrigue_choice_actions,
        legal_intrigue_play_actions,
    )

    card = "intrigue:rapid_engineering:0"
    option = INTRIGUE_CARDS_BY_ID["rapid_engineering"].options[1]
    top = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)

    def plot(influence: Influence) -> GameState:
        owner = _tech_owner(
            "glowglobes",
            "training_depot",
            "panopticon",
            intrigue_cards=(card,),
            hand=(),
            influence=influence,
        )
        return _turn_state(owner, stacks=((), (), ()))

    full = plot(top)
    assert legal_intrigue_play_actions(full, 0) == ()
    block = option_unplayable_reason(full, 0, option)
    assert block is not None
    assert intrigue_option_reason(full, 0, option, block)[2] == "top"
    # One Faction below the top: the first pick takes it, the second fizzles.
    one = plot(replace(top, fremen=5))
    play = DomainAction("play_intrigue", 0, (("card_id", card), ("option", 1)))
    assert legal_intrigue_play_actions(one, 0) == (play,)
    played = apply_intrigue_play(one, play).state
    first = legal_intrigue_choice_actions(played, 0)
    assert [dict(action.arguments).get("faction") for action in first] == ["fremen"]
    after = apply_intrigue_choice(played, first[0]).state
    assert [action.action_id for action in legal_intrigue_choice_actions(after, 0)] == [
        "resolve_intrigue_influence_without_faction"
    ]


def test_battlefield_research_scores_its_point_only_at_the_endgame() -> None:
    # "If you have three or more Tech tiles: [VP]" sits in the dark-green
    # Endgame band [Battlefield Research card; Main p. 7].
    from dune_imperium.rules.endgame import begin_endgame_intrigue
    from dune_imperium.rules.intrigue import (
        apply_intrigue_play,
        legal_intrigue_play_actions,
    )

    card = "intrigue:battlefield_research:0"

    def window(*tech_ids: str) -> GameState:
        owner = _tech_owner(*tech_ids, intrigue_cards=(card,), victory_points=1)
        state = replace(
            _turn_state(
                owner,
                stacks=(("plasteel_blades",), ("delivery_bay",), ("servo_receivers",)),
            ),
            phase=GamePhase.ENDGAME,
            first_player=0,
            reveal_order=(0, 1, 2, 3),
            decision_stack=(),
        )
        return begin_endgame_intrigue(state).state

    two = window("glowglobes", "training_depot")
    assert legal_intrigue_play_actions(two, 0) == ()
    three = window("glowglobes", "training_depot", "panopticon")
    plays = legal_intrigue_play_actions(three, 0)
    assert [dict(a.arguments)["option"] for a in plays] == [1]
    scored = apply_intrigue_play(three, plays[0]).state
    assert scored.players[0].victory_points == 2


def test_kota_odax_needs_the_tech_module_and_picks_a_secret_project() -> None:
    from dune_imperium.content.uprising.leaders import leaders_for_choam
    from dune_imperium.rules.tech import (
        apply_secret_project,
        legal_secret_project_actions,
    )

    assert "kota_odax_of_ix" not in {
        leader.leader_id for leader in leaders_for_choam(True, bloodlines=True)
    }
    with pytest.raises(ValueError, match="not available"):
        create_initial_state(
            RulesetConfig(bloodlines=True),
            seed=3,
            leader_ids=("kota_odax_of_ix", *LEADERS[1:]),
        )
    setup = create_initial_state(
        TECH_CHOAM, seed=3, leader_ids=("kota_odax_of_ix", *LEADERS[1:])
    ).state
    assert setup.phase is GamePhase.SETUP
    assert setup.decision_stack[-1].kind == "tech_secret_project"
    bottoms = tuple(stack[-1] for stack in setup.tech_stacks)
    picks = legal_secret_project_actions(setup, 0)
    assert {dict(a.arguments)["tech_id"] for a in picks} == set(bottoms)
    chosen = apply_secret_project(setup, picks[1]).state
    assert chosen.phase is GamePhase.ROUND_START
    seat = chosen.players[0]
    assert seat.secret_project_tech_id == bottoms[1]
    assert tuple(len(stack) for stack in chosen.tech_stacks) == (6, 5, 6)
    # Opponents learn that a tile waits, not which one.
    rival = observe_state(chosen, 1)
    assert rival.players[0].has_secret_project
    own = observe_state(chosen, 0).private
    assert own is not None and own.secret_project_tech_id == bottoms[1]
    check_observation_privacy(chosen)


def test_the_secret_project_tile_is_one_spice_cheaper_wherever_tech_is_acquired() -> (
    None
):
    owner = _owner(
        leader_id="kota_odax_of_ix",
        secret_project_tech_id="sardaukar_high_command",
        resources=Resources(spice=6),
    )
    state = _visit(_turn_state(owner), "assembly_hall")
    offered = _tech_actions(state)
    # Seven spice printed, six as the Secret Project.
    assert "sardaukar_high_command" in offered
    bought = _acquire(state, "sardaukar_high_command")
    seat = bought.players[0]
    assert seat.resources.spice == 0
    assert seat.secret_project_tech_id == ""
    assert seat.tech_ids == ("sardaukar_high_command",)
    assert seat.victory_points == 2
    assert bought.tech_stacks == STACKS


def test_reverse_engineering_takes_spice_or_trades_a_tile_for_cards() -> None:
    from dune_imperium.rules.leader_abilities import (
        apply_kota_signet_action,
        legal_leader_signet_actions,
    )

    signet = "player:0:starter:signet_ring:0"
    owner = _tech_owner(
        "glowglobes",
        leader_id="kota_odax_of_ix",
        hand=(signet,),
        deck=tuple(c for c in starting_deck_instance_ids(0) if c != signet),
    )
    state = _turn_state(owner, stacks=((), (), ()))
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "assembly_hall"
    )
    placed = apply_agent_action(state, action).state
    actions = legal_leader_signet_actions(placed, 0)
    assert [a.action_id for a in actions] == [
        "gain_leader_signet_spice",
        "trash_leader_tech",
    ]
    spice = apply_kota_signet_action(placed, actions[0]).state
    assert spice.players[0].resources.spice == 6 + 1
    traded = apply_kota_signet_action(placed, actions[1]).state
    seat = traded.players[0]
    assert seat.tech_ids == ()
    assert traded.tech_trash == ("glowglobes",)
    # The tile is the arrow's cost; the Intrigue card and the card wait for
    # their own steps in either order (user ruling 2026-10-10, OQ-106), and
    # the turn cannot end before both.
    assert seat.intrigue_cards == () and seat.hand == ()
    rewards = legal_leader_signet_actions(traded, 0)
    assert rewards == (
        DomainAction("resolve_agent_card_effect", 0, (("effect", "intrigue"),)),
        DomainAction("resolve_agent_card_effect", 0, (("effect", "cards"),)),
    )
    engine = UprisingRulesEngine()
    legal = engine.legal_actions(traded, 0)
    assert set(rewards) <= set(legal)
    assert DomainAction("finish_agent_turn", 0) not in legal
    for order in (rewards, tuple(reversed(rewards))):
        working = traded
        for reward in order:
            working = engine.apply(working, reward).state
        seat = working.players[0]
        # Assembly Hall's own Intrigue icon is still pending: only the Signet's.
        assert len(seat.intrigue_cards) == 1
        assert len(seat.hand) == 1
        assert not set(rewards) & set(engine.legal_actions(working, 0))


def test_kota_actions_round_trip_in_the_tech_catalog() -> None:
    codec = ActionCodec(TECH)
    actions = (
        DomainAction("choose_secret_project", 0, (("tech_id", "glowglobes"),)),
        DomainAction("gain_leader_signet_spice", 2),
        DomainAction("trash_leader_tech", 1, (("tech_id", "panopticon"),)),
        DomainAction("gain_reveal_influence", 3, (("faction", "emperor"),)),
    )
    for action in actions:
        assert codec.decode(codec.encode(action), action.actor) == action


def test_random_tech_games_with_kota_finish_under_every_check() -> None:
    report = run_checked_game(
        TECH_CHOAM,
        game_seed=51,
        policy_seed=900_051,
        privacy_interval=10,
        soundness_interval=10,
        engine=UprisingRulesEngine(leader_ids=("kota_odax_of_ix", *LEADERS[1:])),
    )
    assert report.rounds >= 1


def test_reveal_spice_may_be_taken_after_forbidden_weapons_trashes() -> None:
    from dune_imperium.rules.reveal_turn import (
        apply_reveal_gain,
        legal_reveal_gain_actions,
    )
    from dune_imperium.rules.tech import apply_tech_choice, legal_tech_reveal_actions

    # Rebel Supplier: "Reveal: 1 spice, 1 sword" (retail card face).
    supplier = "imperium:rebel_supplier:0"
    owner = _tech_owner(
        "forbidden_weapons", hand=(supplier,), resources=Resources(spice=2)
    )
    state = _reveal(_turn_state(owner, stacks=((), (), ()))).state
    # The spice is a pending gain, not yet in the supply.
    assert state.players[0].resources.spice == 2
    gains = legal_reveal_gain_actions(state, 0)
    assert [dict(a.arguments) for a in gains] == [{"solari": 0, "spice": 1, "water": 0}]
    trash = next(
        a
        for a in legal_tech_reveal_actions(state, 0)
        if a.action_id == "choose_tech_trash"
    )
    trashed = apply_tech_choice(state, trash).state
    assert trashed.players[0].resources.spice == 0
    # Taken afterwards, the revealed spice survives the trash (OQ-045).
    kept = apply_reveal_gain(trashed, gains[0]).state
    assert kept.players[0].resources.spice == 1
    assert legal_reveal_gain_actions(kept, 0) == ()


# --- an acquire Influence never offers a Faction at the top ------------------
# User decision 2026-10-17 (composed-effects plan 5, rule decision 1; OQ-060):
# "the legal-action provider already offers no Faction at 6", so Glowglobes'
# and Navigation Chamber's "Influence with any Faction" offers none either.
# With no Faction left it waits like an Agent box's Influence and the turn's
# end lapses it (OQ-057 (1)); Combat, which has no turn end, asks for a
# confirm instead.

_TOP = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)


def _owing(state: GameState, *keys: str) -> GameState:
    """Put Tech acquire icons (``<tech_id>:<effect>``) on the top frame."""

    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context[TECH_ACQUIRE_PENDING_KEY] = ",".join(keys)
    return replace(
        state,
        decision_stack=(*state.decision_stack[:-1], with_context(frame, context)),
    )


def _bought_glowglobes(influence: Influence) -> GameState:
    """An Assembly Hall visit that bought Glowglobes: its Influence is owed."""

    state = _visit(_turn_state(_owner(influence=influence)), "assembly_hall")
    purchase = next(
        action
        for action in legal_tech_acquisition_actions(state, 0)
        if dict(action.arguments).get("tech_id") == "glowglobes"
    )
    return apply_tech_acquisition(state, purchase).state


def _revealing(influence: Influence) -> GameState:
    owner = _owner(hand=starting_deck_instance_ids(0)[:5], influence=influence)
    state = _gains(_reveal(_turn_state(owner, stacks=((), (), ()))).state)
    assert state.decision_stack[-1].kind == "reveal"
    return state


def _combat_acquire_frame(influence: Influence) -> GameState:
    """Battlefield Research played in Combat bought Glowglobes: the
    acquire-effects-only frame holds its Influence."""

    from dune_imperium.rules.combat import begin_combat_intrigue
    from dune_imperium.rules.intrigue import (
        apply_intrigue_choice,
        apply_intrigue_play,
        legal_intrigue_choice_actions,
        legal_intrigue_play_actions,
    )

    owner = _tech_owner(
        "training_depot",
        "panopticon",
        intrigue_cards=("intrigue:battlefield_research:0",),
        troops_supply=8,
        troops_garrison=1,
        troops_conflict=3,
        combat_strength=6,
        has_revealed=True,
        hand=(),
        resources=Resources(spice=4),
        influence=influence,
    )
    state = replace(
        _turn_state(
            owner,
            stacks=(("glowglobes",), ("delivery_bay",), ("servo_receivers",)),
        ),
        phase=GamePhase.COMBAT,
        first_player=0,
        decision_stack=(),
        players=(
            owner,
            *(
                replace(PlayerState(player_id=seat), has_revealed=True)
                for seat in range(1, 4)
            ),
        ),
    )
    combat = begin_combat_intrigue(state).state
    retreat = apply_intrigue_play(
        combat, legal_intrigue_play_actions(combat, 0)[0]
    ).state
    picked = apply_intrigue_choice(
        retreat, legal_intrigue_choice_actions(retreat, 0)[0]
    ).state
    purchase = next(
        action
        for action in legal_tech_acquisition_actions(picked, 0)
        if dict(action.arguments).get("tech_id") == "glowglobes"
    )
    bought = apply_tech_acquisition(picked, purchase).state
    frame = bought.decision_stack[-1]
    assert frame.kind == "tech_acquisition"
    assert dict(frame.context)["acquire_effects_only"] is True
    return bought


def _influence_lapsed(tech_id: str) -> GameEvent:
    return GameEvent(
        event_id=f"round:1:player:0:tech:{tech_id}:acquire:influence:lapsed",
        kind="tech_acquire_effect_lapsed",
        payload=(("effect", "influence"), ("player", 0), ("tech_id", tech_id)),
    )


def _holds_the_key(state: GameState) -> bool:
    return any(
        TECH_ACQUIRE_PENDING_KEY in dict(frame.context)
        for frame in state.decision_stack
    )


@pytest.mark.parametrize("tech_id", ["glowglobes", "navigation_chamber"])
def test_an_acquire_influence_never_offers_a_faction_at_the_top(tech_id: str) -> None:
    # OQ-060; user decision 2026-10-17, composed-effects plan 5, rule
    # decision 1: the Factions below 6 stay on offer, Emperor and Fremen at
    # the top do not.
    owner = _owner(
        influence=Influence(emperor=6, spacing_guild=5, bene_gesserit=0, fremen=6)
    )
    state = _owing(_turn_state(owner), f"{tech_id}:influence")

    actions = legal_tech_acquire_effect_actions(state, 0)

    assert [dict(action.arguments)["faction"] for action in actions] == [
        "spacing_guild",
        "bene_gesserit",
    ]
    top_pick = DomainAction(
        "resolve_tech_acquire_effect",
        0,
        (("effect", "influence"), ("faction", "fremen"), ("tech_id", tech_id)),
    )
    with pytest.raises(ValueError, match="not a legal Tech acquire effect"):
        apply_tech_acquire_effect(state, top_pick)
    gained = apply_tech_acquire_effect(state, actions[1]).state
    assert gained.players[0].influence.bene_gesserit == 1
    assert not _holds_the_key(gained)


def test_every_faction_at_the_top_lapses_the_acquire_influence_at_the_agent_end() -> (
    None
):
    # OQ-060 and OQ-057 (1); user decision 2026-10-17, composed-effects plan
    # 5, rule decision 1: no row, the end is not held, and the press lapses
    # the icon with its event.
    bought = _bought_glowglobes(_TOP)
    assert dict(bought.decision_stack[-1].context)[TECH_ACQUIRE_PENDING_KEY] == (
        "glowglobes:influence"
    )

    assert legal_tech_acquire_effect_actions(bought, 0) == ()
    legal = UprisingRulesEngine().legal_actions(bought, 0)
    assert [action.action_id for action in legal] == ["finish_agent_turn"]

    cleared = turn_rows.lapse(bought, 0)
    assert not _holds_the_key(cleared.state)
    assert list(cleared.events) == [_influence_lapsed("glowglobes")]

    result = finish_agent_turn_result(bought)
    lapsed = [e for e in result.events if e.kind == "tech_acquire_effect_lapsed"]
    assert lapsed == [_influence_lapsed("glowglobes")]
    assert result.state.players[0].influence == _TOP
    assert not _holds_the_key(result.state)


def test_every_faction_at_the_top_lapses_the_acquire_influence_at_the_reveal_end() -> (
    None
):
    # The same for the Reveal turn's "finish_reveal" (OQ-060, OQ-057 (1);
    # user decision 2026-10-17, composed-effects plan 5, rule decision 1).
    state = _owing(_revealing(_TOP), "navigation_chamber:influence")

    assert legal_tech_acquire_effect_actions(state, 0) == ()
    engine = UprisingRulesEngine()
    assert [a.action_id for a in engine.legal_actions(state, 0)] == ["finish_reveal"]

    result = engine.apply(state, DomainAction("finish_reveal", 0))

    lapsed = [e for e in result.events if e.kind == "tech_acquire_effect_lapsed"]
    assert lapsed == [_influence_lapsed("navigation_chamber")]
    assert not _holds_the_key(result.state)


def test_a_blocked_acquire_influence_still_waits_for_the_other_owed_icon() -> None:
    # OQ-098 (an owed acquire icon holds the turn's end) beside OQ-060 /
    # OQ-057 (1); user decision 2026-10-17, composed-effects plan 5, rule
    # decision 1: only the icon that offers no row stops holding the end.
    keys = ("glowglobes:influence", "plasteel_blades:solari")
    engine = UprisingRulesEngine()
    solari = DomainAction(
        "resolve_tech_acquire_effect",
        0,
        (("effect", "solari"), ("tech_id", "plasteel_blades")),
    )

    agent = _owing(_bought_glowglobes(_TOP), *keys)
    assert engine.legal_actions(agent, 0) == (solari,)
    paid = engine.apply(agent, solari).state
    assert [a.action_id for a in engine.legal_actions(paid, 0)] == [
        "finish_agent_turn"
    ]
    lapsed = [
        e
        for e in finish_agent_turn_result(paid).events
        if e.kind == "tech_acquire_effect_lapsed"
    ]
    assert lapsed == [_influence_lapsed("glowglobes")]

    reveal = _owing(_revealing(_TOP), *keys)
    assert engine.legal_actions(reveal, 0) == (solari,)
    paid = engine.apply(reveal, solari).state
    assert [a.action_id for a in engine.legal_actions(paid, 0)] == ["finish_reveal"]


def test_combat_acquire_influence_with_every_faction_at_the_top_is_confirmed() -> None:
    # Battlefield Research in Combat has no turn end to lapse the icon, so
    # its owner confirms it, as a Conflict reward's (OQ-060; user decision
    # 2026-10-17, composed-effects plan 5, rule decision 1).
    engine = UprisingRulesEngine()
    bought = _combat_acquire_frame(_TOP)
    confirm = DomainAction("resolve_tech_influence_without_faction", 0)
    assert legal_tech_acquire_effect_actions(bought, 0) == (confirm,)
    assert engine.legal_actions(bought, 0) == (confirm,)

    result = engine.apply(bought, confirm)

    assert [e for e in result.events] == [_influence_lapsed("glowglobes")]
    assert [frame.kind for frame in result.state.decision_stack] == ["combat_intrigue"]
    assert result.state.players[0].influence == _TOP


def test_combat_acquire_influence_with_a_faction_below_the_top_has_no_confirm() -> (
    None
):
    # The confirm exists only while no Faction can rise (OQ-060; user
    # decision 2026-10-17, composed-effects plan 5, rule decision 1).
    bought = _combat_acquire_frame(replace(_TOP, fremen=5))

    actions = legal_tech_acquire_effect_actions(bought, 0)

    assert [action.action_id for action in actions] == ["resolve_tech_acquire_effect"]
    assert [dict(action.arguments)["faction"] for action in actions] == ["fremen"]
    with pytest.raises(ValueError):
        apply_tech_influence_without_faction(
            bought, DomainAction("resolve_tech_influence_without_faction", 0)
        )


def test_the_combat_confirm_keeps_the_frame_for_another_owed_icon() -> None:
    # The confirm lapses only the blocked Influence; the frame goes once
    # nothing else is owed (OQ-060, OQ-098; user decision 2026-10-17,
    # composed-effects plan 5, rule decision 1).
    engine = UprisingRulesEngine()
    bought = _owing(
        _combat_acquire_frame(_TOP), "glowglobes:influence", "plasteel_blades:solari"
    )
    confirm = DomainAction("resolve_tech_influence_without_faction", 0)
    assert confirm in engine.legal_actions(bought, 0)

    result = engine.apply(bought, confirm)

    assert [e.event_id for e in result.events] == [
        _influence_lapsed("glowglobes").event_id
    ]
    frame = result.state.decision_stack[-1]
    assert frame.kind == "tech_acquisition"
    assert dict(frame.context)[TECH_ACQUIRE_PENDING_KEY] == "plasteel_blades:solari"
    assert confirm not in engine.legal_actions(result.state, 0)
