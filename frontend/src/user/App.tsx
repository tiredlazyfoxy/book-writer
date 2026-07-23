import { BrowserRouter } from "react-router-dom";
import { MantineProvider } from "@mantine/core";
import { observer } from "mobx-react-lite";
import "@mantine/core/styles.css";
import "../../global.css";
import { theme } from "../../theme";
import { getToken } from "../auth";
import { UserRoutes } from "./routes";

export const App = observer(function App() {
  // Mount-time protected-route gate (feature 004): no access token -> bounce to the
  // login entry before any routed content mounts.
  if (getToken() === null) {
    window.location.href = "/login/";
    return null;
  }

  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <BrowserRouter>
        <UserRoutes />
      </BrowserRouter>
    </MantineProvider>
  );
});
