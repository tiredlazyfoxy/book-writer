/**
 * The book-settings system-prompt editor — 021.per-author-system-prompt /
 * 005.settings-page-editor,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-8.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 005):
 *   const BookSettingsPage: FunctionComponent  // observer, no props; reads :bookId
 *   const SystemPromptCard: FunctionComponent<{ state: BookSettingsPageState; bookId: string }>
 *   getOwnSystemPrompt(bookId, signal?): Promise<BookAuthorPromptResponse>
 *   updateOwnSystemPrompt(bookId, body: UpdateBookAuthorPromptRequest, signal?)
 *                                      : Promise<BookAuthorPromptResponse>
 *   interface BookAuthorPromptResponse { book_id: string; system_prompt: string;
 *                                        modified_at: ISODateString | null }
 * The page renders the card from its EXISTING mount effect, so mounting the page
 * under `/books/:bookId/settings` is the whole arrangement.
 *
 * `api/books` is mocked (never `fetch`). A module factory replaces the WHOLE
 * module and this page reaches a good many of its exports, so the factory is an
 * `importOriginal` SPREAD with `vi.fn()` overrides for every call the page can
 * make: a spread cannot silently strip an export the page needs (which would
 * make the page fail to render for the wrong reason), while the overrides still
 * guarantee no call escapes to the network. `../../src/auth` is stubbed with the
 * signed-in book owner so the owner-only settings surface renders; `ApiError` is
 * the real class from `api/client`.
 *
 * Expected values come from the spec, never from the page's code:
 *   - a stored prompt is what `GET /api/books/{id}/system-prompt` returned
 *     (`context.md` -> "The wire contract") — DoD-1;
 *   - `""` + `modified_at: null` is the NORMAL starting state of every book for
 *     every author, so it renders an empty EDITABLE field, not an error — DoD-2;
 *   - after a save the surface shows what the server returned, not the draft
 *     (`context.md` -> "the backend is the source of truth") — DoD-3, which is why
 *     the stored value in that case deliberately differs from what was typed;
 *   - the save control is gated on "dirty AND not in flight" — DoD-4;
 *   - an empty save is legal and clears the prompt, and no DELETE verb exists, so
 *     no delete control may be offered (`context.md` -> decision 6) — DoD-5;
 *   - a refusal shows the server's own message and loses nothing typed — DoD-6;
 *   - a failed load shows the error branch with a way to retry and binds no editor
 *     to stale data — DoD-7;
 *   - the copy says the prompt is the author's own, not the book's — this is the
 *     wording that REPLACES UC-093's book-wide framing (`context.md` -> Goal) — DoD-8.
 *
 * The spec pins no exact labels, so the editor is located as the prompt-labelled
 * `<textarea>` and the save control as the nearest `save`-named button above it —
 * never by test id or DOM shape.
 *
 * `globals: false`: every primitive is imported explicitly.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import type { CurrentUser } from "../../src/auth";
import type { BookAuthorPromptResponse, BookDetailResponse } from "../../src/types/books";
import { ApiError } from "../../src/api/client";
import * as booksApi from "../../src/api/books";
import * as auth from "../../src/auth";
import { BookSettingsPage } from "../../src/user/pages/BookSettingsPage";
import { renderWithProviders } from "../support/render";

// `importOriginal` spread + explicit `vi.fn()` overrides: every function the page
// or its state can call is replaced (so nothing reaches the network), while every
// other export — the Select option constants among them — keeps its real value.
vi.mock("../../src/api/books", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/books")>();
  return {
    ...actual,
    getBookDetail: vi.fn(),
    getOwnSystemPrompt: vi.fn(),
    updateOwnSystemPrompt: vi.fn(),
    archiveBook: vi.fn(),
    unarchiveBook: vi.fn(),
    transferOwnership: vi.fn(),
    addMember: vi.fn(),
    removeMember: vi.fn(),
    setVisibility: vi.fn(),
  };
});

// The settings page aggregates owner-only capabilities; stub the session as the
// book's owner so nothing is hidden for a reason this step does not own.
vi.mock("../../src/auth", () => ({
  getToken: vi.fn(),
  getRefreshToken: vi.fn(),
  setTokens: vi.fn(),
  setAccessToken: vi.fn(),
  getCurrentUser: vi.fn(),
  logout: vi.fn(),
}));

/** A snowflake id as it crosses the wire: a string beyond 2^53. */
const BOOK_ID = "9007199254740993";
const OWNER_ID = "u-owner-77";
const OWNER: CurrentUser = { user_id: OWNER_ID, username: "author", role: "author" };

const STORED_PROMPT = "Write in close third person, past tense.";

function makeDetail(overrides: Partial<BookDetailResponse> = {}): BookDetailResponse {
  return {
    id: BOOK_ID,
    owner_id: OWNER_ID,
    title: "The Winds of Winter",
    description: "A sprawling saga told across nine kingdoms.",
    collaboration_mode: "free",
    visibility: "private",
    state: "active",
    created_at: "2018-05-01T10:00:00Z",
    modified_at: "2026-07-01T15:00:00Z",
    members: [],
    ...overrides,
  };
}

function makePrompt(overrides: Partial<BookAuthorPromptResponse> = {}): BookAuthorPromptResponse {
  return {
    book_id: BOOK_ID,
    system_prompt: STORED_PROMPT,
    modified_at: "2026-07-01T12:00:00Z",
    ...overrides,
  };
}

/** Mounts the page under its own route so `useParams().bookId` resolves. */
function renderPage(): void {
  renderWithProviders(
    <Routes>
      <Route path="/books/:bookId/settings" element={<BookSettingsPage />} />
    </Routes>,
    { route: `/books/${BOOK_ID}/settings` },
  );
}

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
 * The multi-line prompt editor: the `<textarea>` whose own labelling names a
 * prompt, or the page's sole textarea when nothing is labelled that way.
 */
function queryPromptEditor(): HTMLTextAreaElement | null {
  const areas = Array.from(document.querySelectorAll("textarea"));
  if (areas.length === 0) return null;
  const named = areas.filter((area) => /prompt/i.test(labelTextFor(area)));
  if (named.length > 0) return named[0];
  return areas.length === 1 ? areas[0] : null;
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

/** True when the author cannot save right now — the control is absent or disabled. */
function saveIsUnavailable(): boolean {
  const button = findSaveControl();
  return button === null || button.disabled;
}

/** The prompt card's own subtree: the smallest ancestor of the editor holding its save control. */
function promptRegion(): HTMLElement {
  const editor = promptEditor();
  let node: HTMLElement | null = editor.parentElement;
  while (node !== null && node !== document.body) {
    if (saveButtonsIn(node).length > 0) return node;
    node = node.parentElement;
  }
  return editor.parentElement ?? document.body;
}

function pageText(): string {
  return document.body.textContent ?? "";
}

function type(field: HTMLTextAreaElement, value: string): void {
  fireEvent.change(field, { target: { value } });
}

/** Waits for the mount load to settle with the prompt on screen. */
async function waitForEditor(value: string): Promise<HTMLTextAreaElement> {
  await waitFor(() => {
    expect(queryPromptEditor()).not.toBeNull();
    expect(promptEditor().value).toBe(value);
  });
  return promptEditor();
}

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests — arrange the happy path;
  // individual cases override.
  vi.mocked(auth.getCurrentUser).mockReturnValue(OWNER);
  vi.mocked(auth.getToken).mockReturnValue("token");
  vi.mocked(booksApi.getBookDetail).mockResolvedValue(makeDetail());
  vi.mocked(booksApi.getOwnSystemPrompt).mockResolvedValue(makePrompt());
  vi.mocked(booksApi.updateOwnSystemPrompt).mockResolvedValue(makePrompt());
});

describe("BookSettingsPage — the author's own system prompt", () => {
  it("DoD-1: on mount the page loads the caller's own prompt for this book and shows its text in the editor", async () => {
    renderPage();

    await waitFor(() => expect(vi.mocked(booksApi.getOwnSystemPrompt)).toHaveBeenCalled());
    // Addressed to the book in the URL — the endpoint names no user, so the value
    // is the caller's own by construction.
    expect(vi.mocked(booksApi.getOwnSystemPrompt).mock.calls[0][0]).toBe(BOOK_ID);

    const editor = await waitForEditor(STORED_PROMPT);
    expect(editor).toBeEnabled();
  });

  it("DoD-2: an author with no stored prompt gets an empty, EDITABLE field — not an error state", async () => {
    vi.mocked(booksApi.getOwnSystemPrompt).mockResolvedValue(
      makePrompt({ system_prompt: "", modified_at: null }),
    );

    renderPage();

    await waitFor(() => expect(queryPromptEditor()).not.toBeNull());
    const editor = promptEditor();

    expect(editor.value).toBe("");
    expect(editor).toBeEnabled();
    expect(editor.readOnly).toBe(false);

    // The empty response is the normal starting state, so the card shows no
    // failure and offers no retry.
    expect(promptRegion().textContent ?? "").not.toMatch(/failed|could not|couldn't|unavailable/i);
    expect(screen.queryAllByRole("button", { name: /retry|try again/i })).toHaveLength(0);

    // And it is genuinely editable.
    type(editor, "A first prompt.");
    await waitFor(() => expect(promptEditor().value).toBe("A first prompt."));
  });

  it("DoD-3: saving sends the draft, and the editor then shows what the SERVER returned rather than the local draft", async () => {
    renderPage();
    const editor = await waitForEditor(STORED_PROMPT);

    type(editor, "What the author typed.");
    await waitFor(() => expect(promptEditor().value).toBe("What the author typed."));

    // The stored value deliberately differs from the draft, so "shows the server's
    // answer" is distinguishable from "kept the draft".
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
    renderPage();
    await waitForEditor(STORED_PROMPT);

    expect(saveIsUnavailable()).toBe(true);

    // Editing opens the gate...
    type(promptEditor(), `${STORED_PROMPT} And never head-hop.`);
    await waitFor(() => expect(saveIsUnavailable()).toBe(false));

    // ...and restoring the loaded value closes it again.
    type(promptEditor(), STORED_PROMPT);
    await waitFor(() => expect(saveIsUnavailable()).toBe(true));
  });

  it("DoD-4: the save control is unavailable while a save is in flight", async () => {
    renderPage();
    const editor = await waitForEditor(STORED_PROMPT);

    type(editor, "Edited text.");
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
    renderPage();
    const editor = await waitForEditor(STORED_PROMPT);

    type(editor, "");
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

  it("DoD-5: no delete control is offered anywhere on the surface — an empty save is the only way to clear", async () => {
    renderPage();
    const editor = await waitForEditor(STORED_PROMPT);

    // Make the card's own subtree locatable (its save control is rendered).
    type(editor, "Edited text.");
    await waitFor(() => expect(saveIsUnavailable()).toBe(false));

    const region = promptRegion();
    const destructive = Array.from(region.querySelectorAll("button")).filter((button) =>
      /delete|remove|clear|discard/i.test(button.textContent ?? ""),
    );
    expect(destructive).toHaveLength(0);

    // Nor anywhere else on the page may a control offer to delete the prompt.
    const promptDestructive = Array.from(document.querySelectorAll("button")).filter((button) => {
      const label = button.textContent ?? "";
      return /prompt/i.test(label) && /delete|remove|clear|discard/i.test(label);
    });
    expect(promptDestructive).toHaveLength(0);
  });

  it("DoD-6: a refused save surfaces the server's message and leaves the draft intact", async () => {
    renderPage();
    const editor = await waitForEditor(STORED_PROMPT);

    type(editor, "Typed but refused — do not lose me.");
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

  it("DoD-7: a failed load renders an error with a way to retry, and binds no editor to stale data", async () => {
    vi.mocked(booksApi.getOwnSystemPrompt).mockRejectedValue(
      new ApiError(500, "Prompt service unavailable"),
    );

    renderPage();

    await waitFor(() => expect(vi.mocked(booksApi.getOwnSystemPrompt)).toHaveBeenCalled());

    // The error branch is on screen — not a blank region, not an editor.
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: /retry|try again/i }).length).toBeGreaterThan(0),
    );
    expect(queryPromptEditor()).toBeNull();
    expect(pageText().trim()).not.toBe("");

    // The retry really retries: a second read succeeds and the editor appears.
    vi.mocked(booksApi.getOwnSystemPrompt).mockResolvedValue(
      makePrompt({ system_prompt: "Recovered text." }),
    );
    fireEvent.click(screen.getAllByRole("button", { name: /retry|try again/i })[0]);

    await waitForEditor("Recovered text.");
  });

  it("DoD-8: the surface tells the author the prompt is theirs alone, never a book-wide one", async () => {
    renderPage();
    await waitForEditor(STORED_PROMPT);

    // The copy that replaces UC-093's book-wide framing: this prompt belongs to
    // the author, and every author of the book keeps their own.
    expect(pageText()).toMatch(/prompt/i);
    expect(pageText()).toMatch(
      /(your own|yours alone|only you|only yours|your personal|each author|every author|per[\s-]author)/i,
    );

    // ...and the card never frames it as the book's single shared prompt.
    const regionText = promptRegion().textContent ?? "";
    expect(regionText).not.toMatch(
      /(book[\s-]wide|shared (system )?prompt|applies to (all|every|everyone)|everyone'?s)/i,
    );
  });
});
