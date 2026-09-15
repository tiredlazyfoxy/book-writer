import { observer } from "mobx-react-lite";
import type { CSSProperties, ReactElement } from "react";
import { ActionIcon, Group, Stack } from "@mantine/core";
import { IconArrowDown, IconArrowUp, IconGripVertical } from "@tabler/icons-react";
import { DndContext, closestCenter } from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import type { MemoResponse } from "../../../types/memos";
import type { MemoMoveDirection } from "../../pages/memosListPageState";
import { memoLabel } from "./MemoRow";

/**
 * Props of {@link MemoOrderList}. FROZEN (skeleton 026/011).
 *
 * The component is PRESENTATIONAL and holds **no memo state of its own**: no state
 * class, no `bookId`, no api import, no `useState`, no `useEffect`. The working list,
 * the in-flight flag and both persist entry points are handed down by
 * `MemosListPage`, which owns `MemosListPageState`. That is the difference from the
 * `ChapterOrderList` template (which takes `state` + `bookId`): the memo row's wiring
 * — body, busy, error, autofocus, the five handlers — is built ONCE by the page's
 * `renderRow` and shared with the archived section, so the two lists cannot drift.
 */
export interface MemoOrderListProps {
  /**
   * The WORKING list in display order — `state.displayedWorkingMemos`, i.e. the
   * pending order while a reorder is in flight and the server's ordinal order
   * otherwise. **Never contains an archived memo**, and never the archived section's
   * rows even when the show-archived filter is on: the filter is a *view* concern and
   * does not change what the working list is. Its ids are exactly what
   * {@link MemoOrderListProps.onReorder} is handed.
   */
  memos: MemoResponse[];
  /**
   * `true` while a reorder `PUT` is in flight (`state.reorderStatus === "loading"`).
   * Disables the sortable rows AND every arrow control, so a second reorder cannot
   * interleave into an order nobody chose (DoD-8).
   */
  reordering: boolean;
  /**
   * Renders one memo through step 010's `MemoRow` — supplied by the page so the
   * working list and the archived section share one row wiring. `position` is the
   * row's **1-based index in this list**, the same number this component's arrow
   * names are built from through `memoLabel`.
   */
  renderMemo: (memo: MemoResponse, position: number) => ReactElement;
  /**
   * **THE persist path** (DoD-1). Receives the **complete ordered id list** of the
   * working list — never a partial list, never a single moved id, never an archived
   * id (backend step 004 answers `400` to any of those). The page wires it to
   * `applyMemoOrder(state, bookId, memoIds)`.
   *
   * Called by the drag-end handler with `arrayMove(ids, from, to)` and by nothing
   * else — the arrow controls reach the same `PUT` through
   * {@link MemoOrderListProps.onMove}, whose state-side function delegates here. One
   * persist path, two affordances.
   */
  onReorder: (memoIds: string[]) => void;
  /**
   * The arrow controls' handler — the page wires it to
   * `moveMemo(state, bookId, memoId, direction)`, which computes the fully swapped id
   * list locally and delegates to the SAME persist function `onReorder` reaches. This
   * component never calls an api function and never computes a one-step swap itself.
   */
  onMove: (memoId: string, direction: MemoMoveDirection) => void;
}

/** Props of {@link SortableMemoRow} — module-private, not part of the freeze. */
interface SortableMemoRowProps {
  memo: MemoResponse;
  /** The row's 1-based index in the working list — every accessible name is built from it. */
  position: number;
  /** How many rows the list has, so the last row's ↓ control can be disabled (DoD-3). */
  total: number;
  reordering: boolean;
  renderMemo: (memo: MemoResponse, position: number) => ReactElement;
  onMove: (memoId: string, direction: MemoMoveDirection) => void;
}

/**
 * One draggable row: the drag handle, the two arrow controls and the page's own row
 * markup through `renderMemo`.
 *
 * `useSortable` is `@dnd-kit`'s OWN hook — calling it directly here is not a breach of
 * the no-custom-hooks rule, which forbids AUTHORING hooks. It is deliberately not
 * wrapped in a hook of ours and holds none of our state: the order, the in-flight
 * status and the pending sequence all live on `MemosListPageState`.
 *
 * The arrows call `onMove` and nothing else — no local order computation, no api call
 * and no optimistic write happens in this module.
 */
const SortableMemoRow = observer(function SortableMemoRow({
  memo,
  position,
  total,
  reordering,
  renderMemo,
  onMove,
}: SortableMemoRowProps): ReactElement {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: memo.id,
    // A drag cannot race an in-flight reorder either — the same condition that
    // disables both arrow controls (DoD-8).
    disabled: reordering,
  });

  const style: CSSProperties = {
    transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : undefined,
    transition,
    opacity: isDragging ? 0.6 : undefined,
  };

  // The SAME convention as the row's other controls (`Archive memo 1`), position-
  // derived so it survives an empty body and never reads `memo.ordinal`.
  const label = memoLabel(position).toLowerCase();

  return (
    <div ref={setNodeRef} style={style}>
      <Group gap="xs" wrap="nowrap" align="flex-start">
        <Group gap={4} wrap="nowrap" align="center">
          <ActionIcon
            variant="subtle"
            color="gray"
            aria-label={`Drag ${label} to reorder`}
            {...attributes}
            {...listeners}
          >
            <IconGripVertical size={16} />
          </ActionIcon>
          <ActionIcon
            variant="subtle"
            color="gray"
            aria-label={`Move ${label} up`}
            disabled={reordering || position === 1}
            onClick={() => {
              onMove(memo.id, "up");
            }}
          >
            <IconArrowUp size={16} />
          </ActionIcon>
          <ActionIcon
            variant="subtle"
            color="gray"
            aria-label={`Move ${label} down`}
            disabled={reordering || position === total}
            onClick={() => {
              onMove(memo.id, "down");
            }}
          >
            <IconArrowDown size={16} />
          </ActionIcon>
        </Group>

        {/* The page's ONE row wiring, shared with the archived section. */}
        <div style={{ flex: 1, minWidth: 0 }}>{renderMemo(memo, position)}</div>
      </Group>
    </div>
  );
});

/**
 * The reorderable working list of `/work/:bookId/memos` (FEAT-021 · UC-105 · US-126) —
 * a drag surface plus per-row arrow controls, wrapping the rows step 010 built.
 *
 * `frontend/src/work/components/chapters/ChapterOrderList.tsx` is the template and is
 * COPIED rather than re-derived. What the coder fills in, exactly:
 *
 * - `DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}` wrapping
 *   `SortableContext items={memoIds} strategy={verticalListSortingStrategy}`, where
 *   `memoIds = props.memos.map((memo) => memo.id)` — the working list's ids, in the
 *   order rendered.
 * - A module-private `SortableMemoRow` calling `@dnd-kit`'s **own**
 *   `useSortable({ id: memo.id, disabled: reordering })`. Calling a library's hook is
 *   explicitly NOT a breach of the no-custom-hooks rule, which forbids *authoring*
 *   hooks; it is deliberately not wrapped in a hook of ours and holds none of our
 *   state. It renders the drag handle (`ActionIcon`, `IconGripVertical`, accessible
 *   name `` `Drag ${memoLabel(position).toLowerCase()} to reorder` `` → `Drag memo 1
 *   to reorder`), the two arrow controls and `renderMemo(memo, position)`.
 * - `handleDragEnd(event: DragEndEvent)`: ignore a drop with no `over` or onto itself,
 *   look both ids up in `memoIds`, ignore an unknown one, and otherwise call
 *   `onReorder(arrayMove(memoIds, from, to))` — the full new id sequence, through the
 *   SAME entry point the arrows reach (DoD-1, and the premise DoD-4's `[manual/live]`
 *   drag check rides on: jsdom cannot drive the pointer sensor).
 *
 * **The arrow controls — FROZEN, because the specs bind to these strings.** Two
 * `ActionIcon` buttons per row, built from step 010's `memoLabel(position)` — the SAME
 * convention as the row's other controls, never a second scheme:
 *
 * | Control | Role | Accessible name (position 1) | `disabled` |
 * |---|---|---|---|
 * | up (`IconArrowUp`) | `button` | `` `Move ${memoLabel(position).toLowerCase()} up` `` → `Move memo 1 up` | `reordering \|\| position === 1` |
 * | down (`IconArrowDown`) | `button` | `` `Move ${memoLabel(position).toLowerCase()} down` `` → `Move memo 1 down` | `reordering \|\| position === memos.length` |
 *
 * The verb-first shape matches `Archive memo 1` / `Restore memo 1`; the name carries
 * the memo AND the direction, and it is position-derived, so it survives an empty body
 * (UC-103) and a memo has no title to use instead. `position` is the row's 1-based
 * index in THIS list and never `memo.ordinal`, which carries gaps.
 *
 * On click: `onMove(memo.id, "up" | "down")` and nothing else — no local order
 * computation, no api call, no optimistic write here. The first row's up control and
 * the last row's down control are disabled (DoD-3), and while a reorder is in flight
 * EVERY arrow of EVERY row is disabled (DoD-8).
 *
 * **Hard rules.** `observer` on this component and on the sortable row. No `useState`,
 * no `useEffect`, no custom `useX` hook of ours, no `useCallback` / `useMemo` /
 * `useReducer`, no React context. All reorder state lives on `MemosListPageState` —
 * never in the drag library's own local state. **No archived memo and no archived
 * control ever appears here**: the archived section is not reorderable and is rendered
 * by the page exactly as step 010 left it (DoD-7).
 */
export const MemoOrderList = observer(function MemoOrderList(
  props: MemoOrderListProps,
): ReactElement {
  const { memos, reordering, renderMemo, onReorder, onMove } = props;

  // The working list's ids, in the order rendered — what the drag-end handler moves
  // within and what `onReorder` is handed, whole.
  const memoIds = memos.map((memo) => memo.id);

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const from = memoIds.indexOf(String(active.id));
    const to = memoIds.indexOf(String(over.id));
    if (from === -1 || to === -1) return;
    // The NEW FULL id sequence, through the SAME single persist path the arrow
    // controls reach via `onMove` → `moveMemo` → `applyMemoOrder` (DoD-1, DoD-4).
    onReorder(arrayMove(memoIds, from, to));
  };

  return (
    <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={memoIds} strategy={verticalListSortingStrategy}>
        <Stack gap="sm">
          {memos.map((memo, index) => (
            <SortableMemoRow
              key={memo.id}
              memo={memo}
              position={index + 1}
              total={memos.length}
              reordering={reordering}
              renderMemo={renderMemo}
              onMove={onMove}
            />
          ))}
        </Stack>
      </SortableContext>
    </DndContext>
  );
});
