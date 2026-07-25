import { makeAutoObservable, runInAction } from "mobx";
import * as booksApi from "../../api/books";
import { COLLABORATION_MODE_OPTIONS, VISIBILITY_OPTIONS } from "../../api/books";
import { ApiError } from "../../api/client";
import type { BookDetailResponse, BookMemberResponse, BookState } from "../../types/books";

/** Author-facing labels for the `BookState` union (no exported map exists — see `003.context.md`). */
const LIFECYCLE_STATE_LABELS: Record<BookState, string> = {
  active: "Active",
  archived: "Archived",
  quarantined: "Quarantined",
  destroyed: "Destroyed",
};

/**
 * Page state for `BookStatePage` (`/work/:bookId/state`, the working page's
 * landing view — UC-091 / US-106.AC-1), held via `useState(() => new
 * BookStatePageState())`.
 *
 * Holds the book-detail async-resource trio (`bookDetail` / `bookDetailStatus` /
 * `bookDetailError`) plus `makeAutoObservable`. This page loads the book again by
 * URL id rather than warm-starting from the shell's copy (frontend.md — every page
 * is deep-linkable; `useOutletContext` is banned React context); see
 * `003.context.md`. Per the MobX hard rules the class has NO effectful methods and
 * NO setters — the load lives in the external `loadBookState(state, bookId, signal)`
 * function below. Every derivation is a `get` computed:
 *   - `collaborationModeLabel` / `visibilityLabel` — author-facing labels, reusing
 *     `COLLABORATION_MODE_OPTIONS` / `VISIBILITY_OPTIONS` from `api/books.ts`.
 *   - `lifecycleStateLabel` — author-facing `BookState` label (no exported map
 *     exists; the coder derives it here — `003.context.md`).
 *   - `memberList` / `memberCount` — the co-author members to render and their count.
 *
 * Skeleton: the observable trio is fully declared; the computed getters and the
 * external loader are frozen with throwing stub bodies for the coder to implement.
 */
export class BookStatePageState {
  bookDetail: BookDetailResponse | null = null;
  bookDetailStatus: "idle" | "loading" | "ready" | "error" = "idle";
  bookDetailError: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  /** Author-facing collaboration-mode label, reusing `COLLABORATION_MODE_OPTIONS`. */
  get collaborationModeLabel(): string {
    const mode = this.bookDetail?.collaboration_mode;
    if (!mode) return "";
    return COLLABORATION_MODE_OPTIONS.find((o) => o.value === mode)?.label ?? "";
  }

  /** Author-facing visibility label, reusing `VISIBILITY_OPTIONS`. */
  get visibilityLabel(): string {
    const visibility = this.bookDetail?.visibility;
    if (!visibility) return "";
    return VISIBILITY_OPTIONS.find((o) => o.value === visibility)?.label ?? "";
  }

  /** Author-facing lifecycle-state label. */
  get lifecycleStateLabel(): string {
    const state = this.bookDetail?.state;
    if (!state) return "";
    return LIFECYCLE_STATE_LABELS[state] ?? "";
  }

  /** The co-author member rows to render. */
  get memberList(): BookMemberResponse[] {
    return this.bookDetail?.members ?? [];
  }

  /** The count of members to render. */
  get memberCount(): number {
    return this.memberList.length;
  }
}

/**
 * Load the book detail into `state` (unimplemented — coder fills). Intent: set
 * `bookDetailStatus = "loading"`, await `booksApi.getBookDetail(bookId, signal)`,
 * `runInAction` the trio to `ready` on success; return silently when
 * `signal?.aborted`; map an `ApiError` into an author-facing `bookDetailError` with
 * `bookDetailStatus = "error"`, else rethrow.
 */
export async function loadBookState(
  state: BookStatePageState,
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
