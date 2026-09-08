"""The Tleilaxu deck, Reclaimed Forces, and their play data [Immortality pp. 8-9].

Tleilaxu cards "are similar to Imperium cards. You acquire them during your
Reveal turn ... You play them during an Agent turn or reveal them during a
Reveal turn. However, Tleilaxu cards come from the Tleilaxu Row and cost
specimens to acquire rather than persuasion" [Immortality p. 8]. They are
therefore ``ImperiumCardEntry`` records with a specimen cost instead of a
Persuasion cost, resolved from ``tleilaxu:<card>:<copy>`` instance IDs.

Identities and copies: the rulebook's 18 Tleilaxu deck cards plus the
Reclaimed Forces reserve card [Immortality p. 3]; the Dune Cards Hub catalog
lists one copy of each. Printed text is transcribed from the card faces
(asset repository ``cards/en/immortality/tleilaxu/``) slice by slice; a card
whose play data is not complete stays out of the deck.
"""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import (
    CardDefinition,
    SourceDocument,
    SourceRef,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import ImperiumCardEntry
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAcquisitionEffect,
    PersonalCardAgentEffect,
    PersonalCardRevealEffect,
)

TLEILAXU_SOURCES: Final = (
    SourceRef(SourceDocument.IMMORTALITY_RULEBOOK, (3, 8, 9)),
    SourceRef(SourceDocument.CARD_FACE, (1,)),
)
# Piter, Genius Advisor appears in no official document; the card face is
# the source.
PROMO_SOURCES: Final = (SourceRef(SourceDocument.CARD_FACE, (1,)),)


@dataclass(frozen=True, slots=True)
class TleilaxuCardEntry(ImperiumCardEntry):
    """One Tleilaxu card: an Imperium-style card bought with specimens."""

    # "paying the specimen cost shown in the top right corner" [Immortality
    # p. 8].
    specimen_cost: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.specimen_cost < 1:
            raise ValueError("Tleilaxu cards cost at least one specimen")
        if self.acquisition_cost is not None:
            raise ValueError("Tleilaxu cards have no Persuasion cost")


def _entry(
    catalog_id: int | None,
    slug: str,
    name: str,
    specimen_cost: int,
    *,
    promo: bool = False,
    graft: bool = False,
    factions: tuple[Faction, ...] = (),
    agent_icons: tuple[AgentIcon, ...] = (),
    agent_effect: PersonalCardAgentEffect | None = None,
    acquisition_effect: PersonalCardAcquisitionEffect | None = None,
    reveal_persuasion: int = 0,
    reveal_strength: int = 0,
    reveal_effects: tuple[PersonalCardRevealEffect, ...] = (),
    play_data_complete: bool = False,
) -> TleilaxuCardEntry:
    return TleilaxuCardEntry(
        card=CardDefinition(
            card_id=slug.replace("-", "_"),
            name=name,
            sources=PROMO_SOURCES if promo else TLEILAXU_SOURCES,
            catalog_url=(
                None
                if catalog_id is None
                else f"https://dunecardshub.com/cards/{catalog_id}/immortality-{slug}"
            ),
        ),
        promo=promo,
        immortality_only=True,
        specimen_cost=specimen_cost,
        graft=graft,
        factions=factions,
        agent_icons=agent_icons,
        agent_effect=agent_effect,
        acquisition_effect=acquisition_effect,
        has_acquisition_bonus=acquisition_effect is not None,
        reveal_persuasion=reveal_persuasion,
        reveal_strength=reveal_strength,
        reveal_effects=reveal_effects,
        play_data_complete=play_data_complete,
    )


# The 18 Tleilaxu deck cards [Immortality p. 3], in catalog order. Play data
# is transcribed from the card faces slice by slice.
TLEILAXU_CARDS: Final[tuple[TleilaxuCardEntry, ...]] = (
    _entry(403, "beguiling-pheromones", "Beguiling Pheromones", 3, graft=True),
    _entry(404, "chairdog", "Chairdog", 2, graft=True),
    # Contaminator (Fremen): Fremen icon; Agent: Tleilaxu; Reveal: 1
    # Persuasion [card face].
    _entry(
        405,
        "contaminator",
        "Contaminator",
        1,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN,),
        agent_effect=PersonalCardAgentEffect.ADVANCE_TLEILAXU,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Corrino Genes (Emperor): acquire box 2 Solari; Emperor icon; Agent:
    # "If grafted: Tleilaxu"; Reveal: 1 Persuasion [card face].
    _entry(
        406,
        "corrino-genes",
        "Corrino Genes",
        1,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR,),
        agent_effect=PersonalCardAgentEffect.ADVANCE_TLEILAXU_IF_GRAFTED,
        acquisition_effect=PersonalCardAcquisitionEffect.GAIN_TWO_SOLARI,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Face Dancer (Emperor, Guild, Fremen): three Faction icons; GRAFT: draw
    # a card; Reveal: 1 Persuasion [card face].
    _entry(
        407,
        "face-dancer",
        "Face Dancer",
        2,
        graft=True,
        factions=(Faction.EMPEROR, Faction.SPACING_GUILD, Faction.FREMEN),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.SPACING_GUILD, AgentIcon.FREMEN),
        agent_effect=PersonalCardAgentEffect.DRAW_PERSONAL_CARD,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Face Dancer Initiate (Emperor, Guild, Fremen): three Faction icons;
    # GRAFT with an empty box; Reveal: 1 Persuasion [card face].
    _entry(
        408,
        "face-dancer-initiate",
        "Face Dancer Initiate",
        1,
        graft=True,
        factions=(Faction.EMPEROR, Faction.SPACING_GUILD, Faction.FREMEN),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.SPACING_GUILD, AgentIcon.FREMEN),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # From the Tanks: Landsraad icon; Agent: 2 troops; Reveal: 1 Persuasion
    # [card face].
    _entry(
        409,
        "from-the-tanks",
        "From the Tanks",
        2,
        agent_icons=(AgentIcon.LANDSRAAD,),
        agent_effect=PersonalCardAgentEffect.RECRUIT_TWO_TROOPS,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(410, "ghola", "Ghola", 3, graft=True),
    _entry(411, "guild-impersonator", "Guild Impersonator", 2, graft=True),
    _entry(412, "industrial-espionage", "Industrial Espionage", 1),
    _entry(414, "scientific-breakthrough", "Scientific Breakthrough", 3),
    _entry(415, "slig-farmer", "Slig Farmer", 2, graft=True),
    _entry(416, "stitched-horror", "Stitched Horror", 3, graft=True),
    # Subject X-137: acquire box Tleilaxu; Landsraad and Spice Trade icons;
    # Agent: "[one genetic marker]: Tleilaxu"; Reveal: 1 Persuasion [card
    # face].
    _entry(
        417,
        "subject-x-137",
        "Subject X-137",
        2,
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.ADVANCE_TLEILAXU_IF_ONE_MARKER,
        acquisition_effect=PersonalCardAcquisitionEffect.ADVANCE_TLEILAXU,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Tleilaxu Infiltrator: City; GRAFT: enemy Agents do not block, draw a
    # card, and at two genetic markers an Intrigue card; Reveal: 1
    # Persuasion [card face].
    _entry(
        418,
        "tleilaxu-infiltrator",
        "Tleilaxu Infiltrator",
        2,
        graft=True,
        agent_icons=(AgentIcon.CITY,),
        agent_effect=PersonalCardAgentEffect.DRAW_ONE_AND_INTRIGUE_IF_TWO_MARKERS,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    # Twisted Mentat: Landsraad, City; GRAFT: may recall the Agent sent this
    # turn; Reveal: 1 Persuasion, 1 sword, a specimen [card face].
    _entry(
        419,
        "twisted-mentat",
        "Twisted Mentat",
        4,
        graft=True,
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY),
        agent_effect=PersonalCardAgentEffect.MAY_RECALL_AGENT_SENT_THIS_TURN,
        reveal_persuasion=1,
        reveal_strength=1,
        reveal_effects=(PersonalCardRevealEffect(specimens=1),),
        play_data_complete=True,
    ),
    # Unnatural Reflexes: Spice Trade; GRAFT: at one genetic marker draw two
    # cards; Reveal: 1 Persuasion, 1 sword [card face].
    _entry(
        420,
        "unnatural-reflexes",
        "Unnatural Reflexes",
        3,
        graft=True,
        agent_icons=(AgentIcon.SPICE_TRADE,),
        agent_effect=PersonalCardAgentEffect.DRAW_TWO_IF_ONE_MARKER,
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(421, "usurp", "Usurp", 4, graft=True),
    # Promo card in the Tleilaxu layout (asset repository
    # ``cards/en/immortality/promo/``): joins the Tleilaxu deck only with
    # ``promo_cards`` as well.
    _entry(None, "piter-genius-advisor", "Piter, Genius Advisor", 3, promo=True),
)
TLEILAXU_CARDS_BY_ID: Final = {entry.card.card_id: entry for entry in TLEILAXU_CARDS}

# "The Reclaimed Forces card is never removed from the Tleilaxu Row. When a
# player 'acquires' it, they choose one of its effects (to recruit two
# troops, or advance their Tleilaxu token one space on the Tleilaxu track),
# but leave the card in place" [Immortality p. 9]. Not a deck card: it never
# enters a player's deck, so it carries no play data.
RECLAIMED_FORCES: Final = TleilaxuCardEntry(
    card=CardDefinition(
        card_id="reclaimed_forces",
        name="Reclaimed Forces",
        sources=(
            SourceRef(SourceDocument.IMMORTALITY_RULEBOOK, (3, 4, 9)),
            SourceRef(SourceDocument.CARD_FACE, (1,)),
        ),
        catalog_url="https://dunecardshub.com/cards/413/immortality-reclaimed-forces",
    ),
    immortality_only=True,
    specimen_cost=3,
)


def tleilaxu_cards_for(promo_cards: bool = False) -> tuple[TleilaxuCardEntry, ...]:
    """Return the Tleilaxu deck entries the selected setup shuffles.

    Only cards with complete play data join the deck (an incomplete card
    would be inert in a hand); the promo needs ``promo_cards``.
    """

    return tuple(
        entry
        for entry in TLEILAXU_CARDS
        if entry.play_data_complete and (promo_cards or not entry.promo)
    )


def tleilaxu_deck_instance_ids(promo_cards: bool = False) -> tuple[str, ...]:
    """Return stable IDs for every physical Tleilaxu deck card copy."""

    return tuple(
        f"tleilaxu:{entry.card.card_id}:{copy}"
        for entry in tleilaxu_cards_for(promo_cards)
        for copy in range(entry.copies)
    )


def tleilaxu_card_for_instance(instance_id: str) -> TleilaxuCardEntry:
    """Resolve a stable Tleilaxu deck instance ID to its definition."""

    prefix = "tleilaxu:"
    if not instance_id.startswith(prefix):
        raise ValueError("not a Tleilaxu-card instance ID")
    try:
        card_id, copy_text = instance_id.removeprefix(prefix).rsplit(":", maxsplit=1)
        copy = int(copy_text)
        entry = TLEILAXU_CARDS_BY_ID[card_id]
    except (KeyError, ValueError) as error:
        raise ValueError("unknown Tleilaxu-card instance ID") from error
    if copy < 0 or copy >= entry.copies:
        raise ValueError("Tleilaxu-card copy index is out of range")
    return entry
