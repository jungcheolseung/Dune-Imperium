"""Arrakeen Scouts missions [Scouts mission: <name>].

Each ``MissionKind`` has its own engine hook; the numbers here are the
pieces the app tells players to place. Effects are paraphrased in
``docs/rules/arrakeen-scouts.md``. The Uprising pools' missions come first,
then Rise of Ix's three and the original game's own (stage P8b-2), so no
observation column of an older mission moves.
"""

from typing import Final

from dune_imperium.content.arrakeen_scouts.types import (
    ALL_POOLS,
    IMMORTALITY_POOLS,
    IMPERIUM_IMMORTALITY_ONLY,
    IMPERIUM_POOLS,
    UPRISING_IMMORTALITY_ONLY,
    UPRISING_ONLY,
    UPRISING_POOLS,
    AppDefinition,
    Mission,
    MissionKind,
    TroopSource,
)
from dune_imperium.content.core.effects import (
    DiscardFromHand,
    EffectSection,
    GainResources,
    LoseGarrisonTroops,
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
        pools=UPRISING_POOLS,
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
        pools=UPRISING_POOLS,
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
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Mission_DesertRiding", 15),
        space_id="hagga_basin",
    ),
    Mission(
        mission_id="urban_surveillance",
        name="Urban Surveillance",
        kind=MissionKind.URBAN_SURVEILLANCE,
        mission_type=0,
        rounds=(2, 3),
        pools=UPRISING_POOLS,
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
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Mission_ValuedInformants_PlanetaryExploration", 15, 1),
        goods=GainResources(spice=1),
    ),
    Mission(
        mission_id="choam_research",
        name="CHOAM Research",
        kind=MissionKind.CHOAM_RESEARCH,
        mission_type=0,
        rounds=(2, 3),
        pools=UPRISING_POOLS,
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
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Mission_CHOAMEscort", 17),
        choam_only=True,
        # The second line's pieces wait on one of the seat's face-up
        # Contracts and are gained when that Contract is completed.
        choices=(
            EffectSection(rewards=(RecruitTroops(1),)),
            EffectSection(rewards=(GainResources(solari=1, spice=1),)),
        ),
    ),
    Mission(
        mission_id="sponsored_research",
        name="Sponsored Research",
        kind=MissionKind.SPONSORED_RESEARCH,
        mission_type=0,
        rounds=(2, 2),
        pools=IMMORTALITY_POOLS,
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
        pools=IMMORTALITY_POOLS,
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
        pools=UPRISING_POOLS,
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
        pools=UPRISING_POOLS,
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
        pools=UPRISING_POOLS,
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
        pools=UPRISING_POOLS,
        app=AppDefinition("Def_Mission_SendForAid", 21),
        space_id="gather_support",
        parked_troops=1,
        troop_source=TroopSource.GARRISON,
        seat_goods=GainResources(water=1),
        # Not in the Uprising+Ix pools: the half overlay covers Gather
        # Support [Main p. 18] [Scouts schedule].
        no_rise_of_ix=True,
    ),
    Mission(
        mission_id="coordinate_with_the_emperor",
        name="Coordinate With The Emperor",
        kind=MissionKind.COORDINATE_WITH_THE_EMPEROR,
        mission_type=1,
        rounds=(3, 3),
        pools=UPRISING_IMMORTALITY_ONLY,
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
        pools=IMMORTALITY_POOLS,
        app=AppDefinition("Def_Mission_TleilaxuOffering", 11),
        # On the third space of the Tleilaxu track.
        parked_troops=2,
        troop_source=TroopSource.SUPPLY,
    ),
    # --- Rise of Ix (stage P7f-2) -----------------------------------------------
    # The app's Uprising+Ix and Uprising+Ix+Immortality pools add these three
    # (and drop Send for Aid) [Scouts schedule]; after every older mission,
    # so their observation columns keep their places.
    Mission(
        mission_id="secret_stash",
        name="Secret Stash",
        kind=MissionKind.SECRET_STASH,
        mission_type=0,
        rounds=(3, 3),
        pools=ALL_POOLS,
        app=AppDefinition("Def_Mission_SecretStash", 6),
        space_id="smuggling",
        goods=GainResources(spice=2),
        rise_of_ix_only=True,
    ),
    Mission(
        mission_id="armed_escort",
        name="Armed Escort",
        kind=MissionKind.ARMED_ESCORT,
        mission_type=0,
        rounds=(2, 3),
        pools=ALL_POOLS,
        app=AppDefinition("Def_Mission_ArmedEscort", 7),
        space_id="dreadnought",
        # Each seat's, with no choice: a dreadnought of its supply and the
        # bank's spice under it.
        parked_dreadnoughts=1,
        seat_goods=GainResources(spice=1),
        rise_of_ix_only=True,
    ),
    Mission(
        mission_id="stowaways",
        name="Stowaways",
        kind=MissionKind.STOWAWAYS,
        mission_type=1,
        rounds=(2, 3),
        pools=ALL_POOLS,
        app=AppDefinition("Def_Mission_Stowaways", 8),
        space_id="smuggling",
        participation_cost=(PayResources(spice=1),),
        parked_troops=2,
        troop_source=TroopSource.SUPPLY,
        rise_of_ix_only=True,
    ),
    # --- The original game's own (stage P8b-2) ----------------------------------
    # The app's original pools (docs/rules/arrakeen-scouts.md 9a); the ones
    # whose mechanism an earlier mission already has. After Rise of Ix's, so
    # every older observation column keeps its place.
    Mission(
        mission_id="space_travel_deal",
        name="Space Travel Deal",
        kind=MissionKind.SPACE_TRAVEL_DEAL,
        mission_type=0,
        rounds=(2, 3),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Mission_SpaceTravel", 0),
        space_id="imperium_heighliner",
        goods=GainResources(solari=3),
    ),
    Mission(
        mission_id="muster_spice_incentive",
        name="Muster an Army - Spice Incentive",
        kind=MissionKind.MUSTER_SPICE_INCENTIVE,
        mission_type=0,
        rounds=(2, 3),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Mission_MusterArmy_Spice", 1),
        space_id="rally_troops",
        goods=GainResources(spice=2),
        # Rally Troops is covered by the Rise of Ix overlay [Main p. 18]
        # (docs/rules/rise-of-ix.md 3), so the app's +Ix pools drop both
        # Muster missions.
        no_rise_of_ix=True,
    ),
    Mission(
        mission_id="muster_strongarmed_alliance",
        name="Muster an Army - Strongarmed Alliance",
        kind=MissionKind.MUSTER_STRONGARMED_ALLIANCE,
        mission_type=0,
        rounds=(2, 3),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Mission_MusterArmy_StrongArm", 1, 1),
        space_id="rally_troops",
        # Each seat's, with no choice (no "may" in the app's text): a troop of
        # its supply [Scouts mission: Muster an Army - Strongarmed Alliance].
        parked_troops=1,
        troop_source=TroopSource.SUPPLY,
        no_rise_of_ix=True,
    ),
    Mission(
        mission_id="botanical_secrets_in_the_desert",
        name="Botanical Testing - Secrets in the Desert",
        kind=MissionKind.BOTANICAL_SECRETS_IN_THE_DESERT,
        mission_type=0,
        rounds=(2, 3),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Mission_BotanicalTesting_Secrets", 2, 1),
        space_id="imperium_research_station",
        goods_cards=2,
    ),
    Mission(
        mission_id="genetic_research",
        name="Genetic Research",
        kind=MissionKind.GENETIC_RESEARCH,
        mission_type=1,
        rounds=(2, 3),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Mission_GeneticResearch", 3),
        space_id="selective_breeding",
        parked_troops=1,
        troop_source=TroopSource.GARRISON,
        seat_goods=GainResources(solari=2),
    ),
    Mission(
        mission_id="guild_maneuvers",
        name="Guild Maneuvers",
        kind=MissionKind.GUILD_MANEUVERS,
        mission_type=1,
        rounds=(3, 3),
        pools=IMPERIUM_POOLS,
        # The app's spelling of the asset.
        app=AppDefinition("Def_Mission_GuildManuevers", 5),
        space_id="foldspace",
        participation_cost=(PayResources(spice=1),),
        parked_troops=2,
        troop_source=TroopSource.SUPPLY,
        # Not for a covered space (Foldspace stays with Rise of Ix): the app's
        # base+Ix schedule simply lists no Guild Maneuvers [Scouts schedule].
        no_rise_of_ix=True,
    ),
    Mission(
        mission_id="imperium_coordinate_with_the_emperor",
        name="Coordinate With The Emperor",
        kind=MissionKind.COORDINATE_WITH_THE_EMPEROR,
        mission_type=1,
        rounds=(3, 3),
        pools=IMPERIUM_IMMORTALITY_ONLY,
        # The original game's variant: the same mechanism as the Uprising one
        # (so the same kind), on Conspire, in a family of its own.
        app=AppDefinition("Def_Mission_CoordinateWithTheEmporer", 12),
        space_id="conspire",
        parked_troops=1,
        troop_source=TroopSource.SPECIMENS,
        seat_goods=GainResources(solari=2),
    ),
    Mission(
        mission_id="sapho_juice",
        name="Sapho Juice",
        kind=MissionKind.SAPHO_JUICE,
        mission_type=1,
        rounds=(2, 3),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Mission_SaphoJuice", 4),
        space_id="mentat",
        # Each seat's, with no choice: one of its own Control markers on the
        # Mentat space with the bank's spice on it (the marker rows of Prison
        # Planet, without its troop cost).
        seat_goods=GainResources(spice=1),
    ),
    # Stage P8c: a way in paid with a card of the seat's choice. Botanical
    # Testing's other mission, so the two share a family.
    Mission(
        mission_id="botanical_stationed_support",
        name="Botanical Testing - Stationed Support",
        kind=MissionKind.BOTANICAL_STATIONED_SUPPORT,
        mission_type=0,
        rounds=(2, 3),
        pools=IMPERIUM_POOLS,
        app=AppDefinition("Def_Mission_BotanicalTesting_Support", 2),
        space_id="imperium_research_station",
        participation_cost=(DiscardFromHand(1),),
        parked_troops=2,
        troop_source=TroopSource.SUPPLY,
    ),
)

MISSIONS_BY_ID: Final = {entry.mission_id: entry for entry in MISSIONS}
