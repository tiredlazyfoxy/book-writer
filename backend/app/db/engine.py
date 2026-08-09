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

from sqlalchemy import inspect
from sqlalchemy.dialects import sqlite
from sqlalchemy.engine import Connection
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

# A reusable SQLite dialect for compiling column types and quoting identifiers
# in the additive-migration seam below (same device ``db/schema.py`` uses).
_sqlite_dialect = sqlite.dialect()


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
    import app.models.llm_server  # noqa: F401
    import app.models.assistant_mode  # noqa: F401
    import app.models.sub_agent  # noqa: F401
    import app.models.mode_tool  # noqa: F401
    import app.models.subagent_tool  # noqa: F401
    import app.models.mode_subagent  # noqa: F401
    import app.models.book  # noqa: F401
    import app.models.book_member  # noqa: F401
    import app.models.book_author_prompt  # noqa: F401
    import app.models.chapter  # noqa: F401
    import app.models.chapter_author_prompt  # noqa: F401
    import app.models.chapter_change  # noqa: F401
    import app.models.chapter_text_revision  # noqa: F401
    import app.models.chapter_notes  # noqa: F401
    import app.models.codex_entry  # noqa: F401
    import app.models.codex_entry_version  # noqa: F401
    import app.models.flag  # noqa: F401
    import app.models.chat  # noqa: F401

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


# --- ADDITIVE MIGRATION SEAM (declaration half) ---------------------------
# ``SQLModel.metadata.create_all`` creates MISSING TABLES only — it never alters
# a table that already exists. So a column added to a model reaches a fresh
# database for free and an EXISTING database never, unless it is listed here.
#
# One entry per ``(table name, column name)`` a model gained after that table
# first shipped. The SQL type is NOT written out: it is compiled from
# ``SQLModel.metadata`` at run time, so the DDL can never drift from the model.
# Adding the next one is a single line — append it, nothing else to change.
#
# Two hard rules, both SQLite's:
#   * the column must be NULLABLE (``ADD COLUMN`` cannot add ``NOT NULL``
#     without a default), and
#   * there is no supported DROP/ALTER path — this seam is ADDITIVE ONLY.
# Removing or retyping a column stays feature 007's admin ``sync_table_schema``
# job, not this one.
#
# Why raw DDL rather than ``db/schema.py``'s ``introspect`` / ``add_columns``:
# ``schema.py`` imports THIS module (it reaches ``engine._engine``), so calling
# into it from here would invert the dependency and require a deferred import to
# dodge the cycle. ``engine.py`` is the bottom of the ``db/`` layer and stays
# there; the DDL below is deliberately the same shape ``schema.add_columns``
# emits.
ADDITIVE_COLUMNS: tuple[tuple[str, str], ...] = (
    # (table, column)
    ("chat_messages", "tool_trace"),  # feature 024 — ChatMessage.tool_trace
)


async def init_db() -> None:
    """Create the schema (idempotent, additive).

    Runs the model-registration hook, then creates all tables via
    ``async with _engine.begin() as conn: await conn.run_sync(
    SQLModel.metadata.create_all)``, then runs the idempotent in-code
    ``ALTER TABLE ... ADD COLUMN`` migration seam over
    :data:`ADDITIVE_COLUMNS` — which is how a column added to a model reaches a
    database that already existed before that column did.
    """
    if _engine is None:
        raise RuntimeError(
            "DB engine not initialized — call init_engine(config) before init_db()."
        )

    _register_models()

    async with _engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # --- ADDITIVE MIGRATION SEAM (application half): apply an idempotent
    #     ``ALTER TABLE <table> ADD COLUMN <col> <type>`` for every entry of
    #     ``ADDITIVE_COLUMNS`` that the live database is missing. To add a
    #     column, append to ``ADDITIVE_COLUMNS`` above — this half never
    #     changes. Every run after the first is a silent no-op. ---
    async with _engine.begin() as conn:
        await conn.run_sync(_apply_additive_columns)


def _apply_additive_columns(sync_conn: Connection) -> None:
    """Add each missing :data:`ADDITIVE_COLUMNS` entry (run under ``run_sync``).

    Idempotent by **introspection**, not by error text: the live column names are
    reflected first and an entry already present is skipped without emitting any
    DDL, so the second and every later run does nothing at all. The ``ALTER`` is
    still wrapped in ``try/except OperationalError`` as a backstop (a concurrent
    process winning the race between the reflection and the statement), logged
    and swallowed — ``init_db`` must never fail because a column it wanted is
    already there. An entry naming a table that does not exist yet, or a column
    no longer in ``SQLModel.metadata``, is skipped with a warning rather than
    raising: the seam is a repair path and must not become a new way to break
    startup of the setup flows.
    """
    inspector = inspect(sync_conn)
    live_tables = set(inspector.get_table_names())

    for table_name, column_name in ADDITIVE_COLUMNS:
        if table_name not in live_tables:
            # Nothing to migrate: ``create_all`` above builds a missing table
            # complete with this column.
            continue

        table = SQLModel.metadata.tables.get(table_name)
        if table is None or column_name not in table.columns:
            logger.warning(
                "Additive migration entry %s.%s is not in SQLModel.metadata — "
                "skipping (stale seam entry?).",
                table_name,
                column_name,
            )
            continue

        live_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        if column_name in live_columns:
            continue

        # Type text compiled from the model; emitted NULLABLE (no NOT NULL, no
        # DEFAULT) — SQLite permits nothing else on ``ADD COLUMN``.
        type_sql = table.columns[column_name].type.compile(dialect=_sqlite_dialect)
        quoted_table = _sqlite_dialect.identifier_preparer.quote(table_name)
        quoted_column = _sqlite_dialect.identifier_preparer.quote(column_name)
        statement = (
            f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {type_sql}"
        )
        try:
            sync_conn.exec_driver_sql(statement)
        except OperationalError:
            logger.debug(
                "Additive migration %s.%s already applied — no-op.",
                table_name,
                column_name,
            )
        else:
            logger.info(
                "Additive migration applied: %s.%s added.", table_name, column_name
            )


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
