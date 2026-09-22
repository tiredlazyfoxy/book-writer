"""Tests for the chat service — CRUD, privacy, model pair and sampling (feature 011, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001), in
`app.services.chats`:
    class ChatErrorReason(str, enum.Enum) { chat_not_found, invalid_model_pair,
        unknown_or_inactive_server, model_not_enabled, invalid_sampling }
    class ChatError(Exception)  __init__(reason, message="")  -> .reason / .message
    def _parse_sampling(raw: str) -> ChatSamplingParams  (defaults on unparseable)
    async def create_chat(access, req: CreateChatRequest) -> ChatResponse
    async def list_chats(access, archived: bool) -> ChatListResponse
    async def get_chat(access, chat_id: str) -> ChatDetailResponse
    async def update_chat(access, chat_id: str, req: UpdateChatRequest) -> ChatResponse
    async def list_model_options(access) -> ModelOptionListResponse
and the DTOs of `app.models.schemas.chats` + the frozen `authz.BookAccess`.

Expected values come from the step spec (001.chat-crud-model-sampling.md DoD +
001.context.md + feature context.md decisions 4/5/6), never from implementation
internals.

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. Book / LlmServer / ChatMessage rows are
seeded directly through the db layer (008/009 test_data_domain style); a
`BookAccess` is constructed directly (frozen dataclass) with the caller's user id
and book id, mirroring tests/services/test_authz.py -- no HTTP round-trip, no
network, no LLM client.
"""

import pytest

from app.db import books, chat_messages, chats, llm_servers, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chat import ChatMessage
from app.models.llm_server import LlmServer
from app.models.user import User, UserRole
from app.services import chats as chat_service
from app.services.authz import AccessRole, BookAccess
from app.services.chats import ChatError, ChatErrorReason, _parse_sampling
from app.models.schemas.chats import (
    ChatSamplingParams,
    CreateChatRequest,
    UpdateChatRequest,
)


# ---------------------------------------------------------------------------
# Seeding helpers (008/009 style: construct rows directly through the db layer).
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(owner_id: int) -> Book:
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


async def _seed_server(
    *,
    name: str,
    enabled_models: str,
    is_active: bool = True,
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


def _access(book_id: int, user_id: int) -> BookAccess:
    """A BookAccess for `user_id` on `book_id`; role is irrelevant to the chat
    ownership rule (keyed on Chat.author_id == user_id), so any member role works.
    """
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=AccessRole.owner,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=CollaborationMode.free,
    )


# ---------------------------------------------------------------------------
# DoD-1 — create stores the chat against the caller + book, string ids
# ---------------------------------------------------------------------------


# DoD-1 (UC-053, US-056.AC-1): create_chat stores the chat against the caller as
# author and the resolved book, and returns it with string ids and archived=False.
async def test_create_stores_author_and_book_string_ids__DoD1_US056_AC1(db: DbConfig):
    author = await _seed_user("alice")
    book = await _seed_book(author.id)

    resp = await chat_service.create_chat(
        _access(book.id, author.id), CreateChatRequest(title="Villain arc")
    )

    assert resp.author_id == str(author.id)
    assert resp.book_id == str(book.id)
    assert isinstance(resp.id, str)
    assert resp.title == "Villain arc"
    assert resp.archived is False


# ---------------------------------------------------------------------------
# DoD-2 — list returns only the caller's own non-archived chats, newest first
# ---------------------------------------------------------------------------


# DoD-2 (US-061.AC-1, US-095.AC-1): list_chats returns only the caller's own
# non-archived chats in the book -- another author's chat in the same book is
# never present.
async def test_list_excludes_other_authors_chat__DoD2_US061_AC1(db: DbConfig):
    author_a = await _seed_user("a")
    author_b = await _seed_user("b")
    book = await _seed_book(author_a.id)

    mine = await chat_service.create_chat(
        _access(book.id, author_a.id), CreateChatRequest(title="mine")
    )
    theirs = await chat_service.create_chat(
        _access(book.id, author_b.id), CreateChatRequest(title="theirs")
    )

    listed = await chat_service.list_chats(_access(book.id, author_a.id), False)
    ids = [c.id for c in listed.items]

    assert mine.id in ids
    assert theirs.id not in ids


# ---------------------------------------------------------------------------
# DoD-3 — another author's chat answers not-found (404, not 403)
# ---------------------------------------------------------------------------


# DoD-3 (US-061.AC-1): fetching a chat owned by another author raises
# ChatError(chat_not_found) even for a co-member of the same book -- existence is
# not confirmed (the route maps this reason to 404, never 403).
async def test_get_other_authors_chat_is_not_found__DoD3_US061_AC1(db: DbConfig):
    author_a = await _seed_user("owner")
    author_b = await _seed_user("intruder")
    book = await _seed_book(author_a.id)

    chat = await chat_service.create_chat(
        _access(book.id, author_a.id), CreateChatRequest(title="private")
    )

    with pytest.raises(ChatError) as exc:
        await chat_service.get_chat(_access(book.id, author_b.id), chat.id)
    assert exc.value.reason == ChatErrorReason.chat_not_found


# DoD-3 (US-061.AC-1): updating/archiving a chat owned by another author likewise
# raises ChatError(chat_not_found).
async def test_update_other_authors_chat_is_not_found__DoD3_US061_AC1(db: DbConfig):
    author_a = await _seed_user("owner2")
    author_b = await _seed_user("intruder2")
    book = await _seed_book(author_a.id)

    chat = await chat_service.create_chat(
        _access(book.id, author_a.id), CreateChatRequest(title="private")
    )

    with pytest.raises(ChatError) as exc:
        await chat_service.update_chat(
            _access(book.id, author_b.id), chat.id, UpdateChatRequest(archived=True)
        )
    assert exc.value.reason == ChatErrorReason.chat_not_found


# DoD-3: a non-existent chat id also answers not-found.
async def test_get_missing_chat_is_not_found__DoD3(db: DbConfig):
    author = await _seed_user("solo")
    book = await _seed_book(author.id)

    with pytest.raises(ChatError) as exc:
        await chat_service.get_chat(_access(book.id, author.id), "999999999")
    assert exc.value.reason == ChatErrorReason.chat_not_found


# ---------------------------------------------------------------------------
# DoD-4 — chat fetch returns messages ordered by position ascending
# ---------------------------------------------------------------------------


# DoD-4 (UC-081, US-095.AC-2): get_chat returns the chat plus its messages ordered
# by `position` ascending, so a reopened chat carries its full prior history in
# order. (Messages are seeded via the db layer -- this step ships no writer.)
async def test_get_chat_returns_messages_in_position_order__DoD4_UC081(db: DbConfig):
    author = await _seed_user("reader")
    book = await _seed_book(author.id)
    chat = await chat_service.create_chat(
        _access(book.id, author.id), CreateChatRequest(title="history")
    )
    cid = int(chat.id)
    # Seed out of order.
    await chat_messages.create(
        ChatMessage(chat_id=cid, role="assistant", content="a2", position=2)
    )
    await chat_messages.create(
        ChatMessage(chat_id=cid, role="user", content="a0", position=0)
    )
    await chat_messages.create(
        ChatMessage(chat_id=cid, role="assistant", content="a1", position=1)
    )

    detail = await chat_service.get_chat(_access(book.id, author.id), chat.id)

    assert [m.position for m in detail.messages] == [0, 1, 2]
    assert [m.content for m in detail.messages] == ["a0", "a1", "a2"]


# ---------------------------------------------------------------------------
# DoD-5 — archive removes from active list; restore returns it; rows survive
# ---------------------------------------------------------------------------


# DoD-5 (UC-082, US-096.AC-1/AC-2): archiving removes a chat from the active list
# while the row and its messages survive, and restoring returns it to the active
# list.
async def test_archive_then_restore_round_trip__DoD5_US096(db: DbConfig):
    author = await _seed_user("keeper")
    book = await _seed_book(author.id)
    chat = await chat_service.create_chat(
        _access(book.id, author.id), CreateChatRequest(title="keepme")
    )
    await chat_messages.create(
        ChatMessage(chat_id=int(chat.id), role="user", content="hi", position=0)
    )

    # Archive.
    await chat_service.update_chat(
        _access(book.id, author.id), chat.id, UpdateChatRequest(archived=True)
    )
    active = await chat_service.list_chats(_access(book.id, author.id), False)
    archived = await chat_service.list_chats(_access(book.id, author.id), True)
    assert chat.id not in [c.id for c in active.items]
    assert chat.id in [c.id for c in archived.items]

    # The row and its message survive archiving.
    detail = await chat_service.get_chat(_access(book.id, author.id), chat.id)
    assert detail.chat.archived is True
    assert [m.content for m in detail.messages] == ["hi"]

    # Restore.
    await chat_service.update_chat(
        _access(book.id, author.id), chat.id, UpdateChatRequest(archived=False)
    )
    active_again = await chat_service.list_chats(_access(book.id, author.id), False)
    assert chat.id in [c.id for c in active_again.items]


# ---------------------------------------------------------------------------
# DoD-6 — the model pair moves together and is validated
# ---------------------------------------------------------------------------


# DoD-6: a both-null model pair is accepted; the stored pair is null.
async def test_create_accepts_both_null_pair__DoD6(db: DbConfig):
    author = await _seed_user("np")
    book = await _seed_book(author.id)

    resp = await chat_service.create_chat(
        _access(book.id, author.id),
        CreateChatRequest(title="t", llm_server_id=None, model_name=None),
    )
    assert resp.llm_server_id is None
    assert resp.model_name is None


# DoD-6: a both-set pair naming an active server whose enabled_models contains the
# model is accepted; the response carries the pair (server id as a string).
async def test_create_accepts_valid_pair__DoD6(db: DbConfig):
    author = await _seed_user("vp")
    book = await _seed_book(author.id)
    server = await _seed_server(name="S", enabled_models='["gpt-x"]')

    resp = await chat_service.create_chat(
        _access(book.id, author.id),
        CreateChatRequest(
            title="t", llm_server_id=str(server.id), model_name="gpt-x"
        ),
    )
    assert resp.llm_server_id == str(server.id)
    assert resp.model_name == "gpt-x"


# DoD-6: a half-set pair (server without model, or model without server) is
# refused with the invalid_model_pair reason.
async def test_create_refuses_half_set_pair__DoD6(db: DbConfig):
    author = await _seed_user("hp")
    book = await _seed_book(author.id)
    server = await _seed_server(name="S", enabled_models='["gpt-x"]')

    with pytest.raises(ChatError) as exc1:
        await chat_service.create_chat(
            _access(book.id, author.id),
            CreateChatRequest(
                title="t", llm_server_id=str(server.id), model_name=None
            ),
        )
    assert exc1.value.reason == ChatErrorReason.invalid_model_pair

    with pytest.raises(ChatError) as exc2:
        await chat_service.create_chat(
            _access(book.id, author.id),
            CreateChatRequest(title="t", llm_server_id=None, model_name="gpt-x"),
        )
    assert exc2.value.reason == ChatErrorReason.invalid_model_pair


# DoD-6: a pair naming an INACTIVE server is refused with the
# unknown_or_inactive_server reason.
async def test_create_refuses_inactive_server__DoD6(db: DbConfig):
    author = await _seed_user("is")
    book = await _seed_book(author.id)
    server = await _seed_server(
        name="Down", enabled_models='["gpt-x"]', is_active=False
    )

    with pytest.raises(ChatError) as exc:
        await chat_service.create_chat(
            _access(book.id, author.id),
            CreateChatRequest(
                title="t", llm_server_id=str(server.id), model_name="gpt-x"
            ),
        )
    assert exc.value.reason == ChatErrorReason.unknown_or_inactive_server


# DoD-6: a pair naming a model absent from the server's enabled_models is refused
# with the model_not_enabled reason.
async def test_create_refuses_model_not_enabled__DoD6(db: DbConfig):
    author = await _seed_user("mne")
    book = await _seed_book(author.id)
    server = await _seed_server(name="S", enabled_models='["only-this"]')

    with pytest.raises(ChatError) as exc:
        await chat_service.create_chat(
            _access(book.id, author.id),
            CreateChatRequest(
                title="t", llm_server_id=str(server.id), model_name="not-there"
            ),
        )
    assert exc.value.reason == ChatErrorReason.model_not_enabled


# ---------------------------------------------------------------------------
# DoD-7 — sampling params round-trip through the TEXT column
# ---------------------------------------------------------------------------


# DoD-7 (decision 6): an absent sampling object yields the documented defaults.
async def test_create_absent_sampling_yields_defaults__DoD7(db: DbConfig):
    author = await _seed_user("s1")
    book = await _seed_book(author.id)

    resp = await chat_service.create_chat(
        _access(book.id, author.id), CreateChatRequest(title="t", sampling=None)
    )

    s = resp.sampling
    assert s.temperature == 0.8
    assert s.top_p == 0.95
    assert s.top_k == 40
    assert s.repeat_penalty == 1.1
    assert s.min_p == 0.05
    assert s.max_tokens is None
    assert s.seed is None
    assert s.presence_penalty == 0.0
    assert s.frequency_penalty == 0.0
    assert s.enable_thinking is True


# DoD-7 (decision 6): a partial sampling object keeps the provided field and
# defaults the rest.
async def test_create_partial_sampling_defaults_the_rest__DoD7(db: DbConfig):
    author = await _seed_user("s2")
    book = await _seed_book(author.id)

    resp = await chat_service.create_chat(
        _access(book.id, author.id),
        CreateChatRequest(title="t", sampling=ChatSamplingParams(temperature=0.2)),
    )

    assert resp.sampling.temperature == 0.2  # provided
    assert resp.sampling.top_k == 40  # default retained


# DoD-7: _parse_sampling falls back to defaults on an unparseable stored value
# rather than raising, and returns the parsed values for a valid one.
def test_parse_sampling_falls_back_to_defaults__DoD7():
    fallback = _parse_sampling("this is not json")
    assert fallback == ChatSamplingParams()

    valid = _parse_sampling(ChatSamplingParams(temperature=0.11).model_dump_json())
    assert valid.temperature == 0.11


# DoD-7: a stored unparseable sampling value reads back as defaults (not raising)
# through get_chat.
async def test_get_chat_reads_corrupt_sampling_as_defaults__DoD7(db: DbConfig):
    author = await _seed_user("s3")
    book = await _seed_book(author.id)
    chat = await chat_service.create_chat(
        _access(book.id, author.id), CreateChatRequest(title="t")
    )
    # Corrupt the stored JSON directly at the db layer.
    row = await chats.get_by_id(int(chat.id))
    row.sampling_params = "{ not valid json"
    await chats.update(row)

    detail = await chat_service.get_chat(_access(book.id, author.id), chat.id)
    assert detail.chat.sampling == ChatSamplingParams()


# DoD-7: a param the UI never surfaces (top_k) survives an unrelated update
# (title-only) untouched.
async def test_unsurfaced_param_survives_unrelated_update__DoD7(db: DbConfig):
    author = await _seed_user("s4")
    book = await _seed_book(author.id)
    chat = await chat_service.create_chat(
        _access(book.id, author.id),
        CreateChatRequest(title="t", sampling=ChatSamplingParams(top_k=7)),
    )

    updated = await chat_service.update_chat(
        _access(book.id, author.id), chat.id, UpdateChatRequest(title="renamed")
    )

    assert updated.title == "renamed"
    assert updated.sampling.top_k == 7


# ---------------------------------------------------------------------------
# DoD-8 — model-options triples from active servers, no api key
# ---------------------------------------------------------------------------


# DoD-8 (UC-053 precondition, FEAT-004): list_model_options flattens active
# servers' enabled_models into (server id, server name, model) triples; inactive
# servers contribute nothing and no api key appears anywhere in the response.
async def test_model_options_active_only_no_api_key__DoD8_FEAT004(db: DbConfig):
    author = await _seed_user("mo")
    book = await _seed_book(author.id)
    s1 = await _seed_server(
        name="S1", enabled_models='["a", "b"]', api_key="$SECRET_KEY_VALUE"
    )
    s2 = await _seed_server(name="S2", enabled_models='["c"]')
    await _seed_server(name="Inactive", enabled_models='["x"]', is_active=False)

    resp = await chat_service.list_model_options(_access(book.id, author.id))

    triples = {(o.server_name, o.model_name) for o in resp.items}
    assert triples == {("S1", "a"), ("S1", "b"), ("S2", "c")}
    # server_id is the active server's id as a string.
    by_name = {o.server_name for o in resp.items}
    assert by_name == {"S1", "S2"}
    for o in resp.items:
        assert isinstance(o.server_id, str)
    assert str(s1.id) in {o.server_id for o in resp.items}
    assert str(s2.id) in {o.server_id for o in resp.items}

    # No api key value (raw or masked) anywhere in the serialized response.
    assert "$SECRET_KEY_VALUE" not in resp.model_dump_json()
