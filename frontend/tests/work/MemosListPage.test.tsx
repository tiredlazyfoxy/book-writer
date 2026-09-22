/**
 * The memos list page — 026.memos / 010.memos-list-page, DoD-1 … DoD-16
 * (all sixteen are `[test]`; the step has no `[manual/live]` item).
 *
 * Bound to the frozen interface in status.md -> `## Skeleton` (026 step 010), plus
 * step 009's DTOs and api module:
 *   const MemosListPage: () => ReactElement              // observer, NO props, bookId from useParams
 *   class MemosListPageState { memos; memosStatus; memosError; showArchived; bodyDrafts;
 *                              focusMemoId; actionStatus; actionError;
 *                              get workingMemos; get archivedMemos; get displayedBodies; get isEmpty }
 *   loadMemos / createMemo / saveMemoBody / setMemoActive / archiveMemo / restoreMemo
 *                                                        // (state, bookId, …, signal?)
 *   memoLabel(position: number): string                  // `Memo ${position}`
 *   interface MemoRowProps { memo; position; body; busy; error; autoFocus;
 *                            onBodyChange; onSaveBody; onSetActive;
 *                            onArchive?; onRestore?; onBodyFocus? }
 *   api/memos: listMemos(bookId, includeArchived, signal?) · createMemo(bookId, body, signal?)
 *              updateMemoBody(bookId, memoId, body, signal?) · reorderMemos(bookId, body, signal?)
 *              activateMemo / deactivateMemo / archiveMemo / restoreMemo (bookId, memoId, signal?)
 *   interface MemoResponse { id; book_id; body; ordinal; active; archived;
 *                            created_at; modified_at }   // and NO user_id
 *
 * THE ACCESSIBLE-NAME CONTRACT (frozen with the interface — the only handle a spec has
 * on an icon control, since a memo has no title and `""` is a legitimate body). Every
 * name derives from `memoLabel(position)`, where `position` is the row's **1-based index
 * in the list it is rendered in** — NOT `memo.ordinal`, which carries gaps. The working
 * list and the archived section each number from 1:
 *   body field      role `textbox`  name `Memo 1 body`
 *   on/off control  role `switch`   name `Memo 1 active`, `checked` = `memo.active`
 *                                   (so OFF is reported as aria-checked="false")
 *   off marker      aria-label      `Memo 1 is off`
 *   archive control role `button`   name `Archive memo 1`   (working rows only)
 *   restore control role `button`   name `Restore memo 1`   (archived section only)
 *   row error       role `alert`    name `Memo 1 error`, text = the message
 * Page level: heading `Memos`, create control `New memo`, toggle `Show archived`.
 * The name is STABLE across a toggle, so a row is addressable before and after.
 * Queries are by ROLE AND ACCESSIBLE NAME ONLY — never a test id (`context.md` ->
 * "Testing facts shared by every step").
 *
 * Every expected value comes from the SPEC — the step file's Definition of done, its
 * "Interface intent", `010.context.md` and `context.md` decisions 12/13 — never from code:
 *   - DoD-1  (US-123.AC-1) creating a memo adds it LAST in the working list;
 *   - DoD-2  (US-123.AC-2) the new memo's body field takes focus IMMEDIATELY;
 *   - DoD-3  (US-123.AC-3) the new memo renders ACTIVE;
 *   - DoD-4  (UC-103 postcondition) the new memo is EMPTY and immediately typeable, and an
 *            empty body is NEVER reported as an error;
 *   - DoD-5  (US-125.AC-1) typing then MOVING FOCUS AWAY saves, and the row then shows what
 *            the SERVER returned; a draft identical to the server's value saves nothing;
 *   - DoD-6  (US-125.AC-2) NO save control exists — idle, mid-edit, or with a dirty draft;
 *   - DoD-7  (US-127.AC-1) switching a memo off leaves it IN the list;
 *   - DoD-8  (US-127.AC-2) an off memo is visibly marked off through role/name, not styling;
 *   - DoD-9  (US-127.AC-4) switching back on returns it to the on state;
 *   - DoD-10 (US-127.AC-5) switching off the ONLY active memo succeeds — nothing refuses and
 *            nothing is restored behind the author's back;
 *   - DoD-11 (US-128.AC-1) archiving removes the row from the working list;
 *   - DoD-12 (US-128.AC-2) revealing the archived memos and restoring one returns it to the
 *            working list, LAST;
 *   - DoD-13 (US-128.AC-3) each row offers archive and there is NO delete control at all;
 *   - DoD-14 (UC-107 step 3) the show-archived toggle is a PURE CLIENT-SIDE filter: one fetch,
 *            include-archived ON, and toggling refetches nothing;
 *   - DoD-15 (US-124.AC-1) the page sends NO user id — the only identity is the book in the URL;
 *   - DoD-16 (UC-104 exception handling) a failed save or toggle surfaces an author-facing
 *            message AGAINST THAT ROW, and the row falls back to SERVER TRUTH.
 *
 * Harness: the page is mounted under its own `/:bookId/memos` route (the `ChatsListPage`
 * precedent) so nothing but the page under test is on screen; routes are basename-stripped
 * (`/bk-1/memos`, never `/work/bk-1/memos`). `../../src/api/memos` is mocked WHOLESALE in
 * module-factory form, never `fetch`; the double keeps a mutable server list so "what the
 * server returned" is a real round trip. `ApiError` is the REAL class from `api/client`.
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import type { MemoResponse } from "../../src/types/memos";
import { ApiError } from "../../src/api/client";
import * as memosApi from "../../src/api/memos";
import { MemosListPage } from "../../src/work/pages/MemosListPage";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module — every export of step 009's frozen
// `api/memos`, so the page's namespace import finds a double for anything it reaches.
vi.mock("../../src/api/memos", () => ({
  listMemos: vi.fn(),
  createMemo: vi.fn(),
  updateMemoBody: vi.fn(),
  reorderMemos: vi.fn(),
  activateMemo: vi.fn(),
  deactivateMemo: vi.fn(),
  archiveMemo: vi.fn(),
  restoreMemo: vi.fn(),
}));

const BOOK_ID = "bk-1";

/** The server's normalisation, visible to a spec: proves the row shows the SERVER's value. */
const SERVER_SUFFIX = " [server]";

function makeMemo(
  id: string,
  body: string,
  ordinal: number,
  overrides: Partial<MemoResponse> = {},
): MemoResponse {
  return {
    id,
    book_id: BOOK_ID,
    body,
    ordinal,
    active: true,
    archived: false,
    created_at: "2026-09-01T00:00:00Z",
    modified_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

/**
 * Ordinals deliberately carry a GAP (archiving never renumbers — `context.md` decision 2),
 * so BETA sits at ordinal 4 while being working-list POSITION 2. A name derived from the
 * ordinal would therefore be wrong; the frozen scheme derives it from the position.
 */
const ALPHA = makeMemo("m-1", "Alpha memo", 1);
const BETA = makeMemo("m-2", "Beta memo", 4);
const RETIRED = makeMemo("m-9", "Retired memo", 3, { archived: true });

/** The double's mutable server state; every verb reads and writes it. */
let serverMemos: MemoResponse[] = [];

function seedServer(memos: MemoResponse[]): void {
  serverMemos = memos.map((memo) => ({ ...memo }));
}

function nextOrdinal(): number {
  return serverMemos.reduce((max, memo) => Math.max(max, memo.ordinal), 0) + 1;
}

function replaceRow(updated: MemoResponse): MemoResponse {
  serverMemos = serverMemos.map((memo) => (memo.id === updated.id ? updated : memo));
  return updated;
}

function serverRow(memoId: string): MemoResponse {
  const found = serverMemos.find((memo) => memo.id === memoId);
  if (found === undefined) {
    throw new Error(`test double: no memo ${memoId}`);
  }
  return found;
}

/** Mount the page under its own route, the way the work shell mounts it. */
function renderPage(): void {
  renderWithProviders(
    <Routes>
      <Route path="/:bookId/memos" element={<MemosListPage />} />
    </Routes>,
    { route: `/${BOOK_ID}/memos` },
  );
}

/** Wait for the loaded list: the first working row's body field. */
async function awaitLoaded(): Promise<void> {
  await screen.findByRole("textbox", { name: "Memo 1 body" });
}

/** Every body field on screen, in render order, by value. */
function bodyValues(): string[] {
  return screen
    .getAllByRole("textbox")
    .map((field) => (field as HTMLTextAreaElement | HTMLInputElement).value);
}

/**
 * The show-archived toggle by its frozen accessible name. The clause is about the FILTER's
 * behaviour, not the widget kind, so a labelled control (switch / checkbox) and a named
 * button are both accepted — the name `Show archived` is what is frozen.
 */
function showArchivedToggle(): HTMLElement {
  const labelled = screen.queryAllByLabelText("Show archived");
  if (labelled.length > 0) {
    return labelled[0];
  }
  return screen.getByRole("button", { name: "Show archived" });
}

beforeEach(() => {
  seedServer([ALPHA, BETA, RETIRED]);

  // `restoreMocks` wipes implementations between tests — re-arm the whole server double.
  // The ONE load returns everything the author owns, archived rows included.
  vi.mocked(memosApi.listMemos).mockImplementation(async () => serverMemos.map((m) => ({ ...m })));

  // Create appends an EMPTY memo with the next ordinal, and hands it back FIRST in nothing:
  // the page must place it last by ordinal, not by arrival.
  vi.mocked(memosApi.createMemo).mockImplementation(async (_bookId, body) => {
    const created = makeMemo(`m-new-${serverMemos.length + 1}`, body.body, nextOrdinal());
    serverMemos = [created, ...serverMemos];
    return { ...created };
  });

  // The server normalises the body it stores, so "the row shows what the server returned"
  // is observable rather than indistinguishable from the local draft.
  vi.mocked(memosApi.updateMemoBody).mockImplementation(async (_bookId, memoId, body) =>
    replaceRow({ ...serverRow(memoId), body: `${body.body}${SERVER_SUFFIX}` }),
  );

  vi.mocked(memosApi.activateMemo).mockImplementation(async (_bookId, memoId) =>
    replaceRow({ ...serverRow(memoId), active: true }),
  );
  vi.mocked(memosApi.deactivateMemo).mockImplementation(async (_bookId, memoId) =>
    replaceRow({ ...serverRow(memoId), active: false }),
  );
  vi.mocked(memosApi.archiveMemo).mockImplementation(async (_bookId, memoId) =>
    replaceRow({ ...serverRow(memoId), archived: true }),
  );
  // Restore APPENDS: the row comes back with a fresh, highest ordinal (`context.md` -> "Ordinals").
  vi.mocked(memosApi.restoreMemo).mockImplementation(async (_bookId, memoId) =>
    replaceRow({ ...serverRow(memoId), archived: false, ordinal: nextOrdinal() }),
  );
});

/* ------------------------------------------------------------------ create: DoD-1..DoD-4 */

describe("creating a memo (DoD-1, DoD-2, DoD-3, DoD-4)", () => {
  it("DoD-1 (US-123.AC-1): the created memo is added LAST in the working list", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();
    expect(bodyValues()).toEqual(["Alpha memo", "Beta memo"]);

    await user.click(screen.getByRole("button", { name: "New memo" }));

    // Last in the working list — third position, after the two existing rows.
    expect(await screen.findByRole("textbox", { name: "Memo 3 body" })).toBeInTheDocument();
    expect(bodyValues()).toEqual(["Alpha memo", "Beta memo", ""]);
    // It is the row the SERVER returned: exactly one create call, for this book.
    expect(vi.mocked(memosApi.createMemo)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(memosApi.createMemo).mock.calls[0][0]).toBe(BOOK_ID);
  });

  it("DoD-2 (US-123.AC-2): the new memo's body field receives focus immediately, with no further author action", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    await user.click(screen.getByRole("button", { name: "New memo" }));

    const created = await screen.findByRole("textbox", { name: "Memo 3 body" });
    expect(created).toHaveFocus();
  });

  it("DoD-3 (US-123.AC-3): the new memo renders as active", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    await user.click(screen.getByRole("button", { name: "New memo" }));
    await screen.findByRole("textbox", { name: "Memo 3 body" });

    expect(screen.getByRole("switch", { name: "Memo 3 active" })).toBeChecked();
    // The on state is the on state: no off marker against the new row.
    expect(screen.queryByLabelText("Memo 3 is off")).toBeNull();
  });

  it("DoD-4 (UC-103 postcondition): the new memo is empty and immediately typeable, and an empty body is never an error", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    await user.click(screen.getByRole("button", { name: "New memo" }));
    const created = (await screen.findByRole("textbox", {
      name: "Memo 3 body",
    })) as HTMLTextAreaElement;

    // Empty — and the row is addressable anyway: the naming scheme is body-independent.
    expect(created.value).toBe("");
    // An empty body is a legitimate state, never reported as a failure.
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByLabelText("Memo 3 error")).toBeNull();
    // The create request carried the empty body and nothing else.
    expect(vi.mocked(memosApi.createMemo).mock.calls[0][1]).toEqual({ body: "" });

    // Immediately typeable, with no intervening click.
    await user.keyboard("Fresh thought");
    expect((screen.getByRole("textbox", { name: "Memo 3 body" }) as HTMLTextAreaElement).value).toBe(
      "Fresh thought",
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

/* --------------------------------------------------- blur-save and no save control: 5, 6 */

describe("editing a memo (DoD-5, DoD-6)", () => {
  it("DoD-5 (US-125.AC-1): moving focus away saves the edited body and the row then shows what the server returned", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    const field = screen.getByRole("textbox", { name: "Memo 1 body" });
    await user.clear(field);
    await user.type(field, "Edited body");
    // Not yet saved: the write happens on focus loss, not on a keystroke.
    expect(vi.mocked(memosApi.updateMemoBody)).not.toHaveBeenCalled();

    await user.tab();

    await screen.findByDisplayValue(`Edited body${SERVER_SUFFIX}`);
    expect(vi.mocked(memosApi.updateMemoBody)).toHaveBeenCalledTimes(1);
    const call = vi.mocked(memosApi.updateMemoBody).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe("m-1");
    // The focus-loss PUT carries the body and nothing else.
    expect(call[2]).toEqual({ body: "Edited body" });
    // Server truth on screen, not the local draft.
    expect(bodyValues()).toEqual([`Edited body${SERVER_SUFFIX}`, "Beta memo"]);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("DoD-5 (US-125.AC-1): a draft identical to the server's value saves nothing", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    // Dirty, then reverted by hand: the displayed body equals the server's again.
    const field = screen.getByRole("textbox", { name: "Memo 2 body" });
    await user.click(field);
    await user.type(field, "!");
    await user.keyboard("{Backspace}");
    expect((field as HTMLTextAreaElement).value).toBe("Beta memo");

    await user.tab();

    expect(vi.mocked(memosApi.updateMemoBody)).not.toHaveBeenCalled();
  });

  it("DoD-6 (US-125.AC-2): no save control exists — not idle, not mid-edit, not with a dirty draft", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    // Non-vacuous: the list really is on screen, so "no save control" is a finding, not an
    // artefact of an empty render.
    expect(bodyValues()).toEqual(["Alpha memo", "Beta memo"]);
    expect(screen.queryAllByRole("button", { name: /save/i })).toHaveLength(0);

    // Mid-edit: the field is focused.
    const field = screen.getByRole("textbox", { name: "Memo 1 body" });
    await user.click(field);
    expect(field).toHaveFocus();
    expect(screen.queryAllByRole("button", { name: /save/i })).toHaveLength(0);

    // Dirty: an unsaved draft differs from the server's value.
    await user.type(field, " and more");
    expect((field as HTMLTextAreaElement).value).toBe("Alpha memo and more");
    expect(screen.queryAllByRole("button", { name: /save/i })).toHaveLength(0);

    // And with the archived section revealed, where a second row shape is on screen.
    await user.click(showArchivedToggle());
    expect(await screen.findByDisplayValue("Retired memo")).toBeInTheDocument();
    expect(screen.queryAllByRole("button", { name: /save/i })).toHaveLength(0);
  });
});

/* ----------------------------------------------------- the on/off axis: DoD-7, 8, 9, 10 */

describe("the on/off switch (DoD-7, DoD-8, DoD-9, DoD-10)", () => {
  it("DoD-7 (US-127.AC-1): switching a memo off leaves it in the list", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    await user.click(screen.getByRole("switch", { name: "Memo 1 active" }));

    const call = vi.mocked(memosApi.deactivateMemo).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe("m-1");
    // Still in the working list, in place: off is not removal.
    expect(await screen.findByRole("textbox", { name: "Memo 1 body" })).toBeInTheDocument();
    expect(bodyValues()).toEqual(["Alpha memo", "Beta memo"]);
  });

  it("DoD-8 (US-127.AC-2): a switched-off memo is marked off through role and name, not styling alone", async () => {
    // BETA arrives already off, so the marking is asserted on a loaded row too.
    seedServer([ALPHA, { ...BETA, active: false }, RETIRED]);
    renderPage();
    await awaitLoaded();

    // The off state travels on the control's own checked state (role `switch`, accessible
    // name `Memo 2 active`) and on a named marker — never on styling alone.
    const off = screen.getByRole("switch", { name: "Memo 2 active" });
    expect(off).not.toBeChecked();
    expect(screen.getByLabelText("Memo 2 is off")).toBeInTheDocument();

    // The active row is unmarked, so the marker means something.
    expect(screen.getByRole("switch", { name: "Memo 1 active" })).toBeChecked();
    expect(screen.queryByLabelText("Memo 1 is off")).toBeNull();
  });

  it("DoD-9 (US-127.AC-4): switching it back on returns it to the on state", async () => {
    const user = userEvent.setup();
    seedServer([ALPHA, { ...BETA, active: false }, RETIRED]);
    renderPage();
    await awaitLoaded();
    expect(screen.getByRole("switch", { name: "Memo 2 active" })).not.toBeChecked();

    // The name is stable across the axis, so the same handle addresses the row.
    await user.click(screen.getByRole("switch", { name: "Memo 2 active" }));

    expect(vi.mocked(memosApi.activateMemo).mock.calls[0][1]).toBe("m-2");
    await screen.findByLabelText("Memo 2 active");
    expect(screen.getByRole("switch", { name: "Memo 2 active" })).toBeChecked();
    expect(screen.queryByLabelText("Memo 2 is off")).toBeNull();
  });

  it("DoD-10 (US-127.AC-5): switching off the ONLY active memo succeeds — nothing refuses, nothing is restored behind the author's back", async () => {
    const user = userEvent.setup();
    // Exactly one active memo in the whole set.
    seedServer([ALPHA, { ...BETA, active: false }, { ...RETIRED, active: false }]);
    renderPage();
    await awaitLoaded();

    await user.click(screen.getByRole("switch", { name: "Memo 1 active" }));

    const switched = await screen.findByRole("switch", { name: "Memo 1 active" });
    expect(switched).not.toBeChecked();
    expect(screen.getByLabelText("Memo 1 is off")).toBeInTheDocument();
    // No active memo remains, and the page says so with no complaint.
    expect(screen.getByRole("switch", { name: "Memo 2 active" })).not.toBeChecked();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByLabelText("Memo 1 error")).toBeNull();
    // Nothing was switched back on behind the author.
    expect(vi.mocked(memosApi.activateMemo)).not.toHaveBeenCalled();
    // And the row stayed in the list.
    expect(bodyValues()).toEqual(["Alpha memo", "Beta memo"]);
  });
});

/* -------------------------------------------- archive, restore and no delete: 11, 12, 13 */

describe("the archive axis (DoD-11, DoD-12, DoD-13)", () => {
  it("DoD-11 (US-128.AC-1): archiving a memo removes it from the working list", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    await user.click(screen.getByRole("button", { name: "Archive memo 1" }));

    const call = vi.mocked(memosApi.archiveMemo).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe("m-1");
    // Gone from the working list; the survivor renumbers to position 1.
    await screen.findByRole("textbox", { name: "Memo 1 body" });
    expect(bodyValues()).toEqual(["Beta memo"]);
    expect(screen.queryByDisplayValue("Alpha memo")).toBeNull();
  });

  it("DoD-12 (US-128.AC-2): revealing the archived memos and restoring one returns it to the working list, last", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();
    // Hidden by default.
    expect(screen.queryByDisplayValue("Retired memo")).toBeNull();

    await user.click(showArchivedToggle());

    // Revealed, in the archived section — which numbers from 1 in its own right, so the
    // archived row's restore control is `Restore memo 1`.
    expect(await screen.findByDisplayValue("Retired memo")).toBeInTheDocument();
    const restore = screen.getByRole("button", { name: "Restore memo 1" });

    await user.click(restore);

    const call = vi.mocked(memosApi.restoreMemo).mock.calls[0];
    expect(call[0]).toBe(BOOK_ID);
    expect(call[1]).toBe("m-9");
    // Back in the working list, LAST — and no longer an archived row.
    await screen.findByRole("button", { name: "Archive memo 3" });
    expect(bodyValues()).toEqual(["Alpha memo", "Beta memo", "Retired memo"]);
    expect(screen.queryAllByRole("button", { name: /^Restore memo/ })).toHaveLength(0);
  });

  it("DoD-13 (US-128.AC-3): every row offers archive, and there is no delete control in the list at all", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    // Archive, on each working row.
    expect(screen.getByRole("button", { name: "Archive memo 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Archive memo 2" })).toBeInTheDocument();
    // Non-vacuous: the rows really are rendered.
    expect(bodyValues()).toEqual(["Alpha memo", "Beta memo"]);
    // No delete, anywhere.
    expect(screen.queryAllByRole("button", { name: /delete|remove|trash|discard/i })).toHaveLength(
      0,
    );

    // Nor in the archived section.
    await user.click(showArchivedToggle());
    expect(await screen.findByDisplayValue("Retired memo")).toBeInTheDocument();
    expect(screen.queryAllByRole("button", { name: /delete|remove|trash|discard/i })).toHaveLength(
      0,
    );
  });
});

/* ------------------------------------------- the client-side filter and identity: 14, 15 */

describe("the show-archived filter and the request's identity (DoD-14, DoD-15)", () => {
  it("DoD-14 (UC-107 step 3): the list is fetched ONCE with archived memos included, and toggling refetches nothing", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    // One load, include-archived ON.
    expect(vi.mocked(memosApi.listMemos)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(memosApi.listMemos).mock.calls[0][0]).toBe(BOOK_ID);
    expect(vi.mocked(memosApi.listMemos).mock.calls[0][1]).toBe(true);
    // ...yet the archived memo is filtered out client-side by default.
    expect(bodyValues()).toEqual(["Alpha memo", "Beta memo"]);

    await user.click(showArchivedToggle());
    expect(await screen.findByDisplayValue("Retired memo")).toBeInTheDocument();
    expect(vi.mocked(memosApi.listMemos)).toHaveBeenCalledTimes(1);

    await user.click(showArchivedToggle());
    expect(bodyValues()).toEqual(["Alpha memo", "Beta memo"]);
    expect(vi.mocked(memosApi.listMemos)).toHaveBeenCalledTimes(1);
  });

  it("DoD-15 (US-124.AC-1): the page sends no user id — the only identity in every call is the book from the URL", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    // The list call: book id, the include-archived flag, and at most an AbortSignal.
    const listCall = vi.mocked(memosApi.listMemos).mock.calls[0];
    expect(listCall.length).toBeLessThanOrEqual(3);
    expect(listCall[0]).toBe(BOOK_ID);
    expect(typeof listCall[1]).toBe("boolean");
    expect(listCall[2] === undefined || listCall[2] instanceof AbortSignal).toBe(true);

    // A write carries no author either: book id, memo id, and a body-only payload.
    const field = screen.getByRole("textbox", { name: "Memo 1 body" });
    await user.clear(field);
    await user.type(field, "Edited body");
    await user.tab();
    await screen.findByDisplayValue(`Edited body${SERVER_SUFFIX}`);

    const updateCall = vi.mocked(memosApi.updateMemoBody).mock.calls[0];
    expect(updateCall[0]).toBe(BOOK_ID);
    expect(updateCall[1]).toBe("m-1");
    expect(Object.keys(updateCall[2])).toEqual(["body"]);

    // Create likewise: the payload is the body alone, with no author field.
    await user.click(screen.getByRole("button", { name: "New memo" }));
    await screen.findByRole("textbox", { name: "Memo 3 body" });
    const createCall = vi.mocked(memosApi.createMemo).mock.calls[0];
    expect(createCall[0]).toBe(BOOK_ID);
    expect(Object.keys(createCall[1])).toEqual(["body"]);

    // And a state verb: book id, memo id, nothing else that could name a user.
    await user.click(screen.getByRole("switch", { name: "Memo 1 active" }));
    const deactivateCall = vi.mocked(memosApi.deactivateMemo).mock.calls[0];
    expect(deactivateCall.length).toBeLessThanOrEqual(3);
    expect(deactivateCall[0]).toBe(BOOK_ID);
    expect(deactivateCall[1]).toBe("m-1");
    expect(deactivateCall[2] === undefined || deactivateCall[2] instanceof AbortSignal).toBe(true);
  });
});

/* --------------------------------------------------------- failure against the row: 16 */

describe("a failed write is reported against its row, and the row shows server truth (DoD-16)", () => {
  it("DoD-16 (UC-104): a failed save surfaces the message against that row and the field falls back to the server's value", async () => {
    const user = userEvent.setup();
    const refusal = "Memos are unavailable right now.";
    vi.mocked(memosApi.updateMemoBody).mockRejectedValue(new ApiError(500, refusal));
    renderPage();
    await awaitLoaded();

    const field = screen.getByRole("textbox", { name: "Memo 1 body" });
    await user.clear(field);
    await user.type(field, "Never saved");
    await user.tab();

    // The message is author-facing and belongs to THIS row.
    const alert = await screen.findByRole("alert", { name: "Memo 1 error" });
    expect(alert).toHaveTextContent(refusal);
    // ...and no other row is blamed.
    expect(screen.queryByLabelText("Memo 2 error")).toBeNull();
    // Server truth on screen: the unsaved optimistic value is dropped.
    expect(bodyValues()).toEqual(["Alpha memo", "Beta memo"]);
    // The list survives the failure.
    expect(screen.getByRole("textbox", { name: "Memo 2 body" })).toBeInTheDocument();
  });

  it("DoD-16 (UC-104): a failed toggle surfaces the message against that row and the switch shows the server's state", async () => {
    const user = userEvent.setup();
    const refusal = "That memo could not be switched off.";
    vi.mocked(memosApi.deactivateMemo).mockRejectedValue(new ApiError(403, refusal));
    renderPage();
    await awaitLoaded();

    await user.click(screen.getByRole("switch", { name: "Memo 1 active" }));

    const alert = await screen.findByRole("alert", { name: "Memo 1 error" });
    expect(alert).toHaveTextContent(refusal);
    expect(screen.queryByLabelText("Memo 2 error")).toBeNull();
    // Server truth: the memo is still on, and not marked off.
    expect(screen.getByRole("switch", { name: "Memo 1 active" })).toBeChecked();
    expect(screen.queryByLabelText("Memo 1 is off")).toBeNull();
    // The list is intact.
    expect(bodyValues()).toEqual(["Alpha memo", "Beta memo"]);
  });
});
