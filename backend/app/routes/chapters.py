"""Chapter route family for ``/api/books/{book_id}/chapters`` (feature 014,
step 003).

HTTP only: parse the request, call **one** :mod:`app.services.chapters` function,
map the typed refusal to a status, and return (see ``docs/architecture/backend.md``
— layer separation; no business logic, no capability check and no DB access here).
Every endpoint is gated by ``access: authz.BookAccess = Depends(authz.book_access)``
— the ``{book_id}`` path param is consumed **entirely** by that dependency, so no
handler re-declares it, and the 401-without-a-token / 404-for-a-book-you-cannot-see
rules are inherited for free (``routes/codex.py`` and
``routes/book_author_prompts.py`` are the same shape). Response models are the
handlers' **return annotations**, never ``response_model=``.

This is a book-scoped **sub-resource** router with its own module rather than
handlers bolted onto ``routes/books.py`` (the ``routes/book_author_prompts.py``
placement precedent).

Route ordering is load-bearing: FastAPI matches in declaration order, so
``PUT .../chapters/order`` is declared **before** any ``.../chapters/{chapter_id}``
route — otherwise ``order`` would be captured as a ``chapter_id``. There is no
``PUT /{chapter_id}`` in this family today, so the collision is latent rather than
live, but the literal segment is declared first anyway so the next feature to add a
chapter ``PUT`` cannot silently break reorder (``003.context.md``; DoD-16). The same
rule ``routes/books.py`` documents for ``/shared``.

Typed-error → status map: ``not_found`` → **404** (an unknown chapter id, a
non-numeric one, or one belonging to another book — produced by the *service's*
resolver, since the ``book_access`` dependency only ever sees ``{book_id}``);
``not_planned`` → **409** (the caller *has* the capability; what refuses them is a
state-machine constraint, so 403 would be a lie — ``context.md`` → "Status
taxonomy"); ``invalid_reorder_set`` → **400** (the body is structurally valid, so
this is not a 422). ``authz.BookAuthorizationError`` → **403**, which is how a
reader is refused a write and a co-author is refused a reorder (US-033.AC-2).

Success codes: **201** on create, **204** on delete, 200 everywhere else.

The router object and its prefix, the six route registrations (path, method,
status code), every handler signature and return annotation, and the reason →
status map with both mapping helpers are frozen (014 step 003).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas.chapters import (
    ChapterListResponse,
    ChapterResponse,
    CreateChapterRequest,
    ReorderChaptersRequest,
    UpdateChapterSketchRequest,
)
from app.services import authz
from app.services import chapters as chapters_service

router = APIRouter(prefix="/api/books", tags=["chapters"])

_CHAPTER_ERROR_STATUS: dict[chapters_service.ChapterErrorReason, int] = {
    chapters_service.ChapterErrorReason.not_found: status.HTTP_404_NOT_FOUND,
    chapters_service.ChapterErrorReason.not_planned: status.HTTP_409_CONFLICT,
    chapters_service.ChapterErrorReason.invalid_reorder_set: (
        status.HTTP_400_BAD_REQUEST
    ),
}


def _map_chapter_error(err: chapters_service.ChapterError) -> HTTPException:
    """Translate a typed :class:`~app.services.chapters.ChapterError` to an
    :class:`HTTPException` per :data:`_CHAPTER_ERROR_STATUS`, passing
    ``err.message`` straight through as the ``detail`` (the plain-string shape
    ``routes/books.py`` uses — the client has one refusal to render, nothing to
    branch on)."""
    return HTTPException(
        status_code=_CHAPTER_ERROR_STATUS[err.reason],
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


@router.get("/{book_id}/chapters")
async def list_chapters(
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterListResponse:
    """The book's chapters, ordered by ordinal ascending
    (``GET /api/books/{book_id}/chapters`` → 200).

    Delegates to ``chapters_service.list_chapters(access)``. The envelope carries
    ``can_reorder``, the owner-only affordance hint the service computes from
    ``access.role`` — enforcement stays on the ``PUT``, the hint never substitutes
    for it (``context.md`` → "The wire contract").
    """
    try:
        return await chapters_service.list_chapters(access)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chapters_service.ChapterError as err:
        raise _map_chapter_error(err)


@router.post("/{book_id}/chapters", status_code=status.HTTP_201_CREATED)
async def create_chapter(
    payload: CreateChapterRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterResponse:
    """Append a new ``planned`` chapter to the book
    (``POST /api/books/{book_id}/chapters`` → **201**, UC-031 / US-032.AC-1).

    Delegates to ``chapters_service.add_chapter(access, payload)``. ``ordinal`` is
    server-assigned (appended last); a blank ``title`` is refused **422** by the
    request model before the service runs, while an empty ``sketch`` is
    legitimate. A reader is refused 403 through :func:`_map_authz_error`.
    """
    try:
        return await chapters_service.add_chapter(access, payload)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chapters_service.ChapterError as err:
        raise _map_chapter_error(err)


@router.put("/{book_id}/chapters/order")
async def reorder_chapters(
    payload: ReorderChaptersRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterListResponse:
    """Rewrite the book's chapter order in one bulk call
    (``PUT /api/books/{book_id}/chapters/order`` → 200, UC-032 / US-033.AC-1,
    AC-2).

    Delegates to ``chapters_service.reorder_chapters(access, payload)``, which
    takes the **full ordered chapter-id list** and refuses a list that is not
    exactly the book's current chapter set with ``invalid_reorder_set`` → **400**
    (decision D3). Owner-only: a co-author is refused 403 through
    :func:`_map_authz_error`.

    **Declared before every ``/{chapter_id}`` route below** so the literal
    ``order`` segment can never be captured as a chapter id (DoD-16).
    """
    try:
        return await chapters_service.reorder_chapters(access, payload)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chapters_service.ChapterError as err:
        raise _map_chapter_error(err)


@router.get("/{book_id}/chapters/{chapter_id}")
async def get_chapter(
    chapter_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterResponse:
    """One chapter by id
    (``GET /api/books/{book_id}/chapters/{chapter_id}`` → 200).

    Delegates to ``chapters_service.get_chapter(access, chapter_id)``. An unknown
    id and a chapter belonging to **another book** both answer 404 through
    :func:`_map_chapter_error` — the service's own resolver produces it, not the
    ``book_access`` dependency (decision D4).
    """
    try:
        return await chapters_service.get_chapter(access, chapter_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chapters_service.ChapterError as err:
        raise _map_chapter_error(err)


@router.patch("/{book_id}/chapters/{chapter_id}")
async def update_chapter_sketch(
    chapter_id: str,
    payload: UpdateChapterSketchRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterResponse:
    """Replace a ``planned`` chapter's sketch
    (``PATCH /api/books/{book_id}/chapters/{chapter_id}`` → 200, UC-033 /
    US-034.AC-1, AC-2).

    Delegates to ``chapters_service.update_sketch(access, chapter_id, payload)``.
    ``PATCH`` rather than ``PUT`` because the body carries one field of a larger
    resource and the rest of that resource is other features' to write. A chapter
    that is not ``planned`` answers **409** through :func:`_map_chapter_error`.
    No version token, no 409 concurrency path — last write wins (decision D6).
    """
    try:
        return await chapters_service.update_sketch(access, chapter_id, payload)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chapters_service.ChapterError as err:
        raise _map_chapter_error(err)


@router.delete(
    "/{book_id}/chapters/{chapter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_chapter(
    chapter_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> None:
    """Remove a ``planned`` chapter
    (``DELETE /api/books/{book_id}/chapters/{chapter_id}`` → **204**, no body,
    UC-034 / US-035.AC-1, AC-2).

    Delegates to ``chapters_service.remove_chapter(access, chapter_id)``. A
    chapter that is not ``planned`` answers **409** through
    :func:`_map_chapter_error`; the remaining ordinals are deliberately not
    renumbered.
    """
    try:
        await chapters_service.remove_chapter(access, chapter_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chapters_service.ChapterError as err:
        raise _map_chapter_error(err)
