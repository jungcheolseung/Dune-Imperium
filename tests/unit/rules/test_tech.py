"""Tests for the Tech Module's Ixian Embassy and Tech tile acquisition.

Rule source: ``docs/rules/bloodlines.md`` section 5 [Bloodlines pp. 6-7, 12]
and the eighteen Tech tile faces transcribed on 2026-09-07.
"""

from dataclasses import replace

import pytest

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
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
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
    observe_state,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    legal_board_effect_actions,
    resolve_board_effect,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.optional_trash import legal_optional_trash_actions
from dune_imperium.rules.setup import create_draft_initial_state, create_initial_state
from dune_imperium.rules.spy_moves import (
    apply_spy_placement,
    legal_spy_placement_actions,
)
from dune_imperium.rules.tech import (
    apply_tech_acquisition,
    legal_tech_acquisition_actions,
    push_tech_acquisition,
    tech_cost,
)
from dune_imperium.simulation.invariants import check_observation_privacy
from dune_imperium.simulation.sweep import run_checked_game

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


def _acquire(state: GameState, key: str) -> GameState:
    return apply_tech_acquisition(state, _tech_actions(state)[key]).state


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


def test_a_landsraad_visit_offers_the_face_up_tiles_the_owner_can_afford() -> None:
    state = _visit(_turn_state(_owner(resources=Resources(spice=2))), "assembly_hall")

    offered = _tech_actions(state)
    # Glowglobes (2) with any Faction, Gene-Locked Vault (2) either way; the
    # 3-spice Advanced Data Analysis also needs a placed Spy.
    assert "decline_tech" in offered
    assert {key for key in offered if key.startswith("glowglobes")} == {
        f"glowglobes:faction={faction}"
        for faction in ("emperor", "spacing_guild", "bene_gesserit", "fremen")
    }
    assert {key for key in offered if key.startswith("gene_locked_vault")} == {
        "gene_locked_vault:choice=intrigue",
        "gene_locked_vault:choice=card",
    }
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
    assert "gene_locked_vault:choice=card" in offered
    assert tech_cost(owner, TECH_TILES_BY_ID["training_depot"]) == 0
    bought = _acquire(state, "gene_locked_vault:choice=card")
    seat = bought.players[0]
    assert seat.resources.spice == 0
    assert len(seat.hand) == 4 + 1  # one card played, one drawn


def test_declining_keeps_the_stacks_and_closes_the_offer() -> None:
    state = _visit(_turn_state(_owner()), "assembly_hall")
    declined = apply_tech_acquisition(state, _tech_actions(state)["decline_tech"])
    assert declined.events[0].kind == "tech_declined"
    assert declined.state.tech_stacks == STACKS
    assert legal_tech_acquisition_actions(declined.state, 0) == ()


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
        "decline_tech",
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
    assert {"forbidden_weapons", "forbidden_weapons:destroy_shield_wall=True"} <= set(
        offered
    )
    kept = _acquire(state, "forbidden_weapons")
    assert kept.shield_wall_present
    assert kept.players[0].troops_garrison == 3 + 1
    # The troop counts as recruited this turn [Bloodlines p. 7] [FAQ p. 4].
    assert dict(kept.decision_stack[-1].context).get("troops_recruited") == 1

    destroyed = apply_tech_acquisition(
        state, offered["forbidden_weapons:destroy_shield_wall=True"]
    )
    assert not destroyed.state.shield_wall_present
    assert any(event.kind == "shield_wall_destroyed" for event in destroyed.events)


def test_without_the_wall_the_detonation_variant_disappears() -> None:
    state = _visit(
        _turn_state(
            _owner(), stacks=(("servo_receivers",), (), ()), shield_wall_present=False
        ),
        "assembly_hall",
    )
    assert set(_tech_actions(state)) == {"decline_tech", "servo_receivers"}


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
def test_immediate_acquire_effects(tech_id: str, check: object) -> None:
    owner = _owner(resources=Resources(solari=4, spice=12))
    state = _visit(_turn_state(owner, stacks=((tech_id,), (), ())), "assembly_hall")
    bought = _acquire(state, tech_id)
    assert check(bought.players[0])  # type: ignore[operator]
    assert bought.players[0].tech_ids == (tech_id,)


def test_planetary_array_opens_an_optional_trash_after_the_visit() -> None:
    state = _visit(
        _turn_state(_owner(), stacks=(("planetary_array",), (), ())), "assembly_hall"
    )
    bought = _acquire(state, "planetary_array")
    assert bought.decision_stack[-1].kind == "optional_trash"
    actions = legal_optional_trash_actions(bought, 0)
    assert actions[0].action_id == "decline_optional_trash"
    assert len(actions) == 1 + 4 + 1  # hand (Dagger played) + played card


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
    second = legal_spy_placement_actions(placed, 0)
    assert LANDSRAAD_POST not in {dict(a.arguments)["post_id"] for a in second}
    done = apply_spy_placement(placed, second[0]).state
    assert done.players[0].spies_supply == 1
    assert done.decision_stack[-1].kind == "turn"


def test_ornithopter_fleet_matches_every_face_up_battle_card_at_once() -> None:
    owner = _owner(
        objective_ids=("propaganda",),
        won_conflict_ids=("skirmish_ornithopter", "storms_in_the_south"),
        face_down_battle_card_ids=(),
    )
    state = _visit(
        _turn_state(owner, stacks=(("ornithopter_fleet",), (), ())), "assembly_hall"
    )
    result = apply_tech_acquisition(state, _tech_actions(state)["ornithopter_fleet"])
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
    assert "gene_locked_vault:choice=intrigue" in offered  # 2 - 1 = 1 spice
    assert not any(key.startswith("training_depot") for key in offered)
    bought = _acquire(opened.state, "gene_locked_vault:choice=intrigue")
    assert bought.players[0].resources.spice == 0
    assert len(bought.players[0].intrigue_cards) == 1
    assert bought.decision_stack[-1].kind == "turn"


def test_a_tech_discount_icon_over_empty_stacks_does_nothing() -> None:
    state = _turn_state(_owner(), stacks=((), (), ()))
    result = push_tech_acquisition(state, 0, discount=1, source="test")
    assert result.state is state
    assert result.events[0].kind == "tech_acquisition_unavailable"


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
            "acquire_tech",
            2,
            (("faction", "fremen"), ("tech_id", "navigation_chamber")),
        ),
        DomainAction(
            "acquire_tech", 3, (("choice", "card"), ("tech_id", "gene_locked_vault"))
        ),
        DomainAction(
            "acquire_tech",
            0,
            (("post_id", SIETCH_POST), ("tech_id", "advanced_data_analysis")),
        ),
        DomainAction(
            "acquire_tech",
            0,
            (("destroy_shield_wall", True), ("tech_id", "forbidden_weapons")),
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
