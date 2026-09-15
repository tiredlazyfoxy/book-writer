"""Memo service — lists, creates and body-edits **the caller's own** memos for
one book (feature 026, step 002).

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (see ``docs/architecture/backend.md``
— layer separation). All persistence goes through the session-free
``app.db.memos`` module (namespace import). Domain refusals raise the typed
:class:`MemoError`, discriminated by :class:`MemoErrorReason` so the step-003
route maps each to its HTTP status; the route stays HTTP-only.
``services/book_author_prompts.py`` is the shape precedent for the pair, the
membership guard and the access-scoped entry points.

**The ownership rule — the fourth row-ownership rule, not a capability.**
``book_access`` establishes *membership*; this module then scopes every read and
every write to ``access.user_id`` and ``access.book_id``. The user id and the
book id are taken from :class:`app.services.authz.BookAccess` and **never** from
an argument, a body field or a path segment — **no entry point takes a user id
or a book id as a separate parameter**, because that is the shape in which
another author's row would become addressable. Nobody, **including the book's
owner**, ever reads someone else's memo (``authorization.md`` → "Chats,
per-author prompts and memos — four row-ownership rules"). Consequently **no
``Capability`` member and no ``_CAPABILITY_MATRIX`` row is added** and
``authz.require`` is never called from this module (``context.md`` →
decision 3); the membership test is ``access.role in {owner, co_author}``,
written here in :func:`_require_member`.

**One refusal, no existence oracle.** :func:`_resolve_memo` is the single site
that turns a wire id into a row, and it raises the *same* ``not_found`` reason
for a non-numeric id, an unknown id, a memo whose ``user_id`` is not
``access.user_id`` and a memo whose ``book_id`` is not ``access.book_id``. The
four sources are indistinguishable from outside, which is what makes US-124
structural rather than a check a later feature could bypass.
``services/chapters.py``'s ``_resolve_chapter`` is the structural precedent.
The id is parsed **here**, not in the route: a malformed id is this feature's
``404``, never FastAPI's ``422``.

**No archived-book gate — the one named carve-out.** ``BookAccess.book_state``
is deliberately **not read** by this module: memos stay writable while the book
is ``archived``, because a memo is not book content but the author's private
note *about* a book they have set aside (``authorization.md`` → "The one named
exception: memos stay writable on an archived book", ``context.md`` →
decision 4). A reader copying ``services/chapters.py``'s archived-book refusal
into this module breaks the carve-out.

**No collaboration-mode check either.** ``BookAccess.collaboration_mode`` is
likewise unread: a memo is never book content, so there is nothing for an owner
to review and no proposal state to hold. The *(mode)* qualifier
``services/codex.py`` and ``services/continuity.py`` layer on top of the matrix
has no counterpart here.

**Ordinals — append at ``max + 1``.** :func:`create_memo` is the *single*
implementation of the append rule: the next ordinal is one past the highest
among the caller's **non-archived** memos in that book, and ``1`` when there are
none (``context.md`` → decision 2). Archiving leaves a gap and never renumbers,
so an archived row may legitimately share an ordinal with a live one — inert,
because an archived row is never in the working list. Step 005's restore and
step 008's tool reach the list through this rule rather than recomputing it.

**Timestamps are this layer's policy.** ``db/memos`` persists the row it is
handed and sets no timestamps, so the create path stamps both ``created_at`` and
``modified_at`` and the body-update path stamps ``modified_at`` only.

**Reorder is the whole set or nothing.** :func:`reorder_memos` takes the full
ordered id list of the caller's non-archived memos, validates it **before any
write** and rewrites ordinals ``1..N`` from positions.
``services/chapters.py::reorder_chapters`` is the shape precedent in full — with
**one deliberate difference**: that function calls
``authz.require(access, Capability.set_chapter_order)`` because chapter order is
owner-only (US-033.AC-2), and **this one must not**. There is no capability and
no matrix row for memos; the caller reorders **their own** list, so membership
plus the ``access.user_id`` scoping is the whole rule, and copying that line
would invent an owner-only gate over an author's private notes. There is also
deliberately **no bulk ``db/`` writer**: a bulk update would move the ``1..N``
rule out of this layer, which is where it belongs.

**Two axes, four verbs, and no new refusal (step 005).** Inactive and archived
are two *independent* axes on the row, not one state enum (``domain-book.md`` →
"two booleans, not one enum"), so each axis gets its own verb pair:
:func:`activate_memo` / :func:`deactivate_memo` write ``active`` and nothing
else, :func:`archive_memo` / :func:`restore_memo` write ``archived``. Archive
leaves **both** ``active`` and ``ordinal`` alone — preserving ``active`` is what
lets a restore return the memo in the state its author chose, and leaving
``ordinal`` alone is the deliberate gap (the ``chapters`` DELETE precedent).
Restore is where the ordinal moves, and it moves to the **end** via
:func:`_next_ordinal`. All four are **idempotent ``200`` no-ops** when the memo
is already in the requested state: they raise nothing, and
:class:`MemoErrorReason` is **unchanged at exactly three members** — there is no
``409`` anywhere in this family (``context.md`` → decision 5 and
"Planner-derived: repeat state calls are ``200`` no-ops"). Deactivation refuses
**nothing**, not even the caller's last active memo (US-127.AC-5), and there is
**no ``delete_memo``**: archive-not-delete, and ``db/memos.py`` has no delete
function to call (decision 6).

Skeleton (026 steps 002, 004 and 005): the error taxonomy and the function
signatures are frozen. Steps 002, 004 and 005 are implemented.
"""

import enum
from datetime import datetime, timezone

from app.db import memos
from app.models.memo import Memo
from app.models.schemas.memos import (
    CreateMemoRequest,
    MemoListResponse,
    MemoResponse,
    ReorderMemosRequest,
    UpdateMemoRequest,
)
from app.services import authz


class MemoErrorReason(str, enum.Enum):
    """Discriminator for :class:`MemoError` — the memo-service refusal taxonomy.

    Exactly **three** members, and the route maps each to one status:
    ``not_a_member`` → **403** (the caller can legitimately see the book — a
    reader on a public book — and is simply not allowed to hold memos on it),
    ``not_found`` → **404** and ``invalid_reorder_set`` → **400**
    (``authorization.md`` → "Failure modes").

    ``not_found`` is **one** reason covering four sources — a non-numeric id, an
    unknown id, another author's memo and another book's memo — so that no
    caller can tell them apart. Do not split it.

    ``invalid_reorder_set`` (step 004) is deliberately **not** ``not_found``:
    the caller is being told their *set* is wrong, not that a resource is
    missing, and the submitted list is refused **whole** before any write. It is
    likewise one reason for five sources — too short, too long, a duplicate, an
    archived memo's id, a foreign id — which is what keeps a caller from probing
    whether some id exists by watching the refusal change shape
    (``004.context.md`` → "Why the refusal is one reason, not four"). It maps to
    **400**, not ``422``: the body is structurally valid and the refusal is a
    business rule, so a ``422`` would misreport where validation happened.

    Nothing here is a ``409``: the memo taxonomy names no version token and no
    conflict status (``context.md`` → decision 5), and every other refusal on
    this path (no token, an invisible book, a missing book) is produced upstream
    by the ``book_access`` dependency and never reaches this service.
    """

    not_a_member = "not-a-member"
    not_found = "not-found"
    invalid_reorder_set = "invalid-reorder-set"


class MemoError(Exception):
    """Raised by the memo service for its domain refusals.

    Carries a :class:`MemoErrorReason` discriminator (``reason``) plus a
    human-readable ``message``; the route branches on ``reason`` to pick the
    status. Mirrors
    :class:`app.services.book_author_prompts.BookAuthorPromptError`.
    """

    def __init__(self, reason: MemoErrorReason, message: str = "") -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


def _require_member(access: authz.BookAccess) -> None:
    """The membership guard every entry point calls first.

    Returns ``None`` for an ``owner`` or a ``co_author`` — the two roles that
    author in a book and therefore may hold memos for it. Any other role (a
    ``reader``, or no relationship) raises :class:`MemoError` with the
    ``not_a_member`` reason. Copied from ``services/book_author_prompts.py``'s
    ``_require_member``: makes **no** capability check, adds **no**
    ``_CAPABILITY_MATRIX`` row, calls **no** ``authz.require``, and makes **no**
    collaboration-mode or book-state check.
    """
    if access.role not in (authz.AccessRole.owner, authz.AccessRole.co_author):
        raise MemoError(
            MemoErrorReason.not_a_member,
            "You are not a member of this book.",
        )


def _to_memo_response(row: Memo) -> MemoResponse:
    """Map a stored :class:`Memo` row to a :class:`MemoResponse` by hand (never
    dump the ORM). ``id`` and ``book_id`` are stringified; ``user_id`` is
    **not** emitted.

    **This is the only place the DTO is constructed**, so no two entry points
    can drift into different wire shapes.
    """
    return MemoResponse(
        id=str(row.id),
        book_id=str(row.book_id),
        body=row.body,
        ordinal=row.ordinal,
        active=row.active,
        archived=row.archived,
        created_at=row.created_at,
        modified_at=row.modified_at,
    )


async def _resolve_memo(access: authz.BookAccess, memo_id: str) -> Memo:
    """Return the memo ``memo_id`` **owned by ``access.user_id`` within
    ``access.book_id``**.

    The single refusal site: a non-numeric id, an unknown id, a memo whose
    ``user_id`` is not ``access.user_id``, and a memo whose ``book_id`` is not
    ``access.book_id`` all raise ``MemoError(not_found)`` with the same message,
    so another author's — or another book's — memo is never returned and its
    existence is never confirmed (US-124.AC-1). Every entry point that names a
    memo goes through this function.

    Callers invoke it **after** :func:`_require_member`, so a non-member is
    refused before any row is read.
    """
    try:
        parsed_id = int(memo_id)
    except (ValueError, TypeError):
        raise MemoError(MemoErrorReason.not_found, "Memo not found.")
    row = await memos.get_by_id(parsed_id)
    if (
        row is None
        or row.user_id != access.user_id
        or row.book_id != access.book_id
    ):
        # One refusal for all four sources — same reason, same message — so the
        # four stay indistinguishable and no existence oracle is opened.
        raise MemoError(MemoErrorReason.not_found, "Memo not found.")
    return row


async def list_memos(
    access: authz.BookAccess, include_archived: bool = False
) -> MemoListResponse:
    """Return **the caller's own** memos for ``access.book_id`` as a
    :class:`MemoListResponse` (UC-105, US-124.AC-1, US-124.AC-2).

    Guards membership, reads the ``(access.book_id, access.user_id)`` pair
    through ``db.memos.list_for_author`` and maps the rows through
    :func:`_to_memo_response`, ordinal ascending (US-131.AC-2). Archived memos
    are excluded unless ``include_archived`` (US-128.AC-1 / US-128.AC-2);
    **inactive memos are always listed** — the on/off switch decides what
    reaches the assistant, not what the author sees (US-127.AC-1).
    """
    _require_member(access)
    rows = await memos.list_for_author(
        access.book_id, access.user_id, include_archived
    )
    return MemoListResponse(items=[_to_memo_response(row) for row in rows])


async def _next_ordinal(access: authz.BookAccess) -> int:
    """The ordinal a memo appended to the caller's list for ``access.book_id``
    takes: one past the highest among their **non-archived** memos in that book,
    and ``1`` when there are none (``context.md`` -> decision 2).

    Computed **in Python over the rows** ``db.memos.list_for_author`` returns,
    never in a query — this layer opens no session. Archived rows are excluded
    from the maximum, so archiving leaves a gap that is never reused and an
    archived row may legitimately share an ordinal with a live one.

    Module-private and reusable: step 005's restore and step 008's tool append
    through this one rule rather than recomputing it.
    """
    live = await memos.list_for_author(
        access.book_id, access.user_id, include_archived=False
    )
    if not live:
        return 1
    return max(row.ordinal for row in live) + 1


async def create_memo(
    access: authz.BookAccess, req: CreateMemoRequest
) -> MemoResponse:
    """Create a memo for ``(access.book_id, access.user_id)`` and return it
    (UC-103, US-123).

    Guards membership, then appends: the new ordinal is one past the highest
    among the caller's **non-archived** memos in that book, and ``1`` when there
    are none. The row is created **active and not archived** (US-123.AC-3) with
    ``req.body`` stored verbatim — ``""`` is stored as ``""`` and is never a
    validation failure. Both ``created_at`` and ``modified_at`` are stamped here
    (``db/`` sets none). Succeeds on an archived book.

    **The single implementation of the append rule** — step 005's restore and
    step 008's ``create_memo`` tool arrive at the list through this rule rather
    than recomputing it.
    """
    _require_member(access)
    now = datetime.now(timezone.utc)
    row = Memo(
        book_id=access.book_id,
        user_id=access.user_id,
        body=req.body,
        ordinal=await _next_ordinal(access),
        active=True,
        archived=False,
        created_at=now,
        modified_at=now,
    )
    row = await memos.create(row)
    return _to_memo_response(row)


async def update_memo_body(
    access: authz.BookAccess, memo_id: str, req: UpdateMemoRequest
) -> MemoResponse:
    """Replace the body of the caller's memo ``memo_id`` and return it (UC-104,
    US-125.AC-1).

    Guards membership, resolves the row through :func:`_resolve_memo` (so the
    one ``404``-shaped refusal covers every source), writes ``req.body`` and
    advances ``modified_at``. It touches ``ordinal``, ``active`` and
    ``archived`` **not at all** — each of those has its own verb (steps 004 and
    005), so a focus-loss save can never move a memo or flip a flag.
    ``created_at`` is preserved. There is no version token and no ``409``.
    Succeeds on an archived book.
    """
    _require_member(access)
    row = await _resolve_memo(access, memo_id)
    row.body = req.body
    # ``ordinal`` / ``active`` / ``archived`` are untouched here: each axis has
    # its own verb (steps 004 and 005). ``created_at`` is preserved.
    row.modified_at = datetime.now(timezone.utc)
    row = await memos.update(row)
    return _to_memo_response(row)


async def reorder_memos(
    access: authz.BookAccess, req: ReorderMemosRequest
) -> MemoListResponse:
    """Rewrite the caller's memo ordinals to ``1..N`` in the submitted order and
    return the refreshed list (UC-106 / US-126.AC-2, US-131.AC-2).

    Guards membership and **nothing else**: unlike
    ``services/chapters.py::reorder_chapters`` this function makes **no**
    ``authz.require`` call and names **no** ``Capability`` — memo order is the
    author's own, not an owner-only act (``context.md`` → decision 3). It reads
    no ``book_state`` either, so a reorder succeeds on an ``archived`` book (the
    carve-out).

    "The current set" is the caller's **non-archived** memos in ``access.book_id``
    — the same read the working list uses. The whole submitted list is validated
    **before a single ordinal is written**: a different length, a duplicate id, or
    any id absent from the set (which covers an unknown id, an archived memo's id,
    another author's memo and another book's memo alike) raises
    ``MemoError(invalid_reorder_set)`` → **400**, and **nothing is written**.
    Validating up front is what makes "an invalid list changes no ordinal" true
    without a transaction spanning the db module: ``db.memos.update`` commits per
    row by design, and **no bulk writer is added**, because that would move the
    ``1..N`` rule out of this layer.

    On success it walks the submitted list in order, setting each row's
    ``ordinal`` to its 1-based position and stamping ``modified_at``, through the
    ordinary per-row ``db.memos.update``. It touches ``body``, ``active``,
    ``archived`` and ``created_at`` **not at all**, and **archived rows are never
    renumbered** — archiving left a gap and a reorder does not reclaim it, so an
    archived row may keep an ordinal a live row now shares (inert: an archived row
    is never in the list). Returns the list envelope in the new order.
    """
    _require_member(access)
    current = await memos.list_for_author(
        access.book_id, access.user_id, include_archived=False
    )
    by_id = {str(row.id): row for row in current}
    submitted = list(req.memo_ids)

    # Validate the WHOLE list before touching a single ordinal: same length as
    # the caller's current non-archived set, no duplicates, and every id in that
    # set (an unknown id, an archived memo's id, another author's memo and
    # another book's memo are all simply absent from ``by_id``). Together those
    # three make the submitted list exactly the current set. One reason and one
    # message for every source, so the refusal never changes shape and cannot be
    # used to probe whether some id exists.
    if (
        len(submitted) != len(current)
        or len(set(submitted)) != len(submitted)
        or any(memo_id not in by_id for memo_id in submitted)
    ):
        raise MemoError(
            MemoErrorReason.invalid_reorder_set,
            "The submitted order must list exactly your memos once each.",
        )

    now = datetime.now(timezone.utc)
    reordered: list[Memo] = []
    for position, memo_id in enumerate(submitted, start=1):
        row = by_id[memo_id]
        row.ordinal = position
        row.modified_at = now
        # Per-row write: no bulk writer exists, so the ``1..N`` rule stays here.
        reordered.append(await memos.update(row))

    return MemoListResponse(items=[_to_memo_response(row) for row in reordered])


async def activate_memo(access: authz.BookAccess, memo_id: str) -> MemoResponse:
    """Switch the caller's memo ``memo_id`` **on** and return it (UC-107 /
    US-127.AC-4).

    Guards membership, resolves the row through :func:`_resolve_memo` (so the one
    ``404``-shaped refusal covers a non-numeric id, an unknown id, another
    author's memo and another book's memo alike), sets ``active`` true and stamps
    ``modified_at``. It touches ``archived``, ``ordinal`` and ``body`` **not at
    all** — the archive axis is independent of the on/off switch.

    An **idempotent ``200`` no-op** on an already-active memo: the row comes back
    unchanged and nothing is raised, because these verbs are state assertions, not
    lifecycle transitions with a state machine behind them. Succeeds on an
    ``archived`` book — the carve-out.
    """
    _require_member(access)
    row = await _resolve_memo(access, memo_id)
    if row.active:
        # Idempotent 200 no-op: the memo is already in the requested state, so
        # nothing is written — not even ``modified_at`` — and the row is
        # returned unchanged. No reason is raised; there is no 409 here.
        return _to_memo_response(row)
    row.active = True
    # ``archived``, ``ordinal`` and ``body`` are untouched: the archive axis is
    # independent of the on/off switch.
    row.modified_at = datetime.now(timezone.utc)
    row = await memos.update(row)
    return _to_memo_response(row)


async def deactivate_memo(
    access: authz.BookAccess, memo_id: str
) -> MemoResponse:
    """Switch the caller's memo ``memo_id`` **off** and return it (UC-107 /
    US-127.AC-2).

    Guards membership, resolves the row through :func:`_resolve_memo`, sets
    ``active`` false and stamps ``modified_at``. ``archived``, ``ordinal`` and
    ``body`` are untouched, so a deactivated memo **stays in the working list**
    and is still returned by the ordinary read (US-127.AC-1) — the flag decides
    what reaches the assistant, not what the author sees.

    **It refuses nothing.** Deactivating the caller's *last* active memo is
    allowed and leaves them with an empty active set, which is a legitimate end
    state (US-127.AC-5); there is no book-level memos-off switch to consult. An
    idempotent ``200`` no-op on an already-inactive memo. Succeeds on an
    ``archived`` book.
    """
    _require_member(access)
    row = await _resolve_memo(access, memo_id)
    if not row.active:
        # Idempotent 200 no-op — nothing written, row returned unchanged.
        return _to_memo_response(row)
    # Nothing is refused here: the caller's *last* active memo may be switched
    # off, leaving an empty active set (US-127.AC-5), and there is no
    # book-level memos-off switch to consult.
    row.active = False
    # ``archived``, ``ordinal`` and ``body`` are untouched, so the memo stays in
    # the working list and is still returned by the ordinary read.
    row.modified_at = datetime.now(timezone.utc)
    row = await memos.update(row)
    return _to_memo_response(row)


async def archive_memo(access: authz.BookAccess, memo_id: str) -> MemoResponse:
    """Archive the caller's memo ``memo_id`` and return it (UC-107 /
    US-128.AC-1).

    Guards membership, resolves the row through :func:`_resolve_memo`, sets
    ``archived`` true and stamps ``modified_at``. The memo leaves the working
    list — absent from the default read, present in the include-archived one —
    and is **never deleted** (US-128.AC-3).

    **Two things it must not do**, both load-bearing:

    - it does **not** touch ``active``. Two booleans exist precisely so a restored
      memo comes back in the state its author chose; clearing ``active`` here
      would collapse the model into the three-value enum ``domain-book.md``
      rejects.
    - it does **not** touch ``ordinal``. The gap it leaves is the design: nothing
      is renumbered, the surviving memos keep their ordinals, and the vacated
      number is never reused (an archived row may therefore share an ordinal with
      a live one — inert, because an archived row is never in the list).

    ``body`` is untouched too. An idempotent ``200`` no-op on an already-archived
    memo — **not** a ``409``, deliberately unlike
    ``POST /books/{book_id}/archive``, whose subject is a book lifecycle.
    Succeeds on an ``archived`` book.
    """
    _require_member(access)
    row = await _resolve_memo(access, memo_id)
    if row.archived:
        # Idempotent 200 no-op — deliberately NOT the 409 that
        # ``POST /books/{book_id}/archive`` answers.
        return _to_memo_response(row)
    row.archived = True
    # ``active`` is NOT cleared — that flag is what lets a restore return the
    # memo in the state its author chose (two booleans, not one enum) — and
    # ``ordinal`` is NOT rewritten: the gap this leaves is the design, nothing
    # is renumbered and the vacated number is never reused. ``body`` is
    # untouched too.
    row.modified_at = datetime.now(timezone.utc)
    row = await memos.update(row)
    return _to_memo_response(row)


async def restore_memo(access: authz.BookAccess, memo_id: str) -> MemoResponse:
    """Restore the caller's archived memo ``memo_id`` to the working list,
    **appended last**, and return it (UC-107 / US-128.AC-2).

    Guards membership, resolves the row through :func:`_resolve_memo`, sets
    ``archived`` false, rewrites ``ordinal`` to one past the highest among the
    caller's non-archived memos and stamps ``modified_at``. The memo does **not**
    return to the slot it held before: the ordinal is recomputed through
    :func:`_next_ordinal` — step 002's single append rule, reused rather than
    reimplemented, so that manual create, assistant create and restore cannot
    drift (``domain-book.md``: one rule covers every way a memo arrives in the
    list).

    It does **not** touch ``active``: a memo archived while switched off comes
    back switched off, and one archived while on comes back on — the whole reason
    the row carries two booleans. ``body`` is untouched. The verb is **restore**,
    not ``unarchive`` (the memos route table). An idempotent ``200`` no-op on a
    memo that is not archived. Succeeds on an ``archived`` book.
    """
    _require_member(access)
    row = await _resolve_memo(access, memo_id)
    if not row.archived:
        # Idempotent 200 no-op, ``ordinal`` included: a verb applied to a memo
        # already in the requested state returns the row unchanged, so restore
        # never silently relocates a memo that is already in the working list.
        return _to_memo_response(row)
    # Appended last through step 002's single append rule — the same one manual
    # create and the assistant tool use — computed while the row is still
    # archived, so it cannot count itself. The memo never returns to its old
    # slot.
    next_ordinal = await _next_ordinal(access)
    row.archived = False
    row.ordinal = next_ordinal
    # ``active`` is preserved: a memo archived while switched off comes back
    # switched off, and one archived while on comes back on. ``body`` too.
    row.modified_at = datetime.now(timezone.utc)
    row = await memos.update(row)
    return _to_memo_response(row)
