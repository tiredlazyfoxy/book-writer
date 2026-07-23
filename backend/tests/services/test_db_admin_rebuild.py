"""Tests for the admin vector-index rebuild (feature 007, step 004).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 004):
    app.services.db_admin.rebuild_vector_index() -> int
    app.db.vector.rebuild_index() -> int
    app.db.vector.VECTOR_SOURCE_REGISTRY: list   (empty in Stage 1)
    app.db.vector.init_vector(vector_dir: Path) -> None   (existing)
    app.db.import_export_queries.run_vector_rebuild() -> None
    app.services.db_admin.DbAdminError(case, message="")  # attrs .case, .message
    app.services.db_admin.DbAdminErrorCase.no_embedding_provider  # "no-embedding-provider"

Expected values come from the step spec (D6 in context.md) and the DoD, never
from implementation internals:
    - With a VALID embedding designation (`get_embedding_server()` returns a row
      whose `embedding_model` is set), `rebuild_vector_index()` resets the
      sidecar index and returns 0 (Stage-1 empty `VECTOR_SOURCE_REGISTRY`, i.e.
      zero source rows). The reset is idempotent — running twice stays valid.
    - No-provider contract = OPTION (a) RAISE (frozen skeleton): when
      `get_embedding_server()` returns `None`, OR the returned row's
      `embedding_model` is falsy, `rebuild_vector_index()` raises `DbAdminError`
      whose `.case` is `DbAdminErrorCase.no_embedding_provider`.
    - Shared path (D6): `run_vector_rebuild()` delegates to
      `vector.rebuild_index()` so post-import rebuild and the admin button share
      one path.

Test-setup mechanism for a temp LanceDB dir (frozen): call
`await vector.init_vector(tmp_path / "vector")` BEFORE invoking the rebuild in
tests whose path actually reaches it (DoD-1/DoD-2), so `rebuild_index` reuses the
pre-initialized module `_db` and no settings monkeypatch is needed.

The embedding server is faked by monkeypatching the name the service resolves at
call time (`app.db.llm_servers.get_embedding_server`), and the delegation spy by
monkeypatching `app.db.vector.rebuild_index`. Async tests run under
`asyncio_mode = "auto"`.
"""

from pathlib import Path

import pytest

from app.db import import_export_queries, vector
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
# returns a count of 0 (Stage-1 empty VECTOR_SOURCE_REGISTRY -> zero source rows).
async def test_rebuild_valid_designation_returns_zero__DoD1_US020_AC1(
    tmp_path: Path, monkeypatch
):
    await vector.init_vector(tmp_path / "vector")
    _patch_embedding_server(monkeypatch, _valid_designation())

    result = await db_admin.rebuild_vector_index()

    assert result == 0


# DoD-2 (US-020.AC-1 idempotent reset): calling rebuild_vector_index() twice
# leaves the index freshly-reset without error — both calls return 0, no
# exception (the reset is valid regardless of prior state).
async def test_rebuild_twice_is_idempotent__DoD2_US020_AC1(
    tmp_path: Path, monkeypatch
):
    await vector.init_vector(tmp_path / "vector")
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


# DoD-5 (D6 deferral, optional cheap guard): VECTOR_SOURCE_REGISTRY ships empty
# in Stage 1 (no vector-backed source models; embedding bridge deferred).
def test_vector_source_registry_is_empty__DoD5_D6():
    assert vector.VECTOR_SOURCE_REGISTRY == []
