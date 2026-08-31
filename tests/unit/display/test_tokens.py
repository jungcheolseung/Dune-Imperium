"""Coverage and golden-text tests for personal-card enum token maps."""

import dataclasses

from dune_imperium.content.uprising.types import (
    PersonalCardAcquisitionEffect,
    PersonalCardAgentEffect,
    PersonalCardBond,
    PersonalCardDiscardEffect,
    PersonalCardRevealAcquisitionEffect,
    PersonalCardRevealChoiceEffect,
    PersonalCardRevealEffect,
    PersonalCardTrashEffect,
)
from dune_imperium.display.tokens import (
    _HANDLED_REVEAL_FIELDS,
    ACQUISITION_EFFECT_TEXT,
    AGENT_EFFECT_TEXT,
    DISCARD_EFFECT_TEXT,
    REVEAL_ACQUISITION_EFFECT_TEXT,
    REVEAL_CHOICE_EFFECT_TEXT,
    TRASH_EFFECT_TEXT,
    reveal_effect_text,
)


def test_agent_effect_text_covers_every_member() -> None:
    assert set(AGENT_EFFECT_TEXT.keys()) == set(PersonalCardAgentEffect)


def test_trash_effect_text_covers_every_member() -> None:
    assert set(TRASH_EFFECT_TEXT.keys()) == set(PersonalCardTrashEffect)


def test_discard_effect_text_covers_every_member() -> None:
    assert set(DISCARD_EFFECT_TEXT.keys()) == set(PersonalCardDiscardEffect)


def test_acquisition_effect_text_covers_every_member() -> None:
    assert set(ACQUISITION_EFFECT_TEXT.keys()) == set(PersonalCardAcquisitionEffect)


def test_reveal_acquisition_effect_text_covers_every_member() -> None:
    assert set(REVEAL_ACQUISITION_EFFECT_TEXT.keys()) == set(
        PersonalCardRevealAcquisitionEffect
    )


def test_reveal_choice_effect_text_covers_every_member() -> None:
    assert set(REVEAL_CHOICE_EFFECT_TEXT.keys()) == set(PersonalCardRevealChoiceEffect)


def test_every_agent_effect_text_is_non_empty_or_documented_sentinel() -> None:
    # No PersonalCardAgentEffect member is currently a "no effect" sentinel;
    # every entry must therefore carry real text. If a future member is
    # added as a sentinel, give it "" here and update this test alongside
    # the module docstring's sentinel note.
    assert all(text for text in AGENT_EFFECT_TEXT.values())


def test_handled_reveal_fields_matches_dataclass_fields() -> None:
    assert _HANDLED_REVEAL_FIELDS == {
        field.name for field in dataclasses.fields(PersonalCardRevealEffect)
    }


def test_reveal_effect_text_bene_gesserit_operative_golden() -> None:
    effect = PersonalCardRevealEffect(persuasion=2, minimum_spies_placed=2)

    assert (
        reveal_effect_text(effect)
        == "If you have placed 2 or more Spies: +2 Persuasion"
    )


def test_reveal_effect_text_flat_persuasion_and_strength() -> None:
    effect = PersonalCardRevealEffect(persuasion=1, strength=1)

    assert reveal_effect_text(effect) == "+1 Persuasion, +1 sword"


def test_reveal_effect_text_faction_bond_condition() -> None:
    # Northern Watermaster: PersonalCardRevealEffect(spice=2,
    # required_faction_bond=PersonalCardBond.FREMEN).
    effect = PersonalCardRevealEffect(
        spice=2,
        required_faction_bond=PersonalCardBond.FREMEN,
    )

    assert reveal_effect_text(effect) == "If Fremen Bond: Gain 2 spice"


def test_reveal_effect_text_high_council_and_swordmaster() -> None:
    # Paracompass's second Reveal effect.
    effect = PersonalCardRevealEffect(
        persuasion=1,
        requires_high_council=True,
        requires_swordmaster=True,
    )

    assert (
        reveal_effect_text(effect)
        == "If High Council and Swordmaster: +1 Persuasion"
    )


def test_reveal_effect_text_per_revealed_faction_scales_the_gain() -> None:
    # Stilgar, The Devoted: PersonalCardRevealEffect(persuasion=2,
    # per_revealed_faction=PersonalCardBond.FREMEN).
    effect = PersonalCardRevealEffect(
        persuasion=2,
        per_revealed_faction=PersonalCardBond.FREMEN,
    )

    assert (
        reveal_effect_text(effect)
        == "+2 Persuasion per revealed Fremen card"
    )


def test_reveal_effect_text_influence_gain_names_its_faction() -> None:
    # Shishakli: PersonalCardRevealEffect(influence=1,
    # influence_faction=PersonalCardBond.FREMEN,
    # required_faction_bond=PersonalCardBond.FREMEN).
    effect = PersonalCardRevealEffect(
        influence=1,
        influence_faction=PersonalCardBond.FREMEN,
        required_faction_bond=PersonalCardBond.FREMEN,
    )

    assert reveal_effect_text(effect) == "If Fremen Bond: Gain 1 Fremen Influence"


def test_reveal_effect_text_persuasion_per_completed_contract() -> None:
    # Interstellar Trade: PersonalCardRevealEffect(
    # persuasion_per_completed_contract=1).
    effect = PersonalCardRevealEffect(persuasion_per_completed_contract=1)

    assert reveal_effect_text(effect) == "+1 Persuasion per completed Contract"
