"""End-to-end tests for the side-chat start / finish routes and the two DTO fields
(feature 027.side-chats, step 002 -- DoD-1..DoD-7).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). Each test seeds its
own users, books, members, chats and message rows on the same process-global
engine the app uses, mirroring tests/routes/test_chats.py (helpers copied
verbatim -- every test module defines its own local helpers).

Bound to the frozen skeleton (status.md -> Skeleton -> Step 002), router
`app.routes.chats` with prefix "/api/books", every endpoint gated by
`Depends(authz.book_access)`:
    POST /{book_id}/chats/{chat_id}/side-chats                        -> 201 ChatResponse
    POST /{book_id}/chats/{chat_id}/side-chats/{side_chat_id}/finish  -> 200 ChatResponse
    GET  /{book_id}/chats/{chat_id}                                   -> 200 ChatDetailResponse
DTO fields: `ChatResponse.active_side_chat_id: str | None`,
`ChatMessageResponse.side_chat_id: str | None`. Error mapping:
`side_chat_already_active` -> 409, `side_chat_not_found` -> 404,
`side_chat_not_active` -> 409; another author's chat -> 404 (never 403).

Expected values come from the SPEC ONLY -- the step DoD, the Interface intent,
and context.md decisions D-A / D-D / D-E -- never from implementation internals.

Async tests use asyncio_mode = "auto".
"""

import datetime

from app.db import book_members, books, chat_messages, users
from app.db.engine import init_db, set_db_ready
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_member import BookMember, MemberRole
from app.models.chat import ChatMessage
from app.models.schemas.chats import ChatDetailResponse, ChatResponse
from app.models.user import User, UserRole
from app.services import auth


# ---------------------------------------------------------------------------
# Helpers -- copied from tests/routes/test_chats.py (local per module).
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


async def _seed_private_book(owner_id: int) -> Book:
    return await books.create(
        Book(
            title="A Book",
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt="",
            active_notes="",
        )
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


def _chats_url(book_id: int) -> str:
    return f"/api/books/{book_id}/chats"


async def _create_chat(http_client, token: str, book_id: int, **body) -> dict:
    payload = {"title": "A Chat", **body}
    resp = await http_client.post(
        _chats_url(book_id), headers=_auth_header(token), json=payload
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Side-chat helpers local to this module.
# ---------------------------------------------------------------------------


def _side_chats_url(book_id: int, chat_id: str) -> str:
    return f"{_chats_url(book_id)}/{chat_id}/side-chats"


def _finish_url(book_id: int, chat_id: str, side_chat_id: str) -> str:
    return f"{_side_chats_url(book_id, chat_id)}/{side_chat_id}/finish"


async def _seed_row(
    chat_id: int,
    *,
    role: str,
    content: str,
    position: int,
    side_chat_id: int | None = None,
) -> ChatMessage:
    return await chat_messages.create(
        ChatMessage(
            chat_id=chat_id,
            role=role,
            content=content,
            position=position,
            side_chat_id=side_chat_id,
        )
    )


async def _get_detail(http_client, token: str, book_id: int, chat_id: str) -> dict:
    resp = await http_client.get(
        f"{_chats_url(book_id)}/{chat_id}", headers=_auth_header(token)
    )
    assert resp.status_code == 200, resp.text
    ChatDetailResponse.model_validate(resp.json())
    return resp.json()


async def _start(http_client, token: str, book_id: int, chat_id: str):
    return await http_client.post(
        _side_chats_url(book_id, chat_id), headers=_auth_header(token)
    )


async def _finish(http_client, token: str, book_id: int, chat_id: str, sid: str):
    return await http_client.post(
        _finish_url(book_id, chat_id, sid), headers=_auth_header(token)
    )


# ---------------------------------------------------------------------------
# DoD-1 -- the wire half of "set apart": null fields with no side chat; a seeded
#          row's side_chat_id surfaces as a decimal string
# ---------------------------------------------------------------------------


# DoD-1 (D-E; US-135.AC-1): a chat with no side chat reads
# `chat.active_side_chat_id: null` and every message `side_chat_id: null`.
async def test_detail_null_side_chat_fields_without_side_chat__DoD1(http_client):
    author, token = await _seed_author("plain")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="no side")
    cid = int(chat["id"])
    await _seed_row(cid, role="user", content="q", position=0)
    await _seed_row(cid, role="assistant", content="a", position=1)

    detail = await _get_detail(http_client, token, book.id, chat["id"])

    assert detail["chat"]["active_side_chat_id"] is None
    assert len(detail["messages"]) == 2
    assert [m["side_chat_id"] for m in detail["messages"]] == [None, None]


# DoD-1 (D-E; US-135.AC-1): a message row seeded directly with a side-chat id is
# shown by the detail with `side_chat_id` equal to that id's decimal string,
# while an unstamped sibling row stays null and the pointer stays null.
async def test_detail_shows_seeded_row_side_chat_id_as_decimal_string__DoD1(
    http_client,
):
    author, token = await _seed_author("seeded")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="seeded")
    cid = int(chat["id"])
    sid = 770000000000000001
    await _seed_row(cid, role="user", content="main", position=0)
    await _seed_row(cid, role="user", content="side", position=1, side_chat_id=sid)

    detail = await _get_detail(http_client, token, book.id, chat["id"])

    by_content = {m["content"]: m["side_chat_id"] for m in detail["messages"]}
    assert by_content["main"] is None
    assert by_content["side"] == str(sid)
    assert type(by_content["side"]) is str
    # Seeding a row does not make the side chat active -- the pointer is the
    # server's, and nothing set it.
    assert detail["chat"]["active_side_chat_id"] is None


# ---------------------------------------------------------------------------
# DoD-2 -- start on a chat with messages: 201, pointer set, detail agrees
# ---------------------------------------------------------------------------


# DoD-2 (UC-110 steps 1-2; US-141.AC-1): POST .../side-chats on a chat that has
# messages and no active side chat answers 201 with a ChatResponse whose
# `active_side_chat_id` is a non-null decimal string; GET detail then shows the
# same value (the server holds the pointer).
async def test_start_side_chat_sets_pointer_and_detail_agrees__DoD2(http_client):
    author, token = await _seed_author("starter")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="with msgs")
    cid = int(chat["id"])
    await _seed_row(cid, role="user", content="hello", position=0)
    await _seed_row(cid, role="assistant", content="hi", position=1)

    resp = await _start(http_client, token, book.id, chat["id"])

    assert resp.status_code == 201, resp.text
    body = resp.json()
    ChatResponse.model_validate(body)
    assert body["id"] == chat["id"]
    sid = body["active_side_chat_id"]
    assert sid is not None
    assert type(sid) is str
    assert sid.isdigit()

    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] == sid
    # Starting stamps no existing row: the prior main-line rows stay main line.
    assert [m["side_chat_id"] for m in detail["messages"]] == [None, None]


# ---------------------------------------------------------------------------
# DoD-3 -- start on a chat with zero messages is allowed
# ---------------------------------------------------------------------------


# DoD-3 (UC-110 alternate flow): POST .../side-chats on a chat with no messages
# at all also answers 201 with the pointer set.
async def test_start_side_chat_on_empty_chat_is_allowed__DoD3(http_client):
    author, token = await _seed_author("emptystart")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="empty")

    resp = await _start(http_client, token, book.id, chat["id"])

    assert resp.status_code == 201, resp.text
    body = resp.json()
    ChatResponse.model_validate(body)
    assert body["active_side_chat_id"] is not None
    assert body["active_side_chat_id"].isdigit()

    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] == body["active_side_chat_id"]
    assert detail["messages"] == []


# ---------------------------------------------------------------------------
# DoD-4 -- a second start while one is active: 409, pointer unchanged
# ---------------------------------------------------------------------------


# DoD-4 (US-135.AC-2; D-D `side_chat_already_active` -> 409): a second POST
# .../side-chats while a side chat is active answers 409 and the pointer keeps
# its first value.
async def test_second_start_while_active_is_409_pointer_unchanged__DoD4(
    http_client,
):
    author, token = await _seed_author("twice")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="twice")
    await _seed_row(int(chat["id"]), role="user", content="hello", position=0)

    first = await _start(http_client, token, book.id, chat["id"])
    assert first.status_code == 201, first.text
    first_sid = first.json()["active_side_chat_id"]

    second = await _start(http_client, token, book.id, chat["id"])

    assert second.status_code == 409, second.text

    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] == first_sid


# ---------------------------------------------------------------------------
# DoD-5 -- finish the active side chat: 200, pointer null, rows keep their id
# ---------------------------------------------------------------------------


# DoD-5 (US-137.AC-1 server half; US-138.AC-2): finishing the active side chat
# answers 200 with `active_side_chat_id: null`; rows that carried the id STILL
# carry it and are still returned by GET detail.
async def test_finish_active_side_chat_clears_pointer_keeps_rows__DoD5(
    http_client,
):
    author, token = await _seed_author("finisher")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="finish")
    cid = int(chat["id"])
    await _seed_row(cid, role="user", content="main-q", position=0)

    started = await _start(http_client, token, book.id, chat["id"])
    assert started.status_code == 201, started.text
    sid = started.json()["active_side_chat_id"]
    # Rows produced "inside" the side chat carry the pointer's id.
    await _seed_row(cid, role="user", content="side-q", position=1, side_chat_id=int(sid))
    await _seed_row(cid, role="assistant", content="side-a", position=2, side_chat_id=int(sid))

    resp = await _finish(http_client, token, book.id, chat["id"], sid)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    ChatResponse.model_validate(body)
    assert body["id"] == chat["id"]
    assert body["active_side_chat_id"] is None

    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] is None
    assert [m["content"] for m in detail["messages"]] == ["main-q", "side-q", "side-a"]
    assert [m["side_chat_id"] for m in detail["messages"]] == [None, sid, sid]


# DoD-5 (D-D: "finish of an active side chat with zero rows just clears the
# pointer"): finishing an active side chat that has received no rows answers 200
# with the pointer cleared.
async def test_finish_active_side_chat_with_zero_rows_clears_pointer__DoD5(
    http_client,
):
    author, token = await _seed_author("emptyfinish")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="empty finish")

    started = await _start(http_client, token, book.id, chat["id"])
    assert started.status_code == 201, started.text
    sid = started.json()["active_side_chat_id"]

    resp = await _finish(http_client, token, book.id, chat["id"], sid)

    assert resp.status_code == 200, resp.text
    assert resp.json()["active_side_chat_id"] is None
    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] is None
    assert detail["messages"] == []


# ---------------------------------------------------------------------------
# DoD-6 -- finish error taxonomy: finished -> 409; unknown / non-numeric -> 404
# ---------------------------------------------------------------------------


# DoD-6 (D-D `side_chat_not_active` -> 409): finishing an id that rows carry but
# which is not the pointer (a finished side chat) answers 409.
async def test_finish_finished_side_chat_is_409__DoD6(http_client):
    author, token = await _seed_author("refinish")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="refinish")
    cid = int(chat["id"])
    finished_sid = 424242
    # A finished side chat: rows carry the id, the pointer is null.
    await _seed_row(cid, role="user", content="old-side", position=0, side_chat_id=finished_sid)
    await _seed_row(cid, role="assistant", content="old-side-a", position=1, side_chat_id=finished_sid)

    resp = await _finish(http_client, token, book.id, chat["id"], str(finished_sid))

    assert resp.status_code == 409, resp.text
    # Nothing moved: the rows still carry the id, the pointer is still null.
    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] is None
    assert [m["side_chat_id"] for m in detail["messages"]] == [
        str(finished_sid),
        str(finished_sid),
    ]


# DoD-6 (D-D `side_chat_not_found` -> 404): finishing an id nobody carries -- not
# the pointer, not on any row -- answers 404, even while another side chat is
# active.
async def test_finish_unknown_side_chat_id_is_404__DoD6(http_client):
    author, token = await _seed_author("unknownfinish")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="unknown")
    cid = int(chat["id"])
    await _seed_row(cid, role="user", content="side", position=0, side_chat_id=111111)

    started = await _start(http_client, token, book.id, chat["id"])
    assert started.status_code == 201, started.text
    active_sid = started.json()["active_side_chat_id"]

    resp = await _finish(http_client, token, book.id, chat["id"], "999999999")

    assert resp.status_code == 404, resp.text
    # The active side chat is untouched by the refused finish.
    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] == active_sid


# DoD-6 (D-D: a non-numeric id is `side_chat_not_found` -> 404, never FastAPI's
# 422): finishing with a non-numeric side-chat id answers 404.
async def test_finish_non_numeric_side_chat_id_is_404__DoD6(http_client):
    author, token = await _seed_author("nonnumeric")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="non-numeric")

    started = await _start(http_client, token, book.id, chat["id"])
    assert started.status_code == 201, started.text
    active_sid = started.json()["active_side_chat_id"]

    resp = await _finish(http_client, token, book.id, chat["id"], "not-a-number")

    assert resp.status_code == 404, resp.text
    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] == active_sid


# ---------------------------------------------------------------------------
# DoD-7 -- ownership: another author's chat -> 404 (never 403); stranger -> 404
# ---------------------------------------------------------------------------


# DoD-7 (US-061 inherited; authorization.md -> chat row ownership): a co-author
# of the same book who does not own the chat gets 404 -- never 403 -- from both
# start and finish, and the owner's chat state is untouched.
async def test_start_and_finish_on_other_authors_chat_are_404__DoD7(http_client):
    owner, owner_token = await _seed_author("chat_owner")
    other, other_token = await _seed_author("same_book_author")
    book = await _seed_private_book(owner.id)
    await _add_co_author(book.id, other.id)
    chat = await _create_chat(http_client, owner_token, book.id, title="owned")

    # Start on someone else's chat.
    start_resp = await _start(http_client, other_token, book.id, chat["id"])
    assert start_resp.status_code == 404, start_resp.text
    assert start_resp.status_code != 403

    # The owner opens a side chat; the other author cannot finish it either.
    started = await _start(http_client, owner_token, book.id, chat["id"])
    assert started.status_code == 201, started.text
    sid = started.json()["active_side_chat_id"]

    finish_resp = await _finish(http_client, other_token, book.id, chat["id"], sid)
    assert finish_resp.status_code == 404, finish_resp.text
    assert finish_resp.status_code != 403

    # The owner's pointer survived both attempts.
    detail = await _get_detail(http_client, owner_token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] == sid


# DoD-7 (authorization.md): a logged-in caller with no relationship to the
# private book gets 404 from both start and finish.
async def test_start_and_finish_by_stranger_are_404__DoD7(http_client):
    owner, owner_token = await _seed_author("private_owner")
    _stranger, stranger_token = await _seed_author("total_stranger")
    book = await _seed_private_book(owner.id)
    chat = await _create_chat(http_client, owner_token, book.id, title="private")

    started = await _start(http_client, owner_token, book.id, chat["id"])
    assert started.status_code == 201, started.text
    sid = started.json()["active_side_chat_id"]

    start_resp = await _start(http_client, stranger_token, book.id, chat["id"])
    assert start_resp.status_code == 404, start_resp.text

    finish_resp = await _finish(http_client, stranger_token, book.id, chat["id"], sid)
    assert finish_resp.status_code == 404, finish_resp.text

    detail = await _get_detail(http_client, owner_token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] == sid
