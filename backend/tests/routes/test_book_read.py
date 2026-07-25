"""End-to-end tests for the book read-projection HTTP surface (feature 009, step 004).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). Each test seeds its
own author users on the same process-global engine the app uses (schema built
with `init_db`, readiness flipped with `set_db_ready(True)`), mirroring
tests/routes/test_books.py's `_seed_user` / `_auth_header` / `_create_book` /
`_add_co_author` helpers. The autouse `_reset_db_ready` fixture (conftest)
restores the cold-boot readiness default before each test.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 004):

    app.routes.books  (router prefix "/api/books"), two new GET routes, both
      gated by Depends(authz.book_access) which yields 401 (no token) and 404
      (missing / private non-member) upstream:
        GET "/{book_id}"       -> 200, BookDetailResponse  (owner/co-author only)
        GET "/{book_id}/read"  -> 200, ReaderBookResponse  (owner/co-author/reader)

    app.models.schemas.books (frozen step 004):
        BookMemberResponse -- user_id: str, role: MemberRole,
                              created_at: datetime | None.
        BookDetailResponse(BookResponse) -- inherits BookResponse fields
                              (id, owner_id, title, description,
                              collaboration_mode, visibility, state, created_at,
                              modified_at) + members: list[BookMemberResponse].
        ReaderBookResponse -- title: str, chapters: list[str]  (chapters is the
                              empty placeholder TOC; carries NO members-only
                              surface -- exclusion enforced structurally).

Seeding facts (feature 009 context + step 004 context):
    Visibility {private, public}; a book's visibility is chosen at create time
    (POST body). Owner is the scalar Book.owner_id (NOT a BookMember row); a
    co-author is a BookMember row (role=MemberRole.co_author) inserted via the db
    layer; a reader of a PUBLIC book is any logged-in non-member (no row).

    Status taxonomy the two routes exercise:
        401 -- no token (the book_access dependency via get_current_user).
        404 -- private book, non-member caller (resolve_book_access existence
               hiding) -- the service is never reached.
        403 -- member-detail requested by a public-book reader
               (authz.require(view_book_detail) denial, mapped by the route).

Expected values come from the SPEC ONLY -- the step DoD (DoD-1..DoD-7), the step
Interface intent, and the cited US-###.AC-# acceptance criteria -- never from
implementation internals.

Async tests use asyncio_mode = "auto".
"""

import datetime

from app.db import book_members, users
from app.db.engine import init_db, set_db_ready
from app.models.book_member import BookMember, MemberRole
from app.models.schemas.books import BookDetailResponse, ReaderBookResponse
from app.models.user import User, UserRole
from app.services import auth

BASE = "/api/books"


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_user(
    *,
    username: str,
    password: str = "password123",
    role: UserRole = UserRole.author,
) -> User:
    """Seed a persisted author on the app's engine and mark the instance ready.

    Mirrors tests/routes/test_books.py's `_seed_user`: builds the schema
    (`init_db`, idempotent), creates the user with a real bcrypt pwdhash and a
    per-user signing key, then flips readiness True. Returns the created `User`
    so the caller can mint an access token for it.
    """
    await init_db()
    user = await users.create(
        User(
            username=username,
            role=role,
            pwdhash=auth.hash_password(password),
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )
    set_db_ready(True)
    return user


async def _seed_author(username: str) -> tuple[User, str]:
    """Seed an author caller and return (user, access token)."""
    user = await _seed_user(username=username, role=UserRole.author)
    return user, auth.create_access_token(user)


async def _create_book(
    http_client,
    token: str,
    *,
    title: str = "A Book",
    description: str = "a description",
    collaboration_mode: str = "free",
    visibility: str = "private",
) -> dict:
    """POST a book via the route as the token's caller; return the 201 body."""
    resp = await http_client.post(
        BASE,
        headers=_auth_header(token),
        json={
            "title": title,
            "description": description,
            "collaboration_mode": collaboration_mode,
            "visibility": visibility,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _add_co_author(book_id: int, user_id: int) -> None:
    """Insert a co-author BookMember row directly through the db layer.

    The owner has no member row, so a co-author relationship is established by
    inserting a BookMember (role=MemberRole.co_author) linking the user to the
    book -- mirroring tests/routes/test_books.py's `_add_co_author`.
    """
    await book_members.create(
        BookMember(
            book_id=book_id,
            user_id=user_id,
            role=MemberRole.co_author,
            created_at=_now(),
        )
    )


# ---------------------------------------------------------------------------
# DoD-1 (US-029.AC-2): GET /api/books/{book_id} returns 200 with the book fields
# and its `members` list for the OWNER and for a CO-AUTHOR of a PRIVATE book.
# ---------------------------------------------------------------------------
async def test_owner_gets_detail_of_private_book__DoD1_US029_AC2(http_client):
    owner, owner_token = await _seed_author("alice")
    co_author, _co_token = await _seed_author("bob")

    book = await _create_book(http_client, owner_token, visibility="private")
    await _add_co_author(int(book["id"]), co_author.id)

    resp = await http_client.get(
        f"{BASE}/{book['id']}", headers=_auth_header(owner_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    BookDetailResponse.model_validate(body)

    assert body["id"] == book["id"]
    assert body["owner_id"] == str(owner.id)
    assert body["visibility"] == "private"
    # members list carries the co-author (owner is NOT a member row).
    member_ids = [m["user_id"] for m in body["members"]]
    assert str(co_author.id) in member_ids


async def test_co_author_gets_detail_of_private_book__DoD1_US029_AC2(http_client):
    owner, owner_token = await _seed_author("carol")
    co_author, co_token = await _seed_author("dave")

    book = await _create_book(http_client, owner_token, visibility="private")
    await _add_co_author(int(book["id"]), co_author.id)

    resp = await http_client.get(
        f"{BASE}/{book['id']}", headers=_auth_header(co_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    BookDetailResponse.model_validate(body)

    assert body["id"] == book["id"]
    member_ids = [m["user_id"] for m in body["members"]]
    assert str(co_author.id) in member_ids


# ---------------------------------------------------------------------------
# DoD-2 (US-030.AC-3, existence hiding): GET /api/books/{book_id} -> 404 for a
# logged-in non-member of a PRIVATE book.
# ---------------------------------------------------------------------------
async def test_detail_private_non_member_404__DoD2_US030_AC3(http_client):
    _owner, owner_token = await _seed_author("erin")
    _outsider, outsider_token = await _seed_author("frank")

    book = await _create_book(http_client, owner_token, visibility="private")

    resp = await http_client.get(
        f"{BASE}/{book['id']}", headers=_auth_header(outsider_token)
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# DoD-3 (US-030.AC-2): GET /api/books/{book_id} -> 403 for a logged-in
# non-member reader of a PUBLIC book (member detail is members-only).
# ---------------------------------------------------------------------------
async def test_detail_public_reader_403__DoD3_US030_AC2(http_client):
    _owner, owner_token = await _seed_author("grace")
    _reader, reader_token = await _seed_author("heidi")

    book = await _create_book(http_client, owner_token, visibility="public")

    resp = await http_client.get(
        f"{BASE}/{book['id']}", headers=_auth_header(reader_token)
    )
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# DoD-4 (US-030.AC-1): GET /api/books/{book_id}/read -> 200 reader-safe
# projection for a logged-in non-member of a PUBLIC book.
# ---------------------------------------------------------------------------
async def test_read_public_non_member_200__DoD4_US030_AC1(http_client):
    _owner, owner_token = await _seed_author("ivan")
    _reader, reader_token = await _seed_author("judy")

    book = await _create_book(
        http_client, owner_token, title="Public Read", visibility="public"
    )

    resp = await http_client.get(
        f"{BASE}/{book['id']}/read", headers=_auth_header(reader_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ReaderBookResponse.model_validate(body)
    assert body["title"] == "Public Read"


# ---------------------------------------------------------------------------
# DoD-5 (US-030.AC-2 / UC-029 exclusion list): the ReaderBookResponse JSON
# exposes ONLY `title` + the placeholder `chapters` TOC -- every members-only
# field is ABSENT from the payload.
# ---------------------------------------------------------------------------
async def test_read_projection_excludes_members_only_fields__DoD5_US030_AC2(
    http_client,
):
    _owner, owner_token = await _seed_author("kevin")
    _reader, reader_token = await _seed_author("laura")

    book = await _create_book(
        http_client, owner_token, title="Reader Safe", visibility="public"
    )

    resp = await http_client.get(
        f"{BASE}/{book['id']}/read", headers=_auth_header(reader_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Reader-safe projection exposes EXACTLY title + placeholder TOC/chapters.
    assert set(body.keys()) == {"title", "chapters"}

    # None of the members-only surface leaks into the reader payload.
    for forbidden in (
        "members",
        "owner_id",
        "id",
        "state",
        "visibility",
        "collaboration_mode",
        "description",
        "system_prompt",
        "active_notes",
        "moderation_reason",
        "moderated_by",
        "moderated_at",
    ):
        assert forbidden not in body

    # chapters is the empty-placeholder TOC (shape only -- content is Stage 5).
    assert isinstance(body["chapters"], list)


# ---------------------------------------------------------------------------
# DoD-6 (US-030.AC-3): GET /api/books/{book_id}/read -> 404 for a logged-in
# non-member of a PRIVATE book.
# ---------------------------------------------------------------------------
async def test_read_private_non_member_404__DoD6_US030_AC3(http_client):
    _owner, owner_token = await _seed_author("mike")
    _outsider, outsider_token = await _seed_author("nina")

    book = await _create_book(http_client, owner_token, visibility="private")

    resp = await http_client.get(
        f"{BASE}/{book['id']}/read", headers=_auth_header(outsider_token)
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# DoD-7 (US-030.AC-4): GET /api/books/{book_id}/read without a valid token
# -> 401 (no anonymous reader surface).
# ---------------------------------------------------------------------------
async def test_read_without_token_401__DoD7_US030_AC4(http_client):
    _owner, owner_token = await _seed_author("oscar")

    book = await _create_book(http_client, owner_token, visibility="public")

    resp = await http_client.get(f"{BASE}/{book['id']}/read")
    assert resp.status_code == 401, resp.text
