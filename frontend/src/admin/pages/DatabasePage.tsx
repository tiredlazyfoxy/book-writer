import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import {
  Badge,
  Button,
  Container,
  FileInput,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import {
  DatabasePageState,
  createTableAction,
  exportAction,
  importAction,
  loadReport,
  rebuildAction,
  seedTableAction,
  syncTableAction,
} from "./databasePageState";

/**
 * Admin SPA database-management page (`/database`). Owns a stable
 * `DatabasePageState` via `useState`, loads the consistency report on mount /
 * aborts on unmount via a single page-level `useEffect` (deps `[state]`), and
 * renders the per-table drift report (status badge + drift column lists) with
 * per-row Create/Sync/Seed actions plus Export / Import / Rebuild controls.
 *
 * Each row action is offered for exactly one status — `Create` for `missing`,
 * `Sync` for `drift`, `Seed` for `seed-missing` — and confirms itself by the
 * reloaded report showing the row as `ok`.
 */
export const DatabasePage = observer(function DatabasePage() {
  const [state] = useState(() => new DatabasePageState());

  // File-picker flag — component-local, not page state (MobX hard rules).
  const [importFile, setImportFile] = useState<File | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    void loadReport(state, ctrl.signal);
    return () => ctrl.abort();
  }, [state]);

  const handleCreate = (name: string) => {
    const ctrl = new AbortController();
    void createTableAction(state, name, ctrl.signal);
  };

  const handleSync = (name: string) => {
    const ctrl = new AbortController();
    void syncTableAction(state, name, ctrl.signal);
  };

  const handleSeed = (name: string) => {
    const ctrl = new AbortController();
    void seedTableAction(state, name, ctrl.signal);
  };

  const handleRebuild = () => {
    const ctrl = new AbortController();
    void rebuildAction(state, ctrl.signal);
  };

  const handleImport = () => {
    if (!importFile) return;
    const ctrl = new AbortController();
    void importAction(state, importFile, ctrl.signal);
  };

  const handleExport = () => {
    void exportAction(state);
  };

  const loading =
    state.reportStatus === "idle" || state.reportStatus === "loading";

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>Database</Title>
        <Group>
          <Button onClick={handleExport}>Export</Button>
          <Button onClick={handleRebuild}>Rebuild index</Button>
        </Group>
      </Group>

      <Group mb="md">
        <FileInput
          placeholder="Select a .jsonl.gz export"
          value={importFile}
          onChange={setImportFile}
        />
        <Button onClick={handleImport} disabled={!importFile}>
          Import
        </Button>
      </Group>

      {state.rebuildResult && (
        <Text mb="md">Indexed rows: {state.rebuildResult.indexed_rows}</Text>
      )}

      {state.reportError && (
        <Text c="red" mb="md">
          {state.reportError}
        </Text>
      )}
      {state.actionError && (
        <Text c="red" mb="md">
          {state.actionError}
        </Text>
      )}

      {loading && (
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      )}

      {!loading && state.report && (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Table</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Columns</Table.Th>
              <Table.Th>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {state.report.tables.map((entry) => {
              const statusColor = {
                ok: "green",
                drift: "yellow",
                missing: "red",
                "seed-missing": "orange",
              }[entry.status];
              return (
                <Table.Tr key={entry.name}>
                  <Table.Td>{entry.name}</Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={statusColor}>
                      {entry.status}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {entry.status === "drift" ? (
                      <Stack gap={2}>
                        <Text size="xs">
                          Missing: {entry.missing_columns.join(", ") || "—"}
                        </Text>
                        <Text size="xs">
                          Extra: {entry.extra_columns.join(", ") || "—"}
                        </Text>
                      </Stack>
                    ) : (
                      "—"
                    )}
                  </Table.Td>
                  <Table.Td>
                    {entry.status === "missing" && (
                      <Button size="xs" onClick={() => handleCreate(entry.name)}>
                        Create
                      </Button>
                    )}
                    {entry.status === "drift" && (
                      <Button size="xs" onClick={() => handleSync(entry.name)}>
                        Sync
                      </Button>
                    )}
                    {entry.status === "seed-missing" && (
                      <Button size="xs" onClick={() => handleSeed(entry.name)}>
                        Seed
                      </Button>
                    )}
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}
    </Container>
  );
});
