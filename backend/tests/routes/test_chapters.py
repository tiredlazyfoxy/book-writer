"""End-to-end tests for the `/api/books/{book_id}/chapters` route family
(feature 014, step 003).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). Each test seeds its
own author users on the same process-global engine the app uses, mirroring
`tests/routes/test_book_settings.py`'s `_now` / `_auth_header` / `_seed_user` /
`_seed_author` / `_create_book` / `_add_co_author` helpers, which are copied
per-file rather than imported (they are deliberately not shared fixtures). Auth
is real: a user row is seeded and a real JWT is minted, so the whole request
path -- dependency included -- runs.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 003), six handlers on
a router with prefix "/api/books", each gated by `Depends(authz.book_access)`:

    GET    "/{book_id}/chapters"                -> 200 ChapterListResponse
    POST   "/{book_id}/chapters"                -> 201 ChapterResponse
    PUT    "/{book_id}/chapters/order"          -> 200 ChapterListResponse
    GET    "/{book_id}/chapters/{chapter_id}"   -> 200 ChapterResponse
    PATCH  "/{book_id}/chapters/{chapter_id}"   -> 200 ChapterResponse
    DELETE "/{book_id}/chapters/{chapter_id}"   -> 204, no body

Request/response DTOs are step 002's (status.md -> Skeleton -> Step 002):
    CreateChapterRequest        title (non-blank), sketch (may be "")
    UpdateChapterSketchRequest  sketch                 (no version token, D6)
    ReorderChaptersRequest      chapter_ids: list[str] (the FULL ordered list, D3)
    ChapterResponse             id, book_id, ordinal, title, state, sketch,
                                version, created_at, modified_at
    ChapterListResponse         chapters, can_reorder

Expected values come from the SPEC ONLY -- `003.chapter-routes.md`'s Definition of
done (DoD-1..DoD-17) and Interface intent, `003.context.md`, and the feature
`context.md` ("Endpoints", "Status taxonomy", the wire contract, the
authorization matrix) -- never from implementation internals. The status
taxonomy this module pins:

    no token                                   -> 401  (the dependency's)
    private book, no relationship              -> 404  (existence hiding, the
                                                        dependency's, never re-derived)
    visible book, missing capability           -> 403  (the service's authz.require)
    unknown chapter id, or ANOTHER BOOK's      -> 404  (the service's resolver, D4)
    chapter not `planned`, on sketch/remove    -> 409  (a state-machine constraint,
                                                        NOT 403 -- the caller holds
                                                        the capability)
    reorder list != the book's chapter set     -> 400  (a cross-row invariant, NOT
                                                        422 -- the body is
                                                        structurally valid)
    malformed body                             -> 422  (framework validation)
    success                                    -> 200, 201 on create, 204 on delete

This feature ships no state transition, so a spec needing an `open` / `closing` /
`closed` chapter writes the state straight through `app.db.chapters` (DoD-5 and
DoD-7). That is the same "reach past the routes for a relationship the route
family cannot create" move `_add_co_author` already makes, and it runs against
the app's own engine -- the `db` fixture is deliberately NOT requested, because
it would repoint the process-global engine away from the one `http_client`'s
lifespan initialized.

Async tests use asyncio_mode = "auto".
"""

import datetime

import pytest

from app.db import book_members, chapters as chapters_db, users
from app.db.engine import init_db, set_db_ready
from app.models.book_member import BookMember, MemberRole
from app.models.chapter import Chapter, ChapterState
from app.models.schemas.chapters import ChapterListResponse, ChapterResponse
from app.models.user import User, UserRole
from app.services import auth

BASE = "/api/books"

# The exact ChapterResponse field set, from context.md -> "The wire contract":
# no `text`, no `summary`, no `summary_status`, no `system_prompt`.
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
    """Seed a persisted author on the app's engine and mark the instance ready."""
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
    """Insert a co-author BookMember row directly through the db layer."""
    await book_members.create(
        BookMember(
            book_id=book_id,
            user_id=user_id,
            role=MemberRole.co_author,
            created_at=_now(),
        )
    )


# ---------------------------------------------------------------------------
# Chapter-family helpers.
# ---------------------------------------------------------------------------


def _c_url(book_id) -> str:
    """The collection path for a book's chapters."""
    return f"{BASE}/{book_id}/chapters"


async def _create_chapter(
    http_client,
    token: str,
    book_id,
    *,
    title: str = "A Chapter",
    sketch: str = "a sketch",
) -> dict:
    """POST a chapter via the route as the token's caller; return the 201 body."""
    resp = await http_client.post(
        _c_url(book_id),
        headers=_auth_header(token),
        json={"title": title, "sketch": sketch},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _list_body(http_client, token: str, book_id) -> dict:
    """GET the collection and return the validated envelope body."""
    resp = await http_client.get(_c_url(book_id), headers=_auth_header(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ChapterListResponse.model_validate(body)
    return body


async def _list_ids(http_client, token: str, book_id) -> list[str]:
    body = await _list_body(http_client, token, book_id)
    return [c["id"] for c in body["chapters"]]


async def _stored_ordinals(book_id) -> dict[int, int]:
    """{chapter id -> stored ordinal}, read straight from the db layer."""
    return {c.id: c.ordinal for c in await chapters_db.list_by_book(int(book_id))}


async def _force_state(chapter_id, state: ChapterState) -> None:
    """Write a chapter's state directly -- this feature ships no transition."""
    row = await chapters_db.get_by_id(int(chapter_id))
    assert row is not None
    row.state = state
    await chapters_db.update(row)


async def _seed_chapter_row(
    book_id,
    *,
    ordinal: int,
    title: str = "Seeded",
    sketch: str = "seeded sketch",
    state: ChapterState = ChapterState.planned,
) -> Chapter:
    """A Chapter inserted straight through db/chapters.py, bypassing the routes."""
    return await chapters_db.create(
        Chapter(
            book_id=int(book_id),
            ordinal=ordinal,
            title=title,
            state=state,
            sketch=sketch,
            text="",
        )
    )


NON_PLANNED_STATES = [
    pytest.param(ChapterState.open, id="open"),
    pytest.param(ChapterState.closing, id="closing"),
    pytest.param(ChapterState.closed, id="closed"),
]


# ---------------------------------------------------------------------------
# DoD-1: GET on the collection returns 200 and the book's chapters ordered by
# ordinal ascending, each carrying its id as a string and no body text.
# ---------------------------------------------------------------------------
async def test_list_returns_ordinal_ascending_string_ids_no_text__DoD1(http_client):
    _owner, owner_token = await _seed_author("alice")
    book = await _create_book(http_client, owner_token)

    # Seeded out of ordinal order, so ascending ordering is a real assertion.
    third = await _seed_chapter_row(book["id"], ordinal=3, title="Third")
    first = await _seed_chapter_row(book["id"], ordinal=1, title="First")
    second = await _seed_chapter_row(book["id"], ordinal=2, title="Second")

    resp = await http_client.get(_c_url(book["id"]), headers=_auth_header(owner_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ChapterListResponse.model_validate(body)

    assert [c["ordinal"] for c in body["chapters"]] == [1, 2, 3]
    assert [c["id"] for c in body["chapters"]] == [
        str(first.id),
        str(second.id),
        str(third.id),
    ]
    for chapter in body["chapters"]:
        assert isinstance(chapter["id"], str)
        assert isinstance(chapter["book_id"], str)
        # The wire contract carries no body text (and no summary fields).
        assert "text" not in chapter
        assert set(chapter.keys()) == WIRE_FIELDS


# DoD-1: the collection is scoped to the addressed book -- another book's
# chapters never appear in it.
async def test_list_is_scoped_to_the_addressed_book__DoD1(http_client):
    _owner, owner_token = await _seed_author("bob")
    book_a = await _create_book(http_client, owner_token, title="A")
    book_b = await _create_book(http_client, owner_token, title="B")

    mine = await _create_chapter(http_client, owner_token, book_a["id"], title="Mine")
    await _create_chapter(http_client, owner_token, book_b["id"], title="Theirs")

    assert await _list_ids(http_client, owner_token, book_a["id"]) == [mine["id"]]


# ---------------------------------------------------------------------------
# DoD-2 (US-032.AC-1, UC-031): POST returns 201 and a `planned` chapter carrying
# the submitted sketch; a following GET on the collection includes it, appended
# last.
# ---------------------------------------------------------------------------
async def test_create_returns_201_planned_and_appends_last__DoD2_US032_AC1(
    http_client,
):
    _owner, owner_token = await _seed_author("carol")
    book = await _create_book(http_client, owner_token)

    first = await _create_chapter(
        http_client, owner_token, book["id"], title="The Arrival", sketch="they arrive"
    )

    resp = await http_client.post(
        _c_url(book["id"]),
        headers=_auth_header(owner_token),
        json={"title": "The Departure", "sketch": "they leave at dawn"},
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    ChapterResponse.model_validate(created)

    assert created["title"] == "The Departure"
    assert created["sketch"] == "they leave at dawn"
    assert created["state"] == ChapterState.planned.value

    # Appended LAST: the new chapter is the final entry of the ordered list.
    listed = await _list_ids(http_client, owner_token, book["id"])
    assert listed == [first["id"], created["id"]]
    assert created["id"] in listed


# ---------------------------------------------------------------------------
# DoD-3: POST with a blank title is refused as a validation error (422) and
# nothing is stored; POST with an empty sketch succeeds.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "blank_title",
    [pytest.param("", id="empty"), pytest.param("   ", id="whitespace")],
)
async def test_create_blank_title_422_stores_nothing__DoD3(http_client, blank_title):
    _owner, owner_token = await _seed_author("dave")
    book = await _create_book(http_client, owner_token)

    resp = await http_client.post(
        _c_url(book["id"]),
        headers=_auth_header(owner_token),
        json={"title": blank_title, "sketch": "a sketch"},
    )
    assert resp.status_code == 422, resp.text

    assert await _list_ids(http_client, owner_token, book["id"]) == []


async def test_create_with_empty_sketch_succeeds__DoD3(http_client):
    _owner, owner_token = await _seed_author("erin")
    book = await _create_book(http_client, owner_token)

    resp = await http_client.post(
        _c_url(book["id"]),
        headers=_auth_header(owner_token),
        json={"title": "Untitled Yet", "sketch": ""},
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    ChapterResponse.model_validate(created)
    assert created["sketch"] == ""

    assert await _list_ids(http_client, owner_token, book["id"]) == [created["id"]]


# ---------------------------------------------------------------------------
# DoD-4 (US-034.AC-1): PATCH on a `planned` chapter returns 200 with the updated
# sketch, and a following GET on that chapter returns the same value.
# ---------------------------------------------------------------------------
async def test_patch_planned_updates_sketch__DoD4_US034_AC1(http_client):
    _owner, owner_token = await _seed_author("frank")
    book = await _create_book(http_client, owner_token)
    chapter = await _create_chapter(
        http_client, owner_token, book["id"], sketch="the first idea"
    )

    resp = await http_client.patch(
        f"{_c_url(book['id'])}/{chapter['id']}",
        headers=_auth_header(owner_token),
        json={"sketch": "a much better idea"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ChapterResponse.model_validate(body)
    assert body["sketch"] == "a much better idea"

    read_back = await http_client.get(
        f"{_c_url(book['id'])}/{chapter['id']}", headers=_auth_header(owner_token)
    )
    assert read_back.status_code == 200, read_back.text
    ChapterResponse.model_validate(read_back.json())
    assert read_back.json()["sketch"] == "a much better idea"


# ---------------------------------------------------------------------------
# DoD-5 (US-034.AC-2): PATCH on a chapter that is not `planned` returns 409 --
# a state-machine constraint, not 403: the caller HAS the capability -- and the
# stored sketch is unchanged.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("state", NON_PLANNED_STATES)
async def test_patch_non_planned_409_sketch_unchanged__DoD5_US034_AC2(
    http_client, state
):
    _owner, owner_token = await _seed_author("grace")
    book = await _create_book(http_client, owner_token)
    chapter = await _create_chapter(
        http_client, owner_token, book["id"], sketch="the original sketch"
    )
    await _force_state(chapter["id"], state)

    resp = await http_client.patch(
        f"{_c_url(book['id'])}/{chapter['id']}",
        headers=_auth_header(owner_token),
        json={"sketch": "an edit that must not land"},
    )
    assert resp.status_code == 409, resp.text

    stored = await chapters_db.get_by_id(int(chapter["id"]))
    assert stored is not None
    assert stored.sketch == "the original sketch"


# ---------------------------------------------------------------------------
# DoD-6 (US-035.AC-1): DELETE on a `planned` chapter returns 204 and the chapter
# no longer appears in the collection.
# ---------------------------------------------------------------------------
async def test_delete_planned_returns_204_and_removes__DoD6_US035_AC1(http_client):
    _owner, owner_token = await _seed_author("heidi")
    book = await _create_book(http_client, owner_token)
    doomed = await _create_chapter(http_client, owner_token, book["id"], title="Doomed")
    kept = await _create_chapter(http_client, owner_token, book["id"], title="Kept")

    resp = await http_client.delete(
        f"{_c_url(book['id'])}/{doomed['id']}", headers=_auth_header(owner_token)
    )
    assert resp.status_code == 204, resp.text
    assert resp.content == b""

    assert await _list_ids(http_client, owner_token, book["id"]) == [kept["id"]]


# ---------------------------------------------------------------------------
# DoD-7 (US-035.AC-2): DELETE on a chapter that is not `planned` returns 409 and
# the chapter is still there.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("state", NON_PLANNED_STATES)
async def test_delete_non_planned_409_chapter_survives__DoD7_US035_AC2(
    http_client, state
):
    _owner, owner_token = await _seed_author("ivan")
    book = await _create_book(http_client, owner_token)
    chapter = await _create_chapter(http_client, owner_token, book["id"])
    await _force_state(chapter["id"], state)

    resp = await http_client.delete(
        f"{_c_url(book['id'])}/{chapter['id']}", headers=_auth_header(owner_token)
    )
    assert resp.status_code == 409, resp.text

    assert await chapters_db.get_by_id(int(chapter["id"])) is not None
    assert chapter["id"] in await _list_ids(http_client, owner_token, book["id"])


# ---------------------------------------------------------------------------
# DoD-8 (US-033.AC-1): PUT on /order as the OWNER returns 200, and the returned
# list -- and a following GET -- reflect the submitted order. The server rewrites
# ordinals 1..N (D3).
# ---------------------------------------------------------------------------
async def test_owner_reorder_applies_submitted_order__DoD8_US033_AC1(http_client):
    _owner, owner_token = await _seed_author("judy")
    book = await _create_book(http_client, owner_token)
    one = await _create_chapter(http_client, owner_token, book["id"], title="One")
    two = await _create_chapter(http_client, owner_token, book["id"], title="Two")
    three = await _create_chapter(http_client, owner_token, book["id"], title="Three")

    submitted = [three["id"], one["id"], two["id"]]

    resp = await http_client.put(
        f"{_c_url(book['id'])}/order",
        headers=_auth_header(owner_token),
        json={"chapter_ids": submitted},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ChapterListResponse.model_validate(body)

    assert [c["id"] for c in body["chapters"]] == submitted
    assert [c["ordinal"] for c in body["chapters"]] == [1, 2, 3]

    assert await _list_ids(http_client, owner_token, book["id"]) == submitted


# ---------------------------------------------------------------------------
# DoD-9 (US-033.AC-2): PUT on /order as a CO-AUTHOR returns 403 (reorder is
# owner-only) and the order is unchanged.
# ---------------------------------------------------------------------------
async def test_co_author_reorder_403_order_unchanged__DoD9_US033_AC2(http_client):
    _owner, owner_token = await _seed_author("kevin")
    co_author, co_token = await _seed_author("laura")
    book = await _create_book(http_client, owner_token)
    await _add_co_author(int(book["id"]), co_author.id)

    one = await _create_chapter(http_client, owner_token, book["id"], title="One")
    two = await _create_chapter(http_client, owner_token, book["id"], title="Two")
    before = await _stored_ordinals(book["id"])

    resp = await http_client.put(
        f"{_c_url(book['id'])}/order",
        headers=_auth_header(co_token),
        json={"chapter_ids": [two["id"], one["id"]]},
    )
    assert resp.status_code == 403, resp.text

    assert await _stored_ordinals(book["id"]) == before
    assert await _list_ids(http_client, owner_token, book["id"]) == [
        one["id"],
        two["id"],
    ]


# ---------------------------------------------------------------------------
# DoD-10: PUT on /order with a list that omits a chapter, adds an unknown id,
# repeats an id, or names another book's chapter returns 400 -- not 422: the body
# is structurally valid, a cross-row invariant fails -- and changes no ordinal.
# ---------------------------------------------------------------------------
def _omits_one(ids: list[str], foreign_id: str) -> list[str]:
    return ids[:-1]


def _adds_unknown(ids: list[str], foreign_id: str) -> list[str]:
    return [*ids, "999999999999"]


def _repeats_one(ids: list[str], foreign_id: str) -> list[str]:
    return [ids[0], ids[0], ids[2]]


def _names_another_books_chapter(ids: list[str], foreign_id: str) -> list[str]:
    return [ids[0], ids[1], foreign_id]


@pytest.mark.parametrize(
    "build_list",
    [
        pytest.param(_omits_one, id="omits_a_chapter"),
        pytest.param(_adds_unknown, id="adds_an_unknown_id"),
        pytest.param(_repeats_one, id="repeats_an_id"),
        pytest.param(_names_another_books_chapter, id="another_books_chapter"),
    ],
)
async def test_invalid_reorder_set_400_no_ordinal_changes__DoD10(
    http_client, build_list
):
    _owner, owner_token = await _seed_author("mike")
    book = await _create_book(http_client, owner_token, title="Mine")
    other = await _create_book(http_client, owner_token, title="Other")

    ids = [
        (await _create_chapter(http_client, owner_token, book["id"], title=t))["id"]
        for t in ("One", "Two", "Three")
    ]
    foreign = await _create_chapter(
        http_client, owner_token, other["id"], title="Foreign"
    )

    before = await _stored_ordinals(book["id"])
    before_other = await _stored_ordinals(other["id"])

    resp = await http_client.put(
        f"{_c_url(book['id'])}/order",
        headers=_auth_header(owner_token),
        json={"chapter_ids": build_list(ids, foreign["id"])},
    )
    assert resp.status_code == 400, resp.text

    assert await _stored_ordinals(book["id"]) == before
    assert await _stored_ordinals(other["id"]) == before_other
    assert await _list_ids(http_client, owner_token, book["id"]) == ids


# ---------------------------------------------------------------------------
# DoD-11: a co-author may POST, PATCH and DELETE; a logged-in NON-MEMBER of a
# PUBLIC book gets 403 from all three (the book resolves for them -- they are a
# reader -- so the service, not the dependency, refuses them).
# ---------------------------------------------------------------------------
async def test_co_author_may_create_patch_delete__DoD11(http_client):
    _owner, owner_token = await _seed_author("nina")
    co_author, co_token = await _seed_author("oscar")
    book = await _create_book(http_client, owner_token, visibility="public")
    await _add_co_author(int(book["id"]), co_author.id)

    created = await http_client.post(
        _c_url(book["id"]),
        headers=_auth_header(co_token),
        json={"title": "By the co-author", "sketch": "their sketch"},
    )
    assert created.status_code == 201, created.text
    chapter = created.json()

    patched = await http_client.patch(
        f"{_c_url(book['id'])}/{chapter['id']}",
        headers=_auth_header(co_token),
        json={"sketch": "their revised sketch"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["sketch"] == "their revised sketch"

    deleted = await http_client.delete(
        f"{_c_url(book['id'])}/{chapter['id']}", headers=_auth_header(co_token)
    )
    assert deleted.status_code == 204, deleted.text
    assert await _list_ids(http_client, owner_token, book["id"]) == []


@pytest.mark.parametrize(
    "verb",
    [
        pytest.param("create", id="create"),
        pytest.param("patch", id="patch"),
        pytest.param("delete", id="delete"),
    ],
)
async def test_non_member_of_public_book_403__DoD11(http_client, verb):
    _owner, owner_token = await _seed_author("paula")
    _outsider, outsider_token = await _seed_author("quinn")
    book = await _create_book(http_client, owner_token, visibility="public")
    chapter = await _create_chapter(http_client, owner_token, book["id"])

    if verb == "create":
        resp = await http_client.post(
            _c_url(book["id"]),
            headers=_auth_header(outsider_token),
            json={"title": "Not yours", "sketch": "s"},
        )
    elif verb == "patch":
        resp = await http_client.patch(
            f"{_c_url(book['id'])}/{chapter['id']}",
            headers=_auth_header(outsider_token),
            json={"sketch": "not yours"},
        )
    else:
        resp = await http_client.delete(
            f"{_c_url(book['id'])}/{chapter['id']}",
            headers=_auth_header(outsider_token),
        )

    assert resp.status_code == 403, resp.text

    # Nothing changed: the owner's collection is exactly as it was.
    assert await _list_ids(http_client, owner_token, book["id"]) == [chapter["id"]]


# ---------------------------------------------------------------------------
# DoD-12: a user with NO relationship to a PRIVATE book gets 404 from every route
# in the family -- existence hiding, inherited from the dependency.
# DoD-13: a request with NO TOKEN gets 401 from every route in the family.
# ---------------------------------------------------------------------------
def _list_request(book_id, chapter_id):
    return "GET", _c_url(book_id), None


def _create_request(book_id, chapter_id):
    return "POST", _c_url(book_id), {"title": "T", "sketch": "s"}


def _reorder_request(book_id, chapter_id):
    return "PUT", f"{_c_url(book_id)}/order", {"chapter_ids": [chapter_id]}


def _read_request(book_id, chapter_id):
    return "GET", f"{_c_url(book_id)}/{chapter_id}", None


def _sketch_request(book_id, chapter_id):
    return "PATCH", f"{_c_url(book_id)}/{chapter_id}", {"sketch": "s"}


def _delete_request(book_id, chapter_id):
    return "DELETE", f"{_c_url(book_id)}/{chapter_id}", None


EVERY_ROUTE = [
    pytest.param(_list_request, id="list"),
    pytest.param(_create_request, id="create"),
    pytest.param(_reorder_request, id="reorder"),
    pytest.param(_read_request, id="read"),
    pytest.param(_sketch_request, id="sketch"),
    pytest.param(_delete_request, id="delete"),
]


@pytest.mark.parametrize("build_request", EVERY_ROUTE)
async def test_private_book_stranger_gets_404_everywhere__DoD12(
    http_client, build_request
):
    _owner, owner_token = await _seed_author("rosa")
    _stranger, stranger_token = await _seed_author("sam")
    book = await _create_book(http_client, owner_token, visibility="private")
    chapter = await _create_chapter(http_client, owner_token, book["id"])

    method, url, json_body = build_request(book["id"], chapter["id"])

    resp = await http_client.request(
        method, url, headers=_auth_header(stranger_token), json=json_body
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.parametrize("build_request", EVERY_ROUTE)
async def test_no_token_gets_401_everywhere__DoD13(http_client, build_request):
    _owner, owner_token = await _seed_author("tina")
    book = await _create_book(http_client, owner_token, visibility="public")
    chapter = await _create_chapter(http_client, owner_token, book["id"])

    method, url, json_body = build_request(book["id"], chapter["id"])

    resp = await http_client.request(method, url, json=json_body)
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# DoD-14: addressing a chapter id that belongs to ANOTHER BOOK returns 404 -- not
# 403 and not 200 -- on the read, sketch and delete paths. The caller is a member
# of BOTH books, so the refusal is provably the book-scoping check and not an
# authorization failure.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "build_request",
    [
        pytest.param(_read_request, id="read"),
        pytest.param(_sketch_request, id="sketch"),
        pytest.param(_delete_request, id="delete"),
    ],
)
async def test_another_books_chapter_is_404__DoD14(http_client, build_request):
    _owner, owner_token = await _seed_author("uma")
    book_a = await _create_book(http_client, owner_token, title="A")
    book_b = await _create_book(http_client, owner_token, title="B")

    # Sanity: the caller is a member of BOTH books and can list each of them.
    await _list_body(http_client, owner_token, book_a["id"])
    await _list_body(http_client, owner_token, book_b["id"])

    foreign = await _create_chapter(
        http_client, owner_token, book_b["id"], title="Lives in B"
    )

    method, url, json_body = build_request(book_a["id"], foreign["id"])

    resp = await http_client.request(
        method, url, headers=_auth_header(owner_token), json=json_body
    )
    assert resp.status_code == 404, resp.text

    # Untouched in its own book.
    assert await _list_ids(http_client, owner_token, book_b["id"]) == [foreign["id"]]


# ---------------------------------------------------------------------------
# DoD-15: `can_reorder` is true in the OWNER's list response and false in a
# CO-AUTHOR's.
# ---------------------------------------------------------------------------
async def test_can_reorder_true_for_owner_false_for_co_author__DoD15(http_client):
    _owner, owner_token = await _seed_author("vera")
    co_author, co_token = await _seed_author("walt")
    book = await _create_book(http_client, owner_token)
    await _add_co_author(int(book["id"]), co_author.id)
    await _create_chapter(http_client, owner_token, book["id"])

    owner_body = await _list_body(http_client, owner_token, book["id"])
    assert owner_body["can_reorder"] is True

    co_body = await _list_body(http_client, co_token, book["id"])
    assert co_body["can_reorder"] is False


# ---------------------------------------------------------------------------
# DoD-16: PUT /order reaches the REORDER handler rather than a chapter-id route --
# the literal segment is not shadowed by the parameterised one. Evidence: the PUT
# answers 200 with the LIST envelope and applies the submitted order, while the
# parameterised chapter-id route treats "order" as an unknown chapter id (404).
# ---------------------------------------------------------------------------
async def test_put_order_reaches_the_reorder_handler__DoD16(http_client):
    _owner, owner_token = await _seed_author("xena")
    book = await _create_book(http_client, owner_token)
    one = await _create_chapter(http_client, owner_token, book["id"], title="One")
    two = await _create_chapter(http_client, owner_token, book["id"], title="Two")

    resp = await http_client.put(
        f"{_c_url(book['id'])}/order",
        headers=_auth_header(owner_token),
        json={"chapter_ids": [two["id"], one["id"]]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # The list envelope, not a single ChapterResponse -- so the reorder handler ran.
    ChapterListResponse.model_validate(body)
    assert "chapters" in body
    assert "can_reorder" in body
    assert [c["id"] for c in body["chapters"]] == [two["id"], one["id"]]

    # The parameterised route does NOT own the literal segment: addressed as a
    # chapter id, "order" is simply an id that resolves to nothing.
    as_chapter = await http_client.get(
        f"{_c_url(book['id'])}/order", headers=_auth_header(owner_token)
    )
    assert as_chapter.status_code == 404, as_chapter.text


# ---------------------------------------------------------------------------
# DoD-17: a malformed body on POST, PATCH or PUT /order (missing field, wrong
# type) is refused as a validation error and nothing is stored.
# ---------------------------------------------------------------------------
def _post_missing_field(book_id, chapter_id):
    return "POST", _c_url(book_id), {"title": "T"}


def _post_wrong_type(book_id, chapter_id):
    return "POST", _c_url(book_id), {"title": 17, "sketch": "s"}


def _patch_missing_field(book_id, chapter_id):
    return "PATCH", f"{_c_url(book_id)}/{chapter_id}", {}


def _patch_wrong_type(book_id, chapter_id):
    return "PATCH", f"{_c_url(book_id)}/{chapter_id}", {"sketch": 17}


def _order_missing_field(book_id, chapter_id):
    return "PUT", f"{_c_url(book_id)}/order", {}


def _order_wrong_type(book_id, chapter_id):
    return "PUT", f"{_c_url(book_id)}/order", {"chapter_ids": 17}


@pytest.mark.parametrize(
    "build_request",
    [
        pytest.param(_post_missing_field, id="post_missing_sketch"),
        pytest.param(_post_wrong_type, id="post_title_wrong_type"),
        pytest.param(_patch_missing_field, id="patch_missing_sketch"),
        pytest.param(_patch_wrong_type, id="patch_sketch_wrong_type"),
        pytest.param(_order_missing_field, id="order_missing_chapter_ids"),
        pytest.param(_order_wrong_type, id="order_chapter_ids_wrong_type"),
    ],
)
async def test_malformed_body_422_stores_nothing__DoD17(http_client, build_request):
    _owner, owner_token = await _seed_author("yuri")
    book = await _create_book(http_client, owner_token)
    one = await _create_chapter(
        http_client, owner_token, book["id"], title="One", sketch="untouched"
    )
    two = await _create_chapter(
        http_client, owner_token, book["id"], title="Two", sketch="untouched"
    )

    before = await _stored_ordinals(book["id"])

    method, url, json_body = build_request(book["id"], one["id"])
    resp = await http_client.request(
        method, url, headers=_auth_header(owner_token), json=json_body
    )
    assert resp.status_code == 422, resp.text

    # Nothing stored: no new chapter, no ordinal moved, no sketch rewritten.
    listed = await _list_body(http_client, owner_token, book["id"])
    assert [c["id"] for c in listed["chapters"]] == [one["id"], two["id"]]
    assert all(c["sketch"] == "untouched" for c in listed["chapters"])
    assert await _stored_ordinals(book["id"]) == before
