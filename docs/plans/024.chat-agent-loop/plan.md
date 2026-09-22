# 024.chat-agent-loop — plan

## Goal

Make the assistant's tool loop actually run in the codex (lore) edit modes — and the chapter and
close-chapter modes — by seeding real prompts and tool selections for all five modes, and make
what the assistant does while it runs visible in the chat pane: every tool call it makes, in
order, with a per-tool-kind rendering, live during the turn and preserved after it ends.

## Realizes

FEAT-013, FEAT-018, FEAT-020, UC-069, UC-070, UC-076, UC-077, UC-078, UC-087, UC-081, US-086,
US-087, US-088, US-101

## Source areas

- `backend/app/services/chat_turn.py` — the turn runtime; tool-call wrapping, trace assembly,
  persistence, debug-level context dump.
- `backend/app/models/schemas/chats.py` — new frame/trace Pydantic schemas, `ChatMessageResponse`
  field.
- `backend/app/models/**` — the `ChatMessage` SQLModel table; add the `tool_trace` column.
- `backend/app/db/assistant_modes.py` — default mode `system_prompt` text.
- `backend/app/db/mode_tools.py` — default `mode_tool` row seeding.
- `backend/app/services/setup.py` — wire the new seed call into both first-run paths.
- `backend/app/services/db_import_export.py` — extend the existing `chat_messages` codec pair for
  `tool_trace`.
- `frontend/src/types/chats.d.ts` — new frame/trace types.
- `frontend/src/api/chats.ts` — narrowing functions, `TurnStreamHandlers` fields.
- `frontend/src/work/components/chat/chatPaneState.ts` — live trace accumulation, rendered-message
  shape, row-expand toggling.
- `frontend/src/work/components/chat/ToolCallTrace.tsx` — new component (create).
- `frontend/src/work/components/chat/MessageList.tsx` — wire `ToolCallTrace` beside
  `ThinkingBlock`.
- `frontend/src/work/pages/CodexEntryPage.tsx` — header `Group`, Save/Discard as `ActionIcon`s.

## Test files

- `backend/tests/services/test_chat_turn_tool_trace.py` (new)
- `backend/tests/services/test_db_import_export_tool_trace.py` (new)
- `backend/tests/db/test_mode_tools_seed.py` (new)
- `frontend/tests/work/chatToolCallFrames.test.ts` (new)
- `frontend/tests/work/chatStreaming.test.ts` (extend — existing file, DoD-6 only)

## Interface

### `backend/app/models/schemas/chats.py`

```python
class ToolCallFrame(BaseModel):
    tool_name: str
    arguments: dict[str, Any]

class ToolResultFrame(BaseModel):
    tool_name: str
    result: str
    ok: bool

class ToolTraceEntry(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    result: str
    ok: bool

class ToolTrace(BaseModel):
    entries: list[ToolTraceEntry]

    @classmethod
    def parse_column(cls, raw: str | None) -> list[ToolTraceEntry] | None: ...
    def to_column(self) -> str: ...
```
`ToolCallFrame`/`ToolResultFrame` are the two new SSE frame payloads (events `tool_call`,
`tool_result`). `ToolTraceEntry` is one persisted/live trace row. `ToolTrace.parse_column` reads
the nullable `tool_trace` TEXT column into entries (`None` in → `None` out); `to_column`
serializes an instance to the column's JSON-in-TEXT form. This pair **is** DoD-3's Pydantic gate.

`ChatMessageResponse` (existing class) gains one field:
```python
tool_trace: list[ToolTraceEntry] | None = None
```

### `backend/app/models/**` (the `ChatMessage` SQLModel table)

```python
tool_trace: str | None = Field(default=None)
```
Nullable TEXT column, same shape as `Chat.sampling_params` (`backend/persistence.md`'s sanctioned
JSON-in-TEXT-behind-a-Pydantic-model pattern). Written via `ToolTrace(...).to_column()`, read via
`ToolTrace.parse_column(...)`.

### `backend/app/services/chat_turn.py`

```python
def _wrap_tool_with_trace(
    name: str,
    func: Callable[..., object],
    emit_frame: FrameEmitter,
    trace: list[ToolTraceEntry],
) -> Callable[..., Awaitable[str]]: ...
```
Returns an async wrapper closing over `name`/`func`/`emit_frame`/`trace`. On call: emits a
`tool_call` frame (`ToolCallFrame(tool_name=name, arguments=kwargs)`) before invoking
`func(**kwargs)` (awaiting it if awaitable); emits a `tool_result` frame after
(`ToolResultFrame(tool_name=name, result=<str>, ok=<bool>)`); appends one `ToolTraceEntry` to
`trace`. Catches any exception from `func` **or** from either `emit_frame` call and converts it
to an error-string result (`ok=False`) — never re-raises, never lets a failed frame emission abort
the tool call. Called once per entry of the turn's existing `tool_map`, immediately before the
existing `client.chat_with_tools(...)` call; `tools=` receives the wrapped dict, every other
argument to `chat_with_tools` is unchanged.

### `backend/app/db/assistant_modes.py`

```python
DEFAULT_MODE_SYSTEM_PROMPTS: dict[str, str]
```
Module constant, one non-blank entry per `DEFAULT_MODE_KEYS`. `seed_default_modes()` (existing,
signature unchanged) is extended to write `AssistantMode(key=key, system_prompt=<from this
dict>)` for a key with no existing row, in place of today's `system_prompt=None` — the
check-then-create idempotency is unchanged.

### `backend/app/db/mode_tools.py`

```python
DEFAULT_MODE_TOOL_NAMES: dict[str, tuple[str, ...]]

async def seed_default_mode_tools() -> None: ...
```
`DEFAULT_MODE_TOOL_NAMES` holds exactly the five entries in `context.md` → "Default per-mode tool
selections". `seed_default_mode_tools()`: for each of the five default mode keys, if that mode
currently holds **zero** `mode_tool` rows, insert its default set; a mode with **any** existing
row (previously seeded, or admin-edited down to a subset, or admin-added) is left untouched. This
is the idempotency unit — per-mode, not per-row, so a deliberately-removed single tool is never
re-added as long as the mode still has at least one row. Called from `services/setup.py` at both
existing `seed_default_modes()` call sites, immediately after that call.

### `frontend/src/types/chats.d.ts`

```ts
export interface ToolCallFrame {
  tool_name: string;
  arguments: Record<string, unknown>;
}

export interface ToolResultFrame {
  tool_name: string;
  result: string;
  ok: boolean;
}

export interface ToolTraceEntry {
  tool_name: string;
  arguments: Record<string, unknown>;
  result: string;
  ok: boolean;
}
```
`ChatMessageResponse` (existing interface) gains: `tool_trace: ToolTraceEntry[] | null;`

### `frontend/src/api/chats.ts`

```ts
function toolCallFrame(data: unknown): ToolCallFrame | null;
function toolResultFrame(data: unknown): ToolResultFrame | null;
```
Module-private, mirroring `canvasFrame`'s exact discipline: narrow field-by-field from `unknown`,
return `null` (drop the whole frame) on any type mismatch or missing required field — never
default a bad or absent field.

`TurnStreamHandlers` (existing interface) gains:
```ts
onToolCall?: (frame: ToolCallFrame) => void;
onToolResult?: (frame: ToolResultFrame) => void;
```
`streamChatTurn`'s exported signature is unchanged; its internal `onEvent` dispatch gains two
branches (`event === "tool_call"` / `"tool_result"`) using the two narrowing functions above,
same shape as the existing `"canvas"` branch.

### `frontend/src/work/components/chat/chatPaneState.ts`

```ts
export interface ToolTraceRow {
  toolName: string;
  arguments: Record<string, unknown>;
  result: string | null;
  ok: boolean | null;
}
```
`result`/`ok` are `null` exactly while a call is in flight (between its `tool_call` and
`tool_result` frames).

`RenderedMessage` (existing interface) gains: `toolTrace: ToolTraceRow[];`

New `ChatPaneState` observable fields:
```ts
streamingToolTrace: ToolTraceRow[]          // live accumulation during a streaming turn
expandedToolCallRows: Record<string, boolean>   // key: `${messageKey}:${rowIndex}`
```

```ts
export function toggleToolCallRow(state: ChatPaneState, rowKey: string): void;
```
Flips `state.expandedToolCallRows[rowKey]`, external effectful-operation shape per project
convention.

`turnStreamHandlers` (existing function, unchanged exported signature) gains internal
`onToolCall`/`onToolResult` cases: `onToolCall` pushes a new pending row
(`{ toolName: frame.tool_name, arguments: frame.arguments, result: null, ok: null }`) onto
`state.streamingToolTrace`; `onToolResult` fills the most recent row with `result === null`
(sequential dispatch guarantees at most one such row exists, per `context.md`). The
`RenderedMessage`-building getter maps a persisted message's `ChatMessageResponse.tool_trace`
(`null` → `[]`) into `toolTrace: ToolTraceRow[]` with `result`/`ok` always non-null.

### `frontend/src/work/components/chat/ToolCallTrace.tsx` (new file)

```tsx
export interface ToolCallTraceProps {
  rows: ToolTraceRow[];
  expanded: Record<string, boolean>;
  rowKeyPrefix: string;
  onToggle: (rowKey: string) => void;
}
export function ToolCallTrace(props: ToolCallTraceProps): JSX.Element | null;
```
Renders one row per entry in `rows`. Per-tool-name rendering: `web_search` shows its query
argument; `codex_search` shows its query plus a hit count derived from the result text;
`codex_read_entry` shows the entry it pulled; `write_codex_draft` shows which field (`name`/
`body`) it wrote; any other `tool_name` renders a generic name-plus-arguments row (never breaks on
an unrecognized name). A row with `result === null` shows a pending/loading affordance. Each row
is collapsible for its full arguments and result, driven by `expanded[`${rowKeyPrefix}:${index}`]`
/ `onToggle`, mirroring `ThinkingBlock`'s fully-controlled, no-internal-state shape.

### `frontend/src/work/pages/CodexEntryPage.tsx`

No new exported symbol. Contract: the bare `<Title order={3}>` gets a wrapping header `<Group>`;
Save and Discard move into it as `<ActionIcon aria-label="Save">` / `<ActionIcon
aria-label="Discard">`, removed from the footer `Group`. The `aria-label` strings must be exactly
`"Save"` / `"Discard"` (case-insensitive substring match) so `codexEntryPage.test.tsx`'s existing
`/save/i` / `/discard/i` queries keep resolving unchanged. `canSave` / `isReadOnly` gating and the
"Unsaved changes" text carry over unchanged — this is a relocation only.

## Implementation outline

1. Backend: `ToolCallFrame` / `ToolResultFrame` / `ToolTraceEntry` / `ToolTrace` in
   `models/schemas/chats.py`; `ChatMessage.tool_trace` column; `ChatMessageResponse.tool_trace`.
2. Backend: `_wrap_tool_with_trace` in `chat_turn.py`; wrap `tool_map` immediately before the
   existing `chat_with_tools` call; persist `tool_trace` on the assistant `ChatMessage` alongside
   `content`/`reasoning`; add the debug-level context/tool-result dump, gated on log level.
3. Backend: extend the existing `chat_messages` codec pair in `db_import_export.py` for
   `tool_trace` (no new `TABLE_REGISTRY` entry — the table is already registered).
4. Backend: `DEFAULT_MODE_SYSTEM_PROMPTS` + extend `seed_default_modes()`
   (`db/assistant_modes.py`); `DEFAULT_MODE_TOOL_NAMES` + `seed_default_mode_tools()`
   (`db/mode_tools.py`); wire the new seed call into both `services/setup.py` first-run paths.
5. Frontend: `ToolCallFrame`/`ToolResultFrame`/`ToolTraceEntry` types; `toolCallFrame`/
   `toolResultFrame` narrowing + `TurnStreamHandlers` fields + `onEvent` branches in `api/chats.ts`.
6. Frontend: `chatPaneState.ts` — `ToolTraceRow`, `streamingToolTrace`, `expandedToolCallRows`,
   `toggleToolCallRow`, `RenderedMessage.toolTrace`, `turnStreamHandlers` wiring.
7. Frontend: `ToolCallTrace.tsx` (new); wire into `MessageList.tsx` beside `ThinkingBlock`.
8. Frontend: `CodexEntryPage.tsx` header `Group` with Save/Discard `ActionIcon`s.

## Definition of done

1. `[test]` The tool wrapper emits a `tool_call` frame before and a `tool_result` frame after
   each call; a raising wrapped tool yields an error-string result (`ok=False`) rather than
   propagating out of the wrapper.
2. `[test]` Trace ordering is preserved across multiple tool calls in one turn, and the assembled
   trace is persisted onto the assistant `ChatMessage` (`tool_trace` column) — `null` when no tool
   ran during the turn.
3. `[test]` `ToolTrace.parse_column` / `.to_column()` round-trip correctly (the Pydantic gate),
   and the `chat_messages` JSONL export/import round-trip preserves `tool_trace` end to end.
4. `[test]` Seeding idempotency: a fresh database carries all five modes with the exact default
   tool sets in `context.md` and a non-blank `system_prompt` for each; re-running the seed leaves
   an admin-edited `system_prompt` and a deliberately-removed single `mode_tool` row (with the
   mode's other rows intact) both untouched.
5. `[test]` Frontend `toolCallFrame`/`toolResultFrame` narrowing: well-formed payloads parse;
   malformed payloads (wrong type, missing required field) are dropped (return `null`), never
   forwarded to a handler.
6. `[test]` The live-to-persisted handoff: after `finishTurn`'s reload, the message's rendered
   `toolTrace` still reflects the tool calls made during the turn (sourced from the reloaded
   `ChatMessageResponse.tool_trace`, not from the cleared `streamingToolTrace` buffer).
7. `[verify]` The relocated Save/Discard `ActionIcon`s keep `aria-label`s resolving to `/save/i`
   and `/discard/i` — checked by the existing `codexEntryPage.test.tsx` suite, no new test.
8. `[verify]` The debug-level context/tool-result dump in `chat_turn.py` is gated on log level
   (`logger.isEnabledFor(logging.DEBUG)` or equivalent) — not written at default log level.
9. `[verify]` `ToolCallTrace.tsx` renders a distinct affordance for each of `web_search`,
   `codex_search`, `codex_read_entry`, `write_codex_draft`, plus a generic fallback row for any
   other tool name.
10. `[verify]` `ToolCallFrame` and `ToolResultFrame` are declared in
    `frontend/src/types/chats.d.ts`.
11. `[verify]` `client.chat_with_tools(...)` in `chat_turn.py` is called with every argument
    unchanged except `tools=`, which receives the wrapped map.
12. `[verify]` Each of the five seeded `AssistantMode` rows carries a non-blank `system_prompt`
    on a fresh database.
13. `[manual/live]` Reasoning (`<think>`-tag) rendering against a real model server that inlines
    the tags — depends on server/model configuration (`--reasoning-format none` or equivalent);
    nothing in this repository can force it and it must not be claimed as delivered behaviour.
14. `[manual/live]` End-to-end: open a codex entry, discuss a change with the assistant, ask it to
    apply, watch the content pane update via the existing canvas path.
15. `[manual/live]` A close-chapter run exercising its five newly-live tools end to end against a
    real chapter in `closing` state.

## Test plan

**Tested:**
- DoD-1 — wrapper emits `tool_call`/`tool_result` in order and never propagates a tool exception —
  contract/invariant: this is the property the whole feature's safety rests on ("a tool never
  raises" must survive being wrapped).
- DoD-2 — trace ordering + persistence, null when empty — state/sequencing: multiple calls in one
  turn must not interleave or drop entries, and the persisted column must reflect exactly what
  streamed.
- DoD-3 — Pydantic gate round-trip + JSONL round-trip — contract: the JSON-in-TEXT column is only
  as safe as its gate; import/export is non-optional per root `CLAUDE.md` for any new persisted
  field.
- DoD-4 — seeding idempotency — invariant: the seed must converge on a fresh instance and must
  never re-impose configuration an admin deliberately changed; this is the property that makes
  D4's reversal acceptable at all.
- DoD-5 — frontend frame narrowing, malformed-drop — edge semantics: a malformed frame must be
  invisible, not partially rendered or defaulted, matching `canvasFrame`'s established discipline.
- DoD-6 — live-to-persisted handoff — seam: `finishTurn`'s reload is the exact point the reference
  diagnosis (D2) identified as where a live-only trace would vanish; this is the regression test
  for that seam.

**Not tested (deliberate):**
- Per-tool icon/label styling (DoD-9's visual rendering) — presentation; jsdom cannot judge visual
  styling, and the underlying "renders something for every tool name" property is `[verify]`.
- Save/Discard icon placement and appearance — same reason; the *behavioural* contract (accessible
  names) is covered by the existing `codexEntryPage.test.tsx` suite, not a new test.
- The debug-level context dump — logging, not test-worthy; covered by `[verify]` (gated on level).
- The new frame schema declarations (`ToolCallFrame`/`ToolResultFrame`/`ToolTraceEntry` shape
  itself) — declarative DTOs, no logic to fail.
- Mode `system_prompt` wording (the actual instruction text written for each mode) — content, not
  logic; only its non-blankness is `[verify]`.
- The thinking panel (`ThinkingBlock`) — already built and covered by `ChatConversation.test.tsx`;
  this feature does not touch it.

## Decisions taken

- **D1 — wrap the bound callables, not the loop.** `chat_with_tools` exposes no before/after tool
  hook (`llm` client, confirmed no `on_tool_call`/tracer callback surface); the app already
  supplies the callables it dispatches through, so a generic wrapper sees every call with zero
  library changes. Rejected: a manual `chat`-in-a-loop driver (~250 LoC re-implementing the wire
  protocol, pushes the feature out of the ultra band, and the seam stays available unspoiled by
  not taking it). Rejected: each tool emitting its own events (edits all 13 tool modules, silently
  omits any tool added later).
- **One wrapper, one call site.** The reference project (`llm-rp-server`) duplicates its wrapper
  at three call sites; BookWriter has exactly one (`chat_turn.py`), so it is written once — do not
  copy the reference's duplication.
- **D2 — trace persisted on `ChatMessage`, not live-only.** `finishTurn` discards the pane's local
  buffers and re-fetches from the server on `done`; a live-only trace would vanish the instant the
  turn completes. Precedent both directions: the reference persists an identical
  `tool_calls`/`thinking_content` pair; BookWriter already persists `reasoning`, `tool_trace` is
  its twin, using the `Chat.sampling_params` JSON-in-TEXT-behind-Pydantic pattern
  (`backend/persistence.md`). Rejected: live-only (cheapest, but self-erasing). Rejected: defer the
  column to a follow-up (ships the erasure as a known defect).
- **D3 — no change needed for reasoning.** `ThinkSplitter` already scans `<think>` tags out of
  `on_delta` text; the reference project gets thinking on its tools path the identical way, with
  the same `llm-client v0.1.4` pin. Accepted, real limitation: only works if the model inlines the
  tags — `[manual/live]`, not claimed as delivered. Rejected: patching the `llm` git dependency
  (~10 LoC, but edits a repo this feature can neither test nor verify, for a capability already
  obtained without it). Rejected: coupling to the rejected manual loop from D1.
- **D4 — seed all five modes' prompts and tool rows, by explicit author decision.** Reverses
  `assistant-runtime.md`'s three "ships unreachable" statements (recorded for `outcome.md`); the
  empty-allowlist rule itself is unchanged, only the seeded starting state. Idempotency
  (per-mode "zero rows" check) is the safety property that makes this acceptable — an admin's
  deliberate configuration, including a deliberate removal, is never re-imposed. Scope
  consequence, reaffirmed by the author: seeding `close-chapter`'s five tools makes feature 016's
  close procedure genuinely live for the first time (it writes real artifacts). Rejected: seed
  prompts only (leaves lore editing inert, the exact state being fixed). Rejected: seed the three
  codex modes only (the author chose the wider set once the consequence was put to them).
- **D5 — "context visibility" is the retrieval tool calls plus a debug log dump.** BookWriter has
  no assembled-context step to display (context assembly is deliberately undesigned,
  `domain-chat.md`); showing `codex_search`/`codex_read_entry` calls shows the real mechanism, not
  a narrowed version of the request. The debug dump satisfies the author's explicit ask
  ("logs on server side when debug enabled — dump the context") and is logging, `[verify]` only.
  Rejected: a frame carrying the assembled prompt to the client (~100 LoC, a sixth+seventh frame
  kind, to surface what the debug log already gives). Rejected: designing real context assembly
  (its own feature, its own design session).
- **D6 — typed rows with per-tool icons, not uniform rows.** The author named five distinct things
  to see; uniform rows would technically satisfy the request while defeating its point. Diverges
  from the reference deliberately (it groups by stage with no per-tool icons — right for a
  homogeneous generation pipeline, wrong for five heterogeneous capabilities). Unknown tool names
  degrade to a generic row, never break the trace.
- **D7 — Save/Discard become header icons.** The page has no header row today, so one is
  introduced around the `Title`. The load-bearing constraint is `codexEntryPage.test.tsx`'s
  existing `/save/i`/`/discard/i` accessible-name queries — the `aria-label`s must keep resolving;
  this is the existing suite's gate, not a new test. `canSave`/`isReadOnly`/"Unsaved changes"
  carry over unchanged — a relocation, not a behaviour change.
- **Default per-mode tool sets (this plan's own itemization of D4).** See `context.md` — codex
  modes and `write-chapter` get `web_search` back (its disappearance was an unintended regression,
  not a deliberate narrowing); `close-chapter` gets exactly the five tools
  `assistant-runtime.md` already names as its set, no more.

## Out of scope

- Context / content assembly (US-057, UC-085/086/078 internals) — deliberately deferred
  architecture, untouched.
- Token-level canvas streaming.
- Any modification, fork or replacement of `chat_with_tools` — the manual-loop seam stays
  available for a later feature.
- Streamed tool-argument frames — arguments arrive whole, same as the reference project.
- Auto-scroll in the transcript (still deferred from feature 023's F1).
- Any change to the `ChatPane` header popovers, the composer, or feature 023's delivered shape.
- Editing `docs/architecture/` or `docs/product/` — drift goes to `outcome.md` only.

## Risks

- **The `<think>`-tag dependency (D3).** Reasoning visibility depends entirely on the model
  server inlining `<think>` tags into raw content text; a server returning structured
  `reasoning_content` instead (the tools-path default per the `llm` client) will show no thinking
  at all, and no code change here can detect or fix that at build time.
- **The close-chapter tools going live (D4).** `draft_chapter_summary`, `draft_chapter_notes`,
  `raise_check_flag` and the post-turn `finalize_close_turn` hook now execute for real once
  `close-chapter` is seeded — a model going off-script during a close run writes real artifacts
  against a real chapter, where previously it was a no-op.
- **The import/export coupling (D2).** `tool_trace` must be added to the `chat_messages` codec in
  the same change (root `CLAUDE.md`'s non-optional rule); a missed codec update would silently
  drop trace data on the next export/import cycle without any error at write or read time.
- **The default per-mode tool-name sets are this plan's own choice**, not literally itemized in
  the design notes (D4 mandates seeding but not which tools per mode). If the itemization in
  `context.md` is wrong for the author's intent, only the two `DEFAULT_MODE_*` constants change —
  no schema or interface impact.
