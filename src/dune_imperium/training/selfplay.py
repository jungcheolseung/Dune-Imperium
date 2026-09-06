"""Lockstep self-play over many games with batched policy inference (M9/M10).

``SelfPlayRunner.run`` drives a set of seeded games at once. Every lockstep
round it resolves each game's chance decisions, builds one
``PolicyRequest`` per game that waits on a player decision, groups the
requests by the policy that owns that seat (the game's lineup names a
policy per seat, so a league of learner, frozen checkpoints and rule-based
baselines shares one run), calls each policy once with its whole batch,
validates that every answer is a legal catalog index, and applies the
decoded actions. Finished games yield an ``Episode`` with the terminal
zero-sum rewards of the RL environment design (winner ``+1``, the others
``-1/3``; a truncated game pays ``0``) and, when recording is on, the
per-decision trajectory (observation, mask, action, seat) the learner
trains on. ``stack_episodes`` turns episodes into flat NumPy arrays whose
per-step return is the acting seat's terminal reward.
"""

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.adapters.observation_encoding import encode_player_view
from dune_imperium.adapters.pettingzoo_env import LOSER_REWARD, WINNER_REWARD
from dune_imperium.config import RulesetConfig
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.endgame import final_standings
from dune_imperium.training.policy import BatchPolicy, PolicyRequest

_MAX_CONSECUTIVE_CHANCE_STEPS = 64


@dataclass(frozen=True, slots=True)
class SelfPlaySpec:
    """One game of a self-play run: its seed and the policy name per seat."""

    game_seed: int
    lineup: tuple[str, ...]
    leader_ids: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class TrajectoryStep:
    """One recorded decision: what the acting seat saw and chose."""

    seat: int
    observation: np.ndarray
    mask: np.ndarray
    action: int


@dataclass(frozen=True, slots=True)
class Episode:
    """One finished (or truncated) self-play game."""

    game_seed: int
    ruleset: str
    lineup: tuple[str, ...]
    rewards: tuple[float, ...]
    ranks: tuple[int, ...]
    victory_points: tuple[int, ...]
    rounds: int
    decisions: int
    truncated: bool
    steps: tuple[TrajectoryStep, ...]


@dataclass(frozen=True, slots=True)
class TrainingBatch:
    """Flat arrays over every recorded step of a set of episodes."""

    observations: np.ndarray  # int32 [steps, OBSERVATION_SIZE]
    masks: np.ndarray  # int8 [steps, codec size]
    actions: np.ndarray  # int64 [steps]
    seats: np.ndarray  # int8 [steps]
    returns: np.ndarray  # float32 [steps]: terminal reward of the acting seat
    episode_ids: np.ndarray  # int32 [steps]: index into the episode sequence


@dataclass(slots=True)
class _Game:
    index: int
    spec: SelfPlaySpec
    state: GameState
    chance: ChanceResolver
    decisions: int = 0
    steps: list[TrajectoryStep] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SelfPlayResult:
    """Episodes of one run plus throughput facts."""

    episodes: tuple[Episode, ...]
    duration_seconds: float

    @property
    def decisions(self) -> int:
        return sum(episode.decisions for episode in self.episodes)


class SelfPlayRunner:
    """Run many games in lockstep, batching every policy's decisions."""

    def __init__(
        self,
        config: RulesetConfig,
        *,
        max_steps: int = 30_000,
        record: bool = True,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        self.config = config
        self.max_steps = max_steps
        self.record = record
        self.codec = ActionCodec(config)
        self._engines: dict[tuple[str, ...] | None, UprisingRulesEngine] = {}

    def _engine(self, leader_ids: tuple[str, ...] | None) -> UprisingRulesEngine:
        engine = self._engines.get(leader_ids)
        if engine is None:
            engine = (
                UprisingRulesEngine(leader_ids=leader_ids)
                if leader_ids is not None
                else UprisingRulesEngine()
            )
            self._engines[leader_ids] = engine
        return engine

    def run(
        self,
        policies: Mapping[str, BatchPolicy],
        specs: Sequence[SelfPlaySpec],
    ) -> SelfPlayResult:
        """Play every spec to the end and return the episodes in spec order."""

        started = time.perf_counter()
        games = []
        for index, spec in enumerate(specs):
            if len(spec.lineup) != self.config.players:
                raise ValueError("a lineup names exactly one policy per seat")
            for name in spec.lineup:
                if name not in policies:
                    raise ValueError(f"lineup names an unknown policy: {name!r}")
            engine = self._engine(spec.leader_ids)
            games.append(
                _Game(
                    index=index,
                    spec=spec,
                    state=engine.reset(self.config, spec.game_seed),
                    chance=ChanceResolver(seed=spec.game_seed),
                )
            )
        episodes: dict[int, Episode] = {}
        active = list(games)
        while active:
            waiting: list[_Game] = []
            requests: dict[str, list[tuple[_Game, PolicyRequest]]] = {}
            for game in active:
                self._advance_chance(game)
                if game.state.phase is GamePhase.FINISHED:
                    episodes[game.index] = self._finish(game, truncated=False)
                    continue
                if game.decisions >= self.max_steps:
                    episodes[game.index] = self._finish(game, truncated=True)
                    continue
                request = self._request(game)
                requests.setdefault(game.spec.lineup[request.seat], []).append(
                    (game, request)
                )
                waiting.append(game)
            for name, batch in requests.items():
                answers = policies[name].act([request for _, request in batch])
                if len(answers) != len(batch):
                    raise ValueError(f"policy {name!r} answered a different batch size")
                for (game, request), index in zip(batch, answers, strict=True):
                    self._apply(game, request, int(index), name)
            active = waiting
        return SelfPlayResult(
            episodes=tuple(episodes[game.index] for game in games),
            duration_seconds=time.perf_counter() - started,
        )

    def _advance_chance(self, game: _Game) -> None:
        engine = self._engine(game.spec.leader_ids)
        for _ in range(_MAX_CONSECUTIVE_CHANCE_STEPS):
            decision = engine.current_decision(game.state)
            if not isinstance(decision, ChanceDecision):
                return
            game.state = engine.apply(game.state, game.chance.resolve(decision)).state
        raise RuntimeError("too many consecutive chance decisions")

    def _request(self, game: _Game) -> PolicyRequest:
        engine = self._engine(game.spec.leader_ids)
        decision = engine.current_decision(game.state)
        if not isinstance(decision, PlayerDecision):
            raise RuntimeError("self-play requires a pending player decision")
        seat = decision.owner
        legal_actions = engine.legal_actions(game.state, seat)
        if not legal_actions:
            raise RuntimeError("current player decision has no legal actions")
        legal_indices = tuple(self.codec.encode(action) for action in legal_actions)
        mask = np.zeros(self.codec.size, dtype=np.int8)
        mask[list(legal_indices)] = 1
        view = engine.observe(game.state, seat)
        return PolicyRequest(
            game=game.index,
            seat=seat,
            state=game.state,
            view=view,
            legal_actions=legal_actions,
            legal_indices=legal_indices,
            observation=np.asarray(encode_player_view(view), dtype=np.int32),
            mask=mask,
        )

    def _apply(
        self, game: _Game, request: PolicyRequest, index: int, policy: str
    ) -> None:
        try:
            position = request.legal_indices.index(index)
        except ValueError:
            raise ValueError(
                f"policy {policy!r} chose illegal action index {index} for seat "
                f"{request.seat} of game seed {game.spec.game_seed}"
            ) from None
        if self.record:
            game.steps.append(
                TrajectoryStep(
                    seat=request.seat,
                    observation=request.observation,
                    mask=request.mask,
                    action=index,
                )
            )
        engine = self._engine(game.spec.leader_ids)
        game.state = engine.apply(game.state, request.legal_actions[position]).state
        game.decisions += 1

    def _finish(self, game: _Game, *, truncated: bool) -> Episode:
        players = self.config.players
        if truncated:
            rewards = tuple(0.0 for _ in range(players))
            ranks = tuple(0 for _ in range(players))
        else:
            standings = final_standings(game.state)
            by_player = {standing.player: standing for standing in standings}
            rewards = tuple(
                WINNER_REWARD if by_player[seat].rank == 1 else LOSER_REWARD
                for seat in range(players)
            )
            ranks = tuple(by_player[seat].rank for seat in range(players))
        return Episode(
            game_seed=game.spec.game_seed,
            ruleset=self.config.identifier,
            lineup=game.spec.lineup,
            rewards=rewards,
            ranks=ranks,
            victory_points=tuple(
                player.victory_points for player in game.state.players
            ),
            rounds=game.state.round_number,
            decisions=game.decisions,
            truncated=truncated,
            steps=tuple(game.steps),
        )


def stack_episodes(episodes: Sequence[Episode]) -> TrainingBatch:
    """Flatten recorded steps into arrays; the return is the seat's reward."""

    steps = [
        (episode_id, step)
        for episode_id, episode in enumerate(episodes)
        for step in episode.steps
    ]
    if not steps:
        raise ValueError("no recorded steps to stack")
    observations = np.stack([step.observation for _, step in steps])
    masks = np.stack([step.mask for _, step in steps])
    return TrainingBatch(
        observations=observations,
        masks=masks,
        actions=np.asarray([step.action for _, step in steps], dtype=np.int64),
        seats=np.asarray([step.seat for _, step in steps], dtype=np.int8),
        returns=np.asarray(
            [episodes[episode_id].rewards[step.seat] for episode_id, step in steps],
            dtype=np.float32,
        ),
        episode_ids=np.asarray([episode_id for episode_id, _ in steps], dtype=np.int32),
    )
