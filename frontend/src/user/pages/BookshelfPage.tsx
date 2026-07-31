import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import {
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { IconPlus } from "@tabler/icons-react";
import type { BookResponse } from "../../types/books";
import type { PublicBookRef } from "../../types/reader";
import { BookshelfPageState, loadBookshelf } from "./bookshelfPageState";
import { CreateBookModal } from "../components/books/CreateBookModal";

/**
 * Shell SPA root page (`/`) — the bookshelf. Owns a stable `BookshelfPageState`
 * via `useState`, loads all three lists on mount / aborts on unmount via a single
 * page-level `useEffect([state])` spinning an `AbortController`. Renders the owned,
 * shared and public book lists (three async-resource trios) plus a header Create
 * button and the create-book modal; a successful create re-loads the shelf. Modal
 * open flag is component-local `useState`, not page state.
 *
 * "Public books" (feature 022, D16) is the discovery feed: books the caller can
 * READ but is not part of. It gets its own renderer rather than reusing
 * `renderList` — the rows are `PublicBookRef`, which deliberately carries no
 * visibility, state or owner (D14) — and its rows link into `/read/<id>` with a
 * plain `<a href>`, because the reader is a separate Vite entry and crossing to it
 * is a full page load, not a react-router navigation.
 */
export const BookshelfPage = observer(function BookshelfPage() {
  const [state] = useState(() => new BookshelfPageState());
  const [createOpen, setCreateOpen] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    void loadBookshelf(state, ctrl.signal);
    return () => ctrl.abort();
  }, [state]);

  /** Page reload passed to the create modal as `onCreated`. */
  const refresh = () => {
    const ctrl = new AbortController();
    void loadBookshelf(state, ctrl.signal);
  };

  const renderList = (
    books: BookResponse[],
    status: BookshelfPageState["ownedStatus"],
    error: string | null,
  ) => {
    const loading = status === "idle" || status === "loading";
    if (error) return <Text c="red">{error}</Text>;
    if (loading) {
      return (
        <Group justify="center" py="md">
          <Loader />
        </Group>
      );
    }
    return (
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Title</Table.Th>
            <Table.Th>Visibility</Table.Th>
            <Table.Th>State</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {books.map((book) => (
            <Table.Tr key={book.id}>
              <Table.Td>
                {/* Plain <a>: /work is a separate Vite entry, so this is a full
                    page load across entries, not a react-router link. */}
                <a href={`/work/${book.id}`}>
                  <Text size="sm">{book.title}</Text>
                </a>
              </Table.Td>
              <Table.Td>
                <Badge variant="light" size="sm">
                  {book.visibility}
                </Badge>
              </Table.Td>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  {book.state}
                </Text>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    );
  };

  /**
   * The public discovery feed's own renderer: two columns (title + description),
   * a labelled empty state rather than a headed-but-blank table, and a plain
   * `<a href="/read/<id>">` per row.
   */
  const renderPublicList = (
    books: PublicBookRef[],
    status: BookshelfPageState["publicStatus"],
    error: string | null,
  ) => {
    const loading = status === "idle" || status === "loading";
    if (error) return <Text c="red">{error}</Text>;
    if (loading) {
      return (
        <Group justify="center" py="md">
          <Loader />
        </Group>
      );
    }
    if (books.length === 0) {
      return <Text c="dimmed">No public books to read right now.</Text>;
    }
    return (
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Title</Table.Th>
            <Table.Th>Description</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {books.map((book) => (
            <Table.Tr key={book.id}>
              <Table.Td>
                {/* Plain <a>: /read is a separate Vite entry, so this is a full
                    page load across entries, not a react-router link. */}
                <a href={`/read/${book.id}`}>
                  <Text size="sm">{book.title}</Text>
                </a>
              </Table.Td>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  {book.description}
                </Text>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    );
  };

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>Bookshelf</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setCreateOpen(true)}>
          Create book
        </Button>
      </Group>

      <Stack gap="xl">
        <Stack gap="xs">
          <Title order={5}>My books</Title>
          {renderList(state.ownedBooks, state.ownedStatus, state.ownedError)}
        </Stack>
        <Stack gap="xs">
          <Title order={5}>Shared with me</Title>
          {renderList(state.sharedBooks, state.sharedStatus, state.sharedError)}
        </Stack>
        <Stack gap="xs">
          <Title order={5}>Public books</Title>
          {renderPublicList(
            state.publicBooks,
            state.publicStatus,
            state.publicError,
          )}
        </Stack>
      </Stack>

      <CreateBookModal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={refresh}
      />
    </Container>
  );
});
