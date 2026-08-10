"""Tests for the `create_codex_entry` assistant tool (fast feature 007).

Bound to the frozen skeleton (`docs/plans/fast/007.codex-create-from-chat/status.md`
-> `## Skeleton`):

    app.services.codex_tools:
        MAX_CODEX_CREATES_PER_TURN: int
        class CreateCodexEntryArgs(BaseModel) { kind: CodexKind;
                                                name: str | None = None;
                                                body: str }
        async def create_codex_entry(context, kind: CodexKind, body: str,
                                     name: str | None = None) -> str
        def bind_create_codex_entry(context) -> Callable[..., object]

    app.services.tools:
        ToolContext.codex_creates_this_turn: int = 0
        TOOL_REGISTRY entry `create_codex_entry` (with a binder)
        resolve_tools / build_tool_bindings   (unchanged)

    app.db.mode_tools:
        DEFAULT_MODE_TOOL_NAMES: dict[str, tuple[str, ...]]   (unchanged shape)

Expected values come from the SPEC ONLY -- `plan.md` -> Interface intent +
Definition of done (DoD-1..DoD-8), `context.md`, and the product rule DoD-2 cites
(US-078.AC-2: a fact has no name) -- never from implementation internals.

Test approach (the `test_codex_tools.py` / `test_codex_canvas_tools.py` house
style): rows are seeded through the `app.db` layer against the real throwaway
temp-SQLite `db` fixture, `BookAccess` is built directly as the frozen dataclass
and `ToolContext` is constructed directly -- no HTTP, no network anywhere.
"No row was created" is always verified through the `db` layer, never through the
tool's own answer. `asyncio_mode = "auto"`.

Two properties shape almost every case below:

  * the tool is **book-scoped, not subject-scoped** (`plan.md` -> Decisions
    carried): running while the subject is a CHAPTER is the point of the feature,
    so the happy path (DoD-1) uses a chapter subject and no case ever relies on a
    codex subject being present;
  * the tool **never raises** (`context.md` -> "Every tool never raises"), so
    every failure clause asserts a returned STRING, never `pytest.raises`.
"""

import inspect

import pytest

from app.db import books, codex_entries, mode_tools, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.user import User, UserRole
from app.services import codex as codex_service
from app.services import codex_tools
from app.services import tools as tools_module
from app.services.assistant_runtime import ResolvedSubject
from app.services.authz import AccessRole, BookAccess
from app.services.codex_tools import CreateCodexEntryArgs
from app.services.tools import ToolContext

# ---------------------------------------------------------------------------
# Seeding helpers (rows built through the db layer).
# ---------------------------------------------------------------------------


async def _seed_user(username: str = "author") -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(
    owner_id: int,
    *,
    title: str = "A Book",
    collaboration_mode: CollaborationMode = CollaborationMode.free,
) -> Book:
    return await books.create(
        Book(
            title=title,
            description="d",
            owner_id=owner_id,
            collaboration_mode=collaboration_mode,
            visibility=Visibility.private,
            state=BookState.active,
            system_prompt="",
            active_notes="",
        )
    )


async def _seed_entry(
    book_id: int,
    author_id: int,
    kind: CodexKind = CodexKind.character,
    *,
    name: str | None = "Seeded",
    body: str = "seeded body",
    archived: bool = False,
) -> CodexEntry:
    """A CodexEntry inserted straight through the db layer (bypassing the tool)."""
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


def _access(
    book_id: int,
    user_id: int,
    *,
    role: AccessRole = AccessRole.owner,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
) -> BookAccess:
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=role,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=collaboration_mode,
    )


# The subject a chapter-writing turn carries -- NOT a codex subject. The tool is
# book-scoped, so this is the ordinary case, not an edge case.
CHAPTER_SUBJECT = ResolvedSubject(kind="chapter", mode_key="write-chapter")


def _ctx(
    book_id: int,
    user_id: int,
    *,
    subject=CHAPTER_SUBJECT,
    role: AccessRole = AccessRole.owner,
    collaboration_mode: CollaborationMode = CollaborationMode.free,
) -> ToolContext:
    return ToolContext(
        book_id=book_id,
        access=_access(
            book_id, user_id, role=role, collaboration_mode=collaboration_mode
        ),
        subject=subject,
    )


async def _rows(book_id: int) -> list[CodexEntry]:
    """Every row of the book, archived included -- read through the db layer."""
    return list(await codex_entries.list_by_book(book_id, include_archived=True))


def _assert_refusal(result: object) -> str:
    """A refusal is a non-empty STRING back -- never an exception."""
    assert isinstance(result, str)
    assert result.strip() != ""
    return result


# ---------------------------------------------------------------------------
# DoD-1 — a valid create persists one entry and returns a naming string
# ---------------------------------------------------------------------------


# DoD-1: creating with a valid kind/name/body persists exactly ONE CodexEntry in
# the TURN'S book carrying that kind, name and body, with `author_id` set to the
# acting user, and returns a string naming what was created (its kind, its name
# and its id). The subject here is a CHAPTER -- "create one while writing a
# chapter" is the whole feature (plan.md -> "Book-scoped, not subject-scoped").
async def test_create_persists_entry_and_names_it__DoD1(db: DbConfig):
    author = await _seed_user("alice")
    book = await _seed_book(author.id)
    other_book = await _seed_book(author.id, title="Elsewhere")

    result = await codex_tools.create_codex_entry(
        _ctx(book.id, author.id),
        kind=CodexKind.character,
        body="a ranger of the north",
        name="Aragorn",
    )

    rows = await _rows(book.id)
    assert len(rows) == 1
    entry = rows[0]
    assert entry.kind is CodexKind.character
    assert entry.name == "Aragorn"
    assert entry.body == "a ranger of the north"
    assert entry.author_id == author.id
    assert entry.book_id == book.id

    # The answer names the created entry: kind, name and id.
    _assert_refusal(result)  # (a non-empty string; the naming is asserted next)
    assert "Aragorn" in result
    assert str(entry.id) in result
    assert CodexKind.character.value in result.lower()

    # The turn's book is the only book written to.
    assert await _rows(other_book.id) == []


# DoD-1: the same holds for a `location`, and for a `fact` (whose name is
# omitted, US-078.AC-2) -- and with NO subject at all, since the tool is scoped by
# the context's book rather than by the turn's subject.
async def test_create_works_for_location_and_fact_without_a_subject__DoD1(
    db: DbConfig,
):
    author = await _seed_user("bob")
    book = await _seed_book(author.id)

    location_result = await codex_tools.create_codex_entry(
        _ctx(book.id, author.id, subject=None),
        kind=CodexKind.location,
        body="a hidden valley",
        name="Rivendell",
    )
    fact_result = await codex_tools.create_codex_entry(
        _ctx(book.id, author.id, subject=None),
        kind=CodexKind.fact,
        body="The Ring was forged in Mount Doom",
    )

    rows = await _rows(book.id)
    assert len(rows) == 2
    by_kind = {row.kind: row for row in rows}

    location = by_kind[CodexKind.location]
    assert location.name == "Rivendell"
    assert location.body == "a hidden valley"
    assert location.author_id == author.id
    assert "Rivendell" in location_result
    assert str(location.id) in location_result

    fact = by_kind[CodexKind.fact]
    assert fact.name is None
    assert fact.body == "The Ring was forged in Mount Doom"
    assert fact.author_id == author.id
    assert str(fact.id) in fact_result
    assert CodexKind.fact.value in fact_result.lower()


# ---------------------------------------------------------------------------
# DoD-2 — a fact with a name is refused (US-078.AC-2: a fact has no name)
# ---------------------------------------------------------------------------


# DoD-2 (US-078.AC-2 -- a fact has no name): supplying a NON-BLANK name with a
# `fact` is refused with a string and NO row is created.
@pytest.mark.parametrize("name", ["Not allowed", "  Padded Name  "])
async def test_fact_with_a_name_is_refused__DoD2_US078_AC2(db: DbConfig, name: str):
    author = await _seed_user("carol")
    book = await _seed_book(author.id)

    result = await codex_tools.create_codex_entry(
        _ctx(book.id, author.id),
        kind=CodexKind.fact,
        body="a fact that should not land",
        name=name,
    )

    _assert_refusal(result)
    assert await _rows(book.id) == []

    # The refusal is the NAME rule, not a blanket refusal of facts: the same fact
    # without a name is created.
    ok = await codex_tools.create_codex_entry(
        _ctx(book.id, author.id),
        kind=CodexKind.fact,
        body="a fact that should not land",
    )
    assert isinstance(ok, str)
    rows = await _rows(book.id)
    assert len(rows) == 1
    assert rows[0].name is None


# ---------------------------------------------------------------------------
# DoD-3 — a character / location with no name is refused
# ---------------------------------------------------------------------------


# DoD-3: a `character` or a `location` supplied with NO name -- absent, or blank
# (whitespace only counts as absent) -- is refused with a string and no row is
# created.
@pytest.mark.parametrize("kind", [CodexKind.character, CodexKind.location])
@pytest.mark.parametrize("name", [None, "", "   ", "\t", "\n", " \t\n "])
async def test_named_kind_without_a_name_is_refused__DoD3(
    db: DbConfig, kind: CodexKind, name: str | None
):
    author = await _seed_user("dave")
    book = await _seed_book(author.id)

    result = await codex_tools.create_codex_entry(
        _ctx(book.id, author.id),
        kind=kind,
        body="should not land",
        name=name,
    )

    _assert_refusal(result)
    assert await _rows(book.id) == []

    # The refusal is the missing name, not the kind: a real name is accepted.
    await codex_tools.create_codex_entry(
        _ctx(book.id, author.id),
        kind=kind,
        body="should not land",
        name="A Real Name",
    )
    assert len(await _rows(book.id)) == 1


# ---------------------------------------------------------------------------
# DoD-4 — the write-path refusals come back as strings, never as exceptions
# ---------------------------------------------------------------------------


# DoD-4 (proposal-mode half): a CO-AUTHOR in a `proposal`-mode book is refused
# with a string and no row is created -- the proposal mechanism (FEAT-010) is not
# built, and a raised CodexError would abort the turn instead of answering.
async def test_co_author_in_proposal_mode_refused_with_a_string__DoD4(db: DbConfig):
    owner = await _seed_user("owner")
    helper = await _seed_user("helper")
    book = await _seed_book(
        owner.id, collaboration_mode=CollaborationMode.proposal
    )

    result = await codex_tools.create_codex_entry(
        _ctx(
            book.id,
            helper.id,
            role=AccessRole.co_author,
            collaboration_mode=CollaborationMode.proposal,
        ),
        kind=CodexKind.character,
        body="should not land",
        name="Proposed",
    )

    _assert_refusal(result)
    assert await _rows(book.id) == []

    # The rule is the collaboration MODE, not the role: the same co-author in a
    # free-mode book does create.
    free_book = await _seed_book(owner.id, title="Free")
    await codex_tools.create_codex_entry(
        _ctx(
            free_book.id,
            helper.id,
            role=AccessRole.co_author,
            collaboration_mode=CollaborationMode.free,
        ),
        kind=CodexKind.character,
        body="lands",
        name="Allowed",
    )
    free_rows = await _rows(free_book.id)
    assert len(free_rows) == 1
    assert free_rows[0].author_id == helper.id


# DoD-4 (capability half): a caller who does not hold
# `Capability.edit_codex_entry` -- a reader, or a non-member -- is refused with a
# STRING, not an exception, and no row is created.
@pytest.mark.parametrize("role", [AccessRole.reader, AccessRole.none])
async def test_caller_without_edit_capability_refused_with_a_string__DoD4(
    db: DbConfig, role: AccessRole
):
    owner = await _seed_user("owner")
    outsider = await _seed_user("outsider")
    book = await _seed_book(owner.id)

    for kind, name in (
        (CodexKind.character, "Intruder"),
        (CodexKind.fact, None),
    ):
        result = await codex_tools.create_codex_entry(
            _ctx(book.id, outsider.id, role=role),
            kind=kind,
            body="should not land",
            name=name,
        )
        _assert_refusal(result)

    assert await _rows(book.id) == []


# ---------------------------------------------------------------------------
# DoD-5 — the duplicate-name backstop for character / location
# ---------------------------------------------------------------------------


# DoD-5: a `character` or `location` whose name already exists in the book FOR
# THAT KIND -- compared TRIMMED and CASE-INSENSITIVELY -- is refused with a string
# and no row is created.
@pytest.mark.parametrize("kind", [CodexKind.character, CodexKind.location])
@pytest.mark.parametrize(
    "attempted", ["Halden", "halden", "HALDEN", "  Halden  ", "\thalden\n"]
)
async def test_duplicate_name_refused_trimmed_and_case_insensitively__DoD5(
    db: DbConfig, kind: CodexKind, attempted: str
):
    author = await _seed_user("erin")
    book = await _seed_book(author.id)
    await _seed_entry(book.id, author.id, kind, name="Halden", body="the original")

    result = await codex_tools.create_codex_entry(
        _ctx(book.id, author.id),
        kind=kind,
        body="a second Halden",
        name=attempted,
    )

    _assert_refusal(result)
    rows = await _rows(book.id)
    assert len(rows) == 1
    assert rows[0].body == "the original"


# DoD-5: the duplicate rule counts ARCHIVED rows too -- recreating a name that
# exists but is hidden is refused.
async def test_duplicate_name_counts_archived_rows__DoD5(db: DbConfig):
    author = await _seed_user("frank")
    book = await _seed_book(author.id)
    await _seed_entry(
        book.id,
        author.id,
        CodexKind.character,
        name="Retired",
        body="put away",
        archived=True,
    )

    result = await codex_tools.create_codex_entry(
        _ctx(book.id, author.id),
        kind=CodexKind.character,
        body="a revival",
        name="  retired  ",
    )

    _assert_refusal(result)
    assert len(await _rows(book.id)) == 1


# DoD-5: the rule is scoped to THIS book and THIS kind, and matches the whole
# trimmed name -- a same-named entry in another book, a same name under another
# kind, and a merely-similar name are all created.
async def test_duplicate_rule_is_scoped_to_book_kind_and_whole_name__DoD5(
    db: DbConfig,
):
    author = await _seed_user("grace")
    book = await _seed_book(author.id)
    other_book = await _seed_book(author.id, title="Elsewhere")
    await _seed_entry(
        other_book.id, author.id, CodexKind.character, name="Halden", body="foreign"
    )
    await _seed_entry(
        book.id, author.id, CodexKind.location, name="Halden", body="a place"
    )

    # Another book's Halden does not block this book's; another KIND's does not
    # block a character.
    character = await codex_tools.create_codex_entry(
        _ctx(book.id, author.id),
        kind=CodexKind.character,
        body="the guardian",
        name="Halden",
    )
    assert isinstance(character, str)

    # A name that merely CONTAINS an existing one is not a duplicate (the needle
    # narrows the scan; only an exact trimmed match decides it).
    similar = await codex_tools.create_codex_entry(
        _ctx(book.id, author.id),
        kind=CodexKind.character,
        body="another guardian",
        name="Halden the Younger",
    )
    assert isinstance(similar, str)

    names = {(row.kind, row.name) for row in await _rows(book.id)}
    assert names == {
        (CodexKind.location, "Halden"),
        (CodexKind.character, "Halden"),
        (CodexKind.character, "Halden the Younger"),
    }
    assert len(await _rows(other_book.id)) == 1


# DoD-5: a `fact` is NEVER refused for duplication -- it has no name to compare
# (US-078.AC-2), so two facts with identical bodies both land.
async def test_fact_is_never_refused_for_duplication__DoD5(db: DbConfig):
    author = await _seed_user("heidi")
    book = await _seed_book(author.id)
    await _seed_entry(
        book.id, author.id, CodexKind.fact, name=None, body="The Ring was forged"
    )

    result = await codex_tools.create_codex_entry(
        _ctx(book.id, author.id),
        kind=CodexKind.fact,
        body="The Ring was forged",
    )

    assert isinstance(result, str)
    rows = await _rows(book.id)
    assert len(rows) == 2
    assert [row.kind for row in rows] == [CodexKind.fact, CodexKind.fact]


# ---------------------------------------------------------------------------
# DoD-6 — the per-turn creation cap, held on the ToolContext
# ---------------------------------------------------------------------------


# DoD-6: the cap is three creations per turn -- the 4th attempt on ONE
# ToolContext is refused with a string and creates no row, while a FRESH context
# (a new turn) starts the count at zero and creates again.
async def test_fourth_creation_in_one_turn_is_capped__DoD6(db: DbConfig):
    author = await _seed_user("ivan")
    book = await _seed_book(author.id)

    # The cap is 3 (plan.md -> "a per-turn creation cap of 3").
    assert codex_tools.MAX_CODEX_CREATES_PER_TURN == 3

    turn = _ctx(book.id, author.id)
    # A fresh context starts at zero.
    assert turn.codex_creates_this_turn == 0

    for index in range(codex_tools.MAX_CODEX_CREATES_PER_TURN):
        created = await codex_tools.create_codex_entry(
            turn,
            kind=CodexKind.character,
            body=f"body {index}",
            name=f"Character {index}",
        )
        assert isinstance(created, str)

    assert len(await _rows(book.id)) == codex_tools.MAX_CODEX_CREATES_PER_TURN

    # The 4th attempt on the SAME context is refused, and writes nothing --
    # neither this kind nor a fact, which no other backstop would refuse.
    for kind, name in (
        (CodexKind.character, "One Too Many"),
        (CodexKind.fact, None),
    ):
        capped = await codex_tools.create_codex_entry(
            turn, kind=kind, body="over the cap", name=name
        )
        _assert_refusal(capped)

    rows = await _rows(book.id)
    assert len(rows) == codex_tools.MAX_CODEX_CREATES_PER_TURN
    assert "One Too Many" not in {row.name for row in rows}

    # A NEW turn's context starts at zero again.
    fresh = _ctx(book.id, author.id)
    assert fresh.codex_creates_this_turn == 0
    allowed = await codex_tools.create_codex_entry(
        fresh,
        kind=CodexKind.character,
        body="a new turn",
        name="Next Turn",
    )
    assert isinstance(allowed, str)
    rows = await _rows(book.id)
    assert len(rows) == codex_tools.MAX_CODEX_CREATES_PER_TURN + 1
    assert "Next Turn" in {row.name for row in rows}


# DoD-6: the cap counts CREATIONS, not attempts -- refused attempts do not burn
# the budget, so a turn that fails twice can still create three entries.
async def test_refused_attempts_do_not_consume_the_cap__DoD6(db: DbConfig):
    author = await _seed_user("judy")
    book = await _seed_book(author.id)
    turn = _ctx(book.id, author.id)

    # Two refusals (a fact with a name, and a character with no name).
    _assert_refusal(
        await codex_tools.create_codex_entry(
            turn, kind=CodexKind.fact, body="b", name="Illegal"
        )
    )
    _assert_refusal(
        await codex_tools.create_codex_entry(
            turn, kind=CodexKind.character, body="b", name="   "
        )
    )
    assert await _rows(book.id) == []

    for index in range(codex_tools.MAX_CODEX_CREATES_PER_TURN):
        result = await codex_tools.create_codex_entry(
            turn, kind=CodexKind.fact, body=f"fact {index}"
        )
        assert isinstance(result, str)

    assert len(await _rows(book.id)) == codex_tools.MAX_CODEX_CREATES_PER_TURN


# ---------------------------------------------------------------------------
# DoD-7 — an exception escaping the create path becomes a string
# ---------------------------------------------------------------------------


# DoD-7 (`context.md` -> "Every tool never raises" -- a raising tool aborts the
# whole chat_with_tools loop): ANY exception escaping the create path comes back
# as a string result. The single write path (`codex_service.create_entry`, the
# boundary the tool delegates to) is made to raise; the tool must answer, not
# raise, and nothing may be written.
@pytest.mark.parametrize(
    "boom",
    [
        RuntimeError("the database went away"),
        ValueError("something unexpected"),
        OSError("disk is gone"),
    ],
)
async def test_exception_from_the_create_path_becomes_a_string__DoD7(
    db: DbConfig, monkeypatch, boom: Exception
):
    author = await _seed_user("ken")
    book = await _seed_book(author.id)

    async def _raise(*args, **kwargs):
        raise boom

    monkeypatch.setattr(codex_service, "create_entry", _raise)

    for kind, name in (
        (CodexKind.character, "Doomed"),
        (CodexKind.location, "Doomed Place"),
        (CodexKind.fact, None),
    ):
        result = await codex_tools.create_codex_entry(
            _ctx(book.id, author.id),
            kind=kind,
            body="should not land",
            name=name,
        )
        _assert_refusal(result)

    assert await _rows(book.id) == []


# ---------------------------------------------------------------------------
# DoD-8 — registry membership and the seeded per-mode defaults
# ---------------------------------------------------------------------------


# DoD-8 (registry half): `create_codex_entry` is present in TOOL_REGISTRY with a
# BINDER (never a plain callable), carries the new args schema and a non-empty
# description, resolves through `resolve_tools`, and binds through
# `build_tool_bindings` into a definition + callable pair whose free parameters
# are exactly the args schema's fields -- the invariant the `llm` client checks.
async def test_tool_is_registered_and_binds__DoD8(db: DbConfig):
    author = await _seed_user("lena")
    book = await _seed_book(author.id)

    registry = {t.name: t for t in tools_module.TOOL_REGISTRY}
    assert "create_codex_entry" in registry

    entry = registry["create_codex_entry"]
    assert entry.args_schema is CreateCodexEntryArgs
    assert isinstance(entry.description, str)
    assert entry.description.strip() != ""
    # A context-bound tool: a binder, not a bare callable.
    assert entry.binder is codex_tools.bind_create_codex_entry
    assert entry.callable is None

    selected = tools_module.resolve_tools(["create_codex_entry"])
    assert [t.name for t in selected] == ["create_codex_entry"]

    context = _ctx(book.id, author.id)
    definitions, callables = tools_module.build_tool_bindings(selected, context)

    assert {d["function"]["name"] for d in definitions} == set(callables.keys())
    assert set(callables.keys()) == {"create_codex_entry"}
    bound = callables["create_codex_entry"]
    assert set(inspect.signature(bound).parameters) == set(
        CreateCodexEntryArgs.model_fields
    )

    # The binding carries the turn's book: dispatched with only its schema
    # arguments, the bound callable writes into THIS book.
    await bound(kind=CodexKind.character, body="bound body", name="Bound")
    rows = await _rows(book.id)
    assert len(rows) == 1
    assert rows[0].name == "Bound"


# DoD-8 (seeded-defaults half): DEFAULT_MODE_TOOL_NAMES lists the tool for the
# four AUTHORING modes -- `edit-character`, `edit-location`, `edit-fact` and
# `write-chapter` -- and NOT for `close-chapter` (`context.md` -> D6: the least
# supervised turn in the system does not mint codex entries).
def test_default_mode_tool_names_cover_the_four_authoring_modes__DoD8():
    defaults = mode_tools.DEFAULT_MODE_TOOL_NAMES

    for mode_key in ("edit-character", "edit-location", "edit-fact", "write-chapter"):
        assert "create_codex_entry" in defaults[mode_key], mode_key

    assert "create_codex_entry" not in defaults["close-chapter"]
