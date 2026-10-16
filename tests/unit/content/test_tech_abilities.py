"""Tech tiles' acquire effects and abilities as ability records (composed A6a, A6b)."""

from dataclasses import replace

import pytest

from dune_imperium.content.bloodlines import tech
from dune_imperium.content.bloodlines.tech import (
    FLIP_ABILITIES,
    TECH_REVEAL_GAINS,
    TECH_TILES,
    TECH_TILES_BY_ID,
    TechAbility,
)
from dune_imperium.content.bloodlines.tech_abilities import (
    TECH_ABILITIES,
    TECH_ACQUIRE_ABILITIES,
    TRASH_SPY_TO_ACQUIRE,
)
from dune_imperium.content.uprising.abilities import AbilityTiming
from dune_imperium.content.uprising.effect_dsl import (
    CommandReached,
    DuringAgentTurn,
    EffectSection,
    GainInfluenceWhereAtMost,
    GainResources,
    RevealPersuasion,
    RevealSwords,
    SpyRecalledThisTurn,
    SummonSandworm,
    UseSignetAbility,
)
from dune_imperium.display.bloodlines import (
    tech_ability_text,
    tech_ability_text_ko,
    tech_acquire_text,
    tech_acquire_text_ko,
)
from dune_imperium.display.effect_dsl_text import condition_text, reward_text
from dune_imperium.display.effect_dsl_text_ko import condition_text_ko, reward_text_ko
from dune_imperium.rules import tech as rules_tech
from dune_imperium.rules.tech import TECH_HOOKS


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


def test_every_tile_prints_its_ability_as_records() -> None:
    """Flip, Reveal and Endgame lines are data; the flows kept as code are
    the hooks ``rules.tech`` names; the rule changes are standing records
    (composed A6b)."""

    assert set(TECH_ABILITIES) == {tile.tech_id for tile in TECH_TILES}
    hooks = {
        record.hook
        for records in TECH_ABILITIES.values()
        for record in records
        if record.hook is not None and record.timing is not AbilityTiming.STANDING
    }
    assert hooks | {TRASH_SPY_TO_ACQUIRE} == TECH_HOOKS
    standing = {
        tech_id
        for tech_id, records in TECH_ABILITIES.items()
        for record in records
        if record.timing is AbilityTiming.STANDING
    }
    assert standing == {
        "gene_locked_vault",
        "glowglobes",
        "navigation_chamber",
        "ornithopter_fleet",
        "sardaukar_high_command",
        "servo_receivers",
    }
    assert FLIP_ABILITIES == {
        TechAbility.FLIP_DRAW_INTRIGUE,
        TechAbility.FLIP_COMBAT_ICON,
        TechAbility.FLIP_SOLARI_AND_TRASH,
    }
    assert [
        (gain.tech_id, gain.command, gain.persuasion, gain.solari, gain.swords)
        for gain in TECH_REVEAL_GAINS
    ] == [
        ("delivery_bay", True, 0, 2, 0),
        ("self_destroying_messages", False, 1, 0, 0),
        ("training_depot", True, 0, 0, 2),
    ]


def test_the_new_tech_pieces_read_as_the_tiles_print_them() -> None:
    dropships = TECH_TILES_BY_ID["rapid_dropships"]
    assert tech_ability_text(dropships).startswith(condition_text(DuringAgentTurn()))
    assert tech_ability_text_ko(dropships).startswith(
        condition_text_ko(DuringAgentTurn())
    )
    panopticon = TECH_TILES_BY_ID["panopticon"]
    assert tech_ability_text(panopticon).endswith(
        reward_text(GainInfluenceWhereAtMost(1))
    )
    assert tech_ability_text_ko(panopticon).endswith(
        reward_text_ko(GainInfluenceWhereAtMost(1))
    )


@pytest.mark.parametrize(
    "line",
    [
        # Command pays no Persuasion: it opens on the others'.
        EffectSection(rewards=(RevealPersuasion(1),), condition=CommandReached()),
        # A Reveal gain the Reveal does not pay from a tile.
        EffectSection(rewards=(GainResources(spice=1),), condition=CommandReached()),
        EffectSection(rewards=(RevealSwords(2),), condition=SpyRecalledThisTurn()),
    ],
)
def test_the_reveal_compiler_refuses_what_the_reveal_cannot_pay(
    line: EffectSection, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = replace(TECH_ABILITIES["training_depot"][0], sections=(line,))
    monkeypatch.setattr(tech, "TECH_ABILITIES", {"training_depot": (record,)})
    with pytest.raises(ValueError):
        tech._reveal_gain(TECH_TILES_BY_ID["training_depot"])


@pytest.mark.parametrize(
    "records",
    [
        # A Flip reward the Flip code does not resolve.
        (
            replace(
                TECH_ABILITIES["advanced_data_analysis"][0],
                sections=(EffectSection(rewards=(SummonSandworm(),)),),
            ),
        ),
        # An Endgame line the Endgame code does not resolve.
        (
            replace(
                TECH_ABILITIES["choam_transports"][1],
                sections=(EffectSection(rewards=(GainResources(spice=1),)),),
            ),
        ),
        # A hook nobody registered.
        (replace(TECH_ABILITIES["suspensor_suits"][0], hook="unknown"),),
        # A standing record that prints a line.
        (
            replace(
                TECH_ABILITIES["glowglobes"][0],
                sections=(EffectSection(rewards=(GainResources(spice=1),)),),
            ),
        ),
    ],
)
def test_the_tech_rules_refuse_records_they_cannot_resolve(
    records: tuple[object, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        rules_tech, "TECH_ABILITIES", {"advanced_data_analysis": records}
    )
    with pytest.raises(ValueError):
        rules_tech._check_tech_records()
