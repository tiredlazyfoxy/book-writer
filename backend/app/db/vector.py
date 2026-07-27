"""LanceDB sidecar — the one discriminated chunk table and its access layer.

SQLite is the source of truth; LanceDB is a **derived** index, rebuilt from
source rows on import and never exported (``docs/architecture/retrieval.md``).
This module owns the LanceDB connection and every table handle: no LanceDB
object leaves ``db/``, for the same reason no ``AsyncSession`` does.

Layering (``docs/architecture/backend.md``): ``db → services`` is **forbidden**,
so this module may not import ``app.services.embedding``. The two embedding
callables :func:`rebuild_index` needs are therefore **injected** at
:func:`init_vector` by the composition root (``app/main.py``), and the callable
*types* are declared here rather than imported from the service. Both existing
``rebuild_index()`` call sites — ``services/db_admin.py:rebuild_vector_index``
and ``db/import_export_queries.py:run_vector_rebuild`` — keep their current
zero-argument shape; the second of those lives in ``db/`` and is exactly why the
injection exists.

A ``db → db`` import (``from app.db import codex_entries`` for the registry's row
selector) is permitted and already precedented by ``db/import_export_queries.py``.
"""

import asyncio
import enum
import logging
from collections.abc import Awaitable, Callable, Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

import lancedb
import pyarrow as pa
from sqlmodel import SQLModel

from app.db import codex_entries
from app.models.codex_entry import CodexEntry

logger = logging.getLogger(__name__)

# Module-level singletons — populated by ``init_vector``.
_vector_dir: Path | None = None
_db: Any = None

# ---------------------------------------------------------------------------
# The injected embedding seam (step 005).
#
# ``db/`` may not import ``services/``, so the shapes of ``services/embedding``'s
# ``embed_batch`` / ``probe_dimension`` are spelled out here. They are structural
# aliases, not an import — ``app/main.py`` supplies the real functions.
# ---------------------------------------------------------------------------

EmbedBatch = Callable[[Sequence[str]], Awaitable[list[list[float]]]]
"""One batch of texts in, one vector per text out, in input order."""

ProbeDimension = Callable[[], Awaitable[int]]
"""Embed a short constant probe text and report the model's vector length."""

# Populated by ``init_vector``; ``None`` until the composition root injects them.
_embed_batch: EmbedBatch | None = None
_probe_dimension: ProbeDimension | None = None


class VectorIndexError(Exception):
    """The sidecar cannot do what was asked of it.

    Raised by :func:`rebuild_index` when it needs to embed — probe the dimension,
    or embed a batch of chunk texts — and **no embedder was injected** at
    :func:`init_vector`. A rebuild that cannot embed has not rebuilt anything, so
    it says so rather than returning a count of zero that reads like success.
    Also raised when the injected embedder answers a batch with a different
    number of vectors than it was given texts: position is the only thing
    pairing a chunk to its vector, so the rebuild stops rather than write a
    silently mis-paired index.

    A **plain exception class, deliberately without the repo's reason-enum
    pairing** (``ChatError`` / ``CodexError`` / ``EmbeddingError``): this module
    has exactly one failure it can name for itself, and a one-member enum would
    be noise. Every *embedding-side* failure already has a taxonomy —
    ``services/embedding.py:EmbeddingErrorReason`` — which this module may not
    import (``db → services``) and must not duplicate; those errors travel out of
    the injected callables unchanged.

    Handling: ``db/import_export_queries.py:run_vector_rebuild`` logs and
    swallows it (a fresh instance with no embedding provider must still finish an
    import), while ``services/db_admin.py:rebuild_vector_index`` lets it
    propagate.
    """


# ---------------------------------------------------------------------------
# Sidecar shape — one table, one row per chunk, discriminated by source kind.
# ---------------------------------------------------------------------------

CHUNK_TABLE_NAME = "chunks"
"""The single sidecar table. Columns (fixed by ``retrieval.md`` → Sidecar shape):
``vector``, ``book_id``, ``source_kind``, ``source_id`` (the snowflake **as a
string**), ``chunk_index``, ``text``. Created lazily at the dimension the probe
returned — never at a declared constant."""


class SourceKind(str, enum.Enum):
    """The corpus a chunk came from — the sidecar's discriminator column.

    A fixed taxonomy over one table (the ``CodexKind`` precedent). Only the
    corpus that exists is declared: ``retrieval.md`` reserves ``chapter``,
    ``chapter_summary`` and ``chapter_notes`` for later stages, and a member is
    added when its chunker is. Subclassing ``str`` means a member compares equal
    to its wire value, so ``hit.source_kind == "codex_entry"`` holds.
    """

    codex_entry = "codex_entry"


@dataclass(frozen=True)
class ChunkHit:
    """One nearest-neighbour result from :func:`search`.

    - ``source_id`` is the **string** form stored in the index (``retrieval.md``
      fixes it as the source entity's snowflake as a string, and the codex
      service's public entry points already take wire-string ids).
    - ``text`` is the chunk's own text, kept in the index because the chunk — not
      the source row — is the retrieval unit.
    - ``score`` is the index's similarity/distance score for the query vector.

    A frozen typed record rather than a dict (root ``CLAUDE.md`` — no free
    dictionaries), following ``services/tools.py:ToolDef``.
    """

    source_kind: SourceKind
    source_id: str
    chunk_index: int
    text: str
    score: float


# ---------------------------------------------------------------------------
# Chunking — tuning parameters, not architecture (``retrieval.md`` pins no
# numbers deliberately). Named constants so a later tune is a one-line change;
# the as-built values are recorded in this feature's ``outcome.md``.
# ---------------------------------------------------------------------------

CHUNK_SIZE_CHARS = 1200
"""Maximum characters in one chunk — comfortably inside a 512-token input window
once the name prefix is added."""

CHUNK_OVERLAP_CHARS = 200
"""Characters shared between adjacent chunks of one source, so a sentence
spanning a boundary survives on both sides."""

SINGLE_CHUNK_THRESHOLD_CHARS = CHUNK_SIZE_CHARS
"""A source whose chunk text fits this is exactly one chunk — the common case for
a codex entry."""

_PARAGRAPH_SEPARATOR = "\n\n"
"""A blank line is the paragraph boundary a long body is split on. Splitting on
it is lossless: the windows a body is cut into concatenate back to the body."""


def _paragraph_units(text: str) -> list[str]:
    """Split ``text`` into paragraphs, each keeping its trailing separator.

    Lossless — ``"".join(_paragraph_units(t)) == t`` — so window boundaries are
    the only thing the splitter decides, and the same text always splits the
    same way.
    """
    parts = text.split(_PARAGRAPH_SEPARATOR)
    last = len(parts) - 1
    units = [
        part if index == last else part + _PARAGRAPH_SEPARATOR
        for index, part in enumerate(parts)
    ]
    return [unit for unit in units if unit]


def _overlap_units(units: Sequence[str], window_chars: int) -> list[str]:
    """The trailing **whole paragraphs** the next window re-opens with.

    The paragraph boundary is the structural rule; :data:`CHUNK_OVERLAP_CHARS`
    is a tuning quantity, so the carry is the shortest suffix of ``units`` that
    reaches it — an overlap of roughly, not exactly, the configured size. It is
    capped at half a window so the overlap can never crowd out the new material
    (that cap is also what guarantees forward progress), and a final paragraph
    bigger than that cap carries nothing: the next window simply starts at the
    boundary after it.
    """
    cap = max(1, window_chars // 2)
    carry: list[str] = []
    carried_chars = 0

    for unit in reversed(units):
        if carried_chars >= CHUNK_OVERLAP_CHARS:
            break
        if carried_chars + len(unit) > cap:
            break
        carry.insert(0, unit)
        carried_chars += len(unit)

    return carry


def _split_into_windows(text: str, window_chars: int) -> list[str]:
    """Cut ``text`` into overlapping windows of at most ``window_chars``.

    A window is closed at a **paragraph boundary** whenever the next paragraph
    would overflow it, and the next window opens with the trailing whole
    paragraphs of the one just closed (:func:`_overlap_units`), so a window both
    begins and ends on a boundary and holds nothing but complete paragraphs of
    the source. The overlap exists so a sentence sitting on a boundary is
    reachable from either side.

    A single paragraph longer than a whole window is the one case with no
    boundary to cut on: it is cut mid-paragraph, and there — and only there —
    the carry is a plain :data:`CHUNK_OVERLAP_CHARS` character tail.

    Deterministic: the same text and window always produce byte-identical
    windows, and no paragraph is dropped from the sequence.
    """
    if len(text) <= window_chars:
        return [text]

    # Clamped so a window always makes progress past its own carried-over tail.
    overlap = min(CHUNK_OVERLAP_CHARS, window_chars - 1)

    windows: list[str] = []
    current: list[str] = []
    current_chars = 0
    carried = 0

    def _carry_over(units: list[str]) -> None:
        """Open the next window with ``units`` (already emitted material)."""
        nonlocal current, current_chars, carried
        current = list(units)
        current_chars = sum(len(unit) for unit in current)
        carried = len(current)

    for unit in _paragraph_units(text):
        piece = unit
        while piece:
            room = window_chars - current_chars
            if len(piece) <= room:
                current.append(piece)
                current_chars += len(piece)
                break
            if len(current) > carried:
                # Close this window at the paragraph boundary in hand, and open
                # the next one with its trailing whole paragraphs.
                windows.append("".join(current))
                _carry_over(_overlap_units(current, window_chars))
                continue
            if carried and len(piece) <= window_chars:
                # Only the carried overlap is standing between this paragraph
                # and a window it would fit in on its own. Overlap is the
                # tuning quantity and the boundary is the rule, so the overlap
                # goes rather than the paragraph getting cut.
                _carry_over([])
                continue
            # The paragraph alone outgrows a window: cut it mid-paragraph —
            # there is no boundary to cut on, so the carry is a character tail.
            current.append(piece[:room])
            piece = piece[room:]
            closed = "".join(current)
            windows.append(closed)
            _carry_over([closed[-overlap:]] if overlap else [])

    if len(current) > carried or (current and not windows):
        windows.append("".join(current))

    return windows


def chunk_codex_entry(entry: CodexEntry) -> list[str]:
    """Split one :class:`CodexEntry` into the chunk texts to embed.

    Pure and **deterministic** — the same entry must always produce
    byte-identical chunks, because a full rebuild has to reproduce what
    incremental maintenance wrote.

    - An entry whose body fits :data:`SINGLE_CHUNK_THRESHOLD_CHARS` is one
      chunk, with the entry's ``name`` prepended so a name-only query ("Marek")
      matches the entry that is about Marek. The threshold is measured on the
      **body**: the name is a handful of characters and the window it borrows
      from is an approximation of a token budget, so letting the prefix push a
      one-chunk entry into two would be arbitrary.
    - A ``fact`` (null ``name``) prepends nothing.
    - A longer body splits on **paragraph boundaries** into windows of at most
      :data:`CHUNK_SIZE_CHARS`, adjacent windows sharing the whole trailing
      paragraphs that approximate :data:`CHUNK_OVERLAP_CHARS`. The boundary is
      the structural rule; the overlap is a tuning quantity.

    The name-prefix *format* is this function's own choice; only determinism is
    specified. It is the name followed by a blank line — the same paragraph
    boundary the body itself is split on — and it is prepended **verbatim**
    (a stored name is kept exactly as the author typed it, ``services/codex.py``
    trims nothing), so the first chunk always starts with ``entry.name``. A name
    that is blank or whitespace-only counts as absent, matching the codex
    service's own name rule.

    On a body long enough to split, only the first chunk carries the prefix: the
    prefix is not part of the body, and repeating it would put text that is not
    in the source into every window, breaking the property that a window holds
    nothing but complete paragraphs of the body. A name-only query therefore
    reaches a long entry through its first chunk.
    """
    name = entry.name or ""
    body = entry.body or ""
    prefix = f"{name}{_PARAGRAPH_SEPARATOR}" if name.strip() else ""

    if not (prefix + body).strip():
        # Nothing to embed — an empty source contributes no chunks at all.
        return []

    if len(body) <= SINGLE_CHUNK_THRESHOLD_CHARS:
        return [prefix + body]

    # A split body: the prefix rides inside the first window's budget, so every
    # chunk stays within CHUNK_SIZE_CHARS.
    windows = _split_into_windows(body, max(1, CHUNK_SIZE_CHARS - len(prefix)))
    return [prefix + windows[0], *windows[1:]]


# ---------------------------------------------------------------------------
# The registry — widening the feature-007 seam.
# ---------------------------------------------------------------------------

TRow = TypeVar("TRow", bound=SQLModel)

RowSelector = Callable[[], Awaitable[Sequence[TRow]]]
"""Returns every row of one corpus that must be indexed, across **all** books,
in a deterministic order — and skips the rows that must not be (archived codex
entries are excluded *by the selector*, not by a query-time predicate)."""

Chunker = Callable[[TRow], list[str]]
"""One row in, its list of chunk texts out. Replaces feature 007's single
``text_extractor``, which could not express "one row becomes many vectors"."""


@dataclass(frozen=True)
class VectorSource(Generic[TRow]):
    """One vector-backed corpus: everything :func:`rebuild_index` needs to walk it.

    Replaces feature 007's ``(model_class, text_extractor)`` tuple — a deliberate
    change to a shipped seam (``retrieval.md`` → Registry).

    - ``source_kind`` — the discriminator written into every chunk row.
    - ``model_class`` — the SQLModel table the rows come from.
    - ``row_selector`` — the indexable rows, all books, deterministic order.
    - ``chunker`` — one row → its chunk texts.
    """

    source_kind: SourceKind
    model_class: type[TRow]
    row_selector: RowSelector[TRow]
    chunker: Chunker[TRow]


# The vector-backed corpora. A plain module-level literal list that each
# vector-backed domain feature appends exactly one entry to (mirroring
# ``TABLE_REGISTRY`` / ``TOOL_REGISTRY``): no decorator, no register function.
#
# The codex is the first — and, at Stage 2, the only — searchable corpus
# (``retrieval.md`` → What gets indexed): chapter text, summaries and state notes
# get their entries when their chunkers land. Users / llm_servers are
# configuration, not searchable content: never append them.
VECTOR_SOURCE_REGISTRY: list[VectorSource[Any]] = [
    VectorSource(
        source_kind=SourceKind.codex_entry,
        model_class=CodexEntry,
        row_selector=codex_entries.list_all_unarchived,
        chunker=chunk_codex_entry,
    ),
]


# ---------------------------------------------------------------------------
# Connection.
# ---------------------------------------------------------------------------


async def init_vector(
    vector_dir: Path,
    embed_batch: EmbedBatch | None = None,
    probe_dimension: ProbeDimension | None = None,
) -> None:
    """Open a connection to the LanceDB directory at ``vector_dir``.

    Stores the connection, the directory and the two injected embedding
    callables in the module-level singletons. Creates no table — the chunk table
    is created lazily, at the dimension ``probe_dimension`` reports.

    ``embed_batch`` / ``probe_dimension`` default to ``None`` so the pre-013
    single-argument call shape (``init_vector(some_dir)``) keeps working: the
    lazy self-connect inside :func:`rebuild_index` uses it, and so do existing
    tests that only need a throwaway index directory. ``app/main.py`` — the one
    composition root that may import both ``db/`` and ``services/`` — passes the
    real ``services/embedding.py`` callables; a test injects deterministic
    doubles the same way, which is the injection seam's second benefit.
    """
    global _vector_dir, _db, _embed_batch, _probe_dimension
    vector_dir.mkdir(parents=True, exist_ok=True)
    _vector_dir = vector_dir
    # ``lancedb.connect`` is blocking — run it off the event loop.
    _db = await asyncio.to_thread(lancedb.connect, str(vector_dir))
    _embed_batch = embed_batch
    _probe_dimension = probe_dimension
    logger.info("Vector store initialized at %s", vector_dir)


# ---------------------------------------------------------------------------
# The chunk table — created lazily, always at a probed dimension.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _PendingChunk:
    """One chunk on its way into the table, before it has been embedded.

    A typed record rather than a free dictionary (root ``CLAUDE.md``); the only
    dictionary in this module is :func:`_chunk_record`'s, which is LanceDB's own
    row format.
    """

    book_id: int
    source_kind: SourceKind
    source_id: str
    chunk_index: int
    text: str


def _chunk_schema(dimension: int) -> pa.Schema:
    """The sidecar's columns, with ``vector`` fixed at ``dimension``.

    The column set is fixed by ``retrieval.md`` → Sidecar shape. ``source_id`` is
    a **string** column: a snowflake exceeds the JS safe-integer range and the id
    convention is string-at-every-boundary.
    """
    return pa.schema(
        [
            pa.field("vector", pa.list_(pa.float32(), dimension)),
            pa.field("book_id", pa.int64()),
            pa.field("source_kind", pa.string()),
            pa.field("source_id", pa.string()),
            pa.field("chunk_index", pa.int64()),
            pa.field("text", pa.string()),
        ]
    )


def _chunk_record(chunk: _PendingChunk, vector: Sequence[float]) -> dict[str, Any]:
    """One chunk as the row shape LanceDB ingests."""
    return {
        "vector": [float(value) for value in vector],
        "book_id": chunk.book_id,
        "source_kind": chunk.source_kind.value,
        "source_id": chunk.source_id,
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
    }


def _sql_string(value: str) -> str:
    """Quote ``value`` as a SQL string literal for a LanceDB filter."""
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _source_predicate(source_kind: SourceKind, source_id: str) -> str:
    """The filter selecting exactly one source's chunks.

    Keyed on ``(source_kind, source_id)``, never on the id alone: the table is
    discriminated, so a delete can never reach another corpus's rows.
    """
    return (
        f"source_kind = {_sql_string(source_kind.value)} "
        f"AND source_id = {_sql_string(source_id)}"
    )


def _create_chunk_table(dimension: int, mode: str = "create") -> Any:
    """Create the chunk table at ``dimension``. Blocking — call in a thread."""
    return _db.create_table(
        CHUNK_TABLE_NAME, schema=_chunk_schema(dimension), mode=mode
    )


async def _open_chunk_table() -> Any:
    """The live chunk table handle, or ``None`` when there is no table yet."""
    if _db is None:
        return None
    table_names = await asyncio.to_thread(_db.table_names)
    if CHUNK_TABLE_NAME not in table_names:
        return None
    return await asyncio.to_thread(_db.open_table, CHUNK_TABLE_NAME)


async def get_table_dimension() -> int | None:
    """Report the dimension the live chunk table was created at.

    Returns ``None`` when no chunk table exists yet (nothing has been indexed on
    this instance). Step 006 compares an incoming batch's vector length against
    this to detect a designated embedding model that changed under a live index —
    a LanceDB table cannot hold mixed dimensions, so that write is refused rather
    than coerced (``retrieval.md`` → Vector dimension).
    """
    table = await _open_chunk_table()
    if table is None:
        return None
    schema: pa.Schema = await asyncio.to_thread(lambda: table.schema)
    vector_type = schema.field("vector").type
    list_size = getattr(vector_type, "list_size", None)
    return int(list_size) if list_size is not None else None


# ---------------------------------------------------------------------------
# Write helpers.
# ---------------------------------------------------------------------------


async def upsert_chunks(
    book_id: int,
    source_kind: SourceKind,
    source_id: int,
    chunks: Sequence[tuple[str, Sequence[float]]],
) -> None:
    """Replace one source's chunks with ``chunks``, in order.

    ``chunks`` is the ordered ``(text, vector)`` pairing for the source. The
    operation is **delete-then-reinsert**, not update: delete every row of this
    ``(source_kind, source_id)``, then insert the new ones with ``chunk_index``
    running from zero in the given order. An update in place would leave orphan
    chunks behind whenever the new text produces *fewer* chunks than the old
    (``retrieval.md`` → Incremental maintenance).

    ``source_id`` is passed as an ``int`` and stringified here — the module is
    the single place the snowflake→string conversion happens. An empty
    ``chunks`` therefore still clears the source.

    Creates the chunk table lazily, at the length of the supplied vectors, when
    it does not exist yet.
    """
    key = str(source_id)

    table = await _open_chunk_table()
    if table is None:
        if not chunks:
            # No table and nothing to write: there is nothing to clear either.
            return
        if _db is None:
            logger.warning(
                "Vector store is not initialized — dropping %d chunk(s) of "
                "%s %s on the floor; the index is stale until a rebuild.",
                len(chunks),
                source_kind.value,
                key,
            )
            return
        table = await asyncio.to_thread(_create_chunk_table, len(chunks[0][1]))

    await asyncio.to_thread(table.delete, _source_predicate(source_kind, key))

    if not chunks:
        return

    records = [
        _chunk_record(
            _PendingChunk(
                book_id=book_id,
                source_kind=source_kind,
                source_id=key,
                chunk_index=index,
                text=text,
            ),
            vector,
        )
        for index, (text, vector) in enumerate(chunks)
    ]
    await asyncio.to_thread(table.add, records)


async def delete_by_source(source_kind: SourceKind, source_id: int) -> None:
    """Remove every chunk of one source.

    Used by codex archive (feature ``017``) and internally by
    :func:`upsert_chunks`. Keyed on ``(source_kind, source_id)`` because the
    table is discriminated: a delete never reaches another corpus's rows. A
    no-op when the table does not exist or the source has no chunks.
    """
    table = await _open_chunk_table()
    if table is None:
        return
    await asyncio.to_thread(
        table.delete, _source_predicate(source_kind, str(source_id))
    )


async def delete_by_book(book_id: int) -> None:
    """Remove every chunk of one book, across every source kind.

    Used when a book is destroyed. A no-op when the table does not exist or the
    book has no chunks.
    """
    table = await _open_chunk_table()
    if table is None:
        return
    await asyncio.to_thread(table.delete, f"book_id = {int(book_id)}")


# ---------------------------------------------------------------------------
# Query.
# ---------------------------------------------------------------------------


async def search(
    book_id: int,
    query_vector: Sequence[float],
    kinds: Collection[SourceKind] | None = None,
    limit: int = 10,
) -> list[ChunkHit]:
    """Nearest chunks to ``query_vector`` **within one book**, nearest first.

    - ``book_id`` is a **hard filter applied inside the query**, never a ranking
      preference: a hit from another book is a permission violation, not a worse
      result (``retrieval.md``; US-085.AC-1).
    - ``kinds`` narrows the corpora; ``None`` means every kind.
    - ``limit`` caps the number of hits returned.

    Takes an **already-embedded** query vector rather than query text — a
    narrowing against ``retrieval.md``'s written ``search(book_id, query_text,
    …)`` surface, because ``db/`` may not embed. A service composes
    ``services/embedding.embed_text`` with this call (step 009).

    Returns ``[]`` when the table does not exist yet.
    """
    if limit <= 0:
        return []

    table = await _open_chunk_table()
    if table is None:
        return []

    predicate = f"book_id = {int(book_id)}"
    if kinds is not None:
        values = sorted({kind.value for kind in kinds})
        if not values:
            # Narrowed to no corpus at all: nothing can match.
            return []
        rendered = ", ".join(_sql_string(value) for value in values)
        predicate = f"{predicate} AND source_kind IN ({rendered})"

    def _query() -> list[dict[str, Any]]:
        # ``prefilter=True`` is what makes ``book_id`` a HARD filter: the
        # predicate runs before the nearest-neighbour search, so another book's
        # chunk cannot occupy a slot in the result at all — it is a permission
        # violation, not a worse result (``retrieval.md``).
        return (
            table.search(list(query_vector))
            .where(predicate, prefilter=True)
            .limit(limit)
            .to_list()
        )

    rows = await asyncio.to_thread(_query)

    return [
        ChunkHit(
            source_kind=SourceKind(row["source_kind"]),
            source_id=str(row["source_id"]),
            chunk_index=int(row["chunk_index"]),
            text=str(row["text"]),
            score=float(row["_distance"]),
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Full rebuild.
# ---------------------------------------------------------------------------

_EMBED_BATCH_SIZE = 32
"""Chunks handed to the injected embedder in one call during a full rebuild. A
rebuild is instance-wide, so the whole corpus never goes out in one request."""


async def _collect_chunks(source: VectorSource[Any]) -> list[_PendingChunk]:
    """Walk one corpus's rows and chunk them, in the selector's order."""
    pending: list[_PendingChunk] = []
    for row in await source.row_selector():
        for chunk_index, text in enumerate(source.chunker(row)):
            pending.append(
                _PendingChunk(
                    book_id=int(row.book_id),
                    source_kind=source.source_kind,
                    source_id=str(row.id),
                    chunk_index=chunk_index,
                    text=text,
                )
            )
    return pending


async def _embed_and_insert(table: Any, pending: Sequence[_PendingChunk]) -> int:
    """Embed ``pending`` in batches and insert it; returns the rows written."""
    if not pending:
        return 0

    if _embed_batch is None:
        raise VectorIndexError(
            "The vector index cannot be rebuilt: no embedder was injected at "
            "init_vector, so the chunk texts cannot be embedded."
        )

    written = 0
    for start in range(0, len(pending), _EMBED_BATCH_SIZE):
        batch = pending[start : start + _EMBED_BATCH_SIZE]
        vectors = await _embed_batch([chunk.text for chunk in batch])
        if len(vectors) != len(batch):
            # The embedder is the one thing pairing text to vector by position;
            # a short answer would mis-pair every chunk after the gap, so the
            # rebuild stops instead of writing a silently wrong index.
            raise VectorIndexError(
                f"The embedder returned {len(vectors)} vector(s) for "
                f"{len(batch)} chunk(s); the index would be mis-paired."
            )
        records = [
            _chunk_record(chunk, vector) for chunk, vector in zip(batch, vectors)
        ]
        await asyncio.to_thread(table.add, records)
        written += len(records)

    return written


async def rebuild_index() -> int:
    """Reset the sidecar index and re-embed every registered source.

    Connection contract (FROZEN — feature 007 step 004 / D6): ensure a live
    connection by reusing the module ``_db`` if already initialized, else lazily
    establish it via ``init_vector(get_settings().lancedb_dir)``. This lets a
    test point LanceDB at a throwaway directory by calling
    ``await vector.init_vector(tmp_path / "vector", ...)`` BEFORE
    ``rebuild_index()``.

    Behaviour (step 005): drop every existing table, probe the dimension through
    the injected ``_probe_dimension`` and create the chunk table at the dimension
    the model actually returned, then for each :data:`VECTOR_SOURCE_REGISTRY`
    entry walk its row selector, chunk each row, embed the chunks in batches
    through the injected ``_embed_batch`` and insert them. Returns the **total
    number of chunks written**.

    Raises :class:`VectorIndexError` when it reaches a point where it must embed
    and no embedder was injected at :func:`init_vector`. Raising does not change
    this function's ``-> int`` signature, and neither caller's call shape moves.
    """
    global _db

    # Connection contract (frozen): reuse the live ``_db`` if already
    # initialized, else lazily connect via the configured settings dir.
    if _db is None:
        from app.settings import get_settings

        await init_vector(get_settings().lancedb_dir)

    # Reset the sidecar: drop every existing table (idempotent — drop-if-exists
    # semantics, no error if a table is already absent). Keep blocking lancedb
    # calls off the event loop, mirroring ``init_vector``.
    table_names = await asyncio.to_thread(_db.table_names)
    for name in table_names:
        await asyncio.to_thread(_db.drop_table, name, ignore_missing=True)

    # The dimension is a property of the model, not of configuration, so it is
    # discovered before the table exists and the table is created at whatever the
    # model actually returned (``retrieval.md`` → Vector dimension).
    if _probe_dimension is None:
        raise VectorIndexError(
            "The vector index cannot be rebuilt: no embedder was injected at "
            "init_vector, so the model's vector dimension cannot be probed."
        )

    dimension = await _probe_dimension()
    # Created before anything is indexed, so an empty codex still leaves a
    # usable — merely empty — table behind.
    table = await asyncio.to_thread(_create_chunk_table, dimension, "overwrite")

    indexed = 0
    for source in VECTOR_SOURCE_REGISTRY:
        pending = await _collect_chunks(source)
        indexed += await _embed_and_insert(table, pending)

    logger.info(
        "Vector index rebuilt at dimension %d — %d chunk(s) written.",
        dimension,
        indexed,
    )
    return indexed
