import { BrowserRouter } from "react-router-dom";
import { MantineProvider } from "@mantine/core";
import { observer } from "mobx-react-lite";
import "@mantine/core/styles.css";
import "../../global.css";
import { theme } from "../../theme";
import { AdminShell } from "./components/shell/AdminShell";
import { AdminRoutes } from "./routes";

/**
 * Admin SPA root: `MantineProvider` (dark) -> `BrowserRouter` (basename="/admin")
 * -> {@link AdminShell} (the `AppShell` chrome) -> the route table.
 *
 * fast/002 removed two things from here: the **render-phase** `getToken()` check
 * that mutated the browser location during render (StrictMode ran it twice, and it
 * made this component unrenderable in a test), and the 44-line inline header.
 * Admission is now decided in `main.tsx` before `createRoot` — see
 * `adminGate.ts` — which is what makes this component, and therefore the whole
 * shell, testable.
 */
export const App = observer(function App() {
  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <BrowserRouter basename="/admin">
        <AdminShell>
          <AdminRoutes />
        </AdminShell>
      </BrowserRouter>
    </MantineProvider>
  );
});
