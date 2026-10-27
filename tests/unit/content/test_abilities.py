"""Ability records (docs/composed-effects-plan.md 4.1).

Stage A1 resolves the Intrigue cards through the executor while their
transcription stays as it is, so every Intrigue and Navigation option must
convert to an ability and back without loss.
"""

import pytest

from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
    intrigue_ability,
    intrigue_option,
)
from dune_imperium.content.uprising.effect_dsl import (
    EffectSection,
    GainResources,
    GainVictoryPoints,
    HasAlliance,
    IntrigueOption,
    IntrigueTiming,
    OnConflictWon,
    OnRevealAcquisitionThisRound,
    PayResources,
)
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS

_VP = EffectSection(rewards=(GainVictoryPoints(1),))
_SPICE = EffectSection(rewards=(GainResources(spice=2),))


def test_every_intrigue_option_converts_both_ways() -> None:
    options = [option for entry in INTRIGUE_CARDS for option in entry.options]
    assert len(options) == 124
    for option in options:
        ability = intrigue_ability(option)
        assert intrigue_option(ability) == option
        assert ability.mark is AbilityMark.MANDATORY


def test_intrigue_timings_and_structures_carry_over() -> None:
    abilities = {
        (entry.card.card_id, index): intrigue_ability(option)
        for entry in INTRIGUE_CARDS
        for index, option in enumerate(entry.options)
    }
    timings = {ability.timing for ability in abilities.values()}
    assert timings == {AbilityTiming.PLOT, AbilityTiming.COMBAT, AbilityTiming.ENDGAME}
    separate = sorted(
        card_id
        for (card_id, _), ability in abilities.items()
        if ability.structure is AbilityStructure.SEPARATE
    )
    assert separate == [
        "change_allegiances",
        "depart_for_arrakis",
        "find_weakness",
        "questionable_methods",
        "strategic_stockpiling",
    ]
    assert any(ability.at_turn_start for ability in abilities.values())
    assert any(ability.trigger is not None for ability in abilities.values())


def test_an_ability_no_intrigue_option_holds_is_refused() -> None:
    for ability in (
        Ability(AbilityTiming.AGENT_BOX, (_VP,)),
        Ability(AbilityTiming.PLOT, (_VP,), mark=AbilityMark.OPTIONAL),
        Ability(AbilityTiming.PLOT, (_VP, _SPICE), structure=AbilityStructure.ONE_OF),
        Ability(AbilityTiming.PLOT, (_VP,), requirement=HasAlliance()),
        Ability(AbilityTiming.PLOT, (_VP,), hook="custom"),
    ):
        with pytest.raises(ValueError, match="no Intrigue option"):
            intrigue_option(ability)


def test_ability_validation() -> None:
    with pytest.raises(TypeError):
        Ability(IntrigueTiming.PLOT, (_VP,))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="printed line or a hook"):
        Ability(AbilityTiming.REVEAL, ())
    assert Ability(AbilityTiming.REVEAL, (), hook="desert_power").hook == "desert_power"
    with pytest.raises(ValueError, match="must be named"):
        Ability(AbilityTiming.REVEAL, (_VP,), hook="")
    with pytest.raises(ValueError, match="two or more lines"):
        Ability(AbilityTiming.AGENT_BOX, (_VP,), structure=AbilityStructure.ONE_OF)
    paid = EffectSection(
        rewards=(GainVictoryPoints(1),), costs=(PayResources(spice=4),)
    )
    with pytest.raises(ValueError, match="nothing to pay"):
        Ability(AbilityTiming.AGENT_BOX, (paid,), mark=AbilityMark.AUTOMATIC)
    with pytest.raises(ValueError, match="free and unconditional"):
        Ability(AbilityTiming.PLOT, (paid,), trigger=OnRevealAcquisitionThisRound())
    with pytest.raises(ValueError, match="start of a turn"):
        Ability(AbilityTiming.COMBAT, (_VP,), at_turn_start=True)


def test_a_winning_intrigue_is_played_with_the_cost_and_condition_it_needs() -> None:
    # "When you win a Conflict:" (the original game's Demand Respect) is played
    # from the hand once the win has happened, in the winner's window: unlike a
    # card waiting face up it may carry a cost and a condition [FAQ p. 2]
    # (OQ-121 decision 6), and it is a Combat card.
    paid = EffectSection(
        rewards=(GainVictoryPoints(1),),
        costs=(PayResources(spice=2),),
        condition=HasAlliance(),
    )
    option = IntrigueOption(
        timing=IntrigueTiming.COMBAT, sections=(paid,), trigger=OnConflictWon()
    )
    assert intrigue_option(intrigue_ability(option)) == option
    with pytest.raises(ValueError, match="combat timing"):
        IntrigueOption(
            timing=IntrigueTiming.PLOT, sections=(paid,), trigger=OnConflictWon()
        )
    with pytest.raises(ValueError, match="free and unconditional"):
        IntrigueOption(
            timing=IntrigueTiming.PLOT,
            sections=(paid,),
            trigger=OnRevealAcquisitionThisRound(),
        )
    assert Ability(AbilityTiming.COMBAT, (paid,), trigger=OnConflictWon()).sections
    with pytest.raises(ValueError, match="free and unconditional"):
        Ability(AbilityTiming.PLOT, (paid,), trigger=OnConflictWon())
