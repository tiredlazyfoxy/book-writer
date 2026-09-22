"""The gated chapter close, its cancel, its finalize decision and the stale reopen
(feature 016.chapter-close-continuity) — DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5.

Bound to the frozen signatures in `status.md` -> `## Skeleton`, in
`app.services.chapters`::

    async def close_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse
    async def cancel_close(access: BookAccess, chapter_id: str) -> ChapterResponse
    async def reopen_chapter(access: BookAccess, chapter_id: str) -> ChapterResponse
    async def finalize_close_turn(access, chapter_id: str,
                                  tool_context: ToolContext) -> ChapterResponse

and in `app.services.tools`::

    @dataclass class ToolContext { book_id; access; subject; emit_frame;
                                   selection_text; active_notes_proposal }

plus the pre-existing frozen `authz.BookAccess` / `AccessRole`, `ChapterError` /
`ChapterErrorReason` and `ChapterResponse` (which now carries `summary` /
`summary_status`).

Every expected value comes from the SPEC — `plan.md` -> Interface + Definition of
done (DoD-1..DoD-5) and Decisions taken D3 / D4 / D6 / D7, and `context.md` — never
from implementation internals:

  - DoD-1 (US-038.AC-3): a close moves `open -> closing`, and is refused with the
    reused not-open reason from `planned` / `closing` / `closed`;
  - DoD-2 (UC-047, D3, D7): the finalize decision is a deterministic function of
    four independent facts — the summary artifact, the changeset artifact, the
    in-run active-notes proposal, and open `origin=check` flags. All three
    artifacts present with no blocking flag -> `closed`, both artifacts
    `approved`, `Book.active_notes` written from the proposal. ANY other
    combination -> `open` with the artifacts wiped, and on those branches
    `Book.active_notes` is never written. A `None` proposal
    (`propose_active_notes` never called) is one of those branches — an uncalled
    tool must never overwrite the book's live notes with `""`;
  - DoD-3 (D4): `cancel_close` on a `closing` chapter returns it to `open` and
    discards the run's artifacts; from any other state it is a no-op that changes
    nothing and still answers with the chapter;
  - DoD-4 (D6): a close deletes every `origin=check` flag on the chapter first and
    leaves `origin=person` flags untouched;
  - DoD-5 (US-055.AC-1): a reopen marks BOTH `Chapter.summary_status` and the
    chapter's `ChapterNoteChangeset.status` `stale`.

Async tests use `asyncio_mode = "auto"`; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. `User` / `Book` / `Chapter` /
`ChapterNoteChangeset` / `Flag` rows are seeded straight through the sibling `db/`
modules and `BookAccess` is built directly (a frozen dataclass), so there is no
route, no client, no JWT and no network in this module. A chapter is put into a
starting state by writing that state through `db/chapters.py` — the transitions are
the code under test and are never used to reach a precondition.
"""

import pytest

from app.db import books, chapter_note_changesets, chapters, flags, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chapter import Chapter, ChapterState, SummaryStatus
from app.models.chapter_notes import ChapterNoteChangeset, NoteStatus
from app.models.flag import Flag, FlagOrigin, FlagStatus
from app.models.schemas.chapters import ChapterResponse
from app.models.user import User, UserRole
from app.services import chapters as chapters_service
from app.services.authz import AccessRole, BookAccess
from app.services.chapters import ChapterError, ChapterErrorReason
from app.services.tools import ToolContext

# The book's accumulated live notes before any close runs — the value D7 exists to
# protect.
ACCUMULATED_NOTES = "Halden holds the north gate. The winter is in its third month."
# What a clean run's `propose_active_notes` offered instead.
PROPOSED_NOTES = "Halden holds the north gate. The gate fell in the fourth month."

DRAFT_SUMMARY = "The gate holds, then does not."


# ---------------------------------------------------------------------------
# Seeding helpers (db-layer rows + a directly-built access context).
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(
    owner_id: int,
    *,
    title: str = "A Book",
    state: BookState = BookState.active,
    active_notes: str = ACCUMULATED_NOTES,
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
            active_notes=active_notes,
        )
    )


def _access(
    book_id: int,
    user_id: int,
    *,
    role: AccessRole = AccessRole.owner,
    book_state: BookState = BookState.active,
) -> BookAccess:
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=role,
        book_state=book_state,
        visibility=Visibility.private,
        collaboration_mode=CollaborationMode.free,
    )


async def _seed_chapter(
    book_id: int,
    *,
    ordinal: int = 1,
    title: str = "Seeded",
    state: ChapterState = ChapterState.open,
    text: str = "the body",
    summary: str | None = None,
    summary_status: SummaryStatus | None = None,
) -> Chapter:
    return await chapters.create(
        Chapter(
            book_id=book_id,
            ordinal=ordinal,
            title=title,
            state=state,
            sketch="a sketch",
            text=text,
            version=1,
            summary=summary,
            summary_status=summary_status,
        )
    )


async def _seed_changeset(
    chapter_id: int, *, status: NoteStatus | None = NoteStatus.draft
) -> ChapterNoteChangeset:
    return await chapter_note_changesets.create(
        ChapterNoteChangeset(
            chapter_id=chapter_id,
            added="A new fact",
            modified="An amended fact",
            deleted="A retired fact",
            status=status,
        )
    )


async def _seed_flag(
    chapter_id: int,
    created_by: int,
    *,
    origin: FlagOrigin,
    status: FlagStatus = FlagStatus.open,
    comment: str = "a finding",
) -> Flag:
    return await flags.create(
        Flag(
            chapter_id=chapter_id,
            origin=origin,
            comment=comment,
            status=status,
            created_by=created_by,
        )
    )


async def _stored(chapter_id: int) -> Chapter:
    row = await chapters.get_by_id(chapter_id)
    assert row is not None
    return row


async def _stored_book(book_id: int) -> Book:
    row = await books.get_by_id(book_id)
    assert row is not None
    return row


def _context(
    book_id: int, access: BookAccess, *, proposal: str | None
) -> ToolContext:
    """The turn's tool context, carrying whatever the run proposed (or nothing)."""
    return ToolContext(book_id=book_id, access=access, active_notes_proposal=proposal)


# ---------------------------------------------------------------------------
# DoD-1 — the close transition is now GATED: open -> closing
# ---------------------------------------------------------------------------


# DoD-1 (US-038.AC-3): the owner's close on an `open` chapter moves it to `closing`
# — not to `closed`. `closing` is where the close procedure runs; only the finalize
# step may end it.
async def test_close_moves_open_to_closing__DoD1_US038_AC3(db: DbConfig):
    owner = await _seed_user("close-gate-owner")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(book.id, state=ChapterState.open)

    result = await chapters_service.close_chapter(_access(book.id, owner.id), str(target.id))

    assert isinstance(result, ChapterResponse)
    assert result.id == str(target.id)
    assert result.state == ChapterState.closing
    assert result.state != ChapterState.closed

    stored = await _stored(target.id)
    assert stored.state == ChapterState.closing


# DoD-1: a close from any non-`open` state is refused with the reused not-open
# reason, and nothing moves.
@pytest.mark.parametrize(
    "state",
    [ChapterState.planned, ChapterState.closing, ChapterState.closed],
    ids=["planned", "closing", "closed"],
)
async def test_close_refused_from_every_non_open_state__DoD1(
    db: DbConfig, state: ChapterState
):
    owner = await _seed_user(f"close-refused-owner-{state.value}")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(book.id, state=state)

    with pytest.raises(ChapterError) as exc:
        await chapters_service.close_chapter(_access(book.id, owner.id), str(target.id))
    assert exc.value.reason == ChapterErrorReason.chapter_not_open

    assert (await _stored(target.id)).state == state


# ---------------------------------------------------------------------------
# DoD-4 — the close deletes THIS chapter's check flags, and only those
# ---------------------------------------------------------------------------


# DoD-4 (D6): `POST /close` deletes every `origin=check` flag on the chapter — open
# or already resolved — so only the run that is starting can produce a blocking
# flag; `origin=person` flags are advisory and survive untouched.
async def test_close_deletes_check_flags_and_keeps_person_flags__DoD4_D6(db: DbConfig):
    owner = await _seed_user("flag-sweep-owner")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(book.id, state=ChapterState.open)

    open_check = await _seed_flag(
        target.id, owner.id, origin=FlagOrigin.check, comment="a stale check finding"
    )
    resolved_check = await _seed_flag(
        target.id,
        owner.id,
        origin=FlagOrigin.check,
        status=FlagStatus.resolved,
        comment="an older check finding",
    )
    open_person = await _seed_flag(
        target.id, owner.id, origin=FlagOrigin.person, comment="a reader's warning"
    )
    resolved_person = await _seed_flag(
        target.id,
        owner.id,
        origin=FlagOrigin.person,
        status=FlagStatus.resolved,
        comment="a warning already dealt with",
    )
    # Presence first: all four really exist before the close runs.
    assert {f.id for f in await flags.list_by_chapter(target.id)} == {
        open_check.id,
        resolved_check.id,
        open_person.id,
        resolved_person.id,
    }

    result = await chapters_service.close_chapter(_access(book.id, owner.id), str(target.id))

    assert result.state == ChapterState.closing

    remaining = await flags.list_by_chapter(target.id)
    assert {f.id for f in remaining} == {open_person.id, resolved_person.id}
    assert {f.origin for f in remaining} == {FlagOrigin.person}


# DoD-4: the sweep is scoped to the chapter being closed — another chapter's check
# flags are not deleted.
async def test_close_flag_sweep_is_scoped_to_the_chapter__DoD4(db: DbConfig):
    owner = await _seed_user("flag-sweep-scope-owner")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(book.id, ordinal=1, state=ChapterState.open)
    bystander = await _seed_chapter(
        book.id, ordinal=2, title="Elsewhere", state=ChapterState.closed
    )
    mine = await _seed_flag(target.id, owner.id, origin=FlagOrigin.check)
    theirs = await _seed_flag(bystander.id, owner.id, origin=FlagOrigin.check)

    await chapters_service.close_chapter(_access(book.id, owner.id), str(target.id))

    assert [f.id for f in await flags.list_by_chapter(target.id)] == []
    assert [f.id for f in await flags.list_by_chapter(bystander.id)] == [theirs.id]
    assert mine.id != theirs.id


# ---------------------------------------------------------------------------
# DoD-2 — the finalize decision table
# ---------------------------------------------------------------------------


# DoD-2 (UC-047, D3, D7): all three artifacts present — a `draft` summary, a
# `draft` changeset and a non-`None` active-notes proposal — with no open
# `origin=check` flag closes the chapter: both artifacts become `approved` in the
# same step (D3: no approval gate) and `Book.active_notes` is written from the
# in-run proposal (D7: written only at finalize).
async def test_finalize_clean_run_closes_and_applies_the_proposal__DoD2_UC047(
    db: DbConfig,
):
    owner = await _seed_user("finalize-clean-owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)
    target = await _seed_chapter(
        book.id,
        state=ChapterState.closing,
        summary=DRAFT_SUMMARY,
        summary_status=SummaryStatus.draft,
    )
    changeset = await _seed_changeset(target.id, status=NoteStatus.draft)

    result = await chapters_service.finalize_close_turn(
        access, str(target.id), _context(book.id, access, proposal=PROPOSED_NOTES)
    )

    assert result.state == ChapterState.closed
    assert result.summary == DRAFT_SUMMARY
    assert result.summary_status == SummaryStatus.approved

    stored = await _stored(target.id)
    assert stored.state == ChapterState.closed
    assert stored.summary == DRAFT_SUMMARY
    assert stored.summary_status is SummaryStatus.approved

    stored_changeset = await chapter_note_changesets.get_by_chapter(target.id)
    assert stored_changeset is not None
    assert stored_changeset.id == changeset.id
    assert stored_changeset.status is NoteStatus.approved

    # The book's live notes are now the run's proposal — not the old value.
    assert (await _stored_book(book.id)).active_notes == PROPOSED_NOTES


# DoD-2: neither a RESOLVED check flag nor an open PERSON flag blocks a clean run —
# only an OPEN `origin=check` flag does (D6: person flags are advisory).
@pytest.mark.parametrize(
    ("origin", "status"),
    [
        (FlagOrigin.check, FlagStatus.resolved),
        (FlagOrigin.person, FlagStatus.open),
        (FlagOrigin.person, FlagStatus.resolved),
    ],
    ids=["resolved_check", "open_person", "resolved_person"],
)
async def test_finalize_non_blocking_flags_still_close__DoD2(
    db: DbConfig, origin: FlagOrigin, status: FlagStatus
):
    owner = await _seed_user(f"finalize-nonblocking-{origin.value}-{status.value}")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)
    target = await _seed_chapter(
        book.id,
        state=ChapterState.closing,
        summary=DRAFT_SUMMARY,
        summary_status=SummaryStatus.draft,
    )
    await _seed_changeset(target.id, status=NoteStatus.draft)
    await _seed_flag(target.id, owner.id, origin=origin, status=status)

    result = await chapters_service.finalize_close_turn(
        access, str(target.id), _context(book.id, access, proposal=PROPOSED_NOTES)
    )

    assert result.state == ChapterState.closed
    assert (await _stored_book(book.id)).active_notes == PROPOSED_NOTES


# DoD-2 (D7's defect-fix branch, and the three other failing inputs): ANY of the
# four facts missing routes the chapter back to `open` with the run's artifacts
# wiped — the summary and its status cleared, the changeset row deleted — and on
# EVERY one of these branches `Book.active_notes` is never written. The `None`
# proposal case is the one D7 exists for: an uncalled `propose_active_notes` must
# never be read as an implicit `""` that overwrites the book's accumulated notes.
@pytest.mark.parametrize(
    ("summary_status", "changeset_status", "proposal", "blocking_check_flag"),
    [
        # 1. `propose_active_notes` was never called.
        (SummaryStatus.draft, NoteStatus.draft, None, False),
        # 2. no summary was drafted.
        (None, NoteStatus.draft, PROPOSED_NOTES, False),
        # 3. no changeset row at all (`changeset_status` sentinel: "no row").
        (SummaryStatus.draft, "absent", PROPOSED_NOTES, False),
        # 4. a changeset row exists but was not drafted by this run.
        (SummaryStatus.draft, NoteStatus.stale, PROPOSED_NOTES, False),
        # 5. the consistency check raised an open flag.
        (SummaryStatus.draft, NoteStatus.draft, PROPOSED_NOTES, True),
    ],
    ids=[
        "proposal_never_made",
        "no_summary_draft",
        "no_changeset_row",
        "changeset_not_draft",
        "open_check_flag",
    ],
)
async def test_finalize_any_missing_fact_reopens_and_wipes__DoD2_D7(
    db: DbConfig,
    summary_status,
    changeset_status,
    proposal: str | None,
    blocking_check_flag: bool,
):
    owner = await _seed_user(f"finalize-fail-{summary_status}-{changeset_status}-{proposal}-{blocking_check_flag}")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)
    target = await _seed_chapter(
        book.id,
        state=ChapterState.closing,
        summary=DRAFT_SUMMARY if summary_status is not None else None,
        summary_status=summary_status,
    )
    if changeset_status != "absent":
        await _seed_changeset(target.id, status=changeset_status)
    if blocking_check_flag:
        await _seed_flag(target.id, owner.id, origin=FlagOrigin.check)

    result = await chapters_service.finalize_close_turn(
        access, str(target.id), _context(book.id, access, proposal=proposal)
    )

    # Back to `open`, never `closed` and never left parked in `closing` (D4).
    assert result.state == ChapterState.open
    stored = await _stored(target.id)
    assert stored.state == ChapterState.open

    # The run's artifacts are gone — the same wipe `cancel_close` performs.
    assert stored.summary is None
    assert stored.summary_status is None
    assert await chapter_note_changesets.get_by_chapter(target.id) is None

    # ...and the book's accumulated live notes were never touched.
    assert (await _stored_book(book.id)).active_notes == ACCUMULATED_NOTES


# DoD-2 (D7): the empty string is a LEGITIMATE proposal — the author's run really
# did propose clearing the notes — and closes the chapter with `Book.active_notes`
# set to `""`. This is the case that must be distinguishable from "never called".
async def test_finalize_empty_string_proposal_is_legitimate__DoD2_D7(db: DbConfig):
    owner = await _seed_user("finalize-empty-proposal-owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)
    target = await _seed_chapter(
        book.id,
        state=ChapterState.closing,
        summary=DRAFT_SUMMARY,
        summary_status=SummaryStatus.draft,
    )
    await _seed_changeset(target.id, status=NoteStatus.draft)

    result = await chapters_service.finalize_close_turn(
        access, str(target.id), _context(book.id, access, proposal="")
    )

    assert result.state == ChapterState.closed
    assert (await _stored_book(book.id)).active_notes == ""


# ---------------------------------------------------------------------------
# DoD-3 — cancel discards; a no-op everywhere else
# ---------------------------------------------------------------------------


# DoD-3 (D4): `close/cancel` on a `closing` chapter returns it to `open` and
# discards the run's draft artifacts — the summary and its status cleared, the
# changeset row deleted. Nothing was ever applied to `Book.active_notes` (D7), so
# the book's live notes are unchanged too.
async def test_cancel_close_returns_to_open_and_discards__DoD3_D4(db: DbConfig):
    owner = await _seed_user("cancel-owner")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(
        book.id,
        state=ChapterState.closing,
        summary=DRAFT_SUMMARY,
        summary_status=SummaryStatus.draft,
    )
    await _seed_changeset(target.id, status=NoteStatus.draft)
    # Presence first: there really is something to discard.
    assert await chapter_note_changesets.get_by_chapter(target.id) is not None

    result = await chapters_service.cancel_close(_access(book.id, owner.id), str(target.id))

    assert isinstance(result, ChapterResponse)
    assert result.state == ChapterState.open
    assert result.summary is None
    assert result.summary_status is None

    stored = await _stored(target.id)
    assert stored.state == ChapterState.open
    assert stored.summary is None
    assert stored.summary_status is None
    assert await chapter_note_changesets.get_by_chapter(target.id) is None
    assert (await _stored_book(book.id)).active_notes == ACCUMULATED_NOTES


# DoD-3: from any other state the cancel is a NO-OP — it raises nothing, answers
# with the chapter as it stands, and discards nothing.
@pytest.mark.parametrize(
    "state",
    [ChapterState.planned, ChapterState.open, ChapterState.closed],
    ids=["planned", "open", "closed"],
)
async def test_cancel_close_is_a_no_op_from_other_states__DoD3(
    db: DbConfig, state: ChapterState
):
    owner = await _seed_user(f"cancel-noop-owner-{state.value}")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(
        book.id,
        state=state,
        summary=DRAFT_SUMMARY,
        summary_status=SummaryStatus.approved,
    )
    changeset = await _seed_changeset(target.id, status=NoteStatus.approved)

    result = await chapters_service.cancel_close(_access(book.id, owner.id), str(target.id))

    # Answered, unchanged.
    assert isinstance(result, ChapterResponse)
    assert result.id == str(target.id)
    assert result.state == state

    stored = await _stored(target.id)
    assert stored.state == state
    assert stored.summary == DRAFT_SUMMARY
    assert stored.summary_status is SummaryStatus.approved

    stored_changeset = await chapter_note_changesets.get_by_chapter(target.id)
    assert stored_changeset is not None
    assert stored_changeset.id == changeset.id
    assert stored_changeset.status is NoteStatus.approved


# ---------------------------------------------------------------------------
# DoD-5 — a reopen marks the continuity data stale
# ---------------------------------------------------------------------------


# DoD-5 (US-055.AC-1): reopening a `closed` chapter moves it to `open` and marks
# BOTH pieces of its continuity data `stale` — `Chapter.summary_status` and the
# chapter's `ChapterNoteChangeset.status`. The TEXT of both artifacts survives;
# only their standing changes.
async def test_reopen_marks_summary_and_changeset_stale__DoD5_US055_AC1(db: DbConfig):
    owner = await _seed_user("reopen-stale-owner")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(
        book.id,
        state=ChapterState.closed,
        summary=DRAFT_SUMMARY,
        summary_status=SummaryStatus.approved,
    )
    changeset = await _seed_changeset(target.id, status=NoteStatus.approved)

    result = await chapters_service.reopen_chapter(_access(book.id, owner.id), str(target.id))

    assert result.state == ChapterState.open
    assert result.summary_status == SummaryStatus.stale

    stored = await _stored(target.id)
    assert stored.state == ChapterState.open
    assert stored.summary_status is SummaryStatus.stale
    # The drafted text itself is not discarded by the reopen.
    assert stored.summary == DRAFT_SUMMARY

    stored_changeset = await chapter_note_changesets.get_by_chapter(target.id)
    assert stored_changeset is not None
    assert stored_changeset.id == changeset.id
    assert stored_changeset.status is NoteStatus.stale
    assert stored_changeset.added == changeset.added


# DoD-5: with no changeset row (a chapter closed under the pre-016 ungated path)
# the stale-marking is defensive — the reopen still succeeds, still marks the
# summary status, and creates no changeset row of its own.
async def test_reopen_with_no_changeset_row_still_marks_the_summary__DoD5(
    db: DbConfig,
):
    owner = await _seed_user("reopen-no-changeset-owner")
    book = await _seed_book(owner.id)
    target = await _seed_chapter(
        book.id,
        state=ChapterState.closed,
        summary=DRAFT_SUMMARY,
        summary_status=SummaryStatus.approved,
    )

    result = await chapters_service.reopen_chapter(_access(book.id, owner.id), str(target.id))

    assert result.state == ChapterState.open
    assert (await _stored(target.id)).summary_status is SummaryStatus.stale
    assert await chapter_note_changesets.get_by_chapter(target.id) is None
