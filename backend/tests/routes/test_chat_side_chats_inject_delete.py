"""End-to-end tests for the side-chat inject / delete routes
(feature 027.side-chats, step 003 -- DoD-1, 2, 4, 5, 6, 7, 9, 10).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). Each test seeds its
own users, books, members, chats and message rows on the same process-global
engine the app uses, mirroring tests/routes/test_chats.py and
tests/routes/test_chat_side_chats.py (helpers copied verbatim -- every test
module defines its own local helpers).

Bound to the frozen skeleton (status.md -> Skeleton -> Steps 002 / 003), router
`app.routes.chats` with prefix "/api/books", every endpoint gated by
`Depends(authz.book_access)`:
    POST   /{book_id}/chats/{chat_id}/side-chats                        -> 201 ChatResponse
    POST   /{book_id}/chats/{chat_id}/side-chats/{side_chat_id}/inject  -> 200 ChatDetailResponse
    DELETE /{book_id}/chats/{chat_id}/side-chats/{side_chat_id}         -> 204, no body
    GET    /{book_id}/chats/{chat_id}                                   -> 200 ChatDetailResponse
    POST   /{book_id}/codex                                             -> 201 (DoD-7)
    GET    /{book_id}/codex/{entry_id}                                  -> 200 (DoD-7)
Error mapping: `side_chat_not_found` -> 404 (unknown id, non-numeric id);
another author's chat -> 404 (never 403).

A "finished" side chat is seeded as rows carrying `side_chat_id=<int>` with a
null pointer; an "active" one is opened through `POST .../side-chats`.

Expected values come from the SPEC ONLY -- the step DoD, the Interface intent,
and context.md decision D-D -- never from implementation internals.

Async tests use asyncio_mode = "auto".
"""

import datetime

from app.db import book_members, books, chat_messages, users
from app.db.engine import init_db, set_db_ready
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_member import BookMember, MemberRole
from app.models.chat import ChatMessage
from app.models.schemas.chats import ChatDetailResponse
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
# Side-chat helpers -- copied from tests/routes/test_chat_side_chats.py, plus
# the inject / delete / codex URLs local to this module.
# ---------------------------------------------------------------------------


def _side_chats_url(book_id: int, chat_id: str) -> str:
    return f"{_chats_url(book_id)}/{chat_id}/side-chats"


def _inject_url(book_id: int, chat_id: str, side_chat_id: str) -> str:
    return f"{_side_chats_url(book_id, chat_id)}/{side_chat_id}/inject"


def _delete_url(book_id: int, chat_id: str, side_chat_id: str) -> str:
    return f"{_side_chats_url(book_id, chat_id)}/{side_chat_id}"


def _codex_url(book_id: int) -> str:
    return f"/api/books/{book_id}/codex"


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


async def _inject(http_client, token: str, book_id: int, chat_id: str, sid: str):
    return await http_client.post(
        _inject_url(book_id, chat_id, sid), headers=_auth_header(token)
    )


async def _delete(http_client, token: str, book_id: int, chat_id: str, sid: str):
    return await http_client.delete(
        _delete_url(book_id, chat_id, sid), headers=_auth_header(token)
    )


def _snapshot(detail: dict) -> list[tuple[str, int, str | None]]:
    """(content, position, side_chat_id) per row, in response order."""
    return [
        (m["content"], m["position"], m["side_chat_id"]) for m in detail["messages"]
    ]


async def _start_active(http_client, token: str, book_id: int, chat_id: str) -> str:
    """Open a side chat and return its wire id (decimal string)."""
    started = await _start(http_client, token, book_id, chat_id)
    assert started.status_code == 201, started.text
    sid = started.json()["active_side_chat_id"]
    assert sid is not None
    return sid


# Two finished side chats, seeded directly (rows carry the id; pointer null).
SID_A = 770000000000000101
SID_B = 770000000000000102


async def _seed_two_finished(cid: int) -> None:
    """main(0) | A(1,2) | main(3) | B(4,5) -- every group contiguous (D-B)."""
    await _seed_row(cid, role="user", content="main-0", position=0)
    await _seed_row(cid, role="user", content="a-1", position=1, side_chat_id=SID_A)
    await _seed_row(cid, role="assistant", content="a-2", position=2, side_chat_id=SID_A)
    await _seed_row(cid, role="assistant", content="main-3", position=3)
    await _seed_row(cid, role="user", content="b-4", position=4, side_chat_id=SID_B)
    await _seed_row(cid, role="assistant", content="b-5", position=5, side_chat_id=SID_B)


TWO_FINISHED_SNAPSHOT = [
    ("main-0", 0, None),
    ("a-1", 1, str(SID_A)),
    ("a-2", 2, str(SID_A)),
    ("main-3", 3, None),
    ("b-4", 4, str(SID_B)),
    ("b-5", 5, str(SID_B)),
]


# ---------------------------------------------------------------------------
# DoD-1 -- inject a finished side chat: 200, its rows become main line in place
# ---------------------------------------------------------------------------


# DoD-1 (US-139.AC-1): injecting a finished side chat answers 200 with a
# ChatDetailResponse in which every row that carried the id now has
# `side_chat_id: null`, rows keep their `position` values and relative order,
# and every other row (main line, the other finished side chat) is unchanged.
async def test_inject_finished_side_chat_rows_become_main_line_in_place__DoD1(
    http_client,
):
    author, token = await _seed_author("inject_finished")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="inject")
    cid = int(chat["id"])
    await _seed_two_finished(cid)

    resp = await _inject(http_client, token, book.id, chat["id"], str(SID_A))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    ChatDetailResponse.model_validate(body)
    assert body["chat"]["id"] == chat["id"]
    assert _snapshot(body) == [
        ("main-0", 0, None),
        ("a-1", 1, None),
        ("a-2", 2, None),
        ("main-3", 3, None),
        ("b-4", 4, str(SID_B)),
        ("b-5", 5, str(SID_B)),
    ]
    # The pointer was null (finished side chat) and stays null.
    assert body["chat"]["active_side_chat_id"] is None

    # A following GET shows the same state -- the inject persisted.
    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert _snapshot(detail) == _snapshot(body)
    assert detail["chat"]["active_side_chat_id"] is None


# ---------------------------------------------------------------------------
# DoD-2 -- inject the ACTIVE side chat: 200, pointer null, rows main line
# ---------------------------------------------------------------------------


# DoD-2 (UC-112 step 2): injecting the active side chat answers 200 with
# `chat.active_side_chat_id: null` and its rows' `side_chat_id: null`.
async def test_inject_active_side_chat_clears_pointer_and_rows__DoD2(http_client):
    author, token = await _seed_author("inject_active")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="inject active")
    cid = int(chat["id"])
    await _seed_row(cid, role="user", content="main-0", position=0)
    sid = await _start_active(http_client, token, book.id, chat["id"])
    await _seed_row(cid, role="user", content="side-1", position=1, side_chat_id=int(sid))
    await _seed_row(cid, role="assistant", content="side-2", position=2, side_chat_id=int(sid))

    resp = await _inject(http_client, token, book.id, chat["id"], sid)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    ChatDetailResponse.model_validate(body)
    assert body["chat"]["active_side_chat_id"] is None
    assert _snapshot(body) == [
        ("main-0", 0, None),
        ("side-1", 1, None),
        ("side-2", 2, None),
    ]

    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] is None
    assert [m["side_chat_id"] for m in detail["messages"]] == [None, None, None]


# ---------------------------------------------------------------------------
# DoD-4 -- inject refusals: unknown id, non-numeric id, another author's chat
# ---------------------------------------------------------------------------


# DoD-4 (D-D `side_chat_not_found` -> 404): injecting an id nobody carries --
# not the pointer, not on any row -- answers 404; the chat and its rows are
# unchanged (the active pointer included).
async def test_inject_unknown_side_chat_id_is_404_and_changes_nothing__DoD4(
    http_client,
):
    author, token = await _seed_author("inject_unknown")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="unknown")
    cid = int(chat["id"])
    await _seed_two_finished(cid)
    active_sid = await _start_active(http_client, token, book.id, chat["id"])
    before = await _get_detail(http_client, token, book.id, chat["id"])

    resp = await _inject(http_client, token, book.id, chat["id"], "999999999")

    assert resp.status_code == 404, resp.text
    after = await _get_detail(http_client, token, book.id, chat["id"])
    assert _snapshot(after) == TWO_FINISHED_SNAPSHOT
    assert _snapshot(after) == _snapshot(before)
    assert after["chat"]["active_side_chat_id"] == active_sid


# DoD-4 (D-D: a non-numeric id is `side_chat_not_found` -> 404, never FastAPI's
# 422): injecting with a non-numeric side-chat id answers 404 and changes
# nothing.
async def test_inject_non_numeric_side_chat_id_is_404_and_changes_nothing__DoD4(
    http_client,
):
    author, token = await _seed_author("inject_nonnumeric")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="non-numeric")
    cid = int(chat["id"])
    await _seed_two_finished(cid)
    active_sid = await _start_active(http_client, token, book.id, chat["id"])

    resp = await _inject(http_client, token, book.id, chat["id"], "not-a-number")

    assert resp.status_code == 404, resp.text
    assert resp.status_code != 422
    after = await _get_detail(http_client, token, book.id, chat["id"])
    assert _snapshot(after) == TWO_FINISHED_SNAPSHOT
    assert after["chat"]["active_side_chat_id"] == active_sid


# DoD-4 (US-061 inherited; D-D: another author's chat -> 404, never 403): a
# co-author of the same book who does not own the chat cannot inject -- 404 --
# and the owner's rows still carry the side-chat id.
async def test_inject_on_other_authors_chat_is_404_and_changes_nothing__DoD4(
    http_client,
):
    owner, owner_token = await _seed_author("inject_owner")
    other, other_token = await _seed_author("inject_same_book_author")
    book = await _seed_private_book(owner.id)
    await _add_co_author(book.id, other.id)
    chat = await _create_chat(http_client, owner_token, book.id, title="owned")
    cid = int(chat["id"])
    await _seed_two_finished(cid)

    resp = await _inject(http_client, other_token, book.id, chat["id"], str(SID_A))

    assert resp.status_code == 404, resp.text
    assert resp.status_code != 403
    after = await _get_detail(http_client, owner_token, book.id, chat["id"])
    assert _snapshot(after) == TWO_FINISHED_SNAPSHOT
    assert after["chat"]["active_side_chat_id"] is None


# ---------------------------------------------------------------------------
# DoD-5 -- delete a finished side chat: 204 empty body, its rows gone, the
#          survivors keep their positions
# ---------------------------------------------------------------------------


# DoD-5 (US-140.AC-3): deleting a finished side chat answers 204 with an empty
# body; a following GET detail contains no row that carried the id, and every
# other row is present with its `position` unchanged (no renumbering, D-D).
async def test_delete_finished_side_chat_removes_its_rows_keeps_positions__DoD5(
    http_client,
):
    author, token = await _seed_author("delete_finished")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="delete")
    cid = int(chat["id"])
    await _seed_two_finished(cid)

    resp = await _delete(http_client, token, book.id, chat["id"], str(SID_A))

    assert resp.status_code == 204, resp.text
    assert resp.content == b""

    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert _snapshot(detail) == [
        ("main-0", 0, None),
        ("main-3", 3, None),
        ("b-4", 4, str(SID_B)),
        ("b-5", 5, str(SID_B)),
    ]
    assert all(m["side_chat_id"] != str(SID_A) for m in detail["messages"])
    assert detail["chat"]["active_side_chat_id"] is None


# ---------------------------------------------------------------------------
# DoD-6 -- delete the ACTIVE side chat: 204, pointer null, none of its rows
# ---------------------------------------------------------------------------


# DoD-6 (UC-113 step 4; D-D): deleting the active side chat answers 204; a
# following GET detail shows `active_side_chat_id: null` and none of its rows,
# while the main-line rows around it are still there.
async def test_delete_active_side_chat_clears_pointer_and_removes_rows__DoD6(
    http_client,
):
    author, token = await _seed_author("delete_active")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="delete active")
    cid = int(chat["id"])
    await _seed_row(cid, role="user", content="main-0", position=0)
    await _seed_row(cid, role="assistant", content="main-1", position=1)
    sid = await _start_active(http_client, token, book.id, chat["id"])
    await _seed_row(cid, role="user", content="side-2", position=2, side_chat_id=int(sid))
    await _seed_row(cid, role="assistant", content="side-3", position=3, side_chat_id=int(sid))

    resp = await _delete(http_client, token, book.id, chat["id"], sid)

    assert resp.status_code == 204, resp.text
    assert resp.content == b""

    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] is None
    assert _snapshot(detail) == [("main-0", 0, None), ("main-1", 1, None)]
    assert all(m["side_chat_id"] != sid for m in detail["messages"])


# ---------------------------------------------------------------------------
# DoD-7 -- what was saved during the side chat survives its deletion
# ---------------------------------------------------------------------------


# DoD-7 (US-140.AC-4; D-D: delete touches `chat_messages` rows only): a codex
# entry created in the same book while the side chat was active is still
# present, unchanged, after the side chat is deleted; the chat's main-line
# rows are also still present.
async def test_codex_entry_created_during_side_chat_survives_delete__DoD7(
    http_client,
):
    author, token = await _seed_author("delete_keeps_codex")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="codex kept")
    cid = int(chat["id"])
    await _seed_row(cid, role="user", content="main-0", position=0)
    await _seed_row(cid, role="assistant", content="main-1", position=1)
    sid = await _start_active(http_client, token, book.id, chat["id"])
    await _seed_row(cid, role="user", content="make a location", position=2, side_chat_id=int(sid))

    # The side task's product: a codex entry created while the side chat is active.
    created = await http_client.post(
        _codex_url(book.id),
        headers=_auth_header(token),
        json={"kind": "location", "name": "The Lighthouse", "body": "A tower on the cliff."},
    )
    assert created.status_code == 201, created.text
    entry = created.json()
    entry_id = entry["id"]

    await _seed_row(cid, role="assistant", content="created it", position=3, side_chat_id=int(sid))

    resp = await _delete(http_client, token, book.id, chat["id"], sid)
    assert resp.status_code == 204, resp.text

    # The codex entry is still there, unchanged.
    fetched = await http_client.get(
        f"{_codex_url(book.id)}/{entry_id}", headers=_auth_header(token)
    )
    assert fetched.status_code == 200, fetched.text
    got = fetched.json()
    assert got["id"] == entry_id
    assert got["kind"] == "location"
    assert got["name"] == "The Lighthouse"
    assert got["body"] == "A tower on the cliff."
    assert got["archived"] is False

    # The chat's main-line rows are also still present; the side rows are gone.
    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert _snapshot(detail) == [("main-0", 0, None), ("main-1", 1, None)]
    assert detail["chat"]["active_side_chat_id"] is None


# ---------------------------------------------------------------------------
# DoD-9 -- delete refusals: unknown id, non-numeric id, another author's chat
# ---------------------------------------------------------------------------


# DoD-9 (D-D `side_chat_not_found` -> 404): deleting an id nobody carries
# answers 404; nothing is deleted and the active pointer is untouched.
async def test_delete_unknown_side_chat_id_is_404_and_deletes_nothing__DoD9(
    http_client,
):
    author, token = await _seed_author("delete_unknown")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="unknown")
    cid = int(chat["id"])
    await _seed_two_finished(cid)
    active_sid = await _start_active(http_client, token, book.id, chat["id"])

    resp = await _delete(http_client, token, book.id, chat["id"], "999999999")

    assert resp.status_code == 404, resp.text
    after = await _get_detail(http_client, token, book.id, chat["id"])
    assert _snapshot(after) == TWO_FINISHED_SNAPSHOT
    assert after["chat"]["active_side_chat_id"] == active_sid


# DoD-9 (D-D: non-numeric -> `side_chat_not_found` -> 404, never 422): deleting
# with a non-numeric side-chat id answers 404 and deletes nothing.
async def test_delete_non_numeric_side_chat_id_is_404_and_deletes_nothing__DoD9(
    http_client,
):
    author, token = await _seed_author("delete_nonnumeric")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="non-numeric")
    cid = int(chat["id"])
    await _seed_two_finished(cid)
    active_sid = await _start_active(http_client, token, book.id, chat["id"])

    resp = await _delete(http_client, token, book.id, chat["id"], "not-a-number")

    assert resp.status_code == 404, resp.text
    assert resp.status_code != 422
    after = await _get_detail(http_client, token, book.id, chat["id"])
    assert _snapshot(after) == TWO_FINISHED_SNAPSHOT
    assert after["chat"]["active_side_chat_id"] == active_sid


# DoD-9 (US-061 inherited; D-D: another author's chat -> 404, never 403): a
# co-author of the same book who does not own the chat cannot delete -- 404 --
# and every row of the owner's chat is still there.
async def test_delete_on_other_authors_chat_is_404_and_deletes_nothing__DoD9(
    http_client,
):
    owner, owner_token = await _seed_author("delete_owner")
    other, other_token = await _seed_author("delete_same_book_author")
    book = await _seed_private_book(owner.id)
    await _add_co_author(book.id, other.id)
    chat = await _create_chat(http_client, owner_token, book.id, title="owned")
    cid = int(chat["id"])
    await _seed_two_finished(cid)

    resp = await _delete(http_client, other_token, book.id, chat["id"], str(SID_A))

    assert resp.status_code == 404, resp.text
    assert resp.status_code != 403
    after = await _get_detail(http_client, owner_token, book.id, chat["id"])
    assert _snapshot(after) == TWO_FINISHED_SNAPSHOT
    assert after["chat"]["active_side_chat_id"] is None


# ---------------------------------------------------------------------------
# DoD-10 -- an active side chat with zero rows: inject 200 / delete 204, the
#           pointer clears, no row changes
# ---------------------------------------------------------------------------


# DoD-10 (D-D: inject of an active side chat with zero rows just clears the
# pointer): start, send nothing, inject -> 200 with `active_side_chat_id: null`
# and the pre-existing main-line rows exactly as they were.
async def test_inject_active_side_chat_with_zero_rows_clears_pointer__DoD10(
    http_client,
):
    author, token = await _seed_author("inject_empty")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="inject empty")
    cid = int(chat["id"])
    await _seed_row(cid, role="user", content="main-0", position=0)
    await _seed_row(cid, role="assistant", content="main-1", position=1)
    sid = await _start_active(http_client, token, book.id, chat["id"])

    resp = await _inject(http_client, token, book.id, chat["id"], sid)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    ChatDetailResponse.model_validate(body)
    assert body["chat"]["active_side_chat_id"] is None
    assert _snapshot(body) == [("main-0", 0, None), ("main-1", 1, None)]

    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] is None
    assert _snapshot(detail) == [("main-0", 0, None), ("main-1", 1, None)]


# DoD-10 (D-D: delete of an active side chat with zero rows just clears the
# pointer): start, send nothing, delete -> 204; GET then shows the pointer null
# and the pre-existing rows unchanged.
async def test_delete_active_side_chat_with_zero_rows_clears_pointer__DoD10(
    http_client,
):
    author, token = await _seed_author("delete_empty")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="delete empty")
    cid = int(chat["id"])
    await _seed_row(cid, role="user", content="main-0", position=0)
    await _seed_row(cid, role="assistant", content="main-1", position=1)
    sid = await _start_active(http_client, token, book.id, chat["id"])

    resp = await _delete(http_client, token, book.id, chat["id"], sid)

    assert resp.status_code == 204, resp.text
    assert resp.content == b""

    detail = await _get_detail(http_client, token, book.id, chat["id"])
    assert detail["chat"]["active_side_chat_id"] is None
    assert _snapshot(detail) == [("main-0", 0, None), ("main-1", 1, None)]
