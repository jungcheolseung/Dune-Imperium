"""Integrity tests for the Arrakeen Scouts catalog (no extraction needed)."""

import hashlib
import itertools
from collections import Counter
from collections.abc import Sequence
from typing import Final, Protocol

import pytest

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.adapters.observation_encoding import SCOUTS_ITEM_IDS
from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS,
    EVENTS,
    EVENTS_BY_ID,
    MISSIONS,
    MISSIONS_BY_ID,
    SALES,
    SALES_BY_ID,
    SUBCOMMITTEES,
    AuctionKind,
    AuctionSlot,
    EventKind,
    ScoutsPool,
    auctions_for,
    base_game_pools,
    events_for,
    missions_for,
    sales_for,
    scouts_pool,
    scouts_rise_of_ix,
    subcommittees_for,
)
from dune_imperium.content.arrakeen_scouts.types import (
    EVENT_TICKET_SCALE,
    IMPERIUM_POOLS,
    UPRISING_POOLS,
)
from dune_imperium.content.core.effects import (
    AcquireReserveCardToHand,
    PayResources,
    RecruitToConflict,
)
from dune_imperium.content.registry.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.rulesets import content_for
from dune_imperium.rules.setup import _require_content


def test_pool_follows_the_base_game_and_the_immortality_option() -> None:
    """The app's pools by base game and Immortality (plan 20.1); Rise of Ix
    filters missions within them and Bloodlines changes nothing."""

    def pool(**options: object) -> ScoutsPool:
        return scouts_pool(RulesetConfig(**options))  # type: ignore[arg-type]

    assert pool() is ScoutsPool.UPRISING
    assert pool(immortality=True) is ScoutsPool.UPRISING_IMMORTALITY
    assert pool(base_game=BaseGame.IMPERIUM) is ScoutsPool.IMPERIUM
    assert (
        pool(base_game=BaseGame.IMPERIUM, immortality=True)
        is ScoutsPool.IMPERIUM_IMMORTALITY
    )
    assert pool(rise_of_ix=True, bloodlines=True, tech_module=True) is (
        ScoutsPool.UPRISING
    )


def test_each_table_lists_the_uprising_items_first() -> None:
    """Every table keeps the Uprising pools' items ahead of the original
    game's own, so an Uprising catalog or observation column never moves
    (stage P8, ``content.arrakeen_scouts``)."""

    for table in (SUBCOMMITTEES, MISSIONS, EVENTS, AUCTIONS, SALES):
        uprising = [
            any(pool in UPRISING_POOLS for pool in entry.pools) for entry in table
        ]
        assert uprising == sorted(uprising, reverse=True)


# --- Pins for the Uprising side (Codex review of P8a, 2026-10-31) -----------
# Stage P8 appends the original game's items after the Uprising ones; these
# pins keep the Uprising order itself, which sets the action catalog's rows
# and the observation's columns (``observation_encoding.SCOUTS_ITEM_IDS``).
_UPRISING_SUBCOMMITTEES: Final = (
    "appropriations",
    "intelligence",
    "readiness",
    "choam_coordination",
    "growth_project",
    "oversight",
    "investigations",
    "forecasting",
    "choam_management",
    "analytics",
    "relations",
    "contingencies",
    "leverage",
    "tleilaxu_relations",
)
_UPRISING_MISSIONS: Final = (
    "security_detail",
    "imperial_reserve",
    "desert_riding",
    "urban_surveillance",
    "planetary_exploration",
    "choam_research",
    "choam_escort",
    "sponsored_research",
    "back_room_deal",
    "prison_planet",
    "emperors_schemes",
    "fedaykin_assistance",
    "weirding_warfare",
    "send_for_aid",
    "coordinate_with_the_emperor",
    "tleilaxu_offering",
    "secret_stash",
    "armed_escort",
    "stowaways",
)
_UPRISING_EVENTS: Final = (
    "private_stock",
    "market_research",
    "smoke_and_mirrors",
    "rotating_doors",
    "moment_of_revelation",
    "water_discipline",
    "royal_delegation",
    "guild_negotiation",
    "covert_assistance",
    "gift_of_water",
    "share_intelligence",
    "political_equilibrium",
    "crackdown",
    "water_for_spice_smugglers",
    "bene_gesserit_treachery",
    "funeral_rites",
    "covert_operation",
    "covert_operation_choam",
    "mating_season",
    "unlikely_allies",
    "clear_the_market",
    "clear_the_market_choam",
    "market_opening",
    "eyes_on_arrakis",
    "friends_everywhere",
    "rebuild_infrastructure",
    "choam_bargain",
    "ingratiate",
    "betrayal",
    "new_innovations",
    "termination_request",
    "offworld_operation",
)
_UPRISING_AUCTIONS: Final = (
    "highest_bidder_mid",
    "highest_bidder_late",
    "mercenaries",
    "competitive_study_mid",
    "competitive_study_late",
    "spies_for_hire_mid",
    "spies_for_hire_late",
    "critical_moment_mid",
    "critical_moment_late",
    "choam_negotiations_mid",
    "choam_negotiations_late",
)
_UPRISING_SALES: Final = (
    "unravel_the_future",
    "imperium_connections",
    "secrets_for_sale",
    "shadow_warfare",
)
# The action catalogs of Uprising games with Arrakeen Scouts at P8a's start
# (master 6c42e88f): size and the first 16 hex of sha256 over the rows.
# Since the collect click (OQ-164, user decision 2026-11-01) each holds one
# row more, ``scouts_collect_reward``; every other row stays as it was, in
# its order (the digest is taken without the new row).
_COLLECT_ROW: Final = "scouts_collect_reward"
_UPRISING_SCOUTS_CATALOGS: Final = {
    "scouts": (1649, "9c472e40b37c76a2"),
    "scouts_choam": (1797, "4df9676eb3c3f828"),
    "scouts_choam_immortality": (2855, "68c3ff81a1ddec9f"),
    "scouts_everything_ix": (6464, "e6df4a2accd3b156"),
}
_UPRISING_SCOUTS_CONFIGS: Final = {
    "scouts": RulesetConfig(arrakeen_scouts=True),
    "scouts_choam": RulesetConfig(arrakeen_scouts=True, choam_module=True),
    "scouts_choam_immortality": RulesetConfig(
        arrakeen_scouts=True, choam_module=True, immortality=True
    ),
    "scouts_everything_ix": RulesetConfig(
        arrakeen_scouts=True,
        choam_module=True,
        immortality=True,
        rise_of_ix=True,
        bloodlines=True,
        tech_module=True,
        promo_cards=True,
    ),
}


class _Pooled(Protocol):
    @property
    def pools(self) -> tuple[ScoutsPool, ...]: ...


def _uprising_side(entries: Sequence[_Pooled], key: str) -> tuple[str, ...]:
    return tuple(
        str(getattr(entry, key))
        for entry in entries
        if any(pool in UPRISING_POOLS for pool in entry.pools)
    )


def test_the_uprising_side_keeps_its_order() -> None:
    """Every Uprising item keeps its place in its table and in the
    observation vocabulary; the original game's come after them all."""

    assert _uprising_side(SUBCOMMITTEES, "subcommittee_id") == _UPRISING_SUBCOMMITTEES
    assert _uprising_side(MISSIONS, "mission_id") == _UPRISING_MISSIONS
    assert _uprising_side(EVENTS, "event_id") == _UPRISING_EVENTS
    assert _uprising_side(AUCTIONS, "auction_id") == _UPRISING_AUCTIONS
    assert _uprising_side(SALES, "sale_id") == _UPRISING_SALES
    ix = tuple(entry.mission_id for entry in MISSIONS if entry.rise_of_ix_only)
    uprising_columns = (
        *_UPRISING_SUBCOMMITTEES,
        *(mission for mission in _UPRISING_MISSIONS if mission not in ix),
        *_UPRISING_EVENTS,
        *_UPRISING_AUCTIONS,
        *_UPRISING_SALES,
        *ix,
    )
    assert SCOUTS_ITEM_IDS[: len(uprising_columns)] == uprising_columns


@pytest.mark.parametrize("name", list(_UPRISING_SCOUTS_CATALOGS))
def test_the_uprising_scouts_catalogs_keep_every_row(name: str) -> None:
    catalog = ActionCodec(_UPRISING_SCOUTS_CONFIGS[name]).catalog
    kept = [template for template in catalog if template.action_id != _COLLECT_ROW]
    assert len(catalog) - len(kept) == 1
    rows = repr([(template.action_id, template.arguments) for template in kept])
    digest = hashlib.sha256(rows.encode()).hexdigest()[:16]
    assert (len(kept), digest) == _UPRISING_SCOUTS_CATALOGS[name]


def _setup_configs() -> list[RulesetConfig]:
    """Every option combination setup takes on either base game (the Leader
    draft and the seat-zero deal change nothing the pool reads)."""

    names = (
        "rise_of_ix",
        "immortality",
        "bloodlines",
        "tech_module",
        "choam_module",
        "epic_game",
        "go_to_11",
        "promo_cards",
        "imperium_cards",
    )
    configs = []
    for base_game in BaseGame:
        for values in itertools.product((False, True), repeat=len(names)):
            options = dict(zip(names, values, strict=True))
            try:
                config = RulesetConfig(
                    base_game=base_game, arrakeen_scouts=True, **options
                )
                _require_content(config)
            except (ValueError, NotImplementedError):
                continue
            configs.append(config)
    return configs


@pytest.mark.parametrize("config", _setup_configs(), ids=lambda c: c.identifier)
def test_every_setup_picks_its_pool_and_rise_of_ix_missions(
    config: RulesetConfig,
) -> None:
    """The pool follows the base game and Immortality alone; Bloodlines, the
    Tech Module, CHOAM, Epic, Go to 11, promos and the original cards change
    nothing, and Rise of Ix filters the missions within it (plan 20.1)."""

    original = config.base_game is BaseGame.IMPERIUM
    expected = {
        (False, False): ScoutsPool.UPRISING,
        (False, True): ScoutsPool.UPRISING_IMMORTALITY,
        (True, False): ScoutsPool.IMPERIUM,
        (True, True): ScoutsPool.IMPERIUM_IMMORTALITY,
    }[(original, config.immortality)]
    assert scouts_pool(config) is expected
    assert scouts_rise_of_ix(config) is config.rise_of_ix
    missions = missions_for(
        expected, choam=config.choam_module, rise_of_ix=scouts_rise_of_ix(config)
    )
    ix = {mission.mission_id for mission in missions if mission.rise_of_ix_only}
    assert ix == (
        {"secret_stash", "armed_escort", "stowaways"} if config.rise_of_ix else set()
    )


def test_event_tickets_scale_by_base_game() -> None:
    """Uprising pools count tenths of the app's weight, the original
    game's twentieths (plan 20.3); a shared event keeps its weight."""

    betrayal = EVENTS_BY_ID["betrayal"]
    assert betrayal.tickets(ScoutsPool.UPRISING_IMMORTALITY) == 10
    assert betrayal.tickets(ScoutsPool.IMPERIUM_IMMORTALITY) == 20
    assert EVENTS_BY_ID["royal_delegation"].tickets(ScoutsPool.UPRISING) == 6
    with pytest.raises(ValueError, match="not in the"):
        EVENTS_BY_ID["royal_delegation"].tickets(ScoutsPool.IMPERIUM)


@pytest.mark.parametrize(
    ("pool", "choam", "sizes"),
    [
        # [Scouts schedule]: definitions per pool, after the CHOAM filter.
        (ScoutsPool.UPRISING, True, (11, 12, 25, 9, 4)),
        (ScoutsPool.UPRISING, False, (9, 10, 24, 7, 4)),
        (ScoutsPool.UPRISING_IMMORTALITY, True, (14, 15, 30, 11, 4)),
        (ScoutsPool.UPRISING_IMMORTALITY, False, (12, 13, 29, 9, 4)),
    ],
)
def test_pool_sizes(
    pool: ScoutsPool, choam: bool, sizes: tuple[int, int, int, int, int]
) -> None:
    assert (
        len(subcommittees_for(pool, choam=choam)),
        len(missions_for(pool, choam=choam)),
        len(events_for(pool, choam=choam)),
        len(auctions_for(pool, choam=choam)),
        len(sales_for(pool)),
    ) == sizes


def test_whole_catalog_sizes() -> None:
    # Uprising pool 11 / 12 / 27 / 9 / 4 plus the Immortality additions and
    # (stage P7f-2) Rise of Ix's three missions, plus the original game's own
    # items so far (stage P8b-1: 6 subcommittees, 10 events, 2 auctions, 1
    # sale; stage P8b-2: 8 missions; stage P8c-1: the 2 Mentat auctions,
    # Fremen Exchange, Stationed Support and Covert Operation; stage P8c-2: 5
    # events and Fremen Mercenaries, the last of them).
    assert (len(SUBCOMMITTEES), len(MISSIONS), len(EVENTS)) == (20, 28, 49)
    assert (len(AUCTIONS), len(SALES)) == (15, 6)


@pytest.mark.parametrize(
    ("pool", "sizes"),
    [
        # The app's original schedule holds nine subcommittees, three per
        # tier; the Immortality pool adds three, one per tier (plan 20.1).
        (ScoutsPool.IMPERIUM, {0: 3, 1: 3, 2: 3}),
        (ScoutsPool.IMPERIUM_IMMORTALITY, {0: 4, 1: 4, 2: 4}),
    ],
)
def test_the_original_pools_hold_their_subcommittees(
    pool: ScoutsPool, sizes: dict[int, int]
) -> None:
    for choam in (False, True):  # the original game has no CHOAM filter
        tiers = Counter(entry.tier for entry in subcommittees_for(pool, choam=choam))
        assert dict(tiers) == sizes
    ids = {entry.subcommittee_id for entry in subcommittees_for(pool, choam=False)}
    assert {
        "imperium_appropriations",
        "imperium_intelligence",
        "imperium_oversight",
        "joint_forces",
        "development",
        "political_affairs",
        "readiness",
        "investigations",
        "relations",
    } <= ids
    # The Uprising wording of the three shared definitions never plays here.
    assert not ids & {"appropriations", "intelligence", "oversight"}


def test_the_original_wording_shares_the_app_definition_of_the_uprising_one() -> None:
    """Appropriations, Intelligence and Oversight are one app definition with
    two wordings; each wording is a record of its own, in its own pools
    (docs/rules/arrakeen-scouts.md 9a, "같은 정의, 다른 문구")."""

    by_id = {entry.subcommittee_id: entry for entry in SUBCOMMITTEES}
    for plain in ("appropriations", "intelligence", "oversight"):
        uprising, original = by_id[plain], by_id[f"imperium_{plain}"]
        assert uprising.app == original.app
        assert (uprising.tier, uprising.name) == (original.tier, original.name)
        assert uprising.pools == UPRISING_POOLS
        assert original.pools == IMPERIUM_POOLS
        assert uprising.option != original.option


def test_ids_are_unique_within_and_across_kinds() -> None:
    ids = [
        *(entry.subcommittee_id for entry in SUBCOMMITTEES),
        *(entry.mission_id for entry in MISSIONS),
        *(entry.event_id for entry in EVENTS),
        *(entry.auction_id for entry in AUCTIONS),
        *(entry.sale_id for entry in SALES),
    ]
    assert len(ids) == len(set(ids))
    assert all(identifier == identifier.lower() for identifier in ids)


def test_every_pool_has_each_subcommittee_tier() -> None:
    for pool in ScoutsPool:
        for choam in (False, True):
            tiers = Counter(
                entry.tier for entry in subcommittees_for(pool, choam=choam)
            )
            # One of each tier, then two more from the rest: five for four
            # players needs at least five items with every tier present.
            assert set(tiers) == {0, 1, 2}
            assert sum(tiers.values()) >= 5


def test_round_four_event_tickets() -> None:
    # Design doc 8: with CHOAM the round-4 table holds 170 tickets (190 in
    # the pool less Friends Everywhere and Rebuild Infrastructure), 30 for
    # each Influence family.
    def tickets(choam: bool, round_number: int) -> Counter[int]:
        counts: Counter[int] = Counter()
        for entry in events_for(ScoutsPool.UPRISING, choam=choam):
            if entry.rounds[0] <= round_number <= entry.rounds[1]:
                counts[entry.app.family] += entry.tickets(ScoutsPool.UPRISING)
        return counts

    with_choam = tickets(True, 4)
    assert sum(with_choam.values()) == 170
    assert with_choam[17] == with_choam[18] == 30
    assert sum(tickets(False, 4).values()) == 160
    assert sum(tickets(True, 7).values()) == 190


# The original pools' event tickets: the app's baseWeight x subWeight times
# 20 (docs/rules/arrakeen-scouts.md 2.3 and 9a; plan 20.3). A single event
# is 20, a Spice Gain or Intrigue Bonus variant 10, an Influence Gain variant
# 3 x 0.25 = 15, Political Equilibrium 3 x 0.4 = 24, every other Influence
# Reduction variant 3 x 0.15 = 9. The Immortality events (weight 1) are 20.
# Twenty-one events: the app's whole original list.
_ORIGINAL_EVENT_TICKETS = {
    "assassination": 10,
    "imperium_secrets_for_sale": 10,
    "change_of_plans": 20,
    "imperium_gift_of_water": 20,
    "test_of_loyalty": 15,
    "imperium_guild_negotiation": 15,
    "imperium_political_equilibrium": 24,
    "emperors_tax": 9,
    "imperium_water_for_spice_smugglers": 9,
    "imperium_bene_gesserit_treachery": 9,
    # Stage P8c-1.
    "fremen_exchange": 9,
    "imperium_covert_operation": 20,
    # Stage P8c-2: Spice Gain and Intrigue Bonus variants 10, No Coming Back a
    # single event, the two Influence Gain variants 15 each.
    "tap_into_spice_reserves": 10,
    "no_coming_back": 20,
    "imperium_rotating_doors": 10,
    "intriguing_gift": 15,
    "desert_gift": 15,
}
_IMMORTALITY_EVENTS = (
    "ingratiate",
    "betrayal",
    "new_innovations",
    "termination_request",
    "offworld_operation",
)


def test_the_original_pools_event_tickets_match_the_app() -> None:
    for pool in (ScoutsPool.IMPERIUM, ScoutsPool.IMPERIUM_IMMORTALITY):
        tickets = {
            entry.event_id: entry.tickets(pool)
            for entry in events_for(pool, choam=False)
        }
        expected = dict(_ORIGINAL_EVENT_TICKETS)
        if pool is ScoutsPool.IMPERIUM_IMMORTALITY:
            expected.update(dict.fromkeys(_IMMORTALITY_EVENTS, 20))
        assert tickets == expected, pool
    # The whole-pool draw weights are whole tickets: a Fraction weight times
    # the pool's scale, nothing rounded.
    for event_id in _ORIGINAL_EVENT_TICKETS:
        entry = EVENTS_BY_ID[event_id]
        assert (
            entry.weight * EVENT_TICKET_SCALE[ScoutsPool.IMPERIUM]
            == _ORIGINAL_EVENT_TICKETS[event_id]
        )
        assert entry.pools == IMPERIUM_POOLS
    # Political Equilibrium's window opens in round 5 (not 4) with every
    # other Influence Reduction variant; Assassination is a round 6-7 event.
    assert EVENTS_BY_ID["imperium_political_equilibrium"].rounds == (5, 7)
    assert EVENTS_BY_ID["emperors_tax"].rounds == (5, 7)
    assert EVENTS_BY_ID["assassination"].rounds == (6, 7)


def test_the_original_round_four_and_five_event_tickets() -> None:
    """Round 4 holds no Influence Reduction event (they start in round 5) and
    no Assassination (round 6); round 5 adds the reductions."""

    def tickets(round_number: int) -> Counter[int]:
        counts: Counter[int] = Counter()
        pool = ScoutsPool.IMPERIUM
        for entry in events_for(pool, choam=False):
            if entry.rounds[0] <= round_number <= entry.rounds[1]:
                counts[entry.app.family] += entry.tickets(pool)
        return counts

    four, five, six = tickets(4), tickets(5), tickets(6)
    assert 7 not in four
    # Round 4: Tap into Spice Reserves (family 0), Secrets for Sale (1),
    # Change of Plans and Gift of Water (2, 5), No Coming Back (3, round 4
    # only), Covert Operation (4) and the four Influence Gain variants (6).
    assert four[0] == four[1] == 10
    assert four[2] == four[3] == four[4] == four[5] == 20 and four[6] == 60
    # Political Equilibrium and the four other Influence Reduction variants
    # (Fremen Exchange since stage P8c-1); No Coming Back is round 4 only.
    assert five[7] == 24 + 9 * 4 and five[6] == 60 and 3 not in five
    # Round 6: Assassination joins Tap into Spice Reserves, Rotating Doors
    # joins Secrets for Sale.
    assert six[0] == 20 and six[1] == 20


def test_event_families_hold_the_documented_variants() -> None:
    families = Counter(entry.app.family for entry in EVENTS)
    assert families[17] == families[18] == 5
    assert families[13] == families[14] == families[19] == families[22] == 2
    uprising = {
        entry.app.family for entry in events_for(ScoutsPool.UPRISING, choam=True)
    }
    assert len(uprising) == 15


def test_secret_events_offer_four_picks() -> None:
    secret = [entry for entry in EVENTS if entry.kind is EventKind.SECRET]
    assert {entry.event_id for entry in secret} == {
        "covert_operation",
        "covert_operation_choam",
        "offworld_operation",
        "imperium_covert_operation",
    }
    assert all(len(entry.secret_choices) == 4 for entry in secret)
    # The original game's own (stage P8c-1, 9a): its second and fourth lines
    # name their Faction at the pick, one Influence and two with one Faction.
    original = EVENTS_BY_ID["imperium_covert_operation"]
    assert original.pools == IMPERIUM_POOLS
    assert [choice.delay for choice in original.secret_choices] == [1, 1, 2, 2]
    assert [choice.names_faction for choice in original.secret_choices] == [
        False,
        True,
        False,
        True,
    ]
    assert not any(choice.grouped for choice in original.secret_choices)
    assert not any(
        choice.names_faction
        for entry in secret
        if entry is not original
        for choice in entry.secret_choices
    )


def test_mission_families_and_spaces() -> None:
    families = Counter(entry.app.family for entry in MISSIONS)
    # Desert Riding and both Valued Informants; the two Elite Sardaukar
    # missions and Coordinate With The Emperor (never in one pool with
    # Prison Planet).
    assert families[15] == 3
    assert families[18] == 3
    # The original game's: Muster an Army's two and Botanical Testing's two
    # (Stationed Support since stage P8c-1); its own Coordinate With The
    # Emperor has a family of its own.
    assert families[1] == 2
    assert families[2] == 2
    assert families[12] == 1
    # Every mission's space is on the board of each game it can be drawn in:
    # the Uprising pools' on Uprising's, the original pools' on the original
    # game's, with or without Rise of Ix wherever the app's pool draws it.
    for entry in MISSIONS:
        if entry.space_id is None:
            continue
        for base_game in BaseGame:
            if not any(pool in base_game_pools(base_game) for pool in entry.pools):
                continue
            for rise_of_ix in (False, True):
                if (rise_of_ix and entry.no_rise_of_ix) or (
                    not rise_of_ix and entry.rise_of_ix_only
                ):
                    continue
                board = content_for(
                    RulesetConfig(
                        base_game=base_game,
                        arrakeen_scouts=True,
                        rise_of_ix=rise_of_ix,
                    )
                ).board_spaces
                assert entry.space_id in {space.space_id for space in board}, (
                    entry.mission_id,
                    base_game,
                    rise_of_ix,
                )
    prison = {entry.mission_id for entry in MISSIONS if entry.app.family == 18}
    # Elite Sardaukar is the Uprising pools' family (the original game's
    # Coordinate With The Emperor is its own, plan 20.3).
    for pool in UPRISING_POOLS:
        in_pool = {
            entry.mission_id
            for entry in missions_for(pool, choam=True)
            if entry.mission_id in prison
        }
        assert len(in_pool) == 2


def test_the_original_pools_hold_their_missions() -> None:
    """Stages P8b-2 and P8c-1: the app's original pools
    (docs/rules/arrakeen-scouts.md 9a) hold eight of the nine missions without
    Immortality, the Immortality pool adds Coordinate With The Emperor, and Rise
    of Ix drops the missions on Rally Troops and Foldspace (the half overlay
    covers Rally Troops [Main p. 18])."""

    plain = {
        entry.mission_id for entry in missions_for(ScoutsPool.IMPERIUM, choam=False)
    }
    assert plain == {
        "space_travel_deal",
        "muster_spice_incentive",
        "muster_strongarmed_alliance",
        "botanical_secrets_in_the_desert",
        "genetic_research",
        "guild_maneuvers",
        "sapho_juice",
        "botanical_stationed_support",
    }
    immortal = {
        entry.mission_id
        for entry in missions_for(ScoutsPool.IMPERIUM_IMMORTALITY, choam=False)
    }
    assert immortal == plain | {
        "imperium_coordinate_with_the_emperor",
        "sponsored_research",
        "back_room_deal",
        "tleilaxu_offering",
    }
    with_ix = {
        entry.mission_id
        for entry in missions_for(ScoutsPool.IMPERIUM, choam=False, rise_of_ix=True)
    }
    assert with_ix == {
        "space_travel_deal",
        "botanical_secrets_in_the_desert",
        "botanical_stationed_support",
        "genetic_research",
        "sapho_juice",
        "secret_stash",
        "armed_escort",
        "stowaways",
    }
    for mission_id in (
        "muster_spice_incentive",
        "muster_strongarmed_alliance",
        "guild_maneuvers",
    ):
        assert MISSIONS_BY_ID[mission_id].no_rise_of_ix
    # Appended after every older mission, in the order the stages added them.
    assert [entry.mission_id for entry in MISSIONS[-9:]] == [
        "space_travel_deal",
        "muster_spice_incentive",
        "muster_strongarmed_alliance",
        "botanical_secrets_in_the_desert",
        "genetic_research",
        "guild_maneuvers",
        "imperium_coordinate_with_the_emperor",
        "sapho_juice",
        "botanical_stationed_support",
    ]
    assert MISSIONS[-10].mission_id == "stowaways"


def test_auction_slots() -> None:
    for pool in ScoutsPool:
        for choam in (False, True):
            entries = auctions_for(pool, choam=choam)
            mid = {e.app.family for e in entries if e.slot is not AuctionSlot.LATE}
            late = {e.app.family for e in entries if e.slot is not AuctionSlot.MID}
            # Every family can be the mid auction and the late one.
            assert mid == late
    mercenaries = next(e for e in AUCTIONS if e.kind is AuctionKind.MERCENARIES)
    assert (mercenaries.max_bid, mercenaries.currency) == (3, "spice")


def test_the_original_pools_hold_the_mentat_auctions() -> None:
    """Stage P8c-1 (docs/rules/arrakeen-scouts.md 9a): the Mentat is an open
    auction of one place, bid in Solari mid and in spice late, one family;
    appended after every older auction, in the original pools only."""

    mid, late = AUCTIONS[-2], AUCTIONS[-1]
    assert (mid.auction_id, late.auction_id) == ("mentat_mid", "mentat_late")
    for entry, slot, currency in (
        (mid, AuctionSlot.MID, "solari"),
        (late, AuctionSlot.LATE, "spice"),
    ):
        assert entry.kind is AuctionKind.OPEN_MENTAT
        assert (entry.slot, entry.currency, entry.places) == (slot, currency, 1)
        assert entry.rank_rewards == () and entry.revealed_cards == 0
        assert entry.pools == IMPERIUM_POOLS
    assert mid.app.family == late.app.family == 0
    assert mid.rounds == (5, 6) and late.rounds == (8, 9)
    for pool in ScoutsPool:
        listed = {entry.auction_id for entry in auctions_for(pool, choam=False)}
        assert ("mentat_mid" in listed) == (pool in IMPERIUM_POOLS)


def test_the_original_pools_hold_their_last_events_and_the_fremen_sale() -> None:
    """Stage P8c-2 (docs/rules/arrakeen-scouts.md 9a): the five events and the
    sale that finish the original pools, appended after every older item, in
    the original pools only."""

    last = [entry.event_id for entry in EVENTS[-5:]]
    assert last == [
        "tap_into_spice_reserves",
        "no_coming_back",
        "imperium_rotating_doors",
        "intriguing_gift",
        "desert_gift",
    ]
    assert SALES[-1].sale_id == "fremen_mercenaries"
    assert all(entry.pools == IMPERIUM_POOLS for entry in EVENTS[-5:])
    assert SALES[-1].pools == IMPERIUM_POOLS
    # The app's windows: Tap into Spice Reserves and the two gifts run rounds
    # 4-7, Rotating Doors 6-7 and No Coming Back round 4 alone.
    assert [EVENTS_BY_ID[event].rounds for event in last] == [
        (4, 7),
        (4, 4),
        (6, 7),
        (4, 7),
        (4, 7),
    ]
    # The Uprising pools keep their lists.
    for pool in UPRISING_POOLS:
        listed = {entry.event_id for entry in events_for(pool, choam=True)}
        assert not listed & set(last)
        assert "fremen_mercenaries" not in {s.sale_id for s in sales_for(pool)}
    # Every original pool draws them.
    for pool in IMPERIUM_POOLS:
        assert set(last) <= {e.event_id for e in events_for(pool, choam=False)}
        assert "fremen_mercenaries" in {s.sale_id for s in sales_for(pool)}


def test_fremen_mercenaries_is_a_line_per_water() -> None:
    """9a: "각자 원하는 만큼 물을 내고 물마다 troop 2를 recruit해 곧바로 Conflict에
    배치한다". One line per count of water, six at most because a seat has
    twelve troops."""

    sale = SALES_BY_ID["fremen_mercenaries"]
    assert len(sale.options) == 6
    for water, option in enumerate(sale.options, start=1):
        assert option.costs == (PayResources(water=water),)
        assert option.rewards == (RecruitToConflict(2 * water),)


def test_reserve_rewards_name_reserve_cards() -> None:
    for entry in EVENTS:
        for option in entry.options:
            for reward in option.rewards:
                if isinstance(reward, AcquireReserveCardToHand):
                    assert reward.card_id in RESERVE_STACKS_BY_ID
