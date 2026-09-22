/**
 * Transcript scroll geometry (fast/010) — a PURE module: no class, no MobX, no
 * DOM access, no import from the pane state. Every value it needs arrives as a
 * plain number.
 *
 * It is pure for exactly the reason `fast/008` extracted its drag geometry and
 * `fast/005` its width geometry: jsdom computes no layout, so a predicate over
 * three plain numbers is the only way to verify the 64px contract at all.
 *
 * It is sited beside its only consumer in `components/chat/` rather than in the
 * `src/work/` module tier because it is chat-pane geometry with no persistence
 * and no cross-page reach — `workspaceLayout.ts` is the tier for device-local
 * persisted layout, and this feature persists nothing.
 */

/**
 * The distance from the bottom, in CSS pixels, within which the transcript counts
 * as "at the bottom" — the user-locked value, roughly one line of prose of slack.
 *
 * Exact-bottom is brittle (fractional scroll heights and browser zoom routinely
 * leave 1–2px, which would silently unpin); a generous ~200px would yank an
 * author who had deliberately scrolled back a little. Neither was chosen.
 */
export const TRANSCRIPT_PIN_THRESHOLD_PX = 64;

/**
 * Is the viewport at the bottom?
 *
 * The distance from the bottom is `scrollHeight - clientHeight - scrollTop`, and
 * the answer is `true` when that distance is **less than or equal to**
 * {@link TRANSCRIPT_PIN_THRESHOLD_PX} — the boundary is INCLUSIVE, so a distance
 * of exactly `64` is pinned.
 *
 * - A viewport with nothing to scroll (`scrollHeight <= clientHeight`) yields a
 *   non-positive distance and is therefore pinned, with no special case.
 * - DEGENERATE INPUT RESOLVES TO PINNED, NEVER TO UNPINNED: if any of the three
 *   numbers is not finite (`NaN`, `±Infinity`), the answer is `true`. This is a
 *   deliberate safety direction rather than defensiveness — an unreadable
 *   measurement must not strand the author away from a reply streaming in. A
 *   wrong `true` costs one unwanted scroll; a wrong `false` is a feature that
 *   appears not to work at all. It also means jsdom's all-zero geometry reads as
 *   pinned, which is the correct default for a fresh pane.
 */
export function isTranscriptPinned(
  scrollTop: number,
  scrollHeight: number,
  clientHeight: number,
): boolean {
  // Degenerate input resolves to PINNED, never to unpinned — see the note above.
  if (
    !Number.isFinite(scrollTop) ||
    !Number.isFinite(scrollHeight) ||
    !Number.isFinite(clientHeight)
  ) {
    return true;
  }
  // Non-positive when there is nothing to scroll, which is pinned with no special
  // case; the comparison is `<=`, so a distance of exactly the threshold is pinned.
  const distanceFromBottom = scrollHeight - clientHeight - scrollTop;
  return distanceFromBottom <= TRANSCRIPT_PIN_THRESHOLD_PX;
}

/**
 * The `scrollTop` value that puts the viewport at its bottom.
 *
 * `scrollHeight - clientHeight`, FLOORED AT `0` (never negative). A
 * non-finite input yields `0` — safe because it coincides with the case where
 * there is nothing to scroll, and assigning a non-finite value to `scrollTop`
 * would be meaningless.
 */
export function transcriptBottomScrollTop(
  scrollHeight: number,
  clientHeight: number,
): number {
  if (!Number.isFinite(scrollHeight) || !Number.isFinite(clientHeight)) return 0;
  return Math.max(0, scrollHeight - clientHeight);
}
