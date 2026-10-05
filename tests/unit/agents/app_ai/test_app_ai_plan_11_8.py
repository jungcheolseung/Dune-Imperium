"""Plan §11.8: the non-window decisions of the Bloodlines / Scouts review.

1. The Commander price skips the troop-supply cap
   (``CommanderUnitValue = uncapped_troop_value(1)``, bloodlines-systems.md
   §1.2).
2. The High Council first visit values the Landsraad Tech purchase with the
   seat's −1 assumed (bloodlines-systems.md §3.1 row 2, D12; Tech Module only).
3. Commanders and the Into the Fray Agent count as units in the card ports
   (bloodlines-systems.md §1.1, D1; Bloodlines only), except where our engine
   refuses a Commander as payment: Tleilaxu Surgeon (OQ-053) and Piter,
   Genius Advisor stay troops only.
4. Market Opening's discounted Reserve The Spice Must Flow at the ability sites
   that build the Reserve card themselves (scouts.md §4.7, D31; Scouts only).

States are real games advanced by ``testing.first_decision``; the fields a
branch reads are set with ``with_player`` / ``with_state`` and the profile
methods a branch does not test are stubbed on the ``Profile`` instance.
"""

from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import testing as _t
from dune_imperium.agents.app_ai.abilities import bloodlines_cards as bc
from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities import intrigue as it
from dune_imperium.agents.app_ai.abilities import leaders as ld
from dune_imperium.agents.app_ai.abilities.base import (
    Request,
    TargetInfo,
    abilities_of,
)
from dune_imperium.agents.app_ai.abilities.immortality import (
    GruesomeSacrificeAbility,
    HarvestCellsAbility,
    HighPriorityTravelAbility,
    PiterGeniusAdvisorAbility,
    TleilaxuSurgeonRevealAbility,
)
from dune_imperium.agents.app_ai.abilities.imperium_a import (
    ChaniCleverTacticianAgentAbility,
    ChaniCleverTacticianRevealAbility,
)
from dune_imperium.agents.app_ai.abilities.imperium_b import (
    PriceIsNoObjectAbility,
    UnswervingLoyaltyAbility,
)
from dune_imperium.agents.app_ai.abilities.intrigue import (
    CallToArmsAbility,
    DetonationAbility,
    SpiceIsPowerAbility,
)
from dune_imperium.agents.app_ai.abilities.leaders import DesertScoutsAbility
from dune_imperium.agents.app_ai.abilities.tech import (
    HIGH_COUNCIL_SPACE,
    AcquireTechAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    intrigue_entity,
    space_entity,
    tech_entity,
)
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile.scouts import discounted_card
from dune_imperium.agents.app_ai.summer import IntSummer, Summer
from dune_imperium.content.uprising.types import PersonalCardRevealChoiceEffect
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules.reveal_turn import _reveal_choice_effect_is_available

BL = RulesetConfig(choam_module=True, bloodlines=True, tech_module=True)
SC = RulesetConfig(
    choam_module=True, bloodlines=True, tech_module=True, arrakeen_scouts=True
)
BASE = RulesetConfig(choam_module=True)

TSMF = "the_spice_must_flow"
MARKET_OPENING = "spice_must_flow_discount"


# =================================================================================
# Fixtures
# =================================================================================


@cache
def bl_state() -> GameState:
    """Round 1, the first Agent turn of a Bloodlines + Tech Module game."""

    return _t.first_decision("turn", config=BL)


@cache
def sc_state() -> GameState:
    """Round 1, the first Agent turn of a Bloodlines + Tech + Scouts game."""

    return _t.first_decision("turn", config=SC)


@cache
def base_state() -> GameState:
    """Round 1, the first Agent turn of an Uprising + CHOAM game."""

    return _t.first_decision("turn", config=BASE)


def seat_of(state: GameState) -> int:
    decision = _t.ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def make(state: GameState) -> Profile:
    return _t.make_profile(state, seat_of(state))


def units(
    state: GameState,
    *,
    seat: int | None = None,
    garrison: int = 0,
    conflict: int = 0,
    cmd_garrison: int = 0,
    cmd_conflict: int = 0,
    agent: int = 0,
    worms: int = 0,
) -> GameState:
    """``state`` with a seat's units set (the rest of its 12 troops in the
    supply; ``agent`` Agents moved from the available ones to the Conflict)."""

    seat = seat_of(state) if seat is None else seat
    me = state.players[seat]
    supply = 12 - garrison - conflict - me.memories - me.specimens - me.troops_parked
    return _t.with_player(
        state,
        seat,
        troops_supply=supply,
        troops_garrison=garrison,
        troops_conflict=conflict,
        commanders_garrison=cmd_garrison,
        commanders_conflict=cmd_conflict,
        agent_in_conflict=me.agent_in_conflict + agent,
        agents_available=me.agents_available - agent,
        sandworms_conflict=worms,
    )


def resources(state: GameState, **changes: int) -> GameState:
    seat = seat_of(state)
    me = state.players[seat]
    return _t.with_player(state, seat, resources=replace(me.resources, **changes))


def summer(value: float) -> Summer:
    s = Summer()
    s.add("stub", value)
    return s


def int_summer(value: int) -> IntSummer:
    s = IntSummer()
    s.add("stub", value)
    return s


def intrigue(card_id: str) -> Entity:
    return intrigue_entity(f"intrigue:{card_id}:0")


# =================================================================================
# 1. CommanderUnitValue without the troop-supply cap
# =================================================================================


def test_commander_unit_value_skips_an_empty_troop_supply() -> None:
    empty = make(units(bl_state(), garrison=2, conflict=10))
    assert empty.ctx.me.troops_supply == 0
    assert empty.troop_value(1, False) == 0.0  # the capped troop price
    unit = empty.commander_unit_value()
    assert unit == empty.uncapped_troop_value(1)
    assert unit > 0.0
    # The prices built on it see the uncapped Commander.
    assert empty.lose_unit_value("garrison", True) == unit
    assert empty.recruit_net() == pytest.approx(
        unit - empty.solari_value(empty.commander_cost())
    )


def test_commander_unit_value_is_a_troop_while_the_supply_has_one() -> None:
    p = make(units(bl_state(), garrison=2, conflict=9))
    assert p.ctx.me.troops_supply == 1
    assert p.commander_unit_value() == p.troop_value(1, False)


# =================================================================================
# 2. The High Council first visit assumes the seat's Tech discount
# =================================================================================


def _cheapest_tile(state: GameState) -> int:
    return min(tech_entity(s[0]).int_attr("SpiceCost") for s in state.tech_stacks)


def _acquire_tech(p: Profile, space_id: str) -> AcquireTechAbility:
    space = space_entity(space_id, p.ctx.board)
    return next(a for a in abilities_of(space) if isinstance(a, AcquireTechAbility))


def test_high_council_first_visit_values_the_tile_the_seat_makes_affordable() -> None:
    cheapest = _cheapest_tile(bl_state())
    p = make(resources(bl_state(), spice=cheapest - 1))
    assert not p.ctx.me.high_council
    assert p.tech_acquire_targets(0, False) == []
    hc = _acquire_tech(p, HIGH_COUNCIL_SPACE)
    assert hc.meets_cost(p)
    value = hc.value_for_player(p).sum
    assert value == p.buy_tech_value(1, False)
    assert value > 0.0
    # Another Landsraad space gets no seat: nothing is affordable there.
    other = _acquire_tech(p, "assembly_hall")
    assert not other.meets_cost(p)
    assert other.value_for_player(p).sum == 0.0


def test_high_council_with_the_seat_held_takes_only_the_real_discount() -> None:
    cheapest = _cheapest_tile(bl_state())
    seat = seat_of(bl_state())
    held = _t.with_player(
        resources(bl_state(), spice=cheapest - 1), seat, high_council=True
    )
    p = make(held)
    hc = _acquire_tech(p, HIGH_COUNCIL_SPACE)
    assert hc.meets_cost(p)  # the held seat's -1 (``tech_cost``)
    assert hc.value_for_player(p).sum == p.buy_tech_value(0, False)
    if cheapest >= 2:
        poorer = _t.with_player(
            resources(bl_state(), spice=cheapest - 2), seat, high_council=True
        )
        q = make(poorer)
        assert not _acquire_tech(q, HIGH_COUNCIL_SPACE).meets_cost(q)  # no second -1
        assert _acquire_tech(q, HIGH_COUNCIL_SPACE).value_for_player(q).sum == 0.0


def test_high_council_hook_is_off_without_the_tech_module() -> None:
    p = make(base_state())
    space = space_entity(HIGH_COUNCIL_SPACE, p.ctx.board)
    assert not any(isinstance(a, AcquireTechAbility) for a in abilities_of(space))
    assert AcquireTechAbility(space)._discount(p) == 0


# =================================================================================
# 3. Commanders and the Into the Fray Agent as units (Bloodlines only)
# =================================================================================


def test_unit_counts_include_the_bloodlines_units() -> None:
    state = units(
        bl_state(),
        garrison=1,
        conflict=2,
        cmd_garrison=1,
        cmd_conflict=2,
        agent=1,
        worms=1,
    )
    p = make(state)
    assert p.conflict_unit_count() == 2 + 1 + 2 + 1  # troops, worm, Commanders, Agent
    assert p.conflict_troop_count() == 2 + 2  # never the worm or the Agent
    assert p.garrison_troop_count() == 1 + 1
    opponent = p.ctx.opponents[0]
    assert p.conflict_unit_count(opponent) == opponent.units_in_conflict


def test_unit_counts_read_troops_only_without_bloodlines() -> None:
    """A game without the option cannot hold Commanders (``GameState``
    rejects them), so the gate is shown on a Bloodlines seat read through a
    profile of a base game."""

    bl = units(
        bl_state(),
        garrison=1,
        conflict=2,
        cmd_garrison=1,
        cmd_conflict=2,
        agent=1,
        worms=1,
    )
    seat_state = bl.players[seat_of(bl)]
    p = make(base_state())
    assert not p.ctx.bloodlines
    assert p.conflict_unit_count(seat_state) == 2 + 1
    assert p.conflict_troop_count(seat_state) == 2
    assert p.garrison_troop_count(seat_state) == 1
    assert (
        p.conflict_unit_count()
        == p.ctx.me.troops_conflict + p.ctx.me.sandworms_conflict
    )


# -- imperium_a ----------------------------------------------------------------------


def test_chani_agent_counts_garrison_commanders() -> None:
    chani = ChaniCleverTacticianAgentAbility(
        card_entity("imperium:chani_clever_tactician:0")
    )
    p = make(units(bl_state(), conflict=1, cmd_garrison=2))
    assert p.intrigue_value() > 0.0
    assert chani.value_for_player(p).sum == p.intrigue_value()
    q = make(units(bl_state(), conflict=1, garrison=1))
    assert chani.value_for_player(q).sum == 0.0


def test_chani_reveal_counts_commanders_and_the_conflict_agent() -> None:
    chani = ChaniCleverTacticianRevealAbility(
        card_entity("imperium:chani_clever_tactician:0")
    )
    p = make(units(bl_state(), conflict=1, cmd_conflict=1, agent=1))
    assert chani.value_for_player(p).sum == p.troop_value(2, False)
    q = make(units(bl_state(), conflict=1, cmd_conflict=1))  # two units only
    assert chani.value_for_player(q).sum == 0.0


# -- imperium_b ----------------------------------------------------------------------


def _loyalty() -> UnswervingLoyaltyAbility:
    return UnswervingLoyaltyAbility(card_entity("imperium:unswerving_loyalty:0"))


def test_unswerving_loyalty_deploys_a_garrison_commander(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make(units(bl_state(), cmd_garrison=1))
    monkeypatch.setattr(p, "units_to_deploy", lambda count, max_units: 1)
    answer = _loyalty().evaluate(p, Request())
    assert (answer.value, answer.response) == (100.0, ((0,),))


def test_unswerving_loyalty_retreats_a_conflict_commander(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make(units(bl_state(), cmd_conflict=1))
    monkeypatch.setattr(p, "troops_to_retreat", lambda max_troops: 1)
    answer = _loyalty().evaluate(p, Request())
    assert (answer.value, answer.response) == (100.0, ((0,),))
    assert "Retreat" in answer.label


# -- intrigue ------------------------------------------------------------------------


def test_spice_is_power_cost_counts_conflict_commanders() -> None:
    card = SpiceIsPowerAbility(intrigue("spice_is_power"))
    assert card.meets_cost(
        make(resources(units(bl_state(), conflict=1, cmd_conflict=2), spice=0))
    )
    assert not card.meets_cost(make(resources(units(bl_state(), conflict=1), spice=0)))


def test_spice_is_power_retreat_counts_conflict_commanders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = SpiceIsPowerAbility(intrigue("spice_is_power"))
    p = make(resources(units(bl_state(), conflict=1, cmd_conflict=2), spice=0))
    monkeypatch.setattr(p, "should_play_retreat_intrigue", lambda *args: 1)
    answer = card.evaluate(p, Request())
    assert (answer.value, answer.response) == (150.0, ((0,),))


def test_call_to_arms_is_bad_with_garrison_commanders() -> None:
    card = CallToArmsAbility(intrigue("call_to_arms"))
    assert card.is_bad_intrigue(make(units(bl_state(), garrison=4, cmd_garrison=2)))
    assert not card.is_bad_intrigue(make(units(bl_state(), garrison=4)))


def test_intrigue_deploy_troops_counts_commanders_on_both_sides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Own garrison Commanders pass the garrison test; an opponent with only a
    Commander in the Conflict passes ``ConflictUnits > 0``."""

    state = units(bl_state(), cmd_garrison=2)
    rival = next(seat for seat in range(4) if seat != seat_of(state))
    state = units(state, seat=rival, cmd_conflict=1)
    p = make(state)
    monkeypatch.setattr(it, "_in_player_turn", lambda p_, turn: True)
    monkeypatch.setattr(p, "is_final_round", lambda: False)
    monkeypatch.setattr(p, "est_strength", lambda: int_summer(4))
    monkeypatch.setattr(p, "conflict_posture_bounds", lambda: (0.0, 100.0))
    monkeypatch.setattr(p, "current_conflict_interest", lambda: summer(10.0))
    monkeypatch.setattr(
        p, "est_opponent_strength", lambda seat: int_summer(8 if seat == rival else 0)
    )
    monkeypatch.setattr(p, "estimated_conflict_rank", lambda k=0: 1 if k > 0 else 2)
    assert it.intrigue_deploy_troops(p, (0, 1)) == 1
    # The same garrison of troops only would have nothing to deploy.
    q = make(units(units(bl_state(), seat=rival, cmd_conflict=1)))
    assert it.intrigue_deploy_troops(q, (0, 1)) == 0


def test_detonation_is_not_bad_with_garrison_commanders() -> None:
    card = DetonationAbility(intrigue("detonation"))
    p = make(units(bl_state(), garrison=1))
    assert p.ctx.shield_wall_present and not p.ctx.me.maker_hooks
    assert card.is_bad_intrigue(p)
    assert not card.is_bad_intrigue(make(units(bl_state(), garrison=1, cmd_garrison=2)))


def test_detonation_deploys_garrison_commanders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = DetonationAbility(intrigue("detonation"))
    monkeypatch.setattr(DetonationAbility, "_can_deploy_units", lambda self, p: True)
    monkeypatch.setattr(it, "intrigue_deploy_troops", lambda p, troops: len(troops))
    request = Request(infos=(TargetInfo(options=(0, 1)), TargetInfo(options=(0,))))
    p = make(units(bl_state(), cmd_garrison=1))
    monkeypatch.setattr(p, "intrigue_blow_wall", lambda: False)
    answer = card.evaluate(p, request)
    assert answer.response == ((1,), (0,))
    q = make(units(bl_state()))
    monkeypatch.setattr(q, "intrigue_blow_wall", lambda: False)
    assert card.evaluate(q, request).response is None


# -- immortality ---------------------------------------------------------------------


def _guild(state: GameState, level: int) -> GameState:
    seat = seat_of(state)
    me = state.players[seat]
    return _t.with_player(
        state, seat, influence=replace(me.influence, spacing_guild=level)
    )


def test_high_priority_travel_cost_counts_a_garrison_commander(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = HighPriorityTravelAbility(card_entity("imperium:high_priority_travel:0"))
    monkeypatch.setattr(g, "_has_drawable_card", lambda p: False)
    assert card.meets_cost(make(_guild(units(bl_state(), cmd_garrison=1), 2)))
    assert not card.meets_cost(make(_guild(units(bl_state()), 2)))


def test_high_priority_travel_deploys_garrison_commanders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = HighPriorityTravelAbility(card_entity("imperium:high_priority_travel:0"))
    p = make(units(bl_state(), cmd_garrison=2))
    monkeypatch.setattr(p, "conflict_posture_bounds", lambda: (0.0, 100.0))
    monkeypatch.setattr(p, "current_conflict_interest", lambda: summer(10.0))
    assert card.evaluate(p, Request()).response == ((1,),)
    q = make(units(bl_state(), garrison=1))
    monkeypatch.setattr(q, "conflict_posture_bounds", lambda: (0.0, 100.0))
    monkeypatch.setattr(q, "current_conflict_interest", lambda: summer(10.0))
    assert card.evaluate(q, Request()).response == ((0,),)


_SURGEON_UNITS = (
    {"cmd_garrison": 1, "cmd_conflict": 1},
    {"garrison": 1, "cmd_garrison": 1},
    {"conflict": 1, "cmd_conflict": 2},
    {"garrison": 1, "conflict": 1},
    {"garrison": 2},
    {"conflict": 2, "cmd_garrison": 1},
)


@pytest.mark.parametrize("unit_counts", _SURGEON_UNITS)
def test_tleilaxu_surgeon_cost_matches_the_engine_troops_only(
    unit_counts: dict[str, int],
) -> None:
    """Commanders never pay Tleilaxu Surgeon (OQ-053: "Sardaukar Commander는
    이 비용에 쓰지 않는다"): the port's cost is the engine's own availability
    gate of the Reveal box, so the app never values a payment our engine
    does not offer."""

    card = TleilaxuSurgeonRevealAbility(card_entity("imperium:tleilaxu_surgeon:0"))
    state = units(bl_state(), **unit_counts)
    seat = seat_of(state)
    engine_offers = _reveal_choice_effect_is_available(
        state,
        seat,
        state.players[seat],
        (),
        "imperium:tleilaxu_surgeon:0",
        PersonalCardRevealChoiceEffect.MAY_LOSE_TWO_TROOPS_FOR_TWO_SPECIMENS,
    )
    assert card.meets_cost(make(state)) == engine_offers


def test_tleilaxu_surgeon_gate_reads_garrison_troops_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = TleilaxuSurgeonRevealAbility(card_entity("imperium:tleilaxu_surgeon:0"))
    monkeypatch.setattr(card, "_trade", lambda p: summer(5.0))
    troops = make(units(bl_state(), garrison=2))
    commanders = make(units(bl_state(), garrison=1, cmd_garrison=2))
    for profile in (troops, commanders):
        monkeypatch.setattr(profile, "conflict_posture_bounds", lambda: (100.0, 200.0))
        monkeypatch.setattr(profile, "current_conflict_interest", lambda: summer(0.0))
    assert card.value_for_player(troops).sum == 5.0
    # Garrison Commanders cannot pay: "cost cannot be paid".
    assert card.value_for_player(commanders).sum == 0.0


def test_piter_genius_advisor_cost_counts_troops_only() -> None:
    """Our engine's "Lose a troop" box offers ``lose_agent_card_troop`` only
    for a zone holding a troop (``legal_agent_card_payment_actions``): a
    Commander alone cannot pay."""

    card = PiterGeniusAdvisorAbility(card_entity("tleilaxu:piter_genius_advisor:0"))
    assert not card.meets_cost(make(units(bl_state(), cmd_conflict=1, cmd_garrison=1)))
    assert card.value_for_player(make(units(bl_state(), cmd_conflict=1))).sum == 0.0
    assert card.meets_cost(make(units(bl_state(), conflict=1)))
    assert card.meets_cost(make(units(bl_state(), garrison=1)))


def test_gruesome_sacrifice_cost_counts_conflict_commanders() -> None:
    card = GruesomeSacrificeAbility(intrigue("gruesome_sacrifice"))
    assert card.meets_cost(make(units(bl_state(), cmd_conflict=2)))
    assert not card.meets_cost(make(units(bl_state(), conflict=1)))


def test_gruesome_sacrifice_counts_the_conflict_agent_as_a_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = GruesomeSacrificeAbility(intrigue("gruesome_sacrifice"))
    p = make(units(bl_state(), conflict=1, cmd_conflict=1, agent=1))
    q = make(units(bl_state(), conflict=1, cmd_conflict=1))
    for profile in (p, q):
        monkeypatch.setattr(profile, "current_conflict_rank", lambda bonus=0: 1)
    assert card.evaluate(p, Request()).value == 5.0
    assert card.evaluate(q, Request()).response is None  # hold: two units


def test_harvest_cells_cost_counts_conflict_commanders() -> None:
    card = HarvestCellsAbility(intrigue("harvest_cells"))
    assert card.meets_cost(make(units(bl_state(), conflict=1, cmd_conflict=2)))
    assert not card.meets_cost(make(units(bl_state(), conflict=1)))


# -- bloodlines_cards, leaders -------------------------------------------------------


def test_twisted_devious_fallback_lists_garrison_commanders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = bc.TwistedDeviousAbility(intrigue("twisted_devious"))
    monkeypatch.setattr(bc, "intrigue_deploy_troops", lambda p, garrison: len(garrison))
    request = Request(infos=(TargetInfo(options=(1,)),))
    answer = card.evaluate(make(units(bl_state(), cmd_garrison=2)), request)
    assert (answer.value, answer.response) == (100.0, ((1,), (0, 1)))
    assert card.evaluate(make(units(bl_state())), request).response is None


def test_leader_unit_reads_use_the_gated_counts() -> None:
    p = make(units(bl_state(), cmd_conflict=1, agent=1))
    assert ld._deployed_units(p) == 2
    scouts = DesertScoutsAbility(Entity(Kind.LEADER, "x"))
    assert scouts.meets_cost(p)
    assert not scouts.meets_cost(
        make(units(bl_state(), agent=1))
    )  # an Agent is no troop


# =================================================================================
# 4. Market Opening's Reserve The Spice Must Flow (Scouts only)
# =================================================================================


def _only_tsmf(state: GameState) -> GameState:
    """No Imperium Row and only The Spice Must Flow left in the Reserve."""

    stacks = tuple((rid, n if rid == TSMF else 0) for rid, n in state.reserve_stacks)
    return _t.with_state(state, imperium_row=(), reserve_stacks=stacks)


def test_price_is_no_object_cost_sees_the_market_opening_discount() -> None:
    card = PriceIsNoObjectAbility(card_entity("imperium:price_is_no_object:0"))
    plain = resources(_only_tsmf(sc_state()), solari=7)
    opening = _t.with_state(plain, scouts_round_modifier=MARKET_OPENING)
    assert card.meets_cost(make(opening))
    assert not card.meets_cost(make(plain))
    used = _t.with_state(opening, scouts_discount_used=True)
    assert not card.meets_cost(make(used))


def test_chroniclers_targets_read_the_market_opening_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opening = _t.with_state(sc_state(), scouts_round_modifier=MARKET_OPENING)
    p = make(opening)
    real = p.market_opening_reserve_card(card_entity(f"reserve:{TSMF}"))
    assert real.int_attr("PersuasionCost") == 7
    assert real.ref not in [c.ref for c in ld.chroniclers_acquire_targets(p)]  # 7 > 1
    # Wiring: the site reads whatever the profile's Market Opening card is.
    monkeypatch.setattr(
        p,
        "market_opening_reserve_card",
        lambda e: discounted_card(e, 8) if e.ref == f"reserve:{TSMF}" else e,
    )
    assert f"reserve:{TSMF}" in [c.ref for c in ld.chroniclers_acquire_targets(p)]
    q = make(bl_state())  # no Scouts: the profile hook is never asked
    monkeypatch.setattr(
        q, "market_opening_reserve_card", lambda e: discounted_card(e, 8)
    )
    assert f"reserve:{TSMF}" not in [c.ref for c in ld.chroniclers_acquire_targets(q)]


def _navigation_tsmf_cost(
    state: GameState, monkeypatch: pytest.MonkeyPatch
) -> list[int]:
    p = make(resources(state, water=1))
    seen: list[int] = []

    def record(card: Entity) -> Summer:
        seen.append(card.int_attr("PersuasionCost"))
        return Summer()

    monkeypatch.setattr(p, "acquire_value", record)
    assert p.navigation_option_value(4, 1, 1, "emperor") is not None
    return seen


def test_navigation_four_values_the_market_opening_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opening = _t.with_state(sc_state(), scouts_round_modifier=MARKET_OPENING)
    assert _navigation_tsmf_cost(opening, monkeypatch) == [7]
    assert _navigation_tsmf_cost(sc_state(), monkeypatch) == [9]
    assert _navigation_tsmf_cost(bl_state(), monkeypatch) == [9]


# =================================================================================
# Main-session follow-ups (verifier findings of the window stage)
# =================================================================================


def test_spice_refinery_trade_is_free_with_navigation_chamber() -> None:
    """Navigation Chamber's −1 spice on the visit makes the 1-spice trade
    free: sell even with no spice, at no spice cost; without the discount
    the app's own value stands."""

    from dune_imperium.agents.app_ai.abilities.base import Request
    from dune_imperium.agents.app_ai.abilities.board import SpiceRefineryAbility
    from dune_imperium.agents.app_ai.catalog import space_entity
    from dune_imperium.agents.app_ai.profile.bloodlines import space_with_cost_cut

    state = bl_state()
    seat = seat_of(state)
    broke = _t.with_player(
        state, seat, resources=replace(state.players[seat].resources, spice=0)
    )
    p = make(broke)
    plain = space_entity("spice_refinery", p.ctx.board)
    cut = space_with_cost_cut(plain, "spice")
    no_discount = SpiceRefineryAbility(plain).evaluate(p, Request())
    free = SpiceRefineryAbility(cut).evaluate(p, Request())
    assert no_discount.response == ((0,),)  # holds no spice: sells nothing
    assert free.response == ((1,),)
    assert free.value == p.solari_value(4)
    v_plain = SpiceRefineryAbility(plain).value_for_player(p, ()).sum
    v_free = SpiceRefineryAbility(cut).value_for_player(p, ()).sum
    assert v_free > v_plain


def test_reveal_recruit_window_closes_once_the_deploy_key_is_used() -> None:
    from dune_imperium.agents.app_ai.abilities.bloodlines_systems import (
        deploy_window_open,
    )

    p = make(bl_state())

    class _Ctx:
        def __init__(self, ctx: object, reveal: dict[str, object]) -> None:
            self._ctx = ctx
            self._reveal = reveal

        def own_frame_context(self, kind: str) -> object:
            return self._reveal if kind == "reveal" else None

        def __getattr__(self, name: str) -> object:
            return getattr(self._ctx, name)

    for deployed, expected in ((0, True), (1, False)):
        p.ctx = _Ctx(  # type: ignore[assignment]
            make(bl_state()).ctx,
            {"combat_deployment": True, "reveal_units_deployed": deployed},
        )
        assert deploy_window_open(p) is expected
