/**
 * Harness self-check — fast/002.admin-ui-retune, DoD-0.
 *
 * This spec deliberately exercises NO feature source. It renders stock Mantine /
 * react-router components through `renderWithProviders` and asserts with
 * jest-dom matchers, proving the whole harness works: jsdom, the `matchMedia`
 * and `ResizeObserver` stubs, `scrollIntoView`, the matcher registration,
 * `env="test"`'s portal-free inline rendering, and the optional `MemoryRouter`.
 *
 * Consequence: **DoD-0 is expected to be GREEN at the red gate** while every
 * other spec in `tests/` is red ("not implemented"). That contrast is the
 * intended signal — see plan.md, "Warning to the red-gate verifier".
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { Button, Menu } from "@mantine/core";
import { Link } from "react-router-dom";
import { renderWithProviders } from "./support/render";

describe("frontend test harness (DoD-0)", () => {
  it("DoD-0: renders a stock Mantine component through renderWithProviders", () => {
    renderWithProviders(<Button>Ping</Button>);

    expect(screen.getByRole("button", { name: "Ping" })).toBeInTheDocument();
  });

  it("DoD-0: jest-dom matchers see Mantine's rendered DOM state", () => {
    renderWithProviders(<Button disabled>Nope</Button>);

    expect(screen.getByRole("button", { name: "Nope" })).toBeDisabled();
  });

  it("DoD-0: env=\"test\" renders an opened Menu inline and synchronously (no portal, no waitFor)", () => {
    renderWithProviders(
      <Menu opened>
        <Menu.Target>
          <Button>Open</Button>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Item>Alpha</Menu.Item>
        </Menu.Dropdown>
      </Menu>,
    );

    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Alpha" })).toBeInTheDocument();
  });

  it("DoD-0: the `route` option wraps the tree in a MemoryRouter", () => {
    renderWithProviders(<Link to="/llm-servers">Servers</Link>, { route: "/" });

    expect(screen.getByRole("link", { name: "Servers" })).toHaveAttribute("href", "/llm-servers");
  });
});
