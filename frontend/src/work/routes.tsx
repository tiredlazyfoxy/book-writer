import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { observer } from "mobx-react-lite";
import { NotFoundPage } from "./pages/NotFoundPage";
import { BookStatePage } from "./pages/BookStatePage";
import { ChapterPage } from "./pages/ChapterPage";
import { ChaptersPage } from "./pages/ChaptersPage";
import { CodexEntryPage } from "./pages/CodexEntryPage";
import { CodexListPage } from "./pages/CodexListPage";
import { SubjectPlaceholderPage } from "./pages/SubjectPlaceholderPage";
import { WorkspaceShell } from "./components/shell/WorkspaceShell";

/**
 * Route wrapper applying the documented `key={bookId}` remount rule
 * (frontend-workspace.md — "Keying the shell on `:bookId`"): reading the param
 * here lets the key sit on the shell element so changing the book id remounts a
 * fresh `WorkspaceShellState`, while navigating between subject routes under the
 * same book id does **not** remount. Mirrors `BookSettingsRoute` in
 * `src/user/routes.tsx`.
 */
function WorkspaceRoute() {
  const { bookId } = useParams();
  return <WorkspaceShell key={bookId} />;
}

/**
 * Item-route wrappers applying `frontend.md`'s path-param remount rule: the `key`
 * sits on the placeholder so navigating between two items of the same kind (e.g.
 * `chapter/1` → `chapter/2`) remounts a fresh subject rather than reusing state.
 * The shell above them does not remount (002's DoD-7). No `chat/:id` route exists —
 * the chat pane resolves its own active chat per book (US-105.AC-3).
 */
function ChapterItemRoute() {
  const { id } = useParams();
  // 014/008 swapped the ELEMENT only: the wrapper and its `key={id}` are what make
  // `chapter/1` → `chapter/2` produce a FRESH `ChapterPageState` rather than showing
  // the previous chapter's drafts (008 DoD-14), and they already existed.
  return <ChapterPage key={id} />;
}

function CodexEntryItemRoute() {
  const { id } = useParams();
  return <CodexEntryPage key={id} mode="existing" />;
}

function ChapterVariantsItemRoute() {
  const { chapterId } = useParams();
  return (
    <SubjectPlaceholderPage
      key={chapterId}
      heading="Chapter variants"
      owner="018.chapter-history-variants"
    />
  );
}

/**
 * `/work/:bookId/chats` degrades to a redirect to the book-state route (011/004):
 * the chat list is owned by the chat pane (US-095.AC-1 / US-105.AC-3), so this
 * documented deep link must neither 404 nor put a chat surface in the content
 * pane. Reads `:bookId` so the redirect is absolute (`/:bookId/state`,
 * basename-resolved), mirroring the index redirect. The doc tension is recorded
 * in `outcome.md`.
 */
function ChatsRedirectRoute() {
  const { bookId } = useParams();
  return <Navigate to={`/${bookId}/state`} replace />;
}

/**
 * Work SPA route table, mounted under the `/work` basename by `App.tsx`. The
 * `/:bookId` route renders the keyed workspace shell; its nested catch-all
 * renders the not-found page **inside** the content pane for an unknown subject
 * path. The terminal top-level catch-all (from step 001) renders the not-found
 * page for any address that is not a book workspace. Step 003 nests the landing
 * view: an index route redirecting (replace) to `state` and the `state` child; step
 * 004 nests the remaining subject routes ahead of the catch-all.
 */
export const WorkRoutes = observer(function WorkRoutes() {
  return (
    <Routes>
      <Route path="/:bookId" element={<WorkspaceRoute />}>
        <Route index element={<Navigate to="state" replace />} />
        <Route path="state" element={<BookStatePage />} />
        <Route path="chapters" element={<ChaptersPage />} />
        <Route path="chapter/:id" element={<ChapterItemRoute />} />
        {/*
          The three codex lists (013/011) share ONE parameterized page — the kind is
          fixed by the route and is never user-selectable. The explicit `key` applies
          `frontend.md`'s "page = route = fresh state instance" rule: without it React
          would reconcile the same component type across `/characters` → `/locations`
          and keep the previous kind's state instance alive.
          `codex/new` (UC-076's blank entry, kind carried as `?kind=`) is declared
          BEFORE `codex/:id`; both render the ONE entry page (013/012), which reads
          its kind from the query string at mount on the blank route.
        */}
        <Route path="characters" element={<CodexListPage key="character" kind="character" />} />
        <Route path="locations" element={<CodexListPage key="location" kind="location" />} />
        <Route path="facts" element={<CodexListPage key="fact" kind="fact" />} />
        <Route path="codex/new" element={<CodexEntryPage mode="blank" />} />
        <Route path="codex/:id" element={<CodexEntryItemRoute />} />
        <Route
          path="variants"
          element={
            <SubjectPlaceholderPage heading="Variants" owner="018.chapter-history-variants" />
          }
        />
        <Route path="variants/:chapterId" element={<ChapterVariantsItemRoute />} />
        <Route path="chats" element={<ChatsRedirectRoute />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
});
