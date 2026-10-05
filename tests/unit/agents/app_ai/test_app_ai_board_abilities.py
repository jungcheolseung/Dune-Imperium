"""Board, conflict and contract ability ports: spec/board.md (abilities/board.py).

Every test builds a real ``GameState`` (``app_ai.testing``), adjusts the
fields the formula reads, and stubs the ``Profile`` methods other areas own
with simple linear prices, so each expected value can be checked by hand.
"""

import random
from collections.abc import Callable
from dataclasses import replace
from types import MappingProxyType
from typing import Any

import pytest

from dune_imperium.agents.app_ai.abilities import board as b
from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities.base import (
    PORTS,
    Answer,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    UnportedAbility,
    abilities_of,
)
from dune_imperium.agents.app_ai.catalog import (
    CONFLICT_ARCHETYPES,
    CONTRACT_ARCHETYPES,
    SPACE_ARCHETYPES,
    agent_entity,
    conflict_entity,
    conflict_reward_entities,
    contract_entity,
    intrigue_entity,
    space_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS, AppContext, Board
from dune_imperium.agents.app_ai.data.archetypes import Archetype
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GamePhase, GameState

# ---------------------------------------------------------------------------
# Fixtures and stubs
# ---------------------------------------------------------------------------

PRICES = {
    Attr.WATER: 1.0,
    Attr.SPICE: 0.5,
    Attr.SOLARI: 0.25,
    Attr.PERSUASION: 0.75,
    Attr.TROOPS: 0.9,
}
INFLUENCE = {"emperor": 2.0, "spacing_guild": 2.5, "bene_gesserit": 3.0, "fremen": 1.0}
SEAT = 3  # the first player of seed 1 (Lady Jessica)
AG = "worm.canis.abilities."


def _base_stubs() -> dict[str, Callable[..., Any]]:
    return {
        "resource_value": lambda attr, n, include=False: PRICES[attr] * n,
        "spice_value": lambda n: 0.5 * n,
        "solari_value": lambda n: 0.25 * n,
        "water_value": lambda n: 1.0 * n,
        "troop_value": lambda n, include=False: 0.9 * n,
        "persuasion_value": lambda n: 0.75 * n,
        "sandworm_value": lambda n, include=False: 3.0 * n,
        "victory_point_value": lambda n: 6.0 * n,
        "card_draw_value": lambda: 1.5,
        "possible_persuasion_gain": lambda: 3,
        "buy_gains": lambda n: 0.1 * n,
        "card_draw_value_with_buy_gains": lambda: 1.8,
        "intrigue_value": lambda: 2.25,
        "high_council_value": lambda: 15.0,
        "swordmaster_value": lambda: 50.0,
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(
            INFLUENCE[f] * n
        ),
        "spy_value": lambda: Summer(1.66),
        "recall_spy_value": lambda: Summer(-1.66),
        "recall_spy": lambda spies: (None, 0.0),
        "recall_agent_value": lambda: 5.0,
        "recall_agent": lambda agents: None,
        "want_contract_count": lambda: 1,
        "maker_hooks_value": lambda: 5.0,
        "blow_wall_value": lambda: Summer(2.0),
        "conflict_posture_bounds": lambda: (2.0, 5.0),
        "current_conflict_interest": lambda: Summer(3.0),
        "lady_jessica_return_memories": lambda: False,
        "spice_for_spice_refinery": lambda: 1,
        "bad_intrigue_cards_in_hand": lambda: [],
        "battle_icon_value": lambda icon: Summer(2.5),
        "game_arc": lambda: 0,
        "is_climax": lambda: False,
        "abundance_level": lambda attr: 1,
        "deck_agent_icons": lambda: {},
        "deploy_value": lambda owner: 1.25,
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
    """``prof(state, decision_kind=None, **stub overrides) -> Profile``."""

    def build(
        state: GameState,
        seat: int = SEAT,
        decision_kind: str | None = None,
        **overrides: Callable[..., Any],
    ) -> Profile:
        profile = make_profile(state, seat)
        if decision_kind is not None:
            view = replace(profile.ctx.view, decision_kind=decision_kind)
            profile.ctx = AppContext(state, seat, view)
        stubs = _base_stubs()
        stubs.update(overrides)
        for name, fn in stubs.items():
            monkeypatch.setattr(profile, name, fn)
        return profile

    return build


@pytest.fixture
def tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep summer reasons, to read which branch a value came from."""

    monkeypatch.setattr(Summer, "tracing", True)


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


def with_frame(state: GameState, **changes: str | int | bool) -> GameState:
    """``state`` with keys of the top frame's context replaced."""

    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context.update(changes)
    new = replace(frame, context=tuple(sorted(context.items())))
    return with_state(state, decision_stack=(*state.decision_stack[:-1], new))


def set_conflict(state: GameState, conflict_id: str | None) -> GameState:
    """``conflict_id`` face up (taken out of the Conflict deck), or none."""

    current = () if conflict_id is None else (conflict_id,)
    return with_state(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
        ),
        current_conflict_ids=current,
    )


def give_contracts(
    state: GameState, seat: int, active: tuple[str, ...] = ()
) -> GameState:
    """Move contracts out of the shared zones into a seat's contract area."""

    taken = set(active)
    state = with_state(
        state,
        contract_bank=tuple(c for c in state.contract_bank if c not in taken),
        face_up_contract_ids=tuple(
            c for c in state.face_up_contract_ids if c not in taken
        ),
    )
    return with_player(state, seat, active_contract_ids=active)


def with_bonus(state: GameState, **bonus: int) -> GameState:
    spaces = ("deep_desert", "hagga_basin", "imperial_basin")
    return with_state(
        state, maker_bonus_spice=tuple((s, bonus.get(s, 0)) for s in spaces)
    )


def req(*entities: Entity, options: tuple[int, ...] = ()) -> Request:
    return Request((TargetInfo(tuple(entities), options, 0, 1),))


def space(space_id: str) -> Entity:
    return space_entity(space_id, Board(True))


def contract(name: str) -> Entity:
    return contract_entity(f"contract:{name}", SEAT)


def total(p: Profile, space_id: str) -> float:
    """``WormSpace.ValueForPlayer``: the merge of every ability of the space."""

    return p.space_value_for_player(space(space_id)).sum


def reasons(summer: Summer) -> list[str]:
    assert summer.reasons is not None
    return [reason for _, reason, _ in summer.reasons]


def assert_answer(answer: Answer, value: float, response: object) -> None:
    """``answer`` is worth ``value`` (approximately) with ``response``."""

    assert answer.value == pytest.approx(value)
    assert answer.response == response


# ---------------------------------------------------------------------------
# Registration, class chains and coverage of the board archetypes
# ---------------------------------------------------------------------------


def test_board_ports_registered_with_the_app_class_chain() -> None:
    expected = {
        "SpaceAbilities.BaseSet.HighCouncilSpaceAbility": b.HighCouncilSpaceAbility,
        "SpaceAbilities.Uprising.HighCouncilUprisingSpaceAbility": (
            b.HighCouncilUprisingSpaceAbility
        ),
        "SpaceAbilities.BaseSet.HeighlinerSpaceAbility": b.HeighlinerSpaceAbility,
        "SpaceAbilities.Uprising.DesertSpaceDeferredAbility": (
            b.DesertSpaceDeferredAbility
        ),
        "SpaceAbilities.Uprising.DeepDesertDeferredAbility": (
            b.DeepDesertDeferredAbility
        ),
        "ActivatedAbilities.Uprising.RecallSpyIntelligenceAbility": (
            b.RecallSpyIntelligenceAbility
        ),
        "ConflictAbilities.Uprising.GainAnyTwoInfluenceConflictAbility": (
            b.GainAnyTwoInfluenceConflictAbility
        ),
        "ActivatedAbilities.Uprising.ContractAbilities.TSMFContractAbility": (
            b.TSMFContractAbility
        ),
        "TriggeredAbilities.Uprising.ActivateTSMFContractTriggeredAbility": (
            b.ActivateTSMFContractTriggeredAbility
        ),
    }
    for name, cls in expected.items():
        assert PORTS[AG + name] is cls
        assert cls.APP_CLASS == AG + name
    space_classes = (
        b.HighCouncilSpaceAbility,
        b.HighCouncilUprisingSpaceAbility,
        b.SwordmasterUprisingSpaceAbility,
        b.HeighlinerSpaceAbility,
        b.SecretsSpaceAbility,
        b.EspionageSpaceAbility,
        b.AssemblyHallSpaceAbility,
        b.GatherSupportAbility,
        b.SpiceRefineryAbility,
    )
    assert all(issubclass(c, g.SpaceAbility) for c in space_classes)
    assert not issubclass(b.HighCouncilUprisingSpaceAbility, b.HighCouncilSpaceAbility)
    deferred = (
        b.SietchTabrUprisingDeferredSpaceAbility,
        b.DesertSpaceDeferredAbility,
        b.ImperialPrivilegeAbility,
        b.RecallSpyInfiltrateAbility,
        b.RecallSpyIntelligenceAbility,
    )
    for cls in deferred:
        assert issubclass(cls, g.DeferredAbility)
        assert not issubclass(cls, g.SpaceAbility)
    assert issubclass(b.HaggaBasinUprisingDeferredAbility, b.DesertSpaceDeferredAbility)
    contracts = (
        b.Harvest3ContractAbility,
        b.Harvest4ContractAbility,
        b.RecallAgentContractAbility,
        b.TSMFContractAbility,
        b.BeneGesseritContractAbility,
    )
    assert all(issubclass(c, g.ContractAbility) for c in contracts)
    assert not issubclass(b.Harvest4ContractAbility, b.Harvest3ContractAbility)
    assert issubclass(b.GainAnyTwoInfluenceConflictAbility, g.ConflictAbility)
    assert not issubclass(b.GainAnyTwoInfluenceConflictAbility, g.DeferredAbility)
    for cls in (
        b.HighCouncilAbility2,
        b.AssemblyHallAbility,
        b.ActivateTSMFContractTriggeredAbility,
    ):
        assert issubclass(cls, g.TriggeredAbility)
        assert cls.should_exhaust is False
    assert not issubclass(
        b.ActivateTSMFContractTriggeredAbility, g.ActivateContractTriggeredAbility
    )


def _scope_entities() -> list[Entity]:
    """Every space, conflict card, conflict reward and contract archetype of
    4-player Uprising, with and without CHOAM."""

    entities: list[Entity] = []
    for choam in (False, True):
        entities.extend(space_entity(s, Board(choam)) for s in SPACE_ARCHETYPES)
        for conflict_id in CONFLICT_ARCHETYPES:
            if conflict_id == "economic_supremacy":
                continue  # Epic Game Mode: covered by the expansion ports.
            entities.append(conflict_entity(conflict_id, choam))
            entities.extend(conflict_reward_entities(conflict_id, choam))
    entities.extend(contract_entity(f"contract:{c}") for c in CONTRACT_ARCHETYPES)
    return entities


def test_every_board_archetype_ability_resolves_to_a_port() -> None:
    names: set[str] = set()
    for entity in _scope_entities():
        names.update(entity.ability_ids)
        for ability in abilities_of(entity):
            assert not isinstance(ability, UnportedAbility), (entity.short, ability)
    missing = sorted(n for n in names if n not in PORTS)
    assert missing == []
    assert len(names) == 50
    # The two playmat spy abilities of the Agent turn are ported too.
    for name in ("RecallSpyInfiltrateAbility", "RecallSpyIntelligenceAbility"):
        assert AG + "ActivatedAbilities.Uprising." + name in PORTS


# ---------------------------------------------------------------------------
# Engine-side members
# ---------------------------------------------------------------------------

_FLAGS: list[tuple[type[g.DeferredAbility], SelectionMode, bool, Timing]] = [
    (
        b.SietchTabrUprisingDeferredSpaceAbility,
        SelectionMode.EXPLICIT,
        False,
        Timing.NONE,
    ),
    (b.DeepDesertDeferredAbility, SelectionMode.EXPLICIT, False, Timing.NONE),
    (b.HaggaBasinUprisingDeferredAbility, SelectionMode.EXPLICIT, False, Timing.NONE),
    (b.ImperialPrivilegeAbility, SelectionMode.OPTIONAL, False, Timing.AGENT),
    (b.RecallSpyInfiltrateAbility, SelectionMode.EXPLICIT, True, Timing.NONE),
    (b.RecallSpyIntelligenceAbility, SelectionMode.EXPLICIT, True, Timing.NONE),
    (b.Harvest3ContractAbility, SelectionMode.EXPLICIT, True, Timing.NONE),
    (b.Harvest4ContractAbility, SelectionMode.EXPLICIT, True, Timing.NONE),
    (b.RecallAgentContractAbility, SelectionMode.EXPLICIT, False, Timing.NONE),
    (b.TSMFContractAbility, SelectionMode.EXPLICIT, False, Timing.NONE),
    (b.BeneGesseritContractAbility, SelectionMode.EXPLICIT, False, Timing.NONE),
]


@pytest.mark.parametrize(("cls", "mode", "always", "timing"), _FLAGS)
def test_engine_side_members(
    turn_state: GameState,
    prof: ProfileFactory,
    cls: type[g.DeferredAbility],
    mode: SelectionMode,
    always: bool,
    timing: Timing,
) -> None:
    ability = cls(space("deep_desert"))
    p = prof(turn_state)
    assert ability.selection_mode(p) == mode
    assert ability.always_run_immediately is always
    assert ability.timing == timing
    if cls in (
        b.SietchTabrUprisingDeferredSpaceAbility,
        b.DeepDesertDeferredAbility,
        b.ImperialPrivilegeAbility,
        b.RecallAgentContractAbility,
    ):
        assert not ability.can_run_immediately(p)
    if always:
        assert ability.can_run_immediately(p)


def test_conflict_reward_and_triggered_timings(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    assert b.GainAnyTwoInfluenceConflictAbility.timing == Timing.COMBAT_RESOLUTION
    p = prof(turn_state)
    for trigger in (
        b.HighCouncilAbility2(space("high_council")),
        b.ActivateTSMFContractTriggeredAbility(contract("acquire")),
    ):
        assert trigger.value_for_player(p, (space("high_council"),)).sum == 0.0
        answer = trigger.evaluate(p, Request())
        assert (answer.value, answer.response) == (0.0, None)


def test_tsmf_and_bg_contract_run_unless_threshold(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    tsmf = b.TSMFContractAbility(contract("acquire"))
    bg = b.BeneGesseritContractAbility(contract("high_council_i"))
    calm = prof(effects_state)
    assert tsmf.can_run_immediately(calm)
    assert bg.can_run_immediately(calm)
    piled = with_frame(effects_state, card_id=f"player:{SEAT}:starter:signet_ring:0")
    assert g.deferred_threshold_reached(prof(piled))
    assert not tsmf.can_run_immediately(prof(piled))
    assert not bg.can_run_immediately(prof(piled))
    # No Reveal-turn exemption for either.
    revealed = with_player(piled, SEAT, has_revealed=True)
    assert not tsmf.can_run_immediately(prof(revealed))
    assert not bg.can_run_immediately(prof(revealed))
    # The BG contract runs when it clears the undo stack (BG influence 3).
    near = with_player(piled, SEAT, influence=Influence(bene_gesserit=3))
    assert bg.will_clear_undo(prof(near))
    assert bg.can_run_immediately(prof(near))
    assert not tsmf.can_run_immediately(prof(near))
    four = with_player(piled, SEAT, influence=Influence(bene_gesserit=4))
    assert not bg.will_clear_undo(prof(four))
    # No current player (outside the player-turn phase): both run.
    no_turn = with_state(piled, phase=GamePhase.COMBAT)
    assert tsmf.can_run_immediately(prof(no_turn))
    assert bg.can_run_immediately(prof(no_turn))


# ---------------------------------------------------------------------------
# High Council (board §1.4.10): the double-counted generic value
# ---------------------------------------------------------------------------


def test_high_council_first_visit(turn_state: GameState, prof: ProfileFactory) -> None:
    p = prof(turn_state)
    seat = b.HighCouncilSpaceAbility(space("high_council"))
    repeat = b.HighCouncilUprisingSpaceAbility(space("high_council"))
    assert seat.meets_cost(p)
    assert not repeat.meets_cost(p)
    base = -5 * 0.25  # the generic value: the 5 Solari cost
    assert seat.value_for_player(p).sum == pytest.approx(base + 15.0)
    assert repeat.value_for_player(p).sum == pytest.approx(base)
    # Seat + Ability2 (0) + generic value again + no repeat intrigue.
    assert total(p, "high_council") == pytest.approx(2 * base + 15.0)


def test_high_council_councilors_ambition(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    held = with_player(
        turn_state, SEAT, intrigue_cards=("intrigue:councilor_s_ambition:0",)
    )
    assert total(prof(held), "high_council") == pytest.approx(-2.5 + 15.0 + 3.0)
    seated = with_player(held, SEAT, high_council=True)
    assert b.HighCouncilSpaceAbility(space("high_council")).value_for_player(
        prof(seated)
    ).sum == pytest.approx(-1.25)


def test_high_council_repeat_visit(turn_state: GameState, prof: ProfileFactory) -> None:
    seated = prof(with_player(turn_state, SEAT, high_council=True))
    repeat = b.HighCouncilUprisingSpaceAbility(space("high_council"))
    assert repeat.meets_cost(seated)
    assert repeat.value_for_player(seated).sum == pytest.approx(-1.25 + 1.0 + 2.7)
    # 2 x generic value + 2 spice + 3 troops + the repeat-visit intrigue.
    assert total(seated, "high_council") == pytest.approx(-2.5 + 1.0 + 2.7 + 2.25)


def test_high_council_seat_taken_this_visit_is_not_a_repeat(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    state = with_frame(
        effects_state, space_id="high_council", board_icons="high_council"
    )
    p = prof(with_player(state, SEAT, high_council=True))
    assert not b.HighCouncilUprisingSpaceAbility(space("high_council")).meets_cost(p)
    assert total(p, "high_council") == pytest.approx(-2.5)


# ---------------------------------------------------------------------------
# Swordmaster, Heighliner, Secrets, Espionage, Assembly Hall
# ---------------------------------------------------------------------------


def test_swordmaster_value_and_cost_drop(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    sword = b.SwordmasterUprisingSpaceAbility(space("swordmaster"))
    assert sword.value_for_player(prof(turn_state)).sum == pytest.approx(-2.0 + 50.0)
    taken = with_player(turn_state, 0, swordmaster_acquired=True, agents_available=3)
    assert sword.value_for_player(prof(taken)).sum == pytest.approx(-1.5 + 50.0)


def _heighliner(p: Profile) -> float:
    return b.HeighlinerSpaceAbility(space("heighliner")).value_for_player(p).sum


HEIGHLINER_BASE = 5 * 0.9 - 5 * 0.5  # 5 troops, pay 5 spice
EARLY = -3.0  # one extra agent left, nobody else can pay 5 spice


def test_heighliner_bonus_branches(turn_state: GameState, prof: ProfileFactory) -> None:
    # Round 1: supply 9, interest 3 between the bounds (2, 5), a level-1 conflict.
    assert _heighliner(prof(turn_state)) == pytest.approx(HEIGHLINER_BASE + EARLY)
    high = prof(turn_state, current_conflict_interest=lambda: Summer(6.0))
    assert _heighliner(high) == pytest.approx(HEIGHLINER_BASE + 4.0 + EARLY)
    at_upper = prof(turn_state, current_conflict_interest=lambda: Summer(5.0))
    assert _heighliner(at_upper) == pytest.approx(HEIGHLINER_BASE + EARLY)
    battle = set_conflict(turn_state, "battle_for_arrakeen")  # level 3
    assert _heighliner(prof(battle)) == pytest.approx(HEIGHLINER_BASE + 4.0 + EARLY)
    at_lower = prof(battle, current_conflict_interest=lambda: Summer(2.0))
    assert _heighliner(at_lower) == pytest.approx(HEIGHLINER_BASE + EARLY)
    order: list[str] = []

    def bounds() -> tuple[float, float]:
        order.append("bounds")
        return (2.0, 5.0)

    def interest() -> Summer:
        order.append("interest")
        return Summer(3.0)

    _heighliner(
        prof(
            turn_state,
            conflict_posture_bounds=bounds,
            current_conflict_interest=interest,
        )
    )
    assert order == ["bounds", "interest"]


def test_heighliner_low_supply_branches(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    high = {"current_conflict_interest": lambda: Summer(6.0)}
    two = with_player(turn_state, SEAT, troops_supply=2, troops_garrison=10)
    assert _heighliner(prof(two, **high)) == pytest.approx(HEIGHLINER_BASE + EARLY)
    one = with_player(turn_state, SEAT, troops_supply=1, troops_garrison=11)
    assert _heighliner(prof(one)) == pytest.approx(HEIGHLINER_BASE - 6.0 + EARLY)
    level3 = set_conflict(one, "battle_for_arrakeen")
    assert _heighliner(prof(level3)) == pytest.approx(HEIGHLINER_BASE + EARLY)
    none = set_conflict(one, None)
    assert _heighliner(prof(none)) == pytest.approx(HEIGHLINER_BASE - 6.0 + EARLY)


def test_heighliner_early_in_round_penalty(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    rich = with_player(turn_state, 0, resources=Resources(spice=5))
    assert _heighliner(prof(rich)) == pytest.approx(HEIGHLINER_BASE)
    four = with_player(turn_state, 0, resources=Resources(spice=4))
    assert _heighliner(prof(four)) == pytest.approx(HEIGHLINER_BASE + EARLY)
    last = with_player(
        turn_state, SEAT, agents_available=1, agent_locations=("arrakeen",)
    )
    assert _heighliner(prof(last)) == pytest.approx(HEIGHLINER_BASE)
    three = with_player(turn_state, SEAT, agents_available=3, swordmaster_acquired=True)
    assert _heighliner(prof(three)) == pytest.approx(HEIGHLINER_BASE + 2 * EARLY)


def _intrigues(n: int) -> tuple[str, ...]:
    return tuple(f"intrigue:buy_access:{k}" for k in range(n))


def test_secrets_steal_term_counts_other_full_hands(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    secrets = b.SecretsSpaceAbility(space("secrets"))
    assert secrets.value_for_player(prof(turn_state)).sum == 0.0
    state = with_player(turn_state, 0, intrigue_cards=_intrigues(4))
    state = with_player(state, 1, intrigue_cards=_intrigues(5))
    state = with_player(state, 2, intrigue_cards=_intrigues(3))
    state = with_player(state, SEAT, intrigue_cards=_intrigues(4))
    assert secrets.value_for_player(prof(state)).sum == pytest.approx((1.0 + 2.25) * 2)


def test_secrets_and_espionage_lady_jessica_memories(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    secrets = b.SecretsSpaceAbility(space("secrets"))
    espionage = b.EspionageSpaceAbility(space("espionage"))
    state = with_player(turn_state, SEAT, memories=2, troops_supply=7)
    assert espionage.value_for_player(prof(state)).sum == pytest.approx(-0.5)
    returns = prof(state, lady_jessica_return_memories=lambda: True)
    assert secrets.value_for_player(returns).sum == pytest.approx(1.5 * 2)
    assert espionage.value_for_player(returns).sum == pytest.approx(-0.5 + 1.5 * 2)


def test_assembly_hall(turn_state: GameState, prof: ProfileFactory) -> None:
    p = prof(turn_state)
    hall = b.AssemblyHallAbility(space("assembly_hall"))
    assert hall.value_for_player(p).sum == pytest.approx(0.75)
    assert b.AssemblyHallSpaceAbility(space("assembly_hall")).value_for_player(
        p
    ).sum == pytest.approx(0.0)
    assert total(p, "assembly_hall") == pytest.approx(0.75 + 2.25)


# ---------------------------------------------------------------------------
# Gather Support, Spice Refinery
# ---------------------------------------------------------------------------


def test_gather_support_cost_and_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    gather = b.GatherSupportAbility(space("gather_support"))
    assert gather.find_solari_cost() == 2
    assert b.GatherSupportAbility(synth(Kind.SPACE, "x")).find_solari_cost() == 2
    custom = synth(Kind.SPACE, "y", PossibleSolariCost=3, SolariDiscount=1)
    assert b.GatherSupportAbility(custom).find_solari_cost() == 4
    # 2 troops + the water trade, counted though the AI holds no Solari.
    assert gather.value_for_player(prof(turn_state)).sum == pytest.approx(
        1.8 + (1.0 - 0.5)
    )
    cheap_water = prof(turn_state, water_value=lambda n: 0.4 * n)
    assert gather.value_for_player(cheap_water).sum == pytest.approx(1.8)


def test_gather_support_evaluate(turn_state: GameState, prof: ProfileFactory) -> None:
    gather = b.GatherSupportAbility(space("gather_support"))
    assert gather.evaluate(prof(turn_state), Request()).response is None
    rich = with_player(turn_state, SEAT, resources=Resources(solari=2))
    paid = gather.evaluate(prof(rich), Request())
    assert (paid.value, paid.response) == (1.0, ((1,),))  # Max(0.5, 1.0)
    precious = prof(rich, water_value=lambda n: 3.0 * n)
    assert gather.evaluate(precious, Request()).value == pytest.approx(2.5)
    even = prof(rich, water_value=lambda n: 0.5 * n)
    kept = gather.evaluate(even, Request())
    assert (kept.value, kept.response) == (1.0, ((0,),))


def test_spice_refinery_value(turn_state: GameState, prof: ProfileFactory) -> None:
    refinery = b.SpiceRefineryAbility(space("spice_refinery"))
    assert refinery.solari_amount(1) == 4
    # 2 Solari == 1 spice: no trade term.
    assert refinery.value_for_player(prof(turn_state)).sum == pytest.approx(0.5)
    cheap_spice = prof(turn_state, spice_value=lambda n: 0.2 * n)
    assert refinery.value_for_player(cheap_spice).sum == pytest.approx(0.5 + 0.5 - 0.2)


def test_spice_refinery_evaluate(turn_state: GameState, prof: ProfileFactory) -> None:
    refinery = b.SpiceRefineryAbility(space("spice_refinery"))
    sell = refinery.evaluate(prof(turn_state), Request())
    assert_answer(sell, 1.0 - 0.5, ((1,),))
    keep = refinery.evaluate(
        prof(turn_state, spice_for_spice_refinery=lambda: 0), Request()
    )
    assert_answer(keep, 0.5, ((0,),))
    assert (
        refinery.evaluate(
            prof(turn_state, spice_for_spice_refinery=lambda: -1), Request()
        ).response
        is None
    )
    floored = refinery.evaluate(
        prof(turn_state, spice_value=lambda n: 2.0 * n), Request()
    )
    assert (floored.value, floored.response) == (1.0, ((1,),))


# ---------------------------------------------------------------------------
# Sietch Tabr, maker spaces
# ---------------------------------------------------------------------------


def test_sietch_tabr_value(
    turn_state: GameState, prof: ProfileFactory, tracing: None
) -> None:
    sietch = b.SietchTabrUprisingDeferredSpaceAbility(space("sietch_tabr"))
    hooks = sietch.value_for_player(prof(turn_state))
    assert hooks.sum == pytest.approx(5.0 + 1.0 + 0.9)
    assert reasons(hooks) == ["Maker Hooks + Troop"]
    wall = sietch.value_for_player(
        prof(turn_state, blow_wall_value=lambda: Summer(10.0))
    )
    assert wall.sum == pytest.approx(11.0)
    assert reasons(wall) == ["Blow Wall"]
    tie = sietch.value_for_player(
        prof(
            turn_state,
            troop_value=lambda n, include=False: 1.0 * n,
            blow_wall_value=lambda: Summer(6.0),
        )
    )
    assert tie.sum == 7.0
    assert reasons(tie) == ["Blow Wall"]


def test_sietch_tabr_evaluate(turn_state: GameState, prof: ProfileFactory) -> None:
    sietch = b.SietchTabrUprisingDeferredSpaceAbility(space("sietch_tabr"))
    hooks = sietch.evaluate(prof(turn_state), Request())
    assert_answer(hooks, 6.9, ((0,),))
    wall = sietch.evaluate(
        prof(turn_state, blow_wall_value=lambda: Summer(10.0)), Request()
    )
    assert (wall.value, wall.response) == (11.0, ((1,),))
    tie = sietch.evaluate(
        prof(
            turn_state,
            troop_value=lambda n, include=False: 1.0 * n,
            blow_wall_value=lambda: Summer(6.0),
        ),
        Request(),
    )
    assert (tie.value, tie.response) == (7.0, ((0,),))


def _desert(space_id: str) -> b.DesertSpaceDeferredAbility:
    cls = (
        b.DeepDesertDeferredAbility
        if space_id == "deep_desert"
        else b.HaggaBasinUprisingDeferredAbility
    )
    return cls(space(space_id))


def test_desert_value_spice_or_worms(
    turn_state: GameState, prof: ProfileFactory, tracing: None
) -> None:
    deep, hagga = _desert("deep_desert"), _desert("hagga_basin")
    no_hooks = deep.value_for_player(prof(turn_state))
    assert (no_hooks.sum, reasons(no_hooks)) == (2.0, ["Desert Space Spice"])
    hooked = with_player(turn_state, SEAT, maker_hooks=True)
    worms = deep.value_for_player(prof(hooked))
    assert (worms.sum, reasons(worms)) == (6.0, ["Desert Space Sandworm"])
    assert hagga.value_for_player(prof(hooked)).sum == 3.0
    # A tie goes to the worms in V.
    tie = hagga.value_for_player(
        prof(hooked, sandworm_value=lambda n, include=False: 1.0 * n)
    )
    assert (tie.sum, reasons(tie)) == (1.0, ["Desert Space Sandworm"])
    reduced = b.DeepDesertDeferredAbility(
        synth(Kind.SPACE, "deep", SpiceGainReduction=-1)
    )
    assert reduced.value_for_player(prof(turn_state)).sum == pytest.approx(1.5)


def test_desert_worms_need_deployable_sandworms(
    turn_state: GameState, effects_state: GameState, prof: ProfileFactory
) -> None:
    deep = _desert("deep_desert")
    hooked = with_player(turn_state, SEAT, maker_hooks=True)
    walled = with_state(
        set_conflict(hooked, "siege_of_arrakeen"), shield_wall_present=True
    )
    assert deep.value_for_player(prof(walled)).sum == 2.0
    open_wall = with_state(walled, shield_wall_present=False)
    assert deep.value_for_player(prof(open_wall)).sum == 6.0
    blocked = with_frame(effects_state, units_deploy_blocked=True)
    blocked = with_player(blocked, SEAT, maker_hooks=True)
    assert deep.value_for_player(prof(blocked)).sum == 2.0


def test_desert_muad_dib_two_worms_cost_an_intrigue(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    muad = with_player(
        turn_state, SEAT, leader_id="muad_dib", leader_face_id=None, maker_hooks=True
    )
    deep, hagga = _desert("deep_desert"), _desert("hagga_basin")
    assert deep.value_for_player(prof(muad)).sum == pytest.approx(6.0 - 2.25)
    calm = prof(muad, current_conflict_interest=lambda: Summer(2.0))  # == lower
    assert deep.value_for_player(calm).sum == 6.0
    assert hagga.value_for_player(prof(muad)).sum == 3.0  # one worm: no penalty
    answer = deep.evaluate(prof(muad), Request())
    assert_answer(answer, 3.75, ((1,),))


def test_desert_evaluate(turn_state: GameState, prof: ProfileFactory) -> None:
    deep, hagga = _desert("deep_desert"), _desert("hagga_basin")
    spice = deep.evaluate(prof(turn_state), Request())
    assert (spice.value, spice.response) == (2.0, ((0,),))
    hooked = with_player(turn_state, SEAT, maker_hooks=True)
    worms = deep.evaluate(prof(hooked), Request())
    assert (worms.value, worms.response) == (6.0, ((1,),))
    # A tie keeps the spice in E.
    tie = hagga.evaluate(
        prof(hooked, sandworm_value=lambda n, include=False: 1.0 * n), Request()
    )
    assert (tie.value, tie.response) == (1.0, ((0,),))


# ---------------------------------------------------------------------------
# Imperial Privilege, agent recall
# ---------------------------------------------------------------------------


def test_imperial_privilege_value(turn_state: GameState, prof: ProfileFactory) -> None:
    privilege = b.ImperialPrivilegeAbility(space("imperial_privilege"))
    held = with_player(turn_state, SEAT, intrigue_cards=("intrigue:buy_access:0",))
    assert privilege.value_for_player(prof(held)).sum == 0.0
    junk = intrigue_entity("intrigue:buy_access:0", SEAT)
    bad = prof(held, bad_intrigue_cards_in_hand=lambda: [junk])
    assert privilege.value_for_player(bad).sum == 2.25
    assert privilege.meets_cost(prof(held))
    assert not privilege.meets_cost(prof(turn_state))


def test_imperial_privilege_evaluate_trashes_a_bad_intrigue(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    privilege = b.ImperialPrivilegeAbility(space("imperial_privilege"))
    cards = [
        intrigue_entity(f"intrigue:{name}:0", SEAT)
        for name in ("buy_access", "detonation", "devour", "cunning")
    ]
    request = req(*cards)
    assert privilege.evaluate(prof(turn_state), request) == Answer(
        0.0, None, "Imperial Privilege no bad intrigue"
    )
    one = prof(turn_state, bad_intrigue_cards_in_hand=lambda: [cards[2]])
    assert privilege.evaluate(one, request).response == ((cards[2].ref,),)
    assert privilege.evaluate(one, request).value == 2.25
    # Several bad cards: the first in the shuffled order (profile rng seed 0).
    bad = [cards[1], cards[2], cards[3]]
    many = prof(turn_state, bad_intrigue_cards_in_hand=lambda: bad)
    shuffled = list(cards)
    random.Random(0).shuffle(shuffled)
    first_bad = next(c for c in shuffled if c in bad)
    assert privilege.evaluate(many, request).response == ((first_bad.ref,),)


def test_recall_agent_contract(turn_state: GameState, prof: ProfileFactory) -> None:
    recall = b.RecallAgentContractAbility(contract("sardaukar_ii"))
    p = prof(turn_state)
    assert recall.resource_value(p).sum == 5.0
    assert recall.value_for_player(p, (space("sardaukar"),)).sum == 5.0
    assert recall.value_for_player(p, (space("arrakeen"),)).sum == 0.0
    # Space contract at Sardaukar: 0.5 x 5 x round factor 1 + Emperor icons
    # (none in the deck: -5 x 0.17) + spice abundance (+3 x 0.16), no spy.
    assert recall.specific_acquire_value(p).sum == pytest.approx(2.5 - 0.85 + 0.48)
    agents = [agent_entity("arrakeen", SEAT), agent_entity("secrets", SEAT)]
    first = recall.evaluate(p, req(*agents))
    assert (first.value, first.response) == (6.0, (("arrakeen",),))
    picked = prof(turn_state, recall_agent=lambda a: a[1])
    assert recall.evaluate(picked, req(*agents)).response == (("secrets",),)
    nothing = recall.evaluate(p, req())
    assert (nothing.value, nothing.response) == (1.0, ())


# ---------------------------------------------------------------------------
# Playmat spy abilities
# ---------------------------------------------------------------------------


def test_recall_spy_infiltrate(turn_state: GameState, prof: ProfileFactory) -> None:
    infiltrate = b.RecallSpyInfiltrateAbility(space("arrakeen"))
    p = prof(turn_state)
    assert infiltrate.evaluate(p, req()) == Answer(100.0, (), "Infiltrate | 100")
    spies = [
        spy_entity("arrakis-spice-refinery-arrakeen", SEAT),
        spy_entity("arrakis-deep-desert", SEAT),
    ]
    fallback = infiltrate.evaluate(p, req(*spies))
    assert (fallback.value, fallback.response) == (100.0, ((spies[0].ref,),))
    worst = prof(turn_state, recall_spy=lambda s: (s[1], 0.4))
    assert infiltrate.evaluate(worst, req(*spies)).response == ((spies[1].ref,),)


def test_recall_spy_intelligence(turn_state: GameState, prof: ProfileFactory) -> None:
    intel = b.RecallSpyIntelligenceAbility(space("arrakeen"))
    p = prof(turn_state)
    yes = intel.evaluate(p, Request())
    assert_answer(yes, 1.8 - 1.66, ((1,),))
    spies = [
        spy_entity("arrakis-spice-refinery-arrakeen", SEAT),
        spy_entity("arrakis-research-station-spice-refinery", SEAT),
    ]
    two_infos = Request(
        (TargetInfo((), (0, 1), 1, 1), TargetInfo(tuple(spies), (), 1, 1))
    )
    assert intel.evaluate(p, two_infos).response == ((1,), (spies[0].ref,))
    worst = prof(turn_state, recall_spy=lambda s: (s[1], 0.4))
    assert intel.evaluate(worst, two_infos).response == ((1,), (spies[1].ref,))
    cheap = prof(turn_state, card_draw_value_with_buy_gains=lambda: 1.0)
    no = intel.evaluate(cheap, two_infos)
    assert (no.value, no.response) == (1.0, ((0,),))
    three = with_player(
        turn_state,
        SEAT,
        spy_post_ids=(
            "arrakis-spice-refinery-arrakeen",
            "arrakis-deep-desert",
            "arrakis-hagga-basin",
        ),
        spies_supply=0,
    )
    forced = intel.evaluate(
        prof(three, card_draw_value_with_buy_gains=lambda: 1.0), Request()
    )
    assert_answer(forced, 100.0 - 0.66, ((1,),))


# ---------------------------------------------------------------------------
# Conflict rewards: Gain any two influence (board §2.4.3)
# ---------------------------------------------------------------------------


def test_gain_any_two_influence_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    propaganda = conflict_entity("propaganda", True)
    two = b.GainAnyTwoInfluenceConflictAbility(propaganda)
    assert two.value_for_player(p).sum == pytest.approx(3.0 + 2.5)
    # Through the 1st-place reward: best two factions + the battle icon.
    first = g.GenericConflictFirstAbility(propaganda)
    assert first.value_for_player(p).sum == pytest.approx(5.5 + 2.5)


def test_gain_any_two_influence_evaluate(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    two = b.GainAnyTwoInfluenceConflictAbility(conflict_entity("propaganda", True))
    tracks = [track_entity(f) for f in FACTIONS]
    best = two.evaluate(prof(turn_state), req(*tracks))
    assert_answer(best, 5.5, (("bene_gesserit", "spacing_guild"),))
    # Equal values: the stable sort keeps the shuffled order (rng seed 0).
    flat = prof(
        turn_state, gain_influence_value=lambda f, n, r=-1, a=False: Summer(-1.0)
    )
    shuffled = list(tracks)
    random.Random(0).shuffle(shuffled)
    tied = two.evaluate(flat, req(*tracks))
    assert tied.response == ((shuffled[0].ref, shuffled[1].ref),)
    assert tied.value == 0.5  # Math.Max(0.5, -2)
    empty = two.evaluate(prof(turn_state), req())
    assert (empty.value, empty.response) == (0.5, ((),))


# ---------------------------------------------------------------------------
# Contracts (board §3)
# ---------------------------------------------------------------------------


def test_harvest_contract_value_needs_spice_at_the_space(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    harvest3 = b.Harvest3ContractAbility(contract("harvest_3"))
    harvest4 = b.Harvest4ContractAbility(contract("harvest_4"))
    basin = (space("imperial_basin"),)
    two = prof(with_bonus(turn_state, imperial_basin=2))
    assert harvest3.value_for_player(two, basin).sum == pytest.approx(0.75)
    assert harvest4.value_for_player(two, basin).sum == 0.0
    three = prof(with_bonus(turn_state, imperial_basin=3))
    assert harvest4.value_for_player(three, basin).sum == pytest.approx(1.0)
    one = prof(with_bonus(turn_state, imperial_basin=1))
    assert harvest3.value_for_player(one, basin).sum == 0.0
    # Hagga Basin has no Spice attribute: only its bonus spice counts.
    hagga = (space("hagga_basin"),)
    hagga2 = prof(with_bonus(turn_state, hagga_basin=2))
    assert harvest3.value_for_player(hagga2, hagga).sum == 0.0
    hagga3 = prof(with_bonus(turn_state, hagga_basin=3))
    assert harvest3.value_for_player(hagga3, hagga).sum == pytest.approx(0.75)
    rich = prof(with_bonus(turn_state, imperial_basin=5))
    assert harvest3.value_for_player(rich, (space("arrakeen"),)).sum == 0.0
    assert harvest3.value_for_player(rich).sum == 0.0


def test_harvest_contract_counts_at_its_space(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    state = give_contracts(
        with_bonus(turn_state, imperial_basin=2), SEAT, ("contract:harvest_3",)
    )
    basin = g.SpaceAbility(space("imperial_basin"))
    # Spice (1 + 2 x 1.25) x 0.5 + the harvest reward + WantContractCount.
    assert basin.value_for_player(prof(state)).sum == pytest.approx(
        3.5 * 0.5 + 0.75 + 1.0
    )


def test_tsmf_contract(turn_state: GameState, prof: ProfileFactory) -> None:
    tsmf = b.TSMFContractAbility(contract("acquire"))
    p = prof(turn_state)
    # Solari 3 + Guild influence + the literal 3 Solari again.
    assert tsmf.resource_value(p).sum == pytest.approx(0.75 + 2.5 + 0.75)
    assert tsmf.value_for_player(p).sum == pytest.approx(4.0)
    assert tsmf.value_for_player(p, (space("arrakeen"),)).sum == pytest.approx(4.0)
    # Acquire: 0.34 x 4 x 1 - 3 x 0.33 (no seat) - 3 x 0.33 (early).
    assert tsmf.specific_acquire_value(p).sum == pytest.approx(1.36 - 0.99 - 0.99)
    late = prof(with_player(turn_state, SEAT, high_council=True), game_arc=lambda: 2)
    assert tsmf.specific_acquire_value(late).sum == pytest.approx(1.36 + 0.99 + 0.99)


def test_bene_gesserit_contract(turn_state: GameState, prof: ProfileFactory) -> None:
    bg = b.BeneGesseritContractAbility(contract("high_council_i"))
    p = prof(turn_state)
    assert bg.resource_value(p).sum == 3.0
    assert bg.value_for_player(p, (space("high_council"),)).sum == 3.0
    assert bg.value_for_player(p, (space("arrakeen"),)).sum == 0.0
    # Space contract at the High Council: 0.5 x 3 x 1, no faction icon, Solari
    # abundance +3 x 0.16, no spy.
    assert bg.specific_acquire_value(p).sum == pytest.approx(1.5 + 0.48)
    assert bg.evaluate(p, Request()).value == 100.0


# Draw-2 contracts (ContractBase_6 Spice Refinery I, ContractBase_12 Sardaukar
# I): ``Draw2ContractAbility::GetResourceValue`` @0x4d59300 adds
# ``2 x CardDrawValue`` (``addsd xmm0, xmm0`` @0x4d59376) and
# ``GetBuyGains(2 x PossiblePersuasionGain())`` (``lea esi, [rax + rax]``
# @0x4d593ac); board.md §3.4 writes the second undoubled. With the stubs:
# 2 x 1.5 + 0.1 x (2 x 3) = 3.6. Space contracts in round 1: 0.5 x 1 x 3.6,
# plus the space's mods (Spice Refinery: no faction icon, Solari 1 worth less
# than 0.5 -> -3 x 0.16; Sardaukar: no Emperor icon in the deck -> -5 x 0.17,
# spice abundance +3 x 0.16).
DRAW2_REWARD = 2 * 1.5 + 0.1 * (2 * 3)
DRAW2_CONTRACTS = [
    ("spice_refinery_i", 0.5 * DRAW2_REWARD - 0.48),
    ("sardaukar_i", 0.5 * DRAW2_REWARD - 0.85 + 0.48),
]


@pytest.mark.parametrize(("name", "expected"), DRAW2_CONTRACTS)
def test_draw2_contract_acquire_value_doubles_the_buy_gains_persuasion(
    turn_state: GameState, prof: ProfileFactory, name: str, expected: float
) -> None:
    port = g.Draw2ContractAbility(contract(name))
    p = prof(turn_state)
    assert port.resource_value(p).sum == pytest.approx(DRAW2_REWARD)
    assert port.specific_acquire_value(p).sum == pytest.approx(expected)


@pytest.mark.parametrize(("name", "expected"), DRAW2_CONTRACTS)
def test_profile_contract_pick_prices_draw2_like_the_app(
    turn_state: GameState, prof: ProfileFactory, name: str, expected: float
) -> None:
    c = contract(name)
    p = prof(turn_state)
    # WormContractPlayable::AcquireValue -> the contract's ContractAbility.
    assert p.contract_acquire_value(c).sum == pytest.approx(expected)
    best, value = p.best_contract([c], False)
    assert best is not None
    assert best.ref == c.ref
    assert value == pytest.approx(expected)
