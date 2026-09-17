"""Tests for the doorbell hub (M14 slice 3): fanning a game's latest change
out to its Server-Sent Events streams, ``docs/multiplayer-design.md``
section 4.5. Pure ``asyncio``, driven with ``asyncio.run`` inside plain sync
tests -- no pytest-asyncio plugin is installed here."""

import asyncio
import json
import threading
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable

import pytest

from dune_imperium.server.events import (
    CHANGE,
    CLOSED,
    HEARTBEAT,
    HELLO,
    DoorbellHub,
    format_event,
)
from dune_imperium.server.persistence import JsonObject

_DEADLINE = 5.0


class _Current:
    """A settable ``current`` callable for ``DoorbellHub.stream``."""

    def __init__(self, payload: JsonObject | None) -> None:
        self.payload = payload

    async def __call__(self) -> JsonObject | None:
        return self.payload


def _open(
    hub: DoorbellHub,
    game_id: str,
    current: Callable[[], Awaitable[JsonObject | None]],
    *,
    heartbeat_seconds: float,
) -> AsyncGenerator[str]:
    return hub.stream(game_id, current, heartbeat_seconds=heartbeat_seconds)


async def _next_chunk(events: AsyncIterator[str]) -> str:
    return await asyncio.wait_for(anext(events), _DEADLINE)


def _parse(chunk: str) -> tuple[str, JsonObject | None]:
    """Split one SSE chunk into its event name and JSON payload.

    A heartbeat comment line has no event name and no payload.
    """

    if chunk.startswith(":"):
        return "heartbeat", None
    lines = chunk.splitlines()
    event_line = next(line for line in lines if line.startswith("event: "))
    data_line = next(line for line in lines if line.startswith("data: "))
    payload = json.loads(data_line.removeprefix("data: "))
    assert isinstance(payload, dict)
    return event_line.removeprefix("event: "), payload


# --- format_event -------------------------------------------------------


def test_format_event_includes_an_id_line_when_the_payload_has_a_seq() -> None:
    text = format_event(CHANGE, {"seq": 7, "revision": 3})

    assert text == 'event: change\nid: 7\ndata: {"seq": 7, "revision": 3}\n\n'


def test_format_event_omits_the_id_line_when_the_payload_has_no_seq() -> None:
    text = format_event(CLOSED, {})

    assert text == "event: closed\ndata: {}\n\n"


# --- greeting -----------------------------------------------------------


def test_the_first_chunk_is_hello_built_from_current() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()
        current = _Current({"seq": 1, "revision": 0})
        events = _open(hub, "g", current, heartbeat_seconds=10.0)

        chunk = await _next_chunk(events)

        assert _parse(chunk) == (HELLO, {"seq": 1, "revision": 0})
        await events.aclose()

    asyncio.run(scenario())


def test_current_returning_none_yields_only_closed_and_ends() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()
        current = _Current(None)
        events = _open(hub, "g", current, heartbeat_seconds=10.0)

        chunk = await _next_chunk(events)
        assert _parse(chunk)[0] == CLOSED

        with pytest.raises(StopAsyncIteration):
            await _next_chunk(events)

    asyncio.run(scenario())


# --- changes: ordering, drops, coalescing --------------------------------


def test_a_newer_payload_after_the_greeting_arrives_as_one_change() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()
        current = _Current({"seq": 5, "revision": 0})
        events = _open(hub, "g", current, heartbeat_seconds=10.0)
        assert _parse(await _next_chunk(events))[0] == HELLO

        hub.publish("g", {"seq": 5, "revision": 1})  # same seq: dropped
        hub.publish("g", {"seq": 3, "revision": 2})  # older: dropped
        hub.publish("g", {"seq": 6, "revision": 3})  # newer: delivered
        await asyncio.sleep(0)

        chunk = await _next_chunk(events)

        assert _parse(chunk) == (CHANGE, {"seq": 6, "revision": 3})
        await events.aclose()

    asyncio.run(scenario())


def test_several_payloads_before_a_read_coalesce_into_one_change() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()
        current = _Current({"seq": 1, "revision": 0})
        events = _open(hub, "g", current, heartbeat_seconds=0.05)
        assert _parse(await _next_chunk(events))[0] == HELLO

        hub.publish("g", {"seq": 2, "revision": 1})
        hub.publish("g", {"seq": 3, "revision": 2})
        hub.publish("g", {"seq": 4, "revision": 3})
        await asyncio.sleep(0)

        chunk = await _next_chunk(events)
        assert _parse(chunk) == (CHANGE, {"seq": 4, "revision": 3})

        # Nothing else was queued behind it: the wait times out to a heartbeat.
        assert await _next_chunk(events) == HEARTBEAT
        await events.aclose()

    asyncio.run(scenario())


def test_publish_none_yields_closed_then_ends() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()
        current = _Current({"seq": 1, "revision": 0})
        events = _open(hub, "g", current, heartbeat_seconds=10.0)
        assert _parse(await _next_chunk(events))[0] == HELLO

        hub.publish("g", None)
        await asyncio.sleep(0)

        chunk = await _next_chunk(events)
        assert _parse(chunk)[0] == CLOSED
        with pytest.raises(StopAsyncIteration):
            await _next_chunk(events)

    asyncio.run(scenario())


def test_a_payload_for_another_game_id_is_not_delivered() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()
        current = _Current({"seq": 1, "revision": 0})
        events = _open(hub, "g", current, heartbeat_seconds=0.05)
        assert _parse(await _next_chunk(events))[0] == HELLO

        hub.publish("other-game", {"seq": 99, "revision": 9})
        await asyncio.sleep(0)

        # Not delivered: the wait times out to a heartbeat instead.
        assert await _next_chunk(events) == HEARTBEAT
        await events.aclose()

    asyncio.run(scenario())


# --- heartbeats and cross-thread publish ---------------------------------


def test_an_idle_stream_yields_a_heartbeat() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()
        current = _Current({"seq": 1, "revision": 0})
        events = _open(hub, "g", current, heartbeat_seconds=0.01)
        assert _parse(await _next_chunk(events))[0] == HELLO

        assert await _next_chunk(events) == HEARTBEAT
        await events.aclose()

    asyncio.run(scenario())


def test_publish_from_another_thread_wakes_the_stream() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()
        current = _Current({"seq": 1, "revision": 0})
        events = _open(hub, "g", current, heartbeat_seconds=10.0)
        assert _parse(await _next_chunk(events))[0] == HELLO

        thread = threading.Thread(
            target=hub.publish, args=("g", {"seq": 2, "revision": 1}), daemon=True
        )
        thread.start()
        thread.join(timeout=_DEADLINE)
        assert not thread.is_alive()

        chunk = await _next_chunk(events)
        assert _parse(chunk) == (CHANGE, {"seq": 2, "revision": 1})
        await events.aclose()

    asyncio.run(scenario())


# --- subscriber bookkeeping ------------------------------------------------


def test_publish_before_any_stream_is_a_silent_no_op() -> None:
    hub = DoorbellHub()

    hub.publish("g", {"seq": 1, "revision": 0})  # must not raise

    assert hub.subscriber_count("g") == 0


def test_subscriber_count_tracks_one_open_stream_and_returns_to_zero() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()
        current = _Current({"seq": 1, "revision": 0})
        events = _open(hub, "g", current, heartbeat_seconds=10.0)
        assert hub.subscriber_count("g") == 0  # not started until first read

        assert _parse(await _next_chunk(events))[0] == HELLO
        assert hub.subscriber_count("g") == 1

        await events.aclose()
        assert hub.subscriber_count("g") == 0

    asyncio.run(scenario())


# --- a change racing the greeting ----------------------------------------


def test_a_change_published_while_the_greeting_is_read_is_not_lost() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()

        async def current() -> JsonObject | None:
            # The greeting was read from the game at seq 1; before it goes
            # out, seq 2 is published. The subscriber is already registered.
            hub.publish("g", {"seq": 2, "revision": 1})
            await asyncio.sleep(0)
            return {"seq": 1, "revision": 0}

        events = _open(hub, "g", current, heartbeat_seconds=10.0)

        assert _parse(await _next_chunk(events)) == (HELLO, {"seq": 1, "revision": 0})
        assert _parse(await _next_chunk(events)) == (CHANGE, {"seq": 2, "revision": 1})
        await events.aclose()

    asyncio.run(scenario())


def test_a_change_the_greeting_already_covers_is_not_sent_twice() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()

        async def current() -> JsonObject | None:
            hub.publish("g", {"seq": 2, "revision": 1})
            await asyncio.sleep(0)
            return {"seq": 2, "revision": 1}

        events = _open(hub, "g", current, heartbeat_seconds=0.05)

        assert _parse(await _next_chunk(events)) == (HELLO, {"seq": 2, "revision": 1})
        assert await _next_chunk(events) == HEARTBEAT
        await events.aclose()

    asyncio.run(scenario())


# --- server shutdown ------------------------------------------------------


def test_close_ends_open_streams_without_saying_the_game_is_gone() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()
        first = _open(hub, "g", _Current({"seq": 1}), heartbeat_seconds=10.0)
        second = _open(hub, "h", _Current({"seq": 1}), heartbeat_seconds=10.0)
        assert _parse(await _next_chunk(first))[0] == HELLO
        assert _parse(await _next_chunk(second))[0] == HELLO

        hub.close()

        # No ``closed`` event: the game may be back after a restart.
        for events in (first, second):
            with pytest.raises(StopAsyncIteration):
                await _next_chunk(events)
        assert hub.subscriber_count("g") == 0
        assert hub.subscriber_count("h") == 0

    asyncio.run(scenario())


def test_close_from_another_thread_ends_the_stream() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()
        events = _open(hub, "g", _Current({"seq": 1}), heartbeat_seconds=10.0)
        assert _parse(await _next_chunk(events))[0] == HELLO

        thread = threading.Thread(target=hub.close, daemon=True)
        thread.start()
        thread.join(timeout=_DEADLINE)

        with pytest.raises(StopAsyncIteration):
            await _next_chunk(events)

    asyncio.run(scenario())


def test_a_closed_hub_opens_no_new_stream_and_close_without_streams_is_quiet() -> None:
    async def scenario() -> None:
        hub = DoorbellHub()
        hub.close()  # never served a stream: nothing to do, nothing raised

        events = _open(hub, "g", _Current({"seq": 1}), heartbeat_seconds=10.0)
        with pytest.raises(StopAsyncIteration):
            await _next_chunk(events)
        hub.publish("g", {"seq": 2})  # still a silent no-op

    asyncio.run(scenario())
