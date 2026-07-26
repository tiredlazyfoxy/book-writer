import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { ActionIcon, Container, Group, Loader, Table, Text, Title } from "@mantine/core";
import { IconEdit } from "@tabler/icons-react";
import { modeLabel } from "../../api/assistantConfig";
import type { AssistantMode } from "../../types/assistantConfig";
import { AssistantModesPageState, loadModesPage } from "./assistantModesPageState";
import { ModeEditorModal } from "../components/assistant-config/ModeEditorModal";

/**
 * Admin SPA assistant-modes page (`/assistant-modes`, feature 012 step 007 — replaces
 * the step-006 shell). Owns a stable `AssistantModesPageState` via `useState`, loads
 * modes + tool catalogue + sub-agent list on mount / aborts on unmount via a single
 * page-level `useEffect` (deps `[state]`), and renders one row per mode in the order
 * the api returned them, with a trailing 60px action column opening the editor.
 *
 * The edit target is component-local `useState` (`LlmServersPage.tsx:50-54`), NOT page
 * state — minus the create case: modes are seeded and fixed, so there is no header
 * action button and no `null` target. Saving closes the modal and re-runs the loader.
 *
 * Exported both by name (the repo-wide admin-page convention, and what `routes.tsx`
 * imports) and as the module default (the plan's stated shape) — step 006 froze both.
 *
 * Skeleton: state/effect/refresh/modal wiring and the page layout are frozen and
 * compile. The coder fills the three summary cells (prompt set? tool count, sub-agent
 * count) with their `Table.Th` headers; the load itself throws until `loadModesPage`
 * is implemented.
 */
export const AssistantModesPage = observer(function AssistantModesPage() {
  const [state] = useState(() => new AssistantModesPageState());

  // Edit target — component-local, not page state. undefined = closed, a mode =
  // editing. There is no create case, hence no `null`.
  const [editTarget, setEditTarget] = useState<AssistantMode | undefined>(undefined);

  useEffect(() => {
    const ctrl = new AbortController();
    void loadModesPage(state, ctrl.signal);
    return () => ctrl.abort();
  }, [state]);

  /** Re-load after a save (no optimistic updates). */
  const refresh = () => {
    const ctrl = new AbortController();
    void loadModesPage(state, ctrl.signal);
  };

  const loading = state.modesStatus === "idle" || state.modesStatus === "loading";
  const error = state.modesError ?? state.toolsError ?? state.subAgentsError;

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>Assistant modes</Title>
      </Group>

      {error && (
        <Text c="red" mb="md">
          {error}
        </Text>
      )}

      {loading && (
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      )}

      {!loading && !error && (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Mode</Table.Th>
              <Table.Th>Prompt</Table.Th>
              <Table.Th>Tools</Table.Th>
              <Table.Th>Sub-agents</Table.Th>
              <Table.Th w={60} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {state.modes.map((mode) => (
              <Table.Tr key={mode.key}>
                <Table.Td>
                  <Text size="sm">{modeLabel(mode.key)}</Text>
                </Table.Td>
                <Table.Td>
                  {/* Prompt PRESENCE only — an empty prompt is a valid saved state. */}
                  <Text size="sm">{mode.system_prompt ? "Yes" : "No"}</Text>
                </Table.Td>
                <Table.Td>
                  {/* Empty means *no tools*, never "all tools". */}
                  <Text size="sm">{mode.tool_names.length}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{mode.sub_agent_ids.length}</Text>
                </Table.Td>
                <Table.Td>
                  <ActionIcon
                    variant="subtle"
                    color="gray"
                    size="sm"
                    aria-label="Edit mode"
                    onClick={() => setEditTarget(mode)}
                  >
                    <IconEdit size={16} />
                  </ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {editTarget !== undefined && (
        <ModeEditorModal
          opened
          mode={editTarget}
          tools={state.tools}
          subAgents={state.subAgents}
          onClose={() => setEditTarget(undefined)}
          onSaved={refresh}
        />
      )}
    </Container>
  );
});

export default AssistantModesPage;
