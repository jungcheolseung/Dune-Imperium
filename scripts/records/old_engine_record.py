"""Write AI-game records with an *older* engine, cut after a few rounds.

The records in ``tests/unit/records/data`` were made this way, so the
migration tests replay records an older engine really wrote instead of
records edited to look old. Run it with the older engine's code on the
import path and this checkout's virtual environment:

    git worktree add --detach tmp/old-engine <commit>
    cd tmp/old-engine
    PYTHONPATH=$PWD/src ../../.venv/bin/python \\
        ../../scripts/records/old_engine_record.py ../../tmp/records 3 app_ai 1 2 3

(``tmp/`` is git-ignored; remove the worktree afterwards with
``git worktree remove``.) Every module is on, with the Leader draft, as at
the play server's tables, unless ``--without MODULE`` turns one off (Prison
Planet, for one, is drawn only without Immortality). The engine's commit
goes into the record's name.

usage: old_engine_record.py [--without MODULE ...] OUT_DIR ROUNDS AGENT SEED [SEED ...]
"""

import json
import subprocess
import sys
from pathlib import Path

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


def main(argv: list[str]) -> None:
    modules = dict(MODULES)
    off: list[str] = []
    while argv and argv[0] == "--without":
        off.append(argv[1])
        if not isinstance(modules.get(argv[1]), bool):
            raise SystemExit(f"--without takes a module flag, not {argv[1]!r}")
        modules[argv[1]] = False
        argv = argv[2:]
    out_dir, rounds, kind = Path(argv[0]), int(argv[1]), argv[2]
    out_dir.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(
        ["git", "rev-parse", "--short=8", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    config = RulesetConfig(**modules)
    engine = UprisingRulesEngine()
    for seed in map(int, argv[3:]):
        agents = [make_agent(kind, seed * 10 + seat) for seat in range(4)]
        game = run_policy_game(engine, config, seed, agents)
        state = engine.reset(config, seed)
        kept = []
        for step in game.replay.steps:
            state = engine.apply(state, step).state
            kept.append(step)
            if state.round_number > rounds:
                break
        document = {
            "format": "dune-imperium-save",
            "format_version": 1,
            "ruleset": modules,
            "game_seed": seed,
            "policy_seed": seed,
            "seats": [kind] * 4,
            "steps": [serialize_step(step) for step in kept],
            "expected_state_hash": canonical_state_hash(state),
            "ruleset_version": game.replay.ruleset_version,
            "content_version": game.replay.content_version,
            "action_codec_version": ACTION_CODEC_VERSION,
            "name": f"{kind} seed {seed}, rounds 1-{rounds}, engine {commit}",
        }
        without = "".join(f"-no-{name}" for name in off)
        path = out_dir / f"v{ACTION_CODEC_VERSION}{without}-{kind}-{seed}.json"
        path.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
        print(path, len(kept), "steps")


if __name__ == "__main__":
    main(sys.argv[1:])
