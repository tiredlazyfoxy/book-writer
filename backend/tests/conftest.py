"""Shared pytest fixtures for the BookWriter backend test-suite.

Introduced in step 002. Provides a throwaway temp-SQLite `DbConfig` fixture
(`db`) that initializes the async engine and builds the schema, so a requesting
test runs against an isolated, ready database.

Step 003 extends this same file with an `http_client` ASGITransport fixture:
it drives the real `app.main.app` in-process (no live server, no network),
running the app's startup lifespan against a throwaway temp DB so the end-to-end
`GET /api/health` flow (routes -> services -> db -> schema) can be exercised.

No `event_loop` override is defined: the suite relies on
`asyncio_mode = "auto"` (the reference project's deprecated `event_loop`
override is deliberately not copied). The fixtures are deliberately *not*
autouse so tests that need a pristine, uninitialized engine (and the settings
tests from step 001) are unaffected.
"""

from pathlib import Path

import httpx
import pytest_asyncio

from app.db.engine import DbConfig, init_db, init_engine


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> DbConfig:
    """A throwaway temp-SQLite database, initialized with its schema built.

    Builds a `DbConfig` pointing at a temp file, then calls `init_engine`
    followed by `init_db`. Yields the `DbConfig` so a requesting test can read
    back the injected path. Each requesting test gets its own temp file, hence
    an isolated database.
    """
    config = DbConfig(db_path=tmp_path / "bookwriter_test.db")
    await init_engine(config)
    await init_db()
    yield config


@pytest_asyncio.fixture
async def http_client(tmp_path: Path, monkeypatch) -> httpx.AsyncClient:
    """An in-process HTTP client bound to the real `app.main.app`.

    Wraps the app in `httpx.ASGITransport` and yields an
    `httpx.AsyncClient(base_url="http://test")` — no live server, no network.

    Hermeticity: the app's startup lifespan builds its `DbConfig` from
    `Settings`, whose default `db_path` points at the real
    `backend/data/bookwriter.db`. To keep each run isolated, this fixture sets
    the `BOOKWRITER_DB_PATH` environment override to a temp path *before* the
    lifespan runs (and clears the cached `Settings` so the override is picked
    up), so startup initializes a throwaway DB and never touches the real one.

    `httpx.ASGITransport` does not emit ASGI lifespan events, so the app's
    startup/shutdown is driven explicitly via the app router's lifespan context
    (no `asgi-lifespan` dependency is available). Startup therefore really runs
    (engine + DB + vector init), so the health check flows through an
    actually-initialized database.
    """
    monkeypatch.setenv("BOOKWRITER_DB_PATH", str(tmp_path / "http_bookwriter.db"))

    import app.settings as settings_module

    if hasattr(settings_module.get_settings, "cache_clear"):
        settings_module.get_settings.cache_clear()

    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client

    if hasattr(settings_module.get_settings, "cache_clear"):
        settings_module.get_settings.cache_clear()
