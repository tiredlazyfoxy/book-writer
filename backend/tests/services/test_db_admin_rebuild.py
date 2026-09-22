"""Tests for the admin vector-index rebuild (feature 007, step 004).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 004):
    app.services.db_admin.rebuild_vector_index() -> int
    app.db.vector.rebuild_index() -> int
    app.db.vector.VECTOR_SOURCE_REGISTRY: list[VectorSource]
        (013.codex step 005: one typed entry, discriminated `codex_entry`)
    app.db.vector.init_vector(vector_dir, embed_batch=None, probe_dimension=None)
        -> None   (013.codex step 005 widened it)
    app.db.import_export_queries.run_vector_rebuild() -> None
    app.services.db_admin.DbAdminError(case, message="")  # attrs .case, .message
    app.services.db_admin.DbAdminErrorCase.no_embedding_provider  # "no-embedding-provider"

Expected values come from the step spec (D6 in context.md) and the DoD, never
from implementation internals:
    - With a VALID embedding designation (`get_embedding_server()` returns a row
      whose `embedding_model` is set), `rebuild_vector_index()` resets the
      sidecar index and returns 0 when there is nothing to index (an empty
      codex). The reset is idempotent — running twice stays valid.
    - No-provider contract = OPTION (a) RAISE (frozen skeleton): when
      `get_embedding_server()` returns `None`, OR the returned row's
      `embedding_model` is falsy, `rebuild_vector_index()` raises `DbAdminError`
      whose `.case` is `DbAdminErrorCase.no_embedding_provider`.
    - Shared path (D6): `run_vector_rebuild()` delegates to
      `vector.rebuild_index()` so post-import rebuild and the admin button share
      one path.

Test-setup mechanism for a temp LanceDB dir: call `init_vector` on a
`tmp_path` dir BEFORE invoking the rebuild in tests whose path actually reaches
it (DoD-1/DoD-2), so `rebuild_index` reuses the pre-initialized module `_db` and
no settings monkeypatch is needed. Since 013.codex step 005 the embedding
callables are INJECTED there (`init_vector(dir, embed_batch=..., probe_
dimension=...)`) and a rebuild that must embed with none injected raises
`vector.VectorIndexError`, so those two tests inject deterministic doubles and
take the `db` fixture to supply an empty codex for the now-populated registry
walk. Only the embedder is mocked; LanceDB runs for real.

The embedding server is faked by monkeypatching the name the service resolves at
call time (`app.db.llm_servers.get_embedding_server`), and the delegation spy by
monkeypatching `app.db.vector.rebuild_index`. Async tests run under
`asyncio_mode = "auto"`.
"""

from collections.abc import Sequence
from pathlib import Path

import pytest

from app.db import import_export_queries, vector
from app.db.engine import DbConfig
from app.models.codex_entry import CodexEntry
from app.models.llm_server import LlmServer
from app.services import db_admin
from app.services.db_admin import DbAdminError, DbAdminErrorCase


def _valid_designation() -> LlmServer:
    """A valid designated embedding server: is_embedding + embedding_model set."""
    return LlmServer(
        name="emb",
        backend_type="openai",
        base_url="http://x",
        is_embedding=True,
        embedding_model="text-embedding-3-small",
    )


def _designation_without_model() -> LlmServer:
    """A designated embedding row whose embedding_model is unset (006 does not
    guarantee it) — the no-provider contract must treat this as no provider."""
    return LlmServer(
        name="emb",
        backend_type="openai",
        base_url="http://x",
        is_embedding=True,
        embedding_model=None,
    )


async def _init_vector_with_doubles(tmp_path: Path, dimension: int = 4) -> None:
    """Connect the sidecar to a temp dir with deterministic embedding doubles.

    013.codex step 005 injects the embedding callables at `init_vector`; a
    `rebuild_index()` that must embed with none injected raises
    `vector.VectorIndexError`, so these tests inject mocks rather than calling
    `init_vector` with one argument. Only the EMBEDDER is mocked — LanceDB runs
    for real against `tmp_path`.
    """

    async def _embed_batch(texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (dimension - 1) for _ in texts]

    async def _probe_dimension() -> int:
        return dimension

    await vector.init_vector(
        tmp_path / "vector",
        embed_batch=_embed_batch,
        probe_dimension=_probe_dimension,
    )


def _patch_embedding_server(monkeypatch, server: LlmServer | None) -> None:
    """Monkeypatch the name the service resolves at call time
    (`app.db.llm_servers.get_embedding_server`) with an async fake returning
    `server` (an `LlmServer` or `None`)."""

    async def _fake_get_embedding_server() -> LlmServer | None:
        return server

    monkeypatch.setattr(
        "app.db.llm_servers.get_embedding_server", _fake_get_embedding_server
    )


# DoD-1 (US-020.AC-1): with a valid embedding designation present,
# rebuild_vector_index() completes, resets/recreates the sidecar index, and
# returns a count of 0 — the `db` fixture supplies an EMPTY codex, so the
# registry walk finds zero source rows (013.codex step 005 populated the
# registry; the intent of this test, "valid designation + nothing to index ->
# 0", is unchanged).
async def test_rebuild_valid_designation_returns_zero__DoD1_US020_AC1(
    db: DbConfig, tmp_path: Path, monkeypatch
):
    await _init_vector_with_doubles(tmp_path)
    _patch_embedding_server(monkeypatch, _valid_designation())

    result = await db_admin.rebuild_vector_index()

    assert result == 0


# DoD-2 (US-020.AC-1 idempotent reset): calling rebuild_vector_index() twice
# leaves the index freshly-reset without error — both calls return 0, no
# exception (the reset is valid regardless of prior state).
async def test_rebuild_twice_is_idempotent__DoD2_US020_AC1(
    db: DbConfig, tmp_path: Path, monkeypatch
):
    await _init_vector_with_doubles(tmp_path)
    _patch_embedding_server(monkeypatch, _valid_designation())

    first = await db_admin.rebuild_vector_index()
    second = await db_admin.rebuild_vector_index()

    assert first == 0
    assert second == 0


# DoD-3 (D6 no-provider contract, case a): no embedding provider designated
# (get_embedding_server() returns None) -> rebuild_vector_index() raises
# DbAdminError with case no_embedding_provider (never silently claims success).
async def test_rebuild_no_provider_raises__DoD3_D6(tmp_path: Path, monkeypatch):
    _patch_embedding_server(monkeypatch, None)

    with pytest.raises(DbAdminError) as excinfo:
        await db_admin.rebuild_vector_index()

    assert excinfo.value.case == DbAdminErrorCase.no_embedding_provider


# DoD-3 (D6 no-provider contract, case b): a designated provider whose
# embedding_model is unset is treated as no provider -> rebuild_vector_index()
# raises DbAdminError with case no_embedding_provider.
async def test_rebuild_unset_embedding_model_raises__DoD3_D6(
    tmp_path: Path, monkeypatch
):
    _patch_embedding_server(monkeypatch, _designation_without_model())

    with pytest.raises(DbAdminError) as excinfo:
        await db_admin.rebuild_vector_index()

    assert excinfo.value.case == DbAdminErrorCase.no_embedding_provider


# DoD-4 (D6 shared path): run_vector_rebuild() delegates to
# vector.rebuild_index() (post-import rebuild and admin rebuild share one path);
# asserted by monkeypatching vector.rebuild_index with a spy and confirming
# run_vector_rebuild invokes it. run_vector_rebuild() returns None (not asserted).
async def test_run_vector_rebuild_delegates_to_rebuild_index__DoD4_D6(monkeypatch):
    calls: list[bool] = []

    async def _spy_rebuild_index() -> int:
        calls.append(True)
        return 0

    monkeypatch.setattr("app.db.vector.rebuild_index", _spy_rebuild_index)

    await import_export_queries.run_vector_rebuild()

    assert calls, "run_vector_rebuild() must delegate to vector.rebuild_index()"


# DoD-5 (D6 deferral) SUPERSEDED by 013.codex step 005 DoD-11/DoD-15: the
# Stage-1 deferral this guard locked in is discharged — VECTOR_SOURCE_REGISTRY
# now holds exactly ONE entry, a typed `VectorSource` (no longer a
# `(model_class, text_extractor)` tuple, so its fields are read BY NAME),
# discriminated `codex_entry` and bound to the CodexEntry model class.
def test_vector_source_registry_holds_codex_entry__DoD5_D6():
    assert len(vector.VECTOR_SOURCE_REGISTRY) == 1

    source = vector.VECTOR_SOURCE_REGISTRY[0]
    assert source.source_kind == "codex_entry"
    assert source.model_class is CodexEntry
