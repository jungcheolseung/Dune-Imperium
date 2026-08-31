"""Tests for the Intrigue effect DSL English text renderer."""

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    CompletedContractsAtLeast,
    EffectSection,
    GainCombatStrength,
    GainResources,
    InfluenceAtLeast,
    IntrigueTiming,
    LoseInfluence,
    OnRevealAcquisitionThisRound,
    OnUnitsDeployedInTurn,
    PayResources,
)
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS, INTRIGUE_CARDS_BY_ID
from dune_imperium.display.effect_dsl_text import (
    condition_text,
    cost_text,
    intrigue_card_text,
    option_text,
    reward_text,
    section_text,
    trigger_text,
)


def test_condition_text_renders_a_faction_influence_threshold() -> None:
    assert (
        condition_text(InfluenceAtLeast(Faction.EMPEROR, 3))
        == "you have 3 or more Emperor Influence"
    )


def test_condition_text_renders_completed_contracts() -> None:
    assert (
        condition_text(CompletedContractsAtLeast(2))
        == "you have completed 2 or more Contracts"
    )


def test_cost_text_renders_pay_resources() -> None:
    assert cost_text(PayResources(spice=2)) == "Pay 2 spice"


def test_cost_text_renders_lose_influence() -> None:
    assert cost_text(LoseInfluence(1)) == "Lose 1 Influence"


def test_reward_text_renders_gain_resources() -> None:
    assert reward_text(GainResources(solari=4)) == "Gain 4 solari"


def test_reward_text_renders_combat_strength_as_swords() -> None:
    assert reward_text(GainCombatStrength(1)) == "Gain 1 sword"
    assert reward_text(GainCombatStrength(4)) == "Gain 4 swords"


def test_trigger_text_renders_on_reveal_acquisition() -> None:
    assert (
        trigger_text(OnRevealAcquisitionThisRound())
        == "Whenever you acquire a card during your Reveal turn this round"
    )


def test_trigger_text_renders_on_units_deployed() -> None:
    assert (
        trigger_text(OnUnitsDeployedInTurn(3))
        == "When you deploy 3 or more units in a turn"
    )


def test_section_text_joins_cost_and_reward_with_an_arrow() -> None:
    section = EffectSection(
        costs=(LoseInfluence(1),),
        rewards=(GainResources(solari=4),),
    )

    assert section_text(section) == "Lose 1 Influence → Gain 4 solari"


def test_section_text_prefixes_a_condition() -> None:
    section = EffectSection(
        condition=CompletedContractsAtLeast(2),
        rewards=(GainCombatStrength(4),),
    )

    assert (
        section_text(section)
        == "If you have completed 2 or more Contracts: Gain 4 swords"
    )


def test_option_text_backed_by_choam_plot_option() -> None:
    entry = INTRIGUE_CARDS_BY_ID["backed_by_choam"]

    assert option_text(entry.options[0]) == "Plot — Lose 1 Influence → Gain 4 solari"
    assert entry.options[0].timing is IntrigueTiming.PLOT
    assert option_text(entry.options[1]) == (
        "Combat — If you have completed 2 or more Contracts: Gain 4 swords"
    )


def test_option_text_renders_a_reveal_acquisition_trigger() -> None:
    entry = INTRIGUE_CARDS_BY_ID["call_to_arms"]

    assert option_text(entry.options[0]) == (
        "Plot — Whenever you acquire a card during your Reveal turn this round: "
        "Recruit 1 troop"
    )


def test_option_text_renders_a_units_deployed_trigger() -> None:
    entry = INTRIGUE_CARDS_BY_ID["distraction"]

    assert option_text(entry.options[0]) == (
        "Plot — When you deploy 3 or more units in a turn: "
        "Place a Spy (sharing another player's Spy's post)"
    )


def test_option_text_joins_multiple_sections_with_a_semicolon() -> None:
    entry = INTRIGUE_CARDS_BY_ID["depart_for_arrakis"]

    assert option_text(entry.options[0]) == (
        "Plot — Pay 2 spice → Recruit 3 troops; "
        "If you have 3 or more Spacing Guild Influence: Draw 1 card"
    )


def test_intrigue_card_text_covers_every_card_with_non_empty_lines() -> None:
    for entry in INTRIGUE_CARDS:
        lines = intrigue_card_text(entry)

        assert lines, f"{entry.card.card_id} produced no option lines"
        for line in lines:
            assert isinstance(line, str)
            assert line.strip()


def test_intrigue_card_text_renders_every_option_of_every_card() -> None:
    for entry in INTRIGUE_CARDS:
        assert len(intrigue_card_text(entry)) == len(entry.options)
