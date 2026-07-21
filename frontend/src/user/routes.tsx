import { Route, Routes } from "react-router-dom";
import { HealthPage } from "./pages/HealthPage";

/** User SPA route table — root path renders the health page. */
export function UserRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HealthPage />} />
    </Routes>
  );
}
