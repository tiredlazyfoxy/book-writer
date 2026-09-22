/**
 * Full-page browser navigation to an absolute href.
 *
 * **Cross-SPA navigation only. In-SPA navigation is react-router** — use
 * `<Link>` / `<NavLink>` / `useNavigate()` for anything inside the current
 * entry, so the router's `basename` is respected and no reload happens.
 *
 * This module exists to be a **mockable seam**: `vi.mock("src/utils/navigate")`
 * lets a test assert "the browser was sent to X" without touching
 * `window.location`. (jsdom does not throw on `window.location.href = …`; it
 * logs `Not implemented: navigation` and leaves `location` unchanged — so the
 * seam is about *assertability*, not crash-avoidance.)
 */
export function navigateTo(href: string): void {
  window.location.href = href;
}
