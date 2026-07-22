"""End-to-end tests for the first-run setup HTTP surface (feature 003, step 004).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). The app's startup
lifespan runs against a throwaway temp DB; per feature 003 the eager schema
creation was removed from the lifespan, so a freshly-booted instance is
*unconfigured* (no schema, `is_db_ready()` False -> `needs_setup` True) until a
setup flow runs. The autouse `_reset_db_ready` fixture (conftest, step 002)
guarantees the cold-boot readiness default before each test.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 004):
    class AuthStatusResponse(BaseModel): needs_setup: bool     (models/schemas/auth.py)
    class CreateDBRequest(BaseModel):
        admin_username: str; password: str; password_confirm: str
    class LoginResponse(BaseModel): token: str
    router = APIRouter(prefix="/api/auth")                     (routes/auth.py)
      GET  /api/auth/status         -> AuthStatusResponse
      POST /api/auth/setup/create   (body CreateDBRequest) -> LoginResponse
      POST /api/auth/setup/import   (multipart, field `file`: UploadFile)
                                    -> AuthStatusResponse

Expected values come from the step spec (004.setup-routes-schemas.md DoD +
Interface intent + 004.context.md + feature context / confirmed decisions),
never from implementation internals:
    - DoD-1: GET /status is `needs_setup: true` on a cold instance and
      `needs_setup: false` after a successful create.
    - DoD-2 (US-001.AC-1): POST /setup/create with valid creds (password >= 8,
      matching confirm) -> HTTP 200 + LoginResponse with a non-empty token
      (operator auto-signed-in, decision 8).
    - DoD-3 (US-001.AC-2): POST /setup/create on an already-configured instance
      -> HTTP 4xx (not 200).
    - DoD-4 (US-001.AC-3): POST /setup/create with a password < 8 chars ->
      HTTP 400, and no token in the body.
    - DoD-5 (US-001.AC-4): POST /setup/create with password != password_confirm
      -> HTTP 400, and no token in the body.
    - DoD-6 (US-002.AC-1): POST /setup/import with a VALID archive -> HTTP 200,
      `needs_setup: false`, and NO token in the body (import does not sign in,
      decision 8).
    - DoD-7 (US-002.AC-2): POST /setup/import with a corrupt archive -> HTTP 400,
      and a subsequent GET /status still reports `needs_setup: true` (instance
      remains unconfigured, decision 4).

Async tests (asyncio_mode = "auto"). The `file` multipart field is uploaded via
httpx's `files=` argument. Archive bytes for DoD-6 are produced in test setup by
seeding a user and calling `export_all()` (test-land helper, sanctioned by the
step brief) on the same process-global engine the app uses.
"""

from app.models.schemas.auth import AuthStatusResponse, LoginResponse

CREATE_URL = "/api/auth/setup/create"
IMPORT_URL = "/api/auth/setup/import"
STATUS_URL = "/api/auth/status"


# DoD-1: GET /api/auth/status returns needs_setup: true on a cold instance and
# needs_setup: false after a successful create.
async def test_status_cold_true_then_false_after_create__DoD1(http_client):
    # Cold instance (autouse readiness reset -> False): setup is needed.
    cold = await http_client.get(STATUS_URL)
    assert cold.status_code == 200
    assert cold.json() == {"needs_setup": True}

    # Drive a successful create through the endpoint (flips readiness).
    created = await http_client.post(
        CREATE_URL,
        json={
            "admin_username": "root",
            "password": "password123",
            "password_confirm": "password123",
        },
    )
    assert created.status_code == 200

    # Re-GET status: the configured instance no longer needs setup.
    warm = await http_client.get(STATUS_URL)
    assert warm.status_code == 200
    assert warm.json() == {"needs_setup": False}


# DoD-2 (US-001.AC-1): POST /api/auth/setup/create with valid credentials
# (password >= 8, matching confirm) returns HTTP 200 and a LoginResponse
# carrying a non-empty token (operator auto-signed-in).
async def test_create_valid_returns_200_and_token__DoD2(http_client):
    resp = await http_client.post(
        CREATE_URL,
        json={
            "admin_username": "root",
            "password": "password123",
            "password_confirm": "password123",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    # Response conforms to LoginResponse and the minted token is present + non-empty.
    model = LoginResponse.model_validate(body)
    assert isinstance(model.token, str)
    assert model.token != ""


# DoD-3 (US-001.AC-2): POST /api/auth/setup/create on an already-configured
# instance is refused with an HTTP 4xx (not 200).
async def test_create_on_configured_instance_refused_4xx__DoD3(http_client):
    # First create succeeds and configures the instance (flips readiness True).
    first = await http_client.post(
        CREATE_URL,
        json={
            "admin_username": "root",
            "password": "password123",
            "password_confirm": "password123",
        },
    )
    assert first.status_code == 200

    # Second create on the now-configured instance is refused with a 4xx.
    second = await http_client.post(
        CREATE_URL,
        json={
            "admin_username": "intruder",
            "password": "password123",
            "password_confirm": "password123",
        },
    )
    assert second.status_code != 200
    assert 400 <= second.status_code < 500


# DoD-4 (US-001.AC-3): POST /api/auth/setup/create with a password shorter than
# 8 characters returns HTTP 400 and mints no token.
async def test_create_short_password_400_no_token__DoD4(http_client):
    short_password = "shortpw"  # 7 chars, below the minimum length of 8
    assert len(short_password) < 8

    resp = await http_client.post(
        CREATE_URL,
        json={
            "admin_username": "root",
            "password": short_password,
            "password_confirm": short_password,
        },
    )

    assert resp.status_code == 400
    # No token minted on refusal.
    assert "token" not in resp.json()


# DoD-5 (US-001.AC-4): POST /api/auth/setup/create with password != confirmation
# returns HTTP 400 and mints no token.
async def test_create_password_mismatch_400_no_token__DoD5(http_client):
    resp = await http_client.post(
        CREATE_URL,
        json={
            "admin_username": "root",
            "password": "password123",
            "password_confirm": "password999",
        },
    )

    assert resp.status_code == 400
    # No token minted on refusal.
    assert "token" not in resp.json()


# DoD-6 (US-002.AC-1): POST /api/auth/setup/import with a VALID archive returns
# HTTP 200 with needs_setup: false and NO token in the body.
async def test_import_valid_archive_200_configured_no_token__DoD6(http_client):
    # Build a valid archive in test setup: seed a user on the app's engine, then
    # export_all() (test-land helper, sanctioned by the step brief). The
    # http_client lifespan has initialized the engine but not the schema, so
    # init_db() is called here to make the schema seedable.
    from app.db import users
    from app.db.engine import init_db, is_db_ready
    from app.models.user import User, UserRole
    from app.services.db_import_export import export_all

    await init_db()
    await users.create(
        User(
            username="restored_admin",
            role=UserRole.admin,
            pwdhash="restored-hash",
            jwt_signing_key="restored-key",
        )
    )
    archive_bytes = await export_all()

    # Precondition: the instance is still unconfigured before the import.
    assert is_db_ready() is False

    resp = await http_client.post(
        IMPORT_URL,
        files={"file": ("export.jsonl.gz", archive_bytes, "application/octet-stream")},
    )

    assert resp.status_code == 200
    body = resp.json()
    # Instance is now configured (needs_setup False) and NO token is returned.
    model = AuthStatusResponse.model_validate(body)
    assert model.needs_setup is False
    assert "token" not in body


# DoD-7 (US-002.AC-2): POST /api/auth/setup/import with a corrupt/invalid archive
# returns HTTP 400, and a subsequent GET /status still reports needs_setup: true
# (instance remains unconfigured).
async def test_import_corrupt_archive_400_stays_unconfigured__DoD7(http_client):
    resp = await http_client.post(
        IMPORT_URL,
        files={"file": ("broken.jsonl.gz", b"not a zip", "application/octet-stream")},
    )
    assert resp.status_code == 400

    # The refused import leaves the instance unconfigured: status still needs setup.
    status = await http_client.get(STATUS_URL)
    assert status.status_code == 200
    assert status.json() == {"needs_setup": True}
