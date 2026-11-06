"""Arrakeen Scouts content (``arrakeen_scouts`` option).

The companion-app module's subcommittees, missions, events, auctions and
sales (``docs/rules/arrakeen-scouts.md``). The pool helpers apply the app's
filters [Scouts schedule]: the base game and ``immortality`` pick the pool
(``scouts_pool``), the CHOAM Module drops the CHOAM-only items when it is off
and, for events only, the no-CHOAM items when it is on, and Rise of Ix swaps
missions (``missions_for``; the other lists are the same).

Each table lists the Uprising pools' items first, in the order they had
before the original game's pools came (stage P8), and the original game's
own items after them; ``*_of_base_game`` returns one base game's items in
that order, so an Uprising catalog or vocabulary never sees the original's.
"""

from typing import Protocol

from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.content.arrakeen_scouts.auctions import (
    AUCTIONS,
    AUCTIONS_BY_ID,
    MAX_AUCTION_BID,
    MAX_MERCENARIES_BID,
    MAX_SPECIMEN_TOP_UP,
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
    EVENT_TICKET_SCALE,
    IMPERIUM_POOLS,
    UPRISING_POOLS,
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
    ScoutsPool,
    ScoutsSale,
    SecretChoice,
    Subcommittee,
    TroopSource,
)


def scouts_rise_of_ix(config: RulesetConfig) -> bool:
    """Whether ``config`` plays the app's Rise of Ix pools: its missions for
    the base game's (Uprising+Ix since stage P7f-2, the original's in P8).

    The app also drops Rise of Ix from the pool when Bloodlines comes with
    "only the Leaders and Tech tiles from Rise of Ix": since stage P8-1 that
    is ``ix_leaders`` (with ``ix_tech_tiles``, OQ-165), which leaves
    ``rise_of_ix`` off, so only "all of Rise of Ix" plays the Ix pools (plan
    20.1; the "원판" note atop docs/rules/arrakeen-scouts.md)."""

    return config.rise_of_ix


def scouts_pool(config: RulesetConfig) -> ScoutsPool:
    """Return the schedule pool the app uses for ``config``'s base game and
    expansions (``SpiceDataController.get_Schedule``, plan 20.1)."""

    if config.base_game is BaseGame.IMPERIUM:
        if config.immortality:
            return ScoutsPool.IMPERIUM_IMMORTALITY
        return ScoutsPool.IMPERIUM
    if config.immortality:
        return ScoutsPool.UPRISING_IMMORTALITY
    return ScoutsPool.UPRISING


def base_game_pools(base_game: BaseGame) -> tuple[ScoutsPool, ...]:
    """Return every pool a game on ``base_game`` may play."""

    return IMPERIUM_POOLS if base_game is BaseGame.IMPERIUM else UPRISING_POOLS


class _Pooled(Protocol):
    @property
    def pools(self) -> tuple[ScoutsPool, ...]: ...


def _of_base_game[T: _Pooled](
    entries: tuple[T, ...], base_game: BaseGame
) -> tuple[T, ...]:
    wanted = base_game_pools(base_game)
    return tuple(
        entry for entry in entries if any(pool in wanted for pool in entry.pools)
    )


def subcommittees_of_base_game(base_game: BaseGame) -> tuple[Subcommittee, ...]:
    """Every subcommittee of ``base_game``'s pools, in catalog order."""

    return _of_base_game(SUBCOMMITTEES, base_game)


def missions_of_base_game(base_game: BaseGame) -> tuple[Mission, ...]:
    """Every mission of ``base_game``'s pools, in catalog order."""

    return _of_base_game(MISSIONS, base_game)


def events_of_base_game(base_game: BaseGame) -> tuple[ScoutsEvent, ...]:
    """Every event of ``base_game``'s pools, in catalog order."""

    return _of_base_game(EVENTS, base_game)


def auctions_of_base_game(base_game: BaseGame) -> tuple[ScoutsAuction, ...]:
    """Every auction of ``base_game``'s pools, in catalog order."""

    return _of_base_game(AUCTIONS, base_game)


def sales_of_base_game(base_game: BaseGame) -> tuple[ScoutsSale, ...]:
    """Every sale of ``base_game``'s pools, in catalog order."""

    return _of_base_game(SALES, base_game)


def subcommittees_for(pool: ScoutsPool, *, choam: bool) -> tuple[Subcommittee, ...]:
    """Return the pool's subcommittees in catalog order."""

    return tuple(
        entry
        for entry in SUBCOMMITTEES
        if pool in entry.pools and (choam or not entry.choam_only)
    )


def missions_for(
    pool: ScoutsPool, *, choam: bool, rise_of_ix: bool = False
) -> tuple[Mission, ...]:
    """Return the pool's missions in catalog order; with Rise of Ix the
    app's Uprising+Ix pool, which adds its three missions and drops Send for
    Aid [Scouts schedule]."""

    return tuple(
        entry
        for entry in MISSIONS
        if pool in entry.pools
        and (choam or not entry.choam_only)
        and not (entry.rise_of_ix_only and not rise_of_ix)
        and not (entry.no_rise_of_ix and rise_of_ix)
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
    "MAX_SPECIMEN_TOP_UP",
    "MISSIONS",
    "MISSIONS_BY_ID",
    "SALES",
    "SALES_BY_ID",
    "SUBCOMMITTEES",
    "SUBCOMMITTEES_BY_ID",
    "EVENT_TICKET_SCALE",
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
    "ScoutsPool",
    "ScoutsSale",
    "SecretChoice",
    "Subcommittee",
    "TroopSource",
    "auctions_for",
    "auctions_of_base_game",
    "base_game_pools",
    "events_for",
    "events_of_base_game",
    "missions_for",
    "missions_of_base_game",
    "sales_for",
    "sales_of_base_game",
    "scouts_pool",
    "scouts_rise_of_ix",
    "subcommittees_for",
    "subcommittees_of_base_game",
]
