"""Side-chat columns and the four new db/chat_messages primitives (feature 027, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001):
    app.models.chat:
        Chat.active_side_chat_id: int | None = None
        ChatMessage.side_chat_id: int | None = None
    app.db.engine:
        ADDITIVE_COLUMNS  -- gains ("chat_messages", "side_chat_id") and
                             ("chats", "active_side_chat_id")
    app.db.chat_messages:
        async def list_transcript(chat_id: int, active_side_chat_id: int | None) -> list[ChatMessage]
        async def side_chat_exists(chat_id: int, side_chat_id: int) -> bool
        async def clear_side_chat(chat_id: int, side_chat_id: int) -> int
        async def delete_by_side_chat(chat_id: int, side_chat_id: int) -> int
    (reused, unchanged) chat_messages.create / get_by_id / list_by_chat_ordered /
    next_position, chats.create / get_by_id

Expected values come from the SPEC ONLY -- `001.side-chat-columns.md` DoD-1..DoD-8 and
`context.md` -> D-A / D-D:
    - both columns default to None and read back the int they were given (DoD-1);
    - the additive seam lists both columns (DoD-2);
    - list_transcript(chat_id, sid) = main-line rows + rows carrying sid, position
      order, other side chats and other chats excluded (DoD-3); with None it is
      main-line rows only (DoD-4);
    - side_chat_exists answers the row half of D-A's existence rule, scoped to the
      chat (DoD-5);
    - clear_side_chat nulls exactly the chat's rows carrying sid, returns their
      count, touches nothing else (DoD-6);
    - delete_by_side_chat removes exactly those rows, returns their count, leaves
      survivors' positions alone and next_position stays max+1 (DoD-7);
    - both mutators return 0 and change nothing when no row carries the id (DoD-8).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. SQLite does not enforce FKs by default,
so messages are seeded with raw integer chat ids and need no parent chat row.
"""

from app.db import chat_messages, chats
from app.db.engine import ADDITIVE_COLUMNS, DbConfig
from app.models.chat import Chat, ChatMessage


async def _seed(
    chat_id: int,
    position: int,
    side_chat_id: int | None,
    *,
    role: str = "user",
    content: str | None = None,
) -> ChatMessage:
    return await chat_messages.create(
        ChatMessage(
            chat_id=chat_id,
            role=role,
            content=content if content is not None else f"c{chat_id}-p{position}",
            position=position,
            side_chat_id=side_chat_id,
        )
    )


def _snapshot(rows: list[ChatMessage]) -> list[tuple[int, int, int, str, str, int | None]]:
    """A comparable (id, chat_id, position, role, content, side_chat_id) view of rows."""
    return [
        (m.id, m.chat_id, m.position, m.role, m.content, m.side_chat_id) for m in rows
    ]


# ---------------------------------------------------------------------------
# DoD-1 -- the two nullable columns persist and read back
# ---------------------------------------------------------------------------


# DoD-1 (D-A): a ChatMessage created without side_chat_id and a Chat created
# without active_side_chat_id persist and read back with None in both.
async def test_columns_default_to_none__DoD1(db: DbConfig):
    chat = await chats.create(
        Chat(book_id=1, author_id=1, title="Draft", archived=False)
    )
    message = await chat_messages.create(
        ChatMessage(chat_id=chat.id, role="user", content="hi", position=0)
    )

    fetched_chat = await chats.get_by_id(chat.id)
    fetched_message = await chat_messages.get_by_id(message.id)

    assert fetched_chat is not None
    assert fetched_chat.active_side_chat_id is None
    assert fetched_message is not None
    assert fetched_message.side_chat_id is None


# DoD-1 (D-A): a ChatMessage created with a side_chat_id reads it back as the
# same int (a snowflake-sized value, stored as int like every other id).
async def test_side_chat_id_round_trips_as_int__DoD1(db: DbConfig):
    sid = 7331987654321001
    message = await chat_messages.create(
        ChatMessage(chat_id=7001, role="user", content="aside", position=0, side_chat_id=sid)
    )

    fetched = await chat_messages.get_by_id(message.id)

    assert fetched is not None
    assert fetched.side_chat_id == sid
    assert isinstance(fetched.side_chat_id, int)


# DoD-1 (D-A): a Chat created with active_side_chat_id persists it as the same int.
async def test_active_side_chat_id_round_trips_as_int__DoD1(db: DbConfig):
    sid = 7331987654321002
    chat = await chats.create(
        Chat(book_id=1, author_id=1, title="Aside", active_side_chat_id=sid)
    )

    fetched = await chats.get_by_id(chat.id)

    assert fetched is not None
    assert fetched.active_side_chat_id == sid
    assert isinstance(fetched.active_side_chat_id, int)


# ---------------------------------------------------------------------------
# DoD-2 -- the additive-column seam
# ---------------------------------------------------------------------------


# DoD-2 (backend/persistence.md -> "The additive-column seam"): both new
# columns are registered so an existing install gets them via ALTER TABLE.
def test_additive_columns_lists_both_side_chat_columns__DoD2():
    entries = list(ADDITIVE_COLUMNS)
    assert ("chat_messages", "side_chat_id") in entries
    assert ("chats", "active_side_chat_id") in entries


# ---------------------------------------------------------------------------
# DoD-3 / DoD-4 -- list_transcript
# ---------------------------------------------------------------------------


# DoD-3 (UC-115 step 1): list_transcript(chat_id, sid) returns, in position
# order, every main-line row plus every row carrying sid -- and no row carrying a
# different side-chat id, and nothing from another chat.
async def test_list_transcript_with_active_side_chat__DoD3(db: DbConfig):
    chat_id = 7003
    other_chat = 7004
    sid_a = 91
    sid_b = 92
    # Inserted out of position order so ordering is proven, not incidental.
    await _seed(chat_id, 4, sid_a, role="assistant", content="a-reply")
    await _seed(chat_id, 1, None, role="assistant", content="main-1")
    await _seed(chat_id, 3, sid_a, content="a-ask")
    await _seed(chat_id, 0, None, content="main-0")
    await _seed(chat_id, 2, sid_b, content="b-ask")  # a different side chat
    await _seed(chat_id, 5, sid_b, role="assistant", content="b-reply")
    await _seed(chat_id, 6, None, content="main-6")
    # Another chat carrying the very same side-chat id must never appear.
    await _seed(other_chat, 0, sid_a, content="foreign-a")
    await _seed(other_chat, 1, None, content="foreign-main")

    listed = await chat_messages.list_transcript(chat_id, sid_a)

    assert [m.content for m in listed] == ["main-0", "main-1", "a-ask", "a-reply", "main-6"]
    assert [m.position for m in listed] == [0, 1, 3, 4, 6]
    assert {m.chat_id for m in listed} == {chat_id}
    assert all(m.side_chat_id in (None, sid_a) for m in listed)


# DoD-4 (UC-115 step 2): list_transcript(chat_id, None) returns main-line rows
# only, in position order, excluding every row that carries any side-chat id.
async def test_list_transcript_main_line_only__DoD4(db: DbConfig):
    chat_id = 7005
    sid_a = 91
    sid_b = 92
    await _seed(chat_id, 3, None, content="main-3")
    await _seed(chat_id, 1, sid_a, content="a-1")
    await _seed(chat_id, 0, None, content="main-0")
    await _seed(chat_id, 2, sid_b, content="b-2")
    await _seed(7006, 0, None, content="foreign-main")

    listed = await chat_messages.list_transcript(chat_id, None)

    assert [m.content for m in listed] == ["main-0", "main-3"]
    assert [m.position for m in listed] == [0, 3]
    assert all(m.side_chat_id is None for m in listed)
    assert {m.chat_id for m in listed} == {chat_id}


# DoD-4 (UC-115 step 2): an empty chat yields an empty transcript for None.
async def test_list_transcript_empty_chat__DoD4(db: DbConfig):
    assert await chat_messages.list_transcript(7007, None) == []


# ---------------------------------------------------------------------------
# DoD-5 -- side_chat_exists
# ---------------------------------------------------------------------------


# DoD-5 (D-A): True when at least one row of the chat carries the id.
async def test_side_chat_exists_true_when_a_row_carries_it__DoD5(db: DbConfig):
    chat_id = 7008
    sid = 91
    await _seed(chat_id, 0, None)
    await _seed(chat_id, 1, sid)

    assert await chat_messages.side_chat_exists(chat_id, sid) is True


# DoD-5 (D-A): False when no row of the chat carries the id -- including when a
# row with that id exists in a DIFFERENT chat.
async def test_side_chat_exists_false_when_no_row_in_this_chat__DoD5(db: DbConfig):
    chat_id = 7009
    other_chat = 7010
    sid = 91
    await _seed(chat_id, 0, None)
    await _seed(chat_id, 1, 92)  # a different side chat in this chat
    await _seed(other_chat, 0, sid)  # the id, but in another chat

    assert await chat_messages.side_chat_exists(chat_id, sid) is False
    # And an entirely empty chat has no side chats at all.
    assert await chat_messages.side_chat_exists(7011, sid) is False


# ---------------------------------------------------------------------------
# DoD-6 / DoD-8 -- clear_side_chat
# ---------------------------------------------------------------------------


# DoD-6 (US-139.AC-1, storage half): clear_side_chat sets side_chat_id to None on
# exactly the rows of that chat carrying sid, returns their count, and leaves
# their position / content / role -- and every other row -- unchanged.
async def test_clear_side_chat_nulls_exactly_the_target_rows__DoD6(db: DbConfig):
    chat_id = 7012
    other_chat = 7013
    sid_a = 91
    sid_b = 92
    m0 = await _seed(chat_id, 0, None, content="main-0")
    a1 = await _seed(chat_id, 1, sid_a, content="a-ask")
    a2 = await _seed(chat_id, 2, sid_a, role="assistant", content="a-reply")
    b3 = await _seed(chat_id, 3, sid_b, content="b-ask")
    m4 = await _seed(chat_id, 4, None, role="assistant", content="main-4")
    fa = await _seed(other_chat, 0, sid_a, content="foreign-a")
    fm = await _seed(other_chat, 1, None, content="foreign-main")

    changed = await chat_messages.clear_side_chat(chat_id, sid_a)

    assert changed == 2

    # The two target rows are now main line, everything else on them intact.
    after = {m.id: m for m in await chat_messages.list_by_chat_ordered(chat_id)}
    assert after[a1.id].side_chat_id is None
    assert after[a2.id].side_chat_id is None
    assert (after[a1.id].position, after[a1.id].role, after[a1.id].content) == (1, "user", "a-ask")
    assert (after[a2.id].position, after[a2.id].role, after[a2.id].content) == (
        2,
        "assistant",
        "a-reply",
    )

    # Main-line rows and the other side chat in this chat are untouched.
    assert (after[m0.id].position, after[m0.id].side_chat_id, after[m0.id].content) == (0, None, "main-0")
    assert (after[m4.id].position, after[m4.id].side_chat_id, after[m4.id].content) == (4, None, "main-4")
    assert (after[b3.id].position, after[b3.id].side_chat_id, after[b3.id].content) == (3, sid_b, "b-ask")
    assert len(after) == 5

    # The other chat -- even the row carrying the same id -- is untouched.
    foreign = {m.id: m for m in await chat_messages.list_by_chat_ordered(other_chat)}
    assert foreign[fa.id].side_chat_id == sid_a
    assert foreign[fm.id].side_chat_id is None
    assert len(foreign) == 2

    # After the inject the side chat no longer exists on the row half.
    assert await chat_messages.side_chat_exists(chat_id, sid_a) is False


# DoD-8 (D-A): clear_side_chat returns 0 and changes nothing when no row of the
# chat carries the id -- even if another chat does.
async def test_clear_side_chat_returns_zero_when_nothing_matches__DoD8(db: DbConfig):
    chat_id = 7014
    other_chat = 7015
    sid = 91
    await _seed(chat_id, 0, None, content="main-0")
    await _seed(chat_id, 1, 92, content="b-1")
    await _seed(other_chat, 0, sid, content="foreign-a")
    before = _snapshot(await chat_messages.list_by_chat_ordered(chat_id))
    before_other = _snapshot(await chat_messages.list_by_chat_ordered(other_chat))

    changed = await chat_messages.clear_side_chat(chat_id, sid)

    assert changed == 0
    assert _snapshot(await chat_messages.list_by_chat_ordered(chat_id)) == before
    assert _snapshot(await chat_messages.list_by_chat_ordered(other_chat)) == before_other


# ---------------------------------------------------------------------------
# DoD-7 / DoD-8 -- delete_by_side_chat
# ---------------------------------------------------------------------------


# DoD-7 (US-140.AC-3, storage half): delete_by_side_chat removes exactly the rows
# of that chat carrying sid, returns their count, and leaves every other row
# (main line, other side chats, other chats) present with unchanged position;
# next_position afterwards is still max+1 over the survivors (no renumbering).
async def test_delete_by_side_chat_removes_exactly_the_target_rows__DoD7(db: DbConfig):
    chat_id = 7016
    other_chat = 7017
    sid_a = 91
    sid_b = 92
    m0 = await _seed(chat_id, 0, None, content="main-0")
    a1 = await _seed(chat_id, 1, sid_a, content="a-ask")
    a2 = await _seed(chat_id, 2, sid_a, role="assistant", content="a-reply")
    b3 = await _seed(chat_id, 3, sid_b, content="b-ask")
    m4 = await _seed(chat_id, 4, None, role="assistant", content="main-4")
    a5 = await _seed(chat_id, 5, sid_a, content="a-late")
    fa = await _seed(other_chat, 0, sid_a, content="foreign-a")
    fm = await _seed(other_chat, 1, None, content="foreign-main")

    deleted = await chat_messages.delete_by_side_chat(chat_id, sid_a)

    assert deleted == 3

    # Deleted rows are gone.
    assert await chat_messages.get_by_id(a1.id) is None
    assert await chat_messages.get_by_id(a2.id) is None
    assert await chat_messages.get_by_id(a5.id) is None

    # Survivors keep their ids, positions and side-chat ids -- gaps included.
    survivors = await chat_messages.list_by_chat_ordered(chat_id)
    assert _snapshot(survivors) == [
        (m0.id, chat_id, 0, "user", "main-0", None),
        (b3.id, chat_id, 3, "user", "b-ask", sid_b),
        (m4.id, chat_id, 4, "assistant", "main-4", None),
    ]

    # The other chat -- even the row carrying the same id -- is untouched.
    assert _snapshot(await chat_messages.list_by_chat_ordered(other_chat)) == [
        (fa.id, other_chat, 0, "user", "foreign-a", sid_a),
        (fm.id, other_chat, 1, "user", "foreign-main", None),
    ]

    # No renumbering: next_position is max+1 over the survivors (4 -> 5).
    assert await chat_messages.next_position(chat_id) == 5
    assert await chat_messages.side_chat_exists(chat_id, sid_a) is False


# DoD-7 (US-140.AC-3): deleting the side chat that held the highest positions
# leaves next_position at max+1 over what remains -- the tail moves back.
async def test_delete_by_side_chat_next_position_follows_survivors__DoD7(db: DbConfig):
    chat_id = 7018
    sid = 91
    await _seed(chat_id, 0, None)
    await _seed(chat_id, 1, None)
    await _seed(chat_id, 2, sid)
    await _seed(chat_id, 3, sid)
    assert await chat_messages.next_position(chat_id) == 4

    deleted = await chat_messages.delete_by_side_chat(chat_id, sid)

    assert deleted == 2
    assert [m.position for m in await chat_messages.list_by_chat_ordered(chat_id)] == [0, 1]
    assert await chat_messages.next_position(chat_id) == 2


# DoD-8 (D-A): delete_by_side_chat returns 0 and changes nothing when no row of
# the chat carries the id -- even if another chat does.
async def test_delete_by_side_chat_returns_zero_when_nothing_matches__DoD8(db: DbConfig):
    chat_id = 7019
    other_chat = 7020
    sid = 91
    await _seed(chat_id, 0, None, content="main-0")
    await _seed(chat_id, 1, 92, content="b-1")
    await _seed(other_chat, 0, sid, content="foreign-a")
    before = _snapshot(await chat_messages.list_by_chat_ordered(chat_id))
    before_other = _snapshot(await chat_messages.list_by_chat_ordered(other_chat))

    deleted = await chat_messages.delete_by_side_chat(chat_id, sid)

    assert deleted == 0
    assert _snapshot(await chat_messages.list_by_chat_ordered(chat_id)) == before
    assert _snapshot(await chat_messages.list_by_chat_ordered(other_chat)) == before_other
    assert await chat_messages.next_position(chat_id) == 2
