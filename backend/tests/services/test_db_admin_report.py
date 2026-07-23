"""Tests for the schema-drift consistency report (feature 007, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    app.services.db_admin.build_consistency_report() -> ConsistencyReport
    ConsistencyReport.tables: list[TableReportEntry]
    TableReportEntry fields: name: str,
                             status: Literal['ok','drift','missing'],
                             missing_columns: list[str],
                             extra_columns: list[str]

Expected values come from the step spec / D1 (context.md) and the DoD, never
from implementation internals:
    - `build_consistency_report()` reads the EXPECTED structure from
      `SQLModel.metadata` (table names + per-table column names) and the ACTUAL
      structure from the live DB, then computes per expected table:
        * `missing` — expected table absent from the live DB;
        * `drift`   — present but the column-NAME sets differ;
        * `ok`      — column-name sets match.
      For a drifted table: `missing_columns = expected - actual`,
      `extra_columns = actual - expected`; `ok`/`missing` tables carry empty
      lists.

Tests read the expected structure the SAME way the service does — from
`SQLModel.metadata` — so they stay valid as the registered table set grows
(today `users`, `llm_servers`; more later). Drift/missing scenarios are built in
the throwaway temp DB from the `db` conftest fixture via raw DDL against the
async engine primitive (`app.db.engine._engine`), exactly as the step brief
prescribes.

Async tests (asyncio_mode = "auto"); the `db` fixture (conftest, step 002)
supplies an initialized throwaway temp-SQLite engine with all registered tables
created.
"""

from sqlmodel import SQLModel

import app.db.engine as engine_module
from app.db.engine import DbConfig
from app.services import db_admin


def _expected_tables() -> dict[str, set[str]]:
    """Expected structure read the same way the service does: table name ->
    set of column names, from `SQLModel.metadata`."""
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


async def _exec_ddl(sql: str) -> None:
    """Run one raw DDL statement against the live temp DB via the async engine
    primitive frozen for this feature (`engine._engine`)."""
    engine = engine_module._engine
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: sync_conn.exec_driver_sql(sql))


def _by_name(report) -> dict[str, object]:
    return {entry.name: entry for entry in report.tables}


# DoD-1 (US-015.AC-1): given a DB whose tables all match metadata,
# build_consistency_report() returns an entry for EVERY expected table, each
# with status 'ok' (and, per spec, empty missing/extra column lists).
async def test_all_match__DoD1_US015_AC1(db: DbConfig):
    expected = _expected_tables()

    report = await db_admin.build_consistency_report()
    entries = _by_name(report)

    # An entry exists for every expected (metadata) table.
    for name in expected:
        assert name in entries, f"no report entry for expected table {name!r}"
        entry = entries[name]
        # A clean, freshly-created DB matches metadata -> status 'ok'.
        assert entry.status == "ok"
        # ok tables carry empty column-diff lists.
        assert entry.missing_columns == []
        assert entry.extra_columns == []


# DoD-2 (US-015.AC-1): given a DB missing an expected table (dropped), that
# table's entry reports status 'missing'.
async def test_missing_table__DoD2_US015_AC1(db: DbConfig):
    target = _pick_table()

    # Drop the live table so it is absent from the actual structure while still
    # present in metadata (the expected structure).
    await _exec_ddl(f"DROP TABLE {target}")

    report = await db_admin.build_consistency_report()
    entries = _by_name(report)

    assert target in entries, f"missing table {target!r} must still be reported"
    entry = entries[target]
    assert entry.status == "missing"
    # missing tables carry empty column-diff lists.
    assert entry.missing_columns == []
    assert entry.extra_columns == []


# DoD-3 (US-015.AC-1): given a DB whose table has a column set differing from
# metadata (an extra column added by raw ALTER), that table's entry reports
# status 'drift'.
async def test_drift_status__DoD3_US015_AC1(db: DbConfig):
    target = _pick_table()

    # Add a column that is NOT part of the table's metadata -> the live and
    # expected column-name sets now differ.
    await _exec_ddl(f"ALTER TABLE {target} ADD COLUMN zzz_drift_extra_col TEXT")

    report = await db_admin.build_consistency_report()
    entries = _by_name(report)

    assert target in entries
    assert entries[target].status == "drift"


# DoD-4 (US-015.AC-2): for a drifted table, extra_columns lists columns present
# live but absent from metadata; with only an extra column added (nothing
# removed), missing_columns is empty. Lists are disjoint.
async def test_drift_extra_column_diff__DoD4_US015_AC2(db: DbConfig):
    target = _pick_table()

    await _exec_ddl(f"ALTER TABLE {target} ADD COLUMN zzz_drift_extra_col TEXT")

    report = await db_admin.build_consistency_report()
    entry = _by_name(report)[target]

    # extra_columns = actual - expected = just the injected column.
    assert set(entry.extra_columns) == {"zzz_drift_extra_col"}
    # Nothing was removed, so no metadata column is absent live.
    assert entry.missing_columns == []
    # The two diff lists are disjoint.
    assert set(entry.missing_columns).isdisjoint(set(entry.extra_columns))


# DoD-4 (US-015.AC-2): for a drifted table, missing_columns lists columns
# present in metadata but absent live, and extra_columns lists columns present
# live but absent from metadata — each correct and disjoint. Constructed by
# replacing the live table with one carrying a single unknown column, so every
# metadata column is missing and the sole live column is extra.
async def test_drift_missing_and_extra_column_diffs__DoD4_US015_AC2(db: DbConfig):
    target = _pick_table()
    # Expected columns read from metadata (unaffected by the live-DB rewrite).
    expected_cols = _expected_tables()[target]
    assert expected_cols, f"table {target!r} must define columns in metadata"

    # Replace the live table with one whose only column is not in metadata:
    # every expected column becomes absent (missing) and the probe column is
    # extra.
    await _exec_ddl(f"DROP TABLE {target}")
    await _exec_ddl(f"CREATE TABLE {target} (zzz_probe_only_col TEXT)")

    report = await db_admin.build_consistency_report()
    entry = _by_name(report)[target]

    # missing_columns = expected - actual = all metadata columns (none live).
    assert set(entry.missing_columns) == expected_cols
    # extra_columns = actual - expected = the sole injected probe column.
    assert set(entry.extra_columns) == {"zzz_probe_only_col"}
    # The diff lists are disjoint.
    assert set(entry.missing_columns).isdisjoint(set(entry.extra_columns))
