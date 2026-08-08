"""Chat route layer for ``/api/books/{book_id}/chats`` (feature 011, step 001).

HTTP only: parse the request, call one :mod:`app.services.chats` function, map the
typed errors to a status, and return (see ``docs/architecture/backend.md`` — layer
separation; no business logic, no DB access here). Every endpoint is gated by
``access: authz.BookAccess = Depends(authz.book_access)`` — book membership (and
the 404-for-a-book-you-cannot-see rule) is resolved for free by the dependency;
the per-chat privacy rule lives one layer down in ``services/chats.py``.

Route ordering is load-bearing: FastAPI matches in declaration order, so the
static ``GET /{book_id}/chats/model-options`` route is declared **before** the
``/{book_id}/chats/{chat_id}`` param routes — otherwise ``model-options`` is
captured as a ``chat_id`` (the same rule ``routes/books.py`` documents for
``/shared``).

Typed-error → status map: ``chat_not_found`` → 404, every validation reason →
400; ``authz.BookAuthorizationError`` → 403.

Step 003 adds ``POST /{book_id}/chats/{chat_id}/turn`` to this same file — keep
the module open so appending it is a local change.

Skeleton (011 step 001): the router object, route registration, handler
signatures (``response_model`` via return annotations, the ``access`` dependency,
the 201 create status) and the error-mapping helpers are frozen; behavior lives in
the service, which is UNIMPLEMENTED.
"""

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.models.schemas.chats import (
    ChatDetailResponse,
    ChatListResponse,
    ChatResponse,
    ChatTitleResponse,
    CreateChatRequest,
    ModelOptionListResponse,
    TurnRequest,
    UpdateChatRequest,
)
from app.services import authz
from app.services import chat_titling
from app.services import chat_turn
from app.services import chats as chats_service
from app.services import llm_servers as llm_servers_service

router = APIRouter(prefix="/api/books", tags=["chats"])

_CHAT_ERROR_STATUS: dict[chats_service.ChatErrorReason, int] = {
    chats_service.ChatErrorReason.chat_not_found: status.HTTP_404_NOT_FOUND,
    chats_service.ChatErrorReason.invalid_model_pair: status.HTTP_400_BAD_REQUEST,
    chats_service.ChatErrorReason.unknown_or_inactive_server: (
        status.HTTP_400_BAD_REQUEST
    ),
    chats_service.ChatErrorReason.model_not_enabled: status.HTTP_400_BAD_REQUEST,
    chats_service.ChatErrorReason.invalid_sampling: status.HTTP_400_BAD_REQUEST,
}


def _map_chat_error(err: chats_service.ChatError) -> HTTPException:
    """Translate a typed :class:`~app.services.chats.ChatError` to an
    :class:`HTTPException` per the chat-error status map."""
    return HTTPException(
        status_code=_CHAT_ERROR_STATUS[err.reason],
        detail=err.message,
    )


def _map_authz_error(err: authz.BookAuthorizationError) -> HTTPException:
    """Translate a typed :class:`~app.services.authz.BookAuthorizationError` to a
    **403** :class:`HTTPException`. Existence-hiding 404s are produced upstream by
    the ``book_access`` resolver, not here."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(err),
    )


# The turn's pre-stream refusals may surface an unset-key-env
# :class:`~app.services.llm_servers.LlmServerError` (``env_not_set`` → 400) —
# mirrors ``routes/admin/llm_servers.py``'s decision-7 map.
_LLM_SERVER_ERROR_STATUS: dict[
    llm_servers_service.LlmServerErrorReason, int
] = {
    llm_servers_service.LlmServerErrorReason.missing_field: (
        status.HTTP_400_BAD_REQUEST
    ),
    llm_servers_service.LlmServerErrorReason.invalid_backend_type: (
        status.HTTP_400_BAD_REQUEST
    ),
    llm_servers_service.LlmServerErrorReason.env_not_set: (
        status.HTTP_400_BAD_REQUEST
    ),
    llm_servers_service.LlmServerErrorReason.not_found: (
        status.HTTP_404_NOT_FOUND
    ),
    llm_servers_service.LlmServerErrorReason.probe_failed: (
        status.HTTP_502_BAD_GATEWAY
    ),
}


def _map_llm_server_error(
    err: llm_servers_service.LlmServerError,
) -> HTTPException:
    """Translate a typed :class:`~app.services.llm_servers.LlmServerError` raised by
    the turn's pre-stream checks to an :class:`HTTPException` (decision-7 status
    map)."""
    return HTTPException(
        status_code=_LLM_SERVER_ERROR_STATUS[err.reason],
        detail=err.message,
    )


@router.get("/{book_id}/chats/model-options")
async def list_model_options(
    access: authz.BookAccess = Depends(authz.book_access),
) -> ModelOptionListResponse:
    """List the ``(server, model)`` picker options drawn from active servers
    (``GET /api/books/{book_id}/chats/model-options`` → 200, UC-053 precondition).
    Declared **before** the ``/chats/{chat_id}`` param routes so the static path
    wins."""
    try:
        return await chats_service.list_model_options(access)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chats_service.ChatError as err:
        raise _map_chat_error(err)


@router.post("/{book_id}/chats", status_code=status.HTTP_201_CREATED)
async def create_chat(
    payload: CreateChatRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChatResponse:
    """Create a chat owned by the caller (``POST /api/books/{book_id}/chats`` →
    201, UC-053 / US-056.AC-1)."""
    try:
        return await chats_service.create_chat(access, payload)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chats_service.ChatError as err:
        raise _map_chat_error(err)


@router.get("/{book_id}/chats")
async def list_chats(
    archived: bool = False,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChatListResponse:
    """List the caller's own chats, filtered by ``archived`` (default false)
    (``GET /api/books/{book_id}/chats`` → 200, UC-081 / US-095.AC-1)."""
    try:
        return await chats_service.list_chats(access, archived)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chats_service.ChatError as err:
        raise _map_chat_error(err)


@router.get("/{book_id}/chats/{chat_id}")
async def get_chat(
    chat_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChatDetailResponse:
    """Fetch an owned chat plus its position-ordered messages
    (``GET /api/books/{book_id}/chats/{chat_id}`` → 200, UC-081 / US-095.AC-2). A
    chat owned by another author answers 404 (US-061.AC-1)."""
    try:
        return await chats_service.get_chat(access, chat_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chats_service.ChatError as err:
        raise _map_chat_error(err)


@router.patch("/{book_id}/chats/{chat_id}")
async def update_chat(
    chat_id: str,
    payload: UpdateChatRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChatResponse:
    """Update title / archived / model / sampling on an owned chat
    (``PATCH /api/books/{book_id}/chats/{chat_id}`` → 200, UC-082 / US-096.AC-2). A
    chat owned by another author answers 404 (US-061.AC-1)."""
    try:
        return await chats_service.update_chat(access, chat_id, payload)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chats_service.ChatError as err:
        raise _map_chat_error(err)


@router.post("/{book_id}/chats/{chat_id}/turn")
async def run_chat_turn(
    chat_id: str,
    payload: TurnRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> StreamingResponse:
    """Run one assistant turn, streaming SSE frames
    (``POST /api/books/{book_id}/chats/{chat_id}/turn``, UC-054 / UC-056 /
    US-058 / US-060). Declared **after** the static ``model-options`` route.

    The **pre-stream refusals** run first via
    :func:`~app.services.chat_turn.prepare_turn` and map to ordinary JSON HTTP
    errors — 404 for a chat that is missing / another author's, 400 for no model
    pair, an inactive/missing server or an unset key env var — **before** any
    streaming begins and before anything is persisted (DoD-8 / DoD-10). Only then
    is a ``text/event-stream`` response returned whose frames are named exactly
    ``thinking`` / ``delta`` / ``done`` / ``error`` with JSON ``data:`` payloads;
    once the stream is open, every failure surfaces as one ``error`` frame, never a
    500. The SSE-response construction is the HTTP concern that stays here; the
    frame-yielding orchestrator is the service (layer separation).
    """
    try:
        context = await chat_turn.prepare_turn(access, chat_id, payload)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chats_service.ChatError as err:
        raise _map_chat_error(err)
    except llm_servers_service.LlmServerError as err:
        raise _map_llm_server_error(err)

    async def event_stream() -> AsyncGenerator[str, None]:
        async for frame in chat_turn.run_turn(context, payload.prompt):
            yield (
                f"event: {frame.event}\n"
                f"data: {frame.data.model_dump_json()}\n\n"
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{book_id}/chats/{chat_id}/title")
async def title_chat(
    chat_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChatTitleResponse:
    """Run the auto-titling pass over an owned chat
    (``POST /api/books/{book_id}/chats/{chat_id}/title`` → 200, 023 / FEAT-013).

    Declared **after** the static ``model-options`` route (DoD-13) and alongside
    ``turn``, so ``model-options`` is never captured as a ``chat_id``.

    The **policy is the service's**, not this route's: whether the chat is at a
    trigger count, which model titles it and what a failure means all live in
    :func:`~app.services.chat_titling.maybe_title_chat`. A titling failure is not
    an HTTP failure — it comes back as the existing title with ``changed=false``.
    The only error this route maps is the ``chat_not_found`` ``ChatError`` for a
    chat that is missing or another author's (404), plus the dependency's 403.
    """
    try:
        return await chat_titling.maybe_title_chat(access, chat_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chats_service.ChatError as err:
        raise _map_chat_error(err)
