import { makeAutoObservable, runInAction } from "mobx";
import * as booksApi from "../../../api/books";
import { ApiError } from "../../../api/client";
import type { BookDetailResponse } from "../../../types/books";

/**
 * Shell state for `WorkspaceShell` (`/work/:bookId`), held via
 * `useState(() => new WorkspaceShellState())`.
 *
 * Holds the book-detail async-resource trio (`bookDetail` / `bookDetailStatus` /
 * `bookDetailError`) used for the shell's header chrome, plus the mobile
 * navbar-open flag (the `AdminShellState` precedent). Per the MobX hard rules
 * this class has NO effectful methods — the book load lives in the external
 * `loadWorkspaceBook(state, bookId, signal)` function below.
 */
export class WorkspaceShellState {
  bookDetail: BookDetailResponse | null = null;
  bookDetailStatus: "idle" | "loading" | "ready" | "error" = "idle";
  bookDetailError: string | null = null;
  /** Is the navbar drawer open on mobile? (Ignored above the `sm` breakpoint.) */
  navbarOpened = false;

  constructor() {
    makeAutoObservable(this);
  }
}

/**
 * Load the book detail into `state` (unimplemented — coder fills). Intent: set
 * `bookDetailStatus = "loading"`, await `booksApi.getBookDetail(bookId, signal)`,
 * `runInAction` the trio to `ready` on success; return silently when
 * `signal?.aborted`; map an `ApiError` (the 403/404 a non-member receives) into
 * an author-facing `bookDetailError` with `bookDetailStatus = "error"`, else
 * rethrow.
 *
 */
export async function loadWorkspaceBook(
  state: WorkspaceShellState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.bookDetailStatus = "loading";
    state.bookDetailError = null;
  });
  try {
    const detail = await booksApi.getBookDetail(bookId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.bookDetail = detail;
      state.bookDetailStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.bookDetailError = err.message;
        state.bookDetailStatus = "error";
      });
      return;
    }
    throw err;
  }
}
