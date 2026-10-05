"""The app_ai combat windows with Immortality, Epic and the promos
(``windows/combat.py``).

Real heuristic games reach each window (``testing.play_until`` with the
option's ``RulesetConfig``); the fields that decide the answer are adjusted
and the handler is checked against the ported app ability.
"""

import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai import agent as agent_module
from dune_imperium.agents.app_ai.abilities.base import Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.epic_promo import (
    EconomicSupremacySolariAbility,
    EconomicSupremacySpiceAbility,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    DeferredAbility,
    GainAnyInfluenceConflictAbility,
)
from dune_imperium.agents.app_ai.catalog import conflict_entity, track_entity
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    make_profile,
    play_until,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import combat as W
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.content.uprising.leaders import leaders_for_choam
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.combat import rank_combat
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

IMMORTALITY = RulesetConfig(immortality=True)
EPIC = RulesetConfig(epic_game=True)
EPIC_PROMO = RulesetConfig(epic_game=True, promo_cards=True)
PROMO = RulesetConfig(promo_cards=True)


def _seat(state: GameState) -> int:
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _legal(state: GameState) -> tuple[DomainAction, ...]:
    return ENGINE.legal_actions(state, _seat(state))


def _run(
    state: GameState, *, legal: Sequence[DomainAction] | None = None
) -> DecisionRun:
    seat = _seat(state)
    profile = make_profile(state, seat)
    actions = tuple(_legal(state) if legal is None else legal)
    return DecisionRun(profile.ctx, profile, actions, profile.rng, Memory())


def _find(state: GameState, action_id: str, **args: object) -> DomainAction:
    for action in _legal(state):
        if action.action_id == action_id and all(
            dict(action.arguments).get(k) == v for k, v in args.items()
        ):
            return action
    raise AssertionError(f"{action_id} {args} is not legal")


def _apply(state: GameState, action: DomainAction) -> GameState:
    return ENGINE.apply(state, action, legal_actions=_legal(state)).state


@cache
def _combat(config: RulesetConfig, seed: int, conflict: str | None = None) -> GameState:
    """The first ``combat_intrigue`` prompt (of ``conflict`` when given)."""

    return play_until(
        lambda s, owner: (
            s.decision_stack[-1].kind == "combat_intrigue"
            and (conflict is None or s.current_conflict_ids[-1] == conflict)
        ),
        config=config,
        seed=seed,
    )


def _rewards(state: GameState, **winner: object) -> GameState:
    """Every combatant passes: the engine pays the rewards and stacks the
    reward frames. ``winner`` adjusts the sole leader first."""

    seat = rank_combat(state.players, first_player=state.first_player).winner
    assert seat is not None
    state = with_player(state, seat, **winner)
    while state.decision_stack[-1].kind == "combat_intrigue":
        state = ENGINE.apply(
            state, DomainAction("pass_combat_intrigue", _seat(state))
        ).state
    return state


def _pledged(state: GameState) -> GameState:
    """A Pivotal Gambit pledged this Conflict's 1st place (bonus + event)."""

    conflict = state.current_conflict_ids[-1]
    event = GameEvent(
        event_id=f"test:pledge:{conflict}",
        kind="first_place_influence_pledged",
        payload=(("conflict_id", conflict), ("player", 0)),
    )
    return with_state(
        state,
        conflict_first_place_influence_bonus=1,
        event_log=(*state.event_log, event),
    )


# ===========================================================================
# Economic Supremacy (Epic): the two charges
# ===========================================================================


def _economic_supremacy(*, solari: int, spice: int) -> GameState:
    state = _combat(EPIC, 1, "economic_supremacy")
    seat = rank_combat(state.players, first_player=state.first_player).winner
    assert seat is not None
    me = state.players[seat]
    resources = replace(me.resources, solari=solari, spice=spice)
    return _rewards(state, resources=resources)


def test_economic_supremacy_solari_charge_is_paid() -> None:
    state = _economic_supremacy(solari=7, spice=5)
    assert state.decision_stack[-1].kind == "combat_reward_optional"
    run = _run(state)
    assert dict(run.ctx.top_frame_context)["resource"] == "solari"
    app = W.app_reward_run(run)
    ability = W._reward_ability(
        app, DeferredAbility, lambda a: W._pay_costs(a) == (6, 0)
    )
    assert isinstance(ability, EconomicSupremacySolariAbility)
    assert W.combat_reward_optional(run) == _find(state, "pay_combat_reward")


def test_economic_supremacy_spice_charge_follows_the_solari_one() -> None:
    state = _economic_supremacy(solari=7, spice=5)
    state = _apply(state, _find(state, "pay_combat_reward"))
    assert state.decision_stack[-1].kind == "combat_reward_optional"
    run = _run(state)
    assert dict(run.ctx.top_frame_context)["resource"] == "spice"
    ability = W._reward_ability(
        W.app_reward_run(run), DeferredAbility, lambda a: W._pay_costs(a) == (0, 4)
    )
    assert isinstance(ability, EconomicSupremacySpiceAbility)
    assert W.combat_reward_optional(run) == _find(state, "pay_combat_reward")


def test_economic_supremacy_unaffordable_charge_is_declined() -> None:
    state = _economic_supremacy(solari=5, spice=5)
    run = _run(state)
    assert dict(run.ctx.top_frame_context)["resource"] == "solari"
    assert [a.action_id for a in run.legal] == ["decline_combat_reward"]
    assert W.combat_reward_optional(run) == _find(state, "decline_combat_reward")


# ===========================================================================
# Pivotal Gambit's extra 1st-place Influence
# ===========================================================================


def _expected_track(run: DecisionRun) -> str:
    app = W.app_reward_run(run)
    factions = [str(dict(a.arguments)["faction"]) for a in run.legal]
    tracks = tuple(track_entity(f) for f in factions)
    conflict = conflict_entity(app.ctx.current_conflict_id or "", app.ctx.choam)
    answer = GainAnyInfluenceConflictAbility(conflict).evaluate(
        app.profile, Request((TargetInfo(entities=tracks),), forced=True)
    )
    assert answer.response is not None
    return str(answer.response[0][0])


@pytest.mark.parametrize(
    ("config", "seed", "conflict"),
    [(PROMO, 1, None), (EPIC_PROMO, 1, "economic_supremacy")],
)
def test_pivotal_gambit_influence_takes_the_best_track(
    config: RulesetConfig, seed: int, conflict: str | None
) -> None:
    """``GainAnyInfluenceConflictAbility`` E (best track, +100). With
    Economic Supremacy the app loses the Influence; our engine asks and the
    same Evaluate answers."""

    state = _rewards(_pledged(_combat(config, seed, conflict)))
    while state.decision_stack[-1].kind != "combat_reward_influence":
        kind = state.decision_stack[-1].kind
        assert kind.startswith("combat_reward"), kind
        state = _apply(state, _legal(state)[0])
    run = _run(state)
    assert run.ctx.seat == rank_combat(state.players).winner
    action = W.combat_reward_influence(run)
    assert action == _find(
        state, "choose_combat_reward_influence", faction=_expected_track(run)
    )


def test_influence_frame_without_a_reward_or_a_pledge_is_not_mirrored() -> None:
    state = _rewards(_pledged(_combat(EPIC_PROMO, 1, "economic_supremacy")))
    assert state.decision_stack[-1].kind == "combat_reward_influence"
    unpledged = with_state(
        state,
        event_log=tuple(
            e for e in state.event_log if e.kind != "first_place_influence_pledged"
        ),
    )
    assert W.combat_reward_influence(_run(unpledged)) is None


# ===========================================================================
# Immortality: Return Specimen at the Combat Intrigue priority, Control
# defense with an empty supply
# ===========================================================================


@cache
def _specimen_combat(want_play: bool) -> GameState:
    def predicate(state: GameState, owner: int) -> bool:
        if state.decision_stack[-1].kind != "combat_intrigue":
            return False
        ids = {a.action_id for a in ENGINE.legal_actions(state, owner)}
        return "return_specimen" in ids and ("play_intrigue" in ids) == want_play

    return play_until(predicate, config=IMMORTALITY, seed=1)


def test_combatant_without_intrigue_is_passed_unasked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _specimen_combat(want_play=False)
    seat = _seat(state)
    state = with_player(state, seat, intrigue_cards=())
    run = _run(state)
    assert [a.action_id for a in run.legal] == [
        "pass_combat_intrigue",
        "return_specimen",
    ]

    def boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("not prompted")

    monkeypatch.setattr(W, "_return_specimen_sources", boom)
    assert W.combat_intrigue(run) == _find(state, "pass_combat_intrigue")


def test_return_specimen_is_no_key_without_a_shortfall() -> None:
    state = _specimen_combat(want_play=True)
    run = _run(state)
    assert run.ctx.ungained_troops() == 0
    (source,) = W._return_specimen_sources(run)
    assert source.evaluate is not None
    assert source.evaluate() == (0.0, None)


def test_return_specimen_key_covers_a_waiting_shortfall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _specimen_combat(want_play=True)
    state = with_player(state, _seat(state), ungained_troops=1)
    monkeypatch.setattr(W, "intrigue_play_sources", lambda run, actions, combat: [])
    run = _run(state)
    assert W.combat_intrigue(run) == _find(state, "return_specimen")


@cache
def _control_defense() -> GameState:
    return play_until(
        lambda s, owner: s.decision_stack[-1].kind == "control_defense",
        config=IMMORTALITY,
        seed=1,
    )


def test_control_defense_with_an_empty_supply_converts_a_specimen() -> None:
    state = _control_defense()
    seat = _seat(state)
    me = state.players[seat]
    state = with_player(
        state, seat, troops_supply=0, specimens=me.specimens + me.troops_supply
    )
    run = _run(state)
    assert {a.action_id for a in run.legal} == {
        "decline_control_defense",
        "return_specimen",
    }
    assert W.control_defense(run) == _find(state, "return_specimen")
    state = _apply(state, _find(state, "return_specimen"))
    assert W.control_defense(_run(state)) == _find(state, "deploy_control_defense")


def test_unknown_combat_intrigue_action_is_not_mirrored() -> None:
    """An action id this window does not mirror (another expansion's) gives
    no answer, even for a combatant the app would pass unasked."""

    state = _specimen_combat(want_play=False)
    seat = _seat(state)
    state = with_player(state, seat, intrigue_cards=())
    odd = DomainAction("use_unknown_combat_ability", seat)
    assert W.combat_intrigue(_run(state)) == _find(state, "pass_combat_intrigue")
    assert W.combat_intrigue(_run(state, legal=(*_legal(state), odd))) is None


def test_unknown_control_defense_action_is_not_mirrored() -> None:
    state = _control_defense()
    assert W.control_defense(_run(state)) == _find(state, "deploy_control_defense")
    odd = DomainAction("deploy_unknown_defender", _seat(state))
    assert W.control_defense(_run(state, legal=(*_legal(state), odd))) is None


def test_control_defense_without_specimens_declines() -> None:
    state = _control_defense()
    seat = _seat(state)
    me = state.players[seat]
    state = with_player(
        state,
        seat,
        troops_supply=0,
        specimens=0,
        troops_garrison=me.troops_garrison + me.troops_supply + me.specimens,
    )
    run = _run(state)
    assert [a.action_id for a in run.legal] == ["decline_control_defense"]
    assert W.control_defense(run) == _find(state, "decline_control_defense")


# ===========================================================================
# Full games
# ===========================================================================


@pytest.mark.parametrize(
    "options",
    [
        {"immortality": True},
        {"epic_game": True, "promo_cards": True},
        {"immortality": True, "go_to_11": True, "epic_game": True},
    ],
)
def test_option_games_never_fall_back_in_the_combat_windows(
    monkeypatch: pytest.MonkeyPatch, options: dict[str, bool]
) -> None:
    """Four app_ai seats with only this module's handlers installed (every
    other window answers at random): no combat decision falls back."""

    def only_combat(kind: str | None) -> Callable[[DecisionRun], object] | None:
        return None if kind is None else W.HANDLERS.get(kind)

    monkeypatch.setattr(agent_module, "handler_for", only_combat)
    mirrored: Counter[str] = Counter()
    for game in range(3):
        choam = game % 2 == 1
        seed = 80 + game
        leaders = tuple(
            random.Random(seed).sample(
                [leader.leader_id for leader in leaders_for_choam(choam)], k=4
            )
        )
        agents = tuple(AppAIAgent(seed=800 + 10 * game + seat) for seat in range(4))
        result = run_policy_game(
            UprisingRulesEngine(leader_ids=leaders),
            RulesetConfig(choam_module=choam, **options),
            seed,
            agents,
        )
        assert result.state.phase is GamePhase.FINISHED
        for agent in agents:
            for kind in W.HANDLERS:
                assert agent.fallbacks[kind] == 0, (game, kind)
                mirrored[kind] += agent.mirrored[kind]
    assert mirrored["combat_intrigue"] > 0, mirrored
