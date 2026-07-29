/**
 * Codex list pages (Characters / Locations / Facts) — 013.codex / 011.codex-api-list-pages,
 * DoD-1 … DoD-10 (all ten are `[test]`; the step has no `[manual/live]` item).
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 011):
 *   type CodexKind = "character" | "location" | "fact"
 *   interface CodexEntryResponse { id; book_id; kind; name; body; archived; author_id;
 *                                  modified_by; created_at; modified_at }
 *   interface CreateCodexEntryRequest { kind; name?; body }
 *   interface UpdateCodexEntryRequest { name?; body; expected_modified_at }
 *   listCodexEntries(bookId, kind, needle?, includeArchived?, signal?) : Promise<CodexEntryResponse[]>
 *   getCodexEntry(bookId, entryId, signal?)      createCodexEntry(bookId, body, signal?)
 *   updateCodexEntry(bookId, entryId, body, signal?)
 *   class CodexListPageState { constructor(kind, initialNeedle?); readonly kind;
 *                              entries; entriesStatus; entriesError; needle; draftNeedle;
 *                              get isEmpty }
 *   loadCodexEntries(state, bookId, signal?) : Promise<void>
 *   submitCodexSearch(state, bookId, signal?) : string      // the query string to push
 *   interface CodexListPageProps { kind: CodexKind }
 *   const CodexListPage: FunctionComponent<CodexListPageProps>   // observer
 *   WorkRoutes  // /:bookId/{characters,locations,facts} -> <CodexListPage kind=…/>
 *
 * Every expected value comes from the STEP FILE's Definition of done, never from code:
 *   - DoD-1: each route is fixed to ONE kind and the kind is not user-selectable;
 *   - DoD-2: submitting a needle writes `q` INTO THE URL FROM THE SUBMIT HANDLER (not from a
 *     `useEffect` watching the query string — `frontend.md`:192) and re-fetches with it;
 *   - DoD-3: a URL that already carries `q` is filtered on the FIRST fetch (deep-linkable);
 *   - DoD-4: clearing the needle and submitting REMOVES `q` and reloads unfiltered;
 *   - DoD-5: activating a row navigates to `/work/:bookId/codex/:id` for THAT entry;
 *   - DoD-6: no matching entries is an EMPTY STATE, never an error;
 *   - DoD-7: a failed load is the trio's error state plus a retry that RE-FETCHES;
 *   - DoD-8: the new-entry action navigates to `/work/:bookId/codex/new?kind=<route kind>`;
 *   - DoD-9: the api module UNWRAPS `{ items: […] }` — the state holds a plain array;
 *   - DoD-10: every id crossing the api boundary is a `string`.
 * Routes here are basename-stripped (`/bk-1/characters`, not `/work/bk-1/characters`).
 *
 * Mocking: the `api/` modules are mocked module-factory form, never `fetch`. `api/codex` is
 * mocked for every page-level case; DoD-9 / DoD-10 instead exercise the REAL `api/codex`
 * through `vi.importActual`, with `api/client.request` stubbed (the module's spread keeps
 * `ApiError` the real class). Any spec mounting `WorkRoutes` must also mock `api/chats` and
 * `api/books`, re-armed in `beforeEach`, or the shell / chat-pane loads throw first.
 * `globals: false`: every primitive is imported explicitly.
 */
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes, useLocation, useSearchParams } from "react-router-dom";
import { runInAction } from "mobx";
import type {
  CodexEntryResponse,
  CodexKind,
  CreateCodexEntryRequest,
  UpdateCodexEntryRequest,
} from "../../src/types/codex";
import type { RequestOptions } from "../../src/api/client";
import { ApiError } from "../../src/api/client";
import * as apiClient from "../../src/api/client";
import * as codexApi from "../../src/api/codex";
import * as booksApi from "../../src/api/books";
import * as chatsApi from "../../src/api/chats";
import {
  CodexListPageState,
  loadCodexEntries,
  submitCodexSearch,
} from "../../src/work/pages/codexListPageState";
import { CodexListPage } from "../../src/work/pages/CodexListPage";
import { WorkRoutes } from "../../src/work/routes";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module — enumerate every export the page /
// state layer reaches through its namespace import.
vi.mock("../../src/api/codex", () => ({
  listCodexEntries: vi.fn(),
  getCodexEntry: vi.fn(),
  createCodexEntry: vi.fn(),
  updateCodexEntry: vi.fn(),
}));

// `request` is stubbed so the DoD-9 / DoD-10 cases can drive the REAL `api/codex` without a
// fetch; everything else (notably `ApiError`, which specs use for real) is the actual module.
vi.mock("../../src/api/client", async () => {
  const actual = await vi.importActual<typeof import("../../src/api/client")>(
    "../../src/api/client",
  );
  return { ...actual, request: vi.fn() };
});

// `WorkRoutes` mounts the workspace shell, which loads the book and owns the chat pane.
// Since 021.per-author-system-prompt / step 006 the Book-state page also loads the caller's
// own prompt through this module; both prompt exports are enumerated so that no route
// reachable from `WorkRoutes` can hit an `undefined` export.
vi.mock("../../src/api/books", () => ({
  getBookDetail: vi.fn(),
  getOwnSystemPrompt: vi.fn(),
  updateOwnSystemPrompt: vi.fn(),
  COLLABORATION_MODE_OPTIONS: [
    { value: "free", label: "Free" },
    { value: "proposal", label: "Proposal" },
  ],
  VISIBILITY_OPTIONS: [
    { value: "private", label: "Private" },
    { value: "public", label: "Public" },
  ],
}));

vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
}));

/* ------------------------------------------------------------------ fixtures */

const BOOK_ID = "bk-1";
const MODIFIED_AT = "2026-03-04T09:00:00Z";

/** A fully-typed CodexEntryResponse fixture; callers override what they assert on. */
function makeEntry(overrides: Partial<CodexEntryResponse> & { id: string }): CodexEntryResponse {
  return {
    book_id: BOOK_ID,
    kind: "character",
    name: "Unnamed",
    body: "Body text.",
    archived: false,
    author_id: "u-owner-1",
    modified_by: null,
    created_at: "2026-01-02T08:00:00Z",
    modified_at: MODIFIED_AT,
    ...overrides,
  };
}

const ARIA = makeEntry({
  id: "ce-char-1",
  kind: "character",
  name: "Aria Stormcrow",
  body: "A sellsword out of the reach.",
});
const BRAN = makeEntry({
  id: "ce-char-2",
  kind: "character",
  name: "Bran the Quiet",
  body: "A ferryman who never speaks.",
});
const WINTERFELL = makeEntry({
  id: "ce-loc-1",
  kind: "location",
  name: "Winterfell Keep",
  body: "A granite hall above hot springs.",
});
// A fact carries NO name (`name: null`) — the page shows a body excerpt for it instead.
const MOON_FACT = makeEntry({
  id: "ce-fact-1",
  kind: "fact",
  name: null,
  body: "The moon is red every seventh night.",
});

/** The whole book's codex, across all three kinds. */
const ALL_ENTRIES: CodexEntryResponse[] = [ARIA, BRAN, WINTERFELL, MOON_FACT];

/** Route segment per kind, as `010.working-page` shipped the navigator paths. */
const LIST_SEGMENT: Record<CodexKind, string> = {
  character: "characters",
  location: "locations",
  fact: "facts",
};

type UserEvt = ReturnType<typeof userEvent.setup>;

/** The stubbed `client.request`, typed for assertions on the url / body it received. */
const requestMock = apiClient.request as unknown as Mock<
  (url: string, opts?: RequestOptions) => Promise<unknown>
>;

/* ------------------------------------------------------------------- harness */

/** Reports the router's location and lets a test write the query string from OUTSIDE the page. */
function RouterProbe(): ReactElement {
  const location = useLocation();
  const [, setSearchParams] = useSearchParams();
  return (
    <>
      <span data-testid="pathname">{location.pathname}</span>
      <span data-testid="search">{location.search}</span>
      <button
        type="button"
        data-testid="external-url-write"
        onClick={() => setSearchParams({ q: "typed-into-the-url-elsewhere" })}
      >
        elsewhere
      </button>
    </>
  );
}

/** Mounts the list page under its own `:bookId` route, beside a probe on the same router. */
function renderPage(kind: CodexKind, route: string): void {
  renderWithProviders(
    <>
      <Routes>
        <Route
          path={`/:bookId/${LIST_SEGMENT[kind]}`}
          element={<CodexListPage kind={kind} />}
        />
      </Routes>
      <RouterProbe />
    </>,
    { route },
  );
}

/** Renders the whole WORK route table at a basename-stripped route. */
function renderRoutes(route: string): void {
  renderWithProviders(<WorkRoutes />, { route });
}

/** The mocked list call — the page's only api dependency. */
function listMock() {
  return vi.mocked(codexApi.listCodexEntries);
}

/** Positional args of the n-th `listCodexEntries` call (the signature is frozen, arity is not). */
function listCallArgs(index: number): unknown[] {
  const calls = listMock().mock.calls;
  expect(calls.length).toBeGreaterThan(index);
  return calls[index] as unknown[];
}

/** The page's single search input (a `searchbox` if typed `search`, else the text input). */
function getSearchInput(): HTMLElement {
  const searchboxes = screen.queryAllByRole("searchbox");
  if (searchboxes.length > 0) return searchboxes[0];
  const textboxes = screen.queryAllByRole("textbox");
  if (textboxes.length === 0) throw new Error("the list page renders no search input");
  return textboxes[0];
}

/** Type `needle` (empty string clears) and trigger the page's search submit action. */
async function submitSearch(user: UserEvt, needle: string): Promise<void> {
  const input = getSearchInput();
  await user.clear(input);
  if (needle !== "") await user.type(input, needle);

  const submitControls = [
    ...screen.queryAllByRole("button", { name: /search|find|filter|apply/i }),
    ...screen.queryAllByRole("link", { name: /search|find|filter|apply/i }),
  ];
  if (submitControls.length > 0) {
    await user.click(submitControls[0]);
    return;
  }
  const form = input.closest("form");
  if (form) {
    fireEvent.submit(form);
    return;
  }
  await user.type(input, "{Enter}");
}

/** The "new entry" action (button or link). */
function getNewEntryAction(): HTMLElement {
  const controls = [
    ...screen.queryAllByRole("button", { name: /new|add|create/i }),
    ...screen.queryAllByRole("link", { name: /new|add|create/i }),
  ];
  if (controls.length === 0) throw new Error("the list page renders no new-entry action");
  return controls[0];
}

/** The error state's retry control (button or link). */
function getRetryControl(): HTMLElement {
  const controls = [
    ...screen.queryAllByRole("button", { name: /retry|try again|reload|refresh/i }),
    ...screen.queryAllByRole("link", { name: /retry|try again|reload|refresh/i }),
  ];
  if (controls.length === 0) throw new Error("the error state offers no retry control");
  return controls[0];
}

function currentPathname(): string {
  return screen.getByTestId("pathname").textContent ?? "";
}

function currentSearch(): URLSearchParams {
  return new URLSearchParams(screen.getByTestId("search").textContent ?? "");
}

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests — re-arm every mock the mount path
  // touches. The codex list answers with the book's entries OF THE REQUESTED KIND, so a page
  // that asked for the wrong kind renders the wrong rows.
  listMock().mockImplementation((_bookId, kind) =>
    Promise.resolve(ALL_ENTRIES.filter((entry) => entry.kind === kind)),
  );
  vi.mocked(codexApi.getCodexEntry).mockResolvedValue(ARIA);
  vi.mocked(codexApi.createCodexEntry).mockResolvedValue(ARIA);
  vi.mocked(codexApi.updateCodexEntry).mockResolvedValue(ARIA);

  requestMock.mockResolvedValue({ items: [] });

  vi.mocked(booksApi.getBookDetail).mockResolvedValue({
    id: BOOK_ID,
    owner_id: "u-owner-1",
    title: "The Long Novel",
    description: "",
    collaboration_mode: "free",
    visibility: "private",
    state: "active",
    created_at: null,
    modified_at: null,
    members: [],
  });
  // The Book-state page's prompt load, re-armed like every other mock: a prompt-shaped
  // resolved value ("" + `modified_at: null` = no stored prompt) keeps it off the network
  // and out of the rejected-promise path.
  vi.mocked(booksApi.getOwnSystemPrompt).mockResolvedValue({
    book_id: BOOK_ID,
    system_prompt: "",
    modified_at: null,
  });
  vi.mocked(booksApi.updateOwnSystemPrompt).mockResolvedValue({
    book_id: BOOK_ID,
    system_prompt: "",
    modified_at: null,
  });
  vi.mocked(chatsApi.listChats).mockResolvedValue([]);
  vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
});

/* ------------------------------------------------------- DoD-1: kind per route */

describe("each route is fixed to one codex kind (DoD-1)", () => {
  const ROUTE_CASES: Array<[CodexKind, string, RegExp, RegExp[]]> = [
    // kind, route, a marker of an entry of THAT kind, markers of the other kinds
    [
      "character",
      `/${BOOK_ID}/characters`,
      /Aria Stormcrow/,
      [/Winterfell Keep/, /moon is red/i],
    ],
    [
      "location",
      `/${BOOK_ID}/locations`,
      /Winterfell Keep/,
      [/Aria Stormcrow/, /moon is red/i],
    ],
    // A fact has no name, so its row is identified by the body excerpt.
    ["fact", `/${BOOK_ID}/facts`, /moon is red/i, [/Aria Stormcrow/, /Winterfell Keep/]],
  ];

  for (const [kind, route, ownMarker, foreignMarkers] of ROUTE_CASES) {
    it(`DoD-1 (US-080.AC-1 / US-105.AC-1): ${route} lists only the book's ${kind} entries`, async () => {
      renderRoutes(route);

      const main = await screen.findByRole("main");

      // The route asked the api for exactly this kind...
      await waitFor(() => expect(listMock()).toHaveBeenCalled());
      const args = listCallArgs(0);
      expect(args[0]).toBe(BOOK_ID);
      expect(args[1]).toBe(kind);

      // ...and only that kind's entries reached the content pane.
      expect(await within(main).findByText(ownMarker)).toBeInTheDocument();
      for (const foreign of foreignMarkers) {
        expect(within(main).queryByText(foreign)).toBeNull();
      }
    });
  }

  it("DoD-1: the kind is fixed by the route — the page offers no kind control", async () => {
    renderRoutes(`/${BOOK_ID}/characters`);
    const main = await screen.findByRole("main");
    expect(await within(main).findByText(/Aria Stormcrow/)).toBeInTheDocument();

    // The content pane carries the search input and the actions — but nothing that would let
    // the author switch kind: no select/combobox, no radio group, no kind-named control.
    expect(within(main).queryAllByRole("combobox")).toHaveLength(0);
    expect(within(main).queryAllByRole("radio")).toHaveLength(0);
    expect(within(main).queryAllByRole("listbox")).toHaveLength(0);
    expect(within(main).queryAllByRole("button", { name: /kind/i })).toHaveLength(0);
  });
});

/* --------------------------------- DoD-2: the submit handler writes the query */

describe("submitting a needle writes q and re-fetches (DoD-2)", () => {
  it("DoD-2 (UC-071): the submit handler writes q into the URL and refetches with the needle", async () => {
    const user = userEvent.setup();
    renderPage("character", `/${BOOK_ID}/characters`);

    // First (unfiltered) load lands.
    await screen.findByText(/Aria Stormcrow/);
    expect(currentSearch().get("q")).toBeNull();

    // Keep the SECOND fetch in flight, so the URL write cannot be a consequence of the load
    // finishing: it must have happened in the submit handler itself.
    listMock().mockReturnValue(new Promise<CodexEntryResponse[]>(() => {}));

    await submitSearch(user, "storm");

    // The query string carries the needle while the refetch is still pending.
    expect(currentSearch().get("q")).toBe("storm");
    // ...and the refetch itself carried the needle (one submit, one fetch).
    await waitFor(() => expect(listMock().mock.calls.length).toBe(2));
    const args = listCallArgs(1);
    expect(args[0]).toBe(BOOK_ID);
    expect(args[1]).toBe("character");
    expect(args[2]).toBe("storm");
  });

  it("DoD-2 (frontend.md:192): the page does NOT re-fetch from an effect watching the query string", async () => {
    const user = userEvent.setup();
    renderPage("character", `/${BOOK_ID}/characters`);

    await screen.findByText(/Aria Stormcrow/);
    await waitFor(() => expect(listMock().mock.calls.length).toBe(1));

    // The query string changes from OUTSIDE the page's submit handler. A page whose load
    // reacts to the URL would fetch again here; the spec puts the write (and the fetch) in
    // the handler, so the URL is read once at mount and never watched.
    await user.click(screen.getByTestId("external-url-write"));
    await waitFor(() => expect(currentSearch().get("q")).toBe("typed-into-the-url-elsewhere"));

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(listMock().mock.calls.length).toBe(1);
    expect(screen.getByText(/Aria Stormcrow/)).toBeInTheDocument();
  });

  it("DoD-2: submitCodexSearch commits the draft needle, starts one fetch, and returns the query string to push", async () => {
    const state = new CodexListPageState("character");
    runInAction(() => {
      state.draftNeedle = "storm";
    });

    const queryString = submitCodexSearch(state, BOOK_ID);

    // Committed into state, and returned as the search string the caller pushes.
    expect(state.needle).toBe("storm");
    expect(new URLSearchParams(queryString).get("q")).toBe("storm");
    expect(queryString.startsWith("?")).toBe(false);

    // One submit fires exactly one fetch, carrying the committed needle.
    await waitFor(() => expect(listMock().mock.calls.length).toBe(1));
    const args = listCallArgs(0);
    expect(args[1]).toBe("character");
    expect(args[2]).toBe("storm");
  });
});

/* ----------------------------------------- DoD-3: a deep-linked q filters first */

describe("a URL that already carries q is filtered on the first fetch (DoD-3)", () => {
  it("DoD-3 (US-080.AC-1): mounting on ?q=… loads filtered on the FIRST fetch", async () => {
    renderPage("character", `/${BOOK_ID}/characters?q=storm`);

    await waitFor(() => expect(listMock()).toHaveBeenCalled());

    // The very first call already carries the needle — no unfiltered load happened first.
    const args = listCallArgs(0);
    expect(args[0]).toBe(BOOK_ID);
    expect(args[1]).toBe("character");
    expect(args[2]).toBe("storm");
    expect(listMock().mock.calls.length).toBe(1);

    // The deep-linked needle is the search input's value, so the active filter is visible.
    await waitFor(() => expect((getSearchInput() as HTMLInputElement).value).toBe("storm"));
  });

  it("DoD-3: the state seeds both the committed and the draft needle from the URL's q", () => {
    const state = new CodexListPageState("character", "storm");
    expect(state.needle).toBe("storm");
    expect(state.draftNeedle).toBe("storm");
    expect(state.kind).toBe("character");
  });
});

/* -------------------------------------- DoD-4: clearing the needle removes q */

describe("clearing the needle removes q and reloads unfiltered (DoD-4)", () => {
  it("DoD-4: clearing the search input and submitting drops q from the URL and refetches unfiltered", async () => {
    const user = userEvent.setup();
    renderPage("character", `/${BOOK_ID}/characters?q=storm`);

    await screen.findByText(/Aria Stormcrow/);
    await waitFor(() => expect(listMock().mock.calls.length).toBe(1));
    expect(currentSearch().get("q")).toBe("storm");

    await submitSearch(user, "");

    // `q` is gone from the URL — not left behind as an empty value.
    await waitFor(() => expect(currentSearch().get("q")).toBeNull());
    // ...and the reload carried no needle.
    await waitFor(() => expect(listMock().mock.calls.length).toBe(2));
    const args = listCallArgs(1);
    expect(args[1]).toBe("character");
    expect((args[2] as string | undefined) ?? "").toBe("");
  });

  it("DoD-4: submitCodexSearch returns an empty query string when the needle was cleared", async () => {
    const state = new CodexListPageState("character", "storm");
    runInAction(() => {
      state.draftNeedle = "";
    });

    const queryString = submitCodexSearch(state, BOOK_ID);

    expect(queryString).toBe("");
    expect(new URLSearchParams(queryString).get("q")).toBeNull();
    expect(state.needle).toBe("");
    await waitFor(() => expect(listMock().mock.calls.length).toBe(1));
    expect((listCallArgs(0)[2] as string | undefined) ?? "").toBe("");
  });
});

/* -------------------------------------------- DoD-5: row activation navigates */

describe("activating a row opens that entry (DoD-5)", () => {
  it("DoD-5 (US-105.AC-2 / UC-083): activating a row navigates to /:bookId/codex/:id for that entry", async () => {
    const user = userEvent.setup();
    renderPage("character", `/${BOOK_ID}/characters`);

    // Two rows are on screen; the SECOND one is activated, so the id must be the row's own.
    await screen.findByText(/Aria Stormcrow/);
    const target = await screen.findByText(/Bran the Quiet/);

    await user.click(target);

    await waitFor(() => expect(currentPathname()).toBe(`/${BOOK_ID}/codex/${BRAN.id}`));
  });
});

/* ---------------------------------------------- DoD-6: empty state, not error */

describe("no matching entries is an empty state (DoD-6)", () => {
  it("DoD-6 (UC-071): a book with no matching entries renders an empty state, not an error", async () => {
    listMock().mockResolvedValue([]);

    renderPage("character", `/${BOOK_ID}/characters`);

    await waitFor(() => expect(listMock()).toHaveBeenCalled());

    // Nothing failed: no alert, no error wording, no retry affordance.
    await waitFor(() => {
      expect(screen.queryByRole("alert")).toBeNull();
    });
    const pageText = document.body.textContent ?? "";
    expect(pageText).not.toMatch(/error|failed|unable|could ?n[o']t/i);
    expect(
      screen.queryAllByRole("button", { name: /retry|try again|reload/i }),
    ).toHaveLength(0);

    // The pane is not blank either — an empty state says there is nothing here.
    expect(pageText.trim()).not.toBe("");
    expect(pageText).toMatch(/\b(no|none|nothing|empty)\b/i);
  });

  it("DoD-6: the state's isEmpty computed is true only for a completed load that matched nothing", async () => {
    const state = new CodexListPageState("character");

    // Idle — nothing loaded yet, so not "empty".
    expect(state.isEmpty).toBe(false);

    // A completed load that matched nothing.
    listMock().mockResolvedValue([]);
    await loadCodexEntries(state, BOOK_ID);
    expect(state.entriesStatus).toBe("ready");
    expect(state.entries).toEqual([]);
    expect(state.isEmpty).toBe(true);

    // A completed load with entries.
    listMock().mockResolvedValue([ARIA]);
    await loadCodexEntries(state, BOOK_ID);
    expect(state.entries).toEqual([ARIA]);
    expect(state.isEmpty).toBe(false);

    // A failed load is an error, never "empty".
    listMock().mockRejectedValue(new ApiError(500, "Server error"));
    await loadCodexEntries(state, BOOK_ID);
    expect(state.entriesStatus).toBe("error");
    expect(state.isEmpty).toBe(false);
  });
});

/* ------------------------------------------- DoD-7: error state plus a retry */

describe("a failed load shows the trio's error state with a retry (DoD-7)", () => {
  it("DoD-7: a failed load renders the error state and the retry re-fetches", async () => {
    const user = userEvent.setup();
    listMock().mockRejectedValue(new ApiError(500, "Server error"));

    renderPage("character", `/${BOOK_ID}/characters`);

    // The error state is on screen (the ready view is not).
    await waitFor(() =>
      expect(document.body.textContent ?? "").toMatch(/error|failed|unable|could ?n[o']t/i),
    );
    expect(screen.queryByText(/Aria Stormcrow/)).toBeNull();

    // The retry re-fetches, and the list arrives on the second attempt.
    listMock().mockResolvedValue([ARIA]);
    await user.click(getRetryControl());

    await waitFor(() => expect(listMock().mock.calls.length).toBe(2));
    expect(await screen.findByText(/Aria Stormcrow/)).toBeInTheDocument();
  });

  it("DoD-7: the loader drives the async trio — error message in, error status set", async () => {
    const state = new CodexListPageState("character");
    listMock().mockRejectedValue(new ApiError(500, "Server error"));

    await loadCodexEntries(state, BOOK_ID);

    expect(state.entriesStatus).toBe("error");
    expect(state.entriesError).not.toBeNull();
    expect(state.entriesError ?? "").not.toBe("");
    expect(state.entries).toEqual([]);
  });
});

/* --------------------------------------- DoD-8: the new-entry action + kind */

describe("the new-entry action opens a blank entry of the route's kind (DoD-8)", () => {
  const NEW_CASES: CodexKind[] = ["character", "fact"];

  for (const kind of NEW_CASES) {
    it(`DoD-8 (UC-076): on the ${kind} route the new-entry action navigates to /codex/new?kind=${kind}`, async () => {
      const user = userEvent.setup();
      renderPage(kind, `/${BOOK_ID}/${LIST_SEGMENT[kind]}`);

      await waitFor(() => expect(listMock()).toHaveBeenCalled());

      await user.click(getNewEntryAction());

      await waitFor(() => expect(currentPathname()).toBe(`/${BOOK_ID}/codex/new`));
      expect(currentSearch().get("kind")).toBe(kind);
    });
  }
});

/* ------------------------------- DoD-9 / DoD-10: the api module's boundary */

type CodexApi = typeof import("../../src/api/codex");
type ListResult = Awaited<ReturnType<CodexApi["listCodexEntries"]>>;

// DoD-9 (compile time): the list api's result is a plain array — the `{ items }` envelope is
// unwrapped in the module and is NOT modelled in `types/codex.d.ts`.
const listResultIsAPlainArray: ListResult = [];
// @ts-expect-error DoD-9: an `{ items }` envelope must not satisfy the list api's result type.
const listResultIsNotAnEnvelope: ListResult = { items: [] };
void listResultIsAPlainArray;
void listResultIsNotAnEnvelope;

// DoD-10 (compile time): every id crossing the api boundary is a `string`.
type BookIdParam = Parameters<CodexApi["getCodexEntry"]>[0];
type EntryIdParam = Parameters<CodexApi["getCodexEntry"]>[1];
const bookIdIsAString: BookIdParam = "bk-1";
const entryIdIsAString: EntryIdParam = "ce-1";
// @ts-expect-error DoD-10: a numeric book id must not compile.
const bookIdRejectsANumber: BookIdParam = 1;
// @ts-expect-error DoD-10: a numeric entry id must not compile.
const entryIdRejectsANumber: EntryIdParam = 2;
const entryIdFieldIsAString: CodexEntryResponse["id"] = "ce-1";
const entryBookIdFieldIsAString: CodexEntryResponse["book_id"] = "bk-1";
void bookIdIsAString;
void entryIdIsAString;
void bookIdRejectsANumber;
void entryIdRejectsANumber;
void entryIdFieldIsAString;
void entryBookIdFieldIsAString;

/** The REAL api module (the file-level `vi.mock` is bypassed on purpose here). */
async function realCodexApi(): Promise<CodexApi> {
  return vi.importActual<CodexApi>("../../src/api/codex");
}

describe("the codex api module's wire boundary (DoD-9, DoD-10)", () => {
  it("DoD-9: listCodexEntries unwraps the { items: […] } envelope into a plain array", async () => {
    const api = await realCodexApi();
    requestMock.mockResolvedValue({ items: [ARIA, BRAN] });

    const entries = await api.listCodexEntries(BOOK_ID, "character");

    // A plain array of entries reaches the caller — no envelope, no `.items` hop.
    const asArray: CodexEntryResponse[] = entries;
    expect(Array.isArray(asArray)).toBe(true);
    expect(asArray).toEqual([ARIA, BRAN]);
    expect(asArray.map((entry) => entry.id)).toEqual([ARIA.id, BRAN.id]);
  });

  it("DoD-9: an empty envelope unwraps to an empty array (the empty state's input, not undefined)", async () => {
    const api = await realCodexApi();
    requestMock.mockResolvedValue({ items: [] });

    const entries = await api.listCodexEntries(BOOK_ID, "fact");

    expect(Array.isArray(entries)).toBe(true);
    expect(entries).toEqual([]);
  });

  it("DoD-10: every id crossing the api boundary is a string — path ids and request bodies alike", async () => {
    const api = await realCodexApi();
    requestMock.mockResolvedValue(ARIA);

    const create: CreateCodexEntryRequest = {
      kind: "character",
      name: "Aria Stormcrow",
      body: "A sellsword out of the reach.",
    };
    const update: UpdateCodexEntryRequest = {
      name: "Aria Stormcrow",
      body: "A sellsword sworn to the Keep.",
      expected_modified_at: MODIFIED_AT,
    };

    await api.createCodexEntry(BOOK_ID, create);
    await api.updateCodexEntry(BOOK_ID, "ce-char-1", update);
    await api.getCodexEntry(BOOK_ID, "ce-char-1");

    const urls = requestMock.mock.calls.map(([url]) => url);
    expect(urls.length).toBe(3);
    for (const url of urls) {
      expect(typeof url).toBe("string");
      expect(url).toContain(`/${BOOK_ID}/`);
    }
    // The snowflake ids travel verbatim as strings, never coerced through a number.
    expect(urls.filter((url) => url.includes("ce-char-1")).length).toBe(2);

    // No id in any request body is a number.
    for (const [, opts] of requestMock.mock.calls) {
      const body = opts?.body;
      if (body !== null && typeof body === "object") {
        for (const [key, value] of Object.entries(body as Record<string, unknown>)) {
          if (/(^|_)id$/.test(key)) expect(typeof value).toBe("string");
        }
      }
    }
  });

  it("DoD-10: the ids the page hands the api are the strings it was given", async () => {
    renderPage("character", `/${BOOK_ID}/characters`);

    await waitFor(() => expect(listMock()).toHaveBeenCalled());
    const args = listCallArgs(0);
    expect(typeof args[0]).toBe("string");
    expect(args[0]).toBe(BOOK_ID);
  });
});
