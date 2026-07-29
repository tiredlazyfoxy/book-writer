/**
 * The per-author system prompt — wire functions + page state.
 * 021.per-author-system-prompt / 005.settings-page-editor,
 * DoD-1 · DoD-2 · DoD-3 · DoD-4 · DoD-5 · DoD-6 · DoD-7 · DoD-9.
 *
 * Bound to the frozen signatures in status.md -> `## Skeleton` (step 005):
 *   interface BookAuthorPromptResponse { book_id: string; system_prompt: string;
 *                                        modified_at: ISODateString | null }   // no user_id
 *   interface UpdateBookAuthorPromptRequest { system_prompt: string }
 *   getOwnSystemPrompt(bookId: string, signal?): Promise<BookAuthorPromptResponse>
 *   updateOwnSystemPrompt(bookId: string, body: UpdateBookAuthorPromptRequest, signal?)
 *                                        : Promise<BookAuthorPromptResponse>
 *   class BookSettingsPageState { systemPrompt; systemPromptStatus; systemPromptError;
 *                                 systemPromptDraft; systemPromptServerErrors;
 *                                 systemPromptSubmitStatus;
 *                                 get systemPromptDirty; get canSaveSystemPrompt }
 *   loadSystemPrompt(state, bookId, signal?): Promise<void>
 *   saveSystemPrompt(state, bookId, signal?): Promise<void>   // no body param
 * and, from `context.md` -> the api layer:
 *   class ApiError extends Error { constructor(status, message, details?) }
 *   request<T>(url, opts): Promise<T>          // opts: { method?; body?; signal? }
 *
 * This spec deliberately mocks `api/client`'s `request` rather than `api/books`:
 * DoD-9 makes the wire module ITSELF the subject (the `assistantConfigApi.test.ts`
 * precedent — the one legitimate reason to test at the HTTP boundary), and driving
 * the state effects through the very same seam keeps one observable surface for
 * both halves. `fetch` is never touched. The `importOriginal` spread keeps the REAL
 * `ApiError` class, which DoD-6 needs.
 *
 * Expected values come from the spec, never from code:
 *   - the two paths and the two verbs are `context.md` -> "The wire contract"
 *     (`GET`/`PUT /api/books/{book_id}/system-prompt`, request body
 *     `{ "system_prompt": <str> }`), and `signal?` is the trailing argument
 *     everywhere (`context.md` -> frontend constraints) — DoD-9;
 *   - a response carries `book_id` / `system_prompt` / `modified_at` and NO
 *     `user_id`, ids as strings;
 *   - "no stored prompt" is a `200` with `""` + `modified_at: null` — a NORMAL
 *     state, never an error (DoD-2 / the wire contract's "a missing row is a 200");
 *   - after a save the surface adopts what the SERVER returned, not the draft
 *     (`context.md` -> "the backend is the source of truth") — DoD-3;
 *   - `""` is a legal save that clears the prompt, and there is no DELETE verb
 *     (`context.md` -> decision 6) — DoD-5;
 *   - a refusal leaves the draft intact (DoD-6), and the save-refusal holder is
 *     separate from the load trio's error (the frozen state shape).
 *
 * `globals: false`: every primitive is imported explicitly. `restoreMocks` wipes
 * implementations between tests, so each case arranges its own.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { BookAuthorPromptResponse } from "../../src/types/books";
import { ApiError, request } from "../../src/api/client";
import { getOwnSystemPrompt, updateOwnSystemPrompt } from "../../src/api/books";
import {
  BookSettingsPageState,
  loadSystemPrompt,
  saveSystemPrompt,
} from "../../src/user/pages/bookSettingsPageState";

// Module-factory mock with `importOriginal`: only `request` is replaced, so the
// real `ApiError` still propagates through the api functions and the effects.
vi.mock("../../src/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/client")>();
  return { ...actual, request: vi.fn() };
});

/** The options bag `request` accepts — read off the frozen signature itself. */
type ClientOpts = Parameters<typeof request>[1];

/** A snowflake id as it crosses the wire: a string beyond 2^53. */
const BOOK_ID = "9007199254740993";

/** The one path both verbs address (`context.md` -> "The wire contract"). */
const PROMPT_PATH = `/api/books/${BOOK_ID}/system-prompt`;

function makePrompt(overrides: Partial<BookAuthorPromptResponse> = {}): BookAuthorPromptResponse {
  return {
    book_id: BOOK_ID,
    system_prompt: "Write in close third person, past tense.",
    modified_at: "2026-07-01T12:00:00Z",
    ...overrides,
  };
}

/** The empty-prompt response: the normal starting state of every book for every author. */
function emptyPrompt(): BookAuthorPromptResponse {
  return makePrompt({ system_prompt: "", modified_at: null });
}

interface RecordedCall {
  url: string;
  opts: ClientOpts;
}

function recordedCalls(): RecordedCall[] {
  return vi.mocked(request).mock.calls.map(([url, opts]) => ({ url, opts }));
}

/** The single `request` call the subject under test must have made. */
function onlyCall(): RecordedCall {
  const calls = recordedCalls();
  expect(calls).toHaveLength(1);
  return calls[0];
}

/** An absent `method` is a GET, per fetch semantics. */
function methodOf(opts: ClientOpts): string {
  return (opts?.method ?? "GET").toUpperCase();
}

/** Lets a pending effect run its microtasks without settling anything. */
async function flush(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
}

/** A promise that never settles — keeps a trio in its in-flight state. */
function pending<T>(): Promise<T> {
  return new Promise<T>(() => {});
}

/** A state whose prompt trio has already loaded `text`, with the draft seeded. */
async function loadedState(text: string): Promise<BookSettingsPageState> {
  const state = new BookSettingsPageState();
  vi.mocked(request).mockResolvedValue(makePrompt({ system_prompt: text }));
  await loadSystemPrompt(state, BOOK_ID);
  vi.mocked(request).mockReset();
  return state;
}

beforeEach(() => {
  // `restoreMocks` wipes implementations between tests; a benign default keeps a
  // case that forgets to arrange from resolving `undefined` into the state.
  vi.mocked(request).mockResolvedValue(emptyPrompt());
});

describe("api/books — the caller's own system prompt (DoD-9)", () => {
  it("DoD-9: getOwnSystemPrompt GETs /api/books/<id>/system-prompt and forwards the abort signal", async () => {
    const stored = makePrompt();
    vi.mocked(request).mockResolvedValue(stored);
    const controller = new AbortController();

    const result = await getOwnSystemPrompt(BOOK_ID, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(PROMPT_PATH);
    expect(methodOf(opts)).toBe("GET");
    expect(opts?.body).toBeUndefined();
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(stored);
  });

  it("DoD-9: getOwnSystemPrompt addresses the book it was given, and works with no signal", async () => {
    vi.mocked(request).mockResolvedValue(makePrompt({ book_id: "42" }));

    const result = await getOwnSystemPrompt("42");

    const { url, opts } = onlyCall();
    expect(url).toBe("/api/books/42/system-prompt");
    expect(opts?.signal).toBeUndefined();
    expect(result.book_id).toBe("42");
  });

  it("DoD-9: updateOwnSystemPrompt PUTs the same path with { system_prompt }, forwards the signal and returns the STORED prompt", async () => {
    const stored = makePrompt({ system_prompt: "Stored by the server." });
    vi.mocked(request).mockResolvedValue(stored);
    const controller = new AbortController();

    const result = await updateOwnSystemPrompt(
      BOOK_ID,
      { system_prompt: "Sent by the author." },
      controller.signal,
    );

    const { url, opts } = onlyCall();
    expect(url).toBe(PROMPT_PATH);
    expect(methodOf(opts)).toBe("PUT");
    expect(opts?.body).toEqual({ system_prompt: "Sent by the author." });
    expect(opts?.signal).toBe(controller.signal);
    expect(result).toEqual(stored);
  });

  it("DoD-9: updateOwnSystemPrompt sends an empty prompt verbatim — `\"\"` is a value, not an omission", async () => {
    vi.mocked(request).mockResolvedValue(emptyPrompt());

    await updateOwnSystemPrompt(BOOK_ID, { system_prompt: "" });

    const { url, opts } = onlyCall();
    expect(url).toBe(PROMPT_PATH);
    expect(methodOf(opts)).toBe("PUT");
    expect(opts?.body).toEqual({ system_prompt: "" });
  });

  it("DoD-9: an ApiError from either function propagates rather than being swallowed", async () => {
    const err = new ApiError(403, "Forbidden");
    vi.mocked(request).mockRejectedValue(err);

    await expect(getOwnSystemPrompt(BOOK_ID)).rejects.toBe(err);
    await expect(updateOwnSystemPrompt(BOOK_ID, { system_prompt: "x" })).rejects.toBe(err);
  });
});

describe("bookSettingsPageState — loading the prompt (DoD-1, DoD-2, DoD-7)", () => {
  it("DoD-1: loadSystemPrompt reads the caller's own prompt for the given book and seeds the draft from it", async () => {
    const stored = makePrompt({ system_prompt: "Never break the fourth wall." });
    vi.mocked(request).mockResolvedValue(stored);
    const state = new BookSettingsPageState();
    const controller = new AbortController();

    await loadSystemPrompt(state, BOOK_ID, controller.signal);

    const { url, opts } = onlyCall();
    expect(url).toBe(PROMPT_PATH);
    expect(methodOf(opts)).toBe("GET");
    expect(opts?.signal).toBe(controller.signal);

    expect(state.systemPromptStatus).toBe("ready");
    expect(state.systemPrompt).toEqual(stored);
    expect(state.systemPromptDraft).toBe("Never break the fourth wall.");
    expect(state.systemPromptError).toBeNull();
  });

  it("DoD-1: the trio reports `loading` while the read is in flight, with no error set", async () => {
    vi.mocked(request).mockReturnValue(pending<BookAuthorPromptResponse>());
    const state = new BookSettingsPageState();

    void loadSystemPrompt(state, BOOK_ID);
    await flush();

    expect(state.systemPromptStatus).toBe("loading");
    expect(state.systemPromptError).toBeNull();
  });

  it("DoD-2: an author with no stored prompt lands in `ready` with an empty draft — an empty response is NOT an error state", async () => {
    vi.mocked(request).mockResolvedValue(emptyPrompt());
    const state = new BookSettingsPageState();

    await loadSystemPrompt(state, BOOK_ID);

    expect(state.systemPromptStatus).toBe("ready");
    expect(state.systemPromptStatus).not.toBe("error");
    expect(state.systemPromptError).toBeNull();
    expect(state.systemPromptDraft).toBe("");
    expect(state.systemPrompt?.system_prompt).toBe("");
    expect(state.systemPrompt?.modified_at).toBeNull();
  });

  it("DoD-7: a failed read leaves the trio in `error` with an author-facing message and NO stale prompt", async () => {
    vi.mocked(request).mockRejectedValue(new ApiError(500, "Prompt service unavailable"));
    const state = new BookSettingsPageState();

    await loadSystemPrompt(state, BOOK_ID);

    expect(state.systemPromptStatus).toBe("error");
    // The spec pins no exact wording, only that the error branch has something
    // author-facing to render.
    expect(typeof state.systemPromptError).toBe("string");
    expect(state.systemPromptError ?? "").not.toBe("");
    // Nothing to bind an editor to: the load produced no prompt at all.
    expect(state.systemPrompt).toBeNull();
    expect(state.systemPromptDraft).toBe("");
  });

  it("DoD-7: the failed read is retryable — a second call succeeds and clears the error", async () => {
    vi.mocked(request).mockRejectedValue(new ApiError(500, "Prompt service unavailable"));
    const state = new BookSettingsPageState();
    await loadSystemPrompt(state, BOOK_ID);
    expect(state.systemPromptStatus).toBe("error");

    vi.mocked(request).mockResolvedValue(makePrompt({ system_prompt: "Recovered text." }));
    await loadSystemPrompt(state, BOOK_ID);

    expect(state.systemPromptStatus).toBe("ready");
    expect(state.systemPromptError).toBeNull();
    expect(state.systemPromptDraft).toBe("Recovered text.");
  });

  it("DoD-7: a prompt failure never touches the book-detail trio (two independent loadables)", async () => {
    vi.mocked(request).mockRejectedValue(new ApiError(500, "Prompt service unavailable"));
    const state = new BookSettingsPageState();

    await loadSystemPrompt(state, BOOK_ID);

    expect(state.detailStatus).not.toBe("error");
    expect(state.detailError).toBeNull();
  });
});

describe("bookSettingsPageState — the save gate (DoD-4)", () => {
  it("DoD-4: saving is unavailable before the prompt has loaded", () => {
    const state = new BookSettingsPageState();

    expect(state.systemPromptStatus).toBe("idle");
    expect(state.canSaveSystemPrompt).toBe(false);
  });

  it("DoD-4: a draft equal to the loaded value is not dirty, so saving is unavailable", async () => {
    const state = await loadedState("Write in close third person.");

    expect(state.systemPromptDraft).toBe("Write in close third person.");
    expect(state.systemPromptDirty).toBe(false);
    expect(state.canSaveSystemPrompt).toBe(false);
  });

  it("DoD-4: an edited draft is dirty and saving becomes available; reverting it closes the gate again", async () => {
    const state = await loadedState("Write in close third person.");

    state.systemPromptDraft = "Write in first person.";
    expect(state.systemPromptDirty).toBe(true);
    expect(state.canSaveSystemPrompt).toBe(true);

    state.systemPromptDraft = "Write in close third person.";
    expect(state.systemPromptDirty).toBe(false);
    expect(state.canSaveSystemPrompt).toBe(false);
  });

  it("DoD-4: saving is unavailable while a save is in flight", async () => {
    const state = await loadedState("Original text.");
    state.systemPromptDraft = "Edited text.";
    expect(state.canSaveSystemPrompt).toBe(true);

    vi.mocked(request).mockReturnValue(pending<BookAuthorPromptResponse>());
    void saveSystemPrompt(state, BOOK_ID);
    await flush();

    expect(state.systemPromptSubmitStatus).toBe("loading");
    expect(state.canSaveSystemPrompt).toBe(false);
  });
});

describe("bookSettingsPageState — saving the prompt (DoD-3, DoD-5, DoD-6)", () => {
  it("DoD-3: the save sends the draft and then adopts the value the SERVER returned", async () => {
    const state = await loadedState("Original text.");
    state.systemPromptDraft = "What the author typed.";

    // The stored value deliberately differs from the draft, so adopting the
    // response is distinguishable from keeping the local draft.
    const stored = makePrompt({
      system_prompt: "What the server stored.",
      modified_at: "2026-07-29T09:30:00Z",
    });
    vi.mocked(request).mockResolvedValue(stored);

    await saveSystemPrompt(state, BOOK_ID);

    const { url, opts } = onlyCall();
    expect(url).toBe(PROMPT_PATH);
    expect(methodOf(opts)).toBe("PUT");
    expect(opts?.body).toEqual({ system_prompt: "What the author typed." });

    expect(state.systemPrompt).toEqual(stored);
    expect(state.systemPromptDraft).toBe("What the server stored.");
    expect(state.systemPromptSubmitStatus).toBe("ready");
    // Adopted, so nothing is left unsaved and the gate closes.
    expect(state.systemPromptDirty).toBe(false);
    expect(state.canSaveSystemPrompt).toBe(false);
  });

  it("DoD-3: the save takes the server's answer from the PUT itself — no follow-up read that could show neither value", async () => {
    const state = await loadedState("Original text.");
    state.systemPromptDraft = "Edited text.";
    vi.mocked(request).mockResolvedValue(makePrompt({ system_prompt: "Edited text." }));

    await saveSystemPrompt(state, BOOK_ID);

    const verbs = recordedCalls().map((call) => methodOf(call.opts));
    expect(verbs).toEqual(["PUT"]);
  });

  it("DoD-3: the save forwards the abort signal it was given", async () => {
    const state = await loadedState("Original text.");
    state.systemPromptDraft = "Edited text.";
    vi.mocked(request).mockResolvedValue(makePrompt({ system_prompt: "Edited text." }));
    const controller = new AbortController();

    await saveSystemPrompt(state, BOOK_ID, controller.signal);

    expect(onlyCall().opts?.signal).toBe(controller.signal);
  });

  it("DoD-5: emptying the editor is a legal, dirty save that sends `\"\"` and clears the stored prompt", async () => {
    const state = await loadedState("A prompt worth clearing.");

    state.systemPromptDraft = "";
    // No client-side validation exists: the empty string is a valid value.
    expect(state.systemPromptDirty).toBe(true);
    expect(state.canSaveSystemPrompt).toBe(true);

    const cleared = makePrompt({ system_prompt: "", modified_at: "2026-07-29T10:00:00Z" });
    vi.mocked(request).mockResolvedValue(cleared);

    await saveSystemPrompt(state, BOOK_ID);

    const { url, opts } = onlyCall();
    expect(url).toBe(PROMPT_PATH);
    expect(methodOf(opts)).toBe("PUT");
    expect(opts?.body).toEqual({ system_prompt: "" });

    expect(state.systemPrompt?.system_prompt).toBe("");
    expect(state.systemPromptDraft).toBe("");
    expect(state.systemPromptSubmitStatus).toBe("ready");
    expect(state.systemPromptServerErrors).toEqual({});
  });

  it("DoD-6: a refused save surfaces the server's message and leaves the draft intact", async () => {
    const state = await loadedState("Original text.");
    state.systemPromptDraft = "Typed but refused — do not lose me.";
    vi.mocked(request).mockRejectedValue(new ApiError(403, "You are not a member of this book"));

    await expect(saveSystemPrompt(state, BOOK_ID)).resolves.toBeUndefined();

    // Nothing the author typed is lost.
    expect(state.systemPromptDraft).toBe("Typed but refused — do not lose me.");
    // The stored value is still the last one the server confirmed.
    expect(state.systemPrompt?.system_prompt).toBe("Original text.");

    expect(state.systemPromptSubmitStatus).toBe("error");
    const messages = Object.values(state.systemPromptServerErrors);
    expect(messages.length).toBeGreaterThan(0);
    expect(messages.join(" ")).toContain("You are not a member of this book");
  });

  it("DoD-6: a save refusal is held apart from the load trio — the loaded prompt stays `ready`", async () => {
    const state = await loadedState("Original text.");
    state.systemPromptDraft = "Edited text.";
    vi.mocked(request).mockRejectedValue(new ApiError(422, "system_prompt is required"));

    await saveSystemPrompt(state, BOOK_ID);

    expect(state.systemPromptStatus).toBe("ready");
    expect(state.systemPromptError).toBeNull();
  });

  it("DoD-6: a following successful save clears the refusal and adopts the server's value", async () => {
    const state = await loadedState("Original text.");
    state.systemPromptDraft = "Edited text.";
    vi.mocked(request).mockRejectedValue(new ApiError(500, "Something went wrong"));
    await saveSystemPrompt(state, BOOK_ID);
    expect(state.systemPromptSubmitStatus).toBe("error");

    vi.mocked(request).mockResolvedValue(makePrompt({ system_prompt: "Edited text." }));
    await saveSystemPrompt(state, BOOK_ID);

    expect(state.systemPromptSubmitStatus).toBe("ready");
    expect(Object.values(state.systemPromptServerErrors).join(" ")).not.toContain(
      "Something went wrong",
    );
    expect(state.systemPrompt?.system_prompt).toBe("Edited text.");
  });
});
