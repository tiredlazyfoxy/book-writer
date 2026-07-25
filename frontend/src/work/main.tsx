import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { enforceWorkAccess } from "./workGate";

// Work admission gate (feature 010): runs OUTSIDE React, before `createRoot`. On
// deny it has already navigated the browser away, so we must not mount. Module
// bodies run once, so this fires exactly once — no StrictMode double-navigation.
if (enforceWorkAccess()) {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
