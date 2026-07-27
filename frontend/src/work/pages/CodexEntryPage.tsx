import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Alert,
  Button,
  Container,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from "@mantine/core";
import type { CodexKind } from "../../types/codex";
import { registerContentSubject, unregisterContentSubject } from "../contentSubject";
import {
  CodexEntryPageState,
  discardCodexDraft,
  editCodexDraft,
  loadCodexEntry,
  parseCodexKind,
  resolveCodexConflict,
  saveCodexEntry,
} from "./codexEntryPageState";
import type { CodexEntryPageMode } from "./codexEntryPageState";

/** Author-facing singular headings, one per codex kind. */
const KIND_HEADINGS: Record<CodexKind, string> = {
  character: "Character",
  location: "Location",
  fact: "Fact",
};

/**
 * The entry page is parameterized by MODE only — the two routes
 * (`/codex/:id` and `/codex/new`) share one component because they share one
 * editor, one draft, one buffer and one reconciliation view; only where the entry
 * comes from differs. The book id and the entry id come from `useParams`, and the
 * blank route's kind from the URL's `?kind=`.
 */
export interface CodexEntryPageProps {
  /** `"existing"` for `/codex/:id`; `"blank"` for `/codex/new?kind=…` (UC-076). */
  mode: CodexEntryPageMode;
}

/**
 * One codex entry in the content pane (UC-069 / UC-070, UC-092 / US-107).
 *
 * Owns a `CodexEntryPageState` via `useState`, seeded with the route params and
 * the `?kind=` query param read ONCE here at mount — never by an effect watching
 * the query string (`frontend.md`:192). One page-level `useEffect` loads on mount
 * and aborts on unmount.
 *
 * Every draft change routes through `editCodexDraft`, so the restore-buffer write
 * can never be skipped; nothing reaches the server until Save. A divergence
 * (a stale buffer found at load, or a 409 from Save) replaces the editor with the
 * reconciliation view — the server's current text against the author's draft, with
 * an explicit per-side choice and no merge.
 */
export const CodexEntryPage = observer(function CodexEntryPage({ mode }: CodexEntryPageProps) {
  const { bookId, id } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [state] = useState(
    () =>
      new CodexEntryPageState(
        bookId ?? "",
        mode === "existing" ? (id ?? null) : null,
        parseCodexKind(searchParams.get("kind")),
      ),
  );

  useEffect(() => {
    const ctrl = new AbortController();
    // The content pane's subject for this page, plus its canvas target: a SOURCE
    // function (read at send time, so the loaded row's kind and archived flag are
    // current) which doubles as the identity token the cleanup unregisters with.
    // `state.applyDraft` is registered directly — it runs exactly the keystroke
    // path, so the assistant's write and the author's are indistinguishable.
    const source = () => state.contentSubject;
    registerContentSubject(source, state.applyDraft);
    void loadCodexEntry(state, ctrl.signal);
    return () => {
      unregisterContentSubject(source);
      ctrl.abort();
    };
  }, [state]);

  /** Save, then navigate when the save CREATED a row (the blank route — UC-069). */
  const handleSave = async () => {
    const createdPath = await saveCodexEntry(state);
    if (createdPath !== null) navigate(createdPath);
  };

  if (state.entryStatus === "error") {
    return (
      <Container size="lg" py="md">
        <Alert color="red" title="Could not load">
          <Stack gap="sm" align="flex-start">
            <Text size="sm">{state.entryError}</Text>
            <Button
              size="xs"
              variant="light"
              onClick={() => {
                void loadCodexEntry(state);
              }}
            >
              Retry
            </Button>
          </Stack>
        </Alert>
      </Container>
    );
  }

  if (state.entryStatus === "idle" || state.entryStatus === "loading") {
    return (
      <Container size="lg" py="md">
        <Group justify="center" py="md" gap="xs">
          <Loader size="sm" />
          <Text size="sm" c="dimmed">
            Loading…
          </Text>
        </Group>
      </Container>
    );
  }

  if (state.isReconciling) {
    return (
      <Container size="lg" py="md">
        <Stack gap="md">
          <Title order={3}>Unsaved changes diverged</Title>
          <Alert color="yellow" title="This entry changed since your draft">
            This entry changed on the server while your draft was unsaved. Nothing has been merged
            — choose which version to keep.
          </Alert>
          <Group align="stretch" grow>
            <Paper withBorder p="sm">
              <Stack gap="xs">
                <Title order={5}>Current server version</Title>
                <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                  {state.conflictEntry?.body ?? ""}
                </Text>
                <Button
                  variant="light"
                  onClick={() => {
                    void resolveCodexConflict(state, "server");
                  }}
                >
                  Keep the server version
                </Button>
              </Stack>
            </Paper>
            <Paper withBorder p="sm">
              <Stack gap="xs">
                <Title order={5}>Your draft</Title>
                <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                  {state.bodyDraft}
                </Text>
                <Button
                  onClick={() => {
                    void resolveCodexConflict(state, "draft");
                  }}
                >
                  Keep my draft
                </Button>
              </Stack>
            </Paper>
          </Group>
        </Stack>
      </Container>
    );
  }

  const kindHeading = state.kind === null ? "Codex entry" : KIND_HEADINGS[state.kind];
  const heading =
    state.entry === null ? `New ${kindHeading.toLowerCase()}` : state.entry.name || kindHeading;

  return (
    <Container size="lg" py="md">
      <Stack gap="md">
        <Title order={3}>{heading}</Title>

        {state.isReadOnly && state.editability.readOnlyReason !== null && (
          <Alert color="yellow" title="Read-only">
            {state.editability.readOnlyReason}
          </Alert>
        )}

        {/* The SERVER's refusal, rendered separately from the local field validation. */}
        {state.saveError !== null && (
          <Alert color="red" title="Could not save">
            {state.saveError}
          </Alert>
        )}

        {state.evictedBufferKeys.length > 0 && (
          <Alert color="yellow" title="Other unsaved drafts were removed">
            <Stack gap={2}>
              <Text size="sm">
                Storage was full, so these buffered drafts were removed to keep this one:
              </Text>
              {state.evictedBufferKeys.map((evictedKey) => (
                <Text key={evictedKey} size="sm">
                  {evictedKey}
                </Text>
              ))}
            </Stack>
          </Alert>
        )}

        {/* A fact has no name by design (US-078.AC-2), so no field is offered. */}
        {state.requiresName && (
          <TextInput
            label="Name"
            value={state.nameDraft}
            error={state.nameError}
            readOnly={state.isReadOnly}
            onChange={(event) => editCodexDraft(state, "name", event.currentTarget.value)}
          />
        )}

        <Textarea
          label="Body"
          value={state.bodyDraft}
          autosize
          minRows={12}
          readOnly={state.isReadOnly}
          onChange={(event) => editCodexDraft(state, "body", event.currentTarget.value)}
        />

        <Group gap="xs">
          <Button
            disabled={!state.canSave}
            loading={state.saveStatus === "saving"}
            onClick={() => {
              void handleSave();
            }}
          >
            Save
          </Button>
          <Button
            variant="default"
            disabled={state.isReadOnly}
            onClick={() => discardCodexDraft(state)}
          >
            Discard
          </Button>
          {state.isDirty && (
            <Text size="sm" c="dimmed">
              Unsaved changes
            </Text>
          )}
        </Group>
      </Stack>
    </Container>
  );
});
