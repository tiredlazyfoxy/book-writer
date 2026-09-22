"""Tests for incremental index maintenance on codex writes (feature 013, step 006).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 006), in
`app.services.codex_index`:
    class IndexStatus(str, enum.Enum) { indexed, dropped, failed }
    class IndexFailureReason(str, enum.Enum) { no_provider, unreachable,
        dimension_mismatch, sidecar_error }
    @dataclass(frozen=True) class IndexOutcome
        status: IndexStatus, chunk_count: int = 0,
        reason: IndexFailureReason | None = None
    async def index_entry(entry: CodexEntry) -> IndexOutcome
    async def drop_entry(entry: CodexEntry) -> IndexOutcome
plus the step-002 codex service entry points (`create_entry` / `update_entry`),
the step-004 embedding surface (`is_available` / `embed_batch` /
`EmbeddingError` / `EmbeddingErrorReason`) and the step-005 sidecar
(`init_vector` / `get_table_dimension` / `upsert_chunks` / `delete_by_source` /
`search` / `SourceKind` / `VectorIndexError`).

Expected values come from the step spec (006.incremental-index.md -> Interface
intent + Definition of done, plus 006.context.md and retrieval.md as cited
there), never from implementation internals:
    - a create writes that entry's chunks to the sidecar under the `codex_entry`
      source kind, the entry's book id and its STRINGIFIED id (DoD-1);
    - an edit DELETES the previous chunks and inserts the new ones, so
      shortening a body leaves no orphan chunk from the longer version (DoD-2);
    - the index write happens AFTER the SQLite write: at the moment the indexer
      is invoked the entry is already readable from the db with its new content
      (DoD-3);
    - with no embedding provider the create and the update both succeed and
      return their DTOs, and the index is simply not updated -- the operation
      reports `failed` with reason `no-provider` (DoD-4);
    - an unreachable embedding server is caught and LOGGED (a warning naming the
      entry and the reason), never raised, and the save still succeeds (DoD-5);
    - vectors whose length differs from the live table's dimension REFUSE the
      index write: the save succeeds and nothing malformed reaches the sidecar
      (DoD-6);
    - a sidecar error (the table missing, the write failing) is caught, logged
      and does not surface (DoD-7);
    - indexing an ARCHIVED entry drops its chunks instead of inserting any
      (DoD-8);
    - the index operation completes before the codex service returns -- nothing
      is scheduled and no asyncio task is left pending (DoD-9);
    - neither operation ever raises, for any of the failure modes above
      (DoD-10).
DoD-11 is [manual/live] (a real embedding server) and has no test here.

No network: only the MODEL CALL is faked. `app.services.embedding`'s
`embed_batch` / `is_available` are monkeypatched (namespace attributes on the
module `codex_index` imports), while LanceDB runs for real against a per-test
`tmp_path` vector dir, so "nothing malformed was inserted" is asserted against
the sidecar's actual contents rather than against a return value. Async tests
use asyncio_mode = "auto"; the `db` fixture (conftest) supplies an initialized
throwaway temp-SQLite engine, and User / Book rows are seeded through the db
layer with `BookAccess` built directly, the `tests/services/test_codex.py`
shape.
"""

import asyncio
import logging
from collections.abc import Sequence
from pathlib import Path

import pytest

from app.db import books, codex_entries, users, vector
from app.db.engine import DbConfig
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.schemas.codex import (
    CreateCodexEntryRequest,
    UpdateCodexEntryRequest,
)
from app.models.user import User, UserRole
from app.services import codex as codex_service
from app.services import codex_index
from app.services import embedding as embedding_service
from app.services.authz import AccessRole, BookAccess
from app.services.embedding import EmbeddingError, EmbeddingErrorReason

# ---------------------------------------------------------------------------
# Fixed vectors + seeding helpers
# ---------------------------------------------------------------------------

DIM = 4
V_A: list[float] = [1.0, 0.0, 0.0, 0.0]


def _vector(dimension: int) -> list[float]:
    return [1.0] + [0.0] * (dimension - 1)


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


def _access(book_id: int, user_id: int) -> BookAccess:
    """A BookAccess built directly -- the frozen dataclass, no resolve, no HTTP."""
    return BookAccess(
        book_id=book_id,
        user_id=user_id,
        role=AccessRole.owner,
        book_state=BookState.active,
        visibility=Visibility.private,
        collaboration_mode=CollaborationMode.free,
    )


async def _seed_context(username: str) -> tuple[User, Book, BookAccess]:
    owner = await _seed_user(username)
    book = await _seed_book(owner.id)
    return owner, book, _access(book.id, owner.id)


async def _seed_entry_row(
    book_id: int,
    author_id: int,
    *,
    kind: CodexKind = CodexKind.character,
    name: str | None = "Seeded",
    body: str = "seeded body",
    archived: bool = False,
) -> CodexEntry:
    """A CodexEntry inserted straight through the db layer (bypassing the rules)."""
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


async def _init_sidecar(tmp_path: Path, name: str = "vector") -> None:
    """Connect the real LanceDB sidecar to this test's own vector dir."""
    await vector.init_vector(tmp_path / name)


async def _chunks_for(book_id: int, source_id: int) -> list[vector.ChunkHit]:
    """Every chunk the sidecar actually holds for one source, in index order."""
    hits = await vector.search(book_id, V_A, limit=100)
    return sorted(
        (hit for hit in hits if hit.source_id == str(source_id)),
        key=lambda hit: hit.chunk_index,
    )


# ---------------------------------------------------------------------------
# Embedding doubles -- the ONLY faked thing (no network anywhere)
# ---------------------------------------------------------------------------


def _arm_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider IS configured (the failure under test is a later one)."""

    async def _is_available() -> bool:
        return True

    monkeypatch.setattr(embedding_service, "is_available", _is_available)


def _arm_embedder(
    monkeypatch: pytest.MonkeyPatch,
    dimension: int = DIM,
    calls: list[list[str]] | None = None,
) -> None:
    """A working embedder returning one fixed `dimension`-long vector per text."""

    async def _embed_batch(texts: Sequence[str]) -> list[list[float]]:
        if calls is not None:
            calls.append(list(texts))
        return [_vector(dimension) for _ in texts]

    monkeypatch.setattr(embedding_service, "embed_batch", _embed_batch)
    _arm_available(monkeypatch)


def _arm_failing_embedder(
    monkeypatch: pytest.MonkeyPatch, reason: EmbeddingErrorReason
) -> None:
    """An embedder that fails the step-004 way: a typed `EmbeddingError`."""

    async def _embed_batch(texts: Sequence[str]) -> list[list[float]]:
        raise EmbeddingError(reason, f"embedding failed: {reason.value}")

    monkeypatch.setattr(embedding_service, "embed_batch", _embed_batch)
    _arm_available(monkeypatch)


# ---------------------------------------------------------------------------
# Log assertion helper
# ---------------------------------------------------------------------------


def _warned_about(caplog: pytest.LogCaptureFixture, entry_id: int, reason) -> bool:
    """True when a WARNING record from an `app.*` logger names entry + reason."""
    for record in caplog.records:
        if record.levelno < logging.WARNING:
            continue
        if not record.name.startswith("app."):
            continue
        carried = " ".join(
            [record.getMessage()] + [str(value) for value in record.__dict__.values()]
        ).lower()
        names_entry = str(entry_id) in carried
        names_reason = reason.value.lower() in carried or reason.name.lower() in carried
        if names_entry and names_reason:
            return True
    return False


# ---------------------------------------------------------------------------
# DoD-1 — a create lands in the sidecar, discriminated and book-scoped
# ---------------------------------------------------------------------------


# DoD-1 (retrieval.md -> Incremental maintenance; UC-078 / US-089.AC-1):
# creating an entry writes that entry's chunks to the sidecar with the
# `codex_entry` source kind, the entry's book id and its STRINGIFIED id.
async def test_create_writes_chunks_to_the_sidecar__DoD1(
    db: DbConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    await _init_sidecar(tmp_path)
    owner, book, access = await _seed_context("indexer-create")
    other_book = await _seed_book(owner.id)
    _arm_embedder(monkeypatch)

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Marek", body="a quiet smith"
        ),
    )

    hits = await _chunks_for(book.id, int(created.id))

    assert hits, "the created entry's chunks must be in the sidecar"
    for hit in hits:
        assert hit.source_kind == vector.SourceKind.codex_entry
        assert isinstance(hit.source_id, str)
        assert hit.source_id == str(created.id)
    joined = "\n".join(hit.text for hit in hits)
    assert "a quiet smith" in joined

    # book id: the chunks belong to this book and to no other.
    assert await vector.search(other_book.id, V_A, limit=100) == []

    # The operation reports the success it performed.
    stored = await codex_entries.get_by_id(int(created.id))
    assert stored is not None
    outcome = await codex_index.index_entry(stored)
    assert outcome.status is codex_index.IndexStatus.indexed
    assert outcome.reason is None
    assert outcome.chunk_count == len(hits)


# ---------------------------------------------------------------------------
# DoD-2 — an edit deletes the previous chunks and inserts the new ones
# ---------------------------------------------------------------------------


# DoD-2 (retrieval.md -> delete-then-reinsert): editing an entry removes the
# previous chunks and inserts the new ones, so shortening a long body leaves NO
# orphan chunk from the longer version.
async def test_edit_replaces_chunks_leaving_no_orphans__DoD2(
    db: DbConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    await _init_sidecar(tmp_path)
    owner, book, access = await _seed_context("indexer-edit")
    _arm_embedder(monkeypatch)

    paragraphs = [f"P{index:02d} " + "x" * 145 for index in range(20)]
    long_body = "\n\n".join(paragraphs)
    assert len(long_body) > vector.CHUNK_SIZE_CHARS  # premise: more than one chunk

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Long One", body=long_body
        ),
    )
    before = await _chunks_for(book.id, int(created.id))
    assert len(before) > 1, "the long body must produce more than one chunk"

    updated = await codex_service.update_entry(
        access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name="Long One",
            body="a short body",
            expected_modified_at=created.modified_at,
        ),
    )
    assert updated.body == "a short body"

    after = await _chunks_for(book.id, int(created.id))

    assert len(after) == 1
    assert after[0].chunk_index == 0
    assert "a short body" in after[0].text
    # No orphan from the longer version survives anywhere in the sidecar.
    everything = "\n".join(
        hit.text for hit in await vector.search(book.id, V_A, limit=100)
    )
    for paragraph in paragraphs:
        assert paragraph not in everything


# ---------------------------------------------------------------------------
# DoD-3 — ordering: the db write commits BEFORE the indexer is invoked
# ---------------------------------------------------------------------------


# DoD-3 (006.context.md -> Ordering inside services/codex.py): at the moment the
# indexer is invoked, the entry is already readable from the db WITH ITS NEW
# CONTENT -- asserted from inside the indexer double, on both the create and the
# update path.
async def test_indexer_sees_the_committed_entry__DoD3(
    db: DbConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    await _init_sidecar(tmp_path)
    owner, book, access = await _seed_context("indexer-order")

    seen: list[tuple[str | None, str]] = []

    async def _spy(entry: CodexEntry) -> codex_index.IndexOutcome:
        stored = await codex_entries.get_by_id(entry.id)
        assert stored is not None, "the entry must be readable from the db already"
        seen.append((stored.name, stored.body))
        # the row handed to the indexer carries the new content too
        assert entry.body == stored.body
        return codex_index.IndexOutcome(
            status=codex_index.IndexStatus.indexed, chunk_count=1
        )

    monkeypatch.setattr(codex_index, "index_entry", _spy)

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Ordered", body="created body"
        ),
    )

    assert seen == [("Ordered", "created body")]

    await codex_service.update_entry(
        access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name="Ordered",
            body="edited body",
            expected_modified_at=created.modified_at,
        ),
    )

    assert len(seen) == 2
    assert seen[1] == ("Ordered", "edited body")


# ---------------------------------------------------------------------------
# DoD-4 — no embedding provider: both saves succeed, the index is not updated
# ---------------------------------------------------------------------------


# DoD-4 (retrieval.md -> "Index maintenance never blocks the author's save";
# US-079.AC-1): with NO embedding provider configured (no designated server row
# at all -- the real embedding service, nothing mocked), the create and the
# update both succeed and return their DTOs, the sidecar stays empty, and the
# index operation reports `failed` with reason `no-provider`.
async def test_no_provider_leaves_both_saves_successful__DoD4(
    db: DbConfig, tmp_path: Path
):
    await _init_sidecar(tmp_path)
    owner, book, access = await _seed_context("indexer-noprovider")

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Saved", body="created body"
        ),
    )

    assert created.name == "Saved"
    assert created.body == "created body"
    assert created.book_id == str(book.id)

    updated = await codex_service.update_entry(
        access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name="Saved",
            body="edited body",
            expected_modified_at=created.modified_at,
        ),
    )

    assert updated.id == created.id
    assert updated.body == "edited body"
    # The save really landed.
    stored = await codex_entries.get_by_id(int(created.id))
    assert stored is not None
    assert stored.body == "edited body"

    # The index was simply not updated: no chunk table was ever created.
    assert await vector.get_table_dimension() is None

    # ...and the operation names the cause rather than merely not raising.
    outcome = await codex_index.index_entry(stored)
    assert outcome.status is codex_index.IndexStatus.failed
    assert outcome.reason is codex_index.IndexFailureReason.no_provider
    assert outcome.chunk_count == 0


# ---------------------------------------------------------------------------
# DoD-5 — an unreachable embedding server is logged, not raised
# ---------------------------------------------------------------------------


# DoD-5 (retrieval.md -> Failure modes, row 2): when the embedding server is
# unreachable the save still succeeds, and the failure is LOGGED (a warning
# naming the entry and the reason) rather than raised.
async def test_unreachable_embedder_is_logged_not_raised__DoD5(
    db: DbConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    await _init_sidecar(tmp_path)
    owner, book, access = await _seed_context("indexer-unreachable")
    _arm_failing_embedder(monkeypatch, EmbeddingErrorReason.unreachable)

    with caplog.at_level(logging.DEBUG):
        created = await codex_service.create_entry(
            access,
            owner,
            CreateCodexEntryRequest(
                kind=CodexKind.character, name="Still Saved", body="created body"
            ),
        )

    assert created.body == "created body"

    stored = await codex_entries.get_by_id(int(created.id))
    assert stored is not None

    # The failure is reported as the specific reason, and nothing was indexed.
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        outcome = await codex_index.index_entry(stored)

    assert outcome.status is codex_index.IndexStatus.failed
    assert outcome.reason is codex_index.IndexFailureReason.unreachable
    assert outcome.chunk_count == 0
    assert await vector.get_table_dimension() is None
    assert _warned_about(
        caplog, stored.id, codex_index.IndexFailureReason.unreachable
    ), "the unreachable embedding server must be logged with the entry id and reason"


# ---------------------------------------------------------------------------
# DoD-6 — a dimension mismatch refuses the index write
# ---------------------------------------------------------------------------


# DoD-6 (retrieval.md -> Failure modes, row 3): when the embedder returns vectors
# of a different length than the LIVE TABLE's dimension, the index write is
# refused, the save still succeeds, and NOTHING MALFORMED is inserted -- asserted
# against the sidecar's actual contents, not against the return value.
async def test_dimension_mismatch_refuses_the_index_write__DoD6(
    db: DbConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    await _init_sidecar(tmp_path)
    owner, book, access = await _seed_context("indexer-mismatch")

    # A live table at dimension DIM, created by a first, healthy index write.
    _arm_embedder(monkeypatch, dimension=DIM)
    settled = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Settled", body="settled body"
        ),
    )
    assert await vector.get_table_dimension() == DIM
    assert await _chunks_for(book.id, int(settled.id))

    # Now the embedder answers with vectors of a different length.
    _arm_embedder(monkeypatch, dimension=DIM * 2)

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Mismatched", body="mismatched body"
        ),
    )

    # The save succeeded.
    assert created.body == "mismatched body"
    stored = await codex_entries.get_by_id(int(created.id))
    assert stored is not None
    assert stored.body == "mismatched body"

    # Nothing malformed was inserted: the table still reports the original
    # dimension, the offending entry has no chunks, and the healthy entry's
    # chunks are untouched.
    assert await vector.get_table_dimension() == DIM
    assert await _chunks_for(book.id, int(created.id)) == []
    everything = await vector.search(book.id, V_A, limit=100)
    assert {hit.source_id for hit in everything} == {str(settled.id)}
    assert "mismatched body" not in "\n".join(hit.text for hit in everything)

    # ...and the refusal names the dimension mismatch.
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        outcome = await codex_index.index_entry(stored)

    assert outcome.status is codex_index.IndexStatus.failed
    assert outcome.reason is codex_index.IndexFailureReason.dimension_mismatch
    assert outcome.chunk_count == 0
    assert await _chunks_for(book.id, int(created.id)) == []
    assert _warned_about(
        caplog, stored.id, codex_index.IndexFailureReason.dimension_mismatch
    ), "the dimension mismatch must be logged with the entry id and reason"


# ---------------------------------------------------------------------------
# DoD-7 — a sidecar error is caught, logged, and does not surface
# ---------------------------------------------------------------------------


# DoD-7 (retrieval.md -> recoverable by rebuild): a failing sidecar WRITE is
# caught, logged with the entry id and the reason, and does not surface to the
# caller -- the codex save still returns its DTO.
async def test_sidecar_write_failure_is_caught_and_logged__DoD7(
    db: DbConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    await _init_sidecar(tmp_path)
    owner, book, access = await _seed_context("indexer-sidecar-write")
    _arm_embedder(monkeypatch)

    async def _boom(*args, **kwargs) -> None:
        raise vector.VectorIndexError("the chunk write failed")

    monkeypatch.setattr(vector, "upsert_chunks", _boom)

    with caplog.at_level(logging.DEBUG):
        created = await codex_service.create_entry(
            access,
            owner,
            CreateCodexEntryRequest(
                kind=CodexKind.character, name="Sidecar", body="sidecar body"
            ),
        )

    assert created.body == "sidecar body"

    stored = await codex_entries.get_by_id(int(created.id))
    assert stored is not None

    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        outcome = await codex_index.index_entry(stored)

    assert outcome.status is codex_index.IndexStatus.failed
    assert outcome.reason is codex_index.IndexFailureReason.sidecar_error
    assert outcome.chunk_count == 0
    assert _warned_about(
        caplog, stored.id, codex_index.IndexFailureReason.sidecar_error
    ), "the sidecar write failure must be logged with the entry id and reason"


# DoD-7: a failing sidecar READ (the table missing when the dimension is asked
# for) is caught the same way -- reported as `sidecar-error`, logged, not raised.
async def test_sidecar_read_failure_is_caught_and_logged__DoD7(
    db: DbConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    await _init_sidecar(tmp_path)
    owner, book, _ = await _seed_context("indexer-sidecar-read")
    entry = await _seed_entry_row(book.id, owner.id, body="read failure body")
    _arm_embedder(monkeypatch)

    async def _boom(*args, **kwargs):
        raise RuntimeError("the chunk table is missing")

    monkeypatch.setattr(vector, "get_table_dimension", _boom)

    with caplog.at_level(logging.DEBUG):
        outcome = await codex_index.index_entry(entry)

    assert outcome.status is codex_index.IndexStatus.failed
    assert outcome.reason is codex_index.IndexFailureReason.sidecar_error
    assert outcome.chunk_count == 0
    assert _warned_about(
        caplog, entry.id, codex_index.IndexFailureReason.sidecar_error
    ), "the sidecar read failure must be logged with the entry id and reason"


# DoD-7: the drop operation has the same contract -- a failing delete is caught,
# logged and reported, never raised.
async def test_sidecar_failure_on_drop_is_caught_and_logged__DoD7(
    db: DbConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    await _init_sidecar(tmp_path)
    owner, book, _ = await _seed_context("indexer-sidecar-drop")
    entry = await _seed_entry_row(book.id, owner.id, body="drop failure body")

    async def _boom(*args, **kwargs) -> None:
        raise OSError("the vector directory is gone")

    monkeypatch.setattr(vector, "delete_by_source", _boom)

    with caplog.at_level(logging.DEBUG):
        outcome = await codex_index.drop_entry(entry)

    assert outcome.status is codex_index.IndexStatus.failed
    assert outcome.reason is codex_index.IndexFailureReason.sidecar_error
    assert outcome.chunk_count == 0
    assert _warned_about(
        caplog, entry.id, codex_index.IndexFailureReason.sidecar_error
    ), "the failing drop must be logged with the entry id and reason"


# ---------------------------------------------------------------------------
# DoD-8 — an archived entry is dropped, never indexed
# ---------------------------------------------------------------------------


# DoD-8 (retrieval.md -> archived entries leave the index): indexing an ARCHIVED
# entry drops its chunks instead of inserting any -- the previously indexed
# chunks disappear, the embedder is never called, and the outcome is `dropped`.
async def test_archived_entry_is_dropped_not_indexed__DoD8(
    db: DbConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    await _init_sidecar(tmp_path)
    owner, book, _ = await _seed_context("indexer-archived")
    entry = await _seed_entry_row(book.id, owner.id, body="indexed then archived")

    calls: list[list[str]] = []
    _arm_embedder(monkeypatch, calls=calls)

    indexed = await codex_index.index_entry(entry)
    assert indexed.status is codex_index.IndexStatus.indexed
    assert await _chunks_for(book.id, entry.id)
    assert len(calls) == 1

    # The entry becomes archived.
    entry.archived = True
    await codex_entries.update(entry)

    outcome = await codex_index.index_entry(entry)

    assert outcome.status is codex_index.IndexStatus.dropped
    assert outcome.reason is None
    assert outcome.chunk_count == 0
    assert await _chunks_for(book.id, entry.id) == []
    # Nothing was embedded for the archived entry.
    assert len(calls) == 1


# DoD-8: the drop operation itself reports success (`dropped`) and removes only
# that entry's chunks -- the mechanism 017.codex-archive-restore reuses.
async def test_drop_entry_removes_only_that_entrys_chunks__DoD8(
    db: DbConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    await _init_sidecar(tmp_path)
    owner, book, _ = await _seed_context("indexer-drop")
    doomed = await _seed_entry_row(book.id, owner.id, name="Doomed", body="doomed body")
    kept = await _seed_entry_row(book.id, owner.id, name="Kept", body="kept body")
    _arm_embedder(monkeypatch)

    await codex_index.index_entry(doomed)
    await codex_index.index_entry(kept)

    outcome = await codex_index.drop_entry(doomed)

    assert outcome.status is codex_index.IndexStatus.dropped
    assert outcome.reason is None
    assert outcome.chunk_count == 0
    assert await _chunks_for(book.id, doomed.id) == []
    assert await _chunks_for(book.id, kept.id)

    # Dropping chunks that are no longer there is a success, not a failure.
    again = await codex_index.drop_entry(doomed)
    assert again.status is codex_index.IndexStatus.dropped
    assert again.reason is None


# ---------------------------------------------------------------------------
# DoD-9 — the index completes before the service returns; nothing is scheduled
# ---------------------------------------------------------------------------


# DoD-9 (retrieval.md -> "No background job queue is introduced"): the index
# operation completes BEFORE the codex service returns -- the embedder has
# already been called and the chunks are already searchable at the moment the
# call returns, and no asyncio task is left pending afterwards.
async def test_index_completes_before_the_service_returns__DoD9(
    db: DbConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    await _init_sidecar(tmp_path)
    owner, book, access = await _seed_context("indexer-inline")
    calls: list[list[str]] = []
    _arm_embedder(monkeypatch, calls=calls)

    before_tasks = asyncio.all_tasks()

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Inline", body="created inline"
        ),
    )

    # Already embedded, with no further awaiting by this test.
    assert len(calls) == 1
    assert {task for task in asyncio.all_tasks() if not task.done()} <= before_tasks

    updated = await codex_service.update_entry(
        access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name="Inline",
            body="edited inline",
            expected_modified_at=created.modified_at,
        ),
    )

    assert len(calls) == 2
    assert {task for task in asyncio.all_tasks() if not task.done()} <= before_tasks

    # ...and the sidecar already holds the edited content.
    hits = await _chunks_for(book.id, int(updated.id))
    assert "edited inline" in "\n".join(hit.text for hit in hits)


# ---------------------------------------------------------------------------
# DoD-10 — neither operation ever raises, for any failure mode
# ---------------------------------------------------------------------------


# DoD-10 (never-raise contract): every failure mode -- no provider, unreachable,
# dimension mismatch and a sidecar error -- comes back as an IndexOutcome naming
# its reason instead of propagating an exception.
@pytest.mark.parametrize(
    "mode, expected_reason",
    [
        ("no_provider", codex_index.IndexFailureReason.no_provider),
        ("unreachable", codex_index.IndexFailureReason.unreachable),
        ("dimension_mismatch", codex_index.IndexFailureReason.dimension_mismatch),
        ("sidecar_error", codex_index.IndexFailureReason.sidecar_error),
    ],
)
async def test_index_entry_never_raises_for_any_failure_mode__DoD10(
    mode: str,
    expected_reason,
    db: DbConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    await _init_sidecar(tmp_path)
    owner, book, _ = await _seed_context(f"indexer-never-raise-{mode}")

    # A live table at DIM, so the dimension check has something to compare to.
    warmup = await _seed_entry_row(book.id, owner.id, name="Warm", body="warm body")
    _arm_embedder(monkeypatch, dimension=DIM)
    await codex_index.index_entry(warmup)

    entry = await _seed_entry_row(
        book.id, owner.id, name="Failing", body="failing body"
    )

    if mode == "no_provider":
        _arm_failing_embedder(monkeypatch, EmbeddingErrorReason.no_provider)
    elif mode == "unreachable":
        _arm_failing_embedder(monkeypatch, EmbeddingErrorReason.unreachable)
    elif mode == "dimension_mismatch":
        _arm_embedder(monkeypatch, dimension=DIM * 2)
    else:

        async def _boom(*args, **kwargs) -> None:
            raise vector.VectorIndexError("the chunk write failed")

        monkeypatch.setattr(vector, "upsert_chunks", _boom)

    outcome = await codex_index.index_entry(entry)

    assert outcome.status is codex_index.IndexStatus.failed
    assert outcome.reason is expected_reason
    assert outcome.chunk_count == 0


# DoD-10: the drop operation is under the same contract -- a raising sidecar is
# reported, not propagated.
async def test_drop_entry_never_raises__DoD10(
    db: DbConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    await _init_sidecar(tmp_path)
    owner, book, _ = await _seed_context("indexer-drop-never-raise")
    entry = await _seed_entry_row(book.id, owner.id, body="drop body")

    async def _boom(*args, **kwargs) -> None:
        raise ValueError("the delete predicate failed")

    monkeypatch.setattr(vector, "delete_by_source", _boom)

    outcome = await codex_index.drop_entry(entry)

    assert outcome.status is codex_index.IndexStatus.failed
    assert outcome.reason is codex_index.IndexFailureReason.sidecar_error
    assert outcome.chunk_count == 0


# DoD-10: and the never-raise contract holds through the codex service -- a
# failing index leaves a successful save on both write paths.
async def test_failing_index_leaves_the_save_successful__DoD10(
    db: DbConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    await _init_sidecar(tmp_path)
    owner, book, access = await _seed_context("indexer-save-survives")
    _arm_failing_embedder(monkeypatch, EmbeddingErrorReason.unreachable)

    created = await codex_service.create_entry(
        access,
        owner,
        CreateCodexEntryRequest(
            kind=CodexKind.character, name="Survivor", body="created body"
        ),
    )
    updated = await codex_service.update_entry(
        access,
        owner,
        created.id,
        UpdateCodexEntryRequest(
            name="Survivor",
            body="edited body",
            expected_modified_at=created.modified_at,
        ),
    )

    assert updated.body == "edited body"
    stored = await codex_entries.get_by_id(int(created.id))
    assert stored is not None
    assert stored.body == "edited body"
