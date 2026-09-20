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
per-step return is the acting seat's terminal reward. With
``undo_actions=False`` the runner withholds the pure-undo actions from every
policy (request, mask and recorded trajectory alike, so a learner stays
on-policy) while the engine still validates against its full legal set.
"""

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.adapters.observation_encoding import encode_player_view
from dune_imperium.adapters.pettingzoo_env import LOSER_REWARD, WINNER_REWARD
from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.endgame import final_standings
from dune_imperium.training.policy import (
    BatchPolicy,
    PolicyRequest,
    without_undo_actions,
)

_MAX_CONSECUTIVE_CHANCE_STEPS = 64


def rank_reward(rank: int, players: int) -> float:
    """Spread the terminal reward evenly over the finishing order.

    The default terminal reward says only whether a seat won: +1 for rank 1
    and -1/3 for everyone else (``pettingzoo_env``), so a seat that played
    well into second place is told the same thing as one that collapsed to
    last. That is 0.811 bits a seat where the finishing order the engine
    already computes carries 2.0.

    This maps rank linearly onto [+1, -1] instead -- 1, 1/3, -1/3, -1 at four
    players -- keeping the sum over a table at zero, so a game stays
    zero-sum and the batch's raw return mean stays centred. It is a
    learning-side reward transform: the environment keeps paying
    winner-take-all (docs/rl-environment.md, "보상"), and the tournament's
    win criterion is untouched.
    """

    if players < 2:
        raise ValueError("a rank reward needs at least two players")
    return 1.0 - 2.0 * (rank - 1) / (players - 1)


@dataclass(frozen=True, slots=True)
class SelfPlaySpec:
    """One game of a self-play run: its seed and the policy name per seat."""

    game_seed: int
    lineup: tuple[str, ...]
    leader_ids: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class TrajectoryStep:
    """One recorded decision: what the acting seat saw and chose.

    ``legal`` holds the catalog indices the policy was offered, not a dense
    mask over the whole catalog. A decision offers about five of them (mean
    4.7 of 32,987 measured over full-expansion games), so the dense form
    costs 32,987 bytes a step to say roughly five things, and a recorded
    game holds one per decision until the episode is stacked.
    """

    seat: int
    observation: np.ndarray
    legal: np.ndarray  # int32 [legal actions]: catalog indices, ascending
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
    """Flat arrays over every recorded step of a set of episodes.

    The legal set is kept in compressed-row form -- ``legal_indices``
    concatenated across steps, ``legal_offsets`` marking where each step's
    slice starts -- instead of a dense ``[steps, action_size]`` mask. The
    dense form is the largest array in training by a wide margin (32,987
    bytes a step against 17,308 for the observation) and it is almost all
    zeros; ``dense_masks`` materializes just the rows an update is about to
    use. Nothing is approximated: the row count is ragged and exact, so a
    decision offering an unusual number of actions needs no padding and can
    never be truncated.
    """

    observations: np.ndarray  # int32 [steps, OBSERVATION_SIZE]
    legal_indices: np.ndarray  # int32 [total legal]: catalog indices
    legal_offsets: np.ndarray  # int64 [steps + 1]: row starts, ascending
    action_size: int  # catalog width a dense mask would have
    actions: np.ndarray  # int64 [steps]
    seats: np.ndarray  # int8 [steps]
    returns: np.ndarray  # float32 [steps]: terminal reward of the acting seat
    episode_ids: np.ndarray  # int32 [steps]: index into the episode sequence

    def dense_masks(self, rows: np.ndarray) -> np.ndarray:
        """Return the dense 0/1 mask of ``rows``, in the order given."""

        selected = np.asarray(rows, dtype=np.int64)
        values, offsets = _gather_rows(
            self.legal_indices, self.legal_offsets, selected
        )
        counts = np.diff(offsets)
        masks = np.zeros((selected.shape[0], self.action_size), dtype=np.int8)
        masks[np.repeat(np.arange(selected.shape[0]), counts), values] = 1
        return masks


def _gather_rows(
    values: np.ndarray, offsets: np.ndarray, rows: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Take ``rows`` of a compressed-row array, keeping the order given."""

    starts = offsets[rows]
    counts = offsets[rows + 1] - starts
    gathered = np.zeros(int(counts.sum()), dtype=values.dtype)
    if gathered.shape[0]:
        # Position i of the output reads values[start(row(i)) + rank(i)],
        # where rank counts from the start of that row's slice.
        row_of = np.repeat(np.arange(rows.shape[0]), counts)
        ends = np.cumsum(counts)
        rank = np.arange(gathered.shape[0]) - np.repeat(ends - counts, counts)
        gathered = values[starts[row_of] + rank]
    new_offsets = np.zeros(rows.shape[0] + 1, dtype=np.int64)
    np.cumsum(counts, out=new_offsets[1:])
    return gathered, new_offsets


@dataclass(slots=True)
class _Game:
    index: int
    spec: SelfPlaySpec
    state: GameState
    chance: ChanceResolver
    decisions: int = 0
    steps: list[TrajectoryStep] = field(default_factory=list)
    # The engine's full legal set of the pending decision; ``apply`` must be
    # handed exactly this tuple even when the policy was offered less.
    legal: tuple[DomainAction, ...] = ()


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
        undo_actions: bool = True,
        rank_rewards: bool = False,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        self.config = config
        self.max_steps = max_steps
        self.record = record
        # False withholds ``UNDO_ACTION_IDS`` from every policy (training).
        self.undo_actions = undo_actions
        # True pays the finishing order instead of winner-take-all; see
        # ``rank_reward``. A learning-side transform, off by default so the
        # environment's documented reward stays the baseline.
        self.rank_rewards = rank_rewards
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
        game.legal = legal_actions
        if not self.undo_actions:
            legal_actions = without_undo_actions(legal_actions)
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
                    # The request's dense mask is the policy's contract and
                    # dies with the lockstep round; the recorded step keeps
                    # only the indices it was built from.
                    legal=np.asarray(request.legal_indices, dtype=np.int32),
                    action=index,
                )
            )
        engine = self._engine(game.spec.leader_ids)
        game.state = engine.apply(
            game.state,
            request.legal_actions[position],
            legal_actions=game.legal,
        ).state
        game.decisions += 1

    def _finish(self, game: _Game, *, truncated: bool) -> Episode:
        players = self.config.players
        if truncated:
            rewards = tuple(0.0 for _ in range(players))
            ranks = tuple(0 for _ in range(players))
        else:
            standings = final_standings(game.state)
            by_player = {standing.player: standing for standing in standings}
            ranks = tuple(by_player[seat].rank for seat in range(players))
            rewards = tuple(
                rank_reward(rank, players) if self.rank_rewards
                else (WINNER_REWARD if rank == 1 else LOSER_REWARD)
                for rank in ranks
            )
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


def stack_episodes(episodes: Sequence[Episode], *, action_size: int) -> TrainingBatch:
    """Flatten recorded steps into arrays; the return is the seat's reward.

    ``action_size`` is the catalog width the recorded indices belong to. It
    is asked for rather than inferred because the steps carry only the
    indices they were offered, and the widest of those is not the catalog.
    """

    steps = [
        (episode_id, step)
        for episode_id, episode in enumerate(episodes)
        for step in episode.steps
    ]
    if not steps:
        raise ValueError("no recorded steps to stack")
    observations = np.stack([step.observation for _, step in steps])
    offsets = np.zeros(len(steps) + 1, dtype=np.int64)
    np.cumsum(
        [step.legal.shape[0] for _, step in steps], out=offsets[1:], dtype=np.int64
    )
    return TrainingBatch(
        observations=observations,
        legal_indices=np.concatenate([step.legal for _, step in steps]),
        legal_offsets=offsets,
        action_size=action_size,
        actions=np.asarray([step.action for _, step in steps], dtype=np.int64),
        seats=np.asarray([step.seat for _, step in steps], dtype=np.int8),
        returns=np.asarray(
            [episodes[episode_id].rewards[step.seat] for episode_id, step in steps],
            dtype=np.float32,
        ),
        episode_ids=np.asarray([episode_id for episode_id, _ in steps], dtype=np.int32),
    )


def select_policy_steps(
    episodes: Sequence[Episode], name: str, *, action_size: int
) -> TrainingBatch:
    """Stack only the steps taken by seats the named policy controlled."""

    batch = stack_episodes(episodes, action_size=action_size)
    keep = np.asarray(
        [
            episodes[episode_id].lineup[seat] == name
            for episode_id, seat in zip(
                batch.episode_ids.tolist(), batch.seats.tolist(), strict=True
            )
        ],
        dtype=bool,
    )
    if not keep.any():
        raise ValueError(f"no steps were taken by policy {name!r}")
    rows = np.flatnonzero(keep)
    legal_indices, legal_offsets = _gather_rows(
        batch.legal_indices, batch.legal_offsets, rows
    )
    return TrainingBatch(
        observations=batch.observations[keep],
        legal_indices=legal_indices,
        legal_offsets=legal_offsets,
        action_size=batch.action_size,
        actions=batch.actions[keep],
        seats=batch.seats[keep],
        returns=batch.returns[keep],
        episode_ids=batch.episode_ids[keep],
    )


def apply_step_penalty(batch: TrainingBatch, penalty: float) -> TrainingBatch:
    """Charge every later decision of the same seat against a step's return.

    Learning-side shaping (the environment itself pays terminal rewards
    only): with ``penalty`` per decision, a step's return becomes the seat's
    terminal reward minus ``penalty`` times the number of decisions that
    seat still makes afterwards in the episode, so pointless reversible
    loops (deploy/withdraw, defer/resume) cost a little instead of nothing.
    Rows must be in chronological order within each episode, as
    ``stack_episodes`` produces them.
    """

    if penalty < 0.0:
        raise ValueError("step penalty must not be negative")
    if penalty == 0.0 or batch.actions.shape[0] == 0:
        return batch
    keys = batch.episode_ids.astype(np.int64) * 64 + batch.seats.astype(np.int64)
    remaining = np.zeros(keys.shape[0], dtype=np.float32)
    later: dict[int, int] = {}
    for index in range(keys.shape[0] - 1, -1, -1):
        key = int(keys[index])
        count = later.get(key, 0)
        remaining[index] = count
        later[key] = count + 1
    return TrainingBatch(
        observations=batch.observations,
        legal_indices=batch.legal_indices,
        legal_offsets=batch.legal_offsets,
        action_size=batch.action_size,
        actions=batch.actions,
        seats=batch.seats,
        returns=(batch.returns - penalty * remaining).astype(np.float32),
        episode_ids=batch.episode_ids,
    )
