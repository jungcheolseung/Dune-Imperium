"""Our content ids <-> app archetypes, and entity construction.

Every lookup the AI makes goes from one of our ids (card instance id, space
id, conflict id, contract id, leader id, post id, faction id) to the app
archetype whose attributes and abilities the app AI would read. The tables
are explicit (no fuzzy matching at runtime) and tests check that every id our
4-player Uprising content can deal maps to an archetype that is dealt in the
app's game with the same CHOAM setting.

Known content differences (``scratchpad R5`` / ``spec/archetypes.md``):
- The app's reserve holds Foldspace x6; our engine has no Foldspace.
- Our three Uprising promos are not in the app's Imperium deck (keep
  ``promo_cards`` off); they map to their app archetypes anyway, but those
  archetypes (``ImperiumArchetypes.Promo.*``) are not in ``ARCHETYPES``.
- Accept Contract, Dutiful Service, CHOAM Security and Trade Dispute have an
  ``...UP`` archetype (no CHOAM) and a ``...CHOAM`` one; pick by ``choam``.
"""

from dune_imperium.agents.app_ai.context import card_id
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.agents.app_ai.entities import Entity, Kind


def _both(short: str) -> tuple[str, str]:
    """An archetype that is the same with and without the CHOAM module."""

    return (short, short)


# card_id -> app archetype short name (starters, reserve, Imperium incl. CHOAM
# and promos).
CARD_ARCHETYPES: dict[str, str] = {
    # Starting deck (BaseSet starters).
    "convincing_argument": "ImperiumArchetypes.BaseSet.ConvincingArgument",
    "dagger": "ImperiumArchetypes.BaseSet.Dagger",
    "diplomacy": "ImperiumArchetypes.BaseSet.Diplomacy",
    "dune_the_desert_planet": "ImperiumArchetypes.BaseSet.DunetheDesertPlanet",
    "reconnaissance": "ImperiumArchetypes.BaseSet.Reconnaissance",
    "seek_allies": "ImperiumArchetypes.BaseSet.SeekAllies",
    "signet_ring": "ImperiumArchetypes.BaseSet.SignetRing",
    # Reserve stacks.
    "prepare_the_way": "ImperiumArchetypes.Uprising.PreparetheWay",
    "the_spice_must_flow": "ImperiumArchetypes.Uprising.TheSpiceMustFlowUP",
    # Imperium deck: base cards and the four CHOAM-only cards.
    "bene_gesserit_operative": "ImperiumArchetypes.Uprising.BeneGesseritOperative",
    "branching_path": "ImperiumArchetypes.Uprising.BranchingPath",
    "calculus_of_power": "ImperiumArchetypes.Uprising.CalculusofPower",
    "captured_mentat": "ImperiumArchetypes.Uprising.CapturedMentat",
    "cargo_runner": "ImperiumArchetypes.Uprising.CargoRunner",
    "chani_clever_tactician": "ImperiumArchetypes.Uprising.ChaniCleverTactician",
    "corrinth_city": "ImperiumArchetypes.Uprising.CorrinthCity",
    "covert_operation": "ImperiumArchetypes.Uprising.CovertOperation",
    "dangerous_rhetoric": "ImperiumArchetypes.Uprising.DangerousRhetoric",
    "delivery_agreement": "ImperiumArchetypes.Uprising.DeliveryAgreement",
    "desert_power": "ImperiumArchetypes.Uprising.DesertPowerImperium",
    "desert_survival": "ImperiumArchetypes.Uprising.DesertSurvival",
    "double_agent": "ImperiumArchetypes.Uprising.DoubleAgent",
    "ecological_testing_station": (
        "ImperiumArchetypes.Uprising.EcologicalTestingStation"
    ),
    "fedaykin_stilltent": "ImperiumArchetypes.Uprising.FedaykinStilltent",
    "guild_envoy": "ImperiumArchetypes.Uprising.GuildEnvoy",
    "guild_spy": "ImperiumArchetypes.Uprising.GuildSpy",
    "hidden_missive": "ImperiumArchetypes.Uprising.HiddenMissive",
    "imperial_spymaster": "ImperiumArchetypes.Uprising.ImperialSpymaster",
    "in_high_places": "ImperiumArchetypes.Uprising.InHighPlaces",
    "interstellar_trade": "ImperiumArchetypes.Uprising.InterstellarTrade",
    "junction_headquarters": "ImperiumArchetypes.Uprising.JunctionHeadquarters",
    "leadership": "ImperiumArchetypes.Uprising.Leadership",
    "long_live_the_fighters": "ImperiumArchetypes.Uprising.LongLivetheFighters",
    "maker_keeper": "ImperiumArchetypes.Uprising.MakerKeeper",
    "maula_pistol": "ImperiumArchetypes.Uprising.MaulaPistol",
    "northern_watermaster": "ImperiumArchetypes.Uprising.NorthernWatermaster",
    "overthrow": "ImperiumArchetypes.Uprising.Overthrow",
    "paracompass": "ImperiumArchetypes.Uprising.Paracompass",
    "price_is_no_object": "ImperiumArchetypes.Uprising.PriceisNoObject",
    "priority_contracts": "ImperiumArchetypes.Uprising.PriorityContracts",
    "public_spectacle": "ImperiumArchetypes.Uprising.PublicSpectacle",
    "rebel_supplier": "ImperiumArchetypes.Uprising.RebelSupplier",
    "reliable_informant": "ImperiumArchetypes.Uprising.ReliableInformant",
    "sardaukar_coordination": "ImperiumArchetypes.Uprising.SardaukarCoordination",
    "sardaukar_soldier": "ImperiumArchetypes.Uprising.SardaukarSoldier",
    "shishakli": "ImperiumArchetypes.Uprising.Shishakli",
    "smuggler_s_harvester": "ImperiumArchetypes.Uprising.SmugglersHarvester",
    "smuggler_s_haven": "ImperiumArchetypes.Uprising.SmugglersHaven",
    "southern_elders": "ImperiumArchetypes.Uprising.SouthernElders",
    "space_time_folding": "ImperiumArchetypes.Uprising.SpacetimeFolding",
    "spacing_guild_s_favor": "ImperiumArchetypes.Uprising.SpacingGuildsFavor",
    "spy_network": "ImperiumArchetypes.Uprising.SpyNetwork",
    "steersman": "ImperiumArchetypes.Uprising.Steersman",
    "stilgar_the_devoted": "ImperiumArchetypes.Uprising.StilgartheDevoted",
    "strike_fleet": "ImperiumArchetypes.Uprising.StrikeFleet",
    "subversive_advisor": "ImperiumArchetypes.Uprising.SubversiveAdvisor",
    "treacherous_maneuver": "ImperiumArchetypes.Uprising.TreacherousManeuver",
    "tread_in_darkness": "ImperiumArchetypes.Uprising.TreadinDarkness",
    "truthtrance": "ImperiumArchetypes.Uprising.Truthtrance",
    "undercover_asset": "ImperiumArchetypes.Uprising.UndercoverAsset",
    "unswerving_loyalty": "ImperiumArchetypes.Uprising.UnswervingLoyalty",
    "weirding_woman": "ImperiumArchetypes.Uprising.WeirdingWoman",
    "wheels_within_wheels": "ImperiumArchetypes.Uprising.WheelsWithinWheels",
    # Uprising promos. The app deals none of them (``ImperiumType = Promo``),
    # so ``data/archetypes.py`` (4-player Uprising only) does not hold these
    # three archetypes: the short names are the app's own, from the full
    # archetype extraction (``analysis/ai/spec/archetypes.json``). A lookup
    # raises ``KeyError`` in ``card_entity``; keep ``promo_cards`` off.
    "arrakis_revolt": "ImperiumArchetypes.Promo.ArrakisRevolt",
    "pivotal_gambit": "ImperiumArchetypes.Promo.PivotalGambit",
    "the_beast_s_spoils": "ImperiumArchetypes.Promo.TheBeastsSpoils",
}
# intrigue card_id -> app archetype short name.
INTRIGUE_ARCHETYPES: dict[str, str] = {
    "backed_by_choam": "IntrigueArchetypes.Uprising.BackedbyCHOAM",
    "buy_access": "IntrigueArchetypes.Uprising.BuyAccess",
    "call_to_arms": "IntrigueArchetypes.Uprising.CalltoArms",
    "change_allegiances": "IntrigueArchetypes.Uprising.ChangeAllegiances",
    "choam_profits": "IntrigueArchetypes.Uprising.CHOAMProfits",
    "contingency_plan": "IntrigueArchetypes.Uprising.ContingencyPlan",
    "councilor_s_ambition": "IntrigueArchetypes.Uprising.CouncilorsAmbition",
    "crysknife": "IntrigueArchetypes.Uprising.CrysknifeIntrigue",
    "cunning": "IntrigueArchetypes.Uprising.Cunning",
    "depart_for_arrakis": "IntrigueArchetypes.Uprising.DepartforArrakis",
    "desert_mouse": "IntrigueArchetypes.Uprising.DesertMouse",
    "detonation": "IntrigueArchetypes.Uprising.Detonation",
    "devour": "IntrigueArchetypes.Uprising.Devour",
    "distraction": "IntrigueArchetypes.Uprising.Distraction",
    "find_weakness": "IntrigueArchetypes.Uprising.FindWeakness",
    "go_to_ground": "IntrigueArchetypes.Uprising.GotoGround",
    "imperium_politics": "IntrigueArchetypes.Uprising.ImperiumPolitics",
    "impress": "IntrigueArchetypes.Uprising.Impress",
    "inspire_awe": "IntrigueArchetypes.Uprising.InspireAwe",
    "intelligence_report": "IntrigueArchetypes.Uprising.IntelligenceReport",
    "leverage": "IntrigueArchetypes.Uprising.Leverage",
    "manipulate": "IntrigueArchetypes.Uprising.ManipulateIntrigue",
    "market_opportunity": "IntrigueArchetypes.Uprising.MarketOpportunity",
    "mercenaries": "IntrigueArchetypes.Uprising.Mercenaries",
    "opportunism": "IntrigueArchetypes.Uprising.Opportunism",
    "ornithopter": "IntrigueArchetypes.Uprising.Ornithopter",
    "questionable_methods": "IntrigueArchetypes.Uprising.QuestionableMethods",
    "reach_agreement": "IntrigueArchetypes.Uprising.ReachAgreement",
    "secure_spice_trade": "IntrigueArchetypes.Uprising.SecureSpiceTrade",
    "shaddam_s_favor": "IntrigueArchetypes.Uprising.ShaddamsFavor",
    "shadow_alliance": "IntrigueArchetypes.Uprising.ShadowAlliance",
    "sietch_ritual": "IntrigueArchetypes.Uprising.SietchRitual",
    "special_mission": "IntrigueArchetypes.Uprising.SpecialMission",
    "spice_is_power": "IntrigueArchetypes.Uprising.SpiceIsPower",
    "spring_the_trap": "IntrigueArchetypes.Uprising.SpringtheTrap",
    "strategic_stockpiling": "IntrigueArchetypes.Uprising.StrategicStockpiling",
    "tactical_option": "IntrigueArchetypes.Uprising.TacticalOption",
    "unexpected_allies": "IntrigueArchetypes.Uprising.UnexpectedAllies",
    "weirding_combat": "IntrigueArchetypes.Uprising.WeirdingCombat",
}
# space_id -> (archetype without CHOAM, archetype with CHOAM).
SPACE_ARCHETYPES: dict[str, tuple[str, str]] = {
    "dutiful_service": (
        "SpaceArchetypes.Uprising.DutifulServiceUP",
        "SpaceArchetypes.Uprising.DutifulServiceCHOAM",
    ),
    "sardaukar": _both("SpaceArchetypes.Uprising.Sardaukar"),
    "deliver_supplies": _both("SpaceArchetypes.Uprising.DeliverSupplies"),
    "heighliner": _both("SpaceArchetypes.Uprising.HeighlinerUP"),
    "espionage": _both("SpaceArchetypes.Uprising.Espionage"),
    "secrets": _both("SpaceArchetypes.BaseSet.Secrets"),
    "desert_tactics": _both("SpaceArchetypes.Uprising.DesertTactics"),
    "fremkit": _both("SpaceArchetypes.Uprising.Fremkit"),
    "assembly_hall": _both("SpaceArchetypes.Uprising.AssemblyHall"),
    "gather_support": _both("SpaceArchetypes.Uprising.GatherSupport"),
    "high_council": _both("SpaceArchetypes.Uprising.HighCouncilUP"),
    "imperial_privilege": _both("SpaceArchetypes.Uprising.ImperialPrivilege"),
    "swordmaster": _both("SpaceArchetypes.Uprising.SwordmasterUP"),
    "arrakeen": _both("SpaceArchetypes.BaseSet.Arrakeen"),
    "research_station": _both("SpaceArchetypes.Uprising.ResearchStationUP"),
    "sietch_tabr": _both("SpaceArchetypes.Uprising.SietchTabrUP"),
    "spice_refinery": _both("SpaceArchetypes.Uprising.SpiceRefinery"),
    "accept_contract": (
        "SpaceArchetypes.Uprising.AcceptContractUP",
        "SpaceArchetypes.Uprising.AcceptContractCHOAM",
    ),
    "deep_desert": _both("SpaceArchetypes.Uprising.DeepDesert"),
    "hagga_basin": _both("SpaceArchetypes.Uprising.HaggaBasinUP"),
    "imperial_basin": _both("SpaceArchetypes.BaseSet.ImperialBasin"),
    "shipping": _both("SpaceArchetypes.Uprising.Shipping"),
}
# conflict card_id -> (archetype without CHOAM, archetype with CHOAM).
CONFLICT_ARCHETYPES: dict[str, tuple[str, str]] = {
    "skirmish_crysknife": _both("ConflictArchetypes.Uprising.SkirmishH"),
    "skirmish_ornithopter": _both("ConflictArchetypes.Uprising.SkirmishG"),
    "skirmish_desert_mouse": _both("ConflictArchetypes.Uprising.SkirmishI"),
    "choam_security": (
        "ConflictArchetypes.Uprising.CHOAMSecurityUP",
        "ConflictArchetypes.Uprising.CHOAMSecurityCHOAM",
    ),
    "spice_freighters": _both("ConflictArchetypes.Uprising.SpiceFreightersUP"),
    "siege_of_arrakeen": _both("ConflictArchetypes.Uprising.SiegeofArrakeenUP"),
    "seize_spice_refinery": _both("ConflictArchetypes.Uprising.SeizeSpiceRefineryUP"),
    "test_of_loyalty": _both("ConflictArchetypes.Uprising.TestofLoyaltyUP"),
    "shadow_contest": _both("ConflictArchetypes.Uprising.ShadowContestUP"),
    "secure_imperial_basin": _both("ConflictArchetypes.Uprising.SecureImperialBasinUP"),
    "protect_the_sietches": _both("ConflictArchetypes.Uprising.ProtecttheSietchesUP"),
    "trade_dispute": (
        "ConflictArchetypes.Uprising.TradeDisputeUP",
        "ConflictArchetypes.Uprising.TradeDisputeCHOAM",
    ),
    "propaganda": _both("ConflictArchetypes.Uprising.PropagandaUP"),
    "battle_for_imperial_basin": _both(
        "ConflictArchetypes.Uprising.BattleforImperialBasinUP"
    ),
    "battle_for_arrakeen": _both("ConflictArchetypes.Uprising.BattleforArrakeenUP"),
    "battle_for_spice_refinery": _both(
        "ConflictArchetypes.Uprising.BattleforSpiceRefineryUP"
    ),
}
# contract card_id -> app archetype short name.
CONTRACT_ARCHETYPES: dict[str, str] = {
    "acquire": "ContractArchetypes.Uprising.ContractBase_20",
    "arrakeen_i": "ContractArchetypes.Uprising.ContractBase_5",
    "arrakeen_ii": "ContractArchetypes.Uprising.ContractBase_4",
    "deliver_supplies": "ContractArchetypes.Uprising.ContractBase_14",
    "espionage_i": "ContractArchetypes.Uprising.ContractBase_17",
    "espionage_i_copy_2": "ContractArchetypes.Uprising.ContractBase_17",
    "harvest_3": "ContractArchetypes.Uprising.ContractBase_1",
    "harvest_3_copy_2": "ContractArchetypes.Uprising.ContractBase_1",
    "harvest_4": "ContractArchetypes.Uprising.ContractBase_3",
    "spice_refinery_i": "ContractArchetypes.Uprising.ContractBase_6",
    "heighliner_i": "ContractArchetypes.Uprising.ContractBase_16",
    "heighliner_ii": "ContractArchetypes.Uprising.ContractBase_15",
    "spice_refinery_ii": "ContractArchetypes.Uprising.ContractBase_7",
    "high_council_i": "ContractArchetypes.Uprising.ContractBase_10",
    "high_council_ii": "ContractArchetypes.Uprising.ContractBase_11",
    "immediate": "ContractArchetypes.Uprising.ContractBase_19",
    "research_station_i": "ContractArchetypes.Uprising.ContractBase_9",
    "research_station_ii": "ContractArchetypes.Uprising.ContractBase_8",
    "sardaukar_i": "ContractArchetypes.Uprising.ContractBase_12",
    "sardaukar_ii": "ContractArchetypes.Uprising.ContractBase_13",
}
# leader_id -> app archetype short name (incl. Lady Jessica's flipped face).
LEADER_ARCHETYPES: dict[str, str] = {
    "feyd_rautha_harkonnen": "LeaderArchetypes.Uprising.FeydRauthaHarkonnen",
    "gurney_halleck": "LeaderArchetypes.Uprising.GurneyHalleckLeader",
    "lady_amber_metulli": "LeaderArchetypes.Uprising.LadyAmberMetulli",
    "lady_jessica": "LeaderArchetypes.Uprising.LadyJessicaLeader",
    "lady_margot_fenring": "LeaderArchetypes.Uprising.LadyMargotFenring",
    "muad_dib": "LeaderArchetypes.Uprising.MuadDib",
    "princess_irulan": "LeaderArchetypes.Uprising.PrincessIrulan",
    "staban_tuek": "LeaderArchetypes.Uprising.StabanTuek",
    "shaddam_corrino_iv": "LeaderArchetypes.Uprising.ShaddamCorrinoIV",
    # Lady Jessica's flipped face (``PublicPlayerView.leader_face_id``).
    "reverend_mother_jessica": "LeaderArchetypes.Uprising.ReverendMotherJessica",
}
# post_id -> the app's observation post index (1-13).
POST_INDEX: dict[str, int] = {
    "emperor-sardaukar-dutiful-service": 1,
    "spacing-guild-heighliner-deliver-supplies": 2,
    "bene-gesserit-espionage-secrets": 3,
    "fremen-desert-tactics-fremkit": 4,
    "landsraad-high-council-imperial-privilege-swordmaster": 5,
    "landsraad-assembly-hall-gather-support": 6,
    "choam-shipping-accept-contract": 7,
    "arrakis-research-station-sietch-tabr": 8,
    "arrakis-research-station-spice-refinery": 9,
    "arrakis-spice-refinery-arrakeen": 10,
    "arrakis-deep-desert": 11,
    "arrakis-hagga-basin": 12,
    "arrakis-imperial-basin": 13,
}
# our faction id -> the app's Factions enum name.
FACTION_NAMES: dict[str, str] = {
    "emperor": "Emperor",
    "spacing_guild": "SpacingGuild",
    "bene_gesserit": "BeneGesserit",
    "fremen": "Fremen",
}


def _archetype(short: str) -> Archetype:
    return ARCHETYPES[short]


def card_entity(instance_id: str, owner: int | None = None) -> Entity:
    """A personal card (starter, reserve or Imperium) by instance id."""

    return Entity(
        Kind.CARD, instance_id, _archetype(CARD_ARCHETYPES[card_id(instance_id)]), owner
    )


def intrigue_entity(instance_id: str, owner: int | None = None) -> Entity:
    """An Intrigue card by instance id."""

    return Entity(
        Kind.INTRIGUE,
        instance_id,
        _archetype(INTRIGUE_ARCHETYPES[card_id(instance_id)]),
        owner,
    )


def contract_entity(instance_id: str, owner: int | None = None) -> Entity:
    """A CHOAM contract by instance id (``contract:<id>``)."""

    return Entity(
        Kind.CONTRACT,
        instance_id,
        _archetype(CONTRACT_ARCHETYPES[card_id(instance_id)]),
        owner,
    )


def space_entity(space_id: str, choam: bool) -> Entity:
    """A board space."""

    without, with_choam = SPACE_ARCHETYPES[space_id]
    return Entity(Kind.SPACE, space_id, _archetype(with_choam if choam else without))


def conflict_entity(conflict_id: str, choam: bool) -> Entity:
    """A Conflict card."""

    without, with_choam = CONFLICT_ARCHETYPES[conflict_id]
    return Entity(
        Kind.CONFLICT, conflict_id, _archetype(with_choam if choam else without)
    )


def conflict_reward_entities(conflict_id: str, choam: bool) -> tuple[Entity, ...]:
    """The 1st/2nd/3rd reward archetypes of a Conflict card, in place order.

    Read from the card archetype's ``ConflictRewardArchetypes``.
    """

    card = conflict_entity(conflict_id, choam)
    return tuple(
        Entity(Kind.CONFLICT, conflict_id, _archetype(short))
        for short in card.list_attr("ConflictRewardArchetypes")
    )


def leader_entity(leader_id: str, face_id: str | None = None) -> Entity:
    """A leader (the flipped face when ``face_id`` names one)."""

    key = face_id if face_id and face_id in LEADER_ARCHETYPES else leader_id
    return Entity(Kind.LEADER, leader_id, _archetype(LEADER_ARCHETYPES[key]))


def post_entity(post_id: str, owner: int | None = None) -> Entity:
    """An observation post (the app's ``WormObservationPost``)."""

    return Entity(Kind.POST, post_id, None, owner)


def spy_entity(post_id: str, owner: int) -> Entity:
    """A spy standing on ``post_id``."""

    return Entity(Kind.SPY, post_id, None, owner)


def agent_entity(space_id: str, owner: int) -> Entity:
    """An agent standing on ``space_id``."""

    return Entity(Kind.AGENT, space_id, None, owner)


def track_entity(faction: str) -> Entity:
    """A faction influence track (our faction id)."""

    return Entity(Kind.TRACK, faction, None)
