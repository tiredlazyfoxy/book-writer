import { makeAutoObservable, runInAction } from "mobx";
import * as booksApi from "../../api/books";
import { ApiError } from "../../api/client";
import type {
  AddMemberRequest,
  BookDetailResponse,
  SetVisibilityRequest,
  TransferOwnershipRequest,
} from "../../types/books";

/**
 * Page state for `BookSettingsPage` (`/books/:bookId/settings`).
 *
 * Holds the single book-detail async-resource trio (`detail` / `detailStatus` /
 * `detailError`) plus `makeAutoObservable`. The `members` list and current
 * `visibility` / `state` all come from `GET /api/books/{id}` (`detail`); after any
 * mutation the detail is re-loaded rather than mutated locally (backend is the
 * source of truth). Per the MobX hard rules this class has NO effectful methods —
 * loading and every mutation action live in the external `(state, …, signal)`
 * functions below.
 *
 * Skeleton: the observable trio is fully declared; the external effect-fn
 * signatures are frozen with throwing stub bodies for the coder to implement.
 */
export class BookSettingsPageState {
  detail: BookDetailResponse | null = null;
  detailStatus: "idle" | "loading" | "ready" | "error" = "idle";
  detailError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

/**
 * Load the book detail into `state` (unimplemented — coder fills). Intent: set
 * `detailStatus = "loading"`, await `booksApi.getBookDetail(bookId, signal)`,
 * `runInAction` the trio to `ready` on success; guard `signal?.aborted`; map an
 * `ApiError` into `detailError` / `detailStatus = "error"`, else rethrow.
 */
export async function loadBookSettings(
  state: BookSettingsPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.detailStatus = "loading";
    state.detailError = null;
  });
  try {
    const detail = await booksApi.getBookDetail(bookId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.detail = detail;
      state.detailStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
        state.detailStatus = "error";
      });
      return;
    }
    throw err;
  }
}

/**
 * Archive the book then re-load the detail (unimplemented — coder fills). Intent:
 * await `booksApi.archiveBook(bookId, signal)` then `loadBookSettings(state,
 * bookId, signal)`; abort-guarded; `ApiError` surfaced into `detailError`.
 */
export async function archiveAction(
  state: BookSettingsPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await booksApi.archiveBook(bookId, signal);
    if (signal?.aborted) return;
    await loadBookSettings(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
      });
      return;
    }
    throw err;
  }
}

/**
 * Unarchive the book then re-load the detail (unimplemented — coder fills). Intent:
 * await `booksApi.unarchiveBook(bookId, signal)` then re-load; same error handling
 * as `archiveAction`.
 */
export async function unarchiveAction(
  state: BookSettingsPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await booksApi.unarchiveBook(bookId, signal);
    if (signal?.aborted) return;
    await loadBookSettings(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
      });
      return;
    }
    throw err;
  }
}

/**
 * Transfer ownership then re-load the detail (unimplemented — coder fills). Intent:
 * await `booksApi.transferOwnership(bookId, body, signal)` then re-load; abort-
 * guarded; `ApiError` surfaced into `detailError`.
 */
export async function transferAction(
  state: BookSettingsPageState,
  bookId: string,
  body: TransferOwnershipRequest,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await booksApi.transferOwnership(bookId, body, signal);
    if (signal?.aborted) return;
    await loadBookSettings(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
      });
      return;
    }
    throw err;
  }
}

/**
 * Add a co-author then re-load the detail (unimplemented — coder fills). Intent:
 * await `booksApi.addMember(bookId, body, signal)` then re-load so the new member
 * appears; abort-guarded; `ApiError` surfaced into `detailError`.
 */
export async function addMemberAction(
  state: BookSettingsPageState,
  bookId: string,
  body: AddMemberRequest,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await booksApi.addMember(bookId, body, signal);
    if (signal?.aborted) return;
    await loadBookSettings(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
      });
      return;
    }
    throw err;
  }
}

/**
 * Remove a co-author then re-load the detail (unimplemented — coder fills). Intent:
 * await `booksApi.removeMember(bookId, userId, signal)` then re-load so the member
 * list updates; abort-guarded; `ApiError` surfaced into `detailError`.
 */
export async function removeMemberAction(
  state: BookSettingsPageState,
  bookId: string,
  userId: string,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await booksApi.removeMember(bookId, userId, signal);
    if (signal?.aborted) return;
    await loadBookSettings(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
      });
      return;
    }
    throw err;
  }
}

/**
 * Set visibility then re-load the detail (unimplemented — coder fills). Intent:
 * await `booksApi.setVisibility(bookId, body, signal)` then re-load; abort-guarded;
 * `ApiError` surfaced into `detailError`.
 */
export async function setVisibilityAction(
  state: BookSettingsPageState,
  bookId: string,
  body: SetVisibilityRequest,
  signal?: AbortSignal,
): Promise<void> {
  try {
    await booksApi.setVisibility(bookId, body, signal);
    if (signal?.aborted) return;
    await loadBookSettings(state, bookId, signal);
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.detailError = err.message;
      });
      return;
    }
    throw err;
  }
}
