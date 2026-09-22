"""End-to-end tests for the admin LLM-server HTTP surface (feature 006, step 004).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). The app's startup
lifespan runs against a throwaway temp DB; each test seeds its own users on the
same process-global engine the app uses (schema built with `init_db`, readiness
flipped with `set_db_ready(True)`), mirroring tests/routes/admin/test_users.py's
`_seed_user` / `_seed_admin` helpers. The autouse `_reset_db_ready` fixture
(conftest) restores the cold-boot readiness default before each test.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 004, and the Step 002
schemas / error taxonomy + Step 003 probe seam it consumes):

    app.routes.admin.llm_servers  (router prefix "/api/admin/llm-servers",
      every endpoint gated by Depends(require_role(UserRole.admin)), D7;
      static /embedding routes declared BEFORE /{server_id} param routes, D5):
        GET    ""                          -> 200, LlmServersListResponse {items:[...]}
        POST   ""    (CreateLlmServerRequest) -> 201, LlmServerResponse
        GET    /embedding                  -> 200, EmbeddingConfigResponse
        DELETE /embedding                  -> 204
        PUT    /{server_id}  (UpdateLlmServerRequest) -> 200, LlmServerResponse (404 missing)
        DELETE /{server_id}                -> 204 (404 missing)
        GET    /{server_id}/available-models -> 200, AvailableModelsResponse (502 probe-fail)
        PUT    /{server_id}/enabled-models (EnabledModelsRequest) -> 200, LlmServerResponse
        PUT    /{server_id}/embedding (SetEmbeddingRequest) -> 204
      typed-error -> status map (D7): missing-field / invalid-backend-type /
      env-not-set -> 400; not-found -> 404; probe-failed -> 502; non-admin -> 403.

    app.services.llm_servers  (given, steps 002/003):
        def _create_client(server, resolved_key)  -- the probe monkeypatch seam.
      Schemas in app.models.schemas.llm_servers (given, step 002):
        LlmServerResponse has NO api_key field, only has_api_key: bool; id is a
        str (snowflake serialized as a string, review R1).

And (features 003/004/005, treated as given):
    app.services.auth.create_access_token / hash_password / generate_signing_key
    app.services.auth.require_role  (mounted on each endpoint)
    app.db.users.create / app.db.engine.init_db / set_db_ready

THE AIR GAP — the probe endpoint tests (DoD-8/DoD-9) monkeypatch the SERVICE seam
`app.services.llm_servers._create_client` with a fake factory returning a fake
client whose `list_models()` is async; the real `llm` library is never touched
and no network is used.

Expected values come from the SPEC ONLY — the step DoD (DoD-1..DoD-12), the step
Interface intent, and decisions D5 (static /embedding ordering), D7 (gating +
error->status taxonomy), D8 (probe-failed -> 502) from context.md, plus the cited
US-###.AC-# acceptance criteria — never from implementation internals.

Async tests use asyncio_mode = "auto".
"""

import datetime

import aiohttp

from app.db import users
from app.db.engine import init_db, set_db_ready
from app.models.schemas.llm_servers import (
    AvailableModelsResponse,
    EmbeddingConfigResponse,
    LlmServerResponse,
    LlmServersListResponse,
)
from app.models.user import User, UserRole
from app.services import auth
from app.services import llm_servers as llm_servers_service

BASE = "/api/admin/llm-servers"
EMBEDDING_URL = f"{BASE}/embedding"

# A server id no test ever creates (snowflake ids are large, review R1) — used to
# reach the not-found path. FastAPI coerces the URL segment back to int.
NONEXISTENT_ID = 999999


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _server_url(server_id: int) -> str:
    return f"{BASE}/{server_id}"


def _available_models_url(server_id: int) -> str:
    return f"{BASE}/{server_id}/available-models"


def _enabled_models_url(server_id: int) -> str:
    return f"{BASE}/{server_id}/enabled-models"


def _server_embedding_url(server_id: int) -> str:
    return f"{BASE}/{server_id}/embedding"


async def _seed_user(
    *,
    username: str,
    password: str | None = "password123",
    role: UserRole = UserRole.admin,
) -> User:
    """Seed a persisted user on the app's engine and mark the instance configured.

    Mirrors tests/routes/admin/test_users.py's `_seed_user`: builds the schema
    (`init_db`, idempotent), creates the user with a real bcrypt pwdhash and a
    per-user signing key, then flips readiness True. Returns the created `User`
    so the caller can mint an access token for it.
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
    admin = await _seed_user(username=username, role=UserRole.admin)
    return admin, auth.create_access_token(admin)


async def _create_server(
    http_client,
    token: str,
    *,
    name: str = "Test Server",
    backend_type: str = "openai",
    base_url: str = "https://api.openai.com/v1",
    api_key: str | None = None,
    is_active: bool = True,
) -> dict:
    """POST a server via the admin route and return the 201 response body."""
    payload: dict[str, object] = {
        "name": name,
        "backend_type": backend_type,
        "base_url": base_url,
        "is_active": is_active,
    }
    if api_key is not None:
        payload["api_key"] = api_key
    resp = await http_client.post(BASE, headers=_auth_header(token), json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


class FakeClient:
    """A stand-in for the real `llm` client returned by `_create_client`.

    `list_models()` is async (probe_models does `await client.list_models()`).
    It returns the configured model list or raises the configured exception,
    driving the success and failure paths without touching the real `llm`
    library.
    """

    def __init__(
        self,
        models: list[str] | None = None,
        list_models_exc: BaseException | None = None,
    ) -> None:
        self._models = models if models is not None else []
        self._list_models_exc = list_models_exc

    async def list_models(self) -> list[str]:
        if self._list_models_exc is not None:
            raise self._list_models_exc
        return list(self._models)


# DoD-1 (D7 gating): GET /api/admin/llm-servers with an author-role token is
# refused 403 (require_role ladder: author < admin); with an admin-role token it
# returns 200.
async def test_list_author_403_admin_200__DoD1_D7(http_client):
    _admin, admin_token = await _seed_admin(http_client)
    author = await _seed_user(username="scribe", role=UserRole.author)

    forbidden = await http_client.get(
        BASE, headers=_auth_header(auth.create_access_token(author))
    )
    assert forbidden.status_code == 403

    allowed = await http_client.get(BASE, headers=_auth_header(admin_token))
    assert allowed.status_code == 200
    LlmServersListResponse.model_validate(allowed.json())


# DoD-2 (US-010.AC-1): POST /api/admin/llm-servers with name + backend_type +
# base_url (a valid backend_type, "openai") returns 201, and a subsequent GET ""
# lists the created server.
async def test_create_201_then_listed__DoD2_US010_AC1(http_client):
    _admin, admin_token = await _seed_admin(http_client)

    resp = await http_client.post(
        BASE,
        headers=_auth_header(admin_token),
        json={
            "name": "OpenAI Main",
            "backend_type": "openai",
            "base_url": "https://api.openai.com/v1",
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    LlmServerResponse.model_validate(created)
    assert created["name"] == "OpenAI Main"
    assert created["backend_type"] == "openai"
    assert created["base_url"] == "https://api.openai.com/v1"

    listing = await http_client.get(BASE, headers=_auth_header(admin_token))
    assert listing.status_code == 200
    body = listing.json()
    LlmServersListResponse.model_validate(body)
    ids = [item["id"] for item in body["items"]]
    assert created["id"] in ids


# DoD-3 (US-010.AC-2): POST with a backend_type outside {llama-swap, openai}
# (e.g. "anthropic") is refused 400 (invalid-backend-type -> 400, D7).
async def test_create_invalid_backend_type_400__DoD3_US010_AC2(http_client):
    _admin, admin_token = await _seed_admin(http_client)

    resp = await http_client.post(
        BASE,
        headers=_auth_header(admin_token),
        json={
            "name": "Bad Backend",
            "backend_type": "anthropic",
            "base_url": "https://api.anthropic.com/v1",
        },
    )
    assert resp.status_code == 400


# DoD-4 (US-010.AC-3): POST with an EMPTY required field (name="") is refused 400
# (empty required field -> missing-field -> 400, D7 / 004.context).
async def test_create_empty_required_field_400__DoD4_US010_AC3(http_client):
    _admin, admin_token = await _seed_admin(http_client)

    resp = await http_client.post(
        BASE,
        headers=_auth_header(admin_token),
        json={
            "name": "",
            "backend_type": "openai",
            "base_url": "https://api.openai.com/v1",
        },
    )
    assert resp.status_code == 400


# DoD-5 (US-013.AC-1): PUT /api/admin/llm-servers/{id} updates fields; the updated
# server in a subsequent GET "" list reflects the new values.
async def test_update_reflects_new_values__DoD5_US013_AC1(http_client):
    _admin, admin_token = await _seed_admin(http_client)
    created = await _create_server(
        http_client,
        admin_token,
        name="Original",
        base_url="https://old.example.com/v1",
    )
    server_id = created["id"]

    resp = await http_client.put(
        _server_url(server_id),
        headers=_auth_header(admin_token),
        json={"name": "Renamed", "base_url": "https://new.example.com/v1"},
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    LlmServerResponse.model_validate(updated)
    assert updated["name"] == "Renamed"
    assert updated["base_url"] == "https://new.example.com/v1"

    listing = await http_client.get(BASE, headers=_auth_header(admin_token))
    assert listing.status_code == 200
    item = next(i for i in listing.json()["items"] if i["id"] == server_id)
    assert item["name"] == "Renamed"
    assert item["base_url"] == "https://new.example.com/v1"


# DoD-6 (US-013.AC-2): DELETE /api/admin/llm-servers/{id} returns 204 and the
# server no longer appears in GET ""; DELETE on a non-existent id returns 404.
async def test_delete_204_and_gone_then_nonexistent_404__DoD6_US013_AC2(http_client):
    _admin, admin_token = await _seed_admin(http_client)
    created = await _create_server(http_client, admin_token, name="Doomed")
    server_id = created["id"]

    resp = await http_client.delete(
        _server_url(server_id), headers=_auth_header(admin_token)
    )
    assert resp.status_code == 204

    listing = await http_client.get(BASE, headers=_auth_header(admin_token))
    assert listing.status_code == 200
    ids = [item["id"] for item in listing.json()["items"]]
    assert server_id not in ids

    missing = await http_client.delete(
        _server_url(NONEXISTENT_ID), headers=_auth_header(admin_token)
    )
    assert missing.status_code == 404


# DoD-7 (US-012.AC-1): PUT /api/admin/llm-servers/{id}/enabled-models with
# {enabled_models:[...]} persists the subset; the server in a subsequent GET ""
# shows that enabled_models list.
async def test_set_enabled_models_persists__DoD7_US012_AC1(http_client):
    _admin, admin_token = await _seed_admin(http_client)
    created = await _create_server(http_client, admin_token, name="Enable Me")
    server_id = created["id"]

    enabled = ["gpt-4o", "gpt-3.5-turbo"]
    resp = await http_client.put(
        _enabled_models_url(server_id),
        headers=_auth_header(admin_token),
        json={"enabled_models": enabled},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    LlmServerResponse.model_validate(body)
    assert body["enabled_models"] == enabled

    listing = await http_client.get(BASE, headers=_auth_header(admin_token))
    assert listing.status_code == 200
    item = next(i for i in listing.json()["items"] if i["id"] == server_id)
    assert item["enabled_models"] == enabled


# DoD-8 (US-011.AC-1): GET /api/admin/llm-servers/{id}/available-models with
# `_create_client` monkeypatched to a fake (whose async list_models yields a
# known unsorted list) returns 200 and the reported model list SORTED, wrapped in
# AvailableModelsResponse.models.
async def test_available_models_200_sorted__DoD8_US011_AC1(http_client, monkeypatch):
    _admin, admin_token = await _seed_admin(http_client)
    created = await _create_server(http_client, admin_token, name="Probe Me")
    server_id = created["id"]

    unsorted_models = ["gpt-4o", "aardvark", "mistral", "gpt-3.5"]
    fake = FakeClient(models=unsorted_models)

    def fake_create(server_arg, resolved_key):
        return fake

    monkeypatch.setattr(llm_servers_service, "_create_client", fake_create)

    resp = await http_client.get(
        _available_models_url(server_id), headers=_auth_header(admin_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    AvailableModelsResponse.model_validate(body)
    assert body["models"] == sorted(unsorted_models)


# DoD-9 (US-011.AC-2): the same endpoint, with the fake client raising
# aiohttp.ClientError, returns 502 (probe-failed -> 502, D8) and no model list.
async def test_available_models_probe_failure_502__DoD9_US011_AC2(
    http_client, monkeypatch
):
    _admin, admin_token = await _seed_admin(http_client)
    created = await _create_server(http_client, admin_token, name="Unreachable")
    server_id = created["id"]

    def fake_create(server_arg, resolved_key):
        raise aiohttp.ClientError("unreachable")

    monkeypatch.setattr(llm_servers_service, "_create_client", fake_create)

    resp = await http_client.get(
        _available_models_url(server_id), headers=_auth_header(admin_token)
    )
    assert resp.status_code == 502
    assert "models" not in resp.json()


# DoD-10 (US-014.AC-1 / US-014.AC-2): PUT /{id}/embedding designates the
# server+model (GET /embedding reflects it); designating a DIFFERENT server
# replaces the prior (GET /embedding then shows server B only); DELETE /embedding
# clears it (204) and GET /embedding shows the all-None indicator. Passing this
# also confirms the static /embedding routes resolve ahead of /{server_id} (D5).
async def test_embedding_designate_replace_clear__DoD10_US014_AC1_AC2(http_client):
    _admin, admin_token = await _seed_admin(http_client)
    headers = _auth_header(admin_token)
    server_a = await _create_server(http_client, admin_token, name="Server A")
    server_b = await _create_server(http_client, admin_token, name="Server B")
    id_a = server_a["id"]
    id_b = server_b["id"]

    # Designate A + model.
    set_a = await http_client.put(
        _server_embedding_url(id_a), headers=headers, json={"model": "text-embed-a"}
    )
    assert set_a.status_code == 204

    cfg = await http_client.get(EMBEDDING_URL, headers=headers)
    assert cfg.status_code == 200
    body = cfg.json()
    EmbeddingConfigResponse.model_validate(body)
    assert body["server_id"] == id_a
    assert body["model"] == "text-embed-a"

    # Designate B -> replaces the prior (A no longer the embedding server).
    set_b = await http_client.put(
        _server_embedding_url(id_b), headers=headers, json={"model": "text-embed-b"}
    )
    assert set_b.status_code == 204

    cfg2 = await http_client.get(EMBEDDING_URL, headers=headers)
    assert cfg2.status_code == 200
    body2 = cfg2.json()
    EmbeddingConfigResponse.model_validate(body2)
    assert body2["server_id"] == id_b
    assert body2["model"] == "text-embed-b"
    assert body2["server_id"] != id_a

    # Clear -> 204; GET /embedding then reports the all-None indicator.
    cleared = await http_client.delete(EMBEDDING_URL, headers=headers)
    assert cleared.status_code == 204

    cfg3 = await http_client.get(EMBEDDING_URL, headers=headers)
    assert cfg3.status_code == 200
    body3 = cfg3.json()
    EmbeddingConfigResponse.model_validate(body3)
    assert body3["server_id"] is None
    assert body3["model"] is None


# DoD-11 (US-021.AC-2): no POST / GET "" response body contains an `api_key` (or
# any raw-key) field; each server object carries `has_api_key`.
async def test_no_api_key_in_responses_has_api_key_present__DoD11_US021_AC2(
    http_client,
):
    _admin, admin_token = await _seed_admin(http_client)

    created = await _create_server(
        http_client, admin_token, name="Keyed", api_key="sk-literal-secret"
    )
    # POST response: no raw key, has_api_key present and True (key stored).
    assert "api_key" not in created
    assert "has_api_key" in created
    assert created["has_api_key"] is True

    listing = await http_client.get(BASE, headers=_auth_header(admin_token))
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert "api_key" not in item
        assert "has_api_key" in item
    keyed = next(i for i in items if i["id"] == created["id"])
    assert keyed["has_api_key"] is True


# DoD-12 (D7 not-found): PUT /{id}, DELETE /{id}, PUT /{id}/enabled-models, and
# PUT /{id}/embedding on a non-existent server_id each return 404.
async def test_mutations_nonexistent_server_404__DoD12_D7(http_client):
    _admin, admin_token = await _seed_admin(http_client)
    headers = _auth_header(admin_token)

    put_update = await http_client.put(
        _server_url(NONEXISTENT_ID), headers=headers, json={"name": "Nope"}
    )
    assert put_update.status_code == 404

    delete = await http_client.delete(_server_url(NONEXISTENT_ID), headers=headers)
    assert delete.status_code == 404

    enabled = await http_client.put(
        _enabled_models_url(NONEXISTENT_ID),
        headers=headers,
        json={"enabled_models": ["gpt-4o"]},
    )
    assert enabled.status_code == 404

    embedding = await http_client.put(
        _server_embedding_url(NONEXISTENT_ID),
        headers=headers,
        json={"model": "text-embed"},
    )
    assert embedding.status_code == 404
