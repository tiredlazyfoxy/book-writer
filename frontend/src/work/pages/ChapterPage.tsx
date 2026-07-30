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
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { registerContentSubject, unregisterContentSubject } from "../contentSubject";
import type { ContentSubjectSource } from "../contentSubject";
import {
  ChapterPageState,
  loadChapter,
  loadSystemPrompt,
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
 * **What it must NOT render.** The chapter's BODY TEXT, in any form, editable or
 * not — it is `015.chapter-writing-free-mode`'s and `ChapterResponse` does not
 * carry it. No restore-buffer surface, no divergence/reconciliation view, no
 * delete control, no chapter-state transition control.
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

  const chapter = state.chapter;
  const chapterLoading = state.chapterStatus === "idle" || state.chapterStatus === "loading";
  const promptLoading =
    state.systemPromptStatus === "idle" || state.systemPromptStatus === "loading";
  const sketchErrorMessages = Object.values(state.sketchServerErrors);
  const promptErrorMessages = Object.values(state.systemPromptServerErrors);

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
