"""Tests for the in-memory WebSocket pub/sub broadcaster.

The broadcaster is the fan-out mechanism behind the ``/ws`` endpoint: every
connected dashboard owns one bounded queue, and ``publish`` pushes an event
into all of them. These tests cover the subscribe/unsubscribe lifecycle, the
fan-out to multiple subscribers, and the backpressure behaviour that protects
the server from a slow client (a full queue drops the event instead of
blocking the whole broadcast).

They run the coroutines via ``asyncio.run`` so no extra async-test plugin is
required; the broadcaster (and its ``asyncio.Queue`` objects) are created
inside the running loop.
"""
from __future__ import annotations

import asyncio

from src.broadcaster import EventBroadcaster

EVENT = {"id": 1, "site_id": "site-001", "kind": "no_helmet"}


def test_fanout_to_all_subscribers() -> None:
    async def scenario() -> None:
        b = EventBroadcaster()
        q1 = b.subscribe()
        q2 = b.subscribe()

        await b.publish(EVENT)

        assert q1.get_nowait() == EVENT
        assert q2.get_nowait() == EVENT

    asyncio.run(scenario())


def test_unsubscribe_stops_delivery() -> None:
    async def scenario() -> None:
        b = EventBroadcaster()
        q = b.subscribe()
        b.unsubscribe(q)

        await b.publish(EVENT)

        assert q.qsize() == 0

    asyncio.run(scenario())


def test_unsubscribe_is_idempotent() -> None:
    async def scenario() -> None:
        b = EventBroadcaster()
        q = b.subscribe()
        b.unsubscribe(q)
        # discarding an already-removed subscriber must not raise
        b.unsubscribe(q)

    asyncio.run(scenario())


def test_backpressure_drops_for_slow_client() -> None:
    """A subscriber whose queue is full is skipped, not blocked, and the
    publish call still completes for everyone else."""

    async def scenario() -> None:
        b = EventBroadcaster()
        slow = b.subscribe()  # bounded queue, maxsize=100
        fast = b.subscribe()

        # saturate the slow client's queue
        for _ in range(100):
            slow.put_nowait({"filler": True})
        assert slow.full()

        # one more publish must not raise and must still reach the fast client
        await b.publish(EVENT)

        assert slow.qsize() == 100  # dropped for the slow client
        assert fast.get_nowait() == EVENT  # delivered to the healthy client

    asyncio.run(scenario())
