"""Tests for the fixed integer Uprising action codec."""

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ACTION_CODEC_VERSION, ActionCodec
from dune_imperium.core import DomainAction, PlayerDecision
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation import run_random_round


def test_catalog_is_fixed_and_versioned_for_a_ruleset() -> None:
    first = ActionCodec(RulesetConfig())
    second = ActionCodec(RulesetConfig())

    assert ACTION_CODEC_VERSION == 71
    assert first.catalog == second.catalog
    assert first.size == len(first.catalog)
    assert first.size == 3923


def test_choam_contract_choice_round_trips_only_in_the_module_catalog() -> None:
    action = DomainAction(
        action_id="take_contract",
        actor=2,
        arguments=(("instance_id", "contract:high_council_ii"),),
    )
    codec = ActionCodec(RulesetConfig(choam_module=True))

    assert codec.decode(codec.encode(action), actor=2) == action
    assert codec.size == 4169

    try:
        ActionCodec(RulesetConfig()).encode(action)
    except ValueError as error:
        assert "not present" in str(error)
    else:
        raise AssertionError("module-off codec accepted a Contract action")


def test_choam_contract_completion_and_spy_choices_round_trip() -> None:
    codec = ActionCodec(RulesetConfig(choam_module=True))
    actions = (
        DomainAction(
            action_id="complete_contract",
            actor=1,
            arguments=(("instance_id", "contract:arrakeen_ii"),),
        ),
        DomainAction(
            action_id="place_contract_spy",
            actor=1,
            arguments=(("post_id", "arrakis-spice-refinery-arrakeen"),),
        ),
        DomainAction(
            action_id="recall_spy_for_contract",
            actor=1,
            arguments=(("post_id", "arrakis-spice-refinery-arrakeen"),),
        ),
        DomainAction(action_id="keep_contract_reveal_spice", actor=1),
        DomainAction(action_id="trash_contract_reveal_for_vp", actor=1),
    )

    for action in actions:
        assert codec.decode(codec.encode(action), actor=1) == action


def test_corrinth_city_staged_payment_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    actions = (
        DomainAction(
            action_id="select_corrinth_city_discard",
            actor=0,
            arguments=(("card_id", "imperium:spacing_guild_s_favor:0"),),
        ),
        DomainAction(
            action_id="pay_corrinth_city",
            actor=0,
            arguments=(("card_id", "player:0:starter:dagger:0"),),
        ),
    )

    for action in actions:
        assert codec.decode(codec.encode(action), actor=0) == action


def test_agent_card_spice_payment_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(action_id="pay_agent_card_spice", actor=0)

    assert codec.decode(codec.encode(action), actor=0) == action


def test_desert_power_reveal_choices_round_trip() -> None:
    codec = ActionCodec(RulesetConfig())
    actions = (
        DomainAction(action_id="decline_reveal_sandworm", actor=0),
        DomainAction(action_id="pay_reveal_water_for_sandworm", actor=2),
    )

    for action in actions:
        assert codec.decode(codec.encode(action), actor=action.actor) == action


def test_long_live_the_fighters_choices_round_trip() -> None:
    codec = ActionCodec(RulesetConfig())
    actions = (
        DomainAction(
            action_id="select_long_live_fighters_draw",
            actor=0,
            arguments=(("card_id", "player:0:starter:dagger:0"),),
        ),
        DomainAction(
            action_id="select_long_live_fighters_discard",
            actor=2,
            arguments=(("card_id", "imperium:sardaukar_soldier:0"),),
        ),
    )

    for action in actions:
        assert codec.decode(codec.encode(action), actor=action.actor) == action


def test_subversive_advisor_agent_turn_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="agent_turn",
        actor=0,
        arguments=(
            ("card_id", "imperium:subversive_advisor:0"),
            ("space_id", "dutiful_service"),
        ),
    )

    assert codec.decode(codec.encode(action), actor=0) == action


def test_agent_card_solari_acquisition_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="acquire_imperium_with_solari",
        actor=0,
        arguments=(("instance_id", "imperium:sardaukar_soldier:0"),),
    )

    assert codec.decode(codec.encode(action), actor=0) == action


def test_reveal_influence_exchange_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="exchange_reveal_influence",
        actor=0,
        arguments=(
            ("alliance_recipient", 2),
            ("gained_faction", "emperor"),
            ("lost_faction", "emperor"),
        ),
    )

    assert codec.decode(codec.encode(action), actor=0) == action


def test_reveal_spice_influence_payment_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="pay_reveal_spice_influence",
        actor=0,
        arguments=(("faction", "spacing_guild"),),
    )

    assert codec.decode(codec.encode(action), actor=0) == action


def test_agent_card_spy_choice_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="place_agent_card_spy",
        actor=1,
        arguments=(("post_id", "bene-gesserit-espionage-secrets"),),
    )

    assert codec.decode(codec.encode(action), actor=1) == action


def test_agent_card_influence_choice_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="choose_agent_card_influence",
        actor=2,
        arguments=(("faction", "fremen"),),
    )

    assert codec.decode(codec.encode(action), actor=2) == action


def test_reveal_spy_placement_choice_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="place_reveal_spy",
        actor=3,
        arguments=(("post_id", "emperor-sardaukar-dutiful-service"),),
    )

    assert codec.decode(codec.encode(action), actor=3) == action


def test_starting_card_actions_share_an_index_between_players() -> None:
    codec = ActionCodec(RulesetConfig())
    first = DomainAction(
        action_id="agent_turn",
        actor=0,
        arguments=(
            ("card_id", "player:0:starter:dagger:0"),
            ("space_id", "assembly_hall"),
        ),
    )
    second = DomainAction(
        action_id="agent_turn",
        actor=3,
        arguments=(
            ("card_id", "player:3:starter:dagger:0"),
            ("space_id", "assembly_hall"),
        ),
    )

    assert codec.encode(first) == codec.encode(second)
    assert codec.decode(codec.encode(first), actor=3) == second


def test_infiltrate_agent_action_round_trips_with_selected_spy() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="agent_turn",
        actor=2,
        arguments=(
            ("card_id", "player:2:starter:dagger:0"),
            (
                "infiltrate_post_id",
                "landsraad-assembly-hall-gather-support",
            ),
            ("space_id", "assembly_hall"),
        ),
    )

    assert codec.decode(codec.encode(action), actor=2) == action


def test_reserve_agent_action_round_trips_without_actor_rewriting() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="agent_turn",
        actor=2,
        arguments=(
            ("card_id", "reserve:prepare_the_way:7"),
            ("space_id", "assembly_hall"),
        ),
    )

    assert codec.decode(codec.encode(action), actor=2) == action


def test_imperium_agent_action_round_trips_with_stable_instance_id() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="agent_turn",
        actor=2,
        arguments=(
            ("card_id", "imperium:maula_pistol:0"),
            ("space_id", "arrakeen"),
        ),
    )

    assert codec.decode(codec.encode(action), actor=2) == action


def test_agent_card_trash_round_trips_with_actor_owned_starting_card() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="trash_agent_card",
        actor=2,
        arguments=(("card_id", "player:2:starter:dagger:0"),),
    )

    assert codec.decode(codec.encode(action), actor=2) == action


def test_endgame_wild_match_round_trips_with_both_card_ids() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="match_endgame_wild_icon",
        actor=1,
        arguments=(
            ("matching_card_id", "objective_crysknife_1"),
            ("wild_card_id", "propaganda"),
        ),
    )

    assert codec.decode(codec.encode(action), actor=1) == action


def test_every_action_in_seeded_round_round_trips_through_codec() -> None:
    codec = ActionCodec(RulesetConfig())
    result = run_random_round(
        UprisingRulesEngine(),
        RulesetConfig(),
        game_seed=4,
        policy_seed=4004,
    )

    for step in result.replay.steps:
        if isinstance(step, DomainAction):
            assert codec.decode(codec.encode(step), step.actor) == step


def test_legal_action_mask_marks_exactly_the_supplied_actions() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    player = decision.owner
    legal_actions = engine.legal_actions(state, player)
    codec = ActionCodec(state.config)

    mask = codec.legal_action_mask(legal_actions)
    enabled = tuple(index for index, value in enumerate(mask) if value)

    assert len(mask) == codec.size
    assert len(enabled) == len(legal_actions)
    assert {codec.decode(index, player) for index in enabled} == set(legal_actions)
