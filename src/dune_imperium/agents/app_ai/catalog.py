"""Our content ids <-> app archetypes, and entity construction.

Every lookup the AI makes goes from one of our ids (card instance id, space
id, conflict id, contract id, leader id, post id, faction id) to the app
archetype whose attributes and abilities the app AI would read. The tables
are explicit (no fuzzy matching at runtime) and tests check that every id our
4-player Uprising content can deal maps to an archetype that is dealt in the
app's game with the same CHOAM setting.

Known content differences (``scratchpad R5`` / ``spec/archetypes.md``):
- The app's reserve holds Foldspace x6; our engine has no Foldspace.
- Our three Uprising promos are not in the app's Imperium deck (keep
  ``promo_cards`` off); they map to their app archetypes anyway.
- Accept Contract, Dutiful Service, CHOAM Security and Trade Dispute have an
  ``...UP`` archetype (no CHOAM) and a ``...CHOAM`` one; pick by ``choam``.
"""

from dune_imperium.agents.app_ai.context import card_id
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.agents.app_ai.entities import Entity, Kind

# card_id -> app archetype short name (starters, reserve, Imperium incl. CHOAM
# and promos).
CARD_ARCHETYPES: dict[str, str] = {}
# intrigue card_id -> app archetype short name.
INTRIGUE_ARCHETYPES: dict[str, str] = {}
# space_id -> (archetype without CHOAM, archetype with CHOAM).
SPACE_ARCHETYPES: dict[str, tuple[str, str]] = {}
# conflict card_id -> (archetype without CHOAM, archetype with CHOAM).
CONFLICT_ARCHETYPES: dict[str, tuple[str, str]] = {}
# contract card_id -> app archetype short name.
CONTRACT_ARCHETYPES: dict[str, str] = {}
# leader_id -> app archetype short name (incl. Lady Jessica's flipped face).
LEADER_ARCHETYPES: dict[str, str] = {}
# post_id -> the app's observation post index (1-13).
POST_INDEX: dict[str, int] = {}
# our faction id -> the app's Factions enum name.
FACTION_NAMES: dict[str, str] = {
    "emperor": "Emperor",
    "spacing_guild": "SpacingGuild",
    "bene_gesserit": "BeneGesserit",
    "fremen": "Fremen",
}


def _archetype(short: str) -> Archetype:
    return ARCHETYPES[short]


def card_entity(instance_id: str, owner: int | None = None) -> Entity:
    """A personal card (starter, reserve or Imperium) by instance id."""

    return Entity(
        Kind.CARD, instance_id, _archetype(CARD_ARCHETYPES[card_id(instance_id)]), owner
    )


def intrigue_entity(instance_id: str, owner: int | None = None) -> Entity:
    """An Intrigue card by instance id."""

    return Entity(
        Kind.INTRIGUE,
        instance_id,
        _archetype(INTRIGUE_ARCHETYPES[card_id(instance_id)]),
        owner,
    )


def contract_entity(instance_id: str, owner: int | None = None) -> Entity:
    """A CHOAM contract by instance id (``contract:<id>``)."""

    return Entity(
        Kind.CONTRACT,
        instance_id,
        _archetype(CONTRACT_ARCHETYPES[card_id(instance_id)]),
        owner,
    )


def space_entity(space_id: str, choam: bool) -> Entity:
    """A board space."""

    without, with_choam = SPACE_ARCHETYPES[space_id]
    return Entity(Kind.SPACE, space_id, _archetype(with_choam if choam else without))


def conflict_entity(conflict_id: str, choam: bool) -> Entity:
    """A Conflict card."""

    without, with_choam = CONFLICT_ARCHETYPES[conflict_id]
    return Entity(
        Kind.CONFLICT, conflict_id, _archetype(with_choam if choam else without)
    )


def conflict_reward_entities(conflict_id: str, choam: bool) -> tuple[Entity, ...]:
    """The 1st/2nd/3rd reward archetypes of a Conflict card, in place order.

    Read from the card archetype's ``ConflictRewardArchetypes``.
    """

    card = conflict_entity(conflict_id, choam)
    return tuple(
        Entity(Kind.CONFLICT, conflict_id, _archetype(short))
        for short in card.list_attr("ConflictRewardArchetypes")
    )


def leader_entity(leader_id: str, face_id: str | None = None) -> Entity:
    """A leader (the flipped face when ``face_id`` names one)."""

    key = face_id if face_id and face_id in LEADER_ARCHETYPES else leader_id
    return Entity(Kind.LEADER, leader_id, _archetype(LEADER_ARCHETYPES[key]))


def post_entity(post_id: str, owner: int | None = None) -> Entity:
    """An observation post (the app's ``WormObservationPost``)."""

    return Entity(Kind.POST, post_id, None, owner)


def spy_entity(post_id: str, owner: int) -> Entity:
    """A spy standing on ``post_id``."""

    return Entity(Kind.SPY, post_id, None, owner)


def agent_entity(space_id: str, owner: int) -> Entity:
    """An agent standing on ``space_id``."""

    return Entity(Kind.AGENT, space_id, None, owner)


def track_entity(faction: str) -> Entity:
    """A faction influence track (our faction id)."""

    return Entity(Kind.TRACK, faction, None)
