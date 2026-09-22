# Feature 023 — chat-ux-revision

| Status  | Verifier | Date |
|---------|----------|------|
| done    | PASS     | 2026-08-08 |

## Files Changed

**Backend**

- `backend/app/db/chat_messages.py` — filled `count_by_chat_and_role` (`func.count` scalar, no
  transcript load)
- `backend/app/services/chat_titling.py` — new module, all four bodies filled: the exact-1/5
  trigger, the 1:1 transcript map, the sanitizer (single line, wrapping-quote unwrap, 80-char cap)
  and `maybe_title_chat`'s resolve → call → persist path. Added private
  `_TITLE_FAILURE_EXCEPTIONS` (local, not imported from `chat_turn`), `_TITLE_QUOTE_CHARS` and
  `_TITLE_INSTRUCTION`
- `backend/app/routes/chats.py` — dropped the stale skeleton note on `title_chat` (registration was
  already frozen and is unchanged)
- `backend/app/models/schemas/chats.py` — untouched by the coder (`ChatTitleResponse` was
  declarative and complete at skeleton)

**Frontend**

- `frontend/src/work/chatPaneController.ts` — new module, all three bodies filled (single slot,
  newest-wins register, identity-guarded unregister, no-throw `requestOpenChat`)
- `frontend/src/work/pages/chatsListPageState.ts` — filled both computeds and both effect fns;
  added the private `chatTimestamp` sort helper
- `frontend/src/work/pages/ChatsListPage.tsx` — new page body: one mount effect, `ChatList`, a
  Show-archived switch, load/error/row-error surfaces; row pick calls `requestOpenChat` only
- `frontend/src/work/components/chat/chatPaneState.ts` — **additions only**: `settingsDirty` /
  `modelLabel` computeds, `createChatInstant`, `refreshChatTitle`, `sendChatTurn`'s
  flush-before-send + `openedPanel` clear, and the fire-and-forget title refresh in the
  module-private `finishTurn`. Added private consts `NO_MODEL_LABEL` /
  `NO_MODEL_OPTIONS_MESSAGE`. Every 011/013/015/016 export preserved verbatim (DoD-16).
  **Verifier round 1 fix (2026-08-08):** `settingsDirty` no longer reads an UNSEEDED draft as an
  author edit — a draft holding no chosen model option while the active chat has a pair returns
  `false` before the temperature comparison, so a pane the author has not edited issues no update
  call and opens the stream directly (DoD-4 clause 2), and the send can never flush an empty model
  pair over a chat that has one. `sendChatTurn`'s pre-step, clause 1 and clause 3, and the
  `openedPanel` discriminator are unchanged
- `frontend/src/work/components/chat/ChatPane.tsx` — reshaped: two `Popover`s driven by
  `openedPanel` (model `<Select>` / `<ChatSettingsPanel>`), a "+" wired to `createChatInstant`;
  dropped the local `showNewChat` state, the archived switch, the list/new-chat icons and the
  Save-settings block
- `frontend/src/work/components/chat/MessageList.tsx` — user bubble (tinted, right-offset, ≤85%),
  assistant role label + per-turn divider; `data-role` hooks preserved
- `frontend/src/work/components/chat/Composer.tsx` — `Ctrl`/`Cmd`+`Enter` send on the `Textarea`,
  gated by the same `canSend` / read-only test as the Send button
- `frontend/src/work/components/shell/navItems.ts` — Chats `paneTarget` → `"content"` (+ the prose
  that described the old exception)
- `frontend/src/work/components/shell/WorkspaceShell.tsx` — registers/unregisters the chat-pane
  controller inside the **existing** mount effect (no second effect)
- `frontend/src/work/routes.tsx` — `ChatsRedirectRoute` deleted; `/chats` renders `ChatsListPage`
- `frontend/src/work/components/chat/ChatList.tsx`, `ChatSettingsPanel.tsx`,
  `components/shell/WorkNavigator.tsx`, `src/api/chats.ts`, `src/types/chats.d.ts` — untouched by
  the coder (complete at skeleton)

## Feedback

### Round 1 (2026-08-08)

- F1 reshape — `frontend/src/work/components/chat/MessageList.tsx`,
  `frontend/src/work/components/chat/ChatPane.tsx`,
  `frontend/src/work/components/chat/Composer.tsx` — built the pane's missing vertical flex chain
  so the transcript fills instead of capping. `MessageList`'s root goes from
  `<ScrollArea.Autosize mah={320} type="auto">` to `<ScrollArea type="auto">` carrying
  `flex: 1` + `minHeight: 0`, so it consumes everything between header and composer and scrolls
  internally (the `minHeight: 0` is what lets it shrink below content height rather than growing the
  column). `ChatPane`'s root `Stack` gains `mih={0}` beside its existing `h="100%"`, documenting the
  chain and holding if that column ever becomes a flex item. `Composer`'s root `Stack` gains
  `flexShrink: 0` — the transcript grows from a zero flex basis and so absorbs no shrinkage, which
  would otherwise make the composer the first thing squeezed on a short pane or with the retry /
  read-only banners showing. Result: composer pinned to the bottom edge at any pane height and any
  conversation length, empty chat included, and no dead space below it. Preserves streaming deltas
  and the thinking region, composer gating and read-only states, mid-stream abort, retry, the
  013/015/016 close-turn / canvas / content-selection wiring, and both popovers on the single
  `openedPanel` discriminator. No auto-scroll added; no `AppShell` or resize-rail change.
  `MessageListProps` / `ComposerProps` / `ChatPaneProps` unchanged
- F2 reshape — `frontend/src/work/components/chat/MessageList.tsx` — user bubble max-width 85% →
  70%, and the fill strengthened from `--mantine-color-blue-light` to
  `bg="var(--mantine-primary-color-filled)"` with `c="var(--mantine-primary-color-contrast)"`, so
  the tint alone carries authorship and stays legible in both colour schemes (theme tokens, not a
  hard-coded colour; `contrast` is the text colour Mantine itself pairs with `filled`). The
  `data-role="user"` wrapper and its right-offset flex mechanism (`display: flex` +
  `justifyContent: flex-end`) are unchanged, as is the assistant's deliberate full width
- F3 reshape — `frontend/src/work/components/chat/MessageList.tsx` — removed the per-turn
  `<Divider>` and the dimmed "Assistant" label from the assistant row, and dropped the now-unused
  `index` map parameter and the `Divider` import with them. The wrapping
  `<Stack gap={4} data-role="assistant">` remains, and `ThinkingBlock` and the markdown body are
  untouched. Supersedes the delivered plan's `## Interface` line for `MessageList.tsx` and narrows
  design-note D9 — recorded in `outcome.md` → `## Observations` for finalization

### Round 2 (2026-08-08)

- F4 reshape — `frontend/src/work/components/chat/Composer.tsx` — the `<Group justify="flex-end">`
  row below the textarea is gone, and with it one full control row of vertical height, which now
  belongs to the transcript (continuous with F1). Send and Stop moved into the `Textarea`'s
  `rightSection` as `ActionIcon`s on the chat pane's own idiom (`@tabler/icons-react` at
  `size={18} stroke={1.5}`, `variant="light"`): `IconSend` with `aria-label="Send"`, and while
  streaming `IconPlayerStop` with `color="red"` and `aria-label="Stop"` — the accessible name an
  icon-only control depends on — swapping into the **same slot** rather than keeping a row of its
  own. Bottom-right anchoring needed three non-obvious Mantine settings, each commented in place:
  `rightSectionProps={{ style: { alignItems: "flex-end", paddingBottom: 4 } }}` because the section
  is absolutely positioned across the input's full height with `align-items: center` and would
  otherwise re-centre as the input autosizes 2→6 rows; `rightSectionPointerEvents="all"` because
  Mantine's default is `"none"`, which would have rendered a completely inert icon that
  `fireEvent`-based tests could not have caught; and `rightSectionWidth={40}` because the default
  width derives from `--input-height`, which an autosizing textarea has no fixed value for, and
  because it drives the input padding that keeps typed text from running under the icon.
  Preserved verbatim: the send gate `disabled={!state.canSend || closeReadOnly}` (with
  `closeReadOnly` still ANDed in separately — `canSend` does not check it), the swap condition
  `streaming && !closeReadOnly` so a close window still shows Send-disabled rather than Stop,
  `Ctrl`/`Cmd`+`Enter` (DoD-6) and its identical gate, the retry `Button` inside the red `Alert`,
  both `Alert` banners, the root `Stack`'s F1 `flexShrink: 0`, and `ComposerProps`. Mantine's
  disabled-input styling targets the input element and not its sections, so the Stop icon is
  neither dimmed nor blocked while the textarea is disabled mid-stream. `getByRole("textbox")`
  still resolves to exactly one element — an `ActionIcon` is a `button`, and the textarea's own
  role and `aria-label` are untouched

## Skeleton

### Frozen interface (2026-08-07)

**Backend**

- `backend/app/db/chat_messages.py` — `async def count_by_chat_and_role(chat_id: int, role: str) -> int` — new (body `raise NotImplementedError`)
- `backend/app/models/schemas/chats.py` — `class ChatTitleResponse(BaseModel): title: str; changed: bool` — new (declarative DTO, declared above `ChatMessageResponse`)
- `backend/app/services/chat_titling.py` — new module. Every body `raise NotImplementedError`:
  - `_TITLE_TRIGGER_COUNTS: frozenset[int] = frozenset({1, 5})`
  - `_TITLE_MAX_LENGTH = 80`
  - `def _is_titling_trigger(user_message_count: int) -> bool`
  - `def _build_title_transcript(messages: list[ChatMessage]) -> list[LLMMessage]`
  - `def _sanitize_title(raw: str) -> str`
  - `async def maybe_title_chat(access: authz.BookAccess, chat_id: str) -> ChatTitleResponse`
- `backend/app/routes/chats.py` — `@router.post("/{book_id}/chats/{chat_id}/title")` / `async def title_chat(chat_id: str, access: authz.BookAccess = Depends(authz.book_access)) -> ChatTitleResponse` — new, declared last (i.e. after the static `model-options` route, alongside `turn`; DoD-13). Registration verified through the OpenAPI path map.

**Frontend**

- `frontend/src/types/chats.d.ts` — `export interface ChatTitleResponse { title: string; changed: boolean; }` — new
- `frontend/src/api/chats.ts` — `export async function titleChat(bookId: string, chatId: string, signal?: AbortSignal): Promise<ChatTitleResponse>` — new
- `frontend/src/work/chatPaneController.ts` — new module. Bodies throw:
  - `export interface ChatPaneController { openChat: (chatId: string) => void }`
  - `export function registerChatPaneController(c: ChatPaneController): void`
  - `export function unregisterChatPaneController(c: ChatPaneController): void`
  - `export function requestOpenChat(chatId: string): boolean`
- `frontend/src/work/pages/chatsListPageState.ts` — new module. Computeds and effect fns throw; the constructor really calls `makeAutoObservable(this)` so the class is constructible:
  - `export class ChatsListPageState` — `chats: ChatResponse[]`, `chatsStatus: "idle" | "loading" | "ready" | "error"`, `chatsError: string | null`, `showArchived: boolean`, `actionStatus: Record<string, "idle" | "loading" | "error">`, `constructor()`, `get isEmpty(): boolean`, `get visibleChats(): ChatResponse[]`
  - `export async function loadChats(state: ChatsListPageState, bookId: string, signal?: AbortSignal): Promise<void>`
  - `export async function archiveListChat(state: ChatsListPageState, bookId: string, chatId: string, archived: boolean, signal?: AbortSignal): Promise<void>`
- `frontend/src/work/pages/ChatsListPage.tsx` — `export const ChatsListPage = observer(function ChatsListPage() { … })` — new, **no props**; body throws
- `frontend/src/work/components/chat/ChatList.tsx` — `export interface ChatListProps { state: ChatsListPageState; onPick: (chatId: string) => void; onSetArchived: (chatId: string, archived: boolean) => void }` — changed (was `state: ChatPaneState`)
- `frontend/src/work/components/chat/ChatSettingsPanel.tsx` — `export interface ChatSettingsPanelProps { draft: ChatModelSettingsDraft; errors: Record<string, string> }` — changed (was `{ options: ModelOptionResponse[]; draft; errors }`)
- `frontend/src/work/components/chat/chatPaneState.ts` — **additions only**; every 011/013/015/016 export preserved verbatim (D11 / DoD-16):
  - `openedPanel: "model" | "settings" | null = null` — new field on `ChatPaneState`
  - `get settingsDirty(): boolean` — new computed, throws
  - `get modelLabel(): string` — new computed, throws
  - `export async function createChatInstant(state: ChatPaneState, bookId: string, signal?: AbortSignal): Promise<void>` — new, throws
  - `export async function refreshChatTitle(state: ChatPaneState, bookId: string, chatId: string, signal?: AbortSignal): Promise<void>` — new, throws
  - `export async function sendChatTurn(state: ChatPaneState, bookId: string, text: string): Promise<void>` — **signature unchanged, body untouched**; the 023 flush-before-send / `openedPanel`-clear extension is documented on it and left unimplemented
- `frontend/src/work/components/shell/WorkNavigator.tsx` — `export interface WorkNavigatorProps { bookId: string; collapsed?: boolean }` — changed (dropped `onShowChatList: () => void`)

**Deliberately NOT touched (coder's, each behind a `[verify]` DoD):** `navItems.ts`'s
`paneTarget` flip (DoD-10), `routes.tsx`'s `ChatsRedirectRoute` removal / `ChatsListPage`
swap (DoD-11), `WorkspaceShell`'s controller register/unregister inside the existing mount
effect (DoD-15), `MessageList.tsx` and `Composer.tsx` (props unchanged by the plan, so
nothing to freeze).

**Freeze rule applied to wiring:** pure wire mapping with no branching and no computed value
is treated as declaration, not behavior — so `routes/chats.py::title_chat`'s dispatch and
`api/chats.ts::titleChat`'s `request<T>` forwarder are written, following each module's own
documented "skeleton freezes registration/forwarders, the service is UNIMPLEMENTED"
convention from 011. Everything with a decision, a computation or a state transition throws.

- Caller-compile edits (out of Source-files scope): **None.** Every file edited is inside the
  plan's Source areas. The three in-scope caller adjustments forced by the frozen props were:
  `ChatPane.tsx` — dropped the `<ChatList>` render plus its now-dead `handlePick` /
  `handleSetArchived` / `pickChat` / `loadChatMessages` / `setChatArchived` imports (`ChatList`
  no longer accepts `ChatPaneState`), and dropped `options=` from both `<ChatSettingsPanel>`
  call sites; `ChatList.tsx` — dropped the `activeChatId`-derived active marker
  (`ChatsListPageState` has no such field, and the plan drops the marker);
  `WorkNavigator.tsx` — dropped the `paneTarget === "chat"` branch (its only consumer was the
  removed prop); `WorkspaceShell.tsx` — dropped the `onShowChatList={…}` prop it passed.

**Compile gate:** backend imports clean and `POST /api/books/{book_id}/chats/{chat_id}/title`
registers after `model-options` (checked via the OpenAPI path map);
`cd backend && .venv/Scripts/python -m pytest` → 1233 passed;
`cd frontend && npx tsc --noEmit` → clean.

## Tests

### Tests (2026-08-07)

- `backend/tests/services/test_chat_titling.py` (new) — covers DoD-1, DoD-2, DoD-3 —
  trigger boundary at exactly 1 / exactly 5 user messages (counts 2/3/4/6 make no LLM
  call at all), the whole failure taxonomy + blank result swallowed with the title
  intact, and a successful call bound to the chat's own model pair persisting a
  sanitized single-line title.
- `frontend/tests/work/chatPaneSettings.test.ts` (new) — covers DoD-4, DoD-5 — the
  settings-flush ordering at the send seam (dirty → update *then* stream; clean → no
  update; failed flush → no stream + author-facing error), and an accepted send
  clearing `openedPanel` from either panel.
- `frontend/tests/work/Composer.test.tsx` (new) — covers DoD-6 — Ctrl+Enter and
  Cmd+Enter send when sending is allowed, the combination is inert while streaming,
  plain Enter does not send.
- `frontend/tests/work/ChatsListPage.test.tsx` (new) — covers DoD-7 — the page loads
  the routed book's active + archived sets (client-side `showArchived` filter,
  most-recent-first), a row pick reaches the registered controller with no route
  change, archive/restore round-trips.
- `frontend/tests/work/WorkspaceShell.test.tsx` (retargeted) — covers DoD-7 (the
  controller half, from the outside: `requestOpenChat` is answered while the shell is
  mounted and the pane's active chat becomes the requested one). Its four 010 cases
  (DoD-4…DoD-7) are preserved verbatim; only the `api/chats` module factory grew
  `streamChatTurn` / `titleChat`.
- `frontend/tests/work/ChatPane.test.tsx` (retargeted) — covers DoD-8 (the pane
  renders no chat list — only the active chat) and DoD-9 (instant create: inherits the
  active chat's pair, falls back to `modelOptions[0]`, refuses with an author-facing
  message when there are none). Every still-valid 011 case is preserved under its
  original 011 DoD id; the three cases asserting the pane-hosted list / the dropped
  `ChatSettingsPanel options` prop are removed as invalidated by design (D12).
- `frontend/tests/work/WorkNavigator.test.tsx` (retargeted) — covers DoD-8 — all seven
  entries are content-pane links in UC-090 order with their hrefs, and Chats now
  navigates to `/:bookId/chats`.
- `frontend/tests/work/chatsNavigatorEntry.test.tsx` (retargeted) — covers DoD-8 —
  clicking Chats moves the route; `/bk-1/chats` renders the list page in `main` without
  redirecting; the pane (`complementary`) shows only the active chat.
- `frontend/tests/work/subjectRoutes.test.tsx` (retargeted) — covers DoD-8 — the
  `/chats` deep link renders the list page in the content pane instead of redirecting.
  Every other route case in the file is untouched.
- `frontend/tests/work/WorkNavigatorRail.test.tsx` (retargeted, authorized 2026-08-07 as
  D12's category) — the removed `onShowChatList` prop is dropped at its render call
  sites (DoD-22), and the entry-set expectations invalidated by DoD-8 are retargeted:
  six links → seven, and its DoD-10 case now asserts that collapsed, Chats is a link to
  `/:bookId/chats` (and no `button` named Chats survives) instead of a control invoking
  `onShowChatList`. fast/005's own rail behaviour — accessible-name reachability while
  collapsed, href parity between modes, `classNames` wiring — is preserved unchanged.
  **No new coverage added.**
- `frontend/tests/work/chatStreaming.test.ts`, `frontend/tests/work/ChatConversation.test.tsx`
  (mock completeness only, authorized 2026-08-07) — `titleChat` added to their
  `src/api/chats` module factories so the fire-and-forget post-turn refresh has
  something to call; `chatStreaming`'s `beforeEach` arms it with a benign
  `{title, changed: false}` so a `done` frame cannot leave a rejected promise behind.
  **No assertions added or changed; neither spec is sensitive to the refresh's timing.**

- Coverage: DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓,
  DoD-9 ✓, DoD-10…DoD-16 [verify, no test], DoD-17…DoD-22 [manual/live, no test]
- Deliberately not tested (per plan `## Test plan`): 6 items — message bubble /
  divider / role-label styling, popover open/close rendering, `count_by_chat_and_role`
  in isolation, the titling api forwarder + DTO, the titling prompt wording, the
  `chatPaneController` registry in isolation.

### Notes from the test-coder (2026-08-07)

- **DoD-5, half of it is structural — no test, by agreement.** `openedPanel` is a single
  discriminator that can hold at most one panel by construction (design-note D7:
  "opening one closes the other **by construction**"), and the plan puts the toggle
  inline in `ChatPane`'s JSX while listing popover render wiring as deliberately not
  tested. The "opening one closes the other" clause therefore has no non-tautological
  assertion; `chatPaneSettings.test.ts` covers the clear-on-send clause for both panels
  and documents the reasoning in its header. The coordinator routed the exclusivity half
  to the **verifier as an inspection item** (2026-08-07).
- **Three delivered specs beyond D12's named five were invalidated by the frozen
  contract** and were repaired in a follow-up round (2026-08-07), all listed above:
  `WorkNavigatorRail.test.tsx` (retargeted to DoD-8's link contract),
  `chatStreaming.test.ts` and `ChatConversation.test.tsx` (`titleChat` mock
  completeness). Selectivity is unchanged: still exactly the nine `[test]` items.

## Notes & Issues

### Skeleton (2026-08-07) — `LLMMessage` import path resolved

`plan.md` → Risks flagged `from llm import LLMMessage` as unverified, and it is **wrong**:
the installed `llm` package's `__init__.py` re-exports only `LLMError` / `LLMClient` /
`OllamaAPIClient` / `OpenAIAPIClient` / `LlamaSwapAPIClient` / `get_llm_client` /
`substitute_placeholders` / `pydantic_to_openai_tool` / `LLMTracer`. `LLMMessage` is a
`TypedDict` (`role: str`, `content: str`) declared in `llm/message.py`, so the verified
import used by `services/chat_titling.py` is:

```python
from llm.message import LLMMessage
```

`LLMClient.chat(messages: List[LLMMessage], *, system=None, options=None, stream=False,
on_delta=None) -> str` is confirmed as described in `context.md`. Same-file import fix, no
frozen signature affected.

### Skeleton (2026-08-07) — one out-of-scope test file breaks on the frozen props

Dropping `onShowChatList` from `WorkNavigatorProps` breaks **four** test files under
`npm run test:types`, but the plan's Test files list names only three of them:

- `frontend/tests/work/ChatPane.test.tsx` — in scope (passes `options` to `ChatSettingsPanel`)
- `frontend/tests/work/chatsNavigatorEntry.test.tsx` — in scope
- `frontend/tests/work/WorkNavigator.test.tsx` — in scope
- **`frontend/tests/work/WorkNavigatorRail.test.tsx` — NOT in the plan's Test files list**, and
  not among D12's five invalidated specs. It renders `<WorkNavigator bookId=… onShowChatList=…>`
  at eight call sites (fast/005's rail spec).

The skeleton does not touch test files, so DoD-22 (`npm run test:types` clean) cannot go green
until someone deletes that dead prop from `WorkNavigatorRail.test.tsx`. The edit is mechanical
(remove the `onShowChatList={…}` prop and its `vi.fn()`; the spec asserts nothing about it), but
it needs an owner: either add the file to the plan's Test files so the test-coder handles it, or
route it as a one-line fix. Flagged rather than done — it is a Test file, and the air gap holds.

### Coder (2026-08-08) — the pane controller also loads the opened chat's messages

`plan.md` sketches the shell's controller as `{ openChat: (chatId) => pickChat(chatPaneState,
bookId, chatId) }`. `pickChat` only moves the active-chat pointer; it does **not** fetch the
transcript (in 011 the pane's own row handler called `pickChat` **and** `loadChatMessages`, and
that handler is exactly what 023 deleted). Taken literally, picking a row on the list page would
swap the pane's title and settings while still rendering the previous chat's conversation. The
controller therefore calls `pickChat` and then fires `loadChatMessages` — the same pair 011's
handler used, no new function and no new behaviour. Flagged because the plan's Interface line
names only the first call.

### Coder (2026-08-08) — `saveChatSettings` resolves an unmatched `optionKey` to an EMPTY pair

011's `saveChatSettings` builds its `UpdateChatRequest` pair from
`modelOptions.find(o => modelOptionKey(o) === settingsDraft.optionKey)`, falling back to
`llm_server_id: null, model_name: null` when nothing matches — i.e. a save from a draft whose
option is not in the loaded list silently CLEARS the chat's model pair. Harmless while the only
caller was an explicit "Save settings" button on a fully-seeded pane; it became the amplifier for
the round-1 defect once the send seam started calling it. Fixed at the `settingsDirty` gate (an
unseeded draft is never flushed) rather than inside `saveChatSettings`, which the plan says to
reuse **as-is** and whose behaviour DoD-4 clause 3 depends on. Worth hardening in a later feature —
an unresolvable `optionKey` arguably ought to leave the stored pair alone rather than null it.

### Coder (2026-08-08) — `ChatPaneState.errors` still validates the NEW-CHAT draft's temperature

`get errors()` (011) derives its `temperature` message from `newChatDraft.temperature`, but its
only remaining consumer is the settings popover, which edits `settingsDraft`. So an out-of-range
temperature typed into the popover shows no message, and the untouched new-chat draft can in
principle show one that belongs to no visible control. Pre-existing, unrelated to any DoD item,
and touching it would change 011 behaviour this feature is not asked to change — recorded, not
fixed.

### Coder (2026-08-08) — an archived chat opened from the list page shows nothing in the pane

`loadChatPane` loads only NON-archived chats into `ChatPaneState.chats`, while the list page loads
both sets. Picking a row in the archived view therefore points `activeChatId` at a chat the pane
has no row for, so `activeChat` stays `null` and the pane renders no conversation. No DoD item
covers it (the archived view exists to restore, per UC-082 / US-096), so it is left as-is rather
than widened into a pane-side refetch.
