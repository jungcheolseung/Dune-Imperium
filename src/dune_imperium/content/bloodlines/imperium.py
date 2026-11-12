"""Bloodlines' Imperium cards for the Uprising-format deck (``bloodlines``).

Moved from ``content.uprising.imperium`` (docs/content-core-refactor-plan.md
8.3, user decision 2026-11-04); ``content.registry.imperium`` puts them after
Uprising's own cards.
"""

from typing import Any, Final

from dune_imperium.content.core.cards import ImperiumCardEntry, imperium_card_entry
from dune_imperium.content.core.icons import AgentIcon, Faction
from dune_imperium.content.core.schema import GameOption, SourceDocument, SourceRef

PROMO_SOURCES: Final = (SourceRef(SourceDocument.CARD_FACE, (1,)),)
# Bloodlines cards: the rulebook lists their counts and setup [Bloodlines
# pp. 2-3]; the printed text comes from the card face.
BLOODLINES_SOURCES: Final = (
    SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (2, 3)),
    SourceRef(SourceDocument.CARD_FACE, (1,)),
)


def _entry(
    catalog_id: int | None,
    slug: str,
    name: str,
    acquisition_cost: int,
    *,
    requires: frozenset[GameOption] = frozenset(),
    **fields: Any,
) -> ImperiumCardEntry:
    return imperium_card_entry(
        catalog_id,
        slug,
        name,
        acquisition_cost,
        catalog_set="bloodlines",
        sources=(
            PROMO_SOURCES if GameOption.PROMO_CARDS in requires else BLOODLINES_SOURCES
        ),
        requires=requires,
        **fields,
    )


BLOODLINES_IMPERIUM_CARDS: Final = (
    # Bloodlines promo card (2026-09-08): printed in the Bloodlines layout
    # and outside the retail deck; dealt only with both
    # RulesetConfig(promo_cards=True) and bloodlines=True, since its Agent
    # box reads the Sardaukar Commanders. Transcribed from the card face.
    _entry(
        None,
        "ruthless-leadership",
        "Ruthless Leadership",
        4,
        requires=frozenset({GameOption.PROMO_CARDS, GameOption.BLOODLINES}),
        factions=(Faction.EMPEROR,),
        # Blue circle (City) and yellow triangle (Spice Trade), checked
        # against assets/icons/agent_icon_*.png: the Emperor icon is the
        # helmet, which this card does not print.
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        reveal_strength=1,
        # "Command (6+): Combat icon" — deploy in this Reveal as though at a
        # Combat space [Bloodlines p. 5] once the Reveal generates six or
        # more Persuasion [Bloodlines pp. 5, 12].
        play_data_complete=True,
    ),
    # Bloodlines Imperium cards (2026-09-07): 25 retail + 5 CHOAM-only + 2
    # Tech-only [Bloodlines pp. 2-3]; copies from the Dune Cards Hub catalog.
    # Play data is transcribed from the card faces slice by slice; a card
    # whose data is not complete yet stays out of the deck (see
    # ``imperium_cards_for_choam``).
    _entry(
        88,
        "arrakis-observer",
        "Arrakis Observer",
        3,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(
        89,
        "bombast",
        "Bombast",
        1,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.LANDSRAAD,),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(
        90,
        "choam-demands",
        "CHOAM Demands",
        6,
        requires=frozenset({GameOption.CHOAM_MODULE, GameOption.BLOODLINES}),
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        play_data_complete=True,
    ),
    _entry(
        91,
        "command-center",
        "Command Center",
        3,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.CITY),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(
        92,
        "corrupt-bureaucrat",
        "Corrupt Bureaucrat",
        4,
        requires=frozenset({GameOption.CHOAM_MODULE, GameOption.BLOODLINES}),
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.SPACING_GUILD, AgentIcon.LANDSRAAD, AgentIcon.SPY),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    _entry(
        94,
        "delivery-logistics",
        "Delivery Logistics",
        2,
        copies=2,
        requires=frozenset({GameOption.CHOAM_MODULE, GameOption.BLOODLINES}),
        factions=(Faction.SPACING_GUILD,),
        agent_icons_from_contracts=True,
        play_data_complete=True,
    ),
    _entry(
        95,
        "disruption-tactics",
        "Disruption Tactics",
        2,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(
        96,
        "eliminate-allies",
        "Eliminate Allies",
        2,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.SPY,),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        97,
        "elite-forces",
        "Elite Forces",
        3,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.EMPEROR, Faction.SPACING_GUILD),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.SPACING_GUILD),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        98,
        "engineered-miracle",
        "Engineered Miracle",
        3,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(
        99,
        "fremen-war-name",
        "Fremen War Name",
        4,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.SPICE_TRADE),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    _entry(
        99,
        "holy-war",
        "Holy War",
        5,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.FREMEN,),
        agent_icons=(
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.LANDSRAAD,
        ),
        play_data_complete=True,
    ),
    _entry(
        101,
        "i-believe",
        "I Believe",
        3,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(
        102,
        "imperial-throneship",
        "Imperial Throneship",
        7,
        requires=frozenset({GameOption.BLOODLINES}),
        has_acquisition_bonus=True,
        factions=(Faction.EMPEROR,),
        agent_icons=(
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.LANDSRAAD,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
        ),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    _entry(
        104,
        "intelligence-training",
        "Intelligence Training",
        3,
        copies=2,
        requires=frozenset({GameOption.BLOODLINES}),
        has_acquisition_bonus=True,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    # Ixian Ambassador (Tech Module, card face): no Faction, Landsraad icon.
    # Agent: 1 spice. Reveal: 1 Persuasion; "If you have two or more Tech
    # tiles: gain 1 Influence of your choice".
    _entry(
        106,
        "ixian-ambassador",
        "Ixian Ambassador",
        4,
        copies=2,
        requires=frozenset({GameOption.BLOODLINES, GameOption.TECH_MODULE}),
        agent_icons=(AgentIcon.LANDSRAAD,),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(
        107,
        "litany-against-fear",
        "Litany Against Fear",
        3,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.BENE_GESSERIT,),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    _entry(
        108,
        "mercantile-affairs",
        "Mercantile Affairs",
        5,
        requires=frozenset({GameOption.CHOAM_MODULE, GameOption.BLOODLINES}),
        has_acquisition_bonus=True,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(
            AgentIcon.BENE_GESSERIT,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
            AgentIcon.SPY,
        ),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    _entry(
        77,
        "pointing-the-way",
        "Pointing the Way",
        6,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        reveal_strength=2,
        play_data_complete=True,
    ),
    _entry(
        78,
        "possible-futures",
        "Possible Futures",
        8,
        requires=frozenset({GameOption.BLOODLINES}),
        has_acquisition_bonus=True,
        factions=(Faction.BENE_GESSERIT, Faction.FREMEN),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    _entry(
        80,
        "quash-rebellion",
        "Quash Rebellion",
        5,
        copies=2,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.SPACING_GUILD, AgentIcon.LANDSRAAD),
        reveal_strength=2,
        play_data_complete=True,
    ),
    _entry(
        82,
        "sandwalk",
        "Sandwalk",
        1,
        copies=2,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.SPICE_TRADE,),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        83,
        "sardaukar-standard",
        "Sardaukar Standard",
        4,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.CITY),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    _entry(
        86,
        "shrouded-counsel",
        "Shrouded Counsel",
        4,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.SPY,),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(
        87,
        "southern-faith",
        "Southern Faith",
        5,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.BENE_GESSERIT, Faction.FREMEN),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY),
        reveal_persuasion=1,
        reveal_strength=2,
        play_data_complete=True,
    ),
    _entry(
        85,
        "urgent-shigawire",
        "Urgent Shigawire",
        2,
        copies=2,
        requires=frozenset({GameOption.BLOODLINES}),
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.BENE_GESSERIT, AgentIcon.CITY),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
)
