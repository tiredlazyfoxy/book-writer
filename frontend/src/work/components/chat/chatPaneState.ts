import { makeAutoObservable, runInAction } from "mobx";
import * as chatsApi from "../../../api/chats";
import { ApiError } from "../../../api/client";
import type {
  ChatMessageResponse,
  ChatResponse,
  ChatSamplingParams,
  CreateChatRequest,
  ModelOptionResponse,
  ToolTraceEntry,
  TurnSubject,
  UpdateChatRequest,
} from "../../../types/chats";
import {
  clearActiveChatId,
  readActiveChatId,
  writeActiveChatId,
} from "../../activeChat";
import { clearCloseTurnActive } from "../../closeTurn";
import type { CloseTurnController } from "../../closeTurn";
import {
  currentContentSelection,
  currentContentSubject,
  dispatchCanvasFrame,
} from "../../contentSubject";
import {
  clampComposerHeight,
  composerHeightFromDrag,
  DEFAULT_COMPOSER_HEIGHT_PX,
  readWorkspaceLayout,
  writeWorkspaceLayout,
} from "../../workspaceLayout";
import { isTranscriptPinned, transcriptBottomScrollTop } from "./transcriptScroll";

/**
 * State for the chat pane (`ChatPane`), owned by `WorkspaceShell` via
 * `useState(() => new ChatPaneState())` and passed explicitly down the tree
 * (frontend.md — no React context). Two async-resource trios (chats,
 * model-options), the device-local active-chat pointer id, the archived-view
 * flag, the new-chat and settings drafts, a `serverErrors` map, and per-action
 * submit statuses.
 *
 * Per the MobX hard rules this class holds observable data + pure `get` computeds
 * ONLY — no effectful methods. Loading, picking, creating, archiving and
 * saving-settings live in the external `(state, …, signal)` functions below.
 *
 * SKELETON (011/004): observable fields + draft/computed shapes are frozen; the
 * getter bodies and the external effect-fn bodies throw for the coder to fill.
 */

/** The model-picker + temperature subset a `ChatSettingsPanel` edits. */
export interface ChatModelSettingsDraft {
  /** The chosen `(server, model)` option key ({@link modelOptionKey}), or none. */
  optionKey: string | null;
  temperature: number;
}

/** The new-chat draft — the settings subset plus a title. */
export interface NewChatDraft extends ChatModelSettingsDraft {
  title: string;
}

/**
 * One entry rendered by `MessageList`: a persisted message or the single in-flight
 * assistant bubble. `role` is the backend's free string (`"user"` / `"assistant"`).
 * `reasoning` is the assistant's thinking (`null` when there is none). `streaming`
 * marks the in-flight bubble, whose thinking expansion is driven by
 * `ChatPaneState.liveThinkingExpanded`; a persisted message uses
 * `ChatPaneState.expandedReasoning[key]` (collapsed by default).
 */
export interface RenderedMessage {
  /** Stable React key — the message id, or a fixed sentinel for the in-flight bubble. */
  key: string;
  role: string;
  content: string;
  reasoning: string | null;
  streaming: boolean;
  /**
   * The tool calls made while this message was produced, in call order (024) —
   * `[]` when none were. For a persisted message this is mapped from the reloaded
   * `ChatMessageResponse.tool_trace` (`null` → `[]`), so `result` / `ok` are
   * always non-null; for the in-flight bubble it is `streamingToolTrace`, where a
   * row still in flight carries `result: null` / `ok: null`.
   */
  toolTrace: ToolTraceRow[];
  /**
   * The side chat this message belongs to (027), or `null` for a main-line row.
   * For a persisted message it is the row's `side_chat_id`; the in-flight bubble
   * carries {@link ChatPaneState.activeSideChatId} so it lands inside the active
   * group. {@link ChatPaneState.renderedTranscript} groups on contiguous runs of
   * equal values (027 → D-B).
   */
  sideChatId: string | null;
}

/**
 * A main-line row of the rendered transcript (027) — one persisted message or
 * the in-flight bubble, outside any side chat.
 */
export type RenderedTranscriptMessageItem = {
  kind: "message";
  message: RenderedMessage;
};

/**
 * One side chat in the rendered transcript (027) — a contiguous run of
 * {@link RenderedMessage}s sharing a non-null `sideChatId`, in position order.
 * `active` is whether it is the chat's `active_side_chat_id`; `expanded` is
 * always `true` for the active group and `expandedSideChats[id] ?? false`
 * (collapsed by default) for a finished one.
 */
export type RenderedTranscriptSideChatItem = {
  kind: "sideChat";
  sideChatId: string;
  messages: RenderedMessage[];
  active: boolean;
  expanded: boolean;
};

/** One item of {@link ChatPaneState.renderedTranscript} — discriminated on `kind`. */
export type RenderedTranscriptItem =
  | RenderedTranscriptMessageItem
  | RenderedTranscriptSideChatItem;

/**
 * One row of the tool-call trace as the pane renders it (024) — the live and the
 * persisted shape unified, so `ToolCallTrace` has ONE thing to render.
 *
 * `result` / `ok` are `null` **exactly while a call is in flight** — between its
 * `tool_call` frame and its `tool_result` frame. A persisted row always has both.
 */
export interface ToolTraceRow {
  toolName: string;
  arguments: Record<string, unknown>;
  result: string | null;
  ok: boolean | null;
}

/**
 * Map a persisted message's wire trace onto the pane's row shape (024) — `null`
 * (no tool ran, or a user message) becomes `[]`.
 *
 * A persisted row is always COMPLETE: it was written after the call returned, so
 * `result` / `ok` are never `null` on this path. Only a live row, between its
 * `tool_call` and `tool_result` frames, carries nulls.
 */
function toolTraceRows(trace: ToolTraceEntry[] | null): ToolTraceRow[] {
  if (trace === null) return [];
  return trace.map((entry) => ({
    toolName: entry.tool_name,
    arguments: entry.arguments,
    result: entry.result,
    ok: entry.ok,
  }));
}

/** Stable React key for the single in-flight assistant bubble (no persisted id yet). */
const STREAMING_MESSAGE_KEY = "__streaming__";

/**
 * The header's model label when there is nothing to name — no active chat, or a
 * chat with no `(server, model)` pair stored on it (023).
 */
const NO_MODEL_LABEL = "No model";

/**
 * The author-facing refusal when the "+" control has no model to create a chat
 * with (023 → D6). UC-054's refuse-to-compose flow survives the removal of the
 * new-chat form: the message moved onto the control that is actually blocked.
 */
const NO_MODEL_OPTIONS_MESSAGE =
  "No model is available yet, so a chat cannot be created. Ask an administrator to " +
  "enable a model on an active server.";

/** The temperature default and bounds surfaced by the picker (feature decision 6). */
export const DEFAULT_TEMPERATURE = 0.8;
export const MIN_TEMPERATURE = 0;
export const MAX_TEMPERATURE = 2;

/**
 * The default sampling set for a brand-new chat (feature decision 6). Only
 * `temperature` is overridden from the new-chat draft; the rest are the recommended
 * defaults the backend also carries. An existing chat's sampling is round-tripped
 * from its own stored values, NOT this constant (decision 4).
 */
const DEFAULT_SAMPLING: ChatSamplingParams = {
  temperature: DEFAULT_TEMPERATURE,
  top_p: 0.95,
  top_k: 40,
  repeat_penalty: 1.1,
  min_p: 0.05,
  max_tokens: null,
  seed: null,
  presence_penalty: 0,
  frequency_penalty: 0,
  enable_thinking: true,
};

/**
 * Canonical encoding of a `(server, model)` option as a single picker value.
 * Pure/structural (the `restoreBufferKey` precedent) — not the model pair itself,
 * which the create/update requests carry as `llm_server_id` + `model_name`.
 */
export function modelOptionKey(option: ModelOptionResponse): string {
  return `${option.server_id}::${option.model_name}`;
}

/** The picker key for a chat's stored `(server, model)` pair, or `null` if unset. */
function optionKeyForChat(chat: ChatResponse): string | null {
  if (chat.llm_server_id === null || chat.model_name === null) return null;
  return `${chat.llm_server_id}::${chat.model_name}`;
}

/** A chat's sort key — most-recently-modified first (created_at fallback, then 0). */
function chatTimestamp(chat: ChatResponse): number {
  const stamp = chat.modified_at ?? chat.created_at;
  if (stamp === null) return 0;
  const ms = Date.parse(stamp);
  return Number.isNaN(ms) ? 0 : ms;
}

/**
 * Resolve which chat should be active for a book: the stored device-local pointer
 * when it still names a non-archived chat, otherwise the most recent non-archived
 * chat by timestamp, otherwise none.
 */
function resolveActiveChatId(state: ChatPaneState, bookId: string): string | null {
  const active = state.chats.filter((c) => !c.archived);
  const stored = readActiveChatId(bookId);
  if (stored !== null && active.some((c) => c.id === stored)) return stored;
  if (active.length === 0) return null;
  const mostRecent = active
    .slice()
    .sort((a, b) => chatTimestamp(b) - chatTimestamp(a))[0];
  return mostRecent.id;
}

/** Seed the settings draft from the current active chat (model pair + temperature). */
function seedSettingsDraft(state: ChatPaneState): void {
  const chat = state.activeChat;
  if (chat === null) return;
  state.settingsDraft.optionKey = optionKeyForChat(chat);
  state.settingsDraft.temperature = chat.sampling.temperature;
}

export class ChatPaneState implements CloseTurnController {
  chats: ChatResponse[] = [];
  chatsStatus: "idle" | "loading" | "ready" | "error" = "idle";
  chatsError: string | null = null;

  modelOptions: ModelOptionResponse[] = [];
  modelOptionsStatus: "idle" | "loading" | "ready" | "error" = "idle";
  modelOptionsError: string | null = null;

  /** The active-chat id (from the device-local pointer / fallback), or none. */
  activeChatId: string | null = null;
  /** Whether the list shows archived chats (restore view) instead of active ones. */
  showArchived = false;

  /**
   * WHICH HEADER POPOVER IS OPEN (023) — the model picker, the settings panel, or
   * neither.
   *
   * ONE DISCRIMINATOR, not two booleans (023 → D7): opening either popover closes
   * the other BY CONSTRUCTION rather than by two flags remembering to disagree,
   * and `sendChatTurn` clears it on acceptance so sending a message closes
   * whatever was open. Nothing else writes it.
   */
  openedPanel: "model" | "settings" | null = null;

  /**
   * THE MODEL DROPDOWN'S SEARCH NEEDLE (fast/009) — the raw text typed into the
   * `"Search models"` field inside the model combobox, `""` when nothing is typed.
   *
   * Two-way bound by `ChatPane`'s search input and read by
   * {@link ChatPaneState.filteredModelOptions}. RESET TO `""` on every open and on
   * every dismissal of the model panel, so a needle never survives a close/reopen
   * (DoD-12). It is deliberately a plain observable next to `openedPanel` rather
   * than a field of a draft: it is view filter text, not an edit awaiting a save.
   */
  modelSearch = "";

  newChatDraft: NewChatDraft = {
    title: "",
    optionKey: null,
    temperature: DEFAULT_TEMPERATURE,
  };
  settingsDraft: ChatModelSettingsDraft = {
    optionKey: null,
    temperature: DEFAULT_TEMPERATURE,
  };

  /** Server-side refusal messages, keyed by field name or a general `form` key. */
  serverErrors: Record<string, string> = {};

  createStatus: "idle" | "loading" | "ready" | "error" = "idle";
  archiveStatus: "idle" | "loading" | "ready" | "error" = "idle";
  settingsStatus: "idle" | "loading" | "ready" | "error" = "idle";

  // --- Conversation half (step 005) ---

  /** The active chat's stored messages (position-ordered), an async-resource trio. */
  messages: ChatMessageResponse[] = [];
  messagesStatus: "idle" | "loading" | "ready" | "error" = "idle";
  messagesError: string | null = null;

  /** The in-flight turn's content buffer — `delta` frames appended as they arrive. */
  streamingContent = "";
  /** The in-flight turn's thinking buffer — `thinking` frames appended as they arrive. */
  streamingThinking = "";
  /**
   * The in-flight turn's tool-call trace (024) — a flat streaming buffer beside
   * `streamingContent` / `streamingThinking`, same pattern. A `tool_call` frame
   * pushes a pending row; the matching `tool_result` frame fills it. Cleared with
   * the other streaming buffers when the turn finishes — the trace the author
   * keeps seeing afterwards comes from the RELOADED message's `tool_trace`, not
   * from here.
   */
  streamingToolTrace: ToolTraceRow[] = [];

  /** The current turn's lifecycle: idle, streaming, or failed. */
  turnStatus: "idle" | "streaming" | "error" = "idle";
  /** The failed turn's author-facing message (set when `turnStatus === "error"`). */
  turnError: string | null = null;

  /** Whether the LIVE (in-flight) thinking region is expanded (auto-collapses on the first delta). */
  liveThinkingExpanded = false;
  /** Per persisted-message reasoning expansion, keyed by message id (collapsed by default). */
  expandedReasoning: Record<string, boolean> = {};

  /**
   * Per tool-trace-row expansion (024), keyed `` `${messageKey}:${rowIndex}` ``
   * — collapsed by default. The row-level twin of {@link expandedReasoning}: a
   * trace row is scoped to its message, so the key has to carry both, and the
   * in-flight bubble's sentinel message key works here unchanged.
   *
   * Written only through {@link toggleToolCallRow} (the external-effect
   * convention), never by the component.
   */
  expandedToolCallRows: Record<string, boolean> = {};

  /**
   * Per finished-side-chat expansion (027), keyed by side-chat id — collapsed by
   * default (US-137.AC-1). The group-level twin of {@link expandedToolCallRows}.
   * The ACTIVE group ignores this map: it is always expanded.
   *
   * Written only through {@link toggleSideChatGroup} (the external-effect
   * convention), as a whole new object per write, never by the component.
   */
  expandedSideChats: Record<string, boolean> = {};

  // --- Side-chat actions (027 step 005) ---

  /**
   * The side-chat ACTION trio's status (027) — `busy` while one of
   * {@link startSideChat} / {@link finishSideChat} / {@link injectSideChat} /
   * {@link deleteSideChat} is in flight, `error` after an `ApiError` refusal,
   * `idle` otherwise. There is deliberately NO `data` member: every action's
   * result is a chat and/or a message array that already lives in `chats` /
   * `messages` — a parallel copy would be a second source of truth (D-F).
   *
   * Read by {@link ChatPaneState.sideChatActionsEnabled}: while `busy` every
   * side-chat control is disabled and every effect refuses to start (D1).
   */
  sideChatActionStatus: "idle" | "busy" | "error" = "idle";
  /** The failed side-chat action's author-facing message (set when `sideChatActionStatus === "error"`). */
  sideChatActionError: string | null = null;

  /**
   * THE SIDE CHAT AWAITING DELETE CONFIRMATION (027 → US-140.AC-1) — its id while
   * the confirmation is open, `null` otherwise. Written only through
   * {@link requestDeleteSideChat} / {@link dismissDeleteSideChat} and cleared by
   * {@link deleteSideChat} on BOTH outcomes, so the modal never stays open over
   * an error banner.
   */
  sideChatDeleteConfirm: string | null = null;

  /** The composer's pending prompt text (cleared only once a send is accepted). */
  pendingPrompt = "";

  // --- The composer's height (fast/008) ---

  /**
   * THE COMPOSER'S LIVE HEIGHT IN PIXELS — a plain observable, read directly by
   * `Composer` and by `ComposerResizeHandle`. Deliberately NOT a CSS custom
   * property driven by an `autorun` (fast/005's width indirection): `Composer`
   * already re-renders per keystroke, so a per-`pointermove` re-render of that same
   * subtree costs the same as ordinary typing.
   *
   * SEEDED IN THE CONSTRUCTOR from `readWorkspaceLayout().composerHeight` passed
   * through `clampComposerHeight` against `window.innerHeight` — this is where the
   * viewport-dependent maximum is first applied, so a height chosen on a larger
   * monitor is corrected on first render rather than overflowing the pane.
   */
  composerHeight: number = DEFAULT_COMPOSER_HEIGHT_PX;

  /** Whether a composer-resize pointer drag is in flight. */
  composerResizing = false;

  /**
   * The live composer drag's detach-and-restore closure, or none. NON-OBSERVABLE
   * (excluded in the constructor beside `start` / `stop` / `setActive`): it is a
   * plain slot the drag lifecycle owns, never something a component renders.
   */
  composerResizeDispose: (() => void) | null = null;

  // --- The transcript's scroll pinning (fast/010) ---

  /**
   * THE SCROLLING TRANSCRIPT ELEMENT, or `null` when nothing is attached — the
   * `ScrollArea`'s internal VIEWPORT div, handed over by `MessageList`'s callback
   * ref (`viewportRef`), NOT the component's root wrapper.
   *
   * NON-OBSERVABLE, excluded in the constructor beside `composerResizeDispose`:
   * it is a raw DOM handle the scroll lifecycle owns, never something a component
   * renders.
   */
  transcriptViewport: HTMLDivElement | null = null;

  /**
   * WHETHER THE TRANSCRIPT IS FOLLOWING THE BOTTOM — `true` from construction, so
   * a fresh pane follows from its very first render with no scroll event needed.
   *
   * NON-OBSERVABLE, and that is LOAD-BEARING rather than stylistic: this flag is
   * rewritten on every scroll event at pointer rate (an observable would fire the
   * pane's observers continuously), and the follow `autorun` READS it — an
   * observable flag would make that autorun re-enter itself on its own
   * programmatic scroll.
   */
  transcriptPinned = true;

  /**
   * The `requestAnimationFrame` id of the follow currently scheduled, or `null`.
   * Used to COALESCE: a streaming turn mutates `streamingContent` per token, and
   * one frame per delta would queue hundreds of redundant scroll writes.
   * NON-OBSERVABLE for the same reason as the two slots above.
   */
  transcriptFollowFrame: number | null = null;

  /** The live turn's abort handle — owned and returned by `streamPost` — or none. */
  turnController: AbortController | null = null;

  // --- The close-chapter turn (016) ---

  /**
   * THE CLOSE CURRENTLY IN PROGRESS, or `null` (016).
   *
   * **Written only through {@link ChatPaneState.setActive}, which only
   * `work/closeTurn.ts` calls** — never assigned by page code, never assigned by
   * an effect in this module. `closeTurn.ts` owns the fact ("is a close running")
   * because it has to be readable independently of which pane mounted first; this
   * field is the pane's OBSERVABLE MIRROR of it, pushed in synchronously so the
   * composer re-renders in the same tick (the paired-observable-bump idiom
   * `contentSubject.ts` / `chapterUndo.ts` already use).
   *
   * It is deliberately NOT derived from `turnStatus`: a page reload mid-close has
   * no stream running and must still show the composer read-only.
   */
  closeTurnActive: { bookId: string; chapterId: string } | null = null;

  constructor() {
    // Hydrated HERE, exactly as `WorkspaceShellState` hydrates the pane width, so
    // the composer paints at the remembered height on the very first frame. This is
    // also where the viewport-dependent maximum is FIRST applied: `readWorkspaceLayout`
    // is DOM-free and clamps to the minimum alone, so a height chosen on a larger
    // monitor is corrected here rather than overflowing this pane.
    this.composerHeight = clampComposerHeight(
      readWorkspaceLayout().composerHeight,
      window.innerHeight,
    );

    // The three `CloseTurnController` members are excluded for the reason
    // `ChapterPageState` excludes `subjectSource` / `applyDraft`: the module tier
    // (`work/closeTurn.ts`) holds this object across the module boundary and calls
    // them itself, and MobX would otherwise wrap each bound member as an action.
    // `composerResizeDispose` joins the exclusion map (fast/008) for the same
    // reason `WorkspaceShellState` excludes its `resizeDispose`: it holds a raw
    // closure the drag lifecycle owns, and MobX would otherwise wrap it as an
    // action. The three `CloseTurnController` entries are untouched.
    // The three transcript-scroll slots (fast/010) join the map for the reason
    // spelled out on each of them: a DOM handle, a flag written at pointer rate and
    // read by the follow `autorun` (an observable one would re-enter that autorun on
    // its own programmatic scroll), and a raw rAF handle. The three
    // `CloseTurnController` entries and `composerResizeDispose` are untouched.
    makeAutoObservable(this, {
      start: false,
      stop: false,
      setActive: false,
      composerResizeDispose: false,
      transcriptViewport: false,
      transcriptPinned: false,
      transcriptFollowFrame: false,
    });
  }

  /**
   * WHETHER THE COMPOSER IS READ-ONLY (016) — `true` for the whole `closing`
   * window, driven by {@link ChatPaneState.closeTurnActive} and NOT by
   * "a stream is running", so a page reload mid-close still renders it read-only
   * (DoD-9).
   *
   * The plan states this as "`closeTurnActive.bookId` matches the pane's own
   * book". **`ChatPaneState` holds no book id** — every effect in this module takes
   * `bookId` as an argument, and the shell already remounts the pane per book
   * (`key={bookId}`), so one pane instance only ever sees one book and the
   * comparison has nothing to compare against. The coder resolves it as
   * "a close is active at all"; **no `bookId` field is added to this class** to
   * manufacture the other side of a comparison that cannot disagree.
   *
   * Pure — no side effects, no I/O.
   */
  get isComposerReadOnly(): boolean {
    return this.closeTurnActive !== null;
  }

  /**
   * WHY the composer is read-only, as author-facing READABLE TEXT — `null` exactly
   * when {@link ChatPaneState.isComposerReadOnly} is `false`, and a non-empty
   * sentence otherwise (the `ChapterPageState.transitionUnavailableReason` shape:
   * a reason must be text a screen reader and a role/label query can reach, never a
   * visual state).
   *
   * The sentence must say that the chapter is being closed and that the close turn
   * owns the conversation until it finishes or is stopped — the author's exit is
   * the chapter page's Stop control, not the composer.
   *
   * Pure.
   */
  get composerReadOnlyReason(): string | null {
    if (!this.isComposerReadOnly) return null;
    return (
      "This chapter is being closed. The close conversation has this chat until it " +
      "finishes, so you cannot send a message here. Use Stop on the chapter's page " +
      "to abandon the close."
    );
  }

  /**
   * `CloseTurnController.start` — post the close turn for `(bookId, chapterId)`.
   *
   * A bound arrow property, excluded from `makeAutoObservable`'s annotations. It
   * delegates to {@link startCloseTurn}, the external effect, so the class keeps no
   * effectful method of its own (the MobX hard rule) and the registry has something
   * to call.
   *
   */
  readonly start = (bookId: string, chapterId: string): void => {
    void startCloseTurn(this, bookId, chapterId);
  };

  /**
   * `CloseTurnController.stop` — abort the live close turn, delegating to
   * {@link stopCloseTurn}. A bound arrow property, as {@link ChatPaneState.start}
   * is.
   */
  readonly stop = (): void => {
    stopCloseTurn(this);
  };

  /**
   * `CloseTurnController.setActive` — the ONLY writer of
   * {@link ChatPaneState.closeTurnActive}, called synchronously by
   * `work/closeTurn.ts` so the composer's read-only state changes in the same tick
   * as the module's own value.
   *
   * A bound arrow property. Writes through `runInAction`, changes nothing else, and
   * never touches the stream: marking a close active does not start one and
   * clearing it does not stop one.
   */
  readonly setActive = (
    active: { bookId: string; chapterId: string } | null,
  ): void => {
    runInAction(() => {
      this.closeTurnActive = active;
    });
  };

  /** The chats to show given `showArchived` — active list or the archived view. */
  get visibleChats(): ChatResponse[] {
    return this.chats
      .filter((c) => c.archived === this.showArchived)
      .slice()
      .sort((a, b) => chatTimestamp(b) - chatTimestamp(a));
  }

  /** The active chat object (resolved from `activeChatId`), or `null`. */
  get activeChat(): ChatResponse | null {
    if (this.activeChatId === null) return null;
    return this.chats.find((c) => c.id === this.activeChatId) ?? null;
  }

  /**
   * The active chat's `active_side_chat_id` (027) — the side chat currently
   * receiving messages — or `null` when there is no active chat or the chat is on
   * its main line.
   */
  get activeSideChatId(): string | null {
    return this.activeChat?.active_side_chat_id ?? null;
  }

  /**
   * WHETHER ANY SIDE-CHAT CONTROL MAY ACT (027 → product D1) — the ONE predicate
   * every side-chat control reads. `false` when there is no active chat, while
   * `turnStatus === "streaming"`, while {@link ChatPaneState.closeTurnActive} is
   * not `null`, or while `sideChatActionStatus === "busy"`; `true` otherwise.
   *
   * Phrased "is a close active at all", never "does the close's book match" —
   * the {@link ChatPaneState.isComposerReadOnly} rule (no book id on this class).
   * Pure.
   */
  get sideChatActionsEnabled(): boolean {
    if (this.activeChat === null) return false;
    if (this.turnStatus === "streaming") return false;
    if (this.closeTurnActive !== null) return false;
    if (this.sideChatActionStatus === "busy") return false;
    return true;
  }

  /**
   * Whether `Start side chat` may act (027 → UC-110 precondition):
   * {@link ChatPaneState.sideChatActionsEnabled} and no side chat is active
   * (`activeSideChatId === null`). Pure.
   */
  get canStartSideChat(): boolean {
    return this.sideChatActionsEnabled && this.activeSideChatId === null;
  }

  /**
   * Whether `Finish side chat` may act (027 → UC-111 precondition):
   * {@link ChatPaneState.sideChatActionsEnabled} and a side chat IS active
   * (`activeSideChatId !== null`). Pure.
   */
  get canFinishSideChat(): boolean {
    return this.sideChatActionsEnabled && this.activeSideChatId !== null;
  }

  /**
   * WHETHER THE AUTHOR HAS AN UNSAVED SETTINGS EDIT (023) — `true` when
   * `settingsDraft`'s `optionKey` / `temperature` diverge from
   * {@link ChatPaneState.activeChat}'s persisted model pair / temperature,
   * `false` when they match and `false` with no active chat.
   *
   * This is the flush test `sendChatTurn` reads before opening the stream (023 →
   * D8): the backend's `prepare_turn` reads the chat's **stored** pair, so an
   * unpersisted change would silently not apply to the very message it was made
   * for. Pure — it decides nothing and persists nothing.
   *
   * AN UNSEEDED DRAFT IS NOT AN EDIT. `seedSettingsDraft` is the one thing that
   * populates this draft from the active chat; until it has run, `optionKey` is
   * `null` and `temperature` is {@link DEFAULT_TEMPERATURE} — values that say
   * "nobody has filled this in yet", not "the author chose these". Read as a raw
   * inequality, such a draft looks dirty against any chat that HAS a model pair,
   * and flushing it would be actively destructive: `saveChatSettings` resolves an
   * unmatched `optionKey` to an EMPTY pair, so the flush would clear the chat's own
   * server/model on the server immediately before a turn that depends on the stored
   * pair — and the send would never open its stream. The guard below is exact
   * rather than a heuristic because the model picker is a `<Select allowDeselect=
   * {false}>`: the author can pick a DIFFERENT option but can never clear the key
   * back to `null`, so "no chosen option while the chat has a pair" can only ever
   * be the unseeded state.
   */
  get settingsDirty(): boolean {
    const chat = this.activeChat;
    // No chat, nothing stored to diverge from — and nothing `sendChatTurn` could
    // flush either, since it no-ops without an active chat.
    if (chat === null) return false;

    const drafted = this.settingsDraft.optionKey;
    const stored = optionKeyForChat(chat);

    // The draft holds no chosen model option while the chat has one: unseeded, so
    // there is nothing to flush. Returned BEFORE the temperature comparison, since
    // an unseeded draft's temperature is the default and would read as an edit too.
    if (drafted === null && stored !== null) return false;

    if (drafted !== stored) return true;
    return this.settingsDraft.temperature !== chat.sampling.temperature;
  }

  /**
   * THE HEADER'S MODEL LABEL (023) — built from
   * {@link ChatPaneState.activeChat}'s **persisted** pair (e.g.
   * `"<server> · <model>"`), NOT from `settingsDraft`, so the header always names
   * the model the next turn will actually use; a placeholder string when the chat
   * has no pair or there is no active chat. Pure.
   */
  get modelLabel(): string {
    const chat = this.activeChat;
    if (chat === null || chat.llm_server_id === null || chat.model_name === null) {
      return NO_MODEL_LABEL;
    }
    // The server's NAME comes from the options list; a pair whose server is no
    // longer offered still names its model rather than falling back to the
    // placeholder — the chat does have a model, it is just not selectable.
    const option = this.modelOptions.find(
      (o) => o.server_id === chat.llm_server_id && o.model_name === chat.model_name,
    );
    if (option === undefined) return chat.model_name;
    return `${option.server_name} · ${option.model_name}`;
  }

  /**
   * THE MODEL OPTIONS THE DROPDOWN SHOWS (fast/009) — the subset of
   * {@link ChatPaneState.modelOptions} whose display label (the existing
   * `"<server_name> · <model_name>"` shape) CONTAINS
   * {@link ChatPaneState.modelSearch}, matched case-insensitively as a plain
   * substring. An empty needle returns every option.
   *
   * ORDER IS `modelOptions`' OWN ORDER — no re-ranking, no fuzzy matching, no
   * grouping (DoD-2). Pure: it filters, it does not fetch; nothing re-loads when
   * the dropdown opens (DoD-13).
   */
  get filteredModelOptions(): ModelOptionResponse[] {
    const needle = this.modelSearch.toLowerCase();
    if (needle === "") return this.modelOptions;
    return this.modelOptions.filter((o) =>
      `${o.server_name} · ${o.model_name}`.toLowerCase().includes(needle),
    );
  }

  /** Whether the new-chat draft can be submitted (a model chosen, temp in range). */
  get canCreateChat(): boolean {
    if (this.createStatus === "loading") return false;
    if (this.newChatDraft.optionKey === null) return false;
    const t = this.newChatDraft.temperature;
    return Number.isFinite(t) && t >= MIN_TEMPERATURE && t <= MAX_TEMPERATURE;
  }

  /** Merged client + server error map for the new-chat / settings surfaces. */
  get errors(): Record<string, string> {
    const client: Record<string, string> = {};
    const t = this.newChatDraft.temperature;
    if (!Number.isFinite(t) || t < MIN_TEMPERATURE || t > MAX_TEMPERATURE) {
      client.temperature = `Temperature must be between ${MIN_TEMPERATURE} and ${MAX_TEMPERATURE}.`;
    }
    // Server refusals override live client validation (the createBookDraft precedent).
    return { ...client, ...this.serverErrors };
  }

  /**
   * Whether the composer may submit: a non-empty (trimmed) `pendingPrompt`, a chat
   * active, and no turn already in flight.
   *
   * SKELETON (011/005): unimplemented — body throws.
   */
  get canSend(): boolean {
    return (
      this.pendingPrompt.trim() !== "" &&
      this.activeChat !== null &&
      this.turnStatus !== "streaming"
    );
  }

  /**
   * Whether a retry is offered — i.e. the last turn failed (`turnStatus === "error"`).
   *
   * SKELETON (011/005): unimplemented — body throws.
   */
  get retryOffered(): boolean {
    return this.turnStatus === "error";
  }

  /**
   * The rendered conversation sequence: the persisted `messages` mapped to
   * {@link RenderedMessage}, plus the single in-flight assistant bubble (fed from
   * `streamingContent` / `streamingThinking`) appended while a turn streams.
   *
   * SKELETON (011/005): unimplemented — body throws.
   */
  get renderedMessages(): RenderedMessage[] {
    const rendered: RenderedMessage[] = this.messages.map((m) => ({
      key: m.id,
      role: m.role,
      content: m.content,
      reasoning: m.reasoning,
      streaming: false,
      sideChatId: m.side_chat_id,
      // THE SEAM (024). This getter is the ONLY place the persisted trace becomes
      // renderable, and it re-derives from `this.messages` — so once `finishTurn`
      // swaps the reloaded array in, the trace the author watched during the turn
      // is still on screen, sourced from the server rather than from the cleared
      // `streamingToolTrace` buffer. No explicit carry-over step exists, or is
      // needed.
      toolTrace: toolTraceRows(m.tool_trace),
    }));
    // The single in-flight assistant bubble, fed from the streaming buffers, is
    // appended only while a turn streams (it carries no persisted id yet).
    if (this.turnStatus === "streaming") {
      rendered.push({
        key: STREAMING_MESSAGE_KEY,
        role: "assistant",
        content: this.streamingContent,
        reasoning: this.streamingThinking === "" ? null : this.streamingThinking,
        streaming: true,
        // The live buffer, read directly: a row still in flight carries
        // `result: null` / `ok: null` and renders as pending.
        toolTrace: this.streamingToolTrace,
        // The in-flight bubble belongs to whatever side chat is active, so it
        // lands INSIDE that group rather than trailing the transcript.
        sideChatId: this.activeSideChatId,
      });
    }
    return rendered;
  }

  /**
   * The rendered transcript (027) — {@link renderedMessages} walked once and
   * folded into main-line `message` items and contiguous `sideChat` groups: a
   * `message` item per null-`sideChatId` row, and a new `sideChat` item whenever
   * the `sideChatId` differs from the previous row's (`A → B` opens a second
   * group; `A → null` closes one). `active` is `sideChatId === activeSideChatId`;
   * `expanded` is `true` for the active group and `expandedSideChats[id] ?? false`
   * otherwise. Never checks or repairs contiguity (027 → D-B).
   */
  get renderedTranscript(): RenderedTranscriptItem[] {
    const items: RenderedTranscriptItem[] = [];
    const activeId = this.activeSideChatId;
    // The group currently being filled, or `null` when the walk is on the main
    // line. A run breaks on ANY change of id, so `A → B` opens a second group
    // with no main-line row between them.
    let open: RenderedTranscriptSideChatItem | null = null;

    for (const message of this.renderedMessages) {
      const sideChatId = message.sideChatId;
      if (sideChatId === null) {
        open = null;
        items.push({ kind: "message", message });
        continue;
      }
      if (open === null || open.sideChatId !== sideChatId) {
        const active: boolean = sideChatId === activeId;
        open = {
          kind: "sideChat",
          sideChatId,
          messages: [],
          active,
          // The active group is always open; a finished one is collapsed until
          // the author expands it (US-137.AC-1).
          expanded: active ? true : (this.expandedSideChats[sideChatId] ?? false),
        };
        items.push(open);
      }
      open.messages.push(message);
    }

    return items;
  }

  /**
   * THE TRANSCRIPT'S GROWTH SIGNATURE (fast/010) — a value that changes whenever
   * the transcript grows, derived from the four observables that can grow it. The
   * shell's follow `autorun` reads this and nothing else.
   *
   * A STRING JOINING THE FOUR COUNTS WITH A SEPARATOR, NOT THEIR SUM, and the
   * distinction is the whole reason this computed exists rather than four bare
   * reads: `finishTurn` appends one persisted message AND clears
   * `streamingContent` in the same action, so a sum can net to the same number,
   * the computed's value would not change, and MobX would NOT re-run the autorun
   * — the transcript would fail to follow at exactly the moment the final answer
   * lands.
   *
   * It reads `messages.length`, NOT `renderedMessages.length`: `renderedMessages`
   * is a presentation derivation whose shape can change without the transcript
   * growing, and rebuilding that array from a non-rendering context is wasted
   * work.
   *
   * Pure — no side effects, no I/O.
   */
  get transcriptGrowthSignature(): string {
    return [
      this.messages.length,
      this.streamingContent.length,
      this.streamingThinking.length,
      this.streamingToolTrace.length,
    ].join(":");
  }
}

/**
 * Load the pane (unimplemented — coder fills). Intent: fetch the book's chats and
 * the model options into their trios, then resolve the active chat — the stored
 * pointer when it still names a visible chat, otherwise the most recent chat by
 * timestamp, otherwise none. Abort-guarded; an `ApiError` becomes an author-facing
 * message in the matching error trio, anything else rethrows.
 *
 * SKELETON: unimplemented — body throws.
 */
export async function loadChatPane(
  state: ChatPaneState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.chatsStatus = "loading";
    state.chatsError = null;
    state.modelOptionsStatus = "loading";
    state.modelOptionsError = null;
  });

  try {
    const chats = await chatsApi.listChats(bookId, false, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chats = chats;
      state.chatsStatus = "ready";
      state.activeChatId = resolveActiveChatId(state, bookId);
      seedSettingsDraft(state);
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.chatsError = err.message;
        state.chatsStatus = "error";
      });
    } else {
      throw err;
    }
  }

  try {
    const options = await chatsApi.listModelOptions(bookId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.modelOptions = options;
      state.modelOptionsStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.modelOptionsError = err.message;
        state.modelOptionsStatus = "error";
      });
    } else {
      throw err;
    }
  }

  // Load the initially-resolved active chat's messages so the conversation renders
  // on mount (the pick flow loads on subsequent picks).
  if (!signal?.aborted && state.activeChatId !== null) {
    await loadChatMessages(state, bookId, state.activeChatId, signal);
  }
}

/**
 * Pick a chat (unimplemented — coder fills). Intent: set `state.activeChatId` and
 * write the device-local per-book pointer. Nothing navigates.
 *
 * SKELETON: unimplemented — body throws.
 */
export function pickChat(state: ChatPaneState, bookId: string, chatId: string): void {
  runInAction(() => {
    state.activeChatId = chatId;
    seedSettingsDraft(state);
  });
  writeActiveChatId(bookId, chatId);
}

/**
 * Create a chat from the new-chat draft (unimplemented — coder fills). Intent:
 * POST the draft's title / model pair / sampling, insert the new chat into the
 * list, make it active, write the pointer, reset the draft. Abort-guarded;
 * `ApiError` → `serverErrors`, else rethrow.
 *
 * SKELETON: unimplemented — body throws.
 */
export async function createChatFromDraft(
  state: ChatPaneState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  const draft = state.newChatDraft;
  const option = state.modelOptions.find((o) => modelOptionKey(o) === draft.optionKey) ?? null;
  const title = draft.title.trim();
  const body: CreateChatRequest = {
    title: title === "" ? null : title,
    llm_server_id: option ? option.server_id : null,
    model_name: option ? option.model_name : null,
    sampling: { ...DEFAULT_SAMPLING, temperature: draft.temperature },
  };

  runInAction(() => {
    state.serverErrors = {};
    state.createStatus = "loading";
  });

  try {
    const created = await chatsApi.createChat(bookId, body, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chats = [created, ...state.chats];
      state.activeChatId = created.id;
      state.newChatDraft.title = "";
      state.newChatDraft.optionKey = null;
      state.newChatDraft.temperature = DEFAULT_TEMPERATURE;
      seedSettingsDraft(state);
      state.createStatus = "ready";
    });
    writeActiveChatId(bookId, created.id);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.serverErrors = { form: err.message || "Could not create the chat." };
        state.createStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * CREATE A CHAT INSTANTLY, WITH NO FORM (023, UC-053 / US-056.AC-1 / UC-054's
 * exception flow; 023 → D6).
 *
 * The pane's "+" control does not open a draft any more: it creates immediately
 * with a DEFAULT MODEL PAIR — the active chat's pair when there is one, otherwise
 * `modelOptions[0]` — and default sampling, posts through `chatsApi.createChat`,
 * and makes the new chat active with an EMPTY transcript. D2's auto-titler names
 * it after the first message, which is precisely why no title is asked for here.
 *
 * With `modelOptions` EMPTY nothing is created and `serverErrors.form` carries the
 * author-facing refusal, so UC-054's refuse-to-compose flow survives the removal
 * of the form.
 *
 * This is an ADDITION: {@link createChatFromDraft} above is untouched and still
 * exported (023 preserves every 011/013/015/016 export, D11).
 */
export async function createChatInstant(
  state: ChatPaneState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  if (state.modelOptions.length === 0) {
    // UC-054's exception flow, moved from the removed form onto the control that
    // is actually blocked: NOTHING is created and the author is told why.
    runInAction(() => {
      state.serverErrors = { form: NO_MODEL_OPTIONS_MESSAGE };
      state.createStatus = "error";
    });
    return;
  }

  // The DEFAULT PAIR: the chat the author is already in, so a "+" continues with
  // the model they were using; otherwise the first offered option.
  const active = state.activeChat;
  const inherited =
    active !== null && active.llm_server_id !== null && active.model_name !== null
      ? { server_id: active.llm_server_id, model_name: active.model_name }
      : null;
  const pair = inherited ?? {
    server_id: state.modelOptions[0].server_id,
    model_name: state.modelOptions[0].model_name,
  };

  const body: CreateChatRequest = {
    // NO TITLE: D2's auto-titler names the chat after its first message, which is
    // precisely why the form asking for one is gone (D6).
    title: null,
    llm_server_id: pair.server_id,
    model_name: pair.model_name,
    sampling: { ...DEFAULT_SAMPLING },
  };

  runInAction(() => {
    state.serverErrors = {};
    state.createStatus = "loading";
  });

  try {
    const created = await chatsApi.createChat(bookId, body, signal);
    if (signal?.aborted) return;
    // Abort any turn still streaming into the chat being left, so no in-flight
    // text leaks onto the new one (the `loadChatMessages` rule, without its fetch —
    // a chat created a moment ago provably has no messages).
    stopChatTurn(state);
    runInAction(() => {
      state.chats = [created, ...state.chats];
      state.activeChatId = created.id;
      // The EMPTY transcript, set rather than fetched.
      state.messages = [];
      state.messagesStatus = "ready";
      state.messagesError = null;
      state.expandedReasoning = {};
      seedSettingsDraft(state);
      state.createStatus = "ready";
    });
    writeActiveChatId(bookId, created.id);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.serverErrors = { form: err.message || "Could not create the chat." };
        state.createStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Archive or restore a chat (unimplemented — coder fills). Intent: PATCH
 * `archived`, update the list, and when the archived chat was active re-resolve
 * the active chat rather than leaving a dangling pointer. Abort-guarded;
 * `ApiError` → an author-facing message, else rethrow.
 *
 * SKELETON: unimplemented — body throws.
 */
export async function setChatArchived(
  state: ChatPaneState,
  bookId: string,
  chatId: string,
  archived: boolean,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.chatsError = null;
    state.archiveStatus = "loading";
  });

  try {
    const updated = await chatsApi.updateChat(bookId, chatId, { archived }, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chats = state.chats.map((c) => (c.id === updated.id ? updated : c));
      state.archiveStatus = "ready";
      // Archiving the active chat must not leave a dangling pointer: re-resolve
      // against the just-updated list (the archived chat is no longer visible) and
      // rewrite/clear the device-local pointer to match.
      if (archived && state.activeChatId === chatId) {
        const next = resolveActiveChatId(state, bookId);
        state.activeChatId = next;
        seedSettingsDraft(state);
        if (next === null) clearActiveChatId(bookId);
        else writeActiveChatId(bookId, next);
      }
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.chatsError = err.message;
        state.archiveStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Save the active chat's settings (unimplemented — coder fills). Intent: PATCH the
 * active chat's model pair + sampling from `settingsDraft`, carrying every
 * non-temperature sampling param through from the loaded chat unchanged (decision
 * 4), and reflect the new values. Abort-guarded; `ApiError` → `serverErrors`,
 * else rethrow.
 *
 * SKELETON: unimplemented — body throws.
 */
export async function saveChatSettings(
  state: ChatPaneState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  const chat = state.activeChat;
  if (chat === null) return;

  const option =
    state.modelOptions.find((o) => modelOptionKey(o) === state.settingsDraft.optionKey) ?? null;
  const body: UpdateChatRequest = {
    // Only `temperature` is editable; every other stored param is carried through
    // from the loaded chat unchanged so an edit never silently resets it (decision 4).
    sampling: { ...chat.sampling, temperature: state.settingsDraft.temperature },
  };
  // AN UNRESOLVABLE DRAFT OPTION IS NOT A REQUEST TO CLEAR THE PAIR (fast/009,
  // known defect 1). When the drafted key matches no LOADED option — the server was
  // deactivated, the model left the catalogue — the model half is OMITTED from the
  // body entirely (both fields are optional on `UpdateChatRequest`) so the chat
  // keeps its stored pair. Sending `{llm_server_id: null, model_name: null}` here
  // would wipe a real pair the author never touched.
  if (option !== null) {
    body.llm_server_id = option.server_id;
    body.model_name = option.model_name;
  }

  runInAction(() => {
    state.serverErrors = {};
    state.settingsStatus = "loading";
  });

  try {
    const updated = await chatsApi.updateChat(bookId, chat.id, body, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chats = state.chats.map((c) => (c.id === updated.id ? updated : c));
      seedSettingsDraft(state);
      state.settingsStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.serverErrors = { form: err.message || "Could not save settings." };
        state.settingsStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * PICK A MODEL AND PERSIST IT IMMEDIATELY (fast/009) — the effect behind a click
 * or an Enter in the header's model dropdown. This is what makes the header label
 * actually change and the pick survive a reload; the temperature half keeps its
 * existing draft + flush-on-send path and is NOT made immediate.
 *
 * `optionKey` is a {@link modelOptionKey} value. Intent, in order:
 *
 * 1. Resolve `optionKey` against the loaded `modelOptions`; unresolvable (or no
 *    active chat) → do NOTHING: no request, no state change.
 * 2. Remember the active chat's stored `llm_server_id` / `model_name` pair.
 * 3. Write the picked pair onto the active chat's row OPTIMISTICALLY, so
 *    {@link ChatPaneState.modelLabel} — and therefore the header — changes at once.
 * 4. Close the model panel (`openedPanel = null`) and clear
 *    {@link ChatPaneState.modelSearch}.
 * 5. Clear the previous `serverErrors.model` and mark the write in flight through
 *    the EXISTING `settingsStatus` trio — no second status is introduced.
 * 6. PATCH through `chatsApi.updateChat` with a body carrying ONLY `llm_server_id`
 *    and `model_name`: no `sampling`, no `title`, no `archived`, so a model pick
 *    never smuggles a temperature draft to the server (DoD-6).
 * 7. On success, replace the chat's row with the server's chat and re-seed ONLY
 *    `settingsDraft.optionKey` to the picked key, leaving
 *    `settingsDraft.temperature` untouched — so `settingsDirty` reads clean on the
 *    model half (no re-PATCH on the next send, DoD-8) while an unsent creativity
 *    edit is not discarded.
 * 8. On failure, and only when the signal did not abort, restore the remembered
 *    pair onto the row, restore `settingsDraft.optionKey` to the remembered pair's
 *    key, and record the author-facing message under the stable `"model"` key of
 *    the existing `serverErrors` map (the module's `err.message || <fallback>`
 *    idiom). `ApiError` → `serverErrors`, anything else rethrows.
 */
export async function pickChatModel(
  state: ChatPaneState,
  bookId: string,
  optionKey: string,
  signal?: AbortSignal,
): Promise<void> {
  const chat = state.activeChat;
  if (chat === null) return;

  // An option key that resolves to nothing is not a pick: no request, no state
  // change, not even a closed dropdown (step 1).
  const option = state.modelOptions.find((o) => modelOptionKey(o) === optionKey) ?? null;
  if (option === null) return;

  const chatId = chat.id;
  const previousServerId = chat.llm_server_id;
  const previousModelName = chat.model_name;
  const previousOptionKey = optionKeyForChat(chat);

  runInAction(() => {
    // OPTIMISTIC: the row moves first, so `modelLabel` — and the header — changes on
    // the click rather than a round trip later. The remembered pair above is what a
    // rejected PATCH restores.
    state.chats = state.chats.map((c) =>
      c.id === chatId
        ? { ...c, llm_server_id: option.server_id, model_name: option.model_name }
        : c,
    );
    state.openedPanel = null;
    state.modelSearch = "";
    // Only the model key is cleared: a pick must not swallow an unrelated `form`
    // refusal already on screen.
    const errors = { ...state.serverErrors };
    delete errors.model;
    state.serverErrors = errors;
    // The EXISTING chat-settings trio marks the write — `settingsStatus` already
    // means "a chat-settings write is in flight" and needs no twin.
    state.settingsStatus = "loading";
  });

  // ONLY THE MODEL PAIR (DoD-6): no `sampling`, no `title`, no `archived`, so a
  // model pick can never smuggle an unsaved temperature draft to the server.
  const body: UpdateChatRequest = {
    llm_server_id: option.server_id,
    model_name: option.model_name,
  };

  try {
    const updated = await chatsApi.updateChat(bookId, chatId, body, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chats = state.chats.map((c) => (c.id === updated.id ? updated : c));
      // ONLY THE MODEL HALF of the draft is re-seeded (DoD-8): `settingsDirty` must
      // read clean on the model so the next send does not re-PATCH a model that is
      // already stored, while an unsent creativity edit still survives the pick.
      // Read back from the SERVER'S row (the picked key by construction) so the
      // draft can never disagree with what is actually stored.
      state.settingsDraft.optionKey = optionKeyForChat(updated);
      state.settingsStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    runInAction(() => {
      state.chats = state.chats.map((c) =>
        c.id === chatId
          ? { ...c, llm_server_id: previousServerId, model_name: previousModelName }
          : c,
      );
      state.settingsDraft.optionKey = previousOptionKey;
      state.settingsStatus = "error";
    });
    if (err instanceof ApiError) {
      runInAction(() => {
        state.serverErrors = {
          ...state.serverErrors,
          model: err.message || "Could not change the model.",
        };
      });
      return;
    }
    throw err;
  }
}

/**
 * Load a chat's stored messages (unimplemented — coder fills). Intent: abort any
 * live turn (`stopChatTurn`) and reset the streaming buffers / turn status so no
 * stray in-flight text leaks onto the newly opened chat, then fetch
 * `chatsApi.getChat(bookId, chatId)` into the messages trio (position-ordered).
 * Abort-guarded; an `ApiError` becomes `messagesError`, anything else rethrows.
 *
 * SKELETON (011/005): unimplemented — body throws.
 */
export async function loadChatMessages(
  state: ChatPaneState,
  bookId: string,
  chatId: string,
  signal?: AbortSignal,
): Promise<void> {
  // Abort any live turn and reset the streaming/turn state so no stray in-flight
  // text from the previous chat leaks onto the newly opened one.
  stopChatTurn(state);
  runInAction(() => {
    state.messagesStatus = "loading";
    state.messagesError = null;
    state.turnStatus = "idle";
    state.turnError = null;
    state.streamingContent = "";
    state.streamingThinking = "";
    // 024: the live trace is a streaming buffer like the two above and is reset
    // with them — the finished turn's trace lives on the reloaded message.
    state.streamingToolTrace = [];
    state.liveThinkingExpanded = false;
    state.expandedReasoning = {};
  });

  try {
    const detail = await chatsApi.getChat(bookId, chatId, signal);
    if (signal?.aborted) return;
    // A detail fetch that resolves without a payload object (or without a
    // messages array) must not throw: normalise to an empty transcript and
    // surface it through the messages trio like the sibling loads, so the
    // pane-load path can never abort on a missing/empty detail payload.
    const messages = Array.isArray(detail?.messages) ? detail.messages : [];
    runInAction(() => {
      state.messages = messages;
      state.messagesStatus = "ready";
    });
    // fast/010: a freshly loaded transcript always starts at its BOTTOM. This one
    // site covers mount, reload, chat switch and `chatPaneController.openChat`,
    // which all run through here — which is why that controller needs no change.
    repinTranscript(state);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.messagesError = err.message;
        state.messagesStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * The content pane's subject as the turn request's three wire fields, read from
 * `work/contentSubject.ts` at SEND time — never stored on `ChatPaneState`, which
 * has no subject field, so a turn sent after the author navigates carries the
 * subject they are looking at NOW (UC-083 / US-086.AC-1 / US-087.AC-1).
 *
 * `undefined` when nothing is registered, which posts exactly `{ prompt }` and
 * leaves `011.chat-panel`'s shipped behaviour untouched. A list subject maps to
 * its kind with a null id (UC-090 — a list is a subject too); a blank codex entry
 * maps to a null id with the `/codex/new?kind=` kind (UC-076).
 */
function turnSubject(): TurnSubject | undefined {
  const subject = currentContentSubject();
  if (subject === null) return undefined;
  return {
    subject_kind: subject.kind,
    subject_id: subject.entityId ?? null,
    codex_kind: subject.codexKind ?? null,
  };
}

/**
 * Send the author's prompt as a new turn (unimplemented — coder fills). Intent:
 * append the user message optimistically, clear the pending prompt (accepted) and
 * the streaming buffers, set `turnStatus = "streaming"`, open the stream via
 * `chatsApi.streamChatTurn(bookId, activeChat.id, text, handlers)` and store the
 * returned `AbortController` on `state.turnController`. The handlers append
 * `thinking` frames to `streamingThinking` and `delta` frames to `streamingContent`
 * through `runInAction` (the first `delta` auto-collapses `liveThinkingExpanded`);
 * `done` replaces the in-flight bubble with the persisted message (reloading, since
 * the frame payload is not forwarded) and re-enables the composer; `error` sets
 * `turnError` / `turnStatus = "error"`, preserving every prior message.
 *
 * 023 EXTENDS THE CONTRACT, SIGNATURE UNCHANGED (D8; DoD-4 / DoD-5) — still
 * UNIMPLEMENTED, and the frozen signature below is what the coder fills against:
 * - BEFORE opening the stream, when {@link ChatPaneState.settingsDirty} is true,
 *   `await saveChatSettings(state, bookId)` — the EXISTING function, reused as-is,
 *   no new effect fn — because the backend's `prepare_turn` reads the chat's
 *   STORED model pair, so an unpersisted change would silently not apply to the
 *   very message it was made for;
 * - if that flush leaves `settingsStatus === "error"`, DO NOT open the stream;
 *   `saveChatSettings`'s own `serverErrors.form` is the author-facing message;
 * - on acceptance, clear {@link ChatPaneState.openedPanel}, so sending closes
 *   whichever popover was open.
 */
export async function sendChatTurn(
  state: ChatPaneState,
  bookId: string,
  text: string,
): Promise<void> {
  const chat = state.activeChat;
  const prompt = text.trim();
  // A send with no active chat or an empty prompt is not accepted, so the composer
  // keeps the (possibly whitespace) text — a failed send never eats the input.
  if (chat === null || prompt === "") return;

  // 023 / D8 — FLUSH BEFORE SEND. The backend's `prepare_turn` reads the chat's
  // STORED model pair, so an unpersisted settings change would silently not apply
  // to the very message it was made for. A clean draft issues no call at all.
  if (state.settingsDirty) {
    await saveChatSettings(state, bookId);
    if (state.settingsStatus === "error") {
      // The flush failed: DO NOT open the stream. `saveChatSettings` has already
      // put the author-facing message in `serverErrors.form`, and the composer
      // keeps the text so the send can be retried once the settings are fixed.
      return;
    }
  }

  const optimistic: ChatMessageResponse = {
    id: `pending-user-${Date.now()}`,
    chat_id: chat.id,
    role: "user",
    content: prompt,
    reasoning: null,
    position: state.messages.length,
    created_at: null,
    // 027: an optimistic user row typed while a side chat is active belongs to
    // that group, exactly as the server will stamp the persisted row.
    side_chat_id: state.activeSideChatId,
    // 024: a user message never carries a tool trace.
    tool_trace: null,
  };

  runInAction(() => {
    state.messages = [...state.messages, optimistic];
    // The send is accepted: clear the composer input now (not before).
    state.pendingPrompt = "";
    // 023 / D7: sending closes whichever header popover was open — one
    // discriminator, so neither can be left behind.
    state.openedPanel = null;
    state.streamingContent = "";
    state.streamingThinking = "";
    // 024: the live trace is a streaming buffer like the two above and is reset
    // with them — the finished turn's trace lives on the reloaded message.
    state.streamingToolTrace = [];
    state.liveThinkingExpanded = false;
    state.turnStatus = "streaming";
    state.turnError = null;
  });

  // fast/010: Send is an explicit "done reading back" gesture, so an author who
  // was scrolled up is re-pinned here — they see their own message land and the
  // reply arrive beneath it. The follow coalesces, so an overlapping schedule from
  // the shell's autorun costs nothing.
  repinTranscript(state);

  const controller = await chatsApi.streamChatTurn(
    bookId,
    chat.id,
    prompt,
    turnStreamHandlers(state, bookId, chat.id),
    // Read at SEND time, so the turn carries whatever the content pane is showing
    // right now — nothing about the subject is stored on the pane.
    turnSubject(),
    // The author's current selection, read from the SAME registry at the SAME
    // moment (015/012; D5). The pane holds no selection field either, and gains no
    // observer relationship to the content pane: the two stay independent because
    // nothing links them but this function call.
    currentContentSelection() ?? undefined,
  );
  runInAction(() => {
    state.turnController = controller;
  });
}

/**
 * REFRESH ONE CHAT'S TITLE FROM THE BACKEND'S AUTO-TITLER (023, D2).
 *
 * Calls `chatsApi.titleChat(bookId, chatId, signal)` — the endpoint owns the whole
 * policy (it titles only at the 1st and 5th user message and swallows its own
 * failures) — and, when the response says `changed`, replaces the matching row's
 * `title` in `state.chats`, which is what `activeChat` and the header derive from.
 *
 * FIRE-AND-FORGET, NEVER AWAITED, from the module-private `finishTurn`, with the
 * chat id captured at that point: it must never delay `turnStatus` returning to
 * `idle`, and a titling failure must never surface as a turn failure. A chat other
 * than the one that just finished may be active by the time it resolves, which is
 * exactly why it patches the row by id rather than touching `activeChat`.
 *
 * TOTAL BY CONSTRUCTION: it never rejects and never throws, whatever the request
 * does, so the fire-and-forget call site cannot produce an unhandled rejection.
 */
export async function refreshChatTitle(
  state: ChatPaneState,
  bookId: string,
  chatId: string,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const result = await chatsApi.titleChat(bookId, chatId, signal);
    if (signal?.aborted) return;
    // `changed: false` covers a non-trigger call, a swallowed backend failure and a
    // blank result alike — in every one of them the stored title is the one already
    // on screen, so there is nothing to patch.
    if (!result.changed) return;
    runInAction(() => {
      state.chats = state.chats.map((c) =>
        c.id === chatId ? { ...c, title: result.title } : c,
      );
    });
  } catch {
    // A title is a nicety: a failed refresh leaves the existing title on screen and
    // is never surfaced to the author. Nothing rethrows — see the note above.
  }
}

/**
 * Retry the failed turn (unimplemented — coder fills). Intent: open the SAME turn
 * stream with NO prompt (`streamChatTurn(bookId, activeChat.id, null, handlers)`),
 * so the already-persisted user message is neither re-sent nor duplicated, wiring
 * the same frame handlers as {@link sendChatTurn}.
 *
 * SKELETON (011/005): unimplemented — body throws.
 */
export async function retryChatTurn(state: ChatPaneState, bookId: string): Promise<void> {
  const chat = state.activeChat;
  if (chat === null) return;

  runInAction(() => {
    state.streamingContent = "";
    state.streamingThinking = "";
    // 024: the live trace is a streaming buffer like the two above and is reset
    // with them — the finished turn's trace lives on the reloaded message.
    state.streamingToolTrace = [];
    state.liveThinkingExpanded = false;
    state.turnStatus = "streaming";
    state.turnError = null;
  });

  // fast/010: retry is the same "I just asked for output" gesture as Send, reached
  // from the same composer, so it re-pins identically — an author who retries
  // expects to watch the new attempt exactly as they would a first one.
  repinTranscript(state);

  // Retry re-opens the SAME turn with NO prompt: the user message is already
  // persisted server-side, so nothing is re-sent or duplicated.
  const controller = await chatsApi.streamChatTurn(
    bookId,
    chat.id,
    null,
    turnStreamHandlers(state, bookId, chat.id),
    // Re-read at RETRY time too: the author may have navigated between the failed
    // send and the retry, and the retry must carry the current subject.
    turnSubject(),
    // The selection is re-read at RETRY time for the same reason and from the same
    // registry — the author may have selected, moved or cleared it since the failed
    // send (015/012).
    currentContentSelection() ?? undefined,
  );
  runInAction(() => {
    state.turnController = controller;
  });
}

/**
 * Stop the live turn (unimplemented — coder fills). Intent: abort
 * `state.turnController` (if any) and clear it; `streamPost` swallows the resulting
 * `AbortError`, so no error frame fires. Used when switching the active chat and by
 * the shell's unmount cleanup.
 *
 * SKELETON (011/005): unimplemented — body throws.
 */
export function stopChatTurn(state: ChatPaneState): void {
  if (state.turnController !== null) {
    // `streamPost` swallows the resulting `AbortError`, so no error frame fires.
    state.turnController.abort();
  }
  runInAction(() => {
    state.turnController = null;
    state.streamingContent = "";
    state.streamingThinking = "";
    // 024: the live trace is a streaming buffer like the two above and is reset
    // with them — the finished turn's trace lives on the reloaded message.
    state.streamingToolTrace = [];
    state.liveThinkingExpanded = false;
    // A user-initiated stop re-enables the composer; an already-failed turn keeps
    // its error/retry surface.
    if (state.turnStatus === "streaming") {
      state.turnStatus = "idle";
      state.turnError = null;
    }
  });
}

/**
 * Flip one tool-trace row's expansion (024) — `state.expandedToolCallRows[rowKey]`,
 * where `rowKey` is `` `${messageKey}:${rowIndex}` ``.
 *
 * An EXTERNAL effectful operation `(state, args)` per the project's MobX rules, so
 * `ChatPaneState` keeps no effectful method and `ToolCallTrace` stays fully
 * controlled and stateless (the `ThinkingBlock` discipline).
 *
 * Collapsed is the default, so an absent key reads as `false` and the first
 * toggle expands it.
 */
export function toggleToolCallRow(state: ChatPaneState, rowKey: string): void {
  runInAction(() => {
    state.expandedToolCallRows[rowKey] = !(state.expandedToolCallRows[rowKey] ?? false);
  });
}

/**
 * Flip one finished side chat's expansion (027) — `state.expandedSideChats[sideChatId]`,
 * writing a WHOLE NEW OBJECT inside `runInAction` (never a key in place).
 *
 * An EXTERNAL effectful operation `(state, args)` per the project's MobX rules, the
 * {@link toggleToolCallRow} twin. Collapsed is the default, so an absent key reads
 * as `false` and the first toggle expands it. Toggling the ACTIVE group's key is
 * harmless: {@link ChatPaneState.renderedTranscript} ignores the map for it.
 */
export function toggleSideChatGroup(state: ChatPaneState, sideChatId: string): void {
  runInAction(() => {
    state.expandedSideChats = {
      ...state.expandedSideChats,
      [sideChatId]: !(state.expandedSideChats[sideChatId] ?? false),
    };
  });
}

/**
 * Start a side chat on the active chat (027 → UC-110 steps 1–2, US-135).
 *
 * Guards INSIDE the function on {@link ChatPaneState.canStartSideChat} and on an
 * active chat id — when either fails it returns without calling the api (the
 * component's `disabled` is presentation; this guard is what makes D1 hold).
 * Otherwise: `sideChatActionStatus = "busy"` (clearing `sideChatActionError`),
 * call `chatsApi.startSideChat(bookId, activeChatId, signal)`; on success REPLACE
 * the matching entry of `state.chats` (by id) with the returned `ChatResponse`
 * — a whole-object replace, never a field patch — so `activeSideChatId` flips,
 * then `"idle"`. On `ApiError`: `"error"` + the error's message, `chats` /
 * `messages` untouched. Any other rejection propagates.
 *
 * All observable writes inside `runInAction`, before and after the await.
 */
export async function startSideChat(
  state: ChatPaneState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  const chatId = state.activeChatId;
  if (!state.canStartSideChat || chatId === null) return;

  runInAction(() => {
    state.sideChatActionStatus = "busy";
    state.sideChatActionError = null;
  });

  try {
    const updated = await chatsApi.startSideChat(bookId, chatId, signal);
    runInAction(() => {
      state.chats = state.chats.map((c) => (c.id === updated.id ? updated : c));
      state.sideChatActionStatus = "idle";
    });
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        state.sideChatActionError = err.message;
        state.sideChatActionStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Finish the active side chat (027 → UC-111, US-137.AC-1 — the client half).
 *
 * Guards INSIDE the function on {@link ChatPaneState.canFinishSideChat} (which
 * implies an active chat and a non-null `activeSideChatId`); when it fails it
 * returns without calling the api. Otherwise: `"busy"`, call
 * `chatsApi.finishSideChat(bookId, activeChatId, activeSideChatId, signal)`; on
 * success replace the matching entry of `state.chats` with the returned chat
 * (the pointer is now `null`) and go `"idle"`. **`state.messages` is untouched**
 * — the group becomes "finished" purely through
 * {@link ChatPaneState.renderedTranscript} (finished = not the pointer, D-A).
 * On `ApiError`: `"error"` + message; anything else propagates.
 */
export async function finishSideChat(
  state: ChatPaneState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  const chatId = state.activeChatId;
  const sideChatId = state.activeSideChatId;
  if (!state.canFinishSideChat || chatId === null || sideChatId === null) return;

  runInAction(() => {
    state.sideChatActionStatus = "busy";
    state.sideChatActionError = null;
  });

  try {
    const updated = await chatsApi.finishSideChat(bookId, chatId, sideChatId, signal);
    runInAction(() => {
      state.chats = state.chats.map((c) => (c.id === updated.id ? updated : c));
      state.sideChatActionStatus = "idle";
    });
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        state.sideChatActionError = err.message;
        state.sideChatActionStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Inject a side chat's messages into the main line (027 → UC-113, US-139.AC-1 —
 * the client half). Works on the active OR a finished side chat.
 *
 * Guards INSIDE the function on {@link ChatPaneState.sideChatActionsEnabled}
 * and an active chat id; when either fails it returns without calling the api.
 * Otherwise: `"busy"`, call `chatsApi.injectSideChat(bookId, activeChatId,
 * sideChatId, signal)`; on success SWAP `state.messages` WHOLE with the
 * response's `messages` (never `push` / `splice`) and replace the matching
 * `state.chats` entry with the response's `chat`, then `"idle"`. On
 * `ApiError`: `"error"` + message, `chats` / `messages` untouched; anything
 * else propagates.
 */
export async function injectSideChat(
  state: ChatPaneState,
  bookId: string,
  sideChatId: string,
  signal?: AbortSignal,
): Promise<void> {
  const chatId = state.activeChatId;
  if (!state.sideChatActionsEnabled || chatId === null) return;

  runInAction(() => {
    state.sideChatActionStatus = "busy";
    state.sideChatActionError = null;
  });

  try {
    const detail = await chatsApi.injectSideChat(bookId, chatId, sideChatId, signal);
    runInAction(() => {
      state.messages = detail.messages;
      state.chats = state.chats.map((c) => (c.id === detail.chat.id ? detail.chat : c));
      state.sideChatActionStatus = "idle";
    });
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        state.sideChatActionError = err.message;
        state.sideChatActionStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Delete a side chat's messages permanently (027 → UC-112, US-140.AC-3 — the
 * client half). Works on the active OR a finished side chat.
 *
 * Guards INSIDE the function on {@link ChatPaneState.sideChatActionsEnabled}
 * and an active chat id; when either fails it returns without calling the api.
 * Otherwise: `"busy"`, call `chatsApi.deleteSideChat(bookId, activeChatId,
 * sideChatId, signal)` (204, nothing comes back), then RELOAD the chat through
 * the existing `chatsApi.getChat(bookId, activeChatId, signal)` — the
 * {@link finishTurn} reload idiom — and swap `state.messages` WHOLE with the
 * reload's `messages` and replace the matching `state.chats` entry with the
 * reload's `chat`, then `"idle"`. On `ApiError` (from either call): `"error"` +
 * message, `chats` / `messages` untouched; anything else propagates.
 *
 * `sideChatDeleteConfirm` is cleared to `null` on BOTH outcomes — leaving the
 * modal open over an error banner would show two conflicting states.
 */
export async function deleteSideChat(
  state: ChatPaneState,
  bookId: string,
  sideChatId: string,
  signal?: AbortSignal,
): Promise<void> {
  const chatId = state.activeChatId;
  if (!state.sideChatActionsEnabled || chatId === null) return;

  runInAction(() => {
    state.sideChatActionStatus = "busy";
    state.sideChatActionError = null;
  });

  try {
    await chatsApi.deleteSideChat(bookId, chatId, sideChatId, signal);
    const detail = await chatsApi.getChat(bookId, chatId, signal);
    runInAction(() => {
      state.messages = detail.messages;
      state.chats = state.chats.map((c) => (c.id === detail.chat.id ? detail.chat : c));
      state.sideChatDeleteConfirm = null;
      state.sideChatActionStatus = "idle";
    });
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        state.sideChatDeleteConfirm = null;
        state.sideChatActionError = err.message;
        state.sideChatActionStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Open the delete confirmation for one side chat (027 → US-140.AC-1): set
 * `state.sideChatDeleteConfirm = sideChatId` inside `runInAction`. Calls NO api
 * and touches nothing else — the delete itself is {@link deleteSideChat}, run
 * only once the author confirms.
 */
export function requestDeleteSideChat(state: ChatPaneState, sideChatId: string): void {
  runInAction(() => {
    state.sideChatDeleteConfirm = sideChatId;
  });
}

/**
 * Dismiss the delete confirmation (027 → US-140.AC-2, `Keep it`): set
 * `state.sideChatDeleteConfirm = null` inside `runInAction`. Calls NO api and
 * leaves `messages` / `chats` unchanged.
 */
export function dismissDeleteSideChat(state: ChatPaneState): void {
  runInAction(() => {
    state.sideChatDeleteConfirm = null;
  });
}

/**
 * The frame handlers shared by {@link sendChatTurn} and {@link retryChatTurn},
 * all observable writes wrapped in `runInAction`:
 * - `thinking` — append to `streamingThinking`, keep the live region expanded;
 * - `delta` — append to `streamingContent`; the FIRST content delta of the turn
 *   auto-collapses the live thinking region (the author may re-expand it);
 * - `done` — reload the chat's messages once (the persisted assistant message does
 *   NOT arrive in the frame; `sse.ts:streamPost` discards the `done` payload),
 *   replacing the in-flight bubble with the stored message and re-enabling the composer;
 * - `error` — set `turnError` / `turnStatus = "error"`, preserving every prior message;
 * - `canvas` — hand the frame straight to `work/contentSubject.ts`'s dispatcher
 *   (013 step 013). The pane owns NO canvas state and no subject state: it neither
 *   inspects nor buffers the draft, and the registry decides between the open
 *   page's apply-draft callback and the restore-buffer fallback.
 */
function turnStreamHandlers(
  state: ChatPaneState,
  bookId: string,
  chatId: string,
): chatsApi.TurnStreamHandlers {
  return {
    onThinking: (text: string) => {
      runInAction(() => {
        state.streamingThinking += text;
        state.liveThinkingExpanded = true;
      });
    },
    onDelta: (text: string) => {
      runInAction(() => {
        // The first content delta collapses the live thinking region exactly once.
        if (state.streamingContent === "") state.liveThinkingExpanded = false;
        state.streamingContent += text;
      });
    },
    onDone: () => {
      void finishTurn(state, bookId, chatId);
    },
    onError: (message: string) => {
      runInAction(() => {
        state.turnStatus = "error";
        state.turnError = message || "The turn failed.";
        state.turnController = null;
      });
    },
    onCanvas: (frame) => {
      dispatchCanvasFrame(bookId, frame);
    },
    // 024 — the live half of the trace. A `tool_call` opens a PENDING row; the
    // `tool_result` that follows closes it. Nothing else in the pane reads these
    // buffers, and both are cleared with the other streaming state once the turn
    // ends — what the author keeps seeing then is the RELOADED message's
    // `tool_trace`.
    onToolCall: (frame) => {
      runInAction(() => {
        state.streamingToolTrace = [
          ...state.streamingToolTrace,
          {
            toolName: frame.tool_name,
            arguments: frame.arguments,
            result: null,
            ok: null,
          },
        ];
      });
    },
    onToolResult: (frame) => {
      runInAction(() => {
        // The MOST RECENT still-open row. Tool dispatch is sequential on the
        // backend, so at most one row is ever open — searching backwards for it
        // is simply the cheapest way to say "the one that is in flight", and a
        // result arriving with none open (a dropped or duplicated call frame) is
        // discarded rather than inventing a row nothing announced.
        const rows = state.streamingToolTrace;
        let pending = -1;
        for (let i = rows.length - 1; i >= 0; i -= 1) {
          if (rows[i].result === null) {
            pending = i;
            break;
          }
        }
        if (pending === -1) return;
        state.streamingToolTrace = rows.map((row, i) =>
          i === pending ? { ...row, result: frame.result, ok: frame.ok } : row,
        );
      });
    },
  };
}

/**
 * Complete a streamed turn: reload the chat's persisted messages once (the `done`
 * frame payload is discarded by `streamPost`), then atomically swap them in and
 * clear the streaming bubble so there is exactly one persisted assistant message —
 * no duplicate and no orphaned in-flight bubble.
 *
 * 023: this is also where the auto-title refresh is FIRED AND FORGOTTEN — the only
 * place that knows a turn just completed successfully, since `onDone` carries no
 * payload. It is never awaited, so `turnStatus` returns to `idle` on the turn's own
 * schedule and a titling round trip can never hold the composer disabled.
 */
async function finishTurn(state: ChatPaneState, bookId: string, chatId: string): Promise<void> {
  let reloaded: ChatMessageResponse[] | null = null;
  try {
    const detail = await chatsApi.getChat(bookId, chatId);
    reloaded = detail.messages;
  } catch {
    // Keep the optimistic transcript if the reload fails; the turn still completed.
    reloaded = null;
  }
  runInAction(() => {
    if (reloaded !== null) state.messages = reloaded;
    state.streamingContent = "";
    state.streamingThinking = "";
    // 024: the live trace is a streaming buffer like the two above and is reset
    // with them — the finished turn's trace lives on the reloaded message.
    state.streamingToolTrace = [];
    state.liveThinkingExpanded = false;
    state.turnStatus = "idle";
    state.turnError = null;
    state.turnController = null;
  });

  // NOT AWAITED, and with the chat id captured HERE: by the time the backend
  // answers, another chat may be active, which is exactly why `refreshChatTitle`
  // patches the row by id. It never rejects, so this cannot become an unhandled
  // rejection.
  void refreshChatTitle(state, bookId, chatId);
}

// ---------------------------------------------------------------------------
// THE CLOSE-CHAPTER TURN (`016.chapter-close-continuity`)
//
// Closing a chapter is an ORDINARY assistant turn in this pane (decision D1) — not
// a second streaming subsystem and not a hidden call. These two effects are the
// pane's half of `work/closeTurn.ts`'s controller seam; the chapter page's half is
// `chapterPageState.ts`'s `requestChapterClose` / `cancelChapterCloseRequest`.
//
// The pane registers ITSELF (`ChatPaneState implements CloseTurnController`) in the
// shell's existing mount effect and unregisters on unmount — the same effect that
// already owns `stopChatTurn`. No new effect, no new component, no new registry.
// ---------------------------------------------------------------------------

/**
 * THE SYNTHETIC PROMPT a close turn posts. The author did not type it, but it is a
 * real user message in a real chat (decision D1) — the transcript is the point, so
 * it reads as an instruction rather than as a machine token.
 *
 * It names the four things the close procedure must produce and states the one fact
 * the model would otherwise get wrong: the SERVER decides the outcome once the
 * conversation ends. The tool descriptions in `services/tools.py` say the same, and
 * the `close-chapter` mode's own system prompt is an admin's to write.
 */
const CLOSE_TURN_PROMPT =
  "Close this chapter. Read it and the book's continuity so far, then: write the " +
  "chapter's summary, record what it added to, changed in and removed from the " +
  "book's state notes, propose the resulting state notes in full, and raise a " +
  "finding for anything in this chapter that contradicts what the book already " +
  "establishes. When you are done, the server decides whether the chapter closes.";

/**
 * POST THE CLOSE TURN for `(bookId, chapterId)` (016; DoD-9).
 *
 * Intent: send a **synthetic prompt** through the pane's EXISTING
 * `chatsApi.streamChatTurn` pipeline — the same handlers {@link sendChatTurn} wires,
 * the same optimistic-message / streaming-buffer / `turnController` bookkeeping —
 * with the turn's subject fixed to this chapter (`subject_kind: "chapter"`,
 * `subject_id: chapterId`) rather than read from `work/contentSubject.ts`: the close
 * is about the chapter that is closing, whatever the author may have navigated to.
 *
 * There is **no second turn runner and no new frame type**: the backend's
 * `chat_turn.run_turn` streams this turn like any other and finalizes the close
 * deterministically once it ends (decision D5).
 *
 * Its `done` / `error` handling must ALSO call
 * `work/closeTurn.ts::clearCloseTurnActive()`, so the composer stops being read-only
 * when the turn finishes either way — the close window ends with the turn, and the
 * server has already decided the outcome by then.
 *
 */
export async function startCloseTurn(
  state: ChatPaneState,
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  const chat = state.activeChat;
  // No chat to post into: the close window is already open server-side and the
  // author's exit is the chapter page's Stop control, so this is a silent no-op
  // rather than an error. Nothing here may clear the close signal — the chapter
  // IS closing.
  if (chat === null || signal?.aborted) return;

  const optimistic: ChatMessageResponse = {
    id: `pending-user-${Date.now()}`,
    chat_id: chat.id,
    role: "user",
    content: CLOSE_TURN_PROMPT,
    reasoning: null,
    position: state.messages.length,
    created_at: null,
    // 027: an optimistic user row typed while a side chat is active belongs to
    // that group, exactly as the server will stamp the persisted row.
    side_chat_id: state.activeSideChatId,
    // 024: a user message never carries a tool trace.
    tool_trace: null,
  };

  runInAction(() => {
    // The SAME optimistic-message / streaming-buffer bookkeeping `sendChatTurn`
    // does — this is an ordinary turn in this pane (decision D1), not a second
    // streaming subsystem. `pendingPrompt` is deliberately NOT cleared: the
    // author did not type this, and whatever they had half-written survives.
    state.messages = [...state.messages, optimistic];
    state.streamingContent = "";
    state.streamingThinking = "";
    // 024: the live trace is a streaming buffer like the two above and is reset
    // with them — the finished turn's trace lives on the reloaded message.
    state.streamingToolTrace = [];
    state.liveThinkingExpanded = false;
    state.turnStatus = "streaming";
    state.turnError = null;
  });

  const controller = await chatsApi.streamChatTurn(
    bookId,
    chat.id,
    CLOSE_TURN_PROMPT,
    closeTurnStreamHandlers(state, bookId, chat.id),
    // FIXED to the closing chapter, never read from `work/contentSubject.ts`: the
    // close is about the chapter that is closing, whatever the author may have
    // navigated to since. This is what routes the turn into the backend's
    // `close-chapter` mode and its close tools.
    { subject_kind: "chapter", subject_id: chapterId, codex_kind: null },
    // No selection rides on a close turn: nothing is being rewritten in an editor.
    undefined,
  );
  runInAction(() => {
    state.turnController = controller;
  });
}

/**
 * The close turn's frame handlers: {@link turnStreamHandlers}'s, with `done` and
 * `error` ALSO releasing the close signal through
 * `work/closeTurn.ts::clearCloseTurnActive()`.
 *
 * The close window ends with the turn either way — the server has already decided
 * the outcome by the time the terminal frame arrives (decision D5) — so the
 * composer stops being read-only on both endings and on neither is anything else
 * about the pane's turn bookkeeping different.
 */
function closeTurnStreamHandlers(
  state: ChatPaneState,
  bookId: string,
  chatId: string,
): chatsApi.TurnStreamHandlers {
  const base = turnStreamHandlers(state, bookId, chatId);
  return {
    ...base,
    onDone: () => {
      clearCloseTurnActive();
      base.onDone();
    },
    onError: (message: string) => {
      clearCloseTurnActive();
      base.onError(message);
    },
  };
}

/**
 * STOP THE LIVE CLOSE TURN (016) — reuses the pane's existing stream-abort control
 * ({@link stopChatTurn}), so there is exactly one abort path for every turn this pane
 * runs.
 *
 * Aborting the stream is only half of the Stop path: `chapterPageState.ts` also calls
 * `POST …/close/cancel`, which is what returns the chapter to `open` and discards the
 * run's artifacts (decision D4). This function neither calls the server nor clears
 * {@link ChatPaneState.closeTurnActive} — that flows back in through
 * `closeTurn.ts::clearCloseTurnActive` on the successful cancel.
 */
export function stopCloseTurn(state: ChatPaneState): void {
  // EXACTLY ONE abort path for every turn this pane runs.
  stopChatTurn(state);
}

// --- The composer resize lifecycle (fast/008) ---------------------------------
//
// Three external `(state, …)` functions, per this file's header rule: the class
// holds observable data + pure `get` computeds ONLY. The drag lifecycle copies
// `workspaceShellState.ts`'s width drag exactly — listeners on `window`, never
// `setPointerCapture`; body styles saved and restored by the dispose closure;
// begin and end both idempotent; storage written ONCE at the end of a drag.

/**
 * START A POINTER DRAG on the composer's divider. Intent: capture the current
 * {@link ChatPaneState.composerHeight} and the pointer-down `clientY` as CLOSURE
 * LOCALS (never as fields on the state); set `composerResizing`; suppress text
 * selection (`document.body.style.userSelect = "none"`) and pin a `row-resize`
 * cursor on `document.body`, SAVING the prior values so they can be restored;
 * attach `pointermove` / `pointerup` / `pointercancel` to **`window`** —
 * deliberately NOT `setPointerCapture` (jsdom implements neither that nor
 * `PointerEvent`, and window listeners keep tracking when the pointer outruns the
 * 6px strip); and store the detach-and-restore closure on
 * {@link ChatPaneState.composerResizeDispose}.
 *
 * IDEMPOTENT: a second call while a drag is already live is a no-op. The
 * `pointermove` handler does EXACTLY one thing — assign
 * `composerHeightFromDrag(startHeight, startY, event.clientY, window.innerHeight)`
 * to `state.composerHeight`. No storage write, no other state change.
 */
export function beginComposerResize(state: ChatPaneState, clientY: number): void {
  // Idempotent: a second pointer-down while a drag is already live changes nothing
  // (and must never attach a second set of listeners).
  if (state.composerResizeDispose !== null) return;

  // CLOSURE LOCALS, never fields on the state: the move handler is created here and
  // closes over them. Fields would have to join the `makeAutoObservable` exclusion
  // map and would re-render the pane at pointer-down for no reason.
  const startHeight = state.composerHeight;
  const startY = clientY;

  const handleMove = (event: PointerEvent): void => {
    // The ONLY thing a pointer move does. No storage write here — the height is
    // persisted once, on pointer-up.
    runInAction(() => {
      state.composerHeight = composerHeightFromDrag(
        startHeight,
        startY,
        event.clientY,
        window.innerHeight,
      );
    });
  };
  const handleEnd = (): void => {
    endComposerResize(state);
  };

  // Listeners on `window`, deliberately NOT `setPointerCapture`: jsdom implements
  // neither that nor `PointerEvent`, and window listeners keep tracking when the
  // pointer outruns the 6px strip.
  window.addEventListener("pointermove", handleMove);
  window.addEventListener("pointerup", handleEnd);
  window.addEventListener("pointercancel", handleEnd);

  const previousUserSelect = document.body.style.userSelect;
  const previousCursor = document.body.style.cursor;
  document.body.style.userSelect = "none";
  document.body.style.cursor = "row-resize";

  state.composerResizeDispose = () => {
    window.removeEventListener("pointermove", handleMove);
    window.removeEventListener("pointerup", handleEnd);
    window.removeEventListener("pointercancel", handleEnd);
    document.body.style.userSelect = previousUserSelect;
    document.body.style.cursor = previousCursor;
  };

  runInAction(() => {
    state.composerResizing = true;
  });
}

/**
 * END A POINTER DRAG: detach the listeners, restore the saved body styles, clear
 * `composerResizing`, and persist the height ONCE as a partial patch carrying
 * `composerHeight` alone.
 *
 * IDEMPOTENT, and guarded on {@link ChatPaneState.composerResizeDispose} rather
 * than on `composerResizing`, so a call with no drag in flight is a TRUE no-op —
 * including no storage write.
 */
export function endComposerResize(state: ChatPaneState): void {
  const dispose = state.composerResizeDispose;
  // No drag in flight (a stray pointer-up, or a second one) — nothing to detach,
  // restore or WRITE. Guarding on the closure rather than on `composerResizing` is
  // what makes this a true no-op, storage included.
  if (dispose === null) return;
  state.composerResizeDispose = null;
  dispose();
  runInAction(() => {
    state.composerResizing = false;
  });
  // ONCE, at the end of the drag — and as a PARTIAL patch carrying this pane's field
  // alone, so the shell's `navCollapsed` / `chatWidth` survive untouched.
  writeWorkspaceLayout({ composerHeight: state.composerHeight });
}

/**
 * THE KEYBOARD PATH: apply a pixel delta to the live height —
 * `clampComposerHeight(state.composerHeight + delta, window.innerHeight)` — and
 * persist the same partial patch. This is what makes the persistence wiring
 * verifiable in jsdom at all; the pointer drag itself is `[manual/live]`.
 */
export function nudgeComposerHeight(state: ChatPaneState, delta: number): void {
  runInAction(() => {
    // `window.innerHeight` is read HERE, at the point of use — the stored value
    // carries no ceiling of its own.
    state.composerHeight = clampComposerHeight(state.composerHeight + delta, window.innerHeight);
  });
  writeWorkspaceLayout({ composerHeight: state.composerHeight });
}

// --- The transcript's scroll pinning (fast/010) ---
//
// Six EXTERNAL operations `(state, …)`, per this file's header rule — the class
// holds observable data and pure `get` computeds only. The geometry itself lives
// in the pure `transcriptScroll.ts` beside this file.
//
// THE PROGRAMMATIC SCROLL'S OWN SCROLL EVENT IS LEFT ALONE, DELIBERATELY: writing
// `scrollTop` fires `onScrollPositionChange`, which re-runs `noteTranscriptScroll`;
// because the write lands at the bottom that recomputes to pinned = true and the
// loop terminates on its first iteration. NO suppression flag — it would also
// swallow a genuine user scroll landing in the same frame, which is the one event
// that must never be missed.

/**
 * Store (or clear) the scrolling transcript viewport — `MessageList`'s callback
 * ref hands the node here. THAT IS ALL IT DOES.
 *
 * It must NOT re-pin and must NOT cancel the pending frame: an inline callback ref
 * has a new function identity on every render, so React detaches with `null` and
 * re-attaches the same node on EVERY render of `MessageList` — which is once per
 * streaming delta. A re-pin there would yank a scrolled-up author back down
 * mid-stream; a cancel there would kill the very frame that is about to follow.
 *
 * It is therefore tolerant of repeated `null`-then-node churn by construction:
 * detach and re-attach happen synchronously inside one React commit, and a pending
 * frame reads the viewport slot only when it fires, which is after that commit.
 */
export function attachTranscriptViewport(
  state: ChatPaneState,
  element: HTMLDivElement | null,
): void {
  state.transcriptViewport = element;
}

/**
 * Recompute the pinned flag from the LIVE element — this is what
 * `onScrollPositionChange` calls.
 *
 * Reads the attached viewport's `scrollTop` / `scrollHeight` / `clientHeight` and
 * assigns {@link isTranscriptPinned}'s answer to
 * `state.transcriptPinned`. A no-op when no viewport is attached (it leaves the
 * flag alone rather than guessing). The `{ x, y }` argument of the Mantine
 * callback is IGNORED on purpose: the predicate needs all three numbers and the
 * element is the truth.
 */
export function noteTranscriptScroll(state: ChatPaneState): void {
  const viewport = state.transcriptViewport;
  // Nothing attached: leave the flag alone rather than guessing from no geometry.
  if (viewport === null) return;
  state.transcriptPinned = isTranscriptPinned(
    viewport.scrollTop,
    viewport.scrollHeight,
    viewport.clientHeight,
  );
}

/**
 * Put the transcript at its bottom, SYNCHRONOUSLY — the single place the contract
 * is enforced, and synchronous so the geometry wiring is testable with no timing
 * at all.
 *
 * If a viewport is attached AND `state.transcriptPinned` is set, it writes
 * {@link transcriptBottomScrollTop}'s result to the viewport's `scrollTop`.
 * Otherwise it does nothing — and in particular does not throw when nothing is
 * attached.
 */
export function scrollTranscriptToBottom(state: ChatPaneState): void {
  const viewport = state.transcriptViewport;
  if (viewport === null || !state.transcriptPinned) return;
  viewport.scrollTop = transcriptBottomScrollTop(
    viewport.scrollHeight,
    viewport.clientHeight,
  );
}

/**
 * Schedule a deferred, coalesced follow — this is what the shell's `autorun`
 * calls.
 *
 * - returns immediately when `state.transcriptPinned` is clear — a scrolled-up
 *   author schedules nothing at all, which IS "the position is preserved";
 * - returns immediately when `state.transcriptFollowFrame` is already set — THIS IS
 *   THE COALESCING, and without it a fast token stream queues one frame per delta;
 * - otherwise it schedules a `requestAnimationFrame`; the frame clears the stored
 *   handle and then
 *   calls {@link scrollTranscriptToBottom}, which RE-CHECKS pinned and the viewport
 *   (the author may have scrolled during the frame).
 *
 * THE DEFERRAL IS MANDATORY, NOT STYLISTIC: a MobX `autorun` fires synchronously
 * on mutation, BEFORE React re-renders, so measuring `scrollHeight` at that instant
 * yields the pre-update height and the scroll lands short of the new bottom by
 * exactly the height of what just arrived.
 */
export function followTranscript(state: ChatPaneState): void {
  // A scrolled-up author schedules nothing at all — that IS "position preserved".
  if (!state.transcriptPinned) return;
  // THE COALESCING: one frame per burst, never one frame per streaming delta.
  if (state.transcriptFollowFrame !== null) return;
  state.transcriptFollowFrame = requestAnimationFrame(() => {
    state.transcriptFollowFrame = null;
    // Re-checks pinned AND the viewport: the author may have scrolled, or the pane
    // released its viewport, during the frame.
    scrollTranscriptToBottom(state);
  });
}

/**
 * FORCE the transcript back to following and schedule the follow — the shared
 * "I just asked for output" gesture behind the three re-pin call sites
 * (`loadChatMessages` on the success path, `sendChatTurn` on acceptance, and
 * `retryChatTurn` at the equivalent point).
 *
 * Sets `state.transcriptPinned = true` (overriding a scrolled-up author), then
 * calls {@link followTranscript}. Because the follow coalesces, an overlapping
 * schedule from the shell's autorun costs nothing, and this stays correct when no
 * shell is mounted.
 */
export function repinTranscript(state: ChatPaneState): void {
  state.transcriptPinned = true;
  followTranscript(state);
}

/**
 * Cancel any pending follow frame and clear the viewport slot — called from
 * `WorkspaceShell`'s EXISTING cleanup.
 */
export function releaseTranscriptViewport(state: ChatPaneState): void {
  if (state.transcriptFollowFrame !== null) {
    cancelAnimationFrame(state.transcriptFollowFrame);
    state.transcriptFollowFrame = null;
  }
  state.transcriptViewport = null;
}
