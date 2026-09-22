// Active-chat pointer (011/004; US-105.AC-3) — module-level plain functions in
// the `restoreBuffer.ts` / `auth.ts` tier: no class, no MobX, no reactivity, and
// NO import from `src/api/`. `localStorage` only.
//
// The pointer is **device-local and deliberately NOT in the URL and NOT on the
// server** (`frontend-workspace.md` → "The active-chat pointer lives in the same
// module tier"): the chat pane resolves its active chat from this pointer,
// falling back to the most recent chat by timestamp. One pointer PER BOOK, keyed
// `(bookId)` under this module's own prefix, so writing one book's pointer never
// touches another's.
//
// Reads NEVER throw — a missing, unparseable, or foreign value reads as "no
// pointer" (`null`).
//
// SKELETON (011/004): the key scheme + signatures + result shapes are frozen; the
// read/write/clear bodies throw until the coder fills them. The pure key builder
// is implemented (structural, no behaviour a DoD asserts — the `restoreBufferKey`
// precedent).

/** Shared prefix for every active-chat pointer key, scoped to this module. */
export const ACTIVE_CHAT_KEY_PREFIX = "bookwriter.active-chat";

/**
 * Build the pointer key for one book. Always begins with
 * {@link ACTIVE_CHAT_KEY_PREFIX}.
 */
export function activeChatKey(bookId: string): string {
  return `${ACTIVE_CHAT_KEY_PREFIX}:${bookId}`;
}

/**
 * Read the stored active-chat id for a book, or `null` when absent, unparseable,
 * or shaped wrong. Never throws — a missing, non-JSON, non-string, or empty stored
 * value all read as "no pointer".
 */
export function readActiveChatId(bookId: string): string | null {
  let raw: string | null;
  try {
    raw = localStorage.getItem(activeChatKey(bookId));
  } catch {
    // A storage access error is treated as "no pointer", never rethrown.
    return null;
  }
  if (raw === null) return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    // Non-JSON / garbage entry — treat as absent, never throw.
    return null;
  }

  if (typeof parsed !== "string") return null;
  if (parsed === "") return null;
  return parsed;
}

/**
 * Store the active-chat id for a book, leaving every other book's pointer
 * untouched. Serialized as JSON so {@link readActiveChatId} can reject garbage.
 */
export function writeActiveChatId(bookId: string, chatId: string): void {
  try {
    localStorage.setItem(activeChatKey(bookId), JSON.stringify(chatId));
  } catch {
    // A device-local pointer is best-effort: a storage failure (quota, disabled
    // storage) must never throw into the caller — the pane simply falls back to
    // resolving the most recent chat next load.
  }
}

/**
 * Remove exactly this book's pointer. Leaves every other book's pointer
 * untouched. Never throws.
 */
export function clearActiveChatId(bookId: string): void {
  try {
    localStorage.removeItem(activeChatKey(bookId));
  } catch {
    // Best-effort removal — a storage error is swallowed, never rethrown.
  }
}
