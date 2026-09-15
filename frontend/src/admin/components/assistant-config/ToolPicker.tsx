import { observer } from "mobx-react-lite";
import { Checkbox, ScrollArea, Stack, Text } from "@mantine/core";
import { TOOL_GROUP_LABELS } from "../../../api/assistantConfig";
import type { AssistantTool } from "../../../types/assistantConfig";

interface ToolPickerProps {
  /** The backend tool catalogue, in registry declaration order — may be empty. */
  tools: AssistantTool[];
  /** The names currently ticked. Owned by the caller's draft; never mutated here. */
  selected: Set<string>;
  /** Called with the tool's name and its new checked state on every toggle. */
  onToggle: (name: string, checked: boolean) => void;
  /** Rendered verbatim, in place of the checkboxes, when `tools` is empty. */
  emptyMessage: string;
}

/** The heading for every group the backend declared and this frontend does not know. */
const OTHER_HEADING = "Other";

/** One rendered group: its heading, and the catalogue tools that fall under it. */
interface ToolGroup {
  key: string;
  heading: string;
  tools: AssistantTool[];
}

/**
 * `tools` split into the groups to render, in display order and with the empty
 * ones dropped.
 *
 * The display order is `TOOL_GROUP_LABELS`' own key order (Codex → Book → Web),
 * so adding a group there is the single edit that places it — followed by the
 * trailing `Other` catch-all, which collects every group key the map does not
 * carry. An unrecognised group is therefore **rendered, never dropped**: a tool
 * the backend added and this map has not caught up with still reaches the admin.
 *
 * A group with no tools is dropped whole — no heading, no container — so the
 * three-tool catalogue this picker started life with renders as three sections at
 * most, and a one-tool catalogue as one.
 *
 * Within a group, `filter` keeps the catalogue's own order, which is the
 * registry's declaration order.
 */
function groupTools(tools: AssistantTool[]): ToolGroup[] {
  const knownKeys = Object.keys(TOOL_GROUP_LABELS);
  const groups: ToolGroup[] = knownKeys.map((key) => ({
    key,
    heading: TOOL_GROUP_LABELS[key],
    tools: tools.filter((tool) => tool.group === key),
  }));
  groups.push({
    key: OTHER_HEADING,
    heading: OTHER_HEADING,
    tools: tools.filter((tool) => !knownKeys.includes(tool.group)),
  });
  return groups.filter((group) => group.tools.length > 0);
}

/**
 * The shared, group-laid-out tool picker (025) — one `<Checkbox>` per catalogue
 * tool, under a plain-text heading per `ToolDef.group`. Replaces the checkbox JSX
 * that `ModeEditorModal` and `SubAgentFormModal` duplicated byte for byte.
 *
 * `ToolPickerProps` is **module-private**, following `ModeEditorModalProps` /
 * `SubAgentFormModalProps`: bind to the component, not the type.
 *
 * The grouping is **visual only**: the headings are plain `<Text>`, never a
 * checkbox and never folded into one's accessible name, and there is no
 * select-all and no per-group state anywhere — a group is a layout of the flat
 * catalogue, not a thing that can be selected. Selection stays the caller's: this
 * component reads `selected` and reports toggles through `onToggle`, and the
 * caller rebuilds its own `Set` (a `Set` mutated in place is not observable to
 * MobX).
 */
export const ToolPicker = observer(function ToolPicker({
  tools,
  selected,
  onToggle,
  emptyMessage,
}: ToolPickerProps) {
  if (tools.length === 0) {
    // The same shape the two modals used inline, so an empty catalogue still
    // explains itself instead of leaving a blank box.
    return (
      <Text size="sm" c="dimmed">
        {emptyMessage}
      </Text>
    );
  }

  return (
    <ScrollArea.Autosize mah={360}>
      <Stack gap="xs">
        {groupTools(tools).map((group) => (
          <Stack key={group.key} gap="xs">
            <Text size="xs" fw={600} c="dimmed" tt="uppercase">
              {group.heading}
            </Text>
            {group.tools.map((tool) => (
              <Checkbox
                key={tool.name}
                label={tool.name}
                description={tool.description}
                checked={selected.has(tool.name)}
                onChange={(e) => onToggle(tool.name, e.currentTarget.checked)}
              />
            ))}
          </Stack>
        ))}
      </Stack>
    </ScrollArea.Autosize>
  );
});
