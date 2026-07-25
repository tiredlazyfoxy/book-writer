import { Route, Routes, useParams } from "react-router-dom";
import { HealthPage } from "./pages/HealthPage";
import { BookshelfPage } from "./pages/BookshelfPage";
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
 * Shell SPA route table — root path renders the bookshelf; the health page is
 * preserved at `/health`; `/books/:bookId/settings` renders the book-settings page
 * with the `key={bookId}` remount rule.
 */
export function UserRoutes() {
  return (
    <Routes>
      <Route path="/" element={<BookshelfPage />} />
      <Route path="/health" element={<HealthPage />} />
      <Route path="/books/:bookId/settings" element={<BookSettingsRoute />} />
    </Routes>
  );
}
