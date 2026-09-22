"""End-to-end tests for the auth HTTP surface (feature 004, step 003).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). A freshly-booted
instance is *unconfigured* until a setup flow runs or a user is seeded; the
autouse `_reset_db_ready` fixture (conftest) restores the cold-boot readiness
default before each test.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 003):

    app.models.schemas.auth:
        class LoginRequest(BaseModel):   username: str; password: str
        class RefreshRequest(BaseModel): refresh_token: str
        class TokenResponse(BaseModel):  access_token: str; refresh_token: str
        class MeResponse(BaseModel):     id: str; username: str; role: UserRole
            # `id` is a STRING on the wire (snowflake convention) — str(user.id)

    routes/auth.py  (router prefix "/api/auth"):
        POST /api/auth/login          (body LoginRequest)   -> TokenResponse
        POST /api/auth/refresh        (body RefreshRequest) -> TokenResponse
        GET  /api/auth/me             (Depends get_current_user) -> MeResponse
        POST /api/auth/setup/create   (body CreateDBRequest) -> TokenResponse

And (steps 001/002, treated as given):
    app.services.auth.create_access_token(user) / create_refresh_token(user)
    app.services.auth.hash_password / generate_signing_key
    app.services.rate_limit.MAX_FAILURES / reset()
    app.db.users.create / app.db.engine.init_db / set_db_ready

Expected values come from the spec ONLY — the step DoD + Interface intent +
003.context.md + feature context ("Token model", "Rate-limiting", "Session
invalidation", "Layering discipline") — never from implementation internals:

    - DoD-1 (US-003.AC-1): POST /login with valid creds -> 200 + TokenResponse
      carrying non-empty access_token AND refresh_token.
    - DoD-2 (US-003.AC-2): POST /login with invalid creds -> 401, no tokens.
    - DoD-3 (US-003.AC-3): after the rate-limit threshold (5 failures) is
      exceeded, POST /login is refused 401 EVEN with valid creds, with the SAME
      generic message as bad creds (no enumeration leak).
    - DoD-4 (US-003.AC-1): GET /me with a valid access token -> 200 + MeResponse
      whose `id` is the STRING form of the snowflake id (JSON string, not number),
      plus username and role.
    - DoD-5 (US-004.AC-2): GET /me with an EXPIRED access token -> 401.
    - DoD-6 (US-004.AC-1): GET /me with NO Authorization header -> 401.
    - DoD-7 (US-003.AC-1): POST /refresh with a valid refresh token -> 200 +
      TokenResponse with a fresh access_token (the incoming refresh_token echoed).
    - DoD-8 (US-004.AC-1): POST /refresh for a DISABLED user (pwdhash is None) ->
      401.

Async tests use asyncio_mode = "auto". Login-route cases reach a configured
instance with a known admin via the real `POST /setup/create` flow, then log in.
The /me and /refresh cases need the persisted `User` object (to mint tokens with
`create_access_token` / `create_refresh_token`), so they seed one via
`db.users.create` on the same process-global engine the app uses (schema built
with `init_db`, readiness flipped with `set_db_ready(True)` to represent a
configured instance) — the pattern used by tests/routes/test_setup.py's import
case. The expired-access case crafts a PyJWT token whose `exp` is in the past,
as tests/services/test_tokens.py does. The rate-limit store is module-global, so
an autouse fixture resets it before each test.
"""

import datetime

import jwt
import pytest

from app.db import users
from app.db.engine import init_db, set_db_ready
from app.models.schemas.auth import MeResponse, TokenResponse
from app.models.user import User, UserRole
from app.services import auth, rate_limit

LOGIN_URL = "/api/auth/login"
REFRESH_URL = "/api/auth/refresh"
ME_URL = "/api/auth/me"
CREATE_URL = "/api/auth/setup/create"

ADMIN_USER = "root"
ADMIN_PW = "password123"  # >= 8 chars, satisfies the create-DB minimum


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> None:
    """Reset the module-global rate-limit store before each test.

    The per-username failure store lives at module scope in
    `services/rate_limit.py`, so a counter left by one test would otherwise leak
    into the next within the same process.
    """
    rate_limit.reset()


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _configure_admin(http_client, username=ADMIN_USER, password=ADMIN_PW):
    """Configure the instance with a known admin via the real setup/create flow."""
    resp = await http_client.post(
        CREATE_URL,
        json={
            "admin_username": username,
            "password": password,
            "password_confirm": password,
        },
    )
    assert resp.status_code == 200
    return resp


async def _seed_user(
    *,
    username: str,
    password: str | None,
    role: UserRole = UserRole.admin,
) -> User:
    """Seed a persisted user on the app's engine and mark the instance configured.

    Builds the schema (`init_db`), creates the user with a real bcrypt pwdhash
    (via `hash_password`, or None for a DISABLED account) and a per-user signing
    key (via `generate_signing_key`), then flips readiness True so the instance
    looks configured. Returns the created `User` (carrying its snowflake id and
    signing key) so the caller can mint spec-shaped tokens for it.
    """
    await init_db()
    user = await users.create(
        User(
            username=username,
            role=role,
            pwdhash=auth.hash_password(password) if password is not None else None,
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )
    set_db_ready(True)
    return user


def _mint_expired_access_token(user: User) -> str:
    """Craft an access-shaped JWT whose `exp` is already in the past.

    Signed with the user's own per-user key (HS256), carrying the documented
    access payload shape from context.md -> "Token model" (`user_id` as the
    STRING str(user.id), `type:"access"`) but with `exp` forced one minute into
    the past — the spec-faithful way to exercise the expired path without waiting.
    """
    payload = {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "type": "access",
        "exp": _now() - datetime.timedelta(minutes=1),
    }
    return jwt.encode(payload, user.jwt_signing_key, algorithm="HS256")


# DoD-1 (US-003.AC-1): POST /api/auth/login with valid credentials -> HTTP 200
# and a TokenResponse carrying a non-empty access_token AND refresh_token.
async def test_login_valid_credentials_returns_token_pair__DoD1_US003_AC1(http_client):
    await _configure_admin(http_client)

    resp = await http_client.post(
        LOGIN_URL, json={"username": ADMIN_USER, "password": ADMIN_PW}
    )

    assert resp.status_code == 200
    body = resp.json()
    model = TokenResponse.model_validate(body)  # conforms to the token-pair schema
    assert isinstance(model.access_token, str) and model.access_token != ""
    assert isinstance(model.refresh_token, str) and model.refresh_token != ""


# DoD-2 (US-003.AC-2): POST /api/auth/login with invalid credentials -> HTTP 401
# and no tokens in the body.
async def test_login_invalid_credentials_401_no_tokens__DoD2_US003_AC2(http_client):
    await _configure_admin(http_client)

    resp = await http_client.post(
        LOGIN_URL, json={"username": ADMIN_USER, "password": "wrong-password"}
    )

    assert resp.status_code == 401
    body = resp.json()
    assert "access_token" not in body
    assert "refresh_token" not in body


# DoD-3 (US-003.AC-3): after the rate-limit threshold (5 failures) is exceeded,
# POST /api/auth/login is refused 401 EVEN with valid credentials, and with the
# SAME generic message as a bad-credential refusal (no user enumeration / no
# lockout-specific message).
async def test_login_lockout_refuses_valid_creds_same_message__DoD3_US003_AC3(
    http_client,
):
    await _configure_admin(http_client)

    # First wrong attempt is a plain bad-cred refusal (counter below threshold);
    # capture its generic message as the comparison baseline.
    first = await http_client.post(
        LOGIN_URL, json={"username": ADMIN_USER, "password": "wrong-password"}
    )
    assert first.status_code == 401
    bad_cred_detail = first.json().get("detail")

    # Drive the remaining failures up to the lockout threshold.
    for _ in range(rate_limit.MAX_FAILURES - 1):
        r = await http_client.post(
            LOGIN_URL, json={"username": ADMIN_USER, "password": "wrong-password"}
        )
        assert r.status_code == 401

    # Now locked: even VALID credentials are refused 401...
    locked = await http_client.post(
        LOGIN_URL, json={"username": ADMIN_USER, "password": ADMIN_PW}
    )
    assert locked.status_code == 401

    # ...with the SAME generic message as the bad-cred refusal (no leak).
    assert locked.json().get("detail") == bad_cred_detail


# DoD-4 (US-003.AC-1): GET /api/auth/me with a valid access token -> HTTP 200 and
# a MeResponse carrying the caller's id (as a JSON STRING, the snowflake form),
# username, and role.
async def test_me_valid_access_token_returns_string_id__DoD4_US003_AC1(http_client):
    user = await _seed_user(username="alice", password="secret123", role=UserRole.admin)

    token = auth.create_access_token(user)
    resp = await http_client.get(ME_URL, headers=_auth_header(token))

    assert resp.status_code == 200
    body = resp.json()
    MeResponse.model_validate(body)  # conforms to the MeResponse schema

    # The wire id is the STRING form of the snowflake id — a JSON string, never a
    # number (a numeric id above 2^53 would lose precision on the frontend).
    assert isinstance(body["id"], str)
    assert body["id"] == str(user.id)
    assert body["username"] == user.username
    assert body["role"] == user.role.value


# DoD-5 (US-004.AC-2): GET /api/auth/me with an EXPIRED access token -> HTTP 401
# (re-authentication required).
async def test_me_expired_access_token_401__DoD5_US004_AC2(http_client):
    user = await _seed_user(username="ed", password="secret123", role=UserRole.author)

    expired = _mint_expired_access_token(user)
    resp = await http_client.get(ME_URL, headers=_auth_header(expired))

    assert resp.status_code == 401


# DoD-6 (US-004.AC-1): GET /api/auth/me with NO Authorization header -> HTTP 401
# (a logged-out client's requests require re-auth). The instance is configured so
# the ONLY reason for refusal is the missing token.
async def test_me_missing_authorization_header_401__DoD6_US004_AC1(http_client):
    await _seed_user(username="someone", password="secret123")

    resp = await http_client.get(ME_URL)

    assert resp.status_code == 401


# DoD-7 (US-003.AC-1): POST /api/auth/refresh with a valid refresh token -> HTTP
# 200 and a TokenResponse with a fresh access_token (session renewed); the
# incoming refresh_token is echoed back per the Token model.
async def test_refresh_valid_token_returns_fresh_access__DoD7_US003_AC1(http_client):
    user = await _seed_user(username="alice", password="secret123", role=UserRole.admin)

    refresh = auth.create_refresh_token(user)
    resp = await http_client.post(REFRESH_URL, json={"refresh_token": refresh})

    assert resp.status_code == 200
    body = resp.json()
    model = TokenResponse.model_validate(body)
    assert isinstance(model.access_token, str) and model.access_token != ""
    # A fresh access token, distinct from the refresh token that produced it...
    assert model.access_token != refresh
    # ...and the incoming refresh token is echoed back (Token model).
    assert model.refresh_token == refresh


# DoD-8 (US-004.AC-1): POST /api/auth/refresh for a DISABLED user (pwdhash is
# None) -> HTTP 401 — access ends when the account is disabled, even with a
# validly-signed, unexpired refresh token.
async def test_refresh_disabled_user_401__DoD8_US004_AC1(http_client):
    user = await _seed_user(username="dave", password=None, role=UserRole.author)

    refresh = auth.create_refresh_token(user)
    resp = await http_client.post(REFRESH_URL, json={"refresh_token": refresh})

    assert resp.status_code == 401
