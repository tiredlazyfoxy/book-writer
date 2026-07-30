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
  Paper,
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import Markdown from "react-markdown";
import { registerContentSubject, unregisterContentSubject } from "../contentSubject";
import type { ContentSubjectSource } from "../contentSubject";
import { ChapterBodyEditor } from "../components/chapter/ChapterBodyEditor";
import { resolveEditability } from "../subject";
import {
  ChapterPageState,
  editBodyDraft,
  loadChapter,
  loadChapterBody,
  loadSystemPrompt,
  resolveBodyConflict,
  saveChapterBody,
  saveSketch,
  saveSystemPrompt,
} from "./chapterPageState";

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
 * `useState(() => new ChapterPageState())`, `useParams()` for `bookId` and `id`,
 * and EXACTLY ONE page-level `useEffect([state])` that: spins a single
 * `AbortController`; builds a stable subject source
 * `() => ({ kind: "chapter", entityId: id, chapterState: state.chapter?.state })` —
 * read at send time, so the pane model's editability answer is about THIS chapter
 * and reflects its state once the load resolves; calls `registerContentSubject`
 * with **NO `applyDraft`** (a `canvas` frame's `CanvasField` is `"name" | "body"`,
 * both codex fields — neither the sketch nor the prompt is a canvas region);
 * starts BOTH loads; and returns a cleanup calling `unregisterContentSubject`
 * then `ctrl.abort()` (DoD-14). The `key={id}` that makes a `:id` change produce a
 * FRESH state instance lives on `ChapterItemRoute` in `work/routes.tsx`.
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
 * **What it must NOT render.** No canvas / undo / selection wiring (step 012 —
 * `onSelectionChange` is a no-op today). No delete control, no chapter-state
 * transition control (step 008).
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
  const [state] = useState(() => new ChapterPageState());

  const book = bookId ?? "";
  const chapterId = id ?? "";

  useEffect(() => {
    const ctrl = new AbortController();
    // Read at send time, not snapshotted: the chapter's lifecycle state is only
    // known once the load resolves. The closure doubles as the unregister identity
    // token (DoD-14). NO apply-draft callback — neither editor is a canvas region.
    const source: ContentSubjectSource = () => ({
      kind: "chapter",
      entityId: chapterId,
      chapterState: state.chapter?.state,
    });
    registerContentSubject(source);
    void loadChapter(state, book, chapterId, ctrl.signal);
    void loadSystemPrompt(state, book, chapterId, ctrl.signal);
    // The third load joins the same single controller and aborts with the others.
    void loadChapterBody(state, book, chapterId, ctrl.signal);
    return () => {
      unregisterContentSubject(source);
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

  /** Take the SERVER's side whole: the draft and its buffer are discarded (015/007). */
  const handleKeepServerBody = () => {
    void resolveBodyConflict(state, "server", book, chapterId);
  };

  /** Take the DRAFT's side whole: the server's version is adopted, then the draft re-saved. */
  const handleKeepDraftBody = () => {
    void resolveBodyConflict(state, "draft", book, chapterId);
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
              </Group>
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
                  `onSelectionChange` is a no-op today: the seam's four props are all
                  required and D5's selection wiring is step 012's. */}
              <ChapterBodyEditor
                key={state.bodyEditorGeneration}
                initialMarkdown={state.bodyDraft}
                onChange={(markdown) => {
                  editBodyDraft(state, book, chapterId, markdown);
                }}
                onSelectionChange={() => {}}
                ariaLabel="Chapter body"
              />
              <Group>
                <Button onClick={handleSaveBody} disabled={!state.canSaveBody}>
                  Save body
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
