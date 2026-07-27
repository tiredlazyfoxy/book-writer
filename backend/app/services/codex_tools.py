"""The codex assistant tools — semantic ``codex_search`` and the entry read
(feature 013, step 009).

The two callables behind ``services/tools.py:TOOL_REGISTRY``'s first **bound**
entries, plus their argument schemas and their binders. Business-logic layer:
**no** ``session`` / ``AsyncSession`` / ``select()`` / ``session.exec()`` /
``session.add()`` here (``docs/architecture/backend.md`` — layer separation);
everything is read through the session-free ``app.db`` modules
(:mod:`app.db.vector`, :mod:`app.db.codex_entries`) and the embedding service.

Four constraints shape every signature in this module:

1. **No per-request context argument.** The ``llm`` client decodes a tool call's
   JSON arguments and applies them as ``func(**kwargs)``, validated against
   ``inspect.signature(func).parameters``. A tool callable therefore accepts
   **exactly** the ``args_schema`` field names as keyword parameters and nothing
   else — so the turn's :class:`~app.services.tools.ToolContext` is bound at
   *binding* time. :func:`codex_search` and :func:`codex_read_entry` take that
   context **positionally first**, precisely so
   ``functools.partial(codex_search, context)`` leaves the schema's fields as the
   only free parameters. :func:`bind_codex_search` and
   :func:`bind_codex_read_entry` are the ``ToolDef.binder`` callables that
   perform exactly that application.
2. **The book scope is never a model-supplied argument.** ``retrieval.md``:
   "``book_id`` is a **hard filter**, never a ranking preference … a hit from
   another book is not a worse result, it is a permission violation." So
   :class:`CodexSearchArgs` has **no book field** — the model cannot ask for
   another book's codex because the tool exposes no way to name one — and
   :class:`CodexEntryReadArgs`' id is **validated** against the context's book
   rather than trusted (US-085.AC-1).
3. **Neither tool ever raises.** No embedding provider, an empty or stale index,
   a transport failure, an unknown / malformed / cross-book / archived id — each
   returns an informative *string* the model can act on
   (``services/web_search.py:web_search``'s contract, copied exactly: a raising
   tool is wrapped as ``RuntimeError`` by the ``llm`` client and aborts the whole
   parent loop, with the error never reaching the model).
   ``retrieval.md``'s degrade rule: "the assistant loses pulled context, it does
   not fail."
4. **No relevance threshold.** UC-078's relevance criterion is an open product
   ``_TBD:`` (challenge C27) and ``retrieval.md`` deliberately picks none. The
   result **limit** is a bounded-output concern, not a relevance criterion —
   there is no minimum-score cutoff here and adding one would close that
   ``_TBD:`` by design.

**``services/codex.py`` is deliberately not imported.** It requires a
``BookAccess`` the tool context does not carry, and its capability check has
already been satisfied upstream by the chat turn's own ``book_access``
dependency; the read tool goes to ``db/codex_entries.get_by_id`` and compares
``book_id`` itself (``009.context.md`` → "Reading entries"). ``codex_search``
applies the same rule to every hit it renders: the sidecar supplies the snippet,
the authoritative row supplies the kind and the name, and a hit whose row is
gone or archived is dropped as stale rather than shown.

**Import direction.** ``services/tools.py`` imports this module (the catalogue →
tool-module direction ``web_search`` already established), so the
:class:`~app.services.tools.ToolContext` annotation is a ``TYPE_CHECKING``-only
import and a quoted annotation — the acyclic-graph discipline
``llm_servers.py:351``'s function-local import follows, applied to a type.

**013 step 010** — the module also carries the **shared-canvas write**,
:func:`write_codex_draft`, the third bound tool and the only one that produces
anything the author sees outside the chat. Its four constraints above all still
hold (it takes the context positionally first, it names no book, it never raises,
it applies no threshold), plus two of its own:

5. **It touches no database at all.** No read of ``codex_entries`` beyond what
   ``services/assistant_runtime.py:resolve_subject`` already resolved before the
   stream opened, no write, no version row. There is **no code path from a chat
   to the ``codex_entries`` table**, and that absence — not a check — is what
   makes US-086.AC-2 / US-087.AC-2 / US-088.AC-2 true (``context.md`` → the
   shared-canvas design, point 5).
6. **The editability rule is mirrored server-side.**
   ``frontend-workspace.md`` requires a read-only subject to refuse writes "from
   the author and from the assistant alike", so :func:`write_codex_draft`
   re-derives ``frontend/src/work/subject.ts:checkWritePermission``'s verdict
   from the turn's own values rather than trusting the client, and adds the
   collaboration-mode nuance that file's line-141 note defers to this feature
   (``context.md`` decision 3).
"""

import functools
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.db import codex_entries, vector
from app.models.book import CollaborationMode
from app.models.codex_entry import CodexEntry, CodexKind
from app.models.schemas.chats import CanvasField, CanvasFrame
from app.services import authz, embedding

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, see module docstring
    from app.services.assistant_runtime import ResolvedSubject
    from app.services.tools import ToolContext

logger = logging.getLogger(__name__)


# How many hits :func:`codex_search` returns when the model names no limit, and
# the ceiling it may ask for. A **bounded-output** concern only: the block the
# model reads has to stay small enough to be worth pulling. Emphatically NOT a
# relevance criterion — there is no minimum score anywhere in this module
# (UC-078's ``_TBD:`` stays open).
DEFAULT_SEARCH_LIMIT = 5
MAX_SEARCH_LIMIT = 20


# Every string a failing tool returns. They are constants because the never-raise
# contract makes them the *only* signal the model gets — an error string has to
# say what went wrong and what (if anything) can be done about it, and the wording
# must not drift between call sites. Two vocabularies, deliberately distinct:
# "… error: …" for a failure and a plain "No codex entries found …" for the
# ordinary outcome of a query that matched nothing (an empty or stale index is
# **not** a failure — ``retrieval.md`` → Failure modes, row 4).
_NO_PROVIDER_MESSAGE = (
    "Codex search error: no embedding model is configured on this server, so the "
    "codex cannot be searched. Answer from what you already know, or ask the "
    "author."
)
_UNREACHABLE_MESSAGE = (
    "Codex search error: the embedding service could not be reached, so the codex "
    "could not be searched. It may work again shortly."
)
_EMBED_FAILED_MESSAGE = (
    "Codex search error: the search query could not be embedded, so the codex "
    "could not be searched."
)
_INDEX_FAILED_MESSAGE = (
    "Codex search error: the codex index could not be searched."
)
_HIT_READ_FAILED_MESSAGE = (
    "Codex search error: the matching codex entries could not be read."
)
_ENTRY_NOT_FOUND_MESSAGE = (
    "Codex error: no codex entry with id {entry_id} exists in this book."
)
_ENTRY_ARCHIVED_MESSAGE = (
    "Codex error: codex entry {entry_id} is archived and cannot be read."
)
_ENTRY_READ_FAILED_MESSAGE = "Codex error: the codex entry could not be read."

# The shared-canvas write's strings (013 step 010). Same reasoning as above — the
# never-raise contract makes them the only signal the model gets — with one more
# distinction: a **refusal** ("Codex draft refused: …") is a verdict about what the
# author has open and what the caller may do to it, and it will read the same on
# every retry; an **error** ("Codex draft error: …") is a transport failure the
# model may reasonably try again. The confirmation is neither, and is deliberately
# short: it exists so ``chat_with_tools`` keeps looping (a tool result is what
# tells the loop the round is not the end of the turn).
_CANVAS_NOT_A_CODEX_ENTRY_MESSAGE = (
    "Codex draft refused: the author does not have a codex entry open, so there "
    "is nothing to draft into. Only a codex entry can be written this way — write "
    "your answer in the chat instead, or ask the author to open the entry."
)
_CANVAS_ARCHIVED_MESSAGE = (
    "Codex draft refused: this codex entry is archived and read-only. It has to "
    "be restored before anything can be written into it."
)
_CANVAS_PROPOSAL_MODE_MESSAGE = (
    "Codex draft refused: this book is in proposal mode, so a co-author's codex "
    "change must be held for the owner's review. That review surface is FEAT-010, "
    "which is not built yet, so the draft cannot be offered. Ask the owner to "
    "switch the book to free mode."
)
_CANVAS_FACT_NAME_MESSAGE = (
    "Codex draft refused: a fact entry has no name — write its body instead."
)
_CANVAS_NO_STREAM_MESSAGE = (
    "Codex draft error: this turn has no open editor to write into, so the draft "
    "could not be delivered."
)
_CANVAS_DELIVERY_FAILED_MESSAGE = (
    "Codex draft error: the draft could not be delivered to the author's editor."
)
_CANVAS_FAILED_MESSAGE = "Codex draft error: the draft could not be written."
_CANVAS_WRITTEN_MESSAGE = (
    "Draft {field} placed in the codex entry the author has open. Nothing is "
    "saved: the author reads it, edits it and decides whether to keep it."
)


# The inverse of ``services/assistant_runtime.py:_CODEX_KIND_MODES`` — a blank
# entry's codex kind, recovered from the mode key the turn's subject resolved to
# (UC-076: a blank entry has no row, so its kind exists nowhere else on the
# resolved subject). Written out here rather than imported because
# ``assistant_runtime`` imports ``services/tools.py``, which imports **this**
# module: a runtime import of it would be a cycle. Keyed and valued by **wire
# value** (the feature's "map across by value" rule), so neither side can drift
# into a lookup that silently misses.
_MODE_KEY_CODEX_KINDS: dict[str, str] = {
    "edit-character": CodexKind.character.value,
    "edit-location": CodexKind.location.value,
    "edit-fact": CodexKind.fact.value,
}


# Arguments for ``codex_search``. The class docstring below is **model-facing** —
# ``llm.pydantic_to_openai_tool`` renders the schema through
# ``model_json_schema()``, which carries it as the parameter object's
# ``description`` — so the engineering notes live here instead:
#
# - the field names are load-bearing twice over (the ``models/schemas/tools.py``
#   rule): they are the JSON-schema property names the model sees *and* they must
#   be exactly the free keyword parameters of the bound callable, i.e.
#   ``functools.partial(codex_search, context)(query=…, limit=…)``;
# - **there is deliberately no book field.** The book comes off the tool context;
#   exposing one would hand the model a way to name another book's codex, which
#   ``retrieval.md`` calls a permission violation rather than a worse result;
# - this schema lives here rather than in ``models/schemas/tools.py`` because
#   that module is outside this step's Source files (step 008's
#   ``DelegationArgs`` precedent); it is a declarative Pydantic schema either
#   way.
class CodexSearchArgs(BaseModel):
    """Arguments for searching this book's codex.

    The search covers only the codex of the book being worked on; there is no
    way to search another book.
    """

    query: str = Field(
        description=(
            "What to look for, in plain language — a name, a place, a fact or a "
            "description of what you need to know."
        )
    )
    limit: int = Field(
        default=DEFAULT_SEARCH_LIMIT,
        ge=1,
        le=MAX_SEARCH_LIMIT,
        description="How many codex entries to return at most.",
    )


# Arguments for ``codex_read_entry``. Same two rules as above: the field name is
# the JSON-schema property name AND the bound callable's only free parameter, and
# the id is **validated** against the tool context's book rather than trusted —
# an entry id from another book is refused with a string (US-085.AC-1). The id is
# a **wire string** (the house rule: every id crossing a boundary is a ``str``,
# snowflakes exceed the JS safe-integer range), which is also the form
# ``db/vector.py:ChunkHit.source_id`` — and therefore ``codex_search``'s output —
# carries.
class CodexEntryReadArgs(BaseModel):
    """Arguments for reading one codex entry of this book in full."""

    entry_id: str = Field(
        description=(
            "The id of the codex entry to read, as returned by the codex search "
            "tool."
        )
    )


# Arguments for ``write_codex_draft``. Same two rules as the schemas above — the
# field names are the JSON-schema property names AND the bound callable's only
# free parameters — plus two shaping decisions:
#
# - **there is deliberately no subject argument.** The draft always goes to the
#   entry the author currently has open, which rides on the tool context
#   (``ToolContext.subject``); a subject/entry-id argument would let the model
#   aim a draft at something the author is not looking at, and would be a second
#   source of truth beside the resolved turn subject;
# - ``field`` is the **constrained literal** ``app.models.schemas.chats``
#   already defines for the wire frame, never a free string: it is the same
#   vocabulary the emitted :class:`~app.models.schemas.chats.CanvasFrame`
#   carries, so the model-facing enum and the wire enum cannot drift, and an
#   unrecognised value is refused by the schema instead of being written to the
#   wrong part of the entry.
class WriteCodexDraftArgs(BaseModel):
    """Arguments for drafting into the codex entry the author has open.

    Write one part at a time: ``name`` for the entry's name, ``body`` for its
    text. The text you send replaces that part of the draft in full, so send it
    whole rather than in pieces.
    """

    field: CanvasField = Field(
        description=(
            "Which part of the open codex entry this text is: 'name' for its "
            "name, 'body' for its text. A fact entry has no name."
        )
    )
    text: str = Field(
        description=(
            "The complete text to place in that part of the entry's draft."
        )
    )


def _parse_entry_id(entry_id: str) -> int | None:
    """The wire-string id as a snowflake, or ``None`` when it is malformed.

    ``services/codex.py:_resolve_entry``'s rule minus the error: a non-numeric id
    is simply an id nothing can be found for.
    """
    try:
        return int(str(entry_id).strip())
    except (TypeError, ValueError):
        return None


def _kind_text(entry: CodexEntry) -> str:
    """The entry's kind as its wire value (``character`` / ``location`` / ``fact``).

    Reads through ``.value`` when the enum survived the round trip and falls back
    to the bare stored string otherwise — the "map across by wire value" rule the
    rest of the feature follows, so a row that came back as a plain ``str`` still
    renders.
    """
    return str(getattr(entry.kind, "value", entry.kind))


def _entry_header(entry: CodexEntry) -> str:
    """One deterministic header line: **entry id first**, then kind, then name.

    The id leads so a follow-up :func:`codex_read_entry` is unambiguous
    (``009.context.md`` → "Result formatting"). The name segment is omitted
    entirely when the entry has none — a fact has no name (US-078.AC-2).
    """
    header = f"entry_id={entry.id} | kind={_kind_text(entry)}"
    name = (entry.name or "").strip()
    if name:
        header = f"{header} | name={name}"
    return header


def _render_hit(hit: vector.ChunkHit, entry: CodexEntry) -> str:
    """One search hit: the header line, then the **matched chunk** as the snippet.

    The chunk, not the whole entry — the model reads the passage that matched and
    calls :func:`codex_read_entry` when it wants the rest.
    """
    return f"{_entry_header(entry)}\n{hit.text.strip()}"


def _subject_codex_kind(subject: "ResolvedSubject") -> str | None:
    """The codex kind (as its wire value) of a resolved codex-entry subject.

    Two sources, in order, and **neither is a database read**: an existing entry
    carries its own ``kind`` on the row the turn already resolved; UC-076's blank
    entry has no row, so its kind comes off the mode key
    ``services/assistant_runtime.py:resolve_subject`` derived from the request's
    ``codex_kind``. ``None`` when neither is available — a blank entry opened with
    no kind at all, which is not a fact and therefore refuses nothing.
    """
    if subject.entry is not None:
        return _kind_text(subject.entry)
    if not subject.mode_key:
        return None
    return _MODE_KEY_CODEX_KINDS.get(str(subject.mode_key))


def _refuse_write(context: "ToolContext", field: CanvasField) -> str | None:
    """The server-side editability verdict: a refusal string, or ``None`` to allow.

    ``frontend/src/work/subject.ts:checkWritePermission``'s rules, re-derived from
    the turn's own values (``frontend-workspace.md``: a read-only subject refuses
    "the author and the assistant alike"), plus the collaboration-mode nuance that
    file's line-141 note defers to this feature.

    **It reads nothing but the tool context** — the subject the turn resolved
    before the stream opened and the caller's access — so no code path from here
    reaches the ``codex_entries`` table.
    """
    subject = context.subject
    if subject is None or subject.kind != "codex-entry":
        # A chapter, book state, any of the list kinds, the chats view, or no
        # subject at all. None of them is a codex entry, and a list "is a list
        # view and cannot be edited".
        return _CANVAS_NOT_A_CODEX_ENTRY_MESSAGE

    entry = subject.entry
    if entry is not None and entry.archived:
        # ``resolveEditability``'s archived row: read-only until it is restored.
        return _CANVAS_ARCHIVED_MESSAGE

    access = context.access
    if (
        access is not None
        and access.role == authz.AccessRole.co_author
        and access.collaboration_mode == CollaborationMode.proposal
    ):
        # ``context.md`` decision 3, the same branch (``role == co_author``, not
        # "not owner") and the same reason ``services/codex.py:_require_writable_mode``
        # applies to the author's own save — refused here so the assistant is
        # refused at the same place in the author's mental model. The **owner** is
        # never refused for mode. US-079.AC-2 is knowingly unmet; naming FEAT-010
        # is what keeps that gap visible instead of silently violated.
        return _CANVAS_PROPOSAL_MODE_MESSAGE
    # A context carrying **no** access cannot name a co-author, so it is not
    # refused: nothing about this tool persists or reveals anything (the frame
    # goes to the author's own editor and no farther), so the conservative reading
    # would cost a legitimate draft and buy nothing. A real turn always carries
    # one — ``prepare_turn`` puts it on the ``TurnContext``.

    if field == "name" and _subject_codex_kind(subject) == CodexKind.fact.value:
        # US-078.AC-2's symmetry: a fact entry has no name, so neither the author
        # nor the assistant may write one.
        return _CANVAS_FACT_NAME_MESSAGE

    return None


async def _load_indexed_entry(source_id: str, book_id: int) -> CodexEntry | None:
    """The authoritative row behind a hit, or ``None`` when the hit is stale.

    ``None`` covers a malformed ``source_id``, a row that no longer exists, one
    belonging to another book (which the hard filter already prevents — this is
    the belt-and-braces half) and an **archived** one, which the index should
    have dropped.
    """
    parsed_id = _parse_entry_id(source_id)
    if parsed_id is None:
        return None
    entry = await codex_entries.get_by_id(parsed_id)
    if entry is None or entry.book_id != book_id or entry.archived:
        return None
    return entry


async def codex_search(
    context: "ToolContext", query: str, limit: int = DEFAULT_SEARCH_LIMIT
) -> str:
    """Search the turn's book codex semantically and return a compact text block.

    ``context`` is bound at build time by :func:`bind_codex_search`, leaving
    ``query`` and ``limit`` — exactly :class:`CodexSearchArgs`' fields — as the
    model-supplied arguments.

    What it does (the step file's Interface intent; ``retrieval.md`` → "Query
    surface"):

    1. embeds ``query`` through ``services/embedding.py:embed_text``;
    2. searches the sidecar through ``db/vector.py:search`` with **the tool
       context's** ``book_id`` as a hard filter, narrowed to the
       ``SourceKind.codex_entry`` corpus so a future corpus in the same table
       cannot leak into a codex answer, and ``limit`` as the cap;
    3. renders the hits **nearest first** into one compact block per hit,
       carrying each hit's **entry id first** (so a follow-up
       :func:`codex_read_entry` is unambiguous), its kind, its name when present,
       and the matched **chunk** text as the snippet — not the whole entry
       (``009.context.md`` → "Result formatting"; deterministic formatting is
       what makes it testable).

    **No score threshold is applied at any point** — see the module docstring.

    **It never raises.** No embedding provider, an empty or stale index, a
    transport failure: each returns its own informative string (a "nothing found"
    string is distinct from an error string), because a raising tool aborts the
    whole parent loop.
    """
    # The schema already bounds ``limit`` to 1..MAX_SEARCH_LIMIT, but the
    # callable is reachable without it (a direct call), so the ceiling is
    # re-applied here. This is bounded output ONLY — there is no score floor.
    try:
        effective_limit = max(0, min(int(limit), MAX_SEARCH_LIMIT))
    except (TypeError, ValueError):
        effective_limit = DEFAULT_SEARCH_LIMIT

    # 1. Embed the query. Every failure here is recoverable for the turn — the
    #    assistant loses pulled context, it does not fail — so each returns its
    #    own string instead of raising.
    try:
        query_vector = await embedding.embed_text(query)
    except embedding.EmbeddingError as err:
        logger.warning(
            "codex_search: query embedding failed for book %s (%s)",
            context.book_id,
            err.reason.value,
        )
        if err.reason is embedding.EmbeddingErrorReason.no_provider:
            return _NO_PROVIDER_MESSAGE
        if err.reason is embedding.EmbeddingErrorReason.unreachable:
            return _UNREACHABLE_MESSAGE
        return _EMBED_FAILED_MESSAGE
    except Exception:
        # The never-raise contract is absolute: a failure mode nobody enumerated
        # must still come back as a string (``web_search``'s shape).
        logger.warning(
            "codex_search: query embedding failed for book %s",
            context.book_id,
            exc_info=True,
        )
        return _EMBED_FAILED_MESSAGE

    # 2. Query the sidecar. ``context.book_id`` is a HARD filter and the corpus is
    #    narrowed to ``codex_entry``, so neither another book's codex nor a future
    #    corpus in the same table can occupy a result slot (US-085.AC-1).
    try:
        hits = await vector.search(
            book_id=context.book_id,
            query_vector=query_vector,
            kinds={vector.SourceKind.codex_entry},
            limit=effective_limit,
        )
    except Exception:
        logger.warning(
            "codex_search: sidecar query failed for book %s",
            context.book_id,
            exc_info=True,
        )
        return _INDEX_FAILED_MESSAGE

    # 3. Render, nearest first. The authoritative row supplies the kind and the
    #    name (``retrieval.md``: a hit is trusted for its snippet and nothing
    #    else); the chunk supplies the snippet.
    blocks: list[str] = []
    loaded: dict[str, CodexEntry | None] = {}
    try:
        for hit in hits:
            if len(blocks) >= effective_limit:
                # The cap is on what the model reads, and the sidecar already
                # applied it; re-applying it here keeps the block bounded
                # whatever the index hands back. Bounded output, not relevance.
                break
            if hit.source_id not in loaded:
                loaded[hit.source_id] = await _load_indexed_entry(
                    hit.source_id, context.book_id
                )
            entry = loaded[hit.source_id]
            if entry is None:
                # A stale index row: the entry is gone, archived or (impossibly,
                # given the filter) another book's. Dropped rather than rendered
                # — the read tool would refuse it, and the two tools present the
                # same world. All hits stale reads as "nothing found" below.
                continue
            blocks.append(_render_hit(hit, entry))
    except Exception:
        logger.warning(
            "codex_search: could not read the matching entries of book %s",
            context.book_id,
            exc_info=True,
        )
        return _HIT_READ_FAILED_MESSAGE

    if not blocks:
        # An empty index, a stale index and a query that simply matched nothing
        # are one outcome, and it is a normal one — never an error.
        return f'No codex entries found for "{query}".'

    return "\n\n".join(blocks)


async def codex_read_entry(context: "ToolContext", entry_id: str) -> str:
    """Read one codex entry of the turn's book in full and return it as text.

    ``context`` is bound at build time by :func:`bind_codex_read_entry`, leaving
    ``entry_id`` — the single :class:`CodexEntryReadArgs` field — as the only
    model-supplied argument.

    Loads the row through ``db/codex_entries.get_by_id`` (**never**
    ``services/codex.py``, which wants a ``BookAccess`` this context does not
    carry and whose capability check the chat turn's ``book_access`` dependency
    already satisfied) and returns the entry's kind, name and body as text.

    Four refusals, each an informative string and **never an exception** and
    never leaking the refused entry's content:

    - an id that is **malformed** (not a snowflake) or **unknown**;
    - an entry belonging to **another book** than ``context.book_id``
      (US-085.AC-1 — validated, not trusted);
    - an **archived** entry: the index drops archived entries, so refusing here
      keeps the two tools presenting the same world.
    """
    parsed_id = _parse_entry_id(entry_id)
    if parsed_id is None:
        # Malformed: refused exactly like an unknown id, and with the same
        # wording — the model learns nothing about what does or does not exist.
        return _ENTRY_NOT_FOUND_MESSAGE.format(entry_id=entry_id)

    try:
        entry = await codex_entries.get_by_id(parsed_id)
    except Exception:
        logger.warning(
            "codex_read_entry: could not read entry %s of book %s",
            parsed_id,
            context.book_id,
            exc_info=True,
        )
        return _ENTRY_READ_FAILED_MESSAGE

    # The book is VALIDATED against the context, never trusted from the id: an
    # unknown entry and one belonging to another book are indistinguishable from
    # out here, so another book's entry is neither read nor confirmed to exist
    # (US-085.AC-1). Neither branch touches the row's content.
    if entry is None or entry.book_id != context.book_id:
        return _ENTRY_NOT_FOUND_MESSAGE.format(entry_id=entry_id)

    if entry.archived:
        # The index drops archived entries, so ``codex_search`` can never point
        # here; refusing keeps the two tools presenting the same world. The
        # refusal names the state and leaks none of the entry's content.
        return _ENTRY_ARCHIVED_MESSAGE.format(entry_id=entry_id)

    return f"{_entry_header(entry)}\n\n{entry.body}"


async def write_codex_draft(
    context: "ToolContext", field: CanvasField, text: str
) -> str:
    """Draft into the codex entry the author has open, and confirm it (UC-076 /
    UC-077; US-086.AC-1 / US-087.AC-1).

    ``context`` is bound at build time by :func:`bind_write_codex_draft`, leaving
    ``field`` and ``text`` — exactly :class:`WriteCodexDraftArgs`' fields — as the
    model-supplied arguments. **The subject is never one of them**: the draft goes
    to ``context.subject``, the content-pane subject
    ``services/assistant_runtime.py:resolve_subject`` settled before the stream
    opened.

    What it does, in order:

    1. **Validates the write server-side**, mirroring
       ``frontend/src/work/subject.ts:checkWritePermission`` — because
       ``frontend-workspace.md`` requires a read-only subject to refuse "the
       author and the assistant alike", and enforcing that in one place per
       writer is what keeps the symmetry true now the assistant has arrived.
       Each of these is a **refusal**: an informative string, **no frame**, and
       nothing else happens:

       - the turn's subject is **not a codex entry** — a chapter, book state, any
         of the list kinds, the chats view, or **no subject at all**
         (``frontend-workspace.md`` → the content-pane editability table; a list
         "is a list view and cannot be edited");
       - the entry is **archived** (``subject.entry.archived``) — the
         ``resolveEditability`` row that reads "archived and read-only; restore
         it to make changes";
       - the caller is a **co-author** and ``context.access.collaboration_mode``
         is ``proposal`` — refused with a reason that **names FEAT-010** as the
         unbuilt mechanism, exactly as ``services/codex.py``'s save path refuses
         the author's own edit (``context.md`` decision 3; US-079.AC-2 is
         knowingly unmet, and this is where that gap is made visible rather than
         silently violated). The **owner** is never refused for mode;
       - ``field`` is ``"name"`` and the subject is a **fact** — a fact entry has
         no name (US-078.AC-2's symmetry). For an existing entry the kind comes
         off ``subject.entry.kind``; for UC-076's blank entry, which has no row,
         it is what ``subject.mode_key`` records (``edit-fact`` /
         ``edit-character`` / ``edit-location``).

       A **blank** entry (``subject.kind == "codex-entry"`` with
       ``subject.entry is None``) is otherwise **allowed** — UC-076 opens a blank
       entry of a chosen kind before any row exists.

    2. **Emits exactly one frame** through ``context.emit_frame`` — event name
       ``"canvas"``, payload a
       :class:`~app.models.schemas.chats.CanvasFrame` carrying the subject kind,
       the subject id as a **string** (``None`` for the blank entry), ``field``
       and ``text``. That emitter is a closure over the very queue ``run_turn``
       already pumps ``thinking`` / ``delta`` through, so the draft is ordered
       naturally among the surrounding content frames and no second transport
       exists. On every refusal path **no frame is emitted at all**.

    3. **Returns a short confirmation string** to the model, so
       ``chat_with_tools`` keeps looping rather than treating the turn as
       finished.

    **It touches no database.** No read, no write, no version row — the entry it
    drafts into is the row the turn already resolved, and nothing about this call
    reaches the ``codex_entries`` table (``context.md`` point 5). The author
    keeps, edits or discards the draft and saves through the ordinary UC-069 /
    UC-070 endpoint.

    **It never raises.** Every refusal above, a missing emitter (a context built
    without one) and a failure *inside* the emitter — a closed or broken queue —
    each return a string, because a raising tool is wrapped as ``RuntimeError``
    by the ``llm`` client and aborts the parent's whole loop with the error never
    reaching the model (``services/web_search.py:web_search``'s contract).
    """
    # The outer never-raise guard (``subagent_delegation.py:run_delegation``'s
    # shape): a failure mode nobody enumerated — a malformed context, a payload
    # the frame model rejects — must still come back as a string. ``Exception``
    # is deliberately broad; ``asyncio.CancelledError`` is a ``BaseException`` and
    # still propagates, so a cancelled turn is not swallowed.
    try:
        refusal = _refuse_write(context, field)
        if refusal is not None:
            # A refusal emits NOTHING: the author's editor is left exactly as it
            # was, and the model is told why in a string it can act on.
            return refusal

        emit_frame = context.emit_frame
        if emit_frame is None:
            # A context built without a stream (a bound tool outside a real turn):
            # there is nowhere to put the frame, so this is a returned string, not
            # a raise.
            return _CANVAS_NO_STREAM_MESSAGE

        subject = context.subject
        if subject is None:  # unreachable: ``_refuse_write`` already refused it
            return _CANVAS_NOT_A_CODEX_ENTRY_MESSAGE
        frame = CanvasFrame(
            subject_kind="codex-entry",
            # ``None`` is UC-076's blank entry, which has no row and therefore no
            # id; an existing entry's id crosses as a **string** (the house rule —
            # snowflakes exceed the JS safe-integer range).
            subject_id=None if subject.entry is None else str(subject.entry.id),
            field=field,
            text=text,
        )
        try:
            # EXACTLY ONE frame, through the turn's own emitter — the same
            # put-onto-the-queue path ``thinking`` / ``delta`` travel, running
            # inside the same ``drive()`` task, so the draft interleaves naturally
            # with the surrounding content frames and no second transport exists.
            await emit_frame("canvas", frame)
        except Exception:
            # A closed or broken queue. DoD-11: still a string — a raising tool
            # aborts the parent's whole loop and the model never learns anything.
            logger.warning(
                "write_codex_draft: the canvas frame could not be delivered for "
                "book %s",
                context.book_id,
                exc_info=True,
            )
            return _CANVAS_DELIVERY_FAILED_MESSAGE

        # A short confirmation, so ``chat_with_tools`` keeps looping rather than
        # treating this round as the end of the turn.
        return _CANVAS_WRITTEN_MESSAGE.format(field=field)
    except Exception:
        logger.warning(
            "write_codex_draft: the draft could not be written for book %s",
            getattr(context, "book_id", None),
            exc_info=True,
        )
        return _CANVAS_FAILED_MESSAGE


def bind_codex_search(context: "ToolContext") -> Callable[..., object]:
    """Bind ``context`` into :func:`codex_search` — the ``ToolDef.binder``.

    Returns a callable whose free parameters are **exactly**
    :class:`CodexSearchArgs`' field names (``query`` / ``limit``), which is what
    the ``llm`` client's ``inspect.signature(func).parameters`` validation and
    ``func(**kwargs)`` dispatch require, there being no per-request context
    argument.
    """
    return functools.partial(codex_search, context)


def bind_codex_read_entry(context: "ToolContext") -> Callable[..., object]:
    """Bind ``context`` into :func:`codex_read_entry` — the ``ToolDef.binder``.

    Returns a callable whose only free parameter is
    :class:`CodexEntryReadArgs`' single field (``entry_id``), for the same reason
    as :func:`bind_codex_search`.
    """
    return functools.partial(codex_read_entry, context)


def bind_write_codex_draft(context: "ToolContext") -> Callable[..., object]:
    """Bind ``context`` into :func:`write_codex_draft` — the ``ToolDef.binder``.

    Returns a callable whose free parameters are **exactly**
    :class:`WriteCodexDraftArgs`' field names (``field`` / ``text``). Binding is
    also what carries the turn's subject and its frame emitter into the tool: the
    model supplies neither, and cannot.
    """
    return functools.partial(write_codex_draft, context)
