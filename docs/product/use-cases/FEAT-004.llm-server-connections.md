<!-- product-spec:start -->
# Use Cases — FEAT-004 LLM server connections

### UC-010 — Register LLM server
- **Feature:** FEAT-004 · **Actor:** ACT-001
- **Preconditions:** Admin authenticated.
- **Main flow:**
  1. Admin submits server details: name, backend type, base URL, API key.
  2. System checks required fields are present.
  3. System stores the server connection.
- **Exception flow:** A required field is missing → registration refused.
- **Postconditions:** Server connection recorded; not yet tested or enabled.
- **Source:** `[confirmed: user]` interview 2026-07-20, "features"; fields per
  reference mapping.

### UC-011 — Test connection / probe models
- **Feature:** FEAT-004 · **Actor:** ACT-001
- **Preconditions:** LLM server registered.
- **Main flow:**
  1. Admin requests a connection test for a server.
  2. System contacts the server.
  3. System returns the list of models the server reports as available.
- **Exception flow:** Server unreachable → error surfaced, no model list
  returned.
- **Postconditions:** Probe result available to the admin; no server record
  changed by the probe itself.
- **Source:** `[inferred]` interview 2026-07-20, "Reference mapping" — probe
  semantics carried from reference project, not explicitly confirmed.

### UC-012 — Enable models
- **Feature:** FEAT-004 · **Actor:** ACT-001
- **Preconditions:** Server has been probed and a model list is available.
- **Main flow:**
  1. Admin selects a subset of the probed models.
  2. System persists that subset as the server's enabled models.
- **Postconditions:** Enabled models recorded for the server.
- **Source:** `[confirmed: user]` interview 2026-07-20, "features"

### UC-013 — Edit / delete LLM server
- **Feature:** FEAT-004 · **Actor:** ACT-001
- **Preconditions:** LLM server exists.
- **Main flow:**
  1. Admin edits server fields, or requests deletion.
  2. System updates the record, or removes it.
- **Postconditions:** Server record updated, or no longer present.
- **Source:** `[confirmed: user]` interview 2026-07-20, "features"

### UC-014 — Designate embedding server + model
- **Feature:** FEAT-004 · **Actor:** ACT-001
- **Preconditions:** At least one LLM server registered with a probed model
  list.
- **Main flow:**
  1. Admin selects a server and one model as the embedding provider.
  2. System designates that server + model as the embedding provider,
     replacing any prior designation.
- **Postconditions:** Exactly one embedding server + model designated.
- **Source:** `[confirmed: user]` interview 2026-07-20, "features": "single
  embedding provider"
<!-- product-spec:end -->
