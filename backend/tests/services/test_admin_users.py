"""Tests for the admin user service (feature 005, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):

    app.models.schemas.admin  (NEW):
        class AdminUserResponse   {id: str, username: str, role: UserRole,
                                   last_login: datetime | None, active: bool}
                                  # id serialized as str(user.id); NO secret fields
        class AdminCreateUserRequest {username, password, password_confirm, role}
        class AdminSetPasswordRequest {password, password_confirm}
        class AdminSetRoleRequest    {role}

    app.services.admin  (NEW):
        class AdminErrorReason(str, enum.Enum)
            username_taken="username-taken", not_found="not-found",
            self_target="self-target", already_disabled="already-disabled",
            password_invalid="password-invalid"
        class AdminError(Exception)  __init__(reason, message="")  -> .reason
        async def list_users() -> list[AdminUserResponse]
        async def create_user(req: AdminCreateUserRequest) -> AdminUserResponse
        async def set_user_password(user_id: int, req: AdminSetPasswordRequest)
                                                            -> AdminUserResponse
        async def set_user_role(caller: User, user_id: int,
                                req: AdminSetRoleRequest) -> AdminUserResponse
        async def disable_user(caller: User, user_id: int) -> AdminUserResponse

    app.services.auth  (given):
        def hash_password(password: str) -> str
        def verify_password(password: str, pwdhash: str) -> bool
        def generate_signing_key() -> str

    app.db.users  (get_all NEW; create/get_by_id given):
        async def get_all() -> list[User]        # ordered by username
        async def create(user: User) -> User
        async def get_by_id(user_id: int) -> User | None

Expected values come from the spec ONLY — the step DoD (DoD-1..DoD-14, minus
DoD-13 which lives in test_require_role.py), the step Interface intent, and
context.md cross-cutting decisions 2-9 — never from implementation internals.

Key spec facts asserted here:
    - active = (pwdhash is not None), derived in the response mapper (decision 3).
    - AdminUserResponse.id is a STRING == str(user.id) (snowflake convention);
      it exposes `active` and NO secret fields (pwdhash/jwt_signing_key/salt).
    - create/reset validate min-length-8 + confirm-match; a violation surfaces as
      AdminError(reason=password_invalid) — NOT the internal PasswordPolicyError.
    - self-guards compare caller.id == user_id -> AdminError(self_target).
    - disable nulls pwdhash + jwt_signing_key, preserving id/username/role/
      last_login (decision 5); already-disabled -> AdminError(already_disabled).

DB-backed cases use the `db` fixture (conftest) — a throwaway temp-SQLite engine
with schema built — and persist users via db.users.create(...), mirroring
tests/db/test_users.py and tests/services/test_login_auth.py. Enabled users carry
a real bcrypt pwdhash (via hash_password) + a jwt_signing_key; a DISABLED user
has pwdhash=None. Timestamps are timezone-aware UTC. Async tests use
asyncio_mode = "auto".
"""

import datetime

import pytest

from app.db import users
from app.db.engine import DbConfig
from app.models.schemas.admin import (
    AdminCreateUserRequest,
    AdminSetPasswordRequest,
    AdminSetRoleRequest,
    AdminUserResponse,
)
from app.models.user import User, UserRole
from app.services import admin as admin_service
from app.services import auth


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def _persist_user(
    username: str,
    role: UserRole = UserRole.author,
    *,
    enabled: bool = True,
    password: str = "initialpass",
    last_login: datetime.datetime | None = None,
) -> User:
    """Persist a User in the isolated test DB and return it.

    Enabled accounts carry a real bcrypt pwdhash + a signing key; a disabled
    account (per the brief) has pwdhash=None. `role`, `username`, and
    `last_login` are set truthfully so attribution/order assertions are honest.
    """
    return await users.create(
        User(
            username=username,
            role=role,
            pwdhash=auth.hash_password(password) if enabled else None,
            jwt_signing_key=auth.generate_signing_key() if enabled else None,
            last_key_update=_now() if enabled else None,
            last_login=last_login,
        )
    )


# DoD-1 (US-006.AC-1): create_user with an untaken username, a valid password,
# and role `author` creates the account with that role; the returned
# AdminUserResponse shows that role and active True. id is the snowflake as a
# STRING (str(created.id)).
async def test_create_user_author_creates_account__DoD1_US006_AC1(db: DbConfig):
    req = AdminCreateUserRequest(
        username="newauthor",
        password="password123",
        password_confirm="password123",
        role=UserRole.author,
    )

    resp = await admin_service.create_user(req)

    assert resp.username == "newauthor"
    assert resp.role == UserRole.author
    assert resp.active is True

    # id is a snowflake serialized as a string == str(created.id).
    assert isinstance(resp.id, str)
    created = await users.get_by_id(int(resp.id))
    assert created is not None
    assert created.role == UserRole.author
    assert resp.id == str(created.id)


# DoD-1 (US-006.AC-1): the same flow with role `admin` creates an admin account;
# the response shows role admin and active True.
async def test_create_user_admin_creates_account__DoD1_US006_AC1(db: DbConfig):
    req = AdminCreateUserRequest(
        username="newadmin",
        password="password123",
        password_confirm="password123",
        role=UserRole.admin,
    )

    resp = await admin_service.create_user(req)

    assert resp.role == UserRole.admin
    assert resp.active is True

    created = await users.get_by_id(int(resp.id))
    assert created is not None
    assert created.role == UserRole.admin


# DoD-2 (US-006.AC-2): create_user with an already-taken username is refused with
# AdminError(reason=username_taken); no new account is created.
async def test_create_user_taken_username_refused__DoD2_US006_AC2(db: DbConfig):
    await _persist_user("dup", role=UserRole.author)
    before = await users.get_all()

    req = AdminCreateUserRequest(
        username="dup",
        password="password123",
        password_confirm="password123",
        role=UserRole.author,
    )

    with pytest.raises(admin_service.AdminError) as exc:
        await admin_service.create_user(req)
    assert exc.value.reason == admin_service.AdminErrorReason.username_taken

    # No account was created — the row count is unchanged.
    after = await users.get_all()
    assert len(after) == len(before)


# DoD-3 (US-007.AC-1): after set_user_password, the stored credential verifies
# against the NEW password and not the old one.
async def test_set_user_password_rehashes_new_credential__DoD3_US007_AC1(
    db: DbConfig,
):
    user = await _persist_user("resettarget", password="oldpassword")

    req = AdminSetPasswordRequest(password="newpassword", password_confirm="newpassword")
    await admin_service.set_user_password(user.id, req)

    updated = await users.get_by_id(user.id)
    assert updated is not None
    assert updated.pwdhash is not None
    assert auth.verify_password("newpassword", updated.pwdhash) is True
    assert auth.verify_password("oldpassword", updated.pwdhash) is False


# DoD-4 (US-007.AC-2): set_user_password on a disabled account (pwdhash is None)
# re-enables it — the returned response shows active True and the credential
# verifies against the new password.
async def test_set_user_password_reenables_disabled__DoD4_US007_AC2(db: DbConfig):
    user = await _persist_user("dormant", enabled=False)
    assert user.pwdhash is None  # precondition: disabled

    req = AdminSetPasswordRequest(password="freshpassword", password_confirm="freshpassword")
    resp = await admin_service.set_user_password(user.id, req)

    # The response reports the account re-enabled.
    assert resp.active is True

    updated = await users.get_by_id(user.id)
    assert updated is not None
    assert updated.pwdhash is not None
    assert auth.verify_password("freshpassword", updated.pwdhash) is True


# DoD-5 (US-008.AC-1): set_user_role on a non-self target updates the role; the
# returned and refetched account both show the new role.
async def test_set_user_role_updates_non_self_target__DoD5_US008_AC1(db: DbConfig):
    caller = await _persist_user("admin_caller", role=UserRole.admin)
    target = await _persist_user("promote_me", role=UserRole.author)

    req = AdminSetRoleRequest(role=UserRole.admin)
    resp = await admin_service.set_user_role(caller, target.id, req)

    assert resp.role == UserRole.admin

    refetched = await users.get_by_id(target.id)
    assert refetched is not None
    assert refetched.role == UserRole.admin


# DoD-6 (US-008.AC-2): set_user_role where the caller IS the target is refused
# with AdminError(reason=self_target).
async def test_set_user_role_self_target_refused__DoD6_US008_AC2(db: DbConfig):
    caller = await _persist_user("self_admin", role=UserRole.admin)

    req = AdminSetRoleRequest(role=UserRole.author)
    with pytest.raises(admin_service.AdminError) as exc:
        await admin_service.set_user_role(caller, caller.id, req)
    assert exc.value.reason == admin_service.AdminErrorReason.self_target


# DoD-7 (US-009.AC-1): disable_user on a non-self target nulls both pwdhash and
# jwt_signing_key; the returned response shows active False.
async def test_disable_user_nulls_credentials__DoD7_US009_AC1(db: DbConfig):
    caller = await _persist_user("admin_caller", role=UserRole.admin)
    target = await _persist_user("victim", role=UserRole.author)

    resp = await admin_service.disable_user(caller, target.id)

    assert resp.active is False

    refetched = await users.get_by_id(target.id)
    assert refetched is not None
    assert refetched.pwdhash is None
    assert refetched.jwt_signing_key is None


# DoD-8 (US-009.AC-2): after disable, the account row's id, username, role, and
# last_login are unchanged (data + attribution intact). Compared against the
# pre-disable DB snapshot so the check is round-trip-faithful.
async def test_disable_user_preserves_identity_fields__DoD8_US009_AC2(db: DbConfig):
    caller = await _persist_user("admin_caller", role=UserRole.admin)
    target = await _persist_user(
        "attributed", role=UserRole.author, last_login=_now()
    )
    before = await users.get_by_id(target.id)
    assert before is not None

    await admin_service.disable_user(caller, target.id)

    after = await users.get_by_id(target.id)
    assert after is not None
    assert after.id == before.id
    assert after.username == before.username
    assert after.role == before.role
    assert after.last_login == before.last_login


# DoD-9 (US-009.AC-3): disable_user where the caller IS the target is refused
# with AdminError(reason=self_target).
async def test_disable_user_self_target_refused__DoD9_US009_AC3(db: DbConfig):
    caller = await _persist_user("self_admin", role=UserRole.admin)

    with pytest.raises(admin_service.AdminError) as exc:
        await admin_service.disable_user(caller, caller.id)
    assert exc.value.reason == admin_service.AdminErrorReason.self_target


# DoD-10 (decision 5): disable_user on an already-disabled account (pwdhash is
# None) is refused with AdminError(reason=already_disabled). Uses a distinct
# caller so the self-guard is passed and the already-disabled check is reached.
async def test_disable_user_already_disabled_refused__DoD10(db: DbConfig):
    caller = await _persist_user("admin_caller", role=UserRole.admin)
    target = await _persist_user("already_off", role=UserRole.author, enabled=False)

    with pytest.raises(admin_service.AdminError) as exc:
        await admin_service.disable_user(caller, target.id)
    assert exc.value.reason == admin_service.AdminErrorReason.already_disabled


# DoD-11 (US-005.AC-1): list_users returns one entry per account, each carrying
# its role and last_login, ordered by username.
async def test_list_users_one_per_account_ordered_by_username__DoD11_US005_AC1(
    db: DbConfig,
):
    login_time = _now()
    # Persisted out of alphabetical order to prove ordering is applied.
    await _persist_user("charlie", role=UserRole.author, last_login=login_time)
    await _persist_user("alice", role=UserRole.admin, last_login=None)
    await _persist_user("bob", role=UserRole.author, last_login=login_time)

    result = await admin_service.list_users()

    # One entry per account, ordered by username.
    assert [r.username for r in result] == ["alice", "bob", "charlie"]

    # Each entry carries role and last_login attributes matching the account.
    by_name = {r.username: r for r in result}
    assert by_name["alice"].role == UserRole.admin
    assert by_name["alice"].last_login is None
    assert by_name["charlie"].role == UserRole.author
    assert by_name["charlie"].last_login is not None


# DoD-12 (US-005.AC-2): an AdminUserResponse exposes NO secret fields
# (no pwdhash / jwt_signing_key / salt) and DOES expose `active`. Also confirms
# id is the snowflake serialized as a STRING == str(user.id).
async def test_admin_response_excludes_secrets_exposes_active__DoD12_US005_AC2(
    db: DbConfig,
):
    user = await _persist_user("visible", role=UserRole.author)

    result = await admin_service.list_users()
    assert len(result) == 1
    resp = result[0]

    # Field surface — via the model schema and a dumped instance.
    field_names = set(AdminUserResponse.model_fields.keys())
    dumped_keys = set(resp.model_dump().keys())
    for keys in (field_names, dumped_keys):
        assert "pwdhash" not in keys
        assert "jwt_signing_key" not in keys
        assert "salt" not in keys
        assert "active" in keys

    # id is a string == str(user.id) (snowflake convention).
    assert isinstance(resp.id, str)
    assert resp.id == str(user.id)


# DoD-14 (decision 4): create_user refuses a password shorter than 8 characters
# OR one whose confirm does not match, raising AdminError(reason=password_invalid)
# — NOT the internal PasswordPolicyError.
async def test_create_user_rejects_bad_password__DoD14(db: DbConfig):
    # Too short (< 8 characters).
    short_req = AdminCreateUserRequest(
        username="shortpw",
        password="short",
        password_confirm="short",
        role=UserRole.author,
    )
    with pytest.raises(admin_service.AdminError) as short_exc:
        await admin_service.create_user(short_req)
    assert short_exc.value.reason == admin_service.AdminErrorReason.password_invalid

    # Confirm does not match.
    mismatch_req = AdminCreateUserRequest(
        username="mismatchpw",
        password="password123",
        password_confirm="different123",
        role=UserRole.author,
    )
    with pytest.raises(admin_service.AdminError) as mismatch_exc:
        await admin_service.create_user(mismatch_req)
    assert mismatch_exc.value.reason == admin_service.AdminErrorReason.password_invalid


# DoD-14 (decision 4): set_user_password refuses a password shorter than 8
# characters OR a mismatched confirm, raising AdminError(reason=password_invalid).
async def test_set_user_password_rejects_bad_password__DoD14(db: DbConfig):
    user = await _persist_user("pwpolicy", password="originalpass")

    short_req = AdminSetPasswordRequest(password="short", password_confirm="short")
    with pytest.raises(admin_service.AdminError) as short_exc:
        await admin_service.set_user_password(user.id, short_req)
    assert short_exc.value.reason == admin_service.AdminErrorReason.password_invalid

    mismatch_req = AdminSetPasswordRequest(
        password="password123", password_confirm="different123"
    )
    with pytest.raises(admin_service.AdminError) as mismatch_exc:
        await admin_service.set_user_password(user.id, mismatch_req)
    assert mismatch_exc.value.reason == admin_service.AdminErrorReason.password_invalid
