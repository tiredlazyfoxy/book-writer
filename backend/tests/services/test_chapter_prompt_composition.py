"""Tests for the caller's own chapter prompt as composition layer 4
(feature 015, step 013).

Bound to the frozen skeleton (``status.md`` -> ``## Skeleton`` -> Step 013), in
``app.services.chat_turn``::

    async def compose_turn_system_prompt(context: TurnContext) -> str

which loads the four layers and returns the composer's result:

    1. base    -- ``prompt_composition.BASE_SYSTEM_PROMPT``
    2. mode    -- ``assistant_runtime.mode_system_prompt(context.subject.mode_key)``
    3. author  -- the ``(chat.book_id, chat.author_id)`` ``BookAuthorPrompt`` row
    4. chapter -- NEW: when and only when ``context.subject.chapter`` is not
                  ``None``, the ``(subject.chapter.id, chat.author_id)``
                  ``ChapterAuthorPrompt`` row.

and, untouched by this step (DoD-7), in ``app.services.prompt_composition``::

    BASE_SYSTEM_PROMPT: str
    def compose_system_prompt(base=None, mode=None, author=None,
                              chapter=None) -> str

Supporting frozen records used only to *call*: ``TurnContext`` (011/013/015 step
009: ``chat``, ``server``, ``resolved_key``, ``subject`` defaulted to
``NO_SUBJECT``, ``access``, ``selection_text``) and ``ResolvedSubject`` (015 step
009: ``kind``, ``entry``, ``chapter``, ``mode_key``).

Expected values come from the SPEC ONLY -- ``013.chapter-prompt-composition.md``
-> Interface intent + Definition of done (DoD-1..DoD-7), ``013.context.md``
("The composer already has the slot", "Whose prompt, and why no ``BookAccess``",
"Testing"), and ``context.md`` -> D12 -- never from implementation internals.

Test approach (``013.context.md`` -> "Testing"): **no LLM server is contacted**.
The composition path is exercised **as a function** and the assertions are over
the composed string; ``chat_with_tools`` is never called and ``run_turn`` is
never driven. Chapters, prompt rows, mode rows and chats are seeded through the
sibling ``db/`` modules against the ``db`` fixture's throwaway temp SQLite;
``asyncio_mode = "auto"``, so no decorator is needed.

This step cites no product id (its criteria are self-contained, the convention
014 and 021 used), so test names carry the DoD id alone.
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
from app.models.user import User, UserRole
from app.services import chat_turn
from app.services.assistant_runtime import NO_SUBJECT, ResolvedSubject
from app.services.chat_turn import TurnContext
from app.services.prompt_composition import BASE_SYSTEM_PROMPT, compose_system_prompt

# Sentinels -- one per layer / per author. Chosen so they cannot collide with a
# section label, a delimiter, or any plausible substring of the base prompt.
MODE_TEXT = "ZZMODEPROMPTZZ"
AUTHOR_TEXT = "ZZAUTHORPROMPTZZ"
CHAPTER_TEXT = "ZZOWNCHAPTERPROMPTZZ"
OTHER_CHAPTER_TEXT = "ZZOTHERMEMBERCHAPTERPROMPTZZ"
DORMANT_TEXT = "ZZDORMANTCOLUMNZZ"

MODE_KEY = "write-chapter"
CODEX_MODE_KEY = "edit-character"


# ---------------------------------------------------------------------------
# Expected-string builders -- the composer's frozen rendering (013.context.md ->
# "The composer already has the slot"; Skeleton -> Step 013): each non-blank
# layer renders as `### <LABEL>\n<text.strip()>`, survivors joined by a blank
# line, labels BASE / MODE / AUTHOR / CHAPTER in that fixed order.
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


async def _seed_book(owner_id: int) -> Book:
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


async def _seed_chapter(
    book_id: int,
    *,
    state: ChapterState = ChapterState.open,
    system_prompt: str = "",
    ordinal: int = 1,
) -> Chapter:
    """A chapter written straight through db/chapters.py in the given state.

    A spec for the prompt path must not depend on the transition path to reach a
    state, and `closing` is reachable no other way in this feature (D8).
    `system_prompt` seeds the DORMANT column (014's D1) -- nothing may read it.
    """
    return await chapters.create(
        Chapter(
            book_id=book_id,
            ordinal=ordinal,
            title="Chapter One",
            state=state,
            sketch="",
            text="",
            system_prompt=system_prompt,
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


def _context(chat: Chat, server: LlmServer, subject=None) -> TurnContext:
    """The frozen record, built by hand -- no `prepare_turn`, no stream.

    `subject` omitted means "leave the field at its default", which is the
    shipped no-subject turn.
    """
    if subject is None:
        return TurnContext(chat=chat, server=server, resolved_key="resolved-secret")
    return TurnContext(
        chat=chat, server=server, resolved_key="resolved-secret", subject=subject
    )


# ---------------------------------------------------------------------------
# DoD-1 -- the caller's own chapter prompt composes as the FOURTH layer, after
# base, mode and author, in that order
# ---------------------------------------------------------------------------


# DoD-1: with all four layers populated, the composed prompt is exactly the four
# sections in the fixed order base -> mode -> author -> chapter. Bound to the
# whole string, not to presence, because a presence-only assertion would pass on
# a wrong order (013.context.md -> "Testing").
async def test_chapter_prompt_is_the_fourth_layer_in_order__DoD1(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    chapter = await _seed_chapter(book.id)
    await _seed_mode(MODE_KEY, MODE_TEXT)
    await _seed_author_prompt(book.id, owner.id, AUTHOR_TEXT)
    await _seed_chapter_prompt(chapter.id, owner.id, CHAPTER_TEXT)

    subject = ResolvedSubject(kind="chapter", chapter=chapter, mode_key=MODE_KEY)

    result = await chat_turn.compose_turn_system_prompt(_context(chat, server, subject))

    assert result == _expected(
        BASE_SECTION,
        _section("MODE", MODE_TEXT),
        _section("AUTHOR", AUTHOR_TEXT),
        _section("CHAPTER", CHAPTER_TEXT),
    )


# DoD-1: the same fact stated as strict ordering -- the chapter text appears
# exactly once, under a `### CHAPTER` heading, after the base, mode and author
# sections. A layer emitted first, twice, or without its heading fails here.
async def test_chapter_layer_follows_base_mode_and_author__DoD1(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    chapter = await _seed_chapter(book.id)
    await _seed_mode(MODE_KEY, MODE_TEXT)
    await _seed_author_prompt(book.id, owner.id, AUTHOR_TEXT)
    await _seed_chapter_prompt(chapter.id, owner.id, CHAPTER_TEXT)

    subject = ResolvedSubject(kind="chapter", chapter=chapter, mode_key=MODE_KEY)

    result = await chat_turn.compose_turn_system_prompt(_context(chat, server, subject))

    assert result.count(CHAPTER_TEXT) == 1
    assert f"### CHAPTER\n{CHAPTER_TEXT}" in result
    assert (
        result.index("### BASE")
        < result.index("### MODE")
        < result.index("### AUTHOR")
        < result.index("### CHAPTER")
    )


# ---------------------------------------------------------------------------
# DoD-2 -- the identity is the CHAT'S OWN AUTHOR; another member's row for the
# same chapter is never read, the owner included
# ---------------------------------------------------------------------------


# DoD-2: two members hold different prompt rows on the SAME chapter. A co-author's
# chat composes the co-author's own text and never the owner's -- the identity is
# the chat's author, not the book's owner (013.context.md -> "Whose prompt, and
# why no `BookAccess`").
async def test_co_author_turn_composes_only_the_co_authors_prompt__DoD2(db: DbConfig):
    owner = await _seed_user("owner")
    co_author = await _seed_user("co-author")
    book = await _seed_book(owner.id)
    await _add_co_author(book.id, co_author.id)
    server = await _seed_server()
    chapter = await _seed_chapter(book.id)
    await _seed_chapter_prompt(chapter.id, owner.id, OTHER_CHAPTER_TEXT)
    await _seed_chapter_prompt(chapter.id, co_author.id, CHAPTER_TEXT)

    chat = await _seed_chat(book.id, co_author.id, server.id)
    subject = ResolvedSubject(kind="chapter", chapter=chapter)

    result = await chat_turn.compose_turn_system_prompt(_context(chat, server, subject))

    assert result == _expected(BASE_SECTION, _section("CHAPTER", CHAPTER_TEXT))
    assert OTHER_CHAPTER_TEXT not in result


# DoD-2, the other direction: nobody -- INCLUDING the book's owner -- reads
# another author's chapter prompt. The owner's turn composes the owner's own row
# and never the co-author's.
async def test_owner_never_reads_another_members_chapter_prompt__DoD2(db: DbConfig):
    owner = await _seed_user("owner")
    co_author = await _seed_user("co-author")
    book = await _seed_book(owner.id)
    await _add_co_author(book.id, co_author.id)
    server = await _seed_server()
    chapter = await _seed_chapter(book.id)
    await _seed_chapter_prompt(chapter.id, co_author.id, OTHER_CHAPTER_TEXT)
    await _seed_chapter_prompt(chapter.id, owner.id, CHAPTER_TEXT)

    chat = await _seed_chat(book.id, owner.id, server.id)
    subject = ResolvedSubject(kind="chapter", chapter=chapter)

    result = await chat_turn.compose_turn_system_prompt(_context(chat, server, subject))

    assert result == _expected(BASE_SECTION, _section("CHAPTER", CHAPTER_TEXT))
    assert OTHER_CHAPTER_TEXT not in result


# DoD-2: a chapter on which ONLY another member holds a row contributes nothing
# to this caller's turn -- the row is not a fallback, it is simply not theirs.
async def test_another_members_row_alone_composes_no_chapter_layer__DoD2(db: DbConfig):
    owner = await _seed_user("owner")
    co_author = await _seed_user("co-author")
    book = await _seed_book(owner.id)
    await _add_co_author(book.id, co_author.id)
    server = await _seed_server()
    chapter = await _seed_chapter(book.id)
    await _seed_chapter_prompt(chapter.id, co_author.id, OTHER_CHAPTER_TEXT)

    chat = await _seed_chat(book.id, owner.id, server.id)
    subject = ResolvedSubject(kind="chapter", chapter=chapter)

    result = await chat_turn.compose_turn_system_prompt(_context(chat, server, subject))

    assert result == BASE_SECTION
    assert OTHER_CHAPTER_TEXT not in result
    assert "### CHAPTER" not in result


# ---------------------------------------------------------------------------
# DoD-3 -- no row, and a row whose prompt is "", both contribute nothing: no
# section, no separator, no blank block
# ---------------------------------------------------------------------------


# DoD-3: a chapter with NO prompt row for the caller contributes nothing -- the
# composed prompt is exactly the surviving layers, with no `### CHAPTER` heading
# and no trailing separator or blank block.
async def test_absent_chapter_prompt_row_contributes_nothing__DoD3(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    chapter = await _seed_chapter(book.id)
    await _seed_mode(MODE_KEY, MODE_TEXT)
    await _seed_author_prompt(book.id, owner.id, AUTHOR_TEXT)

    subject = ResolvedSubject(kind="chapter", chapter=chapter, mode_key=MODE_KEY)

    result = await chat_turn.compose_turn_system_prompt(_context(chat, server, subject))

    assert result == _expected(
        BASE_SECTION,
        _section("MODE", MODE_TEXT),
        _section("AUTHOR", AUTHOR_TEXT),
    )
    assert "### CHAPTER" not in result
    # No trailing separator, no blank block.
    assert result == result.rstrip()


# DoD-3: a row whose prompt is the EMPTY STRING ("" is a real stored value)
# contributes nothing either -- byte-for-byte the same output as having no row
# at all.
async def test_empty_chapter_prompt_matches_having_no_row__DoD3(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    await _seed_mode(MODE_KEY, MODE_TEXT)
    await _seed_author_prompt(book.id, owner.id, AUTHOR_TEXT)

    with_empty_row = await _seed_chapter(book.id, ordinal=1)
    await _seed_chapter_prompt(with_empty_row.id, owner.id, "")
    without_row = await _seed_chapter(book.id, ordinal=2)

    empty_result = await chat_turn.compose_turn_system_prompt(
        _context(
            chat,
            server,
            ResolvedSubject(kind="chapter", chapter=with_empty_row, mode_key=MODE_KEY),
        )
    )
    absent_result = await chat_turn.compose_turn_system_prompt(
        _context(
            chat,
            server,
            ResolvedSubject(kind="chapter", chapter=without_row, mode_key=MODE_KEY),
        )
    )

    assert empty_result == absent_result
    assert empty_result == _expected(
        BASE_SECTION,
        _section("MODE", MODE_TEXT),
        _section("AUTHOR", AUTHOR_TEXT),
    )
    assert "### CHAPTER" not in empty_result
    assert empty_result == empty_result.rstrip()


# DoD-3: with the chapter layer the only candidate, an empty row composes exactly
# the base section -- no separator is emitted for the skipped layer.
async def test_empty_chapter_prompt_adds_no_separator__DoD3(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    chapter = await _seed_chapter(book.id)
    await _seed_chapter_prompt(chapter.id, owner.id, "")

    subject = ResolvedSubject(kind="chapter", chapter=chapter)

    result = await chat_turn.compose_turn_system_prompt(_context(chat, server, subject))

    assert result == BASE_SECTION


# ---------------------------------------------------------------------------
# DoD-4 -- a turn whose subject is NOT a chapter composes exactly what it
# composes today, with no fourth layer (the regression clause)
# ---------------------------------------------------------------------------


# DoD-4: a codex-entry subject, a list subject, a book-state subject, an explicit
# no-subject and the record's default subject all compose base + mode + author
# and no fourth layer -- even though the caller HOLDS a chapter prompt row in the
# same book. The fourth layer applies when and only when the subject is a
# chapter.
@pytest.mark.parametrize(
    "case",
    ["codex-entry", "chapters-list", "book-state", "no-subject", "default-subject"],
    ids=["codex_entry", "list", "book_state", "no_subject", "default_subject"],
)
async def test_non_chapter_subject_composes_no_fourth_layer__DoD4(
    db: DbConfig, case: str
):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    await _seed_author_prompt(book.id, owner.id, AUTHOR_TEXT)

    # The caller's chapter prompt exists and must stay unread on these turns.
    chapter = await _seed_chapter(book.id)
    await _seed_chapter_prompt(chapter.id, owner.id, CHAPTER_TEXT)

    if case == "codex-entry":
        await _seed_mode(CODEX_MODE_KEY, MODE_TEXT)
        entry = await _seed_entry(book.id, owner.id)
        context = _context(
            chat,
            server,
            ResolvedSubject(
                kind="codex-entry", entry=entry, mode_key=CODEX_MODE_KEY
            ),
        )
        expected = _expected(
            BASE_SECTION, _section("MODE", MODE_TEXT), _section("AUTHOR", AUTHOR_TEXT)
        )
    elif case == "chapters-list":
        context = _context(chat, server, ResolvedSubject(kind="chapters"))
        expected = _expected(BASE_SECTION, _section("AUTHOR", AUTHOR_TEXT))
    elif case == "book-state":
        context = _context(chat, server, ResolvedSubject(kind="book-state"))
        expected = _expected(BASE_SECTION, _section("AUTHOR", AUTHOR_TEXT))
    elif case == "no-subject":
        context = _context(chat, server, NO_SUBJECT)
        expected = _expected(BASE_SECTION, _section("AUTHOR", AUTHOR_TEXT))
    else:
        context = _context(chat, server)
        expected = _expected(BASE_SECTION, _section("AUTHOR", AUTHOR_TEXT))

    result = await chat_turn.compose_turn_system_prompt(context)

    assert result == expected
    assert "### CHAPTER" not in result
    assert CHAPTER_TEXT not in result


# ---------------------------------------------------------------------------
# DoD-5 -- the prompt is read for a chapter in EVERY state; the chapter state
# machine does not gate it
# ---------------------------------------------------------------------------


# DoD-5: `planned`, `open`, `closing` and `closed` all compose the caller's
# chapter prompt. A prompt is the author's instruction to their own assistant,
# not chapter content, so the state machine does not gate it (014's
# authorization decision). States are seeded directly through db/chapters.py.
@pytest.mark.parametrize(
    "state",
    [
        ChapterState.planned,
        ChapterState.open,
        ChapterState.closing,
        ChapterState.closed,
    ],
    ids=["planned", "open", "closing", "closed"],
)
async def test_chapter_prompt_is_read_in_every_state__DoD5(
    db: DbConfig, state: ChapterState
):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    chapter = await _seed_chapter(book.id, state=state)
    await _seed_chapter_prompt(chapter.id, owner.id, CHAPTER_TEXT)

    subject = ResolvedSubject(kind="chapter", chapter=chapter)

    result = await chat_turn.compose_turn_system_prompt(_context(chat, server, subject))

    assert result == _expected(BASE_SECTION, _section("CHAPTER", CHAPTER_TEXT))


# ---------------------------------------------------------------------------
# DoD-6 -- `Chapter.system_prompt` is dormant and is NOT read
# ---------------------------------------------------------------------------


# DoD-6: a chapter whose dormant `system_prompt` column holds text, and whose
# `ChapterAuthorPrompt` row is ABSENT, contributes neither -- no chapter section
# at all and no trace of the column's text.
async def test_dormant_chapter_column_is_never_composed__DoD6(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    chapter = await _seed_chapter(book.id, system_prompt=DORMANT_TEXT)

    subject = ResolvedSubject(kind="chapter", chapter=chapter)

    result = await chat_turn.compose_turn_system_prompt(_context(chat, server, subject))

    assert result == BASE_SECTION
    assert DORMANT_TEXT not in result
    assert "### CHAPTER" not in result


# DoD-6: when the caller DOES hold a row, that row is the fourth layer and the
# dormant column still contributes nothing -- the column is superseded, not a
# second source and not a fallback.
async def test_dormant_column_is_ignored_when_a_row_exists__DoD6(db: DbConfig):
    owner = await _seed_user("owner")
    book = await _seed_book(owner.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, owner.id, server.id)
    chapter = await _seed_chapter(book.id, system_prompt=DORMANT_TEXT)
    await _seed_chapter_prompt(chapter.id, owner.id, CHAPTER_TEXT)

    subject = ResolvedSubject(kind="chapter", chapter=chapter)

    result = await chat_turn.compose_turn_system_prompt(_context(chat, server, subject))

    assert result == _expected(BASE_SECTION, _section("CHAPTER", CHAPTER_TEXT))
    assert DORMANT_TEXT not in result


# ---------------------------------------------------------------------------
# DoD-7 -- `services/prompt_composition.py` is unchanged: the fourth layer was
# already there and this step only fills it (a pure preservation clause)
# ---------------------------------------------------------------------------


# DoD-7: the composer's signature is untouched -- four optional layers named
# base / mode / author / chapter, in that positional order, each defaulting to
# None, all keyword-bindable, with no **kwargs catch-all and no fifth parameter.
def test_composer_signature_is_unchanged__DoD7():
    params = inspect.signature(compose_system_prompt).parameters

    assert list(params) == ["base", "mode", "author", "chapter"]
    assert all(p.default is None for p in params.values())
    assert not any(
        p.kind
        in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
        for p in params.values()
    )


# DoD-7: the composer's behaviour is untouched -- the four labels, their fixed
# order, the `### <LABEL>\n<text.strip()>` rendering and the blank-line join are
# exactly as before this step.
def test_composer_behaviour_is_unchanged__DoD7():
    assert compose_system_prompt(
        base="B TEXT", mode="M TEXT", author="A TEXT", chapter="C TEXT"
    ) == (
        "### BASE\nB TEXT\n\n"
        "### MODE\nM TEXT\n\n"
        "### AUTHOR\nA TEXT\n\n"
        "### CHAPTER\nC TEXT"
    )


# DoD-7: the skip rule -- the one this step's DoD-3 rests on and which needed no
# new code -- is unchanged: an absent, empty or whitespace-only layer contributes
# no section, no separator and no blank block.
def test_composer_skip_rule_is_unchanged__DoD7():
    assert compose_system_prompt(
        base="B TEXT", mode=None, author="", chapter="   \n\t "
    ) == "### BASE\nB TEXT"
    assert compose_system_prompt() == ""


# DoD-7: the base constant is still a populated, non-empty string -- the
# always-present layer this step composes around.
def test_base_system_prompt_is_unchanged_in_shape__DoD7():
    assert isinstance(BASE_SYSTEM_PROMPT, str)
    assert BASE_SYSTEM_PROMPT.strip() != ""
