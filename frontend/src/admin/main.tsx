import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { enforceAdminAccess } from "./adminGate";

// Admin admission gate (fast/002): runs OUTSIDE React, before `createRoot`. On
// deny it has already navigated the browser away, so we must not mount — that is
// what removes the flash of admin content and the StrictMode double-navigation of
// the old render-phase check. Module bodies run once, so this fires exactly once.
if (enforceAdminAccess()) {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
