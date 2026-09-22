import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { Link, useParams } from "react-router-dom";
import {
  Alert,
  Anchor,
  Container,
  Group,
  List,
  Loader,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import {
  TableOfContentsPageState,
  loadReaderBook,
} from "./tableOfContentsPageState";

/**
 * Reader SPA `/:bookId` — the book's table of contents (UC-029, US-030.AC-1).
 *
 * Owns a stable `TableOfContentsPageState` via `useState`, reads `bookId` from
 * `useParams`, and starts the single load from ONE page-level `useEffect([state])`
 * spinning an `AbortController` that aborts on unmount. `routes.tsx` applies
 * `key={bookId}`, so a different book gets a fresh state instance.
 *
 * The chapters render **in the order the API returned them**: the backend already
 * filtered to the reader-visible states and sorted by ordinal, and deliberately
 * put no ordinal on the wire — list order *is* reading order, so there is nothing
 * to re-sort by here.
 *
 * Each chapter is a react-router `<Link>` to `/:bookId/:chapterId` — in-SPA
 * navigation under the `/read` basename, not a cross-entry `<a href>`.
 *
 * **Read-only**: no edit control, no create/reorder affordance, no state badge —
 * only the title, the chapter links and the three status branches. The error
 * branch renders `state.bookError`, so a refusal is always a visible message and
 * never a blank pane (DoD-8).
 */
export const TableOfContentsPage = observer(function TableOfContentsPage() {
  const { bookId } = useParams();
  const [state] = useState(() => new TableOfContentsPageState());

  const id = bookId ?? "";

  // The ONE page-level mount effect: a single AbortController drives the load and
  // aborts it on unmount.
  useEffect(() => {
    const ctrl = new AbortController();
    void loadReaderBook(state, id, ctrl.signal);
    return () => ctrl.abort();
  }, [state]);

  const loading = state.bookStatus === "idle" || state.bookStatus === "loading";
  const chapters = state.book ? state.book.chapters : null;

  return (
    <Container size="md" py="md">
      <Stack gap="md">
        {state.bookError && (
          <Alert color="red" title="Could not open this book">
            {state.bookError}
          </Alert>
        )}

        {loading ? (
          <Group justify="center" py="md">
            <Loader />
          </Group>
        ) : (
          state.book && (
            <>
              <Title order={3}>{state.book.title}</Title>
              <Stack gap="xs">
                <Title order={5}>Contents</Title>
                {chapters && chapters.length === 0 ? (
                  <Text c="dimmed">
                    This book has no chapters available to read yet.
                  </Text>
                ) : (
                  chapters && (
                    <List spacing="xs">
                      {chapters.map((chapter) => (
                        <List.Item key={chapter.id}>
                          <Anchor
                            component={Link}
                            to={`/${id}/${chapter.id}`}
                          >
                            {chapter.title}
                          </Anchor>
                        </List.Item>
                      ))}
                    </List>
                  )
                )}
              </Stack>
            </>
          )
        )}
      </Stack>
    </Container>
  );
});
