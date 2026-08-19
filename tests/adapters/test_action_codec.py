"""Tests for the fixed integer Uprising action codec."""

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ACTION_CODEC_VERSION, ActionCodec
from dune_imperium.core import DomainAction, PlayerDecision
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation import run_random_round


def test_catalog_is_fixed_and_versioned_for_a_ruleset() -> None:
    first = ActionCodec(RulesetConfig())
    second = ActionCodec(RulesetConfig())

    assert ACTION_CODEC_VERSION == 17
    assert first.catalog == second.catalog
    assert first.size == len(first.catalog)
    assert first.size == 1114


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
