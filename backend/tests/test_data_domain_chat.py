"""Tests for the Chat + ChatMessage tables (feature 008, step 009 — final step).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 009):
    class Chat(SQLModel, table=True) __tablename__="chats";
        id: int (snowflake PK), book_id: int (FK books.id),
        author_id: int (FK users.id), title: str (required),
        archived: bool = False, created_at: datetime | None,
        modified_at: datetime | None
    class ChatMessage(SQLModel, table=True) __tablename__="chat_messages";
        id: int (snowflake PK), chat_id: int (FK chats.id),
        role: str (required — FREE STRING, no enum), content: str (required),
        position: int (required non-null ordinal), created_at: datetime | None
                                                        both in app.models.chat
    async def create(row: Chat) -> Chat                   in app.db.chats
    async def get_by_id(chat_id: int) -> Chat | None      in app.db.chats
    async def list_by_book(book_id: int) -> list[Chat]    in app.db.chats
    async def create(row: ChatMessage) -> ChatMessage     in app.db.chat_messages
    async def get_by_id(message_id: int) -> ChatMessage | None
                                                          in app.db.chat_messages
    async def list_by_chat(chat_id: int) -> list[ChatMessage]
                                                          in app.db.chat_messages
    def _chat_to_dict / _dict_to_chat                     in app.services.db_import_export
    def _chat_message_to_dict / _dict_to_chat_message     in app.services.db_import_export
    TABLE_REGISTRY: ("chats", ...) then ("chat_messages", ...) — the FINAL two
        entries, after `flags`                            in app.services.db_import_export
    build_consistency_report() -> report with .tables entries each carrying
        .name / .status                                   in app.services.db_admin

Expected values come from the step spec (009.chat.md DoD + 009.context.md +
context.md), never from implementation internals:
    - Chat codec emits `id`/`book_id`/`author_id` as strings parsed back to the
      same ints; `title` is preserved; the `archived` bool round-trips in BOTH
      the True and False shapes; isoformat timestamps (set and None) survive
      (DoD-1);
    - ChatMessage codec emits `id`/`chat_id` as strings parsed back to the same
      ints; `role` (a free string) and `content` are preserved; `position` is a
      plain int that round-trips as-is; isoformat `created_at` (set and None)
      survives (DoD-2);
    - db round-trip: for BOTH tables create -> get_by_id returns an equal row;
      list_by_book returns exactly a book's chats and list_by_chat returns
      exactly a chat's messages (two parents inserted per table) (DoD-3);
    - the COMPLETE TABLE_REGISTRY tablename sequence equals the full 18-entry
      canonical order EXACTLY — order preserved, no duplicates, no extras — the
      final FK-order guard for the whole feature (DoD-4);
    - after init_db(), `chats` and `chat_messages` exist in SQLModel.metadata and
      the FEAT-005 consistency report is clean (DoD-5).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine with the registered tables created.
Pure-codec tests (DoD-1, DoD-2) and the registry test (DoD-4) need no DB.
SQLite does NOT enforce FKs by default, so rows need no parent book/chat row.
"""

from datetime import datetime

import pytest
from sqlmodel import SQLModel

from app.db import chat_messages, chats
from app.db.engine import DbConfig
from app.models.chat import Chat, ChatMessage
from app.models.schemas.chats import ChatSamplingParams
from app.services import db_admin
from app.services.db_import_export import (
    TABLE_REGISTRY,
    _chat_message_to_dict,
    _chat_to_dict,
    _dict_to_chat,
    _dict_to_chat_message,
)

# The FULL canonical FK order (context.md -> "The canonical TABLE_REGISTRY
# order" / 009.context.md -> "Registry position"). Step 009 is the final step,
# so once it lands the live registry must equal this list EXACTLY (DoD-4).
FULL_CANONICAL_ORDER = [
    "users",
    "llm_servers",
    "assistant_modes",
    "sub_agents",
    "mode_tools",
    "subagent_tools",
    "mode_subagents",
    "books",
    "book_members",
    "book_author_prompts",
    "chapter_author_prompts",
    "chapters",
    "chapter_changes",
    "chapter_text_revisions",
    "chapter_note_changesets",
    "codex_entries",
    "codex_entry_versions",
    "flags",
    "chats",
    "chat_messages",
]


# ---------------------------------------------------------------------------
# DoD-1 — Chat codec round-trip
# ---------------------------------------------------------------------------


# DoD-1: a fully-populated chat with archived=False round-trips.
# `id`/`book_id`/`author_id` emit as strings and parse back to the same ints;
# `title` survives; the `archived` bool (False here) round-trips; the isoformat
# timestamps are preserved.
def test_chat_codec_round_trips_active_shape__DoD1():
    created_at = datetime(2026, 7, 25, 9, 0, 0)
    modified_at = datetime(2026, 7, 25, 9, 30, 0)
    chat = Chat(
        id=111222333,
        book_id=444555666,
        author_id=777888999,
        title="Planning the villain arc",
        archived=False,
        created_at=created_at,
        modified_at=modified_at,
    )

    data = _chat_to_dict(chat)

    # ids emitted as strings.
    assert data["id"] == "111222333"
    assert isinstance(data["id"], str)
    assert data["book_id"] == "444555666"
    assert isinstance(data["book_id"], str)
    assert data["author_id"] == "777888999"
    assert isinstance(data["author_id"], str)
    # title passes through.
    assert data["title"] == "Planning the villain arc"
    # archived bool (False) preserved.
    assert data["archived"] is False
    # timestamps via isoformat strings.
    assert data["created_at"] == created_at.isoformat()
    assert data["modified_at"] == modified_at.isoformat()

    restored = _dict_to_chat(data)

    # ids parse back to the same ints.
    assert restored.id == 111222333
    assert isinstance(restored.id, int)
    assert restored.book_id == 444555666
    assert isinstance(restored.book_id, int)
    assert restored.author_id == 777888999
    assert isinstance(restored.author_id, int)
    assert restored.title == "Planning the villain arc"
    assert restored.archived is False
    assert restored.created_at == created_at
    assert restored.modified_at == modified_at


# DoD-1: an archived chat (archived=True) with None timestamps round-trips.
# The `archived` True shape and the None-timestamp shape are both covered here.
def test_chat_codec_round_trips_archived_shape__DoD1():
    chat = Chat(
        id=222333444,
        book_id=555666777,
        author_id=888999000,
        title="Old brainstorm",
        archived=True,
        created_at=None,
        modified_at=None,
    )

    data = _chat_to_dict(chat)

    # archived bool (True) preserved.
    assert data["archived"] is True
    # None timestamps emitted as None.
    assert data["created_at"] is None
    assert data["modified_at"] is None

    restored = _dict_to_chat(data)

    assert restored.id == 222333444
    assert restored.book_id == 555666777
    assert restored.author_id == 888999000
    assert restored.title == "Old brainstorm"
    assert restored.archived is True
    assert restored.created_at is None
    assert restored.modified_at is None


# ---------------------------------------------------------------------------
# DoD-2 — ChatMessage codec round-trip
# ---------------------------------------------------------------------------


# DoD-2: a populated chat message round-trips. `id`/`chat_id` emit as strings
# and parse back to the same ints; `role` (a free string) and `content` survive;
# `position` is a plain int that round-trips as-is; isoformat `created_at`
# survives (the single timestamp — there is no `modified_at`).
def test_chat_message_codec_round_trips_populated_shape__DoD2():
    created_at = datetime(2026, 7, 25, 10, 15, 0)
    message = ChatMessage(
        id=333444555,
        chat_id=666777888,
        role="assistant",
        content="Here is a draft of the scene.",
        position=5,
        created_at=created_at,
    )

    data = _chat_message_to_dict(message)

    # ids emitted as strings.
    assert data["id"] == "333444555"
    assert isinstance(data["id"], str)
    assert data["chat_id"] == "666777888"
    assert isinstance(data["chat_id"], str)
    # role (free string) + content pass through.
    assert data["role"] == "assistant"
    assert data["content"] == "Here is a draft of the scene."
    # position is a plain int, emitted as-is.
    assert data["position"] == 5
    assert isinstance(data["position"], int)
    # single timestamp via isoformat.
    assert data["created_at"] == created_at.isoformat()

    restored = _dict_to_chat_message(data)

    # ids parse back to the same ints.
    assert restored.id == 333444555
    assert isinstance(restored.id, int)
    assert restored.chat_id == 666777888
    assert isinstance(restored.chat_id, int)
    assert restored.role == "assistant"
    assert restored.content == "Here is a draft of the scene."
    # position round-trips as a plain int.
    assert restored.position == 5
    assert isinstance(restored.position, int)
    assert restored.created_at == created_at


# DoD-2: `role` is a FREE STRING (no enum) — a range of role strings from the
# spec ("user", "assistant") and arbitrary free values round-trip verbatim.
@pytest.mark.parametrize("role", ["user", "assistant", "system", "tool"])
def test_chat_message_role_is_free_string__DoD2(role: str):
    message = ChatMessage(
        id=444555666,
        chat_id=777888999,
        role=role,
        content="body",
        position=0,
    )

    data = _chat_message_to_dict(message)
    # role emitted verbatim (no enum coercion).
    assert data["role"] == role

    restored = _dict_to_chat_message(data)
    assert restored.role == role


# DoD-2: `position` is a plain int ordinal — the boundary value 0 and other
# ordinals round-trip as-is (not stringified, not enum-coerced). None
# `created_at` (the single timestamp) also round-trips as None here.
@pytest.mark.parametrize("position", [0, 1, 5])
def test_chat_message_position_round_trips_int__DoD2(position: int):
    message = ChatMessage(
        id=555666777,
        chat_id=888999000,
        role="user",
        content="body",
        position=position,
        created_at=None,
    )

    data = _chat_message_to_dict(message)
    # position emitted as a plain int.
    assert data["position"] == position
    assert isinstance(data["position"], int)
    # None timestamp emitted as None.
    assert data["created_at"] is None

    restored = _dict_to_chat_message(data)
    assert restored.position == position
    assert isinstance(restored.position, int)
    assert restored.created_at is None


# ---------------------------------------------------------------------------
# DoD-3 — DB round-trip (create -> get_by_id + parent-scoped list filters)
# ---------------------------------------------------------------------------


# DoD-3: chats.create(row) then get_by_id(row.id) returns an equal row. Required
# non-null fields (book_id, author_id, title) are provided; archived defaults to
# False; the snowflake PK is populated on create.
async def test_chats_db_round_trip__DoD3(db: DbConfig):
    row = Chat(
        book_id=42,
        author_id=99,
        title="Persisted Chat",
    )

    created = await chats.create(row)
    # Snowflake PK populated on the created row.
    assert created.id is not None

    fetched = await chats.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.book_id == 42
    assert fetched.author_id == 99
    assert fetched.title == "Persisted Chat"
    # archived defaults to False.
    assert fetched.archived is False


# DoD-3: chats.list_by_book(book_id) returns exactly that book's chats. Chats are
# inserted for two different book_ids and the filter selects only the matching
# book's rows.
async def test_chats_list_by_book_filters__DoD3(db: DbConfig):
    chat_a = Chat(book_id=10, author_id=1, title="A0")
    chat_b = Chat(book_id=10, author_id=1, title="A1")
    chat_other = Chat(book_id=20, author_id=2, title="B0")

    await chats.create(chat_a)
    await chats.create(chat_b)
    await chats.create(chat_other)

    listed = await chats.list_by_book(10)

    # Exactly book 10's chats (both, and only those).
    assert {c.book_id for c in listed} == {10}
    assert {c.title for c in listed} == {"A0", "A1"}
    assert len(listed) == 2


# DoD-3: chat_messages.create(row) then get_by_id(row.id) returns an equal row.
# Required non-null fields (chat_id, role, content, position) are provided; the
# snowflake PK is populated on create.
async def test_chat_messages_db_round_trip__DoD3(db: DbConfig):
    row = ChatMessage(
        chat_id=7,
        role="user",
        content="Persisted message",
        position=0,
    )

    created = await chat_messages.create(row)
    assert created.id is not None

    fetched = await chat_messages.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.chat_id == 7
    assert fetched.role == "user"
    assert fetched.content == "Persisted message"
    assert fetched.position == 0


# DoD-3: chat_messages.list_by_chat(chat_id) returns exactly that chat's
# messages. Messages are inserted for two different chat_ids and the filter
# selects only the matching chat's rows.
async def test_chat_messages_list_by_chat_filters__DoD3(db: DbConfig):
    msg_a = ChatMessage(chat_id=100, role="user", content="q1", position=0)
    msg_b = ChatMessage(chat_id=100, role="assistant", content="a1", position=1)
    msg_other = ChatMessage(chat_id=200, role="user", content="q2", position=0)

    await chat_messages.create(msg_a)
    await chat_messages.create(msg_b)
    await chat_messages.create(msg_other)

    listed = await chat_messages.list_by_chat(100)

    # Exactly chat 100's messages (both, and only those).
    assert {m.chat_id for m in listed} == {100}
    assert {m.content for m in listed} == {"q1", "a1"}
    assert {m.position for m in listed} == {0, 1}
    assert len(listed) == 2


# ---------------------------------------------------------------------------
# DoD-4 — FULL TABLE_REGISTRY equality (the final FK-order guard)
# ---------------------------------------------------------------------------


# DoD-4: this is the final step, so the COMPLETE TABLE_REGISTRY tablename
# sequence must equal the full canonical order EXACTLY — order preserved, with
# NO duplicates and NO extras.
def test_full_table_registry_equals_canonical_order__DoD4():
    labels = [entry[0] for entry in TABLE_REGISTRY]

    # Exact, order-sensitive equality with the full canonical order.
    assert labels == FULL_CANONICAL_ORDER

    # No duplicate tablenames.
    assert len(set(labels)) == len(labels)

    # The two final tuples bind the correct model classes.
    by_label = {entry[0]: entry for entry in TABLE_REGISTRY}
    assert by_label["chats"][1] is Chat
    assert by_label["chat_messages"][1] is ChatMessage


# ---------------------------------------------------------------------------
# DoD-5 — schema present + drift-clean consistency report
# ---------------------------------------------------------------------------


# DoD-5: after init_db() (the `db` fixture), `chats` and `chat_messages` exist in
# SQLModel.metadata and the FEAT-005 consistency report is clean (every table
# entry has status "ok").
async def test_schema_present_and_drift_clean__DoD5(db: DbConfig):
    tables = SQLModel.metadata.tables
    assert "chats" in tables
    assert "chat_messages" in tables

    report = await db_admin.build_consistency_report()
    by_name = {entry.name: entry for entry in report.tables}

    # Both new tables are reported and clean.
    assert by_name["chats"].status == "ok"
    assert by_name["chat_messages"].status == "ok"

    # A freshly-created DB matches metadata: no table drifts.
    for entry in report.tables:
        assert entry.status == "ok", f"table {entry.name!r} not clean: {entry.status}"


# ---------------------------------------------------------------------------
# DoD-10 (feature 011, step 001) — import/export round-trips the new columns
# and the field-set pins include the new fields; registry order is unchanged.
# ---------------------------------------------------------------------------

# The frozen full column sets of both tables (status.md -> Skeleton -> Step 001),
# amended to include the columns this step adds: the Chat model pair
# (`llm_server_id`, `model_name`) + `sampling_params`, and `ChatMessage.reasoning`.
CHAT_FIELDS = {
    "id",
    "book_id",
    "author_id",
    "title",
    "llm_server_id",
    "model_name",
    "sampling_params",
    "archived",
    "created_at",
    "modified_at",
}
CHAT_MESSAGE_FIELDS = {
    "id",
    "chat_id",
    "role",
    "content",
    "reasoning",
    "position",
    "created_at",
}


# DoD-10: a chat carrying a model pair and non-default sampling survives
# export -> import unchanged. `llm_server_id` emits as a string (or null) and
# parses back to the same int; `model_name` survives; the sampling JSON round-trips
# to the same parsed ChatSamplingParams.
def test_chat_codec_round_trips_model_pair_and_sampling__DoD10():
    params = ChatSamplingParams(temperature=0.15, top_k=7, max_tokens=512, seed=99)
    chat = Chat(
        id=123123123,
        book_id=456456456,
        author_id=789789789,
        title="Configured chat",
        llm_server_id=555000111,
        model_name="my-model-v1",
        sampling_params=params.model_dump_json(),
        archived=False,
    )

    data = _chat_to_dict(chat)

    # Model pair: server id emitted as a string, model name verbatim.
    assert data["llm_server_id"] == "555000111"
    assert data["model_name"] == "my-model-v1"
    # Sampling column is carried in the export dict.
    assert "sampling_params" in data

    restored = _dict_to_chat(data)

    assert restored.llm_server_id == 555000111
    assert isinstance(restored.llm_server_id, int)
    assert restored.model_name == "my-model-v1"
    # Sampling round-trips to the same parsed object.
    assert ChatSamplingParams.model_validate_json(restored.sampling_params) == params


# DoD-10: a null model pair round-trips as null (server id emitted as None).
def test_chat_codec_round_trips_null_model_pair__DoD10():
    chat = Chat(
        id=222222222,
        book_id=333333333,
        author_id=444444444,
        title="Unconfigured chat",
        llm_server_id=None,
        model_name=None,
    )

    data = _chat_to_dict(chat)
    assert data["llm_server_id"] is None
    assert data["model_name"] is None

    restored = _dict_to_chat(data)
    assert restored.llm_server_id is None
    assert restored.model_name is None


# DoD-10: an assistant message with `reasoning` survives export -> import
# unchanged, and a None reasoning round-trips as None.
def test_chat_message_codec_round_trips_reasoning__DoD10():
    with_reasoning = ChatMessage(
        id=101010101,
        chat_id=202020202,
        role="assistant",
        content="The answer is 42.",
        reasoning="First I considered the question, then computed.",
        position=3,
    )

    data = _chat_message_to_dict(with_reasoning)
    assert data["reasoning"] == "First I considered the question, then computed."
    restored = _dict_to_chat_message(data)
    assert restored.reasoning == "First I considered the question, then computed."

    # A user message with no reasoning.
    without = ChatMessage(
        id=303030303,
        chat_id=202020202,
        role="user",
        content="What is the answer?",
        reasoning=None,
        position=2,
    )
    data2 = _chat_message_to_dict(without)
    assert data2["reasoning"] is None
    restored2 = _dict_to_chat_message(data2)
    assert restored2.reasoning is None


# DoD-10: the field-set pins for both tables include the new columns exactly —
# no missing, no extra — so the codecs and DTOs cannot silently drop a column.
def test_chat_and_message_field_sets_pinned__DoD10():
    assert set(Chat.model_fields) == CHAT_FIELDS
    assert set(ChatMessage.model_fields) == CHAT_MESSAGE_FIELDS


# The registry as feature 011 step 001 knew it. That step added COLUMNS, not a
# table, so its guard below is scoped to the tables that existed when it ran; a
# later feature legitimately inserting an entry of its own (feature 021 adds
# `book_author_prompts`) does not falsify what DoD-10 verifies.
REGISTRY_AS_OF_FEATURE_011 = [
    name for name in FULL_CANONICAL_ORDER if name != "book_author_prompts"
]


# DoD-10: no table is added by this step — the chat domain's registry footprint
# is still exactly one `chats` entry followed by one `chat_messages` entry, and
# the order of the tables that existed when this step ran is unchanged.
def test_registry_order_unchanged_no_table_added__DoD10():
    labels = [entry[0] for entry in TABLE_REGISTRY]

    # This step introduced no chat-domain table: still one entry each, adjacent.
    assert labels.count("chats") == 1
    assert labels.count("chat_messages") == 1
    assert labels.index("chat_messages") == labels.index("chats") + 1

    # The order of the tables this step knew about is unchanged.
    known_names = set(REGISTRY_AS_OF_FEATURE_011)
    assert [name for name in labels if name in known_names] == REGISTRY_AS_OF_FEATURE_011
