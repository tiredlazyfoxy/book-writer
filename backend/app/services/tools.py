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
"""

import logging
from collections.abc import Callable, Collection
from dataclasses import dataclass

import llm
from pydantic import BaseModel

from app.models.schemas.tools import WebSearchArgs
from app.services.web_search import web_search

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolDef:
    """A single tool the assistant may call. A frozen, typed record (not a dict).

    - ``name`` — the tool name the model calls and the key in both built maps.
    - ``description`` — the model-facing description; non-empty.
    - ``args_schema`` — a ``BaseModel`` subclass whose field names are exactly the
      callable's keyword parameters.
    - ``callable`` — the implementation. Typed loosely (``Callable[..., object]``)
      so a future context-bearing tool bound with a closure / ``functools.partial``
      still fits, and so a sync-or-async callable is accepted (``context.md`` →
      tool-callable binding).
    """

    name: str
    description: str
    args_schema: type[BaseModel]
    callable: Callable[..., object]


# The whole catalogue at this feature: web search only. A plain literal list,
# no decorator, no register function (mirrors ``TABLE_REGISTRY`` /
# ``VECTOR_SOURCE_REGISTRY``). Never exported — only selections persist.
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
) -> tuple[list[dict[str, object]], dict[str, Callable[..., object]]]:
    """Build the ``(tools_definitions, tools)`` pair ``chat_with_tools`` wants.

    Returns the OpenAI tool definitions (each via
    ``llm.pydantic_to_openai_tool(name, description, args_schema)``) and the
    name → callable map, built together so their key sets are always identical —
    a mismatch makes the client raise ``ValueError`` at pre-flight
    (``assistant-config.md`` → "Tool gating").

    Skeleton (011 step 002): UNIMPLEMENTED.
    """
    definitions: list[dict[str, object]] = []
    bindings: dict[str, Callable[..., object]] = {}
    for tool in tools:
        definitions.append(
            llm.pydantic_to_openai_tool(tool.name, tool.description, tool.args_schema)
        )
        bindings[tool.name] = tool.callable
    return definitions, bindings
