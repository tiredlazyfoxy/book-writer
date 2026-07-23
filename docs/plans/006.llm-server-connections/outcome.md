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

- Review R1/R2 (2026-07-23) superseded two "Pending" items above. `LlmServer` now uses **snowflake ids** (`default_factory=generate_id`, DTO edge stringified) — the "Pending system-wide ID-strategy item" bullet is resolved for `LlmServer`, and its premise ("006 chose autoincrement int … consistent with User") was inaccurate (`User` is snowflake). Possible impact: rewrite/remove that outcome bullet at finalization; the ID strategy is now uniformly snowflake-as-string. And `LlmServer.api_key` now **exports redacted** (raw literals → `None`, `$ENV` tokens kept verbatim), so the "Pending export-credential-redaction item" is partly solved for `LlmServer` (user `pwdhash`/`jwt_signing_key` still export verbatim). Possible impact: update that outcome bullet to note the LlmServer redaction landed and only the user-credential redaction remains deferred.

---
Status: Applied 2026-07-23
Applied items: 8 (backend.md ×4, frontend.md ×1, quick-reference.md ×3)
Rejected items: 0 — items 9 & 10 applied-with-modification (see notes)

Landed in the architecture docs, reflecting the **post-rewrite** delivered state (review.md R1+R2 DONE/PASS):

- **`backend.md`** — new **"LLM server connections"** section (`Realizes: FEAT-004, UC-010..014`): table+db module, `$ENV` resolver + `has_api_key` masking, probe wiring + failure taxonomy (502), embedding clear-all-then-set, first DELETE pattern, route surface + error→status taxonomy + static-`/embedding` ordering. Added the **`LlmServer`** field table under "Domain models" (snowflake `id`, conformant). Registered `llm_servers` as the **2nd `TABLE_REGISTRY` entry** and rewrote the "Export credential policy" paragraph (literal LLM `api_key` → `null` on export, `$ENV` tokens kept; `User` credentials unchanged; framed as a scoped early slice of the feature-007 target). Added a dated **Decision history** entry (2026-07-23).
- **`frontend.md`** — recorded the Admin SPA's second section (`/admin/llm-servers` page + 3 modals, `api/llmServers.ts`, `types/llmServers.d.ts` with the backend-type union, `Users | LLM Servers` nav; `LlmServer.id` typed `string`; shared shells still deferred).
- **`quick-reference.md`** — added the 9 `/api/admin/llm-servers` endpoint rows, all the LLM-server DTOs (`LlmServerResponse.id: str`, `EmbeddingConfigResponse.server_id: str | null`, no `api_key`), and the `LlmServer` table row.

**Items 9 & 10 (the two "Pending …" bullets above) — applied with modification, not as written.** Both were stale after the R1/R2 rewrite:
- Item 9 ("Pending system-wide ID-strategy item"): the snowflake standard is already settled (per `backend.md`) and was never a pending decision; its premise ("006 chose autoincrement int, consistent with `User`") was inaccurate (`User` is snowflake). Recorded instead that **`LlmServer` now conforms** to the standard — no "pending" framing created.
- Item 10 ("Pending export-credential-redaction item — api_key exports verbatim"): post-rewrite the export does the **opposite**. Recorded the **actual** policy — literal LLM `api_key` redacted to `null` on export, `$ENV` tokens preserved, `User` credentials unchanged — with the feature-007 two-mode split noted as the remaining broader target.

No `docs/product/` back-propagation (FEAT-004 fully specified). No arch doc exceeds the ~400-line limit.
