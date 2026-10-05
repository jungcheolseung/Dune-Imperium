"""App-style Bloodlines card abilities: docs/app-ai/bloodlines-cards.md.

Every test builds a real Bloodlines ``GameState`` (``app_ai.testing``),
adjusts the fields a formula reads, and stubs the ``Profile`` methods other
areas own with simple linear prices, so each expected value is checked by
hand against the spec's formula and literals. A coverage test pins that
every ability id of every bloodlines-cards.md archetype resolves to a port,
and a smoke test runs every port on the real profile.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import PORTS, abilities_of
from dune_imperium.agents.app_ai.abilities import bloodlines_cards as bc
from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Answer,
    Pile,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
)
from dune_imperium.agents.app_ai.abilities.board import (
    Harvest3ContractAbility,
    Harvest4ContractAbility,
)
from dune_imperium.agents.app_ai.abilities.intrigue import (
    COMBAT_TIMING,
    ENDGAME_TIMING,
    PLOT_TIMING,
    IntrigueAbility,
    StrengthIntrigueAbility,
    _placement_value,
    ability_for_prompt,
    endgame_auto_plays,
)
from dune_imperium.agents.app_ai.catalog import (
    CARD_ARCHETYPES,
    CONFLICT_ARCHETYPES,
    CONTRACT_ARCHETYPES,
    INTRIGUE_ARCHETYPES,
    card_entity,
    conflict_entity,
    contract_entity,
    intrigue_entity,
    post_entity,
    space_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.data.synthetic import SYNTHETIC
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile import combat as combat_module
from dune_imperium.agents.app_ai.profile import economy as economy_module
from dune_imperium.agents.app_ai.profile import influence as influence_module
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState

AS = "worm.canis.abilities.AppStyle.Bloodlines."
SEAT = 0  # the first player of seed 1 with Bloodlines and Tech (Feyd-Rautha)
CONFIG = RulesetConfig(choam_module=True, bloodlines=True, tech_module=True)
INFLUENCE = {"emperor": 2.0, "spacing_guild": 2.5, "bene_gesserit": 3.0, "fremen": 1.0}

# ---------------------------------------------------------------------------
# Fixtures and stubs
# ---------------------------------------------------------------------------


def _base_stubs() -> dict[str, Callable[..., Any]]:
    return {
        "persuasion_value": lambda n: 0.75 * n,
        "spice_value": lambda n: 0.5 * n,
        "solari_value": lambda n: 0.25 * n,
        "water_value": lambda n: 1.0 * n,
        "strength_value": lambda n, include=False: 0.66 * n,
        "troop_value": lambda n, include=False: 0.9 * n,
        "victory_point_value": lambda n: 6.0 * n,
        "card_draw_value": lambda: 1.5,
        "possible_persuasion_gain": lambda: 3,
        "buy_gains": lambda n: 0.1 * n,
        "card_draw_value_with_buy_gains": lambda: 1.8,
        "intrigue_value": lambda: 2.25,
        "trash_card_value": lambda: 2.75,
        "trash_mod": lambda: 1.0,
        "discard_value": lambda: -1.0,
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(
            INFLUENCE[f] * n
        ),
        "spy_value": lambda: Summer(1.66),
        "recall_spy_value": lambda: Summer(-1.2),
        "recall_spy": lambda spies: (spies[0], -1.0) if spies else (None, 0.0),
        "best_post": lambda posts: (posts[-1], 2.0) if posts else (None, 0.0),
        "is_climax": lambda: False,
        "is_final_round": lambda: False,
        "acquire_value": lambda card: Summer(float(card.int_attr("PersuasionCost"))),
        "card_to_trash": lambda targets, minimum: (None, minimum),
        "discard_order": lambda cards, bonus: list(cards),
        "deploy_value": lambda owner: 1.25,
        "units_to_deploy": lambda garrison, max_units: (
            min(garrison, max_units) if max_units > 0 else garrison
        ),
        "troops_to_retreat": lambda max_troops: max_troops,
        "should_play_retreat_intrigue": lambda name, a, b, n: 1,
        "should_play_troop_intrigue": lambda name, a, b, n: 100,
        "trash_intrigue_value": lambda: -1.25,
        "gain_contract_value": lambda: Summer(3.5),
        "possible_persuasion": lambda: 4,
        "estimated_conflict_rank": lambda bonus=0: 2,
        "buy_tech_value": lambda discount, allow_solari: 2.2,
        "tech_tile_to_acquire": lambda discount, allow_solari: None,
        "has_or_would_gain_alliance": lambda f, n: False,
        "best_influence_exchange": lambda lose, gain, lf=None, gf=None: (
            (lf or ["emperor"])[0],
            "bene_gesserit",
            2.5,
        ),
        "current_conflict_interest": lambda: Summer(1.0),
        "conflict_posture_bounds": lambda: (0.5, 2.0),
    }


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """Seat 0's first ``turn`` decision (round 1, CHOAM, Bloodlines, Tech)."""

    return first_decision("turn", config=CONFIG)


@pytest.fixture(scope="module")
def effects_state() -> GameState:
    """Seat 0's first ``agent_effects``: Reconnaissance at Arrakeen."""

    return first_decision("agent_effects", config=CONFIG)


@pytest.fixture(scope="module")
def reveal_state() -> GameState:
    """Seat 0's first ``reveal`` (3 Persuasion generated)."""

    return first_decision("reveal", config=CONFIG)


ProfileFactory = Callable[..., Profile]


@pytest.fixture
def prof(monkeypatch: pytest.MonkeyPatch) -> ProfileFactory:
    """``prof(state, **stub overrides) -> Profile`` (stubbed prices)."""

    def build(
        state: GameState, seat: int = SEAT, **overrides: Callable[..., Any]
    ) -> Profile:
        profile = make_profile(state, seat)
        stubs = _base_stubs()
        stubs.update(overrides)
        for name, fn in stubs.items():
            monkeypatch.setattr(profile, name, fn)
        return profile

    return build


def card(name: str, copy: int = 0) -> Entity:
    return card_entity(f"imperium:{name}:{copy}", SEAT)


def starter(name: str, copy: int = 0) -> Entity:
    return card_entity(f"player:{SEAT}:starter:{name}:{copy}", SEAT)


def intrigue(name: str) -> Entity:
    return intrigue_entity(f"intrigue:{name}:0", SEAT)


def contract(name: str) -> Entity:
    return contract_entity(f"contract:bloodlines_{name}", SEAT)


def req(*entities: Entity, options: tuple[int, ...] = ()) -> Request:
    return Request((TargetInfo(tuple(entities), options, 0, 1),))


def reqs(*infos: TargetInfo) -> Request:
    return Request(infos)


def info(*entities: Entity, options: tuple[int, ...] = ()) -> TargetInfo:
    return TargetInfo(tuple(entities), options, 0, 1)


def hand(state: GameState, *cards: Entity) -> GameState:
    return with_player(state, SEAT, hand=tuple(c.ref for c in cards))


def in_play(state: GameState, *cards: Entity) -> GameState:
    return with_player(state, SEAT, in_play=tuple(c.ref for c in cards))


def ability(name: str, owner: Entity) -> Any:
    return PORTS[AS + name](owner)


def units(state: GameState, **counts: int) -> GameState:
    """Seat 0's troops and Commanders, the troop supply keeping the 12."""

    me = state.players[SEAT]
    fields = {
        "troops_garrison": me.troops_garrison,
        "troops_conflict": me.troops_conflict,
    }
    fields.update({k: v for k, v in counts.items() if k in fields})
    others = {k: v for k, v in counts.items() if k not in fields}
    supply = (
        12
        - fields["troops_garrison"]
        - fields["troops_conflict"]
        - me.memories
        - me.specimens
        - me.troops_parked
    )
    return with_player(state, SEAT, troops_supply=supply, **fields, **others)


POSTS = ("arrakis-imperial-basin", "arrakis-hagga-basin", "arrakis-deep-desert")


def spies(state: GameState, n: int) -> GameState:
    """Seat 0 with ``n`` Spies on the board (the rest in the supply)."""

    return with_player(state, SEAT, spy_post_ids=POSTS[:n], spies_supply=3 - n)


def agents(state: GameState, available: int) -> GameState:
    """Seat 0 with ``available`` Agents left (the others on spaces)."""

    placed = ("arrakeen", "imperial_basin")[: 2 - available]
    return with_player(state, SEAT, agents_available=available, agent_locations=placed)


def own_contracts(state: GameState, *ids: str, completed: int = 0) -> GameState:
    """Seat 0 holds the Bloodlines tokens ``ids`` (taken out of the bank and
    the market) and ``completed`` other contracts completed."""

    bank = [c for c in state.contract_bank if c not in ids]
    market = tuple(c for c in state.face_up_contract_ids if c not in ids)
    done = tuple(bank[:completed])
    bank = bank[completed:]
    state = with_state(state, contract_bank=tuple(bank), face_up_contract_ids=market)
    return with_player(
        state, SEAT, active_contract_ids=ids, completed_contract_ids=done
    )


def own_tiles(state: GameState, n: int) -> GameState:
    """Seat 0 holds ``n`` Tech tiles taken from the stacks."""

    pool = [t for stack in state.tech_stacks for t in stack][:n]
    stacks = tuple(
        tuple(t for t in stack if t not in pool) for stack in state.tech_stacks
    )
    state = with_state(state, tech_stacks=stacks)
    return with_player(state, SEAT, tech_ids=tuple(pool))


def won(state: GameState, *conflict_ids: str) -> GameState:
    """Seat 0 won ``conflict_ids`` (taken out of the shared Conflict zones)."""

    state = with_state(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c not in conflict_ids),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c not in conflict_ids
        ),
        current_conflict_ids=tuple(
            c for c in state.current_conflict_ids if c not in conflict_ids
        ),
    )
    return with_player(state, SEAT, won_conflict_ids=conflict_ids)


# ---------------------------------------------------------------------------
# Coverage and class chain
# ---------------------------------------------------------------------------


def _bloodlines_card_shorts() -> list[str]:
    """Every archetype of bloodlines-cards.md (Imperium, Intrigue incl.
    Twisted, Conflict, contract token)."""

    shorts: list[str] = []
    for table in (CARD_ARCHETYPES, INTRIGUE_ARCHETYPES, CONTRACT_ARCHETYPES):
        shorts.extend(s for s in table.values() if ".AppStyle." in s)
    for pair in CONFLICT_ARCHETYPES.values():
        shorts.extend(s for s in pair if ".AppStyle." in s)
    return sorted(set(shorts))


def _synthetic(short: str) -> Entity:
    """An entity carrying the synthetic archetype ``short`` (attribute reads)."""

    return Entity(Kind.CARD, short, SYNTHETIC[short])


def test_every_bloodlines_card_ability_id_has_a_port() -> None:
    shorts = _bloodlines_card_shorts()
    assert len(shorts) == 67  # 27 + 18 + 12 + 2 + 8 (spec §10)
    missing: list[tuple[str, str]] = []
    for short in shorts:
        entity = _synthetic(short)
        ids = list(entity.list_attr("WormAbilityIDs"))
        for reward in entity.list_attr("ConflictRewardArchetypes"):
            ids.extend(_synthetic(reward).list_attr("CustomAbilityIDs"))
        missing.extend((short, i) for i in ids if i not in PORTS)
    assert missing == []


def test_the_module_registers_the_89_spec_classes() -> None:
    names = sorted(n for n, cls in PORTS.items() if cls.__module__ == bc.__name__)
    assert len(names) == 89  # spec §10: 5 shared + 44 + 22 + 13 + 5
    assert all(n.startswith(AS) for n in names)
    used = {
        i
        for short in _bloodlines_card_shorts()
        for i in _synthetic(short).list_attr("WormAbilityIDs")
        if i.startswith(AS)
    }
    abstract = {
        AS + "CommandRevealAbility",
        AS + "RevealCombatIconAbility",
        AS + "DiscardForRewardAgentAbility",
    }
    assert used | abstract == set(names)


_CHAIN: list[tuple[str, type[Ability]]] = [
    ("CommandRevealAbility", g.DeferredAbility),
    ("RevealCombatIconAbility", g.DeployUnitsAbility),
    ("DiscardForRewardAgentAbility", g.DeferredAbility),
    ("AcquirePlaceSpyBonusAbility", g.ActivatedAbility),
    ("AcquireContractBonusAbility", g.ActivatedAbility),
    ("RuthlessLeadershipTrashAbility", g.TrashAgentAbility),
    ("RuthlessLeadershipCommandAbility", bc.RevealCombatIconAbility),
    ("ArrakisObserverAgentAbility", bc.DiscardForRewardAgentAbility),
    ("ArrakisObserverRevealAbility", g.DeferredAbility),
    ("BombastCommandAbility", bc.CommandRevealAbility),
    ("CHOAMDemandsAgentAbility", g.DeferredAbility),
    ("CHOAMDemandsRevealAbility", g.DeferredAbility),
    ("CommandCenterAgentAbility", g.DeferredAbility),
    ("CommandCenterRevealAbility", g.DeferredAbility),
    ("CorruptBureaucratAgentAbility", g.GainContractAbility),
    ("CorruptBureaucratDiscardAbility", g.TriggeredAbility),
    ("DeliveryLogisticsRevealAbility", g.DeferredAbility),
    ("DisruptionTacticsAgentAbility", g.DeferredAbility),
    ("DisruptionTacticsRevealAbility", bc.RevealCombatIconAbility),
    ("EliminateAlliesTrashAbility", g.TriggeredAbility),
    ("EliteForcesAgentAbility", g.TrashAbility),
    ("EngineeredMiracleAgentAbility", bc.DiscardForRewardAgentAbility),
    ("EngineeredMiracleCommandAbility", bc.CommandRevealAbility),
    ("FremenWarNameTroopAbility", g.DeferredAbility),
    ("FremenWarNameDrawAbility", g.DrawAbility),
    ("FremenWarNameBondAbility", g.BondAbility),
    ("HolyWarAgentAbility", g.DeferredAbility),
    ("HolyWarBondAbility", bc.RevealCombatIconAbility),
    ("IBelieveAgentAbility", bc.DiscardForRewardAgentAbility),
    ("IBelieveCommandAbility", bc.CommandRevealAbility),
    ("ImperialThroneshipRevealAbility", g.RevealAbility),
    ("ImperialThroneshipTriggeredAbility", g.TriggeredAbility),
    ("IntelligenceTrainingCommandAbility", g.PlaceSpyRevealAbility),
    ("IxianAmbassadorRevealAbility", g.GainAnyInfluenceRevealAbility),
    ("LitanyTurnStartAbility", g.DeferredAbility),
    ("MercantileAffairsAgentAbility", g.DeferredAbility),
    ("PointingTheWayAgentAbility", g.DeferredAbility),
    ("PointingTheWayCommandAbility", g.GainAnyInfluenceRevealAbility),
    ("PossibleFuturesAgentAbility", g.DeferredAbility),
    ("QuashRebellionRevealAbility", g.RevealAbility),
    ("QuashRebellionTriggeredAbility", g.TriggeredAbility),
    ("SandwalkDrawAbility", g.DrawAbility),
    ("SandwalkRevealAbility", g.RevealAbility),
    ("SandwalkBondAbility", g.BondAbility),
    ("SardaukarStandardTrashAbility", g.TriggeredAbility),
    ("ShroudedCounselCommandAbility", g.TrashAbility),
    ("SouthernFaithAgentAbility", g.DeferredAbility),
    ("SouthernFaithCommandAbility", bc.CommandRevealAbility),
    ("UrgentShigawireAgentAbility", g.DeferredAbility),
    ("AdaptiveTacticsAbility", IntrigueAbility),
    ("BattlefieldResearchCombatAbility", StrengthIntrigueAbility),
    ("BattlefieldResearchEndgameAbility", IntrigueAbility),
    ("CoerciveNegotiationAbility", IntrigueAbility),
    ("DesertSupportAbility", StrengthIntrigueAbility),
    ("EmperorsInvitationAbility", IntrigueAbility),
    ("FalseOrdersAbility", IntrigueAbility),
    ("GraspArrakisCombatAbility", StrengthIntrigueAbility),
    ("GraspArrakisEndgameAbility", IntrigueAbility),
    ("HonorGuardAbility", IntrigueAbility),
    ("InsiderInformationAbility", IntrigueAbility),
    ("RapidEngineeringAbility", IntrigueAbility),
    ("ReturnTheFavorAbility", StrengthIntrigueAbility),
    ("RipplesInTheSandAbility", StrengthIntrigueAbility),
    ("SacredPoolsPlotAbility", IntrigueAbility),
    ("SacredPoolsEndgameAbility", IntrigueAbility),
    ("SeizeProductionAbility", IntrigueAbility),
    ("SleeperUnitAbility", IntrigueAbility),
    ("TenuousBondPlotAbility", IntrigueAbility),
    ("TenuousBondCombatAbility", StrengthIntrigueAbility),
    ("TheStrongSurviveAbility", StrengthIntrigueAbility),
    ("WithdrawalAgreementAbility", StrengthIntrigueAbility),
    ("TwistedAmbitiousAbility", IntrigueAbility),
    ("TwistedCalculatingAbility", IntrigueAbility),
    ("TwistedControlledPlotAbility", IntrigueAbility),
    ("TwistedControlledCombatAbility", StrengthIntrigueAbility),
    ("TwistedDeviousAbility", IntrigueAbility),
    ("TwistedDiscerningAbility", IntrigueAbility),
    ("TwistedInsidiousAbility", IntrigueAbility),
    ("TwistedResourcefulAbility", IntrigueAbility),
    ("TwistedSadisticAbility", IntrigueAbility),
    ("TwistedShrewdAbility", StrengthIntrigueAbility),
    ("TwistedSinisterAbility", StrengthIntrigueAbility),
    ("TwistedUnnaturalAbility", IntrigueAbility),
    ("TwistedWithdrawnAbility", IntrigueAbility),
    ("Draw1ContractAbility", g.Draw2ContractAbility),
    ("Harvest3SpyContractAbility", Harvest3ContractAbility),
    ("Harvest4SpyContractAbility", Harvest4ContractAbility),
    ("ImmediateTrashIntrigueContractAbility", g.ContractAbility),
    ("EarnAllianceContractAbility", g.ContractAbility),
]


@pytest.mark.parametrize(("name", "base"), _CHAIN)
def test_class_chain(name: str, base: type[Ability]) -> None:
    cls = PORTS[AS + name]
    assert cls.APP_CLASS == AS + name
    assert issubclass(cls, base)


def test_chain_covers_every_class() -> None:
    names = {AS + n for n, _ in _CHAIN}
    assert names == {n for n, c in PORTS.items() if c.__module__ == bc.__name__}


_FLAGS: list[tuple[str, SelectionMode, bool, Timing]] = [
    ("BombastCommandAbility", SelectionMode.EXPLICIT, True, Timing.REVEAL),
    ("IBelieveCommandAbility", SelectionMode.EXPLICIT, True, Timing.REVEAL),
    ("SouthernFaithCommandAbility", SelectionMode.EXPLICIT, True, Timing.REVEAL),
    ("EngineeredMiracleCommandAbility", SelectionMode.OPTIONAL, False, Timing.REVEAL),
    ("RuthlessLeadershipCommandAbility", SelectionMode.OPTIONAL, False, Timing.REVEAL),
    ("HolyWarBondAbility", SelectionMode.OPTIONAL, False, Timing.REVEAL),
    ("DisruptionTacticsRevealAbility", SelectionMode.OPTIONAL, False, Timing.REVEAL),
    ("ArrakisObserverAgentAbility", SelectionMode.OPTIONAL, False, Timing.AGENT),
    ("ArrakisObserverRevealAbility", SelectionMode.OPTIONAL, False, Timing.REVEAL),
    ("CHOAMDemandsAgentAbility", SelectionMode.EXPLICIT, False, Timing.AGENT),
    ("CHOAMDemandsRevealAbility", SelectionMode.OPTIONAL, False, Timing.REVEAL),
    ("CommandCenterAgentAbility", SelectionMode.EXPLICIT, True, Timing.AGENT),
    ("CommandCenterRevealAbility", SelectionMode.OPTIONAL, False, Timing.REVEAL),
    ("DeliveryLogisticsRevealAbility", SelectionMode.EXPLICIT, False, Timing.REVEAL),
    ("DisruptionTacticsAgentAbility", SelectionMode.EXPLICIT, False, Timing.AGENT),
    ("EliteForcesAgentAbility", SelectionMode.OPTIONAL, False, Timing.AGENT),
    ("EngineeredMiracleAgentAbility", SelectionMode.OPTIONAL, False, Timing.AGENT),
    ("FremenWarNameTroopAbility", SelectionMode.EXPLICIT, True, Timing.AGENT),
    ("HolyWarAgentAbility", SelectionMode.EXPLICIT, True, Timing.AGENT),
    ("IBelieveAgentAbility", SelectionMode.OPTIONAL, False, Timing.AGENT),
    ("LitanyTurnStartAbility", SelectionMode.OPTIONAL, False, Timing.NONE),
    ("MercantileAffairsAgentAbility", SelectionMode.EXPLICIT, False, Timing.AGENT),
    ("PointingTheWayAgentAbility", SelectionMode.EXPLICIT, False, Timing.AGENT),
    ("PossibleFuturesAgentAbility", SelectionMode.EXPLICIT, False, Timing.AGENT),
    ("ShroudedCounselCommandAbility", SelectionMode.OPTIONAL, False, Timing.REVEAL),
    ("SouthernFaithAgentAbility", SelectionMode.EXPLICIT, False, Timing.AGENT),
    ("UrgentShigawireAgentAbility", SelectionMode.EXPLICIT, True, Timing.AGENT),
    ("RuthlessLeadershipTrashAbility", SelectionMode.EXPLICIT, False, Timing.AGENT),
    (
        "IntelligenceTrainingCommandAbility",
        SelectionMode.EXPLICIT,
        False,
        Timing.REVEAL,
    ),
    ("PointingTheWayCommandAbility", SelectionMode.EXPLICIT, False, Timing.REVEAL),
    ("IxianAmbassadorRevealAbility", SelectionMode.EXPLICIT, False, Timing.REVEAL),
]


@pytest.mark.parametrize(("name", "mode", "auto", "timing"), _FLAGS)
def test_engine_side_members(
    turn_state: GameState,
    prof: ProfileFactory,
    name: str,
    mode: SelectionMode,
    auto: bool,
    timing: Timing,
) -> None:
    port = ability(name, card("sandwalk"))
    assert port.selection_mode(prof(turn_state)) == mode
    assert port.always_run_immediately is auto
    assert port.timing == timing


def test_reveal_and_triggered_timings() -> None:
    for name in (
        "FremenWarNameBondAbility",
        "SandwalkBondAbility",
        "ImperialThroneshipTriggeredAbility",
        "QuashRebellionTriggeredAbility",
        "ImperialThroneshipRevealAbility",
        "QuashRebellionRevealAbility",
        "SandwalkRevealAbility",
    ):
        assert PORTS[AS + name].timing == Timing.REVEAL
    for name in (
        "CorruptBureaucratDiscardAbility",
        "EliminateAlliesTrashAbility",
        "SardaukarStandardTrashAbility",
    ):
        assert PORTS[AS + name].timing == Timing.NONE


def test_intrigue_timings_and_prompt_halves() -> None:
    assert (
        ability_for_prompt(intrigue("tenuous_bond"), False).__class__
        is (PORTS[AS + "TenuousBondPlotAbility"])
    )
    assert (
        ability_for_prompt(intrigue("tenuous_bond"), True).__class__
        is (PORTS[AS + "TenuousBondCombatAbility"])
    )
    assert (
        ability_for_prompt(intrigue("twisted_controlled"), True).__class__
        is (PORTS[AS + "TwistedControlledCombatAbility"])
    )
    for name in ("BattlefieldResearchEndgameAbility", "GraspArrakisEndgameAbility"):
        assert PORTS[AS + name].ability_timing == ENDGAME_TIMING  # type: ignore[attr-defined]
    assert PORTS[AS + "SacredPoolsEndgameAbility"].ability_timing == ENDGAME_TIMING  # type: ignore[attr-defined]
    assert PORTS[AS + "HonorGuardAbility"].ability_timing == PLOT_TIMING  # type: ignore[attr-defined]
    assert PORTS[AS + "TwistedShrewdAbility"].ability_timing == COMBAT_TIMING  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# §2.1 Command (6+)
# ---------------------------------------------------------------------------


def _with_reveal_generated(state: GameState, generated: int) -> GameState:
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context["persuasion_generated"] = generated
    new = replace(frame, context=tuple(sorted(context.items())))
    return with_state(state, decision_stack=(*state.decision_stack[:-1], new))


def test_command_reached_outside_reveal_reads_the_forecast(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    assert bc.command_reached(prof(turn_state, possible_persuasion=lambda: 6))
    assert not bc.command_reached(prof(turn_state, possible_persuasion=lambda: 5))


def test_command_reached_in_the_reveal_reads_generated_persuasion(
    reveal_state: GameState, prof: ProfileFactory
) -> None:
    # The forecast is ignored in the own Reveal turn (purchases never cancel
    # Command: the generated total is read, OQ-033).
    six = _with_reveal_generated(reveal_state, 6)
    assert bc.command_reached(prof(six, possible_persuasion=lambda: 0))
    five = _with_reveal_generated(reveal_state, 5)
    assert not bc.command_reached(prof(five, possible_persuasion=lambda: 9))


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("BombastCommandAbility", 0.25 * 3),
        ("IBelieveCommandAbility", 0.9 * 2),
        ("SouthernFaithCommandAbility", 0.5 * 2),
    ],
)
def test_automatic_command_rewards(
    turn_state: GameState, prof: ProfileFactory, name: str, expected: float
) -> None:
    port = ability(name, card("bombast"))
    reached = prof(turn_state, possible_persuasion=lambda: 6)
    assert port.value_for_player(reached).sum == pytest.approx(expected)
    assert port.evaluate(reached, Request()).value == 100.0
    missed = prof(turn_state, possible_persuasion=lambda: 5)
    assert port.value_for_player(missed).sum == 0.0


def test_command_cards_enter_the_reveal_sum(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state, possible_persuasion=lambda: 6)
    bombast = card("bombast")
    reveal = next(a for a in abilities_of(bombast) if isinstance(a, g.RevealAbility))
    # Persuasion 1 (resource_value stub is not stubbed: use the summer label).
    value = reveal.value_for_player(p)
    assert value.sum == pytest.approx(
        p.resource_value(Attr.PERSUASION, 1, False) + 0.25 * 3
    )


# ---------------------------------------------------------------------------
# §2.2 Reveal Combat icon, §2.3 bonds
# ---------------------------------------------------------------------------


def test_reveal_combat_icon_gates(turn_state: GameState, prof: ProfileFactory) -> None:
    rl = ability("RuthlessLeadershipCommandAbility", card("ruthless_leadership"))
    assert (
        rl.value_for_player(prof(turn_state, possible_persuasion=lambda: 6)).sum == 1.25
    )
    assert (
        rl.value_for_player(prof(turn_state, possible_persuasion=lambda: 5)).sum == 0.0
    )
    dt = ability("DisruptionTacticsRevealAbility", card("disruption_tactics"))
    assert dt.value_for_player(prof(turn_state)).sum == 1.25
    answer = dt.evaluate(prof(turn_state), Request((TargetInfo((), (0, 1, 2), 0, 2),)))
    assert answer == Answer(0.5, ((0, 1),), "Deploy Units | 0.5 | 2")


def test_holy_war_bond_gate_and_fremen_deck_synergy(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    holy_war = card("holy_war")
    bond = ability("HolyWarBondAbility", holy_war)
    alone = hand(turn_state, holy_war, starter("dagger"))
    assert bond.value_for_player(prof(alone)).sum == 0.0
    friends = hand(turn_state, holy_war, card("sandwalk"))
    assert bond.value_for_player(prof(friends)).sum == 1.25
    p = prof(friends)
    deck = bond.value_in_pile_for_other_play(p, Pile.DECK, card("sandwalk"))
    assert deck.sum == p.C.SynergyFremenWithBondInDeck
    assert bond.value_in_pile_for_other_play(p, Pile.DECK, starter("dagger")).sum == 0


def test_fremen_reveal_bonds(turn_state: GameState, prof: ProfileFactory) -> None:
    sandwalk = card("sandwalk")
    fwn = card("fremen_war_name")
    state = hand(turn_state, sandwalk, fwn)
    p = prof(state)
    assert ability("SandwalkBondAbility", sandwalk).value_for_player(p).sum == 0.75
    assert ability("FremenWarNameBondAbility", fwn).value_for_player(p).sum == 0.66 * 2
    lone = prof(hand(turn_state, sandwalk, starter("dagger")))
    assert ability("SandwalkBondAbility", sandwalk).value_for_player(lone).sum == 0.0


# ---------------------------------------------------------------------------
# §2.4 Discard for a reward
# ---------------------------------------------------------------------------


def test_arrakis_observer_discard_with_guild_bonus(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    observer = card("arrakis_observer")
    guild = card("corrupt_bureaucrat")  # a Spacing Guild card
    state = hand(turn_state, observer, guild)
    p = prof(state)
    port = ability("ArrakisObserverAgentAbility", observer)
    answer = port.evaluate(p, req(guild))
    assert answer.value == pytest.approx(-1.0 + 1.66 + 0.5 * 2)
    assert answer.response == ((guild.ref,),)
    # V: hand >= 2; the Guild bonus only at placement (with a space).
    assert port.value_for_player(p).sum == pytest.approx(-1.0 + 1.66)
    placed = port.value_for_player(p, (space_entity("arrakeen", p.ctx.board),))
    assert placed.sum == pytest.approx(-1.0 + 1.66 + 1.0)
    single = prof(hand(turn_state, observer))
    assert port.value_for_player(single).sum == 0.0


def test_i_believe_and_engineered_miracle_rewards(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    dagger = starter("dagger")
    p = prof(hand(turn_state, card("i_believe"), dagger))
    believe = ability("IBelieveAgentAbility", card("i_believe"))
    assert believe.evaluate(p, req(dagger)).value == pytest.approx(-1.0 + 1.5 + 0.3)
    miracle = ability("EngineeredMiracleAgentAbility", card("engineered_miracle"))
    assert miracle.evaluate(p, req(dagger)).value == pytest.approx(-1.0 + 1.0)
    # No target info: the hand (this card excluded) is the fallback.
    fallback = miracle.evaluate(p, req())
    assert fallback.response == ((card("i_believe").ref,),)
    empty = prof(hand(turn_state, card("engineered_miracle")))
    assert miracle.evaluate(empty, req()).response is None


# ---------------------------------------------------------------------------
# §2.5 GainedSpice
# ---------------------------------------------------------------------------


def test_gained_spice_reads_turn_gain_or_the_candidate_space(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    gained = with_player(
        turn_state, SEAT, resources=Resources(spice=3), spice_at_turn_start=1
    )
    p = prof(gained)
    assert bc.spice_gained_this_turn(p) == 2
    assert bc.gained_spice(p, (), 2)
    none = prof(turn_state)
    assert not bc.gained_spice(none, (), 2)
    desert = space_entity("deep_desert", none.ctx.board)  # Spice 0 + bonus
    imperial = space_entity("imperial_basin", none.ctx.board)  # Spice 1 + bonus
    expected = desert.int_attr("Spice") + g._space_bonus_spice(none, desert) >= 2
    assert bc.gained_spice(none, (desert,), 2) is expected
    expected = imperial.int_attr("Spice") + g._space_bonus_spice(none, imperial) >= 2
    assert bc.gained_spice(none, (imperial,), 2) is expected


def test_spice_gained_draws_and_troop(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    gained = with_player(
        turn_state, SEAT, resources=Resources(spice=2), spice_at_turn_start=0
    )
    p = prof(gained)
    fwn = card("fremen_war_name")
    troop = ability("FremenWarNameTroopAbility", fwn)
    assert troop.value_for_player(p).sum == 0.9
    assert troop.meets_cost(p)
    assert troop.evaluate(p, Request()).value == 100.0
    draw = ability("SandwalkDrawAbility", card("sandwalk"))
    assert draw.value_for_player(p).sum == pytest.approx(1.5 + 0.3)
    assert draw.value_for_player(prof(turn_state)).sum == 0.0


# ---------------------------------------------------------------------------
# §2.7 UnlockValue
# ---------------------------------------------------------------------------


def test_unlock_value_compares_new_pairs_with_the_best_now(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Fremen 0: Sietch Tabr (City icon, Fremen 2 required) is closed.
    fremen = card("sandwalk")  # Spice Trade icon
    tabr_card = card("i_believe")  # Fremen and City icons
    state = hand(turn_state, fremen, tabr_card)
    p = prof(state)
    values = {"sietch_tabr": 9.0, "imperial_basin": 2.0}

    def pair(_p: Profile, card_: Entity, space_id: str) -> float | None:
        return values.get(space_id, 1.0)

    monkeypatch.setattr(bc, "_pair_value", pair)
    now = bc._card_spaces(p, p.ctx.me, tabr_card.ref)
    assert "sietch_tabr" not in now
    granted = bc._card_spaces(p, bc.grant_ignore_requirements(p.ctx.me), tabr_card.ref)
    assert "sietch_tabr" in granted
    best_now = max(
        values.get(s, 1.0)
        for c in (fremen, tabr_card)
        for s in bc._card_spaces(p, p.ctx.me, c.ref)
    )
    assert bc.unlock_value(p, bc.grant_ignore_requirements) == 9.0 - best_now


def test_unlock_value_is_zero_without_new_pairs_and_inside_a_nested_call(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bc, "_pair_value", lambda _p, c, s: 5.0)
    p = prof(hand(turn_state, starter("dagger")))
    # Dagger already has the Emperor-free spaces it can use; Emperor's icon
    # opens the Emperor spaces for it, so the grant does unlock pairs here.
    assert bc.unlock_value(p, bc.grant_emperor_icon) == 0.0  # 5 - 5
    nothing = prof(hand(turn_state))
    assert bc.unlock_value(nothing, bc.grant_resourceful_icons) == 0.0
    # The re-entrancy flag is the profile's own (never module state).
    p.unlocking = True
    assert bc.unlock_active(p)
    assert not bc.unlock_active(prof(hand(turn_state, starter("dagger"))))
    assert bc.unlock_value(p, bc.grant_ignore_requirements, ()) == 0.0


def test_grants_change_only_the_seat_state(turn_state: GameState) -> None:
    me = turn_state.players[SEAT]
    assert bc.grant_emperor_icon(me).granted_agent_icon_turn == "emperor"
    assert bc.grant_resourceful_icons(me).granted_agent_icon_turn == (
        "landsraad,city,spice_trade"
    )
    assert bc.grant_ignore_requirements(me).ignores_influence_requirements_turn
    assert bc.grant_bene_gesserit_boost(me).bene_gesserit_boost_pending


def test_unlock_value_real_pairs_are_agent_ability_totals(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(hand(turn_state, card("i_believe")))
    tabr = card("i_believe")
    value = bc._pair_value(p, tabr, "sietch_tabr")
    agent = next(a for a in abilities_of(tabr) if isinstance(a, g.AgentAbility))
    space = space_entity("sietch_tabr", p.ctx.board)
    expected = agent.evaluate(p, Request((TargetInfo((space,)),))).value
    assert value == expected


# ---------------------------------------------------------------------------
# §2.8-§2.13 Helpers
# ---------------------------------------------------------------------------


OPTIONS = (
    ("garrison", False),
    ("garrison", True),
    ("conflict", False),
    ("conflict", True),
)


def test_lose_unit_pick_zone_then_troops_first(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    placing = prof(turn_state, estimated_conflict_rank=lambda bonus=0: 2)
    assert bc.lose_unit_pick(placing, OPTIONS) == ("garrison", False)
    out = prof(turn_state, estimated_conflict_rank=lambda bonus=0: None)
    assert bc.lose_unit_pick(out, OPTIONS) == ("conflict", False)
    assert bc.lose_unit_pick(out, (("garrison", True), ("conflict", True))) == (
        "conflict",
        True,
    )
    assert bc.lose_unit_pick(out, (("garrison", True), ("garrison", False))) == (
        "garrison",
        False,
    )
    assert bc.lose_unit_pick(out, ()) is None


def test_spy_move_pick_is_the_best_post(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    posts = [post_entity("arrakeen_post"), post_entity("imperial_basin_post")]
    assert bc.spy_move_pick(prof(turn_state), posts) is posts[-1]


def test_junk_intrigue_pick_prefers_junk(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    good = intrigue("emperor_s_invitation")
    junk = intrigue("twisted_withdrawn")
    for seed in range(5):
        p = prof(turn_state)
        p.rng.seed(seed)
        assert bc.junk_intrigue_pick(p, [good, junk]) == junk
    assert bc.junk_intrigue_pick(prof(turn_state), []) is None


def test_draw_plot_gate(turn_state: GameState, prof: ProfileFactory) -> None:
    # The turn window (T0) with an Agent left opens the gate.
    assert bc.draw_plot_gate(prof(turn_state))
    no_agent = agents(turn_state, 0)
    assert not bc.draw_plot_gate(prof(no_agent))
    assert bc.draw_plot_gate(prof(no_agent, is_final_round=lambda: True))
    many = with_player(
        no_agent,
        SEAT,
        intrigue_cards=tuple(f"intrigue:{n}:0" for n in ("a", "b", "c", "d")),
    )
    assert bc.draw_plot_gate(prof(many))


def test_rank_with_groups_ties_and_cuts_beyond_third(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    assert bc.rank_with(p, {0: 6, 1: 7, 2: 4, 3: 0}) == 2
    assert bc.rank_with(p, {0: 6, 1: 5, 2: 4, 3: 0}) == 1
    assert bc.rank_with(p, {0: 6, 1: 6, 2: 4, 3: 0}) == 2  # tied first -> 2
    assert bc.rank_with(p, {0: 4, 1: 6, 2: 6, 3: 4}) is None  # 3rd tied -> 4
    assert bc.rank_with(p, {0: 1, 1: 6, 2: 5, 3: 4}) is None  # 4th place


def test_retreat_target_codes() -> None:
    assert bc.retreat_target_code(2, True) == 5
    assert bc.retreat_target_of(5) == (2, True)
    assert bc.retreat_target_of(bc.retreat_target_code(3, False)) == (3, False)


def test_command_center_commanders(turn_state: GameState, prof: ProfileFactory) -> None:
    state = units(turn_state, troops_conflict=1, commanders_conflict=1)
    assert bc.command_center_commanders(prof(state)) == 1
    two = units(turn_state, troops_conflict=3)
    assert bc.command_center_commanders(prof(two)) == 0


def test_tenuous_bond_trash_pick_falls_back_to_the_cheapest(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    cards = [card("holy_war"), card("bombast"), card("sandwalk")]
    # acquire_value stub = PersuasionCost: Bombast and Sandwalk tie at 1.
    assert bc.tenuous_bond_trash_pick(prof(turn_state), cards) == cards[1]
    junk = prof(turn_state, card_to_trash=lambda t, m: (t[0], 3.0))
    assert bc.tenuous_bond_trash_pick(junk, cards) == cards[0]


def test_controlled_peek_choice(turn_state: GameState, prof: ProfileFactory) -> None:
    top = starter("dagger")
    rich = with_player(turn_state, SEAT, resources=Resources(solari=1))
    junk = prof(rich, card_to_trash=lambda t, m: (t[0], 1.0))
    assert bc.controlled_peek_choice(junk, top) == bc.DISCARD_TOP
    # 1.5 + 0.3 - 0.25 > 0 with a Solari held.
    assert bc.controlled_peek_choice(prof(rich), top) == bc.DRAW_TOP_FOR_SOLARI
    assert bc.controlled_peek_choice(prof(turn_state), top) == bc.PUT_BACK_TOP


def test_grasp_arrakis_flips_the_cheapest_icon(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    values = {"": 1.0, "wild": 3.0, "crysknife": 2.0}
    p = prof(turn_state, battle_icon_value=lambda icon: Summer(values.get(icon, 2.0)))
    assert bc.grasp_arrakis_flip_pick(p, ["skirmish_wild", "storms_in_the_south"]) == (
        "skirmish_wild"
    )
    assert bc._battle_icon("skirmish_wild") == "wild"


# ---------------------------------------------------------------------------
# §2.11 Acquire-effect bonuses
# ---------------------------------------------------------------------------


def test_acquire_bonuses(turn_state: GameState, prof: ProfileFactory) -> None:
    p = prof(turn_state)
    spy = ability("AcquirePlaceSpyBonusAbility", card("intelligence_training"))
    assert spy.specific_acquire_value(p).sum == 1.66
    taking = ability("AcquireContractBonusAbility", card("mercantile_affairs"))
    assert taking.specific_acquire_value(p).sum == g.contract_value_for_player(p).sum
    real = make_profile(turn_state, SEAT)
    bonus = real.specific_acquire_bonus(card("intelligence_training"))
    assert bonus.sum == pytest.approx(real.spy_value().sum)


# ---------------------------------------------------------------------------
# §3 Imperium cards
# ---------------------------------------------------------------------------


def test_ruthless_leadership_trash_counts_garrison_commanders(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    port = ability("RuthlessLeadershipTrashAbility", card("ruthless_leadership"))
    assert port.value_for_player(prof(turn_state)).sum == 0.0
    garrison = with_player(turn_state, SEAT, commanders_garrison=1)
    assert port.value_for_player(prof(garrison)).sum == 2.75 + 1.0
    assert not port.meets_cost(prof(garrison))
    conflict = with_player(turn_state, SEAT, commanders_conflict=1)
    assert port.meets_cost(prof(conflict))


def test_arrakis_observer_reveal(turn_state: GameState, prof: ProfileFactory) -> None:
    port = ability("ArrakisObserverRevealAbility", card("arrakis_observer"))
    assert port.value_for_player(prof(turn_state)).sum == 0.0
    spying = spies(turn_state, 1)
    p = prof(spying)
    assert port.value_for_player(p).sum == pytest.approx(0.66 * 3 - 1.2)
    spy = spy_entity(POSTS[0], SEAT)
    answer = port.evaluate(p, req(spy))
    assert answer.value == pytest.approx(0.66 * 3 - 1.2)
    assert answer.response == ((spy.ref,),)
    # No target info: the own Spies are the fallback.
    assert port.evaluate(p, req()).response == ((spy.ref,),)
    assert port.evaluate(prof(turn_state), req()).response is None


def test_choam_demands(turn_state: GameState, prof: ProfileFactory) -> None:
    demands = card("choam_demands")
    agent = ability("CHOAMDemandsAgentAbility", demands)
    p = prof(turn_state)
    assert agent.value_for_player(p).sum == 0.0
    owned = own_contracts(turn_state, "contract:bloodlines_spice_refinery")
    p = prof(owned)
    assert agent.value_for_player(p).sum == pytest.approx(0.9 * 2)  # Troops 2
    refinery = contract("spice_refinery")
    answer = agent.evaluate(p, req(refinery))
    assert answer.response == ((refinery.ref,),)
    reveal = ability("CHOAMDemandsRevealAbility", demands)
    assert reveal.value_for_player(p).sum == 0.0
    four = own_contracts(turn_state, "contract:bloodlines_spice_refinery", completed=4)
    total = sum(INFLUENCE.values())
    p4 = prof(four)
    assert reveal.value_for_player(p4).sum == pytest.approx(total)
    assert reveal.evaluate(p4, Request()).value == pytest.approx(total)


def test_command_center(turn_state: GameState, prof: ProfileFactory) -> None:
    center = card("command_center")
    agent = ability("CommandCenterAgentAbility", center)
    assert agent.value_for_player(prof(turn_state)).sum == 0.0
    emperor = with_player(turn_state, SEAT, influence=Influence(emperor=2))
    assert agent.value_for_player(prof(emperor)).sum == 0.9
    reveal = ability("CommandCenterRevealAbility", center)
    two = units(turn_state, troops_conflict=1, commanders_conflict=1)
    assert reveal.value_for_player(prof(two)).sum == 1.5
    assert reveal.evaluate(prof(two), Request()).value == 1.5
    held = prof(two, should_play_retreat_intrigue=lambda name, a, b, n: 0)
    assert reveal.value_for_player(held).sum == 0.0
    assert reveal.evaluate(held, Request()).response is None


def test_corrupt_bureaucrat_contract_gated_by_the_recall(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    port = ability("CorruptBureaucratAgentAbility", card("corrupt_bureaucrat"))
    assert port.value_for_player(prof(turn_state)).sum == 0.0
    recalled = with_player(turn_state, SEAT, spies_recalled_turn=1)
    p = prof(recalled)
    assert port.value_for_player(p).sum == g.contract_value_for_player(p).sum


def test_delivery_logistics_keeps_persuasion_on_ties(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    port = ability("DeliveryLogisticsRevealAbility", card("delivery_logistics"))
    p = prof(turn_state, gain_contract_value=lambda: Summer(0.75))
    contract_value = g.contract_value_for_player(p).sum
    answer = port.evaluate(p, Request())
    if contract_value > 0.75:
        assert answer.response == ((1,),)
    else:
        assert answer.response == ((0,),)
    assert port.value_for_player(p).sum == max(0.75, contract_value)


def test_disruption_tactics_gain_is_the_reward_place_change(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    players = list(turn_state.players)
    for seat, strength in ((0, 6), (1, 7), (2, 4), (3, 0)):
        players[seat] = replace(players[seat], combat_strength=strength)
    players[1] = replace(
        players[1], troops_conflict=2, troops_supply=players[1].troops_supply - 2
    )
    state = with_state(turn_state, players=tuple(players))
    p = prof(state)
    conflict = conflict_entity(state.current_conflict_ids[-1], True)
    expected = _placement_value(p, conflict, 1) - _placement_value(p, conflict, 2)
    assert bc.disruption_gain(p, 1) == pytest.approx(expected)
    port = ability("DisruptionTacticsAgentAbility", card("disruption_tactics"))
    assert port.value_for_player(p).sum == pytest.approx(max(0.0, expected))
    answer = port.evaluate(p, Request((TargetInfo((), (2, 3), 0, 1),)))
    assert answer.response == ((2,),)  # seat 1's troop (code 2) comes first
    weak = with_player(state, SEAT, combat_strength=0)
    assert bc.disruption_gain(prof(weak), 1) == 0.0


def test_elite_forces(turn_state: GameState, prof: ProfileFactory) -> None:
    forces = card("elite_forces")
    port = ability("EliteForcesAgentAbility", forces)
    cheap_emperor = card("bombast")  # Emperor, cost 1
    state = hand(turn_state, forces, cheap_emperor)
    p = prof(state)
    reward = 2.25 + 0.9 + 1.25
    assert port.value_for_player(p).sum == pytest.approx(reward)
    answer = port.evaluate(p, req(cheap_emperor, starter("dagger")))
    assert answer.value == pytest.approx(reward)
    assert answer.response == ((cheap_emperor.ref,),)
    dear = card("imperial_throneship")  # Emperor, cost 7
    dear_state = prof(hand(turn_state, forces, dear))
    assert port.value_for_player(dear_state).sum == 0.0
    junk = prof(
        hand(turn_state, forces, dear),
        card_to_trash=lambda t, m: (t[0], 9.0) if m >= 1.0 and t else (None, m),
    )
    answer = port.evaluate(junk, req(dear))
    assert answer.value == 9.0  # the junk card beats nothing


def test_engineered_miracle_command(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    port = ability("EngineeredMiracleCommandAbility", card("engineered_miracle"))
    p = prof(turn_state, possible_persuasion=lambda: 6)
    best = max(
        card_entity(i).int_attr("PersuasionCost") for i in turn_state.imperium_row
    )
    assert port.value_for_player(p).sum == float(best)
    row = [card_entity(i) for i in turn_state.imperium_row]
    answer = port.evaluate(p, req(*row))
    assert answer.value == float(best)


def test_holy_war_box_has_no_value(turn_state: GameState, prof: ProfileFactory) -> None:
    port = ability("HolyWarAgentAbility", card("holy_war"))
    assert port.value_for_player(prof(turn_state)).sum == 0.0
    assert port.evaluate(prof(turn_state), Request()).value == 100.0


def test_conditional_reveal_gains_and_previews(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    throneship = card("imperial_throneship")
    quash = card("quash_rebellion")
    sandwalk = card("sandwalk")
    base = prof(turn_state)
    trig = ability("ImperialThroneshipTriggeredAbility", throneship)
    assert trig.value_for_player(base).sum == 0.0
    garrison = with_player(turn_state, SEAT, troops_garrison=3, commanders_garrison=1)
    assert trig.value_for_player(prof(garrison)).sum == pytest.approx(0.75 + 0.75)
    assert (
        bc.reveal_preview_persuasion(
            AS + "ImperialThroneshipRevealAbility", throneship, prof(garrison)
        )
        == 3
    )
    assert (
        bc.reveal_preview_persuasion(
            AS + "ImperialThroneshipRevealAbility", throneship, base
        )
        == 2
    )
    q = ability("QuashRebellionTriggeredAbility", quash)
    commander = with_player(turn_state, SEAT, commanders_conflict=1)
    assert q.value_for_player(prof(commander)).sum == 1.5
    assert (
        bc.reveal_preview_persuasion(
            AS + "QuashRebellionRevealAbility", quash, prof(commander)
        )
        == 2
    )
    assert (
        bc.reveal_preview_persuasion(AS + "QuashRebellionRevealAbility", quash, base)
        == 0
    )
    lone = prof(hand(turn_state, sandwalk))
    assert (
        bc.reveal_preview_persuasion(AS + "SandwalkRevealAbility", sandwalk, lone) == 1
    )
    friends = prof(hand(turn_state, sandwalk, card("holy_war")))
    assert (
        bc.reveal_preview_persuasion(AS + "SandwalkRevealAbility", sandwalk, friends)
        == 2
    )


def test_economy_dispatches_the_appstyle_previews(turn_state: GameState) -> None:
    assert economy_module._APPSTYLE_PREVIEW_REVEALS == bc.APPSTYLE_PREVIEW_REVEALS
    assert bc.APPSTYLE_PREVIEW_REVEALS <= economy_module._REVEAL_CLASSES
    sandwalk = card("sandwalk")
    lone = make_profile(hand(turn_state, sandwalk), SEAT)
    friends = make_profile(hand(turn_state, sandwalk, card("holy_war")), SEAT)
    # Holy War prints 1 Persuasion; Sandwalk's bond adds 1 with it.
    assert friends.possible_persuasion() - lone.possible_persuasion() == 1 + 1


def test_command_gated_reveal_effects(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    reached = prof(turn_state, possible_persuasion=lambda: 6)
    missed = prof(turn_state, possible_persuasion=lambda: 5)
    training = ability(
        "IntelligenceTrainingCommandAbility", card("intelligence_training")
    )
    assert training.value_for_player(reached).sum == 1.66
    assert training.value_for_player(missed).sum == 0.0
    pointing = ability("PointingTheWayCommandAbility", card("pointing_the_way"))
    best = g.gain_any_influence_value(reached, 1).sum
    assert pointing.value_for_player(reached).sum == best
    assert pointing.value_for_player(missed).sum == 0.0
    counsel = ability("ShroudedCounselCommandAbility", card("shrouded_counsel"))
    assert counsel.value_for_player(reached).sum == 2.75 + 1.0
    assert counsel.value_for_player(missed).sum == 0.0


def test_ixian_ambassador_needs_two_tiles(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    port = ability("IxianAmbassadorRevealAbility", card("ixian_ambassador"))
    assert port.value_for_player(prof(turn_state)).sum == 0.0
    tiles = own_tiles(turn_state, 2)
    p = prof(tiles)
    assert port.value_for_player(p).sum == g.gain_any_influence_value(p, 1).sum


def test_litany_turn_start(turn_state: GameState, prof: ProfileFactory) -> None:
    litany = card("litany_against_fear")
    p = prof(turn_state)
    port = ability("LitanyTurnStartAbility", litany)
    reveal = g.value_for_reveal_abilities(litany, p).sum
    expected = 1.8 + p.C.CardPlayValueRevealPenalty * reveal
    assert port.evaluate(p, Request()).value == pytest.approx(expected)
    assert p.C.CardPlayValueRevealPenalty == -0.5


def test_mercantile_affairs(effects_state: GameState, prof: ProfileFactory) -> None:
    port = ability("MercantileAffairsAgentAbility", card("mercantile_affairs"))
    assert port.value_for_player(prof(effects_state)).sum == 0.0
    done = with_player(effects_state, SEAT, contracts_completed_turn=1)
    assert port.value_for_player(prof(done)).sum == 2.25
    holding = own_contracts(effects_state, "contract:bloodlines_secrets")
    p = prof(holding)
    secrets = space_entity("secrets", p.ctx.board)
    assert port.value_for_player(p, (secrets,)).sum == 2.25
    arrakeen = space_entity("arrakeen", p.ctx.board)
    assert port.value_for_player(p, (arrakeen,)).sum == 0.0


def test_pointing_the_way_agent(turn_state: GameState, prof: ProfileFactory) -> None:
    port = ability("PointingTheWayAgentAbility", card("pointing_the_way"))
    assert port.value_for_player(prof(turn_state)).sum == 0.0
    worm = with_player(turn_state, SEAT, sandworms_conflict=1)
    assert port.value_for_player(prof(worm)).sum == 2.25
    assert port.evaluate(prof(worm), Request()).value == 100.0


def test_possible_futures(turn_state: GameState, prof: ProfileFactory) -> None:
    futures = card("possible_futures")
    port = ability("PossibleFuturesAgentAbility", futures)
    p = prof(turn_state)
    tracks = [track_entity(f) for f in ("emperor", "bene_gesserit", "fremen")]
    # No Bond: influence 3.0 (BG) vs troops 1.8: influence.
    answer = port.evaluate(p, req(*tracks))
    assert answer == Answer(3.0, ((0,), ("bene_gesserit",)), "Possible Futures")
    best_any = g.gain_any_influence_value(p, 1).sum
    assert port.value_for_player(p).sum == max(best_any, 1.8)
    troops = prof(turn_state, troop_value=lambda n, include=False: 5.0 * n)
    assert port.evaluate(troops, req(*tracks)).response == ((1,),)
    bond = in_play(turn_state, card("shrouded_counsel"))
    pb = prof(bond)
    assert port.evaluate(pb, req(*tracks)).response == ((2,), ("bene_gesserit",))
    assert port.value_for_player(pb).sum == pytest.approx(best_any + 1.8)
    played = port.value_in_pile_for_other_play(
        prof(turn_state), Pile.PLAY_AREA, card("shrouded_counsel")
    )
    assert played.sum == pytest.approx(0.75 * min(best_any, 1.8))


def test_southern_faith(turn_state: GameState, prof: ProfileFactory) -> None:
    faith = card("southern_faith")
    port = ability("SouthernFaithAgentAbility", faith)
    p = prof(turn_state)
    draw = 1.5 + 0.3 if g._has_drawable_card(p) else 0.0
    assert port.evaluate(p, Request()).response == ((0,),)
    assert port.value_for_player(p).sum == pytest.approx(draw)
    bond = prof(in_play(turn_state, card("shrouded_counsel")))
    assert port.evaluate(bond, Request()).response == (
        ((1,),) if 3.0 > draw else ((0,),)
    )
    assert port.value_for_player(bond).sum == pytest.approx(max(draw, 3.0))
    played = port.value_in_pile_for_other_play(
        p, Pile.PLAY_AREA, card("shrouded_counsel")
    )
    assert played.sum == pytest.approx(0.75 * max(0.0, 3.0 - draw))


def test_urgent_shigawire_draw_and_icon_terms(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    shigawire = card("urgent_shigawire")
    port = ability("UrgentShigawireAgentAbility", shigawire)
    seen: list[tuple[str, ...]] = []

    def fake_unlock(
        _p: Profile, grant: bc.Grant, cards: Sequence[Entity] | None = None
    ) -> float:
        assert grant is bc.grant_bene_gesserit_boost
        seen.append(tuple(c.ref for c in cards or ()))
        return 2.0

    monkeypatch.setattr(bc, "unlock_value", fake_unlock)
    alone = prof(hand(turn_state, shigawire, starter("dagger")))
    assert port.value_for_player(alone).sum == 0.0
    counsel = card("shrouded_counsel")
    with_bg = prof(hand(turn_state, shigawire, counsel))
    assert port.value_for_player(with_bg).sum == pytest.approx(0.75 * 1.8 + 0.75 * 2.0)
    assert seen == [(counsel.ref,)]
    monkeypatch.setattr(bc, "unlock_value", lambda *a, **k: -4.0)
    assert port.value_for_player(with_bg).sum == pytest.approx(0.75 * 1.8)
    one_agent = agents(hand(turn_state, shigawire, counsel), 1)
    assert port.value_for_player(prof(one_agent)).sum == 0.0


def test_urgent_shigawire_on_the_real_profile_does_not_recurse(
    turn_state: GameState,
) -> None:
    two = hand(
        turn_state,
        card("urgent_shigawire"),
        card("urgent_shigawire", 1),
        card("shrouded_counsel"),
    )
    p = make_profile(two, SEAT)
    agent = next(
        a
        for a in abilities_of(card("urgent_shigawire"))
        if isinstance(a, g.AgentAbility)
    )
    space = space_entity("arrakeen", p.ctx.board)
    value = agent.value_for_player(p, (space,))
    assert math.isfinite(value.sum)
    assert not bc.unlock_active(p)


# ---------------------------------------------------------------------------
# §4 Intrigue cards
# ---------------------------------------------------------------------------


def _intrigue_port(name: str, card_name: str) -> Any:
    return PORTS[AS + name](intrigue(card_name))


def test_adaptive_tactics(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("AdaptiveTacticsAbility", "adaptive_tactics")
    assert port.evaluate(prof(turn_state), Request()).value == 100.0
    empty = units(turn_state, troops_garrison=12)
    assert port.evaluate(prof(empty), Request()).response is None
    assert port.is_bad_intrigue(prof(turn_state))  # round 1 < 3


def test_battlefield_research(turn_state: GameState, prof: ProfileFactory) -> None:
    combat = _intrigue_port("BattlefieldResearchCombatAbility", "battlefield_research")
    p = prof(turn_state)
    answer = combat.evaluate(p, Request((TargetInfo((), (0, 1, 2), 0, 2),)))
    assert answer.value == 2.2
    assert answer.response == ((0, 1),)
    assert combat.strength_value(p) == 0
    no_tech = prof(turn_state, buy_tech_value=lambda d, a: 0.0)
    assert combat.evaluate(no_tech, Request()).response is None
    endgame = _intrigue_port(
        "BattlefieldResearchEndgameAbility", "battlefield_research"
    )
    for tiles, junk in ((0, True), (2, False), (3, False)):
        state = own_tiles(turn_state, tiles)
        assert endgame.is_bad_intrigue(prof(state)) is junk
        assert endgame.meets_cost(prof(state)) is (tiles >= 3)
    one = own_tiles(turn_state, 1)
    assert endgame.is_bad_intrigue(prof(one, is_climax=lambda: True))
    assert not endgame.is_bad_intrigue(prof(one))


def test_coercive_negotiation(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("CoerciveNegotiationAbility", "coercive_negotiation")
    assert port.evaluate(prof(turn_state), Request()).value == 3.5
    assert not port.meets_cost(prof(turn_state))
    three = with_player(turn_state, SEAT, units_deployed_turn=3)
    assert port.meets_cost(prof(three))


def test_desert_support(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("DesertSupportAbility", "desert_support")
    dry = with_player(turn_state, SEAT, resources=Resources(water=0))
    assert port.strength_value(prof(dry)) == 0
    assert port.is_bad_intrigue(prof(dry))
    wet = with_player(turn_state, SEAT, resources=Resources(water=1))
    assert port.strength_value(prof(wet)) == 5
    assert port.combat_value(prof(wet)) == 5.0


def test_emperors_invitation(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = _intrigue_port("EmperorsInvitationAbility", "emperor_s_invitation")
    monkeypatch.setattr(bc, "unlock_value", lambda *a, **k: 1.0)
    assert port.evaluate(prof(turn_state), Request()).response == ((1,),)
    assert port.evaluate(prof(turn_state), Request()).value == 100.0
    monkeypatch.setattr(bc, "unlock_value", lambda *a, **k: 0.0)
    answer = port.evaluate(prof(turn_state), Request())
    assert answer.response == ((0,),)
    assert answer.value == pytest.approx(1.5 + 0.3)
    only_draw = Request((TargetInfo((), (0,), 0, 1),))
    monkeypatch.setattr(bc, "unlock_value", lambda *a, **k: 1.0)
    assert port.evaluate(prof(turn_state), only_draw).response == ((0,),)


def test_false_orders(effects_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("FalseOrdersAbility", "false_orders")
    p = prof(effects_state)
    assert port.meets_cost(p)
    assert port.evaluate(p, Request()).value == 1.66
    three = spies(effects_state, 3)
    assert port.evaluate(prof(three), Request()).response is None
    assert port.is_bad_intrigue(prof(three))


def test_grasp_arrakis_endgame_needs_two_face_up_cards(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    port = _intrigue_port("GraspArrakisEndgameAbility", "grasp_arrakis")
    state = with_player(won(turn_state, "skirmish_wild"), SEAT, objective_ids=())
    assert not port.meets_cost(prof(state))
    two = with_player(
        won(turn_state, "skirmish_wild", "storms_in_the_south"), SEAT, objective_ids=()
    )
    assert port.meets_cost(prof(two))
    held = with_player(two, SEAT, intrigue_cards=(intrigue("grasp_arrakis").ref,))
    plays = endgame_auto_plays(prof(held))
    assert [type(a).__name__ for _, a in plays] == ["GraspArrakisEndgameAbility"]


def test_honor_guard(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("HonorGuardAbility", "honor_guard")
    assert port.evaluate(prof(turn_state), Request()).response is None
    final = prof(turn_state, is_final_round=lambda: True)
    assert port.evaluate(final, Request()).value == 100.0
    # OPEN-2: the discount makes the Commander recruit pass (2 -> 1 Solari).
    recruit = with_player(
        turn_state, SEAT, commanders_supply=1, resources=Resources(solari=1)
    )
    passes = prof(recruit, troop_value=lambda n, include=False: 0.4 * n)
    assert port.evaluate(passes, Request()).value == 100.0
    always = prof(recruit, troop_value=lambda n, include=False: 0.9 * n)
    assert port.evaluate(always, Request()).response is None  # passes anyway
    garrison = units(turn_state, troops_garrison=5, commanders_garrison=1)
    assert port.is_bad_intrigue(prof(garrison))


def test_insider_information(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = _intrigue_port("InsiderInformationAbility", "insider_information")
    monkeypatch.setattr(bc, "unlock_value", lambda *a, **k: 2.0)
    assert port.evaluate(prof(turn_state), Request()).response == ((1,),)
    monkeypatch.setattr(bc, "unlock_value", lambda *a, **k: 0.0)
    assert port.evaluate(prof(turn_state), Request()).response is None  # no spy
    spying = spies(turn_state, 1)
    spy = spy_entity(POSTS[0], SEAT)
    dagger = starter("dagger")
    request = reqs(info(), info(spy), info(dagger))
    answer = port.evaluate(prof(spying), request)
    assert answer.value == pytest.approx(-1.2 + 1.8)
    assert answer.response == ((0,), (spy.ref,), ())
    junk = prof(spying, card_to_trash=lambda t, m: (t[0], 2.0))
    answer = port.evaluate(junk, request)
    assert answer.value == pytest.approx(-1.2 + 1.8 + 2.0)
    assert answer.response == ((0,), (spy.ref,), (dagger.ref,))


def test_rapid_engineering(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("RapidEngineeringAbility", "rapid_engineering")
    p = prof(turn_state)
    assert port.is_bad_intrigue(p)
    assert port.evaluate(p, Request()).response is None
    tile = Entity(Kind.TECH, "glowglobes")
    dagger = starter("dagger")
    a = prof(turn_state, tech_tile_to_acquire=lambda d, s: tile)
    answer = port.evaluate(a, reqs(info(), info(dagger)))
    assert answer.value == pytest.approx(-1.0 + 2.2)
    assert answer.response == ((0,), (dagger.ref,))
    tiles = own_tiles(turn_state, 3)
    b = prof(tiles)
    answer = port.evaluate(b, Request())
    assert answer.value == pytest.approx(3.0 + 2.5)
    assert answer.response is not None and answer.response[0] == (1,)
    assert set(answer.response[1]) == {"bene_gesserit", "spacing_guild"}


def test_return_the_favor_strength(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("ReturnTheFavorAbility", "return_the_favor")
    state = with_player(
        turn_state, SEAT, influence=Influence(emperor=2, fremen=3, bene_gesserit=1)
    )
    assert port.strength_value(prof(state)) == 1 + 2
    assert port.combat_value(prof(state)) == 1.0  # the CombatValue attribute


def test_ripples_in_the_sand(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("RipplesInTheSandAbility", "ripples_in_the_sand")
    base = port._strength_choice(prof(turn_state)).value
    worm = with_player(turn_state, SEAT, sandworms_conflict=1)
    wv = port._strength_choice(prof(worm)).value
    assert port.evaluate(prof(worm), Request()).value == pytest.approx(wv + 2.25)
    assert port.evaluate(prof(turn_state), Request()).value == pytest.approx(base)
    assert port.is_bad_intrigue(prof(turn_state, is_climax=lambda: True))


def test_sacred_pools(turn_state: GameState, prof: ProfileFactory) -> None:
    plot = _intrigue_port("SacredPoolsPlotAbility", "sacred_pools")
    dagger = starter("dagger")
    # water_value(1) = 1.0 < 3.0: not played without the bonus.
    assert plot.evaluate(prof(turn_state), req(dagger)).response is None
    climax = prof(turn_state, is_climax=lambda: True)
    answer = plot.evaluate(climax, req(dagger))
    assert answer.value == pytest.approx(11.0)
    assert answer.response == ((dagger.ref,),)
    wet = with_player(turn_state, SEAT, resources=Resources(water=3))
    assert (
        plot.evaluate(prof(wet, is_climax=lambda: True), req(dagger)).response is None
    )
    endgame = _intrigue_port("SacredPoolsEndgameAbility", "sacred_pools")
    for water, junk in ((0, True), (2, False), (3, False)):
        state = with_player(turn_state, SEAT, resources=Resources(water=water))
        assert endgame.is_bad_intrigue(prof(state)) is junk
    one = with_player(turn_state, SEAT, resources=Resources(water=1))
    assert endgame.is_bad_intrigue(prof(one, is_climax=lambda: True))


def test_seize_production(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("SeizeProductionAbility", "seize_production")
    p = prof(turn_state)
    assert port.evaluate(p, Request()).response == ((0,),)  # T0 gate, 2 Solari
    commander = with_player(turn_state, SEAT, commanders_conflict=1)
    assert port.evaluate(prof(commander), Request()).response == ((1,),)  # 1.0 > 0.5
    short = with_player(turn_state, SEAT, resources=Resources(solari=6))
    assert port.evaluate(prof(short), Request()).value == 100.0  # 8 - 6 = 2 short
    no_gate = agents(turn_state, 0)
    assert port.evaluate(prof(no_gate), Request()).response is None


def test_sleeper_unit(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("SleeperUnitAbility", "sleeper_unit")
    rich = with_player(turn_state, SEAT, resources=Resources(solari=1))
    assert port.evaluate(prof(rich), Request()).response == ((0,),)
    spying = spies(turn_state, 1)
    spy = spy_entity(POSTS[0], SEAT)
    answer = port.evaluate(prof(spying), reqs(info(options=(1,)), info(spy)))
    assert answer.value == pytest.approx(-1.2 + 1.8)
    assert answer.response == ((1,), (spy.ref,))


def test_tenuous_bond(turn_state: GameState, prof: ProfileFactory) -> None:
    plot = _intrigue_port("TenuousBondPlotAbility", "tenuous_bond")
    state = with_player(turn_state, SEAT, influence=Influence(emperor=1))
    answer = plot.evaluate(prof(state), Request())
    assert answer == Answer(2.5, (("emperor",),), "Tenuous Bond")
    low = prof(state, best_influence_exchange=lambda *a: ("emperor", "fremen", 1.9))
    assert plot.evaluate(low, Request()).response is None
    combat = _intrigue_port("TenuousBondCombatAbility", "tenuous_bond")
    assert not combat.meets_cost(prof(turn_state))
    discard = with_player(turn_state, SEAT, discard_pile=("imperium:bombast:0",))
    assert combat.meets_cost(prof(discard))
    assert combat.strength_value(prof(discard)) == 4


def test_the_strong_survive(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("TheStrongSurviveAbility", "the_strong_survive")
    players = list(turn_state.players)
    players[SEAT] = replace(players[SEAT], combat_strength=14)
    for seat in (1, 2, 3):
        players[seat] = replace(players[seat], combat_strength=2)
    lead = with_state(turn_state, players=tuple(players))
    answer = port.evaluate(prof(lead), reqs(info(options=(0, 1)), info(options=(7, 8))))
    assert answer.value == 150.0
    assert answer.response == ((1,), (7,))
    assert port.combat_value(prof(lead)) == float(port.strength_value(prof(lead)))


def test_withdrawal_agreement(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("WithdrawalAgreementAbility", "withdrawal_agreement")
    three = units(turn_state, troops_conflict=3)
    p = prof(three)
    answer = port.evaluate(p, Request((TargetInfo((), (4, 5, 6, 7), 0, 3),)))
    assert answer.value == g.gain_any_influence_value(p, 1).sum
    assert answer.response == ((4, 5, 6),)
    assert port.evaluate(prof(turn_state), Request()).response is None
    assert port.is_bad_intrigue(prof(turn_state, is_climax=lambda: True))


# ---------------------------------------------------------------------------
# §5 Twisted Intrigue
# ---------------------------------------------------------------------------


def test_twisted_ambitious(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("TwistedAmbitiousAbility", "twisted_ambitious")
    players = list(turn_state.players)
    players[1] = replace(players[1], influence=Influence(bene_gesserit=2))
    led = with_state(turn_state, players=tuple(players))
    rich = prof(led, gain_influence_value=lambda f, n, r=-1, a=False: Summer(5.0 * n))
    answer = port.evaluate(rich, Request())
    assert answer.value == pytest.approx(5.0 - 2.7)
    assert answer.response == (("bene_gesserit",),)
    answer = port.evaluate(prof(led), Request())  # BG 3.0 - 2.7 > 0
    assert answer.value == pytest.approx(3.0 - 2.7)
    assert port.is_bad_intrigue(prof(turn_state))  # nobody leads


def test_twisted_ambitious_small_gain(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    port = _intrigue_port("TwistedAmbitiousAbility", "twisted_ambitious")
    players = list(turn_state.players)
    players[1] = replace(players[1], influence=Influence(fremen=2))
    led = with_state(turn_state, players=tuple(players))
    # Fremen 1.0 - 2.7 < 0: not played.
    assert port.evaluate(prof(led), Request()).response is None


def test_twisted_calculating(reveal_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("TwistedCalculatingAbility", "twisted_calculating")
    state = units(reveal_state, troops_conflict=2, commanders_conflict=1)
    assert port.evaluate(prof(state), Request()).value == pytest.approx(0.25 * 2)
    empty = units(reveal_state, troops_conflict=0)
    assert port.evaluate(prof(empty), Request()).response is None  # k = 0


def test_twisted_controlled(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("TwistedControlledPlotAbility", "twisted_controlled")
    assert port.evaluate(prof(turn_state), Request()).value == pytest.approx(1.8 - 0.25)


def test_twisted_devious(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = _intrigue_port("TwistedDeviousAbility", "twisted_devious")
    dagger = starter("dagger")
    junk = prof(turn_state, card_to_trash=lambda t, m: (t[0], 2.0))
    monkeypatch.setattr(bc, "intrigue_deploy_troops", lambda p, garrison: 0)
    answer = port.evaluate(junk, reqs(info(), info(dagger), info(options=(0, 1, 2))))
    assert answer.response == ((0,), (dagger.ref,))
    monkeypatch.setattr(bc, "intrigue_deploy_troops", lambda p, garrison: 3)
    answer = port.evaluate(junk, reqs(info(), info(dagger), info(options=(0, 1, 2))))
    assert answer == Answer(100.0, ((1,), (0, 1)), "Twisted Devious")


def test_twisted_discerning(turn_state: GameState, prof: ProfileFactory) -> None:
    port = _intrigue_port("TwistedDiscerningAbility", "twisted_discerning")
    dagger = starter("dagger")
    answer = port.evaluate(prof(turn_state), reqs(info(), info(dagger)))
    assert answer.response == ((0,), (dagger.ref,))
    assert answer.value == pytest.approx(-1.0 + 1.8)
    allied = with_player(turn_state, SEAT, alliance_faction_ids=("fremen",))
    assert port.evaluate(prof(allied), reqs(info(), info(dagger))).response == ((1,),)


def test_twisted_insidious_and_unnatural(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    insidious = intrigue("twisted_insidious")
    good = intrigue("emperor_s_invitation")
    twisted = intrigue("twisted_withdrawn")
    port = bc.TwistedInsidiousAbility(insidious)
    state = with_player(turn_state, SEAT, intrigue_cards=(insidious.ref, good.ref))
    answer = port.evaluate(prof(state), Request())
    assert answer.response is None  # 2 spice 1.0 - 1.25 < 0
    rich = prof(state, trash_intrigue_value=lambda: 0.0)
    assert port.evaluate(rich, Request()).response == ((good.ref,),)
    junk = with_player(turn_state, SEAT, intrigue_cards=(insidious.ref, twisted.ref))
    answer = port.evaluate(prof(junk, trash_intrigue_value=lambda: 0.0), Request())
    assert answer.value == pytest.approx(0.5)  # a Twisted gift: 1 spice only
    assert port.is_bad_intrigue(
        prof(with_player(turn_state, SEAT, intrigue_cards=(insidious.ref,)))
    )
    unnatural = PORTS[AS + "TwistedUnnaturalAbility"](intrigue("twisted_unnatural"))
    plain = with_player(
        turn_state, SEAT, intrigue_cards=(intrigue("twisted_unnatural").ref, good.ref)
    )
    answer = unnatural.evaluate(prof(plain), Request())
    assert answer.value == pytest.approx(2.25 - 1.25 + 0.9)
    assert answer.response == ((good.ref,),)


def test_twisted_resourceful(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    port = _intrigue_port("TwistedResourcefulAbility", "twisted_resourceful")
    monkeypatch.setattr(bc, "unlock_value", lambda *a, **k: 0.5)
    assert port.evaluate(prof(turn_state), Request()).value == 100.0
    monkeypatch.setattr(bc, "unlock_value", lambda *a, **k: 0.0)
    assert port.evaluate(prof(turn_state), Request()).response is None


def test_twisted_costs(turn_state: GameState, prof: ProfileFactory) -> None:
    sadistic = _intrigue_port("TwistedSadisticAbility", "twisted_sadistic")
    assert sadistic.evaluate(prof(turn_state), Request()).value == pytest.approx(
        -0.9 + 1.8
    )
    shrewd = _intrigue_port("TwistedShrewdAbility", "twisted_shrewd")
    assert shrewd.evaluate(prof(turn_state), Request()).response is None  # 0.5 - 0.9
    rich = prof(turn_state, spice_value=lambda n: 2.0 * n)
    assert shrewd.evaluate(rich, Request()).value == pytest.approx(2.0 - 0.9)
    sinister = _intrigue_port("TwistedSinisterAbility", "twisted_sinister")
    assert sinister.evaluate(prof(turn_state), Request()).value == pytest.approx(
        2.25 + 0.25 - 1.8
    )
    none = units(turn_state, troops_garrison=1, troops_conflict=0)
    assert sinister.is_bad_intrigue(prof(none))
    withdrawn = _intrigue_port("TwistedWithdrawnAbility", "twisted_withdrawn")
    assert withdrawn.is_bad_intrigue(prof(turn_state))
    assert withdrawn.evaluate(prof(turn_state), Request()).value == 0.0


# ---------------------------------------------------------------------------
# §7 Contract tokens
# ---------------------------------------------------------------------------


def test_token_resource_values(turn_state: GameState, prof: ProfileFactory) -> None:
    p = prof(turn_state)
    secrets = ability("Draw1ContractAbility", contract("secrets"))
    assert secrets.resource_value(p).sum == pytest.approx(0.25 * 2 + 1.5 + 0.3)
    harvest = ability("Harvest3SpyContractAbility", contract("harvest_3"))
    assert harvest.resource_value(p).sum == pytest.approx(0.25 * 2 + 1.66)
    immediate = ability("ImmediateTrashIntrigueContractAbility", contract("immediate"))
    assert immediate.resource_value(p).sum == pytest.approx(2.25 + 1.5 + 0.3 - 1.25)
    assert immediate.specific_acquire_value(p).sum == pytest.approx(
        2.25 + 1.5 + 0.3 - 1.25
    )


def test_harvest_spy_tokens_keep_the_spy_term_in_v(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    harvest = ability("Harvest4SpyContractAbility", contract("harvest_4"))
    arrakeen = space_entity("arrakeen", p.ctx.board)
    assert harvest.value_for_player(p, (arrakeen,)).sum == 0.0
    basin = space_entity("imperial_basin", p.ctx.board)
    spice = basin.int_attr("Spice") + g._space_bonus_spice(p, basin)
    expected = 0.25 * 3 + 1.66 if spice >= 4 else 0.0
    assert harvest.value_for_player(p, (basin,)).sum == pytest.approx(expected)


def test_earn_any_alliance_acquire_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    token = contract("earn_any_alliance")
    port = ability("EarnAllianceContractAbility", token)
    resource = 0.25 * 2 + 0.9 * 2
    factor = max((9.0 - turn_state.round_number) * 0.125, 0.25)
    c = p.C
    far = factor * (c.AcquireContractRewardValueModRatio * resource)
    far += -3.0 * c.AcquireContractHighCouncilModRatio
    assert port.specific_acquire_value(p).sum == pytest.approx(far)
    near = prof(turn_state, has_or_would_gain_alliance=lambda f, n: f == "fremen")
    assert port.specific_acquire_value(near).sum == pytest.approx(
        far + 6.0 * c.AcquireContractHighCouncilModRatio
    )
    assert port.value_for_player(p).sum == 0.0
    assert c.AcquireContractRewardValueModRatio == 0.34
    assert c.AcquireContractHighCouncilModRatio == 0.33


def test_profile_contract_valuation_reads_the_tokens(turn_state: GameState) -> None:
    assert (
        influence_module._APPSTYLE_CONTRACT_ABILITIES == bc.APPSTYLE_CONTRACT_ABILITIES
    )
    p = make_profile(turn_state, SEAT)
    secrets = contract("secrets")
    value = influence_module.contract_resource_value(p, secrets)
    port = ability("Draw1ContractAbility", secrets)
    assert value.sum == pytest.approx(port.resource_value(p).sum)
    alliance = contract("earn_any_alliance")
    acquire = p.contract_acquire_value(alliance)
    resource = influence_module.contract_resource_value(p, alliance).sum
    assert acquire.sum == pytest.approx(bc.earn_alliance_acquire_value(p, resource).sum)
    immediate = contract("immediate")
    assert p.contract_acquire_value(immediate).sum == pytest.approx(
        ability("ImmediateTrashIntrigueContractAbility", immediate)
        .resource_value(p)
        .sum
    )


# ---------------------------------------------------------------------------
# §6 Conflicts and the smoke test
# ---------------------------------------------------------------------------


def test_bloodlines_conflicts_value_with_the_generic_machinery(
    turn_state: GameState,
) -> None:
    p = make_profile(turn_state, SEAT)
    wild = conflict_entity("skirmish_wild", True)
    first = next(
        a for a in abilities_of(wild) if isinstance(a, g.GenericConflictFirstAbility)
    )
    # 1st place: the trash reward (TrashConflictCustomAbility V) and the
    # Wildcard battle icon (x MatchModWildcard).
    reward = g.value_for_rewards_from(p, g.conflict_reward(wild, 1), wild).sum
    icon = p.battle_icon_value("Wildcard").sum
    assert first.value_for_player(p).sum == pytest.approx(reward + icon)
    storms = conflict_entity("storms_in_the_south", True)
    second = next(
        a for a in abilities_of(storms) if isinstance(a, g.GenericConflictSecondAbility)
    )
    expected = p.solari_value(2) + 2 * p.intrigue_value()
    assert second.value_for_player(p).sum == pytest.approx(expected)
    pool = [a.short for a in p.uprising_conflicts()]
    assert pool and not any(".AppStyle." in short for short in pool)  # D28


def _all_bloodlines_entities() -> list[Entity]:
    entities: list[Entity] = []
    for card_id, short in CARD_ARCHETYPES.items():
        if ".AppStyle." in short:
            entities.append(card_entity(f"imperium:{card_id}:0", SEAT))
    for intrigue_id, short in INTRIGUE_ARCHETYPES.items():
        if ".AppStyle." in short:
            entities.append(intrigue_entity(f"intrigue:{intrigue_id}:0", SEAT))
    for contract_id, short in CONTRACT_ARCHETYPES.items():
        if ".AppStyle." in short:
            entities.append(contract_entity(f"contract:{contract_id}", SEAT))
    return entities


@pytest.mark.parametrize("state_name", ["turn_state", "effects_state", "reveal_state"])
def test_every_port_runs_on_the_real_profile(
    request: pytest.FixtureRequest, state_name: str
) -> None:
    state: GameState = request.getfixturevalue(state_name)
    for entity in _all_bloodlines_entities():
        for port in abilities_of(entity):
            if not type(port).__module__.endswith("bloodlines_cards"):
                continue
            p = make_profile(state, SEAT)
            for value in (
                port.value_for_player(p),
                port.value_for_player(p, (space_entity("arrakeen", p.ctx.board),)),
                port.value_in_pile_for_other_play(p, Pile.DECK, card("sandwalk")),
                port.value_in_pile_for_other_play(p, Pile.PLAY_AREA, card("sandwalk")),
                port.specific_acquire_value(p),
            ):
                assert math.isfinite(value.sum)
            answer = port.evaluate(p, Request())
            assert math.isfinite(answer.value)


# ---------------------------------------------------------------------------
# Verifier regressions (independent check of B2, 2026-10-05)
# ---------------------------------------------------------------------------


def test_honor_guard_recruit_rule_is_the_systems_recruit_net(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    """OPEN-2 uses bloodlines-systems.md §1.2 ``RecruitNet``, which plan
    §11.7 extends with Plasteel Blades' extra Skill: Commander 2 Solari ->
    1 with Honor Guard, unit 0.4/0.2 per troop_value, 1 Solari = 0.25."""

    port = _intrigue_port("HonorGuardAbility", "honor_guard")
    recruit = with_player(
        turn_state, SEAT, commanders_supply=1, resources=Resources(solari=1)
    )
    # 0.4 - 0.5 <= 0 now, 0.4 - 0.25 > 0 discounted: the clause fires...
    plain = prof(recruit, troop_value=lambda n, include=False: 0.4 * n)
    assert plain.recruit_net(2) == pytest.approx(0.4 - 0.5)
    assert port.evaluate(plain, Request()).value == 100.0
    # ...but with Plasteel Blades' +0.2 the recruit already passes at 2.
    blades = prof(
        recruit,
        troop_value=lambda n, include=False: 0.4 * n,
        plasteel_extra_skill_value=lambda taken=None: 0.2,
    )
    assert blades.recruit_net(2) == pytest.approx(0.4 + 0.2 - 0.5)
    assert port.evaluate(blades, Request()).response is None
    # 0.2 + 0.1 - 0.5 <= 0, 0.2 + 0.1 - 0.25 > 0: only the Skill term passes.
    weak = prof(recruit, troop_value=lambda n, include=False: 0.2 * n)
    assert port.evaluate(weak, Request()).response is None
    weak_blades = prof(
        recruit,
        troop_value=lambda n, include=False: 0.2 * n,
        plasteel_extra_skill_value=lambda taken=None: 0.1,
    )
    assert port.evaluate(weak_blades, Request()).value == 100.0


def test_disruption_tactics_last_unit_leaves_no_strength(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    """Spec §3.8 writes ``o.Strength - 2``; our rule leaves a seat without
    units at 0 strength [Main pp. 12, 14] (``rules/units.py``). Seat 1 has
    one troop and 7 strength (swords revealed): after the retreat it has 0,
    not 5, so P (4) moves from 3rd to 2nd behind seat 2 (5)."""

    players = list(turn_state.players)
    for seat, strength in ((0, 4), (1, 7), (2, 5), (3, 0)):
        players[seat] = replace(players[seat], combat_strength=strength)
    players[1] = replace(
        players[1], troops_conflict=1, troops_supply=players[1].troops_supply - 1
    )
    state = with_state(turn_state, players=tuple(players))
    p = prof(state)
    conflict = conflict_entity(state.current_conflict_ids[-1], True)
    expected = _placement_value(p, conflict, 2) - _placement_value(p, conflict, 3)
    assert expected != 0.0
    assert bc.disruption_gain(p, 1) == pytest.approx(expected)
    # Two units: the survivor keeps 7 - 2 = 5 and ties seat 2 above P.
    players[1] = replace(
        players[1], troops_conflict=2, troops_supply=players[1].troops_supply - 1
    )
    tied = prof(with_state(turn_state, players=tuple(players)))
    assert bc.disruption_gain(tied, 1) == 0.0


def _strength_intrigue_classes() -> set[str]:
    return {
        name
        for name, cls in PORTS.items()
        if name.startswith(AS) and issubclass(cls, StrengthIntrigueAbility)
    }


def test_intrigue_hand_strength_counts_the_bloodlines_combat_intrigues(
    turn_state: GameState,
) -> None:
    """``IntrigueHandStrengthValue`` = ``OfType<StrengthIntrigueAbility>()``
    (profile-combat.md §5.3); the spec's Combat halves derive from
    ``StrengthIntrigueAbility`` (§4.1), so their printed swords count:
    Desert Support 5 (1 water held), Grasp Arrakis 3, The Strong Survive 3,
    Twisted Controlled 1, Return the Favor 1 + 2 factions at 2+."""

    assert _strength_intrigue_classes() <= combat_module._STRENGTH_INTRIGUE_ABILITIES
    held = (
        "desert_support",
        "grasp_arrakis",
        "the_strong_survive",
        "twisted_controlled",
        "return_the_favor",
        "battlefield_research",
    )
    state = with_player(
        turn_state,
        SEAT,
        intrigue_cards=tuple(intrigue(n).ref for n in held),
        resources=Resources(water=1),
        influence=Influence(emperor=2, fremen=3),
    )
    p = make_profile(state, SEAT)
    assert p.intrigue_hand_strength_value() == 5 + 3 + 3 + 1 + (1 + 2) + 0
    dry = with_player(state, SEAT, resources=Resources(water=0))
    assert make_profile(dry, SEAT).intrigue_hand_strength_value() == 3 + 3 + 1 + 3


def test_harvest_spy_tokens_value_the_spy_at_a_rich_maker_space(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    """D24: the Harvest-Spy tokens keep ``SpyValue`` in their V. Imperial
    Basin prints 1 spice; 3 bonus spice make 4 (Harvest 3+ and 4+ met)."""

    rich = with_state(
        turn_state,
        maker_bonus_spice=(
            ("deep_desert", 0),
            ("hagga_basin", 0),
            ("imperial_basin", 3),
        ),
    )
    p = prof(rich)
    basin = space_entity("imperial_basin", p.ctx.board)
    four = ability("Harvest4SpyContractAbility", contract("harvest_4"))
    assert four.value_for_player(p, (basin,)).sum == pytest.approx(0.25 * 3 + 1.66)
    three = ability("Harvest3SpyContractAbility", contract("harvest_3"))
    assert three.value_for_player(p, (basin,)).sum == pytest.approx(0.25 * 2 + 1.66)
    poor = prof(turn_state)
    assert three.value_for_player(poor, (basin,)).sum == 0.0  # 1 < 3
