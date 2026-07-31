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

Those "deliberately absent" notes scope to the **skeleton** paths above. Feature
015 extends this module with the chapter **body** (step 001) and the state
transitions (step 002), and those paths do carry an archived-book gate (D10), a
collaboration-mode gate on the body write (D11) and a version token (D1) — see
the 015 section at the foot of this module.

Skeleton (014 step 002 / 015 step 001): signatures + the error taxonomy are
frozen.
"""

import enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.db import books as books_db
from app.db import chapter_changes, chapter_note_changesets, chapter_text_revisions, chapters
from app.db import flags as flags_db
from app.models.book import BookState, CollaborationMode
from app.models.chapter import Chapter, ChapterState, SummaryStatus
from app.models.chapter_change import ChangeStatus, ChapterChange, PlacementKind
from app.models.chapter_notes import NoteStatus
from app.models.chapter_text_revision import ChapterTextRevision
from app.models.flag import FlagOrigin, FlagStatus
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
from app.services.authz import AccessRole, BookAccess, Capability

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, see finalize_close_turn
    # ``services/tools.py`` reaches this module's world through
    # ``services/close_tools.py``, so a runtime import of the tool context here
    # would close a cycle. The annotation is quoted instead — the
    # ``chapter_tools.py`` / ``codex_tools.py`` discipline, applied one layer up.
    from app.services.tools import ToolContext


class ChapterErrorReason(str, enum.Enum):
    """Discriminator for :class:`ChapterError` — the chapter-service refusal
    taxonomy.

    Mirrors :class:`app.services.books.BookErrorReason` in shape. Every other
    refusal on these paths belongs to someone else: a capability failure is
    ``authz.BookAuthorizationError`` (→ 403), a missing or invisible *book* is
    produced upstream by the ``book_access`` dependency (→ 404), and a malformed
    body is the framework's (→ 422).

    014 shipped the **first three** members; 015 step 001 appends the next four
    and 015 step 002 the last two. The existing three are never renamed,
    reordered or re-valued — ``routes/chapters.py``'s status map keys off them.

    The route status map (``_CHAPTER_ERROR_STATUS``): ``not_found`` → **404**,
    ``invalid_reorder_set`` → **400**, ``not_planned`` → **409**,
    ``chapter_not_open`` → **409**, ``stale_version`` → **409**,
    ``book_archived`` → **403**, ``proposal_mode_refused`` → **403**,
    ``chapter_not_closed`` → **409**, ``another_chapter_open`` → **409**.

    ``not_planned`` is **reused** by 015's open transition (a chapter that is not
    ``planned`` cannot be opened) rather than duplicated: the error carries
    ``(reason, message)``, so the message differs per call site while the status
    mapping stays in one place.
    """

    not_found = "chapter-not-found"
    not_planned = "chapter-not-planned"
    invalid_reorder_set = "invalid-reorder-set"
    # 015 step 001 — the body write path.
    #
    # ``chapter_not_open`` — a body write reached a chapter whose state is not
    # ``open`` (``planned``, ``closing`` and ``closed`` all refuse). A
    # state-machine constraint, not authorization: the caller *has* the
    # capability, so it is **409**. It is also the refusal 016 inherits for a
    # ``closing`` chapter, which is why the reason is stated in terms of "not
    # open" rather than "closed".
    #
    # ``stale_version`` — the submitted ``expected_version`` is not the
    # chapter's current ``Chapter.version``. **409** (UC-039, US-041.AC-1).
    #
    # ``book_archived`` — every body save and every state transition is refused
    # on an ``archived`` book (decision D10). **403**, not 409: under archive no
    # member holds the write capability, which is an access answer rather than a
    # resource-state one. Reads are **not** gated by it.
    #
    # ``proposal_mode_refused`` — a co-author's body write in a ``proposal``-mode
    # book, whose message names FEAT-010 as unbuilt (decision D11). **403**. The
    # owner is unaffected, and state transitions are never mode-qualified.
    chapter_not_open = "chapter-not-open"
    stale_version = "stale-version"
    book_archived = "book-archived"
    proposal_mode_refused = "proposal-mode-refused"
    # 015 step 002 — the three state transitions.
    #
    # ``chapter_not_closed`` — a **reopen** reached a chapter whose state is not
    # ``closed`` (``planned``, ``open`` and ``closing`` all refuse). **409**: a
    # state-machine constraint, not authorization — the owner *has* the
    # capability. The open transition does not need a member of its own; it
    # reuses ``not_planned`` above.
    #
    # ``another_chapter_open`` — an **open** or a **reopen** was refused because
    # some other chapter of the same book already holds the one-open slot, i.e.
    # is ``open`` **or** ``closing`` (decision D8's carve-out; CF1). **409**.
    # The ``closing`` half is unreachable in production until 016 writes that
    # state, and is deliberate rather than speculative — see
    # ``002.context.md``.
    chapter_not_closed = "chapter-not-closed"
    another_chapter_open = "another-chapter-open"


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
    / ``version``, **``summary`` / ``summary_status`` (016)** and both
    timestamps, and omits ``text`` and ``system_prompt``.
    """
    return ChapterResponse(
        id=str(chapter.id),
        book_id=str(chapter.book_id),
        ordinal=chapter.ordinal,
        title=chapter.title,
        state=chapter.state,
        sketch=chapter.sketch,
        version=chapter.version,
        # 016: the two continuity fields 014 reserved. Plain column copies —
        # both are ``None`` on a chapter that has never been closed.
        summary=chapter.summary,
        summary_status=chapter.summary_status,
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


# ---------------------------------------------------------------------------
# 015.chapter-writing-free-mode — the chapter body (step 001).
#
# Everything above is 014's and is reused unchanged: ``_resolve_chapter`` is
# still the single chapter→book enforcement point, and ``_to_response`` is still
# the single ``ChapterResponse`` mapper. The body needs its own mapper only
# because it is a different DTO (decision D13).
#
# The signatures below are frozen by the 015 step-001 skeleton record and are
# implemented here unchanged. The reason members above, the ``_Placement``
# structure and the two DTOs are declarative.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Placement:
    """The computed shape of the single :class:`ChapterChange` a save writes
    (decision D9) — a typed structure, not a dict, following
    ``services/tools.py``'s frozen-dataclass idiom for internal data passing.

    - ``kind`` — ``PlacementKind.append`` when the new body **starts with** the
      loaded body (pure growth at the end), ``PlacementKind.range`` otherwise.
    - ``line_from`` / ``line_to`` — both ``None`` for ``append``; ``1`` and the
      loaded body's ``len(splitlines())`` for ``range``. They mirror the
      nullable columns exactly.
    - ``text`` — what the change row stores: the appended remainder for
      ``append``, the whole new body for ``range``.
    """

    kind: PlacementKind
    line_from: int | None
    line_to: int | None
    text: str


def _require_not_archived(access: BookAccess) -> None:
    """Refuse every chapter **write** on an archived book (decision D10).

    Raises ``ChapterError(book_archived)`` when ``access.book_state`` is
    ``BookState.archived``; returns ``None`` otherwise. Called by every write
    path in this feature — the body save here, and step 002's three state
    transitions — immediately after that path's ``authz.require`` line and
    before any db read. **No read path calls it**: UC-023 makes archive a
    preserving, reversible state, so reading an archived book still works
    (:func:`get_chapter_text` deliberately has no archived gate).

    The refusal is **403** rather than 409 because under archive no member holds
    the write capability at all — an access answer, not a resource-state one.
    That the ordering with :func:`_require_writable_mode` is unobservable (both
    are 403) is why ``authz.require`` stays first: every guarded function in this
    codebase is shaped alike.
    """
    if access.book_state == BookState.archived:
        raise ChapterError(
            ChapterErrorReason.book_archived,
            "This book is archived, so its chapters cannot be changed. "
            "Restore the book to write in it again.",
        )
    return None


def _require_writable_mode(access: BookAccess) -> None:
    """Apply the collaboration-mode rule to a chapter **body** write (decision
    D11), mirroring ``services/codex.py::_require_writable_mode``.

    Raises ``ChapterError(proposal_mode_refused)`` when the caller's role is
    ``AccessRole.co_author`` **and** ``access.collaboration_mode`` is
    ``CollaborationMode.proposal``; returns ``None`` otherwise. The branch is on
    ``role == co_author`` rather than "not owner" so no future role slips
    through, and **the owner is always unaffected**. Free mode applies a
    co-author's write immediately.

    Its message names **FEAT-010** as unbuilt, so the author learns *why* rather
    than only *that* — the refusal text is what the client surfaces verbatim.
    ``services/codex.py`` is the shape to copy, never a module to import: the two
    services own their own reason taxonomies.

    Called by :func:`save_chapter_text` **only**. Step 002's transitions are
    owner-only and an owner is never held for review, so they do not call it.
    """
    if (
        access.role == AccessRole.co_author
        and access.collaboration_mode == CollaborationMode.proposal
    ):
        raise ChapterError(
            ChapterErrorReason.proposal_mode_refused,
            "This book is in proposal mode, so a co-author's chapter write must "
            "be held for the owner's review. That review surface is FEAT-010, "
            "which is not built yet, so the change cannot be accepted. Ask the "
            "owner to switch the book to free mode.",
        )
    return None


def _to_text_response(chapter: Chapter) -> ChapterTextResponse:
    """Map a ``Chapter`` to a :class:`ChapterTextResponse` by hand (never dump
    the ORM).

    The single place a chapter row becomes a body representation and the single
    place its snowflake id becomes a ``str`` on this sub-resource. Surfaces
    ``state``, ``text``, ``version`` and ``modified_at``; carries no
    caller-relative field (decision D14). Separate from :func:`_to_response`
    because it is a different DTO — 014's mapper is not insufficient, it simply
    answers a different resource.
    """
    return ChapterTextResponse(
        chapter_id=str(chapter.id),
        state=chapter.state,
        text=chapter.text,
        version=chapter.version,
        modified_at=chapter.modified_at,
    )


def _compute_placement(loaded_text: str, new_text: str) -> _Placement:
    """Derive the single change row's placement from the **loaded** body and the
    submitted body (decision D9). Pure: no session, no clock, no row, no id.

    - ``new_text.startswith(loaded_text)`` → **append**, both line bounds
      ``None``, ``text`` = the appended remainder.
    - otherwise → **range**, ``line_from = 1``,
      ``line_to = len(loaded_text.splitlines())``, ``text`` = the whole
      ``new_text``.

    ``splitlines()`` and not ``count("\\n") + 1``: a body ending in a newline
    would otherwise report a phantom trailing line, and ``018`` diffs against
    these bounds.

    The three degenerate cases are fixed by D9 and are not this function's to
    re-decide: a loaded body of ``""`` is an **append** carrying the whole new
    body (every string starts with ``""``); clearing a non-empty body to ``""``
    is a **range** carrying ``""``; and an unchanged body is an **append**
    carrying ``""`` — there is deliberately **no "unchanged" short-circuit**.

    Because the ``range`` branch is unreachable when the loaded body is ``""``,
    ``line_to`` is always ≥ 1. **Do not add a clamp** — one would hide a genuine
    bug if the starts-with rule were ever changed.
    """
    if new_text.startswith(loaded_text):
        return _Placement(
            kind=PlacementKind.append,
            line_from=None,
            line_to=None,
            text=new_text[len(loaded_text):],
        )
    return _Placement(
        kind=PlacementKind.range,
        line_from=1,
        line_to=len(loaded_text.splitlines()),
        text=new_text,
    )


async def get_chapter_text(
    access: BookAccess, chapter_id: str
) -> ChapterTextResponse:
    """Return one chapter's stored body as a :class:`ChapterTextResponse`
    (``GET /api/books/{book_id}/chapters/{chapter_id}/text``).

    Requires the existing ``Capability.read_book`` — no chapter-read capability
    is minted, exactly as 014's read paths do — then resolves the chapter via
    :func:`_resolve_chapter` (an unknown, non-numeric or **foreign** id is
    ``not_found``, never a permission failure) and maps it with
    :func:`_to_text_response`.

    **No archived gate and no collaboration-mode gate** (decision D10): a read
    is never refused for the book's state or mode, so a reader on a public
    archived book still gets the body.
    """
    authz.require(access, Capability.read_book)
    chapter = await _resolve_chapter(access, chapter_id)
    return _to_text_response(chapter)


async def save_chapter_text(
    access: BookAccess, chapter_id: str, request: UpdateChapterTextRequest
) -> ChapterTextResponse:
    """Replace an ``open`` chapter's whole body against a version token
    (``PUT …/text``; UC-038, UC-039, US-040, US-041; decisions D1, D7, D9).

    The order is the contract, and nothing is written before every refusal has
    been cleared:

    1. ``authz.require(access, Capability.write_chapter_text)`` — owner or
       co-author; a reader and a stranger are refused here (**403**);
    2. :func:`_require_not_archived`, then :func:`_require_writable_mode`;
    3. :func:`_resolve_chapter` — a chapter of another book is ``not_found``;
    4. ``ChapterError(chapter_not_open)`` unless ``chapter.state`` is
       ``ChapterState.open`` — ``planned``, ``closing`` and ``closed`` all refuse
       (US-040.AC-3, and the "no longer editable" half of US-038.AC-1);
    5. ``ChapterError(stale_version)`` unless ``request.expected_version ==
       chapter.version`` — a plain **int equality** check, not a timestamp
       comparison and with no tolerance handling (``domain-chapter.md`` →
       "Concurrency": ``Chapter.version`` is the single authority on whether the
       body has moved);
    6. :func:`_compute_placement` over the **loaded** body and ``request.text``;
    7. ``db/chapter_changes.create`` — one row: the computed placement,
       ``status = ChangeStatus.applied``, ``base_version =
       request.expected_version``, ``author_id = access.user_id`` (this is where
       US-040.AC-2's attribution lives), ``applied_by`` the same user, and
       ``applied_at`` / ``created_at`` stamped **here** (timestamps are the
       service's, never ``db/``'s);
    8. ``db/chapter_text_revisions.create`` — one row: ``applied_change_id`` the
       change from (7), ``text_before`` the **loaded** body, ``applied_by`` and
       ``applied_at`` stamped here. It must follow (7) because
       ``applied_change_id`` is a non-null FK;
    9. ``db/chapters.update`` — ``text = request.text``, ``version`` incremented
       by exactly one, ``modified_at`` stamped here. **Last**, because a body
       that has moved with no history behind it is the one failure that breaks
       revert irrecoverably;
    10. return :func:`_to_text_response` over the stored chapter.

    Steps 7–9 are three separate ``db/`` calls in three separate sessions
    (decision D7). That is accepted, not an oversight: no cross-entity ``db/``
    module is created and no session is threaded through — "one ``db/`` module
    per entity" holds, and the forced FK order is also the safest degradation
    order.

    The book id is never an argument; it comes from ``access``.
    """
    authz.require(access, Capability.write_chapter_text)
    _require_not_archived(access)
    _require_writable_mode(access)
    chapter = await _resolve_chapter(access, chapter_id)
    if chapter.state != ChapterState.open:
        raise ChapterError(
            ChapterErrorReason.chapter_not_open,
            "Only an open chapter's body may be written.",
        )
    if request.expected_version != chapter.version:
        raise ChapterError(
            ChapterErrorReason.stale_version,
            "This chapter has moved on since your draft was composed. "
            "Reload it and reconcile your changes before saving again.",
        )

    loaded_text = chapter.text
    placement = _compute_placement(loaded_text, request.text)
    now = datetime.now(timezone.utc)

    # (1) the change row — history first, and the non-null
    # ``ChapterTextRevision.applied_change_id`` forces this order anyway.
    change = await chapter_changes.create(
        ChapterChange(
            chapter_id=chapter.id,
            author_id=access.user_id,
            placement_kind=placement.kind,
            line_from=placement.line_from,
            line_to=placement.line_to,
            base_version=request.expected_version,
            text=placement.text,
            status=ChangeStatus.applied,
            applied_at=now,
            applied_by=access.user_id,
            created_at=now,
        )
    )
    # (2) the pre-apply snapshot of the body as it stood before this save.
    await chapter_text_revisions.create(
        ChapterTextRevision(
            chapter_id=chapter.id,
            applied_change_id=change.id,
            text_before=loaded_text,
            applied_by=access.user_id,
            applied_at=now,
        )
    )
    # (3) the chapter itself — LAST, so a body can never move with no history
    # behind it.
    chapter.text = request.text
    chapter.version = chapter.version + 1
    chapter.modified_at = now
    await chapters.update(chapter)
    return _to_text_response(chapter)


# ---------------------------------------------------------------------------
# 015.chapter-writing-free-mode — open / close / reopen (step 002).
#
# Three owner-only transitions over ``Chapter.state``. They reuse 014's
# ``_resolve_chapter`` and ``_to_response`` and step 001's
# :func:`_require_not_archived` unchanged, and each touches **``state`` and
# ``modified_at`` only** — never ``text``, ``version``, ``ordinal``, ``title``
# or ``sketch``, and never a ``ChapterChange`` or a ``ChapterTextRevision``.
#
# None of them is collaboration-mode qualified (decision D11): all three require
# ``Capability.set_chapter_state``, which is owner-only, and an owner is never
# held for review — so :func:`_require_writable_mode` is deliberately **not**
# called here.
#
# The signatures below are frozen by the 015 step-002 skeleton record and are
# implemented here unchanged.
# ---------------------------------------------------------------------------


async def _require_open_slot_free(access: BookAccess, chapter: Chapter) -> None:
    """Refuse when another chapter of ``access.book_id`` already holds the
    one-open slot (US-037, CF1, decision D8's carve-out).

    Loads the book's chapters via ``db/chapters.list_by_book(access.book_id)``,
    **skips the row being acted on** (matched on ``Chapter.id``), and raises
    ``ChapterError(another_chapter_open)`` when any remaining chapter's state is
    ``ChapterState.open`` **or** ``ChapterState.closing``. Returns ``None``
    otherwise.

    ``closing`` counts because a chapter parked mid-close has **not** released
    the slot — it is waiting on the owner (``domain-chapter.md``). Nothing in
    015 ever writes ``closing``, so that half of the condition is reachable only
    from a seeded row today; it is written now so 016 does not have to retrofit
    it. **This is one word in a condition, not close mechanics** — no continuity
    is drafted, read or approved anywhere in this module.

    Excluding the acted-on chapter is moot for :func:`open_chapter` (its chapter
    is ``planned``) and for :func:`reopen_chapter` (its chapter is ``closed``),
    but it is done explicitly so the guard stays honest if 016 ever calls it
    from a ``closing`` chapter's approve path.

    Callers invoke it **after** ``authz.require``, :func:`_require_not_archived`
    and :func:`_resolve_chapter`, and after their own state refusal — so a
    chapter in the wrong state answers with its own reason rather than with the
    slot's. No dedicated "is anything open" ``db/`` query exists or is added:
    that would put a domain rule in the data-access layer.
    """
    siblings = await chapters.list_by_book(access.book_id)
    for row in siblings:
        if row.id == chapter.id:
            continue
        if row.state in (ChapterState.open, ChapterState.closing):
            raise ChapterError(
                ChapterErrorReason.another_chapter_open,
                "Another chapter of this book is already open. "
                "Close it first — only one chapter may be open at a time.",
            )
    return None


async def open_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse:
    """Move a ``planned`` chapter to ``open`` (``POST …/open``; UC-035,
    US-036.AC-1, US-037).

    The fixed order, nothing written until every refusal has cleared:

    1. ``authz.require(access, Capability.set_chapter_state)`` — **owner only**;
       a co-author, a reader and a stranger are refused here (**403**,
       US-036.AC-2);
    2. :func:`_require_not_archived` (decision D10);
    3. :func:`_resolve_chapter` — another book's chapter is ``not_found``;
    4. ``ChapterError(not_planned)`` unless ``chapter.state`` is
       ``ChapterState.planned`` — 014's existing reason is **reused**, with this
       call site's own message; ``open``, ``closing`` and ``closed`` all refuse;
    5. :func:`_require_open_slot_free`;
    6. ``chapter.state = ChapterState.open``, ``modified_at`` stamped here via
       ``datetime.now(timezone.utc)``, then ``db/chapters.update``;
    7. return :func:`_to_response` over the stored chapter (014's DTO and 014's
       mapper — no transition DTO is minted).

    Touches ``state`` and ``modified_at`` **only**: no body, no version bump, no
    ordinal, no ``ChapterChange`` and no ``ChapterTextRevision``.
    """
    authz.require(access, Capability.set_chapter_state)
    _require_not_archived(access)
    chapter = await _resolve_chapter(access, chapter_id)
    if chapter.state != ChapterState.planned:
        raise ChapterError(
            ChapterErrorReason.not_planned,
            "Only a planned chapter may be opened.",
        )
    await _require_open_slot_free(access, chapter)
    chapter.state = ChapterState.open
    chapter.modified_at = datetime.now(timezone.utc)
    await chapters.update(chapter)
    return _to_response(chapter)


async def close_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse:
    """Open the close window: move an ``open`` chapter to ``closing``
    (``POST …/close``; UC-036, US-038.AC-1 / US-038.AC-3; decision D5).

    1. ``authz.require(access, Capability.set_chapter_state)`` — owner only
       (US-038.AC-2);
    2. :func:`_require_not_archived`;
    3. :func:`_resolve_chapter`;
    4. ``ChapterError(chapter_not_open)`` unless ``chapter.state`` is
       ``ChapterState.open`` — 015 step 001's reason **reused** with this call
       site's own message; ``planned``, ``closing`` and ``closed`` all refuse,
       and **no new reason member is minted** for the new destination;
    5. **delete every ``origin=check`` ``Flag`` on the chapter FIRST**
       (``db/flags.delete_check_flags_by_chapter``, decision D6). Only *this*
       run's findings may ever block the close, and an ``origin=person`` flag is
       advisory and survives untouched. Deleting before the state moves is what
       makes a failed write leave the chapter ``open`` with nothing claimed;
    6. ``chapter.state = ChapterState.closing`` — **not** ``closed``, which is
       what 015 shipped as a placeholder — ``modified_at`` stamped, then
       ``db/chapters.update``;
    7. return :func:`_to_response`.

    **No LLM call happens here** (decision D5): this endpoint only opens the
    window. The chat pane then posts the close turn, and
    :func:`finalize_close_turn` decides the outcome when that turn ends. No
    open-slot guard runs: ``closing`` still holds the slot
    (:func:`_require_open_slot_free` has always counted it), so nothing is
    released and nothing has to be re-checked.
    """
    authz.require(access, Capability.set_chapter_state)
    _require_not_archived(access)
    chapter = await _resolve_chapter(access, chapter_id)
    if chapter.state != ChapterState.open:
        raise ChapterError(
            ChapterErrorReason.chapter_not_open,
            "Only an open chapter may be closed.",
        )
    # (D6) The previous run's check findings go FIRST: only this run's findings
    # may block the close, and ``origin=person`` flags are advisory and are left
    # exactly as they are — the origin filter is the db query's, not a policy
    # applied to rows out here.
    await flags_db.delete_check_flags_by_chapter(chapter.id)
    chapter.state = ChapterState.closing
    chapter.modified_at = datetime.now(timezone.utc)
    await chapters.update(chapter)
    return _to_response(chapter)


async def reopen_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse:
    """Move a ``closed`` chapter back to ``open`` (``POST …/reopen``; UC-037,
    US-039.AC-1, AC-2).

    1. ``authz.require(access, Capability.set_chapter_state)`` — owner only;
    2. :func:`_require_not_archived`;
    3. :func:`_resolve_chapter`;
    4. ``ChapterError(chapter_not_closed)`` unless ``chapter.state`` is
       ``ChapterState.closed`` — ``planned``, ``open`` and ``closing`` all
       refuse;
    5. :func:`_require_open_slot_free` — the same guard :func:`open_chapter`
       runs, so the two transitions cannot drift (CF1);
    6. ``chapter.state = ChapterState.open``, ``modified_at`` stamped, then
       ``db/chapters.update``;
    7. return :func:`_to_response`.

    **A reopen moves no text**, so it writes neither a ``ChapterChange`` nor a
    ``ChapterTextRevision`` and leaves ``version`` alone. The variant history a
    later edit produces comes from the ordinary save path
    (:func:`save_chapter_text`) and belongs to ``018`` — nothing here marks a
    chapter as "reopened".

    **016 adds the stale-marking (US-055.AC-1).** A reopened chapter has moved
    on, so both continuity artifacts stop describing it: ``summary_status``
    becomes ``SummaryStatus.stale`` and, when a ``ChapterNoteChangeset`` row
    exists, its ``status`` becomes ``NoteStatus.stale``. Neither text is
    deleted — a stale summary is still the best account of the chapter until it
    closes again. A chapter with **no** changeset row is a no-op on that half
    (defensive; only reachable for a chapter closed under the pre-016 ungated
    path).
    """
    authz.require(access, Capability.set_chapter_state)
    _require_not_archived(access)
    chapter = await _resolve_chapter(access, chapter_id)
    if chapter.state != ChapterState.closed:
        raise ChapterError(
            ChapterErrorReason.chapter_not_closed,
            "Only a closed chapter may be reopened.",
        )
    await _require_open_slot_free(access, chapter)
    chapter.state = ChapterState.open
    # (016 / US-055.AC-1) The summary survives, but it no longer describes a
    # closed chapter: it is marked stale rather than cleared.
    chapter.summary_status = SummaryStatus.stale
    chapter.modified_at = datetime.now(timezone.utc)
    await chapters.update(chapter)
    # The changeset's half of the same claim. No row is a no-op, never an error.
    changeset = await chapter_note_changesets.get_by_chapter(chapter.id)
    if changeset is not None:
        changeset.status = NoteStatus.stale
        changeset.modified_at = chapter.modified_at
        await chapter_note_changesets.update(changeset)
    return _to_response(chapter)


# ---------------------------------------------------------------------------
# 016.chapter-close-continuity — the gated close (this feature).
#
# Three of this module's functions carry 016's changes, and **two of them keep
# their 015 signatures exactly**:
#
# - :func:`close_chapter` — MODIFIED. Its destination becomes ``closing``
#   instead of ``closed`` (the one constant 015's docstring named as 016's), and
#   it first deletes every ``origin=check`` ``Flag`` on the chapter
#   (``db/flags.delete_check_flags_by_chapter``, decision D6). It mints **no new
#   reason**: every non-``open`` source state keeps refusing with
#   ``ChapterErrorReason.chapter_not_open``.
# - :func:`reopen_chapter` — MODIFIED. On ``closed → open`` it additionally sets
#   ``Chapter.summary_status = SummaryStatus.stale`` and, when a
#   ``ChapterNoteChangeset`` row exists for the chapter, its ``status =
#   NoteStatus.stale`` (US-055.AC-1). A chapter with no changeset row is a no-op
#   on that half — defensive, and only reachable for a chapter closed under the
#   pre-016 ungated path.
# - :func:`cancel_close` and :func:`finalize_close_turn` are NEW, below.
#
# The two new functions are the only ones this skeleton declares; the two
# modifications above are body-level and are the coder's, so both existing
# functions are left exactly as 015 shipped them.
# ---------------------------------------------------------------------------


async def cancel_close(access: BookAccess, chapter_id: str) -> ChapterResponse:
    """Abandon a chapter's close run, returning it to ``open`` and discarding
    every draft artifact the run produced (``POST …/close/cancel``; decision D4,
    the Stop path — UC-074's "return to open", US-074.AC-1).

    In order:

    1. ``authz.require(access, Capability.set_chapter_state)`` — **owner only**,
       the very capability ``POST …/close`` requires, so no new capability is
       minted for the cancel;
    2. :func:`_require_not_archived`;
    3. :func:`_resolve_chapter` — another book's chapter is ``not_found``;
    4. **when ``chapter.state`` is not ``closing``: return the unchanged
       response** — a **200 no-op**, not a refusal. Cancelling a close that is
       not running is exactly what a client racing the turn's own completion
       does, and answering 409 there would surface a failure for something that
       already holds;
    5. otherwise wipe: ``chapter.state = ChapterState.open``,
       ``chapter.summary = None``, ``chapter.summary_status = None``,
       ``modified_at`` stamped here, ``db/chapters.update``, and
       ``db/chapter_note_changesets.delete_by_chapter(chapter.id)`` — the **same
       wipe** :func:`finalize_close_turn`'s failure branch performs, which is
       what makes D7's "nothing was ever applied" true: ``Book.active_notes`` is
       never written on this path, because the proposal only ever lived in the
       turn's :class:`~app.services.tools.ToolContext`;
    6. return :func:`_to_response` over the stored chapter.

    It touches no ``ChapterChange``, no ``ChapterTextRevision``, no ``version``
    and no ``Flag``: a cancelled run leaves the chapter's body and its warnings
    exactly as it found them.
    """
    authz.require(access, Capability.set_chapter_state)
    _require_not_archived(access)
    chapter = await _resolve_chapter(access, chapter_id)
    if chapter.state != ChapterState.closing:
        # A 200 NO-OP, not a refusal: cancelling a close that is not running is
        # exactly what a client racing the turn's own completion does, and a 409
        # there would surface a failure for something that already holds.
        return _to_response(chapter)
    await _wipe_close_artifacts(chapter)
    return _to_response(chapter)


async def _wipe_close_artifacts(chapter: Chapter) -> None:
    """Return ``chapter`` to ``open`` and discard everything a close run wrote.

    The **one** wipe, shared by :func:`cancel_close` and by
    :func:`finalize_close_turn`'s failure branch, so a stopped run and a failed
    one can never diverge: ``state`` back to ``open``, ``summary`` and
    ``summary_status`` cleared, ``modified_at`` stamped **here** (timestamps are
    the service's, never ``db/``'s), the chapter persisted, and the chapter's
    ``ChapterNoteChangeset`` row deleted.

    **``Book.active_notes`` is never touched.** That is what decision D7 buys:
    the run's proposal only ever lived in the turn's ``ToolContext``, so there is
    nothing applied to undo.

    The wipe is **uniform, not history-aware** (an accepted risk): a *re*-close
    that fails deletes the chapter's prior stale changeset along with this run's
    draft, since no changeset history mechanism exists.
    """
    chapter.state = ChapterState.open
    chapter.summary = None
    chapter.summary_status = None
    chapter.modified_at = datetime.now(timezone.utc)
    await chapters.update(chapter)
    # Deleting for a chapter with no changeset row is a no-op, which is what
    # makes the wipe idempotent.
    await chapter_note_changesets.delete_by_chapter(chapter.id)
    return None


async def finalize_close_turn(
    access: BookAccess,
    chapter_id: str,
    tool_context: "ToolContext",
) -> ChapterResponse:
    """Decide a close run's outcome deterministically once its turn has ended
    (decision D5 — "the frontend posts the turn, the backend decides"; UC-047,
    and UC-048 only in the divergent sense recorded in ``outcome.md``).

    Called **once** by ``services/chat_turn.py`` when a close-chapter turn
    reaches natural completion — success **or** an ``error`` frame — and skipped
    on a client cancellation, whose recovery is :func:`cancel_close`. The model
    never decides the outcome; this function reads four independent facts and
    routes:

    - ``Chapter.summary_status`` — is there a drafted summary?
    - the chapter's ``ChapterNoteChangeset.status`` — is there a drafted
      changeset?
    - ``tool_context.active_notes_proposal`` — did ``propose_active_notes`` run?
      **``""`` is a legitimate proposal; ``None`` (never called) is not**
      (decision D7);
    - any **open ``origin=check``** ``Flag`` on the chapter — did the consistency
      check find something blocking?

    **The clean branch** — ``summary_status == draft`` AND a changeset row exists
    with ``status == draft`` AND ``active_notes_proposal is not None`` AND no
    open ``origin=check`` flag:

        ``chapter.state = ChapterState.closed``,
        ``chapter.summary_status = SummaryStatus.approved``,
        ``changeset.status = NoteStatus.approved``,
        ``Book.active_notes = tool_context.active_notes_proposal``, then persist.

    Both artifacts become ``approved`` in the **same step** as ``closed``: there
    is no approval gate (decision D3).

    **Every other case** — including a ``None`` proposal — routes to ``open``
    with the artifacts wiped, exactly as :func:`cancel_close` wipes them
    (``summary`` / ``summary_status`` cleared, the changeset row deleted).
    **``Book.active_notes`` is never written on this branch**: treating an
    uncalled tool as an implicit ``""`` would silently erase every accumulated
    note in the book, which is the one failure that field exists to prevent.

    **It never raises for a business-rule outcome.** There is no refusal
    taxonomy here — every input combination has a defined destination — which is
    what lets ``chat_turn.py`` call it from a completion path that has no
    refusal channel left to speak on.

    The wipe is **uniform, not history-aware** (an accepted risk): a *re*-close
    that fails deletes the chapter's prior stale changeset along with this run's
    draft, since no changeset history mechanism exists.
    """
    # No ``authz.require`` and no archived gate: this is not an author-facing
    # entry point at all — ``chat_turn`` decides whether the finalize runs, and by
    # the time it calls there is no refusal channel left to speak on. Every input
    # combination below has a defined destination, so nothing here raises for a
    # business-rule outcome.
    chapter = await _resolve_chapter(access, chapter_id)

    changeset = await chapter_note_changesets.get_by_chapter(chapter.id)
    chapter_flags = await flags_db.list_by_chapter(chapter.id)
    blocked = any(
        flag.origin == FlagOrigin.check and flag.status == FlagStatus.open
        for flag in chapter_flags
    )
    proposal = tool_context.active_notes_proposal

    # THE FOUR FACTS. ``proposal is not None`` — never a truthiness test: ``""``
    # is a legitimate proposal (a book may genuinely end up with no live notes)
    # and "the tool was never called" is not. Conflating them would let an
    # uncalled tool erase every accumulated note in the book (decision D7).
    clean = (
        chapter.summary_status == SummaryStatus.draft
        and changeset is not None
        and changeset.status == NoteStatus.draft
        and proposal is not None
        and not blocked
    )

    if not clean:
        # Every other case — a missing summary, a missing or non-draft changeset,
        # an uncalled ``propose_active_notes`` and an open check finding alike —
        # takes the SAME wipe ``cancel_close`` performs, and ``Book.active_notes``
        # is not written.
        await _wipe_close_artifacts(chapter)
        return _to_response(chapter)

    now = datetime.now(timezone.utc)
    # Both artifacts become ``approved`` in the SAME step as ``closed``: there is
    # no approval gate (decision D3).
    chapter.state = ChapterState.closed
    chapter.summary_status = SummaryStatus.approved
    chapter.modified_at = now
    await chapters.update(chapter)

    # ``changeset`` is non-null on this branch — the ``clean`` test proved it —
    # but the narrowing is spelled out so the type stays honest.
    if changeset is not None:
        changeset.status = NoteStatus.approved
        changeset.modified_at = now
        await chapter_note_changesets.update(changeset)

    # THE ONLY WRITE OF ``Book.active_notes`` IN THE WHOLE FEATURE, and only from
    # the in-run proposal (decision D7). A missing book row is unreachable — the
    # chapter resolved inside it — and is a no-op rather than a raise.
    book = await books_db.get_by_id(access.book_id)
    if book is not None:
        book.active_notes = proposal if proposal is not None else ""
        book.modified_at = now
        await books_db.update(book)

    return _to_response(chapter)
