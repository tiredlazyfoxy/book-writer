import { makeAutoObservable, runInAction } from "mobx";
import * as readerApi from "../../api/reader";
import { ApiError } from "../../api/client";
import type { ReaderBookResponse } from "../../types/reader";

/**
 * Page state for `TableOfContentsPage` (Reader SPA `/:bookId`).
 *
 * ONE async-resource trio — `book` / `bookStatus` / `bookError` — plus
 * `makeAutoObservable`. No aggregation type (frontend.md rule). Per the MobX hard
 * rules this class has NO effectful methods: loading lives in the external
 * `(state, bookId, signal?)` function below, which uses `runInAction`.
 *
 * The reader surface is READ-ONLY, so there is no draft field, no
 * `…ServerErrors` holder and no `…SubmitStatus` anywhere in this module — and
 * none may be added.
 *
 */
export class TableOfContentsPageState {
  /**
   * The book's reader projection, as last returned by
   * `GET /api/books/{id}/read`. `null` until the first successful load. A book
   * with no reader-visible chapters loads as a response with an EMPTY `chapters`
   * array — a normal loaded value, never an error.
   */
  book: ReaderBookResponse | null = null;
  bookStatus: "idle" | "loading" | "ready" | "error" = "idle";
  bookError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

/**
 * Refusal copy for a failed table-of-contents load, chosen from the `ApiError`'s
 * status (decision D9).
 *
 * The backend answers **404** both for a book that does not exist and for one the
 * caller may not see (`resolve_book_access`'s existence hiding), so the message
 * must not speculate about which — it says only that the book is not available to
 * read. 403 is unreachable today but mapped for completeness; anything else falls
 * back to the server's own message. There is no branch that yields an empty
 * string: a blank pane is the one outcome this function exists to prevent.
 */
function readerBookRefusal(err: ApiError): string {
  if (err.status === 404) {
    return "This book is not available to read. It may be private, or it may no longer exist.";
  }
  if (err.status === 403) {
    return "You do not have access to this book.";
  }
  return err.message;
}

/**
 * Load the book's table of contents into `state`.
 *
 * On `ApiError`, the REFUSAL MESSAGE IS CHOSEN HERE, not in the component
 * (decision D9, frontend.md's state/component split) — see
 * {@link readerBookRefusal}. Anything that is not an `ApiError` rethrows.
 */
export async function loadReaderBook(
  state: TableOfContentsPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.bookStatus = "loading";
    state.bookError = null;
  });

  try {
    const book = await readerApi.getReaderBook(bookId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.book = book;
      state.bookStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.bookError = readerBookRefusal(err);
        state.bookStatus = "error";
      });
      return;
    }
    throw err;
  }
}
