/**
 * Content-pane subject routes — 010.working-page / 004.content-pane-subject-and-buffer,
 * DoD-4 (route half) · DoD-5 · DoD-6.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 004):
 *   const WorkRoutes: FunctionComponent   // observer; /:bookId shell + nine subject children
 *   interface SubjectPlaceholderPageProps { heading: string; owner: string }
 *   const SubjectPlaceholderPage: FunctionComponent<SubjectPlaceholderPageProps>
 *
 * The `/:bookId` shell (WorkspaceShell, from step 002) loads the book via
 * `api/books.getBookDetail` and renders its `<Outlet/>` inside the content pane
 * (the `main` landmark) once ready; each subject child renders a
 * `SubjectPlaceholderPage` there. Routes are basename-stripped (`/bk-1/chapters`,
 * not `/work/bk-1/chapters`).
 *
 * Every expected value comes from the spec, never from code:
 *   - the owner label each route names is pinned VERBATIM by the step file /
 *     `004.context.md` -> "Owner labels": chapters + one chapter -> `014.chapter-skeleton`;
 *     characters / locations / facts + one codex entry -> `013.codex`; variants + one
 *     chapter's variants -> `018.chapter-history-variants`;
 *   - `/:bookId/chats` no longer renders a content-pane view: under
 *     011.chat-panel / 004 (DoD-5, retarget 2026-07-26) it redirects to the
 *     book-state route (`/:bookId/state`), so no `011.chat-panel` surface appears in
 *     the content pane (US-105.AC-3);
 *   - there is NO `chat/:id` route, so a chat-id path falls through to the in-pane
 *     not-found page (US-105.AC-3) — its back-to-bookshelf anchor (href "/") from
 *     step 001 identifies it;
 *   - the owner labels are asserted INSIDE the content pane (`main`), because the
 *     chat-pane region also renders under `011.chat-panel`, so scoping keeps the
 *     content-pane assertions unambiguous.
 *
 * `api/books` is mocked module-factory form (never `fetch`); the shell subtree reads
 * only `getBookDetail`, but `WorkRoutes` also imports the Book-state page, so the
 * two option arrays are supplied too (their real spec-data pairs) to keep the module
 * shape intact. `api/chats` is likewise mocked module-factory form: the `/:bookId`
 * shell now owns the chat pane and starts a chat load on mount, so every export the
 * pane imports is enumerated and the two list calls resolve empty (no real fetch).
 * `globals: false`.
 */
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import { useLocation } from "react-router-dom";
import type { BookDetailResponse } from "../../src/types/books";
import type { CodexEntryResponse } from "../../src/types/codex";
import * as booksApi from "../../src/api/books";
import * as chatsApi from "../../src/api/chats";
import * as codexApi from "../../src/api/codex";
import { WorkRoutes } from "../../src/work/routes";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module. `getBookDetail` powers the shell
// load; the option arrays are the real spec-data pairs (copied verbatim from
// `src/api/books.ts`) that the Book-state page — imported by `WorkRoutes` — depends on.
// 021.per-author-system-prompt / step 006: the Book-state page's mount effect now also
// loads the caller's own prompt through this module, so both prompt exports must be
// enumerated here too — a factory that omits one strips it to `undefined`.
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

// The `/:bookId` shell (mounted by WorkRoutes) owns the chat pane and starts a chat
// load on mount, reading through this module — enumerate every export it imports.
vi.mock("../../src/api/chats", () => ({
  listChats: vi.fn(),
  createChat: vi.fn(),
  updateChat: vi.fn(),
  getChat: vi.fn(),
  listModelOptions: vi.fn(),
}));

// 013.codex / step 011: `/characters`, `/locations` and `/facts` no longer render a
// placeholder — they render the codex list page, which loads through `api/codex`. Mocked
// module-factory form (never `fetch`) so those three routes resolve locally; the other
// placeholder routes below never reach this module.
vi.mock("../../src/api/codex", () => ({
  listCodexEntries: vi.fn(),
  getCodexEntry: vi.fn(),
  createCodexEntry: vi.fn(),
  updateCodexEntry: vi.fn(),
}));

/** One codex entry per kind, so a route showing the wrong kind is visible. */
const CODEX_ENTRIES: CodexEntryResponse[] = [
  {
    id: "ce-char-1",
    book_id: "bk-1",
    kind: "character",
    name: "Aria Stormcrow",
    body: "A sellsword out of the reach.",
    archived: false,
    author_id: "u-1",
    modified_by: null,
    created_at: null,
    modified_at: "2026-03-04T09:00:00Z",
  },
  {
    id: "ce-loc-1",
    book_id: "bk-1",
    kind: "location",
    name: "Winterfell Keep",
    body: "A granite hall above hot springs.",
    archived: false,
    author_id: "u-1",
    modified_by: null,
    created_at: null,
    modified_at: "2026-03-04T09:00:00Z",
  },
  {
    id: "ce-fact-1",
    book_id: "bk-1",
    kind: "fact",
    name: null,
    body: "The moon is red every seventh night.",
    archived: false,
    author_id: "u-1",
    modified_by: null,
    created_at: null,
    modified_at: "2026-03-04T09:00:00Z",
  },
];

/** A fully-typed BookDetailResponse fixture; only the id matters here. */
function makeDetail(id: string): BookDetailResponse {
  return {
    id,
    owner_id: "u-1",
    title: "The Long Novel",
    description: "",
    collaboration_mode: "free",
    visibility: "private",
    state: "active",
    created_at: null,
    modified_at: null,
    members: [],
  };
}

/** Render the whole WORK route table at a basename-stripped subject route. */
function renderAt(route: string): void {
  renderWithProviders(<WorkRoutes />, { route });
}

/** Reports the router's current pathname, so a redirect is observable. */
function LocationProbe(): ReactElement {
  const location = useLocation();
  return <span data-testid="pathname">{location.pathname}</span>;
}

beforeEach(() => {
  // `restoreMocks` wipes the implementation between tests — the shell needs a resolved
  // book so it reaches `ready` and renders its `<Outlet/>` (the subject placeholder).
  vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail("bk-1"));
  // The Book-state page (the `/state` route + the `/chats` redirect target) loads the
  // caller's own prompt on mount; a prompt-shaped resolved value keeps that load off the
  // network and out of the rejected-promise path. `""` + `modified_at: null` is the
  // "no stored prompt" wire shape.
  vi.mocked(booksApi.getOwnSystemPrompt).mockResolvedValue({
    book_id: "bk-1",
    system_prompt: "",
    modified_at: null,
  });
  vi.mocked(booksApi.updateOwnSystemPrompt).mockResolvedValue({
    book_id: "bk-1",
    system_prompt: "",
    modified_at: null,
  });
  // The shell's chat-pane load resolves empty so no real fetch fires.
  vi.mocked(chatsApi.listChats).mockResolvedValue([]);
  vi.mocked(chatsApi.listModelOptions).mockResolvedValue([]);
  // The codex list page answers with the book's entries OF THE REQUESTED KIND.
  vi.mocked(codexApi.listCodexEntries).mockImplementation((_bookId, kind) =>
    Promise.resolve(CODEX_ENTRIES.filter((entry) => entry.kind === kind)),
  );
  // 013.codex step 012: `/codex/:id` now loads the routed entry through this call.
  vi.mocked(codexApi.getCodexEntry).mockResolvedValue(CODEX_ENTRIES[0]);
});

describe("subject list routes render a read-only empty state naming their owner (DoD-5)", () => {
  // 013.codex step 011 fills the three codex routes, so their rows moved to the block below;
  // chapters and variants are still placeholders and stay here unchanged.
  const LIST_ROUTES: Array<[string, RegExp]> = [
    ["/bk-1/chapters", /014\.chapter-skeleton/],
    ["/bk-1/variants", /018\.chapter-history-variants/],
  ];

  for (const [route, ownerLabel] of LIST_ROUTES) {
    it(`DoD-5: ${route} renders, inside the content pane, an empty state naming ${ownerLabel.source}`, async () => {
      renderAt(route);
      // Scope to the content pane (`main`): the chat-pane region also renders under
      // `011.chat-panel`, so only the placeholder inside `main` counts.
      const main = await screen.findByRole("main");
      expect(await within(main).findByText(ownerLabel)).toBeInTheDocument();
    });
  }
});

describe("the three codex list routes render the codex list page (010 DoD-5, superseded by 013.codex/011 DoD-1)", () => {
  // These three rows used to assert a `013.codex` placeholder. Feature 013 step 011 replaces
  // those elements with the codex list page bound to its kind, so the new truth is: the route
  // lists that kind's entries and no placeholder naming `013.codex` survives in the pane.
  const CODEX_LIST_ROUTES: Array<[string, RegExp]> = [
    ["/bk-1/characters", /Aria Stormcrow/],
    ["/bk-1/locations", /Winterfell Keep/],
    ["/bk-1/facts", /moon is red/i],
  ];

  for (const [route, entryMarker] of CODEX_LIST_ROUTES) {
    it(`DoD-1: ${route} renders the codex list page, not a 013.codex placeholder`, async () => {
      renderAt(route);
      const main = await screen.findByRole("main");
      expect(await within(main).findByText(entryMarker)).toBeInTheDocument();
      expect(within(main).queryByText(/013\.codex/)).toBeNull();
    });
  }
});

describe("the /chats deep link redirects out of the content pane (011.chat-panel/004 DoD-5)", () => {
  it("DoD-5: /:bookId/chats redirects to the book-state route and shows no chats view in the content pane", async () => {
    // Retargeted 2026-07-26: step 004 turns `/:bookId/chats` from a content-pane
    // placeholder into a redirect to `/:bookId/state` (step file Interface intent ->
    // `routes.tsx`; DoD-5). Expected target route + the absence of a content-pane
    // chats surface both come from the spec, not from code.
    renderWithProviders(
      <>
        <WorkRoutes />
        <LocationProbe />
      </>,
      { route: "/bk-1/chats" },
    );

    // The deep link neither 404s nor lands a chat surface in the content pane: it
    // redirects to the book-state route.
    await waitFor(() => expect(screen.getByTestId("pathname").textContent).toBe("/bk-1/state"));

    // No `011.chat-panel` chats placeholder survives inside the content pane.
    const main = await screen.findByRole("main");
    expect(within(main).queryByText(/011\.chat-panel/)).toBeNull();
  });
});

describe("subject item routes resolve into the content pane, not the catch-all (DoD-6)", () => {
  // 013.codex step 012 fills `/codex/:id` with the real entry page, so its row moved to the
  // block below; chapter and variants item routes are still placeholders and stay here.
  const ITEM_ROUTES: Array<[string, RegExp]> = [
    ["/bk-1/chapter/ch-1", /014\.chapter-skeleton/],
    ["/bk-1/variants/ch-9", /018\.chapter-history-variants/],
  ];

  for (const [route, ownerLabel] of ITEM_ROUTES) {
    it(`DoD-6: ${route} renders the placeholder naming ${ownerLabel.source}, not the not-found page`, async () => {
      renderAt(route);
      const main = await screen.findByRole("main");

      // The placeholder resolved inside the content pane...
      expect(await within(main).findByText(ownerLabel)).toBeInTheDocument();

      // ...and it is NOT the catch-all: the not-found page's back-to-bookshelf anchor
      // (href "/") is absent from the content pane.
      const backAnchors = within(main)
        .queryAllByRole("link")
        .filter((anchor) => anchor.getAttribute("href") === "/");
      expect(backAnchors).toHaveLength(0);
    });
  }
});

describe("the codex item route renders the codex entry page (010 DoD-6, superseded by 013.codex/012 DoD-1)", () => {
  // This case used to assert a `013.codex` placeholder at `/bk-1/codex/ce-1`. Feature 013 step
  // 012 points that route at the real entry page, so the new truth is: the route loads the
  // routed entry and renders it, and no placeholder naming `013.codex` survives in the pane.
  it("DoD-1: /bk-1/codex/ce-1 renders the loaded entry, not a 013.codex placeholder", async () => {
    renderAt("/bk-1/codex/ce-1");
    const main = await screen.findByRole("main");

    await waitFor(() =>
      expect(within(main).queryAllByDisplayValue(/Aria Stormcrow/).length).toBeGreaterThan(0),
    );
    expect(within(main).queryByText(/013\.codex/)).toBeNull();
  });
});

describe("no chat/:id route (DoD-4, route half)", () => {
  it("DoD-4: a /:bookId/chat/<id> path falls through to the in-pane not-found page", async () => {
    renderAt("/bk-1/chat/c-1");
    const main = await screen.findByRole("main");

    // The not-found page renders in the content pane: its back-to-bookshelf anchor
    // (href "/", from step 001) is the identifying signal.
    await waitFor(() => {
      const links = within(main).queryAllByRole("link");
      expect(links.some((anchor) => anchor.getAttribute("href") === "/")).toBe(true);
    });

    // No subject placeholder resolved for a chat id: the chat owner label does not
    // appear inside the content pane (it lives only in the chat-pane slot).
    expect(within(main).queryByText(/011\.chat-panel/)).toBeNull();
  });
});
