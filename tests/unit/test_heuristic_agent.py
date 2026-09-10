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
    actions = tuple(_action("deploy_troops", ("count", count)) for count in range(4))

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


def test_tech_tiles_are_bought_and_the_scoring_ones_first() -> None:
    # Bloodlines Tech Module: any buy outranks the decline; a tile that
    # scores or pays back at once (Sardaukar High Command's VP) outranks a
    # plain upgrade (Glowglobes).
    decline = score_action(_action("decline_tech"))
    plain = score_action(_action("acquire_tech", ("tech_id", "glowglobes")))
    scoring = score_action(
        _action("acquire_tech", ("tech_id", "sardaukar_high_command"))
    )
    reveal = score_action(_action("reveal_turn"))
    assert scoring > plain > reveal > decline
    chosen = HeuristicAgent(seed=1).choose_action(
        _view(),
        (
            _action("decline_tech"),
            _action("acquire_tech", ("tech_id", "glowglobes")),
            _action("acquire_tech", ("tech_id", "sardaukar_high_command")),
        ),
    )
    assert dict(chosen.arguments)["tech_id"] == "sardaukar_high_command"


def test_switch_graft_card_never_outranks_a_resolvable_box() -> None:
    """Two grafted boxes whose offers rank below the switch would otherwise
    loop forever (Ghola copying CHOAM Demands, 2026-09-08 sweep seed 32)."""

    agent = HeuristicAgent(seed=1)
    complete = _action("complete_contract_by_card", ("instance_id", "contract:acquire"))
    decline = _action("decline_agent_card_payment")
    switch = _action("switch_graft_card")
    assert agent.choose_action(_view(), (switch, complete)) == complete
    assert agent.choose_action(_view(), (switch, decline)) == decline
    # With nothing of the box left to resolve, the switch is the way on.
    withdraw = _action("withdraw_troops", ("count", 1))
    assert agent.choose_action(_view(), (withdraw, switch)) == switch


def test_tleilaxu_acquisition_scales_with_the_printed_specimen_cost() -> None:
    """A Tleilaxu card is ranked like an Imperium card: base plus cost.

    "Tleilaxu cards come from the Tleilaxu Row and cost specimens to
    acquire rather than persuasion" [Immortality p. 8].
    """

    cheap = score_action(
        _action("acquire_tleilaxu", ("instance_id", "tleilaxu:contaminator:0"))
    )
    dear = score_action(
        _action("acquire_tleilaxu", ("instance_id", "tleilaxu:twisted_mentat:0"))
    )
    # Contaminator costs one specimen, Twisted Mentat four.
    assert dear - cheap == pytest.approx(3.5)
    assert cheap > score_action(_action("decline_agent_card_acquisition"))
    # An unknown instance ID degrades to the flat base instead of failing.
    assert score_action(
        _action("acquire_tleilaxu", ("instance_id", "tleilaxu:nonesuch:0"))
    ) == pytest.approx(2.5)


def test_tleilaxu_acquisition_prefers_paying_boxes_and_the_deck_top() -> None:
    """Acquisition boxes and the first genetic marker's deck-top option."""

    plain = score_action(
        _action("acquire_tleilaxu", ("instance_id", "tleilaxu:face_dancer:0"))
    )
    paying = score_action(
        _action("acquire_tleilaxu", ("instance_id", "tleilaxu:subject_x_137:0"))
    )
    # Both cost two specimens; Subject X-137 also advances the Tleilaxu
    # track the moment it is bought.
    assert paying - plain == pytest.approx(1.0)
    to_deck_top = score_action(
        _action(
            "acquire_tleilaxu",
            ("instance_id", "tleilaxu:face_dancer:0"),
            ("to_deck_top", True),
        )
    )
    assert to_deck_top - plain == pytest.approx(0.5)


def test_research_branch_prefers_the_richer_destination_space() -> None:
    """A Research space "triggers another research icon and immediately
    advances her token again" [Immortality p. 6], so it leads the table."""

    research = score_action(_action("choose_research_space", ("space_id", "c3r1")))
    influence = score_action(_action("choose_research_space", ("space_id", "c6r6")))
    specimen = score_action(_action("choose_research_space", ("space_id", "c1r3")))
    solari = score_action(_action("choose_research_space", ("space_id", "c5r5")))
    assert research > influence > specimen > solari
    assert solari > score_action(_action("decline_research_bonus"))
    # An unknown space degrades to the flat base.
    assert score_action(
        _action("choose_research_space", ("space_id", "c9r9"))
    ) == pytest.approx(3.0)
    chosen = HeuristicAgent(seed=1).choose_action(
        _view(),
        (
            _action("choose_research_space", ("space_id", "c3r3")),
            _action("choose_research_space", ("space_id", "c3r1")),
        ),
    )
    assert dict(chosen.arguments)["space_id"] == "c3r1"


def test_reclaimed_forces_takes_the_troops_over_one_track_step() -> None:
    """Three specimens buy "recruit 2 troops" or one Tleilaxu advance
    [Immortality p. 9]; two units outweigh one step on the same scale."""

    troops = score_action(_action("acquire_reclaimed_forces", ("choice", "troops")))
    tleilaxu = score_action(_action("acquire_reclaimed_forces", ("choice", "tleilaxu")))
    assert troops > tleilaxu > 0.0


def test_intrigue_lines_are_used_before_the_card_is_finished() -> None:
    """An Intrigue card's separate printed lines are used one at a time and
    paid when used (OQ-058); at equal scores the agent abandoned half of
    them (12-game probe with every option on, 20 coin flips)."""

    use = score_action(_action("use_intrigue_effect", ("section", 0)))
    finish = score_action(_action("finish_intrigue_effects"))
    assert use > finish > 0.0
    chosen = HeuristicAgent(seed=1).choose_action(
        _view(),
        (
            _action("finish_intrigue_effects"),
            _action("use_intrigue_effect", ("section", 0)),
        ),
    )
    assert chosen.action_id == "use_intrigue_effect"


def test_returning_a_specimen_ranks_below_every_decline() -> None:
    """Specimens are the agent's own tanks; returning one is the last
    resort [Immortality p. 8], not an equal of declining a purchase."""

    return_specimen = score_action(_action("return_specimen"))
    assert return_specimen < score_action(_action("decline_tech"))
    assert return_specimen < score_action(_action("decline_sardaukar_commander"))
    assert return_specimen > score_action(_action("pass_combat_intrigue"))
    for decline in ("decline_tech", "decline_sardaukar_commander"):
        chosen = HeuristicAgent(seed=1).choose_action(
            _view(), (_action("return_specimen"), _action(decline))
        )
        assert chosen.action_id == decline


def test_a_contract_outranks_the_persuasion_it_is_offered_against() -> None:
    """Delivery Logistics offers "1 Persuasion OR a contract"; a contract
    is a Victory Point path, so it ranks with ``take_contract``."""

    contract = score_action(_action("take_reveal_contract"))
    persuasion = score_action(_action("gain_reveal_persuasion"))
    assert contract == score_action(_action("take_contract")) > persuasion > 0.0
    assert score_action(
        _action("take_trigger_contract", ("instance_id", "contract:0"))
    ) == contract
    chosen = HeuristicAgent(seed=1).choose_action(
        _view(),
        (_action("gain_reveal_persuasion"), _action("take_reveal_contract")),
    )
    assert chosen.action_id == "take_reveal_contract"


def test_every_board_space_is_ranked() -> None:
    # Before 2026-09-10 only Swordmaster and High Council were ranked, so the
    # other 21 spaces tied at ``agent_turn``'s base and the agent picked among
    # them almost uniformly. New board content must come with a preference or
    # it silently rejoins that tie.
    from dune_imperium.agents.heuristic_agent import _SPACE_BONUSES
    from dune_imperium.content.uprising.board import BOARD_SPACES

    unranked = {space.space_id for space in BOARD_SPACES} - set(_SPACE_BONUSES)

    assert unranked == set()


def test_board_space_ranking_separates_the_placements_it_offers() -> None:
    from dune_imperium.content.uprising.board import BOARD_SPACES

    scores = {
        space.space_id: score_action(
            _action("agent_turn", ("space_id", space.space_id))
        )
        for space in BOARD_SPACES
    }

    # The permanent upgrades stay above every one-shot yield: a third Agent
    # for the rest of the game, then a Council seat's standing Persuasion.
    upgrades = {"swordmaster", "high_council"}
    one_shot = {k: v for k, v in scores.items() if k not in upgrades}
    assert scores["swordmaster"] > scores["high_council"] > max(one_shot.values())
    # Costed spaces rank below their uncosted counterparts in the same family:
    # Research Station buys two cards and two troops for two water, while
    # Arrakeen gives a card and a troop for nothing [Board Guide pp. 1-2].
    assert scores["arrakeen"] > scores["research_station"]
    # Nearly every placement must still separate from some other one.
    assert len(set(scores.values())) >= 12


def test_the_untuned_variant_reproduces_the_earlier_ranking() -> None:
    # The registry carries the pre-retune table so a paired A/B runs from the
    # committed tree; the 2026-09-09 retune needed a scratch module because
    # there was no variant slot.
    from dune_imperium.agents.heuristic_agent import SPACE_BONUSES_BEFORE_RETUNE
    from dune_imperium.agents.registry import BASELINE_AGENT_FACTORIES, make_agent

    assert "heuristic_untuned" in BASELINE_AGENT_FACTORIES
    untuned = make_agent("heuristic_untuned", seed=3)
    assert isinstance(untuned, HeuristicAgent)
    assert untuned.space_bonuses == SPACE_BONUSES_BEFORE_RETUNE

    sietch = _action("agent_turn", ("space_id", "sietch_tabr"))
    fremkit = _action("agent_turn", ("space_id", "fremkit"))
    old = SPACE_BONUSES_BEFORE_RETUNE
    assert score_action(sietch, space_bonuses=old) == score_action(
        fremkit, space_bonuses=old
    )
    assert score_action(sietch) != score_action(fremkit)


def _view_for(**options: bool) -> PlayerView:
    from dune_imperium import RulesetConfig
    from dune_imperium.core.observation import observe_state
    from dune_imperium.rules import UprisingRulesEngine

    config = RulesetConfig(**options)
    return observe_state(UprisingRulesEngine().reset(config, seed=2), 0)


def test_the_retuned_ranking_is_used_for_the_rulesets_it_was_measured_on() -> None:
    from dune_imperium.agents.heuristic_agent import _SPACE_BONUSES, space_bonuses_for

    assert space_bonuses_for(_view_for()) is _SPACE_BONUSES
    assert space_bonuses_for(_view_for(choam_module=True)) is _SPACE_BONUSES
    assert space_bonuses_for(_view_for(promo_cards=True)) is _SPACE_BONUSES


def test_an_expansion_table_keeps_the_ranking_it_was_measured_with() -> None:
    # The retuned table measured +5pp on base+CHOAM but -5.6pp with every
    # expansion on, and overlaying the spaces the expansions upgrade measured
    # -34pp because it pulled the agent out of Conflicts. Until an expansion
    # ranking is built and measured, those rulesets keep the old one.
    from dune_imperium.agents.heuristic_agent import (
        SPACE_BONUSES_BEFORE_RETUNE,
        space_bonuses_for,
    )

    for options in (
        {"bloodlines": True},
        {"bloodlines": True, "tech_module": True},
        {"immortality": True},
        {"bloodlines": True, "tech_module": True, "immortality": True},
    ):
        assert space_bonuses_for(_view_for(**options)) is SPACE_BONUSES_BEFORE_RETUNE


def test_the_ruleset_is_read_from_markers_that_outlive_their_supply() -> None:
    # Detection must not flip mid-game and hand a seat a different ranking
    # than it started with: the Tech stacks stay three entries once emptied and
    # the Research tokens never leave the track.
    from dataclasses import replace

    from dune_imperium.agents.heuristic_agent import (
        SPACE_BONUSES_BEFORE_RETUNE,
        space_bonuses_for,
    )

    spent = replace(
        _view_for(bloodlines=True, tech_module=True, immortality=True),
        tech_stack_sizes=(0, 0, 0),
        tleilaxu_deck_size=0,
        skill_stack_size=0,
        sardaukar_commander_space_ids=(),
    )

    assert space_bonuses_for(spent) is SPACE_BONUSES_BEFORE_RETUNE
