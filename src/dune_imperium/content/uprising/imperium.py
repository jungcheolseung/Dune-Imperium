"""Typed identities and transcribed play data for the Uprising Imperium deck."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import (
    CardDefinition,
    DeckCardEntry,
    SourceDocument,
    SourceRef,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAcquisitionEffect,
    PersonalCardAgentEffect,
    PersonalCardBond,
    PersonalCardDiscardEffect,
    PersonalCardRevealAcquisitionEffect,
    PersonalCardRevealChoiceEffect,
    PersonalCardRevealEffect,
    PersonalCardTrashEffect,
    PersonalCardTurnStartEffect,
)

BASE_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4)),)
CHOAM_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4, 16)),)
# Promo cards appear in no official document; the card face is the source.
PROMO_SOURCES: Final = (SourceRef(SourceDocument.CARD_FACE, (1,)),)
# Bloodlines cards: the rulebook lists their counts and setup [Bloodlines
# pp. 2-3]; the printed text comes from the card face.
BLOODLINES_SOURCES: Final = (
    SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (2, 3)),
    SourceRef(SourceDocument.CARD_FACE, (1,)),
)


@dataclass(frozen=True, slots=True)
class ImperiumCardEntry(DeckCardEntry):
    """One shared-deck card plus independently verified play-facing data."""

    factions: tuple[Faction, ...] = ()
    agent_icons: tuple[AgentIcon, ...] = ()
    agent_effect: PersonalCardAgentEffect | None = None
    agent_spy_factions: tuple[Faction, ...] = ()
    ignores_influence_requirements: bool = False
    allows_recruited_troop_deployment: bool = False
    acquisition_effect: PersonalCardAcquisitionEffect | None = None
    discard_effect: PersonalCardDiscardEffect | None = None
    reveal_acquisition_effect: PersonalCardRevealAcquisitionEffect | None = None
    trash_effect: PersonalCardTrashEffect | None = None
    reveal_persuasion: int = 0
    reveal_strength: int = 0
    reveal_effects: tuple[PersonalCardRevealEffect, ...] = ()
    reveal_choice_effects: tuple[PersonalCardRevealChoiceEffect, ...] = ()
    play_data_complete: bool = False
    # Delivery Logistics: its Agent icons are those of the owner's
    # incomplete Contracts, judged when the card is played.
    agent_icons_from_contracts: bool = False
    # Litany Against Fear: the card's turn-start alternative.
    turn_start_effect: PersonalCardTurnStartEffect | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if len(self.factions) != len(set(self.factions)):
            raise ValueError("Imperium-card Factions must be unique")
        if len(self.agent_icons) != len(set(self.agent_icons)):
            raise ValueError("Imperium-card Agent icons must be unique")
        if len(self.agent_spy_factions) != len(set(self.agent_spy_factions)):
            raise ValueError("Imperium-card Spy target Factions must be unique")
        if not isinstance(self.ignores_influence_requirements, bool):
            raise TypeError("Influence-requirement override must be a boolean")
        if not isinstance(self.allows_recruited_troop_deployment, bool):
            raise TypeError("recruited-troop deployment permission must be a boolean")
        if self.agent_spy_factions and (
            self.agent_effect is not PersonalCardAgentEffect.PLACE_SPY
        ):
            raise ValueError("Spy target Factions require a place-Spy Agent effect")
        if min(self.reveal_persuasion, self.reveal_strength) < 0:
            raise ValueError("Imperium-card Reveal values must not be negative")
        if len(self.reveal_effects) != len(set(self.reveal_effects)):
            raise ValueError("Imperium-card Reveal effects must be unique")
        if len(self.reveal_choice_effects) != len(set(self.reveal_choice_effects)):
            raise ValueError("Imperium-card Reveal choices must be unique")
        if self.acquisition_effect is not None and not self.has_acquisition_bonus:
            raise ValueError("typed acquisition effect requires an acquisition bonus")
        if not self.play_data_complete and (
            self.factions
            or self.agent_icons
            or self.agent_effect is not None
            or self.agent_spy_factions
            or self.ignores_influence_requirements
            or self.allows_recruited_troop_deployment
            or self.acquisition_effect is not None
            or self.discard_effect is not None
            or self.reveal_acquisition_effect is not None
            or self.trash_effect is not None
            or self.reveal_persuasion
            or self.reveal_strength
            or self.reveal_effects
            or self.reveal_choice_effects
        ):
            raise ValueError("partial Imperium-card play data must not be exposed")


def _entry(
    catalog_id: int | None,
    slug: str,
    name: str,
    acquisition_cost: int,
    *,
    copies: int = 1,
    choam_only: bool = False,
    promo: bool = False,
    bloodlines_only: bool = False,
    tech_only: bool = False,
    has_acquisition_bonus: bool = False,
    factions: tuple[Faction, ...] = (),
    agent_icons: tuple[AgentIcon, ...] = (),
    agent_effect: PersonalCardAgentEffect | None = None,
    agent_spy_factions: tuple[Faction, ...] = (),
    ignores_influence_requirements: bool = False,
    allows_recruited_troop_deployment: bool = False,
    acquisition_effect: PersonalCardAcquisitionEffect | None = None,
    discard_effect: PersonalCardDiscardEffect | None = None,
    reveal_acquisition_effect: PersonalCardRevealAcquisitionEffect | None = None,
    trash_effect: PersonalCardTrashEffect | None = None,
    reveal_persuasion: int = 0,
    reveal_strength: int = 0,
    reveal_effects: tuple[PersonalCardRevealEffect, ...] = (),
    reveal_choice_effects: tuple[PersonalCardRevealChoiceEffect, ...] = (),
    play_data_complete: bool = False,
    agent_icons_from_contracts: bool = False,
    turn_start_effect: PersonalCardTurnStartEffect | None = None,
) -> ImperiumCardEntry:
    return ImperiumCardEntry(
        card=CardDefinition(
            card_id=slug.replace("-", "_"),
            name=name,
            sources=(
                PROMO_SOURCES
                if promo
                else BLOODLINES_SOURCES
                if bloodlines_only
                else CHOAM_SOURCES
                if choam_only
                else BASE_SOURCES
            ),
            catalog_url=(
                None
                if catalog_id is None
                else f"https://dunecardshub.com/cards/{catalog_id}/"
                f"{'bloodlines' if bloodlines_only else 'uprising'}-{slug}"
            ),
        ),
        copies=copies,
        choam_only=choam_only,
        promo=promo,
        bloodlines_only=bloodlines_only,
        tech_only=tech_only,
        acquisition_cost=acquisition_cost,
        has_acquisition_bonus=has_acquisition_bonus,
        factions=factions,
        agent_icons=agent_icons,
        agent_effect=agent_effect,
        agent_spy_factions=agent_spy_factions,
        ignores_influence_requirements=ignores_influence_requirements,
        allows_recruited_troop_deployment=allows_recruited_troop_deployment,
        acquisition_effect=acquisition_effect,
        discard_effect=discard_effect,
        reveal_acquisition_effect=reveal_acquisition_effect,
        trash_effect=trash_effect,
        reveal_persuasion=reveal_persuasion,
        reveal_strength=reveal_strength,
        reveal_effects=reveal_effects,
        reveal_choice_effects=reveal_choice_effects,
        play_data_complete=play_data_complete,
        agent_icons_from_contracts=agent_icons_from_contracts,
        turn_start_effect=turn_start_effect,
    )


IMPERIUM_CARDS: Final = (
    _entry(
        30,
        "bene-gesserit-operative",
        "Bene Gesserit Operative",
        3,
        copies=2,
        agent_icons=(AgentIcon.BENE_GESSERIT,),
        agent_effect=PersonalCardAgentEffect.PLACE_SPY,
        reveal_persuasion=1,
        reveal_effects=(
            PersonalCardRevealEffect(
                persuasion=2,
                minimum_spies_placed=2,
            ),
        ),
        play_data_complete=True,
    ),
    _entry(
        45,
        "branching-path",
        "Branching Path",
        3,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.BENE_GESSERIT, AgentIcon.LANDSRAAD),
        agent_effect=(
            PersonalCardAgentEffect.MAY_TRASH_FOR_INTRIGUE_AND_TWO_TROOPS_IF_BENE_GESSERIT_ALLIANCE
        ),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    _entry(
        42,
        "calculus-of-power",
        "Calculus of Power",
        3,
        copies=2,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.SPY),
        agent_effect=PersonalCardAgentEffect.TRASH_SELF,
        reveal_persuasion=2,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH,
        ),
        play_data_complete=True,
    ),
    _entry(
        61,
        "captured-mentat",
        "Captured Mentat",
        5,
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.SPICE_TRADE),
        agent_effect=(
            PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD
        ),
        reveal_persuasion=1,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE,
        ),
        play_data_complete=True,
    ),
    _entry(
        181,
        "cargo-runner",
        "Cargo Runner",
        3,
        choam_only=True,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=(
            PersonalCardAgentEffect.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO
        ),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(
        67,
        "chani-clever-tactician",
        "Chani, Clever Tactician",
        5,
        factions=(Faction.FREMEN,),
        agent_icons=(
            AgentIcon.SPACING_GUILD,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
        ),
        agent_effect=(PersonalCardAgentEffect.DRAW_INTRIGUE_IF_THREE_UNITS_IN_CONFLICT),
        reveal_effects=(
            PersonalCardRevealEffect(
                persuasion=2,
                required_faction_bond=PersonalCardBond.FREMEN,
            ),
        ),
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH,
        ),
        play_data_complete=True,
    ),
    _entry(
        69,
        "corrinth-city",
        "Corrinth City",
        6,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.LANDSRAAD),
        agent_effect=(
            PersonalCardAgentEffect.MAY_DISCARD_TWO_AND_PAY_FIVE_SOLARI_FOR_VP
        ),
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL,
        ),
        play_data_complete=True,
    ),
    _entry(
        35,
        "covert-operation",
        "Covert Operation",
        3,
        agent_icons=(AgentIcon.SPY,),
        agent_effect=PersonalCardAgentEffect.EACH_OPPONENT_DISCARDS_PERSONAL_CARD,
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    _entry(
        44,
        "dangerous-rhetoric",
        "Dangerous Rhetoric",
        3,
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.SPY),
        agent_effect=(PersonalCardAgentEffect.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        182,
        "delivery-agreement",
        "Delivery Agreement",
        5,
        choam_only=True,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.CITY,),
        agent_effect=PersonalCardAgentEffect.MAY_DISCARD_TO_TAKE_CONTRACT,
        reveal_effects=(PersonalCardRevealEffect(spice=1),),
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS,
        ),
        play_data_complete=True,
    ),
    _entry(
        71,
        "desert-power",
        "Desert Power",
        6,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.SPICE_TRADE,),
        agent_effect=PersonalCardAgentEffect.GAIN_TWO_SPICE_IF_MAKER_SPACE,
        reveal_persuasion=2,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM,
        ),
        play_data_complete=True,
    ),
    _entry(
        27,
        "desert-survival",
        "Desert Survival",
        2,
        copies=2,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.SPICE_TRADE,),
        agent_effect=PersonalCardAgentEffect.TRASH_PERSONAL_CARD,
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        37,
        "double-agent",
        "Double Agent",
        3,
        copies=2,
        factions=(Faction.EMPEROR, Faction.SPACING_GUILD),
        agent_icons=(
            AgentIcon.LANDSRAAD,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
        ),
        agent_effect=(
            PersonalCardAgentEffect.PLACE_SPY_ALLOW_SHARED_IF_SPYING_ON_VISITED_SPACE
        ),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        46,
        "ecological-testing-station",
        "Ecological Testing Station",
        3,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY),
        agent_effect=PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO,
        reveal_persuasion=1,
        reveal_effects=(
            PersonalCardRevealEffect(
                water=1,
                required_faction_bond=PersonalCardBond.FREMEN,
            ),
        ),
        play_data_complete=True,
    ),
    _entry(
        23,
        "fedaykin-stilltent",
        "Fedaykin Stilltent",
        2,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.SPICE_TRADE,),
        agent_effect=PersonalCardAgentEffect.RECRUIT_ONE_IF_MAKER_SPACE,
        reveal_effects=(PersonalCardRevealEffect(water=1),),
        play_data_complete=True,
    ),
    _entry(
        38,
        "guild-envoy",
        "Guild Envoy",
        3,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.FREMEN,
        ),
        agent_effect=(PersonalCardAgentEffect.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(
        43,
        "guild-spy",
        "Guild Spy",
        3,
        has_acquisition_bonus=True,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.SPY,),
        agent_effect=(
            PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD
        ),
        acquisition_effect=PersonalCardAcquisitionEffect.PLACE_SPY,
        reveal_persuasion=2,
        reveal_acquisition_effect=(
            PersonalCardRevealAcquisitionEffect.GAIN_INFLUENCE_FOR_EACH_SPIED_FACTION_ON_SPICE_MUST_FLOW
        ),
        play_data_complete=True,
    ),
    _entry(
        21,
        "hidden-missive",
        "Hidden Missive",
        2,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.LANDSRAAD,),
        agent_effect=(
            PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO
        ),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        24,
        "imperial-spymaster",
        "Imperial Spymaster",
        2,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.SPY),
        agent_effect=(PersonalCardAgentEffect.DRAW_INTRIGUE_IF_SPY_RECALLED_THIS_TURN),
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        64,
        "in-high-places",
        "In High Places",
        5,
        has_acquisition_bonus=True,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.BENE_GESSERIT, AgentIcon.EMPEROR),
        agent_effect=PersonalCardAgentEffect.GAIN_WATER_IF_BENE_GESSERIT_BOND,
        acquisition_effect=PersonalCardAcquisitionEffect.PLACE_SPY,
        reveal_persuasion=2,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_RECALL_TWO_SPIES_FOR_TWO_PERSUASION,
        ),
        play_data_complete=True,
    ),
    _entry(
        184,
        "interstellar-trade",
        "Interstellar Trade",
        7,
        choam_only=True,
        has_acquisition_bonus=True,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE,
        acquisition_effect=PersonalCardAcquisitionEffect.TAKE_CONTRACT,
        reveal_effects=(PersonalCardRevealEffect(persuasion_per_completed_contract=1),),
        play_data_complete=True,
    ),
    _entry(
        68,
        "junction-headquarters",
        "Junction Headquarters",
        6,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=(
            PersonalCardAgentEffect.MAY_TRASH_INTRIGUE_AND_PAY_TWO_SPICE_FOR_VP_IF_SPACING_GUILD_ALLIANCE
        ),
        reveal_persuasion=1,
        reveal_effects=(PersonalCardRevealEffect(water=1, recruit_troops=1),),
        play_data_complete=True,
    ),
    _entry(
        63,
        "leadership",
        "Leadership",
        5,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.DRAW_PER_SANDWORM_IN_CONFLICT,
        reveal_persuasion=2,
        reveal_strength=1,
        reveal_effects=(PersonalCardRevealEffect(strength_per_other_sword_card=1),),
        play_data_complete=True,
    ),
    _entry(
        74,
        "long-live-the-fighters",
        "Long Live the Fighters",
        7,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY),
        agent_effect=PersonalCardAgentEffect.LOOK_AT_TOP_THREE,
        reveal_persuasion=2,
        reveal_strength=3,
        play_data_complete=True,
    ),
    _entry(
        19,
        "maker-keeper",
        "Maker Keeper",
        2,
        copies=2,
        factions=(Faction.BENE_GESSERIT, Faction.FREMEN),
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=(
            PersonalCardAgentEffect.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO
        ),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    _entry(
        32,
        "maula-pistol",
        "Maula Pistol",
        3,
        copies=2,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.DRAW_PERSONAL_CARD,
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        34,
        "northern-watermaster",
        "Northern Watermaster",
        3,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.CITY,),
        agent_effect=PersonalCardAgentEffect.GAIN_WATER,
        reveal_persuasion=1,
        reveal_effects=(
            PersonalCardRevealEffect(
                spice=2,
                required_faction_bond=PersonalCardBond.FREMEN,
            ),
        ),
        play_data_complete=True,
    ),
    _entry(
        75,
        "overthrow",
        "Overthrow",
        8,
        has_acquisition_bonus=True,
        factions=(Faction.EMPEROR,),
        agent_icons=(
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.FREMEN,
        ),
        agent_effect=PersonalCardAgentEffect.GAIN_VISITED_FACTION_INFLUENCE,
        acquisition_effect=PersonalCardAcquisitionEffect.DRAW_INTRIGUE_CARD,
        reveal_persuasion=2,
        reveal_strength=2,
        reveal_effects=(PersonalCardRevealEffect(recruit_troops=1),),
        play_data_complete=True,
    ),
    _entry(
        49,
        "paracompass",
        "Paracompass",
        4,
        agent_icons=(AgentIcon.CITY,),
        agent_effect=PersonalCardAgentEffect.GAIN_TWO_SOLARI,
        reveal_effects=(
            PersonalCardRevealEffect(
                persuasion=2,
                requires_high_council=True,
            ),
            PersonalCardRevealEffect(
                persuasion=1,
                requires_high_council=True,
                requires_swordmaster=True,
            ),
        ),
        play_data_complete=True,
    ),
    _entry(
        73,
        "price-is-no-object",
        "Price is No Object",
        6,
        has_acquisition_bonus=True,
        factions=(Faction.EMPEROR, Faction.BENE_GESSERIT),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.BENE_GESSERIT),
        agent_effect=PersonalCardAgentEffect.ACQUIRE_WITH_SOLARI_TO_HAND,
        acquisition_effect=PersonalCardAcquisitionEffect.GAIN_TWO_SOLARI,
        reveal_persuasion=2,
        reveal_effects=(PersonalCardRevealEffect(solari=2),),
        play_data_complete=True,
    ),
    _entry(
        183,
        "priority-contracts",
        "Priority Contracts",
        6,
        choam_only=True,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.TAKE_CONTRACT,
        reveal_effects=(PersonalCardRevealEffect(spice=2),),
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS,
        ),
        play_data_complete=True,
    ),
    _entry(
        55,
        "public-spectacle",
        "Public Spectacle",
        4,
        copies=2,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.SPY,),
        agent_effect=(
            PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN
        ),
        reveal_persuasion=1,
        reveal_choice_effects=(PersonalCardRevealChoiceEffect.PLACE_SPY,),
        play_data_complete=True,
    ),
    _entry(
        40,
        "rebel-supplier",
        "Rebel Supplier",
        3,
        copies=2,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.CITY,),
        agent_effect=(PersonalCardAgentEffect.RECRUIT_TWO_IF_SPY_RECALLED_THIS_TURN),
        reveal_strength=1,
        reveal_effects=(PersonalCardRevealEffect(spice=1),),
        play_data_complete=True,
    ),
    _entry(
        20,
        "reliable-informant",
        "Reliable Informant",
        2,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.SPACING_GUILD,),
        agent_effect=PersonalCardAgentEffect.PLACE_SPY,
        agent_spy_factions=(
            Faction.EMPEROR,
            Faction.BENE_GESSERIT,
            Faction.SPACING_GUILD,
        ),
        reveal_persuasion=1,
        reveal_effects=(PersonalCardRevealEffect(solari=1),),
        play_data_complete=True,
    ),
    _entry(
        51,
        "sardaukar-coordination",
        "Sardaukar Coordination",
        4,
        copies=2,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.LANDSRAAD),
        allows_recruited_troop_deployment=True,
        reveal_strength=1,
        reveal_effects=(
            PersonalCardRevealEffect(
                strength=1,
                per_revealed_faction=PersonalCardBond.EMPEROR,
            ),
        ),
        play_data_complete=True,
    ),
    _entry(
        15,
        "sardaukar-soldier",
        "Sardaukar Soldier",
        1,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.CITY,),
        trash_effect=PersonalCardTrashEffect.DRAW_INTRIGUE_CARD,
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        48,
        "shishakli",
        "Shishakli",
        4,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE,
        reveal_strength=2,
        reveal_effects=(
            PersonalCardRevealEffect(
                influence=1,
                influence_faction=PersonalCardBond.FREMEN,
                required_faction_bond=PersonalCardBond.FREMEN,
            ),
        ),
        play_data_complete=True,
    ),
    _entry(
        17,
        "smuggler-s-harvester",
        "Smuggler's Harvester",
        1,
        copies=2,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.SPICE_TRADE,),
        agent_effect=PersonalCardAgentEffect.GAIN_SPICE_IF_MAKER_SPACE,
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(
        47,
        "smuggler-s-haven",
        "Smuggler's Haven",
        4,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.SPACING_GUILD, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.MAY_PAY_FOUR_SPICE_FOR_VP,
        reveal_persuasion=1,
        reveal_effects=(
            PersonalCardRevealEffect(
                spice=2,
                requires_spying_on_maker_space=True,
            ),
        ),
        play_data_complete=True,
    ),
    _entry(
        56,
        "southern-elders",
        "Southern Elders",
        4,
        factions=(Faction.BENE_GESSERIT, Faction.FREMEN),
        agent_icons=(AgentIcon.BENE_GESSERIT, AgentIcon.FREMEN),
        agent_effect=PersonalCardAgentEffect.RECRUIT_TWO_IF_BENE_GESSERIT_BOND,
        reveal_effects=(
            PersonalCardRevealEffect(water=1),
            PersonalCardRevealEffect(
                persuasion=2,
                required_faction_bond=PersonalCardBond.FREMEN,
            ),
        ),
        play_data_complete=True,
    ),
    _entry(
        12,
        "space-time-folding",
        "Space-time Folding",
        1,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.SPACING_GUILD,),
        agent_effect=(
            PersonalCardAgentEffect.DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD
        ),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(
        60,
        "spacing-guild-s-favor",
        "Spacing Guild's Favor",
        5,
        copies=2,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.SPACING_GUILD, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.DRAW_PERSONAL_CARD,
        discard_effect=PersonalCardDiscardEffect.GAIN_TWO_SPICE,
        reveal_persuasion=2,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE,
        ),
        play_data_complete=True,
    ),
    _entry(
        25,
        "spy-network",
        "Spy Network",
        2,
        has_acquisition_bonus=True,
        factions=(Faction.EMPEROR, Faction.SPACING_GUILD),
        acquisition_effect=PersonalCardAcquisitionEffect.PLACE_SPY,
        reveal_persuasion=2,
        reveal_strength=1,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED,
        ),
        play_data_complete=True,
    ),
    _entry(
        76,
        "steersman",
        "Steersman",
        8,
        has_acquisition_bonus=True,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(
            AgentIcon.SPACING_GUILD,
            AgentIcon.LANDSRAAD,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
        ),
        agent_effect=PersonalCardAgentEffect.DRAW_ONE_AND_RECALL_AGENT,
        acquisition_effect=(PersonalCardAcquisitionEffect.GAIN_SPACING_GUILD_INFLUENCE),
        reveal_persuasion=2,
        reveal_effects=(PersonalCardRevealEffect(spice=2),),
        play_data_complete=True,
    ),
    _entry(
        70,
        "stilgar-the-devoted",
        "Stilgar, The Devoted",
        6,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.RECRUIT_TWO_TROOPS,
        reveal_effects=(
            PersonalCardRevealEffect(
                persuasion=2,
                per_revealed_faction=PersonalCardBond.FREMEN,
            ),
        ),
        play_data_complete=True,
    ),
    _entry(
        65,
        "strike-fleet",
        "Strike Fleet",
        5,
        has_acquisition_bonus=True,
        agent_icons=(AgentIcon.SPY,),
        agent_effect=(PersonalCardAgentEffect.RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN),
        acquisition_effect=PersonalCardAcquisitionEffect.PLACE_SPY,
        reveal_persuasion=1,
        reveal_strength=3,
        play_data_complete=True,
    ),
    _entry(
        62,
        "subversive-advisor",
        "Subversive Advisor",
        5,
        has_acquisition_bonus=True,
        agent_icons=(AgentIcon.SPY,),
        agent_effect=(
            PersonalCardAgentEffect.GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF
        ),
        acquisition_effect=PersonalCardAcquisitionEffect.PLACE_SPY,
        reveal_effects=(PersonalCardRevealEffect(solari=1),),
        play_data_complete=True,
    ),
    _entry(
        66,
        "treacherous-maneuver",
        "Treacherous Maneuver",
        5,
        factions=(Faction.EMPEROR,),
        agent_icons=(
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.FREMEN,
        ),
        agent_effect=(
            PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE
        ),
        reveal_persuasion=1,
        reveal_effects=(PersonalCardRevealEffect(draw_intrigue=1),),
        play_data_complete=True,
    ),
    _entry(
        58,
        "tread-in-darkness",
        "Tread in Darkness",
        4,
        copies=2,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=(
            PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND
        ),
        reveal_persuasion=2,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        53,
        "truthtrance",
        "Truthtrance",
        4,
        copies=2,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.FREMEN,
        ),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
    _entry(
        28,
        "undercover-asset",
        "Undercover Asset",
        2,
        factions=(Faction.EMPEROR, Faction.SPACING_GUILD),
        agent_icons=(
            AgentIcon.LANDSRAAD,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
            AgentIcon.SPY,
        ),
        ignores_influence_requirements=True,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.PLACE_SPY_OR_GAIN_TWO_STRENGTH,
        ),
        play_data_complete=True,
    ),
    _entry(
        11,
        "unswerving-loyalty",
        "Unswerving Loyalty",
        1,
        copies=2,
        factions=(Faction.FREMEN,),
        reveal_persuasion=1,
        reveal_effects=(PersonalCardRevealEffect(recruit_troops=1),),
        play_data_complete=True,
    ),
    _entry(
        14,
        "weirding-woman",
        "Weirding Woman",
        1,
        copies=2,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.RETURN_SELF_IF_BENE_GESSERIT_BOND,
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        22,
        "wheels-within-wheels",
        "Wheels Within Wheels",
        2,
        factions=(Faction.EMPEROR, Faction.SPACING_GUILD),
        agent_icons=(AgentIcon.SPY,),
        agent_effect=(
            PersonalCardAgentEffect.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO
        ),
        reveal_persuasion=1,
        reveal_choice_effects=(PersonalCardRevealChoiceEffect.PLACE_SPY,),
        play_data_complete=True,
    ),
    # Uprising promo cards (2026-09-03): printed in the Uprising layout but
    # not in the retail deck; dealt only with RulesetConfig(promo_cards=True).
    # Transcribed from the card faces (Dune Cards Hub has no catalog page
    # for them, hence no catalog_id); project rulings for the gaps the
    # official documents leave are OQ-024 to OQ-026.
    _entry(
        None,
        "arrakis-revolt",
        "Arrakis Revolt",
        6,
        promo=True,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.CITY,),
        has_acquisition_bonus=True,
        acquisition_effect=PersonalCardAcquisitionEffect.RECRUIT_ONE_TROOP,
        agent_effect=(
            PersonalCardAgentEffect.MAY_PAY_TWO_SPICE_FOR_SHIELD_WALL_AND_SANDWORM_IF_MAKER_HOOKS
        ),
        reveal_persuasion=1,
        reveal_strength=3,
        play_data_complete=True,
    ),
    _entry(
        None,
        "pivotal-gambit",
        "Pivotal Gambit",
        3,
        promo=True,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY),
        agent_effect=(
            PersonalCardAgentEffect.MAY_TRASH_SELF_FOR_TROOP_AND_FIRST_PLACE_INFLUENCE
        ),
        reveal_persuasion=1,
        reveal_strength=2,
        play_data_complete=True,
    ),
    _entry(
        None,
        "the-beast-s-spoils",
        "The Beast's Spoils",
        3,
        promo=True,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.CITY,),
        agent_effect=PersonalCardAgentEffect.GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON,
        reveal_strength=3,
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
        bloodlines_only=True,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.MAY_DISCARD_FOR_DEEP_COVER_SPY,
        reveal_persuasion=1,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_RECALL_SPY_FOR_THREE_STRENGTH,
        ),
        play_data_complete=True,
    ),
    _entry(
        89,
        "bombast",
        "Bombast",
        1,
        bloodlines_only=True,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.LANDSRAAD,),
        reveal_persuasion=1,
        reveal_effects=(
            PersonalCardRevealEffect(
                solari=3, requires_command=True, trashes_self=True
            ),
        ),
        play_data_complete=True,
    ),
    _entry(
        90,
        "choam-demands",
        "CHOAM Demands",
        6,
        bloodlines_only=True,
        choam_only=True,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.COMPLETE_ONE_CONTRACT,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS,
        ),
        play_data_complete=True,
    ),
    _entry(
        91,
        "command-center",
        "Command Center",
        3,
        bloodlines_only=True,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.CITY),
        agent_effect=PersonalCardAgentEffect.RECRUIT_ONE_IF_EMPEROR_INFLUENCE_TWO,
        reveal_persuasion=1,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION,
        ),
        play_data_complete=True,
    ),
    _entry(
        92,
        "corrupt-bureaucrat",
        "Corrupt Bureaucrat",
        4,
        bloodlines_only=True,
        choam_only=True,
        factions=(Faction.SPACING_GUILD,),
        agent_icons=(AgentIcon.SPACING_GUILD, AgentIcon.LANDSRAAD, AgentIcon.SPY),
        agent_effect=PersonalCardAgentEffect.TAKE_CONTRACT_IF_SPY_RECALLED_THIS_TURN,
        discard_effect=PersonalCardDiscardEffect.GAIN_THREE_SOLARI,
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    _entry(
        94,
        "delivery-logistics",
        "Delivery Logistics",
        2,
        copies=2,
        bloodlines_only=True,
        choam_only=True,
        factions=(Faction.SPACING_GUILD,),
        agent_icons_from_contracts=True,
        reveal_choice_effects=(PersonalCardRevealChoiceEffect.PERSUASION_OR_CONTRACT,),
        play_data_complete=True,
    ),
    _entry(
        95,
        "disruption-tactics",
        "Disruption Tactics",
        2,
        bloodlines_only=True,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.FORCE_OPPONENT_TROOP_RETREAT,
        reveal_persuasion=1,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_COMBAT_ICON,
        ),
        play_data_complete=True,
    ),
    _entry(
        96,
        "eliminate-allies",
        "Eliminate Allies",
        2,
        bloodlines_only=True,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.SPY,),
        agent_effect=PersonalCardAgentEffect.TRASH_PERSONAL_CARD,
        trash_effect=PersonalCardTrashEffect.RECRUIT_TWO_TROOPS,
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        97,
        "elite-forces",
        "Elite Forces",
        3,
        bloodlines_only=True,
        factions=(Faction.EMPEROR, Faction.SPACING_GUILD),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.SPACING_GUILD),
        agent_effect=PersonalCardAgentEffect.MAY_TRASH_HAND_CARD_FOR_EMPEROR_REWARDS,
        reveal_persuasion=1,
        reveal_strength=1,
        play_data_complete=True,
    ),
    _entry(
        98,
        "engineered-miracle",
        "Engineered Miracle",
        3,
        bloodlines_only=True,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.MAY_DISCARD_FOR_WATER,
        reveal_persuasion=1,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD,
        ),
        play_data_complete=True,
    ),
    _entry(
        99,
        "fremen-war-name",
        "Fremen War Name",
        4,
        bloodlines_only=True,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.SPICE_TRADE),
        agent_effect=(
            PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN
        ),
        reveal_persuasion=2,
        reveal_effects=(
            PersonalCardRevealEffect(
                strength=2, required_faction_bond=PersonalCardBond.FREMEN
            ),
        ),
        play_data_complete=True,
    ),
    _entry(100, "holy-war", "Holy War", 5, bloodlines_only=True),
    _entry(
        101,
        "i-believe",
        "I Believe",
        3,
        bloodlines_only=True,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY),
        agent_effect=PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE,
        reveal_persuasion=1,
        reveal_effects=(
            PersonalCardRevealEffect(recruit_troops=2, requires_command=True),
        ),
        play_data_complete=True,
    ),
    _entry(
        102,
        "imperial-throneship",
        "Imperial Throneship",
        7,
        bloodlines_only=True,
        has_acquisition_bonus=True,
        acquisition_effect=PersonalCardAcquisitionEffect.GAIN_EMPEROR_INFLUENCE,
        factions=(Faction.EMPEROR,),
        agent_icons=(
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.LANDSRAAD,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
        ),
        agent_effect=PersonalCardAgentEffect.DRAW_INTRIGUE_CARD,
        reveal_persuasion=2,
        reveal_effects=(
            PersonalCardRevealEffect(
                persuasion=1, solari=3, minimum_garrisoned_units=4
            ),
        ),
        play_data_complete=True,
    ),
    _entry(
        104,
        "intelligence-training",
        "Intelligence Training",
        3,
        copies=2,
        bloodlines_only=True,
        has_acquisition_bonus=True,
        acquisition_effect=PersonalCardAcquisitionEffect.PLACE_SPY,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY),
        reveal_persuasion=1,
        reveal_strength=1,
        reveal_choice_effects=(PersonalCardRevealChoiceEffect.COMMAND_PLACE_SPY,),
        play_data_complete=True,
    ),
    _entry(
        106,
        "ixian-ambassador",
        "Ixian Ambassador",
        4,
        copies=2,
        bloodlines_only=True,
        tech_only=True,
    ),
    _entry(
        107,
        "litany-against-fear",
        "Litany Against Fear",
        3,
        bloodlines_only=True,
        factions=(Faction.BENE_GESSERIT,),
        turn_start_effect=PersonalCardTurnStartEffect.PLAY_TO_DRAW_AND_PASS,
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    _entry(
        108,
        "mercantile-affairs",
        "Mercantile Affairs",
        5,
        bloodlines_only=True,
        choam_only=True,
        has_acquisition_bonus=True,
        acquisition_effect=PersonalCardAcquisitionEffect.TAKE_CONTRACT,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(
            AgentIcon.BENE_GESSERIT,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
            AgentIcon.SPY,
        ),
        agent_effect=(
            PersonalCardAgentEffect.DRAW_INTRIGUE_IF_CONTRACT_COMPLETED_THIS_TURN
        ),
        reveal_persuasion=2,
        play_data_complete=True,
    ),
    _entry(
        77,
        "pointing-the-way",
        "Pointing the Way",
        6,
        bloodlines_only=True,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=PersonalCardAgentEffect.DRAW_INTRIGUE_IF_SANDWORM_IN_CONFLICT,
        reveal_persuasion=1,
        reveal_strength=2,
        reveal_choice_effects=(
            PersonalCardRevealChoiceEffect.COMMAND_GAIN_CHOSEN_INFLUENCE,
        ),
        play_data_complete=True,
    ),
    _entry(
        78,
        "possible-futures",
        "Possible Futures",
        8,
        bloodlines_only=True,
        has_acquisition_bonus=True,
        acquisition_effect=PersonalCardAcquisitionEffect.GAIN_ONE_WATER,
        factions=(Faction.BENE_GESSERIT, Faction.FREMEN),
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE),
        agent_effect=(
            PersonalCardAgentEffect.CHOSEN_INFLUENCE_OR_TWO_TROOPS_BOTH_IF_BOND
        ),
        reveal_persuasion=2,
        reveal_effects=(PersonalCardRevealEffect(water=1),),
        play_data_complete=True,
    ),
    _entry(
        80,
        "quash-rebellion",
        "Quash Rebellion",
        5,
        copies=2,
        bloodlines_only=True,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.SPACING_GUILD, AgentIcon.LANDSRAAD),
        agent_effect=PersonalCardAgentEffect.GAIN_TWO_SOLARI,
        reveal_strength=2,
        reveal_effects=(
            PersonalCardRevealEffect(persuasion=2, requires_commander_in_conflict=True),
        ),
        play_data_complete=True,
    ),
    _entry(
        82,
        "sandwalk",
        "Sandwalk",
        1,
        copies=2,
        bloodlines_only=True,
        factions=(Faction.FREMEN,),
        agent_icons=(AgentIcon.SPICE_TRADE,),
        agent_effect=PersonalCardAgentEffect.DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN,
        reveal_persuasion=1,
        reveal_strength=1,
        reveal_effects=(
            PersonalCardRevealEffect(
                persuasion=1, required_faction_bond=PersonalCardBond.FREMEN
            ),
        ),
        play_data_complete=True,
    ),
    _entry(
        83,
        "sardaukar-standard",
        "Sardaukar Standard",
        4,
        bloodlines_only=True,
        factions=(Faction.EMPEROR,),
        agent_icons=(AgentIcon.EMPEROR, AgentIcon.CITY),
        trash_effect=PersonalCardTrashEffect.ACQUIRE_BANK_COMMANDER,
        reveal_persuasion=2,
        reveal_effects=(PersonalCardRevealEffect(recruit_troops=1),),
        play_data_complete=True,
    ),
    _entry(
        86,
        "shrouded-counsel",
        "Shrouded Counsel",
        4,
        bloodlines_only=True,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.SPY,),
        agent_effect=PersonalCardAgentEffect.DRAW_INTRIGUE_CARD,
        reveal_persuasion=1,
        reveal_choice_effects=(PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_CARD,),
        play_data_complete=True,
    ),
    _entry(
        87,
        "southern-faith",
        "Southern Faith",
        5,
        bloodlines_only=True,
        factions=(Faction.BENE_GESSERIT, Faction.FREMEN),
        agent_icons=(AgentIcon.FREMEN, AgentIcon.CITY),
        agent_effect=(
            PersonalCardAgentEffect.DRAW_ONE_OR_BENE_GESSERIT_INFLUENCE_IF_BOND
        ),
        reveal_persuasion=1,
        reveal_strength=2,
        reveal_effects=(PersonalCardRevealEffect(spice=2, requires_command=True),),
        play_data_complete=True,
    ),
    _entry(
        85,
        "urgent-shigawire",
        "Urgent Shigawire",
        2,
        copies=2,
        bloodlines_only=True,
        factions=(Faction.BENE_GESSERIT,),
        agent_icons=(AgentIcon.BENE_GESSERIT, AgentIcon.CITY),
        agent_effect=(PersonalCardAgentEffect.BOOST_NEXT_BENE_GESSERIT_CARD_THIS_ROUND),
        reveal_persuasion=1,
        play_data_complete=True,
    ),
)

IMPERIUM_CARDS_BY_ID: Final = {entry.card.card_id: entry for entry in IMPERIUM_CARDS}


def imperium_cards_for_choam(
    choam_module: bool,
    promo_cards: bool = False,
    *,
    bloodlines: bool = False,
    tech_module: bool = False,
) -> tuple[ImperiumCardEntry, ...]:
    """Return physical card entries included by the selected setup.

    Bloodlines cards join only with the option [Bloodlines p. 3], and only
    once their play data is complete: an incomplete card would be inert in
    a hand, so it waits out of the deck until its slice lands.
    """

    return tuple(
        entry
        for entry in IMPERIUM_CARDS
        if (choam_module or not entry.choam_only)
        and (promo_cards or not entry.promo)
        and (
            not entry.bloodlines_only
            or (
                bloodlines
                and entry.play_data_complete
                and (tech_module or not entry.tech_only)
            )
        )
    )


def imperium_deck_instance_ids(
    choam_module: bool,
    promo_cards: bool = False,
    *,
    bloodlines: bool = False,
    tech_module: bool = False,
) -> tuple[str, ...]:
    """Return stable IDs for every physical Imperium card copy."""

    return tuple(
        f"imperium:{entry.card.card_id}:{copy}"
        for entry in imperium_cards_for_choam(
            choam_module, promo_cards, bloodlines=bloodlines, tech_module=tech_module
        )
        for copy in range(entry.copies)
    )


def imperium_card_for_instance(instance_id: str) -> ImperiumCardEntry:
    """Resolve a stable Imperium deck instance ID to its definition."""

    prefix = "imperium:"
    if not instance_id.startswith(prefix):
        raise ValueError("not an Imperium-card instance ID")
    try:
        card_id, copy_text = instance_id.removeprefix(prefix).rsplit(":", maxsplit=1)
        copy = int(copy_text)
        entry = IMPERIUM_CARDS_BY_ID[card_id]
    except (KeyError, ValueError) as error:
        raise ValueError("unknown Imperium-card instance ID") from error
    if copy < 0 or copy >= entry.copies:
        raise ValueError("Imperium-card copy index is out of range")
    return entry
