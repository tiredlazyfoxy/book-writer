// The content pane's subject registry (013/013; UC-083, UC-090, UC-092 —
// US-086.AC-1 / US-087.AC-1 / US-107.AC-1) — module-level plain functions in the
// `restoreBuffer.ts` / `activeChat.ts` / `auth.ts` tier: no class, no MobX, no
// reactivity, no React, and NO import from `src/api/`.
//
// It is the seam between the two panes of the working page: a content page
// declares which subject it is showing, the chat pane reads that subject when it
// composes a turn, and the assistant's `canvas` frame is dispatched back to the
// page that is showing the frame's subject — with the restore buffer as the
// fallback when nothing is registered.
//
// WHY THE MODULE TIER: all three obvious alternatives are banned by
// `frontend.md` — React context (none in this repo), a cross-page callback up to
// the shell (pages never call each other), and a custom `useCanvasTarget()` hook
// (no custom `useX` hooks). `frontend.md`'s state ladder puts app-lifetime state
// at module level, and `frontend-workspace.md` prescribes plain functions (not a
// reactive store) for exactly this tier.
//
// SKELETON (013/013): the four signatures, the registration record and the
// identity-token rule are frozen; every body throws until the coder fills them.

import type { CanvasField, CanvasFrame } from "../types/chats";
import type { CodexKind } from "../types/codex";
import { readBuffer, restoreBufferKey, writeBuffer } from "./restoreBuffer";
import type { LoadedSubject } from "./subject";

/**
 * What a content page declares about itself: its `LoadedSubject`, plus the codex
 * kind where the subject is a codex entry.
 *
 * `codexKind` exists because `LoadedSubject` (in `work/subject.ts`, which this
 * feature CONSUMES and does not modify) carries no kind, while the turn request's
 * `codex_kind` field needs one: for UC-076's blank entry there is no row for the
 * backend to read the kind off, so the `/codex/new?kind=` choice has to ride on
 * the wire. For an existing entry it is the loaded row's kind and the backend
 * ignores it — sending it always is simpler and harmless (`013.context.md`).
 * Absent / `null` for every non-codex subject.
 */
export interface ContentSubject extends LoadedSubject {
  codexKind?: CodexKind | null;
}

/**
 * How a page declares its subject: a function returning the subject as it is
 * RIGHT NOW.
 *
 * It is a function, not a plain record, for two reasons:
 *
 * 1. **The subject is not knowable at mount.** Registration happens in the page's
 *    mount/unmount `useEffect` (the one sanctioned use), but an existing codex
 *    entry's kind and archived flag are only known once the load resolves. A
 *    snapshot taken at mount would put a `null` codex kind on every turn the
 *    author sends afterwards; a source is read at SEND time, so it is always
 *    current (`013.context.md` — "the pane reads the current subject at send
 *    time").
 * 2. **It is the identity token.** {@link unregisterContentSubject} is
 *    identity-guarded against exactly this function reference, so a page's own
 *    cleanup closure already holds the token and {@link registerContentSubject}
 *    returns nothing the caller has to thread anywhere.
 */
export type ContentSubjectSource = () => ContentSubject;

/**
 * How a registered page accepts an assistant draft: the same
 * `(field, text)` pair the wire frame carries. `CodexEntryPageState.applyDraft`
 * (step 012) has exactly this shape, so the page registers it directly — no
 * `useCallback` (banned) and no wrapper.
 */
export type CanvasDraftApplier = (field: CanvasField, text: string) => void;

/**
 * The live registration: the declaring page's source function (which is also its
 * identity token) and, for a page that can accept an assistant draft, its
 * apply-draft callback. A list page registers a source with NO callback.
 */
interface ContentSubjectRegistration {
  source: ContentSubjectSource;
  applyDraft?: CanvasDraftApplier;
}

/**
 * The single live registration — module-level, app-lifetime, deliberately NOT
 * observable: nothing renders off it, it is read at send time and written from a
 * mount/unmount effect.
 */
let registration: ContentSubjectRegistration | null = null;

/**
 * Declare the content pane's current subject, optionally with the callback that
 * applies an assistant draft to it.
 *
 * A page calls this in its page-level mount effect and passes the SAME `source`
 * reference to {@link unregisterContentSubject} from that effect's cleanup. The
 * newest registration wins outright — two pages overlap only for the instant of a
 * route transition, and the mounting page is the one the author is looking at.
 *
 * A page with no callback (the three codex LIST pages) is a legitimate subject
 * with no canvas target: it still reaches the turn request, and a `canvas` frame
 * aimed at it falls through to the buffer fallback.
 *
 * Returns nothing: the caller's token is the `source` it already holds.
 */
export function registerContentSubject(
  source: ContentSubjectSource,
  applyDraft?: CanvasDraftApplier,
): void {
  // The newest registration wins outright: during a route transition the page
  // mounting IS the page the author is looking at.
  registration = { source, applyDraft };
}

/**
 * Clear the registration — but ONLY when it still belongs to `source`.
 *
 * The guard is the point: during a route transition the new page mounts before
 * the old page's cleanup runs, so an unguarded clear would wipe the newer page's
 * registration and leave the chat pane subject-less (DoD-9). A late unmount whose
 * `source` is no longer the registered one is a no-op.
 */
export function unregisterContentSubject(source: ContentSubjectSource): void {
  // Identity guard: a late unmount whose registration has already been superseded
  // clears nothing (DoD-9).
  if (registration !== null && registration.source === source) {
    registration = null;
  }
}

/**
 * The subject the content pane is showing right now — read from the registered
 * source at call time — or `null` when nothing is registered.
 *
 * This is what `ChatPaneState`'s send and retry call while composing a turn, so
 * the turn always carries the subject the author currently has open (US-086.AC-1
 * / US-087.AC-1; UC-090 — a list is a subject too). `null` means the turn carries
 * no subject fields at all, which is `011.chat-panel`'s shipped behaviour.
 */
export function currentContentSubject(): ContentSubject | null {
  if (registration === null) return null;
  // Invoked, never snapshotted: an existing entry's kind and archived flag are
  // only known once its load resolves.
  return registration.source();
}

/**
 * Deliver one `canvas` frame (the assistant's draft) for a book. Contract:
 *
 * - A target is registered, it has an apply-draft callback, and its subject's
 *   kind AND id BOTH match the frame's (`frame.subject_id` compared against the
 *   registered `entityId ?? null`, so UC-076's blank entry — null on both sides —
 *   matches) → hand `(frame.field, frame.text)` to that callback. The page then
 *   runs exactly the path a keystroke does; nothing is saved (US-086.AC-2 /
 *   US-087.AC-2).
 * - Otherwise (nothing registered, no callback, or a DIFFERENT subject — the
 *   author navigated away mid-turn) → write the draft into the restore buffer at
 *   `restoreBufferKey(bookId, "codex-entry", frame.subject_id)`, the same key
 *   step 012's page reads on load, so returning to the entry surfaces it through
 *   the path that already exists (US-107.AC-1). The open entry is NEVER
 *   overwritten by a frame aimed at another subject.
 * - A frame for a BLANK entry (`subject_id === null`) with no matching registered
 *   target is DROPPED: there is no key to buffer it under and no row to return to.
 *
 * Never throws into the SSE handler: an unroutable frame is dropped, not an error.
 *
 * Two behaviours the DoD leaves open, settled here:
 *
 * - **Only a `body` frame is buffered.** `restoreBuffer.ts`'s `BufferedDraft.draft`
 *   is a SINGLE string and `012.context.md` settled that it holds the BODY, so
 *   buffering a `name` frame's text would surface as the body on return —
 *   corrupting the entry rather than restoring it. A targetless `name` frame is
 *   therefore dropped, exactly as a targetless blank-entry frame is.
 * - **The fallback's `baseVersion`** is the one already recorded at that key — the
 *   value the page last loaded — and `""` when there is no buffer to inherit from.
 *   The dispatcher has no `modified_at` of its own to hand; a stale value simply
 *   routes the author into step 012's reconciliation view, which surfaces the
 *   buffered draft either way (`013.context.md` — "the correct outcome, not a bug").
 */
export function dispatchCanvasFrame(bookId: string, frame: CanvasFrame): void {
  const target = registration;
  if (target !== null && target.applyDraft !== undefined) {
    const subject = target.source();
    // Kind AND id must both match; `entityId ?? null` makes UC-076's blank entry
    // match null-to-null, and any other subject fall through to the buffer rather
    // than be overwritten by a frame that is not about it.
    if (subject.kind === frame.subject_kind && (subject.entityId ?? null) === frame.subject_id) {
      target.applyDraft(frame.field, frame.text);
      return;
    }
  }

  // A blank entry has no id to key a buffer on and no row to return to, so a
  // frame aimed at one with no matching target is dropped.
  if (frame.subject_id === null) return;
  if (frame.field !== "body") return;

  // The same key step 012's page reads on load, so the draft surfaces through the
  // path that already exists — no extra code on the page side (US-107.AC-1).
  const key = restoreBufferKey(bookId, "codex-entry", frame.subject_id);
  const existing = readBuffer(key);
  writeBuffer(key, frame.text, existing?.baseVersion ?? "");
}
