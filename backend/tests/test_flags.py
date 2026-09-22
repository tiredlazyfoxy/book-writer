"""Raising and resolving a chapter warning (feature 016.chapter-close-continuity)
— DoD-6.

Bound to the frozen signatures in `status.md` -> `## Skeleton`, in
`app.services.flags`::

    class FlagErrorReason(str, Enum) { not_a_member, book_archived,
                                       chapter_not_found, flag_not_found,
                                       flag_already_resolved }
    class FlagError(Exception)   # carries .reason
    async def list_flags(access: BookAccess, chapter_id: str) -> FlagListResponse
    async def raise_flag(access, chapter_id: str,
                         body: RaiseFlagRequest) -> FlagResponse
    async def resolve_flag(access, chapter_id: str, flag_id: str) -> FlagResponse

with `app.models.schemas.flags.RaiseFlagRequest` / `FlagResponse`, and the
pre-existing frozen `authz.BookAccess` / `AccessRole` / `BookAuthorizationError`.

Every expected value comes from the SPEC — `plan.md` -> Interface + DoD-6 and
Decisions taken D9 — never from implementation internals (US-075.AC-1,
US-076.AC-2, US-077.AC-1, UC-067, UC-068):

  - the capability-matrix rows D9 fixes: `raise_flag` is {owner, co_author}
    (UC-067 names both actors) and `resolve_flag` is {owner} alone (UC-068 names
    the owner only); a reader and a non-member hold neither;
  - a member-raised flag is `origin=person`, `status=open`, attributed to the
    caller;
  - resolving moves `open -> resolved` once, stamping `resolved_by` with the
    caller and `resolved_at` with a time; a second resolve is the
    already-resolved reason.

Async tests use `asyncio_mode = "auto"`; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. Rows are seeded straight through the
sibling `db/` modules and `BookAccess` is built directly, so there is no route, no
client and no network here.
"""

import pytest

from app.db import books, chapters, flags, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chapter import Chapter, ChapterState
from app.models.flag import Flag, FlagOrigin, FlagStatus
from app.models.schemas.flags import FlagResponse, RaiseFlagRequest
from app.models.user import User, UserRole
from app.services import flags as flags_service
from app.services.authz import AccessRole, BookAccess, BookAuthorizationError
from app.services.flags import FlagError, FlagErrorReason

COMMENT = "Halden is described as left-handed here and right-handed in chapter two."

# D9's two matrix rows, as roles.
MAY_RAISE = [AccessRole.owner, AccessRole.co_author]
MAY_NOT_RAISE = [AccessRole.reader, AccessRole.none]
MAY_RESOLVE = [AccessRole.owner]
MAY_NOT_RESOLVE = [AccessRole.co_author, AccessRole.reader, AccessRole.none]


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(owner_id: int, *, state: BookState = BookState.active) -> Book:
    return await books.create(
        Book(
            title="A Book",
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.private,
            state=state,
            system_prompt="",
            active_notes="",
        )
    )


async def _seed_chapter(book_id: int, *, state: ChapterState = ChapterState.open) -> Chapter:
    return await chapters.create(
        Chapter(
            book_id=book_id,
            ordinal=1,
            title="Chapter One",
            state=state,
            sketch="",
            text="the body",
            version=1,
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


async def _seed_open_flag(chapter_id: int, created_by: int) -> Flag:
    return await flags.create(
        Flag(
            chapter_id=chapter_id,
            origin=FlagOrigin.person,
            comment=COMMENT,
            status=FlagStatus.open,
            created_by=created_by,
        )
    )


# ---------------------------------------------------------------------------
# DoD-6 — raising: the matrix row, the origin and the attribution
# ---------------------------------------------------------------------------


# DoD-6 (US-075.AC-1, UC-067, D9): the owner AND a co-author may raise a warning on
# a chapter; the flag they raise is `origin=person` (never `check`), `status=open`,
# and attributed to the caller who raised it.
@pytest.mark.parametrize("role", MAY_RAISE, ids=[r.value for r in MAY_RAISE])
async def test_owner_and_co_author_raise_a_person_flag__DoD6_US075_AC1(
    db: DbConfig, role: AccessRole
):
    owner = await _seed_user(f"raise-owner-{role.value}")
    caller = owner if role == AccessRole.owner else await _seed_user(f"raise-caller-{role.value}")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id)

    result = await flags_service.raise_flag(
        _access(book.id, caller.id, role=role), str(chapter.id), RaiseFlagRequest(comment=COMMENT)
    )

    assert isinstance(result, FlagResponse)
    assert result.chapter_id == str(chapter.id)
    assert result.comment == COMMENT
    # A member's warning is a PERSON flag — the assistant's check flags are the
    # only `check` ones, and only a close run makes those.
    assert result.origin == FlagOrigin.person
    assert result.status == FlagStatus.open
    assert result.created_by == str(caller.id)
    assert result.resolved_by is None
    assert result.resolved_at is None

    stored = await flags.get_by_id(int(result.id))
    assert stored is not None
    assert stored.origin is FlagOrigin.person
    assert stored.status is FlagStatus.open
    assert stored.created_by == caller.id


# DoD-6 (D9): a reader and a non-member hold no `raise_flag` capability — both are
# refused by the authorization error and no flag row is written.
@pytest.mark.parametrize("role", MAY_NOT_RAISE, ids=[r.value for r in MAY_NOT_RAISE])
async def test_reader_and_non_member_cannot_raise__DoD6(db: DbConfig, role: AccessRole):
    owner = await _seed_user(f"raise-refused-owner-{role.value}")
    outsider = await _seed_user(f"raise-refused-caller-{role.value}")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id)

    with pytest.raises(BookAuthorizationError):
        await flags_service.raise_flag(
            _access(book.id, outsider.id, role=role),
            str(chapter.id),
            RaiseFlagRequest(comment=COMMENT),
        )

    assert list(await flags.list_by_chapter(chapter.id)) == []


# ---------------------------------------------------------------------------
# DoD-6 — resolving: owner only, open -> resolved, stamped
# ---------------------------------------------------------------------------


# DoD-6 (US-076.AC-2, US-077.AC-1, UC-068, D9): the OWNER resolves an open warning
# — the flag moves `open -> resolved` and is stamped with who resolved it and
# when. The comment and the raiser's attribution are preserved.
async def test_owner_resolves_an_open_flag_with_a_stamp__DoD6_US076_AC2_US077_AC1(
    db: DbConfig,
):
    owner = await _seed_user("resolve-owner")
    raiser = await _seed_user("resolve-raiser")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id)
    flag = await _seed_open_flag(chapter.id, raiser.id)
    # Presence first: it really is open and unstamped before the resolve.
    assert flag.status is FlagStatus.open
    assert flag.resolved_by is None
    assert flag.resolved_at is None

    result = await flags_service.resolve_flag(
        _access(book.id, owner.id), str(chapter.id), str(flag.id)
    )

    assert isinstance(result, FlagResponse)
    assert result.id == str(flag.id)
    assert result.status == FlagStatus.resolved
    assert result.resolved_by == str(owner.id)
    assert result.resolved_at is not None
    # What was raised is not rewritten by the resolution.
    assert result.comment == COMMENT
    assert result.created_by == str(raiser.id)

    stored = await flags.get_by_id(flag.id)
    assert stored is not None
    assert stored.status is FlagStatus.resolved
    assert stored.resolved_by == owner.id
    assert stored.resolved_at is not None


# DoD-6 (D9): `resolve_flag` is the owner's alone — a co-author, a reader and a
# non-member are all refused by the authorization error, and the flag stays open
# and unstamped. (A co-author MAY raise, so this is the row's own boundary and not
# a blanket refusal of the co-author.)
@pytest.mark.parametrize("role", MAY_NOT_RESOLVE, ids=[r.value for r in MAY_NOT_RESOLVE])
async def test_only_the_owner_may_resolve__DoD6_US076_AC2(
    db: DbConfig, role: AccessRole
):
    owner = await _seed_user(f"resolve-refused-owner-{role.value}")
    caller = await _seed_user(f"resolve-refused-caller-{role.value}")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id)
    flag = await _seed_open_flag(chapter.id, owner.id)

    with pytest.raises(BookAuthorizationError):
        await flags_service.resolve_flag(
            _access(book.id, caller.id, role=role), str(chapter.id), str(flag.id)
        )

    stored = await flags.get_by_id(flag.id)
    assert stored is not None
    assert stored.status is FlagStatus.open
    assert stored.resolved_by is None
    assert stored.resolved_at is None


# DoD-6: the transition runs once — resolving an already-resolved flag is the
# already-resolved reason, and the original stamp is not overwritten.
async def test_resolving_twice_is_refused__DoD6(db: DbConfig):
    owner = await _seed_user("resolve-twice-owner")
    second_owner_access_user = await _seed_user("resolve-twice-other")
    book = await _seed_book(owner.id)
    chapter = await _seed_chapter(book.id)
    flag = await _seed_open_flag(chapter.id, owner.id)

    first = await flags_service.resolve_flag(
        _access(book.id, owner.id), str(chapter.id), str(flag.id)
    )
    assert first.status == FlagStatus.resolved

    with pytest.raises(FlagError) as exc:
        await flags_service.resolve_flag(
            _access(book.id, second_owner_access_user.id),
            str(chapter.id),
            str(flag.id),
        )
    assert exc.value.reason == FlagErrorReason.flag_already_resolved

    stored = await flags.get_by_id(flag.id)
    assert stored is not None
    assert stored.status is FlagStatus.resolved
    # The second caller did not steal the attribution.
    assert stored.resolved_by == owner.id
