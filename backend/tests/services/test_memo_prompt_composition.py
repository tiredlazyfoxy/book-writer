"""Tests for the `MEMOS` prompt layer (feature 026, step 006).

Two halves, both bound to the frozen skeleton (`status.md` -> `## Skeleton` ->
Step 006):

    app.services.prompt_composition:
        def compose_system_prompt(base: str | None = None,
                                  mode: str | None = None,
                                  author: str | None = None,
                                  memos: str | None = None,
                                  chapter: str | None = None) -> str

    app.services.chat_turn:
        def render_memos_section(memos: Sequence[Memo]) -> str | None
        @dataclass(frozen=True) class ComposedTurnPrompt:
            system: str
            memos_section: str | None
        async def compose_turn_system_prompt(context: TurnContext)
                -> ComposedTurnPrompt

plus the step-001 row and reader used only to *seed* and to *call*:

    app.models.memo.Memo(book_id, user_id, body, ordinal, active, archived, ...)
    app.db.memos.create / list_for_author(book_id, user_id,
                                          include_archived=False)

Expected values come from the SPEC ONLY -- `006.memos-prompt-layer.md` ->
Interface intent + Definition of done (DoD-1..DoD-9), `006.context.md`, and
`026/context.md` decisions 1, 7 and 8 -- never from implementation internals.

Key spec facts asserted here:
  - The rendered order is BASE, MODE, AUTHOR, MEMOS, CHAPTER; the section label
    is exactly `MEMOS`, rendered the way the existing labels are.
  - `author` is still the THIRD positional parameter; `memos` is fourth and
    `chapter` fifth.
  - A memo reaches the prompt iff `archived is False AND active is True`
    (`context.md` decision 1 -- context membership is a derived reading rule).
  - Active memos appear in ascending ordinal order -- the author's own order.
  - The renderer renders the bodies IN THE ORDER GIVEN (it never sorts, ranks,
    truncates or budgets), skips a body that is blank after stripping, and
    returns `None` when nothing survives.
  - The turn reads memos for the CHAT'S OWN author and that chat's book, once
    per turn, and renders one section.

What is deliberately NOT asserted, because the spec leaves it to the coder:
the separator between two memo bodies (the only fixed requirement is that two
memos cannot read as one) and any per-memo decoration. Tests therefore assert
presence, count, order and position -- never the exact bytes of a rendered
multi-memo section.

Test approach (`006.context.md` -> "Test seeding"): the composer half is pure,
so it needs no fixture. The turn half exercises the composition path **as a
function** against the `db` fixture's throwaway temp SQLite -- `run_turn` is
never driven, `chat_with_tools` is never called, and **no LLM server is
contacted**. `asyncio_mode = "auto"`, so async tests need no decorator. There is
no shared factory module, so the `_seed_*` helpers are local, copied in idiom
from `tests/services/test_chapter_prompt_composition.py`.
"""

import inspect

import pytest

from app.db import (
    assistant_modes,
    book_author_prompts,
    book_members,
    books,
    chapter_author_prompts,
    chapters,
    chats,
    codex_entries,
    llm_servers,
    memos as memos_db,
    users,
)
from app.db.engine import DbConfig
from app.models.assistant_mode import AssistantMode
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_author_prompt import BookAuthorPrompt
from app.models.book_member import BookMember, MemberRole
from app.models.chapter import Chapter, ChapterState
from app.models.chapter_author_prompt import ChapterAuthorPrompt
from app.models.chat import Chat
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.llm_server import LlmServer
from app.models.memo import Memo
from app.models.user import User, UserRole
from app.services import chat_turn
from app.services.assistant_runtime import ResolvedSubject
from app.services.chat_turn import TurnContext
from app.services.prompt_composition import BASE_SYSTEM_PROMPT, compose_system_prompt

# Sentinels -- chosen so they cannot collide with a section label, a delimiter,
# or any plausible substring of the base prompt or of each other.
MODE_TEXT = "ZZMODEPROMPTZZ"
AUTHOR_TEXT = "ZZAUTHORPROMPTZZ"
CHAPTER_TEXT = "ZZCHAPTERPROMPTZZ"

MEMO_ONE = "ZZMEMOONEZZ"
MEMO_TWO = "ZZMEMOTWOZZ"
MEMO_THREE = "ZZMEMOTHREEZZ"
INACTIVE_MEMO = "ZZINACTIVEMEMOZZ"
ARCHIVED_MEMO = "ZZARCHIVEDMEMOZZ"
OTHER_AUTHOR_MEMO = "ZZOTHERAUTHORMEMOZZ"
OTHER_BOOK_MEMO = "ZZOTHERBOOKMEMOZZ"
CONTROL_MEMO = "ZZCONTROLMEMOZZ"

MODE_KEY = "write-chapter"
CODEX_MODE_KEY = "edit-character"


# ---------------------------------------------------------------------------
# Expected-string builders -- the composer's rendering (`006.context.md` ->
# "`prompt_composition.py` as it stands"): each non-blank layer renders as
# `### <LABEL>\n<text.strip()>`, survivors joined by a blank line.
# ---------------------------------------------------------------------------


def _section(label: str, text: str) -> str:
    return f"### {label}\n{text.strip()}"


def _expected(*sections: str) -> str:
    return "\n\n".join(sections)


BASE_SECTION = _section("BASE", BASE_SYSTEM_PROMPT)


# ---------------------------------------------------------------------------
# Seeding helpers (rows built through the db layer).
# ---------------------------------------------------------------------------


async def _seed_user(username: str) -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(owner_id: int, title: str = "A Book") -> Book:
    return await books.create(
        Book(
            title=title,
            description="d",
            owner_id=owner_id,
            collaboration_mode=CollaborationMode.free,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt="",
            active_notes="",
        )
    )


async def _add_co_author(book_id: int, user_id: int) -> BookMember:
    return await book_members.create(
        BookMember(book_id=book_id, user_id=user_id, role=MemberRole.co_author)
    )


async def _seed_server() -> LlmServer:
    return await llm_servers.create(
        LlmServer(
            name="S",
            backend_type="openai",
            base_url="https://api.example.com/v1",
            api_key="sk-stored",
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


async def _seed_chapter(book_id: int, ordinal: int = 1) -> Chapter:
    return await chapters.create(
        Chapter(
            book_id=book_id,
            ordinal=ordinal,
            title="Chapter One",
            state=ChapterState.open,
            sketch="",
            text="",
            system_prompt="",
        )
    )


async def _seed_entry(book_id: int, author_id: int) -> CodexEntry:
    return await codex_entries.create(
        CodexEntry(
            book_id=book_id,
            kind=CodexKind.character,
            name="Halden",
            body="a codex body",
            archived=False,
            author_id=author_id,
        )
    )


async def _seed_mode(key: str, system_prompt: str) -> AssistantMode:
    return await assistant_modes.create(
        AssistantMode(key=key, system_prompt=system_prompt)
    )


async def _seed_author_prompt(
    book_id: int, user_id: int, text: str
) -> BookAuthorPrompt:
    return await book_author_prompts.create(
        BookAuthorPrompt(book_id=book_id, user_id=user_id, system_prompt=text)
    )


async def _seed_chapter_prompt(
    chapter_id: int, user_id: int, text: str
) -> ChapterAuthorPrompt:
    return await chapter_author_prompts.create(
        ChapterAuthorPrompt(chapter_id=chapter_id, user_id=user_id, system_prompt=text)
    )


async def _seed_memo(
    book_id: int,
    user_id: int,
    body: str,
    ordinal: int,
    *,
    active: bool = True,
    archived: bool = False,
) -> Memo:
    """A memo row written straight through db/memos.py.

    A spec for the prompt path must not depend on the service or route family to
    reach a state; the two flags are seeded directly (026/context.md decision 1 --
    two independent axes, every combination legal).
    """
    return await memos_db.create(
        Memo(
            book_id=book_id,
            user_id=user_id,
            body=body,
            ordinal=ordinal,
            active=active,
            archived=archived,
        )
    )


def _memo(body: str, ordinal: int) -> Memo:
    """An in-memory row for the pure renderer -- never persisted."""
    return Memo(book_id=1, user_id=1, body=body, ordinal=ordinal)


def _context(chat: Chat, server: LlmServer, subject=None) -> TurnContext:
    """The frozen record, built by hand -- no `prepare_turn`, no stream."""
    if subject is None:
        return TurnContext(chat=chat, server=server, resolved_key="resolved-secret")
    return TurnContext(
        chat=chat, server=server, resolved_key="resolved-secret", subject=subject
    )


async def _compose(chat: Chat, server: LlmServer, subject=None):
    return await chat_turn.compose_turn_system_prompt(_context(chat, server, subject))


# ===========================================================================
# The pure renderer -- `chat_turn.render_memos_section`
# ===========================================================================


# DoD-2: the renderer renders the bodies IN THE ORDER GIVEN. The rows are handed
# over with ordinals that DISAGREE with the order given, so a renderer that
# sorted (or ranked, per `context.md` decision 8 -- it may not) would land the
# opposite order and fail here.
def test_renderer_keeps_the_order_it_is_given__DoD2():
    ascending = chat_turn.render_memos_section(
        [_memo(MEMO_ONE, 9), _memo(MEMO_TWO, 5), _memo(MEMO_THREE, 1)]
    )

    assert ascending is not None
    assert (
        ascending.index(MEMO_ONE)
        < ascending.index(MEMO_TWO)
        < ascending.index(MEMO_THREE)
    )

    reversed_ = chat_turn.render_memos_section(
        [_memo(MEMO_THREE, 1), _memo(MEMO_TWO, 5), _memo(MEMO_ONE, 9)]
    )

    assert reversed_ is not None
    assert (
        reversed_.index(MEMO_THREE)
        < reversed_.index(MEMO_TWO)
        < reversed_.index(MEMO_ONE)
    )


# DoD-1: every body handed to the renderer survives into the section, exactly
# once -- nothing is dropped, truncated or budgeted (`context.md` decision 8).
# DoD-1 also fixes the one requirement on the separator: two memos must not read
# as one, so the bodies are not directly adjacent.
def test_renderer_keeps_every_body_and_separates_them__DoD1():
    rendered = chat_turn.render_memos_section(
        [_memo(MEMO_ONE, 1), _memo(MEMO_TWO, 2)]
    )

    assert rendered is not None
    assert rendered.count(MEMO_ONE) == 1
    assert rendered.count(MEMO_TWO) == 1

    between = rendered[rendered.index(MEMO_ONE) + len(MEMO_ONE) : rendered.index(MEMO_TWO)]
    assert between != ""


# DoD-6: a memo whose body is blank after stripping is skipped -- an empty memo
# is a legitimate row (UC-103) and must not contribute a stray separator. The
# section is byte-for-byte what the surviving rows alone render.
def test_renderer_skips_blank_bodies__DoD6():
    with_blanks = chat_turn.render_memos_section(
        [
            _memo("", 1),
            _memo(MEMO_ONE, 2),
            _memo("   \n\t ", 3),
            _memo(MEMO_TWO, 4),
            _memo("  ", 5),
        ]
    )
    survivors_only = chat_turn.render_memos_section(
        [_memo(MEMO_ONE, 2), _memo(MEMO_TWO, 4)]
    )

    assert with_blanks == survivors_only
    assert with_blanks is not None


# DoD-6: `None` is the no-layer value -- returned for an empty sequence and for
# a sequence whose every body is blank after stripping.
@pytest.mark.parametrize(
    "rows",
    [[], [_memo("", 1)], [_memo("   ", 1), _memo("\n\t", 2), _memo("", 3)]],
    ids=["empty", "one_blank", "all_blank"],
)
def test_renderer_returns_none_when_nothing_survives__DoD6(rows):
    assert chat_turn.render_memos_section(rows) is None


# ===========================================================================
# The pure composer -- `prompt_composition.compose_system_prompt`
# ===========================================================================


# DoD-4: the rendered order is BASE, MODE, AUTHOR, MEMOS, CHAPTER -- the memos
# section follows the author layer and precedes the chapter layer, and its label
# is exactly `MEMOS`, rendered the way the existing labels are. Bound to the
# whole string, because a presence-only assertion would pass on a wrong order.
def test_memos_section_renders_fourth_of_five__DoD4():
    result = compose_system_prompt(
        base="B TEXT",
        mode="M TEXT",
        author="A TEXT",
        memos="ME TEXT",
        chapter="C TEXT",
    )

    assert result == (
        "### BASE\nB TEXT\n\n"
        "### MODE\nM TEXT\n\n"
        "### AUTHOR\nA TEXT\n\n"
        "### MEMOS\nME TEXT\n\n"
        "### CHAPTER\nC TEXT"
    )


# DoD-4: the same fact stated as strict ordering, and the label pinned exactly --
# `MEMOS`, not `MEMO`, not `AUTHOR MEMOS`.
def test_memos_label_is_exactly_memos_between_author_and_chapter__DoD4():
    result = compose_system_prompt(
        base="B TEXT",
        mode="M TEXT",
        author="A TEXT",
        memos="ME TEXT",
        chapter="C TEXT",
    )

    assert "### MEMOS\nME TEXT" in result
    assert result.count("### MEMOS") == 1
    assert (
        result.index("### BASE")
        < result.index("### MODE")
        < result.index("### AUTHOR")
        < result.index("### MEMOS")
        < result.index("### CHAPTER")
    )


# DoD-4: the memos layer is stripped before rendering, exactly as every other
# layer is -- surrounding whitespace never leaks into the section.
def test_memos_text_is_stripped_in_its_section__DoD4():
    padded = compose_system_prompt(base="B TEXT", memos="  \n ME TEXT \t ")
    tight = compose_system_prompt(base="B TEXT", memos="ME TEXT")

    assert padded == tight
    assert padded == "### BASE\nB TEXT\n\n### MEMOS\nME TEXT"


# DoD-6 (composer half): the existing skip rule extends to the new layer
# unchanged -- an absent, empty or whitespace-only memos layer contributes no
# section, no separator and no blank block, byte-for-byte identical to omitting
# it. The POSITIVE CONTROL in the same spec distinguishes "renders nothing" from
# "the layer does not exist": a non-blank memos layer DOES change the output.
@pytest.mark.parametrize(
    "memos_value",
    [None, "", "   ", "\t", "\n\t  \n"],
    ids=["none", "empty", "spaces", "tab", "mixed_ws"],
)
def test_blank_memos_layer_contributes_nothing__DoD6(memos_value):
    omitted = compose_system_prompt(base="B TEXT", author="A TEXT", chapter="C TEXT")
    with_blank = compose_system_prompt(
        base="B TEXT", author="A TEXT", memos=memos_value, chapter="C TEXT"
    )

    assert with_blank == omitted
    assert "MEMOS" not in with_blank
    assert with_blank == with_blank.rstrip()

    # Positive control -- the layer exists and does contribute when non-blank.
    populated = compose_system_prompt(
        base="B TEXT", author="A TEXT", memos="ME TEXT", chapter="C TEXT"
    )
    assert populated != omitted
    assert "### MEMOS\nME TEXT" in populated


# DoD-5: `author` is still the THIRD positional parameter and the positional
# contract for the layers before it is unchanged -- `base` first, `mode` second.
# `memos` is fourth and `chapter` fifth; every layer keeps its `None` default and
# there is no **kwargs catch-all (and so no silent compatibility alias).
def test_author_is_still_the_third_positional_parameter__DoD5():
    params = inspect.signature(compose_system_prompt).parameters

    assert list(params) == ["base", "mode", "author", "memos", "chapter"]
    assert list(params).index("author") == 2
    assert all(p.default is None for p in params.values())
    assert not any(
        p.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
        for p in params.values()
    )


# DoD-5: the positional contract holds at the call site too -- three positional
# arguments still bind base / mode / author, and five bind the full order with
# memos fourth and chapter fifth.
def test_positional_binding_is_base_mode_author_memos_chapter__DoD5():
    three = compose_system_prompt("B TEXT", "M TEXT", "A TEXT")
    assert three == compose_system_prompt(base="B TEXT", mode="M TEXT", author="A TEXT")
    assert three == "### BASE\nB TEXT\n\n### MODE\nM TEXT\n\n### AUTHOR\nA TEXT"

    five = compose_system_prompt("B TEXT", "M TEXT", "A TEXT", "ME TEXT", "C TEXT")
    assert five == compose_system_prompt(
        base="B TEXT",
        mode="M TEXT",
        author="A TEXT",
        memos="ME TEXT",
        chapter="C TEXT",
    )
    assert "### MEMOS\nME TEXT" in five


# ===========================================================================
# The turn -- `chat_turn.compose_turn_system_prompt`
# ===========================================================================


# DoD-1 (US-131.AC-1): every one of the author's active memos is present in the
# composed system prompt, each exactly once, and each inside the MEMOS section --
# after its heading and before the chapter layer that follows it.
async def test_every_active_memo_is_in_the_composed_prompt__DoD1(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    chapter = await _seed_chapter(book.id)
    await _seed_author_prompt(book.id, owner.id, AUTHOR_TEXT)
    await _seed_chapter_prompt(chapter.id, owner.id, CHAPTER_TEXT)
    await _seed_memo(book.id, owner.id, MEMO_ONE, 1)
    await _seed_memo(book.id, owner.id, MEMO_TWO, 2)
    await _seed_memo(book.id, owner.id, MEMO_THREE, 3)

    composed = await _compose(
        chat, server, ResolvedSubject(kind="chapter", chapter=chapter)
    )

    system = composed.system
    assert composed.memos_section is not None
    for body in (MEMO_ONE, MEMO_TWO, MEMO_THREE):
        assert system.count(body) == 1
        assert system.index("### MEMOS") < system.index(body) < system.index(
            "### CHAPTER"
        )


# DoD-2 (US-131.AC-2): the memos appear in ascending ordinal order -- the
# author's own order is the order the assistant receives them in. The rows are
# CREATED in the order 3 / 1 / 2 so insertion order and ordinal order disagree.
async def test_memos_appear_in_ascending_ordinal_order__DoD2(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    await _seed_memo(book.id, owner.id, MEMO_THREE, 3)
    await _seed_memo(book.id, owner.id, MEMO_ONE, 1)
    await _seed_memo(book.id, owner.id, MEMO_TWO, 2)

    system = (await _compose(chat, server)).system

    assert (
        system.index(MEMO_ONE) < system.index(MEMO_TWO) < system.index(MEMO_THREE)
    )


# DoD-3 (US-131.AC-3, US-127.AC-3): an inactive memo and an archived memo each
# contribute nothing. Asserted alongside an ACTIVE memo in the same composition,
# so the spec's positive half ("the active one IS there") carries the test and a
# prompt with no memos layer at all cannot satisfy it.
async def test_inactive_and_archived_memos_contribute_nothing__DoD3(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    await _seed_memo(book.id, owner.id, MEMO_ONE, 1)
    await _seed_memo(book.id, owner.id, INACTIVE_MEMO, 2, active=False)
    await _seed_memo(book.id, owner.id, ARCHIVED_MEMO, 3, archived=True)

    composed = await _compose(chat, server)

    # The positive half -- the active memo reached the prompt.
    assert MEMO_ONE in composed.system
    assert "### MEMOS" in composed.system
    assert composed.memos_section is not None
    assert MEMO_ONE in composed.memos_section

    # The negative half -- neither excluded row did, in either place.
    assert INACTIVE_MEMO not in composed.system
    assert ARCHIVED_MEMO not in composed.system
    assert INACTIVE_MEMO not in composed.memos_section
    assert ARCHIVED_MEMO not in composed.memos_section


# DoD-3: an ARCHIVED memo that is also still `active` is excluded too -- the two
# axes are independent and archived wins for context membership
# (`context.md` decision 1: reaches the assistant iff not archived AND active).
async def test_an_archived_but_active_memo_is_excluded__DoD3(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    await _seed_memo(book.id, owner.id, MEMO_ONE, 1)
    await _seed_memo(book.id, owner.id, ARCHIVED_MEMO, 2, active=True, archived=True)

    system = (await _compose(chat, server)).system

    assert MEMO_ONE in system
    assert ARCHIVED_MEMO not in system


# DoD-6 (UC-109 postcondition): an author with NO active memos contributes no
# section, no separator and no blank block. The POSITIVE CONTROL is a second
# author on the SAME book, with the same turn shape, holding one non-blank active
# memo -- so the spec distinguishes "renders nothing" from "the layer does not
# exist yet".
async def test_no_active_memos_render_no_section__DoD6(db: DbConfig):
    owner = await _seed_user("owner")
    co_author = await _seed_user("co-author")
    book = await _seed_book(owner.id)
    await _add_co_author(book.id, co_author.id)
    server = await _seed_server()

    # The subject of the clause: every memo is inactive or archived.
    await _seed_memo(book.id, owner.id, INACTIVE_MEMO, 1, active=False)
    await _seed_memo(book.id, owner.id, ARCHIVED_MEMO, 2, archived=True)
    empty_chat = await _seed_chat(book.id, owner.id, server.id)

    # The positive control: same book, same turn shape, one active memo.
    await _seed_memo(book.id, co_author.id, CONTROL_MEMO, 1)
    control_chat = await _seed_chat(book.id, co_author.id, server.id)

    empty = await _compose(empty_chat, server)
    control = await _compose(control_chat, server)

    # Nothing rendered: no section, no separator, no blank block.
    assert empty.memos_section is None
    assert "MEMOS" not in empty.system
    assert empty.system == BASE_SECTION

    # ...and the layer demonstrably exists.
    assert control.memos_section is not None
    assert f"### MEMOS\n{CONTROL_MEMO}" in control.system


# DoD-6 (UC-109 postcondition, second half): the same holds when every ACTIVE
# memo has a blank body -- an empty memo is a legitimate row (UC-103) and
# contributes no section and no stray separator. Same positive control.
async def test_all_blank_active_bodies_render_no_section__DoD6(db: DbConfig):
    owner = await _seed_user("owner")
    co_author = await _seed_user("co-author")
    book = await _seed_book(owner.id)
    await _add_co_author(book.id, co_author.id)
    server = await _seed_server()
    await _seed_author_prompt(book.id, owner.id, AUTHOR_TEXT)

    await _seed_memo(book.id, owner.id, "", 1)
    await _seed_memo(book.id, owner.id, "   \n\t ", 2)
    blank_chat = await _seed_chat(book.id, owner.id, server.id)

    await _seed_memo(book.id, co_author.id, CONTROL_MEMO, 1)
    control_chat = await _seed_chat(book.id, co_author.id, server.id)

    blank = await _compose(blank_chat, server)
    control = await _compose(control_chat, server)

    assert blank.memos_section is None
    assert "MEMOS" not in blank.system
    assert blank.system == _expected(BASE_SECTION, _section("AUTHOR", AUTHOR_TEXT))
    assert blank.system == blank.system.rstrip()

    assert control.memos_section is not None
    assert f"### MEMOS\n{CONTROL_MEMO}" in control.system


# DoD-7 (US-132.AC-1): the memos layer is composed INDEPENDENTLY OF THE MODE --
# with a mode prompt present and with none, and for a chapter subject as well as
# a codex one. No mode can be missing it.
@pytest.mark.parametrize(
    "case",
    ["chapter-with-mode", "chapter-no-mode", "codex-with-mode", "codex-no-mode"],
    ids=["chapter_with_mode", "chapter_no_mode", "codex_with_mode", "codex_no_mode"],
)
async def test_memos_layer_is_independent_of_the_mode__DoD7(db: DbConfig, case: str):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    await _seed_memo(book.id, owner.id, MEMO_ONE, 1)

    if case == "chapter-with-mode":
        await _seed_mode(MODE_KEY, MODE_TEXT)
        chapter = await _seed_chapter(book.id)
        subject = ResolvedSubject(kind="chapter", chapter=chapter, mode_key=MODE_KEY)
    elif case == "chapter-no-mode":
        chapter = await _seed_chapter(book.id)
        subject = ResolvedSubject(kind="chapter", chapter=chapter)
    elif case == "codex-with-mode":
        await _seed_mode(CODEX_MODE_KEY, MODE_TEXT)
        entry = await _seed_entry(book.id, owner.id)
        subject = ResolvedSubject(
            kind="codex-entry", entry=entry, mode_key=CODEX_MODE_KEY
        )
    else:
        entry = await _seed_entry(book.id, owner.id)
        subject = ResolvedSubject(kind="codex-entry", entry=entry)

    composed = await _compose(chat, server, subject)

    assert composed.memos_section is not None
    assert f"### MEMOS\n{MEMO_ONE}" in composed.system


# DoD-8 (US-124.AC-1): the turn resolves memos for the CHAT'S OWN AUTHOR and
# that chat's book. A co-author's turn carries their own memo and neither the
# owner's memo on the same book nor their own memo on a different book.
async def test_turn_reads_only_the_chats_own_author_and_book__DoD8(db: DbConfig):
    owner = await _seed_user("owner")
    co_author = await _seed_user("co-author")
    book = await _seed_book(owner.id)
    other_book = await _seed_book(co_author.id, title="Another Book")
    await _add_co_author(book.id, co_author.id)
    server = await _seed_server()

    await _seed_memo(book.id, owner.id, OTHER_AUTHOR_MEMO, 1)
    await _seed_memo(book.id, co_author.id, MEMO_ONE, 1)
    await _seed_memo(other_book.id, co_author.id, OTHER_BOOK_MEMO, 1)

    chat = await _seed_chat(book.id, co_author.id, server.id)

    composed = await _compose(chat, server)

    assert MEMO_ONE in composed.system
    assert OTHER_AUTHOR_MEMO not in composed.system
    assert OTHER_BOOK_MEMO not in composed.system
    assert composed.memos_section is not None
    assert OTHER_AUTHOR_MEMO not in composed.memos_section
    assert OTHER_BOOK_MEMO not in composed.memos_section


# DoD-8, the other direction: nobody -- INCLUDING the book's owner -- receives
# another author's memos (026/context.md decision 1: nobody else ever reads
# them).
async def test_owner_never_receives_a_co_authors_memos__DoD8(db: DbConfig):
    owner = await _seed_user("owner")
    co_author = await _seed_user("co-author")
    book = await _seed_book(owner.id)
    await _add_co_author(book.id, co_author.id)
    server = await _seed_server()

    await _seed_memo(book.id, co_author.id, OTHER_AUTHOR_MEMO, 1)
    await _seed_memo(book.id, owner.id, MEMO_ONE, 1)

    chat = await _seed_chat(book.id, owner.id, server.id)

    composed = await _compose(chat, server)

    assert MEMO_ONE in composed.system
    assert OTHER_AUTHOR_MEMO not in composed.system


# DoD-8: an author with memos ONLY on another book gets no section on this
# book's turn -- the other book's rows are not a fallback.
async def test_another_books_memos_alone_render_no_section__DoD8(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    other_book = await _seed_book(owner.id, title="Another Book")
    server = await _seed_server()
    await _seed_memo(other_book.id, owner.id, OTHER_BOOK_MEMO, 1)

    chat = await _seed_chat(book.id, owner.id, server.id)

    composed = await _compose(chat, server)

    assert OTHER_BOOK_MEMO not in composed.system
    assert composed.memos_section is None
    assert "MEMOS" not in composed.system


# DoD-9 (`assistant-runtime.md` -> "the memo section is rendered once"): the turn
# performs ONE memos read and renders ONE section per turn. The read is counted
# by wrapping `db/memos.list_for_author` (the module object `chat_turn` holds,
# per the frozen record) and delegating to the real function, so the composed
# prompt is still the real one.
async def test_turn_performs_one_memos_read_and_one_section__DoD9(
    db: DbConfig, monkeypatch
):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    chapter = await _seed_chapter(book.id)
    await _seed_author_prompt(book.id, owner.id, AUTHOR_TEXT)
    await _seed_chapter_prompt(chapter.id, owner.id, CHAPTER_TEXT)
    await _seed_memo(book.id, owner.id, MEMO_ONE, 1)
    await _seed_memo(book.id, owner.id, MEMO_TWO, 2)

    real_list_for_author = memos_db.list_for_author
    calls: list[tuple] = []

    async def counting_list_for_author(*args, **kwargs):
        calls.append((args, kwargs))
        return await real_list_for_author(*args, **kwargs)

    monkeypatch.setattr(memos_db, "list_for_author", counting_list_for_author)

    composed = await _compose(
        chat, server, ResolvedSubject(kind="chapter", chapter=chapter)
    )

    # Exactly one read...
    assert len(calls) == 1

    # ...and exactly one section, rendered once and reused: the value exposed for
    # delegation IS the one the composer rendered (026/context.md decision 7).
    assert composed.system.count("### MEMOS") == 1
    assert composed.system.count(MEMO_ONE) == 1
    assert composed.system.count(MEMO_TWO) == 1
    assert composed.memos_section is not None
    assert f"### MEMOS\n{composed.memos_section.strip()}" in composed.system
