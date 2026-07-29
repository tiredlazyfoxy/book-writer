import { useEffect, useState } from "react";
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
  Table,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import type { ISODateString } from "../../types/common";
import {
  BookStatePageState,
  loadBookState,
  loadSystemPrompt,
  saveSystemPrompt,
} from "./bookStatePageState";

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
 *
 * Feature 021 step 006 adds the caller's **own** system-prompt editor as its own
 * section — the single editable region on this otherwise read-only view. Its load
 * shares the existing mount effect and its `AbortController` (no second
 * `useEffect`), and it renders its own loading / error branches so that the prompt
 * trio and the book-detail trio fail independently.
 */
export const BookStatePage = observer(function BookStatePage() {
  const { bookId } = useParams();
  const [state] = useState(() => new BookStatePageState());

  useEffect(() => {
    const ctrl = new AbortController();
    void loadBookState(state, bookId ?? "", ctrl.signal);
    void loadSystemPrompt(state, bookId ?? "", ctrl.signal);
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

  // Inner handler closing over `state` / `bookId`; it spins its own controller, since
  // the mount effect's controller exists only to abort the page's initial loads.
  const handleSavePrompt = () => {
    const ctrl = new AbortController();
    void saveSystemPrompt(state, bookId ?? "", ctrl.signal);
  };

  const promptLoading =
    state.systemPromptStatus === "idle" || state.systemPromptStatus === "loading";

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

        {/*
          The caller's own system-prompt editor — the ONE editable region on this
          otherwise read-only view. Its own trio branches keep it independent of the
          book-detail trio above. No delete control, no client-side validation, no
          restore buffer, no 409 path.
        */}
        <Stack gap="xs">
          <Title order={5}>Your system prompt</Title>
          <Text size="sm" c="dimmed">
            This prompt is your own: every author of this book keeps their own, and yours is
            not shared with your co-authors — they cannot see it or edit it.
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
              {state.systemPromptServerErrors.form && (
                <Alert color="red">{state.systemPromptServerErrors.form}</Alert>
              )}
              <Textarea
                label="System prompt"
                placeholder="Write the instructions your assistant should follow for this book."
                value={state.systemPromptDraft}
                autosize
                minRows={6}
                error={state.systemPromptServerErrors.system_prompt}
                onChange={(event) => {
                  state.systemPromptDraft = event.currentTarget.value;
                }}
              />
              <Group>
                <Button onClick={handleSavePrompt} disabled={!state.canSaveSystemPrompt}>
                  Save
                </Button>
              </Group>
            </>
          )}
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
