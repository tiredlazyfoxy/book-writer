# Context — 024.chat-agent-loop

Feature-wide facts distilled from `docs/.cache/ultra/024.chat-agent-loop/harvest.md` (three
harvests) and `design-notes.md` (D1–D7). This file plus `plan.md` must be self-sufficient for a
build session with no conversation history — do not rely on anything said in chat.

## The diagnosis (why this feature exists)

Most of the machinery already exists and is switched off, not missing:

- `seed_default_modes()` (`backend/app/db/assistant_modes.py:72-83`) creates all five
  `AssistantMode` rows with `system_prompt = None`, idempotent by `key` (check-then-create).
- **No `mode_tool` row is seeded anywhere.** A mode with zero `mode_tool` rows is an **empty
  allowlist** (architectural rule, unchanged by this feature) — so today `edit-character` /
  `edit-location` / `edit-fact` / `write-chapter` / `close-chapter` all resolve to **zero
  tools**, and opening a codex entry or the open chapter actually *removes* `web_search` (which
  arrives only via `BASE_TOOL_NAMES` on no-mode turns).
- `write_codex_draft` → `canvas` frame → `CodexEntryPage.applyDraft` is already built, wired and
  tested end to end (`canvasWiring.test.tsx`, `contentSubject.test.ts`). It is unreachable solely
  because of the empty allowlist.
- `ThinkingBlock` is already a collapsible, fully-controlled, tested component. Reasoning capture
  (`ThinkSplitter` scanning literal `<think>` tags out of `on_delta` text) already runs on the
  `chat_with_tools` path — nothing to build there (D3). It only surfaces if the model **inlines**
  the tags; that is a model/server property no code here can force.

So this feature is: (1) a genuinely new tool-call trace (frames + persistence + UI), and
(2) enabling what already exists (seed real prompts and tool selections for all five modes).

## Standing constraints (do not relax)

- `chat_with_tools` is not modified, wrapped-at-the-library-level, or replaced. It is called from
  exactly one place, `backend/app/services/chat_turn.py`'s `drive()` closure
  (chat_turn.py:693-706), with `tools=tool_map` swapped for a wrapped dict — no other argument
  changes. The manual-loop seam (`assistant-runtime.md`'s "the seam") stays available and
  unspoiled for a later feature.
- **A tool never raises.** Every tool module states this. The new wrapper must preserve it:
  catch any exception from the wrapped call, or from frame emission, and turn it into an error
  string — never let it propagate into `chat_with_tools`'s dispatch loop (which would wrap it as
  `RuntimeError` and abort the whole turn).
- The empty-allowlist rule itself is untouched — only the seeded *starting state* changes.
- `docs/architecture/` and `docs/product/` are read-only in this feature. All doc drift goes to
  `outcome.md` for `/architect` to apply later.
- Frame narrowing on the client **drops malformed payloads** rather than defaulting them — the
  discipline `canvasFrame` (`frontend/src/api/chats.ts`) established. New narrowing functions
  must match this discipline exactly.
- `docs/plans/023.chat-ux-revision/` is delivered and `done`. Its `data-role` hooks, the
  `openedPanel` discriminator and composer gating all survive unchanged.
- Tool-call dispatch inside `chat_with_tools` is **sequential, not concurrent**
  (`llama_swap.py:263-285`, confirmed for that backend). At most one tool call is in flight at a
  time — a `tool_call` frame is always followed by exactly one `tool_result` frame for the same
  tool before the next `tool_call` frame, in the same turn.

## Backend runtime shape (grounded facts a build needs)

- `run_turn(context: TurnContext, prompt: str | None) -> AsyncGenerator[TurnFrame, None]`
  (`chat_turn.py:534`) is unchanged in signature. Inside its `drive()` closure: a
  `queue: asyncio.Queue[object]` is created (line 628) before tools are bound; `emit_frame`
  (line 630, type `FrameEmitter = Callable[[str, BaseModel], Awaitable[None]]`, declared in
  `services/tools.py:132`) is a closure over that queue and is handed into `ToolContext`
  (line 638). `tool_map: dict[str, Callable[..., object]]` and `tool_defs` are built before the
  `client.chat_with_tools(...)` call (lines 693-706).
- The assistant `ChatMessage` is persisted once, at natural completion, from `on_delta`
  accumulators (`content_parts` / `thinking_parts`), never from `chat_with_tools`'s return value
  (chat_turn.py:745-756):
  ```python
  reasoning = "".join(thinking_parts) or None
  assistant = await chat_messages.create(ChatMessage(chat_id=..., role="assistant",
      content=content, reasoning=reasoning, position=..., created_at=...))
  ```
  This feature adds a `tool_trace=` kwarg to that same call.
- `routes/chats.py`'s SSE serializer is **generic over `frame.event`** — a new frame kind needs
  zero route changes.
- The five-frame vocabulary as shipped: `thinking`, `delta`, `done`, `error`, `canvas`. This
  feature adds two more: `tool_call`, `tool_result`.
- `TOOL_REGISTRY` (`services/tools.py:261-430`) holds 13 tools; every one returns a plain `str`
  (never raises, contract stated in every tool module's docstring).
- `ChatMessage` fields today (`domain-chat.md`): `id`, `chat_id`, `role`, `content`,
  `reasoning: str | None`, `position`, `created_at`. This feature adds `tool_trace: str | None`,
  the same JSON-in-TEXT-behind-a-Pydantic-model shape `Chat.sampling_params` already uses
  (sanctioned in `backend/persistence.md`).
- The `ChatMessage` SQLModel table's exact source file was not in the harvest (only its field
  shape, via `domain-chat.md`). Locate it by following the import in
  `backend/app/db/chat_messages.py` — do not guess a filename.
- `db_import_export.py`'s `chat_messages` codec pair (`to_dict`/`from_dict`, naming convention
  `_chat_message_to_dict` / `_dict_to_chat_message` per `backend/persistence.md`'s documented
  convention) already handles `content` / `reasoning` / other columns. Extend it with
  `tool_trace` in the same change — do not add a new `TABLE_REGISTRY` entry, `chat_messages` is
  already registered.
- Entity ids serialize as strings in JSONL; `AssistantMode.key` and its link tables' `mode_key`
  are natural keys and pass through **verbatim**, never through `int(...)` — irrelevant to this
  feature's own new column (`tool_trace` is a plain string column) but relevant if touching
  `mode_tool` codecs (unaffected — no schema change to that table, only its seeded row content).

## Default per-mode tool selections (authoritative — the test-coder binds to these)

Chosen by this plan (design notes D4 mandates seeding all five modes but does not itemize sets;
this is the itemization). Every set includes only tools already in `TOOL_REGISTRY`
(`services/tools.py`), matching the registry table in the harvest:

```
edit-character / edit-location / edit-fact:
    ("web_search", "codex_search", "codex_read_entry", "write_codex_draft")

write-chapter:
    ("web_search", "codex_search", "codex_read_entry",
     "read_chapter_text", "set_chapter_text", "update_selection", "add_text")

close-chapter:
    ("draft_chapter_summary", "draft_chapter_notes", "propose_active_notes",
     "raise_check_flag", "read_continuity_context")
```

Reasoning: the three codex modes and `write-chapter` get `web_search` back — its disappearance
on a mode-bearing turn was named in the diagnosis as an unintended regression from the
zero-rows-means-nothing rule, not a deliberate narrowing. `close-chapter` gets exactly the five
tools `assistant-runtime.md` names as "close-chapter's five tools" (`services/close_tools.py`) —
no more, staying literal to that document's own enumeration and to design notes D4's explicit
"close-chapter's five tools" framing.

## Frontend shape (grounded facts a build needs)

- SSE transport: `frontend/src/api/sse.ts`'s `streamPost` forwards any event name that is not
  `done`/`error` to `onEvent(event, data)` — new event names (`tool_call`, `tool_result`) reach
  `api/chats.ts`'s dispatcher with zero transport changes.
- `api/chats.ts`'s `canvasFrame` narrowing (verbatim in harvest) is the pattern to mirror:
  narrow field-by-field from `unknown`, return `null` (drop) on any mismatch — never default a
  bad field.
- `chatPaneState.ts`'s `RenderedMessage` (today: `key`, `role`, `content`, `reasoning`,
  `streaming`) is assembled by a getter (`chatPaneState.ts:470-490`) from persisted messages plus
  the flat streaming fields (`streamingContent`, `streamingThinking`, etc.) while
  `turnStatus === "streaming"`. This feature widens `RenderedMessage` with `toolTrace` and adds a
  `streamingToolTrace` flat field beside the existing streaming buffers, same pattern.
- `finishTurn` (called from `onDone`) reloads messages via `chatsApi.getChat` and clears the
  streaming buffers — this is why the trace must be **persisted**: the reload replaces the
  in-flight message with the persisted `ChatMessageResponse`, and if `tool_trace` did not survive
  the round trip to the server and back, the reload would silently erase visibility exactly when
  the turn finishes. As long as the persisted `ChatMessageResponse.tool_trace` is mapped into
  `RenderedMessage.toolTrace` by the same getter that already builds `RenderedMessage` from
  persisted messages, no explicit "carry-over" step is needed — the getter already re-derives
  from the reloaded array. Only `streamingToolTrace` needs clearing (already covered by the
  existing streaming-buffer-clear in `finishTurn`).
- `MessageList.tsx` renders `ThinkingBlock` before the markdown body for each message when
  `hasReasoning`; it is otherwise a plain `Stack`/`ScrollArea`, `data-role="assistant"` /
  `data-role="user"`. `ToolCallTrace` goes in the same per-message slot, beside `ThinkingBlock`.
- `ThinkingBlock` (`frontend/src/work/components/chat/ThinkingBlock.tsx`) is the precedent for a
  fully-controlled presentational component: props only, no internal state, toggle owned by the
  page-level state class (`chatPaneState.ts`'s `expandedReasoning: Record<string, boolean>` /
  `liveThinkingExpanded`). `ToolCallTrace` follows the same discipline.
- `CodexEntryPage.tsx` has **no header row today** — first child of its `Stack` is a bare
  `<Title order={3}>`. Save/Discard are plain `<Button>`s in a footer `<Group>` under the
  `Textarea`, alongside a conditional "Unsaved changes" `<Text>`. `codexEntryPage.test.tsx`
  queries these controls by accessible name (`/save/i`, `/discard/i`) — moving them to
  `ActionIcon`s in a new header `Group` must keep those exact `aria-label`s so the existing suite
  (not a new test) keeps passing.
- `contentSubject.ts` / `restoreBuffer.ts` / the canvas dispatch path are **untouched** by this
  feature — nothing here changes how a `canvas` frame is applied.

## Reference project pattern used (harvest 3)

`llm-rp-server`'s `_make_tool_wrapper(name, fn, queue, tool_call_records, stage_name)` — a
`functools.wraps` async closure emitting `tool_call_start` before, `tool_call_result` after,
returning an error string (never raising) on exception, and appending a record for later
persistence. BookWriter's version is the same shape, written **once** (BookWriter has exactly one
`chat_with_tools` call site; the reference has three and duplicates the wrapper at each — do not
copy that duplication).

## Product ids relevant to this feature (verified against `docs/product/quick-reference.md`)

FEAT-013, FEAT-018, FEAT-020, UC-069, UC-070, UC-076, UC-077, UC-078, UC-087, US-086, US-087,
US-088, US-101, UC-081. (Story-level `US-###.AC-#` sub-ids were not available in this harvest
pass — DoD items cite the bare id only, never a guessed `AC-#`.)
