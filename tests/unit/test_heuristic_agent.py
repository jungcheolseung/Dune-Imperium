"""Tests for the rule-based heuristic baseline agent."""

import pytest

from dune_imperium.agents import HeuristicAgent
from dune_imperium.agents.heuristic_agent import score_action
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.core import GamePhase
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.observation import PlayerView


def _view(player: int = 0) -> PlayerView:
    return PlayerView(player=player, revision=0, phase=GamePhase.PLAYER_TURNS)


def _action(
    action_id: str,
    *arguments: tuple[str, ActionValue],
    actor: int = 0,
) -> DomainAction:
    return DomainAction(action_id=action_id, actor=actor, arguments=arguments)


def _imperium_instance_ids_by_cost() -> tuple[str, str]:
    """Real cheapest and dearest Imperium instance IDs from the manifest."""

    priced = sorted(
        (
            entry
            for entry in IMPERIUM_CARDS_BY_ID.values()
            if entry.acquisition_cost is not None
        ),
        key=lambda entry: (entry.acquisition_cost or 0, entry.card.card_id),
    )
    cheapest, dearest = priced[0], priced[-1]
    assert (cheapest.acquisition_cost or 0) < (dearest.acquisition_cost or 0)
    return (
        f"imperium:{cheapest.card.card_id}:0",
        f"imperium:{dearest.card.card_id}:0",
    )


def test_requires_at_least_one_legal_action() -> None:
    with pytest.raises(ValueError, match="at least one legal action"):
        HeuristicAgent(seed=1).choose_action(_view(), ())


def test_rejects_actions_for_another_player() -> None:
    foreign = (_action("agent_turn", actor=2),)
    with pytest.raises(ValueError, match="observing player"):
        HeuristicAgent(seed=1).choose_action(_view(player=0), foreign)


def test_rejects_negative_seeds() -> None:
    with pytest.raises(ValueError, match="not be negative"):
        HeuristicAgent(seed=-1)


def test_same_seed_reproduces_tie_breaks() -> None:
    tied = tuple(_action(f"unknown_option_{index}") for index in range(6))
    first = HeuristicAgent(seed=11)
    second = HeuristicAgent(seed=11)

    choices = [first.choose_action(_view(), tied) for _ in range(10)]
    assert choices == [second.choose_action(_view(), tied) for _ in range(10)]
    assert all(choice in tied for choice in choices)


def test_prefers_acquiring_over_declining() -> None:
    cheap_id, _ = _imperium_instance_ids_by_cost()
    actions = (
        _action("decline_agent_card_acquisition"),
        _action("acquire_imperium", ("instance_id", cheap_id)),
    )

    chosen = HeuristicAgent(seed=3).choose_action(_view(), actions)
    assert chosen.action_id == "acquire_imperium"


def test_prefers_the_more_expensive_imperium_card() -> None:
    cheap_id, dear_id = _imperium_instance_ids_by_cost()
    actions = (
        _action("acquire_imperium", ("instance_id", cheap_id)),
        _action("acquire_imperium", ("instance_id", dear_id)),
    )

    chosen = HeuristicAgent(seed=4).choose_action(_view(), actions)
    assert chosen.arguments == (("instance_id", dear_id),)


def test_prefers_the_more_expensive_reserve_stack() -> None:
    actions = (
        _action("acquire_reserve", ("card_id", "prepare_the_way")),
        _action("acquire_reserve", ("card_id", "the_spice_must_flow")),
    )

    chosen = HeuristicAgent(seed=5).choose_action(_view(), actions)
    assert chosen.arguments == (("card_id", "the_spice_must_flow"),)


def test_prefers_full_troop_deployment() -> None:
    actions = tuple(
        _action("deploy_troops", ("count", count)) for count in range(4)
    )

    chosen = HeuristicAgent(seed=6).choose_action(_view(), actions)
    assert chosen.arguments == (("count", 3),)


def test_prefers_placing_agents_over_revealing() -> None:
    actions = (
        _action("reveal_turn"),
        _action("agent_turn", ("card_id", "card"), ("space_id", "arrakeen")),
    )

    chosen = HeuristicAgent(seed=7).choose_action(_view(), actions)
    assert chosen.action_id == "agent_turn"


def test_prefers_permanent_upgrade_spaces() -> None:
    actions = (
        _action("agent_turn", ("card_id", "card"), ("space_id", "arrakeen")),
        _action("agent_turn", ("card_id", "card"), ("space_id", "swordmaster")),
        _action("agent_turn", ("card_id", "card"), ("space_id", "high_council")),
    )

    chosen = HeuristicAgent(seed=8).choose_action(_view(), actions)
    assert chosen.arguments[-1] == ("space_id", "swordmaster")


def test_unknown_actions_fall_back_to_a_legal_choice() -> None:
    actions = (_action("some_future_mechanic", ("value", 1)),)

    assert HeuristicAgent(seed=9).choose_action(_view(), actions) == actions[0]


def test_score_ordering_matches_the_strategy_tiers() -> None:
    complete = score_action(_action("complete_contract"))
    place = score_action(
        _action("agent_turn", ("card_id", "card"), ("space_id", "arrakeen"))
    )
    reveal = score_action(_action("reveal_turn"))
    unknown = score_action(_action("mystery_action"))
    decline = score_action(_action("decline_gather_intelligence"))
    passing = score_action(_action("pass_combat_intrigue"))

    assert complete > place > reveal > unknown > decline > passing


def test_missing_cost_data_still_scores_as_an_acquisition() -> None:
    nameless = score_action(
        _action("acquire_imperium", ("instance_id", "imperium:not_a_card:0"))
    )
    reveal = score_action(_action("reveal_turn"))

    assert nameless > reveal
