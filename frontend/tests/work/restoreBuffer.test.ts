/**
 * Per-item restore buffer — 010.working-page / 004.content-pane-subject-and-buffer,
 * DoD-7 · DoD-8 · DoD-9 · DoD-10 · DoD-11 · DoD-12.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 004):
 *   const RESTORE_BUFFER_KEY_PREFIX = "bookwriter.restore-buffer"
 *   type BufferBaseVersion = number | string
 *   interface BufferedDraft { draft: string; baseVersion: BufferBaseVersion; writtenAt: string }
 *   type WriteResult = { status: "saved" }
 *                    | { status: "saved-after-eviction"; evictedKeys: string[] }
 *                    | { status: "failed" }
 *   restoreBufferKey(bookId, subjectKind, subjectId): string
 *   readBuffer(key): BufferedDraft | null
 *   writeBuffer(key, draft, baseVersion): WriteResult   // stamps writtenAt internally
 *   clearBuffer(key): void
 *
 * Every expected value comes from the spec (`004.context.md` -> "Buffer design" and
 * `frontend-workspace.md`), never from code:
 *   - a written draft round-trips its text, base version and written-at (US-107.AC-1);
 *   - it survives a full reload — a freshly-initialised module reads the same record
 *     from the same store (US-107.AC-2);
 *   - buffers are keyed per `(bookId, subjectKind, subjectId)`; clearing one removes
 *     only that key ("Keyed per item, not per pane");
 *   - it is device-local: a write touches `localStorage` only, no HTTP (US-107.AC-3/AC-4);
 *   - on a quota error it evicts ITS OWN buffers oldest-first, retries between
 *     evictions, never evicts the key being written, and reports what it evicted
 *     ("Accepted limitation — quota");
 *   - reading a missing / unparseable / wrongly-shaped entry returns nothing, never
 *     throws.
 *
 * `tests/setup.ts` runs `localStorage.clear()` in `afterEach`, so each case starts on a
 * clean store. A pure module: no router, no `renderWithProviders`. `globals: false`.
 */
import { describe, expect, it, vi } from "vitest";
import {
  RESTORE_BUFFER_KEY_PREFIX,
  clearBuffer,
  readBuffer,
  restoreBufferKey,
  writeBuffer,
} from "../../src/work/restoreBuffer";

/** True when localStorage holds at least one key under the module's own prefix. */
function hasPrefixedKey(): boolean {
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key !== null && key.startsWith(RESTORE_BUFFER_KEY_PREFIX)) {
      return true;
    }
  }
  return false;
}

describe("writeBuffer / readBuffer round-trip (DoD-7)", () => {
  it("DoD-7: a draft written then read back returns the same text, base version and written-at", () => {
    const key = restoreBufferKey("bk-1", "chapter", "ch-1");
    const result = writeBuffer(key, "chapter one draft", 5);
    expect(result.status).toBe("saved");

    const draft = readBuffer(key);
    expect(draft).not.toBeNull();
    expect(draft?.draft).toBe("chapter one draft");
    // A chapter forks from its numeric `Chapter.version`.
    expect(draft?.baseVersion).toBe(5);
    // `writtenAt` is stamped by the write as an ISO timestamp string.
    expect(typeof draft?.writtenAt).toBe("string");
    expect((draft?.writtenAt ?? "").length).toBeGreaterThan(0);
    expect(Number.isNaN(Date.parse(draft?.writtenAt ?? ""))).toBe(false);
  });

  it("DoD-7: a codex draft round-trips a string base version (the entry's modified_at)", () => {
    const key = restoreBufferKey("bk-1", "codex-entry", "ce-1");
    writeBuffer(key, "codex note", "2026-07-25T10:00:00Z");
    const draft = readBuffer(key);
    expect(draft?.draft).toBe("codex note");
    expect(draft?.baseVersion).toBe("2026-07-25T10:00:00Z");
  });
});

describe("reload survival (DoD-8)", () => {
  it("DoD-8: a buffer survives a full reload — a freshly initialised module reads the same record", async () => {
    const key = restoreBufferKey("bk-1", "chapter", "ch-1");
    writeBuffer(key, "survives reload", 3);

    // Simulate a full page reload: drop the module cache and re-import against the
    // SAME localStorage (which is not cleared between write and re-read here).
    vi.resetModules();
    const fresh = await import("../../src/work/restoreBuffer");
    const draft = fresh.readBuffer(key);

    expect(draft).not.toBeNull();
    expect(draft?.draft).toBe("survives reload");
    expect(draft?.baseVersion).toBe(3);
  });
});

describe("per-item keying (DoD-9)", () => {
  it("DoD-9: writing under one (bookId, kind, id) triple leaves another triple's buffer untouched, and clear removes only its own key", () => {
    const keyA = restoreBufferKey("bk-1", "chapter", "ch-1");
    const keyB = restoreBufferKey("bk-1", "chapter", "ch-2");
    expect(keyA).not.toBe(keyB);

    writeBuffer(keyA, "draft A", 1);
    writeBuffer(keyB, "draft B", 2);
    expect(readBuffer(keyA)?.draft).toBe("draft A");
    expect(readBuffer(keyB)?.draft).toBe("draft B");

    // Clearing A removes ONLY A; B is untouched.
    clearBuffer(keyA);
    expect(readBuffer(keyA)).toBeNull();
    expect(readBuffer(keyB)?.draft).toBe("draft B");
  });

  it("DoD-9: the key varies by book id and by subject kind, not just by subject id", () => {
    const base = restoreBufferKey("bk-1", "chapter", "ch-1");
    expect(restoreBufferKey("bk-2", "chapter", "ch-1")).not.toBe(base);
    expect(restoreBufferKey("bk-1", "codex-entry", "ch-1")).not.toBe(base);
  });
});

describe("device-local, never server-side (DoD-10)", () => {
  it("DoD-10: a write touches localStorage only and issues no HTTP", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    try {
      const key = restoreBufferKey("bk-1", "chapter", "ch-1");
      writeBuffer(key, "local only", 1);

      // No network: a buffered draft is invisible to co-authors and never persisted
      // server-side (US-107.AC-3 / AC-4).
      expect(fetchSpy).not.toHaveBeenCalled();
      // The write landed in localStorage under the module's own prefix.
      expect(hasPrefixedKey()).toBe(true);
      expect(readBuffer(key)).not.toBeNull();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("quota handling (DoD-11)", () => {
  it("DoD-11: on a quota error, evicts its own buffers oldest-first, keeps the current key, and reports the eviction", () => {
    vi.useFakeTimers();
    try {
      const keyOld1 = restoreBufferKey("bk-1", "chapter", "ch-old-1");
      const keyOld2 = restoreBufferKey("bk-1", "chapter", "ch-old-2");
      const keyOld3 = restoreBufferKey("bk-1", "chapter", "ch-old-3");
      const keyCurrent = restoreBufferKey("bk-1", "chapter", "ch-current");

      // Seed three buffers with strictly increasing written-at stamps (oldest first).
      vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
      writeBuffer(keyOld1, "oldest", 1);
      vi.setSystemTime(new Date("2026-01-02T00:00:00Z"));
      writeBuffer(keyOld2, "middle", 2);
      vi.setSystemTime(new Date("2026-01-03T00:00:00Z"));
      writeBuffer(keyOld3, "newest-old", 3);

      // A foreign (non-module) localStorage key the buffer must never evict.
      localStorage.setItem("unrelated-app-key", "keep-me");

      // Make setItem reject with a quota error for its first two attempts (the initial
      // write and the retry after the first eviction), then succeed — so exactly two
      // evictions are forced, proving the oldest-first order.
      let throwsLeft = 2;
      const realSetItem = Storage.prototype.setItem;
      const setItemSpy = vi
        .spyOn(Storage.prototype, "setItem")
        .mockImplementation(function setItemStub(this: Storage, k: string, v: string): void {
          if (throwsLeft > 0) {
            throwsLeft -= 1;
            throw new DOMException("Quota exceeded", "QuotaExceededError");
          }
          realSetItem.call(this, k, v);
        });

      vi.setSystemTime(new Date("2026-01-04T00:00:00Z"));
      const result = writeBuffer(keyCurrent, "current draft", 4);

      setItemSpy.mockRestore();

      // Saved after eviction, naming what it evicted — oldest first, current excluded.
      expect(result.status).toBe("saved-after-eviction");
      if (result.status === "saved-after-eviction") {
        expect(result.evictedKeys).toEqual([keyOld1, keyOld2]);
        expect(result.evictedKeys).not.toContain(keyCurrent);
      }

      // The two oldest were evicted; the newest-old and the current survive.
      expect(readBuffer(keyOld1)).toBeNull();
      expect(readBuffer(keyOld2)).toBeNull();
      expect(readBuffer(keyOld3)).not.toBeNull();
      expect(readBuffer(keyCurrent)?.draft).toBe("current draft");

      // A foreign key is never evicted — the module touches only its own buffers.
      expect(localStorage.getItem("unrelated-app-key")).toBe("keep-me");
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("total read on malformed entries (DoD-12)", () => {
  it("DoD-12: reading an absent key returns null without throwing", () => {
    const key = restoreBufferKey("bk-1", "chapter", "never-written");
    expect(() => readBuffer(key)).not.toThrow();
    expect(readBuffer(key)).toBeNull();
  });

  it("DoD-12: reading an unparseable (non-JSON) entry returns null without throwing", () => {
    const key = restoreBufferKey("bk-1", "chapter", "garbage");
    localStorage.setItem(key, "}{ not json at all");
    expect(() => readBuffer(key)).not.toThrow();
    expect(readBuffer(key)).toBeNull();
  });

  it("DoD-12: reading a wrongly-shaped entry returns null without throwing", () => {
    const key = restoreBufferKey("bk-1", "chapter", "wrong-shape");
    localStorage.setItem(key, JSON.stringify({ unrelated: "value", count: 3 }));
    expect(() => readBuffer(key)).not.toThrow();
    expect(readBuffer(key)).toBeNull();
  });
});
