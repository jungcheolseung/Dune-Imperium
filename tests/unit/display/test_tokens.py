"""Coverage and golden-text tests for personal-card enum token maps."""

import dataclasses
import sys
from pathlib import Path

from dune_imperium.content.immortality.tleilaxu import (
    RECLAIMED_FORCES,
    TLEILAXU_CARDS_BY_ID,
)
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS
from dune_imperium.content.uprising.personal_cards import PersonalCardDefinition
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.starting_cards import STARTING_DECK
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
from dune_imperium.display.tokens_ko import (
    ACQUISITION_EFFECT_TEXT_KO,
    AGENT_EFFECT_TEXT_KO,
    DISCARD_EFFECT_TEXT_KO,
    REVEAL_ACQUISITION_EFFECT_TEXT_KO,
    REVEAL_CHOICE_EFFECT_TEXT_KO,
    TRASH_EFFECT_TEXT_KO,
    reveal_effect_text_ko,
)

# tests/support isn't a package pytest or mypy resolve from a dotted import
# (see tests/unit/display/test_struct_text.py's identical comment).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "support"))
from ko_text import (  # type: ignore[import-not-found]  # noqa: E402
    assert_no_stray_latin,
    assert_no_summon_for_sandworm,
    assert_placeholders_are_terms,
    assert_trash_and_discard_match,
    terms_keys,
)

_ALL_REVEAL_EFFECT_ENTRIES: tuple[PersonalCardDefinition, ...] = (
    *IMPERIUM_CARDS,
    *STARTING_DECK,
    *RESERVE_STACKS,
    *TLEILAXU_CARDS_BY_ID.values(),
    RECLAIMED_FORCES,
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


# ---------- Korean (``*_KO``) ----------


def test_agent_effect_text_ko_covers_every_member() -> None:
    assert set(AGENT_EFFECT_TEXT_KO.keys()) == set(PersonalCardAgentEffect)


def test_trash_effect_text_ko_covers_every_member() -> None:
    assert set(TRASH_EFFECT_TEXT_KO.keys()) == set(PersonalCardTrashEffect)


def test_discard_effect_text_ko_covers_every_member() -> None:
    assert set(DISCARD_EFFECT_TEXT_KO.keys()) == set(PersonalCardDiscardEffect)


def test_acquisition_effect_text_ko_covers_every_member() -> None:
    assert set(ACQUISITION_EFFECT_TEXT_KO.keys()) == set(
        PersonalCardAcquisitionEffect
    )


def test_reveal_acquisition_effect_text_ko_covers_every_member() -> None:
    assert set(REVEAL_ACQUISITION_EFFECT_TEXT_KO.keys()) == set(
        PersonalCardRevealAcquisitionEffect
    )


def test_reveal_choice_effect_text_ko_covers_every_member() -> None:
    assert set(REVEAL_CHOICE_EFFECT_TEXT_KO.keys()) == set(
        PersonalCardRevealChoiceEffect
    )


def test_every_agent_effect_text_ko_is_non_empty() -> None:
    assert all(text for text in AGENT_EFFECT_TEXT_KO.values())


def test_ko_handled_reveal_fields_matches_dataclass_fields() -> None:
    # tokens_ko.py's own module-private copy of the field set (imported
    # here through the same name tokens.py exports) must stay in lockstep
    # with the dataclass, exactly like the English test above — a field
    # tokens.py's renderer grows and this module's private copy misses
    # would otherwise silently under-translate instead of failing a test.
    from dune_imperium.display.tokens_ko import _HANDLED_REVEAL_FIELDS as ko_fields

    assert ko_fields == {
        field.name for field in dataclasses.fields(PersonalCardRevealEffect)
    }


def _all_ko_texts() -> list[tuple[str, str, str]]:
    """(table name, English text, Korean text) for every table entry.

    Built as separate concretely-typed comprehensions, one per table,
    rather than a single loop over a list of (english dict, korean dict)
    pairs: each table's ``Mapping`` has its own ``Enum`` key type, so a
    shared list of them would only type-check as ``object`` under mypy.
    """

    result: list[tuple[str, str, str]] = []
    result += [
        ("AGENT", AGENT_EFFECT_TEXT[key], AGENT_EFFECT_TEXT_KO[key])
        for key in AGENT_EFFECT_TEXT
    ]
    result += [
        ("TRASH", TRASH_EFFECT_TEXT[key], TRASH_EFFECT_TEXT_KO[key])
        for key in TRASH_EFFECT_TEXT
    ]
    result += [
        ("DISCARD", DISCARD_EFFECT_TEXT[key], DISCARD_EFFECT_TEXT_KO[key])
        for key in DISCARD_EFFECT_TEXT
    ]
    result += [
        ("ACQUISITION", ACQUISITION_EFFECT_TEXT[key], ACQUISITION_EFFECT_TEXT_KO[key])
        for key in ACQUISITION_EFFECT_TEXT
    ]
    result += [
        (
            "REVEAL_ACQUISITION",
            REVEAL_ACQUISITION_EFFECT_TEXT[key],
            REVEAL_ACQUISITION_EFFECT_TEXT_KO[key],
        )
        for key in REVEAL_ACQUISITION_EFFECT_TEXT
    ]
    result += [
        (
            "REVEAL_CHOICE",
            REVEAL_CHOICE_EFFECT_TEXT[key],
            REVEAL_CHOICE_EFFECT_TEXT_KO[key],
        )
        for key in REVEAL_CHOICE_EFFECT_TEXT
    ]
    return result


def test_every_table_ko_text_uses_only_known_terms() -> None:
    terms = terms_keys()
    for _name, _en, ko in _all_ko_texts():
        assert_placeholders_are_terms(ko, terms)


def test_every_table_ko_text_has_no_stray_latin() -> None:
    for _name, _en, ko in _all_ko_texts():
        assert_no_stray_latin(ko)


def test_every_table_ko_text_matches_english_trash_and_discard() -> None:
    for _name, en, ko in _all_ko_texts():
        assert_trash_and_discard_match(en, ko)


def test_every_table_ko_text_never_summons_a_sandworm() -> None:
    for _name, en, ko in _all_ko_texts():
        assert_no_summon_for_sandworm(en, ko)


def test_every_real_reveal_effect_ko_text_is_valid() -> None:
    """The composed ``reveal_effect_text_ko`` renderer over every reveal
    effect actually printed on a card (not only the golden unit-test
    cases below), the same "no invalid placeholder / no stray Latin /
    trash matches discard" guard the table tests above run."""

    terms = terms_keys()
    checked = 0
    for entry in _ALL_REVEAL_EFFECT_ENTRIES:
        for effect in entry.reveal_effects:
            checked += 1
            en = reveal_effect_text(effect)
            ko = reveal_effect_text_ko(effect)
            assert isinstance(ko, str) and ko.strip()
            assert_placeholders_are_terms(ko, terms)
            assert_no_stray_latin(ko)
            assert_trash_and_discard_match(en, ko)
            assert_no_summon_for_sandworm(en, ko)
    assert checked > 0


def test_reveal_effect_text_ko_bene_gesserit_operative_golden() -> None:
    effect = PersonalCardRevealEffect(persuasion=2, minimum_spies_placed=2)

    assert (
        reveal_effect_text_ko(effect)
        == "{spy}를 2 이상 배치했다면: +{persuasion:2}"
    )


def test_reveal_effect_text_ko_flat_persuasion_and_strength() -> None:
    effect = PersonalCardRevealEffect(persuasion=1, strength=1)

    assert reveal_effect_text_ko(effect) == "+{persuasion:1}, +{sword:1}"


def test_reveal_effect_text_ko_faction_bond_condition() -> None:
    effect = PersonalCardRevealEffect(
        spice=2,
        required_faction_bond=PersonalCardBond.FREMEN,
    )

    assert reveal_effect_text_ko(effect) == "프레멘의 유대감이면: {spice:2}"


def test_reveal_effect_text_ko_high_council_and_swordmaster() -> None:
    # Paracompass's second Reveal effect.
    effect = PersonalCardRevealEffect(
        persuasion=1,
        requires_high_council=True,
        requires_swordmaster=True,
    )

    assert reveal_effect_text_ko(effect) == (
        "원로회 자리와 소드마스터를 보유했다면: +{persuasion:1}"
    )


def test_reveal_effect_text_ko_per_revealed_faction_scales_the_gain() -> None:
    effect = PersonalCardRevealEffect(
        persuasion=2,
        per_revealed_faction=PersonalCardBond.FREMEN,
    )

    assert reveal_effect_text_ko(effect) == (
        "+{persuasion:2} (공개한 프레멘 카드마다)"
    )


def test_reveal_effect_text_ko_influence_gain_names_its_faction() -> None:
    effect = PersonalCardRevealEffect(
        influence=1,
        influence_faction=PersonalCardBond.FREMEN,
        required_faction_bond=PersonalCardBond.FREMEN,
    )

    assert reveal_effect_text_ko(effect) == (
        "프레멘의 유대감이면: {influence_fremen:1}"
    )


def test_reveal_effect_text_ko_persuasion_per_completed_contract() -> None:
    effect = PersonalCardRevealEffect(persuasion_per_completed_contract=1)

    assert reveal_effect_text_ko(effect) == "+{persuasion:1} (완수한 {contract}마다)"
