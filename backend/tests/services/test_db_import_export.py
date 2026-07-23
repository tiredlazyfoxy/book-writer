"""Tests for the JSONL import/export mechanism and the registered users codec.

Bound to the frozen skeleton signatures (status.md -> Skeleton):
    async def export_all() -> bytes                     in app.services.db_import_export
    async def import_all(zip_bytes: bytes) -> None       in app.services.db_import_export
    TABLE_REGISTRY: list[RegistryEntry]                  in app.services.db_import_export
        -> [("users", User, _user_to_dict, _dict_to_user)]  (Step 003 skeleton);
           each entry's FIRST element is the zip member filename ("users" for
           the users entry) and its SECOND element is the model class (User).
    BATCH_SIZE = 100                                     in app.services.db_import_export
    async def init_db() -> None                          in app.db.engine

Expected values come from the step spec (003 DoD-8 + the frozen skeleton),
never from implementation internals:
    - TABLE_REGISTRY is no longer empty: the first persistent model (`users`) is
      now registered as its first (FK-order) entry, so export_all() yields an
      archive whose members reflect the registered tables (a `users` member)
      rather than an empty archive. This retires feature 001 / step 004's
      transient "empty registry" precondition (valid only before the first
      persistent model existed).
    - import_all(export_all()) is an idempotent no-op over a DB with no user
      rows that still runs init_db() as part of its flow,
    - the mechanism round-trips the archive: after import_all() the DB is still
      usable (readiness holds via db.health.ping() -> True) and import_all can
      be re-run safely.

These are async tests (asyncio_mode = "auto"). The `db` fixture (conftest, step
002) supplies an initialized throwaway temp-SQLite engine so the import flow —
which calls init_db() against an already-initialized engine — can run.
"""

import io
import zipfile

import app.db.engine as engine_module
from app.db.engine import DbConfig
from app.db.health import ping
from app.ids import generate_id
from app.models.user import User, UserRole
from app.services.db_import_export import (
    TABLE_REGISTRY,
    _dict_to_user,
    _user_to_dict,
    export_all,
    import_all,
)


# F003 DoD-8: the users codec is now registered — TABLE_REGISTRY is non-empty
# and its first entry is the `users` entry, so export_all() yields an archive
# that includes the `users` member rather than an empty archive. This retires
# feature 001 / step 004's transient "empty registry" precondition while
# preserving the mechanism coverage.
async def test_export_all_includes_registered_users_member__F003_DoD8(db: DbConfig):
    # The registry is no longer empty: the first persistent model (`users`) is
    # registered as the first (FK-order) entry. Per the frozen skeleton each
    # entry's first element is the zip member filename and its second element is
    # the model class.
    registry = list(TABLE_REGISTRY)
    assert registry, "TABLE_REGISTRY must contain the registered users entry"
    first_entry = registry[0]
    assert first_entry[0] == "users"
    assert first_entry[1] is User

    archive_bytes = await export_all()

    # The return type is bytes...
    assert isinstance(archive_bytes, (bytes, bytearray))

    # ...and those bytes open as a genuine zip archive (ZipFile raises
    # BadZipFile on invalid input) whose members reflect the registered tables.
    # Per F003 DoD-8 the `users` member must be present and first (FK-order);
    # other features may append further members, so this is not an exact match.
    with zipfile.ZipFile(io.BytesIO(bytes(archive_bytes))) as zf:
        members = zf.namelist()
        assert "users" in members
        assert members[0] == "users"


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


# fast/001 DoD-5: _user_to_dict serializes `id` as a JSON string equal to
# str(user.id), and feeding that same dict back through _dict_to_user round-trips
# to the correct int id (64-bit ids exceed JS Number.MAX_SAFE_INTEGER, so they
# cross the JSON boundary as strings). These codecs are pure transforms, so no DB
# fixture is needed.
def test_user_codec_serializes_id_as_string_and_round_trips__fast001_DoD5():
    # A User carrying a real snowflake-shaped id (populated at construction).
    user = User(id=generate_id(), username="codexuser", role=UserRole.author)

    data = _user_to_dict(user)

    # The exported id is a JSON string equal to str(user.id).
    assert isinstance(data["id"], str)
    assert data["id"] == str(user.id)

    # Feeding that dict back in parses the string to the original int id.
    restored = _dict_to_user(data)
    assert restored.id == user.id


# fast/001 DoD-6: _dict_to_user accepts a legacy dict whose `id` is a JSON NUMBER
# (a plain int) and imports it to the correct int id, so pre-snowflake archives
# still import (back-compat). The valid dict shape is obtained from _user_to_dict
# so only the id value differs from a real export.
def test_user_codec_accepts_legacy_int_id__fast001_DoD6():
    # Start from a genuinely-shaped export dict, then downgrade `id` to a legacy
    # JSON number (int) as pre-snowflake archives stored it.
    data = _user_to_dict(User(id=generate_id(), username="legacyuser", role=UserRole.admin))
    data["id"] = 42

    restored = _dict_to_user(data)

    # The legacy numeric id is imported to the correct int.
    assert restored.id == 42
