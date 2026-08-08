"""Seed detection and the seed remediation in the DB-admin service layer.

Feedback round 1, item **F1** — "No operator-reachable way to seed the five
assistant modes into an existing database". Reproduces: a present, schema-clean
`assistant_modes` table holding **zero rows** is reported `ok` today, and there
is no service call an operator can reach to create the missing rows.

Bound to the frozen signatures (status.md -> `## Skeleton` -> "Feedback round 1,
item F1 — re-freeze"), plus the pre-existing ones:

    app.services.db_admin:
        async def build_consistency_report() -> ConsistencyReport
        async def seed_table_rows(name: str) -> None                  # new
        class DbAdminErrorCase(str, enum.Enum)                        # + not_seedable
        class DbAdminError(Exception)                                 # .case / .message
    app.models.schemas.db_admin:
        class TableReportEntry(BaseModel)
            name / status: Literal["ok","drift","missing","seed-missing"]
            missing_columns / extra_columns / missing_seed_keys: list[str]
    app.db.assistant_modes:
        DEFAULT_MODE_KEYS: tuple[str, ...]
        async def create(row) / get_by_id(key) / list_all()

THE AIR GAP — no source is read here. Every expected value comes from
`docs/plans/012.assistant-config-editor/feedback.md` -> F1, points 1-7:

  - point 1: `status` gains a fourth value `"seed-missing"` (present + schema
    clean + one or more required seed rows absent) and the entry gains
    `missing_seed_keys`, listing exactly the absent keys, EMPTY for every other
    table and every other status;
  - point 2: precedence — schema outranks rows, always. Absent from the live DB
    is `missing`; column drift is `drift`; only present-and-schema-clean can ever
    be `seed-missing`; present, clean and fully seeded is `ok`;
  - point 3: presence of keys, not a row count. A row with an unrecognised key is
    not an error, is not reported and is not removed;
  - point 4: the registry holds exactly one entry, `assistant_modes`; every table
    without an entry is never `seed-missing`;
  - point 6: seeding an already-complete table is a no-op that does not raise; a
    name not in the schema metadata is `unknown_table`; a real table with no
    registry entry, or one whose schema is `missing`/`drift`, is `not_seedable`;
  - point 7: existing rows — including an admin-edited `system_prompt` — are
    untouched throughout.

The five keys are the product's fixed system set (feedback.md F1 point 1 ->
`DEFAULT_MODE_KEYS`; `001.context.md`): edit-character, edit-location, edit-fact,
write-chapter, close-chapter.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine, so the schema is present and the
instance starts with zero `AssistantMode` rows — exactly the state F1 reports.
Raw DDL is used to arrange schema drift / absence, mirroring
`tests/routes/admin/test_db.py`'s `_exec_ddl`.
"""

import pytest

import app.db.engine as engine_module
from app.db import assistant_modes
from app.db.engine import DbConfig
from app.models.assistant_mode import AssistantMode
from app.models.schemas.db_admin import TableReportEntry
from app.services import db_admin

MODES_TABLE = "assistant_modes"

# The fixed five (feedback.md F1 point 1 -> the members of DEFAULT_MODE_KEYS).
FIXED_FIVE_KEYS = {
    "edit-character",
    "edit-location",
    "edit-fact",
    "write-chapter",
    "close-chapter",
}


async def _exec_ddl(sql: str) -> None:
    """Run a raw DDL statement against the process-global engine."""
    async with engine_module._engine.begin() as conn:
        await conn.run_sync(lambda c: c.exec_driver_sql(sql))


async def _entry(name: str) -> TableReportEntry:
    report = await db_admin.build_consistency_report()
    return next(e for e in report.tables if e.name == name)


async def _create_mode(key: str, prompt: str | None = None) -> None:
    await assistant_modes.create(AssistantMode(key=key, system_prompt=prompt))


# ---------------------------------------------------------------------------
# Detection (F1 points 1, 3, 4)
# ---------------------------------------------------------------------------


# F1 point 1 — reproduces: a present, schema-clean `assistant_modes` with zero
# rows is reported `ok` today, so the operator is never told anything is wrong.
async def test_report_flags_unseeded_assistant_modes__F1(db: DbConfig):
    assert len(await assistant_modes.list_all()) == 0

    entry = await _entry(MODES_TABLE)

    assert entry.status == "seed-missing"
    # Exactly the absent members of DEFAULT_MODE_KEYS — all five here.
    assert set(entry.missing_seed_keys) == FIXED_FIVE_KEYS
    assert len(entry.missing_seed_keys) == 5
    # The schema itself is clean; only rows are at issue.
    assert entry.missing_columns == []
    assert entry.extra_columns == []


# F1 points 1 + 3 — a PARTIALLY seeded table is still `seed-missing`, and it
# lists only the keys that have no row (presence of keys, not a row count).
async def test_report_lists_only_the_absent_seed_keys__F1(db: DbConfig):
    present = {"edit-character", "write-chapter"}
    for key in sorted(present):
        await _create_mode(key)

    entry = await _entry(MODES_TABLE)

    assert entry.status == "seed-missing"
    assert set(entry.missing_seed_keys) == FIXED_FIVE_KEYS - present


# F1 point 2 — a present, schema-clean, FULLY seeded table is `ok` and carries
# no missing keys.
async def test_report_ok_once_every_key_has_a_row__F1(db: DbConfig):
    for key in sorted(FIXED_FIVE_KEYS):
        await _create_mode(key)

    entry = await _entry(MODES_TABLE)

    assert entry.status == "ok"
    assert entry.missing_seed_keys == []


# F1 point 2 — precedence: schema outranks rows, ALWAYS. With zero mode rows
# throughout (the seed-missing precondition), column drift must still report
# `drift` and an absent table must still report `missing` — never
# `seed-missing`, so seeding is never offered against a table that cannot
# receive rows.
async def test_schema_status_outranks_row_status__F1(db: DbConfig):
    assert len(await assistant_modes.list_all()) == 0

    await _exec_ddl(f"ALTER TABLE {MODES_TABLE} ADD COLUMN drift_probe TEXT")
    drifted = await _entry(MODES_TABLE)
    assert drifted.status == "drift"
    assert "drift_probe" in drifted.extra_columns
    assert drifted.missing_seed_keys == []

    await _exec_ddl(f"DROP TABLE {MODES_TABLE}")
    absent = await _entry(MODES_TABLE)
    assert absent.status == "missing"
    assert absent.missing_seed_keys == []


# F1 points 1 + 4 — no regression in the three existing statuses: every table
# without a registry entry keeps reporting exactly what it reports today and
# carries an EMPTY `missing_seed_keys`, whatever its status.
async def test_other_tables_keep_their_status_and_carry_no_seed_keys__F1(db: DbConfig):
    await _exec_ddl("ALTER TABLE users ADD COLUMN drift_probe TEXT")
    await _exec_ddl("DROP TABLE llm_servers")

    report = await db_admin.build_consistency_report()
    others = [e for e in report.tables if e.name != MODES_TABLE]
    assert len(others) > 0

    for entry in others:
        # Never `seed-missing`: only the one registry entry can be.
        assert entry.status in {"ok", "drift", "missing"}
        assert entry.missing_seed_keys == []

    by_name = {e.name: e for e in others}
    assert by_name["users"].status == "drift"
    assert "drift_probe" in by_name["users"].extra_columns
    assert by_name["llm_servers"].status == "missing"


# F1 point 3 — a row carrying an unrecognised key (reachable via an imported
# archive) is NOT an error: it is not reported and it is not removed.
async def test_unrecognised_mode_key_is_neither_reported_nor_removed__F1(db: DbConfig):
    for key in sorted(FIXED_FIVE_KEYS):
        await _create_mode(key)
    await _create_mode("imported-unknown-mode", "From an archive.")

    entry = await _entry(MODES_TABLE)
    assert entry.status == "ok"
    assert entry.missing_seed_keys == []

    await db_admin.seed_table_rows(MODES_TABLE)

    stray = await assistant_modes.get_by_id("imported-unknown-mode")
    assert stray is not None
    assert stray.system_prompt == "From an archive."
    assert len(await assistant_modes.list_all()) == 6


# ---------------------------------------------------------------------------
# The fix (F1 points 5, 6, 7)
# ---------------------------------------------------------------------------


# F1 points 5 + 6 — reproduces: there is no service-level way to create the
# missing rows. Seeding creates all five keys and flips the row to `ok`; running
# it again is an idempotent no-op that does not raise.
async def test_seed_table_rows_creates_the_five_and_is_idempotent__F1(db: DbConfig):
    await db_admin.seed_table_rows(MODES_TABLE)

    rows = await assistant_modes.list_all()
    assert {row.key for row in rows} == FIXED_FIVE_KEYS
    assert len(rows) == 5

    entry = await _entry(MODES_TABLE)
    assert entry.status == "ok"
    assert entry.missing_seed_keys == []

    # Already complete: a no-op that still succeeds (no refusal, no duplicate).
    await db_admin.seed_table_rows(MODES_TABLE)
    assert len(await assistant_modes.list_all()) == 5


# F1 point 7 — existing rows are untouched: an admin-edited `system_prompt`
# survives the seed verbatim, and the rows the seed creates carry no prompt.
async def test_seed_table_rows_preserves_an_edited_prompt__F1(db: DbConfig):
    await _create_mode("edit-fact", "Admin-edited prompt for edit-fact.")

    await db_admin.seed_table_rows(MODES_TABLE)

    edited = await assistant_modes.get_by_id("edit-fact")
    assert edited is not None
    assert edited.system_prompt == "Admin-edited prompt for edit-fact."

    rows = await assistant_modes.list_all()
    assert {row.key for row in rows} == FIXED_FIVE_KEYS
    assert len(rows) == 5
    for row in rows:
        if row.key != "edit-fact":
            assert row.system_prompt is None


# F1 point 6 — refusals that need no schema arrangement: a name not in the
# schema metadata is `unknown_table`; a real metadata table with no registry
# entry is `not_seedable` (the registry holds exactly one entry).
@pytest.mark.parametrize(
    "name,expected_case",
    [
        ("definitely_not_a_table", db_admin.DbAdminErrorCase.unknown_table),
        ("users", db_admin.DbAdminErrorCase.not_seedable),
    ],
)
async def test_seed_table_rows_refusals__F1(
    db: DbConfig, name: str, expected_case: db_admin.DbAdminErrorCase
):
    with pytest.raises(db_admin.DbAdminError) as excinfo:
        await db_admin.seed_table_rows(name)

    assert excinfo.value.case is expected_case


# F1 point 6 — a registry table whose schema is `drift` or `missing` cannot
# receive rows, so seeding it is refused with `not_seedable` (never a silent
# success and never an escaping DB error).
async def test_seed_table_rows_refuses_an_unclean_schema__F1(db: DbConfig):
    await _exec_ddl(f"ALTER TABLE {MODES_TABLE} ADD COLUMN drift_probe TEXT")
    with pytest.raises(db_admin.DbAdminError) as drifted:
        await db_admin.seed_table_rows(MODES_TABLE)
    assert drifted.value.case is db_admin.DbAdminErrorCase.not_seedable

    await _exec_ddl(f"DROP TABLE {MODES_TABLE}")
    with pytest.raises(db_admin.DbAdminError) as absent:
        await db_admin.seed_table_rows(MODES_TABLE)
    assert absent.value.case is db_admin.DbAdminErrorCase.not_seedable
