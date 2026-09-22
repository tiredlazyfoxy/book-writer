import { makeAutoObservable, runInAction } from "mobx";
import * as booksApi from "../../api/books";
import * as readerApi from "../../api/reader";
import { ApiError } from "../../api/client";
import type { BookResponse, CreateBookRequest } from "../../types/books";
import type { PublicBookRef } from "../../types/reader";

/**
 * Page state for `BookshelfPage` (Shell SPA root `/`).
 *
 * Holds three independent async-resource trios — owned (`ownedBooks` /
 * `ownedStatus` / `ownedError`), shared (`sharedBooks` / `sharedStatus` /
 * `sharedError`) and, since feature 022, public (`publicBooks` / `publicStatus` /
 * `publicError`) — plus `makeAutoObservable`. No aggregation type (frontend.md
 * rule). Per the MobX hard rules it has NO effectful methods — loading and the
 * create-then-reload action live in the external `(state, …, signal)` functions
 * below. Modal open/target flags are component-local `useState` in the page,
 * never page state.
 *
 * Skeleton: observable fields are fully declared; the external effect-fn
 * signatures are frozen with throwing stub bodies for the coder to implement.
 */
export class BookshelfPageState {
  ownedBooks: BookResponse[] = [];
  ownedStatus: "idle" | "loading" | "ready" | "error" = "idle";
  ownedError: string | null = null;

  sharedBooks: BookResponse[] = [];
  sharedStatus: "idle" | "loading" | "ready" | "error" = "idle";
  sharedError: string | null = null;

  /**
   * Third trio (feature 022, D16) — public books the caller can DISCOVER but is
   * not part of, from `GET /api/books/public` via `readerApi.listPublicBooks`.
   *
   * Rows are `PublicBookRef` (`{ id, title, description }`), NOT `BookResponse`:
   * the discovery feed carries no owner, visibility, state or timestamps (D14),
   * so the section renders different columns from the two above it.
   *
   * The three lists are DISJOINT by construction — the backend excludes the
   * caller's own books and the ones they co-author — so a book never appears in
   * two sections.
   */
  publicBooks: PublicBookRef[] = [];
  publicStatus: "idle" | "loading" | "ready" | "error" = "idle";
  publicError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

/**
 * Load the bookshelf lists into `state`. Intent: set every status to `loading`,
 * await each list call, `runInAction` each trio to `ready` on success; guard
 * `signal?.aborted`; map an `ApiError` into the matching error trio, else
 * rethrow.
 *
 * Three lists load here (feature 022 added the public one), in one mount effect
 * and one signal. Each trio fails independently — a failed public load must not
 * blank the owned or shared sections, and vice versa.
 */
export async function loadBookshelf(
  state: BookshelfPageState,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.ownedStatus = "loading";
    state.ownedError = null;
    state.sharedStatus = "loading";
    state.sharedError = null;
    state.publicStatus = "loading";
    state.publicError = null;
  });

  try {
    const owned = await booksApi.listOwnedBooks(signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.ownedBooks = owned.items;
      state.ownedStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.ownedError = err.message;
        state.ownedStatus = "error";
      });
    } else {
      throw err;
    }
  }

  try {
    const shared = await booksApi.listSharedBooks(signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.sharedBooks = shared.items;
      state.sharedStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.sharedError = err.message;
        state.sharedStatus = "error";
      });
    } else {
      throw err;
    }
  }

  // Third block (feature 022, D16): the public discovery feed. Same shape as the
  // two above, its own trio, its own try/catch — the reader surface must not be
  // able to take the author's two sections down with it.
  try {
    const publicBooks = await readerApi.listPublicBooks(signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.publicBooks = publicBooks.items;
      state.publicStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.publicError = err.message;
        state.publicStatus = "error";
      });
    } else {
      throw err;
    }
  }
}

/**
 * Create a book, then re-load the shelf (unimplemented — coder fills). Intent:
 * await `booksApi.createBook(body, signal)` then re-call `loadBookshelf(state,
 * signal)` so the new book appears in the owned list (mirrors the
 * `disableUserAction` re-load pattern; no optimistic local edit). Abort-guarded;
 * `ApiError` recorded into the owned error trio, else rethrow.
 */
export async function createBookAction(
  state: BookshelfPageState,
  body: CreateBookRequest,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await booksApi.createBook(body, signal);
    if (signal?.aborted) return;
    await loadBookshelf(state, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.ownedError = err.message;
      });
      return;
    }
    throw err;
  }
}
