import { makeAutoObservable, runInAction } from "mobx";
import * as booksApi from "../../api/books";
import { ApiError } from "../../api/client";
import type { BookResponse, CreateBookRequest } from "../../types/books";

/**
 * Page state for `BookshelfPage` (Shell SPA root `/`).
 *
 * Holds two independent async-resource trios — owned (`ownedBooks` /
 * `ownedStatus` / `ownedError`) and shared (`sharedBooks` / `sharedStatus` /
 * `sharedError`) — plus `makeAutoObservable`. No aggregation type (frontend.md
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

  constructor() {
    makeAutoObservable(this);
  }
}

/**
 * Load both bookshelf lists into `state` (unimplemented — coder fills). Intent:
 * set both statuses to `loading`, await `booksApi.listOwnedBooks(signal)` and
 * `booksApi.listSharedBooks(signal)`, `runInAction` each trio to `ready` on
 * success; guard `signal?.aborted`; map an `ApiError` into the matching error
 * trio, else rethrow.
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
