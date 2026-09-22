"""Book service — create + list business logic (feature 009, step 003).

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). All persistence goes through the session-free
``app.db.books`` layer (namespace import). Domain refusals raise the typed
:class:`BookError`, discriminated by :class:`BookErrorReason` so the route maps
each case to its HTTP status; the route stays HTTP-only.

The private :func:`_to_response` hand-maps a ``Book`` ORM row to a
:class:`BookResponse` (never dumps the ORM), exposing ``id`` / ``owner_id`` as
strings and omitting moderation internals.

The reader-safe book projection **left this module** in feature 022 (decision
D3): the whole reader surface now lives in :mod:`app.services.reader`, so "what
can a reader reach?" is answerable without auditing this twelve-function book
service. The URL it served (``GET /api/books/{book_id}/read``) is unchanged.

Skeleton (step 003): signatures + the error taxonomy are frozen; the function
bodies are UNIMPLEMENTED (raise ``NotImplementedError``). This module is
**extended** by steps 004 (read projections) and 005 (settings mutations) — the
``BookErrorReason`` enum, :func:`_to_response`, and the module structure are the
shared surface those steps build on; keep them open.
"""

import enum
from datetime import datetime, timezone

from app.db import book_members, books
from app.models.book import Book, BookState, Visibility
from app.models.book_member import BookMember, MemberRole
from app.models.schemas.books import (
    BookDetailResponse,
    BookListResponse,
    BookMemberResponse,
    BookResponse,
    CreateBookRequest,
)
from app.models.user import User
from app.services import authz
from app.services.authz import BookAccess, Capability


class BookErrorReason(str, enum.Enum):
    """Discriminator for :class:`BookError` — the book-service refusal taxonomy.

    Mirrors :class:`app.services.llm_servers.LlmServerErrorReason`. Frozen here
    and **extended** across steps 003/004/005 (shared enum). ``not_found`` maps
    to 404 at the route. Create + both lists in step 003 have no domain refusal
    of their own (401 is produced upstream by ``get_current_user``); the enum is
    seeded with ``not_found`` for the read/mutation steps that follow.

    Step 005 extends the taxonomy with the settings-mutation refusals. The route
    status map (``_BOOK_ERROR_STATUS``): ``not_found`` → 404;
    ``already_archived`` / ``not_archived`` / ``transfer_target_not_member`` /
    ``duplicate_member`` → 409 Conflict; ``remove_target_not_member`` → 404
    (removing a non-member — the membership resource does not exist).
    """

    not_found = "not-found"
    already_archived = "already-archived"
    not_archived = "not-archived"
    transfer_target_not_member = "transfer-target-not-a-member"
    duplicate_member = "duplicate-add-member"
    remove_target_not_member = "remove-target-not-a-member"


class BookError(Exception):
    """Raised by the book service for every domain refusal.

    Carries a :class:`BookErrorReason` discriminator (``reason``) plus a
    human-readable ``message``; the route branches on ``reason`` to pick the HTTP
    status. Mirrors :class:`app.services.llm_servers.LlmServerError`.
    """

    def __init__(self, reason: BookErrorReason, message: str = "") -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


def _to_response(book: Book) -> BookResponse:
    """Map a ``Book`` to a :class:`BookResponse` by hand (never dump the ORM).

    Surfaces ``id`` and ``owner_id`` as strings, copies the display /
    collaboration / visibility / state fields and timestamps, and omits the
    moderation triple and prompt/notes internals.

    Skeleton (step 003): UNIMPLEMENTED.
    """
    return BookResponse(
        id=str(book.id),
        owner_id=str(book.owner_id),
        title=book.title,
        description=book.description,
        collaboration_mode=book.collaboration_mode,
        visibility=book.visibility,
        state=book.state,
        created_at=book.created_at,
        modified_at=book.modified_at,
    )


async def create_book(request: CreateBookRequest, caller: User) -> BookResponse:
    """Create a book with ``caller`` as owner and return its :class:`BookResponse`.

    Builds a ``Book`` with ``owner_id = caller.id``, the requested
    ``collaboration_mode`` / ``visibility``, and defaults ``state = active``,
    ``system_prompt = ""``, ``active_notes = ""``, moderation fields ``None``, and
    ``created_at`` / ``modified_at`` via ``datetime.now(timezone.utc)``; persists
    via ``db/books.create`` and hand-maps the result. Creates no chapter skeleton
    (deferred). Realizes UC-021.

    Skeleton (step 003): UNIMPLEMENTED.
    """
    now = datetime.now(timezone.utc)
    book = Book(
        title=request.title,
        description=request.description,
        owner_id=caller.id,
        collaboration_mode=request.collaboration_mode,
        visibility=request.visibility,
        state=BookState.active,
        moderation_reason=None,
        moderated_by=None,
        moderated_at=None,
        system_prompt="",
        active_notes="",
        created_at=now,
        modified_at=now,
    )
    book = await books.create(book)
    return _to_response(book)


async def list_owned(caller: User) -> BookListResponse:
    """Return the books ``caller`` owns, mapped to :class:`BookResponse`.

    Reads via ``db/books.list_by_owner(caller.id)`` and wraps the mapped rows in a
    :class:`BookListResponse`. Realizes UC-022.

    Skeleton (step 003): UNIMPLEMENTED.
    """
    rows = await books.list_by_owner(caller.id)
    return BookListResponse(items=[_to_response(row) for row in rows])


async def list_shared(caller: User) -> BookListResponse:
    """Return the books shared with ``caller`` (co-author, not owner).

    Reads via ``db/books.list_shared(caller.id)`` and wraps the mapped rows in a
    :class:`BookListResponse`. Realizes UC-030.

    Skeleton (step 003): UNIMPLEMENTED.
    """
    rows = await books.list_shared(caller.id)
    return BookListResponse(items=[_to_response(row) for row in rows])


async def get_book_detail(access: BookAccess) -> BookDetailResponse:
    """Return the members-only :class:`BookDetailResponse` for ``access``'s book.

    Calls ``authz.require(access, Capability.view_book_detail)`` (owner/co-author
    only — a resolved reader is refused 403), loads the book via
    ``db/books.get_by_id`` and its co-authors via
    ``db/book_members.list_by_book``, and hand-maps both into a
    :class:`BookDetailResponse` (``members`` as :class:`BookMemberResponse` rows).
    Realizes UC-029 detail access (US-029.AC-2).

    Skeleton (step 004): UNIMPLEMENTED.
    """
    authz.require(access, Capability.view_book_detail)
    book = await books.get_by_id(access.book_id)
    if book is None:
        raise BookError(BookErrorReason.not_found, "Book not found")
    members = await book_members.list_by_book(access.book_id)
    base = _to_response(book)
    return BookDetailResponse(
        **base.model_dump(),
        members=[
            BookMemberResponse(
                user_id=str(member.user_id),
                role=member.role,
                created_at=member.created_at,
            )
            for member in members
        ],
    )


async def archive_book(access: BookAccess) -> BookResponse:
    """Archive ``access``'s book — set ``state = archived``, return the summary.

    Calls ``authz.require(access, Capability.archive_book)`` (owner-only — 403
    otherwise), loads the book, refuses with
    ``BookError(already_archived)`` when it is already ``archived``, else sets
    ``state = BookState.archived`` and ``modified_at`` via
    ``datetime.now(timezone.utc)``, persists via ``db/books.update`` and returns
    the mapped :class:`BookResponse`. Preserves every content field; touches no
    chapters (US-024.AC-4 deferred) and builds no write-refusal (US-024.AC-3
    deferred). Realizes UC-023 / US-024.AC-1, AC-2.

    Skeleton (step 005): UNIMPLEMENTED.
    """
    authz.require(access, Capability.archive_book)
    book = await books.get_by_id(access.book_id)
    if book is None:
        raise BookError(BookErrorReason.not_found, "Book not found")
    if book.state == BookState.archived:
        raise BookError(
            BookErrorReason.already_archived, "Book is already archived"
        )
    book.state = BookState.archived
    book.modified_at = datetime.now(timezone.utc)
    await books.update(book)
    return _to_response(book)


async def unarchive_book(access: BookAccess) -> BookResponse:
    """Unarchive ``access``'s book — set ``state = active``, return the summary.

    Calls ``authz.require(access, Capability.archive_book)`` (owner-only — the
    reversible return path shares the ``archive_book`` capability), loads the
    book, refuses with ``BookError(not_archived)`` when it is not currently
    ``archived``, else sets ``state = BookState.active`` and ``modified_at``,
    persists via ``db/books.update`` and returns the mapped
    :class:`BookResponse`. Realizes the reversible half of UC-023.

    Skeleton (step 005): UNIMPLEMENTED.
    """
    authz.require(access, Capability.archive_book)
    book = await books.get_by_id(access.book_id)
    if book is None:
        raise BookError(BookErrorReason.not_found, "Book not found")
    if book.state != BookState.archived:
        raise BookError(BookErrorReason.not_archived, "Book is not archived")
    book.state = BookState.active
    book.modified_at = datetime.now(timezone.utc)
    await books.update(book)
    return _to_response(book)


async def transfer_ownership(
    access: BookAccess, target_user_id: str
) -> BookResponse:
    """Transfer ownership of ``access``'s book to ``target_user_id``.

    Calls ``authz.require(access, Capability.transfer_ownership)`` (owner-only),
    resolves ``target_user_id`` (``str`` on the wire) to ``int`` and refuses with
    ``BookError(transfer_target_not_member)`` unless the target is a current
    co-author (a ``db/book_members.get_by_book_and_user`` row exists) — a
    non-member is never implicitly added (the resolved UC-024 ``_TBD_``). On
    success sets ``owner_id = target`` and ``modified_at``, persists via
    ``db/books.update`` and returns the mapped :class:`BookResponse`. Realizes
    UC-024 / US-025.AC-1.

    Skeleton (step 005): UNIMPLEMENTED.
    """
    authz.require(access, Capability.transfer_ownership)
    target = int(target_user_id)
    member = await book_members.get_by_book_and_user(access.book_id, target)
    if member is None:
        raise BookError(
            BookErrorReason.transfer_target_not_member,
            "Transfer target is not a co-author",
        )
    book = await books.get_by_id(access.book_id)
    if book is None:
        raise BookError(BookErrorReason.not_found, "Book not found")
    book.owner_id = target
    book.modified_at = datetime.now(timezone.utc)
    await books.update(book)
    return _to_response(book)


async def add_member(
    access: BookAccess, target_user_id: str
) -> BookDetailResponse:
    """Grant co-author access on ``access``'s book to ``target_user_id``.

    Calls ``authz.require(access, Capability.add_member)`` (owner-only), resolves
    ``target_user_id`` to ``int`` and creates a
    ``BookMember(role = MemberRole.co_author)`` via ``db/book_members.create``.
    The unique ``(book_id, user_id)`` constraint makes re-adding an existing
    member a ``BookError(duplicate_member)`` refusal, never a DB 500. Returns the
    refreshed :class:`BookDetailResponse` (carries the updated ``members`` list).
    Realizes UC-026 / US-027.AC-1.

    Skeleton (step 005): UNIMPLEMENTED.
    """
    authz.require(access, Capability.add_member)
    target = int(target_user_id)
    existing = await book_members.get_by_book_and_user(access.book_id, target)
    if existing is not None:
        raise BookError(
            BookErrorReason.duplicate_member, "User is already a co-author"
        )
    await book_members.create(
        BookMember(
            book_id=access.book_id,
            user_id=target,
            role=MemberRole.co_author,
            created_at=datetime.now(timezone.utc),
        )
    )
    return await get_book_detail(access)


async def remove_member(
    access: BookAccess, target_user_id: str
) -> BookDetailResponse:
    """Revoke ``target_user_id``'s co-author access on ``access``'s book.

    Calls ``authz.require(access, Capability.remove_member)`` (owner-only),
    resolves ``target_user_id`` to ``int`` and deletes the membership via
    ``db/book_members.delete``; a non-member target is refused with
    ``BookError(remove_target_not_member)`` (404). Access ends immediately. No
    block/attribution cascade (US-028.AC-2/AC-3 deferred). Returns the refreshed
    :class:`BookDetailResponse`. Realizes UC-027 / US-028.AC-1.

    Skeleton (step 005): UNIMPLEMENTED.
    """
    authz.require(access, Capability.remove_member)
    target = int(target_user_id)
    removed = await book_members.delete(access.book_id, target)
    if not removed:
        raise BookError(
            BookErrorReason.remove_target_not_member,
            "Remove target is not a co-author",
        )
    return await get_book_detail(access)


async def set_visibility(
    access: BookAccess, visibility: Visibility
) -> BookResponse:
    """Set ``access``'s book visibility to ``visibility``.

    Calls ``authz.require(access, Capability.set_visibility)`` (owner-only), sets
    ``visibility`` and ``modified_at``, persists via ``db/books.update`` and
    returns the mapped :class:`BookResponse`. Realizes UC-028 / US-029.AC-1,
    AC-2.

    Skeleton (step 005): UNIMPLEMENTED.
    """
    authz.require(access, Capability.set_visibility)
    book = await books.get_by_id(access.book_id)
    if book is None:
        raise BookError(BookErrorReason.not_found, "Book not found")
    book.visibility = visibility
    book.modified_at = datetime.now(timezone.utc)
    await books.update(book)
    return _to_response(book)
