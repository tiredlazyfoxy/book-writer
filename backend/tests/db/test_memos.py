"""Tests for the session-free db/memos module (feature 026, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    class Memo(SQLModel, table=True)
        __tablename__ = "memos"; NO __table_args__ (no unique constraint);
        id: int (snowflake PK), book_id: int (FK books.id),
        user_id: int (FK users.id), body: str, ordinal: int,
        active: bool = True, archived: bool = False,
        created_at: datetime | None, modified_at: datetime | None
                                                     in app.models.memo
    async def create(row: Memo) -> Memo                  in app.db.memos
    async def get_by_id(memo_id: int) -> Memo | None     in app.db.memos
    async def list_for_author(book_id: int, user_id: int,
                              include_archived: bool = False) -> list[Memo]
                                                         in app.db.memos
    async def update(row: Memo) -> Memo                  in app.db.memos
    (and NO delete function, at all)

Expected values come from the step spec (001.memo-table.md DoD +
001.context.md + context.md decisions 1/2/6), never from implementation
internals:
    - DoD-1 (US-123.AC-1): an author holds MANY memos in one book — several
      rows for the same (book_id, user_id) pair persist side by side and the
      DATABASE refuses none of them. Asserted by two successful inserts that
      both read back, not by inspecting the model for a constraint object, so
      a later refactor that added a unique constraint must fail this test;
    - DoD-2 (US-123.AC-3): a created row defaults to active=True and
      archived=False, and every column survives create -> get_by_id;
    - DoD-3 (UC-103 postcondition): body="" is stored and returned as "",
      never coerced to null — an empty memo is the normal freshly-created
      state (001.context.md -> "Gotcha: `""` is a value");
    - DoD-4 (US-124.AC-1, US-124.AC-2): list_for_author returns only rows for
      the (book, author) pair asked for — never another author's memos in the
      same book, never the same author's memos in another book;
    - DoD-5 (US-128.AC-1): with include_archived off (its DEFAULT), archived
      rows are absent from the list;
    - DoD-6 (US-128.AC-2): with include_archived on, archived rows come back
      alongside the live ones;
    - DoD-7 (US-127.AC-1): inactive rows are listed exactly like active ones —
      list_for_author filters on `archived` only and never on `active`;
    - DoD-8 (US-131.AC-2): the list comes back in ASCENDING `ordinal` order;
    - DoD-9 (US-125.AC-1): update persists a changed body and returns STORED
      state rather than the in-memory argument, and the db/ layer sets NO
      timestamps of its own (timestamps are the service's policy);
    - DoD-10 (US-127.AC-4, US-128.AC-2): update persists the two flags
      INDEPENDENTLY — writing `active` never rewrites `archived`, and the
      reverse (two independent axes, not one state enum);
    - DoD-11 (US-128.AC-3): the module exposes NO delete function —
      archive-not-delete is structural at the data layer (decision 6).

DoD-12, DoD-13 and DoD-14 (codec, TABLE_REGISTRY, fresh-DB schema) live in the
flat module backend/tests/test_data_domain_memos.py, per 001.context.md ->
"Test seeding".

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
Supporting book/user rows are seeded through the sibling db/ modules (there is
no HTTP in a db-layer spec).
"""

from datetime import datetime

from app.db import books, memos, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.memo import Memo
from app.models.user import User, UserRole


async def _seed_user(username: str) -> User:
    """A persisted author user, seeded through the sibling db/ module."""
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(*, title: str, owner_id: int) -> Book:
    """A persisted book with every required non-null field set."""
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


# ---------------------------------------------------------------------------
# DoD-1 — many memos per (book, author); the database refuses none of them
# ---------------------------------------------------------------------------


# DoD-1 (US-123.AC-1): an author holds MANY memos in one book. Three rows for
# the very same (book_id, user_id) pair are inserted and all three persist side
# by side with distinct ids — the database rejects none of them. This is a
# database-level assertion: if a unique constraint on (book_id, user_id) were
# ever added, the second insert would raise and this test would fail.
async def test_many_memos_for_one_pair_all_persist__DoD1(db: DbConfig):
    author = await _seed_user("memo-many-author")
    book = await _seed_book(title="Many Memos", owner_id=author.id)

    first = await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="first note", ordinal=1)
    )
    second = await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="second note", ordinal=2)
    )
    third = await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="third note", ordinal=3)
    )

    # Three distinct rows for one pair.
    assert len({first.id, second.id, third.id}) == 3

    # All three are genuinely stored and readable back.
    for created, body in (
        (first, "first note"),
        (second, "second note"),
        (third, "third note"),
    ):
        stored = await memos.get_by_id(created.id)
        assert stored is not None
        assert stored.body == body
        assert stored.book_id == book.id
        assert stored.user_id == author.id

    # And the author's list holds all three.
    listed = await memos.list_for_author(book.id, author.id)
    assert len(listed) == 3
    assert {row.body for row in listed} == {"first note", "second note", "third note"}


# ---------------------------------------------------------------------------
# DoD-2 — default flags, and every column survives create -> get_by_id
# ---------------------------------------------------------------------------


# DoD-2 (US-123.AC-3): a memo created without naming the flags defaults to
# active=True and archived=False, and every column survives the round trip
# through create -> get_by_id (snowflake PK populated on create; both FKs, the
# body, the ordinal, both flags and both timestamps read back unchanged).
async def test_created_row_defaults_and_round_trips_every_column__DoD2(db: DbConfig):
    author = await _seed_user("memo-defaults-author")
    book = await _seed_book(title="Defaults", owner_id=author.id)

    created_at = datetime(2026, 9, 15, 9, 0, 0)
    modified_at = datetime(2026, 9, 15, 9, 30, 0)

    created = await memos.create(
        Memo(
            book_id=book.id,
            user_id=author.id,
            body="Always mention the weather.",
            ordinal=7,
            created_at=created_at,
            modified_at=modified_at,
        )
    )
    # Snowflake PK populated on the created row.
    assert created.id is not None
    # The defaults, on the row handed back by create.
    assert created.active is True
    assert created.archived is False

    stored = await memos.get_by_id(created.id)

    assert stored is not None
    assert stored.id == created.id
    assert stored.book_id == book.id
    assert stored.user_id == author.id
    assert stored.body == "Always mention the weather."
    assert stored.ordinal == 7
    # The defaults survived the write.
    assert stored.active is True
    assert stored.archived is False
    assert stored.created_at == created_at
    assert stored.modified_at == modified_at


# DoD-2 (US-123.AC-3): get_by_id resolves nothing for an id that was never
# written — the round trip above is a real read, not a cache of the argument.
async def test_get_by_id_returns_nothing_for_unknown_id__DoD2(db: DbConfig):
    assert await memos.get_by_id(999000111222) is None


# ---------------------------------------------------------------------------
# DoD-3 — `""` is a value: an empty body is stored and returned as ""
# ---------------------------------------------------------------------------


# DoD-3 (UC-103 postcondition): a memo created with body="" — the normal state
# of a freshly created memo — is stored and returned as "", never coerced to
# None. The row itself is genuinely present.
async def test_empty_body_round_trips_as_empty_string__DoD3(db: DbConfig):
    author = await _seed_user("memo-empty-author")
    book = await _seed_book(title="Empty Memo", owner_id=author.id)

    created = await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="", ordinal=1)
    )
    assert created.body == ""
    assert created.body is not None

    stored = await memos.get_by_id(created.id)

    # The row exists...
    assert stored is not None
    # ...and its body is the empty string, not None.
    assert stored.body == ""
    assert stored.body is not None

    # It is a first-class member of the author's list, not an absence.
    listed = await memos.list_for_author(book.id, author.id)
    assert [row.id for row in listed] == [created.id]
    assert listed[0].body == ""


# ---------------------------------------------------------------------------
# DoD-4 — list_for_author never crosses an author or a book boundary
# ---------------------------------------------------------------------------


# DoD-4 (US-124.AC-1, US-124.AC-2): list_for_author returns only the rows for
# the (book, author) pair it was asked for. Another author's memos in the SAME
# book and the same author's memos in ANOTHER book are both absent, in both
# directions.
async def test_list_returns_only_the_requested_pair__DoD4(db: DbConfig):
    author_one = await _seed_user("memo-scope-a")
    author_two = await _seed_user("memo-scope-b")
    book_one = await _seed_book(title="Book One", owner_id=author_one.id)
    book_two = await _seed_book(title="Book Two", owner_id=author_one.id)

    await memos.create(
        Memo(book_id=book_one.id, user_id=author_one.id, body="mine here", ordinal=1)
    )
    await memos.create(
        Memo(book_id=book_one.id, user_id=author_two.id, body="theirs here", ordinal=1)
    )
    await memos.create(
        Memo(book_id=book_two.id, user_id=author_one.id, body="mine there", ordinal=1)
    )

    # Same book, this author — only this author's row.
    mine_here = await memos.list_for_author(book_one.id, author_one.id)
    assert [row.body for row in mine_here] == ["mine here"]

    # Same book, the other author — only theirs.
    theirs_here = await memos.list_for_author(book_one.id, author_two.id)
    assert [row.body for row in theirs_here] == ["theirs here"]

    # The other book, this author — only the row belonging to that book.
    mine_there = await memos.list_for_author(book_two.id, author_one.id)
    assert [row.body for row in mine_there] == ["mine there"]

    # A pair with nothing written is empty, not a fallback to somebody's rows.
    assert await memos.list_for_author(book_two.id, author_two.id) == []


# ---------------------------------------------------------------------------
# DoD-5 / DoD-6 — the include-archived flag, off by default and on by request
# ---------------------------------------------------------------------------


# DoD-5 (US-128.AC-1): with the include-archived flag left at its DEFAULT,
# archived rows are absent from the returned list — the working list is the
# non-archived set.
async def test_archived_rows_absent_by_default__DoD5(db: DbConfig):
    author = await _seed_user("memo-archived-default")
    book = await _seed_book(title="Archived Default", owner_id=author.id)

    await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="live one", ordinal=1)
    )
    await memos.create(
        Memo(
            book_id=book.id,
            user_id=author.id,
            body="put away",
            ordinal=2,
            archived=True,
        )
    )

    # The default call.
    defaulted = await memos.list_for_author(book.id, author.id)
    assert [row.body for row in defaulted] == ["live one"]

    # And the same thing said explicitly.
    explicit = await memos.list_for_author(book.id, author.id, include_archived=False)
    assert [row.body for row in explicit] == ["live one"]


# DoD-6 (US-128.AC-2): with the flag on, archived rows come back alongside the
# live ones, so the author's archived set is reachable at all.
async def test_archived_rows_returned_when_flag_on__DoD6(db: DbConfig):
    author = await _seed_user("memo-archived-on")
    book = await _seed_book(title="Archived Included", owner_id=author.id)

    await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="live one", ordinal=1)
    )
    await memos.create(
        Memo(
            book_id=book.id,
            user_id=author.id,
            body="put away",
            ordinal=2,
            archived=True,
        )
    )

    included = await memos.list_for_author(book.id, author.id, include_archived=True)

    assert [row.body for row in included] == ["live one", "put away"]
    # The archived row really is the archived one.
    archived_rows = [row for row in included if row.archived]
    assert [row.body for row in archived_rows] == ["put away"]


# ---------------------------------------------------------------------------
# DoD-7 — `active` is never a list filter
# ---------------------------------------------------------------------------


# DoD-7 (US-127.AC-1): a switched-off memo is listed exactly like a switched-on
# one. list_for_author filters on `archived` only and never on `active`, so an
# inactive, non-archived row is present in the default list with its flag
# intact; the active rule is a derived reading applied by the caller.
async def test_inactive_rows_are_listed_like_active_ones__DoD7(db: DbConfig):
    author = await _seed_user("memo-inactive-author")
    book = await _seed_book(title="Inactive Listed", owner_id=author.id)

    await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="switched on", ordinal=1)
    )
    await memos.create(
        Memo(
            book_id=book.id,
            user_id=author.id,
            body="switched off",
            ordinal=2,
            active=False,
        )
    )

    listed = await memos.list_for_author(book.id, author.id)

    assert [row.body for row in listed] == ["switched on", "switched off"]
    by_body = {row.body: row for row in listed}
    assert by_body["switched on"].active is True
    assert by_body["switched off"].active is False
    # Neither is archived — `active` did not leak into the archive axis.
    assert by_body["switched off"].archived is False


# ---------------------------------------------------------------------------
# DoD-8 — ascending ordinal order
# ---------------------------------------------------------------------------


# DoD-8 (US-131.AC-2): the list comes back in ASCENDING `ordinal` order,
# regardless of the order in which the rows were inserted.
async def test_list_is_ordered_by_ascending_ordinal__DoD8(db: DbConfig):
    author = await _seed_user("memo-order-author")
    book = await _seed_book(title="Ordered", owner_id=author.id)

    # Inserted out of order on purpose.
    await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="third", ordinal=3)
    )
    await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="first", ordinal=1)
    )
    await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="fourth", ordinal=4)
    )
    await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="second", ordinal=2)
    )

    listed = await memos.list_for_author(book.id, author.id)

    assert [row.ordinal for row in listed] == [1, 2, 3, 4]
    assert [row.body for row in listed] == ["first", "second", "third", "fourth"]


# DoD-8 (US-131.AC-2): ordinals may carry gaps — archiving leaves a gap and
# never renumbers — and the ascending order still holds across them, with the
# include-archived listing ordered the same way.
async def test_list_is_ordered_across_ordinal_gaps__DoD8(db: DbConfig):
    author = await _seed_user("memo-gap-author")
    book = await _seed_book(title="Gapped", owner_id=author.id)

    await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="ten", ordinal=10)
    )
    await memos.create(
        Memo(
            book_id=book.id,
            user_id=author.id,
            body="five archived",
            ordinal=5,
            archived=True,
        )
    )
    await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="two", ordinal=2)
    )

    live = await memos.list_for_author(book.id, author.id)
    assert [row.ordinal for row in live] == [2, 10]

    everything = await memos.list_for_author(book.id, author.id, include_archived=True)
    assert [row.ordinal for row in everything] == [2, 5, 10]


# ---------------------------------------------------------------------------
# DoD-9 — update persists the body, returns stored state, sets no timestamps
# ---------------------------------------------------------------------------


# DoD-9 (US-125.AC-1): update(row) persists the changed body — a subsequent
# get_by_id returns the new value — and the row update RETURNS agrees with that
# stored state on every column (rather than merely echoing the in-memory
# argument). update() does not add a row either.
async def test_update_persists_body_and_returns_stored_state__DoD9(db: DbConfig):
    author = await _seed_user("memo-update-author")
    book = await _seed_book(title="Updatable", owner_id=author.id)

    created = await memos.create(
        Memo(
            book_id=book.id,
            user_id=author.id,
            body="original body",
            ordinal=1,
            created_at=datetime(2026, 9, 15, 8, 0, 0),
            modified_at=datetime(2026, 9, 15, 8, 0, 0),
        )
    )

    created.body = "revised body"
    returned = await memos.update(created)

    stored = await memos.get_by_id(created.id)
    assert stored is not None
    # The change is persisted.
    assert stored.body == "revised body"

    # The returned row reflects stored state on every column.
    assert returned.id == stored.id
    assert returned.book_id == stored.book_id
    assert returned.user_id == stored.user_id
    assert returned.body == stored.body
    assert returned.ordinal == stored.ordinal
    assert returned.active == stored.active
    assert returned.archived == stored.archived
    assert returned.created_at == stored.created_at
    assert returned.modified_at == stored.modified_at

    # No second row was created.
    assert [row.id for row in await memos.list_for_author(book.id, author.id)] == [
        created.id
    ]


# DoD-9 (US-125.AC-1): the db/ layer sets NO timestamps of its own — timestamps
# are the service's policy. A row whose timestamps the caller never set stays
# null across create and update, and a row whose timestamps the caller DID set
# keeps exactly those values when only the body is changed.
async def test_db_layer_sets_no_timestamps_of_its_own__DoD9(db: DbConfig):
    author = await _seed_user("memo-stamp-author")
    book = await _seed_book(title="Timestamps", owner_id=author.id)

    # A row the caller never stamped stays null through create...
    untouched = await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="unstamped", ordinal=1)
    )
    assert untouched.created_at is None
    assert untouched.modified_at is None

    # ...and through update.
    untouched.body = "still unstamped"
    returned = await memos.update(untouched)
    assert returned.created_at is None
    assert returned.modified_at is None

    stored = await memos.get_by_id(untouched.id)
    assert stored is not None
    assert stored.body == "still unstamped"
    assert stored.created_at is None
    assert stored.modified_at is None

    # A row the caller DID stamp keeps exactly the caller's values when only
    # the body changes — the layer neither refreshes nor invents a stamp.
    created_at = datetime(2026, 9, 15, 7, 0, 0)
    modified_at = datetime(2026, 9, 15, 7, 15, 0)
    stamped = await memos.create(
        Memo(
            book_id=book.id,
            user_id=author.id,
            body="stamped",
            ordinal=2,
            created_at=created_at,
            modified_at=modified_at,
        )
    )
    stamped.body = "stamped and edited"
    await memos.update(stamped)

    after = await memos.get_by_id(stamped.id)
    assert after is not None
    assert after.body == "stamped and edited"
    assert after.created_at == created_at
    assert after.modified_at == modified_at


# ---------------------------------------------------------------------------
# DoD-10 — the two flags are independent axes
# ---------------------------------------------------------------------------


# DoD-10 (US-127.AC-4, US-128.AC-2): update persists the two flags
# INDEPENDENTLY. Switching `active` off never rewrites `archived`, and
# archiving never rewrites `active` — which is exactly what lets a restored
# memo remember whether it was switched on or off before it was archived.
async def test_update_persists_the_two_flags_independently__DoD10(db: DbConfig):
    author = await _seed_user("memo-flags-author")
    book = await _seed_book(title="Two Axes", owner_id=author.id)

    row = await memos.create(
        Memo(book_id=book.id, user_id=author.id, body="two axes", ordinal=1)
    )
    assert row.active is True
    assert row.archived is False

    # Writing `active` alone leaves `archived` untouched.
    row.active = False
    await memos.update(row)
    after_deactivate = await memos.get_by_id(row.id)
    assert after_deactivate is not None
    assert after_deactivate.active is False
    assert after_deactivate.archived is False

    # Writing `archived` alone leaves the (off) `active` flag untouched — the
    # switched-off state is remembered across the archive.
    after_deactivate.archived = True
    await memos.update(after_deactivate)
    after_archive = await memos.get_by_id(row.id)
    assert after_archive is not None
    assert after_archive.archived is True
    assert after_archive.active is False

    # Restoring (archived back to False) still leaves `active` alone.
    after_archive.archived = False
    await memos.update(after_archive)
    after_restore = await memos.get_by_id(row.id)
    assert after_restore is not None
    assert after_restore.archived is False
    assert after_restore.active is False

    # And switching back on leaves `archived` alone.
    after_restore.active = True
    await memos.update(after_restore)
    after_activate = await memos.get_by_id(row.id)
    assert after_activate is not None
    assert after_activate.active is True
    assert after_activate.archived is False


# DoD-10 (US-127.AC-4, US-128.AC-2): every one of the four flag combinations is
# a legal stored state — there is no invalid combination to refuse, because
# context membership is a derived reading rule and not a constraint.
async def test_all_four_flag_combinations_are_storable__DoD10(db: DbConfig):
    author = await _seed_user("memo-combos-author")
    book = await _seed_book(title="Four Combos", owner_id=author.id)

    combinations = [
        (True, False),
        (False, False),
        (True, True),
        (False, True),
    ]

    for index, (active, archived) in enumerate(combinations, start=1):
        created = await memos.create(
            Memo(
                book_id=book.id,
                user_id=author.id,
                body=f"combo {index}",
                ordinal=index,
                active=active,
                archived=archived,
            )
        )
        stored = await memos.get_by_id(created.id)
        assert stored is not None
        assert stored.active is active
        assert stored.archived is archived


# ---------------------------------------------------------------------------
# DoD-11 — there is no delete function, structurally
# ---------------------------------------------------------------------------


# DoD-11 (US-128.AC-3): archive-not-delete is structural at the data layer.
# db/memos.py exposes NO delete function under any of the names a caller might
# reach for, and its public surface is exactly the four designed functions.
def test_module_exposes_no_delete_function__DoD11():
    for forbidden in ("delete", "delete_by_id", "remove", "destroy", "purge"):
        assert not hasattr(memos, forbidden), (
            f"db/memos.py must expose no delete path, but defines {forbidden!r}"
        )

    public = {
        name
        for name in vars(memos)
        if not name.startswith("_") and callable(getattr(memos, name))
    }
    # No public callable defined in this module deletes anything.
    module_functions = {
        name
        for name in public
        if getattr(getattr(memos, name), "__module__", None) == memos.__name__
    }
    assert module_functions == {"create", "get_by_id", "list_for_author", "update"}
