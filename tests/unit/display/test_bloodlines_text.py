"""Tests for the Bloodlines Skill and Tech tile display text."""

import sys
from dataclasses import fields
from pathlib import Path

from dune_imperium.content.bloodlines.sardaukar import SKILLS, SKILLS_BY_ID
from dune_imperium.content.bloodlines.tech import (
    TECH_TILES,
    TECH_TILES_BY_ID,
    TechAbility,
)
from dune_imperium.display.bloodlines import (
    TECH_ABILITY_TEXT,
    TECH_ABILITY_TEXT_KO,
    skill_effect_text,
    skill_effect_text_ko,
    tech_ability_text,
    tech_ability_text_ko,
    tech_acquire_text,
    tech_acquire_text_ko,
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


def test_every_tech_ability_has_text() -> None:
    assert set(TECH_ABILITY_TEXT) == set(TechAbility)
    assert all(text for text in TECH_ABILITY_TEXT.values())
    assert len(TECH_TILES) == 18
    assert all(tech_ability_text(tile) for tile in TECH_TILES)


def test_every_skill_renders_a_non_empty_effect() -> None:
    assert len(SKILLS) == 7
    assert all(skill_effect_text(skill) for skill in SKILLS)
    assert skill_effect_text(SKILLS_BY_ID["charismatic"]) == (
        "Reveal Turn: +1 Persuasion"
    )
    driven = skill_effect_text(SKILLS_BY_ID["driven"])
    assert driven.startswith("Reveal Turn: Gain")


def test_acquire_text_is_empty_exactly_when_the_tile_has_no_acquire_effect() -> None:
    acquire_fields = [
        f.name for f in fields(TECH_TILES[0]) if f.name.startswith("acquire_")
    ]
    assert acquire_fields
    for tile in TECH_TILES:
        has_effect = any(getattr(tile, name) for name in acquire_fields)
        assert bool(tech_acquire_text(tile)) is has_effect, tile.tech_id


def test_tech_text_goldens() -> None:
    fleet = TECH_TILES_BY_ID["ornithopter_fleet"]
    assert tech_ability_text(fleet) == "All of your battle icons are Ornithopter"
    high_command = TECH_TILES_BY_ID["sardaukar_high_command"]
    assert tech_acquire_text(high_command) == "Gain 1 VP"
    drones = TECH_TILES_BY_ID["spy_drones"]
    assert tech_acquire_text(drones) == "Place 2 Spies with Deep Cover"
    assert tech_acquire_text(TECH_TILES_BY_ID["ornithopter_fleet"]) == "Gain 2 troops"
    assert tech_acquire_text(TECH_TILES_BY_ID["training_depot"]) == ""


# ---------- Korean twins (Step K4, 2026-09-25) ----------


def test_every_tech_ability_ko_has_valid_korean_text() -> None:
    terms = terms_keys()
    assert set(TECH_ABILITY_TEXT_KO) == set(TechAbility)
    for ability, english in TECH_ABILITY_TEXT.items():
        korean = TECH_ABILITY_TEXT_KO[ability]
        assert isinstance(korean, str) and korean.strip(), ability
        assert_placeholders_are_terms(korean, terms)
        assert_no_stray_latin(korean)
        assert_trash_and_discard_match(english, korean)
    assert all(tech_ability_text_ko(tile) for tile in TECH_TILES)


def test_every_skill_ko_renders_a_non_empty_effect() -> None:
    terms = terms_keys()
    for skill in SKILLS:
        korean = skill_effect_text_ko(skill)
        assert korean, skill.skill_id
        assert_placeholders_are_terms(korean, terms)
        assert_no_stray_latin(korean)
        assert_trash_and_discard_match(skill_effect_text(skill), korean)
        assert_no_summon_for_sandworm(skill_effect_text(skill), korean)
    assert skill_effect_text_ko(SKILLS_BY_ID["charismatic"]) == (
        "{reveal_turn}: +{persuasion:1}"
    )
    driven = skill_effect_text_ko(SKILLS_BY_ID["driven"])
    assert driven.startswith("{reveal_turn}: {spice:")


def test_acquire_text_ko_is_empty_exactly_when_english_is() -> None:
    for tile in TECH_TILES:
        assert bool(tech_acquire_text_ko(tile)) is bool(tech_acquire_text(tile)), (
            tile.tech_id
        )


def test_acquire_text_ko_is_valid_korean_for_every_tile() -> None:
    terms = terms_keys()
    for tile in TECH_TILES:
        english = tech_acquire_text(tile)
        korean = tech_acquire_text_ko(tile)
        if not english:
            continue
        assert_placeholders_are_terms(korean, terms)
        assert_no_stray_latin(korean)
        assert_trash_and_discard_match(english, korean)


def test_tech_text_goldens_ko() -> None:
    fleet = TECH_TILES_BY_ID["ornithopter_fleet"]
    assert tech_ability_text_ko(fleet) == (
        "당신이 보유한 모든 {battle_icon}이 오니솝터가 됨"
    )
    high_command = TECH_TILES_BY_ID["sardaukar_high_command"]
    assert tech_acquire_text_ko(high_command) == "{victory_point:1}"
    drones = TECH_TILES_BY_ID["spy_drones"]
    assert tech_acquire_text_ko(drones) == "{spy} 2 배치 (잠복 스파이)"
    assert tech_acquire_text_ko(TECH_TILES_BY_ID["ornithopter_fleet"]) == "{troop:2}"
    assert tech_acquire_text_ko(TECH_TILES_BY_ID["training_depot"]) == ""


def test_forbidden_weapons_ability_ko_uses_the_generic_influence_icon() -> None:
    """"lose 1 Influence" is lower-case mid-sentence, so ICON_RULES' own
    capital-only "Lose (\\d+) Influence" rule never matches it — English
    draws the generic {influence_any} icon here, not {influence_lose}
    (2026-09-25 review, caught by scripts/e2e/effect_text.py's icon-parity
    sweep against the live client)."""

    korean = TECH_ABILITY_TEXT_KO[TechAbility.FORBIDDEN_WEAPONS]
    assert "{influence_any:1}" in korean
    assert "{influence_lose" not in korean
