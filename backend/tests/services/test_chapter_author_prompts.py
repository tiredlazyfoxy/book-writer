"""Tests for the per-author CHAPTER prompt service (feature 014, step 004).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 004), in
`app.models.schemas.chapter_author_prompts`:
    class UpdateChapterAuthorPromptRequest(BaseModel)
        system_prompt: str                      (required; "" is valid input)
    class ChapterAuthorPromptResponse(BaseModel)
        chapter_id: str, system_prompt: str, modified_at: datetime | None
        (NO user_id field)
and in `app.services.chapter_author_prompts`:
    class ChapterAuthorPromptErrorReason(str, enum.Enum) { not_a_member, not_found }
    class ChapterAuthorPromptError(Exception)  __init__(reason, message="")
        -> .reason / .message
    def _require_member(access) -> None
    async def _resolve_chapter(access, chapter_id: str) -> Chapter
    def _to_prompt_response(chapter_id: int, row) -> ChapterAuthorPromptResponse
    async def get_prompt(access, chapter_id: str) -> ChapterAuthorPromptResponse
    async def upsert_prompt(access, chapter_id: str, req) -> ChapterAuthorPromptResponse
plus the frozen `authz.BookAccess` / `AccessRole` and step 001's
`app.db.chapter_author_prompts`.

Expected values come from the SPEC ONLY -- 004.chapter-prompt-service-routes.md
(Interface intent + Definition of done), 004.context.md and the feature
context.md ("Chapter-prompt DTOs", decision D1) -- never from implementation
internals:
    - DoD-4: each member of the SAME book holds their own prompt on the SAME
      chapter; neither ever reads the other's, owner included;
    - DoD-5: the same author's prompts on two chapters of one book are
      independent -- writing one leaves the other untouched;
    - DoD-6: a second write UPDATES rather than duplicating -- one row for the
      pair, `created_at` preserved, `modified_at` advanced (the db/ layer stamps
      nothing, so the split is this service's own -- 004.context.md ->
      "Timestamps belong to this layer");
    - DoD-7: "" is accepted and read back as an empty prompt, and stays
      DISTINGUISHABLE from "no row at all" -- the difference shows only in
      `modified_at` (a real timestamp vs null), and neither state is normalised
      into the other (004.context.md -> "Empty string is a value, not an
      absence");
    - DoD-8: a prompt is readable and writable on a chapter in `open`,
      `closing` and `closed` state, not only on a `planned` one -- the chapter
      state machine does not reach this table (004.context.md).
    - DoD-2 is asserted here as the service-layer half of "no row is not an
      error" that DoD-7's distinguishability rests on; its HTTP half (200, not
      404) lives in tests/routes/test_chapter_author_prompts.py.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. Users / books / chapters are seeded
through the sibling db/ modules and `BookAccess` is constructed directly (a
frozen dataclass), so there is no route, no client, no JWT and no network in
this module. Chapters are forced into non-`planned` states straight through
`app.db.chapters` -- this feature ships no state transition (004.context.md).
"""

import datetime

import pytest
from sqlmodel import select

from app.db import books, users
from app.db import chapter_author_prompts as prompts_db
from app.db import chapters as chapters_db
from app.db.engine import DbConfig, get_standalone_session
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chapter import Chapter, ChapterState
from app.models.chapter_author_prompt import ChapterAuthorPrompt
from app.models.schemas.chapter_author_prompts import (
    ChapterAuthorPromptResponse,
    UpdateChapterAuthorPromptRequest,
)
from app.models.user import User, UserRole
from app.services import chapter_author_prompts as prompt_service
from app.services.authz import AccessRole, BookAccess


# ---------------------------------------------------------------------------
# Seeding helpers (rows through the db layer, access context built directly).
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(*, title: str, owner_id: int) -> Book:
    return await books.create(
        Book(
            title=title,
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt="",
            active_notes="",
        )
    )


async def _seed_chapter(
    book_id: int,
    *,
    ordinal: int = 1,
    title: str = "A Chapter",
    sketch: str = "a sketch",
    state: ChapterState = ChapterState.planned,
) -> Chapter:
    """A Chapter inserted straight through db/chapters.py, bypassing services."""
    return await chapters_db.create(
        Chapter(
            book_id=book_id,
            ordinal=ordinal,
            title=title,
            state=state,
            sketch=sketch,
            text="",
        )
    )


def _access(
    book_id: int,
    user_id: int,
    *,
    role: AccessRole = AccessRole.owner,
) -> BookAccess:
    """The access context the `book_access` dependency would have resolved."""
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=role,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=CollaborationMode.free,
    )


async def _count_rows(chapter_id: int, user_id: int) -> int:
    """How many stored rows exist for the (chapter, user) pair."""
    session = await get_standalone_session()
    async with session:
        result = await session.execute(
            select(ChapterAuthorPrompt).where(
                ChapterAuthorPrompt.chapter_id == chapter_id,
                ChapterAuthorPrompt.user_id == user_id,
            )
        )
        return len(result.scalars().all())


async def _backdate(
    chapter_id: int,
    user_id: int,
    *,
    created_at: datetime.datetime,
    modified_at: datetime.datetime,
) -> None:
    """Push a stored row's timestamps into the past through the db/ layer.

    Lets DoD-6 assert "created_at preserved / modified_at advanced" against
    fixed, unambiguous reference values rather than against two wall-clock
    stamps taken microseconds apart.
    """
    row = await prompts_db.get_by_chapter_and_user(chapter_id, user_id)
    assert row is not None
    row.created_at = created_at
    row.modified_at = modified_at
    await prompts_db.update(row)


def _naive(stamp: datetime.datetime) -> datetime.datetime:
    """Compare timestamps by instant, whatever tz representation they carry."""
    if stamp.tzinfo is None:
        return stamp
    return stamp.astimezone(datetime.timezone.utc).replace(tzinfo=None)


NON_PLANNED_STATES = [
    pytest.param(ChapterState.open, id="open"),
    pytest.param(ChapterState.closing, id="closing"),
    pytest.param(ChapterState.closed, id="closed"),
]


# ---------------------------------------------------------------------------
# DoD-2 (service half) — no row is the normal starting state, not an error
# ---------------------------------------------------------------------------


# DoD-2: a member who has never written a prompt for this chapter reads an empty
# prompt and a null timestamp; nothing is raised and the read creates no row.
async def test_read_with_no_row_is_empty_and_null__DoD2(db: DbConfig):
    author = await _seed_user("never-wrote")
    book = await _seed_book(title="Unwritten", owner_id=author.id)
    chapter = await _seed_chapter(book.id)

    resp = await prompt_service.get_prompt(
        _access(book.id, author.id), str(chapter.id)
    )

    assert isinstance(resp, ChapterAuthorPromptResponse)
    assert resp.chapter_id == str(chapter.id)
    assert resp.system_prompt == ""
    assert resp.modified_at is None

    # Reading does not create storage.
    assert await prompts_db.get_by_chapter_and_user(chapter.id, author.id) is None


# ---------------------------------------------------------------------------
# DoD-4 — two members, one chapter, two independent prompts
# ---------------------------------------------------------------------------


# DoD-4: an owner and a co-author of the same book each write a prompt on the
# SAME chapter; each read returns their own text and never the other's -- the
# user id comes only from `access.user_id`, so nobody (owner included) can reach
# another author's row.
async def test_two_members_read_only_their_own_prompt__DoD4(db: DbConfig):
    owner = await _seed_user("owner-four")
    co_author = await _seed_user("co-author-four")
    book = await _seed_book(title="Shared Novel", owner_id=owner.id)
    chapter = await _seed_chapter(book.id)

    owner_access = _access(book.id, owner.id, role=AccessRole.owner)
    co_access = _access(book.id, co_author.id, role=AccessRole.co_author)

    await prompt_service.upsert_prompt(
        owner_access,
        str(chapter.id),
        UpdateChapterAuthorPromptRequest(system_prompt="the owner's voice"),
    )
    await prompt_service.upsert_prompt(
        co_access,
        str(chapter.id),
        UpdateChapterAuthorPromptRequest(system_prompt="the co-author's voice"),
    )

    owner_read = await prompt_service.get_prompt(owner_access, str(chapter.id))
    co_read = await prompt_service.get_prompt(co_access, str(chapter.id))

    assert owner_read.system_prompt == "the owner's voice"
    assert co_read.system_prompt == "the co-author's voice"

    # Same chapter for both -- the id is the chapter's, stringified.
    assert owner_read.chapter_id == str(chapter.id) == co_read.chapter_id


# DoD-4: the owner rewriting their own prompt leaves the co-author's row on the
# same chapter untouched -- text and both timestamps.
async def test_write_leaves_the_other_members_row_untouched__DoD4(db: DbConfig):
    owner = await _seed_user("owner-four-b")
    co_author = await _seed_user("co-author-four-b")
    book = await _seed_book(title="Untouched", owner_id=owner.id)
    chapter = await _seed_chapter(book.id)

    owner_access = _access(book.id, owner.id, role=AccessRole.owner)
    co_access = _access(book.id, co_author.id, role=AccessRole.co_author)

    await prompt_service.upsert_prompt(
        owner_access,
        str(chapter.id),
        UpdateChapterAuthorPromptRequest(system_prompt="owner first"),
    )
    await prompt_service.upsert_prompt(
        co_access,
        str(chapter.id),
        UpdateChapterAuthorPromptRequest(system_prompt="co-author's own"),
    )

    before = await prompts_db.get_by_chapter_and_user(chapter.id, co_author.id)
    assert before is not None

    # The write under test.
    await prompt_service.upsert_prompt(
        owner_access,
        str(chapter.id),
        UpdateChapterAuthorPromptRequest(system_prompt="owner rewritten"),
    )

    after = await prompts_db.get_by_chapter_and_user(chapter.id, co_author.id)
    assert after is not None
    assert after.id == before.id
    assert after.system_prompt == "co-author's own"
    assert after.created_at == before.created_at
    assert after.modified_at == before.modified_at

    # And each still reads back as its own through the service.
    assert (
        await prompt_service.get_prompt(co_access, str(chapter.id))
    ).system_prompt == "co-author's own"
    assert (
        await prompt_service.get_prompt(owner_access, str(chapter.id))
    ).system_prompt == "owner rewritten"


# ---------------------------------------------------------------------------
# DoD-5 — one author, two chapters, independent prompts
# ---------------------------------------------------------------------------


# DoD-5: the same author holds independent prompts on two chapters of one book;
# writing one leaves the other's text and timestamps untouched, and each reads
# back its own value.
async def test_prompts_on_two_chapters_are_independent__DoD5(db: DbConfig):
    author = await _seed_user("two-chapter-author")
    book = await _seed_book(title="Two Chapters", owner_id=author.id)
    first = await _seed_chapter(book.id, ordinal=1, title="One")
    second = await _seed_chapter(book.id, ordinal=2, title="Two")
    access = _access(book.id, author.id)

    await prompt_service.upsert_prompt(
        access,
        str(first.id),
        UpdateChapterAuthorPromptRequest(system_prompt="voice for chapter one"),
    )
    await prompt_service.upsert_prompt(
        access,
        str(second.id),
        UpdateChapterAuthorPromptRequest(system_prompt="voice for chapter two"),
    )

    before_second = await prompts_db.get_by_chapter_and_user(second.id, author.id)
    assert before_second is not None

    # Rewrite the FIRST chapter's prompt only.
    await prompt_service.upsert_prompt(
        access,
        str(first.id),
        UpdateChapterAuthorPromptRequest(system_prompt="chapter one, rewritten"),
    )

    after_second = await prompts_db.get_by_chapter_and_user(second.id, author.id)
    assert after_second is not None
    assert after_second.id == before_second.id
    assert after_second.system_prompt == "voice for chapter two"
    assert after_second.created_at == before_second.created_at
    assert after_second.modified_at == before_second.modified_at

    read_first = await prompt_service.get_prompt(access, str(first.id))
    read_second = await prompt_service.get_prompt(access, str(second.id))

    assert read_first.system_prompt == "chapter one, rewritten"
    assert read_second.system_prompt == "voice for chapter two"
    assert read_first.chapter_id == str(first.id)
    assert read_second.chapter_id == str(second.id)


# DoD-5: writing one chapter's prompt does not invent a row on the author's
# other chapter -- an unwritten chapter still reads as "no row".
async def test_writing_one_chapter_leaves_the_other_unwritten__DoD5(db: DbConfig):
    author = await _seed_user("one-of-two-author")
    book = await _seed_book(title="One Written", owner_id=author.id)
    written = await _seed_chapter(book.id, ordinal=1, title="Written")
    untouched = await _seed_chapter(book.id, ordinal=2, title="Untouched")
    access = _access(book.id, author.id)

    await prompt_service.upsert_prompt(
        access,
        str(written.id),
        UpdateChapterAuthorPromptRequest(system_prompt="only here"),
    )

    other = await prompt_service.get_prompt(access, str(untouched.id))
    assert other.system_prompt == ""
    assert other.modified_at is None
    assert await prompts_db.get_by_chapter_and_user(untouched.id, author.id) is None


# ---------------------------------------------------------------------------
# DoD-6 — a second write updates in place, with the timestamp split
# ---------------------------------------------------------------------------


# DoD-6: writing again updates the existing row -- the value changes, the pair
# still has exactly ONE row (the same surrogate id), `created_at` is preserved
# unchanged and `modified_at` advances past its previous value.
async def test_second_write_updates_and_keeps_one_row__DoD6(db: DbConfig):
    author = await _seed_user("rewriter-six")
    book = await _seed_book(title="Revised", owner_id=author.id)
    chapter = await _seed_chapter(book.id)
    access = _access(book.id, author.id)

    await prompt_service.upsert_prompt(
        access,
        str(chapter.id),
        UpdateChapterAuthorPromptRequest(system_prompt="first draft"),
    )
    original = await prompts_db.get_by_chapter_and_user(chapter.id, author.id)
    assert original is not None
    original_id = original.id

    # Anchor both timestamps in the past so "preserved" and "advanced" are
    # unambiguous.
    anchor = datetime.datetime(2026, 7, 1, 9, 0, 0)
    await _backdate(chapter.id, author.id, created_at=anchor, modified_at=anchor)

    updated = await prompt_service.upsert_prompt(
        access,
        str(chapter.id),
        UpdateChapterAuthorPromptRequest(system_prompt="second draft"),
    )
    assert updated.system_prompt == "second draft"
    assert updated.modified_at is not None

    stored = await prompts_db.get_by_chapter_and_user(chapter.id, author.id)
    assert stored is not None
    # Exactly one row for the pair, and it is the same row as before.
    assert await _count_rows(chapter.id, author.id) == 1
    assert stored.id == original_id
    assert stored.system_prompt == "second draft"
    # The creation timestamp is preserved...
    assert stored.created_at is not None
    assert _naive(stored.created_at) == anchor
    # ...and the modified timestamp advances.
    assert stored.modified_at is not None
    assert _naive(stored.modified_at) > anchor


# DoD-6: the FIRST write is a create and stamps BOTH timestamps -- the db/ layer
# stamps nothing, so the split is this service's (004.context.md).
async def test_first_write_stamps_both_timestamps__DoD6(db: DbConfig):
    author = await _seed_user("first-writer-six")
    book = await _seed_book(title="Fresh", owner_id=author.id)
    chapter = await _seed_chapter(book.id)
    access = _access(book.id, author.id)

    assert await prompts_db.get_by_chapter_and_user(chapter.id, author.id) is None

    written = await prompt_service.upsert_prompt(
        access,
        str(chapter.id),
        UpdateChapterAuthorPromptRequest(system_prompt="terse and concrete"),
    )
    assert written.system_prompt == "terse and concrete"
    assert written.modified_at is not None

    stored = await prompts_db.get_by_chapter_and_user(chapter.id, author.id)
    assert stored is not None
    assert stored.system_prompt == "terse and concrete"
    assert stored.created_at is not None
    assert stored.modified_at is not None
    assert await _count_rows(chapter.id, author.id) == 1


# ---------------------------------------------------------------------------
# DoD-7 — "" is a value; clearing needs no delete verb
# ---------------------------------------------------------------------------


# DoD-7: writing "" is accepted and read back as an empty prompt -- and the row
# survives the clear rather than being deleted.
async def test_empty_string_is_accepted_and_read_back_empty__DoD7(db: DbConfig):
    author = await _seed_user("clearer-seven")
    book = await _seed_book(title="Clearable", owner_id=author.id)
    chapter = await _seed_chapter(book.id)
    access = _access(book.id, author.id)

    await prompt_service.upsert_prompt(
        access,
        str(chapter.id),
        UpdateChapterAuthorPromptRequest(system_prompt="a prompt to clear"),
    )
    cleared = await prompt_service.upsert_prompt(
        access, str(chapter.id), UpdateChapterAuthorPromptRequest(system_prompt="")
    )

    assert cleared.system_prompt == ""

    read_back = await prompt_service.get_prompt(access, str(chapter.id))
    assert read_back.system_prompt == ""

    stored = await prompts_db.get_by_chapter_and_user(chapter.id, author.id)
    assert stored is not None
    assert stored.system_prompt == ""


# DoD-7: writing "" as the FIRST write is equally accepted -- a row is created
# holding "", not skipped.
async def test_empty_string_as_the_first_write_creates_a_row__DoD7(db: DbConfig):
    author = await _seed_user("empty-first-seven")
    book = await _seed_book(title="Empty First", owner_id=author.id)
    chapter = await _seed_chapter(book.id)
    access = _access(book.id, author.id)

    written = await prompt_service.upsert_prompt(
        access, str(chapter.id), UpdateChapterAuthorPromptRequest(system_prompt="")
    )
    assert written.system_prompt == ""
    assert written.modified_at is not None

    stored = await prompts_db.get_by_chapter_and_user(chapter.id, author.id)
    assert stored is not None
    assert stored.system_prompt == ""


# DoD-7: "a row holding an empty string" and "no row at all" both render as an
# empty prompt and are NOT normalised into each other -- the difference shows
# only in `modified_at` (a real timestamp for the cleared row, null for the
# absent one).
async def test_cleared_prompt_stays_distinct_from_no_row__DoD7(db: DbConfig):
    cleared_author = await _seed_user("has-cleared-seven")
    absent_author = await _seed_user("never-written-seven")
    book = await _seed_book(title="Two States", owner_id=cleared_author.id)
    chapter = await _seed_chapter(book.id)

    cleared_access = _access(book.id, cleared_author.id, role=AccessRole.owner)
    absent_access = _access(book.id, absent_author.id, role=AccessRole.co_author)

    await prompt_service.upsert_prompt(
        cleared_access,
        str(chapter.id),
        UpdateChapterAuthorPromptRequest(system_prompt="something"),
    )
    await prompt_service.upsert_prompt(
        cleared_access,
        str(chapter.id),
        UpdateChapterAuthorPromptRequest(system_prompt=""),
    )

    cleared = await prompt_service.get_prompt(cleared_access, str(chapter.id))
    absent = await prompt_service.get_prompt(absent_access, str(chapter.id))

    # Both read as "no prompt"...
    assert cleared.system_prompt == ""
    assert absent.system_prompt == ""
    # ...and are still distinguishable, only by the timestamp.
    assert cleared.modified_at is not None
    assert absent.modified_at is None


# ---------------------------------------------------------------------------
# DoD-8 — the chapter state machine does not reach this table
# ---------------------------------------------------------------------------


# DoD-8: a prompt is WRITABLE and READABLE on a chapter in `open` / `closing` /
# `closed` state, not only on a `planned` one -- an author's instruction to
# their own assistant is not chapter content, so step 002's not-planned refusal
# is deliberately absent here (004.context.md).
@pytest.mark.parametrize("state", NON_PLANNED_STATES)
async def test_prompt_works_on_a_non_planned_chapter__DoD8(
    db: DbConfig, state: ChapterState
):
    author = await _seed_user(f"state-author-{state.value}")
    book = await _seed_book(title=f"Book {state.value}", owner_id=author.id)
    chapter = await _seed_chapter(book.id, title=f"Chapter {state.value}", state=state)
    access = _access(book.id, author.id)

    # Readable before anything is written.
    initial = await prompt_service.get_prompt(access, str(chapter.id))
    assert initial.system_prompt == ""
    assert initial.modified_at is None

    # Writable.
    written = await prompt_service.upsert_prompt(
        access,
        str(chapter.id),
        UpdateChapterAuthorPromptRequest(system_prompt=f"voice while {state.value}"),
    )
    assert written.system_prompt == f"voice while {state.value}"
    assert written.chapter_id == str(chapter.id)

    # And readable back.
    read_back = await prompt_service.get_prompt(access, str(chapter.id))
    assert read_back.system_prompt == f"voice while {state.value}"
    assert read_back.modified_at is not None

    # The chapter's own state is untouched by the prompt write.
    stored_chapter = await chapters_db.get_by_id(chapter.id)
    assert stored_chapter is not None
    assert stored_chapter.state == state


# DoD-8: a co-author gets the same answer on a non-`planned` chapter -- the
# absence of a state check is not an owner privilege.
@pytest.mark.parametrize("state", NON_PLANNED_STATES)
async def test_co_author_prompt_works_on_a_non_planned_chapter__DoD8(
    db: DbConfig, state: ChapterState
):
    owner = await _seed_user(f"state-owner-{state.value}")
    co_author = await _seed_user(f"state-co-author-{state.value}")
    book = await _seed_book(title=f"Co Book {state.value}", owner_id=owner.id)
    chapter = await _seed_chapter(book.id, state=state)
    access = _access(book.id, co_author.id, role=AccessRole.co_author)

    written = await prompt_service.upsert_prompt(
        access,
        str(chapter.id),
        UpdateChapterAuthorPromptRequest(system_prompt="co-author's own voice"),
    )
    assert written.system_prompt == "co-author's own voice"

    read_back = await prompt_service.get_prompt(access, str(chapter.id))
    assert read_back.system_prompt == "co-author's own voice"
