"""Chapter route family for ``/api/books/{book_id}/chapters`` (feature 014,
step 003; extended by feature 015, step 003 with the body and transition
handlers).

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
rule ``routes/books.py`` documents for ``/shared``. 015's five additions are all
``/{chapter_id}/<literal>`` — ``/text``, ``/open``, ``/close``, ``/reopen`` — so none
of them can shadow or be shadowed by anything in the family, and the ``/order`` rule
above is untouched. They are grouped **after** 014's six so the module reads
skeleton-then-writing.

Typed-error → status map, covering all nine ``ChapterErrorReason`` members:
``not_found`` → **404** (an unknown chapter id, a non-numeric one, or one belonging
to another book — produced by the *service's* resolver, since the ``book_access``
dependency only ever sees ``{book_id}``); ``not_planned``, ``chapter_not_open``,
``chapter_not_closed``, ``another_chapter_open`` and ``stale_version`` → **409** (the
caller *has* the capability; what refuses them is a state-machine or concurrency
constraint, so 403 would be a lie — ``context.md`` → "Status taxonomy");
``book_archived`` and ``proposal_mode_refused`` → **403** (under archive, and for a
co-author in a ``proposal``-mode book, *no one* holds the write capability, which is
an access answer rather than a resource-state one — decisions D10 / D11). Note these
two 403s travel through :func:`_map_chapter_error`, **not**
:func:`_map_authz_error`, so their typed message survives to the client;
``invalid_reorder_set`` → **400** (the body is structurally valid, so this is not a
422). ``authz.BookAuthorizationError`` → **403**, which is how a reader is refused a
write and a co-author is refused a reorder (US-033.AC-2) or a state transition.

Success codes: **201** on create, **204** on delete, 200 everywhere else.

The router object and its prefix, the eleven route registrations (path, method,
status code), every handler signature and return annotation, and the reason →
status map with both mapping helpers are frozen (014 step 003; 015 step 003).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas.chapters import (
    ChapterListResponse,
    ChapterResponse,
    ChapterTextResponse,
    CreateChapterRequest,
    ReorderChaptersRequest,
    UpdateChapterSketchRequest,
    UpdateChapterTextRequest,
)
from app.services import authz
from app.services import chapters as chapters_service

router = APIRouter(prefix="/api/books", tags=["chapters"])

_CHAPTER_ERROR_STATUS: dict[chapters_service.ChapterErrorReason, int] = {
    # 014's three reasons — unchanged.
    chapters_service.ChapterErrorReason.not_found: status.HTTP_404_NOT_FOUND,
    chapters_service.ChapterErrorReason.not_planned: status.HTTP_409_CONFLICT,
    chapters_service.ChapterErrorReason.invalid_reorder_set: (
        status.HTTP_400_BAD_REQUEST
    ),
    # 015's six — the four state-machine refusals are 409, the two access-shaped
    # refusals are 403 (feature 015, step 003).
    chapters_service.ChapterErrorReason.chapter_not_open: status.HTTP_409_CONFLICT,
    chapters_service.ChapterErrorReason.chapter_not_closed: (
        status.HTTP_409_CONFLICT
    ),
    chapters_service.ChapterErrorReason.another_chapter_open: (
        status.HTTP_409_CONFLICT
    ),
    chapters_service.ChapterErrorReason.stale_version: status.HTTP_409_CONFLICT,
    chapters_service.ChapterErrorReason.book_archived: status.HTTP_403_FORBIDDEN,
    chapters_service.ChapterErrorReason.proposal_mode_refused: (
        status.HTTP_403_FORBIDDEN
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


@router.get("/{book_id}/chapters/{chapter_id}/text")
async def get_chapter_text(
    chapter_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterTextResponse:
    """One chapter's stored body
    (``GET /api/books/{book_id}/chapters/{chapter_id}/text`` → 200).

    Delegates to ``chapters_service.get_chapter_text(access, chapter_id)``. The
    body is a **sub-resource**, not a field of ``ChapterResponse`` (decision
    D13): 014's chapter DTO deliberately carries no ``text`` so a list render
    cannot drag whole bodies onto the wire, and the body's own concurrency token
    (``version``) belongs on the resource that has one.

    A read is never refused for the book's state or collaboration mode — an
    ``archived`` book still serves its chapters (decision D10).
    """
    try:
        return await chapters_service.get_chapter_text(access, chapter_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chapters_service.ChapterError as err:
        raise _map_chapter_error(err)


@router.put("/{book_id}/chapters/{chapter_id}/text")
async def update_chapter_text(
    chapter_id: str,
    payload: UpdateChapterTextRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterTextResponse:
    """Replace an ``open`` chapter's whole body against a version token
    (``PUT /api/books/{book_id}/chapters/{chapter_id}/text`` → 200, UC-038 /
    UC-039 / US-040 / US-041).

    Delegates to
    ``chapters_service.save_chapter_text(access, chapter_id, payload)``.
    ``PUT`` because the request replaces the whole resource — there is exactly
    one body write path and it always carries the entire body (decision D1); the
    append-vs-replace distinction is an editing operation on the client's draft
    and never reaches HTTP.

    Refusals, all produced by the service and mapped here: a stale
    ``expected_version`` and a chapter that is not ``open`` → **409**; an
    ``archived`` book (D10) and a co-author writing in a ``proposal``-mode book
    (D11) → **403** through :func:`_map_chapter_error`, *not* through
    :func:`_map_authz_error`, so the typed reason's message reaches the client
    verbatim. A reader is refused **403** by ``authz.require`` through
    :func:`_map_authz_error`. A malformed body is **422** from the request model
    before this handler runs.
    """
    try:
        return await chapters_service.save_chapter_text(
            access, chapter_id, payload
        )
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chapters_service.ChapterError as err:
        raise _map_chapter_error(err)


@router.post("/{book_id}/chapters/{chapter_id}/open")
async def open_chapter(
    chapter_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterResponse:
    """Open a ``planned`` chapter for writing
    (``POST /api/books/{book_id}/chapters/{chapter_id}/open`` → 200, UC-035 /
    US-036).

    Delegates to ``chapters_service.open_chapter(access, chapter_id)`` and
    returns 014's ``ChapterResponse`` — the transition changes ``state`` and
    nothing else, so it mints no DTO of its own.

    ``POST`` with **no request body**: this is a command, not a representation to
    replace. A chapter that is not ``planned`` and a book that already holds an
    ``open`` (or ``closing``) chapter both answer **409**; a co-author is refused
    **403** by ``authz.require`` (owner-only), an ``archived`` book **403** by
    the typed reason.
    """
    try:
        return await chapters_service.open_chapter(access, chapter_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chapters_service.ChapterError as err:
        raise _map_chapter_error(err)


@router.post("/{book_id}/chapters/{chapter_id}/close")
async def close_chapter(
    chapter_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterResponse:
    """Close the ``open`` chapter
    (``POST /api/books/{book_id}/chapters/{chapter_id}/close`` → 200, UC-036
    partly / US-038.AC-1, AC-2).

    Delegates to ``chapters_service.close_chapter(access, chapter_id)``. **No
    request body.** In this feature the destination is ``closed`` **directly**;
    the ``closing`` state, continuity drafting and the approval gate are
    ``016``'s (decision D8 — "the close seam"), and this handler is the seam:
    ``016`` changes the service's destination, not this route.

    A chapter that is not ``open`` answers **409**; a co-author **403**; an
    ``archived`` book **403**.
    """
    try:
        return await chapters_service.close_chapter(access, chapter_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chapters_service.ChapterError as err:
        raise _map_chapter_error(err)


@router.post("/{book_id}/chapters/{chapter_id}/close/cancel")
async def cancel_chapter_close(
    chapter_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterResponse:
    """Abandon a chapter's close run and return it to ``open``
    (``POST /api/books/{book_id}/chapters/{chapter_id}/close/cancel`` → 200,
    feature 016 decision D4 — the Stop path; US-074.AC-1).

    Delegates to ``chapters_service.cancel_close(access, chapter_id)``. **No
    request body** — a command, not a representation to replace.

    Owner-only through the same ``Capability.set_chapter_state`` the ``/close``
    endpoint requires, so no new capability gates the cancel; a co-author is
    refused **403** through :func:`_map_authz_error`, an ``archived`` book
    **403** through :func:`_map_chapter_error`.

    A chapter that is **not** ``closing`` is a **200 no-op** returning the
    unchanged chapter, not a 409: cancelling a close that is no longer running is
    exactly what a client racing the turn's own completion does.

    Declared as ``/{chapter_id}/close/cancel``, one segment deeper than
    ``/{chapter_id}/close``, so neither can shadow the other regardless of
    declaration order (the ``/order`` rule this module documents).
    """
    try:
        return await chapters_service.cancel_close(access, chapter_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chapters_service.ChapterError as err:
        raise _map_chapter_error(err)


@router.post("/{book_id}/chapters/{chapter_id}/reopen")
async def reopen_chapter(
    chapter_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> ChapterResponse:
    """Reopen a ``closed`` chapter
    (``POST /api/books/{book_id}/chapters/{chapter_id}/reopen`` → 200, UC-037 /
    US-039).

    Delegates to ``chapters_service.reopen_chapter(access, chapter_id)``. **No
    request body.** A chapter that is not ``closed`` answers **409**, as does a
    reopen while another chapter of the book is ``open`` or ``closing`` (the
    one-open-chapter rule, CF1); a co-author is refused **403**, an ``archived``
    book **403**.
    """
    try:
        return await chapters_service.reopen_chapter(access, chapter_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except chapters_service.ChapterError as err:
        raise _map_chapter_error(err)
