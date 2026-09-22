import { useEffect, useState } from "react";
import type { ReactElement } from "react";
import { observer } from "mobx-react-lite";
import { useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Container,
  Group,
  Loader,
  Stack,
  Switch,
  Text,
  Title,
} from "@mantine/core";
import { IconPlus } from "@tabler/icons-react";
import type { MemoResponse } from "../../types/memos";
import { MemoOrderList } from "../components/memos/MemoOrderList";
import { MemoRow } from "../components/memos/MemoRow";
import { registerContentSubject, unregisterContentSubject } from "../contentSubject";
import type { SubjectKind } from "../subject";
import {
  MemosListPageState,
  applyMemoOrder,
  archiveMemo,
  createMemo,
  loadMemos,
  moveMemo,
  restoreMemo,
  saveMemoBody,
  setMemoActive,
} from "./memosListPageState";

/**
 * The content-pane subject kind this page IS — `work/subject.ts`'s `memos` member,
 * added by step 009 (UC-090: a list is a subject too). Module-private, the
 * `CodexListPage` / `ChaptersPage` shape; `subject.ts` is CALLED here, never changed.
 */
const LIST_SUBJECT_KIND: SubjectKind = "memos";

/**
 * The author's own memos for this book, rendered into the CONTENT pane at
 * `/work/:bookId/memos` (FEAT-021 — UC-103..UC-107, US-105.AC-7).
 *
 * Replaces step 009's placeholder. NO PROPS — the book id comes from `useParams()`,
 * like every other subject page. Owns a `MemosListPageState` via
 * `useState(() => new MemosListPageState())` and runs ONE page-level `useEffect`
 * (deps `[state]`) that registers the page's subject, calls
 * `loadMemos(state, bookId, ctrl.signal)` and, on cleanup, unregisters and aborts.
 * A list is a subject with a KIND and no id and with no canvas target, so it
 * registers no apply-draft callback; the `source` closure doubles as the unregister
 * identity token.
 *
 * **This is the content pane's first EDITABLE list** (`026/context.md` decision 12):
 * there is no `/memos/:id` and no `/memos/new` — creation appends into the list in
 * place and the body saves on focus loss. The page renders:
 *
 * - the `Memos` heading (`heading` role, name `Memos` — step 009's route spec binds to it);
 * - a create control, accessible name **`New memo`**, calling `createMemo(state, bookId)`;
 * - a show-archived toggle, accessible name **`Show archived`**, written straight to
 *   `state.showArchived` in the change handler — a pure client-side filter that
 *   refetches NOTHING (UC-107 step 3);
 * - the working list: one `MemoRow` per `state.workingMemos` entry, `position` being
 *   the row's 1-based index in that list, `body` from `state.displayedBodies`, `busy`
 *   from `state.actionStatus`, `error` from `state.actionError`, `autoFocus` from
 *   `state.focusMemoId === memo.id`, and handlers calling `saveMemoBody`,
 *   `setMemoActive` and `archiveMemo`. `onBodyChange` replaces `state.bodyDrafts` with
 *   a whole new object, and `onBodyFocus` clears `state.focusMemoId` — both ordinary
 *   event handlers, assigned directly the way `ChatsListPage` assigns `showArchived`;
 * - the archived section, rendered only while `state.showArchived` is on, from
 *   `state.archivedMemos` (positions numbered from 1 within that section), whose rows
 *   take `onRestore` (calling `restoreMemo`) and NO `onArchive`;
 * - labelled loading / error / empty states, the last driven by `state.isEmpty`.
 *
 * **Absent by decision, not by omission:** no Save control and no dirty/unsaved badge
 * (US-125.AC-2), no delete control (US-128.AC-3), no memo detail link, and no restore
 * buffer write / `baseVersion` / divergence view / `409` path (memos carry no version
 * token).
 *
 * ## Step 011 — the reorder wiring the coder adds (FROZEN, skeleton 026/011)
 *
 * The page's exported signature does NOT change, and neither does anything above. The
 * body gains exactly three things; the stub deliberately leaves them out so step 010's
 * behaviour stays intact while the interface is frozen:
 *
 * 1. **The working list renders through `MemoOrderList`** instead of
 *    `state.workingMemos.map(...)`, inside the same `state.isEmpty` branch:
 *
 *    ```tsx
 *    <MemoOrderList
 *      memos={state.displayedWorkingMemos}
 *      reordering={state.reorderStatus === "loading"}
 *      renderMemo={(memo, position) => renderRow(memo, position - 1, false)}
 *      onReorder={(memoIds) => { void applyMemoOrder(state, book, memoIds); }}
 *      onMove={(memoId, direction) => { void moveMemo(state, book, memoId, direction); }}
 *    />
 *    ```
 *
 *    `renderRow` stays THE one row wiring, shared with the archived section, so the two
 *    lists cannot drift; only its `memo`/`index` source moves.
 * 2. **The reorder error surface** — a LIST-level `Alert` rendered when
 *    `state.reorderError !== null`, named by **`aria-label` `Reorder error`** and
 *    carrying its headline `Could not reorder the memos` plus `state.reorderError`
 *    as its own TEXT. ONE naming mechanism, `MemoRow`'s shape: Mantine's `title`
 *    prop emits an `aria-labelledby` at the headline, which wins the accessible-name
 *    computation, so a `title` alongside the `aria-label` would leave the surface
 *    unreachable under its contracted name. Its own surface: it never shares a
 *    holder with `state.memosError` or a row's `actionError` (DoD-6).
 * 3. Nothing else. **The archived section is NOT reorderable** and is rendered exactly
 *    as it already is — no `MemoOrderList`, no drag handle, no arrows, and its ids
 *    never reach a persist call even while `state.showArchived` is on (DoD-7).
 */
export const MemosListPage = observer(function MemosListPage(): ReactElement {
  const { bookId } = useParams();
  const [state] = useState(() => new MemosListPageState());

  useEffect(() => {
    const ctrl = new AbortController();
    // A list is a subject with a KIND and no id, and with NO canvas target: an
    // assistant draft can never be applied to a list, so it registers no
    // apply-draft callback. The source doubles as the unregister identity token.
    const source = () => ({ kind: LIST_SUBJECT_KIND });
    registerContentSubject(source);
    void loadMemos(state, bookId ?? "", ctrl.signal);
    return () => {
      unregisterContentSubject(source);
      ctrl.abort();
    };
  }, [state]);

  const book = bookId ?? "";

  /** UC-103: one empty, active memo, appended last and focused — no form, no page. */
  const handleCreate = () => {
    void createMemo(state, book);
  };

  /** Error-state retry — re-runs the one load, archived included. */
  const handleRetry = () => {
    void loadMemos(state, book);
  };

  /**
   * One row's wiring, shared by the working list and the archived section so the two
   * cannot drift. `position` is the row's 1-BASED INDEX IN THE LIST IT IS RENDERED
   * IN — each list numbers from 1 — and never `memo.ordinal`, which carries gaps.
   */
  const renderRow = (memo: MemoResponse, index: number, archivedSection: boolean) => (
    <MemoRow
      key={memo.id}
      memo={memo}
      position={index + 1}
      body={state.displayedBodies[memo.id] ?? memo.body}
      busy={state.actionStatus[memo.id] === "loading"}
      error={state.actionError[memo.id] ?? null}
      autoFocus={state.focusMemoId === memo.id}
      onBodyChange={(body) => {
        // A whole new drafts object, written straight from the event handler.
        state.bodyDrafts = { ...state.bodyDrafts, [memo.id]: body };
      }}
      onSaveBody={(body) => {
        void saveMemoBody(state, book, memo.id, body);
      }}
      onSetActive={(active) => {
        void setMemoActive(state, book, memo.id, active);
      }}
      onArchive={
        archivedSection
          ? undefined
          : () => {
              void archiveMemo(state, book, memo.id);
            }
      }
      onRestore={
        archivedSection
          ? () => {
              void restoreMemo(state, book, memo.id);
            }
          : undefined
      }
      onBodyFocus={() => {
        // The autofocus has been consumed; clearing it here is why no effect and no
        // ref-chasing is needed in the row.
        if (state.focusMemoId === memo.id) state.focusMemoId = null;
      }}
    />
  );

  const renderBody = () => {
    if (state.memosStatus === "error") {
      return (
        <Alert color="red" title="Could not load">
          <Stack gap="sm" align="flex-start">
            <Text size="sm">{state.memosError}</Text>
            <Button size="xs" variant="light" onClick={handleRetry}>
              Retry
            </Button>
          </Stack>
        </Alert>
      );
    }

    if (state.memosStatus === "idle" || state.memosStatus === "loading") {
      return (
        <Group justify="center" py="md" gap="xs">
          <Loader size="sm" />
          <Text size="sm" c="dimmed">
            Loading…
          </Text>
        </Group>
      );
    }

    return (
      <Stack gap="sm">
        {/* A failed CREATE is reported here without blanking the list; a failed save
            or toggle reports on its own row instead. */}
        {state.memosError !== null && <Alert color="red">{state.memosError}</Alert>}

        {/* The reorder's OWN surface (DoD-6): a list-level refusal never shares a
            holder with the load trio's error or with a row's `actionError`. */}
        {state.reorderError !== null && (
          // ONE naming mechanism, `MemoRow`'s shape: an `aria-label` and NO `title`.
          // Mantine wires `aria-labelledby` to a `title` headline, and
          // `aria-labelledby` wins the accessible-name computation, which would make
          // this surface unreachable under its contracted name. The headline text is
          // therefore rendered inside the alert instead of through the prop.
          <Alert color="red" variant="light" aria-label="Reorder error">
            <Text size="sm" fw={600}>
              Could not reorder the memos
            </Text>
            <Text size="sm">{state.reorderError}</Text>
          </Alert>
        )}

        {state.isEmpty ? (
          <Text size="sm" c="dimmed" py="sm">
            No memos yet.
          </Text>
        ) : (
          /* The working list is the only reorderable one; `renderRow` stays THE one
             row wiring, shared with the archived section, so the two cannot drift. */
          <MemoOrderList
            memos={state.displayedWorkingMemos}
            reordering={state.reorderStatus === "loading"}
            renderMemo={(memo, position) => renderRow(memo, position - 1, false)}
            onReorder={(memoIds) => {
              void applyMemoOrder(state, book, memoIds);
            }}
            onMove={(memoId, direction) => {
              void moveMemo(state, book, memoId, direction);
            }}
          />
        )}

        {/* Revealed client-side out of what the ONE load already fetched — toggling
            refetches nothing (UC-107 step 3). Positions restart at 1 here. */}
        {state.showArchived && (
          <Stack gap="sm">
            <Title order={4}>Archived</Title>
            {state.archivedMemos.length === 0 ? (
              <Text size="sm" c="dimmed">
                No archived memos.
              </Text>
            ) : (
              state.archivedMemos.map((memo, index) => renderRow(memo, index, true))
            )}
          </Stack>
        )}
      </Stack>
    );
  };

  return (
    <Container size="lg" py="md">
      <Stack gap="md">
        <Group justify="space-between">
          <Title order={3}>Memos</Title>
          <Group gap="md">
            <Switch
              label="Show archived"
              checked={state.showArchived}
              onChange={(event) => {
                // A pure client-side filter: nothing is refetched here, ever.
                state.showArchived = event.currentTarget.checked;
              }}
            />
            <Button leftSection={<IconPlus size={16} />} onClick={handleCreate}>
              New memo
            </Button>
          </Group>
        </Group>

        {renderBody()}
      </Stack>
    </Container>
  );
});
