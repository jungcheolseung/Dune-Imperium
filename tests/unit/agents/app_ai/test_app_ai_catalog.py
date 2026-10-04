"""Our content ids <-> app archetypes: coverage, dealing, titles, printed numbers.

``agents/app_ai/catalog.py`` holds explicit id tables. These tests join every
id a 4-player Uprising game can deal (with and without the CHOAM module) to
the app archetype it names and compare what both sides print: the English
title, costs, Persuasion and swords, Agent icons, factions, copies, timings,
observation posts and conflict levels.

Intentional differences, listed here so none is silent:

- Desert Power: the app prints Persuasion 0 on the card; ours stores 2 (paid
  only through its Reveal choice).
- Skirmish: our three cards are named "Skirmish (Crysknife|Ornithopter|Desert
  Mouse)", the app's three archetypes are all titled "Skirmish" and told apart
  by battle icon.
- The three Uprising promos (Arrakis Revolt, Pivotal Gambit, The Beast's
  Spoils) are never dealt in the app, so ``data/archetypes.py`` has no entry
  for them; ``PROMO_SHORT_NAMES`` pins the app's own short names.
- Contracts have no title in the app (the tile shows its condition and reward).
"""

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

import pytest

from dune_imperium.agents.app_ai.catalog import (
    CARD_ARCHETYPES,
    CONFLICT_ARCHETYPES,
    CONTRACT_ARCHETYPES,
    FACTION_NAMES,
    INTRIGUE_ARCHETYPES,
    LEADER_ARCHETYPES,
    POST_INDEX,
    SPACE_ARCHETYPES,
    card_entity,
    conflict_entity,
    conflict_reward_entities,
    contract_entity,
    intrigue_entity,
    leader_entity,
    space_entity,
)
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    OBSERVATION_POSTS,
    BoardSpace,
    Faction,
)
from dune_imperium.content.uprising.conflicts import (
    ConflictDefinition,
    conflicts_by_tier,
)
from dune_imperium.content.uprising.contracts import (
    STANDARD_CONTRACTS,
    ContractConditionKind,
    contract_instance_ids,
)
from dune_imperium.content.uprising.effect_dsl import IntrigueTiming
from dune_imperium.content.uprising.imperium import (
    ImperiumCardEntry,
    imperium_cards_for_choam,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.intrigue import (
    IntrigueCardEntry,
    intrigue_cards_for_choam,
    intrigue_deck_instance_ids,
)
from dune_imperium.content.uprising.leaders import (
    LEADERS_BY_ID,
    LeaderDefinition,
    leaders_for_choam,
)
from dune_imperium.content.uprising.reserve import (
    RESERVE_STACKS,
    ReserveStackDefinition,
)
from dune_imperium.content.uprising.starting_cards import (
    STARTING_DECK,
    StartingCardEntry,
    starting_deck_instance_ids,
)
from dune_imperium.content.uprising.types import AgentIcon, ConflictTier

CHOAM = pytest.mark.parametrize("choam", [False, True], ids=["no_choam", "choam"])

# The app's own short names for our three promos (``ImperiumType = Promo``);
# the app never deals them, so they are absent from ``ARCHETYPES``.
PROMO_SHORT_NAMES = {
    "arrakis_revolt": "ImperiumArchetypes.Promo.ArrakisRevolt",
    "pivotal_gambit": "ImperiumArchetypes.Promo.PivotalGambit",
    "the_beast_s_spoils": "ImperiumArchetypes.Promo.TheBeastsSpoils",
}

# Our Skirmish names carry the battle icon; the app's three archetypes do not.
CONFLICT_TITLES = {
    "skirmish_crysknife": "Skirmish",
    "skirmish_ornithopter": "Skirmish",
    "skirmish_desert_mouse": "Skirmish",
}

# Desert Power prints Persuasion 0 in the app and 2 in ours (see docstring).
PERSUASION_DIFFERENCES = {"desert_power": (0, 2)}

# The app's ``IconList`` / ``AgentIcon`` names in ours.
APP_ICONS = {
    "Emperor": AgentIcon.EMPEROR,
    "SpacingGuild": AgentIcon.SPACING_GUILD,
    "BeneGesserit": AgentIcon.BENE_GESSERIT,
    "Fremen": AgentIcon.FREMEN,
    "Pentagon": AgentIcon.LANDSRAAD,
    "Circle": AgentIcon.CITY,
    "Triangle": AgentIcon.SPICE_TRADE,
    "Spy": AgentIcon.SPY,
}

APP_BATTLE_ICONS = {
    "crysknife": "Crysknife",
    "ornithopter": "Ornithopter",
    "desert_mouse": "DesertMouse",
    "wild": "Wildcard",
}

APP_TIMINGS = {
    "Plot": IntrigueTiming.PLOT,
    "Combat": IntrigueTiming.COMBAT,
    "Endgame": IntrigueTiming.ENDGAME,
}

# Spaces that carry a separate archetype with the CHOAM module.
CHOAM_SPLIT_SPACES = {"accept_contract", "dutiful_service"}
CHOAM_SPLIT_CONFLICTS = {"choam_security", "trade_dispute"}


def _norm(text: str) -> str:
    """Case and punctuation folded, as titles are compared."""

    return re.sub(r"[^a-z0-9]", "", text.lower())


def _int_attr(archetype: Archetype, name: str, default: int = 0) -> int:
    value = archetype.attributes.get(name, default)
    assert isinstance(value, int)
    assert not isinstance(value, bool)
    return value


def _tuple_attr(archetype: Archetype, name: str) -> tuple[str, ...]:
    value = archetype.attributes.get(name, ())
    assert isinstance(value, tuple)
    return tuple(str(item) for item in value)


def _str_attr(archetype: Archetype, name: str) -> str | None:
    value = archetype.attributes.get(name)
    assert value is None or isinstance(value, str)
    return value


def _dealt(archetype: Archetype, choam: bool) -> bool:
    """Whether the app deals this archetype in a 4-player Uprising game."""

    return archetype.in_uprising_choam if choam else archetype.in_uprising


def _ability_names(archetype: Archetype) -> tuple[str, ...]:
    return tuple(
        name.rsplit(".", 1)[-1] for name in _tuple_attr(archetype, "WormAbilityIDs")
    )


def _pair(table: Mapping[str, tuple[str, str]], key: str, choam: bool) -> str:
    without, with_choam = table[key]
    return with_choam if choam else without


# -- personal cards -----------------------------------------------------------


@dataclass(frozen=True)
class PrintedCard:
    """The printed numbers both sides must agree on."""

    group: str
    card_id: str
    name: str
    copies: int
    cost: int | None
    persuasion: int
    strength: int
    icons: frozenset[AgentIcon]
    factions: frozenset[str]


def _printed(
    group: str,
    entry: StartingCardEntry | ReserveStackDefinition | ImperiumCardEntry,
) -> PrintedCard:
    cost = None if isinstance(entry, StartingCardEntry) else entry.acquisition_cost
    return PrintedCard(
        group=group,
        card_id=entry.card.card_id,
        name=entry.card.name,
        copies=entry.copies,
        cost=cost,
        persuasion=entry.reveal_persuasion,
        strength=entry.reveal_strength,
        icons=frozenset(entry.agent_icons),
        factions=frozenset(faction.value for faction in entry.factions),
    )


def _dealt_cards(choam: bool) -> list[PrintedCard]:
    """Every personal card identity a 4-player Uprising game can deal."""

    return [
        *(_printed("starter", entry) for entry in STARTING_DECK),
        *(_printed("reserve", entry) for entry in RESERVE_STACKS),
        *(
            _printed("imperium", entry)
            for entry in imperium_cards_for_choam(choam, promo_cards=False)
        ),
    ]


def _promo_ids() -> set[str]:
    with_promos = imperium_cards_for_choam(True, promo_cards=True)
    without = imperium_cards_for_choam(True, promo_cards=False)
    return {entry.card.card_id for entry in with_promos} - {
        entry.card.card_id for entry in without
    }


def test_card_table_has_exactly_the_registered_cards() -> None:
    registered = (
        {entry.card.card_id for entry in STARTING_DECK}
        | {entry.card.card_id for entry in RESERVE_STACKS}
        | {entry.card.card_id for entry in imperium_cards_for_choam(True, True)}
    )
    assert set(CARD_ARCHETYPES) == registered
    assert len(CARD_ARCHETYPES) == 7 + 2 + 54 + 3


@CHOAM
def test_every_dealt_card_maps_to_an_archetype_dealt_with_that_setting(
    choam: bool,
) -> None:
    for card in _dealt_cards(choam):
        short = CARD_ARCHETYPES[card.card_id]
        assert short in ARCHETYPES, card.card_id
        assert _dealt(ARCHETYPES[short], choam), card.card_id


def test_card_archetypes_are_unique_and_grouped_by_deck() -> None:
    mapped = [CARD_ARCHETYPES[card.card_id] for card in _dealt_cards(True)]
    assert len(set(mapped)) == len(mapped)
    for card in _dealt_cards(True):
        archetype = ARCHETYPES[CARD_ARCHETYPES[card.card_id]]
        expected_type = {"starter": "Starter", "reserve": "Reserve", "imperium": "Main"}
        assert archetype.attributes["ImperiumType"] == expected_type[card.group]
        assert archetype.kind == card.group


def test_choam_only_cards_are_dealt_only_with_choam() -> None:
    choam_only = {
        entry.card.card_id
        for entry in imperium_cards_for_choam(True)
        if entry.choam_only
    }
    assert choam_only == {
        "cargo_runner",
        "delivery_agreement",
        "interstellar_trade",
        "priority_contracts",
    }
    for card_id in choam_only:
        archetype = ARCHETYPES[CARD_ARCHETYPES[card_id]]
        assert not archetype.in_uprising
        assert archetype.in_uprising_choam


def test_promos_map_to_the_apps_names_but_are_never_dealt() -> None:
    assert _promo_ids() == set(PROMO_SHORT_NAMES)
    for card_id, short in PROMO_SHORT_NAMES.items():
        assert CARD_ARCHETYPES[card_id] == short
        assert short not in ARCHETYPES
    for choam in (False, True):
        dealt = {e.card.card_id for e in imperium_cards_for_choam(choam)}
        assert not dealt & set(PROMO_SHORT_NAMES)


def test_the_app_deals_nothing_our_catalog_leaves_unmapped() -> None:
    """Every app card archetype is ours except Foldspace (the app-only card)."""

    mapped = set(CARD_ARCHETYPES.values())
    app_cards = {
        short
        for short, archetype in ARCHETYPES.items()
        if archetype.kind in {"starter", "reserve", "imperium"}
    }
    assert app_cards - mapped == {"ImperiumArchetypes.BaseSet.FoldspaceImperium"}


@CHOAM
def test_card_titles_match_after_normalising(choam: bool) -> None:
    for card in _dealt_cards(choam):
        archetype = ARCHETYPES[CARD_ARCHETYPES[card.card_id]]
        assert archetype.title is not None
        assert _norm(archetype.title) == _norm(card.name), card.card_id


@CHOAM
def test_card_printed_numbers_agree(choam: bool) -> None:
    for card in _dealt_cards(choam):
        archetype = ARCHETYPES[CARD_ARCHETYPES[card.card_id]]
        attrs = archetype.attributes
        where = card.card_id

        assert attrs.get("PersuasionCost") == card.cost, where

        app_persuasion = _int_attr(archetype, "Persuasion")
        if card.card_id in PERSUASION_DIFFERENCES:
            assert (app_persuasion, card.persuasion) == PERSUASION_DIFFERENCES[where]
        else:
            assert app_persuasion == card.persuasion, where

        assert _int_attr(archetype, "Strength") == card.strength, where

        app_icons = {APP_ICONS[name] for name in _tuple_attr(archetype, "IconList")}
        assert app_icons == card.icons, where

        app_factions = set(_tuple_attr(archetype, "FactionList"))
        assert app_factions == {FACTION_NAMES[f] for f in card.factions}, where

        if card.group == "starter":
            assert "CardCount" not in attrs, where
        else:
            assert _int_attr(archetype, "CardCount") == card.copies, where


def test_desert_power_is_the_only_persuasion_difference() -> None:
    differing = {
        card.card_id
        for card in _dealt_cards(True)
        if _int_attr(ARCHETYPES[CARD_ARCHETYPES[card.card_id]], "Persuasion")
        != card.persuasion
    }
    assert differing == set(PERSUASION_DIFFERENCES)


def test_faction_names_cover_our_factions() -> None:
    assert set(FACTION_NAMES) == {faction.value for faction in Faction}


# -- Intrigue -----------------------------------------------------------------


def _dealt_intrigue(choam: bool) -> tuple[IntrigueCardEntry, ...]:
    return intrigue_cards_for_choam(choam)


def test_intrigue_table_has_exactly_the_uprising_identities() -> None:
    assert set(INTRIGUE_ARCHETYPES) == {
        entry.card.card_id for entry in intrigue_cards_for_choam(True)
    }
    assert len(INTRIGUE_ARCHETYPES) == 39
    assert len(set(INTRIGUE_ARCHETYPES.values())) == 39


@CHOAM
def test_every_dealt_intrigue_maps_to_an_archetype_dealt_with_that_setting(
    choam: bool,
) -> None:
    entries = _dealt_intrigue(choam)
    assert len(entries) == (39 if choam else 35)
    for entry in entries:
        short = INTRIGUE_ARCHETYPES[entry.card.card_id]
        assert short in ARCHETYPES, entry.card.card_id
        archetype = ARCHETYPES[short]
        assert archetype.kind == "intrigue"
        assert _dealt(archetype, choam), entry.card.card_id


@CHOAM
def test_intrigue_titles_copies_and_timings_agree(choam: bool) -> None:
    for entry in _dealt_intrigue(choam):
        archetype = ARCHETYPES[INTRIGUE_ARCHETYPES[entry.card.card_id]]
        where = entry.card.card_id
        assert archetype.title is not None
        assert _norm(archetype.title) == _norm(entry.card.name), where
        assert _int_attr(archetype, "CardCount") == entry.copies, where
        app_timings = {
            APP_TIMINGS[t] for t in _tuple_attr(archetype, "IntrigueTypeList")
        }
        assert app_timings == set(entry.timings), where


# -- board spaces and observation posts --------------------------------------


def _core_spaces() -> list[BoardSpace]:
    """The 22 Uprising spaces (Bloodlines' Tuek's Sietch is gated by a leader)."""

    return [space for space in BOARD_SPACES if space.required_leader_id is None]


def _posts_of(space_id: str) -> set[int]:
    return {
        POST_INDEX[post.post_id]
        for post in OBSERVATION_POSTS
        if space_id in post.connected_space_ids
    }


def test_space_table_has_exactly_the_core_spaces() -> None:
    assert set(SPACE_ARCHETYPES) == {space.space_id for space in _core_spaces()}
    assert len(SPACE_ARCHETYPES) == 22


@CHOAM
def test_every_space_maps_to_an_archetype_dealt_with_that_setting(choam: bool) -> None:
    for space in _core_spaces():
        short = _pair(SPACE_ARCHETYPES, space.space_id, choam)
        assert short in ARCHETYPES, space.space_id
        archetype = ARCHETYPES[short]
        assert archetype.kind == "space"
        assert _dealt(archetype, choam), space.space_id


def test_only_accept_contract_and_dutiful_service_differ_with_choam() -> None:
    differing = {
        space_id
        for space_id, (without, with_choam) in SPACE_ARCHETYPES.items()
        if without != with_choam
    }
    assert differing == CHOAM_SPLIT_SPACES
    for space_id in CHOAM_SPLIT_SPACES:
        without, with_choam = SPACE_ARCHETYPES[space_id]
        assert without.endswith("UP")
        assert with_choam.endswith("CHOAM")


@CHOAM
def test_space_titles_icons_and_combat_agree(choam: bool) -> None:
    for space in _core_spaces():
        archetype = ARCHETYPES[_pair(SPACE_ARCHETYPES, space.space_id, choam)]
        where = space.space_id
        assert archetype.title is not None
        assert _norm(archetype.title) == _norm(space.name), where
        app_icon = _str_attr(archetype, "AgentIcon")
        assert app_icon is not None
        assert APP_ICONS[app_icon] is space.agent_icon, where
        assert bool(archetype.attributes.get("CombatSpace", False)) is space.combat, (
            where
        )


def test_post_index_covers_our_thirteen_posts() -> None:
    assert set(POST_INDEX) == {post.post_id for post in OBSERVATION_POSTS}
    assert sorted(POST_INDEX.values()) == list(range(1, 14))


@CHOAM
def test_space_observation_posts_agree_with_our_board(choam: bool) -> None:
    for space in _core_spaces():
        archetype = ARCHETYPES[_pair(SPACE_ARCHETYPES, space.space_id, choam)]
        app_posts = set(_int_tuple(archetype, "ObservationPosts"))
        assert app_posts == _posts_of(space.space_id), space.space_id


def _int_tuple(archetype: Archetype, name: str) -> tuple[int, ...]:
    value = archetype.attributes.get(name, ())
    assert isinstance(value, tuple)
    assert all(isinstance(item, int) for item in value)
    return tuple(int(item) for item in value)


def test_known_post_indexes() -> None:
    """Spot checks from the board: Arrakeen 10, Imperial Basin 13, ..."""

    assert _posts_of("arrakeen") == {10}
    assert _posts_of("imperial_basin") == {13}
    assert _posts_of("secrets") == {3}
    assert _posts_of("research_station") == {8, 9}
    assert _posts_of("spice_refinery") == {9, 10}


# -- conflicts ----------------------------------------------------------------


def _dealt_conflicts() -> list[ConflictDefinition]:
    """The 16 Uprising Conflict cards (no Bloodlines, no Epic Game)."""

    return [conflict for tier in ConflictTier for conflict in conflicts_by_tier(tier)]


def test_conflict_table_has_exactly_the_uprising_conflicts() -> None:
    conflicts = _dealt_conflicts()
    assert len(conflicts) == 16
    assert set(CONFLICT_ARCHETYPES) == {c.card.card_id for c in conflicts}


@CHOAM
def test_every_conflict_maps_to_an_archetype_dealt_with_that_setting(
    choam: bool,
) -> None:
    mapped: list[str] = []
    for conflict in _dealt_conflicts():
        short = _pair(CONFLICT_ARCHETYPES, conflict.card.card_id, choam)
        assert short in ARCHETYPES, conflict.card.card_id
        archetype = ARCHETYPES[short]
        assert archetype.kind == "conflict"
        assert _dealt(archetype, choam), conflict.card.card_id
        mapped.append(short)
    assert len(set(mapped)) == len(mapped) == 16


def test_only_choam_security_and_trade_dispute_differ_with_choam() -> None:
    differing = {
        conflict_id
        for conflict_id, (without, with_choam) in CONFLICT_ARCHETYPES.items()
        if without != with_choam
    }
    assert differing == CHOAM_SPLIT_CONFLICTS
    for conflict_id in CHOAM_SPLIT_CONFLICTS:
        without, with_choam = CONFLICT_ARCHETYPES[conflict_id]
        assert without.endswith("UP")
        assert with_choam.endswith("CHOAM")


@CHOAM
def test_conflict_titles_levels_and_icons_agree(choam: bool) -> None:
    for conflict in _dealt_conflicts():
        where = conflict.card.card_id
        archetype = ARCHETYPES[_pair(CONFLICT_ARCHETYPES, where, choam)]
        expected_title = CONFLICT_TITLES.get(where, conflict.card.name)
        assert archetype.title is not None
        assert _norm(archetype.title) == _norm(expected_title), where
        assert _int_attr(archetype, "ConflictLevel") == conflict.tier.value, where
        assert conflict.battle_icon is not None
        assert (
            archetype.attributes["BattleIcon"]
            == APP_BATTLE_ICONS[conflict.battle_icon.value]
        ), where
        has_wall = "ShieldWall" in _tuple_attr(archetype, "Tags")
        assert has_wall is conflict.shield_wall_protected, where


@CHOAM
def test_conflict_reward_archetypes_are_dealt_in_place_order(choam: bool) -> None:
    for conflict in _dealt_conflicts():
        where = conflict.card.card_id
        rewards = conflict_reward_entities(where, choam)
        assert len(rewards) == 3, where
        for entity in rewards:
            assert entity.archetype is not None, where
            assert entity.archetype.kind == "conflict_reward"
            assert _dealt(entity.archetype, choam), where


# -- contracts ----------------------------------------------------------------


def test_contract_table_has_exactly_the_twenty_standard_tiles() -> None:
    assert set(CONTRACT_ARCHETYPES) == {c.card.card_id for c in STANDARD_CONTRACTS}
    assert len(CONTRACT_ARCHETYPES) == 20
    assert len(set(CONTRACT_ARCHETYPES.values())) == 18


def test_contract_archetypes_exist_and_are_dealt_only_with_choam() -> None:
    for contract in STANDARD_CONTRACTS:
        archetype = ARCHETYPES[CONTRACT_ARCHETYPES[contract.card.card_id]]
        assert archetype.kind == "contract"
        assert archetype.in_uprising_choam
        assert not archetype.in_uprising


def test_two_tiles_share_an_archetype_exactly_when_the_app_has_two_copies() -> None:
    by_archetype: dict[str, list[str]] = {}
    for card_id, short in CONTRACT_ARCHETYPES.items():
        by_archetype.setdefault(short, []).append(card_id)
    for short, card_ids in by_archetype.items():
        assert _int_attr(ARCHETYPES[short], "CardCount") == len(card_ids), short
    shared = {tuple(sorted(ids)) for ids in by_archetype.values() if len(ids) == 2}
    assert shared == {
        ("espionage_i", "espionage_i_copy_2"),
        ("harvest_3", "harvest_3_copy_2"),
    }


_CONTRACT_TYPES = {
    ContractConditionKind.BOARD_SPACE: "Space",
    ContractConditionKind.HARVEST_SPICE: "Harvest",
    ContractConditionKind.ACQUIRE_CARD: "Acquire",
    ContractConditionKind.IMMEDIATE: "Immediate",
}


def test_contract_conditions_and_rewards_agree() -> None:
    for contract in STANDARD_CONTRACTS:
        where = contract.card.card_id
        archetype = ARCHETYPES[CONTRACT_ARCHETYPES[where]]
        condition = contract.condition
        reward = contract.reward

        assert _str_attr(archetype, "ContractType") == _CONTRACT_TYPES[condition.kind]
        if condition.kind is ContractConditionKind.BOARD_SPACE:
            # Contracts exist only with CHOAM, so the CHOAM space archetype.
            space = SPACE_ARCHETYPES[condition.target][1]
            assert space in _tuple_attr(archetype, "ReferencedArchetypeIDs"), where
        if condition.kind is ContractConditionKind.HARVEST_SPICE:
            assert _int_attr(archetype, "SpiceCost") == condition.amount, where

        assert _int_attr(archetype, "Solari") == reward.solari, where
        assert _int_attr(archetype, "Water") == reward.water, where
        assert _int_attr(archetype, "Troops") == reward.troops, where

        tags = _tuple_attr(archetype, "Tags")
        abilities = _ability_names(archetype)
        assert ("Spy" in tags) is (reward.spies > 0), where
        assert ("RecallAgent" in tags) is (reward.recall_agents > 0), where
        assert ("Draw2ContractAbility" in abilities) is (reward.personal_cards == 2), (
            where
        )
        assert ("BeneGesseritContractAbility" in abilities) is (
            reward.influence_faction is Faction.BENE_GESSERIT
        ), where
        assert ("TSMFContractAbility" in abilities) is (
            condition.kind is ContractConditionKind.ACQUIRE_CARD
        ), where


# -- leaders ------------------------------------------------------------------


@CHOAM
def test_every_leader_maps_to_an_archetype_dealt_with_that_setting(choam: bool) -> None:
    leaders = leaders_for_choam(choam)
    assert len(leaders) == (9 if choam else 8)
    for leader in leaders:
        short = LEADER_ARCHETYPES[leader.leader_id]
        assert short in ARCHETYPES, leader.leader_id
        archetype = ARCHETYPES[short]
        assert archetype.kind == "leader"
        assert _dealt(archetype, choam), leader.leader_id
        assert archetype.title is not None
        assert _norm(archetype.title) == _norm(leader.name), leader.leader_id


def test_leader_table_has_the_nine_leaders_and_jessicas_flipped_face() -> None:
    expected = {leader.leader_id for leader in leaders_for_choam(True)}
    expected.add("reverend_mother_jessica")
    assert set(LEADER_ARCHETYPES) == expected
    assert len(LEADER_ARCHETYPES) == 10
    assert len(set(LEADER_ARCHETYPES.values())) == 10


def test_shaddam_is_dealt_only_with_choam() -> None:
    shaddam = ARCHETYPES[LEADER_ARCHETYPES["shaddam_corrino_iv"]]
    assert not shaddam.in_uprising
    assert shaddam.in_uprising_choam
    assert LEADERS_BY_ID["shaddam_corrino_iv"].choam_only


def test_lady_jessicas_flipped_face_is_the_apps_leader_upgrade() -> None:
    jessica: LeaderDefinition = LEADERS_BY_ID["lady_jessica"]
    assert jessica.alternate_face_id == "reverend_mother_jessica"
    flipped = ARCHETYPES[LEADER_ARCHETYPES["reverend_mother_jessica"]]
    assert flipped.title == "Reverend Mother Jessica"
    assert flipped.attributes["Flipped"] is True
    assert flipped.in_uprising and flipped.in_uprising_choam
    front = ARCHETYPES[LEADER_ARCHETYPES["lady_jessica"]]
    assert _tuple_attr(front, "LeaderUpgradeArchetypes") == (flipped.short,)

    assert leader_entity("lady_jessica").short == front.short
    assert leader_entity("lady_jessica", "lady_jessica").short == front.short
    assert (
        leader_entity("lady_jessica", "reverend_mother_jessica").short == flipped.short
    )


# -- entity constructors ------------------------------------------------------


def _instance_ids(choam: bool) -> Iterator[tuple[str, str]]:
    """(group, instance id) for every personal card, Intrigue and contract."""

    for instance_id in starting_deck_instance_ids(0):
        yield "card", instance_id
    for stack in RESERVE_STACKS:
        yield "card", f"reserve:{stack.card.card_id}:0"
    for instance_id in imperium_deck_instance_ids(choam):
        yield "card", instance_id
    for instance_id in intrigue_deck_instance_ids(choam):
        yield "intrigue", instance_id
    if choam:
        for instance_id in contract_instance_ids():
            yield "contract", instance_id


@CHOAM
def test_entity_constructors_resolve_every_dealt_instance(choam: bool) -> None:
    seen = 0
    for group, instance_id in _instance_ids(choam):
        if group == "card":
            entity = card_entity(instance_id, 0)
        elif group == "intrigue":
            entity = intrigue_entity(instance_id, 0)
        else:
            entity = contract_entity(instance_id, 0)
        assert entity.archetype is not None, instance_id
        assert entity.ref == instance_id
        assert _dealt(entity.archetype, choam), instance_id
        seen += 1
    # 10 starters + 2 reserve + 65/69 Imperium + 40/44 Intrigue (+ 20 contracts).
    assert seen == (10 + 2 + 69 + 44 + 20 if choam else 10 + 2 + 65 + 40)


@CHOAM
def test_space_and_conflict_entities_pick_the_setting_variant(choam: bool) -> None:
    for space in _core_spaces():
        entity = space_entity(space.space_id, choam)
        assert entity.short == _pair(SPACE_ARCHETYPES, space.space_id, choam)
    for conflict in _dealt_conflicts():
        entity = conflict_entity(conflict.card.card_id, choam)
        assert entity.short == _pair(CONFLICT_ARCHETYPES, conflict.card.card_id, choam)
