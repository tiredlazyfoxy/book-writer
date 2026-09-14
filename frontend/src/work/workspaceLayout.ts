// Workspace layout preference (fast/005) — the module tier's sixth member, in the
// `activeChat.ts` / `restoreBuffer.ts` shape: module-level plain functions, no
// class, no MobX, no reactivity, NO import from `src/api/` and NO DOM access.
// `localStorage` only.
//
// The record is **device-local view preference**: it describes THIS SCREEN, not
// this book. It is therefore deliberately NOT in the URL (it must never travel in
// a shared link, unlike the filter/sort/mode query params `frontend.md` mandates)
// and NOT on the server. One single GLOBAL key for the whole workspace —
// deliberately not per book, because a pane width is not a property of a book.
//
// The geometry helpers take every input as an ARGUMENT (`clientX`,
// `viewportWidth`) so they are pure and verifiable without a window — the drag
// gesture itself is unobservable in jsdom, so its entire geometry lives here.
//
// Reads NEVER throw and are TOTAL: a missing entry, an unreadable storage, a
// non-JSON string, a JSON `null`, an array, a bare string or number, and a
// wrong-typed field all resolve to defaults, per field.

/**
 * The single global storage key for the whole workspace layout record.
 * Deliberately NOT per book.
 */
export const WORKSPACE_LAYOUT_KEY = "bookwriter.workspace-layout";

/**
 * The CSS custom property the chat pane's width is driven through. The drag sets
 * it imperatively (via the shell's `autorun`) so no React re-render happens per
 * pointer move.
 */
export const CHAT_WIDTH_CSS_VAR = "--work-chat-width";

/** Chat pane width when nothing is stored, as a fraction of viewport width. */
export const DEFAULT_CHAT_WIDTH_FRACTION = 0.35;

/** Narrowest allowed chat pane width, as a fraction of viewport width. */
export const MIN_CHAT_WIDTH_FRACTION = 0.15;

/** Widest allowed chat pane width, as a fraction of viewport width. */
export const MAX_CHAT_WIDTH_FRACTION = 0.6;

/** One `ArrowLeft` / `ArrowRight` nudge on the resize handle, in fraction units. */
export const CHAT_WIDTH_KEYBOARD_STEP = 0.02;

/** Shortest allowed composer height in PIXELS — approximately two text lines. */
export const MIN_COMPOSER_HEIGHT_PX = 64;

/**
 * Composer height in PIXELS when nothing is stored — approximately three text
 * lines. Deliberately above the minimum: the composer used to auto-grow from two
 * rows to six, so a fixed box at exactly the floor would feel smaller than what
 * authors have today.
 */
export const DEFAULT_COMPOSER_HEIGHT_PX = 96;

/**
 * Tallest allowed composer height, as a fraction of **viewport height** — the
 * transcript can never be squeezed out. Expressed as a fraction (unlike the two
 * pixel constants above) precisely because it depends on the screen.
 */
export const MAX_COMPOSER_HEIGHT_FRACTION = 0.5;

/** One `ArrowUp` / `ArrowDown` nudge on the composer handle, in PIXELS. */
export const COMPOSER_HEIGHT_KEYBOARD_STEP = 24;

/**
 * The persisted layout record. `chatWidth` is a **fraction of viewport width**,
 * always within [{@link MIN_CHAT_WIDTH_FRACTION}, {@link MAX_CHAT_WIDTH_FRACTION}]
 * — it is clamped on read, so a hand-edited storage entry can never widen the pane
 * past its bounds.
 *
 * `composerHeight` is in **PIXELS**, not a fraction — the two bounds are expressed
 * differently on purpose: its lower bound is a text-line count (absolute) while its
 * upper bound is viewport-relative, so only the minimum can be applied on read.
 * Like the rest of this record it is a **device-local view preference**: it
 * describes THIS SCREEN, deliberately not in the URL, not on the server, and
 * deliberately **NOT per book**.
 */
export interface WorkspaceLayout {
  /** Desktop navigator rail flag (orthogonal to the mobile drawer's open flag). */
  navCollapsed: boolean;
  /** Chat pane width as a fraction of viewport width, within the bounds. */
  chatWidth: number;
  /**
   * Chat composer height in PIXELS, at least {@link MIN_COMPOSER_HEIGHT_PX}. The
   * viewport-dependent maximum ({@link MAX_COMPOSER_HEIGHT_FRACTION}) is applied at
   * every point of USE, never on read — this module touches no DOM.
   */
  composerHeight: number;
}

/**
 * Bound a width fraction to [{@link MIN_CHAT_WIDTH_FRACTION},
 * {@link MAX_CHAT_WIDTH_FRACTION}]. Pure. A non-finite input (`NaN`, `Infinity`,
 * `-Infinity`) yields {@link DEFAULT_CHAT_WIDTH_FRACTION} rather than a bound.
 */
export function clampChatWidth(fraction: number): number {
  // A non-finite input is not "too wide" or "too narrow" — it is meaningless, so
  // it resolves to the default rather than to a bound.
  if (!Number.isFinite(fraction)) return DEFAULT_CHAT_WIDTH_FRACTION;
  if (fraction < MIN_CHAT_WIDTH_FRACTION) return MIN_CHAT_WIDTH_FRACTION;
  if (fraction > MAX_CHAT_WIDTH_FRACTION) return MAX_CHAT_WIDTH_FRACTION;
  return fraction;
}

/**
 * The drag's ENTIRE geometry, extracted so it can be verified with no DOM. The
 * pane is **right-anchored**, so the fraction is the distance from the pointer to
 * the right edge over the viewport width, clamped. A non-positive `viewportWidth`
 * yields {@link DEFAULT_CHAT_WIDTH_FRACTION}.
 */
export function chatWidthFromPointer(clientX: number, viewportWidth: number): number {
  if (!Number.isFinite(viewportWidth) || viewportWidth <= 0) return DEFAULT_CHAT_WIDTH_FRACTION;
  // Right-anchored: the pane occupies everything from the pointer to the right
  // edge, so the fraction is that distance over the viewport. A non-finite
  // `clientX` propagates into a non-finite ratio, which the clamp maps to default.
  return clampChatWidth((viewportWidth - clientX) / viewportWidth);
}

/**
 * The CSS length string the custom property is set to: `0.35` becomes `"35vw"`.
 * Rounds to two decimal places so a keyboard-nudged value can never emit float
 * noise such as `"35.000000000000004vw"`.
 */
export function chatWidthCss(fraction: number): string {
  // Two decimal places OF THE PERCENT — `0.35` → `35`, and a float-noisy
  // `0.3700000000000000004` → `37`, never `37.00000000000000004`.
  const percent = Math.round(fraction * 10000) / 100;
  return `${percent}vw`;
}

/**
 * Bound a candidate composer height (pixels) against the minimum and the
 * viewport-dependent maximum. Pure — the viewport height is an ARGUMENT, so this
 * is verifiable with no window.
 *
 * - A non-finite `candidate` yields {@link DEFAULT_COMPOSER_HEIGHT_PX}, then
 *   clamped by the same rules.
 * - The lower bound is always {@link MIN_COMPOSER_HEIGHT_PX}.
 * - The upper bound is `MAX_COMPOSER_HEIGHT_FRACTION × viewportHeight`, **but the
 *   minimum wins when that product falls below it** — a composer thinner than two
 *   lines is unusable.
 * - A `viewportHeight` that is not finite or not positive means the upper bound is
 *   UNKNOWN: the result is clamped against the minimum alone, so a nonsense
 *   environment never shrinks a stored preference.
 */
export function clampComposerHeight(candidate: number, viewportHeight: number): number {
  // A non-finite candidate is not "too tall" or "too short" — it is meaningless,
  // so it resolves to the default and is then bounded by the same rules.
  const height = Number.isFinite(candidate) ? candidate : DEFAULT_COMPOSER_HEIGHT_PX;
  if (height < MIN_COMPOSER_HEIGHT_PX) return MIN_COMPOSER_HEIGHT_PX;
  // A nonsense viewport means the ceiling is UNKNOWN, not zero: clamp against the
  // minimum alone rather than shrinking a stored preference. The next real use
  // re-clamps.
  if (!Number.isFinite(viewportHeight) || viewportHeight <= 0) return height;
  // THE MINIMUM WINS when half the viewport falls below it: on a very short screen
  // a composer thinner than two text lines is unusable, and a short viewport is the
  // rarer problem.
  const maximum = Math.max(MAX_COMPOSER_HEIGHT_FRACTION * viewportHeight, MIN_COMPOSER_HEIGHT_PX);
  if (height > maximum) return maximum;
  return height;
}

/**
 * The composer drag's ENTIRE geometry, extracted so it can be verified with no DOM
 * and no layout engine — the same split {@link chatWidthFromPointer} uses.
 *
 * DELTA-BASED, not absolute: `startHeight + (startY - clientY)`, so dragging
 * UPWARD grows the composer and downward shrinks it. The result goes through
 * {@link clampComposerHeight}.
 */
export function composerHeightFromDrag(
  startHeight: number,
  startY: number,
  clientY: number,
  viewportHeight: number,
): number {
  // DELTA-BASED, never absolute: the handle is not at the composer's exact top edge
  // (there is a `Stack` gap above it), so an absolute formula would make the
  // composer jump to the pointer on the first move. A non-finite input propagates
  // into a non-finite sum, which the clamp maps to the default.
  return clampComposerHeight(startHeight + (startY - clientY), viewportHeight);
}

/**
 * Read the stored layout. NEVER throws and is TOTAL — every unreadable, non-JSON,
 * wrong-shaped or wrong-typed value resolves to the defaults. The fallback is
 * **per field**: a valid `navCollapsed` beside a garbage `chatWidth` keeps the
 * boolean and defaults the number. `chatWidth` is clamped on read.
 */
export function readWorkspaceLayout(): WorkspaceLayout {
  // Built up from the defaults and overwritten FIELD BY FIELD, which is what makes
  // the fallback per field rather than all-or-nothing.
  const layout: WorkspaceLayout = {
    navCollapsed: false,
    chatWidth: DEFAULT_CHAT_WIDTH_FRACTION,
    composerHeight: DEFAULT_COMPOSER_HEIGHT_PX,
  };

  let raw: string | null;
  try {
    raw = localStorage.getItem(WORKSPACE_LAYOUT_KEY);
  } catch {
    // An unreadable storage (disabled, private mode) reads as "nothing stored".
    return layout;
  }
  if (raw === null) return layout;

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    // Non-JSON / garbage entry — treat as absent, never throw.
    return layout;
  }

  // `null`, an array, a bare string and a bare number are all rejected wholesale;
  // only a plain object can contribute a field.
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) return layout;

  const record = parsed as Record<string, unknown>;
  if (typeof record.navCollapsed === "boolean") layout.navCollapsed = record.navCollapsed;
  if (typeof record.chatWidth === "number") layout.chatWidth = clampChatWidth(record.chatWidth);
  // Clamped to the MINIMUM ONLY: the maximum depends on the viewport height, which
  // this DOM-free module has no business knowing. A stored height larger than half
  // of THIS screen is not corrupt data — it is a height chosen on a bigger monitor,
  // and it is corrected the moment it is used.
  if (typeof record.composerHeight === "number" && Number.isFinite(record.composerHeight)) {
    layout.composerHeight = Math.max(record.composerHeight, MIN_COMPOSER_HEIGHT_PX);
  }
  return layout;
}

/**
 * Merge a PARTIAL layout patch over the current record and store the merged whole
 * under {@link WORKSPACE_LAYOUT_KEY} as JSON, touching no other key. Swallows
 * storage errors (quota, private mode) exactly as `activeChat.ts`'s writer does —
 * a device-local view preference is best-effort and must never throw into the
 * caller.
 *
 * The patch is merged over {@link readWorkspaceLayout}'s TOTAL record, not over the
 * raw stored string, so a corrupt store cannot survive a partial write. Two
 * independent state classes own different fields of this one key
 * (`WorkspaceShellState` owns `navCollapsed` + `chatWidth`, `ChatPaneState` owns
 * `composerHeight`); merging is what makes it impossible for either to clobber the
 * other.
 */
export function writeWorkspaceLayout(patch: Partial<WorkspaceLayout>): void {
  try {
    // Exactly one key for the whole workspace — nothing else is touched.
    // Merged over the TOTAL read record, so a partial patch can never drop the other
    // owner's fields and a corrupt store cannot survive the write.
    const merged: WorkspaceLayout = { ...readWorkspaceLayout(), ...patch };
    localStorage.setItem(WORKSPACE_LAYOUT_KEY, JSON.stringify(merged));
  } catch {
    // A device-local view preference is best-effort: a storage failure (quota,
    // disabled storage) must never throw into the caller — the layout simply
    // reverts to the defaults on the next load.
  }
}
