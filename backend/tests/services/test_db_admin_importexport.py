"""Tests for the admin export/import service (feature 007, step 003).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 003):
    app.services.db_admin.export_database() -> bytes
    app.services.db_admin.validate_archive(archive_bytes: bytes) -> None
    app.services.db_admin.import_database(archive_bytes: bytes) -> None
    app.services.db_admin.DbAdminError(case, message="")  # attrs .case, .message
    app.services.db_admin.DbAdminErrorCase.invalid_archive  # value "invalid-archive"

Expected values come from the step spec / D3 + D4 (context.md) and the DoD,
never from implementation internals:
    - `export_database()` is a passthrough to `db_import_export.export_all()`,
      producing a ZIP whose members are the per-table entries of
      `db_import_export.TABLE_REGISTRY` (member name = `entry[0]`, the bare
      table name — never extension-appended).
    - `import_database(bytes)` pre-validates via `validate_archive` (refusing a
      corrupt archive with `DbAdminError(invalid_archive)` BEFORE any mutation),
      then UPSERTs via `import_all` — idempotent (US-019.AC-1/AC-2).
    - `import_database` MUST NOT flip the readiness flag (D4): a successful
      import leaves `is_db_ready()` exactly as it was.

The expected member list is DERIVED from `TABLE_REGISTRY` (not hardcoded) so it
tracks any future model addition. Rows are seeded via the db layer (users, per
the step harness facts) against the throwaway temp DB from the `db` conftest
fixture. Async tests (asyncio_mode = "auto"); the autouse `_reset_db_ready`
fixture sets the readiness flag to `False` before each test.
"""

import io
import zipfile

import pytest

from app.db import users
from app.db.engine import DbConfig, is_db_ready
from app.models.user import User, UserRole
from app.services import db_admin, db_import_export
from app.services.db_admin import DbAdminError, DbAdminErrorCase


def _expected_members() -> list[str]:
    """Per-table member names the export writes / the validator expects, read
    the same way the service does — from `TABLE_REGISTRY` (entry[0] = bare table
    name). Derived, never hardcoded, so it tracks future model additions."""
    members = [entry[0] for entry in db_import_export.TABLE_REGISTRY]
    assert members, "expected at least one table in TABLE_REGISTRY"
    return members


async def _seed_alice() -> None:
    """Seed one row via the db layer (users, per the step harness facts)."""
    await users.create(User(username="alice", role=UserRole.author))


# DoD-1 (US-018.AC-1, service): export_database() returns non-empty bytes that
# open as a valid ZIP containing the expected per-table members.
async def test_export_returns_valid_zip__DoD1_US018_AC1(db: DbConfig):
    data = await db_admin.export_database()

    # Non-empty bytes.
    assert isinstance(data, bytes)
    assert data, "export_database() must return non-empty bytes"

    # Bytes open as a valid ZIP.
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        # Every expected per-table member (bare table name) is present.
        for member in _expected_members():
            assert member in names, (
                f"expected member {member!r} missing from export; got {names!r}"
            )


# DoD-2 (US-019.AC-1): importing a self-produced export through
# import_database(bytes) restores the seeded rows into the DB.
async def test_import_restores_rows__DoD2_US019_AC1(db: DbConfig):
    await _seed_alice()

    archive = await db_admin.export_database()
    await db_admin.import_database(archive)

    # The seeded row is present after the round-trip import.
    restored = await users.get_by_username("alice")
    assert restored is not None, "imported archive must restore the seeded row"
    assert restored.username == "alice"


# DoD-3 (US-019.AC-2): running import_database(bytes) twice with the same export
# yields no duplicate rows (idempotent UPSERT).
async def test_import_is_idempotent__DoD3_US019_AC2(db: DbConfig):
    await _seed_alice()
    assert len(await users.get_all()) == 1

    archive = await db_admin.export_database()

    await db_admin.import_database(archive)
    await db_admin.import_database(archive)

    # Two imports of the same single-row export leave exactly one row.
    assert len(await users.get_all()) == 1


# DoD-4 (US-019.AC-3): import_database(corrupt_bytes) raises
# DbAdminError(invalid-archive) and leaves the database unchanged (no partial
# write — refusal happens before any mutation).
async def test_import_corrupt_archive_rejected__DoD4_US019_AC3(db: DbConfig):
    await _seed_alice()
    before_count = len(await users.get_all())

    corrupt = b"not a valid zip archive"
    with pytest.raises(DbAdminError) as excinfo:
        await db_admin.import_database(corrupt)

    assert excinfo.value.case == DbAdminErrorCase.invalid_archive

    # The DB is unchanged: no partial write from the refused import.
    assert len(await users.get_all()) == before_count


# DoD-5 (D4, no readiness flip): import_database does not toggle the readiness
# flag. is_db_ready() is identical before and after a successful import (the
# service never calls set_db_ready).
async def test_import_does_not_flip_readiness__DoD5_D4(db: DbConfig):
    await _seed_alice()
    archive = await db_admin.export_database()

    before = is_db_ready()
    await db_admin.import_database(archive)

    assert is_db_ready() == before
