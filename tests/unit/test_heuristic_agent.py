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


def test_a_pinned_tech_table_reorders_the_tiles() -> None:
    # ``tech_bonuses`` is the Tech tile slot of the paired A/B, the way
    # ``space_bonuses`` is for the board space ranking: a table passed in
    # replaces the committed ranking for ``acquire_tech`` and nothing else.
    table = {"glowglobes": 3.0, "sardaukar_high_command": 0.0}
    glowglobes = _action("acquire_tech", ("tech_id", "glowglobes"))
    command = _action("acquire_tech", ("tech_id", "sardaukar_high_command"))
    assert score_action(glowglobes, tech_bonuses=table) > score_action(
        command, tech_bonuses=table
    )
    assert score_action(glowglobes) < score_action(command)
    offer = (_action("decline_tech"), command, glowglobes)
    pinned = HeuristicAgent(seed=1, tech_bonuses=table)
    assert dict(pinned.choose_action(_view(), offer).arguments)["tech_id"] == (
        "glowglobes"
    )
    assert HeuristicAgent(seed=1).choose_action(_view(), offer) == command


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
    from dune_imperium.agents.heuristic_agent import UPRISING_SPACE_BONUSES
    from dune_imperium.content.uprising.board import BOARD_SPACES

    unranked = {space.space_id for space in BOARD_SPACES} - set(UPRISING_SPACE_BONUSES)

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
    # Fremkit gives a card and Influence for nothing [Board Guide pp. 1-2].
    assert scores["fremkit"] > scores["research_station"]
    # The three spaces the rubric-priced table lived on went three ways
    # (docs/evaluation/baseline-2026-09-10.md sections 18 to 18(j)): Imperial
    # Basin sits at the floor below every other yield, Secrets at the median
    # with the 0.6 group, and Arrakeen with the Faction spaces' top, below
    # the permanent upgrades.
    assert scores["imperial_basin"] < min(
        v for k, v in one_shot.items() if k != "imperial_basin"
    )
    assert scores["secrets"] == scores["hagga_basin"]
    assert scores["deliver_supplies"] == scores["gather_support"]
    assert scores["hagga_basin"] < scores["fremkit"] < scores["heighliner"]
    assert scores["espionage"] == scores["hagga_basin"]
    assert scores["hagga_basin"] > scores["assembly_hall"] > scores["accept_contract"]
    assert scores["arrakeen"] > scores["sardaukar"]
    assert scores["arrakeen"] > scores["heighliner"]
    assert scores["arrakeen"] < scores["high_council"]
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


def test_one_ranking_serves_every_ruleset() -> None:
    # The Tech Module kept the two-entry table while the rubric-priced table
    # lost there (sections 15 and 16); the demoted table wins on every
    # ruleset (section 18), so the agent no longer reads the ruleset off the
    # observation to pick a table.
    from dune_imperium.agents.heuristic_agent import UPRISING_SPACE_BONUSES

    agent = HeuristicAgent(seed=1)
    for options in (
        {},
        {"choam_module": True},
        {"bloodlines": True, "tech_module": True},
        {"bloodlines": True, "tech_module": True, "immortality": True},
    ):
        view = _view_for(**options)
        secrets = _placement("card", "secrets")
        basin = _placement("card", "imperial_basin")
        assert agent.choose_action(view, (secrets, basin)) == secrets
    assert score_action(_placement("card", "secrets")) == score_action(
        _placement("card", "secrets"), space_bonuses=UPRISING_SPACE_BONUSES
    )


def test_the_uprising_table_variant_pins_the_rubric_priced_ranking() -> None:
    # The registry keeps the 2026-09-10 table so the demotion A/B reruns from
    # the committed tree.
    from dune_imperium.agents.heuristic_agent import (
        SPACE_BONUSES_BEFORE_DEMOTION,
        UPRISING_SPACE_BONUSES,
    )
    from dune_imperium.agents.registry import BASELINE_AGENT_FACTORIES, make_agent

    assert "heuristic_uprising_table" in BASELINE_AGENT_FACTORIES
    priced = make_agent("heuristic_uprising_table", seed=3)
    assert isinstance(priced, HeuristicAgent)
    assert priced.space_bonuses == SPACE_BONUSES_BEFORE_DEMOTION
    assert SPACE_BONUSES_BEFORE_DEMOTION["imperial_basin"] == 0.85
    assert SPACE_BONUSES_BEFORE_DEMOTION["secrets"] == 1.0
    assert SPACE_BONUSES_BEFORE_DEMOTION["arrakeen"] == 0.75
    assert {
        k for k, v in SPACE_BONUSES_BEFORE_DEMOTION.items()
        if UPRISING_SPACE_BONUSES[k] != v
    } == {"imperial_basin", "secrets", "arrakeen", "deliver_supplies", "espionage"}


def test_the_floor_table_variant_pins_the_first_demotion() -> None:
    # The registry keeps the 2026-09-11 floor so the level comparison of
    # section 18(h) reruns from the committed tree.
    from dune_imperium.agents.heuristic_agent import (
        SPACE_BONUSES_DEMOTED_TO_FLOOR,
        UPRISING_SPACE_BONUSES,
    )
    from dune_imperium.agents.registry import BASELINE_AGENT_FACTORIES, make_agent

    assert "heuristic_floor_table" in BASELINE_AGENT_FACTORIES
    floor = make_agent("heuristic_floor_table", seed=3)
    assert isinstance(floor, HeuristicAgent)
    assert floor.space_bonuses == SPACE_BONUSES_DEMOTED_TO_FLOOR
    demoted = ("imperial_basin", "secrets", "arrakeen")
    assert {k: SPACE_BONUSES_DEMOTED_TO_FLOOR[k] for k in demoted} == dict.fromkeys(
        demoted, 0.3
    )
    assert {k: UPRISING_SPACE_BONUSES[k] for k in demoted} == {
        "imperial_basin": 0.3,
        "secrets": 0.6,
        "arrakeen": 1.2,
    }
    assert {
        k for k, v in SPACE_BONUSES_DEMOTED_TO_FLOOR.items()
        if UPRISING_SPACE_BONUSES[k] != v
    } == {"secrets", "arrakeen", "deliver_supplies", "espionage"}


def test_the_median_table_variant_pins_the_morning_demotion() -> None:
    # The registry keeps the 2026-09-16 morning table (all three at 0.6) so
    # the ablation and its follow-up (sections 18(i) and 18(j)) rerun from
    # the committed tree.
    from dune_imperium.agents.heuristic_agent import (
        SPACE_BONUSES_MEDIAN_DEMOTION,
        UPRISING_SPACE_BONUSES,
    )
    from dune_imperium.agents.registry import BASELINE_AGENT_FACTORIES, make_agent

    assert "heuristic_median_table" in BASELINE_AGENT_FACTORIES
    median = make_agent("heuristic_median_table", seed=3)
    assert isinstance(median, HeuristicAgent)
    assert median.space_bonuses == SPACE_BONUSES_MEDIAN_DEMOTION
    demoted = ("imperial_basin", "secrets", "arrakeen")
    assert {k: SPACE_BONUSES_MEDIAN_DEMOTION[k] for k in demoted} == dict.fromkeys(
        demoted, 0.6
    )
    assert {
        k for k, v in SPACE_BONUSES_MEDIAN_DEMOTION.items()
        if UPRISING_SPACE_BONUSES[k] != v
    } == {"imperial_basin", "arrakeen", "deliver_supplies", "espionage"}


def test_the_split_table_variant_pins_the_noon_table() -> None:
    # The registry keeps the split table (Deliver Supplies still 0.7) so the
    # ablation that sent Deliver Supplies down (section 18(l)) reruns from
    # the committed tree; every pin names Deliver Supplies explicitly.
    from dune_imperium.agents.heuristic_agent import (
        SPACE_BONUSES_BEFORE_DEMOTION,
        SPACE_BONUSES_DEMOTED_TO_FLOOR,
        SPACE_BONUSES_MEDIAN_DEMOTION,
        SPACE_BONUSES_SPLIT_DEMOTION,
        UPRISING_SPACE_BONUSES,
    )
    from dune_imperium.agents.registry import BASELINE_AGENT_FACTORIES, make_agent

    assert "heuristic_split_table" in BASELINE_AGENT_FACTORIES
    split = make_agent("heuristic_split_table", seed=3)
    assert isinstance(split, HeuristicAgent)
    assert split.space_bonuses == SPACE_BONUSES_SPLIT_DEMOTION
    assert UPRISING_SPACE_BONUSES["deliver_supplies"] == 0.4
    for pinned in (
        SPACE_BONUSES_BEFORE_DEMOTION,
        SPACE_BONUSES_DEMOTED_TO_FLOOR,
        SPACE_BONUSES_MEDIAN_DEMOTION,
        SPACE_BONUSES_SPLIT_DEMOTION,
    ):
        assert pinned["deliver_supplies"] == 0.7
        assert pinned["espionage"] == 0.8
    assert {
        k for k, v in SPACE_BONUSES_SPLIT_DEMOTION.items()
        if UPRISING_SPACE_BONUSES[k] != v
    } == {"deliver_supplies", "espionage"}


def test_the_supplies_table_variant_pins_the_afternoon_table() -> None:
    # The registry keeps the Deliver Supplies table (Espionage still 0.8) so
    # the ablation that sent Espionage down (section 18(m)) reruns from the
    # committed tree.
    from dune_imperium.agents.heuristic_agent import (
        SPACE_BONUSES_BEFORE_ESPIONAGE,
        UPRISING_SPACE_BONUSES,
    )
    from dune_imperium.agents.registry import BASELINE_AGENT_FACTORIES, make_agent

    assert "heuristic_supplies_table" in BASELINE_AGENT_FACTORIES
    supplies = make_agent("heuristic_supplies_table", seed=3)
    assert isinstance(supplies, HeuristicAgent)
    assert supplies.space_bonuses == SPACE_BONUSES_BEFORE_ESPIONAGE
    assert SPACE_BONUSES_BEFORE_ESPIONAGE["espionage"] == 0.8
    assert UPRISING_SPACE_BONUSES["espionage"] == 0.6
    assert {
        k for k, v in SPACE_BONUSES_BEFORE_ESPIONAGE.items()
        if UPRISING_SPACE_BONUSES[k] != v
    } == {"espionage"}


def _placement(card_id: str, space_id: str) -> DomainAction:
    return _action("agent_turn", ("card_id", card_id), ("space_id", space_id))


def test_a_placement_spends_the_card_whose_reveal_box_costs_least() -> None:
    # "Agent turn에는 낸 card의 Agent box만 처리하고 그 card의 Reveal box는
    # 무시한다" [Main p. 8] [Main p. 9] and "앞선 Agent turn에 낸 card의 Reveal
    # box 효과는 얻지 않는다" [Main p. 12] (docs/rules/player-turns.md 60, 161),
    # so every card that reaches one space costs what its Reveal box would have
    # paid this round. Seek Allies prints nothing, Diplomacy one Persuasion,
    # Long Live the Fighters two Persuasion and three swords.
    from dune_imperium.agents.heuristic_agent import (
        SPENT_CARD_VALUE,
        cheapest_card_for_the_same_space,
    )

    free = _placement("player:0:starter:seek_allies:0", "espionage")
    one = _placement("player:0:starter:diplomacy:0", "espionage")
    dear = _placement("imperium:long_live_the_fighters:0", "espionage")
    tied = (dear, one, free)

    for drawn in tied:
        assert cheapest_card_for_the_same_space(drawn, tied, SPENT_CARD_VALUE) is free


def test_the_tie_break_never_moves_the_agent_to_another_board_space() -> None:
    # This is the invariant the measurement bought. Scoring the card cost --
    # even scaled to fit inside the board table's smallest gap -- let the
    # cheapest card pick the space and cost -8.6pp with every expansion on,
    # where 21 spaces share one rank (docs/evaluation/baseline-2026-09-10.md
    # section 14). The tie-break only ever compares placements that already
    # name the same space.
    from dune_imperium.agents.heuristic_agent import (
        SPENT_CARD_VALUE,
        cheapest_card_for_the_same_space,
    )

    # A free card reaches Assembly Hall; only a dear one reaches Espionage.
    cheap_elsewhere = _placement("player:0:starter:dagger:0", "assembly_hall")
    dear_here = _placement("imperium:long_live_the_fighters:0", "espionage")
    tied = (dear_here, cheap_elsewhere)

    assert (
        cheapest_card_for_the_same_space(dear_here, tied, SPENT_CARD_VALUE) is dear_here
    )
    assert (
        cheapest_card_for_the_same_space(cheap_elsewhere, tied, SPENT_CARD_VALUE)
        is cheap_elsewhere
    )


def test_the_tie_break_leaves_every_other_action_alone() -> None:
    from dune_imperium.agents.heuristic_agent import (
        SPENT_CARD_VALUE,
        cheapest_card_for_the_same_space,
    )

    reveal = _action("reveal_turn")
    placement = _placement("imperium:long_live_the_fighters:0", "espionage")
    tied = (reveal, placement)

    assert cheapest_card_for_the_same_space(reveal, tied, SPENT_CARD_VALUE) is reveal
    # A lone placement has nothing to be re-spent on.
    assert (
        cheapest_card_for_the_same_space(placement, tied, SPENT_CARD_VALUE) is placement
    )


def test_an_unpriced_card_keeps_the_drawn_placement() -> None:
    # New or untranscribed content degrades to the earlier behaviour instead of
    # failing, the way an unknown action ID scores 0. An unknown card prices at
    # 0.0, which is the cheapest there is, so it must not displace a card the
    # manifests do price.
    from dune_imperium.agents.heuristic_agent import (
        SPENT_CARD_VALUE,
        cheapest_card_for_the_same_space,
        reveal_value_forfeited,
    )

    unknown = _placement("nonsense:not_a_card:0", "espionage")
    assert reveal_value_forfeited(unknown, SPENT_CARD_VALUE) == 0.0
    assert reveal_value_forfeited(_action("agent_turn"), SPENT_CARD_VALUE) == 0.0

    free = _placement("player:0:starter:seek_allies:0", "espionage")
    tied = (unknown, free)
    assert cheapest_card_for_the_same_space(unknown, tied, SPENT_CARD_VALUE) is unknown


def test_every_sendable_card_is_priced_from_its_printed_reveal_box() -> None:
    # The price is derived per card instead of tabulated, so new content is
    # priced the moment it is transcribed. This pins that every card the engine
    # can send to a space resolves, and that the printed integers are what the
    # two weights multiply.
    from dune_imperium.agents.heuristic_agent import (
        SPENT_CARD_VALUE,
        reveal_value_forfeited,
    )
    from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS
    from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS
    from dune_imperium.content.uprising.starting_cards import (
        EXPERIMENTATION,
        STARTING_DECK,
    )

    sendable: list[tuple[str, int, int]] = [
        (
            f"player:0:starter:{entry.card.card_id}:0",
            entry.reveal_persuasion,
            entry.reveal_strength,
        )
        for entry in (*STARTING_DECK, EXPERIMENTATION)
        if entry.agent_icons
    ]
    sendable += [
        (
            f"imperium:{entry.card.card_id}:0",
            entry.reveal_persuasion,
            entry.reveal_strength,
        )
        for entry in IMPERIUM_CARDS
        if entry.agent_icons and entry.play_data_complete
    ]
    sendable += [
        (
            f"tleilaxu:{entry.card.card_id}:0",
            entry.reveal_persuasion,
            entry.reveal_strength,
        )
        for entry in TLEILAXU_CARDS
        if entry.agent_icons and entry.play_data_complete
    ]
    assert len(sendable) > 100

    for instance_id, persuasion, strength in sendable:
        expected = (
            SPENT_CARD_VALUE.persuasion * persuasion
            + SPENT_CARD_VALUE.sword * strength
        )
        action = _placement(instance_id, "espionage")
        assert reveal_value_forfeited(action, SPENT_CARD_VALUE) == pytest.approx(
            expected
        )


def test_the_flat_card_variant_reproduces_the_earlier_behaviour() -> None:
    # The registry carries the pre-2026-09-10 spent-card behaviour so the
    # paired A/B for this tie-break runs from the committed tree, the way
    # ``heuristic_untuned`` does for the board space table.
    from dune_imperium.agents.heuristic_agent import (
        cheapest_card_for_the_same_space,
    )
    from dune_imperium.agents.registry import BASELINE_AGENT_FACTORIES, make_agent

    assert "heuristic_flat_cards" in BASELINE_AGENT_FACTORIES
    flat = make_agent("heuristic_flat_cards", seed=3)
    assert isinstance(flat, HeuristicAgent)
    assert flat.spent_card_value is None

    free = _placement("player:0:starter:seek_allies:0", "espionage")
    dear = _placement("imperium:long_live_the_fighters:0", "espionage")
    assert cheapest_card_for_the_same_space(dear, (dear, free), None) is dear


def test_the_swap_changes_the_card_and_nothing_else() -> None:
    # A card is offered once per cost option and once more per Navigation
    # Chamber discount, and every variant forfeits the same Reveal box. Taking
    # the first cheapest would quietly move the cost option the draw made and
    # drop a discount that costs nothing to keep.
    from dune_imperium.agents.heuristic_agent import (
        SPENT_CARD_VALUE,
        cheapest_card_for_the_same_space,
    )

    def variant(card_id: str, cost_option: str, discount: str | None) -> DomainAction:
        arguments: list[tuple[str, ActionValue]] = [("card_id", card_id)]
        arguments.append(("cost_option", cost_option))
        if discount is not None:
            arguments.append(("discount", discount))
        arguments.append(("space_id", "spice_refinery"))
        return _action("agent_turn", *arguments)

    dear = "imperium:long_live_the_fighters:0"
    free = "player:0:starter:seek_allies:0"
    # The cheap card is offered in both cost options, undiscounted first.
    tied = (
        variant(dear, "paid", "spice"),
        variant(free, "free", None),
        variant(free, "paid", None),
        variant(free, "paid", "spice"),
    )

    swapped = cheapest_card_for_the_same_space(tied[0], tied, SPENT_CARD_VALUE)

    assert dict(swapped.arguments)["card_id"] == free
    assert dict(swapped.arguments)["cost_option"] == "paid"
    assert dict(swapped.arguments)["discount"] == "spice"

    # With no matching variant the first cheapest is still taken.
    without_match = (variant(dear, "paid", "spice"), variant(free, "free", None))
    fallback = cheapest_card_for_the_same_space(
        without_match[0], without_match, SPENT_CARD_VALUE
    )
    assert fallback is without_match[1]


def test_the_swap_keeps_a_graft_and_an_infiltrate_as_drawn() -> None:
    # ``graft`` and ``infiltrate_post_id`` are placement terms too: a Graft
    # plays a second card [Immortality p. 10] and an Infiltrate recalls a Spy
    # [Main p. 11], so a swap must not add or drop either.
    from dune_imperium.agents.heuristic_agent import (
        SPENT_CARD_VALUE,
        cheapest_card_for_the_same_space,
    )

    dear = "imperium:long_live_the_fighters:0"
    free = "player:0:starter:seek_allies:0"
    plain_dear = _placement(dear, "espionage")
    plain_free = _placement(free, "espionage")
    infiltrating_free = _action(
        "agent_turn",
        ("card_id", free),
        ("infiltrate_post_id", "post_a"),
        ("space_id", "espionage"),
    )
    infiltrating_dear = _action(
        "agent_turn",
        ("card_id", dear),
        ("infiltrate_post_id", "post_a"),
        ("space_id", "espionage"),
    )
    tied = (plain_dear, infiltrating_dear, plain_free, infiltrating_free)

    # A plain draw stays plain; an Infiltrate draw keeps its post.
    assert cheapest_card_for_the_same_space(plain_dear, tied, SPENT_CARD_VALUE) is (
        plain_free
    )
    assert cheapest_card_for_the_same_space(
        infiltrating_dear, tied, SPENT_CARD_VALUE
    ) is infiltrating_free


def _seated_view(**influence: int) -> PlayerView:
    """A real reset view for seat 0 with seat 0's Influence set."""

    from dataclasses import replace

    from dune_imperium.core.player import Influence

    view = _view_for()
    me = replace(view.players[0], influence=Influence(**influence))
    return replace(view, players=(me, *view.players[1:]))


def _faction_choices(*factions: str) -> tuple[DomainAction, ...]:
    return tuple(_action("choose_intrigue_faction", ("faction", f)) for f in factions)


def test_faction_tie_break_reaches_two_before_anything_else() -> None:
    # "Influence 2에 도달하면 1 VP를 얻는다" [Main pp. 7, 17]: from 1 the next
    # step scores, from 0 or 3 (with nobody at 4 yet) it does not yet.
    view = _seated_view(emperor=1, spacing_guild=0, bene_gesserit=0, fremen=0)
    agent = HeuristicAgent(seed=3)
    choices = _faction_choices("emperor", "spacing_guild", "bene_gesserit", "fremen")
    for _ in range(5):
        assert agent.choose_action(view, choices) == choices[0]


def test_faction_tie_break_takes_the_first_alliance_and_climbs_over_a_holder() -> None:
    # "처음 Influence 4에 도달한 플레이어는 Alliance token과 ... 1 VP" and the
    # token moves only to a player who rises strictly higher [Main p. 7].
    from dataclasses import replace

    from dune_imperium.core.player import Influence

    view = _seated_view(emperor=1, spacing_guild=3, bene_gesserit=0, fremen=0)
    agent = HeuristicAgent(seed=3)
    choices = _faction_choices("emperor", "spacing_guild")
    # Reaching 4 first outranks reaching 2 by the higher track.
    assert agent.choose_action(view, choices) == choices[1]
    # An opponent holding the token at 4 makes 4 a tie: the step to 2 wins.
    holder = replace(
        view.players[1],
        influence=Influence(spacing_guild=4),
        alliance_faction_ids=("spacing_guild",),
    )
    contested = replace(view, players=(view.players[0], holder, *view.players[2:]))
    assert agent.choose_action(contested, choices) == choices[0]
    # From 4 against a holder at 4, the step to 5 takes the token.
    climbing = replace(
        contested,
        players=(
            replace(
                contested.players[0],
                influence=Influence(emperor=1, spacing_guild=4),
            ),
            *contested.players[1:],
        ),
    )
    assert agent.choose_action(climbing, choices) == choices[1]


def test_faction_tie_break_loses_from_the_track_that_costs_least() -> None:
    # Change Allegiances pays "lose 1 Influence" first ("임의의 Faction Influence를
    # ... 1 잃는 효과는 네 Faction 가운데 하나를 고른다" [Main p. 20]): stepping
    # down from 2 loses the Victory Point, so the other track pays.
    from dataclasses import replace

    view = replace(
        _seated_view(emperor=2, spacing_guild=1, bene_gesserit=0, fremen=0),
        intrigue_resolving=("intrigue:change_allegiances:0",),
    )
    agent = HeuristicAgent(seed=3)
    loss = _faction_choices("emperor", "spacing_guild")
    assert agent.choose_action(view, loss) == loss[1]
    # The card's second step is the gain: the empty tracks are offered now,
    # and the step that reaches 2 (Guild, still at 1) wins.
    gain = _faction_choices("emperor", "spacing_guild", "bene_gesserit", "fremen")
    assert agent.choose_action(view, gain) == gain[1]


def test_faction_tie_break_reads_a_gain_step_that_offers_a_full_track() -> None:
    # A gain is unrestricted and offers a track at 6 too (the engine lets
    # that gain fizzle), so a full track among four offered is not a loss:
    # the step that reaches 4 first (Bene Gesserit at 3) wins, not the
    # cheapest track to lose (review of 2026-09-16).
    from dataclasses import replace

    from dune_imperium.agents.heuristic_agent import _intrigue_faction_choice_is_loss

    view = replace(
        _seated_view(emperor=6, spacing_guild=2, bene_gesserit=3, fremen=0),
        intrigue_resolving=("intrigue:change_allegiances:0",),
    )
    gain = _faction_choices("emperor", "spacing_guild", "bene_gesserit", "fremen")
    every = frozenset(("emperor", "spacing_guild", "bene_gesserit", "fremen"))
    assert _intrigue_faction_choice_is_loss(view, every) is False
    assert HeuristicAgent(seed=3).choose_action(view, gain) == gain[2]
    # The same card's loss step offers only the occupied tracks.
    loss = _faction_choices("emperor", "spacing_guild", "bene_gesserit")
    occupied = frozenset(("emperor", "spacing_guild", "bene_gesserit"))
    assert _intrigue_faction_choice_is_loss(view, occupied) is True
    assert HeuristicAgent(seed=3).choose_action(view, loss) == loss[2]
    # Every track occupied and all four offered: the steps look alike, so
    # the tie is left to the draw.
    crowded = replace(
        _seated_view(emperor=6, spacing_guild=2, bene_gesserit=3, fremen=1),
        intrigue_resolving=("intrigue:change_allegiances:0",),
    )
    assert _intrigue_faction_choice_is_loss(crowded, every) is None
    drawn = {HeuristicAgent(seed=s).choose_action(crowded, gain) for s in range(30)}
    assert len(drawn) > 1


def test_trash_tie_break_removes_the_cheapest_card() -> None:
    from dune_imperium.agents.heuristic_agent import card_printed_value

    cheap, dear = _imperium_instance_ids_by_cost()
    dagger = "player:0:starter:dagger:0"
    assert card_printed_value(dagger) < card_printed_value(cheap)
    assert card_printed_value(cheap) < card_printed_value(dear)
    agent = HeuristicAgent(seed=3)
    for family in ("trash_agent_card", "discard_agent_card", "trash_optional_card"):
        choices = tuple(_action(family, ("card_id", c)) for c in (dear, cheap, dagger))
        assert agent.choose_action(_view(), choices) == choices[2]


def test_buy_tie_break_prefers_the_richer_reveal_box_at_the_same_cost() -> None:
    from dune_imperium.agents.heuristic_agent import acquisition_reveal_value

    soldier = "imperium:sardaukar_soldier:0"  # cost 1, Persuasion 1, sword 1
    harvester = "imperium:smuggler_s_harvester:0"  # cost 1, Persuasion 1
    richer = acquisition_reveal_value(
        _action("acquire_imperium", ("instance_id", soldier))
    )
    poorer = acquisition_reveal_value(
        _action("acquire_imperium", ("instance_id", harvester))
    )
    assert richer > poorer
    choices = (
        _action("acquire_imperium", ("instance_id", harvester)),
        _action("acquire_imperium", ("instance_id", soldier)),
    )
    assert score_action(choices[0]) == score_action(choices[1])
    assert HeuristicAgent(seed=3).choose_action(_view(), choices) == choices[1]


def test_tie_breaks_stay_inside_the_tied_family() -> None:
    from dune_imperium.agents.heuristic_agent import TIE_BREAKS, narrow_family_tie

    view = _seated_view(emperor=1, spacing_guild=0, bene_gesserit=0, fremen=0)
    mixed = (
        _action("choose_intrigue_faction", ("faction", "spacing_guild")),
        _action("resolve_board_effect", ("effect", "spice")),
    )
    assert narrow_family_tie(mixed, view, TIE_BREAKS) == mixed
    same = _faction_choices("spacing_guild", "emperor")
    narrowed = narrow_family_tie(same, view, TIE_BREAKS)
    assert narrowed == (same[1],)
    assert all(action in same for action in narrowed)


def test_the_uniform_ties_variant_pins_the_earlier_draw() -> None:
    from dune_imperium.agents.heuristic_agent import UNIFORM_TIES
    from dune_imperium.agents.registry import BASELINE_AGENT_FACTORIES, make_agent

    assert "heuristic_uniform_ties" in BASELINE_AGENT_FACTORIES
    uniform = make_agent("heuristic_uniform_ties", seed=3)
    assert isinstance(uniform, HeuristicAgent)
    assert uniform.tie_breaks == UNIFORM_TIES
    assert not (UNIFORM_TIES.faction or UNIFORM_TIES.trash or UNIFORM_TIES.buy)
    view = _seated_view(emperor=1, spacing_guild=0, bene_gesserit=0, fremen=0)
    choices = _faction_choices("emperor", "spacing_guild", "bene_gesserit", "fremen")
    drawn = {uniform.choose_action(view, choices) for _ in range(40)}
    assert len(drawn) > 1
