"""Regression tests for ``scripts/ab/tipcensus/endgame.py``.

Plays a handful of the tournament's own games (base and full-expansion specs,
``_spec`` mirrors ``tests/unit/test_tip_census.py``) through the census driver
and checks the ``end.*`` / ``bt.*`` columns against invariants tied to the
final game state, not just "the column exists".

``tests/unit/test_tip_census.py`` documents its ``load_tip_census()`` helper
as importable via ``from tests.unit.test_tip_census import load_tip_census``
("tests/ is a package"), but ``tests/unit/`` itself has no ``__init__.py``
(only ``tests/__init__.py`` does), so pytest's default "prepend" import mode
inserts ``tests/unit`` -- not the repo root -- onto ``sys.path`` for a file
collected from there, and the dotted import raises ``ModuleNotFoundError: No
module named 'tests'`` under the plain ``uv run pytest`` invocation (it only
works under ``python -m pytest``, which adds the cwd). This module carries
its own copy of the same tiny loader instead; see the blocker note in the
work report.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.events import GameEvent
from dune_imperium.evaluation import tournament as T

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


BASE_SEEDS = (1, 2, 3)
FULL_SEEDS = (3, 4, 5)


@pytest.fixture(scope="module")
def tip_census() -> ModuleType:
    return _load_tip_census()


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


def _play_to_finished(tip_census: ModuleType, spec: T.MatchSpec) -> Any:
    """Replay ``spec`` with the driver's own loop and return the final state.

    Deterministic replica of ``tip_census.play``'s loop (same seeds, same
    agent construction), kept independent of the collectors so the final
    ``GameState`` can be cross-checked against what ``endgame.py`` counted
    from events alone.
    """

    Tmod = tip_census.T
    engine = (
        Tmod.UprisingRulesEngine(leader_ids=spec.leader_ids)
        if spec.leader_ids is not None
        else Tmod.UprisingRulesEngine()
    )
    agents = tuple(
        Tmod.make_agent(kind, spec.policy_seed + seat)
        for seat, kind in enumerate(spec.seat_agents)
    )
    searchers = tip_census._state_agents(agents)
    state = engine.reset(spec.config, spec.game_seed)
    chance = tip_census.ChanceResolver(seed=spec.game_seed)
    for _ in range(spec.max_steps):
        if state.phase is tip_census.GamePhase.FINISHED:
            return state
        decision = engine.current_decision(state)
        if isinstance(decision, tip_census.ChanceDecision):
            result = engine.apply(state, chance.resolve(decision))
        else:
            owner = decision.owner
            legal = engine.legal_actions(state, owner)
            observation = engine.observe(state, owner)
            searcher = searchers[owner]
            action = (
                searcher.choose_action_with_state(state, observation, legal)
                if searcher is not None
                else agents[owner].choose_action(observation, legal)
            )
            if action not in legal:
                action = legal[0]
            result = engine.apply(state, action, legal_actions=legal)
        state = result.state
    raise RuntimeError(f"step limit reached for seed {spec.game_seed}")


def _play_all(
    tip_census: ModuleType, full: bool, seeds: tuple[int, ...]
) -> list[dict[str, Any]]:
    return [tip_census.play(_spec(full, seed), ("endgame",)) for seed in seeds]


def _bootstrap_state(tip_census: ModuleType, spec: T.MatchSpec) -> Any:
    """A real (otherwise arbitrary) ``GameState`` for a synthetic ``Step``'s
    ``pre``/``post`` fields, for tests below whose collector code path never
    reads them (only ``owner``/``action``/``events`` matter there).
    """

    Tmod = tip_census.T
    engine = (
        Tmod.UprisingRulesEngine(leader_ids=spec.leader_ids)
        if spec.leader_ids is not None
        else Tmod.UprisingRulesEngine()
    )
    return engine.reset(spec.config, spec.game_seed)


def _vp_at_endgame_start(tip_census: ModuleType, spec: T.MatchSpec) -> list[int]:
    """Independently replay ``spec`` and read VP off the ``endgame_started`` step.

    Mirrors ``tip_census.play``'s loop (not ``EndgameCollector``) so the
    check below does not just restate the collector's own bookkeeping.
    """

    Tmod = tip_census.T
    engine = (
        Tmod.UprisingRulesEngine(leader_ids=spec.leader_ids)
        if spec.leader_ids is not None
        else Tmod.UprisingRulesEngine()
    )
    agents = tuple(
        Tmod.make_agent(kind, spec.policy_seed + seat)
        for seat, kind in enumerate(spec.seat_agents)
    )
    searchers = tip_census._state_agents(agents)
    state = engine.reset(spec.config, spec.game_seed)
    chance = tip_census.ChanceResolver(seed=spec.game_seed)
    for _ in range(spec.max_steps):
        if state.phase is tip_census.GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if isinstance(decision, tip_census.ChanceDecision):
            result = engine.apply(state, chance.resolve(decision))
        else:
            owner = decision.owner
            legal = engine.legal_actions(state, owner)
            observation = engine.observe(state, owner)
            searcher = searchers[owner]
            action = (
                searcher.choose_action_with_state(state, observation, legal)
                if searcher is not None
                else agents[owner].choose_action(observation, legal)
            )
            if action not in legal:
                action = legal[0]
            result = engine.apply(state, action, legal_actions=legal)
        if any(event.kind == "endgame_started" for event in result.events):
            return [player.victory_points for player in result.state.players]
        state = result.state
    raise RuntimeError(f"endgame_started never fired for seed {spec.game_seed}")


def test_end_columns_present_with_expected_types(tip_census: ModuleType) -> None:
    for census in _play_all(tip_census, False, BASE_SEEDS[:1]):
        game = census["game"]
        for key in ("end.endgame_round", "end.trigger_vp", "end.trigger_deck"):
            assert key in game, key
        assert isinstance(game["end.leader_changed"], bool)
        for seat in census["seats"]:
            for key in (
                "end.endgame_vp",
                "end.endgame_intrigue_plays",
                "end.plot_icon_plays",
                "end.plot_icon_plays_flippable",
                "end.plot_icon_plays_last_round",
                "end.pass_endgame_with_play",
            ):
                assert key in seat, key
                assert isinstance(seat[key], int)


@pytest.mark.parametrize("full", [False, True])
def test_endgame_round_matches_final_round_and_trigger_fires(
    tip_census: ModuleType, full: bool
) -> None:
    seeds = FULL_SEEDS if full else BASE_SEEDS
    for census in _play_all(tip_census, full, seeds):
        game = census["game"]
        # Endgame opens in the round it opens in: round_number never
        # advances again once Endgame has started (rules/phases.py
        # ``begin_round`` is the only place it increments, and Endgame
        # skips straight to Round Start -> ... -> Endgame instead).
        assert game["end.endgame_round"] == game["rounds"]
        # "Endgame이 시작되면" [Main p. 15]: at least one of the two printed
        # conditions must have held.
        assert game["end.trigger_vp"] or game["end.trigger_deck"]


@pytest.mark.parametrize("full", [False, True])
def test_plot_icon_play_columns_are_consistent_subsets(
    tip_census: ModuleType, full: bool
) -> None:
    seeds = FULL_SEEDS if full else BASE_SEEDS
    for census in _play_all(tip_census, full, seeds):
        for seat in census["seats"]:
            plays = seat["end.plot_icon_plays"]
            assert 0 <= seat["end.plot_icon_plays_flippable"] <= plays
            assert 0 <= seat["end.plot_icon_plays_last_round"] <= plays
            assert seat["end.endgame_intrigue_plays"] >= 0
            assert seat["end.pass_endgame_with_play"] >= 0


def test_bt_columns_are_none_without_bloodlines_or_tech(tip_census: ModuleType) -> None:
    for census in _play_all(tip_census, False, BASE_SEEDS):
        for seat in census["seats"]:
            for key in (
                "bt.commanders_acquired",
                "bt.commanders_recruited_paid",
                "bt.commander_retreats",
                "bt.commanders_deployed",
                "bt.skill_reveal_bonuses",
                "bt.tech_acquired",
                "bt.tech_spice",
                "bt.tech_trashed",
                "bt.fw_strength",
                "bt.fw_trash",
                "bt.fw_influence_lost",
                "bt.ada_spies_trashed",
            ):
                assert seat[key] is None, key


def test_bt_columns_are_ints_with_bloodlines_and_tech(tip_census: ModuleType) -> None:
    totals: dict[str, int] = {}
    for census in _play_all(tip_census, True, FULL_SEEDS):
        for seat in census["seats"]:
            for key in (
                "bt.commanders_acquired",
                "bt.commanders_recruited_paid",
                "bt.commander_retreats",
                "bt.commanders_deployed",
                "bt.skill_reveal_bonuses",
                "bt.tech_acquired",
                "bt.tech_spice",
                "bt.tech_trashed",
                "bt.fw_strength",
                "bt.fw_trash",
                "bt.fw_influence_lost",
                "bt.ada_spies_trashed",
            ):
                assert isinstance(seat[key], int), key
                totals[key] = totals.get(key, 0) + seat[key]
            # A tile can only be trashed if it (or an earlier copy this seat
            # held) was acquired first.
            assert seat["bt.tech_trashed"] <= seat["bt.tech_acquired"]
            # Advanced Data Analysis trashes exactly one Spy per acquisition
            # of it, so this seat cannot have trashed more Spies than it
            # acquired tiles overall.
            assert seat["bt.ada_spies_trashed"] <= seat["bt.tech_acquired"]
            assert seat["bt.tech_spice"] >= 0
    # With three full-expansion heuristic games, Commanders and Tech tiles
    # should show real activity somewhere (guards against a counter that
    # never fires).
    assert totals["bt.commanders_acquired"] > 0
    assert totals["bt.tech_acquired"] > 0


def test_tech_acquired_matches_final_tech_ids_plus_trashed(
    tip_census: ModuleType,
) -> None:
    for seed in FULL_SEEDS:
        spec = _spec(True, seed)
        census = tip_census.play(spec, ("endgame",))
        final = _play_to_finished(tip_census, spec)
        for seat_row, player in zip(census["seats"], final.players, strict=True):
            acquired = seat_row["bt.tech_acquired"]
            trashed = seat_row["bt.tech_trashed"]
            assert acquired == len(player.tech_ids) + trashed


def test_commanders_acquired_matches_final_commander_total(
    tip_census: ModuleType,
) -> None:
    for seed in FULL_SEEDS:
        spec = _spec(True, seed)
        census = tip_census.play(spec, ("endgame",))
        final = _play_to_finished(tip_census, spec)
        for seat_row, player in zip(census["seats"], final.players, strict=True):
            # A Sardaukar Commander cycles between supply, garrison and
            # Conflict but, once acquired from the bank, never leaves its
            # owner or the game [Bloodlines p. 4]: the total is conserved.
            assert player.commanders_total == seat_row["bt.commanders_acquired"]


def test_endgame_vp_matches_final_vp_minus_vp_at_start(
    tip_census: ModuleType,
) -> None:
    for seed in BASE_SEEDS:
        spec = _spec(False, seed)
        vp_at_start = _vp_at_endgame_start(tip_census, spec)
        census = tip_census.play(_spec(False, seed), ("endgame",))
        for seat, seat_vp_start in zip(census["seats"], vp_at_start, strict=True):
            assert seat["vp"] - seat["end.endgame_vp"] == seat_vp_start


def test_endgame_vp_leader_and_trigger_vp_match_the_round_end_check_state(
    tip_census: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: the Endgame-start snapshot must be the state the round-end
    check itself saw, not the state after Tech's Endgame-opening effects.

    "플레이어 중 누구라도 Score track에서 Victory Point 10 이상이거나 Conflict
    Deck이 비어 있으면 Endgame을 시작한다" [Main p. 15] is evaluated in
    ``rules/phases.py`` ``resolve_recall_or_endgame`` against its ``state``
    argument -- before that function builds the phase=ENDGAME state or runs
    ``apply_endgame_tech_effects`` (CHOAM Transports, Panopticon -- OQ-040).
    This monkeypatches the engine's own call site
    (``dune_imperium.rules.engine`` imports the function by name, so patching
    it there redirects every call) to capture that exact argument -- an
    oracle independent of ``EndgameCollector``'s own Tech-VP-subtraction
    logic -- and checks ``end.trigger_vp``, ``end.leader_changed`` and
    ``end.endgame_vp`` against it.

    A code-review finding proved this wrong at seed 23 (full): the buggy
    collector read ``end.endgame_vp`` == 1 for seat 3 and ``end.leader_changed``
    == False there, both because Panopticon's Endgame-opening Influence gain
    (1 -> 2, +1 VP each -- ``rules/influence.py`` line 46) was already folded
    into the snapshot it took.

    Seed 23's game changed with the 2026-09-25 Storms in the South
    correction (its first divergence is that card's first-place Spy with
    Deep Cover) and no longer changes the leader, so the case moved to seed
    45. Re-pinned 2026-09-26 for the card-transcription audit's rules fixes
    (codec v108): seed 45 now diverges at seat 2's round-3 Reveal buy
    (Sardaukar Coordination, whose Reveal was corrected) and its Panopticon
    holder already leads at the check, so the case is seed 29 (full), the
    first of five seeds in 1-200 (29, 39, 63, 128, 130) where the
    Endgame-opening Tech alone changes the leader, checked against the state
    the check saw and the ``:endgame_tech:`` events. There seat 1 (Lady Amber
    Metulli) holds Panopticon and is tied with seat 0 on 7 VP at the check
    (seat 0 ranked first); of its Spacing Guild 0 -> 1 and Fremen 1 -> 2
    gains only the Fremen step scores, making it 8. The buggy collector would
    read ``end.endgame_vp`` == 0 for seat 1 and ``end.leader_changed`` ==
    False.
    """

    import dune_imperium.rules.engine as rules_engine
    from dune_imperium.rules.endgame import final_standings as real_final_standings
    from dune_imperium.rules.phases import resolve_recall_or_endgame as real_resolve

    saw_seed_29 = False
    for seed in (*FULL_SEEDS, 29):
        spec = _spec(True, seed)
        captured: list[Any] = []

        def wrapper(state: Any, _captured: list[Any] = captured) -> Any:
            _captured.append(state)
            return real_resolve(state)

        monkeypatch.setattr(rules_engine, "resolve_recall_or_endgame", wrapper)
        census = tip_census.play(spec, ("endgame",))

        assert captured, "resolve_recall_or_endgame was never called"
        # resolve_recall_or_endgame runs at every round's end; the one that
        # actually opens Endgame is the last call this game made (no further
        # round can follow it).
        checked_state = captured[-1]
        assert checked_state.phase is tip_census.GamePhase.RECALL_OR_ENDGAME
        assert not checked_state.conflict_deck or any(
            player.victory_points >= 10 for player in checked_state.players
        )
        at_check = replace(checked_state, phase=tip_census.GamePhase.ENDGAME)

        assert census["game"]["end.trigger_vp"] == any(
            player.victory_points >= 10 for player in at_check.players
        )
        winner = next(s["seat"] for s in census["seats"] if s["rank"] == 1)
        leader_at_check = next(
            standing.player
            for standing in real_final_standings(at_check)
            if standing.rank == 1
        )
        assert census["game"]["end.leader_changed"] == (winner != leader_at_check)
        for seat, player in zip(census["seats"], at_check.players, strict=True):
            assert seat["vp"] - seat["end.endgame_vp"] == player.victory_points

        if seed == 29:
            saw_seed_29 = True
            assert census["seats"][1]["end.endgame_vp"] == 1
            assert census["game"]["end.leader_changed"] is True

    assert saw_seed_29, "the seed 29 regression case must run"


def test_commander_retreats_excludes_conflict_losses_and_opponent_forced_retreats(
    tip_census: ModuleType,
) -> None:
    """A Commander LOST from the Conflict, or retreated there by an
    opponent's card, is not a "retreat and reuse" (tip C7.2).

    ``lose_unit`` (unit_loss.py) sends a lost Commander through
    ``retreat_units`` first with a ``<source>:loss`` step_source, so its
    event id always ends ``:loss:retreat``. ``retreat_opponent_troop``
    (agent_effects.py) also calls ``retreat_units``, on the *target* seat,
    with a ``<source>:opponent:<target>`` step_source. Neither is this
    seat's own choice to retreat a Commander for later reuse; only the third,
    ordinary event here (a Skill/Intrigue/Leader-ability retreat) should
    count.
    """

    endgame_module = importlib.import_module("tipcensus.endgame")
    spec = _spec(True, 3)
    state = _bootstrap_state(tip_census, spec)
    collector = endgame_module.BloodlinesTechCollector(spec, 4)
    events = (
        # Gruesome Sacrifice's cost (lose_intrigue_troop -> lose_unit):
        # seat 0 pays a Commander from the Conflict -- a loss, not a retreat.
        GameEvent(
            event_id=(
                "round:4:player:0:agent_card:gruesome_sacrifice:0:slot:1:loss:retreat"
            ),
            kind="troops_retreated",
            payload=(("commanders", 1), ("count", 1), ("player", 0)),
        ),
        # Seat 1's card forces seat 2 to retreat a Commander -- seat 2 did
        # not choose this.
        GameEvent(
            event_id="round:4:player:1:agent_card:force_retreat:opponent:2:retreat",
            kind="troops_retreated",
            payload=(("commanders", 1), ("count", 1), ("player", 2)),
        ),
        # Seat 3's own Skill retreats its own Commander by choice.
        GameEvent(
            event_id="round:4:player:3:skill:driven:retreat",
            kind="troops_retreated",
            payload=(("commanders", 1), ("count", 1), ("player", 3)),
        ),
    )
    collector.step(endgame_module.Step(state, state, None, None, (), events))
    per_seat, _ = collector.finish(state, ())
    assert per_seat[0]["commander_retreats"] == 0
    assert per_seat[2]["commander_retreats"] == 0
    assert per_seat[3]["commander_retreats"] == 1


def test_commander_retreats_excludes_a_real_gruesome_sacrifice_loss(
    tip_census: ModuleType,
) -> None:
    """Regression for the code-review finding: full seed 3, seat 0, round 4
    pays a Sardaukar Commander to Gruesome Sacrifice's Intrigue cost, which
    is a Conflict loss (unit_loss.py), not a "retreat and reuse" (C7.2).
    """

    census = tip_census.play(_spec(True, 3), ("endgame",))
    assert census["seats"][0]["bt.commander_retreats"] == 0


def test_commander_retreats_counts_the_reveal_two_troop_retreat_choice(
    tip_census: ModuleType,
) -> None:
    """Chani / Clever Tactician / Command Center's "retreat two troops"
    Reveal choice can move 1 or 2 Commanders to the garrison, but its
    ``troops_retreated`` event carries no ``commanders`` payload key
    (reveal_turn.py lines ~980-984) -- the collector must read it off the
    chosen action's own ``commanders`` argument instead.
    """

    endgame_module = importlib.import_module("tipcensus.endgame")
    spec = _spec(True, 3)
    state = _bootstrap_state(tip_census, spec)
    collector = endgame_module.BloodlinesTechCollector(spec, 4)
    with_commander = DomainAction(
        action_id="retreat_two_troops_for_reveal",
        actor=1,
        arguments=(("commanders", 1),),
    )
    without_commander = DomainAction(
        action_id="retreat_two_troops_for_reveal", actor=2, arguments=()
    )
    event = GameEvent(
        event_id="round:4:player:1:reveal:x:troops_retreated",
        kind="troops_retreated",
        payload=(("count", 2), ("player", 1)),
    )
    collector.step(endgame_module.Step(state, state, 1, with_commander, (), (event,)))
    collector.step(endgame_module.Step(state, state, 2, without_commander, (), ()))
    per_seat, _ = collector.finish(state, ())
    assert per_seat[1]["commander_retreats"] == 1
    assert per_seat[2]["commander_retreats"] == 0


def test_commanders_deployed_nets_a_same_turn_withdrawal(
    tip_census: ModuleType,
) -> None:
    """``apply_commander_withdrawal`` (combat_deployment.py) moves Commanders
    deployed *this* Agent turn back to the garrison before Combat resolves,
    so they never fought; ``commanders_deployed`` must net that out rather
    than count the original deployment alone.
    """

    endgame_module = importlib.import_module("tipcensus.endgame")
    spec = _spec(True, 3)
    state = _bootstrap_state(tip_census, spec)
    collector = endgame_module.BloodlinesTechCollector(spec, 4)
    deploy = GameEvent(
        event_id="round:1:player:0:deploy_commanders:2",
        kind="commanders_deployed",
        payload=(("count", 2), ("player", 0)),
    )
    withdraw = GameEvent(
        event_id="round:1:player:0:withdraw_commanders:1",
        kind="commanders_withdrawn",
        payload=(("count", 1), ("player", 0)),
    )
    collector.step(endgame_module.Step(state, state, 0, None, (), (deploy,)))
    collector.step(endgame_module.Step(state, state, 0, None, (), (withdraw,)))
    per_seat, _ = collector.finish(state, ())
    assert per_seat[0]["commanders_deployed"] == 1
