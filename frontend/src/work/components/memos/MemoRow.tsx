import { observer } from "mobx-react-lite";
import type { ReactElement } from "react";
import { ActionIcon, Alert, Badge, Group, Paper, Stack, Switch, Textarea } from "@mantine/core";
import { IconArchive, IconArchiveOff } from "@tabler/icons-react";
import type { MemoResponse } from "../../../types/memos";

/**
 * The author-facing token every one of this row's accessible names is built from:
 * `Memo 1`, `Memo 2`, … where the number is the row's 1-BASED POSITION in the list it
 * is rendered in (the working list and the archived section each number from 1).
 *
 * A memo has no title — body text only, and `""` is legitimate (UC-103) — so position
 * is the only handle that cannot break. Declarative and complete as written; FROZEN,
 * because the specs bind to these strings.
 */
export function memoLabel(position: number): string {
  return `Memo ${position}`;
}

/**
 * Props of {@link MemoRow}. FROZEN (skeleton 026/010).
 *
 * The row is PRESENTATIONAL: it takes its handlers as props and holds no state class,
 * no `bookId`, no api import, no effect and NO `useEffect`. Everything it reports —
 * the displayed body, the busy flag, the error — is computed by the page from
 * `MemosListPageState` and handed down, so the row has exactly one job: markup plus
 * ordinary event handlers.
 */
export interface MemoRowProps {
  /** The memo as the SERVER last returned it — never the draft. The save comparison's left side. */
  memo: MemoResponse;
  /**
   * 1-based position of this row within the list it is rendered in. Drives every
   * accessible name through {@link memoLabel}; it is NOT the memo's `ordinal`, which
   * carries gaps (archiving never renumbers) and would make the names unstable.
   */
  position: number;
  /** The body to display: `state.displayedBodies[memo.id]` — the draft when one exists, else `memo.body`. */
  body: string;
  /** `true` while one of this row's writes is in flight (`actionStatus[memo.id] === "loading"`). */
  busy: boolean;
  /** This row's own failure message (`actionError[memo.id]`), or `null` when it has none. */
  error: string | null;
  /** `true` when this row's body field should take focus on mount (`state.focusMemoId === memo.id`). */
  autoFocus: boolean;
  /** Draft write — every keystroke; the page replaces `bodyDrafts` with a whole new object. */
  onBodyChange: (body: string) => void;
  /**
   * The focus-loss save (US-125.AC-1). Called from an ordinary `onBlur` handler and
   * ONLY when the displayed body differs from `memo.body` — an unchanged draft writes
   * nothing. There is no Save control anywhere (US-125.AC-2), no debounce and no timer.
   */
  onSaveBody: (body: string) => void;
  /** The on/off switch (US-127) — receives the REQUESTED state, not the current one. */
  onSetActive: (active: boolean) => void;
  /**
   * Archive this memo (US-128.AC-1). Supplied for a working row only; `undefined`
   * renders no archive control at all, never a disabled one (the `dragHandle?`
   * precedent in `ChapterOrderList.tsx`). There is NO delete counterpart, ever.
   */
  onArchive?: () => void;
  /** Restore this memo (US-128.AC-2). Supplied in the ARCHIVED section only; same absent-means-absent rule. */
  onRestore?: () => void;
  /**
   * Reported from the body field's `onFocus`, so the page can clear `state.focusMemoId`
   * once the autofocus has been consumed — an ordinary event handler, not an effect.
   */
  onBodyFocus?: () => void;
}

/**
 * ONE memo row — the list IS the editor (`026/context.md` decision 12), so this is the
 * whole editing surface for a memo: the body field, the on/off switch, the archive (or
 * restore) control, and the row's own busy and error state.
 *
 * **Accessible names are a test contract.** The icon controls have no other handle —
 * specs query by role and accessible name, never by test id — and a memo has no title,
 * so every name is built from {@link memoLabel}`(position)`. FROZEN:
 *
 * | Element | Role | Accessible name |
 * |---|---|---|
 * | body field (`Textarea`) | `textbox` | `` `${memoLabel(position)} body` `` → `Memo 1 body` |
 * | on/off control (`Switch`) | `switch` | `` `${memoLabel(position)} active` `` → `Memo 1 active`, with `checked={memo.active}` so the OFF state is reported as `aria-checked="false"` (US-127.AC-2 — never styling alone) |
 * | off marker (`Badge`, rendered only when `!memo.active`) | — | `` `${memoLabel(position)} is off` `` (`aria-label`), text `Off` |
 * | archive control (`ActionIcon`, working rows) | `button` | `` `Archive ${memoLabel(position).toLowerCase()}` `` → `Archive memo 1` |
 * | restore control (`ActionIcon`, archived section) | `button` | `` `Restore ${memoLabel(position).toLowerCase()}` `` → `Restore memo 1` |
 * | row error (`Alert`, rendered only when `error !== null`) | `alert` | `` `${memoLabel(position)} error` `` (`aria-label`), text `error` |
 *
 * The names are position-derived and therefore stable for an EMPTY body, which is a
 * legitimate state (UC-103) and is never itself reported as an error.
 *
 * The body field saves on BLUR and on blur only. No Save button, no dirty badge, no
 * "unsaved changes" marker — the product forbids a save control (US-125.AC-2). No
 * delete control (US-128.AC-3) and no reorder affordance (step 011's) appear here.
 */
export const MemoRow = observer(function MemoRow(props: MemoRowProps): ReactElement {
  const {
    memo,
    position,
    body,
    busy,
    error,
    autoFocus,
    onBodyChange,
    onSaveBody,
    onSetActive,
    onArchive,
    onRestore,
    onBodyFocus,
  } = props;

  const label = memoLabel(position);

  return (
    <Paper withBorder p="sm">
      <Stack gap="xs">
        <Textarea
          aria-label={`${label} body`}
          placeholder="What should your assistant always keep in mind?"
          value={body}
          autosize
          minRows={2}
          autoFocus={autoFocus}
          onFocus={() => {
            // Ordinary event handler — this is what consumes the page's focus target,
            // so the row needs no effect and no ref.
            onBodyFocus?.();
          }}
          onChange={(event) => {
            onBodyChange(event.currentTarget.value);
          }}
          onBlur={() => {
            // THE one write path (US-125.AC-1). A draft identical to the server's
            // value writes nothing — no pointless save on every focus change.
            if (body !== memo.body) onSaveBody(body);
          }}
        />

        <Group justify="space-between" wrap="nowrap" align="center">
          <Group gap="sm" wrap="nowrap" align="center">
            {/* The state travels on `aria-checked`, and the NAME stays the same
                whether the memo is on or off, so a spec can address one row across a
                toggle (US-127.AC-2). */}
            <Switch
              aria-label={`${label} active`}
              checked={memo.active}
              disabled={busy}
              onChange={(event) => {
                onSetActive(event.currentTarget.checked);
              }}
            />
            {!memo.active && (
              <Badge variant="light" size="sm" color="gray" aria-label={`${label} is off`}>
                Off
              </Badge>
            )}
          </Group>

          <Group gap="xs" wrap="nowrap" align="center">
            {/* Archive and restore are supplied one at a time, and an absent handler
                renders NO control rather than a disabled one. There is no delete
                counterpart at any layer (US-128.AC-3). */}
            {onArchive && (
              <ActionIcon
                variant="subtle"
                aria-label={`Archive ${label.toLowerCase()}`}
                disabled={busy}
                onClick={() => {
                  onArchive();
                }}
              >
                <IconArchive size={16} />
              </ActionIcon>
            )}
            {onRestore && (
              <ActionIcon
                variant="subtle"
                aria-label={`Restore ${label.toLowerCase()}`}
                disabled={busy}
                onClick={() => {
                  onRestore();
                }}
              >
                <IconArchiveOff size={16} />
              </ActionIcon>
            )}
          </Group>
        </Group>

        {/* The failure is reported against the ROW it belongs to, and the field above
            already shows server truth (UC-104 exception handling). */}
        {error !== null && (
          <Alert color="red" variant="light" aria-label={`${label} error`}>
            {error}
          </Alert>
        )}
      </Stack>
    </Paper>
  );
});
