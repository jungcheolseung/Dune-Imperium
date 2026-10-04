"""Card-specific ability ports, Imperium cards A–L (abilities/imperium_a.py).

Spec: spec/imperium-a.md. Every test builds a real ``GameState``
(``app_ai.testing``), adjusts the fields a formula reads, and stubs the
``Profile`` methods other areas own with simple linear prices so each expected
value can be checked by hand.
"""

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import replace
from types import MappingProxyType
from typing import Any, ClassVar

import pytest

from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities import imperium_a as ia
from dune_imperium.agents.app_ai.abilities.base import (
    PORTS,
    Ability,
    Pile,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    UnportedAbility,
    abilities_of,
)
from dune_imperium.agents.app_ai.catalog import (
    CARD_ARCHETYPES,
    card_entity,
    contract_entity,
    intrigue_entity,
    space_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile.influence import NO_FACTION
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState

SEAT = 3  # the first player of seed 1
AG = "worm.canis.abilities."

# ---------------------------------------------------------------------------
# Fixtures and stubs
# ---------------------------------------------------------------------------

PRICES = {
    Attr.WATER: 1.0,
    Attr.SPICE: 0.5,
    Attr.SOLARI: 0.25,
    Attr.PERSUASION: 0.75,
    Attr.STRENGTH: 0.66,
    Attr.TROOPS: 0.9,
    Attr.SPECIMEN: 0.1,
}
INFLUENCE = {
    "emperor": 2.0,
    "spacing_guild": 2.5,
    "bene_gesserit": 3.0,
    "fremen": 1.0,
    NO_FACTION: 3.5,
}


def _base_stubs() -> dict[str, Callable[..., Any]]:
    return {
        "resource_value": lambda attr, n, include=False: PRICES[attr] * n,
        "persuasion_value": lambda n: 0.75 * n,
        "solari_value": lambda n: 0.25 * n,
        "spice_value": lambda n: 0.5 * n,
        "water_value": lambda n: 1.0 * n,
        "strength_value": lambda n, include=False: 0.66 * n,
        "troop_value": lambda n, include=False: 0.9 * n,
        "sandworm_value": lambda n, include=False: 3.0 * n,
        "victory_point_value": lambda n: 6.0 * n,
        "card_draw_value": lambda: 1.5,
        "possible_persuasion_gain": lambda: 3,
        "buy_gains": lambda n: 0.1 * n,
        "intrigue_value": lambda: 2.25,
        "discard_value": lambda: -1.0,
        "trash_card_value": lambda: 2.75,
        "trash_intrigue_value": lambda: -1.25,
        "high_council_value": lambda: 15.0,
        "gain_contract_value": lambda: Summer(2.0),
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(
            INFLUENCE[f] * n
        ),
        "has_or_would_gain_alliance": lambda f, n: True,
        "spy_value": lambda: Summer(1.66),
        "recall_spy_value": lambda: Summer(-1.66),
        "card_to_trash": lambda targets, minimum: (None, minimum),
        "discard_order": lambda cards, sg: list(cards),
        "best_influence_exchange": lambda lose, gain, lf=None, gf=None: (
            None,
            None,
            0.0,
        ),
        "recall_spies": lambda spies, take: (list(spies[:take]), 0.0),
        "best_contract": lambda cs, forced: (cs[0], 3.5) if cs else (None, 1.0),
        "is_final_round": lambda: False,
        "is_climax": lambda: False,
    }


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """Seat 3's first ``turn`` decision (round 1, CHOAM on)."""

    return first_decision("turn")


@pytest.fixture(scope="module")
def effects_state() -> GameState:
    """Seat 3's first ``agent_effects``: Reconnaissance at Arrakeen."""

    return first_decision("agent_effects")


ProfileFactory = Callable[..., Profile]


@pytest.fixture
def prof(monkeypatch: pytest.MonkeyPatch) -> ProfileFactory:
    """``prof(state, **overrides) -> Profile``; an override of None keeps the
    real method."""

    def build(
        state: GameState,
        seat: int = SEAT,
        rng_seed: int = 0,
        **overrides: Callable[..., Any] | None,
    ) -> Profile:
        profile = make_profile(state, seat, rng_seed=rng_seed)
        stubs: dict[str, Callable[..., Any] | None] = dict(_base_stubs())
        stubs.update(overrides)
        for name, fn in stubs.items():
            if fn is not None:
                monkeypatch.setattr(profile, name, fn)
        return profile

    return build


def synth(kind: Kind, ref: str, **attrs: object) -> Entity:
    """An entity with a hand-made archetype (isolates a formula)."""

    archetype = Archetype(
        short=f"Test.{ref}",
        kind="test",
        title=None,
        in_uprising=True,
        in_uprising_choam=True,
        attributes=MappingProxyType(dict(attrs)),
    )
    return Entity(kind, ref, archetype, SEAT)


def imperium(name: str, copy: int = 0) -> Entity:
    return card_entity(f"imperium:{name}:{copy}", SEAT)


def starter(name: str, copy: int = 0) -> Entity:
    return card_entity(f"player:{SEAT}:starter:{name}:{copy}", SEAT)


def space(space_id: str) -> Entity:
    return space_entity(space_id, True)


def intrigue(name: str, copy: int = 0) -> Entity:
    return intrigue_entity(f"intrigue:{name}:{copy}", SEAT)


def req(*entities: Entity, options: tuple[int, ...] = ()) -> Request:
    return Request((TargetInfo(tuple(entities), options, 0, 1),))


_ZONES = ("deck", "hand", "discard_pile", "in_play")


def _into_zone(state: GameState, zone: str, cards: Sequence[Entity]) -> GameState:
    """Seat ``SEAT``'s ``zone`` set to ``cards`` (taken out of its other
    zones, so no card instance sits in two zones)."""

    refs = tuple(c.ref for c in cards)
    me = state.players[SEAT]
    changes: dict[str, object] = {
        other: tuple(i for i in getattr(me, other) if i not in refs)
        for other in _ZONES
        if other != zone
    }
    changes[zone] = refs
    return with_player(state, SEAT, **changes)


def hand(state: GameState, *cards: Entity) -> GameState:
    return _into_zone(state, "hand", cards)


def in_play(state: GameState, *cards: Entity) -> GameState:
    return _into_zone(state, "in_play", cards)


def with_spies(state: GameState, *posts: str) -> GameState:
    return with_player(state, SEAT, spy_post_ids=posts, spies_supply=3 - len(posts))


def with_units(
    state: GameState, conflict: int = 0, garrison: int = 0, worms: int = 0
) -> GameState:
    """Troops in the Conflict and garrison (the rest in supply) and worms."""

    return with_player(
        state,
        SEAT,
        troops_conflict=conflict,
        troops_garrison=garrison,
        troops_supply=12 - conflict - garrison,
        sandworms_conflict=worms,
    )


def completed(state: GameState, *contracts: str) -> GameState:
    """Contracts moved out of the shared zones into SEAT's completed ones."""

    taken = set(contracts)
    state = with_state(
        state,
        contract_bank=tuple(c for c in state.contract_bank if c not in taken),
        face_up_contract_ids=tuple(
            c for c in state.face_up_contract_ids if c not in taken
        ),
        sardaukar_contract_ids=tuple(
            c for c in state.sardaukar_contract_ids if c not in taken
        ),
    )
    return with_player(state, SEAT, completed_contract_ids=contracts)


def with_frame(state: GameState, **changes: str | int | bool) -> GameState:
    """``state`` with keys of the top frame's context replaced."""

    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context.update(changes)
    new = replace(frame, context=tuple(sorted(context.items())))
    return with_state(state, decision_stack=(*state.decision_stack[:-1], new))


def set_conflict(state: GameState, conflict_id: str) -> GameState:
    return with_state(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
        ),
        current_conflict_ids=(conflict_id,),
    )


class _BadIntrigue(Ability):
    """An intrigue port whose ``IsBadIntrigue`` holds."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        return True


class _GoodIntrigue(Ability):
    """An intrigue port whose ``IsBadIntrigue`` does not hold."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        return False


@pytest.fixture
def bad_buy_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """Buy Access is junk, Change Allegiances is not (independent of the
    intrigue agent's ports)."""

    monkeypatch.setitem(
        PORTS, AG + "PlayAbilities.Uprising.BuyAccessAbility", _BadIntrigue
    )
    monkeypatch.setitem(
        PORTS, AG + "PlayAbilities.BaseSet.ChangeAllegiancesAbility", _GoodIntrigue
    )


# ---------------------------------------------------------------------------
# Registration and coverage
# ---------------------------------------------------------------------------

# app class (after "worm.canis.abilities.") -> (port, port of the app base)
EXPECTED: dict[str, tuple[type[Ability], type[Ability]]] = {
    "PlayAbilities.Uprising.BeneGesseritOperativeRevealAbility": (
        ia.BeneGesseritOperativeRevealAbility,
        g.RevealAbility,
    ),
    "PlayAbilities.Uprising.CalculusofPowerRevealAbility": (
        ia.CalculusofPowerRevealAbility,
        g.RevealAbility,
    ),
    "PlayAbilities.Uprising.SouthernEldersRevealAbility": (
        ia.SouthernEldersRevealAbility,
        g.RevealAbility,
    ),
    "PlayAbilities.Uprising.DesertPowerRevealAbility": (
        ia.DesertPowerRevealAbility,
        g.RevealAbility,
    ),
    "PlayAbilities.BaseSet.InHighPlacesRevealAbility": (
        ia.InHighPlacesRevealAbility,
        g.RevealAbility,
    ),
    "PlayAbilities.Uprising.InterstellarTradeRevealAbility": (
        ia.InterstellarTradeRevealAbility,
        g.RevealAbility,
    ),
    "TriggeredAbilities.Immortality.BeneGesseritOperativeTriggeredAbility": (
        ia.BeneGesseritOperativeTriggeredAbility,
        g.TriggeredAbility,
    ),
    "TriggeredAbilities.Uprising.SouthernEldersBondAbility": (
        ia.SouthernEldersBondAbility,
        g.BondAbility,
    ),
    "TriggeredAbilities.Uprising.EcologicalTestingStationBondAbility": (
        ia.EcologicalTestingStationBondAbility,
        g.BondAbility,
    ),
    "PlayAbilities.BaseSet.InterstellarTradeAbility": (
        ia.InterstellarTradeAbility,
        g.TriggeredAbility,
    ),
    "TriggeredAbilities.Uprising.InterstellarTradeTriggeredAbility": (
        ia.InterstellarTradeTriggeredAbility,
        g.TriggeredAbility,
    ),
    "TriggeredAbilities.RiseOfIx.ImperialBasharRevealAbility": (
        ia.ImperialBasharRevealAbility,
        g.TriggeredAbility,
    ),
    "ActivatedAbilities.Uprising.BranchingPathAbility": (
        ia.BranchingPathAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.CalculusofPowerEmperorAbility": (
        ia.CalculusofPowerEmperorAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.RiseOfIx.CapturedMentatAgentAbility": (
        ia.CapturedMentatAgentAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.BaseSet.CapturedMentatRevealAbility": (
        ia.CapturedMentatRevealAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.ChaniCleverTacticianAgentAbility": (
        ia.ChaniCleverTacticianAgentAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.ChaniCleverTacticianRevealAbility": (
        ia.ChaniCleverTacticianRevealAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.CorrinthCityAgentAbility": (
        ia.CorrinthCityAgentAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.CorrinthCityRevealAbility": (
        ia.CorrinthCityRevealAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.CovertOperationAbility": (
        ia.CovertOperationAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.DangerousRhetoricAbility": (
        ia.DangerousRhetoricAbility,
        g.GainAnyInfluenceAgentAbility,
    ),
    "ActivatedAbilities.Uprising.DeliveryAgreementAgentAbility": (
        ia.DeliveryAgreementAgentAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.DeliveryAgreementRevealAbility": (
        ia.DeliveryAgreementRevealAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.DemandAttentionAbility": (
        ia.DemandAttentionAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.DesertCallAbility": (
        ia.DesertCallAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.DesertPowerAgentAbility": (
        ia.DesertPowerAgentAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.DesertPowerDeferredAbility": (
        ia.DesertPowerDeferredAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.DoubleAgentAbility": (
        ia.DoubleAgentAbility,
        g.PlaceSpyAbility,
    ),
    "ActivatedAbilities.Uprising.EcologicalTestingStationAbility": (
        ia.EcologicalTestingStationAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.FedaykinStilltentAbility": (
        ia.FedaykinStilltentAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.GuildEnvoyAbility": (
        ia.GuildEnvoyAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.GuildSpyAgentAbility": (
        ia.GuildSpyAgentAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.GuildSpyRevealAbility": (
        ia.GuildSpyRevealAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.BeneGesseritInfluenceTroopAbility": (
        ia.BeneGesseritInfluenceTroopAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.ImperialSpymasterAbility": (
        ia.ImperialSpymasterAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.InHighPlacesPlaceSpyAbility": (
        ia.InHighPlacesPlaceSpyAbility,
        g.PlaceSpyAbility,
    ),
    "ActivatedAbilities.Uprising.InHighPlacesPersuasionAbility": (
        ia.InHighPlacesPersuasionAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.JunctionHeadquartersAbility": (
        ia.JunctionHeadquartersAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.LeadershipAgentAbility": (
        ia.LeadershipAgentAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.LongLiveTheFightersStartAbility": (
        ia.LongLiveTheFightersStartAbility,
        g.DeferredAbility,
    ),
    "ActivatedAbilities.Uprising.LongLiveTheFightersAbility": (
        ia.LongLiveTheFightersAbility,
        g.DeferredAbility,
    ),
}


def test_every_port_is_registered_under_its_app_name_and_base() -> None:
    for name, (cls, base) in EXPECTED.items():
        assert PORTS[AG + name] is cls
        assert cls.APP_CLASS == AG + name
        assert cls.__bases__ == (base,)
    module_ports = {cls for cls in PORTS.values() if cls.__module__ == ia.__name__} - {
        _BadIntrigue,
        _GoodIntrigue,
    }
    assert module_ports == {cls for cls, _ in EXPECTED.values()}
    # The evaluator is not an ability.
    assert not issubclass(ia.LongLiveTheFightersEvaluator, Ability)


def _in_scope(arch: Archetype) -> bool:
    title = arch.title or ""
    return arch.kind in ("imperium", "starter", "reserve") and "A" <= title[:1] <= "L"


def test_every_ability_of_an_a_to_l_card_resolves_to_a_port() -> None:
    scoped = [arch for arch in ARCHETYPES.values() if _in_scope(arch)]
    titles = {arch.title for arch in scoped}
    assert {
        "Bene Gesserit Operative",
        "Captured Mentat",
        "Dagger",
        "Foldspace",
        "Interstellar Trade",
        "Long Live the Fighters",
    } <= titles
    for arch in scoped:
        names = (
            *Entity(Kind.CARD, "x", arch).list_attr("WormAbilityIDs"),
            *Entity(Kind.CARD, "x", arch).list_attr("CustomAbilityIDs"),
        )
        assert names
        for name in names:
            assert name in PORTS, (arch.title, name)
    # The same through our catalog (promos are not in the app's 4p archetypes).
    checked = 0
    for card_id, short in CARD_ARCHETYPES.items():
        catalogued = ARCHETYPES.get(short)
        if catalogued is None or not _in_scope(catalogued):
            continue
        for ability in abilities_of(card_entity(f"imperium:{card_id}:0", SEAT)):
            assert not isinstance(ability, UnportedAbility), (card_id, ability)
        checked += 1
    assert checked == 28  # 4 starters + 24 Imperium cards A–L


def test_any_faction_spelling_matches_the_influence_port() -> None:
    assert ia._ANY_FACTION == NO_FACTION


def test_real_profile_values_every_scoped_card(
    turn_state: GameState, effects_state: GameState
) -> None:
    """Smoke test with the real profile: every hook of every A–L card runs."""

    for state in (turn_state, effects_state):
        p = make_profile(state, SEAT)
        for card_id, short in CARD_ARCHETYPES.items():
            arch = ARCHETYPES.get(short)
            if arch is None or not _in_scope(arch):
                continue
            card = card_entity(f"imperium:{card_id}:0", SEAT)
            for ability in abilities_of(card):
                if type(ability).__module__ != ia.__name__:
                    continue
                for with_entities in ((), (space("deep_desert"),)):
                    v = ability.value_for_player(p, with_entities).sum
                    assert math.isfinite(v), (card_id, ability)
                for pile in (Pile.DECK, Pile.PLAY_AREA):
                    s = ability.value_in_pile_for_other_play(p, pile, card)
                    assert math.isfinite(s.sum)


# ---------------------------------------------------------------------------
# Engine-side flags
# ---------------------------------------------------------------------------

_FLAGS: list[tuple[type[g.DeferredAbility], str, SelectionMode, Timing, bool]] = [
    (
        ia.BranchingPathAbility,
        "branching_path",
        SelectionMode.OPTIONAL,
        Timing.AGENT,
        False,
    ),
    (
        ia.CalculusofPowerEmperorAbility,
        "calculus_of_power",
        SelectionMode.OPTIONAL,
        Timing.REVEAL,
        False,
    ),
    (
        ia.CapturedMentatAgentAbility,
        "captured_mentat",
        SelectionMode.OPTIONAL,
        Timing.AGENT,
        False,
    ),
    (
        ia.CapturedMentatRevealAbility,
        "captured_mentat",
        SelectionMode.OPTIONAL,
        Timing.REVEAL,
        False,
    ),
    (
        ia.ChaniCleverTacticianAgentAbility,
        "chani_clever_tactician",
        SelectionMode.EXPLICIT,
        Timing.AGENT,
        False,
    ),
    (
        ia.ChaniCleverTacticianRevealAbility,
        "chani_clever_tactician",
        SelectionMode.OPTIONAL,
        Timing.REVEAL,
        False,
    ),
    (
        ia.CorrinthCityAgentAbility,
        "corrinth_city",
        SelectionMode.OPTIONAL,
        Timing.AGENT,
        False,
    ),
    (
        ia.CorrinthCityRevealAbility,
        "corrinth_city",
        SelectionMode.EXPLICIT,
        Timing.REVEAL,
        False,
    ),
    (
        ia.CovertOperationAbility,
        "covert_operation",
        SelectionMode.EXPLICIT,
        Timing.AGENT,
        False,
    ),
    (
        ia.DangerousRhetoricAbility,
        "dangerous_rhetoric",
        SelectionMode.EXPLICIT,
        Timing.AGENT,
        False,
    ),
    (
        ia.DeliveryAgreementAgentAbility,
        "delivery_agreement",
        SelectionMode.OPTIONAL,
        Timing.AGENT,
        False,
    ),
    (
        ia.DeliveryAgreementRevealAbility,
        "delivery_agreement",
        SelectionMode.EXPLICIT,
        Timing.REVEAL,
        False,
    ),
    (
        ia.DesertPowerAgentAbility,
        "desert_power",
        SelectionMode.EXPLICIT,
        Timing.AGENT,
        True,
    ),
    (
        ia.DesertPowerDeferredAbility,
        "desert_power",
        SelectionMode.EXPLICIT,
        Timing.REVEAL,
        False,
    ),
    (
        ia.DoubleAgentAbility,
        "double_agent",
        SelectionMode.EXPLICIT,
        Timing.AGENT,
        False,
    ),
    (
        ia.EcologicalTestingStationAbility,
        "ecological_testing_station",
        SelectionMode.OPTIONAL,
        Timing.AGENT,
        False,
    ),
    (
        ia.FedaykinStilltentAbility,
        "fedaykin_stilltent",
        SelectionMode.EXPLICIT,
        Timing.AGENT,
        True,
    ),
    (ia.GuildEnvoyAbility, "guild_envoy", SelectionMode.EXPLICIT, Timing.AGENT, False),
    (ia.GuildSpyAgentAbility, "guild_spy", SelectionMode.OPTIONAL, Timing.AGENT, False),
    (
        ia.GuildSpyRevealAbility,
        "guild_spy",
        SelectionMode.OPTIONAL,
        Timing.REVEAL,
        True,
    ),
    (
        ia.BeneGesseritInfluenceTroopAbility,
        "hidden_missive",
        SelectionMode.EXPLICIT,
        Timing.AGENT,
        True,
    ),
    (
        ia.ImperialSpymasterAbility,
        "imperial_spymaster",
        SelectionMode.EXPLICIT,
        Timing.AGENT,
        False,
    ),
    (
        ia.InHighPlacesPlaceSpyAbility,
        "in_high_places",
        SelectionMode.EXPLICIT,
        Timing.AGENT,
        False,
    ),
    (
        ia.InHighPlacesPersuasionAbility,
        "in_high_places",
        SelectionMode.OPTIONAL,
        Timing.REVEAL,
        False,
    ),
    (
        ia.JunctionHeadquartersAbility,
        "junction_headquarters",
        SelectionMode.OPTIONAL,
        Timing.AGENT,
        False,
    ),
    (
        ia.LeadershipAgentAbility,
        "leadership",
        SelectionMode.EXPLICIT,
        Timing.AGENT,
        False,
    ),
    (
        ia.LongLiveTheFightersStartAbility,
        "long_live_the_fighters",
        SelectionMode.OPTIONAL,
        Timing.AGENT,
        False,
    ),
    (
        ia.LongLiveTheFightersAbility,
        "long_live_the_fighters",
        SelectionMode.OPTIONAL,
        Timing.AGENT,
        False,
    ),
]


@pytest.mark.parametrize(("cls", "card", "mode", "timing", "runs"), _FLAGS)
def test_deferred_flags(
    turn_state: GameState,
    prof: ProfileFactory,
    cls: type[g.DeferredAbility],
    card: str,
    mode: SelectionMode,
    timing: Timing,
    runs: bool,
) -> None:
    ability = cls(imperium(card))
    p = prof(turn_state)
    assert ability.selection_mode(p) == mode
    assert ability.timing == timing
    assert ability.can_run_immediately(p) is runs


def test_other_timings_and_bond_factions() -> None:
    reveal_only = (
        ia.BeneGesseritOperativeRevealAbility,
        ia.CalculusofPowerRevealAbility,
        ia.SouthernEldersRevealAbility,
        ia.DesertPowerRevealAbility,
        ia.InHighPlacesRevealAbility,
        ia.InterstellarTradeRevealAbility,
        ia.BeneGesseritOperativeTriggeredAbility,
        ia.SouthernEldersBondAbility,
        ia.EcologicalTestingStationBondAbility,
        ia.InterstellarTradeAbility,
        ia.InterstellarTradeTriggeredAbility,
        ia.ImperialBasharRevealAbility,
    )
    assert all(cls.timing == Timing.REVEAL for cls in reveal_only)
    assert ia.SouthernEldersBondAbility.bond_faction == "Fremen"
    assert ia.EcologicalTestingStationBondAbility.bond_faction == "Fremen"
    assert ia.BeneGesseritOperativeTriggeredAbility.should_exhaust is False
    assert ia.DesertCallAbility.timing == Timing.AGENT


def test_corrinth_reveal_runs_immediately_once_seated(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.CorrinthCityRevealAbility(imperium("corrinth_city"))
    seated = with_player(turn_state, SEAT, high_council=True)
    assert ability.can_run_immediately(prof(seated))
    assert not ability.can_run_immediately(prof(turn_state))


def test_inherited_deferred_evaluate_uses_the_card_defer_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    covert = ia.CovertOperationAbility(imperium("covert_operation"))
    answer = covert.evaluate(p, Request())
    assert (answer.value, answer.response) == (2.0, ())  # DeferValue 2
    fedaykin = ia.FedaykinStilltentAbility(imperium("fedaykin_stilltent"))
    assert fedaykin.evaluate(p, Request()).value == 1.0  # no DeferValue, Explicit
    # Desert Call: no DeferValue and Optional -> 0, never used.
    call = ia.DesertCallAbility(synth(Kind.CARD, "desert_call"))
    assert call.selection_mode(p) == SelectionMode.OPTIONAL
    assert call.evaluate(p, Request()).value == 0.0
    assert call.value_for_player(p, (space("deep_desert"),)).sum == 0.0


# ---------------------------------------------------------------------------
# Reveal boxes and triggered abilities
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "card", "expected"),
    [
        # 2 Persuasion; the Emperor trash finds no other Emperor card.
        (ia.CalculusofPowerRevealAbility, "calculus_of_power", 1.5),
        # No printed attrs; the reveal choice: max(2 Pers + BuyGains(2), 0).
        (ia.DesertPowerRevealAbility, "desert_power", 1.5 + 0.2),
        # 2 Persuasion; the recall needs two spies.
        (ia.InHighPlacesRevealAbility, "in_high_places", 1.5),
        # 1 Persuasion; the trigger needs two spies.
        (ia.BeneGesseritOperativeRevealAbility, "bene_gesserit_operative", 0.75),
        # No printed attrs, no units, no other Fremen card.
        (ia.SouthernEldersRevealAbility, "chani_clever_tactician", 0.0),
    ],
)
def test_constructor_only_reveal_boxes_value_like_reveal_ability(
    turn_state: GameState,
    prof: ProfileFactory,
    cls: type[g.RevealAbility],
    card: str,
    expected: float,
) -> None:
    p = prof(hand(turn_state))
    owner = imperium(card)
    assert cls(owner).value_for_player(p).sum == pytest.approx(expected)
    assert (
        cls(owner).value_for_player(p).sum
        == g.RevealAbility(owner).value_for_player(p).sum
    )


def test_bene_gesserit_operative_trigger_needs_two_spies(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("bene_gesserit_operative")
    trigger = ia.BeneGesseritOperativeTriggeredAbility(owner)
    one = with_spies(turn_state, "arrakis-deep-desert")
    assert trigger.value_for_player(prof(one)).sum == 0.0
    two = with_spies(turn_state, "arrakis-deep-desert", "arrakis-hagga-basin")
    assert trigger.value_for_player(prof(two)).sum == pytest.approx(1.5)
    # Merged into the card's reveal box as "Reveal Triggered": 0.75 + 1.5.
    reveal = ia.BeneGesseritOperativeRevealAbility(owner)
    assert reveal.value_for_player(prof(two)).sum == pytest.approx(2.25)


def test_interstellar_trade_reveal_adds_persuasion_per_completed_contract(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("interstellar_trade")
    state = completed(turn_state, "contract:harvest_3", "contract:acquire")
    v = ia.InterstellarTradeRevealAbility(owner).value_for_player(prof(state))
    assert v.sum == pytest.approx(0.75 * 2)  # no printed attrs; triggers add 0
    none = ia.InterstellarTradeRevealAbility(owner).value_for_player(prof(turn_state))
    assert none.sum == 0.0
    for cls in (ia.InterstellarTradeAbility, ia.InterstellarTradeTriggeredAbility):
        assert cls(owner).value_for_player(prof(state)).sum == 0.0


def test_southern_elders_bond_counts_another_fremen_card(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("chani_clever_tactician")
    bond = ia.SouthernEldersBondAbility(owner)
    alone = hand(turn_state, owner, starter("dagger"))
    assert bond.value_for_player(prof(alone)).sum == 0.0
    with_fremen = hand(turn_state, owner, imperium("desert_survival"))
    assert bond.value_for_player(prof(with_fremen)).sum == pytest.approx(1.5)
    played = in_play(hand(turn_state, owner), imperium("leadership"))
    assert bond.value_for_player(prof(played)).sum == pytest.approx(1.5)
    # P: the inherited BondAbility synergy.
    s = bond.value_in_pile_for_other_play(
        prof(turn_state), Pile.DECK, imperium("desert_survival")
    )
    assert s.sum == pytest.approx(0.5)


def test_ecological_testing_station_bond_prices_one_water(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("ecological_testing_station")
    bond = ia.EcologicalTestingStationBondAbility(owner)
    assert bond.value_for_player(prof(hand(turn_state, owner))).sum == 0.0
    state = hand(turn_state, owner, imperium("fedaykin_stilltent"))
    assert bond.value_for_player(prof(state)).sum == pytest.approx(1.0)


def test_imperial_bashar_counts_other_hand_cards_with_strength(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("leadership")  # Strength 1, excluded as the owner
    bashar = ia.ImperialBasharRevealAbility(owner)
    state = hand(
        turn_state,
        owner,
        starter("dagger"),
        starter("convincing_argument"),
        imperium("maula_pistol"),
    )
    assert bashar.value_for_player(prof(state)).sum == pytest.approx(0.66 * 2)
    assert bashar.value_for_player(prof(hand(turn_state, owner))).sum == 0.0


# ---------------------------------------------------------------------------
# Branching Path and Junction Headquarters (intrigue trades)
# ---------------------------------------------------------------------------


def test_branching_path_value_needs_intrigue_and_alliance(
    turn_state: GameState, prof: ProfileFactory, bad_buy_access: None
) -> None:
    ability = ia.BranchingPathAbility(imperium("branching_path"))
    assert ability.value_for_player(prof(turn_state)).sum == 0.0  # no intrigue
    good = with_player(
        turn_state, SEAT, intrigue_cards=("intrigue:change_allegiances:0",)
    )
    # Trash Intrigue (-1.25) + Intrigue (2.25) + 2 Spice (1.0).
    assert ability.value_for_player(prof(good)).sum == pytest.approx(2.0)
    bad = with_player(
        turn_state,
        SEAT,
        intrigue_cards=("intrigue:change_allegiances:0", "intrigue:buy_access:0"),
    )
    assert ability.value_for_player(prof(bad)).sum == pytest.approx(3.25)
    no_alliance = prof(good, has_or_would_gain_alliance=lambda f, n: False)
    assert ability.value_for_player(no_alliance).sum == 0.0


def test_branching_path_bene_gesserit_space_supplies_the_influence(
    turn_state: GameState, prof: ProfileFactory, bad_buy_access: None
) -> None:
    calls: list[tuple[str, int]] = []

    def alliance(faction: str, amount: int) -> bool:
        calls.append((faction, amount))
        return amount == 1

    good = with_player(
        turn_state, SEAT, intrigue_cards=("intrigue:change_allegiances:0",)
    )
    ability = ia.BranchingPathAbility(imperium("branching_path"))
    p = prof(good, has_or_would_gain_alliance=alliance)
    assert ability.value_for_player(p, (space("espionage"),)).sum == pytest.approx(2.0)
    assert ability.value_for_player(p, (space("arrakeen"),)).sum == 0.0
    assert ability.value_for_player(p, ()).sum == 0.0
    assert calls == [("bene_gesserit", 1), ("bene_gesserit", 0), ("bene_gesserit", 0)]


@pytest.mark.parametrize(
    "cls", [ia.BranchingPathAbility, ia.JunctionHeadquartersAbility]
)
def test_intrigue_trade_evaluate_prefers_a_bad_intrigue(
    turn_state: GameState,
    prof: ProfileFactory,
    bad_buy_access: None,
    cls: type[g.DeferredAbility],
) -> None:
    ability = cls(imperium("branching_path"))
    good, bad = intrigue("change_allegiances"), intrigue("buy_access")
    for seed in range(4):
        answer = ability.evaluate(prof(turn_state, rng_seed=seed), req(good, bad))
        assert answer.value == 5.0
        assert answer.response == ((bad.ref,),)
    empty = ability.evaluate(prof(turn_state), req())
    assert (empty.value, empty.response) == (0.0, None)


def test_intrigue_trade_evaluate_takes_the_first_shuffled_good_one(
    turn_state: GameState, prof: ProfileFactory, bad_buy_access: None
) -> None:
    ability = ia.BranchingPathAbility(imperium("branching_path"))
    cards = [intrigue("change_allegiances", 0), intrigue("change_allegiances", 1)]
    for seed in range(4):
        expected = list(cards)
        random.Random(seed).shuffle(expected)
        answer = ability.evaluate(prof(turn_state, rng_seed=seed), req(*cards))
        assert answer.value == 1.0
        assert answer.response == ((expected[0].ref,),)


def test_junction_headquarters_value_needs_the_full_cost(
    turn_state: GameState, prof: ProfileFactory, bad_buy_access: None
) -> None:
    ability = ia.JunctionHeadquartersAbility(imperium("junction_headquarters"))
    ready = with_player(
        turn_state,
        SEAT,
        alliance_faction_ids=("spacing_guild",),
        resources=Resources(spice=2),
        intrigue_cards=("intrigue:change_allegiances:0",),
    )
    assert ability.meets_cost(prof(ready))
    # Trash Intrigue -1.25, Pay 2 Spice -1.0, VP 6.0.
    assert ability.value_for_player(prof(ready)).sum == pytest.approx(3.75)
    bad = with_player(
        ready,
        SEAT,
        intrigue_cards=("intrigue:change_allegiances:0", "intrigue:buy_access:0"),
    )
    assert ability.value_for_player(prof(bad)).sum == pytest.approx(5.0)
    for change in (
        {"alliance_faction_ids": ()},
        {"resources": Resources(spice=1)},
        {"intrigue_cards": ()},
    ):
        short = with_player(ready, SEAT, **change)
        assert not ability.meets_cost(prof(short))
        assert ability.value_for_player(prof(short)).sum == 0.0


# ---------------------------------------------------------------------------
# Calculus of Power
# ---------------------------------------------------------------------------


def test_calculus_of_power_value_counts_cheap_emperor_cards_in_hand_and_play(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("calculus_of_power")
    ability = ia.CalculusofPowerEmperorAbility(owner)
    only_owner = in_play(turn_state, owner)
    assert ability.value_for_player(prof(only_owner)).sum == 0.0
    dear = in_play(turn_state, owner, imperium("corrinth_city"))  # cost 6
    assert ability.value_for_player(prof(dear)).sum == 0.0
    cheap_in_hand = hand(dear, imperium("imperial_spymaster"))  # cost 2
    # TrashCardValue (a gain) + 3 Strength.
    assert ability.value_for_player(prof(cheap_in_hand)).sum == pytest.approx(
        2.75 + 1.98
    )
    junk = prof(dear, card_to_trash=lambda cs, m: (cs[0], 10.0))
    assert ability.value_for_player(junk).sum == pytest.approx(2.75 + 1.98)


def test_calculus_of_power_evaluate_picks_a_cheap_target(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.CalculusofPowerEmperorAbility(imperium("calculus_of_power"))
    corrinth, spymaster = imperium("corrinth_city"), imperium("imperial_spymaster")
    answer = ability.evaluate(prof(turn_state), req(corrinth, spymaster))
    assert answer.value == pytest.approx(0.0 + 1.98)  # GetCardToTrash value 0.0
    assert answer.response == ((spymaster.ref,),)
    none = ability.evaluate(prof(turn_state), req(corrinth))
    assert (none.value, none.response) == (0.0, None)
    junk = prof(turn_state, card_to_trash=lambda cs, m: (cs[0], 10.5))
    answer = ability.evaluate(junk, req(corrinth))
    assert answer.value == pytest.approx(10.5 + 1.98)
    assert answer.response == ((corrinth.ref,),)


# ---------------------------------------------------------------------------
# Captured Mentat
# ---------------------------------------------------------------------------


def test_captured_mentat_agent(turn_state: GameState, prof: ProfileFactory) -> None:
    owner = imperium("captured_mentat")
    ability = ia.CapturedMentatAgentAbility(owner)
    total = -1.0 + 1.5 + 2.25 + 0.3
    assert ability.value_for_player(prof(hand(turn_state, owner))).sum == 0.0
    two = hand(turn_state, owner, starter("dagger"))
    assert ability.value_for_player(prof(two)).sum == pytest.approx(total)
    seen: list[bool] = []

    def order(cards: Sequence[Entity], sg: bool) -> list[Entity]:
        seen.append(sg)
        return list(reversed(cards))

    dagger, argument = starter("dagger"), starter("convincing_argument")
    answer = ability.evaluate(
        prof(turn_state, discard_order=order), req(dagger, argument)
    )
    assert answer.value == pytest.approx(total)
    assert answer.response == ((argument.ref,),)
    assert seen == [False]
    empty = ability.evaluate(prof(turn_state), req())
    assert (empty.value, empty.response) == (0.0, None)


def test_captured_mentat_reveal_value_is_the_floored_best_exchange(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.CapturedMentatRevealAbility(imperium("captured_mentat"))
    calls: list[tuple[object, ...]] = []

    def exchange(
        lose: int, gain: int, lf: object = None, gf: object = None
    ) -> tuple[str | None, str | None, float]:
        calls.append((lose, gain, lf, gf))
        return ("emperor", "fremen", 2.5)

    assert (
        ability.value_for_player(prof(turn_state, best_influence_exchange=exchange)).sum
        == 2.5
    )
    assert calls == [(-1, 1, None, None)]
    negative = prof(turn_state, best_influence_exchange=lambda *a: (None, None, -1.0))
    assert ability.value_for_player(negative).sum == 0.0


def test_captured_mentat_reveal_never_swaps(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    ability = ia.CapturedMentatRevealAbility(imperium("captured_mentat"))
    tracks = tuple(track_entity(f) for f in ("emperor", "fremen"))
    request = Request((TargetInfo(tracks), TargetInfo(tracks)))
    p = prof(turn_state, best_influence_exchange=lambda *a: ("emperor", "fremen", 2.5))
    answer = ability.evaluate(p, request)
    assert (answer.value, answer.response) == (0.0, None)  # no +2 info
    assert ability.evaluate(p, Request()).response is None  # no lose info
    # The app's dead swap path, reached only if Targets put +2 on the gain info.
    monkeypatch.setattr(
        ia.CapturedMentatRevealAbility, "TARGET_INFLUENCE_DELTAS", (-1, 2)
    )
    answer = ability.evaluate(p, request)
    assert answer.value == 2.5
    assert answer.response == (("emperor",), ("fremen",))
    nothing = prof(turn_state, best_influence_exchange=lambda *a: (None, None, 0.0))
    assert ability.evaluate(nothing, request).response is None


# ---------------------------------------------------------------------------
# Chani, Clever Tactician
# ---------------------------------------------------------------------------


def test_chani_agent_counts_conflict_and_garrison_units(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.ChaniCleverTacticianAgentAbility(imperium("chani_clever_tactician"))
    three = with_units(turn_state, conflict=1, garrison=2)
    assert ability.value_for_player(prof(three)).sum == 2.25
    worm = with_units(turn_state, garrison=2, worms=1)
    assert ability.value_for_player(prof(worm)).sum == 2.25
    two = with_units(turn_state, conflict=0, garrison=2)
    assert ability.value_for_player(prof(two)).sum == 0.0
    answer = ability.evaluate(prof(two), Request())
    assert (answer.value, answer.response) == (2.25, ())


@pytest.mark.parametrize(
    ("troops", "worms", "final", "expected"),
    [
        (2, 1, False, 1.8),  # 3 units, 2 troops
        (2, 0, False, 0.0),  # 2 units
        (1, 2, False, 0.0),  # 3 units, 1 troop
        (3, 0, True, 0.0),  # final round
    ],
)
def test_chani_reveal_retreats_two_troops(
    turn_state: GameState,
    prof: ProfileFactory,
    troops: int,
    worms: int,
    final: bool,
    expected: float,
) -> None:
    ability = ia.ChaniCleverTacticianRevealAbility(imperium("chani_clever_tactician"))
    state = with_units(turn_state, conflict=troops, worms=worms)
    p = prof(state, is_final_round=lambda: final)
    assert ability.value_for_player(p).sum == pytest.approx(expected)
    answer = ability.evaluate(p, Request())
    assert answer.value == pytest.approx(expected)
    assert answer.response == (() if expected else None)


# ---------------------------------------------------------------------------
# Corrinth City
# ---------------------------------------------------------------------------


def test_corrinth_city_agent(turn_state: GameState, prof: ProfileFactory) -> None:
    owner = imperium("corrinth_city")
    ability = ia.CorrinthCityAgentAbility(owner)
    total = -2.0 - 1.25 + 6.0
    two = hand(turn_state, owner, starter("dagger"))
    assert ability.value_for_player(prof(two)).sum == 0.0
    three = hand(turn_state, owner, starter("dagger"), starter("diplomacy"))
    assert ability.value_for_player(prof(three)).sum == pytest.approx(total)
    cards = (starter("dagger"), starter("diplomacy"), starter("dagger", 1))
    answer = ability.evaluate(prof(turn_state), req(*cards))
    assert answer.value == pytest.approx(total)
    assert answer.response == ((cards[0].ref, cards[1].ref),)
    one = ability.evaluate(prof(turn_state), req(cards[0]))
    assert (one.value, one.response) == (0.0, None)


def test_corrinth_city_reveal_value_tests_the_seat_inverted(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.CorrinthCityRevealAbility(imperium("corrinth_city"))
    assert ability.value_for_player(prof(turn_state)).sum == pytest.approx(1.25)
    seated = with_player(turn_state, SEAT, high_council=True)
    assert ability.value_for_player(prof(seated)).sum == pytest.approx(-1.25 + 15.0)
    cheap = prof(seated, high_council_value=lambda: 1.0)
    assert ability.value_for_player(cheap).sum == pytest.approx(1.25)


def test_corrinth_city_reveal_evaluate(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.CorrinthCityRevealAbility(imperium("corrinth_city"))
    poor = with_player(turn_state, SEAT, resources=Resources(solari=4))
    assert ability.evaluate(prof(poor), Request()).response == ((0,),)
    rich = with_player(turn_state, SEAT, resources=Resources(solari=5))
    answer = ability.evaluate(prof(rich), Request())
    assert answer.value == pytest.approx(13.75)
    assert answer.response == ((1,),)
    # A seated AI is offered the seat too (no seat test in E).
    seated = with_player(rich, SEAT, high_council=True)
    assert ability.evaluate(prof(seated), Request()).response == ((1,),)
    # Option 1 must be strictly better: a tie keeps option 0.
    tie = ability.evaluate(prof(rich, high_council_value=lambda: 2.5), Request())
    assert (tie.value, tie.response) == (1.25, ((0,),))


# ---------------------------------------------------------------------------
# Covert Operation, Dangerous Rhetoric
# ---------------------------------------------------------------------------


def test_covert_operation_scales_the_share_of_opponents_holding_cards(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.CovertOperationAbility(imperium("covert_operation"))
    assert ability.value_for_player(prof(turn_state)).sum == pytest.approx(2.5)
    state = with_player(turn_state, 0, hand=())
    state = with_player(state, 1, hand=())
    assert ability.value_for_player(prof(state)).sum == pytest.approx(2.5 / 3)


def test_dangerous_rhetoric_is_gain_any_influence(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.DangerousRhetoricAbility(imperium("dangerous_rhetoric"))
    p = prof(turn_state)
    tracks = [track_entity(f) for f in ("emperor", "bene_gesserit", "fremen")]
    answer = ability.evaluate(p, req(*tracks))
    assert (answer.value, answer.response) == (103.0, (("bene_gesserit",),))
    assert ability.value_for_player(p).sum == pytest.approx(3.0)  # best faction


# ---------------------------------------------------------------------------
# Delivery Agreement
# ---------------------------------------------------------------------------


def test_delivery_agreement_agent(turn_state: GameState, prof: ProfileFactory) -> None:
    owner = imperium("delivery_agreement")
    ability = ia.DeliveryAgreementAgentAbility(owner)
    assert ability.value_for_player(prof(hand(turn_state, owner))).sum == 0.0
    two = hand(turn_state, owner, starter("dagger"))
    assert ability.value_for_player(prof(two)).sum == pytest.approx(1.0)
    answer = ability.evaluate(prof(turn_state), req(starter("dagger")))
    assert (answer.value, answer.response) == (1.0, ((starter("dagger").ref,),))
    assert ability.evaluate(prof(turn_state), req()).response is None
    contracts = (
        contract_entity("contract:harvest_3"),
        contract_entity("contract:acquire"),
    )
    leaf = ability.evaluate_contract(prof(turn_state), req(*contracts))
    assert (leaf.value, leaf.response) == (3.5, (("contract:harvest_3",),))


def test_delivery_agreement_reveal(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ia.DeliveryAgreementRevealAbility(imperium("delivery_agreement"))
    assert ability.spice_amount == 1
    assert ability.value_for_player(prof(turn_state)).sum == pytest.approx(0.5)
    answer = ability.evaluate(prof(turn_state), Request())
    assert (answer.value, answer.response) == (0.5, ((0,),))
    four = completed(
        turn_state,
        "contract:harvest_3",
        "contract:acquire",
        "contract:immediate",
        "contract:harvest_4",
    )
    assert ability.value_for_player(prof(four)).sum == pytest.approx(6.0)
    answer = ability.evaluate(prof(four), Request())
    assert (answer.value, answer.response) == (6.0, ((1,),))
    cheap_vp = prof(four, victory_point_value=lambda n: 0.25 * n)
    answer = ability.evaluate(cheap_vp, Request())
    assert (answer.value, answer.response) == (0.5, ((0,),))
    # Tie (VP(1) == Spice(1) == 0.5): the VP option is offered first and
    # sticks; Spice replaces it only when strictly greater (@0x4d02de0).
    tie = prof(four, victory_point_value=lambda n: 0.5 * n)
    answer = ability.evaluate(tie, Request())
    assert (answer.value, answer.response) == (0.5, ((1,),))

    class _ThreeSpice(ia.DeliveryAgreementRevealAbility):
        spice_amount: ClassVar[int] = 3  # as Priority Contracts' subclass would

    three = _ThreeSpice(imperium("priority_contracts"))
    assert three.value_for_player(prof(turn_state)).sum == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# Demand Attention, Desert Power, Double Agent
# ---------------------------------------------------------------------------


def test_demand_attention_space_faction(
    effects_state: GameState,
    turn_state: GameState,
    prof: ProfileFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ability = ia.DemandAttentionAbility(synth(Kind.CARD, "demand_attention"))
    assert ability.space_faction(prof(turn_state)) == NO_FACTION  # no Agent turn
    assert ability.space_faction(prof(effects_state)) == NO_FACTION  # Arrakeen
    espionage = with_frame(effects_state, space_id="espionage")
    assert ability.space_faction(prof(espionage)) == "bene_gesserit"
    two = synth(Kind.SPACE, "two", FactionInfluence={"Emperor": 1, "Fremen": 1})
    monkeypatch.setattr(ia, "_active_space", lambda p: two)
    assert ability.space_faction(prof(espionage)) == NO_FACTION


def test_demand_attention_evaluate(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.DemandAttentionAbility(synth(Kind.CARD, "demand_attention"))
    espionage = with_frame(effects_state, space_id="espionage")
    answer = ability.evaluate(prof(espionage), Request())
    assert (answer.value, answer.response) == (4.0, ((1,),))  # -2 + 2 x 3.0
    dear = prof(espionage, spice_value=lambda n: 2.0 * n)
    answer = ability.evaluate(dear, Request())
    assert (answer.value, answer.response) == (3.0, ((0,),))
    assert ability.value_for_player(prof(espionage)).sum == 0.0


def test_desert_power_agent(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ia.DesertPowerAgentAbility(imperium("desert_power"))
    p = prof(turn_state)
    assert ability.value_for_player(p, (space("deep_desert"),)).sum == 1.0
    assert ability.value_for_player(p, (space("arrakeen"),)).sum == 0.0
    assert ability.value_for_player(p, ()).sum == 0.0
    assert ability.evaluate(p, Request()).value == 100.0
    # Merged into the card's agent box per candidate space.
    box = g.AgentAbility(imperium("desert_power"))
    maker = box.value_for_player(p, (space("hagga_basin"),)).sum
    plain = box.value_for_player(p, (space("arrakeen"),)).sum
    assert maker - plain == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("water", "hooks", "conflict", "wall", "worm_value", "expected"),
    [
        (1, True, None, True, 3.0, (2.0, 1)),  # worm -1 + 3 beats 1.5 + 0.2
        (0, True, None, True, 3.0, (1.7, 0)),  # no water
        (1, False, None, True, 3.0, (1.7, 0)),  # no maker hooks
        (1, True, "battle_for_arrakeen", True, 3.0, (1.7, 0)),  # behind the wall
        (1, True, "battle_for_arrakeen", False, 3.0, (2.0, 1)),  # wall blown
        (1, True, None, True, 2.0, (1.7, 0)),  # worm 1.0 loses
    ],
)
def test_desert_power_reveal_choice(
    turn_state: GameState,
    prof: ProfileFactory,
    water: int,
    hooks: bool,
    conflict: str | None,
    wall: bool,
    worm_value: float,
    expected: tuple[float, int],
) -> None:
    ability = ia.DesertPowerDeferredAbility(imperium("desert_power"))
    state = with_player(
        turn_state, SEAT, resources=Resources(water=water), maker_hooks=hooks
    )
    if conflict is not None:
        state = set_conflict(state, conflict)
    state = with_state(state, shield_wall_present=wall)
    p = prof(state, sandworm_value=lambda n, include=False: worm_value * n)
    answer = ability.evaluate(p, Request())
    assert answer.value == pytest.approx(expected[0])
    assert answer.response == ((expected[1],),)
    assert ability.value_for_player(p).sum == pytest.approx(expected[0])


def test_desert_power_reveal_tie_keeps_the_worm(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    """``DesertPowerDeferredAbility::Evaluate`` @0x4d08e30: the worm option
    (1) is offered first and sticks; option 0 wins only when strictly greater.
    The values are exact in binary so the tie is a real one: Water(-1) +
    Sandworm(1) = -1 + 3 = 2.0 and Persuasion(2) + BuyGains(2) = 1.5 + 0.5."""

    ability = ia.DesertPowerDeferredAbility(imperium("desert_power"))
    state = with_player(
        turn_state, SEAT, resources=Resources(water=1), maker_hooks=True
    )
    p = prof(state, buy_gains=lambda n: 0.25 * n)
    worm = p.water_value(-1) + p.sandworm_value(1, False)
    assert worm == p.persuasion_value(2) + p.buy_gains(2) == 2.0
    answer = ability.evaluate(p, Request())
    assert (answer.value, answer.response) == (2.0, ((1,),))
    assert ability.value_for_player(p).sum == 2.0


def test_double_agent_halves_the_spy_value_at_placement_only(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.DoubleAgentAbility(imperium("double_agent"))
    p = prof(turn_state)
    assert ability.value_for_player(p, (space("arrakeen"),)).sum == pytest.approx(0.83)
    assert ability.evaluate(p, Request()).value == 1.66
    assert (ability.post_filter, ability.auto_select_post) == (3, True)
    assert ability.allow_multiple_spies is True


# ---------------------------------------------------------------------------
# Ecological Testing Station, Fedaykin Stilltent
# ---------------------------------------------------------------------------


def test_ecological_testing_station_value_and_evaluate_differ(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.EcologicalTestingStationAbility(imperium("ecological_testing_station"))
    p = prof(turn_state)  # water 1, so 2 Water cannot be paid at Arrakeen
    assert ability.value_for_player(p, (space("arrakeen"),)).sum == 0.0
    # Without a space: -2 x Water(1), 2 draws, BuyGains(2 x 3).
    assert ability.value_for_player(p, ()).sum == pytest.approx(-2.0 + 3.0 + 0.6)
    wet = prof(with_player(turn_state, SEAT, resources=Resources(water=2)))
    assert ability.value_for_player(wet, (space("arrakeen"),)).sum == pytest.approx(1.6)
    # E: Water(-2), 2 draws, BuyGains(3) (one card's worth).
    answer = ability.evaluate(p, Request())
    assert answer.value == pytest.approx(1.3)
    assert answer.response == ()
    # A non-linear water price separates the two water formulas (§2.16, §4
    # item 8): V adds GetWaterValue(1) x -2.0 (@0x4d0d930, f64=-2.0) = -2.0;
    # E adds GetWaterValue(-2) (@0x4d0dcb0, mov esi,0xfffffffe) = -3.0.
    bent = prof(turn_state, water_value=lambda n: 1.0 * n if n > 0 else 1.5 * n)
    v = ability.value_for_player(bent, ())
    assert v.sum == pytest.approx(-2.0 + 3.0 + 0.6)
    answer = ability.evaluate(bent, Request())
    assert answer.value == pytest.approx(-3.0 + 3.0 + 0.3)


def test_fedaykin_stilltent_prices_a_maker_space_as_one_spice(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.FedaykinStilltentAbility(imperium("fedaykin_stilltent"))
    p = prof(turn_state)
    assert ability.value_for_player(p, (space("hagga_basin"),)).sum == 0.5
    assert ability.value_for_player(p, (space("arrakeen"),)).sum == 0.0


# ---------------------------------------------------------------------------
# Guild Envoy, Guild Spy
# ---------------------------------------------------------------------------


def _recording_order(
    seen: list[bool],
) -> Callable[[Sequence[Entity], bool], list[Entity]]:
    def order(cards: Sequence[Entity], sg: bool) -> list[Entity]:
        seen.append(sg)
        return list(cards)

    return order


def test_guild_envoy_value(turn_state: GameState, prof: ProfileFactory) -> None:
    owner = imperium("guild_envoy")
    ability = ia.GuildEnvoyAbility(owner)
    seen: list[bool] = []
    at = (space("arrakeen"),)
    sg_first = hand(turn_state, owner, imperium("guild_spy"), starter("dagger"))
    p = prof(sg_first, discard_order=_recording_order(seen))
    assert ability.value_for_player(p, at).sum == pytest.approx(3.0 + 0.6)
    assert seen == [True]
    assert ability.value_for_player(p, ()).sum == 0.0  # no candidate space
    dagger_first = hand(turn_state, owner, starter("dagger"), imperium("guild_spy"))
    assert ability.value_for_player(prof(dagger_first), at).sum == 0.0
    assert ability.value_for_player(prof(hand(turn_state, owner)), at).sum == 0.0


def test_guild_envoy_evaluate_floors_at_one_half(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.GuildEnvoyAbility(imperium("guild_envoy"))
    seen: list[bool] = []
    p = prof(turn_state, discard_order=_recording_order(seen))
    spy = imperium("guild_spy")
    answer = ability.evaluate(p, req(spy, starter("dagger")))
    assert answer.value == pytest.approx(2.6)
    assert answer.response == ((spy.ref,),)
    assert seen == [True]
    answer = ability.evaluate(p, req(starter("dagger")))
    assert (answer.value, answer.response) == (0.5, ((starter("dagger").ref,),))
    assert ability.evaluate(p, req()).response is None


def test_guild_spy_agent(turn_state: GameState, prof: ProfileFactory) -> None:
    owner = imperium("guild_spy")
    ability = ia.GuildSpyAgentAbility(owner)
    at = (space("arrakeen"),)
    base = -1.0 + 1.5 + 0.3
    envoy = hand(turn_state, owner, imperium("guild_envoy"))
    assert ability.value_for_player(prof(envoy), at).sum == pytest.approx(base + 2.25)
    assert ability.value_for_player(prof(envoy), ()).sum == pytest.approx(base)
    dagger = hand(turn_state, owner, starter("dagger"))
    assert ability.value_for_player(prof(dagger), at).sum == pytest.approx(base)
    assert ability.value_for_player(prof(hand(turn_state, owner)), at).sum == 0.0
    seen: list[bool] = []
    p = prof(turn_state, discard_order=_recording_order(seen))
    answer = ability.evaluate(p, req(imperium("guild_envoy")))
    assert answer.value == pytest.approx(base + 2.25)
    assert seen == [True]
    answer = ability.evaluate(p, req(starter("dagger")))
    assert answer.value == pytest.approx(base)  # no floor
    assert ability.evaluate(p, req()).response is None


def test_guild_spy_reveal_counts_every_spied_faction(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.GuildSpyRevealAbility(imperium("guild_spy"))
    state = with_spies(
        turn_state,
        "spacing-guild-heighliner-deliver-supplies",
        "landsraad-high-council-imperial-privilege-swordmaster",
        "emperor-sardaukar-dutiful-service",
    )
    p = prof(state)
    assert ia.factions_observed(p) == ["spacing_guild", "emperor"]
    assert ability.value_for_player(p).sum == pytest.approx(2.5 + 2.0)
    assert ability.value_for_player(prof(turn_state)).sum == 0.0
    assert ability.evaluate(p, Request()).value == 1.0


# ---------------------------------------------------------------------------
# Hidden Missive, Imperial Spymaster
# ---------------------------------------------------------------------------


def test_hidden_missive_troop_has_no_influence_condition(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.BeneGesseritInfluenceTroopAbility(imperium("hidden_missive"))
    p = prof(with_player(turn_state, SEAT, influence=Influence()))
    assert ability.value_for_player(p).sum == pytest.approx(0.9)
    assert ability.evaluate(p, Request()).value == 100.0


def test_imperial_spymaster_needs_a_recalled_spy(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.ImperialSpymasterAbility(imperium("imperial_spymaster"))
    assert ability.value_for_player(prof(turn_state)).sum == 0.0
    recalled = with_player(turn_state, SEAT, spies_recalled_turn=1)
    assert ability.value_for_player(prof(recalled)).sum == 2.25
    assert ability.evaluate(prof(turn_state), Request()).value == 100.0


# ---------------------------------------------------------------------------
# In High Places
# ---------------------------------------------------------------------------


def test_in_high_places_spy_value_needs_a_bene_gesserit_card_in_play(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("in_high_places")
    ability = ia.InHighPlacesPlaceSpyAbility(owner)
    assert ability.value_for_player(prof(turn_state)).sum == 0.0
    played = in_play(turn_state, imperium("bene_gesserit_operative"))
    assert ability.value_for_player(prof(played)).sum == pytest.approx(1.66)
    itself = in_play(turn_state, owner)  # the owner is not excluded
    assert ability.value_for_player(prof(itself)).sum == pytest.approx(1.66)
    assert ability.evaluate(prof(turn_state), Request()).value == 1.66


def test_in_high_places_spy_play_area_synergy(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.InHighPlacesPlaceSpyAbility(imperium("in_high_places"))
    bg = imperium("truthtrance")
    p = prof(turn_state)  # two agents left, nothing in play
    s = ability.value_in_pile_for_other_play(p, Pile.PLAY_AREA, bg)
    assert s.sum == pytest.approx(0.75 * 1.66)
    assert ability.value_in_pile_for_other_play(p, Pile.DECK, bg).sum == 0.0
    plain = ability.value_in_pile_for_other_play(p, Pile.PLAY_AREA, starter("dagger"))
    assert plain.sum == 0.0
    one_agent = prof(
        with_player(turn_state, SEAT, agents_available=1, agent_locations=("arrakeen",))
    )
    assert (
        ability.value_in_pile_for_other_play(one_agent, Pile.PLAY_AREA, bg).sum == 0.0
    )
    bg_played = prof(in_play(turn_state, imperium("weirding_woman")))
    assert (
        ability.value_in_pile_for_other_play(bg_played, Pile.PLAY_AREA, bg).sum == 0.0
    )


def test_in_high_places_recall_two_spies(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.InHighPlacesPersuasionAbility(imperium("in_high_places"))
    one = with_spies(turn_state, "arrakis-deep-desert")
    assert not ability.meets_cost(prof(one))
    assert ability.value_for_player(prof(one)).sum == 0.0
    two_posts = ("arrakis-deep-desert", "arrakis-hagga-basin")
    two = with_spies(turn_state, *two_posts)
    assert ability.meets_cost(prof(two))
    assert ability.value_for_player(prof(two)).sum == pytest.approx(-3.32 + 2.25)
    spies = [spy_entity(post, SEAT) for post in two_posts]
    answer = ability.evaluate(prof(two), req(*spies))
    assert answer.value == pytest.approx(2.25 - 3.32)
    assert answer.response == (two_posts,)
    short = prof(two, recall_spies=lambda s, take: (list(s[:1]), 0.0))
    assert ability.evaluate(short, req(*spies)).response is None


# ---------------------------------------------------------------------------
# Leadership
# ---------------------------------------------------------------------------


def test_leadership_agent(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ia.LeadershipAgentAbility(imperium("leadership"))
    assert ability.value_for_player(prof(turn_state)).sum == 0.0
    worms = with_units(turn_state, garrison=3, worms=2)
    assert ability.value_for_player(prof(worms)).sum == pytest.approx(3.0 + 0.6)
    assert ability.evaluate(prof(turn_state), Request()).value == 2.0  # 3.0 - 1.0
    small = prof(turn_state, sandworm_value=lambda n, include=False: 1.5 * n)
    assert ability.evaluate(small, Request()).value == 1.0  # floor


# ---------------------------------------------------------------------------
# Long Live the Fighters
# ---------------------------------------------------------------------------


def test_long_live_the_fighters_start(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.LongLiveTheFightersStartAbility(imperium("long_live_the_fighters"))
    assert len(turn_state.players[SEAT].deck) == 5
    # 2 draws, BuyGains(3), TrashCardValue, LongLiveTheFightersMod (2.0).
    assert ability.value_for_player(prof(turn_state)).sum == pytest.approx(
        3.0 + 0.3 + 2.75 + 2.0
    )
    short = with_player(turn_state, SEAT, deck=turn_state.players[SEAT].deck[:2])
    assert ability.value_for_player(prof(short)).sum == 0.0
    assert ability.evaluate(prof(turn_state), Request()).value == 100.0


def test_long_live_the_fighters_draw_prompt_is_never_offered(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ia.LongLiveTheFightersAbility(imperium("long_live_the_fighters"))
    p = prof(turn_state)
    assert not ability.meets_cost(p)
    assert not ability.can_be_run(p)
    assert ability.value_for_player(p).sum == 0.0


TSMF = card_entity("reserve:the_spice_must_flow:0", SEAT)


@pytest.mark.parametrize(
    ("top", "drawn"),
    [
        # Dagger is junk: trash it, draw the dearer of the other two.
        (
            (
                starter("dagger"),
                imperium("sardaukar_soldier"),
                imperium("corrinth_city"),
            ),
            2,
        ),
        # No junk: trash the cheapest (Convincing Argument is never junk);
        # the dearest left is The Spice Must Flow (cost 9), so the other one.
        ((starter("convincing_argument"), TSMF, imperium("corrinth_city")), 2),
        # Equal costs keep deck order: Diplomacy is trashed, Seek Allies drawn.
        ((starter("diplomacy"), starter("seek_allies"), starter("signet_ring")), 1),
    ],
)
def test_long_live_the_fighters_draw(
    turn_state: GameState,
    prof: ProfileFactory,
    top: tuple[Entity, Entity, Entity],
    drawn: int,
) -> None:
    ability = ia.LongLiveTheFightersAbility(imperium("long_live_the_fighters"))
    p = prof(turn_state, card_to_trash=None)  # the real GetCardToTrash
    answer = ability.evaluate(p, req(*top))
    assert (answer.value, answer.response) == (100.0, ((top[drawn].ref,),))


def test_long_live_the_fighters_evaluator(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state, card_to_trash=None)
    evaluator = ia.LongLiveTheFightersEvaluator
    corrinth, dagger = imperium("corrinth_city"), starter("dagger")
    soldier = imperium("sardaukar_soldier")
    assert evaluator.get_trash_card(p, [corrinth, dagger]) == dagger
    assert evaluator.get_trash_card(p, [corrinth, soldier]) == soldier
    answer = evaluator.evaluate(p, req(corrinth, dagger))
    assert (answer.value, answer.response) == (100.0, ((corrinth.ref,),))
    answer = evaluator.evaluate(p, req(soldier, corrinth))
    assert answer.response == ((corrinth.ref,),)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_dmax_follows_math_max() -> None:
    assert ia._dmax(1.0, 2.0) == 2.0
    assert ia._dmax(2.0, 1.0) == 2.0
    assert math.isnan(ia._dmax(math.nan, 1.0))
    assert math.isnan(ia._dmax(1.0, math.nan))


def test_can_deploy_sandworms_follows_the_shield_wall(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    walled = set_conflict(turn_state, "battle_for_arrakeen")
    assert not ia._can_deploy_sandworms(prof(walled))
    blown = with_state(walled, shield_wall_present=False)
    assert ia._can_deploy_sandworms(prof(blown))
    assert ia._can_deploy_sandworms(prof(turn_state))  # a skirmish
