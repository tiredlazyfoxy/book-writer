import { makeAutoObservable, runInAction } from "mobx";
import * as codexApi from "../../api/codex";
import { ApiError } from "../../api/client";
import type { CodexEntryResponse, CodexKind } from "../../types/codex";

/**
 * Page state for `CodexListPage` — the three codex list routes
 * (`/work/:bookId/characters` · `/locations` · `/facts`, UC-071 / US-080.AC-1 /
 * US-105.AC-1), held via `useState(() => new CodexListPageState(kind, initialNeedle))`.
 *
 * Holds one async-resource trio (`entries` / `entriesStatus` / `entriesError`),
 * the route-fixed `kind`, the committed search `needle` (the value the last load
 * used — i.e. the URL's `q`) and the `draftNeedle` the search input binds to.
 * Nothing derived is stored: `isEmpty` is a pure `get` computed.
 *
 * `kind` is supplied by the route and is NOT user-selectable — it is `readonly`
 * and excluded from `makeAutoObservable`'s annotations, so it can neither be
 * reassigned nor observed as changing. A different kind is a different route and
 * therefore a fresh page instance (`routes.tsx` keys each list element).
 *
 * Per the MobX hard rules this class holds observable data + pure `get` computeds
 * ONLY — no effectful methods, no setters. Loading and search submission live in
 * the external `(state, args, signal)` functions below.
 */
export class CodexListPageState {
  /** The route-fixed codex kind this list shows. Never reassigned, never observable. */
  readonly kind: CodexKind;

  /** The loaded entries — the plain array `api/codex.ts` unwrapped from `{ items }`. */
  entries: CodexEntryResponse[] = [];
  entriesStatus: "idle" | "loading" | "ready" | "error" = "idle";
  entriesError: string | null = null;

  /**
   * The committed search needle — the value the current list was loaded with and
   * the value mirrored into the URL's `q`. Empty string means "no filter".
   */
  needle = "";

  /** The uncommitted needle the search input binds to (committed on submit). */
  draftNeedle = "";

  /**
   * @param kind the route's codex kind.
   * @param initialNeedle the `q` read once from the URL query string at mount, so
   *   a deep-linked filtered list loads filtered on its FIRST fetch. Seeds both
   *   the committed needle and the input's draft.
   */
  constructor(kind: CodexKind, initialNeedle: string = "") {
    this.kind = kind;
    this.needle = initialNeedle;
    this.draftNeedle = initialNeedle;
    makeAutoObservable(this, { kind: false });
  }

  /**
   * The empty-vs-loaded distinction: `true` only when the load has completed and
   * matched nothing (so the page renders an empty state, never an error). `false`
   * while idle/loading, on error, and whenever there is at least one entry.
   */
  get isEmpty(): boolean {
    return this.entriesStatus === "ready" && this.entries.length === 0;
  }
}

/**
 * Load the book's entries of `state.kind`, filtered by the committed
 * `state.needle`, into the trio. The kind comes off `state` (route-fixed, never a
 * caller's choice) and the needle is the committed one, so a deep-linked `?q=`
 * filters the FIRST fetch. Archived entries are excluded (the archive surface is
 * `017.codex-archive-restore`'s). Also the retry path behind the error state.
 */
export async function loadCodexEntries(
  state: CodexListPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.entriesStatus = "loading";
    state.entriesError = null;
  });
  try {
    const entries = await codexApi.listCodexEntries(
      bookId,
      state.kind,
      state.needle || undefined,
      undefined,
      signal,
    );
    if (signal?.aborted) return;
    runInAction(() => {
      state.entries = entries;
      state.entriesStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.entriesError = err.message;
        state.entriesStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Commit the search draft and reload. Commits `state.draftNeedle` (trimmed) into
 * `state.needle`, starts `loadCodexEntries` for the newly committed needle, and
 * **returns the new query string** for the caller to push — the search-string
 * form WITHOUT a leading `?`, i.e. `"q=<encoded needle>"`, or `""` when the
 * needle was cleared (so `setSearchParams(returned)` drops `q` from the URL).
 *
 * Synchronous by design: the URL write happens in the event handler that changed
 * it, immediately, never in a `useEffect` watching the query string
 * (`frontend.md`:192). The reload is kicked off here, not awaited by the caller.
 */
export function submitCodexSearch(
  state: CodexListPageState,
  bookId: string,
  signal?: AbortSignal,
): string {
  const committed = state.draftNeedle.trim();
  runInAction(() => {
    state.needle = committed;
  });

  // Fire-and-forget: the reload runs against the just-committed needle while the
  // caller writes the URL synchronously from the returned search string.
  void loadCodexEntries(state, bookId, signal);

  return committed === "" ? "" : new URLSearchParams({ q: committed }).toString();
}
