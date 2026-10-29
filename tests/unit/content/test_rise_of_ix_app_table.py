"""Rise of Ix's cards against the app's attribute table.

docs/base-game-and-ix-plan.md 17.7, as P3a's ``test_imperium_app_table.py``
did for the original game: the names, copies and costs of Rise of Ix's
Imperium and Intrigue cards come from the Steam app's attribute table
(``agents/app_ai/data/archetypes.py``), and a plain pytest keeps every
identity entry equal to it. ``scripts/dwgr/imperium_entries.py --set ix``
writes the entries from the same table; this test reads it on its own, so a
slip in the generator does not pass unseen. The six Leaders and the three new
Conflict cards (names, tiers), the 18 Tech tiles (names, spice costs, acquire
effects) and the four board spaces (Agent icons, cost, Influence requirement)
are held to the same table.
"""

import re

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.observation_encoding import (
    BATTLE_CARD_IDS,
    CONFLICT_IDS,
    LEADER_IDS,
    SPACE_IDS,
)
from dune_imperium.adapters.observation_encoding import (
    TECH_IDS as OBSERVATION_TECH_IDS,
)
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.content.bloodlines.tech import (
    TECH_IDS,
    TECH_TILES,
    TECH_TILES_BY_ID,
    TechAbility,
    tech_tiles_for,
)
from dune_imperium.content.bloodlines.tech_abilities import (
    TECH_ABILITIES,
    TECH_ACQUIRE_ABILITIES,
)
from dune_imperium.content.imperium.board import IMPERIUM_BOARD_SPACES
from dune_imperium.content.imperium.conflicts import IMPERIUM_CONFLICTS
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.content.imperium.leaders import IMPERIUM_LEADERS
from dune_imperium.content.rise_of_ix.board import IX_BOARD_SPACES, IX_SPACE_IDS
from dune_imperium.content.rise_of_ix.conflicts import IX_CONFLICTS
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.rise_of_ix.intrigue import IX_INTRIGUE_CARDS
from dune_imperium.content.rise_of_ix.leaders import IX_LEADERS
from dune_imperium.content.rise_of_ix.tech import (
    IX_TECH_IDS,
    IX_TECH_TILES,
    IX_TECH_TILES_BY_ID,
)
from dune_imperium.content.rulesets import (
    IMPERIUM_LEADER_IDS,
    IX_LEADER_IDS_OFFERED,
    content_for,
)
from dune_imperium.content.schema import SourceDocument, SourceRef
from dune_imperium.content.uprising.abilities import AbilityTiming
from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    BOARD_SPACES_BY_ID,
    Faction,
    InfluenceRequirement,
    ResourceCost,
)
from dune_imperium.content.uprising.board_abilities import (
    BOARD_CHOICE_ABILITIES,
    BOARD_SPACE_ABILITIES,
)
from dune_imperium.content.uprising.conflicts import (
    CONFLICTS,
    CONFLICTS_BY_ID,
    conflicts_by_tier,
)
from dune_imperium.content.uprising.effect_dsl import (
    DrawIntrigueCards,
    DrawPersonalCards,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    RecruitTroops,
    Reward,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS,
    IMPERIUM_CARDS_BY_ID,
)
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS,
    INTRIGUE_CARDS_BY_ID,
    INTRIGUE_CARDS_BY_INSTANCE,
)
from dune_imperium.content.uprising.leaders import (
    LEADERS,
    LEADERS_BY_ID,
    leaders_for_choam,
)
from dune_imperium.content.uprising.starting_cards import STARTING_CARDS_BY_ID
from dune_imperium.content.uprising.types import AgentIcon, ConflictTier

# The one name Rise of Ix prints that another kind already uses: the
# Bloodlines Leader ``esmar_tuek`` (plan 17.2); it takes ``_card``.
_SUFFIXED = frozenset({"Esmar Tuek"})
_IX_PROMOS = frozenset({"Boundless Ambition"})


def _title(archetype: Archetype) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", archetype.title or "")).strip()


def _id(archetype: Archetype) -> str:
    title = _title(archetype)
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower().replace("'", "")).strip("_")
    return f"{slug}_card" if title in _SUFFIXED else slug


def _imperium_archetypes() -> dict[str, Archetype]:
    # The Imperium deck's Main cards plus the one promo; not Control the
    # Spice, the Epic starting card (``ImperiumType`` Starter).
    return {
        _id(archetype): archetype
        for short, archetype in ARCHETYPES.items()
        if (
            short.startswith("ImperiumArchetypes.RiseOfIx.")
            and archetype.attributes.get("ImperiumType") == "Main"
        )
        or (
            short.startswith("ImperiumArchetypes.Promo.")
            and _title(archetype) in _IX_PROMOS
        )
    }


def _intrigue_archetypes() -> dict[str, Archetype]:
    return {
        _id(archetype): archetype
        for short, archetype in ARCHETYPES.items()
        if short.startswith("IntrigueArchetypes.RiseOfIx.")
    }


def test_every_ix_card_has_an_entry_and_no_more() -> None:
    # 29 Imperium kinds and 35 cards, the promo apart, and 17 Intrigue cards
    # [Rise of Ix p. 2] (docs/rules/rise-of-ix.md 2).
    imperium = {entry.card.card_id: entry for entry in IX_IMPERIUM_CARDS}
    intrigue = {entry.card.card_id: entry for entry in IX_INTRIGUE_CARDS}
    assert len(imperium) == len(IX_IMPERIUM_CARDS)
    assert len(intrigue) == len(IX_INTRIGUE_CARDS)
    assert set(imperium) == set(_imperium_archetypes())
    assert set(intrigue) == set(_intrigue_archetypes())
    deck = [entry for entry in IX_IMPERIUM_CARDS if not entry.promo]
    assert (len(deck), sum(entry.copies for entry in deck)) == (29, 35)
    promos = [entry for entry in IX_IMPERIUM_CARDS if entry.promo]
    assert [(e.card.name, e.copies) for e in promos] == [("Boundless Ambition", 1)]
    assert (len(intrigue), sum(e.copies for e in IX_INTRIGUE_CARDS)) == (17, 17)


def test_the_epic_starting_card_is_not_an_imperium_card() -> None:
    # The app files Control the Spice under Rise of Ix as a Starter; it is
    # Uprising's Epic starting card already (``content.uprising``), and Rise
    # of Ix + Epic uses the same card (plan 17.2).
    starters = [
        archetype
        for short, archetype in ARCHETYPES.items()
        if short.startswith("ImperiumArchetypes.RiseOfIx.")
        and archetype.attributes.get("ImperiumType") != "Main"
    ]
    assert [_title(archetype) for archetype in starters] == ["Control The Spice"]
    assert starters[0].attributes.get("ImperiumType") == "Starter"
    assert "control_the_spice" in STARTING_CARDS_BY_ID
    assert "control_the_spice" not in {e.card.card_id for e in IX_IMPERIUM_CARDS}


def test_names_copies_and_costs_match_the_app() -> None:
    table = _imperium_archetypes()
    for entry in IX_IMPERIUM_CARDS:
        archetype = table[entry.card.card_id]
        assert entry.card.name == _title(archetype), entry.card.card_id
        assert entry.copies == archetype.attributes["CardCount"], entry.card.card_id
        assert entry.acquisition_cost == archetype.attributes.get(
            "PersuasionCost", 0
        ), entry.card.card_id
        assert entry.promo == (".Promo." in archetype.short), entry.card.card_id
    intrigue = _intrigue_archetypes()
    for card in IX_INTRIGUE_CARDS:
        archetype = intrigue[card.card.card_id]
        assert card.card.name == _title(archetype), card.card.card_id
        assert card.copies == archetype.attributes["CardCount"], card.card.card_id


def test_esmar_tuek_takes_the_card_suffix() -> None:
    # The Ix Imperium card and the Bloodlines Leader share a name; the Leader
    # keeps ``esmar_tuek`` and the card is ``esmar_tuek_card`` (plan 17.2).
    ids = {entry.card.card_id: entry for entry in IX_IMPERIUM_CARDS}
    assert "esmar_tuek" not in ids
    assert ids["esmar_tuek_card"].card.name == "Esmar Tuek"
    assert "esmar_tuek" in LEADERS_BY_ID
    assert "esmar_tuek_card" not in LEADERS_BY_ID
    # No other Rise of Ix card takes the suffix.
    assert {card_id for card_id in ids if card_id.endswith("_card")} == {
        "esmar_tuek_card"
    }
    assert not [
        entry.card.card_id
        for entry in IX_INTRIGUE_CARDS
        if entry.card.card_id.endswith("_card")
    ]


def test_no_ix_id_collides_with_an_existing_id() -> None:
    # An id names one printing across the merged lookup tables, so a
    # collision would silently replace a card in them (plan 4.2 7, 17.2).
    ix_imperium = [entry.card.card_id for entry in IX_IMPERIUM_CARDS]
    ix_intrigue = [entry.card.card_id for entry in IX_INTRIGUE_CARDS]
    existing_imperium = {
        entry.card.card_id for entry in (*IMPERIUM_CARDS, *IMPERIUM_BASE_CARDS)
    }
    existing_intrigue = {
        entry.card.card_id for entry in (*INTRIGUE_CARDS, *IMPERIUM_INTRIGUE_CARDS)
    }
    assert not existing_imperium.intersection(ix_imperium)
    assert not existing_intrigue.intersection(ix_intrigue)
    # Nor with a Leader or a starting card; and no id repeats inside the
    # Ix cards, whichever kind they are.
    others = {*LEADERS_BY_ID, *STARTING_CARDS_BY_ID}
    assert not others.intersection(ix_imperium)
    assert not others.intersection(ix_intrigue)
    assert len({*ix_imperium, *ix_intrigue}) == len(ix_imperium) + len(ix_intrigue)
    # The merged tables lost nothing to a collision.
    assert len(IMPERIUM_CARDS_BY_ID) == len(existing_imperium) + len(ix_imperium)
    assert len(INTRIGUE_CARDS_BY_ID) == len(existing_intrigue) + len(ix_intrigue)


def test_ix_cards_resolve_in_the_merged_tables_only() -> None:
    for entry in IX_IMPERIUM_CARDS:
        assert IMPERIUM_CARDS_BY_ID[entry.card.card_id] is entry
    for card in IX_INTRIGUE_CARDS:
        assert INTRIGUE_CARDS_BY_ID[card.card.card_id] is card
        for copy in range(card.copies):
            instance = f"intrigue:{card.card.card_id}:{copy}"
            assert INTRIGUE_CARDS_BY_INSTANCE[instance] is card
    # Code that lists Uprising's or the original game's own cards does not
    # see them: the observation, the slots, the server catalog and the decks
    # list those tuples (plan 17.1: they take Rise of Ix at v39).
    ix_ids = {e.card.card_id for e in IX_IMPERIUM_CARDS}
    ix_ids |= {e.card.card_id for e in IX_INTRIGUE_CARDS}
    listed = {e.card.card_id for e in (*IMPERIUM_CARDS, *IMPERIUM_BASE_CARDS)}
    listed |= {e.card.card_id for e in (*INTRIGUE_CARDS, *IMPERIUM_INTRIGUE_CARDS)}
    assert not ix_ids & listed


# The cards transcribed so far (stage P4d, one per commit).
_IX_INTRIGUE_TRANSCRIBED = {
    "blackmail",
    "cull",
    "glimpse_the_path",
    "expedite",
    "finesse",
    "secret_forces",
    "strongarm",
    "ixian_probe",
    "quid_pro_quo",
}
_IX_IMPERIUM_TRANSCRIBED = {
    "imperial_shock_trooper",
    "jamis",
    "local_fence",
    "sayyadina",
    "truthsayer",
}


def test_ix_entries_are_identities_only() -> None:
    # Stage P4a lists the cards before their play data (plan 17.7); a
    # transcribed card replaces its entry and the deck then takes it.
    for entry in IX_IMPERIUM_CARDS:
        done = entry.card.card_id in _IX_IMPERIUM_TRANSCRIBED
        assert entry.play_data_complete is done, entry.card.card_id
        if not done:
            assert entry.factions == () and entry.agent_icons == (), entry.card.card_id
    for card in IX_INTRIGUE_CARDS:
        done = card.card.card_id in _IX_INTRIGUE_TRANSCRIBED
        assert card.play_data_complete is done, card.card.card_id
        assert bool(card.options) is done, card.card.card_id


def test_ix_entries_cite_the_component_table() -> None:
    sources = (SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (2,)),)
    for entry in (*IX_IMPERIUM_CARDS, *IX_INTRIGUE_CARDS):
        assert entry.card.sources == sources, entry.card.card_id


# --- Leaders (docs/rules/rise-of-ix.md 10) ----------------------------------

# The left ability and the Signet Ring of each Leader, from docs/rules/
# rise-of-ix.md 10 (the app's attribute table lists the ability classes of a
# Leader together, so it does not say which is the Signet).
_IX_LEADER_ABILITIES = {
    "archduke_armand_ecaz": ("Coordination", "Conscript"),
    "ilesa_ecaz": ("One Step Ahead", "Guild Contacts"),
    "prince_rhombur_vernius": ("Heavy Lasgun Cannons", "Ixian Technology"),
    "princess_yuna_moritani": ("Smuggling Operation", "Final Delivery"),
    "tessia_vernius": ("Careful Observation", "Duplicity"),
    "viscount_hundro_moritani": ("Intelligence", "Couriers"),
}


def _leader_archetypes() -> dict[str, Archetype]:
    return {
        _id(archetype): archetype
        for short, archetype in ARCHETYPES.items()
        if short.startswith("LeaderArchetypes.RiseOfIx.")
    }


def _ability_classes(archetype: Archetype) -> str:
    abilities = archetype.attributes["WormAbilityIDs"]
    assert isinstance(abilities, tuple)
    return " ".join(str(name).rsplit(".", 1)[-1] for name in abilities)


def test_every_ix_leader_has_an_entry_and_no_more() -> None:
    # Six Leaders [Rise of Ix p. 2] (docs/rules/rise-of-ix.md 2).
    ids = [leader.leader_id for leader in IX_LEADERS]
    assert len(ids) == len(set(ids)) == 6
    assert set(ids) == set(_leader_archetypes())
    assert set(ids) == set(_IX_LEADER_ABILITIES)


def test_leader_names_match_the_app() -> None:
    table = _leader_archetypes()
    for leader in IX_LEADERS:
        assert leader.name == _title(table[leader.leader_id]), leader.leader_id
    # The one title with quotation marks keeps them, and its id drops them.
    names = {leader.leader_id: leader.name for leader in IX_LEADERS}
    assert names["princess_yuna_moritani"] == '"Princess" Yuna Moritani'


def test_leader_ability_names_match_the_app_and_the_rules() -> None:
    # The app names an ability by its class (``CoordinationAbility``,
    # ``OneStepAheadRoundAbility``), so each printed name, without spaces, is
    # the start of one of the Leader's classes; which of the two is the
    # Signet Ring is docs/rules/rise-of-ix.md 10.
    table = _leader_archetypes()
    for leader in IX_LEADERS:
        classes = _ability_classes(table[leader.leader_id]).split()
        assert (leader.ability_name, leader.signet_name) == _IX_LEADER_ABILITIES[
            leader.leader_id
        ], leader.leader_id
        for name in (leader.ability_name, leader.signet_name):
            assert name is not None
            assert any(
                cls.startswith(name.replace(" ", "")) and cls.endswith("Ability")
                for cls in classes
            ), (leader.leader_id, name, classes)
        assert leader.alternate_face_id is None, leader.leader_id


def test_ix_leaders_are_identities_only() -> None:
    # Stage P4a lists the Leaders before their setup deviations and abilities
    # (stage P4e, plan 17.1): Yuna's water, Hundro's Intrigue look and
    # Tessia's Snooper tokens are not wired, and no printed start differs.
    for leader in IX_LEADERS:
        assert leader.starting_water == 1, leader.leader_id
        assert leader.extra_starting_spice == 0, leader.leader_id
        assert leader.extra_starting_solari == 0, leader.leader_id
        assert leader.removed_starting_card_ids == (), leader.leader_id
        assert not (
            leader.choam_only
            or leader.bloodlines_only
            or leader.tech_only
            or leader.uses_feyd_token
            or leader.uses_tactics_track
            or leader.uses_twisted_intrigue
        ), leader.leader_id


def test_ix_leaders_cite_the_component_table_and_the_card_face() -> None:
    sources = (
        SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (2,)),
        SourceRef(SourceDocument.CARD_FACE, (1,)),
    )
    for leader in IX_LEADERS:
        assert leader.sources == sources, leader.leader_id


# --- Conflicts (docs/rules/rise-of-ix.md 12) --------------------------------


def _conflict_id(archetype: Archetype) -> str:
    # ``…RiseOfIx.SkirmishE`` -> ``skirmish_e``: two cards share the title.
    last = archetype.short.rsplit(".", 1)[-1]
    return re.sub(r"(?<!^)(?=[A-Z])", "_", last).lower()


def _conflict_archetypes() -> dict[str, Archetype]:
    # Economic Supremacy is Uprising's Epic Conflict already (OQ-094).
    return {
        _conflict_id(archetype): archetype
        for short, archetype in ARCHETYPES.items()
        if short.startswith("ConflictArchetypes.RiseOfIx.")
        and _title(archetype) != "Economic Supremacy"
    }


def test_every_new_ix_conflict_has_an_entry_and_no_more() -> None:
    # Rise of Ix prints four Conflict cards, I 2, II 1 and III 1 [Rise of Ix
    # p. 2] (docs/rules/rise-of-ix.md 2); the Conflict III, Economic
    # Supremacy, is not defined again.
    ids = [conflict.card.card_id for conflict in IX_CONFLICTS]
    assert ids == ["skirmish_e", "skirmish_f", "trade_monopoly"]
    assert set(ids) == set(_conflict_archetypes())
    assert "economic_supremacy" not in ids
    economic = CONFLICTS_BY_ID["economic_supremacy"]
    assert economic in CONFLICTS and economic.epic_only
    assert economic.tier is ConflictTier.THREE
    tiers = [conflict.tier for conflict in IX_CONFLICTS]
    assert tiers.count(ConflictTier.ONE) == 2
    assert tiers.count(ConflictTier.TWO) == 1


def test_conflict_names_and_tiers_match_the_app() -> None:
    table = _conflict_archetypes()
    for conflict in IX_CONFLICTS:
        archetype = table[conflict.card.card_id]
        assert conflict.card.name == _title(archetype), conflict.card.card_id
        level = archetype.attributes["ConflictLevel"]
        assert isinstance(level, int)
        assert conflict.tier == ConflictTier(level), conflict.card.card_id
    assert [(c.card.name, c.tier) for c in IX_CONFLICTS] == [
        ("Skirmish", ConflictTier.ONE),
        ("Skirmish", ConflictTier.ONE),
        ("Trade Monopoly", ConflictTier.TWO),
    ]


def test_new_ix_conflicts_print_no_battle_icon_and_take_no_control() -> None:
    # The original game prints no battle icon and the app's table gives these
    # cards none (an Uprising Conflict has a ``BattleIcon`` attribute);
    # Economic Supremacy prints none either (OQ-094). Their rewards are
    # transcribed since stage P4d-1 (three rows from the app's three ability
    # classes each); the app tags each of the three "Freighter", and none
    # takes control of a space (docs/rules/rise-of-ix.md 12).
    table = _conflict_archetypes()
    for conflict in IX_CONFLICTS:
        attributes = table[conflict.card.card_id].attributes
        assert "BattleIcon" not in attributes
        assert attributes["Tags"] == ("Freighter",), conflict.card.card_id
        worm = attributes["WormAbilityIDs"]
        assert isinstance(worm, tuple) and len(worm) == 3, conflict.card.card_id
        assert conflict.battle_icon is None, conflict.card.card_id
        assert conflict.reward_rows is not None, conflict.card.card_id
        assert len(conflict.reward_rows) == 3, conflict.card.card_id
        assert not conflict.shield_wall_protected, conflict.card.card_id
        assert not conflict.bloodlines_only, conflict.card.card_id
        assert not conflict.epic_only, conflict.card.card_id
        assert conflict.control_space_id is None, conflict.card.card_id


def test_new_ix_conflicts_cite_the_component_table_and_setup() -> None:
    sources = (SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (2, 3)),)
    for conflict in IX_CONFLICTS:
        assert conflict.card.sources == sources, conflict.card.card_id


# --- Ids and the merged lookups ----------------------------------------------


def test_no_ix_leader_or_conflict_id_collides_with_an_existing_id() -> None:
    # An id names one printing across the merged lookup tables (plan 4.2 7,
    # 17.2): a collision would silently replace a Leader or Conflict in them.
    # The original game's Skirmishes are ``skirmish_a`` to ``skirmish_d``.
    ix_leaders = [leader.leader_id for leader in IX_LEADERS]
    ix_conflicts = [conflict.card.card_id for conflict in IX_CONFLICTS]
    existing_leaders = {leader.leader_id for leader in (*LEADERS, *IMPERIUM_LEADERS)}
    existing_conflicts = {
        conflict.card.card_id for conflict in (*CONFLICTS, *IMPERIUM_CONFLICTS)
    }
    assert not existing_leaders.intersection(ix_leaders)
    assert not existing_conflicts.intersection(ix_conflicts)
    assert {"skirmish_a", "skirmish_b", "skirmish_c", "skirmish_d"} <= (
        existing_conflicts
    )
    # Nor with a card of any kind, a Leader's id with a Conflict's, or each
    # other.
    ids = [*ix_leaders, *ix_conflicts]
    assert len(set(ids)) == len(ids)
    others = {
        *IMPERIUM_CARDS_BY_ID,
        *INTRIGUE_CARDS_BY_ID,
        *STARTING_CARDS_BY_ID,
        *(entry.card.card_id for entry in IX_IMPERIUM_CARDS),
        *(entry.card.card_id for entry in IX_INTRIGUE_CARDS),
    }
    assert not others.intersection(ids)
    # The merged tables lost nothing to a collision.
    assert len(LEADERS_BY_ID) == len(existing_leaders) + len(ix_leaders)
    assert len(CONFLICTS_BY_ID) == len(existing_conflicts) + len(ix_conflicts)


def test_ix_leaders_and_conflicts_resolve_in_the_merged_tables() -> None:
    for leader in IX_LEADERS:
        assert LEADERS_BY_ID[leader.leader_id] is leader
    for conflict in IX_CONFLICTS:
        assert CONFLICTS_BY_ID[conflict.card.card_id] is conflict


def test_no_uprising_or_original_game_pool_lists_an_ix_leader_or_conflict() -> None:
    # Code that lists Uprising's or the original game's own Leaders and
    # Conflicts iterates these tuples and the Uprising pools; none holds the
    # Ix entries. Only the original game's content with ``rise_of_ix`` offers
    # them (stage P4a's board axis; the Leaders as they are wired, P4e). The
    # observation's universes list them at their end since v39 (plan 17.1,
    # 17.8), after every older identity.
    leader_ids = {leader.leader_id for leader in IX_LEADERS}
    conflict_ids = {conflict.card.card_id for conflict in IX_CONFLICTS}
    listed_leaders = {leader.leader_id for leader in (*LEADERS, *IMPERIUM_LEADERS)}
    listed_conflicts = {c.card.card_id for c in (*CONFLICTS, *IMPERIUM_CONFLICTS)}
    assert not leader_ids & listed_leaders
    assert not conflict_ids & listed_conflicts
    assert not leader_ids & set(IMPERIUM_LEADER_IDS)
    assert LEADER_IDS[-len(IX_LEADERS) :] == tuple(
        leader.leader_id for leader in IX_LEADERS
    )
    assert not leader_ids & set(LEADER_IDS[: -len(IX_LEADERS)])
    assert CONFLICT_IDS[-len(IX_CONFLICTS) :] == tuple(
        conflict.card.card_id for conflict in IX_CONFLICTS
    )
    assert not conflict_ids & set(CONFLICT_IDS[: -len(IX_CONFLICTS)])
    assert not conflict_ids & set(BATTLE_CARD_IDS)
    for choam_module in (False, True):
        for bloodlines in (False, True):
            for tech_module in (False, True):
                pool = leaders_for_choam(
                    choam_module, bloodlines=bloodlines, tech_module=tech_module
                )
                assert not leader_ids & {leader.leader_id for leader in pool}
    for tier in ConflictTier:
        for bloodlines in (False, True):
            for epic_game in (False, True):
                pool_ids = {
                    c.card.card_id
                    for c in conflicts_by_tier(
                        tier, bloodlines=bloodlines, epic_game=epic_game
                    )
                }
                assert not conflict_ids & pool_ids
    # The content of every game either base game sets up, Rise of Ix on or off:
    # the Ix Leaders and the Conflicts transcribed so far are the original
    # game with Rise of Ix's alone (Uprising plus Rise of Ix is stage P7).
    for base_game in BaseGame:
        for rise_of_ix in (False, True):
            for epic_game in (False, True):
                config = RulesetConfig(
                    base_game=base_game, rise_of_ix=rise_of_ix, epic_game=epic_game
                )
                content = content_for(config)
                offered_leaders = {x.leader_id for x in content.leaders}
                offered_conflicts = {x.card.card_id for x in content.conflicts}
                offered_pool = {x.card.card_id for x in content.conflict_pool}
                if base_game is BaseGame.IMPERIUM and rise_of_ix:
                    # A Conflict joins once its rewards are transcribed.
                    transcribed = {
                        c.card.card_id
                        for c in IX_CONFLICTS
                        if c.reward_rows is not None
                    }
                    # A Leader joins once its abilities are wired (held
                    # back until stage P4e, rulesets.IX_LEADER_IDS_OFFERED).
                    assert leader_ids & offered_leaders == set(IX_LEADER_IDS_OFFERED)
                    assert conflict_ids & offered_conflicts == transcribed
                    assert conflict_ids & offered_pool == transcribed
                else:
                    assert not leader_ids & offered_leaders
                    assert not conflict_ids & offered_conflicts
                    assert not conflict_ids & offered_pool


# --- Tech tiles (docs/rules/rise-of-ix.md 4) ---------------------------------

# The app's ``AcquireEffectList`` names and the piece each prints; repeated
# names are one piece's count (as Self-Destroying Messages' two Intrigue).
def _acquire_piece(name: str, count: int) -> Reward:
    match name:
        case "Intrigue":
            return DrawIntrigueCards(count)
        case "Troop":
            return RecruitTroops(count)
        case "VP":
            return GainVictoryPoints(count)
        case "Imperium":
            return DrawPersonalCards(count)
        case "Water":
            return GainResources(water=count)
        case "Trash":
            return TrashPersonalCard()
        case "AnyRank":
            return GainInfluence()
        case "AnyTwoDifferentRanks":
            # "Choose two" Factions: two different ones (OQ-114).
            return GainInfluence(times=2, distinct=True)
    raise AssertionError(f"no acquire piece for the app's {name!r}")


def _slug(archetype: Archetype) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _title(archetype).lower()).strip("_")


def _tech_archetypes() -> dict[str, Archetype]:
    return {
        _slug(archetype): archetype
        for short, archetype in ARCHETYPES.items()
        if short.startswith("TechTileArchetypes.RiseOfIx.")
    }


def test_every_ix_tech_tile_has_an_entry_and_no_more() -> None:
    assert len(IX_TECH_TILES) == 18
    assert list(IX_TECH_IDS) == sorted(_tech_archetypes())
    assert set(IX_TECH_TILES_BY_ID) == set(IX_TECH_IDS)


def test_tech_names_and_costs_match_the_app_and_the_rules_table() -> None:
    archetypes = _tech_archetypes()
    for tile in IX_TECH_TILES:
        archetype = archetypes[tile.tech_id]
        assert tile.name == _title(archetype), tile.tech_id
        assert tile.cost == archetype.attributes["SpiceCost"], tile.tech_id
        assert not tile.choam_only and not tile.rival, tile.tech_id
        assert tile.sources == (SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (2, 4)),)
    # docs/rules/rise-of-ix.md 4: Flagship 8 is the dearest, Artillery 1 the
    # cheapest; the 18 costs sum to 65.
    assert IX_TECH_TILES_BY_ID["flagship"].cost == 8
    assert IX_TECH_TILES_BY_ID["artillery"].cost == 1
    assert sum(tile.cost for tile in IX_TECH_TILES) == 65


def test_tech_acquire_records_are_the_apps_acquire_effects() -> None:
    archetypes = _tech_archetypes()
    for tile in IX_TECH_TILES:
        effects = archetypes[tile.tech_id].attributes.get("AcquireEffectList", ())
        assert isinstance(effects, tuple)
        record = TECH_ACQUIRE_ABILITIES.get(tile.tech_id)
        if not effects:
            assert record is None, tile.tech_id
            continue
        assert record is not None, tile.tech_id
        assert record.timing is AbilityTiming.ACQUIRE
        expected = tuple(
            _acquire_piece(str(name), effects.count(name))
            for name in dict.fromkeys(effects)
        )
        assert tuple(line.rewards[0] for line in record.sections) == expected, (
            tile.tech_id
        )
    assert {tile.tech_id for tile in IX_TECH_TILES} & set(TECH_ACQUIRE_ABILITIES) == {
        "chaumurky",
        "disposal_facility",
        "flagship",
        "invasion_ships",
        "memocorders",
        "shuttle_fleet",
        "sonic_snoopers",
        "spaceport",
        "windtraps",
    }


def test_every_ix_acquire_icon_has_a_key_since_stage_p4c_2a() -> None:
    # Windtraps' water and Shuttle Fleet's two Factions had no key before
    # stage P4c-2a (a key would drop the water and pay one Influence), so the
    # tiles refused theirs; each has its own key now.
    keys = {tile.tech_id: tile.acquire_effect_keys for tile in IX_TECH_TILES}
    assert {tech_id: value for tech_id, value in keys.items() if value} == {
        "chaumurky": ("intrigue",),
        "disposal_facility": ("trash",),
        "flagship": ("victory_points",),
        "invasion_ships": ("troops",),
        "memocorders": ("influence",),
        "shuttle_fleet": ("distinct_influence",),
        "sonic_snoopers": ("intrigue",),
        "spaceport": ("cards",),
        "windtraps": ("water",),
    }
    assert IX_TECH_TILES_BY_ID["invasion_ships"].acquire_troops == 4
    assert IX_TECH_TILES_BY_ID["spaceport"].acquire_cards == 2
    assert IX_TECH_TILES_BY_ID["windtraps"].acquire_water == 1
    assert IX_TECH_TILES_BY_ID["shuttle_fleet"].acquire_distinct_influence
    assert not IX_TECH_TILES_BY_ID["shuttle_fleet"].acquire_influence_choice


def test_each_ix_tile_names_an_ability_of_its_own_and_has_no_record() -> None:
    abilities = [tile.ability for tile in IX_TECH_TILES]
    assert len(set(abilities)) == 18
    assert not set(abilities) & {tile.ability for tile in TECH_TILES}
    assert set(TechAbility) == set(abilities) | {tile.ability for tile in TECH_TILES}
    # The flips, Reveal and Endgame lines and hooks are stage P4c's.
    assert not set(IX_TECH_IDS) & set(TECH_ABILITIES)


def test_ix_tech_tiles_resolve_by_id_only() -> None:
    # No id collides with a Tech Module tile or any other identity, and no
    # stack, setup or list of the Tech Module holds an Ix tile.
    assert not set(IX_TECH_IDS) & set(TECH_IDS)
    others = {
        *IMPERIUM_CARDS_BY_ID,
        *INTRIGUE_CARDS_BY_ID,
        *LEADERS_BY_ID,
        *CONFLICTS_BY_ID,
        *BOARD_SPACES_BY_ID,
        *STARTING_CARDS_BY_ID,
    }
    assert not set(IX_TECH_IDS) & others
    for tile in IX_TECH_TILES:
        assert TECH_TILES_BY_ID[tile.tech_id] is tile
    assert len(TECH_TILES_BY_ID) == len(TECH_TILES) + len(IX_TECH_TILES)
    for choam_module in (False, True):
        assert not set(IX_TECH_IDS) & {t.tech_id for t in tech_tiles_for(choam_module)}
    # The observation lists them after the Tech Module's (v39, plan 17.8).
    assert OBSERVATION_TECH_IDS == (*TECH_IDS, *IX_TECH_IDS)


# --- Board spaces (docs/rules/rise-of-ix.md 8) -------------------------------

_SPACE_ARCHETYPES = {
    "dreadnought": "SpaceArchetypes.RiseOfIx.DreadnoughtSpace",
    "tech_negotiation": "SpaceArchetypes.RiseOfIx.TechNegotiation",
    "interstellar_shipping": "SpaceArchetypes.RiseOfIx.InterstellarShipping",
    "smuggling": "SpaceArchetypes.RiseOfIx.Smuggling",
}
_ICONS = {"Pentagon": AgentIcon.LANDSRAAD, "Triangle": AgentIcon.SPICE_TRADE}


def test_ix_spaces_match_the_rules_table_and_the_app() -> None:
    # Plan 17.2's ids, in the order observation v39 reserved for them.
    assert IX_SPACE_IDS == (
        "dreadnought",
        "tech_negotiation",
        "interstellar_shipping",
        "smuggling",
    )
    assert {
        short
        for short in ARCHETYPES
        if short.startswith("SpaceArchetypes.RiseOfIx.")
    } == set(_SPACE_ARCHETYPES.values())
    for space in IX_BOARD_SPACES:
        attributes = ARCHETYPES[_SPACE_ARCHETYPES[space.space_id]].attributes
        assert space.name == ARCHETYPES[_SPACE_ARCHETYPES[space.space_id]].title
        assert space.agent_icon is _ICONS[str(attributes["AgentIcon"])]
        solari = attributes.get("SolariCost", 0)
        assert isinstance(solari, int)
        assert space.cost_options == (
            (ResourceCost(solari=solari),) if solari else ()
        ), space.space_id
        requirements = attributes.get("InfluenceRequirements", ())
        assert (space.requirement is None) is (not requirements), space.space_id
        assert not (space.combat or space.maker or space.critical)
        assert space.dynamic_cost is None and space.required_leader_id is None
    # docs/rules/rise-of-ix.md 8: Dreadnought costs 3 Solari, Interstellar
    # Shipping needs 2 Spacing Guild Influence.
    by_id = {space.space_id: space for space in IX_BOARD_SPACES}
    assert by_id["interstellar_shipping"].requirement == InfluenceRequirement(
        Faction.SPACING_GUILD, 2
    )
    assert by_id["dreadnought"].cost_options == (ResourceCost(solari=3),)


def test_ix_spaces_resolve_by_id_and_print_their_icons() -> None:
    for space in IX_BOARD_SPACES:
        assert BOARD_SPACES_BY_ID[space.space_id] is space
    assert not set(IX_SPACE_IDS) & {s.space_id for s in IMPERIUM_BOARD_SPACES}
    assert not set(IX_SPACE_IDS) & {s.space_id for s in BOARD_SPACES}
    # Their printed icons are records since stage P4c-4
    # (``content.rise_of_ix.board_abilities``), none of them a choice flow.
    printed = {space for space, _, _ in BOARD_SPACE_ABILITIES}
    assert set(IX_SPACE_IDS) <= printed
    assert not set(IX_SPACE_IDS) & {space for space, _ in BOARD_CHOICE_ABILITIES}
    # Only the original game with ``rise_of_ix`` lists them (the CHOAM
    # overlay's swap, stage P4a's board axis, ``test_rise_of_ix_board_axis``);
    # Uprising plus Rise of Ix is stage P7.
    for base_game in BaseGame:
        for rise_of_ix in (False, True):
            config = RulesetConfig(base_game=base_game, rise_of_ix=rise_of_ix)
            spaces = {space.space_id for space in content_for(config).board_spaces}
            if base_game is BaseGame.IMPERIUM and rise_of_ix:
                assert set(IX_SPACE_IDS) <= spaces
            else:
                assert not set(IX_SPACE_IDS) & spaces
    # The observation lists them after every other space (v39, plan 17.8).
    assert SPACE_IDS[-4:] == IX_SPACE_IDS
    assert not set(IX_SPACE_IDS) & set(SPACE_IDS[:-4])


def test_infiltration_icons_match_the_app_table() -> None:
    """'그 아이콘의 칸에서 상대 Agent(여럿이어도)를 무시' [Rise of Ix p. 7]."""
    icons = {
        "Circle": AgentIcon.CITY,
        "Triangle": AgentIcon.SPICE_TRADE,
        "Pentagon": AgentIcon.LANDSRAAD,
        "Emperor": AgentIcon.EMPEROR,
        "SpacingGuild": AgentIcon.SPACING_GUILD,
        "BeneGesserit": AgentIcon.BENE_GESSERIT,
        "Fremen": AgentIcon.FREMEN,
    }
    table = _imperium_archetypes()
    for entry in IX_IMPERIUM_CARDS:
        printed = table[entry.card.card_id].attributes.get("InfiltrationIconList", ())
        assert isinstance(printed, tuple)
        assert entry.infiltration_icons == tuple(icons[name] for name in printed)
    assert sum(bool(entry.infiltration_icons) for entry in IX_IMPERIUM_CARDS) == 7
    assert all(
        not entry.infiltration_icons
        for entry in (*IMPERIUM_CARDS, *IMPERIUM_BASE_CARDS)
    )
