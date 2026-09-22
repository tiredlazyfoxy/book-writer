import {
  MantineProvider,
  Center,
  Stack,
  Title,
  Text,
  Paper,
  Tabs,
  TextInput,
  PasswordInput,
  FileInput,
  Button,
  Alert,
  Loader,
} from "@mantine/core";
import { observer } from "mobx-react-lite";
import { useEffect, useState, type ReactNode } from "react";
import { runInAction } from "mobx";
import "@mantine/core/styles.css";
import "../../global.css";
import { theme } from "../../theme";
import {
  LoginState,
  loadStatus,
  submitCreate,
  submitImport,
  handleLogin,
  type SetupMode,
} from "./loginState";

// Login entry (rebuilt from the 002 placeholder). Owns a stable LoginState
// instance and runs `loadStatus` on mount. When the instance still needs setup
// it renders the tabbed create/import wizard; once configured it renders the
// real login form (username/password -> `handleLogin`).
// Convention-bound: observer-wrapped, drafts held in the state class (no plain
// useState fields, no Mantine useForm), effects are the external loginState fns,
// navigation via window.location.href inside those fns.

export const Login = observer(function Login() {
  const [state] = useState(() => new LoginState());

  useEffect(() => {
    const controller = new AbortController();
    void loadStatus(state, controller.signal);
    return () => controller.abort();
  }, []);

  const onSubmitCreate = () => {
    void submitCreate(state);
  };
  const onSubmitImport = () => {
    void submitImport(state);
  };
  const onSubmitLogin = () => {
    void handleLogin(state);
  };

  let content: ReactNode;

  if (state.needsSetupStatus === "idle" || state.needsSetupStatus === "loading") {
    content = (
      <Stack align="center">
        <Loader />
        <Text c="dimmed">Checking instance status…</Text>
      </Stack>
    );
  } else if (state.needsSetupStatus === "error") {
    content = (
      <Alert color="red" title="Cannot reach the server">
        {state.needsSetupError}
      </Alert>
    );
  } else if (state.needsSetup === false) {
    content = (
      <Stack>
        <Title order={2}>Sign in</Title>
        <Text c="dimmed">Enter your credentials to access BookWriter.</Text>
        <TextInput
          label="Username"
          value={state.loginUsername}
          onChange={(e) =>
            runInAction(() => {
              state.loginUsername = e.currentTarget.value;
            })
          }
        />
        <PasswordInput
          label="Password"
          value={state.loginPassword}
          onChange={(e) =>
            runInAction(() => {
              state.loginPassword = e.currentTarget.value;
            })
          }
        />
        {state.loginError ? <Alert color="red">{state.loginError}</Alert> : null}
        <Button
          onClick={onSubmitLogin}
          disabled={!state.canSubmitLogin}
          loading={state.loginStatus === "loading"}
        >
          Sign in
        </Button>
      </Stack>
    );
  } else {
    content = (
      <Stack>
        <Title order={2}>BookWriter setup</Title>
        <Text c="dimmed">Create a new instance or import an existing export.</Text>
        <Tabs
          value={state.mode}
          onChange={(value) =>
            runInAction(() => {
              state.mode = (value as SetupMode | null) ?? "create";
            })
          }
        >
          <Tabs.List grow>
            <Tabs.Tab value="create">Create</Tabs.Tab>
            <Tabs.Tab value="import">Import</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="create" pt="md">
            <Stack>
              <TextInput
                label="Admin username"
                value={state.username}
                onChange={(e) =>
                  runInAction(() => {
                    state.username = e.currentTarget.value;
                  })
                }
              />
              <PasswordInput
                label="Password"
                value={state.password}
                error={
                  state.password.length > 0 && state.passwordTooShort
                    ? "Password must be at least 8 characters."
                    : null
                }
                onChange={(e) =>
                  runInAction(() => {
                    state.password = e.currentTarget.value;
                  })
                }
              />
              <PasswordInput
                label="Confirm password"
                value={state.passwordConfirm}
                error={
                  state.passwordConfirm.length > 0 && !state.passwordsMatch
                    ? "Passwords do not match."
                    : null
                }
                onChange={(e) =>
                  runInAction(() => {
                    state.passwordConfirm = e.currentTarget.value;
                  })
                }
              />
              {state.submitError ? (
                <Alert color="red">{state.submitError}</Alert>
              ) : null}
              <Button
                onClick={onSubmitCreate}
                disabled={!state.canSubmitCreate}
                loading={state.submitStatus === "loading"}
              >
                Create instance
              </Button>
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="import" pt="md">
            <Stack>
              <FileInput
                label="Export archive"
                placeholder="Select a .jsonl.gz export"
                value={state.importFile}
                onChange={(file) =>
                  runInAction(() => {
                    state.importFile = file;
                  })
                }
              />
              {state.submitError ? (
                <Alert color="red">{state.submitError}</Alert>
              ) : null}
              <Button
                onClick={onSubmitImport}
                disabled={!state.canSubmitImport}
                loading={state.submitStatus === "loading"}
              >
                Import instance
              </Button>
            </Stack>
          </Tabs.Panel>
        </Tabs>
      </Stack>
    );
  }

  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <Center h="100vh">
        <Paper p="xl" withBorder w={420}>
          {content}
        </Paper>
      </Center>
    </MantineProvider>
  );
});
