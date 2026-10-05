"""App-style Bloodlines systems: ``abilities/bloodlines_systems.py`` and
``profile/bloodlines.py`` with their hooks in the shared profile methods.

Spec: ``docs/app-ai/bloodlines-systems.md`` (section and D-numbers below), as
settled by ``docs/app-ai-plan.md`` §11.7. States are real Bloodlines + Tech
Module (+ CHOAM) games advanced by ``testing.first_decision``; the fields a
formula reads are set with ``with_player`` / ``with_state`` and the prices a
worked example fixes are stubbed on the ``Profile``. Numbers are Hard.
"""

from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import catalog
from dune_imperium.agents.app_ai import testing as _t
from dune_imperium.agents.app_ai.abilities import bloodlines_systems as bs
from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities.base import (
    PORTS,
    Ability,
    Answer,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    UnportedAbility,
    abilities_of,
    ability_for,
)
from dune_imperium.agents.app_ai.abilities.leaders import (
    DesertScoutsAbility,
    SignetAbility,
)
from dune_imperium.agents.app_ai.abilities.tech import (
    AcquireTechAbility,
    TechTileAcquiredAbility,
)
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile import bloodlines as pb
from dune_imperium.agents.app_ai.profile import combat as pc
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState

_AS = "worm.canis.abilities.AppStyle.Bloodlines."
BL = RulesetConfig(choam_module=True, bloodlines=True, tech_module=True)


# =================================================================================
# Fixtures
# =================================================================================


@cache
def bl_state() -> GameState:
    """Round 1, the first Agent turn of a Bloodlines + Tech Module + CHOAM game."""

    return _t.first_decision("turn", config=BL)


@cache
def base_state() -> GameState:
    """Round 1, the first Agent turn of an Uprising + CHOAM game."""

    return _t.first_decision("turn")


def seat_of(state: GameState) -> int:
    decision = _t.ENGINE.current_decision(state)
    owner = getattr(decision, "owner", None)
    assert isinstance(owner, int)
    return owner


def make(state: GameState | None = None, *, rng_seed: int = 0) -> Profile:
    state = bl_state() if state is None else state
    return _t.make_profile(state, seat_of(state), rng_seed=rng_seed)


def me_with(state: GameState | None = None, **changes: object) -> GameState:
    """``state`` (default ``bl_state``) with the deciding seat changed."""

    state = bl_state() if state is None else state
    return _t.with_player(state, seat_of(state), **changes)


def with_troops(
    state: GameState | None = None,
    garrison: int | None = None,
    conflict: int = 0,
    **changes: object,
) -> GameState:
    """The deciding seat with ``garrison``/``conflict`` troops (the supply
    keeps the seat's 12 troops accounted for)."""

    state = bl_state() if state is None else state
    me = state.players[seat_of(state)]
    total = me.troops_supply + me.troops_garrison + me.troops_conflict
    garrison = me.troops_garrison if garrison is None else garrison
    return me_with(
        state,
        troops_garrison=garrison,
        troops_conflict=conflict,
        troops_supply=total - garrison - conflict,
        **changes,
    )


def give_tech(state: GameState, *tech_ids: str) -> GameState:
    """Move Tech tiles from the stacks into the deciding seat's supply."""

    stacks = tuple(
        tuple(t for t in stack if t not in tech_ids) for stack in state.tech_stacks
    )
    state = _t.with_state(state, tech_stacks=stacks)
    seat = seat_of(state)
    held = state.players[seat].tech_ids
    return _t.with_player(state, seat, tech_ids=(*held, *tech_ids))


def give_skills(state: GameState, *skill_instances: str) -> GameState:
    """Move Skill tiles (instance ids) to the deciding seat."""

    state = _t.with_state(
        state,
        skill_stack=tuple(s for s in state.skill_stack if s not in skill_instances),
        skill_face_up=tuple(s for s in state.skill_face_up if s not in skill_instances),
    )
    seat = seat_of(state)
    held = state.players[seat].skill_ids
    return _t.with_player(state, seat, skill_ids=(*held, *skill_instances))


def leader(state: GameState, leader_id: str) -> GameState:
    return me_with(state, leader_id=leader_id, leader_face_id=leader_id)


def at_arc(p: Profile, monkeypatch: pytest.MonkeyPatch, arc: int) -> None:
    monkeypatch.setattr(p, "game_arc", lambda: arc)


def stub(p: Profile, monkeypatch: pytest.MonkeyPatch, **values: float) -> None:
    """Stub zero-argument float prices (``intrigue_value``, ...)."""

    for name, value in values.items():
        monkeypatch.setattr(p, name, lambda value=value: value)


def stub_summer(
    p: Profile, monkeypatch: pytest.MonkeyPatch, name: str, value: float
) -> None:
    monkeypatch.setattr(p, name, lambda: Summer(value))


def request(*infos: TargetInfo) -> Request:
    return Request(infos=infos)


def entities(*items: Entity) -> TargetInfo:
    return TargetInfo(entities=items)


def options(*items: int) -> TargetInfo:
    return TargetInfo(options=items)


def space(space_id: str, p: Profile) -> Entity:
    return catalog.space_entity(space_id, p.ctx.board)


def skill(skill_id: str) -> Entity:
    return catalog.skill_entity(skill_id)


def tile(tech_id: str) -> Entity:
    return catalog.tech_entity(tech_id)


def ability(entity: Entity, cls: type[Ability]) -> Ability:
    for found in abilities_of(entity):
        if isinstance(found, cls):
            return found
    raise AssertionError(f"{entity.ref} has no {cls.__name__}")


# =================================================================================
# Coverage: every ability id of every bloodlines-systems.md archetype
# =================================================================================


def _systems_archetype_shorts() -> list[str]:
    leaders = [
        short for short in catalog.LEADER_ARCHETYPES.values() if ".AppStyle." in short
    ]
    return [
        catalog.COMMANDER_ARCHETYPE,
        *catalog.SKILL_ARCHETYPES.values(),
        *catalog.TECH_ARCHETYPES.values(),
        *leaders,
        *catalog.NAVIGATION_ARCHETYPES.values(),
        *catalog.BLOODLINES_SPACE_ARCHETYPES.values(),
    ]


def _systems_ability_ids() -> list[str]:
    ids: list[str] = []
    for short in _systems_archetype_shorts():
        arch = catalog.archetype(short)
        for key in ("WormAbilityIDs", "CustomAbilityIDs"):
            value = arch.attributes.get(key, ())
            assert isinstance(value, tuple)
            ids.extend(str(i) for i in value)
    # Ids the spec attaches outside an archetype: the board overlays (§6) and
    # the playmat's paid re-buy (§2.2), the Navigation base class (§5).
    ids += [
        catalog.ACQUIRE_COMMANDER_ABILITY,
        catalog.ACQUIRE_TECH_ABILITY,
        _AS + "RecruitCommanderAbility",
        _AS + "NavigationAbility",
    ]
    return sorted(set(ids))


def test_systems_archetypes_are_the_spec_tables() -> None:
    shorts = _systems_archetype_shorts()
    assert len(shorts) == 1 + 7 + 18 + 9 + 10 + 1


@pytest.mark.parametrize("ability_id", _systems_ability_ids())
def test_every_systems_ability_id_resolves_to_a_port(ability_id: str) -> None:
    assert ability_id in PORTS
    owner = Entity(Kind.SPACE, "x")
    assert not isinstance(ability_for(ability_id, owner), UnportedAbility)


def test_every_app_style_bloodlines_id_is_registered_under_its_spec_name() -> None:
    mine = {i for i in _systems_ability_ids() if i.startswith(_AS)}
    for ability_id in mine:
        assert PORTS[ability_id].APP_CLASS == ability_id
    assert len(mine) == 57


_BASES: list[tuple[str, type[Ability]]] = [
    ("SkillRevealAbility", g.TriggeredAbility),
    ("CannySkillAbility", g.TriggeredAbility),
    ("FierceSkillAbility", g.TriggeredAbility),
    ("LoyalSkillAbility", g.TriggeredAbility),
    ("DesperateSkillAbility", g.DeferredAbility),
    ("AcquireCommanderAbility", g.DeferredAbility),
    ("RecruitCommanderAbility", g.DeferredAbility),
    ("AcquireEffectsBonusAbility", Ability),
    ("AdvancedDataAnalysisAbility", g.DeferredAbility),
    ("SpyDronesAbility", g.DeferredAbility),
    ("RapidDropshipsAbility", g.DeferredAbility),
    ("ForbiddenWeaponsAbility", g.DeferredAbility),
    ("GeneLockedVaultAcquiredAbility", TechTileAcquiredAbility),
    ("ServoReceiversAcquiredAbility", TechTileAcquiredAbility),
    ("PlasteelBladesAbility", g.TriggeredAbility),
    ("PanopticonAbility", g.TriggeredAbility),
    ("FedaykinManeuverSignetAbility", SignetAbility),
    ("CorrinoLiaisonSignetAbility", SignetAbility),
    ("IntoTheFraySignetAbility", SignetAbility),
    ("SmuggleSpiceSignetAbility", SignetAbility),
    ("ListenersSignetAbility", SignetAbility),
    ("JudgeOfTheChangeSignetAbility", SignetAbility),
    ("ReverseEngineeringSignetAbility", SignetAbility),
    ("SecretProjectAbility", g.DeferredAbility),
    ("TueksSietchDeferredAbility", g.DeferredAbility),
    ("NavigationAbility", g.DeferredAbility),
    ("NavigationCard7Ability", bs.NavigationAbility),
]


@pytest.mark.parametrize(("name", "base"), _BASES)
def test_app_base_classes(name: str, base: type[Ability]) -> None:
    assert issubclass(PORTS[_AS + name], base)


def test_timings_and_selection_modes() -> None:
    p = make()
    assert bs.SkillRevealAbility.timing == Timing.REVEAL
    assert bs.CannySkillAbility.timing == Timing.COMBAT
    assert bs.DesperateSkillAbility.timing == Timing.REVEAL
    assert bs.AcquireCommanderAbility.timing == Timing.AGENT
    assert bs.RapidDropshipsAbility.timing == Timing.AGENT
    assert bs.ForbiddenWeaponsAbility.timing == Timing.REVEAL
    owner = Entity(Kind.SPACE, "x")
    explicit: tuple[type[g.DeferredAbility], ...] = (
        bs.AcquireCommanderAbility,
        bs.ForbiddenWeaponsAbility,
        bs.SmuggleSpiceSignetAbility,
        bs.ReverseEngineeringSignetAbility,
        bs.SecretProjectAbility,
        bs.TueksSietchDeferredAbility,
    )
    optional: tuple[type[g.DeferredAbility], ...] = (
        bs.DesperateSkillAbility,
        bs.RecruitCommanderAbility,
        bs.AdvancedDataAnalysisAbility,
        bs.SpyDronesAbility,
        bs.RapidDropshipsAbility,
        bs.FedaykinManeuverSignetAbility,
        bs.CorrinoLiaisonSignetAbility,
        bs.IntoTheFraySignetAbility,
        bs.ListenersSignetAbility,
    )
    for cls in explicit:
        assert cls(owner).selection_mode(p) is SelectionMode.EXPLICIT, cls
    for cls in optional:
        assert cls(owner).selection_mode(p) is SelectionMode.OPTIONAL, cls
    assert bs.JudgeOfTheChangeSignetAbility(owner).can_run_immediately(p)
    assert bs.ServoReceiversAcquiredAbility.always_run_immediately


# =================================================================================
# §1.1 Units: Commanders and the Into the Fray Agent
# =================================================================================


def test_unit_counts_include_commanders_and_the_conflict_agent() -> None:
    state = with_troops(
        None,
        2,
        1,
        commanders_garrison=1,
        commanders_supply=0,
        commanders_conflict=1,
        sandworms_conflict=1,
    )
    me = state.players[seat_of(state)]
    assert pc._garrison_units(me) == 3
    assert pc._garrison_troops(me) == 3
    assert pc._conflict_units(me) == 3
    assert pc._conflict_troops(me) == 2


def test_troop_abundance_counts_garrison_commanders() -> None:
    """§1.1: ``GetAbundanceLevel(Troops)`` reads ``P.GarrisonTroops``
    (profile-economy §2.3), which counts a garrison Commander as a troop.

    Hard bands: garrison troops 0–1 Poor, 2–3 Supplied, 4 Rich. One troop
    and three Commanders is four garrison troops (Rich), as four troops are.
    """

    one = with_troops(None, 1, 0, commanders_garrison=0)
    mixed = with_troops(None, 1, 0, commanders_garrison=3)
    four = with_troops(None, 4, 0, commanders_garrison=0)
    assert make(one).abundance_level(Attr.TROOPS) == 0
    assert make(four).abundance_level(Attr.TROOPS) == 2
    assert make(mixed).abundance_level(Attr.TROOPS) == 2
    assert make(mixed).troop_value(1) == make(four).troop_value(1)


def test_strength_value_counts_a_lone_commander_as_a_conflict_unit() -> None:
    """``GetResourceValue(Strength)`` is 0 with no unit and <= 1 Agent left."""

    me = _me(bl_state())
    away = (*me.agent_locations, "arrakeen")[-1:]
    lone = me_with(commanders_conflict=1, agents_available=1, agent_locations=away)
    none = me_with(agents_available=1, agent_locations=away)
    assert make(none).strength_value(2) == 0.0
    assert make(lone).strength_value(2) > 0.0


def test_desert_scouts_cost_counts_commanders() -> None:
    state = me_with(commanders_conflict=1)
    p = make(state)
    assert DesertScoutsAbility(Entity(Kind.LEADER, "x")).meets_cost(p)


# =================================================================================
# §1.2 Commander and Skill prices
# =================================================================================


def test_commander_unit_value_is_a_troop() -> None:
    p = make()
    assert p.commander_unit_value() == p.troop_value(1) + p.strength_value(0)
    assert p.commander_unit_value() == p.troop_value(1)


def test_commander_cost_reads_the_rules() -> None:
    assert make().commander_cost() == 2
    assert make(give_tech(bl_state(), "sardaukar_high_command")).commander_cost() == 1
    assert make(me_with(commander_discount_turn=2)).commander_cost() == 0


def test_commander_acquire_net_and_recruit_net() -> None:
    p = make()
    unit = p.commander_unit_value()
    cost = p.solari_value(2)
    assert p.commander_acquire_net(None) == pytest.approx(unit - cost)
    assert p.commander_acquire_net("driven") == pytest.approx(
        unit + p.skill_value("driven") - cost
    )
    assert p.recruit_net() == pytest.approx(unit - cost)
    assert p.recruit_net(cost=0) == pytest.approx(unit)


def test_plasteel_blades_adds_the_extra_skill_to_both_nets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plan §11.7: ``max(0, SkillValue(best other) − HeldTileValue)``."""

    p = make(give_tech(bl_state(), "plasteel_blades"))
    at_arc(p, monkeypatch, 1)
    values = {"canny": 9.0, "hardy": 8.5, "charismatic": 1.0, "driven": 2.0}
    monkeypatch.setattr(p, "skill_value", lambda k, w=(): values[k])
    held = p.held_tile_value("plasteel_blades")
    assert held == 6.0
    unit = p.commander_unit_value()
    cost = p.solari_value(2)
    # Taking Canny leaves Hardy (8.5) as the extra Skill.
    assert p.plasteel_extra_skill_value("canny") == pytest.approx(2.5)
    assert p.commander_acquire_net("canny") == pytest.approx(unit + 9.0 - cost + 2.5)
    assert p.recruit_net() == pytest.approx(unit - cost + 3.0)
    values.update(canny=1.0, hardy=1.0)
    assert p.plasteel_extra_skill_value(None) == 0.0


# =================================================================================
# §2 Skills
# =================================================================================


def test_skill_reveal_prices() -> None:
    p = make()
    assert p.skill_value("driven") == p.spice_value(1)
    assert p.skill_value("charismatic") == p.resource_value(Attr.PERSUASION, 1)
    assert p.skill_value("hardy") == p.troop_value(1)


def test_canny_needs_a_landsraad_agent_or_space() -> None:
    state = with_troops(None, None, 1)
    p = make(state)
    assert p.skill_value("canny") == 0.0
    assert p.skill_value("canny", (space("high_council", p),)) == p.strength_value(2)
    assert p.skill_value("canny", (space("arrakeen", p),)) == 0.0
    on = make(me_with(state, agent_locations=("gather_support",), agents_available=1))
    assert on.ctx.me.agent_locations == ("gather_support",)
    assert on.skill_value("canny") == on.strength_value(2)


def test_fierce_gains_a_sword_against_an_opposing_sandworm() -> None:
    state = with_troops(None, None, 1)
    p = make(state)
    assert p.skill_value("fierce") == p.strength_value(1)
    other = (seat_of(state) + 1) % 4
    worm = _t.with_player(state, other, sandworms_conflict=1)
    q = make(worm)
    assert q.skill_value("fierce") == q.strength_value(2)


def test_loyal_needs_three_emperor_influence() -> None:
    state = with_troops(None, None, 1)
    me = state.players[seat_of(state)]
    assert make(state).skill_value("loyal") == 0.0
    loyal = me_with(state, influence=replace(me.influence, emperor=3))
    assert make(loyal).skill_value("loyal") == make(loyal).strength_value(2)


def test_desperate_uses_devious_strengths_conditions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make(me_with(commanders_conflict=1))
    desperate = ability(skill("desperate"), bs.DesperateSkillAbility)
    assert isinstance(desperate, bs.DesperateSkillAbility)
    assert desperate.meets_cost(p)
    assert desperate.value_for_player(p).sum == p.strength_value(3)
    monkeypatch.setattr(p, "is_final_round", lambda: True)
    answer = desperate.evaluate(p, request(entities(skill("desperate"))))
    assert answer == Answer(100.0, (("desperate",),), "Desperate | Last Round")
    monkeypatch.setattr(p, "is_final_round", lambda: False)
    monkeypatch.setattr(p, "conflict_posture_bounds", lambda: (5.0, 10.0))
    monkeypatch.setattr(p, "current_conflict_interest", lambda: Summer(10.0))
    monkeypatch.setattr(p, "est_strength", lambda: _int_summer(6))
    monkeypatch.setattr(p, "est_opponent_strength", lambda seat: _int_summer(10))
    assert desperate.evaluate(p, request()).value == 100.0
    monkeypatch.setattr(p, "est_opponent_strength", lambda seat: _int_summer(11))
    assert desperate.evaluate(p, request()).response is None
    monkeypatch.setattr(p, "current_conflict_interest", lambda: Summer(6.0))
    monkeypatch.setattr(p, "est_opponent_strength", lambda seat: _int_summer(7))
    assert desperate.evaluate(p, request()).label == "Desperate | Mid conflict interest"


def _int_summer(value: int) -> object:
    from dune_imperium.agents.app_ai.summer import IntSummer

    return IntSummer(value)


def test_acquire_commander_value_and_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    state = me_with(resources=replace(_me(bl_state()).resources, solari=5))
    p = make(state)
    hc = space("sardaukar", p)  # High Council's own 5 Solari would leave none
    acquire = ability(hc, bs.AcquireCommanderAbility)
    nets = {"canny": 3.0, "hardy": 4.0, "charismatic": 4.0, "driven": -1.0, None: -0.5}
    monkeypatch.setattr(p, "commander_acquire_net", lambda k, w=(): nets[k])
    assert acquire.value_for_player(p, ()).sum == 4.0
    answer = acquire.evaluate(
        p, request(entities(*(skill(k) for k in ("canny", "hardy", "charismatic"))))
    )
    assert answer.response == (("hardy",),)  # first strictly best
    assert answer.value == 4.0
    no_skill = acquire.evaluate(p, request())
    assert no_skill == Answer(0.5, (), "Sardaukar Commander | decline")
    nets[None] = 1.0
    assert acquire.evaluate(p, request()).response == ((),)


def test_acquire_commander_value_is_zero_without_commander_or_money() -> None:
    p = make(me_with(resources=replace(_me(bl_state()).resources, solari=1)))
    acquire = ability(space("high_council", p), bs.AcquireCommanderAbility)
    assert acquire.value_for_player(p, ()).sum == 0.0  # 2 Solari needed
    gone = _t.with_state(bl_state(), sardaukar_commander_space_ids=())
    q = make(me_with(gone, resources=replace(_me(gone).resources, solari=9)))
    acquire = ability(space("high_council", q), bs.AcquireCommanderAbility)
    assert acquire.value_for_player(q, ()).sum == 0.0


def test_acquire_commander_never_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make(me_with(resources=replace(_me(bl_state()).resources, solari=5)))
    monkeypatch.setattr(p, "commander_acquire_net", lambda k, w=(): -2.0)
    acquire = ability(space("sardaukar", p), bs.AcquireCommanderAbility)
    assert acquire.value_for_player(p, ()).sum == 0.0


def _me(state: GameState) -> PlayerState:
    return state.players[seat_of(state)]


def test_recruit_commander(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    recruit = bs.RecruitCommanderAbility(Entity(Kind.LEADER, "playmat"))
    monkeypatch.setattr(p, "recruit_net", lambda cost=None: -0.1)
    assert recruit.evaluate(p, request()).response is None
    monkeypatch.setattr(p, "recruit_net", lambda cost=None: 0.7)
    assert recruit.evaluate(p, request()) == Answer(0.7, (), "Recruit Commander")
    monkeypatch.setattr(bs, "deploy_window_open", lambda q: True)
    assert recruit.evaluate(p, request()).value == 100.0


# =================================================================================
# §1.3 Deploy split, §1.4 retreat and forced loss
# =================================================================================


def test_deploy_order_puts_commanders_first_only_with_a_skill() -> None:
    plain = make(me_with(commanders_garrison=1))
    assert not plain.commanders_deploy_first()
    assert plain.deploy_split(2, 3, 1) == (2, 0)
    state = give_skills(me_with(commanders_garrison=1), "skill:canny:0")
    skilled = make(state)
    assert skilled.commanders_deploy_first()
    assert skilled.deploy_split(2, 3, 1) == (1, 1)
    fighting = make(me_with(state, commanders_conflict=1, commanders_garrison=0))
    assert not fighting.commanders_deploy_first()


def test_retreat_takes_troops_first() -> None:
    p = make(with_troops(None, None, 2, commanders_conflict=1))
    assert p.retreat_split(1) == (1, 0)
    assert p.retreat_split(3) == (2, 1)


def test_lose_unit_values() -> None:
    state = give_skills(
        with_troops(None, None, 1, commanders_conflict=1, commanders_garrison=1),
        "skill:fierce:0",
        "skill:driven:0",
        "skill:desperate:0",
    )
    p = make(state)
    assert p.lose_unit_value("garrison", False) == p.troop_value(1)
    assert p.lose_unit_value("garrison", True) == p.commander_unit_value()
    assert p.lose_unit_value("conflict", False) == p.strength_value(2)
    expected = (
        p.strength_value(2) + p.skill_value("fierce") + p.skill_value("driven") + 0.0
    )
    assert p.lose_unit_value("conflict", True) == pytest.approx(expected)
    revealed = make(me_with(state, has_revealed=True))
    assert revealed.lose_unit_value("conflict", True) == pytest.approx(
        revealed.strength_value(2) + revealed.skill_value("fierce")
    )
    two = make(me_with(state, commanders_conflict=2, commanders_garrison=0))
    assert two.lose_unit_value("conflict", True) == two.strength_value(2)


def test_reveal_skills_are_paid_once_the_reveal_begins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§1.4: a Reveal Skill's loss is its value only before the Reveal
    begins. ``has_revealed`` turns True only when the Reveal turn ends, so
    inside the seat's own open Reveal turn (bonus already paid,
    ``rules/reveal_turn.py``) the Reveal Skills lose nothing."""

    state = give_skills(
        with_troops(None, None, 1, commanders_conflict=1),
        "skill:fierce:0",
        "skill:driven:0",
    )
    p = make(state)
    before = p.lose_unit_value("conflict", True)
    assert before == pytest.approx(
        p.strength_value(2) + p.skill_value("fierce") + p.skill_value("driven")
    )
    monkeypatch.setattr(
        p.ctx, "own_frame_context", lambda kind: {} if kind == "reveal" else None
    )
    assert p.active_skill_loss("driven") == 0.0
    assert p.active_skill_loss("fierce") == p.skill_value("fierce")
    assert p.lose_unit_value("conflict", True) == pytest.approx(
        p.strength_value(2) + p.skill_value("fierce")
    )


def test_chani_loses_the_tactics_reward(monkeypatch: pytest.MonkeyPatch) -> None:
    state = leader(with_troops(None, None, 1, tactics_track_space=4), "chani")
    p = make(state)
    assert p.tactics_reward(1) == p.spice_value(1)
    assert p.lose_unit_value("conflict", False) == pytest.approx(
        p.strength_value(2) - p.spice_value(1)
    )
    assert p.lose_unit_value("garrison", False) == p.troop_value(1)


def test_tactics_reward_follows_the_track() -> None:
    p = make(leader(me_with(tactics_track_space=2), "chani"))
    assert p.tactics_reward(2) == 0.0  # 3, 4
    assert p.tactics_reward(3) == p.spice_value(1)  # passes 5
    assert p.tactics_reward(8) == p.spice_value(1) + p.water_value(1)  # reaches 10
    assert make().tactics_reward(5) == 0.0  # not Chani


def test_least_loss_choice_breaks_ties_with_the_agent_rng() -> None:
    p = make()
    assert p.least_loss_choice([3.0, 1.0, 2.0]) == 1
    picks = {make(rng_seed=s).least_loss_choice([1.0, 5.0, 1.0]) for s in range(30)}
    assert picks == {0, 2}


# =================================================================================
# §1.7 Icon grants and cost changes
# =================================================================================


def test_icon_grants() -> None:
    signet = catalog.card_entity("player:0:starter:signet_ring:0")
    dagger = catalog.card_entity("player:0:starter:dagger:0")
    plain = make()
    assert plain.icon_list(signet) == ("Pentagon", "Circle", "Triangle")
    mohiam = make(leader(bl_state(), "gaius_helen_mohiam"))
    assert mohiam.icon_list(dagger) == (*dagger.list_attr("IconList"), "Spy")
    servo = make(give_tech(bl_state(), "servo_receivers"))
    assert servo.icon_list(signet) == (
        "Pentagon",
        "Circle",
        "Triangle",
        "Emperor",
        "SpacingGuild",
        "BeneGesserit",
        "Fremen",
    )
    assert servo.icon_list(dagger) == dagger.list_attr("IconList")


def test_deck_icons_read_the_grants() -> None:
    plain = make()
    mohiam = make(leader(bl_state(), "gaius_helen_mohiam"))
    assert mohiam.deck_agent_icons().get("Spy", 0) == plain.deck_agent_icons().get(
        "Spy", 0
    ) + sum(1 for c in mohiam._deck_cards() if "Spy" not in c.list_attr("IconList"))


def test_icon_grant_value() -> None:
    """§1.7: the best placement the grant opens over the best without it."""

    p = make()
    candidates = ("dutiful_service", "arrakeen", "accept_contract")

    def valid(card: Entity, icons: object) -> list[Entity]:
        assert isinstance(icons, tuple)
        return [
            space(sid, p)
            for sid in candidates
            if space(sid, p).attr("AgentIcon") in icons
        ]

    def best(grant: tuple[str, ...]) -> float:
        values = []
        for instance in p.ctx.hand:
            card = catalog.card_entity(instance, p.ctx.seat)
            icons = (*p.icon_list(card), *grant)
            value = p.best_agent_eval(card, icons, valid)
            if value is not None:
                values.append(value)
        return max(values, default=0.0)

    expected = max(0.0, best(("Emperor",)) - best(()))
    assert p.icon_grant_value(("Emperor",), valid) == pytest.approx(expected)
    assert p.icon_grant_value((), valid) == 0.0


def test_duncan_swordmaster_costs_two_less() -> None:
    p = make()
    sword = space("swordmaster", p)
    assert g.space_solari_cost(p, sword) == 8
    duncan = make(leader(bl_state(), "duncan_idaho"))
    assert g.space_solari_cost(duncan, sword) == 6


def test_space_cost_cut_variant() -> None:
    p = make()
    shipping = space("shipping", p)
    cut = pb.space_with_cost_cut(shipping, "spice")
    assert cut.int_attr("SpiceDiscount") == -1
    base = g.SpaceAbility(shipping).value_for_player(p).sum
    cheaper = g.SpaceAbility(cut).value_for_player(p).sum
    assert cheaper - base == pytest.approx(p.spice_value(-2) - p.spice_value(-3))
    sardaukar = pb.space_with_cost_cut(space("sardaukar", p), "solari")
    assert sardaukar.int_attr("SolariDiscount") == -1


# =================================================================================
# §3 Tech Module
# =================================================================================


def test_board_reads_follow_the_tech_stacks() -> None:
    p = make()
    state = bl_state()
    assert [t.ref for t in p.tech_face_up_tiles()] == [s[0] for s in state.tech_stacks]
    assert all(t.kind is Kind.TECH for t in p.tech_face_up_tiles())
    assert p.tech_negotiator_count() == 0
    assert p.tech_dreadnoughts_in_supply() == 0
    assert make(base_state()).tech_face_up_tiles() == []


def test_tech_targets_use_our_cost_rule() -> None:
    state = bl_state()
    tops = [s[0] for s in state.tech_stacks]
    costs = {t: tile(t).int_attr("SpiceCost") for t in tops}
    cheapest = min(costs.values())
    me = _me(state)
    poor = me_with(resources=replace(me.resources, spice=cheapest - 1))
    assert make(poor).tech_acquire_targets(0, False) == []
    # The High Council seat's -1 makes the cheapest tile affordable.
    seated = me_with(poor, high_council=True)
    assert [t.ref for t in make(seated).tech_acquire_targets(0, False)] == [
        t for t in tops if costs[t] == cheapest
    ]
    # A Tech Discount icon does the same.
    assert make(poor).tech_acquire_targets(1, False) != []
    rich = me_with(resources=replace(me.resources, spice=20))
    assert [t.ref for t in make(rich).tech_acquire_targets(0, False)] == tops


def test_secret_project_is_an_own_candidate_at_one_less() -> None:
    state = bl_state()
    project = state.tech_stacks[0][-1]
    stacks = (state.tech_stacks[0][:-1], *state.tech_stacks[1:])
    state = _t.with_state(state, tech_stacks=stacks)
    cost = tile(project).int_attr("SpiceCost")
    me = _me(state)
    kota = me_with(
        state,
        secret_project_tech_id=project,
        resources=replace(me.resources, spice=cost - 1),
    )
    targets = [t.ref for t in make(kota).tech_acquire_targets(0, False)]
    assert targets[-1] == project
    # An opponent never sees it.
    other = (seat_of(kota) + 1) % 4
    q = _t.make_profile(kota, other)
    assert q.ctx.secret_project_tech_id == ""


def test_advanced_data_analysis_needs_an_own_spy() -> None:
    state = bl_state()
    stacks = tuple(
        ("advanced_data_analysis", *(t for t in s if t != "advanced_data_analysis"))
        if i == 0
        else tuple(t for t in s if t != "advanced_data_analysis")
        for i, s in enumerate(state.tech_stacks)
    )
    state = _t.with_state(state, tech_stacks=stacks)
    me = _me(state)
    rich = me_with(state, resources=replace(me.resources, spice=20))
    assert "advanced_data_analysis" not in [
        t.ref for t in make(rich).tech_acquire_targets(0, False)
    ]
    post = next(iter(catalog.POST_INDEX))
    spied = me_with(rich, spy_post_ids=(post,), spies_supply=2)
    assert "advanced_data_analysis" in [
        t.ref for t in make(spied).tech_acquire_targets(0, False)
    ]


def test_landsraad_acquire_tech_runs_on_the_bloodlines_tiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§3.1: the Rise of Ix ``AcquireTechAbility`` overlay on the Landsraad
    spaces, unchanged, over the Tech Module's tops and cost rule."""

    me = _me(bl_state())
    p = make(me_with(resources=replace(me.resources, spice=20)))
    at_arc(p, monkeypatch, 1)
    acquire = ability(space("gather_support", p), AcquireTechAbility)
    assert acquire.value_for_player(p, ()).sum == p.buy_tech_value(0, False)
    tops = p.tech_face_up_tiles()
    answer = acquire.evaluate(p, request(entities(*tops)))
    best = max(tops, key=lambda t: p.tech_tile_acquire_value(t).sum)
    assert answer.response == ((best.ref,),)


def test_held_tile_value_is_acquire_value_times_the_arc_mod(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make()
    for arc, expected in ((0, 6.0), (1, 4.0), (2, 2.0)):
        at_arc(p, monkeypatch, arc)
        assert p.held_tile_value("planetary_array") == expected
        assert p.held_tile_value("training_depot") == 2.0
    at_arc(p, monkeypatch, 2)
    assert p.held_tile_value("delivery_bay") == 0.0


def _tile_value(p: Profile, tech_id: str) -> float:
    return p.tech_tile_acquire_value(tile(tech_id)).sum


def test_worked_tile_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """§3.2 worked values (Hard, Supplied abundance, Mid arc unless stated)."""

    p = make()
    monkeypatch.setattr(p, "synergy_mod", lambda card: Summer())
    stub(p, monkeypatch, intrigue_value=2.5, trash_card_value=2.75, trash_mod=-1.0)
    monkeypatch.setattr(p, "victory_point_value", lambda n: 6.0 * n)
    stub_summer(p, monkeypatch, "spy_value", 1.66)
    at_arc(p, monkeypatch, 1)
    assert _tile_value(p, "training_depot") == 2.0
    assert _tile_value(p, "self_destroying_messages") == 13.0
    assert _tile_value(p, "sardaukar_high_command") == 20.0
    assert _tile_value(p, "spy_drones") == pytest.approx(13.32)
    stub_summer(p, monkeypatch, "spy_value", 1.66 * 0.67)
    assert _tile_value(p, "advanced_data_analysis") == pytest.approx(4.8878)
    at_arc(p, monkeypatch, 2)
    assert _tile_value(p, "training_depot") == 0.0  # 2.0 < 2.2
    assert _tile_value(p, "planetary_array") == pytest.approx(2.875)
    at_arc(p, monkeypatch, 0)
    assert _tile_value(p, "training_depot") == 0.0  # no EarlyMod
    assert _tile_value(p, "planetary_array") == pytest.approx(8.625)


def test_acquire_effects_bonus_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    stub(p, monkeypatch, intrigue_value=2.5, trash_card_value=2.0, trash_mod=1.5)
    stub_summer(p, monkeypatch, "spy_value", 1.0)
    bonus = ability(tile("choam_transports"), bs.AcquireEffectsBonusAbility)
    assert bonus.specific_acquire_value(p).sum == g.contract_value_for_player(p).sum
    bonus = ability(tile("planetary_array"), bs.AcquireEffectsBonusAbility)
    assert bonus.specific_acquire_value(p).sum == 3.5
    bonus = ability(tile("spy_drones"), bs.AcquireEffectsBonusAbility)
    assert bonus.specific_acquire_value(p).sum == 2.0


def test_flip_tiles(monkeypatch: pytest.MonkeyPatch) -> None:
    state = give_tech(bl_state(), "advanced_data_analysis", "spy_drones")
    p = make(state)
    ada = ability(tile("advanced_data_analysis"), bs.AdvancedDataAnalysisAbility)
    assert isinstance(ada, bs.AdvancedDataAnalysisAbility)
    assert ada.meets_cost(p)
    assert ada.evaluate(p, request()).value == 100.0
    assert ada.specific_acquire_value(p).sum == -p.spy_value().sum
    flipped = make(me_with(state, tech_flipped=("advanced_data_analysis",)))
    assert not ada.meets_cost(flipped)
    drones = ability(tile("spy_drones"), bs.SpyDronesAbility)
    assert drones.evaluate(p, request()) == Answer(
        100.0, (), "Spy Drones | always flip"
    )


def test_rapid_dropships(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    drop = ability(tile("rapid_dropships"), bs.RapidDropshipsAbility)
    monkeypatch.setattr(p, "units_to_deploy", lambda n, m: 1)
    assert drop.evaluate(p, request()).value == 100.0
    monkeypatch.setattr(p, "units_to_deploy", lambda n, m: 0)
    assert drop.evaluate(p, request()).response is None
    monkeypatch.setattr(p, "units_to_deploy", lambda n, m: 1)
    frame = {"existing_troop_deployment_limit": 2, "space_id": "arrakeen"}
    monkeypatch.setattr(
        p.ctx,
        "own_frame_context",
        lambda kind: frame if kind == "agent_effects" else None,
    )
    assert drop.evaluate(p, request()).response is None


def test_forbidden_weapons_is_a_forced_least_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make()
    fw = ability(tile("forbidden_weapons"), bs.ForbiddenWeaponsAbility)
    S, T = bs.ForbiddenWeaponsAbility.STRENGTH, bs.ForbiddenWeaponsAbility.TRASH
    monkeypatch.setattr(p, "strength_value", lambda n, c=False: 3.0)
    losses = {"emperor": -2.0, "fremen": -1.0}
    monkeypatch.setattr(
        p, "gain_influence_value", lambda f, n, r=-1, a=False: Summer(losses[f])
    )
    tracks = entities(catalog.track_entity("emperor"), catalog.track_entity("fremen"))
    answer = fw.evaluate(p, request(options(S, T), tracks))
    assert answer.response == ((S,), ("fremen",))
    assert answer.value == 2.0
    monkeypatch.setattr(p, "strength_value", lambda n, c=False: 0.0)
    monkeypatch.setattr(p, "spice_value", lambda n: 0.0)
    monkeypatch.setattr(p, "held_tile_value", lambda t: 4.0)
    worst = fw.evaluate(p, request(options(S, T), tracks))
    assert worst == Answer(  # every branch loses: answered at 1.0
        1.0, ((S,), ("fremen",)), "Forbidden Weapons | strength, lose fremen"
    )
    monkeypatch.setattr(p, "held_tile_value", lambda t: 0.5)
    trash = fw.evaluate(p, request(options(S, T), tracks))
    assert trash == Answer(1.0, ((T,),), "Forbidden Weapons | trash")
    bare = fw.evaluate(p, request(options(S)))
    assert bare.response == ((S,),)


def test_forbidden_weapons_shield_wall_acquire(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make(_t.with_state(bl_state(), shield_wall_present=True))
    fw = ability(tile("forbidden_weapons"), bs.ForbiddenWeaponsAbility)
    monkeypatch.setattr(p, "should_blow_wall", lambda: True)
    monkeypatch.setattr(p, "blow_wall_value", lambda: Summer(4.0))
    assert fw.specific_acquire_value(p).sum == 4.0
    monkeypatch.setattr(p, "should_blow_wall", lambda: False)
    assert fw.specific_acquire_value(p).sum == 0.0
    q = make(_t.with_state(bl_state(), shield_wall_present=False))
    monkeypatch.setattr(q, "should_blow_wall", lambda: True)
    assert fw.specific_acquire_value(q).sum == 0.0


def test_gene_locked_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    vault = ability(tile("gene_locked_vault"), bs.GeneLockedVaultAcquiredAbility)
    stub(p, monkeypatch, intrigue_value=2.5, card_draw_value_with_buy_gains=2.5)
    assert vault.specific_acquire_value(p).sum == 2.5
    assert vault.evaluate(p, request()).response == ((0,),)  # tie keeps Intrigue
    stub(p, monkeypatch, card_draw_value_with_buy_gains=2.6)
    assert vault.evaluate(p, request()).response == ((1,),)


def test_plasteel_blades_trade(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make(give_tech(bl_state(), "plasteel_blades"))
    at_arc(p, monkeypatch, 1)
    blades = ability(tile("plasteel_blades"), bs.PlasteelBladesAbility)
    values = {"canny": 7.0, "hardy": 7.0}
    monkeypatch.setattr(p, "skill_value", lambda k, w=(): values[k])
    answer = blades.evaluate(p, request(entities(skill("canny"), skill("hardy"))))
    assert answer == Answer(1.0, (("canny",),), "Plasteel Blades | canny")
    values.update(canny=6.0, hardy=5.0)
    assert blades.evaluate(p, request(entities(skill("canny")))).response is None


def test_servo_receivers_prices_the_leader_signet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make(leader(bl_state(), "liet_kynes"))
    servo = ability(tile("servo_receivers"), bs.ServoReceiversAcquiredAbility)
    assert servo.specific_acquire_value(p).sum == 0.0  # no space: Judge gives 0
    frame = {"space_id": "arrakeen", "card_id": "x"}
    monkeypatch.setattr(
        p.ctx,
        "own_frame_context",
        lambda kind: frame if kind == "agent_effects" else None,
    )
    assert servo.specific_acquire_value(p).sum == p.solari_value(1)


# =================================================================================
# §4 Leaders
# =================================================================================


def test_fedaykin_maneuver(monkeypatch: pytest.MonkeyPatch) -> None:
    me = _me(bl_state())
    state = leader(
        with_troops(
            None,
            None,
            2,
            influence=replace(me.influence, fremen=2),
        ),
        "chani",
    )
    p = make(state)
    fed = bs.FedaykinManeuverSignetAbility(Entity(Kind.LEADER, "chani"))
    draw = p.water_value(-1) + p.draw_two_value()
    assert fed.value_for_player(p).sum == max(0.0, draw)
    R, W = fed.RETREAT, fed.WATER
    monkeypatch.setattr(p, "troops_to_retreat", lambda n: 2)
    monkeypatch.setattr(p, "draw_two_value", lambda: 0.0)
    answer = fed.evaluate(p, request(options(R, W), options(1, 2)))
    assert answer.response == ((R,), (2,))
    assert answer.value == 1.0 + p.tactics_reward(2)
    monkeypatch.setattr(p, "draw_two_value", lambda: 10.0)
    assert fed.evaluate(p, request(options(R, W), options(1, 2))).response == ((W,),)
    monkeypatch.setattr(p, "troops_to_retreat", lambda n: 0)
    monkeypatch.setattr(p, "draw_two_value", lambda: 0.0)
    assert fed.evaluate(p, request(options(R, W), options(1, 2))).response is None


def test_draw_two_is_the_draw2_contract_price() -> None:
    p = make()
    assert p.draw_two_value() == pytest.approx(
        p.card_draw_value() * 2.0 + p.buy_gains(2 * p.possible_persuasion_gain())
    )


def test_corrino_liaison(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make(leader(bl_state(), "count_hasimir_fenring"))
    liaison = bs.CorrinoLiaisonSignetAbility(Entity(Kind.LEADER, "x"))
    T, S = liaison.TRASH, liaison.SPY
    trash = p.trash_card_value() + p.trash_mod()
    spy = p.spy_value().sum
    informant = spy + (p.C.ArrakisInformantMod * spy - spy)
    assert liaison.value_for_player(p).sum == max(trash, informant)
    card = catalog.card_entity("player:0:starter:dagger:0")
    monkeypatch.setattr(p, "card_to_trash", lambda cards, m: (card, 11.0))
    assert liaison.evaluate(p, request(options(T, S), entities(card))).response == (
        (T,),
        (card.ref,),
    )
    monkeypatch.setattr(p, "card_to_trash", lambda cards, m: (None, 1.0))
    assert liaison.evaluate(p, request(options(T, S), entities(card))) == Answer(
        spy, ((S,),), "Corrino Liaison | Spy"
    )
    assert liaison.evaluate(p, request(options(T))).response is None


def test_assassin_raises_the_trash_value() -> None:
    plain = make()
    fenring = make(leader(bl_state(), "count_hasimir_fenring"))
    assert (
        fenring.trash_card_value() == plain.trash_card_value() + fenring.solari_value(1)
    )


def test_into_the_fray(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make(leader(bl_state(), "duncan_idaho"))
    fray = bs.IntoTheFraySignetAbility(Entity(Kind.LEADER, "x"))
    arrakeen = space("arrakeen", p)
    assert fray.value_for_player(p, (arrakeen,)).sum == p.deploy_value(arrakeen)
    assert fray.value_for_player(p, ()).sum == 0.0
    monkeypatch.setattr(p, "units_to_deploy", lambda n, m: (n, m) == (1, 1))
    assert fray.evaluate(p, request()) == Answer(0.5, (), "Into the Fray | deploy")
    monkeypatch.setattr(p, "units_to_deploy", lambda n, m: 0)
    assert fray.evaluate(p, request()).response is None


def test_smuggle_spice(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make(leader(bl_state(), "esmar_tuek"))
    smuggle = bs.SmuggleSpiceSignetAbility(Entity(Kind.LEADER, "x"))
    sietch = catalog.space_entity("tuek_sietch", p.ctx.board)
    later = p.spice_value(1)
    assert smuggle.place_value(p, (sietch,)) == later * p.C.BonusSpiceMod
    assert smuggle.place_value(p) == later
    monkeypatch.setattr(p, "is_final_round", lambda: True)
    assert smuggle.place_value(p) == 0.0
    P, T = smuggle.PLACE, smuggle.TAKE
    basin = space("hagga_basin", p)
    answer = smuggle.evaluate(p, request(options(P, T), entities(basin)))
    assert answer.response == ((T,), ("hagga_basin",))
    monkeypatch.setattr(p, "is_final_round", lambda: False)
    tie = smuggle.evaluate(p, request(options(P, T), entities(basin)))
    assert tie.response == ((T,), ("hagga_basin",))  # take first, place not greater


def test_listeners(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make(leader(bl_state(), "gaius_helen_mohiam"))
    listeners = bs.ListenersSignetAbility(Entity(Kind.LEADER, "x"))
    L, P = listeners.LANDSRAAD, listeners.PAY
    assert listeners.evaluate(p, request(options(L, P))).response == ((L,),)
    stub_summer(p, monkeypatch, "spy_value", 3.0)
    paid = listeners.evaluate(p, request(options(P)))
    assert paid.response == ((P,),)
    assert paid.value == 3.0 + p.spice_value(-1)
    stub_summer(p, monkeypatch, "spy_value", 0.1)
    assert listeners.evaluate(p, request(options(P))).response is None


def test_judge_of_the_change() -> None:
    me = _me(bl_state())
    p = make(leader(bl_state(), "liet_kynes"))
    judge = bs.JudgeOfTheChangeSignetAbility(Entity(Kind.LEADER, "x"))
    assert judge.value_for_player(p, (space("arrakeen", p),)).sum == p.solari_value(1)
    assert judge.value_for_player(p, (space("accept_contract", p),)).sum == (
        p.spice_value(1)
    )
    assert judge.value_for_player(p, (space("high_council", p),)).sum == 0.0
    emperor = make(
        me_with(
            leader(bl_state(), "liet_kynes"),
            influence=replace(me.influence, emperor=2),
        )
    )
    assert judge.value_for_player(emperor, (space("high_council", emperor),)).sum == (
        emperor.water_value(1)
    )
    assert judge.value_for_player(p, ()).sum == 0.0


def test_liet_replaces_sandworms() -> None:
    p = make(leader(bl_state(), "liet_kynes"))
    per = p.trash_card_value() + p.trash_mod() + p.spice_value(1) + p.intrigue_value()
    assert p.sandworm_value(2) == pytest.approx(2 * per)
    assert p.sandworm_value(0) == 0.0


def test_reverse_engineering(monkeypatch: pytest.MonkeyPatch) -> None:
    state = give_tech(leader(bl_state(), "kota_odax_of_ix"), "training_depot")
    p = make(state)
    at_arc(p, monkeypatch, 1)
    rev = bs.ReverseEngineeringSignetAbility(Entity(Kind.LEADER, "x"))
    trash = p.intrigue_value() + p.card_draw_value_with_buy_gains() - 2.0
    assert rev.value_for_player(p).sum == max(p.spice_value(1), trash)
    S, T = rev.SPICE, rev.TRASH
    answer = rev.evaluate(p, request(options(S, T), entities(tile("training_depot"))))
    expected = ((T,), ("training_depot",)) if trash > p.spice_value(1) else ((S,),)
    assert answer.response == expected
    stub(p, monkeypatch, intrigue_value=0.0, card_draw_value_with_buy_gains=0.0)
    assert rev.evaluate(
        p, request(options(S, T), entities(tile("training_depot")))
    ).response == ((S,),)


def test_secret_project_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    project = bs.SecretProjectAbility(Entity(Kind.LEADER, "x"))
    values = {"training_depot": 0.0, "panopticon": 0.0, "glowglobes": 0.0}
    monkeypatch.setattr(p, "tech_tile_acquire_value", lambda t: Summer(values[t.ref]))
    tiles = entities(*(tile(t) for t in values))
    assert project.evaluate(p, request(tiles)).response == (("training_depot",),)
    values["glowglobes"] = 3.0
    assert project.evaluate(p, request(tiles)).response == (("glowglobes",),)


def test_tuek_sietch(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    sietch = catalog.space_entity("tuek_sietch", p.ctx.board)
    deferred = ability(sietch, bs.TueksSietchDeferredAbility)
    spice = p.spice_value(1)
    draw = p.card_draw_value_with_buy_gains()
    assert deferred.value_for_player(p).sum == max(spice, draw)
    esmar = make(leader(bl_state(), "esmar_tuek"))
    assert deferred.value_for_player(esmar).sum == pytest.approx(
        max(esmar.spice_value(1), esmar.card_draw_value_with_buy_gains())
        + esmar.solari_value(1)
    )
    stub(p, monkeypatch, card_draw_value_with_buy_gains=spice)
    assert deferred.evaluate(p, request()).response == ((0,),)  # tie: spice
    stub(p, monkeypatch, card_draw_value_with_buy_gains=spice + 0.01)
    assert deferred.evaluate(p, request()).response == ((1,),)


def test_recall_agent_counts_the_conflict_agent() -> None:
    state = leader(
        me_with(agent_in_conflict=1, agents_available=1, agent_locations=()),
        "duncan_idaho",
    )
    p = make(state)
    assert p.recall_agent_value() != -3.0
    assert make(
        me_with(agent_locations=(), agents_available=2)
    ).recall_agent_value() == (-3.0)


def test_recall_agent_treats_tuek_sietch_as_a_space() -> None:
    p = make()
    agents = [catalog.agent_entity("tuek_sietch", p.ctx.seat)]
    assert p.recall_agent(agents) is not None
    assert p.recall_agent([catalog.agent_entity("conflict", p.ctx.seat)]) is None


# =================================================================================
# §5 Navigation
# =================================================================================


def _yrkoon(**changes: object) -> GameState:
    state = leader(bl_state(), "steersman_y_rkoon")
    return me_with(state, **changes) if changes else state


def test_navigation_option_values(monkeypatch: pytest.MonkeyPatch) -> None:
    me = _me(bl_state())
    state = _yrkoon(
        resources=replace(me.resources, solari=3, spice=5, water=1),
        influence=replace(me.influence, emperor=2, spacing_guild=1),
    )
    p = make(state)
    v = p.navigation_option_value
    assert v(1, 0, 1, None) == p.spice_value(1)
    assert v(1, 1, 1, None) is None  # influence-conditional at setup
    assert v(1, 1, 1, "fremen") == pytest.approx(
        p.gain_influence_value("emperor", 1).sum + p.solari_value(-2)
    )
    assert v(1, 1, 1, "emperor") is None  # G != F
    assert v(3, 0, 2, None) == p.solari_value(2)
    assert v(3, 0, 4, None) == pytest.approx(p.solari_value(2) + p.persuasion_value(1))
    assert v(4, 1, 2, None) is None  # slot 1 only
    assert v(5, 0, 1, None) == p.trash_card_value() + p.trash_mod()
    assert v(6, 1, 1, None) == pytest.approx(p.troop_value(3) + p.solari_value(-3))
    assert v(7, 0, 1, None) == p.spice_value(1)
    assert v(8, 0, 1, "spacing_guild") == p.water_value(1) + p.spice_value(1)
    assert v(8, 0, 1, None) == p.water_value(1)
    assert v(9, 0, 1, None) == p.card_draw_value_with_buy_gains()
    assert v(9, 1, 1, None) == pytest.approx(
        p.spice_value(-5) + p.victory_point_value(1)
    )
    assert v(10, 0, 1, None) is None
    monkeypatch.setattr(p, "best_influence_exchange", lambda a, b: ("x", "y", 1.9))
    assert v(10, 0, 1, "emperor") == 0.0
    monkeypatch.setattr(p, "best_influence_exchange", lambda a, b: ("x", "y", 2.0))
    assert v(10, 0, 1, "emperor") == 2.0


def test_navigation_value_is_the_best_playable_option() -> None:
    me = _me(bl_state())
    p = make(_yrkoon(resources=replace(me.resources, solari=0, spice=0)))
    assert p.navigation_value(6, 1, None) == p.troop_value(1)  # 3 Solari missing
    assert p.navigation_value(10, 1, None) == 0.0


def test_plot_course_term(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _yrkoon(navigation_slots=("navigation_card_8", "navigation_card_3"))
    p = make(state)
    assert p.plot_course_value("spacing_guild", 1) == pytest.approx(
        p.water_value(1) + p.spice_value(1)
    )
    base = p.gain_influence_value("spacing_guild", 1).sum
    assert "Steersman" not in repr(base)
    empty = make(_yrkoon())
    assert empty.plot_course_value("emperor", 1) == 0.0
    # Card 10's exchange values influence again: the nested term is 0.
    ten = make(_yrkoon(navigation_slots=("navigation_card_10",)))
    ten.gain_influence_value("emperor", 1)  # no infinite recursion


def test_plot_course_enters_gain_influence_value() -> None:
    """Added in the leader block like Margot's term, so a later multiplier
    (the Fremen Maker Hooks mod) scales it too; Emperor has none."""

    with_slot = make(_yrkoon(navigation_slots=("navigation_card_9",)))
    without = make(_yrkoon())
    delta = (
        with_slot.gain_influence_value("emperor", 1).sum
        - without.gain_influence_value("emperor", 1).sum
    )
    assert delta == pytest.approx(with_slot.navigation_value(9, 1, "emperor"))
    fremen = (
        with_slot.gain_influence_value("fremen", 1).sum
        - without.gain_influence_value("fremen", 1).sum
    )
    assert fremen == pytest.approx(
        with_slot.navigation_value(9, 1, "fremen") * with_slot.C.MakerHooksFremenMod
    )


def test_navigation_ability_answers_the_best_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = make(_yrkoon(navigation_active_slot=1, navigation_trigger_faction="emperor"))
    nav = catalog.navigation_entity("intrigue:navigation_card_9:0")
    card = ability(nav, bs.NavigationAbility)
    assert isinstance(card, bs.NavigationAbility)
    assert card.card_number == 9
    values = {0: 2.0, 1: 2.0}
    monkeypatch.setattr(p, "navigation_option_value", lambda c, o, s, f: values[o])
    assert card.evaluate(p, request(options(0, 1))).response == ((0,),)
    values[1] = 2.5
    assert card.evaluate(p, request(options(0, 1))).response == ((1,),)


def test_navigation_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make()
    assert bs.navigation_one_faction(p, ["emperor", "fremen"], "emperor") == "fremen"
    paid = catalog.card_entity("imperium:guild_envoy:0")
    free = catalog.card_entity("player:0:starter:dagger:0")
    monkeypatch.setattr(
        p, "card_to_trash", lambda cards, m: (cards[0], 1.0) if cards else (None, 0.0)
    )
    assert bs.navigation_trash_pick(p, [free, paid]) is paid
    assert pb.navigation_number("intrigue:navigation_card_10:0") == 10


# =================================================================================
# §9 Automatic effects as valuation terms
# =================================================================================


def test_hungry_for_spice_term() -> None:
    me = _me(bl_state())
    p = make(
        _yrkoon(
            spice_at_turn_start=0,
            resources=replace(me.resources, spice=1),
        )
    )
    draw = p.card_draw_value() + p.buy_gains(p.possible_persuasion_gain())
    assert p.hungry_for_spice_value(2) == pytest.approx(draw)
    assert p.hungry_for_spice_value(1) == 0.0
    basin = space("hagga_basin", p)  # PossibleSpice 2
    plain = make(
        me_with(spice_at_turn_start=0, resources=replace(me.resources, spice=1))
    )
    delta = (
        g.SpaceAbility(basin).value_for_player(p).sum
        - g.SpaceAbility(basin).value_for_player(plain).sum
    )
    assert delta == pytest.approx(draw)
    granted = make(
        _yrkoon(
            spice_at_turn_start=0,
            resources=replace(me.resources, spice=1),
            hungry_for_spice_granted_turn=True,
        )
    )
    assert granted.hungry_for_spice_value(5) == 0.0


def test_suspensor_suits_term(monkeypatch: pytest.MonkeyPatch) -> None:
    state = give_tech(bl_state(), "suspensor_suits")
    p = make(state)
    base = make().intrigue_value()
    assert p.intrigue_value() == base  # not in an own Agent or Reveal turn
    monkeypatch.setattr(
        p.ctx, "own_frame_context", lambda kind: {} if kind == "reveal" else None
    )
    assert p.intrigue_value() == pytest.approx(base + p.troop_value(1))


def test_reveal_preview_bonus() -> None:
    state = give_skills(
        give_tech(bl_state(), "self_destroying_messages"), "skill:charismatic:0"
    )
    p = make(me_with(state, commanders_conflict=1, reveal_persuasion_bonus=1))
    assert p.reveal_preview_bonus() == 3
    plain = make()
    assert p.possible_persuasion() == plain.possible_persuasion() + 3


def test_planetary_array_in_relative_conflict_value() -> None:
    plain = make()
    owner = make(give_tech(bl_state(), "planetary_array"))
    assert plain.ctx.current_conflict_id is not None
    assert owner.relative_conflict_value().sum == pytest.approx(
        plain.relative_conflict_value().sum + owner.card_draw_value_with_buy_gains()
    )


def test_choam_transports_in_contract_resource_value() -> None:
    from dune_imperium.agents.app_ai.profile.influence import contract_resource_value

    contract = catalog.contract_entity("contract:harvest_3")
    plain = make()
    owner = make(give_tech(bl_state(), "choam_transports"))
    assert contract_resource_value(owner, contract).sum == pytest.approx(
        contract_resource_value(plain, contract).sum
        + owner.card_draw_value_with_buy_gains()
    )
    ability_ = g.ContractAbility(contract)
    assert ability_.resource_value(owner).sum == pytest.approx(
        ability_.resource_value(plain).sum + owner.card_draw_value_with_buy_gains()
    )


def test_ornithopter_fleet_battle_icons(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every icon of the owner, wild and evaluated ones included, is an
    Ornithopter: a held Crysknife matches a Desert Mouse or a wild icon."""

    from dune_imperium.agents.app_ai.profile import influence

    monkeypatch.setattr(influence, "_battle_icon_list", lambda player: ["Crysknife"])
    plain = make()
    fleet = make(give_tech(bl_state(), "ornithopter_fleet"))
    c = plain.C
    base = plain.battle_icon_value("").sum
    matched = base + (c.MatchModStandard * base - base)
    assert plain.battle_icon_value("crysknife").sum == matched
    assert plain.battle_icon_value("desert_mouse").sum == base
    assert plain.battle_icon_value("wild").sum == base + (
        c.MatchModWildcard * base - base
    )
    assert fleet.battle_icon_value("desert_mouse").sum == matched
    assert fleet.battle_icon_value("wild").sum == matched
    assert fleet.battle_icon_value("").sum == base


def test_clandestine_forced_recall_term(monkeypatch: pytest.MonkeyPatch) -> None:
    p = make(leader(bl_state(), "gaius_helen_mohiam"))
    stub(p, monkeypatch, card_draw_value_with_buy_gains=1.0)
    stub_summer(p, monkeypatch, "spy_value", 1.5)
    assert p.clandestine_recall_value() == -0.5
    stub(p, monkeypatch, card_draw_value_with_buy_gains=2.0)
    assert p.clandestine_recall_value() == 0.0


# =================================================================================
# Gating: games without Bloodlines read nothing new
# =================================================================================


def test_base_game_reads_are_unchanged() -> None:
    p = make(base_state())
    signet = catalog.card_entity("player:0:starter:signet_ring:0")
    assert p.icon_list(signet) == signet.list_attr("IconList")
    assert p.reveal_preview_bonus() == 0
    assert not p.counts_conflict_agent()
    assert not p.suspensor_suits_active()
    assert p.tech_face_up_tiles() == []
    assert p.ctx.tech_face_up_ids == ()
    assert p.ctx.commander_space_ids == ()


def test_private_bloodlines_reads_are_the_owners_only() -> None:
    state = _yrkoon(navigation_slots=("navigation_card_2",))
    other = (seat_of(state) + 1) % 4
    q = _t.make_profile(state, other)
    assert q.ctx.navigation_slots == ()
    assert make(state).ctx.navigation_slots == ("navigation_card_2",)
