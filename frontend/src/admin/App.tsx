import { BrowserRouter, Route, Routes } from "react-router-dom";
import { MantineProvider, Center, Title } from "@mantine/core";
import { observer } from "mobx-react-lite";
import "@mantine/core/styles.css";
import "../../global.css";
import { theme } from "../../theme";

export const App = observer(function App() {
  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <BrowserRouter basename="/admin">
        <Routes>
          <Route
            path="*"
            element={
              <Center h="100%">
                <Title order={2}>BookWriter — Admin (coming soon)</Title>
              </Center>
            }
          />
        </Routes>
      </BrowserRouter>
    </MantineProvider>
  );
});
