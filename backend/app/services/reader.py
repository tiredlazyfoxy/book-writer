"""Reader service — everything ACT-006 can reach (feature 022). Realizes the
reader half of FEAT-007: UC-029, US-030.

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). All persistence goes through the session-free ``app.db``
layer (namespace imports). Domain refusals raise the typed :class:`ReaderError`,
discriminated by :class:`ReaderErrorReason` so the route maps each case to its
HTTP status; the route stays HTTP-only. The shape mirrors
:class:`app.services.chapters.ChapterError` exactly — ``(reason, message="")``.

**Why a module of its own** (decision D3): UC-029 is an exclusion list, and "what
can a reader reach?" must be answerable from this module plus
``models/schemas/reader.py`` alone, rather than by auditing a twelve-route book
service. :func:`get_reader_book` **moved here** from ``services/books.py``; the
URLs it serves are unchanged.

Three properties this module is built on:

1. **Existence hiding is never re-derived here.** A book the caller has no
   relationship with is 404'd by ``authz.resolve_book_access`` before any of
   these functions runs, and a caller with no token is 401'd by
   ``get_current_user`` upstream. What this module adds is the *chapter*-level
   404 (2).
2. **A not-reader-visible chapter answers 404, indistinguishable from an unknown
   id, a non-numeric id and another book's chapter** (decision D5). A 403 would
   confirm a chapter exists at that id and let a reader walk the id space to
   reconstruct the author's unwritten skeleton — the enumeration-oracle reasoning
   ``authorization.md`` uses for a private book.
3. **The state filter and the ordinal sort run here, over the full row list**
   (decision D6): ``db.chapters.list_by_book`` takes no state filter, every state
   filter in the codebase today is service-side, and book-sized chapter counts
   make a filtered query unjustified. No ``db/chapters.py`` function is added.

``authz.require(access, Capability.read_book)`` is the first line of both
book-scoped entry points. It is unreachable today — ``resolve_book_access``
already 404s ``AccessRole.none`` and admin role resolution is deferred to
FEAT-011 — and is kept anyway (decision D7): it is the spine every book-scoped
service binds to, and the guard if the resolver ever admits another role. No new
``Capability`` and no new ``_CAPABILITY_MATRIX`` row.

:func:`list_public_books` is the one entry point that is **not** book-scoped
(D14): there is no ``book_id`` to resolve a role against, so it takes the
authenticated ``User`` directly and holds no ``BookAccess``.

Skeleton (feature 022): signatures, the error taxonomy and
:data:`READER_VISIBLE_STATES` are frozen.
"""

import enum

from app.db import books, chapters
from app.models.chapter import Chapter, ChapterState
from app.models.schemas.reader import (
    PublicBookListResponse,
    PublicBookRef,
    ReaderBookResponse,
    ReaderChapterRef,
    ReaderChapterResponse,
)
from app.models.user import User
from app.services import authz
from app.services.authz import BookAccess, Capability


class ReaderErrorReason(str, enum.Enum):
    """Discriminator for :class:`ReaderError` — the reader-service refusal
    taxonomy.

    Both members map to **404** in the route
    (``routes/reader.py::_READER_ERROR_STATUS``). ``chapter_not_found`` covers
    all five refusal sources at once — an unknown id, a non-numeric id, a chapter
    belonging to another book, a ``planned`` chapter and a ``closing`` chapter —
    deliberately indistinguishable from one another (decision D5).
    """

    # Values are the plan's Interface verbatim (underscored), deliberately NOT
    # re-spelled to the hyphenated house style of ``BookErrorReason`` /
    # ``ChapterErrorReason``: neither value ever reaches the wire (the route maps
    # ``reason`` to a status and passes ``message`` as the detail), so fidelity to
    # the frozen interface wins over cosmetic consistency.
    book_not_found = "book_not_found"
    chapter_not_found = "chapter_not_found"


class ReaderError(Exception):
    """Raised by the reader service for every domain refusal.

    Carries a :class:`ReaderErrorReason` discriminator (``reason``) plus a
    human-readable ``message``; the route branches on ``reason`` to pick the HTTP
    status. Mirrors :class:`app.services.chapters.ChapterError`.
    """

    def __init__(self, reason: ReaderErrorReason, message: str = "") -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


READER_VISIBLE_STATES: frozenset[ChapterState] = frozenset(
    {ChapterState.open, ChapterState.closed}
)
"""The chapter states a reader may see — ``open`` and ``closed``, nothing else
(decision D2).

``planned`` is a sketch: author working material that must never reach a reader.
``closing`` is a chapter mid-close-run, so a chapter briefly leaves the table of
contents and 404s while it closes, then reappears — an accepted cost, and no
reader-facing information travels in the flicker.

This constant is the single definition of "reader-visible": both
:func:`get_reader_book` (which filters the TOC with it) and
:func:`get_reader_chapter` (which 404s anything outside it) read it, so the two
surfaces cannot drift apart.
"""


async def _resolve_reader_chapter(
    access: BookAccess, chapter_id: str
) -> Chapter:
    """Return the **reader-visible** chapter ``chapter_id`` within
    ``access.book_id``, or raise ``ReaderError(chapter_not_found)``.

    Five refusal sources, one indistinguishable answer (decision D5): a
    non-numeric id, an unknown id, a chapter whose ``book_id`` differs from
    ``access.book_id``, a ``planned`` chapter and a ``closing`` chapter. Mirrors
    ``services/chapters.py::_resolve_chapter`` and adds the reader's state gate —
    the same ``READER_VISIBLE_STATES`` :func:`get_reader_book` filters the table
    of contents with, so a chapter absent from the TOC can never be fetched by
    guessing its id.

    Called **after** the caller's ``authz.require`` line, so a caller lacking the
    capability is refused before any row is read.
    """
    try:
        parsed_id = int(chapter_id)
    except (ValueError, TypeError):
        raise ReaderError(
            ReaderErrorReason.chapter_not_found, "Chapter not found."
        )
    chapter = await chapters.get_by_id(parsed_id)
    if (
        chapter is None
        or chapter.book_id != access.book_id
        or chapter.state not in READER_VISIBLE_STATES
    ):
        raise ReaderError(
            ReaderErrorReason.chapter_not_found, "Chapter not found."
        )
    return chapter


async def get_reader_book(access: BookAccess) -> ReaderBookResponse:
    """Return the reader-safe table of contents for ``access``'s book.

    Intent (UC-029, US-030.AC-1): ``authz.require(access,
    Capability.read_book)``; load the book via ``db/books.get_by_id`` and refuse
    with ``ReaderError(book_not_found)`` when it is gone; read every chapter via
    ``db/chapters.list_by_book(access.book_id)``, keep only the rows whose
    ``state`` is in :data:`READER_VISIBLE_STATES`, sort them by ``ordinal``
    ascending, and map each to a ``ReaderChapterRef(id=str(row.id),
    title=row.title)``. The ordinal never reaches the wire — list order *is*
    reading order.
    """
    authz.require(access, Capability.read_book)
    book = await books.get_by_id(access.book_id)
    if book is None:
        raise ReaderError(ReaderErrorReason.book_not_found, "Book not found.")
    rows = await chapters.list_by_book(access.book_id)
    visible = sorted(
        (row for row in rows if row.state in READER_VISIBLE_STATES),
        key=lambda row: row.ordinal,
    )
    return ReaderBookResponse(
        title=book.title,
        chapters=[
            ReaderChapterRef(id=str(row.id), title=row.title) for row in visible
        ],
    )


async def get_reader_chapter(
    access: BookAccess, chapter_id: str
) -> ReaderChapterResponse:
    """Return the reader-safe body of ``chapter_id`` within ``access``'s book.

    Intent (UC-029, US-030.AC-2): ``authz.require(access,
    Capability.read_book)``; resolve ``chapter_id`` and answer
    ``ReaderError(chapter_not_found)`` — never a 403, never a distinguishable
    variant — for **all five** refusal sources: a non-numeric id, an unknown id,
    a chapter whose ``book_id`` differs from ``access.book_id``, a ``planned``
    chapter and a ``closing`` chapter (decision D5). On success return
    ``ReaderChapterResponse(id=str(row.id), title=row.title, text=row.text)`` —
    the saved text only, no ``sketch``, ``summary``, ``state`` or ``version``.
    """
    authz.require(access, Capability.read_book)
    chapter = await _resolve_reader_chapter(access, chapter_id)
    return ReaderChapterResponse(
        id=str(chapter.id),
        title=chapter.title,
        text=chapter.text,
    )


async def list_public_books(caller: User) -> PublicBookListResponse:
    """Return the public books ``caller`` can discover but is not part of.

    Intent (UC-029 discovery, D13/D14): read
    ``db/books.list_public_for_reader(caller.id)`` — which applies all four
    exclusions (public visibility, ``active`` state, not owned by the caller, no
    ``BookMember`` row for the caller) — and map each row to a ``PublicBookRef``
    (``id`` as a string, ``title``, ``description``), wrapped in a
    :class:`PublicBookListResponse`. No capability check: there is no ``book_id``
    to resolve a role against, and the route's authenticated gate is the whole
    admission rule (D14).
    """
    rows = await books.list_public_for_reader(caller.id)
    return PublicBookListResponse(
        items=[
            PublicBookRef(
                id=str(row.id),
                title=row.title,
                description=row.description,
            )
            for row in rows
        ]
    )
