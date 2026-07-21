import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { Container, Loader, Table, Text, Title } from "@mantine/core";
import { HealthPageState, loadHealth } from "./healthPageState";

/**
 * User SPA root page. Owns a stable `HealthPageState` via `useState`, loads on
 * mount / aborts on unmount via a single page-level `useEffect` (empty deps), and
 * renders directly from `state.*` (loading / ready `status`+`db` / error).
 */
export const HealthPage = observer(function HealthPage() {
  const [state] = useState(() => new HealthPageState());

  useEffect(() => {
    const ctrl = new AbortController();
    void loadHealth(state, ctrl.signal);
    return () => ctrl.abort();
  }, []);

  return (
    <Container size="sm" py="xl">
      <Title order={2} mb="md">BookWriter — Backend Health</Title>
      {state.healthStatus === "loading" && <Loader />}
      {state.healthStatus === "error" && (
        <Text c="red">{state.healthError ?? "Failed to load health."}</Text>
      )}
      {state.healthStatus === "ready" && state.health && (
        <Table>
          <Table.Tbody>
            <Table.Tr>
              <Table.Td>status</Table.Td>
              <Table.Td>{state.health.status}</Table.Td>
            </Table.Tr>
            <Table.Tr>
              <Table.Td>db</Table.Td>
              <Table.Td>{state.health.db}</Table.Td>
            </Table.Tr>
          </Table.Tbody>
        </Table>
      )}
    </Container>
  );
});
