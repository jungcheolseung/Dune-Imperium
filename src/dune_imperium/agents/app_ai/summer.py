"""Value accumulators that mirror the app's ``Canis.ai.value.AIValueSummer``.

The app AI builds most values as a running sum with named reasons. Two
operations matter for faithfulness: ``Add`` appends a term, and
``AIProfileAbsUtils::Multiply`` scales the running sum *so far* (later terms
are not scaled). Porting a formula therefore means replaying its Add/Multiply
calls in the binary's order, which these classes make explicit.

Reasons are kept only while ``Summer.tracing`` is on (a debugging aid, like
the app's stripped ``AILog``); the arithmetic never depends on them.
"""

from typing import ClassVar


class Summer:
    """A float running sum: the port of ``AIValueSummer<double>``."""

    __slots__ = ("reasons", "value")

    tracing: ClassVar[bool] = False

    def __init__(self, value: float = 0.0) -> None:
        self.value = float(value)
        self.reasons: list[tuple[str, str, float]] | None = (
            [] if Summer.tracing else None
        )

    @property
    def sum(self) -> float:
        """The app's ``Sum``."""

        return self.value

    def add(self, reason: str, amount: float) -> Summer:
        """``Add(reason, amount)``: append one term."""

        self.value += amount
        if self.reasons is not None:
            self.reasons.append(("+", reason, amount))
        return self

    def multiply(self, reason: str, factor: float) -> Summer:
        """``AIProfileAbsUtils::Multiply``: scale the sum accumulated so far."""

        self.value *= factor
        if self.reasons is not None:
            self.reasons.append(("*", reason, factor))
        return self

    def merge(self, other: Summer) -> Summer:
        """``Merge``: add another summer's total (and its reasons)."""

        self.value += other.value
        if self.reasons is not None and other.reasons is not None:
            self.reasons.extend(other.reasons)
        return self

    def __repr__(self) -> str:
        return f"Summer({self.value!r})"


class IntSummer:
    """An int running sum: the port of ``AIValueSummer<int>``.

    The app's integer summers (strength estimates, unit counts) add whole
    numbers only; a fractional estimate is rounded by the caller first with
    ``app_round`` (``Convert.ToInt32``), never truncated.
    """

    __slots__ = ("reasons", "value")

    def __init__(self, value: int = 0) -> None:
        self.value = int(value)
        self.reasons: list[tuple[str, str, float]] | None = (
            [] if Summer.tracing else None
        )

    @property
    def sum(self) -> int:
        """The app's ``Sum``."""

        return self.value

    def add(self, reason: str, amount: int) -> IntSummer:
        """``Add(reason, amount)``."""

        self.value += amount
        if self.reasons is not None:
            self.reasons.append(("+", reason, float(amount)))
        return self

    def merge(self, other: IntSummer) -> IntSummer:
        """``Merge``."""

        self.value += other.value
        if self.reasons is not None and other.reasons is not None:
            self.reasons.extend(other.reasons)
        return self

    def __repr__(self) -> str:
        return f"IntSummer({self.value!r})"


def app_round(value: float) -> int:
    """``System.Convert.ToInt32(double)``: round half to even, like ``round``."""

    return round(value)
