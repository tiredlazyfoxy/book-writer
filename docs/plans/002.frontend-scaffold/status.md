# Feature 002 — frontend-scaffold

| Step | File                    | Status  | Verifier | Date |
|------|-------------------------|---------|----------|------|
| 001  | `001.mpa-skeleton.md`   | done    | PASS     | 2026-07-21 |
| 002  | `002.api-layer.md`      | done    | PASS     | 2026-07-21 |
| 003  | `003.health-page.md`    | done    | PASS     | 2026-07-21 |

## Files Changed

### Step 001 — MPA skeleton: tooling, config, three entries, theming
- `frontend/package.json` — deps/scripts manifest (`type:module`, dev/build/preview)
- `frontend/tsconfig.json` — single strict typecheck config, `include:["src"]`
- `frontend/vite.config.ts` — MPA config (3 inputs, `/api` proxy) + `spaFallback` dev plugin
- `frontend/theme.ts` — `createTheme()` steel primary + custom dark scale + component defaults
- `frontend/global.css` — reset + `.md-body` markdown styles
- `frontend/index.html` — User SPA entry document
- `frontend/admin/index.html` — Admin SPA entry document
- `frontend/login/index.html` — Login entry document
- `frontend/src/vite-env.d.ts` — vite/client type reference
- `frontend/src/utils/.gitkeep` — shared folder seed
- `frontend/src/components/.gitkeep` — shared folder seed
- `frontend/src/user/main.tsx` — User `createRoot` bootstrap
- `frontend/src/user/App.tsx` — User MantineProvider + router placeholder
- `frontend/src/admin/main.tsx` — Admin `createRoot` bootstrap
- `frontend/src/admin/App.tsx` — Admin MantineProvider + router placeholder (`basename="/admin"`)
- `frontend/src/login/main.tsx` — Login `createRoot` bootstrap (no router)
- `frontend/src/login/Login.tsx` — bare centered Login placeholder owning its own MantineProvider

### Step 002 — API layer + types seed
- `frontend/src/auth.ts` — `getToken()` reads `localStorage["token"]`; `logout()` removes it (no api/ import)
- `frontend/src/api/client.ts` — `authHeaders()`, `request<T>` (Bearer/JSON/abort, 204→undefined), `throwApiError` (`{detail}`→`ApiError`)
- `frontend/src/api/sse.ts` — `streamPost` hand-rolled fetch-POST SSE reader; dispatches frames to generic handlers, swallows `AbortError`
- `frontend/src/types/common.d.ts` — unchanged (shapes already frozen-complete); imported by `client.ts` for `ApiErrorBody`

### Step 003 — Health page: MobX convention + end-to-end proof
- `frontend/src/types/health.d.ts` — unchanged (frozen-complete `HealthResponse { status; db }`)
- `frontend/src/api/health.ts` — `getHealth(signal?)` returns `request<HealthResponse>(BASE, { signal })`
- `frontend/src/user/pages/healthPageState.ts` — `loadHealth(state, signal)` fills the trio via `runInAction`; aborts early on `signal.aborted`
- `frontend/src/user/pages/HealthPage.tsx` — render body: loading `Loader` / error `Text` / ready status+db `Table`
- `frontend/src/user/routes.tsx` — unchanged (route table already frozen-complete by skeleton)
- `frontend/src/user/App.tsx` — unchanged (route wiring to `UserRoutes` already applied by skeleton)

## Skeleton

### Step 001 — frozen interface (2026-07-21)

Config / non-code deliverables (written substantially complete — no runtime behavior to fill):
- `frontend/package.json` — new — name `bookwriter-frontend`, `"type":"module"`, scripts `dev`/`build`/`preview`, dep set per intent.
- `frontend/tsconfig.json` — new — single strict config, `"include":["src"]`, no `tsconfig.node.json`.
- `frontend/vite.config.ts` — new — `export default defineConfig(...)` (`appType:'mpa'`, 3 Rollup inputs, `server.port 8194`, proxy `/api`→`http://localhost:8185`); module-local `function spaFallback(): Plugin`.
- `frontend/theme.ts` — new — `export const theme = createTheme({...})` (named export; primary `steel` + custom `dark` scale + component defaults).
- `frontend/global.css` — new — reset + `.md-body` block.
- `frontend/index.html`, `frontend/admin/index.html`, `frontend/login/index.html` — new — BookWriter `<title>`, `<div id="root">`, module script to `/src/{user,admin,login}/main.tsx`.
- `frontend/src/vite-env.d.ts` — new — `/// <reference types="vite/client" />`.
- `frontend/src/utils/.gitkeep`, `frontend/src/components/.gitkeep` — new — empty folder seeds.

Frozen React exports (the contract other steps/coder bind to):
- `frontend/src/user/App.tsx` — `export const App` (observer component, `() => JSX`). Imports `../../theme`, `../../global.css`, `@mantine/core/styles.css`. Renders `MantineProvider theme={theme} defaultColorScheme="dark"` > `BrowserRouter` > single `Routes`/`Route path="*"` placeholder. (Step 003 replaces the placeholder route.)
- `frontend/src/user/main.tsx` — new — `createRoot(document.getElementById("root")!).render(<StrictMode><App/></StrictMode>)` from `./App`.
- `frontend/src/admin/App.tsx` — `export const App` (observer component, `() => JSX`). Same shape; `BrowserRouter basename="/admin"`.
- `frontend/src/admin/main.tsx` — new — renders `<StrictMode><App/></StrictMode>` from `./App`.
- `frontend/src/login/Login.tsx` — `export const Login` (observer component, `() => JSX`). Owns its own `MantineProvider defaultColorScheme="dark"` + CSS/theme imports; bare centered "Login (coming soon)". No form/fields/auth (decision 1).
- `frontend/src/login/main.tsx` — new — renders `<StrictMode><Login/></StrictMode>` from `./Login`. No router, no page state.

Caller-compile edits (out of Source-files scope): None. Greenfield feature — no pre-existing callers.

Compile gate: `npm install` (184 pkgs, clean) → `npx tsc --noEmit` exit 0 → `npm run build` exit 0, emitting all three entry chunks (user/admin/login) + three `index.html`.

### Step 002 — frozen interface (2026-07-21)

- `frontend/src/auth.ts` — new — module-level (not a class/store), no `src/api/` import:
  - `getToken(): string | null`
  - `logout(): void`
  - (getCurrentUser / JWT-decode / redirect deliberately omitted — feature 004, decision 3)
- `frontend/src/api/client.ts` — new:
  - `class ApiError extends Error` — `constructor(public status: number, message: string, public details?: unknown)`; sets `name = "ApiError"` (data/error shape declared fully — the frozen contract).
  - `interface RequestOptions { method?: "GET" | "POST" | "PUT" | "DELETE"; body?: unknown; signal?: AbortSignal }`
  - `authHeaders(): HeadersInit`
  - `request<T>(url: string, opts?: RequestOptions): Promise<T>`
  - `throwApiError(res: Response): Promise<never>`
- `frontend/src/api/sse.ts` — new:
  - `interface SSEHandlers { onEvent?: (event: string, data: unknown) => void; onError?: (message: string) => void; onDone?: () => void }` — generic non-domain seed, co-located with its sole consumer (a callback bag, not a wire DTO, so not in `common.d.ts`).
  - `streamPost(url: string, body: object, handlers: SSEHandlers): AbortController`
- `frontend/src/types/common.d.ts` — new — pure wire shapes:
  - `interface ApiErrorBody { detail?: string }`
  - `type ISODateString = string`

Function/class stub bodies throw `Error("not implemented")` (data/error shapes declared fully). Real param names are frozen; unused-in-stub params/imports suppressed via `void x;` to satisfy `noUnusedLocals`/`noUnusedParameters` without renaming the frozen signature.

Caller-compile edits (out of Source-files scope): None. Greenfield step — no pre-existing callers; `api/health.ts` (003) will be the first consumer.

Compile gate: `cd frontend && npx tsc --noEmit` → exit 0.

### Step 003 — frozen interface (2026-07-21)

- `frontend/src/types/health.d.ts` — new — `export interface HealthResponse { status: string; db: string }` (matches backend `HealthResponse` 1:1; pure wire shape, no runtime validation).
- `frontend/src/api/health.ts` — new — module-local `const BASE = "/api/health"`; `export async function getHealth(signal?: AbortSignal): Promise<HealthResponse>` (calls `request<HealthResponse>` from `./client`; `signal?` last; namespace-imported by state as `* as healthApi`).
- `frontend/src/user/pages/healthPageState.ts` — new:
  - `export class HealthPageState` — `makeAutoObservable(this)` in ctor; trio fields `health: HealthResponse | null`, `healthStatus: "idle" | "loading" | "ready" | "error"`, `healthError: string | null`. No effectful methods.
  - `export async function loadHealth(state: HealthPageState, signal: AbortSignal): Promise<void>` — external effectful function (body is the coder's).
- `frontend/src/user/pages/HealthPage.tsx` — new — `export const HealthPage = observer(function HealthPage() {...})` (owns stable state via `useState(() => new HealthPageState())`; single mount `useEffect([])` creating an `AbortController`, `void loadHealth(state, ctrl.signal)`, returns `() => ctrl.abort()`; JSX render body left for coder).
- `frontend/src/user/routes.tsx` — new — `export function UserRoutes()` returning `<Routes><Route path="/" element={<HealthPage />} /></Routes>` (User SPA route table).
- `frontend/src/user/App.tsx` — changed (from step 001) — route wiring only: inline `<Routes>/<Route path="*">` placeholder replaced with `<UserRoutes />` inside the intact `<MantineProvider>` + `<BrowserRouter>` shell; dropped now-unused imports (`Route`, `Routes`, `Center`, `Title`), added `import { UserRoutes } from "./routes"`. `export const App` shape unchanged.

Stub bodies for `getHealth` / `loadHealth` / `HealthPage` throw `Error("not implemented")`; frozen param names preserved, unused-in-stub imports/params suppressed with `void x;` to satisfy `noUnusedLocals`/`noUnusedParameters`. `HealthPageState` fields and both `.d.ts` / route-table shapes are declared complete (structural, no behavior to fill).

Caller-compile edits (out of Source-files scope): None. `App.tsx` is a listed Source file for step 003 (see context.md "App.tsx edited across two steps"), not an out-of-scope caller.

Compile gate: `cd frontend && npx tsc --noEmit` → exit 0.

## Notes & Issues

_populated by the coder when worth saying_
