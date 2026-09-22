"""Tests for the `MEMOS` section reaching a delegated sub-agent (feature 026,
step 007).

Bound to the frozen skeleton (`status.md` -> `## Skeleton` -> Step 007, and Step
006 for the two values this step consumes):

    app.services.subagent_delegation:
        @dataclass(frozen=True) class ParentTurn {
            server: LlmServer; resolved_key: str | None; model: str;
            tool_context: ToolContext | None = None;
            memos_section: str | None = None }
        async def build_delegation_tools(mode_key: str | None,
                                         parent: ParentTurn) -> list[ToolDef]
        async def run_delegation(sub_agent, parent, task) -> str

    app.services.chat_turn:
        @dataclass(frozen=True) class ComposedTurnPrompt {
            system: str; memos_section: str | None }
        async def compose_turn_system_prompt(context: TurnContext)
                -> ComposedTurnPrompt

    app.services.prompt_composition:
        def compose_system_prompt(base=None, mode=None, author=None,
                                  memos=None, chapter=None) -> str

plus the step-001 row and reader used only to *seed* and to *count*:

    app.models.memo.Memo(book_id, user_id, body, ordinal, active, archived, ...)
    app.db.memos.create / list_for_author(book_id, user_id,
                                          include_archived=False)

Expected values come from the SPEC ONLY -- `007.memos-in-delegation.md` ->
Interface intent + Definition of done (DoD-1..DoD-7), `007.context.md`, and
`026/context.md` decision 7 -- never from implementation internals.

The composition shape asserted here is the one the plan and the frozen record
fix: the nested `system` is the sub-agent's own `system_prompt`, a blank line,
then the **composer's own** `MEMOS` section (`compose_system_prompt(memos=...)`)
and nothing else; with no section it is the sub-agent's prompt verbatim. The
section is therefore never hand-assembled in a spec either: the expected child
string is built by calling the same composer the parent's prompt goes through,
so the child's section cannot be asserted to differ from the parent's.

Test approach (`007.context.md` -> "Test seeding"): the nested-call harness is
`tests/services/test_subagent_delegation.py`'s -- the client-construction seam
`app.services.llm_servers.create_model_client` is monkeypatched with a factory
handing back a fake async-context-manager client that records every
`chat_with_tools` kwarg, so **no network is opened**; the `system` argument the
nested call received is the observation point. Rows are seeded through the `db/`
layer against the real temp-SQLite `db` fixture; `asyncio_mode = "auto"`, so
async tests need no decorator. There is no shared factory module, so the
`_seed_*` helpers are local, copied in idiom from
`tests/services/test_subagent_delegation.py` and
`tests/services/test_memo_prompt_composition.py`.
"""

import types

import pytest
from llm import LLMError

from app.db import (
    assistant_modes,
    book_author_prompts,
    books,
    chapter_author_prompts,
    chapters,
    chats,
    llm_servers,
    memos as memos_db,
    mode_subagents,
    sub_agents,
    users,
)
from app.db.engine import DbConfig
from app.models.assistant_mode import AssistantMode
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.book_author_prompt import BookAuthorPrompt
from app.models.chapter import Chapter, ChapterState
from app.models.chapter_author_prompt import ChapterAuthorPrompt
from app.models.chat import Chat
from app.models.llm_server import LlmServer
from app.models.memo import Memo
from app.models.mode_subagent import ModeSubagent
from app.models.sub_agent import SubAgent
from app.models.user import User, UserRole
from app.services import chat_turn, subagent_delegation
from app.services.assistant_runtime import ResolvedSubject
from app.services.chat_turn import TurnContext
from app.services.prompt_composition import BASE_SYSTEM_PROMPT, compose_system_prompt
from app.services.subagent_delegation import ParentTurn, build_delegation_tools
from app.services.tools import ToolDef

# The nested call's scripted final string.
NESTED_ANSWER = "NESTED_SUBAGENT_ANSWER"

PARENT_KEY = "PARENT_RESOLVED_KEY"
PARENT_MODEL = "parent-model"

# The sub-agent's own, admin-configured prompt.
SUBAGENT_PROMPT = "ZZSUBAGENTPROMPTZZ"

# Sentinels -- chosen so they cannot collide with a section label, a delimiter,
# or any plausible substring of the base prompt or of each other.
MODE_TEXT = "ZZMODEPROMPTZZ"
AUTHOR_TEXT = "ZZAUTHORPROMPTZZ"
CHAPTER_TEXT = "ZZCHAPTERPROMPTZZ"

MEMO_ONE = "ZZMEMOONEZZ"
MEMO_TWO = "ZZMEMOTWOZZ"
MEMO_THREE = "ZZMEMOTHREEZZ"
MID_TURN_MEMO = "ZZMIDTURNMEMOZZ"
INACTIVE_MEMO = "ZZINACTIVEMEMOZZ"
ARCHIVED_MEMO = "ZZARCHIVEDMEMOZZ"

MODE_KEY = "edit-character"
SUBAGENT_NAME = "Continuity Checker"
SUBAGENT_TOOL = "ask_continuity_checker"


# ---------------------------------------------------------------------------
# The fake LLM client + the recording construction seam (no network).
# ---------------------------------------------------------------------------


class _FakeClient:
    """A stand-in for ``llm.LLMClient`` used as an async context manager."""

    def __init__(self, *, result: str = NESTED_ANSWER, exc=None):
        self._result = result
        self._exc = exc
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
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
        self.calls.append({"messages": messages, "system": system})
        if self._exc is not None:
            raise self._exc
        return self._result


class _ClientFactory:
    """The monkeypatched ``create_model_client``; one fresh client per call."""

    def __init__(self, *, result: str = NESTED_ANSWER, exc=None):
        self._result = result
        self._exc = exc
        self.clients: list[_FakeClient] = []

    def __call__(self, server, resolved_key, model):
        client = _FakeClient(result=self._result, exc=self._exc)
        self.clients.append(client)
        return client


def _install_factory(monkeypatch, factory: _ClientFactory) -> _ClientFactory:
    monkeypatch.setattr("app.services.llm_servers.create_model_client", factory)
    monkeypatch.setattr(
        "app.services.chat_turn.create_model_client", factory, raising=False
    )
    return factory


# ---------------------------------------------------------------------------
# Seeding helpers (rows built through the db layer).
# ---------------------------------------------------------------------------


async def _seed_user(username: str = "author") -> User:
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


async def _seed_server(name: str = "S") -> LlmServer:
    return await llm_servers.create(
        LlmServer(
            name=name,
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
    """A memo row written straight through ``db/memos.py``."""
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


async def _seed_sub_agent(
    name: str = SUBAGENT_NAME, *, system_prompt: str = SUBAGENT_PROMPT
) -> SubAgent:
    return await sub_agents.create(
        SubAgent(
            name=name,
            system_prompt=system_prompt,
            disabled=False,
            llm_server_id=None,
            model_name=None,
        )
    )


async def _link_sub_agent(mode_key: str, sub_agent_id: int) -> ModeSubagent:
    return await mode_subagents.create(
        ModeSubagent(mode_key=mode_key, sub_agent_id=sub_agent_id)
    )


# ---------------------------------------------------------------------------
# Composition helpers.
# ---------------------------------------------------------------------------


def _context(chat: Chat, server: LlmServer, subject=None) -> TurnContext:
    if subject is None:
        return TurnContext(chat=chat, server=server, resolved_key="resolved-secret")
    return TurnContext(
        chat=chat, server=server, resolved_key="resolved-secret", subject=subject
    )


async def _compose_parent(chat: Chat, server: LlmServer, subject=None):
    """The turn's own composition -- the source of the carried section."""
    return await chat_turn.compose_turn_system_prompt(_context(chat, server, subject))


def _expected_child(sub_agent_prompt: str, memos_section: str | None) -> str:
    """The nested system the spec requires.

    `007.memos-in-delegation.md` -> Interface intent + `007.context.md` ->
    "compose, do not concatenate": the sub-agent's own prompt plus the `MEMOS`
    section **through the same composer** the parent's prompt goes through, and
    nothing else; with no section, the sub-agent's prompt verbatim (DoD-4).
    """
    composed = compose_system_prompt(memos=memos_section)
    if composed == "":
        return sub_agent_prompt
    return f"{sub_agent_prompt}\n\n{composed}"


def _find(tools: list[ToolDef], name: str) -> ToolDef:
    return [tool for tool in tools if tool.name == name][0]


async def _delegate(
    parent: ParentTurn, factory: _ClientFactory, task: str = "check the timeline"
) -> str:
    """Invoke the synthetic delegation tool and return the parent's result."""
    built = await build_delegation_tools(MODE_KEY, parent)
    return await _find(built, SUBAGENT_TOOL).callable(task=task)


def _nested_system(factory: _ClientFactory) -> str:
    assert len(factory.clients) == 1, "exactly one nested client per delegation"
    assert factory.clients[0].calls, "the nested chat_with_tools was never reached"
    return factory.clients[0].calls[0]["system"] or ""


async def _seed_world(
    *,
    with_mode_prompt: bool = False,
) -> tuple[User, Book, LlmServer, Chat]:
    """A user, their book, a server, their chat, the mode and the sub-agent."""
    user = await _seed_user()
    book = await _seed_book(user.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, user.id, server.id)
    await _seed_mode(MODE_KEY, MODE_TEXT if with_mode_prompt else None)
    agent = await _seed_sub_agent()
    await _link_sub_agent(MODE_KEY, agent.id)
    return user, book, server, chat


def _parent_turn(server: LlmServer, memos_section: str | None) -> ParentTurn:
    return ParentTurn(
        server=server,
        resolved_key=PARENT_KEY,
        model=PARENT_MODEL,
        memos_section=memos_section,
    )


# ===========================================================================
# DoD-1 — the author's active memos reach the sub-agent, in the author's order
# ===========================================================================


# DoD-1 (US-132.AC-2): a delegated sub-agent's nested system prompt contains the
# author's active memos, in the author's order. The rows are CREATED 3 / 1 / 2 so
# insertion order and ordinal order disagree, and the section carried is the one
# the parent's own turn composed.
async def test_delegated_system_carries_the_active_memos_in_order__DoD1(
    db: DbConfig, monkeypatch
):
    user, book, server, chat = await _seed_world()
    await _seed_memo(book.id, user.id, MEMO_THREE, 3)
    await _seed_memo(book.id, user.id, MEMO_ONE, 1)
    await _seed_memo(book.id, user.id, MEMO_TWO, 2)

    composed = await _compose_parent(chat, server)
    assert composed.memos_section is not None

    factory = _install_factory(monkeypatch, _ClientFactory())
    result = await _delegate(_parent_turn(server, composed.memos_section), factory)

    assert result == NESTED_ANSWER

    system = _nested_system(factory)
    for body in (MEMO_ONE, MEMO_TWO, MEMO_THREE):
        assert system.count(body) == 1
    assert system.index(MEMO_ONE) < system.index(MEMO_TWO) < system.index(MEMO_THREE)

    # The sub-agent's own prompt is still there, and the section is the
    # composer's own `MEMOS` section -- identical in shape to the parent's.
    assert SUBAGENT_PROMPT in system
    assert system.count("### MEMOS") == 1
    assert system == _expected_child(SUBAGENT_PROMPT, composed.memos_section)


# ===========================================================================
# DoD-2 — only the sub-agent's prompt and the MEMOS section thread through
# ===========================================================================


# DoD-2 (US-132.AC-2): the nested system contains ONLY the sub-agent's own prompt
# and the `MEMOS` section -- no base, mode, author or chapter layer. Staged
# against a parent turn that demonstrably HAS all four other layers, so the
# absence is an exclusion rather than an empty world.
async def test_no_other_layer_threads_into_the_delegated_system__DoD2(
    db: DbConfig, monkeypatch
):
    user, book, server, chat = await _seed_world(with_mode_prompt=True)
    chapter = await _seed_chapter(book.id)
    await _seed_author_prompt(book.id, user.id, AUTHOR_TEXT)
    await _seed_chapter_prompt(chapter.id, user.id, CHAPTER_TEXT)
    await _seed_memo(book.id, user.id, MEMO_ONE, 1)

    composed = await _compose_parent(
        chat,
        server,
        ResolvedSubject(kind="chapter", chapter=chapter, mode_key=MODE_KEY),
    )
    # The parent really does carry all five layers -- otherwise the child's
    # exclusions below would prove nothing.
    for marker in ("### BASE", "### MODE", "### AUTHOR", "### MEMOS", "### CHAPTER"):
        assert marker in composed.system

    factory = _install_factory(monkeypatch, _ClientFactory())
    await _delegate(_parent_turn(server, composed.memos_section), factory)

    system = _nested_system(factory)

    assert system == _expected_child(SUBAGENT_PROMPT, composed.memos_section)
    assert SUBAGENT_PROMPT in system
    assert MEMO_ONE in system

    # Neither the other layers' text...
    assert BASE_SYSTEM_PROMPT not in system
    assert MODE_TEXT not in system
    assert AUTHOR_TEXT not in system
    assert CHAPTER_TEXT not in system
    # ...nor their headings: `MEMOS` is the only section in the nested prompt.
    for marker in ("### BASE", "### MODE", "### AUTHOR", "### CHAPTER"):
        assert marker not in system
    assert system.count("###") == 1


# ===========================================================================
# DoD-3 — inactive and archived memos are absent, exactly as from the parent's
# ===========================================================================


# DoD-3 (US-131.AC-3): an inactive memo and an archived memo are absent from the
# sub-agent's prompt exactly as they are from the parent's -- asserted as the
# IDENTITY of the section rather than by re-deriving the expected text, with an
# active memo present in the same composition as the positive half.
async def test_inactive_and_archived_memos_reach_no_subagent__DoD3(
    db: DbConfig, monkeypatch
):
    user, book, server, chat = await _seed_world()
    await _seed_memo(book.id, user.id, MEMO_ONE, 1)
    await _seed_memo(book.id, user.id, INACTIVE_MEMO, 2, active=False)
    await _seed_memo(book.id, user.id, ARCHIVED_MEMO, 3, archived=True)
    await _seed_memo(book.id, user.id, ARCHIVED_MEMO + "X", 4, active=True, archived=True)

    composed = await _compose_parent(chat, server)
    assert composed.memos_section is not None

    factory = _install_factory(monkeypatch, _ClientFactory())
    await _delegate(_parent_turn(server, composed.memos_section), factory)

    system = _nested_system(factory)

    # The section the child carries IS the parent's section, rendered the same
    # way -- one string, so the two cannot disagree about membership.
    assert system == _expected_child(SUBAGENT_PROMPT, composed.memos_section)
    assert f"### MEMOS\n{composed.memos_section.strip()}" in composed.system
    assert f"### MEMOS\n{composed.memos_section.strip()}" in system

    # The positive half, and the two exclusions in both prompts alike.
    assert MEMO_ONE in system
    assert MEMO_ONE in composed.system
    for excluded in (INACTIVE_MEMO, ARCHIVED_MEMO):
        assert excluded not in system
        assert excluded not in composed.system


# ===========================================================================
# DoD-4 — with no active memos the nested system is the prompt alone
# ===========================================================================


# DoD-4 (UC-109 postcondition): with NO active memos the sub-agent's system is
# its own prompt alone, unchanged from today's behaviour -- no empty section, no
# stray separator, not even a trailing blank line. Three carriers of "no
# section": the value a memo-less turn composes, an explicit `None`, and a
# `ParentTurn` constructed without the field at all.
@pytest.mark.parametrize(
    "carrier", ["composed", "explicit_none", "field_omitted"]
)
async def test_no_memos_leaves_the_subagent_prompt_verbatim__DoD4(
    db: DbConfig, monkeypatch, carrier: str
):
    user, book, server, chat = await _seed_world()
    # Every memo the author has is excluded from context.
    await _seed_memo(book.id, user.id, INACTIVE_MEMO, 1, active=False)
    await _seed_memo(book.id, user.id, ARCHIVED_MEMO, 2, archived=True)

    if carrier == "field_omitted":
        parent = ParentTurn(server=server, resolved_key=PARENT_KEY, model=PARENT_MODEL)
    elif carrier == "explicit_none":
        parent = _parent_turn(server, None)
    else:
        composed = await _compose_parent(chat, server)
        assert composed.memos_section is None
        parent = _parent_turn(server, composed.memos_section)

    factory = _install_factory(monkeypatch, _ClientFactory())
    result = await _delegate(parent, factory)

    assert result == NESTED_ANSWER

    system = _nested_system(factory)
    assert system == SUBAGENT_PROMPT
    assert "MEMOS" not in system
    assert INACTIVE_MEMO not in system
    assert ARCHIVED_MEMO not in system


# ===========================================================================
# DoD-5 — the delegation module performs no memos read of its own
# ===========================================================================


def _members_from(module, source_module: str) -> set[str]:
    """Names bound in ``module`` that came from ``source_module``.

    Catches both ``from app.db import memos`` (a module object) and
    ``from app.db.memos import list_for_author`` (a function whose
    ``__module__`` is the source).
    """
    found: set[str] = set()
    for name, value in vars(module).items():
        if isinstance(value, types.ModuleType):
            if value.__name__ == source_module:
                found.add(name)
        elif getattr(value, "__module__", None) == source_module:
            found.add(name)
    return found


# DoD-5 (`assistant-runtime.md` -> "the memo section is rendered once"):
# `subagent_delegation.py` reaches no memo data by any path of its own -- it
# imports no memo data-access module and binds no symbol defined by one.
def test_delegation_module_imports_no_memo_data_access__DoD5():
    assert _members_from(subagent_delegation, "app.db.memos") == set()
    assert not hasattr(subagent_delegation, "render_memos_section")


# DoD-5: and behaviourally -- a whole delegation, with a section carried,
# performs ZERO memo reads. The read counter wraps `db/memos.list_for_author`
# (the one module object every importer shares) and is installed AFTER the
# parent's own composition, so the only reads it could see are the delegation's.
# The positive control proves the counter works: composing a turn prompt counts
# one read.
async def test_delegation_performs_zero_memo_reads__DoD5(db: DbConfig, monkeypatch):
    user, book, server, chat = await _seed_world()
    await _seed_memo(book.id, user.id, MEMO_ONE, 1)

    composed = await _compose_parent(chat, server)
    assert composed.memos_section is not None

    real_list_for_author = memos_db.list_for_author
    calls: list[tuple] = []

    async def counting_list_for_author(*args, **kwargs):
        calls.append((args, kwargs))
        return await real_list_for_author(*args, **kwargs)

    monkeypatch.setattr(memos_db, "list_for_author", counting_list_for_author)

    factory = _install_factory(monkeypatch, _ClientFactory())
    await _delegate(_parent_turn(server, composed.memos_section), factory)

    assert calls == []
    # ...and the carried section still reached the child, so the zero is not the
    # zero of a delegation that never happened.
    assert MEMO_ONE in _nested_system(factory)

    # Positive control for the counter itself.
    await _compose_parent(chat, server)
    assert len(calls) == 1


# ===========================================================================
# DoD-6 — parent and child see an identical set within one turn
# ===========================================================================


# DoD-6 (US-132.AC-2): a memo created BETWEEN the parent's composition and the
# delegated call appears in neither prompt -- parent and child see one identical
# set per turn. The mid-turn row is written through the `db/` layer at exactly
# that point; the positive control (a fresh composition afterwards DOES carry it)
# proves the row is real and would have been picked up by a second read.
async def test_a_mid_turn_memo_reaches_neither_parent_nor_child__DoD6(
    db: DbConfig, monkeypatch
):
    user, book, server, chat = await _seed_world()
    await _seed_memo(book.id, user.id, MEMO_ONE, 1)
    await _seed_memo(book.id, user.id, MEMO_TWO, 2)

    composed = await _compose_parent(chat, server)
    assert composed.memos_section is not None

    # ...mid-turn, `create_memo`'s effect: a third active memo appears.
    await _seed_memo(book.id, user.id, MID_TURN_MEMO, 3)

    factory = _install_factory(monkeypatch, _ClientFactory())
    await _delegate(_parent_turn(server, composed.memos_section), factory)

    system = _nested_system(factory)

    # The child carries the parent's set, whole and unchanged.
    assert MEMO_ONE in system
    assert MEMO_TWO in system
    assert system == _expected_child(SUBAGENT_PROMPT, composed.memos_section)

    # The mid-turn row is in neither.
    assert MID_TURN_MEMO not in system
    assert MID_TURN_MEMO not in composed.system
    assert MID_TURN_MEMO not in composed.memos_section

    # Positive control: the row exists and a LATER turn does see it.
    later = await _compose_parent(chat, server)
    assert later.memos_section is not None
    assert MID_TURN_MEMO in later.memos_section


# ===========================================================================
# DoD-7 — delegation failure still returns a short error string, never raises
# ===========================================================================


# DoD-7 (`assistant-runtime.md` -> delegation failures): a failing nested call
# returns a short error string to the parent rather than raising -- with a memo
# section present and absent alike.
@pytest.mark.parametrize(
    "exc",
    [LLMError("upstream 500"), RuntimeError("max_loops exhausted")],
    ids=["llm_error", "runtime_error"],
)
@pytest.mark.parametrize("with_memos", [True, False], ids=["with_memos", "no_memos"])
async def test_delegation_failure_returns_an_error_string__DoD7(
    db: DbConfig, monkeypatch, exc, with_memos: bool
):
    user, book, server, chat = await _seed_world()
    if with_memos:
        await _seed_memo(book.id, user.id, MEMO_ONE, 1)

    composed = await _compose_parent(chat, server)
    if with_memos:
        assert composed.memos_section is not None
    else:
        assert composed.memos_section is None

    factory = _install_factory(monkeypatch, _ClientFactory(exc=exc))

    # No pytest.raises: a raising tool would abort the whole parent loop.
    result = await _delegate(_parent_turn(server, composed.memos_section), factory)

    assert isinstance(result, str)
    assert result.strip() != ""
    assert result != NESTED_ANSWER
