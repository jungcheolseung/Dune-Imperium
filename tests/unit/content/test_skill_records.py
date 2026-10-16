"""The Sardaukar Skill tiles as ability records (composed A7a)."""

from dataclasses import replace

import pytest

from dune_imperium.content.bloodlines import sardaukar
from dune_imperium.content.bloodlines.sardaukar import SKILLS, SKILLS_BY_ID, SkillKind
from dune_imperium.content.bloodlines.skill_abilities import SKILL_ABILITIES
from dune_imperium.content.uprising.abilities import AbilityTiming
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AgentOnSpaceWithIcon,
    EffectSection,
    GainCombatStrength,
    InfluenceAtLeast,
    OpponentSandwormInConflict,
    RevealPersuasion,
    SummonSandworm,
)
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.display.bloodlines import skill_effect_text, skill_effect_text_ko
from dune_imperium.display.effect_dsl_text import condition_text
from dune_imperium.display.effect_dsl_text_ko import condition_text_ko


def test_every_skill_takes_its_effect_from_its_record() -> None:
    assert set(SKILL_ABILITIES) == set(SKILLS_BY_ID)
    assert len(SKILLS) == 7
    for skill in SKILLS:
        timing = SKILL_ABILITIES[skill.skill_id].timing
        expected = (
            AbilityTiming.REVEAL
            if skill.kind is SkillKind.REVEAL
            else AbilityTiming.IN_CONFLICT
        )
        assert timing is expected
    assert SKILLS_BY_ID["loyal"].emperor_influence_required == 3
    assert SKILLS_BY_ID["desperate"].trash_for_strength == 3


def test_the_skill_conditions_read_as_the_tiles_print_them() -> None:
    canny = SKILLS_BY_ID["canny"]
    landsraad = AgentOnSpaceWithIcon(AgentIcon.LANDSRAAD)
    assert f"If {condition_text(landsraad)}:" in skill_effect_text(canny)
    assert condition_text_ko(landsraad) in skill_effect_text_ko(canny)
    fierce = SKILLS_BY_ID["fierce"]
    sandworm = OpponentSandwormInConflict()
    assert f"If {condition_text(sandworm)}:" in skill_effect_text(fierce)
    assert condition_text_ko(sandworm) in skill_effect_text_ko(fierce)


@pytest.mark.parametrize(
    "record",
    [
        # Strength printed twice without a condition.
        replace(
            SKILL_ABILITIES["fierce"],
            sections=(
                EffectSection(rewards=(GainCombatStrength(1),)),
                EffectSection(rewards=(GainCombatStrength(1),)),
            ),
        ),
        # A condition no Skill field holds.
        replace(
            SKILL_ABILITIES["loyal"],
            sections=(
                EffectSection(
                    rewards=(GainCombatStrength(2),),
                    condition=InfluenceAtLeast(Faction.FREMEN, 3),
                ),
            ),
        ),
        # A Reveal reward no Skill field holds.
        replace(
            SKILL_ABILITIES["charismatic"],
            sections=(EffectSection(rewards=(SummonSandworm(),)),),
        ),
        # Reveal Persuasion as strength.
        replace(
            SKILL_ABILITIES["fierce"],
            sections=(EffectSection(rewards=(RevealPersuasion(1),)),),
        ),
    ],
)
def test_the_skill_compiler_refuses_what_the_fields_cannot_hold(
    record: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sardaukar, "SKILL_ABILITIES", {"skill": record})
    with pytest.raises(ValueError):
        sardaukar._skill("skill", "Skill")
