# Fast feature 010 — transcript-autoscroll

| Status  | Verifier | Date |
|---------|----------|------|
| done    | PASS     | 2026-09-14 |

## Files Changed

- `frontend/src/work/components/chat/transcriptScroll.ts` — the pure scroll geometry: the 64px threshold, the inclusive pinned predicate (non-finite input → pinned), the bottom-position helper (floored at 0, non-finite → 0)
- `frontend/src/work/components/chat/chatPaneState.ts` — the `transcriptGrowthSignature` string computed, the six external scroll operations (attach / note / scroll-to-bottom / deferred-and-coalesced follow / re-pin / release), plus the three re-pin call sites in `loadChatMessages` (success path), `sendChatTurn` and `retryChatTurn` (both on acceptance)
- `frontend/src/work/components/chat/MessageList.tsx` — docblock correction only: the auto-scroll side-effect IS shipped, in `WorkspaceShell`'s existing mount autorun; the leaf still holds no effect
- `frontend/src/work/components/shell/WorkspaceShell.tsx` — no coder change needed beyond the skeleton's wiring (second autorun inside the existing mount effect, disposer + release in the existing cleanup)

## Skeleton

### Frozen interface (2026-09-14)

**`frontend/src/work/components/chat/transcriptScroll.ts`** (NEW — pure module: no class, no MobX, no DOM, no import from the state)

- `frontend/src/work/components/chat/transcriptScroll.ts` — `export const TRANSCRIPT_PIN_THRESHOLD_PX = 64` — new (**real value, not a stub** — the literal IS the contract)
- `frontend/src/work/components/chat/transcriptScroll.ts` — `export function isTranscriptPinned(scrollTop: number, scrollHeight: number, clientHeight: number): boolean` — new (throws). **Argument order is `scrollTop, scrollHeight, clientHeight`.**
- `frontend/src/work/components/chat/transcriptScroll.ts` — `export function transcriptBottomScrollTop(scrollHeight: number, clientHeight: number): number` — new (throws). **Argument order is `scrollHeight, clientHeight`** (`(2000, 500)` → `1500`).

**`frontend/src/work/components/chat/chatPaneState.ts` — the class**

- `new ChatPaneState()` — **UNCHANGED, recorded because the test-coder must construct one and may not read source: the constructor takes NO ARGUMENTS.** It hydrates the composer height from `localStorage` + `window.innerHeight` inside the constructor, so any storage seeding must happen *before* construction; it is otherwise side-effect-free and makes no network call.
- `ChatPaneState.transcriptViewport: HTMLDivElement | null` — new **non-observable** slot, initial `null`. **The element type is `HTMLDivElement`** (the `ScrollArea`'s internal viewport div, not its root wrapper); a test stub may be a plain `document.createElement("div")`.
- `ChatPaneState.transcriptPinned: boolean` — new **non-observable** slot, **initial `true`** (a fresh pane follows from its first render with no scroll event — DoD-6).
- `ChatPaneState.transcriptFollowFrame: number | null` — new **non-observable** slot, initial `null` (the pending `requestAnimationFrame` id, used to coalesce).
- All three joined the existing `makeAutoObservable` exclusion map beside `composerResizeDispose: false`; `start` / `stop` / `setActive` are untouched.
- `ChatPaneState.get transcriptGrowthSignature(): string` — new pure `get` computed (throws). **A string, never a number** — the coder joins `messages.length`, `streamingContent.length`, `streamingThinking.length`, `streamingToolTrace.length` with a separator. The exact separator is **not** part of the contract: DoD-11 must assert that the value **changes**, never what it equals.
- Observable fields the signature derives from, for DoD-11 (writable directly in a test, ideally inside `runInAction`): `messages: ChatMessageResponse[]`, `streamingContent: string`, `streamingThinking: string`, `streamingToolTrace: ToolTraceRow[]`. `ToolTraceRow` is exported from this same module: `export interface ToolTraceRow { toolName: string; arguments: Record<string, unknown>; result: string | null; ok: boolean | null }`.

**`frontend/src/work/components/chat/chatPaneState.ts` — the external operations** (all `export function`, state first, per this file's "no effectful methods" rule)

- `export function attachTranscriptViewport(state: ChatPaneState, element: HTMLDivElement | null): void` — new (**stub is a NO-OP**, see stub conventions below)
- `export function noteTranscriptScroll(state: ChatPaneState): void` — new (throws). **Takes no position argument** — Mantine's `{ x, y }` is ignored by design; it measures the element.
- `export function scrollTranscriptToBottom(state: ChatPaneState): void` — new (throws). The synchronous one.
- `export function followTranscript(state: ChatPaneState): void` — new (throws). The deferred + coalesced one (schedules a rAF).
- `export function repinTranscript(state: ChatPaneState): void` — new (throws). **THE FORCE-RE-PIN DECISION, made here as the plan allows: ONE new exported function, not "write the pinned flag then call the follow".** Reasons: the pinned flag is non-observable and must not become part of the test surface; DoD-8 names "the re-pin operation" as a single thing; and the three call sites want one shared helper. It sets `transcriptPinned = true` and then calls `followTranscript`, so **DoD-8 needs a frame flush after calling it.**
- `export function releaseTranscriptViewport(state: ChatPaneState): void` — new (**stub is a NO-OP**, see below)
- **The three re-pin CALL SITES are deliberately NOT inserted by the skeleton** — inserting them would implement DoD-12. `loadChatMessages`, `sendChatTurn` and `retryChatTurn` are unchanged.

**`loadChatMessages`, and everything DoD-12 needs to mock `api/chats` blind**

- `frontend/src/work/components/chat/chatPaneState.ts` — `export async function loadChatMessages(state: ChatPaneState, bookId: string, chatId: string, signal?: AbortSignal): Promise<void>` — **UNCHANGED signature**, recorded because DoD-12 drives it.
- The module imports the api as a NAMESPACE: `import * as chatsApi from "../../../api/chats"`, so a whole-module `vi.mock("../../src/api/chats", () => ({ … }))` factory (the specifier every existing spec under `tests/work/` uses) replaces it wholesale.
- **What `loadChatMessages` calls on the success path — the complete list:**
  1. `stopChatTurn(state)` — same module, **no api call**, no network; it aborts any live turn and resets the streaming buffers / turn status;
  2. `chatsApi.getChat(bookId, chatId, signal)` — **the one and only `api/chats` call on this path.**
- **`getChat`'s exact signature and DTO:** `export async function getChat(bookId: string, chatId: string, signal?: AbortSignal): Promise<ChatDetailResponse>`.
  - `ChatDetailResponse` comes from `src/types/chats.d.ts` (specifier from a spec: `../../src/types/chats`) and is `{ chat: ChatResponse; messages: ChatMessageResponse[] }`.
  - `ChatMessageResponse` (same file): `{ id: string; chat_id: string; role: string; content: string; reasoning: string | null; position: number; created_at: ISODateString | null; tool_trace: ToolTraceEntry[] | null }`. A minimal mocked row needs all eight keys; `reasoning: null` and `tool_trace: null` are valid.
  - The success path is guarded — it reads `Array.isArray(detail?.messages) ? detail.messages : []`, so a factory may resolve a full `ChatDetailResponse` or an object with no messages without the load throwing. It then assigns `state.messages` and `messagesStatus = "ready"`.
  - Failure path: an `ApiError` becomes `messagesError` + `messagesStatus = "error"`; anything else rethrows; an aborted `signal` returns early.
- **Every other export of `src/api/chats.ts`, so a whole-module factory can be complete:**
  - `listChats(bookId: string, archived: boolean, signal?: AbortSignal): Promise<ChatResponse[]>`
  - `createChat(bookId: string, body: CreateChatRequest, signal?: AbortSignal): Promise<ChatResponse>`
  - `updateChat(bookId: string, chatId: string, body: UpdateChatRequest, signal?: AbortSignal): Promise<ChatResponse>`
  - `getChat(bookId: string, chatId: string, signal?: AbortSignal): Promise<ChatDetailResponse>`
  - `listModelOptions(bookId: string, signal?: AbortSignal): Promise<ModelOptionResponse[]>`
  - `titleChat(bookId: string, chatId: string, signal?: AbortSignal): Promise<ChatTitleResponse>`
  - `streamChatTurn(bookId: string, chatId: string, prompt: string | null, handlers: TurnStreamHandlers, subject?: TurnSubject, selectionText?: string | null): Promise<AbortController>`
  - `export interface TurnStreamHandlers { onThinking: (text: string) => void; onDelta: (text: string) => void; onDone: () => void; onError: (message: string) => void; onCanvas?: (frame: CanvasFrame) => void; onToolCall?: (frame: ToolCallFrame) => void; onToolResult?: (frame: ToolResultFrame) => void }` — **type-only**; a runtime factory does not provide it.
  - Every DTO name above lives in `src/types/chats.d.ts`.

**`frontend/src/work/components/chat/MessageList.tsx`** — wired for real (props only; no signature change)

- `export interface MessageListProps { state: ChatPaneState }` and `export const MessageList` — unchanged.
- Two props added to the EXISTING `<ScrollArea>`: `viewportRef={(el) => attachTranscriptViewport(state, el)}` and `onScrollPositionChange={() => noteTranscriptScroll(state)}`. **The rendered element tree is unchanged** (DoD-17's property) — no wrapper, no sentinel, no `id`, no `data-*`; `flex: 1` / `minHeight: 0` untouched. No `useRef`, no `useCallback`, no `useEffect`.
- The stale docblock at `:39-43` was left for the coder (prose, not interface).

**`frontend/src/work/components/shell/WorkspaceShell.tsx`** — wired for real (no signature change)

- A **second `autorun` inside the EXISTING mount `useEffect`**, immediately after `disposeChatWidthVar`: it reads `chatPaneState.transcriptGrowthSignature` and calls `followTranscript(chatPaneState)`. Its disposer plus `releaseTranscriptViewport(chatPaneState)` sit in the **existing cleanup** beside `disposeChatWidthVar()`. **No new `useEffect`; the deps array is still `[state, chatPaneState]`; no new import from `react` or `mobx`.**

**Stub-value conventions the coder replaces (and the test-coder must not rely on)**

- Throwing stubs: `isTranscriptPinned`, `transcriptBottomScrollTop`, `transcriptGrowthSignature`, `noteTranscriptScroll`, `scrollTranscriptToBottom`, `followTranscript`, `repinTranscript`.
- **No-op (non-throwing) stubs: `attachTranscriptViewport` and `releaseTranscriptViewport`.** Both sit on a LIVE path existing specs exercise — the attach runs on every render of `MessageList`, the release on every shell unmount — and a throw there would break `ChatConversation.test.tsx` / `ChatPane.test.tsx` / `WorkspaceShell.test.tsx` during the red gate, which DoD-17 forbids. Neither can satisfy an assertion: with the attach a no-op the viewport slot stays `null`, so DoD-5 and DoD-13 still fail red. Precedent: `fast/008` kept `readWorkspaceLayout` total for the same reason.
- The throwing `transcriptGrowthSignature` is read by the new shell autorun at mount. MobX's reaction boundary **catches** it and logs `[mobx] Encountered an uncaught exception …` to stderr — verified: all four specs named in DoD-17 still pass against the skeleton (47 tests green). That stderr line is expected red-gate noise, not a failure.

**Caller-compile edits (out of Source-files scope): None.** No file outside the plan's four Source files was touched.

**Compile gate:** `cd frontend && npx tsc --noEmit` clean; `cd frontend && npm run test:types` clean. Sanity run of the four DoD-17 specs (`ChatConversation`, `WorkspaceShell`, `ChatPane`, `chatStreaming`): 47/47 passing.

## Tests

### Tests (2026-09-14)

- `frontend/tests/work/transcriptScroll.test.ts` — covers DoD-1, DoD-2, DoD-3, DoD-4 — the pure module: the `64` literal, the inclusive pin boundary (`1500`/`1436` pinned, `1435`/`0` not), degenerate input resolving to pinned, and the bottom helper (`(2000, 500)` → `1500`, floored at `0`, non-finite → `0`). No DOM, no mocks.
- `frontend/tests/work/transcriptAutoscroll.test.tsx` — covers DoD-5 … DoD-13 — attach/release own the viewport slot; a fresh pane is pinned with no scroll event; note-scroll preserves a scrolled-up position with **zero writes** and re-engages at the bottom; `repinTranscript` + one frame overrides an unpinned viewport; `followTranscript` writes nothing synchronously and coalesces four rapid calls into exactly one write, and nothing at all while unpinned; the growth signature **changes** for each of the four sources and for the append-while-clearing mutation a sum would cancel; `loadChatMessages` (with `api/chats` mocked wholesale) re-pins; `MessageList` attaches the ScrollArea's viewport and clears it on unmount.
- DoD-13's structural clause (revised 2026-09-14): the attached node is asserted to be **a strict ancestor of the rendered transcript content** and **not the outermost element of the component's own subtree** — the property that holds for the scroll container and fails for the root wrapper. The component root is derived by walking **up** from a node found by its visible text until its parent is the RTL container; `container.firstElementChild` is deliberately **not** used, because `renderWithProviders`' `MantineProvider` emits `<style>` elements as the container's first children, so that anchor is a style tag and the containment check would be false for every implementation alike. No Mantine class name is touched.
- Mechanics: a hand-made stub `div` with `scrollHeight` / `clientHeight` via `Object.defineProperty` and `scrollTop` as a counting getter/setter pair (jsdom computes no layout); frames flushed by queueing a real rAF behind the pending one — **no fake timers**.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 [manual/live, no test], DoD-15 [manual/live, no test], DoD-16 [manual/live, no test], DoD-17 [manual/live, no test]

## Notes & Issues

- No suppression flag for the programmatic scroll's own event, as specified: the write lands at the bottom, so `noteTranscriptScroll` recomputes to pinned = true and the loop terminates on its first iteration.
- The re-pin in `sendChatTurn` / `retryChatTurn` sits immediately after the accepting `runInAction` and before `chatsApi.streamChatTurn` — i.e. after validation and the settings flush, at the point the turn actually begins. Neither signature changed.
- No new `useEffect` / `useRef` / `useCallback` / `useMemo` anywhere; the shell's deps array is still `[state, chatPaneState]`; `MessageList`'s rendered element tree and its `flex: 1` / `minHeight: 0` are untouched; nothing is persisted.
- `cd frontend && npm run build` clean (tsc + vite). Tests not run by the coder, per the air gap.
