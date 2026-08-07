import { observer } from "mobx-react-lite";
import type { ReactElement } from "react";
import { Box } from "@mantine/core";
import { beginChatResize, nudgeChatWidth } from "./workspaceShellState";
import type { WorkspaceShellState } from "./workspaceShellState";
import {
  CHAT_WIDTH_KEYBOARD_STEP,
  MAX_CHAT_WIDTH_FRACTION,
  MIN_CHAT_WIDTH_FRACTION,
} from "../../workspaceLayout";

/**
 * The chat pane's drag/keyboard divider (fast/005) — shell chrome sitting on the
 * aside's LEFT edge, not pane content (`ChatPaneSlot`'s props are untouched;
 * `011.chat-panel` owns the pane's contents).
 *
 * A leaf with NO state, NO effect and NO hook: it reads computeds and calls the
 * external effect functions, per `frontend.md`'s component rules. It is the ONLY
 * component allowed to observe `state.chatWidthFraction` — if `WorkspaceShell`
 * read it, every `pointermove` would re-render the whole content pane.
 *
 * The keyboard path (`ArrowLeft` widens, `ArrowRight` narrows) is not a courtesy:
 * jsdom has no layout engine, no `PointerEvent` and no `setPointerCapture`, so it
 * is the ONLY way the persistence and the CSS-variable wiring are verifiable at
 * all. The drag gesture itself is a `[manual/live]` criterion.
 */
export interface ChatResizeHandleProps {
  /** The shell state the handle reads the live width from and drives. */
  state: WorkspaceShellState;
}

export const ChatResizeHandle = observer(function ChatResizeHandle({
  state,
}: ChatResizeHandleProps): ReactElement {
  return (
    <Box
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize chat pane"
      aria-valuemin={Math.round(MIN_CHAT_WIDTH_FRACTION * 100)}
      aria-valuemax={Math.round(MAX_CHAT_WIDTH_FRACTION * 100)}
      aria-valuenow={Math.round(state.chatWidthFraction * 100)}
      tabIndex={0}
      // The aside itself is hidden below `md`, so there is no pane to resize there.
      visibleFrom="md"
      onPointerDown={(event) => {
        // Suppresses the browser's own text-selection drag before it starts.
        event.preventDefault();
        beginChatResize(state);
      }}
      onKeyDown={(event) => {
        // LEFT WIDENS: the pane is right-anchored, so it grows leftward.
        if (event.key === "ArrowLeft") {
          event.preventDefault();
          nudgeChatWidth(state, CHAT_WIDTH_KEYBOARD_STEP);
          return;
        }
        if (event.key === "ArrowRight") {
          event.preventDefault();
          nudgeChatWidth(state, -CHAT_WIDTH_KEYBOARD_STEP);
        }
        // Every other key is ignored — no preventDefault, no state change.
      }}
      style={{
        // Relies on `AppShell.Aside` being `position: fixed` (it is).
        position: "absolute",
        insetBlock: 0,
        insetInlineStart: 0,
        width: 6,
        cursor: "col-resize",
        touchAction: "none",
        zIndex: 1,
      }}
    />
  );
});
