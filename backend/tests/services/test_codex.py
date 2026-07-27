"""Tests for the codex service + DTOs (feature 013, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002), in
`app.models.schemas.codex`:
    class CreateCodexEntryRequest(BaseModel)  kind, name=None, body
    class UpdateCodexEntryRequest(BaseModel)  name=None, body, expected_modified_at
        (required but nullable; `kind` is deliberately absent -- not updatable)
    class CodexEntryResponse(BaseModel)  id, book_id, kind, name, body, archived,
        author_id, modified_by, created_at, modified_at  (every id a str)
    class CodexEntryListResponse(BaseModel)  items
and in `app.services.codex`:
    class CodexErrorReason(str, enum.Enum) { entry_not_found, name_required,
        name_not_allowed, entry_archived, stale_modified_at,
        proposal_mode_unsupported }
    class CodexError(Exception)  __init__(reason, message="") -> .reason / .message
    async def create_entry(access, user, req) -> CodexEntryResponse
    async def list_entries(access, kind=None, needle=None, include_archived=False)
        -> CodexEntryListResponse
    async def get_entry(access, entry_id: str) -> CodexEntryResponse
    async def update_entry(access, user, entry_id: str, req) -> CodexEntryResponse
plus the frozen `authz.BookAccess` / `AccessRole` / `BookAuthorizationError`.

Expected values come from the step spec (002.codex-schemas-service.md -> Interface
intent + Definition of done, plus 002.context.md and the feature context.md
decisions), never from implementation internals:
    - character/location require a non-blank name, fact refuses one and stores
      null; a whitespace-only name counts as absent (DoD-1..4, US-078.AC-1/AC-2);
    - free mode applies both the owner's and a co-author's write immediately
      (DoD-5, DoD-6, US-079.AC-1);
    - proposal mode refuses a **co-author's** create and edit with the
      proposal-unsupported reason, whose message names FEAT-010, while the
      owner's write still applies (DoD-7..9, decision 3);
    - an edit writes exactly one CodexEntryVersion carrying the entry's PRIOR
      name/body/kind, with 1-based generations incrementing per edit, and sets
      modified_by while leaving author_id at the original creator
      (DoD-10..12, UC-070 / domain-codex.md);
    - a stale expected `modified_at` is refused with no version row written and
      the entry unchanged; an archived entry is refused (DoD-13, DoD-14);
    - listing applies the kind / needle / include-archived filters and emits
      string ids (DoD-15, UC-071 / US-080.AC-1);
    - another book's entry is not-found, and reader / non-member access is
      refused by authz on all four calls (DoD-16, DoD-17, US-085.AC-1).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. User / Book / CodexEntry rows are seeded
through the db layer (tests/services/test_chats.py style) and `BookAccess` is
constructed directly (a frozen dataclass), so there is no HTTP round-trip and no
network anywhere in this module.
"""

from datetime import datetime, timedelta

import pytest

from app.db import books, codex_entries, codex_entry_versions, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.user import User, UserRole
from app.models.schemas.codex import (
    CreateCodexEntryRequest,
    UpdateCodexEntryRequest,
)
from app.services import codex as codex_service
from app.services.authz import AccessRole, BookAccess, BookAuthorizationError
from app.services.codex import CodexError, CodexErrorReason


# ---------------------------------------------------------------------------
# Seeding helpers (db-layer rows + a directly-built access context).
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(
    owner_id: int,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
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
            active_notes="",
        )
    )


def _access(
    book_id: int,
    user_id: int,
    *,
    role: AccessRole = AccessRole.owner,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
) -> BookAccess:
    """A BookAccess built directly -- the frozen dataclass, no resolve, no HTTP.

    `collaboration_mode` is already resolved on the context handed to the service
    (002.context.md), so the service never re-reads the book to learn the mode.
    """
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=role,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=collaboration_mode,
    )


async def _seed_entry_row(
    book_id: int,
    author_id: int,
    *,
    kind: CodexKind = CodexKind.character,
    name: str | None = "Seeded",
    body: str = "seeded body",
    archived: bool = False,
) -> CodexEntry:
    """A CodexEntry inserted straight through the db layer (bypassing the rules)."""
    return await codex_entries.create(
        CodexEntry(
            book_id=book_id,
            kind=kind,
            name=name,
            body=body,
            archived=archived,
            author_id=author_id,
        )
    )


# ---------------------------------------------------------------------------
# DoD-1 — a character / location with a non-blank name is stored and returned
# ---------------------------------------------------------------------------


# DoD-1 (US-078.AC-1): creating a `character` with a non-blank name stores the
# entry with that name and returns it; the stored row agrees with the response.
async def test_create_character_with_name__DoD1_US078_AC1(db: DbConfig):
    author = await _seed_user("alice")
    book = await _seed_book(author.id)

    resp = await codex_service.create_entry(
        _access(book.id, author.id),
        author,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Aragorn", body="a ranger"
        ),
    )

    assert resp.name == "Aragorn"
    assert resp.body == "a ranger"
    assert resp.kind is CodexKind.character
    assert resp.book_id == str(book.id)
    assert resp.author_id == str(author.id)
    assert resp.archived is False

    stored = await codex_entries.get_by_id(int(resp.id))
    assert stored is not None
    assert stored.name == "Aragorn"
    assert stored.body == "a ranger"
    assert stored.kind is CodexKind.character
    assert stored.book_id == book.id
    assert stored.author_id == author.id


# DoD-1 (US-078.AC-1): the same holds for a `location`.
async def test_create_location_with_name__DoD1_US078_AC1(db: DbConfig):
    author = await _seed_user("bob")
    book = await _seed_book(author.id)

    resp = await codex_service.create_entry(
        _access(book.id, author.id),
        author,
        CreateCodexEntryRequest(
            kind=CodexKind.location, name="Rivendell", body="a hidden valley"
        ),
    )

    assert resp.name == "Rivendell"
    assert resp.kind is CodexKind.location

    stored = await codex_entries.get_by_id(int(resp.id))
    assert stored is not None
    assert stored.name == "Rivendell"
    assert stored.kind is CodexKind.location


# ---------------------------------------------------------------------------
# DoD-2 — a missing or whitespace-only name is refused for character / location
# ---------------------------------------------------------------------------


# DoD-2 (US-078.AC-1): creating a `character` or a `location` with NO name is
# refused with the name-required reason and writes nothing.
@pytest.mark.parametrize("kind", [CodexKind.character, CodexKind.location])
async def test_create_named_kind_without_name_is_refused__DoD2_US078_AC1(
    db: DbConfig, kind: CodexKind
):
    author = await _seed_user("carol")
    book = await _seed_book(author.id)

    with pytest.raises(CodexError) as exc:
        await codex_service.create_entry(
            _access(book.id, author.id),
            author,
            CreateCodexEntryRequest(kind=kind, name=None, body="some body"),
        )
    assert exc.value.reason == CodexErrorReason.name_required

    assert await codex_entries.list_by_book(book.id, include_archived=True) == []


# DoD-2 (US-078.AC-1): a WHITESPACE-ONLY name counts as absent -- it is refused
# with the name-required reason and writes nothing.
@pytest.mark.parametrize("blank", ["   ", "\t", "\n", " \t\n "])
async def test_create_character_with_blank_name_is_refused__DoD2_US078_AC1(
    db: DbConfig, blank: str
):
    author = await _seed_user("dave")
    book = await _seed_book(author.id)

    with pytest.raises(CodexError) as exc:
        await codex_service.create_entry(
            _access(book.id, author.id),
            author,
            CreateCodexEntryRequest(
                kind=CodexKind.character, name=blank, body="some body"
            ),
        )
    assert exc.value.reason == CodexErrorReason.name_required

    assert await codex_entries.list_by_book(book.id, include_archived=True) == []


# DoD-2 (US-078.AC-1): a whitespace-only name is refused for a `location` too.
async def test_create_location_with_blank_name_is_refused__DoD2_US078_AC1(
    db: DbConfig,
):
    author = await _seed_user("erin")
    book = await _seed_book(author.id)

    with pytest.raises(CodexError) as exc:
        await codex_service.create_entry(
            _access(book.id, author.id),
            author,
            CreateCodexEntryRequest(
                kind=CodexKind.location, name="   ", body="a place"
            ),
        )
    assert exc.value.reason == CodexErrorReason.name_required

    assert await codex_entries.list_by_book(book.id, include_archived=True) == []


# ---------------------------------------------------------------------------
# DoD-3 — a fact with no name succeeds and stores a null name
# ---------------------------------------------------------------------------


# DoD-3 (US-078.AC-2): creating a `fact` with no name succeeds and the stored
# entry's name is null (as is the response's).
async def test_create_fact_without_name_stores_null__DoD3_US078_AC2(db: DbConfig):
    author = await _seed_user("frank")
    book = await _seed_book(author.id)

    resp = await codex_service.create_entry(
        _access(book.id, author.id),
        author,
        CreateCodexEntryRequest(
            kind=CodexKind.fact, name=None, body="The Ring was forged in Mount Doom"
        ),
    )

    assert resp.name is None
    assert resp.kind is CodexKind.fact
    assert resp.body == "The Ring was forged in Mount Doom"

    stored = await codex_entries.get_by_id(int(resp.id))
    assert stored is not None
    assert stored.name is None
    assert stored.kind is CodexKind.fact


# ---------------------------------------------------------------------------
# DoD-4 — a fact WITH a name is refused
# ---------------------------------------------------------------------------


# DoD-4 (US-078.AC-2): creating a `fact` with a name is refused with the
# name-not-allowed reason, and nothing is written.
async def test_create_fact_with_name_is_refused__DoD4_US078_AC2(db: DbConfig):
    author = await _seed_user("grace")
    book = await _seed_book(author.id)

    with pytest.raises(CodexError) as exc:
        await codex_service.create_entry(
            _access(book.id, author.id),
            author,
            CreateCodexEntryRequest(
                kind=CodexKind.fact, name="Not allowed", body="a fact"
            ),
        )
    assert exc.value.reason == CodexErrorReason.name_not_allowed

    assert await codex_entries.list_by_book(book.id, include_archived=True) == []


# ---------------------------------------------------------------------------
# DoD-5 — free mode: owner's AND co-author's create apply immediately
# ---------------------------------------------------------------------------


# DoD-5 (US-079.AC-1): in a free-mode book, the OWNER's create applies
# immediately -- the entry is readable straight after the call.
async def test_free_mode_owner_create_applies_immediately__DoD5_US079_AC1(
    db: DbConfig,
):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id, CollaborationMode.free)
    access = _access(
        book.id,
        owner.id,
        role=AccessRole.owner,
        collaboration_mode=CollaborationMode.free,
    )

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Owned", body="owner body"
        ),
    )

    read_back = await codex_service.get_entry(access, created.id)
    assert read_back.id == created.id
    assert read_back.name == "Owned"
    assert read_back.body == "owner body"


# DoD-5 (US-079.AC-1): in a free-mode book, a CO-AUTHOR's create applies
# immediately too -- the entry is readable straight after the call, authored by
# the co-author.
async def test_free_mode_co_author_create_applies_immediately__DoD5_US079_AC1(
    db: DbConfig,
):
    owner = await _seed_user("owner")
    helper = await _seed_user("helper")
    book = await _seed_book(owner.id, CollaborationMode.free)
    co_access = _access(
        book.id,
        helper.id,
        role=AccessRole.co_author,
        collaboration_mode=CollaborationMode.free,
    )

    created = await codex_service.create_entry(
        co_access,
        helper,
        CreateCodexEntryRequest(
            kind=CodexKind.location, name="Shared Hall", body="co-author body"
        ),
    )

    read_back = await codex_service.get_entry(co_access, created.id)
    assert read_back.body == "co-author body"
    assert read_back.author_id == str(helper.id)

    stored = await codex_entries.get_by_id(int(created.id))
    assert stored is not None
    assert stored.body == "co-author body"


# ---------------------------------------------------------------------------
# DoD-6 — free mode: owner's AND co-author's edit apply immediately
# ---------------------------------------------------------------------------


# DoD-6 (US-079.AC-1): in a free-mode book, the OWNER's edit applies immediately.
async def test_free_mode_owner_edit_applies_immediately__DoD6_US079_AC1(
    db: DbConfig,
):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id, CollaborationMode.free)
    access = _access(
        book.id,
        owner.id,
        role=AccessRole.owner,
        collaboration_mode=CollaborationMode.free,
    )
    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(kind=CodexKind.character, name="Hero", body="v0"),
    )

    updated = await codex_service.update_entry(
        access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name="Hero", body="v1", expected_modified_at=created.modified_at
        ),
    )

    assert updated.body == "v1"
    read_back = await codex_service.get_entry(access, created.id)
    assert read_back.body == "v1"


# DoD-6 (US-079.AC-1): in a free-mode book, a CO-AUTHOR's edit of the owner's
# entry applies immediately.
async def test_free_mode_co_author_edit_applies_immediately__DoD6_US079_AC1(
    db: DbConfig,
):
    owner = await _seed_user("owner")
    helper = await _seed_user("helper")
    book = await _seed_book(owner.id, CollaborationMode.free)
    owner_access = _access(
        book.id,
        owner.id,
        role=AccessRole.owner,
        collaboration_mode=CollaborationMode.free,
    )
    co_access = _access(
        book.id,
        helper.id,
        role=AccessRole.co_author,
        collaboration_mode=CollaborationMode.free,
    )
    created = await codex_service.create_entry(
        owner_access,
        owner,
        CreateCodexEntryRequest(kind=CodexKind.character, name="Hero", body="v0"),
    )

    updated = await codex_service.update_entry(
        co_access,
        helper,
        created.id,
        UpdateCodexEntryRequest(
            name="Hero rewritten",
            body="co-author edit",
            expected_modified_at=created.modified_at,
        ),
    )

    assert updated.name == "Hero rewritten"
    assert updated.body == "co-author edit"

    stored = await codex_entries.get_by_id(int(created.id))
    assert stored is not None
    assert stored.body == "co-author edit"


# ---------------------------------------------------------------------------
# DoD-7 — proposal mode: a co-author's CREATE is refused, naming FEAT-010
# ---------------------------------------------------------------------------


# DoD-7 (decision 3; US-079.AC-2 knowingly unmet): in a proposal-mode book a
# CO-AUTHOR's create is refused with the proposal-unsupported reason, nothing is
# written, and the error message names FEAT-010.
async def test_proposal_mode_co_author_create_refused__DoD7_US079_AC2(db: DbConfig):
    owner = await _seed_user("owner")
    helper = await _seed_user("helper")
    book = await _seed_book(owner.id, CollaborationMode.proposal)
    co_access = _access(
        book.id,
        helper.id,
        role=AccessRole.co_author,
        collaboration_mode=CollaborationMode.proposal,
    )

    with pytest.raises(CodexError) as exc:
        await codex_service.create_entry(
            co_access,
            helper,
            CreateCodexEntryRequest(
                kind=CodexKind.character, name="Proposed", body="should not land"
            ),
        )

    assert exc.value.reason == CodexErrorReason.proposal_mode_unsupported
    assert "FEAT-010" in exc.value.message

    # Nothing was written.
    assert await codex_entries.list_by_book(book.id, include_archived=True) == []


# ---------------------------------------------------------------------------
# DoD-8 — proposal mode: a co-author's EDIT is refused, entry unchanged
# ---------------------------------------------------------------------------


# DoD-8 (decision 3): in a proposal-mode book a CO-AUTHOR's edit is refused with
# the proposal-unsupported reason and the entry is unchanged.
async def test_proposal_mode_co_author_edit_refused__DoD8_US079_AC2(db: DbConfig):
    owner = await _seed_user("owner")
    helper = await _seed_user("helper")
    book = await _seed_book(owner.id, CollaborationMode.proposal)
    owner_access = _access(
        book.id,
        owner.id,
        role=AccessRole.owner,
        collaboration_mode=CollaborationMode.proposal,
    )
    co_access = _access(
        book.id,
        helper.id,
        role=AccessRole.co_author,
        collaboration_mode=CollaborationMode.proposal,
    )
    created = await codex_service.create_entry(
        owner_access,
        owner,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Untouched", body="original body"
        ),
    )

    with pytest.raises(CodexError) as exc:
        await codex_service.update_entry(
            co_access,
            helper,
            created.id,
            UpdateCodexEntryRequest(
                name="Rewritten",
                body="should not land",
                expected_modified_at=created.modified_at,
            ),
        )

    assert exc.value.reason == CodexErrorReason.proposal_mode_unsupported
    assert "FEAT-010" in exc.value.message

    stored = await codex_entries.get_by_id(int(created.id))
    assert stored is not None
    assert stored.name == "Untouched"
    assert stored.body == "original body"
    assert stored.modified_by is None
    assert await codex_entry_versions.list_by_entry(int(created.id)) == []


# ---------------------------------------------------------------------------
# DoD-9 — proposal mode: the OWNER's create and edit still apply
# ---------------------------------------------------------------------------


# DoD-9 (decision 3): in a proposal-mode book the OWNER's create and edit still
# apply -- the mode rule branches on the co-author role, not on "not owner".
async def test_proposal_mode_owner_create_and_edit_apply__DoD9_US079_AC1(
    db: DbConfig,
):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id, CollaborationMode.proposal)
    owner_access = _access(
        book.id,
        owner.id,
        role=AccessRole.owner,
        collaboration_mode=CollaborationMode.proposal,
    )

    created = await codex_service.create_entry(
        owner_access,
        owner,
        CreateCodexEntryRequest(kind=CodexKind.fact, name=None, body="a fact"),
    )
    assert created.body == "a fact"

    updated = await codex_service.update_entry(
        owner_access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name=None, body="an amended fact", expected_modified_at=created.modified_at
        ),
    )
    assert updated.body == "an amended fact"

    stored = await codex_entries.get_by_id(int(created.id))
    assert stored is not None
    assert stored.body == "an amended fact"


# ---------------------------------------------------------------------------
# DoD-10 — an edit writes exactly one version row carrying the PRIOR content
# ---------------------------------------------------------------------------


# DoD-10 (UC-070 postcondition; domain-codex.md): an edit writes exactly one
# CodexEntryVersion whose name, body and kind are the entry's content AS IT STOOD
# BEFORE the edit -- never the new content. Create writes no version row.
async def test_edit_writes_one_version_with_prior_content__DoD10_UC070(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Old Name", body="old body"
        ),
    )
    entry_id = int(created.id)

    # No version row is written on create -- the first version row records the
    # state *before* the first edit.
    assert await codex_entry_versions.list_by_entry(entry_id) == []

    await codex_service.update_entry(
        access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name="New Name", body="new body", expected_modified_at=created.modified_at
        ),
    )

    versions = await codex_entry_versions.list_by_entry(entry_id)
    assert len(versions) == 1
    version = versions[0]
    assert version.name == "Old Name"
    assert version.body == "old body"
    assert version.kind is CodexKind.character
    assert version.entry_id == entry_id
    # "Who produced that version" -- the acting user of the edit that supersedes
    # this content (002.context.md).
    assert version.author_id == owner.id

    # And the entry itself now carries the NEW content.
    stored = await codex_entries.get_by_id(entry_id)
    assert stored is not None
    assert stored.name == "New Name"
    assert stored.body == "new body"


# DoD-10 (UC-070 postcondition): the prior content captured is the content at the
# time of THAT edit -- a second edit's version row carries the first edit's
# content, not the original.
async def test_second_edit_version_carries_first_edits_content__DoD10_UC070(
    db: DbConfig,
):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(kind=CodexKind.location, name="n0", body="b0"),
    )
    first = await codex_service.update_entry(
        access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name="n1", body="b1", expected_modified_at=created.modified_at
        ),
    )
    await codex_service.update_entry(
        access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name="n2", body="b2", expected_modified_at=first.modified_at
        ),
    )

    versions = await codex_entry_versions.list_by_entry(int(created.id))
    assert len(versions) == 2
    assert [(v.name, v.body) for v in versions] == [("n0", "b0"), ("n1", "b1")]
    assert {v.kind for v in versions} == {CodexKind.location}


# ---------------------------------------------------------------------------
# DoD-11 — generations are 1-based and increment by one per edit
# ---------------------------------------------------------------------------


# DoD-11 (UC-070 postcondition): three edits produce version generations 1, 2, 3
# -- 1-based, incrementing by one, each row carrying the content superseded by
# that edit.
async def test_three_edits_produce_generations_1_2_3__DoD11_UC070(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    current = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(kind=CodexKind.character, name="Gen", body="v0"),
    )
    for body in ("v1", "v2", "v3"):
        current = await codex_service.update_entry(
            access,
            owner,
            current.id,
            UpdateCodexEntryRequest(
                name="Gen", body=body, expected_modified_at=current.modified_at
            ),
        )

    versions = await codex_entry_versions.list_by_entry(int(current.id))
    assert [v.generation for v in versions] == [1, 2, 3]
    assert [v.body for v in versions] == ["v0", "v1", "v2"]
    assert current.body == "v3"


# DoD-11 (UC-070 postcondition): the very first edit's version row is generation
# 1, not 0.
async def test_first_version_generation_is_one__DoD11_UC070(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(kind=CodexKind.fact, name=None, body="f0"),
    )
    await codex_service.update_entry(
        access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name=None, body="f1", expected_modified_at=created.modified_at
        ),
    )

    versions = await codex_entry_versions.list_by_entry(int(created.id))
    assert [v.generation for v in versions] == [1]


# ---------------------------------------------------------------------------
# DoD-12 — an edit sets modified_by; author_id stays the original creator
# ---------------------------------------------------------------------------


# DoD-12 (domain-codex.md): an edit sets modified_by to the EDITING user and
# leaves author_id at the ORIGINAL creator.
async def test_edit_sets_modified_by_and_keeps_author__DoD12_UC070(db: DbConfig):
    owner = await _seed_user("owner")
    helper = await _seed_user("helper")
    book = await _seed_book(owner.id)
    owner_access = _access(book.id, owner.id, role=AccessRole.owner)
    co_access = _access(book.id, helper.id, role=AccessRole.co_author)

    created = await codex_service.create_entry(
        owner_access,
        owner,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Shared", body="original"
        ),
    )
    assert created.author_id == str(owner.id)

    updated = await codex_service.update_entry(
        co_access,
        helper,
        created.id,
        UpdateCodexEntryRequest(
            name="Shared",
            body="edited by the co-author",
            expected_modified_at=created.modified_at,
        ),
    )

    assert updated.modified_by == str(helper.id)
    assert updated.author_id == str(owner.id)

    stored = await codex_entries.get_by_id(int(created.id))
    assert stored is not None
    assert stored.modified_by == helper.id
    assert stored.author_id == owner.id


# ---------------------------------------------------------------------------
# DoD-13 — a stale expected modified_at is refused; nothing is written
# ---------------------------------------------------------------------------


# DoD-13 (frontend-workspace.md -> stale-buffer / 409): an edit whose expected
# modified_at does not match the stored value is refused with the stale reason,
# no version row is written, and the entry is unchanged.
async def test_stale_modified_at_is_refused__DoD13_UC070(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Stable", body="original body"
        ),
    )
    entry_id = int(created.id)
    # A value guaranteed to differ from whatever is stored.
    stale = (created.modified_at or datetime(2000, 1, 1)) - timedelta(days=1)

    with pytest.raises(CodexError) as exc:
        await codex_service.update_entry(
            access,
            owner,
            created.id,
            UpdateCodexEntryRequest(
                name="Clobbered",
                body="should not land",
                expected_modified_at=stale,
            ),
        )
    assert exc.value.reason == CodexErrorReason.stale_modified_at

    # No version row.
    assert await codex_entry_versions.list_by_entry(entry_id) == []
    # The entry is unchanged.
    stored = await codex_entries.get_by_id(entry_id)
    assert stored is not None
    assert stored.name == "Stable"
    assert stored.body == "original body"
    assert stored.modified_by is None


# DoD-13: once the entry HAS been edited, a null expected modified_at no longer
# matches the stored value and is refused as stale -- an omitted/null value must
# not silently pass the staleness check.
async def test_null_expected_modified_at_is_stale_after_an_edit__DoD13_UC070(
    db: DbConfig,
):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(kind=CodexKind.location, name="Keep", body="b0"),
    )
    first = await codex_service.update_entry(
        access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name="Keep", body="b1", expected_modified_at=created.modified_at
        ),
    )
    assert first.modified_at is not None

    with pytest.raises(CodexError) as exc:
        await codex_service.update_entry(
            access,
            owner,
            created.id,
            UpdateCodexEntryRequest(
                name="Keep", body="b2", expected_modified_at=None
            ),
        )
    assert exc.value.reason == CodexErrorReason.stale_modified_at

    stored = await codex_entries.get_by_id(int(created.id))
    assert stored is not None
    assert stored.body == "b1"
    assert len(await codex_entry_versions.list_by_entry(int(created.id))) == 1


# DoD-13: a second edit reusing the FIRST edit's now-superseded modified_at is
# refused -- the classic lost-update the check exists to prevent.
async def test_reusing_a_superseded_modified_at_is_refused__DoD13_UC070(
    db: DbConfig,
):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(kind=CodexKind.character, name="Race", body="b0"),
    )
    await codex_service.update_entry(
        access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name="Race", body="b1", expected_modified_at=created.modified_at
        ),
    )

    # Second writer still holds the pre-first-edit value.
    with pytest.raises(CodexError) as exc:
        await codex_service.update_entry(
            access,
            owner,
            created.id,
            UpdateCodexEntryRequest(
                name="Race",
                body="b2-lost-update",
                expected_modified_at=created.modified_at,
            ),
        )
    assert exc.value.reason == CodexErrorReason.stale_modified_at

    stored = await codex_entries.get_by_id(int(created.id))
    assert stored is not None
    assert stored.body == "b1"
    assert len(await codex_entry_versions.list_by_entry(int(created.id))) == 1


# ---------------------------------------------------------------------------
# DoD-14 — an archived entry is read-only
# ---------------------------------------------------------------------------


# DoD-14 (UC-070 precondition): editing an archived entry is refused with the
# archived reason; the entry is unchanged and no version row is written.
async def test_edit_of_archived_entry_is_refused__DoD14_UC070(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)
    row = await _seed_entry_row(
        book.id,
        owner.id,
        kind=CodexKind.character,
        name="Retired",
        body="put away",
        archived=True,
    )

    with pytest.raises(CodexError) as exc:
        await codex_service.update_entry(
            access,
            owner,
            str(row.id),
            UpdateCodexEntryRequest(
                name="Revived",
                body="should not land",
                expected_modified_at=row.modified_at,
            ),
        )
    assert exc.value.reason == CodexErrorReason.entry_archived

    stored = await codex_entries.get_by_id(row.id)
    assert stored is not None
    assert stored.name == "Retired"
    assert stored.body == "put away"
    assert await codex_entry_versions.list_by_entry(row.id) == []


# ---------------------------------------------------------------------------
# DoD-15 — listing applies the filters and returns string ids
# ---------------------------------------------------------------------------


# DoD-15 (UC-071 / US-080.AC-1): list_entries applies the kind filter and returns
# only that kind, scoped to the access context's book.
async def test_list_applies_kind_filter__DoD15_US080_AC1(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    other_book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    await _seed_entry_row(
        book.id, owner.id, kind=CodexKind.character, name="Aragorn", body="a ranger"
    )
    await _seed_entry_row(
        book.id, owner.id, kind=CodexKind.character, name="Boromir", body="a captain"
    )
    await _seed_entry_row(
        book.id, owner.id, kind=CodexKind.location, name="Rivendell", body="a valley"
    )
    await _seed_entry_row(
        book.id, owner.id, kind=CodexKind.fact, name=None, body="a recorded fact"
    )
    # Another book's character must never appear.
    await _seed_entry_row(
        other_book.id,
        owner.id,
        kind=CodexKind.character,
        name="Stranger",
        body="elsewhere",
    )

    listed = await codex_service.list_entries(access, kind=CodexKind.character)

    assert {item.name for item in listed.items} == {"Aragorn", "Boromir"}
    assert {item.kind for item in listed.items} == {CodexKind.character}
    assert {item.book_id for item in listed.items} == {str(book.id)}


# DoD-15 (UC-071 / US-080.AC-1): list_entries applies the needle filter as a
# substring over name OR body (case-insensitively, per feature decision 2).
async def test_list_applies_needle_filter__DoD15_US080_AC1(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    await _seed_entry_row(
        book.id,
        owner.id,
        kind=CodexKind.character,
        name="Aragorn",
        body="a ranger of the north",
    )
    await _seed_entry_row(
        book.id,
        owner.id,
        kind=CodexKind.location,
        name="Rivendell",
        body="a hidden valley refuge",
    )
    await _seed_entry_row(
        book.id,
        owner.id,
        kind=CodexKind.fact,
        name=None,
        body="The Ring was forged in Mount Doom",
    )

    by_name = await codex_service.list_entries(access, needle="Aragorn")
    assert {item.name for item in by_name.items} == {"Aragorn"}

    by_body = await codex_service.list_entries(access, needle="hidden valley")
    assert {item.name for item in by_body.items} == {"Rivendell"}

    # A null-named fact is still matched on its body alone.
    null_named = await codex_service.list_entries(access, needle="Mount Doom")
    assert len(null_named.items) == 1
    assert null_named.items[0].name is None
    assert null_named.items[0].kind is CodexKind.fact

    # Case-insensitive substring (feature context decision 2).
    lowered = await codex_service.list_entries(access, needle="ragorn")
    assert {item.name for item in lowered.items} == {"Aragorn"}

    # No needle does not narrow.
    everything = await codex_service.list_entries(access)
    assert len(everything.items) == 3


# DoD-15 (UC-071 / US-080.AC-1): archived entries are excluded unless
# include_archived is asked for, and the filters compose.
async def test_list_applies_include_archived_filter__DoD15_US080_AC1(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    await _seed_entry_row(
        book.id, owner.id, kind=CodexKind.character, name="Active", body="in play"
    )
    await _seed_entry_row(
        book.id,
        owner.id,
        kind=CodexKind.character,
        name="Retired",
        body="put away",
        archived=True,
    )

    default_listed = await codex_service.list_entries(access)
    assert {item.name for item in default_listed.items} == {"Active"}

    with_archived = await codex_service.list_entries(access, include_archived=True)
    assert {item.name for item in with_archived.items} == {"Active", "Retired"}
    assert {item.archived for item in with_archived.items} == {False, True}

    # Composed with the kind filter.
    composed = await codex_service.list_entries(
        access, kind=CodexKind.character, include_archived=True
    )
    assert {item.name for item in composed.items} == {"Active", "Retired"}


# DoD-15 (UC-071 / US-080.AC-1): every id in a list DTO is a STRING -- id,
# book_id, author_id and (when set) modified_by.
async def test_list_dto_ids_are_strings__DoD15_US080_AC1(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    access = _access(book.id, owner.id)

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(kind=CodexKind.character, name="Ids", body="b0"),
    )
    await codex_service.update_entry(
        access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name="Ids", body="b1", expected_modified_at=created.modified_at
        ),
    )

    listed = await codex_service.list_entries(access)

    assert len(listed.items) == 1
    item = listed.items[0]
    assert isinstance(item.id, str)
    assert isinstance(item.book_id, str)
    assert isinstance(item.author_id, str)
    assert isinstance(item.modified_by, str)
    assert item.id == created.id
    assert item.book_id == str(book.id)
    assert item.author_id == str(owner.id)
    assert item.modified_by == str(owner.id)


# ---------------------------------------------------------------------------
# DoD-16 — another book's entry is not-found
# ---------------------------------------------------------------------------


# DoD-16 (US-085.AC-1): getting an entry that exists but belongs to ANOTHER book
# raises the not-found reason -- it never returns another book's content.
async def test_get_entry_of_another_book_is_not_found__DoD16_US085_AC1(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    other_book = await _seed_book(owner.id)
    foreign = await _seed_entry_row(
        other_book.id,
        owner.id,
        kind=CodexKind.character,
        name="Secret",
        body="another book's content",
    )

    with pytest.raises(CodexError) as exc:
        await codex_service.get_entry(_access(book.id, owner.id), str(foreign.id))
    assert exc.value.reason == CodexErrorReason.entry_not_found


# DoD-16 (US-085.AC-1): an unknown entry id also raises the not-found reason.
async def test_get_unknown_entry_is_not_found__DoD16_US085_AC1(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)

    with pytest.raises(CodexError) as exc:
        await codex_service.get_entry(_access(book.id, owner.id), "999999999")
    assert exc.value.reason == CodexErrorReason.entry_not_found


# DoD-16 (US-085.AC-1): updating another book's entry is likewise not-found, and
# that entry is left untouched.
async def test_update_entry_of_another_book_is_not_found__DoD16_US085_AC1(
    db: DbConfig,
):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    other_book = await _seed_book(owner.id)
    foreign = await _seed_entry_row(
        other_book.id,
        owner.id,
        kind=CodexKind.character,
        name="Secret",
        body="another book's content",
    )

    with pytest.raises(CodexError) as exc:
        await codex_service.update_entry(
            _access(book.id, owner.id),
            owner,
            str(foreign.id),
            UpdateCodexEntryRequest(
                name="Leak",
                body="should not land",
                expected_modified_at=foreign.modified_at,
            ),
        )
    assert exc.value.reason == CodexErrorReason.entry_not_found

    stored = await codex_entries.get_by_id(foreign.id)
    assert stored is not None
    assert stored.name == "Secret"
    assert stored.body == "another book's content"


# ---------------------------------------------------------------------------
# DoD-17 — reader / non-member refused by authz on all four calls
# ---------------------------------------------------------------------------


# DoD-17 (US-085.AC-1): a `reader` and a non-member (`none`) access context are
# refused by authz.require -- raising BookAuthorizationError -- on every one of
# create, list, get and update.
@pytest.mark.parametrize("role", [AccessRole.reader, AccessRole.none])
async def test_non_member_roles_refused_on_every_call__DoD17_US085_AC1(
    db: DbConfig, role: AccessRole
):
    owner = await _seed_user("owner")
    outsider = await _seed_user("outsider")
    book = await _seed_book(owner.id)
    entry = await _seed_entry_row(
        book.id, owner.id, kind=CodexKind.character, name="Private", body="members only"
    )
    denied = _access(book.id, outsider.id, role=role)

    with pytest.raises(BookAuthorizationError):
        await codex_service.create_entry(
            denied,
            outsider,
            CreateCodexEntryRequest(
                kind=CodexKind.character, name="Intruder", body="should not land"
            ),
        )

    with pytest.raises(BookAuthorizationError):
        await codex_service.list_entries(denied)

    with pytest.raises(BookAuthorizationError):
        await codex_service.get_entry(denied, str(entry.id))

    with pytest.raises(BookAuthorizationError):
        await codex_service.update_entry(
            denied,
            outsider,
            str(entry.id),
            UpdateCodexEntryRequest(
                name="Intruder",
                body="should not land",
                expected_modified_at=entry.modified_at,
            ),
        )

    # Nothing the refused caller attempted reached the database.
    stored = await codex_entries.get_by_id(entry.id)
    assert stored is not None
    assert stored.name == "Private"
    assert stored.body == "members only"
    assert await codex_entry_versions.list_by_entry(entry.id) == []
    assert len(await codex_entries.list_by_book(book.id, include_archived=True)) == 1
