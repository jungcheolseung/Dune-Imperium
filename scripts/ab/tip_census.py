"""Tip census: play tournament games and record per-seat tip statistics.

Players' strategy tips (docs/player-tips-for-training.md, the community list in
docs/evaluation/community-tips-2026-09-22.md) are hypotheses. This tool plays
the tournament's own specs -- same seeds, Leaders and seat rotations as
``dune-imperium-tournament`` and the A/B cells -- and, at every transition,
feeds the collectors in ``scripts/ab/tipcensus/``. It writes one JSONL line per
game (seat rows + game columns) and a summary table per agent kind, with the
winners' mean beside the all-seats mean.

The same command runs any registry kind, so the trained policy's numbers come
from the Mac mini with a ``checkpoint:<path>`` lineup:

    uv run python scripts/ab/tip_census.py --agents heuristic --games 40 \\
        --ruleset choam --bloodlines --tech-module --immortality \\
        --out ab-runs/tips/heuristic-usual
    uv run python scripts/ab/tip_census.py \\
        --agents checkpoint:checkpoints/2026-09-22/exploit/champion-5081.pt \\
        --games 40 --ruleset choam --bloodlines --tech-module --immortality \\
        --promo-cards --out ab-runs/tips/5081-train

A census is correlational: a column that moves with winning is a lead to test
by intervention (a heuristic variant or a policy override A/B), never a cause
(docs/lessons.md 2026-09-11).
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tipcensus import COLLECTOR_MODULES  # noqa: E402
from tipcensus.base import Collector, Step  # noqa: E402

from dune_imperium.core.chance import ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import ChanceDecision  # noqa: E402
from dune_imperium.core.state import GamePhase  # noqa: E402
from dune_imperium.evaluation import tournament as T  # noqa: E402
from dune_imperium.rules.endgame import final_standings  # noqa: E402
from dune_imperium.simulation.runner import _state_agents  # noqa: E402


def collector_classes(names: Iterable[str] = ()) -> tuple[type[Collector], ...]:
    """Collectors of the named modules (every module when ``names`` is empty)."""

    wanted = tuple(names) or COLLECTOR_MODULES
    unknown = set(wanted) - set(COLLECTOR_MODULES)
    if unknown:
        raise ValueError(f"unknown collector modules: {sorted(unknown)}")
    classes: list[type[Collector]] = []
    for module_name in wanted:
        module = importlib.import_module(f"tipcensus.{module_name}")
        classes.extend(module.COLLECTORS)
    return tuple(classes)


def play(spec: T.MatchSpec, modules: Sequence[str] = ()) -> dict[str, Any]:
    """Play one spec to FINISHED with the collectors watching every step.

    The loop is ``simulation.runner._advance_one_decision`` with the events
    kept, so the game is the one the tournament plays for the same spec.
    """

    config = spec.config
    engine = (
        T.UprisingRulesEngine(leader_ids=spec.leader_ids)
        if spec.leader_ids is not None
        else T.UprisingRulesEngine()
    )
    agents = tuple(
        T.make_agent(kind, spec.policy_seed + seat)
        for seat, kind in enumerate(spec.seat_agents)
    )
    searchers = _state_agents(agents)
    seats = len(spec.seat_agents)
    collectors = [cls(spec, seats) for cls in collector_classes(modules)]
    state = engine.reset(config, spec.game_seed)
    chance = ChanceResolver(seed=spec.game_seed)
    illegal = [0] * seats
    decisions = [0] * seats
    started = time.perf_counter()
    for _ in range(spec.max_steps):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            result = engine.apply(state, chance.resolve(decision))
            step = Step(state, result.state, None, None, (), tuple(result.events))
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
            decisions[owner] += 1
            if action not in legal:
                illegal[owner] += 1
                action = legal[0]
            result = engine.apply(state, action, legal_actions=legal)
            step = Step(state, result.state, owner, action, legal, tuple(result.events))
        for collector in collectors:
            collector.step(step)
        state = result.state
    else:
        raise RuntimeError(f"step limit reached for seed {spec.game_seed}")
    standings = final_standings(state)
    by_player = {standing.player: standing for standing in standings}
    seat_rows: list[dict[str, Any]] = [
        {
            "kind": kind,
            "seat": seat,
            "leader": state.players[seat].leader_id,
            "rank": by_player[seat].rank,
            "vp": by_player[seat].victory_points,
            "win": by_player[seat].rank == 1,
            "decisions": decisions[seat],
            "illegal": illegal[seat],
        }
        for seat, kind in enumerate(spec.seat_agents)
    ]
    game_row: dict[str, Any] = {"rounds": state.round_number}
    for collector in collectors:
        per_seat, game = collector.finish(state, standings)
        if len(per_seat) != seats:
            raise RuntimeError(f"{collector.name} returned {len(per_seat)} seat rows")
        for row, columns in zip(seat_rows, per_seat, strict=True):
            row.update({f"{collector.name}.{k}": v for k, v in columns.items()})
        game_row.update({f"{collector.name}.{k}": v for k, v in game.items()})
    return {
        "seed": spec.game_seed,
        "ruleset": config.identifier,
        "seconds": round(time.perf_counter() - started, 3),
        "seats": seat_rows,
        "game": game_row,
    }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float))  # bool is an int: a share


def summarize(rows: Sequence[dict[str, Any]], group: str) -> dict[str, dict[str, Any]]:
    """Mean of every numeric column and summed tallies, per value of ``group``.

    ``rows`` are flat dicts; a numeric column's mean skips None (reported as n),
    a dict column is summed and divided by the group's row count.
    """

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[group])].append(row)
    out: dict[str, dict[str, Any]] = {}
    for key, members in grouped.items():
        columns: dict[str, Any] = {"n": len(members)}
        names = sorted({name for row in members for name in row})
        for name in names:
            values = [row.get(name) for row in members]
            present = [v for v in values if v is not None]
            if present and all(_is_number(v) for v in present):
                columns[name] = (
                    sum(float(v) for v in present) / len(present),
                    len(present),
                )
            elif present and all(isinstance(v, dict) for v in present):
                tally: Counter[str] = Counter()
                for v in present:
                    tally.update({str(k): float(n) for k, n in v.items()})
                columns[name] = {k: n / len(members) for k, n in tally.most_common()}
        out[key] = columns
    return out


def _format_cell(value: Any, n_rows: int) -> str:
    if value is None:
        return ""
    if isinstance(value, tuple):
        mean, n = value
        text = f"{mean:.2f}"
        return text if n == n_rows else f"{text} (n={n})"
    if isinstance(value, dict):
        return ", ".join(f"{k} {v:.2f}" for k, v in list(value.items())[:6])
    return str(value)


def summary_markdown(results: Sequence[dict[str, Any]]) -> str:
    """Seat table (all seats and winners per kind) and game table per ruleset."""

    seat_rows = [
        {**seat, "_group": seat["kind"]} for game in results for seat in game["seats"]
    ]
    winner_rows = [
        {**row, "_group": row["kind"] + " (winners)"} for row in seat_rows if row["win"]
    ]
    seats = summarize(seat_rows + winner_rows, "_group")
    skip = {"seat", "_group", "kind", "leader"}
    groups = sorted(seats)
    names = sorted({n for g in groups for n in seats[g] if n not in skip and n != "n"})
    lines = [
        "| column | " + " | ".join(f"{g} (n={seats[g]['n']})" for g in groups) + " |",
        "| --- |" + " ---: |" * len(groups),
    ]
    for name in names:
        lines.append(
            f"| {name} | "
            + " | ".join(
                _format_cell(seats[g].get(name), seats[g]["n"]) for g in groups
            )
            + " |"
        )
    games = summarize(
        [{**game["game"], "_group": game["ruleset"]} for game in results], "_group"
    )
    game_groups = sorted(games)
    game_names = sorted(
        {n for g in game_groups for n in games[g] if n not in ("_group", "n")}
    )
    lines += [
        "",
        "| game column | "
        + " | ".join(f"{g} (n={games[g]['n']})" for g in game_groups)
        + " |",
        "| --- |" + " ---: |" * len(game_groups),
    ]
    for name in game_names:
        lines.append(
            f"| {name} | "
            + " | ".join(
                _format_cell(games[g].get(name), games[g]["n"]) for g in game_groups
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _play_star(args: tuple[T.MatchSpec, tuple[str, ...]]) -> dict[str, Any]:
    return play(*args)


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--agents", default="heuristic", help="comma-separated lineup (1-4 kinds)"
    )
    ap.add_argument("--games", type=int, default=40, help="seeds per ruleset")
    ap.add_argument("--start-seed", type=int, default=0)
    ap.add_argument("--ruleset", choices=("base", "choam", "both"), default="base")
    ap.add_argument("--bloodlines", action="store_true")
    ap.add_argument("--tech-module", action="store_true")
    ap.add_argument("--immortality", action="store_true")
    ap.add_argument("--promo-cards", action="store_true")
    ap.add_argument(
        "--collectors", default="", help=f"subset of {','.join(COLLECTOR_MODULES)}"
    )
    ap.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    ap.add_argument("--out", required=True, help="output directory")
    a = ap.parse_args(argv)
    modules = tuple(m for m in a.collectors.split(",") if m)
    collector_classes(modules)  # fail fast on a typo
    rulesets = {"base": (False,), "choam": (True,), "both": (False, True)}[a.ruleset]
    specs = T.tournament_specs(
        agents=tuple(a.agents.split(",")),
        games=a.games,
        rulesets=rulesets,
        start_seed=a.start_seed,
        rotate_leaders=True,
        promo_cards=a.promo_cards,
        bloodlines=a.bloodlines,
        tech_module=a.tech_module,
        immortality=a.immortality,
    )
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "args.json").write_text(json.dumps(vars(a), indent=1) + "\n")
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    with (
        (out / "rows.jsonl").open("w") as fh,
        ProcessPoolExecutor(max_workers=a.workers) as pool,
    ):
        for result in pool.map(
            _play_star, [(spec, modules) for spec in specs], chunksize=1
        ):
            results.append(result)
            fh.write(json.dumps(result) + "\n")
            fh.flush()
    table = summary_markdown(results)
    (out / "summary.md").write_text(table)
    illegal = sum(seat["illegal"] for game in results for seat in game["seats"])
    print(
        f"games={len(results)} agents={a.agents} ruleset={a.ruleset} "
        f"illegal={illegal} seconds={time.perf_counter() - started:.0f}"
    )
    print(table)


if __name__ == "__main__":
    main()
