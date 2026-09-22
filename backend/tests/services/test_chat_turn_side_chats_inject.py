"""Tests for what the turn sees after a side chat is injected or deleted
(feature 027.side-chats, step 003 -- DoD-3, DoD-8, DoD-11).

Bound to the frozen skeleton (status.md -> Skeleton -> Steps 001 / 002 / 003):
    app.services.chats.inject_side_chat(access: authz.BookAccess, chat_id: str,
        side_chat_id: str) -> ChatDetailResponse
    app.services.chats.delete_side_chat(access: authz.BookAccess, chat_id: str,
        side_chat_id: str) -> None
    app.services.chat_turn.run_turn(context: TurnContext, prompt: str | None)
        -> AsyncGenerator[TurnFrame, None]        (signature unchanged)
    app.db.chat_messages.list_by_chat_ordered(chat_id) (unfiltered read-back)

The inject / delete is performed through the SERVICE function (no HTTP needed
in a service test) before running a turn with the fake client. Rows carry
sentinel strings per transcript region; every "a fact stated only in X is / is
not handed to the model" criterion asserts on ``fake.call["messages"]``.

No network / no real LLM: the fake ``LLMClient`` and the ``create_model_client``
monkeypatch are copied verbatim from tests/services/test_chat_turn.py, the
seeding helpers from tests/services/test_chat_turn_side_chats.py, and the
``_access`` builder from tests/services/test_assistant_runtime.py (every test
module defines its own local helpers).

Expected values come from the SPEC ONLY -- the step DoD, the Interface intent,
and context.md decisions D-C / D-D -- never from implementation internals.
``asyncio_mode = "auto"``.
"""

import inspect

from app.db import books, chat_messages, chats, llm_servers, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chat import Chat, ChatMessage
from app.models.llm_server import LlmServer
from app.models.schemas.chats import ChatDetailResponse
from app.models.user import User, UserRole
from app.services import chat_turn
from app.services import chats as chats_service
from app.services.authz import AccessRole, BookAccess
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
# The access builder -- copied from tests/services/test_assistant_runtime.py.
# ---------------------------------------------------------------------------


def _access(book_id: int, user_id: int) -> BookAccess:
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=AccessRole.owner,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=CollaborationMode.free,
    )


# ---------------------------------------------------------------------------
# Side-chat helpers -- copied from tests/services/test_chat_turn_side_chats.py,
# plus the owner-access and context-refresh helpers local to this module.
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


def _owner_access(context: TurnContext) -> BookAccess:
    """The access the `book_access` dependency would resolve for the chat's own
    author in the chat's own book."""
    return _access(context.chat.book_id, context.chat.author_id)


async def _refreshed(context: TurnContext) -> TurnContext:
    """A TurnContext over the chat row as it is NOW in the database -- used after
    a service call may have cleared the pointer, so the turn captures the
    persisted state rather than the stale in-memory row."""
    chat = await chats.get_by_id(context.chat.id)
    assert chat is not None
    return TurnContext(chat=chat, server=context.server, resolved_key=context.resolved_key)


# Sentinels: one per transcript region. Each appears in exactly one seeded row.
MAIN_BEFORE = "MAIN-BEFORE-FACT"
MAIN_AFTER = "MAIN-AFTER-FACT"
SIDE_A = "SIDE-A-FACT"
SIDE_A_REPLY = "SIDE-A-REPLY-FACT"
SIDE_B = "SIDE-B-FACT"

SID_A = 880000000000000101
SID_B = 880000000000000102


# ---------------------------------------------------------------------------
# DoD-3 -- after inject, the next main-line turn sees the injected messages
# ---------------------------------------------------------------------------


# DoD-3 (US-139.AC-2): after a FINISHED side chat is injected, the next
# main-line turn receives, in the messages handed to the model, a fact stated
# only in the injected messages -- alongside the main line around them.
async def test_main_line_turn_after_inject_sees_injected_messages__DoD3(
    db: DbConfig, monkeypatch
):
    context = await _context()
    cid = context.chat.id
    await _seed_row(cid, role="user", content=MAIN_BEFORE, position=0)
    await _seed_row(cid, role="assistant", content="main reply 1", position=1)
    # A finished side chat: rows carry SID_A, the pointer stays None.
    await _seed_row(cid, role="user", content=SIDE_A, position=2, side_chat_id=SID_A)
    await _seed_row(cid, role="assistant", content=SIDE_A_REPLY, position=3, side_chat_id=SID_A)
    await _seed_row(cid, role="user", content=MAIN_AFTER, position=4)
    await _seed_row(cid, role="assistant", content="main reply 2", position=5)
    assert context.chat.active_side_chat_id is None

    detail = await chats_service.inject_side_chat(
        _owner_access(context), str(cid), str(SID_A)
    )

    assert isinstance(detail, ChatDetailResponse)
    assert detail.chat.active_side_chat_id is None
    assert [m.side_chat_id for m in detail.messages] == [None] * 6
    assert [m.position for m in detail.messages] == [0, 1, 2, 3, 4, 5]

    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))
    frames = await _run(await _refreshed(context), "main question")

    assert frames[-1].event == "done"
    assert _sent(fake, SIDE_A)
    assert _sent(fake, SIDE_A_REPLY)
    assert _sent(fake, MAIN_BEFORE)
    assert _sent(fake, MAIN_AFTER)


# DoD-3 (US-139.AC-2; UC-112 step 2): injecting the ACTIVE side chat makes its
# messages main line and returns the author to the main line -- the next turn
# is a main-line turn (both new rows unstamped) and it still sees the injected
# fact. A different, finished side chat stays excluded.
async def test_main_line_turn_after_injecting_active_side_chat_sees_it__DoD3(
    db: DbConfig, monkeypatch
):
    context = await _context()
    cid = context.chat.id
    await _seed_row(cid, role="user", content=MAIN_BEFORE, position=0)
    await _seed_row(cid, role="assistant", content="main reply 1", position=1)
    # Finished side chat B, never injected.
    await _seed_row(cid, role="user", content=SIDE_B, position=2, side_chat_id=SID_B)
    await _seed_row(cid, role="assistant", content="side b reply", position=3, side_chat_id=SID_B)
    # Active side chat A.
    await _seed_row(cid, role="user", content=SIDE_A, position=4, side_chat_id=SID_A)
    await _seed_row(cid, role="assistant", content=SIDE_A_REPLY, position=5, side_chat_id=SID_A)
    await _activate(context, SID_A)

    detail = await chats_service.inject_side_chat(
        _owner_access(context), str(cid), str(SID_A)
    )

    assert detail.chat.active_side_chat_id is None
    by_content = {m.content: m.side_chat_id for m in detail.messages}
    assert by_content[SIDE_A] is None
    assert by_content[SIDE_A_REPLY] is None
    assert by_content[SIDE_B] == str(SID_B)

    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))
    frames = await _run(await _refreshed(context), "main question")

    assert frames[-1].event == "done"
    assert _sent(fake, SIDE_A)
    assert _sent(fake, SIDE_A_REPLY)
    assert _sent(fake, MAIN_BEFORE)
    assert not _sent(fake, SIDE_B)
    # The turn was a main-line turn: its two new rows are unstamped.
    stored = await _messages(cid)
    new_rows = [m for m in stored if m.content in ("main question", "ok")]
    assert [m.side_chat_id for m in new_rows] == [None, None]


# ---------------------------------------------------------------------------
# DoD-8 -- after delete, the turn sees nothing from the deleted rows
# ---------------------------------------------------------------------------


# DoD-8 (UC-115 step 4): after a FINISHED side chat is deleted, a turn's
# messages handed to the model contain nothing from the deleted rows, while the
# main line around them is still handed over; the deleted rows are gone from
# the unfiltered read-back too.
async def test_turn_after_deleting_finished_side_chat_sees_nothing_of_it__DoD8(
    db: DbConfig, monkeypatch
):
    context = await _context()
    cid = context.chat.id
    await _seed_row(cid, role="user", content=MAIN_BEFORE, position=0)
    await _seed_row(cid, role="assistant", content="main reply 1", position=1)
    await _seed_row(cid, role="user", content=SIDE_A, position=2, side_chat_id=SID_A)
    await _seed_row(cid, role="assistant", content=SIDE_A_REPLY, position=3, side_chat_id=SID_A)
    await _seed_row(cid, role="user", content=MAIN_AFTER, position=4)
    await _seed_row(cid, role="assistant", content="main reply 2", position=5)
    assert context.chat.active_side_chat_id is None

    result = await chats_service.delete_side_chat(
        _owner_access(context), str(cid), str(SID_A)
    )
    assert result is None

    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))
    frames = await _run(await _refreshed(context), "main question")

    assert frames[-1].event == "done"
    assert not _sent(fake, SIDE_A)
    assert not _sent(fake, SIDE_A_REPLY)
    assert _sent(fake, MAIN_BEFORE)
    assert _sent(fake, MAIN_AFTER)
    stored = await _messages(cid)
    assert all(SIDE_A not in m.content for m in stored)
    assert all(m.side_chat_id != SID_A for m in stored)


# DoD-8 (UC-115 step 4; UC-113 step 4): deleting the ACTIVE side chat removes
# its rows and clears the pointer -- the next turn is a main-line turn that is
# handed nothing from the deleted rows and stamps its new rows with None.
async def test_turn_after_deleting_active_side_chat_sees_nothing_of_it__DoD8(
    db: DbConfig, monkeypatch
):
    context = await _context()
    cid = context.chat.id
    await _seed_row(cid, role="user", content=MAIN_BEFORE, position=0)
    await _seed_row(cid, role="assistant", content="main reply 1", position=1)
    await _seed_row(cid, role="user", content=SIDE_A, position=2, side_chat_id=SID_A)
    await _seed_row(cid, role="assistant", content=SIDE_A_REPLY, position=3, side_chat_id=SID_A)
    await _activate(context, SID_A)

    await chats_service.delete_side_chat(_owner_access(context), str(cid), str(SID_A))

    refreshed = await _refreshed(context)
    assert refreshed.chat.active_side_chat_id is None
    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))
    frames = await _run(refreshed, "main question")

    assert frames[-1].event == "done"
    assert not _sent(fake, SIDE_A)
    assert not _sent(fake, SIDE_A_REPLY)
    assert _sent(fake, MAIN_BEFORE)
    stored = await _messages(cid)
    assert [m.content for m in stored] == [
        MAIN_BEFORE,
        "main reply 1",
        "main question",
        "ok",
    ]
    assert [m.side_chat_id for m in stored] == [None, None, None, None]


# ---------------------------------------------------------------------------
# DoD-11 -- a delete leaves a gap; the next turn appends at max+1, no renumbering
# ---------------------------------------------------------------------------


# DoD-11 (D-D -- no renumbering): positions 0..4 with the side chat at 1..3;
# after the delete the survivors keep 0 and 4, the next turn's two new rows
# land at 5 and 6 (max+1 over the survivors), and the ordered read-back is
# strictly ascending in `position`.
async def test_turn_after_delete_appends_at_max_plus_one_no_renumbering__DoD11(
    db: DbConfig, monkeypatch
):
    context = await _context()
    cid = context.chat.id
    await _seed_row(cid, role="user", content=MAIN_BEFORE, position=0)
    await _seed_row(cid, role="assistant", content="side reply 1", position=1, side_chat_id=SID_A)
    await _seed_row(cid, role="user", content=SIDE_A, position=2, side_chat_id=SID_A)
    await _seed_row(cid, role="assistant", content="side reply 2", position=3, side_chat_id=SID_A)
    await _seed_row(cid, role="assistant", content=MAIN_AFTER, position=4)
    assert context.chat.active_side_chat_id is None

    await chats_service.delete_side_chat(_owner_access(context), str(cid), str(SID_A))

    # The gap is left as is: survivors keep 0 and 4.
    survivors = await _messages(cid)
    assert [(m.content, m.position) for m in survivors] == [
        (MAIN_BEFORE, 0),
        (MAIN_AFTER, 4),
    ]

    _install_client(monkeypatch, _FakeClient(chunks=["new reply"]))
    frames = await _run(await _refreshed(context), "new question")

    assert frames[-1].event == "done"
    stored = await _messages(cid)
    assert [(m.content, m.position) for m in stored] == [
        (MAIN_BEFORE, 0),
        (MAIN_AFTER, 4),
        ("new question", 5),
        ("new reply", 6),
    ]
    positions = [m.position for m in stored]
    assert positions == sorted(positions)
    assert len(set(positions)) == len(positions)
    assert [m.side_chat_id for m in stored] == [None, None, None, None]
