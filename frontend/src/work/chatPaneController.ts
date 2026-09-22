// The chat-pane controller registry (023) — the SIXTH member of the working
// page's module tier, beside `restoreBuffer.ts`, `activeChat.ts`,
// `contentSubject.ts`, `chapterUndo.ts` and `closeTurn.ts`. Plain module
// functions matching its siblings: no class, no MobX, no reactivity, no React,
// and NO import from `src/api/`.
//
// WHAT PROBLEM IT SOLVES. 023 moves the chat list out of the chat pane and onto
// `ChatsListPage`, a CONTENT-pane page (D1). Picking a row there must open that
// chat in the chat pane WITHOUT changing the route (D5) — but the page and the
// pane are two independent subtrees that never call each other, and all three
// obvious alternatives are banned by `frontend.md`: React context, a cross-page
// callback up to the shell, and a custom `useX` hook. `closeTurn.ts` already
// solved exactly this shape for "post a turn", so this module copies its idiom
// (single module slot, newest registration wins, identity-guarded unregister)
// rather than inventing one.
//
// It is DELIBERATELY smaller than `closeTurn.ts`: one verb, no stored fact, no
// paired-observable bump. `WorkspaceShell` registers a controller inside its
// EXISTING mount effect (the one that already registers the close-turn
// controller) and unregisters it in the same cleanup — no second effect
// (DoD-15).

/**
 * What the chat pane offers a content-pane page: open a chat by id.
 *
 * One verb, because that is the whole seam — the list page never reads pane
 * state, never learns which chat is active, and never navigates. The shell
 * constructs a small object delegating to `pickChat(chatPaneState, bookId, …)`;
 * that object doubles as its own unregister identity token, exactly as
 * `closeTurn.ts` / `contentSubject.ts` treat theirs.
 */
export interface ChatPaneController {
  openChat: (chatId: string) => void;
}

/**
 * The single live controller — module-level, app-lifetime, deliberately NOT
 * observable: it is written from a mount/unmount effect and read at command time,
 * and nothing renders off it.
 */
let controller: ChatPaneController | null = null;

/**
 * Register the chat pane as the open-chat controller.
 *
 * The newest registration wins outright (`registerCloseTurnController`'s rule,
 * and for the same reason: during a route transition the pane mounting IS the one
 * the author is looking at). Returns nothing — the caller's token is the
 * `controller` object it already holds.
 */
export function registerChatPaneController(c: ChatPaneController): void {
  // The newest registration wins outright: during a route transition the pane
  // mounting IS the one the author is looking at.
  controller = c;
}

/**
 * Clear the registration — but ONLY while it still belongs to `c`.
 *
 * The identity guard is the point: a late unmount whose registration has already
 * been superseded must clear nothing, or the newly-mounted pane would be left
 * unreachable (`unregisterCloseTurnController`'s rule verbatim).
 */
export function unregisterChatPaneController(c: ChatPaneController): void {
  // Identity guard: a late unmount whose registration has already been superseded
  // clears nothing.
  if (controller === c) controller = null;
}

/**
 * Ask the chat pane to open the chat `chatId`, returning whether a registered
 * controller handled it: `true` when one was registered and called, `false` when
 * none was.
 *
 * With NO controller registered this is a **no-op returning `false`**, never a
 * throw — the caller is a row click in the content pane, and a missing aside
 * (mobile, or a pane that has not mounted yet) must not turn a click into an
 * error. NOTHING here navigates: opening a chat leaves the URL untouched (D5).
 */
export function requestOpenChat(chatId: string): boolean {
  if (controller === null) return false;
  controller.openChat(chatId);
  return true;
}
