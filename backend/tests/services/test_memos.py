"""Tests for the memo DTOs and the read / create / update service (026, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002):
    class CreateMemoRequest(BaseModel)      body: str
    class UpdateMemoRequest(BaseModel)      body: str
    class MemoResponse(BaseModel)
        id: str, book_id: str, body: str, ordinal: int, active: bool,
        archived: bool, created_at, modified_at      (NO user_id field)
    class MemoListResponse(BaseModel)       items: list[MemoResponse]
                            in app.models.schemas.memos
    class MemoErrorReason(str, enum.Enum) { not_a_member, not_found }
    class MemoError(Exception)  __init__(reason, message="") -> .reason/.message
    def _require_member(access: authz.BookAccess) -> None
    async def list_memos(access, include_archived: bool = False)
        -> MemoListResponse
    async def create_memo(access, req: CreateMemoRequest) -> MemoResponse
    async def update_memo_body(access, memo_id: str, req: UpdateMemoRequest)
        -> MemoResponse
                            in app.services.memos
plus the frozen `authz.BookAccess` and step 001's `app.db.memos`.

Expected values come from the step spec (002.memo-service.md DoD +
002.context.md + feature context.md — "The wire contract", decisions 1..4),
never from implementation internals:
    - DoD-1: the first memo in a book gets ordinal 1; each later one lands one
      past the highest ordinal among the caller's NON-ARCHIVED memos in that
      book (context.md -> decision 2, 002.context.md -> "which memos the next
      ordinal is computed over");
    - DoD-2: a created memo is active and not archived;
    - DoD-3: `body = ""` succeeds and stores "" — never a validation failure;
    - DoD-4: the list returns only the caller's own memos, in BOTH directions:
      a co-author does not see the owner's, and the book's OWNER does not see a
      co-author's (US-124.AC-2);
    - DoD-5: include-archived defaults to excluding archived memos, and includes
      them when set;
    - DoD-6: the list is ordinal-ordered;
    - DoD-7: the body update writes the body and stamps `modified_at`, leaving
      `ordinal`, `active` and `archived` exactly as they were;
    - DoD-8: all four refusal sources — a non-numeric id, an unknown id, another
      author's memo, another book's memo — raise the SAME not-found reason with
      no distinguishable difference (no existence oracle);
    - DoD-9: a caller who is neither owner nor co-author is refused with the
      not-a-member reason on EVERY entry point, from the service's own typed
      error (context.md -> decision 3: no authz.require, no Capability);
    - DoD-10: `MemoResponse` carries no `user_id` and every id on it is a string;
    - DoD-11: create and body-update both succeed while
      `BookAccess.book_state` is `archived` (context.md -> decision 4, the one
      named carve-out).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. Users, books and pre-existing memo
rows are seeded through the sibling db/ modules, and a `BookAccess` is
constructed directly (a frozen dataclass), as
tests/services/test_book_author_prompts.py does. No route, no HTTP client and no
JWT at this layer — those are step 003's.
"""

from datetime import datetime

import pytest

from app.db import books, users
from app.db import memos as memos_db
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.memo import Memo
from app.models.schemas.memos import (
    CreateMemoRequest,
    MemoListResponse,
    MemoResponse,
    UpdateMemoRequest,
)
from app.models.user import User, UserRole
from app.services import memos as memo_service
from app.services.authz import AccessRole, BookAccess
from app.services.memos import MemoError, MemoErrorReason

# A fixed past anchor, so "the service stamped a fresh timestamp" is an
# unambiguous comparison rather than two wall-clock reads microseconds apart.
ANCHOR = datetime(2026, 1, 1, 9, 0, 0)


# ---------------------------------------------------------------------------
# Seeding helpers (services-test style: rows through the db layer, access
# context constructed directly). There is no shared factory module.
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

    The service is the only thing that stamps timestamps, so a seeded row is
    anchored in the past on purpose.
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


# ---------------------------------------------------------------------------
# DoD-1 (US-123.AC-1) — create appends at max + 1 over the non-archived list
# ---------------------------------------------------------------------------


# DoD-1: the first memo in a book gets ordinal 1, and each later one lands one
# past the highest ordinal so far.
async def test_first_memo_is_ordinal_one_and_later_ones_append__DoD1(db: DbConfig):
    author = await _seed_user("appender")
    book = await _seed_book(title="Append Book", owner_id=author.id)
    access = _access(book.id, author.id)

    first = await memo_service.create_memo(access, CreateMemoRequest(body="one"))
    second = await memo_service.create_memo(access, CreateMemoRequest(body="two"))
    third = await memo_service.create_memo(access, CreateMemoRequest(body="three"))

    assert first.ordinal == 1
    assert second.ordinal == 2
    assert third.ordinal == 3


# DoD-1: the append rule is computed over the caller's NON-ARCHIVED memos —
# archiving the highest one lowers the next ordinal (context.md -> decision 2).
# Live ordinals 1, 2, 3; archiving the 3 means max over the working list is 2,
# so the next memo is 3 — not 4.
async def test_next_ordinal_ignores_archived_memos__DoD1(db: DbConfig):
    author = await _seed_user("archiver")
    book = await _seed_book(title="Gap Book", owner_id=author.id)
    access = _access(book.id, author.id)

    await _seed_memo(book_id=book.id, user_id=author.id, body="a", ordinal=1)
    await _seed_memo(book_id=book.id, user_id=author.id, body="b", ordinal=2)
    await _seed_memo(
        book_id=book.id, user_id=author.id, body="c", ordinal=3, archived=True
    )

    appended = await memo_service.create_memo(access, CreateMemoRequest(body="d"))

    assert appended.ordinal == 3


# DoD-1: the ordinal is scoped per (book, author) — another author's memos in
# the same book, and the caller's memos in another book, do not push it along.
async def test_next_ordinal_is_scoped_per_book_and_author__DoD1(db: DbConfig):
    author = await _seed_user("scoped-author")
    other = await _seed_user("other-author")
    book = await _seed_book(title="Scoped Book", owner_id=author.id)
    other_book = await _seed_book(title="Other Book", owner_id=author.id)

    await _seed_memo(book_id=book.id, user_id=other.id, body="theirs", ordinal=9)
    await _seed_memo(book_id=other_book.id, user_id=author.id, body="mine", ordinal=7)

    created = await memo_service.create_memo(
        _access(book.id, author.id), CreateMemoRequest(body="first here")
    )

    assert created.ordinal == 1


# DoD-1: an author whose only memos in the book are archived starts again at 1 —
# an empty working list gives 1.
async def test_empty_non_archived_list_gives_ordinal_one__DoD1(db: DbConfig):
    author = await _seed_user("all-archived")
    book = await _seed_book(title="Emptied Book", owner_id=author.id)

    await _seed_memo(
        book_id=book.id, user_id=author.id, body="gone", ordinal=5, archived=True
    )

    created = await memo_service.create_memo(
        _access(book.id, author.id), CreateMemoRequest(body="fresh start")
    )

    assert created.ordinal == 1


# ---------------------------------------------------------------------------
# DoD-2 (US-123.AC-3) — a created memo is active and not archived
# ---------------------------------------------------------------------------


# DoD-2: a newly created memo comes back active and not archived, and is stored
# that way; both timestamps are stamped on create (002.context.md ->
# "Timestamps").
async def test_created_memo_is_active_and_not_archived__DoD2(db: DbConfig):
    author = await _seed_user("creator-two")
    book = await _seed_book(title="Fresh Memo Book", owner_id=author.id)

    created = await memo_service.create_memo(
        _access(book.id, author.id), CreateMemoRequest(body="a standing note")
    )

    assert created.active is True
    assert created.archived is False
    assert created.body == "a standing note"
    assert created.created_at is not None
    assert created.modified_at is not None

    row = await _stored(int(created.id))
    assert row.active is True
    assert row.archived is False
    assert row.created_at is not None
    assert row.modified_at is not None


# ---------------------------------------------------------------------------
# DoD-3 (UC-103 postcondition) — an empty body is a value, not a failure
# ---------------------------------------------------------------------------


# DoD-3: creating with body = "" succeeds and stores "" — a new memo is created
# empty, and the empty string is never a validation failure.
async def test_empty_body_create_succeeds_and_stores_empty__DoD3(db: DbConfig):
    author = await _seed_user("empty-creator")
    book = await _seed_book(title="Empty Body Book", owner_id=author.id)
    access = _access(book.id, author.id)

    created = await memo_service.create_memo(access, CreateMemoRequest(body=""))

    assert created.body == ""
    assert (await _stored(int(created.id))).body == ""

    # It is a real, listed memo — not swallowed as "nothing to create".
    listed = await memo_service.list_memos(access)
    assert [item.body for item in listed.items] == [""]


# DoD-3: the create DTO itself places no constraint on the body — "" constructs.
def test_create_request_accepts_empty_body__DoD3():
    assert CreateMemoRequest(body="").body == ""


# DoD-3: clearing a memo to "" through the body update is equally legitimate.
async def test_empty_body_update_succeeds_and_stores_empty__DoD3(db: DbConfig):
    author = await _seed_user("empty-updater")
    book = await _seed_book(title="Clearable Memo Book", owner_id=author.id)
    memo = await _seed_memo(book_id=book.id, user_id=author.id, body="something")

    updated = await memo_service.update_memo_body(
        _access(book.id, author.id), str(memo.id), UpdateMemoRequest(body="")
    )

    assert updated.body == ""
    assert (await _stored(memo.id)).body == ""


# ---------------------------------------------------------------------------
# DoD-4 (US-124.AC-1, US-124.AC-2) — the list is the caller's own memos only
# ---------------------------------------------------------------------------


# DoD-4: a co-author lists only their own memos — the owner's memos in the same
# book are absent (US-124.AC-1).
async def test_co_author_does_not_see_the_owners_memos__DoD4(db: DbConfig):
    owner = await _seed_user("owner-four")
    co_author = await _seed_user("co-author-four")
    book = await _seed_book(title="Shared Memo Book", owner_id=owner.id)

    await _seed_memo(book_id=book.id, user_id=owner.id, body="owner note", ordinal=1)
    await _seed_memo(book_id=book.id, user_id=co_author.id, body="mine", ordinal=1)

    listed = await memo_service.list_memos(
        _access(book.id, co_author.id, role=AccessRole.co_author)
    )

    assert [item.body for item in listed.items] == ["mine"]


# DoD-4: the OTHER direction, which is US-124.AC-2 — the book's OWNER sees NONE
# of a co-author's memos. Owning the book grants no access to another author's
# private notes.
async def test_owner_does_not_see_a_co_authors_memos__DoD4(db: DbConfig):
    owner = await _seed_user("owner-four-b")
    co_author = await _seed_user("co-author-four-b")
    book = await _seed_book(title="Owner Blind Book", owner_id=owner.id)

    await _seed_memo(book_id=book.id, user_id=owner.id, body="owner note", ordinal=1)
    await _seed_memo(
        book_id=book.id, user_id=co_author.id, body="private one", ordinal=1
    )
    await _seed_memo(
        book_id=book.id, user_id=co_author.id, body="private two", ordinal=2
    )

    listed = await memo_service.list_memos(
        _access(book.id, owner.id, role=AccessRole.owner)
    )

    bodies = [item.body for item in listed.items]
    assert bodies == ["owner note"]
    assert "private one" not in bodies
    assert "private two" not in bodies


# DoD-4: the list is also scoped to the book of the access context — the
# caller's memos in another book are absent.
async def test_list_is_scoped_to_the_access_book__DoD4(db: DbConfig):
    author = await _seed_user("two-book-author")
    this_book = await _seed_book(title="This Book", owner_id=author.id)
    that_book = await _seed_book(title="That Book", owner_id=author.id)

    await _seed_memo(book_id=this_book.id, user_id=author.id, body="here", ordinal=1)
    await _seed_memo(book_id=that_book.id, user_id=author.id, body="there", ordinal=1)

    listed = await memo_service.list_memos(_access(this_book.id, author.id))

    assert [item.body for item in listed.items] == ["here"]
    assert all(item.book_id == str(this_book.id) for item in listed.items)


# ---------------------------------------------------------------------------
# DoD-5 (US-128.AC-1, US-128.AC-2) — the include-archived flag
# ---------------------------------------------------------------------------


# DoD-5: by default an archived memo is out of the list — archiving takes a memo
# out of the working list without deleting it (US-128.AC-1).
async def test_archived_memos_are_excluded_by_default__DoD5(db: DbConfig):
    author = await _seed_user("default-lister")
    book = await _seed_book(title="Archive Default Book", owner_id=author.id)

    await _seed_memo(book_id=book.id, user_id=author.id, body="live", ordinal=1)
    await _seed_memo(
        book_id=book.id, user_id=author.id, body="put away", ordinal=2, archived=True
    )

    listed = await memo_service.list_memos(_access(book.id, author.id))

    assert [item.body for item in listed.items] == ["live"]


# DoD-5: with the flag set, archived memos are included alongside the live ones
# (US-128.AC-2) — the archive is reviewable.
async def test_archived_memos_are_included_when_flag_set__DoD5(db: DbConfig):
    author = await _seed_user("archive-lister")
    book = await _seed_book(title="Archive Included Book", owner_id=author.id)

    await _seed_memo(book_id=book.id, user_id=author.id, body="live", ordinal=1)
    await _seed_memo(
        book_id=book.id, user_id=author.id, body="put away", ordinal=2, archived=True
    )

    listed = await memo_service.list_memos(
        _access(book.id, author.id), include_archived=True
    )

    assert [item.body for item in listed.items] == ["live", "put away"]
    assert [item.archived for item in listed.items] == [False, True]


# DoD-5: the include-archived flag is not the on/off axis — an INACTIVE memo is
# listed exactly like an active one, both by default and with the flag set
# (context.md -> decision 1: two independent axes).
async def test_inactive_memos_are_listed_like_active_ones__DoD5(db: DbConfig):
    author = await _seed_user("switched-off-lister")
    book = await _seed_book(title="Inactive Book", owner_id=author.id)

    await _seed_memo(book_id=book.id, user_id=author.id, body="on", ordinal=1)
    await _seed_memo(
        book_id=book.id, user_id=author.id, body="off", ordinal=2, active=False
    )

    default_listed = await memo_service.list_memos(_access(book.id, author.id))
    with_archived = await memo_service.list_memos(
        _access(book.id, author.id), include_archived=True
    )

    assert [item.body for item in default_listed.items] == ["on", "off"]
    assert [item.body for item in with_archived.items] == ["on", "off"]
    assert [item.active for item in default_listed.items] == [True, False]


# ---------------------------------------------------------------------------
# DoD-6 (US-131.AC-2) — the list is ordinal-ordered
# ---------------------------------------------------------------------------


# DoD-6: whatever order the rows were stored in, the list comes back in ordinal
# order — the author's chosen order is the order they see.
async def test_list_is_ordinal_ordered__DoD6(db: DbConfig):
    author = await _seed_user("orderer")
    book = await _seed_book(title="Ordered Book", owner_id=author.id)

    await _seed_memo(book_id=book.id, user_id=author.id, body="third", ordinal=3)
    await _seed_memo(book_id=book.id, user_id=author.id, body="first", ordinal=1)
    await _seed_memo(book_id=book.id, user_id=author.id, body="second", ordinal=2)

    listed = await memo_service.list_memos(_access(book.id, author.id))

    assert [item.ordinal for item in listed.items] == [1, 2, 3]
    assert [item.body for item in listed.items] == ["first", "second", "third"]


# DoD-6: ordinal order holds across a gap left by archiving, and with archived
# rows included (archiving never renumbers — context.md -> decision 2).
async def test_list_is_ordinal_ordered_across_gaps__DoD6(db: DbConfig):
    author = await _seed_user("gap-orderer")
    book = await _seed_book(title="Gapped Order Book", owner_id=author.id)

    await _seed_memo(book_id=book.id, user_id=author.id, body="d", ordinal=7)
    await _seed_memo(
        book_id=book.id, user_id=author.id, body="b", ordinal=2, archived=True
    )
    await _seed_memo(book_id=book.id, user_id=author.id, body="c", ordinal=4)
    await _seed_memo(book_id=book.id, user_id=author.id, body="a", ordinal=1)

    live = await memo_service.list_memos(_access(book.id, author.id))
    everything = await memo_service.list_memos(
        _access(book.id, author.id), include_archived=True
    )

    assert [item.ordinal for item in live.items] == [1, 4, 7]
    assert [item.ordinal for item in everything.items] == [1, 2, 4, 7]


# ---------------------------------------------------------------------------
# DoD-7 (US-125.AC-1) — the body update touches the body and modified_at only
# ---------------------------------------------------------------------------


# DoD-7: the body update writes the new body and stamps `modified_at`, and
# leaves `ordinal`, `active` and `archived` exactly as they were — the two state
# axes have their own verbs and the focus-loss PUT never writes them.
async def test_body_update_writes_body_and_stamps_modified_at_only__DoD7(
    db: DbConfig,
):
    author = await _seed_user("body-updater")
    book = await _seed_book(title="Body Update Book", owner_id=author.id)
    memo = await _seed_memo(
        book_id=book.id,
        user_id=author.id,
        body="the old text",
        ordinal=7,
        active=False,
        archived=False,
    )

    updated = await memo_service.update_memo_body(
        _access(book.id, author.id), str(memo.id), UpdateMemoRequest(body="the new text")
    )

    # The body changed...
    assert updated.body == "the new text"
    # ...and nothing else on the DTO did.
    assert updated.id == str(memo.id)
    assert updated.ordinal == 7
    assert updated.active is False
    assert updated.archived is False

    row = await _stored(memo.id)
    assert row.body == "the new text"
    assert row.ordinal == 7
    assert row.active is False
    assert row.archived is False
    # `modified_at` is stamped forward; `created_at` is not touched
    # (002.context.md -> "Timestamps": modified_at only on update).
    assert row.modified_at is not None
    assert row.modified_at > ANCHOR
    assert row.created_at == ANCHOR


# DoD-7: the update leaves an archived memo archived — the archive axis is not
# reachable through the body verb in either direction.
async def test_body_update_leaves_archived_flag_untouched__DoD7(db: DbConfig):
    author = await _seed_user("archived-body-updater")
    book = await _seed_book(title="Archived Memo Book", owner_id=author.id)
    memo = await _seed_memo(
        book_id=book.id,
        user_id=author.id,
        body="old",
        ordinal=3,
        active=True,
        archived=True,
    )

    updated = await memo_service.update_memo_body(
        _access(book.id, author.id), str(memo.id), UpdateMemoRequest(body="new")
    )

    assert updated.body == "new"
    assert updated.archived is True
    assert updated.active is True
    assert updated.ordinal == 3

    row = await _stored(memo.id)
    assert row.archived is True
    assert row.active is True
    assert row.ordinal == 3


# DoD-7: the update DTO carries a body and nothing else — no version token and
# no state flags (context.md -> decision 5, "Two axes, four verbs").
def test_update_request_carries_only_a_body__DoD7():
    assert set(UpdateMemoRequest.model_fields) == {"body"}


# ---------------------------------------------------------------------------
# DoD-8 (US-124.AC-1) — the four refusal sources are ONE indistinguishable
# refusal: no existence oracle
# ---------------------------------------------------------------------------


# DoD-8: a non-numeric id, an unknown id, another author's memo and another
# book's memo all raise the SAME not-found reason, with nothing about the raised
# error telling them apart. Asserting sameness (not merely "each raises") is the
# point: a difference between any two would be an existence oracle.
async def test_all_four_refusal_sources_are_indistinguishable__DoD8(db: DbConfig):
    author = await _seed_user("resolver-caller")
    other_author = await _seed_user("resolver-other")
    book = await _seed_book(title="Resolver Book", owner_id=author.id)
    other_book = await _seed_book(title="Resolver Other Book", owner_id=author.id)
    access = _access(book.id, author.id)

    others_memo = await _seed_memo(
        book_id=book.id, user_id=other_author.id, body="not yours", ordinal=1
    )
    other_books_memo = await _seed_memo(
        book_id=other_book.id, user_id=author.id, body="elsewhere", ordinal=1
    )

    candidates = {
        "non-numeric id": "not-a-number",
        "unknown id": "9999999999999999",
        "another author's memo": str(others_memo.id),
        "another book's memo": str(other_books_memo.id),
    }

    errors: dict[str, MemoError] = {}
    for label, memo_id in candidates.items():
        with pytest.raises(MemoError) as exc_info:
            await memo_service.update_memo_body(
                access, memo_id, UpdateMemoRequest(body="trespass")
            )
        errors[label] = exc_info.value

    # Every one of the four is the not-found reason...
    for label, error in errors.items():
        assert error.reason is MemoErrorReason.not_found, label

    # ...and no pair of them is distinguishable from another.
    fingerprints = {
        (type(error), error.reason, error.message) for error in errors.values()
    }
    assert len(fingerprints) == 1

    # Nothing was written to either foreign row.
    assert (await _stored(others_memo.id)).body == "not yours"
    assert (await _stored(other_books_memo.id)).body == "elsewhere"


# DoD-8: a memo the caller does own, in the book of the access context, is NOT
# refused — the refusal above is about ownership and scope, not about the
# resolver rejecting everything.
async def test_the_callers_own_memo_resolves__DoD8(db: DbConfig):
    author = await _seed_user("rightful-owner")
    book = await _seed_book(title="Rightful Book", owner_id=author.id)
    memo = await _seed_memo(book_id=book.id, user_id=author.id, body="mine", ordinal=1)

    updated = await memo_service.update_memo_body(
        _access(book.id, author.id), str(memo.id), UpdateMemoRequest(body="edited")
    )

    assert updated.id == str(memo.id)
    assert updated.body == "edited"


# ---------------------------------------------------------------------------
# DoD-9 (authorization.md, the fourth row-ownership rule) — non-members are
# refused by the service's own helper, on every entry point
# ---------------------------------------------------------------------------


# DoD-9: a `reader` is refused on ALL THREE entry points with the service's own
# typed not-a-member reason.
async def test_reader_is_refused_on_every_entry_point__DoD9(db: DbConfig):
    owner = await _seed_user("owner-nine")
    reader = await _seed_user("reader-nine")
    book = await _seed_book(title="Reader Refused Book", owner_id=owner.id)
    memo = await _seed_memo(book_id=book.id, user_id=owner.id, body="owner's", ordinal=1)
    access = _access(book.id, reader.id, role=AccessRole.reader)

    with pytest.raises(MemoError) as list_exc:
        await memo_service.list_memos(access)
    assert list_exc.value.reason is MemoErrorReason.not_a_member

    with pytest.raises(MemoError) as create_exc:
        await memo_service.create_memo(access, CreateMemoRequest(body="not mine"))
    assert create_exc.value.reason is MemoErrorReason.not_a_member

    with pytest.raises(MemoError) as update_exc:
        await memo_service.update_memo_body(
            access, str(memo.id), UpdateMemoRequest(body="not mine")
        )
    assert update_exc.value.reason is MemoErrorReason.not_a_member

    # Nothing was created for the reader, and the owner's memo is untouched.
    assert (
        await memos_db.list_for_author(book.id, reader.id, include_archived=True) == []
    )
    assert (await _stored(memo.id)).body == "owner's"


# DoD-9: a caller with NO relationship to the book is refused the same way on
# all three entry points.
async def test_non_member_is_refused_on_every_entry_point__DoD9(db: DbConfig):
    owner = await _seed_user("owner-nine-b")
    stranger = await _seed_user("stranger-nine")
    book = await _seed_book(title="Stranger Refused Book", owner_id=owner.id)
    memo = await _seed_memo(book_id=book.id, user_id=owner.id, body="owner's", ordinal=1)
    access = _access(book.id, stranger.id, role=AccessRole.none)

    with pytest.raises(MemoError) as list_exc:
        await memo_service.list_memos(access)
    assert list_exc.value.reason is MemoErrorReason.not_a_member

    with pytest.raises(MemoError) as create_exc:
        await memo_service.create_memo(access, CreateMemoRequest(body="trespass"))
    assert create_exc.value.reason is MemoErrorReason.not_a_member

    with pytest.raises(MemoError) as update_exc:
        await memo_service.update_memo_body(
            access, str(memo.id), UpdateMemoRequest(body="trespass")
        )
    assert update_exc.value.reason is MemoErrorReason.not_a_member

    assert (
        await memos_db.list_for_author(book.id, stranger.id, include_archived=True)
        == []
    )
    assert (await _stored(memo.id)).body == "owner's"


# DoD-9: the refusal is the SERVICE's own membership helper — calling it
# directly with a non-member raises the service's typed error, and it admits an
# owner and a co-author outright (context.md -> decision 3: no `authz.require`,
# no `Capability`).
def test_membership_helper_is_the_refusal_site__DoD9():
    for refused_role in (AccessRole.reader, AccessRole.none):
        with pytest.raises(MemoError) as exc_info:
            memo_service._require_member(_access(1, 2, role=refused_role))
        assert exc_info.value.reason is MemoErrorReason.not_a_member

    # Owner and co-author pass through with nothing raised.
    memo_service._require_member(_access(1, 2, role=AccessRole.owner))
    memo_service._require_member(_access(1, 2, role=AccessRole.co_author))


# DoD-9: this step's service owns exactly two typed reasons — membership and the
# single not-found. Anything else on this path is produced upstream by the
# `book_access` dependency and never reaches here.
def test_service_reasons_are_membership_and_one_not_found__DoD9():
    assert list(MemoErrorReason) == [
        MemoErrorReason.not_a_member,
        MemoErrorReason.not_found,
        MemoErrorReason.invalid_reorder_set,
    ]


# DoD-9: a co-author is a member — the membership rule refuses by role, not by
# book ownership, so a co-author uses all three entry points normally.
async def test_co_author_is_a_member_on_every_entry_point__DoD9(db: DbConfig):
    owner = await _seed_user("owner-nine-c")
    co_author = await _seed_user("co-author-nine")
    book = await _seed_book(title="Co-author Allowed Book", owner_id=owner.id)
    access = _access(book.id, co_author.id, role=AccessRole.co_author)

    created = await memo_service.create_memo(access, CreateMemoRequest(body="mine"))
    updated = await memo_service.update_memo_body(
        access, created.id, UpdateMemoRequest(body="mine, edited")
    )
    listed = await memo_service.list_memos(access)

    assert created.ordinal == 1
    assert updated.body == "mine, edited"
    assert [item.body for item in listed.items] == ["mine, edited"]


# ---------------------------------------------------------------------------
# DoD-10 (quick-reference.md, the Memos DTO subsection) — no user_id, ids are
# strings
# ---------------------------------------------------------------------------


# DoD-10: the response DTO carries exactly the wire-contract fields and NO
# `user_id` — the subject is always the caller, and echoing an id would invite
# the reading that another author's memo is addressable here.
def test_memo_response_has_no_user_id_field__DoD10():
    field_names = set(MemoResponse.model_fields)

    assert field_names == {
        "id",
        "book_id",
        "body",
        "ordinal",
        "active",
        "archived",
        "created_at",
        "modified_at",
    }
    assert "user_id" not in field_names
    assert not [name for name in field_names if "user" in name.lower()]


# DoD-10: every id on a real response is a STRING — snowflakes exceed the JS
# safe-integer range — on the create, update and list paths alike.
async def test_every_id_on_a_response_is_a_string__DoD10(db: DbConfig):
    author = await _seed_user("string-ids")
    book = await _seed_book(title="String Id Book", owner_id=author.id)
    access = _access(book.id, author.id)

    created = await memo_service.create_memo(access, CreateMemoRequest(body="note"))
    updated = await memo_service.update_memo_body(
        access, created.id, UpdateMemoRequest(body="note, edited")
    )
    listed = await memo_service.list_memos(access)

    assert isinstance(listed, MemoListResponse)
    assert len(listed.items) == 1

    for response in (created, updated, listed.items[0]):
        assert isinstance(response, MemoResponse)
        assert isinstance(response.id, str)
        assert isinstance(response.book_id, str)
        assert response.book_id == str(book.id)
        assert not hasattr(response, "user_id")

    assert created.id == updated.id == listed.items[0].id


# ---------------------------------------------------------------------------
# DoD-11 (authorization.md, the archived-book carve-out) — an archived book does
# not refuse memo writes
# ---------------------------------------------------------------------------


# DoD-11: create succeeds while `BookAccess.book_state` is `archived` — a memo
# is the author's private note ABOUT a book they have deliberately set aside, so
# the chapters-style archived-book refusal deliberately does not apply here.
async def test_create_succeeds_on_an_archived_book__DoD11(db: DbConfig):
    author = await _seed_user("archived-book-creator")
    book = await _seed_book(title="Set Aside Book", owner_id=author.id)
    access = _access(book.id, author.id, book_state=BookState.archived)

    created = await memo_service.create_memo(
        access, CreateMemoRequest(body="still writing notes")
    )

    assert created.body == "still writing notes"
    assert created.ordinal == 1
    assert created.active is True
    assert created.archived is False
    assert (await _stored(int(created.id))).body == "still writing notes"

    # And the list still answers on an archived book.
    listed = await memo_service.list_memos(access)
    assert [item.body for item in listed.items] == ["still writing notes"]


# DoD-11: the body update likewise succeeds while the book is archived.
async def test_body_update_succeeds_on_an_archived_book__DoD11(db: DbConfig):
    author = await _seed_user("archived-book-updater")
    book = await _seed_book(title="Set Aside Edit Book", owner_id=author.id)
    memo = await _seed_memo(book_id=book.id, user_id=author.id, body="old", ordinal=1)
    access = _access(book.id, author.id, book_state=BookState.archived)

    updated = await memo_service.update_memo_body(
        access, str(memo.id), UpdateMemoRequest(body="revised while archived")
    )

    assert updated.body == "revised while archived"
    assert (await _stored(memo.id)).body == "revised while archived"
