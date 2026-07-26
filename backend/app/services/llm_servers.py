"""LLM-server service — CRUD / enable / embedding business logic (feature 006, step 002).

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). All persistence goes through the session-free
``app.db.llm_servers`` layer (namespace import). Domain refusals raise the typed
:class:`LlmServerError`, discriminated by :class:`LlmServerErrorReason` so step
004's route maps each case to its HTTP status (D7); the route stays HTTP-only.

Secret masking (D3): the response mapper never dumps the ORM and never exposes
``api_key`` — only the computed ``has_api_key``. ``enabled_models`` is the sole
JSON-string ⇄ ``list[str]`` boundary (``json.dumps`` on set, decode in the
mapper).

Import direction (cycle avoidance): the shared ``$ENV`` resolver lives in
``app.services.secrets`` and imports :class:`LlmServerError` **from this module**;
this module does **not** import ``secrets`` (step-002 functions never resolve a
key). Step 003's probe adds a function-local ``from app.services import secrets``
to keep the module graph acyclic.

Skeleton (step 002): signatures + the error taxonomy + the backend-type constant
are frozen; the function bodies are UNIMPLEMENTED.
"""

import enum
import json
from datetime import datetime, timezone

import aiohttp
from llm import LLMClient, LLMError, LlamaSwapAPIClient, OpenAIAPIClient

from app.db import llm_servers
from app.models.llm_server import LlmServer
from app.models.schemas.llm_servers import (
    CreateLlmServerRequest,
    EmbeddingConfigResponse,
    LlmServerResponse,
    LlmServersListResponse,
    UpdateLlmServerRequest,
)

# D2 — the valid backend types, validated at the service level (not a DB/Pydantic
# enum). The frontend mirrors this as a TS union; keep the two lists in agreement.
_VALID_BACKEND_TYPES: set[str] = {"llama-swap", "openai"}


class LlmServerErrorReason(str, enum.Enum):
    """Discriminator for :class:`LlmServerError` — the LLM-server refusal taxonomy.

    Frozen here (shared across steps 002/003/004). Step 004's route maps each case
    to its HTTP status (D7): ``invalid_backend_type`` → 400, ``missing_field`` →
    400, ``not_found`` → 404, ``env_not_set`` → 400, ``probe_failed`` → 502.

    ``env_not_set`` is raised from :func:`app.services.secrets.resolve_env_ref`;
    ``probe_failed`` is raised by step 003's probe. This step raises
    ``invalid_backend_type`` / ``missing_field`` / ``not_found``.
    """

    invalid_backend_type = "invalid-backend-type"
    missing_field = "missing-field"
    not_found = "not-found"
    env_not_set = "env-not-set"
    probe_failed = "probe-failed"


class LlmServerError(Exception):
    """Raised by the LLM-server service (and ``secrets``) for every domain refusal.

    Carries a :class:`LlmServerErrorReason` discriminator (``reason``) plus a
    human-readable ``message``; step 004's route branches on ``reason`` to pick
    the status (D7). Mirrors :class:`app.services.admin.AdminError` (feature 005).
    """

    def __init__(self, reason: LlmServerErrorReason, message: str = "") -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


def _to_response(server: LlmServer) -> LlmServerResponse:
    """Map an ``LlmServer`` to a :class:`LlmServerResponse` by hand (never dump the ORM).

    Computes ``has_api_key = api_key is not None and api_key != ""`` (D3), decodes
    ``enabled_models`` JSON to ``list[str]``, and copies only non-secret fields —
    never exposing ``api_key`` (US-021.AC-2).
    """
    return LlmServerResponse(
        id=str(server.id),
        name=server.name,
        backend_type=server.backend_type,
        base_url=server.base_url,
        has_api_key=server.api_key is not None and server.api_key != "",
        enabled_models=json.loads(server.enabled_models),
        is_active=server.is_active,
        is_embedding=server.is_embedding,
        embedding_model=server.embedding_model,
        created_at=server.created_at,
        modified_at=server.modified_at,
    )


async def get_all_servers() -> LlmServersListResponse:
    """Return every server (via ``llm_servers.get_all``) mapped to
    :class:`LlmServerResponse`, ordered by name, wrapped in a
    :class:`LlmServersListResponse` (US-010)."""
    servers = await llm_servers.get_all()
    return LlmServersListResponse(items=[_to_response(s) for s in servers])


async def get_server(server_id: int) -> LlmServerResponse:
    """Return one server's :class:`LlmServerResponse`.

    Fetches via ``llm_servers.get_by_id``; a missing target raises
    :class:`LlmServerError` with the ``not_found`` case (D7)."""
    server = await llm_servers.get_by_id(server_id)
    if server is None:
        raise LlmServerError(LlmServerErrorReason.not_found, "Server not found.")
    return _to_response(server)


async def create_server(req: CreateLlmServerRequest) -> LlmServerResponse:
    """Create a new server and return its :class:`LlmServerResponse`.

    Validates required fields non-empty (:class:`LlmServerError` ``missing_field``,
    US-010.AC-3) and ``backend_type`` ∈ ``_VALID_BACKEND_TYPES``
    (:class:`LlmServerError` ``invalid_backend_type``, US-010.AC-2), sets
    ``created_at`` / ``modified_at``, persists via ``llm_servers.create``
    (US-010.AC-1)."""
    if not (isinstance(req.name, str) and req.name != ""):
        raise LlmServerError(LlmServerErrorReason.missing_field, "name is required.")
    if not (isinstance(req.backend_type, str) and req.backend_type != ""):
        raise LlmServerError(
            LlmServerErrorReason.missing_field, "backend_type is required."
        )
    if not (isinstance(req.base_url, str) and req.base_url != ""):
        raise LlmServerError(
            LlmServerErrorReason.missing_field, "base_url is required."
        )
    if req.backend_type not in _VALID_BACKEND_TYPES:
        raise LlmServerError(
            LlmServerErrorReason.invalid_backend_type,
            f"Unknown backend type '{req.backend_type}'.",
        )

    now = datetime.now(timezone.utc)
    server = LlmServer(
        name=req.name,
        backend_type=req.backend_type,
        base_url=req.base_url,
        api_key=req.api_key,
        enabled_models="[]",
        is_active=req.is_active,
        created_at=now,
        modified_at=now,
    )
    server = await llm_servers.create(server)
    return _to_response(server)


async def update_server(
    server_id: int, req: UpdateLlmServerRequest
) -> LlmServerResponse:
    """Partial-update a server and return its :class:`LlmServerResponse`.

    Fetches the target (:class:`LlmServerError` ``not_found``); applies only
    provided fields; ``api_key == ""`` clears the key to ``None`` while omitted /
    ``None`` leaves it unchanged; re-validates ``backend_type`` if provided
    (``invalid_backend_type``); bumps ``modified_at``; persists via
    ``llm_servers.update`` (which returns ``None`` — re-read if a fresh row is
    needed) (US-013.AC-1)."""
    server = await llm_servers.get_by_id(server_id)
    if server is None:
        raise LlmServerError(LlmServerErrorReason.not_found, "Server not found.")

    if req.name is not None:
        server.name = req.name
    if req.base_url is not None:
        server.base_url = req.base_url
    if req.is_active is not None:
        server.is_active = req.is_active
    if req.backend_type is not None:
        if req.backend_type not in _VALID_BACKEND_TYPES:
            raise LlmServerError(
                LlmServerErrorReason.invalid_backend_type,
                f"Unknown backend type '{req.backend_type}'.",
            )
        server.backend_type = req.backend_type
    if req.api_key is not None:
        server.api_key = None if req.api_key == "" else req.api_key

    server.modified_at = datetime.now(timezone.utc)
    await llm_servers.update(server)
    return _to_response(server)


async def delete_server(server_id: int) -> None:
    """Delete a server via ``llm_servers.delete``.

    A ``False`` return (no row matched) raises :class:`LlmServerError` with the
    ``not_found`` case (D7)."""
    if not await llm_servers.delete(server_id):
        raise LlmServerError(LlmServerErrorReason.not_found, "Server not found.")


async def set_enabled_models(
    server_id: int, models: list[str]
) -> LlmServerResponse:
    """Persist the enabled-models subset and return the response.

    Fetches the target (:class:`LlmServerError` ``not_found``), ``json.dumps`` the
    given subset into ``enabled_models``, persists, and returns the response whose
    ``enabled_models`` is the decoded ``list[str]`` (US-012.AC-1)."""
    server = await llm_servers.get_by_id(server_id)
    if server is None:
        raise LlmServerError(LlmServerErrorReason.not_found, "Server not found.")

    server.enabled_models = json.dumps(models)
    await llm_servers.update(server)
    return _to_response(server)


async def set_embedding_server(server_id: int, model: str) -> LlmServerResponse:
    """Designate ``server_id`` + ``model`` as the embedding provider.

    Fetches the target (:class:`LlmServerError` ``not_found``), calls
    ``llm_servers.clear_all_embedding()`` then sets ``is_embedding=True`` +
    ``embedding_model=model`` on the target and persists — clear-all-then-set so
    exactly one row stays flagged (D5, US-014.AC-1/AC-2)."""
    server = await llm_servers.get_by_id(server_id)
    if server is None:
        raise LlmServerError(LlmServerErrorReason.not_found, "Server not found.")

    await llm_servers.clear_all_embedding()
    server.is_embedding = True
    server.embedding_model = model
    await llm_servers.update(server)
    return _to_response(server)


async def clear_embedding_server() -> None:
    """Clear the embedding designation on every server via
    ``llm_servers.clear_all_embedding()`` (US-014 clear path)."""
    await llm_servers.clear_all_embedding()


async def get_embedding_config() -> EmbeddingConfigResponse:
    """Return the current :class:`EmbeddingConfigResponse`.

    From ``llm_servers.get_embedding_server``; when no server is designated,
    returns the all-``None`` indicator (``has_api_key`` false). ``has_api_key`` is
    masked — never the key (US-014.AC-1)."""
    server = await llm_servers.get_embedding_server()
    if server is None:
        return EmbeddingConfigResponse(
            server_id=None,
            server_name=None,
            base_url=None,
            backend_type=None,
            model=None,
            has_api_key=False,
        )
    return EmbeddingConfigResponse(
        server_id=str(server.id),
        server_name=server.name,
        base_url=server.base_url,
        backend_type=server.backend_type,
        model=server.embedding_model,
        has_api_key=server.api_key is not None and server.api_key != "",
    )


def _construct_client(
    server: LlmServer, resolved_key: str | None, model: str
) -> LLMClient:
    """The single ``backend_type`` → client-class branch (the ``"openai"`` /
    ``"llama-swap"`` mapping lives here and nowhere else).

    ``"openai"`` → :class:`OpenAIAPIClient`, otherwise :class:`LlamaSwapAPIClient`,
    each with ``model``, ``base_url=server.base_url`` and
    ``bearer_token=resolved_key``. Shared by :func:`_create_client` (``model=""``,
    for ``list_models``) and :func:`create_model_client` (a real chat model) so the
    stored-value translation is written once (feature 011, step 003 — Interface
    intent: "reuse its ``backend_type`` branch").
    """
    if server.backend_type == "openai":
        return OpenAIAPIClient(
            model=model, base_url=server.base_url, bearer_token=resolved_key
        )
    return LlamaSwapAPIClient(
        model=model, base_url=server.base_url, bearer_token=resolved_key
    )


def _create_client(server: LlmServer, resolved_key: str | None) -> LLMClient:
    """Construct the ``llm`` client for ``server`` given its already-resolved key (D4/D8).

    Private construction seam — **tests monkeypatch this** so no real ``llm``
    library / network is touched. ``resolved_key`` is passed in explicitly (never
    resolved inside) so a fake client can capture exactly what flows toward it
    (US-021.AC-1). Hardcodes ``model=""`` because it exists only to serve
    ``list_models()``. Name / signature / behaviour are **frozen** — this is the
    monkeypatch seam the LLM-server tests bind to.
    """
    return _construct_client(server, resolved_key, model="")


def create_model_client(
    server: LlmServer, resolved_key: str | None, model: str
) -> LLMClient:
    """Construct a **model-bound** ``llm`` client for a chat turn (feature 011,
    step 003).

    The chat-turn sibling of :func:`_create_client`: same
    ``backend_type`` → client-class mapping (via :func:`_construct_client`) but
    bound to a real ``model`` rather than ``""``. ``resolved_key`` is the already
    ``$ENV``-resolved api key (via :func:`app.services.secrets.resolve_env_ref`),
    passed in so a fake client can capture it.

    The returned :class:`~llm.LLMClient` MUST be used as an **async context
    manager** — it exposes ``__aenter__`` / ``__aexit__`` (which open/close its
    internal ``aiohttp.ClientSession``) and **no standalone ``close()``**. Entering
    it in an ``async with`` is what closes the session on every path, including
    failure (``003.context.md`` → "The existing client construction path").

    """
    return _construct_client(server, resolved_key, model)


async def probe_models(server_id: int) -> list[str]:
    """Probe a server for the model ids it reports, sorted (D4/D8).

    Fetches the RAW server (with its ``api_key``) via ``llm_servers.get_by_id`` —
    not the masking ``get_server``; a missing target raises :class:`LlmServerError`
    ``not_found``. Resolves the ``api_key`` ``$ENV`` ref via a function-local
    ``secrets.resolve_env_ref`` **before** client construction so ``env_not_set``
    surfaces on its own (not folded into ``probe_failed``). Constructs the client
    via :func:`_create_client`, ``await``s ``list_models()``, and returns the ids
    **sorted**. The three failure modes around construction + listing —
    :class:`aiohttp.ClientError` (unreachable), :class:`LLMError` (HTTP/auth), and
    :class:`ValueError` (keyless OpenAI) — are re-raised as :class:`LlmServerError`
    ``probe_failed`` (returning no model list). Changes no server record.

    Skeleton (step 003): UNIMPLEMENTED.
    """
    server = await llm_servers.get_by_id(server_id)
    if server is None:
        raise LlmServerError(LlmServerErrorReason.not_found, "Server not found.")

    # Resolve the ``$ENV`` ref at use time, BEFORE the try — an unset env var
    # surfaces as ``env_not_set`` on its own, never folded into ``probe_failed``.
    from app.services import secrets

    resolved_key = secrets.resolve_env_ref(server.api_key)

    try:
        client = _create_client(server, resolved_key)
        models = await client.list_models()
        return sorted(models)
    except (aiohttp.ClientError, LLMError, ValueError) as exc:
        raise LlmServerError(
            LlmServerErrorReason.probe_failed,
            f"Failed to probe server '{server.name}': {exc}",
        ) from exc
