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
    UpdateChatRequest,
)
from app.services import authz


class ChatErrorReason(str, enum.Enum):
    """Discriminator for :class:`ChatError` — the chat refusal taxonomy.

    The route maps each case to its HTTP status: ``chat_not_found`` → 404, and
    every validation reason (``invalid_model_pair`` / ``unknown_or_inactive_server``
    / ``model_not_enabled`` / ``invalid_sampling``) → 400. Mirrors the shape of
    :class:`app.services.llm_servers.LlmServerErrorReason`.
    """

    chat_not_found = "chat-not-found"
    invalid_model_pair = "invalid-model-pair"
    unknown_or_inactive_server = "unknown-or-inactive-server"
    model_not_enabled = "model-not-enabled"
    invalid_sampling = "invalid-sampling"


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
    )


def _to_message_response(message: ChatMessage) -> ChatMessageResponse:
    """Map a ``ChatMessage`` row to a :class:`ChatMessageResponse` by hand. Ids
    stringified; nullable ``reasoning`` passed through.

    Skeleton (011 step 001): UNIMPLEMENTED.
    """
    return ChatMessageResponse(
        id=str(message.id),
        chat_id=str(message.chat_id),
        role=message.role,
        content=message.content,
        reasoning=message.reasoning,
        position=message.position,
        created_at=message.created_at,
    )


def _parse_chat_id(chat_id: str) -> int:
    """Coerce a wire ``chat_id`` string to ``int``; a non-numeric id is treated as
    a missing chat (``chat_not_found`` → 404, never 403 — US-061.AC-1)."""
    try:
        return int(chat_id)
    except (ValueError, TypeError):
        raise ChatError(ChatErrorReason.chat_not_found, "Chat not found.")


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
