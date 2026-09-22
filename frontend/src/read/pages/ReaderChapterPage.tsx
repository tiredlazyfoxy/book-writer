import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { Link, useParams } from "react-router-dom";
import {
  Alert,
  Anchor,
  Container,
  Group,
  Loader,
  Stack,
  Title,
} from "@mantine/core";
import Markdown from "react-markdown";
import {
  ReaderChapterPageState,
  loadReaderChapter,
} from "./readerChapterPageState";

/**
 * Reader SPA `/:bookId/:chapterId` — one chapter's saved text, read-only
 * (UC-029, US-030.AC-2).
 *
 * Owns a stable `ReaderChapterPageState` via `useState`, reads `bookId` and
 * `chapterId` from `useParams`, and starts the single load from ONE page-level
 * `useEffect([state])` spinning an `AbortController` that aborts on unmount.
 * `routes.tsx` applies `key={chapterId}`, so following one chapter link to the
 * next inside the same book still remounts with fresh state.
 *
 * The body is rendered with `<Markdown>{chapter.text}</Markdown>` — no
 * `remarkPlugins`, no `rehypePlugins`, no `components` prop (decision D11,
 * inherited from the delivered `work/pages/ChapterPage.tsx` call, not
 * re-decided).
 *
 * **NO EDIT AFFORDANCE OF ANY KIND** (DoD-9, DoD-17): no textbox, no textarea, no
 * contentEditable, no save/edit/publish control, and no import of
 * `@mantine/tiptap` or any editor component — here or anywhere else under
 * `src/read/`. That absence is the build-time property the separate Vite entry
 * exists to guarantee.
 */
export const ReaderChapterPage = observer(function ReaderChapterPage() {
  const { bookId, chapterId } = useParams();
  const [state] = useState(() => new ReaderChapterPageState());

  const id = bookId ?? "";
  const cid = chapterId ?? "";

  // The ONE page-level mount effect: a single AbortController drives the load and
  // aborts it on unmount.
  useEffect(() => {
    const ctrl = new AbortController();
    void loadReaderChapter(state, id, cid, ctrl.signal);
    return () => ctrl.abort();
  }, [state]);

  const loading =
    state.chapterStatus === "idle" || state.chapterStatus === "loading";

  return (
    <Container size="md" py="md">
      <Stack gap="md">
        <Anchor component={Link} to={`/${id}`}>
          Back to contents
        </Anchor>

        {state.chapterError && (
          <Alert color="red" title="Could not open this chapter">
            {state.chapterError}
          </Alert>
        )}

        {loading ? (
          <Group justify="center" py="md">
            <Loader />
          </Group>
        ) : (
          state.chapter && (
            <Stack gap="sm">
              <Title order={3}>{state.chapter.title}</Title>
              <Markdown>{state.chapter.text}</Markdown>
            </Stack>
          )
        )}
      </Stack>
    </Container>
  );
});
