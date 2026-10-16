"""Tech tiles' acquire effects as ability records (composed A6a)."""

from dataclasses import replace

import pytest

from dune_imperium.content.bloodlines import tech
from dune_imperium.content.bloodlines.tech import TECH_TILES, TECH_TILES_BY_ID
from dune_imperium.content.bloodlines.tech_abilities import (
    TECH_ACQUIRE_ABILITIES,
    TRASH_SPY_TO_ACQUIRE,
)
from dune_imperium.content.uprising.abilities import AbilityTiming
from dune_imperium.content.uprising.effect_dsl import (
    EffectSection,
    GainResources,
    SummonSandworm,
    UseSignetAbility,
)
from dune_imperium.display.bloodlines import tech_acquire_text, tech_acquire_text_ko
from dune_imperium.display.effect_dsl_text import reward_text
from dune_imperium.display.effect_dsl_text_ko import reward_text_ko


def test_every_tile_with_an_acquire_box_takes_it_from_its_record() -> None:
    """The records name exactly the tiles printing an acquire box or
    prerequisite (16 keys on 14 tiles, plus Advanced Data Analysis)."""

    printed = {
        tile.tech_id
        for tile in TECH_TILES
        if tile.acquire_effect_keys or tile.acquire_requires_spy_trash
    }
    assert printed == set(TECH_ACQUIRE_ABILITIES)
    assert sum(len(tile.acquire_effect_keys) for tile in TECH_TILES) == 16
    for ability in TECH_ACQUIRE_ABILITIES.values():
        assert ability.timing is AbilityTiming.ACQUIRE
    assert TECH_ACQUIRE_ABILITIES["advanced_data_analysis"].hook == (
        TRASH_SPY_TO_ACQUIRE
    )
    assert TECH_TILES_BY_ID["advanced_data_analysis"].acquire_requires_spy_trash
    assert TECH_TILES_BY_ID["spy_drones"].acquire_deep_cover_spies == 2
    assert TECH_TILES_BY_ID["gene_locked_vault"].acquire_intrigue_or_card


def test_the_signet_icon_reads_as_servo_receivers_prints_it() -> None:
    servo = TECH_TILES_BY_ID["servo_receivers"]
    assert TECH_ACQUIRE_ABILITIES["servo_receivers"].sections == (
        EffectSection(rewards=(UseSignetAbility(),)),
    )
    assert reward_text(UseSignetAbility()) == tech_acquire_text(servo)
    assert reward_text_ko(UseSignetAbility()) == tech_acquire_text_ko(servo)


@pytest.mark.parametrize(
    "record",
    [
        # The same icon twice: no field holds it.
        replace(
            TECH_ACQUIRE_ABILITIES["plasteel_blades"],
            sections=(
                EffectSection(rewards=(GainResources(solari=4),)),
                EffectSection(rewards=(GainResources(solari=1),)),
            ),
            structure=TECH_ACQUIRE_ABILITIES["forbidden_weapons"].structure,
        ),
        # A reward no acquire field holds.
        replace(
            TECH_ACQUIRE_ABILITIES["plasteel_blades"],
            sections=(EffectSection(rewards=(SummonSandworm(),)),),
        ),
        # Spice: the tiles print none.
        replace(
            TECH_ACQUIRE_ABILITIES["plasteel_blades"],
            sections=(EffectSection(rewards=(GainResources(spice=1),)),),
        ),
        # An unknown hook.
        replace(TECH_ACQUIRE_ABILITIES["advanced_data_analysis"], hook="unknown"),
    ],
)
def test_the_compiler_refuses_what_the_tile_fields_cannot_hold(
    record: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tech, "TECH_ACQUIRE_ABILITIES", {"plasteel_blades": record})
    with pytest.raises(ValueError):
        tech._acquire("plasteel_blades")
