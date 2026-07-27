import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Alert,
  Button,
  Container,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  UnstyledButton,
} from "@mantine/core";
import { IconPlus, IconSearch } from "@tabler/icons-react";
import type { CodexEntryResponse, CodexKind } from "../../types/codex";
import type { ISODateString } from "../../types/common";
import { registerContentSubject, unregisterContentSubject } from "../contentSubject";
import type { SubjectKind } from "../subject";
import { CodexListPageState, loadCodexEntries, submitCodexSearch } from "./codexListPageState";

/**
 * The content-pane subject kind each codex list IS — `work/subject.ts`'s plural
 * members (UC-090: a list is a subject too, so a turn sent from a list carries its
 * kind and no id). Private to the page: nothing outside it needs the mapping.
 */
const LIST_SUBJECT_KINDS: Record<CodexKind, SubjectKind> = {
  character: "characters",
  location: "locations",
  fact: "facts",
};

/**
 * Author-facing plural headings, one per codex kind — the same words the work
 * navigator uses (`components/shell/navItems.ts`). Declarative data; complete.
 */
export const CODEX_KIND_LABELS: Record<CodexKind, string> = {
  character: "Characters",
  location: "Locations",
  fact: "Facts",
};

/** Longest body excerpt shown in the list for an entry with no name (a fact). */
const EXCERPT_LENGTH = 120;

/** Render an ISO timestamp for the author, or an em dash when the field is null. */
function formatTimestamp(value: ISODateString | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

/** Whitespace-collapsed, length-capped opening of an entry's body. */
function bodyExcerpt(body: string): string {
  const collapsed = body.replace(/\s+/g, " ").trim();
  if (collapsed.length <= EXCERPT_LENGTH) return collapsed;
  return `${collapsed.slice(0, EXCERPT_LENGTH)}…`;
}

/**
 * The row's author-facing label: the entry's name, or — for a fact, which has
 * none by design (`domain-codex.md`: `name` is null for a fact) — an excerpt of
 * its body.
 */
function entryLabel(entry: CodexEntryResponse): string {
  return entry.name || bodyExcerpt(entry.body) || "Untitled";
}

/**
 * The list page is parameterized by kind ONLY — the three routes
 * (`/characters` · `/locations` · `/facts`) share one component rather than
 * triplicating a table, and the kind is fixed by the route, never user-selectable
 * (US-080.AC-1). The heading is derived from {@link CODEX_KIND_LABELS}, the book
 * id from `useParams`, and the initial needle from the URL's `q`.
 */
export interface CodexListPageProps {
  kind: CodexKind;
}

/**
 * The codex list view for one kind (UC-071 / US-080.AC-1 / US-105.AC-1).
 *
 * Owns a `CodexListPageState` via `useState`, seeded with the URL's `q` read ONCE
 * here at mount so a deep-linked filtered list is filtered on its first fetch.
 * One page-level `useEffect` loads on mount and aborts on unmount. The search
 * submit handler commits the draft needle and pushes the returned query string
 * itself — the URL is written in the event handler that changed it, never by an
 * effect watching the query string (`frontend.md`:192).
 */
export const CodexListPage = observer(function CodexListPage({ kind }: CodexListPageProps) {
  const { bookId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [state] = useState(() => new CodexListPageState(kind, searchParams.get("q") ?? ""));

  useEffect(() => {
    const ctrl = new AbortController();
    // A list is a subject with a KIND and no id, and with NO canvas target: an
    // assistant draft can never be applied to a list, so it registers no
    // apply-draft callback. The source doubles as the unregister identity token.
    const source = () => ({ kind: LIST_SUBJECT_KINDS[kind] });
    registerContentSubject(source);
    void loadCodexEntries(state, bookId ?? "", ctrl.signal);
    return () => {
      unregisterContentSubject(source);
      ctrl.abort();
    };
  }, [state]);

  const label = CODEX_KIND_LABELS[kind];

  /** Commit the draft needle, reload, and write `q` into the URL — here, not in an effect. */
  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = submitCodexSearch(state, bookId ?? "");
    setSearchParams(query);
  };

  /** Error-state retry — re-runs the loader with the committed needle. */
  const handleRetry = () => {
    void loadCodexEntries(state, bookId ?? "");
  };

  /** UC-076's blank entry: the kind rides in a query param, the route stays deep-linkable. */
  const handleNewEntry = () => {
    navigate(`/${bookId}/codex/new?kind=${kind}`);
  };

  /** Row activation — one codex entry (US-105.AC-2 / UC-083). */
  const openEntry = (entryId: string) => {
    navigate(`/${bookId}/codex/${entryId}`);
  };

  const renderBody = () => {
    if (state.entriesStatus === "error") {
      return (
        <Alert color="red" title="Could not load">
          <Stack gap="sm" align="flex-start">
            <Text size="sm">{state.entriesError}</Text>
            <Button size="xs" variant="light" onClick={handleRetry}>
              Retry
            </Button>
          </Stack>
        </Alert>
      );
    }

    if (state.entriesStatus === "idle" || state.entriesStatus === "loading") {
      return (
        <Group justify="center" py="md" gap="xs">
          <Loader size="sm" />
          <Text size="sm" c="dimmed">
            Loading…
          </Text>
        </Group>
      );
    }

    if (state.isEmpty) {
      return (
        <Text size="sm" c="dimmed" py="sm">
          No {label.toLowerCase()} found.
        </Text>
      );
    }

    return (
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{kind === "fact" ? "Fact" : "Name"}</Table.Th>
            <Table.Th>Modified</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {state.entries.map((entry) => (
            <Table.Tr
              key={entry.id}
              style={{ cursor: "pointer" }}
              onClick={() => openEntry(entry.id)}
            >
              <Table.Td>
                <UnstyledButton
                  onClick={(event) => {
                    // The row itself is clickable too; stop here so one activation
                    // is one navigation.
                    event.stopPropagation();
                    openEntry(entry.id);
                  }}
                >
                  <Text size="sm">{entryLabel(entry)}</Text>
                </UnstyledButton>
              </Table.Td>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  {formatTimestamp(entry.modified_at)}
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
      <Stack gap="md">
        <Group justify="space-between">
          <Title order={3}>{label}</Title>
          <Button leftSection={<IconPlus size={16} />} onClick={handleNewEntry}>
            New entry
          </Button>
        </Group>

        <form onSubmit={handleSearchSubmit}>
          <Group gap="xs" align="flex-end">
            <TextInput
              label="Search"
              placeholder={`Search ${label.toLowerCase()}`}
              value={state.draftNeedle}
              onChange={(event) => {
                state.draftNeedle = event.currentTarget.value;
              }}
              style={{ flex: 1 }}
            />
            <Button type="submit" leftSection={<IconSearch size={16} />} variant="light">
              Search
            </Button>
          </Group>
        </form>

        {renderBody()}
      </Stack>
    </Container>
  );
});
