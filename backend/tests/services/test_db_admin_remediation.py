"""Tests for schema-drift remediation (feature 007, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002),
reusing the step-001 report DTOs to verify post-remediation state:

    app.services.db_admin.create_missing_table(name: str) -> None
    app.services.db_admin.sync_table_schema(name: str) -> None
    app.services.db_admin.build_consistency_report() -> ConsistencyReport
    app.services.db_admin.DbAdminError(case, message)  (.case, .message)
    app.services.db_admin.DbAdminErrorCase  (enum: not_in_metadata="not-in-metadata",
        table_not_missing="table-not-missing", unknown_table="unknown-table")

    ConsistencyReport.tables: list[TableReportEntry]
    TableReportEntry: name: str, status: Literal['ok','drift','missing'],
                      missing_columns: list[str], extra_columns: list[str]

Expected values come from the step spec / D2 (context.md) and the DoD, never from
implementation internals:
    - `create_missing_table(name)` validates the name is in `SQLModel.metadata` AND
      currently absent from the live DB; on success the table exists and reports ok.
      An unknown name raises `DbAdminError(not_in_metadata)`; an already-present table
      raises `DbAdminError(table_not_missing)`; the DB is unchanged in both guards.
    - `sync_table_schema(name)` recomputes the drift and ADDs `missing_columns` +
      DROPs `extra_columns` so the table then reports ok.

Reconciled after feedback round 1 (012.assistant-config-editor -> F1, decision
D-c): `status` gained a fourth value, `seed-missing`, for a present and
schema-clean table whose required seed rows are absent, and schema remediation
deliberately does NOT seed — seeding is a separate action. Both remediation
tests below therefore target a table OUTSIDE the one-entry seed registry
(`assistant_modes`, F1 point 4), so `ok` after `create` / `sync` stays a pure
schema verdict. The identity of the table is incidental to what they assert;
what they assert — that `create` makes a missing table exist with the right
columns and that `sync` drops extra columns — is unchanged.

Tests read the EXPECTED structure the same way the service does — from
`SQLModel.metadata` — so they stay valid as the registered table set grows (today
`users`, `llm_servers`; more later). Drift/missing scenarios are seeded in the
throwaway temp DB from the `db` conftest fixture via raw DDL against the async
engine primitive (`app.db.engine._engine`), exactly as the step brief prescribes.

Async tests (asyncio_mode = "auto"); the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with all registered tables created.
"""

import pytest
from sqlmodel import SQLModel

import app.db.engine as engine_module
from app.db.engine import DbConfig
from app.services import db_admin
from app.services.db_admin import DbAdminError, DbAdminErrorCase


def _expected_tables() -> dict[str, set[str]]:
    """Expected structure read the same way the service does: table name -> set of
    column names, from `SQLModel.metadata`."""
    return {
        name: set(table.columns.keys())
        for name, table in SQLModel.metadata.tables.items()
    }


def _pick_table() -> str:
    """Deterministically pick one registered (metadata) table name, without
    hardcoding the table list (it may grow as features are added)."""
    names = sorted(_expected_tables())
    assert names, "expected at least one registered table in SQLModel.metadata"
    return names[0]


# The seed registry holds exactly ONE entry today — `assistant_modes`
# (feedback round 1 -> F1 point 4). A schema-clean but rowless table there
# reports `seed-missing`, not `ok`, so tests whose subject is *schema*
# remediation must not target it.
SEED_REGISTRY_TABLES = {"assistant_modes"}


def _pick_table_outside_seed_registry() -> str:
    """Deterministically pick one registered (metadata) table that is NOT in the
    seed registry, so its post-remediation status is a pure schema verdict."""
    names = [
        name for name in sorted(_expected_tables())
        if name not in SEED_REGISTRY_TABLES
    ]
    assert names, "expected at least one registered table outside the seed registry"
    return names[0]


def _pick_table_with_columns(min_cols: int) -> str:
    """Deterministically pick a registered table having at least `min_cols`
    metadata columns, without hardcoding the table list."""
    expected = _expected_tables()
    for name in sorted(expected):
        if len(expected[name]) >= min_cols:
            return name
    raise AssertionError(
        f"no registered metadata table has >= {min_cols} columns; "
        f"cannot construct the drift scenario"
    )


async def _exec_ddl(sql: str) -> None:
    """Run one raw DDL statement against the live temp DB via the async engine
    primitive frozen for this feature (`engine._engine`)."""
    engine = engine_module._engine
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: sync_conn.exec_driver_sql(sql))


def _by_name(report) -> dict[str, object]:
    return {entry.name: entry for entry in report.tables}


def _snapshot(report) -> dict[str, tuple]:
    """A comparable snapshot of a report: table name -> (status, sorted missing,
    sorted extra). Used to assert the DB is unchanged across a guarded call."""
    return {
        entry.name: (
            entry.status,
            tuple(sorted(entry.missing_columns)),
            tuple(sorted(entry.extra_columns)),
        )
        for entry in report.tables
    }


# DoD-1 (US-016.AC-1): given a table reported `missing`, `create_missing_table(name)`
# creates it and a fresh consistency report then shows that table as `ok`.
async def test_create_missing__DoD1_US016_AC1(db: DbConfig):
    # A non-registry table: post-F1, creating a *seedable* table leaves it
    # schema-clean but rowless (`seed-missing`) because seeding is a separate
    # action, and this test is about the schema verdict alone.
    target = _pick_table_outside_seed_registry()

    # Seed the "missing" scenario: drop the live table so it is absent from the
    # actual structure while still present in metadata.
    await _exec_ddl(f"DROP TABLE {target}")

    # Precondition: the report classifies the dropped table as 'missing'.
    pre = _by_name(await db_admin.build_consistency_report())
    assert pre[target].status == "missing"

    await db_admin.create_missing_table(target)

    # A fresh report now shows the table 'ok' with empty diff lists.
    post = _by_name(await db_admin.build_consistency_report())
    assert target in post, f"table {target!r} must be reported after creation"
    assert post[target].status == "ok"
    assert post[target].missing_columns == []
    assert post[target].extra_columns == []


# DoD-2 (US-016 guard): `create_missing_table` on a name NOT in `SQLModel.metadata`
# raises `DbAdminError(not_in_metadata)` and leaves the DB unchanged.
async def test_create_missing_unknown_name_rejected__DoD2_US016(db: DbConfig):
    before = _snapshot(await db_admin.build_consistency_report())

    with pytest.raises(DbAdminError) as exc:
        await db_admin.create_missing_table("definitely_not_a_real_table")

    assert exc.value.case == DbAdminErrorCase.not_in_metadata

    # The DB is unchanged: same tables, same statuses, same column diffs.
    after = _snapshot(await db_admin.build_consistency_report())
    assert after == before


# DoD-2 (US-016 guard): `create_missing_table` on a table that already exists
# raises `DbAdminError(table_not_missing)` and leaves the DB unchanged.
async def test_create_missing_already_present_rejected__DoD2_US016(db: DbConfig):
    target = _pick_table()  # present in the freshly-built DB
    before = _snapshot(await db_admin.build_consistency_report())

    with pytest.raises(DbAdminError) as exc:
        await db_admin.create_missing_table(target)

    assert exc.value.case == DbAdminErrorCase.table_not_missing

    # The DB is unchanged: no table added or dropped, no column diffs introduced.
    after = _snapshot(await db_admin.build_consistency_report())
    assert after == before


# DoD-3 (US-017.AC-1): given a table in `drift` with MISSING columns,
# `sync_table_schema(name)` adds them; a fresh report then lists no
# `missing_columns` for that table.
async def test_sync_adds_missing_columns__DoD3_US017_AC1(db: DbConfig):
    target = _pick_table_with_columns(2)
    expected_cols = _expected_tables()[target]

    # Seed "drift with missing columns": replace the live table with one carrying
    # only a single metadata column (column-NAME sets differ), so every other
    # metadata column is missing. Type is irrelevant — the report diffs on names.
    keep = sorted(expected_cols)[0]
    await _exec_ddl(f"DROP TABLE {target}")
    await _exec_ddl(f"CREATE TABLE {target} ({keep} TEXT)")

    # Precondition: the seeded state is drift with a non-empty missing set.
    pre = _by_name(await db_admin.build_consistency_report())
    assert pre[target].status == "drift"
    assert set(pre[target].missing_columns) == (expected_cols - {keep})

    await db_admin.sync_table_schema(target)

    # A fresh report lists no missing columns for the synced table.
    post = _by_name(await db_admin.build_consistency_report())
    assert post[target].missing_columns == []


# DoD-4 (US-017.AC-2): given a table in `drift` with EXTRA columns,
# `sync_table_schema(name)` drops them and a fresh report shows the table `ok`.
async def test_sync_drops_extra_columns__DoD4_US017_AC2(db: DbConfig):
    # A non-registry table: post-F1, syncing a *seedable* table leaves it
    # schema-clean but rowless (`seed-missing`) because seeding is a separate
    # action, and this test is about the schema verdict alone.
    target = _pick_table_outside_seed_registry()

    # Seed "drift with extra columns": add a column that is NOT part of the
    # table's metadata, so the live column-NAME set has one column too many.
    await _exec_ddl(f"ALTER TABLE {target} ADD COLUMN zzz_drift_extra_col TEXT")

    # Precondition: the seeded state is drift with the injected extra column.
    pre = _by_name(await db_admin.build_consistency_report())
    assert pre[target].status == "drift"
    assert set(pre[target].extra_columns) == {"zzz_drift_extra_col"}

    await db_admin.sync_table_schema(target)

    # A fresh report shows the table 'ok' with the extra column dropped.
    post = _by_name(await db_admin.build_consistency_report())
    assert post[target].status == "ok"
    assert post[target].extra_columns == []
    assert post[target].missing_columns == []
