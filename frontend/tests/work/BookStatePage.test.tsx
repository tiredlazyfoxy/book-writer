/**
 * Book-state landing view — 010.working-page / 003.book-state-landing,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 003):
 *   const BookStatePage: FunctionComponent   // observer, no props; reads :bookId via router
 *   class BookStatePageState { bookDetail; bookDetailStatus; bookDetailError;
 *                              get collaborationModeLabel; get visibilityLabel;
 *                              get lifecycleStateLabel; get memberList; get memberCount }
 *   loadBookState(state, bookId, signal?) : Promise<void>          // calls getBookDetail
 *   WorkRoutes  // /:bookId index -> <Navigate to="state" replace/>, state -> <BookStatePage/>
 *
 * The page reads `:bookId` from the router, so DoD-2..5 mount it under a
 * `Route path="/:bookId/state"`; routes are basename-stripped (`/bk-1/state`,
 * not `/work/bk-1/state`). DoD-1 renders the whole WORK route table (`WorkRoutes`)
 * at `/bk-1` and observes the redirect landing on `state`.
 *
 * `api/books` is mocked module-factory form (never `fetch`). A factory replaces the
 * WHOLE module, and this page reads THREE exports from it — `getBookDetail` (the
 * loader), and `COLLABORATION_MODE_OPTIONS` / `VISIBILITY_OPTIONS` (the author-facing
 * labels). The two option arrays are SPEC DATA copied verbatim from `src/api/books.ts`
 * (`context.md` -> "reuse them for the author-facing labels"), so the factory supplies
 * their real value/label pairs. `ApiError` is the real class from `api/client`.
 *
 * Expected values come from the spec, never from the page's code:
 *   - the redirect target and landing view are US-106.AC-1 / the step's route map;
 *   - the rendered fields are exactly what `BookDetailResponse` carries (DoD-2 /
 *     `domain-book.md` minus the wire gap);
 *   - the state-notes region exists even on a SUCCESSFUL load — it is its own concern,
 *     not a load failure (DoD-3);
 *   - the per-chapter continuity region is present and the page never says "flag" —
 *     "warning" is the author-facing word (DoD-4 / `frontend-workspace.md`);
 *   - the trio never blanks the pane: a pending load shows a loading state, a failed one
 *     an author-facing error (DoD-5).
 *
 * RE-BOUND by `016.chapter-close-continuity` (`plan.md` -> D8, DoD-12; Implementation
 * outline 6): the two PLACEHOLDER stubs this file was written against — the "State
 * notes" stub whose copy said the notes were "not yet available", and the "Per-chapter
 * continuity" stub that named `016.chapter-close-continuity` as its owner — are the very
 * things this feature replaces, with a real state-notes editor and a real per-chapter
 * continuity list. Three things moved, and nothing else did:
 *   (a) the marker for "the Book-state view is up" is no longer the owning feature's
 *       literal name (DoD-1, and `expectBookStateContentIntact`);
 *   (b) the state-notes region is a real, EDITABLE region rather than a "not yet
 *       available" placeholder (DoD-3);
 *   (c) the page now carries TWO editable regions, not one — the author prompt and the
 *       state notes (021/006's DoD-9). That test's closed-set claim is widened by
 *       exactly one region, not dropped: a third editable control still fails it.
 * The DELIVERED surfaces' own content (per-chapter summaries, changesets and warning
 * lists) is on `plan.md` -> Test plan -> "Not tested (deliberate)", so nothing here
 * asserts on it; `api/continuity` is mocked and armed benignly for that reason.
 * The `warning`-not-`flag` vocabulary rule, the book-state table, the archived branch
 * and the prompt trio's independent failure are all unchanged.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import type { BookAuthorPromptResponse, BookDetailResponse } from "../../src/types/books";
import type {
  BookContinuityResponse,
  BookStateNotesResponse,
} from "../../src/types/continuity";
import { ApiError } from "../../src/api/client";
import * as booksApi from "../../src/api/books";
import * as chatsApi from "../../src/api/chats";
import * as continuityApi from "../../src/api/continuity";
import { BookStatePage } from "../../src/work/pages/BookStatePage";
import { WorkRoutes } from "../../src/work/routes";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module. The page's render subtree reaches
// `getBookDetail` (the loader) plus `COLLABORATION_MODE_OPTIONS` / `VISIBILITY_OPTIONS`
// (the label sources). The two arrays are the real spec-data pairs from
// `src/api/books.ts` — a factory that dropped them would strip the page's labels.
//
// 021.per-author-system-prompt / 006 widens this factory with the two prompt calls the
// page now makes (`getOwnSystemPrompt` / `updateOwnSystemPrompt`, step 005's shared
// contract). A whole-module factory that omitted an export the page imports would leave
// it `undefined` and the page would fail to render for the wrong reason — so every
// pre-existing entry stays exactly as it was.
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

// The DoD-1 case mounts the whole `WorkRoutes` table at `/bk-1`, which matches
// `/:bookId` and renders the workspace shell; the shell now owns `ChatPaneState`
// and kicks off a chat-pane load in its mount effect (`listChats` / `listModelOptions`
// from `src/api/chats`). Replace the WHOLE module so that mount-time load resolves
// locally instead of firing a real fetch (an unhandled rejection would fail the run).
// The two list calls resolve empty; the rest are never reached from a mount and get
// trivial resolved values. Pure harness mocking — no assertion here depends on it.
vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn().mockResolvedValue([]),
  createChat: vi.fn().mockResolvedValue(undefined),
  updateChat: vi.fn().mockResolvedValue(undefined),
  getChat: vi.fn().mockResolvedValue(undefined),
  listModelOptions: vi.fn().mockResolvedValue([]),
}));

// `016.chapter-close-continuity` replaces this page's two stubs with real surfaces, so
// the page's mount now reads the book's state notes and its per-chapter continuity
// (`plan.md` -> Interface for `bookStatePageState.ts`). Whole-module factory, armed
// benignly in `beforeEach`. The delivered surfaces' CONTENT is on the plan's
// "Not tested (deliberate)" list, so nothing here asserts on the returned data — it
// exists so the page can render.
vi.mock("../../src/api/continuity", () => ({
  getStateNotes: vi.fn(),
  updateStateNotes: vi.fn(),
  getBookContinuity: vi.fn(),
  getChapterChangeset: vi.fn(),
}));

const OWNER_ID = "u-owner-77";
const CO_AUTHOR_ID = "u-coauthor-42";
const BOOK_TITLE = "The Winds of Winter";
const BOOK_DESCRIPTION = "A sprawling saga told across nine kingdoms.";

/** The book every route in this spec addresses — the same id `makeDetail` carries. */
const BOOK_ID = "bk-1";
const STATE_ROUTE = `/${BOOK_ID}/state`;
/** The caller's own stored prompt, as `GET /api/books/{id}/system-prompt` returns it. */
const STORED_PROMPT = "Write in close third person, past tense.";

/** A fully-typed BookDetailResponse fixture; callers override the fields they assert on. */
function makeDetail(overrides: Partial<BookDetailResponse> = {}): BookDetailResponse {
  return {
    id: "bk-1",
    owner_id: OWNER_ID,
    title: BOOK_TITLE,
    description: BOOK_DESCRIPTION,
    collaboration_mode: "free",
    visibility: "private",
    state: "active",
    created_at: "2018-05-01T10:00:00Z",
    modified_at: "2026-11-30T15:00:00Z",
    members: [{ user_id: CO_AUTHOR_ID, role: "co_author", created_at: "2021-06-02T09:00:00Z" }],
    ...overrides,
  };
}

/**
 * A fully-typed `BookAuthorPromptResponse` fixture (step 005's shared DTO, consumed
 * unchanged here): `system_prompt` is never null — `""` means "this author has no
 * prompt" — and `modified_at` is null only when no row exists yet.
 */
function makePrompt(overrides: Partial<BookAuthorPromptResponse> = {}): BookAuthorPromptResponse {
  return {
    book_id: BOOK_ID,
    system_prompt: STORED_PROMPT,
    modified_at: "2026-07-01T12:00:00Z",
    ...overrides,
  };
}

/** The book's live state notes, as `GET /api/books/{id}/state-notes` returns them. */
const STORED_STATE_NOTES = "Halden holds the north gate through the long winter.";

function makeStateNotes(
  overrides: Partial<BookStateNotesResponse> = {},
): BookStateNotesResponse {
  return {
    book_id: BOOK_ID,
    active_notes: STORED_STATE_NOTES,
    modified_at: "2026-07-01T12:00:00Z",
    ...overrides,
  };
}

/**
 * One chapter's continuity, carrying one open warning. HARNESS ONLY: the per-chapter
 * region's rendering is on `plan.md` -> Test plan -> "Not tested (deliberate)", so no
 * case asserts on this content. It exists so the region has something to render, and it
 * deliberately contains neither the word "flag" (DoD-4's vocabulary rule) nor a
 * lifecycle token that would collide with DoD-2's `archiv` match.
 */
function makeContinuity(): BookContinuityResponse {
  return {
    items: [
      {
        chapter_id: "ch-1",
        title: "The Long Road",
        ordinal: 1,
        summary: "The gate holds until the fourth month.",
        summary_status: "approved",
        changeset: null,
        warnings: [
          {
            id: "warn-1",
            chapter_id: "ch-1",
            origin: "check",
            comment: "Halden is left-handed here and right-handed in chapter two.",
            status: "open",
            created_by: OWNER_ID,
            created_at: "2026-07-02T09:00:00Z",
            resolved_by: null,
            resolved_at: null,
          },
        ],
      },
    ],
  };
}

/** Mounts the page directly under a `:bookId` route so `useParams().bookId` resolves. */
function renderPage(route: string): void {
  renderWithProviders(
    <Routes>
      <Route path="/:bookId/state" element={<BookStatePage />} />
    </Routes>,
    { route },
  );
}

/** Reports the router's current pathname, so the redirect target is observable. */
function LocationProbe(): ReactElement {
  const location = useLocation();
  return <span data-testid="pathname">{location.pathname}</span>;
}

beforeEach(() => {
  // `restoreMocks` wipes the implementation between tests — default to a resolved detail;
  // pending / rejected cases override in-test.
  vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail());
  // Same re-arming for the two prompt calls the page makes from the same mount effect:
  // without it they would resolve `undefined` and every pre-existing assertion in this
  // file would go red for the wrong reason. The default is the happy path — a stored
  // prompt for this book; individual cases override.
  vi.mocked(booksApi.getOwnSystemPrompt).mockResolvedValue(makePrompt());
  vi.mocked(booksApi.updateOwnSystemPrompt).mockResolvedValue(makePrompt());
  // `restoreMocks` also clears the factory's chat-list implementations, so re-arm the two
  // list calls here (mirrors WorkspaceShell.test.tsx) — the shell's mount-time chat load
  // must resolve empty, not `undefined`, or the pane computeds crash. Pure harness mocking.
  vi.mocked(chatsApi.listChats).mockResolvedValue([]);
  vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
  // 016's two mount reads for this page, armed on the happy path. Harness only — no case
  // asserts on what they return.
  vi.mocked(continuityApi.getStateNotes).mockResolvedValue(makeStateNotes());
  vi.mocked(continuityApi.updateStateNotes).mockResolvedValue(makeStateNotes());
  vi.mocked(continuityApi.getBookContinuity).mockResolvedValue(makeContinuity());
});

describe("BookStatePage", () => {
  it("DoD-1: opening the working page at /:bookId redirects to /:bookId/state and the Book-state view renders", async () => {
    // Render the whole WORK route table at the bare `/:bookId` entry. A `LocationProbe`
    // shares the MemoryRouter so the redirect target is directly observable. The index
    // route redirects (replace) to `state`; landing there proves it is not a back-trap.
    renderWithProviders(
      <MemoryRouter initialEntries={["/bk-1"]}>
        <WorkRoutes />
        <LocationProbe />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/state"),
    );

    // The Book-state view itself is up: its state-notes region is on screen — a marker
    // unique to this page (not the shell chrome). Re-bound by `016`: the old marker was
    // the per-chapter stub's literal naming of its owning feature, which that feature has
    // now replaced with the real region.
    expect((await screen.findAllByText(/state notes/i)).length).toBeGreaterThan(0);
  });

  it("DoD-2: renders every field BookDetailResponse carries — title, description, mode/visibility/state labels, both timestamps, owner and co-author", async () => {
    // `archived` is a distinctive lifecycle token (the continuity region mentions
    // "warnings", so `active` would collide); years 2018/2026 distinguish the two
    // timestamps; ids distinguish owner from co-author.
    vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail({ state: "archived" }));

    renderPage("/bk-1/state");

    // The book's own fields.
    expect(await screen.findByText(BOOK_TITLE)).toBeInTheDocument();
    expect(screen.getByText(BOOK_DESCRIPTION)).toBeInTheDocument();

    const pageText = document.body.textContent ?? "";
    // Collaboration-mode + visibility labels come from the spec option arrays.
    expect(pageText).toContain("Free"); // collaboration_mode "free" -> "Free"
    expect(pageText).toContain("Private"); // visibility "private" -> "Private"
    // Lifecycle state rendered human-readably (spec pins no exact wording; the derived
    // label carries the state token, not a raw unrelated word).
    expect(pageText).toMatch(/archiv/i); // state "archived"
    // Both timestamps rendered (any reasonable date format includes the year).
    expect(pageText).toMatch(/2018/); // created_at
    expect(pageText).toMatch(/2026/); // modified_at
    // Owner and co-author members both shown.
    expect(pageText).toContain(OWNER_ID);
    expect(pageText).toContain(CO_AUTHOR_ID);
  });

  it("DoD-3: the state-notes region is its own labelled region — present on a SUCCESSFUL load, not a load failure and not omitted", async () => {
    renderPage("/bk-1/state");

    // A successful load (the title is on screen), and the state-notes region is present
    // alongside it as its own concern.
    expect(await screen.findByText(BOOK_TITLE)).toBeInTheDocument();

    // A spec-faithful page names "state notes" in more than one element — the region
    // label and the field's own labelling — so match without assuming uniqueness.
    expect(screen.getAllByText(/state notes/i).length).toBeGreaterThan(0);

    // Re-bound by `016` (D8, Implementation outline 6): the region is no longer a "not
    // yet available" placeholder — it is the book's live note set, offered as an editable
    // field. That the field EXISTS and is writable is the region's presence claim; what
    // it renders is on the plan's "Not tested (deliberate)" list.
    await waitFor(() => {
      expect(queryStateNotesEditor()).not.toBeNull();
    });
    expect(stateNotesEditor()).toBeEnabled();
    // ...and the region is not the old placeholder dressed up as one.
    expect(document.body.textContent ?? "").not.toMatch(/not yet (available|exposed)/i);
  });

  it("DoD-4: the per-chapter continuity region is present, and the page says 'warning' never 'flag'", async () => {
    renderPage("/bk-1/state");

    await screen.findByText(BOOK_TITLE);

    // Re-bound by `016` (D8: the feature "reuses the two stubs that already name this
    // feature"): the region is delivered, so it is located by its own label rather than
    // by the owner-naming sentence the stub used to carry.
    await waitFor(() => {
      expect(document.body.textContent ?? "").toMatch(/continuity/i);
    });

    // UNCHANGED, and the durable half of this case: "warning" is the author-facing word;
    // "flag" must never appear anywhere on the page (`frontend-workspace.md`).
    const pageText = document.body.textContent ?? "";
    expect(pageText).toMatch(/warning/i);
    expect(pageText).not.toMatch(/flag/i);
  });

  it("DoD-5: a pending load shows a loading state, not the book fields and not a blank pane", async () => {
    // A promise that never settles keeps the trio in its loading state.
    vi.mocked(booksApi.getBookDetail).mockReturnValue(new Promise<BookDetailResponse>(() => {}));

    renderPage("/bk-1/state");

    // The load was kicked off, the book's own fields are NOT shown yet (not ready)...
    expect(vi.mocked(booksApi.getBookDetail)).toHaveBeenCalled();
    expect(screen.queryByText(BOOK_TITLE)).toBeNull();
    // ...and the pane is not blank — the loading state is on screen.
    expect((document.body.textContent ?? "").trim()).not.toBe("");
  });

  it("DoD-5: a failed load (ApiError) shows an author-facing error rather than a blank pane", async () => {
    vi.mocked(booksApi.getBookDetail).mockRejectedValue(new ApiError(500, "Server error"));

    renderPage("/bk-1/state");

    await waitFor(() => expect(vi.mocked(booksApi.getBookDetail)).toHaveBeenCalled());

    // The ready view never appears...
    await waitFor(() => expect(screen.queryByText(BOOK_TITLE)).toBeNull());
    // ...and the pane is not blank — an author-facing error is rendered instead. The spec
    // pins no exact error wording, so DoD-5 asserts the pane is not blank.
    expect((document.body.textContent ?? "").trim()).not.toBe("");
  });
});

/* ------------------------------------------------------------------------------------
 * 021.per-author-system-prompt / 006.book-state-editor — the Book-state prompt editor.
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-8 · DoD-9.
 * (DoD-10 is [manual/live] — two authors on one book — and has no test here.)
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 006, and step 005
 * for the shared contract consumed unchanged):
 *   getOwnSystemPrompt(bookId, signal?): Promise<BookAuthorPromptResponse>
 *   updateOwnSystemPrompt(bookId, body: UpdateBookAuthorPromptRequest, signal?)
 *                                      : Promise<BookAuthorPromptResponse>
 *   interface BookAuthorPromptResponse { book_id: string; system_prompt: string;
 *                                        modified_at: ISODateString | null }
 *   PUT body: { system_prompt: string }
 * The page loads the prompt from its EXISTING mount effect, so mounting it under
 * `/:bookId/state` is the whole arrangement — exactly as the six cases above do.
 *
 * Expected values come from the spec, never from the page's code:
 *   - the prompt is loaded ALONGSIDE the book state and its text lands in the editor
 *     (`006` Interface intent) — DoD-1;
 *   - `""` + `modified_at: null` is the normal starting state of every book for every
 *     author (`context.md` -> "The wire contract"), so it renders an empty EDITABLE
 *     field, never an error and never a read-only placeholder — DoD-2;
 *   - after a save the surface shows what the SERVER returned, not the optimistic draft
 *     (`context.md` -> cross-cutting frontend constraints), which is why the stored value
 *     deliberately differs from what was typed — DoD-3;
 *   - the save control is gated on "dirty AND no save in flight" — DoD-4;
 *   - an empty save is legal and clears the prompt, and there is NO DELETE verb, so no
 *     delete control may be offered (`context.md` -> decision 6) — DoD-5;
 *   - a refusal shows the server's own message and loses nothing typed — DoD-6;
 *   - the prompt is a SECOND, independent trio: its failure renders its own error branch
 *     and leaves the book-state view whole — DoD-7;
 *   - the copy says the prompt is the caller's own and not shared with co-authors — the
 *     wording that replaces UC-093's book-wide framing (`context.md` -> Goal) — DoD-8;
 *   - this step adds EXACTLY ONE editable region: the prompt editor is editable, and it
 *     is the only editable control on the surface (`006.context.md` -> the editability
 *     table). Asserting only "nothing else is editable" would pass by construction, so
 *     both halves are asserted together — DoD-9.
 *
 * Out of scope by decision, and deliberately unasserted: any restore buffer, keystroke
 * persistence, `baseVersion`, stale-buffer detection or 409 path (`006.context.md`).
 *
 * The spec pins no exact labels, so the editor is located as the prompt-labelled
 * `<textarea>` and the save control as the nearest `save`-named button above it — never
 * by test id or DOM shape.
 * ---------------------------------------------------------------------------------- */

/** Everything that could name a field for its author. */
function labelTextFor(field: HTMLTextAreaElement): string {
  const parts: string[] = [
    field.getAttribute("aria-label") ?? "",
    field.getAttribute("placeholder") ?? "",
    field.getAttribute("name") ?? "",
  ];
  const labels = field.labels;
  if (labels !== null) {
    for (const label of Array.from(labels)) parts.push(label.textContent ?? "");
  }
  return parts.join(" ");
}

/**
 * The multi-line prompt editor: the `<textarea>` whose own labelling names a prompt, or
 * the page's sole textarea when nothing is labelled that way.
 */
function queryPromptEditor(): HTMLTextAreaElement | null {
  const areas = Array.from(document.querySelectorAll("textarea"));
  if (areas.length === 0) return null;
  const named = areas.filter((area) => /prompt/i.test(labelTextFor(area)));
  if (named.length > 0) return named[0];
  // Re-bound by `016`: this page now carries a SECOND editable region (the state-notes
  // editor), so the old "the page's sole textarea" fallback narrows to "the sole textarea
  // that is not that one". The helper's intent — locate the prompt editor without
  // assuming an exact label — is unchanged.
  const notes = queryStateNotesEditor();
  const others = areas.filter((area) => area !== notes);
  return others.length === 1 ? others[0] : null;
}

/**
 * Everything that could name a control for its author — the same parts `labelTextFor`
 * reads, widened past `<textarea>` because the state-notes region's control kind is not
 * fixed by the frozen interface.
 */
function labelTextForControl(node: HTMLElement): string {
  const parts: string[] = [
    node.getAttribute("aria-label") ?? "",
    node.getAttribute("placeholder") ?? "",
    node.getAttribute("name") ?? "",
  ];
  const labels = (node as HTMLInputElement).labels;
  if (labels !== null && labels !== undefined) {
    for (const label of Array.from(labels)) parts.push(label.textContent ?? "");
  }
  return parts.join(" ");
}

/**
 * The state-notes editor `016` delivers in place of the old "not yet available"
 * placeholder (`plan.md` -> D8, Implementation outline 6): the editable control whose own
 * labelling names the state notes.
 */
function queryStateNotesEditor(): HTMLElement | null {
  const named = editableControls().filter((node) =>
    /state notes/i.test(labelTextForControl(node)),
  );
  return named.length > 0 ? named[0] : null;
}

function stateNotesEditor(): HTMLElement {
  const editor = queryStateNotesEditor();
  if (editor === null) throw new Error("no state-notes editor is rendered");
  return editor;
}

function promptEditor(): HTMLTextAreaElement {
  const editor = queryPromptEditor();
  if (editor === null) throw new Error("no system-prompt editor is rendered");
  return editor;
}

function saveButtonsIn(root: ParentNode): HTMLButtonElement[] {
  return Array.from(root.querySelectorAll("button")).filter((button) =>
    /save/i.test(button.textContent ?? ""),
  );
}

/** The save control belonging to the prompt editor, or `null` when none is offered. */
function findSaveControl(): HTMLButtonElement | null {
  const editor = queryPromptEditor();
  if (editor === null) return null;
  let node: HTMLElement | null = editor.parentElement;
  while (node !== null && node !== document.body) {
    const found = saveButtonsIn(node);
    if (found.length > 0) return found[0];
    node = node.parentElement;
  }
  return null;
}

function saveControl(): HTMLButtonElement {
  const button = findSaveControl();
  if (button === null) throw new Error("no save control is offered for the prompt editor");
  return button;
}

/**
 * True when the author cannot save right now. DoD-4 says only that saving is
 * *unavailable*, so an absent control counts exactly as a disabled one does.
 */
function saveIsUnavailable(): boolean {
  const button = findSaveControl();
  return button === null || button.disabled;
}

/** The prompt section's own subtree: the smallest ancestor of the editor holding its save control. */
function promptRegion(): HTMLElement {
  const editor = promptEditor();
  let node: HTMLElement | null = editor.parentElement;
  while (node !== null && node !== document.body) {
    if (saveButtonsIn(node).length > 0) return node;
    node = node.parentElement;
  }
  return editor.parentElement ?? document.body;
}

/**
 * Every control the author can actually change on the rendered surface: text-bearing
 * inputs, textareas, selects and contenteditable regions that are neither disabled nor
 * read-only. Buttons are not editable regions — they act, they do not hold author text.
 */
function editableControls(): HTMLElement[] {
  const nodes = Array.from(
    document.querySelectorAll<HTMLElement>("input, textarea, select, [contenteditable='true']"),
  );
  return nodes.filter((node) => {
    if (node instanceof HTMLInputElement) {
      if (["hidden", "button", "submit", "reset", "image"].includes(node.type)) return false;
      return !node.disabled && !node.readOnly;
    }
    if (node instanceof HTMLTextAreaElement) return !node.disabled && !node.readOnly;
    if (node instanceof HTMLSelectElement) return !node.disabled;
    return true;
  });
}

function pageText(): string {
  return document.body.textContent ?? "";
}

function typeInto(field: HTMLTextAreaElement, value: string): void {
  fireEvent.change(field, { target: { value } });
}

/** Waits for the mount load to settle with the given prompt text in the editor. */
async function waitForEditor(value: string): Promise<HTMLTextAreaElement> {
  await waitFor(() => {
    expect(queryPromptEditor()).not.toBeNull();
    expect(promptEditor().value).toBe(value);
  });
  return promptEditor();
}

/** The read-only book-state content that must keep rendering exactly as it does today. */
async function expectBookStateContentIntact(): Promise<void> {
  expect(await screen.findByText(BOOK_TITLE)).toBeInTheDocument();
  expect(screen.getByText(BOOK_DESCRIPTION)).toBeInTheDocument();
  const text = pageText();
  expect(text).toContain("Free"); // collaboration_mode label
  expect(text).toContain("Private"); // visibility label
  expect(text).toMatch(/2018/); // created_at
  expect(text).toMatch(/2026/); // modified_at
  expect(text).toContain(OWNER_ID);
  expect(text).toContain(CO_AUTHOR_ID);
  expect(screen.getAllByText(/state notes/i).length).toBeGreaterThan(0);
  // Re-bound by `016`: the per-chapter region is delivered, so it is located by its own
  // label rather than by the stub's owner-naming sentence.
  expect(text).toMatch(/continuity/i);
}

describe("BookStatePage — the author's own system prompt", () => {
  it("DoD-1: on mount the page loads the caller's own prompt ALONGSIDE the book state, and shows its text in the editor", async () => {
    renderPage(STATE_ROUTE);

    // Both loadables are kicked off by the same mount, addressed to the book in the URL.
    // The prompt endpoint names no user, so the value is the caller's own by construction.
    await waitFor(() => expect(vi.mocked(booksApi.getOwnSystemPrompt)).toHaveBeenCalled());
    expect(vi.mocked(booksApi.getOwnSystemPrompt).mock.calls[0][0]).toBe(BOOK_ID);
    expect(vi.mocked(booksApi.getBookDetail)).toHaveBeenCalled();

    // The stored text is in the editor...
    const editor = await waitForEditor(STORED_PROMPT);
    expect(editor).toBeEnabled();
    // ...and the book state it loads alongside is on screen too.
    await expectBookStateContentIntact();
  });

  it("DoD-2: a member with no stored prompt gets an empty, EDITABLE field — not an error and not a read-only placeholder", async () => {
    // The normal starting state of every book for every author: 200 with an empty prompt
    // and no row yet, never a failure.
    vi.mocked(booksApi.getOwnSystemPrompt).mockResolvedValue(
      makePrompt({ system_prompt: "", modified_at: null }),
    );

    renderPage(STATE_ROUTE);

    await waitFor(() => expect(queryPromptEditor()).not.toBeNull());
    const editor = promptEditor();

    expect(editor.value).toBe("");
    expect(editor).toBeEnabled();
    expect(editor.readOnly).toBe(false);

    // No failure copy and no retry — an empty prompt is not an error...
    expect(promptRegion().textContent ?? "").not.toMatch(/failed|could not|couldn'?t|unavailable/i);
    expect(screen.queryAllByRole("button", { name: /retry|try again/i })).toHaveLength(0);

    // ...and the field genuinely accepts text.
    typeInto(editor, "A first prompt.");
    await waitFor(() => expect(promptEditor().value).toBe("A first prompt."));
  });

  it("DoD-3: saving sends the draft, and the editor then shows what the SERVER returned rather than the local draft", async () => {
    renderPage(STATE_ROUTE);
    const editor = await waitForEditor(STORED_PROMPT);

    typeInto(editor, "What the author typed.");
    await waitFor(() => expect(promptEditor().value).toBe("What the author typed."));

    // The stored value deliberately differs from the draft, so "shows the server's answer"
    // is distinguishable from "kept the draft".
    vi.mocked(booksApi.updateOwnSystemPrompt).mockResolvedValue(
      makePrompt({ system_prompt: "What the server stored.", modified_at: "2026-07-29T09:30:00Z" }),
    );

    fireEvent.click(saveControl());

    await waitFor(() => expect(vi.mocked(booksApi.updateOwnSystemPrompt)).toHaveBeenCalled());
    const [bookIdArg, bodyArg] = vi.mocked(booksApi.updateOwnSystemPrompt).mock.calls[0];
    expect(bookIdArg).toBe(BOOK_ID);
    expect(bodyArg).toEqual({ system_prompt: "What the author typed." });

    await waitFor(() => expect(promptEditor().value).toBe("What the server stored."));
  });

  it("DoD-4: the save control is unavailable while the draft still matches the loaded value", async () => {
    renderPage(STATE_ROUTE);
    await waitForEditor(STORED_PROMPT);

    expect(saveIsUnavailable()).toBe(true);

    // Editing opens the gate...
    typeInto(promptEditor(), `${STORED_PROMPT} And never head-hop.`);
    await waitFor(() => expect(saveIsUnavailable()).toBe(false));

    // ...and restoring the loaded value closes it again.
    typeInto(promptEditor(), STORED_PROMPT);
    await waitFor(() => expect(saveIsUnavailable()).toBe(true));
  });

  it("DoD-4: the save control is unavailable while a save is in flight", async () => {
    renderPage(STATE_ROUTE);
    const editor = await waitForEditor(STORED_PROMPT);

    typeInto(editor, "Edited text.");
    await waitFor(() => expect(saveIsUnavailable()).toBe(false));

    // A save that never settles keeps the submit in flight.
    vi.mocked(booksApi.updateOwnSystemPrompt).mockReturnValue(
      new Promise<BookAuthorPromptResponse>(() => {}),
    );
    fireEvent.click(saveControl());

    await waitFor(() => expect(saveIsUnavailable()).toBe(true));
    expect(vi.mocked(booksApi.updateOwnSystemPrompt)).toHaveBeenCalledTimes(1);
  });

  it("DoD-5: emptying the editor is a legal save that clears the prompt", async () => {
    renderPage(STATE_ROUTE);
    const editor = await waitForEditor(STORED_PROMPT);

    typeInto(editor, "");
    await waitFor(() => expect(saveIsUnavailable()).toBe(false));

    vi.mocked(booksApi.updateOwnSystemPrompt).mockResolvedValue(
      makePrompt({ system_prompt: "", modified_at: "2026-07-29T10:00:00Z" }),
    );

    fireEvent.click(saveControl());

    await waitFor(() => expect(vi.mocked(booksApi.updateOwnSystemPrompt)).toHaveBeenCalled());
    expect(vi.mocked(booksApi.updateOwnSystemPrompt).mock.calls[0][1]).toEqual({
      system_prompt: "",
    });
    await waitFor(() => expect(promptEditor().value).toBe(""));
  });

  it("DoD-5: no delete control is offered — an empty save is the only way to clear the prompt", async () => {
    renderPage(STATE_ROUTE);
    const editor = await waitForEditor(STORED_PROMPT);

    // Make the section's own subtree locatable (its save control is rendered).
    typeInto(editor, "Edited text.");
    await waitFor(() => expect(saveIsUnavailable()).toBe(false));

    const destructive = Array.from(promptRegion().querySelectorAll("button")).filter((button) =>
      /delete|remove|clear|discard/i.test(button.textContent ?? ""),
    );
    expect(destructive).toHaveLength(0);

    // Nor may any control elsewhere on the page offer to delete the prompt.
    const promptDestructive = Array.from(document.querySelectorAll("button")).filter((button) => {
      const label = button.textContent ?? "";
      return /prompt/i.test(label) && /delete|remove|clear|discard/i.test(label);
    });
    expect(promptDestructive).toHaveLength(0);
  });

  it("DoD-6: a refused save surfaces the server's message and leaves the draft intact", async () => {
    renderPage(STATE_ROUTE);
    const editor = await waitForEditor(STORED_PROMPT);

    typeInto(editor, "Typed but refused — do not lose me.");
    await waitFor(() => expect(saveIsUnavailable()).toBe(false));

    vi.mocked(booksApi.updateOwnSystemPrompt).mockRejectedValue(
      new ApiError(403, "You are not a member of this book"),
    );

    fireEvent.click(saveControl());

    // The server's own words reach the author...
    await waitFor(() => expect(pageText()).toContain("You are not a member of this book"));
    // ...and nothing typed is lost.
    expect(promptEditor().value).toBe("Typed but refused — do not lose me.");
  });

  it("DoD-7: a failed prompt load renders its own error branch and leaves the rest of the Book-state view whole", async () => {
    // Only the prompt trio fails; the book-state trio succeeds. The two are independent.
    vi.mocked(booksApi.getOwnSystemPrompt).mockRejectedValue(
      new ApiError(500, "Prompt service unavailable"),
    );

    renderPage(STATE_ROUTE);

    await waitFor(() => expect(vi.mocked(booksApi.getOwnSystemPrompt)).toHaveBeenCalled());

    // Half one — the prompt section is in its error branch: something failure-shaped is
    // on screen (the spec pins no wording) and no editor is bound to data never read.
    await waitFor(() =>
      expect(pageText()).toMatch(
        /(Prompt service unavailable|failed|could not|couldn'?t|unavailable|error|retry|try again)/i,
      ),
    );
    expect(queryPromptEditor()).toBeNull();

    // Half two — the book state loaded fine and still renders in full.
    await expectBookStateContentIntact();
  });

  it("DoD-8: the section says the prompt is the caller's own and not shared with co-authors", async () => {
    renderPage(STATE_ROUTE);
    await waitForEditor(STORED_PROMPT);

    // The copy that replaces UC-093's book-wide framing: this prompt belongs to the
    // caller, and co-authors neither see nor share it.
    expect(pageText()).toMatch(/prompt/i);
    expect(pageText()).toMatch(
      /(your own|yours alone|only you|only yours|your personal|not shared|no[- ]one else|each author|every author|per[\s-]author)/i,
    );

    // ...and the section never frames it as one prompt the whole book shares.
    const regionText = promptRegion().textContent ?? "";
    expect(regionText).not.toMatch(/book[\s-]wide/i);
    expect(regionText).not.toMatch(/applies to (all|every|everyone)/i);
  });

  it("DoD-9: the prompt editor is editable, and the surface's editable regions are exactly it and 016's state-notes editor — nothing else", async () => {
    renderPage(STATE_ROUTE);
    const editor = await waitForEditor(STORED_PROMPT);

    // Half one — the region this step adds really is editable. UNCHANGED.
    expect(editor).toBeEnabled();
    expect(editor.readOnly).toBe(false);
    typeInto(editor, "Edited by the author.");
    await waitFor(() => expect(promptEditor().value).toBe("Edited by the author."));

    // Half two — the CLOSED SET of editable controls. Re-bound by `016` (D8: this feature
    // replaces the "State notes" stub with a real editor, so a second editable region on
    // this page is now correct): the set is widened by exactly that one region and stays
    // closed, so a third editable control anywhere on the surface still fails this case.
    await waitFor(() => {
      expect(queryStateNotesEditor()).not.toBeNull();
    });
    const editable = editableControls();
    expect(editable).toHaveLength(2);
    expect(editable).toContain(promptEditor());
    expect(editable).toContain(stateNotesEditor());

    // The read-only content it sits among is untouched.
    await expectBookStateContentIntact();
  });
});
