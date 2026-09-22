"""The side-chat fields in the chat / chat_message JSONL codecs (feature 027, step 001).

Bound to the frozen skeleton (status.md -> Skeleton -> Step 001), in
`app.services.db_import_export` (signatures unchanged, keys added):
    def _chat_to_dict(chat: Chat) -> dict[str, object]
        -- gains key "active_side_chat_id" as str | None on the wire
    def _dict_to_chat(data: dict[str, object]) -> Chat
        -- restores active_side_chat_id via data.get(...), int(...) when present,
           None when the key is absent (legacy archive)
    def _chat_message_to_dict(message: ChatMessage) -> dict[str, object]
        -- gains key "side_chat_id" as str | None on the wire
    def _dict_to_chat_message(data: dict[str, object]) -> ChatMessage
        -- restores side_chat_id the same way

Expected values come from the SPEC ONLY -- `001.side-chat-columns.md` DoD-9 / DoD-10
and `context.md` -> D-A ("export `str(x) if x is not None else None` ... restore via
`data.get(...)` with `int(...)` when present -- so an archive written before this
feature imports as `None`"):
    - the new key is the id's decimal string when set, null when None; the
      `_dict_to_*` twin restores the int (DoD-9);
    - a dict WITHOUT the new key restores with None in the new field and every
      other field intact (DoD-10).

These are direct codec calls -- no database, no fixture needed.
"""

from datetime import datetime

from app.models.chat import Chat, ChatMessage
from app.services.db_import_export import (
    _chat_message_to_dict,
    _chat_to_dict,
    _dict_to_chat,
    _dict_to_chat_message,
)

ACTIVE_SID = 7331987654321001
SIDE_SID = 7331987654321002


def _chat(active_side_chat_id: int | None) -> Chat:
    return Chat(
        id=5001,
        book_id=11,
        author_id=22,
        title="Aside chat",
        llm_server_id=424242,
        model_name="some-model",
        sampling_params='{"temperature": 0.3}',
        archived=False,
        created_at=datetime(2026, 9, 20, 9, 0, 0),
        modified_at=datetime(2026, 9, 20, 10, 0, 0),
        active_side_chat_id=active_side_chat_id,
    )


def _message(side_chat_id: int | None) -> ChatMessage:
    return ChatMessage(
        id=6001,
        chat_id=5001,
        role="assistant",
        content="Håldén keeps the gate.",
        reasoning="checking the codex first",
        position=3,
        created_at=datetime(2026, 9, 20, 9, 30, 0),
        tool_trace=None,
        side_chat_id=side_chat_id,
    )


def _assert_chat_fields_intact(restored: Chat, original: Chat) -> None:
    assert restored.id == original.id
    assert restored.book_id == original.book_id
    assert restored.author_id == original.author_id
    assert restored.title == original.title
    assert restored.llm_server_id == original.llm_server_id
    assert restored.model_name == original.model_name
    assert restored.sampling_params == original.sampling_params
    assert restored.archived == original.archived


def _assert_message_fields_intact(restored: ChatMessage, original: ChatMessage) -> None:
    assert restored.id == original.id
    assert restored.chat_id == original.chat_id
    assert restored.role == original.role
    assert restored.content == original.content
    assert restored.reasoning == original.reasoning
    assert restored.position == original.position
    assert restored.tool_trace == original.tool_trace


# ---------------------------------------------------------------------------
# DoD-9 -- the new keys on the wire, and their restoration
# ---------------------------------------------------------------------------


# DoD-9 (root CLAUDE.md -> DB Import/Export): _chat_to_dict emits
# active_side_chat_id as the id's decimal string when set, and _dict_to_chat
# restores the int.
def test_chat_codec_emits_string_and_restores_int__DoD9():
    original = _chat(ACTIVE_SID)

    data = _chat_to_dict(original)

    assert "active_side_chat_id" in data
    assert data["active_side_chat_id"] == str(ACTIVE_SID)
    assert isinstance(data["active_side_chat_id"], str)

    restored = _dict_to_chat(data)

    assert restored.active_side_chat_id == ACTIVE_SID
    assert isinstance(restored.active_side_chat_id, int)
    _assert_chat_fields_intact(restored, original)


# DoD-9: _chat_to_dict emits active_side_chat_id as null when None, and
# _dict_to_chat restores None (not 0, not "").
def test_chat_codec_emits_null_and_restores_none__DoD9():
    original = _chat(None)

    data = _chat_to_dict(original)

    assert "active_side_chat_id" in data
    assert data["active_side_chat_id"] is None

    restored = _dict_to_chat(data)

    assert restored.active_side_chat_id is None
    _assert_chat_fields_intact(restored, original)


# DoD-9: _chat_message_to_dict emits side_chat_id as the id's decimal string
# when set, and _dict_to_chat_message restores the int.
def test_message_codec_emits_string_and_restores_int__DoD9():
    original = _message(SIDE_SID)

    data = _chat_message_to_dict(original)

    assert "side_chat_id" in data
    assert data["side_chat_id"] == str(SIDE_SID)
    assert isinstance(data["side_chat_id"], str)

    restored = _dict_to_chat_message(data)

    assert restored.side_chat_id == SIDE_SID
    assert isinstance(restored.side_chat_id, int)
    _assert_message_fields_intact(restored, original)


# DoD-9: _chat_message_to_dict emits side_chat_id as null when None, and
# _dict_to_chat_message restores None.
def test_message_codec_emits_null_and_restores_none__DoD9():
    original = _message(None)

    data = _chat_message_to_dict(original)

    assert "side_chat_id" in data
    assert data["side_chat_id"] is None

    restored = _dict_to_chat_message(data)

    assert restored.side_chat_id is None
    _assert_message_fields_intact(restored, original)


# ---------------------------------------------------------------------------
# DoD-10 -- a legacy archive written before this feature
# ---------------------------------------------------------------------------


# DoD-10 (backend/persistence.md -> "A superseded column keeps its codec", read
# forward): a chat dict WITHOUT the active_side_chat_id key -- an archive written
# before this feature -- restores with None and every other field intact.
def test_legacy_chat_dict_without_key_restores_none__DoD10():
    original = _chat(ACTIVE_SID)
    data = _chat_to_dict(original)
    del data["active_side_chat_id"]
    assert "active_side_chat_id" not in data

    restored = _dict_to_chat(data)

    assert restored.active_side_chat_id is None
    _assert_chat_fields_intact(restored, original)


# DoD-10: a message dict WITHOUT the side_chat_id key restores with None and
# every other field intact.
def test_legacy_message_dict_without_key_restores_none__DoD10():
    original = _message(SIDE_SID)
    data = _chat_message_to_dict(original)
    del data["side_chat_id"]
    assert "side_chat_id" not in data

    restored = _dict_to_chat_message(data)

    assert restored.side_chat_id is None
    _assert_message_fields_intact(restored, original)
