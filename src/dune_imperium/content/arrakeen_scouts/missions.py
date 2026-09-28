"""Arrakeen Scouts missions [Scouts mission: <name>].

Each ``MissionKind`` has its own engine hook; the numbers here are the
pieces the app tells players to place. Effects are paraphrased in
``docs/rules/arrakeen-scouts.md``.
"""

from typing import Final

from dune_imperium.content.arrakeen_scouts.types import (
    BOTH_POOLS,
    IMMORTALITY_ONLY,
    UPRISING_ONLY,
    AppDefinition,
    LoseGarrisonTroops,
    Mission,
    MissionKind,
    ScoutsOption,
    TroopSource,
)
from dune_imperium.content.uprising.effect_dsl import (
    GainResources,
    PayResources,
    RecruitTroops,
)

MISSIONS: Final[tuple[Mission, ...]] = (
    # --- Type 0 -------------------------------------------------------------------
    Mission(
        mission_id="security_detail",
        name="Security Detail",
        kind=MissionKind.SECURITY_DETAIL,
        mission_type=0,
        rounds=(2, 3),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Mission_SecurityDetail", 13),
        space_id="deliver_supplies",
        parked_troops=1,
        troop_source=TroopSource.SUPPLY,
    ),
    Mission(
        mission_id="imperial_reserve",
        name="Imperial Reserve",
        kind=MissionKind.IMPERIAL_RESERVE,
        mission_type=0,
        rounds=(2, 3),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Mission_ImperialReserve", 14),
        space_id="imperial_privilege",
        goods=GainResources(solari=2, spice=1),
    ),
    Mission(
        mission_id="desert_riding",
        name="Desert Riding",
        kind=MissionKind.DESERT_RIDING,
        mission_type=0,
        rounds=(2, 3),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Mission_DesertRiding", 15),
        space_id="hagga_basin",
    ),
    Mission(
        mission_id="urban_surveillance",
        name="Urban Surveillance",
        kind=MissionKind.URBAN_SURVEILLANCE,
        mission_type=0,
        rounds=(2, 3),
        pools=BOTH_POOLS,
        # Shares family 15.0 with Desert Riding in the app's data.
        app=AppDefinition("Def_Mission_ValuedInformants_UrbanSurveillance", 15),
        goods=GainResources(solari=1),
    ),
    Mission(
        mission_id="planetary_exploration",
        name="Planetary Exploration",
        kind=MissionKind.PLANETARY_EXPLORATION,
        mission_type=0,
        rounds=(2, 3),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Mission_ValuedInformants_PlanetaryExploration", 15, 1),
        goods=GainResources(spice=1),
    ),
    Mission(
        mission_id="choam_research",
        name="CHOAM Research",
        kind=MissionKind.CHOAM_RESEARCH,
        mission_type=0,
        rounds=(2, 3),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Mission_CHOAMResearch", 16),
        choam_only=True,
        space_id="research_station",
        goods_cards=2,
    ),
    Mission(
        mission_id="choam_escort",
        name="CHOAM Escort",
        kind=MissionKind.CHOAM_ESCORT,
        mission_type=0,
        rounds=(2, 3),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Mission_CHOAMEscort", 17),
        choam_only=True,
        # The second line's pieces wait on one of the seat's face-up
        # Contracts and are gained when that Contract is completed.
        choices=(
            ScoutsOption(rewards=(RecruitTroops(1),)),
            ScoutsOption(rewards=(GainResources(solari=1, spice=1),)),
        ),
    ),
    Mission(
        mission_id="sponsored_research",
        name="Sponsored Research",
        kind=MissionKind.SPONSORED_RESEARCH,
        mission_type=0,
        rounds=(2, 2),
        pools=IMMORTALITY_ONLY,
        app=AppDefinition("Def_Mission_SponsoredResearch", 9),
        # Beside the Helix on the research track.
        goods=GainResources(spice=2),
    ),
    Mission(
        mission_id="back_room_deal",
        name="Back Room Deal",
        kind=MissionKind.BACK_ROOM_DEAL,
        mission_type=0,
        rounds=(2, 3),
        pools=IMMORTALITY_ONLY,
        app=AppDefinition("Def_Mission_BackRoomDeal", 10),
        # On Reclaimed Forces in the Tleilaxu Row.
        goods=GainResources(solari=2),
    ),
    # --- Type 1 -------------------------------------------------------------------
    Mission(
        mission_id="prison_planet",
        name="Prison Planet",
        kind=MissionKind.PRISON_PLANET,
        mission_type=1,
        rounds=(2, 3),
        pools=UPRISING_ONLY,
        app=AppDefinition("Def_Mission_EliteSardaukar_PrisonPlanet", 18),
        space_id="sardaukar",
        participation_cost=(LoseGarrisonTroops(1),),
        seat_goods=GainResources(spice=2),
    ),
    Mission(
        mission_id="emperors_schemes",
        name="Emperor's Schemes",
        kind=MissionKind.EMPERORS_SCHEMES,
        mission_type=1,
        rounds=(2, 3),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Mission_EliteSardaukar_EmperorsSchemes", 18, 1),
        space_id="sardaukar",
        goods_cards=2,
    ),
    Mission(
        mission_id="fedaykin_assistance",
        name="Fedaykin Assistance",
        kind=MissionKind.FEDAYKIN_ASSISTANCE,
        mission_type=1,
        rounds=(3, 3),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Mission_FedaykinAssistance", 19),
        space_id="desert_tactics",
        participation_cost=(PayResources(spice=1),),
        parked_troops=2,
        troop_source=TroopSource.SUPPLY,
    ),
    Mission(
        mission_id="weirding_warfare",
        name="Weirding Warfare",
        kind=MissionKind.WEIRDING_WARFARE,
        mission_type=1,
        rounds=(2, 3),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Mission_WeirdingWarfare", 20),
        space_id="espionage",
        participation_cost=(PayResources(solari=2),),
        parked_troops=2,
        troop_source=TroopSource.SUPPLY,
    ),
    Mission(
        mission_id="send_for_aid",
        name="Send for Aid",
        kind=MissionKind.SEND_FOR_AID,
        mission_type=1,
        rounds=(2, 3),
        pools=BOTH_POOLS,
        app=AppDefinition("Def_Mission_SendForAid", 21),
        space_id="gather_support",
        parked_troops=1,
        troop_source=TroopSource.GARRISON,
        seat_goods=GainResources(water=1),
    ),
    Mission(
        mission_id="coordinate_with_the_emperor",
        name="Coordinate With The Emperor",
        kind=MissionKind.COORDINATE_WITH_THE_EMPEROR,
        mission_type=1,
        rounds=(3, 3),
        pools=IMMORTALITY_ONLY,
        # The Uprising variant (the base-game one uses Conspire). Family
        # 18.0 like Prison Planet, which it replaces in this pool.
        app=AppDefinition("Def_Mission_CoordinateWithTheEmporer2", 18),
        space_id="sardaukar",
        parked_troops=1,
        troop_source=TroopSource.SPECIMENS,
        seat_goods=GainResources(solari=2),
    ),
    Mission(
        mission_id="tleilaxu_offering",
        name="Tleilaxu Offering",
        kind=MissionKind.TLEILAXU_OFFERING,
        mission_type=1,
        rounds=(2, 2),
        pools=IMMORTALITY_ONLY,
        app=AppDefinition("Def_Mission_TleilaxuOffering", 11),
        # On the third space of the Tleilaxu track.
        parked_troops=2,
        troop_source=TroopSource.SUPPLY,
    ),
)

MISSIONS_BY_ID: Final = {entry.mission_id: entry for entry in MISSIONS}
