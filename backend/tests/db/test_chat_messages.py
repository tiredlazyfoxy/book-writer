"""Tests for the new session-free db/chat_messages primitives (feature 011, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001), in
`app.db.chat_messages` (existing `create`/`get_by_id`/`list_by_chat` unchanged):
    async def list_by_chat_ordered(chat_id: int) -> list[ChatMessage]
        -- `position` ascending
    async def next_position(chat_id: int) -> int
        -- `0` for an empty chat, else `max(position) + 1`

Expected values come from the step spec (001.chat-crud-model-sampling.md DoD-4 +
001.context.md), never from implementation internals:
    - a chat's messages read back ordered by `position` ascending regardless of
      insertion order, and the ordered read is scoped to the chat (DoD-4);
    - next-position allocation is `0` on an empty chat and `max(position) + 1`
      otherwise (DoD-4).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. SQLite does not enforce FKs by default,
so messages need no parent chat row.
"""

from app.db import chat_messages
from app.db.engine import DbConfig
from app.models.chat import ChatMessage


# DoD-4 (UC-081, US-095.AC-2): list_by_chat_ordered returns a chat's messages by
# `position` ascending even when they were inserted out of order.
async def test_list_by_chat_ordered_sorts_by_position__DoD4_UC081(db: DbConfig):
    chat_id = 5001
    # Insert deliberately out of position order.
    await chat_messages.create(
        ChatMessage(chat_id=chat_id, role="assistant", content="third", position=2)
    )
    await chat_messages.create(
        ChatMessage(chat_id=chat_id, role="user", content="first", position=0)
    )
    await chat_messages.create(
        ChatMessage(chat_id=chat_id, role="assistant", content="second", position=1)
    )

    listed = await chat_messages.list_by_chat_ordered(chat_id)

    # Positions ascending, and the accompanying content follows that order.
    assert [m.position for m in listed] == [0, 1, 2]
    assert [m.content for m in listed] == ["first", "second", "third"]


# DoD-4: the ordered read is scoped to the chat — another chat's messages never
# leak into the result.
async def test_list_by_chat_ordered_scoped_to_chat__DoD4(db: DbConfig):
    await chat_messages.create(
        ChatMessage(chat_id=6001, role="user", content="mine-0", position=0)
    )
    await chat_messages.create(
        ChatMessage(chat_id=6001, role="assistant", content="mine-1", position=1)
    )
    await chat_messages.create(
        ChatMessage(chat_id=6002, role="user", content="other", position=0)
    )

    listed = await chat_messages.list_by_chat_ordered(6001)

    assert {m.chat_id for m in listed} == {6001}
    assert [m.content for m in listed] == ["mine-0", "mine-1"]


# DoD-4: next_position returns 0 for an empty chat.
async def test_next_position_zero_for_empty_chat__DoD4(db: DbConfig):
    assert await chat_messages.next_position(7001) == 0


# DoD-4: next_position returns max(position) + 1 for a non-empty chat -- proven
# with contiguous positions {0,1,2} -> 3 and with a lone message at 7 -> 8 (so it
# is max+1, not a count).
async def test_next_position_is_max_plus_one__DoD4_US095_AC2(db: DbConfig):
    for pos in (0, 1, 2):
        await chat_messages.create(
            ChatMessage(chat_id=7002, role="user", content=f"m{pos}", position=pos)
        )
    assert await chat_messages.next_position(7002) == 3

    # A single message at position 7 -> next is 8 (max+1, not count).
    await chat_messages.create(
        ChatMessage(chat_id=7003, role="assistant", content="lone", position=7)
    )
    assert await chat_messages.next_position(7003) == 8
