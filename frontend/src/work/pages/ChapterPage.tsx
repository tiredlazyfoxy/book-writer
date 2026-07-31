import { useEffect, useState } from "react";
import type { ReactElement } from "react";
import { observer } from "mobx-react-lite";
import { useParams } from "react-router-dom";
import {
  Alert,
  Badge,
  Button,
  Container,
  Divider,
  Group,
  Loader,
  Modal,
  Paper,
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import Markdown from "react-markdown";
import { registerContentSubject, unregisterContentSubject } from "../contentSubject";
import { chapterUndoDepth } from "../chapterUndo";
import { ChapterBodyEditor } from "../components/chapter/ChapterBodyEditor";
import { resolveEditability } from "../subject";
import {
  ChapterPageState,
  cancelChapterCloseRequest,
  editBodyDraft,
  loadChapter,
  loadChapterBody,
  loadChapterChangeset,
  loadChapterWarnings,
  loadSystemPrompt,
  openChapterState,
  raiseChapterFlag,
  reopenChapterState,
  requestChapterClose,
  resolveBodyConflict,
  resolveChapterFlag,
  saveChapterBody,
  saveSketch,
  saveSystemPrompt,
  setChapterSelection,
  undoAssistantBodyWrite,
} from "./chapterPageState";
import type { ChapterTransition } from "./chapterPageState";
import type { ContinuityStatus } from "../../types/continuity";
import type { FlagOrigin, FlagStatus } from "../../types/flags";

/**
 * The VISIBLE label of the one offered transition control — the action word alone.
 * The control's full accessible name widens it with the chapter (`Open chapter:
 * {title}`), so the visible label is CONTAINED in the accessible name, exactly as the
 * state `Badge` beside it already does.
 */
const TRANSITION_LABELS: Record<ChapterTransition, string> = {
  open: "Open",
  close: "Close",
  reopen: "Reopen",
  // 016: the `closing` chapter's one offered transition. The action word is "Stop",
  // not "Cancel": a `Cancel` button beside a close confirmation would read as
  // "dismiss this dialog", while what it does is abandon the close run in progress
  // (decision D4).
  cancel: "Stop",
};

/**
 * Author-facing labels for a continuity artifact's freshness (016). Module-private
 * and deliberately not exported, exactly as `LIFECYCLE_STATE_LABELS` in
 * `chapterPageState.ts` is: no shared label map was frozen.
 */
const CONTINUITY_STATUS_LABELS: Record<ContinuityStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  stale: "Stale",
};

/** Author-facing labels for where a warning came from — "the check" or "an author". */
const FLAG_ORIGIN_LABELS: Record<FlagOrigin, string> = {
  check: "Consistency check",
  person: "Raised by an author",
};

/** Author-facing labels for a warning's lifecycle. */
const FLAG_STATUS_LABELS: Record<FlagStatus, string> = {
  open: "Open",
  resolved: "Resolved",
};

/**
 * One chapter in the working page's content pane — `/work/:bookId/chapter/:id`
 * (FEAT-008 · UC-033 · US-034), plus the caller's OWN chapter system prompt
 * (decision D1; no product id yet — `014.chapter-skeleton/context.md` →
 * "Product situation").
 *
 * Zero props: both ids come from `useParams`. The contract, which this body
 * implements and may not widen:
 *
 * **Structure (`BookStatePage` + `ChaptersPage` are the models).** One
 * `useState(() => new ChapterPageState(bookId, id))`, `useParams()` for `bookId`
 * and `id`, and EXACTLY ONE page-level `useEffect([state])` that: spins a single
 * `AbortController`; calls `registerContentSubject(state.subjectSource,
 * state.applyDraft)` — the source is read at send time, so the pane model's
 * editability answer is about THIS chapter and reflects its state once the load
 * resolves, and it lives on the state instance because it is also the identity token
 * the selection registry is stamped with (015/012); starts the THREE loads; and
 * returns a cleanup calling `unregisterContentSubject(state.subjectSource)` then
 * `ctrl.abort()` (DoD-14). The `key={id}` that makes a `:id` change produce a FRESH
 * state instance lives on `ChapterItemRoute` in `work/routes.tsx`.
 * `contentSubject.ts` is CALLED here, never changed.
 *
 * **What it renders.** The chapter's title, ordinal and readable state (the state
 * through `state.lifecycleStateLabel` — the lifecycle word as TEXT, never a
 * colour; DoD-1). The chapter trio's own loading and error branches and the
 * prompt trio's own loading and error branches INDEPENDENTLY — the prompt section
 * is a SIBLING of the chapter section, never nested inside its success path, so a
 * failed chapter load cannot hide the prompt's state and vice versa (DoD-11). A
 * sketch section: a labelled multi-line editor bound to `state.sketchDraft`,
 * disabled unless `state.canEditSketch`, a save control gated on
 * `state.canSaveSketch` (DoD-5) and rendered ONLY where a save is possible (DoD-3
 * — a non-`planned` chapter offers no save), a surface for
 * `state.sketchServerErrors` (DoD-4), and `state.sketchDisabledReason` as readable
 * text whenever it is non-null. A system-prompt section: a labelled multi-line
 * editor bound to `state.systemPromptDraft` with NO disabled state in any chapter
 * lifecycle state (DoD-10), a save control gated on `state.canSaveSystemPrompt`, a
 * surface for `state.systemPromptServerErrors`, and ONE line of copy stating the
 * prompt is the caller's OWN and is not shared with co-authors. That line does NOT
 * promise the prompt affects the assistant today: composition is deferred (D7),
 * and "your own, not shared" is the honest claim. There is NO delete control
 * (DoD-9 — saving `""` is how a prompt is cleared).
 *
 * **The body section (`015.chapter-writing-free-mode` step 006).** A THIRD sibling
 * section, never nested inside the chapter section's success path, so the body's
 * own trio loads and fails independently of the other two in both directions
 * (015/006 DoD-1): its own loading branch, its own load-error alert, and then
 * either — for an `open` chapter, which is what `state.canEditBody` answers off the
 * BODY response's state — the `ChapterBodyEditor` KEYED ON
 * `state.bodyEditorGeneration` (D15: an external draft write re-syncs TipTap by
 * remount; the counter is read HERE and nowhere else, never rendered and never
 * compared), seeded with `state.bodyDraft`, wired to `editBodyDraft` (the single
 * entry point every draft change routes through), plus a `Save body` control gated
 * on `state.canSaveBody` and a surface for `state.bodyServerErrors` — or, for a
 * `planned` / `closing` / `closed` chapter, the stored body through
 * `react-markdown` with NO editor and NO save control at all, under
 * `resolveEditability`'s author-facing read-only reason, verbatim (D16 / DoD-8).
 *
 * **The divergence view and the eviction notice (step 007).** Both live INSIDE the
 * body section, never as an early `return` from the component, so the rest of the
 * page keeps rendering (DoD-11). Inside that section the branch order is loading →
 * load-error → `state.isReconcilingBody` → the `state.canEditBody` fork, so while
 * the divergence view is open the editor is NOT mounted and `Save body` is NOT
 * rendered: the two side controls are the view's only controls. The view is a
 * normal landing, not an error state — plain in-flow layout (no modal, no overlay,
 * no focus trap), `yellow` rather than `red`, exactly two choices with neither
 * pre-selected and no third merged outcome, and both sides shown as raw readable
 * text with no diff library and no highlighting. The eviction notice names the
 * evicted keys whenever `state.evictedBufferKeys` is non-empty, independently of
 * the divergence flag.
 *
 * **The state transition (step 008).** EXACTLY ONE control, rendered inside the
 * chapter header's `Group` beside the ordinal and the state badge and only when
 * `state.offeredTransition` is non-null — `planned` → `Open`, `open` → `Close`,
 * `closed` → `Reopen`, and, since `016`, `closing` → `Stop` — never four with three
 * disabled. Its accessible name widens the visible action word with the chapter
 * (`Open chapter: {title}`), so it is reachable by role and label. Directly beneath
 * that group, still inside the header stack: the server's refusal
 * (`state.transitionError`) as a red alert, and `state.transitionUnavailableReason`
 * as readable text whenever a loaded chapter offers nothing. The control is offered
 * to EVERY member and gated on chapter state alone (D14); a non-owner's `403`, an
 * archived book's `403` and the one-open-chapter `409` are all surfaced rather than
 * predicted.
 *
 * **The close confirmation, the continuity section and the warnings section
 * (`016.chapter-close-continuity`).** `Close` is the one transition that asks first:
 * the control opens a Mantine `Modal` and **posts nothing**, and only the modal's
 * `Close chapter` control calls `requestChapterClose` (DoD-9) — closing is no longer
 * a reversible one-click change, it starts an assistant turn that takes over the chat
 * pane. Below the body: the chapter's summary and note changeset, READ-ONLY (they are
 * written by the close run's tools, never here), and its warnings — open and resolved,
 * newest first — with a raise form and a per-warning resolve control, both offered to
 * every member and both enforced server-side.
 *
 * **The canvas wiring (step 012).** The mount effect registers
 * `state.subjectSource` **with `state.applyDraft`**, so the open chapter is a
 * WRITABLE canvas target where 014 registered it as a subject only; the cleanup
 * unregisters the same token, which is what clears the selection registry too. The
 * editor's `onSelectionChange` feeds `setChapterSelection`, the one path the author's
 * selection takes into that registry (D5 — never persisted, never saved). Beside
 * `Save body`, an undo control labelled for what it undoes — **the assistant's last
 * write**, not "the last change", since the author's own typing is undone inside the
 * editor by ProseMirror's history (D6) — rendered-and-disabled while the stack for
 * this chapter is empty, its depth read straight from `work/chapterUndo.ts` rather
 * than through a computed over a non-observable `Map`. And, independently of every
 * body branch, a yellow alert for the one assistant write that was NOT applied: a
 * `replace_selection` frame that arrived with nothing selected changes nothing and is
 * reported, never appended and never placed at position zero.
 *
 * **What it must NOT render.** No delete control.
 *
 * **Hard rules.** `observer` (applied here). Handlers are inner functions closing
 * over the state — no `useCallback` / `useMemo` / `useReducer`, no custom `useX`
 * hook, no React context, no Mantine `useForm`. `useState` only to own the state
 * instance; `useEffect` only at page level, mount-load / unmount-cleanup. No
 * optimistic mutation: after either save the surface shows what the server
 * returned.
 */
export const ChapterPage = observer(function ChapterPage(): ReactElement {
  const { bookId, id } = useParams();

  const book = bookId ?? "";
  const chapterId = id ?? "";

  // The ids are read BEFORE the instance is built: since 015 step 012 the state stores
  // them for the two bound members the content-pane registry holds. `key={id}` on
  // `ChapterItemRoute` already forces a fresh instance when the route's chapter changes.
  const [state] = useState(() => new ChapterPageState(book, chapterId));

  useEffect(() => {
    const ctrl = new AbortController();
    // THE SAME registration 014 made, now WITH the apply-draft callback (015/012):
    // the open chapter is a WRITABLE canvas target, where 014 registered it as a
    // subject only. The source is read at send time, not snapshotted — the chapter's
    // lifecycle state is only known once the load resolves — and it is also the
    // identity token for the register, the unregister and the selection registry, so
    // it lives on the state instance rather than in this closure.
    registerContentSubject(state.subjectSource, state.applyDraft);
    void loadChapter(state, book, chapterId, ctrl.signal);
    void loadSystemPrompt(state, book, chapterId, ctrl.signal);
    // The third load joins the same single controller and aborts with the others.
    void loadChapterBody(state, book, chapterId, ctrl.signal);
    // 016: two more loads on the SAME controller — the chapter's warnings and its
    // note changeset. Each has its own trio and fails independently of the other
    // four, so neither can blank the chapter, the body or the prompt.
    void loadChapterWarnings(state, book, chapterId, ctrl.signal);
    void loadChapterChangeset(state, book, chapterId, ctrl.signal);
    return () => {
      // Unregistering clears the SELECTION too — `contentSubject.ts`'s shipped
      // `clearContentSelection(source)`, identity-guarded on this same token.
      unregisterContentSubject(state.subjectSource);
      ctrl.abort();
    };
  }, [state]);

  /** Error-state retry for the chapter trio alone — the prompt trio is untouched. */
  const handleRetryChapter = () => {
    void loadChapter(state, book, chapterId);
  };

  /** Save the sketch; the draft is read off the state by `saveSketch` itself. */
  const handleSaveSketch = () => {
    if (!state.canSaveSketch) return;
    void saveSketch(state, book, chapterId);
  };

  /** Save the caller's own prompt; the draft is read off the state by the effect. */
  const handleSavePrompt = () => {
    if (!state.canSaveSystemPrompt) return;
    void saveSystemPrompt(state, book, chapterId);
  };

  /** Save the body; the draft AND its base version are read off the state. */
  const handleSaveBody = () => {
    if (!state.canSaveBody) return;
    void saveChapterBody(state, book, chapterId);
  };

  /**
   * Undo THE ASSISTANT'S LAST WRITE (015/012) — pop this chapter's most recent
   * snapshot back into the draft. Not "undo the last change": the author's own typing
   * is undone inside the editor by ProseMirror's own history (D6), and the label says
   * exactly what this control does.
   */
  const handleUndoAssistantWrite = () => {
    undoAssistantBodyWrite(state, book, chapterId);
  };

  /** Take the SERVER's side whole: the draft and its buffer are discarded (015/007). */
  const handleKeepServerBody = () => {
    void resolveBodyConflict(state, "server", book, chapterId);
  };

  /** Take the DRAFT's side whole: the server's version is adopted, then the draft re-saved. */
  const handleKeepDraftBody = () => {
    void resolveBodyConflict(state, "draft", book, chapterId);
  };

  /**
   * Run the ONE transition currently on offer — exactly the effect matching
   * `state.offeredTransition`, never a different one. `null` means no control was
   * rendered at all.
   *
   * **`close` is the exception and posts NOTHING here (016 / DoD-9):** it opens the
   * confirmation and returns. Closing is no longer a reversible one-click state
   * change — it starts an assistant turn that takes over the chat pane for its
   * duration (D1 / D4) — which is a thing to say out loud before it happens. The
   * other three go straight to their effect, as 015 shipped them.
   */
  const handleTransition = () => {
    switch (state.offeredTransition) {
      case "open":
        void openChapterState(state, book, chapterId);
        return;
      case "close":
        // ASKS, does not post. `requestChapterClose` runs only from the dialog's
        // affirmative control below.
        state.closeConfirmOpen = true;
        return;
      case "reopen":
        void reopenChapterState(state, book, chapterId);
        return;
      case "cancel":
        // Stop: abandon the close run (D4). It aborts the live stream AND posts
        // `close/cancel`, which is what returns the chapter to `open`.
        void cancelChapterCloseRequest(state, book, chapterId);
        return;
      default:
        return;
    }
  };

  /** The confirmed close — the only caller of `requestChapterClose` (016 / DoD-9). */
  const handleConfirmClose = () => {
    void requestChapterClose(state, book, chapterId);
  };

  /** Dismiss the close confirmation, having posted nothing. */
  const handleDismissClose = () => {
    state.closeConfirmOpen = false;
  };

  /** Raise a warning from the draft comment; the draft is cleared only on acceptance. */
  const handleRaiseFlag = () => {
    if (state.raiseFlagDraft.trim() === "") return;
    void raiseChapterFlag(state, book, chapterId, state.raiseFlagDraft);
  };

  /** Resolve one warning. Owner-only server-side; a co-author's `403` is surfaced. */
  const handleResolveFlag = (flagId: string) => {
    void resolveChapterFlag(state, book, chapterId, flagId);
  };

  const chapter = state.chapter;
  const chapterLoading = state.chapterStatus === "idle" || state.chapterStatus === "loading";
  const promptLoading =
    state.systemPromptStatus === "idle" || state.systemPromptStatus === "loading";
  const sketchErrorMessages = Object.values(state.sketchServerErrors);
  const promptErrorMessages = Object.values(state.systemPromptServerErrors);

  const body = state.body;
  const bodyLoading = state.bodyStatus === "idle" || state.bodyStatus === "loading";
  const bodyErrorMessages = Object.values(state.bodyServerErrors);
  // The read-only reason is `work/subject.ts`'s copy, rendered VERBATIM — no new
  // string is written here — and it is derived from the BODY response's state, like
  // `canEditBody`, never from `chapter.state` (which is what `sketchDisabledReason`
  // answers about; the two are independent).
  const bodyReadOnlyReason =
    body === null
      ? null
      : resolveEditability({
          kind: "chapter",
          entityId: chapterId,
          chapterState: body.state,
        }).readOnlyReason;

  return (
    <Container size="lg" py="md">
      <Stack gap="lg">
        {/* THE CLOSE CONFIRMATION (016 / DoD-9) — the Close control GATES on it:
            clicking Close posts nothing at all, and only the affirmative control
            here calls `requestChapterClose`. Rendered at the top of the page's
            stack, outside every trio branch, so it cannot be unmounted underneath
            the author by a load that resolves while it is open.

            The affirmative is named "Close chapter" and NOT the bare word "Close",
            which is Mantine's own dismiss control's name. */}
        <Modal
          opened={state.closeConfirmOpen}
          onClose={handleDismissClose}
          title="Close this chapter?"
        >
          <Stack gap="sm">
            <Text size="sm">
              Closing starts a conversation with the assistant: it writes the chapter&apos;s
              summary, works out what changed in the book&apos;s state notes and checks the
              chapter against the rest of the book. The chat is unavailable for anything
              else until it finishes, and the chapter only closes if the run comes back
              clean.
            </Text>
            <Text size="sm" c="dimmed">
              You can stop it at any time from this page. Stopping discards whatever the
              run had drafted and returns the chapter to Open.
            </Text>
            <Group justify="flex-end">
              <Button variant="default" onClick={handleDismissClose}>
                Keep writing
              </Button>
              <Button onClick={handleConfirmClose}>Close chapter</Button>
            </Group>
          </Stack>
        </Modal>

        {/* THE CHAPTER TRIO — its own loading and error branches. The prompt
            section below is a sibling, so neither branch can hide it (DoD-11). */}
        {chapterLoading ? (
          <Group justify="center" py="md" gap="xs">
            <Loader size="sm" />
            <Text size="sm" c="dimmed">
              Loading…
            </Text>
          </Group>
        ) : state.chapterStatus === "error" || chapter === null ? (
          <Alert color="red" title="Could not load the chapter">
            <Stack gap="sm" align="flex-start">
              <Text size="sm">{state.chapterError}</Text>
              <Button size="xs" variant="light" onClick={handleRetryChapter}>
                Retry
              </Button>
            </Stack>
          </Alert>
        ) : (
          <>
            <Stack gap={4}>
              <Title order={3}>{chapter.title}</Title>
              <Group gap="sm" align="center">
                {/* The ordinal, then the lifecycle word in BOTH the text and the
                    accessible name — a colour is not a state (DoD-1). Same wording
                    as the chapters list's badge, by `lifecycleStateLabel`. */}
                <Text size="sm" c="dimmed">
                  {chapter.ordinal}
                </Text>
                <Badge variant="light" size="sm" aria-label={state.lifecycleStateLabel}>
                  {state.lifecycleStateLabel}
                </Badge>
                {/* THE ONE TRANSITION CONTROL (015/008) — rendered BESIDE the state
                    badge, which is what makes an absent control legible rather than
                    mysterious. The state machine admits exactly one transition per
                    state, so there is never a second control and never a disabled one:
                    a transition that is not offered is not rendered. Offered to EVERY
                    member, gated on chapter state alone (D14) — a non-owner's attempt
                    is refused `403` and the message is surfaced below. */}
                {state.offeredTransition !== null && (
                  <Button
                    size="xs"
                    variant="light"
                    aria-label={`${TRANSITION_LABELS[state.offeredTransition]} chapter: ${chapter.title}`}
                    disabled={state.transitionStatus === "loading"}
                    onClick={handleTransition}
                  >
                    {TRANSITION_LABELS[state.offeredTransition]}
                  </Button>
                )}
              </Group>
              {/* The server's refusal, verbatim — D14's accepted cost paid where the
                  author can read it. Nothing else on the page moved. */}
              {state.transitionError !== null && (
                <Alert color="red" title="Could not change the chapter state">
                  <Text size="sm">{state.transitionError}</Text>
                </Alert>
              )}
              {/* The `closing` case: NO control at all, and a stated reason naming the
                  close gate as not yet built — `closing` is a state the author cannot
                  currently produce (D8) and will not recognise, so it is the one state
                  that gets a sentence rather than silence. Readable text, never a
                  visual state. */}
              {state.transitionUnavailableReason !== null && (
                <Text size="sm" c="dimmed">
                  {state.transitionUnavailableReason}
                </Text>
              )}
            </Stack>

            <Divider />

            {/* THE SKETCH EDITOR — editable only while the chapter is `planned`
                (UC-033 / US-034.AC-1). The client affordance never substitutes for
                the server's `409`, which lands in `sketchServerErrors` (DoD-4). */}
            <Stack gap="xs">
              <Title order={5}>Chapter sketch</Title>
              {sketchErrorMessages.length > 0 && (
                <Alert color="red" title="Could not save the sketch">
                  <Stack gap={4}>
                    {sketchErrorMessages.map((message) => (
                      <Text key={message} size="sm">
                        {message}
                      </Text>
                    ))}
                  </Stack>
                </Alert>
              )}
              <Textarea
                label="Sketch"
                placeholder="What happens in this chapter?"
                value={state.sketchDraft}
                autosize
                minRows={6}
                disabled={!state.canEditSketch}
                onChange={(event) => {
                  state.sketchDraft = event.currentTarget.value;
                }}
              />
              {/* DoD-3's "with a stated reason" is READABLE TEXT, never a visual
                  state — a role/label query and a screen reader both reach it. */}
              {state.sketchDisabledReason !== null && (
                <Text size="sm" c="dimmed">
                  {state.sketchDisabledReason}
                </Text>
              )}
              {/* A non-`planned` chapter offers NO save at all (DoD-3); where a save
                  is possible it is gated on `canSaveSketch` (DoD-5). */}
              {state.canEditSketch && (
                <Group>
                  <Button onClick={handleSaveSketch} disabled={!state.canSaveSketch}>
                    Save sketch
                  </Button>
                </Group>
              )}
            </Stack>
          </>
        )}

        <Divider />

        {/* THE CHAPTER BODY (015/006) — a THIRD trio and a SIBLING section: it is
            deliberately outside the chapter section's success path, so a body
            failure cannot blank the chapter or the prompt and neither of those can
            hide the body (DoD-1). The editor is mounted ONLY for an `open` chapter
            (D16); every other state renders the stored body read-only. */}
        <Stack gap="xs">
          <Title order={5}>Chapter body</Title>

          {/* THE EVICTION NOTICE (015/007) — an eviction is data loss on some OTHER
              item, so it is never silent: the keys that went are named. Rendered
              independently of the divergence flag and of every body branch, since a
              write that evicted happened whatever the region is showing now. */}
          {state.evictedBufferKeys.length > 0 && (
            <Alert color="yellow" title="Other unsaved drafts were removed">
              <Stack gap={2}>
                <Text size="sm">
                  Storage was full, so these buffered drafts were removed to keep this one:
                </Text>
                {state.evictedBufferKeys.map((evictedKey) => (
                  <Text key={evictedKey} size="sm">
                    {evictedKey}
                  </Text>
                ))}
              </Stack>
            </Alert>
          )}

          {/* THE UNAPPLIED ASSISTANT WRITE (015/012) — a `replace_selection` frame
              arrived with nothing selected, so it was REFUSED rather than placed
              somewhere nobody chose: no append, no write at position zero, nothing
              changed. The author is told, and is shown the text the assistant wrote so
              it is not simply lost. Rendered independently of every body branch,
              exactly where and how the eviction notice above is. */}
          {state.unappliedSelectionWrite !== null && (
            <Alert color="yellow" title="The assistant's write was not applied">
              <Stack gap={2}>
                <Text size="sm">
                  Nothing was selected when the assistant tried to replace the selection, so
                  nothing was changed. Here is what it wrote:
                </Text>
                <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                  {state.unappliedSelectionWrite}
                </Text>
              </Stack>
            </Alert>
          )}

          {bodyLoading ? (
            <Group justify="center" py="md" gap="xs">
              <Loader size="sm" />
              <Text size="sm" c="dimmed">
                Loading…
              </Text>
            </Group>
          ) : state.bodyStatus === "error" || body === null ? (
            <Alert color="red" title="Could not load the chapter body">
              <Text size="sm">{state.bodyError}</Text>
            </Alert>
          ) : state.isReconcilingBody ? (
            /* THE DIVERGENCE VIEW (015/007) — reached from BOTH entrances: a stale
               buffer found at load (the load-bearing one, where no save was
               attempted) and a `409` from the save. Checked BEFORE the `canEditBody`
               fork, so it replaces the editor AND its `Save body` control while it is
               open, and a stale buffer on a no-longer-`open` chapter still reaches a
               view rather than raising a flag nothing renders.

               It is the NORMAL landing for the navigated-away-mid-turn path, not an
               error state (`frontend-work-drafts.md`): plain in-flow layout — no
               modal, no drawer, no overlay, no focus trap — `yellow` rather than
               `red`, and rendered INSIDE the body section, so the chapter, the sketch
               and the prompt sections all keep rendering beside it.

               The two sides are shown as RAW text, not through `react-markdown`:
               they are compared literally, and rendering one of them would hide
               exactly the differences the author is choosing between. Two choices,
               neither pre-selected, and no third — a merged body is something the
               author types (no diff library, no highlighting, no merged pane). */
            <Stack gap="md">
              <Title order={4}>Unsaved changes diverged</Title>
              <Alert color="yellow" title="This chapter's body changed since your draft">
                This chapter&apos;s body changed on the server while your draft was unsaved.
                Nothing has been merged — choose which version to keep.
              </Alert>
              <Group align="stretch" grow>
                <Paper withBorder p="sm">
                  <Stack gap="xs">
                    <Title order={5}>Current server version</Title>
                    <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                      {state.bodyConflict?.text ?? ""}
                    </Text>
                    <Button variant="light" onClick={handleKeepServerBody}>
                      Keep the server version
                    </Button>
                  </Stack>
                </Paper>
                <Paper withBorder p="sm">
                  <Stack gap="xs">
                    <Title order={5}>Your draft</Title>
                    <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                      {state.bodyDraft}
                    </Text>
                    <Button onClick={handleKeepDraftBody}>Keep my draft</Button>
                  </Stack>
                </Paper>
              </Group>
            </Stack>
          ) : state.canEditBody ? (
            <>
              {bodyErrorMessages.length > 0 && (
                <Alert color="red" title="Could not save the chapter body">
                  <Stack gap={4}>
                    {bodyErrorMessages.map((message) => (
                      <Text key={message} size="sm">
                        {message}
                      </Text>
                    ))}
                  </Stack>
                </Alert>
              )}
              {/* KEYED ON THE GENERATION COUNTER (D15) — the only thing the view
                  reads it for. A remount is how TipTap learns about a draft written
                  from outside it; a keystroke never bumps it, so the caret survives.
                  `onSelectionChange` feeds the page's selection state and, through it,
                  the module-level selection registry the chat pane reads at send time
                  (015/012; D5) — the selection is never persisted and never saved. */}
              <ChapterBodyEditor
                key={state.bodyEditorGeneration}
                initialMarkdown={state.bodyDraft}
                onChange={(markdown) => {
                  editBodyDraft(state, book, chapterId, markdown);
                }}
                onSelectionChange={(selectedText) => {
                  setChapterSelection(state, selectedText);
                }}
                ariaLabel="Chapter body"
              />
              <Group>
                <Button onClick={handleSaveBody} disabled={!state.canSaveBody}>
                  Save body
                </Button>
                {/* THE UNDO CONTROL (015/012) — beside `Save body`, so it exists only
                    where the editor does. RENDERED-AND-DISABLED when the stack is
                    empty, deliberately the opposite of the transition control above:
                    "there is nothing to undo yet" needs no sentence, and a control
                    that appeared only after the first assistant write would move the
                    save control under the author's cursor.

                    The depth is read straight from the module, NOT through a `get`
                    computed: `chapterUndoDepth` reads a plain `Map` with no observable
                    inside it, so a computed over it would be cached and never
                    invalidated. This read is current because every push and every pop
                    is paired with a bump of the OBSERVABLE
                    `state.bodyEditorGeneration`, which this component already reads
                    for the editor's `key` — that read is what schedules the
                    re-render. */}
                <Button
                  variant="light"
                  aria-label="Undo the assistant's last write"
                  disabled={chapterUndoDepth(book, chapterId) === 0}
                  onClick={handleUndoAssistantWrite}
                >
                  {"Undo the assistant's last write"}
                </Button>
              </Group>
            </>
          ) : (
            <>
              {/* NOT `open` (D16 / DoD-8): the stored body through `react-markdown`
                  with NO plugins configured (the repo's inherited default), no
                  editor and no save control at all — plus the stated reason. */}
              {bodyReadOnlyReason !== null && (
                <Text size="sm" c="dimmed">
                  {bodyReadOnlyReason}
                </Text>
              )}
              <Markdown>{body.text}</Markdown>
            </>
          )}
        </Stack>

        <Divider />

        {/* THE CHAPTER'S CONTINUITY (016) — its summary and its note changeset, both
            READ-ONLY here: they are written by the close run's assistant tools and by
            nothing on the client, which is why there is no draft and no save control
            in this section. A chapter that has never been closed has neither, and says
            so rather than rendering an empty box (DoD-12). */}
        <Stack gap="xs">
          <Title order={5}>Chapter continuity</Title>

          <Group gap="sm" align="center">
            <Text size="sm" fw={600}>
              Summary
            </Text>
            {chapter?.summary_status != null && (
              <Badge
                variant="light"
                size="sm"
                aria-label={CONTINUITY_STATUS_LABELS[chapter.summary_status]}
              >
                {CONTINUITY_STATUS_LABELS[chapter.summary_status]}
              </Badge>
            )}
          </Group>
          {chapter?.summary ? (
            <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
              {chapter.summary}
            </Text>
          ) : (
            <Text size="sm" c="dimmed">
              This chapter has no summary yet. One is written when the chapter is closed.
            </Text>
          )}

          {state.changesetStatus === "error" ? (
            <Alert color="red" title="Could not load the state-note changeset">
              <Text size="sm">{state.changesetError}</Text>
            </Alert>
          ) : (
            <>
              <Group gap="sm" align="center">
                <Text size="sm" fw={600}>
                  What this chapter changed
                </Text>
                {state.changeset?.status != null && (
                  <Badge
                    variant="light"
                    size="sm"
                    aria-label={CONTINUITY_STATUS_LABELS[state.changeset.status]}
                  >
                    {CONTINUITY_STATUS_LABELS[state.changeset.status]}
                  </Badge>
                )}
              </Group>
              {state.changeset === null || state.changeset.status === null ? (
                <Text size="sm" c="dimmed">
                  Nothing has been recorded against the book&apos;s state notes for this
                  chapter yet.
                </Text>
              ) : (
                /* THREE SEPARATE DELTAS and no merged view: there is no correct
                   mechanical merge of three free-text deltas (backend D7). */
                <Stack gap={4}>
                  <Text size="sm" c="dimmed">
                    Added
                  </Text>
                  <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                    {state.changeset.added === "" ? "—" : state.changeset.added}
                  </Text>
                  <Text size="sm" c="dimmed">
                    Changed
                  </Text>
                  <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                    {state.changeset.modified === "" ? "—" : state.changeset.modified}
                  </Text>
                  <Text size="sm" c="dimmed">
                    No longer true
                  </Text>
                  <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                    {state.changeset.deleted === "" ? "—" : state.changeset.deleted}
                  </Text>
                </Stack>
              )}
            </>
          )}
        </Stack>

        <Divider />

        {/* THE CHAPTER'S WARNINGS (016; UC-067 / UC-068) — open AND resolved, newest
            first, each with where it came from. Raising is offered to every member and
            resolving is owner-only SERVER-SIDE: this page has no caller-role signal
            (the D14 rule), so both controls are rendered and the server's refusal is
            what the author reads. */}
        <Stack gap="xs">
          <Title order={5}>Warnings</Title>

          {state.warningsError !== null && (
            <Alert color="red" title="Could not load or change the warnings">
              <Text size="sm">{state.warningsError}</Text>
            </Alert>
          )}

          {state.warningsStatus === "idle" || state.warningsStatus === "loading" ? (
            <Group py="xs">
              <Loader size="sm" />
            </Group>
          ) : state.warnings.length === 0 ? (
            <Text size="sm" c="dimmed">
              No warnings on this chapter.
            </Text>
          ) : (
            <Stack gap="xs">
              {state.warnings.map((warning) => (
                <Paper key={warning.id} withBorder p="sm">
                  <Stack gap={4}>
                    <Group gap="sm" align="center">
                      <Badge
                        variant="light"
                        size="sm"
                        aria-label={FLAG_STATUS_LABELS[warning.status]}
                      >
                        {FLAG_STATUS_LABELS[warning.status]}
                      </Badge>
                      <Text size="sm" c="dimmed">
                        {FLAG_ORIGIN_LABELS[warning.origin]}
                      </Text>
                    </Group>
                    <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                      {warning.comment}
                    </Text>
                    {warning.status === "open" && (
                      <Group>
                        <Button
                          size="xs"
                          variant="light"
                          aria-label={`Resolve warning: ${warning.comment}`}
                          disabled={state.raiseFlagSubmitStatus === "loading"}
                          onClick={() => handleResolveFlag(warning.id)}
                        >
                          Resolve
                        </Button>
                      </Group>
                    )}
                  </Stack>
                </Paper>
              ))}
            </Stack>
          )}

          <Textarea
            label="Raise a warning"
            placeholder="What is wrong with this chapter, stated so someone can act on it?"
            value={state.raiseFlagDraft}
            autosize
            minRows={2}
            onChange={(event) => {
              state.raiseFlagDraft = event.currentTarget.value;
            }}
          />
          <Group>
            <Button
              onClick={handleRaiseFlag}
              disabled={
                state.raiseFlagDraft.trim() === "" ||
                state.raiseFlagSubmitStatus === "loading"
              }
            >
              Raise warning
            </Button>
          </Group>
        </Stack>

        <Divider />

        {/* THE CALLER'S OWN CHAPTER SYSTEM PROMPT — its own trio, its own branches,
            and NO lifecycle gate: a member writes their own prompt on a chapter in
            every state (DoD-10). No delete control (DoD-9), no client-side
            validation, no restore buffer, no `409` path. */}
        <Stack gap="xs">
          <Title order={5}>Your system prompt</Title>
          <Text size="sm" c="dimmed">
            This prompt is your own: every author of this book keeps their own for this chapter,
            and yours is not shared with your co-authors — they cannot see it or edit it.
          </Text>

          {promptLoading ? (
            <Group py="xs">
              <Loader size="sm" />
            </Group>
          ) : state.systemPromptStatus === "error" ? (
            <Alert color="red">
              {state.systemPromptError ?? "Could not load your system prompt."}
            </Alert>
          ) : (
            <>
              {promptErrorMessages.length > 0 && (
                <Alert color="red" title="Could not save your system prompt">
                  <Stack gap={4}>
                    {promptErrorMessages.map((message) => (
                      <Text key={message} size="sm">
                        {message}
                      </Text>
                    ))}
                  </Stack>
                </Alert>
              )}
              <Textarea
                label="System prompt"
                placeholder="Your own standing instructions for this chapter, saved with it."
                value={state.systemPromptDraft}
                autosize
                minRows={6}
                onChange={(event) => {
                  state.systemPromptDraft = event.currentTarget.value;
                }}
              />
              <Group>
                <Button onClick={handleSavePrompt} disabled={!state.canSaveSystemPrompt}>
                  Save system prompt
                </Button>
              </Group>
            </>
          )}
        </Stack>
      </Stack>
    </Container>
  );
});
