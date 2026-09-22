import { observer } from "mobx-react-lite";
import { Box, Code, Group, Loader, Stack, Text, UnstyledButton } from "@mantine/core";
import {
  IconAlertTriangle,
  IconBook,
  IconChevronDown,
  IconChevronRight,
  IconFileText,
  IconPencil,
  IconTool,
  IconWorldSearch,
} from "@tabler/icons-react";
import type { ToolTraceRow } from "./chatPaneState";

/**
 * The assistant's tool-call trace for one message (024) — one row per call, in
 * call order, live during the turn and preserved after it ends.
 *
 * Fully controlled and STATELESS, exactly like
 * {@link import("./ThinkingBlock").ThinkingBlock}: the parent supplies the rows,
 * the expansion map and the toggle, and this component holds no state of its own.
 * Expansion is keyed `` `${rowKeyPrefix}:${index}` `` and owned by
 * `ChatPaneState.expandedToolCallRows` / `toggleToolCallRow`.
 *
 * PER-TOOL-NAME RENDERING (D6) — the point of the component is that the five
 * things the author was promised to see are visibly different:
 * - `web_search` — its query argument;
 * - `codex_search` — its query plus a hit count derived from the result text;
 * - `codex_read_entry` — the entry it pulled;
 * - `write_codex_draft` — which field (`name` / `body`) it wrote;
 * - ANY OTHER `tool_name` — a generic name-plus-arguments row. An unrecognized
 *   name must degrade to this, never break the trace.
 *
 * A row with `result === null` is still IN FLIGHT and shows a pending affordance.
 * Each row is collapsible for its full arguments and result.
 *
 * Renders `null` when there is nothing to show, so the caller can place it
 * unconditionally beside `ThinkingBlock`.
 */
export interface ToolCallTraceProps {
  /** The calls to render, in call order. */
  rows: ToolTraceRow[];
  /** Per-row expansion, keyed `` `${rowKeyPrefix}:${index}` ``. */
  expanded: Record<string, boolean>;
  /** The owning message's key — the first half of every row key. */
  rowKeyPrefix: string;
  /** Toggle one row's expansion (parent-owned; this component holds none). */
  onToggle: (rowKey: string) => void;
}

/** Icon size used for every row's leading glyph, matching `ThinkingBlock`'s chevron. */
const ICON_SIZE = 14;

/** How many characters of a tool result the collapsed summary may borrow. */
const SUMMARY_CHARS = 80;

/**
 * Read one argument as a string, or `null` when it is absent or not a string.
 *
 * Arguments come off the wire as `Record<string, unknown>` — the model produced
 * them, so a tool may perfectly well be called with a missing or wrongly-typed
 * argument. Every per-tool summary below therefore has to survive that, which is
 * the same reason an unknown `tool_name` falls back rather than throwing.
 */
function stringArg(args: Record<string, unknown>, key: string): string | null {
  const value = args[key];
  return typeof value === "string" ? value : null;
}

/** Trim a borrowed fragment to one line of at most {@link SUMMARY_CHARS}. */
function short(text: string): string {
  const oneLine = text.replace(/\s+/g, " ").trim();
  return oneLine.length > SUMMARY_CHARS ? `${oneLine.slice(0, SUMMARY_CHARS)}…` : oneLine;
}

/**
 * How many codex entries a `codex_search` result names.
 *
 * The tool renders each hit with an `entry_id=…` header line, so counting those
 * markers is what "how many entries matched" means on this wire — there is no
 * count field, and inventing one would mean parsing the whole block. `null` while
 * the call is still in flight; `null` too when the result carries no marker at
 * all (a "nothing found" or error string), where a bare "0 entries" would read as
 * a searched-and-found-nothing that may not be what happened.
 */
function codexHitCount(result: string | null): number | null {
  if (result === null) return null;
  const matches = result.match(/entry_id=/g);
  return matches === null ? null : matches.length;
}

/** The leading glyph for a row, by tool name — the generic wrench for anything unknown. */
function rowIcon(toolName: string) {
  switch (toolName) {
    case "web_search":
      return <IconWorldSearch size={ICON_SIZE} stroke={1.5} />;
    case "codex_search":
      return <IconBook size={ICON_SIZE} stroke={1.5} />;
    case "codex_read_entry":
      return <IconFileText size={ICON_SIZE} stroke={1.5} />;
    case "write_codex_draft":
      return <IconPencil size={ICON_SIZE} stroke={1.5} />;
    default:
      return <IconTool size={ICON_SIZE} stroke={1.5} />;
  }
}

/**
 * The one-line label for a row — what the assistant DID, in the author's terms
 * rather than the wire's.
 *
 * The four named tools each get their own phrasing; every other name degrades to
 * the tool's own name plus a compact argument list, so a tool added later (or one
 * this build has never heard of) still renders a readable row instead of breaking
 * the trace.
 */
function rowLabel(row: ToolTraceRow): string {
  const args = row.arguments;
  switch (row.toolName) {
    case "web_search": {
      const query = stringArg(args, "query");
      return query === null ? "Searched the web" : `Searched the web for “${short(query)}”`;
    }
    case "codex_search": {
      const query = stringArg(args, "query");
      const base =
        query === null ? "Searched the codex" : `Searched the codex for “${short(query)}”`;
      const hits = codexHitCount(row.result);
      if (hits === null) return base;
      return `${base} — ${hits} ${hits === 1 ? "entry" : "entries"}`;
    }
    case "codex_read_entry": {
      const entryId = stringArg(args, "entry_id");
      return entryId === null ? "Read a codex entry" : `Read codex entry ${entryId}`;
    }
    case "write_codex_draft": {
      const field = stringArg(args, "field");
      if (field === "name") return "Wrote the entry's name";
      if (field === "body") return "Wrote the entry's text";
      return "Wrote the entry's draft";
    }
    default: {
      // The generic fallback: the name as the backend knows it, plus whichever
      // arguments it happened to carry. Never throws on an unrecognized shape.
      const keys = Object.keys(args);
      return keys.length === 0 ? row.toolName : `${row.toolName}(${keys.join(", ")})`;
    }
  }
}

/** Pretty-print a row's arguments for the expanded view; never throws on a cycle. */
function formatArguments(args: Record<string, unknown>): string {
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return String(args);
  }
}

export const ToolCallTrace = observer(function ToolCallTrace({
  rows,
  expanded,
  rowKeyPrefix,
  onToggle,
}: ToolCallTraceProps): React.JSX.Element | null {
  // Nothing to show — the caller places this unconditionally beside
  // `ThinkingBlock`, so the "was there a trace at all" question is answered here.
  if (rows.length === 0) return null;

  return (
    <Stack gap={2}>
      {rows.map((row, index) => {
        const rowKey = `${rowKeyPrefix}:${index}`;
        const isOpen = expanded[rowKey] ?? false;
        const pending = row.result === null;
        const failed = row.ok === false;

        return (
          <Box key={rowKey}>
            <UnstyledButton
              onClick={() => onToggle(rowKey)}
              aria-expanded={isOpen}
              aria-label={`Toggle tool call ${row.toolName}`}
            >
              <Group gap={4} wrap="nowrap">
                {isOpen ? (
                  <IconChevronDown size={ICON_SIZE} stroke={1.5} />
                ) : (
                  <IconChevronRight size={ICON_SIZE} stroke={1.5} />
                )}
                {rowIcon(row.toolName)}
                <Text size="xs" c={failed ? "red" : "dimmed"} fw={600}>
                  {rowLabel(row)}
                </Text>
                {/* A call still in flight: the row exists the moment the
                    `tool_call` frame lands, so the author sees the assistant
                    reach for a tool rather than only that it did. */}
                {pending && <Loader size={ICON_SIZE} />}
                {failed && <IconAlertTriangle size={ICON_SIZE} stroke={1.5} color="red" />}
              </Group>
            </UnstyledButton>

            {isOpen && (
              <Stack gap={2} mt={2} ml={ICON_SIZE}>
                <Code block fz="xs">
                  {formatArguments(row.arguments)}
                </Code>
                <Text size="xs" c="dimmed" style={{ whiteSpace: "pre-wrap" }}>
                  {row.result ?? "Running…"}
                </Text>
              </Stack>
            )}
          </Box>
        );
      })}
    </Stack>
  );
});
