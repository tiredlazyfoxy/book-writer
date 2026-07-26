"""End-to-end tests for the admin assistant-config HTTP surface (feature 012, step 005).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). The app's startup
lifespan runs against a throwaway temp DB; each test seeds its own users, modes
and servers on the same process-global engine the app uses (schema built with
`init_db`, readiness flipped with `set_db_ready(True)`), mirroring
tests/routes/admin/test_llm_servers.py's `_auth_header` / `_seed_user` /
`_seed_admin` helpers (context.md -> "Testing facts shared by every step").

Bound to the frozen skeleton (status.md -> Skeleton -> Step 005),
`app.routes.admin.assistant_config`, router prefix "/api/admin/assistant-config",
every handler carrying `Depends(auth_service.require_role(UserRole.admin))`:

    GET  /tools                              -> 200 ToolsListResponse
    GET  /modes                              -> 200 AssistantModesListResponse
    PUT  /modes/{mode_key}                   -> 200 AssistantModeResponse
        body UpdateAssistantModeRequest {system_prompt, tool_names, sub_agent_ids}
    GET  /sub-agents                         -> 200 SubAgentsListResponse
    POST /sub-agents                         -> 201 SubAgentResponse
        body CreateSubAgentRequest {name, system_prompt, llm_server_id,
                                    model_name, tool_names?, mode_keys?}
    PUT  /sub-agents/{sub_agent_id}          -> 200 SubAgentResponse
        body UpdateSubAgentRequest (same six fields)
    POST /sub-agents/{sub_agent_id}/disable  -> 200 SubAgentResponse  (NO body)
    POST /sub-agents/{sub_agent_id}/enable   -> 200 SubAgentResponse  (NO body)

`sub_agent_id` and `mode_key` are plain `str` path params handed to the service
verbatim -- an ill-formed id is the service's `sub-agent-not-found`, i.e. 404,
never FastAPI's 422 and never a 500 (frozen record; step DoD-7).

Reason -> status map, exhaustive over the ten `AssistantConfigErrorReason`
members (step Interface intent + frozen record):
    mode-not-found, sub-agent-not-found                      -> 404
    name-taken                                               -> 409
    blank-name, invalid-model-pair, unknown-or-inactive-server,
    model-not-enabled, unknown-tool, unknown-sub-agent,
    sub-agent-disabled                                       -> 400
403 (non-admin) and 401 (no token) come from the auth dependency itself and are
in no handler and in no map entry.

Arrangement uses the already-delivered lower layers (steps 001-004, all `done` /
PASS): `app.db.assistant_modes.seed_default_modes` for the fixed five mode rows
(the HTTP surface does not seed -- seeding is `services/setup.py`'s, closed in
step 001) and `app.db.llm_servers.create` for the model-pair fixture. Everything
else goes through the route family under test.

Expected values come from the SPEC ONLY -- the step DoD (DoD-1..DoD-12), the step
Interface intent, 005.context.md, the feature context.md scope decisions, and the
cited UC-### / US-###.AC-# ids -- never from implementation internals.

Registry independence: `TOOL_REGISTRY` has exactly one entry today (`web_search`)
but nothing here hard-codes that count (context.md -> "Inbound dependency"); every
tool-name expectation is DERIVED from the imported registry, so these tests stay
correct for zero, one or many entries.

Async tests use asyncio_mode = "auto". No network in any test.
"""

import datetime

from app.db import assistant_modes, llm_servers, sub_agents, users
from app.db.engine import init_db, set_db_ready
from app.models.llm_server import LlmServer
from app.models.schemas.assistant_config import (
    AssistantModeResponse,
    AssistantModesListResponse,
    SubAgentResponse,
    SubAgentsListResponse,
    ToolsListResponse,
)
from app.models.sub_agent import SubAgent
from app.models.user import User, UserRole
from app.services import auth
from app.services.tools import TOOL_REGISTRY

BASE = "/api/admin/assistant-config"
TOOLS_URL = f"{BASE}/tools"
MODES_URL = f"{BASE}/modes"
SUB_AGENTS_URL = f"{BASE}/sub-agents"

# The fixed five seeded mode keys (context.md -> "Modes"; 002.context.md ->
# "Mode ordering"). Written out here so the expectation is anchored in the spec.
SPEC_MODE_KEYS = (
    "edit-character",
    "edit-location",
    "edit-fact",
    "write-chapter",
    "close-chapter",
)

# Every tool name the catalogue can offer, DERIVED from the registry -- never a
# literal, never a count.
ALL_TOOL_NAMES = [tool.name for tool in TOOL_REGISTRY]

# A name the registry does not contain (asserted, not assumed, at point of use).
UNKNOWN_TOOL_NAME = "definitely-not-a-registered-tool"

# A mode key `seed_default_modes` never creates.
UNKNOWN_MODE_KEY = "definitely-not-a-seeded-mode"

# A well-formed but never-created sub-agent id, and an id that is not an id at
# all -- DoD-7 requires 404 for BOTH (never 422, never 500).
MISSING_SUB_AGENT_ID = "9999999999999999"
ILL_FORMED_SUB_AGENT_IDS = ("not-an-id", "12x", "1e5")


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mode_url(mode_key: str) -> str:
    return f"{MODES_URL}/{mode_key}"


def _sub_agent_url(sub_agent_id: str) -> str:
    return f"{SUB_AGENTS_URL}/{sub_agent_id}"


def _disable_url(sub_agent_id: str) -> str:
    return f"{_sub_agent_url(sub_agent_id)}/disable"


def _enable_url(sub_agent_id: str) -> str:
    return f"{_sub_agent_url(sub_agent_id)}/enable"


async def _seed_user(
    *,
    username: str,
    password: str | None = "password123",
    role: UserRole = UserRole.admin,
) -> User:
    """Seed a persisted user on the app's engine and mark the instance configured.

    Mirrors tests/routes/admin/test_llm_servers.py's `_seed_user`: builds the
    schema (`init_db`, idempotent), creates the user with a real bcrypt pwdhash
    and a per-user signing key, then flips readiness True.
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


async def _seed_admin(username: str = "root") -> tuple[User, str]:
    """Seed an admin caller and return (user, access token)."""
    admin = await _seed_user(username=username, role=UserRole.admin)
    return admin, auth.create_access_token(admin)


async def _seed_author(username: str = "scribe") -> tuple[User, str]:
    """Seed a NON-admin (author) caller and return (user, access token)."""
    author = await _seed_user(username=username, role=UserRole.author)
    return author, auth.create_access_token(author)


async def _seed_modes() -> None:
    """Create the fixed five `AssistantMode` rows this feature edits.

    The HTTP surface never seeds; seeding lives on the two `services/setup.py`
    first-run paths (context.md -> scope decision 4), so a route test arranges it
    directly through the already-delivered `db/` layer.
    """
    await init_db()
    await assistant_modes.seed_default_modes()


async def _seed_sub_agent(name: str = "Sweep Target") -> SubAgent:
    """Insert a sub-agent row directly through the `db/` layer.

    Used to arrange a target for clauses that are NOT about creating one, so a
    broken create endpoint cannot fail an authorization test for a reason that
    has nothing to do with authorization.
    """
    await init_db()
    return await sub_agents.create(
        SubAgent(
            name=name,
            system_prompt="Seeded through db/, not through the surface under test.",
            disabled=False,
            llm_server_id=None,
            model_name=None,
            created_at=_now(),
            modified_at=_now(),
        )
    )


async def _seed_server(
    *,
    name: str,
    enabled_models: str,
    is_active: bool = True,
    api_key: str | None = None,
) -> LlmServer:
    """Seed an LLM server row (the `tests/routes/test_chats.py:_seed_server` idiom).

    `enabled_models` is the stored JSON *string*, decoded at the service edge.
    """
    return await llm_servers.create(
        LlmServer(
            name=name,
            backend_type="openai",
            base_url="https://api.example.com/v1",
            api_key=api_key,
            enabled_models=enabled_models,
            is_active=is_active,
        )
    )


def _mode_body(
    *,
    system_prompt: str | None = None,
    tool_names: list[str] | None = None,
    sub_agent_ids: list[str] | None = None,
) -> dict:
    """An `UpdateAssistantModeRequest` body -- all three fields always present.

    Writes are full-replace, and no field of this request has a default
    (context.md -> "Writes are full-replace"; step-002 frozen record).
    """
    return {
        "system_prompt": system_prompt,
        "tool_names": [] if tool_names is None else tool_names,
        "sub_agent_ids": [] if sub_agent_ids is None else sub_agent_ids,
    }


def _sub_agent_body(
    *,
    name: str,
    system_prompt: str = "You keep the continuity straight.",
    llm_server_id: str | None = None,
    model_name: str | None = None,
    tool_names: list[str] | None = None,
    mode_keys: list[str] | None = None,
) -> dict:
    """A Create/UpdateSubAgentRequest body.

    The four scalars are always explicit (none has a default -- the model pair's
    inherit state is `null` + `null`, passed deliberately). The two selection
    lists ARE defaulted, so they are sent only when the caller supplies them.
    """
    body: dict = {
        "name": name,
        "system_prompt": system_prompt,
        "llm_server_id": llm_server_id,
        "model_name": model_name,
    }
    if tool_names is not None:
        body["tool_names"] = tool_names
    if mode_keys is not None:
        body["mode_keys"] = mode_keys
    return body


async def _create_sub_agent(http_client, token: str, **kwargs) -> dict:
    """POST a sub-agent through the route and return the 201 response body."""
    resp = await http_client.post(
        SUB_AGENTS_URL, headers=_auth_header(token), json=_sub_agent_body(**kwargs)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


HTTP_METHOD_NAMES = ("GET", "PUT", "POST", "PATCH", "DELETE")


def _family_operations() -> dict[str, set[str]]:
    """Path template -> declared HTTP methods, for the mounted family only.

    Read from the app's GENERATED OpenAPI document, which enumerates the
    operations the running application actually exposes (the top-level
    `app.routes` list does not: `include_router` keeps included routes wrapped).
    """
    from app.main import app

    paths = app.openapi()["paths"]
    return {
        path: {method.upper() for method in item if method.upper() in HTTP_METHOD_NAMES}
        for path, item in paths.items()
        if path.startswith(BASE)
    }


def _family_operation_set() -> set[tuple[str, str]]:
    """(METHOD, path template) for every operation the app exposes in the family."""
    return {
        (method, path)
        for path, methods in _family_operations().items()
        for method in methods
    }


def _family_requests(
    *, mode_key: str, sub_agent_id: str
) -> list[tuple[str, str, dict | None]]:
    """(method, url, json-body) for EVERY endpoint in the family -- all eight.

    Enumerated, never sampled: DoD-2 and DoD-3 are whole-family sweeps, reads as
    well as writes. The two state transitions are zero-body POSTs (frozen record).

    The table is cross-checked against the operations the app actually exposes,
    so the sweep covers the family exactly -- neither missing an endpoint the app
    added nor silently shrinking. Path templates carry the frozen param names
    `{mode_key}` / `{sub_agent_id}`.
    """
    requests = [
        ("GET", f"{BASE}/tools", TOOLS_URL, None),
        ("GET", f"{BASE}/modes", MODES_URL, None),
        (
            "PUT",
            f"{BASE}/modes/{{mode_key}}",
            _mode_url(mode_key),
            _mode_body(system_prompt="swept"),
        ),
        ("GET", f"{BASE}/sub-agents", SUB_AGENTS_URL, None),
        (
            "POST",
            f"{BASE}/sub-agents",
            SUB_AGENTS_URL,
            _sub_agent_body(name="Swept Into Existence"),
        ),
        (
            "PUT",
            f"{BASE}/sub-agents/{{sub_agent_id}}",
            _sub_agent_url(sub_agent_id),
            _sub_agent_body(name="Swept Rename"),
        ),
        (
            "POST",
            f"{BASE}/sub-agents/{{sub_agent_id}}/disable",
            _disable_url(sub_agent_id),
            None,
        ),
        (
            "POST",
            f"{BASE}/sub-agents/{{sub_agent_id}}/enable",
            _enable_url(sub_agent_id),
            None,
        ),
    ]
    assert len(requests) == 8, "the family has exactly eight operations"
    assert {
        (method, template) for method, template, _url, _body in requests
    } == _family_operation_set(), (
        "the sweep must cover exactly the operations the app exposes in this family"
    )
    return [(method, url, body) for method, _template, url, body in requests]


def _walk(node, path: str = "$"):
    """Yield (path, key, value) for every dict entry in a decoded JSON payload."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield f"{path}.{key}", key, value
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, f"{path}[{index}]")


# ---------------------------------------------------------------------------
# DoD-1 (UC-095; US-110.AC-1, US-111.AC-1, US-112.AC-1): the mode surface.
# ---------------------------------------------------------------------------


# DoD-1 (UC-095 step 1; US-110.AC-1): GET /modes as an admin returns the five
# modes, each carrying its prompt and its two selections.
async def test_get_modes_returns_the_five_with_prompt_and_selections__DoD1_US110_AC1(
    http_client,
):
    _admin, admin_token = await _seed_admin()
    await _seed_modes()

    resp = await http_client.get(MODES_URL, headers=_auth_header(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    AssistantModesListResponse.model_validate(body)

    items = body["items"]
    assert len(items) == 5
    assert {item["key"] for item in items} == set(SPEC_MODE_KEYS)
    for item in items:
        assert "system_prompt" in item
        assert item["tool_names"] == []
        assert item["sub_agent_ids"] == []


# DoD-1 (UC-095 steps 2-5; US-110.AC-1, US-111.AC-1, US-112.AC-1): PUT
# /modes/{mode_key} stores a prompt, a tool set and a sub-agent set, returns the
# updated mode, and a subsequent GET /modes reports the same stored state.
async def test_put_mode_stores_prompt_tools_and_sub_agents__DoD1_UC095(http_client):
    _admin, admin_token = await _seed_admin()
    await _seed_modes()
    headers = _auth_header(admin_token)

    helper = await _create_sub_agent(http_client, admin_token, name="Continuity Checker")
    selected_tools = ALL_TOOL_NAMES[:1]  # derived, correct at any registry size

    resp = await http_client.put(
        _mode_url("edit-character"),
        headers=headers,
        json=_mode_body(
            system_prompt="Stay in character.",
            tool_names=selected_tools,
            sub_agent_ids=[helper["id"]],
        ),
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    AssistantModeResponse.model_validate(updated)
    assert updated["key"] == "edit-character"
    assert updated["system_prompt"] == "Stay in character."
    assert set(updated["tool_names"]) == set(selected_tools)
    assert updated["sub_agent_ids"] == [helper["id"]]

    listing = await http_client.get(MODES_URL, headers=headers)
    assert listing.status_code == 200
    stored = next(m for m in listing.json()["items"] if m["key"] == "edit-character")
    assert stored["system_prompt"] == "Stay in character."
    assert set(stored["tool_names"]) == set(selected_tools)
    assert stored["sub_agent_ids"] == [helper["id"]]


# ---------------------------------------------------------------------------
# DoD-2 / DoD-3: the authorization sweeps -- EVERY endpoint, reads and writes.
# ---------------------------------------------------------------------------


# DoD-2 (US-110.AC-2, US-113.AC-4; authorization.md -> "Global assistant
# configuration (FEAT-020) -- admin only"): every endpoint in the family answers
# 403 to an authenticated non-admin (an author). Real, existing target ids are
# used so a 403 cannot be confused with a not-found refusal.
async def test_every_endpoint_403_for_author__DoD2_US110_AC2_US113_AC4(http_client):
    _admin, _admin_token = await _seed_admin()
    await _seed_modes()
    _author, author_token = await _seed_author()
    existing = await _seed_sub_agent()

    for method, url, body in _family_requests(
        mode_key="edit-character", sub_agent_id=str(existing.id)
    ):
        resp = await http_client.request(
            method, url, headers=_auth_header(author_token), json=body
        )
        assert resp.status_code == 403, f"{method} {url} -> {resp.status_code}"


# DoD-3 (US-110.AC-2, US-113.AC-4; authorization.md -> "Failure modes"): every
# endpoint answers 401 with no bearer token -- there is no anonymous surface.
async def test_every_endpoint_401_without_token__DoD3_US110_AC2_US113_AC4(http_client):
    _admin, _admin_token = await _seed_admin()
    await _seed_modes()
    existing = await _seed_sub_agent()

    for method, url, body in _family_requests(
        mode_key="edit-character", sub_agent_id=str(existing.id)
    ):
        resp = await http_client.request(method, url, json=body)
        assert resp.status_code == 401, f"{method} {url} -> {resp.status_code}"


# ---------------------------------------------------------------------------
# DoD-4 (UC-096; US-113.AC-1): create + list.
# ---------------------------------------------------------------------------


# DoD-4: POST /sub-agents returns 201 with a sub-agent carrying a STRING id, and
# GET /sub-agents lists it.
async def test_create_201_string_id_then_listed__DoD4_UC096_US113_AC1(http_client):
    _admin, admin_token = await _seed_admin()
    headers = _auth_header(admin_token)

    resp = await http_client.post(
        SUB_AGENTS_URL,
        headers=headers,
        json=_sub_agent_body(
            name="Continuity Checker", system_prompt="Check the continuity."
        ),
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    SubAgentResponse.model_validate(created)
    assert isinstance(created["id"], str)
    assert created["name"] == "Continuity Checker"
    assert created["system_prompt"] == "Check the continuity."
    assert created["disabled"] is False

    listing = await http_client.get(SUB_AGENTS_URL, headers=headers)
    assert listing.status_code == 200, listing.text
    body = listing.json()
    SubAgentsListResponse.model_validate(body)
    listed = [item["id"] for item in body["items"]]
    assert created["id"] in listed
    assert all(isinstance(item["id"], str) for item in body["items"])


# ---------------------------------------------------------------------------
# DoD-5 (US-113.AC-3): duplicate name -> 409, on create and on update.
# ---------------------------------------------------------------------------


async def test_duplicate_name_409_on_create_and_update__DoD5_US113_AC3(http_client):
    _admin, admin_token = await _seed_admin()
    headers = _auth_header(admin_token)

    await _create_sub_agent(http_client, admin_token, name="Continuity Checker")
    other = await _create_sub_agent(http_client, admin_token, name="Style Editor")

    duplicate_create = await http_client.post(
        SUB_AGENTS_URL, headers=headers, json=_sub_agent_body(name="Continuity Checker")
    )
    assert duplicate_create.status_code == 409, duplicate_create.text

    duplicate_update = await http_client.put(
        _sub_agent_url(other["id"]),
        headers=headers,
        json=_sub_agent_body(name="Continuity Checker"),
    )
    assert duplicate_update.status_code == 409, duplicate_update.text


# ---------------------------------------------------------------------------
# DoD-6 (UC-096 exception flow; US-113.AC-5): blank name -> 400, half-set model
# pair -> 400.
# ---------------------------------------------------------------------------


async def test_blank_name_400_on_create_and_update__DoD6_US113_AC5(http_client):
    _admin, admin_token = await _seed_admin()
    headers = _auth_header(admin_token)
    existing = await _create_sub_agent(http_client, admin_token, name="Renameable")

    for blank in ("", "   "):
        created = await http_client.post(
            SUB_AGENTS_URL, headers=headers, json=_sub_agent_body(name=blank)
        )
        assert created.status_code == 400, f"create name={blank!r}: {created.text}"

        updated = await http_client.put(
            _sub_agent_url(existing["id"]),
            headers=headers,
            json=_sub_agent_body(name=blank),
        )
        assert updated.status_code == 400, f"update name={blank!r}: {updated.text}"


async def test_half_set_model_pair_400__DoD6_US113_AC5(http_client):
    _admin, admin_token = await _seed_admin()
    headers = _auth_header(admin_token)
    server = await _seed_server(name="Active One", enabled_models='["gpt-4o"]')

    server_without_model = await http_client.post(
        SUB_AGENTS_URL,
        headers=headers,
        json=_sub_agent_body(
            name="Half A", llm_server_id=str(server.id), model_name=None
        ),
    )
    assert server_without_model.status_code == 400, server_without_model.text

    model_without_server = await http_client.post(
        SUB_AGENTS_URL,
        headers=headers,
        json=_sub_agent_body(name="Half B", llm_server_id=None, model_name="gpt-4o"),
    )
    assert model_without_server.status_code == 400, model_without_server.text


# ---------------------------------------------------------------------------
# DoD-7 (UC-095 precondition, UC-097 precondition): the 404 clauses.
# ---------------------------------------------------------------------------


# DoD-7: an unknown mode_key on PUT /modes/{mode_key}, and an unknown (but
# well-formed) sub_agent_id on PUT / disable / enable, each answer 404.
async def test_unknown_targets_404__DoD7_UC095_UC097(http_client):
    _admin, admin_token = await _seed_admin()
    await _seed_modes()
    headers = _auth_header(admin_token)

    unknown_mode = await http_client.put(
        _mode_url(UNKNOWN_MODE_KEY),
        headers=headers,
        json=_mode_body(system_prompt="nowhere to store this"),
    )
    assert unknown_mode.status_code == 404, unknown_mode.text

    missing_update = await http_client.put(
        _sub_agent_url(MISSING_SUB_AGENT_ID),
        headers=headers,
        json=_sub_agent_body(name="Ghost"),
    )
    assert missing_update.status_code == 404, missing_update.text

    missing_disable = await http_client.post(
        _disable_url(MISSING_SUB_AGENT_ID), headers=headers
    )
    assert missing_disable.status_code == 404, missing_disable.text

    missing_enable = await http_client.post(
        _enable_url(MISSING_SUB_AGENT_ID), headers=headers
    )
    assert missing_enable.status_code == 404, missing_enable.text


# DoD-7 (the clause the `str` path param exists for): a sub_agent_id that is NOT
# A VALID ID AT ALL answers 404 on PUT / disable / enable -- never 422, never 500.
async def test_ill_formed_sub_agent_id_404_not_422_not_500__DoD7_UC097(http_client):
    _admin, admin_token = await _seed_admin()
    headers = _auth_header(admin_token)

    for bad_id in ILL_FORMED_SUB_AGENT_IDS:
        update = await http_client.put(
            _sub_agent_url(bad_id), headers=headers, json=_sub_agent_body(name="Ghost")
        )
        assert update.status_code == 404, f"PUT id={bad_id!r}: {update.status_code}"

        disable = await http_client.post(_disable_url(bad_id), headers=headers)
        assert disable.status_code == 404, f"disable id={bad_id!r}: {disable.status_code}"

        enable = await http_client.post(_enable_url(bad_id), headers=headers)
        assert enable.status_code == 404, f"enable id={bad_id!r}: {enable.status_code}"


# ---------------------------------------------------------------------------
# DoD-8 (US-111.AC-1, US-113.AC-1): unknown tool name -> 400 on both saves.
# ---------------------------------------------------------------------------


async def test_unknown_tool_400_on_mode_and_sub_agent_save__DoD8_US111_AC1_US113_AC1(
    http_client,
):
    _admin, admin_token = await _seed_admin()
    await _seed_modes()
    headers = _auth_header(admin_token)
    assert UNKNOWN_TOOL_NAME not in ALL_TOOL_NAMES

    existing = await _create_sub_agent(http_client, admin_token, name="Tool User")

    mode_save = await http_client.put(
        _mode_url("write-chapter"),
        headers=headers,
        json=_mode_body(system_prompt="Write.", tool_names=[UNKNOWN_TOOL_NAME]),
    )
    assert mode_save.status_code == 400, mode_save.text

    sub_agent_create = await http_client.post(
        SUB_AGENTS_URL,
        headers=headers,
        json=_sub_agent_body(name="Bad Tools", tool_names=[UNKNOWN_TOOL_NAME]),
    )
    assert sub_agent_create.status_code == 400, sub_agent_create.text

    sub_agent_update = await http_client.put(
        _sub_agent_url(existing["id"]),
        headers=headers,
        json=_sub_agent_body(name="Tool User", tool_names=[UNKNOWN_TOOL_NAME]),
    )
    assert sub_agent_update.status_code == 400, sub_agent_update.text


# ---------------------------------------------------------------------------
# DoD-9 (US-114.AC-2, US-114.AC-3): disable / enable.
# ---------------------------------------------------------------------------


# DoD-9: POST /sub-agents/{id}/disable returns the sub-agent with `disabled` true
# and an EMPTY accessible-modes list, and the modes that referenced it no longer
# list it; POST .../enable returns it with `disabled` false and STILL no modes.
async def test_disable_detaches_modes_enable_restores_none__DoD9_US114_AC2_AC3(
    http_client,
):
    _admin, admin_token = await _seed_admin()
    await _seed_modes()
    headers = _auth_header(admin_token)

    attached_modes = ["edit-character", "edit-location"]
    agent = await _create_sub_agent(
        http_client, admin_token, name="Detachable", mode_keys=attached_modes
    )
    agent_id = agent["id"]
    assert set(agent["mode_keys"]) == set(attached_modes)

    before = await http_client.get(MODES_URL, headers=headers)
    assert before.status_code == 200
    for mode in before.json()["items"]:
        if mode["key"] in attached_modes:
            assert agent_id in mode["sub_agent_ids"]

    disabled = await http_client.post(_disable_url(agent_id), headers=headers)
    assert disabled.status_code == 200, disabled.text
    disabled_body = disabled.json()
    SubAgentResponse.model_validate(disabled_body)
    assert disabled_body["id"] == agent_id
    assert disabled_body["disabled"] is True
    assert disabled_body["mode_keys"] == []

    after_disable = await http_client.get(MODES_URL, headers=headers)
    assert after_disable.status_code == 200
    for mode in after_disable.json()["items"]:
        assert agent_id not in mode["sub_agent_ids"]

    enabled = await http_client.post(_enable_url(agent_id), headers=headers)
    assert enabled.status_code == 200, enabled.text
    enabled_body = enabled.json()
    SubAgentResponse.model_validate(enabled_body)
    assert enabled_body["id"] == agent_id
    assert enabled_body["disabled"] is False
    assert enabled_body["mode_keys"] == []

    after_enable = await http_client.get(MODES_URL, headers=headers)
    assert after_enable.status_code == 200
    for mode in after_enable.json()["items"]:
        assert agent_id not in mode["sub_agent_ids"]


# ---------------------------------------------------------------------------
# DoD-10 (UC-095 step 3): the tool catalogue.
# ---------------------------------------------------------------------------


# DoD-10: GET /tools returns the catalogue entries with `name` and `description`
# ONLY, and is admin-gated like the rest of the family.
async def test_tools_catalogue_name_and_description_only_admin_gated__DoD10_UC095(
    http_client,
):
    _admin, admin_token = await _seed_admin()
    _author, author_token = await _seed_author()

    resp = await http_client.get(TOOLS_URL, headers=_auth_header(admin_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ToolsListResponse.model_validate(body)

    items = body["items"]
    assert len(items) == len(ALL_TOOL_NAMES)
    assert {entry["name"] for entry in items} == set(ALL_TOOL_NAMES)
    for entry in items:
        assert set(entry.keys()) == {"name", "description"}

    forbidden = await http_client.get(TOOLS_URL, headers=_auth_header(author_token))
    assert forbidden.status_code == 403

    anonymous = await http_client.get(TOOLS_URL)
    assert anonymous.status_code == 401


# ---------------------------------------------------------------------------
# DoD-11 (UC-097 "No hard delete"; context.md -> scope decision 6): no DELETE.
# ---------------------------------------------------------------------------


# DoD-11: NO DELETE endpoint exists in the family. Asserted against the set of
# operations the running app actually exposes (its generated OpenAPI document) --
# not against one probed URL -- so no DELETE can reach a handler that removes
# anything; confirmed behaviorally by a DELETE that leaves the row listed.
async def test_no_delete_endpoint_in_family__DoD11_UC097(http_client):
    operations = _family_operations()
    assert operations, "the assistant-config route family must be mounted"
    for path, methods in operations.items():
        assert "DELETE" not in methods, f"{path} exposes DELETE"

    _admin, admin_token = await _seed_admin()
    headers = _auth_header(admin_token)
    agent = await _seed_sub_agent(name="Undeletable")

    attempt = await http_client.delete(_sub_agent_url(str(agent.id)), headers=headers)
    assert attempt.status_code not in (200, 201, 202, 204), attempt.text

    listing = await http_client.get(SUB_AGENTS_URL, headers=headers)
    assert listing.status_code == 200
    assert str(agent.id) in [item["id"] for item in listing.json()["items"]]


# ---------------------------------------------------------------------------
# DoD-12 (FEAT-004 secret policy; assistant-config.md -> "Tool registry"): the
# secret sweep across every response in the family.
# ---------------------------------------------------------------------------


# A distinctive stored key: the marker below must appear in NO response, whether
# raw or partially masked.
RAW_API_KEY = "sk-dod12-raw-secret-value"
SECRET_MARKER = "dod12"

# Key names no assistant-config response may carry: an api key in any spelling,
# or anything derived from ToolDef.args_schema / ToolDef.callable.
FORBIDDEN_KEY_SUBSTRINGS = (
    "api_key",
    "apikey",
    "api-key",
    "secret",
    "args_schema",
    "argsschema",
    "callable",
)


def _assert_no_secrets(label: str, payload) -> None:
    for path, key, value in _walk(payload):
        lowered = key.lower()
        for forbidden in FORBIDDEN_KEY_SUBSTRINGS:
            assert forbidden not in lowered, f"{label}: forbidden key at {path}"
        if isinstance(value, str):
            assert SECRET_MARKER not in value.lower(), f"{label}: key value at {path}"
            assert "***" not in value, f"{label}: masked key at {path}"


async def test_no_api_key_or_tool_internals_in_any_response__DoD12(http_client):
    _admin, admin_token = await _seed_admin()
    await _seed_modes()
    headers = _auth_header(admin_token)
    server = await _seed_server(
        name="Sweep Server", enabled_models='["gpt-4o"]', api_key=RAW_API_KEY
    )

    responses: list[tuple[str, object]] = []

    tools = await http_client.get(TOOLS_URL, headers=headers)
    assert tools.status_code == 200, tools.text
    responses.append(("GET /tools", tools.json()))
    # The args_schema / callable half, asserted directly on the catalogue shape.
    for entry in tools.json()["items"]:
        assert set(entry.keys()) == {"name", "description"}

    created = await http_client.post(
        SUB_AGENTS_URL,
        headers=headers,
        json=_sub_agent_body(
            name="Keyed Agent",
            llm_server_id=str(server.id),
            model_name="gpt-4o",
            mode_keys=["edit-fact"],
        ),
    )
    assert created.status_code == 201, created.text
    agent_id = created.json()["id"]
    responses.append(("POST /sub-agents", created.json()))

    listed = await http_client.get(SUB_AGENTS_URL, headers=headers)
    assert listed.status_code == 200, listed.text
    responses.append(("GET /sub-agents", listed.json()))

    updated = await http_client.put(
        _sub_agent_url(agent_id),
        headers=headers,
        json=_sub_agent_body(
            name="Keyed Agent",
            llm_server_id=str(server.id),
            model_name="gpt-4o",
            tool_names=ALL_TOOL_NAMES[:1],
            mode_keys=["edit-fact"],
        ),
    )
    assert updated.status_code == 200, updated.text
    responses.append(("PUT /sub-agents/{id}", updated.json()))

    saved_mode = await http_client.put(
        _mode_url("edit-fact"),
        headers=headers,
        json=_mode_body(
            system_prompt="Facts only.",
            tool_names=ALL_TOOL_NAMES[:1],
            sub_agent_ids=[agent_id],
        ),
    )
    assert saved_mode.status_code == 200, saved_mode.text
    responses.append(("PUT /modes/{mode_key}", saved_mode.json()))

    modes = await http_client.get(MODES_URL, headers=headers)
    assert modes.status_code == 200, modes.text
    responses.append(("GET /modes", modes.json()))

    disabled = await http_client.post(_disable_url(agent_id), headers=headers)
    assert disabled.status_code == 200, disabled.text
    responses.append(("POST /sub-agents/{id}/disable", disabled.json()))

    enabled = await http_client.post(_enable_url(agent_id), headers=headers)
    assert enabled.status_code == 200, enabled.text
    responses.append(("POST /sub-agents/{id}/enable", enabled.json()))

    assert len(responses) == 8, "every endpoint in the family is swept"
    for label, payload in responses:
        _assert_no_secrets(label, payload)
