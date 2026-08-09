# Outcome — 024.chat-agent-loop

Intended `docs/architecture/` changes, for `/architect` to apply at finalization. Seeded from
`docs/.cache/ultra/024.chat-agent-loop/design-notes.md` (D1–D7) and this plan. Nothing here is
applied by the coder — `docs/architecture/` stays read-only through this feature.

## `docs/architecture/assistant-runtime.md`

- **Section "The shared-canvas write for chapters, as built" → "The tools ship unreachable, by
  design."** Currently states no `mode_tool` rows were seeded and changing that "would be a
  FEAT-020 default-policy decision" pointing the default "in the unsafe direction the
  empty-allowlist rule exists to avoid." **Reversed by this feature, by explicit author
  decision (D4):** `write-chapter`'s chapter tools are now seeded by default. Update to record
  that the default-policy decision was made, by whom (the author, not an inferred default), and
  that the empty-allowlist *rule* is unchanged — only the seeded starting state.
- **Section "The close-chapter procedure, as built" → "The tools ship registered but unreachable —
  and the feature is inert without them."** States feature 016 "is delivered but inert until an
  administrator assigns the five tools to the `close-chapter` mode." **No longer true** — this
  feature seeds those five tools by default. Update to state feature 016's close procedure is now
  live on a fresh install, and record the accepted risk (a model-driven close run now writes real
  artifacts) alongside the existing domain rules in `domain-continuity.md`.
- **Section "Tool gating" → case 1 discussion, and the "013.codex closed it" decision history.**
  The codex modes (`edit-character`/`edit-location`/`edit-fact`) previously resolved to an empty
  allowlist by default; they now resolve to a seeded default set (`web_search`, `codex_search`,
  `codex_read_entry`, `write_codex_draft`). Update the narrative to note the seeded starting state
  without changing the stated gating rule (mode-bearing subject gets exactly its `mode_tool` rows;
  zero rows is still an empty allowlist for a mode an admin has since edited down to nothing).
- **Section "The SSE frame vocabulary."** Currently: "Five named frames as shipped: `thinking`,
  `delta`, `done`, `error`... and `canvas`." Add `tool_call` and `tool_result` (seven total),
  carrying `ToolCallFrame(tool_name, arguments)` / `ToolResultFrame(tool_name, result, ok)`. Note
  they are emitted generically by a wrapper around every bound tool call (not by individual tools
  calling `emit_frame` themselves, unlike `canvas`), and that tool arguments arrive whole (same
  accepted-whole-not-streamed property `canvas` already has).
- **New subsection, "Tool-call visibility (feature 024)."** Record the wrapper pattern: every
  entry of a turn's `tool_map` is wrapped once, uniformly, in `chat_turn.py`, closing over the
  turn's `emit_frame` and a per-turn trace list; `chat_with_tools` itself is unmodified and
  unforked. Cross-reference the reference-project pattern this generalizes from (harvest 3) and
  that BookWriter has exactly one call site so the wrapper is written once, unlike the reference's
  three duplicated wrappers.

Reason for all of the above: design notes D1 and D4, both explicit author decisions, both
reversing or extending statements this document currently makes as settled fact.

## `docs/architecture/domain-chat.md`

- **`ChatMessage` field table.** Add a row: `tool_trace` | nullable — the ordered tool-call trace
  for this message, when the turn made any tool calls; JSON-in-TEXT gated by a Pydantic model
  (`ToolTrace`/`ToolTraceEntry`), same pattern `Chat.sampling_params` uses. Cross-reference
  `backend/persistence.md`'s "JSON-in-TEXT gated by a Pydantic model" section as the third
  instance of the pattern (after `LlmServer.enabled_models` and `Chat.sampling_params`).

Reason: design note D2 — a genuinely new persisted column, not previously in the entity map.

## `docs/architecture/quick-reference.md` (the architecture one, not `docs/product/`'s)

- Add `tool_call` / `tool_result` to whatever SSE frame table exists there alongside the other
  five.
- Add `ChatMessage.tool_trace` to whatever column/DTO table lists `ChatMessage`'s fields.

Reason: this file is the architecture folder's dense concrete-detail exception (endpoints, DTOs,
columns) — new frame kinds and a new column belong there per the folder's own write-rules.

## Cross-cutting note for `/architect`

**Delivery-status implication.** `docs/product/features.md` (2026-07-31 reconciliation) records
explicitly: "the five assistant modes seed with no prompts and no tool assignments, so every
assistant-facing feature below needs an administrator to configure it... before it does
anything." This feature removes that precondition for a fresh install. Whether this changes any
`docs/product/` status field (e.g. a `partially delivered` → `delivered` transition for ids that
were only blocked by the empty seed) is **`/product-spec`'s call, not `/architect`'s** — surfacing
it here because the architecture-side cause of that product note is exactly what this feature
changes.

## Observations

- The "ships unreachable" claim is repeated in SOURCE docstrings as well as in the architecture
  docs — `backend/app/services/tools.py`, `chapter_tools.py` and `close_tools.py` each state that
  their registry entries are unreachable until an admin assigns them to a mode. All three are now
  stale for a fresh install, and all three are outside this feature's Source areas so they were
  left untouched. Possible impact: fold into the same `/architect` pass that applies the
  `assistant-runtime.md` reversals above, as a source-docstring sweep.
- `ChatMessageResponse.tool_trace` is populated in `services/chats.py:_to_message_response`, which
  the plan's `## Source areas` does not list — the DTO field was specified but no owner was named
  for the one mapper that fills it, and both the `done` frame and `finishTurn`'s reload go through
  it. Possible impact: when a plan adds a field to an existing response DTO, its mapper's module
  belongs in Source areas by default.
- The three-layer JSON-in-TEXT trio is now `LlmServer.enabled_models`, `Chat.sampling_params` and
  `ChatMessage.tool_trace`, and only the last one is read through a gate that TOLERATES an
  unparseable stored value (mirroring `services/chats.py:_parse_sampling`, which does the same for
  `sampling_params` at the service layer rather than in the model). Possible impact: state the
  tolerance rule once in `backend/persistence.md` → "JSON-in-TEXT gated by a Pydantic model", so
  the next instance does not have to rediscover where it belongs.
