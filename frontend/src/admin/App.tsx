import { BrowserRouter, NavLink } from "react-router-dom";
import { MantineProvider, Group, Title } from "@mantine/core";
import { observer } from "mobx-react-lite";
import "@mantine/core/styles.css";
import "../../global.css";
import { theme } from "../../theme";
import { getToken } from "../auth";
import { AdminRoutes } from "./routes";

export const App = observer(function App() {
  // Mount-time protected-route gate (feature 004): no access token -> bounce to the
  // login entry before any routed content mounts. Feature 005 grows this App's
  // layout below but MUST keep this gate firing first.
  if (getToken() === null) {
    window.location.href = "/login/";
    return null;
  }

  // MantineProvider (dark) -> BrowserRouter (basename="/admin") -> a MINIMAL local
  // layout (a simple header, NO shared cross-SPA shell — decision 10) -> the route
  // table. The header/route-table markup is a skeleton shell; the coder refines it.
  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <BrowserRouter basename="/admin">
        <Group
          h={56}
          px="md"
          justify="space-between"
          style={{ borderBottom: "1px solid var(--mantine-color-dark-4)" }}
        >
          <Title order={4}>BookWriter — Admin</Title>
          {/* Minimal top nav (feature 006). Deliberately NOT a shared sidebar/shell
              framework — decision 10 deferred nav growth to "when 006 adds pages". */}
          <Group gap="md">
            <NavLink to="/">Users</NavLink>
            <NavLink to="/llm-servers">LLM Servers</NavLink>
            <NavLink to="/database">Database</NavLink>
          </Group>
        </Group>
        <AdminRoutes />
      </BrowserRouter>
    </MantineProvider>
  );
});
