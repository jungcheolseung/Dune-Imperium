"""Emit ``agents/app_ai/data/synthetic.py``: the app-style archetypes.

usage: uv run python scripts/dwgr/app_ai_synth.py [--out PATH]

The Steam app has no Bloodlines and no Arrakeen Scouts. app_ai values their
items through synthetic archetypes built the way the app builds its own
(docs/app-ai-plan.md §11.3, §11.7): the app's attribute names, the printed
numbers copied from our content definitions (``dune_imperium.content``), and
the values the app authors by hand computed by the rules the specs fitted on
the app's own data (``agents/app_ai/data/archetypes.py``):

- docs/app-ai/bloodlines-cards.md: Imperium cards (§1.1-§1.4, §3), Intrigue
  and Twisted Intrigue cards (§1.5-§1.8, §4, §5), the two Conflict cards
  (§1.11, §6) and the eight contract tokens (§1.10, §7);
- docs/app-ai/bloodlines-systems.md: the Sardaukar Commander and the Skills
  (§2.1), the Tech tiles (§3.2 as revised by plan §11.7), the leaders (§4),
  the Navigation cards (§5) and Tuek's Sietch (§6);
- docs/app-ai/scouts.md: one line archetype per Scouts cost -> reward line
  (§1, §2.2, §5).

The hand tables below hold only what the specs state item by item (ability
lists, tag choices, the Agent-box effect kinds the DeferValue rule reads,
short-name exceptions), each with its section. Everything else is read from
the content definitions or computed. The output is deterministic and goes
through ``ruff format``, so re-running reproduces the module byte for byte
(``tests/unit/agents/app_ai/test_app_ai_synthetic.py`` checks it).
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES
from dune_imperium.content.arrakeen_scouts.auctions import AUCTIONS, SALES
from dune_imperium.content.arrakeen_scouts.events import EVENTS
from dune_imperium.content.arrakeen_scouts.missions import MISSIONS
from dune_imperium.content.arrakeen_scouts.subcommittees import SUBCOMMITTEES
from dune_imperium.content.arrakeen_scouts.types import (
    AcquireReserveCardToHand,
    AuctionKind,
    GainLowestInfluence,
    GainSpiceWithHelixBonus,
    LoseFactionInfluence,
    LoseGarrisonTroops,
    LoseHighestInfluence,
    Mission,
    PaySpecimens,
    RecallOtherAgent,
    RecruitToConflict,
    ScoutsOption,
    TroopSource,
)
from dune_imperium.content.bloodlines.sardaukar import (
    COMMANDER_COST_SOLARI,
    COMMANDER_STRENGTH,
    COMMANDER_TOTAL,
    SKILL_COPIES,
    SKILLS,
)
from dune_imperium.content.bloodlines.tech import TECH_TILES, TechTile
from dune_imperium.content.uprising.board import (
    BOARD_SPACES_BY_ID,
    OBSERVATION_POSTS,
    Faction,
)
from dune_imperium.content.uprising.conflicts import CONFLICTS, ConflictReward
from dune_imperium.content.uprising.contracts import (
    BLOODLINES_CONTRACTS,
    ContractConditionKind,
)
from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardUpTo,
    AcquireReserveCard,
    AcquireTech,
    AdvanceTleilaxu,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPersonalCards,
    GainCombatStrength,
    GainInfluence,
    GainResources,
    GenerateSpecimens,
    IntrigueTiming,
    LoseInfluence,
    PayResources,
    PeekTopCard,
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    Research,
    TakeContract,
    TrashIntrigueCard,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS, ImperiumCardEntry
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS, IntrigueCardEntry
from dune_imperium.content.uprising.leaders import LEADERS
from dune_imperium.content.uprising.types import (
    AgentIcon,
    BattleIcon,
    PersonalCardAcquisitionEffect,
    PersonalCardAgentEffect,
    PersonalCardRevealEffect,
)

_OUT_DEFAULT = (
    Path(__file__).resolve().parents[2]
    / "src/dune_imperium/agents/app_ai/data/synthetic.py"
)

# -- app class names ------------------------------------------------------------------

_W = "worm.canis.abilities."
_AA = _W + "ActivatedAbilities."
_UP = _AA + "Uprising."
_IM = _AA + "Immortality."
_CONTRACT = _UP + "ContractAbilities."
_BL = _W + "AppStyle.Bloodlines."
_SC = _W + "AppStyle.Scouts."

AGENT_ABILITY = _W + "PlayAbilities.AgentAbility"
REVEAL_ABILITY = _W + "PlayAbilities.RevealAbility"
ACQUIRE_ABILITY = _AA + "AcquireAbility"
DRAW_ABILITY = _AA + "DrawAbility"
TRASH_AGENT_ABILITY = _AA + "TrashAgentAbility"
AGENT_GAIN_INTRIGUE = _AA + "AgentGainIntrigueAbility"
TRASH_CUSTOM = _AA + "TrashCustomAbility"
GAIN_ANY_INFLUENCE_AGENT = _AA + "GainAnyInfluenceAgentAbility"
DEPLOY_UNITS = _AA + "DeployUnitsAbility"
DISPOSAL_FACILITY_ACQUIRED = _AA + "DisposalFacilityAcquiredAbility"
PLACE_SPY_CUSTOM = _UP + "PlaceSpyCustomAbility"
PLACE_SPY_REVEAL = _UP + "PlaceSpyRevealAbility"
GAIN_CONTRACT_CUSTOM = _UP + "GainContractCustomAbility"
RECALL_AGENT = _UP + "RecallAgentAbility"
WARMASTER = _UP + "WarmasterAbility"
GAIN_RESEARCH_CUSTOM = _IM + "GainResearchCustomAbility"
GAIN_TLEILAXU_CUSTOM = _IM + "GainTleilaxuInfluenceCustomAbility"
SPACE_ABILITY = _W + "SpaceAbilities.SpaceAbility"
MINIMIC_FILM = _W + "TriggeredAbilities.RiseOfIx.MinimicFilmAbility"
DRAW_IMPERIUM_ACQUIRED = _W + "ConflictAbilities.BaseSet.DrawImperiumAcquiredAbility"
MEMOCORDERS_ACQUIRED = _W + "ConflictAbilities.BaseSet.MemocordersAcquiredAbility"
GENERIC_CONFLICT = tuple(
    _W + f"ConflictAbilities.Uprising.GenericConflict{place}Ability"
    for place in ("First", "Second", "Third")
)
TRASH_CONFLICT_CUSTOM = _W + "ConflictAbilities.Uprising.TrashConflictCustomAbility"
ACTIVATE_CONTRACT = _W + "TriggeredAbilities.Uprising.ActivateContractTriggeredAbility"
PLACE_SPY_CONTRACT = _CONTRACT + "PlaceSpyContractAbility"
RECALL_AGENT_CONTRACT = _CONTRACT + "RecallAgentContractAbility"
CONTRACT_ABILITY = _CONTRACT + "ContractAbility"


def _bl(name: str) -> str:
    """``worm.canis.abilities.AppStyle.Bloodlines.<name>`` (the specs' ``AS.``)."""

    return _BL + name


def _sc(name: str) -> str:
    """``worm.canis.abilities.AppStyle.Scouts.<name>`` (scouts.md's ``AS.``)."""

    return _SC + name


# -- our enums -> app names -----------------------------------------------------------

#: ``Factions`` names, in the app's order.
FACTION_NAMES: Mapping[Faction, str] = {
    Faction.EMPEROR: "Emperor",
    Faction.SPACING_GUILD: "SpacingGuild",
    Faction.BENE_GESSERIT: "BeneGesserit",
    Faction.FREMEN: "Fremen",
}
#: ``IconList`` names in the app's order: factions, Pentagon (Landsraad),
#: Circle (City), Triangle (Spice Trade), Spy (bloodlines-cards.md §0).
ICON_NAMES: Mapping[AgentIcon, str] = {
    AgentIcon.EMPEROR: "Emperor",
    AgentIcon.SPACING_GUILD: "SpacingGuild",
    AgentIcon.BENE_GESSERIT: "BeneGesserit",
    AgentIcon.FREMEN: "Fremen",
    AgentIcon.LANDSRAAD: "Pentagon",
    AgentIcon.CITY: "Circle",
    AgentIcon.SPICE_TRADE: "Triangle",
    AgentIcon.SPY: "Spy",
}
BATTLE_ICON_NAMES: Mapping[BattleIcon, str] = {
    BattleIcon.CRYSKNIFE: "Crysknife",
    BattleIcon.DESERT_MOUSE: "DesertMouse",
    BattleIcon.ORNITHOPTER: "Ornithopter",
    BattleIcon.WILD: "Wildcard",
}
TIMING_NAMES: Mapping[IntrigueTiming, str] = {
    IntrigueTiming.PLOT: "Plot",
    IntrigueTiming.COMBAT: "Combat",
    IntrigueTiming.ENDGAME: "Endgame",
}


def _factions(factions: Iterable[Faction]) -> tuple[str, ...]:
    chosen = set(factions)
    return tuple(name for f, name in FACTION_NAMES.items() if f in chosen)


def _icons(icons: Iterable[AgentIcon]) -> tuple[str, ...]:
    chosen = set(icons)
    return tuple(name for icon, name in ICON_NAMES.items() if icon in chosen)


def pascal(name: str) -> str:
    """The app's short-name spelling of a printed name: words joined with
    their printed case, punctuation dropped (``Pointing the Way`` ->
    ``PointingtheWay``, ``Harvest 3+`` -> ``Harvest3``)."""

    return "".join(re.findall(r"[A-Za-z0-9]+", name.replace("'", "")))


def scouts_pascal(item_id: str) -> str:
    """``<PascalItem>`` of a Scouts item id (scouts.md §2.2): each word
    capitalised, ``choam`` as the app spells it (``CHOAM``)."""

    return "".join(
        "CHOAM" if word == "choam" else word.capitalize() for word in item_id.split("_")
    )


# -- records --------------------------------------------------------------------------


@dataclass(slots=True)
class Record:
    """One synthetic archetype before rendering."""

    short: str
    kind: str
    title: str | None
    attributes: dict[str, object] = field(default_factory=dict)
    #: A Scouts line's catalog key, ``<item id>:<line>`` (``SCOUTS_LINES``).
    scouts_ref: str | None = None


def _record(
    short: str, kind: str, title: str | None, attributes: Mapping[str, object]
) -> Record:
    attrs = {"ArchID": short}
    attrs.update(attributes)
    return Record(short, kind, title, dict(attrs))


def _put(attrs: dict[str, object], name: str, value: object) -> None:
    """Set an attribute unless it is empty/zero (absent, as in the app data)."""

    if value in (None, 0, 0.0, ()):
        return
    attrs[name] = value


# =====================================================================================
# Value rules fitted on the app's data (bloodlines-cards.md §1)
# =====================================================================================


def _main_imperium() -> list[Mapping[str, object]]:
    """The app's ``ImperiumType = Main`` cards with a cost and a value (151)."""

    return [
        arch.attributes
        for arch in ARCHETYPES.values()
        if arch.attributes.get("EntityType") == "Imperium"
        and arch.attributes.get("ImperiumType") == "Main"
        and "AcquireValue" in arch.attributes
        and "PersuasionCost" in arch.attributes
    ]


def _cost(attrs: Mapping[str, object]) -> int:
    value = attrs["PersuasionCost"]
    assert isinstance(value, int)
    return value


def _float(attrs: Mapping[str, object], name: str) -> float:
    value = attrs[name]
    assert isinstance(value, int | float)
    return float(value)


def imperium_offsets() -> dict[int, float]:
    """§1.1: per printed cost, the median of ``AcquireValue - PersuasionCost``
    over the app's Main cards, to one decimal (the app's authoring precision)."""

    by_cost: defaultdict[int, list[float]] = defaultdict(list)
    for attrs in _main_imperium():
        by_cost[_cost(attrs)].append(_float(attrs, "AcquireValue") - _cost(attrs))
    return {cost: round(statistics.median(v), 1) for cost, v in sorted(by_cost.items())}


def _modal(values: Counter[object]) -> object:
    """The unique most common value (a tie would leave the rule undefined)."""

    (top, count), *rest = values.most_common()
    assert not rest or rest[0][1] < count, f"tied mode {values}"
    return top


def imperium_arc_mods(name: str) -> dict[int, float | None]:
    """§1.2: per printed cost, the modal ``EarlyMod``/``LateMod`` of the
    app's Main cards (``None``: absent, the app's 1.0)."""

    by_cost: defaultdict[int, Counter[object]] = defaultdict(Counter)
    for attrs in _main_imperium():
        by_cost[_cost(attrs)][attrs.get(name)] += 1
    result: dict[int, float | None] = {}
    for cost, values in sorted(by_cost.items()):
        top = _modal(values)
        assert top is None or isinstance(top, float)
        result[cost] = top
    return result


def imperium_defer_value(kinds: Sequence[str]) -> int:
    """§1.3: ``min(2, max over the Agent box's kinds of w)``; ``w(D)`` is the
    number of draw effects, ``w(Dc) = w(T) = w(I) = w(F) = 2``, other kinds 0.
    0 means the attribute is absent."""

    weights = [kinds.count("D")]
    weights += [2 for kind in kinds if kind in ("Dc", "T", "I", "F")]
    return min(2, max(weights))


def intrigue_rating(types: frozenset[str]) -> int:
    """§1.7: the modal ``Rating`` of the app's Uprising intrigues (CHOAM
    included) with the same ``IntrigueTypeList``; with no such card or a
    tie, the mode over every set."""

    uprising: Counter[object] = Counter()
    every: Counter[object] = Counter()
    for arch in ARCHETYPES.values():
        attrs = arch.attributes
        if attrs.get("EntityType") != "Intrigue":
            continue
        type_list = attrs["IntrigueTypeList"]
        assert isinstance(type_list, tuple)
        if frozenset(type_list) != types:
            continue
        every[attrs["Rating"]] += 1
        set_list = attrs["SetList"]
        assert isinstance(set_list, tuple)
        if {"Uprising", "CHOAMModule"} & set(set_list):
            uprising[attrs["Rating"]] += 1
    ranked = uprising.most_common()
    if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
        rating = ranked[0][0]
    else:
        rating = _modal(every)
    assert isinstance(rating, int)
    return rating


def tech_value_ratio() -> float:
    """Plan §11.3: every app tile has ``AcquireValue = k x SpiceCost``; ``k``."""

    ratios = {
        _float(arch.attributes, "AcquireValue") / _float(arch.attributes, "SpiceCost")
        for arch in ARCHETYPES.values()
        if arch.attributes.get("EntityType") == "TechTile"
    }
    assert len(ratios) == 1, ratios
    return ratios.pop()


# =====================================================================================
# Imperium cards (bloodlines-cards.md §3)
# =====================================================================================


@dataclass(frozen=True, slots=True)
class ImperiumHand:
    """What §3 states per card: the Agent-box kinds of the §1.3 rule (the
    §3.0 "DV (kinds)" column), the tags (§1.4 / §3.0, §9 D27-D27a), the
    reveal-slot class when it is not ``RevealAbility`` (§2.3, §2.6, OPEN-6)
    and the card-specific ability tail (§3.1-§3.27)."""

    kinds: tuple[str, ...]
    tags: tuple[str, ...]
    tail: tuple[str, ...]
    reveal: str | None = None
    extra: Mapping[str, object] = field(default_factory=dict)


IMPERIUM_HAND: Mapping[str, ImperiumHand] = {
    # §3.1
    "ruthless_leadership": ImperiumHand(
        ("T",),
        ("Combat",),
        (
            _bl("RuthlessLeadershipTrashAbility"),
            _bl("RuthlessLeadershipTrashAbility"),
            _bl("RuthlessLeadershipCommandAbility"),
        ),
    ),
    # §3.2
    "arrakis_observer": ImperiumHand(
        ("Dc", "S", "R"),
        ("Spy", "WantSpy", "RecallSpy", "WantSG"),
        (_bl("ArrakisObserverAgentAbility"), _bl("ArrakisObserverRevealAbility")),
    ),
    # §3.3
    "bombast": ImperiumHand((), (), (_bl("BombastCommandAbility"),)),
    # §3.4
    "choam_demands": ImperiumHand(
        ("C",),
        ("WantContract4",),
        (_bl("CHOAMDemandsAgentAbility"), _bl("CHOAMDemandsRevealAbility")),
    ),
    # §3.5
    "command_center": ImperiumHand(
        ("R",),
        ("EmperorInfluence",),
        (_bl("CommandCenterAgentAbility"), _bl("CommandCenterRevealAbility")),
    ),
    # §3.6
    "corrupt_bureaucrat": ImperiumHand(
        ("C",),
        ("WantSpy", "WantRecall", "IncentiveDiscard", "Contract"),
        (_bl("CorruptBureaucratAgentAbility"), _bl("CorruptBureaucratDiscardAbility")),
    ),
    # §3.7: the Agent icons are the incomplete contracts' (no IconList); the
    # contract-space icons as ConditionalIconList (no reader).
    "delivery_logistics": ImperiumHand(
        (),
        ("Contract", "WantContractX"),
        (_bl("DeliveryLogisticsRevealAbility"),),
        extra={
            "ConditionalIconList": (
                "Emperor",
                "SpacingGuild",
                "BeneGesserit",
                "Pentagon",
                "Circle",
                "Triangle",
            )
        },
    ),
    # §3.8
    "disruption_tactics": ImperiumHand(
        ("A",),
        ("Combat",),
        (_bl("DisruptionTacticsAgentAbility"), _bl("DisruptionTacticsRevealAbility")),
    ),
    # §3.9
    "eliminate_allies": ImperiumHand(
        ("T",),
        ("WantSpy",),
        (TRASH_AGENT_ABILITY, _bl("EliminateAlliesTrashAbility")),
    ),
    # §3.10
    "elite_forces": ImperiumHand(
        ("T", "I", "R"), ("WantE", "Combat"), (_bl("EliteForcesAgentAbility"),)
    ),
    # §3.11
    "engineered_miracle": ImperiumHand(
        ("Dc", "R"),
        ("DiscardEnabler",),
        (_bl("EngineeredMiracleAgentAbility"), _bl("EngineeredMiracleCommandAbility")),
    ),
    # §3.12
    "fremen_war_name": ImperiumHand(
        ("D", "R"),
        ("FremenBond", "ConditionalStrength"),
        (
            _bl("FremenWarNameTroopAbility"),
            _bl("FremenWarNameDrawAbility"),
            _bl("FremenWarNameBondAbility"),
        ),
    ),
    # §3.13
    "holy_war": ImperiumHand(
        ("A",),
        ("FremenBond", "Combat"),
        (_bl("HolyWarAgentAbility"), _bl("HolyWarBondAbility")),
    ),
    # §3.14
    "i_believe": ImperiumHand(
        ("Dc", "D"),
        ("DiscardEnabler",),
        (_bl("IBelieveAgentAbility"), _bl("IBelieveCommandAbility")),
    ),
    # §3.15
    "imperial_throneship": ImperiumHand(
        ("I",),
        (),
        (AGENT_GAIN_INTRIGUE, _bl("ImperialThroneshipTriggeredAbility")),
        reveal=_bl("ImperialThroneshipRevealAbility"),
    ),
    # §3.16
    "intelligence_training": ImperiumHand(
        (),
        ("Spy",),
        (
            _bl("IntelligenceTrainingCommandAbility"),
            _bl("AcquirePlaceSpyBonusAbility"),
        ),
    ),
    # §3.17
    "ixian_ambassador": ImperiumHand(
        ("R",), (), (_bl("IxianAmbassadorRevealAbility"),)
    ),
    # §3.18
    "litany_against_fear": ImperiumHand((), (), (_bl("LitanyTurnStartAbility"),)),
    # §3.19
    "mercantile_affairs": ImperiumHand(
        ("I",),
        ("WantSpy", "WantContractX"),
        (_bl("MercantileAffairsAgentAbility"), _bl("AcquireContractBonusAbility")),
    ),
    # §3.20
    "pointing_the_way": ImperiumHand(
        ("I",),
        ("WantHooks",),
        (_bl("PointingTheWayAgentAbility"), _bl("PointingTheWayCommandAbility")),
    ),
    # §3.21 ("F/R": one of the two, F weighs)
    "possible_futures": ImperiumHand(
        ("F", "R"), ("WantBG",), (_bl("PossibleFuturesAgentAbility"),)
    ),
    # §3.22
    "quash_rebellion": ImperiumHand(
        ("R",),
        (),
        (_bl("QuashRebellionTriggeredAbility"),),
        reveal=_bl("QuashRebellionRevealAbility"),
    ),
    # §3.23
    "sandwalk": ImperiumHand(
        ("D",),
        ("FremenBond",),
        (_bl("SandwalkDrawAbility"), _bl("SandwalkBondAbility")),
        reveal=_bl("SandwalkRevealAbility"),
    ),
    # §3.24
    "sardaukar_standard": ImperiumHand((), (), (_bl("SardaukarStandardTrashAbility"),)),
    # §3.25
    "shrouded_counsel": ImperiumHand(
        ("I",),
        ("WantSpy",),
        (AGENT_GAIN_INTRIGUE, _bl("ShroudedCounselCommandAbility")),
    ),
    # §3.26 ("D/F": one of the two, F weighs)
    "southern_faith": ImperiumHand(
        ("D", "F"),
        ("WantBG",),
        (_bl("SouthernFaithAgentAbility"), _bl("SouthernFaithCommandAbility")),
    ),
    # §3.27
    "urgent_shigawire": ImperiumHand(
        ("X",), ("WantBG",), (_bl("UrgentShigawireAgentAbility"),)
    ),
}

#: §3.0: unconditional Agent-box resources (the app's ``AgentSpice`` etc.).
AGENT_BOX_ATTRIBUTES: Mapping[PersonalCardAgentEffect, tuple[str, int]] = {
    PersonalCardAgentEffect.GAIN_ONE_SPICE: ("AgentSpice", 1),
    PersonalCardAgentEffect.GAIN_TWO_SOLARI: ("AgentSolari", 2),
}
#: §3.0 ``AcquireEffectList`` of the acquire boxes (``GetAcquireEffectsValue``
#: values ``RankE`` and ``Water``; ``PlaceSpy``/``Contract`` are priced by the
#: §2.11 bonus classes).
ACQUIRE_EFFECT_NAMES: Mapping[PersonalCardAcquisitionEffect, str] = {
    PersonalCardAcquisitionEffect.GAIN_EMPEROR_INFLUENCE: "RankE",
    PersonalCardAcquisitionEffect.PLACE_SPY: "PlaceSpy",
    PersonalCardAcquisitionEffect.TAKE_CONTRACT: "Contract",
    PersonalCardAcquisitionEffect.GAIN_ONE_WATER: "Water",
}


def _unconditional(effect: PersonalCardRevealEffect) -> bool:
    """A Reveal gain that pays whatever the state (the app's plain
    ``Persuasion``/``Troops``/``Water`` attributes); conditional gains live in
    the card's abilities (§2.1-§2.3, §2.6)."""

    return not (
        effect.requires_command
        or effect.required_faction_bond is not None
        or effect.minimum_garrisoned_units
        or effect.requires_commander_in_conflict
        or effect.requires_high_council
        or effect.requires_swordmaster
        or effect.minimum_spies_placed
        or effect.requires_spying_on_maker_space
        or effect.per_revealed_faction is not None
        or effect.per_in_play_faction is not None
        or effect.grants_combat_icon
    )


def _set_list(*, choam: bool = False, tech: bool = False) -> tuple[str, ...]:
    """``SetList``: ``Bloodlines`` plus the module a module item needs (§0)."""

    return (
        "Bloodlines",
        *(("CHOAMModule",) if choam else ()),
        *(("TechModule",) if tech else ()),
    )


def _bloodlines_imperium() -> list[ImperiumCardEntry]:
    return [entry for entry in IMPERIUM_CARDS if entry.bloodlines_only]


def imperium_records() -> list[Record]:
    offsets = imperium_offsets()
    early = imperium_arc_mods("EarlyMod")
    late = imperium_arc_mods("LateMod")
    records: list[Record] = []
    entries = _bloodlines_imperium()
    assert {e.card.card_id for e in entries} == set(IMPERIUM_HAND)
    for entry in entries:
        hand = IMPERIUM_HAND[entry.card.card_id]
        short = "ImperiumArchetypes.AppStyle." + pascal(entry.card.name)
        cost = entry.acquisition_cost
        plain = [e for e in entry.reveal_effects if _unconditional(e)]
        attrs: dict[str, object] = {
            "EntityType": "Imperium",
            "ImperiumType": "Promo" if entry.promo else "Main",
            "CardCount": entry.copies,
            "SetList": _set_list(choam=entry.choam_only, tech=entry.tech_only),
            "PersuasionCost": cost,
            "AcquireValue": round(cost + offsets[cost], 2),
        }
        _put(attrs, "FactionList", _factions(entry.factions))
        _put(attrs, "IconList", _icons(entry.agent_icons))
        _put(
            attrs,
            "Persuasion",
            entry.reveal_persuasion + sum(e.persuasion for e in plain),
        )
        _put(attrs, "Strength", entry.reveal_strength + sum(e.strength for e in plain))
        _put(attrs, "Troops", sum(e.recruit_troops for e in plain))
        _put(attrs, "Water", sum(e.water for e in plain))
        _put(attrs, "Solari", sum(e.solari for e in plain))
        _put(attrs, "Spice", sum(e.spice for e in plain))
        if entry.agent_effect in AGENT_BOX_ATTRIBUTES:
            name, amount = AGENT_BOX_ATTRIBUTES[entry.agent_effect]
            attrs[name] = amount
        _put(attrs, "EarlyMod", early[cost])
        _put(attrs, "LateMod", late[cost])
        _put(attrs, "DeferValue", imperium_defer_value(hand.kinds))
        if entry.acquisition_effect is not None:
            attrs["AcquireEffectList"] = (
                ACQUIRE_EFFECT_NAMES[entry.acquisition_effect],
            )
        _put(attrs, "Tags", hand.tags)
        attrs.update(hand.extra)
        attrs["WormAbilityIDs"] = (
            AGENT_ABILITY,
            hand.reveal or REVEAL_ABILITY,
            ACQUIRE_ABILITY,
            *hand.tail,
        )
        records.append(_record(short, "imperium", entry.card.name, attrs))
    return records


# =====================================================================================
# Intrigue and Twisted Intrigue cards (bloodlines-cards.md §4, §5)
# =====================================================================================


@dataclass(frozen=True, slots=True)
class IntrigueHand:
    """What §4.0/§4.1 state per card: tags and the ability classes."""

    tags: tuple[str, ...]
    abilities: tuple[str, ...]


INTRIGUE_HAND: Mapping[str, IntrigueHand] = {
    "adaptive_tactics": IntrigueHand((), (_bl("AdaptiveTacticsAbility"),)),
    "battlefield_research": IntrigueHand(
        ("BuyTech", "ConditionalEndgameVP"),
        (
            _bl("BattlefieldResearchCombatAbility"),
            _bl("BattlefieldResearchEndgameAbility"),
        ),
    ),
    "coercive_negotiation": IntrigueHand(
        ("Contract",), (_bl("CoerciveNegotiationAbility"),)
    ),
    "desert_support": IntrigueHand((), (_bl("DesertSupportAbility"),)),
    "emperor_s_invitation": IntrigueHand((), (_bl("EmperorsInvitationAbility"),)),
    "false_orders": IntrigueHand(("Spy",), (_bl("FalseOrdersAbility"),)),
    "grasp_arrakis": IntrigueHand(
        ("ConditionalEndgameVP",),
        (_bl("GraspArrakisCombatAbility"), _bl("GraspArrakisEndgameAbility")),
    ),
    "honor_guard": IntrigueHand((), (_bl("HonorGuardAbility"),)),
    "insider_information": IntrigueHand(
        ("WantSpy", "RecallSpy"), (_bl("InsiderInformationAbility"),)
    ),
    "rapid_engineering": IntrigueHand(
        ("BuyTech", "DiscardEnabler"), (_bl("RapidEngineeringAbility"),)
    ),
    "return_the_favor": IntrigueHand(
        (
            "EmperorInfluence",
            "SpacingGuildInfluence",
            "BeneGesseritInfluence",
            "FremenInfluence",
        ),
        (_bl("ReturnTheFavorAbility"),),
    ),
    "ripples_in_the_sand": IntrigueHand(
        ("WantHooks",), (_bl("RipplesInTheSandAbility"),)
    ),
    "sacred_pools": IntrigueHand(
        ("DiscardEnabler", "ConditionalEndgameVP"),
        (_bl("SacredPoolsPlotAbility"), _bl("SacredPoolsEndgameAbility")),
    ),
    "seize_production": IntrigueHand((), (_bl("SeizeProductionAbility"),)),
    "sleeper_unit": IntrigueHand(
        ("Spy", "WantSpy", "RecallSpy"), (_bl("SleeperUnitAbility"),)
    ),
    "tenuous_bond": IntrigueHand(
        (), (_bl("TenuousBondPlotAbility"), _bl("TenuousBondCombatAbility"))
    ),
    "the_strong_survive": IntrigueHand((), (_bl("TheStrongSurviveAbility"),)),
    "withdrawal_agreement": IntrigueHand((), (_bl("WithdrawalAgreementAbility"),)),
}

#: §1.5 weights of the effect kinds (``w(draw)`` is the number of cards).
#: The swap (lose one Influence -> gain one) takes Change Allegiances' 2 and
#: Acquire Tech takes Machine Culture's 2 (the nearest app cards, plan §11.3).
#: Controlled's peek may draw the top card (for 1 Solari): a draw of one.
INTRIGUE_KIND_WEIGHTS: Mapping[str, int] = {
    "trash": 2,
    "intrigue": 2,
    "influence": 1,
    "acquire": 1,
    "swap": 2,
    "tech": 2,
}


def _intrigue_kinds(entry: IntrigueCardEntry) -> list[tuple[str, int]]:
    """§1.5 effect kinds of every option, with their weights."""

    kinds: list[tuple[str, int]] = []
    for option in entry.options:
        for section in option.sections:
            loses = any(isinstance(c, LoseInfluence) for c in section.costs)
            for reward in section.rewards:
                if isinstance(reward, DrawPersonalCards):
                    kinds.append(("draw", reward.count))
                elif isinstance(reward, PeekTopCard):
                    kinds.append(("draw", 1))
                elif isinstance(reward, TrashPersonalCard):
                    kinds.append(("trash", INTRIGUE_KIND_WEIGHTS["trash"]))
                elif isinstance(reward, DrawIntrigueCards):
                    kinds.append(("intrigue", INTRIGUE_KIND_WEIGHTS["intrigue"]))
                elif isinstance(reward, GainInfluence):
                    kind = "swap" if loses else "influence"
                    kinds.append((kind, INTRIGUE_KIND_WEIGHTS[kind]))
                elif isinstance(reward, AcquireCardUpTo | AcquireReserveCard):
                    kinds.append(("acquire", INTRIGUE_KIND_WEIGHTS["acquire"]))
                elif isinstance(reward, AcquireTech):
                    kinds.append(("tech", INTRIGUE_KIND_WEIGHTS["tech"]))
    return kinds


def intrigue_defer_value(entry: IntrigueCardEntry) -> int:
    """§1.5: ``max over kinds of w`` (0: absent)."""

    return max((w for _, w in _intrigue_kinds(entry)), default=0)


def _combat_swords(entry: IntrigueCardEntry) -> list[tuple[int, int, int]]:
    """Per Combat option: (all swords, free swords, costed swords)."""

    rows = []
    for option in entry.options:
        if option.timing is not IntrigueTiming.COMBAT:
            continue
        total = free = costed = 0
        for section in option.sections:
            n = sum(
                r.amount for r in section.rewards if isinstance(r, GainCombatStrength)
            )
            total += n
            if section.costs:
                costed += n
            elif section.condition is None:
                free += n
        rows.append((total, free, costed))
    return rows


def intrigue_strength(entry: IntrigueCardEntry) -> int:
    """§1.6 ``Strength``: the largest printed sword total of a Combat option."""

    return max((total for total, _, _ in _combat_swords(entry)), default=0)


def intrigue_combat_value(entry: IntrigueCardEntry) -> float | None:
    """§1.6 ``CombatValue``: absent with no swords or on a Plot/Combat card;
    else the swords gained without paying anything, or, when every sword is
    behind a cost, the costed swords."""

    rows = _combat_swords(entry)
    if not rows or max(total for total, _, _ in rows) == 0:
        return None
    if {IntrigueTiming.PLOT, IntrigueTiming.COMBAT} <= entry.timings:
        return None
    free = max(f for _, f, _ in rows)
    return float(free if free > 0 else max(c for _, _, c in rows))


def _type_list(entry: IntrigueCardEntry) -> tuple[str, ...]:
    return tuple(name for t, name in TIMING_NAMES.items() if t in entry.timings)


def _twisted_abilities(entry: IntrigueCardEntry, name: str) -> tuple[str, ...]:
    """§5: one ``AS.Twisted<Name>Ability`` per printed half (a card with two
    timings names each half after its timing)."""

    types = _type_list(entry)
    if len(types) == 1:
        return (_bl(f"Twisted{name}Ability"),)
    return tuple(_bl(f"Twisted{name}{t}Ability") for t in types)


def intrigue_records() -> list[Record]:
    records: list[Record] = []
    plain = [
        e
        for e in INTRIGUE_CARDS
        if e.bloodlines_only and not e.twisted and not e.navigation
    ]
    assert {e.card.card_id for e in plain} == set(INTRIGUE_HAND)
    for entry in plain:
        hand = INTRIGUE_HAND[entry.card.card_id]
        short = "IntrigueArchetypes.AppStyle." + pascal(entry.card.name)
        records.append(
            _intrigue_record(short, entry, entry.card.name, hand.tags, hand.abilities)
        )
    for entry in INTRIGUE_CARDS:
        if not entry.twisted:
            continue
        name = pascal(entry.card.name.removeprefix("Twisted Intrigue: "))
        short = "IntrigueArchetypes.AppStyle.Twisted" + name
        records.append(
            _intrigue_record(
                short, entry, entry.card.name, (), _twisted_abilities(entry, name)
            )
        )
    return records


def _intrigue_record(
    short: str,
    entry: IntrigueCardEntry,
    title: str,
    tags: tuple[str, ...],
    abilities: tuple[str, ...],
) -> Record:
    types = _type_list(entry)
    attrs: dict[str, object] = {
        "EntityType": "Intrigue",
        "CardCount": entry.copies,
        "SetList": _set_list(choam=entry.choam_only, tech=entry.tech_only),
        "IntrigueTypeList": types,
        "Rating": intrigue_rating(frozenset(types)),
    }
    _put(attrs, "Strength", intrigue_strength(entry))
    _put(attrs, "CombatValue", intrigue_combat_value(entry))
    _put(attrs, "DeferValue", intrigue_defer_value(entry))
    _put(attrs, "Tags", tags)
    attrs["WormAbilityIDs"] = abilities
    return _record(short, "intrigue", title, attrs)


# =====================================================================================
# Navigation cards (bloodlines-systems.md §5)
# =====================================================================================


def navigation_records() -> list[Record]:
    records = []
    for entry in INTRIGUE_CARDS:
        if not entry.navigation:
            continue
        number = int(entry.card.card_id.removeprefix("navigation_card_"))
        short = f"NavigationArchetypes.AppStyle.NavigationCard{number}"
        attrs = {
            "EntityType": "Navigation",
            "CardCount": entry.copies,
            "SetList": _set_list(),
            "IntrigueTypeList": (),
            "WormAbilityIDs": (_bl(f"NavigationCard{number}Ability"),),
        }
        records.append(_record(short, "other", entry.card.name, attrs))
    return records


# =====================================================================================
# Conflict cards (bloodlines-cards.md §1.11, §6)
# =====================================================================================

PLACES = ("First", "Second", "Third")


def _reward_attributes(reward: ConflictReward) -> dict[str, object]:
    """The app reward attributes (``ValueForRewardsFrom`` reads them) and the
    custom abilities of the trash and Spy rewards (§6)."""

    attrs: dict[str, object] = {}
    _put(attrs, "Solari", reward.solari)
    _put(attrs, "Spice", reward.spice)
    _put(attrs, "Water", reward.water)
    _put(attrs, "IntrigueCard", reward.intrigue)
    _put(attrs, "Troops", reward.troops)
    custom = [TRASH_CONFLICT_CUSTOM] * reward.trash_cards
    custom += [PLACE_SPY_CUSTOM] * (reward.place_spies + reward.deep_cover_spies)
    _put(attrs, "CustomAbilityIDs", tuple(custom))
    unsupported = (
        reward.contracts,
        reward.victory_points,
        reward.choose_influence,
        reward.choose_distinct_influence,
        reward.faction_influence,
        reward.control_space_id,
        reward.optional_spice_cost,
        reward.optional_solari_cost,
        reward.optional_recall_spies,
    )
    assert not any(unsupported), reward
    return attrs


def conflict_records() -> list[Record]:
    records: list[Record] = []
    for conflict in CONFLICTS:
        if not conflict.bloodlines_only:
            continue
        short = "ConflictArchetypes.AppStyle." + pascal(conflict.card.name)
        reward_shorts = tuple(short + place for place in PLACES)
        spy = any(r.place_spies or r.deep_cover_spies for r in conflict.rewards)
        assert conflict.battle_icon is not None
        attrs = {
            "EntityType": "Conflict",
            "CardCount": 1,
            "SetList": _set_list(),
            "ConflictLevel": int(conflict.tier),
            "BattleIcon": BATTLE_ICON_NAMES[conflict.battle_icon],
            "Tags": ("BattleIcon", *(("Spy",) if spy else ())),
            "ConflictRewardArchetypes": reward_shorts,
            "WormAbilityIDs": GENERIC_CONFLICT,
        }
        records.append(_record(short, "conflict", conflict.card.name, attrs))
        for reward_short, reward in zip(reward_shorts, conflict.rewards, strict=True):
            reward_attrs: dict[str, object] = {
                "EntityType": "ConflictReward",
                "SetList": _set_list(),
            }
            reward_attrs.update(_reward_attributes(reward))
            records.append(_record(reward_short, "conflict_reward", None, reward_attrs))
    return records


# =====================================================================================
# Contract tokens (bloodlines-cards.md §1.10, §7)
# =====================================================================================

#: §7: the app space archetypes our contract targets name (catalog
#: ``SPACE_ARCHETYPES``; the four token targets exist with and without CHOAM).
CONTRACT_TARGET_SPACES: Mapping[str, str] = {
    "deliver_supplies": "SpaceArchetypes.Uprising.DeliverSupplies",
    "high_council": "SpaceArchetypes.Uprising.HighCouncilUP",
    "secrets": "SpaceArchetypes.BaseSet.Secrets",
    "spice_refinery": "SpaceArchetypes.Uprising.SpiceRefinery",
}
#: §7: the Harvest tokens reference the spaces of ``ContractBase_1`` plus
#: Tuek's Sietch (OPEN-3: a static list; the space exists only with Esmar).
HARVEST_PRECEDENT = "ContractArchetypes.Uprising.ContractBase_1"
TUEKS_SIETCH = "SpaceArchetypes.AppStyle.TueksSietch"
CONTRACT_TYPES: Mapping[ContractConditionKind, str] = {
    ContractConditionKind.BOARD_SPACE: "Space",
    ContractConditionKind.HARVEST_SPICE: "Harvest",
    ContractConditionKind.IMMEDIATE_INTRIGUE_TRASH: "Immediate",
    ContractConditionKind.EARN_ALLIANCE: "Alliance",  # new value (§7)
}
#: §7 ``WormAbilityIDs`` per token (the reused app classes and the new ones).
CONTRACT_ABILITIES: Mapping[str, tuple[str, ...]] = {
    "bloodlines_deliver_supplies": (PLACE_SPY_CONTRACT, ACTIVATE_CONTRACT),
    "bloodlines_earn_any_alliance": (_bl("EarnAllianceContractAbility"),),
    "bloodlines_harvest_3": (_bl("Harvest3SpyContractAbility"), ACTIVATE_CONTRACT),
    "bloodlines_harvest_4": (_bl("Harvest4SpyContractAbility"), ACTIVATE_CONTRACT),
    "bloodlines_high_council": (RECALL_AGENT_CONTRACT, ACTIVATE_CONTRACT),
    "bloodlines_immediate": (_bl("ImmediateTrashIntrigueContractAbility"),),
    "bloodlines_secrets": (_bl("Draw1ContractAbility"), ACTIVATE_CONTRACT),
    "bloodlines_spice_refinery": (CONTRACT_ABILITY, ACTIVATE_CONTRACT),
}


def _harvest_spaces() -> tuple[str, ...]:
    refs = ARCHETYPES[HARVEST_PRECEDENT].attributes["ReferencedArchetypeIDs"]
    assert isinstance(refs, tuple)
    return (*(str(r) for r in refs), TUEKS_SIETCH)


def contract_records() -> list[Record]:
    records: list[Record] = []
    assert {c.card.card_id for c in BLOODLINES_CONTRACTS} == set(CONTRACT_ABILITIES)
    for contract in BLOODLINES_CONTRACTS:
        short = "ContractArchetypes.AppStyle.Bloodlines" + pascal(contract.card.name)
        condition, reward = contract.condition, contract.reward
        attrs: dict[str, object] = {
            "EntityType": "Contract",
            "CardCount": 1,
            "SetList": _set_list(choam=True),
            "ContractType": CONTRACT_TYPES[condition.kind],
        }
        if condition.kind is ContractConditionKind.BOARD_SPACE:
            space = CONTRACT_TARGET_SPACES[condition.target]
            attrs["ReferencedArchetypeIDs"] = (space,)
        elif condition.kind is ContractConditionKind.HARVEST_SPICE:
            attrs["ReferencedArchetypeIDs"] = _harvest_spaces()
            attrs["SpiceCost"] = condition.amount
        _put(attrs, "Solari", reward.solari)
        _put(attrs, "Water", reward.water)
        _put(attrs, "Troops", reward.troops)
        # §1.10: DeferValue = the cards the reward draws.
        _put(attrs, "DeferValue", reward.personal_cards)
        tags = (
            *(("Spy",) if reward.spies or reward.deep_cover_spies else ()),
            *(("RecallAgent",) if reward.recall_agents else ()),
        )
        _put(attrs, "Tags", tags)
        attrs["WormAbilityIDs"] = CONTRACT_ABILITIES[contract.card.card_id]
        records.append(_record(short, "contract", contract.card.name, attrs))
    return records


# =====================================================================================
# Leaders (bloodlines-systems.md §4)
# =====================================================================================

#: §4 table: short name (the app's ``Leader`` suffix where an app card shares
#: the name) and ``WormAbilityIDs``.
LEADER_HAND: Mapping[str, tuple[str, tuple[str, ...]]] = {
    "chani": (
        "ChaniLeader",
        (_bl("TacticianAbility"), _bl("FedaykinManeuverSignetAbility")),
    ),
    "count_hasimir_fenring": (
        "CountHasimirFenring",
        (_bl("AssassinAbility"), _bl("CorrinoLiaisonSignetAbility")),
    ),
    "duncan_idaho": (
        "DuncanIdahoLeader",
        (_bl("GinazSwordmasterAbility"), _bl("IntoTheFraySignetAbility")),
    ),
    "esmar_tuek": (
        "EsmarTuekLeader",
        (_bl("TueksSietchLeaderAbility"), _bl("SmuggleSpiceSignetAbility")),
    ),
    "gaius_helen_mohiam": (
        "GaiusHelenMohiam",
        (_bl("ClandestineAbility"), _bl("ListenersSignetAbility")),
    ),
    "piter_de_vries": ("PiterDeVriesLeader", (_bl("TwistedGeniusAbility"), WARMASTER)),
    "steersman_y_rkoon": (
        "SteersmanYrkoonLeader",
        (
            _bl("StrangeFormAbility"),
            _bl("HungryForSpiceAbility"),
            _bl("PlotCourseAbility"),
        ),
    ),
    "liet_kynes": (
        "LietKynesLeader",
        (_bl("ArrakisPlanetologistAbility"), _bl("JudgeOfTheChangeSignetAbility")),
    ),
    "kota_odax_of_ix": (
        "KotaOdaxOfIx",
        (_bl("SecretProjectAbility"), _bl("ReverseEngineeringSignetAbility")),
    ),
}


def leader_records() -> list[Record]:
    records = []
    leaders = [leader for leader in LEADERS if leader.bloodlines_only]
    assert {leader.leader_id for leader in leaders} == set(LEADER_HAND)
    for leader in leaders:
        name, abilities = LEADER_HAND[leader.leader_id]
        short = "LeaderArchetypes.AppStyle." + name
        attrs = {
            "EntityType": "Leader",
            "SetList": _set_list(tech=leader.tech_only),
            "WormAbilityIDs": abilities,
        }
        records.append(_record(short, "leader", leader.name, attrs))
    return records


# =====================================================================================
# Sardaukar Commander and Skills (bloodlines-systems.md §2.1)
# =====================================================================================

COMMANDER_SHORT = "CommanderArchetypes.AppStyle.SardaukarCommander"
#: §2.1 ``WormAbilityIDs`` per Skill.
SKILL_ABILITIES: Mapping[str, str] = {
    "canny": _bl("CannySkillAbility"),
    "charismatic": _bl("SkillRevealAbility"),
    "desperate": _bl("DesperateSkillAbility"),
    "driven": _bl("SkillRevealAbility"),
    "fierce": _bl("FierceSkillAbility"),
    "hardy": _bl("SkillRevealAbility"),
    "loyal": _bl("LoyalSkillAbility"),
}


def sardaukar_records() -> list[Record]:
    records = [
        _record(
            COMMANDER_SHORT,
            "other",
            "Sardaukar Commander",
            {
                "EntityType": "Commander",
                "CardCount": COMMANDER_TOTAL,
                "SetList": _set_list(),
                "Strength": COMMANDER_STRENGTH,
                "SolariCost": COMMANDER_COST_SOLARI,
                "WormAbilityIDs": (),
            },
        )
    ]
    assert {s.skill_id for s in SKILLS} == set(SKILL_ABILITIES)
    for skill in SKILLS:
        attrs: dict[str, object] = {
            "EntityType": "Skill",
            "CardCount": SKILL_COPIES,
            "SetList": _set_list(),
        }
        # The printed amount; Fierce's "+1 with an opposing sandworm" is its
        # ability's (§2.2).
        strength = (
            skill.strength
            + skill.strength_if_landsraad_agent
            + skill.strength_if_emperor_influence
            + skill.trash_for_strength
        )
        _put(attrs, "Strength", strength)
        _put(attrs, "Persuasion", skill.reveal_persuasion)
        _put(attrs, "Spice", skill.reveal_spice)
        _put(attrs, "Troops", skill.reveal_troops)
        if skill.emperor_influence_required:
            attrs["InfluenceRequirements"] = (
                {"Amount": skill.emperor_influence_required, "Faction": "Emperor"},
            )
        attrs["WormAbilityIDs"] = (SKILL_ABILITIES[skill.skill_id],)
        short = "SkillArchetypes.AppStyle." + pascal(skill.name)
        records.append(_record(short, "other", skill.name, attrs))
    return records


# =====================================================================================
# Tech tiles (bloodlines-systems.md §3.2, plan §11.3 and §11.7)
# =====================================================================================

#: Plan §11.7: the Rise of Ix tile whose ``EarlyMod``/``LateMod`` a tile takes:
#: the nearest lasting ability first, else the identical acquire effect;
#: tiles not listed have neither (§3.2).
TILE_MOD_SOURCE: Mapping[str, str] = {
    "planetary_array": "Windtraps",
    "self_destroying_messages": "MinimicFilm",
    "delivery_bay": "DisposalFacility",
    "rapid_dropships": "TrainingDrones",
    "choam_transports": "HoltzmanEngine",
    "glowglobes": "Memocorders",
    "navigation_chamber": "Memocorders",
    "sardaukar_high_command": "Flagship",
}
#: §3.2 ``WormAbilityIDs`` per tile, in the table's order.
TILE_ABILITIES: Mapping[str, tuple[str, ...]] = {
    "advanced_data_analysis": (_bl("AdvancedDataAnalysisAbility"),),
    "choam_transports": (
        _bl("CHOAMTransportsAbility"),
        _bl("AcquireEffectsBonusAbility"),
    ),
    "delivery_bay": (DRAW_IMPERIUM_ACQUIRED, _bl("DeliveryBayAbility")),
    "forbidden_weapons": (_bl("ForbiddenWeaponsAbility"),),
    "gene_locked_vault": (
        _bl("GeneLockedVaultAcquiredAbility"),
        _bl("GeneLockedVaultAbility"),
    ),
    "glowglobes": (MEMOCORDERS_ACQUIRED, _bl("GlowglobesAbility")),
    "navigation_chamber": (MEMOCORDERS_ACQUIRED, _bl("NavigationChamberAbility")),
    "ornithopter_fleet": (_bl("OrnithopterFleetAbility"),),
    "panopticon": (PLACE_SPY_REVEAL, _bl("PanopticonAbility")),
    "planetary_array": (
        DISPOSAL_FACILITY_ACQUIRED,
        _bl("PlanetaryArrayAbility"),
        _bl("AcquireEffectsBonusAbility"),
    ),
    "plasteel_blades": (_bl("PlasteelBladesAbility"),),
    "rapid_dropships": (_bl("RapidDropshipsAbility"),),
    "sardaukar_high_command": (_bl("SardaukarHighCommandAbility"),),
    "self_destroying_messages": (_bl("AcquireEffectsBonusAbility"), MINIMIC_FILM),
    "servo_receivers": (
        _bl("ServoReceiversAcquiredAbility"),
        _bl("ServoReceiversAbility"),
    ),
    "spy_drones": (_bl("SpyDronesAbility"), _bl("AcquireEffectsBonusAbility")),
    "suspensor_suits": (_bl("SuspensorSuitsAbility"),),
    "training_depot": (_bl("TrainingDepotAbility"),),
}


def tile_acquire_effects(tile: TechTile) -> tuple[str, ...]:
    """§3.2 ``AcquireEffectList`` from the printed acquire icons, in the
    engine's key order (``TechTile.acquire_effect_keys``): the app's names
    where the app has one, the NEW ``IntrigueOrImperium``/``ShieldWall``/
    ``Signet`` (D16) otherwise."""

    effects: list[str] = []
    effects += ["Solari"] * tile.acquire_solari
    effects += ["Troop"] * tile.acquire_troops
    effects += ["Intrigue"] * tile.acquire_intrigue
    effects += ["Imperium"] * tile.acquire_cards
    effects += ["VP"] * tile.acquire_victory_points
    effects += ["Contract"] * tile.acquire_contracts
    if tile.acquire_influence_choice:
        effects.append("AnyRank")
    if tile.acquire_intrigue_or_card:
        effects.append("IntrigueOrImperium")
    if tile.acquire_may_destroy_shield_wall:
        effects.append("ShieldWall")
    if tile.acquire_leader_signet:
        effects.append("Signet")
    if tile.acquire_may_trash_card:
        effects.append("Trash")
    effects += ["PlaceSpy"] * tile.acquire_deep_cover_spies
    return tuple(effects)


def tech_records() -> list[Record]:
    ratio = tech_value_ratio()
    records = []
    assert {t.tech_id for t in TECH_TILES} == set(TILE_ABILITIES)
    for tile in TECH_TILES:
        short = "TechTileArchetypes.AppStyle." + pascal(tile.name)
        attrs: dict[str, object] = {
            "EntityType": "TechTile",
            "CardCount": 1,
            "SetList": _set_list(choam=tile.choam_only, tech=True),
            "SpiceCost": tile.cost,
            "AcquireValue": ratio * tile.cost,
            "Tags": (),
        }
        source = TILE_MOD_SOURCE.get(tile.tech_id)
        if source is not None:
            mods = ARCHETYPES["TechTileArchetypes.RiseOfIx." + source].attributes
            for name in ("EarlyMod", "LateMod"):
                if name in mods:
                    attrs[name] = mods[name]
        _put(attrs, "AcquireEffectList", tile_acquire_effects(tile))
        attrs["WormAbilityIDs"] = TILE_ABILITIES[tile.tech_id]
        records.append(_record(short, "other", tile.name, attrs))
    return records


# =====================================================================================
# Tuek's Sietch (bloodlines-systems.md §6)
# =====================================================================================


def space_records() -> list[Record]:
    space = BOARD_SPACES_BY_ID["tuek_sietch"]
    # No observation post watches it (§6 ``ObservationPosts ()``; the app's
    # post indexes are the catalog's ``POST_INDEX``).
    watched = [p for p in OBSERVATION_POSTS if space.space_id in p.connected_space_ids]
    assert not watched, watched
    posts: tuple[int, ...] = ()
    attrs: dict[str, object] = {
        "EntityType": "Space",
        "SetList": _set_list(),
        "AgentIcon": ICON_NAMES[space.agent_icon],
        "CombatSpace": space.combat,
        "BonusSpice": 0,  # runtime ``maker_bonus_spice`` (§6)
        "PossibleSpice": 1,  # "1 spice OR draw 1" (§6)
        "ObservationPosts": posts,
        "Tags": ("Harvest",) if space.maker else (),
        "WormAbilityIDs": (
            _bl("TueksSietchDeferredAbility"),
            DEPLOY_UNITS,
            SPACE_ABILITY,
        ),
    }
    return [_record(TUEKS_SIETCH, "space", space.name, attrs)]


# =====================================================================================
# Arrakeen Scouts lines (scouts.md §1, §2.2, §5)
# =====================================================================================

#: §1: the app card a Reserve acquisition names (catalog ``CARD_ARCHETYPES``).
RESERVE_CARDS: Mapping[str, str] = {
    "prepare_the_way": "ImperiumArchetypes.Uprising.PreparetheWay",
}
#: §5.2: where a mission's parked troops end up on the seat's visit
#: (``rules/scouts_missions.py`` ``_TO_CONFLICT``; OQ-077) or what they
#: become (Tleilaxu Offering: specimens).
MISSION_PARKED: Mapping[str, str] = {
    "security_detail": "conflict",
    "weirding_warfare": "conflict",
    "send_for_aid": "conflict",
    "fedaykin_assistance": "garrison",
    "coordinate_with_the_emperor": "garrison",
    "tleilaxu_offering": "specimens",
}
#: §5.3: the automatic Political Equilibrium is one line (ties only), and
#: Rebuild Infrastructure's agreed line also returns the Shield Wall.
EVENT_EXTRA_LINES: Mapping[str, tuple[ScoutsOption, ...]] = {
    "political_equilibrium": (ScoutsOption(costs=(LoseHighestInfluence(),)),),
}
EVENT_EXTRA_ABILITIES: Mapping[str, tuple[str, ...]] = {
    "rebuild_infrastructure": (_sc("ShieldWallReturnAbility"),),
}
#: The line attribute that carries the troop count the spec writes as the
#: ability's own ``Troops`` (``AS.RecruitToConflictAbility(Troops n)``,
#: ``AS.ParkedTroopsTo…Ability(Troops n)``, §2.3): the line's ``Troops`` is
#: the plain recruit ``scouts_line_value`` prices, so it cannot carry both.
ABILITY_TROOPS = "AbilityTroops"


class _Line:
    """Attributes and abilities of one line, filled in the engine's order."""

    def __init__(self) -> None:
        self.attrs: dict[str, object] = {}
        self.abilities: list[str] = []

    def add(self, name: str, amount: int) -> None:
        if amount:
            value = self.attrs.get(name, 0)
            assert isinstance(value, int)
            self.attrs[name] = value + amount

    def influence(self, faction: Faction, amount: int) -> None:
        current = self.attrs.setdefault("FactionInfluence", {})
        assert isinstance(current, dict)
        key = FACTION_NAMES[faction]
        current[key] = current.get(key, 0) + amount

    def troops_ability(self, ability: str, count: int) -> None:
        assert ABILITY_TROOPS not in self.attrs
        self.abilities.append(ability)
        self.attrs[ABILITY_TROOPS] = count

    def cost(self, cost: object) -> None:
        """§1 encoding of a cost primitive."""

        if isinstance(cost, PayResources):
            self.add("SolariCost", cost.solari)
            self.add("SpiceCost", cost.spice)
            self.add("WaterCost", cost.water)
        elif isinstance(cost, PaySpecimens):
            self.add("SpecimenCost", cost.count)
        elif isinstance(cost, RecallSpy):
            self.abilities += [_sc("RecallSpyCostAbility")] * cost.count
        elif isinstance(cost, DiscardFromHand):
            self.abilities += [_sc("DiscardCostAbility")] * cost.count
        elif isinstance(cost, TrashIntrigueCard):
            self.abilities.append(_sc("TrashIntrigueCostAbility"))
        elif isinstance(cost, TrashPersonalCard):
            assert cost.hand_only and cost.mandatory, cost
            self.abilities.append(_sc("TrashFromHandCostAbility"))
        elif isinstance(cost, LoseGarrisonTroops):
            self.abilities += [_sc("LoseGarrisonTroopsCostAbility")] * cost.count
        elif isinstance(cost, LoseFactionInfluence):
            self.influence(cost.faction, -cost.count)
        elif isinstance(cost, LoseHighestInfluence):
            self.abilities.append(_sc("LoseHighestInfluenceAbility"))
        else:
            raise TypeError(f"no Scouts encoding for cost {cost!r}")

    def reward(self, reward: object) -> None:
        """§1 encoding of a reward primitive."""

        if isinstance(reward, GainResources):
            self.add("Solari", reward.solari)
            self.add("Spice", reward.spice)
            self.add("Water", reward.water)
        elif isinstance(reward, DrawPersonalCards):
            self.abilities += [DRAW_ABILITY] * reward.count
        elif isinstance(reward, DrawIntrigueCards):
            self.add("IntrigueCard", reward.count)
        elif isinstance(reward, PlaceSpy):
            self.abilities.append(PLACE_SPY_CUSTOM)
        elif isinstance(reward, RecruitTroops):
            self.add("Troops", reward.count)
        elif isinstance(reward, RecruitToConflict):
            self.troops_ability(_sc("RecruitToConflictAbility"), reward.count)
        elif isinstance(reward, GainInfluence):
            if reward.factions is None:
                self.abilities.append(GAIN_ANY_INFLUENCE_AGENT)
            else:
                (faction,) = reward.factions
                self.influence(faction, reward.times)
        elif isinstance(reward, GainLowestInfluence):
            self.abilities.append(_sc("GainLowestInfluenceAbility"))
        elif isinstance(reward, TakeContract):
            self.abilities += [GAIN_CONTRACT_CUSTOM] * reward.count
        elif isinstance(reward, TrashPersonalCard):
            self.abilities.append(TRASH_CUSTOM)
        elif isinstance(reward, RecallOtherAgent):
            self.abilities.append(RECALL_AGENT)
        elif isinstance(reward, AcquireReserveCardToHand):
            self.abilities.append(_sc("AcquireReserveToHandAbility"))
            self.attrs["ReferencedArchetypeIDs"] = (RESERVE_CARDS[reward.card_id],)
        elif isinstance(reward, GenerateSpecimens):
            self.add("Specimen", reward.count)
        elif isinstance(reward, Research):
            self.abilities.append(GAIN_RESEARCH_CUSTOM)
        elif isinstance(reward, AdvanceTleilaxu):
            if reward.count == 1:
                self.abilities.append(GAIN_TLEILAXU_CUSTOM)
            else:
                assert reward.count == 2, reward
                self.abilities.append(_sc("GainTwoTleilaxuAbility"))
        elif isinstance(reward, GainSpiceWithHelixBonus):
            self.abilities.append(_sc("HelixSpiceAbility"))
        else:
            raise TypeError(f"no Scouts encoding for reward {reward!r}")

    def option(self, option: ScoutsOption) -> _Line:
        for cost in option.costs:
            self.cost(cost)
        for reward in option.rewards:
            self.reward(reward)
        return self


def _line_record(prefix: str, item_id: str, k: int, title: str, line: _Line) -> Record:
    short = f"{prefix}Archetypes.AppStyle.Scouts{scouts_pascal(item_id)}{k}"
    attrs: dict[str, object] = {"EntityType": "ScoutsLine"}
    attrs.update(line.attrs)
    attrs["WormAbilityIDs"] = tuple(line.abilities)
    record = _record(short, "other", title, attrs)
    record.scouts_ref = f"{item_id}:{k}"
    return record


def _mission_lines(mission: Mission) -> list[_Line]:
    """§5.2 join lines: a mission's choices, or its participation (cost,
    the seat's goods, the parked troops); none for a mission nobody joins."""

    if mission.choices:
        return [_Line().option(choice) for choice in mission.choices]
    if not (mission.participation_cost or mission.parked_troops or mission.seat_goods):
        return []
    line = _Line()
    for cost in mission.participation_cost:
        line.cost(cost)
    n = mission.parked_troops
    if mission.troop_source is TroopSource.GARRISON:
        line.cost(LoseGarrisonTroops(n))
    elif mission.troop_source is TroopSource.SPECIMENS:
        line.cost(PaySpecimens(n))
    if mission.seat_goods is not None:
        line.reward(mission.seat_goods)
    if n:
        where = MISSION_PARKED[mission.mission_id]
        if where == "conflict":
            line.troops_ability(_sc("ParkedTroopsToConflictAbility"), n)
        elif where == "garrison":
            line.troops_ability(_sc("ParkedTroopsToGarrisonAbility"), n)
        else:
            line.add("Specimen", n)
    return [line]


def scouts_records() -> list[Record]:
    records: list[Record] = []
    ids = [s.subcommittee_id for s in SUBCOMMITTEES]
    ids += [m.mission_id for m in MISSIONS] + [e.event_id for e in EVENTS]
    ids += [a.auction_id for a in AUCTIONS] + [s.sale_id for s in SALES]
    assert len(ids) == len(set(ids)), "Scouts item ids must be unique"
    for sub in SUBCOMMITTEES:
        line = _Line().option(sub.option)
        records.append(
            _line_record("Subcommittee", sub.subcommittee_id, 0, sub.name, line)
        )
    for mission in MISSIONS:
        for k, line in enumerate(_mission_lines(mission)):
            records.append(
                _line_record("Mission", mission.mission_id, k, mission.name, line)
            )
    for event in EVENTS:
        options = (
            *event.options,
            *(choice.option for choice in event.secret_choices),
            *EVENT_EXTRA_LINES.get(event.event_id, ()),
        )
        for k, option in enumerate(options):
            line = _Line().option(option)
            line.abilities += EVENT_EXTRA_ABILITIES.get(event.event_id, ())
            records.append(_line_record("Event", event.event_id, k, event.name, line))
    for auction in AUCTIONS:
        if auction.kind is not AuctionKind.SEALED:
            continue  # Mercenaries and Critical Moment have no line (§5.4)
        for k, rewards in enumerate(auction.rank_rewards):
            line = _Line().option(ScoutsOption(rewards=rewards))
            records.append(
                _line_record("Auction", auction.auction_id, k, auction.name, line)
            )
    for sale in SALES:
        for k, option in enumerate(sale.options):
            line = _Line().option(option)
            records.append(_line_record("Sale", sale.sale_id, k, sale.name, line))
    return records


# =====================================================================================
# Rendering
# =====================================================================================


def all_records() -> list[Record]:
    records = [
        *imperium_records(),
        *intrigue_records(),
        *navigation_records(),
        *conflict_records(),
        *contract_records(),
        *leader_records(),
        *sardaukar_records(),
        *tech_records(),
        *space_records(),
        *scouts_records(),
    ]
    shorts = [r.short for r in records]
    assert len(shorts) == len(set(shorts)), "duplicate synthetic short name"
    assert not set(shorts) & set(ARCHETYPES), "synthetic name collides with the app"
    return sorted(records, key=lambda r: r.short)


def _literal(value: object) -> str:
    """A Python literal for one attribute value (lists become tuples)."""

    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list | tuple):
        inner = ", ".join(_literal(item) for item in value)
        return f"({inner},)" if len(value) == 1 else f"({inner})"
    if isinstance(value, dict):
        items = ", ".join(
            f"{json.dumps(str(key))}: {_literal(item)}"
            for key, item in sorted(value.items())
        )
        return "{" + items + "}"
    if value is None:
        return "None"
    raise TypeError(f"cannot emit {value!r}")


HEADER = '''"""The app-style archetypes of the items the Steam app does not have.

Bloodlines (Imperium, Intrigue, Twisted Intrigue and Navigation cards,
Conflict cards, contract tokens, leaders, the Sardaukar Commander and its
Skills, Tech tiles, Tuek's Sietch) and the Arrakeen Scouts lines, built by
docs/app-ai-plan.md §11.3 and the specs docs/app-ai/bloodlines-cards.md,
docs/app-ai/bloodlines-systems.md and docs/app-ai/scouts.md: the app's
attribute names, the printed numbers of our content definitions, and the
hand-authored app values computed by rules fitted on the app's own data.
Kept apart from the app extraction (``archetypes.py``); every short name is
``<Kind>Archetypes.AppStyle.<Name>`` and none is an app name.

Generated by ``scripts/dwgr/app_ai_synth.py``. Do not edit by hand: change the
content, the specs' rules or the generator's hand tables and re-run it.
``SCOUTS_LINES`` maps each Scouts line (``<item id>:<line index>``) to its
archetype; a line whose ability the spec gives a troop count carries it as
``AbilityTroops``.
"""

# ruff: noqa: E501  (generated data: ability class names do not wrap)

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.agents.app_ai.data.archetypes import Archetype
'''


def render_unformatted(records: Sequence[Record]) -> str:
    lines = [HEADER, "SYNTHETIC: Final[Mapping[str, Archetype]] = MappingProxyType({"]
    for record in records:
        lines.append(f"    {json.dumps(record.short)}: Archetype(")
        lines.append(f"        short={json.dumps(record.short)},")
        lines.append(f"        kind={json.dumps(record.kind)},")
        lines.append(f"        title={_literal(record.title)},")
        lines.append("        in_uprising=False,")
        lines.append("        in_uprising_choam=False,")
        lines.append("        attributes=MappingProxyType({")
        for key in sorted(record.attributes):
            value = _literal(record.attributes[key])
            lines.append(f"            {json.dumps(key)}: {value},")
        lines.append("        }),")
        lines.append("    ),")
    lines += ["})", ""]
    lines.append("SCOUTS_LINES: Final[Mapping[str, str]] = MappingProxyType({")
    refs = sorted((r.scouts_ref, r.short) for r in records if r.scouts_ref)
    for ref, short in refs:
        lines.append(f"    {json.dumps(ref)}: {json.dumps(short)},")
    lines += ["})", ""]
    return "\n".join(lines)


def ruff_format(source: str, path: Path) -> str:
    """``ruff format`` the module text as if it were ``path``."""

    result = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--stdin-filename", str(path), "-"],
        input=source,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def render(path: Path = _OUT_DEFAULT) -> str:
    """The formatted module text the generator writes to ``path``."""

    return ruff_format(render_unformatted(all_records()), path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=_OUT_DEFAULT)
    args = parser.parse_args()
    text = render(args.out)
    args.out.write_text(text)
    print(f"wrote {args.out} ({text.count('Archetype(')} archetypes)")


if __name__ == "__main__":
    main()
