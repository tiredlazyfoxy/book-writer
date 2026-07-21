# Outcome — 002.frontend-scaffold

Intended documentation changes to apply at finalization. The scaffold is
technology/structure and `docs/architecture/frontend.md` already describes this
exact skeleton, so architecture is largely pre-written. Record only the genuine
deltas below; do not restate `frontend.md`.

## `docs/architecture/frontend.md`

- **Section: API layer / `auth.ts` (state ladder — Module-level globals).**
  Change: note the **auth seam** — the scaffold's `src/auth.ts` ships only
  `getToken()` (localStorage read) plus a minimal `logout()` stub, and the
  App.tsx token-gate redirect is deferred. Reason: auth is feature 004, which
  expands `auth.ts` (current-user, real logout/redirect) and adds the token gate;
  recording the seam prevents 004 being read as a rewrite.

- **Section: Folder layout / Theming (scaffold scope note).** Change: record the
  settled 002 scope boundaries as a short note — the Login entry ships a **bare
  placeholder** (real login is 004); the cross-SPA **AppLayout/AppHeader/
  AppSidebar shells are not yet built** (`src/components/` is a seeded-empty
  folder); routing beyond the User health page + an Admin placeholder is
  deferred. Reason: `frontend.md` describes the target shells and login as if
  present; a scope note keeps it honest about what the scaffold actually ships.

- **Section: Testing.** Change: note that **no frontend test runner is
  configured** in the scaffold — verification is `npm run build` (tsc + vite),
  `npx tsc --noEmit`, `npm run dev` serving the three entries, and the live
  `/api/health` call. Reason: `frontend.md`'s "When frontend tests exist…"
  phrasing should be anchored to the fact that none exist yet, so agents don't
  assume a test command.

## `docs/architecture/quick-reference.md` (not yet created)

- Change: once this index is created, it should note the `src/api/` pattern
  (`client.ts` `request<T>` + `ApiError` normalization + `authHeaders`,
  `sse.ts` `streamPost`) and cite the **User health page**
  (`src/user/pages/HealthPage.tsx` + `healthPageState.ts`) as the **reference
  example of the MobX page-state convention** (trio + external
  `load*(state, signal)` + observer + `useState` instance + mount `useEffect`).
  Reason: the health page is the canonical bootstrap of the convention; the
  registry should point new frontend work at it. This is a flag for the
  architect, not a change to author now.
