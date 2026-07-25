import { useEffect, useState } from "react";
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
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import {
  BookSettingsPageState,
  archiveAction,
  loadBookSettings,
  removeMemberAction,
  setVisibilityAction,
  unarchiveAction,
} from "./bookSettingsPageState";
import {
  AddCoAuthorDraft,
  submitAddCoAuthor,
} from "../components/books/addCoAuthorDraft";
import {
  TransferOwnershipDraft,
  submitTransferOwnership,
} from "../components/books/transferOwnershipDraft";

/**
 * Shell SPA book-settings page (`/books/:bookId/settings`) — the repo's first
 * URL-param route. Owns a stable `BookSettingsPageState` via `useState`, reads the
 * `bookId` route param via `useParams`, and loads the detail on mount / aborts on
 * unmount via a single page-level `useEffect([state])` spinning an `AbortController`.
 * The route element applies the `key={bookId}` remount rule (see `routes.tsx`) so a
 * different book id gets a fresh state instance.
 *
 * Renders the current visibility with a toggle, an archive/unarchive control keyed
 * on the current `state`, the members list with remove controls, an add-co-author
 * form, and a transfer-ownership form (offering only current co-authors as targets;
 * a server refusal surfaces as a field error). Each action spins a fresh
 * `AbortController` and re-loads the detail on success (backend is the source of
 * truth — no optimistic local edits).
 */
export const BookSettingsPage = observer(function BookSettingsPage() {
  const { bookId } = useParams();
  const [state] = useState(() => new BookSettingsPageState());
  const [addDraft] = useState(() => new AddCoAuthorDraft());
  const [transferDraft] = useState(() => new TransferOwnershipDraft());

  useEffect(() => {
    const ctrl = new AbortController();
    void loadBookSettings(state, bookId ?? "", ctrl.signal);
    return () => ctrl.abort();
  }, [state]);

  const id = bookId ?? "";

  /** Re-load the detail from the server (passed to the forms as `onDone`). */
  const refresh = () => {
    const ctrl = new AbortController();
    void loadBookSettings(state, id, ctrl.signal);
  };

  const handleToggleArchive = (archived: boolean) => {
    const ctrl = new AbortController();
    if (archived) void unarchiveAction(state, id, ctrl.signal);
    else void archiveAction(state, id, ctrl.signal);
  };

  const handleToggleVisibility = (isPublic: boolean) => {
    const ctrl = new AbortController();
    void setVisibilityAction(
      state,
      id,
      { visibility: isPublic ? "private" : "public" },
      ctrl.signal,
    );
  };

  const handleRemoveMember = (userId: string) => {
    const ctrl = new AbortController();
    void removeMemberAction(state, id, userId, ctrl.signal);
  };

  const handleAddCoAuthor = async () => {
    const ctrl = new AbortController();
    await submitAddCoAuthor(addDraft, id, refresh, ctrl.signal);
    if (addDraft.submitStatus === "ready") addDraft.targetUserId = "";
  };

  const handleTransfer = async () => {
    const ctrl = new AbortController();
    await submitTransferOwnership(transferDraft, id, refresh, ctrl.signal);
    if (transferDraft.submitStatus === "ready") transferDraft.targetUserId = "";
  };

  const loading = state.detailStatus === "idle" || state.detailStatus === "loading";
  const detail = state.detail;

  return (
    <Container size="lg" py="md">
      <Title order={3} mb="md">
        Book settings
      </Title>

      {state.detailError && (
        <Alert color="red" mb="md">
          {state.detailError}
        </Alert>
      )}

      {loading ? (
        <Group justify="center" py="md">
          <Loader />
        </Group>
      ) : detail ? (
        <Stack gap="xl">
          <Stack gap={4}>
            <Title order={4}>{detail.title}</Title>
            <Text size="sm" c="dimmed">
              {detail.description}
            </Text>
          </Stack>

          <Stack gap="xs">
            <Title order={5}>Visibility</Title>
            <Group>
              <Badge variant="light">{detail.visibility}</Badge>
              <Button
                variant="default"
                onClick={() => handleToggleVisibility(detail.visibility === "public")}
              >
                {detail.visibility === "public" ? "Make private" : "Make public"}
              </Button>
            </Group>
          </Stack>

          <Stack gap="xs">
            <Title order={5}>State</Title>
            <Group>
              <Badge variant="light">{detail.state}</Badge>
              <Button
                variant="default"
                onClick={() => handleToggleArchive(detail.state === "archived")}
              >
                {detail.state === "archived" ? "Unarchive" : "Archive"}
              </Button>
            </Group>
          </Stack>

          <Divider />

          <Stack gap="xs">
            <Title order={5}>Co-authors</Title>
            {detail.members.length === 0 ? (
              <Text size="sm" c="dimmed">
                No co-authors yet.
              </Text>
            ) : (
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>User id</Table.Th>
                    <Table.Th>Role</Table.Th>
                    <Table.Th />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {detail.members.map((member) => (
                    <Table.Tr key={member.user_id}>
                      <Table.Td>
                        <Text size="sm">{member.user_id}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" c="dimmed">
                          {member.role}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Button
                          size="xs"
                          variant="light"
                          color="red"
                          onClick={() => handleRemoveMember(member.user_id)}
                        >
                          Remove
                        </Button>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            )}
          </Stack>

          <Stack gap="xs">
            <Title order={5}>Add co-author</Title>
            {addDraft.errors.form && <Alert color="red">{addDraft.errors.form}</Alert>}
            <Group align="flex-end">
              <TextInput
                label="Account id"
                value={addDraft.targetUserId}
                onChange={(e) => {
                  addDraft.targetUserId = e.currentTarget.value;
                }}
                error={addDraft.errors.target_user_id}
              />
              <Button onClick={handleAddCoAuthor} disabled={!addDraft.canSubmit}>
                Add
              </Button>
            </Group>
          </Stack>

          <Stack gap="xs">
            <Title order={5}>Transfer ownership</Title>
            {transferDraft.errors.form && <Alert color="red">{transferDraft.errors.form}</Alert>}
            <Group align="flex-end">
              <Select
                label="New owner"
                placeholder="Select a co-author"
                data={detail.members.map((member) => ({
                  value: member.user_id,
                  label: member.user_id,
                }))}
                value={transferDraft.targetUserId || null}
                onChange={(v) => {
                  transferDraft.targetUserId = v ?? "";
                }}
                error={transferDraft.errors.target_user_id}
              />
              <Button onClick={handleTransfer} disabled={!transferDraft.canSubmit}>
                Transfer
              </Button>
            </Group>
          </Stack>
        </Stack>
      ) : null}
    </Container>
  );
});
