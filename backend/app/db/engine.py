"""Async SQLite engine and session-free ``db/`` core primitives.

This module owns the process-wide async engine singleton and the **only**
session primitive the ``db/`` layer is allowed to use. ``AsyncSession`` and
other ORM/connection types never leak past ``db/`` (see ``docs/architecture/
backend.md`` — layer separation).

Skeleton (step 002): signatures are frozen; bodies are UNIMPLEMENTED.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class DbConfig:
    """Injectable db-layer configuration (distinct from app-level ``Settings``).

    Override in tests to point the engine at a throwaway SQLite file.
    """

    db_path: Path       # SQLite file path (injectable for tests)
    echo: bool = False  # SQLAlchemy echo for debugging


# Module-level singletons — populated by ``init_engine``.
_config: DbConfig | None = None
_engine: AsyncEngine | None = None

# Process-level readiness flag (feature 003 decision 1). ``needs_setup = not
# is_db_ready()``. Default ``False`` on a cold instance; initialized at startup
# from admin-existence and flipped to ``True`` at the end of a successful
# create/import flow. Because it is process-global, tests reset it between runs.
_db_ready: bool = False


def is_db_ready() -> bool:
    """Return the current process-level readiness flag."""
    return _db_ready


def set_db_ready(value: bool) -> None:
    """Set the process-level readiness flag to ``value``."""
    global _db_ready
    _db_ready = value


def _register_models() -> None:
    """Import every ``app.models.*`` table module so its tables register on
    ``SQLModel.metadata`` before ``create_all``.

    Future model table modules are imported here (``# noqa: F401``) so they
    register as a side effect before any ``create_all``.
    """
    # --- MODEL-REGISTRATION SEAM: add ``import app.models.<name>  # noqa: F401``
    #     lines below as table modules are introduced. Do not remove this hook. ---
    import app.models.user  # noqa: F401

    return


async def init_engine(config: DbConfig) -> None:
    """Initialize the module-level async engine from ``config``.

    Ensures the parent directory of ``config.db_path`` exists, builds the
    ``sqlite+aiosqlite:///{db_path}`` async engine, and stores it (with the
    config) in the module-level singletons. Safe to call once per process/test.
    """
    global _config, _engine
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    _config = config
    _engine = create_async_engine(
        f"sqlite+aiosqlite:///{config.db_path}", echo=config.echo
    )
    logger.info("Async DB engine initialized at %s", config.db_path)


async def init_db() -> None:
    """Create the schema (idempotent, additive).

    Runs the model-registration hook, then creates all tables via
    ``async with _engine.begin() as conn: await conn.run_sync(
    SQLModel.metadata.create_all)``, then runs the idempotent in-code
    ``ALTER TABLE ... ADD COLUMN`` migration seam (try/except; no-op now).
    """
    if _engine is None:
        raise RuntimeError(
            "DB engine not initialized — call init_engine(config) before init_db()."
        )

    _register_models()

    async with _engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # --- ADDITIVE MIGRATION SEAM: apply idempotent in-code
    #     ``ALTER TABLE <table> ADD COLUMN <col> <type>`` statements here as the
    #     schema evolves. Each wrapped in try/except so a re-run is a no-op once
    #     the column already exists. No columns to add yet (no models). ---
    async with _engine.begin() as conn:
        pass  # no additive migrations yet


async def get_standalone_session() -> AsyncSession:
    """Return a fresh ``AsyncSession`` bound to the engine singleton.

    The **only** session primitive ``db/`` modules use. Raises a clear error
    when the engine has not been initialized. Sessions never leak past ``db/``.
    """
    if _engine is None:
        raise RuntimeError(
            "DB engine not initialized — call init_engine(config) before "
            "opening a session."
        )
    return AsyncSession(_engine)
