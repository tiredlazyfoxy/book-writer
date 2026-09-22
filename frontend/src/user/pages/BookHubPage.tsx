import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { useParams } from "react-router-dom";
import {
  Alert,
  Anchor,
  Badge,
  Container,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { BookHubPageState, loadBookDetail, loadChapterList } from "./bookHubPageState";

/**
 * Shell SPA book-hub page (`/books/:bookId`) — the READ-ONLY chapter skeleton view.
 *
 * Owns a stable `BookHubPageState` via `useState`, reads the `bookId` route param via
 * `useParams`, and starts BOTH loads (`loadBookDetail` + `loadChapterList`) from ONE
 * page-level `useEffect([state])` spinning a single `AbortController`, aborting on
 * unmount. The route element applies the `key={bookId}` remount rule (see
 * `routes.tsx`), so a different book id gets a fresh state instance and re-loads both
 * resources rather than showing the previous book's chapters.
 *
 * Renders: the book's title as the heading, the chapters in ordinal order each with a
 * readable state badge, an empty-state line when the book has no chapters yet, each
 * trio's own loading and error branch (the two are independent — a failed chapter load
 * must not destroy the heading, and vice versa), a link to each chapter's working-page
 * route (`/work/:bookId/chapter/:chapterId`) and a prominent link into the working page
 * (`/work/:bookId`). Both are plain `<a href>`: `/work` is a separate Vite entry, so
 * crossing to it is a full page load, not a react-router navigation
 * (`BookshelfPage.tsx` is the precedent).
 *
 * **It is read-only** (decision D2 — the Book hub reads, the working page edits): no
 * add form, no remove control, no reorder control, no editable field, nothing else.
 * All chapter mutation lives on `/work/:bookId/chapters` and
 * `/work/:bookId/chapter/:id` (steps 006–008).
 *
 * The chapters are sorted by `ordinal` before rendering: ordinal order is what the page
 * promises, and it must not depend on the order the envelope happened to arrive in. The
 * envelope itself is never unwrapped in state (`can_reorder` survives for steps 006/007),
 * this page simply ignores the hint.
 */
export const BookHubPage = observer(function BookHubPage() {
  const { bookId } = useParams();
  const [state] = useState(() => new BookHubPageState());

  const id = bookId ?? "";

  // The ONE page-level mount effect: a single AbortController drives BOTH loads and
  // aborts them on unmount. The two loaders are separate so the trios fail independently.
  useEffect(() => {
    const ctrl = new AbortController();
    void loadBookDetail(state, id, ctrl.signal);
    void loadChapterList(state, id, ctrl.signal);
    return () => ctrl.abort();
  }, [state]);

  const detailLoading =
    state.detailStatus === "idle" || state.detailStatus === "loading";
  const chaptersLoading =
    state.chapterListStatus === "idle" || state.chapterListStatus === "loading";

  const chapters = state.chapterList
    ? [...state.chapterList.chapters].sort((a, b) => a.ordinal - b.ordinal)
    : null;

  return (
    <Container size="lg" py="md">
      <Stack gap="xl">
        <Stack gap="xs">
          {state.detailError && (
            <Alert color="red" title="Could not load this book">
              {state.detailError}
            </Alert>
          )}
          {detailLoading ? (
            <Group justify="center" py="md">
              <Loader />
            </Group>
          ) : (
            state.detail && <Title order={3}>{state.detail.title}</Title>
          )}
          <Group>
            {/* Plain <a>: /work is a separate Vite entry, so crossing to it is a full
                page load, not a react-router navigation. */}
            <Anchor href={`/work/${id}`} fw={700}>
              Open the working page
            </Anchor>
          </Group>
        </Stack>

        <Stack gap="xs">
          <Title order={4}>Chapters</Title>
          {state.chapterListError && (
            <Alert color="red" title="Could not load the chapters">
              {state.chapterListError}
            </Alert>
          )}
          {chaptersLoading ? (
            <Group justify="center" py="md">
              <Loader />
            </Group>
          ) : chapters && chapters.length === 0 ? (
            <Text c="dimmed">No chapters yet.</Text>
          ) : (
            chapters && (
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>#</Table.Th>
                    <Table.Th>Title</Table.Th>
                    <Table.Th>State</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {chapters.map((chapter) => (
                    <Table.Tr key={chapter.id}>
                      <Table.Td>
                        <Text size="sm">{chapter.ordinal}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Anchor href={`/work/${id}/chapter/${chapter.id}`}>
                          <Text size="sm">{chapter.title}</Text>
                        </Anchor>
                      </Table.Td>
                      <Table.Td>
                        <Badge variant="light" size="sm">
                          {chapter.state}
                        </Badge>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )
          )}
        </Stack>
      </Stack>
    </Container>
  );
});
