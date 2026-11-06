"""The economy part of the ``WormAIProfile`` port (``profile/economy.py``).

Spec: ``analysis/ai/spec/profile-economy.md`` (with ``03-resource-valuation.md``
for the worked example). Each test builds a real game state, adjusts the fields
the formula reads, and stubs the methods other areas own (combat, influence and
the ability ports) on the ``Profile`` instance, so only this module's
arithmetic and branch order are under test.
"""

import random
from collections.abc import Callable, Sequence
from dataclasses import replace
from functools import cache
from types import MappingProxyType
from typing import Any, cast

import pytest

from dune_imperium.agents.app_ai import testing as _conftest
from dune_imperium.agents.app_ai.abilities.base import PORTS, Ability
from dune_imperium.agents.app_ai.catalog import card_entity, space_entity
from dune_imperium.agents.app_ai.context import Board, card_id
from dune_imperium.agents.app_ai.data.archetypes import Archetype
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile, economy
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.core.state import GameState

ME = 3  # Lady Jessica, first player and first to decide in round 1.


def first_decision(kind: str) -> GameState:
    return _conftest.first_decision(kind)


def make_profile(
    state: GameState, seat: int, *, level: int = 2, rng_seed: int = 0
) -> Profile:
    return _conftest.make_profile(state, seat, level=level, rng_seed=rng_seed)


def with_player(state: GameState, seat: int, **changes: object) -> GameState:
    return _conftest.with_player(state, seat, **changes)


def with_state(state: GameState, **changes: object) -> GameState:
    return _conftest.with_state(state, **changes)


# -- states ------------------------------------------------------------------------


@cache
def base_state() -> GameState:
    """Round 1, the first Agent turn (seat 3): starters only, no Conflict won."""

    return first_decision("turn")


@cache
def reveal_state() -> GameState:
    """The first Reveal frame (seat 3's own Reveal, hand already revealed)."""

    return first_decision("reveal")


def troops(garrison: int = 0, conflict: int = 0) -> dict[str, int]:
    """Troop fields that keep the 12-troop invariant."""

    return {
        "troops_garrison": garrison,
        "troops_conflict": conflict,
        "troops_supply": 12 - garrison - conflict,
    }


def with_conflict(state: GameState, conflict_id: str | None) -> GameState:
    """``state`` with ``conflict_id`` face up (and nowhere else), or none."""

    if conflict_id is None:
        return with_state(state, current_conflict_ids=())
    return with_state(
        state,
        current_conflict_ids=(conflict_id,),
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
        ),
    )


def with_pool(state: GameState, persuasion: int) -> GameState:
    """The open Reveal frame with ``persuasion`` left to spend."""

    frame = state.decision_stack[-1]
    assert frame.kind == "reveal"
    context = tuple(
        (key, persuasion if key == "persuasion" else value)
        for key, value in frame.context
    )
    stack = (*state.decision_stack[:-1], replace(frame, context=context))
    return with_state(state, decision_stack=stack)


def with_contracts(
    state: GameState,
    *,
    completed: tuple[str, ...] = (),
    active: tuple[str, ...] = (),
    seat: int = ME,
) -> GameState:
    """Seat ``seat`` holding these contracts (taken out of the shared zones)."""

    taken = {*completed, *active}
    state = with_state(
        state,
        contract_bank=tuple(c for c in state.contract_bank if c not in taken),
        face_up_contract_ids=tuple(
            c for c in state.face_up_contract_ids if c not in taken
        ),
    )
    return with_player(
        state, seat, completed_contract_ids=completed, active_contract_ids=active
    )


TWO_POSTS = (
    "emperor-sardaukar-dutiful-service",
    "spacing-guild-heighliner-deliver-supplies",
)


def starter(name: str, copy: int = 0, seat: int = ME) -> str:
    return f"player:{seat}:starter:{name}:{copy}"


def imperium(name: str, copy: int = 0) -> str:
    return f"imperium:{name}:{copy}"


def card(instance_id: str) -> Entity:
    return card_entity(instance_id)


def fake_card(**attributes: object) -> Entity:
    """A card entity with made-up archetype attributes."""

    archetype = Archetype(
        short="Fake.Card",
        kind="imperium",
        title=None,
        in_uprising=True,
        in_uprising_choam=True,
        attributes=MappingProxyType(dict(attributes)),
    )
    return Entity(Kind.CARD, "imperium:fake:0", archetype)


# -- profiles ----------------------------------------------------------------------


def prof(
    state: GameState,
    monkeypatch: pytest.MonkeyPatch,
    *,
    seat: int = ME,
    level: int = 2,
    combat_order: Sequence[int] = (0, 1, 2, 3),
    interest: float = 0.0,
    lower_bound: float = -10.0,
) -> Profile:
    """A profile with the other areas' methods stubbed to known values."""

    profile = make_profile(state, seat, level=level)
    monkeypatch.setattr(profile, "current_combat_order", lambda: list(combat_order))
    monkeypatch.setattr(profile, "current_conflict_interest", lambda: Summer(interest))
    monkeypatch.setattr(
        profile, "conflict_posture_bounds", lambda: (lower_bound, lower_bound + 15)
    )
    monkeypatch.setattr(profile, "combat_posture_mod", lambda: 2.0)
    monkeypatch.setattr(
        profile,
        "gain_influence_value",
        lambda faction, amount, rank=-1, alliance=False: Summer(2.0),
    )
    return profile


def early(**changes: object) -> GameState:
    """Round 2 (Early arc) with seat 3 changed by ``changes``."""

    return with_player(with_state(base_state(), round_number=2), ME, **changes)


def late(**changes: object) -> GameState:
    """Round 8 (Late arc) with seat 3 changed by ``changes``."""

    return with_player(with_state(base_state(), round_number=8), ME, **changes)


def resources(solari: int = 0, spice: int = 0, water: int = 1) -> Any:
    return replace(
        base_state().players[ME].resources, solari=solari, spice=spice, water=water
    )


# =================================================================================
# §1 Game arc, climax, final round, end-of-round score
# =================================================================================


@pytest.mark.parametrize(
    ("round_number", "arc"), [(1, 0), (3, 0), (4, 1), (6, 1), (7, 2), (9, 2)]
)
def test_game_arc_by_round(
    round_number: int, arc: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = with_state(base_state(), round_number=round_number)
    assert prof(state, monkeypatch).game_arc() == arc


def test_game_arc_is_late_in_climax(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = prof(base_state(), monkeypatch)
    profile._is_climax = True
    assert profile.game_arc() == 2


def test_is_climax_false_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = prof(base_state(), monkeypatch)
    calls: list[int] = []

    def order() -> list[int]:
        calls.append(1)
        return [0, 1, 2, 3]

    monkeypatch.setattr(profile, "current_combat_order", order)
    assert profile.is_climax() is False
    assert profile.is_climax() is False
    assert profile._is_climax is False
    assert calls == [1]  # frozen for the decision


def test_is_climax_one_player_at_trigger_minus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = with_player(base_state(), 1, victory_points=9)
    assert prof(state, monkeypatch).is_climax() is True


def test_is_climax_needs_two_players_at_trigger_minus_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    one = with_player(base_state(), 1, victory_points=8)
    assert prof(one, monkeypatch).is_climax() is False
    two = with_player(one, 2, victory_points=8)
    assert prof(two, monkeypatch).is_climax() is True


def test_is_climax_with_fewer_than_two_conflict_cards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = base_state()
    two = with_state(state, conflict_deck=state.conflict_deck[:2])
    assert prof(two, monkeypatch).is_climax() is False
    one = with_state(state, conflict_deck=state.conflict_deck[:1])
    assert prof(one, monkeypatch).is_climax() is True


def _seven_vp_battle_for_arrakeen() -> GameState:
    """Seat 0 at 7 VP could score 10 this round (VP 1, spies VP 1, icon 1)."""

    state = with_conflict(base_state(), "battle_for_arrakeen")
    return with_player(
        state,
        0,
        victory_points=7,
        spies_supply=1,
        spy_post_ids=(
            "emperor-sardaukar-dutiful-service",
            "spacing-guild-heighliner-deliver-supplies",
        ),
    )


def test_is_climax_from_the_two_strongest_possible_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _seven_vp_battle_for_arrakeen()
    assert prof(state, monkeypatch, combat_order=(1, 0, 2, 3)).is_climax() is True
    assert prof(state, monkeypatch, combat_order=(1, 2, 0, 3)).is_climax() is False


def test_is_final_round_branches_and_no_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    state = base_state()
    empty_deck = with_state(state, conflict_deck=())
    assert prof(empty_deck, monkeypatch).is_final_round() is True
    ten = with_player(state, 2, victory_points=10)
    assert prof(ten, monkeypatch).is_final_round() is True
    possible = _seven_vp_battle_for_arrakeen()
    assert prof(possible, monkeypatch, combat_order=(0, 1, 2, 3)).is_final_round()
    profile = prof(possible, monkeypatch, combat_order=(2, 3, 0, 1))
    calls: list[int] = []

    def order() -> list[int]:
        calls.append(1)
        return [2, 3, 0, 1]

    monkeypatch.setattr(profile, "current_combat_order", order)
    assert profile.is_final_round() is False
    assert profile.is_final_round() is False
    assert calls == [1, 1]  # _isFinalRound is never written
    assert profile._is_final_round is None


def test_possible_end_of_round_score_without_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = with_conflict(with_player(base_state(), 0, victory_points=4), None)
    assert prof(state, monkeypatch).possible_end_of_round_score(0) == 4


def test_possible_end_of_round_score_recall_two_spies_and_icon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _seven_vp_battle_for_arrakeen()
    profile = prof(state, monkeypatch)
    # 7 + reward VP 1 + Recall2SpiesVP 1 + Crysknife objective 1.
    assert profile.possible_end_of_round_score(0) == 10
    no_icon = with_player(state, 0, objective_ids=())
    assert prof(no_icon, monkeypatch).possible_end_of_round_score(0) == 9
    one_spy = with_player(
        no_icon,
        0,
        spies_supply=2,
        spy_post_ids=("emperor-sardaukar-dutiful-service",),
    )
    assert prof(one_spy, monkeypatch).possible_end_of_round_score(0) == 8
    # A sandworm counts the 1st-place reward again with doubleCost: the
    # Recall2Spies VP is not doubled (0 when doubleCost), the reward VP is.
    worm = with_player(no_icon, 0, sandworms_conflict=1)
    assert prof(worm, monkeypatch).possible_end_of_round_score(0) == 7 + 2 + 1


@pytest.mark.parametrize(
    ("spice", "worm", "expected"),
    [(3, 0, 1), (4, 0, 2), (4, 1, 3), (7, 1, 3), (8, 1, 4)],
)
def test_possible_end_of_round_score_pay_spice_for_vp(
    spice: int, worm: int, expected: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = with_conflict(base_state(), "battle_for_imperial_basin")
    state = with_player(
        state,
        1,
        victory_points=0,
        objective_ids=(),
        sandworms_conflict=worm,
        resources=resources(spice=spice),
    )
    assert prof(state, monkeypatch).possible_end_of_round_score(1) == expected


@pytest.mark.parametrize(("solari", "expected"), [(5, 1), (6, 2), (12, 2)])
def test_possible_end_of_round_score_pay_solari_for_vp(
    solari: int, expected: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = with_conflict(base_state(), "battle_for_spice_refinery")
    state = with_player(
        state, 1, victory_points=0, objective_ids=(), resources=resources(solari)
    )
    assert prof(state, monkeypatch).possible_end_of_round_score(1) == expected


def test_possible_end_of_round_score_pay_three_spice_without_reward_vp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = with_conflict(base_state(), "spice_freighters")
    poor = with_player(state, 1, victory_points=2, resources=resources(spice=2))
    assert prof(poor, monkeypatch).possible_end_of_round_score(1) == 2
    rich = with_player(state, 1, victory_points=2, resources=resources(spice=3))
    assert prof(rich, monkeypatch).possible_end_of_round_score(1) == 3


def test_select_for_game_arc(monkeypatch: pytest.MonkeyPatch) -> None:
    mid = prof(with_state(base_state(), round_number=5), monkeypatch)
    assert mid.select_for_game_arc([1.0, 2.0, 3.0]) == 2.0
    assert mid.select_for_game_arc([1.0, 2.0]) == 0.0


# =================================================================================
# §2-3 Abundance and GetResourceValue
# =================================================================================


@pytest.mark.parametrize(
    ("solari", "level"), [(0, 0), (2, 0), (3, 1), (7, 1), (8, 2), (9, 3), (20, 3)]
)
def test_abundance_level_solari_bands(
    solari: int, level: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = prof(early(resources=resources(solari)), monkeypatch)
    assert profile.abundance_level(Attr.SOLARI) == level


def test_abundance_level_reads_garrison_intrigue_and_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = prof(
        early(
            **troops(garrison=4),
            intrigue_cards=("intrigue:detonation:0", "intrigue:devour:0"),
        ),
        monkeypatch,
    )
    assert profile.abundance_level(Attr.TROOPS) == 2
    assert profile.abundance_level(Attr.INTRIGUE_CARD) == 2
    assert profile.abundance_level(Attr.PERSUASION) == -1
    assert profile.abundance_level(Attr.SANDWORMS) == -1


def _example_round_2() -> GameState:
    """03 worked example, round 2: VP 1, 2 Solari, 1 spice, 1 water, 3 troops."""

    return early(victory_points=1, resources=resources(2, 1, 1), **troops(garrison=3))


def _example_round_8() -> GameState:
    """03 worked example, round 8: VP 6, 5/4/2, garrison 4, 6 in supply, titles."""

    return late(
        victory_points=6,
        resources=resources(5, 4, 2),
        troops_garrison=4,
        troops_conflict=2,
        troops_supply=6,
        swordmaster_acquired=True,
        agents_available=3,
        high_council=True,
        intrigue_cards=("intrigue:tactical_option:0",),
    )


def test_worked_example_round_2_hard(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = prof(_example_round_2(), monkeypatch)
    assert profile.spice_value(2) == pytest.approx(5.0)
    assert profile.water_value(1) == pytest.approx(2.8125)
    assert profile.victory_point_value(1) == pytest.approx(6.0)
    assert profile.troop_value(2) == pytest.approx(2.5)
    assert profile.solari_value(1) == pytest.approx(0.65 * 1.25 * 1.1 * 1.6)
    assert profile.intrigue_value() == pytest.approx(2.8125)


def test_worked_example_round_8_hard(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = prof(_example_round_8(), monkeypatch)
    assert profile.spice_value(2) == pytest.approx(3.0)
    assert profile.water_value(1) == pytest.approx(1.3)
    assert profile.victory_point_value(1) == pytest.approx(9.0)
    assert profile.troop_value(2) == pytest.approx(1.25)
    assert profile.solari_value(1) == pytest.approx(0.25)
    assert profile.intrigue_value() == pytest.approx(2.75)
    nine = prof(late(victory_points=9), monkeypatch)
    assert nine.victory_point_value(1) == pytest.approx(18.0)


@pytest.mark.parametrize(
    ("level", "spice", "water", "late_troops"),
    [(1, 4.2, 2.3625, 2.5), (0, 3.4, 1.9125, 2.875)],
)
def test_worked_example_other_levels(
    level: int,
    spice: float,
    water: float,
    late_troops: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    round_2 = prof(_example_round_2(), monkeypatch, level=level)
    assert round_2.spice_value(2) == pytest.approx(spice)
    assert round_2.water_value(1) == pytest.approx(water)
    round_8 = prof(_example_round_8(), monkeypatch, level=level)
    assert round_8.troop_value(2) == pytest.approx(late_troops)


def test_multiply_replays_the_apps_add_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """``Multiply`` appends ``m*Sum - Sum``; the result is bit-exact to that."""

    value = prof(_example_round_2(), monkeypatch).solari_value(3)
    expected = 0.65
    for factor in (1.25, 1.1, 1.6, 3.0):
        expected = expected + (factor * expected - expected)
    assert value == expected
    # Early, flooded with Solari, both titles held: 0.65 x 0.25 x 1. The app's
    # order gives 0.16249999999999998, a plain product 0.1625.
    flooded = early(
        resources=resources(solari=9),
        high_council=True,
        swordmaster_acquired=True,
        agents_available=3,
    )
    assert prof(flooded, monkeypatch).solari_value(1) == 0.16249999999999998
    assert 0.65 * 0.25 * 1.0 == 0.1625


def test_resource_value_zero_amount_and_unvalued_attributes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = prof(_example_round_2(), monkeypatch)
    assert profile.resource_value(Attr.SPICE, 0) == 0.0
    assert profile.resource_value(Attr.VICTORY_POINTS, 3) == 0.0
    assert profile.resource_value(Attr.INTRIGUE_CARD, 1) == 0.0


@pytest.mark.parametrize(
    ("solari", "expected"),
    [(8, 0.25 * 0.5 * 0.5), (9, 0.25 * 0.25 * 0.25), (3, 0.25)],
)
def test_late_solari_takes_the_abundance_mod_twice(
    solari: int, expected: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = prof(late(resources=resources(solari)), monkeypatch)
    assert profile.solari_value(1) == pytest.approx(expected)


def test_early_rich_solari_takes_it_once_and_missing_titles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rich = prof(early(resources=resources(8)), monkeypatch)
    assert rich.solari_value(1) == pytest.approx(0.65 * 0.5 * 1.1 * 1.6)
    titled = prof(
        early(
            resources=resources(8),
            high_council=True,
            swordmaster_acquired=True,
            agents_available=3,
        ),
        monkeypatch,
    )
    assert titled.solari_value(1) == pytest.approx(0.65 * 0.5)
    medium = prof(early(resources=resources(8)), monkeypatch, level=1)
    assert medium.solari_value(1) == pytest.approx(0.65 * 1.0 * 1.0 * 1.0)


@pytest.mark.parametrize(
    ("intrigues", "attr", "factor"),
    [
        (("buy_access",), Attr.SOLARI, 1.2),
        (("market_opportunity",), Attr.SOLARI, 1.2),
        (("mercenaries",), Attr.SOLARI, 1.1),
        (("market_opportunity",), Attr.SPICE, 1.1),
        (("strategic_stockpiling",), Attr.SPICE, 1.2),
        (("unexpected_allies",), Attr.WATER, 1.2),
        (("strategic_stockpiling",), Attr.WATER, 1.0),  # needs 2 Fremen
    ],
)
def test_uprising_intrigue_multipliers(
    intrigues: tuple[str, ...],
    attr: Attr,
    factor: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plain = prof(early(resources=resources(3, 3, 2)), monkeypatch)
    held = prof(
        early(
            resources=resources(3, 3, 2),
            intrigue_cards=tuple(f"intrigue:{i}:0" for i in intrigues),
        ),
        monkeypatch,
    )
    assert held.resource_value(attr, 1) == pytest.approx(
        plain.resource_value(attr, 1) * factor
    )


def test_water_hooks_and_stockpiling_with_two_fremen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = early(resources=resources(water=2))
    plain = prof(base, monkeypatch).water_value(1)
    assert plain == pytest.approx(2.25)
    hooks = prof(with_player(base, ME, maker_hooks=True), monkeypatch)
    assert hooks.water_value(1) == pytest.approx(2.25 * 1.25)
    fremen = with_player(
        base,
        ME,
        influence=replace(base.players[ME].influence, fremen=2),
        intrigue_cards=("intrigue:strategic_stockpiling:0",),
    )
    assert prof(fremen, monkeypatch).water_value(1) == pytest.approx(2.25 * 1.2)


@pytest.mark.parametrize(
    ("shorts", "leader", "attr", "factor"),
    [
        ((economy._CHOAM_SHARES,), "", Attr.SOLARI, 1.25),
        ((economy._SLEEPER_MUST_AWAKEN,), "", Attr.SPICE, 1.25),
        ((economy._PRIVATE_ARMY,), "", Attr.SPICE, 1.1),
        ((economy._RAPID_MOBILIZATION,), "", Attr.TROOPS, 1.3),
        ((economy._STAGED_INCIDENT,), "", Attr.TROOPS, 1.2),
        ((), economy._GLOSSU_RABBAN, Attr.TROOPS, 0.9),
        ((), economy._DUKE_LETO, Attr.SPICE, 1.1),
        ((), economy._EARL_MEMNON, Attr.SPICE, 0.9),
        ((), economy._COUNTESS_ARIANA, Attr.WATER, 0.95),
    ],
)
def test_base_set_intrigue_and_leader_multipliers(
    shorts: tuple[str, ...],
    leader: str,
    attr: Attr,
    factor: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Base-set cards are never dealt with our content: fake the holdings.
    state = early(resources=resources(3, 3, 2), **troops(garrison=2))
    plain = prof(state, monkeypatch).resource_value(attr, 1)
    profile = prof(state, monkeypatch)
    monkeypatch.setattr(profile, "_intrigue_shorts", lambda: list(shorts))
    monkeypatch.setattr(profile, "_leader_short", lambda: leader)
    assert profile.resource_value(attr, 1) == pytest.approx(plain * factor)


def test_staged_incident_needs_few_troops(monkeypatch: pytest.MonkeyPatch) -> None:
    # Total troops (conflict + garrison) must be at most 3.0.
    state = early(**troops(garrison=4))
    plain = prof(state, monkeypatch).troop_value(1)
    profile = prof(state, monkeypatch)
    monkeypatch.setattr(profile, "_intrigue_shorts", lambda: [economy._STAGED_INCIDENT])
    assert profile.troop_value(1) == pytest.approx(plain)


def test_strength_is_worthless_with_no_units_and_one_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    two_agents = prof(early(agents_available=2), monkeypatch)
    assert two_agents.strength_value(3) == pytest.approx(0.66 * 3)
    one_agent = prof(
        early(agents_available=1, agent_locations=("secrets",)), monkeypatch
    )
    assert one_agent.strength_value(3) == 0.0
    deployed = prof(
        early(agents_available=1, agent_locations=("secrets",), **troops(1, 1)),
        monkeypatch,
    )
    assert deployed.strength_value(3) == pytest.approx(0.66 * 3)


def test_combat_posture_flag_multiplies_units(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = prof(early(**troops(garrison=3)), monkeypatch)
    assert profile.strength_value(1, True) == pytest.approx(0.66 * 2.0)
    assert profile.troop_value(1, True) == pytest.approx(1.25 * 2.0)
    assert profile.dreadnought_value(1, True) == pytest.approx(6.0 * 2.0)
    assert profile.sandworm_value(1, True) == pytest.approx(3.0 * 2.0)
    assert profile.spice_value(1) == pytest.approx(2.0 * 1.25)


def test_troops_are_capped_at_the_supply(monkeypatch: pytest.MonkeyPatch) -> None:
    one_left = prof(
        early(troops_garrison=3, troops_conflict=8, troops_supply=1), monkeypatch
    )
    assert one_left.troop_value(2) == pytest.approx(1.25)
    none_left = prof(
        early(troops_garrison=3, troops_conflict=9, troops_supply=0), monkeypatch
    )
    assert none_left.troop_value(2) == 0.0
    assert none_left.troop_value(-2) == pytest.approx(-2.5)  # Min(neg, 0)


def test_persuasion_adds_buy_gains_once(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = prof(early(), monkeypatch)
    calls: list[int] = []

    def gains(amount: int) -> float:
        calls.append(amount)
        return 0.75

    monkeypatch.setattr(profile, "buy_gains", gains)
    assert profile.persuasion_value(2) == pytest.approx(1.0 * 2 + 0.75)
    assert calls == [2]


def test_specimen_and_dreadnought_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = prof(early(), monkeypatch)
    assert profile.specimen_value(2) == pytest.approx(1.0 * 1.25 * 2)
    assert profile.dreadnought_value(1) == pytest.approx(6.0)


def test_sandworm_value_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    state = early(
        leader_id="muad_dib",
        leader_face_id="muad_dib",
        maker_hooks=True,
        intrigue_cards=("intrigue:detonation:0", "intrigue:devour:0"),
    )
    profile = prof(state, monkeypatch, interest=0.0, lower_bound=-10.0)
    # 3 + IntrigueValue (2 held: Rich 2.25*0.5) + Detonation 4, x Devour 1.1, x 2.
    assert profile.sandworm_value(2) == pytest.approx((3.0 + 1.125 + 4.0) * 1.1 * 2)
    cold = prof(state, monkeypatch, interest=0.0, lower_bound=5.0)
    assert cold.sandworm_value(2) == pytest.approx((3.0 + 1.125) * 1.1 * 2)
    awe = early(
        maker_hooks=True,
        intrigue_cards=("intrigue:inspire_awe:0", "intrigue:special_mission:0"),
    )
    assert prof(awe, monkeypatch).sandworm_value(1) == pytest.approx(3.0 * 1.1 + 4.0)
    no_hooks = early(intrigue_cards=("intrigue:special_mission:0",))
    assert prof(no_hooks, monkeypatch).sandworm_value(1) == pytest.approx(3.0)


def test_sandworm_value_always_computes_the_interest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = prof(early(), monkeypatch)
    calls: list[int] = []

    def interest() -> Summer:
        calls.append(1)
        return Summer(0.0)

    monkeypatch.setattr(profile, "current_conflict_interest", interest)
    assert profile.sandworm_value(1) == pytest.approx(3.0)
    assert calls == [1]


# =================================================================================
# §4 Scalars
# =================================================================================


@pytest.mark.parametrize(
    ("victory_points", "amount", "expected"),
    [(7, 2, 12.0), (8, 2, 24.0), (1, 1, 6.0), (8, -1, -6.0)],
)
def test_victory_point_value_doubles_from_ten(
    victory_points: int,
    amount: int,
    expected: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = prof(early(victory_points=victory_points), monkeypatch)
    assert profile.victory_point_value(amount) == pytest.approx(expected)


def test_card_draw_values(monkeypatch: pytest.MonkeyPatch) -> None:
    state = early(
        deck=(starter("convincing_argument"), starter("dagger")),
        hand=(),
    )
    profile = prof(state, monkeypatch)
    assert profile.card_draw_value() == 1.5
    calls: list[int] = []

    def gains(amount: int) -> float:
        calls.append(amount)
        return 0.4

    monkeypatch.setattr(profile, "buy_gains", gains)
    assert profile.card_draw_value_with_buy_gains() == pytest.approx(1.9)
    assert calls == [1]  # the mean deck Persuasion (2 + 0) / 2


@pytest.mark.parametrize(
    ("held", "expected"),
    [(0, 2.25 * 1.25), (1, 2.25), (2, 2.25 * 0.5), (3, 2.25 * 0.25)],
)
def test_intrigue_value_by_hand_size(
    held: int, expected: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    cards = ("tactical_option", "detonation", "devour", "cunning")[:held]
    profile = prof(
        early(intrigue_cards=tuple(f"intrigue:{c}:0" for c in cards)), monkeypatch
    )
    assert profile.intrigue_value() == pytest.approx(expected)


@pytest.mark.parametrize(
    ("round_number", "level", "values"),
    [
        (2, 2, (2.75, 1.2, 50.0, 15.0, 3.0, 2.25, 4.0, 6.0, -1.0)),
        (5, 2, (2.0, 1.7, 50.0, 9.0, 1.5, 3.5, 1.75, 3.0, -1.0)),
        (8, 2, (1.0, 2.2, 10.0, 5.0, 0.5, 4.5, 0.33, 1.0, -1.0)),
        (5, 1, (2.0, 0.75, 50.0, 9.0, 1.5, 3.5, 1.75, 3.0, -1.0)),
        (8, 0, (1.0, 0.5, 10.0, 5.0, 0.5, 4.5, 0.33, 1.0, -1.0)),
    ],
)
def test_arc_indexed_scalars(
    round_number: int,
    level: int,
    values: tuple[float, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = prof(
        with_state(base_state(), round_number=round_number), monkeypatch, level=level
    )
    got = (
        profile.trash_card_value(),
        profile.minimum_acquire_value(),
        profile.swordmaster_value(),
        profile.high_council_value(),
        profile.foldspace_value(),
        profile.mentat_value(),
        profile.control_solari_value(),
        profile.control_spice_value(),
        profile.discard_value(),
    )
    assert got == pytest.approx(values)
    spice, solari = values[7], values[6]
    assert profile.control_value_avg() == pytest.approx((spice + 2 * solari) / 3.0)


def test_mentat_value_base_set_intrigue_mods(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = prof(early(), monkeypatch)
    monkeypatch.setattr(
        profile,
        "_intrigue_shorts",
        lambda: [economy._CALCULATED_HIRE, economy._URGENT_MISSION],
    )
    assert profile.mentat_value() == pytest.approx((2.25 * 0.33) * 0.5)


def test_trash_mod(monkeypatch: pytest.MonkeyPatch) -> None:
    none = prof(early(discard_pile=(), in_play=()), monkeypatch)
    assert none.trash_mod() == -1.0
    bought = prof(early(in_play=(imperium("calculus_of_power"),)), monkeypatch)
    assert bought.trash_mod() == -1.0  # TrashValue 0
    recon = prof(
        early(
            hand=(starter("dagger"),),
            discard_pile=(starter("reconnaissance"), starter("convincing_argument")),
        ),
        monkeypatch,
    )
    assert recon.trash_mod() == 0.5
    dagger = prof(
        early(
            hand=(),
            discard_pile=(starter("reconnaissance"),),
            in_play=(starter("dagger"),),
        ),
        monkeypatch,
    )
    assert dagger.trash_mod() == 1.0
    capped = prof(early(), monkeypatch)
    monkeypatch.setattr(
        capped, "_own_cards", lambda *zones: [fake_card(TrashValue=2.0)]
    )
    assert capped.trash_mod() == 1.5


# =================================================================================
# §5 Persuasion forecast and the knapsack
# =================================================================================


def test_reveal_preview_outside_the_reveal_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hand = (
        starter("reconnaissance"),
        starter("convincing_argument", 1),
        starter("convincing_argument"),
        starter("dagger"),
    )
    plain = prof(early(hand=hand), monkeypatch)
    assert plain.possible_persuasion() == 1 + 2 + 2 + 0
    seated = prof(
        early(
            hand=hand,
            high_council=True,
            agents_available=1,
            agent_locations=("assembly_hall",),
        ),
        monkeypatch,
    )
    assert seated.possible_persuasion() == 5 + 2 + 1


@pytest.mark.parametrize(
    ("hand", "changes", "expected"),
    [
        ((imperium("desert_power"),), {}, 0),  # app Persuasion attribute 0
        ((imperium("bene_gesserit_operative", 1),), {}, 1),
        (
            (imperium("bene_gesserit_operative", 1),),
            {"spies_supply": 1, "spy_post_ids": TWO_POSTS},
            3,
        ),
        ((imperium("calculus_of_power", 1),), {}, 2),
        ((imperium("sardaukar_coordination"),), {}, 2),
        ((imperium("in_high_places"),), {}, 2),
        ((imperium("treacherous_maneuver"),), {}, 1),
        ((imperium("undercover_asset"),), {}, 0),
        (
            (imperium("interstellar_trade"),),
            {"completed_contract_ids": ("contract:immediate", "contract:acquire")},
            2,
        ),
        ((imperium("paracompass"),), {}, 0),
        ((imperium("paracompass"),), {"high_council": True}, 2 + 2),
        (
            (imperium("paracompass"),),
            {"high_council": True, "swordmaster_acquired": True, "agents_available": 3},
            3 + 2,
        ),
        ((imperium("southern_elders"),), {}, 0),
        ((imperium("southern_elders"), imperium("maula_pistol")), {}, 2 + 1),
        ((imperium("southern_elders"),), {"in_play": (imperium("maula_pistol"),)}, 2),
        ((imperium("stilgar_the_devoted"),), {}, 2),
        ((imperium("stilgar_the_devoted"), imperium("maula_pistol")), {}, 4 + 1),
    ],
)
def test_reveal_preview_overrides(
    hand: tuple[str, ...],
    changes: dict[str, object],
    expected: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = changes.pop("completed_contract_ids", ())
    state = early(hand=hand, **changes)
    state = with_contracts(state, completed=cast(tuple[str, ...], completed))
    assert prof(state, monkeypatch).possible_persuasion() == expected


def test_reveal_preview_in_the_reveal_turn_is_the_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = with_pool(reveal_state(), 7)
    state = with_player(state, ME, high_council=True)
    profile = prof(state, monkeypatch)
    assert profile._in_reveal_turn()
    assert profile.possible_persuasion() == 7  # no High Council +2 here


def test_possible_persuasion_gain(monkeypatch: pytest.MonkeyPatch) -> None:
    half = prof(
        early(deck=(starter("dune_the_desert_planet"), starter("dagger")), hand=()),
        monkeypatch,
    )
    assert half.possible_persuasion_gain() == 0  # 0.5 rounds half to even
    desert = prof(
        early(deck=(imperium("desert_power"), starter("convincing_argument")), hand=()),
        monkeypatch,
    )
    assert desert.possible_persuasion_gain() == 1  # Desert Power counts 0
    from_discard = prof(
        early(
            deck=(),
            hand=(),
            discard_pile=(
                starter("convincing_argument"),
                starter("convincing_argument", 1),
                starter("dune_the_desert_planet"),
            ),
        ),
        monkeypatch,
    )
    assert from_discard.possible_persuasion_gain() == 2  # 5/3
    empty = prof(early(deck=(), hand=(), discard_pile=()), monkeypatch)
    assert empty.possible_persuasion_gain() == 0


ROW = (
    imperium("calculus_of_power"),  # cost 3
    imperium("spy_network"),  # cost 2
    imperium("strike_fleet"),  # cost 5
    imperium("sardaukar_soldier"),  # cost 1
    imperium("truthtrance"),  # cost 4
)
ROW_VALUES = {
    "calculus_of_power": 3.0,
    "spy_network": 2.0,
    "strike_fleet": 5.0,
    "sardaukar_soldier": 0.5,
    "truthtrance": -1.0,
    "prepare_the_way": 1.8,  # cost 2
    "the_spice_must_flow": 3.8,  # cost 9
}


def row_profile(
    monkeypatch: pytest.MonkeyPatch,
    values: dict[str, float] | None = None,
    reserve: tuple[tuple[str, int], ...] = (
        ("prepare_the_way", 8),
        ("the_spice_must_flow", 10),
    ),
) -> Profile:
    table = dict(ROW_VALUES if values is None else values)
    state = with_state(early(), imperium_row=ROW, reserve_stacks=reserve)
    profile = prof(state, monkeypatch)
    monkeypatch.setattr(
        profile, "acquire_value", lambda c: Summer(table[card_id(c.ref)])
    )
    return profile


def refs(cards: Sequence[Entity]) -> list[str]:
    return [card_id(c.ref) for c in cards]


@pytest.mark.parametrize(
    ("persuasion", "expected"),
    [
        (5, ["spy_network", "calculus_of_power"]),  # ties keep low indices
        (4, ["prepare_the_way", "spy_network"]),  # yield order: descending index
        (3, ["calculus_of_power"]),
        (1, ["sardaukar_soldier"]),
        (0, []),
        (-1, []),
        (
            9,  # Strike Fleet + Spy Network + Prepare the Way = 8.8
            ["prepare_the_way", "strike_fleet", "spy_network"],
        ),
    ],
)
def test_predict_card_buys(
    persuasion: int, expected: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = row_profile(monkeypatch)
    assert refs(profile.predict_card_buys(persuasion)) == expected


def test_predict_card_buys_skips_an_empty_reserve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = row_profile(
        monkeypatch, reserve=(("prepare_the_way", 0), ("the_spice_must_flow", 10))
    )
    assert refs(profile.predict_card_buys(4)) == [
        "sardaukar_soldier",
        "calculus_of_power",
    ]


def test_buy_gains_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    values = dict(ROW_VALUES, strike_fleet=7.0)
    profile = row_profile(monkeypatch, values)
    monkeypatch.setattr(profile, "_reveal_preview_persuasion", lambda: 3)
    # knapsack(3) = 3.0 (Calculus); knapsack(5) = 7.0 (Strike Fleet).
    assert profile.buy_gains(2) == pytest.approx((7.0 - 3.0) - 2)
    # knapsack(4) = 3.8 (Spy Network + Prepare the Way): (3.8 - 3.0) - 1 < 0.
    assert profile.buy_gains(1) == 0.0
    # Negative amounts: knapsack(2) = 2.0; (2.0 - 3.0) + 1 = 0.
    assert profile.buy_gains(-1) == 0.0
    assert profile._cached_buy_gains == {2: pytest.approx(2.0), 1: 0.0, -1: 0.0}
    monkeypatch.setattr(profile, "_reveal_preview_persuasion", lambda: 0)
    assert profile.buy_gains(2) == pytest.approx(2.0)  # frozen per decision
    assert profile.buy_value() == 0.0
    monkeypatch.setattr(profile, "_reveal_preview_persuasion", lambda: 5)
    assert profile.buy_value() == pytest.approx(7.0)


def test_acquire_cards_by_value_is_a_stable_descending_sort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = dict(ROW_VALUES, prepare_the_way=2.0)
    profile = row_profile(monkeypatch, values)
    assert refs(profile.acquire_cards_by_value(4)) == [
        "calculus_of_power",
        "spy_network",
        "prepare_the_way",
        "sardaukar_soldier",
        "truthtrance",
    ]


def test_knapsack_decimal_conversion_keeps_fifteen_digits() -> None:
    assert economy._to_decimal(0.1 + 0.2) == economy._to_decimal(0.3)
    assert str(economy._to_decimal(1 / 3)) == "0.333333333333333"


def test_deck_agent_icons_count_the_draw_pile(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = prof(base_state(), monkeypatch)
    # Seat 3's draw pile: Dune x2, Signet Ring, Seek Allies, Diplomacy.
    assert profile.deck_agent_icons() == {
        "Triangle": 3,
        "Pentagon": 1,
        "Circle": 1,
        "Emperor": 2,
        "SpacingGuild": 2,
        "BeneGesserit": 2,
        "Fremen": 2,
    }
    reordered = with_player(
        base_state(), ME, deck=tuple(reversed(base_state().players[ME].deck))
    )
    assert prof(reordered, monkeypatch).deck_agent_icons() == profile.deck_agent_icons()


# =================================================================================
# §6-10 AcquireValue and its terms
# =================================================================================


def isolated(
    state: GameState,
    monkeypatch: pytest.MonkeyPatch,
    *,
    terms: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0),
    **kwargs: Any,
) -> Profile:
    """A profile whose synergy/friendship/effects/specific terms are stubbed."""

    profile = prof(state, monkeypatch, **kwargs)
    names = (
        "synergy_mod",
        "friendship_mod",
        "acquire_effects_value",
        "specific_acquire_bonus",
    )
    for name, value in zip(names, terms, strict=True):
        monkeypatch.setattr(profile, name, lambda c, v=value: Summer(v))
    return profile


def test_acquire_value_new_icons(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = isolated(base_state(), monkeypatch)
    # Calculus of Power 2.9; Circle (1 in deck) and Spy (none): 2 x 0.45.
    assert profile.acquire_value(card(imperium("calculus_of_power"))).sum == (
        pytest.approx(2.9 + 0.9)
    )
    # Desert Power 5.8; Triangle is in the deck 3 times (> 2): no bonus.
    assert profile.acquire_value(card(imperium("desert_power"))).sum == pytest.approx(
        5.8
    )
    # Steersman 8.0, EarlyMod 1.2; SG 2, Pentagon 1, Circle 1 (Triangle 3).
    assert profile.acquire_value(card(imperium("steersman"))).sum == pytest.approx(
        (8.0 + 3 * 0.45) * 1.2
    )


def test_acquire_value_staban_tuek_and_want_spy_leaders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calculus = card(imperium("calculus_of_power"))
    staban = with_player(
        base_state(), ME, leader_id="staban_tuek", leader_face_id="staban_tuek"
    )
    assert isolated(staban, monkeypatch).acquire_value(calculus).sum == pytest.approx(
        2.9 + 0.9 * 1.2
    )
    feyd = with_player(
        base_state(),
        ME,
        leader_id="feyd_rautha_harkonnen",
        leader_face_id="feyd_rautha_harkonnen",
    )
    assert isolated(feyd, monkeypatch).acquire_value(calculus).sum == pytest.approx(
        (2.9 + 0.9) * 1.15
    )


def test_acquire_value_no_icons_in_climax(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = isolated(base_state(), monkeypatch)
    profile._is_climax = True
    # Late arc (climax): no new icons, LateMod 1.0, minimum 2.2.
    assert profile.acquire_value(card(imperium("calculus_of_power"))).sum == (
        pytest.approx(2.9)
    )


def test_acquire_value_consolidation_uses_the_live_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calculus = card(imperium("calculus_of_power"))
    state = with_pool(reveal_state(), 7)
    profile = isolated(state, monkeypatch)
    icons = profile.acquire_value(calculus).sum - 2.9 + 0.55 * (4 / 3)
    poor = isolated(with_pool(reveal_state(), 2), monkeypatch)
    assert poor.acquire_value(calculus).sum == pytest.approx(icons + 2.9)
    assert profile.acquire_value(calculus).sum == pytest.approx(
        2.9 + icons - 0.55 * ((7.0 - 3.0) / 3.0)
    )


def test_acquire_value_game_arc_and_minimum(monkeypatch: pytest.MonkeyPatch) -> None:
    late_state = with_state(base_state(), round_number=8)
    # Desert Survival 1.0 (Triangle: no bonus) x LateMod 0.8 < 2.2: zeroed.
    survival = isolated(late_state, monkeypatch).acquire_value(
        card(imperium("desert_survival"))
    )
    assert survival.sum == 0.0
    # Overthrow 8.0 + four faction icons (2 each in the deck): kept.
    overthrow = isolated(late_state, monkeypatch).acquire_value(
        card(imperium("overthrow"))
    )
    assert overthrow.sum == pytest.approx(8.0 + 4 * 0.45)
    # Mid arc: Weirding Woman 0.8 + Circle 0.45 = 1.25 < 1.7.
    mid = with_state(base_state(), round_number=5)
    woman = isolated(mid, monkeypatch).acquire_value(card(imperium("weirding_woman")))
    assert woman.sum == 0.0
    # Early: x EarlyMod 1.2 = 1.5 >= 1.2.
    early_woman = isolated(base_state(), monkeypatch).acquire_value(
        card(imperium("weirding_woman"))
    )
    assert early_woman.sum == pytest.approx(1.25 * 1.2)


def test_acquire_value_merges_terms_and_call_to_arms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    desert = card(imperium("desert_power"))
    merged = isolated(base_state(), monkeypatch, terms=(0.1, 0.2, 0.3, 0.4))
    assert merged.acquire_value(desert).sum == pytest.approx(5.8 + 1.0)
    armed = with_player(base_state(), ME, intrigue_faceup=("intrigue:call_to_arms:0",))
    assert isolated(armed, monkeypatch).acquire_value(desert).sum == pytest.approx(
        5.8 + 0.5
    )


class _FakeVIP(Ability):
    """Every owned ability adds 0.1 deck synergy and 0.25 acquire bonus."""

    def value_in_pile_for_other_play(self, p: Any, pile: Any, card: Entity) -> Summer:
        return Summer(0.1)

    def specific_acquire_value(self, p: Any) -> Summer:
        return Summer(0.25)


def synergy_profile(
    state: GameState, monkeypatch: pytest.MonkeyPatch, *, climax: bool = False
) -> Profile:
    profile = prof(state, monkeypatch)
    monkeypatch.setattr(profile, "_abilities", lambda owner: (_FakeVIP(owner),))
    if climax:
        profile._is_climax = True
    return profile


def test_synergy_mod_concatenates_owned_abilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Seat 3 owns 10 starters (5 in hand, 5 in the deck): 10 x 0.1.
    profile = synergy_profile(base_state(), monkeypatch)
    assert profile.synergy_mod(card(imperium("desert_survival"))).sum == pytest.approx(
        1.0
    )
    in_climax = synergy_profile(base_state(), monkeypatch, climax=True)
    assert in_climax.synergy_mod(card(imperium("desert_survival"))).sum == 0.0


def test_synergy_mod_tag_incentives(monkeypatch: pytest.MonkeyPatch) -> None:
    lean = with_player(base_state(), ME, deck=(), hand=())  # no owned abilities
    spies = with_player(lean, ME, spies_supply=1, spy_post_ids=TWO_POSTS)
    strike = card(imperium("strike_fleet"))  # WantSpy
    assert synergy_profile(spies, monkeypatch).synergy_mod(strike).sum == pytest.approx(
        1.0
    )
    contracts = with_contracts(
        lean, completed=("contract:immediate",), active=("contract:acquire",)
    )
    cargo = card(imperium("cargo_runner"))  # WantContract2/4
    assert synergy_profile(contracts, monkeypatch).synergy_mod(
        cargo
    ).sum == pytest.approx(0.75 + 0.5)
    desert = card(imperium("desert_power"))  # WantHooks
    hooks = with_player(lean, ME, maker_hooks=True)
    assert synergy_profile(hooks, monkeypatch).synergy_mod(desert).sum == pytest.approx(
        1.5
    )
    fremen = with_player(
        lean, ME, influence=replace(lean.players[ME].influence, fremen=2)
    )
    assert synergy_profile(fremen, monkeypatch).synergy_mod(
        desert
    ).sum == pytest.approx(1.0)
    assert synergy_profile(lean, monkeypatch).synergy_mod(desert).sum == 0.0


def test_synergy_mod_contract_incentives_are_capped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lean = with_contracts(
        with_player(base_state(), ME, deck=(), hand=()),
        completed=("contract:immediate", "contract:harvest_3", "contract:harvest_4"),
    )
    cargo = card(imperium("cargo_runner"))
    # min(0.75 x 3, 3.0) = 2.25 > 2.0: the synergy cap replaces the sum.
    assert synergy_profile(lean, monkeypatch).synergy_mod(cargo).sum == 2.0


def test_synergy_mod_tsmf_uprising_mod_in_the_reveal_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tsmf = card("reserve:the_spice_must_flow")
    state = reveal_state()
    me = state.players[ME]
    spy = with_player(
        state, ME, deck=(), hand=(), discard_pile=(), in_play=(imperium("guild_spy"),)
    )
    profile = synergy_profile(spy, monkeypatch)
    assert profile.synergy_mod(tsmf).sum == 2.0  # 5.0 + 0.1, capped at 2.0
    contract = with_contracts(
        with_player(
            state, ME, deck=(), hand=(), discard_pile=(), in_play=me.in_play[:1]
        ),
        active=("contract:acquire",),
    )
    assert (
        synergy_profile(contract, monkeypatch, climax=True).synergy_mod(tsmf).sum == 2.0
    )
    plain = with_player(
        state, ME, deck=(), hand=(), discard_pile=(), in_play=me.in_play[:1]
    )
    assert synergy_profile(plain, monkeypatch).synergy_mod(tsmf).sum == pytest.approx(
        0.1
    )
    # Outside the Reveal turn the TSMF mod is off.
    agent_turn = with_player(
        base_state(), ME, deck=(), hand=(), in_play=(imperium("guild_spy"),)
    )
    assert synergy_profile(agent_turn, monkeypatch).synergy_mod(
        tsmf
    ).sum == pytest.approx(0.1)


@pytest.mark.parametrize(
    ("name", "influence", "alliances", "opponent_alliances", "expected"),
    [
        ("maker_keeper", {"bene_gesserit": 2, "fremen": 1}, (), (), 1.5 + 0.5),
        ("maker_keeper", {"bene_gesserit": 0, "fremen": 0}, (), (), 0.0),
        ("junction_headquarters", {}, ("spacing_guild",), (), 2.5),
        ("junction_headquarters", {"spacing_guild": 2}, (), (), 1.0),
        ("junction_headquarters", {"spacing_guild": 2}, (), ("spacing_guild",), 0.0),
        ("junction_headquarters", {"spacing_guild": 1}, (), (), 0.0),
        ("branching_path", {"bene_gesserit": 3}, (), (), 1.0),
        ("wheels_within_wheels", {"emperor": 1, "spacing_guild": 3}, (), (), 0.5 + 1.5),
        ("corrinth_city", {"emperor": 3}, (), (), 0.0),  # DiscardEnabler only
    ],
)
def test_friendship_mod(
    name: str,
    influence: dict[str, int],
    alliances: tuple[str, ...],
    opponent_alliances: tuple[str, ...],
    expected: float,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = base_state()
    state = with_player(
        state,
        ME,
        influence=replace(state.players[ME].influence, **influence),
        alliance_faction_ids=alliances,
    )
    state = with_player(state, 1, alliance_faction_ids=opponent_alliances)
    profile = prof(state, monkeypatch)
    assert profile.friendship_mod(card(imperium(name))).sum == pytest.approx(expected)


def test_acquire_effects_value(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = prof(base_state(), monkeypatch)
    calls: list[tuple[object, ...]] = []

    def influence(*args: object) -> Summer:
        calls.append(args)
        return Summer(3.3)

    monkeypatch.setattr(profile, "gain_influence_value", influence)
    assert profile.acquire_effects_value(card(imperium("steersman"))).sum == 3.3
    assert calls == [("spacing_guild", 1, -1, False)]
    tsmf = profile.acquire_effects_value(card("reserve:the_spice_must_flow"))
    assert tsmf.sum == pytest.approx(6.0)  # 1 VP, Early, 1 + 1 < 10
    price = profile.acquire_effects_value(card(imperium("price_is_no_object")))
    assert price.sum == pytest.approx(2 * 0.65 * 1.25 * 1.1 * 1.6)
    overthrow = profile.acquire_effects_value(card(imperium("overthrow")))
    assert overthrow.sum == 0.0  # Intrigue: outside the table


def test_specific_acquire_bonus(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = prof(base_state(), monkeypatch)
    # The real ports: no Uprising card ability overrides SpecificAcquireValue.
    assert profile.specific_acquire_bonus(card(imperium("steersman"))).sum == 0.0
    monkeypatch.setattr(
        profile, "_abilities", lambda owner: (_FakeVIP(owner), _FakeVIP(owner))
    )
    assert profile.specific_acquire_bonus(card(imperium("steersman"))).sum == 0.5


# =================================================================================
# §4.6-4.7 Space costs
# =================================================================================


def test_spice_for_spice_refinery(monkeypatch: pytest.MonkeyPatch) -> None:
    assert (
        prof(
            early(resources=resources(spice=0)), monkeypatch
        ).spice_for_spice_refinery()
        == 0
    )
    assert (
        prof(
            early(resources=resources(spice=2)), monkeypatch
        ).spice_for_spice_refinery()
        == 1
    )
    # Late and flooded with Solari: one Solari is worth < 0.25.
    flooded = late(resources=resources(solari=9, spice=2))
    assert prof(flooded, monkeypatch).spice_for_spice_refinery() == 0


@pytest.mark.parametrize(
    ("space", "attr", "amount", "changes", "expected"),
    [
        ("sardaukar", Attr.SPICE, 0, {"resources": (0, 4, 1)}, True),
        ("sardaukar", Attr.SPICE, 1, {"resources": (0, 4, 1)}, False),
        ("imperial_basin", Attr.SPICE, 1, {"resources": (0, 0, 1)}, True),
        ("imperial_basin", Attr.SPICE, 2, {"resources": (0, 0, 1)}, False),
        ("high_council", Attr.SOLARI, 0, {"resources": (5, 0, 1)}, True),
        ("high_council", Attr.SOLARI, 0, {"resources": (4, 0, 1)}, False),
        ("shipping", Attr.SOLARI, 5, {"resources": (0, 0, 1)}, True),
        ("deep_desert", Attr.WATER, 0, {"resources": (0, 0, 3)}, True),
        ("deep_desert", Attr.WATER, 1, {"resources": (0, 0, 3)}, False),
        ("deliver_supplies", Attr.WATER, 1, {"resources": (0, 0, 0)}, True),
        ("deep_desert", Attr.TROOPS, 9, {"resources": (0, 0, 0)}, True),
    ],
)
def test_can_agent_ability_be_played_with_space(
    space: str,
    attr: Attr,
    amount: int,
    changes: dict[str, tuple[int, int, int]],
    expected: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    solari, spice, water = changes["resources"]
    profile = prof(early(resources=resources(solari, spice, water)), monkeypatch)
    entity = space_entity(space, Board(True))
    assert (
        profile.can_agent_ability_be_played_with_space(entity, attr, amount) is expected
    )


def test_can_agent_ability_counts_maker_bonus_spice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = with_state(
        early(),
        maker_bonus_spice=(
            ("deep_desert", 0),
            ("hagga_basin", 0),
            ("imperial_basin", 2),
        ),
    )
    profile = prof(state, monkeypatch)
    basin = space_entity("imperial_basin", Board(True))
    assert profile.can_agent_ability_be_played_with_space(basin, Attr.SPICE, 3)
    assert not profile.can_agent_ability_be_played_with_space(basin, Attr.SPICE, 4)
    assert profile.can_agent_ability_be_played_with_space(None, Attr.SPICE, 0)


# =================================================================================
# §11 Trashing
# =================================================================================


def trash_state() -> GameState:
    return early(
        hand=(
            starter("dagger", 1),
            starter("reconnaissance"),
            starter("convincing_argument"),
        ),
        discard_pile=(starter("dagger"),),
        in_play=(imperium("calculus_of_power"),),
        deck=(starter("dune_the_desert_planet"),),
    )


def test_card_to_trash_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = prof(trash_state(), monkeypatch)
    targets = [
        card(starter("dagger")),
        card(starter("dagger", 1)),
        card(starter("reconnaissance")),
    ]
    best, value = profile.card_to_trash(targets, 1.0)
    assert best is not None and best.ref == starter("dagger")
    assert value == pytest.approx(10.0 + 0.2 + 0.09)  # Discard
    recon, value = profile.card_to_trash([card(starter("reconnaissance"))], 1.0)
    assert recon is not None and value == pytest.approx(5.0 + 0.09)  # in hand
    deck, value = profile.card_to_trash([card(starter("dune_the_desert_planet"))], 1.0)
    assert deck is not None and value == pytest.approx(10.0 + 0.09)  # no location


def test_card_to_trash_convincing_argument_lowers_every_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = prof(trash_state(), monkeypatch)
    targets = [card(starter("dagger")), card(starter("convincing_argument"))]
    best, value = profile.card_to_trash(targets, 1.0)
    assert best is not None and best.ref == starter("dagger")
    assert value == pytest.approx(7.5 + 0.2 + 0.09)
    alone, value = profile.card_to_trash([card(starter("convincing_argument"))], -1.0)
    assert alone is not None and value == pytest.approx(-1.0 + 0.09)


def test_card_to_trash_bought_cards_and_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = prof(trash_state(), monkeypatch)
    calculus = [card(imperium("calculus_of_power"))]
    assert profile.card_to_trash(calculus, 0.0) == (None, 0.0)
    played, value = profile.card_to_trash(calculus, -1.0)
    assert played is not None
    assert value == pytest.approx(-1.0 + 0.1 + (3 * -0.01 + 0.09))


def test_card_to_trash_breaks_ties_with_the_shuffle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = early(
        hand=(),
        discard_pile=(starter("dagger"), starter("dagger", 1)),
    )
    targets = [card(starter("dagger")), card(starter("dagger", 1))]
    seen = set()
    for seed in range(12):
        profile = make_profile(state, ME, rng_seed=seed)
        best, _ = profile.card_to_trash(targets, 1.0)
        shuffled = list(targets)
        random.Random(seed).shuffle(shuffled)
        assert best == shuffled[-1]  # >=: the later card of a tie wins
        seen.add(best.ref if best else None)
    assert seen == {starter("dagger"), starter("dagger", 1)}


# =================================================================================
# §3.3, §13 Opponents and turn order
# =================================================================================


def test_opponent_ratio(monkeypatch: pytest.MonkeyPatch) -> None:
    state = with_player(
        with_player(base_state(), 0, victory_points=3), 1, victory_points=4
    )
    profile = prof(state, monkeypatch)
    assert profile.opponent_ratio(lambda p: p.victory_points >= 3) == pytest.approx(
        2 / 3
    )
    assert profile.opponent_ratio(lambda p: p.victory_points >= 9) == 0.0


def test_ordered_players(monkeypatch: pytest.MonkeyPatch) -> None:
    # Turn start (PlayerTurn Undetermined): the active player comes first.
    assert prof(base_state(), monkeypatch).ordered_players() == [3, 0, 1, 2]
    # Inside the turn (Reveal): the active player goes last.
    assert prof(reveal_state(), monkeypatch).ordered_players() == [0, 1, 2, 3]


@pytest.mark.parametrize(
    ("first", "opponent", "expected"),
    [
        (0, 0, True),
        (3, 0, False),
        (1, 2, False),
        (1, 0, True),
        (2, 1, True),
        (0, 1, False),
        (0, 2, False),
        (None, 0, False),
    ],
)
def test_has_turn_before_opponent_next_round(
    first: int | None, opponent: int, expected: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = with_state(base_state(), first_player=first)
    assert (
        prof(state, monkeypatch).has_turn_before_opponent_next_round(opponent)
        is expected
    )


class _BadIntrigue(Ability):
    def is_bad_intrigue(self, p: Any) -> bool:
        return self.owner.ref.startswith("intrigue:cunning")


def test_bad_intrigue_cards_in_hand(monkeypatch: pytest.MonkeyPatch) -> None:
    state = early(intrigue_cards=("intrigue:cunning:0", "intrigue:devour:0"))
    profile = prof(state, monkeypatch)
    assert profile.bad_intrigue_cards_in_hand() == []  # no hook: IntrigueAbility false
    monkeypatch.setattr(profile, "_abilities", lambda owner: (_BadIntrigue(owner),))
    assert [c.ref for c in profile.bad_intrigue_cards_in_hand()] == [
        "intrigue:cunning:0"
    ]


# =================================================================================
# §12 Discarding
# =================================================================================


class _FakeReveal(Ability):
    """Reveal value = the card's app ``Persuasion`` attribute."""

    def value_for_player(self, p: Any, with_entities: Sequence[Entity] = ()) -> Summer:
        return Summer(float(self.owner.int_attr("Persuasion")))


class _FakeAgent(Ability):
    def value_for_player(self, p: Any, with_entities: Sequence[Entity] = ()) -> Summer:
        return Summer(1.0)


DISCARD_HAND = (
    starter("dagger"),
    starter("diplomacy"),
    starter("reconnaissance"),
    starter("convincing_argument"),
    imperium("spacing_guild_s_favor"),  # IncentiveDiscard, cost 5
    imperium("space_time_folding"),  # Spacing Guild, cost 1
    imperium("calculus_of_power"),  # cost 3
)


def discard_profile(
    monkeypatch: pytest.MonkeyPatch, agents: int
) -> tuple[Profile, list[Entity]]:
    for name in economy._REVEAL_CLASSES:
        monkeypatch.setitem(PORTS, name, _FakeReveal)
    for name in economy._AGENT_CLASSES:
        monkeypatch.setitem(PORTS, name, _FakeAgent)
    placed = ("secrets", "espionage")[: 2 - agents]
    state = early(
        agents_available=agents, agent_locations=placed, hand=DISCARD_HAND, deck=()
    )
    profile = prof(state, monkeypatch)
    return profile, [card_entity(i, ME) for i in DISCARD_HAND]


@pytest.mark.parametrize(
    ("bonus", "expected"),
    [
        (
            False,
            [
                "spacing_guild_s_favor",
                "dagger",
                "reconnaissance",
                "convincing_argument",
                "diplomacy",
                "space_time_folding",
                "calculus_of_power",
            ],
        ),
        (
            True,
            [
                "spacing_guild_s_favor",
                "space_time_folding",
                "dagger",
                "reconnaissance",
                "convincing_argument",
                "diplomacy",
                "calculus_of_power",
            ],
        ),
    ],
)
def test_discard_order_with_an_agent_left(
    bonus: bool, expected: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    profile, cards = discard_profile(monkeypatch, agents=1)
    assert refs(profile.discard_order(cards, bonus)) == expected


def test_discard_order_without_agents_is_by_reveal_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile, cards = discard_profile(monkeypatch, agents=0)
    # Diplomacy and Reconnaissance tie at 100: input order is kept.
    assert refs(profile.discard_order(cards, False)) == [
        "spacing_guild_s_favor",
        "dagger",
        "diplomacy",
        "reconnaissance",
        "space_time_folding",
        "convincing_argument",
        "calculus_of_power",
    ]


def test_discard_order_keys_are_exact(monkeypatch: pytest.MonkeyPatch) -> None:
    profile, cards = discard_profile(monkeypatch, agents=1)
    seen: dict[str, float] = {}
    original: Callable[..., list[Entity]] = sorted

    def spy(items: Sequence[Entity], key: Callable[[Entity], float]) -> list[Entity]:
        for item in items:
            seen[card_id(item.ref)] = key(item)
        return original(items, key=key)

    monkeypatch.setattr(economy, "sorted", spy, raising=False)
    profile.discard_order(cards, False)
    assert seen["dagger"] == 0.0 + (1.0 + (0.0 + (1.0 * -10000.0 + 0.0)))
    assert seen["spacing_guild_s_favor"] == 1.5 * 2 + (
        1.0 + (500.0 + ((1.0 - (100000.0 * 2 + 1000000.0)) + 0.0))
    )
    assert seen["calculus_of_power"] == 1.5 * 2 + (1.0 + (300.0 + 0.0))
