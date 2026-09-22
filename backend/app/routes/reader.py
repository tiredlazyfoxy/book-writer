"""Reader route family for ``/api/books/{book_id}/read`` (feature 022).

HTTP only: parse the request, call **one** :mod:`app.services.reader` function,
map the typed refusal to a status, and return (see
``docs/architecture/backend.md`` — layer separation; no business logic, no
capability check and no DB access here). Both endpoints are gated by
``access: authz.BookAccess = Depends(authz.book_access)`` — the ``{book_id}`` path
param is consumed **entirely** by that dependency, so no handler re-declares it,
and the 401-without-a-token / 404-for-a-book-you-cannot-see rules are inherited
for free (``routes/chapters.py`` is the same shape). Response models are the
handlers' **return annotations**, never ``response_model=``.

**Why a module of its own** (decision D3): this is the whole reader surface, and
UC-029 is an exclusion list — "what can ACT-006 reach?" must be answerable by
reading this file, not by auditing a twelve-route ``routes/books.py``. The
delivered ``GET /{book_id}/read`` route **moved here** from ``routes/books.py``;
its URL is unchanged, so no client sees a difference.

The router carries the shared ``/api/books`` prefix and is registered in
``app/main.py``. Neither path can collide with a ``routes/books.py`` or
``routes/chapters.py`` route: ``/{book_id}/read`` and
``/{book_id}/read/chapters/{chapter_id}`` are distinct literal shapes at their
respective depths.

Typed-error → status map: **both** ``ReaderErrorReason`` members → **404**.
``chapter_not_found`` is deliberately the same answer for all five refusal
sources (unknown id, non-numeric id, another book's chapter, a ``planned``
chapter, a ``closing`` chapter) — a 403 would confirm a chapter exists at that id
and let a reader walk the id space to reconstruct the author's unwritten skeleton
(decision D5). ``authz.BookAuthorizationError`` → **403**, kept for spine
consistency though unreachable today (decision D7).

Skeleton (feature 022): the router object and its prefix, both route
registrations, both handler signatures and return annotations, and the reason →
status map with both mapping helpers are frozen and arrive complete — the
behavior lives in :mod:`app.services.reader`, which is UNIMPLEMENTED.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas.reader import ReaderBookResponse, ReaderChapterResponse
from app.services import authz
from app.services import reader as reader_service

router = APIRouter(prefix="/api/books", tags=["reader"])

_READER_ERROR_STATUS: dict[reader_service.ReaderErrorReason, int] = {
    reader_service.ReaderErrorReason.book_not_found: status.HTTP_404_NOT_FOUND,
    reader_service.ReaderErrorReason.chapter_not_found: (
        status.HTTP_404_NOT_FOUND
    ),
}


def _map_reader_error(err: reader_service.ReaderError) -> HTTPException:
    """Translate a typed :class:`~app.services.reader.ReaderError` to an
    :class:`HTTPException` per :data:`_READER_ERROR_STATUS`, passing
    ``err.message`` straight through as the ``detail`` (the plain-string shape
    ``routes/books.py`` and ``routes/chapters.py`` both use)."""
    return HTTPException(
        status_code=_READER_ERROR_STATUS[err.reason],
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


@router.get("/{book_id}/read")
async def get_reader_book(
    access: authz.BookAccess = Depends(authz.book_access),
) -> ReaderBookResponse:
    """The reader-safe table of contents
    (``GET /api/books/{book_id}/read`` → 200, UC-029 / US-030.AC-1).

    Delegates to ``reader_service.get_reader_book(access)``. Open to
    owner/co-author/reader via ``read_book``; a private-book non-member is 404'd
    by the resolver, an anonymous caller 401'd by ``get_current_user`` — both
    upstream of this handler.
    """
    try:
        return await reader_service.get_reader_book(access)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except reader_service.ReaderError as err:
        raise _map_reader_error(err)


@router.get("/{book_id}/read/chapters/{chapter_id}")
async def get_reader_chapter(
    chapter_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ReaderChapterResponse:
    """One chapter's saved text, read-only
    (``GET /api/books/{book_id}/read/chapters/{chapter_id}`` → 200, UC-029 /
    US-030.AC-2).

    Delegates to ``reader_service.get_reader_chapter(access, chapter_id)``. Every
    refusal the service raises is a 404 with the same body, whatever its source
    (decision D5).
    """
    try:
        return await reader_service.get_reader_chapter(access, chapter_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except reader_service.ReaderError as err:
        raise _map_reader_error(err)
