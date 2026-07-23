"""End-to-end tests for the admin user HTTP surface (feature 005, step 002).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). The app's startup
lifespan runs against a throwaway temp DB; each test seeds its own users on the
same process-global engine the app uses (schema built with `init_db`, readiness
flipped with `set_db_ready(True)` to represent a configured instance) — the
pattern used by tests/routes/test_auth.py's `_seed_user`. The autouse
`_reset_db_ready` fixture (conftest) restores the cold-boot readiness default
before each test.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 002, and the Step 001
schemas it consumes):

    app.models.schemas.admin:
        class AdminUserResponse(BaseModel):
            id: str                      # STRING on the wire (snowflake convention)
            username: str
            role: UserRole
            last_login: datetime | None
            active: bool                 # derived: pwdhash is not None
            # secret-excluding: no pwdhash / jwt_signing_key / salt
        class AdminCreateUserRequest(BaseModel):
            username: str; password: str; password_confirm: str; role: UserRole
        class AdminSetPasswordRequest(BaseModel):
            password: str; password_confirm: str
        class AdminSetRoleRequest(BaseModel): role: UserRole

    routes/admin/users.py  (router prefix "/api/admin/users",
      every endpoint gated by Depends(require_role(UserRole.admin))):
        GET  ""                     -> 200, list[AdminUserResponse]
        POST ""                     (body AdminCreateUserRequest) -> 201, AdminUserResponse
        PUT  /{user_id}/password    (body AdminSetPasswordRequest) -> 204
        PUT  /{user_id}/role        (body AdminSetRoleRequest)     -> 204
        PUT  /{user_id}/disable                                    -> 204
      typed-error -> status map: username-taken -> 409, not-found -> 404,
      self-target -> 400, already-disabled -> 400, password-invalid -> 400;
      non-admin -> 403 (produced by require_role).

And (features 003/004, treated as given):
    app.services.auth.create_access_token(user)
    app.services.auth.hash_password / generate_signing_key
    app.db.users.create / app.db.engine.init_db / set_db_ready

Expected values come from the spec ONLY — the step DoD + Interface intent +
002.context.md + feature context.md (the status taxonomy = decision 2, derived
`active` = decision 3, password policy in the service = decision 4, disable nulls
credentials = decision 5, self-guards = decision 9) — never from implementation
internals.

Async tests use asyncio_mode = "auto".
"""

import datetime

from app.db import users
from app.db.engine import init_db, set_db_ready
from app.models.schemas.admin import AdminUserResponse
from app.models.user import User, UserRole
from app.services import auth

USERS_URL = "/api/admin/users"

# A snowflake id that is never seeded — used to reach the not-found path. Well
# inside the 64-bit range FastAPI parses the {user_id} path param into.
NONEXISTENT_ID = 999999999999999999


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _password_url(user_id: int) -> str:
    return f"{USERS_URL}/{user_id}/password"


def _role_url(user_id: int) -> str:
    return f"{USERS_URL}/{user_id}/role"


def _disable_url(user_id: int) -> str:
    return f"{USERS_URL}/{user_id}/disable"


async def _seed_user(
    *,
    username: str,
    password: str | None,
    role: UserRole = UserRole.admin,
) -> User:
    """Seed a persisted user on the app's engine and mark the instance configured.

    Builds the schema (`init_db`, idempotent), creates the user with a real
    bcrypt pwdhash (via `hash_password`, or None for a DISABLED account — null
    pwdhash == disabled, no separate flag) and a per-user signing key, then flips
    readiness True so the instance looks configured. Returns the created `User`
    (carrying its snowflake id) so the caller can mint an access token for it.
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


async def _seed_admin(http_client, username: str = "root") -> tuple[User, str]:
    """Seed an admin caller and return (user, access token)."""
    admin = await _seed_user(username=username, password="password123", role=UserRole.admin)
    return admin, auth.create_access_token(admin)


# DoD-1 (US-005.AC-3): GET /api/admin/users with an author-role token is refused
# 403 (require_role ladder: author < admin); with an admin-role token it returns
# 200.
async def test_list_author_403_admin_200__DoD1_US005_AC3(http_client):
    admin, admin_token = await _seed_admin(http_client)
    author = await _seed_user(username="scribe", password="password123", role=UserRole.author)

    forbidden = await http_client.get(
        USERS_URL, headers=_auth_header(auth.create_access_token(author))
    )
    assert forbidden.status_code == 403

    allowed = await http_client.get(USERS_URL, headers=_auth_header(admin_token))
    assert allowed.status_code == 200


# DoD-2 (US-005.AC-1): the GET list carries, per account, its role, last_login,
# and active.
async def test_list_items_carry_role_last_login_active__DoD2_US005_AC1(http_client):
    admin, admin_token = await _seed_admin(http_client)

    resp = await http_client.get(USERS_URL, headers=_auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and len(body) >= 1

    for item in body:
        AdminUserResponse.model_validate(item)  # conforms to the response schema
        assert "role" in item
        assert "last_login" in item
        assert "active" in item

    me = next(i for i in body if i["id"] == str(admin.id))
    assert me["role"] == admin.role.value
    assert me["active"] is True


# DoD-3 (US-005.AC-2): no GET list item contains a secret field (no pwdhash,
# jwt_signing_key, or salt), and each item's id is a JSON string (snowflake
# convention).
async def test_list_items_exclude_secrets_and_id_is_string__DoD3_US005_AC2(http_client):
    admin, admin_token = await _seed_admin(http_client)

    resp = await http_client.get(USERS_URL, headers=_auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and len(body) >= 1

    for item in body:
        assert "pwdhash" not in item
        assert "jwt_signing_key" not in item
        assert "salt" not in item
        assert isinstance(item["id"], str)


# DoD-4 (US-006.AC-1): POST /api/admin/users with an untaken username + password +
# role returns 201 and an AdminUserResponse with that role and active true.
async def test_create_user_201_role_active__DoD4_US006_AC1(http_client):
    admin, admin_token = await _seed_admin(http_client)

    resp = await http_client.post(
        USERS_URL,
        headers=_auth_header(admin_token),
        json={
            "username": "newbie",
            "password": "password123",
            "password_confirm": "password123",
            "role": UserRole.author.value,
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    AdminUserResponse.model_validate(body)  # conforms to the response schema
    assert body["username"] == "newbie"
    assert body["role"] == UserRole.author.value
    assert body["active"] is True
    assert isinstance(body["id"], str)


# DoD-5 (US-006.AC-2): POST /api/admin/users with an already-taken username is
# refused 409.
async def test_create_duplicate_username_409__DoD5_US006_AC2(http_client):
    admin, admin_token = await _seed_admin(http_client)
    await _seed_user(username="taken", password="password123", role=UserRole.author)

    resp = await http_client.post(
        USERS_URL,
        headers=_auth_header(admin_token),
        json={
            "username": "taken",
            "password": "password123",
            "password_confirm": "password123",
            "role": UserRole.author.value,
        },
    )

    assert resp.status_code == 409


# DoD-6 (US-007.AC-1 / US-007.AC-2): PUT /api/admin/users/{id}/password returns
# 204; when the target was disabled (pwdhash None), a subsequent GET shows it
# active true again (password reset is the sole re-enable path).
async def test_set_password_204_reenables_disabled__DoD6_US007_AC1_AC2(http_client):
    admin, admin_token = await _seed_admin(http_client)
    # A disabled target: null pwdhash == disabled account.
    target = await _seed_user(username="dormant", password=None, role=UserRole.author)

    resp = await http_client.put(
        _password_url(target.id),
        headers=_auth_header(admin_token),
        json={"password": "newpass123", "password_confirm": "newpass123"},
    )
    assert resp.status_code == 204

    listing = await http_client.get(USERS_URL, headers=_auth_header(admin_token))
    assert listing.status_code == 200
    item = next(i for i in listing.json() if i["id"] == str(target.id))
    assert item["active"] is True


# DoD-7 (US-008.AC-1): PUT /api/admin/users/{id}/role on a non-self target returns
# 204 and a subsequent GET shows the updated role.
async def test_set_role_204_updates_role__DoD7_US008_AC1(http_client):
    admin, admin_token = await _seed_admin(http_client)
    target = await _seed_user(username="promote-me", password="password123", role=UserRole.author)

    resp = await http_client.put(
        _role_url(target.id),
        headers=_auth_header(admin_token),
        json={"role": UserRole.admin.value},
    )
    assert resp.status_code == 204

    listing = await http_client.get(USERS_URL, headers=_auth_header(admin_token))
    assert listing.status_code == 200
    item = next(i for i in listing.json() if i["id"] == str(target.id))
    assert item["role"] == UserRole.admin.value


# DoD-8 (US-008.AC-2): PUT /api/admin/users/{id}/role on the caller's OWN id is
# refused 400 (self-guard, decision 9).
async def test_set_role_self_400__DoD8_US008_AC2(http_client):
    admin, admin_token = await _seed_admin(http_client)

    resp = await http_client.put(
        _role_url(admin.id),
        headers=_auth_header(admin_token),
        json={"role": UserRole.author.value},
    )
    assert resp.status_code == 400


# DoD-9 (US-009.AC-1): PUT /api/admin/users/{id}/disable on a non-self target
# returns 204 and a subsequent GET shows the target active false.
async def test_disable_204_target_inactive__DoD9_US009_AC1(http_client):
    admin, admin_token = await _seed_admin(http_client)
    target = await _seed_user(username="victim", password="password123", role=UserRole.author)

    resp = await http_client.put(
        _disable_url(target.id), headers=_auth_header(admin_token)
    )
    assert resp.status_code == 204

    listing = await http_client.get(USERS_URL, headers=_auth_header(admin_token))
    assert listing.status_code == 200
    item = next(i for i in listing.json() if i["id"] == str(target.id))
    assert item["active"] is False


# DoD-10 (US-009.AC-3): PUT /api/admin/users/{id}/disable on the caller's OWN id
# is refused 400 (self-guard, decision 9).
async def test_disable_self_400__DoD10_US009_AC3(http_client):
    admin, admin_token = await _seed_admin(http_client)

    resp = await http_client.put(
        _disable_url(admin.id), headers=_auth_header(admin_token)
    )
    assert resp.status_code == 400


# DoD-11 (decision 2): each mutating endpoint called with a non-existent user_id
# returns 404.
async def test_mutations_nonexistent_user_404__DoD11_decision2(http_client):
    admin, admin_token = await _seed_admin(http_client)
    headers = _auth_header(admin_token)

    pw = await http_client.put(
        _password_url(NONEXISTENT_ID),
        headers=headers,
        json={"password": "password123", "password_confirm": "password123"},
    )
    assert pw.status_code == 404

    role = await http_client.put(
        _role_url(NONEXISTENT_ID),
        headers=headers,
        json={"role": UserRole.author.value},
    )
    assert role.status_code == 404

    disable = await http_client.put(_disable_url(NONEXISTENT_ID), headers=headers)
    assert disable.status_code == 404


# DoD-12 (decision 2/4): create with a password shorter than 8 chars is refused
# 400 (password validation lives in the service, mapped to 400).
async def test_create_short_password_400__DoD12_decision2_4(http_client):
    admin, admin_token = await _seed_admin(http_client)
    short_password = "shortpw"  # 7 chars, below the minimum length of 8
    assert len(short_password) < 8

    resp = await http_client.post(
        USERS_URL,
        headers=_auth_header(admin_token),
        json={
            "username": "newbie",
            "password": short_password,
            "password_confirm": short_password,
            "role": UserRole.author.value,
        },
    )
    assert resp.status_code == 400


# DoD-12 (decision 2/4): create with a mismatched confirm is refused 400.
async def test_create_mismatched_confirm_400__DoD12_decision2_4(http_client):
    admin, admin_token = await _seed_admin(http_client)

    resp = await http_client.post(
        USERS_URL,
        headers=_auth_header(admin_token),
        json={
            "username": "newbie",
            "password": "password123",
            "password_confirm": "password999",
            "role": UserRole.author.value,
        },
    )
    assert resp.status_code == 400


# DoD-12 (decision 2/4): reset with a password shorter than 8 chars is refused
# 400.
async def test_reset_short_password_400__DoD12_decision2_4(http_client):
    admin, admin_token = await _seed_admin(http_client)
    target = await _seed_user(username="target", password="password123", role=UserRole.author)
    short_password = "shortpw"  # 7 chars, below the minimum length of 8
    assert len(short_password) < 8

    resp = await http_client.put(
        _password_url(target.id),
        headers=_auth_header(admin_token),
        json={"password": short_password, "password_confirm": short_password},
    )
    assert resp.status_code == 400


# DoD-12 (decision 2/4): reset with a mismatched confirm is refused 400.
async def test_reset_mismatched_confirm_400__DoD12_decision2_4(http_client):
    admin, admin_token = await _seed_admin(http_client)
    target = await _seed_user(username="target", password="password123", role=UserRole.author)

    resp = await http_client.put(
        _password_url(target.id),
        headers=_auth_header(admin_token),
        json={"password": "password123", "password_confirm": "password999"},
    )
    assert resp.status_code == 400
