// Per-item draft restore buffer (010/004; UC-092, US-107) — module-level plain
// functions in the `auth.ts` tier: no class, no MobX, no reactivity, and NO
// import from `src/api/`. `localStorage` only (survives a full reload; never
// server-side, so a buffered draft stays private to the author on that device).
//
// One buffer per item, keyed `(bookId, subjectKind, subjectId)`
// (`frontend-workspace.md` → "Keyed per item, not per pane"). A write records the
// base version the draft forked from so a stale-base mismatch is detectable on
// return (`domain-chapter.md` → "Concurrency"). On quota, the module evicts its
// OWN buffers oldest-written-first, never another `localStorage` key and never the
// key currently being written.
//
// SKELETON (004): the key scheme + signatures + result shapes are frozen; every
// body throws until the coder fills them.

import type { SubjectKind } from "./subject";

/**
 * Shared prefix for every buffer key, so eviction can scope to this module's own
 * keys and never touch another `localStorage` consumer (e.g. `auth.ts` tokens).
 */
export const RESTORE_BUFFER_KEY_PREFIX = "bookwriter.restore-buffer";

/**
 * The base version a draft forked from: a chapter's `Chapter.version` (a number)
 * or a codex entry's `modified_at` (an ISO string). Recorded so the stale-base
 * mismatch is detectable without a round-trip.
 */
export type BufferBaseVersion = number | string;

/**
 * A buffered draft record as stored under a key: the draft text, the base version
 * it forked from, and when it was written (an ISO string, stamped by
 * {@link writeBuffer}).
 */
export interface BufferedDraft {
  draft: string;
  baseVersion: BufferBaseVersion;
  writtenAt: string;
}

/**
 * The outcome of a write: saved outright, saved after evicting other buffers (the
 * evicted keys are named so the author can be told), or failed (quota could not be
 * satisfied even after eviction, or another storage error).
 */
export type WriteResult =
  | { status: "saved" }
  | { status: "saved-after-eviction"; evictedKeys: string[] }
  | { status: "failed" };

/**
 * Build the buffer key for one item from its `(bookId, subjectKind, subjectId)`
 * triple. Always begins with {@link RESTORE_BUFFER_KEY_PREFIX}.
 *
 * SKELETON: unimplemented — body throws.
 */
export function restoreBufferKey(
  bookId: string,
  subjectKind: SubjectKind,
  subjectId: string,
): string {
  return `${RESTORE_BUFFER_KEY_PREFIX}:${bookId}:${subjectKind}:${subjectId}`;
}

/**
 * Read the buffered draft under a key, or `null` when the entry is absent,
 * unparseable, or shaped wrong. Never throws.
 *
 * SKELETON: unimplemented — body throws (frozen return type is total).
 */
export function readBuffer(key: string): BufferedDraft | null {
  const raw = localStorage.getItem(key);
  if (raw === null) return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    // Non-JSON entry — treat as absent, never throw.
    return null;
  }

  if (typeof parsed !== "object" || parsed === null) return null;
  const candidate = parsed as {
    draft?: unknown;
    baseVersion?: unknown;
    writtenAt?: unknown;
  };

  if (typeof candidate.draft !== "string") return null;
  if (
    typeof candidate.baseVersion !== "number" &&
    typeof candidate.baseVersion !== "string"
  ) {
    return null;
  }
  if (typeof candidate.writtenAt !== "string") return null;

  return {
    draft: candidate.draft,
    baseVersion: candidate.baseVersion,
    writtenAt: candidate.writtenAt,
  };
}

/**
 * Store a draft under a key, stamping `writtenAt`, and report the outcome. On a
 * quota error, evict this module's own buffers oldest-written-first, retrying
 * between evictions, and never evict `key` itself; name the evicted keys in the
 * result.
 *
 * SKELETON: unimplemented — body throws.
 */
/**
 * Whether a thrown storage error is a quota-exhaustion error. Covers the standard
 * `QuotaExceededError` (code 22), Firefox's `NS_ERROR_DOM_QUOTA_REACHED` (code
 * 1014), and generic error-shaped objects carrying the same name/code (test
 * stubs). Any other error is a hard failure, not something eviction can help.
 */
function isQuotaError(err: unknown): boolean {
  if (err instanceof DOMException) {
    return (
      err.code === 22 ||
      err.code === 1014 ||
      err.name === "QuotaExceededError" ||
      err.name === "NS_ERROR_DOM_QUOTA_REACHED"
    );
  }
  if (typeof err === "object" && err !== null) {
    const e = err as { name?: unknown; code?: unknown };
    return (
      e.name === "QuotaExceededError" ||
      e.name === "NS_ERROR_DOM_QUOTA_REACHED" ||
      e.code === 22 ||
      e.code === 1014
    );
  }
  return false;
}

/**
 * This module's own buffer keys (never another `localStorage` consumer's),
 * excluding `excludeKey` (never evict the key being written), ordered
 * oldest-written-first by each buffer's `writtenAt`. A malformed buffer sorts as
 * oldest so it is cleaned up first.
 */
function collectEvictionCandidates(excludeKey: string): string[] {
  const entries: { key: string; ts: number }[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k === null) continue;
    if (!k.startsWith(RESTORE_BUFFER_KEY_PREFIX)) continue;
    if (k === excludeKey) continue;
    const record = readBuffer(k);
    const ts = record ? Date.parse(record.writtenAt) : 0;
    entries.push({ key: k, ts: Number.isNaN(ts) ? 0 : ts });
  }
  entries.sort((a, b) => a.ts - b.ts);
  return entries.map((e) => e.key);
}

export function writeBuffer(
  key: string,
  draft: string,
  baseVersion: BufferBaseVersion,
): WriteResult {
  const record: BufferedDraft = {
    draft,
    baseVersion,
    writtenAt: new Date().toISOString(),
  };
  const serialized = JSON.stringify(record);

  try {
    localStorage.setItem(key, serialized);
    return { status: "saved" };
  } catch (err) {
    if (!isQuotaError(err)) {
      return { status: "failed" };
    }
  }

  // Quota hit: evict this module's own buffers oldest-first, one at a time,
  // retrying the write between evictions (never a bulk clear), and never evicting
  // the key being written. Name the evicted keys so the caller can tell the author.
  const candidates = collectEvictionCandidates(key);
  const evictedKeys: string[] = [];
  for (const candidate of candidates) {
    localStorage.removeItem(candidate);
    evictedKeys.push(candidate);
    try {
      localStorage.setItem(key, serialized);
      return { status: "saved-after-eviction", evictedKeys };
    } catch (err) {
      if (!isQuotaError(err)) {
        return { status: "failed" };
      }
      // Still over quota — evict the next oldest and retry.
    }
  }

  return { status: "failed" };
}

/**
 * Remove exactly this key's buffer entry. Leaves every other key untouched.
 *
 * SKELETON: unimplemented — body throws.
 */
export function clearBuffer(key: string): void {
  localStorage.removeItem(key);
}
