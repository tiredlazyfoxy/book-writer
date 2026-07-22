"""Tests for unconfigured detection + the startup lifespan (feature 003, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002):
    def is_db_ready() -> bool                                    in app.db.engine
    def set_db_ready(value: bool) -> None                        in app.db.engine
    @dataclass class DbConfig(db_path, echo=False)               in app.db.engine
    async def init_engine(config: DbConfig) -> None              in app.db.engine
    async def init_db() -> None                                  in app.db.engine
    async def admin_exists() -> bool                             in app.db.users
    class User(SQLModel, table=True) / class UserRole            in app.models.user
    app  (FastAPI singleton) + lifespan(app)                     in app.main

Expected values come from the step spec (002.unconfigured-detection-startup.md
DoD + 002.context.md + feature context), never from implementation internals:

    - DoD-1: on a cold instance (engine initialized, no init_db / no tables)
      the instance reports itself unconfigured: is_db_ready() is False AND
      db.users.admin_exists() is False.
    - DoD-2: after tables are created and an admin user exists, is_db_ready()
      becomes True once set_db_ready(True) is called (the detection state
      reflects admin presence).
    - DoD-3: the startup lifespan does NOT create tables — after the lifespan
      runs against a cold temp DB, the `users` table is absent (schema creation
      is deferred to the setup flows).

These are async tests (asyncio_mode = "auto"). The process-global readiness flag
is reset to False before each test by the autouse `_reset_db_ready` fixture in
conftest.py, so is_db_ready() starts from its cold-boot default.

DoD-1 and DoD-3 deliberately DO NOT use the standard `db` conftest fixture: that
fixture calls init_db() and therefore builds the schema, which is unsuitable for
the zero-tables cold-instance cases. They wire the engine (or drive the app
lifespan) against a temp DbConfig without init_db(), so no tables exist.
"""

import sqlite3
from pathlib import Path

from app.db import users
from app.db.engine import (
    DbConfig,
    init_engine,
    is_db_ready,
    set_db_ready,
)
from app.models.user import User, UserRole


# DoD-1: On a cold instance (engine initialized on a temp DbConfig WITHOUT
# init_db, so no tables), the instance reports itself unconfigured:
# is_db_ready() is False AND admin_exists() is False.
async def test_cold_instance_reports_unconfigured__DoD1(tmp_path: Path):
    # Wire the engine directly against a temp DB, without init_db() — so the
    # schema is never built and the `users` table is absent (a cold instance).
    config = DbConfig(db_path=tmp_path / "cold_instance.db")
    await init_engine(config)

    # A cold instance is unconfigured: the readiness flag has not been flipped
    # (initializing the engine alone must not mark the DB ready)...
    assert is_db_ready() is False

    # ...and no admin exists — admin_exists() reports False gracefully against
    # the missing `users` table. Together these mean `needs_setup` is true.
    assert await users.admin_exists() is False


# DoD-2: After tables are created and an admin user exists, is_db_ready()
# becomes True once set_db_ready(True) is called — the detection state reflects
# admin presence. Uses the standard `db` fixture (which runs init_db, so the
# schema exists), creates an admin, then drives the flag via set_db_ready.
async def test_ready_flag_reflects_admin_presence__DoD2(db: DbConfig):
    # Precondition: schema exists but no admin yet -> unconfigured.
    assert is_db_ready() is False
    assert await users.admin_exists() is False

    # An admin user now exists in the built schema.
    await users.create(User(username="root", role=UserRole.admin))
    assert await users.admin_exists() is True

    # Flipping the flag to reflect the detected admin presence marks the
    # instance ready.
    set_db_ready(True)
    assert is_db_ready() is True


# DoD-3: The startup lifespan does NOT create tables. After the app's startup
# lifespan runs against a cold temp DB, the `users` table is absent (schema
# creation is deferred to the setup flows). Drives the real app.main.app
# lifespan against a throwaway temp DB, then inspects the sqlite schema.
async def test_lifespan_does_not_create_tables__DoD3(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "cold_lifespan.db"

    # Point the app's startup DbConfig at a throwaway temp DB (via the settings
    # env override) and clear the cached Settings so the override is picked up
    # before the lifespan builds its config.
    monkeypatch.setenv("BOOKWRITER_DB_PATH", str(db_file))

    import app.settings as settings_module

    if hasattr(settings_module.get_settings, "cache_clear"):
        settings_module.get_settings.cache_clear()

    from app.main import app

    # ASGITransport does not emit lifespan events, so drive startup/shutdown
    # explicitly via the app router's lifespan context (mirrors the http_client
    # fixture). Startup really runs (engine init + readiness detection).
    async with app.router.lifespan_context(app):
        pass

    # Inspect the sqlite schema directly: after a cold-instance startup the
    # `users` table must not have been created.
    conn = sqlite3.connect(str(db_file))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchall()
    finally:
        conn.close()

    if hasattr(settings_module.get_settings, "cache_clear"):
        settings_module.get_settings.cache_clear()

    # Schema creation is deferred: no `users` table exists after startup.
    assert rows == []
