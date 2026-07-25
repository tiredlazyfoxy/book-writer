import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

/**
 * Vitest config — the repo's frontend test harness (fast/002).
 *
 * Deliberately a SEPARATE file from `vite.config.ts`: Vitest prefers
 * `vitest.config.*` automatically, and `vite dev` / `vite build` ignore this
 * file entirely, so the bundle (three MPA entries, `appType: "mpa"`, the
 * `spaFallback` dev middleware) carries zero risk from the harness.
 *
 * - `globals: false` — every test file imports its own `describe` / `it` /
 *   `expect` / `vi` from `"vitest"`. Consequence: RTL does not self-register
 *   `cleanup()`, so `tests/setup.ts` calls it in an explicit `afterEach`.
 * - `css` is left at its default `false`: CSS imports resolve to empty modules
 *   (nothing asserts styling), which keeps runs fast.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    restoreMocks: true,
    clearMocks: true,
  },
});
