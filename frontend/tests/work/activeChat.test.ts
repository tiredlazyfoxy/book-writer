/**
 * Active-chat pointer — 011.chat-panel / 004.chat-pane-list-and-settings, DoD-4.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 004):
 *   const ACTIVE_CHAT_KEY_PREFIX = "bookwriter.active-chat"
 *   activeChatKey(bookId: string): string                    // pure key builder
 *   readActiveChatId(bookId: string): string | null          // never throws
 *   writeActiveChatId(bookId: string, chatId: string): void
 *   clearActiveChatId(bookId: string): void
 *
 * Every expected value comes from the spec (`004.md` -> Interface intent + DoD-4 and
 * `frontend-workspace.md` -> "The active-chat pointer lives in the same module tier"),
 * never from code:
 *   - the pointer is PER BOOK: writing one book's pointer leaves another book's
 *     untouched, and clearing removes only that book's key;
 *   - it is DEVICE-LOCAL: a write touches `localStorage` only and issues no HTTP,
 *     and it is deliberately not in the URL and not on the server;
 *   - a read NEVER THROWS on garbage — a missing / unparseable / foreign value reads
 *     as "no pointer".
 *
 * A pure module in the `restoreBuffer.ts` / `auth.ts` tier: no class, no MobX, no
 * router, no `renderWithProviders`. `tests/setup.ts` runs `localStorage.clear()` in
 * `afterEach`, so each case starts on a clean store. `globals: false`.
 */
import { describe, expect, it, vi } from "vitest";
import {
  ACTIVE_CHAT_KEY_PREFIX,
  activeChatKey,
  clearActiveChatId,
  readActiveChatId,
  writeActiveChatId,
} from "../../src/work/activeChat";

/** True when localStorage holds at least one key under the module's own prefix. */
function hasPrefixedKey(): boolean {
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key !== null && key.startsWith(ACTIVE_CHAT_KEY_PREFIX)) {
      return true;
    }
  }
  return false;
}

describe("writeActiveChatId / readActiveChatId round-trip (DoD-4)", () => {
  it("DoD-4: a written pointer reads back the same chat id for that book", () => {
    writeActiveChatId("bk-1", "c-42");
    expect(readActiveChatId("bk-1")).toBe("c-42");
  });

  it("DoD-4: a book with no pointer written reads as null (no pointer)", () => {
    expect(readActiveChatId("bk-never-written")).toBeNull();
  });
});

describe("per-book keying (DoD-4)", () => {
  it("DoD-4: writing one book's pointer leaves another book's pointer untouched", () => {
    writeActiveChatId("bk-A", "c-A");
    writeActiveChatId("bk-B", "c-B");

    expect(readActiveChatId("bk-A")).toBe("c-A");
    expect(readActiveChatId("bk-B")).toBe("c-B");
  });

  it("DoD-4: clearing one book's pointer removes only that book's key", () => {
    writeActiveChatId("bk-A", "c-A");
    writeActiveChatId("bk-B", "c-B");

    clearActiveChatId("bk-A");

    expect(readActiveChatId("bk-A")).toBeNull();
    // The other book's pointer is untouched.
    expect(readActiveChatId("bk-B")).toBe("c-B");
  });

  it("DoD-4: the storage key varies by book id and carries the module's own prefix", () => {
    const keyA = activeChatKey("bk-A");
    const keyB = activeChatKey("bk-B");

    expect(keyA).not.toBe(keyB);
    expect(keyA.startsWith(ACTIVE_CHAT_KEY_PREFIX)).toBe(true);
    expect(keyB.startsWith(ACTIVE_CHAT_KEY_PREFIX)).toBe(true);
  });
});

describe("device-local, never server-side (DoD-4)", () => {
  it("DoD-4: a write touches localStorage only and issues no HTTP", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    try {
      writeActiveChatId("bk-1", "c-1");

      // No network: the pointer is device-local, not in the URL and not on the server.
      expect(fetchSpy).not.toHaveBeenCalled();
      // The write landed in localStorage under the module's own prefix.
      expect(hasPrefixedKey()).toBe(true);
      expect(readActiveChatId("bk-1")).toBe("c-1");
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("total read on garbage (DoD-4)", () => {
  it("DoD-4: reading an absent pointer returns null without throwing", () => {
    expect(() => readActiveChatId("bk-1")).not.toThrow();
    expect(readActiveChatId("bk-1")).toBeNull();
  });

  it("DoD-4: reading a garbage stored value never throws", () => {
    // Plant a malformed value at the module's own key, bypassing the writer.
    localStorage.setItem(activeChatKey("bk-1"), "￿ }{ not a normal pointer");
    expect(() => readActiveChatId("bk-1")).not.toThrow();
  });

  it("DoD-4: reading an empty stored value never throws", () => {
    localStorage.setItem(activeChatKey("bk-1"), "");
    expect(() => readActiveChatId("bk-1")).not.toThrow();
  });
});
