import { BrowserRouter } from "react-router-dom";
import { MantineProvider } from "@mantine/core";
import { observer } from "mobx-react-lite";
import "@mantine/core/styles.css";
import "../../global.css";
import { theme } from "../../theme";
import { WorkRoutes } from "./routes";

/**
 * Work SPA root: `MantineProvider` (shared `theme`, dark default) wrapping a
 * `BrowserRouter` with `basename="/work"` wrapping the route element. No shell yet —
 * step 002 adds it. Admission is decided in `main.tsx` before `createRoot` (see
 * `workGate.ts`), which is what keeps this component renderable in tests.
 */
export const App = observer(function App() {
  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <BrowserRouter basename="/work">
        <WorkRoutes />
      </BrowserRouter>
    </MantineProvider>
  );
});
