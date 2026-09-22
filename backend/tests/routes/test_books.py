"""End-to-end tests for the book create + list HTTP surface (feature 009, step 003).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). The app's startup
lifespan runs against a throwaway temp DB; each test seeds its own author users
on the same process-global engine the app uses (schema built with `init_db`,
readiness flipped with `set_db_ready(True)`), mirroring
tests/routes/admin/test_llm_servers.py's `_seed_user` / `_auth_header` helpers.
The autouse `_reset_db_ready` fixture (conftest) restores the cold-boot readiness
default before each test.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 003):

    app.routes.books  (router prefix "/api/books", each endpoint gated by
      Depends(auth_service.get_current_user) -- author-scoped, NOT the admin
      require_role gate):
        POST ""        (CreateBookRequest {title, description,
                        collaboration_mode, visibility}) -> 201, BookResponse
        GET  ""        -> 200, BookListResponse {items:[BookResponse,...]}  (owned)
        GET  "/shared" -> 200, BookListResponse {items:[BookResponse,...]}  (shared)

    app.models.schemas.books (frozen step 003):
        BookResponse    -- id: str, owner_id: str, title, description,
                           collaboration_mode, visibility, state, created_at,
                           modified_at.  ids are STRINGS (snowflake-as-string).
        BookListResponse -- items: list[BookResponse].

Seeding facts (feature 009 context + step 003 context):
    CollaborationMode {free, proposal}; Visibility {private, public};
    BookState {active, archived, quarantined, destroyed}.  A create defaults
    state -> active.  Owner is the scalar Book.owner_id (NOT a BookMember row).
    A SHARED book is seeded by creating a book owned by author A (via POST), then
    inserting a BookMember row (role=MemberRole.co_author) linking author B via
    the db layer (`db/book_members.create`) -- per the step 003 briefing.

Expected values come from the SPEC ONLY -- the step DoD (DoD-1..DoD-7), the step
Interface intent, and the cited US-###.AC-# acceptance criteria -- never from
implementation internals.

Async tests use asyncio_mode = "auto".
"""

import datetime

from app.db import book_members, users
from app.db.engine import init_db, set_db_ready
from app.models.book_member import BookMember, MemberRole
from app.models.schemas.books import BookListResponse, BookResponse
from app.models.user import User, UserRole
from app.services import auth

BASE = "/api/books"
SHARED_URL = f"{BASE}/shared"


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

    Mirrors tests/routes/admin/test_llm_servers.py's `_seed_user`: builds the
    schema (`init_db`, idempotent), creates the user with a real bcrypt pwdhash
    and a per-user signing key, then flips readiness True. Returns the created
    `User` so the caller can mint an access token for it.
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

    Per the step 003 briefing: a shared book is a book owned by A with a
    BookMember (role=MemberRole.co_author) linking B; the owner has no member
    row, so this is how the shared relationship is established for the test.
    """
    await book_members.create(
        BookMember(
            book_id=book_id,
            user_id=user_id,
            role=MemberRole.co_author,
            created_at=_now(),
        )
    )


# DoD-1 (US-022.AC-1): POST /api/books with a chosen collaboration_mode and
# visibility returns 201 and the created book reflects BOTH requested values.
async def test_create_reflects_mode_and_visibility__DoD1_US022_AC1(http_client):
    _author, token = await _seed_author("alice")

    created = await _create_book(
        http_client,
        token,
        collaboration_mode="proposal",
        visibility="public",
    )
    BookResponse.model_validate(created)
    assert created["collaboration_mode"] == "proposal"
    assert created["visibility"] == "public"


# DoD-2 (US-022.AC-2): POST /api/books sets the caller as the book's owner --
# the response owner_id equals the caller's id (as a string).
async def test_create_sets_caller_as_owner__DoD2_US022_AC2(http_client):
    author, token = await _seed_author("bob")

    created = await _create_book(http_client, token)
    assert created["owner_id"] == str(author.id)


# DoD-3 (UC-021 postcondition): a created book defaults to state == "active".
async def test_create_defaults_state_active__DoD3(http_client):
    _author, token = await _seed_author("carol")

    created = await _create_book(http_client, token)
    assert created["state"] == "active"


# DoD-4 (authorization taxonomy: no anonymous book surface): POST /api/books
# without a valid token -> 401.
async def test_create_without_token_401__DoD4(http_client):
    resp = await http_client.post(
        BASE,
        json={
            "title": "No Auth",
            "description": "should be rejected",
            "collaboration_mode": "free",
            "visibility": "private",
        },
    )
    assert resp.status_code == 401


# DoD-5 (US-023.AC-1): GET /api/books returns EXACTLY the books the caller owns
# and none owned by another author.
async def test_list_owned_exactly_owned__DoD5_US023_AC1(http_client):
    author_a, token_a = await _seed_author("dave")
    _author_b, token_b = await _seed_author("erin")

    mine = await _create_book(http_client, token_a, title="Dave's Book")
    others = await _create_book(http_client, token_b, title="Erin's Book")

    resp = await http_client.get(BASE, headers=_auth_header(token_a))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    BookListResponse.model_validate(body)

    ids = [item["id"] for item in body["items"]]
    assert mine["id"] in ids
    assert others["id"] not in ids
    # exactly owned: every returned book is owned by the caller.
    for item in body["items"]:
        assert item["owner_id"] == str(author_a.id)


# DoD-6 (US-031.AC-1): GET /api/books/shared returns EXACTLY the books where the
# caller is a co-author and NOT the owner -- excluding books they own and books
# they have no relationship to.
async def test_list_shared_exactly_shared__DoD6_US031_AC1(http_client):
    author_a, token_a = await _seed_author("frank")
    author_b, token_b = await _seed_author("grace")

    # Book X: owned by A, B is a co-author -> should appear in B's shared list.
    shared_book = await _create_book(http_client, token_a, title="Shared X")
    await _add_co_author(int(shared_book["id"]), author_b.id)

    # Book Y: owned by B (no member row) -> owned, must NOT appear in B's shared.
    owned_by_b = await _create_book(http_client, token_b, title="B's Own Y")

    # Book Z: owned by A, B has no relationship -> must NOT appear in B's shared.
    unrelated = await _create_book(http_client, token_a, title="Unrelated Z")

    resp = await http_client.get(SHARED_URL, headers=_auth_header(token_b))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    BookListResponse.model_validate(body)

    ids = [item["id"] for item in body["items"]]
    assert shared_book["id"] in ids
    assert owned_by_b["id"] not in ids
    assert unrelated["id"] not in ids
    # none returned in the shared list is owned by the caller.
    for item in body["items"]:
        assert item["owner_id"] != str(author_b.id)


# DoD-7 (API typing convention: snowflake-as-string): response DTO ids (`id`,
# `owner_id`) are JSON strings -- on the create result and on list items.
async def test_response_ids_are_json_strings__DoD7(http_client):
    author, token = await _seed_author("heidi")

    created = await _create_book(http_client, token)
    assert type(created["id"]) is str
    assert type(created["owner_id"]) is str

    resp = await http_client.get(BASE, headers=_auth_header(token))
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert type(item["id"]) is str
        assert type(item["owner_id"]) is str
