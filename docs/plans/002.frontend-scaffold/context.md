# Feature 002 — frontend-scaffold (feature-wide context)

## Goal & scope

Stand up the BookWriter **Vite multi-page frontend as a runnable, typechecking
skeleton**. Greenfield: `frontend/` does not exist yet. When done, a developer
can `npm install`, run `npm run dev` (Vite on `:8194`) and load all three
entries — User (`/`), Admin (`/admin`), Login (`/login`) — and `npm run build`
(`tsc && vite build`) is clean. End-to-end wiring is proven by a trivial
User-SPA page that fetches the 001 backend `GET /api/health` endpoint through
`src/api/`, via the Vite `/api` dev proxy.

This is **Stage 0 scaffold**. It delivers **no product ids** — DoD items cite
the brief's behavioural scope, not `US/AC` ids. The settled boundary is
`brief.md` (Definition + Scope In/Out). Do not widen it.

## Authoritative sources

- `docs/architecture/frontend.md` — the FULL enforced frontend rules and is
  highly prescriptive; follow it literally. Covers: stack/versions, the exact
  `tsconfig.json` flags, the `vite.config.ts` MPA shape (3 Rollup inputs + the
  `spaFallback` dev plugin + `/api` proxy), npm scripts, theming
  (`createTheme()` + `defaultColorScheme="dark"`), the folder layout, the MobX
  hard rules, and the API layer (`client.ts` / `api/<resource>.ts` / `types/` /
  `sse.ts`).
- `docs/architecture/dev-environment.md` — ports (frontend Vite 8194, backend
  8185), the `/api` dev proxy, `.env.local`.
- Root `CLAUDE.md` — Build & Test: frontend dev `cd frontend && npm run dev`;
  build (=typecheck+bundle) `cd frontend && npm run build`; typecheck only
  `cd frontend && npx tsc --noEmit`. **Linter: none. No frontend test runner is
  configured** (see "No test runner" below).

## Reference project (mirror its scaffold patterns)

Sibling `D:/GitRoot/_TextGens/LLMRPTextOnlyProject/frontend` implements the same
stack; BookWriter mirrors it. Step-specific context files cite concrete `path`
anchors under that tree for the skeleton/coder to consult. Deliberate
**divergences** from the reference, applied in every step:

1. **Rename all "LLMRP" strings** — html `<title>`s, theme identifiers,
   placeholder copy — to **BookWriter**.
2. **OMIT reference domain code** (e.g. `loadTranslationSettings()`,
   translation settings) — none of it belongs in the scaffold.
3. **OMIT the reference App.tsx token-gate redirect** and the reference Login
   auth form — see the "Confirmed scope decisions" below.

## Cross-cutting conventions (apply in every step)

- **MobX hard rules** (from `frontend.md`): `observer` on every component; a
  state object holds observable fields + pure `get` computeds and **never**
  effectful methods; effectful ops are external `(state, args, signal)`
  functions using `runInAction`; the async-resource **trio** is
  `<name>` / `<name>Status: 'idle'|'loading'|'ready'|'error'` / `<name>Error`;
  `useState(() => new XState())` holds a stable instance; `useEffect` only at
  page level for mount-load / unmount-abort; no `useCallback` / `useMemo` /
  `useReducer` / custom hooks. Only the health page bootstraps this convention
  in this feature.
- **API layer** (from `frontend.md`): all HTTP lives in `src/api/`; `client.ts`
  `request<T>()` injects Bearer from `src/auth.ts`, normalizes non-2xx to
  `ApiError`, forwards `AbortSignal`; `api/<resource>.ts` exports REST-verb
  functions with `signal?` last, namespace-imported; DTOs are hand-written
  `.d.ts` in `src/types/`; **no zod / runtime validation**; SSE uses
  `sse.ts` `streamPost()`, not `EventSource`.
- **Dark is the default** color scheme everywhere a `MantineProvider` mounts.
- **Single `tsconfig.json`** — no `tsconfig.node.json`. Ports: frontend 8194,
  proxy → backend 8185.

## Confirmed scope decisions (settled — do not re-open)

1. **Login entry = bare placeholder.** `login/main.tsx` + `login/Login.tsx`
   render a minimal placeholder owning its own
   `MantineProvider defaultColorScheme="dark"` + simple centered copy (e.g.
   "Login (coming soon)"). No form, no fields, no auth wiring. It only proves
   the third Vite input mounts and builds. Feature **004** builds the real login.
2. **nginx configs + docker-compose + frontend Dockerfile = deferred entirely**
   (as 001 deferred them). Dev uses the Vite `/api` proxy; the Stage-0 health
   call flows browser → Vite proxy → backend, no nginx. **Do NOT author**
   `nginx/`, compose files, or `frontend/Dockerfile` in this feature.
3. **No auth/token logic in the scaffold** — auth is feature 004. OMIT the
   reference App.tsx token-gate redirect. `src/auth.ts` ships only `getToken()`
   (localStorage read, what `client.ts` needs for Bearer) plus a minimal
   `logout()` stub. `getCurrentUser()` / JWT-decode and the redirect flow are
   004's. This is a recorded seam: 004 expands `auth.ts` and adds the token gate.
4. **No shared AppLayout/AppSidebar/AppHeader shell, no real routing.**
   `src/components/` exists as a folder (seeded minimal) but the cross-SPA
   shells are NOT built. The User SPA routes only the trivial health page; the
   Admin SPA renders a placeholder route.
5. **No frontend test runner.** The brief doesn't scope one, the reference has
   none, and `CLAUDE.md` declares no frontend test command. All DoD items are
   **`[manual/live]`** — verified by `npm run build` (tsc+vite),
   `npx tsc --noEmit`, `npm run dev` serving the 3 entries, and the live health
   call. Steps have **zero `[test]` items**; the pipeline runs skeleton → coder
   → verifier without a test-coder red-gate. **Do not introduce vitest/jest.**
   Consequently, each step's **Test files** list is empty by design.
6. **Keep `@mantine/form` as a dependency** (in-stack) but follow the
   drafts-in-state form pattern — do **not** use Mantine `useForm`.

## Files touched across the feature

```
frontend/
  package.json                       (001)
  tsconfig.json                      (001)
  vite.config.ts                     (001, incl. spaFallback plugin)
  theme.ts                           (001)
  global.css                         (001)
  index.html                         (001)  User SPA entry
  admin/index.html                   (001)  Admin SPA entry
  login/index.html                   (001)  Login entry
  src/
    vite-env.d.ts                    (001)
    utils/.gitkeep                   (001)  establishes folder layout
    components/.gitkeep              (001)  establishes folder layout
    user/main.tsx                    (001)
    user/App.tsx                     (001 create placeholder → 003 add health route)
    user/routes.tsx                  (003)
    user/pages/HealthPage.tsx        (003)
    user/pages/healthPageState.ts    (003)
    admin/main.tsx                   (001)
    admin/App.tsx                    (001)
    login/main.tsx                   (001)
    login/Login.tsx                  (001)
    auth.ts                          (002)
    api/client.ts                    (002)
    api/sse.ts                       (002)
    api/health.ts                    (003)
    types/common.d.ts                (002)
    types/health.d.ts                (003)
```

## `src/user/App.tsx` is edited across two steps (not scope drift)

`src/user/App.tsx` legitimately appears in the Source-files list of **both step
001 and step 003**. Step 001 **creates** it with the MantineProvider + router
shell and a placeholder route; step 003 **edits** it to wire the health route
(via `src/user/routes.tsx`). This is the same coder role editing one file
incrementally across dependent steps — intended, not a cross-step breach.

## Backend contract this feature consumes

`GET /api/health` (from 001) returns a Pydantic `HealthResponse`:
`{ status: "ok", db: "ready" }` — both fields are `str`. The frontend
`src/types/health.d.ts` DTO must match this shape 1:1 (`status: string;
db: string`). No other backend endpoint is consumed.
