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
  Paper,
  Stack,
  Table,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import type { ISODateString } from "../../types/common";
import type { ContinuityStatus } from "../../types/continuity";
import {
  BookStatePageState,
  loadBookContinuity,
  loadBookState,
  loadStateNotes,
  loadSystemPrompt,
  saveStateNotes,
  saveSystemPrompt,
} from "./bookStatePageState";

/**
 * Author-facing labels for a continuity artifact's freshness (016). Module-private,
 * like every other label map on this page's tier — no shared map is exported.
 */
const CONTINUITY_STATUS_LABELS: Record<ContinuityStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  stale: "Stale",
};

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
    // 016: two more loads on the SAME controller, filling the page's two stubs. Each
    // has its own trio and fails independently of the other three.
    void loadStateNotes(state, bookId ?? "", ctrl.signal);
    void loadBookContinuity(state, bookId ?? "", ctrl.signal);
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

  /** Save the book's live state notes; the draft is read off the state by the effect. */
  const handleSaveStateNotes = () => {
    if (!state.canSaveStateNotes) return;
    const ctrl = new AbortController();
    void saveStateNotes(state, bookId ?? "", ctrl.signal);
  };

  const stateNotesLoading =
    state.stateNotesStatus === "idle" || state.stateNotesStatus === "loading";
  const continuityLoading =
    state.continuityStatus === "idle" || state.continuityStatus === "loading";

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

        {/* THE BOOK'S LIVE STATE NOTES (016; UC-049 / UC-050's direct-edit path —
            US-052.AC-1, US-053.AC-1). Editable by owner and co-author; a co-author in
            a PROPOSAL-mode book is refused `403` server-side and reads that refusal
            here, because this page has no caller-role signal and manufactures none.
            `""` is a legal save that clears the set, so there is no emptiness check
            and no delete control. */}
        <Stack gap="xs">
          <Title order={5}>State notes</Title>
          <Text size="sm" c="dimmed">
            What is true in the book right now — the live set every chapter is written
            against. A close run proposes the next version of it; you can also edit it
            directly here.
          </Text>

          {stateNotesLoading ? (
            <Group py="xs">
              <Loader size="sm" />
            </Group>
          ) : state.stateNotesStatus === "error" ? (
            <Alert color="red">
              {state.stateNotesError ?? "Could not load the state notes."}
            </Alert>
          ) : (
            <>
              {state.stateNotesServerErrors.form && (
                <Alert color="red">{state.stateNotesServerErrors.form}</Alert>
              )}
              <Textarea
                label="State notes"
                placeholder="What is established in this book so far?"
                value={state.stateNotesDraft}
                autosize
                minRows={6}
                error={state.stateNotesServerErrors.active_notes}
                onChange={(event) => {
                  state.stateNotesDraft = event.currentTarget.value;
                }}
              />
              <Group>
                <Button onClick={handleSaveStateNotes} disabled={!state.canSaveStateNotes}>
                  Save state notes
                </Button>
              </Group>
            </>
          )}
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

        {/* PER-CHAPTER CONTINUITY (016; UC-089 / UC-091 — US-104.AC-1,
            US-106.AC-2 / AC-3). READ-ONLY: one entry per chapter in ordinal order with
            its summary, its note changeset and its OPEN warnings, all produced by the
            close run and none of them edited here. */}
        <Stack gap="xs">
          <Title order={5}>Per-chapter continuity</Title>

          {continuityLoading ? (
            <Group py="xs">
              <Loader size="sm" />
            </Group>
          ) : state.continuityStatus === "error" || state.continuity === null ? (
            <Alert color="red">
              {state.continuityError ?? "Could not load the per-chapter continuity."}
            </Alert>
          ) : state.continuity.items.length === 0 ? (
            <Text size="sm" c="dimmed">
              This book has no chapters yet.
            </Text>
          ) : (
            <Stack gap="sm">
              {state.continuity.items.map((entry) => (
                <Paper key={entry.chapter_id} withBorder p="sm">
                  <Stack gap={4}>
                    <Group gap="sm" align="center">
                      <Text size="sm" c="dimmed">
                        {entry.ordinal}
                      </Text>
                      <Text size="sm" fw={600}>
                        {entry.title}
                      </Text>
                      {entry.summary_status !== null && (
                        <Badge
                          variant="light"
                          size="sm"
                          aria-label={CONTINUITY_STATUS_LABELS[entry.summary_status]}
                        >
                          {CONTINUITY_STATUS_LABELS[entry.summary_status]}
                        </Badge>
                      )}
                    </Group>

                    {entry.summary === null ? (
                      <Text size="sm" c="dimmed">
                        No summary yet.
                      </Text>
                    ) : (
                      <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                        {entry.summary}
                      </Text>
                    )}

                    {entry.changeset !== null && (
                      /* Three separate deltas, never merged (backend D7). */
                      <Stack gap={2}>
                        <Text size="sm" c="dimmed">
                          Added: {entry.changeset.added === "" ? "—" : entry.changeset.added}
                        </Text>
                        <Text size="sm" c="dimmed">
                          Changed:{" "}
                          {entry.changeset.modified === "" ? "—" : entry.changeset.modified}
                        </Text>
                        <Text size="sm" c="dimmed">
                          No longer true:{" "}
                          {entry.changeset.deleted === "" ? "—" : entry.changeset.deleted}
                        </Text>
                      </Stack>
                    )}

                    {/* THE CHAPTER'S ACTIVE WARNINGS, named as warnings.
                        `frontend-workspace.md` fixes the vocabulary as a project
                        rule: **"warning" is the author-facing word for a flag** —
                        the entity, table, DTOs and API stay `flag`, and every
                        string the author reads says *warning*. The heading, the
                        per-item accessible label and the empty state all carry the
                        word, exactly as `ChapterPage`'s own warnings section does,
                        so an author never sees an unexplained coloured sentence
                        under a chapter's summary. Open warnings only — the roll-up
                        carries what still needs attention. */}
                    <Text size="sm" fw={600}>
                      Warnings
                    </Text>
                    {entry.warnings.length === 0 ? (
                      <Text size="sm" c="dimmed">
                        No warnings on this chapter.
                      </Text>
                    ) : (
                      <Stack gap={2}>
                        {entry.warnings.map((warning) => (
                          <Text
                            key={warning.id}
                            size="sm"
                            c="orange"
                            aria-label={`Warning on ${entry.title}: ${warning.comment}`}
                          >
                            {warning.comment}
                          </Text>
                        ))}
                      </Stack>
                    )}
                  </Stack>
                </Paper>
              ))}
            </Stack>
          )}
        </Stack>
      </Stack>
    </Container>
  );
});
