import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { useParams } from "react-router-dom";
import {
  Alert,
  Container,
  Divider,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import type { ISODateString } from "../../types/common";
import { BookStatePageState, loadBookState } from "./bookStatePageState";

/** Render an ISO timestamp for the author, or an em dash when the field is null. */
function formatTimestamp(value: ISODateString | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

/**
 * The Book-state landing view for `/work/:bookId/state` (UC-091 / US-106.AC-1).
 * Reads `:bookId` from the router, owns a `BookStatePageState` via `useState`, runs
 * a single mount-only `useEffect` that loads the detail and aborts on unmount, and
 * renders the book's own fields, its members, the state-notes empty state (the
 * `BookResponse` wire gap), and the deferred per-chapter continuity empty state. The
 * loading and error states of the async trio replace the content rather than a blank
 * pane. No props.
 */
export const BookStatePage = observer(function BookStatePage() {
  const { bookId } = useParams();
  const [state] = useState(() => new BookStatePageState());

  useEffect(() => {
    const ctrl = new AbortController();
    void loadBookState(state, bookId ?? "", ctrl.signal);
    return () => ctrl.abort();
  }, [state]);

  const loading = state.bookDetailStatus === "idle" || state.bookDetailStatus === "loading";
  const detail = state.bookDetail;

  if (state.bookDetailStatus === "error") {
    return (
      <Container size="lg" py="md">
        <Alert color="red">{state.bookDetailError}</Alert>
      </Container>
    );
  }

  if (loading || !detail) {
    return (
      <Container size="lg" py="md">
        <Group justify="center" py="md">
          <Loader />
        </Group>
      </Container>
    );
  }

  return (
    <Container size="lg" py="md">
      <Stack gap="xl">
        <Stack gap={4}>
          <Title order={3}>{detail.title}</Title>
          <Text size="sm" c="dimmed">
            {detail.description}
          </Text>
        </Stack>

        <Stack gap="xs">
          <Title order={5}>Book state</Title>
          <Table withRowBorders={false}>
            <Table.Tbody>
              <Table.Tr>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    Collaboration mode
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{state.collaborationModeLabel}</Text>
                </Table.Td>
              </Table.Tr>
              <Table.Tr>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    Visibility
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{state.visibilityLabel}</Text>
                </Table.Td>
              </Table.Tr>
              <Table.Tr>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    Lifecycle state
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{state.lifecycleStateLabel}</Text>
                </Table.Td>
              </Table.Tr>
              <Table.Tr>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    Created
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{formatTimestamp(detail.created_at)}</Text>
                </Table.Td>
              </Table.Tr>
              <Table.Tr>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    Modified
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{formatTimestamp(detail.modified_at)}</Text>
                </Table.Td>
              </Table.Tr>
            </Table.Tbody>
          </Table>
        </Stack>

        <Divider />

        <Stack gap="xs">
          <Title order={5}>Members ({state.memberCount})</Title>
          <Text size="sm">Owner: {detail.owner_id}</Text>
          {state.memberList.length === 0 ? (
            <Text size="sm" c="dimmed">
              No co-authors yet.
            </Text>
          ) : (
            <Table striped>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Co-author</Table.Th>
                  <Table.Th>Role</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {state.memberList.map((member) => (
                  <Table.Tr key={member.user_id}>
                    <Table.Td>
                      <Text size="sm">{member.user_id}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed">
                        {member.role}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Stack>

        <Divider />

        <Stack gap="xs">
          <Title order={5}>State notes</Title>
          <Text size="sm" c="dimmed">
            The book's state notes are not yet exposed by the API and cannot be shown here yet.
          </Text>
        </Stack>

        <Divider />

        <Stack gap="xs">
          <Title order={5}>Per-chapter continuity</Title>
          <Text size="sm" c="dimmed">
            Per-chapter continuity — each chapter's title, summary, after-chapter notes and any
            active warnings — is delivered by 016.chapter-close-continuity and is not available yet.
          </Text>
        </Stack>
      </Stack>
    </Container>
  );
});
