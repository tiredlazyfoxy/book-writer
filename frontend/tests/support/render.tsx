import type { ReactNode } from "react";
import { MantineProvider } from "@mantine/core";
import { MemoryRouter } from "react-router-dom";
import { render, type RenderResult } from "@testing-library/react";
import { theme } from "../../theme";

/** Options for {@link renderWithProviders}. */
export interface RenderWithProvidersOptions {
  /**
   * Initial router location. When given, the tree is additionally wrapped in a
   * `MemoryRouter` seeded with this single entry. Paths are **basename-stripped**
   * — production's `basename="/admin"` never appears here, so the routes are
   * `/`, `/llm-servers`, `/database`.
   */
  route?: string;
}

/**
 * The ONLY way tests should render. Bare RTL `render` is wrong: every Mantine
 * component needs a `MantineProvider` ancestor, and the theme under test is the
 * real app theme.
 *
 * `env="test"` is load-bearing, not cosmetic — it disables Mantine's portals and
 * transitions, so an opened `Menu` / `Popover` renders **inline and
 * synchronously**. That removes every `waitFor` and every `document.body`
 * lookup from menu tests. `defaultColorScheme` is deliberately omitted; nothing
 * asserts colour.
 */
export function renderWithProviders(
  ui: ReactNode,
  options: RenderWithProvidersOptions = {},
): RenderResult {
  const { route } = options;
  const routed =
    route === undefined ? ui : <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>;

  return render(
    <MantineProvider theme={theme} env="test">
      {routed}
    </MantineProvider>,
  );
}
