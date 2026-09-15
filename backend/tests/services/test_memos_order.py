"""Tests for the whole-set memo reorder service (feature 026, step 004).

Bound to the frozen skeleton (status.md -> Skeleton -> Step 004):
    class ReorderMemosRequest(BaseModel)    memo_ids: list[str]
                            in app.models.schemas.memos
    MemoErrorReason gains a third member: invalid_reorder_set
    async def reorder_memos(access: authz.BookAccess, req: ReorderMemosRequest)
        -> MemoListResponse
                            in app.services.memos

Expected values come from the SPEC ONLY -- `004.memo-reorder.md` (Goal,
Interface intent, DoD-1..DoD-8), `004.context.md` and the feature `context.md`
(decision 2 "Ordinals -- append, gap, append again", decision 3 "row ownership,
not a capability", decision 4 "the archived-book carve-out") -- never from
implementation internals:

    - DoD-1 (US-126.AC-2): submitting the caller's full memo id list in a new
      order rewrites ordinals 1..N in that order, and the returned envelope
      reflects the new order;
    - DoD-2 (US-131.AC-2): the following ordinal-ordered read returns the memos
      in exactly the submitted order;
    - DoD-3: each invalid set -- too short, too long, one carrying a duplicate,
      one carrying an id outside the caller's non-archived set -- is refused
      with the invalid-set reason, and NOTHING is written;
    - DoD-4 (US-124.AC-1): another author's id and another book's id are refused
      as an invalid set, indistinguishably from an id belonging to nobody (no
      existence oracle -- `004.context.md` -> "Why the refusal is one reason,
      not four");
    - DoD-5 (US-128.AC-1): archived memos are outside the submitted set --
      including one is refused, and a successful reorder of the survivors leaves
      the archived row's ordinal untouched (archiving left a gap and reorder does
      not reclaim it);
    - DoD-8: a reorder succeeds while `BookAccess.book_state` is `archived`.

DoD-6 (route ordering) and DoD-7 (401 / 404 / 403) are HTTP-level and live in
tests/routes/test_memos_order.py.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. Rows are seeded through the sibling
db/ modules -- including the archived flag, written directly, because step 005's
archive route does not exist yet -- and a `BookAccess` is constructed directly,
as tests/services/test_memos.py does. There is no shared factory module.
"""

from datetime import datetime

import pytest

from app.db import books, users
from app.db import memos as memos_db
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.memo import Memo
from app.models.schemas.memos import ReorderMemosRequest
from app.models.user import User, UserRole
from app.services import memos as memo_service
from app.services.authz import AccessRole, BookAccess
from app.services.memos import MemoError, MemoErrorReason

# A fixed past anchor: "nothing was written" is then an unambiguous comparison
# (the service is the only thing that stamps `modified_at`).
ANCHOR = datetime(2026, 1, 1, 9, 0, 0)


# ---------------------------------------------------------------------------
# Seeding helpers (copied from tests/services/test_memos.py -- no shared
# factory module exists)
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(*, title: str, owner_id: int) -> Book:
    return await books.create(
        Book(
            title=title,
            description="desc",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt="",
            active_notes="",
        )
    )


async def _seed_memo(
    *,
    book_id: int,
    user_id: int,
    body: str = "seeded memo",
    ordinal: int = 1,
    active: bool = True,
    archived: bool = False,
) -> Memo:
    """A stored memo row, written straight through the db/ layer.

    `archived` is set here rather than through a route on purpose: step 005's
    archive endpoint does not exist for this step's tests to depend on.
    """
    return await memos_db.create(
        Memo(
            book_id=book_id,
            user_id=user_id,
            body=body,
            ordinal=ordinal,
            active=active,
            archived=archived,
            created_at=ANCHOR,
            modified_at=ANCHOR,
        )
    )


def _access(
    book_id: int,
    user_id: int,
    *,
    role: AccessRole = AccessRole.owner,
    book_state: BookState = BookState.active,
) -> BookAccess:
    """The access context the `book_access` dependency would have resolved."""
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=role,
        book_state=book_state,
        visibility=Visibility.private,
        collaboration_mode=CollaborationMode.free,
    )


async def _stored(memo_id: int) -> Memo:
    row = await memos_db.get_by_id(memo_id)
    assert row is not None
    return row


async def _ordinals(*rows: Memo) -> list[int]:
    return [(await _stored(row.id)).ordinal for row in rows]


async def _seed_three(author: User, book: Book) -> tuple[Memo, Memo, Memo]:
    """Three live memos of the caller, ordinals 1, 2, 3."""
    first = await _seed_memo(book_id=book.id, user_id=author.id, body="A", ordinal=1)
    second = await _seed_memo(book_id=book.id, user_id=author.id, body="B", ordinal=2)
    third = await _seed_memo(book_id=book.id, user_id=author.id, body="C", ordinal=3)
    return first, second, third


def _req(*rows: Memo) -> ReorderMemosRequest:
    return ReorderMemosRequest(memo_ids=[str(row.id) for row in rows])


# ---------------------------------------------------------------------------
# DoD-1 (US-126.AC-2) -- the full list in a new order rewrites ordinals 1..N
# ---------------------------------------------------------------------------


# DoD-1: submitting the caller's full id list in a new order writes ordinals
# 1..N in exactly that order, and the returned envelope shows the new order.
async def test_full_list_rewrites_ordinals_one_to_n__DoD1(db: DbConfig):
    author = await _seed_user("reorder-author-1")
    book = await _seed_book(title="Reorder Book", owner_id=author.id)
    access = _access(book.id, author.id)
    first, second, third = await _seed_three(author, book)

    result = await memo_service.reorder_memos(access, _req(third, first, second))

    assert [m.body for m in result.items] == ["C", "A", "B"]
    assert [m.ordinal for m in result.items] == [1, 2, 3]
    # ...and the rewrite is persisted, not merely reported
    assert (await _stored(third.id)).ordinal == 1
    assert (await _stored(first.id)).ordinal == 2
    assert (await _stored(second.id)).ordinal == 3


# DoD-1: the rule is positional, not a swap -- a full reversal of a four-memo
# list lands 1..4 in the submitted order.
async def test_reversal_of_a_four_memo_list_lands_one_to_four__DoD1(db: DbConfig):
    author = await _seed_user("reorder-author-1b")
    book = await _seed_book(title="Four Memo Book", owner_id=author.id)
    access = _access(book.id, author.id)
    first, second, third = await _seed_three(author, book)
    fourth = await _seed_memo(book_id=book.id, user_id=author.id, body="D", ordinal=4)

    result = await memo_service.reorder_memos(
        access, _req(fourth, third, second, first)
    )

    assert [m.body for m in result.items] == ["D", "C", "B", "A"]
    assert [m.ordinal for m in result.items] == [1, 2, 3, 4]
    assert await _ordinals(first, second, third, fourth) == [4, 3, 2, 1]


# ---------------------------------------------------------------------------
# DoD-2 (US-131.AC-2) -- the ordinal-ordered read IS the submitted order
# ---------------------------------------------------------------------------


# DoD-2: the author's order is the order the assistant receives them in -- the
# ordinary ordinal-ordered read, after a reorder, is exactly the submitted list.
async def test_read_after_reorder_is_the_submitted_order__DoD2(db: DbConfig):
    author = await _seed_user("reorder-author-2")
    book = await _seed_book(title="Read Order Book", owner_id=author.id)
    access = _access(book.id, author.id)
    first, second, third = await _seed_three(author, book)

    await memo_service.reorder_memos(access, _req(second, third, first))

    listed = await memo_service.list_memos(access)
    assert [m.body for m in listed.items] == ["B", "C", "A"]


# ---------------------------------------------------------------------------
# DoD-3 -- every invalid set is refused, and nothing is written
# ---------------------------------------------------------------------------


# DoD-3: a list SHORTER than the caller's non-archived set is refused with the
# invalid-set reason, and no ordinal moves.
async def test_too_short_list_is_refused_and_writes_nothing__DoD3(db: DbConfig):
    author = await _seed_user("reorder-author-3a")
    book = await _seed_book(title="Too Short Book", owner_id=author.id)
    access = _access(book.id, author.id)
    first, second, third = await _seed_three(author, book)

    with pytest.raises(MemoError) as exc_info:
        await memo_service.reorder_memos(access, _req(third, first))

    assert exc_info.value.reason is MemoErrorReason.invalid_reorder_set
    assert await _ordinals(first, second, third) == [1, 2, 3]
    assert (await _stored(first.id)).modified_at == ANCHOR
    assert (await _stored(second.id)).modified_at == ANCHOR
    assert (await _stored(third.id)).modified_at == ANCHOR


# DoD-3: a list LONGER than the caller's non-archived set is refused, and no
# ordinal moves.
async def test_too_long_list_is_refused_and_writes_nothing__DoD3(db: DbConfig):
    author = await _seed_user("reorder-author-3b")
    book = await _seed_book(title="Too Long Book", owner_id=author.id)
    access = _access(book.id, author.id)
    first, second, third = await _seed_three(author, book)

    too_long = ReorderMemosRequest(
        memo_ids=[str(first.id), str(second.id), str(third.id), "987654321"]
    )
    with pytest.raises(MemoError) as exc_info:
        await memo_service.reorder_memos(access, too_long)

    assert exc_info.value.reason is MemoErrorReason.invalid_reorder_set
    assert await _ordinals(first, second, third) == [1, 2, 3]


# DoD-3: a list of the right LENGTH that repeats one id (and therefore drops
# another) is refused, and no ordinal moves.
async def test_duplicate_id_is_refused_and_writes_nothing__DoD3(db: DbConfig):
    author = await _seed_user("reorder-author-3c")
    book = await _seed_book(title="Duplicate Book", owner_id=author.id)
    access = _access(book.id, author.id)
    first, second, third = await _seed_three(author, book)

    with pytest.raises(MemoError) as exc_info:
        await memo_service.reorder_memos(access, _req(first, first, second))

    assert exc_info.value.reason is MemoErrorReason.invalid_reorder_set
    assert await _ordinals(first, second, third) == [1, 2, 3]
    assert (await _stored(first.id)).modified_at == ANCHOR
    assert (await _stored(second.id)).modified_at == ANCHOR
    assert (await _stored(third.id)).modified_at == ANCHOR


# DoD-3: a list of the right length carrying an id that is in nobody's set is
# refused, and no ordinal moves.
async def test_unknown_id_in_the_set_is_refused_and_writes_nothing__DoD3(db: DbConfig):
    author = await _seed_user("reorder-author-3d")
    book = await _seed_book(title="Unknown Id Book", owner_id=author.id)
    access = _access(book.id, author.id)
    first, second, third = await _seed_three(author, book)

    submitted = ReorderMemosRequest(
        memo_ids=[str(first.id), str(second.id), "987654321"]
    )
    with pytest.raises(MemoError) as exc_info:
        await memo_service.reorder_memos(access, submitted)

    assert exc_info.value.reason is MemoErrorReason.invalid_reorder_set
    assert await _ordinals(first, second, third) == [1, 2, 3]


# DoD-3: the reason is the invalid-set one and deliberately NOT the not-found
# one -- the caller is told their set is wrong, not that a resource is missing
# (Interface intent -> "One added error reason").
async def test_the_refusal_reason_is_not_the_not_found_reason__DoD3(db: DbConfig):
    author = await _seed_user("reorder-author-3e")
    book = await _seed_book(title="Reason Book", owner_id=author.id)
    access = _access(book.id, author.id)
    first, _second, _third = await _seed_three(author, book)

    with pytest.raises(MemoError) as exc_info:
        await memo_service.reorder_memos(access, _req(first))

    assert exc_info.value.reason is not MemoErrorReason.not_found
    assert exc_info.value.reason is MemoErrorReason.invalid_reorder_set


# ---------------------------------------------------------------------------
# DoD-4 (US-124.AC-1) -- a foreign id is simply not in the caller's set, and
# the refusal reveals nothing about whether it exists
# ---------------------------------------------------------------------------


# DoD-4: an id belonging to another AUTHOR of the same book, an id belonging to
# another BOOK of the same author, and an id belonging to nobody are all refused
# as one and the same invalid set -- a caller cannot probe existence by watching
# the refusal change shape (`004.context.md` -> "Why the refusal is one reason,
# not four").
async def test_foreign_ids_are_refused_indistinguishably__DoD4(db: DbConfig):
    author = await _seed_user("reorder-author-4")
    other_author = await _seed_user("reorder-other-author-4")
    book = await _seed_book(title="Foreign Id Book", owner_id=author.id)
    other_book = await _seed_book(title="Another Book", owner_id=author.id)
    access = _access(book.id, author.id)

    first, second, third = await _seed_three(author, book)
    other_authors_memo = await _seed_memo(
        book_id=book.id, user_id=other_author.id, body="THEIRS", ordinal=1
    )
    other_books_memo = await _seed_memo(
        book_id=other_book.id, user_id=author.id, body="ELSEWHERE", ordinal=1
    )

    fingerprints: set[tuple[str, MemoErrorReason, str]] = set()
    for foreign_id in (
        str(other_authors_memo.id),
        str(other_books_memo.id),
        "987654321",
    ):
        submitted = ReorderMemosRequest(
            memo_ids=[str(first.id), str(second.id), foreign_id]
        )
        with pytest.raises(MemoError) as exc_info:
            await memo_service.reorder_memos(access, submitted)
        err = exc_info.value
        assert err.reason is MemoErrorReason.invalid_reorder_set
        fingerprints.add((type(err).__name__, err.reason, err.message))

    # One refusal, not three: nothing distinguishes an id that exists elsewhere
    # from an id that exists nowhere.
    assert len(fingerprints) == 1

    # ...and neither foreign row -- nor the caller's own list -- was touched.
    assert await _ordinals(first, second, third) == [1, 2, 3]
    assert (await _stored(other_authors_memo.id)).ordinal == 1
    assert (await _stored(other_books_memo.id)).ordinal == 1


# DoD-4: the foreign rows stay unwritten even when the submitted list is the
# caller's own set plus a foreign id appended (a "too long" probe).
async def test_appending_a_foreign_id_leaves_it_untouched__DoD4(db: DbConfig):
    author = await _seed_user("reorder-author-4b")
    other_author = await _seed_user("reorder-other-author-4b")
    book = await _seed_book(title="Probe Book", owner_id=author.id)
    access = _access(book.id, author.id)
    first, second, third = await _seed_three(author, book)
    theirs = await _seed_memo(
        book_id=book.id, user_id=other_author.id, body="THEIRS", ordinal=5
    )

    submitted = ReorderMemosRequest(
        memo_ids=[str(first.id), str(second.id), str(third.id), str(theirs.id)]
    )
    with pytest.raises(MemoError) as exc_info:
        await memo_service.reorder_memos(access, submitted)

    assert exc_info.value.reason is MemoErrorReason.invalid_reorder_set
    assert (await _stored(theirs.id)).ordinal == 5
    assert (await _stored(theirs.id)).modified_at == ANCHOR
    assert await _ordinals(first, second, third) == [1, 2, 3]


# ---------------------------------------------------------------------------
# DoD-5 (US-128.AC-1) -- archived memos are outside the submitted set
# ---------------------------------------------------------------------------


# DoD-5, first half: an archived memo's id inside the submitted list is refused
# as an invalid set -- an archived memo is not in the list the author reorders.
async def test_including_an_archived_id_is_refused__DoD5(db: DbConfig):
    author = await _seed_user("reorder-author-5a")
    book = await _seed_book(title="Archived Member Book", owner_id=author.id)
    access = _access(book.id, author.id)
    live_a = await _seed_memo(book_id=book.id, user_id=author.id, body="A", ordinal=1)
    live_b = await _seed_memo(book_id=book.id, user_id=author.id, body="B", ordinal=2)
    archived = await _seed_memo(
        book_id=book.id, user_id=author.id, body="GONE", ordinal=3, archived=True
    )

    with pytest.raises(MemoError) as exc_info:
        await memo_service.reorder_memos(access, _req(live_b, live_a, archived))

    assert exc_info.value.reason is MemoErrorReason.invalid_reorder_set
    assert await _ordinals(live_a, live_b, archived) == [1, 2, 3]


# DoD-5, second half: a successful reorder of the survivors leaves the archived
# row's ordinal exactly as it was -- archiving left a gap and reorder does not
# reclaim it (context.md -> decision 2).
async def test_reorder_leaves_archived_ordinals_untouched__DoD5(db: DbConfig):
    author = await _seed_user("reorder-author-5b")
    book = await _seed_book(title="Archived Gap Book", owner_id=author.id)
    access = _access(book.id, author.id)
    live_a = await _seed_memo(book_id=book.id, user_id=author.id, body="A", ordinal=1)
    archived = await _seed_memo(
        book_id=book.id, user_id=author.id, body="GONE", ordinal=2, archived=True
    )
    live_c = await _seed_memo(book_id=book.id, user_id=author.id, body="C", ordinal=3)

    result = await memo_service.reorder_memos(access, _req(live_c, live_a))

    # the envelope carries only the non-archived memos, in the submitted order
    assert [m.body for m in result.items] == ["C", "A"]
    assert [m.ordinal for m in result.items] == [1, 2]
    # the survivors were renumbered 1..N ...
    assert (await _stored(live_c.id)).ordinal == 1
    assert (await _stored(live_a.id)).ordinal == 2
    # ...and the archived row kept the ordinal it had, and stays archived
    assert (await _stored(archived.id)).ordinal == 2
    assert (await _stored(archived.id)).archived is True
    assert (await _stored(archived.id)).modified_at == ANCHOR


# DoD-5: the submitted set is the caller's non-archived memos ONLY -- with every
# memo archived but one, that one id alone is the whole valid set.
async def test_the_valid_set_excludes_archived_memos__DoD5(db: DbConfig):
    author = await _seed_user("reorder-author-5c")
    book = await _seed_book(title="Mostly Archived Book", owner_id=author.id)
    access = _access(book.id, author.id)
    archived_one = await _seed_memo(
        book_id=book.id, user_id=author.id, body="X", ordinal=1, archived=True
    )
    archived_two = await _seed_memo(
        book_id=book.id, user_id=author.id, body="Y", ordinal=2, archived=True
    )
    live = await _seed_memo(book_id=book.id, user_id=author.id, body="Z", ordinal=3)

    result = await memo_service.reorder_memos(access, _req(live))

    assert [m.body for m in result.items] == ["Z"]
    assert [m.ordinal for m in result.items] == [1]
    assert (await _stored(archived_one.id)).ordinal == 1
    assert (await _stored(archived_two.id)).ordinal == 2


# ---------------------------------------------------------------------------
# DoD-8 -- the archived-book carve-out covers reorder too
# ---------------------------------------------------------------------------


# DoD-8 (authorization.md -> the archived-book carve-out; context.md ->
# decision 4): a memo is the author's private note ABOUT a book they have set
# aside, so a reorder succeeds while the book's state is `archived`.
async def test_reorder_succeeds_on_an_archived_book__DoD8(db: DbConfig):
    author = await _seed_user("reorder-author-8")
    book = await _seed_book(title="Archived Book", owner_id=author.id)
    access = _access(book.id, author.id, book_state=BookState.archived)
    first, second, third = await _seed_three(author, book)

    result = await memo_service.reorder_memos(access, _req(third, second, first))

    assert [m.body for m in result.items] == ["C", "B", "A"]
    assert [m.ordinal for m in result.items] == [1, 2, 3]
    assert await _ordinals(first, second, third) == [3, 2, 1]
