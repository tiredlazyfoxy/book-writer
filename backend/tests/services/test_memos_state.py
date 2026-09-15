"""Tests for the four memo state verbs (feature 026, step 005) -- service half.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 005):
    async def activate_memo(access: authz.BookAccess, memo_id: str)   -> MemoResponse
    async def deactivate_memo(access: authz.BookAccess, memo_id: str) -> MemoResponse
    async def archive_memo(access: authz.BookAccess, memo_id: str)    -> MemoResponse
    async def restore_memo(access: authz.BookAccess, memo_id: str)    -> MemoResponse
                            in app.services.memos
    `MemoErrorReason` is UNCHANGED at exactly three members -- this step adds
    no reason, no status and (in particular) no 409.

Expected values come from the SPEC ONLY -- `005.memo-state-axes.md` (Goal,
Interface intent, DoD-1..DoD-12), `005.context.md` ("The flag each verb writes,
and the flags it must leave alone") and the feature `context.md` (decision 1
"two booleans, not one state enum", decision 2 "Ordinals -- append, gap, append
again", decision 4 "the archived-book carve-out", decision 5 "no 409", decision
6 "No DELETE") -- never from implementation internals.

The contract this module pins, verb by verb:

    | verb       | writes                       | must NOT touch            |
    | activate   | active = True                | archived, ordinal, body   |
    | deactivate | active = False               | archived, ordinal, body   |
    | archive    | archived = True              | active, ordinal, body     |
    | restore    | archived = False, ord = max+1| active, body              |

and, across all four, `modified_at` is stamped.

By DoD item:
    - DoD-1  (US-127.AC-1): a deactivated memo stays in the ordinary read;
    - DoD-2  (US-127.AC-2): it comes back with `active` False;
    - DoD-3  (US-127.AC-4): activating an inactive memo sets `active` True;
    - DoD-4  (US-127.AC-5): deactivating the caller's ONLY active memo succeeds
      -- the empty active set is a legitimate end state, nothing refuses;
    - DoD-5  (US-128.AC-1): an archived memo leaves the working list and appears
      only in the include-archived read;
    - DoD-6  (US-128.AC-2): a restored memo is appended LAST, at one past the
      highest ordinal among the caller's non-archived memos -- never back to the
      slot it held;
    - DoD-7  (domain-book.md, the ordinal rules): archiving leaves a gap and
      renumbers nothing;
    - DoD-8  (domain-book.md, two booleans not one enum): archiving preserves
      `active`, so a memo archived while off comes back off and one archived
      while on comes back on;
    - DoD-9  (US-124.AC-1): all four verbs answer the one `not_found` refusal
      for an unknown / non-numeric / another author's / another book's memo;
    - DoD-10 (context.md, repeat state calls): each verb applied to a memo
      already in that state succeeds and returns the row unchanged -- no 409
      and no new reason exists in this family. "Unchanged" has no carve-out:
      restore on a memo that is NOT archived leaves `ordinal` alone too (the
      max+1 append in the table above is the archived-memo path, DoD-6);
    - DoD-11 (US-128.AC-3): no call ever removes a memo from the
      include-archived read (the 405 half is HTTP-level, in tests/routes/);
    - DoD-12 (the archived-book carve-out): all four verbs succeed while
      `BookAccess.book_state` is `archived`.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. Rows are seeded through the sibling
db/ modules and a `BookAccess` is constructed directly, as
tests/services/test_memos.py and tests/services/test_memos_order.py do. There is
no shared factory module.
"""

from datetime import datetime

import pytest

from app.db import books, users
from app.db import memos as memos_db
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.memo import Memo
from app.models.user import User, UserRole
from app.services import memos as memo_service
from app.services.authz import AccessRole, BookAccess
from app.services.memos import MemoError, MemoErrorReason

# A fixed past anchor: "this row was written" / "this row was not" is then an
# unambiguous comparison (the service is the only thing that stamps timestamps).
ANCHOR = datetime(2026, 1, 1, 9, 0, 0)

# The four verbs under test, in the order the step file declares them.
VERBS = (
    ("activate", memo_service.activate_memo),
    ("deactivate", memo_service.deactivate_memo),
    ("archive", memo_service.archive_memo),
    ("restore", memo_service.restore_memo),
)


# ---------------------------------------------------------------------------
# Seeding helpers (copied from tests/services/test_memos_order.py -- no shared
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
    """A stored memo row, written straight through the db/ layer."""
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


# ---------------------------------------------------------------------------
# DoD-1 (US-127.AC-1) -- a deactivated memo stays in the list
# ---------------------------------------------------------------------------


# DoD-1: switching a memo off does not remove it from the working list -- the
# ordinary (non-archived) read still returns it. Off is not gone; that is the
# archive axis, and it is a different axis.
async def test_deactivated_memo_stays_in_the_ordinary_list__DoD1(db: DbConfig):
    author = await _seed_user("state-deactivate-1")
    book = await _seed_book(title="Deactivate Book 1", owner_id=author.id)
    access = _access(book.id, author.id)
    first = await _seed_memo(book_id=book.id, user_id=author.id, body="A", ordinal=1)
    second = await _seed_memo(book_id=book.id, user_id=author.id, body="B", ordinal=2)

    await memo_service.deactivate_memo(access, str(first.id))

    listed = await memo_service.list_memos(access)
    assert [item.id for item in listed.items] == [str(first.id), str(second.id)]
    assert [item.body for item in listed.items] == ["A", "B"]


# ---------------------------------------------------------------------------
# DoD-2 (US-127.AC-2) -- deactivate writes `active` False and nothing else
# ---------------------------------------------------------------------------


# DoD-2: the deactivated memo comes back with `active` False (the state the
# client renders its visibly-off marking from), while `archived`, `ordinal` and
# `body` are untouched and `modified_at` is stamped.
async def test_deactivate_writes_active_false_only__DoD2(db: DbConfig):
    author = await _seed_user("state-deactivate-2")
    book = await _seed_book(title="Deactivate Book 2", owner_id=author.id)
    access = _access(book.id, author.id)
    memo = await _seed_memo(
        book_id=book.id,
        user_id=author.id,
        body="a standing note",
        ordinal=7,
        active=True,
        archived=False,
    )

    result = await memo_service.deactivate_memo(access, str(memo.id))

    assert result.id == str(memo.id)
    assert result.active is False
    assert result.archived is False
    assert result.ordinal == 7
    assert result.body == "a standing note"

    row = await _stored(memo.id)
    assert row.active is False
    assert row.archived is False
    assert row.ordinal == 7
    assert row.body == "a standing note"
    assert row.created_at == ANCHOR
    assert row.modified_at is not None
    assert row.modified_at > ANCHOR


# DoD-2: the flag is visible on the ordinary read too, not only on the verb's
# own response.
async def test_deactivated_memo_is_listed_as_inactive__DoD2(db: DbConfig):
    author = await _seed_user("state-deactivate-2b")
    book = await _seed_book(title="Deactivate Book 2b", owner_id=author.id)
    access = _access(book.id, author.id)
    memo = await _seed_memo(book_id=book.id, user_id=author.id, body="A", ordinal=1)

    await memo_service.deactivate_memo(access, str(memo.id))

    listed = await memo_service.list_memos(access)
    assert len(listed.items) == 1
    assert listed.items[0].active is False
    assert listed.items[0].archived is False


# ---------------------------------------------------------------------------
# DoD-3 (US-127.AC-4) -- activate writes `active` True and nothing else
# ---------------------------------------------------------------------------


# DoD-3: activating an inactive memo sets `active` True again, making it
# eligible for context once more; `archived`, `ordinal` and `body` are
# untouched and `modified_at` is stamped.
async def test_activate_writes_active_true_only__DoD3(db: DbConfig):
    author = await _seed_user("state-activate-3")
    book = await _seed_book(title="Activate Book 3", owner_id=author.id)
    access = _access(book.id, author.id)
    memo = await _seed_memo(
        book_id=book.id,
        user_id=author.id,
        body="switched off earlier",
        ordinal=4,
        active=False,
        archived=False,
    )

    result = await memo_service.activate_memo(access, str(memo.id))

    assert result.active is True
    assert result.archived is False
    assert result.ordinal == 4
    assert result.body == "switched off earlier"

    row = await _stored(memo.id)
    assert row.active is True
    assert row.archived is False
    assert row.ordinal == 4
    assert row.body == "switched off earlier"
    assert row.created_at == ANCHOR
    assert row.modified_at is not None
    assert row.modified_at > ANCHOR


# DoD-3: activate does not reach across to the archive axis -- an archived memo
# that is switched back on is still archived (only `restore` writes that flag).
async def test_activate_leaves_the_archive_flag_alone__DoD3(db: DbConfig):
    author = await _seed_user("state-activate-3b")
    book = await _seed_book(title="Activate Book 3b", owner_id=author.id)
    access = _access(book.id, author.id)
    memo = await _seed_memo(
        book_id=book.id,
        user_id=author.id,
        body="A",
        ordinal=2,
        active=False,
        archived=True,
    )

    result = await memo_service.activate_memo(access, str(memo.id))

    assert result.active is True
    assert result.archived is True
    assert result.ordinal == 2

    row = await _stored(memo.id)
    assert row.active is True
    assert row.archived is True
    assert row.ordinal == 2


# ---------------------------------------------------------------------------
# DoD-4 (US-127.AC-5) -- the empty active set is a legitimate end state
# ---------------------------------------------------------------------------


# DoD-4: deactivating the caller's ONLY active memo succeeds. Nothing refuses:
# there is no "at least one active memo" rule and no book-level memos-off switch
# to consult, so the author is simply left with no active memo.
async def test_deactivating_the_only_active_memo_succeeds__DoD4(db: DbConfig):
    author = await _seed_user("state-deactivate-4")
    book = await _seed_book(title="Last Active Book", owner_id=author.id)
    access = _access(book.id, author.id)
    only = await _seed_memo(
        book_id=book.id, user_id=author.id, body="the only one", ordinal=1, active=True
    )

    result = await memo_service.deactivate_memo(access, str(only.id))

    assert result.active is False

    listed = await memo_service.list_memos(access)
    # Still in the list, and nothing in it is active any more.
    assert [item.id for item in listed.items] == [str(only.id)]
    assert [item.active for item in listed.items] == [False]


# DoD-4: the same when the author's other memos are merely already off -- the
# last *active* one goes off without complaint.
async def test_deactivating_the_last_active_of_several_succeeds__DoD4(db: DbConfig):
    author = await _seed_user("state-deactivate-4b")
    book = await _seed_book(title="Last Active Book 2", owner_id=author.id)
    access = _access(book.id, author.id)
    off_one = await _seed_memo(
        book_id=book.id, user_id=author.id, body="A", ordinal=1, active=False
    )
    last_on = await _seed_memo(
        book_id=book.id, user_id=author.id, body="B", ordinal=2, active=True
    )

    result = await memo_service.deactivate_memo(access, str(last_on.id))

    assert result.active is False
    assert (await _stored(off_one.id)).active is False
    assert (await _stored(last_on.id)).active is False


# ---------------------------------------------------------------------------
# DoD-5 (US-128.AC-1) -- archive takes the memo out of the working list
# ---------------------------------------------------------------------------


# DoD-5: an archived memo is absent from the default read and present in the
# include-archived read, flagged `archived`.
async def test_archived_memo_leaves_the_working_list__DoD5(db: DbConfig):
    author = await _seed_user("state-archive-5")
    book = await _seed_book(title="Archive Book 5", owner_id=author.id)
    access = _access(book.id, author.id)
    kept = await _seed_memo(book_id=book.id, user_id=author.id, body="A", ordinal=1)
    gone = await _seed_memo(book_id=book.id, user_id=author.id, body="B", ordinal=2)

    result = await memo_service.archive_memo(access, str(gone.id))
    assert result.archived is True

    live = await memo_service.list_memos(access)
    assert [item.id for item in live.items] == [str(kept.id)]

    everything = await memo_service.list_memos(access, include_archived=True)
    assert [item.id for item in everything.items] == [str(kept.id), str(gone.id)]
    by_id = {item.id: item for item in everything.items}
    assert by_id[str(gone.id)].archived is True
    assert by_id[str(kept.id)].archived is False


# DoD-5: archive writes `archived` and stamps `modified_at`, leaving `body`
# alone (`005.context.md` -> the verb table).
async def test_archive_writes_archived_true_and_stamps__DoD5(db: DbConfig):
    author = await _seed_user("state-archive-5b")
    book = await _seed_book(title="Archive Book 5b", owner_id=author.id)
    access = _access(book.id, author.id)
    memo = await _seed_memo(
        book_id=book.id, user_id=author.id, body="the text", ordinal=3
    )

    result = await memo_service.archive_memo(access, str(memo.id))

    assert result.archived is True
    assert result.body == "the text"

    row = await _stored(memo.id)
    assert row.archived is True
    assert row.body == "the text"
    assert row.created_at == ANCHOR
    assert row.modified_at is not None
    assert row.modified_at > ANCHOR


# ---------------------------------------------------------------------------
# DoD-6 (US-128.AC-2) -- restore appends LAST, never back to the old slot
# ---------------------------------------------------------------------------


# DoD-6: a restored memo returns to the working list appended last, at one past
# the highest ordinal among the caller's non-archived memos. The fixture is
# built so that "back to the old slot" and "appended last" give different
# answers: the memo is archived from ordinal 2 while a live memo sits at 3, so
# an old-slot restore would read 2 and an append-last restore reads 4.
async def test_restore_appends_last_not_to_the_old_slot__DoD6(db: DbConfig):
    author = await _seed_user("state-restore-6")
    book = await _seed_book(title="Restore Book 6", owner_id=author.id)
    access = _access(book.id, author.id)
    first = await _seed_memo(book_id=book.id, user_id=author.id, body="A", ordinal=1)
    middle = await _seed_memo(book_id=book.id, user_id=author.id, body="B", ordinal=2)
    last = await _seed_memo(book_id=book.id, user_id=author.id, body="C", ordinal=3)

    await memo_service.archive_memo(access, str(middle.id))
    result = await memo_service.restore_memo(access, str(middle.id))

    assert result.archived is False
    assert result.ordinal == 4
    assert result.ordinal != 2  # not the slot it held

    # The survivors are where they were; the restored memo is last in the list.
    assert (await _stored(first.id)).ordinal == 1
    assert (await _stored(last.id)).ordinal == 3
    row = await _stored(middle.id)
    assert row.archived is False
    assert row.ordinal == 4
    assert row.body == "B"
    assert row.modified_at is not None
    assert row.modified_at > ANCHOR

    listed = await memo_service.list_memos(access)
    assert [item.id for item in listed.items] == [
        str(first.id),
        str(last.id),
        str(middle.id),
    ]


# DoD-6: the append rule is computed over the caller's NON-ARCHIVED memos, so a
# second still-archived row holding a higher ordinal does not push the restored
# memo past the live maximum. Live ordinals are 1 and 5, a separate archived row
# sits at 9, so the restored memo is 6.
async def test_restore_appends_past_the_live_maximum_only__DoD6(db: DbConfig):
    author = await _seed_user("state-restore-6b")
    book = await _seed_book(title="Restore Book 6b", owner_id=author.id)
    access = _access(book.id, author.id)
    live_low = await _seed_memo(book_id=book.id, user_id=author.id, body="A", ordinal=1)
    live_high = await _seed_memo(book_id=book.id, user_id=author.id, body="B", ordinal=5)
    still_archived = await _seed_memo(
        book_id=book.id, user_id=author.id, body="C", ordinal=9, archived=True
    )
    coming_back = await _seed_memo(
        book_id=book.id, user_id=author.id, body="D", ordinal=2, archived=True
    )

    result = await memo_service.restore_memo(access, str(coming_back.id))

    assert result.archived is False
    assert result.ordinal == 6

    assert (await _stored(live_low.id)).ordinal == 1
    assert (await _stored(live_high.id)).ordinal == 5
    # The row that stayed archived is untouched by someone else's restore.
    assert (await _stored(still_archived.id)).ordinal == 9
    assert (await _stored(still_archived.id)).archived is True


# DoD-6: restoring into an empty working list gives ordinal 1 -- the same single
# append rule (`005.context.md` -> "one past the highest, 1 when there are
# none").
async def test_restore_into_an_empty_list_is_ordinal_one__DoD6(db: DbConfig):
    author = await _seed_user("state-restore-6c")
    book = await _seed_book(title="Restore Book 6c", owner_id=author.id)
    access = _access(book.id, author.id)
    memo = await _seed_memo(
        book_id=book.id, user_id=author.id, body="A", ordinal=7, archived=True
    )

    result = await memo_service.restore_memo(access, str(memo.id))

    assert result.archived is False
    assert result.ordinal == 1


# ---------------------------------------------------------------------------
# DoD-7 (domain-book.md, the ordinal rules) -- archiving leaves a gap
# ---------------------------------------------------------------------------


# DoD-7: archiving the MIDDLE of three memos renumbers nothing -- the survivors
# keep ordinals 1 and 3 (the gap at 2 is the design, the `chapters` DELETE
# precedent), and the archived row keeps the ordinal it had.
async def test_archiving_leaves_a_gap_and_renumbers_nothing__DoD7(db: DbConfig):
    author = await _seed_user("state-archive-7")
    book = await _seed_book(title="Gap Book 7", owner_id=author.id)
    access = _access(book.id, author.id)
    first = await _seed_memo(book_id=book.id, user_id=author.id, body="A", ordinal=1)
    middle = await _seed_memo(book_id=book.id, user_id=author.id, body="B", ordinal=2)
    last = await _seed_memo(book_id=book.id, user_id=author.id, body="C", ordinal=3)

    result = await memo_service.archive_memo(access, str(middle.id))
    assert result.ordinal == 2  # archive does not touch the ordinal either

    # Materialize each row with its own await -- never a generator expression
    # around `await`.
    stored_first = await _stored(first.id)
    stored_middle = await _stored(middle.id)
    stored_last = await _stored(last.id)
    assert stored_first.ordinal == 1
    assert stored_middle.ordinal == 2
    assert stored_last.ordinal == 3

    # The gap is visible in the working list: 1 and 3, with no 2.
    listed = await memo_service.list_memos(access)
    assert [item.ordinal for item in listed.items] == [1, 3]
    assert [item.id for item in listed.items] == [str(first.id), str(last.id)]


# DoD-7: archiving the LAST memo does not free its ordinal either -- the
# survivors are untouched and the archived row still reads 3.
async def test_archiving_the_last_memo_renumbers_nothing__DoD7(db: DbConfig):
    author = await _seed_user("state-archive-7b")
    book = await _seed_book(title="Gap Book 7b", owner_id=author.id)
    access = _access(book.id, author.id)
    first = await _seed_memo(book_id=book.id, user_id=author.id, body="A", ordinal=1)
    second = await _seed_memo(book_id=book.id, user_id=author.id, body="B", ordinal=2)
    third = await _seed_memo(book_id=book.id, user_id=author.id, body="C", ordinal=3)

    await memo_service.archive_memo(access, str(third.id))

    stored_first = await _stored(first.id)
    stored_second = await _stored(second.id)
    stored_third = await _stored(third.id)
    assert stored_first.ordinal == 1
    assert stored_second.ordinal == 2
    assert stored_third.ordinal == 3


# ---------------------------------------------------------------------------
# DoD-8 (domain-book.md, two booleans not one enum) -- archive preserves `active`
# ---------------------------------------------------------------------------


# DoD-8: four memos make this unambiguous. One is archived while switched ON and
# one while switched OFF; both are then restored, and each comes back carrying
# the flag it went in with. This is the proof that the model holds two
# independent booleans rather than one three-value enum -- archive clearing
# `active` would collapse the two cases into one.
async def test_archive_and_restore_preserve_the_active_flag__DoD8(db: DbConfig):
    author = await _seed_user("state-two-axes-8")
    book = await _seed_book(title="Two Axes Book", owner_id=author.id)
    access = _access(book.id, author.id)
    was_on = await _seed_memo(
        book_id=book.id, user_id=author.id, body="ON", ordinal=1, active=True
    )
    was_off = await _seed_memo(
        book_id=book.id, user_id=author.id, body="OFF", ordinal=2, active=False
    )
    stays_on = await _seed_memo(
        book_id=book.id, user_id=author.id, body="STAY-ON", ordinal=3, active=True
    )
    stays_off = await _seed_memo(
        book_id=book.id, user_id=author.id, body="STAY-OFF", ordinal=4, active=False
    )

    # Archiving preserves `active` in both directions, right away.
    archived_on = await memo_service.archive_memo(access, str(was_on.id))
    archived_off = await memo_service.archive_memo(access, str(was_off.id))
    assert archived_on.archived is True
    assert archived_on.active is True
    assert archived_off.archived is True
    assert archived_off.active is False

    # ...and the restore returns each in the state its author chose.
    restored_on = await memo_service.restore_memo(access, str(was_on.id))
    restored_off = await memo_service.restore_memo(access, str(was_off.id))
    assert restored_on.archived is False
    assert restored_on.active is True
    assert restored_off.archived is False
    assert restored_off.active is False

    stored_was_on = await _stored(was_on.id)
    stored_was_off = await _stored(was_off.id)
    assert stored_was_on.active is True
    assert stored_was_off.active is False

    # The two bystanders kept their own flags throughout.
    stored_stays_on = await _stored(stays_on.id)
    stored_stays_off = await _stored(stays_off.id)
    assert stored_stays_on.active is True
    assert stored_stays_on.archived is False
    assert stored_stays_off.active is False
    assert stored_stays_off.archived is False


# DoD-8: the restore verb writes only the archive axis -- it never switches a
# memo back on as a side effect of returning it to the list.
async def test_restore_does_not_switch_a_memo_back_on__DoD8(db: DbConfig):
    author = await _seed_user("state-two-axes-8b")
    book = await _seed_book(title="Two Axes Book 2", owner_id=author.id)
    access = _access(book.id, author.id)
    memo = await _seed_memo(
        book_id=book.id,
        user_id=author.id,
        body="A",
        ordinal=1,
        active=False,
        archived=True,
    )

    result = await memo_service.restore_memo(access, str(memo.id))

    assert result.archived is False
    assert result.active is False
    assert (await _stored(memo.id)).active is False


# ---------------------------------------------------------------------------
# DoD-9 (US-124.AC-1) -- one `not_found` refusal, on all four verbs
# ---------------------------------------------------------------------------


# DoD-9: each of the four verbs refuses an unknown id, a non-numeric id, another
# author's memo and another book's memo with the same single `not_found` -- no
# existence oracle, and no verb has a refusal of its own.
async def test_every_verb_refuses_unreachable_ids_identically__DoD9(db: DbConfig):
    author = await _seed_user("state-refusal-9")
    other_author = await _seed_user("state-refusal-9-other")
    book = await _seed_book(title="Refusal Book", owner_id=author.id)
    other_book = await _seed_book(title="Other Refusal Book", owner_id=author.id)
    access = _access(book.id, author.id)

    foreign_author_memo = await _seed_memo(
        book_id=book.id, user_id=other_author.id, body="theirs", ordinal=1
    )
    foreign_book_memo = await _seed_memo(
        book_id=other_book.id, user_id=author.id, body="elsewhere", ordinal=1
    )

    unreachable = [
        "not-a-number",
        "999999999999999",
        str(foreign_author_memo.id),
        str(foreign_book_memo.id),
    ]

    fingerprints = set()
    for verb_name, verb in VERBS:
        for memo_id in unreachable:
            with pytest.raises(MemoError) as excinfo:
                await verb(access, memo_id)
            assert excinfo.value.reason is MemoErrorReason.not_found, (
                f"{verb_name} on {memo_id}"
            )
            fingerprints.add(
                (type(excinfo.value), excinfo.value.reason, excinfo.value.message)
            )

    # Sameness, not merely "each raises": one refusal shape across all sixteen
    # (verb, id) combinations.
    assert len(fingerprints) == 1

    # Neither foreign row was written by any of the sixteen attempts.
    stored_foreign_author = await _stored(foreign_author_memo.id)
    stored_foreign_book = await _stored(foreign_book_memo.id)
    assert stored_foreign_author.active is True
    assert stored_foreign_author.archived is False
    assert stored_foreign_author.ordinal == 1
    assert stored_foreign_author.modified_at == ANCHOR
    assert stored_foreign_book.active is True
    assert stored_foreign_book.archived is False
    assert stored_foreign_book.ordinal == 1
    assert stored_foreign_book.modified_at == ANCHOR


# DoD-9: the positive counterpart -- the caller's own memo is reachable by every
# one of the four verbs, so the refusal above is about reachability and not
# about the verbs being closed.
async def test_every_verb_admits_the_callers_own_memo__DoD9(db: DbConfig):
    author = await _seed_user("state-refusal-9b")
    book = await _seed_book(title="Own Memo Book", owner_id=author.id)
    access = _access(book.id, author.id)

    for verb_name, verb in VERBS:
        memo = await _seed_memo(
            book_id=book.id, user_id=author.id, body=verb_name, ordinal=1
        )
        result = await verb(access, str(memo.id))
        assert result.id == str(memo.id)


# DoD-9: this step adds no error reason -- `MemoErrorReason` is still exactly
# the three members step 004 left it at, and no 409-shaped reason exists.
def test_no_new_error_reason_is_added_by_the_state_verbs__DoD9():
    assert list(MemoErrorReason) == [
        MemoErrorReason.not_a_member,
        MemoErrorReason.not_found,
        MemoErrorReason.invalid_reorder_set,
    ]


# ---------------------------------------------------------------------------
# DoD-10 (context.md, repeat state calls) -- idempotent no-ops, never a 409
# ---------------------------------------------------------------------------


# DoD-10: activating an already-active memo succeeds and returns the row
# unchanged -- an idempotent state assertion, not a refused transition.
async def test_activate_on_an_active_memo_is_a_no_op__DoD10(db: DbConfig):
    author = await _seed_user("state-noop-10a")
    book = await _seed_book(title="No-op Book A", owner_id=author.id)
    access = _access(book.id, author.id)
    memo = await _seed_memo(
        book_id=book.id,
        user_id=author.id,
        body="already on",
        ordinal=5,
        active=True,
        archived=False,
    )

    result = await memo_service.activate_memo(access, str(memo.id))

    assert result.id == str(memo.id)
    assert result.active is True
    assert result.archived is False
    assert result.ordinal == 5
    assert result.body == "already on"

    row = await _stored(memo.id)
    assert row.active is True
    assert row.archived is False
    assert row.ordinal == 5
    assert row.body == "already on"
    assert row.created_at == ANCHOR


# DoD-10: deactivating an already-inactive memo succeeds and returns the row
# unchanged.
async def test_deactivate_on_an_inactive_memo_is_a_no_op__DoD10(db: DbConfig):
    author = await _seed_user("state-noop-10b")
    book = await _seed_book(title="No-op Book B", owner_id=author.id)
    access = _access(book.id, author.id)
    memo = await _seed_memo(
        book_id=book.id,
        user_id=author.id,
        body="already off",
        ordinal=5,
        active=False,
        archived=False,
    )

    result = await memo_service.deactivate_memo(access, str(memo.id))

    assert result.active is False
    assert result.archived is False
    assert result.ordinal == 5
    assert result.body == "already off"

    row = await _stored(memo.id)
    assert row.active is False
    assert row.archived is False
    assert row.ordinal == 5
    assert row.body == "already off"


# DoD-10: archiving an already-archived memo succeeds and returns the row
# unchanged -- including its `ordinal` and its `active` flag.
async def test_archive_on_an_archived_memo_is_a_no_op__DoD10(db: DbConfig):
    author = await _seed_user("state-noop-10c")
    book = await _seed_book(title="No-op Book C", owner_id=author.id)
    access = _access(book.id, author.id)
    memo = await _seed_memo(
        book_id=book.id,
        user_id=author.id,
        body="already archived",
        ordinal=5,
        active=False,
        archived=True,
    )

    result = await memo_service.archive_memo(access, str(memo.id))

    assert result.archived is True
    assert result.active is False
    assert result.ordinal == 5
    assert result.body == "already archived"

    row = await _stored(memo.id)
    assert row.archived is True
    assert row.active is False
    assert row.ordinal == 5
    assert row.body == "already archived"


# DoD-10: restoring a memo that is NOT archived is a full no-op -- `ordinal`
# included. DoD-10 says "row unchanged" with no carve-out for restore, and the
# alternative would let an idempotent-looking verb silently relocate a live memo
# in the author's list. The fixture makes the assertion meaningful: three live
# memos at ordinals 1, 2, 3 and the restore targets the MIDDLE one, so "unchanged"
# reads 2 while an unconditional append-last would read 4. DoD-6 still governs
# restore of a genuinely archived memo.
async def test_restore_on_a_live_memo_is_a_full_no_op__DoD10(db: DbConfig):
    author = await _seed_user("state-noop-10d")
    book = await _seed_book(title="No-op Book D", owner_id=author.id)
    access = _access(book.id, author.id)
    first = await _seed_memo(book_id=book.id, user_id=author.id, body="A", ordinal=1)
    memo = await _seed_memo(
        book_id=book.id,
        user_id=author.id,
        body="never archived",
        ordinal=2,
        active=False,
        archived=False,
    )
    last = await _seed_memo(book_id=book.id, user_id=author.id, body="C", ordinal=3)

    result = await memo_service.restore_memo(access, str(memo.id))

    assert result.id == str(memo.id)
    assert result.archived is False
    assert result.active is False
    assert result.body == "never archived"
    # Unchanged, not appended last: the memo was never archived, so nothing moves.
    assert result.ordinal == 2

    row = await _stored(memo.id)
    assert row.archived is False
    assert row.active is False
    assert row.body == "never archived"
    assert row.ordinal == 2

    # The bystanders are untouched as well -- materialize each with its own await.
    stored_first = await _stored(first.id)
    stored_last = await _stored(last.id)
    assert stored_first.ordinal == 1
    assert stored_last.ordinal == 3

    # Still exactly three memos, in their original order -- the no-op created
    # nothing and reordered nothing.
    listed = await memo_service.list_memos(access)
    assert [item.id for item in listed.items] == [
        str(first.id),
        str(memo.id),
        str(last.id),
    ]
    assert [item.ordinal for item in listed.items] == [1, 2, 3]


# DoD-10: applying each verb TWICE lands the same state as applying it once --
# the second call is a no-op and never raises.
async def test_each_verb_is_idempotent_when_repeated__DoD10(db: DbConfig):
    author = await _seed_user("state-noop-10e")
    book = await _seed_book(title="No-op Book E", owner_id=author.id)
    access = _access(book.id, author.id)

    activated = await _seed_memo(
        book_id=book.id, user_id=author.id, body="A", ordinal=1, active=False
    )
    await memo_service.activate_memo(access, str(activated.id))
    twice_activated = await memo_service.activate_memo(access, str(activated.id))
    assert twice_activated.active is True

    deactivated = await _seed_memo(
        book_id=book.id, user_id=author.id, body="B", ordinal=2, active=True
    )
    await memo_service.deactivate_memo(access, str(deactivated.id))
    twice_deactivated = await memo_service.deactivate_memo(access, str(deactivated.id))
    assert twice_deactivated.active is False

    archived = await _seed_memo(
        book_id=book.id, user_id=author.id, body="C", ordinal=3
    )
    await memo_service.archive_memo(access, str(archived.id))
    first_archived_ordinal = (await _stored(archived.id)).ordinal
    twice_archived = await memo_service.archive_memo(access, str(archived.id))
    assert twice_archived.archived is True
    # Archive is a pure flag write: the repeat did not move the ordinal either.
    assert (await _stored(archived.id)).ordinal == first_archived_ordinal

    restored = await _seed_memo(
        book_id=book.id, user_id=author.id, body="D", ordinal=4, archived=True
    )
    await memo_service.restore_memo(access, str(restored.id))
    twice_restored = await memo_service.restore_memo(access, str(restored.id))
    assert twice_restored.archived is False


# ---------------------------------------------------------------------------
# DoD-11 (US-128.AC-3) -- nothing removes a memo
# ---------------------------------------------------------------------------


# DoD-11: no sequence of the four verbs ever removes a memo from the
# include-archived read. Archive-not-delete: the row is always still there.
# (The "no DELETE route -> 405" half is HTTP-level and lives in
# tests/routes/test_memos_state.py.)
async def test_no_verb_ever_removes_a_memo__DoD11(db: DbConfig):
    author = await _seed_user("state-never-deleted-11")
    book = await _seed_book(title="Never Deleted Book", owner_id=author.id)
    access = _access(book.id, author.id)
    memo = await _seed_memo(
        book_id=book.id, user_id=author.id, body="indestructible", ordinal=1
    )

    for _verb_name, verb in VERBS:
        await verb(access, str(memo.id))
        everything = await memo_service.list_memos(access, include_archived=True)
        assert [item.id for item in everything.items] == [str(memo.id)]
        assert everything.items[0].body == "indestructible"

    # And the row itself is still stored at the end of the whole sequence.
    row = await _stored(memo.id)
    assert row.body == "indestructible"


# ---------------------------------------------------------------------------
# DoD-12 (the archived-book carve-out) -- all four verbs work on an archived book
# ---------------------------------------------------------------------------


# DoD-12: a memo is the author's private note *about* a book they set aside, so
# all four state verbs succeed while `BookAccess.book_state` is `archived`.
async def test_all_four_verbs_succeed_on_an_archived_book__DoD12(db: DbConfig):
    author = await _seed_user("state-archived-book-12")
    book = await _seed_book(title="Archived Book", owner_id=author.id)
    access = _access(book.id, author.id, book_state=BookState.archived)

    memo = await _seed_memo(
        book_id=book.id, user_id=author.id, body="on a shelved book", ordinal=1
    )

    deactivated = await memo_service.deactivate_memo(access, str(memo.id))
    assert deactivated.active is False

    activated = await memo_service.activate_memo(access, str(memo.id))
    assert activated.active is True

    archived = await memo_service.archive_memo(access, str(memo.id))
    assert archived.archived is True

    restored = await memo_service.restore_memo(access, str(memo.id))
    assert restored.archived is False
