"""Book route layer for ``/api/books`` (feature 009, step 003).

HTTP only: parse the request, call one :mod:`app.services.books` function, map the
typed :class:`~app.services.books.BookError` to a status, and return (see
``docs/architecture/backend.md`` — layer separation; no business logic, no DB
access here). Every endpoint is gated by ``Depends(auth_service.get_current_user)``
— books are the first author-owned (non-admin) resource, so this is the plain
authenticated gate, **not** the admin ``require_role`` gate. ``get_current_user``
supplies the 401 (no anonymous book surface).

Route ordering is load-bearing: FastAPI matches in declaration order, so the
static ``GET /shared`` route is declared **before** any ``/{book_id}`` param route
(added in step 004) — otherwise ``shared`` is captured as a ``book_id``. Feature
022 adds a second static route under the same rule, ``GET /public``, declared
immediately after ``/shared`` and before ``/{book_id}`` (decision D15).

Feature 022 also **removed** ``GET /{book_id}/read`` from this module: the whole
reader surface moved to ``routes/reader.py`` + ``services/reader.py`` (decision
D3), at the same URL. ``GET /public`` is the one reader-facing route that stayed,
and only because ``/public`` and ``/{book_id}`` collide at the same path depth —
declaring it in a second router would make ``main.py``'s include order
load-bearing and invisible; its logic still lives in ``services/reader.py``.

Typed-error → status map the handlers implement: ``not-found`` → 404.

Skeleton (feature 009, step 003): the router object, route registration, and
handler signatures (``response_model`` via return annotations, the ``caller``
dependency, the 201 create status) are frozen, and the error→status map + helper
are real; behavior lives in the service, which is UNIMPLEMENTED. This router is
**extended** by steps 004 (read) and 005 (mutations) — keep the module open.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas.books import (
    AddMemberRequest,
    BookDetailResponse,
    BookListResponse,
    BookResponse,
    CreateBookRequest,
    SetVisibilityRequest,
    TransferOwnershipRequest,
)
from app.models.schemas.reader import PublicBookListResponse
from app.models.user import User
from app.services import auth as auth_service
from app.services import authz
from app.services import books as books_service
from app.services import reader as reader_service

router = APIRouter(prefix="/api/books", tags=["books"])

_BOOK_ERROR_STATUS: dict[books_service.BookErrorReason, int] = {
    books_service.BookErrorReason.not_found: status.HTTP_404_NOT_FOUND,
    books_service.BookErrorReason.already_archived: status.HTTP_409_CONFLICT,
    books_service.BookErrorReason.not_archived: status.HTTP_409_CONFLICT,
    books_service.BookErrorReason.transfer_target_not_member: (
        status.HTTP_409_CONFLICT
    ),
    books_service.BookErrorReason.duplicate_member: status.HTTP_409_CONFLICT,
    books_service.BookErrorReason.remove_target_not_member: (
        status.HTTP_404_NOT_FOUND
    ),
}


def _map_book_error(err: books_service.BookError) -> HTTPException:
    """Translate a typed :class:`~app.services.books.BookError` to an
    :class:`HTTPException` per the book-error status map."""
    return HTTPException(
        status_code=_BOOK_ERROR_STATUS[err.reason],
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


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_book(
    payload: CreateBookRequest,
    caller: User = Depends(auth_service.get_current_user),
) -> BookResponse:
    """Create a book with the caller as owner (``POST /api/books`` → 201, UC-021)."""
    try:
        return await books_service.create_book(payload, caller)
    except books_service.BookError as err:
        raise _map_book_error(err)


@router.get("")
async def list_owned(
    caller: User = Depends(auth_service.get_current_user),
) -> BookListResponse:
    """List the caller's owned books (``GET /api/books`` → 200, UC-022)."""
    return await books_service.list_owned(caller)


@router.get("/shared")
async def list_shared(
    caller: User = Depends(auth_service.get_current_user),
) -> BookListResponse:
    """List the books shared with the caller (``GET /api/books/shared`` → 200,
    UC-030). Declared before any ``/{book_id}`` route (step 004) so the static
    path wins."""
    return await books_service.list_shared(caller)


@router.get("/public")
async def list_public_books(
    caller: User = Depends(auth_service.get_current_user),
) -> PublicBookListResponse:
    """Public books the caller can discover but is not part of
    (``GET /api/books/public`` → 200, UC-029 discovery, feature 022).

    Declared **immediately after** ``GET /shared`` and **before** ``GET
    /{book_id}`` — declaration order is load-bearing (decision D15): FastAPI
    matches in declaration order, so a ``/public`` declared after the param route
    would be captured as a ``book_id`` and answer 422. Keeping it in this file,
    beside ``/shared``, is what makes static-before-dynamic provable by reading
    one module.

    Delegates to ``reader_service.list_public_books(caller)`` — the route is the
    only reader-surface line that lives outside the reader module pair; every
    line of reader *logic* and every reader DTO stays there (D15). Gated by
    authentication alone: there is no ``book_id`` to resolve a role against, so
    ``Depends(authz.book_access)`` is inapplicable and ``get_current_user`` (the
    same gate the two delivered list routes use) supplies the 401 (D14). The
    service raises no typed refusal on this path — an empty feed is an empty
    list, not an error."""
    return await reader_service.list_public_books(caller)


@router.get("/{book_id}")
async def get_book_detail(
    access: authz.BookAccess = Depends(authz.book_access),
) -> BookDetailResponse:
    """Members-only book detail (``GET /api/books/{book_id}`` → 200, US-029.AC-2).

    The ``book_access`` dependency yields 401 (no token) and 404 (missing / private
    non-member) before the service runs; the service's ``require`` refuses a
    public-book reader, mapped here to 403. Declared **after** the static
    ``/shared`` route so the param route does not capture it."""
    try:
        return await books_service.get_book_detail(access)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except books_service.BookError as err:
        raise _map_book_error(err)


@router.post("/{book_id}/archive")
async def archive_book(
    access: authz.BookAccess = Depends(authz.book_access),
) -> BookResponse:
    """Archive a book (``POST /api/books/{book_id}/archive`` → 200, UC-023 /
    US-024.AC-1). Owner-only via ``archive_book``; a co-author/reader is 403'd, a
    private non-member 404'd upstream by the resolver. Re-archiving is 409."""
    try:
        return await books_service.archive_book(access)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except books_service.BookError as err:
        raise _map_book_error(err)


@router.post("/{book_id}/unarchive")
async def unarchive_book(
    access: authz.BookAccess = Depends(authz.book_access),
) -> BookResponse:
    """Unarchive a book (``POST /api/books/{book_id}/unarchive`` → 200, UC-023
    reversible). Owner-only via ``archive_book``; unarchiving a non-archived book
    is 409."""
    try:
        return await books_service.unarchive_book(access)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except books_service.BookError as err:
        raise _map_book_error(err)


@router.post("/{book_id}/transfer")
async def transfer_ownership(
    payload: TransferOwnershipRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> BookResponse:
    """Transfer ownership to a current co-author
    (``POST /api/books/{book_id}/transfer`` → 200, UC-024 / US-025.AC-1).
    Owner-only via ``transfer_ownership``; a non-member target is refused 409."""
    try:
        return await books_service.transfer_ownership(
            access, payload.target_user_id
        )
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except books_service.BookError as err:
        raise _map_book_error(err)


@router.post("/{book_id}/members")
async def add_member(
    payload: AddMemberRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> BookDetailResponse:
    """Grant co-author access (``POST /api/books/{book_id}/members`` → 200,
    UC-026 / US-027.AC-1). Owner-only via ``add_member``; a duplicate add is
    refused 409. Returns the refreshed detail (with the updated ``members``
    list)."""
    try:
        return await books_service.add_member(access, payload.target_user_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except books_service.BookError as err:
        raise _map_book_error(err)


@router.delete("/{book_id}/members/{user_id}")
async def remove_member(
    user_id: str,
    access: authz.BookAccess = Depends(authz.book_access),
) -> BookDetailResponse:
    """Revoke a co-author's access
    (``DELETE /api/books/{book_id}/members/{user_id}`` → 200, UC-027 /
    US-028.AC-1). Owner-only via ``remove_member``; a non-member target is
    refused 404. Returns the refreshed detail (with the updated ``members``
    list)."""
    try:
        return await books_service.remove_member(access, user_id)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except books_service.BookError as err:
        raise _map_book_error(err)


@router.patch("/{book_id}/visibility")
async def set_visibility(
    payload: SetVisibilityRequest,
    access: authz.BookAccess = Depends(authz.book_access),
) -> BookResponse:
    """Set a book's visibility (``PATCH /api/books/{book_id}/visibility`` → 200,
    UC-028 / US-029.AC-1, AC-2). Owner-only via ``set_visibility``."""
    try:
        return await books_service.set_visibility(access, payload.visibility)
    except authz.BookAuthorizationError as err:
        raise _map_authz_error(err)
    except books_service.BookError as err:
        raise _map_book_error(err)
