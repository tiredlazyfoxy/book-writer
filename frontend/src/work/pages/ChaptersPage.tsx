import { useEffect, useState } from "react";
import type { FormEvent, ReactElement } from "react";
import { observer } from "mobx-react-lite";
import { useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Container,
  Divider,
  Group,
  Loader,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import { ChapterOrderList } from "../components/chapters/ChapterOrderList";
import { registerContentSubject, unregisterContentSubject } from "../contentSubject";
import type { SubjectKind } from "../subject";
import { ChaptersPageState, addChapter, loadChapters } from "./chaptersPageState";

/**
 * The content-pane subject kind this page IS — `work/subject.ts`'s plural `chapters`
 * member (UC-090: a list is a subject too). Module-private: nothing outside needs it.
 */
const CHAPTERS_SUBJECT_KIND: SubjectKind = "chapters";

/**
 * The working page's chapter list (`/work/:bookId/chapters`) — the ADD and REMOVE
 * surface of the chapter skeleton (FEAT-008 · UC-031 / UC-034 · US-032 / US-035).
 * Decision D2: the Shell's book hub reads, this page edits.
 *
 * Zero props — the book id comes from `useParams`.
 *
 * The component symbol and its zero-prop shape are FROZEN (skeleton 014/006). The
 * contract the body implements, and may not widen:
 *
 * **Structure (`CodexListPage` is the model).** One `useState(() => new ChaptersPageState())`,
 * `useParams()` for `bookId`, and exactly ONE page-level `useEffect([state])` that:
 * spins a single `AbortController`; builds a stable subject `source` closure
 * `() => ({ kind: "chapters" })` (`SubjectKind` from `../subject`, which is NOT edited);
 * calls `registerContentSubject(source)` from `../contentSubject` with **NO
 * `applyDraft`** — the pane model treats "Any list" as read-only and the add/remove
 * controls are page chrome, not a writable canvas region; starts
 * `loadChapters(state, bookId ?? "", ctrl.signal)`; and returns a cleanup that calls
 * `unregisterContentSubject(source)` and `ctrl.abort()` (DoD-12). `contentSubject.ts`
 * and `subject.ts` are CALLED here, never changed.
 *
 * **What it renders.**
 * - The list trio's `"idle" | "loading"` branch and its `"error"` branch, the latter
 *   carrying a retry control that re-runs `loadChapters` — and, in the error branch, NO
 *   add form and NO rows, so nothing is bound to stale data (DoD-10).
 * - The chapter rows — through `<ChapterOrderList state={state} bookId={id} />` and
 *   NOWHERE ELSE. Step 007 MOVED the row rendering (ordinal, title link, state badge,
 *   remove control, per-chapter removal message) out of this page and into that
 *   component, which is now the single rendering site for a chapter row; this page has
 *   no `renderChapterRow` of its own and must not grow one back.
 * - The **reorder error surface**: `state.reorderError` as a list-level message,
 *   independent of `state.chapterListError`, `state.addServerErrors` and
 *   `state.removeServerErrors` (step 007, DoD-5 / DoD-8). A reorder concerns the whole
 *   list, so it is not a per-row message.
 * - An empty state when the load succeeded with no chapters, alongside a usable add form
 *   (DoD-2) — an empty list is never an error branch.
 * - The **add form**: a labelled title field bound to `state.addTitleDraft`, a labelled
 *   multi-line sketch field bound to `state.addSketchDraft`, a submit control gated on
 *   `state.canSubmitAdd` (so it is unavailable while the title is blank or
 *   whitespace-only and while a submit is in flight — DoD-5), and a surface for
 *   `state.addServerErrors` (DoD-6). Submitting calls `addChapter(state, bookId ?? "")`.
 * The **remove control** (only when `state.canRemoveChapter(chapter)`, accessible name
 * `Remove "<title>"`, DoD-8) and its per-chapter refusal message (DoD-9) live in
 * `ChapterOrderList` now, together with `state.canReorder`'s move / drag affordances.
 * This page neither renders nor calls them.
 *
 * **Hard rules.** `observer` (applied here). Handlers are inner functions closing over
 * the state — no extracted callbacks, no `useCallback` / `useMemo` / `useReducer`, no
 * custom `useX` hook, no React context, no Mantine `useForm`. `useState` only to own the
 * state instance; `useEffect` only at page level, mount-load / unmount-cleanup. No
 * optimistic mutation anywhere — after a write the surface shows what the server
 * returned.
 */
export const ChaptersPage = observer(function ChaptersPage(): ReactElement {
  const { bookId } = useParams();
  const [state] = useState(() => new ChaptersPageState());

  const id = bookId ?? "";

  useEffect(() => {
    const ctrl = new AbortController();
    // A list is a subject with a KIND and no id, and with NO canvas target: an
    // assistant draft can never be applied to a list, so it registers NO apply-draft
    // callback. The source doubles as the unregister identity token (DoD-12).
    const source = () => ({ kind: CHAPTERS_SUBJECT_KIND });
    registerContentSubject(source);
    void loadChapters(state, id, ctrl.signal);
    return () => {
      unregisterContentSubject(source);
      ctrl.abort();
    };
  }, [state]);

  /** Error-state retry — re-runs the loader (DoD-10). */
  const handleRetry = () => {
    void loadChapters(state, id);
  };

  /** Submit the add form; the drafts are read off the state by `addChapter` itself. */
  const handleAddSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!state.canSubmitAdd) return;
    void addChapter(state, id);
  };

  // The failed-load branch: a retry, and NEITHER rows NOR the add form, so nothing is
  // bound to stale data (DoD-10).
  if (state.chapterListStatus === "error") {
    return (
      <Container size="lg" py="md">
        <Stack gap="md">
          <Title order={3}>Chapters</Title>
          <Alert color="red" title="Could not load the chapters">
            <Stack gap="sm" align="flex-start">
              <Text size="sm">{state.chapterListError}</Text>
              <Button size="xs" variant="light" onClick={handleRetry}>
                Retry
              </Button>
            </Stack>
          </Alert>
        </Stack>
      </Container>
    );
  }

  const listLoading =
    state.chapterListStatus === "idle" || state.chapterListStatus === "loading";
  const chapters = state.orderedChapters;
  const addErrorMessages = Object.values(state.addServerErrors);

  return (
    <Container size="lg" py="md">
      <Stack gap="lg">
        <Title order={3}>Chapters</Title>

        {/* The reorder refusal — a LIST-level message, and its own surface: it never
            shares a holder with the load error, the add form's errors or a per-chapter
            removal message (DoD-8). */}
        {state.reorderError && (
          <Alert color="red" title="Could not reorder the chapters">
            {state.reorderError}
          </Alert>
        )}

        {listLoading ? (
          <Group justify="center" py="md" gap="xs">
            <Loader size="sm" />
            <Text size="sm" c="dimmed">
              Loading…
            </Text>
          </Group>
        ) : chapters.length === 0 ? (
          <Text size="sm" c="dimmed">
            No chapters yet.
          </Text>
        ) : (
          /* The SINGLE rendering site for a chapter row (step 007). This page owns no
             row markup: move controls, drag affordance and the moved step-006 row
             content all live there, so the two affordances cannot diverge. */
          <ChapterOrderList state={state} bookId={id} />
        )}

        <Divider />

        <form onSubmit={handleAddSubmit}>
          <Stack gap="xs">
            <Title order={5}>Add a chapter</Title>
            {addErrorMessages.length > 0 && (
              <Alert color="red" title="Could not add the chapter">
                <Stack gap={4}>
                  {addErrorMessages.map((message) => (
                    <Text key={message} size="sm">
                      {message}
                    </Text>
                  ))}
                </Stack>
              </Alert>
            )}
            <TextInput
              label="Title"
              placeholder="What is this chapter called?"
              value={state.addTitleDraft}
              onChange={(event) => {
                state.addTitleDraft = event.currentTarget.value;
              }}
            />
            <Textarea
              label="Sketch"
              placeholder="What happens in this chapter? (optional)"
              value={state.addSketchDraft}
              autosize
              minRows={3}
              onChange={(event) => {
                state.addSketchDraft = event.currentTarget.value;
              }}
            />
            <Group>
              <Button type="submit" disabled={!state.canSubmitAdd}>
                Add chapter
              </Button>
            </Group>
          </Stack>
        </form>
      </Stack>
    </Container>
  );
});
