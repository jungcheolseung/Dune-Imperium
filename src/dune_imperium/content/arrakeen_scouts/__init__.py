"""Arrakeen Scouts content (``arrakeen_scouts`` option).

The companion-app module's subcommittees, missions, events, auctions and
sales (``docs/rules/arrakeen-scouts.md``). The pool helpers apply the app's
filters [Scouts schedule]: ``immortality`` picks the Uprising+Immortality
pool, and the CHOAM Module drops the CHOAM-only items when it is off and,
for events only, the no-CHOAM items when it is on.
"""

from dune_imperium.content.arrakeen_scouts.auctions import (
    AUCTIONS,
    AUCTIONS_BY_ID,
    MAX_AUCTION_BID,
    MAX_MERCENARIES_BID,
    SALES,
    SALES_BY_ID,
)
from dune_imperium.content.arrakeen_scouts.events import EVENTS, EVENTS_BY_ID
from dune_imperium.content.arrakeen_scouts.missions import MISSIONS, MISSIONS_BY_ID
from dune_imperium.content.arrakeen_scouts.subcommittees import (
    SUBCOMMITTEES,
    SUBCOMMITTEES_BY_ID,
)
from dune_imperium.content.arrakeen_scouts.types import (
    AppDefinition,
    AuctionKind,
    AuctionSlot,
    AutomaticEffect,
    EventKind,
    Mission,
    MissionKind,
    RoundModifier,
    ScoutsAuction,
    ScoutsEvent,
    ScoutsOption,
    ScoutsPool,
    ScoutsSale,
    SecretChoice,
    Subcommittee,
    TroopSource,
)


def scouts_pool(*, immortality: bool) -> ScoutsPool:
    """Return the schedule pool the app uses for these expansions."""

    return ScoutsPool.UPRISING_IMMORTALITY if immortality else ScoutsPool.UPRISING


def subcommittees_for(pool: ScoutsPool, *, choam: bool) -> tuple[Subcommittee, ...]:
    """Return the pool's subcommittees in catalog order."""

    return tuple(
        entry
        for entry in SUBCOMMITTEES
        if pool in entry.pools and (choam or not entry.choam_only)
    )


def missions_for(pool: ScoutsPool, *, choam: bool) -> tuple[Mission, ...]:
    """Return the pool's missions in catalog order."""

    return tuple(
        entry
        for entry in MISSIONS
        if pool in entry.pools and (choam or not entry.choam_only)
    )


def events_for(pool: ScoutsPool, *, choam: bool) -> tuple[ScoutsEvent, ...]:
    """Return the pool's events in catalog order."""

    return tuple(
        entry
        for entry in EVENTS
        if pool in entry.pools
        and not (entry.choam_only and not choam)
        and not (entry.no_choam_only and choam)
    )


def auctions_for(pool: ScoutsPool, *, choam: bool) -> tuple[ScoutsAuction, ...]:
    """Return the pool's auctions in catalog order."""

    return tuple(
        entry
        for entry in AUCTIONS
        if pool in entry.pools and (choam or not entry.choam_only)
    )


def sales_for(pool: ScoutsPool) -> tuple[ScoutsSale, ...]:
    """Return the pool's sales in catalog order (no CHOAM or round filter)."""

    return tuple(entry for entry in SALES if pool in entry.pools)


__all__ = [
    "AUCTIONS",
    "AUCTIONS_BY_ID",
    "EVENTS",
    "EVENTS_BY_ID",
    "MAX_AUCTION_BID",
    "MAX_MERCENARIES_BID",
    "MISSIONS",
    "MISSIONS_BY_ID",
    "SALES",
    "SALES_BY_ID",
    "SUBCOMMITTEES",
    "SUBCOMMITTEES_BY_ID",
    "AppDefinition",
    "AuctionKind",
    "AuctionSlot",
    "AutomaticEffect",
    "EventKind",
    "Mission",
    "MissionKind",
    "RoundModifier",
    "ScoutsAuction",
    "ScoutsEvent",
    "ScoutsOption",
    "ScoutsPool",
    "ScoutsSale",
    "SecretChoice",
    "Subcommittee",
    "TroopSource",
    "auctions_for",
    "events_for",
    "missions_for",
    "sales_for",
    "scouts_pool",
    "subcommittees_for",
]
