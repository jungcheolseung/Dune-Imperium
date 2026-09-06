"""Seeded cross-seat tournaments between named baseline agents (M9).

A tournament is a list of ``MatchSpec`` values. ``tournament_specs`` crosses
the requested agent lineup over every seat rotation, every selected ruleset,
and a contiguous seed range (optionally with a per-seed Leader roster), so a
lineup meets every seat, Leader, and first-player position the seeds
produce. Because setup depends only on the game seed, the rotations of one
seed share the same Leaders, decks, and first player and differ solely in
which agent sits where.

``play_match`` runs one spec through ``run_policy_game`` with every seat's
agent metered for decision count, wall-clock decision time, and illegal
choices (an illegal choice is counted and replaced by the first legal
action so the game still finishes). ``run_tournament`` fans the specs out
over worker processes and collects one ``TournamentReport``.
"""

import random
import time
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from dune_imperium.agents import Agent, StateAgent
from dune_imperium.agents.registry import is_agent_kind, make_agent
from dune_imperium.config import RulesetConfig
from dune_imperium.content.uprising.leaders import leaders_for_choam
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game


@dataclass(frozen=True, slots=True)
class MatchSpec:
    """One seeded game with a named agent in every seat."""

    game_seed: int
    policy_seed: int
    seat_agents: tuple[str, ...]
    choam_module: bool = False
    promo_cards: bool = False
    leader_ids: tuple[str, ...] | None = None
    max_steps: int = 30_000

    @property
    def config(self) -> RulesetConfig:
        return RulesetConfig(
            choam_module=self.choam_module,
            promo_cards=self.promo_cards,
        )


@dataclass(frozen=True, slots=True)
class SeatResult:
    """One seat's outcome and metering in a finished match."""

    seat: int
    agent: str
    leader_id: str
    rank: int
    victory_points: int
    decisions: int
    illegal_actions: int
    decision_seconds: float


@dataclass(frozen=True, slots=True)
class MatchResult:
    """A finished match: setup facts, standings, and per-seat metering."""

    ruleset: str
    game_seed: int
    policy_seed: int
    first_player: int
    rounds: int
    steps: int
    duration_seconds: float
    seats: tuple[SeatResult, ...]

    @property
    def winner(self) -> SeatResult:
        return next(seat for seat in self.seats if seat.rank == 1)


@dataclass(frozen=True, slots=True)
class MatchFailure:
    """A match that raised instead of finishing."""

    ruleset: str
    game_seed: int
    policy_seed: int
    seat_agents: tuple[str, ...]
    error: str


@dataclass(frozen=True, slots=True)
class TournamentReport:
    """Every finished match and every failure of one tournament run."""

    matches: tuple[MatchResult, ...]
    failures: tuple[MatchFailure, ...]
    duration_seconds: float


class _MeteredAgent:
    """Time an agent's decisions and count choices outside the legal set."""

    def __init__(self, inner: Agent) -> None:
        self._inner = inner
        self.decisions = 0
        self.illegal_actions = 0
        self.seconds = 0.0

    def choose_action(
        self,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        started = time.perf_counter()
        action = self._inner.choose_action(observation, legal_actions)
        return self._record(action, legal_actions, started)

    def choose_action_with_state(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        started = time.perf_counter()
        action = (
            self._inner.choose_action_with_state(state, observation, legal_actions)
            if isinstance(self._inner, StateAgent)
            else self._inner.choose_action(observation, legal_actions)
        )
        return self._record(action, legal_actions, started)

    def _record(
        self,
        action: DomainAction,
        legal_actions: tuple[DomainAction, ...],
        started: float,
    ) -> DomainAction:
        self.seconds += time.perf_counter() - started
        self.decisions += 1
        if action not in legal_actions:
            # Recorded as the agent's fault; the game continues with a legal
            # choice so the rest of the table is still evaluated.
            self.illegal_actions += 1
            action = legal_actions[0]
        return action


def play_match(
    spec: MatchSpec,
    *,
    engine: UprisingRulesEngine | None = None,
) -> MatchResult:
    """Play one spec to FINISHED and meter every seat."""

    config = spec.config
    if len(spec.seat_agents) != config.players:
        raise ValueError("exactly one agent kind per seat is required")
    if engine is None:
        engine = (
            UprisingRulesEngine(leader_ids=spec.leader_ids)
            if spec.leader_ids is not None
            else UprisingRulesEngine()
        )
    metered = tuple(
        _MeteredAgent(make_agent(kind, spec.policy_seed + seat))
        for seat, kind in enumerate(spec.seat_agents)
    )
    started = time.perf_counter()
    simulation = run_policy_game(
        engine,
        config,
        spec.game_seed,
        metered,
        max_steps=spec.max_steps,
    )
    duration = time.perf_counter() - started
    state = simulation.state
    if state.first_player is None:
        raise RuntimeError("a finished game must record its first player")
    standing_by_player = {
        standing.player: standing for standing in simulation.standings
    }
    leader_ids = tuple(player.leader_id for player in state.players)
    if any(leader_id is None for leader_id in leader_ids):
        raise RuntimeError("a finished game must assign a Leader to every seat")
    seats = tuple(
        SeatResult(
            seat=seat,
            agent=kind,
            leader_id=leader_ids[seat] or "",
            rank=standing_by_player[seat].rank,
            victory_points=standing_by_player[seat].victory_points,
            decisions=meter.decisions,
            illegal_actions=meter.illegal_actions,
            decision_seconds=meter.seconds,
        )
        for seat, (kind, meter) in enumerate(
            zip(spec.seat_agents, metered, strict=True)
        )
    )
    return MatchResult(
        ruleset=config.identifier,
        game_seed=spec.game_seed,
        policy_seed=spec.policy_seed,
        first_player=state.first_player,
        rounds=state.round_number,
        steps=len(simulation.replay.steps),
        duration_seconds=duration,
        seats=seats,
    )


def _run_spec(spec: MatchSpec) -> MatchResult | MatchFailure:
    try:
        return play_match(spec)
    except Exception as error:  # noqa: BLE001 - every failure belongs in the report
        return MatchFailure(
            ruleset=spec.config.identifier,
            game_seed=spec.game_seed,
            policy_seed=spec.policy_seed,
            seat_agents=spec.seat_agents,
            error=f"{type(error).__name__}: {error}",
        )


def run_tournament(
    specs: Iterable[MatchSpec],
    *,
    workers: int = 1,
) -> TournamentReport:
    """Play every spec, optionally across worker processes."""

    started = time.perf_counter()
    spec_list = list(specs)
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_run_spec, spec_list, chunksize=2))
    else:
        results = [_run_spec(spec) for spec in spec_list]
    return TournamentReport(
        matches=tuple(r for r in results if isinstance(r, MatchResult)),
        failures=tuple(r for r in results if isinstance(r, MatchFailure)),
        duration_seconds=time.perf_counter() - started,
    )


def seat_rotations(lineup: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    """Return the distinct cyclic rotations of a lineup, starting with it."""

    rotations: list[tuple[str, ...]] = []
    for offset in range(len(lineup)):
        rotation = lineup[offset:] + lineup[:offset]
        if rotation not in rotations:
            rotations.append(rotation)
    return tuple(rotations)


def fill_lineup(agents: tuple[str, ...], players: int = 4) -> tuple[str, ...]:
    """Cycle one to ``players`` agent kinds into a full-table lineup."""

    if not 1 <= len(agents) <= players:
        raise ValueError(f"a lineup names between 1 and {players} agents")
    for kind in agents:
        if not is_agent_kind(kind):
            raise ValueError(f"unknown agent kind: {kind!r}")
    return tuple(agents[index % len(agents)] for index in range(players))


def tournament_specs(
    *,
    agents: tuple[str, ...],
    games: int,
    rulesets: tuple[bool, ...] = (False,),
    start_seed: int = 0,
    policy_offset: int = 900_000,
    rotate_seats: bool = True,
    rotate_leaders: bool = False,
    promo_cards: bool = False,
    max_steps: int = 30_000,
) -> tuple[MatchSpec, ...]:
    """Cross a lineup over seats, rulesets, and a seed range.

    ``games`` counts seeds per ruleset; every seed yields one match per
    distinct seat rotation of the lineup (four for a mixed table, one when
    every seat holds the same agent). The policy seed is shared by the
    rotations of a seed so only the seating differs between them.
    """

    if games < 1:
        raise ValueError("a tournament needs at least one game seed")
    if not rulesets:
        raise ValueError("a tournament needs at least one ruleset")
    lineup = fill_lineup(agents)
    rotations = seat_rotations(lineup) if rotate_seats else (lineup,)
    return tuple(
        MatchSpec(
            game_seed=seed,
            policy_seed=policy_offset + seed,
            seat_agents=rotation,
            choam_module=choam_module,
            promo_cards=promo_cards,
            leader_ids=(
                _rotated_leader_ids(seed, choam_module) if rotate_leaders else None
            ),
            max_steps=max_steps,
        )
        for choam_module in rulesets
        for seed in range(start_seed, start_seed + games)
        for rotation in rotations
    )


def _rotated_leader_ids(seed: int, choam_module: bool) -> tuple[str, ...]:
    # Same derivation as the verification sweep's --rotate-leaders so a
    # tournament seed reproduces the sweep's roster for that seed.
    return tuple(
        random.Random(seed).sample(
            [leader.leader_id for leader in leaders_for_choam(choam_module)],
            k=4,
        )
    )
