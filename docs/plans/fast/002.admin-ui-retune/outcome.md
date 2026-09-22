# Outcome — fast feature 002 admin-ui-retune

Intended documentation changes once this feature ships, for the architect to
apply at finalization. Grouped by target architecture file. The coder appends
`## Observations` at the bottom when implementation lands.

## `docs/architecture/frontend.md`

- **"Scaffold scope (feature 002)" (line 104)** — the sentence "the cross-SPA
  `AppLayout` / `AppHeader` / `AppSidebar` shells are not yet built —
  `src/components/` is a seeded-empty folder" stays true **by decision**, but now
  needs its counterpart: the **admin SPA has a real local shell** — an
  `AppShell`-based layout under `admin/components/shell/` (`AdminShell`,
  `AdminNav`, `AdminUserMenu`, `navItems`), deliberately admin-local. State the
  rule that came with the decision: the cross-SPA shells stay deferred until a
  **second** SPA needs the same chrome. Reason: readers must not conclude the
  admin SPA is still chrome-less, nor that `src/components/` was quietly
  populated.

- **"Admin SPA — LLM servers section (feature 006)" (line 106) and "Admin SPA —
  Database section (feature 007)" (line 108)** — both say nav is "still under the
  **minimal local Admin layout**". That is no longer accurate: the admin layout is
  now `AppShell` + a left navbar with a real active indicator + a mobile burger +
  a header user menu (Logout, disabled Change password) + a "Main site" exit + a
  catch-all `path="*"` route. Reword both mentions and add the retune as its own
  short paragraph so the history (minimal → retuned) survives. Reason: two
  sections assert a state this feature replaces.

- **"Testing" (lines 248-251)** — "No frontend test runner is configured in the
  scaffold today" becomes **false**. Replace it with the concrete harness:
  **Vitest + jsdom + React Testing Library**; specs live in `frontend/tests/`
  (mirroring `src/` sub-paths); config in `frontend/vitest.config.ts`
  (`globals: false`, `setupFiles: ./tests/setup.ts`) with `vite.config.ts`
  untouched; tests typecheck through `frontend/tsconfig.test.json` only, so
  `npm run build` **deliberately does not** typecheck tests (`npm run test:types`
  does); component tests render through `tests/support/render.tsx`, which supplies
  `MantineProvider theme={theme} env="test"` (no portals, no transitions) and an
  optional `MemoryRouter`; `tests/setup.ts` stubs `matchMedia`, `ResizeObserver`
  and `scrollIntoView`, which Mantine requires under jsdom. The existing "mock the
  `api/` module, not `fetch`" guidance **holds** and is now extended by precedent
  to **"mock the `auth.ts` seam, not `window.location`"**. Reason: the doc's
  stated absence is now a delivered subsystem, and the conventions above are the
  ones later features must follow.

- **The folder tree at line 93 and the state-ladder row at line 129** —
  `src/utils/` is no longer empty; it holds `navigate.ts`. Name the rule it
  encodes: **cross-SPA navigation goes through `navigateTo`; in-SPA navigation is
  react-router.** Add the honest note that `auth.ts` and the login/user entries
  **still assign `location.href` directly**, pending a later unification (see the
  follow-up below). Reason: the tree lists `utils/` as a placeholder, and the new
  seam is a convention later code must find and follow — including the caveat that
  it is not yet universal.

## Follow-ups spotted at planning (seeds for the coder's `## Observations`)

These are **not** this feature's work. They were found while harvesting and are
recorded so they are not lost.

- **Navigation-seam asymmetry.** `adminGate` uses `navigateTo`, while
  `auth.logout`, `user/App.tsx` and `loginState.ts` still assign `location.href`
  directly. Deliberate: `auth.ts` is delivered code with three live call sites in
  `api/client.ts`'s 401/refresh path, its contract is documented, and it carries a
  "MUST NOT import from `src/api/`" leaf constraint. Unify when the user SPA gets
  the same shell treatment.
- **A missing nav edge.** `loginState.ts` sends every successful login to `/`, and
  after this feature there is still no link from the user SPA to `/admin`. So an
  admin logs in, lands on the user SPA, and must hand-type `/admin` — while we
  ship a polished "Main site" exit out of admin. The retune is one-directional by
  the brief's own wording. The fix (an admin-only "Admin" entry in the user SPA's
  header) is genuinely blocked on the user SPA having a header at all, i.e. on the
  deferred cross-SPA shells.
- **`user/App.tsx` keeps its render-phase gate** — the same defect this feature
  fixes on the admin side. Obvious follow-up.
- **`UserRoutes` is not wrapped in `observer`** (`frontend/src/user/routes.tsx`),
  unlike `AdminRoutes` — a standing violation of the "observer on every component"
  rule, noticed in passing and out of scope here.
- **`getCurrentUser()` decodes the JWT on every `AdminShell` render** (i.e. on
  every burger toggle). Negligible; the inline read was chosen for a simpler
  frozen signature and simpler tests. If it ever matters, capture it as a field on
  `AdminShellState` in the constructor.

<!-- coder appends ## Observations below -->

## Observations

- The repo calls `mobx.configure()` nowhere, so MobX runs with its default
  `enforceActions: "observed"`, under which the established pattern of assigning a
  state-class field directly from a component handler (`CreateUserModal`,
  `SetRoleModal`, and now `AdminShell`'s burger toggle) can emit a strict-mode
  console warning. The convention itself is sound and intentional; only its
  interaction with strict mode is undocumented. Possible impact: in
  `docs/architecture/frontend.md` under the state/mutation rules, say explicitly
  that trivial single-field assignment from a component is sanctioned alongside the
  `runInAction` rule for effectful operations, and record whether an explicit
  `configure({ enforceActions: "never" })` (or "always" plus wrapper actions) is the
  intended posture.
- Mantine's `NavLink` renders its *description* `<span>` unconditionally and stamps
  `data-active` on it as well as on the root `<a>`, so an active nav item matches a
  bare `[data-active="true"]` selector twice. Any future assertion or styling that
  keys off `data-active` must scope to the link element. Possible impact: a short
  caveat in `docs/architecture/frontend.md`'s testing section, beside the existing
  Mantine-under-jsdom notes.
