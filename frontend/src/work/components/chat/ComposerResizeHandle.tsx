import { observer } from "mobx-react-lite";
import type { ReactElement } from "react";
import { Box } from "@mantine/core";
import { beginComposerResize, nudgeComposerHeight } from "./chatPaneState";
import type { ChatPaneState } from "./chatPaneState";
import {
  COMPOSER_HEIGHT_KEYBOARD_STEP,
  MAX_COMPOSER_HEIGHT_FRACTION,
  MIN_COMPOSER_HEIGHT_PX,
} from "../../workspaceLayout";

/**
 * The composer's drag/keyboard divider (fast/008) — the horizontal twin of
 * `shell/ChatResizeHandle.tsx`, sitting between the transcript and the composer.
 *
 * A leaf with NO state, NO effect and NO hook: it reads one observable
 * (`state.composerHeight`) and calls the external effect functions
 * (`beginComposerResize` / `nudgeComposerHeight`), per `frontend.md`'s component
 * rules.
 *
 * THE ONE STRUCTURAL DIFFERENCE FROM `ChatResizeHandle`: that handle is absolutely
 * positioned over the aside's edge; this one is an ORDINARY FLOW CHILD of the
 * pane's `Stack`, so it carries `flexShrink: 0` and no positioning at all.
 *
 * It renders exactly one Mantine `Box`:
 * - `role="separator"`, `aria-orientation="horizontal"`,
 *   `aria-label="Resize composer"`, `tabIndex={0}`, and the value triple in
 *   PIXELS — `aria-valuemin` = `MIN_COMPOSER_HEIGHT_PX`, `aria-valuemax` =
 *   `MAX_COMPOSER_HEIGHT_FRACTION × window.innerHeight` rounded, `aria-valuenow` =
 *   the current `composerHeight` rounded.
 * - `visibleFrom="md"` — matching the aside's own breakpoint; there is no pane to
 *   resize below it.
 * - `onPointerDown`: `preventDefault()` then `beginComposerResize(state,
 *   event.clientY)`.
 * - `onKeyDown`: `ArrowUp` GROWS by `+COMPOSER_HEIGHT_KEYBOARD_STEP` and
 *   `ArrowDown` shrinks by the same step, both through `nudgeComposerHeight`, both
 *   calling `preventDefault()`. (Up grows, because the composer grows upward from
 *   the pane's bottom — the same direction as the drag.) Every other key is
 *   ignored.
 * - Inline style: `height: 6`, `flexShrink: 0`, `cursor: "row-resize"`,
 *   `touchAction: "none"`.
 *
 * The keyboard path is not a courtesy: jsdom has no layout engine, no
 * `PointerEvent` and no `setPointerCapture`, so it is the ONLY way the persistence
 * wiring is verifiable at all. The drag gesture itself is `[manual/live]`.
 */
export interface ComposerResizeHandleProps {
  /** The chat-pane state the handle reads the live composer height from and drives. */
  state: ChatPaneState;
}

export const ComposerResizeHandle = observer(function ComposerResizeHandle({
  state,
}: ComposerResizeHandleProps): ReactElement {
  return (
    <Box
      role="separator"
      aria-orientation="horizontal"
      aria-label="Resize composer"
      // The value triple is in PIXELS, because the height is. The ceiling is read
      // from the live viewport here for the same reason it is applied at use
      // everywhere else: `workspaceLayout.ts` touches no DOM.
      aria-valuemin={MIN_COMPOSER_HEIGHT_PX}
      aria-valuemax={Math.round(MAX_COMPOSER_HEIGHT_FRACTION * window.innerHeight)}
      aria-valuenow={Math.round(state.composerHeight)}
      tabIndex={0}
      // The aside itself is hidden below `md`, so there is no pane to resize there.
      visibleFrom="md"
      onPointerDown={(event) => {
        // Suppresses the browser's own text-selection drag before it starts.
        event.preventDefault();
        beginComposerResize(state, event.clientY);
      }}
      onKeyDown={(event) => {
        // UP GROWS: the composer grows upward from the pane's bottom edge — the same
        // direction as the drag.
        if (event.key === "ArrowUp") {
          event.preventDefault();
          nudgeComposerHeight(state, COMPOSER_HEIGHT_KEYBOARD_STEP);
          return;
        }
        if (event.key === "ArrowDown") {
          event.preventDefault();
          nudgeComposerHeight(state, -COMPOSER_HEIGHT_KEYBOARD_STEP);
        }
        // Every other key is ignored — no preventDefault, no state change.
      }}
      style={{
        // An ORDINARY FLOW CHILD of the pane's `Stack`, unlike `ChatResizeHandle`:
        // no positioning at all, and `flexShrink: 0` so the column never eats it.
        //
        // THE HIT TARGET IS 12px, THE LAYOUT FOOTPRINT IS STILL 6px: the negative
        // block margin reclaims 3px of the `Stack`'s `gap="sm"` on each side. At the
        // original bare 6px the strip was an invisible band floating inside ~30px of
        // blank gap — pressing a few pixels off it did nothing at all, which reads as
        // "the resize is broken" rather than "you missed".
        height: 12,
        marginBlock: -3,
        flexShrink: 0,
        cursor: "row-resize",
        touchAction: "none",
        display: "flex",
        alignItems: "center",
      }}
    >
      {/*
        The visible affordance. `pointerEvents: "none"` so the line can never swallow
        the pointer-down the separator above it needs — the whole 12px strip stays
        one grab target.
      */}
      <Box
        style={{
          height: 2,
          width: "100%",
          borderRadius: 1,
          backgroundColor: "var(--mantine-color-default-border)",
          pointerEvents: "none",
        }}
      />
    </Box>
  );
});
