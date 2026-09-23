"""Regression tests for ``tipcensus.combat`` (the Combat tip census columns).

``tests/unit/test_tip_census.py`` documents its ``load_tip_census()`` helper
as importable via ``from tests.unit.test_tip_census import load_tip_census``
("tests/ is a package"), but ``tests/unit/`` itself has no ``__init__.py``
(only ``tests/__init__.py`` does), so pytest's default "prepend" import mode
inserts ``tests/unit`` -- not the repo root -- onto ``sys.path`` for a file
collected from there, and the dotted import raises ``ModuleNotFoundError:
No module named 'tests'`` under the plain ``uv run pytest`` invocation (it
only works under ``python -m pytest``, which adds the cwd). This module
carries its own copy of the same tiny loader instead of depending on that
import; see the blocker note in the work report.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from dune_imperium.agents.registry import make_agent
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.types import ConflictTier
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.evaluation import tournament as T
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.combat import rank_combat
from dune_imperium.rules.endgame import final_standings

_TOOL = Path(__file__).resolve().parents[2] / "scripts" / "ab" / "tip_census.py"


def _load_tip_census() -> ModuleType:
    """Import ``scripts/ab/tip_census.py`` (it puts ``scripts/ab`` on sys.path)."""

    if "tip_census" in sys.modules:
        return sys.modules["tip_census"]
    spec = importlib.util.spec_from_file_location("tip_census", _TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tip_census"] = module
    spec.loader.exec_module(module)
    return module


_tip_census: ModuleType = _load_tip_census()  # also puts scripts/ab on sys.path

# mypy has no visibility into the sys.path insertion above (it happens at
# runtime, inside the loaded tip_census module), so these two are unresolved
# imports from its perspective even though they succeed at test time.
from tipcensus.base import Step  # type: ignore[import-not-found]  # noqa: E402
from tipcensus.combat import (  # type: ignore[import-not-found]  # noqa: E402
    COLLECTORS,
    CombatCollector,
)


def _avg(values: list[int]) -> float | None:
    """Arithmetic mean of ``values``, or None for "mean over zero items" --
    an independent copy of ``tipcensus.combat._mean`` so a broken mean in the
    module under test cannot also break its own regression check."""

    return sum(values) / len(values) if values else None


def _spec(full: bool, seed: int) -> T.MatchSpec:
    return T.tournament_specs(
        agents=("heuristic",),
        games=1,
        rulesets=(full,),
        start_seed=seed,
        rotate_leaders=True,
        bloodlines=full,
        tech_module=full,
        immortality=full,
    )[0]


def _conflict_snapshot(state: GameState) -> dict[str, Any]:
    """Read one Conflict's unit/strength snapshot straight off ``state``,
    independently of ``CombatCollector._record_conflict`` /
    ``_record_missing_conflict``, for a field-by-field cross-check."""

    return {
        "conflict_id": state.current_conflict_ids[-1],
        "round": state.round_number,
        "troops": [p.troops_conflict for p in state.players],
        "sandworms": [p.sandworms_conflict for p in state.players],
        "commanders": [p.commanders_conflict for p in state.players],
        "agents": [p.agent_in_conflict for p in state.players],
        "strength": [p.combat_strength for p in state.players],
        "garrison": [p.troops_garrison for p in state.players],
    }


@dataclass
class GroundTruth:
    """Engine-observed counters built independently of ``CombatCollector``,
    for comparing its columns to something other than its own bookkeeping."""

    conflict_won_events: int = 0
    combat_cleaned_up_events: int = 0
    # Per-seat total of positive sandworms_conflict deltas on steps that do
    # not clean up a Conflict (cleanup zeroes the field, which is a decrease,
    # not a summon) -- independent of which event kind caused the increase.
    worms_summoned: list[int] = field(default_factory=lambda: [0] * 4)
    # One entry per Conflict resolution, in order, mirroring self._conflicts'
    # bookkeeping of *when* to snapshot (combat_intrigue_finished, or a
    # combat_cleaned_up with no prior snapshot this cycle) but reading the
    # snapshot itself straight off state, not through the collector.
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    # Agent-turn-onto-a-Combat-space visits, read straight off state.
    garrison_visits: list[list[int]] = field(
        default_factory=lambda: [[] for _ in range(4)]
    )
    garrison_tier3_visits: list[list[int]] = field(
        default_factory=lambda: [[] for _ in range(4)]
    )
    heighliner_visits: list[int] = field(default_factory=lambda: [0] * 4)


def _play_with_ground_truth(
    spec: T.MatchSpec,
) -> tuple[list[dict[str, Any]], dict[str, Any], GameState, GroundTruth]:
    """Replay one game like ``tip_census.play`` but also keep the final
    ``GameState`` and a ``GroundTruth`` built from the raw engine steps,
    neither of which the driver's ``play()`` exposes, so the invariants below
    can compare the collector's own bookkeeping to engine ground truth rather
    than only to itself."""

    config = spec.config
    engine = (
        UprisingRulesEngine(leader_ids=spec.leader_ids)
        if spec.leader_ids is not None
        else UprisingRulesEngine()
    )
    agents = tuple(
        make_agent(kind, spec.policy_seed + seat)
        for seat, kind in enumerate(spec.seat_agents)
    )
    seats = len(spec.seat_agents)
    collector = CombatCollector(spec, seats)
    state = engine.reset(config, spec.game_seed)
    chance = ChanceResolver(seed=spec.game_seed)
    gt = GroundTruth()
    gt_recorded = True  # mirrors CombatCollector._recorded
    for _ in range(spec.max_steps):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if decision is None:
            raise RuntimeError("an unfinished game must always have a decision")
        if isinstance(decision, ChanceDecision):
            result = engine.apply(state, chance.resolve(decision))
            step = Step(state, result.state, None, None, (), tuple(result.events))
        else:
            owner = decision.owner
            legal = engine.legal_actions(state, owner)
            observation = engine.observe(state, owner)
            action = agents[owner].choose_action(observation, legal)
            if action not in legal:
                action = legal[0]
            result = engine.apply(state, action, legal_actions=legal)
            step = Step(state, result.state, owner, action, legal, tuple(result.events))

        for event in step.events:
            kind = event.kind
            if kind == "conflict_won":
                gt.conflict_won_events += 1
            elif kind == "combat_intrigue_finished":
                gt.conflicts.append(_conflict_snapshot(step.pre))
                gt_recorded = True
            elif kind == "combat_cleaned_up":
                gt.combat_cleaned_up_events += 1
                if not gt_recorded:
                    gt.conflicts.append(_conflict_snapshot(step.pre))
                gt_recorded = False

        # combat_reward_gained is always in the same step as the
        # combat_intrigue_finished that precedes it (tipcensus.combat's
        # module docstring), so step.pre is the exact state the engine's own
        # rank_combat ran against; recomputing it here and comparing to the
        # emitted events checks C2.1's "reward auction" independently of
        # anything CombatCollector does with those same events.
        reward_events = [e for e in step.events if e.kind == "combat_reward_gained"]
        if reward_events:
            ranking = rank_combat(step.pre.players, first_player=step.pre.first_player)
            expected = {
                reward.player: (int(reward.rank), reward.multiplier)
                for reward in ranking.rewards
            }
            actual = {
                int(dict(e.payload)["player"]): (
                    int(dict(e.payload)["rank"]),
                    int(dict(e.payload)["multiplier"]),
                )
                for e in reward_events
            }
            assert actual == expected

        if not any(e.kind == "combat_cleaned_up" for e in step.events):
            for seat_index in range(seats):
                delta = (
                    step.post.players[seat_index].sandworms_conflict
                    - step.pre.players[seat_index].sandworms_conflict
                )
                if delta > 0:
                    gt.worms_summoned[seat_index] += delta

        if (
            step.owner is not None
            and step.action is not None
            and step.action.action_id == "agent_turn"
        ):
            space_id = dict(step.action.arguments).get("space_id")
            if isinstance(space_id, str):
                space = BOARD_SPACES_BY_ID.get(space_id)
                if space is not None and space.combat:
                    garrison = step.pre.players[step.owner].troops_garrison
                    gt.garrison_visits[step.owner].append(garrison)
                    current_conflict_ids = step.pre.current_conflict_ids
                    if current_conflict_ids:
                        conflict = CONFLICTS_BY_ID.get(current_conflict_ids[-1])
                        if conflict is not None and conflict.tier is ConflictTier.THREE:
                            gt.garrison_tier3_visits[step.owner].append(garrison)
                    if space_id == "heighliner":
                        gt.heighliner_visits[step.owner] += 1

        collector.step(step)
        state = result.state
    else:
        raise RuntimeError(f"step limit reached for seed {spec.game_seed}")
    standings = final_standings(state)
    per_seat, game = collector.finish(state, standings)
    return per_seat, game, state, gt


def _expected_from_conflicts(
    conflicts: Sequence[dict[str, Any]], seats: int
) -> list[dict[str, Any]]:
    """Recompute ``CombatCollector.finish()``'s per-seat aggregates directly
    from the raw per-Conflict rows, in a second, independently written pass,
    so a wrong aggregation formula in ``finish()`` does not go uncaught."""

    expected: list[dict[str, Any]] = []
    for seat in range(seats):
        entered = won = unopposed_wins = 0
        one_unit_entries = one_unit_rewarded = 0
        worm_entries = worm_not_first = doubled_rewards = 0
        intrigue_flip_won = intrigue_flip_lost = 0
        win_margins: list[int] = []
        excess_troops: list[int] = []
        for c in conflicts:
            troops = c["troops"][seat]
            worms = c["sandworms"][seat]
            commanders = c["commanders"][seat]
            agents = c["agents"][seat]
            units = troops + worms + commanders + agents
            is_winner = c["winner"] == seat
            rank = c["rank"][seat]
            if c["multiplier"][seat] == 2:
                doubled_rewards += 1
            if units >= 1:
                entered += 1
                if units == 1:
                    one_unit_entries += 1
                    if rank in (2, 3):
                        one_unit_rewarded += 1
                if worms >= 1:
                    worm_entries += 1
                    if not is_winner:
                        worm_not_first += 1
            if is_winner:
                won += 1
                others = [c["strength"][i] for i in range(seats) if i != seat]
                if max(others) == 0:
                    unopposed_wins += 1
                if c["margin"] is not None:
                    win_margins.append(c["margin"])
                    bound = max(0, (c["margin"] - 1) // 2)
                    floor = 1 if worms + commanders + agents == 0 and troops > 0 else 0
                    excess_troops.append(min(troops - floor, bound))
            pre = c["pre_intrigue_strength"]
            top = max(pre)
            leaders = [i for i, value in enumerate(pre) if value == top]
            strict_leader = leaders[0] if len(leaders) == 1 else None
            if is_winner and strict_leader != seat:
                intrigue_flip_won += 1
            if strict_leader == seat and not is_winner:
                intrigue_flip_lost += 1
        expected.append(
            {
                "entered": entered,
                "won": won,
                "unopposed_wins": unopposed_wins,
                "win_margin": _avg(win_margins),
                "excess_troops": _avg(excess_troops),
                "one_unit_entries": one_unit_entries,
                "one_unit_rewarded": one_unit_rewarded,
                "worm_entries": worm_entries,
                "worm_not_first": worm_not_first,
                "doubled_rewards": doubled_rewards,
                "intrigue_flip_won": intrigue_flip_won,
                "intrigue_flip_lost": intrigue_flip_lost,
            }
        )
    return expected


def test_every_collector_class_is_unique_and_named_combat() -> None:
    names = [cls.name for cls in COLLECTORS]
    assert names == ["combat"]


@pytest.mark.parametrize("full", [False, True])
def test_combat_columns_tie_to_the_engine_ground_truth(full: bool) -> None:
    spec = _spec(full, seed=3)
    per_seat, game, state, gt = _play_with_ground_truth(spec)
    conflicts: Sequence[dict[str, Any]] = game["conflicts"]

    # len(conflicts) equals the number of Conflicts resolved: one
    # combat_cleaned_up event (finish_combat, combat.py:1347) per Conflict,
    # win or not, whether or not Combat Intrigue ever emitted its own event.
    assert len(conflicts) == gt.combat_cleaned_up_events

    resolved_with_winner = sum(1 for c in conflicts if c["winner"] is not None)
    won_conflict_ids_total = sum(len(p.won_conflict_ids) for p in state.players)
    # sum over seats of won == number of conflict_won events == sum of
    # len(won_conflict_ids).
    assert resolved_with_winner == gt.conflict_won_events == won_conflict_ids_total
    assert sum(seat["won"] for seat in per_seat) == won_conflict_ids_total
    assert game["conflicts_no_winner"] == len(conflicts) - resolved_with_winner

    # Field-by-field: the collector's own snapshot of each Conflict matches
    # one read straight off the engine state at the same step.
    assert len(gt.conflicts) == len(conflicts)
    for expected, actual in zip(gt.conflicts, conflicts, strict=True):
        for key in (
            "conflict_id",
            "round",
            "troops",
            "sandworms",
            "commanders",
            "agents",
            "strength",
            "garrison",
        ):
            assert expected[key] == actual[key], key

    # The per-seat aggregates in finish() match a second, independent
    # computation from the raw per-Conflict rows.
    expected_seats = _expected_from_conflicts(conflicts, seats=4)
    for seat_index, (expected, actual) in enumerate(
        zip(expected_seats, per_seat, strict=True)
    ):
        for key, value in expected.items():
            assert actual[key] == value, (seat_index, key)

    for seat_index, seat in enumerate(per_seat):
        # Tied to the actual PlayerState field, not just to this module's
        # own bookkeeping.
        assert seat["won"] == len(state.players[seat_index].won_conflict_ids)
        assert seat["won"] <= seat["entered"]
        if seat["doubled_rewards"] > 0:
            assert seat["worm_entries"] > 0
        if seat["worm_entries"] > 0:
            assert seat["worms_summoned"] > 0
        # Tied to the engine's own sandworms_conflict deltas, not just to
        # which event kinds this module happens to watch for.
        assert seat["worms_summoned"] == gt.worms_summoned[seat_index]
        assert seat["heighliner_visits"] == gt.heighliner_visits[seat_index]
        assert seat["garrison_combat_visit"] == _avg(gt.garrison_visits[seat_index])
        assert seat["garrison_tier3_visit"] == _avg(
            gt.garrison_tier3_visits[seat_index]
        )
        assert seat["dropped_wall"] == (game["wall_dropper"] == seat_index)

    for c in conflicts:
        winner = c["winner"]
        strengths = c["strength"]
        if winner is not None:
            others = [strengths[i] for i in range(4) if i != winner]
            # Strictly the highest strength among all four seats, and the
            # margin is measured against the *best* other seat, not any
            # other one [Main p. 14] ("the reward auction").
            assert all(strengths[winner] > other for other in others)
            assert c["margin"] == strengths[winner] - max(others)
        else:
            assert c["margin"] is None
        for seat_index in range(4):
            if c["multiplier"][seat_index] == 2:
                # A doubled reward requires that seat's own sandworm
                # [Main p. 14].
                assert c["sandworms"][seat_index] > 0
        assert len(c["pre_intrigue_strength"]) == 4

    assert (game["wall_fall_round"] is None) == (game["wall_dropper"] is None)
    if game["wall_fall_round"] is not None:
        assert 1 <= game["wall_fall_round"] <= state.round_number
        assert sum(seat["dropped_wall"] for seat in per_seat) == 1


def test_a_conflict_nobody_entered_is_still_recorded() -> None:
    """Regression for the empty-Conflict miss (issue: combat.conflicts /
    combat.conflicts_no_winner drop a Conflict nobody entered). Every seat is
    forced to take a Reveal turn at its very first turn decision of round 1,
    so nobody ever places an Agent turn and round 1's Conflict has zero
    participants: begin_combat_intrigue then emits combat_intrigue_finished
    at once (combat.py ~137-146), inside the same apply() as the last seat's
    finish_reveal (the one that flips state.phase to COMBAT), so the *Step*'s
    pre.phase is still PLAYER_TURNS even though the Conflict did finish
    Combat Intrigue. Forced game per the reviewer's own reproduction:
    heuristic, base ruleset, start seed 3."""

    spec = _spec(False, seed=3)
    config = spec.config
    engine = UprisingRulesEngine()
    agents = tuple(
        make_agent(kind, spec.policy_seed + seat)
        for seat, kind in enumerate(spec.seat_agents)
    )
    seats = len(spec.seat_agents)
    collector = CombatCollector(spec, seats)
    state = engine.reset(config, spec.game_seed)
    chance = ChanceResolver(seed=spec.game_seed)
    saw_empty_conflict_step = False
    for _ in range(spec.max_steps):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        assert decision is not None
        if isinstance(decision, ChanceDecision):
            result = engine.apply(state, chance.resolve(decision))
            step = Step(state, result.state, None, None, (), tuple(result.events))
        else:
            owner = decision.owner
            legal = engine.legal_actions(state, owner)
            if state.round_number == 1 and state.phase is GamePhase.PLAYER_TURNS:
                # Force the Reveal choice the instant it is offered, so this
                # seat never places an Agent turn in round 1.
                forced = next((a for a in legal if a.action_id == "reveal_turn"), None)
                action = forced if forced is not None else legal[0]
            else:
                observation = engine.observe(state, owner)
                action = agents[owner].choose_action(observation, legal)
                if action not in legal:
                    action = legal[0]
            result = engine.apply(state, action, legal_actions=legal)
            step = Step(state, result.state, owner, action, legal, tuple(result.events))
        if step.pre.round_number == 1 and any(
            e.kind == "combat_intrigue_finished" for e in step.events
        ):
            saw_empty_conflict_step = True
            # Confirm the forcing actually produced zero participants, not
            # just that the event fired.
            for player in step.pre.players:
                assert player.units_in_conflict == 0
        collector.step(step)
        state = result.state
    else:
        raise RuntimeError(f"step limit reached for seed {spec.game_seed}")
    assert saw_empty_conflict_step

    standings = final_standings(state)
    per_seat, game = collector.finish(state, standings)
    conflicts: Sequence[dict[str, Any]] = game["conflicts"]
    assert len(conflicts) >= 1
    round_one = conflicts[0]
    assert round_one["round"] == 1
    assert round_one["winner"] is None
    assert round_one["strength"] == [0, 0, 0, 0]
    assert round_one["troops"] == [0, 0, 0, 0]
    assert game["conflicts_no_winner"] >= 1
    # Nobody entered round 1's Conflict, so it must not count toward any
    # seat's "entered".
    assert all(seat["entered"] < len(conflicts) for seat in per_seat)


@pytest.mark.parametrize("full", [False, True])
def test_the_driver_wires_the_combat_collector(full: bool) -> None:
    spec = _spec(full, seed=11)
    result = _tip_census.play(spec, ("combat",))
    for seat in result["seats"]:
        assert seat["combat.won"] <= seat["combat.entered"]
        assert isinstance(seat["combat.entered"], int)
        assert isinstance(seat["combat.worms_summoned"], int)
        assert isinstance(seat["combat.dropped_wall"], bool)
    game = result["game"]
    assert isinstance(game["combat.conflicts"], list)
    assert game["combat.conflicts_no_winner"] >= 0
    assert game["combat.conflicts_no_winner"] <= len(game["combat.conflicts"])
