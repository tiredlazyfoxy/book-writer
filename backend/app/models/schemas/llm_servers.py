"""LLM-server request & response schemas (feature 006, step 002).

Declarative Pydantic schemas — the typed contracts for the admin LLM-server
surface (``/api/admin/llm-servers``, step 004). Plain typed data shapes, no logic
(see ``docs/architecture/backend.md`` — ``models/`` is tables + schemas only).

Secret masking (D3): the response DTOs carry **no** ``api_key`` field — only
``has_api_key: bool`` — and ``enabled_models`` is surfaced as a decoded
``list[str]`` (the JSON-string ⇄ list boundary is the service's job, never here).
Ids are surfaced as ``str`` (snowflake serialized as a string — 64-bit ids exceed
the JS safe-integer range, mirroring ``AdminUserResponse.id``).

Skeleton (step 002): field names/types are frozen.
"""

from datetime import datetime

from pydantic import BaseModel


class CreateLlmServerRequest(BaseModel):
    """Body of ``POST /api/admin/llm-servers`` — a new connection's fields.

    - ``name`` / ``backend_type`` / ``base_url`` — required, non-empty (validated
      service-side: missing-field / invalid-backend-type cases, D2).
    - ``api_key`` — optional; stored raw or as a ``"$ENV_VAR"`` token (D3).
    - ``is_active`` — selectable flag, default true.
    """

    name: str
    backend_type: str
    base_url: str
    api_key: str | None = None
    is_active: bool = True


class UpdateLlmServerRequest(BaseModel):
    """Body of the edit endpoint — **all fields optional** (partial update, D-lock).

    An omitted / ``None`` field leaves the stored value unchanged. The only place
    "absent" vs "empty" matters: ``api_key == ""`` clears the stored key to
    ``None``; ``api_key is None`` leaves it unchanged (US-013.AC-1).
    """

    name: str | None = None
    backend_type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    is_active: bool | None = None


class LlmServerResponse(BaseModel):
    """A single server as surfaced to an admin (list + mutation results).

    Secret-masking (D3/US-021): **no** ``api_key`` field; ``has_api_key`` is the
    service-computed ``api_key is not None and api_key != ""``. ``enabled_models``
    is the decoded ``list[str]``. Built by hand in the service mapper — never
    dumped from the ORM. ``id`` is a ``str`` (snowflake serialized as a string,
    mirroring ``AdminUserResponse.id``).
    """

    id: str
    name: str
    backend_type: str
    base_url: str
    has_api_key: bool
    enabled_models: list[str]
    is_active: bool
    is_embedding: bool
    embedding_model: str | None
    created_at: datetime | None
    modified_at: datetime | None


class LlmServersListResponse(BaseModel):
    """List envelope for ``GET /api/admin/llm-servers`` — servers ordered by name."""

    items: list[LlmServerResponse]


class AvailableModelsResponse(BaseModel):
    """Probe result (step 003 / D4) — the sorted model ids a server offers."""

    models: list[str]


class EnabledModelsRequest(BaseModel):
    """Body of the enable-models endpoint — the subset to persist (US-012)."""

    enabled_models: list[str]


class SetEmbeddingRequest(BaseModel):
    """Body of ``PUT /api/admin/llm-servers/{id}/embedding`` — the embedding model id."""

    model: str


class EmbeddingConfigResponse(BaseModel):
    """Current embedding designation (D5 / US-014).

    All descriptor fields are nullable: when no server is designated the service
    returns the all-``None`` indicator (``has_api_key`` false). ``server_id`` is a
    ``str`` (snowflake serialized as a string). ``has_api_key`` is masked — never
    the key.
    """

    server_id: str | None
    server_name: str | None
    base_url: str | None
    backend_type: str | None
    model: str | None
    has_api_key: bool
