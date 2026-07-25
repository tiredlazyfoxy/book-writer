"""End-to-end tests for the owner-only book settings mutations (feature 009, step 005).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). Each test seeds its
own author users on the same process-global engine the app uses (schema built
with `init_db`, readiness flipped with `set_db_ready(True)`), mirroring
tests/routes/test_books.py / test_book_read.py's `_seed_user` / `_seed_author`
/ `_auth_header` / `_create_book` / `_add_co_author` helpers. The autouse
`_reset_db_ready` fixture (conftest) restores the cold-boot readiness default
before each test.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 005):

    app.routes.books  (router prefix "/api/books"), six new mutation routes, each
      gated by Depends(authz.book_access) -> 401 (no token) / 404 (missing or
      private non-member) upstream, then authz.require(<capability>) in the
      service -> BookAuthorizationError mapped to 403 by the route:
        POST   "/{book_id}/archive"            -> 200, BookResponse
        POST   "/{book_id}/unarchive"          -> 200, BookResponse
        POST   "/{book_id}/transfer"           (TransferOwnershipRequest) -> BookResponse
        POST   "/{book_id}/members"            (AddMemberRequest)         -> BookDetailResponse
        DELETE "/{book_id}/members/{user_id}"  -> BookDetailResponse
        PATCH  "/{book_id}/visibility"         (SetVisibilityRequest)     -> BookResponse

    app.models.schemas.books (frozen step 005 request DTOs, target ids as STRING):
        TransferOwnershipRequest -- target_user_id: str
        AddMemberRequest         -- target_user_id: str
        SetVisibilityRequest     -- visibility: Visibility
      Response DTOs (steps 003/004):
        BookResponse       -- id, owner_id (str), title, description,
                              collaboration_mode, visibility, state,
                              created_at, modified_at.
        BookDetailResponse -- BookResponse fields + members: list[BookMemberResponse].
      Content note: BookResponse / BookDetailResponse do NOT expose
      system_prompt / active_notes (excluded per step-004 decision), so
      content-preservation (DoD-2 / DoD-3) is asserted over the exposed content
      fields `title` + `description`.

    Frozen error-status decisions (status.md -> Skeleton -> Step 005):
        transfer to a non-co-author  -> 409 (transfer_target_not_member)
        remove of a non-member       -> 404 (remove_target_not_member)
        owner-only mutation by a co-author caller -> 403 (BookAuthorizationError)

Seeding facts (feature 009 context + step 005 context):
    Visibility {private, public}; a book's visibility is chosen at create time
    (POST body) and flipped via PATCH /visibility. Owner is the scalar
    Book.owner_id (NOT a BookMember row); a co-author is a BookMember row
    (role=MemberRole.co_author) inserted via the db layer. Each test seeds an
    owner author, a co-author (member row), and a third non-member author to
    exercise the owner-only matrix and the transfer/visibility refusals.

Expected values come from the SPEC ONLY -- the step DoD (DoD-1..DoD-10), the
step Interface intent, the frozen skeleton return/error decisions, and the cited
US-###.AC-# acceptance criteria -- never from implementation internals.

Async tests use asyncio_mode = "auto".
"""

import datetime

import pytest

from app.db import book_members, users
from app.db.engine import init_db, set_db_ready
from app.models.book_member import BookMember, MemberRole
from app.models.schemas.books import BookDetailResponse, BookResponse
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
# DoD-1 (US-024.AC-1): POST /{book_id}/archive by the owner sets state -> archived.
# ---------------------------------------------------------------------------
async def test_owner_archive_sets_state_archived__DoD1_US024_AC1(http_client):
    _owner, owner_token = await _seed_author("alice")

    book = await _create_book(http_client, owner_token, visibility="private")

    resp = await http_client.post(
        f"{BASE}/{book['id']}/archive", headers=_auth_header(owner_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    BookResponse.model_validate(body)
    assert body["state"] == "archived"


# ---------------------------------------------------------------------------
# DoD-2 (US-024.AC-2): archiving preserves the book's content -- the exposed
# content fields (title, description) are unchanged by the archive mutation.
# (BookResponse deliberately excludes system_prompt/active_notes, so content
# preservation is asserted over the surface the response exposes.)
# ---------------------------------------------------------------------------
async def test_archive_preserves_content_fields__DoD2_US024_AC2(http_client):
    _owner, owner_token = await _seed_author("bob")

    book = await _create_book(
        http_client,
        owner_token,
        title="Original Title",
        description="Original description",
        visibility="private",
    )

    resp = await http_client.post(
        f"{BASE}/{book['id']}/archive", headers=_auth_header(owner_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    BookResponse.model_validate(body)

    assert body["state"] == "archived"
    assert body["title"] == "Original Title"
    assert body["description"] == "Original description"


# ---------------------------------------------------------------------------
# DoD-3 (US-024.AC-2 / UC-023 reversible): archive -> unarchive round-trip
# returns the book to state == active with content still intact.
# ---------------------------------------------------------------------------
async def test_unarchive_restores_active_content_intact__DoD3_US024_AC2(http_client):
    _owner, owner_token = await _seed_author("carol")

    book = await _create_book(
        http_client,
        owner_token,
        title="Round Trip",
        description="survives the round trip",
        visibility="private",
    )

    archived = await http_client.post(
        f"{BASE}/{book['id']}/archive", headers=_auth_header(owner_token)
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["state"] == "archived"

    resp = await http_client.post(
        f"{BASE}/{book['id']}/unarchive", headers=_auth_header(owner_token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    BookResponse.model_validate(body)

    assert body["state"] == "active"
    assert body["title"] == "Round Trip"
    assert body["description"] == "survives the round trip"


# ---------------------------------------------------------------------------
# DoD-4 (US-025.AC-1): POST /{book_id}/transfer to a current CO-AUTHOR makes that
# co-author the new owner -- owner_id updated to the target's id.
# ---------------------------------------------------------------------------
async def test_transfer_to_co_author_updates_owner__DoD4_US025_AC1(http_client):
    _owner, owner_token = await _seed_author("dave")
    co_author, _co_token = await _seed_author("erin")

    book = await _create_book(http_client, owner_token, visibility="private")
    await _add_co_author(int(book["id"]), co_author.id)

    resp = await http_client.post(
        f"{BASE}/{book['id']}/transfer",
        headers=_auth_header(owner_token),
        json={"target_user_id": str(co_author.id)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    BookResponse.model_validate(body)
    assert body["owner_id"] == str(co_author.id)


# ---------------------------------------------------------------------------
# DoD-5 (US-025.AC-1 complement -- resolved _TBD_ = refuse): transfer to a
# NON-MEMBER is refused (4xx, frozen 409) and ownership does NOT change.
# ---------------------------------------------------------------------------
async def test_transfer_to_non_member_refused_no_change__DoD5_US025_AC1(http_client):
    owner, owner_token = await _seed_author("frank")
    non_member, _nm_token = await _seed_author("grace")

    book = await _create_book(http_client, owner_token, visibility="private")

    resp = await http_client.post(
        f"{BASE}/{book['id']}/transfer",
        headers=_auth_header(owner_token),
        json={"target_user_id": str(non_member.id)},
    )
    assert resp.status_code == 409, resp.text

    # Ownership unchanged: the owner still sees themselves as owner.
    detail = await http_client.get(
        f"{BASE}/{book['id']}", headers=_auth_header(owner_token)
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["owner_id"] == str(owner.id)


# ---------------------------------------------------------------------------
# DoD-6 (US-027.AC-1): POST /{book_id}/members by the owner grants the target
# co-author access -- the target appears in the detail members list AND can open
# the book afterward.
# ---------------------------------------------------------------------------
async def test_add_member_grants_co_author_access__DoD6_US027_AC1(http_client):
    _owner, owner_token = await _seed_author("heidi")
    target, target_token = await _seed_author("ivan")

    book = await _create_book(http_client, owner_token, visibility="private")

    resp = await http_client.post(
        f"{BASE}/{book['id']}/members",
        headers=_auth_header(owner_token),
        json={"target_user_id": str(target.id)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    BookDetailResponse.model_validate(body)

    member_ids = [m["user_id"] for m in body["members"]]
    assert str(target.id) in member_ids

    # The newly-added co-author can now open the (private) book detail.
    opened = await http_client.get(
        f"{BASE}/{book['id']}", headers=_auth_header(target_token)
    )
    assert opened.status_code == 200, opened.text


# ---------------------------------------------------------------------------
# DoD-7 (US-028.AC-1): DELETE /{book_id}/members/{user_id} by the owner ends the
# co-author's access -- the removed user is refused (404) on the private book.
# ---------------------------------------------------------------------------
async def test_remove_member_ends_access_404__DoD7_US028_AC1(http_client):
    _owner, owner_token = await _seed_author("judy")
    co_author, co_token = await _seed_author("kevin")

    book = await _create_book(http_client, owner_token, visibility="private")
    await _add_co_author(int(book["id"]), co_author.id)

    # Precondition: the co-author currently CAN open the private book.
    before = await http_client.get(
        f"{BASE}/{book['id']}", headers=_auth_header(co_token)
    )
    assert before.status_code == 200, before.text

    removed = await http_client.delete(
        f"{BASE}/{book['id']}/members/{co_author.id}",
        headers=_auth_header(owner_token),
    )
    assert removed.status_code == 200, removed.text
    BookDetailResponse.model_validate(removed.json())

    # Access ended: the removed co-author is now hidden behind a 404.
    after = await http_client.get(
        f"{BASE}/{book['id']}", headers=_auth_header(co_token)
    )
    assert after.status_code == 404, after.text


# ---------------------------------------------------------------------------
# DoD-8 (US-029.AC-1): PATCH /{book_id}/visibility -> public lets a logged-in
# non-member open the reader projection (200 on /read).
# ---------------------------------------------------------------------------
async def test_visibility_public_opens_reader__DoD8_US029_AC1(http_client):
    _owner, owner_token = await _seed_author("laura")
    _non_member, nm_token = await _seed_author("mike")

    book = await _create_book(http_client, owner_token, visibility="private")

    # Precondition: while private, the non-member gets 404 on /read.
    pre = await http_client.get(
        f"{BASE}/{book['id']}/read", headers=_auth_header(nm_token)
    )
    assert pre.status_code == 404, pre.text

    flipped = await http_client.patch(
        f"{BASE}/{book['id']}/visibility",
        headers=_auth_header(owner_token),
        json={"visibility": "public"},
    )
    assert flipped.status_code == 200, flipped.text
    BookResponse.model_validate(flipped.json())

    resp = await http_client.get(
        f"{BASE}/{book['id']}/read", headers=_auth_header(nm_token)
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# DoD-9 (US-029.AC-2): PATCH /{book_id}/visibility -> private refuses a logged-in
# non-member (404 on /read).
# ---------------------------------------------------------------------------
async def test_visibility_private_refuses_reader__DoD9_US029_AC2(http_client):
    _owner, owner_token = await _seed_author("nina")
    _non_member, nm_token = await _seed_author("oscar")

    book = await _create_book(http_client, owner_token, visibility="public")

    # Precondition: while public, the non-member gets 200 on /read.
    pre = await http_client.get(
        f"{BASE}/{book['id']}/read", headers=_auth_header(nm_token)
    )
    assert pre.status_code == 200, pre.text

    flipped = await http_client.patch(
        f"{BASE}/{book['id']}/visibility",
        headers=_auth_header(owner_token),
        json={"visibility": "private"},
    )
    assert flipped.status_code == 200, flipped.text
    BookResponse.model_validate(flipped.json())

    resp = await http_client.get(
        f"{BASE}/{book['id']}/read", headers=_auth_header(nm_token)
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# DoD-10 (owner-only matrix): every mutation refuses a CO-AUTHOR caller with 403 --
# archive, transfer, add-member, remove-member, set-visibility. The co-author is a
# legitimate member of a private book (so book_access resolves and the service is
# reached), but lacks the owner-only capability -> authz denial mapped to 403.
# ---------------------------------------------------------------------------
def _archive_request(book_id, target_id):
    return "POST", f"{BASE}/{book_id}/archive", None


def _transfer_request(book_id, target_id):
    return "POST", f"{BASE}/{book_id}/transfer", {"target_user_id": target_id}


def _add_member_request(book_id, target_id):
    return "POST", f"{BASE}/{book_id}/members", {"target_user_id": target_id}


def _remove_member_request(book_id, target_id):
    return "DELETE", f"{BASE}/{book_id}/members/{target_id}", None


def _set_visibility_request(book_id, target_id):
    return "PATCH", f"{BASE}/{book_id}/visibility", {"visibility": "public"}


@pytest.mark.parametrize(
    "build_request",
    [
        pytest.param(_archive_request, id="archive"),
        pytest.param(_transfer_request, id="transfer"),
        pytest.param(_add_member_request, id="add_member"),
        pytest.param(_remove_member_request, id="remove_member"),
        pytest.param(_set_visibility_request, id="set_visibility"),
    ],
)
async def test_mutation_refuses_co_author_403__DoD10(http_client, build_request):
    _owner, owner_token = await _seed_author("paula")
    co_author, co_token = await _seed_author("quinn")
    third, _third_token = await _seed_author("rosa")

    book = await _create_book(http_client, owner_token, visibility="private")
    await _add_co_author(int(book["id"]), co_author.id)

    method, url, json_body = build_request(book["id"], str(third.id))

    resp = await http_client.request(
        method, url, headers=_auth_header(co_token), json=json_body
    )
    assert resp.status_code == 403, resp.text
