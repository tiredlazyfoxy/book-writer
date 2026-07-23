"""Tests for the LLM-server service — CRUD / enable / embedding / masking
(feature 006, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002):

    app.models.schemas.llm_servers  (NEW):
        CreateLlmServerRequest {name: str, backend_type: str, base_url: str,
                                api_key: str | None = None, is_active: bool = True}
        UpdateLlmServerRequest {name, backend_type, base_url, api_key, is_active
                                — all optional, default None}
        LlmServerResponse {id: str, name, backend_type, base_url,
                           has_api_key: bool, enabled_models: list[str],
                           is_active, is_embedding, embedding_model,
                           created_at, modified_at}   # NO api_key field
        EmbeddingConfigResponse {server_id, server_name, base_url, backend_type,
                                 model, has_api_key}   # all-None when none

    app.services.llm_servers  (NEW):
        class LlmServerErrorReason(str, enum.Enum)
            invalid_backend_type="invalid-backend-type", missing_field="missing-field",
            not_found="not-found", env_not_set="env-not-set",
            probe_failed="probe-failed"
        class LlmServerError(Exception)  __init__(reason, message="")  -> .reason
        def _to_response(server: LlmServer) -> LlmServerResponse            (sync mapper)
        async def get_all_servers() -> LlmServersListResponse
        async def get_server(server_id: int) -> LlmServerResponse
        async def create_server(req: CreateLlmServerRequest) -> LlmServerResponse
        async def update_server(server_id: int, req: UpdateLlmServerRequest)
                                                        -> LlmServerResponse
        async def delete_server(server_id: int) -> None
        async def set_enabled_models(server_id: int, models: list[str])
                                                        -> LlmServerResponse
        async def set_embedding_server(server_id: int, model: str)
                                                        -> LlmServerResponse
        async def clear_embedding_server() -> None
        async def get_embedding_config() -> EmbeddingConfigResponse

    app.db.llm_servers  (given, step 001):
        async def get_by_id(server_id: int) -> LlmServer | None
        async def get_all() -> list[LlmServer]
        async def create(server: LlmServer) -> LlmServer

Expected values come from the SPEC ONLY — the step DoD (DoD-1..DoD-7, DoD-9,
DoD-10), the step Interface intent, and context.md decisions D2/D3/D5/D7 — never
from implementation internals.

Key spec facts asserted here:
    - backend_type is validated against {"llama-swap", "openai"} in the service
      (D2); an invalid value -> LlmServerError(invalid_backend_type); no row.
    - a required field left empty ("") -> LlmServerError(missing_field).
    - api_key partial-update rule (D3): omitted/None leaves the stored key
      unchanged; "" clears it (subsequent has_api_key false).
    - has_api_key = (api_key is not None and api_key != "") (D3), computed by
      the response mapper; the response NEVER carries the raw api_key.
    - enabled_models crosses the JSON-string <-> list[str] boundary: the
      response exposes the decoded list.
    - embedding designation is clear-all-then-set (D5): designating B clears A;
      exactly one server stays flagged.
    - not-found (D7): update/delete/set_enabled_models/set_embedding_server on a
      non-existent id each raise LlmServerError(not_found).

DB-backed cases use the `db` fixture (conftest) — a throwaway temp-SQLite engine
with schema built — and read back persistence via db.llm_servers. Async tests
run under asyncio_mode = "auto".
"""

import pytest

from app.db import llm_servers as db_llm_servers
from app.db.engine import DbConfig
from app.models.llm_server import LlmServer
from app.models.schemas.llm_servers import (
    CreateLlmServerRequest,
    LlmServerResponse,
    UpdateLlmServerRequest,
)
from app.services import llm_servers as svc
from app.services.llm_servers import LlmServerError, LlmServerErrorReason

# An id that no test ever creates — used for the not-found cases (D7).
_MISSING_ID = 999999


# DoD-1 (US-010.AC-1): create_server with name + backend_type + base_url + api_key
# persists the server (readable back via db.llm_servers.get_by_id) and returns a
# LlmServerResponse reflecting the supplied fields. id is a str (snowflake
# serialized as a string, review R1); because an api_key was supplied,
# has_api_key is True and the raw key is never exposed.
async def test_create_server_persists_and_reflects_fields__DoD1_US010_AC1(
    db: DbConfig,
):
    req = CreateLlmServerRequest(
        name="OpenAI Prod",
        backend_type="openai",
        base_url="https://api.openai.com/v1",
        api_key="$OPENAI_API_KEY",
    )

    resp = await svc.create_server(req)

    # The response reflects the supplied fields.
    assert isinstance(resp, LlmServerResponse)
    assert isinstance(resp.id, str)
    assert resp.name == "OpenAI Prod"
    assert resp.backend_type == "openai"
    assert resp.base_url == "https://api.openai.com/v1"
    assert resp.is_active is True
    # An api_key was supplied -> masked as has_api_key True; raw key never exposed.
    assert resp.has_api_key is True

    # The server was actually persisted with the supplied fields (the DTO id is
    # the stringified snowflake; the db layer keys on the int form).
    stored = await db_llm_servers.get_by_id(int(resp.id))
    assert stored is not None
    assert stored.name == "OpenAI Prod"
    assert stored.backend_type == "openai"
    assert stored.base_url == "https://api.openai.com/v1"
    assert stored.api_key == "$OPENAI_API_KEY"


# DoD-2 (US-010.AC-2): create_server with a backend_type outside
# {"llama-swap", "openai"} raises LlmServerError(invalid_backend_type) and no
# server is created.
async def test_create_server_invalid_backend_type_rejected__DoD2_US010_AC2(
    db: DbConfig,
):
    before = await db_llm_servers.get_all()

    req = CreateLlmServerRequest(
        name="Bogus",
        backend_type="anthropic",  # not in {"llama-swap", "openai"}
        base_url="https://example.com/v1",
    )

    with pytest.raises(LlmServerError) as exc:
        await svc.create_server(req)
    assert exc.value.reason == LlmServerErrorReason.invalid_backend_type

    # No server was created — the row count is unchanged.
    after = await db_llm_servers.get_all()
    assert len(after) == len(before)


# DoD-3 (US-010.AC-3): create_server with a required field (name / backend_type /
# base_url) left empty ("") raises LlmServerError(missing_field). Each required
# field is checked independently.
async def test_create_server_empty_required_field_rejected__DoD3_US010_AC3(
    db: DbConfig,
):
    cases = [
        CreateLlmServerRequest(
            name="", backend_type="openai", base_url="https://api.openai.com/v1"
        ),
        CreateLlmServerRequest(
            name="NoType", backend_type="", base_url="https://api.openai.com/v1"
        ),
        CreateLlmServerRequest(
            name="NoUrl", backend_type="openai", base_url=""
        ),
    ]

    for req in cases:
        with pytest.raises(LlmServerError) as exc:
            await svc.create_server(req)
        assert exc.value.reason == LlmServerErrorReason.missing_field


# DoD-4 (US-013.AC-1): update_server applies provided fields to the stored record;
# an omitted api_key (None) leaves the stored key unchanged.
async def test_update_server_applies_fields_and_keeps_key_when_omitted__DoD4_US013_AC1(
    db: DbConfig,
):
    created = await svc.create_server(
        CreateLlmServerRequest(
            name="Original",
            backend_type="openai",
            base_url="https://api.openai.com/v1",
            api_key="$OPENAI_API_KEY",
        )
    )

    # Update name + base_url; api_key omitted (None) -> stored key unchanged.
    resp = await svc.update_server(
        int(created.id),
        UpdateLlmServerRequest(
            name="Renamed", base_url="https://api.openai.com/v2"
        ),
    )

    # The provided fields are reflected.
    assert resp.name == "Renamed"
    assert resp.base_url == "https://api.openai.com/v2"
    # The omitted api_key was left unchanged (still present -> has_api_key True).
    assert resp.has_api_key is True

    stored = await db_llm_servers.get_by_id(int(created.id))
    assert stored is not None
    assert stored.name == "Renamed"
    assert stored.base_url == "https://api.openai.com/v2"
    assert stored.api_key == "$OPENAI_API_KEY"


# DoD-4 (US-013.AC-1): update_server with api_key == "" clears the stored key; the
# subsequent response shows has_api_key False and the stored key is None.
async def test_update_server_empty_api_key_clears_it__DoD4_US013_AC1(db: DbConfig):
    created = await svc.create_server(
        CreateLlmServerRequest(
            name="HasKey",
            backend_type="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-literal",
        )
    )
    assert created.has_api_key is True  # precondition: a key is stored

    resp = await svc.update_server(int(created.id), UpdateLlmServerRequest(api_key=""))

    # The empty string clears the key -> has_api_key False.
    assert resp.has_api_key is False

    stored = await db_llm_servers.get_by_id(int(created.id))
    assert stored is not None
    assert stored.api_key is None


# DoD-5 (US-012.AC-1): set_enabled_models persists the given subset; the returned
# response's enabled_models is the decoded list[str], and a re-fetch also decodes
# to that list (the JSON-string <-> list boundary).
async def test_set_enabled_models_persists_decoded_list__DoD5_US012_AC1(
    db: DbConfig,
):
    created = await svc.create_server(
        CreateLlmServerRequest(
            name="Models",
            backend_type="openai",
            base_url="https://api.openai.com/v1",
        )
    )

    subset = ["gpt-4o", "gpt-4o-mini"]
    resp = await svc.set_enabled_models(int(created.id), subset)

    # The returned response carries the decoded list[str].
    assert resp.enabled_models == subset

    # It was persisted: a fresh single-get also returns the decoded list.
    refetched = await svc.get_server(int(created.id))
    assert refetched.enabled_models == subset


# DoD-6 (US-014.AC-1): set_embedding_server(id, model) records the target as the
# embedding provider (is_embedding true + embedding_model set); get_embedding_config
# then returns that server + model.
async def test_set_embedding_server_records_and_reports__DoD6_US014_AC1(
    db: DbConfig,
):
    created = await svc.create_server(
        CreateLlmServerRequest(
            name="Embedder",
            backend_type="openai",
            base_url="https://api.openai.com/v1",
        )
    )

    resp = await svc.set_embedding_server(int(created.id), "text-embedding-3-small")

    # The target is now flagged with its embedding model.
    assert resp.is_embedding is True
    assert resp.embedding_model == "text-embedding-3-small"

    # get_embedding_config reports that server + model (server_id is the
    # stringified snowflake, matching the create response's id).
    config = await svc.get_embedding_config()
    assert config.server_id == created.id
    assert config.server_name == "Embedder"
    assert config.model == "text-embedding-3-small"


# DoD-7 (US-014.AC-2): after designating server A then server B, exactly one
# server stays flagged — is_embedding true only on B, cleared on A
# (clear-all-then-set, D5).
async def test_set_embedding_server_replaces_prior__DoD7_US014_AC2(db: DbConfig):
    a = await svc.create_server(
        CreateLlmServerRequest(
            name="ServerA",
            backend_type="openai",
            base_url="https://a.example.com/v1",
        )
    )
    b = await svc.create_server(
        CreateLlmServerRequest(
            name="ServerB",
            backend_type="openai",
            base_url="https://b.example.com/v1",
        )
    )

    await svc.set_embedding_server(int(a.id), "model-a")
    await svc.set_embedding_server(int(b.id), "model-b")

    stored_a = await db_llm_servers.get_by_id(int(a.id))
    stored_b = await db_llm_servers.get_by_id(int(b.id))
    assert stored_a is not None and stored_b is not None

    # Exactly one server is flagged — B, not A.
    assert stored_a.is_embedding is False
    assert stored_b.is_embedding is True

    # And the reported config points at B with its model.
    config = await svc.get_embedding_config()
    assert config.server_id == b.id
    assert config.model == "model-b"


# DoD-9 (US-021.AC-2): a LlmServerResponse produced by _to_response exposes NO
# api_key field and DOES expose has_api_key, computed as
# (api_key is not None and api_key != "") — True for a stored token/literal,
# False for None/empty. _to_response is a pure sync mapper; no DB is needed.
def test_to_response_masks_api_key__DoD9_US021_AC2():
    # The schema itself has no api_key field at all (masking by omission).
    assert "api_key" not in LlmServerResponse.model_fields
    assert "has_api_key" in LlmServerResponse.model_fields

    def _server(api_key: str | None) -> LlmServer:
        return LlmServer(
            id=1,
            name="S",
            backend_type="openai",
            base_url="https://api.openai.com/v1",
            api_key=api_key,
            enabled_models="[]",
        )

    # A stored literal token -> has_api_key True; no api_key on the response.
    resp_token = svc._to_response(_server("sk-literal"))
    assert resp_token.has_api_key is True
    assert not hasattr(resp_token, "api_key")
    assert "api_key" not in resp_token.model_dump()

    # A "$ENV" token is also a stored value -> has_api_key True.
    resp_env = svc._to_response(_server("$OPENAI_API_KEY"))
    assert resp_env.has_api_key is True

    # None -> has_api_key False.
    resp_none = svc._to_response(_server(None))
    assert resp_none.has_api_key is False

    # Empty string -> has_api_key False.
    resp_empty = svc._to_response(_server(""))
    assert resp_empty.has_api_key is False


# DoD-10 (D7 not-found): update_server on a non-existent id raises
# LlmServerError(not_found).
async def test_update_server_not_found__DoD10_D7(db: DbConfig):
    with pytest.raises(LlmServerError) as exc:
        await svc.update_server(_MISSING_ID, UpdateLlmServerRequest(name="X"))
    assert exc.value.reason == LlmServerErrorReason.not_found


# DoD-10 (D7 not-found): delete_server on a non-existent id raises
# LlmServerError(not_found).
async def test_delete_server_not_found__DoD10_D7(db: DbConfig):
    with pytest.raises(LlmServerError) as exc:
        await svc.delete_server(_MISSING_ID)
    assert exc.value.reason == LlmServerErrorReason.not_found


# DoD-10 (D7 not-found): set_enabled_models on a non-existent id raises
# LlmServerError(not_found).
async def test_set_enabled_models_not_found__DoD10_D7(db: DbConfig):
    with pytest.raises(LlmServerError) as exc:
        await svc.set_enabled_models(_MISSING_ID, ["gpt-4o"])
    assert exc.value.reason == LlmServerErrorReason.not_found


# DoD-10 (D7 not-found): set_embedding_server on a non-existent id raises
# LlmServerError(not_found).
async def test_set_embedding_server_not_found__DoD10_D7(db: DbConfig):
    with pytest.raises(LlmServerError) as exc:
        await svc.set_embedding_server(_MISSING_ID, "text-embedding-3-small")
    assert exc.value.reason == LlmServerErrorReason.not_found
