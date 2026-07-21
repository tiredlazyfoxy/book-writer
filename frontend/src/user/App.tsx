import { BrowserRouter } from "react-router-dom";
import { MantineProvider } from "@mantine/core";
import { observer } from "mobx-react-lite";
import "@mantine/core/styles.css";
import "../../global.css";
import { theme } from "../../theme";
import { UserRoutes } from "./routes";

export const App = observer(function App() {
  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <BrowserRouter>
        <UserRoutes />
      </BrowserRouter>
    </MantineProvider>
  );
});
