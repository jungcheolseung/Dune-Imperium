"""Interactive and seeded-random debug interface for the Uprising engine."""

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict
from typing import Any

from dune_imperium import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RulesEngine
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation import run_random_round


def debug_snapshot(
    engine: RulesEngine,
    state: GameState,
    player: int,
) -> dict[str, Any]:
    """Build a JSON-safe decision snapshot from one player's observation."""

    view = engine.observe(state, player)
    actions = engine.legal_actions(state, player)
    return {
        "revision": view.revision,
        "round": view.round_number,
        "phase": view.phase,
        "first_player": view.first_player,
        "decision_owner": player,
        "current_conflicts": view.current_conflict_ids,
        "shield_wall_present": view.shield_wall_present,
        "players": [
            {
                "player": candidate.player,
                "leader_id": candidate.leader_id,
                "victory_points": candidate.victory_points,
                "resources": asdict(candidate.resources),
                "agents_available": candidate.agents_available,
                "agent_locations": candidate.agent_locations,
                "troops_garrison": candidate.troops_garrison,
                "troops_conflict": candidate.troops_conflict,
                "combat_strength": candidate.combat_strength,
                "has_revealed": candidate.has_revealed,
            }
            for candidate in view.players
        ],
        "private": None if view.private is None else asdict(view.private),
        "legal_actions": [
            _action_record(index, action) for index, action in enumerate(actions)
        ],
    }


def run_interactive_session(
    engine: RulesEngine,
    config: RulesetConfig,
    seed: int,
    *,
    read: Callable[[str], str] = input,
    write: Callable[[str], None] = print,
    max_steps: int = 500,
) -> GameState:
    """Let a user inspect and choose actions until the current round ends."""

    state = engine.reset(config, seed)
    for _ in range(max_steps):
        if state.phase in (GamePhase.ROUND_START, GamePhase.ENDGAME):
            write(_completion_summary(state))
            return state
        decision = engine.current_decision(state)
        if not isinstance(decision, PlayerDecision):
            raise RuntimeError("debug session requires a pending player decision")
        actions = engine.legal_actions(state, decision.owner)
        write(
            json.dumps(
                debug_snapshot(engine, state, decision.owner),
                ensure_ascii=False,
                indent=2,
            )
        )
        selected = _read_action(read, write, actions)
        if selected is None:
            write("Session stopped without changing the current state.")
            return state
        state = engine.apply(state, selected).state
    raise RuntimeError(f"debug session exceeded the {max_steps}-action limit")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the debug CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=0, help="game setup seed")
    parser.add_argument(
        "--random-policy-seed",
        type=int,
        help="run one non-interactive random round with this policy seed",
    )
    args = parser.parse_args(argv)
    engine = UprisingRulesEngine()
    config = RulesetConfig()
    if args.random_policy_seed is None:
        run_interactive_session(engine, config, args.seed)
    else:
        result = run_random_round(
            engine,
            config,
            game_seed=args.seed,
            policy_seed=args.random_policy_seed,
        )
        print(_completion_summary(result.state, len(result.replay.steps)))
    return 0


def _action_record(index: int, action: DomainAction) -> dict[str, Any]:
    return {
        "index": index,
        "action_id": action.action_id,
        "arguments": dict(action.arguments),
    }


def _read_action(
    read: Callable[[str], str],
    write: Callable[[str], None],
    actions: tuple[DomainAction, ...],
) -> DomainAction | None:
    while True:
        raw = read("Choose action index (or q): ").strip()
        if raw.lower() in {"q", "quit"}:
            return None
        try:
            return actions[int(raw)]
        except ValueError, IndexError:
            write(f"Enter an action index from 0 to {len(actions) - 1}, or q.")


def _completion_summary(state: GameState, steps: int | None = None) -> str:
    summary: dict[str, Any] = {
        "round": state.round_number,
        "phase": state.phase,
        "revision": state.revision,
        "victory_points": [player.victory_points for player in state.players],
    }
    if steps is not None:
        summary["steps"] = steps
    return json.dumps(summary, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
