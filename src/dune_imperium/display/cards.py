"""English display lines for one personal card's play-facing data.

Wording follows the same shared display contract as ``tokens``,
``effect_dsl_text`` and ``structs``: short imperative fragments, no trailing
period, resources lowercase, game terms capitalized as printed. Printed
Persuasion and strength (``reveal_persuasion``/``reveal_strength``) are
existing catalog fields the UI already surfaces directly, so
:func:`personal_card_text` never restates them; only dynamic effect data
(Agent-box effects, passives, automatic and choice Reveal effects, and
acquire/discard/trash triggers) produces lines.
"""

from typing import Final

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import ImperiumCardEntry
from dune_imperium.content.uprising.personal_cards import PersonalCardDefinition
from dune_imperium.content.uprising.reserve import ReserveStackDefinition
from dune_imperium.display.tokens import (
    ACQUISITION_EFFECT_TEXT,
    AGENT_EFFECT_TEXT,
    DISCARD_EFFECT_TEXT,
    REVEAL_ACQUISITION_EFFECT_TEXT,
    REVEAL_CHOICE_EFFECT_TEXT,
    TRASH_EFFECT_TEXT,
    reveal_effect_text,
)

_FACTION_NAMES: dict[Faction, str] = {
    Faction.EMPEROR: "Emperor",
    Faction.SPACING_GUILD: "Spacing Guild",
    Faction.BENE_GESSERIT: "Bene Gesserit",
    Faction.FREMEN: "Fremen",
}


def _faction_name(faction: Faction) -> str:
    return _FACTION_NAMES[faction]


def _factions_or(factions: tuple[Faction, ...]) -> str:
    """Join Faction names with a natural "or"/Oxford-comma list."""

    names = [_faction_name(faction) for faction in factions]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} or {names[1]}"
    return f"{', '.join(names[:-1])}, or {names[-1]}"


_NO_ADDITIONAL_ABILITY: Final = "(no additional ability)"
_PLAY_DATA_NOT_TRANSCRIBED: Final = "(play data not transcribed)"

# The single transcribed PersonalCardRevealAcquisitionEffect member is
# specific to The Spice Must Flow (see its enum name and Guild Spy's audit
# entry in docs/implementation-audits/personal-cards.md); this prefix names
# that condition rather than the generic "per acquired card" wording, since
# the effect does not trigger for other acquisitions.
_REVEAL_ACQUISITION_PREFIX = "Reveal, if you acquire The Spice Must Flow: "


def _agent_line(entry: PersonalCardDefinition) -> str | None:
    effect = entry.agent_effect
    if effect is None:
        return None
    text = AGENT_EFFECT_TEXT[effect]
    if not text:
        return None
    if entry.agent_spy_factions:
        text = f"{text} ({_factions_or(entry.agent_spy_factions)} Spy)"
    return f"Agent: {text}"


def _reveal_line(entry: PersonalCardDefinition) -> str | None:
    parts = [reveal_effect_text(effect) for effect in entry.reveal_effects]
    parts.extend(
        REVEAL_CHOICE_EFFECT_TEXT[choice] for choice in entry.reveal_choice_effects
    )
    if not parts:
        return None
    return f"Reveal: {'; '.join(parts)}"


def personal_card_text(entry: PersonalCardDefinition) -> list[str]:
    """Render one personal card's ordered English display lines.

    Covers ``ImperiumCardEntry``, ``StartingCardEntry`` and
    ``ReserveStackDefinition`` — the three sources sharing the personal-card
    Agent/Reveal schema (see ``content.uprising.personal_cards``). Each
    source declares a different subset of the optional fields (only
    ``ImperiumCardEntry`` carries ``ignores_influence_requirements``,
    ``allows_recruited_troop_deployment``, ``acquisition_effect``,
    ``trash_effect`` and ``play_data_complete``; only
    ``ReserveStackDefinition`` carries ``acquisition_vp``), so those are
    read through ``isinstance`` narrowing instead of a blanket ``getattr``.
    """

    if isinstance(entry, ImperiumCardEntry) and not entry.play_data_complete:
        return [_PLAY_DATA_NOT_TRANSCRIBED]

    lines: list[str] = []

    agent_line = _agent_line(entry)
    if agent_line is not None:
        lines.append(agent_line)

    if isinstance(entry, ImperiumCardEntry):
        if entry.ignores_influence_requirements:
            lines.append("Ignores Influence requirements")
        if entry.allows_recruited_troop_deployment:
            lines.append("Recruited troops may be deployed to the Conflict")

    reveal_line = _reveal_line(entry)
    if reveal_line is not None:
        lines.append(reveal_line)

    if isinstance(entry, ImperiumCardEntry) and entry.acquisition_effect is not None:
        lines.append(
            f"On acquire: {ACQUISITION_EFFECT_TEXT[entry.acquisition_effect]}"
        )

    if isinstance(entry, ReserveStackDefinition) and entry.acquisition_vp:
        lines.append(f"On acquire: Gain {entry.acquisition_vp} VP")

    if entry.discard_effect is not None:
        lines.append(f"On discard: {DISCARD_EFFECT_TEXT[entry.discard_effect]}")

    if isinstance(entry, ImperiumCardEntry) and entry.trash_effect is not None:
        lines.append(f"When trashed: {TRASH_EFFECT_TEXT[entry.trash_effect]}")

    if entry.reveal_acquisition_effect is not None:
        reward = REVEAL_ACQUISITION_EFFECT_TEXT[entry.reveal_acquisition_effect]
        lines.append(f"{_REVEAL_ACQUISITION_PREFIX}{reward}")

    if not lines:
        lines.append(_NO_ADDITIONAL_ABILITY)

    return lines
