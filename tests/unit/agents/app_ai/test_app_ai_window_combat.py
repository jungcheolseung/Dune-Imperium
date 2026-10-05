"""The combat decision windows of app_ai (``windows/combat.py``).

Each test reaches the window in a real heuristic game (``testing.play_until``),
adjusts the fields that decide the answer, builds a ``DecisionRun`` and checks
the exact action the app's engine order and reward abilities give. The shared
``intrigue_play_sources`` (another window module) is stubbed.
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
from dune_imperium.agents.app_ai.abilities.base import Answer, Request
from dune_imperium.agents.app_ai.abilities.generic import (
    GainAnyInfluenceConflictAbility,
    Pay4SpiceToGain1VPAbility,
    PayAttributeToGainVPAbility,
)
from dune_imperium.agents.app_ai.catalog import post_entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    make_profile,
    play_until,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import combat as W
from dune_imperium.agents.app_ai.windows.common import Source, Stage
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.content.uprising.leaders import leaders_for_choam
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.combat import rank_combat
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

COMBAT_KINDS = frozenset(
    {
        "combat_intrigue",
        "combat_reward_optional",
        "combat_reward_distinct_influence",
        "combat_reward_influence",
        "combat_reward_spy",
        "combat_reward_spy_recall",
        "combat_reward_trash",
        "control_defense",
        "endgame_intrigue",
    }
)
_WANTS: dict[str, Callable[[set[str]], bool]] = {
    "any": lambda ids: True,
    "several": lambda ids: len(ids) > 1,
    "play": lambda ids: "play_intrigue" in ids,
    "pay": lambda ids: "pay_combat_reward" in ids,
    "recall": lambda ids: "recall_spies_for_combat_reward" in ids,
    "play_and_match": lambda ids: {"play_intrigue", "match_endgame_wild_icon"} <= ids,
}


@cache
def _reach(kind: str, *, choam: bool, seed: int, want: str = "any") -> GameState:
    """The first heuristic-game state asking ``kind`` whose legal ids pass."""

    def predicate(state: GameState, owner: int) -> bool:
        if state.decision_stack[-1].kind != kind:
            return False
        ids = {a.action_id for a in ENGINE.legal_actions(state, owner)}
        return _WANTS[want](ids)

    return play_until(predicate, choam=choam, seed=seed)


@cache
def _sandworm_rewards(conflict: str, seed: int) -> GameState:
    """The first reward frame of ``conflict`` won with a sandworm (base game).

    From the Conflict's first ``combat_intrigue`` prompt the sole leader gets
    a sandworm and every combatant passes, so the engine pays the doubled
    reward and stacks its frames.
    """

    state = play_until(
        lambda s, owner: (
            s.decision_stack[-1].kind == "combat_intrigue"
            and s.current_conflict_ids[-1] == conflict
        ),
        choam=False,
        seed=seed,
    )
    winner = rank_combat(state.players, first_player=state.first_player).winner
    assert winner is not None
    state = with_player(state, winner, sandworms_conflict=1)
    while state.decision_stack[-1].kind == "combat_intrigue":
        state = ENGINE.apply(
            state, DomainAction("pass_combat_intrigue", _seat(state))
        ).state
    return state


def _seat(state: GameState) -> int:
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _run(
    state: GameState,
    *,
    legal: Sequence[DomainAction] | None = None,
    memory: Memory | None = None,
    rng_seed: int = 0,
) -> DecisionRun:
    seat = _seat(state)
    profile = make_profile(state, seat, rng_seed=rng_seed)
    actions = tuple(ENGINE.legal_actions(state, seat) if legal is None else legal)
    return DecisionRun(profile.ctx, profile, actions, profile.rng, memory or Memory())


def _ids(actions: Sequence[DomainAction]) -> list[str]:
    return [a.action_id for a in actions]


def _args(action: DomainAction | None) -> tuple[str, dict[str, object]]:
    assert action is not None
    return action.action_id, dict(action.arguments)


# -- registry ------------------------------------------------------------------------


def test_handlers_cover_every_combat_window() -> None:
    assert set(W.HANDLERS) == COMBAT_KINDS


# -- control_defense -----------------------------------------------------------------


def test_control_defense_always_deploys() -> None:
    run = _run(_reach("control_defense", choam=False, seed=1))
    assert _ids(run.legal) == ["decline_control_defense", "deploy_control_defense"]
    assert _args(W.control_defense(run)) == ("deploy_control_defense", {})


def test_control_defense_declines_only_when_it_is_the_sole_answer() -> None:
    state = _reach("control_defense", choam=False, seed=1)
    run = _run(state, legal=[DomainAction("decline_control_defense", _seat(state))])
    assert _args(W.control_defense(run)) == ("decline_control_defense", {})


# -- combat_intrigue -----------------------------------------------------------------


def _intrigue_state() -> GameState:
    return _reach("combat_intrigue", choam=False, seed=1, want="play")


def test_combat_intrigue_plays_the_best_positive_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _run(_intrigue_state())
    plays = run.by_id("play_intrigue")
    seen: list[tuple[tuple[DomainAction, ...], bool]] = []

    def stub(
        run: DecisionRun, actions: Sequence[DomainAction], *, combat: bool
    ) -> list[Source]:
        seen.append((tuple(actions), combat))
        return [
            Source("weak", Stage.PROMPT, (plays[0],), lambda: (3.0, plays[0])),
            Source("strong", Stage.PROMPT, (plays[-1],), lambda: (8.0, plays[-1])),
        ]

    monkeypatch.setattr(W, "intrigue_play_sources", stub)
    assert W.combat_intrigue(run) == plays[-1]
    assert seen == [(plays, True)]


@pytest.mark.parametrize("value", [-1.0, 0.0])
def test_combat_intrigue_passes_without_a_positive_source(
    monkeypatch: pytest.MonkeyPatch, value: float
) -> None:
    run = _run(_intrigue_state())
    play = run.by_id("play_intrigue")[0]
    monkeypatch.setattr(
        W,
        "intrigue_play_sources",
        lambda run, actions, *, combat: [
            Source("sole first", Stage.PROMPT, (play,), lambda: (value, play))
        ],
    )
    assert _args(W.combat_intrigue(run)) == ("pass_combat_intrigue", {})


def test_combat_intrigue_without_plays_passes_unasked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _intrigue_state()
    run = _run(state, legal=[DomainAction("pass_combat_intrigue", _seat(state))])

    def boom(run: DecisionRun, actions: object, *, combat: bool) -> list[Source]:
        raise AssertionError("no play to evaluate")

    monkeypatch.setattr(W, "intrigue_play_sources", boom)
    assert _args(W.combat_intrigue(run)) == ("pass_combat_intrigue", {})


# -- the app's view of a reward window -------------------------------------------------


def _recall_state() -> GameState:
    # Base seed 88, round 10: seat 3 wins Battle for Arrakeen (crysknife) with
    # three spies out and a face-up crysknife Objective. (Seed 4 reached this
    # until the 2026-10-06 card-comparison batch moved its game.)
    return _reach("combat_reward_spy_recall", choam=False, seed=88, want="recall")


def test_app_reward_run_scores_the_winners_pending_icon_pair() -> None:
    state = _recall_state()
    seat = _seat(state)
    me = state.players[seat]
    assert state.current_conflict_ids[-1] == "battle_for_arrakeen"
    assert me.objective_ids == ("objective_crysknife_2",)
    app = W.app_reward_run(_run(state)).ctx.state.players[seat]
    assert app.victory_points == me.victory_points + 1
    assert app.won_conflict_ids == (*me.won_conflict_ids, "battle_for_arrakeen")
    assert app.face_down_battle_card_ids == (
        *me.face_down_battle_card_ids,
        "objective_crysknife_2",
        "battle_for_arrakeen",
    )
    # The engine's own state is untouched.
    assert state.players[seat] is me


def test_app_reward_run_pending_vp_doubles_the_vp_value() -> None:
    state = _recall_state()
    seat = _seat(state)
    state = with_player(state, seat, victory_points=8)
    run = _run(state)
    # GetVictoryPointValue: late arc 9.0, doubled from 10 VP (literal 10).
    assert run.profile.victory_point_value(1) == 9.0
    assert W.app_reward_run(run).profile.victory_point_value(1) == 18.0


def test_app_reward_run_adds_an_unpaired_icon_without_vp() -> None:
    state = _reach("combat_reward_optional", choam=False, seed=1, want="pay")
    seat = _seat(state)
    me = state.players[seat]
    assert state.current_conflict_ids[-1] == "battle_for_imperial_basin"
    app = W.app_reward_run(_run(state)).ctx.state.players[seat]
    assert app.victory_points == me.victory_points
    assert app.won_conflict_ids == (*me.won_conflict_ids, "battle_for_imperial_basin")
    assert app.face_down_battle_card_ids == me.face_down_battle_card_ids


def test_app_reward_run_without_a_sole_winner_is_the_same_run() -> None:
    state = _recall_state()
    top = max(p.combat_strength for p in state.players)
    tied = with_player(state, 0, combat_strength=top)
    tied = with_player(tied, 1, combat_strength=top)
    run = _run(tied)
    assert W.app_reward_run(run) is run


# -- combat_reward_optional ----------------------------------------------------------


def test_optional_reward_pays_whenever_affordable() -> None:
    state = _reach("combat_reward_optional", choam=False, seed=1, want="pay")
    run = _run(state)
    assert dict(run.ctx.top_frame_context)["cost"] == 4
    ability = W._reward_ability(run, PayAttributeToGainVPAbility)
    assert isinstance(ability, Pay4SpiceToGain1VPAbility)
    assert _args(W.combat_reward_optional(run)) == ("pay_combat_reward", {})


def test_optional_reward_declines_when_unaffordable() -> None:
    state = _reach("combat_reward_optional", choam=False, seed=1, want="pay")
    seat = _seat(state)
    me = state.players[seat]
    poor = with_player(state, seat, resources=replace(me.resources, spice=3))
    run = _run(poor)
    assert _ids(run.legal) == ["decline_combat_reward"]
    assert _args(W.combat_reward_optional(run)) == ("decline_combat_reward", {})


def test_optional_reward_with_no_matching_app_ability_falls_back() -> None:
    state = _reach("combat_reward_optional", choam=False, seed=1, want="pay")
    frame = state.decision_stack[-1]
    context = {**dict(frame.context), "cost": 5}
    odd = replace(frame, context=tuple(sorted(context.items())))
    state = with_state(state, decision_stack=(*state.decision_stack[:-1], odd))
    assert W.combat_reward_optional(_run(state)) is None


# -- combat_reward_spy_recall --------------------------------------------------------


def test_spy_recall_takes_the_vp_with_the_two_worst_posts() -> None:
    run = _run(_recall_state())
    app = W.app_reward_run(run)
    seat = run.ctx.seat
    values = {
        post: app.profile.post_value(post_entity(post, seat))
        for post in run.ctx.me.spy_post_ids
    }
    assert values == {
        "arrakis-research-station-sietch-tabr": 3.5,
        "bene-gesserit-espionage-secrets": 3.0,
        "choam-shipping-accept-contract": 0.0,
    }
    assert _args(W.combat_reward_spy_recall(run)) == (
        "recall_spies_for_combat_reward",
        {
            "first_post_id": "bene-gesserit-espionage-secrets",
            "second_post_id": "choam-shipping-accept-contract",
        },
    )


def test_spy_recall_declines_when_the_value_is_not_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Evaluate = VP value + 2 RecallSpyValue; with the VP worth nothing the
    # two (negative) recall values decide.
    monkeypatch.setattr(Profile, "victory_point_value", lambda self, amount: 0.0)
    run = _run(_recall_state())
    assert W.app_reward_run(run).profile.recall_spy_value().sum < 0.0
    assert _args(W.combat_reward_spy_recall(run)) == ("decline_combat_reward", {})


def test_spy_recall_without_two_spies_declines_unasked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Cost (HasAtLeastSpiesOnBoard) fails: the key is not offered, so the
    # window's empty answer; the ability is never looked up or evaluated.
    state = _recall_state()
    seat = _seat(state)
    me = state.players[seat]
    state = with_player(
        state,
        seat,
        spy_post_ids=("arrakis-hagga-basin",),
        spies_supply=me.spies_supply + len(me.spy_post_ids) - 1,
    )
    run = _run(state)
    assert _ids(run.legal) == ["decline_combat_reward"]

    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("no pair to evaluate")

    monkeypatch.setattr(W, "_reward_ability", boom)
    assert _args(W.combat_reward_spy_recall(run)) == ("decline_combat_reward", {})


# -- combat_reward_trash -------------------------------------------------------------


def _trash_state(discard: tuple[str, ...]) -> GameState:
    # Base seed 2, round 4: seat 3 takes Trade Dispute's 2nd-place trash.
    state = _reach("combat_reward_trash", choam=False, seed=2)
    seat = _seat(state)
    assert state.players[seat].hand == ()
    assert state.players[seat].in_play == ()
    return with_player(state, seat, discard_pile=discard)


def test_trash_reward_trashes_the_junk_card() -> None:
    state = _trash_state(
        (
            "imperium:steersman:0",
            "player:3:starter:diplomacy:0",
            "player:3:starter:dagger:0",
            "player:3:starter:signet_ring:0",
        )
    )
    assert _args(W.combat_reward_trash(_run(state))) == (
        "trash_combat_reward_card",
        {"card_id": "player:3:starter:dagger:0"},
    )


def test_trash_reward_trashes_nothing_without_junk() -> None:
    state = _trash_state(
        (
            "imperium:steersman:0",
            "player:3:starter:diplomacy:0",
            "player:3:starter:signet_ring:0",
        )
    )
    assert _args(W.combat_reward_trash(_run(state))) == (
        "decline_combat_reward_trash",
        {},
    )


# -- combat_reward_influence ---------------------------------------------------------


def test_influence_reward_takes_the_best_track() -> None:
    # Base seed 2, round 6: seat 2 wins Spice Freighters with Emperor at 6.
    state = _reach("combat_reward_influence", choam=False, seed=2)
    run = _run(state)
    assert [arg(a, "faction") for a in run.legal] == [
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    ]
    app = W.app_reward_run(run)
    values = {
        f: app.profile.gain_influence_value(f, 1, -1, False).sum
        for f in ("spacing_guild", "bene_gesserit", "fremen")
    }
    assert values == pytest.approx(
        {"spacing_guild": 2.7, "bene_gesserit": 2.8125, "fremen": 2.7}
    )
    assert _args(W.combat_reward_influence(run)) == (
        "choose_combat_reward_influence",
        {"faction": "bene_gesserit"},
    )


def test_influence_reward_with_every_track_full_confirms() -> None:
    state = _reach("combat_reward_influence", choam=False, seed=2)
    confirm = DomainAction("resolve_combat_influence_without_faction", _seat(state))
    assert W.combat_reward_influence(_run(state, legal=[confirm])) == confirm


@pytest.mark.parametrize(
    ("spice", "answers", "seen"),
    [
        # Both payments affordable: the second pick sees the first payment
        # (spice 6 -> 3, VP +1 on top of Bene Gesserit's 2-Influence VP).
        (
            6,
            [
                "bene_gesserit",
                "pay_combat_reward",
                "spacing_guild",
                "pay_combat_reward",
            ],
            [(6, 5), (3, 7)],
        ),
        # The first payment leaves 1 spice: the second copy is not offered.
        (
            4,
            [
                "bene_gesserit",
                "pay_combat_reward",
                "spacing_guild",
                "decline_combat_reward",
            ],
            [(4, 5), (1, 7)],
        ),
        # Never affordable. The app's window ends after the first copy (no
        # prompt key left) and never gains the second Influence; our engine
        # still asks it (forced), answered by the same Evaluate: not mirrored.
        (
            2,
            [
                "bene_gesserit",
                "decline_combat_reward",
                "spacing_guild",
                "decline_combat_reward",
            ],
            [(2, 5), (2, 6)],
        ),
    ],
)
def test_sandworm_spice_freighters_values_each_copy_after_the_previous_one(
    monkeypatch: pytest.MonkeyPatch,
    spice: int,
    answers: list[str],
    seen: list[tuple[int, int]],
) -> None:
    """Our frames (influence, pay, influence, pay) are the app's order: one
    copy of the deferred influence ability per window pass, the pay prompt
    between them (``windows.combat.combat_reward_influence``)."""

    # Base seed 2, round 6: seat 2 wins Spice Freighters (Emperor at 6).
    state = _sandworm_rewards("spice_freighters", 2)
    seat = _seat(state)
    me = state.players[seat]
    state = with_player(state, seat, resources=replace(me.resources, spice=spice))
    assert [f.kind for f in reversed(state.decision_stack)] == [
        "combat_reward_influence",
        "combat_reward_optional",
        "combat_reward_influence",
        "combat_reward_optional",
    ]
    evaluated: list[tuple[int, int]] = []
    evaluate = GainAnyInfluenceConflictAbility.evaluate

    def spy(
        self: GainAnyInfluenceConflictAbility, p: Profile, request: Request
    ) -> Answer:
        evaluated.append((p.ctx.me.resources.spice, p.ctx.me.victory_points))
        return evaluate(self, p, request)

    monkeypatch.setattr(GainAnyInfluenceConflictAbility, "evaluate", spy)
    taken: list[str] = []
    for _ in range(4):
        run = _run(state)
        action = W.HANDLERS[state.decision_stack[-1].kind](run)
        assert action is not None
        taken.append(str(dict(action.arguments).get("faction", action.action_id)))
        state = ENGINE.apply(state, action, legal_actions=run.legal).state
    assert taken == answers
    # The app's view (battle-icon pair already scored: +1 VP) of each pick.
    assert evaluated == seen


# -- combat_reward_distinct_influence ------------------------------------------------


def _propaganda_state() -> GameState:
    # Base seed 25, round 8: seat 2 wins Propaganda; Spacing Guild and Bene
    # Gesserit tie at the top (4.4625), Emperor 3.45, Fremen 1.875. (Seed 1
    # reached the same values until the 2026-10-06 card-comparison batch
    # moved its game.)
    return _reach("combat_reward_distinct_influence", choam=False, seed=25)


def test_distinct_influence_names_both_tracks_in_one_answer() -> None:
    state = _propaganda_state()
    memory = Memory()
    run = _run(state, memory=memory)
    app = W.app_reward_run(run)
    values = {
        f: app.profile.gain_influence_value(f, 1, -1, False).sum
        for f in ("emperor", "spacing_guild", "bene_gesserit", "fremen")
    }
    assert values == pytest.approx(
        {
            "emperor": 3.45,
            "spacing_guild": 4.4625,
            "bene_gesserit": 4.4625,
            "fremen": 1.875,
        }
    )
    first = W.combat_reward_distinct_influence(run)
    key = (W.DISTINCT_INFLUENCE_INTENT, state.round_number, run.ctx.seat, 0)
    plan = memory.intents[key]
    assert isinstance(plan, tuple)
    assert set(plan) == {"spacing_guild", "bene_gesserit"}
    assert _args(first) == (
        "choose_distinct_combat_reward_influence",
        {"faction": plan[0]},
    )
    assert first is not None
    second_state = ENGINE.apply(state, first).state
    assert second_state.decision_stack[-1].kind == "combat_reward_distinct_influence"
    second = W.combat_reward_distinct_influence(_run(second_state, memory=memory))
    assert _args(second) == (
        "choose_distinct_combat_reward_influence",
        {"faction": plan[1]},
    )
    assert key not in memory.intents


def test_distinct_influence_second_pick_without_a_plan_reevaluates() -> None:
    state = _propaganda_state()
    first = W.combat_reward_distinct_influence(_run(state))
    assert first is not None
    named = arg(first, "faction")
    second_state = ENGINE.apply(state, first).state
    second = W.combat_reward_distinct_influence(_run(second_state, memory=Memory()))
    assert named in {"spacing_guild", "bene_gesserit"}
    other = ({"spacing_guild", "bene_gesserit"} - {named}).pop()
    assert _args(second) == (
        "choose_distinct_combat_reward_influence",
        {"faction": other},
    )


def test_distinct_influence_sandworm_plans_each_group_after_the_previous() -> None:
    # Base seed 0, round 9, everyone passing: seat 0 wins Propaganda with a
    # sandworm. Copy 1 asks frames of group 0, copy 2 frames of group 2; the
    # app runs copy 2's Evaluate once copy 1's two gains are applied. (Seed 1
    # reached the same shape until the 2026-10-06 card-comparison batch
    # moved its game.)
    state = _sandworm_rewards("propaganda", 0)
    seat, round_number = _seat(state), state.round_number
    assert round_number == 9
    assert [dict(f.context)["group"] for f in reversed(state.decision_stack)] == [
        0,
        0,
        2,
        2,
    ]
    memory = Memory()
    factions = ("emperor", "spacing_guild", "bene_gesserit", "fremen")
    plans: dict[tuple[object, ...], object] = {}
    values: list[dict[str, float]] = []
    taken: list[object] = []
    while state.decision_stack and (
        state.decision_stack[-1].kind == "combat_reward_distinct_influence"
    ):
        run = _run(state, memory=memory)
        app = W.app_reward_run(run)
        values.append(
            {f: app.profile.gain_influence_value(f, 1, -1, False).sum for f in factions}
        )
        action = W.combat_reward_distinct_influence(run)
        assert action is not None
        plans.update(memory.intents)
        taken.append(arg(action, "faction"))
        state = ENGINE.apply(state, action, legal_actions=run.legal).state
    key = (W.DISTINCT_INFLUENCE_INTENT, round_number, seat)
    assert set(plans) == {(*key, 0), (*key, 2)}
    assert not memory.intents
    first, second = plans[(*key, 0)], plans[(*key, 2)]
    assert isinstance(first, tuple)
    assert isinstance(second, tuple)
    assert taken == [*first, *second]
    # Copy 1: Fremen best; Spacing Guild and Bene Gesserit tie (shuffled).
    assert values[0] == pytest.approx(
        {
            "emperor": 1.125,
            "spacing_guild": 2.7,
            "bene_gesserit": 2.7,
            "fremen": 3.875,
        }
    )
    # The Evaluate's shuffle (rng seed 0) puts Bene Gesserit first of the tie.
    assert first == ("fremen", "bene_gesserit")
    # Copy 2 sees copy 1's gains: Bene Gesserit at 3 is now worth the most,
    # and Fremen at 4 the least.
    assert values[2] == pytest.approx(
        {
            "emperor": 1.125,
            "spacing_guild": 2.7,
            "bene_gesserit": 7.375,
            "fremen": 0.5625,
        }
    )
    assert second == ("bene_gesserit", "spacing_guild")
    assert state.players[seat].influence.bene_gesserit == 4


# -- combat_reward_spy ---------------------------------------------------------------


def _spy_state() -> GameState:
    # Base seed 1, round 5: seat 0 wins Seize Spice Refinery with 3 spies in
    # supply; Fremkit and Sardaukar posts value 3.0, High Council 2.0.
    return _reach("combat_reward_spy", choam=False, seed=1)


def test_reward_spy_goes_to_the_best_free_post() -> None:
    state = _spy_state()
    other = state.players[1]
    state = with_player(
        state,
        1,
        spy_post_ids=(*other.spy_post_ids, "fremen-desert-tactics-fremkit"),
        spies_supply=other.spies_supply - 1,
    )
    run = _run(state)
    assert "fremen-desert-tactics-fremkit" not in {arg(a, "post_id") for a in run.legal}
    assert _args(W.combat_reward_spy(run)) == (
        "place_combat_reward_spy",
        {"post_id": "emperor-sardaukar-dutiful-service"},
    )


def test_reward_spy_with_an_empty_supply_recalls_the_worst_post() -> None:
    state = _spy_state()
    seat = _seat(state)
    posts = (
        "emperor-sardaukar-dutiful-service",
        "landsraad-assembly-hall-gather-support",
        "arrakis-hagga-basin",
    )
    state = with_player(state, seat, spy_post_ids=posts, spies_supply=0)
    run = _run(state)
    assert _ids(run.legal) == [
        "decline_combat_reward_spy",
        *["recall_spy_for_combat_reward"] * 3,
    ]
    app = W.app_reward_run(run)
    values = [app.profile.post_value(post_entity(p, seat)) for p in posts]
    assert values == [3.0, 0.0, 1.0]
    assert _args(W.combat_reward_spy(run)) == (
        "recall_spy_for_combat_reward",
        {"post_id": "landsraad-assembly-hall-gather-support"},
    )


# -- endgame_intrigue ----------------------------------------------------------------


def test_endgame_plays_first_then_matches_then_passes() -> None:
    # Base seed 18: seat 2 holds Shadow Alliance (offered) and Secure Spice
    # Trade (not playable), and a face-up crysknife Objective beside Propaganda.
    state = _reach("endgame_intrigue", choam=False, seed=18, want="play_and_match")
    seat = _seat(state)
    taken: list[tuple[str, dict[str, object]]] = []
    while state.decision_stack and state.decision_stack[-1].kind == "endgame_intrigue":
        if _seat(state) != seat:
            break
        run = _run(state)
        action = W.endgame_intrigue(run) if len(run.legal) > 1 else run.legal[0]
        assert action is not None
        taken.append(_args(action))
        state = ENGINE.apply(state, action, legal_actions=run.legal).state
    assert taken == [
        ("play_intrigue", {"card_id": "intrigue:shadow_alliance:0", "option": 0}),
        (
            "match_endgame_wild_icon",
            {"matching_card_id": "objective_crysknife_1", "wild_card_id": "propaganda"},
        ),
        ("pass_endgame_intrigue", {}),
    ]


def test_endgame_plays_secure_spice_trade() -> None:
    state = _reach("endgame_intrigue", choam=True, seed=1, want="several")
    assert _args(W.endgame_intrigue(_run(state))) == (
        "play_intrigue",
        {"card_id": "intrigue:secure_spice_trade:0", "option": 0},
    )


def test_endgame_never_takes_a_match_the_app_would_not_score() -> None:
    # Base seed 1: seat 1 holds Propaganda (wild) beside face-up Secure
    # Imperial Basin (desert mouse) and Battle for Imperial Basin
    # (ornithopter); the engine offers both matches, and the app's own pair
    # order takes Secure Imperial Basin. (Until the 2026-10-06
    # card-comparison batch moved this game, the seat paired a crysknife
    # Objective.)
    state = _reach("endgame_intrigue", choam=False, seed=1, want="several")
    seat = _seat(state)
    stray = DomainAction(
        "match_endgame_wild_icon",
        seat,
        (("matching_card_id", "battle_for_arrakeen"), ("wild_card_id", "propaganda")),
    )
    legal = [DomainAction("pass_endgame_intrigue", seat), stray]
    assert _args(W.endgame_intrigue(_run(state, legal=legal))) == (
        "pass_endgame_intrigue",
        {},
    )
    assert _ids(_run(state).legal).count("match_endgame_wild_icon") == 2
    assert _args(W.endgame_intrigue(_run(state))) == (
        "match_endgame_wild_icon",
        {"matching_card_id": "secure_imperial_basin", "wild_card_id": "propaganda"},
    )


# -- coverage: full games with four app_ai seats ---------------------------------------


def test_app_ai_games_answer_every_combat_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Six games (base and CHOAM, leaders rotated by seed) with only these
    handlers active: none of the combat windows falls back, every game ends."""

    def worth_half(action: DomainAction) -> Callable[[], tuple[float, DomainAction]]:
        return lambda: (0.5, action)

    def stub(
        run: DecisionRun, actions: Sequence[DomainAction], *, combat: bool
    ) -> list[Source]:
        assert combat
        return [
            Source(f"stub {i}", Stage.PROMPT, (a,), worth_half(a))
            for i, a in enumerate(actions)
        ]

    monkeypatch.setattr(W, "intrigue_play_sources", stub)
    monkeypatch.setattr(
        agent_module,
        "handler_for",
        lambda kind: None if kind is None else W.HANDLERS.get(kind),
    )
    mirrored: Counter[str] = Counter()
    fallbacks: Counter[str] = Counter()
    for choam, seed in (
        (False, 3),
        (True, 4),
        (False, 5),
        (True, 6),
        (False, 7),
        (True, 8),
    ):
        roster = [leader.leader_id for leader in leaders_for_choam(choam)]
        leaders = tuple(random.Random(seed).sample(roster, k=4))
        engine = UprisingRulesEngine(leader_ids=leaders)
        agents = tuple(AppAIAgent(seed=1000 * seed + s) for s in range(4))
        result = run_policy_game(
            engine, RulesetConfig(choam_module=choam), seed, agents
        )
        assert result.state.phase is GamePhase.FINISHED
        assert tuple(p.leader_id for p in result.state.players) == leaders
        for agent in agents:
            mirrored.update(agent.mirrored)
            fallbacks.update(agent.fallbacks)
    assert not {kind: n for kind, n in fallbacks.items() if kind in COMBAT_KINDS}
    assert {"combat_intrigue", "control_defense", "combat_reward_spy"} <= set(mirrored)
    assert set(mirrored) <= COMBAT_KINDS
