"""Sardaukar Commanders and their Skill tiles [Bloodlines pp. 3-4].

The Commander rules live in ``docs/rules/bloodlines.md`` section 3; the seven
Skill effects are transcribed from the printed tile faces (asset repository
``cards/en/bloodlines/skill/``), cited as ``[<name> Skill tile]``, as ability
records (``skill_abilities.py``, composed A7a) compiled into the fields
below.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from dune_imperium.content.bloodlines.skill_abilities import SKILL_ABILITIES
from dune_imperium.content.schema import SourceDocument, SourceRef
from dune_imperium.content.uprising.abilities import (
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AgentOnSpaceWithIcon,
    GainCombatStrength,
    GainResources,
    InfluenceAtLeast,
    OpponentSandwormInConflict,
    RecruitTroops,
    RevealPersuasion,
    RevealSwords,
    TrashCard,
)
from dune_imperium.content.uprising.types import AgentIcon

# Four-player setup: five printed spaces plus Assembly Hall, and one
# Commander in the bank for Sardaukar Standard [Bloodlines p. 3].
COMMANDER_SETUP_SPACE_IDS: Final = (
    "sardaukar",
    "dutiful_service",
    "deliver_supplies",
    "high_council",
    "gather_support",
    "assembly_hall",
)
COMMANDER_TOTAL: Final = 7
COMMANDER_BANK_AT_SETUP: Final = COMMANDER_TOTAL - len(COMMANDER_SETUP_SPACE_IDS)
# "you may spend 2 Solari to acquire and then immediately recruit that
# Sardaukar Commander" / "you may pay 2 Solari to recruit one Sardaukar
# Commander from your supply" [Bloodlines p. 4].
COMMANDER_COST_SOLARI: Final = 2
# "It is a 'troop' that's worth 2 strength in the Conflict" [Bloodlines p. 4].
COMMANDER_STRENGTH: Final = 2
# 14 tiles, two of each of the seven Skills [Bloodlines pp. 2-3]; four face up.
SKILL_COPIES: Final = 2
SKILL_FACE_UP: Final = 4


class SkillKind(StrEnum):
    """Whether a Skill pays out in the Reveal turn or as Combat strength."""

    REVEAL = "reveal"
    STRENGTH = "strength"


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    """One Sardaukar Commander Skill and its printed effect."""

    skill_id: str
    name: str
    kind: SkillKind
    # Reveal turn bonuses, granted once when the Reveal begins with a
    # Commander in the Conflict.
    reveal_persuasion: int = 0
    reveal_spice: int = 0
    # Troops recruited in the Reveal turn (Hardy's troop icon).
    reveal_troops: int = 0
    # "Reveal Turn: Trash this -> 3 swords" (Desperate): an optional arrow.
    trash_for_strength: int = 0
    # Combat strength while a Commander is in the Conflict.
    strength: int = 0
    strength_if_landsraad_agent: int = 0
    strength_if_opponent_sandworm: int = 0
    strength_if_emperor_influence: int = 0
    emperor_influence_required: int = 0
    sources: tuple[SourceRef, ...] = (
        SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (4,)),
        SourceRef(SourceDocument.CARD_FACE, (1,)),
    )

    def __post_init__(self) -> None:
        if not self.skill_id or not self.name:
            raise ValueError("Skills require stable IDs and names")
        if (self.emperor_influence_required > 0) != (
            self.strength_if_emperor_influence > 0
        ):
            raise ValueError("an Emperor Influence bonus needs its threshold")


def _skill(skill_id: str, name: str) -> SkillDefinition:
    """One Skill, its kind and printed effect compiled from its record
    (composed A7a); raises ``ValueError`` for a record the fields cannot
    hold."""

    ability = SKILL_ABILITIES[skill_id]
    if (
        ability.requirement is not None
        or ability.trigger is not None
        or ability.hook is not None
        or ability.structure is not AbilityStructure.SEQUENCE
    ):
        raise ValueError(f"{skill_id}: a Skill pays every printed line")
    fields: dict[str, int] = {}

    def put(field: str, amount: int) -> None:
        if field in fields:
            raise ValueError(f"{skill_id}: {field} printed twice")
        fields[field] = amount

    if ability.timing is AbilityTiming.REVEAL:
        kind = SkillKind.REVEAL
        (line,) = ability.sections
        match ability.mark, line.condition, line.costs, line.rewards:
            case AbilityMark.AUTOMATIC, None, (), (
                RevealPersuasion(amount=n, per=None),
            ):
                put("reveal_persuasion", n)
            case AbilityMark.AUTOMATIC, None, (), (
                GainResources(solari=0, spice=n, water=0),
            ):
                put("reveal_spice", n)
            case AbilityMark.AUTOMATIC, None, (), (RecruitTroops(count=n),):
                put("reveal_troops", n)
            case AbilityMark.OPTIONAL, None, (TrashCard(this_card=True),), (
                RevealSwords(amount=n, per=None),
            ):
                put("trash_for_strength", n)
            case _:
                raise ValueError(f"{skill_id}: no Skill field holds {line!r}")
    elif ability.timing is AbilityTiming.IN_CONFLICT:
        kind = SkillKind.STRENGTH
        if ability.mark is not AbilityMark.AUTOMATIC:
            raise ValueError(f"{skill_id}: Skill strength needs no choice")
        for line in ability.sections:
            match line.condition, line.costs, line.rewards:
                case None, (), (GainCombatStrength(amount=n),):
                    put("strength", n)
                case AgentOnSpaceWithIcon(icon=AgentIcon.LANDSRAAD), (), (
                    GainCombatStrength(amount=n),
                ):
                    put("strength_if_landsraad_agent", n)
                case OpponentSandwormInConflict(), (), (GainCombatStrength(amount=n),):
                    put("strength_if_opponent_sandworm", n)
                case InfluenceAtLeast(faction=Faction.EMPEROR, amount=threshold), (), (
                    GainCombatStrength(amount=n),
                ):
                    put("strength_if_emperor_influence", n)
                    put("emperor_influence_required", threshold)
                case _:
                    raise ValueError(f"{skill_id}: no Skill field holds {line!r}")
    else:
        raise ValueError(f"{skill_id}: a Skill pays on the Reveal or in the Conflict")
    return SkillDefinition(
        skill_id,
        name,
        kind,
        reveal_persuasion=fields.get("reveal_persuasion", 0),
        reveal_spice=fields.get("reveal_spice", 0),
        reveal_troops=fields.get("reveal_troops", 0),
        trash_for_strength=fields.get("trash_for_strength", 0),
        strength=fields.get("strength", 0),
        strength_if_landsraad_agent=fields.get("strength_if_landsraad_agent", 0),
        strength_if_opponent_sandworm=fields.get("strength_if_opponent_sandworm", 0),
        strength_if_emperor_influence=fields.get("strength_if_emperor_influence", 0),
        emperor_influence_required=fields.get("emperor_influence_required", 0),
    )


# The seven Skills (their effects are the records in ``skill_abilities.py``).
SKILLS: Final[tuple[SkillDefinition, ...]] = (
    _skill("canny", "Canny"),
    _skill("charismatic", "Charismatic"),
    _skill("desperate", "Desperate"),
    _skill("driven", "Driven"),
    _skill("fierce", "Fierce"),
    _skill("hardy", "Hardy"),
    _skill("loyal", "Loyal"),
)
SKILLS_BY_ID: Final = {skill.skill_id: skill for skill in SKILLS}


def skill_tile_instance_ids() -> tuple[str, ...]:
    """Return stable IDs for the 14 physical Skill tiles."""

    return tuple(
        f"skill:{skill.skill_id}:{copy}"
        for skill in SKILLS
        for copy in range(SKILL_COPIES)
    )


def skill_for_instance(instance_id: str) -> SkillDefinition:
    """Resolve a Skill tile instance ID to its definition."""

    prefix = "skill:"
    if not instance_id.startswith(prefix):
        raise ValueError("not a Skill tile instance ID")
    try:
        skill_id, copy_text = instance_id.removeprefix(prefix).rsplit(":", maxsplit=1)
        copy = int(copy_text)
        skill = SKILLS_BY_ID[skill_id]
    except (KeyError, ValueError) as error:
        raise ValueError("unknown Skill tile instance ID") from error
    if not 0 <= copy < SKILL_COPIES:
        raise ValueError("Skill tile copy index is out of range")
    return skill
