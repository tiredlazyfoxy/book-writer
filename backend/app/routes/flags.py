"""Flag ("warning") route family for a chapter's flags (feature 016).

HTTP only: parse the request, call **one** :mod:`app.services.flags` function,
map the typed refusal to a status, and return (see
``docs/architecture/backend.md`` — layer separation; no business logic, no
capability check and no DB access here). Every endpoint is gated by
``access: authz.BookAccess = Depends(authz.book_access)`` — the ``{book_id}``
path param is consumed **entirely** by that dependency — and response models are
the handlers' **return annotations**, never ``response_model=``.

A book-scoped **sub-resource** router with its own module, sibling to
``routes/continuity.py`` (the ``routes/book_author_prompts.py`` placement
precedent).

Routes, all under the shared ``/api/books`` prefix:

    GET  /{book_id}/chapters/{chapter_id}/flags                    -> FlagListResponse
    POST /{book_id}/chapters/{chapter_id}/flags                    -> FlagResponse
    POST /{book_id}/chapters/{chapter_id}/flags/{flag_id}/resolve  -> FlagResponse

Nothing here can shadow or be shadowed by ``routes/chapters.py``: every path is
at least one segment deeper than that family's ``/{book_id}/chapters/{chapter_id}``
routes, and the ``resolve`` route is a literal segment under a distinct
``{flag_id}``.

Typed-error → status map, covering all five ``FlagErrorReason`` members:
``not_a_member`` → **403**, ``book_archived`` → **403**, ``chapter_not_found`` →
**404**, ``flag_not_found`` → **404**, ``flag_already_resolved`` → **409** (the
caller *has* the capability; the flag's own lifecycle refuses them, so 403 would
be a lie — ``routes/chapters.py``'s status taxonomy).
``authz.BookAuthorizationError`` → **403**, which is how a reader is refused a
raise and a co-author a resolve (US-076.AC-2).

Success codes: **201** on raise (a flag is created), 200 on the other two.

Skeleton (016): the router object and its prefix, the three route registrations
(path, method, status code), every handler signature and return annotation, and
the reason → status map with both mapping helpers are frozen. The handler bodies
delegate to the (unimplemented) service.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas.flags import (
    FlagListResponse,
    FlagResponse,
    RaiseFlagRequest,
)
from app.services import authz
from app.services import flags as flags_service

router = APIRouter(prefix="/api/books", tags=["flags"])

_FLAG_ERROR_STATUS: dict[flags_service.FlagErrorReason, int] = {
    flags_service.FlagErrorReason.not_a_member: status.HTTP_403_FORBIDDEN,
    flags_service.FlagErrorReason.book_archived: status.HTTP_403_FORBIDDEN,
    flags_service.FlagErrorReason.chapter_not_found: status.HTTP_404_NOT_FOUND,
    flags_service.FlagErrorReason.flag_not_found: status.HTTP_404_NOT_FOUND,
    flags_service.FlagErrorReason.flag_already_resolved: (
        status.HTTP_409_CONFLICT
    ),
}


def _map_flag_error(err: flags_service.FlagError) -> HTTPException:
    """Translate a typed :class:`~app.services.flags.FlagError` to an
    :class:`HTTPException` per :data:`_FLAG_ERROR_STATUS`, passing ``err.message``
    straight through as the ``detail`` (the plain-string shape
    ``routes/chapters.py`` uses)."""
    return HTTPException(
        status_code=_FLAG_ERROR_STATUS[err.reason],
        detail=err.message,
    )


def _map_authz_error(err: authz.BookAuthorizationError) -> HTTPException:
    """Translate a typed :class:`~app.services.authz.BookAuthorizationError`
    to a **403** :class:`HTTPException`. Existence-hiding 404s are produced
    upstream by the ``book_access`` resolver, not here."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(err),
    )


@router.get("/{book_id}/chapters/{chapter_id}/flags")
async def list_flags(
    chapter_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> FlagListResponse:
    """A chapter's warnings — open **and** resolved, newest first
    (``GET /api/books/{book_id}/chapters/{chapter_id}/flags`` → 200).

    Delegates to ``flags_service.list_flags(access, chapter_id)``. Members-only
    (``not_a_member`` → **403**); an unknown or foreign chapter id is **404**.
    """
    try:
        return await flags_service.list_flags(access, chapter_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except flags_service.FlagError as err:
        raise _map_flag_error(err)


@router.post(
    "/{book_id}/chapters/{chapter_id}/flags",
    status_code=status.HTTP_201_CREATED,
)
async def raise_flag(
    chapter_id: str,
    payload: RaiseFlagRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> FlagResponse:
    """Raise a warning on a chapter
    (``POST /api/books/{book_id}/chapters/{chapter_id}/flags`` → **201**, UC-067
    / US-075.AC-1).

    Delegates to ``flags_service.raise_flag(access, chapter_id, payload)``. The
    stored flag is always ``origin=person`` and ``status=open``, attributed to
    the caller — the body carries no origin field, so a member cannot forge a
    check finding. A blank ``comment`` is refused **422** by the request model
    before the service runs; a reader is refused **403**, an ``archived`` book
    **403**.
    """
    try:
        return await flags_service.raise_flag(access, chapter_id, payload)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except flags_service.FlagError as err:
        raise _map_flag_error(err)


@router.post("/{book_id}/chapters/{chapter_id}/flags/{flag_id}/resolve")
async def resolve_flag(
    chapter_id: str,
    flag_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> FlagResponse:
    """Resolve an open warning
    (``POST /api/books/{book_id}/chapters/{chapter_id}/flags/{flag_id}/resolve``
    → 200, UC-068 / US-076.AC-2, US-077.AC-1).

    Delegates to ``flags_service.resolve_flag(access, chapter_id, flag_id)``.
    **No request body** — a command, not a representation to replace.
    **Owner-only**: a co-author is refused **403** by ``authz.require`` through
    :func:`_map_authz_error`. An unknown or foreign chapter or flag id is
    **404**; an already-resolved flag is **409** through :func:`_map_flag_error`.

    There is no un-resolve verb.
    """
    try:
        return await flags_service.resolve_flag(access, chapter_id, flag_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except flags_service.FlagError as err:
        raise _map_flag_error(err)
