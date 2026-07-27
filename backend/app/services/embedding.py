"""Embedding service — the single point where text becomes vectors (feature 013,
step 004).

The module ``docs/architecture/retrieval.md`` → "Dependency" names and feature 007
explicitly did **not** build. It owns three things and nothing else:

1. **Resolution** — the designated embedding server via
   ``app.db.llm_servers.get_embedding_server()`` (at most one row carries the
   FEAT-004 / UC-014 designation), and its ``api_key`` through the ``$ENV``
   indirection (``app.services.secrets.resolve_env_ref``, resolved **at use time**
   only — root ``CLAUDE.md`` → Config & Secrets).
2. **The model call** — through a model-bound ``llm`` client built by
   :func:`app.services.llm_servers.create_model_client`, never a direct HTTP call
   (``backend.md`` → "LLM client").
3. **A typed failure taxonomy** — :class:`EmbeddingError` discriminated by
   :class:`EmbeddingErrorReason`. No caller should ever have to catch
   ``aiohttp.ClientError``, ``LLMError`` or ``LlmServerError`` to use this module.

Business-logic layer: **no** ``session`` / ``AsyncSession`` / ``select()`` /
``session.exec()`` / ``session.add()`` here (``docs/architecture/backend.md`` —
layer separation). All persistence goes through the session-free ``app.db``
layer (namespace import).

**This module must not import ``app.db.vector``.** ``db → services`` is forbidden,
so step 005 reaches :func:`probe_dimension` and :func:`embed_batch` through
callables **injected** at ``init_vector`` from the composition root
(``context.md`` → "``db/vector.py`` receives its embedder as an injected
callable"). Those two signatures are therefore what the injection is typed
against; keep them plain and positional.

**The client lifetime contract.** :class:`~llm.LLMClient` exposes ``__aenter__`` /
``__aexit__`` and has **no standalone ``close()``** (``011.chat-panel`` finding).
Every call path here MUST enter it with ``async with`` so its ``aiohttp`` session
closes on every path, including failure.

**Import direction.** ``app.services.secrets`` imports :class:`LlmServerError`
*from* ``app.services.llm_servers``; neither imports this module, so the
module-level imports below are acyclic and the function-local form used at
``llm_servers.py:351`` is not needed here (that one guards the reverse edge,
``llm_servers`` → ``secrets``). If a future edge ever makes this cyclic, move the
``secrets`` import inside the function and say so, per that precedent.

**What lives elsewhere and is not duplicated here.**
``services/db_admin.py:rebuild_vector_index()`` keeps its own no-embedding-provider
gate (→ 400 at ``routes/admin/db.py``); ``EmbeddingErrorReason.no_provider`` is the
*service-side* equivalent for every other caller, including
``db/import_export_queries.py:run_vector_rebuild()``, which deliberately bypasses
that gate and needs a clean typed raise it can swallow.
"""

import enum
from collections.abc import Sequence

import aiohttp
from llm import LLMError

from app.db import llm_servers as llm_servers_db
from app.services import llm_servers as llm_servers_service
from app.services import secrets

# The short constant text :func:`probe_dimension` embeds to discover the model's
# vector length. Private and NOT part of the frozen contract — the coder may
# reword it; only the *behaviour* (one short constant string, embedded once) is
# specified. ``retrieval.md`` → "Vector dimension": the dimension is a property of
# the model and is discovered, never declared.
_PROBE_TEXT = "dimension probe"


class EmbeddingErrorReason(str, enum.Enum):
    """Discriminator for :class:`EmbeddingError` — the embedding refusal taxonomy.

    One member per row of ``retrieval.md`` → "Failure modes" that this module can
    produce. Shape copied from :class:`app.services.chats.ChatErrorReason`.

    - ``no_provider`` — no row carries the FEAT-004 / UC-014 embedding
      designation, **or** the designated row's ``embedding_model`` is null / blank
      (``retrieval.md`` → "Dependency"). Raised before any client is constructed.
    - ``unreachable`` — the call could not be made or failed: a transport error
      (``aiohttp.ClientError`` — connection failures are **not** wrapped by the
      ``llm`` library), an ``LLMError``, or an unresolvable ``$ENV`` key reference
      (``LlmServerError(env_not_set)``). Mirror the breadth of
      ``chat_turn.py:_TURN_FAILURE_EXCEPTIONS``.
    - ``dimension_mismatch`` — a returned vector's length differs from an expected
      one, i.e. the designated model changed under a live index. Never coerced:
      truncating or padding produces vectors whose distances mean nothing
      (``retrieval.md`` → "Vector dimension").

    These reasons do not reach the wire through any route this feature adds; the
    hyphenated values follow the house convention regardless.
    """

    no_provider = "no-provider"
    unreachable = "unreachable"
    dimension_mismatch = "dimension-mismatch"


class EmbeddingError(Exception):
    """Raised by the embedding service for every failure — the single taxonomy.

    Carries an :class:`EmbeddingErrorReason` discriminator (``reason``) plus a
    human-readable ``message``. Copied from
    :class:`app.services.chats.ChatError`. Callers that must degrade quietly
    (step 006's best-effort index maintenance) catch this one type; callers that
    must not raise at all (step 009's tool) convert it to a string.
    """

    def __init__(self, reason: EmbeddingErrorReason, message: str = "") -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)


async def is_available() -> bool:
    """Report whether a usable embedding designation exists **right now**.

    Reads ``llm_servers_db.get_embedding_server()`` and returns ``True`` only when
    a row is designated **and** its ``embedding_model`` is present and not blank —
    exactly the condition whose absence makes :func:`embed_batch` raise
    ``no_provider``. Embeds nothing, constructs no client and contacts no server;
    it never raises for the "not configured yet" case.

    This is the quiet-degradation probe: step 006's maintenance path calls it to
    skip indexing on the common unconfigured install instead of catching a raise.
    """
    server = await llm_servers_db.get_embedding_server()
    if server is None:
        return False
    return bool((server.embedding_model or "").strip())


async def embed_batch(texts: Sequence[str]) -> list[list[float]]:
    """Embed a sequence of texts, returning **one vector per text, in input order**.

    Order is load-bearing: a chunk's vector must stay paired with its chunk
    (``retrieval.md`` → "Chunking"), so the result is positionally aligned with
    ``texts`` — same length, same order, no filtering or deduplication.

    The one place resolution happens: designated server →
    :func:`secrets.resolve_env_ref` on its ``api_key`` (the raw stored ``$NAME``
    token must never reach client construction) →
    :func:`llm_servers_service.create_model_client` bound to the row's
    ``embedding_model`` → ``async with`` the client → ``embed_batch``.

    An **empty** ``texts`` returns ``[]`` without resolving or contacting anything.

    Failures: no designation / blank ``embedding_model`` → ``no_provider``, raised
    before a client is constructed; an unset ``$ENV`` variable, a transport error
    or an ``LLMError`` → ``unreachable``. Nothing else escapes.

    Also one half of step 005's injection: ``init_vector`` receives this function
    as the embedder callable, so the parameter stays a single positional
    ``Sequence[str]``.
    """
    # Nothing to embed: no designation lookup, no key resolution, no client.
    if len(texts) == 0:
        return []

    server = await llm_servers_db.get_embedding_server()
    model = (server.embedding_model or "").strip() if server is not None else ""
    if server is None or not model:
        # Raised BEFORE any client is constructed (``retrieval.md`` → Failure
        # modes, row 1). The admin rebuild keeps its own equivalent gate.
        raise EmbeddingError(
            EmbeddingErrorReason.no_provider,
            "No embedding server is designated, or it carries no embedding model.",
        )

    # Resolve the ``$ENV`` ref at use time, BEFORE the client call — the raw
    # stored ``$NAME`` token must never reach client construction. An unset
    # variable is an ``LlmServerError(env_not_set)``, which this module converts
    # rather than letting it escape (``llm_servers.py:345-363`` is the pattern).
    try:
        resolved_key = secrets.resolve_env_ref(server.api_key)
    except llm_servers_service.LlmServerError as exc:
        raise EmbeddingError(
            EmbeddingErrorReason.unreachable,
            f"The embedding server's api key could not be resolved: {exc}",
        ) from exc

    try:
        # ``async with`` is what closes the client's aiohttp session on EVERY
        # path, including when the call raises — there is no standalone
        # ``close()``.
        async with llm_servers_service.create_model_client(
            server, resolved_key, model
        ) as client:
            return await client.embed_batch(list(texts))
    except (aiohttp.ClientError, LLMError, ValueError, RuntimeError) as exc:
        # The breadth of ``chat_turn.py:_TURN_FAILURE_EXCEPTIONS``: connection
        # failures are NOT wrapped by the ``llm`` library, so raw
        # ``aiohttp.ClientError`` subclasses propagate alongside ``LLMError``.
        raise EmbeddingError(
            EmbeddingErrorReason.unreachable,
            f"The embedding server could not be reached: {exc}",
        ) from exc


async def embed_text(text: str) -> list[float]:
    """Embed a single text — the query path (step 009's ``codex_search``).

    A thin wrapper over :func:`embed_batch`: it must **not** duplicate the
    resolution logic, so the same failure taxonomy applies unchanged. Returns the
    single vector, not a one-element list.
    """
    vectors = await embed_batch([text])
    if len(vectors) == 0:
        # A non-empty input that came back with nothing is a failed call, not an
        # empty result — keep it inside the single taxonomy rather than letting
        # an IndexError reach the caller.
        raise EmbeddingError(
            EmbeddingErrorReason.unreachable,
            "The embedding server returned no vector.",
        )
    return vectors[0]


async def probe_dimension() -> int:
    """Embed one short constant probe text and return the length of the vector the
    model actually returned.

    ``retrieval.md`` → "Vector dimension": the dimension is a property of the
    model, discovered rather than declared, so step 005 creates the sidecar table
    with whatever this reports. Goes through :func:`embed_batch` (or the same
    resolution path) with :data:`_PROBE_TEXT`, so ``no_provider`` / ``unreachable``
    surface identically.

    The other half of step 005's injection: ``init_vector`` receives this function
    as the dimension-probe callable, so it takes no arguments.
    """
    vector = await embed_text(_PROBE_TEXT)
    return len(vector)


def check_dimension(
    vectors: Sequence[Sequence[float]], expected_dimension: int
) -> None:
    """Raise ``dimension_mismatch`` when any vector's length differs from
    ``expected_dimension``; return ``None`` otherwise.

    Synchronous and I/O-free. It exists as its own callable because the comparison
    happens where the table's dimension is known (steps 005 / 006) while the error
    taxonomy lives here — ``db/`` must not raise a service error type of its own,
    and must not import this module either.

    An empty ``vectors`` passes (there is nothing that mismatches).
    """
    for vector in vectors:
        if len(vector) != expected_dimension:
            raise EmbeddingError(
                EmbeddingErrorReason.dimension_mismatch,
                f"Embedding dimension {len(vector)} does not match the index "
                f"dimension {expected_dimension}; the designated embedding model "
                "has changed and a full rebuild is required.",
            )
