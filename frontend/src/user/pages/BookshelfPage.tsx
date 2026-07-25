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
import { BookshelfPageState, loadBookshelf } from "./bookshelfPageState";
import { CreateBookModal } from "../components/books/CreateBookModal";

/**
 * Shell SPA root page (`/`) — the bookshelf. Owns a stable `BookshelfPageState`
 * via `useState`, loads both lists on mount / aborts on unmount via a single
 * page-level `useEffect([state])` spinning an `AbortController`. Renders the owned
 * and shared book lists (two async-resource trios) plus a header Create button and
 * the create-book modal; a successful create re-loads the shelf. Modal open flag is
 * component-local `useState`, not page state.
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
                <Text size="sm">{book.title}</Text>
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
      </Stack>

      <CreateBookModal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={refresh}
      />
    </Container>
  );
});
