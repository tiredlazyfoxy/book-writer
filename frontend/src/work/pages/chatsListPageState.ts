import { makeAutoObservable, runInAction } from "mobx";
import * as chatsApi from "../../api/chats";
import { ApiError } from "../../api/client";
import type { ChatResponse } from "../../types/chats";

/** A chat's sort key — most-recently-modified first (created_at fallback, then 0). */
function chatTimestamp(chat: ChatResponse): number {
  const stamp = chat.modified_at ?? chat.created_at;
  if (stamp === null) return 0;
  const ms = Date.parse(stamp);
  return Number.isNaN(ms) ? 0 : ms;
}

/**
 * Page state for `ChatsListPage` — the content-pane chat list at
 * `/work/:bookId/chats` (023, UC-081 / UC-082 / US-095 / US-096), held via
 * `useState(() => new ChatsListPageState())`.
 *
 * 023 MOVES THE CHAT LIST out of the chat pane and into the content pane (D1),
 * which knowingly inverts `US-095.AC-1` / `US-105.AC-3` / `UC-081` step 1 — the
 * doc reconciliation is `outcome.md`'s obligation, not this file's.
 *
 * The page loads ITS OWN chats rather than sharing `ChatPaneState` (D5): "page =
 * route = fresh state instance", and the redundant fetch is the blessed pattern
 * (`frontend-workspace.md`). The pane is reached only through
 * `work/chatPaneController.ts` — nothing here holds, reads or writes pane state.
 *
 * One async-resource trio (`chats` / `chatsStatus` / `chatsError`), the
 * archived-view flag, and a per-row action status map. Nothing derived is stored:
 * `visibleChats` and `isEmpty` are pure `get` computeds.
 *
 * Per the MobX hard rules this class holds observable data + pure `get` computeds
 * ONLY — no effectful methods, no setters. Loading and archive/restore live in
 * the external `(state, args, signal)` functions below.
 */
export class ChatsListPageState {
  /**
   * Every chat the book has for this author — BOTH the archived and the
   * non-archived set, merged, so that toggling {@link showArchived} is a
   * client-side filter and never a refetch (the `ChatPaneState.visibleChats`
   * shape, kept identical on purpose).
   */
  chats: ChatResponse[] = [];
  chatsStatus: "idle" | "loading" | "ready" | "error" = "idle";
  chatsError: string | null = null;

  /** Whether the list shows archived chats (restore view) instead of active ones. */
  showArchived = false;

  /**
   * Per-row action status for archive/restore, keyed by chat id — so one row's
   * in-flight PATCH disables and reports on that row alone, never the whole list.
   * A row with no entry is `"idle"` by absence.
   */
  actionStatus: Record<string, "idle" | "loading" | "error"> = {};

  constructor() {
    makeAutoObservable(this);
  }

  /**
   * The empty-vs-loaded distinction: `true` when {@link visibleChats} is empty,
   * so the page renders an empty state for a book with no chats (and for an
   * archived view with nothing archived) rather than a bare table.
   */
  get isEmpty(): boolean {
    return this.visibleChats.length === 0;
  }

  /**
   * The chats to show given {@link showArchived} — the active list or the
   * archived view, most-recently-modified first (`created_at` fallback), filtered
   * client-side out of the merged {@link chats}.
   */
  get visibleChats(): ChatResponse[] {
    return this.chats
      .filter((c) => c.archived === this.showArchived)
      .slice()
      .sort((a, b) => chatTimestamp(b) - chatTimestamp(a));
  }
}

/**
 * Load the book's chats into the trio (023).
 *
 * Fetches BOTH sets — `chatsApi.listChats(bookId, false, signal)` and
 * `chatsApi.listChats(bookId, true, signal)` — and merges them into
 * `state.chats`, so `showArchived` filters what is already loaded instead of
 * triggering a second round trip. Abort-guarded; an `ApiError` becomes an
 * author-facing `chatsError`, anything else rethrows.
 */
export async function loadChats(
  state: ChatsListPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.chatsStatus = "loading";
    state.chatsError = null;
  });

  try {
    // BOTH sets, so `showArchived` is a client-side filter over what is already
    // loaded — archiving a row moves it between the two views with no refetch.
    const active = await chatsApi.listChats(bookId, false, signal);
    if (signal?.aborted) return;
    const archived = await chatsApi.listChats(bookId, true, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chats = [...active, ...archived];
      state.chatsStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.chatsError = err.message;
        state.chatsStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Archive or restore one chat from the list page (023, UC-082 / US-096.AC-1 /
 * US-096.AC-2).
 *
 * Persists through `chatsApi.updateChat(bookId, chatId, { archived }, signal)` —
 * the same single PATCH that serves archive, restore and settings — tracking the
 * call in `state.actionStatus[chatId]` and replacing the matching row in
 * `state.chats` with the returned chat on success, so the round trip is
 * idempotent and the row moves between the two views without a reload.
 * Abort-guarded; an `ApiError` leaves the row's status `"error"`, anything else
 * rethrows.
 */
export async function archiveListChat(
  state: ChatsListPageState,
  bookId: string,
  chatId: string,
  archived: boolean,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    // A whole new map object, not a mutation of the old one: `makeAutoObservable`
    // makes the record deeply observable either way, and replacing it keeps the
    // per-row status a plain value the page can read without a reaction subtlety.
    state.actionStatus = { ...state.actionStatus, [chatId]: "loading" };
  });

  try {
    const updated = await chatsApi.updateChat(bookId, chatId, { archived }, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      // The returned row REPLACES the local one, so archive and restore are the
      // same round trip run twice and the row simply moves between the two views.
      state.chats = state.chats.map((c) => (c.id === updated.id ? updated : c));
      state.actionStatus = { ...state.actionStatus, [chatId]: "idle" };
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        // The failure is the ROW's, not the list's: `chatsError` belongs to the
        // load trio and is left alone so a failed archive never blanks the list.
        state.actionStatus = { ...state.actionStatus, [chatId]: "error" };
      });
      return;
    }
    throw err;
  }
}
