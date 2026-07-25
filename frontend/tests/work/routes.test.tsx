/**
 * Work route table — 010.working-page / 001.work-entry-scaffold, DoD-3.
 *
 * Bound to the frozen signature in status.md -> `## Skeleton` (step 001):
 *   const WorkRoutes: FunctionComponent   // observer, no props
 *   const NotFoundPage: FunctionComponent // observer, no props
 *
 * At this step the route table declares ONLY the terminal catch-all rendering the
 * work not-found page (later steps nest the real routes into it). The spec
 * ("Interface intent") gives the not-found page "a not-found message and a plain
 * anchor back to the bookshelf at `/`" — that back anchor (href exactly "/") is
 * the page's identifying signal here. Its being the *only* link on screen proves
 * the catch-all is terminal: no route page's content sits beside it.
 *
 * Routes passed to `renderWithProviders` are basename-stripped (production's
 * `basename="/work"` never appears), so the work entry root is "/". The durable
 * assertion here is the entry root (no book id): "/" does not match `/:bookId`, so
 * it reaches the terminal top-level catch-all → NotFoundPage. (The unmatched
 * deep-path case is superseded from step 002 on: `/:bookId` + a splat child now
 * renders the workspace shell with an *in-pane* not-found, covered by that step's
 * shell nested-catch-all test in tests/work/WorkspaceShell.test.tsx.)
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { WorkRoutes } from "../../src/work/routes";
import { renderWithProviders } from "../support/render";

describe("WorkRoutes", () => {
  it("DoD-3: the entry root (no book id) renders the not-found page", () => {
    renderWithProviders(<WorkRoutes />, { route: "/" });

    // The not-found page's back-to-bookshelf anchor identifies it ...
    expect(screen.getByRole("link")).toHaveAttribute("href", "/");
    // ... and it is the only link on screen: the catch-all is terminal, no route
    // page's content leaked in beside it.
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });
});
