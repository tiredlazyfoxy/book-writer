"""Editing the book's live state notes (feature 016.chapter-close-continuity)
— DoD-8.

Bound to the frozen signatures in `status.md` -> `## Skeleton`, in
`app.services.continuity`::

    class ContinuityErrorReason(str, Enum) { not_a_member, book_archived,
                                            proposal_mode_refused,
                                            chapter_not_found }
    class ContinuityError(Exception)   # carries .reason
    async def get_state_notes(access: BookAccess) -> BookStateNotesResponse
    async def update_state_notes(access,
        body: UpdateBookStateNotesRequest) -> BookStateNotesResponse

with `app.models.schemas.continuity.UpdateBookStateNotesRequest` /
`BookStateNotesResponse`, and the frozen `authz.BookAccess` / `AccessRole`.

Every expected value comes from the SPEC — `plan.md` -> Interface
("Writes `Book.active_notes` directly (UC-050 direct-edit path)"), DoD-8, and
Decisions taken D9 — never from implementation internals:

  - US-053.AC-1: in a FREE-mode book an authorized member's edit applies to the
    LIVE note set immediately — the next read is the edited value, with no
    intermediate proposal and no approval step;
  - US-053.AC-2 is deliberately NOT satisfied (D9, out of scope): in a
    PROPOSAL-mode book a co-author's edit is REFUSED with the proposal-mode reason
    rather than held, because FEAT-010's proposal-holding mechanism is not built.
    The refusal is the mode-and-role combination and nothing broader: the OWNER of
    the same proposal-mode book still edits, and the same co-author still edits in
    a free-mode book.

The per-chapter continuity reads (`get_chapter_changeset` / `get_book_continuity`)
and the flag/continuity route handlers are DTO mapping and pass-throughs, listed
under `plan.md` -> Test plan -> "Not tested (deliberate)", and are asserted
nowhere here.

Async tests use `asyncio_mode = "auto"`; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. Rows are seeded through the sibling `db/`
modules and `BookAccess` is built directly — no route, no client, no network.
"""

import pytest

from app.db import books, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.schemas.continuity import (
    BookStateNotesResponse,
    UpdateBookStateNotesRequest,
)
from app.models.user import User, UserRole
from app.services import continuity as continuity_service
from app.services.authz import AccessRole, BookAccess
from app.services.continuity import ContinuityError, ContinuityErrorReason

EXISTING_NOTES = "Halden holds the north gate."
EDITED_NOTES = "Halden held the north gate until the fourth month."

# D9: `edit_state_notes` is {owner, co_author}.
MAY_EDIT = [AccessRole.owner, AccessRole.co_author]


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(
    owner_id: int,
    *,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
    active_notes: str = EXISTING_NOTES,
) -> Book:
    return await books.create(
        Book(
            title="A Book",
            description="d",
            owner_id=owner_id,
            collaboration_mode=collaboration_mode,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt="",
            active_notes=active_notes,
        )
    )


def _access(
    book_id: int,
    user_id: int,
    *,
    role: AccessRole,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
) -> BookAccess:
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=role,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=collaboration_mode,
    )


# ---------------------------------------------------------------------------
# DoD-8 — free mode applies to the live note set immediately
# ---------------------------------------------------------------------------


# DoD-8 (US-053.AC-1, UC-050's direct-edit path): in a FREE-mode book both the
# owner and a co-author may edit the state notes, and the edit lands on the LIVE
# set at once — the response carries it, the stored book carries it, and a fresh
# read returns it. Nothing is held anywhere in between.
@pytest.mark.parametrize("role", MAY_EDIT, ids=[r.value for r in MAY_EDIT])
async def test_free_mode_edit_applies_immediately__DoD8_US053_AC1(
    db: DbConfig, role: AccessRole
):
    owner = await _seed_user(f"notes-owner-{role.value}")
    caller = owner if role == AccessRole.owner else await _seed_user(f"notes-caller-{role.value}")
    book = await _seed_book(owner.id, collaboration_mode=CollaborationMode.free)
    access = _access(book.id, caller.id, role=role)

    # Presence first: the book really holds the earlier notes.
    before = await continuity_service.get_state_notes(access)
    assert isinstance(before, BookStateNotesResponse)
    assert before.book_id == str(book.id)
    assert before.active_notes == EXISTING_NOTES

    result = await continuity_service.update_state_notes(
        access, UpdateBookStateNotesRequest(active_notes=EDITED_NOTES)
    )

    assert isinstance(result, BookStateNotesResponse)
    assert result.book_id == str(book.id)
    assert result.active_notes == EDITED_NOTES

    # The LIVE set, straight from the book row — not a proposal parked elsewhere.
    stored = await books.get_by_id(book.id)
    assert stored is not None
    assert stored.active_notes == EDITED_NOTES

    # ...and the next read agrees.
    after = await continuity_service.get_state_notes(access)
    assert after.active_notes == EDITED_NOTES


# DoD-8: the empty string is a legal edit — clearing the live notes is an edit like
# any other, not a no-op or a validation failure.
async def test_free_mode_edit_may_clear_the_notes__DoD8_US053_AC1(db: DbConfig):
    owner = await _seed_user("notes-clear-owner")
    book = await _seed_book(owner.id, collaboration_mode=CollaborationMode.free)
    access = _access(book.id, owner.id, role=AccessRole.owner)

    result = await continuity_service.update_state_notes(
        access, UpdateBookStateNotesRequest(active_notes="")
    )

    assert result.active_notes == ""
    stored = await books.get_by_id(book.id)
    assert stored is not None
    assert stored.active_notes == ""


# ---------------------------------------------------------------------------
# DoD-8 — proposal mode refuses a co-author (US-053.AC-2 is NOT satisfied)
# ---------------------------------------------------------------------------


# DoD-8 (D9; US-053.AC-2 deliberately unsatisfied): in a PROPOSAL-mode book a
# co-author's state-note edit is refused with the proposal-mode reason. FEAT-010's
# proposal-holding mechanism does not exist, so nothing is held: the live notes are
# exactly what they were.
async def test_proposal_mode_refuses_a_co_author__DoD8_D9(db: DbConfig):
    owner = await _seed_user("proposal-notes-owner")
    helper = await _seed_user("proposal-notes-co-author")
    book = await _seed_book(owner.id, collaboration_mode=CollaborationMode.proposal)

    with pytest.raises(ContinuityError) as exc:
        await continuity_service.update_state_notes(
            _access(
                book.id,
                helper.id,
                role=AccessRole.co_author,
                collaboration_mode=CollaborationMode.proposal,
            ),
            UpdateBookStateNotesRequest(active_notes=EDITED_NOTES),
        )
    assert exc.value.reason == ContinuityErrorReason.proposal_mode_refused

    stored = await books.get_by_id(book.id)
    assert stored is not None
    assert stored.active_notes == EXISTING_NOTES


# DoD-8: the refusal is the MODE-and-ROLE combination, not a blanket rule. The
# OWNER of the same proposal-mode book still edits the live set...
async def test_proposal_mode_still_lets_the_owner_edit__DoD8_D9(db: DbConfig):
    owner = await _seed_user("proposal-notes-owner-allowed")
    book = await _seed_book(owner.id, collaboration_mode=CollaborationMode.proposal)

    result = await continuity_service.update_state_notes(
        _access(
            book.id,
            owner.id,
            role=AccessRole.owner,
            collaboration_mode=CollaborationMode.proposal,
        ),
        UpdateBookStateNotesRequest(active_notes=EDITED_NOTES),
    )

    assert result.active_notes == EDITED_NOTES
    stored = await books.get_by_id(book.id)
    assert stored is not None
    assert stored.active_notes == EDITED_NOTES


# DoD-8: ...and the same co-author role edits freely in a FREE-mode book, so the
# refusal above is the collaboration mode and not the role alone.
async def test_a_co_author_edits_in_a_free_mode_book__DoD8_D9(db: DbConfig):
    owner = await _seed_user("free-notes-owner")
    helper = await _seed_user("free-notes-co-author")
    book = await _seed_book(owner.id, collaboration_mode=CollaborationMode.free)

    result = await continuity_service.update_state_notes(
        _access(
            book.id,
            helper.id,
            role=AccessRole.co_author,
            collaboration_mode=CollaborationMode.free,
        ),
        UpdateBookStateNotesRequest(active_notes=EDITED_NOTES),
    )

    assert result.active_notes == EDITED_NOTES
    stored = await books.get_by_id(book.id)
    assert stored is not None
    assert stored.active_notes == EDITED_NOTES
