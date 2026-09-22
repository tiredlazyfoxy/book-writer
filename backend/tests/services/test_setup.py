"""Tests for the setup service + User import/export codec (feature 003, step 003).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 003):
    class SetupError(Exception)                                       in app.services.setup
    MIN_PASSWORD_LENGTH = 8                                           in app.services.setup
    async def create_database(admin_username: str, password: str,
        password_confirm: str) -> User                               in app.services.setup
    async def import_database(archive_bytes: bytes) -> None           in app.services.setup
    async def export_all() -> bytes                                  in app.services.db_import_export
    async def import_all(zip_bytes: bytes) -> None                    in app.services.db_import_export
    async def create(user: User) -> User                             in app.db.users
    async def get_by_username(username: str) -> User | None           in app.db.users
    async def admin_exists() -> bool                                 in app.db.users
    def is_db_ready() -> bool / def set_db_ready(value: bool) -> None in app.db.engine
    class User(SQLModel, table=True) / class UserRole                in app.models.user

Expected values come from the step spec (003.setup-service-user-codec.md DoD +
Interface intent + feature/step context), never from implementation internals:
    - DoD-1 (US-001.AC-1): unconfigured instance + valid credentials ->
      create_database builds the schema, persists an `admin`-role user, leaves
      is_db_ready() True; the returned admin has an id and a signing key;
    - DoD-2 (US-001.AC-2): already-configured (is_db_ready() True) ->
      create_database raises SetupError and does not create a second admin;
    - DoD-3 (US-001.AC-3): password shorter than MIN_PASSWORD_LENGTH (8) ->
      SetupError, instance left unconfigured (is_db_ready() False);
    - DoD-4 (US-001.AC-4): password != confirmation -> SetupError, instance
      left unconfigured;
    - DoD-5 (US-002.AC-1): import_database given a valid `users` archive (from
      export_all after seeding a user) restores the user and leaves the instance
      configured (is_db_ready() True);
    - DoD-6 (US-002.AC-2): import_database given corrupt/invalid bytes raises
      SetupError and leaves the instance unconfigured (set_db_ready not called);
    - DoD-7: the `users` codec round-trips through export_all/import_all — a user
      upserts back with the same username, role, and credential fields (pwdhash,
      jwt_signing_key) and re-import is idempotent.

These are async tests (asyncio_mode = "auto"). The `db` fixture (conftest, step
002) supplies an initialized throwaway temp-SQLite engine (init_engine +
init_db), so the schema is present. The autouse `_reset_db_ready` fixture
(conftest, step 002) resets the process-global readiness flag to False before
each test; per the step context, tests that need an already-configured instance
set that state INSIDE the test.
"""

import pytest

from app.db import users
from app.db.engine import DbConfig, is_db_ready, set_db_ready
from app.models.user import User, UserRole
from app.services import setup
from app.services.db_import_export import export_all, import_all


# DoD-1 (US-001.AC-1): given an unconfigured instance, create_database with valid
# credentials builds the schema, persists an `admin`-role user, and leaves the
# instance configured (is_db_ready() True); the returned admin has an id and a
# signing key.
async def test_create_database_creates_first_admin_and_configures__DoD1(
    db: DbConfig,
):
    # Precondition: the instance is unconfigured (autouse reset -> False).
    assert is_db_ready() is False

    admin = await setup.create_database("root", "password123", "password123")

    # The returned admin carries a generated id and a signing key (per the spec).
    assert admin.id is not None
    assert admin.jwt_signing_key is not None
    assert admin.jwt_signing_key != ""
    # ...and is the `admin` role, under the supplied username.
    assert admin.role == UserRole.admin
    assert admin.username == "root"

    # The admin is persisted and retrievable through the db layer.
    fetched = await users.get_by_username("root")
    assert fetched is not None
    assert fetched.role == UserRole.admin
    assert await users.admin_exists() is True

    # The instance is now configured.
    assert is_db_ready() is True


# DoD-2 (US-001.AC-2): given an already-configured instance (is_db_ready() True),
# create_database raises SetupError and does not create a second admin.
async def test_create_database_refuses_when_already_configured__DoD2(
    db: DbConfig,
):
    # Seed an existing admin and mark the instance configured INSIDE the test
    # (the autouse reset runs before the test, so configured state is set here).
    await users.create(
        User(
            username="root",
            role=UserRole.admin,
            pwdhash="existing-hash",
            jwt_signing_key="existing-key",
        )
    )
    set_db_ready(True)

    with pytest.raises(setup.SetupError):
        await setup.create_database("intruder", "password123", "password123")

    # No second admin was created: the attempted username never persisted.
    assert await users.get_by_username("intruder") is None
    # The original admin is untouched.
    assert await users.get_by_username("root") is not None


# DoD-3 (US-001.AC-3): create_database with a password shorter than
# MIN_PASSWORD_LENGTH (8) raises SetupError and leaves the instance unconfigured.
async def test_create_database_refuses_short_password__DoD3(db: DbConfig):
    # A 5-character password is below the minimum length of 8.
    short_password = "abcde"
    assert len(short_password) < setup.MIN_PASSWORD_LENGTH

    with pytest.raises(setup.SetupError):
        await setup.create_database("root", short_password, short_password)

    # The instance remains unconfigured, and no admin was created.
    assert is_db_ready() is False
    assert await users.admin_exists() is False


# DoD-4 (US-001.AC-4): create_database with password != confirmation raises
# SetupError and leaves the instance unconfigured.
async def test_create_database_refuses_password_mismatch__DoD4(db: DbConfig):
    with pytest.raises(setup.SetupError):
        await setup.create_database("root", "password123", "password999")

    # The instance remains unconfigured, and no admin was created.
    assert is_db_ready() is False
    assert await users.admin_exists() is False


# DoD-5 (US-002.AC-1): import_database given a valid `users` archive (produced by
# export_all after seeding a user) restores the user(s) and leaves the instance
# configured (is_db_ready() True).
async def test_import_database_restores_users_and_configures__DoD5(db: DbConfig):
    # Seed a user with credentials, then produce a valid archive via export_all.
    await users.create(
        User(
            username="scribe",
            role=UserRole.author,
            pwdhash="scribe-hash",
            jwt_signing_key="scribe-key",
        )
    )
    archive_bytes = await export_all()

    # Precondition: unconfigured before the import (autouse reset -> False).
    assert is_db_ready() is False

    await setup.import_database(archive_bytes)

    # The user is restored (present after the import) with its fields intact.
    restored = await users.get_by_username("scribe")
    assert restored is not None
    assert restored.role == UserRole.author

    # The instance is now configured.
    assert is_db_ready() is True


# DoD-6 (US-002.AC-2): import_database given corrupt/invalid bytes raises
# SetupError and leaves the instance unconfigured (set_db_ready not called).
async def test_import_database_refuses_corrupt_archive__DoD6(db: DbConfig):
    with pytest.raises(setup.SetupError):
        await setup.import_database(b"not a zip")

    # The corrupt import is refused and the instance remains unconfigured:
    # set_db_ready was never flipped to True.
    assert is_db_ready() is False


# DoD-7: the `users` codec round-trips through export_all/import_all — a user
# upserts back with the same username, role, and credential fields (pwdhash,
# jwt_signing_key), and re-import is idempotent.
async def test_users_codec_round_trips_and_is_idempotent__DoD7(db: DbConfig):
    seeded = await users.create(
        User(
            username="author1",
            role=UserRole.author,
            pwdhash="hash-abc",
            jwt_signing_key="key-xyz",
        )
    )

    archive_bytes = await export_all()

    # Round-trip: importing the archive upserts the user back with its fields.
    await import_all(archive_bytes)

    restored = await users.get_by_username("author1")
    assert restored is not None
    assert restored.id == seeded.id
    assert restored.username == "author1"
    assert restored.role == UserRole.author
    # The codec includes credentials, so they survive the round-trip.
    assert restored.pwdhash == "hash-abc"
    assert restored.jwt_signing_key == "key-xyz"

    # Idempotent on re-import: importing the same archive again does not error
    # and leaves the user unchanged (same id and fields, no duplication).
    await import_all(archive_bytes)

    reimported = await users.get_by_username("author1")
    assert reimported is not None
    assert reimported.id == seeded.id
    assert reimported.username == "author1"
    assert reimported.role == UserRole.author
    assert reimported.pwdhash == "hash-abc"
    assert reimported.jwt_signing_key == "key-xyz"
