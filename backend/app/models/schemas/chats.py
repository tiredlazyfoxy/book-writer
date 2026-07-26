"""Chat request & response schemas (feature 011, step 001).

Declarative Pydantic schemas — the typed contracts for the book-nested chat
surface (``/api/books/{book_id}/chats``). Plain typed data shapes, no logic
(see ``docs/architecture/backend.md`` — ``models/`` is tables + schemas only).

Conventions this file follows:

- **Ids are ``str``** on the wire (snowflakes exceed the JS safe-integer range,
  mirroring ``LlmServerResponse.id`` / ``AdminUserResponse.id``).
- **The model pair moves together** — ``llm_server_id`` + ``model_name`` are both
  nullable; validation that they are both-null or both-set is a service rule
  (``services/chats.py``), not modelled here.
- ``sampling`` is the typed :class:`ChatSamplingParams` gate over the ``Chat``
  table's ``sampling_params`` TEXT/JSON column — the **only** way the column is
  read or written (feature decision 5; the JSON-string boundary lives in the
  service mapper, never here).
- ``model_config = ConfigDict(protected_namespaces=())`` on every schema carrying
  a ``model_name`` field — silences Pydantic's ``model_``-namespace warning while
  keeping the field name aligned with the ``Chat`` / ``SubAgent`` columns.

Skeleton (011 step 001): field names / types / defaults are frozen. DTOs are
declarative — there is nothing to leave unimplemented.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatSamplingParams(BaseModel):
    """The typed gate over the ``Chat.sampling_params`` JSON/TEXT column.

    The nine llama.cpp sampling params plus ``enable_thinking``, with the
    feature's recommended defaults (``context.md`` → decision 6). ``max_tokens``
    and ``seed`` are optional-and-unset (``None``). This model is the sole reader
    and writer of the column: a stored value is parsed through it, a new value is
    serialized from it. Params the ``llm`` client's allowlist currently drops
    (``top_k`` / ``repeat_penalty`` / ``min_p``) are still stored and round-tripped
    (decision 5).
    """

    temperature: float = 0.8
    top_p: float = 0.95
    top_k: int = 40
    repeat_penalty: float = 1.1
    min_p: float = 0.05
    max_tokens: int | None = None
    seed: int | None = None
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    enable_thinking: bool = True


class CreateChatRequest(BaseModel):
    """Body of ``POST /api/books/{book_id}/chats`` — a new chat's fields.

    - ``title`` — optional; a service default applies when omitted.
    - ``llm_server_id`` / ``model_name`` — the optional model pair (both-null or
      both-set, validated service-side).
    - ``sampling`` — optional sampling overrides; when omitted the column defaults
      to the serialized default :class:`ChatSamplingParams`.
    """

    model_config = ConfigDict(protected_namespaces=())

    title: str | None = None
    llm_server_id: str | None = None
    model_name: str | None = None
    sampling: ChatSamplingParams | None = None


class UpdateChatRequest(BaseModel):
    """Body of ``PATCH /api/books/{book_id}/chats/{chat_id}`` — **all fields
    optional** so one body doubles as archive/restore and settings-edit.

    An omitted / ``None`` field leaves the stored value unchanged; ``archived``
    toggles the archive state; the model pair and ``sampling`` re-run the same
    validation as create.
    """

    model_config = ConfigDict(protected_namespaces=())

    title: str | None = None
    archived: bool | None = None
    llm_server_id: str | None = None
    model_name: str | None = None
    sampling: ChatSamplingParams | None = None


class ChatResponse(BaseModel):
    """A single chat as surfaced to its author (create / list / update results).

    Built by hand in the service mapper (never dumped from the ORM). Ids are
    ``str``; ``sampling`` is the parsed :class:`ChatSamplingParams`.
    """

    model_config = ConfigDict(protected_namespaces=())

    id: str
    book_id: str
    author_id: str
    title: str
    llm_server_id: str | None
    model_name: str | None
    sampling: ChatSamplingParams
    archived: bool
    created_at: datetime | None
    modified_at: datetime | None


class ChatListResponse(BaseModel):
    """List envelope for ``GET /api/books/{book_id}/chats`` — the caller's own
    chats, most-recently-modified first."""

    items: list[ChatResponse]


class ChatMessageResponse(BaseModel):
    """A single message within a chat. ``reasoning`` is the assistant's thinking
    (``None`` for user messages and assistants that produced none)."""

    id: str
    chat_id: str
    role: str
    content: str
    reasoning: str | None
    position: int
    created_at: datetime | None


class ChatMessageListResponse(BaseModel):
    """List envelope for a chat's messages, ordered by ``position`` ascending."""

    items: list[ChatMessageResponse]


class ChatDetailResponse(BaseModel):
    """Return of ``GET /api/books/{book_id}/chats/{chat_id}`` — the chat plus its
    position-ordered messages (the "chat + messages" fetch, DoD-4)."""

    chat: ChatResponse
    messages: list[ChatMessageResponse]


class ModelOptionResponse(BaseModel):
    """One selectable ``(server, model)`` option for the author's model picker —
    a server id + display name and one model enabled on it. **Never** carries an
    api key, raw or masked."""

    model_config = ConfigDict(protected_namespaces=())

    server_id: str
    server_name: str
    model_name: str


class ModelOptionListResponse(BaseModel):
    """List envelope for ``GET /api/books/{book_id}/chats/model-options`` — the
    flattened ``(server id, server name, model)`` triples from active servers."""

    items: list[ModelOptionResponse]


class TurnRequest(BaseModel):
    """Body of ``POST /api/books/{book_id}/chats/{chat_id}/turn`` — run one
    assistant turn.

    ``prompt`` is **optional**: when present it is persisted as a new ``"user"``
    message before the assistant runs; when **absent** (``None``) the turn is a
    **retry** — the assistant re-runs over the already-stored history and no new
    user message is written (``003.context.md`` → "Retry semantics").
    """

    prompt: str | None = None


class ThinkingFrame(BaseModel):
    """``data:`` payload of a ``thinking`` SSE frame — a chunk of reasoning text
    routed off the token stream by the think splitter."""

    text: str


class DeltaFrame(BaseModel):
    """``data:`` payload of a ``delta`` SSE frame — a chunk of assistant content
    text."""

    text: str


class DoneFrame(BaseModel):
    """``data:`` payload of the single terminal ``done`` SSE frame — the persisted
    assistant :class:`ChatMessageResponse` (content from the streamed content
    deltas, ``reasoning`` from the thinking deltas)."""

    message: ChatMessageResponse


class ErrorFrame(BaseModel):
    """``data:`` payload of the single terminal ``error`` SSE frame — an
    author-facing failure message. The user message stays stored; retry is
    offered (UC-056 / US-060)."""

    message: str
