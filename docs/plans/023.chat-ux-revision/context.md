# Context — 023.chat-ux-revision

Feature-wide facts for a build session with no conversation history. Distilled from
`docs/.cache/ultra/023.chat-ux-revision/harvest.md` and `design-notes.md` (both still on disk,
read them for full detail) plus the architecture docs. Do not re-derive decisions from here —
`plan.md` → Decisions taken is authoritative for the *why*; this file is the *what already exists*.

## What this feature revises

Delivered `011.chat-panel` (`docs/plans/011.chat-panel/status.md`, all steps `done`). This feature
reshapes the chat pane and adds one backend endpoint. It does **not** touch the turn/streaming
path (`chat_turn.py`, `POST .../turn`) except by calling existing exports.

## Backend ground truth

- 4-layer separation is enforced: `routes → services/db → models`. No `session`/`select()` outside
  `db/`. Namespace imports (`from app.db import chat_messages`, `from app.services import chats as
  chats_service`).
- `services/chats.py` (not a Source file this feature touches, but freely called): `_resolve_owned_chat(access, chat_id: int) -> Chat`
  (404-not-403 ownership gate), `_parse_chat_id(chat_id: str) -> int`, `ChatError`/`ChatErrorReason`.
  `chat_turn.py`'s `prepare_turn` already reuses these privates by precedent — the new
  `chat_titling.py` does the same.
- `db/chats.py::update(row: Chat) -> Chat` persists changed columns and bumps `modified_at` itself —
  the titler just mutates `chat.title` and calls this.
- `db/chat_messages.py` has `create`, `get_by_id`, `list_by_chat`, `list_by_chat_ordered` (position
  asc), `next_position`. **No count function exists** — this feature adds the first one.
- `Chat.title: str` is non-nullable; default `"New chat"` is a service-level literal
  (`services/chats.py:218`), not a column default. `Chat.llm_server_id: int | None`,
  `Chat.model_name: str | None` — the model pair, mirrors `SubAgent`. **No column records "titling
  already ran"** — trigger is derived from a live count each call (D3).
- `_TURN_FAILURE_EXCEPTIONS` in `chat_turn.py` = `(aiohttp.ClientError, LLMError, ValueError,
  RuntimeError)`. The titler defines its **own** identical tuple locally rather than importing
  `chat_turn`'s private constant — same taxonomy, no new cross-service private coupling.
- Non-streaming LLM precedent is `services/embedding.py`: resolve server → `secrets.resolve_env_ref`
  → `llm_servers.create_model_client(server, resolved_key, model)` entered `async with` → call →
  catch the four exception types → typed outcome. The titler follows the same shape but swallows
  rather than re-raising (mirrors `_finalize_close_turn_if_needed`'s swallow-and-log, not
  `embedding.py`'s re-raise).
- `llm.LLMClient.chat(messages: List[LLMMessage], *, system=None, options=None, stream=False,
  on_delta=None) -> str` — never called anywhere in `backend/app` today; this is the first call
  site. `LLMError` and `LLMClient` are already imported directly from the `llm` package elsewhere in
  this codebase (`from llm import LLMError`, per `chat_turn.py`'s `_TURN_FAILURE_EXCEPTIONS`) — the
  new transcript-builder helper's `LLMMessage` import is expected to follow the same top-level form
  (`from llm import LLMMessage`); the harvest does not show the literal import line, so **confirm
  against source before filling the body** — a wrong import path is a same-file fix, not a
  frozen-signature break (see Risks in `plan.md`).
- Route ordering rule (existing, followed by `turn`): a static path segment (`model-options`) must
  be declared before `{chat_id}`-parameterised routes so FastAPI doesn't swallow it as a chat id.
  The new `title` route sits alongside `turn`, after `model-options`.
- `backend/tests/services/test_chat_turn.py`'s `_FakeClient` is an async-context-manager stand-in
  for `llm.LLMClient` implementing **only `chat_with_tools`**. A titling test needs `.chat()` on a
  fake — either extend `_FakeClient` or add a sibling fake in the new titling test file. The
  patch seam is `app.services.llm_servers.create_model_client`, monkeypatched with `raising=False`
  also at `app.services.chat_titling.create_model_client` in case of a direct import (the belt-and-
  suspenders idiom `_install_client` already uses for `chat_turn`).
- **No `Chat`/`ChatMessage` column is added.** `services/db_import_export.py`'s chat codecs are
  untouched — D3 chose derive-from-count precisely to avoid that obligation.

## Frontend ground truth

- MobX hard rules (`frontend.md`): every component `observer`; state = data + `get` computeds, no
  effectful methods; loads/saves are external `(state, args, signal)` functions using
  `runInAction`; `useState` only to hold a stable state instance; `useEffect` only at page level;
  no context, no custom hooks, no `useCallback`/`useMemo`/`useReducer`; async resources are always
  the `data`/`dataStatus`/`dataError` trio.
- **Module-registry idiom, twice already shipped**: `closeTurnController` (register/unregister a
  `CloseTurnController`-shaped object; `ChatPaneState` implements it directly with `start`/`stop`/
  `setActive`) and `contentSubject`/`turnSubject` (canvas target registry). `chatPaneController.ts`
  is a third instance: register/unregister a small object, `requestOpenChat` returns whether a
  registered controller handled the id. `WorkspaceShell` already registers/unregisters
  `chatPaneState` as the `CloseTurnController` inside its **one** mount effect — the new controller
  is registered/unregistered in that same effect, no second effect.
- `CodexListPage`/`codexListPageState.ts` is the list-page template: page reads `useParams` +
  `useNavigate` + `useSearchParams`; state via `useState(() => new XState(...))`; one page-level
  mount `useEffect` (register + load, cleanup unregisters + aborts); row click navigates via
  `navigate(...)`. **`ChatsListPage` deliberately does not navigate on row click** — D5 chose the
  controller precisely so the pane opens the chat without a route change, so the page's row-click
  handler calls `requestOpenChat` only.
- `Popover`: **zero usages anywhere in `frontend/src/`** before this feature. `Menu` is the only
  existing dropdown (`AdminUserMenu.tsx`, `Menu.Target`/`Menu.Dropdown`/`Menu.Item`) — not a
  template for this feature since a `NumberInput` doesn't fit `Menu.Item`. This feature is the
  first `Popover` call site; there is no in-repo idiom to copy for its open/close wiring, so
  `openedPanel` is that wiring (see D7 in `plan.md`).
- Keyboard handling: **one `onKeyDown` in the whole frontend**, `ChatResizeHandle.tsx:51-63`
  (`ArrowLeft`/`ArrowRight`, `event.preventDefault()` per branch). That is the only local idiom for
  the Composer's new `Ctrl`/`Cmd`+`Enter` handler to follow.
- `chatPaneState.ts`'s existing exported surface (interfaces `ChatModelSettingsDraft`,
  `NewChatDraft`, `RenderedMessage`; consts `DEFAULT_TEMPERATURE`/`MIN_TEMPERATURE`/
  `MAX_TEMPERATURE`; `modelOptionKey`; class `ChatPaneState` incl. every field/computed listed in
  the harvest; effect fns `loadChatPane`, `pickChat`, `createChatFromDraft`, `setChatArchived`,
  `saveChatSettings`, `loadChatMessages`, `sendChatTurn`, `retryChatTurn`, `stopChatTurn`,
  `startCloseTurn`, `stopCloseTurn`) is **preserved verbatim** — this feature only adds members.
  Some (e.g. `newChatDraft`, `NewChatDraft`, `createChatFromDraft`, `chats`/`chatsStatus`/
  `chatsError`, `visibleChats`) stop being wired to pane JSX (the list/new-chat form leave the
  pane) but remain exported and functional; nothing here is deleted. **`CloseTurnController`
  members (`start`/`stop`/`setActive`, `closeTurnActive`), `isComposerReadOnly`/
  `composerReadOnlyReason`, `startCloseTurn`/`stopCloseTurn`, the `onCanvas` handler, `turnSubject()`
  and `currentContentSelection()` are the features-013/015/016 surface that must survive
  unchanged** (design-note D11) — touch nothing in that list beyond what the Interface section
  names.
- `saveChatSettings(state, bookId, signal?)` already builds an `UpdateChatRequest` from
  `state.activeChat` + `state.settingsDraft` (temperature overridden, every other sampling field
  carried through), persists via `chatsApi.updateChat`, and sets `serverErrors.form` /
  `settingsStatus="error"` on `ApiError`. `sendChatTurn`'s new pre-flush step **reuses this
  function as-is** rather than adding a new effect fn.
- `streamChatTurn`'s `TurnStreamHandlers.onDone` carries **no payload** (frozen since 011) —
  `finishTurn` (module-private) is the only place that knows a turn just completed successfully;
  the title refresh is fired from there.
- Harness-mock sweep (frontend tests): every spec that mounts `WorkRoutes`/`WorkspaceShell` mocks
  `src/api/chats` (module-factory form, all exports) because the shell's mount effect always starts
  a chat load. `ChatsListPage` renders inside that same shell via `<Outlet/>`, so any spec mounting
  `/bk-1/chats` needs the same `api/chats` + `api/books` mocks as the other subject-route specs.
- `frontend/tsconfig.json` covers `src` only; `npm run build` never typechecks `tests/`.
  `npm run test:types` is the only command that does.

## Product-layer note

`docs/product/` ids `US-095.AC-1`, `US-105.AC-3`, `UC-081` step 1 describe the pane-hosted list this
feature removes. The code is deliberately ahead of the docs as of this feature — see `plan.md` →
Decisions taken (D1) and `outcome.md` item 1 for the reconciliation obligation this feature does
**not** discharge.
