"""Session-free schema introspection (feature 007, step 001).

The ``db/`` layer is the **only** place SQLAlchemy reflection / ``inspect()`` /
``run_sync`` / raw connections are sanctioned (see ``docs/architecture/
backend.md`` — layer separation; feature 007 decision D1). This module reads the
**actual** structure of the live SQLite database — the table names present and,
per table, its column names plus each column's reflected type — so the service
layer can diff it against the **expected** ``SQLModel.metadata`` structure.

Engine access: ``engine.py`` exposes no public accessor, so — being itself a
``db/`` module — this module reaches the async engine singleton directly via
``from app.db import engine`` / ``engine._engine`` (guarding ``None`` the same way
``get_standalone_session`` does), then opens and closes its own connection:
``async with engine._engine.connect() as conn: await conn.run_sync(
lambda sync_conn: inspect(sync_conn)...)``. Connections never leak past ``db/``.

Skeleton (step 001): the ``TypedDict`` shapes and ``introspect()`` signature are
frozen; the body is UNIMPLEMENTED.
"""

from collections.abc import Sequence
from typing import TypedDict

from sqlalchemy import inspect
from sqlalchemy.dialects import sqlite
from sqlalchemy.engine import Connection
from sqlmodel import SQLModel

from app.db import engine

# A single reusable SQLite dialect for compiling column types and quoting
# identifiers safely (D2 remediation DDL below).
_sqlite_dialect = sqlite.dialect()


class TableStructure(TypedDict):
    """The actual structure of one live table.

    ``columns`` maps each live column name to a string rendering of its reflected
    SQL type — enough type info for step 002's ``add_columns`` to key off, while
    step 001's status computation compares only the column-name **sets**.
    """

    name: str
    columns: dict[str, str]  # column name -> reflected type, compiled to a string


class DbStructure(TypedDict):
    """The actual structure of the whole live database.

    ``tables`` maps each live table name to its :class:`TableStructure`. Absence
    of a metadata-expected table name from this mapping is what the service reads
    as ``missing``.
    """

    tables: dict[str, TableStructure]  # live table name -> its structure


async def introspect() -> DbStructure:
    """Reflect the live database's actual structure over the async engine.

    Opens its own connection on ``engine._engine`` and runs SQLAlchemy
    ``inspect()`` under ``run_sync`` to collect the set of live table names and,
    per table, its column name→type mapping. Session-free; opens and closes its
    own connection (nothing leaks). Raises ``RuntimeError`` if the engine has not
    been initialized (mirroring ``get_standalone_session``).
    """
    if engine._engine is None:
        raise RuntimeError(
            "DB engine not initialized — call init_engine(config) before "
            "introspecting the schema."
        )

    async with engine._engine.connect() as conn:
        return await conn.run_sync(_reflect)


def _reflect(sync_conn: Connection) -> DbStructure:
    """Reflect the live structure over a sync-bound connection (run under ``run_sync``)."""
    inspector = inspect(sync_conn)
    tables: dict[str, TableStructure] = {}
    for table_name in inspector.get_table_names():
        columns: dict[str, str] = {
            column["name"]: str(column["type"])
            for column in inspector.get_columns(table_name)
        }
        tables[table_name] = TableStructure(name=table_name, columns=columns)
    return DbStructure(tables=tables)


# ---------------------------------------------------------------------------
# Remediation DDL (feature 007, step 002; decision D2)
#
# The ``db/`` layer is the only place session-free DDL is sanctioned. Each of
# the three ops below opens and closes its own transaction on the async engine
# singleton (``async with engine._engine.begin() as conn: await conn.run_sync(
# ...)``) — mirroring ``introspect`` / ``init_db`` — and drives SQLAlchemy DDL
# under ``run_sync`` against the sync-bound ``Connection``. The **expected**
# shape of a table/column is read from ``SQLModel.metadata`` (the same source
# the service's report reads); nothing leaks past ``db/``.
#
# Skeleton (step 002): signatures are frozen; bodies are UNIMPLEMENTED.
# ---------------------------------------------------------------------------


async def create_table(name: str) -> None:
    """Create ONE table from ``SQLModel.metadata.tables[name]`` (session-free DDL).

    Opens its own transaction on ``engine._engine`` and, under ``run_sync``,
    calls ``SQLModel.metadata.tables[name].create(sync_conn)`` — the single-table
    create that ``create_all`` does not offer. The caller (service
    ``create_missing_table``) guarantees ``name`` is in metadata and currently
    absent. Raises ``RuntimeError`` if the engine is not initialized.
    """
    if engine._engine is None:
        raise RuntimeError(
            "DB engine not initialized — call init_engine(config) before "
            "creating a table."
        )

    table = SQLModel.metadata.tables[name]
    async with engine._engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: table.create(sync_conn, checkfirst=True)
        )


async def add_columns(name: str, columns: Sequence[str]) -> None:
    """Add each named column to live table ``name`` via ``ALTER TABLE ADD COLUMN``.

    For every column in ``columns``, runs
    ``ALTER TABLE <name> ADD COLUMN <col> <compiled-type>`` where the SQL type
    text is the column's type from ``SQLModel.metadata.tables[name].columns[col]``
    compiled against the SQLite dialect (``col.type.compile(dialect=...)``).
    Columns are added **nullable** regardless of the metadata column's
    nullability — SQLite cannot ``ADD COLUMN ... NOT NULL`` without a default
    (a storage-engine constraint, D2). Session-free via ``engine._engine.begin``
    / ``run_sync``. Raises ``RuntimeError`` if the engine is not initialized.
    """
    if engine._engine is None:
        raise RuntimeError(
            "DB engine not initialized — call init_engine(config) before "
            "adding columns."
        )

    table = SQLModel.metadata.tables[name]
    quoted_table = _sqlite_dialect.identifier_preparer.quote(name)
    statements: list[str] = []
    for col_name in columns:
        column = table.columns[col_name]
        # Compile the SQL type text against SQLite; emit the column as NULLABLE
        # regardless of metadata nullability — SQLite cannot ADD a NOT NULL
        # column without a default (D2 hard constraint). No NOT NULL/DEFAULT.
        type_sql = column.type.compile(dialect=_sqlite_dialect)
        quoted_col = _sqlite_dialect.identifier_preparer.quote(col_name)
        statements.append(
            f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_col} {type_sql}"
        )

    async with engine._engine.begin() as conn:
        await conn.run_sync(_exec_statements, statements)


async def drop_columns(name: str, columns: Sequence[str]) -> None:
    """Drop each named column from live table ``name`` via ``ALTER TABLE DROP COLUMN``.

    For every column in ``columns``, runs
    ``ALTER TABLE <name> DROP COLUMN <col>`` (SQLite >= 3.35, satisfied by
    Python 3.13's bundled sqlite). Session-free via ``engine._engine.begin`` /
    ``run_sync``. Raises ``RuntimeError`` if the engine is not initialized.
    """
    if engine._engine is None:
        raise RuntimeError(
            "DB engine not initialized — call init_engine(config) before "
            "dropping columns."
        )

    quoted_table = _sqlite_dialect.identifier_preparer.quote(name)
    statements: list[str] = []
    for col_name in columns:
        quoted_col = _sqlite_dialect.identifier_preparer.quote(col_name)
        statements.append(
            f"ALTER TABLE {quoted_table} DROP COLUMN {quoted_col}"
        )

    async with engine._engine.begin() as conn:
        await conn.run_sync(_exec_statements, statements)


def _exec_statements(sync_conn: Connection, statements: Sequence[str]) -> None:
    """Execute each raw DDL statement over a sync-bound connection (run under ``run_sync``)."""
    for statement in statements:
        sync_conn.exec_driver_sql(statement)
