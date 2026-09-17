"""The doorbell hub: fan a game's latest change out to its event streams.

The session layer knows nothing about asyncio: after every change it calls
``DoorbellHub.publish`` on whatever worker thread made the change. The hub
hands the payload to the server's event loop, where each open stream
(``GET /games/{id}/events``, Server-Sent Events) picks it up.

A doorbell is state, not a message queue. Each subscriber keeps only the
newest payload, so a burst of changes collapses into one notification, a
slow client cannot make the server hold a backlog, and nothing ever has to
be replayed: a client that reconnects is greeted with the current payload
(``hello``) and refreshes if its picture is stale. Payloads carry a
sequence number because two threads may publish out of order once the
session lock is released; an older one never overwrites a newer one.

SSE rather than WebSocket: the client only listens (its actions stay plain
POSTs), ``EventSource`` reconnects by itself, and a streaming response
needs no dependency the server does not already have.
"""

import asyncio
import json
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Final

from dune_imperium.server.persistence import JsonObject

DEFAULT_HEARTBEAT_SECONDS: Final = 15.0

HELLO: Final = "hello"
CHANGE: Final = "change"
CLOSED: Final = "closed"


def format_event(event: str, payload: JsonObject) -> str:
    """Encode one Server-Sent Event; the sequence number doubles as its ID."""

    lines = [f"event: {event}"]
    sequence = payload.get("seq")
    if sequence is not None:
        lines.append(f"id: {sequence}")
    lines.append(f"data: {json.dumps(payload, ensure_ascii=False)}")
    return "\n".join(lines) + "\n\n"


# A comment line: ignored by ``EventSource``, but it keeps idle connections
# alive through proxies and lets the server notice a client that went away.
HEARTBEAT: Final = ": ping\n\n"


class _Subscriber:
    """One open stream: the newest payload it has not sent yet."""

    def __init__(self) -> None:
        self.latest: JsonObject | None = None
        self.sequence = -1
        # The game was deleted: say so (``closed``) and end the stream.
        self.gone = False
        # The server is stopping: just end the stream. The game may well be
        # back after a restart, so the client must not be told it is gone.
        self.shutdown = False
        self.wake = asyncio.Event()

    def offer(self, payload: JsonObject | None) -> None:
        if payload is None:
            self.gone = True
        else:
            sequence = payload.get("seq")
            if not isinstance(sequence, int) or sequence <= self.sequence:
                return
            self.latest = payload
            self.sequence = sequence
        self.wake.set()


class DoorbellHub:
    """Deliver each game's newest doorbell payload to its open streams.

    ``publish`` is safe to call from any thread. Everything else runs on
    the event loop that serves the streams, so the subscriber table needs
    no lock of its own.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: dict[str, set[_Subscriber]] = {}
        self._closed = False

    def publish(self, game_id: str, payload: JsonObject | None) -> None:
        """Offer one payload (``None``: the game is gone) to the game's streams.

        Never raises: a change to the game has already happened when its
        doorbell rings, and a lost ring only delays a refresh.
        """

        loop = self._loop
        if loop is None:
            return
        try:
            loop.call_soon_threadsafe(self._deliver, game_id, payload)
        except RuntimeError:
            # The loop that served the streams is closed (server shutdown).
            self._loop = None

    def close(self) -> None:
        """End every open stream, now and from here on (server shutdown).

        Safe to call from any thread and from a signal handler. An event
        stream never ends by itself, and a server waits for its open
        responses before it exits.
        """

        self._closed = True
        loop = self._loop
        if loop is None:
            return
        try:
            loop.call_soon_threadsafe(self._end_all)
        except RuntimeError:
            self._loop = None

    def subscriber_count(self, game_id: str) -> int:
        """Return how many streams of one game are open (for tests)."""

        return len(self._subscribers.get(game_id, ()))

    async def stream(
        self,
        game_id: str,
        current: Callable[[], Awaitable[JsonObject | None]],
        *,
        heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
    ) -> AsyncGenerator[str]:
        """Yield one game's events until the client leaves or the game ends.

        The subscriber registers *before* ``current`` reads the payload to
        greet with, so a change made in between is never lost: it is either
        in the greeting or waiting right behind it. ``current`` returns
        ``None`` when the game no longer exists.
        """

        if self._closed:
            return
        self._loop = asyncio.get_running_loop()
        subscriber = _Subscriber()
        self._subscribers.setdefault(game_id, set()).add(subscriber)
        try:
            greeting = await current()
            if greeting is None:
                yield format_event(CLOSED, {})
                return
            sent = _sequence(greeting)
            subscriber.sequence = max(subscriber.sequence, sent)
            yield format_event(HELLO, greeting)
            while True:
                try:
                    await asyncio.wait_for(subscriber.wake.wait(), heartbeat_seconds)
                except TimeoutError:
                    yield HEARTBEAT
                    continue
                subscriber.wake.clear()
                if subscriber.shutdown:
                    return
                if subscriber.gone:
                    yield format_event(CLOSED, {})
                    return
                # A payload that arrived while the greeting was being read
                # may be no newer than the greeting that went out after it.
                latest = subscriber.latest
                if latest is not None and _sequence(latest) > sent:
                    sent = _sequence(latest)
                    yield format_event(CHANGE, latest)
        finally:
            streams = self._subscribers.get(game_id)
            if streams is not None:
                streams.discard(subscriber)
                if not streams:
                    del self._subscribers[game_id]

    def _deliver(self, game_id: str, payload: JsonObject | None) -> None:
        for subscriber in tuple(self._subscribers.get(game_id, ())):
            subscriber.offer(payload)

    def _end_all(self) -> None:
        for streams in tuple(self._subscribers.values()):
            for subscriber in tuple(streams):
                subscriber.shutdown = True
                subscriber.wake.set()


def _sequence(payload: JsonObject) -> int:
    sequence = payload.get("seq")
    return sequence if isinstance(sequence, int) else -1
