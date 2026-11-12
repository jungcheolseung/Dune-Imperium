"""Arrakeen Scouts auctions and sales [Scouts auction: <name>], [Scouts sale: <name>].

A mid and a late definition of the same auction share a family, so the late
draw never repeats the mid one [Scouts schedule]. Effects are paraphrased in
``docs/rules/arrakeen-scouts.md``.
"""

from typing import Final

from dune_imperium.content.arrakeen_scouts.abilities import (
    scouts_options,
    scouts_rank_rewards,
)
from dune_imperium.content.arrakeen_scouts.types import (
    ALL_POOLS,
    IMMORTALITY_POOLS,
    IMPERIUM_POOLS,
    UPRISING_POOLS,
    AppDefinition,
    AuctionKind,
    AuctionSlot,
    ScoutsAuction,
    ScoutsSale,
)

# The app's bid cap for the sealed auctions (D4: kept as is). The app never
# reads it for the open auction (Critical Moment, bid aloud); the project
# uses it there too as a bound on the spice a seat can hold (OQ-087).
MAX_AUCTION_BID: Final = 99
# Mercenaries' own cap: 0-3 spice, one troop each.
MAX_MERCENARIES_BID: Final = 3
# The most specimens one Immortality top-up returns before a Scouts recruit
# or a mission's parking: the most troops any of them takes at once (a test
# checks each; the original game's Fremen Mercenaries recruits twelve for six
# water, a seat's whole twelve troops). Mercenaries returns its shortfall by
# itself (OQ-074 (a)).
MAX_SPECIMEN_TOP_UP: Final = 12

_MID: Final = (5, 6)
_LATE: Final = (8, 9)

AUCTIONS: Final[tuple[ScoutsAuction, ...]] = (
    ScoutsAuction(
        auction_id="highest_bidder_mid",
        name="To The Highest Bidder",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.MID,
        rounds=_MID,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=ALL_POOLS,
        app=AppDefinition("Def_Auction_HighestBidder_Mid", 1),
        rank_rewards=scouts_rank_rewards("highest_bidder_mid"),
    ),
    ScoutsAuction(
        auction_id="highest_bidder_late",
        name="To The Highest Bidder",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.LATE,
        rounds=_LATE,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=ALL_POOLS,
        app=AppDefinition("Def_Auction_HighestBidder_Late", 1, 1),
        places=2,
        rank_rewards=scouts_rank_rewards("highest_bidder_late"),
    ),
    ScoutsAuction(
        auction_id="mercenaries",
        name="Mercenaries",
        kind=AuctionKind.MERCENARIES,
        slot=AuctionSlot.EITHER,
        rounds=(5, 9),
        currency="spice",
        max_bid=MAX_MERCENARIES_BID,
        pools=ALL_POOLS,
        app=AppDefinition("Def_Auction_Mercenaries", 3),
    ),
    ScoutsAuction(
        auction_id="competitive_study_mid",
        name="Competitive Study",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.MID,
        rounds=_MID,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=IMMORTALITY_POOLS,
        app=AppDefinition("Def_Auction_CompetitiveStudy_Mid", 4),
        rank_rewards=scouts_rank_rewards("competitive_study_mid"),
    ),
    ScoutsAuction(
        auction_id="competitive_study_late",
        name="Competitive Study",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.LATE,
        rounds=_LATE,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=IMMORTALITY_POOLS,
        app=AppDefinition("Def_Auction_CompetitiveStudy_Late", 4, 1),
        places=2,
        rank_rewards=scouts_rank_rewards("competitive_study_late"),
    ),
    ScoutsAuction(
        auction_id="spies_for_hire_mid",
        name="Spies for Hire",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.MID,
        rounds=_MID,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Auction_SpiesForHire_Mid", 5),
        rank_rewards=scouts_rank_rewards("spies_for_hire_mid"),
    ),
    ScoutsAuction(
        auction_id="spies_for_hire_late",
        name="Spies for Hire",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.LATE,
        rounds=_LATE,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Auction_SpiesForHire_Late", 5, 1),
        places=2,
        rank_rewards=scouts_rank_rewards("spies_for_hire_late"),
    ),
    ScoutsAuction(
        auction_id="critical_moment_mid",
        name="Critical Moment",
        kind=AuctionKind.OPEN_CARDS,
        slot=AuctionSlot.MID,
        rounds=_MID,
        currency="spice",
        max_bid=MAX_AUCTION_BID,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Auction_CriticalMoment_Mid", 6),
        revealed_cards=2,
    ),
    ScoutsAuction(
        auction_id="critical_moment_late",
        name="Critical Moment",
        kind=AuctionKind.OPEN_CARDS,
        slot=AuctionSlot.LATE,
        rounds=_LATE,
        currency="spice",
        max_bid=MAX_AUCTION_BID,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Auction_CriticalMoment_Late", 6, 1),
        places=2,
        revealed_cards=3,
    ),
    ScoutsAuction(
        auction_id="choam_negotiations_mid",
        name="CHOAM Negotiations",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.MID,
        rounds=_MID,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Auction_CHOAMNegotiations_Mid", 7),
        choam_only=True,
        rank_rewards=scouts_rank_rewards("choam_negotiations_mid"),
    ),
    ScoutsAuction(
        auction_id="choam_negotiations_late",
        name="CHOAM Negotiations",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.LATE,
        rounds=_LATE,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Auction_CHOAMNegotiations_Late", 7, 1),
        choam_only=True,
        places=2,
        rank_rewards=scouts_rank_rewards("choam_negotiations_late"),
    ),
    # --- The original game's own (stage P8b): Treachery, sealed bids in spice, ------
    # only the winners pay (docs/rules/arrakeen-scouts.md 8.1).
    ScoutsAuction(
        auction_id="treachery_mid",
        name="Treachery",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.MID,
        rounds=_MID,
        currency="spice",
        max_bid=MAX_AUCTION_BID,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Auction_Treachery_Mid", 2),
        rank_rewards=scouts_rank_rewards("treachery_mid"),
    ),
    ScoutsAuction(
        auction_id="treachery_late",
        name="Treachery",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.LATE,
        rounds=_LATE,
        currency="spice",
        max_bid=MAX_AUCTION_BID,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Auction_Treachery_Late", 2, 1),
        places=2,
        rank_rewards=scouts_rank_rewards("treachery_late"),
    ),
    # --- The original game's Mentat (stage P8c): open calls, each higher than ------
    # the highest so far; the highest caller pays and takes the Mentat for the
    # round (docs/rules/arrakeen-scouts.md 9a, OQ-162). The two share a family.
    ScoutsAuction(
        auction_id="mentat_mid",
        name="Mentat",
        kind=AuctionKind.OPEN_MENTAT,
        slot=AuctionSlot.MID,
        rounds=_MID,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Auction_Mentat_Mid", 0),
    ),
    ScoutsAuction(
        auction_id="mentat_late",
        name="Mentat",
        kind=AuctionKind.OPEN_MENTAT,
        slot=AuctionSlot.LATE,
        rounds=_LATE,
        # Spice, as the late auction's text and reminder say: the app's
        # costResource (Solari) is never read by an open auction (9a).
        currency="spice",
        max_bid=MAX_AUCTION_BID,
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Auction_Mentat_Late", 0, 1),
    ),
)

AUCTIONS_BY_ID: Final = {entry.auction_id: entry for entry in AUCTIONS}

SALES: Final[tuple[ScoutsSale, ...]] = (
    ScoutsSale(
        sale_id="unravel_the_future",
        name="Unravel the Future",
        options=scouts_options("unravel_the_future"),
        pools=ALL_POOLS,
        app=AppDefinition("Def_Sale_Future", 2),
    ),
    ScoutsSale(
        sale_id="imperium_connections",
        name="Imperium Connections",
        options=scouts_options("imperium_connections"),
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Sale_ImperiumConnections", 3),
    ),
    ScoutsSale(
        sale_id="secrets_for_sale",
        name="Secrets for Sale",
        options=scouts_options("secrets_for_sale"),
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Sale_SecretsForSale", 4),
    ),
    ScoutsSale(
        sale_id="shadow_warfare",
        name="Shadow Warfare",
        # Left of the arrow is the cost. A text line of the app adds that
        # every troop this sale recruits goes straight into the Conflict
        # (``spice.sale.description.shadowwarfare2``): RecruitToConflict.
        options=scouts_options("shadow_warfare"),
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Sale_ShadowWarfare", 5),
    ),
    # The original game's own (stage P8b).
    ScoutsSale(
        sale_id="water_peddlers",
        name="Soo-Soo Sook! Water Peddlers",
        options=scouts_options("water_peddlers"),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Sale_WaterPeddlers", 0),
    ),
    # Stage P8c: any number of water, two troops each into the Conflict (one
    # line per count, 9a).
    ScoutsSale(
        sale_id="fremen_mercenaries",
        name="Fremen Mercenaries",
        options=scouts_options("fremen_mercenaries"),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Sale_Fremen", 1),
    ),
)

SALES_BY_ID: Final = {entry.sale_id: entry for entry in SALES}
