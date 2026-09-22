/**
 * The codex entry page — 013.codex / 012.codex-entry-page, DoD-1 … DoD-13
 * (all thirteen are `[test]`; the step has no `[manual/live]` item).
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 012):
 *   type CodexEntryPageMode = "existing" | "blank"
 *   type CodexDraftField = "name" | "body"
 *   type ReconciliationSide = "server" | "draft"
 *   function parseCodexKind(value: string | null): CodexKind | null
 *   class CodexEntryPageState {
 *     constructor(bookId: string, entryId: string | null, initialKind?: CodexKind | null)
 *     readonly bookId; readonly mode; readonly initialKind; entryId;
 *     entry; entryStatus; entryError; saveStatus; saveError;
 *     nameDraft; bodyDraft; conflictEntry; isReconciling; evictedBufferKeys;
 *     get kind; get requiresName; get isDirty; get nameError; get isValid;
 *     get editability; get isReadOnly; get canSave; get bufferKey; get baseVersion;
 *     readonly applyDraft(field, text): void
 *   }
 *   loadCodexEntry(state, signal?): Promise<void>
 *   editCodexDraft(state, field, text): void
 *   saveCodexEntry(state, signal?): Promise<string | null>
 *   discardCodexDraft(state): void
 *   resolveCodexConflict(state, side, signal?): Promise<void>
 *   interface CodexEntryPageProps { mode: CodexEntryPageMode }
 *   const CodexEntryPage: FunctionComponent<CodexEntryPageProps>   // observer
 *
 * Every expected value comes from the STEP FILE's Definition of done / Interface intent and
 * `012.context.md`, never from code:
 *   - DoD-1: `/codex/:id` loads the entry and renders its name and body;
 *   - DoD-2: editing the body marks the page dirty and writes the buffer under the
 *     `(bookId, "codex-entry", id)` key with the entry's `modified_at` as `baseVersion`;
 *   - DoD-3: a buffer whose `baseVersion` MATCHES restores the buffered draft, not server text;
 *   - DoD-4: nothing reaches the server until Save — editing + navigating away writes nothing;
 *   - DoD-5: Save on an existing entry updates with the LOADED `modified_at` and clears the buffer;
 *   - DoD-6: a 409 renders the reconciliation view, server text BESIDE the buffered draft, with
 *     no auto-merge and no silent overwrite;
 *   - DoD-7: a buffer whose `baseVersion` no longer matches opens the reconciliation view on LOAD,
 *     without attempting a save;
 *   - DoD-8: taking the server's side discards the draft and clears the buffer; taking the draft's
 *     side re-saves against the NEW `modified_at` and succeeds;
 *   - DoD-9: an archived entry is read-only with `subject.ts:resolveEditability`'s exact reason and
 *     no save action;
 *   - DoD-10: a fact renders no name field and saves with no name; a character / location keeps
 *     Save disabled until a non-blank name is present;
 *   - DoD-11: the blank route creates with the kind from the query param, then navigates to the
 *     created entry's route;
 *   - DoD-12: a 403 surfaces the server's reason text (naming FEAT-010) and leaves the draft AND
 *     the buffer intact;
 *   - DoD-13: a buffer write reporting an eviction names the evicted buffers, and the CURRENT
 *     item's buffer is never the victim.
 * Routes here are basename-stripped (`/bk-1/codex/ce-1`, not `/work/bk-1/codex/ce-1`).
 *
 * Mocking: the `api/` module is mocked module-factory form, never `fetch`; `ApiError` is imported
 * REAL from `../../src/api/client` so 409 / 403 rejections are the genuine class. The page is
 * mounted DIRECTLY (never through `WorkRoutes`), so no `api/chats` / `api/books` mock is needed.
 * `restoreBuffer.ts` is used for real — it is complete and unit-tested, and
 * `tests/setup.ts` clears `localStorage` in `afterEach`, so every buffer is seeded in the test
 * that needs it. `globals: false`: every primitive is imported explicitly.
 */
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import type { RenderResult } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes, useLocation } from "react-router-dom";
import type { CodexEntryResponse, CodexKind } from "../../src/types/codex";
import { ApiError } from "../../src/api/client";
import * as codexApi from "../../src/api/codex";
import * as flagsApi from "../../src/api/flags";
import * as continuityApi from "../../src/api/continuity";

// HARNESS ONLY, added by `016.chapter-close-continuity`: the work surfaces this file
// mounts now read continuity data on mount — the Book-state landing reads the book's
// state notes and its per-chapter continuity, and a chapter surface reads that chapter's
// warnings and note changeset (`plan.md` -> Interface for `bookStatePageState.ts` /
// `chapterPageState.ts`). Whole-module factories (never `fetch`), armed with EMPTY
// fixtures in `beforeEach`, so those loads resolve locally instead of reaching the real
// HTTP client and leaving rejected promises behind. `vi.mock` is hoisted, so declaring
// these beside the imports they pair with is equivalent to declaring them below.
// NOTHING in this file asserts on either module — no assertion here changed.
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

/**
 * HARNESS ONLY (`016.chapter-close-continuity`): every continuity read the work surfaces
 * make on mount, answered with EMPTY fixtures. Nothing here is asserted on — the
 * Book-state surface's own content is on `plan.md` -> Test plan -> "Not tested
 * (deliberate)".
 */
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
import { readBuffer, restoreBufferKey, writeBuffer } from "../../src/work/restoreBuffer";
import {
  CodexEntryPageState,
  discardCodexDraft,
  editCodexDraft,
  loadCodexEntry,
  resolveCodexConflict,
  saveCodexEntry,
} from "../../src/work/pages/codexEntryPageState";
import { CodexEntryPage } from "../../src/work/pages/CodexEntryPage";
import { renderWithProviders } from "../support/render";

// A module-factory mock replaces the WHOLE module — enumerate every export the page /
// state layer reaches through its namespace import.
vi.mock("../../src/api/codex", () => ({
  listCodexEntries: vi.fn(),
  getCodexEntry: vi.fn(),
  createCodexEntry: vi.fn(),
  updateCodexEntry: vi.fn(),
}));

/* ------------------------------------------------------------------ fixtures */

const BOOK_ID = "bk-1";
const ENTRY_ID = "ce-1";

/** The `modified_at` the entry loads at — the base version of both the buffer and the save. */
const M1 = "2026-03-04T09:00:00Z";
/** A LATER server `modified_at`: someone else's save landed in between. */
const M2 = "2026-03-05T10:30:00Z";
/** The `modified_at` a successful save answers with. */
const M3 = "2026-03-06T11:45:00Z";
/** An OLDER base version — a buffer forked from it is stale against `M1`. */
const M0 = "2026-01-01T08:00:00Z";

/** The exact archived read-only reason `work/subject.ts:resolveEditability` already returns. */
const ARCHIVED_REASON =
  "This codex entry is archived and read-only; restore it to make changes.";

/** The proposal-mode refusal's wire reason + message (013 step 003; decision 3). */
const PROPOSAL_REASON = "proposal_mode_unsupported";
const PROPOSAL_MESSAGE =
  "Proposal mode holds a co-author's codex change for review, which FEAT-010 has not built yet.";

function makeEntry(overrides: Partial<CodexEntryResponse> & { id: string }): CodexEntryResponse {
  return {
    book_id: BOOK_ID,
    kind: "character",
    name: "Aria Stormcrow",
    body: "A sellsword out of the reach.",
    archived: false,
    author_id: "u-owner-1",
    modified_by: null,
    created_at: "2026-01-02T08:00:00Z",
    modified_at: M1,
    ...overrides,
  };
}

/** The entry as loaded: name "Aria Stormcrow", body mentioning "reach", version `M1`. */
const CHARACTER = makeEntry({ id: ENTRY_ID });
/** The server's CURRENT entry after somebody else saved: different body, version `M2`. */
const SERVER_V2 = makeEntry({
  id: ENTRY_ID,
  body: "A sellsword sworn to the granite Keep.",
  modified_at: M2,
});
/** A fact: no name at all (`name: null`). */
const FACT = makeEntry({
  id: "ce-fact-1",
  kind: "fact",
  name: null,
  body: "The moon is red every seventh night.",
});
/** An archived entry — read-only per the editability table. */
const ARCHIVED = makeEntry({ id: ENTRY_ID, archived: true });

/** The author's draft body — the distinctive word is "coin". */
const DRAFT_BODY = "A sellsword who answers only to coin.";
const DRAFT_BODY_RE = /answers only to coin/;
/** A body buffered on a previous visit — the distinctive word is "lantern". */
const BUFFERED_BODY = "A sellsword carrying a shuttered lantern.";
const BUFFERED_BODY_RE = /shuttered lantern/;

const SERVER_BODY_RE = /out of the reach/;
const SERVER_V2_BODY_RE = /sworn to the granite Keep/;

/** The entry a successful save answers with: the draft body at a fresh `modified_at`. */
const SAVED_V3 = makeEntry({ id: ENTRY_ID, body: DRAFT_BODY, modified_at: M3 });

type UserEvt = ReturnType<typeof userEvent.setup>;

/** This entry's buffer key, derived the way the spec keys it: (bookId, "codex-entry", id). */
function entryBufferKey(entryId: string = ENTRY_ID): string {
  return restoreBufferKey(BOOK_ID, "codex-entry", entryId);
}

/* ------------------------------------------------------------------- harness */

/** Reports the router's location so a post-create navigation is observable. */
function RouterProbe(): ReactElement {
  const location = useLocation();
  return (
    <>
      <span data-testid="pathname">{location.pathname}</span>
      <span data-testid="search">{location.search}</span>
    </>
  );
}

/** Mounts the entry page under both codex routes, beside a probe on the same router. */
function renderEntryPage(route: string): RenderResult {
  return renderWithProviders(
    <>
      <Routes>
        <Route path="/:bookId/codex/new" element={<CodexEntryPage mode="blank" />} />
        <Route path="/:bookId/codex/:id" element={<CodexEntryPage mode="existing" />} />
      </Routes>
      <RouterProbe />
    </>,
    { route },
  );
}

function currentPathname(): string {
  return screen.getByTestId("pathname").textContent ?? "";
}

/** Whether `matcher` is visible anywhere — as a field's value or as rendered text. */
function pageShows(matcher: RegExp): boolean {
  if (screen.queryAllByDisplayValue(matcher).length > 0) return true;
  return matcher.test(document.body.textContent ?? "");
}

async function waitForPage(matcher: RegExp): Promise<void> {
  await waitFor(() => expect(pageShows(matcher)).toBe(true));
}

/** Every textbox the page renders (a name input and a body editor are both `textbox`). */
function textboxes(): HTMLElement[] {
  return screen.queryAllByRole("textbox");
}

/** The name field, if the page renders one (a fact must not). */
function queryNameField(): HTMLElement | null {
  const labelled = screen.queryAllByRole("textbox", { name: /name/i });
  if (labelled.length > 0) return labelled[0];
  const placeheld = screen.queryAllByPlaceholderText(/name/i);
  if (placeheld.length > 0) return placeheld[0];
  const inputs = textboxes().filter((el) => el.tagName === "INPUT");
  return inputs.length > 0 ? inputs[0] : null;
}

function getNameField(): HTMLElement {
  const field = queryNameField();
  if (field === null) throw new Error("the entry page renders no name field");
  return field;
}

/** The body editor. When the current value is known, it identifies the field unambiguously. */
function getBodyField(currentValue?: string): HTMLElement {
  if (currentValue !== undefined) {
    const byValue = screen.queryAllByDisplayValue(currentValue);
    if (byValue.length > 0) return byValue[0];
  }
  const areas = textboxes().filter((el) => el.tagName === "TEXTAREA");
  if (areas.length > 0) return areas[0];
  const labelled = screen.queryAllByRole("textbox", { name: /body|content|text/i });
  if (labelled.length > 0) return labelled[0];
  const all = textboxes();
  if (all.length === 1) return all[0];
  throw new Error("the entry page renders no identifiable body editor");
}

/** Set a controlled field's value in one change event (a keystroke's path, once). */
function setField(field: HTMLElement, value: string): void {
  fireEvent.change(field, { target: { value } });
}

function isEnabled(control: HTMLElement): boolean {
  if ((control as HTMLButtonElement).disabled) return false;
  return control.getAttribute("aria-disabled") !== "true";
}

function querySaveControls(): HTMLElement[] {
  return [
    ...screen.queryAllByRole("button", { name: /save|create/i }),
    ...screen.queryAllByRole("link", { name: /save|create/i }),
  ];
}

function getEnabledSave(): HTMLElement {
  const enabled = querySaveControls().filter(isEnabled);
  if (enabled.length === 0) throw new Error("the entry page offers no enabled save action");
  return enabled[0];
}

/** Save is unavailable when it is either absent or present-but-disabled. */
function expectSaveUnavailable(): void {
  expect(querySaveControls().filter(isEnabled)).toHaveLength(0);
}

async function clickSave(user: UserEvt): Promise<void> {
  await user.click(getEnabledSave());
}

/**
 * The reconciliation view: the server's current text and the author's draft on screen at the
 * same time, with an explicit per-side choice and no merged single text.
 */
async function expectReconciliationView(
  serverText: RegExp,
  draftText: RegExp,
): Promise<void> {
  await waitFor(() => {
    expect(pageShows(serverText)).toBe(true);
    expect(pageShows(draftText)).toBe(true);
  });

  // An explicit per-side choice — two actions, so neither side is applied for the author.
  expect(screen.queryAllByRole("button").filter(isEnabled).length).toBeGreaterThanOrEqual(2);
}

/** No write of any kind reached the server. */
function expectNoWriteCall(): void {
  expect(vi.mocked(codexApi.createCodexEntry)).not.toHaveBeenCalled();
  expect(vi.mocked(codexApi.updateCodexEntry)).not.toHaveBeenCalled();
}

/** A loaded existing-entry state, ready for a state-level assertion. */
async function loadedState(entry: CodexEntryResponse = CHARACTER): Promise<CodexEntryPageState> {
  vi.mocked(codexApi.getCodexEntry).mockResolvedValue(entry);
  const state = new CodexEntryPageState(BOOK_ID, entry.id);
  await loadCodexEntry(state);
  return state;
}

beforeEach(() => {
  armContinuityReads();
  // `restoreMocks` wipes implementations between tests — re-arm every call the mount path
  // touches. The default answers describe a healthy, editable character entry at `M1`.
  vi.mocked(codexApi.getCodexEntry).mockResolvedValue(CHARACTER);
  vi.mocked(codexApi.updateCodexEntry).mockResolvedValue(SAVED_V3);
  vi.mocked(codexApi.createCodexEntry).mockResolvedValue(SAVED_V3);
  vi.mocked(codexApi.listCodexEntries).mockResolvedValue([]);
});

/* --------------------------------------------------- DoD-1: load and render */

describe("mounting on /codex/:id loads the entry (DoD-1)", () => {
  it("DoD-1 (UC-070 step 1 / US-105.AC-2): the page loads the routed entry and renders its name and body", async () => {
    renderEntryPage(`/${BOOK_ID}/codex/${ENTRY_ID}`);

    await waitFor(() => expect(vi.mocked(codexApi.getCodexEntry)).toHaveBeenCalled());
    const [bookId, entryId] = vi.mocked(codexApi.getCodexEntry).mock.calls[0];
    expect(bookId).toBe(BOOK_ID);
    expect(entryId).toBe(ENTRY_ID);

    // Both fields carry the loaded entry's content.
    await waitForPage(/Aria Stormcrow/);
    expect(pageShows(SERVER_BODY_RE)).toBe(true);
  });

  it("DoD-1: the loader drives the async trio and seeds both drafts from the server row", async () => {
    const state = await loadedState();

    expect(state.entryStatus).toBe("ready");
    expect(state.entryError).toBeNull();
    expect(state.entry).toEqual(CHARACTER);
    expect(state.nameDraft).toBe("Aria Stormcrow");
    expect(state.bodyDraft).toBe(CHARACTER.body);
    expect(state.isDirty).toBe(false);
    // The concurrency anchor is the loaded row's `modified_at`.
    expect(state.baseVersion).toBe(M1);
    expect(state.isReconciling).toBe(false);
  });
});

/* ----------------------------- DoD-2: editing writes the keyed restore buffer */

describe("editing the body writes the restore buffer (DoD-2)", () => {
  it("DoD-2 (UC-092 / US-107.AC-1): a body edit buffers under (bookId, codex-entry, id) with modified_at as baseVersion", async () => {
    renderEntryPage(`/${BOOK_ID}/codex/${ENTRY_ID}`);
    await waitForPage(SERVER_BODY_RE);

    setField(getBodyField(CHARACTER.body), DRAFT_BODY);

    await waitFor(() => expect(readBuffer(entryBufferKey())).not.toBeNull());
    const buffered = readBuffer(entryBufferKey());
    expect(buffered?.draft).toBe(DRAFT_BODY);
    // The base version is the entry's `modified_at` ISO string — not a number, not the id.
    expect(buffered?.baseVersion).toBe(M1);
  });

  it("DoD-2: editCodexDraft marks the page dirty and keys the buffer through state.bufferKey", async () => {
    const state = await loadedState();
    expect(state.isDirty).toBe(false);
    expect(state.bufferKey).toBe(entryBufferKey());

    editCodexDraft(state, "body", DRAFT_BODY);

    expect(state.bodyDraft).toBe(DRAFT_BODY);
    expect(state.isDirty).toBe(true);
    expect(readBuffer(entryBufferKey())?.draft).toBe(DRAFT_BODY);
    expect(readBuffer(entryBufferKey())?.baseVersion).toBe(M1);
  });

  it("DoD-2: applyDraft takes the same dirty/buffer path a keystroke does", async () => {
    // The apply-draft entry point exists so step 013 can hand the assistant's canvas draft to
    // the page; the DoD's buffer rule must hold for that route identically.
    const state = await loadedState();

    state.applyDraft("body", DRAFT_BODY);

    expect(state.bodyDraft).toBe(DRAFT_BODY);
    expect(state.isDirty).toBe(true);
    expect(readBuffer(entryBufferKey())?.draft).toBe(DRAFT_BODY);
    expect(readBuffer(entryBufferKey())?.baseVersion).toBe(M1);
  });
});

/* ------------------------- DoD-3: a matching buffer restores the buffered draft */

describe("a buffer whose baseVersion matches restores the draft (DoD-3)", () => {
  it("DoD-3 (US-107.AC-1 / US-107.AC-2): returning to the entry shows the buffered body, not the server text", async () => {
    // Seeded here: `tests/setup.ts` clears localStorage after every test.
    writeBuffer(entryBufferKey(), BUFFERED_BODY, M1);

    renderEntryPage(`/${BOOK_ID}/codex/${ENTRY_ID}`);

    await waitForPage(BUFFERED_BODY_RE);
    // The server text it forked from is NOT what the author is looking at.
    expect(screen.queryAllByDisplayValue(SERVER_BODY_RE)).toHaveLength(0);
  });

  it("DoD-3: a matching buffer restores the body draft and is NOT a reconciliation", async () => {
    writeBuffer(entryBufferKey(), BUFFERED_BODY, M1);

    const state = await loadedState();

    expect(state.bodyDraft).toBe(BUFFERED_BODY);
    expect(state.isDirty).toBe(true);
    expect(state.isReconciling).toBe(false);
    expect(state.conflictEntry).toBeNull();
    // The loaded server row is still the base the next save carries.
    expect(state.baseVersion).toBe(M1);
  });

  it("DoD-3: with no buffer at all the server text stands", async () => {
    const state = await loadedState();

    expect(readBuffer(entryBufferKey())).toBeNull();
    expect(state.bodyDraft).toBe(CHARACTER.body);
    expect(state.isReconciling).toBe(false);
  });
});

/* ------------------------------ DoD-4: nothing reaches the server until Save */

describe("nothing reaches the server until Save (DoD-4)", () => {
  it("DoD-4 (US-107.AC-4 / US-088.AC-2 / US-103.AC-3): editing and navigating away makes no write call", async () => {
    const { unmount } = renderEntryPage(`/${BOOK_ID}/codex/${ENTRY_ID}`);
    await waitForPage(SERVER_BODY_RE);

    setField(getBodyField(CHARACTER.body), DRAFT_BODY);
    const nameField = getNameField();
    setField(nameField, "Aria of the Reach");

    // Still nothing — the edits live in the draft and the buffer only.
    await waitFor(() => expect(readBuffer(entryBufferKey())?.draft).toBe(DRAFT_BODY));
    expectNoWriteCall();

    // The author navigates away: the page unmounts with the draft unsaved.
    unmount();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expectNoWriteCall();
    // ...and the draft survived in the buffer rather than reaching the server.
    expect(readBuffer(entryBufferKey())?.draft).toBe(DRAFT_BODY);
  });

  it("DoD-4: editCodexDraft is server-free — no api call of any kind", async () => {
    const state = await loadedState();
    vi.mocked(codexApi.getCodexEntry).mockClear();

    editCodexDraft(state, "name", "Aria of the Reach");
    editCodexDraft(state, "body", DRAFT_BODY);

    expectNoWriteCall();
    expect(vi.mocked(codexApi.getCodexEntry)).not.toHaveBeenCalled();
  });
});

/* ------------------- DoD-5: Save updates with the loaded version, clears buffer */

describe("Save on an existing entry updates and clears the buffer (DoD-5)", () => {
  it("DoD-5 (UC-070 / US-079.AC-1): Save calls update with the LOADED modified_at and clears the buffer", async () => {
    const user = userEvent.setup();
    renderEntryPage(`/${BOOK_ID}/codex/${ENTRY_ID}`);
    await waitForPage(SERVER_BODY_RE);

    setField(getBodyField(CHARACTER.body), DRAFT_BODY);
    await waitFor(() => expect(readBuffer(entryBufferKey())).not.toBeNull());

    await clickSave(user);

    await waitFor(() => expect(vi.mocked(codexApi.updateCodexEntry)).toHaveBeenCalled());
    const [bookId, entryId, payload] = vi.mocked(codexApi.updateCodexEntry).mock.calls[0];
    expect(bookId).toBe(BOOK_ID);
    expect(entryId).toBe(ENTRY_ID);
    expect(payload.body).toBe(DRAFT_BODY);
    expect(payload.expected_modified_at).toBe(M1);

    // The draft is on the server now, so the buffer that protected it is gone.
    await waitFor(() => expect(readBuffer(entryBufferKey())).toBeNull());
  });

  it("DoD-5: a successful save reports saved and adopts the response's modified_at as the next base", async () => {
    const state = await loadedState();
    editCodexDraft(state, "body", DRAFT_BODY);

    const navigateTo = await saveCodexEntry(state);

    expect(vi.mocked(codexApi.updateCodexEntry)).toHaveBeenCalledTimes(1);
    expect(state.saveStatus).toBe("saved");
    expect(state.saveError).toBeNull();
    expect(readBuffer(entryBufferKey())).toBeNull();
    // An update navigates nowhere (only a create does).
    expect(navigateTo).toBeNull();

    // `012.context.md` -> the response's `modified_at` is the new base version, or the NEXT
    // save 409s against a value the client itself produced.
    expect(state.baseVersion).toBe(M3);
    editCodexDraft(state, "body", "A sellsword who answers to nobody.");
    await saveCodexEntry(state);
    const secondPayload = vi.mocked(codexApi.updateCodexEntry).mock.calls[1][2];
    expect(secondPayload.expected_modified_at).toBe(M3);
  });

  it("DoD-5: discarding a draft clears the buffer and restores the loaded text (no server call)", async () => {
    const state = await loadedState();
    editCodexDraft(state, "body", DRAFT_BODY);
    expect(readBuffer(entryBufferKey())).not.toBeNull();

    discardCodexDraft(state);

    expect(state.bodyDraft).toBe(CHARACTER.body);
    expect(state.isDirty).toBe(false);
    expect(readBuffer(entryBufferKey())).toBeNull();
    expectNoWriteCall();
  });
});

/* --------------------------------- DoD-6: a 409 becomes the reconciliation view */

describe("a 409 from Save renders the reconciliation view (DoD-6)", () => {
  it("DoD-6: the server's current text is shown BESIDE the buffered draft, with no auto-merge", async () => {
    const user = userEvent.setup();
    // The load answers the entry at `M1`; the post-409 re-fetch answers the server's CURRENT row.
    vi.mocked(codexApi.getCodexEntry)
      .mockResolvedValueOnce(CHARACTER)
      .mockResolvedValue(SERVER_V2);
    vi.mocked(codexApi.updateCodexEntry).mockRejectedValue(
      new ApiError(409, "Conflict", {
        detail: { reason: "stale_modified_at", message: "The entry changed since you loaded it." },
      }),
    );

    renderEntryPage(`/${BOOK_ID}/codex/${ENTRY_ID}`);
    await waitForPage(SERVER_BODY_RE);

    setField(getBodyField(CHARACTER.body), DRAFT_BODY);
    await clickSave(user);

    // Both sides are on screen at once, with an explicit per-side choice.
    await expectReconciliationView(SERVER_V2_BODY_RE, DRAFT_BODY_RE);

    // No silent overwrite: exactly one update attempt, and no retry behind the author's back.
    expect(vi.mocked(codexApi.updateCodexEntry)).toHaveBeenCalledTimes(1);
    // No auto-merge: the draft is intact, not spliced with the server's text.
    expect(pageShows(DRAFT_BODY_RE)).toBe(true);
  });

  it("DoD-6: the 409 re-fetches the server entry into conflictEntry and raises the reconciling flag", async () => {
    const state = await loadedState();
    editCodexDraft(state, "body", DRAFT_BODY);
    vi.mocked(codexApi.getCodexEntry).mockResolvedValue(SERVER_V2);
    vi.mocked(codexApi.updateCodexEntry).mockRejectedValue(
      new ApiError(409, "Conflict", {
        detail: { reason: "stale_modified_at", message: "The entry changed since you loaded it." },
      }),
    );

    await saveCodexEntry(state);

    expect(state.isReconciling).toBe(true);
    expect(state.conflictEntry).toEqual(SERVER_V2);
    // The author's draft is held beside it, untouched and unmerged.
    expect(state.bodyDraft).toBe(DRAFT_BODY);
    expect(vi.mocked(codexApi.updateCodexEntry)).toHaveBeenCalledTimes(1);
  });
});

/* ------------------- DoD-7: a stale buffer reconciles on load, without a save */

describe("a stale buffer opens the reconciliation view on load (DoD-7)", () => {
  it("DoD-7: a buffer whose baseVersion no longer matches reconciles directly, attempting no save", async () => {
    // The buffer forked from `M0`; the server now says `M1`.
    writeBuffer(entryBufferKey(), BUFFERED_BODY, M0);

    renderEntryPage(`/${BOOK_ID}/codex/${ENTRY_ID}`);

    await expectReconciliationView(SERVER_BODY_RE, BUFFERED_BODY_RE);
    // The mismatch was detected client-side: nothing was sent to be refused.
    expectNoWriteCall();
  });

  it("DoD-7: loadCodexEntry sets conflictEntry from the loaded row and never calls update", async () => {
    writeBuffer(entryBufferKey(), BUFFERED_BODY, M0);

    const state = await loadedState();

    expect(state.isReconciling).toBe(true);
    expect(state.conflictEntry).toEqual(CHARACTER);
    expect(state.bodyDraft).toBe(BUFFERED_BODY);
    expect(state.saveStatus).toBe("idle");
    expectNoWriteCall();
  });
});

/* ------------------------------------- DoD-8: resolving by taking one side */

describe("resolving a reconciliation by taking one side (DoD-8)", () => {
  /** Drive the state into the reconciliation view through the 409 path. */
  async function reconcilingState(): Promise<CodexEntryPageState> {
    const state = await loadedState();
    editCodexDraft(state, "body", DRAFT_BODY);
    vi.mocked(codexApi.getCodexEntry).mockResolvedValue(SERVER_V2);
    vi.mocked(codexApi.updateCodexEntry).mockRejectedValueOnce(
      new ApiError(409, "Conflict", {
        detail: { reason: "stale_modified_at", message: "The entry changed since you loaded it." },
      }),
    );
    await saveCodexEntry(state);
    expect(state.isReconciling).toBe(true);
    return state;
  }

  it("DoD-8: taking the SERVER's side discards the draft and clears the buffer", async () => {
    const state = await reconcilingState();
    expect(readBuffer(entryBufferKey())).not.toBeNull();

    await resolveCodexConflict(state, "server");

    // The server's text won; the author's draft is gone, along with its buffer.
    expect(state.bodyDraft).toBe(SERVER_V2.body);
    expect(readBuffer(entryBufferKey())).toBeNull();
    expect(state.isReconciling).toBe(false);
    // Discarding is local — nothing was written back to the server.
    expect(vi.mocked(codexApi.updateCodexEntry)).toHaveBeenCalledTimes(1);
  });

  it("DoD-8: taking the DRAFT's side re-saves against the NEW modified_at and succeeds", async () => {
    const state = await reconcilingState();
    vi.mocked(codexApi.updateCodexEntry).mockResolvedValue(SAVED_V3);

    await resolveCodexConflict(state, "draft");

    // The second attempt carries the server's CURRENT version — this is what stops an
    // infinite 409 loop.
    await waitFor(() => expect(vi.mocked(codexApi.updateCodexEntry)).toHaveBeenCalledTimes(2));
    const secondPayload = vi.mocked(codexApi.updateCodexEntry).mock.calls[1][2];
    expect(secondPayload.expected_modified_at).toBe(M2);
    expect(secondPayload.body).toBe(DRAFT_BODY);

    // ...and it succeeded: the view is left, the save reports saved, the buffer is cleared.
    expect(state.saveStatus).toBe("saved");
    expect(state.isReconciling).toBe(false);
    expect(state.saveError).toBeNull();
    expect(readBuffer(entryBufferKey())).toBeNull();
  });
});

/* --------------------------------------------- DoD-9: an archived entry is read-only */

describe("an archived entry is read-only (DoD-9)", () => {
  it("DoD-9: the page shows resolveEditability's exact reason and offers no save action", async () => {
    vi.mocked(codexApi.getCodexEntry).mockResolvedValue(ARCHIVED);

    renderEntryPage(`/${BOOK_ID}/codex/${ENTRY_ID}`);

    await waitFor(() =>
      expect(document.body.textContent ?? "").toContain(ARCHIVED_REASON),
    );
    expectSaveUnavailable();
  });

  it("DoD-9: the state resolves the archived verdict through subject.ts, verbatim", async () => {
    const state = await loadedState(ARCHIVED);

    expect(state.isReadOnly).toBe(true);
    expect(state.editability.editable).toBe("none");
    expect(state.editability.readOnlyReason).toBe(ARCHIVED_REASON);
    expect(state.canSave).toBe(false);
  });

  it("DoD-9: a non-archived entry is editable whole, with no read-only reason", async () => {
    const state = await loadedState();

    expect(state.isReadOnly).toBe(false);
    expect(state.editability.editable).toBe("whole");
    expect(state.editability.readOnlyReason).toBeNull();
    expect(state.canSave).toBe(true);
  });
});

/* ------------------------------- DoD-10: the kind/name rule on the surface */

describe("the kind decides whether a name field exists (DoD-10)", () => {
  it("DoD-10 (US-078.AC-2): a fact renders NO name field", async () => {
    vi.mocked(codexApi.getCodexEntry).mockResolvedValue(FACT);

    renderEntryPage(`/${BOOK_ID}/codex/${FACT.id}`);

    await waitForPage(/moon is red/i);
    // No name-labelled field, and only one editable field on the page: the body.
    expect(screen.queryAllByRole("textbox", { name: /name/i })).toHaveLength(0);
    expect(textboxes()).toHaveLength(1);
  });

  it("DoD-10 (US-078.AC-2): a fact saves with no name", async () => {
    const user = userEvent.setup();
    vi.mocked(codexApi.getCodexEntry).mockResolvedValue(FACT);

    renderEntryPage(`/${BOOK_ID}/codex/${FACT.id}`);
    await waitForPage(/moon is red/i);

    setField(getBodyField(FACT.body), "The moon is red every ninth night.");
    await clickSave(user);

    await waitFor(() => expect(vi.mocked(codexApi.updateCodexEntry)).toHaveBeenCalled());
    const payload = vi.mocked(codexApi.updateCodexEntry).mock.calls[0][2];
    expect(payload.name ?? null).toBeNull();
    expect(payload.body).toBe("The moon is red every ninth night.");
  });

  it("DoD-10: a fact's state requires no name and is valid without one", async () => {
    const state = await loadedState(FACT);

    expect(state.kind).toBe("fact");
    expect(state.requiresName).toBe(false);
    expect(state.nameError).toBeNull();
    expect(state.isValid).toBe(true);
    expect(state.canSave).toBe(true);
  });

  const NAMED_KINDS: CodexKind[] = ["character", "location"];

  for (const kind of NAMED_KINDS) {
    it(`DoD-10 (US-078.AC-1): a ${kind} keeps Save disabled until a non-blank name is present`, async () => {
      const entry = makeEntry({ id: ENTRY_ID, kind, name: "Aria Stormcrow" });
      vi.mocked(codexApi.getCodexEntry).mockResolvedValue(entry);

      renderEntryPage(`/${BOOK_ID}/codex/${ENTRY_ID}`);
      await waitForPage(/Aria Stormcrow/);

      // Emptied: no save.
      setField(getNameField(), "");
      await waitFor(() => expectSaveUnavailable());

      // Whitespace is still blank.
      setField(getNameField(), "   ");
      await waitFor(() => expectSaveUnavailable());

      // A real name unlocks it.
      setField(getNameField(), "Aria of the Reach");
      await waitFor(() =>
        expect(querySaveControls().filter(isEnabled).length).toBeGreaterThanOrEqual(1),
      );
      expectNoWriteCall();
    });

    it(`DoD-10: a ${kind} state reports a name error and refuses to save while the name is blank`, async () => {
      const entry = makeEntry({ id: ENTRY_ID, kind, name: "Aria Stormcrow" });
      const state = await loadedState(entry);

      expect(state.requiresName).toBe(true);

      editCodexDraft(state, "name", "   ");
      expect(state.nameError).not.toBeNull();
      expect(state.isValid).toBe(false);
      expect(state.canSave).toBe(false);

      editCodexDraft(state, "name", "Aria of the Reach");
      expect(state.nameError).toBeNull();
      expect(state.isValid).toBe(true);
      expect(state.canSave).toBe(true);
    });
  }
});

/* ------------------------- DoD-11: the blank route creates, then navigates */

describe("the blank route creates with the query param's kind (DoD-11)", () => {
  it("DoD-11 (UC-069 / UC-076 precondition): a blank location creates with kind=location and navigates to the new entry", async () => {
    const user = userEvent.setup();
    const created = makeEntry({
      id: "ce-new-9",
      kind: "location",
      name: "The Glass Ford",
      body: "A shallow crossing under white cliffs.",
      modified_at: null,
    });
    vi.mocked(codexApi.createCodexEntry).mockResolvedValue(created);
    vi.mocked(codexApi.getCodexEntry).mockResolvedValue(created);

    renderEntryPage(`/${BOOK_ID}/codex/new?kind=location`);

    // A blank entry contacts nothing on mount — there is no row to fetch.
    await waitFor(() => expect(textboxes().length).toBeGreaterThan(0));
    expect(vi.mocked(codexApi.getCodexEntry)).not.toHaveBeenCalled();

    setField(getNameField(), "The Glass Ford");
    setField(getBodyField(), "A shallow crossing under white cliffs.");
    await clickSave(user);

    await waitFor(() => expect(vi.mocked(codexApi.createCodexEntry)).toHaveBeenCalled());
    const [bookId, payload] = vi.mocked(codexApi.createCodexEntry).mock.calls[0];
    expect(bookId).toBe(BOOK_ID);
    expect(payload.kind).toBe("location");
    expect(payload.name).toBe("The Glass Ford");
    expect(payload.body).toBe("A shallow crossing under white cliffs.");
    // An update was never attempted for a row that did not exist.
    expect(vi.mocked(codexApi.updateCodexEntry)).not.toHaveBeenCalled();

    // ...and the author lands on the created entry's own route.
    await waitFor(() => expect(currentPathname()).toBe(`/${BOOK_ID}/codex/ce-new-9`));
  });

  it("DoD-11 (US-078.AC-2): a blank fact creates with kind=fact and no name field", async () => {
    const user = userEvent.setup();
    const created = makeEntry({
      id: "ce-new-fact",
      kind: "fact",
      name: null,
      body: "Iron rusts red in the salt marsh.",
      modified_at: null,
    });
    vi.mocked(codexApi.createCodexEntry).mockResolvedValue(created);
    vi.mocked(codexApi.getCodexEntry).mockResolvedValue(created);

    renderEntryPage(`/${BOOK_ID}/codex/new?kind=fact`);

    await waitFor(() => expect(textboxes().length).toBeGreaterThan(0));
    expect(screen.queryAllByRole("textbox", { name: /name/i })).toHaveLength(0);
    expect(textboxes()).toHaveLength(1);

    setField(getBodyField(), "Iron rusts red in the salt marsh.");
    await clickSave(user);

    await waitFor(() => expect(vi.mocked(codexApi.createCodexEntry)).toHaveBeenCalled());
    const payload = vi.mocked(codexApi.createCodexEntry).mock.calls[0][1];
    expect(payload.kind).toBe("fact");
    expect(payload.name ?? null).toBeNull();
    expect(payload.body).toBe("Iron rusts red in the salt marsh.");

    await waitFor(() => expect(currentPathname()).toBe(`/${BOOK_ID}/codex/ce-new-fact`));
  });

  it("DoD-11: a blank state settles ready without contacting the server, and creates on save", async () => {
    const created = makeEntry({ id: "ce-new-9", kind: "character", modified_at: null });
    vi.mocked(codexApi.createCodexEntry).mockResolvedValue(created);
    const state = new CodexEntryPageState(BOOK_ID, null, "character");

    expect(state.mode).toBe("blank");
    expect(state.kind).toBe("character");
    expect(state.bufferKey).toBeNull();

    await loadCodexEntry(state);
    expect(state.entryStatus).toBe("ready");
    expect(state.entry).toBeNull();
    expect(vi.mocked(codexApi.getCodexEntry)).not.toHaveBeenCalled();

    editCodexDraft(state, "name", "Aria Stormcrow");
    editCodexDraft(state, "body", DRAFT_BODY);
    const navigateTo = await saveCodexEntry(state);

    // The create's route is returned for the caller to navigate to (basename-stripped).
    expect(navigateTo).toBe(`/${BOOK_ID}/codex/ce-new-9`);
    expect(state.entryId).toBe("ce-new-9");
  });
});

/* ------------------------------ DoD-12: a 403 surfaces the server's reason */

describe("a 403 surfaces the server's reason and keeps the draft (DoD-12)", () => {
  /** The wire body step 003 sends for a refusal: `{"detail": {"reason": …, "message": …}}`. */
  function proposalRefusal(): ApiError {
    return new ApiError(403, "Forbidden", {
      detail: { reason: PROPOSAL_REASON, message: PROPOSAL_MESSAGE },
    });
  }

  it("DoD-12 (decision 3): the proposal-mode refusal naming FEAT-010 is shown, draft and buffer intact", async () => {
    const user = userEvent.setup();
    vi.mocked(codexApi.updateCodexEntry).mockRejectedValue(proposalRefusal());

    renderEntryPage(`/${BOOK_ID}/codex/${ENTRY_ID}`);
    await waitForPage(SERVER_BODY_RE);

    setField(getBodyField(CHARACTER.body), DRAFT_BODY);
    await waitFor(() => expect(readBuffer(entryBufferKey())).not.toBeNull());

    await clickSave(user);

    // The server's own reason text reaches the author — including the FEAT-010 naming.
    await waitFor(() => expect(document.body.textContent ?? "").toMatch(/FEAT-010/));

    // The refusal cost the author nothing: the draft is still in the editor...
    expect(pageShows(DRAFT_BODY_RE)).toBe(true);
    // ...and its buffer survives, so navigating away still restores it.
    expect(readBuffer(entryBufferKey())?.draft).toBe(DRAFT_BODY);
    expect(readBuffer(entryBufferKey())?.baseVersion).toBe(M1);
  });

  it("DoD-12: the refusal lands in saveError (not in the field validation), and is not a reconciliation", async () => {
    const state = await loadedState();
    editCodexDraft(state, "body", DRAFT_BODY);
    vi.mocked(codexApi.updateCodexEntry).mockRejectedValue(proposalRefusal());

    await saveCodexEntry(state);

    expect(state.saveStatus).toBe("error");
    expect(state.saveError ?? "").toMatch(/FEAT-010/);
    // Server errors are merged separately from local validation.
    expect(state.nameError).toBeNull();
    // A 403 is not a version conflict — no reconciliation view, no re-fetch.
    expect(state.isReconciling).toBe(false);
    expect(state.conflictEntry).toBeNull();
    // The draft and its buffer are untouched.
    expect(state.bodyDraft).toBe(DRAFT_BODY);
    expect(readBuffer(entryBufferKey())?.draft).toBe(DRAFT_BODY);
  });
});

/* ------------------------------------ DoD-13: eviction is surfaced, never self */

describe("a buffer write that evicted other buffers tells the author (DoD-13)", () => {
  /** Another item's buffer, old enough to be the eviction candidate. */
  const VICTIM_KEY = restoreBufferKey(BOOK_ID, "codex-entry", "ce-other-7");

  /** Make `localStorage.setItem` refuse `key` once with a quota error, then behave. */
  function failWithQuotaOnce(key: string): void {
    const original = localStorage.setItem.bind(localStorage);
    let budget = 1;
    vi.spyOn(Storage.prototype, "setItem").mockImplementation((k: string, v: string) => {
      if (k === key && budget > 0) {
        budget -= 1;
        const err = new Error("quota");
        err.name = "QuotaExceededError";
        throw err;
      }
      original(k, v);
    });
  }

  it("DoD-13: the evicted buffer keys are named to the author, and the current item's buffer survives", async () => {
    writeBuffer(VICTIM_KEY, "Another entry's unsaved draft.", M1);

    renderEntryPage(`/${BOOK_ID}/codex/${ENTRY_ID}`);
    await waitForPage(SERVER_BODY_RE);

    failWithQuotaOnce(entryBufferKey());
    setField(getBodyField(CHARACTER.body), DRAFT_BODY);

    // The author is told WHICH buffer was lost.
    await waitFor(() => expect(document.body.textContent ?? "").toContain(VICTIM_KEY));

    // The victim is gone; the buffer being written is never the victim.
    expect(readBuffer(VICTIM_KEY)).toBeNull();
    expect(readBuffer(entryBufferKey())?.draft).toBe(DRAFT_BODY);
  });

  it("DoD-13: the state records the evicted keys and never its own", async () => {
    const state = await loadedState();
    writeBuffer(VICTIM_KEY, "Another entry's unsaved draft.", M1);

    failWithQuotaOnce(entryBufferKey());
    editCodexDraft(state, "body", DRAFT_BODY);

    expect(state.evictedBufferKeys).toContain(VICTIM_KEY);
    expect(state.evictedBufferKeys).not.toContain(entryBufferKey());
    expect(readBuffer(entryBufferKey())?.draft).toBe(DRAFT_BODY);
  });

  it("DoD-13: an ordinary write reports no eviction", async () => {
    const state = await loadedState();

    editCodexDraft(state, "body", DRAFT_BODY);

    expect(state.evictedBufferKeys).toEqual([]);
  });
});
