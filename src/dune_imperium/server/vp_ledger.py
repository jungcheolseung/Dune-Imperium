"""Each seat's Victory Point changes, step by step: the seat panel's VP list.

Victory Points change at about two dozen places in the engine (an Influence
track reaching 2, an Alliance gained, passed on or lost, a Conflict reward,
a Battle icon match, Endgame cards, Intrigue cards, the research and
Tleilaxu tracks, Tech, ...), and most of them emit no Victory Point event:
reaching 2 Influence logs ``influence_gained`` alone, and an Alliance passing
from one seat to another logs ``alliance_transferred`` while one seat loses
a point and the other gains one. So the ledger does not read events. It walks
the live steps of the game from the opening state, as an undo or a review
rebuilds a state (``sessions._state_after``), and compares every seat's
``victory_points`` before and after each step.

A row names the step by its index in the session log, the index every
client already holds for the log entry (``_log_entry_json``), so a client
names the cause from its own, already redacted, log entry and can scroll to
it. Everything else in a row is public: the round, the seat and how its
Victory Points moved, which the board's track shows every seat. Steps taken
back are not live and never appear; chance steps are, and count like any
other step (the pause before a Conflict reward carries the reward).

The ledger is kept per session and extended as the game goes on
(``extend_ledger``): it remembers how many live steps it walked and the log
index of the last one. The log only ever grows, and a step logged after an
undo has a larger index than every step before it, so while the live step at
that position still has that index, every step the ledger walked is still
live and in the same order.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from dune_imperium.core.replay import ReplayStep
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.server.persistence import JsonObject, JsonValue


@dataclass(frozen=True, slots=True)
class VpChange:
    """One seat's Victory Points moved by one live step."""

    # The step's index in the session log (``LoggedStep`` entries and undo
    # markers alike are counted), as a client's log entries carry it.
    index: int
    # The round the step was taken in: the round before the step, so a step
    # that ends a round counts its points to the round it ended.
    round: int
    seat: int
    delta: int
    # The seat's Victory Points after the step.
    total: int


@dataclass(frozen=True, slots=True)
class VpLedger:
    """The ledger of a game's first ``steps`` live steps."""

    steps: int
    # The log index of the last live step walked; -1 before any.
    last_index: int
    # The state after those steps, where the walk goes on from.
    state: GameState
    # Every seat's Victory Points in the opening state.
    start: tuple[int, ...]
    changes: tuple[VpChange, ...]

    def extends(self, live: Sequence[tuple[int, ReplayStep]]) -> bool:
        """Whether every step walked is still the same live step of ``live``.

        ``live`` is the game's live steps in order, each with its log index.
        """

        if self.steps > len(live):
            return False
        return self.steps == 0 or live[self.steps - 1][0] == self.last_index


def start_ledger(state: GameState) -> VpLedger:
    """The empty ledger of a game whose opening state is ``state``."""

    return VpLedger(
        steps=0,
        last_index=-1,
        state=state,
        start=tuple(player.victory_points for player in state.players),
        changes=(),
    )


def step_changes(
    before: GameState, after: GameState, index: int
) -> tuple[VpChange, ...]:
    """The Victory Point changes of one step, seat by seat (zero ones left out)."""

    pairs = zip(before.players, after.players, strict=True)
    return tuple(
        VpChange(
            index=index,
            round=before.round_number,
            seat=seat,
            delta=now.victory_points - was.victory_points,
            total=now.victory_points,
        )
        for seat, (was, now) in enumerate(pairs)
        if now.victory_points != was.victory_points
    )


def extend_ledger(
    engine: UprisingRulesEngine,
    ledger: VpLedger,
    live: Sequence[tuple[int, ReplayStep]],
) -> VpLedger:
    """Walk the live steps the ledger has not walked yet.

    ``live`` is every live step of the game in order, each with its log
    index, and must extend the ledger (``VpLedger.extends``).
    """

    if not ledger.extends(live):
        raise ValueError("the live steps do not extend this ledger")
    if ledger.steps == len(live):
        return ledger
    state = ledger.state
    changes = list(ledger.changes)
    for index, step in live[ledger.steps :]:
        after = engine.apply(state, step).state
        changes.extend(step_changes(state, after, index))
        state = after
    return VpLedger(
        steps=len(live),
        last_index=live[-1][0],
        state=state,
        start=ledger.start,
        changes=tuple(changes),
    )


def ledger_json(ledger: VpLedger) -> JsonObject:
    """The public payload: the opening points and every change, in order."""

    entries: list[JsonValue] = [
        {
            "index": change.index,
            "round": change.round,
            "seat": change.seat,
            "delta": change.delta,
            "total": change.total,
        }
        for change in ledger.changes
    ]
    return {
        "step_count": ledger.steps,
        "start": list(ledger.start),
        "entries": entries,
    }
