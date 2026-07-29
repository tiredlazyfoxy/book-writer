# Frontend Architecture

React SPAs plus a standalone Login page, built with **TypeScript + React + MobX + Mantine** and bundled by Vite as a multi-page app. Each SPA has its own entry point but shares conventions, the state model, the API layer, and the folder layout. This document is self-contained: it holds the full set of enforced frontend rules, and they bind every entry.

**Book-domain surfaces are in `frontend-workspace.md`** — the five-entry map (Shell, Working page, Reader, Admin, Login), the per-entry route map, and the working page's navigator / content pane / chat pane. Its **draft tier** — the restore buffer, the module-state modules beside it, the canvas target registry and reconciliation — is in **`frontend-work-drafts.md`**. This document keeps the rules; those two apply them to the book domain. The **server side** of the assistant the chat pane talks to — prompt composition, the tool/agent loop, and the SSE frame vocabulary — is in `assistant-runtime.md`.

## Stack and versions

| Concern | Choice |
|---------|--------|
| Language | TypeScript 5.8 (strict) |
| Framework | React 19.1 |
| Bundler | Vite 6.3 + `@vitejs/plugin-react` (multi-page, `appType:"mpa"`) |
| UI | Mantine v7.17 (`@mantine/core`, `@mantine/form`, `@mantine/hooks`) + `@tabler/icons-react` + `react-markdown` |
| State | MobX 6.13 + `mobx-react-lite` — **only** |
| Routing | react-router-dom 7 |

No Redux, Zustand, React-Query, React-Context, zod, Tailwind, CSS modules, or styled-components.

## `tsconfig.json` flags

Strict mode with the extra safety flags on:

- `strict: true`, `noUnusedLocals: true`, `noUnusedParameters: true`, `noFallthroughCasesInSwitch: true`
- `noEmit: true` (Vite owns emit; `tsc` is typecheck-only, preventing stray `.js` siblings next to `.tsx`)
- `moduleResolution: "bundler"`, `jsx: "react-jsx"`, `target: "ES2022"`

## `vite.config.ts` shape

A multi-page build with a dev proxy. **Five inputs** — `work` and `read` joined `user` / `admin` / `login` with feature 010, and `spaFallback` branches `/work` and `/read` before its catch-all. See `frontend-workspace.md` for why the workspace and the reader get their own bundles.

```ts
export default defineConfig({
  appType: 'mpa',
  plugins: [react(), spaFallback()], // spaFallback: custom dev plugin, see below
  build: {
    rollupOptions: {
      input: {
        user:  resolve(__dirname, 'index.html'),        // Shell SPA at /
        work:  resolve(__dirname, 'work/index.html'),   // Working page SPA at /work
        read:  resolve(__dirname, 'read/index.html'),   // Reader entry at /read
        admin: resolve(__dirname, 'admin/index.html'),  // Admin SPA at /admin
        login: resolve(__dirname, 'login/index.html'),  // Login at /login
      },
    },
  },
  server: {
    port: 8194,
    proxy: { '/api': 'http://localhost:8185' },
  },
});
```

- `appType: "mpa"` disables Vite's built-in single-page history fallback; a custom **`spaFallback`** dev plugin rewrites deep links back to the right entry `index.html` so client-side routes resolve in dev. It branches `/work` and `/read` **before** its catch-all `else`, which is what makes `/work/:bookId/...` deep links resolve rather than falling through to the Shell entry.
- `/api` is proxied to the backend on `:8185` in dev.

## npm scripts

```json
"scripts": {
  "dev": "vite --port 8194",
  "build": "tsc && vite build",
  "preview": "vite preview"
}
```

`npm run build` typechecks (`tsc`) then bundles (`vite build`); treat it as the typecheck-and-bundle command. `npx tsc --noEmit` is typecheck-only. The test scripts (`test`, `test:watch`, `test:types`) were added alongside Vitest — see "Testing" below and the root `CLAUDE.md`, which owns the command list.

## Theming

- Styling is Mantine's built-in system plus a single `global.css` and a `theme.ts`.
- `theme.ts` calls `createTheme()` with a **custom primary palette** and a **custom dark scale**.
- **Dark is the default color scheme** — the app mounts with `defaultColorScheme="dark"` on the `MantineProvider`.
- No Tailwind, no CSS modules, no styled-components.

## Folder layout

The build has five entries: `login/` (separate entry, outside React Router), `user/` (Shell SPA), `admin/` (Admin SPA), `work/` (working page SPA) and `read/` (reader). Each SPA owns its `pages/` and `components/`; `api/`, `types/`, `utils/`, `components/` (cross-SPA shells), `theme.ts`, and `auth.ts` are shared at `src/` root. See `frontend-workspace.md` for the entry-by-entry route map.

```
frontend/
  index.html              # User SPA entry
  admin/index.html        # Admin SPA entry
  login/index.html        # Login entry
  theme.ts                # createTheme() — custom primary + dark scale
  global.css
  src/
    api/                  # HTTP layer — flat, one file per resource
      client.ts           # fetch wrapper: Bearer auth, ApiError normalization, AbortSignal
      sse.ts              # streamPost() — SSE frame reader (not EventSource)
      <resource>.ts       # one per backend resource
    types/                # full API surface — DTOs only, flat (.d.ts)
      <resource>.d.ts
    utils/                # shared helpers (formatDate, ...)
    components/           # cross-SPA shells: AppLayout, AppHeader, AppSidebar
    auth.ts              # current user / token — module-level state, not a class
    user/                 # User SPA
      main.tsx, App.tsx, routes.tsx
      pages/              # flat: page component + adjacent state file
      components/         # grouped by area
    admin/                # Admin SPA — same shape as user/
    login/                # Login entry — main.tsx, Login.tsx (no router, no page state)
    work/                 # Working page SPA
      main.tsx, App.tsx, routes.tsx
      workGate.ts         # auth-only entry gate, run before createRoot
      subject.ts          # the content-pane subject model + editability table
      restoreBuffer.ts    # device-local draft buffer   ─┐
      activeChat.ts       # per-book active-chat pointer  ├─ module tier
      contentSubject.ts   # canvas target registry       ─┘
      pages/              # flat: page component + adjacent state file
      components/shell/   # navigator, workspace shell, chat-pane slot
      components/chat/    # the chat pane (feature 011)
    read/                 # Reader entry — main.tsx, App.tsx (STUB, see below)
```

**`src/work/` is real** as of feature 010, and its three root modules (`restoreBuffer.ts`, `activeChat.ts`, `contentSubject.ts` — the last two added by features 011 and 013) form a state tier of their own, documented in `frontend-work-drafts.md`.

**`src/read/` is real but the `read` entry is a stub.** What shipped with feature 010 is a table-of-contents placeholder: a Mantine-themed component with **no router and no gate**, mounted by a `main.tsx` that mirrors `login/`'s. The reader's real build is still out (`frontend-workspace.md` → Reader). The stub's shallowness is scaffolding for a designed surface, not the designed surface.

**Scaffold scope (feature 002).** The layout above is the target. What the scaffold actually ships today: the **Login entry is a bare placeholder** ("Login (coming soon)" — real login is feature 004); the cross-SPA **`AppLayout` / `AppHeader` / `AppSidebar` shells are not yet built** — `src/components/` is a seeded-empty folder (`.gitkeep`); routing beyond the User **health page** and an **Admin placeholder** is deferred. The seams (empty `components/`, placeholder entries) are intentional, not missing work.

**Admin SPA — LLM servers section (feature 006).** The Admin SPA has grown its **second section** at `/admin/llm-servers`: a list page (`admin/pages/LlmServersPage.tsx` + `llmServersPageState.ts`) plus **three modals** under `admin/components/llm-servers/` — a server form (create/edit), a models modal (probe available models + enable a subset), and an embedding-designation modal. It is backed by the `api/llmServers.ts` resource module and `types/llmServers.d.ts` (which includes the `"llama-swap" | "openai"` backend-type union). `LlmServer.id` is typed **`string`**, per the string-id convention (see "types/" below). Adding this section realized the minimal **`Users | LLM Servers`** nav that feature 005 deferred "until 006 adds pages" — still under the **minimal local Admin layout**; the shared cross-SPA `AppLayout` / `AppHeader` / `AppSidebar` shells remain deferred.

**Admin SPA — Database section (feature 007).** The Admin SPA grew a **third section** at `/admin/database`: `admin/pages/DatabasePage.tsx` + `databasePageState.ts` (a report async trio plus external `(state, …, signal)` action functions), rendering a per-table consistency table (an ok / drift / missing badge, the drift column lists, and per-row **Create** / **Sync** actions) plus **Export** / **Import** / **Rebuild** controls. Nav is now **`Users | LLM Servers | Database`**, still under the minimal local Admin layout (the shared `AppLayout` / `AppHeader` / `AppSidebar` shells remain deferred). It is backed by `api/db.ts` and `types/db.d.ts`.

**Admin SPA — Assistant configuration (feature 012).** The Admin SPA grew **two more flat sections**, `/admin/assistant-modes` and `/admin/sub-agents`, backed by `api/assistantConfig.ts` and `types/assistantConfig.d.ts`:

- `admin/pages/AssistantModesPage.tsx` + `assistantModesPageState.ts` — the repo's **first three-trio page state** (modes, tools and sub-agents load together in one `Promise.all`, and all three trios move as a unit into `ready` or `error`; the page renders the first non-null error and `modesStatus` is what suppresses the table). It is not an aggregation type — it is three trios, per the rule below.
- `admin/components/assistant-config/` — `ModeEditorModal.tsx` + `modeEditorDraft.ts`, the mode editor.
- `admin/pages/SubAgentsPage.tsx` + `subAgentsPageState.ts` (four trios — the three above plus LLM servers, needed to label model assignments) and `admin/components/sub-agents/` — `SubAgentFormModal.tsx` + `subAgentFormDraft.ts`.
- Nav is now **`Users | LLM Servers | Database | Assistant Modes | Sub-agents`**, still under the minimal local Admin layout; the shared `AppLayout` / `AppHeader` / `AppSidebar` shells remain deferred.

The Mantine inventory grew with it: the mode editor introduces the repo's **first `<Textarea>`**, and the first use of the **`ScrollArea.Autosize` + `Checkbox` multi-select idiom** outside `components/llm-servers/ModelsModal.tsx`. Both editors reuse that idiom for tool and mode/sub-agent pickers rather than reaching for a new component, because a checkbox list inside a bounded scroll area is already the repo's answer to "pick a subset of a catalogue whose size is unknown."

## MobX hard rules

These rules work as a system; loosening one breaks the others.

### State library

- **MobX, only.** No Redux, Zustand, React-Query, React-Context.
- `enforceActions: 'always'` is **off** — direct two-way binding (`state.field = value`) is legitimate and common; `runInAction` is used only for multi-field atomic mutations.

### Observer everywhere

- **Every component is wrapped in `observer`** (from `mobx-react-lite`). No exceptions — not "leaf only," not "container only." A missing `observer` is a code-review failure (it produces silent staleness, not a loud error).

### The state ladder

Three layers, each with a clear lifetime:

| Layer | Where | Lifetime | Holds |
|-------|-------|----------|-------|
| Module-level globals | `src/auth.ts`, `src/utils/*` | app boot → unload | Auth token + current user, global settings — **plain module state, not a class, not a store** |
| `<Page>State` | `pages/<page>PageState.ts` | page mount → unmount | Loaded data, drafts, modes, pagination, status flags |
| `<Component>State` | inline or sibling file | component mount → unmount | Local UI state too noisy to lift |

Globals are plain functions (`getToken()`), not reactive stores — auth changes navigate away; settings changes re-read on next use.

**Auth seam (scaffold vs. target).** The row above states the *target*: `auth.ts` will hold both token and current user. The current scaffold (feature 002) ships a **subset** — `auth.ts` exposes only `getToken()` (a localStorage read) plus a minimal `logout()` stub. `getCurrentUser()` / JWT-decode and the `App.tsx` token-gate redirect are **deferred to feature 004**, which expands `auth.ts` and adds the token gate. This is recorded so 004 is read as an expansion, not a rewrite.

### State is data + computed, never effectful methods

A state object holds **observable fields** and **pure `get` computed derivations** (validation, `isDirty`, `isValid`, `canSubmit`, filtered/sorted views). It is **not** a class with `load()` / `save()` / `delete()` or any method that calls an API.

### Effectful operations are external functions

All loads, saves, deletes — anything touching the network — are **top-level functions** in the same file as the page state, taking `(state, args, signal)` and writing via `runInAction`:

```ts
export async function loadItems(state: ItemsPageState, signal: AbortSignal): Promise<void> {
  state.itemsStatus = 'loading';
  state.itemsError = null;
  try {
    const items = await itemsApi.list(signal);
    runInAction(() => { state.items = items; state.itemsStatus = 'ready'; });
  } catch (err) {
    if (signal.aborted) return;
    runInAction(() => { state.itemsStatus = 'error'; state.itemsError = String(err); });
  }
}
```

### Async resource trio

Every loadable resource is a triple — no wrapper type, no booleans:

```ts
items: Item[];
itemsStatus: 'idle' | 'loading' | 'ready' | 'error';
itemsError: string | null;
```

No `AsyncValue<T>`, no `isLoading`. Naming is `<name>` / `<name>Status` / `<name>Error`. A page with three loadables has three trios; there is no aggregation type.

### Mutation rules

- Trivial single-field assignment from a component is fine (`state.search = e.target.value`).
- Multi-field mutations wrap in `runInAction` to fire observers once.
- State exposes **derivations, not setters** — a `get filteredCount`, never a `setFilteredCount`.

### React hook rules

- **`useState`** only to own a stable instance: `const [state] = useState(() => new ItemsPageState())`. Never for reactive data.
- **`useEffect`** only at the page-component level, only for initial load on mount and cleanup/abort on unmount. Empty deps `[]` is the only deps array you should write — pages remount on path-param change via router `key`. Forbidden in leaf components, for derivations, and for prop-watching.
- **No `useCallback` / `useMemo`** for stability — `observer` re-renders are already scoped.
- **No `useReducer`.**
- **No custom `useX` hooks.** Reusable stateful UI is a wrapper component owning a `<Component>State` class instance; page state is `<Page>State`; extracted effectful logic is an external `(state, args, signal)` function.
- For rare imperative side-effects on observable change (e.g. auto-scroll while streaming), use a single `autorun` started in the mount `useEffect` and disposed on cleanup.

### Routes and pages

- **A page owns the browser route** — one route = one page = one fresh state instance per navigation.
- **Path-param changes force a remount** via React Router `key={id}`; the same mount `useEffect` handles the new load.
- **Each page loads its own data by URL id** — no warm start from a parent's data; every page is deep-linkable.
- **No upward callbacks across pages.** Save → API → done; returning to a parent route remounts and refetches. The backend is the only cross-page source of truth.
- **URL query params are the persistence layer** for filter, sort, mode, scroll-anchor — anything that should survive navigation, refresh, or bookmark. Query-param changes are handled in the event handler that changed them, never by a `useEffect` watching the query string.

**The mechanism — the returned-search-string convention (feature 013).** The rule above says *where* the URL write happens but named no mechanism, and the enforced MobX split makes the obvious one illegal: an external effect function **cannot call `setSearchParams`**, which is a React hook binding owned by the component. The seam, first built for the codex list's search needle:

> the effect function **returns the new search string** — `"q=…"`, or `""` to drop the param — and the **submit handler pushes it** with `setSearchParams(...)`.

The commit-and-reload therefore stays in the state layer and the URL write stays in the event handler, with neither reaching into the other. The initial read is done **once**, inside the `useState(() => new …State(searchParams.get("q") ?? ""))` initializer, so a deep link filters the first fetch and nothing watches the query string afterwards. Copy this rather than reaching for a hook inside a state module.

**Persisted-state exception — the working page's restore buffer.** The rule above is about *view* state: small, shareable, and correct to put in a bookmarkable link. Unsaved **draft content** (UC-092, US-107) is none of those — it is large, private to one author on one device, and must not travel in a URL. It therefore lives in **`localStorage`, keyed per item**, in **`src/work/restoreBuffer.ts`** — plain module-level functions in the `work` entry, in the same tier of the state ladder as `auth.ts` (which already reads `localStorage` for the token). Feature 010 shipped it as a **pure module with no editable subject wired to it**; feature 013's codex entry page is its first writer. It is a deliberate exception, not a general licence to persist state outside the URL; its full design — key shape, quota eviction, the stale-version reconciliation it feeds, and the two sibling modules that joined it — is in **`frontend-work-drafts.md`**.

### Components

- Pure props, no React context — stores and slices are passed explicitly down the tree.
- Generic components (Button, Modal, Input) take primitives + callbacks, no domain knowledge.
- Page-aware components take state slices.
- Page-specific orchestration and handlers are inner functions inside the component, closing over `state` and props — not extracted "to keep the component small."
- A growing component is split into smaller `observer` subcomponents, each owning its JSX slice and inner handlers; state stays in the page.

**Worked example — a shell owns one state instance and shares it with a child (feature 011).** The chat pane needs the same state from two places: the pane itself, and the navigator entry that reveals it. The shipped shape, which is what "pass stores and slices explicitly, one owner" looks like in practice:

- `WorkspaceShell` **owns** the single `ChatPaneState` (`useState(() => new ChatPaneState(…))`) and starts its load inside the **existing** mount `useEffect` — no second effect was added.
- It passes **the instance** down to `ChatPane` (through `ChatPaneSlot`), and passes `WorkNavigator` a **zero-arg `onShowChatList` handler** rather than the state — the navigator needs to trigger, not to read.
- **No React context.** The slice travels explicitly down the tree, which is why there is exactly one owner and the ownership is visible at the call site.
- `ChatPane` holds only an **ephemeral `useState` boolean** for its new-chat form (the `BookshelfPage` `createOpen` precedent) and runs **no effect** — a child that receives a state instance does not also acquire a lifecycle.

### Forms

- Drafts live in page state (modal-dialog drafts may live in component-local state).
- Validation is `get` computed derivations (`errors`, `isValid`, `isDirty`, `canSubmit`) — pure functions of observable fields.
- Server-side field errors are stored separately (e.g. `serverErrors`) and unioned with client errors in the `errors` getter.
- **The union is the shape *when client validation exists* (feature 021).** Some fields have no client-side rules at all — the per-author system-prompt editor accepts every string, `""` included — and such a form carries only its server-error map (`systemPromptServerErrors`), with **no `clientErrors` and no `errors` union**. The server-error surface is then the only error surface. Do not manufacture an empty `clientErrors` and a pass-through `errors` getter to satisfy the pattern; a field with no client rules **binds the server-error map directly**.
- **Do not use Mantine `useForm`.** The draft-in-state + computed-validation model is the form system.

## API layer

All HTTP lives in `src/api/`. Direct `fetch()` outside `client.ts` (and `sse.ts`) is a code-review failure.

**Blob-download / multipart-upload exception (feature 007).** `api/db.ts` introduces the frontend's **first blob-download and multipart-upload** helpers, and both **bypass `request<T>`** — which is JSON-only. `exportDatabase()` does a Bearer `fetch` and reads `res.blob()` to trigger a browser save of the archive; `importDatabase(file)` posts a `FormData` field `file` with **no JSON `Content-Type`** (the browser sets the multipart boundary), mirroring 003's `api/auth.ts::setupImport`. Both still read the Bearer token from `auth.ts` `getToken()`. These are **sanctioned exceptions** to "all HTTP goes through `request<T>`," in the same spirit as `sse.ts` — the wrapper handles only JSON, so non-JSON transfers live in their own resource helpers.

### `client.ts`

A single `request<T>()` wrapper is responsible for:

- Passing the `url` straight to `fetch` (resource modules supply absolute `/api/...` paths, typically via a per-module `BASE`).
- **Bearer auth** — reads the JWT from `auth.ts` (`getToken()`) and sets `Authorization: Bearer <token>`.
- **JSON parsing** on success; `204` returns `undefined`.
- **Error normalization** — non-2xx becomes a typed `ApiError(status, message, details?)`.
- **AbortSignal pass-through** — every request accepts an optional `signal` and forwards it.

Dependency direction is one-way: `api/` imports from `auth.ts`; `auth.ts` never imports from `api/`; pages/components import from `api/`.

### `api/<resource>.ts`

One file per backend resource, exporting typed async functions named by REST verb (`list`, `get`, `create`, `update`, `remove`). `signal?: AbortSignal` is always the last argument; return types are DTOs from `types/`, never `any`. Import in state files via the namespace: `import * as itemsApi from '../api/items'`.

### `types/`

Hand-written DTO `.d.ts`, flat, one file per resource. **Grep rule: if a type appears in any `api/` function signature, it lives in `types/`.** DTOs are pure shapes matching wire JSON 1:1 — no methods, no classes, no getters. State and prop interfaces live with their state/component, not here.

**Entity ids are `string`, not `number`.** Backend entity ids are 64-bit snowflakes that exceed JavaScript's `Number.MAX_SAFE_INTEGER` (2^53), so the backend serializes them as strings; type them as `string` in every `.d.ts` DTO. See `backend/auth-ids.md` → Conventions — entity ID strategy.

### No runtime validation

No zod / io-ts / runtypes. `response.json() as Item[]` — the backend (Pydantic) is the single source of truth for shapes; a mismatch is fixed at source rather than double-bookkept with a client schema. Strict TypeScript plus end-to-end testing is the safety net.

### SSE / streaming

Streaming endpoints use `streamPost()` in `src/api/sse.ts`: a `fetch`-based reader that issues a `POST` (with `Bearer` auth) and parses `event:` / `data:` frames from the response body. This is **not** the browser `EventSource` API (which supports neither POST bodies nor auth headers). Frame handlers push updates into observable state via `runInAction`.

**The first call site and its two sanctioned deviations (feature 011).** The chat pane's turn stream (`api/chats.ts::streamChatTurn`) is the repo's first `streamPost()` consumer, and it exposed two places where the streaming path cannot obey the conventions above. Both are deliberate; the next streaming surface will meet them again.

1. **Refresh before stream.** `streamPost` uses raw `fetch` + `authHeaders()` and therefore **bypasses `client.ts`'s `request<T>` on-401 silent refresh** — by the time a 401 arrives the stream is already open and there is nothing to transparently retry. `client.ts` therefore exports a **reusable refresh entry point** (`refreshAuthToken`), and `streamChatTurn` **awaits it before opening the stream**. Refreshing up front is cheap; retrying a half-consumed stream is not.
2. **The stream owns its controller, so the effect takes no `signal`.** `streamPost` **creates and returns its own `AbortController` and accepts no `signal`**, which does not fit the `(state, args, signal)` effect convention. Consequently the send/retry effect functions **take no trailing `signal`**, store the returned controller on the state, and expose an **explicit stop** function that the shell's unmount cleanup calls. This is the one sanctioned break of the trailing-`signal` convention — a stream's lifetime is longer than a request's and belongs to the state that displays it.

**The terminal payload needs a reload.** `streamPost` calls `onDone()` with **no argument**, so the `done` frame's persisted assistant-message DTO is unreachable through it. The send/retry path therefore obtains the stored message by **reloading the chat once via `getChat`** on `done` and swapping `messages` atomically, which makes the in-flight bubble disappear with no duplicate or orphan. If a future streaming surface needs the terminal payload without a reload, `streamPost`'s `onDone` signature has to forward the parsed `done` data — a frozen-signature change, not a local workaround.

The frame vocabulary itself is the assistant runtime's, not this layer's: `thinking` / `delta` / `done` / `error` / `canvas`, documented in `assistant-runtime.md`. `sse.ts` carries named handling for the frames it was written against and a **generic event branch** beside it, which is why feature 013 could add `canvas` in the resource module (`api/chats.ts`) **without opening `sse.ts` at all**. Keep new frames on that path: the reader is transport, and a frame name is not.

**Markdown rendering.** Feature 011 is also the repo's **first use of `react-markdown`** — assistant message content only (user text renders plain), with **no plugins configured**, because none were needed. That no-plugin default is the baseline for future markdown surfaces; adding a plugin is a decision to record, not a default to inherit.

### Testing

Vitest + jsdom + React Testing Library. Specs live under `frontend/tests/`; the exact commands are in the root `CLAUDE.md`.

**Specs mock `api/` resource modules, never `fetch`** (first done in `tests/user/BookshelfPage.test.tsx`). State files never know they are mocked, and a spec never encodes a URL, a header or a status code — those belong to `api/`. `client.ts` is the exception and is tested directly, for auth injection, error normalization and abort behavior.

**Two typecheck programs, on purpose.** `npm run build` (`tsc && vite build`) covers `src` only — `frontend/tsconfig.json` keeps `include: ["src"]` — so **a broken test can never break the bundle**. `frontend/tsconfig.test.json` is the only program covering `tests/`, and **`npm run test:types` is the only command that runs it**. Both must pass; neither substitutes for the other.
