"""Tests for the async DB engine core — app.db.engine + app.db.health (step 002).

Bound to the frozen skeleton signatures (status.md → Skeleton → Step 002):
    @dataclass class DbConfig(db_path: Path, echo: bool = False)   in app.db.engine
    async def init_engine(config: DbConfig) -> None
    async def init_db() -> None
    async def get_standalone_session() -> AsyncSession
    module-level singletons  _config / _engine  in app.db.engine
    async def ping() -> bool                                        in app.db.health

Expected values come from the step spec (002.db-engine-core.md DoD + context),
never from implementation internals:
    - init_engine + init_db build the schema and init_db is an idempotent no-op,
    - ping() reports readiness (True) once the engine is initialized,
    - get_standalone_session() raises a clear error when the engine is
      uninitialized (not the not-yet-implemented placeholder),
    - init_engine honors the injected db_path (the SQLite file lands there,
      not at the default).

The only implementation-internal names touched are the frozen module-level
singletons `_config` / `_engine`, per the step's documented reset guidance.
"""

from pathlib import Path

import pytest

import app.db.engine as engine_module
from app.db.engine import DbConfig, get_standalone_session, init_db, init_engine
from app.db.health import ping


# DoD-1: after init_engine + init_db the schema builds without error, and
# calling init_db() again is a safe, additive, idempotent no-op.
async def test_init_db_is_idempotent__DoD1(db: DbConfig):
    # The `db` fixture already ran init_engine + init_db once (first schema
    # build). Repeated init_db() calls must not raise (idempotent, additive)...
    await init_db()
    await init_db()
    # ...and must leave a working, ready database behind.
    assert await ping() is True


# DoD-2: db.health.ping() returns a ready result (True) once the engine is
# initialized.
async def test_ping_ready_after_engine_init__DoD2(db: DbConfig):
    assert await ping() is True


# DoD-3: get_standalone_session() raises when called before init_engine
# (engine uninitialized).
async def test_standalone_session_raises_when_engine_uninitialized__DoD3():
    # Force the pristine, uninitialized-engine state: the module-level
    # singletons persist across the session and may linger set from an earlier
    # test, so reset them explicitly (frozen singleton names only).
    engine_module._engine = None
    engine_module._config = None

    with pytest.raises(Exception) as exc_info:
        await get_standalone_session()

    # It must raise a genuine "engine uninitialized" error — not the
    # not-yet-implemented placeholder.
    assert not isinstance(exc_info.value, NotImplementedError)


# DoD-4: init_engine honors the injected DbConfig.db_path — the throwaway
# SQLite file is created at the injected path, not the default.
async def test_init_engine_honors_injected_db_path__DoD4(tmp_path: Path):
    injected = tmp_path / "nested" / "injected.db"
    config = DbConfig(db_path=injected)

    await init_engine(config)
    await init_db()

    # The database materialized at exactly the injected path (its nested parent
    # directory was created too), proving the injected config was honored rather
    # than a default location.
    assert injected.is_file()
