"""Tests for the two codex assistant tools (feature 013, step 009).

Bound to the frozen skeleton (``status.md`` -> ``## Skeleton`` -> Step 009).

In ``app.services.codex_tools``::

    DEFAULT_SEARCH_LIMIT: int
    MAX_SEARCH_LIMIT: int
    class CodexSearchArgs(BaseModel)      { query: str; limit: int }
    class CodexEntryReadArgs(BaseModel)   { entry_id: str }
    def bind_codex_search(context: ToolContext) -> Callable[..., object]
    def bind_codex_read_entry(context: ToolContext) -> Callable[..., object]
    async def codex_search(context, query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> str
    async def codex_read_entry(context, entry_id: str) -> str

in ``app.services.tools``::

    @dataclass(frozen=True) class ToolContext { book_id: int }
    ToolBinder = Callable[[ToolContext], Callable[..., object]]
    @dataclass(frozen=True) class ToolDef { name; description; args_schema;
        callable=None; binder=None }
    TOOL_REGISTRY: list[ToolDef]          # web_search, codex_search, codex_read_entry
    def build_tool_bindings(tools, context: ToolContext | None = None)
        -> tuple[list[dict[str, object]], dict[str, Callable[..., object]]]

Expected values come from the SPEC ONLY -- ``009.codex-assistant-tools.md`` ->
Interface intent + Definition of done (DoD-1..DoD-13), ``009.context.md``,
``context.md`` decision 6 and ``retrieval.md``'s hard-filter / failure-mode rules
-- never from implementation internals.

Test approach (009.context.md -> "Test approach"): step 004's embed call is
MOCKED; step 005's sidecar runs FOR REAL against a per-test ``tmp_path`` vector
dir with fixed short vectors so nearest-neighbour ordering is predictable; codex
rows are seeded in TWO different books through the ``db/`` layer against the real
``db`` fixture. Assertions are made on the returned STRING's content. There is no
network anywhere, and ``web_search`` is never invoked (only its binding is
asserted). ``asyncio_mode = "auto"``.

Deliberately NOT asserted: any minimum-score / relevance threshold. UC-078's
relevance criterion is an open product ``_TBD:`` (challenge C27); the result
limit is a bounded-output concern only.
"""

import enum
import inspect
from pathlib import Path

from app.db import (
    assistant_modes,
    books,
    chats,
    codex_entries,
    llm_servers,
    mode_tools,
    users,
    vector,
)
from app.db.engine import DbConfig
from app.models.assistant_mode import AssistantMode
from app.models.book import Book, BookState, CollaborationMode, Visibility
from app.models.chat import Chat
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.llm_server import LlmServer
from app.models.mode_tool import ModeTool
from app.models.schemas.tools import WebSearchArgs
from app.models.user import User, UserRole
from app.services import assistant_runtime, chat_turn, codex_tools, embedding
from app.services import tools as tools_module
from app.services.assistant_runtime import ResolvedSubject
from app.services.chat_turn import TurnContext
from app.services.codex_tools import CodexEntryReadArgs, CodexSearchArgs
from app.services.embedding import EmbeddingError, EmbeddingErrorReason
from app.services.tools import ToolContext
from app.services.web_search import web_search

# ---------------------------------------------------------------------------
# Fixed short vectors -- deterministic ordering under any distance metric.
#
#   V_EXACT is the query vector itself (distance 0),
#   V_NEAR is close to it, V_MID and V_FAR are orthogonal to it.
# ---------------------------------------------------------------------------

V_EXACT: list[float] = [1.0, 0.0, 0.0, 0.0]
V_NEAR: list[float] = [0.8, 0.6, 0.0, 0.0]
V_MID: list[float] = [0.0, 1.0, 0.0, 0.0]
V_FAR: list[float] = [0.0, 0.0, 1.0, 0.0]

QUERY = "who guards the north?"


class _OtherSourceKind(str, enum.Enum):
    """A second discriminator value for the one-table sidecar.

    ``db.vector.SourceKind`` carries only ``codex_entry`` today; ``retrieval.md``
    adds chapter / summary / state-note corpora to the SAME table later. DoD-2
    is about a future corpus not leaking into a codex answer, so a chunk written
    under another discriminator value is exactly what makes the clause bite.
    """

    chapter = "chapter"


# ---------------------------------------------------------------------------
# The embedding seam -- step 004's call, mocked. No network.
# ---------------------------------------------------------------------------


def _install_embed(
    monkeypatch,
    *,
    vector_value: list[float] | None = None,
    exc: Exception | None = None,
    available: bool = True,
) -> None:
    """Substitute ``services/embedding``'s query path.

    ``embed_text`` returns ``vector_value`` (the query vector) or raises ``exc``;
    ``is_available`` reports ``available`` so the "no provider configured" world
    is consistent whichever of the two the tool consults first.
    """
    fixed = list(vector_value) if vector_value is not None else list(V_EXACT)

    async def _embed_text(text: str) -> list[float]:
        if exc is not None:
            raise exc
        return list(fixed)

    async def _embed_batch(texts) -> list[list[float]]:
        if exc is not None:
            raise exc
        return [list(fixed) for _ in texts]

    async def _is_available() -> bool:
        return available

    monkeypatch.setattr(embedding, "embed_text", _embed_text)
    monkeypatch.setattr(embedding, "embed_batch", _embed_batch)
    monkeypatch.setattr(embedding, "is_available", _is_available)


# ---------------------------------------------------------------------------
# The fake LLM client -- feature 011's substituted construction seam.
# ---------------------------------------------------------------------------


class _FakeClient:
    """A stand-in for ``llm.LLMClient`` used as an async context manager."""

    def __init__(self, *, chunks=None, return_value=""):
        self._chunks = list(chunks or [])
        self._return_value = return_value
        self.call: dict | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def chat_with_tools(
        self,
        messages,
        *,
        tools_definitions=None,
        tools=None,
        system=None,
        max_loops=None,
        options=None,
        stream=False,
        on_delta=None,
        response_format=None,
        **kwargs,
    ):
        self.call = {
            "messages": messages,
            "tools_definitions": tools_definitions,
            "tools": tools,
            "system": system,
        }
        if on_delta is not None:
            for chunk in self._chunks:
                result = on_delta(chunk)
                if inspect.isawaitable(result):
                    await result
        return self._return_value


def _install_client(monkeypatch, fake: _FakeClient) -> _FakeClient:
    def factory(server, resolved_key, model):
        return fake

    monkeypatch.setattr("app.services.llm_servers.create_model_client", factory)
    monkeypatch.setattr(
        "app.services.chat_turn.create_model_client", factory, raising=False
    )
    return fake


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


async def _seed_server() -> LlmServer:
    return await llm_servers.create(
        LlmServer(
            name="S",
            backend_type="openai",
            base_url="https://api.example.com/v1",
            api_key="sk-stored",
            enabled_models='["gpt-x"]',
            is_active=True,
        )
    )


async def _seed_chat(book_id: int, author_id: int, server_id: int) -> Chat:
    return await chats.create(
        Chat(
            book_id=book_id,
            author_id=author_id,
            title="A Chat",
            llm_server_id=server_id,
            model_name="gpt-x",
        )
    )


async def _seed_mode(key: str, system_prompt: str | None = "MODE_RULES") -> AssistantMode:
    return await assistant_modes.create(
        AssistantMode(key=key, system_prompt=system_prompt)
    )


async def _seed_mode_tool(mode_key: str, tool_name: str) -> ModeTool:
    return await mode_tools.create(ModeTool(mode_key=mode_key, tool_name=tool_name))


async def _index_vector_dir(tmp_path: Path, name: str = "vec") -> None:
    """Point the real sidecar at this test's own throwaway vector dir."""
    await vector.init_vector(tmp_path / name)


async def _index(
    book_id: int,
    source_id: int,
    pairs,
    source_kind=vector.SourceKind.codex_entry,
) -> None:
    """Write ``(text, vector)`` chunks straight into the real sidecar."""
    await vector.upsert_chunks(book_id, source_kind, source_id, list(pairs))


async def _run(context: TurnContext, prompt: str | None = "ask"):
    return [frame async for frame in chat_turn.run_turn(context, prompt)]


# ---------------------------------------------------------------------------
# DoD-1 — the turn's book is a HARD filter on codex_search
# ---------------------------------------------------------------------------


# DoD-1 (retrieval.md -> hard filter; US-085.AC-1): codex_search searches with the
# TURN's book id -- an entry in another book that is the NEAREST NEIGHBOUR of the
# query is never returned. The foreign chunk sits exactly on the query vector and
# the turn's own chunks are orthogonal to it, so the foreign entry genuinely IS
# nearest (proved by a direct sidecar search against the other book).
async def test_search_never_crosses_books_even_when_nearest__DoD1_US085_AC1(
    db: DbConfig, tmp_path: Path, monkeypatch
):
    await _index_vector_dir(tmp_path)
    user = await _seed_user()
    mine = await _seed_book(user.id, title="Mine")
    theirs = await _seed_book(user.id, title="Theirs")

    own = await _seed_entry(
        mine.id, user.id, name="Halden", body="OWN_BODY a distant guardian"
    )
    foreign = await _seed_entry(
        theirs.id, user.id, name="Intruder", body="FOREIGN_BODY the true nearest"
    )

    await _index(mine.id, own.id, [("OWN_CHUNK a distant guardian", V_MID)])
    await _index(theirs.id, foreign.id, [("FOREIGN_CHUNK the true nearest", V_EXACT)])

    # Proof that the foreign chunk really is the query's nearest neighbour.
    foreign_hits = await vector.search(theirs.id, V_EXACT, limit=10)
    assert foreign_hits[0].text == "FOREIGN_CHUNK the true nearest"

    _install_embed(monkeypatch, vector_value=V_EXACT)

    result = await codex_tools.codex_search(
        ToolContext(book_id=mine.id), query=QUERY, limit=10
    )

    assert "FOREIGN_CHUNK" not in result
    assert "FOREIGN_BODY" not in result
    assert str(foreign.id) not in result
    # The turn's own -- strictly worse-matching -- entry is what comes back.
    assert "OWN_CHUNK" in result
    assert str(own.id) in result


# ---------------------------------------------------------------------------
# DoD-2 — restricted to the codex_entry source kind
# ---------------------------------------------------------------------------


# DoD-2 (retrieval.md -> Query surface): codex_search restricts to the
# `codex_entry` source kind, so another corpus sharing the one sidecar table
# cannot leak into a codex answer -- even when its chunk is the nearest
# neighbour, and even though it belongs to the very same book.
async def test_search_restricted_to_codex_entry_kind__DoD2(
    db: DbConfig, tmp_path: Path, monkeypatch
):
    await _index_vector_dir(tmp_path)
    user = await _seed_user()
    book = await _seed_book(user.id)
    entry = await _seed_entry(book.id, user.id, name="Halden", body="CODEX_BODY")

    # Same book, another corpus, sitting exactly on the query vector.
    await _index(
        book.id,
        999001,
        [("CHAPTER_CHUNK prose from a chapter", V_EXACT)],
        source_kind=_OtherSourceKind.chapter,
    )
    await _index(book.id, entry.id, [("CODEX_CHUNK the guardian", V_MID)])

    _install_embed(monkeypatch, vector_value=V_EXACT)

    result = await codex_tools.codex_search(
        ToolContext(book_id=book.id), query=QUERY, limit=10
    )

    assert "CHAPTER_CHUNK" not in result
    assert "CODEX_CHUNK" in result
    assert str(entry.id) in result


# ---------------------------------------------------------------------------
# DoD-3 — every hit carries its entry id beside the snippet
# ---------------------------------------------------------------------------


# DoD-3 (UC-078): the result text carries EACH hit's entry id alongside its
# snippet, so the model can follow up with the read tool -- the id being the wire
# string form the read tool accepts.
async def test_result_carries_entry_id_beside_snippet__DoD3_UC078(
    db: DbConfig, tmp_path: Path, monkeypatch
):
    await _index_vector_dir(tmp_path)
    user = await _seed_user()
    book = await _seed_book(user.id)
    first = await _seed_entry(book.id, user.id, name="Halden", body="first body")
    second = await _seed_entry(
        book.id, user.id, CodexKind.location, name="Northgate", body="second body"
    )

    await _index(book.id, first.id, [("SNIPPET_ONE the guardian", V_EXACT)])
    await _index(book.id, second.id, [("SNIPPET_TWO the gate", V_NEAR)])

    _install_embed(monkeypatch, vector_value=V_EXACT)

    result = await codex_tools.codex_search(
        ToolContext(book_id=book.id), query=QUERY, limit=10
    )

    for entry, snippet in ((first, "SNIPPET_ONE"), (second, "SNIPPET_TWO")):
        assert snippet in result
        assert str(entry.id) in result

    # The id is usable verbatim as the read tool's argument.
    read = await codex_tools.codex_read_entry(
        ToolContext(book_id=book.id), entry_id=str(first.id)
    )
    assert "first body" in read


# ---------------------------------------------------------------------------
# DoD-4 — the result limit is honoured and hits are nearest-first
# ---------------------------------------------------------------------------


# DoD-4: codex_search honours its result limit and returns hits nearest-first.
# Three entries at three strictly different distances from the query vector; a
# limit of two must yield the two nearest, in that order, and drop the third.
async def test_limit_honoured_and_nearest_first__DoD4(
    db: DbConfig, tmp_path: Path, monkeypatch
):
    await _index_vector_dir(tmp_path)
    user = await _seed_user()
    book = await _seed_book(user.id)
    nearest = await _seed_entry(book.id, user.id, name="Nearest", body="b1")
    middle = await _seed_entry(book.id, user.id, name="Middle", body="b2")
    farthest = await _seed_entry(book.id, user.id, name="Farthest", body="b3")

    await _index(book.id, nearest.id, [("HIT_NEAREST", V_EXACT)])
    await _index(book.id, middle.id, [("HIT_MIDDLE", V_NEAR)])
    await _index(book.id, farthest.id, [("HIT_FARTHEST", V_MID)])

    _install_embed(monkeypatch, vector_value=V_EXACT)

    result = await codex_tools.codex_search(
        ToolContext(book_id=book.id), query=QUERY, limit=2
    )

    # The limit is a ceiling on the hits rendered.
    assert "HIT_FARTHEST" not in result
    assert str(farthest.id) not in result
    # Nearest first.
    assert "HIT_NEAREST" in result
    assert "HIT_MIDDLE" in result
    assert result.index("HIT_NEAREST") < result.index("HIT_MIDDLE")
    assert result.index(str(nearest.id)) < result.index(str(middle.id))


# ---------------------------------------------------------------------------
# DoD-5 — no embedding provider configured
# ---------------------------------------------------------------------------


# DoD-5 (retrieval.md -> Failure modes; the web_search never-raise contract): with
# NO embedding provider configured, codex_search returns an informative string and
# does not raise -- a raising tool would abort the whole chat_with_tools loop.
async def test_no_embedding_provider_returns_string__DoD5(
    db: DbConfig, tmp_path: Path, monkeypatch
):
    await _index_vector_dir(tmp_path)
    user = await _seed_user()
    book = await _seed_book(user.id)
    entry = await _seed_entry(book.id, user.id, name="Halden", body="INDEXED_BODY")
    await _index(book.id, entry.id, [("INDEXED_CHUNK", V_EXACT)])

    _install_embed(
        monkeypatch,
        available=False,
        exc=EmbeddingError(
            EmbeddingErrorReason.no_provider, "no embedding server designated"
        ),
    )

    # No exception escapes.
    result = await codex_tools.codex_search(
        ToolContext(book_id=book.id), query=QUERY, limit=5
    )

    assert isinstance(result, str)
    assert result.strip() != ""
    # Nothing was searched, so no indexed content can be in the answer.
    assert "INDEXED_CHUNK" not in result


# ---------------------------------------------------------------------------
# DoD-6 — an empty or stale index is "nothing found", not an error
# ---------------------------------------------------------------------------


# DoD-6 (retrieval.md -> Failure modes, row 4): with an empty or stale index,
# codex_search returns a "nothing found" string rather than an error -- a
# DISTINCT string from the no-provider and the transport-failure answers.
async def test_empty_index_says_nothing_found_not_error__DoD6(
    db: DbConfig, tmp_path: Path, monkeypatch
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    other = await _seed_book(user.id, title="Other")
    context = ToolContext(book_id=book.id)

    # (a) a wholly empty index -- nothing has ever been written.
    await _index_vector_dir(tmp_path, "empty")
    _install_embed(monkeypatch, vector_value=V_EXACT)
    empty_result = await codex_tools.codex_search(context, query=QUERY, limit=5)

    # (b) a stale index -- chunks exist, but none of them are this book's.
    await _index_vector_dir(tmp_path, "stale")
    stray = await _seed_entry(other.id, user.id, name="Stray", body="b")
    await _index(other.id, stray.id, [("STRAY_CHUNK", V_EXACT)])
    stale_result = await codex_tools.codex_search(context, query=QUERY, limit=5)

    for result in (empty_result, stale_result):
        assert isinstance(result, str)
        assert result.strip() != ""
    assert "STRAY_CHUNK" not in stale_result

    # Distinct from the two failure answers: "nothing found" is not an error.
    _install_embed(
        monkeypatch,
        available=False,
        exc=EmbeddingError(EmbeddingErrorReason.no_provider, "no provider"),
    )
    no_provider_result = await codex_tools.codex_search(context, query=QUERY, limit=5)

    _install_embed(
        monkeypatch,
        exc=EmbeddingError(EmbeddingErrorReason.unreachable, "connection refused"),
    )
    unreachable_result = await codex_tools.codex_search(context, query=QUERY, limit=5)

    assert empty_result != no_provider_result
    assert empty_result != unreachable_result
    assert stale_result != no_provider_result
    assert stale_result != unreachable_result


# ---------------------------------------------------------------------------
# DoD-7 — an embedding transport failure
# ---------------------------------------------------------------------------


# DoD-7 (the web_search contract -- a raising tool aborts the parent loop): an
# embedding TRANSPORT failure returns an error string and does not raise.
async def test_embedding_transport_failure_returns_string__DoD7(
    db: DbConfig, tmp_path: Path, monkeypatch
):
    await _index_vector_dir(tmp_path)
    user = await _seed_user()
    book = await _seed_book(user.id)
    entry = await _seed_entry(book.id, user.id, name="Halden", body="INDEXED_BODY")
    await _index(book.id, entry.id, [("INDEXED_CHUNK", V_EXACT)])

    _install_embed(
        monkeypatch,
        exc=EmbeddingError(
            EmbeddingErrorReason.unreachable, "embedding server unreachable"
        ),
    )

    # No exception escapes.
    result = await codex_tools.codex_search(
        ToolContext(book_id=book.id), query=QUERY, limit=5
    )

    assert isinstance(result, str)
    assert result.strip() != ""
    assert "INDEXED_CHUNK" not in result


# ---------------------------------------------------------------------------
# DoD-8 — the read tool returns kind, name and body
# ---------------------------------------------------------------------------


# DoD-8 (UC-078 follow-up): the read tool returns the KIND, NAME and BODY of an
# entry in the turn's book.
async def test_read_returns_kind_name_and_body__DoD8_UC078(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    entry = await _seed_entry(
        book.id,
        user.id,
        CodexKind.location,
        name="Northgate Keep",
        body="A cold fortress above the pass.",
    )

    result = await codex_tools.codex_read_entry(
        ToolContext(book_id=book.id), entry_id=str(entry.id)
    )

    assert entry.kind.value in result.lower()
    assert "Northgate Keep" in result
    assert "A cold fortress above the pass." in result


# ---------------------------------------------------------------------------
# DoD-9 — the read tool refuses another book's entry and leaks nothing
# ---------------------------------------------------------------------------


# DoD-9 (US-085.AC-1): the read tool given an entry id from ANOTHER book returns
# an error string and leaks NO content of that entry -- neither its body nor its
# name reaches the model.
async def test_read_refuses_other_books_entry_without_leaking__DoD9_US085_AC1(
    db: DbConfig,
):
    user = await _seed_user()
    mine = await _seed_book(user.id, title="Mine")
    theirs = await _seed_book(user.id, title="Theirs")
    foreign = await _seed_entry(
        theirs.id,
        user.id,
        name="SecretForeignName",
        body="SECRET_FOREIGN_BODY_TEXT",
    )

    result = await codex_tools.codex_read_entry(
        ToolContext(book_id=mine.id), entry_id=str(foreign.id)
    )

    assert isinstance(result, str)
    assert result.strip() != ""
    assert "SECRET_FOREIGN_BODY_TEXT" not in result
    assert "SecretForeignName" not in result

    # The same id read from its OWN book does return the content -- so the
    # refusal above is the book check, not a broken lookup.
    allowed = await codex_tools.codex_read_entry(
        ToolContext(book_id=theirs.id), entry_id=str(foreign.id)
    )
    assert "SECRET_FOREIGN_BODY_TEXT" in allowed


# ---------------------------------------------------------------------------
# DoD-10 — an unknown or malformed id
# ---------------------------------------------------------------------------


# DoD-10: the read tool given an UNKNOWN or MALFORMED id returns an error string
# and does not raise (a non-numeric id is a refusal, never a crash).
async def test_read_unknown_or_malformed_id_returns_string__DoD10(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    real = await _seed_entry(book.id, user.id, name="Halden", body="REAL_BODY")
    context = ToolContext(book_id=book.id)

    for entry_id in (
        str(real.id + 1),  # unknown, but well-formed
        "not-a-number",
        "12x",
        "",
        "-1",
    ):
        result = await codex_tools.codex_read_entry(context, entry_id=entry_id)

        assert isinstance(result, str)
        assert result.strip() != ""
        assert "REAL_BODY" not in result


# ---------------------------------------------------------------------------
# DoD-11 — an archived entry is refused
# ---------------------------------------------------------------------------


# DoD-11 (consistency with the index, which drops archived entries): the read tool
# refuses an ARCHIVED entry with an informative string -- the two tools present
# the same world, so an entry the search can never surface cannot be read either.
async def test_read_refuses_archived_entry__DoD11(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)
    archived = await _seed_entry(
        book.id,
        user.id,
        name="Retired Character",
        body="ARCHIVED_BODY_TEXT",
        archived=True,
    )
    live = await _seed_entry(book.id, user.id, name="Live", body="LIVE_BODY_TEXT")
    context = ToolContext(book_id=book.id)

    result = await codex_tools.codex_read_entry(context, entry_id=str(archived.id))

    assert isinstance(result, str)
    assert result.strip() != ""
    assert "ARCHIVED_BODY_TEXT" not in result

    # A live sibling in the same book still reads -- the refusal is the archived
    # rule, not a broken lookup.
    live_result = await codex_tools.codex_read_entry(context, entry_id=str(live.id))
    assert "LIVE_BODY_TEXT" in live_result


# ---------------------------------------------------------------------------
# DoD-12 — both tools are registered, and bound with the TURN's context
# ---------------------------------------------------------------------------


# DoD-12 (US-111.AC-2): both tools are present in TOOL_REGISTRY, and
# build_tool_bindings binds them WITH THE TURN'S CONTEXT -- the bound callables'
# free parameters are exactly their args-schema fields (the invariant the `llm`
# client checks), definitions and callables share one key set, and what the
# callable can reach is decided by the context supplied at BINDING time.
async def test_codex_tools_are_registered_and_bound_with_context__DoD12_US111_AC2(
    db: DbConfig,
):
    user = await _seed_user()
    mine = await _seed_book(user.id, title="Mine")
    theirs = await _seed_book(user.id, title="Theirs")
    entry = await _seed_entry(mine.id, user.id, name="Halden", body="MINE_BODY_TEXT")

    registry_names = {t.name for t in tools_module.TOOL_REGISTRY}
    assert {"codex_search", "codex_read_entry"} <= registry_names

    selected = tools_module.resolve_tools(["codex_search", "codex_read_entry"])
    assert {t.name for t in selected} == {"codex_search", "codex_read_entry"}

    definitions, callables = tools_module.build_tool_bindings(
        selected, ToolContext(book_id=mine.id)
    )

    assert {d["function"]["name"] for d in definitions} == set(callables.keys())
    assert set(callables.keys()) == {"codex_search", "codex_read_entry"}

    # Each bound callable exposes exactly its args-schema fields as free params.
    assert set(
        inspect.signature(callables["codex_search"]).parameters
    ) == set(CodexSearchArgs.model_fields)
    assert set(
        inspect.signature(callables["codex_read_entry"]).parameters
    ) == set(CodexEntryReadArgs.model_fields)

    # The binding carries the book: dispatched with only its schema arguments,
    # the read tool reaches this book's entry...
    bound_read = callables["codex_read_entry"]
    assert "MINE_BODY_TEXT" in await bound_read(entry_id=str(entry.id))

    # ...and the SAME tool bound to another book's context does not.
    _, other_callables = tools_module.build_tool_bindings(
        selected, ToolContext(book_id=theirs.id)
    )
    assert "MINE_BODY_TEXT" not in await other_callables["codex_read_entry"](
        entry_id=str(entry.id)
    )


# DoD-12 (US-111.AC-2), through a live turn: a mode whose mode_tool rows select
# the two codex tools offers both to the model, bound to the TURN's book -- while
# a mode whose rows do NOT select them builds NEITHER into the definitions or the
# callable map.
async def test_mode_gating_decides_whether_codex_tools_are_built__DoD12_US111_AC2(
    db: DbConfig, monkeypatch
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, user.id, server.id)
    entry = await _seed_entry(book.id, user.id, name="Halden", body="TURN_BODY_TEXT")

    await _seed_mode("edit-character")
    await _seed_mode_tool("edit-character", "codex_search")
    await _seed_mode_tool("edit-character", "codex_read_entry")
    # A sibling mode selects neither.
    await _seed_mode("edit-fact")
    await _seed_mode_tool("edit-fact", "web_search")

    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    selecting = TurnContext(
        chat=chat,
        server=server,
        resolved_key="resolved-secret",
        subject=ResolvedSubject(kind="codex-entry", mode_key="edit-character"),
    )
    frames = await _run(selecting)

    assert frames[-1].event == "done"
    assert set(fake.call["tools"].keys()) == {"codex_search", "codex_read_entry"}
    assert {d["function"]["name"] for d in fake.call["tools_definitions"]} == {
        "codex_search",
        "codex_read_entry",
    }
    # Bound to THIS turn's book: the offered callable reaches this book's entry.
    assert "TURN_BODY_TEXT" in await fake.call["tools"]["codex_read_entry"](
        entry_id=str(entry.id)
    )

    # The mode that selects neither builds neither.
    not_selecting = TurnContext(
        chat=chat,
        server=server,
        resolved_key="resolved-secret",
        subject=ResolvedSubject(kind="codex-entry", mode_key="edit-fact"),
    )
    frames = await _run(not_selecting)

    assert frames[-1].event == "done"
    assert "codex_search" not in fake.call["tools"]
    assert "codex_read_entry" not in fake.call["tools"]
    assert "codex_search" not in str(fake.call["tools_definitions"])
    assert "codex_read_entry" not in str(fake.call["tools_definitions"])


# ---------------------------------------------------------------------------
# DoD-13 — web_search's context-free entry is unchanged
# ---------------------------------------------------------------------------


# DoD-13 (regression guard on 011's shipped tool): web_search's existing
# CONTEXT-FREE registry entry still binds and dispatches unchanged through the
# widened build_tool_bindings -- even when a real ToolContext is supplied, its
# plain callable is used verbatim and its args schema is untouched.
async def test_web_search_binds_unchanged_with_a_context__DoD13(db: DbConfig):
    user = await _seed_user()
    book = await _seed_book(user.id)

    entry = tools_module.TOOL_REGISTRY[0]
    assert entry.name == "web_search"
    assert entry.args_schema is WebSearchArgs
    assert entry.callable is web_search

    selected = tools_module.resolve_tools(["web_search"])
    definitions, callables = tools_module.build_tool_bindings(
        selected, ToolContext(book_id=book.id)
    )

    assert {d["function"]["name"] for d in definitions} == {"web_search"}
    assert set(callables.keys()) == {"web_search"}
    # Dispatch is to the very same callable 011 shipped -- not a bound wrapper.
    assert callables["web_search"] is web_search
    assert set(inspect.signature(callables["web_search"]).parameters) == set(
        WebSearchArgs.model_fields
    )

    # And the pre-013 context-free call still yields exactly the same binding.
    _, context_free = tools_module.build_tool_bindings(selected)
    assert context_free["web_search"] is web_search


# DoD-13, through a live turn: a no-mode turn (BASE_TOOL_NAMES, context.md
# decision 6) still OFFERS web_search, now that build_tool_bindings is handed the
# turn's ToolContext.
#
# Amended by feature 024 (chat-agent-loop): this case also asserted that the
# callable handed to `chat_with_tools` under "web_search" IS the raw `web_search`
# function object. 024/plan.md -> DoD-11 and decision D1 require the turn to pass
# `tools=` a map of TRACE-WRAPPED callables (every other argument unchanged), so
# object identity can never hold again by design. The behavioural property this
# case is for -- a no-mode turn still offers web_search, under that exact name,
# alongside exactly BASE_TOOL_NAMES -- is preserved and asserted below; the
# identity check is dropped as the only thing D1 invalidates. The context-free
# binding identity at `build_tool_bindings` level is untouched: it is asserted by
# `test_web_search_binds_unchanged_with_a_context__DoD13` above, which the wrapper
# does not sit on.
async def test_web_search_still_offered_on_a_no_mode_turn__DoD13(
    db: DbConfig, monkeypatch
):
    user = await _seed_user()
    book = await _seed_book(user.id)
    server = await _seed_server()
    chat = await _seed_chat(book.id, user.id, server.id)

    fake = _install_client(monkeypatch, _FakeClient(chunks=["ok"]))

    context = TurnContext(
        chat=chat,
        server=server,
        resolved_key="resolved-secret",
        subject=ResolvedSubject(kind="chats", mode_key=None),
    )
    frames = await _run(context)

    assert frames[-1].event == "done"
    assert set(fake.call["tools"].keys()) == set(assistant_runtime.BASE_TOOL_NAMES)
    # web_search is offered, by name, with a dispatchable callable behind it and a
    # matching tool definition -- the turn can still reach it.
    assert "web_search" in fake.call["tools"]
    assert callable(fake.call["tools"]["web_search"])
    assert "web_search" in {
        d["function"]["name"] for d in fake.call["tools_definitions"]
    }
