import { Route, Routes } from "react-router-dom";
import { observer } from "mobx-react-lite";
import { UsersPage } from "./pages/UsersPage";
import { LlmServersPage } from "./pages/LlmServersPage";
import { DatabasePage } from "./pages/DatabasePage";
import { NotFoundPage } from "./pages/NotFoundPage";

/**
 * Admin SPA route table. Mounted under the `/admin` basename by `App.tsx`; the
 * root path `/` renders the users list and `/llm-servers` the LLM-server list
 * (feature 006). More admin pages arrive with 007.
 *
 * The terminal `path="*"` (fast/002) catches unknown deep links, which previously
 * rendered the chrome plus a blank body.
 */
export const AdminRoutes = observer(function AdminRoutes() {
  return (
    <Routes>
      <Route path="/" element={<UsersPage />} />
      <Route path="/llm-servers" element={<LlmServersPage />} />
      <Route path="/database" element={<DatabasePage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
});
