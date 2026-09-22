import { Route, Routes, useParams } from "react-router-dom";
import { HealthPage } from "./pages/HealthPage";
import { BookshelfPage } from "./pages/BookshelfPage";
import { BookHubPage } from "./pages/BookHubPage";
import { BookSettingsPage } from "./pages/BookSettingsPage";

/**
 * Route wrapper applying the documented `key={bookId}` remount rule (frontend.md —
 * "page = route = fresh state instance"). Reading the param here lets the key sit on
 * the page element so changing the book id remounts a fresh `BookSettingsPageState`.
 * This is the repo's first URL-param route.
 */
function BookSettingsRoute() {
  const { bookId } = useParams();
  return <BookSettingsPage key={bookId} />;
}

/**
 * Route wrapper for the book hub, applying the same `key={bookId}` remount rule so a
 * book change gets a fresh `BookHubPageState` and re-loads both of its resources
 * rather than showing the previous book's chapters (014/005 DoD-6).
 */
function BookHubRoute() {
  const { bookId } = useParams();
  return <BookHubPage key={bookId} />;
}

/**
 * Shell SPA route table — root path renders the bookshelf; the health page is
 * preserved at `/health`; `/books/:bookId/settings` renders the book-settings page and
 * `/books/:bookId` the read-only book hub, both with the `key={bookId}` remount rule.
 *
 * The more specific `/books/:bookId/settings` is declared first; react-router 7 ranks
 * matches by specificity rather than declaration order, so the hub cannot shadow it
 * either way, and the ordering states the intent.
 */
export function UserRoutes() {
  return (
    <Routes>
      <Route path="/" element={<BookshelfPage />} />
      <Route path="/health" element={<HealthPage />} />
      <Route path="/books/:bookId/settings" element={<BookSettingsRoute />} />
      <Route path="/books/:bookId" element={<BookHubRoute />} />
    </Routes>
  );
}
