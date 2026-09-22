# Fast feature 009 — model-picker

| Status  | Verifier | Date |
|---------|----------|------|
| done    | PASS     | 2026-09-14 |

## Files Changed

- `frontend/src/work/components/chat/ChatPane.tsx` — the header model control is now a controlled Mantine `Combobox` (already-open, searchable option list, `autoFocus`ed `"Search models"` input, the three labelled non-option states) wired to `pickChatModel`, plus the `serverErrors.model` alert in the header region
- `frontend/src/work/components/chat/chatPaneState.ts` — `filteredModelOptions` implemented, `pickChatModel` implemented (optimistic header, model-pair-only PATCH, revert + `serverErrors.model` on refusal, model-half draft re-seed), and `saveChatSettings` now omits the model pair instead of nulling it when the drafted option resolves to nothing

## Skeleton

### Frozen interface (2026-09-14)

**New members — `frontend/src/work/components/chat/chatPaneState.ts`**

- `frontend/src/work/components/chat/chatPaneState.ts` — `ChatPaneState.modelSearch: string` (plain observable field, initial value `""`) — **new**. The model dropdown's search needle; two-way bound by the `"Search models"` input, reset to `""` on open and on dismissal.
- `frontend/src/work/components/chat/chatPaneState.ts` — `get filteredModelOptions(): ModelOptionResponse[]` (computed on `ChatPaneState`) — **new**. Case-insensitive substring match of `modelSearch` against the `` `${server_name} · ${model_name}` `` label; empty needle → all options; `modelOptions`' own order preserved. Body throws (stub).
- `frontend/src/work/components/chat/chatPaneState.ts` — `export async function pickChatModel(state: ChatPaneState, bookId: string, optionKey: string, signal?: AbortSignal): Promise<void>` — **new**. The immediate-pick effect (`signal` last, per the house convention). `optionKey` is a `modelOptionKey(option)` value. Body throws (stub).
- Failure surface for a pick: the existing map, under the stable key `"model"` — `state.serverErrors["model"]` (a `string`). The in-flight marker is the **existing** `state.settingsStatus` trio; no new status field exists.

**Unchanged and NOT re-declared — behaviour the `fast-coder` fills, not signature work:** `get modelLabel(): string` (its unresolvable-pair fallback) and `saveChatSettings`'s omit-instead-of-null request body. Both keep the signatures recorded below.

**Existing signatures the tests bind to (unchanged by this feature; recorded because the test-coder may not read source)**

All from `frontend/src/work/components/chat/chatPaneState.ts`:

- `new ChatPaneState()` — **constructor takes no arguments.** It reads `readWorkspaceLayout()` and `window.innerHeight` during construction (both available under jsdom). The pane holds **no book id**; every effect function takes `bookId` as an argument.
- `export function modelOptionKey(option: ModelOptionResponse): string` — returns `` `${option.server_id}::${option.model_name}` ``.
- `export async function loadChatPane(state: ChatPaneState, bookId: string, signal?: AbortSignal): Promise<void>`
- `export async function saveChatSettings(state: ChatPaneState, bookId: string, signal?: AbortSignal): Promise<void>`
- `export async function sendChatTurn(state: ChatPaneState, bookId: string, text: string): Promise<void>` — **no `signal` parameter**; it owns its own `AbortController`.
- `export async function createChatInstant(state: ChatPaneState, bookId: string, signal?: AbortSignal): Promise<void>`
- `export function pickChat(state: ChatPaneState, bookId: string, chatId: string): void`
- `export function stopChatTurn(state: ChatPaneState): void`
- `export interface ChatModelSettingsDraft { optionKey: string | null; temperature: number }`
- `export interface NewChatDraft extends ChatModelSettingsDraft { title: string }` — i.e. `{ title: string; optionKey: string | null; temperature: number }`
- `export const DEFAULT_TEMPERATURE = 0.8`, `export const MIN_TEMPERATURE = 0`, `export const MAX_TEMPERATURE = 2`

**`ChatPaneState` public surface after this change** (fields, then computeds; `<Trio>` = `"idle" | "loading" | "ready" | "error"`):

- Fields: `chats: ChatResponse[]`, `chatsStatus: <Trio>`, `chatsError: string | null`, `modelOptions: ModelOptionResponse[]`, `modelOptionsStatus: <Trio>`, `modelOptionsError: string | null`, `activeChatId: string | null`, `showArchived: boolean`, `openedPanel: "model" | "settings" | null`, **`modelSearch: string`** *(new)*, `newChatDraft: NewChatDraft`, `settingsDraft: ChatModelSettingsDraft`, `serverErrors: Record<string, string>`, `createStatus: <Trio>`, `archiveStatus: <Trio>`, `settingsStatus: <Trio>`, `messages: ChatMessageResponse[]`, `messagesStatus: <Trio>`, `messagesError: string | null`, `streamingContent: string`, `streamingThinking: string`, `streamingToolTrace: ToolTraceRow[]`, `turnStatus: "idle" | "streaming" | "error"`, `turnError: string | null`, `liveThinkingExpanded: boolean`, `expandedReasoning: Record<string, boolean>`, `expandedToolCallRows: Record<string, boolean>`, `pendingPrompt: string`, `composerHeight: number`, `composerResizing: boolean`, `composerResizeDispose: (() => void) | null`, `turnController: AbortController | null`, `closeTurnActive: { bookId: string; chapterId: string } | null`; bound methods `start(bookId, chapterId): void`, `stop(): void`, `setActive(active): void`.
- Computeds: `isComposerReadOnly: boolean`, `composerReadOnlyReason: string | null`, `visibleChats: ChatResponse[]`, `activeChat: ChatResponse | null`, `settingsDirty: boolean`, `modelLabel: string`, **`filteredModelOptions: ModelOptionResponse[]`** *(new)*, `canCreateChat: boolean`, `errors: Record<string, string>`, `canSend: boolean`, `retryOffered: boolean`, `renderedMessages: RenderedMessage[]`.
- `settingsDirty` is **unchanged** — re-seeding `settingsDraft.optionKey` in `pickChatModel` is sufficient to make the model half read clean, so the computed was not widened.

**`frontend/src/work/components/chat/ChatPane.tsx` — component signature unchanged**

- `export interface ChatPaneProps { bookId: string; state: ChatPaneState }`
- `export const ChatPane` — an `observer` function component `({ bookId, state }: ChatPaneProps)`. No stub was written here: swapping the `Popover` + `<Select>` for a `Combobox` is behaviour, not signature.

**Accessible handles — the rendering contract for `ChatPane.tsx` (exact strings, test-bindable):**

| Handle | Accessible name / exact text |
|---|---|
| Header model button (opens the dropdown) | `aria-label="Model"`, rendering `state.modelLabel` as its visible text |
| Search input inside the dropdown | accessible name exactly `"Search models"` |
| Each option row | `` `${server_name} · ${model_name}` `` — the existing label shape (`·` is U+00B7, space-padded) |
| Empty loaded catalogue | exactly `"No models available"` |
| Options failed to load | the value of `state.modelOptionsError` |
| Needle matches nothing | exactly `"Nothing found"` |
| Pick failure message | the value of `state.serverErrors["model"]`, rendered in the header region with the dropdown closed |

**Wire types (unchanged, `frontend/src/types/chats.d.ts`):** `ModelOptionResponse { server_id: string; server_name: string; model_name: string }`; `UpdateChatRequest { title?: string | null; archived?: boolean | null; llm_server_id?: string | null; model_name?: string | null; sampling?: ChatSamplingParams | null }` (every field optional); `ChatResponse.llm_server_id: string | null` / `.model_name: string | null` / `.sampling: ChatSamplingParams`.

- Caller-compile edits (out of Source-files scope): None.
- Typecheck: `cd frontend && npx tsc --noEmit` clean; `npm run test:types` clean.

## Tests

### Tests (2026-09-14)

- `frontend/tests/work/ChatModelPicker.test.tsx` — **new** — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5, DoD-7, DoD-10, DoD-11, DoD-12, DoD-13 — the component-level interaction spec: one click opens a rendered, focused list; case-insensitive label filtering and order-preserving restore; click-pick closes + moves the header; Enter picks the first *filtered* option; Escape closes and persists nothing; a rejected pick reverts the header and renders `serverErrors["model"]` with the dropdown closed; the three exact non-option lines (`"No models available"`, the `modelOptionsError` text, `"Nothing found"`) each accept no pick; the `openedPanel` discriminator both directions; the needle resets on reopen; opening triggers no `listModelOptions` call.
- `frontend/tests/work/chatPaneSettings.test.ts` — **extended** — covers DoD-6, DoD-8, DoD-9, DoD-11 — a pick issues exactly one update whose body key set is exactly `{llm_server_id, model_name}` and opens no stream; the model half of `settingsDraft` is re-seeded (no re-PATCH on the next send) while an unsent temperature edit survives and still flushes; an unresolvable stored pair makes the flush **omit** both fields (not null them) and `modelLabel` falls back to the stored `model_name`; an accepted send still clears `openedPanel`. The pre-existing 023 DoD-4 / DoD-5 cases are untouched.
- `frontend/tests/work/ChatPane.test.tsx` — **repaired only** — its `"settings are editable on the active chat (011 DoD-8)"` case now drives the model half through the new header picker (one click opens, one picks) and keeps the temperature half on the draft + `saveChatSettings` flush; imports gained `waitFor` and `userEvent`. No other case in the file was changed.
- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 [manual/live, no test], DoD-15 [manual/live, no test]
- Naming: new cases are prefixed `009 DoD-N` so they never collide with the `011 DoD-N` / `023 DoD-N` ids already living in the two inherited files.

## Notes & Issues

- `Combobox`'s `keepMounted` defaults to `true` (a bare `Popover`'s defaults to `false`), so `keepMounted={false}` is passed explicitly — without it the dropdown mounts once at first render and the search input's `autoFocus` never fires on open.
- DoD-4 ("Enter picks the first option of the filtered list") is an explicit `onKeyDown` on the search input rather than Mantine's built-in Enter: Mantine only clicks an **already highlighted** option (selected index starts at `-1`), and its own `Select` highlights the first option from a `useEffect`, which leaf components here may not use. The handler bails out when something *is* highlighted, so Mantine keeps DoD-14's arrows/Enter-picks-highlighted and no pick can fire twice.
- Consequence for DoD-14's live check: after the needle changes the highlight is **dropped** (not moved to the first option), because moving it would have to read the pre-filter DOM list. Enter still picks the first filtered option and ArrowDown still lands on it, but nothing is visibly highlighted until an arrow key is pressed.
- `pickChatModel` reverts the optimistic row and the draft for **any** rejection, but only an `ApiError` produces the `serverErrors.model` message — the module-wide idiom (`ApiError` → state, anything else rethrows), as recorded in the frozen interface.
- Out of scope, not touched: the settings popover's temperature validation still reads the *new-chat* draft's error (known defect 3), so a bad temperature typed in the header settings panel surfaces no message.
