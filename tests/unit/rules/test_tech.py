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
from dune_imperium.core.engine import RuleResult
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
    from dune_imperium.rules.combat import finish_combat

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
    winner = finish_combat(state).state.players[0]
    assert winner.face_down_battle_card_ids == ("propaganda", "skirmish_wild")
    assert winner.victory_points == 2


def test_ornithopter_fleet_blocks_crysknife_flips_but_frees_ornithopter_ones() -> None:
    from dune_imperium.content.uprising.types import BattleIcon
    from dune_imperium.rules.effect_interpreter import flippable_battle_card_ids

    seat = _tech_owner("ornithopter_fleet", won_conflict_ids=("skirmish_wild",))
    assert flippable_battle_card_ids(seat, BattleIcon.CRYSKNIFE) == ()
    assert flippable_battle_card_ids(seat, BattleIcon.ORNITHOPTER) == ("skirmish_wild",)


def test_planetary_array_owes_a_card_the_engine_draws_after_the_win() -> None:
    from dune_imperium.rules.combat import finish_combat
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
    finished = finish_combat(state)
    assert finished.state.players[0].tech_cards_owed == 1
    drawn = draw_owed_tech_cards(finished).state
    assert drawn.players[0].tech_cards_owed == 0
    assert len(drawn.players[0].hand) == 1


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
    assert drones.state.decision_stack[-1].kind == "optional_trash"

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

    # Without any Spy left (all boxed) the effect lapses at the finish.
    boxed = _tech_owner(
        "panopticon",
        hand=starting_deck_instance_ids(0)[:5],
        spies_supply=0,
        spies_boxed=3,
    )
    lapsing = _reveal(_turn_state(boxed, stacks=((), (), ()))).state
    lapsing = apply_reveal_gain(lapsing, legal_reveal_gain_actions(lapsing, 0)[0]).state
    assert legal_tech_reveal_actions(lapsing, 0) == ()
    (finish,) = legal_finish_reveal_actions(lapsing, 0)
    finished = finish_reveal_turn(lapsing, finish)
    assert any(e.kind == "tech_reveal_unavailable" for e in finished.events)


def test_choam_transports_draws_on_completion_and_scores_at_the_endgame() -> None:
    from dune_imperium.rules.contract_tiles import receive_contract
    from dune_imperium.rules.phases import resolve_recall_or_endgame
    from dune_imperium.rules.tech import draw_owed_tech_cards

    owner = _tech_owner("choam_transports", "panopticon")
    completed = (
        receive_contract(owner, "contract:immediate_solari_i") if False else owner
    )
    owed = replace(completed, tech_cards_owed=1)
    state = _turn_state(owed, stacks=((), (), ()), config=TECH_CHOAM)
    drawn = draw_owed_tech_cards(RuleResult(state=state)).state
    assert len(drawn.players[0].hand) == 5 + 1

    four = replace(
        owner,
        completed_contract_ids=tuple(f"contract:test_{i}" for i in range(4))
        if False
        else (),
        influence=Influence(emperor=2, spacing_guild=1),
        hand=(),
        deck=(),
    )
    endgame = replace(
        _turn_state(four, stacks=((), (), ()), config=TECH_CHOAM),
        phase=GamePhase.RECALL_OR_ENDGAME,
        first_player=0,
        conflict_deck=(),
        decision_stack=(),
        reveal_order=(0, 1, 2, 3),
    )
    ended = resolve_recall_or_endgame(endgame).state
    seat = ended.players[0]
    assert ended.phase is GamePhase.ENDGAME
    # Panopticon: Guild 1 -> 2, BG 0 -> 1, Fremen 0 -> 1; Emperor stays at 2.
    assert (seat.influence.emperor, seat.influence.spacing_guild) == (2, 2)
    assert (seat.influence.bene_gesserit, seat.influence.fremen) == (1, 1)


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
    )

    card = "imperium:ixian_ambassador:0"
    owner = _tech_owner("glowglobes", "training_depot", hand=(card,), deck=())
    state = _turn_state(owner, stacks=((), (), ()))
    placed = _visit(state, "assembly_hall")
    assert placed.players[0].resources.spice == 6
    resolved = resolve_agent_card_effect(placed).state
    assert resolved.players[0].resources.spice == 6 + 1

    # Reveal: two tiles open the Influence choice; one tile defers it.
    revealed = _reveal(_turn_state(replace(owner, hand=(card,)), stacks=((), (), ())))
    frame = revealed.state.decision_stack[-1]
    assert frame.kind == "reveal_choice"
    choices = legal_reveal_influence_gain_actions(revealed.state, 0)
    assert len(choices) == 4
    gained = apply_reveal_influence_gain(revealed.state, choices[3]).state
    assert gained.players[0].influence.fremen == 1
    single = _reveal(
        _turn_state(
            replace(owner, hand=(card,), tech_ids=("glowglobes",)), stacks=((), (), ())
        )
    )
    assert single.state.decision_stack[-1].kind == "reveal"


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

    rich = _turn_state(
        _tech_owner(
            "glowglobes", "training_depot", "panopticon", intrigue_cards=(card,)
        ),
        stacks=((), (), ()),
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
    second = legal_intrigue_choice_actions(after_first, 0)
    # "Choose two": the second pick excludes the first Faction.
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
    assert [dict(a.arguments)["option"] for a in plays] == [0, 1]
    scored = apply_intrigue_play(combat, plays[1]).state
    assert scored.players[0].victory_points == 1 + 1

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
    # Assembly Hall's own Intrigue icon is still pending: only the Signet's.
    assert len(seat.intrigue_cards) == 1
    assert len(seat.hand) == 1


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
