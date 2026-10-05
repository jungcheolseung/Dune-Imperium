"""The app-style data layer: ``data/synthetic.py`` and its catalog mapping.

``scripts/dwgr/app_ai_synth.py`` builds the synthetic archetypes of the items
the Steam app does not have (docs/app-ai-plan.md §11.3, §11.7) from our
content definitions and the rules the specs fitted on the app's data. These
tests pin:

- the generator reproduces ``data/synthetic.py`` byte for byte;
- every id our Bloodlines / Tech Module / Ruthless Leadership / Arrakeen
  Scouts content can deal maps to an archetype through the catalog;
- the printed numbers agree with the content;
- the specs' value tables (docs/app-ai/bloodlines-cards.md §1.1, §1.7, §3.0,
  §4.0, §5, §6, §7; docs/app-ai/bloodlines-systems.md §2.1, §3.2, §4, §5, §6;
  docs/app-ai/scouts.md §5) and worked values are reproduced;
- no synthetic short name is an app name, and every app class a synthetic
  archetype reuses has a port (the app-style ``AppStyle`` classes are the
  later stages' work);
- the board overlays exist only with their option (games without Bloodlines
  or Scouts keep the app's archetype objects).
"""

# ruff: noqa: E501  (the spec tables are transcribed one row per item)

import importlib.util
import sys
from collections.abc import Mapping
from dataclasses import replace
from functools import cache
from pathlib import Path
from types import ModuleType

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import catalog
from dune_imperium.agents.app_ai import testing as _t
from dune_imperium.agents.app_ai.abilities import PORTS
from dune_imperium.agents.app_ai.abilities.base import Timing
from dune_imperium.agents.app_ai.abilities.tech import ChaumurkyAbility, is_tech_tile
from dune_imperium.agents.app_ai.catalog import (
    BLOODLINES_SPACE_ARCHETYPES,
    CARD_ARCHETYPES,
    COMMANDER_SPACES,
    CONFLICT_ARCHETYPES,
    CONTRACT_ARCHETYPES,
    EYES_ON_ARRAKIS_SPACES,
    INTRIGUE_ARCHETYPES,
    LEADER_ARCHETYPES,
    NAVIGATION_ARCHETYPES,
    SCOUTS_LINE_ARCHETYPES,
    SKILL_ARCHETYPES,
    SPACE_ARCHETYPES,
    TECH_ARCHETYPES,
    TECH_SPACES,
    card_entity,
    commander_entity,
    conflict_entity,
    conflict_reward_entities,
    contract_entity,
    intrigue_entity,
    leader_entity,
    navigation_entity,
    scouts_line_entity,
    skill_entity,
    space_archetype,
    space_entity,
    tech_entity,
)
from dune_imperium.agents.app_ai.context import AppContext, Board
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.agents.app_ai.data.synthetic import SCOUTS_LINES, SYNTHETIC
from dune_imperium.agents.app_ai.entities import Kind
from dune_imperium.agents.app_ai.profile import tech as pt
from dune_imperium.content.arrakeen_scouts.auctions import AUCTIONS, SALES
from dune_imperium.content.arrakeen_scouts.events import EVENTS
from dune_imperium.content.arrakeen_scouts.missions import MISSIONS
from dune_imperium.content.arrakeen_scouts.subcommittees import SUBCOMMITTEES
from dune_imperium.content.arrakeen_scouts.types import AuctionKind
from dune_imperium.content.bloodlines.sardaukar import (
    COMMANDER_SETUP_SPACE_IDS,
    SKILLS,
    skill_tile_instance_ids,
)
from dune_imperium.content.bloodlines.tech import TECH_TILES, tech_tiles_for
from dune_imperium.content.uprising.board import BOARD_SPACES, BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS, conflicts_by_tier
from dune_imperium.content.uprising.contracts import (
    BLOODLINES_CONTRACTS,
    contract_instance_ids,
)
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS,
    intrigue_deck_instance_ids,
    navigation_card_instance_ids,
    twisted_intrigue_instance_ids,
)
from dune_imperium.content.uprising.leaders import leaders_for_choam
from dune_imperium.content.uprising.types import AgentIcon, ConflictTier
from dune_imperium.core.state import GameState
from dune_imperium.rules.scouts_missions import _TO_CONFLICT

REPO = Path(__file__).resolve().parents[4]
SYNTH_SCRIPT = REPO / "scripts/dwgr/app_ai_synth.py"
SYNTH_MODULE = REPO / "src/dune_imperium/agents/app_ai/data/synthetic.py"
BL = "worm.canis.abilities.AppStyle.Bloodlines."
SC = "worm.canis.abilities.AppStyle.Scouts."


@cache
def synth() -> ModuleType:
    """The generator script, imported from its file."""

    spec = importlib.util.spec_from_file_location("app_ai_synth", SYNTH_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["app_ai_synth"] = module
    spec.loader.exec_module(module)
    return module


def arch(short: str) -> Archetype:
    return SYNTHETIC[short]


def attrs(short: str) -> Mapping[str, object]:
    return SYNTHETIC[short].attributes


def archetype_list(archetype: Archetype, name: str) -> tuple[str, ...]:
    value = archetype.attributes.get(name, ())
    assert isinstance(value, tuple)
    return tuple(str(item) for item in value)


def last(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def abilities(short: str) -> tuple[str, ...]:
    value = attrs(short).get("WormAbilityIDs", ())
    assert isinstance(value, tuple)
    return tuple(last(str(v)) for v in value)


# ---------------------------------------------------------------------------
# The generator and the module
# ---------------------------------------------------------------------------


def test_the_generator_reproduces_the_module_byte_for_byte() -> None:
    assert synth().render(SYNTH_MODULE) == SYNTH_MODULE.read_text()


def test_the_module_has_one_archetype_per_spec_item() -> None:
    kinds: dict[str, int] = {}
    for short in SYNTHETIC:
        prefix = short.split(".", 1)[0]
        kinds[prefix] = kinds.get(prefix, 0) + 1
    assert kinds == {
        "ImperiumArchetypes": 27,  # bloodlines-cards.md §3 (27 identities)
        "IntrigueArchetypes": 18 + 12,  # §4, §5
        "NavigationArchetypes": 10,  # bloodlines-systems.md §5
        "ConflictArchetypes": 2 + 6,  # cards.md §6: cards and reward rows
        "ContractArchetypes": 8,  # §7
        "LeaderArchetypes": 9,  # systems §4
        "CommanderArchetypes": 1,  # systems §2.1
        "SkillArchetypes": 7,
        "TechTileArchetypes": 18,  # systems §3.2
        "SpaceArchetypes": 1,  # systems §6
        # scouts.md §5: 14 + 9 + 42 + 12 + 8 = 85 lines
        "SubcommitteeArchetypes": 14,
        "MissionArchetypes": 9,
        "EventArchetypes": 42,
        "AuctionArchetypes": 12,
        "SaleArchetypes": 8,
    }
    for short, archetype in SYNTHETIC.items():
        assert archetype.short == short
        assert archetype.attributes["ArchID"] == short
        assert ".AppStyle." in short
        assert not archetype.in_uprising and not archetype.in_uprising_choam


def test_no_synthetic_name_is_an_app_name() -> None:
    """Plan §11.3: ``AppStyle`` short names, and no PascalName equals the
    last part of an app short name (cards.md §0; R8's false friends)."""

    assert not set(SYNTHETIC) & set(ARCHETYPES)
    app_last = {last(short) for short in ARCHETYPES}
    assert not {last(short) for short in SYNTHETIC} & app_last


def test_reused_app_classes_are_ported_and_new_ones_are_app_style() -> None:
    """Every ability id is a ported app class or a new ``AppStyle`` class."""

    for short, archetype in SYNTHETIC.items():
        for key in ("WormAbilityIDs", "CustomAbilityIDs"):
            ids = archetype.attributes.get(key, ())
            assert isinstance(ids, tuple)
            for name in ids:
                assert isinstance(name, str)
                if name.startswith((BL, SC)):
                    continue
                assert name in PORTS, (short, name)


# ---------------------------------------------------------------------------
# Value rules fitted on the app's data (bloodlines-cards.md §1)
# ---------------------------------------------------------------------------


def test_imperium_offsets_are_the_plan_table() -> None:
    """§1.1 / plan §11.3: median AcquireValue - PersuasionCost per cost."""

    assert len(synth()._main_imperium()) == 151
    assert synth().imperium_offsets() == {
        1: 0.0,
        2: -0.1,
        3: 0.0,
        4: -0.2,
        5: -0.2,
        6: -0.2,
        7: -0.2,
        8: 0.0,
    }


def test_imperium_arc_mods_are_the_modes() -> None:
    """§1.2: LateMod 0.8 for cost 1 only; no EarlyMod."""

    late = synth().imperium_arc_mods("LateMod")
    assert late == {1: 0.8, **{cost: None for cost in range(2, 9)}}
    assert set(synth().imperium_arc_mods("EarlyMod").values()) == {None}


@pytest.mark.parametrize(
    ("kinds", "value"),
    [
        ((), 0),
        (("R",), 0),
        (("D",), 1),
        (("D", "D"), 2),
        (("D", "R"), 1),
        (("Dc", "S", "R"), 2),
        (("T",), 2),
        (("I",), 2),
        (("F", "R"), 2),
        (("D", "F"), 2),
        (("A",), 0),
        (("X",), 0),
        (("C",), 0),
    ],
)
def test_imperium_defer_value_rule(kinds: tuple[str, ...], value: int) -> None:
    """§1.3: ``min(2, max w)``; w(D) = draws, Dc/T/I/F = 2, others 0."""

    assert synth().imperium_defer_value(kinds) == value


def test_intrigue_rating_modes() -> None:
    """§1.7: Plot 2, Combat 2, Plot+Endgame 3; Plot+Combat (an Uprising
    tie) and Combat+Endgame (no Uprising card) take the all-sets mode."""

    rating = synth().intrigue_rating
    assert rating(frozenset({"Plot"})) == 2
    assert rating(frozenset({"Combat"})) == 2
    assert rating(frozenset({"Plot", "Endgame"})) == 3
    assert rating(frozenset({"Plot", "Combat"})) == 3
    assert rating(frozenset({"Combat", "Endgame"})) == 2


def test_tech_tiles_cost_twice_their_spice() -> None:
    """Plan §11.3: every app tile is worth exactly 2 x SpiceCost."""

    assert synth().tech_value_ratio() == 2.0


# ---------------------------------------------------------------------------
# bloodlines-cards.md §3.0: Imperium attributes
# ---------------------------------------------------------------------------

# card_id: (short, cost, copies, factions, icons, Persuasion, Strength,
#           AcquireValue, LateMod, DeferValue, AcquireEffectList, Tags, extra)
IMPERIUM_TABLE: dict[str, tuple[object, ...]] = {
    "ruthless_leadership": ("RuthlessLeadership", 4, 1, ("Emperor",), ("Circle", "Triangle"), 1, 1, 3.8, None, 2, None, ("Combat",), {}),
    "arrakis_observer": ("ArrakisObserver", 3, 1, ("SpacingGuild",), ("Circle", "Triangle"), 1, None, 3.0, None, 2, None, ("Spy", "WantSpy", "RecallSpy", "WantSG"), {}),
    "bombast": ("Bombast", 1, 1, ("Emperor",), ("Pentagon",), 1, None, 1.0, 0.8, None, None, None, {}),
    "choam_demands": ("CHOAMDemands", 6, 1, ("SpacingGuild",), ("Pentagon", "Circle", "Triangle"), None, None, 5.8, None, None, None, ("WantContract4",), {}),
    "command_center": ("CommandCenter", 3, 1, ("Emperor",), ("Emperor", "Circle"), 1, None, 3.0, None, None, None, ("EmperorInfluence",), {}),
    "corrupt_bureaucrat": ("CorruptBureaucrat", 4, 1, ("SpacingGuild",), ("SpacingGuild", "Pentagon", "Spy"), 2, None, 3.8, None, None, None, ("WantSpy", "WantRecall", "IncentiveDiscard", "Contract"), {}),
    "delivery_logistics": ("DeliveryLogistics", 2, 2, ("SpacingGuild",), None, None, None, 1.9, None, None, None, ("Contract", "WantContractX"), {"ConditionalIconList": ("Emperor", "SpacingGuild", "BeneGesserit", "Pentagon", "Circle", "Triangle")}),
    "disruption_tactics": ("DisruptionTactics", 2, 1, ("Fremen",), ("Fremen", "Triangle"), 1, None, 1.9, None, None, None, ("Combat",), {}),
    "eliminate_allies": ("EliminateAllies", 2, 1, ("Emperor",), ("Spy",), 1, 1, 1.9, None, 2, None, ("WantSpy",), {}),
    "elite_forces": ("EliteForces", 3, 1, ("Emperor", "SpacingGuild"), ("Emperor", "SpacingGuild"), 1, 1, 3.0, None, 2, None, ("WantE", "Combat"), {}),
    "engineered_miracle": ("EngineeredMiracle", 3, 1, ("BeneGesserit",), ("Fremen", "Triangle"), 1, None, 3.0, None, 2, None, ("DiscardEnabler",), {}),
    "fremen_war_name": ("FremenWarName", 4, 1, ("Fremen",), ("Fremen", "Triangle"), 2, None, 3.8, None, 1, None, ("FremenBond", "ConditionalStrength"), {}),
    "holy_war": ("HolyWar", 5, 1, ("Fremen",), ("Emperor", "SpacingGuild", "BeneGesserit", "Pentagon"), 1, None, 4.8, None, None, None, ("FremenBond", "Combat"), {"Troops": 1}),
    "i_believe": ("IBelieve", 3, 1, ("Fremen",), ("Fremen", "Circle"), 1, None, 3.0, None, 2, None, ("DiscardEnabler",), {}),
    "imperial_throneship": ("ImperialThroneship", 7, 1, ("Emperor",), ("Emperor", "SpacingGuild", "BeneGesserit", "Pentagon", "Circle", "Triangle"), 2, None, 6.8, None, 2, ("RankE",), None, {}),
    "intelligence_training": ("IntelligenceTraining", 3, 2, ("Emperor",), ("Pentagon", "Circle"), 1, 1, 3.0, None, None, ("PlaceSpy",), ("Spy",), {}),
    "ixian_ambassador": ("IxianAmbassador", 4, 2, None, ("Pentagon",), 1, None, 3.8, None, None, None, None, {"AgentSpice": 1}),
    "litany_against_fear": ("LitanyAgainstFear", 3, 1, ("BeneGesserit",), None, 2, None, 3.0, None, None, None, None, {}),
    "mercantile_affairs": ("MercantileAffairs", 5, 1, ("BeneGesserit",), ("BeneGesserit", "Circle", "Triangle", "Spy"), 2, None, 4.8, None, 2, ("Contract",), ("WantSpy", "WantContractX"), {}),
    "pointing_the_way": ("PointingtheWay", 6, 1, ("Fremen",), ("Fremen", "Circle", "Triangle"), 1, 2, 5.8, None, 2, None, ("WantHooks",), {}),
    "possible_futures": ("PossibleFutures", 8, 1, ("BeneGesserit", "Fremen"), ("Pentagon", "Circle", "Triangle"), 2, None, 8.0, None, 2, ("Water",), ("WantBG",), {"Water": 1}),
    "quash_rebellion": ("QuashRebellion", 5, 2, ("Emperor",), ("Emperor", "SpacingGuild", "Pentagon"), None, 2, 4.8, None, None, None, None, {"AgentSolari": 2}),
    "sandwalk": ("Sandwalk", 1, 2, ("Fremen",), ("Triangle",), 1, 1, 1.0, 0.8, 1, None, ("FremenBond",), {}),
    "sardaukar_standard": ("SardaukarStandard", 4, 1, ("Emperor",), ("Emperor", "Circle"), 2, None, 3.8, None, None, None, None, {"Troops": 1}),
    "shrouded_counsel": ("ShroudedCounsel", 4, 1, ("BeneGesserit",), ("Spy",), 1, None, 3.8, None, 2, None, ("WantSpy",), {}),
    "southern_faith": ("SouthernFaith", 5, 1, ("BeneGesserit", "Fremen"), ("Fremen", "Circle"), 1, 2, 4.8, None, 2, None, ("WantBG",), {}),
    "urgent_shigawire": ("UrgentShigawire", 2, 2, ("BeneGesserit",), ("BeneGesserit", "Circle"), 1, None, 1.9, None, None, None, ("WantBG",), {}),
}  # fmt: skip
#: The reveal-slot class and the tail of each card (cards.md §3.1-§3.27).
IMPERIUM_ABILITIES: dict[str, tuple[str, ...]] = {
    "ruthless_leadership": ("RevealAbility", "RuthlessLeadershipTrashAbility", "RuthlessLeadershipTrashAbility", "RuthlessLeadershipCommandAbility"),
    "arrakis_observer": ("RevealAbility", "ArrakisObserverAgentAbility", "ArrakisObserverRevealAbility"),
    "bombast": ("RevealAbility", "BombastCommandAbility"),
    "choam_demands": ("RevealAbility", "CHOAMDemandsAgentAbility", "CHOAMDemandsRevealAbility"),
    "command_center": ("RevealAbility", "CommandCenterAgentAbility", "CommandCenterRevealAbility"),
    "corrupt_bureaucrat": ("RevealAbility", "CorruptBureaucratAgentAbility", "CorruptBureaucratDiscardAbility"),
    "delivery_logistics": ("RevealAbility", "DeliveryLogisticsRevealAbility"),
    "disruption_tactics": ("RevealAbility", "DisruptionTacticsAgentAbility", "DisruptionTacticsRevealAbility"),
    "eliminate_allies": ("RevealAbility", "TrashAgentAbility", "EliminateAlliesTrashAbility"),
    "elite_forces": ("RevealAbility", "EliteForcesAgentAbility"),
    "engineered_miracle": ("RevealAbility", "EngineeredMiracleAgentAbility", "EngineeredMiracleCommandAbility"),
    "fremen_war_name": ("RevealAbility", "FremenWarNameTroopAbility", "FremenWarNameDrawAbility", "FremenWarNameBondAbility"),
    "holy_war": ("RevealAbility", "HolyWarAgentAbility", "HolyWarBondAbility"),
    "i_believe": ("RevealAbility", "IBelieveAgentAbility", "IBelieveCommandAbility"),
    "imperial_throneship": ("ImperialThroneshipRevealAbility", "AgentGainIntrigueAbility", "ImperialThroneshipTriggeredAbility"),
    "intelligence_training": ("RevealAbility", "IntelligenceTrainingCommandAbility", "AcquirePlaceSpyBonusAbility"),
    "ixian_ambassador": ("RevealAbility", "IxianAmbassadorRevealAbility"),
    "litany_against_fear": ("RevealAbility", "LitanyTurnStartAbility"),
    "mercantile_affairs": ("RevealAbility", "MercantileAffairsAgentAbility", "AcquireContractBonusAbility"),
    "pointing_the_way": ("RevealAbility", "PointingTheWayAgentAbility", "PointingTheWayCommandAbility"),
    "possible_futures": ("RevealAbility", "PossibleFuturesAgentAbility"),
    "quash_rebellion": ("QuashRebellionRevealAbility", "QuashRebellionTriggeredAbility"),
    "sandwalk": ("SandwalkRevealAbility", "SandwalkDrawAbility", "SandwalkBondAbility"),
    "sardaukar_standard": ("RevealAbility", "SardaukarStandardTrashAbility"),
    "shrouded_counsel": ("RevealAbility", "AgentGainIntrigueAbility", "ShroudedCounselCommandAbility"),
    "southern_faith": ("RevealAbility", "SouthernFaithAgentAbility", "SouthernFaithCommandAbility"),
    "urgent_shigawire": ("RevealAbility", "UrgentShigawireAgentAbility"),
}  # fmt: skip


@pytest.mark.parametrize("card_id", sorted(IMPERIUM_TABLE))
def test_imperium_table(card_id: str) -> None:
    (
        name,
        cost,
        copies,
        factions,
        icons,
        persuasion,
        strength,
        acquire_value,
        late_mod,
        defer_value,
        acquire_effects,
        tags,
        extra,
    ) = IMPERIUM_TABLE[card_id]
    short = "ImperiumArchetypes.AppStyle." + str(name)
    assert CARD_ARCHETYPES[card_id] == short
    a = attrs(short)
    assert a["EntityType"] == "Imperium"
    expected_type = "Promo" if card_id == "ruthless_leadership" else "Main"
    assert a["ImperiumType"] == expected_type  # §9 D3
    assert a["PersuasionCost"] == cost
    assert a["CardCount"] == copies
    assert a.get("FactionList") == factions
    assert a.get("IconList") == icons
    assert a.get("Persuasion") == persuasion
    assert a.get("Strength") == strength
    assert a["AcquireValue"] == acquire_value
    assert a.get("LateMod") == late_mod
    assert "EarlyMod" not in a and "TrashValue" not in a  # §1.2
    assert a.get("DeferValue") == defer_value
    assert a.get("AcquireEffectList") == acquire_effects
    assert a.get("Tags") == tags
    assert isinstance(extra, dict)
    for key, value in extra.items():
        assert a[key] == value
    assert abilities(short) == (
        "AgentAbility",
        IMPERIUM_ABILITIES[card_id][0],
        "AcquireAbility",
        *IMPERIUM_ABILITIES[card_id][1:],
    )


def test_imperium_printed_numbers_agree_with_the_content() -> None:
    for entry in IMPERIUM_CARDS:
        if not entry.bloodlines_only:
            continue
        archetype = catalog.archetype(CARD_ARCHETYPES[entry.card.card_id])
        a = archetype.attributes
        assert archetype.title == entry.card.name
        assert a["PersuasionCost"] == entry.acquisition_cost
        assert a["CardCount"] == entry.copies
        icons = {synth().ICON_NAMES[i] for i in entry.agent_icons}
        assert set(archetype_list(archetype, "IconList")) == icons
        assert a.get("Strength", 0) == entry.reveal_strength
        set_list = a["SetList"]
        assert isinstance(set_list, tuple)
        assert ("CHOAMModule" in set_list) == entry.choam_only
        assert ("TechModule" in set_list) == entry.tech_only


# ---------------------------------------------------------------------------
# bloodlines-cards.md §4.0 and §5: Intrigue and Twisted Intrigue
# ---------------------------------------------------------------------------

# card_id: (short, types, Strength, CombatValue, DeferValue, Rating, Tags)
INTRIGUE_TABLE: dict[str, tuple[object, ...]] = {
    "adaptive_tactics": ("AdaptiveTactics", ("Plot",), None, None, None, 2, None),
    "battlefield_research": ("BattlefieldResearch", ("Combat", "Endgame"), None, None, 2, 2, ("BuyTech", "ConditionalEndgameVP")),
    "coercive_negotiation": ("CoerciveNegotiation", ("Plot",), None, None, None, 2, ("Contract",)),
    "desert_support": ("DesertSupport", ("Combat",), 5, 5.0, None, 2, None),
    "emperor_s_invitation": ("EmperorsInvitation", ("Plot",), None, None, 1, 2, None),
    "false_orders": ("FalseOrders", ("Plot",), None, None, None, 2, ("Spy",)),
    "grasp_arrakis": ("GraspArrakis", ("Combat", "Endgame"), 3, 3.0, None, 2, ("ConditionalEndgameVP",)),
    "honor_guard": ("HonorGuard", ("Plot",), None, None, None, 2, None),
    "insider_information": ("InsiderInformation", ("Plot",), None, None, 2, 2, ("WantSpy", "RecallSpy")),
    "rapid_engineering": ("RapidEngineering", ("Plot",), None, None, 2, 2, ("BuyTech", "DiscardEnabler")),
    "return_the_favor": ("ReturntheFavor", ("Combat",), 5, 1.0, None, 2, ("EmperorInfluence", "SpacingGuildInfluence", "BeneGesseritInfluence", "FremenInfluence")),
    "ripples_in_the_sand": ("RipplesintheSand", ("Combat",), 3, 3.0, 2, 2, ("WantHooks",)),
    "sacred_pools": ("SacredPools", ("Plot", "Endgame"), None, None, None, 3, ("DiscardEnabler", "ConditionalEndgameVP")),
    "seize_production": ("SeizeProduction", ("Plot",), None, None, None, 2, None),
    "sleeper_unit": ("SleeperUnit", ("Plot",), None, None, None, 2, ("Spy", "WantSpy", "RecallSpy")),
    "tenuous_bond": ("TenuousBond", ("Plot", "Combat"), 4, None, 2, 3, None),
    "the_strong_survive": ("TheStrongSurvive", ("Combat",), 3, 3.0, 2, 2, None),
    "withdrawal_agreement": ("WithdrawalAgreement", ("Combat",), None, None, 1, 2, None),
    # §5: Twisted (no Tags)
    "twisted_ambitious": ("TwistedAmbitious", ("Plot",), None, None, 1, 2, None),
    "twisted_calculating": ("TwistedCalculating", ("Plot",), None, None, None, 2, None),
    "twisted_controlled": ("TwistedControlled", ("Plot", "Combat"), 1, None, 1, 3, None),
    "twisted_devious": ("TwistedDevious", ("Plot",), None, None, 2, 2, None),
    "twisted_discerning": ("TwistedDiscerning", ("Plot",), None, None, 1, 2, None),
    "twisted_insidious": ("TwistedInsidious", ("Plot",), None, None, None, 2, None),
    "twisted_resourceful": ("TwistedResourceful", ("Plot",), None, None, None, 2, None),
    "twisted_sadistic": ("TwistedSadistic", ("Plot",), None, None, 1, 2, None),
    "twisted_shrewd": ("TwistedShrewd", ("Combat",), None, None, None, 2, None),
    "twisted_sinister": ("TwistedSinister", ("Combat",), None, None, 2, 2, None),
    "twisted_unnatural": ("TwistedUnnatural", ("Plot",), None, None, 2, 2, None),
    "twisted_withdrawn": ("TwistedWithdrawn", ("Plot",), None, None, None, 2, None),
}  # fmt: skip
#: §4.1 / §5 ability classes (one per printed half; Controlled has two).
INTRIGUE_ABILITIES: dict[str, tuple[str, ...]] = {
    "battlefield_research": ("BattlefieldResearchCombatAbility", "BattlefieldResearchEndgameAbility"),
    "grasp_arrakis": ("GraspArrakisCombatAbility", "GraspArrakisEndgameAbility"),
    "sacred_pools": ("SacredPoolsPlotAbility", "SacredPoolsEndgameAbility"),
    "tenuous_bond": ("TenuousBondPlotAbility", "TenuousBondCombatAbility"),
    "return_the_favor": ("ReturnTheFavorAbility",),
    "ripples_in_the_sand": ("RipplesInTheSandAbility",),
    "twisted_controlled": ("TwistedControlledPlotAbility", "TwistedControlledCombatAbility"),
}  # fmt: skip


@pytest.mark.parametrize("card_id", sorted(INTRIGUE_TABLE))
def test_intrigue_table(card_id: str) -> None:
    name, types, strength, combat_value, defer_value, rating, tags = INTRIGUE_TABLE[
        card_id
    ]
    short = "IntrigueArchetypes.AppStyle." + str(name)
    assert INTRIGUE_ARCHETYPES[card_id] == short
    a = attrs(short)
    assert a["EntityType"] == "Intrigue"
    assert a["CardCount"] == 1
    assert a["IntrigueTypeList"] == types
    assert a.get("Strength") == strength
    assert a.get("CombatValue") == combat_value
    assert a.get("DeferValue") == defer_value
    assert a["Rating"] == rating
    assert a.get("Tags") == tags
    default = (str(name) + "Ability",)
    assert abilities(short) == INTRIGUE_ABILITIES.get(card_id, default)


def test_intrigue_printed_data_agree_with_the_content() -> None:
    timing_names = synth().TIMING_NAMES
    for entry in INTRIGUE_CARDS:
        if not entry.bloodlines_only or entry.navigation:
            continue
        archetype = catalog.archetype(INTRIGUE_ARCHETYPES[entry.card.card_id])
        assert archetype.title == entry.card.name
        assert archetype.attributes["CardCount"] == entry.copies
        types = archetype.attributes["IntrigueTypeList"]
        assert isinstance(types, tuple)
        assert set(types) == {timing_names[t] for t in entry.timings}


# ---------------------------------------------------------------------------
# bloodlines-cards.md §6 and §7: Conflict cards and contract tokens
# ---------------------------------------------------------------------------


def test_conflict_cards_and_reward_rows() -> None:
    wild = "ConflictArchetypes.AppStyle.SkirmishWild"
    storms = "ConflictArchetypes.AppStyle.StormsintheSouth"
    assert CONFLICT_ARCHETYPES["skirmish_wild"] == (wild, wild)
    assert CONFLICT_ARCHETYPES["storms_in_the_south"] == (storms, storms)
    for short, level, tags in ((wild, 1, ("BattleIcon",)), (storms, 2, ("BattleIcon", "Spy"))):  # fmt: skip
        a = attrs(short)
        assert a["ConflictLevel"] == level
        assert a["BattleIcon"] == "Wildcard"
        assert a["Tags"] == tags
        assert a["SetList"] == ("Bloodlines",)  # D28: out of the RCV pool
        assert abilities(short) == tuple(
            f"GenericConflict{p}Ability" for p in ("First", "Second", "Third")
        )
    rewards = {
        wild: ({"CustomAbilityIDs": ("TrashConflictCustomAbility",)}, {"Water": 1, "Solari": 1}, {"Solari": 2}),
        storms: ({"Spice": 2, "CustomAbilityIDs": ("PlaceSpyCustomAbility",)}, {"IntrigueCard": 2, "Solari": 2}, {"IntrigueCard": 1, "Solari": 2}),
    }  # fmt: skip
    for conflict_id, short in (
        ("skirmish_wild", wild),
        ("storms_in_the_south", storms),
    ):
        for choam in (False, True):
            entities = conflict_reward_entities(conflict_id, choam)
            assert [e.short for e in entities] == [
                short + p for p in ("First", "Second", "Third")
            ]
            for entity, expected in zip(entities, rewards[short], strict=True):
                assert entity.archetype is not None
                got = {
                    k: v
                    for k, v in entity.archetype.attributes.items()
                    if k not in ("ArchID", "EntityType", "SetList")
                }
                if "CustomAbilityIDs" in got:
                    got["CustomAbilityIDs"] = tuple(
                        last(str(i)) for i in entity.list_attr("CustomAbilityIDs")
                    )
                assert got == expected
                assert entity.attr("EntityType") == "ConflictReward"


def test_bloodlines_conflicts_stay_out_of_the_uprising_pool() -> None:
    """§9 D28: ``GetUprisingConflicts`` keeps ``SetList`` ∋ Uprising."""

    for short in ("SkirmishWild", "StormsintheSouth"):
        set_list = attrs("ConflictArchetypes.AppStyle." + short)["SetList"]
        assert isinstance(set_list, tuple)
        assert "Uprising" not in set_list


# token: (short, ContractType, ReferencedArchetypeIDs, rewards, DV, Tags, abilities)
CONTRACT_TABLE: dict[str, tuple[object, ...]] = {
    "deliver_supplies": ("BloodlinesDeliverSupplies", "Space", ("DeliverSupplies",), {"Solari": 1}, None, ("Spy",), ("PlaceSpyContractAbility", "ActivateContractTriggeredAbility")),
    "earn_any_alliance": ("BloodlinesEarnAnyAlliance", "Alliance", None, {"Solari": 2, "Troops": 2}, None, None, ("EarnAllianceContractAbility",)),
    "harvest_3": ("BloodlinesHarvest3", "Harvest", ("ImperialBasin", "HaggaBasinUP", "DeepDesert", "TueksSietch"), {"Solari": 2, "SpiceCost": 3}, None, ("Spy",), ("Harvest3SpyContractAbility", "ActivateContractTriggeredAbility")),
    "harvest_4": ("BloodlinesHarvest4", "Harvest", ("ImperialBasin", "HaggaBasinUP", "DeepDesert", "TueksSietch"), {"Solari": 3, "SpiceCost": 4}, None, ("Spy",), ("Harvest4SpyContractAbility", "ActivateContractTriggeredAbility")),
    "high_council": ("BloodlinesHighCouncil", "Space", ("HighCouncilUP",), {}, None, ("RecallAgent",), ("RecallAgentContractAbility", "ActivateContractTriggeredAbility")),
    "immediate": ("BloodlinesImmediate", "Immediate", None, {}, 1, None, ("ImmediateTrashIntrigueContractAbility",)),
    "secrets": ("BloodlinesSecrets", "Space", ("Secrets",), {"Solari": 2}, 1, None, ("Draw1ContractAbility", "ActivateContractTriggeredAbility")),
    "spice_refinery": ("BloodlinesSpiceRefinery", "Space", ("SpiceRefinery",), {"Troops": 2}, None, None, ("ContractAbility", "ActivateContractTriggeredAbility")),
}  # fmt: skip


@pytest.mark.parametrize("token", sorted(CONTRACT_TABLE))
def test_contract_token_table(token: str) -> None:
    name, contract_type, refs, rewards, defer_value, tags, ability_names = (
        CONTRACT_TABLE[token]
    )
    short = "ContractArchetypes.AppStyle." + str(name)
    assert CONTRACT_ARCHETYPES["bloodlines_" + token] == short
    entity = contract_entity("contract:bloodlines_" + token)
    assert entity.short == short
    a = attrs(short)
    assert a["ContractType"] == contract_type
    got_refs = archetype_list(arch(short), "ReferencedArchetypeIDs")
    assert (tuple(last(r) for r in got_refs) or None) == refs
    assert isinstance(rewards, dict)
    for key in ("Solari", "Troops", "Water", "SpiceCost"):
        assert a.get(key) == rewards.get(key)
    assert a.get("DeferValue") == defer_value
    assert a.get("Tags") == tags
    assert abilities(short) == ability_names


def test_contract_reference_spaces_are_the_catalogs() -> None:
    for target, short in synth().CONTRACT_TARGET_SPACES.items():
        assert space_archetype(target, Board(True)) == short
    for contract in BLOODLINES_CONTRACTS:
        a = attrs(CONTRACT_ARCHETYPES[contract.card.card_id])
        assert a.get("Solari", 0) == contract.reward.solari
        assert a.get("Troops", 0) == contract.reward.troops
        assert a.get("DeferValue", 0) == contract.reward.personal_cards  # §1.10


# ---------------------------------------------------------------------------
# bloodlines-systems.md §3.2: Tech tiles
# ---------------------------------------------------------------------------

# tech_id: (short, SpiceCost, AcquireValue, EarlyMod, LateMod, AcquireEffectList,
#           WormAbilityIDs)
TECH_TABLE: dict[str, tuple[object, ...]] = {
    "advanced_data_analysis": ("AdvancedDataAnalysis", 3, 6.0, None, None, None, ("AdvancedDataAnalysisAbility",)),
    "choam_transports": ("CHOAMTransports", 6, 12.0, 1.2, None, ("Contract",), ("CHOAMTransportsAbility", "AcquireEffectsBonusAbility")),
    "delivery_bay": ("DeliveryBay", 3, 6.0, 1.5, 0.0, ("Imperium",), ("DrawImperiumAcquiredAbility", "DeliveryBayAbility")),
    "forbidden_weapons": ("ForbiddenWeapons", 2, 4.0, None, None, ("Troop", "ShieldWall"), ("ForbiddenWeaponsAbility",)),
    "gene_locked_vault": ("GeneLockedVault", 2, 4.0, None, None, ("IntrigueOrImperium",), ("GeneLockedVaultAcquiredAbility", "GeneLockedVaultAbility")),
    "glowglobes": ("Glowglobes", 2, 4.0, None, None, ("AnyRank",), ("MemocordersAcquiredAbility", "GlowglobesAbility")),
    "navigation_chamber": ("NavigationChamber", 5, 10.0, None, None, ("AnyRank",), ("MemocordersAcquiredAbility", "NavigationChamberAbility")),
    "ornithopter_fleet": ("OrnithopterFleet", 4, 8.0, None, None, ("Troop", "Troop"), ("OrnithopterFleetAbility",)),
    "panopticon": ("Panopticon", 5, 10.0, None, None, None, ("PlaceSpyRevealAbility", "PanopticonAbility")),
    "planetary_array": ("PlanetaryArray", 2, 4.0, 1.5, 0.5, ("Trash",), ("DisposalFacilityAcquiredAbility", "PlanetaryArrayAbility", "AcquireEffectsBonusAbility")),
    "plasteel_blades": ("PlasteelBlades", 3, 6.0, None, None, ("Solari",) * 4, ("PlasteelBladesAbility",)),
    "rapid_dropships": ("RapidDropships", 4, 8.0, 1.1, 0.75, ("Troop", "Troop"), ("RapidDropshipsAbility",)),
    "sardaukar_high_command": ("SardaukarHighCommand", 7, 14.0, None, None, ("VP",), ("SardaukarHighCommandAbility",)),
    "self_destroying_messages": ("SelfDestroyingMessages", 4, 8.0, 1.5, None, ("Intrigue", "Intrigue"), ("AcquireEffectsBonusAbility", "MinimicFilmAbility")),
    "servo_receivers": ("ServoReceivers", 2, 4.0, None, None, ("Signet",), ("ServoReceiversAcquiredAbility", "ServoReceiversAbility")),
    "spy_drones": ("SpyDrones", 5, 10.0, None, None, ("PlaceSpy", "PlaceSpy"), ("SpyDronesAbility", "AcquireEffectsBonusAbility")),
    "suspensor_suits": ("SuspensorSuits", 3, 6.0, None, None, None, ("SuspensorSuitsAbility",)),
    "training_depot": ("TrainingDepot", 1, 2.0, None, None, None, ("TrainingDepotAbility",)),
}  # fmt: skip


@pytest.mark.parametrize("tech_id", sorted(TECH_TABLE))
def test_tech_table(tech_id: str) -> None:
    name, cost, value, early, late, effects, ability_names = TECH_TABLE[tech_id]
    short = "TechTileArchetypes.AppStyle." + str(name)
    assert TECH_ARCHETYPES[tech_id] == short
    entity = tech_entity(tech_id, owner=1)
    assert entity.kind is Kind.TECH and entity.ref == tech_id and entity.owner == 1
    assert is_tech_tile(entity)
    a = attrs(short)
    assert a["SpiceCost"] == cost
    assert a["AcquireValue"] == value
    assert a.get("EarlyMod") == early
    assert a.get("LateMod") == late
    assert a.get("AcquireEffectList") == effects
    assert abilities(short) == ability_names


def test_tech_printed_costs_agree_and_profile_entities_match() -> None:
    for tile in TECH_TILES:
        a = attrs(TECH_ARCHETYPES[tile.tech_id])
        assert a["SpiceCost"] == tile.cost
        set_list = a["SetList"]
        assert isinstance(set_list, tuple)
        assert ("CHOAMModule" in set_list) == tile.choam_only
        archetype = SYNTHETIC[TECH_ARCHETYPES[tile.tech_id]]
        assert pt.tech_tile_entity(archetype, tile.tech_id) == tech_entity(tile.tech_id)
    assert pt.TECH_TILE_KIND is Kind.TECH


@cache
def _round_one() -> GameState:
    return _t.first_decision("turn")


@pytest.mark.parametrize("arc", [0, 1, 2])
def test_worked_values_training_depot(
    arc: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§3.2: Training Depot Mid 2.0, Late 0 (2.0 < 2.2), Early 0 (no
    EarlyMod: "Not early tech")."""

    state = _round_one()
    p = _t.make_profile(state)
    monkeypatch.setattr(p, "game_arc", lambda: arc)
    value = p.tech_tile_acquire_value(tech_entity("training_depot")).sum
    assert value == (0.0, 2.0, 0.0)[arc]


def test_worked_value_sardaukar_high_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """§3.2: 14.0 + ``victory_point_value(1)`` (Flagship's VP acquire
    effect, valued by ``GetAcquireEffectsValue``), Mid arc."""

    state = _round_one()
    p = _t.make_profile(state)
    monkeypatch.setattr(p, "game_arc", lambda: 1)
    value = p.tech_tile_acquire_value(tech_entity("sardaukar_high_command")).sum
    assert value == 14.0 + p.victory_point_value(1)


# ---------------------------------------------------------------------------
# bloodlines-systems.md §2.1, §4, §5, §6
# ---------------------------------------------------------------------------


def test_commander_and_skills() -> None:
    commander = commander_entity()
    assert commander.kind is Kind.COMMANDER
    assert commander.attr("EntityType") == "Commander"
    assert commander.attr("Strength") == 2
    assert commander.attr("SolariCost") == 2
    assert commander.attr("CardCount") == 7
    assert commander.ability_ids == ()
    expected = {
        "canny": ({"Strength": 2}, "CannySkillAbility"),
        "charismatic": ({"Persuasion": 1}, "SkillRevealAbility"),
        "desperate": ({"Strength": 3}, "DesperateSkillAbility"),
        "driven": ({"Spice": 1}, "SkillRevealAbility"),
        "fierce": ({"Strength": 1}, "FierceSkillAbility"),
        "hardy": ({"Troops": 1}, "SkillRevealAbility"),
        "loyal": (
            {
                "Strength": 2,
                "InfluenceRequirements": ({"Amount": 3, "Faction": "Emperor"},),
            },
            "LoyalSkillAbility",
        ),
    }
    assert set(SKILL_ARCHETYPES) == {s.skill_id for s in SKILLS} == set(expected)
    for skill_id, (values, ability) in expected.items():
        a = attrs(SKILL_ARCHETYPES[skill_id])
        assert a["EntityType"] == "Skill" and a["CardCount"] == 2
        got = {
            k: v
            for k, v in a.items()
            if k not in ("ArchID", "EntityType", "CardCount", "SetList")
            and k != "WormAbilityIDs"
        }
        assert got == values
        assert abilities(SKILL_ARCHETYPES[skill_id]) == (ability,)
    for instance in skill_tile_instance_ids():
        entity = skill_entity(instance, owner=0)
        assert entity.kind is Kind.SKILL and entity.ref == instance
        assert entity.short == SKILL_ARCHETYPES[instance.split(":")[1]]


LEADER_TABLE: dict[str, tuple[str, tuple[str, ...]]] = {
    "chani": ("ChaniLeader", ("TacticianAbility", "FedaykinManeuverSignetAbility")),
    "count_hasimir_fenring": ("CountHasimirFenring", ("AssassinAbility", "CorrinoLiaisonSignetAbility")),
    "duncan_idaho": ("DuncanIdahoLeader", ("GinazSwordmasterAbility", "IntoTheFraySignetAbility")),
    "esmar_tuek": ("EsmarTuekLeader", ("TueksSietchLeaderAbility", "SmuggleSpiceSignetAbility")),
    "gaius_helen_mohiam": ("GaiusHelenMohiam", ("ClandestineAbility", "ListenersSignetAbility")),
    "piter_de_vries": ("PiterDeVriesLeader", ("TwistedGeniusAbility", "WarmasterAbility")),
    "steersman_y_rkoon": ("SteersmanYrkoonLeader", ("StrangeFormAbility", "HungryForSpiceAbility", "PlotCourseAbility")),
    "liet_kynes": ("LietKynesLeader", ("ArrakisPlanetologistAbility", "JudgeOfTheChangeSignetAbility")),
    "kota_odax_of_ix": ("KotaOdaxOfIx", ("SecretProjectAbility", "ReverseEngineeringSignetAbility")),
}  # fmt: skip


@pytest.mark.parametrize("choam", [False, True])
def test_every_bloodlines_leader_maps(choam: bool) -> None:
    leaders = leaders_for_choam(choam, bloodlines=True, tech_module=True)
    bloodlines = [leader for leader in leaders if leader.bloodlines_only]
    assert {leader.leader_id for leader in bloodlines} == set(LEADER_TABLE)
    for leader in leaders:
        entity = leader_entity(leader.leader_id)
        assert entity.archetype is not None
    for leader in bloodlines:
        name, ability_names = LEADER_TABLE[leader.leader_id]
        short = "LeaderArchetypes.AppStyle." + name
        assert LEADER_ARCHETYPES[leader.leader_id] == short
        assert leader.alternate_face_id is None
        assert leader_entity(leader.leader_id).short == short
        assert arch(short).title == leader.name
        assert attrs(short)["EntityType"] == "Leader"
        assert abilities(short) == ability_names


def test_navigation_cards() -> None:
    instances = navigation_card_instance_ids()
    assert len(instances) == 10
    for n, instance in enumerate(instances, start=1):
        entity = navigation_entity(instance, owner=2)
        assert entity.kind is Kind.NAVIGATION and entity.ref == instance
        assert entity.short == f"NavigationArchetypes.AppStyle.NavigationCard{n}"
        assert entity.attr("EntityType") == "Navigation"
        assert entity.list_attr("IntrigueTypeList") == ()
        assert entity.ability_ids == (BL + f"NavigationCard{n}Ability",)
    assert set(NAVIGATION_ARCHETYPES) == {i.split(":")[1] for i in instances}
    # Not Intrigue cards (§5).
    assert not set(NAVIGATION_ARCHETYPES) & set(INTRIGUE_ARCHETYPES)


def test_tueks_sietch() -> None:
    space = BOARD_SPACES_BY_ID["tuek_sietch"]
    assert space.required_leader_id == "esmar_tuek"
    assert "tuek_sietch" not in SPACE_ARCHETYPES  # the board's own spaces
    for board in (Board(False), Board(True, bloodlines=True)):
        entity = space_entity("tuek_sietch", board)
        assert entity.short == "SpaceArchetypes.AppStyle.TueksSietch"
        assert entity.attr("AgentIcon") == "Triangle"
        assert entity.attr("CombatSpace") is True
        assert entity.attr("BonusSpice") == 0
        assert entity.attr("PossibleSpice") == 1
        assert entity.list_attr("ObservationPosts") == ()
        assert entity.list_attr("Tags") == ("Harvest",)
        assert tuple(last(i) for i in entity.ability_ids) == (
            "TueksSietchDeferredAbility",
            "DeployUnitsAbility",
            "SpaceAbility",
        )
    assert set(BLOODLINES_SPACE_ARCHETYPES) == {
        s.space_id for s in BOARD_SPACES if s.required_leader_id is not None
    }


# ---------------------------------------------------------------------------
# Every id our Bloodlines content deals maps
# ---------------------------------------------------------------------------

OPTION_SETS = [
    {"bloodlines": True},
    {"bloodlines": True, "tech_module": True},
    {"bloodlines": True, "tech_module": True, "promo_cards": True},
]


@pytest.mark.parametrize("choam", [False, True])
@pytest.mark.parametrize("options", OPTION_SETS, ids=["bl", "bl_tech", "bl_promo"])
def test_every_dealt_bloodlines_id_maps(choam: bool, options: dict[str, bool]) -> None:
    tech = options.get("tech_module", False)
    for instance in imperium_deck_instance_ids(
        choam,
        options.get("promo_cards", False),
        bloodlines=True,
        tech_module=tech,
    ):
        assert card_entity(instance).archetype is not None
    for instance in (
        *intrigue_deck_instance_ids(choam, bloodlines=True, tech_module=tech),
        *twisted_intrigue_instance_ids(),
    ):
        assert intrigue_entity(instance).archetype is not None
    for tier in ConflictTier:
        for conflict in conflicts_by_tier(tier, bloodlines=True):
            assert conflict_entity(conflict.card.card_id, choam).archetype is not None
            assert len(conflict_reward_entities(conflict.card.card_id, choam)) == 3
    if choam:
        for instance in contract_instance_ids(bloodlines=True):
            assert contract_entity(instance).archetype is not None
    if tech:
        for tile in tech_tiles_for(choam):
            assert tech_entity(tile.tech_id).archetype is not None
    board = Board.of(RulesetConfig(choam_module=choam, **options))
    for space in BOARD_SPACES:
        assert space_entity(space.space_id, board).archetype is not None


def test_bloodlines_ids_map_to_synthetic_archetypes() -> None:
    blood_cards = {e.card.card_id for e in IMPERIUM_CARDS if e.bloodlines_only}
    assert {k for k, v in CARD_ARCHETYPES.items() if v in SYNTHETIC} == blood_cards
    blood_intrigue = {
        e.card.card_id for e in INTRIGUE_CARDS if e.bloodlines_only and not e.navigation
    }
    assert {
        k for k, v in INTRIGUE_ARCHETYPES.items() if v in SYNTHETIC
    } == blood_intrigue
    blood_conflicts = {c.card.card_id for c in CONFLICTS if c.bloodlines_only}
    assert {
        k for k, (v, _) in CONFLICT_ARCHETYPES.items() if v in SYNTHETIC
    } == blood_conflicts
    assert {k for k, v in CONTRACT_ARCHETYPES.items() if v in SYNTHETIC} == {
        c.card.card_id for c in BLOODLINES_CONTRACTS
    }
    assert set(TECH_ARCHETYPES) == {t.tech_id for t in TECH_TILES}


# ---------------------------------------------------------------------------
# docs/app-ai/scouts.md §5: Scouts lines
# ---------------------------------------------------------------------------


def _expected_scouts_refs() -> set[str]:
    """The lines scouts.md §5 lists, counted from our content."""

    refs = {f"{s.subcommittee_id}:0" for s in SUBCOMMITTEES}
    joins = {
        "security_detail": 1,
        "choam_escort": 2,
        "prison_planet": 1,
        "fedaykin_assistance": 1,
        "weirding_warfare": 1,
        "send_for_aid": 1,
        "coordinate_with_the_emperor": 1,
        "tleilaxu_offering": 1,
    }
    for mission in MISSIONS:
        refs |= {
            f"{mission.mission_id}:{k}" for k in range(joins.get(mission.mission_id, 0))
        }
    for event in EVENTS:
        n = len(event.options) + len(event.secret_choices)
        n += 1 if event.event_id == "political_equilibrium" else 0
        refs |= {f"{event.event_id}:{k}" for k in range(n)}
    for auction in AUCTIONS:
        if auction.kind is AuctionKind.SEALED:
            refs |= {f"{auction.auction_id}:{k}" for k in range(auction.places)}
    for sale in SALES:
        refs |= {f"{sale.sale_id}:{k}" for k in range(len(sale.options))}
    return refs


def test_every_scouts_line_maps() -> None:
    refs = _expected_scouts_refs()
    assert len(refs) == 85
    assert set(SCOUTS_LINES) == refs
    assert SCOUTS_LINE_ARCHETYPES is SCOUTS_LINES
    for ref in refs:
        item, line = ref.rsplit(":", 1)
        entity = scouts_line_entity(item, int(line))
        assert entity.kind is Kind.SCOUTS and entity.ref == ref
        assert entity.attr("EntityType") == "ScoutsLine"


def test_mission_troop_destinations_follow_the_engine() -> None:
    """The parked-troop table agrees with ``rules/scouts_missions.py``."""

    parked = synth().MISSION_PARKED
    to_conflict = {m.value for m in _TO_CONFLICT}
    assert {k for k, v in parked.items() if v == "conflict"} == to_conflict
    with_troops = {m.mission_id for m in MISSIONS if m.parked_troops}
    assert set(parked) == with_troops


# ref: (attributes other than ArchID/EntityType/WormAbilityIDs, abilities)
SCOUTS_TABLE: dict[str, tuple[dict[str, object], tuple[str, ...]]] = {
    # §5.1 subcommittees
    "appropriations:0": ({"Water": 1}, ("DiscardCostAbility",)),
    "intelligence:0": ({}, ("PlaceSpyCustomAbility",)),
    "readiness:0": ({"Troops": 1}, ()),
    "choam_coordination:0": ({}, ("GainContractCustomAbility",)),
    "growth_project:0": ({"Specimen": 1}, ()),
    "oversight:0": ({"Spice": 1}, ("RecallSpyCostAbility", "TrashCustomAbility")),
    "investigations:0": ({"SolariCost": 1, "IntrigueCard": 1}, ()),
    "forecasting:0": ({"SpiceCost": 1}, ("DrawAbility", "DrawAbility")),
    "choam_management:0": ({"SpiceCost": 1}, ("GainContractCustomAbility",) * 2),
    "analytics:0": ({"SolariCost": 1}, ("GainResearchCustomAbility",)),
    "relations:0": ({"SpiceCost": 2}, ("GainAnyInfluenceAgentAbility",)),
    "contingencies:0": ({}, ("TrashIntrigueCostAbility", "RecallAgentAbility")),
    "leverage:0": ({"IntrigueCard": 1}, ("RecallSpyCostAbility", "RecallSpyCostAbility", "GainAnyInfluenceAgentAbility")),
    "tleilaxu_relations:0": ({"SpiceCost": 3}, ("GainTwoTleilaxuAbility",)),
    # §5.2 missions (the troop count of a troop ability: AbilityTroops)
    "security_detail:0": ({"AbilityTroops": 1}, ("ParkedTroopsToConflictAbility",)),
    "choam_escort:0": ({"Troops": 1}, ()),
    "choam_escort:1": ({"Solari": 1, "Spice": 1}, ()),
    "prison_planet:0": ({"Spice": 2}, ("LoseGarrisonTroopsCostAbility",)),
    "fedaykin_assistance:0": ({"SpiceCost": 1, "AbilityTroops": 2}, ("ParkedTroopsToGarrisonAbility",)),
    "weirding_warfare:0": ({"SolariCost": 2, "AbilityTroops": 2}, ("ParkedTroopsToConflictAbility",)),
    "send_for_aid:0": ({"Water": 1, "AbilityTroops": 1}, ("LoseGarrisonTroopsCostAbility", "ParkedTroopsToConflictAbility")),
    "coordinate_with_the_emperor:0": ({"SpecimenCost": 1, "Solari": 2, "AbilityTroops": 1}, ("ParkedTroopsToGarrisonAbility",)),
    "tleilaxu_offering:0": ({"Specimen": 2}, ()),
    # §5.3 events
    "private_stock:0": ({"Spice": 1}, ()),
    "private_stock:1": ({}, ("DrawAbility",)),
    "market_research:0": ({"Spice": 2}, ("RecallSpyCostAbility",)),
    "smoke_and_mirrors:0": ({}, ("PlaceSpyCustomAbility",)),
    "smoke_and_mirrors:1": ({"SolariCost": 1, "IntrigueCard": 1}, ()),
    "rotating_doors:0": ({"IntrigueCard": 1}, ("TrashIntrigueCostAbility", "DrawAbility")),
    "moment_of_revelation:0": ({"SpiceCost": 2, "ReferencedArchetypeIDs": ("ImperiumArchetypes.Uprising.PreparetheWay",)}, ("AcquireReserveToHandAbility",)),
    "water_discipline:0": ({"WaterCost": 1}, ("TrashCustomAbility", "DrawAbility")),
    "royal_delegation:0": ({"SolariCost": 2, "FactionInfluence": {"Emperor": 1}}, ()),
    "guild_negotiation:0": ({"SpiceCost": 1, "FactionInfluence": {"SpacingGuild": 1}}, ("DiscardCostAbility",)),
    "covert_assistance:0": ({"FactionInfluence": {"BeneGesserit": 1}}, ("RecallSpyCostAbility",)),
    "gift_of_water:0": ({"WaterCost": 1, "FactionInfluence": {"Fremen": 1}}, ()),
    "share_intelligence:0": ({"SolariCost": 1}, ("TrashIntrigueCostAbility", "GainAnyInfluenceAgentAbility")),
    "political_equilibrium:0": ({}, ("LoseHighestInfluenceAbility",)),
    "crackdown:0": ({}, ("RecallSpyCostAbility",)),
    "crackdown:1": ({"FactionInfluence": {"Emperor": -1}}, ()),
    "water_for_spice_smugglers:0": ({"WaterCost": 1}, ()),
    "water_for_spice_smugglers:1": ({"FactionInfluence": {"SpacingGuild": -1}}, ()),
    "bene_gesserit_treachery:0": ({}, ("LoseGarrisonTroopsCostAbility",)),
    "bene_gesserit_treachery:1": ({"FactionInfluence": {"BeneGesserit": -1}}, ()),
    "funeral_rites:0": ({}, ("TrashFromHandCostAbility",)),
    "funeral_rites:1": ({"FactionInfluence": {"Fremen": -1}}, ()),
    "covert_operation:0": ({}, ("PlaceSpyCustomAbility",)),
    "covert_operation:1": ({"Solari": 2}, ()),
    "covert_operation:2": ({"Troops": 3}, ("DiscardCostAbility",)),
    "covert_operation:3": ({}, ("GainLowestInfluenceAbility",)),
    "covert_operation_choam:0": ({}, ("PlaceSpyCustomAbility",)),
    "covert_operation_choam:1": ({}, ("GainContractCustomAbility",)),
    "covert_operation_choam:2": ({"Troops": 3}, ("DiscardCostAbility",)),
    "covert_operation_choam:3": ({}, ("GainLowestInfluenceAbility",)),
    "rebuild_infrastructure:0": ({"SpiceCost": 1}, ("ShieldWallReturnAbility",)),
    "choam_bargain:0": ({}, ("DrawAbility",)),
    "choam_bargain:1": ({}, ("GainContractCustomAbility",)),
    "ingratiate:0": ({"SpecimenCost": 1}, ("GainAnyInfluenceAgentAbility",)),
    "betrayal:0": ({"FactionInfluence": {"BeneGesserit": -1}}, ("GainTleilaxuInfluenceCustomAbility",)),
    "new_innovations:0": ({"SolariCost": 1}, ("GainResearchCustomAbility",)),
    "new_innovations:1": ({"SpiceCost": 1}, ("GainResearchCustomAbility",)),
    "termination_request:0": ({"Specimen": 1}, ("TrashFromHandCostAbility",)),
    "offworld_operation:0": ({"Solari": 2}, ()),
    "offworld_operation:1": ({}, ("HelixSpiceAbility",)),
    "offworld_operation:2": ({}, ("GainTleilaxuInfluenceCustomAbility",)),
    "offworld_operation:3": ({"IntrigueCard": 1}, ()),
    # §5.4 auctions (line = place - 1)
    "highest_bidder_mid:0": ({}, ("DrawAbility",)),
    "highest_bidder_late:0": ({}, ("DrawAbility", "DrawAbility")),
    "highest_bidder_late:1": ({}, ("DrawAbility",)),
    "competitive_study_mid:0": ({"Specimen": 1}, ("GainResearchCustomAbility",)),
    "competitive_study_late:0": ({"Specimen": 1}, ("GainResearchCustomAbility",)),
    "competitive_study_late:1": ({}, ("GainResearchCustomAbility",)),
    "spies_for_hire_mid:0": ({}, ("PlaceSpyCustomAbility",)),
    "spies_for_hire_late:0": ({"IntrigueCard": 1}, ("PlaceSpyCustomAbility",)),
    "spies_for_hire_late:1": ({}, ("PlaceSpyCustomAbility",)),
    "choam_negotiations_mid:0": ({}, ("GainContractCustomAbility",)),
    "choam_negotiations_late:0": ({"IntrigueCard": 1}, ("GainContractCustomAbility",)),
    "choam_negotiations_late:1": ({}, ("GainContractCustomAbility",)),
    # §5.5 sales
    "unravel_the_future:0": ({"SpiceCost": 1}, ("DrawAbility",)),
    "unravel_the_future:1": ({"SpiceCost": 3}, ("DrawAbility", "DrawAbility")),
    "imperium_connections:0": ({"SolariCost": 2}, ("PlaceSpyCustomAbility",)),
    "imperium_connections:1": ({"SolariCost": 2, "Water": 1}, ()),
    "secrets_for_sale:0": ({"SpiceCost": 1, "IntrigueCard": 1}, ()),
    "secrets_for_sale:1": ({"SpiceCost": 3, "IntrigueCard": 2}, ()),
    "shadow_warfare:0": ({"Spice": 1, "AbilityTroops": 1}, ("RecallSpyCostAbility", "RecruitToConflictAbility")),
    "shadow_warfare:1": ({"Spice": 2, "AbilityTroops": 3}, ("RecallSpyCostAbility", "RecallSpyCostAbility", "RecruitToConflictAbility")),
}  # fmt: skip


def test_scouts_table_covers_every_line() -> None:
    assert set(SCOUTS_TABLE) == set(SCOUTS_LINES)


@pytest.mark.parametrize("ref", sorted(SCOUTS_TABLE))
def test_scouts_line_table(ref: str) -> None:
    values, ability_names = SCOUTS_TABLE[ref]
    short = SCOUTS_LINES[ref]
    got = {
        k: v
        for k, v in attrs(short).items()
        if k not in ("ArchID", "EntityType", "WormAbilityIDs")
    }
    assert got == values
    assert abilities(short) == ability_names
    item = ref.rsplit(":", 1)[0]
    prefix = short.split(".")[0]
    assert short == f"{prefix}.AppStyle.Scouts{synth().scouts_pascal(item)}{ref[-1]}"


# ---------------------------------------------------------------------------
# Board overlays and the small follow-ups
# ---------------------------------------------------------------------------


def _all_spaces() -> list[str]:
    return [*SPACE_ARCHETYPES, *BLOODLINES_SPACE_ARCHETYPES]


@pytest.mark.parametrize("immortality", [False, True])
@pytest.mark.parametrize("choam", [False, True])
def test_boards_without_the_options_keep_the_app_objects(
    choam: bool, immortality: bool
) -> None:
    board = Board(choam, immortality)
    for space_id in SPACE_ARCHETYPES:
        entity = space_entity(space_id, board)
        assert entity.archetype is ARCHETYPES[space_archetype(space_id, board)]


def test_board_of_reads_the_options() -> None:
    config = RulesetConfig(
        choam_module=True, bloodlines=True, tech_module=True, arrakeen_scouts=True
    )
    assert Board.of(config) == Board(
        True, False, bloodlines=True, tech_module=True, scouts=True
    )
    assert Board.of(RulesetConfig()) == Board(False)


def test_bloodlines_and_tech_overlays() -> None:
    assert set(COMMANDER_SPACES) == set(COMMANDER_SETUP_SPACE_IDS)
    landsraad = {
        s.space_id for s in BOARD_SPACES if s.agent_icon is AgentIcon.LANDSRAAD
    }
    assert set(TECH_SPACES) == landsraad
    board = Board(True, bloodlines=True, tech_module=True)
    plain = Board(True)
    for space_id in _all_spaces():
        ids = space_entity(space_id, board).ability_ids
        base = space_entity(space_id, plain).ability_ids
        added = ids[len(base) :]
        assert ids[: len(base)] == base
        expected = (
            *((BL + "AcquireCommanderAbility",) * (space_id in COMMANDER_SPACES)),
            *(
                ("worm.canis.abilities.ActivatedAbilities.RiseOfIx.AcquireTechAbility",)
                * (space_id in TECH_SPACES)
            ),
        )
        assert added == expected, space_id


def test_scouts_overlays() -> None:
    board = Board(True, scouts=True)
    plain = Board(True)
    for space_id in _all_spaces():
        ids = space_entity(space_id, board).ability_ids
        base = space_entity(space_id, plain).ability_ids
        assert ids[-1] == SC + "MissionPiecesSpaceAbility"
        if space_id == "high_council":
            assert ids[-2] == SC + "SubcommitteeOfferAbility"
        if space_id == "hagga_basin":
            assert ids[0] == SC + "DesertRidingAbility"
            assert last(base[0]) == "HaggaBasinUprisingDeferredAbility"
            assert ids[1 : len(base)] == base[1:]
        else:
            assert ids[: len(base)] == base


def test_eyes_on_arrakis_overlay() -> None:
    combat_less = {
        s.space_id for s in BOARD_SPACES if s.faction is not None and not s.combat
    }
    assert set(EYES_ON_ARRAKIS_SPACES) == combat_less
    board = Board(True, scouts=True, faction_spaces_combat=True)
    for space_id in EYES_ON_ARRAKIS_SPACES:
        entity = space_entity(space_id, board)
        assert entity.attr("CombatSpace") is True
        assert entity.ability_ids[-1] == (
            "worm.canis.abilities.ActivatedAbilities.DeployUnitsAbility"
        )


def test_app_context_board_reads_the_round_modifier() -> None:
    config = RulesetConfig(choam_module=True, arrakeen_scouts=True)
    state = _t.first_decision("turn", config=config)
    seat = 0
    view = _t.ENGINE.observe(state, seat)
    assert AppContext(state, seat, view).board == Board(True, scouts=True)
    eyes = replace(state, scouts_round_modifier="faction_spaces_are_combat")
    board = AppContext(eyes, seat, view).board
    assert board == Board(True, scouts=True, faction_spaces_combat=True)


def test_new_entity_kinds_and_timing() -> None:
    assert {Kind.TECH, Kind.COMMANDER, Kind.SKILL, Kind.NAVIGATION, Kind.SCOUTS} <= set(
        Kind
    )
    assert int(Timing.ENDGAME) == 4
    assert ChaumurkyAbility.timing is Timing.ENDGAME


def test_catalog_archetype_looks_in_the_app_then_the_synthetic_set() -> None:
    app = "ImperiumArchetypes.Uprising.CapturedMentat"
    assert catalog.archetype(app) is ARCHETYPES[app]
    short = "ImperiumArchetypes.AppStyle.Sandwalk"
    assert catalog.archetype(short) is SYNTHETIC[short]
    with pytest.raises(KeyError):
        catalog.archetype("ImperiumArchetypes.AppStyle.Missing")


# ---------------------------------------------------------------------------
# The lookups outside the catalog that a synthetic short reaches
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("choam", [False, True])
def test_conflict_reward_reads_the_synthetic_reward_rows(choam: bool) -> None:
    """``generic.conflict_reward`` resolves a Bloodlines card's reward rows
    (cards.md §6; a plain ``ARCHETYPES`` lookup raised KeyError in every
    Bloodlines game)."""

    from dune_imperium.agents.app_ai.abilities.generic import conflict_reward

    storms = conflict_entity("storms_in_the_south", choam)
    first = conflict_reward(storms, 1)
    assert first.short == "ConflictArchetypes.AppStyle.StormsintheSouthFirst"
    assert first.archetype is SYNTHETIC[first.short]
    assert first.int_attr("Spice") == 2
    third = conflict_reward(conflict_entity("skirmish_wild", choam), 3)
    assert third.int_attr("Solari") == 2
    # App cards keep the app's own row objects.
    app = conflict_reward(conflict_entity("skirmish_crysknife", choam), 1)
    assert app.short == "ConflictArchetypes.Uprising.SkirmishHFirst"
    assert app.archetype is ARCHETYPES[app.short]


def test_combat_card_archetype_reads_the_synthetic_cards() -> None:
    """``profile.combat._card_archetype`` (hand and hidden-pool strength,
    guild icons) resolves Bloodlines cards: Sandwalk prints 1 sword
    (cards.md §3.0)."""

    from dune_imperium.agents.app_ai.profile import combat

    archetype = combat._card_archetype("sandwalk")
    assert archetype is SYNTHETIC["ImperiumArchetypes.AppStyle.Sandwalk"]
    assert combat._card_strength("sandwalk") == 1
    app = CARD_ARCHETYPES["captured_mentat"]
    assert combat._card_archetype("captured_mentat") is ARCHETYPES[app]


@pytest.mark.parametrize(
    ("conflict_id", "level"), [("skirmish_wild", 1), ("storms_in_the_south", 2)]
)
def test_relative_conflict_value_with_a_bloodlines_conflict_face_up(
    conflict_id: str, level: int
) -> None:
    """Cards.md §6 / D28: a Bloodlines card face up is divided by the
    Uprising cards of its level; it is never in that pool itself."""

    config = RulesetConfig(choam_module=True, bloodlines=True)
    state = _t.first_decision("turn", config=config)
    state = replace(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
        ),
        current_conflict_ids=(conflict_id,),
    )
    p = _t.make_profile(state)
    pool = [c for c in p.uprising_conflicts() if c.attributes["ConflictLevel"] == level]
    assert pool and all(".AppStyle." not in c.short for c in pool)
    value = p.relative_conflict_value().sum
    assert value == value and abs(value) != float("inf")  # finite, not NaN
