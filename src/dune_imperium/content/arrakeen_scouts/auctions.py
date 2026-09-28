"""Arrakeen Scouts auctions and sales [Scouts auction: <name>], [Scouts sale: <name>].

A mid and a late definition of the same auction share a family, so the late
draw never repeats the mid one [Scouts schedule]. Effects are paraphrased in
``docs/rules/arrakeen-scouts.md``.
"""

from typing import Final

from dune_imperium.content.arrakeen_scouts.types import (
    BOTH_POOLS,
    IMMORTALITY_ONLY,
    AppDefinition,
    AuctionKind,
    AuctionSlot,
    RecruitToConflict,
    ScoutsAuction,
    ScoutsOption,
    ScoutsSale,
)
from dune_imperium.content.uprising.effect_dsl import (
    DrawIntrigueCards,
    DrawPersonalCards,
    GainResources,
    GenerateSpecimens,
    PayResources,
    PlaceSpy,
    RecallSpy,
    Research,
    TakeContract,
)

# The app's bid cap for the sealed auctions (D4: kept as is). The app never
# reads it for the open auction (Critical Moment, bid aloud); the project
# uses it there too as a bound on the spice a seat can hold (OQ-087).
MAX_AUCTION_BID: Final = 99
# Mercenaries' own cap: 0-3 spice, one troop each.
MAX_MERCENARIES_BID: Final = 3

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
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Auction_HighestBidder_Mid", 1),
        rank_rewards=((DrawPersonalCards(1),),),
    ),
    ScoutsAuction(
        auction_id="highest_bidder_late",
        name="To The Highest Bidder",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.LATE,
        rounds=_LATE,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Auction_HighestBidder_Late", 1, 1),
        places=2,
        rank_rewards=((DrawPersonalCards(2),), (DrawPersonalCards(1),)),
    ),
    ScoutsAuction(
        auction_id="mercenaries",
        name="Mercenaries",
        kind=AuctionKind.MERCENARIES,
        slot=AuctionSlot.EITHER,
        rounds=(5, 9),
        currency="spice",
        max_bid=MAX_MERCENARIES_BID,
        pools=BOTH_POOLS,
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
        pools=IMMORTALITY_ONLY,
        app=AppDefinition("Def_Auction_CompetitiveStudy_Mid", 4),
        rank_rewards=((Research(), GenerateSpecimens(1)),),
    ),
    ScoutsAuction(
        auction_id="competitive_study_late",
        name="Competitive Study",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.LATE,
        rounds=_LATE,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=IMMORTALITY_ONLY,
        app=AppDefinition("Def_Auction_CompetitiveStudy_Late", 4, 1),
        places=2,
        rank_rewards=((Research(), GenerateSpecimens(1)), (Research(),)),
    ),
    ScoutsAuction(
        auction_id="spies_for_hire_mid",
        name="Spies for Hire",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.MID,
        rounds=_MID,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Auction_SpiesForHire_Mid", 5),
        rank_rewards=((PlaceSpy(),),),
    ),
    ScoutsAuction(
        auction_id="spies_for_hire_late",
        name="Spies for Hire",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.LATE,
        rounds=_LATE,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Auction_SpiesForHire_Late", 5, 1),
        places=2,
        rank_rewards=((PlaceSpy(), DrawIntrigueCards(1)), (PlaceSpy(),)),
    ),
    ScoutsAuction(
        auction_id="critical_moment_mid",
        name="Critical Moment",
        kind=AuctionKind.OPEN_CARDS,
        slot=AuctionSlot.MID,
        rounds=_MID,
        currency="spice",
        max_bid=MAX_AUCTION_BID,
        pools=BOTH_POOLS,
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
        pools=BOTH_POOLS,
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
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Auction_CHOAMNegotiations_Mid", 7),
        choam_only=True,
        rank_rewards=((TakeContract(1),),),
    ),
    ScoutsAuction(
        auction_id="choam_negotiations_late",
        name="CHOAM Negotiations",
        kind=AuctionKind.SEALED,
        slot=AuctionSlot.LATE,
        rounds=_LATE,
        currency="solari",
        max_bid=MAX_AUCTION_BID,
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Auction_CHOAMNegotiations_Late", 7, 1),
        choam_only=True,
        places=2,
        rank_rewards=((TakeContract(1), DrawIntrigueCards(1)), (TakeContract(1),)),
    ),
)

AUCTIONS_BY_ID: Final = {entry.auction_id: entry for entry in AUCTIONS}

SALES: Final[tuple[ScoutsSale, ...]] = (
    ScoutsSale(
        sale_id="unravel_the_future",
        name="Unravel the Future",
        options=(
            ScoutsOption(
                costs=(PayResources(spice=1),), rewards=(DrawPersonalCards(1),)
            ),
            ScoutsOption(
                costs=(PayResources(spice=3),), rewards=(DrawPersonalCards(2),)
            ),
        ),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Sale_Future", 2),
    ),
    ScoutsSale(
        sale_id="imperium_connections",
        name="Imperium Connections",
        options=(
            ScoutsOption(costs=(PayResources(solari=2),), rewards=(PlaceSpy(),)),
            ScoutsOption(
                costs=(PayResources(solari=2),), rewards=(GainResources(water=1),)
            ),
        ),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Sale_ImperiumConnections", 3),
    ),
    ScoutsSale(
        sale_id="secrets_for_sale",
        name="Secrets for Sale",
        options=(
            ScoutsOption(
                costs=(PayResources(spice=1),), rewards=(DrawIntrigueCards(1),)
            ),
            ScoutsOption(
                costs=(PayResources(spice=3),), rewards=(DrawIntrigueCards(2),)
            ),
        ),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Sale_SecretsForSale", 4),
    ),
    ScoutsSale(
        sale_id="shadow_warfare",
        name="Shadow Warfare",
        # Icon-only in the app: read left of the arrow as the cost.
        options=(
            ScoutsOption(
                costs=(RecallSpy(1),),
                rewards=(RecruitToConflict(1), GainResources(spice=1)),
            ),
            ScoutsOption(
                costs=(RecallSpy(2),),
                rewards=(RecruitToConflict(3), GainResources(spice=2)),
            ),
        ),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Sale_ShadowWarfare", 5),
    ),
)

SALES_BY_ID: Final = {entry.sale_id: entry for entry in SALES}
