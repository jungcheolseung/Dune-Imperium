"""Screen leaf value networks for the search seat offline (``evaluation.value_screen``).

Record a search seat's playout ends on the gate's games, one process per
match (run several at once), then rate the ends with every value network
and compare each one's choices with a reference network's:

    uv run python scripts/ab/value_screen.py record \
        --agent 'search:<student.pt>::flip=0.01' \
        --opponent older:checkpoints/play/readapt-v147-4400.pt \
        --match 0 --out leaves/m0.npz
    uv run python scripts/ab/value_screen.py score --leaves leaves/m*.npz \
        --reference checkpoints/play/readapt-v147-4400.pt \
        --value student=<student.pt> --value e7b=<value.pt> --json screen.json

The games are the gate's: every option with the Leader draft, the seat
against three ``--opponent`` seats, ``--start-seed`` 7400000 and the
tournament's seat rotation (match 4k + s is seed 7400000 + k with the
seat in chair s).
"""

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

PLAY = dict(
    rulesets=(True,),
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
    leader_draft=True,
)


def _single_thread() -> None:
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(name, "1")


def record(arguments: argparse.Namespace) -> int:
    _single_thread()
    import torch

    torch.set_num_threads(1)
    from dune_imperium.evaluation.tournament import tournament_specs
    from dune_imperium.evaluation.value_screen import record_leaves, save_leaves

    opponent = arguments.opponent
    specs = tournament_specs(
        agents=(arguments.agent, opponent, opponent, opponent),
        games=arguments.match // 4 + 1,
        start_seed=arguments.start_seed,
        **PLAY,
    )
    started = time.perf_counter()
    spec = specs[arguments.match]
    leaves = record_leaves(spec, arguments.agent, game=arguments.match)
    save_leaves(leaves, arguments.out)
    seconds = time.perf_counter() - started
    print(
        f"match {arguments.match}: {leaves.decisions} searched decisions, "
        f"{int(leaves.offsets[-1])} leaves ({int(leaves.finished.sum())} finished), "
        f"{seconds:.0f}s -> {arguments.out}"
    )
    return 0


def score(arguments: argparse.Namespace) -> int:
    import numpy as np
    import torch

    torch.set_num_threads(arguments.threads)
    from dune_imperium.config import RulesetConfig
    from dune_imperium.evaluation.value_screen import (
        decision_scores,
        leaf_values,
        load_leaves,
        paired_difference,
        screen,
        search_pick,
        value_network,
    )

    started = time.perf_counter()
    leaves = load_leaves(sorted(arguments.leaves))
    picks = [
        search_pick(leaves.matrix(leaves.recorded, decision), arguments.flip)
        for decision in range(leaves.decisions)
    ]
    if picks != leaves.chosen.tolist():
        print("the pick rule does not reproduce the recorded choices", file=sys.stderr)
        return 1
    config = RulesetConfig(
        choam_module=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        go_to_11=True,
        epic_game=True,
        arrakeen_scouts=True,
        leader_draft=True,
    )
    named = [("reference", str(arguments.reference))]
    for item in arguments.value:
        name, _, path = item.partition("=")
        if not path:
            print(f"--value takes NAME=PATH, not {item!r}", file=sys.stderr)
            return 2
        named.append((name, path))
    values = {}
    for name, path in named:
        values[name] = leaf_values(value_network(path, config), leaves)
    rated = time.perf_counter() - started
    reference = values["reference"]
    per = {
        name: decision_scores(leaves, value, reference, flip_margin=arguments.flip)
        for name, value in values.items()
    }
    scores_out: dict[str, dict[str, float]] = {}
    against_recorder: dict[str, float] = {}
    pairs: dict[str, dict[str, tuple[float, float, float]]] = {}
    print(f"{leaves.decisions} decisions, {int(leaves.offsets[-1])} leaves, "
          f"rated in {rated:.0f}s")
    print(f"{'network':12s} {'agree':>7s} {'regret':>8s} {'gap rmse':>9s} "
          f"{'leaf rmse':>9s} {'|v-rec| max':>11s}")
    open_leaves = ~leaves.finished
    for name, scores in per.items():
        result = screen(scores)
        recorder_gap = float(
            np.abs(values[name][open_leaves] - leaves.recorded[open_leaves]).max()
        )
        scores_out[name] = asdict(result)
        against_recorder[name] = recorder_gap
        print(f"{name:12s} {result.agreement:7.3f} {result.regret:8.5f} "
              f"{result.gap_rmse:9.5f} {result.leaf_rmse:9.5f} {recorder_gap:11.2e}")
    names = [name for name, _ in named if name != "reference"]
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            pair = {}
            for statistic in ("agree", "regret", "gap_error"):
                pair[statistic] = paired_difference(
                    getattr(per[first], statistic), getattr(per[second], statistic)
                )
            pairs[f"{first}-{second}"] = pair
            agree, regret = pair["agree"], pair["regret"]
            print(f"{first} - {second}: agreement {agree[0]:+.3f} "
                  f"[{agree[1]:+.3f}, {agree[2]:+.3f}], regret {regret[0]:+.5f} "
                  f"[{regret[1]:+.5f}, {regret[2]:+.5f}]")
    if arguments.json is not None:
        report = {
            "leaves": [str(path) for path in sorted(arguments.leaves)],
            "decisions": leaves.decisions,
            "open_leaves": int((~leaves.finished).sum()),
            "flip": arguments.flip,
            "networks": dict(named),
            "seconds_to_rate": rated,
            "scores": scores_out,
            "against_recorder": against_recorder,
            "pairs": pairs,
        }
        arguments.json.parent.mkdir(parents=True, exist_ok=True)
        arguments.json.write_text(json.dumps(report, indent=1) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    recording = commands.add_parser("record", help="keep one match's playout ends")
    recording.add_argument("--agent", required=True, help="the search seat's kind")
    recording.add_argument("--opponent", required=True, help="the other seats' kind")
    recording.add_argument("--start-seed", type=int, default=7_400_000)
    recording.add_argument("--match", type=int, required=True)
    recording.add_argument("--out", type=Path, required=True)
    recording.set_defaults(run=record)
    scoring = commands.add_parser("score", help="rate recorded ends with networks")
    scoring.add_argument("--leaves", type=Path, nargs="+", required=True)
    scoring.add_argument("--reference", type=Path, required=True)
    scoring.add_argument("--value", action="append", default=[], metavar="NAME=PATH")
    scoring.add_argument("--flip", type=float, default=0.01)
    scoring.add_argument("--threads", type=int, default=2)
    scoring.add_argument("--json", type=Path)
    scoring.set_defaults(run=score)
    arguments = parser.parse_args(argv)
    result: int = arguments.run(arguments)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
