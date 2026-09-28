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
)
from dune_imperium.content.arrakeen_scouts.types import AppDefinition

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

# The app's schedule names for the two pools this project plays.
_SCHEDULES = {
    ScoutsPool.UPRISING: "Uprising",
    ScoutsPool.UPRISING_IMMORTALITY: "Uprising+Immortality",
}
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
    kind: str, records: Mapping[str, tuple[AppDefinition, tuple[ScoutsPool, ...]]]
) -> None:
    pools = _pool_assets(kind)
    for record_id, (app, record_pools) in records.items():
        assert app.asset_name in _definitions(kind), record_id
        assert {pool for pool, assets in pools.items() if app.asset_name in assets} == (
            set(record_pools)
        ), record_id
    listed = {app.asset_name for app, _ in records.values()}
    assert listed == set().union(*pools.values())


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
        "Mission", {entry.mission_id: (entry.app, entry.pools) for entry in MISSIONS}
    )
    for entry in MISSIONS:
        data = _definitions("Mission")[entry.app.asset_name]
        _check_beat(entry.mission_id, entry.app, data)
        assert entry.rounds == (data["startRound"], data["endRound"]), entry.mission_id
        assert entry.choam_only == bool(data["CHOAMOnly"]), entry.mission_id
        assert not data["NoCHOAMOnly"], entry.mission_id
        assert entry.mission_type == data["missionType"], entry.mission_id


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
        weight = data["baseWeight"] * data["subWeight"] * 10
        assert math.isclose(entry.weight_tickets, weight, abs_tol=1e-4), entry.event_id
        delays = [choice["completionDelay"] for choice in data["secretChoices"]]
        assert [choice.delay for choice in entry.secret_choices] == delays
        # The app's CondenseEventCompletions merges same-pick completions
        # onto one screen only for these choice ids [Scouts schedule].
        grouped = [choice["choiceID"] in _GROUPED for choice in data["secretChoices"]]
        assert [choice.grouped for choice in entry.secret_choices] == grouped
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
        sealed = entry.kind is not AuctionKind.OPEN_CARDS
        assert sealed == bool(data["secretAuction"]), entry.auction_id
        assert entry.max_bid == data["maxBid"], entry.auction_id
        currency = {0: "solari", 1: "spice"}[data["costResource"]]
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
