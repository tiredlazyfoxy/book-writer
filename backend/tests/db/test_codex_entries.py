"""Tests for the widened db/codex_entries query surface (feature 013, step 001).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 001), in
`app.db.codex_entries` (existing `create` / `get_by_id` unchanged):
    async def list_by_book(
        book_id: int,
        kind: CodexKind | None = None,
        include_archived: bool = False,
        needle: str | None = None,
    ) -> list[CodexEntry]
    async def update(row: CodexEntry) -> CodexEntry

Expected values come from the step spec (001.codex-db-authz.md -> Interface
intent + Definition of done, plus 001.context.md), never from implementation
internals:
    - a `kind` filter returns only that kind, and never another book's rows
      (DoD-1);
    - archived rows are excluded by default and included only when explicitly
      asked (DoD-2);
    - the free-text needle matches case-insensitively as a substring of `name`
      OR of `body`, and a fact entry (null `name`) is still matched on its body
      (DoD-3);
    - an empty / absent needle returns the full filtered set (DoD-4);
    - ordering is deterministic and explicit: by `name` ascending with
      NULL-named rows LAST, then by `id` (DoD-5) -- SQLite's default sorts NULL
      first, so the order is asserted literally;
    - `update` persists every changed field and the returned row reflects the
      stored state (DoD-6).

Async tests use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an
initialized throwaway temp-SQLite engine. SQLite does not enforce FKs by
default, so entries need no parent book/user rows. No HTTP, no network.
"""

from datetime import datetime

from app.db import codex_entries
from app.db.engine import DbConfig
from app.models.codex_entry import CodexEntry, CodexKind


def _entry(
    book_id: int,
    kind: CodexKind,
    name: str | None,
    body: str,
    *,
    archived: bool = False,
    author_id: int = 1,
) -> CodexEntry:
    """A CodexEntry with the step's required non-null fields populated."""
    return CodexEntry(
        book_id=book_id,
        kind=kind,
        name=name,
        body=body,
        archived=archived,
        author_id=author_id,
    )


# ---------------------------------------------------------------------------
# DoD-1 — the `kind` filter
# ---------------------------------------------------------------------------


# DoD-1 (UC-071 / US-080.AC-1): list_by_book filtered by a kind returns only
# entries of that kind, and never entries of another kind or of another book.
async def test_list_by_book_filters_by_kind__DoD1_US080_AC1(db: DbConfig):
    book = 100
    other_book = 200
    await codex_entries.create(
        _entry(book, CodexKind.character, "Aragorn", "a ranger")
    )
    await codex_entries.create(
        _entry(book, CodexKind.character, "Boromir", "a captain")
    )
    await codex_entries.create(
        _entry(book, CodexKind.location, "Rivendell", "a valley")
    )
    await codex_entries.create(_entry(book, CodexKind.fact, None, "a recorded fact"))
    # Same kind, different book -- must never appear.
    await codex_entries.create(
        _entry(other_book, CodexKind.character, "Stranger", "another book's character")
    )

    listed = await codex_entries.list_by_book(book, kind=CodexKind.character)

    assert [e.name for e in listed] == ["Aragorn", "Boromir"]
    assert {e.kind for e in listed} == {CodexKind.character}
    assert {e.book_id for e in listed} == {book}


# DoD-1: each of the three kinds selects exactly its own rows.
async def test_list_by_book_kind_filter_selects_each_kind__DoD1_US080_AC1(
    db: DbConfig,
):
    book = 101
    await codex_entries.create(_entry(book, CodexKind.character, "Char", "c body"))
    await codex_entries.create(_entry(book, CodexKind.location, "Loc", "l body"))
    await codex_entries.create(_entry(book, CodexKind.fact, None, "f body"))

    characters = await codex_entries.list_by_book(book, kind=CodexKind.character)
    locations = await codex_entries.list_by_book(book, kind=CodexKind.location)
    facts = await codex_entries.list_by_book(book, kind=CodexKind.fact)

    assert [e.body for e in characters] == ["c body"]
    assert [e.body for e in locations] == ["l body"]
    assert [e.body for e in facts] == ["f body"]


# ---------------------------------------------------------------------------
# DoD-2 — archived excluded by default, included on request
# ---------------------------------------------------------------------------


# DoD-2 (domain-codex.md -- archived, never deleted): list_by_book excludes
# archived entries by default and includes them when explicitly asked.
async def test_list_by_book_excludes_archived_by_default__DoD2(db: DbConfig):
    book = 300
    await codex_entries.create(
        _entry(book, CodexKind.character, "Active", "still in play")
    )
    await codex_entries.create(
        _entry(book, CodexKind.character, "Retired", "put away", archived=True)
    )

    default_listed = await codex_entries.list_by_book(book)
    assert [e.name for e in default_listed] == ["Active"]

    with_archived = await codex_entries.list_by_book(book, include_archived=True)
    assert [e.name for e in with_archived] == ["Active", "Retired"]


# DoD-2: the archived filter composes with the kind filter -- an archived row of
# the requested kind stays hidden by default and appears when asked for.
async def test_archived_filter_composes_with_kind__DoD2(db: DbConfig):
    book = 301
    await codex_entries.create(
        _entry(book, CodexKind.location, "Open Gate", "reachable")
    )
    await codex_entries.create(
        _entry(book, CodexKind.location, "Ruined Keep", "gone", archived=True)
    )

    default_listed = await codex_entries.list_by_book(book, kind=CodexKind.location)
    assert [e.name for e in default_listed] == ["Open Gate"]

    with_archived = await codex_entries.list_by_book(
        book, kind=CodexKind.location, include_archived=True
    )
    assert [e.name for e in with_archived] == ["Open Gate", "Ruined Keep"]


# ---------------------------------------------------------------------------
# DoD-3 — the free-text needle (case-insensitive, name OR body)
# ---------------------------------------------------------------------------


async def _seed_needle_book(book: int) -> None:
    """Three entries: a named character, a named location, a null-named fact."""
    await codex_entries.create(
        _entry(book, CodexKind.character, "Aragorn", "a ranger of the north")
    )
    await codex_entries.create(
        _entry(book, CodexKind.location, "Rivendell", "a hidden valley refuge")
    )
    await codex_entries.create(
        _entry(book, CodexKind.fact, None, "The Ring was forged in Mount Doom")
    )


# DoD-3 (US-080.AC-1): the needle matches as a substring of `name`, and does so
# case-insensitively (a lowercase needle finds a capitalised name and vice
# versa).
async def test_needle_matches_name_case_insensitively__DoD3_US080_AC1(db: DbConfig):
    book = 400
    await _seed_needle_book(book)

    lowered = await codex_entries.list_by_book(book, needle="ragorn")
    assert [e.name for e in lowered] == ["Aragorn"]

    uppered = await codex_entries.list_by_book(book, needle="ARAGORN")
    assert [e.name for e in uppered] == ["Aragorn"]


# DoD-3 (US-080.AC-1): the needle matches as a substring of `body`, again
# case-insensitively.
async def test_needle_matches_body_case_insensitively__DoD3_US080_AC1(db: DbConfig):
    book = 401
    await _seed_needle_book(book)

    matched = await codex_entries.list_by_book(book, needle="HIDDEN valley")
    assert [e.name for e in matched] == ["Rivendell"]


# DoD-3 (US-080.AC-1): a fact entry (null `name`) is still matched on its body
# alone -- a null name must not suppress the row.
async def test_needle_matches_null_named_fact_on_body__DoD3_US080_AC1(db: DbConfig):
    book = 402
    await _seed_needle_book(book)

    matched = await codex_entries.list_by_book(book, needle="mount doom")

    assert len(matched) == 1
    assert matched[0].name is None
    assert matched[0].kind is CodexKind.fact
    assert matched[0].body == "The Ring was forged in Mount Doom"


# DoD-3 (US-080.AC-1): a needle matching neither `name` nor `body` of any row
# returns nothing.
async def test_needle_with_no_match_returns_empty__DoD3_US080_AC1(db: DbConfig):
    book = 403
    await _seed_needle_book(book)

    assert await codex_entries.list_by_book(book, needle="zzz-nothing-here") == []


# ---------------------------------------------------------------------------
# DoD-4 — an empty / absent needle does not filter
# ---------------------------------------------------------------------------


# DoD-4 (US-080.AC-1): an absent (None) or empty ("") needle returns the full
# filtered set -- it is not treated as a match on the empty string only.
async def test_empty_or_absent_needle_returns_full_set__DoD4_US080_AC1(db: DbConfig):
    book = 500
    await _seed_needle_book(book)

    absent = await codex_entries.list_by_book(book)
    assert len(absent) == 3

    explicit_none = await codex_entries.list_by_book(book, needle=None)
    assert len(explicit_none) == 3

    empty = await codex_entries.list_by_book(book, needle="")
    assert len(empty) == 3
    assert {e.body for e in empty} == {
        "a ranger of the north",
        "a hidden valley refuge",
        "The Ring was forged in Mount Doom",
    }


# DoD-4 (US-080.AC-1): an empty needle still respects the other filters -- it
# widens nothing, it merely does not narrow.
async def test_empty_needle_still_respects_kind_and_archived__DoD4_US080_AC1(
    db: DbConfig,
):
    book = 501
    await codex_entries.create(_entry(book, CodexKind.character, "Kept", "kept body"))
    await codex_entries.create(
        _entry(book, CodexKind.character, "Hidden", "hidden body", archived=True)
    )
    await codex_entries.create(_entry(book, CodexKind.location, "Elsewhere", "e body"))

    listed = await codex_entries.list_by_book(
        book, kind=CodexKind.character, needle=""
    )

    assert [e.name for e in listed] == ["Kept"]


# ---------------------------------------------------------------------------
# DoD-5 — deterministic ordering: name ascending, NULL-named rows LAST, then id
# ---------------------------------------------------------------------------


# DoD-5 (US-080.AC-1): two calls with the same arguments return rows in the same
# order, and that order is by `name` ascending with null-named rows LAST, then
# by `id`. SQLite sorts NULL first by default, so the fixture includes two
# null-named fact entries and the expected order is asserted literally.
async def test_ordering_is_name_then_id_with_nulls_last__DoD5_US080_AC1(
    db: DbConfig,
):
    book = 600
    # Inserted deliberately out of the expected order.
    fact_first = await codex_entries.create(
        _entry(book, CodexKind.fact, None, "first fact")
    )
    beta = await codex_entries.create(
        _entry(book, CodexKind.character, "beta", "beta body")
    )
    alpha_one = await codex_entries.create(
        _entry(book, CodexKind.character, "alpha", "alpha body one")
    )
    alpha_two = await codex_entries.create(
        _entry(book, CodexKind.character, "alpha", "alpha body two")
    )
    fact_second = await codex_entries.create(
        _entry(book, CodexKind.fact, None, "second fact")
    )

    # Same-name rows tie-break on id ascending; so do the null-named rows.
    alpha_low, alpha_high = sorted([alpha_one.id, alpha_two.id])
    fact_low, fact_high = sorted([fact_first.id, fact_second.id])
    expected_ids = [alpha_low, alpha_high, beta.id, fact_low, fact_high]

    listed = await codex_entries.list_by_book(book)
    assert [e.id for e in listed] == expected_ids
    # Names read in the same order: alpha, alpha, beta, then the null-named
    # rows last.
    assert [e.name for e in listed] == ["alpha", "alpha", "beta", None, None]

    # Determinism: the identical call yields the identical order.
    again = await codex_entries.list_by_book(book)
    assert [e.id for e in again] == expected_ids


# DoD-5 (US-080.AC-1): the ordering holds under a filter too -- a filtered call
# repeated with the same arguments is stable and still name-then-id ordered.
async def test_ordering_is_stable_under_filters__DoD5_US080_AC1(db: DbConfig):
    book = 601
    await codex_entries.create(_entry(book, CodexKind.character, "gamma", "g"))
    await codex_entries.create(_entry(book, CodexKind.character, "alpha", "a"))
    await codex_entries.create(_entry(book, CodexKind.character, "beta", "b"))

    first = await codex_entries.list_by_book(book, kind=CodexKind.character)
    second = await codex_entries.list_by_book(book, kind=CodexKind.character)

    assert [e.name for e in first] == ["alpha", "beta", "gamma"]
    assert [e.id for e in second] == [e.id for e in first]


# ---------------------------------------------------------------------------
# DoD-6 — update persists every changed field; the returned row is the stored row
# ---------------------------------------------------------------------------


# DoD-6 (UC-070): update persists every changed field, and the returned row
# reflects the stored state -- it agrees field-for-field with an independent
# re-read of the row, not merely with the in-memory argument.
async def test_update_persists_changed_fields__DoD6_UC070(db: DbConfig):
    created = await codex_entries.create(
        _entry(700, CodexKind.character, "Old Name", "old body", author_id=11)
    )

    created.name = "New Name"
    created.body = "new body"
    created.kind = CodexKind.location
    created.archived = True
    created.modified_by = 22
    created.modified_at = datetime(2026, 7, 27, 12, 0, 0)

    returned = await codex_entries.update(created)

    stored = await codex_entries.get_by_id(created.id)
    assert stored is not None

    # Every changed field reached the database.
    assert stored.name == "New Name"
    assert stored.body == "new body"
    assert stored.kind is CodexKind.location
    assert stored.archived is True
    assert stored.modified_by == 22
    assert stored.modified_at == datetime(2026, 7, 27, 12, 0, 0)
    # Untouched fields survive unchanged.
    assert stored.book_id == 700
    assert stored.author_id == 11

    # The returned row reflects that stored state.
    assert returned is not None
    assert returned.id == stored.id
    assert returned.book_id == stored.book_id
    assert returned.kind is stored.kind
    assert returned.name == stored.name
    assert returned.body == stored.body
    assert returned.archived == stored.archived
    assert returned.author_id == stored.author_id
    assert returned.modified_by == stored.modified_by
    assert returned.modified_at == stored.modified_at


# DoD-6 (UC-070): a null `name` written by update is persisted as null (a fact
# losing its name is a real edit, not a no-op), and the row stays fetchable.
async def test_update_persists_null_name__DoD6_UC070(db: DbConfig):
    created = await codex_entries.create(
        _entry(701, CodexKind.fact, "Provisional title", "a fact body")
    )

    created.name = None
    created.body = "an amended fact body"
    returned = await codex_entries.update(created)

    stored = await codex_entries.get_by_id(created.id)
    assert stored is not None
    assert stored.name is None
    assert stored.body == "an amended fact body"
    assert returned.name is stored.name
    assert returned.body == stored.body


# DoD-6 (UC-070): update touches only the given row -- a sibling entry in the
# same book is untouched.
async def test_update_touches_only_the_given_row__DoD6_UC070(db: DbConfig):
    book = 702
    target = await codex_entries.create(
        _entry(book, CodexKind.character, "Target", "target body")
    )
    sibling = await codex_entries.create(
        _entry(book, CodexKind.character, "Sibling", "sibling body")
    )

    target.body = "changed"
    await codex_entries.update(target)

    stored_sibling = await codex_entries.get_by_id(sibling.id)
    assert stored_sibling is not None
    assert stored_sibling.name == "Sibling"
    assert stored_sibling.body == "sibling body"
