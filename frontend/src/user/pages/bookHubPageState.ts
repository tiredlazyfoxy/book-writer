import { makeAutoObservable, runInAction } from "mobx";
import * as booksApi from "../../api/books";
import * as chaptersApi from "../../api/chapters";
import { ApiError } from "../../api/client";
import type { BookDetailResponse } from "../../types/books";
import type { ChapterListResponse } from "../../types/chapters";

/**
 * Page state for `BookHubPage` (Shell SPA `/books/:bookId`).
 *
 * Holds TWO independent async-resource trios — the book detail (`detail` /
 * `detailStatus` / `detailError`, loaded through the EXISTING
 * `booksApi.getBookDetail`, the same read `bookSettingsPageState.ts` already calls;
 * no function is added to `api/books.ts`) and the chapter list (`chapterList` /
 * `chapterListStatus` / `chapterListError`) — plus `makeAutoObservable`. No
 * aggregation type (frontend.md rule). Per the MobX hard rules this class has NO
 * effectful methods: loading lives in the external `(state, bookId, signal?)`
 * functions below, one per trio, each using `runInAction`.
 *
 * The two trios load and FAIL INDEPENDENTLY: a failed chapter load must not blank the
 * book heading, and a failed detail load must not hide the chapters.
 *
 * The hub is READ-ONLY (decision D2 — the Book hub reads, the working page edits), so
 * there is no draft field, no `…ServerErrors` holder and no `…SubmitStatus` anywhere
 * in this module.
 *
 * Skeleton (014/005): observable fields are fully declared; the two external
 * effect-fn signatures are frozen with throwing stub bodies for the coder to fill.
 */
export class BookHubPageState {
  /** The book, as last returned by `GET /api/books/{id}`. `null` until the first successful load. */
  detail: BookDetailResponse | null = null;
  detailStatus: "idle" | "loading" | "ready" | "error" = "idle";
  detailError: string | null = null;

  /**
   * The WHOLE chapter list envelope as returned by `GET /api/books/{id}/chapters` —
   * `{ chapters, can_reorder }`, not a bare array. Keeping the envelope means nothing
   * downstream has to re-fetch to learn `can_reorder`, even though this read-only page
   * ignores the hint. `null` until the first successful load; a book with no chapters
   * loads as an envelope with an EMPTY `chapters` array, which is a normal loaded
   * value and never an error.
   */
  chapterList: ChapterListResponse | null = null;
  chapterListStatus: "idle" | "loading" | "ready" | "error" = "idle";
  chapterListError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

/**
 * Load the book detail into `state` through the EXISTING `booksApi.getBookDetail` — no
 * function is added to `api/books.ts`. Abort-guarded before every write; an `ApiError`
 * lands in `detailError` / `detailStatus = "error"`, anything else rethrows.
 *
 * Touches nothing in the chapter-list trio: a detail failure leaves the chapters
 * rendering.
 */
export async function loadBookDetail(
  state: BookHubPageState,
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
 * Load the book's chapter list into `state`, storing the WHOLE envelope returned by
 * `chaptersApi.listChapters` — never `.chapters` alone, so `can_reorder` survives for
 * steps 006 / 007. Abort-guarded before every write; an `ApiError` lands in
 * `chapterListError` / `chapterListStatus = "error"`, anything else rethrows.
 *
 * An empty `chapters` array is a successful load, not an error. Touches nothing in the
 * detail trio: a chapter failure leaves the book heading rendering.
 */
export async function loadChapterList(
  state: BookHubPageState,
  bookId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.chapterListStatus = "loading";
    state.chapterListError = null;
  });
  try {
    const list = await chaptersApi.listChapters(bookId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chapterList = list;
      state.chapterListStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.chapterListError = err.message;
        state.chapterListStatus = "error";
      });
      return;
    }
    throw err;
  }
}
