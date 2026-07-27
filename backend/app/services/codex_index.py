"""Codex index maintenance — keep the vector sidecar current on every codex write
(feature 013, step 006).

This module is the **composition** ``docs/architecture/retrieval.md`` places in the
service layer: "the LanceDB session and table handles live in ``db/vector.py``;
``services/embedding.py`` owns the model call; a service composes the two". It
chunks an entry (``db.vector.chunk_codex_entry``), embeds the chunks in one batch
(``services.embedding.embed_batch``), checks the returned vectors against the live
table's dimension (``db.vector.get_table_dimension`` +
``services.embedding.check_dimension``) and replaces that entry's chunks through
the sidecar's delete-then-reinsert upsert (``db.vector.upsert_chunks``).

**The contract that makes this module different from every other service:
it never raises.** Both entry points report success or failure as a *return
value* (:class:`IndexOutcome`). ``retrieval.md``: "Refusing an author's save
because an embedding server is unreachable would make writing a book depend on an
optional subsystem — and the index is derived, so the failure is recoverable by
definition." A failed index leaves a successful save and a stale index, logged at
warning level with the entry id and the reason, recoverable by the next admin
rebuild.

**The archived rule.** An archived entry is never indexed: calling
:func:`index_entry` on one **drops** its chunks instead of inserting any.
Archived entries leave the index rather than being filtered at query time
(``retrieval.md``). :func:`drop_entry` is public for the same rule's sake — it is
what ``017.codex-archive-restore`` calls on archive, so that feature does not
re-derive the rule.

**No background task, no queue.** ``retrieval.md`` rejects a queue explicitly for
a single-instance app over local SQLite: ``services/codex.py`` awaits these calls
inside the request, *after* the db-layer write returns.

**Import direction is one-way.** ``services/codex.py`` imports this module; this
module must **never** import ``services/codex.py``. A shared helper, if one is
ever needed, belongs in ``db/`` or here — never back-imported.

Skeleton (013 step 006): :class:`IndexStatus`, :class:`IndexFailureReason`,
:class:`IndexOutcome`, :data:`_SIDECAR_FAILURE_EXCEPTIONS` and the two function
signatures are the frozen contract.
"""

import enum
import logging
from dataclasses import dataclass

from app.db import vector
from app.models.codex_entry import CodexEntry
from app.services import embedding as embedding_service

logger = logging.getLogger(__name__)


class IndexStatus(str, enum.Enum):
    """What an index operation did — the discriminator of :class:`IndexOutcome`.

    - ``indexed`` — the entry's chunks were embedded and written; the index now
      reflects the stored row.
    - ``dropped`` — the entry's chunks were removed and none were inserted. The
      archived-entry path and :func:`drop_entry`'s success both report this.
    - ``failed`` — nothing was changed in the index (or the change could not be
      completed); ``IndexOutcome.reason`` says why and the failure has been
      logged. **The caller's own operation still succeeded** — this is never an
      error signal for the save.
    """

    indexed = "indexed"
    dropped = "dropped"
    failed = "failed"


class IndexFailureReason(str, enum.Enum):
    """Why an index operation reported ``failed``.

    The first three mirror :class:`app.services.embedding.EmbeddingErrorReason`
    member-for-member (same names, same wire values), so a caught
    ``EmbeddingError`` maps across by value; ``sidecar_error`` covers every
    failure raised by ``db/vector.py`` itself (a missing/unwritable table, a
    failing write — see :data:`_SIDECAR_FAILURE_EXCEPTIONS`).
    """

    no_provider = "no-provider"
    unreachable = "unreachable"
    dimension_mismatch = "dimension-mismatch"
    sidecar_error = "sidecar-error"


@dataclass(frozen=True)
class IndexOutcome:
    """The result of one index operation — returned, never raised.

    - ``status`` — see :class:`IndexStatus`.
    - ``chunk_count`` — how many chunks were written; zero for ``dropped`` and
      for ``failed``.
    - ``reason`` — set **iff** ``status`` is ``failed``; ``None`` otherwise.

    A frozen typed record rather than a bare ``bool`` (or a dict): the caller
    ignores it, but the archived path (``dropped``) and each failure cause are
    materially different outcomes that a test must be able to tell apart.
    Follows ``db/vector.py:ChunkHit`` / ``services/tools.py:ToolDef``.
    """

    status: IndexStatus
    chunk_count: int = 0
    reason: IndexFailureReason | None = None


_SIDECAR_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    vector.VectorIndexError,
    OSError,
    ValueError,
    RuntimeError,
)
"""The exception family a sidecar call may raise, caught as ``sidecar_error``.

Shape copied from ``services/chat_turn.py:_TURN_FAILURE_EXCEPTIONS``. This tuple
belongs **only** around the ``db/vector.py`` calls (``get_table_dimension`` /
``upsert_chunks`` / ``delete_by_source``) — never around ``chunk_codex_entry``,
which is a pure function whose programming errors must keep failing loudly, and
never as a bare ``except Exception`` over the whole body (``006.context.md`` →
"The failure taxonomy to catch"). ``embedding.EmbeddingError`` is caught by name
beside it; step 004 converts every transport/provider failure to that one type.
"""


def _failure_reason(error: embedding_service.EmbeddingError) -> IndexFailureReason:
    """Map an :class:`~app.services.embedding.EmbeddingError` onto this module's
    reason taxonomy **by wire value**.

    The three embedding reasons are mirrored member-for-member here, so the value
    is the mapping and no lookup table can drift out of date. A member this
    module does not know yet degrades to ``unreachable`` — "the call did not
    produce usable vectors" — rather than crashing the never-raise path.
    """
    try:
        return IndexFailureReason(error.reason.value)
    except ValueError:
        return IndexFailureReason.unreachable


def _failed(
    entry: CodexEntry, reason: IndexFailureReason, detail: str
) -> IndexOutcome:
    """Log one index failure at warning level and return it as an outcome.

    The single place a failure becomes a return value. The record names the
    **entry id** and the **reason** so a stale entry is identifiable from the log
    alone, and it says explicitly that the author's save stands: ``retrieval.md``
    — "Refusing an author's save because an embedding server is unreachable would
    make writing a book depend on an optional subsystem — and the index is
    derived, so the failure is recoverable by definition."
    """
    logger.warning(
        "Codex index maintenance failed for entry %s (book %s) with reason %s "
        "(%s). The author's save is unaffected and stands — refusing it because "
        "an optional subsystem failed would make writing a book depend on that "
        "subsystem, and the index is derived, so this is recoverable by "
        "definition: the entry stays stale in the index until the next rebuild.",
        entry.id,
        entry.book_id,
        reason.value,
        detail,
    )
    return IndexOutcome(status=IndexStatus.failed, reason=reason)


async def index_entry(entry: CodexEntry) -> IndexOutcome:
    """Bring the sidecar in line with one **already-stored** codex entry.

    Takes the entry **row** the codex service just wrote — not an id to re-read:
    the caller already holds the freshly stored row, and re-reading would open a
    window where the index and the save disagree.

    The composition: chunk the entry, embed the chunks in **one** batch, check
    the returned vectors against the live table's dimension (skipping the check
    when no table exists yet — the first upsert creates it), then replace the
    entry's chunks through ``vector.upsert_chunks`` with
    ``SourceKind.codex_entry``, the entry's ``book_id`` and its id. The vectors
    pair with the chunks **positionally**, so a batch that comes back with a
    different number of vectors than there were chunks is a failure, not a
    ``zip``-truncation (the guard ``db/vector.py:rebuild_index`` already applies
    on the rebuild path, restated here for the incremental one).

    An **archived** entry is never indexed: it delegates to :func:`drop_entry`
    and reports ``dropped``. An entry with no chunks at all likewise clears the
    index for that source rather than leaving stale rows.

    **Never raises.** Every failure — no configured provider, an unreachable
    embedding server, a dimension mismatch, a sidecar error — is caught, logged
    at warning level with the entry id and the reason, and returned as
    ``IndexOutcome(status=failed, reason=…)``. The index is left stale until the
    next rebuild.
    """
    if entry.archived:
        # The archived rule: an archived entry leaves the index rather than
        # being filtered at query time (``retrieval.md``).
        return await drop_entry(entry)

    # Deliberately UNGUARDED: the chunker is pure, so a failure in it is a
    # programming error that must keep failing loudly rather than being reported
    # as a stale index (``006.context.md`` → "The failure taxonomy to catch").
    chunks = vector.chunk_codex_entry(entry)
    if not chunks:
        # An entry with nothing to embed still clears whatever it left behind.
        return await drop_entry(entry)

    try:
        # One batch for the whole entry — the chunks of one codex entry are
        # small and always embedded together.
        vectors = await embedding_service.embed_batch(chunks)
    except embedding_service.EmbeddingError as exc:
        return _failed(entry, _failure_reason(exc), str(exc))

    if len(vectors) != len(chunks):
        # Position is the only thing pairing a chunk to its vector, so a short or
        # over-long answer would mis-pair every chunk after the gap. The same
        # guard ``db/vector.py:_embed_and_insert`` applies on the rebuild path;
        # here it is a failure reason rather than a raise, because this path
        # never raises. ``unreachable`` is the reason for it: the call did not
        # produce usable vectors, exactly as ``embedding.embed_text`` treats an
        # empty answer to a non-empty input.
        return _failed(
            entry,
            IndexFailureReason.unreachable,
            f"the embedder returned {len(vectors)} vector(s) for "
            f"{len(chunks)} chunk(s), so the chunks could not be paired",
        )

    try:
        dimension = await vector.get_table_dimension()
    except _SIDECAR_FAILURE_EXCEPTIONS as exc:
        return _failed(entry, IndexFailureReason.sidecar_error, str(exc))

    if dimension is not None:
        # Skipped when no table exists yet: the first upsert creates it at the
        # length of the vectors in hand, so there is nothing to disagree with.
        try:
            embedding_service.check_dimension(vectors, dimension)
        except embedding_service.EmbeddingError as exc:
            return _failed(entry, _failure_reason(exc), str(exc))

    try:
        # Delete-then-reinsert, inside the sidecar: shortening a body can never
        # leave an orphan chunk from the longer version.
        await vector.upsert_chunks(
            entry.book_id,
            vector.SourceKind.codex_entry,
            entry.id,
            list(zip(chunks, vectors)),
        )
    except _SIDECAR_FAILURE_EXCEPTIONS as exc:
        return _failed(entry, IndexFailureReason.sidecar_error, str(exc))

    return IndexOutcome(status=IndexStatus.indexed, chunk_count=len(chunks))


async def drop_entry(entry: CodexEntry) -> IndexOutcome:
    """Remove one entry's chunks from the sidecar.

    The maintenance-table row ``retrieval.md`` assigns to archiving: an archived
    entry leaves the index rather than being filtered at query time. Public so
    ``017.codex-archive-restore`` calls it on archive without re-deriving the
    rule, and used internally by :func:`index_entry` whenever the entry is not
    indexable. Takes the entry **row** for symmetry with :func:`index_entry` and
    so the log line can name the book as well as the entry.

    Removing chunks that are not there is a success, not a failure — the drop is
    idempotent (``vector.delete_by_source`` is a no-op on a missing table or an
    unindexed source), so a never-indexed entry reports ``dropped`` too.

    **Never raises**, on the same terms as :func:`index_entry`: a sidecar failure
    is logged and returned as ``IndexOutcome(status=failed,
    reason=sidecar_error)``.
    """
    try:
        await vector.delete_by_source(vector.SourceKind.codex_entry, entry.id)
    except _SIDECAR_FAILURE_EXCEPTIONS as exc:
        return _failed(entry, IndexFailureReason.sidecar_error, str(exc))

    # Idempotent: removing chunks that were never there is a success, so a
    # never-indexed entry reports ``dropped`` exactly like an indexed one.
    return IndexOutcome(status=IndexStatus.dropped)
