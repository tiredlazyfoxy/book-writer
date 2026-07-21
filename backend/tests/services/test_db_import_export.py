"""Tests for the JSONL import/export mechanism (step 004).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 004):
    async def export_all() -> bytes                    in app.services.db_import_export
    async def import_all(zip_bytes: bytes) -> None      in app.services.db_import_export
    TABLE_REGISTRY: list[...] = []  (empty)             in app.services.db_import_export
    BATCH_SIZE = 100                                    in app.services.db_import_export
    async def init_db() -> None                         in app.db.engine

Expected values come from the step spec (004.import-export-mechanism.md DoD +
context), never from implementation internals:
    - the TABLE_REGISTRY is empty for feature 001, so export_all() yields a
      valid but *empty* zip archive (no `<table>.jsonl.gz` members),
    - import_all(export_all()) is an idempotent no-op over the empty registry
      that still runs init_db() as part of its flow,
    - the mechanism round-trips the empty archive: after import_all() the DB is
      still usable (readiness holds via db.health.ping() -> True) and import_all
      can be re-run safely.

These are async tests (asyncio_mode = "auto"). The `db` fixture (conftest, step
002) supplies an initialized throwaway temp-SQLite engine so the import flow —
which calls init_db() against an already-initialized engine — can run.
"""

import io
import zipfile

import app.db.engine as engine_module
from app.db.engine import DbConfig
from app.db.health import ping
from app.services.db_import_export import (
    TABLE_REGISTRY,
    export_all,
    import_all,
)


# DoD-1: export_all() over the empty registry returns bytes that parse as a
# valid (empty) zip archive — no `<table>.jsonl.gz` members.
async def test_export_all_returns_valid_empty_zip__DoD1(db: DbConfig):
    # Precondition from the spec: the registry is empty for feature 001, so
    # there is nothing to serialize into the archive.
    assert list(TABLE_REGISTRY) == []

    archive_bytes = await export_all()

    # The return type is bytes...
    assert isinstance(archive_bytes, (bytes, bytearray))

    # ...and those bytes open as a genuine zip archive (ZipFile raises
    # BadZipFile on invalid input) with zero entries — the empty registry means
    # no `<table>.jsonl.gz` members are present.
    with zipfile.ZipFile(io.BytesIO(bytes(archive_bytes))) as zf:
        assert zf.namelist() == []


# DoD-2: import_all(export_all()) completes without error as an idempotent
# no-op over the empty registry.
async def test_import_all_empty_is_idempotent_noop__DoD2(db: DbConfig):
    archive_bytes = await export_all()

    # Importing the empty archive must complete without raising...
    await import_all(archive_bytes)
    # ...and re-importing it must also complete without raising (idempotent).
    await import_all(archive_bytes)

    # The database remains usable after the no-op import.
    assert await ping() is True


# DoD-2: import_all() invokes init_db() as part of its flow (the spec: it calls
# init_db() first, before streaming/upserting). Asserted via a spy on the
# public engine API named in the spec — the observable effect (an initialized
# DB) is insufficient here because the empty registry creates no tables, so an
# initialized-engine round-trip is indistinguishable from a skipped init_db().
async def test_import_all_invokes_init_db__DoD2(db: DbConfig, monkeypatch):
    original_init_db = engine_module.init_db
    calls = {"count": 0}

    async def spy_init_db() -> None:
        calls["count"] += 1
        await original_init_db()

    monkeypatch.setattr(engine_module, "init_db", spy_init_db)

    archive_bytes = await export_all()
    await import_all(archive_bytes)

    # init_db() was invoked as part of the import flow (the spy fired after the
    # fixture's own setup call, which happened before the spy was installed).
    assert calls["count"] >= 1


# DoD-3: the mechanism round-trips the empty archive — import_all(export_all())
# leaves the DB usable (readiness still holds) and can be re-run safely.
async def test_empty_archive_round_trip_keeps_db_usable_and_rerunnable__DoD3(
    db: DbConfig,
):
    # Round-trip: export then import the empty archive.
    await import_all(await export_all())

    # Readiness still holds after the round-trip.
    assert await ping() is True

    # Re-running the round-trip is safe (idempotent, no error)...
    await import_all(await export_all())

    # ...and the DB is still ready afterwards.
    assert await ping() is True
