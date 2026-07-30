import { observer } from "mobx-react-lite";
import type { CSSProperties, ReactElement, ReactNode } from "react";
import { Link } from "react-router-dom";
import { ActionIcon, Anchor, Badge, Button, Group, Paper, Stack, Text } from "@mantine/core";
import { IconGripVertical } from "@tabler/icons-react";
import { DndContext, closestCenter } from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import type { ChapterLifecycleState, ChapterResponse } from "../../../types/chapters";
import type { ChaptersPageState } from "../../pages/chaptersPageState";
import { applyChapterOrder, moveChapter, removeChapter } from "../../pages/chaptersPageState";

/**
 * The author-facing word for each lifecycle state. Module-private: no exported label
 * map is frozen anywhere in feature 014, and this is now the only site that renders a
 * chapter's state, so there is nothing to share it with.
 */
const CHAPTER_STATE_LABELS: Record<ChapterLifecycleState, string> = {
  planned: "Planned",
  open: "Open",
  closing: "Closing",
  closed: "Closed",
};

/**
 * Props of {@link ChapterOrderList}. FROZEN (skeleton 014/007).
 *
 * `bookId` is a prop and not a `useParams()` read: `useEffect` and route reads are
 * page-level only, and the row's chapter link plus all three effect calls need it. This
 * is the `ChatPane.tsx` shape — a non-page component that takes `bookId` and calls the
 * external `(state, bookId, …)` effects directly.
 */
export interface ChapterOrderListProps {
  /** The page's state instance, owned by `ChaptersPage`'s `useState`. */
  state: ChaptersPageState;
  /** The book whose chapters these are — the first argument of every effect call. */
  bookId: string;
}

/** Props of the one row markup, shared by the sortable and the plain branch. */
interface ChapterRowProps {
  state: ChaptersPageState;
  bookId: string;
  chapter: ChapterResponse;
  /**
   * The drag handle, supplied ONLY by {@link SortableChapterRow} — i.e. only when the
   * caller may reorder. `undefined` renders no handle at all, never a disabled one.
   */
  dragHandle?: ReactNode;
}

/**
 * ONE chapter row — the single piece of row markup on this page, so the move buttons,
 * the drag affordance and the row content cannot diverge. Everything step 006 rendered
 * lives here now (DoD-9): the ordinal, the title link, the lifecycle badge, the remove
 * control and that chapter's own removal refusal.
 */
const ChapterRow = observer(function ChapterRow({
  state,
  bookId,
  chapter,
  dragHandle,
}: ChapterRowProps): ReactElement {
  // Keyed by CHAPTER ID, so a refusal renders inside the row it concerns rather than as
  // a page-level banner (step-006 DoD-9).
  const removeError = state.removeServerErrors[chapter.id];
  const stateLabel = CHAPTER_STATE_LABELS[chapter.state];

  return (
    <Paper withBorder p="sm">
      <Stack gap="xs">
        <Group justify="space-between" wrap="nowrap" align="center">
          <Group gap="sm" wrap="nowrap" align="center">
            {dragHandle}
            <Text size="sm" c="dimmed">
              {chapter.ordinal}
            </Text>
            {/* `/work` IS this Vite entry, so the chapter is an in-SPA navigation. */}
            <Anchor component={Link} to={`/${bookId}/chapter/${chapter.id}`}>
              <Text size="sm">{chapter.title}</Text>
            </Anchor>
            {/* The readable word in BOTH the text and the accessible name — a colour is
                not a badge. */}
            <Badge variant="light" size="sm" aria-label={stateLabel}>
              {stateLabel}
            </Badge>
          </Group>

          <Group gap="xs" wrap="nowrap" align="center">
            {/* Move controls exist ONLY for a caller who may reorder — absent, never
                disabled, when they may not (DoD-4). `canMoveUp` / `canMoveDown` already
                fold in the ends of the list (DoD-3) and the in-flight reorder (DoD-7). */}
            {state.canReorder && (
              <>
                <Button
                  size="xs"
                  variant="default"
                  aria-label={`Move "${chapter.title}" up`}
                  disabled={!state.canMoveUp(chapter)}
                  onClick={() => {
                    void moveChapter(state, bookId, chapter.id, "up");
                  }}
                >
                  ↑
                </Button>
                <Button
                  size="xs"
                  variant="default"
                  aria-label={`Move "${chapter.title}" down`}
                  disabled={!state.canMoveDown(chapter)}
                  onClick={() => {
                    void moveChapter(state, bookId, chapter.id, "down");
                  }}
                >
                  ↓
                </Button>
              </>
            )}

            {state.canRemoveChapter(chapter) && (
              <Button
                size="xs"
                color="red"
                variant="light"
                aria-label={`Remove "${chapter.title}"`}
                disabled={state.removingChapterId === chapter.id}
                onClick={() => {
                  void removeChapter(state, bookId, chapter.id);
                }}
              >
                Remove
              </Button>
            )}
          </Group>
        </Group>

        {removeError && (
          <Text size="sm" c="red">
            {removeError}
          </Text>
        )}
      </Stack>
    </Paper>
  );
});

/**
 * {@link ChapterRow} plus the drag affordance — rendered only inside the
 * `DndContext` / `SortableContext` branch, i.e. only when the caller may reorder.
 *
 * `useSortable` is `@dnd-kit`'s OWN hook: calling it directly here is not a breach of
 * the no-custom-hooks rule, which forbids AUTHORING hooks. It is deliberately not
 * wrapped in a hook of ours, and it holds none of our state — the order, the in-flight
 * status and the pending sequence all live on `ChaptersPageState`.
 */
const SortableChapterRow = observer(function SortableChapterRow({
  state,
  bookId,
  chapter,
}: ChapterRowProps): ReactElement {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: chapter.id,
    // A drag cannot race an in-flight reorder either — the same condition the ↑ / ↓
    // controls read through `canMoveUp` / `canMoveDown`.
    disabled: state.reorderStatus === "loading",
  });

  const style: CSSProperties = {
    transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : undefined,
    transition,
    opacity: isDragging ? 0.6 : undefined,
  };

  return (
    <div ref={setNodeRef} style={style}>
      <ChapterRow
        state={state}
        bookId={bookId}
        chapter={chapter}
        dragHandle={
          <ActionIcon
            variant="subtle"
            color="gray"
            aria-label={`Drag "${chapter.title}" to reorder`}
            {...attributes}
            {...listeners}
          >
            <IconGripVertical size={16} />
          </ActionIcon>
        }
      />
    </div>
  );
});

/**
 * The chapters in the order to render: the pending sequence resolved against the loaded
 * chapters while a reorder is in flight, otherwise ordinal order as the server has it.
 *
 * A plain function, not a computed — the freeze names exactly two new computeds, and
 * this is the `const` derivation `ChaptersPage` already does for its own render values.
 * A chapter the pending sequence does not name (it arrived from a concurrent load)
 * keeps its ordinal place at the end rather than vanishing.
 */
function resolveRenderedOrder(
  chapters: ChapterResponse[],
  pendingOrder: string[] | null,
): ChapterResponse[] {
  if (pendingOrder === null) return chapters;

  const remaining = new Map(chapters.map((chapter) => [chapter.id, chapter]));
  const rendered: ChapterResponse[] = [];
  for (const id of pendingOrder) {
    const chapter = remaining.get(id);
    if (chapter !== undefined) {
      rendered.push(chapter);
      remaining.delete(id);
    }
  }
  for (const chapter of chapters) {
    if (remaining.has(chapter.id)) rendered.push(chapter);
  }
  return rendered;
}

/**
 * The ordered chapter rows of `/work/:bookId/chapters` — **the SINGLE rendering site for
 * a chapter row on this page** (FEAT-008 · UC-032 · US-033), so the move buttons, the
 * drag affordance and the row content cannot diverge.
 *
 * **The rows it renders are step 006's, MOVED here — not duplicated, not re-designed.**
 * `ChaptersPage` no longer renders a row; it renders this component. Everything step 006
 * shipped is still there (DoD-9), namely, per chapter:
 * - the ordinal (`chapter.ordinal`, dimmed `Text`);
 * - the title as a react-router `Anchor component={Link} to={`/${bookId}/chapter/${chapter.id}`}`
 *   (`/work` is this Vite entry, so it is an in-SPA link);
 * - a lifecycle `Badge` whose TEXT and `aria-label` carry the readable word, so it is
 *   reachable by accessible name and never by colour alone;
 * - a remove `Button` rendered ONLY when `state.canRemoveChapter(chapter)`, accessible
 *   name `Remove "<title>"`, `disabled` while `state.removingChapterId === chapter.id`,
 *   calling `removeChapter(state, bookId, chapter.id)`;
 * - `state.removeServerErrors[chapter.id]` rendered INSIDE that chapter's row, never as
 *   a page-level banner.
 *
 * **The order it renders.** `state.pendingOrder` when it is non-`null` — the sequence
 * being arranged, resolved against `state.orderedChapters` — otherwise
 * `state.orderedChapters` itself. That is a RENDERING optimism only: nothing in the list
 * trio is mutated until the server answers, and the pending sequence is discarded on
 * both success and failure, so a refused `PUT` snaps the rendered order back to the
 * order the server still holds (DoD-5, US-033.AC-2).
 *
 * **The move controls** — per row, ONLY when `state.canReorder`: an ↑ control named
 * `Move "<title>" up` and a ↓ control named `Move "<title>" down` (the accessible name
 * carries the chapter AND the direction), disabled through `state.canMoveUp` /
 * `state.canMoveDown`, each calling `moveChapter(state, bookId, chapter.id, …)` and
 * nothing else.
 *
 * **The drag affordance** — also ONLY when `state.canReorder`: `DndContext` wrapping a
 * `SortableContext` over the rendered chapter ids, with a per-row sortable handle. Its
 * drag-end handler produces the NEW FULL ordered id sequence and calls
 * `applyChapterOrder(state, bookId, nextIds)` — **the same effect the buttons reach
 * through `moveChapter`**, which is the invariant DoD-6 protects and the reason the
 * pointer gesture itself can stay a `[manual/live]` item (DoD-10).
 *
 * **When `state.canReorder` is false**, neither move control NOR any drag affordance is
 * rendered — no `DndContext`, no drag handle, no disabled arrows — and the rows render
 * as a plain ordered list with everything above still intact (DoD-4). This MIRRORS the
 * server's answer and never replaces it: the hint can go stale, so the `403` path works
 * even when the controls rendered (DoD-5).
 *
 * **Hard rules.** `observer` (applied here and on both row components). ALL state lives
 * on `ChaptersPageState` — never in the drag library's own local state. No `useState`,
 * no `useEffect`, no custom `useX` hook of ours, no `useCallback` / `useMemo` /
 * `useReducer`, no React context, no Mantine `useForm`. No optimistic mutation: after a
 * reorder the surface shows what the server returned.
 */
export const ChapterOrderList = observer(function ChapterOrderList({
  state,
  bookId,
}: ChapterOrderListProps): ReactElement {
  const rendered = resolveRenderedOrder(state.orderedChapters, state.pendingOrder);

  // The caller may not reorder: a plain ordered list, with every row's content intact
  // and no reorder affordance of either kind (DoD-4).
  if (!state.canReorder) {
    return (
      <Stack gap="sm">
        {rendered.map((chapter) => (
          <ChapterRow key={chapter.id} state={state} bookId={bookId} chapter={chapter} />
        ))}
      </Stack>
    );
  }

  const renderedIds = rendered.map((chapter) => chapter.id);

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const from = renderedIds.indexOf(String(active.id));
    const to = renderedIds.indexOf(String(over.id));
    if (from === -1 || to === -1) return;
    // The NEW FULL id sequence, through the same single persist path the ↑ / ↓ controls
    // reach via `moveChapter` (DoD-6, DoD-10).
    void applyChapterOrder(state, bookId, arrayMove(renderedIds, from, to));
  };

  return (
    <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={renderedIds} strategy={verticalListSortingStrategy}>
        <Stack gap="sm">
          {rendered.map((chapter) => (
            <SortableChapterRow
              key={chapter.id}
              state={state}
              bookId={bookId}
              chapter={chapter}
            />
          ))}
        </Stack>
      </SortableContext>
    </DndContext>
  );
});
