"""Tests for the Bloodlines Skill and Tech tile display text."""

from dataclasses import fields

from dune_imperium.content.bloodlines.sardaukar import SKILLS, SKILLS_BY_ID
from dune_imperium.content.bloodlines.tech import (
    TECH_TILES,
    TECH_TILES_BY_ID,
    TechAbility,
)
from dune_imperium.display.bloodlines import (
    TECH_ABILITY_TEXT,
    skill_effect_text,
    tech_ability_text,
    tech_acquire_text,
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
