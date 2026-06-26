"""Tests for the ``/ws`` WebSocket relay handler in ``routers/stream.py``.

The handler is the live edge between the broadcaster and a connected
dashboard: on connect it accepts the socket and subscribes a queue; for every
event published to the broadcaster it forwards a JSON frame; on disconnect it
unsubscribes so the queue is not leaked.

A full TestClient round-trip (open ``/ws`` then ``POST /events``) is *not* used
here on purpose: Starlette runs the WebSocket session and a separate HTTP
request on different event loops, so the in-memory ``asyncio.Queue`` fan-out
never crosses between them and the test would deadlock. Instead we drive the
handler coroutine directly against the real ``broadcaster`` singleton on a
single loop with a minimal fake WebSocket, which exercises the actual handler
code (accept -> subscribe -> send_json -> unsubscribe) deterministically.
"""
from __future__ import annotations

import asyncio

from fastapi import WebSocketDisconnect

from src.broadcaster import broadcaster
from src.routers.stream import websocket_stream

EVENT = {"id": 1, "site_id": "site-001", "kind": "no_helmet"}


class _FakeWebSocket:
    """Minimal stand-in for ``starlette.websockets.WebSocket``.

    ``send_json`` optionally raises ``WebSocketDisconnect`` so the handler's
    ``while True`` loop terminates the same way it would when a real client
    drops mid-send.
    """

    def __init__(self, *, disconnect_after_send: bool) -> None:
        self.accepted = False
        self.sent: list[dict] = []
        self._disconnect_after_send = disconnect_after_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)
        if self._disconnect_after_send:
            raise WebSocketDisconnect()


def test_ws_handler_accepts_and_forwards_published_event() -> None:
    """A published event is accepted, forwarded as JSON, and the queue is
    cleaned up after the client disconnects."""

    async def scenario() -> None:
        baseline = len(broadcaster._subscribers)
        ws = _FakeWebSocket(disconnect_after_send=True)

        task = asyncio.create_task(websocket_stream(ws))
        await asyncio.sleep(0)  # let the handler reach `await q.get()`

        await broadcaster.publish(EVENT)
        await asyncio.wait_for(task, timeout=2)

        assert ws.accepted is True
        assert ws.sent == [EVENT]
        # the disconnect path must run the finally-block unsubscribe
        assert len(broadcaster._subscribers) == baseline

    asyncio.run(scenario())


def test_ws_handler_subscribes_then_unsubscribes_on_disconnect() -> None:
    """While connected the handler holds exactly one subscription; on
    disconnect (here, cancellation) the finally-block removes it."""

    async def scenario() -> None:
        baseline = len(broadcaster._subscribers)
        ws = _FakeWebSocket(disconnect_after_send=False)

        task = asyncio.create_task(websocket_stream(ws))
        await asyncio.sleep(0)  # let the handler subscribe and block on get()

        assert len(broadcaster._subscribers) == baseline + 1

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(broadcaster._subscribers) == baseline

    asyncio.run(scenario())
