"""The four codex LISTING tools and their excerpt helper (feature 025, ultra track).

Bound to the frozen skeleton (`docs/plans/025.codex-listing-tools/status.md` ->
`## Skeleton`), in ``app.services.codex_tools``::

    def _excerpt(text: str, limit: int = 60) -> str
    class CodexListEntriesArgs(BaseModel)     # zero fields
    class CodexListCharactersArgs(BaseModel)  # zero fields
    class CodexListLocationsArgs(BaseModel)   # zero fields
    class CodexListFactsArgs(BaseModel)       # zero fields
    async def codex_list_entries(context: "ToolContext") -> str
    async def codex_list_characters(context: "ToolContext") -> str
    async def codex_list_locations(context: "ToolContext") -> str
    async def codex_list_facts(context: "ToolContext") -> str
    def bind_codex_list_*(context: "ToolContext") -> Callable[..., object]

Covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5 and DoD-11 of `plan.md`. Nothing else:
the plan's `## Test plan` -> "Not tested (deliberate)" list is binding.

Expected values come from the SPEC ONLY -- `plan.md` -> Interface ("Render
contract, all four tools", the `_excerpt` rule, the `list_by_book` call) and
Definition of done, plus `context.md` -> "Shared vocabulary" (kind stays `fact`,
the author's word is "lore"; "short form" is id + name, or id + a 60-character
body excerpt, never the full body).

Where the plan pins a LITERAL it is asserted exactly -- the ``entry_id=<id> | …``
row shape, the ``Codex error: `` prefix, the single ``…`` character. Where the
plan pins only a CONTRACT (the header "names what was listed and states the
count"; the empty listing is "a plain sentence") the contract is asserted and no
wording is invented.

Rows are seeded through the ``db/`` layer against the real ``db`` fixture, the
way `tests/services/test_codex_tools.py` does. ``asyncio_mode = "auto"``.
"""

import pytest

from app.db import books, codex_entries, users
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.user import User, UserRole
from app.services import codex_tools
from app.services.tools import TOOL_REGISTRY, ToolContext

# ---------------------------------------------------------------------------
# Seeding helpers (rows built through the db layer).
# ---------------------------------------------------------------------------


async def _seed_user(username: str = "author") -> User:
    return await users.create(User(username=username, role=UserRole.author))


async def _seed_book(owner_id: int, *, title: str = "A Book") -> Book:
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


async def _seed_entry(
    book_id: int,
    author_id: int,
    kind: CodexKind = CodexKind.character,
    *,
    name: str | None = None,
    body: str = "entry body",
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


# ---------------------------------------------------------------------------
# The four tools, and what each of them is specified to list.
# ---------------------------------------------------------------------------

# `plan.md` -> Interface: `codex_list_entries` passes `kind=None`; the other three
# pass their CodexKind member.
PER_KIND_TOOLS = (
    (codex_tools.codex_list_characters, CodexKind.character),
    (codex_tools.codex_list_locations, CodexKind.location),
    (codex_tools.codex_list_facts, CodexKind.fact),
)

ALL_TOOLS = (
    codex_tools.codex_list_entries,
    codex_tools.codex_list_characters,
    codex_tools.codex_list_locations,
    codex_tools.codex_list_facts,
)

# The vocabulary a header may legitimately use for each kind (`context.md` ->
# "Shared vocabulary": the enum value stays `fact`, while the author's word for an
# unnamed fact entry is "lore").
KIND_WORDS: dict[CodexKind, tuple[str, ...]] = {
    CodexKind.character: ("character",),
    CodexKind.location: ("location",),
    CodexKind.fact: ("fact", "lore"),
}

# A fixture size larger than any search-style limit this module carries, so DoD-2's
# "no cap" clause has real bite (`plan.md` -> "No cap, no pagination").
_SEARCH_LIMITS = [
    value
    for value in (
        getattr(codex_tools, "DEFAULT_SEARCH_LIMIT", 0),
        getattr(codex_tools, "MAX_SEARCH_LIMIT", 0),
    )
    if isinstance(value, int)
]
NO_CAP_COUNT = max([*_SEARCH_LIMITS, 25]) + 5


# ---------------------------------------------------------------------------
# Render helpers -- the contract, never a wording.
# ---------------------------------------------------------------------------


def _row(entry_id: int, tail: str) -> str:
    """The pinned row shape: ``entry_id=<id> | <name-or-excerpt>``."""
    return f"entry_id={entry_id} | {tail}"


def _lines(result: str) -> list[str]:
    return [line for line in result.splitlines() if line.strip() != ""]


def _header(result: str) -> str:
    """Render contract clause 1: the header is the FIRST line, and is not a row."""
    lines = _lines(result)
    assert lines, "the listing rendered nothing at all"
    header = lines[0]
    assert "entry_id=" not in header, f"the first line is an entry row, not a header: {header!r}"
    return header


def _entry_rows(result: str) -> list[str]:
    return [line for line in _lines(result) if "entry_id=" in line]


def _assert_header_states_count(result: str, count: int) -> None:
    """Clause 1: the header states the count of what was listed."""
    header = _header(result)
    assert str(count) in header, f"header does not state the count {count}: {header!r}"


def _expected_excerpt(text: str, limit: int = 60) -> str:
    """The spec's excerpt rule, transcribed -- NOT a call into the code under test.

    `plan.md` -> Interface: "Collapses whitespace runs to a single space, trims,
    takes the first `limit` characters, appends `…` only when the collapsed text
    was longer than `limit`."
    """
    collapsed = " ".join(text.split())
    if len(collapsed) > limit:
        return collapsed[:limit] + "…"
    return collapsed


# ===========================================================================
# DoD-1 -- the excerpt helper
# ===========================================================================


# DoD-1: `_excerpt` collapses whitespace runs to a single space, trims, cuts to 60
# characters and appends `…` ONLY when the collapsed text exceeded 60 -- the
# boundary (exactly 60 vs 61), a whitespace-heavy input, and the empty input.
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # empty, and whitespace-only: nothing to excerpt, and no ellipsis.
        ("", ""),
        ("   \t\n  ", ""),
        # whitespace-heavy: runs collapse to ONE space and the ends are trimmed.
        ("  Halden   the\n\tguardian  ", "Halden the guardian"),
        # the cut is applied to the COLLAPSED text: 88 raw characters, 9 collapsed.
        ("word" + " " * 80 + "tail", "word tail"),
        # exactly 60 collapsed characters: returned whole, with NO ellipsis.
        ("A" * 60, "A" * 60),
        # 61: cut to the first 60 characters, then the single `…` character.
        ("A" * 61, "A" * 60 + "…"),
        # 61 collapsed characters, reached only after the whitespace collapses:
        # 30 + one space + 30 = 61, so exactly one character is lost to the cut.
        (
            "  " + "B" * 30 + "   \n " + "C" * 30 + "  ",
            "B" * 30 + " " + "C" * 29 + "…",
        ),
    ],
)
def test_excerpt_collapses_trims_and_cuts_at_sixty__DoD1(raw: str, expected: str):
    assert codex_tools._excerpt(raw) == expected


# DoD-1: the boundary stated as a property -- 60 keeps its whole text, 61 loses
# exactly one character to the ellipsis, and the marker is the single `…`, never
# three dots.
def test_excerpt_boundary_is_sixty_and_marker_is_one_character__DoD1():
    at_limit = codex_tools._excerpt("A" * 60)
    over_limit = codex_tools._excerpt("A" * 61)

    assert len(at_limit) == 60
    assert not at_limit.endswith("…")
    assert over_limit.endswith("…")
    assert "..." not in over_limit
    assert len(over_limit.rstrip("…")) == 60


# ===========================================================================
# DoD-2 -- kind filtering, archived exclusion, order pass-through, no cap
# ===========================================================================


# DoD-2: each per-kind tool returns ONLY its own kind and excludes the other two,
# while `codex_list_entries` returns all three kinds.
async def test_each_tool_lists_only_its_own_kind__DoD2(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)

    seeded: dict[CodexKind, CodexEntry] = {
        CodexKind.character: await _seed_entry(
            book.id, user.id, CodexKind.character, name="Halden", body="a guardian"
        ),
        CodexKind.location: await _seed_entry(
            book.id, user.id, CodexKind.location, name="Northgate", body="a keep"
        ),
        CodexKind.fact: await _seed_entry(
            book.id, user.id, CodexKind.fact, name=None, body="the north never thaws"
        ),
    }

    for tool, kind in PER_KIND_TOOLS:
        result = await tool(ToolContext(book_id=book.id))

        assert f"entry_id={seeded[kind].id} " in result
        for other_kind, other in seeded.items():
            if other_kind is kind:
                continue
            assert f"entry_id={other.id} " not in result
        _assert_header_states_count(result, 1)

    # The unfiltered tool lists all three.
    everything = await codex_tools.codex_list_entries(ToolContext(book_id=book.id))
    for entry in seeded.values():
        assert f"entry_id={entry.id} " in everything
    _assert_header_states_count(everything, 3)


# DoD-2: archived entries are excluded from all four tools -- an archived sibling of
# each kind never reaches the model, while its live sibling still does.
async def test_archived_entries_are_excluded_from_all_four__DoD2(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)

    live: list[CodexEntry] = []
    archived: list[CodexEntry] = []
    for index, kind in enumerate(
        (CodexKind.character, CodexKind.location, CodexKind.fact)
    ):
        live.append(
            await _seed_entry(
                book.id,
                user.id,
                kind,
                name=None if kind is CodexKind.fact else f"Live{index}",
                body=f"LIVE_BODY_{index}",
            )
        )
        archived.append(
            await _seed_entry(
                book.id,
                user.id,
                kind,
                name=None if kind is CodexKind.fact else f"Retired{index}",
                body=f"ARCHIVED_BODY_{index}",
                archived=True,
            )
        )

    for tool in ALL_TOOLS:
        result = await tool(ToolContext(book_id=book.id))
        for entry in archived:
            assert f"entry_id={entry.id} " not in result
            if entry.name is not None:
                assert entry.name not in result

    # The live siblings are all present in the unfiltered listing -- so the
    # exclusion above is the archived rule, not an empty listing.
    everything = await codex_tools.codex_list_entries(ToolContext(book_id=book.id))
    for entry in live:
        assert f"entry_id={entry.id} " in everything
    _assert_header_states_count(everything, len(live))


# DoD-2: the rendered order is `list_by_book`'s own order -- the tools impose none.
# The expectation is taken from what `list_by_book` itself returns for exactly the
# call the Interface pins, never from a sort invented here.
async def test_entry_order_is_list_by_books_own_order__DoD2(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)

    # Seeded in an order that is neither alphabetical nor reverse-alphabetical.
    for name in ("Mira", "Ashen", "Zorah", "Corvin", "Beren"):
        await _seed_entry(book.id, user.id, CodexKind.character, name=name, body="b")

    expected = await codex_entries.list_by_book(
        book.id, kind=None, include_archived=False
    )
    assert len(expected) == 5

    result = await codex_tools.codex_list_entries(ToolContext(book_id=book.id))

    positions = [result.index(f"entry_id={entry.id} ") for entry in expected]
    assert positions == sorted(positions), (
        "the rendered order differs from the order list_by_book returned"
    )


# DoD-2: there is no cap -- a fixture larger than any search-style limit this
# module carries is listed in full (`plan.md`: "No cap, no pagination").
async def test_listing_has_no_cap__DoD2(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)

    entries = [
        await _seed_entry(
            book.id, user.id, CodexKind.character, name=f"Char{index:03d}", body="b"
        )
        for index in range(NO_CAP_COUNT)
    ]

    for tool in (codex_tools.codex_list_entries, codex_tools.codex_list_characters):
        result = await tool(ToolContext(book_id=book.id))

        for entry in entries:
            assert f"entry_id={entry.id} " in result
        assert len(_entry_rows(result)) == NO_CAP_COUNT
        _assert_header_states_count(result, NO_CAP_COUNT)


# ===========================================================================
# DoD-3 -- the render contract
# ===========================================================================


# DoD-3: a NAMED entry renders as `entry_id=<id> | <name>`, an UNNAMED entry (a
# fact, whose `name` is None by design) as `entry_id=<id> | <excerpt>`, the header
# names what was listed and states the count, and the full body never appears.
async def test_render_contract_named_unnamed_header_and_no_body__DoD3(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)

    long_body = (
        "The   guardian of the northern gate, sworn in the year of the long winter, "
        "and never once relieved of the watch."
    )
    named = await _seed_entry(
        book.id, user.id, CodexKind.character, name="Halden", body=long_body
    )
    unnamed = await _seed_entry(
        book.id, user.id, CodexKind.fact, name=None, body=long_body
    )

    result = await codex_tools.codex_list_entries(ToolContext(book_id=book.id))

    # Clause 2, named: id and NAME, in the pinned shape.
    assert _row(named.id, "Halden") in result
    # Clause 2, unnamed: id and the 60-character EXCERPT of the body.
    excerpt = _expected_excerpt(long_body)
    assert excerpt.endswith("…"), "the fixture body must be long enough to be cut"
    assert _row(unnamed.id, excerpt) in result

    # Clause 1: header first, naming what was listed and stating the count.
    header = _header(result)
    assert any(word in header.lower() for word in ("codex", "entr")), (
        f"the header does not name what was listed: {header!r}"
    )
    _assert_header_states_count(result, 2)
    assert len(_entry_rows(result)) == 2

    # "Short form": the FULL body never reaches the model -- for either entry.
    assert long_body not in result
    assert "never once relieved of the watch" not in result


# DoD-3: each per-kind listing names its own kind in the header and renders its
# entries in the same pinned row shape.
@pytest.mark.parametrize(
    ("tool", "kind"), PER_KIND_TOOLS, ids=["characters", "locations", "facts"]
)
async def test_per_kind_header_names_its_kind_and_rows_keep_the_shape__DoD3(
    db: DbConfig, tool, kind: CodexKind
):
    user = await _seed_user()
    book = await _seed_book(user.id)

    body = "A long body that the short form must never carry across to the model in full."
    named = None if kind is CodexKind.fact else "Subject One"
    entry = await _seed_entry(book.id, user.id, kind, name=named, body=body)

    result = await tool(ToolContext(book_id=book.id))

    header = _header(result)
    assert any(word in header.lower() for word in KIND_WORDS[kind]), (
        f"the header does not name the {kind.value} listing: {header!r}"
    )
    _assert_header_states_count(result, 1)

    tail = named if named is not None else _expected_excerpt(body)
    assert _row(entry.id, tail) in result
    assert body not in result


# ===========================================================================
# DoD-4 -- the empty listing
# ===========================================================================


def _assert_plain_empty_sentence(result: str) -> None:
    """DoD-4: a plain sentence -- not empty, not a bare header, not an error."""
    assert isinstance(result, str)
    assert result.strip() != ""
    # Not an error string (`plan.md`: ordinary "nothing found" is deliberately
    # neither of the module's two error categories).
    assert not result.startswith("Codex error: ")
    assert "Codex error" not in result
    # Not a listing: no rows at all.
    assert "entry_id=" not in result
    # A sentence, not a bare header: several words, ending in a full stop.
    assert len(result.split()) >= 3, f"not a sentence: {result!r}"
    assert result.strip().endswith("."), f"not a sentence: {result!r}"


# DoD-4: with nothing to list, every tool returns the plain "no entries of this
# kind yet" sentence -- never an empty string, never a bare header, never
# `Codex error:`-prefixed.
async def test_empty_book_renders_a_plain_sentence_from_every_tool__DoD4(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)

    for tool in ALL_TOOLS:
        _assert_plain_empty_sentence(await tool(ToolContext(book_id=book.id)))


# DoD-4: a kind with no entries is empty even when the book's OTHER kinds are
# populated -- and the sentence leaks none of them.
async def test_empty_kind_in_a_populated_book__DoD4(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    character = await _seed_entry(
        book.id, user.id, CodexKind.character, name="Halden", body="OTHER_KIND_BODY"
    )

    for tool, kind in PER_KIND_TOOLS:
        if kind is CodexKind.character:
            continue
        result = await tool(ToolContext(book_id=book.id))

        _assert_plain_empty_sentence(result)
        assert "Halden" not in result
        assert "OTHER_KIND_BODY" not in result
        assert str(character.id) not in result


# DoD-4: a book whose only entries are ARCHIVED lists as empty -- the same plain
# sentence, not an error and not a header with nothing under it.
async def test_only_archived_entries_render_the_empty_sentence__DoD4(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    await _seed_entry(
        book.id,
        user.id,
        CodexKind.character,
        name="Retired",
        body="ARCHIVED_ONLY_BODY",
        archived=True,
    )

    for tool in ALL_TOOLS:
        result = await tool(ToolContext(book_id=book.id))

        _assert_plain_empty_sentence(result)
        assert "Retired" not in result
        assert "ARCHIVED_ONLY_BODY" not in result


# ===========================================================================
# DoD-5 -- the failure path never raises
# ===========================================================================


# DoD-5: any failure of the underlying listing returns a string beginning
# `Codex error: ` -- no listing tool raises. A raising tool would abort the whole
# assistant turn (`context.md` -> "A tool refusal is a string the model reads").
@pytest.mark.parametrize(
    "tool", ALL_TOOLS, ids=["entries", "characters", "locations", "facts"]
)
@pytest.mark.parametrize(
    "failure", [RuntimeError("boom"), ValueError("bad state")], ids=["runtime", "value"]
)
async def test_failure_returns_a_codex_error_string_and_never_raises__DoD5(
    db: DbConfig, monkeypatch, tool, failure: Exception
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    await _seed_entry(book.id, user.id, CodexKind.character, name="Halden", body="b")

    async def _exploding_list_by_book(book_id, kind=None, include_archived=False):
        raise failure

    monkeypatch.setattr(codex_entries, "list_by_book", _exploding_list_by_book)

    # No exception escapes.
    result = await tool(ToolContext(book_id=book.id))

    assert isinstance(result, str)
    assert result.startswith("Codex error: "), result
    # The prefix is not the whole answer.
    assert result[len("Codex error: ") :].strip() != ""


# ===========================================================================
# DoD-11 -- "lore" is the description's word; `fact` is still the filter
# ===========================================================================


# DoD-11 (`context.md` -> "Shared vocabulary"): `codex_list_facts`'s registered
# description contains the author's word "lore", while the kind it actually filters
# on stays `fact` -- a fact entry is listed, a character and a location are not.
async def test_list_facts_says_lore_but_filters_fact__DoD11(db: DbConfig):
    entry = next(
        (tool for tool in TOOL_REGISTRY if tool.name == "codex_list_facts"), None
    )
    assert entry is not None, "codex_list_facts is not registered"
    assert "lore" in entry.description.lower(), entry.description

    user = await _seed_user()
    book = await _seed_book(user.id)
    fact = await _seed_entry(
        book.id, user.id, CodexKind.fact, name=None, body="the north never thaws"
    )
    character = await _seed_entry(
        book.id, user.id, CodexKind.character, name="Halden", body="a guardian"
    )
    location = await _seed_entry(
        book.id, user.id, CodexKind.location, name="Northgate", body="a keep"
    )

    result = await codex_tools.codex_list_facts(ToolContext(book_id=book.id))

    # The enum value is untouched -- `fact` is what the data still carries.
    assert fact.kind is CodexKind.fact
    assert f"entry_id={fact.id} " in result
    assert f"entry_id={character.id} " not in result
    assert f"entry_id={location.id} " not in result
