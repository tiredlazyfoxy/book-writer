"""LlmServer table — an LLM backend connection (feature 006, step 001).

Declarative SQLModel table. No logic lives here (see ``docs/architecture/
backend.md`` — ``models/`` is tables + schemas only). The ``LlmServer`` class
registers on ``SQLModel.metadata`` at import time (via the ``db/engine.py``
registration hook).

Skeleton (step 001): the model shape is frozen. A table is a declarative type,
not behavior — there is nothing to leave unimplemented.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.ids import generate_id


class LlmServer(SQLModel, table=True):
    """A registered LLM server connection — the first ``llm``-client entity.

    Per feature 006 decision **D1** (single table, no companion tables):

    - ``id`` — application-generated 64-bit snowflake primary key (system-wide
      entity-id strategy, mirroring ``User``). Populated at construction via
      ``default_factory=generate_id`` *before* insert; surfaced as a ``str`` at
      the DTO edge (64-bit ids exceed the JS safe-integer range).
    - ``name`` — human-facing connection name.
    - ``backend_type`` — bare ``str`` (``"llama-swap" | "openai"``); validated at
      the service level, **not** a DB/Pydantic enum (D2).
    - ``base_url`` — base URL including the ``/v1`` segment (operator-supplied).
    - ``api_key`` — nullable; stored raw or as a ``"$ENV_VAR"`` token, resolved
      only at use time (D3). Never returned raw.
    - ``enabled_models`` — JSON-encoded ``list[str]`` in a TEXT column; defaults
      to the empty-list string ``"[]"``. Decoding is the service's job.
    - ``is_active`` — connection is selectable (default true).
    - ``is_embedding`` — this server is the designated embedding provider
      (default false); at most one row set, enforced clear-all-then-set (D5).
    - ``embedding_model`` — nullable model id on this server used for embeddings.
    - ``created_at`` / ``modified_at`` — nullable timestamps.
    """

    __tablename__ = "llm_servers"

    id: int = Field(default_factory=generate_id, primary_key=True)
    name: str
    backend_type: str
    base_url: str
    api_key: str | None = Field(default=None)
    enabled_models: str = "[]"
    is_active: bool = True
    is_embedding: bool = False
    embedding_model: str | None = Field(default=None)
    created_at: datetime | None = Field(default=None)
    modified_at: datetime | None = Field(default=None)
