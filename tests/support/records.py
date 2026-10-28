"""Save documents of games played on this engine, for the records tests.

Records are converted to the current codec at each codec bump
(docs/human-records.md), so the records tests keep no record of an older
engine: they play a game here (``current_save``) and, where they need a
record an older engine wrote, take out what that engine never recorded --
the pauses (``rules/pauses.py``), which the one bridge every record may use
answers again (``older_steps``).
"""

from collections.abc import Sequence
from typing import Any

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.agents.registry import make_agent
from dune_imperium.config import RulesetConfig
from dune_imperium.core.chance import ChanceOutcome, is_fixed_outcome
from dune_imperium.core.decisions import ChanceDecision
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.core.state import canonical_state_hash
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.server.persistence import serialize_step
from dune_imperium.simulation.runner import run_policy_game

FULL = RulesetConfig(
    players=4,
    choam_module=True,
    leader_draft=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
)
_ENGINE = UprisingRulesEngine()


def played_steps(
    seed: int,
    *,
    config: RulesetConfig = FULL,
    agents: Sequence[str] = ("heuristic",) * 4,
    rounds: int | None = None,
) -> tuple[ReplayStep, ...]:
    """A game of ``agents`` on this engine, cut after round ``rounds``."""

    players = [make_agent(kind, seed * 10 + seat) for seat, kind in enumerate(agents)]
    steps = run_policy_game(_ENGINE, config, seed, players).replay.steps
    if rounds is None:
        return steps
    state = _ENGINE.reset(config, seed)
    for index, step in enumerate(steps):
        state = _ENGINE.apply(state, step).state
        if state.round_number > rounds:
            return steps[: index + 1]
    return steps


def save_document(
    seed: int,
    steps: Sequence[ReplayStep],
    *,
    seats: Sequence[str] = ("human",) * 4,
    config: RulesetConfig = FULL,
    codec: int = ACTION_CODEC_VERSION,
    reached: Sequence[ReplayStep] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """A play-server save document (format version 2) of ``steps``.

    Its state hash, round and phase are the ones ``reached`` (by default
    ``steps``) reach on this engine; ``codec`` stamps it as another engine's
    save, whose steps (``older_steps``) this engine may not take as they
    are."""

    state = _ENGINE.reset(config, seed)
    for step in steps if reached is None else reached:
        state = _ENGINE.apply(state, step).state
    replay = GameReplay(config, seed, tuple(steps), canonical_state_hash(state))
    document: dict[str, Any] = {
        "format": "dune-imperium-save",
        "format_version": 2,
        "ruleset": {"players": config.players, **_flags(config)},
        "game_seed": seed,
        "policy_seed": seed,
        "seats": list(seats),
        "steps": [serialize_step(step) for step in steps],
        "log": [{**serialize_step(step), "undone": False} for step in steps],
        "expected_state_hash": replay.expected_state_hash,
        "ruleset_version": replay.ruleset_version,
        "content_version": replay.content_version,
        "action_codec_version": codec,
        "name": f"seed {seed}",
        "saved_at": "2026-10-29T09:00:00+00:00",
        "source_game_id": f"{seed:032x}",
        "round_number": state.round_number,
        "phase": str(state.phase),
        "finished": False,
        "confirmation": None,
        "sealed_steps": len(steps),
        "open_units": [],
        "ai_pace": "instant",
    }
    document.update(extra)
    return document


def _flags(config: RulesetConfig) -> dict[str, Any]:
    return {
        "base_game": config.base_game.value,
        "choam_module": config.choam_module,
        "leader_draft": config.leader_draft,
        "promo_cards": config.promo_cards,
        "bloodlines": config.bloodlines,
        "tech_module": config.tech_module,
        "immortality": config.immortality,
        "go_to_11": config.go_to_11,
        "epic_game": config.epic_game,
        "arrakeen_scouts": config.arrakeen_scouts,
        "first_player_seat_zero": config.first_player_seat_zero,
        "rise_of_ix": config.rise_of_ix,
    }


def pause_indices(
    seed: int, steps: Sequence[ReplayStep], config: RulesetConfig = FULL
) -> list[int]:
    """The steps of ``steps`` that answer a pause (one fixed outcome)."""

    found = []
    state = _ENGINE.reset(config, seed)
    for index, step in enumerate(steps):
        decision = _ENGINE.current_decision(state)
        if (
            isinstance(step, ChanceOutcome)
            and isinstance(decision, ChanceDecision)
            and is_fixed_outcome(decision)
        ):
            found.append(index)
        state = _ENGINE.apply(state, step).state
    return found


def older_steps(
    seed: int, steps: Sequence[ReplayStep], config: RulesetConfig = FULL
) -> tuple[ReplayStep, ...]:
    """``steps`` as an engine without pauses recorded them."""

    pauses = set(pause_indices(seed, steps, config))
    return tuple(step for index, step in enumerate(steps) if index not in pauses)
