"""Tests for the chapter DTOs + chapter service + the four new capabilities
(feature 014, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002), in
`app.models.schemas.chapters`:
    class CreateChapterRequest(BaseModel)        title, sketch
    class UpdateChapterSketchRequest(BaseModel)  sketch                (no version token, D6)
    class ReorderChaptersRequest(BaseModel)      chapter_ids: list[str]
    class ChapterResponse(BaseModel)             id, book_id, ordinal, title, state,
                                                 sketch, version, created_at, modified_at
    class ChapterListResponse(BaseModel)         chapters, can_reorder
and in `app.services.chapters`:
    class ChapterErrorReason(str, enum.Enum) { not_found, not_planned,
        invalid_reorder_set }
    class ChapterError(Exception)  __init__(reason, message="") -> .reason / .message
    async def list_chapters(access) -> ChapterListResponse
    async def get_chapter(access, chapter_id: str) -> ChapterResponse
    async def add_chapter(access, request: CreateChapterRequest) -> ChapterResponse
    async def update_sketch(access, chapter_id: str, request: UpdateChapterSketchRequest)
        -> ChapterResponse
    async def remove_chapter(access, chapter_id: str) -> None
    async def reorder_chapters(access, request: ReorderChaptersRequest)
        -> ChapterListResponse
plus the frozen `authz.BookAccess` / `AccessRole` / `BookAuthorizationError`.

Expected values come from the step spec (002.chapter-service.md -> Interface intent
+ Definition of done, 002.context.md, and the feature context.md wire contract /
authorization matrix / D5 / D6), never from implementation internals:
    - a new chapter is `planned`, carries the submitted sketch, and shows up in a
      following list (DoD-1, US-032.AC-1);
    - add APPENDS: an empty book's first chapter takes ordinal 1 and every further
      one takes the NEXT ORDINAL AFTER THE CURRENT HIGHEST -- not count + 1, because
      removal deliberately leaves a gap (DoD-2, UC-031, 002.context.md);
    - add / sketch-edit / remove are owner + co-author; a reader and a non-member
      are refused by the authorization error (DoD-3, the authorization matrix);
    - a sketch edit on a `planned` chapter stores the new sketch, does NOT bump
      `version`, takes no version token, and the last of two sequential edits wins
      (DoD-4, US-034.AC-1, D6);
    - a sketch edit or a removal on `open` / `closing` / `closed` is refused with the
      not-planned reason and writes nothing (DoD-5, DoD-7, US-034.AC-2, US-035.AC-2);
    - removing a `planned` chapter removes it from the list (DoD-6, US-035.AC-1);
    - reorder rewrites ordinals to 1..N in the submitted order (DoD-8, US-033.AC-1),
      is OWNER-ONLY (DoD-9, US-033.AC-2), validates the whole list BEFORE any write so
      an invalid list changes no ordinal at all (DoD-10), and works while a chapter is
      `open`, leaving that chapter's state, body and version alone (DoD-11, D5);
    - a chapter belonging to another book is NOT FOUND on every entry point that names
      one, never a permission failure (DoD-12, D4);
    - the list is ordered by ordinal ascending and `can_reorder` is true only for the
      owner (DoD-13, the wire contract);
    - every response carries string ids and exactly the wire contract's field set --
      no body text, no summary, no summary status -- and no ORM object escapes the
      service (DoD-14).

002.context.md forbids asserting `read_book`'s READER behaviour here (the reader
surface is the Reader SPA, out of scope): DoD-3 and DoD-12 are written against members
and non-members only, and DoD-13 asserts a reader's `can_reorder` WITHOUT asserting
whether the reader reached the list at all.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. User / Book / Chapter rows are seeded through
the sibling db/ modules and `BookAccess` is constructed directly (a frozen dataclass),
so there is no route, no client, no JWT and no network anywhere in this module.
"""

import pytest

from app.db import books, chapters, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chapter import Chapter, ChapterState
from app.models.schemas.chapters import (
    ChapterListResponse,
    ChapterResponse,
    CreateChapterRequest,
    ReorderChaptersRequest,
    UpdateChapterSketchRequest,
)
from app.models.user import User, UserRole
from app.services import chapters as chapters_service
from app.services.authz import AccessRole, BookAccess, BookAuthorizationError
from app.services.chapters import ChapterError, ChapterErrorReason


# The exact ChapterResponse field set, from context.md -> "The wire contract".
WIRE_FIELDS = {
    "id",
    "book_id",
    "ordinal",
    "title",
    "state",
    "sketch",
    "version",
    "created_at",
    "modified_at",
}


# ---------------------------------------------------------------------------
# Seeding helpers (db-layer rows + a directly-built access context).
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(owner_id: int, title: str = "A Book") -> Book:
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


def _access(
    book_id: int,
    user_id: int,
    *,
    role: AccessRole = AccessRole.owner,
) -> BookAccess:
    """A BookAccess built directly -- the frozen dataclass, no resolve, no HTTP."""
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=role,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=CollaborationMode.free,
    )


async def _seed_chapter(
    book_id: int,
    *,
    ordinal: int,
    title: str = "Seeded",
    sketch: str = "seeded sketch",
    state: ChapterState = ChapterState.planned,
    text: str = "",
) -> Chapter:
    """A Chapter inserted straight through db/chapters.py, bypassing the service.

    `ordinal` and `state` are required with no model default (002.context.md), so
    every insert supplies both. This is also how DoD-11's `open` chapter is forced
    into existence -- this feature ships no open transition.
    """
    return await chapters.create(
        Chapter(
            book_id=book_id,
            ordinal=ordinal,
            title=title,
            state=state,
            sketch=sketch,
            text=text,
        )
    )


async def _ordinals(book_id: int) -> dict[int, int]:
    """{chapter id -> stored ordinal}, read straight from the db layer."""
    return {c.id: c.ordinal for c in await chapters.list_by_book(book_id)}


# ---------------------------------------------------------------------------
# DoD-1 — add_chapter creates a planned chapter with the submitted sketch
# ---------------------------------------------------------------------------


# DoD-1 (US-032.AC-1): add_chapter creates a chapter in the `planned` state carrying
# the submitted sketch, and a following list_chapters includes it.
async def test_add_chapter_creates_planned_with_sketch__DoD1_US032_AC1(db: DbConfig):
    owner = await _seed_user("add-owner")
    book = await _seed_book(owner.id)

    created = await chapters_service.add_chapter(
        _access(book.id, owner.id),
        CreateChapterRequest(title="The Arrival", sketch="they arrive at dusk"),
    )

    assert created.title == "The Arrival"
    assert created.sketch == "they arrive at dusk"
    assert created.state == ChapterState.planned
    assert created.book_id == str(book.id)

    listing = await chapters_service.list_chapters(_access(book.id, owner.id))
    assert [c.id for c in listing.chapters] == [created.id]
    assert listing.chapters[0].sketch == "they arrive at dusk"
    assert listing.chapters[0].state == ChapterState.planned


# DoD-1 (US-032.AC-1): an empty sketch is a legitimate starting state -- it is stored
# as given and comes back as "".
async def test_add_chapter_accepts_an_empty_sketch__DoD1_US032_AC1(db: DbConfig):
    owner = await _seed_user("add-owner-empty-sketch")
    book = await _seed_book(owner.id)

    created = await chapters_service.add_chapter(
        _access(book.id, owner.id),
        CreateChapterRequest(title="Untitled Beat", sketch=""),
    )

    assert created.sketch == ""
    assert created.state == ChapterState.planned

    listing = await chapters_service.list_chapters(_access(book.id, owner.id))
    assert [c.sketch for c in listing.chapters] == [""]


# ---------------------------------------------------------------------------
# DoD-2 — add_chapter APPENDS: next ordinal after the current highest
# ---------------------------------------------------------------------------


# DoD-2 (UC-031): the first chapter of an empty book takes ordinal 1, and each further
# chapter takes the next ordinal after the current highest.
async def test_add_chapter_appends_from_ordinal_one__DoD2_UC031(db: DbConfig):
    owner = await _seed_user("append-owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    first = await chapters_service.add_chapter(
        access, CreateChapterRequest(title="One", sketch="a")
    )
    second = await chapters_service.add_chapter(
        access, CreateChapterRequest(title="Two", sketch="b")
    )
    third = await chapters_service.add_chapter(
        access, CreateChapterRequest(title="Three", sketch="c")
    )

    assert first.ordinal == 1
    assert second.ordinal == 2
    assert third.ordinal == 3


# DoD-2 (UC-031): the next ordinal is derived from the current HIGHEST, not from a
# count -- a book seeded with a single chapter at ordinal 7 appends at 8.
async def test_add_chapter_follows_the_highest_ordinal_not_the_count__DoD2_UC031(
    db: DbConfig,
):
    owner = await _seed_user("append-owner-high")
    book = await _seed_book(owner.id)
    await _seed_chapter(book.id, ordinal=7, title="Lone High")

    appended = await chapters_service.add_chapter(
        _access(book.id, owner.id),
        CreateChapterRequest(title="After The High One", sketch="s"),
    )

    assert appended.ordinal == 8


# DoD-2 (UC-031): removal deliberately leaves a gap and ordinals are NOT renumbered, so
# after removing the middle of three the next chapter still takes the ordinal after the
# highest (4), never count + 1 (3).
async def test_add_chapter_after_a_removal_leaves_the_gap__DoD2_UC031(db: DbConfig):
    owner = await _seed_user("append-owner-gap")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    await chapters_service.add_chapter(access, CreateChapterRequest(title="One", sketch=""))
    middle = await chapters_service.add_chapter(
        access, CreateChapterRequest(title="Two", sketch="")
    )
    await chapters_service.add_chapter(access, CreateChapterRequest(title="Three", sketch=""))

    await chapters_service.remove_chapter(access, middle.id)

    appended = await chapters_service.add_chapter(
        access, CreateChapterRequest(title="Four", sketch="")
    )

    assert appended.ordinal == 4

    # The gap at 2 survives -- removal renumbers nothing.
    listing = await chapters_service.list_chapters(access)
    assert [c.ordinal for c in listing.chapters] == [1, 3, 4]


# DoD-2 (UC-031): the rule holds whatever order the chapters were created in -- a
# chapter seeded at a HIGHER ordinal than the service-created ones still sets the mark.
async def test_add_chapter_appends_whatever_the_creation_order__DoD2_UC031(
    db: DbConfig,
):
    owner = await _seed_user("append-owner-order")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    await _seed_chapter(book.id, ordinal=5, title="Seeded Five")
    await _seed_chapter(book.id, ordinal=2, title="Seeded Two")

    appended = await chapters_service.add_chapter(
        access, CreateChapterRequest(title="Next", sketch="")
    )

    assert appended.ordinal == 6


# ---------------------------------------------------------------------------
# DoD-3 — co-author may add / edit sketch / remove; reader and non-member may not
# ---------------------------------------------------------------------------


# DoD-3: a co-author may add a chapter, edit a planned chapter's sketch and remove a
# planned chapter -- all three land.
async def test_co_author_may_add_edit_sketch_and_remove__DoD3(db: DbConfig):
    owner = await _seed_user("matrix-owner")
    helper = await _seed_user("matrix-co-author")
    book = await _seed_book(owner.id)
    co_access = _access(book.id, helper.id, role=AccessRole.co_author)

    created = await chapters_service.add_chapter(
        co_access, CreateChapterRequest(title="Co-authored", sketch="first")
    )
    assert created.state == ChapterState.planned

    edited = await chapters_service.update_sketch(
        co_access, created.id, UpdateChapterSketchRequest(sketch="second")
    )
    assert edited.sketch == "second"

    await chapters_service.remove_chapter(co_access, created.id)

    listing = await chapters_service.list_chapters(_access(book.id, owner.id))
    assert listing.chapters == []


# DoD-3: a reader and a caller with no relationship are refused on add, sketch edit and
# remove by the authorization error, and nothing is written.
@pytest.mark.parametrize("role", [AccessRole.reader, AccessRole.none])
async def test_reader_and_non_member_are_refused_on_all_three__DoD3(
    db: DbConfig, role: AccessRole
):
    owner = await _seed_user(f"refused-owner-{role.value}")
    outsider = await _seed_user(f"refused-caller-{role.value}")
    book = await _seed_book(owner.id)
    existing = await _seed_chapter(book.id, ordinal=1, title="Kept", sketch="untouched")
    bad_access = _access(book.id, outsider.id, role=role)

    with pytest.raises(BookAuthorizationError):
        await chapters_service.add_chapter(
            bad_access, CreateChapterRequest(title="Nope", sketch="nope")
        )

    with pytest.raises(BookAuthorizationError):
        await chapters_service.update_sketch(
            bad_access, str(existing.id), UpdateChapterSketchRequest(sketch="leak")
        )

    with pytest.raises(BookAuthorizationError):
        await chapters_service.remove_chapter(bad_access, str(existing.id))

    # Nothing landed: no new chapter, and the existing one is intact.
    stored = await chapters.list_by_book(book.id)
    assert [c.id for c in stored] == [existing.id]
    assert stored[0].sketch == "untouched"


# ---------------------------------------------------------------------------
# DoD-4 — update_sketch stores the sketch, leaves version alone, last write wins
# ---------------------------------------------------------------------------


# DoD-4 (US-034.AC-1, D6): update_sketch on a `planned` chapter stores the new sketch
# and leaves `version` unchanged.
async def test_update_sketch_stores_and_leaves_version__DoD4_US034_AC1(db: DbConfig):
    owner = await _seed_user("sketch-owner")
    book = await _seed_book(owner.id)
    seeded = await _seed_chapter(book.id, ordinal=1, title="Draftable", sketch="old")
    version_before = seeded.version

    updated = await chapters_service.update_sketch(
        _access(book.id, owner.id),
        str(seeded.id),
        UpdateChapterSketchRequest(sketch="a fresh sketch"),
    )

    assert updated.sketch == "a fresh sketch"
    assert updated.version == version_before
    assert updated.state == ChapterState.planned
    # The layer stamps modified_at on the write.
    assert updated.modified_at is not None

    stored = await chapters.get_by_id(seeded.id)
    assert stored is not None
    assert stored.sketch == "a fresh sketch"
    assert stored.version == version_before


# DoD-4 (D6): the request carries NO version token -- `sketch` is its only field.
def test_update_sketch_request_has_no_version_token__DoD4_US034_AC1():
    assert set(UpdateChapterSketchRequest.model_fields) == {"sketch"}


# DoD-4 (D6): two sequential edits both succeed and the last one wins -- no version
# token, no conflict, no bump.
async def test_two_sequential_sketch_edits_last_one_wins__DoD4_US034_AC1(db: DbConfig):
    owner = await _seed_user("sketch-owner-lww")
    helper = await _seed_user("sketch-co-author-lww")
    book = await _seed_book(owner.id)
    seeded = await _seed_chapter(book.id, ordinal=1, title="Contested", sketch="v0")
    version_before = seeded.version

    first = await chapters_service.update_sketch(
        _access(book.id, owner.id),
        str(seeded.id),
        UpdateChapterSketchRequest(sketch="v1 by the owner"),
    )
    second = await chapters_service.update_sketch(
        _access(book.id, helper.id, role=AccessRole.co_author),
        str(seeded.id),
        UpdateChapterSketchRequest(sketch="v2 by the co-author"),
    )

    assert first.sketch == "v1 by the owner"
    assert second.sketch == "v2 by the co-author"

    stored = await chapters.get_by_id(seeded.id)
    assert stored is not None
    assert stored.sketch == "v2 by the co-author"
    assert stored.version == version_before


# ---------------------------------------------------------------------------
# DoD-5 — update_sketch on a non-planned chapter is refused, and stores nothing
# ---------------------------------------------------------------------------


# DoD-5 (US-034.AC-2): a sketch edit on a chapter in `open`, `closing` or `closed` is
# refused with the not-planned reason and stores nothing.
@pytest.mark.parametrize(
    "state", [ChapterState.open, ChapterState.closing, ChapterState.closed]
)
async def test_update_sketch_on_non_planned_is_refused__DoD5_US034_AC2(
    db: DbConfig, state: ChapterState
):
    owner = await _seed_user(f"sketch-locked-owner-{state.value}")
    book = await _seed_book(owner.id)
    seeded = await _seed_chapter(
        book.id, ordinal=1, title="Locked", sketch="original", state=state
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.update_sketch(
            _access(book.id, owner.id),
            str(seeded.id),
            UpdateChapterSketchRequest(sketch="should not land"),
        )
    assert exc.value.reason == ChapterErrorReason.not_planned

    stored = await chapters.get_by_id(seeded.id)
    assert stored is not None
    assert stored.sketch == "original"
    assert stored.state == state


# ---------------------------------------------------------------------------
# DoD-6 — remove_chapter removes a planned chapter
# ---------------------------------------------------------------------------


# DoD-6 (US-035.AC-1): remove_chapter on a `planned` chapter removes it, and it no
# longer appears in list_chapters. The book's other chapters survive.
async def test_remove_planned_chapter__DoD6_US035_AC1(db: DbConfig):
    owner = await _seed_user("remove-owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)
    doomed = await _seed_chapter(book.id, ordinal=1, title="Doomed")
    survivor = await _seed_chapter(book.id, ordinal=2, title="Survivor")

    result = await chapters_service.remove_chapter(access, str(doomed.id))
    assert result is None

    listing = await chapters_service.list_chapters(access)
    assert [c.id for c in listing.chapters] == [str(survivor.id)]

    assert await chapters.get_by_id(doomed.id) is None


# ---------------------------------------------------------------------------
# DoD-7 — remove_chapter on a non-planned chapter is refused, and it survives
# ---------------------------------------------------------------------------


# DoD-7 (US-035.AC-2): removing a chapter in `open`, `closing` or `closed` is refused
# with the not-planned reason and the chapter still exists.
@pytest.mark.parametrize(
    "state", [ChapterState.open, ChapterState.closing, ChapterState.closed]
)
async def test_remove_non_planned_is_refused__DoD7_US035_AC2(
    db: DbConfig, state: ChapterState
):
    owner = await _seed_user(f"remove-locked-owner-{state.value}")
    book = await _seed_book(owner.id)
    seeded = await _seed_chapter(
        book.id, ordinal=1, title="Unremovable", sketch="kept", state=state
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.remove_chapter(_access(book.id, owner.id), str(seeded.id))
    assert exc.value.reason == ChapterErrorReason.not_planned

    stored = await chapters.get_by_id(seeded.id)
    assert stored is not None
    assert stored.state == state
    assert stored.sketch == "kept"


# ---------------------------------------------------------------------------
# DoD-8 — reorder rewrites ordinals to 1..N in the submitted order
# ---------------------------------------------------------------------------


# DoD-8 (US-033.AC-1): reorder_chapters rewrites ordinals to 1..N in the submitted
# order, returns the freshly ordered list, and a following list_chapters agrees.
async def test_reorder_rewrites_ordinals_one_to_n__DoD8_US033_AC1(db: DbConfig):
    owner = await _seed_user("reorder-owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)
    a = await _seed_chapter(book.id, ordinal=1, title="A")
    b = await _seed_chapter(book.id, ordinal=2, title="B")
    c = await _seed_chapter(book.id, ordinal=3, title="C")

    submitted = [str(c.id), str(a.id), str(b.id)]
    result = await chapters_service.reorder_chapters(
        access, ReorderChaptersRequest(chapter_ids=submitted)
    )

    assert [ch.id for ch in result.chapters] == submitted
    assert [ch.ordinal for ch in result.chapters] == [1, 2, 3]

    listing = await chapters_service.list_chapters(access)
    assert [ch.id for ch in listing.chapters] == submitted
    assert [ch.ordinal for ch in listing.chapters] == [1, 2, 3]

    # The stored rows carry the new ordinals.
    assert await _ordinals(book.id) == {c.id: 1, a.id: 2, b.id: 3}


# DoD-8 (US-033.AC-1): reorder normalizes a gapped ordinal set to a contiguous 1..N.
async def test_reorder_normalizes_gapped_ordinals__DoD8_US033_AC1(db: DbConfig):
    owner = await _seed_user("reorder-owner-gapped")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)
    a = await _seed_chapter(book.id, ordinal=3, title="A")
    b = await _seed_chapter(book.id, ordinal=9, title="B")

    result = await chapters_service.reorder_chapters(
        access, ReorderChaptersRequest(chapter_ids=[str(b.id), str(a.id)])
    )

    assert [ch.ordinal for ch in result.chapters] == [1, 2]
    assert await _ordinals(book.id) == {b.id: 1, a.id: 2}


# ---------------------------------------------------------------------------
# DoD-9 — reorder is owner-only
# ---------------------------------------------------------------------------


# DoD-9 (US-033.AC-2): a co-author calling reorder_chapters is refused by the
# authorization error, and the ordinals are unchanged.
async def test_co_author_reorder_is_refused__DoD9_US033_AC2(db: DbConfig):
    owner = await _seed_user("reorder-owner-only")
    helper = await _seed_user("reorder-co-author")
    book = await _seed_book(owner.id)
    a = await _seed_chapter(book.id, ordinal=1, title="A")
    b = await _seed_chapter(book.id, ordinal=2, title="B")
    before = await _ordinals(book.id)

    with pytest.raises(BookAuthorizationError):
        await chapters_service.reorder_chapters(
            _access(book.id, helper.id, role=AccessRole.co_author),
            ReorderChaptersRequest(chapter_ids=[str(b.id), str(a.id)]),
        )

    assert await _ordinals(book.id) == before


# ---------------------------------------------------------------------------
# DoD-10 — an invalid reorder list changes NO ordinal
# ---------------------------------------------------------------------------


# DoD-10: reorder_chapters refuses with the invalid-set reason, and changes no ordinal,
# when the submitted list omits a chapter, adds an unknown id or repeats an id.
@pytest.mark.parametrize("flavour", ["omits", "unknown", "duplicate"])
async def test_invalid_reorder_list_changes_nothing__DoD10(db: DbConfig, flavour: str):
    owner = await _seed_user(f"reorder-invalid-owner-{flavour}")
    book = await _seed_book(owner.id)
    a = await _seed_chapter(book.id, ordinal=1, title="A")
    b = await _seed_chapter(book.id, ordinal=2, title="B")
    c = await _seed_chapter(book.id, ordinal=3, title="C")
    before = await _ordinals(book.id)

    if flavour == "omits":
        # A real reordering of the two it does name -- so nothing but the validation
        # can be what leaves the ordinals alone.
        submitted = [str(c.id), str(a.id)]
    elif flavour == "unknown":
        submitted = [str(c.id), str(b.id), str(a.id), "999999999999"]
    else:
        submitted = [str(c.id), str(c.id), str(a.id)]

    with pytest.raises(ChapterError) as exc:
        await chapters_service.reorder_chapters(
            _access(book.id, owner.id), ReorderChaptersRequest(chapter_ids=submitted)
        )
    assert exc.value.reason == ChapterErrorReason.invalid_reorder_set

    assert await _ordinals(book.id) == before


# DoD-10: a list naming a chapter that belongs to ANOTHER book is likewise the
# invalid-set reason, and neither book's ordinals move.
async def test_reorder_list_with_a_foreign_chapter_changes_nothing__DoD10(db: DbConfig):
    owner = await _seed_user("reorder-foreign-owner")
    book = await _seed_book(owner.id, title="Mine")
    other = await _seed_book(owner.id, title="Theirs")
    a = await _seed_chapter(book.id, ordinal=1, title="A")
    b = await _seed_chapter(book.id, ordinal=2, title="B")
    foreign = await _seed_chapter(other.id, ordinal=1, title="Foreign")
    before = await _ordinals(book.id)
    other_before = await _ordinals(other.id)

    with pytest.raises(ChapterError) as exc:
        await chapters_service.reorder_chapters(
            _access(book.id, owner.id),
            ReorderChaptersRequest(chapter_ids=[str(b.id), str(foreign.id)]),
        )
    assert exc.value.reason == ChapterErrorReason.invalid_reorder_set

    assert await _ordinals(book.id) == before
    assert await _ordinals(other.id) == other_before
    # a's ordinal specifically is untouched -- the write never started.
    assert before[a.id] == 1


# ---------------------------------------------------------------------------
# DoD-11 — reorder works while a chapter is open (D5)
# ---------------------------------------------------------------------------


# DoD-11 (D5): reorder_chapters succeeds while one of the book's chapters is `open`,
# and that chapter's state, body and version are unchanged afterwards. Only `ordinal`
# moves.
async def test_reorder_with_an_open_chapter__DoD11(db: DbConfig):
    owner = await _seed_user("reorder-open-owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)
    planned = await _seed_chapter(book.id, ordinal=1, title="Planned")
    opened = await _seed_chapter(
        book.id,
        ordinal=2,
        title="Open One",
        sketch="an open chapter's sketch",
        state=ChapterState.open,
        text="the body that must not move",
    )
    version_before = opened.version

    result = await chapters_service.reorder_chapters(
        access, ReorderChaptersRequest(chapter_ids=[str(opened.id), str(planned.id)])
    )

    assert [ch.id for ch in result.chapters] == [str(opened.id), str(planned.id)]
    assert [ch.ordinal for ch in result.chapters] == [1, 2]

    stored = await chapters.get_by_id(opened.id)
    assert stored is not None
    assert stored.ordinal == 1
    assert stored.state == ChapterState.open
    assert stored.text == "the body that must not move"
    assert stored.version == version_before


# ---------------------------------------------------------------------------
# DoD-12 — another book's chapter is NOT FOUND, never a permission failure
# ---------------------------------------------------------------------------


# DoD-12 (D4): a chapter whose book_id differs from the access context's book is
# not-found on read, on the sketch edit and on remove -- for a member who HAS the
# capability, so the refusal cannot be an authorization failure. The foreign chapter is
# left untouched.
async def test_foreign_chapter_is_not_found_on_every_entry_point__DoD12(db: DbConfig):
    owner = await _seed_user("crossbook-owner")
    book = await _seed_book(owner.id, title="Mine")
    other = await _seed_book(owner.id, title="Theirs")
    access = _access(book.id, owner.id)
    foreign = await _seed_chapter(
        other.id, ordinal=1, title="Foreign", sketch="another book's sketch"
    )

    with pytest.raises(ChapterError) as exc:
        await chapters_service.get_chapter(access, str(foreign.id))
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.update_sketch(
            access, str(foreign.id), UpdateChapterSketchRequest(sketch="leak")
        )
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.remove_chapter(access, str(foreign.id))
    assert exc.value.reason == ChapterErrorReason.not_found

    stored = await chapters.get_by_id(foreign.id)
    assert stored is not None
    assert stored.sketch == "another book's sketch"


# DoD-12 (D4): the same holds for a co-author of the access context's book -- another
# book's chapter is not-found, not a permission failure.
async def test_foreign_chapter_is_not_found_for_a_co_author__DoD12(db: DbConfig):
    owner = await _seed_user("crossbook-owner-co")
    helper = await _seed_user("crossbook-co-author")
    book = await _seed_book(owner.id, title="Mine")
    other = await _seed_book(owner.id, title="Theirs")
    co_access = _access(book.id, helper.id, role=AccessRole.co_author)
    foreign = await _seed_chapter(other.id, ordinal=1, title="Foreign")

    with pytest.raises(ChapterError) as exc:
        await chapters_service.get_chapter(co_access, str(foreign.id))
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.update_sketch(
            co_access, str(foreign.id), UpdateChapterSketchRequest(sketch="leak")
        )
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.remove_chapter(co_access, str(foreign.id))
    assert exc.value.reason == ChapterErrorReason.not_found

    assert await chapters.get_by_id(foreign.id) is not None


# DoD-12 (D4): an id that exists nowhere is the same not-found reason on all three.
async def test_unknown_chapter_id_is_not_found__DoD12(db: DbConfig):
    owner = await _seed_user("unknown-chapter-owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    with pytest.raises(ChapterError) as exc:
        await chapters_service.get_chapter(access, "999999999999")
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.update_sketch(
            access, "999999999999", UpdateChapterSketchRequest(sketch="x")
        )
    assert exc.value.reason == ChapterErrorReason.not_found

    with pytest.raises(ChapterError) as exc:
        await chapters_service.remove_chapter(access, "999999999999")
    assert exc.value.reason == ChapterErrorReason.not_found


# ---------------------------------------------------------------------------
# DoD-13 — ordering by ordinal ascending, and can_reorder
# ---------------------------------------------------------------------------


# DoD-13: list_chapters returns the chapters ordered by ordinal ascending, whatever
# order the rows were created in, and scoped to the access context's book.
async def test_list_is_ordered_by_ordinal_ascending__DoD13(db: DbConfig):
    owner = await _seed_user("list-order-owner")
    book = await _seed_book(owner.id, title="Mine")
    other = await _seed_book(owner.id, title="Theirs")
    third = await _seed_chapter(book.id, ordinal=3, title="Third")
    first = await _seed_chapter(book.id, ordinal=1, title="First")
    second = await _seed_chapter(book.id, ordinal=2, title="Second")
    await _seed_chapter(other.id, ordinal=1, title="Not Mine")

    listing = await chapters_service.list_chapters(_access(book.id, owner.id))

    assert [ch.id for ch in listing.chapters] == [
        str(first.id),
        str(second.id),
        str(third.id),
    ]
    assert [ch.ordinal for ch in listing.chapters] == [1, 2, 3]
    assert [ch.title for ch in listing.chapters] == ["First", "Second", "Third"]


# DoD-13: can_reorder is true for the owner and false for a co-author. For a reader it
# is likewise false -- asserted only if the reader reaches the list at all, because
# read_book's reader row is out of this step's scope (002.context.md).
async def test_can_reorder_is_owner_only__DoD13(db: DbConfig):
    owner = await _seed_user("can-reorder-owner")
    helper = await _seed_user("can-reorder-co-author")
    lurker = await _seed_user("can-reorder-reader")
    book = await _seed_book(owner.id)
    await _seed_chapter(book.id, ordinal=1, title="Only")

    owner_listing = await chapters_service.list_chapters(_access(book.id, owner.id))
    assert owner_listing.can_reorder is True

    co_listing = await chapters_service.list_chapters(
        _access(book.id, helper.id, role=AccessRole.co_author)
    )
    assert co_listing.can_reorder is False

    reader_listing: ChapterListResponse | None
    try:
        reader_listing = await chapters_service.list_chapters(
            _access(book.id, lurker.id, role=AccessRole.reader)
        )
    except BookAuthorizationError:
        # Whether a reader reaches the list is deliberately NOT asserted here.
        reader_listing = None
    if reader_listing is not None:
        assert reader_listing.can_reorder is False


# ---------------------------------------------------------------------------
# DoD-14 — string ids, the wire contract's field set, no ORM object
# ---------------------------------------------------------------------------


# DoD-14: ChapterResponse carries exactly the wire contract's fields -- no body text,
# no summary, no summary status.
def test_chapter_response_exposes_only_the_wire_fields__DoD14():
    assert set(ChapterResponse.model_fields) == WIRE_FIELDS


# DoD-14: every response from every entry point carries its ids as strings, exposes
# only the wire contract's fields, and is a DTO -- no ORM object reaches the caller.
async def test_responses_are_string_id_dtos_only__DoD14(db: DbConfig):
    owner = await _seed_user("dto-owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    created = await chapters_service.add_chapter(
        access, CreateChapterRequest(title="Shaped", sketch="s")
    )
    fetched = await chapters_service.get_chapter(access, created.id)
    edited = await chapters_service.update_sketch(
        access, created.id, UpdateChapterSketchRequest(sketch="s2")
    )
    listing = await chapters_service.list_chapters(access)
    reordered = await chapters_service.reorder_chapters(
        access, ReorderChaptersRequest(chapter_ids=[created.id])
    )

    assert isinstance(listing, ChapterListResponse)
    assert isinstance(reordered, ChapterListResponse)

    every = [created, fetched, edited, *listing.chapters, *reordered.chapters]
    assert len(every) == 5
    for resp in every:
        assert isinstance(resp, ChapterResponse)
        assert not isinstance(resp, Chapter)
        assert isinstance(resp.id, str)
        assert isinstance(resp.book_id, str)
        assert resp.id == str(created.id)
        assert resp.book_id == str(book.id)
        assert set(resp.model_dump()) == WIRE_FIELDS
