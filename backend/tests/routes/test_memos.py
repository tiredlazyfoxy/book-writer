"""End-to-end tests for the memo HTTP surface (feature 026, step 003).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). The app's startup
lifespan runs against a throwaway temp DB; each test seeds its own users, books,
members and memo rows on the same process-global engine the app uses (schema
built with `init_db`, readiness flipped with `set_db_ready(True)`), mirroring
tests/routes/test_book_author_prompts.py.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 003), router
`app.routes.memos` with prefix "/api/books", every handler gated by
`Depends(authz.book_access)` and none re-declaring `book_id`:
    GET /{book_id}/memos            -> 200 MemoListResponse
                                       (`include_archived` optional query, default false)
    POST /{book_id}/memos           -> 201 MemoResponse
    PUT /{book_id}/memos/{memo_id}  -> 200 MemoResponse
and the step-002 DTOs of `app.models.schemas.memos`.

Wire contract (context.md -> "The wire contract"): `MemoResponse` carries `id`,
`book_id`, `body`, `ordinal`, `active`, `archived`, `created_at`, `modified_at`
-- ids as **strings**, and **no `user_id`**. The list envelope key is `items`.

Status taxonomy (context.md; authorization.md -> "Failure modes"): no token ->
401; no relationship to a **private** book -> 404 (existence hiding, produced by
the dependency); a logged-in non-member of a book they can see -> 403; a memo
that does not exist, belongs to another author, or belongs to another book ->
404, one single refusal with no existence oracle; a member acting on their own
memo -> 200 (201 on create). An **archived book still accepts memo writes** --
the one named carve-out (context.md -> decision 4). There is no `DELETE` at any
layer (decision 6), so the framework answers 405.

Expected values come from the SPEC ONLY -- the step DoD (DoD-1..DoD-13), the
step Interface intent, `003.context.md` and the feature `context.md` decisions --
never from implementation internals.

Async tests use asyncio_mode = "auto".
"""

import datetime
import json

from app.db import book_members, books, users
from app.db import memos as memos_db
from app.db.engine import init_db, set_db_ready
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_member import BookMember, MemberRole
from app.models.memo import Memo
from app.models.schemas.memos import MemoListResponse, MemoResponse
from app.models.user import User, UserRole
from app.services import auth

# ---------------------------------------------------------------------------
# Seed helpers -- copied from tests/routes/test_book_author_prompts.py
# (auth is real: a seeded user row plus a real JWT)
# ---------------------------------------------------------------------------


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_user(username: str, role: UserRole = UserRole.author) -> User:
    await init_db()
    user = await users.create(
        User(
            username=username,
            role=role,
            pwdhash=auth.hash_password("password123"),
            jwt_signing_key=auth.generate_signing_key(),
            last_key_update=_now(),
        )
    )
    set_db_ready(True)
    return user


async def _seed_author(username: str) -> tuple[User, str]:
    user = await _seed_user(username)
    return user, auth.create_access_token(user)


async def _seed_book(
    owner_id: int,
    visibility: Visibility = Visibility.private,
    state: BookState = BookState.active,
    title: str = "A Book",
) -> Book:
    return await books.create(
        Book(
            title=title,
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=visibility,
            state=state,
            system_prompt="",
            active_notes="",
        )
    )


async def _seed_private_book(owner_id: int, title: str = "A Book") -> Book:
    return await _seed_book(owner_id, Visibility.private, BookState.active, title)


async def _seed_public_book(owner_id: int) -> Book:
    """A book anyone logged in can see -- DoD-10's 403 fixture."""
    return await _seed_book(
        owner_id, Visibility.public, BookState.active, "A Public Book"
    )


async def _add_co_author(book_id: int, user_id: int) -> None:
    await book_members.create(
        BookMember(
            book_id=book_id,
            user_id=user_id,
            role=MemberRole.co_author,
            created_at=_now(),
        )
    )


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _list_url(book_id: int) -> str:
    return f"/api/books/{book_id}/memos"


def _memo_url(book_id: int, memo_id: object) -> str:
    return f"/api/books/{book_id}/memos/{memo_id}"


async def _seed_memo(
    book_id: int,
    user_id: int,
    body: str,
    ordinal: int,
    *,
    active: bool = True,
    archived: bool = False,
) -> Memo:
    """Seed a stored memo directly through the db layer (no route involved)."""
    stamp = _now()
    return await memos_db.create(
        Memo(
            book_id=book_id,
            user_id=user_id,
            body=body,
            ordinal=ordinal,
            active=active,
            archived=archived,
            created_at=stamp,
            modified_at=stamp,
        )
    )


async def _list_memos(
    http_client, token: str, book_id: int, include_archived: bool | None = None
) -> MemoListResponse:
    params = {} if include_archived is None else {"include_archived": include_archived}
    resp = await http_client.get(
        _list_url(book_id), headers=_auth_header(token), params=params
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "items" in payload, payload
    return MemoListResponse.model_validate(payload)


async def _create_memo(http_client, token: str, book_id: int, body: str) -> MemoResponse:
    resp = await http_client.post(
        _list_url(book_id), headers=_auth_header(token), json={"body": body}
    )
    assert resp.status_code == 201, resp.text
    return MemoResponse.model_validate(resp.json())


# ---------------------------------------------------------------------------
# DoD-1 -- GET returns only the caller's own memos, in both directions
# ---------------------------------------------------------------------------


# DoD-1 (US-124.AC-1, US-124.AC-2; context.md -> decision 1: "nobody else,
# including the book's owner, ever reads it"): two members of one book each see
# exactly their own memos -- and crucially the OWNER sees none of the
# co-author's.
async def test_list_returns_only_the_callers_own_memos__DoD1(http_client):
    owner, owner_token = await _seed_author("memo_owner_1")
    co_author, co_token = await _seed_author("memo_co_author_1")
    book = await _seed_private_book(owner.id)
    await _add_co_author(book.id, co_author.id)

    await _create_memo(http_client, owner_token, book.id, "OWNER NOTE A")
    await _create_memo(http_client, owner_token, book.id, "OWNER NOTE B")
    await _create_memo(http_client, co_token, book.id, "CO-AUTHOR NOTE")

    owner_bodies = [m.body for m in (await _list_memos(http_client, owner_token, book.id)).items]
    co_bodies = [m.body for m in (await _list_memos(http_client, co_token, book.id)).items]

    # the co-author sees none of the owner's
    assert co_bodies == ["CO-AUTHOR NOTE"]
    # ...and the owner -- the book's owner -- sees none of the co-author's
    assert owner_bodies == ["OWNER NOTE A", "OWNER NOTE B"]


# ---------------------------------------------------------------------------
# DoD-2 -- the default list omits archived memos
# ---------------------------------------------------------------------------


# DoD-2 (US-128.AC-1): with no query parameter at all, an archived memo is not
# in the list; an inactive-but-live one still is (two independent axes,
# context.md -> decision 1).
async def test_list_without_query_omits_archived__DoD2(http_client):
    owner, owner_token = await _seed_author("memo_owner_2")
    book = await _seed_private_book(owner.id)

    await _seed_memo(book.id, owner.id, "LIVE", 1)
    await _seed_memo(book.id, owner.id, "SWITCHED OFF", 2, active=False)
    await _seed_memo(book.id, owner.id, "ARCHIVED", 3, archived=True)

    listed = await _list_memos(http_client, owner_token, book.id)
    assert [m.body for m in listed.items] == ["LIVE", "SWITCHED OFF"]
    assert all(m.archived is False for m in listed.items)


# ---------------------------------------------------------------------------
# DoD-3 -- the include-archived parameter reaches the archived set over HTTP
# ---------------------------------------------------------------------------


# DoD-3 (US-128.AC-2): asking for archived memos returns them alongside the live
# ones, flagged `archived`.
async def test_list_with_include_archived_returns_archived_too__DoD3(http_client):
    owner, owner_token = await _seed_author("memo_owner_3")
    book = await _seed_private_book(owner.id)

    await _seed_memo(book.id, owner.id, "LIVE", 1)
    await _seed_memo(book.id, owner.id, "ARCHIVED", 2, archived=True)

    listed = await _list_memos(http_client, owner_token, book.id, include_archived=True)
    by_body = {m.body: m for m in listed.items}
    assert set(by_body) == {"LIVE", "ARCHIVED"}
    assert by_body["ARCHIVED"].archived is True
    assert by_body["LIVE"].archived is False

    # an explicit false is the same as omitting it
    explicit_off = await _list_memos(
        http_client, owner_token, book.id, include_archived=False
    )
    assert [m.body for m in explicit_off.items] == ["LIVE"]


# ---------------------------------------------------------------------------
# DoD-4 -- the returned list is ordinal-ordered
# ---------------------------------------------------------------------------


# DoD-4 (US-131.AC-2): rows stored out of ordinal order come back in ordinal
# order, and the order holds across the gap an archive leaves behind
# (context.md -> decision 2: archiving never renumbers).
async def test_list_is_ordinal_ordered__DoD4(http_client):
    owner, owner_token = await _seed_author("memo_owner_4")
    book = await _seed_private_book(owner.id)

    await _seed_memo(book.id, owner.id, "THIRD", 7)
    await _seed_memo(book.id, owner.id, "FIRST", 1)
    await _seed_memo(book.id, owner.id, "SECOND", 4)

    listed = await _list_memos(http_client, owner_token, book.id)
    assert [m.body for m in listed.items] == ["FIRST", "SECOND", "THIRD"]
    assert [m.ordinal for m in listed.items] == [1, 4, 7]


# ---------------------------------------------------------------------------
# DoD-5 -- POST answers 201 and the created memo is last in the list
# ---------------------------------------------------------------------------


# DoD-5 (US-123.AC-1; context.md -> decision 2: "a new memo is appended at
# max + 1"): the create answers 201 with the memo on the wire (string ids, no
# user_id), and a following list ends with it.
async def test_create_answers_201_and_appends_last__DoD5(http_client):
    owner, owner_token = await _seed_author("memo_owner_5")
    book = await _seed_private_book(owner.id)

    await _create_memo(http_client, owner_token, book.id, "FIRST")
    await _create_memo(http_client, owner_token, book.id, "SECOND")

    resp = await http_client.post(
        _list_url(book.id),
        headers=_auth_header(owner_token),
        json={"body": "NEWEST"},
    )
    assert resp.status_code == 201, resp.text
    payload = resp.json()
    assert isinstance(payload["id"], str)
    assert isinstance(payload["book_id"], str)
    assert "user_id" not in payload

    created = MemoResponse.model_validate(payload)
    assert created.body == "NEWEST"
    assert created.book_id == str(book.id)

    listed = await _list_memos(http_client, owner_token, book.id)
    assert [m.body for m in listed.items] == ["FIRST", "SECOND", "NEWEST"]
    assert listed.items[-1].id == created.id
    assert listed.items[-1].ordinal == created.ordinal


# ---------------------------------------------------------------------------
# DoD-6 -- the created memo comes back active and not archived
# ---------------------------------------------------------------------------


# DoD-6 (US-123.AC-3): a fresh memo is switched on and not archived, both in the
# 201 response and in the list read back afterwards.
async def test_created_memo_is_active_and_not_archived__DoD6(http_client):
    owner, owner_token = await _seed_author("memo_owner_6")
    book = await _seed_private_book(owner.id)

    created = await _create_memo(http_client, owner_token, book.id, "A standing note.")
    assert created.active is True
    assert created.archived is False

    listed = await _list_memos(http_client, owner_token, book.id)
    assert len(listed.items) == 1
    assert listed.items[0].active is True
    assert listed.items[0].archived is False


# ---------------------------------------------------------------------------
# DoD-7 -- POST with an empty body succeeds and is never a 422
# ---------------------------------------------------------------------------


# DoD-7 (UC-103 postcondition; context.md -> decision 1: an empty string is
# legal -- a new memo is created empty): an empty body is legitimate input, so the create
# answers 201 with an empty body and the memo is listed.
async def test_create_with_empty_body_succeeds__DoD7(http_client):
    owner, owner_token = await _seed_author("memo_owner_7")
    book = await _seed_private_book(owner.id)

    resp = await http_client.post(
        _list_url(book.id), headers=_auth_header(owner_token), json={"body": ""}
    )
    assert resp.status_code != 422, resp.text
    assert resp.status_code == 201, resp.text

    created = MemoResponse.model_validate(resp.json())
    assert created.body == ""
    assert created.active is True
    assert created.archived is False

    listed = await _list_memos(http_client, owner_token, book.id)
    assert [m.body for m in listed.items] == [""]


# ---------------------------------------------------------------------------
# DoD-8 -- PUT writes the body and changes no other field
# ---------------------------------------------------------------------------


# DoD-8 (US-125.AC-1): the body-only PUT answers 200 with the updated memo; id,
# book_id, ordinal, active, archived and created_at are all untouched (the only
# other field that moves is `modified_at`, the modification stamp).
async def test_put_writes_only_the_body__DoD8(http_client):
    owner, owner_token = await _seed_author("memo_owner_8")
    book = await _seed_private_book(owner.id)
    seeded = await _seed_memo(book.id, owner.id, "Before.", 7, active=False)

    before = await _list_memos(http_client, owner_token, book.id)
    original = before.items[0]

    resp = await http_client.put(
        _memo_url(book.id, seeded.id),
        headers=_auth_header(owner_token),
        json={"body": "After."},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "user_id" not in payload
    updated = MemoResponse.model_validate(payload)

    assert updated.body == "After."
    assert updated.id == original.id == str(seeded.id)
    assert updated.book_id == str(book.id)
    assert updated.ordinal == 7
    assert updated.active is False
    assert updated.archived is False
    assert updated.created_at == original.created_at

    read_back = await _list_memos(http_client, owner_token, book.id)
    assert [m.body for m in read_back.items] == ["After."]
    assert read_back.items[0].ordinal == 7
    assert read_back.items[0].active is False


# ---------------------------------------------------------------------------
# DoD-9 -- four unreachable memo ids, one identical 404, no existence oracle
# ---------------------------------------------------------------------------


# DoD-9 (US-124.AC-1; context.md -> decision 3: "one refusal, 404 -- no
# existence oracle"): another author's memo, a memo of another book, an id that
# belongs to nobody, and a non-numeric id all answer 404 with the SAME body --
# so the response can never be used to tell one case from another.
async def test_unreachable_memo_ids_answer_one_identical_404__DoD9(http_client):
    owner, owner_token = await _seed_author("memo_owner_9")
    co_author, _co_token = await _seed_author("memo_co_author_9")
    book = await _seed_private_book(owner.id, title="Book One")
    other_book = await _seed_private_book(owner.id, title="Book Two")
    await _add_co_author(book.id, co_author.id)

    foreign_author_memo = await _seed_memo(book.id, co_author.id, "Not yours.", 1)
    other_book_memo = await _seed_memo(other_book.id, owner.id, "Elsewhere.", 1)

    candidates = [
        foreign_author_memo.id,  # another author's memo, this book
        other_book_memo.id,  # the caller's own memo, but another book
        1234567890123456789,  # belongs to nobody
        "not-a-number",  # malformed -- still 404, never a 422
    ]

    bodies: list[str] = []
    for memo_id in candidates:
        resp = await http_client.put(
            _memo_url(book.id, memo_id),
            headers=_auth_header(owner_token),
            json={"body": "sneaky"},
        )
        assert resp.status_code == 404, f"{memo_id!r} -> {resp.status_code} {resp.text}"
        bodies.append(json.dumps(resp.json(), sort_keys=True))

    # sameness, not merely "each is a 404"
    assert len(set(bodies)) == 1, bodies

    # neither foreign row was written
    for row_id in (foreign_author_memo.id, other_book_memo.id):
        row = await memos_db.get_by_id(row_id)
        assert row is not None
        assert row.body in ("Not yours.", "Elsewhere.")
        assert row.body != "sneaky"


# ---------------------------------------------------------------------------
# DoD-10 -- 401 with no token, 404 on an invisible private book, 403 for a
#           logged-in non-member of a book they can see
# ---------------------------------------------------------------------------


# DoD-10 (authorization.md -> the memo status table; context.md -> "Status
# taxonomy"): a request carrying no Authorization header at all is a 401 on
# every one of the three routes.
async def test_missing_token_is_401_on_every_route__DoD10(http_client):
    owner, owner_token = await _seed_author("memo_owner_10a")
    book = await _seed_private_book(owner.id)
    memo = await _create_memo(http_client, owner_token, book.id, "Mine.")

    assert (await http_client.get(_list_url(book.id))).status_code == 401
    assert (
        await http_client.post(_list_url(book.id), json={"body": "anon"})
    ).status_code == 401
    assert (
        await http_client.put(
            _memo_url(book.id, memo.id), json={"body": "anon"}
        )
    ).status_code == 401


# DoD-10 (authorization.md -> "Failure modes"): a logged-in caller with no
# relationship at all to a PRIVATE book is answered 404 by the dependency --
# existence hiding, never re-derived in the route.
async def test_stranger_on_private_book_is_404_on_every_route__DoD10(http_client):
    owner, owner_token = await _seed_author("memo_owner_10b")
    _stranger, stranger_token = await _seed_author("memo_stranger_10b")
    book = await _seed_private_book(owner.id)
    memo = await _create_memo(http_client, owner_token, book.id, "Mine.")
    h = _auth_header(stranger_token)

    assert (await http_client.get(_list_url(book.id), headers=h)).status_code == 404
    assert (
        await http_client.post(_list_url(book.id), headers=h, json={"body": "sneaky"})
    ).status_code == 404
    assert (
        await http_client.put(
            _memo_url(book.id, memo.id), headers=h, json={"body": "sneaky"}
        )
    ).status_code == 404


# DoD-10 (authorization.md -> the memo status table): a logged-in caller who CAN
# see the book -- a reader on a public book -- but is not a member is refused
# with 403, naming the permission rather than hiding the book. Nothing is
# written for them either.
async def test_non_member_of_visible_book_is_403_on_every_route__DoD10(http_client):
    owner, owner_token = await _seed_author("memo_owner_10c")
    _reader, reader_token = await _seed_author("memo_reader_10c")
    book = await _seed_public_book(owner.id)
    memo = await _create_memo(http_client, owner_token, book.id, "Owner note.")
    h = _auth_header(reader_token)

    assert (await http_client.get(_list_url(book.id), headers=h)).status_code == 403
    assert (
        await http_client.post(_list_url(book.id), headers=h, json={"body": "not mine"})
    ).status_code == 403
    assert (
        await http_client.put(
            _memo_url(book.id, memo.id), headers=h, json={"body": "not mine"}
        )
    ).status_code == 403

    # the refused write reached no storage
    survivors = await _list_memos(http_client, owner_token, book.id)
    assert [m.body for m in survivors.items] == ["Owner note."]


# ---------------------------------------------------------------------------
# DoD-11 -- an archived book still accepts memo writes (the named carve-out)
# ---------------------------------------------------------------------------


# DoD-11 (authorization.md -> the archived-book carve-out; context.md ->
# decision 4): a memo is the author's private note ABOUT a book they have set
# aside, so create AND body-update both succeed while the book's state is
# `archived` -- unlike chapters, which refuse writes there.
async def test_archived_book_still_accepts_memo_writes__DoD11(http_client):
    owner, owner_token = await _seed_author("memo_owner_11")
    book = await _seed_private_book(owner.id)

    book.state = BookState.archived
    await books.update(book)

    create_resp = await http_client.post(
        _list_url(book.id),
        headers=_auth_header(owner_token),
        json={"body": "Written after archiving."},
    )
    assert create_resp.status_code == 201, create_resp.text
    created = MemoResponse.model_validate(create_resp.json())
    assert created.body == "Written after archiving."

    update_resp = await http_client.put(
        _memo_url(book.id, created.id),
        headers=_auth_header(owner_token),
        json={"body": "Edited after archiving."},
    )
    assert update_resp.status_code == 200, update_resp.text
    assert MemoResponse.model_validate(update_resp.json()).body == (
        "Edited after archiving."
    )

    listed = await _list_memos(http_client, owner_token, book.id)
    assert [m.body for m in listed.items] == ["Edited after archiving."]


# ---------------------------------------------------------------------------
# DoD-12 -- there is no DELETE on either path
# ---------------------------------------------------------------------------


# DoD-12 (US-128.AC-3; context.md -> decision 6: "no DELETE route"): archive,
# never delete. Neither memo path answers DELETE, so the framework refuses it
# with 405, and the memo survives the attempt.
async def test_delete_is_refused_by_the_framework__DoD12(http_client):
    owner, owner_token = await _seed_author("memo_owner_12")
    book = await _seed_private_book(owner.id)
    memo = await _create_memo(http_client, owner_token, book.id, "Still here.")
    h = _auth_header(owner_token)

    assert (await http_client.delete(_list_url(book.id), headers=h)).status_code == 405
    assert (
        await http_client.delete(_memo_url(book.id, memo.id), headers=h)
    ).status_code == 405

    survivors = await _list_memos(http_client, owner_token, book.id)
    assert [m.body for m in survivors.items] == ["Still here."]


# ---------------------------------------------------------------------------
# DoD-13 -- the router is registered: all three paths resolve on the live app
# ---------------------------------------------------------------------------


# DoD-13 (infrastructural; step file -> "one import plus one
# app.include_router"): read from the app's GENERATED OpenAPI document, which
# enumerates the operations the running application actually exposes -- the
# top-level `app.routes` list does not, because `include_router` keeps included
# routes wrapped.
async def test_router_is_registered_and_paths_resolve__DoD13(http_client):
    from app.main import app

    paths = app.openapi()["paths"]

    assert "/api/books/{book_id}/memos" in paths
    assert "/api/books/{book_id}/memos/{memo_id}" in paths

    collection = {m.lower() for m in paths["/api/books/{book_id}/memos"]}
    item = {m.lower() for m in paths["/api/books/{book_id}/memos/{memo_id}"]}

    assert "get" in collection
    assert "post" in collection
    assert "put" in item
    assert "delete" not in collection
    assert "delete" not in item
