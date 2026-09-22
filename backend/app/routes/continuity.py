"""Continuity route family — the book's live state notes, one chapter's note
changeset and the per-chapter continuity roll-up (feature 016).

HTTP only: parse the request, call **one** :mod:`app.services.continuity`
function, map the typed refusal to a status, and return (see
``docs/architecture/backend.md`` — layer separation; no business logic, no
capability check and no DB access here). Every endpoint is gated by
``access: authz.BookAccess = Depends(authz.book_access)`` — the ``{book_id}``
path param is consumed **entirely** by that dependency, so no handler re-declares
it, and the 401-without-a-token / 404-for-a-book-you-cannot-see rules are
inherited for free (``routes/chapters.py`` is the same shape). Response models
are the handlers' **return annotations**, never ``response_model=``.

A book-scoped **sub-resource** router with its own module rather than handlers
bolted onto ``routes/books.py`` or ``routes/chapters.py`` (the
``routes/book_author_prompts.py`` placement precedent): the four routes here span
two parents (the book and one of its chapters) and answer one service.

Routes, all under the shared ``/api/books`` prefix:

    GET  /{book_id}/state-notes                        -> BookStateNotesResponse
    PUT  /{book_id}/state-notes                        -> BookStateNotesResponse
    GET  /{book_id}/continuity                          -> BookContinuityResponse
    GET  /{book_id}/chapters/{chapter_id}/notes         -> ChapterNoteChangesetResponse

**Route ordering is not load-bearing here** and the family cannot collide with
``routes/books.py`` or ``routes/chapters.py``: ``state-notes`` and ``continuity``
are literal segments where those modules have only ``/{book_id}`` and its own
literals, and ``…/chapters/{chapter_id}/notes`` is one segment deeper than
``routes/chapters.py``'s ``GET /{book_id}/chapters/{chapter_id}``.

Typed-error → status map, covering all four ``ContinuityErrorReason`` members:
``not_a_member`` → **403** (the book is legitimately visible; its continuity
material is members-only — existence hiding already happened in the dependency),
``book_archived`` → **403**, ``proposal_mode_refused`` → **403**,
``chapter_not_found`` → **404**. ``authz.BookAuthorizationError`` → **403**.

Skeleton (016): the router object and its prefix, the four route registrations
(path, method, status code), every handler signature and return annotation, and
the reason → status map with both mapping helpers are frozen. The handler bodies
delegate to the (unimplemented) service.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas.continuity import (
    BookContinuityResponse,
    BookStateNotesResponse,
    ChapterNoteChangesetResponse,
    UpdateBookStateNotesRequest,
)
from app.services import authz
from app.services import continuity as continuity_service

router = APIRouter(prefix="/api/books", tags=["continuity"])

_CONTINUITY_ERROR_STATUS: dict[continuity_service.ContinuityErrorReason, int] = {
    continuity_service.ContinuityErrorReason.not_a_member: (
        status.HTTP_403_FORBIDDEN
    ),
    continuity_service.ContinuityErrorReason.book_archived: (
        status.HTTP_403_FORBIDDEN
    ),
    continuity_service.ContinuityErrorReason.proposal_mode_refused: (
        status.HTTP_403_FORBIDDEN
    ),
    continuity_service.ContinuityErrorReason.chapter_not_found: (
        status.HTTP_404_NOT_FOUND
    ),
}


def _map_continuity_error(
    err: continuity_service.ContinuityError,
) -> HTTPException:
    """Translate a typed
    :class:`~app.services.continuity.ContinuityError` to an
    :class:`HTTPException` per :data:`_CONTINUITY_ERROR_STATUS`, passing
    ``err.message`` straight through as the ``detail`` (the plain-string shape
    ``routes/chapters.py`` uses — the client has one refusal to render, nothing
    to branch on)."""
    return HTTPException(
        status_code=_CONTINUITY_ERROR_STATUS[err.reason],
        detail=err.message,
    )


def _map_authz_error(err: authz.BookAuthorizationError) -> HTTPException:
    """Translate a typed :class:`~app.services.authz.BookAuthorizationError`
    (a capability denial for a book the caller can legitimately see) to a
    **403** :class:`HTTPException`. Existence-hiding 404s are produced upstream by
    the ``book_access`` resolver, not here."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(err),
    )


@router.get("/{book_id}/state-notes")
async def get_state_notes(
    access: authz.BookAccess = Depends(authz.book_access),
) -> BookStateNotesResponse:
    """The book's live state notes
    (``GET /api/books/{book_id}/state-notes`` → 200, UC-049 / US-052.AC-1).

    Delegates to ``continuity_service.get_state_notes(access)``. Members-only: a
    reader on a public book is refused **403** with ``not_a_member``. An empty
    ``active_notes`` is a normal **200**, never a 404.
    """
    try:
        return await continuity_service.get_state_notes(access)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except continuity_service.ContinuityError as err:
        raise _map_continuity_error(err)


@router.put("/{book_id}/state-notes")
async def update_state_notes(
    payload: UpdateBookStateNotesRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> BookStateNotesResponse:
    """Replace the book's live state notes
    (``PUT /api/books/{book_id}/state-notes`` → 200, UC-050's direct-edit path /
    US-053.AC-1).

    Delegates to ``continuity_service.update_state_notes(access, payload)``.
    ``PUT`` because the body carries the **whole** note set — free text with no
    per-note addressing, so there is nothing for a PATCH to address — and there
    is no version token.

    Refusals: an ``archived`` book and a co-author in a ``proposal``-mode book
    both **403** through :func:`_map_continuity_error`, so the typed reason's
    message (which names FEAT-010 as unbuilt) reaches the client verbatim; a
    reader is refused **403** by ``authz.require`` through
    :func:`_map_authz_error`.
    """
    try:
        return await continuity_service.update_state_notes(access, payload)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except continuity_service.ContinuityError as err:
        raise _map_continuity_error(err)


@router.get("/{book_id}/continuity")
async def get_book_continuity(
    access: authz.BookAccess = Depends(authz.book_access),
) -> BookContinuityResponse:
    """The book's per-chapter continuity roll-up
    (``GET /api/books/{book_id}/continuity`` → 200, UC-089 / UC-091;
    US-104.AC-1, US-106.AC-2 / AC-3).

    Delegates to ``continuity_service.get_book_continuity(access)``. One entry
    per chapter in ordinal order, each carrying the chapter's summary, its
    changeset (or ``null``) and its **open** warnings. Members-only.
    """
    try:
        return await continuity_service.get_book_continuity(access)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except continuity_service.ContinuityError as err:
        raise _map_continuity_error(err)


@router.get("/{book_id}/chapters/{chapter_id}/notes")
async def get_chapter_changeset(
    chapter_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterNoteChangesetResponse:
    """One chapter's note changeset
    (``GET /api/books/{book_id}/chapters/{chapter_id}/notes`` → 200, UC-051 /
    US-054.AC-1).

    Delegates to
    ``continuity_service.get_chapter_changeset(access, chapter_id)``. An unknown
    id and a chapter belonging to **another book** both answer **404** through
    :func:`_map_continuity_error` — the service's own resolver produces it, not
    the ``book_access`` dependency.

    A chapter with **no changeset row yet** answers a **default-empty 200**, not
    a 404 (the ``ChapterAuthorPromptResponse`` convention): a chapter that has
    never been closed is a normal chapter, not a missing resource.
    """
    try:
        return await continuity_service.get_chapter_changeset(access, chapter_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except continuity_service.ContinuityError as err:
        raise _map_continuity_error(err)
