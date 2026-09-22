# Fast feature 002 — admin-ui-retune (feature-wide context)

Read `brief.md` first (the roadmapped definition). This file distills the
harvested evidence and the user-locked decisions the plan rests on. Everything
here was verified against the repo at planning time (2026-07-25) — the plan does
not need re-derivation.

## What this feature is

A single UI pass over the **admin SPA shell**: replace the 44-line inline header
with a Mantine `AppShell` (left navbar + mobile burger), add a working active-nav
indicator, a user chip with Logout, a "Main site" exit back to the user SPA, an
admin **role** gate that runs outside React, and a catch-all route. It also
stands up the repo's **first frontend test harness** (Vitest + jsdom + RTL),
because none exists and the fast pipeline's red gate needs one.

No backend change. No new API call. No new `types/*.d.ts`. No book-domain work.

## The current state of the admin shell (verified)

`frontend/src/admin/App.tsx` is 44 lines and *is* the entire shell:

```
MantineProvider theme={theme} defaultColorScheme="dark"
  BrowserRouter basename="/admin"
    Group h={56} px="md" justify="space-between"   ← inline borderBottom
      Title order={4}  "BookWriter — Admin"
      Group gap="md"   ← three react-router NavLinks, top-right
    AdminRoutes
```

Nine defects were enumerated and confirmed:

1. **No left menu at all** — nav is a horizontal group in the top-right. No
   Mantine `AppShell` exists anywhere in the repo.
2. **Active state can never render** — react-router `NavLink` only adds
   `class="active"`; `frontend/global.css` has **no `.active` rule** and the
   links pass no `className`/`style` callback.
3. **`to="/"` has no `end`** — Users is `isActive` on every route.
4. **Raw browser-blue `<a>` tags** inside a dark Mantine header.
5. **No logout anywhere in any SPA.** `frontend/src/auth.ts:93` `logout()`
   exists; its only callers are the 401/refresh-failure branches in
   `frontend/src/api/client.ts:92,107,112`.
6. **No link back to the user SPA** — and `<Link to="/">` cannot work, because
   `basename="/admin"` resolves it to `/admin/`.
7. **No catch-all route** — `frontend/src/admin/routes.tsx` maps `/`,
   `/llm-servers`, `/database` and has no `path="*"`; unknown `/admin/xyz`
   renders header + blank body.
8. **No role gate** — `App.tsx:12-17` checks only `getToken() === null`. An
   authenticated `author` mounts the full admin shell and collects 403s.
   `getCurrentUser()` (`auth.ts:54`) exposes `role` and has **zero callers**
   repo-wide.
9. **Render-phase side effect** — `App.tsx:14` assigns `window.location.href`
   during render; StrictMode runs it twice.

## Auth facts the work must respect

`frontend/src/auth.ts` is **plain module state, not a MobX store** — intentional
per `docs/architecture/frontend.md:129,133`.

- Keys: `ACCESS_TOKEN_KEY = "access_token"`, `REFRESH_TOKEN_KEY = "refresh_token"`.
- `interface CurrentUser { user_id: string; username: string; role: UserRole }`,
  with `UserRole = "admin" | "author"` (`frontend/src/types/auth.d.ts:6`).
- Surface: `getToken()`, `getRefreshToken()`, `setTokens()`, `setAccessToken()`,
  `getCurrentUser()`, `logout()`.
- `getCurrentUser()` base64url-decodes the access-token JWT payload **locally** —
  no network, no signature check. The backend access token really does carry
  `role` (`backend/app/services/auth.py:124-130`), so it works live.
- `logout()` clears both keys then sets `window.location.href = "/login/"`.
- **Hard constraint (`auth.ts:3-5`): `auth.ts` MUST NOT import from `src/api/`.**
- There is **no backend logout endpoint** — logout is purely client-side.

**Cross-SPA navigation convention**: a full page navigation via
`window.location.href` — `"/login/"` (trailing slash) and `"/"` for the user SPA.
Existing sites: `auth.ts:96`, `user/App.tsx:15`, `admin/App.tsx:15`,
`login/loginState.ts:132,188`.

## Frontend conventions that constrain the design (hard rules)

From root `CLAUDE.md` + `docs/architecture/frontend.md`:

- **MobX only**; `observer` on **every** component, no exceptions.
- Component state lives in a `<Component>State` class next to the component;
  effectful operations are external functions `(state, args, signal)` using
  `runInAction`.
- **No custom `useX` hooks.** `useState` **only** to hold a stable state-class
  instance — never for reactive data. `useEffect` only at page level. No
  `useCallback` / `useMemo` / `useReducer`. No Mantine `useForm`.
- Mantine only — no Tailwind, no CSS modules.
- All HTTP in `src/api/`; tests mock the `api/` module, not `fetch`.
- Modal/draft precedent to mirror:
  `frontend/src/admin/components/users/SetPasswordModal.tsx` — state class in the
  same `.tsx`, `makeAutoObservable`, `get clientErrors()` / `get errors()` /
  `get canSubmit()`, external `submitX(draft, …)`, and
  `const [draft] = useState(() => new XDraft())`.

## Folder facts

- `frontend/src/components/` holds only `.gitkeep`. It is reserved for the
  cross-SPA `AppLayout` / `AppHeader` / `AppSidebar`, which `frontend.md:104`
  calls **deliberately deferred**. The user chose an **admin-local** shell, so
  **nothing may land in `src/components/`** in this feature.
- `frontend/src/utils/` holds only `.gitkeep`; it receives `navigate.ts`.
- Installed but unused: `@mantine/hooks` ^7.17 (never imported in `src/`) and
  `@tabler/icons-react` ^3.40 (used in pages, not in nav). Mantine is **7.17.8**;
  its `MantineProvider` supports `env="test"`, which disables transitions and
  portals.

## Testing ground truth

- **No frontend test harness exists.** `frontend/package.json` scripts are only
  `dev` / `build` / `preview`; devDeps are `@types/react`, `@types/react-dom`,
  `@vitejs/plugin-react`, `typescript`, `vite`. Zero `*.test.*` / `*.spec.*`
  files in the repo.
- `frontend/tsconfig.json` has `include: ["src"]`.
- `frontend/vite.config.ts` carries `appType: "mpa"`, a custom `spaFallback()`
  dev middleware, port 8194, an `/api` proxy to `localhost:8185`, and
  `rollupOptions.input = { user, admin, login }` (three entries).
- `docs/architecture/frontend.md:248-251` says "No frontend test runner is
  configured in the scaffold today" — this feature makes that false, hence the
  `outcome.md` entry.

## Commands (from root `CLAUDE.md`)

- Frontend build + typecheck: `cd frontend && npm run build` (= `tsc && vite build`)
- Typecheck only: `cd frontend && npx tsc --noEmit`
- No linter is configured — do not run one.
- This feature **adds**: `cd frontend && npm test` and
  `cd frontend && npm run test:types`, and records both in root `CLAUDE.md`.

## User-locked decisions (settled — do not revisit or offer alternatives)

1. **Left sidebar + mobile burger** via Mantine `AppShell` with a real left navbar.
2. **Header controls**: current-user display (username + role from
   `getCurrentUser()`), a user menu behind it with **Logout** and **Change
   password (disabled)**, plus a "switch to main site" control. Skin/theme
   selection is explicitly LATER.
3. **Change password ships as a visibly disabled menu item** — zero backend work.
   Verified: no self-service password route/schema/service exists, and no product
   UC/US covers it (UC-007 is admin-resets-a-target only).
4. **Admin-local layout** — nothing in `src/components/`.
5. Also in scope: the admin **role** gate, the catch-all route, and removing the
   render-phase `window.location` mutation.
6. **The Vitest harness lands inside this feature** — vitest + jsdom + React
   Testing Library, with the command recorded in root `CLAUDE.md`.

## Product ids

None. The brief carries no `Delivers:` line — this is a correction pass over
already-delivered FEAT-001..005 admin surfaces, adding no domain behaviour.
