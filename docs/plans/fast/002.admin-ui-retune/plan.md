# fast/002.admin-ui-retune — Admin SPA nav retune

## Goal

Replace the admin SPA's inline top-right nav with a Mantine `AppShell` shell — a
real left navbar with a working active indicator, a mobile burger, a user chip
carrying Logout and a disabled "Change password", and a "Main site" exit back to
the user SPA — and move the auth check out of React's render phase into an
admin-**role** gate in `main.tsx`, adding a catch-all route for unknown paths.
The repo's first frontend test harness (Vitest + jsdom + RTL) lands with it.

**Scope note (for the verifier — this is NOT a promotion signal).** Source is
~375 written lines including the repo's customary JSDoc headers (~255 excluding
comments), plus ~110 declarative lines of harness. That sits at the top of the
fast budget, but there are **no internal step boundaries**: no backend, no API
surface, no new `types/*.d.ts`, no cross-layer coordination, and no mid-flight
design decision — every decision is locked in `context.md`. Do not read the size
as a reason to promote.

## Pipeline note — the harness lands in the SKELETON stage

The fast pipeline is skeleton → test-coder → red-gate verify → coder → verify.
There is **no frontend test harness in the repo**, so if the harness waited for
the coder the test-coder would have nothing to write against and the red gate
could not run. Therefore the **skeleton** owns, in addition to the frozen
signatures for the seven new modules:

- the six new devDependencies and the three `package.json` scripts,
- `frontend/vitest.config.ts`,
- `frontend/tsconfig.test.json`,
- `frontend/tests/setup.ts`,
- `frontend/tests/support/render.tsx`,
- the two new command lines in root `CLAUDE.md`.

**The skeleton must run `npm test` after installing** and confirm Vitest exits
cleanly reporting **no test files found**. That proves the harness works before
any test exists.

The three signatures the blind test-coder cannot guess and the skeleton must
nail: `AdminAccessDecision`'s variant shape, `AdminNavItem`'s field names, and
`AdminUserMenu`'s prop names.

**Warning to the red-gate verifier.** **DoD-0 is expected to PASS at the red
gate.** It exercises no new source — it renders a stock Mantine component through
`renderWithProviders` — so a green DoD-0 alongside red DoD-1..16 is the *intended*
signal that the harness works and the feature does not. Do not read that one
passing test as a red-gate violation. Conversely, the skeleton's stubs throw, so
shell tests failing with "not implemented" **is** the right failure reason — a
crash there is not a harness fault.

## Source files

New:

- `frontend/src/utils/navigate.ts` — the single mockable seam for full-page cross-SPA navigation.
- `frontend/src/admin/adminGate.ts` — pure admission decision + impure enforcer.
- `frontend/src/admin/components/shell/navItems.ts` — nav-item declaration table + pure active-path matcher; no JSX.
- `frontend/src/admin/components/shell/AdminShell.tsx` — `AdminShellState` class + the `AppShell` chrome.
- `frontend/src/admin/components/shell/AdminNav.tsx` — the navbar's Mantine `NavLink` list; the only `useLocation()` call.
- `frontend/src/admin/components/shell/AdminUserMenu.tsx` — pure-props user chip + `Menu`.
- `frontend/src/admin/pages/NotFoundPage.tsx` — the `path="*"` page.

Modified:

- `frontend/src/admin/App.tsx` — drop the render-phase gate and the inline header; becomes `MantineProvider > BrowserRouter > AdminShell > AdminRoutes`.
- `frontend/src/admin/main.tsx` — call the gate enforcer before `createRoot`; skip mounting when denied.
- `frontend/src/admin/routes.tsx` — add the terminal `path="*"` route.

Harness (source-file scope, but landed by the **skeleton** — see Pipeline note):

- `frontend/vitest.config.ts` — NEW. `defineConfig` from `vitest/config`, `plugins: [react()]`, `test: { environment: "jsdom", globals: false, setupFiles: ["./tests/setup.ts"], include: ["tests/**/*.test.{ts,tsx}"], restoreMocks: true, clearMocks: true }`. **`vite.config.ts` is NOT touched** — Vitest prefers `vitest.config.*` automatically, and `vite build` / `vite dev` ignore the new file, so build risk is zero. Leave `css` at its default `false` (CSS imports resolve to empty modules; nothing asserts styling).
- `frontend/tsconfig.test.json` — NEW. Extends the base config, `include: ["tests", "src"]`. This is the **only** program that typechecks tests; `frontend/tsconfig.json` stays unchanged (`include: ["src"]`), so `npm run build` structurally cannot break on a test file.
- `frontend/package.json` — MOD. devDeps below, plus scripts `"test": "vitest run"`, `"test:watch": "vitest"`, `"test:types": "tsc -p tsconfig.test.json --noEmit"`.
- `CLAUDE.md` (root) — MOD. Under **Build & Test Commands** record `**Frontend tests**: cd frontend && npm test` (Vitest + jsdom + RTL; specs under `frontend/tests/`) and `**Frontend test typecheck**: cd frontend && npm run test:types`, plus a note that `npm run build` deliberately does **not** typecheck tests.

devDependencies to add (all Vite 6 / React 19 / TS 5.8 compatible):

| Package | Version | Why |
|---------|---------|-----|
| `vitest` | `^3.2` | runner |
| `jsdom` | `^26` | DOM environment |
| `@testing-library/react` | `^16.3` | React 19 renderer |
| `@testing-library/dom` | `^10.4` | explicit RTL-16 peer — install it, don't rely on hoisting |
| `@testing-library/jest-dom` | `^6.6` | matchers; import the `/vitest` entry point |
| `@testing-library/user-event` | `^14.6` | Mantine's `Popover` target needs the full pointer sequence — `fireEvent.click` can silently no-op |

Test-support files (harness, not tests — but they live in the test tree, so they
are named here and assigned to the **skeleton**, not the test-coder):

- `frontend/tests/setup.ts` — exactly five things:
  1. `import "@testing-library/jest-dom/vitest"`.
  2. A **`window.matchMedia` stub** — MantineProvider's color-scheme manager reads it and every render throws without it. Return `{ matches: false, media, onchange: null }` plus no-op `addListener` / `removeListener` / `addEventListener` / `removeEventListener` / `dispatchEvent` (the deprecated pair included — Mantine still calls them on some paths).
  3. A **`ResizeObserver` stub** class with no-op `observe` / `unobserve` / `disconnect` — `Menu` → `Popover` → floating-ui's `autoUpdate` needs it.
  4. An `Element.prototype.scrollIntoView` no-op for Mantine's menu keyboard nav.
  5. `afterEach(() => { cleanup(); localStorage.clear(); })` — `cleanup()` manually because `globals: false` means RTL does not self-register it, and `localStorage.clear()` because gate tests seed tokens and MantineProvider writes a color-scheme key.
- `frontend/tests/support/render.tsx` — `renderWithProviders(ui, { route })`, wrapping in `MantineProvider theme={theme} env="test"` and, when `route` is given, `MemoryRouter initialEntries={[route]}`. **`env="test"` is essential** — no portals, no transitions, so an opened `Menu` renders inline and synchronously, with no `waitFor` and no `document.body` spelunking. Omit `defaultColorScheme`.

**Pages are NOT edited.** `UsersPage`, `LlmServersPage` and `DatabasePage` keep
their own `<Container size="lg" py="md">`. Because `AppShell`'s `padding`
defaults to `0` and the plan omits it, `<main>` adds no padding and those
Containers supply exactly the padding they do today — the content area is
visually unchanged and the diff touches zero page files.

## Test files

- `frontend/tests/harness.test.tsx`
- `frontend/tests/admin/adminGate.test.ts`
- `frontend/tests/admin/navItems.test.ts`
- `frontend/tests/admin/AdminNav.test.tsx`
- `frontend/tests/admin/AdminUserMenu.test.tsx`
- `frontend/tests/admin/AdminShell.test.tsx`
- `frontend/tests/admin/routes.test.tsx`

### Notes the blind test-coder cannot infer — read all of them

- **`globals: false`.** Every test file must import its own primitives:
  `import { describe, it, expect, vi, beforeEach } from "vitest"`.
- Always render via `renderWithProviders` from `tests/support/render.tsx`. Never
  bare RTL `render` — Mantine components need the provider.
- Mantine `NavLink` marks the active item with **`data-active="true"`** on the
  root `<a>` and **omits the attribute entirely** when inactive. So
  `not.toHaveAttribute("data-active")` is the valid negative assertion.
- `AppShell.Header` renders `<header>` (role `banner`), `AppShell.Navbar` renders
  `<nav>` (role `navigation`), `AppShell.Main` renders `<main>` (role `main`).
- `Burger`'s `data-opened` sits on an inner `<Box>`, not on the button — **do not
  assert it**. Assert the `aria-expanded` the component passes to the button.
- `pathname` is basename-stripped by the router, so `MemoryRouter` routes are
  `/`, `/llm-servers`, `/database` — no basename divergence from production.
- The three real pages **fetch on mount**. A routes test may exercise **only** the
  catch-all branch; never mount a real page.
- Mock the **`auth.ts` seam** (`vi.mock` of `src/auth.ts`), not `window.location`.
  This extends the repo's documented rule ("tests mock the `api/` module, not
  `fetch`"). `AdminUserMenu` takes `onLogout` as a prop, so its own test needs no
  mock at all — a `vi.fn()` suffices.
- Mock `src/utils/navigate.ts` to assert the gate enforcer's navigation.
- jsdom does **not throw** on `window.location.href =`; it logs
  `Not implemented: navigation` to the virtual console and leaves `location`
  unchanged. The `navigateTo` seam exists for **assertability**, not
  crash-avoidance — do not chase a phantom crash.

## Interface intent

### `navigateTo` — `frontend/src/utils/navigate.ts`

Takes an absolute href string, performs a full page navigation, returns nothing.
One statement; its entire purpose is to be a mockable module boundary. Its doc
comment must state the rule: **cross-SPA navigation only; in-SPA navigation is
react-router.**

### `AdminAccessDecision` — `frontend/src/admin/adminGate.ts`

A discriminated result with exactly two variants: "may mount", or "may not, send
the browser to this absolute href".

### `resolveAdminAccess` — `adminGate.ts`

**Pure** (it reads `getToken()` / `getCurrentUser()`; no navigation, no writes).
Takes nothing, returns an `AdminAccessDecision`. Rules, in order:

1. No access token → deny, target `"/login/"`.
2. Token present but `getCurrentUser()` returns `null` (malformed / undecodable)
   → deny, target `"/login/"` — a session we cannot read is a broken session.
3. `role !== "admin"` → deny, target `"/"`.
4. Otherwise → allow.

It must **not** clear tokens in case 3 — that token is valid for the user SPA.

*Why `/` and not `/login/` for a non-admin:* the author **is** authenticated.
Bouncing them to login would be a lie and would loop (they log in, get bounced
again). `/` is the surface they are entitled to, and it matches the header's
"Main site" exit, so the admin SPA has exactly one non-admin exit.

### `enforceAdminAccess` — `adminGate.ts`

Impure. Calls `resolveAdminAccess`; on deny it calls `navigateTo` **exactly once**
with the decision's href and returns `false`; on allow it returns `true` and never
navigates. The boolean means "mount the SPA".

*Gate placement rationale (record it in the code's doc comment too).* The gate
runs in `main.tsx` **before `createRoot`** — not in `App`'s render body (today's
bug: render-phase mutation, StrictMode double-invoke, unmockable, and it makes
`App` unrenderable in a test), not in a `useEffect` (violates "useEffect only at
page level", fires after first paint so unauthorized content flashes, and
StrictMode double-mounts it anyway — strictly worse than today), and not in a
dedicated `<AdminGate>` component inside the router (still needs a side effect
somewhere, inheriting one of the above; its only advantage — re-checking on route
change — is worthless, because the role cannot change without a new token, and
server-side 401s are already handled by `client.ts`'s refresh → `logout()` path).
In `main.tsx` the navigation happens outside React entirely: no render phase, no
effects, no StrictMode double-invocation (module bodies run once), and it fires
before first paint, so there is no unauthorized flash. Splitting into pure
`resolveAdminAccess` + impure `enforceAdminAccess` puts 100% of the branching
logic under unit test and leaves a single untested `if` in an entry file.
Consequences: `App.tsx` becomes gate-free and therefore renderable in tests
(this is what makes the shell testable at all), and nothing tests `main.tsx`
itself (importing it calls `createRoot`) — accepted, covered by a `[manual/live]`
DoD.

### `AdminNavItem` — `navItems.ts`

A declaration record per nav entry: router-relative path, visible label, the
`@tabler` icon component reference, and an optional flag marking the path
exact-match-only.

### `ADMIN_NAV_ITEMS` — `navItems.ts`

A module-level readonly array of three items in display order: Users (`/`,
**exact**, `IconUsers`), LLM Servers (`/llm-servers`, `IconServer2`), Database
(`/database`, `IconDatabase`).

### `isNavItemActive` — `navItems.ts`

Pure. Takes the current pathname and one item; returns whether that item is
active. Exact items match only on string equality. Non-exact items match the path
itself **or** a `/`-delimited descendant — never a bare string prefix, so
`/database` must not light up for `/database-export`. This is the entire fix for
defects 2 and 3, and it is a better contract than trusting react-router's `end`.

### `AdminNav` — `AdminNav.tsx`

`observer`. Props: an optional "a nav item was activated" callback. Reads the
current pathname via react-router's `useLocation()`, maps `ADMIN_NAV_ITEMS` to
Mantine `NavLink`s rendered `component={RouterLink}` with `to`, `label`,
`leftSection`, `active={isNavItemActive(pathname, item)}`, and an `onClick` that
fires the callback. No state, no MobX fields.

*Why `useLocation()` is allowed:* it is react-router's own hook reading router
context (the URL, which react-router owns). It is not a custom `useX` hook and
not reactive app state, so it does not violate the no-custom-hooks rule — and it
is required, because without it nothing re-renders on navigation. `useMatch` is
rejected: it would need one call per item, i.e. a hook in a loop.
`component={RouterNavLink}` is rejected: it cannot set Mantine's `active` prop,
gives zero visual change (no `.active` CSS exists), and would create two sources
of truth for one boolean.

### `AdminUserMenu` — `AdminUserMenu.tsx`

`observer`, **pure props only**: the current user (`CurrentUser | null`) and an
`onLogout` callback. Renders an `UnstyledButton` menu target showing the username
(primary) + role (dimmed) + a chevron. The dropdown carries **Logout** (icon
`IconLogout`, invokes `onLogout`) and **Change password**, which is `disabled`
with a "coming soon" hint. When the user prop is `null` it renders nothing. It
imports nothing from `auth.ts` — that is what keeps its test mock-free.

### `AdminShellState` — in `AdminShell.tsx`

The component state class, in the same `.tsx` as `AdminShell` (mirroring the
`SetPasswordDraft` precedent). One observable boolean — "the navbar is open on
mobile" — default `false`, `makeAutoObservable` in the constructor. **No
methods**; the component assigns directly, per the repo's mutation rules.

*Tradeoff:* a state class rather than `@mantine/hooks`' `useDisclosure`, because
`useDisclosure` is a `useX` hook holding reactive data — banned twice over ("no
custom `useX` hooks"; "`useState` only to own a stable instance, never for
reactive data"). The rule does not distinguish Mantine's hooks from ours, and
carving an exception would be the first crack in a rule the repo enforces
absolutely. Cost: ~12 lines and a MobX observable for one boolean. Benefit:
consistency, plus a home for shell state to grow (desktop collapse, pinning, the
deferred skin picker) without a refactor. `@mantine/hooks` stays unimported
repo-wide after this feature — a useful invariant.

### `AdminShell` — `AdminShell.tsx`

`observer`. Props: `children`. Owns a stable `AdminShellState` via
`useState(() => new AdminShellState())`. Renders `AppShell` with
`header={{ height: 56 }}` (keeping today's 56px),
`navbar={{ width: 220, breakpoint: "sm", collapsed: { mobile: <the negation of the open flag> } }}`,
and **`padding` omitted** (its default is `0`).

- `AppShell.Header`: a full-height `Group`. Left — `Burger` (`hiddenFrom="sm"`,
  `opened` bound to state, `size="sm"`, `aria-label="Toggle navigation"`, and an
  explicit `aria-expanded` bound to the flag) plus the `BookWriter — Admin`
  title. Right — the **Main site** control and `AdminUserMenu`, fed
  `getCurrentUser()` and an `onLogout` that calls `logout()`.
- `AppShell.Navbar` (`p="xs"`): `AdminNav`, given a callback that sets the open
  flag `false`, so a mobile tap closes the drawer.
- `AppShell.Main`: `{children}`.
- It is the only new module importing `auth.ts`.
- **The "Main site" control is a real anchor** — a Mantine
  `Button variant="subtle" component="a" href="/"` with `IconExternalLink` — **not**
  a JS handler and **not** `navigateTo`. This gives correct middle-click /
  ctrl-click / copy-link semantics for free, and makes the regression assertion a
  plain `href` check against `/` rather than `/admin/`.
- **`collapsed.mobile` means "is collapsed", i.e. the negation of "is open".**
  Inverting it is the classic `AppShell` bug and it looks correct in a desktop
  browser, where the flag is ignored.
- `AppShell`'s `withBorder` defaults to `true`, which replaces the hand-rolled
  inline `borderBottom` — **delete that inline style**; the border is themed now.
- `children` rather than a react-router layout route / `<Outlet/>`: it keeps
  `routes.tsx` a flat table (one added line), keeps the shell renderable in
  isolation, and introduces no `<Outlet/>` into a repo that has none. There is
  exactly one layout, so a layout route buys nothing.

### `NotFoundPage` — `frontend/src/admin/pages/NotFoundPage.tsx`

`observer`. No props, no state, no `useEffect`, no data load. Its own
`<Container size="lg" py="md">` (consistent with the three real pages) holding a
heading, a dimmed explanation, and a Mantine `Button component={RouterLink} to="/"`
back to Users — a **router** link here, correctly, because it is in-SPA and must
respect `basename`.

### `main.tsx`

Guard `createRoot(...).render(...)` behind `enforceAdminAccess()`. Nothing else.

### `routes.tsx`

Add the terminal `path="*"` → `NotFoundPage`. Existing routes unchanged.

### `App.tsx`

Becomes `MantineProvider theme={theme} defaultColorScheme="dark"` >
`BrowserRouter basename="/admin"` > `AdminShell` > `AdminRoutes`. The
render-phase token check and the inline header both go away.

## Definition of done

- **DoD-0** `[test]` Harness self-check (**expected GREEN at the red gate**; it exercises no new source): a stock Mantine component renders through `renderWithProviders` and a jest-dom matcher asserts on it, proving jsdom + the `matchMedia`/`ResizeObserver` stubs + the matchers + `env="test"` all work.
- **DoD-1** `[test]` With no access token, `resolveAdminAccess()` denies with target `"/login/"`.
- **DoD-2** `[test]` Token present but no decodable identity (`getCurrentUser()` → `null`) → denies with target `"/login/"`.
- **DoD-3** `[test]` Identity with role `"author"` → denies with target `"/"` (**not** `"/login/"`) and does not clear the stored tokens.
- **DoD-4** `[test]` Identity with role `"admin"` → allows.
- **DoD-5** `[test]` `enforceAdminAccess()` returns `false` and calls `navigateTo` exactly once with the denied decision's href; when allowed it returns `true` and `navigateTo` is never called.
- **DoD-6** `[test]` `isNavItemActive`: the Users item (`/`) is active at `/` only — not at `/llm-servers` or `/database`; the Database item is active at `/database` and `/database/anything`, and not at `/`, `/llm-servers`, or `/database-export`.
- **DoD-7** `[test]` `AdminNav` at `/database` marks exactly one link `data-active="true"` (Database); Users and LLM Servers carry no `data-active`. At `/`, exactly Users is active.
- **DoD-8** `[test]` `AdminNav` renders exactly three links labelled Users / LLM Servers / Database with hrefs `/`, `/llm-servers`, `/database`.
- **DoD-9** `[test]` `AdminShell` exposes exactly one `banner`, one `navigation` and one `main` landmark, and renders its `children` inside `main`.
- **DoD-10** `[test]` The header shows the title `BookWriter — Admin` and a link named /main site/ whose `href` is exactly `/` (attribute assertion — the regression guard against `/admin/`).
- **DoD-11** `[test]` The burger button is present with an accessible label, starts `aria-expanded="false"`, becomes `"true"` after a click, and `"false"` after a second click.
- **DoD-12** `[test]` Clicking a navbar link returns the burger to `aria-expanded="false"` (the mobile drawer auto-closes on navigation).
- **DoD-13** `[test]` `AdminUserMenu` given an admin user shows that username and role in the menu target; given `null` it renders nothing.
- **DoD-14** `[test]` Opening the user menu reveals items named /logout/ and /change password/; Change password is **disabled**; clicking Logout invokes the logout callback exactly once; clicking the disabled item invokes nothing.
- **DoD-15** `[test]` In `AdminShell`, activating Logout calls `auth.logout()` exactly once (module-mocked).
- **DoD-16** `[test]` `AdminRoutes` at an unknown path (e.g. `/nope`) renders the not-found page, which offers a link back to `/`; no route page's content appears. *(Tests may not mount the three real pages — they fetch on mount.)*
- **DoD-17** `[manual/live]` Below the `sm` breakpoint the navbar is hidden and the burger visible; above it the navbar is visible and the burger hidden; the burger opens/closes the overlay navbar. *(CSS media queries — `AppShell`'s collapse is CSS-only and the navbar is always in the DOM, so this is structurally unobservable in jsdom.)*
- **DoD-18** `[manual/live]` The active nav item is visibly distinct in the `steel`/dark theme; no browser-default blue link remains anywhere in the shell; the header border is Mantine's themed `withBorder`, not an inline style.
- **DoD-19** `[manual/live]` Live auth matrix: no token → `/login/`; author token → the user SPA at `/`; admin token → the admin shell loads with no flash of admin content; Logout clears **both** localStorage keys and lands on `/login/`; "Main site" performs a full page load of `/` (not `/admin/`); an unknown `/admin/whatever` deep link renders the not-found page (dev `spaFallback`).
- **DoD-20** `[manual/live]` `cd frontend && npm run build` passes, `npm test` is green, `npm run test:types` is clean; the build output keeps its three entries and `tsc` picks up no test file.
- **DoD-21** `[manual/live]` No render-phase `window.location` assignment remains in the admin entry (`src/admin/**` contains no `window.location`), and the admin SPA shows no double navigation under StrictMode.

## Out of scope

1. **Skin / theme / color-scheme selection** — explicitly deferred by the user.
2. **Self-service change password** — backend route, service, schema, product
   UC/US id, and the real modal. Ships as a **disabled** menu item only.
3. **The cross-SPA `src/components/AppLayout|AppHeader|AppSidebar` shells** —
   remain deferred; **nothing lands in `src/components/`**.
4. **The user SPA** — its shell, its render-phase gate in `user/App.tsx`, and a
   link *from* the user SPA *to* `/admin`.
5. **The login entry** and `loginState.ts`'s post-login `/` navigation.
6. **Refactoring `auth.ts::logout`** (or `user/App.tsx`, or `loginState.ts`) onto
   `navigateTo`.
7. Any backend change; any new API call; any new `types/*.d.ts`.
8. **Page bodies** — the three real pages are not edited.
9. A react-router **layout route / `<Outlet/>`** refactor.
10. Role-based nav filtering, nested/collapsible nav, breadcrumbs, desktop navbar
    collapse, persisting navbar state.
11. **Retrofitting tests onto already-delivered features.** The harness lands;
    back-filling coverage is separate work.
12. CI wiring for `npm test`, coverage thresholds, `@vitest/ui`, any E2E /
    browser-mode runner.
13. Changing `basename`, route paths, or `vite.config.ts` (including
    `spaFallback`).
