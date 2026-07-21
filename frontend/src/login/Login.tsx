import { MantineProvider, Center, Title } from "@mantine/core";
import { observer } from "mobx-react-lite";
import "@mantine/core/styles.css";
import "../../global.css";
import { theme } from "../../theme";

export const Login = observer(function Login() {
  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <Center h="100vh">
        <Title order={2}>Login (coming soon)</Title>
      </Center>
    </MantineProvider>
  );
});
