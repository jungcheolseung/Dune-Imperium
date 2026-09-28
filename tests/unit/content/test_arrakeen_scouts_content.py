"""Integrity tests for the Arrakeen Scouts catalog (no extraction needed)."""

from collections import Counter

import pytest

from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS,
    EVENTS,
    MISSIONS,
    SALES,
    SUBCOMMITTEES,
    AuctionKind,
    AuctionSlot,
    EventKind,
    ScoutsPool,
    auctions_for,
    events_for,
    missions_for,
    sales_for,
    scouts_pool,
    subcommittees_for,
)
from dune_imperium.content.arrakeen_scouts.types import AcquireReserveCardToHand
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID


def test_pool_follows_the_immortality_option() -> None:
    assert scouts_pool(immortality=False) is ScoutsPool.UPRISING
    assert scouts_pool(immortality=True) is ScoutsPool.UPRISING_IMMORTALITY


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
    # Uprising pool 11 / 12 / 27 / 9 / 4 plus the Immortality additions.
    assert (len(SUBCOMMITTEES), len(MISSIONS), len(EVENTS)) == (14, 16, 32)
    assert (len(AUCTIONS), len(SALES)) == (11, 4)


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
                counts[entry.app.family] += entry.weight_tickets
        return counts

    with_choam = tickets(True, 4)
    assert sum(with_choam.values()) == 170
    assert with_choam[17] == with_choam[18] == 30
    assert sum(tickets(False, 4).values()) == 160
    assert sum(tickets(True, 7).values()) == 190


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
    }
    assert all(len(entry.secret_choices) == 4 for entry in secret)


def test_mission_families_and_spaces() -> None:
    families = Counter(entry.app.family for entry in MISSIONS)
    # Desert Riding and both Valued Informants; the two Elite Sardaukar
    # missions and Coordinate With The Emperor (never in one pool with
    # Prison Planet).
    assert families[15] == 3
    assert families[18] == 3
    for entry in MISSIONS:
        if entry.space_id is not None:
            assert entry.space_id in BOARD_SPACES_BY_ID, entry.mission_id
    prison = {entry.mission_id for entry in MISSIONS if entry.app.family == 18}
    for pool in ScoutsPool:
        in_pool = {
            entry.mission_id
            for entry in missions_for(pool, choam=True)
            if entry.mission_id in prison
        }
        assert len(in_pool) == 2


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


def test_reserve_rewards_name_reserve_cards() -> None:
    for entry in EVENTS:
        for option in entry.options:
            for reward in option.rewards:
                if isinstance(reward, AcquireReserveCardToHand):
                    assert reward.card_id in RESERVE_STACKS_BY_ID
