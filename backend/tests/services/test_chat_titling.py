"""Background chat auto-titling — 023.chat-ux-revision, DoD-1 · DoD-2 · DoD-3.

Bound to the frozen skeleton (status.md -> `## Skeleton`), in
``app.services.chat_titling``:
    _TITLE_TRIGGER_COUNTS: frozenset[int] = frozenset({1, 5})
    _TITLE_MAX_LENGTH = 80
    def _is_titling_trigger(user_message_count: int) -> bool
    def _build_title_transcript(messages: list[ChatMessage]) -> list[LLMMessage]
    def _sanitize_title(raw: str) -> str
    async def maybe_title_chat(access: authz.BookAccess, chat_id: str)
        -> ChatTitleResponse
and ``app.models.schemas.chats.ChatTitleResponse { title: str; changed: bool }``.

No network / no real LLM. The client-construction path is the seam, exactly as in
``test_chat_turn.py``: a fake ``LLMClient`` (async context manager) is monkeypatched
in at ``app.services.llm_servers.create_model_client`` and — belt and braces, in case
of a direct import — at ``app.services.chat_titling.create_model_client``
(``raising=False``). The delivered ``_FakeClient`` in ``test_chat_turn.py`` implements
only ``chat_with_tools``; titling calls ``.chat()``, so this module carries its own
sibling fake rather than reshaping that one.

Expected values come from the SPEC ONLY -- `plan.md` -> Definition of done (DoD-1,
DoD-2, DoD-3), its Interface section for ``chat_titling``, and `context.md`'s backend
ground truth -- never from implementation internals:
  - DoD-1: titling fires when the persisted USER-message count is exactly 1 and
    exactly 5; counts 2, 3, 4 and 6 return the existing title with ``changed=False``
    and make NO LLM call at all (the client is never even constructed);
  - DoD-2: every member of the failure taxonomy
    ``(aiohttp.ClientError, LLMError, ValueError, RuntimeError)``, plus a blank /
    whitespace-only sanitized result, leaves the existing title intact, returns
    ``changed=False``, persists nothing, and raises nothing;
  - DoD-3: a successful titling call is made through the CHAT'S OWN configured
    ``(llm_server_id, model_name)`` pair, and the sanitized single-line title is
    persisted on the chat row.

``asyncio_mode = "auto"``.
"""

import aiohttp
import pytest
from llm import LLMError

from app.db import books, chat_messages, chats, llm_servers, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chat import Chat, ChatMessage
from app.models.llm_server import LlmServer
from app.models.user import User, UserRole
from app.services import chat_titling
from app.services.authz import AccessRole, BookAccess

# ---------------------------------------------------------------------------
# The fake LLM client -- the substituted construction seam.
# ---------------------------------------------------------------------------


class _FakeTitleClient:
    """A stand-in for ``llm.LLMClient`` used as an async context manager.

    Titling is a one-shot, non-streaming call, so only ``chat`` is implemented. It
    records the messages it was handed, then either raises the configured exception
    or returns the configured raw string. ``constructed`` records every
    ``create_model_client(server, resolved_key, model)`` triple, so a test can assert
    the client was never even built (the off-trigger "no LLM call" clause) or that it
    was built for a specific model pair.
    """

    def __init__(self, *, result: str = "", exc: BaseException | None = None):
        self._result = result
        self._exc = exc
        self.constructed: list[tuple] = []
        self.calls: list[dict] = []
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True
        return False

    async def chat(
        self,
        messages,
        *,
        system=None,
        options=None,
        stream=False,
        on_delta=None,
        **kwargs,
    ):
        self.calls.append({"messages": messages, "system": system, "options": options})
        if self._exc is not None:
            raise self._exc
        return self._result


def _install_client(monkeypatch, fake: _FakeTitleClient) -> _FakeTitleClient:
    """Monkeypatch ``create_model_client`` (the frozen seam) to yield ``fake``."""

    def factory(server, resolved_key, model):
        fake.constructed.append((server, resolved_key, model))
        return fake

    monkeypatch.setattr("app.services.llm_servers.create_model_client", factory)
    monkeypatch.setattr(
        "app.services.chat_titling.create_model_client", factory, raising=False
    )
    return fake


# ---------------------------------------------------------------------------
# Seeding helpers (rows constructed through the db layer).
# ---------------------------------------------------------------------------


ORIGINAL_TITLE = "New chat"


async def _seed_world(
    *,
    title: str = ORIGINAL_TITLE,
    model_name: str | None = "gpt-x",
) -> tuple[BookAccess, Chat, LlmServer]:
    """Seed user + book + server + chat, and build the caller's ``BookAccess``."""
    user = await users.create(User(username="author", role=UserRole.author))
    book = await books.create(
        Book(
            title="A Book",
            description="d",
            owner_id=user.id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt="",
            active_notes="",
        )
    )
    server = await llm_servers.create(
        LlmServer(
            name="S",
            backend_type="openai",
            base_url="https://api.example.com/v1",
            api_key="sk-stored",
            enabled_models='["gpt-x"]',
            is_active=True,
        )
    )
    chat = await chats.create(
        Chat(
            book_id=book.id,
            author_id=user.id,
            title=title,
            llm_server_id=server.id,
            model_name=model_name,
        )
    )
    access = BookAccess(
        book_id=book.id,
        user_id=user.id,
        role=AccessRole.owner,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=CollaborationMode.free,
    )
    return access, chat, server


async def _seed_exchanges(chat_id: int, user_message_count: int) -> None:
    """Persist ``user_message_count`` completed exchanges (one user + one assistant).

    Interleaving assistant replies is deliberate: the trigger is the count of USER
    messages, so a transcript whose TOTAL message count is never 1 or 5 keeps the
    boundary honest.
    """
    position = 0
    for index in range(user_message_count):
        await chat_messages.create(
            ChatMessage(
                chat_id=chat_id,
                role="user",
                content=f"question {index}",
                position=position,
            )
        )
        position += 1
        await chat_messages.create(
            ChatMessage(
                chat_id=chat_id,
                role="assistant",
                content=f"answer {index}",
                position=position,
            )
        )
        position += 1


# ---------------------------------------------------------------------------
# DoD-1 — the trigger boundary: exactly 1 and exactly 5, never `>=`
# ---------------------------------------------------------------------------


# DoD-1: at a user-message count of exactly 1 and exactly 5, titling fires -- the
# model client is constructed and called, and the chat is reported as retitled.
@pytest.mark.parametrize("user_message_count", [1, 5])
async def test_titling_fires_at_exactly_one_and_five__DoD1(
    db: DbConfig, monkeypatch, user_message_count: int
):
    access, chat, _server = await _seed_world()
    await _seed_exchanges(chat.id, user_message_count)
    fake = _install_client(monkeypatch, _FakeTitleClient(result="A Generated Title"))

    result = await chat_titling.maybe_title_chat(access, str(chat.id))

    # The LLM was actually reached...
    assert len(fake.constructed) == 1
    assert len(fake.calls) == 1
    # ...and the chat was retitled.
    assert result.changed is True
    assert result.title == "A Generated Title"


# DoD-1: at every other user-message count the existing title is returned with
# `changed=False` and NO LLM call is made -- the client is never constructed, so the
# trigger is an exact-membership test, not a `>=` threshold.
@pytest.mark.parametrize("user_message_count", [2, 3, 4, 6])
async def test_titling_silent_off_trigger_with_no_llm_call__DoD1(
    db: DbConfig, monkeypatch, user_message_count: int
):
    access, chat, _server = await _seed_world()
    await _seed_exchanges(chat.id, user_message_count)
    fake = _install_client(monkeypatch, _FakeTitleClient(result="Should Not Be Used"))

    result = await chat_titling.maybe_title_chat(access, str(chat.id))

    # No LLM call at all -- not merely a discarded result.
    assert fake.constructed == []
    assert fake.calls == []
    # The existing title stands, unchanged and unpersisted-over.
    assert result.changed is False
    assert result.title == ORIGINAL_TITLE
    stored = await chats.get_by_id(chat.id)
    assert stored is not None
    assert stored.title == ORIGINAL_TITLE


# ---------------------------------------------------------------------------
# DoD-2 — the failure taxonomy plus a blank result: swallowed identically
# ---------------------------------------------------------------------------


# DoD-2: on a trigger count, every failure-taxonomy exception -- and a blank or
# whitespace-only model result, which the sanitizer reduces to nothing usable --
# leaves the existing title intact, returns `changed=False`, persists nothing and
# raises nothing. A titling failure must never surface as a request failure.
@pytest.mark.parametrize(
    "exc, raw",
    [
        (aiohttp.ClientError("connection reset"), None),
        (LLMError("upstream 500"), None),
        (ValueError("bad payload"), None),
        (RuntimeError("no model available"), None),
        (None, ""),
        (None, "   \n\t  "),
    ],
    ids=[
        "aiohttp-client-error",
        "llm-error",
        "value-error",
        "runtime-error",
        "empty-result",
        "whitespace-only-result",
    ],
)
async def test_titling_failure_leaves_title_intact_and_raises_nothing__DoD2(
    db: DbConfig, monkeypatch, exc, raw
):
    access, chat, _server = await _seed_world()
    await _seed_exchanges(chat.id, 1)  # a trigger count: the LLM path IS taken
    fake = _install_client(
        monkeypatch, _FakeTitleClient(result=raw or "", exc=exc)
    )

    # Nothing is raised out of the titler.
    result = await chat_titling.maybe_title_chat(access, str(chat.id))

    # The failing path really was exercised (the client was built and called).
    assert len(fake.constructed) == 1
    assert len(fake.calls) == 1
    # The existing title stands: nothing changed, nothing persisted.
    assert result.changed is False
    assert result.title == ORIGINAL_TITLE
    stored = await chats.get_by_id(chat.id)
    assert stored is not None
    assert stored.title == ORIGINAL_TITLE


# ---------------------------------------------------------------------------
# DoD-3 — success: the chat's OWN model pair, a sanitized single-line title
# ---------------------------------------------------------------------------


# DoD-3 (decision D4 -- no global/utility model exists, so the client must resolve
# per-chat): a successful titling call constructs the client for the chat's own
# (llm_server_id, model_name) pair, and the sanitized result -- wrapping quotes and
# newlines stripped, collapsed to a single line -- is persisted on the chat row and
# returned with `changed=True`.
async def test_successful_titling_uses_chat_pair_and_persists_sanitized_title__DoD3(
    db: DbConfig, monkeypatch
):
    access, chat, chat_server = await _seed_world(model_name="chat-own-model")
    # A second, unrelated server exists: picking the chat's own pair must be a
    # resolution, not a "first server wins" accident.
    other = await llm_servers.create(
        LlmServer(
            name="Other",
            backend_type="openai",
            base_url="https://other.example.com/v1",
            api_key="sk-other",
            enabled_models='["other-model"]',
            is_active=True,
        )
    )
    await _seed_exchanges(chat.id, 1)
    fake = _install_client(
        monkeypatch, _FakeTitleClient(result='"A Grand Title"\n')
    )

    result = await chat_titling.maybe_title_chat(access, str(chat.id))

    # Bound to the CHAT'S own model pair.
    assert len(fake.constructed) == 1
    used_server, _used_key, used_model = fake.constructed[0]
    assert used_server.id == chat_server.id
    assert used_server.id != other.id
    assert used_model == "chat-own-model"

    # The sanitized title: no wrapping quotes, no newline, one line.
    assert result.changed is True
    assert result.title == "A Grand Title"
    assert "\n" not in result.title

    # ...and it is what got persisted.
    stored = await chats.get_by_id(chat.id)
    assert stored is not None
    assert stored.title == "A Grand Title"
