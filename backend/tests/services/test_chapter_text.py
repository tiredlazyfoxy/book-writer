"""Tests for the chapter BODY DTOs, the two write capabilities and the read/save
service (feature 015, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001), in
`app.models.schemas.chapters`:
    class ChapterTextResponse(BaseModel)     chapter_id: str, state: ChapterState,
                                             text: str, version: int,
                                             modified_at: datetime | None
    class UpdateChapterTextRequest(BaseModel) text: str (no constraint),
                                              expected_version: int
in `app.services.authz`:
    Capability.set_chapter_state / Capability.write_chapter_text + `_CAPABILITY_MATRIX`
in `app.services.chapters`:
    ChapterErrorReason { ..., chapter_not_open, stale_version, book_archived,
        proposal_mode_refused }
    def _require_not_archived(access: BookAccess) -> None
    async def get_chapter_text(access, chapter_id: str) -> ChapterTextResponse
    async def save_chapter_text(access, chapter_id: str,
        request: UpdateChapterTextRequest) -> ChapterTextResponse
plus 014's frozen `ChapterError` and the frozen `authz.BookAccess` / `AccessRole` /
`BookAuthorizationError`.

Expected values come from the step spec (001.chapter-body-service.md -> Interface
intent + Definition of done, 001.context.md, and the feature context.md -> the wire
contract / D7 / D9 / D10 / D11), never from implementation internals:
    - a read returns the stored body, state, version and a STRING id, for the owner,
      for a co-author, and on an ARCHIVED book -- reads are never archive-gated
      (DoD-1, D10);
    - a co-author's save into an `open` chapter of a FREE-mode book becomes the body
      immediately and bumps `version` by exactly one (DoD-2, US-040.AC-1);
    - the ChapterChange written by that save carries the SAVING MEMBER as author
      (DoD-3, US-040.AC-2);
    - placement (D9): the new body STARTS WITH the loaded body -> `append`, null line
      bounds, change text = the appended remainder; otherwise -> `range`,
      `line_from` = 1, `line_to` = len(loaded.splitlines()), change text = the whole
      new body (DoD-4);
    - D9's three degenerate cases: loaded "" -> append carrying the whole body;
      cleared to "" -> range carrying ""; unchanged body -> append carrying "" and
      the version still bumps (DoD-5);
    - one ChapterChange (status applied, base_version = the SUBMITTED version,
      applied_by set) and one ChapterTextRevision (applied_change_id = that change,
      text_before = the body BEFORE the save) per successful save, read back through
      the db layer (DoD-6, D7);
    - a stale version is refused with the stale reason and writes NOTHING (DoD-7,
      US-041.AC-1, UC-039), after which a save carrying the CURRENT version -- of a
      body holding both members' text -- lands (DoD-8, US-041.AC-2, US-040.AC-4);
    - a save into `planned` / `closing` / `closed` is refused with the not-open reason
      and writes nothing (DoD-9, US-040.AC-3, US-038.AC-1);
    - a reader and a caller with no relationship are refused the save by the
      authorization error, while a reader still READS on a public book (DoD-10);
    - a co-author's save in a PROPOSAL-mode book is refused with the proposal reason
      naming FEAT-010, while the owner's lands (DoD-11, D11);
    - every save and the shared transition guard are refused with the archived reason
      on an `archived` book, writing nothing (DoD-12, D10);
    - another book's chapter is NOT FOUND on both entry points (DoD-13, 014's D4);
    - the two new Capability members carry exactly the matrix's role sets and no
      pre-existing capability's role set changed (DoD-14).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. User / Book / Chapter rows are seeded
through the sibling db/ modules and `BookAccess` is constructed directly (a frozen
dataclass), so there is no route, no client, no JWT and no network anywhere in this
module. Chapters are put into a given state by writing the state straight through
`db/chapters.py` -- this step ships no transition (001.context.md).
"""

import pytest

from app.db import books, chapter_changes, chapter_text_revisions, chapters, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chapter import Chapter, ChapterState
from app.models.chapter_change import ChangeStatus, ChapterChange, PlacementKind
from app.models.chapter_text_revision import ChapterTextRevision
from app.models.schemas.chapters import ChapterTextResponse, UpdateChapterTextRequest
from app.models.user import User, UserRole
from app.services import authz
from app.services import chapters as chapters_service
from app.services.authz import AccessRole, BookAccess, BookAuthorizationError, Capability
from app.services.chapters import ChapterError, ChapterErrorReason

# The exact ChapterTextResponse field set, from context.md -> "The wire contract".
TEXT_WIRE_FIELDS = {"chapter_id", "state", "text", "version", "modified_at"}


# ---------------------------------------------------------------------------
# Seeding helpers (db-layer rows + a directly-built access context).
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(
    owner_id: int,
    *,
    title: str = "A Book",
    collaboration_mode: CollaborationMode = CollaborationMode.free,
    visibility: Visibility = Visibility.private,
    state: BookState = BookState.active,
) -> Book:
    return await books.create(
        Book(
            title=title,
            description="d",
            owner_id=owner_id,
            collaboration_mode=collaboration_mode,
            visibility=visibility,
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
    state: ChapterState = ChapterState.open,
    text: str = "",
    version: int = 1,
) -> Chapter:
    """A Chapter inserted straight through db/chapters.py, bypassing the service.

    The chapter's STATE is written directly: this step ships no transition, and a
    body spec must not depend on one (001.context.md).
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


async def _changes(chapter_id: int) -> list[ChapterChange]:
    return list(await chapter_changes.list_by_chapter(chapter_id))


async def _revisions(chapter_id: int) -> list[ChapterTextRevision]:
    return list(await chapter_text_revisions.list_by_chapter(chapter_id))


# ---------------------------------------------------------------------------
# DoD-1 — get_chapter_text: body, state, version, string id; never archive-gated
# ---------------------------------------------------------------------------


# DoD-1: ChapterTextResponse carries exactly the wire contract's fields.
def test_text_response_exposes_only_the_wire_fields__DoD1():
    assert set(ChapterTextResponse.model_fields) == TEXT_WIRE_FIELDS


# DoD-1: get_chapter_text returns the chapter's stored body, its state, its version
# and its id as a STRING, for the owner and for a co-author alike.
async def test_get_chapter_text_returns_the_stored_body__DoD1(db: DbConfig):
    owner = await _seed_user("read-owner")
    helper = await _seed_user("read-co-author")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text="The stored body.\nLine two.", version=4
    )

    owner_view = await chapters_service.get_chapter_text(
        _access(book.id, owner.id), str(chapter.id)
    )
    assert isinstance(owner_view, ChapterTextResponse)
    assert owner_view.chapter_id == str(chapter.id)
    assert isinstance(owner_view.chapter_id, str)
    assert owner_view.state == ChapterState.open
    assert owner_view.text == "The stored body.\nLine two."
    assert owner_view.version == 4

    co_view = await chapters_service.get_chapter_text(
        _access(book.id, helper.id, role=AccessRole.co_author), str(chapter.id)
    )
    assert co_view.chapter_id == str(chapter.id)
    assert co_view.text == "The stored body.\nLine two."
    assert co_view.version == 4
    assert co_view.state == ChapterState.open


# DoD-1 (D10): a read on an ARCHIVED book is NOT refused -- the archive gate covers
# writes only, which is what makes "archive preserves content" mean something.
async def test_get_chapter_text_works_on_an_archived_book__DoD1(db: DbConfig):
    owner = await _seed_user("read-archived-owner")
    helper = await _seed_user("read-archived-co-author")
    book = await _seed_book(owner.id, state=BookState.archived)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.closed, text="Preserved body.", version=9
    )

    owner_view = await chapters_service.get_chapter_text(
        _access(book.id, owner.id, book_state=BookState.archived), str(chapter.id)
    )
    assert owner_view.text == "Preserved body."
    assert owner_view.version == 9
    assert owner_view.state == ChapterState.closed

    co_view = await chapters_service.get_chapter_text(
        _access(
            book.id,
            helper.id,
            role=AccessRole.co_author,
            book_state=BookState.archived,
        ),
        str(chapter.id),
    )
    assert co_view.text == "Preserved body."
    assert co_view.version == 9


# DoD-1: an empty body reads back as "" -- a legitimate value, not a missing one.
async def test_get_chapter_text_returns_an_empty_body__DoD1(db: DbConfig):
    owner = await _seed_user("read-empty-owner")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open, text="")

    view = await chapters_service.get_chapter_text(
        _access(book.id, owner.id), str(chapter.id)
    )
    assert view.text == ""


# ---------------------------------------------------------------------------
# DoD-2 — a co-author's save lands immediately and bumps version by exactly one
# ---------------------------------------------------------------------------


# DoD-2 (US-040.AC-1): a co-author saving a new body into an `open` chapter of a
# FREE-mode book makes it the chapter's body immediately, and the chapter's version
# is incremented by exactly one.
async def test_co_author_save_lands_and_bumps_version_by_one__DoD2_US040_AC1(
    db: DbConfig,
):
    owner = await _seed_user("save-owner")
    helper = await _seed_user("save-co-author")
    book = await _seed_book(owner.id, collaboration_mode=CollaborationMode.free)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text="The opening beat.", version=1
    )

    result = await chapters_service.save_chapter_text(
        _access(book.id, helper.id, role=AccessRole.co_author),
        str(chapter.id),
        UpdateChapterTextRequest(
            text="The opening beat.\n\nAnd what the co-author added.",
            expected_version=1,
        ),
    )

    assert result.text == "The opening beat.\n\nAnd what the co-author added."
    assert result.version == 2
    assert result.chapter_id == str(chapter.id)
    assert result.state == ChapterState.open
    assert result.modified_at is not None

    stored = await _stored(chapter.id)
    assert stored.text == "The opening beat.\n\nAnd what the co-author added."
    assert stored.version == 2
    assert stored.state == ChapterState.open


# DoD-2 (US-040.AC-1): the owner's save lands the same way, and two sequential saves
# bump the version once each.
async def test_sequential_saves_bump_the_version_once_each__DoD2_US040_AC1(
    db: DbConfig,
):
    owner = await _seed_user("save-owner-seq")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open, text="v0", version=1)
    access = _access(book.id, owner.id)

    first = await chapters_service.save_chapter_text(
        access, str(chapter.id), UpdateChapterTextRequest(text="v0v1", expected_version=1)
    )
    assert first.version == 2

    second = await chapters_service.save_chapter_text(
        access,
        str(chapter.id),
        UpdateChapterTextRequest(text="v0v1v2", expected_version=2),
    )
    assert second.version == 3
    assert second.text == "v0v1v2"

    stored = await _stored(chapter.id)
    assert stored.text == "v0v1v2"
    assert stored.version == 3


# ---------------------------------------------------------------------------
# DoD-3 — attribution: the ChapterChange's author is the saving member
# ---------------------------------------------------------------------------


# DoD-3 (US-040.AC-2): the ChapterChange written by a co-author's save carries THAT
# member as its author -- not the book's owner.
async def test_change_author_is_the_saving_member__DoD3_US040_AC2(db: DbConfig):
    owner = await _seed_user("attrib-owner")
    helper = await _seed_user("attrib-co-author")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open, text="", version=1)

    await chapters_service.save_chapter_text(
        _access(book.id, helper.id, role=AccessRole.co_author),
        str(chapter.id),
        UpdateChapterTextRequest(text="Written by the co-author.", expected_version=1),
    )

    written = await _changes(chapter.id)
    assert len(written) == 1
    assert written[0].author_id == helper.id
    assert written[0].author_id != owner.id


# DoD-3 (US-040.AC-2): two members saving in turn leave one change each, attributed
# to the member who saved it.
async def test_each_save_is_attributed_to_its_own_author__DoD3_US040_AC2(db: DbConfig):
    owner = await _seed_user("attrib-owner-two")
    helper = await _seed_user("attrib-co-author-two")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open, text="", version=1)

    await chapters_service.save_chapter_text(
        _access(book.id, owner.id),
        str(chapter.id),
        UpdateChapterTextRequest(text="Owner's paragraph.", expected_version=1),
    )
    await chapters_service.save_chapter_text(
        _access(book.id, helper.id, role=AccessRole.co_author),
        str(chapter.id),
        UpdateChapterTextRequest(
            text="Owner's paragraph.\nCo-author's paragraph.", expected_version=2
        ),
    )

    written = await _changes(chapter.id)
    assert len(written) == 2
    by_author = {c.author_id: c for c in written}
    assert set(by_author) == {owner.id, helper.id}
    assert by_author[owner.id].base_version == 1
    assert by_author[helper.id].base_version == 2


# ---------------------------------------------------------------------------
# DoD-4 — D9's placement rule: append vs range
# ---------------------------------------------------------------------------


# DoD-4 (D9): a new body that STARTS WITH the loaded body writes an `append` change
# with NULL line bounds whose text is the appended remainder only.
async def test_growing_body_writes_an_append_change__DoD4(db: DbConfig):
    owner = await _seed_user("placement-append-owner")
    book = await _seed_book(owner.id)
    loaded = "First line.\nSecond line."
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text=loaded, version=1
    )

    await chapters_service.save_chapter_text(
        _access(book.id, owner.id),
        str(chapter.id),
        UpdateChapterTextRequest(text=loaded + "\nThird line.", expected_version=1),
    )

    written = await _changes(chapter.id)
    assert len(written) == 1
    change = written[0]
    assert change.placement_kind is PlacementKind.append
    assert change.line_from is None
    assert change.line_to is None
    assert change.text == "\nThird line."


# DoD-4 (D9): a new body that does NOT start with the loaded body writes a `range`
# change with line_from 1, line_to = the LOADED body's line count, and the WHOLE new
# body as its text.
async def test_rewritten_body_writes_a_range_change__DoD4(db: DbConfig):
    owner = await _seed_user("placement-range-owner")
    book = await _seed_book(owner.id)
    loaded = "First line.\nSecond line."  # two lines
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text=loaded, version=1
    )

    await chapters_service.save_chapter_text(
        _access(book.id, owner.id),
        str(chapter.id),
        UpdateChapterTextRequest(text="Rewritten entirely.", expected_version=1),
    )

    written = await _changes(chapter.id)
    assert len(written) == 1
    change = written[0]
    assert change.placement_kind is PlacementKind.range
    assert change.line_from == 1
    assert change.line_to == 2
    assert change.text == "Rewritten entirely."


# DoD-4 (D9): line_to counts with splitlines() -- a loaded body ENDING IN A NEWLINE
# reports no phantom trailing line (001.context.md -> "Line counting").
async def test_range_line_count_ignores_a_trailing_newline__DoD4(db: DbConfig):
    owner = await _seed_user("placement-newline-owner")
    book = await _seed_book(owner.id)
    loaded = "Alpha\nBeta\n"  # two lines, trailing newline
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text=loaded, version=1
    )

    await chapters_service.save_chapter_text(
        _access(book.id, owner.id),
        str(chapter.id),
        UpdateChapterTextRequest(text="Gamma\nDelta", expected_version=1),
    )

    written = await _changes(chapter.id)
    assert len(written) == 1
    assert written[0].placement_kind is PlacementKind.range
    assert written[0].line_from == 1
    assert written[0].line_to == 2
    assert written[0].text == "Gamma\nDelta"


# DoD-4 (D9): a prefix-shortening save (the new body is a PREFIX of the loaded one,
# not the other way round) does not start with the loaded body -> `range`.
async def test_shortened_body_writes_a_range_change__DoD4(db: DbConfig):
    owner = await _seed_user("placement-shorten-owner")
    book = await _seed_book(owner.id)
    loaded = "Kept part.\nCut part.\nAlso cut."  # three lines
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text=loaded, version=1
    )

    await chapters_service.save_chapter_text(
        _access(book.id, owner.id),
        str(chapter.id),
        UpdateChapterTextRequest(text="Kept part.", expected_version=1),
    )

    written = await _changes(chapter.id)
    assert len(written) == 1
    assert written[0].placement_kind is PlacementKind.range
    assert written[0].line_from == 1
    assert written[0].line_to == 3
    assert written[0].text == "Kept part."


# ---------------------------------------------------------------------------
# DoD-5 — D9's three degenerate cases
# ---------------------------------------------------------------------------


# DoD-5 (D9): the request DTO puts NO constraint on the body -- "" is a valid value
# and there is no force flag.
def test_update_request_accepts_an_empty_body__DoD5():
    assert set(UpdateChapterTextRequest.model_fields) == {"text", "expected_version"}
    request = UpdateChapterTextRequest(text="", expected_version=1)
    assert request.text == ""
    assert request.expected_version == 1


# DoD-5 (D9, case 1): a save into an EMPTY body is an `append` carrying the whole new
# body -- every string starts with "".
async def test_first_save_into_an_empty_body_is_an_append__DoD5(db: DbConfig):
    owner = await _seed_user("degenerate-empty-owner")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open, text="", version=1)

    await chapters_service.save_chapter_text(
        _access(book.id, owner.id),
        str(chapter.id),
        UpdateChapterTextRequest(text="The whole first draft.", expected_version=1),
    )

    written = await _changes(chapter.id)
    assert len(written) == 1
    assert written[0].placement_kind is PlacementKind.append
    assert written[0].line_from is None
    assert written[0].line_to is None
    assert written[0].text == "The whole first draft."


# DoD-5 (D9, case 2): CLEARING a non-empty body to "" is a `range` with line_from 1,
# line_to = the loaded body's line count, carrying "".
async def test_clearing_a_body_is_a_range_carrying_empty_text__DoD5(db: DbConfig):
    owner = await _seed_user("degenerate-clear-owner")
    book = await _seed_book(owner.id)
    loaded = "One\nTwo\nThree"  # three lines
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text=loaded, version=1
    )

    result = await chapters_service.save_chapter_text(
        _access(book.id, owner.id),
        str(chapter.id),
        UpdateChapterTextRequest(text="", expected_version=1),
    )

    assert result.text == ""
    assert result.version == 2

    written = await _changes(chapter.id)
    assert len(written) == 1
    assert written[0].placement_kind is PlacementKind.range
    assert written[0].line_from == 1
    assert written[0].line_to == 3
    assert written[0].text == ""

    stored = await _stored(chapter.id)
    assert stored.text == ""


# DoD-5 (D9, case 3): RE-SAVING an unchanged body is an `append` carrying "" and it
# STILL bumps the version -- no "unchanged" short-circuit.
async def test_resaving_an_unchanged_body_appends_nothing_and_bumps__DoD5(db: DbConfig):
    owner = await _seed_user("degenerate-unchanged-owner")
    book = await _seed_book(owner.id)
    loaded = "Exactly the same body."
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text=loaded, version=1
    )

    result = await chapters_service.save_chapter_text(
        _access(book.id, owner.id),
        str(chapter.id),
        UpdateChapterTextRequest(text=loaded, expected_version=1),
    )

    assert result.text == loaded
    assert result.version == 2

    written = await _changes(chapter.id)
    assert len(written) == 1
    assert written[0].placement_kind is PlacementKind.append
    assert written[0].line_from is None
    assert written[0].line_to is None
    assert written[0].text == ""

    revisions = await _revisions(chapter.id)
    assert len(revisions) == 1
    assert revisions[0].text_before == loaded

    stored = await _stored(chapter.id)
    assert stored.text == loaded
    assert stored.version == 2


# ---------------------------------------------------------------------------
# DoD-6 — exactly one change + one revision per save, and they read back (D7)
# ---------------------------------------------------------------------------


# DoD-6 (D7): a successful save writes exactly ONE ChapterChange -- status applied,
# base_version = the SUBMITTED version, applied_by set, applied_at / created_at
# stamped -- and exactly ONE ChapterTextRevision whose applied_change_id names that
# change and whose text_before is the body as it stood BEFORE the save.
async def test_one_change_and_one_revision_per_save__DoD6(db: DbConfig):
    owner = await _seed_user("history-owner")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text="The body before the save.", version=4
    )

    await chapters_service.save_chapter_text(
        _access(book.id, owner.id),
        str(chapter.id),
        UpdateChapterTextRequest(
            text="The body before the save. Plus a new sentence.", expected_version=4
        ),
    )

    written = await _changes(chapter.id)
    assert len(written) == 1
    change = written[0]
    assert change.status is ChangeStatus.applied
    assert change.base_version == 4
    assert change.applied_by == owner.id
    assert change.author_id == owner.id
    assert change.applied_at is not None
    assert change.created_at is not None
    assert change.chapter_id == chapter.id

    revisions = await _revisions(chapter.id)
    assert len(revisions) == 1
    revision = revisions[0]
    assert revision.applied_change_id == change.id
    assert revision.text_before == "The body before the save."
    assert revision.applied_by == owner.id
    assert revision.applied_at is not None
    assert revision.chapter_id == chapter.id

    stored = await _stored(chapter.id)
    assert stored.text == "The body before the save. Plus a new sentence."
    assert stored.version == 5


# DoD-6 (D7): two saves leave two changes and two revisions, and each revision's
# text_before is the body as it stood before ITS save -- the history chain reads back
# in order.
async def test_history_chain_reads_back_over_two_saves__DoD6(db: DbConfig):
    owner = await _seed_user("history-owner-chain")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id, state=ChapterState.open, text="A", version=1)
    access = _access(book.id, owner.id)

    await chapters_service.save_chapter_text(
        access, str(chapter.id), UpdateChapterTextRequest(text="AB", expected_version=1)
    )
    await chapters_service.save_chapter_text(
        access, str(chapter.id), UpdateChapterTextRequest(text="ABC", expected_version=2)
    )

    written = await _changes(chapter.id)
    revisions = await _revisions(chapter.id)
    assert len(written) == 2
    assert len(revisions) == 2

    assert {c.base_version for c in written} == {1, 2}
    change_ids = {c.id for c in written}
    assert {r.applied_change_id for r in revisions} == change_ids
    assert {r.text_before for r in revisions} == {"A", "AB"}
    assert all(c.status is ChangeStatus.applied for c in written)


# ---------------------------------------------------------------------------
# DoD-7 — a stale version is refused and writes NOTHING
# ---------------------------------------------------------------------------


# DoD-7 (US-041.AC-1, UC-039): a save carrying a version that is not the chapter's
# current version is refused with the stale reason, and nothing is written -- the
# body, the version, and the change and revision counts are unchanged.
async def test_stale_save_is_refused_and_writes_nothing__DoD7_US041_AC1(db: DbConfig):
    owner = await _seed_user("stale-owner")
    helper = await _seed_user("stale-co-author")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text="Shared body.", version=1
    )

    # B's save moves the body to version 2.
    await chapters_service.save_chapter_text(
        _access(book.id, helper.id, role=AccessRole.co_author),
        str(chapter.id),
        UpdateChapterTextRequest(
            text="Shared body. B's paragraph.", expected_version=1
        ),
    )
    assert len(await _changes(chapter.id)) == 1
    assert len(await _revisions(chapter.id)) == 1

    # A composed against version 1 and is now stale.
    with pytest.raises(ChapterError) as exc:
        await chapters_service.save_chapter_text(
            _access(book.id, owner.id),
            str(chapter.id),
            UpdateChapterTextRequest(
                text="Shared body. A's paragraph.", expected_version=1
            ),
        )
    assert exc.value.reason == ChapterErrorReason.stale_version

    stored = await _stored(chapter.id)
    assert stored.text == "Shared body. B's paragraph."
    assert stored.version == 2
    assert len(await _changes(chapter.id)) == 1
    assert len(await _revisions(chapter.id)) == 1


# DoD-7 (US-041.AC-1): a version AHEAD of the chapter's current one is equally stale
# -- the rule is equality, not "not older".
async def test_a_version_ahead_is_also_stale__DoD7_US041_AC1(db: DbConfig):
    owner = await _seed_user("stale-ahead-owner")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text="Untouched.", version=3
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.save_chapter_text(
            _access(book.id, owner.id),
            str(chapter.id),
            UpdateChapterTextRequest(text="Should not land.", expected_version=4),
        )
    assert exc.value.reason == ChapterErrorReason.stale_version

    stored = await _stored(chapter.id)
    assert stored.text == "Untouched."
    assert stored.version == 3
    assert await _changes(chapter.id) == []
    assert await _revisions(chapter.id) == []


# ---------------------------------------------------------------------------
# DoD-8 — the reconciliation mechanism: re-issue against the CURRENT version
# ---------------------------------------------------------------------------


# DoD-8 (US-041.AC-2, US-040.AC-4): after the refusal, a save of a body containing
# BOTH members' text, carrying the CURRENT version, succeeds and becomes the
# chapter's body. The merging is the author's; the system guarantees the refusal,
# and that a re-issue against the current version lands.
async def test_reissued_merged_save_lands__DoD8_US041_AC2(db: DbConfig):
    owner = await _seed_user("merge-owner")
    helper = await _seed_user("merge-co-author")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text="Base.", version=1
    )
    owner_access = _access(book.id, owner.id)

    await chapters_service.save_chapter_text(
        _access(book.id, helper.id, role=AccessRole.co_author),
        str(chapter.id),
        UpdateChapterTextRequest(text="Base. B's block.", expected_version=1),
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.save_chapter_text(
            owner_access,
            str(chapter.id),
            UpdateChapterTextRequest(text="Base. A's block.", expected_version=1),
        )
    assert exc.value.reason == ChapterErrorReason.stale_version

    merged = await chapters_service.save_chapter_text(
        owner_access,
        str(chapter.id),
        UpdateChapterTextRequest(
            text="Base. B's block. A's block.", expected_version=2
        ),
    )

    assert merged.text == "Base. B's block. A's block."
    assert merged.version == 3

    stored = await _stored(chapter.id)
    assert "B's block." in stored.text
    assert "A's block." in stored.text
    assert stored.text == "Base. B's block. A's block."
    assert stored.version == 3


# ---------------------------------------------------------------------------
# DoD-9 — a save into a non-`open` chapter is refused and writes nothing
# ---------------------------------------------------------------------------


# DoD-9 (US-040.AC-3, US-038.AC-1): a save into a chapter whose state is `planned`,
# `closing` or `closed` is refused with the not-open reason and writes nothing.
@pytest.mark.parametrize(
    "state", [ChapterState.planned, ChapterState.closing, ChapterState.closed]
)
async def test_save_into_a_non_open_chapter_is_refused__DoD9_US040_AC3(
    db: DbConfig, state: ChapterState
):
    owner = await _seed_user(f"not-open-owner-{state.value}")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(
        book.id, state=state, text="The frozen body.", version=2
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.save_chapter_text(
            _access(book.id, owner.id),
            str(chapter.id),
            UpdateChapterTextRequest(text="Should not land.", expected_version=2),
        )
    assert exc.value.reason == ChapterErrorReason.chapter_not_open

    stored = await _stored(chapter.id)
    assert stored.text == "The frozen body."
    assert stored.version == 2
    assert stored.state == state
    assert await _changes(chapter.id) == []
    assert await _revisions(chapter.id) == []


# DoD-9 (US-040.AC-3): a co-author is refused a non-`open` chapter the same way --
# the refusal is the chapter's state, not the caller's role.
async def test_co_author_save_into_a_closed_chapter_is_refused__DoD9_US040_AC3(
    db: DbConfig,
):
    owner = await _seed_user("not-open-owner-co")
    helper = await _seed_user("not-open-co-author")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.closed, text="Done.", version=7
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.save_chapter_text(
            _access(book.id, helper.id, role=AccessRole.co_author),
            str(chapter.id),
            UpdateChapterTextRequest(text="Reopened by stealth.", expected_version=7),
        )
    assert exc.value.reason == ChapterErrorReason.chapter_not_open

    stored = await _stored(chapter.id)
    assert stored.text == "Done."
    assert stored.version == 7


# ---------------------------------------------------------------------------
# DoD-10 — a reader / a non-member may not save; a reader may still read
# ---------------------------------------------------------------------------


# DoD-10: a reader and a caller with no relationship are refused save_chapter_text by
# the authorization error, and nothing is written.
@pytest.mark.parametrize("role", [AccessRole.reader, AccessRole.none])
async def test_reader_and_non_member_may_not_save__DoD10(db: DbConfig, role: AccessRole):
    owner = await _seed_user(f"save-refused-owner-{role.value}")
    outsider = await _seed_user(f"save-refused-caller-{role.value}")
    book = await _seed_book(owner.id, visibility=Visibility.public)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text="Members only.", version=1
    )

    with pytest.raises(BookAuthorizationError):
        await chapters_service.save_chapter_text(
            _access(
                book.id, outsider.id, role=role, visibility=Visibility.public
            ),
            str(chapter.id),
            UpdateChapterTextRequest(text="Vandalism.", expected_version=1),
        )

    stored = await _stored(chapter.id)
    assert stored.text == "Members only."
    assert stored.version == 1
    assert await _changes(chapter.id) == []
    assert await _revisions(chapter.id) == []


# DoD-10: a reader may still READ a chapter's body on a public book -- the write
# capability is what they lack, not the read one.
async def test_reader_may_read_the_body_on_a_public_book__DoD10(db: DbConfig):
    owner = await _seed_user("public-read-owner")
    lurker = await _seed_user("public-read-reader")
    book = await _seed_book(owner.id, visibility=Visibility.public)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text="Readable body.", version=2
    )

    view = await chapters_service.get_chapter_text(
        _access(
            book.id, lurker.id, role=AccessRole.reader, visibility=Visibility.public
        ),
        str(chapter.id),
    )

    assert view.text == "Readable body."
    assert view.version == 2
    assert view.chapter_id == str(chapter.id)


# ---------------------------------------------------------------------------
# DoD-11 — proposal mode refuses a co-author's body write; the owner is unaffected
# ---------------------------------------------------------------------------


# DoD-11 (D11): a CO-AUTHOR saving into a PROPOSAL-mode book is refused with the
# proposal reason -- whose message names FEAT-010 as unbuilt -- and nothing is
# written.
async def test_co_author_save_in_proposal_mode_is_refused__DoD11(db: DbConfig):
    owner = await _seed_user("proposal-owner")
    helper = await _seed_user("proposal-co-author")
    book = await _seed_book(owner.id, collaboration_mode=CollaborationMode.proposal)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text="Owner's body.", version=1
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.save_chapter_text(
            _access(
                book.id,
                helper.id,
                role=AccessRole.co_author,
                collaboration_mode=CollaborationMode.proposal,
            ),
            str(chapter.id),
            UpdateChapterTextRequest(
                text="Owner's body. A proposal.", expected_version=1
            ),
        )
    assert exc.value.reason == ChapterErrorReason.proposal_mode_refused
    assert "FEAT-010" in exc.value.message

    stored = await _stored(chapter.id)
    assert stored.text == "Owner's body."
    assert stored.version == 1
    assert await _changes(chapter.id) == []
    assert await _revisions(chapter.id) == []


# DoD-11 (D11): the OWNER saving into the same proposal-mode book succeeds -- the
# mode gate exempts the owner.
async def test_owner_save_in_proposal_mode_succeeds__DoD11(db: DbConfig):
    owner = await _seed_user("proposal-owner-writes")
    book = await _seed_book(owner.id, collaboration_mode=CollaborationMode.proposal)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text="Owner's body.", version=1
    )

    result = await chapters_service.save_chapter_text(
        _access(
            book.id, owner.id, collaboration_mode=CollaborationMode.proposal
        ),
        str(chapter.id),
        UpdateChapterTextRequest(
            text="Owner's body. And more.", expected_version=1
        ),
    )

    assert result.text == "Owner's body. And more."
    assert result.version == 2

    stored = await _stored(chapter.id)
    assert stored.text == "Owner's body. And more."
    assert stored.version == 2
    assert len(await _changes(chapter.id)) == 1
    assert len(await _revisions(chapter.id)) == 1


# ---------------------------------------------------------------------------
# DoD-12 — an archived book refuses every write (D10)
# ---------------------------------------------------------------------------


# DoD-12 (D10): a save on a book whose state is `archived` is refused with the
# archived reason -- for the owner and for a co-author alike -- and nothing is
# written.
@pytest.mark.parametrize("role", [AccessRole.owner, AccessRole.co_author])
async def test_save_on_an_archived_book_is_refused__DoD12(
    db: DbConfig, role: AccessRole
):
    owner = await _seed_user(f"archived-owner-{role.value}")
    helper = await _seed_user(f"archived-caller-{role.value}")
    book = await _seed_book(owner.id, state=BookState.archived)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.open, text="Preserved.", version=1
    )
    caller = owner if role is AccessRole.owner else helper

    with pytest.raises(ChapterError) as exc:
        await chapters_service.save_chapter_text(
            _access(book.id, caller.id, role=role, book_state=BookState.archived),
            str(chapter.id),
            UpdateChapterTextRequest(text="Should not land.", expected_version=1),
        )
    assert exc.value.reason == ChapterErrorReason.book_archived

    stored = await _stored(chapter.id)
    assert stored.text == "Preserved."
    assert stored.version == 1
    assert await _changes(chapter.id) == []
    assert await _revisions(chapter.id) == []


# DoD-12 (D10): the shared archived guard -- the one every write path in this feature
# calls, including the state transitions -- raises the archived reason on an
# `archived` book and passes silently on an active one.
def test_the_archived_guard_refuses_and_otherwise_passes__DoD12():
    archived = _access(1, 2, book_state=BookState.archived)
    with pytest.raises(ChapterError) as exc:
        chapters_service._require_not_archived(archived)
    assert exc.value.reason == ChapterErrorReason.book_archived

    assert chapters_service._require_not_archived(_access(1, 2)) is None


# DoD-12 (D10): the archive gate holds whatever the chapter's state and whatever the
# submitted version -- a stale save on an archived book is still the archived reason,
# because the gate runs before the chapter is even resolved.
async def test_archive_gate_precedes_the_state_and_version_checks__DoD12(db: DbConfig):
    owner = await _seed_user("archived-precedence-owner")
    book = await _seed_book(owner.id, state=BookState.archived)
    chapter = await _seed_chapter(
        book.id, state=ChapterState.closed, text="Preserved.", version=5
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.save_chapter_text(
            _access(book.id, owner.id, book_state=BookState.archived),
            str(chapter.id),
            UpdateChapterTextRequest(text="Nope.", expected_version=1),
        )
    assert exc.value.reason == ChapterErrorReason.book_archived


# ---------------------------------------------------------------------------
# DoD-13 — another book's chapter is NOT FOUND on both entry points
# ---------------------------------------------------------------------------


# DoD-13 (014's D4): a chapter whose book_id differs from the access context's book is
# not-found on BOTH entry points, for a caller who HAS the capability -- so the
# refusal cannot be a permission failure. The foreign chapter is untouched.
async def test_foreign_chapter_is_not_found_on_both_entry_points__DoD13(db: DbConfig):
    owner = await _seed_user("crossbook-text-owner")
    book = await _seed_book(owner.id, title="Mine")
    other = await _seed_book(owner.id, title="Theirs")
    access = _access(book.id, owner.id)
    foreign = await _seed_chapter(
        other.id, state=ChapterState.open, text="Another book's body.", version=1
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.get_chapter_text(access, str(foreign.id))
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.save_chapter_text(
            access, str(foreign.id), UpdateChapterTextRequest(text="x", expected_version=1)
        )
    assert exc.value.reason == ChapterErrorReason.not_found

    stored = await _stored(foreign.id)
    assert stored.text == "Another book's body."
    assert stored.version == 1
    assert await _changes(foreign.id) == []
    assert await _revisions(foreign.id) == []


# DoD-13: the same holds for a co-author of the access context's book, and an id that
# exists nowhere is likewise not-found on both entry points.
async def test_unknown_and_foreign_ids_are_not_found_for_a_co_author__DoD13(
    db: DbConfig,
):
    owner = await _seed_user("crossbook-text-owner-co")
    helper = await _seed_user("crossbook-text-co-author")
    book = await _seed_book(owner.id, title="Mine")
    other = await _seed_book(owner.id, title="Theirs")
    co_access = _access(book.id, helper.id, role=AccessRole.co_author)
    foreign = await _seed_chapter(other.id, state=ChapterState.open, text="Foreign")

    with pytest.raises(ChapterError) as exc:
        await chapters_service.get_chapter_text(co_access, str(foreign.id))
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.save_chapter_text(
            co_access,
            str(foreign.id),
            UpdateChapterTextRequest(text="x", expected_version=1),
        )
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.get_chapter_text(co_access, "999999999999")
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.save_chapter_text(
            co_access,
            "999999999999",
            UpdateChapterTextRequest(text="x", expected_version=1),
        )
    assert exc.value.reason == ChapterErrorReason.not_found


# ---------------------------------------------------------------------------
# DoD-14 — the two new capabilities, and no existing role set changed
# ---------------------------------------------------------------------------

# The role sets frozen by 009's authorization spine (authorization.md -> "Capability
# x role matrix", "Book lifecycle and settings -- owner only"), restated here so the
# "no existing capability's role set changed" half of DoD-14 is checkable without
# enumerating the whole matrix as a literal.
FROZEN_009_ROWS = {
    "read_book": {AccessRole.owner, AccessRole.co_author, AccessRole.reader},
    "view_book_detail": {AccessRole.owner, AccessRole.co_author},
    "archive_book": {AccessRole.owner},
    "transfer_ownership": {AccessRole.owner},
    "add_member": {AccessRole.owner},
    "remove_member": {AccessRole.owner},
    "set_visibility": {AccessRole.owner},
}


# DoD-14: the open / close / reopen capability is OWNER ONLY, and the body-write
# capability is owner + co-author -- exactly the two matrix rows in the step's table.
def test_the_two_new_capability_rows__DoD14():
    matrix = authz._CAPABILITY_MATRIX

    assert set(matrix[Capability.set_chapter_state]) == {AccessRole.owner}
    assert set(matrix[Capability.write_chapter_text]) == {
        AccessRole.owner,
        AccessRole.co_author,
    }


# DoD-14: the same two rows expressed through `require` -- the owner holds both, the
# co-author holds only the body write, and a reader / a non-member hold neither.
def test_require_honours_the_two_new_capabilities__DoD14():
    def access(role: AccessRole) -> BookAccess:
        return _access(1, 2, role=role)

    assert authz.require(access(AccessRole.owner), Capability.set_chapter_state) is None
    assert (
        authz.require(access(AccessRole.owner), Capability.write_chapter_text) is None
    )
    assert (
        authz.require(access(AccessRole.co_author), Capability.write_chapter_text)
        is None
    )

    for role in (AccessRole.co_author, AccessRole.reader, AccessRole.none):
        with pytest.raises(BookAuthorizationError):
            authz.require(access(role), Capability.set_chapter_state)

    for role in (AccessRole.reader, AccessRole.none):
        with pytest.raises(BookAuthorizationError):
            authz.require(access(role), Capability.write_chapter_text)


# DoD-14: no EXISTING capability's role set changed -- the 009-frozen rows still
# carry exactly their documented role sets, and every Capability member (old and new)
# still has exactly one matrix row.
def test_no_existing_capability_role_set_changed__DoD14():
    matrix = authz._CAPABILITY_MATRIX

    for name, expected_roles in FROZEN_009_ROWS.items():
        capability = Capability[name]
        assert set(matrix[capability]) == expected_roles, name

    # Every capability is covered exactly once -- the two new rows were appended, not
    # substituted for existing ones.
    assert set(matrix) == set(Capability)
    assert len(matrix) == len(Capability)
    assert Capability.set_chapter_state in matrix
    assert Capability.write_chapter_text in matrix
