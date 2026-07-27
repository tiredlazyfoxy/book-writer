"""Tests for the embedding service (feature 013.codex, step 004).

Bound to the frozen skeleton (status.md -> Skeleton -> Step 004):

    app.services.embedding  (NEW):
        class EmbeddingErrorReason(str, enum.Enum)
            no_provider="no-provider", unreachable="unreachable",
            dimension_mismatch="dimension-mismatch"
        class EmbeddingError(Exception)  __init__(reason, message="") -> .reason/.message
        async def is_available() -> bool
        async def embed_batch(texts: Sequence[str]) -> list[list[float]]
        async def embed_text(text: str) -> list[float]
        async def probe_dimension() -> int
        def check_dimension(vectors, expected_dimension) -> None   # sync

    Patch seams named by the skeleton (namespace imports):
        app.db.llm_servers.get_embedding_server
        app.services.llm_servers.create_model_client

Expected values come from the step spec ONLY
(`docs/plans/013.codex/004.embedding-service.md` -> Interface intent + DoD,
plus `004.context.md`), never from implementation internals.

Test approach fixed by the step context: **no network**. The designated-server
lookup and the client factory are monkeypatched; the factory returns an
async-context-manager double whose `embed` / `embed_batch` are scripted and
whose `__aenter__` / `__aexit__` are observable. `$ENV` key resolution is NOT
mocked -- it is driven through `monkeypatch.setenv` / `delenv` so the real
`resolve_env_ref` semantics are exercised (DoD-4, DoD-5).

DoD-12 is `[manual/live]` (a real configured embedding server) and has no test
here by design.

Async tests need no decorator (`asyncio_mode = "auto"`). No database is
touched: the only db-layer call this module makes is mocked out.
"""

import aiohttp
import pytest
from llm import LLMError

from app.models.llm_server import LlmServer
from app.services import embedding

# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


class _FakeEmbedClient:
    """Stand-in for ``llm.LLMClient``, used as an async context manager.

    `llm`'s clients expose ``embed(text)`` and ``embed_batch(texts)``; both are
    scripted here so a test does not have to know which one the module reaches
    for. ``entered`` / ``exited`` flag the async-context-manager lifecycle so a
    test can assert the session was closed on every path (DoD-9).
    """

    def __init__(self, *, vectors=None, dimension=None, exc=None):
        self._vectors = vectors
        self._dimension = dimension
        self._exc = exc
        self.entered = False
        self.exited = False
        self.embed_calls: list[str] = []
        self.embed_batch_calls: list[list[str]] = []

    # -- lifecycle ---------------------------------------------------------

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True
        return False

    # -- observation -------------------------------------------------------

    @property
    def call_count(self) -> int:
        return len(self.embed_calls) + len(self.embed_batch_calls)

    # -- embedding surface -------------------------------------------------

    def _batch_for(self, texts) -> list[list[float]]:
        if self._vectors is not None:
            return [list(v) for v in self._vectors]
        return [[0.5] * int(self._dimension) for _ in texts]

    async def embed(self, text, *, options=None):
        self.embed_calls.append(text)
        if self._exc is not None:
            raise self._exc
        return self._batch_for([text])[0]

    async def embed_batch(self, texts, *, options=None):
        received = list(texts)
        self.embed_batch_calls.append(received)
        if self._exc is not None:
            raise self._exc
        return self._batch_for(received)


class _RecordingFactory:
    """Stand-in for ``create_model_client(server, resolved_key, model)``.

    Records every construction so a test can assert the factory was NOT called
    (DoD-1, DoD-3, DoD-8) and can inspect what reached client construction
    (DoD-4).
    """

    def __init__(self, client: _FakeEmbedClient | None = None):
        self.client = client
        self.calls: list[tuple] = []

    def __call__(self, server, resolved_key, model):
        self.calls.append((server, resolved_key, model))
        return self.client


def _server(
    *,
    embedding_model: str | None = "text-embedding-3-small",
    api_key: str | None = "sk-stored-literal",
    backend_type: str = "openai",
) -> LlmServer:
    """A designated embedding server row (constructed in memory, never stored)."""
    return LlmServer(
        name="Embedder",
        backend_type=backend_type,
        base_url="https://api.example.com/v1",
        api_key=api_key,
        enabled_models="[]",
        is_active=True,
        is_embedding=True,
        embedding_model=embedding_model,
    )


def _install_server(monkeypatch, server: LlmServer | None) -> None:
    """Monkeypatch the designated-server lookup to yield ``server``."""

    async def _get_embedding_server():
        return server

    monkeypatch.setattr(
        "app.db.llm_servers.get_embedding_server", _get_embedding_server
    )


def _install_factory(
    monkeypatch, client: _FakeEmbedClient | None = None
) -> _RecordingFactory:
    """Monkeypatch the client factory seam and return the recorder."""
    factory = _RecordingFactory(client)
    monkeypatch.setattr("app.services.llm_servers.create_model_client", factory)
    return factory


# ---------------------------------------------------------------------------
# DoD-1 -- no designated embedding server
# ---------------------------------------------------------------------------


# DoD-1 (retrieval.md -> Failure modes, row 1): with NO designated embedding
# server the batch embed raises the no-provider reason and never constructs a
# client.
async def test_batch_embed_without_designated_server_raises_no_provider__DoD1(
    monkeypatch,
):
    _install_server(monkeypatch, None)
    factory = _install_factory(monkeypatch, _FakeEmbedClient(dimension=3))

    with pytest.raises(embedding.EmbeddingError) as exc:
        await embedding.embed_batch(["a chunk of text"])

    assert exc.value.reason == embedding.EmbeddingErrorReason.no_provider
    assert factory.calls == []


# ---------------------------------------------------------------------------
# DoD-2 -- designated row with no usable embedding_model
# ---------------------------------------------------------------------------


# DoD-2 (retrieval.md -> Dependency): a designated server whose
# `embedding_model` is empty, whitespace-only or absent carries no provider, so
# the batch embed raises the no-provider reason.
@pytest.mark.parametrize("model_value", ["", "   ", "\t\n ", None])
async def test_batch_embed_with_blank_embedding_model_raises_no_provider__DoD2(
    monkeypatch, model_value
):
    _install_server(monkeypatch, _server(embedding_model=model_value))
    factory = _install_factory(monkeypatch, _FakeEmbedClient(dimension=3))

    with pytest.raises(embedding.EmbeddingError) as exc:
        await embedding.embed_batch(["a chunk of text"])

    assert exc.value.reason == embedding.EmbeddingErrorReason.no_provider
    assert factory.calls == []


# ---------------------------------------------------------------------------
# DoD-3 -- the availability probe
# ---------------------------------------------------------------------------


# DoD-3 (retrieval.md -> Failure modes): the availability probe reports False
# when no row is designated, and never contacts the client.
async def test_is_available_false_without_designated_server__DoD3(monkeypatch):
    _install_server(monkeypatch, None)
    client = _FakeEmbedClient(dimension=3)
    factory = _install_factory(monkeypatch, client)

    assert await embedding.is_available() is False
    assert factory.calls == []
    assert client.call_count == 0
    assert client.entered is False


# DoD-3: the availability probe reports False when the designated row's
# `embedding_model` is blank/absent, and never contacts the client.
@pytest.mark.parametrize("model_value", ["", "   ", None])
async def test_is_available_false_with_blank_embedding_model__DoD3(
    monkeypatch, model_value
):
    _install_server(monkeypatch, _server(embedding_model=model_value))
    client = _FakeEmbedClient(dimension=3)
    factory = _install_factory(monkeypatch, client)

    assert await embedding.is_available() is False
    assert factory.calls == []
    assert client.call_count == 0
    assert client.entered is False


# DoD-3: the availability probe reports True for a fully designated server,
# and still never contacts the client (it embeds nothing).
async def test_is_available_true_for_full_designation_without_client__DoD3(
    monkeypatch,
):
    _install_server(monkeypatch, _server(embedding_model="text-embedding-3-small"))
    client = _FakeEmbedClient(dimension=3)
    factory = _install_factory(monkeypatch, client)

    assert await embedding.is_available() is True
    assert factory.calls == []
    assert client.call_count == 0
    assert client.entered is False


# ---------------------------------------------------------------------------
# DoD-4 / DoD-5 -- `$ENV` key resolution at use time (real resolve_env_ref)
# ---------------------------------------------------------------------------


# DoD-4 (retrieval.md -> Dependency; root CLAUDE.md -> Config & Secrets): an api
# key stored as `$SOME_VAR` is resolved from the environment AT USE TIME and the
# RESOLVED value is what reaches client construction -- the raw stored `$NAME`
# string never does. The client is model-bound to the designated
# `embedding_model`.
async def test_env_ref_api_key_is_resolved_before_client_construction__DoD4(
    monkeypatch,
):
    monkeypatch.setenv("BOOKWRITER_TEST_EMBED_KEY", "resolved-secret-value")
    server = _server(
        api_key="$BOOKWRITER_TEST_EMBED_KEY",
        embedding_model="text-embedding-3-small",
    )
    _install_server(monkeypatch, server)
    factory = _install_factory(monkeypatch, _FakeEmbedClient(dimension=2))

    await embedding.embed_batch(["some text"])

    assert len(factory.calls) == 1
    constructed_server, resolved_key, model = factory.calls[0]
    assert resolved_key == "resolved-secret-value"
    assert resolved_key != "$BOOKWRITER_TEST_EMBED_KEY"
    assert model == "text-embedding-3-small"
    assert constructed_server is server


# DoD-5 (single taxonomy for callers): a `$SOME_VAR` reference whose environment
# variable is unset surfaces as THIS module's `unreachable` reason, not as a raw
# LlmServerError.
async def test_unset_env_ref_surfaces_as_unreachable__DoD5(monkeypatch):
    monkeypatch.delenv("BOOKWRITER_TEST_EMBED_MISSING", raising=False)
    _install_server(
        monkeypatch, _server(api_key="$BOOKWRITER_TEST_EMBED_MISSING")
    )
    _install_factory(monkeypatch, _FakeEmbedClient(dimension=2))

    with pytest.raises(embedding.EmbeddingError) as exc:
        await embedding.embed_batch(["some text"])

    assert exc.value.reason == embedding.EmbeddingErrorReason.unreachable


# ---------------------------------------------------------------------------
# DoD-6 -- transport / LLM failures become `unreachable`
# ---------------------------------------------------------------------------


# DoD-6 (retrieval.md -> Failure modes, row 2): a transport failure or LLM error
# raised by the client surfaces as the `unreachable` reason, never as a raw
# exception. The breadth mirrors `services/chat_turn.py`'s failure set --
# connection failures are NOT wrapped by the `llm` library, so raw
# aiohttp.ClientError subclasses propagate alongside LLMError.
@pytest.mark.parametrize(
    "client_exc",
    [
        aiohttp.ClientError("unreachable"),
        aiohttp.ClientConnectionError("no route to host"),
        LLMError("upstream 500"),
        ValueError("keyless openai client"),
        RuntimeError("session already closed"),
    ],
)
async def test_client_failure_surfaces_as_unreachable__DoD6(monkeypatch, client_exc):
    _install_server(monkeypatch, _server())
    _install_factory(monkeypatch, _FakeEmbedClient(exc=client_exc))

    with pytest.raises(embedding.EmbeddingError) as exc:
        await embedding.embed_batch(["some text"])

    assert exc.value.reason == embedding.EmbeddingErrorReason.unreachable


# ---------------------------------------------------------------------------
# DoD-7 -- one vector per text, in input order
# ---------------------------------------------------------------------------


# DoD-7 (retrieval.md -> Chunking): the batch embed returns one vector per input
# text, in input order, for a multi-text call -- a chunk's vector must stay
# paired with its chunk.
async def test_batch_embed_returns_one_vector_per_text_in_order__DoD7(monkeypatch):
    scripted = [[1.0, 1.1], [2.0, 2.1], [3.0, 3.1]]
    _install_server(monkeypatch, _server())
    client = _FakeEmbedClient(vectors=scripted)
    _install_factory(monkeypatch, client)

    texts = ["alpha chunk", "beta chunk", "gamma chunk"]
    result = await embedding.embed_batch(texts)

    assert len(result) == len(texts)
    assert [list(v) for v in result] == scripted
    # the texts reached the client in input order, unreordered and unmerged
    assert client.embed_batch_calls == [texts]


# ---------------------------------------------------------------------------
# DoD-8 -- empty input short-circuits
# ---------------------------------------------------------------------------


# DoD-8: an empty input list returns an empty result and makes no client call at
# all -- nothing is even constructed.
async def test_empty_input_returns_empty_without_contacting_client__DoD8(
    monkeypatch,
):
    _install_server(monkeypatch, _server())
    client = _FakeEmbedClient(vectors=[[9.0]])
    factory = _install_factory(monkeypatch, client)

    result = await embedding.embed_batch([])

    assert result == []
    assert factory.calls == []
    assert client.call_count == 0
    assert client.entered is False


# ---------------------------------------------------------------------------
# DoD-9 -- the client is an async context manager, exited on every path
# ---------------------------------------------------------------------------


# DoD-9 (011 finding: LLMClient has no standalone close()): the client is entered
# as an async context manager and exited on the SUCCESS path.
async def test_client_context_entered_and_exited_on_success__DoD9(monkeypatch):
    _install_server(monkeypatch, _server())
    client = _FakeEmbedClient(vectors=[[0.1, 0.2]])
    _install_factory(monkeypatch, client)

    await embedding.embed_batch(["some text"])

    assert client.entered is True
    assert client.exited is True


# DoD-9: the client is exited on the FAILURE path too -- when the client itself
# raises, __aexit__ still runs.
async def test_client_context_exited_when_client_raises__DoD9(monkeypatch):
    _install_server(monkeypatch, _server())
    client = _FakeEmbedClient(exc=LLMError("boom"))
    _install_factory(monkeypatch, client)

    with pytest.raises(embedding.EmbeddingError):
        await embedding.embed_batch(["some text"])

    assert client.entered is True
    assert client.exited is True


# ---------------------------------------------------------------------------
# DoD-10 -- the dimension probe
# ---------------------------------------------------------------------------


# DoD-10 (retrieval.md -> Vector dimension): the dimension probe returns the
# length of the vector the model actually returned -- the dimension is
# discovered, never declared. Asserted for two different mocked lengths.
@pytest.mark.parametrize("dimension", [3, 1536])
async def test_probe_dimension_reports_returned_vector_length__DoD10(
    monkeypatch, dimension
):
    _install_server(monkeypatch, _server())
    client = _FakeEmbedClient(dimension=dimension)
    _install_factory(monkeypatch, client)

    assert await embedding.probe_dimension() == dimension


# ---------------------------------------------------------------------------
# DoD-11 -- the dimension check
# ---------------------------------------------------------------------------


# DoD-11 (retrieval.md -> Failure modes, row 3): the dimension check returns
# normally for a batch whose vectors all match the expected length.
def test_check_dimension_passes_uniform_batch__DoD11():
    vectors = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]

    assert embedding.check_dimension(vectors, 3) is None


# DoD-11: the dimension check raises the mismatch reason when ANY one vector's
# length differs from the expected one.
@pytest.mark.parametrize(
    "vectors",
    [
        [[1.0, 2.0]],  # the only vector is short
        [[1.0, 2.0, 3.0], [4.0, 5.0], [7.0, 8.0, 9.0]],  # a middle one is short
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0, 7.0]],  # a trailing one is long
    ],
)
def test_check_dimension_raises_on_any_mismatch__DoD11(vectors):
    with pytest.raises(embedding.EmbeddingError) as exc:
        embedding.check_dimension(vectors, 3)

    assert exc.value.reason == embedding.EmbeddingErrorReason.dimension_mismatch
