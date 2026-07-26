import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import {
  ActionIcon,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Menu,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { IconDots, IconEdit, IconPlayerPause, IconPlayerPlay, IconPlus } from "@tabler/icons-react";
import type { SubAgent } from "../../types/assistantConfig";
import {
  SubAgentsPageState,
  disableSubAgentAction,
  enableSubAgentAction,
  loadSubAgentsPage,
} from "./subAgentsPageState";
import { SubAgentFormModal } from "../components/sub-agents/SubAgentFormModal";

/**
 * Admin SPA sub-agents page (`/sub-agents`, feature 012 step 008 — replaces the step-006
 * shell). Owns a stable `SubAgentsPageState` via `useState`, loads sub-agents + tool
 * catalogue + modes + LLM servers on mount / aborts on unmount via a single page-level
 * `useEffect` (deps `[state]`), and renders one row per sub-agent — **disabled ones
 * included** — with a trailing 60px `Menu` column.
 *
 * The form target is component-local `useState` (`LlmServersPage.tsx:50-54`), NOT page
 * state, in its full three-state form: `undefined` = closed, `null` = create, a
 * sub-agent = edit. Every mutation refreshes through the loader; there are no optimistic
 * updates.
 *
 * The row menu offers **Edit** and **Disable** or **Enable** — and **no Delete item at
 * all**: there is no hard delete for a sub-agent anywhere in the system (UC-097,
 * `context.md` → scope decision 6). Disable is a row action rather than a form field
 * because it cascades, detaching the sub-agent from every mode (US-114.AC-2).
 *
 * Exported both by name (what `routes.tsx` imports) and as the module default — step 006
 * froze both and step 007 kept both.
 *
 * Each row summarises the model assignment (`server / model`, or *inherits main chat*
 * when both wire fields are null), the tool count and the accessible-mode count.
 */
export const SubAgentsPage = observer(function SubAgentsPage() {
  const [state] = useState(() => new SubAgentsPageState());

  // Form target — component-local, not page state (decision 9). undefined = closed,
  // null = create, a sub-agent = edit.
  const [formTarget, setFormTarget] = useState<SubAgent | null | undefined>(undefined);

  useEffect(() => {
    const ctrl = new AbortController();
    void loadSubAgentsPage(state, ctrl.signal);
    return () => ctrl.abort();
  }, [state]);

  /** Re-load after a save or a disable/enable (no optimistic updates). */
  const refresh = () => {
    const ctrl = new AbortController();
    void loadSubAgentsPage(state, ctrl.signal);
  };

  const handleDisable = (id: string) => {
    const ctrl = new AbortController();
    void disableSubAgentAction(state, id, ctrl.signal);
  };

  const handleEnable = (id: string) => {
    const ctrl = new AbortController();
    void enableSubAgentAction(state, id, ctrl.signal);
  };

  const loading = state.subAgentsStatus === "idle" || state.subAgentsStatus === "loading";
  const error =
    state.subAgentsError ?? state.toolsError ?? state.modesError ?? state.serversError;

  /**
   * The row's model assignment: `server / model`, or the inherit wording when the pair
   * is unset. An id with no loaded server (a since-removed one) degrades to the raw id
   * rather than rendering blank.
   */
  const modelAssignment = (subAgent: SubAgent) => {
    if (subAgent.llm_server_id === null || subAgent.model_name === null) {
      return "inherits main chat";
    }
    const server = state.servers.find((candidate) => candidate.id === subAgent.llm_server_id);
    return `${server ? server.name : subAgent.llm_server_id} / ${subAgent.model_name}`;
  };

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>Sub-agents</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setFormTarget(null)}>
          New sub-agent
        </Button>
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
              <Table.Th>Name</Table.Th>
              <Table.Th>Model</Table.Th>
              <Table.Th>Tools</Table.Th>
              <Table.Th>Modes</Table.Th>
              <Table.Th w={60} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {state.subAgents.map((subAgent) => (
              <Table.Tr key={subAgent.id}>
                <Table.Td>
                  {/* A disabled sub-agent is still listed — and visibly marked
                      (UC-097 step 1, US-114.AC-3). */}
                  <Group gap="xs">
                    <Text size="sm">{subAgent.name}</Text>
                    {subAgent.disabled && (
                      <Badge variant="light" size="sm" color="gray">
                        Disabled
                      </Badge>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{modelAssignment(subAgent)}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{subAgent.tool_names.length}</Text>
                </Table.Td>
                <Table.Td>
                  {/* The sub-agent side of the same `mode_subagent` rows the modes
                      page writes (US-112.AC-2). */}
                  <Text size="sm">{subAgent.mode_keys.length}</Text>
                </Table.Td>
                <Table.Td>
                  <Menu shadow="md" width={180} position="bottom-end">
                    <Menu.Target>
                      <ActionIcon
                        variant="subtle"
                        color="gray"
                        size="sm"
                        aria-label="Sub-agent actions"
                      >
                        <IconDots size={16} />
                      </ActionIcon>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Item
                        leftSection={<IconEdit size={14} />}
                        onClick={() => setFormTarget(subAgent)}
                      >
                        Edit
                      </Menu.Item>
                      {subAgent.disabled ? (
                        <Menu.Item
                          leftSection={<IconPlayerPlay size={14} />}
                          onClick={() => handleEnable(subAgent.id)}
                        >
                          Enable
                        </Menu.Item>
                      ) : (
                        <Menu.Item
                          leftSection={<IconPlayerPause size={14} />}
                          onClick={() => handleDisable(subAgent.id)}
                        >
                          Disable
                        </Menu.Item>
                      )}
                      {/* NO Delete item — deliberately. There is no hard delete for a
                          sub-agent anywhere (UC-097; context.md -> scope decision 6). */}
                    </Menu.Dropdown>
                  </Menu>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {formTarget !== undefined && (
        <SubAgentFormModal
          opened
          subAgent={formTarget}
          tools={state.tools}
          modes={state.modes}
          servers={state.servers}
          onClose={() => setFormTarget(undefined)}
          onSaved={refresh}
        />
      )}
    </Container>
  );
});

export default SubAgentsPage;
