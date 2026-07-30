"""Tests for the three chapter state transitions (feature 015, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002), in
`app.services.chapters`:
    ChapterErrorReason { ..., chapter_not_closed, another_chapter_open }
        (plus 014's `not_found` / `not_planned`, and step 001's `chapter_not_open`
         and `book_archived`, all REUSED here)
    async def open_chapter(access, chapter_id: str) -> ChapterResponse
    async def close_chapter(access, chapter_id: str) -> ChapterResponse
    async def reopen_chapter(access, chapter_id: str) -> ChapterResponse
plus the frozen `authz.BookAccess` / `AccessRole` / `BookAuthorizationError` and
014's `ChapterError` / `ChapterResponse`.

Expected values come from the step spec (002.chapter-state-transitions.md ->
Interface intent + Definition of done, 002.context.md, and the feature context.md
-> D8 / D10 / "The close seam" / the status taxonomy), never from implementation
internals:
    - the owner opens a `planned` chapter and it becomes `open` (DoD-1, US-036.AC-1,
      UC-035); a co-author is refused by the authorization error (DoD-2, US-036.AC-2);
    - the one-open-chapter guard reads TWO states: opening while another chapter is
      `open` (DoD-3, US-037.AC-2) or `closing` (DoD-4, US-038.AC-4) is refused with
      the another-chapter-open reason, and both chapters keep their states;
    - across a sequence of open / close / reopen calls at most one chapter is ever
      `open` (DoD-5, US-037.AC-1);
    - opening a chapter that is not `planned` is the not-planned reason (DoD-6);
    - a close writes `closed` DIRECTLY -- never `closing`, no summary, no continuity,
      no approval record (DoD-7, US-038.AC-1, "The close seam"); a co-author is
      refused (DoD-8, US-038.AC-2); a close of a chapter that is not `open` is the
      not-open reason (DoD-9); after a close the slot is genuinely released (DoD-10);
    - the owner reopens a `closed` chapter (DoD-11, US-039.AC-1, UC-037); a reopen
      while a different chapter is `open` (DoD-12, US-039.AC-2, CF1) or `closing`
      (DoD-13, US-038.AC-4) is refused with the another-chapter-open reason; a reopen
      of a chapter that is not `closed` is the not-closed reason (DoD-14);
    - every transition is refused with the archived reason on an `archived` book
      (DoD-15, D10) and by the authorization error for a reader / non-member
      (DoD-16);
    - all three touch STATE and `modified_at` ONLY -- `text`, `version`, `ordinal`,
      `title`, `sketch` unchanged and no `ChapterChange` / `ChapterTextRevision` row
      written (DoD-17);
    - another book's chapter is NOT FOUND on all three (DoD-18, 014's D4).

US-038.AC-3 (the close gate) is `016`'s and is asserted NOWHERE here (D8). The only
sanctioned use of `closing` is the seeded row DoD-4 / DoD-9 / DoD-13 / DoD-14 need.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. User / Book / Chapter rows are seeded
through the sibling db/ modules and `BookAccess` is constructed directly (a frozen
dataclass), so there is no route, no client, no JWT and no network anywhere in this
module. A chapter is put into a starting state by writing that state straight through
`db/chapters.py` -- the transitions are the code under test and are never used to
reach a precondition, and `closing` is reachable no other way (D8).
"""

import pytest

from app.db import (
    books,
    chapter_changes,
    chapter_text_revisions,
    chapters,
    flags,
    users,
)
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chapter import Chapter, ChapterState
from app.models.schemas.chapters import ChapterResponse
from app.models.user import User, UserRole
from app.services import chapters as chapters_service
from app.services.authz import AccessRole, BookAccess, BookAuthorizationError
from app.services.chapters import ChapterError, ChapterErrorReason

# The two states that HOLD the one-open slot (002.context.md, D8's carve-out, CF1).
SLOT_HOLDING_STATES = (ChapterState.open, ChapterState.closing)


# ---------------------------------------------------------------------------
# Seeding helpers (db-layer rows + a directly-built access context).
# Per-file, not shared -- the convention in context.md -> "Testing facts".
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(
    owner_id: int,
    *,
    title: str = "A Book",
    state: BookState = BookState.active,
) -> Book:
    return await books.create(
        Book(
            title=title,
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.private,
            state=state,
            system_prompt="",
            active_notes="",
        )
    )


def _access(
    book_id: int,
    user_id: int,
    *,
    role: AccessRole = AccessRole.owner,
    book_state: BookState = BookState.active,
    visibility: Visibility = Visibility.private,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
) -> BookAccess:
    """A BookAccess built directly -- the frozen dataclass, no resolve, no HTTP."""
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=role,
        book_state=book_state,
        visibility=visibility,
        collaboration_mode=collaboration_mode,
    )


async def _seed_chapter(
    book_id: int,
    *,
    ordinal: int = 1,
    title: str = "Seeded",
    sketch: str = "seeded sketch",
    state: ChapterState = ChapterState.planned,
    text: str = "",
    version: int = 1,
) -> Chapter:
    """A Chapter inserted straight through db/chapters.py, bypassing the service.

    The STATE is written directly. The transitions are the code under test, so they
    are never used to reach a starting state, and `closing` has no other producer in
    this feature at all (D8).
    """
    return await chapters.create(
        Chapter(
            book_id=book_id,
            ordinal=ordinal,
            title=title,
            state=state,
            sketch=sketch,
            text=text,
            version=version,
        )
    )


async def _stored(chapter_id: int) -> Chapter:
    row = await chapters.get_by_id(chapter_id)
    assert row is not None
    return row


async def _states(book_id: int) -> dict[int, ChapterState]:
    """{chapter id -> stored state}, read straight from the db layer."""
    return {c.id: c.state for c in await chapters.list_by_book(book_id)}


async def _open_ids(book_id: int) -> list[int]:
    return [c.id for c in await chapters.list_by_book(book_id) if c.state == ChapterState.open]


async def _slot_holder_ids(book_id: int) -> list[int]:
    return [
        c.id
        for c in await chapters.list_by_book(book_id)
        if c.state in SLOT_HOLDING_STATES
    ]


# ---------------------------------------------------------------------------
# DoD-1 — the owner opens a planned chapter in a book with nothing open
# ---------------------------------------------------------------------------


# DoD-1 (US-036.AC-1, UC-035): the owner opens a `planned` chapter in a book where
# nothing is open, and its state becomes `open`.
async def test_owner_opens_a_planned_chapter__DoD1_US036_AC1(db: DbConfig):
    owner = await _seed_user("open-owner")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(book.id, ordinal=1, title="First Beat")
    # A second chapter that holds no slot -- `planned` never blocks an open.
    other = await _seed_chapter(book.id, ordinal=2, title="Later Beat")

    result = await chapters_service.open_chapter(_access(book.id, owner.id), str(target.id))

    assert isinstance(result, ChapterResponse)
    assert result.id == str(target.id)
    assert result.state == ChapterState.open

    stored = await _stored(target.id)
    assert stored.state == ChapterState.open
    # The bystander is untouched.
    assert (await _stored(other.id)).state == ChapterState.planned


# ---------------------------------------------------------------------------
# DoD-2 — a co-author may not open a chapter
# ---------------------------------------------------------------------------


# DoD-2 (US-036.AC-2): a co-author attempting to open a chapter is refused by the
# authorization error and the chapter's state is unchanged.
async def test_co_author_cannot_open__DoD2_US036_AC2(db: DbConfig):
    owner = await _seed_user("open-owner-only")
    helper = await _seed_user("open-co-author")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(book.id, ordinal=1, title="Not Yours")

    with pytest.raises(BookAuthorizationError):
        await chapters_service.open_chapter(
            _access(book.id, helper.id, role=AccessRole.co_author), str(target.id)
        )

    assert (await _stored(target.id)).state == ChapterState.planned


# ---------------------------------------------------------------------------
# DoD-3 / DoD-4 — the one-open guard reads BOTH `open` and `closing`
# ---------------------------------------------------------------------------


# DoD-3 (US-037.AC-2, UC-035 exception flow): opening a chapter while another chapter
# of the book is `open` is refused with the another-chapter-open reason, and BOTH
# chapters keep their states.
async def test_open_refused_while_another_is_open__DoD3_US037_AC2(db: DbConfig):
    owner = await _seed_user("slot-owner-open")
    book = await _seed_book(owner.id)
    holder = await _seed_chapter(
        book.id, ordinal=1, title="Holder", state=ChapterState.open
    )
    target = await _seed_chapter(book.id, ordinal=2, title="Wants In")

    with pytest.raises(ChapterError) as exc:
        await chapters_service.open_chapter(_access(book.id, owner.id), str(target.id))
    assert exc.value.reason == ChapterErrorReason.another_chapter_open

    assert await _states(book.id) == {
        holder.id: ChapterState.open,
        target.id: ChapterState.planned,
    }


# DoD-4 (US-038.AC-4): a chapter parked in `closing` still HOLDS the slot -- opening
# another chapter is refused the same way. The `closing` row is seeded directly (D8).
async def test_open_refused_while_another_is_closing__DoD4_US038_AC4(db: DbConfig):
    owner = await _seed_user("slot-owner-closing")
    book = await _seed_book(owner.id)
    holder = await _seed_chapter(
        book.id, ordinal=1, title="Half Closed", state=ChapterState.closing
    )
    target = await _seed_chapter(book.id, ordinal=2, title="Wants In")

    with pytest.raises(ChapterError) as exc:
        await chapters_service.open_chapter(_access(book.id, owner.id), str(target.id))
    assert exc.value.reason == ChapterErrorReason.another_chapter_open

    assert await _states(book.id) == {
        holder.id: ChapterState.closing,
        target.id: ChapterState.planned,
    }


# DoD-3 (US-037.AC-2): the guard is scoped to the book -- another BOOK's open chapter
# does not hold this book's slot.
async def test_another_books_open_chapter_does_not_hold_the_slot__DoD3_US037_AC2(
    db: DbConfig,
):
    owner = await _seed_user("slot-owner-scoped")
    mine = await _seed_book(owner.id, title="Mine")
    theirs = await _seed_book(owner.id, title="Theirs")
    elsewhere = await _seed_chapter(
        theirs.id, ordinal=1, title="Open Elsewhere", state=ChapterState.open
    )
    target = await _seed_chapter(mine.id, ordinal=1, title="Mine To Open")

    result = await chapters_service.open_chapter(
        _access(mine.id, owner.id), str(target.id)
    )

    assert result.state == ChapterState.open
    assert (await _stored(target.id)).state == ChapterState.open
    assert (await _stored(elsewhere.id)).state == ChapterState.open


# ---------------------------------------------------------------------------
# DoD-5 — at most one chapter is ever `open`, across a sequence of transitions
# ---------------------------------------------------------------------------


# DoD-5 (US-037.AC-1): across a sequence of open / close / reopen calls, at most one
# of the book's chapters is ever in the `open` state. Each step asserts the
# transition's OWN success first, so the invariant is never satisfied vacuously.
async def test_at_most_one_open_across_a_sequence__DoD5_US037_AC1(db: DbConfig):
    owner = await _seed_user("sequence-owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)
    a = await _seed_chapter(book.id, ordinal=1, title="A")
    b = await _seed_chapter(book.id, ordinal=2, title="B")

    # 1. open A
    opened_a = await chapters_service.open_chapter(access, str(a.id))
    assert opened_a.state == ChapterState.open
    assert await _open_ids(book.id) == [a.id]

    # 2. close A
    closed_a = await chapters_service.close_chapter(access, str(a.id))
    assert closed_a.state == ChapterState.closed
    assert await _open_ids(book.id) == []

    # 3. open B
    opened_b = await chapters_service.open_chapter(access, str(b.id))
    assert opened_b.state == ChapterState.open
    assert await _open_ids(book.id) == [b.id]

    # 4. close B
    closed_b = await chapters_service.close_chapter(access, str(b.id))
    assert closed_b.state == ChapterState.closed
    assert await _open_ids(book.id) == []

    # 5. reopen A
    reopened_a = await chapters_service.reopen_chapter(access, str(a.id))
    assert reopened_a.state == ChapterState.open
    assert await _open_ids(book.id) == [a.id]

    assert await _states(book.id) == {a.id: ChapterState.open, b.id: ChapterState.closed}


# ---------------------------------------------------------------------------
# DoD-6 — opening a chapter that is not `planned`
# ---------------------------------------------------------------------------


# DoD-6: opening a chapter that is `open`, `closing` or `closed` is refused with the
# not-planned reason and nothing changes.
@pytest.mark.parametrize(
    "state", [ChapterState.open, ChapterState.closing, ChapterState.closed]
)
async def test_open_on_a_non_planned_chapter_is_refused__DoD6(
    db: DbConfig, state: ChapterState
):
    owner = await _seed_user(f"open-nonplanned-owner-{state.value}")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(
        book.id, ordinal=1, title="Already Moved On", state=state, text="body"
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.open_chapter(_access(book.id, owner.id), str(target.id))
    assert exc.value.reason == ChapterErrorReason.not_planned

    stored = await _stored(target.id)
    assert stored.state == state
    assert stored.text == "body"


# ---------------------------------------------------------------------------
# DoD-7 — a close writes `closed` DIRECTLY, with no continuity mechanics
# ---------------------------------------------------------------------------


# DoD-7 (US-038.AC-1, context.md -> "The close seam"): the owner closes an `open`
# chapter and its state becomes `closed` directly -- it does NOT pass through
# `closing`, and no summary, continuity or approval record is written.
async def test_close_goes_straight_to_closed__DoD7_US038_AC1(db: DbConfig):
    owner = await _seed_user("close-owner")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(
        book.id, ordinal=1, title="Done", state=ChapterState.open, text="the body"
    )
    before = await _stored(target.id)

    result = await chapters_service.close_chapter(_access(book.id, owner.id), str(target.id))

    assert result.state == ChapterState.closed
    assert result.state != ChapterState.closing

    stored = await _stored(target.id)
    assert stored.state == ChapterState.closed

    # Nothing continuity-shaped was drafted, and nothing was approved.
    assert stored.summary == before.summary
    assert stored.summary_status == before.summary_status
    assert list(await flags.list_by_chapter(target.id)) == []
    assert list(await chapter_changes.list_by_chapter(target.id)) == []
    assert list(await chapter_text_revisions.list_by_chapter(target.id)) == []


# ---------------------------------------------------------------------------
# DoD-8 — a co-author may not close the open chapter
# ---------------------------------------------------------------------------


# DoD-8 (US-038.AC-2): a co-author attempting to close the open chapter is refused by
# the authorization error and the chapter stays `open`.
async def test_co_author_cannot_close__DoD8_US038_AC2(db: DbConfig):
    owner = await _seed_user("close-owner-only")
    helper = await _seed_user("close-co-author")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(
        book.id, ordinal=1, title="Still Open", state=ChapterState.open
    )

    with pytest.raises(BookAuthorizationError):
        await chapters_service.close_chapter(
            _access(book.id, helper.id, role=AccessRole.co_author), str(target.id)
        )

    assert (await _stored(target.id)).state == ChapterState.open


# ---------------------------------------------------------------------------
# DoD-9 — closing a chapter that is not `open`
# ---------------------------------------------------------------------------


# DoD-9: closing a chapter that is `planned`, `closing` or `closed` is refused with
# the not-open reason and nothing changes. The `closing` case is seeded directly (D8).
@pytest.mark.parametrize(
    "state", [ChapterState.planned, ChapterState.closing, ChapterState.closed]
)
async def test_close_on_a_non_open_chapter_is_refused__DoD9(
    db: DbConfig, state: ChapterState
):
    owner = await _seed_user(f"close-nonopen-owner-{state.value}")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(
        book.id, ordinal=1, title="Not Open", state=state, text="body"
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.close_chapter(_access(book.id, owner.id), str(target.id))
    assert exc.value.reason == ChapterErrorReason.chapter_not_open

    stored = await _stored(target.id)
    assert stored.state == state
    assert stored.text == "body"


# ---------------------------------------------------------------------------
# DoD-10 — a close genuinely releases the slot
# ---------------------------------------------------------------------------


# DoD-10: after a close, the book has no chapter in `open` or `closing`, and a
# DIFFERENT `planned` chapter can then be opened.
async def test_close_releases_the_slot__DoD10(db: DbConfig):
    owner = await _seed_user("slot-release-owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)
    first = await _seed_chapter(
        book.id, ordinal=1, title="First", state=ChapterState.open
    )
    second = await _seed_chapter(book.id, ordinal=2, title="Second")

    closed = await chapters_service.close_chapter(access, str(first.id))
    assert closed.state == ChapterState.closed

    assert await _slot_holder_ids(book.id) == []

    opened = await chapters_service.open_chapter(access, str(second.id))
    assert opened.state == ChapterState.open

    assert await _states(book.id) == {
        first.id: ChapterState.closed,
        second.id: ChapterState.open,
    }


# ---------------------------------------------------------------------------
# DoD-11 — the owner reopens a closed chapter
# ---------------------------------------------------------------------------


# DoD-11 (US-039.AC-1, UC-037): the owner reopens a `closed` chapter when nothing else
# is open and its state becomes `open`.
async def test_owner_reopens_a_closed_chapter__DoD11_US039_AC1(db: DbConfig):
    owner = await _seed_user("reopen-owner")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(
        book.id,
        ordinal=1,
        title="Revisited",
        state=ChapterState.closed,
        text="already written",
    )
    bystander = await _seed_chapter(book.id, ordinal=2, title="Untouched")

    result = await chapters_service.reopen_chapter(
        _access(book.id, owner.id), str(target.id)
    )

    assert isinstance(result, ChapterResponse)
    assert result.id == str(target.id)
    assert result.state == ChapterState.open

    stored = await _stored(target.id)
    assert stored.state == ChapterState.open
    assert stored.text == "already written"
    assert (await _stored(bystander.id)).state == ChapterState.planned


# ---------------------------------------------------------------------------
# DoD-12 / DoD-13 — a reopen runs the same two-state slot guard
# ---------------------------------------------------------------------------


# DoD-12 (US-039.AC-2, CF1): reopening a `closed` chapter while a DIFFERENT chapter is
# `open` is refused with the another-chapter-open reason, and the open chapter is
# unaffected.
async def test_reopen_refused_while_another_is_open__DoD12_US039_AC2(db: DbConfig):
    owner = await _seed_user("reopen-slot-owner-open")
    book = await _seed_book(owner.id)
    holder = await _seed_chapter(
        book.id, ordinal=1, title="Holder", state=ChapterState.open, text="in progress"
    )
    target = await _seed_chapter(
        book.id, ordinal=2, title="Wants Back In", state=ChapterState.closed
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.reopen_chapter(_access(book.id, owner.id), str(target.id))
    assert exc.value.reason == ChapterErrorReason.another_chapter_open

    assert await _states(book.id) == {
        holder.id: ChapterState.open,
        target.id: ChapterState.closed,
    }
    assert (await _stored(holder.id)).text == "in progress"


# DoD-13 (US-038.AC-4): reopening while a DIFFERENT chapter is `closing` is refused
# the same way -- `closing` holds the slot (seeded directly, D8).
async def test_reopen_refused_while_another_is_closing__DoD13_US038_AC4(db: DbConfig):
    owner = await _seed_user("reopen-slot-owner-closing")
    book = await _seed_book(owner.id)
    holder = await _seed_chapter(
        book.id, ordinal=1, title="Half Closed", state=ChapterState.closing
    )
    target = await _seed_chapter(
        book.id, ordinal=2, title="Wants Back In", state=ChapterState.closed
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.reopen_chapter(_access(book.id, owner.id), str(target.id))
    assert exc.value.reason == ChapterErrorReason.another_chapter_open

    assert await _states(book.id) == {
        holder.id: ChapterState.closing,
        target.id: ChapterState.closed,
    }


# ---------------------------------------------------------------------------
# DoD-14 — reopening a chapter that is not `closed`
# ---------------------------------------------------------------------------


# DoD-14: reopening a chapter that is `planned`, `open` or `closing` is refused with
# the not-closed reason and nothing changes.
@pytest.mark.parametrize(
    "state", [ChapterState.planned, ChapterState.open, ChapterState.closing]
)
async def test_reopen_on_a_non_closed_chapter_is_refused__DoD14(
    db: DbConfig, state: ChapterState
):
    owner = await _seed_user(f"reopen-nonclosed-owner-{state.value}")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(
        book.id, ordinal=1, title="Not Closed", state=state, text="body"
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.reopen_chapter(_access(book.id, owner.id), str(target.id))
    assert exc.value.reason == ChapterErrorReason.chapter_not_closed

    stored = await _stored(target.id)
    assert stored.state == state
    assert stored.text == "body"


# ---------------------------------------------------------------------------
# DoD-15 — an archived book refuses all three transitions
# ---------------------------------------------------------------------------


# DoD-15 (D10): all three transitions are refused with the archived reason on a book
# whose state is `archived`, and no state changes.
async def test_all_three_refused_on_an_archived_book__DoD15(db: DbConfig):
    owner = await _seed_user("archived-owner")
    book = await _seed_book(owner.id, state=BookState.archived)
    access = _access(book.id, owner.id, book_state=BookState.archived)
    to_open = await _seed_chapter(book.id, ordinal=1, title="Planned One")
    to_close = await _seed_chapter(
        book.id, ordinal=2, title="Open One", state=ChapterState.open
    )
    to_reopen = await _seed_chapter(
        book.id, ordinal=3, title="Closed One", state=ChapterState.closed
    )
    before = await _states(book.id)

    with pytest.raises(ChapterError) as exc:
        await chapters_service.open_chapter(access, str(to_open.id))
    assert exc.value.reason == ChapterErrorReason.book_archived

    with pytest.raises(ChapterError) as exc:
        await chapters_service.close_chapter(access, str(to_close.id))
    assert exc.value.reason == ChapterErrorReason.book_archived

    with pytest.raises(ChapterError) as exc:
        await chapters_service.reopen_chapter(access, str(to_reopen.id))
    assert exc.value.reason == ChapterErrorReason.book_archived

    assert await _states(book.id) == before
    assert before == {
        to_open.id: ChapterState.planned,
        to_close.id: ChapterState.open,
        to_reopen.id: ChapterState.closed,
    }


# ---------------------------------------------------------------------------
# DoD-16 — a reader and a non-member are refused all three
# ---------------------------------------------------------------------------


# DoD-16: a reader and a caller with no relationship are refused all three
# transitions by the authorization error, and no state changes.
@pytest.mark.parametrize("role", [AccessRole.reader, AccessRole.none])
async def test_reader_and_non_member_are_refused_all_three__DoD16(
    db: DbConfig, role: AccessRole
):
    owner = await _seed_user(f"authz-owner-{role.value}")
    outsider = await _seed_user(f"authz-caller-{role.value}")
    book = await _seed_book(owner.id)
    bad_access = _access(book.id, outsider.id, role=role)
    to_open = await _seed_chapter(book.id, ordinal=1, title="Planned One")
    to_close = await _seed_chapter(
        book.id, ordinal=2, title="Open One", state=ChapterState.open
    )
    to_reopen = await _seed_chapter(
        book.id, ordinal=3, title="Closed One", state=ChapterState.closed
    )
    before = await _states(book.id)

    with pytest.raises(BookAuthorizationError):
        await chapters_service.open_chapter(bad_access, str(to_open.id))

    with pytest.raises(BookAuthorizationError):
        await chapters_service.close_chapter(bad_access, str(to_close.id))

    with pytest.raises(BookAuthorizationError):
        await chapters_service.reopen_chapter(bad_access, str(to_reopen.id))

    assert await _states(book.id) == before


# ---------------------------------------------------------------------------
# DoD-17 — state and modified_at ONLY; no change row, no revision row
# ---------------------------------------------------------------------------


# DoD-17: a successful OPEN touches state and `modified_at` only -- `text`, `version`,
# `ordinal`, `title` and `sketch` are unchanged and neither history table gains a row.
# The success assertion runs first, so this cannot pass against a transition that
# wrote nothing at all.
async def test_open_touches_state_and_modified_at_only__DoD17(db: DbConfig):
    owner = await _seed_user("columns-owner-open")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(
        book.id,
        ordinal=4,
        title="Column Guard",
        sketch="the sketch that must not move",
        state=ChapterState.planned,
        text="the body that must not move",
        version=3,
    )
    before = await _stored(target.id)

    result = await chapters_service.open_chapter(
        _access(book.id, owner.id), str(target.id)
    )

    # The transition actually happened -- without this the rest is vacuous.
    assert result.state == ChapterState.open
    stored = await _stored(target.id)
    assert stored.state == ChapterState.open
    assert result.modified_at is not None

    assert stored.text == before.text
    assert stored.version == before.version
    assert stored.ordinal == before.ordinal
    assert stored.title == before.title
    assert stored.sketch == before.sketch

    assert list(await chapter_changes.list_by_chapter(target.id)) == []
    assert list(await chapter_text_revisions.list_by_chapter(target.id)) == []


# DoD-17: the same for a successful CLOSE.
async def test_close_touches_state_and_modified_at_only__DoD17(db: DbConfig):
    owner = await _seed_user("columns-owner-close")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(
        book.id,
        ordinal=6,
        title="Column Guard",
        sketch="the sketch that must not move",
        state=ChapterState.open,
        text="the body that must not move",
        version=5,
    )
    before = await _stored(target.id)

    result = await chapters_service.close_chapter(
        _access(book.id, owner.id), str(target.id)
    )

    assert result.state == ChapterState.closed
    stored = await _stored(target.id)
    assert stored.state == ChapterState.closed
    assert result.modified_at is not None

    assert stored.text == before.text
    assert stored.version == before.version
    assert stored.ordinal == before.ordinal
    assert stored.title == before.title
    assert stored.sketch == before.sketch

    assert list(await chapter_changes.list_by_chapter(target.id)) == []
    assert list(await chapter_text_revisions.list_by_chapter(target.id)) == []


# DoD-17: the same for a successful REOPEN -- a reopen moves no text, so it writes no
# `ChapterChange` and no `ChapterTextRevision` (002.context.md -> "A reopen writes no
# history"). The variant history a later edit produces is `018`'s.
async def test_reopen_touches_state_and_modified_at_only__DoD17(db: DbConfig):
    owner = await _seed_user("columns-owner-reopen")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(
        book.id,
        ordinal=9,
        title="Column Guard",
        sketch="the sketch that must not move",
        state=ChapterState.closed,
        text="the body that must not move",
        version=7,
    )
    before = await _stored(target.id)

    result = await chapters_service.reopen_chapter(
        _access(book.id, owner.id), str(target.id)
    )

    assert result.state == ChapterState.open
    stored = await _stored(target.id)
    assert stored.state == ChapterState.open
    assert result.modified_at is not None

    assert stored.text == before.text
    assert stored.version == before.version
    assert stored.ordinal == before.ordinal
    assert stored.title == before.title
    assert stored.sketch == before.sketch

    assert list(await chapter_changes.list_by_chapter(target.id)) == []
    assert list(await chapter_text_revisions.list_by_chapter(target.id)) == []


# ---------------------------------------------------------------------------
# DoD-18 — another book's chapter is NOT FOUND on all three
# ---------------------------------------------------------------------------


# DoD-18: a chapter id belonging to another book is not-found on all three entry
# points -- for the OWNER of the access context's book, who holds the capability, so
# the refusal cannot be an authorization failure. The foreign chapter is untouched.
@pytest.mark.parametrize(
    "state", [ChapterState.planned, ChapterState.open, ChapterState.closed]
)
async def test_foreign_chapter_is_not_found_on_all_three__DoD18(
    db: DbConfig, state: ChapterState
):
    owner = await _seed_user(f"crossbook-owner-{state.value}")
    mine = await _seed_book(owner.id, title="Mine")
    theirs = await _seed_book(owner.id, title="Theirs")
    access = _access(mine.id, owner.id)
    foreign = await _seed_chapter(
        theirs.id, ordinal=1, title="Foreign", state=state, text="not mine"
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.open_chapter(access, str(foreign.id))
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.close_chapter(access, str(foreign.id))
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.reopen_chapter(access, str(foreign.id))
    assert exc.value.reason == ChapterErrorReason.not_found

    stored = await _stored(foreign.id)
    assert stored.state == state
    assert stored.text == "not mine"


# DoD-18: an id that exists nowhere is the same not-found reason on all three.
async def test_unknown_chapter_id_is_not_found_on_all_three__DoD18(db: DbConfig):
    owner = await _seed_user("unknown-chapter-owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    with pytest.raises(ChapterError) as exc:
        await chapters_service.open_chapter(access, "999999999999")
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.close_chapter(access, "999999999999")
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.reopen_chapter(access, "999999999999")
    assert exc.value.reason == ChapterErrorReason.not_found
