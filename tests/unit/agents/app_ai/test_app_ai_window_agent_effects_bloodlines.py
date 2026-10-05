"""The ``agent_effects`` window on Bloodlines and the Tech Module.

Each test reaches a real Agent turn of a Bloodlines game (the first turn of
the seat whose leader matters, the seat's hand and board pieces adjusted,
then a real ``agent_turn``), builds the ``DecisionRun`` the agent would build
and asserts the source the window builds for the app-style ability or the
exact action it answers (docs/app-ai/bloodlines-cards.md §8,
bloodlines-systems.md §2.3, §3.4, §4, §6). Profile values or ability answers
a branch depends on are pinned (``monkeypatch``); ``intrigue_play_sources``
(another window's) is stubbed.
"""

import random
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import bloodlines_cards as bc
from dune_imperium.agents.app_ai.abilities import bloodlines_systems as bs
from dune_imperium.agents.app_ai.abilities.base import Answer, Request
from dune_imperium.agents.app_ai.abilities.generic import DeployUnitsAbility
from dune_imperium.agents.app_ai.abilities.tech import AcquireTechAbility
from dune_imperium.agents.app_ai.agent import AppAIAgent
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import agent_effects as ae
from dune_imperium.agents.app_ai.windows.common import Source, Stage
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.agents.heuristic_agent import HeuristicAgent
from dune_imperium.content.uprising.leaders import leaders_for_choam
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.engine import UprisingRulesEngine

BL = RulesetConfig(choam_module=True, bloodlines=True, tech_module=True)
BL_PROMO = RulesetConfig(
    choam_module=True, bloodlines=True, tech_module=True, promo_cards=True
)
IMM = RulesetConfig(choam_module=False, immortality=True)
RICH = Resources(solari=8, spice=8, water=2)

type Patches = Mapping[str, object]


@pytest.fixture(autouse=True)
def no_plots(monkeypatch: pytest.MonkeyPatch) -> None:
    """``intrigue_play_sources`` belongs to the intrigue window: stub it."""

    monkeypatch.setattr(ae, "intrigue_play_sources", lambda run, plays, combat: [])


# ---------------------------------------------------------------------------
# Real states
# ---------------------------------------------------------------------------


def _settle(state: GameState) -> GameState:
    chance = ChanceResolver(seed=1)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    return state


def _apply(state: GameState, seat: int, action: DomainAction) -> GameState:
    legal = ENGINE.legal_actions(state, seat)
    return _settle(ENGINE.apply(state, action, legal_actions=legal).state)


def _game(config: RulesetConfig, leader: str | None) -> tuple[GameState, int]:
    """The first ``turn`` decision of the seat playing ``leader`` (any seat
    without one), heuristic seats advancing the game."""

    engine = ENGINE
    if leader is not None:
        pool = [
            lid.leader_id
            for lid in leaders_for_choam(True, bloodlines=True, tech_module=True)
            if lid.leader_id != leader
        ]
        engine = UprisingRulesEngine(leader_ids=(leader, *pool[:3]))
    state = _settle(engine.reset(config, 1))
    agents = [HeuristicAgent(seed=10 + seat) for seat in range(4)]
    for _ in range(5_000):
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = _settle(state)
            continue
        assert isinstance(decision, PlayerDecision)
        owner = decision.owner
        if state.decision_stack[-1].kind == "turn" and (
            leader is None or state.players[owner].leader_id == leader
        ):
            return state, owner
        legal = ENGINE.legal_actions(state, owner)
        action = agents[owner].choose_action(ENGINE.observe(state, owner), legal)
        state = ENGINE.apply(state, action, legal_actions=legal).state
    raise AssertionError("no turn reached")


def _take(state: GameState, seat: int, card: str) -> tuple[GameState, str]:
    """Move one copy of ``card`` into ``seat``'s hand and return its id."""

    me = state.players[seat]
    for zone in ("hand", "deck", "discard_pile"):
        for ref in getattr(me, zone):
            if f":{card}:" in ref:
                if zone == "hand":
                    return state, ref
                rest = tuple(r for r in getattr(me, zone) if r != ref)
                return with_player(
                    state, seat, **{zone: rest}, hand=(ref, *me.hand)
                ), ref
    for zone in ("imperium_deck", "imperium_row"):
        for ref in getattr(state, zone):
            if ref.startswith(f"imperium:{card}:"):
                rest = tuple(r for r in getattr(state, zone) if r != ref)
                state = with_state(state, **{zone: rest})
                hand = (ref, *state.players[seat].hand)
                return with_player(state, seat, hand=hand), ref
    raise KeyError(card)


def _place(
    config: RulesetConfig,
    card: str,
    *,
    space: str | None = None,
    leader: str | None = None,
    extra: Sequence[str] = (),
    adjust: Mapping[str, object] | None = None,
    **before: object,
) -> tuple[GameState, int, str]:
    """The leader's (or the first) seat plays ``card`` to ``space``;
    ``before`` adjusts the seat, ``adjust`` the state, first."""

    state, seat = _game(config, leader)
    for other in extra:
        state, _ = _take(state, seat, other)
    state, ref = _take(state, seat, card)
    if adjust:
        state = with_state(state, **adjust)
    if before:
        state = _with_units(state, seat, **before)
    legal = ENGINE.legal_actions(state, seat)
    placements = [
        action
        for action in legal
        if action.action_id == "agent_turn"
        and arg(action, "card_id") == ref
        and (space is None or arg(action, "space_id") == space)
        and arg(action, "infiltrate_post_id") is None
        and arg(action, "graft") is not True
    ]
    assert placements, f"{card} cannot go to {space}"
    state = _apply(state, seat, placements[0])
    assert state.decision_stack[-1].kind == "agent_effects"
    return state, seat, ref


def _with_units(state: GameState, seat: int, **changes: object) -> GameState:
    """``with_player`` keeping the 12 troops accounted for (the supply takes
    the difference) and the agent count (an Agent in the Conflict leaves the
    Leader)."""

    me = state.players[seat]
    merged: dict[str, object] = dict(changes)

    def get(name: str) -> int:
        value = merged.get(name, getattr(me, name))
        assert isinstance(value, int)
        return value

    if "troops_garrison" in changes or "troops_conflict" in changes:
        placed = get("troops_garrison") + get("troops_conflict") + get("memories")
        placed += get("specimens") + get("troops_parked")
        merged["troops_supply"] = 12 - placed
    if "agent_in_conflict" in changes:
        active = 3 if me.swordmaster_acquired else 2
        merged["agents_available"] = (
            active - len(me.agent_locations) - get("agent_in_conflict")
        )
    return with_player(state, seat, **merged)


def _give_skill(state: GameState, seat: int) -> tuple[GameState, str]:
    """Hand ``seat`` the first Skill tile of the stack."""

    skill = state.skill_stack[0]
    state = with_state(state, skill_stack=state.skill_stack[1:])
    return with_player(state, seat, skill_ids=(skill,)), skill


def _give_tech(state: GameState, seat: int, tech_id: str) -> GameState:
    """Move ``tech_id`` from its stack to ``seat``."""

    stacks = tuple(
        tuple(t for t in stack if t != tech_id) for stack in state.tech_stacks
    )
    me = state.players[seat]
    state = with_state(state, tech_stacks=stacks)
    return with_player(state, seat, tech_ids=(*me.tech_ids, tech_id))


def _run(
    state: GameState,
    seat: int,
    patches: Patches | None = None,
    memory: Memory | None = None,
) -> DecisionRun:
    profile = make_profile(state, seat)
    for name, value in (patches or {}).items():
        setattr(profile, name, value)
    legal = ENGINE.legal_actions(state, seat)
    return DecisionRun(
        profile.ctx, profile, legal, random.Random(0), memory or Memory()
    )


def _turn(
    state: GameState,
    seat: int,
    patches: Patches | None = None,
    memory: Memory | None = None,
) -> ae._Turn:
    t = ae._turn(_run(state, seat, patches, memory))
    ae._collect(t)
    return t


def _source(t: ae._Turn, label: str) -> Source:
    found = [s for s in t.sources if s.label == label]
    assert found, (label, [s.label for s in t.sources], t.unmapped)
    return found[0]


def _evaluate(source: Source) -> tuple[float, DomainAction | None]:
    assert source.evaluate is not None
    return source.evaluate()


def _a(seat: int, action_id: str, **arguments: str | int) -> DomainAction:
    return DomainAction(
        action_id=action_id, actor=seat, arguments=tuple(sorted(arguments.items()))
    )


def _answer(
    state: GameState,
    seat: int,
    patches: Patches | None = None,
    memory: Memory | None = None,
) -> DomainAction | None:
    return ae.agent_effects_window(_run(state, seat, patches, memory))


def _ids(state: GameState, seat: int) -> set[str]:
    return {a.action_id for a in ENGINE.legal_actions(state, seat)}


def _first(state: GameState, seat: int, action_id: str) -> DomainAction:
    for action in ENGINE.legal_actions(state, seat):
        if action.action_id == action_id:
            return action
    raise AssertionError(action_id)


def _fixed(value: float) -> object:
    return lambda *_args, **_kwargs: value


# ---------------------------------------------------------------------------
# Sardaukar Commanders (bloodlines-systems.md §2.2-2.3)
# ---------------------------------------------------------------------------


def _commander_space(**before: Any) -> tuple[GameState, int]:
    state, seat, _ref = _place(
        BL, "imperial_throneship", space="dutiful_service", resources=RICH, **before
    )
    assert "acquire_sardaukar_commander" in _ids(state, seat)
    return state, seat


def test_commander_acquire_takes_the_best_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _commander_space()
    skills = [
        str(arg(a, "skill_id"))
        for a in ENGINE.legal_actions(state, seat)
        if a.action_id == "acquire_sardaukar_commander"
    ]
    best = skills[1]
    nets = {best: 5.0}
    monkeypatch.setattr(
        Profile,
        "commander_acquire_net",
        lambda self, skill, with_entities=(): nets.get(skill or "", 1.0),
    )
    t = _turn(state, seat)
    source = _source(t, "Sardaukar Commander")
    assert source.stage is Stage.PROMPT and source.extra["explicit"] is True
    assert _evaluate(source) == (
        5.0,
        _a(seat, "acquire_sardaukar_commander", skill_id=best),
    )


def test_commander_acquire_declines_at_half_when_nothing_pays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _commander_space()
    monkeypatch.setattr(
        Profile, "commander_acquire_net", lambda self, skill, with_entities=(): -1.0
    )
    t = _turn(state, seat)
    assert _evaluate(_source(t, "Sardaukar Commander")) == (
        0.5,
        _a(seat, "decline_sardaukar_commander"),
    )


def test_commander_acquire_without_a_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat = _commander_space()
    # Every face-up Skill gone: the Commander comes without one (OQ-031).
    state = with_state(
        state,
        skill_face_up=(),
        skill_trash=(*state.skill_trash, *state.skill_face_up),
    )
    assert _first(state, seat, "acquire_sardaukar_commander").arguments == ()
    monkeypatch.setattr(
        Profile, "commander_acquire_net", lambda self, skill, with_entities=(): 3.0
    )
    t = _turn(state, seat)
    assert _evaluate(_source(t, "Sardaukar Commander")) == (
        3.0,
        _a(seat, "acquire_sardaukar_commander"),
    )


def test_unaffordable_commander_refusal_is_a_chore() -> None:
    state, seat = _commander_space()
    state = with_player(state, seat, resources=Resources(solari=0, spice=8, water=2))
    assert _ids(state, seat) >= {"decline_sardaukar_commander"}
    assert "acquire_sardaukar_commander" not in _ids(state, seat)
    t = _turn(state, seat)
    assert _a(seat, "decline_sardaukar_commander") in t.chores
    assert not [s for s in t.sources if s.label == "Sardaukar Commander"]


def test_recruit_commander_is_an_optional_key(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat = _commander_space(commanders_supply=2)
    assert "recruit_sardaukar_commander" in _ids(state, seat)
    monkeypatch.setattr(
        bs.RecruitCommanderAbility,
        "evaluate",
        lambda self, p, r: Answer(2.5, (), "recruit"),
    )
    t = _turn(state, seat)
    source = _source(t, "Recruit Commander")
    assert source.extra["explicit"] is False
    assert _evaluate(source) == (2.5, _a(seat, "recruit_sardaukar_commander"))
    monkeypatch.setattr(
        bs.RecruitCommanderAbility, "evaluate", lambda self, p, r: Answer(0.0, None)
    )
    assert _evaluate(_source(_turn(state, seat), "Recruit Commander"))[1] is None


# ---------------------------------------------------------------------------
# Deployment with Commanders (§1.3, D1, D6, D61)
# ---------------------------------------------------------------------------


def _combat_space(**before: Any) -> tuple[GameState, int]:
    state, seat, _ref = _place(
        BL, "reconnaissance", space="arrakeen", resources=RICH, **before
    )
    return state, seat


def test_deploy_splits_commanders_first_with_a_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _combat_space(troops_garrison=3, commanders_garrison=1)
    state, _skill = _give_skill(state, seat)
    assert {"deploy_troops", "deploy_commanders"} <= _ids(state, seat)
    monkeypatch.setattr(Profile, "units_to_deploy", lambda self, units, maximum: 2)
    memory = Memory()
    t = _turn(state, seat, memory=memory)
    source = _source(t, "Deploy Units")
    value, action = _evaluate(source)
    assert value == 0.5 and action == _a(seat, "deploy_commanders", count=1)
    key = (ae.DEPLOY_SPLIT_INTENT, state.round_number, seat, t.card_ref)
    assert t.on_choose[action] == [(key, ("deploy_troops", 1))]

    # The window stores the rest; the next decision deploys it at once.
    chosen = ae.agent_effects_window(_run(state, seat, memory=memory))
    while chosen is not None and chosen.action_id not in (
        "deploy_troops",
        "deploy_commanders",
    ):
        state = _apply(state, seat, chosen)
        chosen = ae.agent_effects_window(_run(state, seat, memory=memory))
    assert chosen == _a(seat, "deploy_commanders", count=1)
    state = _apply(state, seat, chosen)
    rest = ae.agent_effects_window(_run(state, seat, memory=memory))
    assert rest == _a(seat, "deploy_troops", count=1)
    assert key not in memory.intents


def test_deploy_troops_first_without_a_skill(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat = _combat_space(troops_garrison=1, commanders_garrison=1)
    monkeypatch.setattr(Profile, "units_to_deploy", lambda self, units, maximum: 2)
    t = _turn(state, seat)
    value, action = _evaluate(_source(t, "Deploy Units"))
    assert action == _a(seat, "deploy_troops", count=1)
    key = (ae.DEPLOY_SPLIT_INTENT, state.round_number, seat, t.card_ref)
    assert t.on_choose[action] == [(key, ("deploy_commanders", 1))]


def test_deploy_room_reads_the_shared_garrison_extra() -> None:
    state, seat = _combat_space(troops_garrison=3, commanders_garrison=2)
    t = ae._turn(_run(state, seat))
    # Arrakeen: no recruit yet, a shared garrison extra of 2 units.
    assert ae._deploy_room(t, 2, 2) == 2


def test_off_combat_space_deploy_is_a_deploy_units_custom_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Elite Forces trashing an Emperor card grants a Combat icon off a Combat
    # space (bloodlines-cards.md §3.10; D61).
    state, seat, _ref = _place(
        BL,
        "elite_forces",
        space="dutiful_service",
        extra=("command_center",),
        resources=RICH,
        troops_garrison=2,
    )
    trash = [
        a
        for a in ENGINE.legal_actions(state, seat)
        if a.action_id == "trash_agent_card"
        and "command_center" in str(arg(a, "card_id"))
    ]
    state = _apply(state, seat, trash[0])
    assert "deploy_troops" in _ids(state, seat)
    monkeypatch.setattr(Profile, "units_to_deploy", lambda self, units, maximum: 1)
    t = _turn(state, seat)
    assert _evaluate(_source(t, "Deploy Units")) == (
        0.5,
        _a(seat, "deploy_troops", count=1),
    )
    icons = [s for s in t.sources if s.label.startswith("elite_forces ")]
    assert icons and all(s.stage is Stage.COST_FIRST for s in icons)


def test_no_second_deployment_without_a_stored_rest() -> None:
    state, seat = _combat_space(troops_garrison=3)
    state = _apply(state, seat, _a(seat, "deploy_troops", count=1))
    assert "deploy_troops" in _ids(state, seat)
    t = _turn(state, seat)
    assert not [s for s in t.sources if s.label.startswith("Deploy Units")]


# ---------------------------------------------------------------------------
# The Tech Module (bloodlines-systems.md §3.1, §3.3-3.4)
# ---------------------------------------------------------------------------


def _landsraad(**before: Any) -> tuple[GameState, int]:
    state, seat, _ref = _place(
        BL, "imperial_throneship", space="assembly_hall", **before
    )
    return state, seat


def test_landsraad_acquire_tech_buys_the_answered_tile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _landsraad(resources=RICH)
    tiles = [
        str(arg(a, "tech_id"))
        for a in ENGINE.legal_actions(state, seat)
        if a.action_id == "acquire_tech"
    ]
    assert tiles
    monkeypatch.setattr(
        AcquireTechAbility,
        "evaluate",
        lambda self, p, r: Answer(4.0, ((r.infos[0].entities[-1].ref,),)),
    )
    t = _turn(state, seat)
    source = _source(t, "Acquire Tech")
    assert source.extra["explicit"] is True
    value, action = _evaluate(source)
    assert value == 4.0 and action is not None
    assert action.action_id == "acquire_tech" and arg(action, "tech_id") == tiles[-1]


def test_landsraad_acquire_tech_empty_answer_declines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _landsraad(resources=RICH)
    monkeypatch.setattr(
        AcquireTechAbility, "evaluate", lambda self, p, r: Answer(0.5, ())
    )
    assert _evaluate(_source(_turn(state, seat), "Acquire Tech")) == (
        0.5,
        _a(seat, "decline_tech"),
    )


def test_unaffordable_tech_refusal_is_a_chore() -> None:
    state, seat = _landsraad(resources=Resources(solari=8, spice=0, water=2))
    assert "acquire_tech" not in _ids(state, seat)
    t = _turn(state, seat)
    assert _a(seat, "decline_tech") in t.chores


def test_advanced_data_analysis_boxes_the_worst_spy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _landsraad(resources=RICH)
    ada = "advanced_data_analysis"
    stacks = tuple(
        (ada, *(t for t in s if t != ada))
        if i == 0
        else tuple(t for t in s if t != ada)
        for i, s in enumerate(state.tech_stacks)
    )
    posts = ("arrakis-imperial-basin", "arrakis-hagga-basin")
    state = with_state(state, tech_stacks=stacks)
    state = with_player(state, seat, spy_post_ids=posts, spies_supply=1)
    variants = [
        a
        for a in ENGINE.legal_actions(state, seat)
        if a.action_id == "acquire_tech"
        and arg(a, "tech_id") == "advanced_data_analysis"
    ]
    assert len(variants) == 2
    monkeypatch.setattr(
        AcquireTechAbility,
        "evaluate",
        lambda self, p, r: Answer(3.0, (("advanced_data_analysis",),)),
    )
    monkeypatch.setattr(
        Profile,
        "recall_spy",
        lambda self, spies: (next(s for s in spies if s.ref == posts[1]), 1.0),
    )
    _value, action = _evaluate(_source(_turn(state, seat), "Acquire Tech"))
    assert action is not None and arg(action, "post_id") == posts[1]


def _owed(state: GameState, seat: int, keys: str) -> GameState:
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context["pending_tech_acquire_effects"] = keys
    return replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),
        ),
    )


def test_tech_acquire_effects_resolve_first_in_key_order() -> None:
    state, seat = _landsraad(resources=RICH)
    state = _owed(state, seat, "ornithopter_fleet:troops,ornithopter_fleet:troops")
    t = _turn(state, seat)
    source = _source(t, "tech ornithopter_fleet troops")
    assert source.stage is Stage.COST_FIRST and source.order == -3
    chosen = ae.agent_effects_window(_run(state, seat))
    assert chosen == _a(
        seat,
        "resolve_tech_acquire_effect",
        effect="troops",
        tech_id="ornithopter_fleet",
    )


def test_tech_influence_key_takes_memocorders_track(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dune_imperium.agents.app_ai.abilities.tech import MemocordersAcquiredAbility

    state, seat = _landsraad(resources=RICH)
    state = _owed(state, seat, "glowglobes:influence")
    monkeypatch.setattr(
        MemocordersAcquiredAbility,
        "evaluate",
        lambda self, p, r: Answer(101.0, (("fremen",),)),
    )
    t = _turn(state, seat)
    source = _source(t, "tech glowglobes influence")
    assert source.actions == (
        _a(
            seat,
            "resolve_tech_acquire_effect",
            effect="influence",
            faction="fremen",
            tech_id="glowglobes",
        ),
    )


def test_gene_locked_vault_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat = _landsraad(resources=RICH)
    state = _owed(state, seat, "gene_locked_vault:intrigue_or_card")
    monkeypatch.setattr(
        bs.GeneLockedVaultAcquiredAbility,
        "evaluate",
        lambda self, p, r: Answer(2.0, ((1,),)),
    )
    t = _turn(state, seat)
    assert _source(t, "tech gene_locked_vault intrigue_or_card").actions == (
        _a(
            seat,
            "resolve_tech_acquire_effect",
            choice="card",
            effect="intrigue_or_card",
            tech_id="gene_locked_vault",
        ),
    )


@pytest.mark.parametrize("blow", [True, False])
def test_forbidden_weapons_wall_follows_should_blow_wall(
    monkeypatch: pytest.MonkeyPatch, blow: bool
) -> None:
    state, seat = _landsraad(resources=RICH)
    state = with_state(
        _owed(state, seat, "forbidden_weapons:shield_wall"), shield_wall_present=True
    )
    monkeypatch.setattr(Profile, "should_blow_wall", lambda self: blow)
    (action,) = _source(
        _turn(state, seat), "tech forbidden_weapons shield_wall"
    ).actions
    assert (arg(action, "destroy_shield_wall") is True) is blow


def test_flip_tech_is_an_optional_key(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat = _landsraad(resources=RICH)
    state = _give_tech(state, seat, "spy_drones")
    assert "flip_tech" in _ids(state, seat)
    t = _turn(state, seat)
    source = _source(t, "flip spy_drones")
    assert source.extra["explicit"] is False
    assert _evaluate(source) == (100.0, _a(seat, "flip_tech", tech_id="spy_drones"))


# ---------------------------------------------------------------------------
# Bloodlines Agent boxes (bloodlines-cards.md §3, §8)
# ---------------------------------------------------------------------------


def test_holy_war_box_runs_immediately() -> None:
    state, seat, _ref = _place(BL, "holy_war", resources=RICH)
    source = _source(_turn(state, seat), "holy_war box")
    assert source.stage is Stage.IMMEDIATE


def test_imperial_throneship_draws_its_intrigue_immediately() -> None:
    state, seat, _ref = _place(BL, "imperial_throneship", resources=RICH)
    assert _source(_turn(state, seat), "imperial_throneship box").stage is (
        Stage.IMMEDIATE
    )


def test_ixian_ambassador_is_the_generic_box() -> None:
    state, seat, _ref = _place(BL, "ixian_ambassador", resources=RICH)
    assert _source(_turn(state, seat), "ixian_ambassador box").stage is (
        Stage.AGENT_BOX
    )


def test_urgent_shigawire_runs_immediately() -> None:
    state, seat, _ref = _place(BL, "urgent_shigawire", resources=RICH)
    assert _source(_turn(state, seat), "urgent_shigawire box").stage is (
        Stage.IMMEDIATE
    )


def test_command_center_box_with_emperor_two() -> None:
    state, seat, _ref = _place(
        BL, "command_center", resources=RICH, influence=Influence(emperor=2)
    )
    assert "resolve_agent_card_effect" in _ids(state, seat)
    assert _source(_turn(state, seat), "command_center box").stage is (Stage.IMMEDIATE)


def test_southern_faith_without_bond_is_its_draw_key() -> None:
    state, seat, _ref = _place(BL, "southern_faith", resources=RICH)
    assert "choose_agent_card_influence" not in _ids(state, seat)
    source = _source(_turn(state, seat), "southern_faith box")
    assert source.stage is Stage.PROMPT and source.extra["explicit"] is True
    _value, action = _evaluate(source)
    assert action == _a(seat, "resolve_agent_card_effect")


@pytest.mark.parametrize(
    ("option", "expected"),
    [(0, "resolve_agent_card_effect"), (1, "choose_agent_card_influence")],
)
def test_southern_faith_bond_choice(
    monkeypatch: pytest.MonkeyPatch, option: int, expected: str
) -> None:
    state, seat, _ref = _place(BL, "southern_faith", resources=RICH)
    me = state.players[seat]
    state, other = _take(state, seat, "urgent_shigawire")
    me = state.players[seat]
    state = with_player(
        state,
        seat,
        hand=tuple(r for r in me.hand if r != other),
        in_play=(*me.in_play, other),
    )
    assert "choose_agent_card_influence" in _ids(state, seat)
    monkeypatch.setattr(
        bc.SouthernFaithAgentAbility,
        "evaluate",
        lambda self, p, r: Answer(3.0, ((option,),)),
    )
    t = _turn(state, seat)
    assert not [s for s in t.sources if s.label == "southern_faith box"]
    _value, action = _evaluate(_source(t, "southern_faith choice"))
    assert action is not None and action.action_id == expected


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (((0,), ("spacing_guild",)), ("choose_agent_card_influence", "spacing_guild")),
        (((1,),), ("resolve_agent_card_effect", None)),
    ],
)
def test_possible_futures_choice(
    monkeypatch: pytest.MonkeyPatch,
    response: tuple[tuple[str | int, ...], ...],
    expected: tuple[str, str | None],
) -> None:
    state, seat, _ref = _place(BL, "possible_futures", resources=RICH)
    monkeypatch.setattr(
        bc.PossibleFuturesAgentAbility,
        "evaluate",
        lambda self, p, r: Answer(3.0, response),
    )
    _value, action = _evaluate(_source(_turn(state, seat), "possible_futures choice"))
    assert action is not None
    assert (action.action_id, arg(action, "faction")) == expected


def test_fremen_war_name_icons_once_two_spice_gained() -> None:
    state, seat, _ref = _place(
        BL,
        "fremen_war_name",
        space="hagga_basin",
        resources=RICH,
        spice_at_turn_start=RICH.spice,
    )
    assert "resolve_agent_card_effect" not in _ids(state, seat)  # the icons wait
    state = _apply(state, seat, _first(state, seat, "harvest_maker_spice"))
    labels = {s.label: s for s in _turn(state, seat).sources}
    assert labels["fremen_war_name troops"].stage is Stage.IMMEDIATE
    assert "fremen_war_name cards" in labels


def test_a_gated_icon_whose_cost_fails_is_a_chore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat, _ref = _place(
        BL,
        "fremen_war_name",
        space="hagga_basin",
        resources=RICH,
        spice_at_turn_start=RICH.spice,
    )
    state = _apply(state, seat, _first(state, seat, "harvest_maker_spice"))
    monkeypatch.setattr(
        bc.FremenWarNameTroopAbility, "meets_cost", lambda self, p: False
    )
    t = _turn(state, seat)
    assert _a(seat, "resolve_agent_card_effect", effect="troops") in t.chores
    assert not [s for s in t.sources if s.label == "fremen_war_name troops"]


def test_ruthless_leadership_trash_and_empty_pick_declines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat, _ref = _place(
        BL_PROMO, "ruthless_leadership", resources=RICH, commanders_conflict=1
    )
    monkeypatch.setattr(
        bc.RuthlessLeadershipTrashAbility,
        "evaluate",
        lambda self, p, r: Answer(1.0, ((),)),
    )
    t = _turn(state, seat)
    assert _evaluate(_source(t, "ruthless_leadership trash")) == (
        1.0,
        _a(seat, "decline_agent_card_trash"),
    )


def test_eliminate_allies_trash_uses_the_generic_trash_agent_ability() -> None:
    state, seat, _ref = _place(
        BL,
        "eliminate_allies",
        resources=RICH,
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
        spies_supply=2,
    )
    state = _apply(state, seat, _first(state, seat, "decline_gather_intelligence"))
    t = _turn(state, seat)
    source = _source(t, "eliminate_allies trash")
    assert source.extra["explicit"] is True
    _value, action = _evaluate(source)
    assert action is not None and action.action_id in (
        "trash_agent_card",
        "decline_agent_card_trash",
    )


def test_elite_forces_trash_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat, _ref = _place(
        BL, "elite_forces", extra=("command_center",), resources=RICH
    )
    monkeypatch.setattr(
        bc.EliteForcesAgentAbility,
        "evaluate",
        lambda self, p, r: Answer(0.0, None),
    )
    t = _turn(state, seat)
    assert _evaluate(_source(t, "elite_forces trash")) == (0.0, None)
    assert _a(seat, "decline_agent_card_trash") in t.declines


def test_arrakis_observer_discard_then_spy_follow_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat, _ref = _place(BL, "arrakis_observer", space="arrakeen", resources=RICH)
    hand = state.players[seat].hand
    monkeypatch.setattr(
        bc.ArrakisObserverAgentAbility,
        "evaluate",
        lambda self, p, r: Answer(2.0, ((hand[0],),)),
    )
    t = _turn(state, seat)
    _value, action = _evaluate(_source(t, "arrakis_observer discard"))
    assert action == _a(seat, "discard_agent_card", card_id=hand[0])
    assert _a(seat, "decline_agent_card_discard") in t.declines
    state = _apply(state, seat, action)
    assert "place_agent_card_spy" in _ids(state, seat)
    follow = _source(_turn(state, seat), "Arrakis Observer spy")
    assert follow.stage is Stage.COST_FIRST
    assert follow.actions[0].action_id == "place_agent_card_spy"


@pytest.mark.parametrize("card", ["engineered_miracle", "i_believe"])
def test_discard_for_reward_boxes(card: str) -> None:
    state, seat, _ref = _place(BL, card, resources=RICH)
    t = _turn(state, seat)
    _source(t, f"{card} discard")
    assert _a(seat, "decline_agent_card_discard") in t.declines


def test_choam_demands_completes_the_answered_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, _seat = _game(BL, None)
    contracts = state.face_up_contract_ids[:2]
    state, seat, _ref = _place(
        BL,
        "choam_demands",
        resources=RICH,
        active_contract_ids=contracts,
        adjust={"face_up_contract_ids": state.face_up_contract_ids[2:]},
    )
    assert "complete_contract_by_card" in _ids(state, seat)
    monkeypatch.setattr(
        bc.CHOAMDemandsAgentAbility,
        "evaluate",
        lambda self, p, r: Answer(3.0, ((r.infos[0].entities[1].ref,),)),
    )
    source = _source(_turn(state, seat), "CHOAM Demands")
    assert source.extra["explicit"] is True
    _value, action = _evaluate(source)
    assert action is not None and action.action_id == "complete_contract_by_card"
    assert arg(action, "instance_id") == contracts[1]


def test_disruption_tactics_maps_the_victim_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat, _ref = _place(BL, "disruption_tactics", resources=RICH)
    victim = (seat + 1) % 4
    state = _with_units(state, victim, troops_conflict=1, commanders_conflict=1)
    actions = [
        a
        for a in ENGINE.legal_actions(state, seat)
        if a.action_id == "retreat_opponent_troop"
    ]
    assert len(actions) == 2
    code = bc.retreat_target_code(victim, True)
    seen: list[tuple[int, ...]] = []

    def evaluate(self: object, p: Profile, r: Request) -> Answer:
        seen.append(r.infos[0].options)
        return Answer(1.0, ((code,),))

    monkeypatch.setattr(bc.DisruptionTacticsAgentAbility, "evaluate", evaluate)
    _value, action = _evaluate(_source(_turn(state, seat), "Disruption Tactics"))
    assert seen == [(bc.retreat_target_code(victim, False), code)]
    assert action == _a(seat, "retreat_opponent_troop", commanders=1, player=victim)


# ---------------------------------------------------------------------------
# Bloodlines leaders (bloodlines-systems.md §4)
# ---------------------------------------------------------------------------


def _signet(
    leader: str, space: str | None = None, **before: Any
) -> tuple[GameState, int]:
    state, seat, _ref = _place(BL, "signet_ring", space=space, leader=leader, **before)
    return state, seat


@pytest.mark.parametrize(
    ("leader", "label"),
    [("piter_de_vries", "signet piter_de_vries"), ("liet_kynes", "signet liet_kynes")],
)
def test_automatic_signet_boxes(leader: str, label: str) -> None:
    state, seat = _signet(leader, resources=RICH)
    assert _source(_turn(state, seat), label).stage is Stage.IMMEDIATE


def test_fedaykin_retreat_troops_first(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat = _signet(
        "chani",
        resources=RICH,
        troops_conflict=1,
        commanders_conflict=1,
        influence=Influence(fremen=2),
    )
    monkeypatch.setattr(
        bs.FedaykinManeuverSignetAbility,
        "evaluate",
        lambda self, p, r: Answer(2.0, ((0,), (2,))),
    )
    t = _turn(state, seat)
    _value, action = _evaluate(_source(t, "Fedaykin Maneuver"))
    assert action == _a(seat, "retreat_leader_troops", commanders=1, count=2)
    assert _a(seat, "decline_leader_signet_payment") in t.declines
    monkeypatch.setattr(
        bs.FedaykinManeuverSignetAbility,
        "evaluate",
        lambda self, p, r: Answer(2.0, ((1,),)),
    )
    _value, action = _evaluate(_source(_turn(state, seat), "Fedaykin Maneuver"))
    assert action == _a(seat, "pay_leader_signet_water")


def test_corrino_liaison_trash_or_spy(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat = _signet("count_hasimir_fenring", resources=RICH)
    trash = _first(state, seat, "trash_leader_card")
    monkeypatch.setattr(
        bs.CorrinoLiaisonSignetAbility,
        "evaluate",
        lambda self, p, r: Answer(2.0, ((0,), (r.infos[1].entities[0].ref,))),
    )
    _value, action = _evaluate(_source(_turn(state, seat), "Corrino Liaison"))
    assert action == trash
    monkeypatch.setattr(
        bs.CorrinoLiaisonSignetAbility,
        "evaluate",
        lambda self, p, r: Answer(2.0, ((1,),)),
    )
    _value, action = _evaluate(_source(_turn(state, seat), "Corrino Liaison"))
    assert action is not None and action.action_id == "place_leader_spy"


def test_into_the_fray(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat = _signet("duncan_idaho", resources=RICH)
    monkeypatch.setattr(Profile, "units_to_deploy", lambda self, units, maximum: 1)
    t = _turn(state, seat)
    assert _evaluate(_source(t, "Into the Fray")) == (
        0.5,
        _a(seat, "deploy_leader_agent"),
    )
    assert _a(seat, "decline_leader_signet_payment") in t.declines


def test_smuggle_spice_and_tueks_sietch(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat = _signet("esmar_tuek", space="tuek_sietch", resources=RICH)
    t = _turn(state, seat)
    smuggle = _source(t, "Smuggle Spice")
    assert smuggle.extra["explicit"] is True
    monkeypatch.setattr(
        bs.SmuggleSpiceSignetAbility,
        "evaluate",
        lambda self, p, r: Answer(2.0, ((0,),)),
    )
    assert _evaluate(_source(_turn(state, seat), "Smuggle Spice")) == (
        2.0,
        _a(seat, "place_leader_bonus_spice"),
    )
    monkeypatch.setattr(
        bs.TueksSietchDeferredAbility,
        "evaluate",
        lambda self, p, r: Answer(3.0, ((1,),)),
    )
    sietch = _source(_turn(state, seat), "Tuek's Sietch")
    assert sietch.extra["explicit"] is True
    assert _evaluate(sietch) == (3.0, _a(seat, "take_tuek_sietch_card"))


def test_smuggle_spice_takes_from_a_maker_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _signet("esmar_tuek", space="tuek_sietch", resources=RICH)
    bonus = tuple(
        (space, 2 if space == "hagga_basin" else amount)
        for space, amount in state.maker_bonus_spice
    )
    state = with_state(state, maker_bonus_spice=bonus)
    seen: list[tuple[str, ...]] = []

    def evaluate(self: object, p: Profile, r: Request) -> Answer:
        seen.append(tuple(e.ref for e in r.infos[1].entities))
        return Answer(2.0, ((1,), ("hagga_basin",)))

    monkeypatch.setattr(bs.SmuggleSpiceSignetAbility, "evaluate", evaluate)
    _value, action = _evaluate(_source(_turn(state, seat), "Smuggle Spice"))
    assert action == _a(seat, "take_leader_bonus_spice", space_id="hagga_basin")
    assert "hagga_basin" in seen[0]


def test_listeners_landsraad_pay_and_follow_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _signet("gaius_helen_mohiam", resources=RICH)
    monkeypatch.setattr(
        bs.ListenersSignetAbility,
        "evaluate",
        lambda self, p, r: Answer(2.0, ((0,),)),
    )
    _value, action = _evaluate(_source(_turn(state, seat), "Listeners"))
    assert action is not None and action.action_id == "place_leader_spy"
    monkeypatch.setattr(
        bs.ListenersSignetAbility,
        "evaluate",
        lambda self, p, r: Answer(2.0, ((1,),)),
    )
    pay = _a(seat, "pay_leader_signet_spice")
    assert _evaluate(_source(_turn(state, seat), "Listeners")) == (2.0, pay)
    state = _apply(state, seat, pay)
    follow = _source(_turn(state, seat), "Listeners spy")
    assert follow.stage is Stage.COST_FIRST
    assert follow.actions[0].action_id == "place_leader_spy"


def test_reverse_engineering(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat = _signet("kota_odax_of_ix", resources=RICH)
    state = _give_tech(state, seat, "glowglobes")
    monkeypatch.setattr(
        bs.ReverseEngineeringSignetAbility,
        "evaluate",
        lambda self, p, r: Answer(4.0, ((1,), ("glowglobes",))),
    )
    source = _source(_turn(state, seat), "Reverse Engineering")
    assert source.extra["explicit"] is True
    assert _evaluate(source) == (
        4.0,
        _a(seat, "trash_leader_tech", tech_id="glowglobes"),
    )


# ---------------------------------------------------------------------------
# The Into the Fray Agent as a recall candidate (D55)
# ---------------------------------------------------------------------------


def test_steersman_recall_lists_the_conflict_agent_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat, _ref = _place(
        BL, "steersman", resources=RICH, leader="duncan_idaho", agent_in_conflict=1
    )
    seen: list[tuple[str, ...]] = []
    from dune_imperium.agents.app_ai.abilities.generic import RecallAgentAbility

    def evaluate(self: object, p: Profile, r: Request) -> Answer:
        seen.append(tuple(e.ref for e in r.infos[0].entities))
        return Answer(1.0, (("conflict",),))

    monkeypatch.setattr(RecallAgentAbility, "evaluate", evaluate)
    if "recall_conflict_agent_for_agent_card" not in _ids(state, seat):
        pytest.skip("the engine offers no Conflict Agent recall in this state")
    _value, action = _evaluate(_source(_turn(state, seat), "Steersman recall"))
    assert seen[0][-1] == "conflict"
    assert action == _a(seat, "recall_conflict_agent_for_agent_card")


def test_imperial_privilege_recalls_the_conflict_agent_without_falling_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression (Z1 verify): ``recall_conflict_agent_for_imperial_privilege``
    was handled by ``_imperial_privilege`` but missing from the known ids, so
    every such decision fell back (``unknown action``)."""

    state, seat, _ref = _place(
        BL,
        "imperial_throneship",
        space="imperial_privilege",
        leader="duncan_idaho",
        resources=RICH,
        agent_in_conflict=1,
        influence=Influence(emperor=2),
    )
    state = _apply(
        state, seat, _first(state, seat, "decline_imperial_privilege_intrigue")
    )
    assert "recall_conflict_agent_for_imperial_privilege" in _ids(state, seat)
    t = _turn(state, seat)
    assert t.unmapped == []
    assert _answer(state, seat) is not None
    from dune_imperium.agents.app_ai.abilities.generic import RecallAgentAbility

    seen: list[tuple[str, ...]] = []
    real = RecallAgentAbility.evaluate

    def evaluate(self: RecallAgentAbility, p: Profile, r: Request) -> Answer:
        seen.append(tuple(e.ref for e in r.infos[0].entities))
        return real(self, p, r)

    monkeypatch.setattr(RecallAgentAbility, "evaluate", evaluate)
    source = _source(_turn(state, seat), "Imperial Privilege recall")
    assert source.extra["explicit"] is True
    _value, action = _evaluate(source)
    # The only candidate: GetRecallAgent skips it, ``?? FirstOrDefault`` takes it.
    assert seen == [("conflict",)]
    assert action == _a(seat, "recall_conflict_agent_for_imperial_privilege")


@pytest.mark.parametrize("earlier_turn", [True, False])
def test_recall_contract_is_valued_with_the_conflict_agent(
    monkeypatch: pytest.MonkeyPatch, earlier_turn: bool
) -> None:
    """Regression (Z1 verify, D55): ``RecallAgentContractAbility``'s targets
    include an earlier turn's Into the Fray Agent, as the reward's recall
    will (``recall_conflict_agent_for_contract``); this turn's Agent moved
    there by Into the Fray is not one (OQ-068)."""

    from dune_imperium.agents.app_ai.abilities.board import (
        RecallAgentContractAbility,
    )

    state0, _seat0 = _game(BL, "duncan_idaho")
    pool = (
        *state0.contract_bank,
        *state0.face_up_contract_ids,
        *state0.sardaukar_contract_ids,
    )
    contract = next(c for c in pool if c.endswith("sardaukar_ii"))
    adjust = {
        name: tuple(c for c in getattr(state0, name) if c != contract)
        for name in ("contract_bank", "face_up_contract_ids", "sardaukar_contract_ids")
    }
    state, seat, _ref = _place(
        BL,
        "imperial_throneship",
        space="sardaukar",
        leader="duncan_idaho",
        resources=RICH,
        agent_in_conflict=1,
        influence=Influence(emperor=2),
        active_contract_ids=(contract,),
        adjust=adjust,
    )
    if not earlier_turn:
        # This turn's Agent went to the Conflict (Into the Fray): the one
        # Conflict Agent is the one sent this turn (the other Agent is home).
        me = state.players[seat]
        locations = tuple(s for s in me.agent_locations if s != "sardaukar")
        state = with_player(
            state,
            seat,
            agent_locations=locations,
            agents_available=me.agents_available + 1,
        )
    assert _a(seat, "complete_contract", instance_id=contract) in ENGINE.legal_actions(
        state, seat
    )
    seen: list[tuple[str, ...]] = []
    real = RecallAgentContractAbility.evaluate

    def evaluate(self: RecallAgentContractAbility, p: Profile, r: Request) -> Answer:
        seen.append(tuple(e.ref for e in r.infos[0].entities))
        return real(self, p, r)

    monkeypatch.setattr(RecallAgentContractAbility, "evaluate", evaluate)
    monkeypatch.setattr(Profile, "recall_agent_value", _fixed(2.0))
    value, action = _evaluate(_source(_turn(state, seat), f"contract {contract}"))
    assert action == _a(seat, "complete_contract", instance_id=contract)
    if earlier_turn:
        assert seen == [("conflict",)] and value == 3.0
    else:
        assert seen == [()] and value == 1.0


def test_mohiam_forced_gather_intelligence_recalls_get_recall_spy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression (Z1 verify, bloodlines-systems.md §4.5): Clandestine leaves
    no decline, so the app's "no" has no legal twin; the Spy recalled is
    ``GetRecallSpy``'s, not the first offered post."""

    from dune_imperium.agents.app_ai.abilities.board import (
        RecallSpyIntelligenceAbility,
    )

    posts = (
        "arrakis-research-station-spice-refinery",
        "arrakis-spice-refinery-arrakeen",
    )
    state, seat, _ref = _place(
        BL,
        "imperial_throneship",
        space="spice_refinery",
        leader="gaius_helen_mohiam",
        resources=RICH,
        spy_post_ids=posts,
        spies_supply=1,
    )
    gathers = [
        a
        for a in ENGINE.legal_actions(state, seat)
        if a.action_id == "gather_intelligence"
    ]
    assert len(gathers) == 2
    assert "decline_gather_intelligence" not in _ids(state, seat)
    monkeypatch.setattr(
        RecallSpyIntelligenceAbility,
        "evaluate",
        lambda self, p, r: Answer(1.0, ((0,),)),
    )
    worst = str(arg(gathers[1], "post_id"))
    monkeypatch.setattr(
        Profile,
        "recall_spy",
        lambda self, spies: (next(s for s in spies if s.ref == worst), 1.0),
    )
    assert _answer(state, seat) == gathers[1]


# ---------------------------------------------------------------------------
# Gating: Bloodlines ids outside a Bloodlines game
# ---------------------------------------------------------------------------


def test_bloodlines_ids_are_unknown_outside_bloodlines() -> None:
    state, seat, _ref = _place(IMM, "dagger")
    run = _run(state, seat)
    widened = DecisionRun(
        run.ctx,
        run.profile,
        (*run.legal, _a(seat, "recruit_sardaukar_commander")),
        run.rng,
        Memory(),
    )
    assert ae.agent_effects_window(widened) is None


def test_bloodlines_game_has_no_agent_effects_fallback() -> None:
    agents = [AppAIAgent(seed=7 + s) for s in range(4)]
    from dune_imperium.simulation.runner import run_policy_game

    leaders = (
        "esmar_tuek",
        "count_hasimir_fenring",
        "gaius_helen_mohiam",
        "kota_odax_of_ix",
    )
    run_policy_game(UprisingRulesEngine(leader_ids=leaders), BL_PROMO, 3, agents)
    assert sum(a.fallbacks.get("agent_effects", 0) for a in agents) == 0
    assert sum(a.mirrored.get("agent_effects", 0) for a in agents) > 0


def test_deploy_units_ability_is_the_deploy_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The space's ``DeployUnitsAbility`` answers, its targets the garrison
    troops and Commanders (D1) and ``NumberToSelect`` the joint room."""

    state, seat = _combat_space(troops_garrison=3, commanders_garrison=2)
    seen: list[tuple[str, int, int]] = []

    def evaluate(self: DeployUnitsAbility, p: Profile, r: Request) -> Answer:
        info = r.infos[0]
        seen.append((self.owner.ref, len(info.options), info.max_select))
        return Answer(0.5, ((0, 1),))

    monkeypatch.setattr(DeployUnitsAbility, "evaluate", evaluate)
    t = _turn(state, seat)
    source = _source(t, "Deploy Units")
    assert source.actions[0].action_id == "deploy_troops"
    _value, action = _evaluate(source)
    assert seen == [("arrakeen", 5, ae._deploy_room(t, 2, 2))]
    assert action == _a(seat, "deploy_troops", count=2)
