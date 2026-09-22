"""Self-play collection for the learner, in-process or over worker processes.

Collection dominates training time (the Python engine, not the network),
so ``Collector`` can fan one iteration's games out over worker processes.
Each worker rebuilds the learner network on the CPU from the state dict it
receives, plays its chunk of games with the lockstep runner, keeps only the
learner's own decisions, and hands the arrays back through a temporary
``.npz`` file (hundreds of megabytes per iteration would otherwise cross
the pipe); the episode summaries come back without their steps. Chunk
seeds derive from the iteration so a run is reproducible for a fixed
worker count, and serial collection re-seeds the same way. Collection
always withholds the pure-undo actions (``undo_actions=False``): a sampled
policy that is offered deploy/withdraw learns to loop on it.
"""

import os
import shutil
import tempfile
import time
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from multiprocessing import get_context
from pathlib import Path
from typing import Any

import numpy as np
import torch

from dune_imperium.agents.registry import CHECKPOINT_PREFIX
from dune_imperium.config import RulesetConfig
from dune_imperium.training.network import PolicyValueNetwork
from dune_imperium.training.policy import AgentBatchPolicy, BatchPolicy
from dune_imperium.training.selfplay import (
    Episode,
    SelfPlayRunner,
    SelfPlaySpec,
    TrainingBatch,
    select_policy_steps,
)
from dune_imperium.training.torch_policy import TorchBatchPolicy, load_frozen_network

LEARNER = "learner"


@dataclass(frozen=True, slots=True)
class CollectionResult:
    """One iteration's episodes (steps stripped when parallel) and batch."""

    episodes: tuple[Episode, ...]
    batch: TrainingBatch
    decisions: int
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class _ChunkJob:
    weights_path: str
    hidden: tuple[int, ...]
    action_size: int
    ruleset: RulesetConfig
    specs: tuple[SelfPlaySpec, ...]
    policy_seed: int
    temperature: float
    opponent: str | None
    opponent_seed: int
    max_steps: int
    rank_rewards: bool
    out_path: str


@dataclass(frozen=True, slots=True)
class _ChunkResult:
    episodes: tuple[Episode, ...]
    decisions: int
    out_path: str


def _policies(
    network: PolicyValueNetwork,
    device: torch.device,
    job_seed: int,
    temperature: float,
    opponent: str | None,
    opponent_seed: int,
) -> dict[str, BatchPolicy]:
    policies: dict[str, BatchPolicy] = {
        LEARNER: TorchBatchPolicy(
            network, device, seed=job_seed, sample=True, temperature=temperature
        )
    }
    if opponent is not None:
        if opponent.startswith(CHECKPOINT_PREFIX):
            # A frozen checkpoint answers its seats' decisions in one batched
            # greedy pass. Through ``AgentBatchPolicy`` every decision was its
            # own forward pass behind a fresh observation encode and a
            # per-seat ActionCodec, which on 2026-09-22 made a 1-vs-3
            # collection take 28.9s against 8.5s for pure self-play.
            policies[opponent] = TorchBatchPolicy(
                load_frozen_network(opponent[len(CHECKPOINT_PREFIX) :]),
                torch.device("cpu"),
                seed=opponent_seed,
                sample=False,
            )
        else:
            policies[opponent] = AgentBatchPolicy(opponent, opponent_seed)
    return policies


def _collect_chunk(job: _ChunkJob) -> _ChunkResult:
    torch.set_num_threads(1)
    network = PolicyValueNetwork(job.action_size, hidden=job.hidden)
    network.load_state_dict(
        torch.load(job.weights_path, map_location="cpu", weights_only=True)
    )
    network.eval()
    runner = SelfPlayRunner(
        job.ruleset,
        max_steps=job.max_steps,
        record=True,
        undo_actions=False,
        rank_rewards=job.rank_rewards,
    )
    policies = _policies(
        network,
        torch.device("cpu"),
        job.policy_seed,
        job.temperature,
        job.opponent,
        job.opponent_seed,
    )
    result = runner.run(policies, job.specs)
    batch = select_policy_steps(
        result.episodes, LEARNER, action_size=runner.codec.size
    )
    if batch.observations.max(initial=0) > np.iinfo(np.int16).max:
        raise RuntimeError("observation values exceed the int16 transport range")
    np.savez(
        job.out_path,
        observations=batch.observations.astype(np.int16),
        legal_indices=batch.legal_indices,
        legal_offsets=batch.legal_offsets,
        actions=batch.actions,
        seats=batch.seats,
        returns=batch.returns,
        episode_ids=batch.episode_ids,
    )
    return _ChunkResult(
        episodes=tuple(replace(episode, steps=()) for episode in result.episodes),
        decisions=result.decisions,
        out_path=job.out_path,
    )


class Collector:
    """Collect one iteration of learner self-play, serially or in parallel."""

    def __init__(
        self,
        config: RulesetConfig,
        *,
        workers: int = 1,
        max_steps: int = 30_000,
        temperature: float = 1.0,
        opponent: str | None = None,
        rank_rewards: bool = False,
    ) -> None:
        if workers < 1:
            raise ValueError("workers must be positive")
        self.config = config
        self.workers = workers
        self.max_steps = max_steps
        self.temperature = temperature
        self.opponent = opponent
        self.rank_rewards = rank_rewards
        self._pool: ProcessPoolExecutor | None = None
        self._scratch: Path | None = None
        if workers > 1:
            self._pool = ProcessPoolExecutor(
                max_workers=workers, mp_context=get_context("spawn")
            )
            self._scratch = Path(tempfile.mkdtemp(prefix="dune-imperium-selfplay-"))

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            self._pool = None
        if self._scratch is not None:
            shutil.rmtree(self._scratch, ignore_errors=True)
            self._scratch = None

    def __enter__(self) -> Collector:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def collect(
        self,
        network: PolicyValueNetwork,
        device: torch.device,
        specs: Sequence[SelfPlaySpec],
        *,
        policy_seed: int,
        opponent_seed: int,
    ) -> CollectionResult:
        """Play ``specs`` with ``network`` as the learner and return the batch."""

        started = time.perf_counter()
        if self._pool is None or self._scratch is None:
            runner = SelfPlayRunner(
                self.config,
                max_steps=self.max_steps,
                record=True,
                undo_actions=False,
                rank_rewards=self.rank_rewards,
            )
            policies = _policies(
                network,
                device,
                policy_seed,
                self.temperature,
                self.opponent,
                opponent_seed,
            )
            result = runner.run(policies, specs)
            return CollectionResult(
                episodes=result.episodes,
                batch=select_policy_steps(
                    result.episodes, LEARNER, action_size=runner.codec.size
                ),
                decisions=result.decisions,
                duration_seconds=time.perf_counter() - started,
            )

        weights_path = self._scratch / f"weights_{policy_seed}.pt"
        torch.save(
            {
                key: value.detach().to("cpu")
                for key, value in network.state_dict().items()
            },
            weights_path,
        )
        chunks = [tuple(specs[index :: self.workers]) for index in range(self.workers)]
        jobs = [
            _ChunkJob(
                weights_path=str(weights_path),
                hidden=network.hidden,
                action_size=network.action_size,
                ruleset=self.config,
                specs=chunk,
                policy_seed=policy_seed + index * 7_919,
                temperature=self.temperature,
                opponent=self.opponent,
                opponent_seed=opponent_seed + index * 104_729,
                max_steps=self.max_steps,
                rank_rewards=self.rank_rewards,
                out_path=str(self._scratch / f"chunk_{policy_seed}_{index}.npz"),
            )
            for index, chunk in enumerate(chunks)
            if chunk
        ]
        results = list(self._pool.map(_collect_chunk, jobs))
        os.remove(weights_path)
        episodes: list[Episode] = []
        parts: list[TrainingBatch] = []
        offset = 0
        for chunk_result in results:
            with np.load(chunk_result.out_path) as arrays:
                parts.append(
                    TrainingBatch(
                        observations=arrays["observations"].astype(np.int32),
                        legal_indices=arrays["legal_indices"],
                        legal_offsets=arrays["legal_offsets"],
                        action_size=network.action_size,
                        actions=arrays["actions"],
                        seats=arrays["seats"],
                        returns=arrays["returns"],
                        episode_ids=arrays["episode_ids"] + offset,
                    )
                )
            os.remove(chunk_result.out_path)
            episodes.extend(chunk_result.episodes)
            offset += len(chunk_result.episodes)
        # A chunk's row starts are relative to its own index array, so each
        # part's offsets shift by every earlier part's length. The first
        # entry of every part is a duplicate 0 and is dropped.
        lengths = [int(part.legal_indices.shape[0]) for part in parts]
        shifts = np.cumsum([0] + lengths[:-1])  # index rows already written
        batch = TrainingBatch(
            observations=np.concatenate([part.observations for part in parts]),
            legal_indices=np.concatenate([part.legal_indices for part in parts]),
            legal_offsets=np.concatenate(
                [parts[0].legal_offsets]
                + [
                    part.legal_offsets[1:] + shift
                    for part, shift in zip(parts[1:], shifts[1:], strict=True)
                ]
            ),
            action_size=network.action_size,
            actions=np.concatenate([part.actions for part in parts]),
            seats=np.concatenate([part.seats for part in parts]),
            returns=np.concatenate([part.returns for part in parts]),
            episode_ids=np.concatenate([part.episode_ids for part in parts]),
        )
        return CollectionResult(
            episodes=tuple(episodes),
            batch=batch,
            decisions=sum(result.decisions for result in results),
            duration_seconds=time.perf_counter() - started,
        )
