/**
 * Reordering the memos list — 026.memos / 011.memos-list-reorder,
 * DoD-1 · DoD-2 · DoD-3 · DoD-5 · DoD-6 · DoD-7 · DoD-8.
 *
 * DoD-4 (US-126.AC-1 — the drag GESTURE) is `[manual/live]` and has NO test here:
 * jsdom has no pointer-event pipeline `@dnd-kit`'s sensor can drive, the resolution
 * `frontend/tests/work/ChaptersPageReorder.test.tsx` already records. The gesture is
 * verified live; the persistence it funnels into is covered by DoD-1, which both
 * affordances share — which is exactly why DoD-1 asserts a SINGLE call carrying the
 * WHOLE id list rather than merely that the order changed.
 *
 * Deliberately a SEPARATE file from step 010's `MemosListPage.test.tsx`, which is
 * untouched and must keep passing unchanged.
 *
 * Bound to the frozen interface in status.md -> `## Skeleton` (026 step 011, plus
 * steps 009/010 for the api, DTO and row contracts consumed unchanged):
 *   type MemoMoveDirection = "up" | "down"
 *   class MemosListPageState { … reorderStatus; reorderError; pendingOrder;
 *                              get displayedWorkingMemos }
 *   moveMemo(state, bookId, memoId, direction, signal?): Promise<void>
 *   applyMemoOrder(state, bookId, memoIds, signal?): Promise<void>
 *   interface MemoOrderListProps { memos; reordering; renderMemo; onReorder; onMove }
 *   const MemoOrderList: observer component taking those props
 *   const MemosListPage: () => ReactElement          // observer, NO props, :bookId from the URL
 *   api/memos: reorderMemos(bookId, body: ReorderMemosRequest, signal?)
 *                                                 : Promise<{ items: MemoResponse[] }>
 *
 * THE ACCESSIBLE-NAME CONTRACT (frozen). Every name derives from `memoLabel(position)`
 * — the row's **1-based position in the list it is rendered in**, NEVER `memo.ordinal`
 * (ordinals carry gaps: archiving never renumbers). Step 010 froze the row's names and
 * step 011 continues the SAME convention, verb-first — there is not a second naming
 * scheme anywhere in the row:
 *   up arrow      role `button`  name `Move memo 1 up`
 *   down arrow    role `button`  name `Move memo 1 down`
 *   drag handle   role `button`  name `Drag memo 1 to reorder`
 *   reorder error role `alert`   name `Reorder error`   (LIST level, its own surface)
 * Queries are by ROLE AND ACCESSIBLE NAME ONLY — never a test id.
 *
 * Every expected value comes from the SPEC — the step file's Definition of done, its
 * "Interface intent", `011.context.md` and `context.md` — never from code:
 *   - DoD-1 (US-126.AC-2) an arrow moves that memo ONE position and persists the WHOLE
 *     id list in a SINGLE api call — the full ordered id list of the caller's
 *     non-archived memos, which is the only list backend step 004 accepts (a short
 *     list, a long one, a duplicate, an archived id or another author's id is a 400);
 *   - DoD-2 (US-126.AC-2) after success the list renders the SERVER's returned order,
 *     not the local computation — so the double answers with an order that DIFFERS
 *     from the clicked move's local result;
 *   - DoD-3 (US-126.AC-2) up is disabled on the first memo, down on the last, and each
 *     control names its memo;
 *   - DoD-5 (US-126.AC-2) the new order is applied OPTIMISTICALLY — it is on screen
 *     before the call resolves;
 *   - DoD-6 (UC-105 failure handling) a failed reorder ROLLS BACK to the server's order
 *     and surfaces an author-facing message; no partial order survives;
 *   - DoD-7 (US-128.AC-1) the submitted id list contains ONLY non-archived memos — also
 *     with the show-archived filter ON, since a view filter does not change what the
 *     working list is — and the archived section offers NO reorder control while the
 *     working rows DO carry theirs;
 *   - DoD-8 (UC-105) while a reorder is in flight the row's controls are disabled, so a
 *     second reorder cannot interleave into an order nobody chose.
 *
 * `../../src/api/memos` is mocked WHOLESALE in module-factory form, never `fetch`; the
 * double keeps a mutable server list so "the server's order" is a real round trip. For
 * DoD-5 / DoD-6 / DoD-8 the reorder double is a DEFERRED promise this spec resolves or
 * rejects, so the optimistic window and the rollback are both observable. `ApiError` is
 * the REAL class from `api/client`. `globals: false`: every primitive is imported.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import type { MemoResponse } from "../../src/types/memos";
import { ApiError } from "../../src/api/client";
import * as memosApi from "../../src/api/memos";
import { MemosListPage } from "../../src/work/pages/MemosListPage";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module — every export of step 009's frozen
// `api/memos`, so the page's namespace import finds a double for anything it reaches.
// Omitting one would leave it `undefined` and the page would fail for the wrong reason.
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

/* ----------------------------------------------------------------------- fixtures */

const BOOK_ID = "bk-1";

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
 * Three working memos and one archived one. The ordinals deliberately carry GAPS
 * (`context.md` -> "Ordinals": archiving leaves a gap and never renumbers), so a name
 * derived from `ordinal` would be wrong — BETA is ordinal 4 but working POSITION 2.
 * The archived row sits at ordinal 3, between two live ones, so a list built by
 * ordinal alone without the archived filter would visibly include it.
 */
const ALPHA = makeMemo("m-1", "Alpha memo", 1);
const BETA = makeMemo("m-2", "Beta memo", 4);
const GAMMA = makeMemo("m-3", "Gamma memo", 7);
const RETIRED = makeMemo("m-9", "Retired memo", 3, { archived: true });

const WORKING_BODIES = ["Alpha memo", "Beta memo", "Gamma memo"];

/* ------------------------------------------------------------------ server double */

/** The memos the server currently holds — archived rows included. */
let serverMemos: MemoResponse[] = [];

function seedServer(memos: MemoResponse[]): void {
  serverMemos = memos.map((memo) => ({ ...memo }));
}

/** The working rows the server would return, ordinal ascending. */
function serverWorking(): MemoResponse[] {
  return serverMemos
    .filter((memo) => !memo.archived)
    .sort((a, b) => a.ordinal - b.ordinal)
    .map((memo) => ({ ...memo }));
}

/**
 * Apply an order to the server's working rows, rewriting their ordinals `1..N` — what
 * backend step 004 does. Archived rows keep the ordinals they had.
 */
function applyServerOrder(memoIds: string[]): void {
  serverMemos = serverMemos.map((memo) => {
    const index = memoIds.indexOf(memo.id);
    return index === -1 ? memo : { ...memo, ordinal: index + 1 };
  });
}

/* --------------------------------------------------------------------- deferred */

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
}

/** A promise this spec settles by hand, so the in-flight window is observable. */
function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/* ------------------------------------------------------------------------ harness */

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
  await screen.findAllByRole("textbox", { name: "Memo 1 body" });
}

/** Every body field on screen, in render order, by value. */
function bodyValues(): string[] {
  return screen
    .getAllByRole("textbox")
    .map((field) => (field as HTMLTextAreaElement | HTMLInputElement).value);
}

/** One arrow control, by the frozen position-derived name. */
function arrow(position: number, direction: "up" | "down"): HTMLButtonElement {
  return screen.getByRole("button", {
    name: `Move memo ${position} ${direction}`,
  }) as HTMLButtonElement;
}

/** Every arrow control on screen, whichever memo and direction it names. */
function allArrows(): HTMLButtonElement[] {
  return screen.queryAllByRole("button", {
    name: /^Move memo \d+ (up|down)$/,
  }) as HTMLButtonElement[];
}

/** Every drag handle on screen. */
function allDragHandles(): HTMLElement[] {
  return screen.queryAllByRole("button", { name: /^Drag memo \d+ to reorder$/ });
}

function showArchivedToggle(): HTMLElement {
  const labelled = screen.queryAllByLabelText("Show archived");
  if (labelled.length > 0) {
    return labelled[0];
  }
  return screen.getByRole("button", { name: "Show archived" });
}

/** Lets an already-resolved promise chain settle before a "still only once" assertion. */
async function settle(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

/** The one write call the reorder path is allowed to make, and nothing else. */
function expectNoOtherMemoWrite(): void {
  expect(vi.mocked(memosApi.createMemo)).not.toHaveBeenCalled();
  expect(vi.mocked(memosApi.updateMemoBody)).not.toHaveBeenCalled();
  expect(vi.mocked(memosApi.activateMemo)).not.toHaveBeenCalled();
  expect(vi.mocked(memosApi.deactivateMemo)).not.toHaveBeenCalled();
  expect(vi.mocked(memosApi.archiveMemo)).not.toHaveBeenCalled();
  expect(vi.mocked(memosApi.restoreMemo)).not.toHaveBeenCalled();
}

beforeEach(() => {
  seedServer([ALPHA, BETA, GAMMA, RETIRED]);

  // `restoreMocks` wipes implementations between tests — re-arm the whole double.
  // The ONE load returns everything the author owns, archived rows included.
  vi.mocked(memosApi.listMemos).mockImplementation(async () => serverMemos.map((m) => ({ ...m })));

  // The default reorder: the server accepts the submitted sequence, rewrites the
  // working ordinals `1..N` and answers with the working rows only — the `{ items }`
  // envelope step 009 froze.
  vi.mocked(memosApi.reorderMemos).mockImplementation(async (_bookId, body) => {
    applyServerOrder(body.memo_ids);
    return { items: serverWorking() };
  });
});

/* ------------------------------------------------ DoD-1 (one persist, whole list) */

describe("moving a memo with an arrow control (DoD-1)", () => {
  it("DoD-1 (US-126.AC-2): moving a memo UP shifts it one position and persists the WHOLE id list in a SINGLE api call", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();
    expect(bodyValues()).toEqual(WORKING_BODIES);

    await user.click(arrow(2, "up"));

    await waitFor(() => expect(vi.mocked(memosApi.reorderMemos)).toHaveBeenCalled());
    await settle();

    // ONE call. Both affordances funnel into one persist path, so a component with a
    // second path — or a double submit — fails here even though the order would look
    // right on screen.
    expect(vi.mocked(memosApi.reorderMemos)).toHaveBeenCalledTimes(1);
    const [bookIdArg, bodyArg] = vi.mocked(memosApi.reorderMemos).mock.calls[0];
    expect(bookIdArg).toBe(BOOK_ID);
    // The WHOLE ordered id list, with BETA one position earlier — never a partial list
    // and never a single moved id.
    expect(bodyArg).toEqual({ memo_ids: ["m-2", "m-1", "m-3"] });

    // Complete: every working memo named exactly once, none dropped, none invented —
    // any other shape is a 400 from backend step 004.
    expect(bodyArg.memo_ids).toHaveLength(3);
    expect([...bodyArg.memo_ids].sort()).toEqual(["m-1", "m-2", "m-3"]);

    await waitFor(() => expect(bodyValues()).toEqual(["Beta memo", "Alpha memo", "Gamma memo"]));
    expectNoOtherMemoWrite();
  });

  it("DoD-1 (US-126.AC-2): moving a memo DOWN is the mirror image — one position later, one call, the whole list", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    await user.click(arrow(1, "down"));

    await waitFor(() => expect(vi.mocked(memosApi.reorderMemos)).toHaveBeenCalled());
    await settle();

    expect(vi.mocked(memosApi.reorderMemos)).toHaveBeenCalledTimes(1);
    const [bookIdArg, bodyArg] = vi.mocked(memosApi.reorderMemos).mock.calls[0];
    expect(bookIdArg).toBe(BOOK_ID);
    expect(bodyArg).toEqual({ memo_ids: ["m-2", "m-1", "m-3"] });

    await waitFor(() => expect(bodyValues()).toEqual(["Beta memo", "Alpha memo", "Gamma memo"]));
    expectNoOtherMemoWrite();
  });
});

/* ---------------------------------------------------- DoD-2 (the server's order) */

describe("after a successful reorder the list shows the SERVER's order (DoD-2)", () => {
  it("DoD-2 (US-126.AC-2): the page renders the order the server returned, not the local computation", async () => {
    const user = userEvent.setup();

    // The server settles on an order of its OWN — the exact reverse — which differs
    // from the clicked move's local result ["m-2", "m-1", "m-3"]. A page that renders
    // its optimistic computation instead of the server's answer fails here.
    const SERVER_ORDER = ["m-3", "m-2", "m-1"];
    vi.mocked(memosApi.reorderMemos).mockImplementation(async () => {
      applyServerOrder(SERVER_ORDER);
      return { items: serverWorking() };
    });

    renderPage();
    await awaitLoaded();
    expect(bodyValues()).toEqual(WORKING_BODIES);

    await user.click(arrow(2, "up"));

    await waitFor(() =>
      expect(bodyValues()).toEqual(["Gamma memo", "Beta memo", "Alpha memo"]),
    );
    // And it stays the server's — the optimistic sequence is not re-applied afterwards.
    await settle();
    expect(bodyValues()).toEqual(["Gamma memo", "Beta memo", "Alpha memo"]);
    // Nothing archived was lost because a reorder happened.
    await user.click(showArchivedToggle());
    expect(await screen.findByDisplayValue("Retired memo")).toBeInTheDocument();
  });
});

/* -------------------------------------------------------- DoD-3 (the two ends) */

describe("the ends of the working list (DoD-3)", () => {
  it("DoD-3 (US-126.AC-2): up is disabled on the FIRST memo, down on the LAST, and each control names its memo", async () => {
    renderPage();
    await awaitLoaded();

    // Each memo has its own pair, named for its 1-based position in the working list.
    expect(allArrows()).toHaveLength(6);
    expect(bodyValues()).toEqual(WORKING_BODIES);

    // The first memo cannot move up; it can still move down.
    expect(arrow(1, "up").disabled).toBe(true);
    expect(arrow(1, "down").disabled).toBe(false);

    // The last memo cannot move down; it can still move up.
    expect(arrow(3, "down").disabled).toBe(true);
    expect(arrow(3, "up").disabled).toBe(false);

    // The middle memo offers both, so the two negatives above are not vacuous.
    expect(arrow(2, "up").disabled).toBe(false);
    expect(arrow(2, "down").disabled).toBe(false);
  });

  it("DoD-3 (US-126.AC-2): a one-memo working list offers NEITHER direction", async () => {
    seedServer([ALPHA, RETIRED]);
    renderPage();
    await awaitLoaded();

    expect(bodyValues()).toEqual(["Alpha memo"]);
    expect(arrow(1, "up").disabled).toBe(true);
    expect(arrow(1, "down").disabled).toBe(true);
  });
});

/* ------------------------------------------------------- DoD-5 (the optimism) */

describe("the new order is applied optimistically (DoD-5)", () => {
  it("DoD-5 (US-126.AC-2): the list reorders BEFORE the call resolves, and then settles on the server's answer", async () => {
    const user = userEvent.setup();
    const pending = deferred<{ items: MemoResponse[] }>();
    vi.mocked(memosApi.reorderMemos).mockReturnValue(pending.promise);

    renderPage();
    await awaitLoaded();
    expect(bodyValues()).toEqual(WORKING_BODIES);

    await user.click(arrow(3, "up"));

    // Unresolved — and the moved order is already on screen.
    await waitFor(() => expect(bodyValues()).toEqual(["Alpha memo", "Gamma memo", "Beta memo"]));
    expect(vi.mocked(memosApi.reorderMemos)).toHaveBeenCalledTimes(1);
    // No failure is reported for a call that has not answered.
    expect(screen.queryByRole("alert", { name: "Reorder error" })).toBeNull();

    // Now the server answers, and the list is re-seeded from what it returned.
    applyServerOrder(["m-1", "m-3", "m-2"]);
    pending.resolve({ items: serverWorking() });

    await waitFor(() => expect(bodyValues()).toEqual(["Alpha memo", "Gamma memo", "Beta memo"]));
    expect(screen.queryByRole("alert", { name: "Reorder error" })).toBeNull();
  });
});

/* --------------------------------------------------------- DoD-6 (the rollback) */

describe("a refused reorder rolls back to server truth (DoD-6)", () => {
  it("DoD-6 (UC-105 failure handling): the order snaps back to the server's, an author-facing message is surfaced, and no partial order survives", async () => {
    const user = userEvent.setup();
    const REFUSAL = "That memo order could not be saved.";
    const pending = deferred<{ items: MemoResponse[] }>();
    vi.mocked(memosApi.reorderMemos).mockReturnValue(pending.promise);

    renderPage();
    await awaitLoaded();
    expect(bodyValues()).toEqual(WORKING_BODIES);

    await user.click(arrow(1, "down"));
    // The attempt is on screen while it is in flight...
    await waitFor(() => expect(bodyValues()).toEqual(["Beta memo", "Alpha memo", "Gamma memo"]));

    pending.reject(new ApiError(400, REFUSAL));

    // ...the refusal reaches the author on the list-level surface...
    const alert = await screen.findByRole("alert", { name: "Reorder error" });
    expect(alert).toHaveTextContent(REFUSAL);

    // ...and the order returns to the server's, whole: no partial order survives, and
    // no memo was lost or duplicated on the way back.
    await waitFor(() => expect(bodyValues()).toEqual(WORKING_BODIES));
    await settle();
    expect(bodyValues()).toEqual(WORKING_BODIES);

    // The failure belongs to the list, not to a row.
    expect(screen.queryByLabelText("Memo 1 error")).toBeNull();
    expect(screen.queryByLabelText("Memo 2 error")).toBeNull();
    expect(screen.queryByLabelText("Memo 3 error")).toBeNull();
    // The list is still usable afterwards: the controls came back.
    await waitFor(() => expect(arrow(2, "up").disabled).toBe(false));
  });
});

/* ------------------------------------- DoD-7 (only the working list, only its ids) */

describe("the archived memos are outside the reorder (DoD-7)", () => {
  it("DoD-7 (US-128.AC-1): the working rows carry reorder controls and the archived rows carry NONE", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    // The positive half, which makes the negative half mean something: every working
    // row has its own pair of arrows and its own drag handle.
    expect(bodyValues()).toEqual(WORKING_BODIES);
    expect(allArrows()).toHaveLength(6);
    expect(allDragHandles()).toHaveLength(3);
    for (const position of [1, 2, 3]) {
      expect(arrow(position, "up")).toBeInTheDocument();
      expect(arrow(position, "down")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: `Drag memo ${position} to reorder` }),
      ).toBeInTheDocument();
    }

    // Now reveal the archived section — a fourth row appears on screen...
    await user.click(showArchivedToggle());
    expect(await screen.findByDisplayValue("Retired memo")).toBeInTheDocument();
    expect(screen.queryAllByRole("button", { name: /^Restore memo \d+$/ })).toHaveLength(1);
    // Four rows on screen now — the three working ones and the archived one. Their
    // relative placement is the page's business; the count is what matters here.
    expect(bodyValues()).toHaveLength(4);
    expect([...bodyValues()].sort()).toEqual([...WORKING_BODIES, "Retired memo"].sort());

    // ...and it brought no reorder affordance with it: the counts are unchanged, so
    // exactly the three working rows are reorderable.
    expect(allArrows()).toHaveLength(6);
    expect(allDragHandles()).toHaveLength(3);
  });

  it("DoD-7 (US-128.AC-1): with the show-archived filter ON the submitted id list is still the non-archived memos alone", async () => {
    const user = userEvent.setup();
    renderPage();
    await awaitLoaded();

    await user.click(showArchivedToggle());
    expect(await screen.findByDisplayValue("Retired memo")).toBeInTheDocument();

    await user.click(arrow(2, "up"));

    await waitFor(() => expect(vi.mocked(memosApi.reorderMemos)).toHaveBeenCalled());
    await settle();
    expect(vi.mocked(memosApi.reorderMemos)).toHaveBeenCalledTimes(1);
    const [, bodyArg] = vi.mocked(memosApi.reorderMemos).mock.calls[0];
    // A view filter is not a list: the archived memo's id never goes over the wire,
    // and the list is still exactly the caller's non-archived set.
    expect(bodyArg).toEqual({ memo_ids: ["m-2", "m-1", "m-3"] });
    expect(bodyArg.memo_ids).not.toContain("m-9");
  });
});

/* ------------------------------------------------------- DoD-8 (no interleaving) */

describe("a reorder in flight (DoD-8)", () => {
  it("DoD-8 (UC-105): the row's controls are disabled while a reorder is in flight, so a second reorder cannot interleave", async () => {
    const user = userEvent.setup();
    const pending = deferred<{ items: MemoResponse[] }>();
    vi.mocked(memosApi.reorderMemos).mockReturnValue(pending.promise);

    renderPage();
    await awaitLoaded();
    // Before the click these are live controls — so "disabled" below is a change.
    expect(arrow(2, "up").disabled).toBe(false);
    expect(arrow(2, "down").disabled).toBe(false);

    await user.click(arrow(1, "down"));

    // Every arrow is disabled while the call is unanswered, the ends included.
    await waitFor(() => {
      const controls = allArrows();
      expect(controls).toHaveLength(6);
      for (const control of controls) {
        expect(control.disabled).toBe(true);
      }
    });

    // A second move clicked anyway gets nowhere: no order nobody chose is submitted.
    fireEvent.click(arrow(3, "up"));
    await settle();
    expect(vi.mocked(memosApi.reorderMemos)).toHaveBeenCalledTimes(1);

    // Once the server answers, the controls are live again.
    applyServerOrder(["m-2", "m-1", "m-3"]);
    pending.resolve({ items: serverWorking() });
    await waitFor(() => expect(arrow(2, "up").disabled).toBe(false));
  });
});
