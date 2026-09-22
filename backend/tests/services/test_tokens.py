"""Tests for the token core + auth dependency (feature 004, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001) in
`app.services.auth`:
    def create_access_token(user: User) -> str
    def create_refresh_token(user: User) -> str
    def decode_token_unverified(token: str) -> int
    def verify_token_signature(token: str, signing_key: str) -> dict
        (propagates jwt.ExpiredSignatureError vs jwt.InvalidSignatureError/
         jwt.InvalidTokenError; does NOT convert to HTTP)
    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)
    ) -> User        (raises fastapi.HTTPException 401 on any failure)
    def maybe_rotate_signing_key(user: User) -> bool
        (mutates user in memory if key stale >~30d by last_key_update; does NOT
         persist)
And (feature 003, treated as given):
    class User / class UserRole                       in app.models.user
    async def create(user: User) -> User              in app.db.users
    async def get_by_id(user_id: int) -> User | None  in app.db.users

Expected values come from the spec ONLY — the step DoD, the step Interface
intent, and context.md -> "Token model" — never from implementation internals:
    - Access payload: {user_id, username, role, type:"access", exp:+30min};
      refresh payload: {user_id, type:"refresh", exp:+30days}. In BOTH the
      `user_id` claim is serialized as a STRING, `str(user.id)`, per the
      system-wide snowflake-id convention.
    - get_current_user requires type=="access", rejects unknown/disabled users
      and bad/rotated/expired signatures, all as HTTP 401.
    - A stale (>~30d) signing key rotates; rotation invalidates prior tokens.

Async tests use asyncio_mode = "auto". DB-backed tests use the `db` fixture
(conftest) — a throwaway temp-SQLite engine with schema built — and persist a
`User` via `db.users.create(...)`, mirroring tests/db/test_users.py and
tests/services/test_setup.py. get_current_user is exercised by calling the
dependency directly with a crafted `HTTPAuthorizationCredentials`, per the
frozen signature.
"""

import datetime

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.db import users
from app.db.engine import DbConfig
from app.models.user import User, UserRole
from app.services import auth


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    """Wrap a raw token as the Bearer credentials the frozen dependency accepts."""
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _mint_expired_access_token(user: User) -> str:
    """Craft an access-shaped JWT whose `exp` is already in the past.

    Signed with the user's own key (HS256), carrying the documented access
    payload shape from context.md -> "Token model" (`user_id` as a STRING,
    `type:"access"`) but with `exp` forced one minute into the past. This is the
    spec-faithful way to exercise the expired path without waiting ~30 minutes.
    """
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
    payload = {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "type": "access",
        "exp": past,
    }
    return jwt.encode(payload, user.jwt_signing_key, algorithm="HS256")


# DoD-1 (US-003.AC-1): create_access_token(user) produces a JWT that
# verify_token_signature (with the user's own key) decodes to claims carrying
# user_id (the STRING form, str(user.id)), username, role, and type=="access".
def test_access_token_claims_verify_with_user_key__DoD1_US003_AC1():
    signing_key = auth.generate_signing_key()
    user = User(
        id=42,
        username="alice",
        role=UserRole.admin,
        jwt_signing_key=signing_key,
    )

    token = auth.create_access_token(user)

    # Verified against THAT user's own per-user key (per Token model, HS256).
    claims = auth.verify_token_signature(token, user.jwt_signing_key)

    # The user_id claim is the STRING form (snowflake-id convention), not the int.
    assert claims["user_id"] == str(user.id)
    assert claims["username"] == user.username
    assert claims["role"] == user.role.value
    assert claims["type"] == "access"


# DoD-1 (US-003.AC-1): a valid access token authenticates through the dependency
# — get_current_user returns the issued-for User (session usable end to end).
async def test_get_current_user_accepts_valid_access_token__DoD1_US003_AC1(
    db: DbConfig,
):
    signing_key = auth.generate_signing_key()
    user = await users.create(
        User(
            username="alice",
            role=UserRole.admin,
            pwdhash="hash",
            jwt_signing_key=signing_key,
        )
    )

    token = auth.create_access_token(user)

    authed = await auth.get_current_user(_bearer(token))

    assert authed.id == user.id
    assert authed.username == user.username


# DoD-2 (US-004.AC-2): an expired access token is rejected at verification —
# verify_token_signature propagates the native expiry error (frozen contract).
def test_expired_access_token_fails_verification__DoD2_US004_AC2():
    signing_key = auth.generate_signing_key()
    user = User(
        id=99,
        username="ed",
        role=UserRole.author,
        jwt_signing_key=signing_key,
    )

    expired = _mint_expired_access_token(user)

    with pytest.raises(jwt.ExpiredSignatureError):
        auth.verify_token_signature(expired, user.jwt_signing_key)


# DoD-2 (US-004.AC-2): an expired access token yields a 401-class failure through
# get_current_user — never a valid user (expired session -> request refused).
async def test_expired_access_token_rejected_by_get_current_user__DoD2_US004_AC2(
    db: DbConfig,
):
    signing_key = auth.generate_signing_key()
    user = await users.create(
        User(
            username="ed",
            role=UserRole.author,
            pwdhash="hash",
            jwt_signing_key=signing_key,
        )
    )

    expired = _mint_expired_access_token(user)

    with pytest.raises(HTTPException) as exc:
        await auth.get_current_user(_bearer(expired))
    assert exc.value.status_code == 401


# DoD-3 (US-003.AC-1): a refresh token (type=="refresh", from create_refresh_token)
# is NOT accepted by get_current_user — only type=="access" authenticates.
async def test_refresh_token_rejected_by_get_current_user__DoD3_US003_AC1(
    db: DbConfig,
):
    signing_key = auth.generate_signing_key()
    user = await users.create(
        User(
            username="bob",
            role=UserRole.author,
            pwdhash="hash",
            jwt_signing_key=signing_key,
        )
    )

    refresh = auth.create_refresh_token(user)

    # The refresh token is well-formed and validly signed with the user's key;
    # per the Token model its `type` claim is "refresh" (spec), so the sole reason
    # for rejection is the type mismatch, not a bad signature.
    refresh_claims = auth.verify_token_signature(refresh, user.jwt_signing_key)
    assert refresh_claims["type"] == "refresh"

    with pytest.raises(HTTPException) as exc:
        await auth.get_current_user(_bearer(refresh))
    assert exc.value.status_code == 401


# DoD-4 (US-003.AC-1, UC-003 alt flow): a stale (>~30d) signing key rotates, and
# a token minted with the OLD key no longer verifies against the rotated key.
def test_maybe_rotate_rotates_when_stale_and_invalidates_old_token__DoD4_US003_AC1():
    old_key = auth.generate_signing_key()
    stale = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=40)
    user = User(
        id=7,
        username="carol",
        role=UserRole.author,
        jwt_signing_key=old_key,
        last_key_update=stale,
    )

    # Mint under the pre-rotation key.
    old_token = auth.create_access_token(user)

    rotated = auth.maybe_rotate_signing_key(user)

    # Rotation occurred and the key material actually changed.
    assert rotated is True
    assert user.jwt_signing_key != old_key

    # The pre-rotation token's signature no longer verifies against the new key.
    with pytest.raises(jwt.InvalidSignatureError):
        auth.verify_token_signature(old_token, user.jwt_signing_key)


# DoD-4 (US-003.AC-1): the rotation window is respected — a fresh key
# (last_key_update = now) does NOT rotate, so the guard is not a tautology.
def test_maybe_rotate_no_rotation_when_key_fresh__DoD4_US003_AC1():
    key = auth.generate_signing_key()
    fresh = datetime.datetime.now(datetime.timezone.utc)
    user = User(
        id=8,
        username="carol-fresh",
        role=UserRole.author,
        jwt_signing_key=key,
        last_key_update=fresh,
    )

    rotated = auth.maybe_rotate_signing_key(user)

    assert rotated is False
    assert user.jwt_signing_key == key


# DoD-4 (US-003.AC-1, UC-003 alt flow): via the dependency — a token minted with
# a pre-rotation key is refused (401) once the stored user carries a different
# (rotated) key.
async def test_get_current_user_rejects_pre_rotation_key_token__DoD4_US003_AC1(
    db: DbConfig,
):
    # The stored user carries the CURRENT (post-rotation) key.
    current_key = auth.generate_signing_key()
    user = await users.create(
        User(
            username="carol-db",
            role=UserRole.author,
            pwdhash="hash",
            jwt_signing_key=current_key,
        )
    )

    # The client presents a token for the same user id but signed with a DIFFERENT
    # (pre-rotation) key — exactly what a rotation leaves behind.
    old_key = auth.generate_signing_key()
    assert old_key != current_key
    stand_in = User(
        id=user.id,
        username=user.username,
        role=user.role,
        jwt_signing_key=old_key,
    )
    old_token = auth.create_access_token(stand_in)

    with pytest.raises(HTTPException) as exc:
        await auth.get_current_user(_bearer(old_token))
    assert exc.value.status_code == 401


# DoD-5 (US-004.AC-1): a token for a DISABLED user (pwdhash is None) is rejected
# by get_current_user (401) even though its signature and type are valid.
async def test_get_current_user_rejects_disabled_user__DoD5_US004_AC1(
    db: DbConfig,
):
    signing_key = auth.generate_signing_key()
    user = await users.create(
        User(
            username="dave",
            role=UserRole.author,
            pwdhash=None,  # null == account disabled
            jwt_signing_key=signing_key,
        )
    )

    token = auth.create_access_token(user)

    # The signature is valid and the token is an access token, so the ONLY reason
    # for rejection is the disabled account.
    claims = auth.verify_token_signature(token, signing_key)
    assert claims["type"] == "access"

    with pytest.raises(HTTPException) as exc:
        await auth.get_current_user(_bearer(token))
    assert exc.value.status_code == 401
