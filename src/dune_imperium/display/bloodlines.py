"""English display text for the Bloodlines Skill tiles and Tech tiles.

The engine's typed definitions (``content/bloodlines``) are rendered into
the short lines the browser catalog shows; the wording follows the tile
faces transcribed in ``docs/rules/bloodlines.md``.
"""

from types import MappingProxyType
from typing import Final

from dune_imperium.content.bloodlines.sardaukar import SkillDefinition
from dune_imperium.content.bloodlines.tech import TechAbility, TechTile

TECH_ABILITY_TEXT: Final = MappingProxyType(
    {
        TechAbility.FLIP_DRAW_INTRIGUE: "Flip → Draw 1 Intrigue card",
        TechAbility.CONTRACT_COMPLETION_DRAW: (
            "When you complete a contract: Draw 1 card. Endgame: 1 VP if you "
            "have completed four or more contracts"
        ),
        TechAbility.COMMAND_TWO_SOLARI: "Reveal Turn: Command (6+): Gain 2 solari",
        TechAbility.FORBIDDEN_WEAPONS: (
            "Reveal Turn: You must choose: +3 swords and lose 1 Influence — or — "
            "lose all your spice and trash this"
        ),
        TechAbility.INTRIGUE_STEAL_PROTECTION: (
            "Your Intrigue cards can't be stolen unless you have five or more"
        ),
        TechAbility.PEEK_TOP_CARD: (
            "You may look at the top card of your deck at any time"
        ),
        TechAbility.SPACE_DISCOUNT: "Board spaces cost you 1 spice or 1 solari less",
        TechAbility.ORNITHOPTER_ICONS: "All of your battle icons are Ornithopter",
        TechAbility.PANOPTICON: (
            "Reveal Turn: Place a Spy, Gain 1 troop. Endgame: Gain 1 Influence "
            "with each Faction where you have 1 or less Influence"
        ),
        TechAbility.CONFLICT_WIN_DRAW: "When you win a Conflict: Draw 1 card",
        TechAbility.PLASTEEL_BLADES: (
            "Whenever you recruit a Sardaukar Commander: Trash this → Gain an "
            "additional Sardaukar Commander Skill"
        ),
        TechAbility.FLIP_COMBAT_ICON: "Agent Turn: Flip → Combat icon",
        TechAbility.COMMANDER_DISCOUNT: (
            "Recruiting a Sardaukar Commander (including when you acquire one) "
            "costs you 1 solari less"
        ),
        TechAbility.REVEAL_PERSUASION: "Reveal Turn: +1 Persuasion",
        TechAbility.SIGNET_FACTION_ICONS: (
            "Your Signet Ring has the Emperor, Spacing Guild, Bene Gesserit and "
            "Fremen icons"
        ),
        TechAbility.FLIP_SOLARI_AND_TRASH: (
            "Flip → Gain 1 solari, and if you recalled a Spy this turn: trash a card"
        ),
        TechAbility.INTRIGUE_DRAW_TROOP: (
            "For each Intrigue card you draw or steal during your turn: Gain 1 "
            "troop, deploy it to the Conflict"
        ),
        TechAbility.COMMAND_TWO_STRENGTH: "Reveal Turn: Command (6+): +2 swords",
    }
)


def skill_effect_text(skill: SkillDefinition) -> str:
    """Render one Skill tile's printed effect."""

    parts: list[str] = []
    if skill.reveal_persuasion:
        parts.append(f"Reveal Turn: +{skill.reveal_persuasion} Persuasion")
    if skill.reveal_spice:
        parts.append(f"Reveal Turn: Gain {skill.reveal_spice} spice")
    if skill.reveal_water:
        parts.append(f"Reveal Turn: Gain {skill.reveal_water} water")
    if skill.trash_for_strength:
        parts.append(f"Reveal Turn: Trash this → +{skill.trash_for_strength} swords")
    if skill.strength:
        parts.append(f"+{skill.strength} sword")
    if skill.strength_if_landsraad_agent:
        parts.append(
            "If you have an Agent on a Landsraad board space: "
            f"+{skill.strength_if_landsraad_agent} swords"
        )
    if skill.strength_if_opponent_sandworm:
        parts.append(
            "If any opponent has a sandworm in the Conflict: "
            f"+{skill.strength_if_opponent_sandworm} sword"
        )
    if skill.strength_if_emperor_influence:
        parts.append(
            f"Emperor Influence {skill.emperor_influence_required}+: "
            f"+{skill.strength_if_emperor_influence} swords"
        )
    return ". ".join(parts)


def tech_acquire_text(tile: TechTile) -> str:
    """Render the tile's acquire effect (empty when the tile has none)."""

    parts: list[str] = []
    if tile.acquire_requires_spy_trash:
        parts.append("To acquire this, trash one of your Spies from the board")
    if tile.acquire_may_destroy_shield_wall:
        parts.append("You may destroy the Shield Wall")
    if tile.acquire_solari:
        parts.append(f"Gain {tile.acquire_solari} solari")
    if tile.acquire_troops:
        parts.append(
            f"Gain {tile.acquire_troops} troop{'s' if tile.acquire_troops > 1 else ''}"
        )
    if tile.acquire_intrigue:
        parts.append(f"Draw {tile.acquire_intrigue} Intrigue card")
    if tile.acquire_cards:
        parts.append(f"Draw {tile.acquire_cards} card")
    if tile.acquire_victory_points:
        parts.append(f"Gain {tile.acquire_victory_points} VP")
    if tile.acquire_contracts:
        parts.append("Gain a contract")
    if tile.acquire_influence_choice:
        parts.append("Gain 1 Influence with a chosen Faction")
    if tile.acquire_intrigue_or_card:
        parts.append("Draw 1 Intrigue card — or — Draw 1 card")
    if tile.acquire_may_trash_card:
        parts.append("You may trash a card")
    if tile.acquire_deep_cover_spies:
        parts.append(f"Place {tile.acquire_deep_cover_spies} Spies with Deep Cover")
    return ". ".join(parts)


def tech_ability_text(tile: TechTile) -> str:
    """Render the tile's ability."""

    return TECH_ABILITY_TEXT[tile.ability]
