"""Where do people beat the play network? Search-judge their recorded moves.

Three steps, each writing JSON lines under ``--diag``:

``judge``    At every recorded human decision of the saved games that
             offers more than one action, record the network's probability
             of the person's choice. Where the choice is not the network's
             first, evaluate the network's top three and the person's choice
             with the network's search in ``--worlds`` worlds drawn from that
             seat's own knowledge (common random numbers: every candidate
             meets the same world and chance stream).
``confirm``  Judge the clear verdicts again with another file's search
             (``--net``) and more worlds: the candidates are the first
             network's choice and the person's.
``report``   Tables and the confirmed decisions.
``freeze``   Write the decisions both judges agreed on as a suite of human
             problems with their games (``records.problems``), to score
             later agents with ``dune-imperium-records problems score``.
             ``--append`` adds a later run's games to the suite at ``--out``
             (judge only the new saves: ``--saves-dir`` a folder holding
             just them).

A verdict is clear when the mean paired difference (person minus network,
on the value head's scale: a win is 1, a loss -1/3) is beyond two standard
errors and 0.01. The judge plays every seat by the network's greedy policy
to the end of the round and reads the value head there, so it shares the
network's blind spots; a second network of another lineage would be a
stronger check. docs/evaluation/human-games-2026-10-10.md is the first run.

    uv run python scripts/records/human_diagnosis.py judge \\
        --net checkpoints/play/search.pt --diag tmp/records/diag
    uv run python scripts/records/human_diagnosis.py confirm \\
        --net <other.pt> --diag tmp/records/diag
    uv run python scripts/records/human_diagnosis.py report --diag tmp/records/diag
"""

import argparse
import glob
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import torch

from dune_imperium.adapters.observation_encoding import encode_player_view
from dune_imperium.agents.network_search_agent import (
    NetworkSearchAgent,
    orders_agent_effects,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView
from dune_imperium.paths import SAVES_DIR
from dune_imperium.records.problems import (
    DEFAULT_SUITE,
    build_suite,
    load_suite,
    merge_suites,
    save_suite,
)
from dune_imperium.records.saves import HumanDecision, human_decisions, saved_games
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.training.expert import decision_frame
from dune_imperium.training.policy import without_undo_actions
from dune_imperium.training.torch_policy import NetworkAgent

MARGIN = 0.01


def _probabilities(
    agent: NetworkAgent, view: PlayerView, offered: tuple[DomainAction, ...]
) -> np.ndarray:
    indices = [agent.codec.encode(action) for action in offered]
    mask = np.zeros(agent.codec.size, dtype=np.int8)
    mask[indices] = 1
    observation = np.asarray(encode_player_view(view), dtype=np.int32)
    with torch.no_grad():
        logits, _ = agent.network(
            torch.from_numpy(observation).unsqueeze(0),
            torch.from_numpy(mask).unsqueeze(0),
        )
    return torch.softmax(logits[0][indices], dim=0).numpy()


def _text(action: DomainAction) -> dict[str, object]:
    return {"id": action.action_id, "args": dict(action.arguments)}


def _paired(values: list[list[float]], human: int, other: int) -> tuple[float, float]:
    """Mean and standard error of ``human - other`` over the worlds."""

    diffs = [world[human] - world[other] for world in values]
    mean = sum(diffs) / len(diffs)
    variance = sum((d - mean) ** 2 for d in diffs) / (len(diffs) - 1)
    return mean, math.sqrt(variance / len(diffs))


def verdict(mean: float, error: float) -> str:
    if mean > 2 * error and mean > MARGIN:
        return "human"
    if mean < -2 * error and mean < -MARGIN:
        return "net"
    return "none"


def _decisions(
    saves_dir: Path, unfinished: bool, shard: int, shards: int
) -> Iterator[tuple[str, HumanDecision, tuple[DomainAction, ...]]]:
    """This shard's human decisions that offer a choice, per game."""

    for game in saved_games(saves_dir):
        if not (game.finished or unfinished) or not game.human_seats:
            continue
        number = -1
        for decision in human_decisions(game):
            offered = without_undo_actions(decision.legal_actions)
            if len(offered) < 2 or decision.chosen not in offered:
                continue
            number += 1
            if number % shards == shard:
                yield game.game_id[:8], decision, offered


def _judge(args: tuple[str, Path, int, bool, int, int, Path]) -> str:
    net, saves_dir, worlds, unfinished, shard, shards, out = args
    torch.set_num_threads(1)
    engine = UprisingRulesEngine()
    searches: dict[str, NetworkSearchAgent] = {}
    with out.open("w", encoding="utf-8") as handle:
        for game_id, decision, offered in _decisions(
            saves_dir, unfinished, shard, shards
        ):
            state = decision.state
            config = state.config
            if config.identifier not in searches:
                searches[config.identifier] = NetworkSearchAgent(
                    net, seed=1000 + shard, rollouts=worlds, config=config
                )
            search = searches[config.identifier]
            view = engine.observe(state, decision.seat)
            probabilities = _probabilities(search.greedy, view, offered)
            chosen = offered.index(decision.chosen)
            top = [int(i) for i in np.argsort(-probabilities, kind="stable")[:3]]
            row: dict[str, object] = {
                "game": game_id,
                "step": decision.recorded_index,
                "round": state.round_number,
                "seat": decision.seat,
                "frame": decision_frame(state),
                "effect_order": orders_agent_effects(state),
                "offered": len(offered),
                "human": _text(decision.chosen),
                "p_human": float(probabilities[chosen]),
                "agree": top[0] == chosen,
                "net_top": [
                    {**_text(offered[i]), "p": float(probabilities[i])} for i in top
                ],
            }
            if top[0] != chosen:
                candidates = top if chosen in top else [*top, chosen]
                values = search.evaluate_candidates(
                    state, decision.seat, tuple(offered[i] for i in candidates)
                )
                row["candidates"] = [_text(offered[i]) for i in candidates]
                row["human_col"] = candidates.index(chosen)
                row["values"] = [list(map(float, world)) for world in values]
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return f"judged {out.name}"


def _judged(diag: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for path in sorted(glob.glob(str(diag / "judge-*.jsonl")))
        for line in Path(path).read_text(encoding="utf-8").splitlines()
    ]


def _kind(row: dict[str, object]) -> str:
    human = row["human"]
    assert isinstance(human, dict)
    return "effect order" if row["effect_order"] else str(human["id"])


def _first_verdict(row: dict[str, object]) -> str:
    values = row["values"]
    assert isinstance(values, list)
    column = row["human_col"]
    assert isinstance(column, int)
    return verdict(*_paired(values, column, 0))


def _confirm(args: tuple[str, Path, Path, int, int, int, Path]) -> str:
    net, saves_dir, diag, worlds, shard, shards, out = args
    torch.set_num_threads(1)
    wanted = {
        (row["game"], row["step"]): row
        for row in _judged(diag)
        if not row["agree"] and _first_verdict(row) != "none"
    }
    searches: dict[str, NetworkSearchAgent] = {}
    with out.open("w", encoding="utf-8") as handle:
        for game_id, decision, offered in _decisions(saves_dir, True, shard, shards):
            row = wanted.get((game_id, decision.recorded_index))
            if row is None:
                continue
            state = decision.state
            config = state.config
            if config.identifier not in searches:
                searches[config.identifier] = NetworkSearchAgent(
                    net, seed=5000 + shard, rollouts=worlds, config=config
                )
            search = searches[config.identifier]
            top = row["net_top"]
            assert isinstance(top, list)
            first = next(
                action
                for action in offered
                if _text(action) == {"id": top[0]["id"], "args": top[0]["args"]}
            )
            values = search.evaluate_candidates(
                state, decision.seat, (first, decision.chosen)
            )
            mean, error = _paired([list(world) for world in values], 1, 0)
            handle.write(
                json.dumps(
                    {
                        **{key: row[key] for key in ("game", "step", "round", "seat")},
                        "kind": _kind(row),
                        "first": _first_verdict(row),
                        "mean": mean,
                        "error": error,
                        "second": verdict(mean, error),
                        "p_human": row["p_human"],
                        "human": row["human"],
                        "net_first": top[0],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return f"confirmed {out.name}"


def _report(diag: Path) -> None:
    rows = _judged(diag)
    print(f"human decisions with a choice: {len(rows)}")
    print(f"network's first choice = person's: {sum(bool(r['agree']) for r in rows)}")
    judged = [r for r in rows if not r["agree"]]
    by_kind: dict[str, Counter[str]] = defaultdict(Counter)
    for row in judged:
        by_kind[_kind(row)][_first_verdict(row)] += 1
    total = Counter(_first_verdict(row) for row in judged)
    print(f"disagreements: {len(judged)} {dict(total)}")
    print("by kind (person better / no clear difference / network better):")
    for kind, counts in sorted(by_kind.items(), key=lambda item: -item[1].total()):
        print(
            f"  {kind:36s} {counts['human']:4d} {counts['none']:4d} {counts['net']:4d}"
        )
    confirmed = [
        json.loads(line)
        for path in sorted(glob.glob(str(diag / "confirm-*.jsonl")))
        for line in Path(path).read_text(encoding="utf-8").splitlines()
    ]
    if not confirmed:
        return
    print("\nfirst verdict -> second verdict:")
    print(" ", dict(Counter((r["first"], r["second"]) for r in confirmed)))
    both = sorted(
        (r for r in confirmed if r["first"] == r["second"] == "human"),
        key=lambda r: -r["mean"],
    )
    print(f"\nperson better in both ({len(both)}):")
    for r in both:
        print(
            f"  {r['game']} R{r['round']} seat {r['seat']} {r['mean']:+.3f}"
            f"±{r['error']:.3f} p={r['p_human']:.3f}  person {r['human']['id']}"
            f" {r['human']['args']} | network {r['net_first']['id']}"
            f" {r['net_first']['args']}"
        )


def _freeze(diag: Path, saves_dir: Path, out: Path, note: str, append: bool) -> None:
    confirmed = [
        json.loads(line)
        for path in sorted(glob.glob(str(diag / "confirm-*.jsonl")))
        for line in Path(path).read_text(encoding="utf-8").splitlines()
    ]
    suite = build_suite(saved_games(saves_dir), _judged(diag), confirmed, note)
    if append and out.exists():
        suite = merge_suites(load_suite(out), suite)
    save_suite(out, suite)
    families = Counter(problem.family for problem in suite.problems)
    print(f"wrote {out}: {dict(families)} from {len(suite.records)} games")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("judge", "confirm"):
        command = sub.add_parser(name)
        command.add_argument("--net", required=True)
        command.add_argument(
            "--worlds", type=int, default=32 if name == "judge" else 64
        )
        command.add_argument("--workers", type=int, default=8)
        command.add_argument("--saves-dir", type=Path, default=SAVES_DIR)
        command.add_argument("--diag", type=Path, required=True)
        if name == "judge":
            command.add_argument(
                "--unfinished", action="store_true", help="also unfinished games"
            )
    report = sub.add_parser("report")
    report.add_argument("--diag", type=Path, required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--diag", type=Path, required=True)
    freeze.add_argument("--saves-dir", type=Path, default=SAVES_DIR)
    freeze.add_argument("--out", type=Path, default=DEFAULT_SUITE)
    freeze.add_argument(
        "--note", required=True, help="the judges and worlds, for the suite file"
    )
    freeze.add_argument(
        "--append",
        action="store_true",
        help="add these games' problems to the suite already at --out",
    )
    args = parser.parse_args()

    if args.command == "report":
        _report(args.diag)
        return
    if args.command == "freeze":
        _freeze(args.diag, args.saves_dir, args.out, args.note, args.append)
        return
    args.diag.mkdir(parents=True, exist_ok=True)
    shards = args.workers
    with ProcessPoolExecutor(max_workers=shards) as pool:
        if args.command == "judge":
            jobs = [
                pool.submit(
                    _judge,
                    (
                        args.net,
                        args.saves_dir,
                        args.worlds,
                        args.unfinished,
                        shard,
                        shards,
                        args.diag / f"judge-{shard}.jsonl",
                    ),
                )
                for shard in range(shards)
            ]
        else:
            jobs = [
                pool.submit(
                    _confirm,
                    (
                        args.net,
                        args.saves_dir,
                        args.diag,
                        args.worlds,
                        shard,
                        shards,
                        args.diag / f"confirm-{shard}.jsonl",
                    ),
                )
                for shard in range(shards)
            ]
        for job in jobs:
            print(job.result())


if __name__ == "__main__":
    main()
