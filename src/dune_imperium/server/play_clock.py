"""The play clock: how long a game has been played, and by whom.

Two numbers per game ("게임 ui에 플레이한 시간이 기록되면 좋겠어", user,
2026-10-10, every recommendation accepted): the game time, which runs while
the server has the game loaded and unfinished, and each seat's time holding
control, a chess clock. A seat holds control while the game waits on it: its
own decisions, its answers inside another seat's turn, its decisions outside
the turns, and the time before it presses "턴 종료 ▶". AI seats count like
humans, pace waits included ("ai 좌석도 구분 없이 시간 세자").

The session decides who holds control, from public fields only (the pending
decision's owner, the held turn end, the thinking seat), so a clock tells no
seat anything the table does not show (``pacing``'s principle). This module
only keeps the totals: it is told the holder at every transition
(``settle``) and charges the time since the last one.

One refinement keeps a human from paying for the browser's narration: after
AI moves, the tables show their cards and banners for a few seconds
(``pacing.cue_seconds``) before the next human can be expected to act. Each
AI step's narration is a segment of time charged to that AI seat while a
human holds control; the human's clock runs in the gaps and after the last
segment. A human's own request (a move, a press, an undo) ends whatever
narration is still due: whoever acted was not waiting for the tables. Time
is never refunded: an undo rewinds the game, not the clock.

Values change only at transitions, so a summary read twice between them is
the same; a client adds the time since the last transition (the age the
snapshot reports) to what it was sent.
"""

from dataclasses import dataclass, field

from dune_imperium.server.persistence import JsonObject, JsonValue


@dataclass(slots=True)
class PlayClock:
    """Game time and per-seat control time of one session, in seconds.

    ``live`` is False until the session starts the clock (after a new
    game's first advance, or after a load's replay), so replayed steps never
    charge anyone. ``mark`` is the monotonic time of the last transition,
    ``holder`` the seat charged since then (``None``: nobody), ``grace``
    whether the narration segments apply to it (a human holder), and
    ``counting`` whether the game time runs (the game is unfinished).
    ``spell`` is the holder's own time since it took control. ``narration``
    holds (seat, start, end) segments in monotonic time, in order and never
    overlapping. ``known`` is False when the totals were lost: a load of a
    save that recorded none counts from the load.
    """

    seats: int
    elapsed: float = 0.0
    seat_seconds: list[float] = field(default_factory=list)
    known: bool = True
    live: bool = False
    mark: float = 0.0
    holder: int | None = None
    grace: bool = False
    counting: bool = False
    spell: float = 0.0
    narration: list[tuple[int, float, float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.seat_seconds:
            self.seat_seconds = [0.0] * self.seats

    def start(
        self,
        now: float,
        *,
        holder: int | None,
        grace: bool,
        counting: bool,
        elapsed: float = 0.0,
        seat_seconds: tuple[float, ...] | None = None,
        known: bool = True,
    ) -> None:
        """Start counting at ``now`` from the given totals."""

        self.elapsed = elapsed
        self.seat_seconds = (
            [0.0] * self.seats if seat_seconds is None else list(seat_seconds)
        )
        self.known = known
        self.live = True
        self.mark = now
        self.holder = holder
        self.grace = grace
        self.counting = counting
        self.spell = 0.0
        self.narration = []

    def settle(
        self, now: float, *, holder: int | None, grace: bool, counting: bool
    ) -> None:
        """Charge the time since the last transition, then hand over to ``holder``."""

        if not self.live:
            return
        now = max(now, self.mark)
        elapsed, seats, spell = self._charges(now)
        self.elapsed += elapsed
        for seat, seconds in enumerate(seats):
            self.seat_seconds[seat] += seconds
        self.spell = self.spell + spell if holder == self.holder else 0.0
        self.mark = now
        self.holder = holder
        self.grace = grace
        self.counting = counting
        self.narration = [segment for segment in self.narration if segment[2] > now]

    def narrate(self, seat: int, start: float, end: float) -> None:
        """Charge ``seat`` for the tables' narration of its step, if a human waits."""

        if not self.live or end <= start:
            return
        if self.narration:
            start = max(start, self.narration[-1][2])
        if end > start:
            self.narration.append((seat, start, end))

    def drop_narration(self) -> None:
        """Forget the narration still due: a human just acted, so was not waiting."""

        self.narration = []

    def extend_narration(self, start: float, end: float) -> None:
        """A chance step's cues right after an AI step's go on that seat's segment."""

        if not self.live or not self.narration or end <= start:
            return
        seat, begun, until = self.narration[-1]
        if until >= start:
            self.narration[-1] = (seat, begun, max(until, end))

    def totals(self, now: float) -> tuple[float, tuple[float, ...]]:
        """The game time and every seat's time as of ``now``, without settling."""

        if not self.live:
            return self.elapsed, tuple(self.seat_seconds)
        elapsed, seats, _ = self._charges(max(now, self.mark))
        pairs = zip(self.seat_seconds, seats, strict=True)
        return self.elapsed + elapsed, tuple(total + extra for total, extra in pairs)

    def payload(self) -> JsonObject:
        """The clock as of the last transition, for the summary.

        ``narration`` is the run of [seat, ms] pieces from the transition
        on, before ``running``'s own clock runs: the AI seats whose moves
        the tables are still showing, and the gaps between them, which are
        the holder's.
        """

        pieces: list[JsonValue] = []
        if self.grace and self.holder is not None:
            cursor = self.mark
            for seat, start, end in self.narration:
                if end <= cursor:
                    continue
                if start > cursor:
                    pieces.append([self.holder, _ms(start - cursor)])
                    cursor = start
                pieces.append([seat, _ms(end - cursor)])
                cursor = end
        return {
            "elapsed_ms": _ms(self.elapsed),
            "seat_ms": [_ms(seconds) for seconds in self.seat_seconds],
            "running": self.holder,
            "spell_ms": _ms(self.spell),
            "narration": pieces,
            "counting": self.counting,
            "known": self.known,
        }

    def age_ms(self, now: float) -> int:
        """Milliseconds since the last transition (the snapshot envelope's)."""

        return _ms(max(0.0, now - self.mark)) if self.live else 0

    def _charges(self, now: float) -> tuple[float, list[float], float]:
        """What [mark, now] adds: game time, each seat's time, the holder's spell."""

        span = now - self.mark
        seats = [0.0] * self.seats
        elapsed = span if self.counting else 0.0
        holder = self.holder
        if holder is None or span <= 0:
            return elapsed, seats, 0.0
        if not self.grace:
            seats[holder] = span
            return elapsed, seats, span
        cursor = self.mark
        own = 0.0
        for seat, start, end in self.narration:
            if end <= cursor:
                continue
            if start >= now:
                break
            begin = max(start, cursor)
            own += begin - cursor
            stop = min(end, now)
            seats[seat] += stop - begin
            cursor = stop
            if cursor >= now:
                break
        own += now - cursor
        seats[holder] += own
        return elapsed, seats, own


def _ms(seconds: float) -> int:
    return round(seconds * 1000)
