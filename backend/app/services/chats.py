"""Chat service — chat CRUD, the model-pair / sampling validation, and the
single place the chat privacy rule lives (feature 011, step 001).

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). All persistence goes through the session-free
``app.db.chats`` / ``app.db.chat_messages`` / ``app.db.llm_servers`` layers
(namespace imports). Domain refusals raise the typed :class:`ChatError`,
discriminated by :class:`ChatErrorReason` so the route maps each case to its HTTP
status; the route stays HTTP-only.

**The privacy rule (US-061.AC-1).** A chat is reachable only by its author:
:func:`_resolve_owned_chat` requires ``book`` membership (already proven by the
``book_access`` dependency) **and** ``Chat.author_id == access.user_id``. A chat
belonging to another author answers the ``not_found`` reason → **404, not 403** —
a 403 would confirm the chat exists, which US-061.AC-1 forbids. Every ownership
path goes through this resolver. The rule is **not** a ``Capability`` /
``_CAPABILITY_MATRIX`` entry — that table maps capability → roles and has no
notion of row ownership (``context.md`` → "The chat privacy rule").

**Model-options secret rule.** :func:`list_model_options` reads active servers
through ``db.llm_servers`` directly (not ``services/llm_servers.get_server()``,
which masks the api key) and flattens each server's ``enabled_models`` JSON —
**no api key, masked or otherwise, appears in the response** (the ``probe_models``
bypass precedent).

Skeleton (011 step 001): the error taxonomy, the function signatures, and the
private helpers are frozen; every function body is UNIMPLEMENTED.
"""

import enum
import json
from datetime import datetime, timezone

from app.db import chat_messages, chats, llm_servers
from app.ids import generate_id
from app.models.chat import Chat, ChatMessage
from app.models.schemas.chats import (
    ChatDetailResponse,
    ChatListResponse,
    ChatMessageResponse,
    ChatResponse,
    ChatSamplingParams,
    CreateChatRequest,
    ModelOptionListResponse,
    ModelOptionResponse,
    ToolTrace,
    UpdateChatRequest,
)
from app.services import authz


class ChatErrorReason(str, enum.Enum):
    """Discriminator for :class:`ChatError` — the chat refusal taxonomy.

    The route maps each case to its HTTP status: ``chat_not_found`` → 404, and
    every validation reason (``invalid_model_pair`` / ``unknown_or_inactive_server``
    / ``model_not_enabled`` / ``invalid_sampling``) → 400. Mirrors the shape of
    :class:`app.services.llm_servers.LlmServerErrorReason`.

    Side chats (027, FEAT-022; ``context.md`` → D-D): ``side_chat_already_active``
    → 409 (start while the pointer is set), ``side_chat_not_found`` → 404 (an id
    neither the pointer nor carried by any row, or a non-numeric wire id — never
    a 422), ``side_chat_not_active`` → 409 (finish on a finished side chat).
    """

    chat_not_found = "chat-not-found"
    invalid_model_pair = "invalid-model-pair"
    unknown_or_inactive_server = "unknown-or-inactive-server"
    model_not_enabled = "model-not-enabled"
    invalid_sampling = "invalid-sampling"
    side_chat_already_active = "side-chat-already-active"
    side_chat_not_found = "side-chat-not-found"
    side_chat_not_active = "side-chat-not-active"


class ChatError(Exception):
    """Raised by the chat service for every domain refusal.

    Carries a :class:`ChatErrorReason` discriminator (``reason``) plus a
    human-readable ``message``; the route branches on ``reason`` to pick the
    status. Mirrors :class:`app.services.llm_servers.LlmServerError`.
    """

    def __init__(self, reason: ChatErrorReason, message: str = "") -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


def _parse_sampling(raw: str) -> ChatSamplingParams:
    """Parse a stored ``sampling_params`` JSON string through
    :class:`ChatSamplingParams`. A value that no longer parses falls back to the
    default :class:`ChatSamplingParams` rather than failing the read (DoD-7).

    Skeleton (011 step 001): UNIMPLEMENTED.
    """
    try:
        return ChatSamplingParams.model_validate_json(raw)
    except (ValueError, TypeError):
        return ChatSamplingParams()


def _to_chat_response(chat: Chat) -> ChatResponse:
    """Map a ``Chat`` row to a :class:`ChatResponse` by hand (never dump the ORM).
    Ids stringified; ``sampling`` parsed via :func:`_parse_sampling`.

    Skeleton (011 step 001): UNIMPLEMENTED.
    """
    return ChatResponse(
        id=str(chat.id),
        book_id=str(chat.book_id),
        author_id=str(chat.author_id),
        title=chat.title,
        llm_server_id=(
            str(chat.llm_server_id) if chat.llm_server_id is not None else None
        ),
        model_name=chat.model_name,
        sampling=_parse_sampling(chat.sampling_params),
        archived=chat.archived,
        created_at=chat.created_at,
        modified_at=chat.modified_at,
        active_side_chat_id=(
            str(chat.active_side_chat_id)
            if chat.active_side_chat_id is not None
            else None
        ),
    )


def _to_message_response(message: ChatMessage) -> ChatMessageResponse:
    """Map a ``ChatMessage`` row to a :class:`ChatMessageResponse` by hand. Ids
    stringified; nullable ``reasoning`` passed through.

    ``tool_trace`` (024) is read through :meth:`ToolTrace.parse_column`, the
    column's only reader — ``None`` stays ``None``. This mapper is what carries
    the persisted trace back to the client after the pane discards its live
    buffers and re-reads the chat, so it is the same call that serves the ``done``
    frame's DTO and the reload.
    """
    return ChatMessageResponse(
        id=str(message.id),
        chat_id=str(message.chat_id),
        role=message.role,
        content=message.content,
        reasoning=message.reasoning,
        position=message.position,
        created_at=message.created_at,
        side_chat_id=(
            str(message.side_chat_id) if message.side_chat_id is not None else None
        ),
        tool_trace=ToolTrace.parse_column(message.tool_trace),
    )


def _parse_chat_id(chat_id: str) -> int:
    """Coerce a wire ``chat_id`` string to ``int``; a non-numeric id is treated as
    a missing chat (``chat_not_found`` → 404, never 403 — US-061.AC-1)."""
    try:
        return int(chat_id)
    except (ValueError, TypeError):
        raise ChatError(ChatErrorReason.chat_not_found, "Chat not found.")


def _parse_side_chat_id(side_chat_id: str) -> int:
    """Coerce a wire ``side_chat_id`` string to ``int``; a non-numeric id is
    treated as a missing side chat (``side_chat_not_found`` → 404, never a 422 —
    the codex ``entry_not_found`` precedent; 027 D-D). The :func:`_parse_chat_id`
    twin; step 003's inject / delete reuse it.
    """
    try:
        return int(side_chat_id)
    except (ValueError, TypeError):
        raise ChatError(ChatErrorReason.side_chat_not_found, "Side chat not found.")


async def _validate_model_pair(
    llm_server_id: str | None, model_name: str | None
) -> int | None:
    """Validate the (server, model) pair and return the resolved integer server id
    (or ``None`` when both are unset).

    Both-null and both-set are accepted; a half-set pair raises
    ``invalid_model_pair``. A set pair must name an **active** server
    (``unknown_or_inactive_server``) whose ``enabled_models`` contains the model
    (``model_not_enabled``)."""
    if (llm_server_id is None) != (model_name is None):
        raise ChatError(
            ChatErrorReason.invalid_model_pair,
            "llm_server_id and model_name must both be set or both be null.",
        )
    if llm_server_id is None:
        return None
    try:
        server_id = int(llm_server_id)
    except (ValueError, TypeError):
        raise ChatError(
            ChatErrorReason.unknown_or_inactive_server,
            f"Unknown server '{llm_server_id}'.",
        )
    server = await llm_servers.get_by_id(server_id)
    if server is None or not server.is_active:
        raise ChatError(
            ChatErrorReason.unknown_or_inactive_server,
            "Server is unknown or inactive.",
        )
    if model_name not in json.loads(server.enabled_models):
        raise ChatError(
            ChatErrorReason.model_not_enabled,
            f"Model '{model_name}' is not enabled on this server.",
        )
    return server_id


async def _resolve_owned_chat(access: authz.BookAccess, chat_id: int) -> Chat:
    """Return the ``Chat`` for ``chat_id`` only when it belongs to
    ``access.book_id`` **and** ``author_id == access.user_id``; otherwise raise
    :class:`ChatError` with the ``chat_not_found`` reason (→ 404, never 403 —
    US-061.AC-1). Every ownership path routes through this helper.

    Skeleton (011 step 001): UNIMPLEMENTED.
    """
    chat = await chats.get_by_id(chat_id)
    if (
        chat is None
        or chat.book_id != access.book_id
        or chat.author_id != access.user_id
    ):
        raise ChatError(ChatErrorReason.chat_not_found, "Chat not found.")
    return chat


async def create_chat(
    access: authz.BookAccess, req: CreateChatRequest
) -> ChatResponse:
    """Create a chat owned by ``access.user_id`` in ``access.book_id`` and return
    its :class:`ChatResponse`.

    Validates the model pair (both-null or both-set; a half-set pair raises
    ``invalid_model_pair``); a set pair must name an **active** server
    (``unknown_or_inactive_server``) whose ``enabled_models`` contains the model
    (``model_not_enabled``). Serializes the sampling object to JSON and stores the
    row with no subject/chapter/codex binding (UC-053, US-056.AC-1).

    Skeleton (011 step 001): UNIMPLEMENTED.
    """
    server_id = await _validate_model_pair(req.llm_server_id, req.model_name)
    sampling = req.sampling if req.sampling is not None else ChatSamplingParams()
    now = datetime.now(timezone.utc)
    chat = Chat(
        book_id=access.book_id,
        author_id=access.user_id,
        title=req.title if req.title else "New chat",
        llm_server_id=server_id,
        model_name=req.model_name,
        sampling_params=sampling.model_dump_json(),
        archived=False,
        created_at=now,
        modified_at=now,
    )
    chat = await chats.create(chat)
    return _to_chat_response(chat)


async def list_chats(
    access: authz.BookAccess, archived: bool
) -> ChatListResponse:
    """Return the caller's own chats in ``access.book_id`` filtered by
    ``archived``, most-recently-modified first (US-095.AC-1). Another author's
    chats never appear.

    Skeleton (011 step 001): UNIMPLEMENTED.
    """
    rows = await chats.list_by_book_and_author(
        access.book_id, access.user_id, archived
    )
    return ChatListResponse(items=[_to_chat_response(c) for c in rows])


async def get_chat(
    access: authz.BookAccess, chat_id: str
) -> ChatDetailResponse:
    """Return the owned chat plus its ``position``-ordered messages (UC-081,
    US-095.AC-2) via :func:`_resolve_owned_chat`.

    Skeleton (011 step 001): UNIMPLEMENTED.
    """
    chat = await _resolve_owned_chat(access, _parse_chat_id(chat_id))
    messages = await chat_messages.list_by_chat_ordered(chat.id)
    return ChatDetailResponse(
        chat=_to_chat_response(chat),
        messages=[_to_message_response(m) for m in messages],
    )


async def update_chat(
    access: authz.BookAccess, chat_id: str, req: UpdateChatRequest
) -> ChatResponse:
    """Apply whichever of title / archived / model pair / sampling was sent to the
    owned chat, under the same pair and sampling validation as create, and return
    its refreshed :class:`ChatResponse`. This is the archive (UC-082), restore
    (US-096.AC-2) and settings-edit path.

    Skeleton (011 step 001): UNIMPLEMENTED.
    """
    chat = await _resolve_owned_chat(access, _parse_chat_id(chat_id))
    if req.title is not None:
        chat.title = req.title
    if req.archived is not None:
        chat.archived = req.archived
    if req.llm_server_id is not None or req.model_name is not None:
        chat.llm_server_id = await _validate_model_pair(
            req.llm_server_id, req.model_name
        )
        chat.model_name = req.model_name
    if req.sampling is not None:
        chat.sampling_params = req.sampling.model_dump_json()
    chat = await chats.update(chat)
    return _to_chat_response(chat)


async def start_side_chat(access: authz.BookAccess, chat_id: str) -> ChatResponse:
    """Open a side chat on the owned chat and return its refreshed
    :class:`ChatResponse` with ``active_side_chat_id`` set (UC-110, US-141.AC-1;
    027 D-D).

    Resolves the chat through :func:`_resolve_owned_chat` (missing / other book /
    other author → ``chat_not_found`` → 404, never 403). Refuses with
    ``side_chat_already_active`` (409) when ``Chat.active_side_chat_id`` is
    already non-null (US-135.AC-2). Otherwise mints a new id with
    ``app.ids.generate_id()`` **in this service** — no row exists for a side
    chat, so no model ``default_factory`` can mint it — sets the pointer, persists
    through ``db/chats.update`` (which bumps ``modified_at``) and maps the row.
    **Allowed on a chat with zero messages** (UC-110 alternate flow). Touches no
    message row.
    """
    chat = await _resolve_owned_chat(access, _parse_chat_id(chat_id))
    if chat.active_side_chat_id is not None:
        raise ChatError(
            ChatErrorReason.side_chat_already_active,
            "A side chat is already active on this chat.",
        )
    chat.active_side_chat_id = generate_id()
    chat = await chats.update(chat)
    return _to_chat_response(chat)


async def finish_side_chat(
    access: authz.BookAccess, chat_id: str, side_chat_id: str
) -> ChatResponse:
    """Close the active side chat on the owned chat and return its refreshed
    :class:`ChatResponse` with ``active_side_chat_id`` cleared (UC-111,
    US-137.AC-1, US-138.AC-2; 027 D-D).

    Resolves the chat through :func:`_resolve_owned_chat` (→ ``chat_not_found``,
    404). Parses ``side_chat_id`` with :func:`_parse_side_chat_id` (non-numeric →
    ``side_chat_not_found``, 404). Existence is **pointer first, rows second**:
    the id exists iff ``chat.active_side_chat_id == sid`` **or**
    ``chat_messages.side_chat_exists(chat.id, sid)`` — so an active side chat with
    zero rows finishes cleanly. An id that exists nowhere → ``side_chat_not_found``
    (404); one carried by rows but not the pointer (a finished side chat) →
    ``side_chat_not_active`` (409). Otherwise clears the pointer, persists through
    ``db/chats.update`` and maps the row. **Touches no message row** — the rows
    keep their ``side_chat_id``; "finished" is derived (D-A).
    """
    chat = await _resolve_owned_chat(access, _parse_chat_id(chat_id))
    sid = _parse_side_chat_id(side_chat_id)
    if chat.active_side_chat_id == sid:
        chat.active_side_chat_id = None
        chat = await chats.update(chat)
        return _to_chat_response(chat)
    if await chat_messages.side_chat_exists(chat.id, sid):
        raise ChatError(
            ChatErrorReason.side_chat_not_active,
            "This side chat is not the active one.",
        )
    raise ChatError(ChatErrorReason.side_chat_not_found, "Side chat not found.")


async def inject_side_chat(
    access: authz.BookAccess, chat_id: str, side_chat_id: str
) -> ChatDetailResponse:
    """Inject a side chat into the main line of the owned chat and return the
    refreshed :class:`ChatDetailResponse` (UC-112, US-139.AC-1; 027 D-D).

    Resolves the chat through :func:`_resolve_owned_chat` (missing / other book /
    other author → ``chat_not_found``, 404). Parses ``side_chat_id`` with
    :func:`_parse_side_chat_id` (non-numeric → ``side_chat_not_found``, 404).
    Existence is checked **before** any mutation, pointer first, rows second: the
    id exists iff ``chat.active_side_chat_id == sid`` **or**
    ``chat_messages.side_chat_exists(chat.id, sid)``; otherwise
    ``side_chat_not_found`` (404). Then ``chat_messages.clear_side_chat(chat.id,
    sid)`` — the rows become ordinary main-line rows **in place**: ``side_chat_id``
    set ``NULL``, ``position`` and relative order untouched (one-way; product C6).
    Clears ``Chat.active_side_chat_id`` **only if** it equalled ``sid``, and
    persists through ``db/chats.update`` **in every case** — a finished side chat's
    pointer does not move, but ``modified_at`` must still bump (D-D). An active
    side chat with zero rows just clears the pointer (``clear_side_chat`` → ``0``
    is not a 404 signal). Returns exactly what :func:`get_chat` returns — the chat
    plus **all** rows in ``position`` order, through the same mapping.
    """
    chat = await _resolve_owned_chat(access, _parse_chat_id(chat_id))
    sid = _parse_side_chat_id(side_chat_id)
    was_active = chat.active_side_chat_id == sid
    if not was_active and not await chat_messages.side_chat_exists(chat.id, sid):
        raise ChatError(ChatErrorReason.side_chat_not_found, "Side chat not found.")
    await chat_messages.clear_side_chat(chat.id, sid)
    if was_active:
        chat.active_side_chat_id = None
    await chats.update(chat)
    return await get_chat(access, chat_id)


async def delete_side_chat(
    access: authz.BookAccess, chat_id: str, side_chat_id: str
) -> None:
    """Permanently delete a side chat's rows from the owned chat (UC-113,
    US-140.AC-3, US-140.AC-4; 027 D-D). Returns nothing — the route answers 204.

    Same resolution and existence check as :func:`inject_side_chat`
    (``chat_not_found`` / ``side_chat_not_found`` → 404, checked **before** any
    mutation). Then ``chat_messages.delete_by_side_chat(chat.id, sid)`` — the
    chat family's **first hard delete**, sanctioned by D-D (the second exception
    to archive-only after FEAT-011's destroy; see the ``db/chat_messages.py``
    module docstring). Writes **no table other than ``chat_messages``** (plus the
    ``chats`` pointer): a codex entry, chapter change or memo saved during the
    side chat is untouched. Surviving rows are **not renumbered** — gaps in
    ``position`` are tolerated by ``next_position`` (max+1). Clears
    ``Chat.active_side_chat_id`` **only if** it equalled ``sid``, and persists
    through ``db/chats.update`` in every case so ``modified_at`` bumps. An active
    side chat with zero rows just clears the pointer (``delete_by_side_chat`` →
    ``0`` is not a 404 signal).
    """
    chat = await _resolve_owned_chat(access, _parse_chat_id(chat_id))
    sid = _parse_side_chat_id(side_chat_id)
    was_active = chat.active_side_chat_id == sid
    if not was_active and not await chat_messages.side_chat_exists(chat.id, sid):
        raise ChatError(ChatErrorReason.side_chat_not_found, "Side chat not found.")
    await chat_messages.delete_by_side_chat(chat.id, sid)
    if was_active:
        chat.active_side_chat_id = None
    await chats.update(chat)


async def list_model_options(access: authz.BookAccess) -> ModelOptionListResponse:
    """Return the selectable ``(server id, server name, model)`` triples flattened
    from **active** servers' ``enabled_models`` — read through ``db.llm_servers``
    directly so **no api key** appears in the response (UC-053 precondition,
    FEAT-004). Inactive servers contribute nothing.

    Skeleton (011 step 001): UNIMPLEMENTED.
    """
    servers = await llm_servers.get_active()
    items: list[ModelOptionResponse] = []
    for server in servers:
        for model in json.loads(server.enabled_models):
            items.append(
                ModelOptionResponse(
                    server_id=str(server.id),
                    server_name=server.name,
                    model_name=model,
                )
            )
    return ModelOptionListResponse(items=items)
