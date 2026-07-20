<!-- product-spec:start -->
# Stories — FEAT-004 LLM server connections

### US-010 — Register LLM server
- **Feature:** FEAT-004 · **Actor:** ACT-001 · **Realizes:** UC-010
- **Status:** proposed
- **Story:** As an admin, I want to register an LLM server connection, so
  that its models become available to the system.
- **Acceptance criteria:**
  - **US-010.AC-1** — Given name, backend type, base URL, and API key are
    all supplied, when the admin submits the form, then the server
    connection is stored.
  - **US-010.AC-2** — Given a backend type outside {llama-swap, openai},
    when the admin submits the form, then registration is refused.
  - **US-010.AC-3** — Given a required field is omitted, when the admin
    submits the form, then registration is refused.
- **Source:** `[confirmed: user]` interview 2026-07-20, "features"; field set
  per reference mapping.

### US-011 — Test connection / probe models
- **Feature:** FEAT-004 · **Actor:** ACT-001 · **Realizes:** UC-011
- **Status:** proposed
- **Story:** As an admin, I want to test a registered server's connection, so
  that I can see which models it actually offers before enabling any.
- **Acceptance criteria:**
  - **US-011.AC-1** — Given a registered server is reachable, when the admin
    tests the connection, then the list of models the server reports is
    returned.
  - **US-011.AC-2** — Given a registered server is unreachable, when the
    admin tests the connection, then an error is surfaced and no model list
    is returned.
- **Source:** `[inferred]` interview 2026-07-20, "Reference mapping" — probe
  semantics carried from reference project, not explicitly confirmed.

### US-012 — Enable models
- **Feature:** FEAT-004 · **Actor:** ACT-001 · **Realizes:** UC-012
- **Status:** proposed
- **Story:** As an admin, I want to enable a subset of a server's probed
  models, so that only vetted models are available for use.
- **Acceptance criteria:**
  - **US-012.AC-1** — Given a server has a probed model list, when the admin
    selects a subset and saves, then that subset is persisted as the
    server's enabled models.
- **Source:** `[confirmed: user]` interview 2026-07-20, "features"

### US-013 — Edit / delete LLM server
- **Feature:** FEAT-004 · **Actor:** ACT-001 · **Realizes:** UC-013
- **Status:** proposed
- **Story:** As an admin, I want to edit or delete a registered LLM server,
  so that I can correct its details or remove one no longer in use.
- **Acceptance criteria:**
  - **US-013.AC-1** — Given an existing server, when the admin updates its
    fields, then the stored record reflects the new values.
  - **US-013.AC-2** — Given an existing server, when the admin deletes it,
    then the server record no longer exists.
- **Source:** `[confirmed: user]` interview 2026-07-20, "features"

### US-014 — Designate embedding server
- **Feature:** FEAT-004 · **Actor:** ACT-001 · **Realizes:** UC-014
- **Status:** proposed
- **Story:** As an admin, I want to designate one server and model as the
  embedding provider, so that embedding operations have a single, known
  source.
- **Acceptance criteria:**
  - **US-014.AC-1** — Given a server with a probed model, when the admin
    designates that server + model as the embedding provider, then it is
    recorded as the embedding provider.
  - **US-014.AC-2** — Given an embedding provider is already designated,
    when the admin designates a different server + model, then the new
    designation replaces the prior one.
- **Source:** `[confirmed: user]` interview 2026-07-20, "features": "single
  embedding provider"

### US-021 — API-key $ENV indirection & secret masking
- **Feature:** FEAT-004 · **Actor:** ACT-001
- **Realizes:** _(none — cross-cutting security requirement on FEAT-004, no
  dedicated use case)_
- **Status:** proposed
- **Story:** As an admin, I want an LLM server's API key to be stored
  indirectly and never shown back to me in full, so that the credential
  isn't exposed through the system.
- **Acceptance criteria:**
  - **US-021.AC-1** — Given a server's API key is stored as an environment-
    variable reference, when the system uses the key, then the actual value
    is resolved from the environment at use time.
  - **US-021.AC-2** — Given a server has an API key configured, when its
    details are returned to the admin, then only a boolean presence
    indicator is included, never the key value.
- **Source:** `[inferred]` interview 2026-07-20, "Reference mapping" —
  secret-masking specifics carried from reference project, not explicitly
  confirmed.
<!-- product-spec:end -->
