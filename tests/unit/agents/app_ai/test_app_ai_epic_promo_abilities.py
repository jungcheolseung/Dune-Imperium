"""Epic Game Mode and promo ability ports: spec/epic-goto11-promo-draft.md.

Control the Spice (§2.3), Economic Supremacy (§2.4), the three Uprising promos
(§4: Arrakis Revolt here; Pivotal Gambit and The Beast's Spoils are ported in
``imperium_b.py``) and the reachability of Economic Supremacy's rewards
(``board.granted_reward_abilities``).

Most tests build a real ``GameState`` (``app_ai.testing``), adjust the fields
the formula reads and stub the ``Profile`` prices with simple linear ones, so
each expected value can be checked by hand against the spec's literals. A few
run the real Hard profile (the junk-card choice, ``ConflictValue``, the
promos' purchase value).
"""

import random
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import PORTS, abilities_of
from dune_imperium.agents.app_ai.abilities import board as b
from dune_imperium.agents.app_ai.abilities import epic_promo as e
from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities import imperium_b as ib
from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Answer,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    UnportedAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    conflict_entity,
    conflict_reward_entities,
    space_entity,
)
from dune_imperium.agents.app_ai.context import AppContext, Board
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES
from dune_imperium.agents.app_ai.data.constants import TABLES
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    play_until,
    with_player,
)
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Resources
from dune_imperium.core.state import GameState

SEAT = 1  # the first player of seed 1 in an Epic game
AA = "worm.canis.abilities.ActivatedAbilities."
CA = "worm.canis.abilities.ConflictAbilities."
PA = "worm.canis.abilities.PlayAbilities."
EPIC = RulesetConfig(epic_game=True, choam_module=True)
PROMOS = RulesetConfig(promo_cards=True, choam_module=True)

# ---------------------------------------------------------------------------
# Fixtures and stubs
# ---------------------------------------------------------------------------


def _base_stubs() -> dict[str, Callable[..., Any]]:
    return {
        "spice_value": lambda n: 0.5 * n,
        "solari_value": lambda n: 0.25 * n,
        "troop_value": lambda n, include=False: 0.9 * n,
        "sandworm_value": lambda n, include=False: 3.0 * n,
        "victory_point_value": lambda n: 6.0 * n,
        "trash_card_value": lambda: 2.75,
        "trash_mod": lambda: 1.0,
        "blow_wall_value": lambda: Summer(4.0),
        "card_to_trash": lambda targets, minimum: (None, minimum),
        "can_agent_ability_be_played_with_space": lambda space, attr, n: True,
    }


ProfileFactory = Callable[..., Profile]


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """Seat 1's first ``turn`` decision of an Epic game (CHOAM on)."""

    state = first_decision("turn", config=EPIC)
    assert _owner(state) == SEAT
    return state


def _owner(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


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


def starter(name: str, copy: int = 7) -> Entity:
    """A starter instance no zone of the fixture holds (copy 7)."""

    return card_entity(f"player:{SEAT}:starter:{name}:{copy}", SEAT)


def imperium(name: str, copy: int = 0) -> Entity:
    return card_entity(f"imperium:{name}:{copy}", SEAT)


def space(space_id: str) -> Entity:
    return space_entity(space_id, Board(True))


def resources(state: GameState, **amounts: int) -> GameState:
    return with_player(state, SEAT, resources=Resources(**amounts))


def es() -> Entity:
    return conflict_entity("economic_supremacy", True)


# ---------------------------------------------------------------------------
# Registration, class chain, flags and coverage
# ---------------------------------------------------------------------------

_REGISTERED: list[tuple[str, type[Ability], type[Ability]]] = [
    (AA + "RiseOfIx.ControlTheSpiceAbility", e.ControlTheSpiceAbility,
     g.DeferredAbility),
    (AA + "Promo.ArrakisRevoltAbility", e.ArrakisRevoltAbility, g.DeferredAbility),
    (CA + "RiseOfIx.EconomicSupremacyFirstAbility",
     e.EconomicSupremacyFirstAbility, g.ConflictAbility),
    (CA + "RiseOfIx.EconomicSupremacySecondAbility",
     e.EconomicSupremacySecondAbility, g.ConflictAbility),
    (CA + "RiseOfIx.EconomicSupremacyThirdAbility",
     e.EconomicSupremacyThirdAbility, g.ConflictAbility),
    (CA + "RiseOfIx.EconomicSupremacySolariAbility",
     e.EconomicSupremacySolariAbility, g.DeferredAbility),
    (CA + "RiseOfIx.EconomicSupremacySpiceAbility",
     e.EconomicSupremacySpiceAbility, g.DeferredAbility),
    # Ported in imperium_b.py (spec §4.4-§4.5 agree with it).
    (AA + "Promo.PivotalGambitAbility", ib.PivotalGambitAbility, g.DeferredAbility),
    (AA + "Promo.TheBeastsSpoilsCrysknifeAbility",
     ib.TheBeastsSpoilsCrysknifeAbility, g.TrashAbility),
    (AA + "Promo.TheBeastsSpoilsDesertMouseAbility",
     ib.TheBeastsSpoilsDesertMouseAbility, g.DeferredAbility),
    (AA + "Promo.TheBeastsSpoilsOrnithopterAbility",
     ib.TheBeastsSpoilsOrnithopterAbility, g.DeferredAbility),
]  # fmt: skip


@pytest.mark.parametrize(("name", "cls", "base"), _REGISTERED)
def test_registered_under_the_app_class_with_its_base(
    name: str, cls: type[Ability], base: type[Ability]
) -> None:
    assert PORTS[name] is cls
    assert cls.APP_CLASS == name
    assert issubclass(cls, base)


def test_economic_supremacy_rewards_are_not_generic_conflict_abilities() -> None:
    # ConflictAbilities.ConflictAbility, not GenericConflictAbility (§2.4).
    for cls in (
        e.EconomicSupremacyFirstAbility,
        e.EconomicSupremacySecondAbility,
        e.EconomicSupremacyThirdAbility,
    ):
        assert not issubclass(cls, g.GenericConflictAbility)
    assert e.EconomicSupremacyFirstAbility.place == 1
    assert e.EconomicSupremacySecondAbility.place == 2
    assert e.EconomicSupremacyThirdAbility.place == 3


_FLAGS: list[tuple[type[g.DeferredAbility], Timing]] = [
    (e.ControlTheSpiceAbility, Timing.AGENT),
    (e.ArrakisRevoltAbility, Timing.AGENT),
    (e.EconomicSupremacySolariAbility, Timing.COMBAT_RESOLUTION),
    (e.EconomicSupremacySpiceAbility, Timing.COMBAT_RESOLUTION),
]


@pytest.mark.parametrize(("cls", "timing"), _FLAGS)
def test_deferred_flags(
    cls: type[g.DeferredAbility], timing: Timing, turn_state: GameState
) -> None:
    owner = es() if timing is Timing.COMBAT_RESOLUTION else starter("dagger")
    ability = cls(owner)
    p = make_profile(turn_state, SEAT)
    # Every one is Optional and waits in the post-action / resolution prompt.
    assert ability.selection_mode(p) is SelectionMode.OPTIONAL
    assert ability.can_run_immediately(p) is False
    assert cls.timing is timing


_COVERED_ARCHETYPES = (
    "ImperiumArchetypes.RiseOfIx.ControltheSpice",
    "ConflictArchetypes.RiseOfIx.EconomicSupremacy",
    "ImperiumArchetypes.Promo.ArrakisRevolt",
    "ImperiumArchetypes.Promo.PivotalGambit",
    "ImperiumArchetypes.Promo.TheBeastsSpoils",
)


def test_every_epic_and_promo_ability_resolves_to_a_port() -> None:
    entities = [
        starter("control_the_spice"),
        es(),
        conflict_entity("economic_supremacy", False),
        imperium("arrakis_revolt"),
        imperium("pivotal_gambit"),
        imperium("the_beast_s_spoils"),
    ]
    assert {entity.short for entity in entities} == set(_COVERED_ARCHETYPES)
    names: set[str] = set()
    for short in _COVERED_ARCHETYPES:
        names.update(ARCHETYPES[short].attributes["WormAbilityIDs"])  # type: ignore[arg-type]
    for entity in entities:
        for ability in abilities_of(entity):
            assert not isinstance(ability, UnportedAbility), (entity.short, ability)
    assert sorted(n for n in names if n not in PORTS) == []
    # CtS 1 + ES 5 + the shared Agent/Reveal/Acquire 3 + promos 1 + 1 + 3.
    assert len(names) == 14


# ---------------------------------------------------------------------------
# Control the Spice (§2.3)
# ---------------------------------------------------------------------------


def test_control_the_spice_archetype() -> None:
    card = starter("control_the_spice")
    assert card.int_attr("DeferValue") == 2
    assert not card.has("TrashValue")
    assert not card.has("AcquireValue")
    assert [type(a) for a in abilities_of(card)] == [
        e.ControlTheSpiceAbility,
        g.AgentAbility,
        g.RevealAbility,
    ]
    # The DeferValue 2 is the deferral weight of the card (threshold 3).
    p_state = first_decision("turn", config=EPIC)
    assert e.ControlTheSpiceAbility(card).defer_value(make_profile(p_state)) == 2


def test_control_the_spice_cost_is_one_spice(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = e.ControlTheSpiceAbility(starter("control_the_spice"))
    assert not ability.meets_cost(prof(resources(turn_state, spice=0)))
    assert ability.meets_cost(prof(resources(turn_state, spice=1)))


def test_control_the_spice_targets_hand_then_play_then_discard(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    cts = starter("control_the_spice")
    hand = (starter("dagger"), starter("diplomacy"))
    played = (cts,)
    discard = (starter("dune_the_desert_planet"), starter("reconnaissance"))
    state = with_player(
        turn_state,
        SEAT,
        hand=tuple(c.ref for c in hand),
        in_play=tuple(c.ref for c in played),
        discard_pile=tuple(c.ref for c in discard),
    )
    request = e.ControlTheSpiceAbility(cts).target_request(prof(state))
    assert len(request.infos) == 1
    info = request.infos[0]
    assert [c.ref for c in info.entities] == [c.ref for c in (*hand, *played, *discard)]
    assert (info.min_select, info.max_select, info.forced) == (0, 1, False)
    assert request.forced is False


def test_control_the_spice_evaluate_names_the_junk_card(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    dagger = starter("dagger")
    seen: list[tuple[list[str], float]] = []

    def to_trash(targets: list[Entity], minimum: float) -> tuple[Entity | None, float]:
        seen.append(([t.ref for t in targets], minimum))
        return dagger, 10.09

    ability = e.ControlTheSpiceAbility(starter("control_the_spice"))
    request = Request((TargetInfo((dagger, starter("diplomacy")), (), 0, 1),))
    answer = ability.evaluate(prof(turn_state, card_to_trash=to_trash), request)
    # -spice(1) + TrashCardValue + TrashMod + troop(1); not the trash score.
    assert answer.value == pytest.approx(-0.5 + 2.75 + 1.0 + 0.9)
    assert answer.response == ((dagger.ref,),)
    assert e.ControlTheSpiceAbility.trash_target(answer) == dagger.ref
    # GetCardToTrash(targets, 1.0) over the request's cards.
    assert seen == [([dagger.ref, starter("diplomacy").ref], 1.0)]


def test_control_the_spice_without_junk_is_not_taken(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = e.ControlTheSpiceAbility(starter("control_the_spice"))
    request = Request((TargetInfo((starter("diplomacy"),), (), 0, 1),))
    answer = ability.evaluate(prof(turn_state), request)
    assert answer.value == 0.0
    assert answer.response is None
    assert e.ControlTheSpiceAbility.trash_target(answer) is None


def test_control_the_spice_placement_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = e.ControlTheSpiceAbility(starter("control_the_spice"))
    full = -0.5 + 2.75 + 1.0 + 0.9
    p = prof(turn_state)
    assert ability.value_for_player(p).sum == pytest.approx(full)  # no space
    assert ability.value_for_player(p, (space("arrakeen"),)).sum == pytest.approx(full)
    asked: list[tuple[str, str, int]] = []

    def cannot(space_: Entity, attr: Any, n: int) -> bool:
        asked.append((space_.ref, str(attr), n))
        return False

    short = prof(turn_state, can_agent_ability_be_played_with_space=cannot)
    # Not inverted: the trade counts only when 1 more spice can be paid.
    assert ability.value_for_player(short, (space("spice_refinery"),)).sum == 0.0
    assert asked == [("spice_refinery", "Spice", 1)]


def test_control_the_spice_real_profile_picks_dagger_not_convincing_argument(
    turn_state: GameState,
) -> None:
    cts = starter("control_the_spice")
    ability = e.ControlTheSpiceAbility(cts)

    def state_with(*hand: Entity) -> GameState:
        return with_player(
            resources(turn_state, spice=2, water=1),
            SEAT,
            hand=tuple(c.ref for c in hand),
            in_play=(cts.ref,),
            discard_pile=(),
        )

    def answer_for(*hand: Entity) -> Answer:
        p = make_profile(state_with(*hand), SEAT)
        return ability.evaluate(p, ability.target_request(p))

    # Convincing Argument's -0.25 mod (applied to every card when it is a
    # target) brings its own 0.25 to 0: never trashed; Dagger's 1.0 - 0.25 is.
    hand = (starter("convincing_argument"), starter("dagger"))
    picked = answer_for(*hand)
    assert e.ControlTheSpiceAbility.trash_target(picked) == starter("dagger").ref
    nothing = answer_for(starter("convincing_argument"), starter("diplomacy"))
    assert nothing.response is None and nothing.value == 0.0
    # The value is the four Hard-profile terms, whatever the card.
    p = make_profile(state_with(*hand), SEAT)
    assert p.trash_card_value() == TABLES[2].TrashCardEarly == 2.75
    expected = (
        p.spice_value(-1) + p.trash_card_value() + p.trash_mod() + p.troop_value(1)
    )
    assert picked.value == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Arrakis Revolt (§4.3, imperium-a.md §2.1)
# ---------------------------------------------------------------------------


def test_arrakis_revolt_cost_needs_two_spice_and_hooks(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = e.ArrakisRevoltAbility(imperium("arrakis_revolt"))
    poor = with_player(resources(turn_state, spice=1), SEAT, maker_hooks=True)
    hooked = with_player(resources(turn_state, spice=2), SEAT, maker_hooks=True)
    unhooked = with_player(resources(turn_state, spice=5), SEAT, maker_hooks=False)
    assert not ability.meets_cost(prof(poor))
    assert ability.meets_cost(prof(hooked))
    assert not ability.meets_cost(prof(unhooked))


def test_arrakis_revolt_evaluate_has_no_gate(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = e.ArrakisRevoltAbility(imperium("arrakis_revolt"))
    broke = with_player(resources(turn_state, spice=0), SEAT, maker_hooks=False)
    answer = ability.evaluate(prof(broke), Request())
    # GetSpiceValue(-2) + BlowWallValue + GetSandWormValue(1, false).
    assert answer.value == pytest.approx(-1.0 + 4.0 + 3.0)
    assert answer.response == ()


def test_arrakis_revolt_value_counts_only_the_unaffordable_trade(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = e.ArrakisRevoltAbility(imperium("arrakis_revolt"))
    hooked = with_player(turn_state, SEAT, maker_hooks=True)
    at = (space("arrakeen"),)
    asked: list[int] = []

    def affordable(value: bool) -> Callable[[Entity, Any, int], bool]:
        def check(space_: Entity, attr: Any, n: int) -> bool:
            asked.append(n)
            return value

        return check

    # App bug kept (17 §16): affordable -> nothing, unaffordable -> the trade.
    p = prof(hooked, can_agent_ability_be_played_with_space=affordable(True))
    assert ability.value_for_player(p, at).sum == 0.0
    p = prof(hooked, can_agent_ability_be_played_with_space=affordable(False))
    assert ability.value_for_player(p, at).sum == pytest.approx(-1.0 + 4.0 + 3.0)
    assert asked == [2, 2]
    # No space, or no maker hooks: nothing.
    assert ability.value_for_player(p).sum == 0.0
    unhooked = with_player(turn_state, SEAT, maker_hooks=False)
    p = prof(unhooked, can_agent_ability_be_played_with_space=affordable(False))
    assert ability.value_for_player(p, at).sum == 0.0


def test_arrakis_revolt_wall_question_sees_the_spice_paid(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[int, int, int]] = []

    def should_blow_wall(self: Profile) -> bool:
        seen.append(
            (
                self.ctx.me.resources.spice,
                self.ctx.me.resources.solari,
                self.ctx.state.players[0].resources.spice,
            )
        )
        return True

    state = with_player(
        resources(turn_state, spice=5, solari=3), SEAT, maker_hooks=True
    )
    p = make_profile(state, SEAT)
    monkeypatch.setattr(Profile, "should_blow_wall", should_blow_wall)
    ability = e.ArrakisRevoltAbility(imperium("arrakis_revolt"))
    assert ability.should_blow_wall_after_payment(p) is True
    assert seen == [(3, 3, state.players[0].resources.spice)]
    # The original profile still sees the unpaid state.
    assert p.ctx.me.resources.spice == 5


def test_arrakis_revolt_wall_question_real_profile(turn_state: GameState) -> None:
    ability = e.ArrakisRevoltAbility(imperium("arrakis_revolt"))
    state = with_player(resources(turn_state, spice=4), SEAT, maker_hooks=True)
    p = make_profile(state, SEAT)
    paid = make_profile(resources(state, spice=2), SEAT)
    assert ability.should_blow_wall_after_payment(p) == paid.should_blow_wall()
    # Without the wall ShouldBlowWall is false (the AI declines then).
    gone = replace(state, shield_wall_present=False)
    assert ability.should_blow_wall_after_payment(make_profile(gone, SEAT)) is False


# ---------------------------------------------------------------------------
# Pivotal Gambit (§4.4 Errata) and The Beast's Spoils (§4.5)
# ---------------------------------------------------------------------------


def test_pivotal_gambit_extends_only_a_generic_first_reward() -> None:
    battle = conflict_entity("battle_for_spice_refinery", True)
    target = e.pivotal_gambit_reward_ability(battle)
    assert isinstance(target, g.GenericConflictFirstAbility)
    assert target.owner == battle
    # Economic Supremacy has no GenericConflictFirstAbility: influence lost.
    assert e.pivotal_gambit_reward_ability(es()) is None


def test_promo_cards_carry_their_ported_abilities() -> None:
    assert [type(a) for a in abilities_of(imperium("pivotal_gambit"))] == [
        g.AgentAbility,
        g.RevealAbility,
        g.AcquireAbility,
        ib.PivotalGambitAbility,
    ]
    assert [type(a) for a in abilities_of(imperium("the_beast_s_spoils"))] == [
        g.AgentAbility,
        g.RevealAbility,
        g.AcquireAbility,
        ib.TheBeastsSpoilsCrysknifeAbility,
        ib.TheBeastsSpoilsDesertMouseAbility,
        ib.TheBeastsSpoilsOrnithopterAbility,
    ]
    assert [type(a) for a in abilities_of(imperium("arrakis_revolt"))] == [
        g.AgentAbility,
        g.RevealAbility,
        g.AcquireAbility,
        e.ArrakisRevoltAbility,
    ]


def test_pivotal_gambit_port_matches_the_spec(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    gambit = ib.PivotalGambitAbility(imperium("pivotal_gambit"))
    p = prof(turn_state)
    assert gambit.evaluate(p, Request()).value == 100.0
    assert gambit.selection_mode(p) is SelectionMode.OPTIONAL
    # Smuggler's Haven's V copied without the affordability test.
    assert gambit.value_for_player(p, (space("arrakeen"),)).sum == -2.0 + 6.0


# ---------------------------------------------------------------------------
# §4.2: the promos have no AcquireValue (base 0)
# ---------------------------------------------------------------------------

_PROMOS = ("arrakis_revolt", "pivotal_gambit", "the_beast_s_spoils")


@pytest.mark.parametrize("name", _PROMOS)
def test_promo_archetypes_have_no_purchase_data(name: str) -> None:
    card = imperium(name)
    for attr in ("AcquireValue", "EarlyMod", "LateMod", "DeferValue", "Tags"):
        assert not card.has(attr), (name, attr)
    assert card.attr("ImperiumType") == "Promo"


@pytest.mark.parametrize("level", [2, 1, 0])
def test_promo_acquire_value_starts_from_zero(level: int) -> None:
    state = first_decision("turn", config=PROMOS)
    seat = _owner(state)
    Summer.tracing = True
    try:
        for name in _PROMOS:
            card = card_entity(f"imperium:{name}:0", seat)
            value = make_profile(state, seat, level=level).acquire_value(card)
            assert value.reasons is not None
            assert value.reasons[0] == ("+", "Archetype Value", 0.0)
            # Round 1: only new icons can add; every level stays below its
            # MinimumAcquireValueEarly (1.2 / 0.7 / 0.5), so the value is 0.
            assert value.sum == 0.0, (name, level)
    finally:
        Summer.tracing = False
    hard = TABLES[2]
    assert (hard.MinimumAcquireValueEarly, hard.AcquireNewIconsBonus) == (1.2, 0.45)


# ---------------------------------------------------------------------------
# Economic Supremacy (§2.4)
# ---------------------------------------------------------------------------


def test_economic_supremacy_card() -> None:
    card = es()
    assert card.int_attr("VictoryPoints") == 4
    assert not card.has("ConflictRewardArchetypes")
    assert not card.has("BattleIcon")
    assert conflict_reward_entities("economic_supremacy", True) == ()
    assert [type(a) for a in abilities_of(card)] == [
        e.EconomicSupremacyFirstAbility,
        e.EconomicSupremacySecondAbility,
        e.EconomicSupremacyThirdAbility,
        e.EconomicSupremacySolariAbility,
        e.EconomicSupremacySpiceAbility,
    ]


@pytest.mark.parametrize(
    ("solari", "spice", "value", "label"),
    [
        (5, 3, 6.0, "1 VP"),
        (6, 3, -1.5 + 12.0, "2 VP"),  # GetSolariValue(-6) + VP(2)
        (5, 4, -2.0 + 12.0, "2 VP"),  # GetSpiceValue(1) * -4.0 + VP(2)
        (6, 4, -1.5 - 2.0 + 18.0, "3 VP"),
        (20, 20, -1.5 - 2.0 + 18.0, "3 VP"),
    ],
)
def test_economic_supremacy_first_value(
    solari: int,
    spice: int,
    value: float,
    label: str,
    turn_state: GameState,
    prof: ProfileFactory,
) -> None:
    Summer.tracing = True
    try:
        p = prof(resources(turn_state, solari=solari, spice=spice))
        v = e.EconomicSupremacyFirstAbility(es()).value_for_player(p)
    finally:
        Summer.tracing = False
    assert v.sum == pytest.approx(value)
    assert v.reasons is not None
    assert v.reasons[-1][1] == f"Economic Supremacy First {label}"


@pytest.mark.parametrize(
    ("solari", "spice", "double", "vp"),
    [
        (5, 3, False, 1),
        (6, 3, False, 2),
        (5, 4, False, 2),
        (6, 4, False, 3),
        (6, 4, True, 1),  # the sandworm copy needs 12 Solari / 8 spice
        (12, 7, True, 2),
        (11, 8, True, 2),
        (12, 8, True, 3),
    ],
)
def test_economic_supremacy_first_possible_reward_vp(
    solari: int,
    spice: int,
    double: bool,
    vp: int,
    turn_state: GameState,
    prof: ProfileFactory,
) -> None:
    state = resources(turn_state, solari=solari, spice=spice)
    first = e.EconomicSupremacyFirstAbility(es())
    assert first.possible_reward_vp(prof(state), double) == vp
    # The same for any player (the end-of-round projection asks every seat).
    assert e.economic_supremacy_first_reward_vp(state.players[SEAT], double) == vp


def test_economic_supremacy_second_and_third(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(resources(turn_state, solari=0, spice=0))
    second = e.EconomicSupremacySecondAbility(es())
    third = e.EconomicSupremacyThirdAbility(es())
    assert second.value_for_player(p).sum == 6.0
    assert second.possible_reward_vp(p, False) == 1
    assert second.possible_reward_vp(p, True) == 1
    # 2 x GetSpiceValue(1) + GetSolariValue(2).
    assert third.value_for_player(p).sum == pytest.approx(0.5 + 0.5 + 0.5)
    assert third.possible_reward_vp(p, False) == 0  # base: place 3


def test_economic_supremacy_charges(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    solari = e.EconomicSupremacySolariAbility(es())
    spice = e.EconomicSupremacySpiceAbility(es())
    p = prof(turn_state)
    for charge in (solari, spice):
        assert charge.evaluate(p, Request()).value == 100.0
        assert charge.evaluate(p, Request()).response == ()
        assert charge.value_for_player(p).sum == 0.0  # V not overridden
        assert charge.possible_conflict_vp(p, False) == 0
        assert charge.victory_points == 1
    assert (solari.solari_cost, solari.spice_cost) == (6, 0)
    assert (spice.solari_cost, spice.spice_cost) == (0, 4)


def _reward_profile(state: GameState, *, winner: int, kind: str) -> Profile:
    """A Hard profile for SEAT in ``kind``, ``winner`` alone with strength 5."""

    players = tuple(
        replace(pl, combat_strength=5 if pl.player_id == winner else 1)
        for pl in state.players
    )
    state = replace(state, players=players)
    view = replace(ENGINE.observe(state, SEAT), decision_kind=kind)
    return Profile(AppContext(state, SEAT, view), TABLES[2], random.Random(0))


def test_economic_supremacy_charge_cost(turn_state: GameState) -> None:
    rich = resources(turn_state, solari=6, spice=4)
    solari = e.EconomicSupremacySolariAbility(es())
    spice = e.EconomicSupremacySpiceAbility(es())
    p = _reward_profile(rich, winner=SEAT, kind="combat_reward_optional")
    assert solari.meets_cost(p) and spice.meets_cost(p)
    # IsRewardPlace(1): only the sole winner holds the grant.
    p = _reward_profile(rich, winner=0, kind="combat_reward_optional")
    assert not solari.meets_cost(p) and not spice.meets_cost(p)
    # HasCustomAbility: only while the reward is being resolved.
    p = _reward_profile(rich, winner=SEAT, kind="turn")
    assert not solari.meets_cost(p) and not spice.meets_cost(p)
    poor = resources(turn_state, solari=5, spice=3)
    p = _reward_profile(poor, winner=SEAT, kind="combat_reward_optional")
    assert not solari.meets_cost(p) and not spice.meets_cost(p)


def _es_reward_frame(seed: int) -> GameState:
    """A real Epic game paused at an Economic Supremacy optional-VP frame."""

    return play_until(
        lambda state, owner: (
            state.decision_stack[-1].kind == "combat_reward_optional"
            and state.current_conflict_ids[-1:] == ("economic_supremacy",)
        ),
        seed=seed,
        config=RulesetConfig(epic_game=True),
    )


@pytest.mark.parametrize("seed", [1, 3])  # seed 3: the winner has a sandworm
def test_economic_supremacy_charges_in_the_engine_reward_frames(seed: int) -> None:
    # The charges' Cost (IsRewardPlace(1), HasCustomAbility, the resource) is
    # read where the window will read it: on the engine's own reward frames,
    # with Conflict strengths still on the table. Each frame (resource, cost)
    # is one of the two charges ES 1st grants (6 Solari, 4 spice; §2.4), the
    # sandworm copy included.
    state = _es_reward_frame(seed)
    winner = _owner(state)
    card = conflict_entity("economic_supremacy", False)
    granted = b.granted_reward_abilities(card, 1)
    charges = [a for a in granted if isinstance(a, e._EconomicSupremacyPayAbility)]
    assert len(charges) == len(granted) == 2
    by_cost = {(a.solari_cost, a.spice_cost): a for a in charges}
    frames = [dict(frame.context) for frame in state.decision_stack]
    assert len(frames) in (2, 4)
    for context in frames:
        cost = context["cost"]
        assert isinstance(cost, int)
        key = (cost, 0) if context["resource"] == "solari" else (0, cost)
        assert key in by_cost, context
        assert context["victory_points"] == by_cost[key].victory_points
    rich = with_player(state, winner, resources=Resources(solari=6, spice=4))
    poor = with_player(state, winner, resources=Resources(solari=5, spice=3))
    for charge in charges:
        assert charge.meets_cost(make_profile(rich, winner))
        assert not charge.meets_cost(make_profile(poor, winner))
        # Another seat sees the same frame kind but is not reward place 1.
        loser = (winner + 1) % 4
        other = with_player(rich, loser, resources=Resources(solari=20, spice=20))
        assert not charge.meets_cost(make_profile(other, loser))


def test_control_the_spice_real_profile_value_terms(turn_state: GameState) -> None:
    # Hard, round 1 (Early): TrashCardEarly 2.75 and TrashMod = the best
    # TrashValue in discard + play (Dagger 1.0 <= 1.5); E names the junk
    # Dagger; V at no space is the same four terms (GetSpiceValue(-1) ==
    # -GetSpiceValue(1), §2.3).
    cts = starter("control_the_spice")
    dagger = starter("dagger")
    state = with_player(
        resources(turn_state, spice=2),
        SEAT,
        hand=(starter("diplomacy").ref,),
        in_play=(cts.ref,),
        discard_pile=(dagger.ref,),
    )
    p = make_profile(state, SEAT)
    ability = e.ControlTheSpiceAbility(cts)
    assert p.trash_card_value() == 2.75
    assert p.trash_mod() == 1.0
    answer = ability.evaluate(p, ability.target_request(p))
    assert e.ControlTheSpiceAbility.trash_target(answer) == dagger.ref
    terms = -p.spice_value(1) + 2.75 + 1.0 + p.troop_value(1, False)
    assert answer.value == pytest.approx(terms)
    assert ability.value_for_player(p).sum == pytest.approx(answer.value)


def test_economic_supremacy_rewards_are_reachable() -> None:
    card = es()
    first, second, third = (b.place_reward_ability(card, n) for n in (1, 2, 3))
    assert isinstance(first, e.EconomicSupremacyFirstAbility)
    assert isinstance(second, e.EconomicSupremacySecondAbility)
    assert isinstance(third, e.EconomicSupremacyThirdAbility)
    assert b.place_reward_ability(card, 4) is None
    granted = b.granted_reward_abilities(card, 1)
    assert [type(a) for a in granted] == [
        e.EconomicSupremacySolariAbility,
        e.EconomicSupremacySpiceAbility,
    ]
    assert all(a.owner == card for a in granted)
    assert b.granted_reward_abilities(card, 2) == ()
    assert b.granted_reward_abilities(card, 3) == ()


@pytest.mark.parametrize("choam", [False, True])
def test_generic_rewards_are_granted_from_the_reward_archetypes(choam: bool) -> None:
    # The same abilities the combat windows reach through the catalog.
    for conflict_id in ("battle_for_spice_refinery", "propaganda", "trade_dispute"):
        card = conflict_entity(conflict_id, choam)
        rewards = conflict_reward_entities(conflict_id, choam)
        for place in (1, 2, 3):
            got = b.granted_reward_abilities(card, place)
            want = abilities_of(rewards[place - 1])
            assert [(type(a), a.owner) for a in got] == [
                (type(a), a.owner) for a in want
            ]


def test_economic_supremacy_conflict_value_is_the_three_rewards(
    turn_state: GameState,
) -> None:
    # WormConflictPlayable::ConflictValue merges every card ability's V:
    # First + Second + Third + 0 (Solari charge) + 0 (Spice charge).
    state = resources(turn_state, solari=7, spice=5, water=1)
    p = make_profile(state, SEAT)
    card = es()
    parts = [
        cls(card).value_for_player(p).sum
        for cls in (
            e.EconomicSupremacyFirstAbility,
            e.EconomicSupremacySecondAbility,
            e.EconomicSupremacyThirdAbility,
        )
    ]
    assert p._conflict_value(card).sum == pytest.approx(sum(parts))
    first = e.EconomicSupremacyFirstAbility(card).value_for_player(p).sum
    assert first == pytest.approx(
        p.solari_value(-6) + p.spice_value(1) * -4.0 + p.victory_point_value(3)
    )
