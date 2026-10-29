"""Rise of Ix's Imperium cards and its promo (stage P4a).

docs/base-game-and-ix-plan.md 17.1 and 17.7: 29 Imperium kinds, 35 cards
shuffled into the Imperium deck, and the promo Boundless Ambition kept apart
behind ``promo_cards`` (plan 9 8) [Rise of Ix p. 2]
(docs/rules/rise-of-ix.md 2). Per D1 (plan 2.4) every value comes from the
Steam app: the attribute table for cost and copies now, the card's screen
pieces and English text when its play data is transcribed; the rules behind
them are docs/rules/rise-of-ix.md.

These began as stage P4a identity entries (name, copies and cost), generated
by ``scripts/dwgr/imperium_entries.py --set ix skeleton``. Incomplete entries
keep ``play_data_complete`` False and expose no partial play data; printed
Infiltration icons are identity metadata. With ``rise_of_ix`` the original
game's deck takes only completed cards (Jamis and Sayyadina so far), while
the observation lists every identity from v39. Setup takes Rise of Ix on the
original game since stage P4c-5.
``content.uprising.imperium``'s
``IMPERIUM_CARDS_BY_ID`` resolves them; code that lists Uprising's own
cards iterates ``IMPERIUM_CARDS`` instead, and the original game's
``IMPERIUM_BASE_CARDS`` does not hold them.
"""

from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import ImperiumCardEntry
from dune_imperium.content.uprising.types import AgentIcon, PersonalCardAgentEffect

# The component table lists the cards [Rise of Ix p. 2]; the printed values
# are the app's (plan 2.4, D1).
IX_IMPERIUM_SOURCES: Final = (SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (2,)),)


def ix_imperium_card(card_id: str, name: str) -> CardDefinition:
    """The identity of a Rise of Ix Imperium card (no Dune Cards Hub URL:
    the faces are not read, D1)."""

    return CardDefinition(card_id=card_id, name=name, sources=IX_IMPERIUM_SOURCES)


# Typed: ``content.uprising.imperium`` reads it while both modules load.
IX_IMPERIUM_CARDS: Final[tuple[ImperiumCardEntry, ...]] = (
    ImperiumCardEntry(
        card=ix_imperium_card("appropriate", "Appropriate"),
        copies=1,
        acquisition_cost=5,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("bounty_hunter", "Bounty Hunter"),
        copies=1,
        acquisition_cost=1,
        infiltration_icons=(AgentIcon.CITY,),
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("choam_delegate", "CHOAM Delegate"),
        copies=1,
        acquisition_cost=1,
        infiltration_icons=(AgentIcon.SPICE_TRADE,),
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("court_intrigue", "Court Intrigue"),
        copies=1,
        acquisition_cost=2,
        infiltration_icons=(AgentIcon.EMPEROR,),
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("desert_ambush", "Desert Ambush"),
        copies=1,
        acquisition_cost=3,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("embedded_agent", "Embedded Agent"),
        copies=1,
        acquisition_cost=5,
        infiltration_icons=(AgentIcon.LANDSRAAD,),
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("esmar_tuek_card", "Esmar Tuek"),
        copies=1,
        acquisition_cost=5,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("freighter_fleet", "Freighter Fleet"),
        copies=2,
        acquisition_cost=2,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("full_scale_assault", "Full-Scale Assault"),
        copies=1,
        acquisition_cost=8,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("guild_accord", "Guild Accord"),
        copies=1,
        acquisition_cost=6,
        infiltration_icons=(AgentIcon.SPACING_GUILD,),
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("guild_chief_administrator", "Guild Chief Administrator"),
        copies=1,
        acquisition_cost=4,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("imperial_bashar", "Imperial Bashar"),
        copies=1,
        acquisition_cost=4,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("imperial_shock_trooper", "Imperial Shock Trooper"),
        copies=1,
        acquisition_cost=3,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("in_the_shadows", "In The Shadows"),
        copies=2,
        acquisition_cost=2,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("ix_guild_compact", "Ix-Guild Compact"),
        copies=1,
        acquisition_cost=3,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("ixian_engineer", "Ixian Engineer"),
        copies=2,
        acquisition_cost=5,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("jamis", "Jamis"),
        copies=1,
        acquisition_cost=2,
        infiltration_icons=(AgentIcon.FREMEN,),
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN,),
        agent_effect=PersonalCardAgentEffect.TRASH_PERSONAL_CARD,
        reveal_persuasion=1,
        reveal_strength=2,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("landing_rights", "Landing Rights"),
        copies=1,
        acquisition_cost=4,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("local_fence", "Local Fence"),
        copies=1,
        acquisition_cost=3,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("negotiated_withdrawal", "Negotiated Withdrawal"),
        copies=2,
        acquisition_cost=4,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("satellite_ban", "Satellite Ban"),
        copies=1,
        acquisition_cost=5,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("sayyadina", "Sayyadina"),
        copies=1,
        acquisition_cost=3,
        factions=(Faction.BENE_GESSERIT, Faction.FREMEN),
        agent_icons=(AgentIcon.BENE_GESSERIT, AgentIcon.FREMEN),
        # App pieces: "[3 water] -> [1 Victory Point]"; the arrow is
        # optional [DI p. 9] [FAQ p. 3]. Reveal: "Fremen Bond: [P3]",
        # another Fremen card in play [DI p. 16], no fixed Persuasion.
        agent_effect=PersonalCardAgentEffect.MAY_PAY_THREE_WATER_FOR_VP,
        play_data_complete=True,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("shai_hulud", "Shai-Hulud"),
        copies=1,
        acquisition_cost=7,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("spice_trader", "Spice Trader"),
        copies=1,
        acquisition_cost=4,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("treachery", "Treachery"),
        copies=2,
        acquisition_cost=6,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("truthsayer", "Truthsayer"),
        copies=2,
        acquisition_cost=3,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("water_peddler", "Water Peddler"),
        copies=1,
        acquisition_cost=1,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("web_of_power", "Web of Power"),
        copies=1,
        acquisition_cost=4,
        infiltration_icons=(AgentIcon.BENE_GESSERIT,),
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("weirding_way", "Weirding Way"),
        copies=1,
        acquisition_cost=3,
    ),
    ImperiumCardEntry(
        card=ix_imperium_card("boundless_ambition", "Boundless Ambition"),
        copies=1,
        acquisition_cost=5,
        promo=True,
    ),
)
