# Fast feature 002 — admin-ui-retune

| Status | Verifier | Date       |
|--------|----------|------------|
| done   | PASS     | 2026-07-25 |

## Files Changed

Bodies filled by the coder (stubs landed by the skeleton):

- `frontend/src/utils/navigate.ts` — `navigateTo` performs the full-page cross-SPA navigation.
- `frontend/src/admin/adminGate.ts` — the four ordered admission rules + the single-navigation enforcer.
- `frontend/src/admin/components/shell/navItems.ts` — `isNavItemActive`: exact equality, else `/`-delimited descendant match.
- `frontend/src/admin/components/shell/AdminShell.tsx` — the `AppShell` chrome (header/navbar/main, burger, "Main site" anchor, user menu).
- `frontend/src/admin/components/shell/AdminNav.tsx` — the three-item Mantine `NavLink` list with the sole `useLocation()` call.
- `frontend/src/admin/components/shell/AdminUserMenu.tsx` — user chip + dropdown (Logout, disabled Change password).
- `frontend/src/admin/pages/NotFoundPage.tsx` — the `path="*"` page with its single link back to Users.

Already complete when the coder started — the skeleton had rewired them, so no coder change was needed:

- `frontend/src/admin/App.tsx` — gate-free `MantineProvider > BrowserRouter > AdminShell > AdminRoutes`.
- `frontend/src/admin/main.tsx` — `createRoot` guarded by `enforceAdminAccess()`.
- `frontend/src/admin/routes.tsx` — terminal `path="*"` route added.

## Skeleton

### Frozen interface (2026-07-25)

Verbatim TypeScript. The test-coder binds to exactly these names; the coder may
not change any of them (re-route to skeleton if a change is unavoidable).

**Harness contract**

- `globals: false` in `frontend/vitest.config.ts` — **every test file must import
  its own primitives**: `import { describe, it, expect, vi, beforeEach } from "vitest"`.
  Nothing is injected globally. (RTL's `cleanup()` is registered for you in
  `tests/setup.ts`, so tests need not call it.)
- `include: ["tests/**/*.test.{ts,tsx}"]`, `environment: "jsdom"`,
  `setupFiles: ["./tests/setup.ts"]`, `restoreMocks: true`, `clearMocks: true`.
- `frontend/tests/support/render.tsx`:

```ts
export interface RenderWithProvidersOptions {
  route?: string;
}

export function renderWithProviders(
  ui: ReactNode,
  options?: RenderWithProvidersOptions,
): RenderResult;
```

  Wraps in `MantineProvider theme={theme} env="test"`, and — only when `route` is
  given — additionally in `MemoryRouter initialEntries={[route]}`. `RenderResult`
  is `@testing-library/react`'s. Routes are basename-stripped (`/`,
  `/llm-servers`, `/database`).

**Frozen signatures**

- `frontend/src/utils/navigate.ts` — `export function navigateTo(href: string): void` — new
- `frontend/src/admin/adminGate.ts` — new:

```ts
export type AdminAccessDecision =
  | { allowed: true }
  | { allowed: false; redirectTo: string };

export function resolveAdminAccess(): AdminAccessDecision;
export function enforceAdminAccess(): boolean;
```

  Discriminant is `allowed`; the href field is `redirectTo` (`"/login/"` or `"/"`).
  `enforceAdminAccess()` returns "mount the SPA".

- `frontend/src/admin/components/shell/navItems.ts` — new:

```ts
import { type Icon } from "@tabler/icons-react";

export interface AdminNavItem {
  path: string;
  label: string;
  icon: Icon;
  exact?: boolean;
}

export const ADMIN_NAV_ITEMS: readonly AdminNavItem[] = [
  { path: "/", label: "Users", icon: IconUsers, exact: true },
  { path: "/llm-servers", label: "LLM Servers", icon: IconServer2 },
  { path: "/database", label: "Database", icon: IconDatabase },
];

export function isNavItemActive(pathname: string, item: AdminNavItem): boolean;
```

  `ADMIN_NAV_ITEMS` is populated (pure declarative data, fully specified by the
  plan — no `[test]` DoD can pass from it alone, since both `isNavItemActive` and
  `AdminNav` throw). `isNavItemActive`'s body throws. Field names are
  `path` / `label` / `icon` / `exact`; `exact` is the exact-match-only flag.

- `frontend/src/admin/components/shell/AdminShell.tsx` — new:

```ts
export class AdminShellState {
  navbarOpened = false;   // observable; default false; makeAutoObservable in ctor; NO methods
  constructor();
}

export interface AdminShellProps {
  children: ReactNode;
}

export const AdminShell: FunctionComponent<AdminShellProps>;   // observer
```

  The observable field name is **`navbarOpened`** ("open on mobile"). The class is
  written out (declarative shape only); `AdminShell`'s body throws.

- `frontend/src/admin/components/shell/AdminNav.tsx` — new:

```ts
export interface AdminNavProps {
  onNavigate?: () => void;
}

export const AdminNav: FunctionComponent<AdminNavProps>;   // observer
```

- `frontend/src/admin/components/shell/AdminUserMenu.tsx` — new:

```ts
import type { CurrentUser } from "../../../auth";

export interface AdminUserMenuProps {
  user: CurrentUser | null;
  onLogout: () => void;
}

export const AdminUserMenu: FunctionComponent<AdminUserMenuProps>;   // observer
```

  Prop names are **`user`** and **`onLogout`**. Type-only import of `CurrentUser`
  — no runtime dependency on `auth.ts`, so this component's test needs no mock.

- `frontend/src/admin/pages/NotFoundPage.tsx` — `export const NotFoundPage: FunctionComponent` (no props) — new, `observer`
- `frontend/src/admin/routes.tsx` — `export const AdminRoutes` — unchanged signature; gained the terminal `<Route path="*" element={<NotFoundPage />} />`
- `frontend/src/admin/App.tsx` — `export const App` — unchanged signature; body rewired to `MantineProvider > BrowserRouter > AdminShell > AdminRoutes`, render-phase gate and inline header removed
- `frontend/src/admin/main.tsx` — no exports; `createRoot(...).render(...)` now guarded by `if (enforceAdminAccess())`

**Unimplemented bodies (throw at the red gate):** `navigateTo`,
`resolveAdminAccess`, `enforceAdminAccess`, `isNavItemActive`, `AdminNav`,
`AdminUserMenu`, `AdminShell`, `NotFoundPage`. Because `App` renders `AdminShell`
and `AdminRoutes` renders `NotFoundPage`, those two compose the throw upward —
"not implemented" is the expected red-gate failure reason.

- Caller-compile edits (out of Source-files scope): **None.** No file outside the
  plan's Source-files list was touched except root `CLAUDE.md` (assigned to the
  skeleton by the plan) and `frontend/tests/{setup.ts,support/render.tsx}` +
  `frontend/{vitest.config.ts,tsconfig.test.json,package.json}` (likewise). No
  page file, no `vite.config.ts`, no `tsconfig.json`, no `auth.ts`, nothing in
  `src/components/`.

### Harness verification (2026-07-25)

- `npm install` — 90 packages added (vitest 3.2.7, jsdom 26, RTL 16.3, @testing-library/dom 10.4, jest-dom 6.6, user-event 14.6).
- `npm test` → Vitest v3.2.7 starts, resolves `vitest.config.ts`, prints
  `No test files found, exiting with code 1` with `include: tests/**/*.test.{ts,tsx}`.
  That non-zero exit is Vitest's normal "nothing matched" behaviour and disappears
  once the test-coder lands a spec.
- The harness was additionally proven end-to-end with a **throwaway probe outside
  `tests/`** (deleted afterwards; no `*.test.*` file was written): rendering a stock
  Mantine `Button` and an opened `Menu` through `renderWithProviders`, asserting with
  jest-dom `toBeInTheDocument` / `toBeDisabled` and driving it with
  `userEvent.click` — **2 passed**. This confirms jsdom, the `matchMedia` and
  `ResizeObserver` stubs, `scrollIntoView`, the matchers, and `env="test"`'s
  inline/synchronous portal-free rendering all work, i.e. DoD-0 is mechanically
  achievable.
- `npx tsc --noEmit` clean · `npm run test:types` clean · `npm run build` passes
  (three entries: `index.html`, `admin/index.html`, `login/index.html`; no test
  file in the program or the bundle).
- `grep -rn "window.location" frontend/src/admin/` → no matches (DoD-21's static half).

## Tests

### Tests (2026-07-25)

- `frontend/tests/harness.test.tsx` — covers DoD-0 — stock Mantine `Button` / opened `Menu` / router `Link` render through `renderWithProviders` and satisfy jest-dom matchers (**expected GREEN at the red gate** — touches no feature source).
- `frontend/tests/admin/adminGate.test.ts` — covers DoD-1, DoD-2, DoD-3, DoD-4, DoD-5 — `resolveAdminAccess()`'s four ordered outcomes (`{allowed:false,redirectTo:"/login/"}` twice, `"/"` for `author`, `{allowed:true}` for `admin`), that denying an author leaves both localStorage tokens and never calls `logout()`, and that `enforceAdminAccess()` returns the mount boolean while calling `navigateTo` exactly once (never, when allowed). `src/auth.ts` and `src/utils/navigate.ts` are the module-mocked seams.
- `frontend/tests/admin/navItems.test.ts` — covers DoD-6 — `isNavItemActive`: exact `/` matches only `/`; non-exact items match themselves and `/`-delimited descendants but never a bare prefix (`/database-export`, `/llm-servers-archive`).
- `frontend/tests/admin/AdminNav.test.tsx` — covers DoD-7, DoD-8 — three links with labels + hrefs `/`, `/llm-servers`, `/database`; exactly one `data-active="true"` at `/database` and at `/` (inactive links carry no `data-active` attribute at all).
- `frontend/tests/admin/AdminUserMenu.test.tsx` — covers DoD-13, DoD-14 — username + role in the menu target, empty render for `user={null}` (`toBeEmptyDOMElement`), opened dropdown exposing Logout and a **disabled** Change password, `onLogout` called exactly once on Logout and never on the disabled item. No module mock — a `vi.fn()` prop is the whole seam.
- `frontend/tests/admin/AdminShell.test.tsx` — covers DoD-9, DoD-10, DoD-11, DoD-12, DoD-15 — one `banner`/`navigation`/`main` landmark with `children` inside `main`; the `BookWriter — Admin` title; a /main site/ link with `href` exactly `/`; the burger's `aria-expanded` false → true → false; a navbar link click returning it to false; Logout calling the module-mocked `auth.logout()` once.
- `frontend/tests/admin/routes.test.tsx` — covers DoD-16 — `/nope` renders the not-found page (heading present, its single link points at `/`, so no route page's content is beside it). Only the catch-all branch is mounted; the three fetching pages are never rendered.
- Coverage: DoD-0 ✓, DoD-1 ✓, DoD-2 ✓, DoD-3 ✓, DoD-4 ✓, DoD-5 ✓, DoD-6 ✓, DoD-7 ✓, DoD-8 ✓, DoD-9 ✓, DoD-10 ✓, DoD-11 ✓, DoD-12 ✓, DoD-13 ✓, DoD-14 ✓, DoD-15 ✓, DoD-16 ✓, DoD-17 [manual/live, no test], DoD-18 [manual/live, no test], DoD-19 [manual/live, no test], DoD-20 [manual/live, no test], DoD-21 [manual/live, no test]

Notes for the verifier / coder-side faults:

- DoD-16's negative half ("no route page's content appears") is asserted
  structurally — exactly one link in the tree — because `NotFoundPage`'s heading
  and button *wording* is not fixed by the plan and the three real pages may not
  be mounted.
- DoD-11/DoD-12 assert the `aria-expanded` the plan pins on the `Burger` button;
  the inner `<Box data-opened>` is deliberately not asserted.
- The burger is located by the accessible label the Interface intent pins
  (`aria-label="Toggle navigation"`); the user-menu target by its username text.

## Notes & Issues

- Gate: `npx tsc --noEmit` clean; `npm run build` passes with three entries
  (`index.html`, `admin/index.html`, `login/index.html`). Tests not run (air gap).
- Static DoD-21 half re-confirmed after implementation: `window.location` has no
  matches under `frontend/src/admin/`. `@mantine/hooks` is still unimported
  repo-wide (it appears only inside an `AdminShell.tsx` doc comment explaining why).
- **Mantine `NavLink` nuance worth knowing:** its *description* `<span>` is rendered
  unconditionally and also receives `data-active="true"` when `active` is set
  (`NavLink.mjs:124`). So an active item yields **two** nodes matching a bare
  `[data-active="true"]` selector — the root `<a>` and that empty inner span. The
  `<a>` is the only *link* of the two, so DoD-7's "exactly one link" holds as
  written; a document-wide attribute-selector count would not. Not fixable without
  hacking Mantine, and no page/description text was added to avoid it.
- The burger toggle assigns `state.navbarOpened` directly from the component, per
  the skeleton's frozen "no methods" shape and the repo's precedent
  (`CreateUserModal`, `SetRoleModal`). The repo calls no `mobx.configure()`, so
  MobX's default `enforceActions: "observed"` may log a strict-mode warning on
  toggle — pre-existing behaviour of the established pattern, not introduced here
  and not "fixed" here. See the matching `## Observations` entry in `outcome.md`.
- Out of scope, untouched, noticed in passing: `frontend/src/auth.ts:7-8` still
  carries a stale `Skeleton (004): … bodies throw until the coder fills them`
  header comment over fully-implemented bodies.
