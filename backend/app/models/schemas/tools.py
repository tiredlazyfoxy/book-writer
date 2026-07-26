"""Tool argument schemas (feature 011, step 002).

Declarative Pydantic schemas — the typed argument contracts for entries in
``services/tools.py:TOOL_REGISTRY``. Plain data shapes, no logic (see
``docs/architecture/backend.md`` — ``models/`` is tables + schemas only).

A tool's ``args_schema`` field names are **load-bearing twice over**: they become
the JSON-schema property names the model sees (via
``llm.pydantic_to_openai_tool``) *and* they must be exactly the keyword parameters
the tool callable accepts, because the ``llm`` client applies decoded JSON args as
``func(**kwargs)`` and validates them against ``inspect.signature`` (``context.md``
→ tool callables). Changing a field name here means changing the callable
signature in ``services/web_search.py`` in lockstep.

Skeleton (011 step 002): field names / types / defaults are frozen. DTOs are
declarative — there is nothing to leave unimplemented.
"""

from pydantic import BaseModel, Field


class WebSearchArgs(BaseModel):
    """Arguments for the ``web_search`` tool.

    - ``query`` — the free-text search query.
    - ``num_results`` — how many results to request, bounded to the Google
      Custom Search JSON API's per-request maximum of 10; optional with a sane
      default.

    Field names bind directly to ``web_search``'s keyword parameters.
    """

    query: str
    num_results: int = Field(default=5, ge=1, le=10)
