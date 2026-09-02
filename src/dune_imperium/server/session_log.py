"""The server-side session log: every step, its events, and undo history.

The engine's ``GameState.event_log`` is part of the state, so taking a step
back also drops the events it produced. OQ-010 wants the opposite ("once
revealed, information stays re-checkable"), so the server keeps its own
append-only log: one ``LoggedStep`` per applied step — including steps that
were later undone — plus one ``LoggedUndo`` marker per undo. The live game
is the sequence of ``LoggedStep`` entries that are not ``undone``.

Two visibility facts are computed when a step is applied, from
``known_card_seats`` (the visibility authority in ``core.observation``):

- ``reveals``: the step let some seat learn a card it could not identify
  before, other than the actor disclosing a card only the actor knew (an
  Intrigue play, a discard from hand). Such a step cannot be undone: a draw
  would let the owner redraw with knowledge of the deck top, and a refilled
  Imperium Row or a flipped Contract cannot be un-seen. This is the M11
  slice 6 boundary the user fixed on 2026-09-02 (see implementation-plan).
- ``hidden_arguments``: action argument values naming cards that are still
  not public after the step, redacted for every seat but the actor when the
  live log is served.
"""

from dataclasses import dataclass, replace

from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import known_card_seats
from dune_imperium.core.replay import ReplayStep
from dune_imperium.core.state import GameState


@dataclass(frozen=True, slots=True)
class LoggedStep:
    """One applied step with the events it produced."""

    step: ReplayStep
    events: tuple[GameEvent, ...]
    reveals: bool
    hidden_arguments: frozenset[str]
    undone: bool = False

    @property
    def actor(self) -> int | None:
        return None if isinstance(self.step, ChanceOutcome) else self.step.actor


@dataclass(frozen=True, slots=True)
class LoggedUndo:
    """``seat`` took back the ``count`` live steps logged just before."""

    seat: int
    count: int


type LogEntry = LoggedStep | LoggedUndo


def reveals_hidden_information(
    before: GameState, after: GameState, actor: int | None
) -> bool:
    """Return whether the step from ``before`` to ``after`` revealed a card.

    A card counts as revealed when a seat can identify it after the step
    but could not before. The one exception is the actor voluntarily
    disclosing a card that only the actor knew (playing an Intrigue,
    discarding or trashing from hand, revealing the hand): that is the
    actor's own loss to accept when undoing. Chance steps have no actor,
    so any of their reveals count.
    """

    everyone = frozenset(range(before.config.players))
    known_before = known_card_seats(before)
    known_after = known_card_seats(after)
    own_secret = frozenset({actor}) if actor is not None else None
    for card_id, seats_before in known_before.items():
        seats_after = known_after.get(card_id, everyone)
        if seats_after <= seats_before:
            continue
        if own_secret is not None and seats_before == own_secret:
            continue
        return True
    return False


def hidden_argument_values(step: ReplayStep, after: GameState) -> frozenset[str]:
    """Return action argument values that name a card still hidden after the step."""

    if isinstance(step, ChanceOutcome):
        return frozenset()
    known = known_card_seats(after)
    everyone = frozenset(range(after.config.players))
    return frozenset(
        value
        for _, value in step.arguments
        if isinstance(value, str) and known.get(value, everyone) != everyone
    )


def log_step(
    before: GameState,
    after: GameState,
    step: ReplayStep,
    events: tuple[GameEvent, ...],
) -> LoggedStep:
    """Build the log entry for one applied step."""

    actor = None if isinstance(step, ChanceOutcome) else step.actor
    return LoggedStep(
        step=step,
        events=events,
        reveals=reveals_hidden_information(before, after, actor),
        hidden_arguments=hidden_argument_values(step, after),
    )


def live_steps(log: list[LogEntry]) -> list[LoggedStep]:
    """Return the log entries that make up the current game, in order."""

    return [
        entry
        for entry in log
        if isinstance(entry, LoggedStep) and not entry.undone
    ]


def undo_window(log: list[LogEntry], seat: int) -> int:
    """Count how many trailing live steps ``seat`` may take back.

    The window holds the seat's own consecutive latest actions and closes
    at the first step that is a chance outcome, another seat's action, or
    a step that revealed hidden information (which cannot be undone
    itself, so the window closes below it).
    """

    count = 0
    for entry in reversed(live_steps(log)):
        if entry.actor != seat or entry.reveals:
            break
        count += 1
    return count


def mark_undone(log: list[LogEntry], seat: int, count: int) -> None:
    """Flag the last ``count`` live steps as undone and append the marker."""

    remaining = count
    for index in range(len(log) - 1, -1, -1):
        if remaining == 0:
            break
        entry = log[index]
        if isinstance(entry, LoggedStep) and not entry.undone:
            if entry.actor != seat:
                raise ValueError("cannot undo another seat's step")
            log[index] = replace(entry, undone=True)
            remaining -= 1
    if remaining:
        raise ValueError("fewer live steps than the undo count")
    log.append(LoggedUndo(seat=seat, count=count))


def undo_history(log: list[LogEntry]) -> list[tuple[int, LoggedUndo, list[LoggedStep]]]:
    """Return every undo as (live step index it rewound to, marker, undone steps)."""

    history: list[tuple[int, LoggedUndo, list[LoggedStep]]] = []
    live_position = 0
    pending: list[LoggedStep] = []
    for entry in log:
        if isinstance(entry, LoggedUndo):
            history.append((live_position, entry, pending[-entry.count :]))
            pending = []
        elif entry.undone:
            pending.append(entry)
        else:
            live_position += 1
            pending = []
    return history

