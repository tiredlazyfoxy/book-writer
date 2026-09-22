import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { enforceReadAccess } from "./readGate";

// Reader SPA entry (feature 022 — replaces feature 010's ungated 9-line stub).
// The admission gate runs HERE, outside React, before `createRoot`: an
// unauthenticated visitor is sent to `/login/` and the SPA never mounts, so no
// reader surface can flash before the redirect (US-030.AC-4, DoD-14). Verbatim
// mirror of `src/work/main.tsx`.
if (enforceReadAccess()) {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
