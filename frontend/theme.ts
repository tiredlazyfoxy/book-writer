import { createTheme } from "@mantine/core";

export const theme = createTheme({
  primaryColor: "steel",
  defaultRadius: "sm",
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  headings: {
    fontWeight: "600",
  },
  colors: {
    // Muted steel blue — subdued blue for buttons/actions
    steel: [
      "#eef1f5",
      "#dce2ea",
      "#b4c0d0",
      "#8a9db6",
      "#6680a0",
      "#506d92",
      "#43628a",
      "#345278",
      "#2b496c",
      "#1e3d60",
    ],
    // Warm neutral palette — office feel
    dark: [
      "#c9c9c9",
      "#b8b8b8",
      "#828282",
      "#696969",
      "#424242",
      "#3b3b3b",
      "#2e2e2e",
      "#242424",
      "#1f1f1f",
      "#141414",
    ],
  },
  components: {
    Button: {
      defaultProps: {
        variant: "filled",
      },
    },
    TextInput: {
      defaultProps: {
        variant: "filled",
      },
    },
    PasswordInput: {
      defaultProps: {
        variant: "filled",
      },
    },
    FileInput: {
      defaultProps: {
        variant: "filled",
      },
    },
    Tabs: {
      defaultProps: {
        variant: "outline",
      },
    },
  },
});
