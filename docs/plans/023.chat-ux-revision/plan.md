# 023.chat-ux-revision — plan

## Goal

Reshapes the delivered chat pane: authorship is visually distinct, chat management moves to a
content-pane list page, chats get a background auto-title after the 1st and 5th user message,
model/settings become inline popovers that flush before sending, and Ctrl/Cmd+Enter sends.

## Realizes

FEAT-013, UC-053, UC-054, UC-081, UC-082, US-056, US-095, US-096, US-105

## Source areas

Backend:
- `backend/app/services/` — new `chat_titling.py` (titling policy); `chats.py` only if a shared
  helper is genuinely needed, no new `ChatErrorReason`
- `backend/app/db/chat_messages.py` — message counting query
- `backend/app/routes/chats.py` — HTTP wiring for the new titling endpoint
- `backend/app/models/schemas/chats.py` — titling response DTO

Frontend:
- `frontend/src/work/pages/` — new `ChatsListPage.tsx` + `chatsListPageState.ts`
- `frontend/src/work/components/chat/` — `ChatPane.tsx`, `chatPaneState.ts`, `MessageList.tsx`,
  `Composer.tsx`, `ChatSettingsPanel.tsx`, `ChatList.tsx`
- `frontend/src/work/components/shell/` — `navItems.ts`, `WorkNavigator.tsx`, `WorkspaceShell.tsx`
- `frontend/src/work/` — `routes.tsx`, new `chatPaneController.ts`
- `frontend/src/api/chats.ts`, `frontend/src/types/chats.d.ts` — wire layer for titling

## Test files

- `backend/tests/services/test_chat_titling.py` (new)
- `frontend/tests/work/ChatPane.test.tsx` (retargeted)
- `frontend/tests/work/chatsNavigatorEntry.test.tsx` (retargeted)
- `frontend/tests/work/WorkNavigator.test.tsx` (retargeted)
- `frontend/tests/work/subjectRoutes.test.tsx` (retargeted)
- `frontend/tests/work/WorkspaceShell.test.tsx` (retargeted)
- `frontend/tests/work/chatPaneSettings.test.ts` (new)
- `frontend/tests/work/Composer.test.tsx` (new)
- `frontend/tests/work/ChatsListPage.test.tsx` (new)

The five retargeted specs assert the arrangement 023 inverts (D12); the test-coder **rewrites**
them against this plan's contract — never weakens them to pass against the old one, and the coder
never edits them to go green.

## Interface

### Backend — `backend/app/db/chat_messages.py`

```python
async def count_by_chat_and_role(chat_id: int, role: str) -> int
```
Counts persisted messages for a chat filtered by role; lets the titler detect the 1st/5th user
message without loading the transcript.

### Backend — `backend/app/services/chat_titling.py` (new file)

```python
_TITLE_TRIGGER_COUNTS: frozenset[int] = frozenset({1, 5})
_TITLE_MAX_LENGTH = 80  # sanitizer cap, planner-owned; no DoD pins the number

def _is_titling_trigger(user_message_count: int) -> bool
def _build_title_transcript(messages: list[ChatMessage]) -> list[LLMMessage]
def _sanitize_title(raw: str) -> str
async def maybe_title_chat(access: authz.BookAccess, chat_id: str) -> ChatTitleResponse
```
- `_is_titling_trigger` — true exactly when the count is 1 or 5, false otherwise (not `>=`).
- `_build_title_transcript` — maps persisted messages (role + content), oldest first, into the
  `llm` client's chat-message shape for a one-shot summarization prompt.
- `_sanitize_title` — strips wrapping quotes/whitespace/newlines, collapses to one line, caps at
  `_TITLE_MAX_LENGTH`; returns `""` when nothing usable remains (an empty result is a failure, per
  DoD-2).
- `maybe_title_chat` — resolves the caller's owned chat via `chats_service._resolve_owned_chat`
  (propagates `ChatError(chat_not_found)` uncaught — the only exception allowed to reach the
  route), counts user messages via `count_by_chat_and_role(chat.id, "user")`. Off-trigger: returns
  `ChatTitleResponse(title=chat.title, changed=False)`, no LLM call. On trigger: resolves the
  chat's own `(llm_server_id, model_name)` server + `secrets.resolve_env_ref`-resolved key, opens
  `llm_servers.create_model_client(...)` `async with`, calls `client.chat(transcript)`, sanitizes,
  and on a non-empty result persists via `chats.update` and returns `changed=True`. A missing model
  pair, any of `(aiohttp.ClientError, LLMError, ValueError, RuntimeError)`, or a blank sanitized
  result are all swallowed identically: existing title stands, `changed=False`, nothing persisted,
  nothing raised.

### Backend — `backend/app/models/schemas/chats.py` (append)

```python
class ChatTitleResponse(BaseModel):
    title: str
    changed: bool
```

### Backend — `backend/app/routes/chats.py` (append)

```python
async def title_chat(chat_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> ChatTitleResponse
```
`POST /{book_id}/chats/{chat_id}/title`. Calls `chat_titling.maybe_title_chat`; maps `ChatError` via
the existing `_map_chat_error`. Declared after `model-options`, alongside `turn`.

### Frontend — `frontend/src/types/chats.d.ts` (append)

```ts
export interface ChatTitleResponse { title: string; changed: boolean; }
```

### Frontend — `frontend/src/api/chats.ts` (append)

```ts
export async function titleChat(bookId: string, chatId: string, signal?: AbortSignal): Promise<ChatTitleResponse>
```
Thin `request<T>` forwarder, `POST {BASE}/{bookId}/chats/{chatId}/title`, no body.

### Frontend — `frontend/src/work/chatPaneController.ts` (new file)

```ts
export interface ChatPaneController {
  openChat: (chatId: string) => void;
}
export function registerChatPaneController(controller: ChatPaneController): void
export function unregisterChatPaneController(controller: ChatPaneController): void
export function requestOpenChat(chatId: string): boolean
```
Single-slot module registry mirroring `closeTurnController`. `requestOpenChat` calls the
registered controller's `openChat` and returns `true` if one is registered, `false` otherwise (no
throw when nothing is registered).

### Frontend — `frontend/src/work/pages/chatsListPageState.ts` (new file)

```ts
export class ChatsListPageState {
  chats: ChatResponse[] = [];
  chatsStatus: "idle" | "loading" | "ready" | "error" = "idle";
  chatsError: string | null = null;
  showArchived = false;
  actionStatus: Record<string, "idle" | "loading" | "error"> = {};
  constructor()
  get isEmpty(): boolean
  get visibleChats(): ChatResponse[]
}
export async function loadChats(state: ChatsListPageState, bookId: string, signal?: AbortSignal): Promise<void>
export async function archiveListChat(state: ChatsListPageState, bookId: string, chatId: string, archived: boolean, signal?: AbortSignal): Promise<void>
```
`loadChats` fetches both archived and non-archived sets (two `listChats` calls, merged into
`chats`) so toggling `showArchived` is a client-side filter, matching `chatPaneState`'s existing
`visibleChats` shape. `visibleChats` filters `chats` by `showArchived`, most-recent-first.
`isEmpty` is true when `visibleChats.length === 0`. `archiveListChat` persists via
`chatsApi.updateChat(bookId, chatId, {archived}, signal)`, tracks per-row status in
`actionStatus[chatId]`, replaces the row in `chats` on success.

### Frontend — `frontend/src/work/pages/ChatsListPage.tsx` (new file)

```ts
export const ChatsListPage = observer(function ChatsListPage() { ... })
```
No props — reads `bookId` via `useParams()`. Own `useState(() => new ChatsListPageState())`. One
page-level mount `useEffect` (deps `[state]`): `loadChats(state, bookId, ctrl.signal)`, cleanup
aborts. Renders `<ChatList>`; row pick calls `requestOpenChat(chatId)` and does **not** navigate;
row archive/restore calls `archiveListChat`.

### Frontend — `frontend/src/work/components/chat/ChatList.tsx` (changed)

```ts
export interface ChatListProps {
  state: ChatsListPageState;
  onPick: (chatId: string) => void;
  onSetArchived: (chatId: string, archived: boolean) => void;
}
export const ChatList = observer(function ChatList({ state, onPick, onSetArchived }: ChatListProps) …)
```
Same row shape as before (title, stamp, archive/restore icon, active-marker dropped — the list
page has no notion of "active"); now reads `ChatsListPageState` instead of `ChatPaneState`.

### Frontend — `frontend/src/work/components/chat/chatPaneState.ts` (additions; every existing
exported symbol from the harvest is preserved unchanged)

```ts
// new field on ChatPaneState
openedPanel: "model" | "settings" | null

// new computeds
get settingsDirty(): boolean
get modelLabel(): string

// new effect functions
export async function createChatInstant(state: ChatPaneState, bookId: string, signal?: AbortSignal): Promise<void>
export async function refreshChatTitle(state: ChatPaneState, bookId: string, chatId: string, signal?: AbortSignal): Promise<void>

// extended contract, signature unchanged
export async function sendChatTurn(state: ChatPaneState, bookId: string, text: string): Promise<void>
```
- `settingsDirty` — true when `settingsDraft` (`optionKey`/`temperature`) differs from
  `activeChat`'s persisted pair/temperature; false with no active chat.
- `modelLabel` — header label built from `activeChat`'s persisted model pair (not the draft), e.g.
  `"<server> · <model>"`, or a placeholder string when unset.
- `createChatInstant` — no form: default model pair is the active chat's, else `modelOptions[0]`;
  default sampling; creates via `chatsApi.createChat`, makes the new chat active with an empty
  transcript. Sets `serverErrors.form` and creates nothing when `modelOptions` is empty (UC-054's
  refuse-to-compose flow survives).
- `refreshChatTitle` — calls `chatsApi.titleChat(bookId, chatId, signal)`; when `changed`, replaces
  the matching row's `title` in `state.chats` (which `activeChat` derives from). Called
  fire-and-forget (not awaited) from the module-private `finishTurn`, with the chat id captured at
  that point — never blocks `turnStatus` returning to `idle`.
- `sendChatTurn` — same signature; now, before opening the stream: if `settingsDirty`, `await
  saveChatSettings(state, bookId)` (existing function, reused as-is); if that leaves
  `settingsStatus === "error"`, do not open the stream (the existing `serverErrors.form` from
  `saveChatSettings` is the author-facing message). On acceptance, sets `openedPanel = null`.

### Frontend — `frontend/src/work/components/chat/ChatPane.tsx` (changed)

`ChatPaneProps` unchanged: `{ bookId: string; state: ChatPaneState }`. Header keeps the title but
drops the list/new-chat icons; gains a model control (click → `openedPanel = openedPanel === "model"
? null : "model"`, showing a `<Select>` bound to `state.settingsDraft.optionKey` over
`state.modelOptions`) and a settings control (same toggle on `"settings"`, `Popover.Dropdown`
containing `<ChatSettingsPanel draft={state.settingsDraft} errors={state.errors}/>`), and a "+"
icon wired to `createChatInstant`. No `ChatList`, no new-chat form, no "Save settings" button
anywhere in the tree — chat management lives only on `ChatsListPage` now.

### Frontend — `frontend/src/work/components/chat/MessageList.tsx` (changed)

`MessageListProps` unchanged: `{ state: ChatPaneState }`. User messages: tinted, right-offset
`Box`/`Paper`, `max-width: 85%`, `data-role="user"` preserved. Assistant messages: full-width,
`data-role="assistant"` preserved, a role label, a `Divider` before each new turn.

### Frontend — `frontend/src/work/components/chat/Composer.tsx` (changed)

`ComposerProps` unchanged: `{ state, onSend, onStop, onRetry }`. `Textarea` gains `onKeyDown`:
`event.key === "Enter" && (event.ctrlKey || event.metaKey)` → `preventDefault()` + `onSend()`, only
when `state.canSend`; no-op while streaming; plain `Enter` untouched (inserts a newline).

### Frontend — `frontend/src/work/components/chat/ChatSettingsPanel.tsx` (changed)

```ts
export interface ChatSettingsPanelProps {
  draft: ChatModelSettingsDraft;
  errors: Record<string, string>;
}
export const ChatSettingsPanel = observer(function ChatSettingsPanel({ draft, errors }: ChatSettingsPanelProps) …)
```
Drops `options` — renders `NumberInput label="Temperature"` only (`MIN_TEMPERATURE`/
`MAX_TEMPERATURE`/step `0.1`), bound to `draft.temperature`. Model selection moved to `ChatPane`'s
own "model" popover (a plain `<Select>`, not this component).

### Frontend — `frontend/src/work/components/shell/WorkNavigator.tsx` (changed)

```ts
export interface WorkNavigatorProps { bookId: string; collapsed?: boolean; }
export const WorkNavigator = observer(function WorkNavigator({ bookId, collapsed = false }: WorkNavigatorProps) …)
```
`onShowChatList` is gone. All seven entries render identically as `<NavLink component={RouterLink}
to={workNavHref(bookId, item)} active={...}/>` — no `paneTarget`-based branching left in the body.

### Frontend — `frontend/src/work/components/shell/navItems.ts` (one-line change)

The Chats entry's `paneTarget` becomes `"content"`. `WorkPaneTarget`, `WorkNavItem`,
`WORK_NAV_ITEMS`, `workNavHref`, `isWorkNavItemActive` signatures unchanged.

### Frontend — `frontend/src/work/components/shell/WorkspaceShell.tsx` (changed, no new exports)

Inside the **existing** mount `useEffect` (no second effect): constructs one controller object
(`{ openChat: (chatId) => pickChat(chatPaneState, bookId, chatId) }`), calls
`registerChatPaneController(controller)`; cleanup calls `unregisterChatPaneController(controller)`
alongside the existing `unregisterCloseTurnController`. Drops the `onShowChatList` prop passed to
`<WorkNavigator>`.

### Frontend — `frontend/src/work/routes.tsx` (changed)

`chats` route renders `<ChatsListPage/>` instead of `<ChatsRedirectRoute/>`; `ChatsRedirectRoute`
function is deleted.

## Implementation outline

1. Backend: `count_by_chat_and_role`, `chat_titling.py` (trigger/transcript/sanitize/entry point),
   `ChatTitleResponse`, the `POST .../title` route.
2. Frontend wire layer: `ChatTitleResponse` DTO, `titleChat` forwarder, `chatPaneController.ts`.
3. `chatPaneState.ts`: `openedPanel`, `settingsDirty`, `modelLabel`, `createChatInstant`,
   `refreshChatTitle`, `sendChatTurn`'s flush-before-send extension — preserving every existing
   export.
4. Chat pane UI: `ChatPane.tsx` (popovers, "+" control, drop list/new-chat/Save), `MessageList.tsx`
   (bubble/divider/role-label), `Composer.tsx` (Ctrl/Cmd+Enter), `ChatSettingsPanel.tsx` (narrowed
   to temperature).
5. Chats list page: `chatsListPageState.ts`, `ChatsListPage.tsx`, `ChatList.tsx`'s retargeted props.
6. Navigator/shell/routes: `navItems.ts` flip, `WorkNavigator.tsx` simplification,
   `WorkspaceShell.tsx` controller registration + dropped prop, `routes.tsx` swap.

## Definition of done

1. `[test]` Titling fires when the user-message count is exactly 1 and exactly 5; counts 2, 3, 4
   and 6 return the existing title with `changed=false` and make no LLM call.
2. `[test]` A titling LLM failure (each failure-taxonomy class, plus a blank result) leaves the
   existing title intact, returns `changed=false`, raises nothing.
3. `[test]` A successful titling call uses the chat's own configured model pair and persists a
   sanitized single-line title.
4. `[test]` A dirty settings change is persisted via the update call before the turn stream opens;
   a clean state issues no update call; a failed flush aborts the send with an author-facing error
   and opens no stream.
5. `[test]` Opening either popover closes the other, and sending a message clears both
   (`openedPanel`).
6. `[test]` Ctrl+Enter and Cmd+Enter send when sending is allowed, do nothing while streaming, and
   plain Enter does not send.
7. `[test]` The chat list page loads its own chats for the book, picking one opens it through the
   registered pane controller without changing the route, and archive/restore round-trips
   (UC-082, US-095.AC-2, US-096.AC-1/AC-2).
8. `[test]` The Chats navigator entry navigates to `/:bookId/chats`, that route renders the list
   page rather than redirecting, and the chat pane renders no chat list — **contradicts
   US-105.AC-3, US-095.AC-1 and UC-081 step 1 by design; see `outcome.md` item 1.**
9. `[test]` Creating a chat from the pane's "+" resolves a default model pair, makes the new chat
   active with an empty transcript, and is refused with an author-facing message when no model
   options exist (UC-053, US-056.AC-1, UC-054 exception flow).
10. `[verify]` The Chats nav entry's `paneTarget` is `"content"` in `navItems.ts`.
11. `[verify]` `ChatsRedirectRoute` is gone from `routes.tsx` and `/chats` renders `ChatsListPage`.
12. `[verify]` `onShowChatList` is removed from both `WorkNavigatorProps` and `WorkspaceShell`'s
    call site, with no dead prop left on either side.
13. `[verify]` The titling route is registered on the chats router after the static `model-options`
    route.
14. `[verify]` `count_by_chat_and_role` exists in `db/chat_messages.py`.
15. `[verify]` `chatPaneController` is registered and unregistered inside `WorkspaceShell`'s
    existing mount effect — no second effect added.
16. `[verify]` Every feature-013/015/016 member of `ChatPaneState` listed in design-note D11 (in
    `docs/.cache/ultra/023.chat-ux-revision/design-notes.md`) still exists, unchanged.
17. `[manual/live]` Real titling against a live LLM server.
18. `[manual/live]` Visual review of the message bubble/divider/role-label treatment and both
    popovers.
19. `[manual/live]` `cd backend && .venv/Scripts/python -m pytest` — full backend suite green.
20. `[manual/live]` `cd frontend && npm run build` — typecheck + bundle clean.
21. `[manual/live]` `cd frontend && npm test` — full frontend suite green.
22. `[manual/live]` `cd frontend && npm run test:types` — test-tree typecheck clean.

## Test plan

**Tested:**
- DoD-1 — titling fires only at user-message counts 1 and 5, not `>=` — edge semantics (the exact
  trigger boundary is the whole point of D3's design).
- DoD-2 — every failure-taxonomy exception plus a blank result leaves title/changed untouched and
  raises nothing — invariant (a titling failure must never surface as a turn or request failure).
- DoD-3 — a successful call is bound to the chat's own model pair and persists a sanitized title —
  contract (D4: no global/utility model exists; the client must resolve per-chat).
- DoD-4 — settings flush ordering around the send seam (dirty → persisted before stream; clean → no
  call; failed flush → no stream) — seam (D8: this is the one place client state and server state
  must agree before the turn reads the stored pair).
- DoD-5 — `openedPanel` discriminator (exclusive open, cleared on send) — state machine.
- DoD-6 — Ctrl/Cmd+Enter contract vs. plain Enter vs. streaming — edge semantics (keyboard
  contract, the one place a modifier combination is meaningful).
- DoD-7 — list page load, pick-through-controller with no navigation, archive/restore round-trip —
  contract + idempotency (archive/restore is a round trip).
- DoD-8 — nav entry → route → list page → empty pane list — contract (this is the inversion of
  011's shipped routing contract; the whole point is that it now holds).
- DoD-9 — instant-create default-pair resolution and the no-options refusal — edge semantics /
  exception flow (UC-054).

**Not tested (deliberate):**
- Message bubble / divider / role-label styling — pure presentation with no branching; the
  delivered 005 specs' `data-role` assertions remain the authorship contract.
- Popover open/close rendering — Mantine framework wiring; the `openedPanel` state machine is
  tested instead.
- The count-by-chat-and-role db function in isolation — a one-line query, covered through DoD-1.
- The titling api forwarder and its DTO — thin pass-through, no logic.
- The titling prompt's wording and any real model output — no precise expected value exists in the
  spec; covered as `[manual/live]`.
- The `chatPaneController` registry in isolation — covered through DoD-7, and it mirrors the
  already-tested `closeTurnController` idiom.

## Decisions taken

- **D0 — One ultra feature, not a bug fix + split routing.** Only item 1 (message styling) repairs
  011's contract; items 2–5 add/invert behaviour. Rejected splitting across `/bug-fixer` +
  `/product-spec` + `/planner`: all five reshape the same two files and would collide.
- **D1 — Item 2 knowingly inverts shipped product spec.** Moving the chat list to a content-pane
  page contradicts `US-095.AC-1`, `UC-081` step 1, `US-105.AC-3` and two sections of
  `frontend-workspace.md`. Decision: build now, reconcile docs later (user reaffirmed after being
  shown the conflict); `outcome.md` carries the obligation. Rejected: run `/product-spec` first
  (correct order, but the user chose momentum); rejected: keep the list in the pane (preserves
  spec, doesn't deliver what was asked).
- **D2 — Titling runs behind a dedicated endpoint the frontend fires post-turn**, not inside
  `run_turn` and not a detached task. No background-task infrastructure exists anywhere in this
  backend (`BackgroundTasks`, a queue, a registry — none). An ordinary route+service tests like any
  other and adds zero turn latency. Rejected: inside `run_turn` before `done` (blocks the terminal
  frame ~1-3s, not actually "background"); rejected: detached `asyncio.create_task` (no precedent,
  swallows errors invisibly, outlives the response, races the client's `getChat` reload).
- **D3 — Trigger is derived from a live message count; no new column.** Title exactly at 1 or 5
  via `count_by_chat_and_role`. Rejected: a `title_auto: bool` column (costs a column + two
  import/export codec keys); rejected: "only while title is still default" (the 5th-message pass
  could never fire once titled). Accepted trade-off, confirmed with the user: a hand-rename before
  the 5th user message is silently overwritten.
- **D4 — Titling uses the chat's own model pair.** No utility/small-model designation exists;
  mirrors `subagent_delegation.ParentTurn`'s "inherit the parent's pair" precedent. Rejected: a new
  designated titling model (needs an `LlmServer` column, an admin route, an import/export change, a
  UI — far beyond this feature). Failure swallowed, mirrors `_finalize_close_turn_if_needed`.
- **D5 — The list page reaches the pane through a module registry, not context.**
  `chatPaneController.ts` mirrors `closeTurnController`/`contentSubject`. The list page still loads
  its own chats (redundant fetch, blessed per "each page loads its own data by URL id"). Rejected:
  React context (banned outright); rejected: page writes the `activeChat` localStorage pointer (no
  reactivity, needs a remount); rejected: sharing the single `ChatPaneState` (breaks page=route=
  fresh-instance, couples a content page to the shell's aside state).
- **D6 — "+" creates a chat instantly, no form.** Default pair (active chat's, else first option) +
  default sampling; becomes active with an empty transcript; D2's titler names it later. Rejected:
  keep the current form (fights item 3 — a hand-typed title leaves auto-naming nothing to do — and
  keeps management chrome in a pane the user wants reduced).
- **D7 — One `openedPanel` discriminator drives both popovers.** Opening one closes the other by
  construction; `sendChatTurn` clears it. `Popover` is the codebase's first use (only `Menu`
  precedent, and a `NumberInput` doesn't fit `Menu.Item`).
- **D8 — Settings flush before send; a failed flush aborts the send.** Forced by the backend:
  `prepare_turn` reads the chat's **stored** pair, so unpersisted settings would silently not apply
  to the very message just sent. Rejected: send anyway with stored settings (silent mismatch);
  rejected: keep an explicit Save button too (re-adds the chrome being removed). Accepted
  trade-off: settings changed but never followed by a message are lost on reload — the literal
  spec'd behaviour.
- **D9 — Role-differentiated messages.** User: tinted, right-offset, ≤85% width bubble. Assistant:
  full-width markdown, role label, divider between turns — full width is deliberate, bubbling would
  narrow the author's actual working content. `data-role` hooks preserved. Rejected: bubbles both
  sides (narrows assistant markdown); rejected: label+divider only, no bubble (authorship still
  slow to scan).
- **D10 — Ctrl/Cmd+Enter on the Textarea.** Follows `ChatResizeHandle.tsx`, the only keyboard idiom
  in the repo. `metaKey` included for macOS even though development is Windows-only.
- **D11 — What must survive untouched.** `CloseTurnController` members, `isComposerReadOnly`/
  `composerReadOnlyReason`, `startCloseTurn`/`stopCloseTurn`, `onCanvas`, `turnSubject()`,
  `currentContentSelection()` — all from features 013/015/016. Called out as an explicit
  out-of-scope boundary (DoD-16).
- **D12 — Five delivered specs invalidated by design.** `ChatPane.test.tsx`,
  `chatsNavigatorEntry.test.tsx`, `WorkNavigator.test.tsx`, `subjectRoutes.test.tsx`,
  `WorkspaceShell.test.tsx` assert the pre-023 arrangement; the test-coder rewrites them against
  this plan, the coder never edits them to go green.

## Out of scope

- Reconciling `docs/product/` and `frontend-workspace.md` with the routing inversion — deferred by
  explicit user decision; obligation recorded in `outcome.md`.
- Any sampling parameter beyond `temperature` in the settings popover. Every other sampling field
  still round-trips unchanged on update (011's carry-through rule).
- Any change to close-turn / canvas / content-selection behaviour riding on `ChatPaneState` from
  features 013/015/016 (D11's list) — preserve exactly.
- Backfilling titles for chats that already exist.
- Any new `Chat` column, and therefore any `db_import_export.py` change (D3).
- Any new designated "utility"/"titling" model concept.
- `roadmap.md` and `brief.md` — not written by this feature.

## Risks

- The exact import path for `llm.LLMMessage` (the new transcript-builder helper's return type)
  isn't shown in the harvest; `from llm import LLMMessage` is the expected form by precedent
  (`LLMError`/`LLMClient` are already imported top-level from `llm` elsewhere) but is unverified —
  a wrong path is a same-file import fix, not a frozen-signature break.
- This is the frontend's first `Popover` — no in-repo idiom to copy for its open/close styling;
  visual coherence with the rest of the pane is a `[manual/live]` judgment call (DoD-18).
- `ChatsListPage` mounts inside `WorkspaceShell` via `<Outlet/>`, so its tests need the same
  `api/chats`/`api/books` mock sweep as every other subject-route spec — easy to miss and get a
  false failure unrelated to the page under test.
- `chatPaneState.ts` is touched by three independent axes (openedPanel/settings-flush, instant
  create, title refresh) in the same file already carrying features 013/015/016 — a careless edit
  risks clipping one of the D11-listed members; DoD-16 exists specifically to catch that.
