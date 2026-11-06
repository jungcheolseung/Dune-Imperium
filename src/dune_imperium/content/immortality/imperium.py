"""Immortality's Imperium cards for the Uprising-format deck (``immortality``).

Moved from ``content.uprising.imperium`` (docs/content-core-refactor-plan.md
8.3, user decision 2026-11-04); ``content.registry.imperium`` puts them after
Bloodlines' cards.
"""

from typing import Any, Final

from dune_imperium.content.core.cards import ImperiumCardEntry, imperium_card_entry
from dune_imperium.content.core.icons import AgentIcon, Faction
from dune_imperium.content.core.schema import GameOption, SourceDocument, SourceRef

# Immortality cards: the rulebook lists their count and setup [Immortality
# pp. 3-5]; the printed text comes from the card face.
IMMORTALITY_SOURCES: Final = (
    SourceRef(SourceDocument.IMMORTALITY_RULEBOOK, (3, 4, 5)),
    SourceRef(SourceDocument.CARD_FACE, (1,)),
)


def _entry(
    catalog_id: int | None,
    slug: str,
    name: str,
    acquisition_cost: int,
    **fields: Any,
) -> ImperiumCardEntry:
    return imperium_card_entry(
        catalog_id,
        slug,
        name,
        acquisition_cost,
        catalog_set="immortality",
        sources=IMMORTALITY_SOURCES,
        **fields,
    )


IMMORTALITY_IMPERIUM_CARDS: Final = (
    # Immortality Imperium cards (2026-09-08): 30 cards [Immortality p. 3].
    # Identities and copies follow the Dune Cards Hub catalog (25 identities,
    # 27 copies: Dissecting Kit and Tleilaxu Master twice), which is three
    # copies short of the rulebook's count; see docs/implementation-audits/
    # immortality.md. Play data is transcribed from the card faces slice by
    # slice; a card whose data is not complete stays out of the deck.
    # Bene Tleilax Lab: City, Spice Trade; Agent: a specimen; Reveal: 1
    # Persuasion, +1 spice at one genetic marker [card face].
    _entry(
        367,
        "bene-tleilax-lab",
        "Bene Tleilax Lab",
        2,
        requires=frozenset({GameOption.IMMORTALITY}),
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Bene Tleilax Researcher: Landsraad; GRAFT: Research; Reveal: 1
    # Persuasion, +1 at one genetic marker, +1 more at two [card face].
    _entry(
        368,
        "bene-tleilax-researcher",
        "Bene Tleilax Researcher",
        4,
        requires=frozenset({GameOption.IMMORTALITY}),
        graft=True,
        agent_icons=(AgentIcon.LANDSRAAD,),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Blank Slate: Landsraad, City, Spice Trade; "If grafted: this has" the
    # four Faction icons (``effective_agent_icons``); Reveal: 1 Persuasion.
    _entry(
        369,
        "blank-slate",
        "Blank Slate",
        1,
        requires=frozenset({GameOption.IMMORTALITY}),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Clandestine Meeting (Bene Gesserit): no Agent icons (played grafted
    # [Immortality p. 14]); Agent: Bene Gesserit Influence and an Intrigue
    # card; Reveal: 2 Persuasion [card face].
    _entry(
        370,
        "clandestine-meeting",
        "Clandestine Meeting",
        4,
        requires=frozenset({GameOption.IMMORTALITY}),
        factions=(Faction.BENE_GESSERIT,),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    # Corrupt Smuggler (Guild, Fremen): Guild, Spice Trade; Agent: "If
    # grafted: 2 spice"; Reveal: 1 Persuasion, 1 sword [card face].
    _entry(
        371,
        "corrupt-smuggler",
        "Corrupt Smuggler",
        3,
        requires=frozenset({GameOption.IMMORTALITY}),
        factions=(Faction.SPACING_GUILD, Faction.FREMEN),
        agent_icons=(AgentIcon.SPACING_GUILD, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    # Dissecting Kit (no Faction, Graft): Landsraad, City; Agent: "Trash the
    # other grafted card -> a specimen"; Reveal: 1 Persuasion and "[one
    # genetic marker]: Tleilaxu" [card face].
    _entry(
        372,
        "dissecting-kit",
        "Dissecting Kit",
        2,
        copies=2,
        requires=frozenset({GameOption.IMMORTALITY}),
        graft=True,
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # For Humanity (Bene Gesserit): BG, Landsraad, Spice Trade; Agent:
    # Influence of your choice; Reveal: 2 Persuasion and "Bene Gesserit
    # Alliance: lose two Influence (one Faction) -> 1 Victory Point" [card
    # face: a "?" diamond with two red chevrons].
    _entry(
        373,
        "for-humanity",
        "For Humanity",
        7,
        requires=frozenset({GameOption.IMMORTALITY}),
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(
            AgentIcon.BENE_GESSERIT,
            AgentIcon.LANDSRAAD,
            AgentIcon.SPICE_TRADE,
        ),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    # High Priority Travel (Spacing Guild): Landsraad, Spice Trade; Agent:
    # "[Guild] 2 Influence: draw a card —OR— Combat"; Reveal: 1 Persuasion
    # and 1 Solari [card face].
    _entry(
        374,
        "high-priority-travel",
        "High Priority Travel",
        1,
        copies=2,
        requires=frozenset({GameOption.IMMORTALITY}),
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Imperium Ceremony (Emperor, Spacing Guild): Emperor, Guild, Landsraad;
    # Agent: "Look at the top two cards of the Intrigue deck. Keep one and
    # put the other back on top"; Reveal: 3 Persuasion [card face].
    _entry(
        375,
        "imperium-ceremony",
        "Imperium Ceremony",
        6,
        requires=frozenset({GameOption.IMMORTALITY}),
        factions=(Faction.EMPEROR, Faction.SPACING_GUILD),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.SPACING_GUILD, AgentIcon.LANDSRAAD),
        reveal_persuasion=3,
        play_data_complete=True,
    ),
    # Interstellar Conspiracy (no Faction, Graft): City; Agent: "1 spice
    # —AND— If grafted with an Emperor or Spacing Guild card: Influence of
    # your choice"; Reveal: 2 Persuasion [card face].
    _entry(
        376,
        "interstellar-conspiracy",
        "Interstellar Conspiracy",
        4,
        requires=frozenset({GameOption.IMMORTALITY}),
        graft=True,
        agent_icons=(AgentIcon.CITY,),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    # Keys to Power (Guild, Bene Gesserit): Guild, BG, Landsraad; Agent:
    # "[Emperor] 2 Influence: 2 spice"; Reveal: 2 Persuasion [card face].
    _entry(
        377,
        "keys-to-power",
        "Keys to Power",
        5,
        requires=frozenset({GameOption.IMMORTALITY}),
        factions=(Faction.SPACING_GUILD, Faction.BENE_GESSERIT),
        agent_icons=(
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.LANDSRAAD,
        ),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    # Lisan al Gaib (Bene Gesserit, Fremen): acquire box 1 spice; Fremen,
    # City, Spice Trade; Agent: with another Bene Gesserit card in play,
    # Fremen Influence; Reveal: 1 Persuasion, Fremen Bond 2 swords.
    _entry(
        378,
        "lisan-al-gaib",
        "Lisan al Gaib",
        4,
        requires=frozenset({GameOption.IMMORTALITY}),
        has_acquisition_bonus=True,
        factions=(Faction.BENE_GESSERIT, Faction.FREMEN),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Long Reach (Bene Gesserit): with another Bene Gesserit card in play
    # the greyed Landsraad, City and Spice Trade icons; Agent: choose two
    # Faction Influences; Reveal: 1 Persuasion, an Intrigue card.
    _entry(
        379,
        "long-reach",
        "Long Reach",
        6,
        requires=frozenset({GameOption.IMMORTALITY}),
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Occupation (Guild): acquire box 3 troops; the four Faction icons plus
    # City and Spice Trade; Agent: draw a card and the Combat icon; Reveal:
    # 1 water, 1 spice, 1 troop [card face].
    _entry(
        380,
        "occupation",
        "Occupation",
        8,
        requires=frozenset({GameOption.IMMORTALITY}),
        has_acquisition_bonus=True,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.FREMEN,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
        ),
        play_data_complete=True,
    ),
    # Organ Merchants: City, Spice Trade; Agent: "specimen -> 4 Solari";
    # Reveal: 1 Persuasion, 1 Solari [card face].
    _entry(
        381,
        "organ-merchants",
        "Organ Merchants",
        3,
        requires=frozenset({GameOption.IMMORTALITY}),
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Planned Coupling (Bene Gesserit): BG icon; GRAFT: draw a card;
    # Reveal: 1 Persuasion [card face].
    _entry(
        382,
        "planned-coupling",
        "Planned Coupling",
        3,
        copies=2,
        requires=frozenset({GameOption.IMMORTALITY}),
        graft=True,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.BENE_GESSERIT,),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Replacement Eyes: City; GRAFT: "When this card is trashed: Tleilaxu";
    # "[trash] -> draw a card"; Reveal: 1 Persuasion, 1 sword [card face].
    _entry(
        383,
        "replacement-eyes",
        "Replacement Eyes",
        5,
        requires=frozenset({GameOption.IMMORTALITY}),
        graft=True,
        agent_icons=(AgentIcon.CITY,),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    # Sardaukar Quartermaster (Emperor): Landsraad, City; Agent: "If grafted:
    # troop, draw a card"; Reveal: 1 Persuasion, 2 swords [card face].
    _entry(
        384,
        "sardaukar-quartermaster",
        "Sardaukar Quartermaster",
        2,
        requires=frozenset({GameOption.IMMORTALITY}),
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY),
        reveal_persuasion=1,
        reveal_strength=2,
        play_data_complete=True,
    ),
    # Shadout Mapes (Fremen): Fremen, Spice Trade; no Agent box; Reveal: 1
    # Persuasion, 1 sword and "You may deploy or retreat one troop" [card
    # face].
    _entry(
        385,
        "shadout-mapes",
        "Shadout Mapes",
        2,
        requires=frozenset({GameOption.IMMORTALITY}),
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    # Show of Strength (Emperor, Fremen): with more deployed troops than
    # each opponent the greyed Landsraad and Spice Trade icons; Agent: draw
    # two cards; Reveal: 1 Persuasion, 2 swords [card face].
    _entry(
        386,
        "show-of-strength",
        "Show of Strength",
        3,
        requires=frozenset({GameOption.IMMORTALITY}),
        factions=(Faction.EMPEROR, Faction.FREMEN),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        reveal_strength=2,
        play_data_complete=True,
    ),
    # Spiritual Fervor: acquire box Research; Spice Trade; empty Agent box;
    # Reveal: 1 Persuasion, a specimen [card face].
    _entry(
        387,
        "spiritual-fervor",
        "Spiritual Fervor",
        3,
        copies=2,
        requires=frozenset({GameOption.IMMORTALITY}),
        has_acquisition_bonus=True,
        agent_icons=(AgentIcon.SPICE_TRADE,),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Stillsuit Manufacturer (Fremen): Fremen, City; Agent: water —AND—
    # Fremen Alliance: return this card from play to your hand; Reveal: 1
    # Persuasion —AND— Fremen Bond: 2 spice [card face].
    _entry(
        388,
        "stillsuit-manufacturer",
        "Stillsuit Manufacturer",
        5,
        requires=frozenset({GameOption.IMMORTALITY}),
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Throne Room Politics (Emperor, Bene Gesserit): Emperor; Agent: a troop
    # and a trash icon; Reveal: 1 Persuasion, Bene Gesserit Influence.
    _entry(
        389,
        "throne-room-politics",
        "Throne Room Politics",
        4,
        requires=frozenset({GameOption.IMMORTALITY}),
        factions=(Faction.EMPEROR, Faction.BENE_GESSERIT),
        agent_icons=(AgentIcon.EMPEROR,),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Tleilaxu Master (no Faction): Landsraad, Spice Trade; Agent: "[one
    # genetic marker]: you may acquire a card costing 6 or less. [two
    # markers]: put that card in your hand"; Reveal: 1 Persuasion and two
    # Research icons [card face].
    _entry(
        390,
        "tleilaxu-master",
        "Tleilaxu Master",
        5,
        copies=2,
        requires=frozenset({GameOption.IMMORTALITY}),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.SPICE_TRADE),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Tleilaxu Surgeon (no Faction): Emperor, City; Agent: "2 specimens ->
    # Tleilaxu Tleilaxu"; Reveal: 2 Persuasion and "Lose two troops -> two
    # specimens" [card face].
    _entry(
        391,
        "tleilaxu-surgeon",
        "Tleilaxu Surgeon",
        3,
        requires=frozenset({GameOption.IMMORTALITY}),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.CITY),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
)
