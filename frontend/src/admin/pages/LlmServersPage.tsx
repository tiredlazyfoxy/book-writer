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
import {
  IconDots,
  IconEdit,
  IconListCheck,
  IconPlus,
  IconStar,
  IconStarOff,
  IconTrash,
} from "@tabler/icons-react";
import type { LlmServer } from "../../types/llmServers";
import {
  LlmServersPageState,
  clearEmbeddingAction,
  deleteServerAction,
  loadServers,
} from "./llmServersPageState";
import { ServerFormModal } from "../components/llm-servers/ServerFormModal";
import { ModelsModal } from "../components/llm-servers/ModelsModal";
import { EmbeddingModal } from "../components/llm-servers/EmbeddingModal";

/**
 * Admin SPA LLM-servers page (`/llm-servers`). Owns a stable `LlmServersPageState`
 * via `useState`, loads on mount / aborts on unmount via a single page-level
 * `useEffect` (deps `[state]`), and renders the servers list (name, backend-type
 * badge, api-key-presence badge, enabled-model count, embedding indicator) with a
 * per-row `Menu` (Clear Embedding / Delete) plus a header Add button.
 *
 * SEAM FOR STEP 006 — modal wiring (New server / per-row Select Models / Set
 * Embedding / Edit) and its component-local `useState` open/target flags arrive in
 * step 006. This skeleton freezes the state/effect/route wiring and compiles; the
 * `Add server` button and Menu items are placeholders the coder fleshes out.
 */
export const LlmServersPage = observer(function LlmServersPage() {
  const [state] = useState(() => new LlmServersPageState());

  // Modal open/target flags — component-local, not page state (decision 9).
  // formTarget: undefined = closed, null = create, server = edit.
  const [formTarget, setFormTarget] = useState<LlmServer | null | undefined>(undefined);
  const [modelsTarget, setModelsTarget] = useState<LlmServer | null>(null);
  const [embeddingTarget, setEmbeddingTarget] = useState<LlmServer | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    void loadServers(state, ctrl.signal);
    return () => ctrl.abort();
  }, [state]);

  /** Re-load the list after a mutation (delete / clear-embedding / step-006 modals). */
  const refresh = () => {
    const ctrl = new AbortController();
    void loadServers(state, ctrl.signal);
  };

  const handleDelete = (id: string) => {
    const ctrl = new AbortController();
    void deleteServerAction(state, id, ctrl.signal);
  };

  const handleClearEmbedding = () => {
    const ctrl = new AbortController();
    void clearEmbeddingAction(state, ctrl.signal);
  };

  const loading = state.serversStatus === "idle" || state.serversStatus === "loading";

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>LLM Servers</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setFormTarget(null)}>
          Add server
        </Button>
      </Group>

      {state.serversError && (
        <Text c="red" mb="md">
          {state.serversError}
        </Text>
      )}

      {loading ? (
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Type</Table.Th>
              <Table.Th>Base URL</Table.Th>
              <Table.Th>Key</Table.Th>
              <Table.Th>Models</Table.Th>
              <Table.Th>Active</Table.Th>
              <Table.Th w={60} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {state.servers.map((server) => (
              <Table.Tr
                key={server.id}
                style={server.is_active ? undefined : { opacity: 0.5 }}
              >
                <Table.Td>
                  <Group gap="xs">
                    <Text size="sm">{server.name}</Text>
                    {server.is_embedding && (
                      <Badge variant="light" size="sm" color="teal">
                        Embedding: {server.embedding_model ?? "—"}
                      </Badge>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" size="sm">
                    {server.backend_type}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" truncate="end" maw={250}>
                    {server.base_url}
                  </Text>
                </Table.Td>
                <Table.Td>
                  {/* Key PRESENCE only — the DTO carries no api_key value (US-021.AC-2). */}
                  <Text size="sm">{server.has_api_key ? "Yes" : "No"}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{server.enabled_models.length}</Text>
                </Table.Td>
                <Table.Td>
                  <Badge
                    variant="light"
                    size="sm"
                    color={server.is_active ? "green" : "gray"}
                  >
                    {server.is_active ? "Active" : "Inactive"}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Menu shadow="md" width={180} position="bottom-end">
                    <Menu.Target>
                      <ActionIcon variant="subtle" color="gray" size="sm">
                        <IconDots size={16} />
                      </ActionIcon>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Item
                        leftSection={<IconEdit size={14} />}
                        onClick={() => setFormTarget(server)}
                      >
                        Edit
                      </Menu.Item>
                      <Menu.Item
                        leftSection={<IconListCheck size={14} />}
                        onClick={() => setModelsTarget(server)}
                      >
                        Select Models
                      </Menu.Item>
                      <Menu.Item
                        leftSection={<IconStar size={14} />}
                        onClick={() => setEmbeddingTarget(server)}
                      >
                        Set Embedding
                      </Menu.Item>
                      {server.is_embedding && (
                        <Menu.Item
                          leftSection={<IconStarOff size={14} />}
                          onClick={handleClearEmbedding}
                        >
                          Clear Embedding
                        </Menu.Item>
                      )}
                      <Menu.Item
                        color="red"
                        leftSection={<IconTrash size={14} />}
                        onClick={() => handleDelete(server.id)}
                      >
                        Delete
                      </Menu.Item>
                    </Menu.Dropdown>
                  </Menu>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      {formTarget !== undefined && (
        <ServerFormModal
          opened
          server={formTarget}
          onClose={() => setFormTarget(undefined)}
          onSaved={refresh}
          onSelectModels={(server) => setModelsTarget(server)}
        />
      )}

      {modelsTarget && (
        <ModelsModal
          opened
          server={modelsTarget}
          onClose={() => setModelsTarget(null)}
          onSaved={refresh}
        />
      )}

      {embeddingTarget && (
        <EmbeddingModal
          opened
          server={embeddingTarget}
          onClose={() => setEmbeddingTarget(null)}
          onSaved={refresh}
        />
      )}
    </Container>
  );
});
