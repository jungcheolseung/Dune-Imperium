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
    PersonalCardRevealChoiceEffect,
    PersonalCardRevealEffect,
    PersonalCardTrashEffect,
)

BASE_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4)),)
CHOAM_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4, 16)),)


@dataclass(frozen=True, slots=True)
class ImperiumCardEntry(DeckCardEntry):
    """One shared-deck card plus independently verified play-facing data."""

    factions: tuple[Faction, ...] = ()
    agent_icons: tuple[AgentIcon, ...] = ()
    agent_effect: PersonalCardAgentEffect | None = None
    agent_spy_factions: tuple[Faction, ...] = ()
    acquisition_effect: PersonalCardAcquisitionEffect | None = None
    trash_effect: PersonalCardTrashEffect | None = None
    reveal_persuasion: int = 0
    reveal_strength: int = 0
    reveal_effects: tuple[PersonalCardRevealEffect, ...] = ()
    reveal_choice_effects: tuple[PersonalCardRevealChoiceEffect, ...] = ()
    play_data_complete: bool = False

    def __post_init__(self) -> None:
        super().__post_init__()
        if len(self.factions) != len(set(self.factions)):
            raise ValueError("Imperium-card Factions must be unique")
        if len(self.agent_icons) != len(set(self.agent_icons)):
            raise ValueError("Imperium-card Agent icons must be unique")
        if len(self.agent_spy_factions) != len(set(self.agent_spy_factions)):
            raise ValueError("Imperium-card Spy target Factions must be unique")
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
            or self.acquisition_effect is not None
            or self.trash_effect is not None
            or self.reveal_persuasion
            or self.reveal_strength
            or self.reveal_effects
            or self.reveal_choice_effects
        ):
            raise ValueError("partial Imperium-card play data must not be exposed")


def _entry(
    catalog_id: int,
    slug: str,
    name: str,
    acquisition_cost: int,
    *,
    copies: int = 1,
    choam_only: bool = False,
    has_acquisition_bonus: bool = False,
    factions: tuple[Faction, ...] = (),
    agent_icons: tuple[AgentIcon, ...] = (),
    agent_effect: PersonalCardAgentEffect | None = None,
    agent_spy_factions: tuple[Faction, ...] = (),
    acquisition_effect: PersonalCardAcquisitionEffect | None = None,
    trash_effect: PersonalCardTrashEffect | None = None,
    reveal_persuasion: int = 0,
    reveal_strength: int = 0,
    reveal_effects: tuple[PersonalCardRevealEffect, ...] = (),
    reveal_choice_effects: tuple[PersonalCardRevealChoiceEffect, ...] = (),
    play_data_complete: bool = False,
) -> ImperiumCardEntry:
    return ImperiumCardEntry(
        card=CardDefinition(
            card_id=slug.replace("-", "_"),
            name=name,
            sources=CHOAM_SOURCES if choam_only else BASE_SOURCES,
            catalog_url=f"https://dunecardshub.com/cards/{catalog_id}/uprising-{slug}",
        ),
        copies=copies,
        choam_only=choam_only,
        acquisition_cost=acquisition_cost,
        has_acquisition_bonus=has_acquisition_bonus,
        factions=factions,
        agent_icons=agent_icons,
        agent_effect=agent_effect,
        agent_spy_factions=agent_spy_factions,
        acquisition_effect=acquisition_effect,
        trash_effect=trash_effect,
        reveal_persuasion=reveal_persuasion,
        reveal_strength=reveal_strength,
        reveal_effects=reveal_effects,
        reveal_choice_effects=reveal_choice_effects,
        play_data_complete=play_data_complete,
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
    _entry(45, "branching-path", "Branching Path", 3),
    _entry(42, "calculus-of-power", "Calculus of Power", 3, copies=2),
    _entry(61, "captured-mentat", "Captured Mentat", 5),
    _entry(181, "cargo-runner", "Cargo Runner", 3, choam_only=True),
    _entry(67, "chani-clever-tactician", "Chani, Clever Tactician", 5),
    _entry(69, "corrinth-city", "Corrinth City", 6),
    _entry(35, "covert-operation", "Covert Operation", 3),
    _entry(44, "dangerous-rhetoric", "Dangerous Rhetoric", 3),
    _entry(182, "delivery-agreement", "Delivery Agreement", 5, choam_only=True),
    _entry(71, "desert-power", "Desert Power", 6),
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
    _entry(37, "double-agent", "Double Agent", 3, copies=2),
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
    _entry(38, "guild-envoy", "Guild Envoy", 3),
    _entry(43, "guild-spy", "Guild Spy", 3, has_acquisition_bonus=True),
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
        agent_effect=(
            PersonalCardAgentEffect.DRAW_INTRIGUE_IF_SPY_RECALLED_THIS_TURN
        ),
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
    ),
    _entry(68, "junction-headquarters", "Junction Headquarters", 6),
    _entry(63, "leadership", "Leadership", 5),
    _entry(74, "long-live-the-fighters", "Long Live the Fighters", 7),
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
    ),
    _entry(183, "priority-contracts", "Priority Contracts", 6, choam_only=True),
    _entry(55, "public-spectacle", "Public Spectacle", 4, copies=2),
    _entry(40, "rebel-supplier", "Rebel Supplier", 3, copies=2),
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
    _entry(51, "sardaukar-coordination", "Sardaukar Coordination", 4, copies=2),
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
    _entry(48, "shishakli", "Shishakli", 4),
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
    _entry(47, "smuggler-s-haven", "Smuggler's Haven", 4),
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
    _entry(12, "space-time-folding", "Space-time Folding", 1),
    _entry(60, "spacing-guild-s-favor", "Spacing Guild's Favor", 5, copies=2),
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
    _entry(76, "steersman", "Steersman", 8, has_acquisition_bonus=True),
    _entry(70, "stilgar-the-devoted", "Stilgar, The Devoted", 6),
    _entry(
        65,
        "strike-fleet",
        "Strike Fleet",
        5,
        has_acquisition_bonus=True,
        agent_icons=(AgentIcon.SPY,),
        agent_effect=(
            PersonalCardAgentEffect.RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN
        ),
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
    ),
    _entry(66, "treacherous-maneuver", "Treacherous Maneuver", 5),
    _entry(58, "tread-in-darkness", "Tread in Darkness", 4, copies=2),
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
    _entry(28, "undercover-asset", "Undercover Asset", 2),
    _entry(11, "unswerving-loyalty", "Unswerving Loyalty", 1, copies=2),
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
    _entry(22, "wheels-within-wheels", "Wheels Within Wheels", 2),
)

IMPERIUM_CARDS_BY_ID: Final = {
    entry.card.card_id: entry for entry in IMPERIUM_CARDS
}


def imperium_cards_for_choam(choam_module: bool) -> tuple[ImperiumCardEntry, ...]:
    """Return physical card entries included by the selected setup."""

    return tuple(
        entry for entry in IMPERIUM_CARDS if choam_module or not entry.choam_only
    )


def imperium_deck_instance_ids(choam_module: bool) -> tuple[str, ...]:
    """Return stable IDs for every physical Imperium card copy."""

    return tuple(
        f"imperium:{entry.card.card_id}:{copy}"
        for entry in imperium_cards_for_choam(choam_module)
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
