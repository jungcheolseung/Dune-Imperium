"""The Agent icons a card carries as it is played: printed plus borrowed.

Kept apart from ``agent_turn`` so the Agent-box rules (Slig Farmer counts
"the Agent icons on the other grafted card", OQ-055) can read it without
importing the placement module.
"""

from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, Faction
from dune_imperium.content.uprising.contracts import (
    ContractConditionKind,
    contract_for_instance,
)
from dune_imperium.content.uprising.imperium import ImperiumCardEntry
from dune_imperium.content.uprising.personal_cards import (
    PersonalCardDefinition,
    personal_card_for_instance,
)
from dune_imperium.content.uprising.types import AgentIcon, PersonalCardIconCondition
from dune_imperium.core.player import PlayerState


def is_ghola(card_instance_id: str) -> bool:
    """Return whether the instance is Ghola (Immortality), the copying graft."""

    return personal_card_for_instance(card_instance_id).card.card_id == "ghola"


def effective_agent_icons(
    card: PersonalCardDefinition,
    owner: PlayerState,
    *,
    grafted: bool = False,
    opponents: tuple[PlayerState, ...] = (),
    ghola_partner: bool = False,
) -> tuple[AgentIcon, ...]:
    """Return the card's Agent icons as printed, plus any it borrows.

    Delivery Logistics (Bloodlines) has "the Agent icons of all your
    incomplete contracts": each active Contract that names a board space
    lends that space's icon, and a harvest Contract lends the Spice Trade
    icon of the Maker spaces. With ``ghola_partner`` the card is (or may
    be) grafted with Ghola, whose copy satisfies the card's own Bene
    Gesserit Bond icons (designer ruling: Ghola + Long Reach has all three
    icons; OQ-057).
    """

    icons = list(card.agent_icons)
    if isinstance(card, ImperiumCardEntry) and card.icon_condition is not None:
        # Greyed icons that a printed condition turns on, judged as the card
        # is played (Long Reach, Show of Strength) [card faces].
        icon_condition = card.icon_condition
        if icon_condition is PersonalCardIconCondition.BENE_GESSERIT_BOND:
            met = ghola_partner or any(
                Faction.BENE_GESSERIT in personal_card_for_instance(other).factions
                for other in owner.in_play
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
            condition = contract_for_instance(instance_id).condition
            if condition.kind is ContractConditionKind.BOARD_SPACE:
                icons.append(BOARD_SPACES_BY_ID[condition.target].agent_icon)
            elif condition.kind is ContractConditionKind.HARVEST_SPICE:
                icons.append(AgentIcon.SPICE_TRADE)
    return tuple(dict.fromkeys(icons))


def card_is_boosted(card: PersonalCardDefinition, owner: PlayerState) -> bool:
    """Return whether Urgent Shigawire's boost applies to this card."""

    return owner.bene_gesserit_boost_pending and Faction.BENE_GESSERIT in card.factions
