"""Shared pytest fixtures for the API test suite.

Every test runs against an isolated in-memory SQLite database so that test
runs are deterministic and never touch the on-disk ``data/events.db`` used at
runtime. We override the FastAPI ``get_db`` dependency with a session bound to
a ``StaticPool`` engine; ``StaticPool`` keeps a single underlying connection
alive for the lifetime of the engine, which is what lets an in-memory SQLite
database persist across requests within one test.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base, get_db
from src.main import app


@pytest.fixture()
def db_engine():
    """Fresh in-memory SQLite engine with the schema created, per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    """A session on the test engine, usable directly for persistence asserts."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine) -> Generator[TestClient, None, None]:
    """A TestClient whose ``get_db`` dependency uses the in-memory engine.

    Note we deliberately do not enter the app's lifespan (no
    ``with TestClient(app)``) so the real ``init_db()`` never creates an
    on-disk database during tests.
    """
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
