"""Verifies POST /events broadcasts to WebSocket subscribers.

Two complementary checks:

1. A mock broadcast: we monkeypatch ``broadcaster.publish`` so we can assert
   exactly what the ingestion endpoint fans out to dashboards — notably that
   the (potentially large) ``snapshot_b64`` is *excluded* from the broadcast
   payload while the structured fields are present.

2. A real fan-out through the public API surface: we subscribe a queue to the
   live broadcaster, POST an event, and confirm the same event object is
   delivered. This exercises the actual ``broadcaster`` singleton that the
   ``/ws`` endpoint reads from, without needing a running WebSocket server.
"""
from __future__ import annotations

import src.routers.events as events_router
from src.broadcaster import broadcaster

EVENT_WITH_SNAPSHOT = {
    "site_id": "site-001",
    "kind": "no_helmet",
    "confidence": 0.91,
    "bbox_xyxy_norm": [0.1, 0.2, 0.5, 0.8],
    "description": "Person detected without helmet",
    "snapshot_b64": "ZmFrZS1qcGVn",
}


def test_post_event_broadcasts_without_snapshot(client, monkeypatch) -> None:
    published: list[dict] = []

    async def fake_publish(event: dict) -> None:
        published.append(event)

    monkeypatch.setattr(events_router.broadcaster, "publish", fake_publish)

    resp = client.post("/events", json=EVENT_WITH_SNAPSHOT)
    assert resp.status_code == 201

    assert len(published) == 1
    broadcast = published[0]
    # structured fields are present for the dashboard
    assert broadcast["site_id"] == "site-001"
    assert broadcast["kind"] == "no_helmet"
    assert broadcast["confidence"] == 0.91
    assert broadcast["bbox_xyxy_norm"] == [0.1, 0.2, 0.5, 0.8]
    assert "occurred_at" in broadcast
    # the heavy snapshot is intentionally NOT broadcast to clients
    assert "snapshot_b64" not in broadcast


def test_post_event_reaches_live_subscriber(client) -> None:
    """The real broadcaster singleton delivers POSTed events to a subscriber."""
    queue = broadcaster.subscribe()
    try:
        resp = client.post("/events", json=EVENT_WITH_SNAPSHOT)
        assert resp.status_code == 201

        delivered = queue.get_nowait()
        assert delivered["kind"] == "no_helmet"
        assert delivered["site_id"] == "site-001"
        assert "snapshot_b64" not in delivered
    finally:
        broadcaster.unsubscribe(queue)
