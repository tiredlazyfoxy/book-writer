"""Codex route layer for ``/api/books/{book_id}/codex`` (feature 013, step 003).

HTTP only: parse the request, call one :mod:`app.services.codex` function, map the
typed errors to a status, and return (see ``docs/architecture/backend.md`` — layer
separation; no business logic, no DB access here). Every endpoint is gated by
``access: authz.BookAccess = Depends(authz.book_access)`` — the ``{book_id}`` path
param is consumed **entirely** by that dependency, so no handler declares it, and
the 401-without-a-token / 404-for-a-book-you-cannot-see rules are inherited for
free. The capability check (``browse_codex`` / ``edit_codex_entry``) and every
domain rule live one layer down in ``services/codex.py``.

The two **write** paths additionally take the acting user via
``Depends(auth_service.get_current_user)`` beside the access dependency: the codex
service records ``author_id`` on create and ``modified_by`` / the version row's
author on update, and ``BookAccess`` carries only the caller's id, not the row.

Route ordering is load-bearing: FastAPI matches in declaration order, so
``/{book_id}/codex`` is declared **before** ``/{book_id}/codex/{entry_id}`` (the
same rule ``routes/books.py`` documents for ``/shared`` and ``routes/chats.py``
for ``model-options``).

Typed-error → status map: ``entry_not_found`` → 404; ``name_required`` /
``name_not_allowed`` / ``entry_archived`` → 400; ``stale_modified_at`` → 409;
``proposal_mode_unsupported`` → 403 (the caller can legitimately see the book, so
``authorization.md``'s taxonomy gives 403 — ``context.md`` → "Planner-derived
decisions"). ``authz.BookAuthorizationError`` → 403 as well, with a plain-string
detail: the two 403 producers are distinguished by their **detail body**, not by
their status.

Skeleton (013 step 003): the router object, route registration, handler signatures
(response models via return annotations, the query-param names/types/defaults, the
dependencies, the 201 create status) are frozen, as are the error→status map and
its mapping helpers.
"""

from typing import TypedDict

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.codex_entry import CodexKind
from app.models.schemas.codex import (
    CodexEntryListResponse,
    CodexEntryResponse,
    CreateCodexEntryRequest,
    UpdateCodexEntryRequest,
)
from app.models.user import User
from app.services import auth as auth_service
from app.services import authz
from app.services import codex as codex_service

router = APIRouter(prefix="/api/books", tags=["codex"])


class CodexErrorDetail(TypedDict):
    """The ``detail`` body of every codex refusal.

    Structured rather than a bare string because the client must **branch** on the
    refusal (a 409 opens the reconciliation view, a 400 is a validation surface, a
    403 is surfaced as prose) — ``reason`` is the wire value of
    :class:`~app.services.codex.CodexErrorReason`, ``message`` the human-readable
    text (for ``proposal_mode_unsupported`` it names FEAT-010). A ``TypedDict``
    keeps the route layer free of dictionaries while leaving the schema layer to
    ``models/schemas/`` (root ``CLAUDE.md`` — typing discipline).
    """

    reason: str
    message: str


_CODEX_ERROR_STATUS: dict[codex_service.CodexErrorReason, int] = {
    codex_service.CodexErrorReason.entry_not_found: status.HTTP_404_NOT_FOUND,
    codex_service.CodexErrorReason.name_required: status.HTTP_400_BAD_REQUEST,
    codex_service.CodexErrorReason.name_not_allowed: status.HTTP_400_BAD_REQUEST,
    codex_service.CodexErrorReason.entry_archived: status.HTTP_400_BAD_REQUEST,
    codex_service.CodexErrorReason.stale_modified_at: status.HTTP_409_CONFLICT,
    codex_service.CodexErrorReason.proposal_mode_unsupported: (
        status.HTTP_403_FORBIDDEN
    ),
}


def _map_codex_error(err: codex_service.CodexError) -> HTTPException:
    """Translate a typed :class:`~app.services.codex.CodexError` to an
    :class:`HTTPException` per the codex-error status map, carrying the reason's
    wire value in the detail body so the client can branch on it."""
    return HTTPException(
        status_code=_CODEX_ERROR_STATUS[err.reason],
        detail=CodexErrorDetail(reason=err.reason.value, message=err.message),
    )


def _map_authz_error(err: authz.BookAuthorizationError) -> HTTPException:
    """Translate a typed :class:`~app.services.authz.BookAuthorizationError` to a
    **403** :class:`HTTPException`. Existence-hiding 404s are produced upstream by
    the ``book_access`` resolver, not here."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(err),
    )


@router.post("/{book_id}/codex", status_code=status.HTTP_201_CREATED)
async def create_codex_entry(
    payload: CreateCodexEntryRequest,
    access: authz.BookAccess = Depends(authz.book_access),
    caller: User = Depends(auth_service.get_current_user),
) -> CodexEntryResponse:
    """Create a codex entry in the book (``POST /api/books/{book_id}/codex`` → 201,
    UC-069 / US-078). The kind/name rule and the collaboration-mode refusal are the
    service's; both surface here through ``_map_codex_error``.
    """
    try:
        return await codex_service.create_entry(access, caller, payload)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except codex_service.CodexError as err:
        raise _map_codex_error(err)


@router.get("/{book_id}/codex")
async def list_codex_entries(
    kind: CodexKind | None = None,
    q: str | None = None,
    include_archived: bool = False,
    access: authz.BookAccess = Depends(authz.book_access),
) -> CodexEntryListResponse:
    """List the book's codex entries (``GET /api/books/{book_id}/codex`` → 200,
    UC-071 / US-080.AC-1).

    ``kind`` absent means every kind; ``q`` is the optional case-insensitive
    substring over ``name`` or ``body`` (the service's ``needle`` argument — ``q``
    is the wire spelling); archived entries are excluded unless
    ``include_archived``. Declared **before** the ``/{entry_id}`` param route so
    the shorter path wins.
    """
    try:
        return await codex_service.list_entries(
            access,
            kind=kind,
            needle=q,
            include_archived=include_archived,
        )
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except codex_service.CodexError as err:
        raise _map_codex_error(err)


@router.get("/{book_id}/codex/{entry_id}")
async def get_codex_entry(
    entry_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> CodexEntryResponse:
    """Fetch one codex entry (``GET /api/books/{book_id}/codex/{entry_id}`` → 200,
    UC-070 step 1). An unknown id and an entry belonging to another book both
    answer 404 (US-085.AC-1).
    """
    try:
        return await codex_service.get_entry(access, entry_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except codex_service.CodexError as err:
        raise _map_codex_error(err)


@router.put("/{book_id}/codex/{entry_id}")
async def update_codex_entry(
    entry_id: str,
    payload: UpdateCodexEntryRequest,
    access: authz.BookAccess = Depends(authz.book_access),
    caller: User = Depends(auth_service.get_current_user),
) -> CodexEntryResponse:
    """Full-replace edit of one codex entry
    (``PUT /api/books/{book_id}/codex/{entry_id}`` → 200, UC-070 / US-079.AC-1).

    The payload carries ``expected_modified_at``; a disagreement with the stored
    value answers **409** so the client can open its reconciliation view rather
    than auto-merging (``frontend-workspace.md`` → stale buffer).
    """
    try:
        return await codex_service.update_entry(
            access, caller, entry_id, payload
        )
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except codex_service.CodexError as err:
        raise _map_codex_error(err)
