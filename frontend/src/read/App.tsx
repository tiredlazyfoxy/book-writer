import { BrowserRouter } from "react-router-dom";
import { MantineProvider } from "@mantine/core";
import { observer } from "mobx-react-lite";
import "@mantine/core/styles.css";
import "../../global.css";
import { theme } from "../../theme";
import { ReadRoutes } from "./routes";

/**
 * Reader SPA root (feature 022 — replaces feature 010's routerless placeholder).
 *
 * `MantineProvider` → `<BrowserRouter basename="/read">` → the route table, the
 * `src/work/App.tsx` shape verbatim. `<BrowserRouter>`, never
 * `createBrowserRouter` (decision D8, DoD-15): the reader is a separate Vite
 * entry served from `/read/index.html`, so the basename is what makes
 * `/read/:bookId` deep links resolve.
 *
 * Nothing editing-related is mounted or imported anywhere beneath this tree —
 * `@mantine/tiptap` and every save control stay out of `src/read/` so "does a
 * reader have an edit affordance?" stays a **build-time** property
 * (frontend-workspace.md, decision D11, DoD-17).
 */
export const App = observer(function App() {
  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <BrowserRouter basename="/read">
        <ReadRoutes />
      </BrowserRouter>
    </MantineProvider>
  );
});
