import { observer } from "mobx-react-lite";
import { Container, MantineProvider, Stack, Text, Title } from "@mantine/core";
import "@mantine/core/styles.css";
import "../../global.css";
import { theme } from "../../theme";

/**
 * Reader SPA stub (feature 010): a Mantine-themed placeholder naming the table of
 * contents as the reader's only Stage-2 surface. **No router, no gate, no data** —
 * the reader's real build is out of scope per the feature brief.
 */
export const App = observer(function App() {
  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <Container size="lg" py="md">
        <Stack align="flex-start" gap="sm">
          <Title order={3}>Reader</Title>
          <Text c="dimmed">
            The reader is not built yet. Its only Stage-2 surface will be the table of
            contents; the rest arrives in a later feature.
          </Text>
        </Stack>
      </Container>
    </MantineProvider>
  );
});
