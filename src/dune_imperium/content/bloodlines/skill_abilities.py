"""The Sardaukar Commander Skill tiles as ability records (composed effects, A7a).

docs/composed-effects-plan.md 5 (A7a; user decision 2026-10-17): a Skill
tile pays while its Commander is in the Conflict [Bloodlines p. 4] -- a
Reveal Turn line, or strength (the new ``IN_CONFLICT`` timing). Keyed by
Skill id; ``content.bloodlines.sardaukar`` compiles the records back into the
unchanged ``SkillDefinition`` fields, which ``rules.reveal_turn``,
``rules.strength`` and the rest read. The printed text is
``display/bloodlines.py``.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityTiming,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AgentOnSpaceWithIcon,
    EffectSection,
    GainCombatStrength,
    GainResources,
    InfluenceAtLeast,
    OpponentSandwormInConflict,
    RecruitTroops,
    RevealPersuasion,
    RevealSwords,
    Reward,
    TrashCard,
)
from dune_imperium.content.uprising.types import AgentIcon


def _reveal(reward: Reward) -> Ability:
    """A Reveal Turn line, paid without a choice."""

    return Ability(
        timing=AbilityTiming.REVEAL,
        sections=(EffectSection(rewards=(reward,)),),
        mark=AbilityMark.AUTOMATIC,
    )


def _strength(*lines: EffectSection) -> Ability:
    """Strength while the Commander is in the Conflict."""

    return Ability(
        timing=AbilityTiming.IN_CONFLICT, sections=lines, mark=AbilityMark.AUTOMATIC
    )


SKILL_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # "If you have an Agent on a [Landsraad] board space: 2 swords".
        "canny": _strength(
            EffectSection(
                rewards=(GainCombatStrength(2),),
                condition=AgentOnSpaceWithIcon(AgentIcon.LANDSRAAD),
            )
        ),
        # "Reveal Turn: 1 Persuasion".
        "charismatic": _reveal(RevealPersuasion(1)),
        # "Reveal Turn: Trash this -> 3 swords": an optional arrow.
        "desperate": Ability(
            timing=AbilityTiming.REVEAL,
            sections=(
                EffectSection(
                    rewards=(RevealSwords(3),), costs=(TrashCard(this_card=True),)
                ),
            ),
            mark=AbilityMark.OPTIONAL,
        ),
        # "Reveal Turn: 1 spice".
        "driven": _reveal(GainResources(spice=1)),
        # "1 sword. If any opponent has a sandworm in the Conflict: +1 sword".
        "fierce": _strength(
            EffectSection(rewards=(GainCombatStrength(1),)),
            EffectSection(
                rewards=(GainCombatStrength(1),),
                condition=OpponentSandwormInConflict(),
            ),
        ),
        # "Reveal Turn: [troop]": the grey cube is the troop icon, "Recruit
        # one troop" [Main p. 20] [Hardy Skill tile] (not a water drop).
        "hardy": _reveal(RecruitTroops(1)),
        # "[Emperor] 3 Influence: 2 swords".
        "loyal": _strength(
            EffectSection(
                rewards=(GainCombatStrength(2),),
                condition=InfluenceAtLeast(Faction.EMPEROR, 3),
            )
        ),
    }
)
