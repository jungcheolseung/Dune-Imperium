"""A network of an older codec, answering the current engine's decisions.

Retrain (가) of the stage B handoff (docs/development-handoff.md ②, user
decision 2026-10-21): the play network ``readapt-v147-4400`` learnt codec
v147, where an Agent turn, an effect with its target and a Reveal gain were
one row each. Codec v150 offers them step by step (stage B1, B3) and names
some by the entity that printed them (B3c-2b, B3e-1), so the file's rows
reach only 84 of the 4,311 rows of a game with every option
(``load_checkpoint`` moves rows by template identity). To use it as a
teacher at v150, this module scores the *whole* actions a decision stands
for instead of its rows:

1. the whole actions, as the heuristic sees them
   (``agents.agent_turn_steps.placements_for_steps``): an Agent-turn step's
   rows as the card-and-space placements (``agent_turn``), a waiting
   effect's as the effect with its target, as the older engine offered them
   (``agents.engine_order.older_engine_wholes``: of the actions now one per
   printing entity, only the one that engine took);
2. each mapped to a row of the file's own template list
   (``action_templates``) -- as it is, else without ``printed``, else
   without ``printed`` and ``source`` (``older_row``);
3. the file's own policy head (its rows, not the migrated ones) scores
   them on the current observation (the trunk's first layer is moved by
   segment like any older file); a whole action with no row scores 0, as an
   untrained row does in ``NetworkAgent``;
4. the softmax over the whole actions is summed onto each one's row of
   the decision (the step toward it).

A decision the older engine never asked -- a Conflict reward's or a
Contract's icons in the seat's order (stage B2) -- takes that engine's
fixed answer (``engine_order_answer``), and one with no mapped whole action
goes to the heuristic, as ``NetworkAgent`` does with untrained rows.

A search seat given such a file (``search:<path>``, ``reads_older_rows``)
plays it the same way: its candidates are ranked by ``row_scores``, its
playouts are ``OlderNetworkAgent`` games and its leaves the file's value
head (``agents.network_search_agent``).
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

import numpy as np
import torch
from torch import Tensor

from dune_imperium.adapters.action_codec import _normalize_arguments
from dune_imperium.agents.agent_turn_steps import PlacementMemory, placements_for_steps
from dune_imperium.agents.engine_order import engine_order_answer
from dune_imperium.agents.heuristic_agent import HeuristicAgent
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GameState
from dune_imperium.training.checkpoint import load_checkpoint
from dune_imperium.training.network import PolicyValueNetwork
from dune_imperium.training.policy import (
    BatchPolicy,
    PolicyRequest,
    encoded_view,
    without_undo_actions,
)
from dune_imperium.training.trunk_cache import TrunkCache

TemplateKey = tuple[str, tuple[tuple[str, Any], ...]]

# How a decision was answered (``TeacherAnswer.source``).
NETWORK = "network"
ENGINE_ORDER = "engine_order"
FALLBACK = "fallback"

_STRIPPED = (("printed",), ("printed", "source"))

# The first codec that offers an Agent turn as a card pick and a space pick
# (stage B1). An MLP file written before it reaches only a few rows of a
# current catalog -- 84 of 4,311 for the play network -- so a seat plays it
# through this module instead of its migrated rows (``reads_older_rows``).
STEP_CODEC_VERSION: Final = 150


@dataclass(frozen=True, slots=True)
class OlderNetwork:
    """A checkpoint's trunk on current observations and its own head."""

    network: PolicyValueNetwork
    weight: Tensor  # [file rows, width]: the file's own policy head
    bias: Tensor  # [file rows]
    rows: Mapping[TemplateKey, int]  # the file's template -> its head row
    codec_version: int
    path: str

    def scores(
        self,
        observation: np.ndarray,
        rows: Sequence[int | None],
        trunks: TrunkCache | None = None,
    ) -> tuple[np.ndarray, float]:
        """Logits of ``rows`` (0 for None) and the value, on one observation;
        ``trunks`` hands back a trunk a search decision already read."""

        with torch.no_grad():
            if trunks is None:
                batch = torch.from_numpy(observation).unsqueeze(0)
                hidden = self.network.trunk(batch)[0]
            else:
                hidden = trunks.hidden(self.network, observation)[0]
            value = float(self.network.value_head(hidden).item())
            known = [index for index, row in enumerate(rows) if row is not None]
            logits = np.zeros(len(rows), dtype=np.float64)
            if known:
                picked = torch.tensor([rows[index] for index in known])
                values = self.weight[picked] @ hidden + self.bias[picked]
                logits[known] = values.numpy()
        return logits, value


def _key(entry: Sequence[Any]) -> TemplateKey:
    action_id, arguments = entry
    return str(action_id), tuple((str(name), value) for name, value in arguments)


def load_older_network(path: Path) -> OlderNetwork:
    """Load an MLP checkpoint with its own policy-head rows kept."""

    network, info = load_checkpoint(path)
    if info.arch != "mlp":
        raise ValueError(f"an older teacher must be an MLP, not {info.arch}")
    document = torch.load(path, map_location="cpu", weights_only=True)
    templates = document.get("action_templates")
    if templates is None:
        raise ValueError("the checkpoint carries no template list")
    rows = {_key(entry): index for index, entry in enumerate(templates)}
    weight = document["state_dict"]["policy_head.weight"].to(torch.float32)
    bias = document["state_dict"]["policy_head.bias"].to(torch.float32)
    if weight.shape[0] != len(rows):
        raise ValueError("checkpoint head does not match its template list")
    network.eval()
    return OlderNetwork(
        network=network,
        weight=weight,
        bias=bias,
        rows=rows,
        codec_version=int(document["action_codec_version"]),
        path=str(path),
    )


@lru_cache(maxsize=4)
def _cached_older(path: str, modified: float) -> OlderNetwork:
    del modified  # part of the key so a rewritten file reloads
    return load_older_network(Path(path))


def cached_older_network(path: str | Path) -> OlderNetwork:
    """``load_older_network`` once per process and file."""

    resolved = str(Path(path).expanduser())
    return _cached_older(resolved, os.path.getmtime(resolved))


@lru_cache(maxsize=16)
def _file_kind(path: str, modified: float) -> tuple[int, str] | None:
    """The file's codec version and architecture, or None when it cannot be
    read so (``load_checkpoint`` then reports what is wrong with it)."""

    del modified  # part of the key so a rewritten file is read again
    try:
        document = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
        arch = document.get("arch")
        kind = "mlp" if arch is None else str(arch.get("kind", "mlp"))
        return int(document["action_codec_version"]), kind
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError, OSError):
        return None


def reads_older_rows(path: str | Path) -> bool:
    """Whether a seat plays ``path`` through this module: an MLP file of a
    codec before ``STEP_CODEC_VERSION`` (the only architecture
    ``load_older_network`` reads)."""

    resolved = str(Path(path).expanduser())
    found = _file_kind(resolved, os.path.getmtime(resolved))
    return found is not None and found[1] == "mlp" and found[0] < STEP_CODEC_VERSION


def load_older_agent(path: str, *, seed: int = 0) -> OlderNetworkAgent:
    """A greedy ``OlderNetworkAgent`` of a file, loaded once per process."""

    return OlderNetworkAgent(cached_older_network(path), seed=seed)


def older_row(rows: Mapping[TemplateKey, int], action: DomainAction) -> int | None:
    """The file's row for a whole action, or None (module docstring, 2)."""

    arguments = _normalize_arguments(action.arguments, action.actor)
    row = rows.get((action.action_id, arguments))
    if row is not None:
        return row
    for names in _STRIPPED:
        stripped = tuple(item for item in arguments if item[0] not in names)
        if stripped != arguments:
            row = rows.get((action.action_id, stripped))
            if row is not None:
                return row
    return None


@dataclass(frozen=True, slots=True)
class TeacherAnswer:
    """The teacher's distribution over a decision's legal actions."""

    probabilities: np.ndarray  # float64, parallel to the legal actions
    value: float  # the file's value of the position
    source: str  # NETWORK, ENGINE_ORDER or FALLBACK
    wholes: int = 0  # whole actions scored
    unmapped: tuple[str, ...] = ()  # action ids of whole actions with no row


@dataclass(slots=True)
class OlderTeacher:
    """Answer current decisions with an ``OlderNetwork`` (module docstring).

    ``key`` names the seat a decision belongs to (a game and seat in
    self-play): each key has its own heuristic for the decisions with no
    mapped whole action, as each ``NetworkAgent`` seat has its own.
    """

    older: OlderNetwork
    seed: int = 0
    _fallbacks: dict[object, HeuristicAgent] = field(default_factory=dict)
    counts: Counter[str] = field(default_factory=Counter)
    unmapped: Counter[str] = field(default_factory=Counter)
    # A search seat's trunks of the decision it answers (``TrunkCache``).
    trunks: TrunkCache | None = None

    def fallback(self, key: object) -> HeuristicAgent:
        agent = self._fallbacks.get(key)
        if agent is None:
            agent = self._fallbacks[key] = HeuristicAgent(seed=self.seed)
        return agent

    def wholes(
        self,
        state: GameState,
        player: int,
        legal_actions: tuple[DomainAction, ...],
    ) -> tuple[tuple[DomainAction, ...], list[int]]:
        """The whole actions of the decision and each one's legal row."""

        position = {action: index for index, action in enumerate(legal_actions)}
        steps = placements_for_steps(state, player, legal_actions)
        if steps is None:
            return legal_actions, list(range(len(legal_actions)))
        shown, to_row = steps
        kept: list[DomainAction] = []
        targets: list[int] = []
        for whole in shown:
            target = position.get(to_row(whole))
            if target is not None:
                kept.append(whole)
                targets.append(target)
        return tuple(kept), targets

    def untrained_only(
        self,
        state: GameState,
        player: int,
        legal_actions: tuple[DomainAction, ...],
    ) -> bool:
        """Whether no whole action of the decision has a row of the file:
        ``answer`` hands such a decision to the heuristic."""

        wholes, _ = self.wholes(state, player, legal_actions)
        return all(older_row(self.older.rows, whole) is None for whole in wholes)

    def row_scores(
        self,
        state: GameState,
        player: int,
        legal_actions: tuple[DomainAction, ...],
        observation: np.ndarray,
    ) -> np.ndarray:
        """Each legal row's log probability under ``answer``'s distribution
        (the softmax over the whole actions, summed onto their rows), in
        log-sum-exp form so a small probability never rounds to zero; a row
        no whole action reaches scores -inf. A search ranks its candidates
        by it."""

        scores = np.full(len(legal_actions), -np.inf, dtype=np.float64)
        wholes, targets = self.wholes(state, player, legal_actions)
        if not wholes:
            return scores
        rows = [older_row(self.older.rows, whole) for whole in wholes]
        logits, _ = self.older.scores(observation, rows, self.trunks)
        total = np.logaddexp.reduce(logits)
        for target in set(targets):
            mine = logits[[index for index, row in enumerate(targets) if row == target]]
            scores[target] = np.logaddexp.reduce(mine) - total
        return scores

    def value(self, observation: np.ndarray) -> float:
        """The file's value of the position."""

        return self.older.scores(observation, [], self.trunks)[1]

    def whole_scores(
        self,
        view: PlayerView,
        wholes: Sequence[DomainAction],
        observation: np.ndarray | None,
    ) -> tuple[np.ndarray, float, list[int | None]]:
        """Logits of ``wholes`` (0 with no row), the value, and the rows."""

        rows = [older_row(self.older.rows, whole) for whole in wholes]
        if observation is None:
            observation = encoded_view(view)
        logits, value = self.older.scores(observation, rows, self.trunks)
        return logits, value, rows

    def answer(
        self,
        state: GameState,
        player: int,
        view: PlayerView,
        legal_actions: tuple[DomainAction, ...],
        observation: np.ndarray | None = None,
        *,
        key: object = None,
    ) -> TeacherAnswer:
        """The distribution over ``legal_actions`` (no undo rows among them)
        and the file's value of the position."""

        if observation is None:
            observation = encoded_view(view)
        answer = engine_order_answer(state, player, legal_actions)
        if answer is not None:
            index = legal_actions.index(answer)
            return self._one_hot(
                observation, index, len(legal_actions), ENGINE_ORDER
            )
        wholes, targets = self.wholes(state, player, legal_actions)
        rows = [older_row(self.older.rows, whole) for whole in wholes]
        missing = tuple(
            whole.action_id for whole, row in zip(wholes, rows, strict=True)
            if row is None
        )
        if not wholes or all(row is None for row in rows):
            self.unmapped.update(missing)
            choice = self.fallback(key).choose_action_with_state(
                state, view, legal_actions
            )
            return self._one_hot(
                observation,
                legal_actions.index(choice),
                len(legal_actions),
                FALLBACK,
                missing,
            )
        logits, value = self.older.scores(observation, rows, self.trunks)
        weights = np.exp(logits - logits.max())
        weights /= weights.sum()
        probabilities = np.zeros(len(legal_actions), dtype=np.float64)
        np.add.at(probabilities, np.asarray(targets), weights)
        self.counts[NETWORK] += 1
        if missing:
            self.counts["network_with_unmapped"] += 1
            self.unmapped.update(missing)
        return TeacherAnswer(
            probabilities=probabilities,
            value=value,
            source=NETWORK,
            wholes=len(wholes),
            unmapped=missing,
        )

    def _one_hot(
        self,
        observation: np.ndarray,
        index: int,
        size: int,
        source: str,
        missing: tuple[str, ...] = (),
    ) -> TeacherAnswer:
        self.counts[source] += 1
        probabilities = np.zeros(size, dtype=np.float64)
        probabilities[index] = 1.0
        _, value = self.older.scores(observation, [], self.trunks)
        return TeacherAnswer(
            probabilities=probabilities,
            value=value,
            source=source,
            unmapped=missing,
        )


class OlderNetworkAgent:
    """Greedy play of an ``OlderTeacher`` (tournament seat ``older:<path>``).

    It picks the whole action the file scores highest and plays its steps
    without weighing them again (``PlacementMemory``), as ``NetworkAgent``
    played one row when a placement was one row. Like ``NetworkAgent`` it
    does not take a whole action again at an observation where it already
    took it this round, unless nothing else is left: greedy, the file sets
    an Arrakeen Scouts bid again and again rather than confirm it (a
    30,000-action game in the 2026-10-21 feasibility check).
    """

    def __init__(
        self,
        older: OlderNetwork,
        *,
        seed: int = 0,
        trunks: TrunkCache | None = None,
    ) -> None:
        self.teacher = OlderTeacher(older, seed=seed, trunks=trunks)
        self._memory = PlacementMemory()
        self._round = -1
        self._taken: dict[bytes, set[DomainAction]] = {}

    def choose_action(
        self, observation: PlayerView, legal_actions: tuple[DomainAction, ...]
    ) -> DomainAction:
        raise ValueError("an older-network seat needs the state")

    def choose_action_with_state(
        self,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        legal_actions = without_undo_actions(legal_actions)
        player = legal_actions[0].actor
        answer = engine_order_answer(state, player, legal_actions)
        if answer is not None:
            self.teacher.counts[ENGINE_ORDER] += 1
            return answer

        if observation.round_number != self._round:
            self._round = observation.round_number
            self._taken.clear()

        # Encoded only when the file is asked: the later step of a placement
        # or whole action it chose is answered from memory (about one call
        # in seven inside a search seat's playouts).
        def decide(shown: tuple[DomainAction, ...]) -> DomainAction:
            encoded = encoded_view(observation)
            taken = self._taken.setdefault(encoded.tobytes(), set())
            logits, _, rows = self.teacher.whole_scores(observation, shown, encoded)
            if all(row is None for row in rows):
                self.teacher.counts[FALLBACK] += 1
                return self.teacher.fallback(None).choose_action_with_state(
                    state, observation, legal_actions
                )
            self.teacher.counts[NETWORK] += 1
            fresh = [index for index, whole in enumerate(shown) if whole not in taken]
            if fresh:
                best = max(fresh, key=lambda index: logits[index])
            else:
                best = int(np.argmax(logits))
            taken.add(shown[best])
            return shown[best]

        return self._memory.choose(state, player, legal_actions, decide)


# Each game's teacher answers in order: the legal catalog indices offered
# and the answer over them (``OlderTeacherPolicy.answers``).
GameAnswers = dict[int, list[tuple[tuple[int, ...], TeacherAnswer]]]


def _label(
    teacher: OlderTeacher, answers: GameAnswers, request: PolicyRequest
) -> TeacherAnswer:
    """The teacher's answer to ``request``, kept at the end of its game's list."""

    answer = teacher.answer(
        request.state,
        request.seat,
        request.view,
        request.legal_actions,
        request.observation,
        key=(request.game, request.seat),
    )
    answers.setdefault(request.game, []).append((request.legal_indices, answer))
    return answer


@dataclass(slots=True)
class OlderTeacherPolicy:
    """Sampled self-play policy of an ``OlderTeacher`` that keeps its answers.

    ``answers[game]`` lists each of that game's decisions in order: the
    legal catalog indices offered and the teacher's answer over them. The
    runner records the same decisions as steps, so the two line up
    (``training.older_distill``).
    """

    teacher: OlderTeacher
    seed: int
    answers: GameAnswers = field(default_factory=dict)
    _rng: np.random.Generator | None = None

    def act(self, requests: Sequence[PolicyRequest]) -> Sequence[int]:
        if self._rng is None:
            self._rng = np.random.default_rng(self.seed)
        chosen: list[int] = []
        for request in requests:
            answer = _label(self.teacher, self.answers, request)
            size = len(answer.probabilities)
            pick = int(self._rng.choice(size, p=answer.probabilities))
            chosen.append(request.legal_indices[pick])
        return chosen


@dataclass(slots=True)
class LabelledStudentPolicy:
    """A student plays; an ``OlderTeacher`` labels every decision it is asked.

    Student-position distillation (DAgger; Czarnecki et al. 2019,
    "Distilling Policy Distillation"): the data's positions are the ones
    the student itself reaches, while each keeps the teacher's distribution
    and value. ``student`` answers every request -- for the data a
    ``TorchBatchPolicy`` sampling the student network at temperature 1, as
    the collector's learner does -- after the teacher answered it, and
    ``answers`` keeps those answers exactly as ``OlderTeacherPolicy.answers``
    does, so ``older_distill.teacher_rows`` lines them up with the recorded
    steps the same way.
    """

    teacher: OlderTeacher
    student: BatchPolicy
    answers: GameAnswers = field(default_factory=dict)

    def act(self, requests: Sequence[PolicyRequest]) -> Sequence[int]:
        for request in requests:
            _label(self.teacher, self.answers, request)
        return self.student.act(requests)
