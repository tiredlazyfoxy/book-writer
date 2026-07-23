"""Tests for the LLM-server probe / test-connection service
(feature 006, step 003).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 003,
plus the Step 002 error taxonomy):

    app.services.llm_servers  (amended, step 003):
        def _create_client(server: LlmServer, resolved_key: str | None) -> LLMClient
            # private, SYNC — the monkeypatch construction seam. `resolved_key`
            # is an explicit param (never resolved inside), so a fake client can
            # capture it (US-021.AC-1).
        async def probe_models(server_id: int) -> list[str]

    app.services.llm_servers  (given, step 002):
        class LlmServerErrorReason(str, enum.Enum)
            ... not_found="not-found", env_not_set="env-not-set",
            probe_failed="probe-failed"
        class LlmServerError(Exception)  __init__(reason, message="")  -> .reason

    app.db.llm_servers  (given, step 001):
        async def get_by_id(server_id: int) -> LlmServer | None
        async def create(server: LlmServer) -> LlmServer

    app.models.llm_server.LlmServer  (given, step 001)

THE AIR GAP — the real `llm` library is NEVER touched. `_create_client` is the
monkeypatch seam: every test replaces it (via `monkeypatch.setattr(svc,
"_create_client", ...)`) with a fake factory `(server, resolved_key)` returning
a fake client defined in this file. No network, no live server.

Expected values come from the SPEC ONLY — the step DoD (DoD-1..DoD-4), the step
Interface intent, and decisions D4/D8 (context.md) + the D3/US-021.AC-1
use-time `$ENV` resolution rule — never from implementation internals.

Key spec facts asserted here:
    - probe_models returns the model names the server reports, SORTED (D4/
      US-011.AC-1); it changes no server record.
    - construction OR list_models() raising aiohttp.ClientError (unreachable),
      llm.LLMError (HTTP/auth), or ValueError (keyless OpenAI) each surfaces as
      LlmServerError(probe_failed) with no model list returned (D8/US-011.AC-2).
    - a stored "$ENV" api_key is resolved at USE TIME (US-021.AC-1): with the
      env var set the resolved secret flows to _create_client; with it unset,
      probe_models raises env_not_set BEFORE any client is constructed.

DB-backed cases use the `db` fixture (conftest) — a throwaway temp-SQLite engine
with schema built — and seed a server row via db.llm_servers.create. Async tests
run under asyncio_mode = "auto".
"""

import os

import aiohttp
import pytest
from llm import LLMError

from app.db import llm_servers as db_llm_servers
from app.db.engine import DbConfig
from app.models.llm_server import LlmServer
from app.services import llm_servers as svc
from app.services.llm_servers import LlmServerError, LlmServerErrorReason

# An env-var name no other test relies on — used for the $ENV resolution cases.
_ENV_VAR_NAME = "BOOKWRITER_TEST_PROBE_KEY"

# An id that no test ever creates — used for the not-found guard, if reached.
_MISSING_ID = 999999


class FakeClient:
    """A stand-in for the real `llm` client returned by `_create_client`.

    `list_models()` is async (probe_models does `await client.list_models()`).
    It either returns the configured model list or raises the configured
    exception — letting a test drive the success and failure paths without ever
    touching the real `llm` library.
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


async def _seed_server(
    *,
    api_key: str | None = None,
    enabled_models: str = "[]",
    is_embedding: bool = False,
    name: str = "Probe Target",
    backend_type: str = "openai",
    base_url: str = "https://api.openai.com/v1",
) -> LlmServer:
    """Create one LlmServer row via the db layer and return the stored record."""
    return await db_llm_servers.create(
        LlmServer(
            name=name,
            backend_type=backend_type,
            base_url=base_url,
            api_key=api_key,
            enabled_models=enabled_models,
            is_embedding=is_embedding,
        )
    )


# DoD-1 (US-011.AC-1): with _create_client monkeypatched to return a fake client
# whose list_models() yields a KNOWN unsorted list, probe_models returns exactly
# that list SORTED, and leaves the server record unchanged (enabled_models /
# is_embedding and the other fields untouched).
async def test_probe_returns_sorted_models_and_leaves_record_unchanged__DoD1_US011_AC1(
    db: DbConfig, monkeypatch
):
    server = await _seed_server(
        api_key=None,
        enabled_models='["already-enabled"]',
        is_embedding=False,
    )

    unsorted_models = ["gpt-4o", "aardvark", "mistral", "gpt-3.5"]
    fake = FakeClient(models=unsorted_models)

    def fake_create(server_arg: LlmServer, resolved_key: str | None) -> FakeClient:
        return fake

    monkeypatch.setattr(svc, "_create_client", fake_create)

    result = await svc.probe_models(server.id)

    # Returned models are exactly the fake's list, sorted.
    assert result == sorted(unsorted_models)

    # The server record was not touched by the probe.
    stored = await db_llm_servers.get_by_id(server.id)
    assert stored is not None
    assert stored.enabled_models == '["already-enabled"]'
    assert stored.is_embedding is False
    assert stored.name == "Probe Target"
    assert stored.backend_type == "openai"
    assert stored.base_url == "https://api.openai.com/v1"
    assert stored.api_key is None


# DoD-2 (US-011.AC-2): when _create_client itself (construction) raises
# aiohttp.ClientError (unreachable server), probe_models raises
# LlmServerError(probe_failed) and returns no model list (the raise happens).
async def test_probe_construction_client_error_is_probe_failed__DoD2_US011_AC2(
    db: DbConfig, monkeypatch
):
    server = await _seed_server(api_key=None)

    def fake_create(server_arg: LlmServer, resolved_key: str | None) -> FakeClient:
        raise aiohttp.ClientError("unreachable")

    monkeypatch.setattr(svc, "_create_client", fake_create)

    with pytest.raises(LlmServerError) as exc:
        await svc.probe_models(server.id)
    assert exc.value.reason == LlmServerErrorReason.probe_failed


# DoD-2 (US-011.AC-2): when the fake client's list_models() raises
# aiohttp.ClientError (unreachable during the model call), probe_models raises
# LlmServerError(probe_failed) and returns no model list.
async def test_probe_list_models_client_error_is_probe_failed__DoD2_US011_AC2(
    db: DbConfig, monkeypatch
):
    server = await _seed_server(api_key=None)

    fake = FakeClient(list_models_exc=aiohttp.ClientError("connection reset"))

    def fake_create(server_arg: LlmServer, resolved_key: str | None) -> FakeClient:
        return fake

    monkeypatch.setattr(svc, "_create_client", fake_create)

    with pytest.raises(LlmServerError) as exc:
        await svc.probe_models(server.id)
    assert exc.value.reason == LlmServerErrorReason.probe_failed


# DoD-3 (D8): a fake client whose list_models() raises llm.LLMError (HTTP/auth
# failure) surfaces as LlmServerError(probe_failed).
async def test_probe_llm_error_is_probe_failed__DoD3_D8(db: DbConfig, monkeypatch):
    server = await _seed_server(api_key=None)

    fake = FakeClient(list_models_exc=LLMError("HTTP 401 unauthorized"))

    def fake_create(server_arg: LlmServer, resolved_key: str | None) -> FakeClient:
        return fake

    monkeypatch.setattr(svc, "_create_client", fake_create)

    with pytest.raises(LlmServerError) as exc:
        await svc.probe_models(server.id)
    assert exc.value.reason == LlmServerErrorReason.probe_failed


# DoD-3 (D8): a keyless OpenAI client raises ValueError at construction; when
# _create_client raises ValueError, probe_models surfaces it as
# LlmServerError(probe_failed).
async def test_probe_value_error_is_probe_failed__DoD3_D8(db: DbConfig, monkeypatch):
    server = await _seed_server(api_key=None)

    def fake_create(server_arg: LlmServer, resolved_key: str | None) -> FakeClient:
        raise ValueError("The api_key client option must be set")

    monkeypatch.setattr(svc, "_create_client", fake_create)

    with pytest.raises(LlmServerError) as exc:
        await svc.probe_models(server.id)
    assert exc.value.reason == LlmServerErrorReason.probe_failed


# DoD-4 (US-021.AC-1): with the env var SET, probe_models resolves a stored
# "$ENV" api_key at use time and passes the RESOLVED secret to _create_client —
# observable because the fake factory captures its resolved_key argument.
async def test_probe_resolves_env_key_at_use_time__DoD4_US021_AC1(
    db: DbConfig, monkeypatch
):
    monkeypatch.setenv(_ENV_VAR_NAME, "secret-resolved-value")
    server = await _seed_server(api_key=f"${_ENV_VAR_NAME}")

    captured: dict[str, str | None] = {}

    def fake_create(server_arg: LlmServer, resolved_key: str | None) -> FakeClient:
        captured["key"] = resolved_key
        return FakeClient(models=["anything"])

    monkeypatch.setattr(svc, "_create_client", fake_create)

    await svc.probe_models(server.id)

    # The key handed to the client factory is the resolved secret, not the token.
    assert captured["key"] == "secret-resolved-value"
    assert captured["key"] == os.environ[_ENV_VAR_NAME]


# DoD-4 (US-021.AC-1): with the env var UNSET, probe_models raises
# LlmServerError(env_not_set) BEFORE constructing any client — the fake
# _create_client is never called.
async def test_probe_unset_env_key_raises_env_not_set_before_client__DoD4_US021_AC1(
    db: DbConfig, monkeypatch
):
    monkeypatch.delenv(_ENV_VAR_NAME, raising=False)
    server = await _seed_server(api_key=f"${_ENV_VAR_NAME}")

    calls = {"n": 0}

    def fake_create(server_arg: LlmServer, resolved_key: str | None) -> FakeClient:
        calls["n"] += 1
        return FakeClient()

    monkeypatch.setattr(svc, "_create_client", fake_create)

    with pytest.raises(LlmServerError) as exc:
        await svc.probe_models(server.id)
    assert exc.value.reason == LlmServerErrorReason.env_not_set

    # Resolution failed at use time, before any client was constructed.
    assert calls["n"] == 0
