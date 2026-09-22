"""End-to-end tests for the streaming turn endpoint (feature 011, step 003).

Exercised in-process against the real ``app.main.app`` via the ``http_client``
fixture (httpx ``ASGITransport``, no live server, no network). Bound to the frozen
skeleton (status.md -> Skeleton -> Step 003):
    POST /api/books/{book_id}/chats/{chat_id}/turn  ->  StreamingResponse
        (media_type text/event-stream; frames serialized
         "event: <event>\\ndata: <payload json>\\n\\n" with the frame names
         thinking / delta / done / error)
    body: TurnRequest { prompt: str | None }

The LLM boundary is always faked: ``create_model_client`` is monkeypatched to a
fake ``LLMClient`` (async context manager) whose ``chat_with_tools`` drives
``on_delta`` with scripted chunks, so no network / no real LLM is touched
(003.context.md -> "Testing this step without a network"). Auth is real: users are
seeded and a real JWT is minted, mirroring tests/routes/test_chats.py.

Expected values come from the SPEC ONLY -- the step DoD (DoD-5, DoD-8, DoD-9,
DoD-10), the Interface intent, and the feature ``context.md`` SSE frame vocabulary
-- never from implementation internals. ``asyncio_mode = "auto"``.
"""

import inspect

from llm import LLMError

from app.db import book_members, books, chat_messages, chats, llm_servers, users
from app.db.engine import init_db, set_db_ready
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_member import BookMember, MemberRole
from app.models.chat import Chat
from app.models.llm_server import LlmServer
from app.models.schemas.chats import DoneFrame, ErrorFrame
from app.models.user import User, UserRole
from app.services import auth


# ---------------------------------------------------------------------------
# The fake LLM client -- substituted at the construction seam.
# ---------------------------------------------------------------------------


class _FakeClient:
    def __init__(self, *, chunks=None, exc=None, return_value=""):
        self._chunks = list(chunks or [])
        self._exc = exc
        self._return_value = return_value

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def chat_with_tools(
        self, messages, *, on_delta=None, **kwargs
    ):
        if on_delta is not None:
            for chunk in self._chunks:
                result = on_delta(chunk)
                if inspect.isawaitable(result):
                    await result
        if self._exc is not None:
            raise self._exc
        return self._return_value


def _install_client(monkeypatch, fake: _FakeClient) -> None:
    def factory(server, resolved_key, model):
        return fake

    monkeypatch.setattr(
        "app.services.llm_servers.create_model_client", factory
    )
    monkeypatch.setattr(
        "app.services.chat_turn.create_model_client", factory, raising=False
    )


# ---------------------------------------------------------------------------
# Seeding + request helpers (mirroring tests/routes/test_chats.py).
# ---------------------------------------------------------------------------


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_user(username: str) -> User:
    await init_db()
    user = await users.create(
        User(
            username=username,
            role=UserRole.author,
            pwdhash=auth.hash_password("password123"),
            jwt_signing_key=auth.generate_signing_key(),
        )
    )
    set_db_ready(True)
    return user


async def _seed_author(username: str) -> tuple[User, str]:
    user = await _seed_user(username)
    return user, auth.create_access_token(user)


async def _seed_book(owner_id: int, *, system_prompt: str = "") -> Book:
    return await books.create(
        Book(
            title="A Book",
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt=system_prompt,
            active_notes="",
        )
    )


async def _add_co_author(book_id: int, user_id: int) -> None:
    await book_members.create(
        BookMember(book_id=book_id, user_id=user_id, role=MemberRole.co_author)
    )


async def _seed_server(
    *,
    is_active: bool = True,
    enabled_models: str = '["gpt-x"]',
    api_key: str | None = "sk-stored",
) -> LlmServer:
    return await llm_servers.create(
        LlmServer(
            name="S",
            backend_type="openai",
            base_url="https://api.example.com/v1",
            api_key=api_key,
            enabled_models=enabled_models,
            is_active=is_active,
        )
    )


async def _seed_chat(
    *, book_id: int, author_id: int, llm_server_id, model_name
) -> Chat:
    return await chats.create(
        Chat(
            book_id=book_id,
            author_id=author_id,
            title="A Chat",
            llm_server_id=llm_server_id,
            model_name=model_name,
        )
    )


def _turn_url(book_id: int, chat_id) -> str:
    return f"/api/books/{book_id}/chats/{chat_id}/turn"


def _parse_sse(body: str) -> list[tuple[str | None, str | None]]:
    """Parse an SSE body into a list of ``(event, data)`` pairs."""
    frames: list[tuple[str | None, str | None]] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        event = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = line[len("data:"):].strip()
        frames.append((event, data))
    return frames


# ---------------------------------------------------------------------------
# DoD-5 / DoD-9 (wire) — success emits named frames ending in `done`
# ---------------------------------------------------------------------------


# DoD-5 (US-058.AC-1): the endpoint returns a text/event-stream whose frames are
# named thinking / delta / done; a successful turn terminates with a single
# `done` carrying the persisted assistant message DTO.
async def test_turn_streams_named_frames_and_done__DoD5_US058_AC1(
    http_client, monkeypatch
):
    monkeypatch.setenv("TURN_ROUTE_KEY", "resolved-secret")
    author, token = await _seed_author("streamer")
    book = await _seed_book(author.id)
    server = await _seed_server(api_key="$TURN_ROUTE_KEY")
    chat = await _seed_chat(
        book_id=book.id,
        author_id=author.id,
        llm_server_id=server.id,
        model_name="gpt-x",
    )
    _install_client(
        monkeypatch,
        _FakeClient(chunks=["<think>", "thinkA", "</think>", "ansB"]),
    )

    resp = await http_client.post(
        _turn_url(book.id, chat.id),
        headers=_auth_header(token),
        json={"prompt": "hello"},
    )
    assert resp.status_code == 200, resp.text
    assert "text/event-stream" in resp.headers.get("content-type", "")

    frames = _parse_sse(resp.text)
    events = [e for e, _ in frames]
    assert "thinking" in events
    assert "delta" in events
    assert events.count("done") == 1
    assert events[-1] == "done"
    assert "error" not in events

    done_data = [d for e, d in frames if e == "done"][0]
    done = DoneFrame.model_validate_json(done_data)
    assert done.message.content == "ansB"
    assert done.message.reasoning == "thinkA"

    # The turn persisted the user prompt and the assistant reply.
    stored = await chat_messages.list_by_chat_ordered(chat.id)
    assert [m.content for m in stored if m.role == "user"] == ["hello"]
    assert [m.content for m in stored if m.role == "assistant"] == ["ansB"]


# DoD-9 (UC-056, US-060.AC-1): a library failure after the stream opens surfaces
# as one `error` frame over an HTTP 200 stream -- never a 500 or a hung stream --
# leaving the user message stored and no assistant message.
async def test_library_failure_is_error_frame_not_500__DoD9_US060_AC1(
    http_client, monkeypatch
):
    monkeypatch.setenv("TURN_ROUTE_KEY2", "resolved-secret")
    author, token = await _seed_author("failer")
    book = await _seed_book(author.id)
    server = await _seed_server(api_key="$TURN_ROUTE_KEY2")
    chat = await _seed_chat(
        book_id=book.id,
        author_id=author.id,
        llm_server_id=server.id,
        model_name="gpt-x",
    )
    _install_client(monkeypatch, _FakeClient(exc=LLMError("upstream failed")))

    resp = await http_client.post(
        _turn_url(book.id, chat.id),
        headers=_auth_header(token),
        json={"prompt": "q"},
    )
    assert resp.status_code == 200, resp.text

    frames = _parse_sse(resp.text)
    events = [e for e, _ in frames]
    assert events.count("error") == 1
    assert "done" not in events
    error_data = [d for e, d in frames if e == "error"][0]
    ErrorFrame.model_validate_json(error_data)

    stored = await chat_messages.list_by_chat_ordered(chat.id)
    assert [m.content for m in stored if m.role == "user"] == ["q"]
    assert [m for m in stored if m.role == "assistant"] == []


# ---------------------------------------------------------------------------
# DoD-8 — pre-stream refusals answer as ordinary HTTP errors, nothing persisted
# ---------------------------------------------------------------------------


# DoD-8 (UC-054 exception flow): a chat with no model pair answers an ordinary
# HTTP 400 (not a stream) with nothing persisted.
async def test_no_model_pair_refused_400_nothing_persisted__DoD8(
    http_client, monkeypatch
):
    author, token = await _seed_author("nopair")
    book = await _seed_book(author.id)
    chat = await _seed_chat(
        book_id=book.id, author_id=author.id, llm_server_id=None, model_name=None
    )

    resp = await http_client.post(
        _turn_url(book.id, chat.id),
        headers=_auth_header(token),
        json={"prompt": "hi"},
    )
    assert resp.status_code == 400
    assert await chat_messages.list_by_chat_ordered(chat.id) == []


# DoD-8 (UC-054 exception flow): a chat whose server is inactive, and a chat
# pointing at a missing server, each answer an ordinary HTTP 400 with nothing
# persisted.
async def test_inactive_or_missing_server_refused_400__DoD8(
    http_client, monkeypatch
):
    author, token = await _seed_author("downserver")
    book = await _seed_book(author.id)
    inactive = await _seed_server(is_active=False)
    inactive_chat = await _seed_chat(
        book_id=book.id,
        author_id=author.id,
        llm_server_id=inactive.id,
        model_name="gpt-x",
    )
    missing_chat = await _seed_chat(
        book_id=book.id,
        author_id=author.id,
        llm_server_id=999999999,
        model_name="gpt-x",
    )

    inactive_resp = await http_client.post(
        _turn_url(book.id, inactive_chat.id),
        headers=_auth_header(token),
        json={"prompt": "hi"},
    )
    assert inactive_resp.status_code == 400
    assert await chat_messages.list_by_chat_ordered(inactive_chat.id) == []

    missing_resp = await http_client.post(
        _turn_url(book.id, missing_chat.id),
        headers=_auth_header(token),
        json={"prompt": "hi"},
    )
    assert missing_resp.status_code == 400
    assert await chat_messages.list_by_chat_ordered(missing_chat.id) == []


# DoD-8 (UC-054 exception flow): a chat whose server key env var is unset answers
# an ordinary HTTP 400 with nothing persisted.
async def test_unset_key_env_refused_400_nothing_persisted__DoD8(
    http_client, monkeypatch
):
    monkeypatch.delenv("TURN_UNSET_ROUTE_KEY", raising=False)
    author, token = await _seed_author("nokey")
    book = await _seed_book(author.id)
    server = await _seed_server(api_key="$TURN_UNSET_ROUTE_KEY")
    chat = await _seed_chat(
        book_id=book.id,
        author_id=author.id,
        llm_server_id=server.id,
        model_name="gpt-x",
    )

    resp = await http_client.post(
        _turn_url(book.id, chat.id),
        headers=_auth_header(token),
        json={"prompt": "hi"},
    )
    assert resp.status_code == 400
    assert await chat_messages.list_by_chat_ordered(chat.id) == []


# ---------------------------------------------------------------------------
# DoD-10 — another author's chat and a non-member get 404 before any streaming
# ---------------------------------------------------------------------------


# DoD-10 (US-061.AC-1): a chat authored by B answers 404 to A (the book owner and
# a member) before any streaming and before anything is persisted.
async def test_other_authors_chat_404_before_stream__DoD10_US061_AC1(
    http_client, monkeypatch
):
    author_a, token_a = await _seed_author("owner_a")
    author_b, _token_b = await _seed_author("author_b")
    book = await _seed_book(author_a.id)
    await _add_co_author(book.id, author_b.id)
    server = await _seed_server()
    b_chat = await _seed_chat(
        book_id=book.id,
        author_id=author_b.id,
        llm_server_id=server.id,
        model_name="gpt-x",
    )

    resp = await http_client.post(
        _turn_url(book.id, b_chat.id),
        headers=_auth_header(token_a),
        json={"prompt": "hi"},
    )
    assert resp.status_code == 404
    assert await chat_messages.list_by_chat_ordered(b_chat.id) == []


# DoD-10 (US-061.AC-1): a caller who is not a member of the private book gets 404
# before any streaming and before anything is persisted.
async def test_non_member_gets_404_before_stream__DoD10_US061_AC1(
    http_client, monkeypatch
):
    owner, _owner_token = await _seed_author("book_owner")
    _stranger, stranger_token = await _seed_author("stranger")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(
        book_id=book.id,
        author_id=owner.id,
        llm_server_id=server.id,
        model_name="gpt-x",
    )

    resp = await http_client.post(
        _turn_url(book.id, chat.id),
        headers=_auth_header(stranger_token),
        json={"prompt": "hi"},
    )
    assert resp.status_code == 404
    assert await chat_messages.list_by_chat_ordered(chat.id) == []
