"""Tests for one printed Agent-box icon's English/Korean detail text."""

import sys
from pathlib import Path

import pytest

from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.display.actions import (
    _ICON_CONDITIONS,
    _ICON_CONDITIONS_KO,
    agent_card_icon_text,
    agent_card_icon_text_ko,
)

# tests/support isn't a package pytest or mypy resolve from a dotted import
# (see tests/unit/display/test_struct_text.py's identical comment).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "support"))
from ko_text import (  # type: ignore[import-not-found]  # noqa: E402
    assert_no_stray_latin,
    assert_placeholders_are_terms,
    assert_trash_and_discard_match,
    terms_keys,
)

_KEYS = (
    "cards",
    "intrigue",
    "troops",
    "solari",
    "spice",
    "water",
    "trash_self",
    "pledge",
)

# One representative effect per _ICON_CONDITIONS row, plus None (no
# condition suffix) and a member with no row at all.
_EFFECTS = (
    None,
    PersonalCardAgentEffect.DRAW_PERSONAL_CARD,
    PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO,
    PersonalCardAgentEffect.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO,
    PersonalCardAgentEffect.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO,
    PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN,
    (
        PersonalCardAgentEffect
        .MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
    ),
)


def test_icon_conditions_ko_covers_the_same_pairs_as_english() -> None:
    assert set(_ICON_CONDITIONS_KO.keys()) == set(_ICON_CONDITIONS.keys())


def test_agent_card_icon_text_ko_matches_every_english_case() -> None:
    terms = terms_keys()
    for effect in _EFFECTS:
        for key in _KEYS:
            en = agent_card_icon_text(effect, key)
            ko = agent_card_icon_text_ko(effect, key)

            assert isinstance(ko, str) and ko.strip(), (effect, key)
            assert_placeholders_are_terms(ko, terms)
            assert_no_stray_latin(ko)
            assert_trash_and_discard_match(en, ko)


def test_agent_card_icon_text_ko_golden_base_cases() -> None:
    assert agent_card_icon_text_ko(None, "cards") == "{draw:1}"
    assert agent_card_icon_text_ko(None, "intrigue") == "{intrigue:1}"
    assert agent_card_icon_text_ko(None, "troops") == "{troop:1}"
    assert agent_card_icon_text_ko(None, "solari") == "{solari:2}"
    assert agent_card_icon_text_ko(None, "spice") == "{spice:1}"
    assert agent_card_icon_text_ko(None, "water") == "{water:1}"
    assert agent_card_icon_text_ko(None, "trash_self") == "이 카드 {trash}"
    assert (
        agent_card_icon_text_ko(None, "pledge")
        == "1등 보상에 {influence_any} 선택 추가"
    )


def test_agent_card_icon_text_ko_bene_gesserit_alliance_spice_is_two() -> None:
    # The only member whose "spice" base text differs by which card holds
    # it (English: "Gain 2 spice" instead of "Gain 1 spice").
    effect = (
        PersonalCardAgentEffect
        .MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
    )

    assert agent_card_icon_text(effect, "spice") == "Gain 2 spice"
    assert agent_card_icon_text_ko(effect, "spice") == "{spice:2}"


def test_agent_card_icon_text_ko_appends_the_influence_condition() -> None:
    effect = PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO

    assert (
        agent_card_icon_text(effect, "troops")
        == "Recruit 1 troop (at 2 Bene Gesserit Influence)"
    )
    assert (
        agent_card_icon_text_ko(effect, "troops")
        == "{troop:1} ({influence_bene_gesserit:2}일 때)"
    )


def test_agent_card_icon_text_ko_appends_the_spice_this_turn_condition() -> None:
    effect = (
        PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN
    )

    assert (
        agent_card_icon_text(effect, "cards")
        == "Draw 1 card (if you gained 2 or more spice this turn)"
    )
    assert (
        agent_card_icon_text_ko(effect, "cards")
        == "{draw:1} (이번 차례에 {spice}를 2 이상 얻었다면)"
    )


def test_agent_card_icon_text_ko_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        agent_card_icon_text_ko(None, "not_a_real_key")
