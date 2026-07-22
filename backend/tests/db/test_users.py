"""Tests for the session-free db/users access layer (feature 003, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    class UserRole(str, enum.Enum)  {admin="admin", author="author"}  in app.models.user
    class User(SQLModel, table=True) __tablename__="users"; id: int | None,
        username: str (unique/index), pwdhash: str | None, role: UserRole
        (required, no default), jwt_signing_key: str | None, last_login,
        last_key_update                                                in app.models.user
    async def create(user: User) -> User                              in app.db.users
    async def get_by_username(username: str) -> User | None            in app.db.users
    async def get_by_id(user_id: int) -> User | None                  in app.db.users
    async def admin_exists() -> bool                                  in app.db.users
    @dataclass class DbConfig(db_path, echo=False)                    in app.db.engine
    async def init_engine(config: DbConfig) -> None                   in app.db.engine

Expected values come from the step spec (001.user-model-auth-primitives.md DoD +
context) and the feature context, never from implementation internals:
    - create then get_by_username round-trips the stored user (same username and
      role), and create populates the generated id (DoD-3),
    - admin_exists() is False with no admin present and True once an admin user
      exists; the discriminator is the `admin` role (DoD-4),
    - admin_exists() returns False *gracefully* (no unhandled error) when the
      `users` table does not exist — a cold instance (DoD-5).

These are async tests (asyncio_mode = "auto"). The `db` fixture (conftest, from
feature 001/002) supplies an initialized throwaway temp-SQLite engine whose
schema — including the `users` table — is built via init_db(). DoD-5 deliberately
bypasses that fixture: it calls init_engine() *without* init_db() (which "does
not create tables", per context) so the `users` table is absent.
"""

from pathlib import Path

from app.db import users
from app.db.engine import DbConfig, init_engine
from app.models.user import User, UserRole


# DoD-3: users.create followed by users.get_by_username round-trips the stored
# user — same username and role — and create returns it with its generated id.
async def test_create_then_get_by_username_round_trips__DoD3(db: DbConfig):
    created = await users.create(User(username="alice", role=UserRole.author))

    # create() populates the autoincrement primary key on the returned user.
    assert created.id is not None

    fetched = await users.get_by_username("alice")

    # The user round-trips: same username and same role are read back.
    assert fetched is not None
    assert fetched.username == "alice"
    assert fetched.role == UserRole.author


# fast/001 DoD-4: a User obtained via users.create has a populated snowflake id —
# positive and in the snowflake range far above legacy small autoincrement ints —
# assigned at construction rather than by DB autoincrement. Round-tripping via
# get_by_username reads back the same id. (No autoincrement/sequential assertion.)
async def test_create_populates_snowflake_id__fast001_DoD4(db: DbConfig):
    created = await users.create(User(username="snowuser", role=UserRole.author))

    # The id is populated (app-generated at construction, not DB-assigned)...
    assert created.id is not None

    # ...and sits in the snowflake range: a 2024-epoch, 22-bit-shifted timestamp
    # id is far larger than small autoincrement values. Use the frozen timestamp
    # shift so the lower bound is derived from the spec's bit-layout, not a magic
    # number.
    from app.ids import TIMESTAMP_SHIFT

    assert created.id > (1 << TIMESTAMP_SHIFT)

    # The same id round-trips through the DB.
    fetched = await users.get_by_username("snowuser")
    assert fetched is not None
    assert fetched.id == created.id


# DoD-4: admin_exists() is False when no admin is present and True after an
# admin user is created. Per the spec the discriminator is the `admin` role, so
# a non-admin (author) account must NOT flip it to True.
async def test_admin_exists_reflects_admin_presence__DoD4(db: DbConfig):
    # Fresh schema, no users yet -> no admin.
    assert await users.admin_exists() is False

    # A non-admin (author) user exists, but still no admin.
    await users.create(User(username="scribe", role=UserRole.author))
    assert await users.admin_exists() is False

    # Once an admin-role user exists, admin_exists() reports True.
    await users.create(User(username="root", role=UserRole.admin))
    assert await users.admin_exists() is True


# DoD-5: admin_exists() returns False gracefully (no unhandled error) when the
# `users` table has not been created (cold instance). The engine is initialized
# via init_engine but init_db() is NOT run, so — per context — no tables exist.
async def test_admin_exists_missing_table_returns_false_gracefully__DoD5(
    tmp_path: Path,
):
    # Initialize an engine whose schema was never built: init_engine does not
    # create tables, and init_db() is deliberately skipped, so `users` is absent.
    config = DbConfig(db_path=tmp_path / "cold_instance.db")
    await init_engine(config)

    # Against the missing `users` table, admin_exists must catch the
    # missing-table error and return False rather than propagate it.
    result = await users.admin_exists()

    assert result is False
