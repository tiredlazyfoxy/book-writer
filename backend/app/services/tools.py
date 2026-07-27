"""The code-defined tool catalogue — ``ToolDef`` + ``TOOL_REGISTRY`` and the
selection helpers the ``chat_with_tools`` loop consumes (feature 011, step 002).

The registry mirrors ``services/db_import_export.py:TABLE_REGISTRY`` and
``db/vector.py:VECTOR_SOURCE_REGISTRY``: a **plain module-level literal list**,
with no decorator and no register function (``assistant-config.md`` names them as
the shape this copies). ``ToolDef`` has four named members, so a frozen dataclass
(the ``services/authz.py:BookAccess`` precedent) reads better than a 4-tuple. The
catalogue is the source of truth; only *selections* ever persist — it is never
exported.

Two helpers sit on top:

- :func:`resolve_tools` — turns an optional allowed-name collection into the
  matching ``ToolDef`` list. **Null mode means the whole registry**; a name with
  no registry entry is skipped and logged, never an error. The null-mode branch
  is the seam ``013.codex`` replaces with real ``mode_tool`` gating.
- :func:`build_tool_bindings` — turns a ``ToolDef`` list into the pair the ``llm``
  client wants: the OpenAI tool definitions (via
  ``llm.pydantic_to_openai_tool``) and the name → callable map. They are built
  together and always carry identical key sets, because a mismatch makes the
  client raise ``ValueError`` at pre-flight.

Skeleton (011 step 002): ``ToolDef`` and ``TOOL_REGISTRY`` are the frozen
declarative contract; :func:`resolve_tools` and :func:`build_tool_bindings`
signatures are frozen and their bodies are UNIMPLEMENTED.

Skeleton (013 step 009): the catalogue gains **bound** tools. The ``llm`` client
dispatches a tool as ``func(**kwargs)`` with **no per-request context argument**,
so anything a tool needs from the turn it runs inside must be closed over at
binding time. Three additions express that:

- :class:`ToolContext` — the frozen per-turn value a bound tool is closed over
  (this step: the turn's book id; ``010.shared-canvas-write`` extends it with the
  content-pane subject and the frame emitter, additively);
- ``ToolDef.binder`` — an **optional** callable that, given a
  :class:`ToolContext`, returns the callable to dispatch. It is additive
  precisely so ``web_search``'s context-free entry keeps its plain ``callable``
  and needs no edit;
- :func:`build_tool_bindings` takes the tool context and calls the binder for
  every bound tool, leaving the context-free path exactly as ``011`` shipped it.

Skeleton (013 step 010): the catalogue gains the **shared-canvas write**. Nothing
about the resolution machinery changes — :class:`ToolContext` grows three further
**defaulted** fields (the turn's access, its resolved content-pane subject and a
frame emitter), and ``write_codex_draft`` joins the registry as a fourth entry,
bound exactly like the two codex tools. The widening is strictly additive:
``ToolContext(book_id=…)`` still constructs, and every step-009 binding behaves
identically.
"""

import logging
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass
from typing import TYPE_CHECKING

import llm
from pydantic import BaseModel

from app.models.schemas.tools import WebSearchArgs
from app.services import authz
from app.services.codex_tools import (
    CodexEntryReadArgs,
    CodexSearchArgs,
    WriteCodexDraftArgs,
    bind_codex_read_entry,
    bind_codex_search,
    bind_write_codex_draft,
)
from app.services.web_search import web_search

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, see ToolContext
    from app.services.assistant_runtime import ResolvedSubject

logger = logging.getLogger(__name__)


# How a bound tool puts an SSE frame onto the stream of the turn it runs inside:
# ``await emit_frame(event_name, payload)`` (013 step 010).
#
# ``services/chat_turn.py:run_turn`` supplies a closure over the very
# ``asyncio.Queue`` it already pumps ``thinking`` / ``delta`` through, and wraps
# the pair into its own ``TurnFrame`` — so a tool's frame is ordered naturally
# among the surrounding content frames and **no second transport exists**. The
# alias is spelled ``(str, BaseModel)`` rather than ``(TurnFrame,)`` because
# ``chat_turn`` imports this module: naming its frame envelope here — or
# constructing one in a tool — would be an import cycle. The event **name** is
# still the tool's to choose, which is what keeps the frame vocabulary a
# protocol rather than a per-caller decision.
FrameEmitter = Callable[[str, BaseModel], Awaitable[None]]


@dataclass(frozen=True)
class ToolContext:
    """What a **bound** tool needs from the turn it runs inside.

    A frozen typed record (the ``ToolDef`` / ``ParentTurn`` / ``ResolvedSubject``
    precedent — no free dictionaries), built once per turn by
    ``services/chat_turn.py:run_turn`` and closed over by every bound tool's
    callable, because the ``llm`` client passes no context argument.

    - ``book_id`` — the turn's book. For the codex tools this is the **hard
      filter** ``retrieval.md`` requires: the model cannot name a book, so a hit
      or a read can only ever concern this one (US-085.AC-1). Unchanged by step
      010 and still the only book the read/search tools consult.
    - ``access`` — the turn's :class:`~app.services.authz.BookAccess` (013 step
      010). Carried because the shared-canvas write must mirror
      ``frontend/src/work/subject.ts:checkWritePermission`` **server-side**, and
      that verdict needs the caller's ``role`` and the book's
      ``collaboration_mode`` — neither of which any other value on this record
      carries (``context.md`` decision 3: a co-author's write in a
      ``proposal``-mode book is refused, an owner's is not). ``book_id`` above
      stays the frozen hard filter; ``run_turn`` builds both from the same
      resolved turn, so they always name the same book.
    - ``subject`` — the turn's resolved content-pane subject
      (``services/assistant_runtime.py:ResolvedSubject``, 013 step 007), i.e.
      *what the author is looking at*. The shared-canvas write targets it and
      nothing else: the tool takes no subject argument, so the model cannot aim a
      draft at a subject the author does not have open.
    - ``emit_frame`` — the turn's :data:`FrameEmitter`; how a tool puts an SSE
      frame onto the stream (013 step 010).

    All three step-010 fields **default**, so step 009's
    ``ToolContext(book_id=…)`` construction keeps binding and a caller with no
    turn to speak of (a sub-agent built without one) still gets a usable record —
    a tool that needs a field it was not given refuses with a string rather than
    failing.

    The ``ResolvedSubject`` annotation is quoted and its import is
    ``TYPE_CHECKING``-only: ``services/assistant_runtime.py`` imports **this**
    module (it resolves the turn's tools), so a runtime import here would be a
    cycle — the ``codex_tools.py`` ↔ ``tools.py`` discipline, applied the other
    way round.
    """

    book_id: int
    access: authz.BookAccess | None = None
    subject: "ResolvedSubject | None" = None
    emit_frame: FrameEmitter | None = None


# A ``ToolDef.binder``: given the turn's context, return the callable to
# dispatch. The returned callable's free parameters must be **exactly** the
# ``args_schema`` field names — the ``llm`` client validates them against
# ``inspect.signature`` and applies decoded JSON args as ``func(**kwargs)``.
ToolBinder = Callable[[ToolContext], Callable[..., object]]


@dataclass(frozen=True)
class ToolDef:
    """A single tool the assistant may call. A frozen, typed record (not a dict).

    - ``name`` — the tool name the model calls and the key in both built maps.
    - ``description`` — the model-facing description; non-empty.
    - ``args_schema`` — a ``BaseModel`` subclass whose field names are exactly the
      callable's keyword parameters.
    - ``callable`` — the implementation, for a **context-free** tool. Typed
      loosely (``Callable[..., object]``) so a sync-or-async callable is accepted
      (``context.md`` → tool-callable binding).
    - ``binder`` — for a **bound** tool: given the turn's :class:`ToolContext`,
      it returns the callable to dispatch (013 step 009). Additive, so
      ``web_search``'s context-free entry is untouched.

    **Exactly one of ``callable`` / ``binder`` is set.** A binder-bearing entry
    has no context-free callable to offer — the whole reason it needs a binder is
    that the ``llm`` client dispatches ``func(**kwargs)`` with no context
    argument — so carrying a plain callable beside it would be a callable whose
    signature does not match its ``args_schema``. :func:`build_tool_bindings` is
    the one place the pair is resolved.
    """

    name: str
    description: str
    args_schema: type[BaseModel]
    callable: Callable[..., object] | None = None
    binder: ToolBinder | None = None


# The whole catalogue: web search (011), the two codex tools (013 step 009) and
# the shared-canvas write (013 step 010).
# A plain literal list, no decorator, no register function (mirrors
# ``TABLE_REGISTRY`` / ``VECTOR_SOURCE_REGISTRY``). Never exported — only
# selections persist.
#
# The two codex entries are the **first bound** entries and the first entries a
# mode must *select* to reach: under step 007's gating a mode with no
# ``mode_tool`` row for them cannot see them, and a subject with no mode gets
# ``assistant_runtime.BASE_TOOL_NAMES`` — which does not name them either.
TOOL_REGISTRY: list[ToolDef] = [
    ToolDef(
        name="web_search",
        description=(
            "Search the public web via Google Custom Search and return a "
            "compact list of result titles, snippets and links for a query."
        ),
        args_schema=WebSearchArgs,
        callable=web_search,
    ),
    ToolDef(
        name="codex_search",
        description=(
            "Search this book's codex — its characters, locations and facts — "
            "for the entries most relevant to a plain-language query, and "
            "return each match's entry id, kind, name and the matching passage."
        ),
        args_schema=CodexSearchArgs,
        binder=bind_codex_search,
    ),
    ToolDef(
        name="codex_read_entry",
        description=(
            "Read one codex entry of this book in full by its id — its kind, "
            "its name and its whole body — typically an id returned by the "
            "codex search tool."
        ),
        args_schema=CodexEntryReadArgs,
        binder=bind_codex_read_entry,
    ),
    ToolDef(
        name="write_codex_draft",
        description=(
            "Write a draft into the codex entry the author currently has open, "
            "so they can read it, edit it and decide whether to keep it. "
            "Nothing is saved: the draft only appears in the author's editor. "
            "Choose 'name' or 'body' for the part you are writing, and send the "
            "whole text at once — it replaces that part of the draft."
        ),
        args_schema=WriteCodexDraftArgs,
        binder=bind_write_codex_draft,
    ),
]


def resolve_tools(allowed_names: Collection[str] | None) -> list[ToolDef]:
    """Return the ``ToolDef``s selected by ``allowed_names``.

    ``None`` (null mode) resolves to the **whole** ``TOOL_REGISTRY``. A concrete
    collection resolves to just the registry entries whose ``name`` appears in it;
    an allowed name with no registry entry is **skipped and logged**, never an
    error (``assistant-config.md`` → "the catalogue is source of truth"). The
    null-mode branch is the ``013.codex`` seam for real ``mode_tool`` gating.

    Skeleton (011 step 002): the null-mode branch below is the seam ``013.codex``
    replaces with real ``mode_tool`` gating.
    """
    if allowed_names is None:
        # Null mode: the whole catalogue is allowed (today: just ``web_search``).
        # This branch is what ``013.codex`` replaces with real ``mode_tool``
        # gating once a mode-bearing subject exists.
        return list(TOOL_REGISTRY)

    allowed = set(allowed_names)
    known = {tool.name for tool in TOOL_REGISTRY}
    for name in allowed - known:
        logger.warning(
            "resolve_tools: allowed tool %r has no TOOL_REGISTRY entry — skipped",
            name,
        )
    return [tool for tool in TOOL_REGISTRY if tool.name in allowed]


def build_tool_bindings(
    tools: list[ToolDef],
    context: ToolContext | None = None,
) -> tuple[list[dict[str, object]], dict[str, Callable[..., object]]]:
    """Build the ``(tools_definitions, tools)`` pair ``chat_with_tools`` wants.

    Returns the OpenAI tool definitions (each via
    ``llm.pydantic_to_openai_tool(name, description, args_schema)``) and the
    name → callable map, built together so their key sets are always identical —
    a mismatch makes the client raise ``ValueError`` at pre-flight
    (``assistant-config.md`` → "Tool gating"). That pre-flight contract is
    unchanged by this step: a tool that cannot be bound is left out of **both**
    maps, never out of one.

    ``context`` is the turn's :class:`ToolContext` (013 step 009). A ``ToolDef``
    carrying a ``binder`` is dispatched through ``binder(context)``; one carrying
    a plain ``callable`` is used **unchanged**, so ``web_search`` behaves exactly
    as ``011`` shipped it. ``context`` defaults to ``None`` for the callers that
    have no turn to speak of — a bound tool is then skipped and logged, since
    there is nothing to close it over.
    """
    definitions: list[dict[str, object]] = []
    bindings: dict[str, Callable[..., object]] = {}
    for tool in tools:
        if tool.binder is not None:
            if context is None:
                # Nothing to close the tool over: it is left out of BOTH maps, so
                # the client's pre-flight ("every definition name has a
                # callable") still holds. This is the pre-013 truth for every
                # caller that has no turn context — before this step no registry
                # entry was bound at all.
                logger.warning(
                    "build_tool_bindings: tool %r needs a tool context and none "
                    "was supplied — skipped",
                    tool.name,
                )
                continue
            # A bound tool: the binder closes the turn's context over the
            # callable, leaving exactly the ``args_schema`` field names free —
            # which is what the ``llm`` client's ``inspect.signature``
            # validation and its ``func(**kwargs)`` dispatch require.
            definitions.append(
                llm.pydantic_to_openai_tool(
                    tool.name, tool.description, tool.args_schema
                )
            )
            bindings[tool.name] = tool.binder(context)
            continue
        if tool.callable is None:
            # Neither a callable nor a binder: a malformed registry entry. Skipped
            # and logged rather than raised, like an unknown allowed name.
            logger.warning(
                "build_tool_bindings: tool %r has neither a callable nor a "
                "binder — skipped",
                tool.name,
            )
            continue
        definitions.append(
            llm.pydantic_to_openai_tool(tool.name, tool.description, tool.args_schema)
        )
        bindings[tool.name] = tool.callable
    return definitions, bindings
