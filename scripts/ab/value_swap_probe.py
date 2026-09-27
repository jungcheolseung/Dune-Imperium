"""Value sensitivity to counterfactual identity swaps.

See docs/evaluation/m10-2026-09-27.md section 3.

Takes real observations, swaps one identity at a time -- an Imperium Row card for a
neighbouring or a far-away card id, one hand card for a far-away one, the current
Conflict for another -- and reports each checkpoint's mean |value change|. A network
that reads the Row through ``log1p`` of ``index + 1`` barely moves on a Row swap
(champion 5081: 0.0013 against 0.039 for a hand swap). Same rows and swaps for every
checkpoint, so the numbers compare like for like; only the value head is read, so the
observations need no matching action catalog.

usage: uv run python scripts/ab/value_swap_probe.py CKPT [CKPT ...]
       [--shards 'checkpoints/2026-09-24/exit/data/c0/g*.npz'] [--rows 3000]

The shards are the expert-iteration label files (observation v20, key ``observations``);
any ``.npz`` with that key works. Run it from a checkout whose code can load every
checkpoint given (format 3 ``mlp_slots`` files need the current code).
"""

import argparse
import glob
from pathlib import Path

import numpy as np
import torch

from dune_imperium.adapters import observation_encoding as e
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.training.checkpoint import load_checkpoint

MODES = ("row_near", "row_far", "hand_far", "conflict")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("checkpoints", nargs="+", type=Path)
    parser.add_argument(
        "--shards", default="checkpoints/2026-09-24/exit/data/c0/g*.npz"
    )
    parser.add_argument("--every", type=int, default=12, help="take every Nth shard")
    parser.add_argument("--max-shards", type=int, default=60)
    parser.add_argument("--rows", type=int, default=3000)
    parser.add_argument("--threads", type=int, default=2)
    arguments = parser.parse_args()
    torch.set_num_threads(arguments.threads)

    files = sorted(glob.glob(arguments.shards))[:: arguments.every][
        : arguments.max_shards
    ]
    if not files:
        raise SystemExit(f"no shards match {arguments.shards}")
    observations = np.concatenate(
        [np.load(f)["observations"].astype(np.int64) for f in files]
    )
    rng = np.random.default_rng(0)
    rows = rng.choice(
        len(observations), size=min(len(observations), arguments.rows), replace=False
    )
    base = observations[rows]
    swaps = {mode: _swapped(base, mode) for mode in MODES}
    print(
        f"rows {len(rows)} from {len(files)} shards; swaps valid: "
        + ", ".join(f"{mode} {int(ok.sum())}" for mode, (_, ok) in swaps.items())
    )
    for path in arguments.checkpoints:
        network, info = load_checkpoint(path)
        with torch.no_grad():
            before = _values(network, base)
            parts = []
            for mode, (after_obs, ok) in swaps.items():
                change = np.abs(_values(network, after_obs) - before)[ok]
                parts.append(f"{mode} {change.mean():.4f}")
        extra = ""
        embedding = getattr(network, "slot_embed", None)
        if embedding is not None:
            norms = embedding.weight.detach().norm(dim=1)[:-1]
            extra = (
                f"; slot rows norm mean {norms.mean():.4f} max {norms.max():.4f} "
                f"trained {(norms > 0).sum().item()}/{norms.shape[0]}"
            )
        print(
            f"{path} [{info.arch} it{info.iteration}] std V {before.std():.4f}; "
            "mean|dV|: " + ", ".join(parts) + extra
        )
        del network


def _values(network: torch.nn.Module, observations: np.ndarray) -> np.ndarray:
    hidden = network.trunk(torch.from_numpy(observations))
    values: np.ndarray = network.value_head(hidden).squeeze(-1).numpy()
    return values


def _swapped(base: np.ndarray, mode: str) -> tuple[np.ndarray, np.ndarray]:
    segments = {s.name: s for s in e.OBSERVATION_SEGMENTS}
    row = segments["imperium_row"].offset
    hand = segments["private_hand"].offset
    conflict = segments["current_conflict"].offset
    imperium = sorted(
        i + 1
        for i, card in enumerate(e.PERSONAL_CARD_IDS)
        if card in IMPERIUM_CARDS_BY_ID
    )
    new = base.copy()
    ok = np.zeros(len(base), bool)
    rng = np.random.default_rng(1)
    for j in range(len(base)):
        o = new[j]
        if mode in ("row_near", "row_far"):
            present = set(o[row : row + 5].tolist())
            slots = [k for k in range(5) if o[row + k] in imperium]
            if not slots:
                continue
            k = rng.choice(slots)
            value = o[row + k]
            if mode == "row_near":
                candidates = [
                    w
                    for w in (value + 1, value - 1, value + 2, value - 2)
                    if w in imperium and w not in present
                ]
                pick = candidates[0] if candidates else None
            else:
                candidates = [
                    w
                    for w in imperium
                    if w not in present and abs(np.log1p(w) - np.log1p(value)) >= 0.4
                ]
                pick = rng.choice(candidates) if candidates else None
            if pick is not None:
                o[row + k] = pick
                ok[j] = True
        elif mode == "hand_far":
            held = [c for c in range(10, 119) if o[hand + c] > 0]
            if not held:
                continue
            card = rng.choice(held)
            candidates = [
                d for d in range(10, 119) if abs(d - card) >= 30 and o[hand + d] == 0
            ]
            if candidates:
                other = rng.choice(candidates)
                o[hand + card] -= 1
                o[hand + other] += 1
                ok[j] = True
        elif mode == "conflict":
            value = o[conflict]
            if value > 0:
                o[conflict] = rng.choice(
                    [w for w in range(1, len(e.CONFLICT_IDS) + 1) if w != value]
                )
                ok[j] = True
    return new, ok


if __name__ == "__main__":
    main()
