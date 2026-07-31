import { Route, Routes, useParams } from "react-router-dom";
import { observer } from "mobx-react-lite";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ReaderChapterPage } from "./pages/ReaderChapterPage";
import { TableOfContentsPage } from "./pages/TableOfContentsPage";

/**
 * Route wrappers applying `frontend.md`'s path-param remount rule ("page = route
 * = fresh state instance"): reading the param here lets the `key` sit on the page
 * element, so changing the id remounts fresh state rather than showing the
 * previous book's / chapter's data. The `src/work/routes.tsx` idiom verbatim.
 *
 * The table of contents keys on `bookId`; the chapter page keys on `chapterId`,
 * so following one chapter link to the next inside the same book still remounts.
 */
function TableOfContentsRoute() {
  const { bookId } = useParams();
  return <TableOfContentsPage key={bookId} />;
}

function ReaderChapterRoute() {
  const { chapterId } = useParams();
  return <ReaderChapterPage key={chapterId} />;
}

/**
 * Reader SPA route table, mounted under the `/read` basename by `App.tsx`
 * (DoD-16). Exactly three routes, and that is the whole reader address space:
 * `/:bookId` (table of contents), `/:bookId/:chapterId` (one chapter's text),
 * and the terminal catch-all. **No fourth route may ever be added** — no codex,
 * state notes, flags, book state, settings or chat (UC-029's postcondition, and
 * the plan's "Out of scope").
 *
 * There is no index route: `/read/` alone names no book, so it falls to the
 * catch-all.
 */
export const ReadRoutes = observer(function ReadRoutes() {
  return (
    <Routes>
      <Route path="/:bookId" element={<TableOfContentsRoute />} />
      <Route path="/:bookId/:chapterId" element={<ReaderChapterRoute />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
});
