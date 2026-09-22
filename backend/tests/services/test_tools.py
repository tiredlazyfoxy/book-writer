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
from app.services.memo_tools import CreateMemoArgs, bind_create_memo
from app.services.web_search import web_search


# DoD-3: TOOL_REGISTRY's contents are known and pinned: `web_search` is present
# and FIRST, with a non-empty description, its args schema is WebSearchArgs and
# its callable is web_search.
#
# Updated by 013.codex step 009, which added the two BOUND codex entries
# (`codex_search` / `codex_read_entry`) to the catalogue, and again by step 010,
# which added the bound `write_codex_draft` entry; the original "exactly one
# entry" wording was superseded by those steps' Interface intent (step 009's
# DoD-12, step 010's DoD-12). The intent of this test -- the registry's contents
# are pinned, not open-ended -- is unchanged.
#
# Widened again by 015.chapter-writing-free-mode step 010, whose DoD-1 requires
# the four chapter tools (`read_chapter_text` / `set_chapter_text` /
# `update_selection` / `add_text`) to be in this registry with names colliding
# with no existing entry -- so this pinned name set is superseded by that step's
# own contract. Their own assertions live in tests/services/test_chapter_tools.py.
#
# Widened once more by 016.chapter-close-continuity, whose DoD-14 requires the five
# close-chapter tools (`draft_chapter_summary` / `draft_chapter_notes` /
# `propose_active_notes` / `raise_check_flag` / `read_continuity_context`) to be
# registered and context-bound (`status.md` -> `## Skeleton` -> "Backend — tools
# registry"). Their own assertions live in tests/test_close_tools.py. As with every
# widening above, the intent of THIS test is unchanged: the registry's contents are
# pinned rather than open-ended, and `web_search` is still its first entry.
#
# Widened once more by fast/007.codex-create-from-chat, whose DoD-8 requires
# `create_codex_entry` to be a TOOL_REGISTRY member with a binder (its own
# assertions live in tests/services/test_codex_create_tool.py). As with every
# widening above, this stays an EXACT-set assertion -- never a "contains" check.
#
# Widened once more by 025.codex-listing-tools, which takes the registry from 14
# entries to 18: the four codex LISTING tools (`codex_list_entries` /
# `codex_list_characters` / `codex_list_locations` / `codex_list_facts`) join the
# catalogue under exactly those names (025/plan.md -> Interface -> "All 18
# TOOL_REGISTRY entries"). This is a FORCED widening of a pre-existing exact set,
# not new coverage: 025 deliberately leaves symbol-existence untested. Those tools'
# own assertions live in tests/services/test_codex_list_tools.py. The intent of
# THIS test is unchanged:
# the registry's contents are pinned rather than open-ended, `web_search` is still
# its first entry, and the set is still EXACT.
#
# Widened once more by 026.memos step 008, which takes the registry from 18 entries
# to 19: `create_memo` joins the catalogue under exactly that name, in the EXISTING
# `"book"` group (`008.create-memo-tool.md` -> Interface intent ->
# `backend/app/services/tools.py`; `026/context.md` -> decision 9). This is a FORCED
# widening of a pre-existing exact set, not new coverage -- that entry's own
# assertions are `test_create_memo_registry_entry__026_DoD10` below. The intent of
# THIS test is unchanged: `web_search` is still its first entry and the set is still
# EXACT.
def test_registry_has_single_web_search_entry__DoD3():
    assert {t.name for t in tools.TOOL_REGISTRY} == {
        "web_search",
        "codex_search",
        "codex_read_entry",
        "write_codex_draft",
        "create_codex_entry",  # fast/007 DoD-8
        "read_chapter_text",
        "set_chapter_text",
        "update_selection",
        "add_text",
        "draft_chapter_summary",
        "draft_chapter_notes",
        "propose_active_notes",
        "raise_check_flag",
        "read_continuity_context",
        "codex_list_entries",  # 025
        "codex_list_characters",  # 025
        "codex_list_locations",  # 025
        "codex_list_facts",  # 025
        "create_memo",  # 026 step 008
    }

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


# ---------------------------------------------------------------------------
# 025.codex-listing-tools — DoD-6
# ---------------------------------------------------------------------------


# 025 DoD-6: ALL 18 TOOL_REGISTRY entries declare a `group`, and every declared
# value is one of the three machine keys the wire contract allows
# (`025/plan.md` -> Interface -> `backend/app/services/tools.py`; `025/context.md`
# -> "Shared vocabulary" -> **group**). An invariant over a table a human will
# edit again: a nineteenth entry added with no `group`, or with a typo'd one, is
# exactly what this catches. The tool-for-tool assignment table is deliberately
# NOT duplicated here (`025/plan.md` -> Test plan, DoD-18).
#
# 026.memos step 008 adds the nineteenth entry -- the very case the count above was
# written to catch -- so the count moves with it, and the invariant is now ALSO
# 026's DoD-10 ("every registry entry still declares a valid group"): the new entry
# takes the EXISTING `"book"` group, so the valid-group set is NOT widened
# (`026/context.md` -> decision 9). Nothing else here changes.
def test_every_registry_entry_declares_a_valid_group__025_DoD6__026_DoD10():
    assert len(tools.TOOL_REGISTRY) == 19

    valid_groups = {"codex", "book", "web"}
    for entry in tools.TOOL_REGISTRY:
        assert isinstance(entry.group, str), entry.name
        assert entry.group in valid_groups, f"{entry.name} declares group={entry.group!r}"

    # All three groups are actually in use — the registry is not one flat group.
    assert {entry.group for entry in tools.TOOL_REGISTRY} == valid_groups


# ---------------------------------------------------------------------------
# 026.memos step 008 — DoD-10 (the `create_memo` registry entry)
# ---------------------------------------------------------------------------


# 026 DoD-10 (architecture — `quick-reference.md` -> TOOL_REGISTRY): the entry
# declares the name `create_memo`, the group `"book"`, the args schema
# `CreateMemoArgs`, and a BINDER with the plain callable left unset — the
# exactly-one-of rule every context-bearing tool follows
# (`008.create-memo-tool.md` -> Interface intent). The description is asserted
# non-blank only: its WORDING is the coder's, not a test surface.
def test_create_memo_registry_entry__026_DoD10():
    matches = [entry for entry in tools.TOOL_REGISTRY if entry.name == "create_memo"]
    assert len(matches) == 1, "create_memo is not a single registry entry"
    entry = matches[0]

    assert entry.group == "book"
    assert entry.args_schema is CreateMemoArgs
    assert entry.binder is bind_create_memo
    assert entry.callable is None

    assert isinstance(entry.description, str)
    assert entry.description.strip() != ""
