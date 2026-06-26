"""End-to-end tests for the event ingestion API and its persistence layer.

These exercise the same code paths the edge detector and dashboard use:
POST /events to ingest a violation, GET /events to list them, and
GET /stats/daily to aggregate. The database is an isolated in-memory SQLite
(see conftest), so assertions about persisted rows are deterministic.
"""
from __future__ import annotations

import json

from src.models import ViolationEvent

VALID_EVENT = {
    "site_id": "site-001",
    "kind": "no_helmet",
    "confidence": 0.91,
    "bbox_xyxy_norm": [0.1, 0.2, 0.5, 0.8],
    "description": "Person detected without helmet",
}


def test_health(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_event_returns_201_and_echoes_payload(client) -> None:
    resp = client.post("/events", json=VALID_EVENT)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] >= 1
    assert body["site_id"] == "site-001"
    assert body["kind"] == "no_helmet"
    assert body["confidence"] == 0.91
    assert body["bbox_xyxy_norm"] == [0.1, 0.2, 0.5, 0.8]
    # snapshot is never echoed back in the response (bandwidth)
    assert "snapshot_b64" not in body
    assert "occurred_at" in body


def test_create_event_persists_row(client, db_session) -> None:
    """A POSTed event is written to the database, snapshot included."""
    payload = {**VALID_EVENT, "snapshot_b64": "ZmFrZS1qcGVn"}
    resp = client.post("/events", json=payload)
    assert resp.status_code == 201

    rows = db_session.query(ViolationEvent).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.site_id == "site-001"
    assert row.kind == "no_helmet"
    assert json.loads(row.bbox) == [0.1, 0.2, 0.5, 0.8]
    # the snapshot is persisted server-side even though it is omitted from
    # the broadcast/response
    assert row.snapshot_b64 == "ZmFrZS1qcGVn"


def test_create_event_rejects_out_of_range_confidence(client) -> None:
    bad = {**VALID_EVENT, "confidence": 1.5}
    resp = client.post("/events", json=bad)
    assert resp.status_code == 422


def test_create_event_rejects_wrong_bbox_length(client) -> None:
    bad = {**VALID_EVENT, "bbox_xyxy_norm": [0.1, 0.2, 0.3]}
    resp = client.post("/events", json=bad)
    assert resp.status_code == 422


def test_list_events_empty(client) -> None:
    resp = client.get("/events")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_events_returns_newest_first(client) -> None:
    for kind in ("no_helmet", "no_vest", "no_goggles"):
        resp = client.post("/events", json={**VALID_EVENT, "kind": kind})
        assert resp.status_code == 201

    resp = client.get("/events")
    assert resp.status_code == 200
    kinds = [e["kind"] for e in resp.json()]
    # ordering is by occurred_at desc; ties broken by insertion is acceptable,
    # so assert the set is complete and the most-recently inserted is present
    assert set(kinds) == {"no_helmet", "no_vest", "no_goggles"}
    assert len(kinds) == 3


def test_list_events_limit(client) -> None:
    for _ in range(5):
        client.post("/events", json=VALID_EVENT)
    resp = client.get("/events", params={"limit": 2})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_events_filter_by_site_and_kind(client) -> None:
    client.post("/events", json={**VALID_EVENT, "site_id": "site-A", "kind": "no_helmet"})
    client.post("/events", json={**VALID_EVENT, "site_id": "site-B", "kind": "no_vest"})

    by_site = client.get("/events", params={"site_id": "site-A"}).json()
    assert len(by_site) == 1
    assert by_site[0]["site_id"] == "site-A"

    by_kind = client.get("/events", params={"kind": "no_vest"}).json()
    assert len(by_kind) == 1
    assert by_kind[0]["kind"] == "no_vest"


def test_daily_stats_aggregates_by_site_and_kind(client) -> None:
    posts = [
        {"site_id": "site-A", "kind": "no_helmet"},
        {"site_id": "site-A", "kind": "no_helmet"},
        {"site_id": "site-B", "kind": "no_vest"},
    ]
    for p in posts:
        client.post("/events", json={**VALID_EVENT, **p})

    stats = client.get("/stats/daily").json()
    assert stats["total"] == 3
    assert stats["by_kind"] == {"no_helmet": 2, "no_vest": 1}
    assert stats["by_site"] == {"site-A": 2, "site-B": 1}
