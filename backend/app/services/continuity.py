"""Continuity service — the read/edit surfaces over the book's live state notes,
a chapter's note changeset and the per-chapter continuity roll-up (feature 016).

Realizes FEAT-012: UC-049, UC-050, UC-051, UC-089, UC-091; US-052, US-053.AC-1,
US-054, US-104, US-106.AC-2 / AC-3.

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). All persistence goes through the session-free ``app.db``
modules (namespace imports). Domain refusals raise the typed
:class:`ContinuityError`, discriminated by :class:`ContinuityErrorReason` so
``routes/continuity.py`` maps each case to its HTTP status; the route stays
HTTP-only.

It is the **sibling** of ``services/chapters.py`` and ``services/flags.py`` and
copies their grain rather than importing from them: each service owns its own
refusal taxonomy, and a shared abstraction over three three-member enums would be
premature (the ``chapter_tools.py`` / ``codex_tools.py`` precedent, one layer up).

Three invariants, inherited verbatim from ``services/chapters.py``:

1. **The membership / capability gate is the first line of every entry point**,
   before any db read, so a ``403`` never depends on whether a row happens to
   exist.
2. **The book id is never an argument** — it comes from :class:`BookAccess`,
   which the ``book_access`` dependency resolved.
3. **A chapter is resolved against ``access.book_id``**, and a mismatch is
   ``chapter_not_found``, never a permission failure.

Two shapes this module fixes, both deliberate:

- **Viewing is gated by plain membership, not by a capability** (decision D9):
  ``role not in {owner, co_author}`` is
  :attr:`ContinuityErrorReason.not_a_member` → **403**. Only the *edit* path goes
  through ``authz.require(Capability.edit_state_notes)``.
- **A chapter with no ``ChapterNoteChangeset`` row answers a default-empty
  200**, not a 404 — the ``ChapterAuthorPrompt`` "no row yet" convention.

Skeleton (016): the signatures and the error taxonomy are frozen; the four entry
point bodies are UNIMPLEMENTED (raise ``NotImplementedError``).
"""

import enum
from datetime import datetime, timezone

from app.db import books as books_db
from app.db import chapter_note_changesets
from app.db import chapters as chapters_db
from app.db import flags as flags_db
from app.models.book import BookState, CollaborationMode
from app.models.chapter import Chapter
from app.models.chapter_notes import ChapterNoteChangeset
from app.models.flag import Flag, FlagStatus
from app.models.schemas.continuity import (
    BookContinuityResponse,
    BookStateNotesResponse,
    ChapterContinuityResponse,
    ChapterNoteChangesetResponse,
    UpdateBookStateNotesRequest,
)
from app.models.schemas.flags import FlagResponse
from app.services import authz
from app.services.authz import AccessRole, BookAccess, Capability

# The two roles that may see a book's continuity material at all (decision D9).
# Plain membership, not a capability: the matrix maps capability → role set and
# already carries enough ``{owner, co_author}`` rows, and D9 fixed the count of
# new capabilities at three — none of them a *read* one.
_MEMBER_ROLES: frozenset[AccessRole] = frozenset(
    {AccessRole.owner, AccessRole.co_author}
)


class ContinuityErrorReason(str, enum.Enum):
    """Discriminator for :class:`ContinuityError` — the continuity-service refusal
    taxonomy. Mirrors :class:`app.services.chapters.ChapterErrorReason` in shape.

    Every other refusal on these paths belongs to someone else: a missing or
    invisible *book* is produced upstream by the ``book_access`` dependency
    (→ 404), and a malformed body is the framework's (→ 422).

    The route status map (``routes/continuity.py``): ``not_a_member`` → **403**,
    ``book_archived`` → **403**, ``proposal_mode_refused`` → **403**,
    ``chapter_not_found`` → **404**.

    ``not_a_member`` is a **403 rather than a 404** because the book itself is
    legitimately visible to the caller — a reader on a public book can see the
    book and is refused its continuity material (the members-only rule
    ``authorization.md`` states for the codex, applied here). Existence hiding
    already happened upstream.
    """

    not_a_member = "not-a-member"
    book_archived = "book-archived"
    proposal_mode_refused = "proposal-mode-refused"
    chapter_not_found = "chapter-not-found"


class ContinuityError(Exception):
    """Raised by the continuity service for every domain refusal.

    Carries a :class:`ContinuityErrorReason` discriminator (``reason``) plus a
    human-readable ``message``; the route branches on ``reason`` to pick the HTTP
    status and passes ``message`` through as the ``detail``. Mirrors
    :class:`app.services.chapters.ChapterError`.
    """

    def __init__(self, reason: ContinuityErrorReason, message: str = "") -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


def _require_member(access: BookAccess) -> None:
    """Refuse a caller who is not a member of the book (decision D9).

    Raises ``ContinuityError(not_a_member)`` — **403** — when ``access.role`` is
    outside ``{owner, co_author}``; returns ``None`` otherwise. It is the first
    line of every *read* entry point here, before any db read, so the answer
    never depends on whether a row happens to exist. The *edit* path goes through
    ``authz.require(Capability.edit_state_notes)`` instead, which is the only
    capability this service names.
    """
    if access.role not in _MEMBER_ROLES:
        raise ContinuityError(
            ContinuityErrorReason.not_a_member,
            "This book's continuity material is for its authors. "
            "Ask the owner to add you as a co-author.",
        )
    return None


def _require_not_archived(access: BookAccess) -> None:
    """Refuse a continuity **write** on an archived book (**403**).

    ``services/chapters.py:_require_not_archived``'s rule restated in this
    service's own taxonomy — the two services own their own reasons and neither
    imports the other. **No read path calls it**: archive is preserving and
    reversible (UC-023), so an archived book's notes still read.
    """
    if access.book_state == BookState.archived:
        raise ContinuityError(
            ContinuityErrorReason.book_archived,
            "This book is archived, so its state notes cannot be changed. "
            "Restore the book to write in it again.",
        )
    return None


def _require_writable_mode(access: BookAccess) -> None:
    """Apply the collaboration-mode rule to the state-notes write (decision D9).

    Raises ``ContinuityError(proposal_mode_refused)`` — **403** — when the
    caller's role is ``AccessRole.co_author`` **and** the book's
    ``collaboration_mode`` is ``CollaborationMode.proposal``. The branch is on
    ``role == co_author`` rather than "not owner", exactly as
    ``services/chapters.py:_require_writable_mode`` is, so **the owner is never
    refused for mode** and no future role slips through.

    Its message names **FEAT-010** as the unbuilt proposal-holding mechanism, so
    US-053.AC-2's gap stays visible rather than silently violated.
    """
    if (
        access.role == AccessRole.co_author
        and access.collaboration_mode == CollaborationMode.proposal
    ):
        raise ContinuityError(
            ContinuityErrorReason.proposal_mode_refused,
            "This book is in proposal mode, so a co-author's change to the "
            "state notes must be held for the owner's review. That review "
            "surface is FEAT-010, which is not built yet, so the change cannot "
            "be accepted. Ask the owner to switch the book to free mode.",
        )
    return None


async def _resolve_chapter(access: BookAccess, chapter_id: str) -> Chapter:
    """Return the chapter ``chapter_id`` **within** ``access.book_id``.

    ``services/chapters.py:_resolve_chapter``'s three-way rule in this service's
    taxonomy: a non-numeric id, an unknown id and a chapter belonging to another
    book are all ``ContinuityError(chapter_not_found)`` — **404**, never a
    permission failure, and another book's chapter is never returned nor its
    existence confirmed.
    """
    try:
        parsed_id = int(chapter_id)
    except (ValueError, TypeError):
        raise ContinuityError(
            ContinuityErrorReason.chapter_not_found, "Chapter not found."
        )
    chapter = await chapters_db.get_by_id(parsed_id)
    if chapter is None or chapter.book_id != access.book_id:
        raise ContinuityError(
            ContinuityErrorReason.chapter_not_found, "Chapter not found."
        )
    return chapter


def _to_changeset_response(
    chapter_id: int, row: ChapterNoteChangeset | None
) -> ChapterNoteChangesetResponse:
    """Map a chapter's changeset row — or its **absence** — to the DTO.

    ``None`` yields the **default-empty** body (all three texts ``""``,
    ``status`` ``None``, both timestamps ``None``), which is what makes
    :func:`get_chapter_changeset` a 200 rather than a 404 for a chapter that has
    never been closed (the ``ChapterAuthorPromptResponse`` convention). The
    single place a snowflake becomes a string on this resource.
    """
    if row is None:
        return ChapterNoteChangesetResponse(
            chapter_id=str(chapter_id),
            added="",
            modified="",
            deleted="",
            status=None,
            created_at=None,
            modified_at=None,
        )
    return ChapterNoteChangesetResponse(
        chapter_id=str(chapter_id),
        added=row.added,
        modified=row.modified,
        deleted=row.deleted,
        status=row.status,
        created_at=row.created_at,
        modified_at=row.modified_at,
    )


def _to_flag_response(flag: Flag) -> FlagResponse:
    """Map a ``Flag`` row to its DTO by hand (never dump the ORM).

    Deliberately a **copy** of ``services/flags.py``'s mapper rather than an
    import of it: the two services are siblings that own their own taxonomies and
    neither imports the other, and a shared abstraction over one six-line mapper
    would be premature (the ``chapter_tools.py`` / ``codex_tools.py`` precedent).
    """
    return FlagResponse(
        id=str(flag.id),
        chapter_id=str(flag.chapter_id),
        origin=flag.origin,
        comment=flag.comment,
        status=flag.status,
        created_by=str(flag.created_by),
        created_at=flag.created_at,
        resolved_by=None if flag.resolved_by is None else str(flag.resolved_by),
        resolved_at=flag.resolved_at,
    )


async def get_state_notes(access: BookAccess) -> BookStateNotesResponse:
    """Return the book's live state notes (``GET …/state-notes``; UC-049 /
    US-052.AC-1).

    Refuses ``ContinuityError(not_a_member)`` when ``access.role`` is not in
    ``{owner, co_author}`` — plain membership, no capability (decision D9) — then
    reads the ``Book`` row and maps ``active_notes`` and the row's ``modified_at``
    into a :class:`BookStateNotesResponse`. ``""`` is a normal loaded value, never
    an absence.

    **No archived gate and no collaboration-mode gate**: a read is never refused
    for the book's state or mode, exactly as ``chapters.get_chapter_text`` is not.
    """
    _require_member(access)
    book = await books_db.get_by_id(access.book_id)
    if book is None:
        # Unreachable: the ``book_access`` dependency resolved this book before
        # the route ran. Answered as ``not_a_member`` rather than invented as an
        # empty note set — existence hiding already happened upstream.
        raise ContinuityError(
            ContinuityErrorReason.not_a_member, "This book is not available."
        )
    return BookStateNotesResponse(
        book_id=str(book.id),
        active_notes=book.active_notes,
        modified_at=book.modified_at,
    )


async def update_state_notes(
    access: BookAccess, body: UpdateBookStateNotesRequest
) -> BookStateNotesResponse:
    """Replace the book's live state notes (``PUT …/state-notes``; UC-050's
    direct-edit path / US-053.AC-1).

    The order is the contract, and nothing is written before every refusal has
    cleared:

    1. ``authz.require(access, Capability.edit_state_notes)`` — owner or
       co-author; a reader and a stranger are refused here (**403**);
    2. ``ContinuityError(book_archived)`` when ``access.book_state`` is
       ``archived`` — the ``chapters._require_not_archived`` rule, restated for
       this service's own taxonomy (**403**);
    3. ``ContinuityError(proposal_mode_refused)`` when ``access.role`` is
       ``co_author`` **and** ``access.collaboration_mode`` is ``proposal`` — the
       same ``role == co_author`` branch (never "not owner")
       ``chapters._require_writable_mode`` applies, so **the owner is never
       refused for mode**. Its message must name **FEAT-010** as the unbuilt
       proposal-holding mechanism, so US-053.AC-2's gap stays visible instead of
       being silently violated (decision D9);
    4. write ``Book.active_notes = body.active_notes`` and stamp the row's
       ``modified_at`` **here** (timestamps are the service's, never ``db/``'s),
       persist, and return the stored :class:`BookStateNotesResponse`.

    **Last write wins**: the note set carries no version token.
    """
    authz.require(access, Capability.edit_state_notes)
    _require_not_archived(access)
    _require_writable_mode(access)
    book = await books_db.get_by_id(access.book_id)
    if book is None:  # unreachable — see :func:`get_state_notes`
        raise ContinuityError(
            ContinuityErrorReason.not_a_member, "This book is not available."
        )
    # ``""`` is a legitimate value (an author clearing the set), so the text is
    # taken verbatim — no trimming and no emptiness check.
    book.active_notes = body.active_notes
    book.modified_at = datetime.now(timezone.utc)
    await books_db.update(book)
    return BookStateNotesResponse(
        book_id=str(book.id),
        active_notes=book.active_notes,
        modified_at=book.modified_at,
    )


async def get_chapter_changeset(
    access: BookAccess, chapter_id: str
) -> ChapterNoteChangesetResponse:
    """Return one chapter's note changeset (``GET …/chapters/{chapter_id}/notes``;
    UC-051 / US-054.AC-1).

    Refuses ``ContinuityError(not_a_member)`` for a role outside
    ``{owner, co_author}``, then resolves the chapter **within ``access.book_id``**
    — an unknown, non-numeric or foreign id is
    ``ContinuityError(chapter_not_found)`` (**404**), never a permission failure.

    A chapter with **no ``ChapterNoteChangeset`` row yet** answers a
    **default-empty 200** — ``added`` / ``modified`` / ``deleted`` all ``""``,
    ``status`` ``None``, both timestamps ``None`` — matching the
    ``ChapterAuthorPromptResponse`` "no row yet" convention rather than a 404. A
    chapter that has never been closed is a normal chapter, not a missing
    resource.
    """
    _require_member(access)
    chapter = await _resolve_chapter(access, chapter_id)
    row = await chapter_note_changesets.get_by_chapter(chapter.id)
    return _to_changeset_response(chapter.id, row)


async def get_book_continuity(access: BookAccess) -> BookContinuityResponse:
    """Return the book's per-chapter continuity roll-up (``GET …/continuity``;
    UC-089 / UC-091, US-104.AC-1 / US-106.AC-2 / AC-3).

    Refuses ``ContinuityError(not_a_member)`` for a role outside
    ``{owner, co_author}``, then builds **one**
    :class:`~app.models.schemas.continuity.ChapterContinuityResponse` per chapter
    of the book, in **ordinal ascending** order, carrying:

    - the chapter's ``title`` / ``ordinal`` / ``summary`` / ``summary_status``;
    - its ``changeset``, or ``None`` when the chapter has no row (nullable here,
      unlike :func:`get_chapter_changeset`'s default-empty body);
    - ``warnings`` — the chapter's **open** flags only, of **both** origins
      (``check`` and ``person``). Resolved flags are the flag-list endpoint's.
    """
    _require_member(access)
    rows = await chapters_db.list_by_book(access.book_id)
    items: list[ChapterContinuityResponse] = []
    for chapter in sorted(rows, key=lambda row: row.ordinal):
        changeset = await chapter_note_changesets.get_by_chapter(chapter.id)
        chapter_flags = await flags_db.list_by_chapter(chapter.id)
        items.append(
            ChapterContinuityResponse(
                chapter_id=str(chapter.id),
                title=chapter.title,
                ordinal=chapter.ordinal,
                summary=chapter.summary,
                summary_status=chapter.summary_status,
                # NULLABLE here, unlike the dedicated endpoint's default-empty
                # body: in a list, "this chapter has no changeset" is a fact
                # worth carrying as ``None``.
                changeset=(
                    None
                    if changeset is None
                    else _to_changeset_response(chapter.id, changeset)
                ),
                # OPEN flags only, of BOTH origins — this is the roll-up of what
                # still needs attention; the flag-list endpoint carries the whole
                # history.
                warnings=[
                    _to_flag_response(flag)
                    for flag in chapter_flags
                    if flag.status == FlagStatus.open
                ],
            )
        )
    return BookContinuityResponse(items=items)
