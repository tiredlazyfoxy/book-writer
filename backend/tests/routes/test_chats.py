"""End-to-end tests for the chat HTTP surface (feature 011, step 001).

Exercised in-process against the real `app.main.app` via the `http_client`
fixture (httpx `ASGITransport`, no live server, no network). The app's startup
lifespan runs against a throwaway temp DB; each test seeds its own users, books,
members, servers and messages on the same process-global engine the app uses
(schema built with `init_db`, readiness flipped with `set_db_ready(True)`),
mirroring tests/routes/test_books.py.

Bound to the frozen skeleton (status.md -> Skeleton -> Step 001), router
`app.routes.chats` with prefix "/api/books", every endpoint gated by
`Depends(authz.book_access)`:
    GET   /{book_id}/chats/model-options  -> 200 ModelOptionListResponse
    POST  /{book_id}/chats                -> 201 ChatResponse
    GET   /{book_id}/chats                -> 200 ChatListResponse (archived flag)
    GET   /{book_id}/chats/{chat_id}      -> 200 ChatDetailResponse
    PATCH /{book_id}/chats/{chat_id}      -> 200 ChatResponse
and the DTOs of `app.models.schemas.chats`.

Expected values come from the SPEC ONLY -- the step DoD (DoD-1..DoD-9), the step
Interface intent, the feature context.md decisions, and the cited US-###.AC-#
acceptance criteria -- never from implementation internals.

Async tests use asyncio_mode = "auto".
"""

import datetime

from app.db import book_members, books, chat_messages, llm_servers, users
from app.db.engine import init_db, set_db_ready
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_member import BookMember, MemberRole
from app.models.chat import ChatMessage
from app.models.llm_server import LlmServer
from app.models.schemas.chats import (
    ChatDetailResponse,
    ChatListResponse,
    ChatResponse,
    ModelOptionListResponse,
)
from app.models.user import User, UserRole
from app.services import auth


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


async def _seed_server(
    *, name: str, enabled_models: str, is_active: bool = True,
    api_key: str | None = "$SECRET_KEY_VALUE",
) -> LlmServer:
    return await llm_servers.create(
        LlmServer(
            name=name,
            backend_type="openai",
            base_url="https://api.example.com/v1",
            api_key=api_key,
            enabled_models=enabled_models,
            is_active=is_active,
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
# DoD-1 — create stores against caller + book, string ids
# ---------------------------------------------------------------------------


# DoD-1 (UC-053, US-056.AC-1): POST creates a chat owned by the caller in the
# book, with string ids and no subject/chapter/codex binding.
async def test_create_stores_author_and_book_string_ids__DoD1_US056_AC1(http_client):
    author, token = await _seed_author("alice")
    book = await _seed_private_book(author.id)

    created = await _create_chat(http_client, token, book.id, title="Villain arc")
    ChatResponse.model_validate(created)

    assert created["author_id"] == str(author.id)
    assert created["book_id"] == str(book.id)
    assert type(created["id"]) is str
    assert created["title"] == "Villain arc"
    assert created["archived"] is False


# ---------------------------------------------------------------------------
# DoD-2 — list is caller-private; no other role sees another author's chat
# ---------------------------------------------------------------------------


# DoD-2 (US-061.AC-1, US-095.AC-1): a chat authored by B is never in the list of,
# nor fetchable by, the book owner (A) or a second co-author (C); B's own list
# returns it, most recently modified first.
async def test_list_is_caller_private_across_roles__DoD2_US061_AC1(http_client):
    author_a, token_a = await _seed_author("owner_a")  # book owner
    author_b, token_b = await _seed_author("author_b")  # co-author, chat author
    author_c, token_c = await _seed_author("author_c")  # another co-author
    book = await _seed_private_book(author_a.id)
    await _add_co_author(book.id, author_b.id)
    await _add_co_author(book.id, author_c.id)

    # B creates two chats; the second is the most recently modified.
    b_first = await _create_chat(http_client, token_b, book.id, title="b-first")
    b_second = await _create_chat(http_client, token_b, book.id, title="b-second")

    # Owner A: B's chat absent from list and not fetchable.
    a_list = await http_client.get(_chats_url(book.id), headers=_auth_header(token_a))
    assert a_list.status_code == 200, a_list.text
    ChatListResponse.model_validate(a_list.json())
    assert b_first["id"] not in [c["id"] for c in a_list.json()["items"]]
    a_fetch = await http_client.get(
        f"{_chats_url(book.id)}/{b_first['id']}", headers=_auth_header(token_a)
    )
    assert a_fetch.status_code == 404

    # Co-author C: same.
    c_list = await http_client.get(_chats_url(book.id), headers=_auth_header(token_c))
    assert c_list.status_code == 200
    assert b_first["id"] not in [c["id"] for c in c_list.json()["items"]]
    c_fetch = await http_client.get(
        f"{_chats_url(book.id)}/{b_first['id']}", headers=_auth_header(token_c)
    )
    assert c_fetch.status_code == 404

    # B sees its own chats, most-recently-modified first.
    b_list = await http_client.get(_chats_url(book.id), headers=_auth_header(token_b))
    assert b_list.status_code == 200
    b_ids = [c["id"] for c in b_list.json()["items"]]
    assert b_first["id"] in b_ids and b_second["id"] in b_ids
    assert b_ids[0] == b_second["id"]


# ---------------------------------------------------------------------------
# DoD-3 — another author's chat answers 404, not 403
# ---------------------------------------------------------------------------


# DoD-3 (US-061.AC-1): GET and PATCH of a chat owned by another author answer
# 404 (existence hidden), never 403.
async def test_other_authors_chat_is_404_not_403__DoD3_US061_AC1(http_client):
    author_a, token_a = await _seed_author("owner_x")
    author_b, token_b = await _seed_author("author_bx")
    book = await _seed_private_book(author_a.id)
    await _add_co_author(book.id, author_b.id)

    b_chat = await _create_chat(http_client, token_b, book.id, title="bs")

    get_resp = await http_client.get(
        f"{_chats_url(book.id)}/{b_chat['id']}", headers=_auth_header(token_a)
    )
    assert get_resp.status_code == 404

    patch_resp = await http_client.patch(
        f"{_chats_url(book.id)}/{b_chat['id']}",
        headers=_auth_header(token_a),
        json={"archived": True},
    )
    assert patch_resp.status_code == 404


# ---------------------------------------------------------------------------
# DoD-4 — fetch returns messages ordered by position ascending
# ---------------------------------------------------------------------------


# DoD-4 (UC-081, US-095.AC-2): GET /{chat_id} returns the chat's messages ordered
# by position ascending. Messages are seeded via the db layer (no writer route in
# this step).
async def test_fetch_returns_messages_position_ordered__DoD4_UC081(http_client):
    author, token = await _seed_author("reader")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="history")
    cid = int(chat["id"])
    await chat_messages.create(
        ChatMessage(chat_id=cid, role="assistant", content="a2", position=2)
    )
    await chat_messages.create(
        ChatMessage(chat_id=cid, role="user", content="a0", position=0)
    )
    await chat_messages.create(
        ChatMessage(chat_id=cid, role="assistant", content="a1", position=1)
    )

    resp = await http_client.get(
        f"{_chats_url(book.id)}/{chat['id']}", headers=_auth_header(token)
    )
    assert resp.status_code == 200, resp.text
    ChatDetailResponse.model_validate(resp.json())
    messages = resp.json()["messages"]
    assert [m["position"] for m in messages] == [0, 1, 2]
    assert [m["content"] for m in messages] == ["a0", "a1", "a2"]


# ---------------------------------------------------------------------------
# DoD-5 — archive removes from active list; restore returns it; rows survive
# ---------------------------------------------------------------------------


# DoD-5 (UC-082, US-096.AC-1/AC-2): PATCH archived=true removes the chat from the
# active list while its row and messages survive (still fetchable, present in the
# archived list); PATCH archived=false returns it to the active list.
async def test_archive_then_restore__DoD5_US096(http_client):
    author, token = await _seed_author("keeper")
    book = await _seed_private_book(author.id)
    chat = await _create_chat(http_client, token, book.id, title="keepme")
    await chat_messages.create(
        ChatMessage(chat_id=int(chat["id"]), role="user", content="hi", position=0)
    )

    # Archive.
    patch = await http_client.patch(
        f"{_chats_url(book.id)}/{chat['id']}",
        headers=_auth_header(token),
        json={"archived": True},
    )
    assert patch.status_code == 200, patch.text

    active = await http_client.get(
        f"{_chats_url(book.id)}?archived=false", headers=_auth_header(token)
    )
    assert chat["id"] not in [c["id"] for c in active.json()["items"]]

    archived = await http_client.get(
        f"{_chats_url(book.id)}?archived=true", headers=_auth_header(token)
    )
    assert chat["id"] in [c["id"] for c in archived.json()["items"]]

    # Row + message survive.
    detail = await http_client.get(
        f"{_chats_url(book.id)}/{chat['id']}", headers=_auth_header(token)
    )
    assert detail.status_code == 200
    assert detail.json()["chat"]["archived"] is True
    assert [m["content"] for m in detail.json()["messages"]] == ["hi"]

    # Restore.
    restore = await http_client.patch(
        f"{_chats_url(book.id)}/{chat['id']}",
        headers=_auth_header(token),
        json={"archived": False},
    )
    assert restore.status_code == 200
    active_again = await http_client.get(
        f"{_chats_url(book.id)}?archived=false", headers=_auth_header(token)
    )
    assert chat["id"] in [c["id"] for c in active_again.json()["items"]]


# ---------------------------------------------------------------------------
# DoD-6 — half-set model pair refused with 400; valid pair accepted
# ---------------------------------------------------------------------------


# DoD-6: a half-set model pair is refused at the service edge with 400; a valid
# both-set pair (active server + enabled model) is accepted with 201.
async def test_half_set_pair_400_valid_pair_201__DoD6(http_client):
    author, token = await _seed_author("pairing")
    book = await _seed_private_book(author.id)
    server = await _seed_server(name="S", enabled_models='["gpt-x"]')

    half = await http_client.post(
        _chats_url(book.id),
        headers=_auth_header(token),
        json={"title": "t", "llm_server_id": str(server.id)},
    )
    assert half.status_code == 400

    ok = await http_client.post(
        _chats_url(book.id),
        headers=_auth_header(token),
        json={"title": "t", "llm_server_id": str(server.id), "model_name": "gpt-x"},
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["llm_server_id"] == str(server.id)
    assert ok.json()["model_name"] == "gpt-x"


# ---------------------------------------------------------------------------
# DoD-7 — create without sampling returns the documented defaults
# ---------------------------------------------------------------------------


# DoD-7 (decision 6): a create with no sampling override returns the documented
# default sampling object.
async def test_create_returns_default_sampling__DoD7(http_client):
    author, token = await _seed_author("sampler")
    book = await _seed_private_book(author.id)

    created = await _create_chat(http_client, token, book.id, title="t")
    s = created["sampling"]
    assert s["temperature"] == 0.8
    assert s["top_p"] == 0.95
    assert s["top_k"] == 40
    assert s["repeat_penalty"] == 1.1
    assert s["min_p"] == 0.05
    assert s["max_tokens"] is None
    assert s["seed"] is None
    assert s["presence_penalty"] == 0.0
    assert s["frequency_penalty"] == 0.0
    assert s["enable_thinking"] is True


# ---------------------------------------------------------------------------
# DoD-8 — model-options: active-server triples only, no api key
# ---------------------------------------------------------------------------


# DoD-8 (UC-053 precondition, FEAT-004): GET /model-options lists
# (server id, server name, model) triples from active servers only; inactive
# servers contribute nothing and no api key appears anywhere in the response.
async def test_model_options_active_only_no_api_key__DoD8_FEAT004(http_client):
    author, token = await _seed_author("optioner")
    book = await _seed_private_book(author.id)
    await _seed_server(name="S1", enabled_models='["a", "b"]', api_key="$SECRET_KEY_VALUE")
    await _seed_server(name="S2", enabled_models='["c"]')
    await _seed_server(name="Off", enabled_models='["x"]', is_active=False)

    resp = await http_client.get(
        f"{_chats_url(book.id)}/model-options", headers=_auth_header(token)
    )
    assert resp.status_code == 200, resp.text
    ModelOptionListResponse.model_validate(resp.json())

    triples = {(o["server_name"], o["model_name"]) for o in resp.json()["items"]}
    assert triples == {("S1", "a"), ("S1", "b"), ("S2", "c")}
    assert "$SECRET_KEY_VALUE" not in resp.text


# ---------------------------------------------------------------------------
# DoD-9 — a non-member of the book gets 404 from every chat route
# ---------------------------------------------------------------------------


# DoD-9 (authorization.md): a logged-in caller who is not a member of the private
# book gets 404 from every chat route (existence hidden by book_access).
async def test_non_member_gets_404_from_every_route__DoD9(http_client):
    owner, _owner_token = await _seed_author("book_owner")
    _stranger, stranger_token = await _seed_author("stranger")
    book = await _seed_private_book(owner.id)
    h = _auth_header(stranger_token)
    base = _chats_url(book.id)

    assert (await http_client.get(f"{base}/model-options", headers=h)).status_code == 404
    assert (await http_client.get(base, headers=h)).status_code == 404
    assert (
        await http_client.post(base, headers=h, json={"title": "x"})
    ).status_code == 404
    assert (await http_client.get(f"{base}/123", headers=h)).status_code == 404
    assert (
        await http_client.patch(f"{base}/123", headers=h, json={"title": "x"})
    ).status_code == 404
