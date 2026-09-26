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
from dune_imperium.content.uprising.personal_cards import (
    PersonalCardDefinition,
    card_is_ghola,
    card_is_usurp,
)
from dune_imperium.content.uprising.reserve import ReserveStackDefinition
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.display.tokens import (
    ACQUISITION_EFFECT_TEXT,
    AGENT_EFFECT_TEXT,
    DISCARD_EFFECT_TEXT,
    ICON_CONDITION_TEXT,
    REVEAL_ACQUISITION_EFFECT_TEXT,
    REVEAL_CHOICE_EFFECT_TEXT,
    TRASH_EFFECT_TEXT,
    TURN_START_EFFECT_TEXT,
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


_AGENT_ICON_NAMES: Final[dict[AgentIcon, str]] = {
    AgentIcon.EMPEROR: "Emperor",
    AgentIcon.SPACING_GUILD: "Spacing Guild",
    AgentIcon.BENE_GESSERIT: "Bene Gesserit",
    AgentIcon.FREMEN: "Fremen",
    AgentIcon.LANDSRAAD: "Landsraad",
    AgentIcon.CITY: "City",
    AgentIcon.SPICE_TRADE: "Spice Trade",
    AgentIcon.SPY: "Spy",
}


def _names_and(names: list[str]) -> str:
    """Join names with a natural "and"/Oxford-comma list."""

    if len(names) <= 2:
        return " and ".join(names)
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _icon_condition_line(entry: PersonalCardDefinition) -> str | None:
    """Render the printed condition under which the greyed icons are real.

    Long Reach's and Show of Strength's Agent icons are printed greyed and
    only exist while the card's condition holds [card faces]; the catalog
    still lists them, so the text must say so.
    """

    if not isinstance(entry, ImperiumCardEntry) or entry.icon_condition is None:
        return None
    icons = _names_and([_AGENT_ICON_NAMES[icon] for icon in entry.agent_icons])
    return f"{ICON_CONDITION_TEXT[entry.icon_condition]}, this has {icons}"


_NO_ADDITIONAL_ABILITY: Final = "(no additional ability)"
_GHOLA_AGENT_LINE: Final = (
    "Agent: This card has the same Agent box as the other grafted card"
)
_PLAY_DATA_NOT_TRANSCRIBED: Final = "(play data not transcribed)"

# Reclaimed Forces never enters a player's deck (it is "never removed from
# the Tleilaxu Row" [Immortality p. 9] [Reclaimed Forces card]), so it has
# no Agent/Reveal play data and personal_card_text() would otherwise print
# "(play data not transcribed)" for it. Its printed acquire box is a choice
# ("recruit two troops -OR- Tleilaxu"), which fits no single
# PersonalCardAcquisitionEffect, so server.catalog renders this text
# directly instead of routing the card through personal_card_text().
RECLAIMED_FORCES_TEXT: Final[tuple[str, ...]] = (
    "On acquire (choose one): Recruit 2 troops / Tleilaxu "
    "(advance your Tleilaxu token)",
    "Never removed from the Tleilaxu Row",
)

# Blank Slate: "If grafted: This has [Emperor], [Spacing Guild], [Bene
# Gesserit], and [Fremen]" [Blank Slate card face]. The four Faction icons
# are added by rules.agent_icons via a card_id check rather than a typed
# ImperiumCardEntry field, so this line is hand-authored the same way.
_BLANK_SLATE_GRAFT_ICONS_LINE: Final = (
    "If grafted: This has Emperor, Spacing Guild, Bene Gesserit, "
    "and Fremen Agent icons"
)

# Usurp's GRAFT box is a passive with no PersonalCardAgentEffect member: it
# grafts to a card in the Imperium Row instead of one from the player's hand
# [Usurp card face].
_USURP_GRAFT_LINE: Final = (
    "Graft: You may graft this to a card in the Imperium Row without "
    "acquiring it. If you do, trash that card at the end of your turn"
)

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

    icon_condition_line = _icon_condition_line(entry)
    if icon_condition_line is not None:
        lines.append(icon_condition_line)
    agent_line = _agent_line(entry)
    if agent_line is not None:
        lines.append(agent_line)
    if card_is_ghola(entry):
        # The box is borrowed at play time (``rules.effects``), so the
        # printed Graft box has no effect of its own to render [Ghola card].
        lines.append(_GHOLA_AGENT_LINE)

    if isinstance(entry, ImperiumCardEntry) and entry.turn_start_effect is not None:
        # Litany Against Fear: a red turn-start box replaces its Agent box
        # [Litany Against Fear card face].
        lines.append(
            "At the start of your turn: "
            f"{TURN_START_EFFECT_TEXT[entry.turn_start_effect]}"
        )

    if isinstance(entry, ImperiumCardEntry):
        if entry.card.card_id == "blank_slate":
            lines.append(_BLANK_SLATE_GRAFT_ICONS_LINE)
        if card_is_usurp(entry):
            lines.append(_USURP_GRAFT_LINE)
        if entry.agent_icons_from_contracts:
            lines.append(
                "Has the Agent icons shown on all your incomplete contracts"
            )
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
