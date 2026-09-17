"""Measure what a play-server client downloads over one full game.

Backs the numbers in ``docs/multiplayer-design.md`` (section 9). One game
runs through ``GameSessionManager`` exactly like the HTTP layer drives it:
the "human" seats are answered by heuristic agents (so the game has a
realistic length and shape), the other seats are heuristic AI seats. Before
every human decision the script sizes what a browser fetches to render it —
seat view, legal-action listing (with its dry runs), the full log as
``app.js`` requests it today, and the incremental log tail — raw and
gzip-compressed, and times the server side of each call.

Raw byte counts are deterministic for a seed (gzip sizes wobble by a byte
with the random game id inside the payloads); times depend on the machine.

    uv run python scripts/measure_server_payloads.py --seed 20260917
"""

import argparse
import gzip
import json
import statistics
import time
from collections.abc import Sequence

from dune_imperium.agents import StateAgent, make_agent
from dune_imperium.server.sessions import GameSessionManager

_DRIVER_SEED_OFFSET = 900_000


def _size(payload: object) -> tuple[int, int]:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return len(raw), len(gzip.compress(raw, compresslevel=6))


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def _describe(name: str, values: Sequence[float], unit: str) -> None:
    if not values:
        print(f"{name}: (none)")
        return
    print(
        f"{name}: n={len(values)} median={statistics.median(values):,.1f} "
        f"p95={_percentile(values, 0.95):,.1f} max={max(values):,.1f} {unit}"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=20260917, help="game seed")
    parser.add_argument(
        "--humans",
        type=int,
        default=3,
        choices=(1, 2, 3, 4),
        help="how many seats (from seat 0) are human (default: 3)",
    )
    parser.add_argument(
        "--ruleset",
        choices=("all", "base"),
        default="all",
        help="'all' turns on CHOAM, Bloodlines, Tech, Immortality and promos",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    humans = tuple(range(arguments.humans))
    everything = arguments.ruleset == "all"
    manager = GameSessionManager()
    seats = tuple("human" if seat in humans else "heuristic" for seat in range(4))
    started = time.perf_counter()
    summary = manager.create_game(
        seats,
        choam_module=everything,
        leader_draft=True,
        promo_cards=everything,
        bloodlines=everything,
        tech_module=everything,
        immortality=everything,
        game_seed=arguments.seed,
    )
    game_id = str(summary["game_id"])
    # The drivers need the engine's action objects, which the JSON API does
    # not carry; a measurement script may reach into the session for them.
    session = manager._get(game_id)  # noqa: SLF001
    drivers = {
        seat: make_agent("heuristic", _DRIVER_SEED_OFFSET + seat) for seat in humans
    }

    sizes: dict[str, list[float]] = {
        name: []
        for name in (
            "summary raw",
            "view raw",
            "view gzip",
            "actions raw",
            "actions gzip",
            "log FULL raw",
            "log FULL gzip",
            "log incremental raw",
        )
    }
    times: dict[str, list[float]] = {
        name: [] for name in ("view", "actions (dry runs)", "log FULL", "apply/confirm")
    }
    action_counts: list[float] = []
    steps_per_request: list[float] = []
    cursors = {seat: 0 for seat in humans}
    human_decisions = 0
    confirmations = 0

    while not summary["finished"]:
        revision = int(str(summary["revision"]))
        undo_count = int(str(summary["undo_count"]))
        if summary["confirmation"] is not None:
            seat = int(str(summary["confirmation"]))
            before = len(session.steps)
            tick = time.perf_counter()
            summary = manager.confirm_turn(
                game_id, seat, revision, undo_count=undo_count
            )
            times["apply/confirm"].append((time.perf_counter() - tick) * 1000)
            steps_per_request.append(len(session.steps) - before)
            confirmations += 1
            continue
        decision = summary["decision"]
        assert isinstance(decision, dict)
        seat = int(str(decision["owner"]))

        tick = time.perf_counter()
        view = manager.view(game_id, seat)
        times["view"].append((time.perf_counter() - tick) * 1000)
        raw, packed = _size(view)
        sizes["view raw"].append(raw)
        sizes["view gzip"].append(packed)

        tick = time.perf_counter()
        listing = manager.legal_actions(game_id, seat)
        times["actions (dry runs)"].append((time.perf_counter() - tick) * 1000)
        raw, packed = _size(listing)
        sizes["actions raw"].append(raw)
        sizes["actions gzip"].append(packed)
        listed = listing["actions"]
        assert isinstance(listed, list)
        action_counts.append(len(listed))

        tick = time.perf_counter()
        full = manager.log(game_id, seat)
        times["log FULL"].append((time.perf_counter() - tick) * 1000)
        raw, packed = _size(full)
        sizes["log FULL raw"].append(raw)
        sizes["log FULL gzip"].append(packed)
        tail = manager.log(game_id, seat, after=cursors[seat])
        sizes["log incremental raw"].append(_size(tail)[0])
        cursors[seat] = int(str(full["count"]))
        sizes["summary raw"].append(_size(summary)[0])

        actions = session.engine.legal_actions(session.state, seat)
        observation = session.engine.observe(session.state, seat)
        driver = drivers[seat]
        if isinstance(driver, StateAgent):
            chosen = driver.choose_action_with_state(
                session.state, observation, actions
            )
        else:
            chosen = driver.choose_action(observation, actions)
        before = len(session.steps)
        tick = time.perf_counter()
        summary = manager.apply_action(
            game_id, seat, revision, actions.index(chosen), undo_count=undo_count
        )
        times["apply/confirm"].append((time.perf_counter() - tick) * 1000)
        steps_per_request.append(len(session.steps) - before)
        human_decisions += 1

    elapsed = time.perf_counter() - started
    print(f"seed={arguments.seed} ruleset={arguments.ruleset} seats={seats}")
    print(
        f"rounds={summary['round_number']} steps={len(session.steps)} "
        f"log_entries={len(session.log)} human_decisions={human_decisions} "
        f"confirmations={confirmations} wall={elapsed:.1f}s"
    )
    for name, values in sizes.items():
        _describe(name, values, "bytes")
    _describe("legal actions per decision", action_counts, "actions")
    for name, values in times.items():
        _describe(f"server time: {name}", values, "ms")
    _describe("steps applied per request", steps_per_request, "steps")
    print(
        "log bytes downloaded over the game (one fetch per human decision): "
        f"full={sum(sizes['log FULL raw']) / 1e6:,.1f} MB "
        f"(gzip {sum(sizes['log FULL gzip']) / 1e6:,.1f} MB), "
        f"incremental={sum(sizes['log incremental raw']) / 1e6:,.2f} MB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
