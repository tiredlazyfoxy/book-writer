import { useState, type ReactNode } from "react";
import { makeAutoObservable } from "mobx";
import { observer } from "mobx-react-lite";
import { AppShell, Burger, Button, Group, Title } from "@mantine/core";
import { IconExternalLink } from "@tabler/icons-react";
import { getCurrentUser, logout } from "../../../auth";
import { AdminNav } from "./AdminNav";
import { AdminUserMenu } from "./AdminUserMenu";

/**
 * Component state for {@link AdminShell}, held via
 * `useState(() => new AdminShellState())` — the `SetPasswordDraft` precedent.
 *
 * **No methods**: the component assigns `state.navbarOpened = …` directly, per the
 * repo's mutation rules (trivial single-field assignment from a component is
 * fine).
 *
 * A state class rather than `@mantine/hooks`' `useDisclosure`, because
 * `useDisclosure` is a `useX` hook holding reactive data — banned twice over
 * ("no custom `useX` hooks"; "`useState` only to own a stable instance, never for
 * reactive data"). The rule does not distinguish Mantine's hooks from ours, and
 * carving an exception would be the first crack in a rule the repo enforces
 * absolutely. Cost: a MobX observable for one boolean. Benefit: consistency, plus
 * a home for shell state to grow (desktop collapse, pinning, the deferred skin
 * picker) without a refactor — and `@mantine/hooks` stays unimported repo-wide.
 */
export class AdminShellState {
  /** Is the navbar drawer open on mobile? (Ignored above the `sm` breakpoint.) */
  navbarOpened = false;

  constructor() {
    makeAutoObservable(this);
  }
}

export interface AdminShellProps {
  /** The routed content, rendered inside `AppShell.Main`. */
  children: ReactNode;
}

/**
 * The admin chrome: Mantine `AppShell` with `header={{ height: 56 }}` (today's
 * 56px), `navbar={{ width: 220, breakpoint: "sm", collapsed: { mobile: !opened } }}`
 * and **`padding` omitted** (its default is `0`, so `<main>` adds nothing and the
 * pages' own `<Container size="lg" py="md">` supplies exactly the padding they
 * have today — zero page files are edited).
 *
 * - `AppShell.Header`: a full-height `Group`. Left — `Burger` (`hiddenFrom="sm"`,
 *   `opened` bound to state, `size="sm"`, `aria-label="Toggle navigation"`, plus an
 *   explicit `aria-expanded` bound to the flag) and the `BookWriter — Admin`
 *   title. Right — the **Main site** control and {@link AdminUserMenu}, fed
 *   `getCurrentUser()` and an `onLogout` that calls `logout()`.
 * - `AppShell.Navbar` (`p="xs"`): {@link AdminNav}, given a callback that sets
 *   `navbarOpened = false`, so a mobile tap closes the drawer.
 * - `AppShell.Main`: `{children}`.
 *
 * Notes that are easy to get wrong:
 * - **`collapsed.mobile` means "is collapsed" — the NEGATION of "is open".**
 *   Inverting it is the classic `AppShell` bug and it looks correct in a desktop
 *   browser, where the flag is ignored.
 * - The **"Main site" control is a real anchor** — `Button variant="subtle"
 *   component="a" href="/"` with `IconExternalLink` — **not** a JS handler and
 *   **not** `navigateTo`. That buys correct middle-click / ctrl-click /
 *   copy-link semantics, and makes the regression assertion a plain `href` check
 *   against `/` rather than `/admin/` (a react-router `<Link to="/">` would
 *   resolve through `basename` to `/admin/`, which is defect 6).
 * - `AppShell`'s `withBorder` defaults to `true` and replaces the hand-rolled
 *   inline `borderBottom` — that inline style is deleted, the border is themed.
 * - `children` rather than a react-router layout route / `<Outlet/>`: keeps
 *   `routes.tsx` a flat table, keeps the shell renderable in isolation, and
 *   introduces no `<Outlet/>` into a repo that has none. There is exactly one
 *   layout, so a layout route buys nothing.
 *
 * This is the only new module importing `auth.ts` at runtime.
 */
export const AdminShell = observer(function AdminShell({ children }: AdminShellProps) {
  const [state] = useState(() => new AdminShellState());

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{
        width: 220,
        breakpoint: "sm",
        // `collapsed.mobile` is "is collapsed" — the NEGATION of "is open".
        collapsed: { mobile: !state.navbarOpened },
      }}
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger
              opened={state.navbarOpened}
              onClick={() => {
                state.navbarOpened = !state.navbarOpened;
              }}
              hiddenFrom="sm"
              size="sm"
              aria-label="Toggle navigation"
              // `Burger` does not emit `aria-expanded` itself — it only spreads
              // `...others` onto its button, and its own `data-opened` sits on an
              // inner element. Pass the state explicitly.
              aria-expanded={state.navbarOpened}
            />
            <Title order={4}>BookWriter — Admin</Title>
          </Group>

          <Group gap="md" wrap="nowrap">
            {/* A real anchor, not a handler: correct middle-click / ctrl-click /
                copy-link semantics, and `href` is `/` — a react-router `<Link to="/">`
                would resolve through the `/admin` basename to `/admin/`. */}
            <Button
              component="a"
              href="/"
              variant="subtle"
              leftSection={<IconExternalLink size={16} stroke={1.5} />}
            >
              Main site
            </Button>
            <AdminUserMenu user={getCurrentUser()} onLogout={() => logout()} />
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs">
        <AdminNav
          onNavigate={() => {
            state.navbarOpened = false;
          }}
        />
      </AppShell.Navbar>

      <AppShell.Main>{children}</AppShell.Main>
    </AppShell>
  );
});
