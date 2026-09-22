"""Tests for the side-chat behaviour of the streaming turn
(feature 027.side-chats, step 002 -- DoD-8..DoD-14).

Bound to the frozen skeleton (status.md -> Skeleton -> Step 001 / Step 002):
    app.services.chat_turn.run_turn(context: TurnContext, prompt: str | None)
        -> AsyncGenerator[TurnFrame, None]        (signature unchanged)
    Chat.active_side_chat_id: int | None           (the pointer, step 001)
    ChatMessage.side_chat_id: int | None           (the row stamp, step 001)
    ChatMessageResponse.side_chat_id: str | None   (the `done` frame's message)

The behaviour under test is decision D-C (context.md): the turn captures the
chat's `active_side_chat_id` once at turn start, stamps it on the user row and
the assistant row (the retry path included), and reads the transcript through
`list_transcript(chat_id, <captured id>)` -- main-line rows plus the active
side chat's rows, never a finished side chat's.

No network / no real LLM: the fake ``LLMClient`` and the ``create_model_client``
monkeypatch are copied verbatim from tests/services/test_chat_turn.py (every
test module defines its own local helpers). The fake captures the outgoing
message list in ``fake.call["messages"]``; every "a fact stated only in X is /
is not available to the turn" criterion asserts on that capture.

The pointer is set for a turn test by mutating ``context.chat.active_side_chat_id``
and persisting through ``db/chats.update`` -- no route needed. Rows are read
back UNFILTERED through ``chat_messages.list_by_chat_ordered``.

Expected values come from the SPEC ONLY -- the step DoD, the Interface intent,
and context.md decisions D-C / D-E -- never from implementation internals.
``asyncio_mode = "auto"``.
"""

import inspect

from app.db import books, chat_messages, chats, llm_servers, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chat import Chat, ChatMessage
from app.models.llm_server import LlmServer
from app.models.schemas.chats import DoneFrame
from app.models.user import User, UserRole
from app.services import chat_turn
from app.services.chat_turn import TurnContext


# ---------------------------------------------------------------------------
# The fake LLM client -- copied from tests/services/test_chat_turn.py.
# ---------------------------------------------------------------------------


class _FakeClient:
    """A stand-in for ``llm.LLMClient`` used as an async context manager.

    ``chat_with_tools`` drives ``on_delta`` with the scripted chunks exactly the
    way the real library does (calling it, awaiting the result if it is
    awaitable), records the call kwargs, then either raises the configured
    exception or returns the configured final string.
    """

    def __init__(self, *, chunks=None, exc=None, return_value=""):
        self._chunks = list(chunks or [])
        self._exc = exc
        self._return_value = return_value
        self.entered = False
        self.exited = False
        self.call: dict | None = None
        self.construct_args: tuple | None = None

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True
        return False

    async def chat_with_tools(
        self,
        messages,
        *,
        tools_definitions=None,
        tools=None,
        system=None,
        max_loops=None,
        options=None,
        stream=False,
        on_delta=None,
        response_format=None,
        **kwargs,
    ):
        self.call = {
            "messages": messages,
            "tools_definitions": tools_definitions,
            "tools": tools,
            "system": system,
            "max_loops": max_loops,
            "options": options,
            "stream": stream,
        }
        if on_delta is not None:
            for chunk in self._chunks:
                result = on_delta(chunk)
                if inspect.isawaitable(result):
                    await result
        if self._exc is not None:
            raise self._exc
        return self._return_value


def _install_client(monkeypatch, fake: _FakeClient) -> _FakeClient:
    """Monkeypatch ``create_model_client`` (the frozen seam) to yield ``fake``."""

    def factory(server, resolved_key, model):
        fake.construct_args = (server, resolved_key, model)
        return fake

    monkeypatch.setattr(
        "app.services.llm_servers.create_model_client", factory
    )
    monkeypatch.setattr(
        "app.services.chat_turn.create_model_client", factory, raising=False
    )
    return fake


# ---------------------------------------------------------------------------
# Seeding helpers -- copied from tests/services/test_chat_turn.py.
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


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


async def _seed_server(
    *,
    backend_type: str = "openai",
    enabled_models: str = '["gpt-x"]',
    is_active: bool = True,
    api_key: str | None = "sk-stored",
) -> LlmServer:
    return await llm_servers.create(
        LlmServer(
            name="S",
            backend_type=backend_type,
            base_url="https://api.example.com/v1",
            api_key=api_key,
            enabled_models=enabled_models,
            is_active=is_active,
        )
    )


async def _seed_chat(
    *,
    book_id: int,
    author_id: int,
    llm_server_id: int | None,
    model_name: str | None,
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


async def _context(
    *,
    backend_type: str = "openai",
    resolved_key: str | None = "resolved-secret",
    model_name: str = "gpt-x",
    username: str = "author",
) -> TurnContext:
    """Seed a full world (user/book/server/chat) and build a TurnContext directly."""
    user = await _seed_user(username)
    book = await _seed_book(user.id)
    server = await _seed_server(backend_type=backend_type)
    chat = await _seed_chat(
        book_id=book.id,
        author_id=user.id,
        llm_server_id=server.id,
        model_name=model_name,
    )
    return TurnContext(chat=chat, server=server, resolved_key=resolved_key)


async def _run(context: TurnContext, prompt: str | None):
    return [frame async for frame in chat_turn.run_turn(context, prompt)]


async def _messages(chat_id: int) -> list[ChatMessage]:
    return await chat_messages.list_by_chat_ordered(chat_id)


# ---------------------------------------------------------------------------
# Side-chat helpers local to this module.
# ---------------------------------------------------------------------------


async def _activate(context: TurnContext, side_chat_id: int | None) -> None:
    """Set the chat's active side-chat pointer and persist it (the TurnContext
    holds the Chat row; `db/chats.update` is the single write path)."""
    context.chat.active_side_chat_id = side_chat_id
    await chats.update(context.chat)


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


def _sent_contents(fake: _FakeClient) -> list[str]:
    """The `content` of every message handed to the model, in order."""
    assert fake.call is not None, "the model was never called"
    return [str(m.get("content")) for m in fake.call["messages"]]


def _sent(fake: _FakeClient, sentinel: str) -> bool:
    return any(sentinel in c for c in _sent_contents(fake))


def _done_frame(frames):
    done = [f for f in frames if f.event == "done"]
    assert len(done) == 1, [f.event for f in frames]
    return done[0]


# Sentinels: one per transcript region. Each appears in exactly one seeded row.
MAIN_BEFORE = "MAIN-BEFORE-FACT"
MAIN_AFTER = "MAIN-AFTER-FACT"
SIDE_A = "SIDE-A-FACT"
SIDE_B = "SIDE-B-FACT"

SID_A = 880000000000000001
SID_B = 880000000000000002


# ---------------------------------------------------------------------------
# DoD-8 -- both rows of a turn are stamped with the pointer (or None)
# ---------------------------------------------------------------------------


# DoD-8 (UC-110 step 3): a turn run while a side chat is active persists BOTH the
# user row and the assistant row with `side_chat_id` equal to the pointer.
async def test_turn_inside_active_side_chat_stamps_both_rows__DoD8(
    db: DbConfig, monkeypatch
):
    context = await _context()
    await _activate(context, SID_A)
    _install_client(monkeypatch, _FakeClient(chunks=["side reply"]))

    frames = await _run(context, "side question")

    assert frames[-1].event == "done"
    stored = await _messages(context.chat.id)
    assert [m.role for m in stored] == ["user", "assistant"]
    assert [m.content for m in stored] == ["side question", "side reply"]
    assert [m.side_chat_id for m in stored] == [SID_A, SID_A]


# DoD-8 (UC-110 step 3): a turn run with no active side chat persists both rows
# with `side_chat_id` None -- the main line.
async def test_turn_without_side_chat_leaves_both_rows_main_line__DoD8(
    db: DbConfig, monkeypatch
):
    context = await _context()
    assert context.chat.active_side_chat_id is None
    _install_client(monkeypatch, _FakeClient(chunks=["main reply"]))

    frames = await _run(context, "main question")

    assert frames[-1].event == "done"
    stored = await _messages(context.chat.id)
    assert [m.role for m in stored] == ["user", "assistant"]
    assert [m.side_chat_id for m in stored] == [None, None]


# ---------------------------------------------------------------------------
# DoD-9 -- inside a side chat, the main line before it is visible
# ---------------------------------------------------------------------------


# DoD-9 (US-136.AC-1): a turn inside an active side chat receives, in the
# messages handed to the model, a fact stated only in a main-line message that
# precedes the side chat.
#
# The scenario also seeds a FINISHED side chat B (rows carry SID_B, the pointer
# is SID_A) between the main line and the active side chat. UC-115 step 1 /
# DoD-12 (D-C): a turn inside an active side chat never receives a finished
# side chat's rows -- so the model must see MAIN_BEFORE and must NOT see SIDE_B.
# The exclusion is what distinguishes the filtered transcript read from an
# unfiltered "hand the model every row" load.
async def test_side_chat_turn_sees_preceding_main_line__DoD9(
    db: DbConfig, monkeypatch
):
    context = await _context()
    cid = context.chat.id
    await _seed_row(cid, role="user", content=MAIN_BEFORE, position=0)
    await _seed_row(cid, role="assistant", content="main reply", position=1)
    # Finished side chat B: rows stamped SID_B, never the pointer for this turn.
    await _seed_row(cid, role="user", content=SIDE_B, position=2, side_chat_id=SID_B)
    await _seed_row(cid, role="assistant", content="side b reply", position=3, side_chat_id=SID_B)
    await _activate(context, SID_A)
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    frames = await _run(context, "side question")

    assert frames[-1].event == "done"
    # The clause under test: the preceding main line is visible inside side chat A.
    assert _sent(fake, MAIN_BEFORE)
    # The companion exclusion (UC-115 step 1): finished side chat B is not.
    assert not _sent(fake, SIDE_B)


# ---------------------------------------------------------------------------
# DoD-10 -- inside a side chat, its own earlier messages are visible
# ---------------------------------------------------------------------------


# DoD-10 (US-136.AC-2): a turn inside an active side chat receives a fact stated
# only in an earlier message of that same side chat.
#
# The scenario also seeds a FINISHED side chat B (rows carry SID_B, the pointer
# is SID_A) before side chat A's own earlier exchange. UC-115 step 1 / DoD-12
# (D-C): the turn inside A must see A's own earlier row (SIDE_A) and the main
# line, and must NOT see SIDE_B -- the exclusion is what makes a presence
# assertion meaningful against an unfiltered transcript load.
async def test_side_chat_turn_sees_its_own_earlier_messages__DoD10(
    db: DbConfig, monkeypatch
):
    context = await _context()
    cid = context.chat.id
    await _seed_row(cid, role="user", content="main opener", position=0)
    await _seed_row(cid, role="assistant", content="main reply", position=1)
    # Finished side chat B: rows stamped SID_B, never the pointer for this turn.
    await _seed_row(cid, role="user", content=SIDE_B, position=2, side_chat_id=SID_B)
    await _seed_row(cid, role="assistant", content="side b reply", position=3, side_chat_id=SID_B)
    # Active side chat A's own earlier exchange.
    await _seed_row(cid, role="user", content=SIDE_A, position=4, side_chat_id=SID_A)
    await _seed_row(cid, role="assistant", content="side reply", position=5, side_chat_id=SID_A)
    await _activate(context, SID_A)
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    frames = await _run(context, "second side question")

    assert frames[-1].event == "done"
    # The clause under test: A's own earlier message is visible inside A.
    assert _sent(fake, SIDE_A)
    # And the main line before it, as DoD-9 requires, is still there too.
    assert _sent(fake, "main opener")
    # The companion exclusion (UC-115 step 1): finished side chat B is not.
    assert not _sent(fake, SIDE_B)


# ---------------------------------------------------------------------------
# DoD-11 -- after a finish, the main line does not see the side chat
# ---------------------------------------------------------------------------


# DoD-11 (US-138.AC-1): a main-line turn after a side chat is finished (pointer
# null, rows still carry the id) does NOT receive a fact stated only in that
# side chat, while still receiving the main-line messages around it.
async def test_main_line_turn_after_finish_excludes_side_chat__DoD11(
    db: DbConfig, monkeypatch
):
    context = await _context()
    cid = context.chat.id
    await _seed_row(cid, role="user", content=MAIN_BEFORE, position=0)
    await _seed_row(cid, role="assistant", content="main reply 1", position=1)
    # A finished side chat: rows carry SID_A, the pointer stays None.
    await _seed_row(cid, role="user", content=SIDE_A, position=2, side_chat_id=SID_A)
    await _seed_row(cid, role="assistant", content="side reply", position=3, side_chat_id=SID_A)
    await _seed_row(cid, role="user", content=MAIN_AFTER, position=4)
    await _seed_row(cid, role="assistant", content="main reply 2", position=5)
    assert context.chat.active_side_chat_id is None
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    frames = await _run(context, "main question")

    assert frames[-1].event == "done"
    assert not _sent(fake, SIDE_A)
    assert _sent(fake, MAIN_BEFORE)
    assert _sent(fake, MAIN_AFTER)
    # The finished side chat's rows are untouched by the main-line turn.
    stored = await _messages(cid)
    stamped = [m.side_chat_id for m in stored if m.content in (SIDE_A, "side reply")]
    assert stamped == [SID_A, SID_A]


# ---------------------------------------------------------------------------
# DoD-12 -- side chat B does not see finished side chat A
# ---------------------------------------------------------------------------


# DoD-12 (UC-115 steps 1-2): a turn inside active side chat B does not receive a
# fact stated only in FINISHED side chat A, while receiving the main line and
# B's own earlier messages.
async def test_side_chat_b_excludes_finished_side_chat_a__DoD12(
    db: DbConfig, monkeypatch
):
    context = await _context()
    cid = context.chat.id
    await _seed_row(cid, role="user", content=MAIN_BEFORE, position=0)
    await _seed_row(cid, role="assistant", content="main reply 1", position=1)
    # Finished side chat A.
    await _seed_row(cid, role="user", content=SIDE_A, position=2, side_chat_id=SID_A)
    await _seed_row(cid, role="assistant", content="side a reply", position=3, side_chat_id=SID_A)
    await _seed_row(cid, role="user", content=MAIN_AFTER, position=4)
    await _seed_row(cid, role="assistant", content="main reply 2", position=5)
    # Active side chat B with one earlier exchange.
    await _seed_row(cid, role="user", content=SIDE_B, position=6, side_chat_id=SID_B)
    await _seed_row(cid, role="assistant", content="side b reply", position=7, side_chat_id=SID_B)
    await _activate(context, SID_B)
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    frames = await _run(context, "second side b question")

    assert frames[-1].event == "done"
    assert not _sent(fake, SIDE_A)
    assert _sent(fake, MAIN_BEFORE)
    assert _sent(fake, MAIN_AFTER)
    assert _sent(fake, SIDE_B)


# ---------------------------------------------------------------------------
# DoD-13 -- the retry path (no user row) stamps the assistant row
# ---------------------------------------------------------------------------


# DoD-13 (D-C): a retry turn (prompt None, so no user row is written) while a side
# chat is active persists the assistant row with `side_chat_id` equal to the
# pointer.
async def test_retry_inside_active_side_chat_stamps_assistant_row__DoD13(
    db: DbConfig, monkeypatch
):
    context = await _context()
    cid = context.chat.id
    await _seed_row(cid, role="user", content="main opener", position=0)
    await _seed_row(cid, role="assistant", content="main reply", position=1)
    # The prior (failed) side-chat turn left its user row and no assistant reply.
    await _seed_row(cid, role="user", content="stored side question", position=2, side_chat_id=SID_A)
    await _activate(context, SID_A)
    _install_client(monkeypatch, _FakeClient(chunks=["retried reply"]))

    frames = await _run(context, None)

    assert frames[-1].event == "done"
    stored = await _messages(cid)
    user_rows = [m for m in stored if m.role == "user"]
    assistant_rows = [m for m in stored if m.role == "assistant"]
    # No user row was added by the retry; exactly one new assistant row landed.
    assert [m.content for m in user_rows] == ["main opener", "stored side question"]
    assert len(assistant_rows) == 2
    new_reply = assistant_rows[-1]
    assert new_reply.content == "retried reply"
    assert new_reply.side_chat_id == SID_A


# ---------------------------------------------------------------------------
# DoD-14 -- the `done` frame carries the stamp as a decimal string
# ---------------------------------------------------------------------------


# DoD-14 (D-E, the single-mapper rule): the turn's `done` frame carries the
# persisted assistant message with `side_chat_id` equal to the pointer as a
# decimal string.
async def test_done_frame_message_carries_side_chat_id_string__DoD14(
    db: DbConfig, monkeypatch
):
    context = await _context()
    await _activate(context, SID_A)
    _install_client(monkeypatch, _FakeClient(chunks=["the answer"]))

    frames = await _run(context, "ask")

    done = _done_frame(frames)
    assert isinstance(done.data, DoneFrame)
    assert done.data.message.content == "the answer"
    assert done.data.message.side_chat_id == str(SID_A)
    assert type(done.data.message.side_chat_id) is str


# DoD-14 (D-E): with no side chat active, the `done` frame's message carries
# `side_chat_id` None -- the same mapper, the other branch.
async def test_done_frame_message_side_chat_id_is_none_on_main_line__DoD14(
    db: DbConfig, monkeypatch
):
    context = await _context()
    _install_client(monkeypatch, _FakeClient(chunks=["the answer"]))

    frames = await _run(context, "ask")

    done = _done_frame(frames)
    assert isinstance(done.data, DoneFrame)
    assert done.data.message.side_chat_id is None
