"""Printed symbols every content set uses: Factions, Agent and battle icons,
Conflict tiers (docs/content-core-refactor-plan.md 2.1).
"""

from enum import IntEnum, StrEnum


class AgentIcon(StrEnum):
    """Agent icons shared by cards and board spaces."""

    EMPEROR = "emperor"
    SPACING_GUILD = "spacing_guild"
    BENE_GESSERIT = "bene_gesserit"
    FREMEN = "fremen"
    LANDSRAAD = "landsraad"
    CITY = "city"
    SPICE_TRADE = "spice_trade"
    SPY = "spy"


class PersonalCardBond(StrEnum):
    """Faction affiliation required from another card in play."""

    EMPEROR = "emperor"
    SPACING_GUILD = "spacing_guild"
    BENE_GESSERIT = "bene_gesserit"
    FREMEN = "fremen"


class BattleIcon(StrEnum):
    """Icons paired by Objective and won Conflict cards."""

    CRYSKNIFE = "crysknife"
    DESERT_MOUSE = "desert_mouse"
    ORNITHOPTER = "ornithopter"
    WILD = "wild"


class ConflictTier(IntEnum):
    """The three Conflict deck backs."""

    ONE = 1
    TWO = 2
    THREE = 3


class Faction(StrEnum):
    """The four influence factions."""

    EMPEROR = "emperor"
    SPACING_GUILD = "spacing_guild"
    BENE_GESSERIT = "bene_gesserit"
    FREMEN = "fremen"
