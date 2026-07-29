"""Tests for the per-author prompt DTOs and service (feature 021, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002):
    class UpdateBookAuthorPromptRequest(BaseModel)
        system_prompt: str                    (required; "" is valid input)
    class BookAuthorPromptResponse(BaseModel)
        book_id: str, system_prompt: str, modified_at: datetime | None
        (NO user_id field)
                            in app.models.schemas.book_author_prompts
    class BookAuthorPromptErrorReason(str, enum.Enum) { not_a_member }
    class BookAuthorPromptError(Exception)  __init__(reason, message="")
        -> .reason / .message
    def _require_member(access: authz.BookAccess) -> None
    def _to_prompt_response(book_id: int, row: BookAuthorPrompt | None)
        -> BookAuthorPromptResponse
    async def get_prompt(access) -> BookAuthorPromptResponse
    async def upsert_prompt(access, req: UpdateBookAuthorPromptRequest)
        -> BookAuthorPromptResponse
                            in app.services.book_author_prompts
plus the frozen `authz.BookAccess` and step 001's `app.db.book_author_prompts`.

Expected values come from the step spec (002.author-prompt-service.md DoD +
002.context.md + feature context.md — "The wire contract", decisions 4 and 6),
never from implementation internals:
    - DoD-1: each author of the SAME book reads back only their own text;
    - DoD-2: no row is not an error — empty prompt, null timestamp;
    - DoD-3: the write entry point creates the row (stamping BOTH timestamps)
      and a subsequent read returns it;
    - DoD-4: the write entry point updates IN PLACE — one row for the pair,
      `created_at` preserved, `modified_at` advanced (the db/ layer sets no
      timestamps, so this split is the service's own — 002.context.md ->
      "Timestamps belong to this layer");
    - DoD-5: "" is accepted and read back as an empty prompt — and stays
      DISTINGUISHABLE from "no row at all", which shows only in `modified_at`
      (a real timestamp vs null — 002.context.md -> "Empty string is a value");
    - DoD-6: a `reader` and a caller with NO relationship are refused with the
      service's single typed reason, on BOTH entry points;
    - DoD-7: a co-author is NOT refused on the write path — this deliberately
      reverses US-108.AC-2 (context.md -> "Product situation");
    - DoD-8: the response DTO exposes no user identifier, and neither entry
      point takes a user id — the id comes only from `access.user_id`;
    - DoD-9: writing one author's prompt leaves every other author's row in
      that book, and the same author's row in other books, untouched.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. Supporting users/books are seeded
through the sibling db/ modules, and a `BookAccess` is constructed directly (a
frozen dataclass), as tests/services/test_chats.py does. No route, no HTTP
client, no JWT at this layer — those are step 003's.
"""

import inspect
from datetime import datetime

import pytest
from sqlmodel import select

from app.db import book_author_prompts as prompts_db
from app.db import books, users
from app.db.engine import DbConfig, get_standalone_session
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_author_prompt import BookAuthorPrompt
from app.models.schemas.book_author_prompts import (
    BookAuthorPromptResponse,
    UpdateBookAuthorPromptRequest,
)
from app.models.user import User, UserRole
from app.services import book_author_prompts as prompt_service
from app.services.authz import AccessRole, BookAccess
from app.services.book_author_prompts import (
    BookAuthorPromptError,
    BookAuthorPromptErrorReason,
)


# ---------------------------------------------------------------------------
# Seeding helpers (services-test style: rows through the db layer, access
# context constructed directly).
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


async def _count_rows(book_id: int, user_id: int) -> int:
    """How many stored rows exist for the (book, user) pair."""
    session = await get_standalone_session()
    async with session:
        result = await session.execute(
            select(BookAuthorPrompt).where(
                BookAuthorPrompt.book_id == book_id,
                BookAuthorPrompt.user_id == user_id,
            )
        )
        return len(result.scalars().all())


async def _backdate(
    book_id: int, user_id: int, *, created_at: datetime, modified_at: datetime
) -> None:
    """Push a stored row's timestamps into the past through the db/ layer.

    Lets DoD-4 assert "created_at preserved / modified_at advanced" against
    fixed, unambiguous reference values rather than against two wall-clock
    stamps taken microseconds apart.
    """
    row = await prompts_db.get_by_book_and_user(book_id, user_id)
    assert row is not None
    row.created_at = created_at
    row.modified_at = modified_at
    await prompts_db.update(row)


# ---------------------------------------------------------------------------
# DoD-1 — two authors of one book each read back only their own prompt
# ---------------------------------------------------------------------------


# DoD-1: an owner and a co-author of the SAME book each store a prompt and each
# read back their own text — the service scopes every read to access.user_id, so
# neither ever sees the other's.
async def test_owner_and_co_author_each_read_their_own_prompt__DoD1(db: DbConfig):
    owner = await _seed_user("owner-one")
    co_author = await _seed_user("co-author-one")
    book = await _seed_book(title="Shared Novel", owner_id=owner.id)

    owner_access = _access(book.id, owner.id, role=AccessRole.owner)
    co_author_access = _access(book.id, co_author.id, role=AccessRole.co_author)

    await prompt_service.upsert_prompt(
        owner_access, UpdateBookAuthorPromptRequest(system_prompt="the owner's voice")
    )
    await prompt_service.upsert_prompt(
        co_author_access,
        UpdateBookAuthorPromptRequest(system_prompt="the co-author's voice"),
    )

    owner_read = await prompt_service.get_prompt(owner_access)
    co_author_read = await prompt_service.get_prompt(co_author_access)

    assert owner_read.system_prompt == "the owner's voice"
    assert co_author_read.system_prompt == "the co-author's voice"

    # Same book for both — the id is the book's, stringified (the wire contract).
    assert owner_read.book_id == str(book.id)
    assert co_author_read.book_id == str(book.id)


# ---------------------------------------------------------------------------
# DoD-2 — no row is the normal starting state, not an error
# ---------------------------------------------------------------------------


# DoD-2: a member who has never written a prompt reads an empty prompt and a
# null timestamp; nothing is raised, and no row is invented by the read.
async def test_read_with_no_row_is_empty_prompt_and_null_timestamp__DoD2(db: DbConfig):
    author = await _seed_user("never-wrote")
    book = await _seed_book(title="Unwritten", owner_id=author.id)

    resp = await prompt_service.get_prompt(_access(book.id, author.id))

    assert resp.book_id == str(book.id)
    assert resp.system_prompt == ""
    assert resp.modified_at is None

    # Reading does not create storage.
    assert await prompts_db.get_by_book_and_user(book.id, author.id) is None


# ---------------------------------------------------------------------------
# DoD-3 — the write entry point creates a row when none exists
# ---------------------------------------------------------------------------


# DoD-3: with no row for the pair, the write entry point creates one — the
# response carries the stored text and a real timestamp, both timestamps are
# stamped on the stored row (the db/ layer sets none), and a subsequent read
# returns the same prompt.
async def test_write_creates_row_and_read_returns_it__DoD3(db: DbConfig):
    author = await _seed_user("first-writer")
    book = await _seed_book(title="Fresh Book", owner_id=author.id)
    access = _access(book.id, author.id)

    assert await prompts_db.get_by_book_and_user(book.id, author.id) is None

    written = await prompt_service.upsert_prompt(
        access, UpdateBookAuthorPromptRequest(system_prompt="terse and concrete")
    )

    assert written.book_id == str(book.id)
    assert written.system_prompt == "terse and concrete"
    assert written.modified_at is not None

    # The row really exists, with BOTH timestamps set by this layer on create.
    stored = await prompts_db.get_by_book_and_user(book.id, author.id)
    assert stored is not None
    assert stored.system_prompt == "terse and concrete"
    assert stored.created_at is not None
    assert stored.modified_at is not None

    # A subsequent read returns it.
    read_back = await prompt_service.get_prompt(access)
    assert read_back.system_prompt == "terse and concrete"
    assert read_back.modified_at == written.modified_at


# ---------------------------------------------------------------------------
# DoD-4 — the write entry point updates in place
# ---------------------------------------------------------------------------


# DoD-4: writing again updates the existing row in place — the pair still has
# exactly one row (same surrogate id), `created_at` is preserved unchanged, and
# `modified_at` advances past its previous value.
async def test_second_write_updates_in_place_preserving_created_at__DoD4(db: DbConfig):
    author = await _seed_user("rewriter")
    book = await _seed_book(title="Revised Book", owner_id=author.id)
    access = _access(book.id, author.id)

    await prompt_service.upsert_prompt(
        access, UpdateBookAuthorPromptRequest(system_prompt="first draft")
    )
    original = await prompts_db.get_by_book_and_user(book.id, author.id)
    assert original is not None
    original_id = original.id

    # Anchor both timestamps in the past so "preserved" and "advanced" are
    # unambiguous.
    anchor_created = datetime(2026, 7, 1, 9, 0, 0)
    anchor_modified = datetime(2026, 7, 1, 9, 0, 0)
    await _backdate(
        book.id, author.id, created_at=anchor_created, modified_at=anchor_modified
    )

    updated = await prompt_service.upsert_prompt(
        access, UpdateBookAuthorPromptRequest(system_prompt="second draft")
    )

    assert updated.system_prompt == "second draft"

    stored = await prompts_db.get_by_book_and_user(book.id, author.id)
    assert stored is not None
    # Exactly one row for the pair, and it is the same row as before.
    assert await _count_rows(book.id, author.id) == 1
    assert stored.id == original_id
    # The creation timestamp is preserved...
    assert stored.created_at == anchor_created
    # ...and the modified timestamp advances.
    assert stored.modified_at is not None
    assert stored.modified_at > anchor_modified
    assert updated.modified_at == stored.modified_at


# ---------------------------------------------------------------------------
# DoD-5 — an empty string is an accepted value; no delete verb is needed
# ---------------------------------------------------------------------------


# DoD-5: writing "" is accepted and read back as an empty prompt — clearing a
# prompt needs no delete verb, so the row survives the clear.
async def test_writing_empty_string_is_accepted_and_read_back_empty__DoD5(
    db: DbConfig,
):
    author = await _seed_user("clearer")
    book = await _seed_book(title="Clearable Book", owner_id=author.id)
    access = _access(book.id, author.id)

    await prompt_service.upsert_prompt(
        access, UpdateBookAuthorPromptRequest(system_prompt="a prompt to clear")
    )
    cleared = await prompt_service.upsert_prompt(
        access, UpdateBookAuthorPromptRequest(system_prompt="")
    )

    assert cleared.system_prompt == ""

    read_back = await prompt_service.get_prompt(access)
    assert read_back.system_prompt == ""

    # The row is still stored, holding "" rather than being deleted.
    stored = await prompts_db.get_by_book_and_user(book.id, author.id)
    assert stored is not None
    assert stored.system_prompt == ""


# DoD-5: "a row holding an empty string" and "no row at all" both render as an
# empty prompt, and are NOT normalised into each other — the difference shows in
# `modified_at`: a real timestamp for the cleared row, null for the absent one.
async def test_cleared_prompt_stays_distinct_from_no_row__DoD5(db: DbConfig):
    cleared_author = await _seed_user("has-cleared")
    absent_author = await _seed_user("never-written")
    book = await _seed_book(title="Two States", owner_id=cleared_author.id)

    cleared_access = _access(book.id, cleared_author.id, role=AccessRole.owner)
    absent_access = _access(book.id, absent_author.id, role=AccessRole.co_author)

    await prompt_service.upsert_prompt(
        cleared_access, UpdateBookAuthorPromptRequest(system_prompt="something")
    )
    await prompt_service.upsert_prompt(
        cleared_access, UpdateBookAuthorPromptRequest(system_prompt="")
    )

    cleared = await prompt_service.get_prompt(cleared_access)
    absent = await prompt_service.get_prompt(absent_access)

    # Both read as "no prompt"...
    assert cleared.system_prompt == ""
    assert absent.system_prompt == ""
    # ...and are still distinguishable, only by the timestamp.
    assert cleared.modified_at is not None
    assert absent.modified_at is None


# ---------------------------------------------------------------------------
# DoD-6 — non-members are refused, with the one typed reason, on both verbs
# ---------------------------------------------------------------------------


# DoD-6: a `reader` is refused on the READ entry point with the service's typed
# reason.
async def test_reader_is_refused_on_read__DoD6(db: DbConfig):
    owner = await _seed_user("book-owner-r1")
    reader = await _seed_user("a-reader-r1")
    book = await _seed_book(title="Public Read", owner_id=owner.id)

    with pytest.raises(BookAuthorPromptError) as exc_info:
        await prompt_service.get_prompt(
            _access(book.id, reader.id, role=AccessRole.reader)
        )

    assert exc_info.value.reason is BookAuthorPromptErrorReason.not_a_member


# DoD-6: a `reader` is refused on the WRITE entry point with the same typed
# reason, and the refusal happens before anything is stored.
async def test_reader_is_refused_on_write__DoD6(db: DbConfig):
    owner = await _seed_user("book-owner-r2")
    reader = await _seed_user("a-reader-r2")
    book = await _seed_book(title="Public Write", owner_id=owner.id)

    with pytest.raises(BookAuthorPromptError) as exc_info:
        await prompt_service.upsert_prompt(
            _access(book.id, reader.id, role=AccessRole.reader),
            UpdateBookAuthorPromptRequest(system_prompt="not mine to set"),
        )

    assert exc_info.value.reason is BookAuthorPromptErrorReason.not_a_member
    assert await prompts_db.get_by_book_and_user(book.id, reader.id) is None


# DoD-6: a caller with NO relationship to the book is refused the same way, on
# both entry points.
async def test_non_member_is_refused_on_both_entry_points__DoD6(db: DbConfig):
    owner = await _seed_user("book-owner-n")
    stranger = await _seed_user("a-stranger")
    book = await _seed_book(title="Stranger's Reach", owner_id=owner.id)
    access = _access(book.id, stranger.id, role=AccessRole.none)

    with pytest.raises(BookAuthorPromptError) as read_exc:
        await prompt_service.get_prompt(access)
    assert read_exc.value.reason is BookAuthorPromptErrorReason.not_a_member

    with pytest.raises(BookAuthorPromptError) as write_exc:
        await prompt_service.upsert_prompt(
            access, UpdateBookAuthorPromptRequest(system_prompt="trespass")
        )
    assert write_exc.value.reason is BookAuthorPromptErrorReason.not_a_member

    assert await prompts_db.get_by_book_and_user(book.id, stranger.id) is None


# DoD-6: the service owns exactly ONE typed reason — every other refusal on this
# path is produced upstream by the `book_access` dependency and never reaches
# here (002.author-prompt-service.md -> Interface intent).
def test_service_has_exactly_one_typed_reason__DoD6():
    assert list(BookAuthorPromptErrorReason) == [
        BookAuthorPromptErrorReason.not_a_member
    ]


# ---------------------------------------------------------------------------
# DoD-7 — a co-author is NOT refused on the write path
# ---------------------------------------------------------------------------


# DoD-7: a co-author writing their own prompt is accepted, not refused. This
# deliberately REVERSES US-108.AC-2 (which refused a co-author editing the book
# prompt): there is no book-wide prompt any more, and each author owns theirs.
async def test_co_author_is_not_refused_on_write__DoD7(db: DbConfig):
    owner = await _seed_user("owner-seven")
    co_author = await _seed_user("co-author-seven")
    book = await _seed_book(title="Collaborative Book", owner_id=owner.id)
    access = _access(book.id, co_author.id, role=AccessRole.co_author)

    resp = await prompt_service.upsert_prompt(
        access, UpdateBookAuthorPromptRequest(system_prompt="my own instructions")
    )

    # Not refused: the write went through and is readable back.
    assert resp.system_prompt == "my own instructions"
    assert resp.modified_at is not None
    assert (await prompt_service.get_prompt(access)).system_prompt == (
        "my own instructions"
    )

    # And the guard admits a co-author outright.
    prompt_service._require_member(access)


# ---------------------------------------------------------------------------
# DoD-8 — the DTO offers no handle on another author's prompt
# ---------------------------------------------------------------------------


# DoD-8: the response DTO carries exactly the three wire-contract fields and no
# user identifier — echoing one would invite the belief that the endpoint can
# serve another user's prompt (context.md -> "The wire contract").
def test_response_dto_exposes_no_user_identifier__DoD8():
    field_names = set(BookAuthorPromptResponse.model_fields)

    assert field_names == {"book_id", "system_prompt", "modified_at"}
    assert not [name for name in field_names if "user" in name.lower()]


# DoD-8: no field a caller could vary reaches another author's prompt — the
# request DTO carries only the prompt text, and neither service entry point
# takes a user id at all: it comes only from `access.user_id`.
def test_no_caller_supplied_field_selects_the_author__DoD8():
    assert set(UpdateBookAuthorPromptRequest.model_fields) == {"system_prompt"}

    read_params = list(inspect.signature(prompt_service.get_prompt).parameters)
    write_params = list(inspect.signature(prompt_service.upsert_prompt).parameters)

    assert read_params == ["access"]
    assert write_params == ["access", "req"]


# ---------------------------------------------------------------------------
# DoD-9 — a write touches exactly one (book, author) row
# ---------------------------------------------------------------------------


# DoD-9: writing one author's prompt leaves every OTHER author's row in that
# book, and the SAME author's row in other books, untouched — text and
# timestamps both.
async def test_write_leaves_other_rows_untouched__DoD9(db: DbConfig):
    author = await _seed_user("writer-nine")
    other_author = await _seed_user("bystander-nine")
    book_one = await _seed_book(title="Book One", owner_id=author.id)
    book_two = await _seed_book(title="Book Two", owner_id=author.id)

    target_access = _access(book_one.id, author.id, role=AccessRole.owner)
    other_author_access = _access(
        book_one.id, other_author.id, role=AccessRole.co_author
    )
    other_book_access = _access(book_two.id, author.id, role=AccessRole.owner)

    await prompt_service.upsert_prompt(
        target_access, UpdateBookAuthorPromptRequest(system_prompt="mine, book one")
    )
    await prompt_service.upsert_prompt(
        other_author_access,
        UpdateBookAuthorPromptRequest(system_prompt="theirs, book one"),
    )
    await prompt_service.upsert_prompt(
        other_book_access, UpdateBookAuthorPromptRequest(system_prompt="mine, book two")
    )

    before_other_author = await prompts_db.get_by_book_and_user(
        book_one.id, other_author.id
    )
    before_other_book = await prompts_db.get_by_book_and_user(book_two.id, author.id)
    assert before_other_author is not None and before_other_book is not None

    # The write under test.
    await prompt_service.upsert_prompt(
        target_access, UpdateBookAuthorPromptRequest(system_prompt="mine, rewritten")
    )

    after_other_author = await prompts_db.get_by_book_and_user(
        book_one.id, other_author.id
    )
    after_other_book = await prompts_db.get_by_book_and_user(book_two.id, author.id)
    assert after_other_author is not None and after_other_book is not None

    # The other author's row in the same book is untouched.
    assert after_other_author.id == before_other_author.id
    assert after_other_author.system_prompt == "theirs, book one"
    assert after_other_author.created_at == before_other_author.created_at
    assert after_other_author.modified_at == before_other_author.modified_at

    # The same author's row in the other book is untouched.
    assert after_other_book.id == before_other_book.id
    assert after_other_book.system_prompt == "mine, book two"
    assert after_other_book.created_at == before_other_book.created_at
    assert after_other_book.modified_at == before_other_book.modified_at

    # And each still reads back as its own through the service.
    assert (
        await prompt_service.get_prompt(other_author_access)
    ).system_prompt == "theirs, book one"
    assert (
        await prompt_service.get_prompt(other_book_access)
    ).system_prompt == "mine, book two"
    assert (
        await prompt_service.get_prompt(target_access)
    ).system_prompt == "mine, rewritten"
