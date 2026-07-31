"""Flag service — raising, listing and resolving a chapter's warnings
(feature 016).

Realizes FEAT-016: UC-067, UC-068; US-075.AC-1, US-076.AC-2, US-077.AC-1.

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). All persistence goes through the session-free ``app.db``
modules; because this module's own name is ``flags``, the data-access namespace
is imported **aliased** (``from app.db import flags as flags_db``) so the two
never shadow each other.

The **sibling** of ``services/continuity.py``, same grain, its own refusal
taxonomy: a :class:`FlagError` discriminated by :class:`FlagErrorReason`, which
``routes/flags.py`` maps to a status. Neither service imports the other.

Invariants, inherited verbatim from ``services/chapters.py``:

1. the gate is the **first line** of every entry point, before any db read;
2. the **book id is never an argument** — it comes from :class:`BookAccess`;
3. a chapter is resolved **within ``access.book_id``**, and a mismatch is
   ``chapter_not_found``, never a permission failure. A flag is likewise
   resolved through its chapter: the ``Flag`` row carries no ``book_id``.

Decision D9's split applies here too: **listing is gated by plain membership**
(``not_a_member``), while raising and resolving go through
``authz.require(Capability.raise_flag)`` / ``…(Capability.resolve_flag)`` —
the latter **owner-only**, because UC-068 names the owner alone.

Skeleton (016): the signatures and the error taxonomy are frozen; the three entry
point bodies are UNIMPLEMENTED (raise ``NotImplementedError``).
"""

import enum
from datetime import datetime, timezone

from app.db import chapters as chapters_db
from app.db import flags as flags_db
from app.models.book import BookState
from app.models.chapter import Chapter
from app.models.flag import Flag, FlagOrigin, FlagStatus
from app.models.schemas.flags import FlagListResponse, FlagResponse, RaiseFlagRequest
from app.services import authz
from app.services.authz import AccessRole, BookAccess, Capability

# The two roles that may see a chapter's warnings at all (decision D9) — plain
# membership, no capability, exactly as ``services/continuity.py`` reads it.
_MEMBER_ROLES: frozenset[AccessRole] = frozenset(
    {AccessRole.owner, AccessRole.co_author}
)


class FlagErrorReason(str, enum.Enum):
    """Discriminator for :class:`FlagError` — the flag-service refusal taxonomy.

    The route status map (``routes/flags.py``): ``not_a_member`` → **403**,
    ``book_archived`` → **403**, ``chapter_not_found`` → **404**,
    ``flag_not_found`` → **404**, ``flag_already_resolved`` → **409**.

    ``flag_already_resolved`` is a **409, not a 403**: the caller *has* the
    capability, and what refuses them is the flag's own lifecycle state — the
    same reasoning ``chapters.ChapterErrorReason.chapter_not_closed`` records.

    There is deliberately **no ``proposal_mode_refused``**: raising and resolving
    a warning are not authored content and are never held for review.
    """

    not_a_member = "not-a-member"
    book_archived = "book-archived"
    chapter_not_found = "chapter-not-found"
    flag_not_found = "flag-not-found"
    flag_already_resolved = "flag-already-resolved"


class FlagError(Exception):
    """Raised by the flag service for every domain refusal.

    Carries a :class:`FlagErrorReason` discriminator (``reason``) plus a
    human-readable ``message``; the route branches on ``reason`` to pick the HTTP
    status and passes ``message`` through as the ``detail``. Mirrors
    :class:`app.services.chapters.ChapterError`.
    """

    def __init__(self, reason: FlagErrorReason, message: str = "") -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


def _require_member(access: BookAccess) -> None:
    """Refuse a caller who is not a member of the book (**403**, decision D9).

    The first line of the *read* entry point, before any db read. Raising and
    resolving go through ``authz.require`` instead — they are the two capabilities
    this service names.
    """
    if access.role not in _MEMBER_ROLES:
        raise FlagError(
            FlagErrorReason.not_a_member,
            "This chapter's warnings are for the book's authors. "
            "Ask the owner to add you as a co-author.",
        )
    return None


def _require_not_archived(access: BookAccess) -> None:
    """Refuse a flag **write** on an archived book (**403**).

    ``services/chapters.py:_require_not_archived``'s rule in this service's own
    taxonomy. **No read path calls it**: archive is preserving and reversible.
    """
    if access.book_state == BookState.archived:
        raise FlagError(
            FlagErrorReason.book_archived,
            "This book is archived, so its warnings cannot be changed. "
            "Restore the book to work in it again.",
        )
    return None


async def _resolve_chapter(access: BookAccess, chapter_id: str) -> Chapter:
    """Return the chapter ``chapter_id`` **within** ``access.book_id``.

    A non-numeric id, an unknown id and a chapter belonging to another book are
    all ``FlagError(chapter_not_found)`` — **404**, never a permission failure.
    """
    try:
        parsed_id = int(chapter_id)
    except (ValueError, TypeError):
        raise FlagError(FlagErrorReason.chapter_not_found, "Chapter not found.")
    chapter = await chapters_db.get_by_id(parsed_id)
    if chapter is None or chapter.book_id != access.book_id:
        raise FlagError(FlagErrorReason.chapter_not_found, "Chapter not found.")
    return chapter


async def _resolve_flag(chapter: Chapter, flag_id: str) -> Flag:
    """Return the flag ``flag_id`` **within** ``chapter``.

    The ``Flag`` row carries no ``book_id``, so the book is enforced through the
    chapter: the caller resolves the chapter first (which enforces the book) and
    this then enforces the chapter. A non-numeric id, an unknown id and a flag on
    another chapter are all ``FlagError(flag_not_found)`` — **404**.
    """
    try:
        parsed_id = int(flag_id)
    except (ValueError, TypeError):
        raise FlagError(FlagErrorReason.flag_not_found, "Warning not found.")
    flag = await flags_db.get_by_id(parsed_id)
    if flag is None or flag.chapter_id != chapter.id:
        raise FlagError(FlagErrorReason.flag_not_found, "Warning not found.")
    return flag


def _to_response(flag: Flag) -> FlagResponse:
    """Map a ``Flag`` row to a :class:`FlagResponse` by hand (never dump the ORM).

    The single mapper for every entry point here, and the single place a
    snowflake becomes a string on this resource.
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


def _newest_first_key(flag: Flag) -> tuple[int, float, int]:
    """Sort key for "newest first", total over a nullable ``created_at``.

    A flag with **no** ``created_at`` sorts last (its leading element is ``0``,
    every stamped row's is ``1``), and the row's own snowflake id — which is
    time-ordered — breaks a tie between two rows stamped in the same instant, so
    the ordering is deterministic rather than dependent on the db's row order.
    The caller reverses this key.
    """
    created = flag.created_at
    return (0 if created is None else 1, 0.0 if created is None else created.timestamp(), flag.id)


async def list_flags(access: BookAccess, chapter_id: str) -> FlagListResponse:
    """Return every flag of one chapter — **open and resolved**, newest first
    (US-075 / US-077's read side).

    Refuses ``FlagError(not_a_member)`` when ``access.role`` is not in
    ``{owner, co_author}`` — plain membership, no capability (decision D9) — then
    resolves the chapter within ``access.book_id`` (an unknown, non-numeric or
    foreign id is ``chapter_not_found`` → **404**) and maps its flags.

    Ordering is **newest first** by ``created_at``, so the most recent warning is
    the one an author sees without scrolling. Resolved flags are **not** filtered
    out here: this is the chapter's whole warning history, and the continuity
    roll-up is the surface that carries open ones only.

    **No archived gate**: a read is never refused for the book's state.
    """
    _require_member(access)
    chapter = await _resolve_chapter(access, chapter_id)
    rows = await flags_db.list_by_chapter(chapter.id)
    return FlagListResponse(
        items=[
            _to_response(flag)
            for flag in sorted(rows, key=_newest_first_key, reverse=True)
        ]
    )


async def raise_flag(
    access: BookAccess, chapter_id: str, body: RaiseFlagRequest
) -> FlagResponse:
    """Raise a member's warning on a chapter (``POST …/flags``; UC-067 /
    US-075.AC-1).

    In order:

    1. ``authz.require(access, Capability.raise_flag)`` — owner or co-author; a
       reader and a stranger are refused here (**403**);
    2. ``FlagError(book_archived)`` when ``access.book_state`` is ``archived``
       (**403**) — the ``chapters._require_not_archived`` rule in this service's
       own taxonomy;
    3. resolve the chapter within ``access.book_id`` (``chapter_not_found`` →
       **404**);
    4. create the ``Flag`` with ``origin = FlagOrigin.person`` — **never
       client-settable**, which is why :class:`RaiseFlagRequest` has no origin
       field; ``status = FlagStatus.open``; ``created_by = access.user_id`` (this
       is where attribution lives); ``created_at`` stamped **here** (timestamps
       are the service's, never ``db/``'s); ``resolved_by`` / ``resolved_at``
       left ``None``;
    5. return the stored flag's :class:`FlagResponse`.
    """
    authz.require(access, Capability.raise_flag)
    _require_not_archived(access)
    chapter = await _resolve_chapter(access, chapter_id)
    flag = await flags_db.create(
        Flag(
            chapter_id=chapter.id,
            # NEVER client-settable — which is why ``RaiseFlagRequest`` has no
            # origin field: a member cannot forge a check finding.
            origin=FlagOrigin.person,
            comment=body.comment,
            status=FlagStatus.open,
            created_by=access.user_id,
            created_at=datetime.now(timezone.utc),
        )
    )
    return _to_response(flag)


async def resolve_flag(
    access: BookAccess, chapter_id: str, flag_id: str
) -> FlagResponse:
    """Resolve an open flag (``POST …/flags/{flag_id}/resolve``; UC-068 /
    US-076.AC-2, US-077.AC-1).

    In order:

    1. ``authz.require(access, Capability.resolve_flag)`` — **owner only**; a
       co-author is refused **403** (US-076.AC-2);
    2. ``FlagError(book_archived)`` when the book is ``archived`` (**403**);
    3. resolve the chapter within ``access.book_id`` (``chapter_not_found`` →
       **404**), then the flag **within that chapter** — an unknown, non-numeric
       or foreign flag id is ``flag_not_found`` → **404**, never a permission
       failure;
    4. ``FlagError(flag_already_resolved)`` when ``flag.status`` is already
       ``resolved`` (**409**) — the caller has the capability; the flag's own
       lifecycle refuses them, and re-resolving would re-stamp somebody else's
       attribution;
    5. write ``status = FlagStatus.resolved``, ``resolved_by = access.user_id``
       and ``resolved_at`` stamped **here**, persist, and return the stored
       :class:`FlagResponse`.

    There is **no un-resolve verb**: nothing in this feature moves a flag back to
    ``open``.
    """
    authz.require(access, Capability.resolve_flag)
    _require_not_archived(access)
    chapter = await _resolve_chapter(access, chapter_id)
    flag = await _resolve_flag(chapter, flag_id)
    if flag.status == FlagStatus.resolved:
        raise FlagError(
            FlagErrorReason.flag_already_resolved,
            "This warning has already been resolved.",
        )
    flag.status = FlagStatus.resolved
    flag.resolved_by = access.user_id
    flag.resolved_at = datetime.now(timezone.utc)
    stored = await flags_db.update(flag)
    return _to_response(stored)
