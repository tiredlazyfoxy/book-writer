import { observer } from "mobx-react-lite";
import { Group, Menu, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconChevronDown, IconKey, IconLogout } from "@tabler/icons-react";
import type { CurrentUser } from "../../../auth";

export interface AdminUserMenuProps {
  /** The signed-in identity, or `null` when there is none. */
  user: CurrentUser | null;
  /** Invoked when the Logout item is activated. */
  onLogout: () => void;
}

/**
 * Header user chip + dropdown. **Pure props only** — it imports nothing runtime
 * from `auth.ts` (only the `CurrentUser` type), which is exactly what keeps its
 * test mock-free: a `vi.fn()` for `onLogout` suffices.
 *
 * Target: an `UnstyledButton` showing the username (primary) + role (dimmed) + a
 * chevron. Dropdown: **Logout** (`IconLogout`, invokes `onLogout`) and **Change
 * password**, which is `disabled` with a "coming soon" hint (the real feature is
 * out of scope — there is no backend route for it). When `user` is `null` the
 * component renders nothing.
 */
export const AdminUserMenu = observer(function AdminUserMenu({
  user,
  onLogout,
}: AdminUserMenuProps) {
  if (!user) return null;

  return (
    <Menu shadow="md" width={220} position="bottom-end">
      <Menu.Target>
        <UnstyledButton px="xs" py={4}>
          <Group gap="xs" wrap="nowrap">
            <Stack gap={0}>
              <Text size="sm" fw={500} lh={1.2}>
                {user.username}
              </Text>
              <Text size="xs" c="dimmed" lh={1.2}>
                {user.role}
              </Text>
            </Stack>
            <IconChevronDown size={16} stroke={1.5} />
          </Group>
        </UnstyledButton>
      </Menu.Target>

      <Menu.Dropdown>
        <Menu.Item
          leftSection={<IconLogout size={16} stroke={1.5} />}
          onClick={onLogout}
        >
          Logout
        </Menu.Item>
        {/* Self-service password change is deliberately out of scope (no backend
            route exists yet) — it ships visibly disabled. */}
        <Menu.Item
          leftSection={<IconKey size={16} stroke={1.5} />}
          disabled
          title="Coming soon"
        >
          Change password
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
});
