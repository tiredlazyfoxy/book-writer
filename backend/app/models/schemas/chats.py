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
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.codex_entry import CodexKind

# The vocabulary of things the working page's content pane can hold — the wire
# mirror of ``frontend/src/work/subject.ts:SubjectKind``, value for value
# (``frontend-workspace.md`` → "Content pane — subject and editability"). A
# **literal union, not a free string**: an unknown kind is a 422 at the schema
# boundary rather than a silently mode-less turn. ``services/assistant_runtime.py``
# maps these onto FEAT-020's modes (013 step 007).
SubjectKind = Literal[
    "book-state",
    "chapters",
    "chapter",
    "characters",
    "locations",
    "facts",
    "codex-entry",
    "variants",
    "chapter-variants",
    "chats",
]


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

    The three subject fields (013 step 007) carry the working page's content-pane
    subject so the turn can resolve a FEAT-020 mode
    (``services/assistant_runtime.py``). **All three are optional and default to
    absent**, so ``011.chat-panel``'s callers and tests keep working unchanged
    (DoD-13) — a body of ``{"prompt": "..."}`` is still a complete request.

    - ``subject_kind`` — which pane subject the author had open; the literal
      union :data:`SubjectKind`, never a free string.
    - ``subject_id`` — the subject's entity id **as a string** (ids are ``str`` on
      the wire). ``None`` for a list / book-state subject **and** for UC-076's
      blank codex entry, which has no row yet.
    - ``codex_kind`` — the kind of a blank codex entry. Only consulted when the
      subject is a codex entry with **no** ``subject_id``: for an existing entry
      the stored row's ``kind`` wins and this field is ignored
      (``context.md`` → the shared-canvas design, point 1).
    """

    prompt: str | None = None
    subject_kind: SubjectKind | None = None
    subject_id: str | None = None
    codex_kind: CodexKind | None = None


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


# Which part of the content-pane subject a canvas write targets. A **constrained
# literal, never a free string** (the :data:`SubjectKind` discipline): a codex
# character or location entry has both a ``name`` and a ``body``, so the frame —
# and the tool argument that produces it — must say which one it carries, and an
# unknown value is refused at the schema boundary rather than silently applied to
# the wrong field. Shared by :class:`CanvasFrame` and
# ``services/codex_tools.py:WriteCodexDraftArgs`` so the wire vocabulary and the
# model-facing vocabulary can never drift apart.
CanvasField = Literal["name", "body"]


class CanvasFrame(BaseModel):
    """``data:`` payload of a ``canvas`` SSE frame — the assistant's draft for the
    subject open in the working page's content pane (013 step 010, UC-076 /
    UC-077; ``013.codex/context.md`` → "The shared-canvas write design" point 3).

    The fifth frame kind, beside ``thinking`` / ``delta`` / ``done`` / ``error``.
    ``routes/chats.py``'s serializer is generic over the event name, so this frame
    reaches the client with **no route change**; the client dispatches it to the
    registered canvas target by ``(subject_kind, subject_id)``
    (``context.md`` point 4).

    - ``subject_kind`` — which pane subject the draft is for, the
      :data:`SubjectKind` literal union (this step emits only ``"codex-entry"``;
      the field is the general protocol's, so a later chapter canvas needs no new
      frame).
    - ``subject_id`` — that subject's entity id **as a string**, or ``None`` for
      UC-076's blank entry, which has no row yet. Required-but-nullable: an
      omitted id must never be mistaken for a blank entry.
    - ``field`` — which part of the subject the ``text`` is
      (:data:`CanvasField`).
    - ``text`` — the draft itself, whole. It arrives in **one** frame, not
      streamed token by token: ``chat_with_tools`` hands a tool its arguments only
      once the model has finished emitting them (``context.md`` point 6 —
      token-level canvas streaming is the later manual-loop swap).

    **Nothing about this frame persists.** There is no code path from a chat to
    the ``codex_entries`` table at all; the author hand-edits if they wish and
    saves through the ordinary UC-069 / UC-070 endpoint (``context.md`` point 5,
    which is what makes US-086.AC-2 / US-087.AC-2 / US-088.AC-2 true by
    construction).
    """

    subject_kind: SubjectKind
    subject_id: str | None
    field: CanvasField
    text: str
