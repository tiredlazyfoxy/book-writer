"""Tests for the code-defined tool registry (feature 011, step 002).

Bound to the frozen skeleton signatures (status.md -> Skeleton -> Step 002):

    app.services.tools  (NEW):
        @dataclass(frozen=True) class ToolDef
            name: str
            description: str
            args_schema: type[BaseModel]
            callable: Callable[..., object]
        TOOL_REGISTRY: list[ToolDef]           # one entry: web_search
        def resolve_tools(allowed_names: Collection[str] | None) -> list[ToolDef]
        def build_tool_bindings(
            tools: list[ToolDef],
        ) -> tuple[list[dict[str, object]], dict[str, Callable[..., object]]]

    app.services.web_search.web_search  (NEW callable, keyword params query/num_results)
    app.models.schemas.tools.WebSearchArgs  (NEW; fields query, num_results)

Expected values come from the SPEC ONLY — the step DoD (DoD-3, DoD-4, DoD-5), the
step Interface intent, context.md decision 9, and `assistant-config.md` ->
"Tool gating" / the `chat_with_tools` protocol block — never from implementation
internals.

Key spec facts asserted here:
    - TOOL_REGISTRY holds exactly one entry, named `web_search`, with a non-empty
      description and an args schema whose field names are EXACTLY the callable's
      keyword parameters — the property the `llm` client validates via
      `inspect.signature` (DoD-3).
    - build_tool_bindings yields OpenAI tool definitions (name/description/JSON
      schema) plus a name->callable map with an IDENTICAL key set, so the client's
      pre-flight cannot raise ValueError (DoD-4).
    - A null (None) mode resolves to the whole registry; an explicit allow-list
      resolves to just those tools; an unknown name is skipped, never raised
      (DoD-5, context.md decision 9 / the 013.codex seam).
"""

import inspect

from app.models.schemas.tools import WebSearchArgs
from app.services import tools
from app.services.web_search import web_search


# DoD-3: TOOL_REGISTRY contains exactly one entry, named `web_search`, with a
# non-empty description, its args schema is WebSearchArgs and its callable is
# web_search.
def test_registry_has_single_web_search_entry__DoD3():
    assert len(tools.TOOL_REGISTRY) == 1

    entry = tools.TOOL_REGISTRY[0]
    assert entry.name == "web_search"
    assert isinstance(entry.description, str)
    assert entry.description.strip() != ""
    assert entry.args_schema is WebSearchArgs
    assert entry.callable is web_search


# DoD-3: the args schema's field names are EXACTLY the keyword parameters the
# callable accepts — the invariant the `llm` client checks with inspect.signature.
def test_args_schema_fields_match_callable_params__DoD3():
    entry = tools.TOOL_REGISTRY[0]

    schema_fields = set(entry.args_schema.model_fields.keys())
    callable_params = set(inspect.signature(entry.callable).parameters.keys())

    assert schema_fields == callable_params


# DoD-4: build_tool_bindings returns OpenAI tool definitions and a name->callable
# map whose key sets are IDENTICAL — so chat_with_tools' pre-flight cannot raise
# ValueError (every definition name has a callable).
def test_build_bindings_have_identical_key_sets__DoD4():
    definitions, callables = tools.build_tool_bindings(tools.TOOL_REGISTRY)

    assert isinstance(definitions, list)
    assert isinstance(callables, dict)

    definition_names = {d["function"]["name"] for d in definitions}
    assert definition_names == set(callables.keys())


# DoD-4: each OpenAI definition carries the tool's name, a non-empty description
# and a JSON schema (parameters) exposing the args field names as properties; the
# name maps to the actual callable.
def test_build_bindings_carry_name_description_schema__DoD4():
    definitions, callables = tools.build_tool_bindings(tools.TOOL_REGISTRY)

    assert len(definitions) == 1
    function = definitions[0]["function"]

    assert function["name"] == "web_search"
    assert isinstance(function["description"], str)
    assert function["description"].strip() != ""

    parameters = function["parameters"]
    properties = parameters["properties"]
    # The args schema's fields surface as JSON-schema properties.
    assert set(WebSearchArgs.model_fields.keys()) <= set(properties.keys())

    # The name resolves to the real callable in the paired map.
    assert callables["web_search"] is web_search


# DoD-5: a null (None) mode resolves to the WHOLE registry (the 013.codex seam:
# null mode == every tool allowed).
def test_resolve_null_is_whole_registry__DoD5():
    resolved = tools.resolve_tools(None)

    assert [t.name for t in resolved] == [t.name for t in tools.TOOL_REGISTRY]


# DoD-5: an explicit allow-list resolves to just the named tools.
def test_resolve_allowlist_selects_named_tools__DoD5():
    resolved = tools.resolve_tools(["web_search"])

    assert [t.name for t in resolved] == ["web_search"]


# DoD-5: a name with no registry entry is SKIPPED, not raised — and the known
# names in the same allow-list still resolve.
def test_resolve_unknown_name_is_skipped_not_raised__DoD5():
    resolved = tools.resolve_tools(["web_search", "does_not_exist"])

    # No exception; the unknown name simply does not appear.
    assert [t.name for t in resolved] == ["web_search"]


# DoD-5: an allow-list of only unknown names resolves to nothing (skipped, not
# raised) — proving None (whole registry) is distinct from an empty selection.
def test_resolve_only_unknown_names_yields_empty__DoD5():
    assert tools.resolve_tools(["ghost_tool", "another_ghost"]) == []
