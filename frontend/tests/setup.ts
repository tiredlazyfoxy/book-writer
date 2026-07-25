// Vitest setup file (`setupFiles` in vitest.config.ts) — runs once per test file,
// before the file's own imports execute. Five responsibilities, no more:
//
//   1. register the jest-dom matchers (`toBeDisabled`, `toHaveAttribute`, ...),
//   2. stub `window.matchMedia`   — MantineProvider's color-scheme manager reads
//      it and EVERY Mantine render throws without it,
//   3. stub `ResizeObserver`      — `Menu` -> `Popover` -> floating-ui's
//      `autoUpdate` requires it; jsdom does not implement it,
//   4. stub `Element.prototype.scrollIntoView` — Mantine's menu keyboard nav,
//   5. per-test teardown (`cleanup()` + `localStorage.clear()`).
//
// `cleanup()` is explicit because `globals: false` means React Testing Library
// does not self-register its own afterEach hook.

import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

/** Inert MediaQueryList: never matches, never notifies. */
function createMediaQueryList(query: string): MediaQueryList {
  return {
    matches: false,
    media: query,
    onchange: null,
    // The deprecated pair is included on purpose — Mantine still calls
    // addListener/removeListener on some code paths.
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  };
}

Object.defineProperty(window, "matchMedia", {
  writable: true,
  configurable: true,
  value: createMediaQueryList,
});

/** No-op ResizeObserver: observing never fires, which is all floating-ui needs. */
class ResizeObserverStub implements ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

Object.defineProperty(globalThis, "ResizeObserver", {
  writable: true,
  configurable: true,
  value: ResizeObserverStub,
});

Object.defineProperty(Element.prototype, "scrollIntoView", {
  writable: true,
  configurable: true,
  value: () => {},
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});
