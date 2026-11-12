"""The Agent icons a card carries as it is played: printed plus borrowed.

Kept apart from ``agent_turn`` so the Agent-box rules (Slig Farmer counts
"the Agent icons on the other grafted card", OQ-055) can read it without
importing the placement module.
"""

from dune_imperium.content.core.cards import ImperiumCardEntry, PersonalCardDefinition
from dune_imperium.content.core.icons import AgentIcon, Faction
from dune_imperium.content.core.tech import TechAbility
from dune_imperium.content.registry.board import BOARD_SPACES_BY_ID
from dune_imperium.content.registry.card_abilities import card_icon_condition
from dune_imperium.content.registry.contracts import contract_for_instance
from dune_imperium.content.registry.personal_cards import (
    card_copies_partner_box,
    personal_card_for_instance,
)
from dune_imperium.content.registry.tech import has_tech
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.card_bonds import counted_in_play


def copies_partner_box(card_instance_id: str) -> bool:
    """Whether the instance copies its graft partner's Agent box (Ghola,
    Immortality)."""

    return card_copies_partner_box(personal_card_for_instance(card_instance_id))


def is_bond_partner(card_instance_id: str) -> bool:
    """Return whether a graft partner meets a Bene Gesserit Bond icon condition.

    A Bene Gesserit card grafted with Long Reach is "another Bene Gesserit
    card in play" [Long Reach card]: both cards are played together and
    "You may use an Agent icon from either card" [Immortality p. 10], and the
    Ghola clarification already counts the Bene Gesserit card Ghola is
    grafted to as in play for "if you have a Bene Gesserit card in play"
    [Immortality p. 14]. Ghola is "not itself a Bene Gesserit card"
    [Immortality p. 14], but its copy of Long Reach's box counts Long Reach
    (designer ruling, OQ-057 (12)).
    """

    factions = personal_card_for_instance(card_instance_id).factions
    return copies_partner_box(card_instance_id) or Faction.BENE_GESSERIT in factions


def effective_agent_icons(
    card: PersonalCardDefinition,
    owner: PlayerState,
    *,
    grafted: bool = False,
    opponents: tuple[PlayerState, ...] = (),
    bond_partner: bool = False,
    card_instance_id: str | None = None,
) -> tuple[AgentIcon, ...]:
    """Return the card's Agent icons as printed, plus any it borrows.

    Delivery Logistics (Bloodlines) has "the Agent icons of all your
    incomplete contracts": each active Contract that names a board space
    lends that space's icon, and a harvest Contract lends the Spice Trade
    icon of the Maker spaces. With ``bond_partner`` the card is (or may be)
    grafted with a partner that meets its Bene Gesserit Bond icons: a Bene
    Gesserit card played with it is "in play" once both are played
    [Immortality pp. 10, 14], and Ghola's copy counts too (designer ruling:
    Ghola + Long Reach has all three icons; OQ-057). ``card_instance_id``
    keeps a card already in play from counting as its own "another Bene
    Gesserit card" [Long Reach card].
    """

    icons = list(card.agent_icons)
    icon_condition = card_icon_condition(card)
    if isinstance(card, ImperiumCardEntry) and icon_condition is not None:
        # Greyed icons that a printed condition turns on, judged as the card
        # is played (Long Reach, Show of Strength) [card faces].
        if icon_condition == "bene_gesserit_bond":
            # "If you have another Bene Gesserit card in play" [Long Reach card];
            # a Row card borrowed with Usurp is not in play (OQ-054).
            met = bond_partner or any(
                other != card_instance_id
                and Faction.BENE_GESSERIT in personal_card_for_instance(other).factions
                for other in counted_in_play(owner)
            )
        else:
            met = all(
                owner.troops_conflict + owner.commanders_conflict
                > seat.troops_conflict + seat.commanders_conflict
                for seat in opponents
            )
        if not met:
            icons = []
    if card.card.card_id == "signet_ring" and has_tech(
        owner.tech_ids, TechAbility.SIGNET_FACTION_ICONS
    ):
        # Servo-Receivers: "Your Signet Ring has the following icons": the
        # four Faction Agent icons [Tech tile face].
        icons.extend(
            (
                AgentIcon.EMPEROR,
                AgentIcon.SPACING_GUILD,
                AgentIcon.BENE_GESSERIT,
                AgentIcon.FREMEN,
            )
        )
    if grafted and card.card.card_id == "blank_slate":
        # Blank Slate: "If grafted: this has [Emperor], [Guild], [Bene
        # Gesserit], and [Fremen]" [card face].
        icons.extend(
            (
                AgentIcon.EMPEROR,
                AgentIcon.SPACING_GUILD,
                AgentIcon.BENE_GESSERIT,
                AgentIcon.FREMEN,
            )
        )
    if isinstance(card, ImperiumCardEntry) and card.agent_icons_from_contracts:
        for instance_id in owner.active_contract_ids:
            contract = contract_for_instance(instance_id)
            if contract.board_space is not None:
                icons.append(BOARD_SPACES_BY_ID[contract.board_space].agent_icon)
            elif contract.harvest_spice:
                icons.append(AgentIcon.SPICE_TRADE)
    if owner.leader_id == "gaius_helen_mohiam":
        # Clandestine: "Each card you play has the [Spy] icon" [Gaius Helen
        # Mohiam card] -- after the icon condition, which cannot take it
        # away, so Slig Farmer counts it with the other icons (OQ-055).
        icons.append(AgentIcon.SPY)
    return tuple(dict.fromkeys(icons))


def card_is_boosted(card: PersonalCardDefinition, owner: PlayerState) -> bool:
    """Return whether Urgent Shigawire's boost applies to this card."""

    return owner.bene_gesserit_boost_pending and Faction.BENE_GESSERIT in card.factions
