"""End-to-end tests for the `canvas` SSE frame (feature 013, step 010).

Exercised in-process against the real ``app.main.app`` via the ``http_client``
fixture (httpx ``ASGITransport``, no live server, no network), through the
already-shipped endpoint::

    POST /api/books/{book_id}/chats/{chat_id}/turn  ->  StreamingResponse
        (media_type text/event-stream; every frame serialized
         "event: <event>\\ndata: <payload json>\\n\\n")
    body: TurnRequest { prompt, subject_kind, subject_id, codex_kind }

Bound to the frozen skeleton (``status.md`` -> ``## Skeleton`` -> Step 010):
``app.models.schemas.chats.CanvasFrame`` { subject_kind; subject_id; field; text }
and the `write_codex_draft` ``TOOL_REGISTRY`` entry, mode-gated by a
``mode_tool`` row.

The LLM boundary is faked: ``create_model_client`` is monkeypatched to a fake
``LLMClient`` whose ``chat_with_tools`` drives ``on_delta`` with scripted chunks
AND INVOKES the tool callable it was handed -- which is what makes DoD-2 bite
(``010.context.md`` -> "Route-level test shape"). Auth is real: users are seeded
and a real JWT is minted, mirroring tests/routes/test_chats.py.

Expected values come from the SPEC ONLY -- ``010.shared-canvas-write.md`` ->
DoD-2 and DoD-3, ``context.md`` -> "The shared-canvas write design" points 2 and
5 -- never from implementation internals. ``asyncio_mode = "auto"``.

Note the deliberate absence: ``backend/app/routes/chats.py`` is NOT changed by
this step. Its serializer is generic over the event name, so a `canvas` frame
reaches the wire with zero route edits -- which is exactly what these tests
observe from outside.
"""

import inspect
import json

from app.db import (
    assistant_modes,
    books,
    chat_messages,
    chats,
    codex_entries,
    codex_entry_versions,
    llm_servers,
    mode_tools,
    users,
)
from app.db.engine import init_db, set_db_ready
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chat import Chat
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.llm_server import LlmServer
from app.models.mode_tool import ModeTool
from app.models.schemas.chats import CanvasFrame
from app.models.user import User, UserRole
from app.services import auth

DRAFT = "Halden keeps the north gate through the long winter."


# ---------------------------------------------------------------------------
# The fake LLM client -- substituted at the construction seam. It INVOKES the
# tool callable it was handed, between two scripted prose chunks.
# ---------------------------------------------------------------------------


class _ToolInvokingClient:
    """Streams prose, calls one tool mid-stream, then streams more prose."""

    def __init__(
        self,
        *,
        before=("Let me draft that. ",),
        after=("Done -- take a look.",),
        tool_name="write_codex_draft",
        tool_args=None,
        return_value="Let me draft that. Done -- take a look.",
    ):
        self._before = list(before)
        self._after = list(after)
        self._tool_name = tool_name
        self._tool_args = dict(tool_args or {"field": "body", "text": DRAFT})
        self._return_value = return_value
        self.tools = None
        self.tool_definition_names = None
        self.tool_result = None
        self.tool_invoked = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def chat_with_tools(
        self, messages, *, tools_definitions=None, tools=None, on_delta=None, **kwargs
    ):
        self.tools = tools
        self.tool_definition_names = {
            d["function"]["name"] for d in (tools_definitions or [])
        }

        async def _drive(chunks):
            if on_delta is None:
                return
            for chunk in chunks:
                result = on_delta(chunk)
                if inspect.isawaitable(result):
                    await result

        await _drive(self._before)

        if tools and self._tool_name in tools:
            self.tool_invoked = True
            result = tools[self._tool_name](**self._tool_args)
            if inspect.isawaitable(result):
                result = await result
            self.tool_result = result

        await _drive(self._after)
        return self._return_value


def _install_client(monkeypatch, fake) -> None:
    def factory(server, resolved_key, model):
        return fake

    monkeypatch.setattr("app.services.llm_servers.create_model_client", factory)
    monkeypatch.setattr(
        "app.services.chat_turn.create_model_client", factory, raising=False
    )


# ---------------------------------------------------------------------------
# Seeding + request helpers (copied from tests/routes/test_chats.py).
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


async def _seed_server(*, api_key: str) -> LlmServer:
    return await llm_servers.create(
        LlmServer(
            name="S",
            backend_type="openai",
            base_url="https://api.example.com/v1",
            api_key=api_key,
            enabled_models='["gpt-x"]',
            is_active=True,
        )
    )


async def _seed_chat(book_id: int, author_id: int, server_id: int) -> Chat:
    return await chats.create(
        Chat(
            book_id=book_id,
            author_id=author_id,
            title="A Chat",
            llm_server_id=server_id,
            model_name="gpt-x",
        )
    )


async def _seed_entry(
    book_id: int,
    author_id: int,
    kind: CodexKind = CodexKind.character,
    *,
    name: str | None = "Halden",
    body: str = "the original body",
    archived: bool = False,
) -> CodexEntry:
    return await codex_entries.create(
        CodexEntry(
            book_id=book_id,
            kind=kind,
            name=name,
            body=body,
            archived=archived,
            author_id=author_id,
        )
    )


async def _select_write_tool(mode_key: str = "edit-character") -> None:
    """Give the running mode the `mode_tool` row that unlocks the write tool."""
    await assistant_modes.seed_default_modes()
    await mode_tools.create(
        ModeTool(mode_key=mode_key, tool_name="write_codex_draft")
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


async def _table_snapshot(book_id: int, entry_ids: list[int]) -> dict:
    """Every row of `codex_entries` / `codex_entry_versions`, field by field."""
    entries = await codex_entries.list_by_book(book_id, include_archived=True)
    versions = []
    for entry_id in entry_ids:
        versions.extend(await codex_entry_versions.list_by_entry(entry_id))
    return {
        "entries": [row.model_dump() for row in entries],
        "versions": [row.model_dump() for row in versions],
    }


# ---------------------------------------------------------------------------
# DoD-2 — the frame reaches the HTTP stream, interleaved with `delta`
# ---------------------------------------------------------------------------


# DoD-2 (context.md -> shared-canvas design point 2): the frame reaches the HTTP
# stream serialized as `event: canvas` carrying the CanvasFrame model's JSON
# payload, interleaved with the turn's ordinary `delta` frames -- through the
# route's existing generic serializer, with no change to routes/chats.py.
async def test_canvas_frame_reaches_the_stream_between_deltas__DoD2(
    http_client, monkeypatch
):
    monkeypatch.setenv("CANVAS_ROUTE_KEY", "resolved-secret")
    author, token = await _seed_author("canvas_author")
    book = await _seed_private_book(author.id)
    server = await _seed_server(api_key="$CANVAS_ROUTE_KEY")
    chat = await _seed_chat(book.id, author.id, server.id)
    entry = await _seed_entry(book.id, author.id)
    await _select_write_tool("edit-character")

    fake = _ToolInvokingClient()
    _install_client(monkeypatch, fake)

    resp = await http_client.post(
        _turn_url(book.id, chat.id),
        headers=_auth_header(token),
        json={
            "prompt": "draft Halden's body",
            "subject_kind": "codex-entry",
            "subject_id": str(entry.id),
        },
    )

    assert resp.status_code == 200, resp.text
    assert "text/event-stream" in resp.headers.get("content-type", "")

    # The tool really was offered and really was invoked -- otherwise the rest of
    # this test would pass against a turn that never reached the tool.
    assert "write_codex_draft" in fake.tool_definition_names
    assert fake.tool_invoked is True

    # The raw wire carries the event name the step names.
    assert "event: canvas" in resp.text

    frames = _parse_sse(resp.text)
    events = [event for event, _ in frames]

    assert events.count("canvas") == 1
    assert events[-1] == "done"
    assert "error" not in events

    # The payload is the CanvasFrame model's JSON.
    canvas_data = [d for e, d in frames if e == "canvas"][0]
    payload = json.loads(canvas_data)
    assert set(payload) == {"subject_kind", "subject_id", "field", "text"}
    assert payload["subject_kind"] == "codex-entry"
    assert payload["subject_id"] == str(entry.id)
    assert payload["field"] == "body"
    assert payload["text"] == DRAFT

    canvas = CanvasFrame.model_validate_json(canvas_data)
    assert canvas.subject_id == str(entry.id)
    assert canvas.text == DRAFT

    # Interleaved with the turn's ordinary prose: a `delta` before it and a
    # `delta` after it, on the one stream.
    canvas_index = events.index("canvas")
    assert "delta" in events[:canvas_index]
    assert "delta" in events[canvas_index + 1:]


# ---------------------------------------------------------------------------
# DoD-3 — nothing is persisted; there is no chat -> codex_entries path at all
# ---------------------------------------------------------------------------


# DoD-3 (US-086.AC-2, US-087.AC-2, US-088.AC-2): after a turn that INVOKED the
# tool, `codex_entries` and `codex_entry_versions` are byte-for-byte unchanged --
# the draft is a proposal on the canvas, never a write. The invocation is
# asserted (via the emitted frame and the tool's own return) so the clause cannot
# pass against a turn that never reached the tool.
async def test_turn_persists_nothing_to_the_codex_tables__DoD3_US086_AC2(
    http_client, monkeypatch
):
    monkeypatch.setenv("CANVAS_ROUTE_KEY2", "resolved-secret")
    author, token = await _seed_author("nopersist_author")
    book = await _seed_private_book(author.id)
    server = await _seed_server(api_key="$CANVAS_ROUTE_KEY2")
    chat = await _seed_chat(book.id, author.id, server.id)
    entry = await _seed_entry(book.id, author.id, body="the original body")
    sibling = await _seed_entry(
        book.id, author.id, CodexKind.location, name="Northgate", body="a cold keep"
    )
    await _select_write_tool("edit-character")

    before = await _table_snapshot(book.id, [entry.id, sibling.id])

    fake = _ToolInvokingClient()
    _install_client(monkeypatch, fake)

    resp = await http_client.post(
        _turn_url(book.id, chat.id),
        headers=_auth_header(token),
        json={
            "prompt": "draft Halden's body",
            "subject_kind": "codex-entry",
            "subject_id": str(entry.id),
        },
    )
    assert resp.status_code == 200, resp.text

    # The tool was genuinely invoked and answered the model.
    assert fake.tool_invoked is True
    assert isinstance(fake.tool_result, str)
    assert fake.tool_result.strip() != ""
    events = [event for event, _ in _parse_sse(resp.text)]
    assert events.count("canvas") == 1

    after = await _table_snapshot(book.id, [entry.id, sibling.id])

    # Byte-for-byte unchanged -- no update, no new row, no version row.
    assert after == before
    assert after["versions"] == []

    # And the entry itself still reads exactly as it was seeded.
    reloaded = await codex_entries.get_by_id(entry.id)
    assert reloaded.body == "the original body"
    assert reloaded.name == "Halden"

    # The chat side of the turn did persist, so the turn was a real one.
    stored = await chat_messages.list_by_chat_ordered(chat.id)
    assert [m.content for m in stored if m.role == "user"] == ["draft Halden's body"]
