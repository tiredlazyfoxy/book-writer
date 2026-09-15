"""End-to-end tests for `PUT /api/books/{book_id}/memos/order` (026, step 004).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network), mirroring
tests/routes/test_memos.py. Auth is real: a seeded user row plus a minted JWT.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 004):
    class ReorderMemosRequest(BaseModel)    memo_ids: list[str]
    PUT /{book_id}/memos/order  ->  200 MemoListResponse
                                    (envelope key `items`, ids as strings)
    MemoErrorReason.invalid_reorder_set -> 400 (NOT 422: the body is
        structurally valid and the refusal is a business-rule one)
    declared BEFORE `PUT /{book_id}/memos/{memo_id}`, which stays last.

Expected values come from the SPEC ONLY -- `004.memo-reorder.md`
(DoD-1..DoD-8), `004.context.md`, and the feature `context.md` ("The wire
contract", the status taxonomy, decision 4's archived-book carve-out) -- never
from implementation internals:

    - DoD-1 (US-126.AC-2): the full id list in a new order answers 200 with
      ordinals rewritten 1..N in that order;
    - DoD-2 (US-131.AC-2): the following GET returns them in the submitted
      order;
    - DoD-3: every invalid set -- too short, too long, duplicated, carrying an
      id outside the caller's non-archived set -- answers **400**, and the list
      afterwards is unchanged (nothing was written);
    - DoD-4 (US-124.AC-1): another author's id and another book's id are refused
      exactly as an id belonging to nobody is -- no existence oracle;
    - DoD-5 (US-128.AC-1): an archived memo's id in the list is refused;
    - DoD-6: `PUT .../memos/order` resolves to the reorder handler and is never
      captured by `/{memo_id}`, while a real memo id on `/{memo_id}` still
      reaches the body-update handler;
    - DoD-7: no token -> 401; no relationship to a private book -> 404; a
      logged-in non-member of a visible book -> 403;
    - DoD-8: a reorder succeeds on a book whose state is `archived`.

Archived memo rows are seeded through the db/ layer directly -- step 005's
archive route does not exist for this step's tests to depend on.

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
from app.models.schemas.memos import MemoListResponse
from app.models.user import User, UserRole
from app.services import auth

# ---------------------------------------------------------------------------
# Seed helpers -- copied from tests/routes/test_memos.py (there is no shared
# factory module)
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
    """A book anyone logged in can see -- DoD-7's 403 fixture."""
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


# ---------------------------------------------------------------------------
# Local URL / call helpers
# ---------------------------------------------------------------------------


def _list_url(book_id: int) -> str:
    return f"/api/books/{book_id}/memos"


def _order_url(book_id: int) -> str:
    return f"/api/books/{book_id}/memos/order"


def _memo_url(book_id: int, memo_id: object) -> str:
    return f"/api/books/{book_id}/memos/{memo_id}"


async def _list_memos(http_client, token: str, book_id: int) -> MemoListResponse:
    resp = await http_client.get(_list_url(book_id), headers=_auth_header(token))
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "items" in payload, payload
    return MemoListResponse.model_validate(payload)


async def _reorder(http_client, token: str, book_id: int, memo_ids: list[str]):
    return await http_client.put(
        _order_url(book_id),
        headers=_auth_header(token),
        json={"memo_ids": memo_ids},
    )


async def _seed_three(book_id: int, user_id: int) -> tuple[Memo, Memo, Memo]:
    first = await _seed_memo(book_id, user_id, "A", 1)
    second = await _seed_memo(book_id, user_id, "B", 2)
    third = await _seed_memo(book_id, user_id, "C", 3)
    return first, second, third


async def _stored_ordinals(*rows: Memo) -> list[int]:
    out: list[int] = []
    for row in rows:
        stored = await memos_db.get_by_id(row.id)
        assert stored is not None
        out.append(stored.ordinal)
    return out


# ---------------------------------------------------------------------------
# DoD-1 (US-126.AC-2) -- the endpoint rewrites ordinals 1..N
# ---------------------------------------------------------------------------


# DoD-1: a well-formed full id list answers 200 with the list envelope, ordinals
# rewritten 1..N in the submitted order.
async def test_reorder_answers_200_with_ordinals_one_to_n__DoD1(http_client):
    owner, token = await _seed_author("memo_order_owner_1")
    book = await _seed_private_book(owner.id)
    first, second, third = await _seed_three(book.id, owner.id)

    resp = await _reorder(
        http_client, token, book.id, [str(third.id), str(first.id), str(second.id)]
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "items" in payload, payload
    listed = MemoListResponse.model_validate(payload)
    assert [m.body for m in listed.items] == ["C", "A", "B"]
    assert [m.ordinal for m in listed.items] == [1, 2, 3]
    # ids stay strings on the wire, and no user_id is echoed
    assert all(isinstance(item["id"], str) for item in payload["items"])
    assert all("user_id" not in item for item in payload["items"])
    assert await _stored_ordinals(first, second, third) == [2, 3, 1]


# ---------------------------------------------------------------------------
# DoD-2 (US-131.AC-2) -- the read after the reorder is the submitted order
# ---------------------------------------------------------------------------


# DoD-2: the author's order IS the order the list is read back in -- a plain GET
# after a reorder returns exactly the submitted sequence.
async def test_get_after_reorder_returns_the_submitted_order__DoD2(http_client):
    owner, token = await _seed_author("memo_order_owner_2")
    book = await _seed_private_book(owner.id)
    first, second, third = await _seed_three(book.id, owner.id)

    resp = await _reorder(
        http_client, token, book.id, [str(second.id), str(third.id), str(first.id)]
    )
    assert resp.status_code == 200, resp.text

    listed = await _list_memos(http_client, token, book.id)
    assert [m.body for m in listed.items] == ["B", "C", "A"]
    assert [m.ordinal for m in listed.items] == [1, 2, 3]


# ---------------------------------------------------------------------------
# DoD-3 -- every invalid set is a 400, and nothing is written
# ---------------------------------------------------------------------------


# DoD-3: four separately-seeded invalid sets -- too short, too long, one with a
# duplicate id, one carrying an id outside the caller's non-archived set -- each
# answer 400 (NOT 422: the body is structurally valid), and the stored ordinals
# are unchanged after each refusal.
async def test_every_invalid_set_is_400_and_writes_nothing__DoD3(http_client):
    owner, token = await _seed_author("memo_order_owner_3")
    book = await _seed_private_book(owner.id)
    first, second, third = await _seed_three(book.id, owner.id)
    ids = [str(first.id), str(second.id), str(third.id)]

    invalid_sets = {
        "too short": ids[:2],
        "too long": ids + ["987654321"],
        "duplicate": [ids[0], ids[0], ids[1]],
        "not in the caller's set": [ids[0], ids[1], "987654321"],
    }

    for label, memo_ids in invalid_sets.items():
        resp = await _reorder(http_client, token, book.id, memo_ids)
        assert resp.status_code == 400, f"{label}: {resp.status_code} {resp.text}"
        # nothing written: the ordinals are exactly as seeded
        assert await _stored_ordinals(first, second, third) == [1, 2, 3], label
        # ...and the list the author reads is untouched too
        listed = await _list_memos(http_client, token, book.id)
        assert [m.body for m in listed.items] == ["A", "B", "C"], label


# ---------------------------------------------------------------------------
# DoD-4 (US-124.AC-1) -- foreign ids are refused with no existence oracle
# ---------------------------------------------------------------------------


# DoD-4: another author's memo id, another book's memo id and an id belonging to
# nobody are all refused as ONE invalid set -- same status and same response
# body, so nothing reveals whether the id exists.
async def test_foreign_ids_are_refused_indistinguishably__DoD4(http_client):
    owner, token = await _seed_author("memo_order_owner_4")
    co_author, co_token = await _seed_author("memo_order_co_author_4")
    book = await _seed_private_book(owner.id)
    await _add_co_author(book.id, co_author.id)
    other_book = await _seed_private_book(owner.id, title="Another Book")

    first, second, _third = await _seed_three(book.id, owner.id)
    theirs = await _seed_memo(book.id, co_author.id, "THEIRS", 1)
    elsewhere = await _seed_memo(other_book.id, owner.id, "ELSEWHERE", 1)

    fingerprints: set[str] = set()
    for foreign_id in (str(theirs.id), str(elsewhere.id), "987654321"):
        resp = await _reorder(
            http_client,
            token,
            book.id,
            [str(first.id), str(second.id), foreign_id],
        )
        assert resp.status_code == 400, resp.text
        fingerprints.add(json.dumps(resp.json(), sort_keys=True))

    # one refusal, not three
    assert len(fingerprints) == 1

    # the foreign rows were not written, and the co-author still sees their memo
    assert await _stored_ordinals(theirs, elsewhere) == [1, 1]
    co_listed = await _list_memos(http_client, co_token, book.id)
    assert [m.body for m in co_listed.items] == ["THEIRS"]


# ---------------------------------------------------------------------------
# DoD-5 (US-128.AC-1) -- archived memos are outside the submitted set
# ---------------------------------------------------------------------------


# DoD-5: including an archived memo's id is refused with 400, and a successful
# reorder of the survivors leaves the archived row's ordinal untouched --
# archiving left a gap and reorder does not reclaim it.
async def test_archived_memos_are_outside_the_reorder_set__DoD5(http_client):
    owner, token = await _seed_author("memo_order_owner_5")
    book = await _seed_private_book(owner.id)
    live_a = await _seed_memo(book.id, owner.id, "A", 1)
    archived = await _seed_memo(book.id, owner.id, "GONE", 2, archived=True)
    live_c = await _seed_memo(book.id, owner.id, "C", 3)

    # (a) the archived id inside the submitted list is refused
    refused = await _reorder(
        http_client,
        token,
        book.id,
        [str(live_c.id), str(live_a.id), str(archived.id)],
    )
    assert refused.status_code == 400, refused.text
    assert await _stored_ordinals(live_a, archived, live_c) == [1, 2, 3]

    # (b) the survivors alone are the valid set, and the archived ordinal stays
    accepted = await _reorder(
        http_client, token, book.id, [str(live_c.id), str(live_a.id)]
    )
    assert accepted.status_code == 200, accepted.text
    listed = MemoListResponse.model_validate(accepted.json())
    assert [m.body for m in listed.items] == ["C", "A"]
    assert [m.ordinal for m in listed.items] == [1, 2]
    assert await _stored_ordinals(live_c, live_a, archived) == [1, 2, 2]


# ---------------------------------------------------------------------------
# DoD-6 -- route ordering: `order` is never swallowed by `/{memo_id}`
# ---------------------------------------------------------------------------


# DoD-6 (quick-reference.md -> the memos route table): the literal `order`
# segment reaches the reorder handler. A well-formed reorder body succeeds,
# while the SAME path carrying the body-update handler's body shape is NOT
# interpreted as a memo id -- if `/{memo_id}` had captured it, `{"body": ...}`
# would be a valid update of a memo called "order" (404), never a validation
# failure of the reorder request.
async def test_order_path_reaches_the_reorder_handler__DoD6(http_client):
    owner, token = await _seed_author("memo_order_owner_6a")
    book = await _seed_private_book(owner.id)
    first, second, third = await _seed_three(book.id, owner.id)

    ok = await _reorder(
        http_client, token, book.id, [str(third.id), str(second.id), str(first.id)]
    )
    assert ok.status_code == 200, ok.text

    swallowed = await http_client.put(
        _order_url(book.id),
        headers=_auth_header(token),
        json={"body": "if this were an update, `order` would be a memo id"},
    )
    assert swallowed.status_code == 422, swallowed.text
    assert swallowed.status_code != 404
    assert swallowed.status_code != 200


# DoD-6: the `/{memo_id}` route is intact -- a real memo id on that path still
# reaches the body-update handler.
async def test_memo_id_path_still_reaches_the_body_update_handler__DoD6(http_client):
    owner, token = await _seed_author("memo_order_owner_6b")
    book = await _seed_private_book(owner.id)
    memo = await _seed_memo(book.id, owner.id, "OLD", 1)

    resp = await http_client.put(
        _memo_url(book.id, memo.id),
        headers=_auth_header(token),
        json={"body": "NEW"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["body"] == "NEW"
    assert resp.json()["ordinal"] == 1


# DoD-6: the two paths are distinct entries on the published contract -- the
# literal segment is a path of its own, not a value of `{memo_id}`.
async def test_order_is_a_distinct_published_path__DoD6(http_client):
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/books/{book_id}/memos/order" in paths
    assert "put" in paths["/api/books/{book_id}/memos/order"]
    assert "/api/books/{book_id}/memos/{memo_id}" in paths
    assert "put" in paths["/api/books/{book_id}/memos/{memo_id}"]


# ---------------------------------------------------------------------------
# DoD-7 -- the status taxonomy on the reorder path
# ---------------------------------------------------------------------------


# DoD-7 (authorization.md -> the memo status table): no Authorization header at
# all is a 401.
async def test_missing_token_is_401__DoD7(http_client):
    owner, token = await _seed_author("memo_order_owner_7a")
    book = await _seed_private_book(owner.id)
    first, second, _third = await _seed_three(book.id, owner.id)

    resp = await http_client.put(
        _order_url(book.id), json={"memo_ids": [str(second.id), str(first.id)]}
    )

    assert resp.status_code == 401


# DoD-7 (authorization.md -> "Failure modes"): a logged-in caller with no
# relationship at all to a PRIVATE book is answered 404 -- existence hiding.
async def test_stranger_on_private_book_is_404__DoD7(http_client):
    owner, _owner_token = await _seed_author("memo_order_owner_7b")
    _stranger, stranger_token = await _seed_author("memo_order_stranger_7b")
    book = await _seed_private_book(owner.id)
    first, second, _third = await _seed_three(book.id, owner.id)

    resp = await _reorder(
        http_client, stranger_token, book.id, [str(second.id), str(first.id)]
    )

    assert resp.status_code == 404
    assert await _stored_ordinals(first, second) == [1, 2]


# DoD-7 (authorization.md -> the memo status table): a logged-in caller who CAN
# see the book but is not a member is refused with 403, and nothing is written.
async def test_non_member_of_visible_book_is_403__DoD7(http_client):
    owner, _owner_token = await _seed_author("memo_order_owner_7c")
    _reader, reader_token = await _seed_author("memo_order_reader_7c")
    book = await _seed_public_book(owner.id)
    first, second, third = await _seed_three(book.id, owner.id)

    resp = await _reorder(
        http_client,
        reader_token,
        book.id,
        [str(third.id), str(second.id), str(first.id)],
    )

    assert resp.status_code == 403
    assert await _stored_ordinals(first, second, third) == [1, 2, 3]


# ---------------------------------------------------------------------------
# DoD-8 -- the archived-book carve-out
# ---------------------------------------------------------------------------


# DoD-8 (context.md -> decision 4): a memo is the author's private note ABOUT a
# book they have set aside, so a reorder succeeds while the book's state is
# `archived` -- unlike chapters, which refuse writes there.
async def test_reorder_succeeds_on_an_archived_book__DoD8(http_client):
    owner, token = await _seed_author("memo_order_owner_8")
    book = await _seed_private_book(owner.id)
    first, second, third = await _seed_three(book.id, owner.id)

    book.state = BookState.archived
    await books.update(book)

    resp = await _reorder(
        http_client, token, book.id, [str(third.id), str(second.id), str(first.id)]
    )

    assert resp.status_code == 200, resp.text
    listed = MemoListResponse.model_validate(resp.json())
    assert [m.body for m in listed.items] == ["C", "B", "A"]
    assert [m.ordinal for m in listed.items] == [1, 2, 3]
