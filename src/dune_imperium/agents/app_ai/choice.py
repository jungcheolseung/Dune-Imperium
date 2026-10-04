"""The app's answer rule: ``worm.canis.ai.WormAIProfile::MakeChoice``.

``MakeChoice`` (@0x48fef80) evaluates every source of a prompt, shuffles all
evaluated candidates (including those worth 0 or less), keeps the ones worth
strictly more than 0, stable-sorts them by value descending and answers with
the first. With no positive candidate it sends an empty answer on an optional
prompt (pass, decline, Reveal turn, End Turn) and a uniformly random legal
answer on a forced one (``PlayerEntity::DefaultRandomChoice``).

The app draws its shuffle from a wall-clock seeded ``System.Random``; the port
draws from the agent's own seeded ``random.Random`` so games replay. The
outcome distribution is the same: a uniform pick among the tied best.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass

from dune_imperium.core.actions import DomainAction


@dataclass(frozen=True, slots=True)
class Candidate:
    """One evaluated answer: the action that realises it and its app value."""

    action: DomainAction
    value: float
    label: str = ""


def make_choice(
    candidates: Sequence[Candidate], rng: random.Random
) -> Candidate | None:
    """Return the app's pick among ``candidates``, or None for the empty answer.

    Shuffle everything, keep ``value > 0`` (strict), stable-sort descending,
    take the first. None means no candidate is worth more than 0.
    """

    pool = list(candidates)
    rng.shuffle(pool)
    positive = [candidate for candidate in pool if candidate.value > 0.0]
    if not positive:
        return None
    positive.sort(key=lambda candidate: candidate.value, reverse=True)
    return positive[0]


def default_random_choice(
    legal_actions: Sequence[DomainAction], rng: random.Random
) -> DomainAction:
    """``DefaultRandomChoice``: a uniformly random legal answer (forced prompt)."""

    return legal_actions[rng.randrange(len(legal_actions))]


def first_strictly_best[T](items: Sequence[tuple[T, float]]) -> tuple[T, float] | None:
    """Keep-best rule of ``WormAIChoiceSelectionWithTargets::UpdateSelection*``.

    Within one source the app overwrites its stored answer only when a later
    candidate is strictly better, so the first strictly-best in evaluation
    order wins. (The first call always sticks, even at a value of 0 or less.)
    """

    best: tuple[T, float] | None = None
    for item, value in items:
        if best is None or value > best[1]:
            best = (item, value)
    return best
