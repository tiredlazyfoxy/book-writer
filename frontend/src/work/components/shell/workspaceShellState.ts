import { makeAutoObservable, runInAction } from "mobx";
import * as booksApi from "../../../api/books";
import { ApiError } from "../../../api/client";
import type { BookDetailResponse } from "../../../types/books";
import {
  CHAT_WIDTH_CSS_VAR,
  DEFAULT_CHAT_WIDTH_FRACTION,
  chatWidthCss,
  chatWidthFromPointer,
  clampChatWidth,
  readWorkspaceLayout,
  writeWorkspaceLayout,
} from "../../workspaceLayout";

/** Navigator width in px when expanded (010/002's hardcoded value, now named). */
export const NAV_EXPANDED_WIDTH = 220;

/** Navigator width in px when collapsed to the icon-only rail. */
export const NAV_RAIL_WIDTH = 54;

/**
 * Shell state for `WorkspaceShell` (`/work/:bookId`), held via
 * `useState(() => new WorkspaceShellState())`.
 *
 * Holds the book-detail async-resource trio (`bookDetail` / `bookDetailStatus` /
 * `bookDetailError`) used for the shell's header chrome, plus the mobile
 * navbar-open flag (the `AdminShellState` precedent). Per the MobX hard rules
 * this class has NO effectful methods — the book load lives in the external
 * `loadWorkspaceBook(state, bookId, signal)` function below.
 *
 * fast/005 adds the layout surface: the desktop rail flag, the live chat-pane
 * width fraction, the drag-in-flight flag, the constant aside width string and the
 * live drag's detach closure — plus the four external effect functions below,
 * which live in `loadWorkspaceBook`'s tier and are never methods.
 */
export class WorkspaceShellState {
  bookDetail: BookDetailResponse | null = null;
  bookDetailStatus: "idle" | "loading" | "ready" | "error" = "idle";
  bookDetailError: string | null = null;
  /** Is the navbar drawer open on mobile? (Ignored above the `sm` breakpoint.) */
  navbarOpened = false;

  /**
   * Desktop icon-rail flag. ORTHOGONAL to `navbarOpened`, which stays the mobile
   * drawer flag — the two are never active at the same viewport.
   */
  navCollapsed: boolean = false;

  /** The live chat-pane width, as a fraction of viewport width. */
  chatWidthFraction: number = DEFAULT_CHAT_WIDTH_FRACTION;

  /** True only while a pointer drag on the resize handle is in flight. */
  resizing: boolean = false;

  /**
   * The aside's width prop string — READONLY and NON-OBSERVABLE, computed once in
   * the constructor from the STORED width, so the pane paints at the remembered
   * width with no flash of the default and so `pointermove` never re-renders the
   * shell. The drag drives the CSS variable instead.
   */
  readonly asideWidthCss: string;

  /** The live drag's detach closure, or `null` when no drag is in flight. Non-observable. */
  resizeDispose: (() => void) | null = null;

  constructor() {
    const layout = readWorkspaceLayout();
    this.navCollapsed = layout.navCollapsed;
    this.chatWidthFraction = layout.chatWidth;
    // MANDATORY `calc(...)` WRAPPER — not stylistic. Mantine's `rem()` passes a
    // string through verbatim only when it starts with `calc(`, `clamp(` or
    // `rgba(`; any other comma-bearing string is split on commas and mangled. A
    // bare `var(--work-chat-width, 35vw)` compiles, typechecks and emits garbage
    // CSS with NO test failure. Never unwrap this.
    //
    // The fallback baked in here is the STORED width, not the default one: the
    // `autorun` that sets the custom property only runs after mount, so a default
    // fallback would paint one frame of a 35% pane before snapping. Frozen at
    // construction and non-observable, so a drag never re-renders the shell.
    this.asideWidthCss = `calc(var(${CHAT_WIDTH_CSS_VAR}, ${chatWidthCss(layout.chatWidth)}))`;
    makeAutoObservable(this, { asideWidthCss: false, resizeDispose: false });
  }

  /**
   * The navbar's px width: the rail width when collapsed, the expanded width
   * otherwise. A derivation, never a setter.
   */
  get navbarWidth(): number {
    return this.navCollapsed ? NAV_RAIL_WIDTH : NAV_EXPANDED_WIDTH;
  }

  /**
   * `chatWidthCss` applied to the live fraction. ONLY the shell's `autorun` and
   * `ChatResizeHandle` may observe this — `WorkspaceShell`'s JSX must never read
   * the live fraction.
   */
  get chatWidthCssValue(): string {
    return chatWidthCss(this.chatWidthFraction);
  }
}

/**
 * Load the book detail into `state` (unimplemented — coder fills). Intent: set
 * `bookDetailStatus = "loading"`, await `booksApi.getBookDetail(bookId, signal)`,
 * `runInAction` the trio to `ready` on success; return silently when
 * `signal?.aborted`; map an `ApiError` (the 403/404 a non-member receives) into
 * an author-facing `bookDetailError` with `bookDetailStatus = "error"`, else
 * rethrow.
 *
 */
export async function loadWorkspaceBook(
  state: WorkspaceShellState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.bookDetailStatus = "loading";
    state.bookDetailError = null;
  });
  try {
    const detail = await booksApi.getBookDetail(bookId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.bookDetail = detail;
      state.bookDetailStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.bookDetailError = err.message;
        state.bookDetailStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Flip the desktop rail flag and persist the WHOLE layout record (both fields read
 * off current state, so no writer can clobber the other one).
 */
export function toggleNavCollapsed(state: WorkspaceShellState): void {
  runInAction(() => {
    state.navCollapsed = !state.navCollapsed;
  });
  writeWorkspaceLayout({ navCollapsed: state.navCollapsed, chatWidth: state.chatWidthFraction });
}

/**
 * Start a pointer drag on the chat pane's divider. Intent: set `resizing`,
 * suppress text selection and pin the `col-resize` cursor on `document.body`, and
 * attach `pointermove` / `pointerup` / `pointercancel` to **`window`** —
 * deliberately NOT `setPointerCapture` (jsdom implements neither that nor
 * `PointerEvent`, and window listeners keep tracking when the pointer outruns the
 * 6px handle). Stores the detach closure on `state.resizeDispose`. IDEMPOTENT: a
 * second call while a drag is live is a no-op. The `pointermove` handler does ONLY
 * one thing — assign `chatWidthFromPointer(event.clientX, window.innerWidth)` to
 * `state.chatWidthFraction`. No storage write, no other state change.
 */
export function beginChatResize(state: WorkspaceShellState): void {
  // Idempotent: a second pointer-down while a drag is already live changes nothing
  // (and must never attach a second set of listeners).
  if (state.resizeDispose !== null) return;

  const handleMove = (event: PointerEvent): void => {
    // The ONLY thing a pointer move does. No storage write here — the width is
    // persisted once, on pointer-up.
    runInAction(() => {
      // `window.innerWidth` is read HERE and nowhere else: the width is a `vw`
      // length, so the browser reflows on viewport change with no resize listener.
      state.chatWidthFraction = chatWidthFromPointer(event.clientX, window.innerWidth);
    });
  };
  const handleEnd = (): void => {
    endChatResize(state);
  };

  // Listeners on `window`, deliberately NOT `setPointerCapture`: jsdom implements
  // neither that nor `PointerEvent`, and window listeners keep tracking when the
  // pointer outruns the 6px handle.
  window.addEventListener("pointermove", handleMove);
  window.addEventListener("pointerup", handleEnd);
  window.addEventListener("pointercancel", handleEnd);

  const previousUserSelect = document.body.style.userSelect;
  const previousCursor = document.body.style.cursor;
  document.body.style.userSelect = "none";
  document.body.style.cursor = "col-resize";

  state.resizeDispose = () => {
    window.removeEventListener("pointermove", handleMove);
    window.removeEventListener("pointerup", handleEnd);
    window.removeEventListener("pointercancel", handleEnd);
    document.body.style.userSelect = previousUserSelect;
    document.body.style.cursor = previousCursor;
  };

  runInAction(() => {
    state.resizing = true;
  });
}

/**
 * End a pointer drag: detach the listeners, restore the body styles, clear
 * `resizing`, and write storage ONCE (the whole record). IDEMPOTENT and safe when
 * no drag is in flight — the shell's unmount cleanup calls it unconditionally.
 */
export function endChatResize(state: WorkspaceShellState): void {
  const dispose = state.resizeDispose;
  // No drag in flight (unmount without one, or a second pointer-up) — nothing to
  // detach, restore or write. This is what makes it idempotent.
  if (dispose === null) return;
  state.resizeDispose = null;
  dispose();
  runInAction(() => {
    state.resizing = false;
  });
  writeWorkspaceLayout({ navCollapsed: state.navCollapsed, chatWidth: state.chatWidthFraction });
}

/**
 * Apply a keyboard delta to the live width fraction, clamped, and persist the
 * whole record.
 */
export function nudgeChatWidth(state: WorkspaceShellState, delta: number): void {
  runInAction(() => {
    state.chatWidthFraction = clampChatWidth(state.chatWidthFraction + delta);
  });
  writeWorkspaceLayout({ navCollapsed: state.navCollapsed, chatWidth: state.chatWidthFraction });
}
