"""Tests for the LanceDB vector sidecar (feature 013, step 005).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 005), in
`app.db.vector`:
    EmbedBatch      = Callable[[Sequence[str]], Awaitable[list[list[float]]]]
    ProbeDimension  = Callable[[], Awaitable[int]]
    CHUNK_TABLE_NAME: str
    class SourceKind(str, enum.Enum) {codex_entry}
    @dataclass(frozen=True) class ChunkHit
        source_kind / source_id / chunk_index / text / score
    CHUNK_SIZE_CHARS / CHUNK_OVERLAP_CHARS / SINGLE_CHUNK_THRESHOLD_CHARS
    @dataclass(frozen=True) class VectorSource(Generic[TRow])
        source_kind / model_class / row_selector / chunker
    VECTOR_SOURCE_REGISTRY: list[VectorSource[Any]]
    class VectorIndexError(Exception)
    async def init_vector(vector_dir, embed_batch=None, probe_dimension=None) -> None
    async def get_table_dimension() -> int | None
    async def upsert_chunks(book_id, source_kind, source_id, chunks) -> None
    async def delete_by_source(source_kind, source_id) -> None
    async def delete_by_book(book_id) -> None
    async def search(book_id, query_vector, kinds=None, limit=10) -> list[ChunkHit]
    def chunk_codex_entry(entry: CodexEntry) -> list[str]
    async def rebuild_index() -> int
and, in `app.db.import_export_queries`:
    async def run_vector_rebuild() -> None

Expected values come from the step spec (005.vector-sidecar.md -> Interface
intent + Definition of done, plus 005.context.md), never from implementation
internals:
    - the chunk table is created at the dimension the PROBE returned, so two
      different probe values yield two differently-dimensioned tables (DoD-1);
    - `upsert_chunks` writes one row per chunk with `source_id` as a STRING and
      `chunk_index` running from zero in the supplied order (DoD-2);
    - re-upserting a source with FEWER chunks leaves no orphan rows -- the
      contract is delete-then-reinsert, not update (DoD-3);
    - `delete_by_source` / `delete_by_book` remove exactly their own scope and
      nothing else (DoD-4, DoD-5);
    - `book_id` is a HARD filter: another book's chunk is never returned even
      when it is the nearest neighbour of the query vector (DoD-6);
    - `search` narrows to the requested kinds, honours `limit`, orders nearest
      first, and every hit carries source_kind / source_id / chunk_index / text
      / score (DoD-7);
    - the chunker yields ONE chunk for a body that fits the chunk size, and that
      chunk begins with the entry's name (DoD-8); a `fact` (null name) prepends
      nothing (DoD-9); a longer body splits on PARAGRAPH boundaries into more
      than one chunk, each within CHUNK_SIZE_CHARS, with CHUNK_OVERLAP_CHARS of
      overlap between adjacent chunks (DoD-10) -- asserted against the module
      constants, never against literal 1200/200;
    - `VECTOR_SOURCE_REGISTRY` holds exactly ONE entry, discriminated
      `codex_entry`, whose row selector never offers an archived entry to the
      chunker (DoD-11);
    - `rebuild_index` drops the existing table, repopulates from the registry
      and returns the total chunk count written (DoD-12); an empty codex returns
      zero and leaves a usable empty table (DoD-13);
    - `run_vector_rebuild` LOGS AND SWALLOWS a rebuild failure, so an import
      into an instance with no embedding provider still completes (DoD-14).

No network and no real embedding server: LanceDB itself runs for real against a
per-test `tmp_path` vector dir, and only the EMBEDDER is mocked -- deterministic
callables are injected through `init_vector`, which is the second benefit of the
injection seam. Fixed short orthogonal vectors keep nearest-neighbour ordering
predictable under any distance metric. Async tests use asyncio_mode = "auto";
the `db` fixture (conftest) supplies an initialized throwaway temp-SQLite engine
where a registry walk needs one. SQLite does not enforce FKs by default, so
codex entries need no parent book/user rows.
"""

import logging
from collections.abc import Sequence
from pathlib import Path

import pytest

from app.db import codex_entries, import_export_queries, vector
from app.db.engine import DbConfig
from app.models.codex_entry import CodexEntry, CodexKind

# ---------------------------------------------------------------------------
# Deterministic doubles + fixed vectors
# ---------------------------------------------------------------------------

DIM = 4

V_A: list[float] = [1.0, 0.0, 0.0, 0.0]
V_B: list[float] = [0.0, 1.0, 0.0, 0.0]
V_C: list[float] = [0.0, 0.0, 1.0, 0.0]
V_D: list[float] = [0.0, 0.0, 0.0, 1.0]


def _doubles(dimension: int = DIM, vector_value: Sequence[float] | None = None):
    """A deterministic (embed_batch, probe_dimension) pair.

    `probe_dimension` reports `dimension`; `embed_batch` returns one fixed
    vector per input text, in input order.
    """
    fixed = list(vector_value) if vector_value is not None else [1.0] + [0.0] * (
        dimension - 1
    )

    async def _embed_batch(texts: Sequence[str]) -> list[list[float]]:
        return [list(fixed) for _ in texts]

    async def _probe_dimension() -> int:
        return dimension

    return _embed_batch, _probe_dimension


async def _init(
    tmp_path: Path,
    name: str = "vector",
    dimension: int = DIM,
    vector_value: Sequence[float] | None = None,
) -> None:
    """Connect the sidecar to this test's own vector dir with mocked callables."""
    embed_batch, probe_dimension = _doubles(dimension, vector_value)
    await vector.init_vector(
        tmp_path / name,
        embed_batch=embed_batch,
        probe_dimension=probe_dimension,
    )


def _entry(
    book_id: int,
    kind: CodexKind,
    name: str | None,
    body: str,
    *,
    archived: bool = False,
    author_id: int = 1,
) -> CodexEntry:
    """A CodexEntry with the required non-null fields populated."""
    return CodexEntry(
        book_id=book_id,
        kind=kind,
        name=name,
        body=body,
        archived=archived,
        author_id=author_id,
    )


def _texts(hits: Sequence[vector.ChunkHit]) -> set[str]:
    return {hit.text for hit in hits}


def _in_index_order(hits: Sequence[vector.ChunkHit]) -> list[vector.ChunkHit]:
    return sorted(hits, key=lambda hit: hit.chunk_index)


# ---------------------------------------------------------------------------
# DoD-1 — the table is created at the PROBED dimension
# ---------------------------------------------------------------------------


# DoD-1 (retrieval.md -> Vector dimension): the chunk table is created at the
# dimension the probe returned -- never at a declared constant -- so two
# different probe values produce two differently-dimensioned tables.
async def test_table_created_at_probed_dimension__DoD1(db: DbConfig, tmp_path: Path):
    # A fresh vector dir has no chunk table yet (the table is created lazily).
    await _init(tmp_path, "probe4", dimension=4)
    assert await vector.get_table_dimension() is None

    await vector.rebuild_index()

    assert await vector.get_table_dimension() == 4

    # A different probe value -> a differently-dimensioned table.
    await _init(tmp_path, "probe8", dimension=8)
    assert await vector.get_table_dimension() is None

    await vector.rebuild_index()

    assert await vector.get_table_dimension() == 8


# ---------------------------------------------------------------------------
# DoD-2 — upsert_chunks writes one row per chunk
# ---------------------------------------------------------------------------


# DoD-2 (retrieval.md -> Sidecar shape): upsert_chunks writes one row per chunk,
# with book_id, source_kind, source_id (AS A STRING) and text populated, and
# chunk_index running from zero in the supplied order.
async def test_upsert_writes_one_row_per_chunk__DoD2(tmp_path: Path):
    await _init(tmp_path)
    book = 100
    source_id = 7001

    await vector.upsert_chunks(
        book,
        vector.SourceKind.codex_entry,
        source_id,
        [("alpha text", V_A), ("beta text", V_B), ("gamma text", V_C)],
    )

    hits = await vector.search(book, V_A, limit=10)

    assert len(hits) == 3
    ordered = _in_index_order(hits)
    assert [hit.chunk_index for hit in ordered] == [0, 1, 2]
    assert [hit.text for hit in ordered] == ["alpha text", "beta text", "gamma text"]
    # source_id is the snowflake AS A STRING.
    for hit in ordered:
        assert isinstance(hit.source_id, str)
        assert hit.source_id == str(source_id)
        assert hit.source_kind == vector.SourceKind.codex_entry

    # book_id is populated: another book sees none of these rows.
    assert await vector.search(999, V_A, limit=10) == []


# ---------------------------------------------------------------------------
# DoD-3 — delete-then-reinsert leaves no orphans
# ---------------------------------------------------------------------------


# DoD-3 (retrieval.md -> Incremental maintenance): re-upserting a source with
# FEWER chunks than before leaves no orphan rows from the longer previous
# version -- which is why the contract is delete-then-reinsert, not update.
async def test_reupsert_with_fewer_chunks_leaves_no_orphans__DoD3(tmp_path: Path):
    await _init(tmp_path)
    book = 110
    source_id = 7002

    await vector.upsert_chunks(
        book,
        vector.SourceKind.codex_entry,
        source_id,
        [("old one", V_A), ("old two", V_B), ("old three", V_C)],
    )
    await vector.upsert_chunks(
        book,
        vector.SourceKind.codex_entry,
        source_id,
        [("new single", V_A)],
    )

    hits = await vector.search(book, V_A, limit=50)

    assert len(hits) == 1
    assert hits[0].text == "new single"
    assert hits[0].chunk_index == 0
    assert _texts(hits).isdisjoint({"old one", "old two", "old three"})


# ---------------------------------------------------------------------------
# DoD-4 / DoD-5 — scoped deletes
# ---------------------------------------------------------------------------


# DoD-4: delete_by_source removes exactly that source's chunks and leaves every
# other source's chunks intact.
async def test_delete_by_source_removes_only_that_source__DoD4(tmp_path: Path):
    await _init(tmp_path)
    book = 120
    doomed = 7003
    kept = 7004

    await vector.upsert_chunks(
        book,
        vector.SourceKind.codex_entry,
        doomed,
        [("doomed one", V_A), ("doomed two", V_B), ("doomed three", V_C)],
    )
    await vector.upsert_chunks(
        book,
        vector.SourceKind.codex_entry,
        kept,
        [("kept one", V_A), ("kept two", V_B)],
    )

    await vector.delete_by_source(vector.SourceKind.codex_entry, doomed)

    hits = await vector.search(book, V_A, limit=50)

    assert _texts(hits) == {"kept one", "kept two"}
    assert {hit.source_id for hit in hits} == {str(kept)}


# DoD-5: delete_by_book removes every chunk of that book and no chunk of
# another book.
async def test_delete_by_book_removes_only_that_book__DoD5(tmp_path: Path):
    await _init(tmp_path)
    book_a = 130
    book_b = 131

    await vector.upsert_chunks(
        book_a,
        vector.SourceKind.codex_entry,
        7005,
        [("a one", V_A), ("a two", V_B)],
    )
    await vector.upsert_chunks(
        book_b,
        vector.SourceKind.codex_entry,
        7006,
        [("b one", V_A), ("b two", V_B)],
    )

    await vector.delete_by_book(book_a)

    assert await vector.search(book_a, V_A, limit=50) == []
    assert _texts(await vector.search(book_b, V_A, limit=50)) == {"b one", "b two"}


# ---------------------------------------------------------------------------
# DoD-6 — book_id is a hard filter, not a ranking preference
# ---------------------------------------------------------------------------


# DoD-6 (retrieval.md -> hard filter; US-085.AC-1): search never returns a chunk
# from another book EVEN WHEN that chunk is the nearest neighbour of the query
# vector. The foreign chunk's vector is made identical to the query vector, and
# the searching book's own chunks are orthogonal to it -- so the foreign chunk
# genuinely IS nearest, which the book_b search proves.
async def test_search_never_crosses_books_even_when_nearest__DoD6(tmp_path: Path):
    await _init(tmp_path)
    book_a = 140
    book_b = 141
    query = V_A

    # book_a's chunks are orthogonal to the query.
    await vector.upsert_chunks(
        book_a,
        vector.SourceKind.codex_entry,
        7007,
        [("a orthogonal one", V_B), ("a orthogonal two", V_C)],
    )
    # book_b's chunk sits exactly ON the query vector -- the true nearest.
    await vector.upsert_chunks(
        book_b,
        vector.SourceKind.codex_entry,
        7008,
        [("b exact match", query)],
    )

    # Proof that the foreign chunk really is the nearest neighbour.
    b_hits = await vector.search(book_b, query, limit=10)
    assert b_hits[0].text == "b exact match"

    a_hits = await vector.search(book_a, query, limit=10)

    assert _texts(a_hits) == {"a orthogonal one", "a orthogonal two"}
    assert "b exact match" not in _texts(a_hits)
    assert {hit.source_id for hit in a_hits} == {str(7007)}


# ---------------------------------------------------------------------------
# DoD-7 — the query surface: kinds, limit, hit shape, nearest first
# ---------------------------------------------------------------------------


# DoD-7 (retrieval.md -> Query surface): every hit carries source_kind,
# source_id, chunk_index, text and score.
async def test_search_hits_carry_the_documented_fields__DoD7(tmp_path: Path):
    await _init(tmp_path)
    book = 150
    source_id = 7009

    await vector.upsert_chunks(
        book,
        vector.SourceKind.codex_entry,
        source_id,
        [("field one", V_A), ("field two", V_B)],
    )

    hits = await vector.search(book, V_A, limit=10)

    assert len(hits) == 2
    for hit in hits:
        assert hit.source_kind == vector.SourceKind.codex_entry
        assert hit.source_id == str(source_id)
        assert hit.chunk_index in (0, 1)
        assert hit.text in {"field one", "field two"}
        # A score is present and numeric.
        assert isinstance(float(hit.score), float)


# DoD-7: search narrows to the requested source kinds -- asking for
# `codex_entry` returns the codex chunks, and every hit carries that kind. An
# omitted `kinds` does not narrow. Both a set and a list bind.
async def test_search_narrows_to_requested_kinds__DoD7(tmp_path: Path):
    await _init(tmp_path)
    book = 151

    await vector.upsert_chunks(
        book,
        vector.SourceKind.codex_entry,
        7010,
        [("kind one", V_A), ("kind two", V_B)],
    )

    as_set = await vector.search(
        book, V_A, kinds={vector.SourceKind.codex_entry}, limit=10
    )
    as_list = await vector.search(
        book, V_A, kinds=[vector.SourceKind.codex_entry], limit=10
    )
    unnarrowed = await vector.search(book, V_A, limit=10)

    assert _texts(as_set) == {"kind one", "kind two"}
    assert _texts(as_list) == {"kind one", "kind two"}
    assert _texts(unnarrowed) == {"kind one", "kind two"}
    assert {hit.source_kind for hit in as_set} == {vector.SourceKind.codex_entry}


# DoD-7: search honours the limit.
async def test_search_honours_the_limit__DoD7(tmp_path: Path):
    await _init(tmp_path)
    book = 152

    await vector.upsert_chunks(
        book,
        vector.SourceKind.codex_entry,
        7011,
        [
            ("limit one", V_A),
            ("limit two", V_B),
            ("limit three", V_C),
            ("limit four", V_D),
            ("limit five", V_A),
        ],
    )

    assert len(await vector.search(book, V_A, limit=2)) == 2
    assert len(await vector.search(book, V_A, limit=5)) == 5


# DoD-7 (Interface intent -> "nearest first"): the chunk whose vector equals the
# query vector is returned before the orthogonal ones.
async def test_search_returns_nearest_first__DoD7(tmp_path: Path):
    await _init(tmp_path)
    book = 153

    await vector.upsert_chunks(
        book,
        vector.SourceKind.codex_entry,
        7012,
        [("far one", V_B), ("exact", V_C), ("far two", V_D)],
    )

    hits = await vector.search(book, V_C, limit=10)

    assert hits[0].text == "exact"


# ---------------------------------------------------------------------------
# DoD-8 / DoD-9 / DoD-10 — the codex chunker (pure, synchronous)
# ---------------------------------------------------------------------------


# DoD-8 (retrieval.md -> Chunking): an entry whose body fits the chunk size
# yields exactly one chunk, and that chunk begins with the entry's name -- so a
# name-only query matches the entry that is about that name.
def test_chunker_prepends_name_for_a_fitting_body__DoD8():
    character = _entry(
        200,
        CodexKind.character,
        "Marek",
        "A quiet smith who works iron before dawn.",
    )

    chunks = vector.chunk_codex_entry(character)

    assert len(chunks) == 1
    assert chunks[0].startswith("Marek")
    assert "A quiet smith who works iron before dawn." in chunks[0]

    location = _entry(200, CodexKind.location, "Ravensmoor", "A wet upland waste.")

    location_chunks = vector.chunk_codex_entry(location)

    assert len(location_chunks) == 1
    assert location_chunks[0].startswith("Ravensmoor")
    assert "A wet upland waste." in location_chunks[0]


# DoD-9 (US-078.AC-2 consequence): a `fact` entry has a null name, so the
# chunker prepends nothing -- the chunk is the body.
def test_chunker_prepends_nothing_for_a_fact__DoD9():
    fact = _entry(
        200,
        CodexKind.fact,
        None,
        "The river freezes for six weeks each winter.",
    )

    chunks = vector.chunk_codex_entry(fact)

    assert len(chunks) == 1
    assert chunks[0] == "The river freezes for six weeks each winter."


def _paragraphs(text: str) -> list[str]:
    """The non-empty paragraphs of a chunk, blank-line separated."""
    return [part.strip() for part in text.split("\n\n") if part.strip()]


def _shared_run(earlier: list[str], later: list[str]) -> list[str]:
    """The longest paragraph run that ends `earlier` and starts `later`."""
    for size in range(min(len(earlier), len(later)), 0, -1):
        if earlier[-size:] == later[:size]:
            return earlier[-size:]
    return []


# DoD-10 (retrieval.md -> Chunking): a body longer than the chunk size splits on
# PARAGRAPH boundaries into more than one chunk, each within the configured
# chunk size, with the configured overlap between adjacent chunks. Asserted
# against the module constants so a later tune cannot falsify the test. A `fact`
# is used so no name prefix perturbs the paragraph arithmetic.
def test_chunker_splits_long_body_on_paragraph_boundaries__DoD10():
    paragraphs = [f"P{index:02d} " + "x" * 145 for index in range(20)]
    longest_paragraph = max(len(paragraph) for paragraph in paragraphs)
    body = "\n\n".join(paragraphs)
    assert len(body) > vector.CHUNK_SIZE_CHARS  # premise of this test

    chunks = vector.chunk_codex_entry(_entry(210, CodexKind.fact, None, body))

    # More than one chunk, each within the configured size.
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= vector.CHUNK_SIZE_CHARS

    # Split on paragraph boundaries: no paragraph is cut, and none is lost.
    original = set(paragraphs)
    seen: set[str] = set()
    for chunk in chunks:
        for paragraph in _paragraphs(chunk):
            assert paragraph in original, "a paragraph was split mid-paragraph"
            seen.add(paragraph)
    assert seen == original

    # The configured overlap between adjacent chunks, rounded to whole
    # paragraphs (the boundary the split respects).
    for earlier, later in zip(chunks, chunks[1:]):
        shared = _shared_run(_paragraphs(earlier), _paragraphs(later))
        assert shared, "adjacent chunks must overlap"
        overlap_chars = len("\n\n".join(shared))
        assert overlap_chars <= vector.CHUNK_OVERLAP_CHARS + longest_paragraph
        assert overlap_chars >= vector.CHUNK_OVERLAP_CHARS - longest_paragraph


# ---------------------------------------------------------------------------
# DoD-11 — the widened registry
# ---------------------------------------------------------------------------


# DoD-11 (retrieval.md -> "Archived codex entries are removed from the index,
# not flagged"): VECTOR_SOURCE_REGISTRY holds exactly one entry, discriminated
# `codex_entry`, and its row selector returns non-archived entries only -- an
# archived entry is never offered to the chunker.
async def test_registry_holds_one_codex_source_skipping_archived__DoD11(db: DbConfig):
    assert len(vector.VECTOR_SOURCE_REGISTRY) == 1

    source = vector.VECTOR_SOURCE_REGISTRY[0]
    assert source.source_kind == vector.SourceKind.codex_entry
    assert source.model_class is CodexEntry

    kept_a = await codex_entries.create(
        _entry(300, CodexKind.character, "Kept A", "kept a body")
    )
    kept_b = await codex_entries.create(
        _entry(301, CodexKind.fact, None, "kept b body")
    )
    archived = await codex_entries.create(
        _entry(300, CodexKind.location, "Gone", "archived body", archived=True)
    )

    rows = await source.row_selector()

    ids = {row.id for row in rows}
    assert ids == {kept_a.id, kept_b.id}
    assert archived.id not in ids

    # The archived entry is never offered to the chunker.
    chunked = [chunk for row in rows for chunk in source.chunker(row)]
    assert not any("archived body" in chunk for chunk in chunked)
    assert any("kept a body" in chunk for chunk in chunked)


# ---------------------------------------------------------------------------
# DoD-12 / DoD-13 — the real rebuild
# ---------------------------------------------------------------------------


# DoD-12 (retrieval.md -> Full rebuild): rebuild_index drops the existing table,
# repopulates it from the registry and returns the TOTAL chunk count written.
# Three short (one-chunk) entries are seeded plus one archived entry, which the
# registry's selector must skip; a pre-existing row from an unrelated book proves
# the drop.
async def test_rebuild_drops_repopulates_and_counts__DoD12(
    db: DbConfig, tmp_path: Path
):
    await _init(tmp_path)
    book = 400
    stale_book = 401

    # A stale row that only the drop can remove (no codex entry backs it).
    await vector.upsert_chunks(
        stale_book,
        vector.SourceKind.codex_entry,
        7100,
        [("stale row", V_A)],
    )

    first = await codex_entries.create(
        _entry(book, CodexKind.character, "Alda", "alda body")
    )
    second = await codex_entries.create(
        _entry(book, CodexKind.location, "Halle", "halle body")
    )
    third = await codex_entries.create(_entry(book, CodexKind.fact, None, "fact body"))
    await codex_entries.create(
        _entry(book, CodexKind.character, "Hidden", "hidden body", archived=True)
    )

    written = await vector.rebuild_index()

    # One chunk per short entry; the archived entry contributes none.
    assert written == 3

    hits = await vector.search(book, V_A, limit=50)
    assert len(hits) == 3
    assert {hit.source_id for hit in hits} == {
        str(first.id),
        str(second.id),
        str(third.id),
    }
    joined = "\n".join(hit.text for hit in hits)
    assert "alda body" in joined
    assert "halle body" in joined
    assert "fact body" in joined
    assert "hidden body" not in joined

    # The previous table was dropped, not appended to.
    assert await vector.search(stale_book, V_A, limit=50) == []


# DoD-13: rebuild_index with an empty codex returns zero and leaves a USABLE
# empty table -- the table exists at the probed dimension and a search answers
# with an empty list rather than failing.
async def test_rebuild_with_empty_codex_returns_zero__DoD13(
    db: DbConfig, tmp_path: Path
):
    await _init(tmp_path, dimension=6)

    written = await vector.rebuild_index()

    assert written == 0
    assert await vector.get_table_dimension() == 6
    assert await vector.search(500, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0], limit=10) == []


# ---------------------------------------------------------------------------
# DoD-14 — run_vector_rebuild logs and swallows a rebuild failure
# ---------------------------------------------------------------------------


# DoD-14 (retrieval.md -> the import path bypasses the gate): with no embedder
# injected -- a fresh instance with no embedding provider -- rebuild_index
# raises VectorIndexError, but run_vector_rebuild logs it and swallows it, so
# the import still completes.
async def test_run_vector_rebuild_swallows_uninjected_failure__DoD14(
    db: DbConfig, tmp_path: Path, caplog
):
    # init_vector called the way a provider-less instance would: no callables.
    await vector.init_vector(tmp_path / "vector")

    with pytest.raises(vector.VectorIndexError):
        await vector.rebuild_index()

    with caplog.at_level(logging.DEBUG):
        assert await import_export_queries.run_vector_rebuild() is None

    assert any(
        record.name.startswith("app.") for record in caplog.records
    ), "the swallowed rebuild failure must be logged"


# DoD-14: the same guard covers a failing embedding provider -- an injected
# probe that raises propagates out of rebuild_index but is swallowed by
# run_vector_rebuild.
async def test_run_vector_rebuild_swallows_embedder_failure__DoD14(
    db: DbConfig, tmp_path: Path, caplog
):
    async def _failing_embed_batch(texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("no embedding provider")

    async def _failing_probe() -> int:
        raise RuntimeError("no embedding provider")

    await vector.init_vector(
        tmp_path / "vector",
        embed_batch=_failing_embed_batch,
        probe_dimension=_failing_probe,
    )
    await codex_entries.create(
        _entry(600, CodexKind.character, "Nera", "nera body")
    )

    with pytest.raises(RuntimeError):
        await vector.rebuild_index()

    with caplog.at_level(logging.DEBUG):
        assert await import_export_queries.run_vector_rebuild() is None

    assert any(
        record.name.startswith("app.") for record in caplog.records
    ), "the swallowed rebuild failure must be logged"
