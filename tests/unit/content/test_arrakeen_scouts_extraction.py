"""Audit the Arrakeen Scouts catalog against the app extraction.

The extraction (``scripts/dwgr/extract.py``) is not in any repository: it
lives in the assets checkout's git-ignored ``reference/dwgr-arrakeen-scouts/``
on the machine that made it (``docs/rules/sources.md``). Without it these
tests skip, like the card-image checks in ``tests/unit/display``.
``DWGR_EXTRACTION`` points them at another extraction folder (the one holding
``schedules.json``).

Checked mechanically, per record: the app asset exists, sits in exactly the
record's pools, and matches the record's family, variant, round window,
CHOAM flags, weight, tier or mission type, secret-pick delays and auction
settings. The pools hold no asset without a record.

Stage P8 adds the original game's pools; every original-pool item has a record
since stage P8c-2, so the completeness checks hold for both base games.
"""

import json
import math
import os
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

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
    missions_for,
)
from dune_imperium.content.arrakeen_scouts.types import (
    IMPERIUM_POOLS,
    UPRISING_POOLS,
    AppDefinition,
)

_DEFAULT = (
    Path(__file__).resolve().parents[3]
    / "assets"
    / "reference"
    / "dwgr-arrakeen-scouts"
    / "data"
)
EXTRACTION = Path(os.environ.get("DWGR_EXTRACTION", _DEFAULT))

pytestmark = pytest.mark.skipif(
    not (EXTRACTION / "schedules.json").is_file(),
    reason="the Dire Wolf Game Room extraction is not on this machine",
)

# The app's schedule names for the pools without Rise of Ix (its pools
# differ only in their missions, ``missions_for(..., rise_of_ix=True)``).
_SCHEDULES = {
    ScoutsPool.UPRISING: "Uprising",
    ScoutsPool.UPRISING_IMMORTALITY: "Uprising+Immortality",
    ScoutsPool.IMPERIUM: "base",
    ScoutsPool.IMPERIUM_IMMORTALITY: "base+Immortality",
}
_IX_SCHEDULES = {
    ScoutsPool.UPRISING: "Uprising+Ix",
    ScoutsPool.UPRISING_IMMORTALITY: "Uprising+Ix+Immortality",
    ScoutsPool.IMPERIUM: "base+Ix",
    ScoutsPool.IMPERIUM_IMMORTALITY: "base+Ix+Immortality",
}
# The auctions whose currency is not the app's costResource: the late Mentat
# auction bids spice, as its text and reminder say; an open auction never
# reads costResource (docs/rules/arrakeen-scouts.md 9a, stage P8c).
_CURRENCY_EXCEPTIONS = {"mentat_late": "spice"}
# Secret-choice ids whose completions the app shows together, in turn order.
_GROUPED = frozenset({5, 6, 7, 8, 10})
_KINDS = {
    "Subcommittee": "availableSubcommittees",
    "Mission": "availableMissions",
    "Event": "availableEvents",
    "Auction": "availableAuctions",
    "Sale": "availableSales",
}


@cache
def _definitions(kind: str) -> dict[str, dict[str, Any]]:
    path = EXTRACTION / "spice_mb" / f"{kind}Definition.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    return {record["m_Name"]: record for record in records}


@cache
def _pool_assets(kind: str) -> dict[ScoutsPool, frozenset[str]]:
    schedules = json.loads((EXTRACTION / "schedules.json").read_text("utf-8"))
    by_path = {record["_path_id"]: name for name, record in _definitions(kind).items()}
    return {
        pool: frozenset(by_path[path_id] for path_id in schedules[name][_KINDS[kind]])
        for pool, name in _SCHEDULES.items()
    }


def _check_membership(
    kind: str,
    records: Mapping[str, tuple[AppDefinition, tuple[ScoutsPool, ...]]],
    checked: tuple[ScoutsPool, ...] = tuple(_SCHEDULES),
) -> None:
    """Every record's asset exists, and the records naming one asset hold it
    in exactly the app's ``checked`` pools between them (a shared
    subcommittee's original-game wording is its own record, plan 20.2)."""

    pools = {
        pool: assets for pool, assets in _pool_assets(kind).items() if pool in checked
    }
    by_asset: dict[str, set[ScoutsPool]] = {}
    for record_id, (app, record_pools) in records.items():
        assert app.asset_name in _definitions(kind), record_id
        held = by_asset.setdefault(app.asset_name, set())
        assert not held & set(record_pools), record_id
        held.update(pool for pool in record_pools if pool in checked)
    for asset, held in by_asset.items():
        assert {pool for pool, assets in pools.items() if asset in assets} == held, (
            asset
        )


def _check_complete(
    kind: str,
    records: Mapping[str, tuple[AppDefinition, tuple[ScoutsPool, ...]]],
    pool_ids: tuple[ScoutsPool, ...],
) -> None:
    """The pools hold no asset without a record."""

    pools = _pool_assets(kind)
    listed = {app.asset_name for app, _ in records.values()}
    assert set().union(*(pools[pool] for pool in pool_ids)) <= listed


def _check_beat(record_id: str, app: AppDefinition, data: Mapping[str, Any]) -> None:
    assert (app.family, app.variant) == (data["beatId"], data["beatSubId"]), record_id


def test_subcommittees_match_the_app_definitions() -> None:
    _check_membership(
        "Subcommittee",
        {entry.subcommittee_id: (entry.app, entry.pools) for entry in SUBCOMMITTEES},
    )
    for entry in SUBCOMMITTEES:
        data = _definitions("Subcommittee")[entry.app.asset_name]
        assert entry.app.family == data["subcommitteeId"], entry.subcommittee_id
        assert entry.app.variant == 0
        assert entry.tier == data["subcommitteeType"], entry.subcommittee_id
        assert entry.choam_only == bool(data["CHOAMOnly"]), entry.subcommittee_id


def test_missions_match_the_app_definitions() -> None:
    _check_membership(
        "Mission",
        {
            entry.mission_id: (entry.app, entry.pools)
            for entry in MISSIONS
            if not entry.rise_of_ix_only
        },
    )
    for entry in MISSIONS:
        data = _definitions("Mission")[entry.app.asset_name]
        _check_beat(entry.mission_id, entry.app, data)
        assert entry.rounds == (data["startRound"], data["endRound"]), entry.mission_id
        assert entry.choam_only == bool(data["CHOAMOnly"]), entry.mission_id
        assert not data["NoCHOAMOnly"], entry.mission_id
        assert entry.mission_type == data["missionType"], entry.mission_id


@pytest.mark.parametrize(
    "pool",
    [
        ScoutsPool.UPRISING,
        ScoutsPool.UPRISING_IMMORTALITY,
        # The original pools' missions are all in (stage P8c-1).
        ScoutsPool.IMPERIUM,
        ScoutsPool.IMPERIUM_IMMORTALITY,
    ],
)
def test_the_rise_of_ix_pools_differ_only_in_missions(pool: ScoutsPool) -> None:
    """With Rise of Ix the app plays its +Ix schedules: the missions of
    ``missions_for(..., rise_of_ix=True)`` exactly, and every other list the
    same as without Rise of Ix [Scouts schedule] (Uprising since stage P7f-2,
    the original game in P8)."""

    schedules = json.loads((EXTRACTION / "schedules.json").read_text("utf-8"))
    by_path = {
        record["_path_id"]: name for name, record in _definitions("Mission").items()
    }
    name, ix_name = _SCHEDULES[pool], _IX_SCHEDULES[pool]
    listed = {by_path[path] for path in schedules[ix_name]["availableMissions"]}
    assert listed == {
        entry.app.asset_name
        for entry in missions_for(pool, choam=True, rise_of_ix=True)
    }
    for key in _KINDS.values():
        if key != "availableMissions":
            assert schedules[ix_name][key] == schedules[name][key], key


def test_the_uprising_ix_pools_swap_send_for_aid_for_three_missions() -> None:
    added = {entry.mission_id for entry in MISSIONS if entry.rise_of_ix_only}
    dropped = {
        entry.mission_id
        for entry in MISSIONS
        if entry.no_rise_of_ix and set(entry.pools) & set(UPRISING_POOLS)
    }
    assert (added, dropped) == (
        {"secret_stash", "armed_escort", "stowaways"},
        {"send_for_aid"},
    )


def _records(kind: str) -> dict[str, tuple[AppDefinition, tuple[ScoutsPool, ...]]]:
    match kind:
        case "Subcommittee":
            return {e.subcommittee_id: (e.app, e.pools) for e in SUBCOMMITTEES}
        case "Mission":
            return {
                e.mission_id: (e.app, e.pools)
                for e in MISSIONS
                if not e.rise_of_ix_only
            }
        case "Event":
            return {e.event_id: (e.app, e.pools) for e in EVENTS}
        case "Auction":
            return {e.auction_id: (e.app, e.pools) for e in AUCTIONS}
        case _:
            return {e.sale_id: (e.app, e.pools) for e in SALES}


@pytest.mark.parametrize("kind", list(_KINDS))
def test_the_uprising_pools_hold_no_item_without_a_record(kind: str) -> None:
    _check_complete(kind, _records(kind), UPRISING_POOLS)


@pytest.mark.parametrize("kind", list(_KINDS))
def test_the_original_pools_hold_no_item_without_a_record(kind: str) -> None:
    _check_complete(kind, _records(kind), IMPERIUM_POOLS)


def test_events_match_the_app_definitions() -> None:
    _check_membership(
        "Event", {entry.event_id: (entry.app, entry.pools) for entry in EVENTS}
    )
    for entry in EVENTS:
        data = _definitions("Event")[entry.app.asset_name]
        _check_beat(entry.event_id, entry.app, data)
        assert entry.rounds == (data["startRound"], data["endRound"]), entry.event_id
        assert entry.choam_only == bool(data["CHOAMOnly"]), entry.event_id
        assert entry.no_choam_only == bool(data["NoCHOAMOnly"]), entry.event_id
        weight = data["baseWeight"] * data["subWeight"]
        assert math.isclose(entry.weight, weight, abs_tol=1e-6), entry.event_id
        delays = [choice["completionDelay"] for choice in data["secretChoices"]]
        assert [choice.delay for choice in entry.secret_choices] == delays
        # The app's CondenseEventCompletions merges same-pick completions
        # onto one screen only for these choice ids [Scouts schedule].
        grouped = [choice["choiceID"] in _GROUPED for choice in data["secretChoices"]]
        assert [choice.grouped for choice in entry.secret_choices] == grouped
        # A pick that names its Faction is a choice with the app's Faction
        # sub-choices (the original game's Covert Operation, stage P8c-1).
        named = [bool(choice["subChoices"]) for choice in data["secretChoices"]]
        assert [choice.names_faction for choice in entry.secret_choices] == named
        assert (entry.kind is EventKind.SECRET) == bool(delays), entry.event_id


def test_auctions_match_the_app_definitions() -> None:
    _check_membership(
        "Auction", {entry.auction_id: (entry.app, entry.pools) for entry in AUCTIONS}
    )
    slots = {
        (5, 6): AuctionSlot.MID,
        (8, 9): AuctionSlot.LATE,
        (5, 9): AuctionSlot.EITHER,
    }
    for entry in AUCTIONS:
        data = _definitions("Auction")[entry.app.asset_name]
        _check_beat(entry.auction_id, entry.app, data)
        window = (data["startRound"], data["endRound"])
        assert entry.rounds == window, entry.auction_id
        assert entry.slot is slots[window], entry.auction_id
        assert entry.choam_only == bool(data["CHOAMOnly"]), entry.auction_id
        assert not data["NoCHOAMOnly"], entry.auction_id
        # Critical Moment and the original game's Mentat are open (8.3, 9a).
        sealed = entry.kind not in (AuctionKind.OPEN_CARDS, AuctionKind.OPEN_MENTAT)
        assert sealed == bool(data["secretAuction"]), entry.auction_id
        assert entry.max_bid == data["maxBid"], entry.auction_id
        currency = {0: "solari", 1: "spice"}[data["costResource"]]
        # The one exception: the late Mentat auction's costResource says
        # Solari, but an open auction never reads it and the auction's text
        # and reminder say spice (docs/rules/arrakeen-scouts.md 9a).
        currency = _CURRENCY_EXCEPTIONS.get(entry.auction_id, currency)
        assert entry.currency == currency, entry.auction_id
        assert entry.places == len(data["rewardRanks"]), entry.auction_id


def test_sales_match_the_app_definitions() -> None:
    _check_membership(
        "Sale", {entry.sale_id: (entry.app, entry.pools) for entry in SALES}
    )
    for entry in SALES:
        data = _definitions("Sale")[entry.app.asset_name]
        _check_beat(entry.sale_id, entry.app, data)
        assert (data["startRound"], data["endRound"]) == (8, 9), entry.sale_id
        assert not data["CHOAMOnly"] and not data["NoCHOAMOnly"], entry.sale_id
