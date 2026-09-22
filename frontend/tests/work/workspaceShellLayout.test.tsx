/**
 * Workspace shell layout chrome — pin control, resize handle, CSS-variable wiring.
 * fast/005.workspace-layout, DoD-12 … DoD-17.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (fast/005):
 *   const WorkspaceShell = observer(...)                    // no props; reads :bookId
 *   class WorkspaceShellState { … navCollapsed; chatWidthFraction; resizing;
 *                               asideWidthCss; get navbarWidth; get chatWidthCssValue }
 *   const ChatResizeHandle = observer(({ state }: ChatResizeHandleProps) => …)
 *   readWorkspaceLayout() / writeWorkspaceLayout(layout) / CHAT_WIDTH_CSS_VAR
 *
 * The shell is mounted whole (it is the page-level mount for `:bookId`), so this spec
 * reuses `WorkspaceShell.test.tsx`'s `api/books` + `api/chats` + `api/flags` +
 * `api/continuity` module-mock block VERBATIM — harness plumbing, without which a
 * shell mount fires real fetches. Nothing here asserts on any of those modules, and
 * that file itself is untouched (DoD-22).
 *
 * Every expected value comes from `plan.md` -> Definition of done, never from code:
 *   - the pin control's accessible name is "Collapse navigator" when expanded and
 *     "Pin navigator open" when collapsed, with `aria-pressed` the negation of
 *     `navCollapsed`; activating it persists (DoD-12);
 *   - a layout record seeded BEFORE the render is honoured on first render — the
 *     state hydrates in its constructor, so seeding after mount would prove nothing
 *     (DoD-13);
 *   - the handle is a `role="separator"` named "Resize chat pane" with integer-percent
 *     `aria-valuemin` 15 / `aria-valuemax` 60 / `aria-valuenow` 35 at defaults (DoD-14);
 *   - `ArrowLeft` WIDENS the pane (it grows leftward from the right edge): one press
 *     from the default gives `aria-valuenow` 37, a stored `chatWidth` of 0.37 and a
 *     `--work-chat-width` of "37vw" — which is what proves the autorun is wired
 *     (DoD-15) — and the keyboard path clamps at the max (DoD-16);
 *   - unmounting removes the custom property (DoD-17).
 *
 * The pointer DRAG is deliberately not simulated: jsdom has no layout engine, no
 * `PointerEvent` and no `setPointerCapture`, so the gesture is `[manual/live]`
 * (DoD-18). Its geometry is covered as a pure function in `workspaceLayout.test.ts`
 * (DoD-6); its persistence and CSS-variable wiring are covered here through the
 * keyboard path. `globals: false`.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import type { RenderResult } from "@testing-library/react";
import type { BookDetailResponse } from "../../src/types/books";
import * as booksApi from "../../src/api/books";
import * as chatsApi from "../../src/api/chats";
import * as flagsApi from "../../src/api/flags";
import * as continuityApi from "../../src/api/continuity";

// HARNESS ONLY — copied from `tests/work/WorkspaceShell.test.tsx`. Whole-module
// factories (never `fetch`), armed with EMPTY fixtures in `beforeEach`, so the shell's
// mount loads resolve locally instead of reaching the real HTTP client and leaving
// rejected promises behind. NOTHING in this file asserts on any of these modules.
vi.mock("../../src/api/flags", () => ({
  listFlags: vi.fn(),
  raiseFlag: vi.fn(),
  resolveFlag: vi.fn(),
}));

vi.mock("../../src/api/continuity", () => ({
  getStateNotes: vi.fn(),
  updateStateNotes: vi.fn(),
  getBookContinuity: vi.fn(),
  getChapterChangeset: vi.fn(),
}));

vi.mock("../../src/api/books", () => ({
  getBookDetail: vi.fn(),
}));

vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
}));

import { WorkspaceShell } from "../../src/work/components/shell/WorkspaceShell";
import {
  CHAT_WIDTH_CSS_VAR,
  readWorkspaceLayout,
  writeWorkspaceLayout,
} from "../../src/work/workspaceLayout";
import { renderWithProviders } from "../support/render";

const BOOK_TITLE = "The Long Novel";

/** A fully-typed BookDetailResponse fixture; only id + title vary. */
function makeDetail(id: string, title: string): BookDetailResponse {
  return {
    id,
    owner_id: "u-1",
    title,
    description: "",
    collaboration_mode: "free",
    visibility: "private",
    state: "active",
    created_at: null,
    modified_at: null,
    members: [],
  };
}

/** HARNESS ONLY: every continuity read the work surfaces make on mount, empty. */
function armContinuityReads(): void {
  vi.mocked(continuityApi.getStateNotes).mockResolvedValue({
    book_id: "bk-1",
    active_notes: "",
    modified_at: null,
  });
  vi.mocked(continuityApi.updateStateNotes).mockResolvedValue({
    book_id: "bk-1",
    active_notes: "",
    modified_at: null,
  });
  vi.mocked(continuityApi.getBookContinuity).mockResolvedValue({ items: [] });
  vi.mocked(flagsApi.listFlags).mockResolvedValue({ items: [] });
  vi.mocked(continuityApi.getChapterChangeset).mockResolvedValue({
    chapter_id: "ch-1",
    added: "",
    modified: "",
    deleted: "",
    status: null,
    created_at: null,
    modified_at: null,
  });
}

/** Mounts the shell under a `:bookId` route with one nested subject view. */
function renderShell(): RenderResult {
  return renderWithProviders(
    <Routes>
      <Route path="/:bookId" element={<WorkspaceShell />}>
        <Route path="state" element={<div data-testid="subject-state">state subject</div>} />
      </Route>
    </Routes>,
    { route: "/bk-1/state" },
  );
}

/** The resize handle, once the shell has mounted. */
function findHandle(): Promise<HTMLElement> {
  return screen.findByRole("separator", { name: "Resize chat pane" });
}

/** The value the shell's autorun has pushed onto the document element. */
function chatWidthVar(): string {
  return document.documentElement.style.getPropertyValue(CHAT_WIDTH_CSS_VAR);
}

beforeEach(() => {
  armContinuityReads();
  vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail("bk-1", BOOK_TITLE));
  vi.mocked(chatsApi.listChats).mockResolvedValue([]);
  vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
});

describe("the pin control (DoD-12)", () => {
  it("DoD-12: the header pin control reads 'Collapse navigator' while the navigator is expanded", async () => {
    renderShell();

    const pin = await screen.findByRole("button", { name: "Collapse navigator" });
    // aria-pressed is the negation of navCollapsed: expanded -> true.
    expect(pin).toHaveAttribute("aria-pressed", "true");
  });

  it("DoD-12: activating it flips the accessible name and aria-pressed, and persists navCollapsed", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(await screen.findByRole("button", { name: "Collapse navigator" }));

    const collapsedPin = await screen.findByRole("button", { name: "Pin navigator open" });
    expect(collapsedPin).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("button", { name: "Collapse navigator" })).toBeNull();
    expect(readWorkspaceLayout().navCollapsed).toBe(true);
  });
});

describe("first-render rehydration (DoD-13)", () => {
  it("DoD-13: a layout record seeded before the render is honoured on the first render", async () => {
    // The shell state hydrates in its CONSTRUCTOR — seed before rendering, never after.
    writeWorkspaceLayout({ navCollapsed: true, chatWidth: 0.5 });

    renderShell();

    // The pin control renders in its collapsed state straight away.
    const pin = await screen.findByRole("button", { name: "Pin navigator open" });
    expect(pin).toHaveAttribute("aria-pressed", "false");

    // ...and the stored width is what the handle reports.
    expect(await findHandle()).toHaveAttribute("aria-valuenow", "50");
  });
});

describe("the resize handle (DoD-14)", () => {
  it("DoD-14: the shell renders a separator named 'Resize chat pane' with the contracted percent bounds", async () => {
    renderShell();

    const handle = await findHandle();
    expect(handle).toHaveAttribute("aria-valuemin", "15");
    expect(handle).toHaveAttribute("aria-valuemax", "60");
    expect(handle).toHaveAttribute("aria-valuenow", "35");
  });
});

describe("the keyboard resize path (DoD-15, DoD-16)", () => {
  it("DoD-15: ArrowLeft widens the pane, persists the width and drives the CSS custom property", async () => {
    const user = userEvent.setup();
    renderShell();

    const handle = await findHandle();
    handle.focus();
    await user.keyboard("{ArrowLeft}");

    // Left widens: the pane grows leftward from the right edge.
    await waitFor(() => expect(handle).toHaveAttribute("aria-valuenow", "37"));
    expect(readWorkspaceLayout().chatWidth).toBeCloseTo(0.37, 10);
    // The autorun is what puts the width on the document element.
    expect(chatWidthVar()).toBe("37vw");
  });

  it("DoD-16: the keyboard path clamps at the maximum — two ArrowLeft presses from 0.59 stop at 60", async () => {
    const user = userEvent.setup();
    // Seeded before the render: the state hydrates in its constructor.
    writeWorkspaceLayout({ navCollapsed: false, chatWidth: 0.59 });

    renderShell();

    const handle = await findHandle();
    expect(handle).toHaveAttribute("aria-valuenow", "59");

    handle.focus();
    await user.keyboard("{ArrowLeft}");
    await user.keyboard("{ArrowLeft}");

    await waitFor(() => expect(handle).toHaveAttribute("aria-valuenow", "60"));
    expect(readWorkspaceLayout().chatWidth).toBeCloseTo(0.6, 10);
  });
});

describe("unmount cleanup (DoD-17)", () => {
  it("DoD-17: unmounting the shell removes the --work-chat-width property from the document element", async () => {
    const view = renderShell();

    await findHandle();
    expect(chatWidthVar()).toBe("35vw");

    view.unmount();

    expect(chatWidthVar()).toBe("");
  });
});
