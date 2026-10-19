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
from tests.support.reward_windows import answer_reward_windows

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
    a sandworm and every combatant passes, so the engine opens the doubled
    reward's window, whose rows are answered in the older engine's order up
    to the first reward frame (stage B2, OQ-112: a window's icons open their
    frames one after the other, no longer all at once).
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
    return answer_reward_windows(ENGINE, state)


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
    # Base seed 116, round 7: seat 1 (Gurney Halleck) wins Battle for Arrakeen
    # (crysknife) with three spies out and a face-up crysknife Objective. (Seed
    # 4 reached this until the 2026-10-06 card-comparison batch moved its
    # game, and seed 88 until 5654d7f8 did, 2026-10-07: a Combat Intrigue
    # pass right after a card play no longer counts as a consecutive pass.
    # Of seeds 88-116, 116 is the first whose winner both pairs the Conflict
    # with a face-up card and has three spies out: 93, 99 and 103 have two
    # spies, 95, 100 and 110 no pair.)
    return _reach("combat_reward_spy_recall", choam=False, seed=116, want="recall")


def test_app_reward_run_scores_the_winners_pending_icon_pair() -> None:
    state = _recall_state()
    seat = _seat(state)
    me = state.players[seat]
    assert state.current_conflict_ids[-1] == "battle_for_arrakeen"
    assert me.objective_ids == ("objective_crysknife_1",)
    app = W.app_reward_run(_run(state)).ctx.state.players[seat]
    assert app.victory_points == me.victory_points + 1
    assert app.won_conflict_ids == (*me.won_conflict_ids, "battle_for_arrakeen")
    assert app.face_down_battle_card_ids == (
        *me.face_down_battle_card_ids,
        "objective_crysknife_1",
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


def _pay_state() -> GameState:
    # Base seed 10, round 8: seat 0 (Feyd-Rautha Harkonnen) wins Battle for
    # Imperial Basin beside a face-down desert mouse pair and may pay 4 spice
    # for a Victory Point. (Seed 1 reached the pay prompt until the user
    # ruling of 2026-10-14 -- an optional effect of the Agent turn offers no
    # refusal and lapses at the turn's end, OQ-095 (2) -- moved the
    # heuristic games; 10 is the first seed from 1 that reaches it again.)
    return _reach("combat_reward_optional", choam=False, seed=10, want="pay")


def test_app_reward_run_adds_an_unpaired_icon_without_vp() -> None:
    state = _pay_state()
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
    state = _pay_state()
    run = _run(state)
    assert dict(run.ctx.top_frame_context)["cost"] == 4
    ability = W._reward_ability(run, PayAttributeToGainVPAbility)
    assert isinstance(ability, Pay4SpiceToGain1VPAbility)
    assert _args(W.combat_reward_optional(run)) == ("pay_combat_reward", {})


def test_optional_reward_declines_when_unaffordable() -> None:
    state = _pay_state()
    seat = _seat(state)
    me = state.players[seat]
    poor = with_player(state, seat, resources=replace(me.resources, spice=3))
    run = _run(poor)
    assert _ids(run.legal) == ["decline_combat_reward"]
    assert _args(W.combat_reward_optional(run)) == ("decline_combat_reward", {})


def test_optional_reward_with_no_matching_app_ability_falls_back() -> None:
    state = _pay_state()
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
        "choam-shipping-accept-contract": 1.0,
        "landsraad-high-council-imperial-privilege-swordmaster": 4.0,
        "arrakis-hagga-basin": 2.5,
    }
    assert _args(W.combat_reward_spy_recall(run)) == (
        "recall_spies_for_combat_reward",
        {
            "first_post_id": "choam-shipping-accept-contract",
            "second_post_id": "arrakis-hagga-basin",
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
    # Base seed 28, round 5: seat 3 wins Trade Dispute, so its trash is the
    # first one asked. (Seed 2 reached seat 3's trash until 5654d7f8 moved
    # its game, 2026-10-07; there seat 3's deck holds the starter Diplomacy
    # and Signet Ring placed in the discard pile below, and Steersman is in
    # the Imperium Row. Seed 28 is the first from 2 whose first trash is
    # seat 3's with these four cards free to place.)
    state = _reach("combat_reward_trash", choam=False, seed=28)
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
    # Base seed 2, round 6: seat 2 (Lady Amber Metulli) wins Spice
    # Freighters with Bene Gesserit at 3, every track offered; Bene Gesserit
    # is worth by far the most. (Until 5654d7f8 moved this game, 2026-10-07,
    # seat 2 won it with Emperor at 6 and Bene Gesserit was the best of
    # three; until Imperial Privilege's card draw became its own icon,
    # 2026-10-10, OQ-027 (d), which moved the game at round 3 seat 2's
    # Imperial Privilege visit, seat 0 won it with only Fremen at 3 and
    # Fremen was worth the most; until the user ruling of 2026-10-14 (an
    # optional effect of the Agent turn lapses at the turn's end, OQ-095
    # (2)) moved the heuristic games, seat 0 won it with Bene Gesserit and
    # Fremen at 3.)
    state = _reach("combat_reward_influence", choam=False, seed=2)
    run = _run(state)
    factions = ("emperor", "spacing_guild", "bene_gesserit", "fremen")
    assert [arg(a, "faction") for a in run.legal] == list(factions)
    app = W.app_reward_run(run)
    values = {
        f: app.profile.gain_influence_value(f, 1, -1, False).sum for f in factions
    }
    assert values == pytest.approx(
        {
            "emperor": 3.45,
            "spacing_guild": 3.0,
            "bene_gesserit": 6.125,
            "fremen": 1.875,
        }
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
        # (spice 6 -> 3, VP +1 on top of Emperor's 2-Influence VP), and with
        # Emperor at 2 Bene Gesserit is now worth more (2.25 against 2.8125).
        (
            6,
            [
                "emperor",
                "pay_combat_reward",
                "bene_gesserit",
                "pay_combat_reward",
            ],
            [(6, 2), (3, 4)],
        ),
        # The first payment leaves 1 spice: the second copy is not offered.
        (
            4,
            [
                "emperor",
                "pay_combat_reward",
                "bene_gesserit",
                "decline_combat_reward",
            ],
            [(4, 2), (1, 4)],
        ),
        # Never affordable. The app's window ends after the first copy (no
        # prompt key left) and never gains the second Influence; our engine
        # still asks it (forced), answered by the same Evaluate: not mirrored.
        (
            2,
            [
                "emperor",
                "decline_combat_reward",
                "bene_gesserit",
                "decline_combat_reward",
            ],
            [(2, 2), (2, 3)],
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

    # Base seed 7, round 2: seat 3 (Lady Jessica, 1 VP, Emperor and Bene
    # Gesserit at 1) wins Spice Freighters (crysknife) beside a face-up
    # crysknife Objective; Emperor and Bene Gesserit tie at 2.8125 and the
    # first strict maximum takes Emperor. (Seed 2 reached this until
    # 5654d7f8 moved its game, 2026-10-07; it now gives Spice Freighters to a
    # seat with no icon pair that takes Fremen twice. Seed 7 is the first
    # from 2 whose winner pairs the icon and picks two different tracks: 3
    # takes Fremen twice, 5 has no sole winner.)
    state = _sandworm_rewards("spice_freighters", 7)
    seat = _seat(state)
    me = state.players[seat]
    state = with_player(state, seat, resources=replace(me.resources, spice=spice))
    # The first copy's Influence frame is on top of the window, whose
    # remaining rows open the others as they are answered.
    assert [f.kind for f in reversed(state.decision_stack)] == [
        "combat_reward_influence",
        "combat_reward_icons",
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
    frames: list[str] = []
    for _ in range(4):
        run = _run(state)
        frames.append(state.decision_stack[-1].kind)
        action = W.HANDLERS[state.decision_stack[-1].kind](run)
        assert action is not None
        taken.append(str(dict(action.arguments).get("faction", action.action_id)))
        state = ENGINE.apply(state, action, legal_actions=run.legal).state
        state = answer_reward_windows(ENGINE, state)
    # Our frames, met one after the other, are the app's order.
    assert frames == [
        "combat_reward_influence",
        "combat_reward_optional",
        "combat_reward_influence",
        "combat_reward_optional",
    ]
    assert taken == answers
    # The app's view (battle-icon pair already scored: +1 VP) of each pick.
    assert evaluated == seen


# -- combat_reward_distinct_influence ------------------------------------------------


_PROPAGANDA_BEST = {"bene_gesserit", "spacing_guild"}


def _propaganda_state() -> GameState:
    # Base seed 32, round 7: seat 1 (Gurney Halleck) wins Propaganda; Bene
    # Gesserit (3.375) and Spacing Guild (2.7) are the two best, Emperor and
    # Fremen 2.25. (Seed 1 reached the same shape until the 2026-10-06
    # card-comparison batch moved its game, then seed 25 until Imperial
    # Privilege's card draw became its own icon, 2026-10-10, OQ-027 (d),
    # moved that game at round 5 seat 2's Imperial Privilege visit, then
    # seed 31 until the user ruling of 2026-10-14 (an optional effect of the
    # Agent turn lapses at the turn's end, OQ-095 (2)) moved the heuristic
    # games: its winner now has three tracks tied at 2.7. Seed 32 is the
    # first from 31 with two strictly best tracks.)
    return _reach("combat_reward_distinct_influence", choam=False, seed=32)


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
            "emperor": 2.25,
            "spacing_guild": 2.7,
            "bene_gesserit": 3.375,
            "fremen": 2.25,
        }
    )
    first = W.combat_reward_distinct_influence(run)
    key = (W.DISTINCT_INFLUENCE_INTENT, state.round_number, run.ctx.seat, 0)
    plan = memory.intents[key]
    assert isinstance(plan, tuple)
    assert set(plan) == _PROPAGANDA_BEST
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
    assert named in _PROPAGANDA_BEST
    other = (_PROPAGANDA_BEST - {named}).pop()
    assert _args(second) == (
        "choose_distinct_combat_reward_influence",
        {"faction": other},
    )


def test_distinct_influence_sandworm_plans_each_group_after_the_previous() -> None:
    # Base seed 1, round 9, everyone passing: seat 0 (Feyd-Rautha Harkonnen,
    # Emperor 5, Bene Gesserit 1) wins Propaganda with a sandworm. Copy 1
    # asks frames of group 0, copy 2 frames of group 2; the app runs copy
    # 2's Evaluate once copy 1's two gains are applied. (Seed 0 reached the
    # same shape until the 2026-10-06 Intrigue effect gate moved its game: a
    # seat no longer plays Call to Arms in a Reveal with nothing left to
    # acquire. Until 5654d7f8 seat 1 won it here, then seat 3 (Lady Jessica)
    # until Imperial Privilege's card draw became its own icon, 2026-10-10,
    # OQ-027 (d), which moved the game at round 4 seat 0's Imperial
    # Privilege visit, then seat 1 (Gurney Halleck) until the user ruling of
    # 2026-10-14, an optional effect of the Agent turn lapsing at the turn's
    # end (OQ-095 (2)), moved the heuristic games.)
    state = _sandworm_rewards("propaganda", 1)
    seat, round_number = _seat(state), state.round_number
    assert round_number == 9
    # The window's first row opens copy 1's two frames (group 0); its second
    # row opens copy 2's (group 2) once those are answered.
    assert [dict(f.context)["group"] for f in reversed(state.decision_stack[1:])] == [
        0,
        0,
    ]
    assert state.decision_stack[0].kind == "combat_reward_icons"
    groups: list[object] = []
    memory = Memory()
    factions = ("emperor", "spacing_guild", "bene_gesserit", "fremen")
    plans: dict[tuple[object, ...], object] = {}
    values: list[dict[str, float]] = []
    taken: list[object] = []
    while state.decision_stack and (
        state.decision_stack[-1].kind == "combat_reward_distinct_influence"
    ):
        run = _run(state, memory=memory)
        groups.append(dict(state.decision_stack[-1].context)["group"])
        app = W.app_reward_run(run)
        values.append(
            {f: app.profile.gain_influence_value(f, 1, -1, False).sum for f in factions}
        )
        action = W.combat_reward_distinct_influence(run)
        assert action is not None
        plans.update(memory.intents)
        taken.append(arg(action, "faction"))
        state = ENGINE.apply(state, action, legal_actions=run.legal).state
        state = answer_reward_windows(ENGINE, state)
    assert groups == [0, 0, 2, 2]
    key = (W.DISTINCT_INFLUENCE_INTENT, round_number, seat)
    assert set(plans) == {(*key, 0), (*key, 2)}
    assert not memory.intents
    first, second = plans[(*key, 0)], plans[(*key, 2)]
    assert isinstance(first, tuple)
    assert isinstance(second, tuple)
    assert taken == [*first, *second]
    # Copy 1: Bene Gesserit best, then Fremen; Spacing Guild and Emperor
    # below them.
    assert values[0] == pytest.approx(
        {
            "emperor": 1.485,
            "spacing_guild": 2.25,
            "bene_gesserit": 3.7125,
            "fremen": 2.5,
        }
    )
    assert first == ("bene_gesserit", "fremen")
    # Copy 2 sees copy 1's gains: Bene Gesserit at 2 is worth less and
    # Fremen at 1 more, so Fremen now leads Bene Gesserit.
    assert values[2] == pytest.approx(
        {
            "emperor": 1.485,
            "spacing_guild": 2.25,
            "bene_gesserit": 2.7,
            "fremen": 3.9625,
        }
    )
    assert second == ("fremen", "bene_gesserit")
    influence = state.players[seat].influence
    assert (influence.bene_gesserit, influence.fremen) == (3, 2)


# -- combat_reward_spy ---------------------------------------------------------------


def _spy_state() -> GameState:
    # Base seed 36, round 4: seat 1 wins Test of Loyalty with 3 spies in
    # supply; the Sardaukar and Fremkit posts value 4.0, the next ones 3.0.
    # (Seed 1, where seat 0 won Seize Spice Refinery, reached it until the
    # user ruling of 2026-10-14 -- an optional effect of the Agent turn
    # lapses at the turn's end, OQ-095 (2) -- moved the heuristic games; 36
    # is the first seed from 2 that passes both tests below.)
    return _reach("combat_reward_spy", choam=False, seed=36)


def test_reward_spy_goes_to_the_best_free_post() -> None:
    state = _spy_state()
    fremkit = "fremen-desert-tactics-fremkit"
    winner = _seat(state)
    others = [s for s in range(4) if s != winner]
    if not any(fremkit in state.players[s].spy_post_ids for s in others):
        # Another seat's Spy takes Fremkit.
        other = state.players[others[0]]
        state = with_player(
            state,
            others[0],
            spy_post_ids=(*other.spy_post_ids, fremkit),
            spies_supply=other.spies_supply - 1,
        )
    run = _run(state)
    assert fremkit not in {arg(a, "post_id") for a in run.legal}
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
    # Base seed 280: seat 0 holds Shadow Alliance (offered), and a face-up
    # Battle for Arrakeen beside Propaganda. (Seed 18, where seat 2 also held
    # an unplayable Secure Spice Trade, reached this until Imperial
    # Privilege's card draw became its own icon, 2026-10-10, OQ-027 (d),
    # which moved its game at round 8 seat 0's Imperial Privilege visit;
    # then seed 47, where seat 3 held Shadow Alliance and a crysknife
    # Objective, until Cunning's draw after its trash became its own step,
    # 2026-10-10, OQ-106, which moved its game at round 7 seat 3's Cunning;
    # then seed 61, where seat 2 held Secure Spice Trade beside an
    # unplayable Buy Access and a face-up desert mouse Objective beside
    # Propaganda, until a triggered Intrigue draw became the owner's own
    # step, 2026-10-10, OQ-106, which moved its game at round 3 seat 0's
    # trash of Sardaukar Soldier; then seed 103, until the user ruling of
    # 2026-10-14 (an optional effect of the Agent turn lapses at the turn's
    # end, OQ-095 (2)) moved the heuristic games. 280, seat 0 (Feyd-Rautha
    # Harkonnen), is the first seed from 103 that offers a play and a match
    # together and takes them in that order.)
    state = _reach("endgame_intrigue", choam=False, seed=280, want="play_and_match")
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
            {
                "matching_card_id": "battle_for_arrakeen",
                "wild_card_id": "propaganda",
            },
        ),
        ("pass_endgame_intrigue", {}),
    ]


def test_endgame_plays_secure_spice_trade() -> None:
    # CHOAM seed 20: seat 3 holds Secure Spice Trade alone. (Seed 1
    # until Imperial Privilege's card draw became its own icon, 2026-10-10,
    # OQ-027 (d), moved its game at round 4 seat 0's Imperial Privilege
    # visit; its seat now holds no Intrigue card and takes a wild match. Then
    # seed 3, where seat 2 held Secure Spice Trade and Inspire Awe, until the
    # Bene Gesserit Influence 4 card became the owner's own step, 2026-10-10,
    # OQ-106, which moved its game at round 6 seat 3's Secrets visit; then
    # seed 9, where seat 1 held it beside Mercenaries, until the user ruling
    # of 2026-10-14 (an optional effect of the Agent turn lapses at the
    # turn's end, OQ-095 (2)) moved the heuristic games; 20 is the first seed
    # from 9 whose seat plays it.)
    state = _reach("endgame_intrigue", choam=True, seed=20, want="several")
    assert _args(W.endgame_intrigue(_run(state))) == (
        "play_intrigue",
        {"card_id": "intrigue:secure_spice_trade:0", "option": 0},
    )


def test_endgame_never_takes_a_match_the_app_would_not_score() -> None:
    # Base seed 31: seat 0 holds Propaganda (wild) beside Test of Loyalty and
    # Skirmish (crysknife); the engine offers both matches, and the app's own
    # pair order takes Skirmish. (Until the 2026-10-06
    # card-comparison batch moved seed 1's game, the seat paired a crysknife
    # Objective there; until 5654d7f8 seed 1 paired Secure Imperial Basin.
    # Seed 12 then held Propaganda beside Battle for Imperial Basin and a
    # crysknife Objective until Imperial Privilege's card draw became its
    # own icon, 2026-10-10, OQ-027 (d), moved its game at round 6 seat 2's
    # Imperial Privilege visit; it now offers one match. Seed 19, where
    # seat 2 held them, followed until the user ruling of 2026-10-14 (an
    # optional effect of the Agent turn lapses at the turn's end, OQ-095
    # (2)) moved the heuristic games. 31 is the first seed from 19 with
    # exactly two matches, both for Propaganda, neither of them Battle for
    # Arrakeen.)
    state = _reach("endgame_intrigue", choam=False, seed=31, want="several")
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
        {"matching_card_id": "skirmish_crysknife", "wild_card_id": "propaganda"},
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
