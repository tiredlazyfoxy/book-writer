"""Chapter service — the chapter skeleton's whole decision surface (feature 014,
step 002). Realizes FEAT-008: UC-031..034, US-032..035.

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). All persistence goes through the session-free
``app.db.chapters`` layer (namespace import). Domain refusals raise the typed
:class:`ChapterError`, discriminated by :class:`ChapterErrorReason` so the route
(step 003) maps each case to its HTTP status; the route stays HTTP-only.

Three invariants this module is built on:

1. **``authz.require`` is the first line of every entry point**, before any db
   read. That is what makes the ``403`` answer independent of whether a chapter
   row happens to exist — otherwise a ``404`` and a ``403`` would be
   distinguishable by which error surfaces first, leaking chapter existence to a
   caller who is not allowed to ask.
2. **The book id is never an argument.** It comes from :class:`BookAccess`, which
   the ``book_access`` dependency resolved, so no entry point can be aimed at a
   book the caller was not resolved against.
3. **No ``chapter_access`` dependency and no chapter→book resolver in ``authz``**
   (decision D4). :func:`_resolve_chapter` is the single place that enforces
   ``chapter.book_id == access.book_id``, and a mismatch is **not found**, never
   a permission failure.

The private :func:`_to_response` hand-maps a ``Chapter`` ORM row to a
:class:`ChapterResponse` (never dumps the ORM) and is the single place a
snowflake becomes a string.

Deliberately absent, and not oversights: no collaboration-mode check (no chapter
skeleton row in ``authorization.md``'s matrix is *(mode)*-qualified — every one
of these writes applies immediately, so ``services/codex.py``'s proposal refusal
is **not** copied); no version token and no bump on the sketch path (D6); no
state, body or version write on the reorder path (D5); no read or write of the
dormant ``Chapter.system_prompt`` column (D1).

Skeleton (014 step 002): signatures + the error taxonomy are frozen.
"""

import enum
from datetime import datetime, timezone

from app.db import chapters
from app.models.chapter import Chapter, ChapterState
from app.models.schemas.chapters import (
    ChapterListResponse,
    ChapterResponse,
    CreateChapterRequest,
    ReorderChaptersRequest,
    UpdateChapterSketchRequest,
)
from app.services import authz
from app.services.authz import AccessRole, BookAccess, Capability


class ChapterErrorReason(str, enum.Enum):
    """Discriminator for :class:`ChapterError` — the chapter-service refusal
    taxonomy, and it is **exactly three wide**.

    Mirrors :class:`app.services.books.BookErrorReason` in shape. Every other
    refusal on these paths belongs to someone else: a capability failure is
    ``authz.BookAuthorizationError`` (→ 403), a missing or invisible *book* is
    produced upstream by the ``book_access`` dependency (→ 404), and a malformed
    body is the framework's (→ 422).

    The route status map (step 003's ``_CHAPTER_ERROR_STATUS``):
    ``not_found`` → **404**, ``not_planned`` → **409**,
    ``invalid_reorder_set`` → **400**.
    """

    not_found = "chapter-not-found"
    not_planned = "chapter-not-planned"
    invalid_reorder_set = "invalid-reorder-set"


class ChapterError(Exception):
    """Raised by the chapter service for every domain refusal.

    Carries a :class:`ChapterErrorReason` discriminator (``reason``) plus a
    human-readable ``message``; the route branches on ``reason`` to pick the HTTP
    status. Mirrors :class:`app.services.books.BookError`.
    """

    def __init__(self, reason: ChapterErrorReason, message: str = "") -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


def _to_response(chapter: Chapter) -> ChapterResponse:
    """Map a ``Chapter`` to a :class:`ChapterResponse` by hand (never dump the
    ORM).

    The single mapper for every entry point, so no response can drift, and the
    single place a snowflake becomes a string: ``id`` and ``book_id`` are
    surfaced as ``str``. Copies ``ordinal`` / ``title`` / ``state`` / ``sketch``
    / ``version`` and both timestamps, and omits ``text``, ``summary``,
    ``summary_status`` and ``system_prompt``.
    """
    return ChapterResponse(
        id=str(chapter.id),
        book_id=str(chapter.book_id),
        ordinal=chapter.ordinal,
        title=chapter.title,
        state=chapter.state,
        sketch=chapter.sketch,
        version=chapter.version,
        created_at=chapter.created_at,
        modified_at=chapter.modified_at,
    )


async def _resolve_chapter(access: BookAccess, chapter_id: str) -> Chapter:
    """Return the chapter ``chapter_id`` **within** ``access.book_id``.

    An unknown id, a non-numeric id and a chapter whose ``book_id`` differs from
    ``access.book_id`` all raise ``ChapterError(not_found)`` — another book's
    chapter is never returned and its existence is never confirmed. Every entry
    point that names a chapter goes through this function; it is what replaces a
    ``chapter_access`` dependency (decision D4).

    Callers invoke it **after** their ``authz.require`` line, so a caller lacking
    the capability is refused before any row is read.
    """
    try:
        parsed_id = int(chapter_id)
    except (ValueError, TypeError):
        raise ChapterError(ChapterErrorReason.not_found, "Chapter not found.")
    chapter = await chapters.get_by_id(parsed_id)
    if chapter is None or chapter.book_id != access.book_id:
        raise ChapterError(ChapterErrorReason.not_found, "Chapter not found.")
    return chapter


async def list_chapters(access: BookAccess) -> ChapterListResponse:
    """Return ``access.book_id``'s chapters as a :class:`ChapterListResponse`.

    Requires the existing ``Capability.read_book`` (reused unchanged — no
    chapter-read capability is minted). Reads
    ``db/chapters.list_by_book(access.book_id)``, orders the mapped rows by
    ``ordinal`` **ascending**, and sets ``can_reorder`` from
    ``access.role == AccessRole.owner`` — an affordance hint only; enforcement
    lives on :func:`reorder_chapters`.
    """
    authz.require(access, Capability.read_book)
    rows = await chapters.list_by_book(access.book_id)
    return ChapterListResponse(
        chapters=[
            _to_response(row) for row in sorted(rows, key=lambda r: r.ordinal)
        ],
        can_reorder=access.role == AccessRole.owner,
    )


async def get_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse:
    """Return one chapter of ``access.book_id`` as a :class:`ChapterResponse`.

    Requires the existing ``Capability.read_book``, then resolves the chapter via
    :func:`_resolve_chapter` (so an unknown, non-numeric or foreign id is
    ``not_found``) and maps it.
    """
    authz.require(access, Capability.read_book)
    chapter = await _resolve_chapter(access, chapter_id)
    return _to_response(chapter)


async def add_chapter(
    access: BookAccess, request: CreateChapterRequest
) -> ChapterResponse:
    """Append a new ``planned`` chapter to ``access.book_id`` (UC-031 /
    US-032.AC-1).

    Requires ``Capability.add_chapter`` (owner or co-author). Computes the next
    ordinal from the book's current chapters — **one past the current highest
    ordinal**, not a count, because removal deliberately leaves a gap; an empty
    book yields ``1``. Stores ``state = ChapterState.planned``, the submitted
    ``title`` and ``sketch``, ``text = ""`` (an initialisation, not a body write:
    no ``ChapterChange``, no version bump), ``version`` at its model default, and
    both ``created_at`` / ``modified_at`` stamped here via
    ``datetime.now(timezone.utc)`` — timestamps are the service's, never the db
    layer's. ``ordinal`` and ``state`` are required-without-default columns and
    must both be supplied explicitly. Returns the stored chapter's response.
    """
    authz.require(access, Capability.add_chapter)
    existing = await chapters.list_by_book(access.book_id)
    next_ordinal = max((row.ordinal for row in existing), default=0) + 1
    now = datetime.now(timezone.utc)
    chapter = Chapter(
        book_id=access.book_id,
        ordinal=next_ordinal,
        title=request.title,
        state=ChapterState.planned,
        sketch=request.sketch,
        text="",
        created_at=now,
        modified_at=now,
    )
    chapter = await chapters.create(chapter)
    return _to_response(chapter)


async def update_sketch(
    access: BookAccess, chapter_id: str, request: UpdateChapterSketchRequest
) -> ChapterResponse:
    """Replace a ``planned`` chapter's sketch (UC-033 / US-034.AC-1, AC-2).

    Requires ``Capability.edit_chapter_sketch`` (owner or co-author), resolves
    the chapter, and refuses with ``ChapterError(not_planned)`` when its state is
    anything but ``ChapterState.planned`` — a state-machine constraint that
    applies even to the owner, which the route answers **409**, not 403 (the
    caller *has* the capability). Otherwise writes the new ``sketch`` and stamps
    ``modified_at``, persists via ``db/chapters.update`` and returns the stored
    response.

    **Last write wins** (decision D6): no version token is accepted and
    ``version`` is **not** bumped — it tracks the body, which this path never
    touches.
    """
    authz.require(access, Capability.edit_chapter_sketch)
    chapter = await _resolve_chapter(access, chapter_id)
    if chapter.state != ChapterState.planned:
        raise ChapterError(
            ChapterErrorReason.not_planned,
            "Only a planned chapter's sketch may be edited.",
        )
    chapter.sketch = request.sketch
    chapter.modified_at = datetime.now(timezone.utc)
    await chapters.update(chapter)
    return _to_response(chapter)


async def remove_chapter(access: BookAccess, chapter_id: str) -> None:
    """Remove a ``planned`` chapter from ``access.book_id`` (UC-034 /
    US-035.AC-1, AC-2).

    Requires ``Capability.remove_chapter`` (owner or co-author), resolves the
    chapter, refuses with ``ChapterError(not_planned)`` when its state is
    anything but ``ChapterState.planned`` (→ 409), else deletes it via
    ``db/chapters.delete``. Returns nothing.

    **The remaining ordinals are not renumbered** — the gap is deliberate and
    invisible to a caller, since every list is ordered by ordinal ascending.
    Only :func:`reorder_chapters` rewrites ordinals.
    """
    authz.require(access, Capability.remove_chapter)
    chapter = await _resolve_chapter(access, chapter_id)
    if chapter.state != ChapterState.planned:
        raise ChapterError(
            ChapterErrorReason.not_planned,
            "Only a planned chapter may be removed.",
        )
    await chapters.delete(chapter.id)
    return None


async def reorder_chapters(
    access: BookAccess, request: ReorderChaptersRequest
) -> ChapterListResponse:
    """Rewrite ``access.book_id``'s chapter ordinals to ``1..N`` in the submitted
    order (UC-032 / US-033.AC-1, AC-2, decisions D3 and D5).

    Requires ``Capability.set_chapter_order`` — **owner only**; a co-author is
    refused by ``authz`` and no ordinal changes. Loads the book's current
    chapters and **validates the whole submitted list before any write**: it must
    be exactly the book's current chapter set — same length, no duplicates, no
    unknown or foreign ids, nothing missing — raising
    ``ChapterError(invalid_reorder_set)`` otherwise (→ 400; the body is
    structurally valid, so this is not a 422). Validating up front is what makes
    "an invalid list changes no ordinal" true without a transaction spanning the
    db module: ``db/chapters.update`` commits per row by design, and no bulk
    writer is added, because that would move the ``1..N`` rule out of the
    service.

    Then writes each chapter's ``ordinal`` to its 1-based position in the
    submitted list, stamping ``modified_at``, and returns the freshly ordered
    :class:`ChapterListResponse`. It touches ``ordinal`` and ``modified_at``
    **only** — never ``state``, never ``text``, never ``version`` — which is why
    it is allowed while a chapter is ``open`` (D5 closes UC-032's ``_TBD``).
    """
    authz.require(access, Capability.set_chapter_order)
    current = await chapters.list_by_book(access.book_id)
    by_id = {str(row.id): row for row in current}
    submitted = list(request.chapter_ids)

    # Validate the WHOLE list before touching a single ordinal: same length as
    # the book's current chapter set, no duplicates, and every id known to this
    # book (an unknown or another book's id is absent from ``by_id``). Together
    # those three make the submitted list exactly the current set.
    if (
        len(submitted) != len(current)
        or len(set(submitted)) != len(submitted)
        or any(chapter_id not in by_id for chapter_id in submitted)
    ):
        raise ChapterError(
            ChapterErrorReason.invalid_reorder_set,
            "The submitted order must list exactly the book's chapters once each.",
        )

    now = datetime.now(timezone.utc)
    for position, chapter_id in enumerate(submitted, start=1):
        chapter = by_id[chapter_id]
        chapter.ordinal = position
        chapter.modified_at = now
        await chapters.update(chapter)

    return ChapterListResponse(
        chapters=[_to_response(by_id[chapter_id]) for chapter_id in submitted],
        can_reorder=access.role == AccessRole.owner,
    )
