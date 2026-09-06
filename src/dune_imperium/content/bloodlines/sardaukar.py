"""Sardaukar Commanders and their Skill tiles [Bloodlines pp. 3-4].

The Commander rules live in ``docs/rules/bloodlines.md`` section 3; the seven
Skill effects are transcribed from the printed tile faces (asset repository
``cards/en/bloodlines/skill/``), cited as ``[<name> Skill tile]``.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from dune_imperium.content.schema import SourceDocument, SourceRef

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
    reveal_water: int = 0
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


SKILLS: Final[tuple[SkillDefinition, ...]] = (
    # "If you have an Agent on a [Landsraad] board space: 2 swords".
    SkillDefinition(
        "canny", "Canny", SkillKind.STRENGTH, strength_if_landsraad_agent=2
    ),
    # "Reveal Turn: 1 Persuasion".
    SkillDefinition(
        "charismatic", "Charismatic", SkillKind.REVEAL, reveal_persuasion=1
    ),
    # "Reveal Turn: Trash this -> 3 swords".
    SkillDefinition("desperate", "Desperate", SkillKind.REVEAL, trash_for_strength=3),
    # "Reveal Turn: 1 spice".
    SkillDefinition("driven", "Driven", SkillKind.REVEAL, reveal_spice=1),
    # "1 sword. If any opponent has a sandworm in the Conflict: +1 sword".
    SkillDefinition(
        "fierce",
        "Fierce",
        SkillKind.STRENGTH,
        strength=1,
        strength_if_opponent_sandworm=1,
    ),
    # "Reveal Turn: 1 water".
    SkillDefinition("hardy", "Hardy", SkillKind.REVEAL, reveal_water=1),
    # "[Emperor] 3 Influence: 2 swords".
    SkillDefinition(
        "loyal",
        "Loyal",
        SkillKind.STRENGTH,
        strength_if_emperor_influence=2,
        emperor_influence_required=3,
    ),
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
