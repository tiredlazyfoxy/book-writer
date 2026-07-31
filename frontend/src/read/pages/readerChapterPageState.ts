import { makeAutoObservable, runInAction } from "mobx";
import * as readerApi from "../../api/reader";
import { ApiError } from "../../api/client";
import type { ReaderChapterResponse } from "../../types/reader";

/**
 * Page state for `ReaderChapterPage` (Reader SPA `/:bookId/:chapterId`).
 *
 * ONE async-resource trio — `chapter` / `chapterStatus` / `chapterError` — plus
 * `makeAutoObservable`. No aggregation type (frontend.md rule). Per the MobX hard
 * rules this class has NO effectful methods: loading lives in the external
 * `(state, bookId, chapterId, signal?)` function below, which uses `runInAction`.
 *
 * READ-ONLY by construction: no draft of the chapter text, no dirty flag, no
 * save status, no version token. There is nothing to send back, so none of those
 * fields may be added (US-030.AC-2, DoD-9).
 *
 */
export class ReaderChapterPageState {
  /**
   * The chapter's reader projection, as last returned by
   * `GET /api/books/{bookId}/read/chapters/{chapterId}` — `{ id, title, text }`.
   * `null` until the first successful load. An empty `text` is a normal loaded
   * value, never an error.
   */
  chapter: ReaderChapterResponse | null = null;
  chapterStatus: "idle" | "loading" | "ready" | "error" = "idle";
  chapterError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }
}

/**
 * Refusal copy for a failed chapter load, chosen from the `ApiError`'s status
 * (decision D9).
 *
 * The backend returns the SAME 404 for an unknown id, a non-numeric id, another
 * book's chapter, a `planned` chapter and a `closing` chapter (decision D5), so
 * the message must not speculate about which — saying "no such chapter" or "not
 * written yet" would rebuild client-side the oracle the backend collapsed. 403 is
 * unreachable today but mapped for completeness; anything else falls back to the
 * server's own message. No branch yields an empty string — never a blank pane.
 */
function readerChapterRefusal(err: ApiError): string {
  if (err.status === 404) {
    return "This chapter is not available to read.";
  }
  if (err.status === 403) {
    return "You do not have access to this chapter.";
  }
  return err.message;
}

/**
 * Load one chapter's saved text into `state`.
 *
 * On `ApiError`, the refusal message is chosen HERE, not in the component
 * (decision D9) — see {@link readerChapterRefusal}. A non-`ApiError` rethrows.
 */
export async function loadReaderChapter(
  state: ReaderChapterPageState,
  bookId: string,
  chapterId: string,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    state.chapterStatus = "loading";
    state.chapterError = null;
  });

  try {
    const chapter = await readerApi.getReaderChapter(bookId, chapterId, signal);
    if (signal?.aborted) return;
    runInAction(() => {
      state.chapter = chapter;
      state.chapterStatus = "ready";
    });
  } catch (err) {
    if (signal?.aborted) return;
    if (err instanceof ApiError) {
      runInAction(() => {
        state.chapterError = readerChapterRefusal(err);
        state.chapterStatus = "error";
      });
      return;
    }
    throw err;
  }
}
