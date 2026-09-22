"""Tests for the login + session service (feature 004, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002),
plus the Step-001 helpers this step builds on:

    app.services.rate_limit  (NEW module, module-global in-memory store):
        MAX_FAILURES = 5
        FAILURE_WINDOW = timedelta(minutes=15)
        def is_locked(username: str) -> bool
        def record_failure(username: str) -> None
        def clear(username: str) -> None
        def reset() -> None

    app.services.auth  (AMEND):
        class AuthError(Exception)         # generic typed refusal, no detail
        async def authenticate_user(username: str, password: str) -> User
            (raises AuthError on any refusal: locked / unknown / disabled / bad pw)
        async def refresh_access_token(refresh_token: str) -> str
            (returns a NEW access token; raises AuthError on any refusal)
        # Step-001, treated as given:
        def hash_password(password: str) -> str
        def generate_signing_key() -> str
        def create_refresh_token(user: User) -> str
        async def get_current_user(credentials) -> User

    app.db.users  (AMEND):
        async def update(user: User) -> User
        async def create(user: User) -> User
        async def get_by_id(user_id: int) -> User | None

Expected values come from the spec ONLY — the step DoD, the step Interface
intent, and context.md ("Rate-limiting", "Token model", "Session
invalidation") — never from implementation internals:

    - Rate limit: 5 failures / 15-minute window, per username, in-memory. On the
      5th failure within the window further attempts are refused REGARDLESS of
      credential validity; a successful login clears the counter.
    - Refusals are the SAME generic AuthError — bad password, unknown username,
      disabled user (pwdhash is None) and rate-limited all raise the identical,
      detail-free error (no enumeration).
    - authenticate_user on success: clears the counter, rotates the signing key
      if stale (>~30d by last_key_update) and persists it, sets last_login, and
      returns the User.
    - refresh_access_token: verifies the refresh token (sig + exp + type=="refresh")
      against the user's per-user key, rejects a disabled user, and returns a NEW
      access token that get_current_user accepts as the same user. Refresh payload
      shape (context.md -> Token model): {user_id: str(user.id), type:"refresh",
      exp:+30days}; user_id serialized as a STRING per the snowflake-id convention.

Async tests use asyncio_mode = "auto". DB-backed cases use the `db` fixture
(conftest) — a throwaway temp-SQLite engine with schema built — and persist a
User via db.users.create(...), mirroring tests/db/test_users.py and
tests/services/test_tokens.py. Users carry a real bcrypt pwdhash (via
hash_password) and a jwt_signing_key (via generate_signing_key) so the
verify_password path is exercised truthfully; a DISABLED user has pwdhash=None.
Timestamps are timezone-AWARE UTC, matching the implementation's aware-UTC use.

The rate-limit store is module-global / per-worker, so an autouse fixture calls
rate_limit.reset() before each test to keep cases from bleeding into each other.
"""

import datetime

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app.db import users
from app.db.engine import DbConfig
from app.models.user import User, UserRole
from app.services import auth
from app.services import rate_limit


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    """Wrap a raw token as the Bearer credentials get_current_user accepts."""
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _mint_expired_refresh_token(user: User) -> str:
    """Craft a refresh-shaped JWT whose `exp` is already in the past.

    Signed with the user's own per-user key (HS256), carrying the documented
    refresh payload shape from context.md -> "Token model" (`user_id` as the
    STRING str(user.id), `type:"refresh"`) but with `exp` forced one minute into
    the past. This is the spec-faithful way to exercise the expired-refresh path
    without waiting ~30 days.
    """
    payload = {
        "user_id": str(user.id),
        "type": "refresh",
        "exp": _now() - datetime.timedelta(minutes=1),
    }
    return jwt.encode(payload, user.jwt_signing_key, algorithm="HS256")


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> None:
    """Reset the module-global rate-limit store before each test.

    The failure store lives at module scope in `services/rate_limit.py`, so a
    counter left by one test would otherwise leak into the next within the same
    process. Restoring the empty default before each test keeps cases isolated.
    """
    rate_limit.reset()


# DoD-1 (US-003.AC-1): authenticate_user with a valid username/password returns
# the matching User and CLEARS that username's failure counter. The clearing is
# proven non-tautologically: 4 pre-existing failures (below the threshold of 5)
# would combine with 4 later failures to lock the username IF the successful
# login had not cleared them; because it did, 4 later failures alone stay below
# the threshold.
async def test_valid_login_returns_user_and_clears_counter__DoD1_US003_AC1(
    db: DbConfig,
):
    user = await users.create(
        User(
            username="alice",
            role=UserRole.admin,
            pwdhash=auth.hash_password("secret"),
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )

    # Some failures accrue, but stay below the lockout threshold.
    for _ in range(rate_limit.MAX_FAILURES - 1):
        rate_limit.record_failure("alice")
    assert rate_limit.is_locked("alice") is False

    result = await auth.authenticate_user("alice", "secret")

    # The matching user is returned.
    assert result.id == user.id
    assert result.username == user.username

    # The counter was cleared by the successful login: another (MAX_FAILURES - 1)
    # failures on their own stay below the threshold. Had the earlier failures
    # NOT been cleared, the total would have reached MAX_FAILURES and locked.
    for _ in range(rate_limit.MAX_FAILURES - 1):
        rate_limit.record_failure("alice")
    assert rate_limit.is_locked("alice") is False


# DoD-2 (US-003.AC-2): a wrong password raises AuthError AND records a failure.
# The recording is proven: one wrong-password attempt plus (MAX_FAILURES - 1)
# further failures reaches the threshold and locks the username — which only
# happens if the wrong-password attempt itself recorded exactly one failure.
async def test_wrong_password_raises_and_records_failure__DoD2_US003_AC2(
    db: DbConfig,
):
    await users.create(
        User(
            username="alice",
            role=UserRole.admin,
            pwdhash=auth.hash_password("secret"),
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )

    with pytest.raises(auth.AuthError):
        await auth.authenticate_user("alice", "wrong-password")

    # One failure was recorded by the attempt above; top up to the threshold.
    for _ in range(rate_limit.MAX_FAILURES - 1):
        rate_limit.record_failure("alice")
    assert rate_limit.is_locked("alice") is True


# DoD-2 (US-003.AC-2): an unknown username, a disabled user (pwdhash is None),
# and a wrong password all raise the SAME generic AuthError — same exception
# type, no distinguishing detail (no user enumeration).
async def test_unknown_disabled_and_bad_pw_raise_same_generic_error__DoD2_US003_AC2(
    db: DbConfig,
):
    # An enabled user (for the wrong-password branch)...
    await users.create(
        User(
            username="alice",
            role=UserRole.admin,
            pwdhash=auth.hash_password("secret"),
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )
    # ...and a disabled user (pwdhash is None == account disabled).
    await users.create(
        User(
            username="dave",
            role=UserRole.author,
            pwdhash=None,
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )

    with pytest.raises(auth.AuthError) as unknown_exc:
        await auth.authenticate_user("ghost", "whatever")
    with pytest.raises(auth.AuthError) as disabled_exc:
        await auth.authenticate_user("dave", "whatever")
    with pytest.raises(auth.AuthError) as badpw_exc:
        await auth.authenticate_user("alice", "wrong-password")

    # Identical exception type across all three refusal reasons.
    assert type(unknown_exc.value) is auth.AuthError
    assert type(disabled_exc.value) is auth.AuthError
    assert type(badpw_exc.value) is auth.AuthError

    # No distinguishing detail: the message does not vary by reason (no leak).
    assert str(unknown_exc.value) == str(disabled_exc.value)
    assert str(disabled_exc.value) == str(badpw_exc.value)


# DoD-3 (US-003.AC-3): after MAX_FAILURES failed attempts within the window, the
# next authenticate_user is refused with AuthError EVEN WITH valid credentials;
# after rate_limit.clear a valid login succeeds again and resets the counter.
async def test_lockout_refuses_even_valid_credentials_then_clears__DoD3_US003_AC3(
    db: DbConfig,
):
    user = await users.create(
        User(
            username="alice",
            role=UserRole.admin,
            pwdhash=auth.hash_password("secret"),
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )

    # Drive the lockout through authenticate_user with wrong passwords.
    for _ in range(rate_limit.MAX_FAILURES):
        with pytest.raises(auth.AuthError):
            await auth.authenticate_user("alice", "wrong-password")
    assert rate_limit.is_locked("alice") is True

    # Rate-limited regardless of credential validity: valid creds are still refused.
    with pytest.raises(auth.AuthError):
        await auth.authenticate_user("alice", "secret")

    # Once cleared, a valid login succeeds again...
    rate_limit.clear("alice")
    result = await auth.authenticate_user("alice", "secret")
    assert result.id == user.id

    # ...and the counter is reset (successful login clears it).
    assert rate_limit.is_locked("alice") is False


# DoD-4 (US-003.AC-1, UC-003 alt): a successful login whose signing key is stale
# (older than the ~30-day rotation window) rotates the key and PERSISTS it — a
# re-fetch shows the changed key — and sets last_login.
async def test_successful_login_rotates_stale_key_and_persists__DoD4_US003_AC1(
    db: DbConfig,
):
    old_key = auth.generate_signing_key()
    stale = _now() - datetime.timedelta(days=40)
    user = await users.create(
        User(
            username="carol",
            role=UserRole.author,
            pwdhash=auth.hash_password("secret"),
            jwt_signing_key=old_key,
            last_key_update=stale,
            last_login=None,
        )
    )

    await auth.authenticate_user("carol", "secret")

    refetched = await users.get_by_id(user.id)
    assert refetched is not None
    # Stale key was rotated and the new key material was persisted.
    assert refetched.jwt_signing_key != old_key
    # last_login was set on the successful login.
    assert refetched.last_login is not None


# DoD-4 (US-003.AC-1): the rotation window is respected — a fresh-key user
# (last_key_update = now) is NOT rotated on login, so the persisted key is
# unchanged afterward (rotation is not a tautology).
async def test_successful_login_does_not_rotate_fresh_key__DoD4_US003_AC1(
    db: DbConfig,
):
    key = auth.generate_signing_key()
    user = await users.create(
        User(
            username="carol-fresh",
            role=UserRole.author,
            pwdhash=auth.hash_password("secret"),
            jwt_signing_key=key,
            last_key_update=_now(),
        )
    )

    await auth.authenticate_user("carol-fresh", "secret")

    refetched = await users.get_by_id(user.id)
    assert refetched is not None
    # Fresh key: no rotation, so the stored key is unchanged.
    assert refetched.jwt_signing_key == key


# DoD-5 (US-003.AC-1): refresh_access_token with a valid refresh token returns a
# NEW access token that get_current_user accepts as the same user (session
# renewed). The user's key is fresh, so the refresh does not rotate it and the
# returned access token verifies against the still-current stored key.
async def test_refresh_returns_new_access_token_accepted_as_same_user__DoD5_US003_AC1(
    db: DbConfig,
):
    user = await users.create(
        User(
            username="alice",
            role=UserRole.admin,
            pwdhash=auth.hash_password("secret"),
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )

    refresh = auth.create_refresh_token(user)

    new_access = await auth.refresh_access_token(refresh)

    # A fresh access token string is returned, distinct from the refresh token.
    assert isinstance(new_access, str)
    assert new_access != refresh

    # It authenticates through the access-token dependency as the same user.
    authed = await auth.get_current_user(_bearer(new_access))
    assert authed.id == user.id
    assert authed.username == user.username


# DoD-6 (US-004.AC-2): refresh_access_token with an EXPIRED refresh token raises
# AuthError — an expired session cannot be renewed.
async def test_refresh_with_expired_refresh_token_raises__DoD6_US004_AC2(
    db: DbConfig,
):
    user = await users.create(
        User(
            username="alice",
            role=UserRole.admin,
            pwdhash=auth.hash_password("secret"),
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )

    expired_refresh = _mint_expired_refresh_token(user)

    with pytest.raises(auth.AuthError):
        await auth.refresh_access_token(expired_refresh)


# DoD-7 (US-004.AC-1): refresh_access_token for a DISABLED user (pwdhash is None)
# raises AuthError — access ends when the account is disabled, even with a
# validly-signed, unexpired refresh token.
async def test_refresh_for_disabled_user_raises__DoD7_US004_AC1(
    db: DbConfig,
):
    user = await users.create(
        User(
            username="dave",
            role=UserRole.author,
            pwdhash=None,  # null == account disabled
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )

    # A well-formed, validly-signed, unexpired refresh token for the user.
    refresh = auth.create_refresh_token(user)

    with pytest.raises(auth.AuthError):
        await auth.refresh_access_token(refresh)
