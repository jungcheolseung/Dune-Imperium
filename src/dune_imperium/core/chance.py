"""Seeded chance resolution and recorded-outcome replay."""

import random
from dataclasses import dataclass

from dune_imperium.core.decisions import ChanceDecision


@dataclass(frozen=True, slots=True)
class ChanceOutcome:
    """The complete, serializable result of one chance decision."""

    decision_id: str
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.decision_id:
            raise ValueError("chance outcome decision_id must not be empty")
        if not self.values:
            raise ValueError("chance outcome values must not be empty")


def validate_chance_outcome(
    decision: ChanceDecision,
    outcome: ChanceOutcome,
) -> None:
    """Raise ``ValueError`` unless ``outcome`` can resolve ``decision``."""

    if outcome.decision_id != decision.decision_id:
        raise ValueError("chance outcome does not match the current decision")
    if len(outcome.values) != decision.count:
        raise ValueError("chance outcome has the wrong number of values")
    if any(value not in decision.options for value in outcome.values):
        raise ValueError("chance outcome contains an unavailable value")
    if not decision.with_replacement and len(outcome.values) != len(
        set(outcome.values)
    ):
        raise ValueError("chance outcome repeats a value without replacement")


class ChanceReplayError(ValueError):
    """Raised when recorded chance data cannot resolve the current decision."""


class ChanceResolver:
    """Resolve decisions from a local RNG or an injected outcome stream."""

    def __init__(
        self,
        seed: int,
        recorded: tuple[ChanceOutcome, ...] | None = None,
    ) -> None:
        if seed < 0:
            raise ValueError("seed must not be negative")
        self._random = random.Random(seed)
        self._recorded = recorded
        self._cursor = 0
        self._outcomes: list[ChanceOutcome] = []

    @property
    def outcomes(self) -> tuple[ChanceOutcome, ...]:
        """Return outcomes consumed or generated so far."""

        return tuple(self._outcomes)

    @property
    def exhausted(self) -> bool:
        """Whether every injected replay outcome has been consumed."""

        return self._recorded is None or self._cursor == len(self._recorded)

    def resolve(self, decision: ChanceDecision) -> ChanceOutcome:
        """Resolve and record one decision."""

        if self._recorded is not None:
            if self._cursor >= len(self._recorded):
                raise ChanceReplayError("recorded chance stream ended early")
            outcome = self._recorded[self._cursor]
            self._cursor += 1
            try:
                validate_chance_outcome(decision, outcome)
            except ValueError as error:
                raise ChanceReplayError(str(error)) from error
        else:
            if decision.with_replacement:
                values = tuple(
                    self._random.choice(decision.options)  # noqa: S311
                    for _ in range(decision.count)
                )
            else:
                values = tuple(self._random.sample(decision.options, k=decision.count))
            outcome = ChanceOutcome(decision_id=decision.decision_id, values=values)

        self._outcomes.append(outcome)
        return outcome
