# Feature 024 — chat-agent-loop

| Status  | Verifier | Date |
|---------|----------|------|
| done    | PASS     | 2026-08-09 |

## Files Changed

**Backend**

- `backend/app/models/schemas/chats.py` — filled `ToolTrace.parse_column` / `.to_column()`, the
  `tool_trace` column's only reader and writer
- `backend/app/services/chat_turn.py` — filled `_wrap_tool_with_trace`; wrapped `tool_map` into
  `traced_tool_map` (the only changed `chat_with_tools` argument); persisted the assembled trace as
  `tool_trace=` on the assistant `ChatMessage`; added the debug-gated context dump. Added two
  private helpers the plan did not name: `_emit_trace_frame` (swallows a frame-delivery failure)
  and `_TOOL_FAILED_MESSAGE` / `_DEBUG_RESULT_CHARS` constants
- `backend/app/db/assistant_modes.py` — wrote the five `DEFAULT_MODE_SYSTEM_PROMPTS`;
  `seed_default_modes()` now creates a missing key with its prompt instead of `None`
- `backend/app/db/mode_tools.py` — wrote the five `DEFAULT_MODE_TOOL_NAMES` sets verbatim from
  `context.md`; filled `seed_default_mode_tools()` (per-mode "zero rows" idempotency)
- `backend/app/services/setup.py` — `seed_default_mode_tools()` wired in at both
  `seed_default_modes()` call sites (`create_database`, `import_database`)
- `backend/app/services/db_import_export.py` — extended the existing `chat_messages` codec pair for
  `tool_trace` (column string verbatim both ways; a pre-024 archive imports as `None`)
- `backend/app/services/chats.py` — **OUT OF THE PLAN'S SOURCE AREAS**, one field:
  `_to_message_response` now fills `ChatMessageResponse.tool_trace` via `ToolTrace.parse_column`.
  See `## Notes & Issues`

**Frontend**

- `frontend/src/api/chats.ts` — filled `toolCallFrame` / `toolResultFrame` (drop-on-mismatch,
  `canvasFrame`'s discipline)
- `frontend/src/work/components/chat/chatPaneState.ts` — filled `toggleToolCallRow`; added the
  `onToolCall` / `onToolResult` cases to `turnStreamHandlers`; replaced both `renderedMessages`
  placeholders (persisted branch maps `tool_trace` via a new private `toolTraceRows` helper, live
  branch reads `streamingToolTrace`); `streamingToolTrace` cleared alongside the other streaming
  buffers at all six existing reset sites
- `frontend/src/work/components/chat/ToolCallTrace.tsx` — NEW; per-tool rows for `web_search`,
  `codex_search` (with a hit count derived from the result), `codex_read_entry`,
  `write_codex_draft`, plus a generic name-plus-arguments fallback; pending affordance while
  `result === null`; per-row collapse driven entirely by the parent
- `frontend/src/work/components/chat/MessageList.tsx` — `ToolCallTrace` wired into the per-message
  slot beside `ThinkingBlock`
- `frontend/src/work/pages/CodexEntryPage.tsx` — reshaped: new header `Group` around the `Title`
  holding Save / Discard as `ActionIcon`s (`aria-label` `"Save"` / `"Discard"`) and the
  "Unsaved changes" text; the footer `Group` is gone. Relocation only — same `canSave` /
  `isReadOnly` gating, same handlers

## Feedback

### Round 1 (2026-08-09)

- F1 bug — `backend/app/db/engine.py` — filled the previously empty **ADDITIVE MIGRATION SEAM** so
  `ChatMessage.tool_trace` reaches a database created before 024 (`create_all` only ever creates
  missing *tables*, so on an existing install every `chat_messages` INSERT — including a plain user
  message — died with `table chat_messages has no column named tool_trace`). Added a module-level
  `ADDITIVE_COLUMNS: tuple[tuple[str, str], ...]` declaration table (one entry:
  `("chat_messages", "tool_trace")`) and a private `_apply_additive_columns(sync_conn)` run under
  `run_sync` inside the seam's existing `_engine.begin()` block. The SQL type is **compiled from
  `SQLModel.metadata`** (`column.type.compile(dialect=sqlite.dialect())`, the same device
  `db/schema.py:add_columns` uses) rather than written out, so the DDL cannot drift from the model,
  and the column is emitted NULLABLE with no default — all SQLite allows on `ADD COLUMN`.
  **Idempotency is by introspection, not by error text**: live column names are reflected with
  `inspect(sync_conn)` first and a present column emits no DDL at all, with a
  `try/except OperationalError` backstop for a lost race; an entry whose table is absent, or whose
  column is no longer in metadata, is skipped (warned) instead of raising. Raw DDL rather than
  reusing `db/schema.py`'s `introspect`/`add_columns` because `schema.py` imports `engine.py` —
  calling into it from here would invert the `db/` layering and need a deferred import to dodge the
  cycle; the reason is recorded in the seam comment. `async def init_db() -> None` is unchanged, as
  are both callers (`services/setup.py`, `services/db_import_export.py`), and a fresh database is
  untouched (the seam emits nothing there — `create_all` already made the column). The seam's
  comment now names `ADDITIVE_COLUMNS` as the one-line extension point instead of saying "no
  columns to add yet".

## Skeleton

### Frozen interface (2026-08-09)

**Backend**

- `backend/app/models/schemas/chats.py` — `class ToolCallFrame(BaseModel)`: `tool_name: str`, `arguments: dict[str, Any]` — new
- `backend/app/models/schemas/chats.py` — `class ToolResultFrame(BaseModel)`: `tool_name: str`, `result: str`, `ok: bool` — new
- `backend/app/models/schemas/chats.py` — `class ToolTraceEntry(BaseModel)`: `tool_name: str`, `arguments: dict[str, Any]`, `result: str`, `ok: bool` — new
- `backend/app/models/schemas/chats.py` — `class ToolTrace(BaseModel)`: `entries: list[ToolTraceEntry]`; `@classmethod parse_column(cls, raw: str | None) -> list[ToolTraceEntry] | None` (raises `NotImplementedError`); `to_column(self) -> str` (raises `NotImplementedError`) — new
- `backend/app/models/schemas/chats.py` — `ChatMessageResponse.tool_trace: list[ToolTraceEntry] | None = None` — changed (field added; every existing construction site still binds because it defaults)
- `backend/app/models/chat.py` — `ChatMessage.tool_trace: str | None = Field(default=None)` — changed (the `ChatMessage` SQLModel table lives here, located via the import in `backend/app/db/chat_messages.py`)
- `backend/app/services/chat_turn.py` — `_wrap_tool_with_trace(name: str, func: Callable[..., object], emit_frame: FrameEmitter, trace: list[ToolTraceEntry]) -> Callable[..., Awaitable[str]]` — new (raises `NotImplementedError`). `Callable`/`Awaitable` are `collections.abc`; `FrameEmitter` is imported from `app.services.tools`. NOT called from anywhere yet — wrapping `tool_map` before `client.chat_with_tools(...)` is the coder's.
- `backend/app/db/assistant_modes.py` — `DEFAULT_MODE_SYSTEM_PROMPTS: dict[str, str]` — new. Placeholder value `{key: "" for key in DEFAULT_MODE_KEYS}`: the five keys and the type are frozen, the prompt TEXT is the coder's (DoD-12 requires each non-blank). `seed_default_modes()` signature AND body unchanged.
- `backend/app/db/mode_tools.py` — `DEFAULT_MODE_TOOL_NAMES: dict[str, tuple[str, ...]]` — new. Placeholder value `{}`; the coder fills the five entries verbatim from `context.md` → "Default per-mode tool selections".
- `backend/app/db/mode_tools.py` — `async def seed_default_mode_tools() -> None` — new (raises `NotImplementedError`). NOT yet called from `services/setup.py` — both call sites are the coder's.

**Frontend**

- `frontend/src/types/chats.d.ts` — `export interface ToolTraceEntry { tool_name: string; arguments: Record<string, unknown>; result: string; ok: boolean; }` — new
- `frontend/src/types/chats.d.ts` — `export interface ToolCallFrame { tool_name: string; arguments: Record<string, unknown>; }` — new
- `frontend/src/types/chats.d.ts` — `export interface ToolResultFrame { tool_name: string; result: string; ok: boolean; }` — new
- `frontend/src/types/chats.d.ts` — `ChatMessageResponse.tool_trace: ToolTraceEntry[] | null;` — changed (**required**, nullable-never-omitted, per plan)
- `frontend/src/api/chats.ts` — `function toolCallFrame(data: unknown): ToolCallFrame | null` — new, module-private, body throws
- `frontend/src/api/chats.ts` — `function toolResultFrame(data: unknown): ToolResultFrame | null` — new, module-private, body throws
- `frontend/src/api/chats.ts` — `TurnStreamHandlers` gains `onToolCall?: (frame: ToolCallFrame) => void;` and `onToolResult?: (frame: ToolResultFrame) => void;` — changed
- `frontend/src/api/chats.ts` — `streamChatTurn(bookId, chatId, prompt, handlers, subject?, selectionText?): Promise<AbortController>` — **UNCHANGED**
- `frontend/src/work/components/chat/chatPaneState.ts` — `export interface ToolTraceRow { toolName: string; arguments: Record<string, unknown>; result: string | null; ok: boolean | null; }` — new
- `frontend/src/work/components/chat/chatPaneState.ts` — `RenderedMessage.toolTrace: ToolTraceRow[];` — changed
- `frontend/src/work/components/chat/chatPaneState.ts` — `ChatPaneState.streamingToolTrace: ToolTraceRow[] = []` — new observable
- `frontend/src/work/components/chat/chatPaneState.ts` — `ChatPaneState.expandedToolCallRows: Record<string, boolean> = {}` — new observable (key `` `${messageKey}:${rowIndex}` ``)
- `frontend/src/work/components/chat/chatPaneState.ts` — `export function toggleToolCallRow(state: ChatPaneState, rowKey: string): void` — new, body throws
- `frontend/src/work/components/chat/ToolCallTrace.tsx` (NEW FILE) — `export interface ToolCallTraceProps { rows: ToolTraceRow[]; expanded: Record<string, boolean>; rowKeyPrefix: string; onToggle: (rowKey: string) => void; }` — new
- `frontend/src/work/components/chat/ToolCallTrace.tsx` — `export const ToolCallTrace = observer(function ToolCallTrace(props: ToolCallTraceProps): React.JSX.Element | null { … })` — new, body throws

### Divergences from the plan's declared `## Interface`

- **`ToolCallTrace` is `observer(function …)`, not a bare `export function`.** The plan writes `export function ToolCallTrace(props: ToolCallTraceProps): JSX.Element | null;`. Root `CLAUDE.md` mandates `observer` on **every** component, and the sibling precedent (`ThinkingBlock.tsx`) is `export const X = observer(function X(props) {…})`. The exported symbol name, the props type and the `… | null` return are all preserved, so every import and call site is identical. `JSX.Element` was written as `React.JSX.Element` — there is no global `JSX` namespace under React 19's types and no `JSX.Element` reference anywhere else in this repo.
- **`api/chats.ts`'s two `onEvent` dispatch branches were wired now, not left to the coder.** `frontend/tsconfig.json` sets `noUnusedLocals: true`, so the two module-private narrowing functions do not compile unless something references them. The branches are a verbatim copy of the existing `"canvas"` branch shape (`const frame = toolXFrame(data); if (frame !== null) handlers.onToolX?.(frame);`); the narrowing functions themselves — DoD-5's actual logic — are unimplemented and throw.

### Placeholders the coder MUST replace (they compile, they are not behaviour)

- `renderedMessages` sets `toolTrace: []` on **both** the persisted-message branch and the in-flight bubble. The persisted branch is DoD-6's seam (map `ChatMessageResponse.tool_trace`, `null` → `[]`); the streaming branch feeds from `streamingToolTrace`.
- `DEFAULT_MODE_SYSTEM_PROMPTS` values are `""`; `DEFAULT_MODE_TOOL_NAMES` is `{}`.

### Caller-compile edits (out of Source-files scope)

None. The only mechanical adaptations were inside plan Source areas: the two optimistic `ChatMessageResponse` literals in `chatPaneState.ts` (`sendChatTurn` ~line 951 and `startCloseTurn` ~line 1302) each gained `tool_trace: null`, and `renderedMessages`' two object literals each gained the `toolTrace: []` placebo above.

### Compile gate

- `cd frontend && npx tsc --noEmit` — clean.
- `cd frontend && npm run build` — clean (`tsc && vite build`).
- Backend has no static type-check (root `CLAUDE.md`); gate run as an import check of `app.main` plus every touched module and every new symbol — clean. No tests were run.

## Tests

### Tests (2026-08-09)

- `backend/tests/services/test_chat_turn_tool_trace.py` — covers DoD-1, DoD-2 — the wrapper
  brackets each call with `tool_call`/`tool_result` frames (sync + async tools), a raising tool
  becomes an error string with `ok=False` and a failed frame emission never propagates; and, end
  to end over the real turn (the `test_chat_turn_canvas.py` `http_client` harness, fake
  `LLMClient` invoking the wrapped tool map), two calls in one turn keep their order on the wire
  and in the persisted `tool_trace` column, which is `NULL` when no tool ran.
- `backend/tests/services/test_db_import_export_tool_trace.py` — covers DoD-3 — `to_column()` /
  `parse_column()` round-trip (mixed-type arguments, `ok=False`, `None` in → `None` out, empty
  trace → `[]` not `None`), plus a real `chat_messages` JSONL export → pristine DB → import
  round-trip preserving `tool_trace` (and a null trace staying null).
- `backend/tests/db/test_mode_tools_seed.py` — covers DoD-4 — a fresh DB carries the five modes
  with exactly `context.md`'s default tool sets and a non-blank `system_prompt` each; a re-seed
  adds no duplicate rows (parameterized over the five modes) and re-imposes neither an
  admin-edited `system_prompt` nor a deliberately-removed single `mode_tool` row, with that
  mode's other rows and every other mode intact.
- `frontend/tests/work/chatToolCallFrames.test.ts` — covers DoD-5 — well-formed `tool_call` /
  `tool_result` payloads (including the falsy-but-valid `ok: false` and `result: ""`) reach
  `onToolCall` / `onToolResult` intact through the real `streamChatTurn` + `sse.ts` generic
  `onEvent` routing; nine malformed `tool_call` and nine malformed `tool_result` payloads
  (non-object, missing required field, wrong type, null field) are dropped whole and never
  forwarded to any handler.
- `frontend/tests/work/chatStreaming.test.ts` — EXTENDED — covers DoD-6 — after `finishTurn`'s
  reload the rendered `toolTrace` reflects the turn's tool calls sourced from the reloaded
  `ChatMessageResponse.tool_trace` (persisted values deliberately differ from the live ones, so
  the live buffer cannot satisfy it), the `streamingToolTrace` buffer is cleared, and a `null`
  persisted trace renders as an empty trace. Its `makeMessage(...)` fixture gained a defaulted
  `tool_trace` — compile re-bind only, no pre-existing assertion changed.
- `frontend/tests/work/ChatConversation.test.tsx` — COMPILE RE-BIND ONLY (authorized by the
  orchestrator, outside the plan's Test files): `tool_trace: null` added to its `message(...)`
  fixture factory because `ChatMessageResponse.tool_trace` is now required-nullable. No
  assertion in that file was touched.
- `backend/tests/test_data_domain_chat.py` — PIN RE-BIND ONLY (authorized by the orchestrator,
  outside the plan's Test files): `tool_trace` added to `CHAT_MESSAGE_FIELDS`, the hardcoded
  `ChatMessage` field-set pin read by `test_chat_and_message_field_sets_pinned__DoD10`, which was
  stale against `plan.md` → `## Interface`'s `ChatMessage.tool_trace: str | None`. No assertion in
  that file was changed and no test added.

- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓,
  DoD-7 [verify, no test], DoD-8 [verify, no test], DoD-9 [verify, no test],
  DoD-10 [verify, no test], DoD-11 [verify, no test], DoD-12 [verify, no test],
  DoD-13/14/15 [manual/live, no test]
### Delivered-suite re-bindings forced by D4 / D11 (2026-08-09)

Seven already-delivered tests asserted the pre-024 world that `plan.md` → `## Decisions taken` →
D4 deliberately reverses (seeded prompts + seeded per-mode tool rows) and that DoD-11 makes
impossible (a wrapped tool map). Amended on the user's ruling via the orchestrator; in every case
only the clause D4/D11 invalidates moved, and no test was deleted, renamed away from its tag, or
weakened elsewhere.

- `backend/tests/test_data_domain_mode_seed.py::test_seed_creates_exactly_the_fixed_five__DoD1` —
  seeded row's `system_prompt is None` → non-blank. Preserved: exactly five rows, exact key set.
- `backend/tests/services/test_assistant_config_modes.py::test_list_modes_returns_fixed_five_in_order__DoD1_UC095_US110_AC1`
  — the never-configured mode's null prompt → non-blank. Preserved: order, count, the configured
  and prompt-only modes' expectations, empty selections, the "listed, not dropped" property.
- `backend/tests/services/test_db_admin_seed.py::test_seed_table_rows_preserves_an_edited_prompt__F1`
  — seed-created rows' `system_prompt is None` → non-blank AND ≠ the admin's text. Preserved (F1
  point 7's actual property): the admin edit survives verbatim, key set, no-duplicate count.
- `backend/tests/services/test_db_admin_import_seed.py::test_admin_import_preserves_archived_mode_rows__F2`
  — seed-created rows' null prompt → non-blank AND not an archived row's text. Preserved: archived
  prompts verbatim, exactly five, no duplicates.
- `backend/tests/services/test_setup_mode_seed.py::test_import_database_seed_is_non_destructive__DoD9`
  — same one clause, same replacement. Preserved: non-destructiveness, no duplicate row, exactly
  five after the bootstrap import.
- `backend/tests/services/test_chapter_tools.py` — `test_open_chapter_turn_is_offered_none_of_the_four__DoD12`
  → `test_open_chapter_turn_is_offered_the_seeded_four__DoD12` (tag intact; the name described the
  reversed premise). Now asserts `write-chapter`'s seeded set is exactly `context.md`'s seven and
  that all four chapter tools are offered and resolve. Preserved, explicitly re-asserted on a
  cleared mode: the empty-allowlist rule (`zero rows → ()`, resolves to nothing) and
  "registration alone grants nothing", which `context.md` → Standing constraints keeps untouched.
- `backend/tests/services/test_codex_tools.py::test_web_search_still_offered_on_a_no_mode_turn__DoD13`
  — dropped only `tools["web_search"] is web_search` (DoD-11 mandates a wrapped map). Preserved and
  extended: the map's key set is still exactly `BASE_TOOL_NAMES`, `web_search` is present by name
  with a dispatchable callable and a matching tool definition. The sibling
  `test_web_search_binds_unchanged_with_a_context__DoD13` (identity at `build_tool_bindings`
  level, where no wrapper sits) is untouched.

- Deliberately not tested (per plan `## Test plan`): 6 items — per-tool icon/label styling,
  Save/Discard placement and appearance, the debug-level context dump, the new frame schema
  declarations, mode `system_prompt` wording, `ThinkingBlock`.

### Feedback round 1 — repro tests (2026-08-09)

- `backend/tests/db/test_engine_additive_migration.py` — reproduces: F1 — `init_db()` never carries
  `ChatMessage.tool_trace` onto a database created before 024, so every `chat_messages` insert
  (including a plain user message) fails with `table chat_messages has no column named tool_trace`
  — defends DoD-2. Four tests, all tagged `__F1`, bound to the harvested `init_engine(config)` /
  `init_db()` signatures: (1) after `init_db()` on a pre-024 database the table carries a nullable
  `tool_trace` column and a normal-path insert succeeds and round-trips the column; (2) idempotency
  — a second and third `init_db()` raise nothing, leave the column present exactly once and already
  written rows intact; (3) first-run on a genuinely fresh database still yields `chat_messages` with
  a nullable `tool_trace` and a working insert; (4) parameterized end-to-end symptom check after one
  or two `init_db()` runs. The pre-024 database is built with stdlib `sqlite3`
  (`ALTER TABLE chat_messages DROP COLUMN tool_trace`) — no implementation internal touched.
- No existing test modified.

## Notes & Issues

### Skeleton (2026-08-09) — two existing test files stop typechecking under `npm run test:types`

Making `ChatMessageResponse.tool_trace` **required** (`ToolTraceEntry[] | null`, exactly as `plan.md` → `## Interface` specifies) breaks the two existing frontend fixtures that build a `ChatMessageResponse` by hand:

- `frontend/tests/work/chatStreaming.test.ts:117` — **in** the plan's Test files (listed as "extend"), so the test-coder owns it.
- `frontend/tests/work/ChatConversation.test.tsx:90` — **NOT** in the plan's Test files. It needs a one-line fixture fix (`tool_trace: null` in its `message(...)` factory) for `npm run test:types` to pass.

The skeleton did not touch either (Test files are outside its access map). This does **not** affect `npm run build`, which deliberately excludes `tests/` (`tsconfig.json` → `include: ["src"]`). The orchestrator should either widen the test-coder's Test-files scope to include `ChatConversation.test.tsx` or accept a failing `npm run test:types` until it is fixed.

### Coder (2026-08-09) — the wrapper's frame-emission ambiguity, and the reading chosen

`plan.md` → `## Interface` says `_wrap_tool_with_trace` "**Catches any exception from `func` or from either `emit_frame` call and converts it to an error-string result (`ok=False`)** — never re-raises, never lets a failed frame emission abort the tool call." Read distributively, the two halves contradict each other: converting a *`tool_call`-frame* emission failure into an error-string result is precisely aborting the tool call.

**Reading chosen** — the dominant, non-negotiable invariant (`context.md` → "A tool never raises") is that the wrapper never raises and always returns a `str`. Under that:

- an exception from `func` → error-string result, `ok=False` (the tested clause, DoD-1);
- an exception from **either** `emit_frame` call → caught in the private `_emit_trace_frame`, logged, **swallowed**; the tool still runs and its **real** result is what the model, the trace and the caller receive. A lost visibility frame must not rewrite what the assistant was told a tool returned;
- an outermost guard around the whole wrapper body returns an error string for anything else, so nothing escapes into `chat_with_tools`'s dispatch loop.

This satisfies "never re-raises" and "never lets a failed frame emission abort the tool call" literally, and "converts it to an error-string result (`ok=False`)" for the case `ok` is actually defined over (`ToolResultFrame.ok` is documented as "whether the call completed without raising"). Precedent: `services/codex_tools.py` guards its own `canvas` emission the same way.

### Coder (2026-08-09) — one edit outside the plan's `## Source areas`

`services/chats.py:_to_message_response` gained one keyword: `tool_trace=ToolTrace.parse_column(message.tool_trace)`.

`plan.md` adds `tool_trace` to `ChatMessageResponse` but its `## Source areas` names no owner for the single mapper that fills that DTO, and that mapper serves **both** the `done` frame and `finishTurn`'s reload. Without it the column is written and never read: the persisted trace would never reach the client and DoD-6's seam would be dead end to end on the real path. The change is one line, is directly traceable to the plan's own `## Interface`, adds no behaviour beyond it, and touches nothing else in that file. Flagged rather than escape-valved because blocking the whole feature over it would have been disproportionate — the orchestrator should confirm or revert it.

### Coder (2026-08-09) — noted, deliberately NOT fixed

- `services/tools.py`, `chapter_tools.py` and `close_tools.py` each carry docstrings stating their
  tools "ship unreachable" until an admin assigns them. All three are stale after D4's seeding and
  all three are outside the Source areas. Recorded in `outcome.md` → `## Observations`.
- `work/subject.ts:checkWritePermission` still appears to have no call site (flagged in harvest 2).
  Untouched — not this feature's.
