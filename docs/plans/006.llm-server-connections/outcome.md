# Outcome — feature 006 llm-server-connections

Intended documentation changes to apply at finalization (architect routing).
FEAT-004 is fully specified and `[confirmed: user]`/`[inferred]` with no `_TBD` —
**no `docs/product/` back-propagation** is needed; nothing routes to `/product-spec`.
These are architecture + quick-ref deltas only. Keep to real deltas.

## `docs/architecture/backend.md`

- **New "LLM server connections" design section** (net-new subsystem, carry a
  `**Realizes:** FEAT-004, UC-010..014` header). Record:
  - The single **`LlmServer`** table (`models/llm_server.py`) and its session-free
    `db/llm_servers.py` module. Note `enabled_models` is a JSON-encoded `list[str]` in
    a TEXT column, decoded only at the service boundary.
  - The **`$ENV` resolver** (`services/secrets.py` → `resolve_env_ref`) as the single
    shared indirection point — resolved **only at use time** (probe/embed), never at
    rest — and the **`has_api_key` masking** pattern (response DTO carries no
    `api_key`, only the boolean; computed `api_key is not None and api_key != ""`).
  - The **probe/test-connection** `llm`-client wiring (first in the codebase): fused,
    synchronous, `GET .../available-models`, sorted `list[str]`, and its **failure
    taxonomy** — `aiohttp.ClientError` (unreachable) vs `llm.LLMError` (HTTP/auth) vs
    `ValueError` (keyless OpenAI) → typed probe-failed → **502**. Note `base_url` must
    include `/v1` (the client appends `/models` raw; no auto-append).
  - The **embedding designation** as per-row `is_embedding` + `embedding_model`
    enforced by **clear-all-then-set** (`db.clear_all_embedding()` is the one
    sanctioned raw-`sqlalchemy.update()` inside `db/`), guaranteeing exactly one.
  - The **first DELETE pattern** (db `delete(id) -> bool`; route → 204, missing → 404).
  - The route surface under `/api/admin/llm-servers`, all `require_role(admin)`, with
    the **static `/embedding` routes declared before `/{server_id}`** (path-capture
    avoidance), and the error→status taxonomy (400 / 404 / 502 / 204 / 403).

- **Pending system-wide ID-strategy item** — 006 chose **autoincrement int** ids for
  `LlmServer` (consistent with `User`, D1), diverging from the reference's
  snowflake-as-string. Add to the same open ID-strategy decision flagged by 003.

- **Pending export-credential-redaction item** — `LlmServer.api_key` **exports
  verbatim** (the stored `$ENV` token / literal), consistent with how 003/004 export
  `pwdhash` / `jwt_signing_key` in plaintext. Add to the same redaction concern; 006
  deliberately did not solve it.

## `docs/architecture/frontend.md`

- **Admin SPA grew a second section** — record the `/admin/llm-servers` page + its
  three modals (server form, models probe+enable, embedding), the `api/llmServers.ts`
  resource module, and `types/llmServers.d.ts` (incl. the `"llama-swap" | "openai"`
  union). Note the Admin SPA now has a minimal **`Users | LLM Servers`** nav —
  realizing the nav growth 005 deferred to "when 006 adds pages" — still under the
  minimal local layout, with the shared cross-SPA `AppLayout/Header/Sidebar` shells
  still deferred.

## `docs/architecture/quick-reference.md` (create if still absent)

- Add the `/api/admin/llm-servers` surface: `GET ""`, `POST ""`, `GET /embedding`,
  `DELETE /embedding`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}`,
  `GET /{id}/available-models`, `PUT /{id}/enabled-models`, `PUT /{id}/embedding` (all
  `require_role(admin)`; statuses per the taxonomy above).
- Add the DTOs: `LlmServerResponse` (id:int, name, backend_type, base_url,
  has_api_key, enabled_models:list[str], is_active, is_embedding, embedding_model,
  timestamps — no api_key), `CreateLlmServerRequest`, `UpdateLlmServerRequest`,
  `AvailableModelsResponse`, `EnabledModelsRequest`, `SetEmbeddingRequest`,
  `EmbeddingConfigResponse`, `LlmServersListResponse`.

## Observations

_populated by the coder / fixer as steps complete_
