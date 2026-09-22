import { observer } from "mobx-react-lite";
import { ScrollArea, Stack } from "@mantine/core";
import { MessageRow } from "./MessageRow";
import { SideChatGroup } from "./SideChatGroup";
import { attachTranscriptViewport, noteTranscriptScroll } from "./chatPaneState";
import type { ChatPaneState } from "./chatPaneState";

/**
 * The conversation transcript for the active chat. Renders
 * `state.renderedTranscript` through {@link import("./MessageRow").MessageRow}:
 * user messages as a bubble, assistant messages through `react-markdown`, each
 * assistant message that carries reasoning preceded by a
 * {@link import("./ThinkingBlock").ThinkingBlock}, plus the in-flight assistant
 * bubble fed from the streaming buffers.
 *
 * IT FILLS, IT DOES NOT CAP (feedback F1). This region consumes whatever vertical
 * space is left between `ChatPane`'s header and its composer and scrolls INSIDE
 * that space. The previous `<ScrollArea.Autosize mah={320}>` was a hard 320px
 * ceiling — it capped the transcript instead of filling the pane, so the composer
 * flowed directly after 320px of content and the rest of the column was left blank.
 * Both that cap and `ChatPane`'s root `h="100%"` are 011-era; 011's in-pane chat
 * list, new-chat form and Save-settings block had been occupying the slack, which is
 * why removing them in 023 is what made the gap visible.
 *
 * AUTHORSHIP IS CARRIED BY THE USER BUBBLE ALONE (D9, narrowed by feedback F2/F3).
 * A user message is a filled, right-offset bubble capped at 70% of the width — the
 * pane is a narrow, resizable aside, where the previous 85% cap was almost
 * indistinguishable from full width and read as a slightly-inset paragraph. The
 * assistant stays FULL WIDTH and now carries no role label and no per-turn divider:
 * with the bubble doing the work they were redundant chrome, and in a narrow column
 * they spent the vertical space F1 exists to reclaim. Assistant output is markdown
 * prose in a writing app, so bubbling it would shorten every line of the content the
 * author actually works with.
 *
 * The `data-role="user"` / `data-role="assistant"` hooks stay exactly where they
 * were — on the element wrapping each message — since they are the delivered
 * authorship contract.
 *
 * Holds NO `useEffect` (frontend.md leaf rule): the one sanctioned imperative
 * side-effect — auto-scroll while streaming — belongs in a single pane-level mount
 * `autorun`, never in this leaf. fast/010 SHIPPED it there: the follow lives in
 * `WorkspaceShell`'s EXISTING mount `autorun`, which reads the pane's transcript
 * growth signature. This leaf still holds no effect — it only hands its scrolling
 * viewport element to the pane state (`viewportRef`) and reports scroll position
 * (`onScrollPositionChange`), both plain props. The leaf rule is unchanged.
 *
 * SIDE CHATS (027 → step 006). The list maps `state.renderedTranscript` and
 * branches on `kind`: `"message"` → {@link import("./MessageRow").MessageRow}
 * (key `item.message.key`), `"sideChat"` →
 * {@link import("./SideChatGroup").SideChatGroup} (key `item.sideChatId`). The
 * group's Inject action needs the book id, which `ChatPaneState` deliberately
 * does not hold (`frontend-workspace.md` → the no-book-id rule), so it arrives
 * as a PROP from `ChatPane` — no context, no hook.
 */
export interface MessageListProps {
  state: ChatPaneState;
  /**
   * The current book id, passed through to each `SideChatGroup`. OPTIONAL ONLY
   * AS A FORWARD-ONLY SPLIT, not a design: `ChatPane.tsx` is step 007's source
   * file, so step 007 wires `<MessageList state={state} bookId={bookId} />`; until
   * then the side-chat Inject / Delete controls render disabled when it is
   * absent (the `026` memos-placeholder idiom).
   */
  bookId?: string;
}

export const MessageList = observer(function MessageList({ state, bookId }: MessageListProps) {
  return (
    <ScrollArea
      type="auto"
      // fast/010: `viewportRef` — and NOT the component's own `ref` — is the only
      // handle on the SCROLLING element; the component's `ref` targets the root,
      // non-scrolling wrapper. A callback ref is a plain prop, not a hook: no
      // `useRef`, no `useCallback`, no `useEffect`, so the leaf rule holds.
      viewportRef={(el) => attachTranscriptViewport(state, el)}
      // The `{ x, y }` argument is ignored on purpose — the pinned predicate needs
      // all three geometry numbers and the element is the truth.
      onScrollPositionChange={() => noteTranscriptScroll(state)}
      style={{
        // F1's fill: the ONLY child of `ChatPane`'s column that grows, so it takes
        // every pixel the header and composer do not.
        flex: 1,
        // The `minHeight: 0` trap: a flex item's automatic minimum size is its
        // CONTENT height, so without this the region refuses to shrink below the
        // conversation's length — it would grow the column and push the composer off
        // the pane's bottom edge instead of scrolling internally. Mantine's
        // `ScrollArea` root is `overflow: hidden` with a `height: 100%` viewport, so
        // a flex-resolved definite height here is exactly what makes it scroll.
        minHeight: 0,
      }}
    >
      <Stack gap="sm" p="xs">
        {state.renderedTranscript.map((item) =>
          item.kind === "message" ? (
            <MessageRow key={item.message.key} state={state} message={item.message} />
          ) : (
            <SideChatGroup
              key={item.sideChatId}
              state={state}
              bookId={bookId}
              group={item}
            />
          ),
        )}
      </Stack>
    </ScrollArea>
  );
});
