import { observer } from "mobx-react-lite";
import { ChatPane } from "../chat/ChatPane";
import type { ChatPaneState } from "../chat/chatPaneState";

/**
 * Thin adapter for the workspace's right-hand aside region: forwards the book id
 * and the shell-owned `ChatPaneState` to `ChatPane`. The 010 placeholder notice
 * ("the chat pane is delivered by 011.chat-panel") is gone — the real pane lives
 * here now. No state, no effect of its own.
 *
 * SKELETON (011/004): props frozen; body is a one-line forward to `ChatPane`.
 */
export interface ChatPaneSlotProps {
  bookId: string;
  state: ChatPaneState;
}

export const ChatPaneSlot = observer(function ChatPaneSlot({ bookId, state }: ChatPaneSlotProps) {
  return <ChatPane bookId={bookId} state={state} />;
});
