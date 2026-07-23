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
import { IconDots, IconKey, IconPlus, IconUserCog, IconUserOff } from "@tabler/icons-react";
import type { AdminUserResponse } from "../../types/admin";
import { UsersPageState, disableUserAction, loadUsers } from "./usersPageState";
import { CreateUserModal } from "../components/users/CreateUserModal";
import { SetPasswordModal } from "../components/users/SetPasswordModal";
import { SetRoleModal } from "../components/users/SetRoleModal";

/**
 * Admin SPA root page (`/`). Owns a stable `UsersPageState` via `useState`, loads on
 * mount / aborts on unmount via a single page-level `useEffect` (empty deps), and
 * renders the users list (username, role badge, last-login, active) with a per-row
 * `Menu` (Set Password / Change Role / Disable) plus a header Create button.
 *
 * Modal open/target flags are component-local `useState` (decision 10), NOT page
 * state. Each successful mutation calls `refresh` (= re-`loadUsers`) so the list
 * reflects the backend. Modal behavior itself is the coder's; this shell freezes the
 * wiring and compiles.
 */
export const UsersPage = observer(function UsersPage() {
  const [state] = useState(() => new UsersPageState());

  // Modal open/target flags — component-local, not page state (decision 10).
  const [createOpen, setCreateOpen] = useState(false);
  const [target, setTarget] = useState<AdminUserResponse | null>(null);
  const [action, setAction] = useState<"password" | "role" | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    void loadUsers(state, ctrl.signal);
    return () => ctrl.abort();
  }, [state]);

  const handleDisable = (userId: string) => {
    const ctrl = new AbortController();
    void disableUserAction(state, userId, ctrl.signal);
  };

  /** The page refresh passed to every modal as `onCreated`/`onSaved`. */
  const refresh = () => {
    const ctrl = new AbortController();
    void loadUsers(state, ctrl.signal);
  };

  const closeTarget = () => {
    setTarget(null);
    setAction(null);
  };

  const loading = state.usersStatus === "idle" || state.usersStatus === "loading";

  return (
    <Container size="lg" py="md">
      <Group justify="space-between" mb="md">
        <Title order={3}>Users</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setCreateOpen(true)}>
          Create user
        </Button>
      </Group>

      {state.usersError && <Text c="red" mb="md">{state.usersError}</Text>}

      {loading ? (
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Username</Table.Th>
              <Table.Th>Role</Table.Th>
              <Table.Th>Last Login</Table.Th>
              <Table.Th>Active</Table.Th>
              <Table.Th w={60} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {state.users.map((user) => (
              <Table.Tr key={user.id}>
                <Table.Td>
                  <Text size="sm">{user.username}</Text>
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" size="sm">
                    {user.role}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {user.last_login ?? "Never"}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{user.active ? "Active" : "Disabled"}</Text>
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
                        leftSection={<IconKey size={14} />}
                        onClick={() => {
                          setTarget(user);
                          setAction("password");
                        }}
                      >
                        Set Password
                      </Menu.Item>
                      <Menu.Item
                        leftSection={<IconUserCog size={14} />}
                        onClick={() => {
                          setTarget(user);
                          setAction("role");
                        }}
                      >
                        Change Role
                      </Menu.Item>
                      <Menu.Item
                        color="red"
                        leftSection={<IconUserOff size={14} />}
                        onClick={() => handleDisable(user.id)}
                      >
                        Disable
                      </Menu.Item>
                    </Menu.Dropdown>
                  </Menu>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <CreateUserModal
        opened={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={refresh}
      />

      {target && action === "password" && (
        <SetPasswordModal
          opened
          userId={target.id}
          username={target.username}
          onClose={closeTarget}
          onSaved={refresh}
        />
      )}

      {target && action === "role" && (
        <SetRoleModal
          opened
          userId={target.id}
          username={target.username}
          currentRole={target.role}
          onClose={closeTarget}
          onSaved={refresh}
        />
      )}
    </Container>
  );
});
