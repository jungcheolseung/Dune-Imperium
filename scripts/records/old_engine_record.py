"""Write AI-game records with an *older* engine, cut after a few rounds.

A bridge from the previous codec (``records.migration``) is protected with
records that engine really wrote, made this way, instead of records edited
to look old (docs/human-records.md; the bridges of codecs v135-v155 and
their records were removed when every kept record was converted to v156).
Run it with the older engine's code on the import path and this checkout's
virtual environment:

    git worktree add --detach tmp/old-engine <commit>
    cd tmp/old-engine
    PYTHONPATH=$PWD/src ../../.venv/bin/python \\
        ../../scripts/records/old_engine_record.py ../../tmp/records 3 app_ai 1 2 3

(``tmp/`` is git-ignored; remove the worktree afterwards with
``git worktree remove``.) Every module is on, with the Leader draft, as at
the play server's tables, unless ``--without MODULE`` turns one off (Prison
Planet, for one, is drawn only without Immortality). The engine's commit
goes into the record's name: the commit of the checkout ``dune_imperium``
was imported from, whatever the current directory.

``play_record`` is the same writer as a function, for the record corpus
(``corpus_generate.py``): per-seat agent kinds, the whole game unless
``rounds`` cuts it, and an ``on_step`` hook inside the one replay that
makes the record's state hash. Like every driver in this folder it runs
under older engines, so it touches the engine only through the names the
corpus tests allow (tests/unit/records/test_corpus_generate.py).

usage: old_engine_record.py [--without MODULE ...] OUT_DIR ROUNDS AGENT SEED [SEED ...]
"""

import dataclasses
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import dune_imperium
from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.agents.registry import make_agent
from dune_imperium.config import RulesetConfig
from dune_imperium.core.state import canonical_state_hash
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.server.persistence import serialize_step
from dune_imperium.simulation.runner import run_policy_game

MODULES = {
    "players": 4,
    "choam_module": True,
    "leader_draft": True,
    "promo_cards": True,
    "bloodlines": True,
    "tech_module": True,
    "immortality": True,
    "go_to_11": True,
    "epic_game": True,
    "arrakeen_scouts": True,
}

# ``on_step(index, before, step, transition)``: the recorded step's index,
# the state before it, the step, and the engine's ``Transition``.
type StepHook = Callable[[int, Any, Any, Any], None]


def modules_with(without: Sequence[str] = ()) -> dict[str, Any]:
    """``MODULES`` with every module named in ``without`` turned off."""

    modules: dict[str, Any] = dict(MODULES)
    for name in without:
        if not isinstance(modules.get(name), bool):
            raise SystemExit(f"--without takes a module flag, not {name!r}")
        modules[name] = False
    return modules


def engine_checkout() -> Path:
    """The checkout ``dune_imperium`` was imported from."""

    return Path(dune_imperium.__file__).resolve().parents[2]


def engine_commit() -> str:
    """The short commit of that checkout, for the record's name."""

    return subprocess.run(
        ["git", "-C", str(engine_checkout()), "rev-parse", "--short=8", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def play_record(
    engine: Any,
    config: Any,
    seats: Sequence[str],
    seed: int,
    *,
    rounds: int | None = None,
    commit: str,
    on_step: StepHook | None = None,
) -> tuple[dict[str, Any], Any]:
    """Play one game and return its save document and the state it ends in.

    Seat ``i`` is ``make_agent(seats[i], seed * 10 + i)``. The game is
    played whole, then replayed step by step to make the document's state
    hash; ``rounds`` cuts that replay after the step that opens round
    ``rounds + 1``. ``on_step`` sees every kept step of that replay.
    """

    agents = [make_agent(kind, seed * 10 + seat) for seat, kind in enumerate(seats)]
    game = run_policy_game(engine, config, seed, agents)
    state = engine.reset(config, seed)
    kept = []
    for index, step in enumerate(game.replay.steps):
        before = state
        transition = engine.apply(state, step)
        state = transition.state
        kept.append(step)
        if on_step is not None:
            on_step(index, before, step, transition)
        if rounds is not None and state.round_number > rounds:
            break
    expected_state_hash = canonical_state_hash(state)
    if len(kept) == len(game.replay.steps) and (
        expected_state_hash != game.replay.expected_state_hash
    ):
        raise RuntimeError(f"seed {seed}: the replay does not reach the played state")
    label = seats[0] if len(set(seats)) == 1 else "/".join(seats)
    span = "" if rounds is None else f", rounds 1-{rounds}"
    document = {
        "format": "dune-imperium-save",
        "format_version": 1,
        "ruleset": {
            field.name: getattr(config, field.name)
            for field in dataclasses.fields(config)
        },
        "game_seed": seed,
        "policy_seed": seed,
        "seats": list(seats),
        "steps": [serialize_step(step) for step in kept],
        "expected_state_hash": expected_state_hash,
        "ruleset_version": game.replay.ruleset_version,
        "content_version": game.replay.content_version,
        "action_codec_version": ACTION_CODEC_VERSION,
        "name": f"{label} seed {seed}{span}, engine {commit}",
    }
    return document, state


def main(argv: list[str]) -> None:
    without: list[str] = []
    while argv and argv[0] == "--without":
        without.append(argv[1])
        argv = argv[2:]
    modules = modules_with(without)
    out_dir, rounds, kind = Path(argv[0]), int(argv[1]), argv[2]
    out_dir.mkdir(parents=True, exist_ok=True)
    commit = engine_commit()
    config = RulesetConfig(**modules)
    engine = UprisingRulesEngine()
    for seed in map(int, argv[3:]):
        document, _ = play_record(
            engine, config, [kind] * 4, seed, rounds=rounds, commit=commit
        )
        suffix = "".join(f"-no-{name}" for name in without)
        path = out_dir / f"v{ACTION_CODEC_VERSION}{suffix}-{kind}-{seed}.json"
        path.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
        print(path, len(document["steps"]), "steps")


if __name__ == "__main__":
    main(sys.argv[1:])
