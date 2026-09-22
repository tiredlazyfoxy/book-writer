# Feature 006 — llm-server-connections (feature-wide context)

## Goal & scope

Give an authenticated **admin** the ability to register, edit, and delete **LLM
server connections** (name, backend type, base URL, API key), **test** a
connection to **probe** the models a server offers, **enable** a subset of those
models, and designate **one** server+model as the embedding provider. API keys
use `$ENV_VAR` indirection (a stored value like `"$OPENAI_API_KEY"` resolved from
the environment at use time) and are **never returned raw** — responses expose
only `has_api_key: bool`.

This is the codebase's **first `llm`-client wiring** and its **first DELETE
pattern** (db + route). Cross-layer:

- **Backend** — a single `LlmServer` table + its session-free db module, JSONL
  import/export codec, the `$ENV` resolver + secret masking, CRUD/enable/embedding
  service logic, the probe/test-connection service (the `llm`-client wiring), the
  admin HTTP routes + schemas, and router wiring.
- **Frontend** — the Admin SPA's second real section: a servers list with
  create/edit/delete + probe→enable→designate modals, plus a minimal
  `Users | LLM Servers` nav (the growth 005 deferred to "when 006 adds pages").

Delivers **FEAT-004** — `UC-010..014` / `US-010, US-011, US-012, US-013, US-014,
US-021`. Read `docs/product/use-cases/FEAT-004.llm-server-connections.md` and
`docs/product/stories/FEAT-004.llm-server-connections.md`; every `[test]` DoD item
cites the `US-###.AC-#` it verifies (or a numbered decision D1..D9 below).

The settled boundary is `brief.md` (Definition + Scope In/Out). **Out of scope (do
not widen):** using models for generation (domain stages); DB consistency
(feature 007); redaction of raw-literal keys on export (routed to `outcome.md`,
not solved here).

## Architecture sources (read these)

- `docs/architecture/backend.md` — the enforced 4-layer rules (`routes/` HTTP-only;
  `services/` no `session`/`AsyncSession`/`select()`/`session.exec()`/`session.add()`;
  `db/` session-free, ORM never leaks, one module per entity; `models/` tables +
  schemas under `models/schemas/`); typed discipline (Pydantic `BaseModel` for all
  API I/O, no free dicts); `create_all` + additive `ALTER` migrations; **provider/
  LLM-server settings live in the DB, not a config file**; the `$ENV_VAR`
  indirection contract (resolved at use time, raw keys never returned); the
  `llm-client` dependency (module `llm`, OpenAI-compatible + llama-swap; route all
  outbound LLM calls through it); gzip-JSONL import/export per persistent model;
  the pytest/httpx in-process harness.
- `docs/architecture/frontend.md` — MobX hard rules (`observer` on every component;
  state = observable fields + pure `get` computeds, **never** effectful methods;
  effectful ops are external `(state, args, signal)` fns with `runInAction`; the
  async trio `<name>`/`<name>Status`/`<name>Error`; forms are drafts-in-state +
  `get`-computed validation + separate `serverErrors` — **no Mantine `useForm`**;
  `useState(() => new XState())`; page-level `useEffect` only; modal drafts may live
  in component-local state); the `api/` layer (`request<T>` + `ApiError`,
  namespace-imported resource modules, `signal?` last, `types/` DTOs match wire JSON
  1:1, no `any`, no zod).
- Root `CLAUDE.md` — backend tests `cd backend && .venv/Scripts/python -m pytest`;
  frontend build/typecheck `cd frontend && npm run build` / `npx tsc --noEmit`;
  **no frontend test runner** — every frontend DoD item is `[manual/live]` (002
  decision 5, carried by 005).

## Substrate — delivered surfaces this feature builds on / amends

Features **001.backend-scaffold**, **003.first-run-bootstrap**, **005.user-management**
are the substrate. Several files here are **amended**, not created — expected
cross-feature amendment, **not** scope drift; per-step context files flag each.

Backend, treat as given:

- `app/db/engine.py` (001/003) — `DbConfig`; `init_engine`; `init_db()` (runs the
  **model-registration hook** then `create_all` + the additive `ALTER` seam);
  `get_standalone_session()` (the sole session primitive — one session per db call).
  The registration hook already imports `app.models.user`; **step 001 adds
  `import app.models.llm_server  # noqa: F401`** (D1).
- `app/db/import_export_queries.py` (001) — `export_table(model_class, callback)`,
  `upsert_batch(items)`, `run_vector_rebuild()` (session-free primitives).
- `app/services/db_import_export.py` (001/003) — the **ordered** `TABLE_REGISTRY`
  of `(zip_filename, model_class, to_dict_fn, from_dict_fn)`; `users` is first;
  an isoformat datetime helper is already present. **Step 001 appends the
  `llm_servers` tuple** after `users` (D6).
- `app/services/auth.py` (004/005) — `get_current_user` and the `require_role`
  dependency factory (ladder `{author:0, admin:1}`, insufficient → 403). An auth
  dependency living in `services/auth.py` raising the HTTP error directly is the
  sanctioned pattern, **not** a routes-layer violation.
- `app/routes/admin/__init__.py` + `app/routes/admin/users.py` (005) — the admin
  route package + the users router (`/api/admin/users`). **Step 004 adds a sibling
  `routes/admin/llm_servers.py`.**
- `app/main.py` (001/003/005) — the composition root that `include_router(...)`s
  each router. **Step 004 includes the new llm-servers router.**
- Test harness (001/005): `pytest`/`pytest-asyncio` `asyncio_mode="auto"`;
  in-process `httpx.AsyncClient` over `ASGITransport`; `tests/conftest.py` provides
  a temp-SQLite `DbConfig` fixture + an `http_client` fixture; process-global flags
  reset between tests.

Frontend, treat as given:

- `src/api/client.ts` (002/004) — `request<T>(url, {method?, body?, signal?})`;
  injects `Authorization: Bearer <getToken()>`; `204` → `undefined`;
  `ApiError(status, message, details?)`. All resource fns go over this.
- `src/admin/App.tsx` + `src/admin/routes.tsx` (002/004/005) — the Admin SPA mounts
  at `/admin` with the 004 mount-time token-gate and a **minimal** local layout
  hosting the users page (005 kept it minimal, deferring nav growth to 006).
  **Step 005 adds the LLM-Servers route + a minimal `Users | LLM Servers` nav** and
  **keeps** the token-gate; do **not** build a heavyweight shared sidebar framework.

## LOCKED design decisions (frozen — the planner does not re-open these)

A sibling reference app, **llm-rp-server**
(`D:/GitRoot/_TextGens/LLMRPTextOnlyProject/backend` + `.../frontend`), implements
this near-1:1. **Reproduce its shape, adapted to BookWriter's conventions**;
reference paths are cited per-step for the coder/skeleton to consult, never copied
verbatim. Decisions D1..D9 override several reference choices.

**D1 — Single `LlmServer` table** (`backend/app/models/llm_server.py`), no companion
tables. Fields: `id` (**autoincrement int** primary key, surfaced as int in DTOs —
follows BookWriter's own `User` pattern, NOT the reference's snowflake-as-string;
flagged for the pending ID-strategy architect item in `outcome.md`); `name: str`;
`backend_type: str`; `base_url: str`; `api_key: str | None = None` (stored raw or as
a `"$ENV_VAR"` token); `enabled_models: str = "[]"` (JSON-encoded `list[str]` in a
TEXT column); `is_active: bool = True`; `is_embedding: bool = False`;
`embedding_model: str | None = None`; `created_at: datetime | None`;
`modified_at: datetime | None`. Register the module in the `db/engine.py` hook.

**D2 — `backend_type` is a bare `str`**, validated at the **service** level against
the module constant set `{"llama-swap", "openai"}`. An invalid value raises the
typed service error (invalid-backend-type case) → route maps to **400** (US-010.AC-2).
**Not** a Pydantic/DB enum. The frontend TS side uses a `"llama-swap" | "openai"`
union.

**D3 — `$ENV` resolver + secret masking.** ONE shared resolver
(`backend/app/services/secrets.py` → `resolve_env_ref`): `None`→`None`; a value
starting with `$` → look up `os.environ[name]`, raising a typed error (mapping to
**400**) if unset; otherwise return the literal. Resolution happens **only at use
time** (during probe/embed), never at rest. Masking: the response DTO has **no
`api_key` field** — only `has_api_key: bool`, computed by the service mapper as
`api_key is not None and api_key != ""` (US-021).

**D4 — Probe == test-connection, fused, synchronous** (not SSE). `probe_models`
resolves the key (at use time), constructs the right `llm` client by `backend_type`
via an internal `_create_client` helper, calls `await client.list_models()`
(returns `list[str]`), returns it **sorted**. Route:
`GET /api/admin/llm-servers/{id}/available-models` → `AvailableModelsResponse`.

**D5 — Embedding designation** = per-row `is_embedding: bool` + `embedding_model`,
enforced as **clear-all-then-set**: db exposes `clear_all_embedding()` (a bulk
`sqlalchemy.update()` over all rows — the one sanctioned spot raw SQLAlchemy appears
inside `db/`, legitimate because it's the db layer) and `get_embedding_server()`.
Service `set_embedding_server(id, model)` calls `clear_all_embedding()` then sets
the flag+model on the target (US-014.AC-2 "replaces prior"). Routes:
`PUT /api/admin/llm-servers/{id}/embedding` (body `{model}`),
`GET /api/admin/llm-servers/embedding` (current config),
`DELETE /api/admin/llm-servers/embedding` (clear). **Static `/embedding` routes MUST
be declared before the `/{server_id}` param routes** to avoid path-param capture.

**D6 — Import/export.** ONE codec pair (`_llm_server_to_dict` /
`_dict_to_llm_server`) and ONE `TABLE_REGISTRY` tuple
`("llm_servers", LlmServer, _llm_server_to_dict, _dict_to_llm_server)` in
`services/db_import_export.py`, placed **after** the `users` entry (LlmServer has no
FK to users; order just needs to be deterministic). `enabled_models` exported/restored
as the JSON string; `is_active`/`is_embedding`/`enabled_models` get `.get(...)`
defaults on import; datetimes via the existing isoformat helper. **`api_key` is
exported verbatim** (the stored `$ENV` token / literal) — redaction of raw literal
keys on export is a KNOWN concern, **not solved here**, routed to `outcome.md`
alongside the already-pending export-credential-redaction item (pwdhash/jwt_signing_key
already export in plaintext per 003/004).

**D7 — Admin gating & router wiring.** Every endpoint `Depends(require_role(admin))`
(the 005 factory in `services/auth.py`). New router
`backend/app/routes/admin/llm_servers.py` = `APIRouter(prefix="/api/admin/llm-servers")`,
HTTP-only (parse → call one service fn → map typed error → return schema), sibling to
005's `routes/admin/users.py`. Amend `main.py` to `include_router(...)` it.
**Error → status taxonomy:** 400 (missing/invalid field, invalid backend_type, unset
`$ENV`), 404 (server not found), **502** (server unreachable / probe failure), 204
(delete, clear-embedding), 403 (non-admin, from the guard).

**D8 — Failure taxonomy for probe** (confirmed against the installed `llm` package):
an **unreachable** server raises a raw `aiohttp.ClientError` (NOT wrapped); an
**HTTP/auth** failure raises `llm.LLMError`; a keyless `openai`-type server raises
`ValueError` at client construction (the OpenAI client mandates a key). The service
must catch all three around client-construction + `list_models()` and surface them as
the typed **probe-failed** case → **502** (US-011.AC-2: error surfaced, no model
list). `base_url` must already include the `/v1` segment (the client appends
`/models` raw) — an operator-input expectation, **not** something to auto-append.

**D9 — Frontend** (mirror the reference; **all** frontend DoD is `[manual/live]` —
no frontend test runner). BookWriter MobX rules: `observer` on every component; the
page owns a `LlmServersPageState` (async trio `servers`/`serversStatus`/`serversError`
only, `makeAutoObservable`, **no** effectful methods); external action fns
`(state, …, signal)` with `runInAction` (`loadServers`, `deleteServerAction`,
`clearEmbeddingAction`); page-level `useEffect` mount-load / unmount-abort; modal
open/target flags are **component-local `useState`**, not page state; forms use
drafts-in-state + `get`-computed validation + `canSubmit` + separate `serverErrors`
(NO Mantine `useForm`). UI flow: `ServerFormModal` has a "Select Models" action;
`ModelsModal` probes-on-open and shows `available ∪ already-enabled` as a checkbox
list (so a failed probe doesn't lose prior selections); `EmbeddingModal`
probes-on-open with a single-select radio. Reference SPA files to consult:
`D:/GitRoot/_TextGens/LLMRPTextOnlyProject/frontend/src/{types/llmServer.d.ts,api/llmServers.ts,admin/pages/LlmServersPage.tsx,admin/pages/llmServersPageState.ts}`.

## Reference project — backend files to consult (adapt, don't copy)

`D:/GitRoot/_TextGens/LLMRPTextOnlyProject/backend/` implements the same capability;
per-step context files cite concrete paths. Divergences from the reference are locked
in D1 (int id not snowflake), D3 (ONE shared `$ENV` resolver, not the reference's
duplication), and the BookWriter 4-layer split.

## Files touched across the feature

```
backend/
  app/
    models/llm_server.py                    (001 create — the LlmServer table)
    db/engine.py                            (001 amend — registration hook line; 001/003 file)
    db/llm_servers.py                       (001 create — session-free data access)
    services/db_import_export.py            (001 amend — codec + registry tuple; 001/003 file)
    models/schemas/llm_servers.py           (002 create — the request/response DTOs)
    services/secrets.py                     (002 create — resolve_env_ref)
    services/llm_servers.py                 (002 create CRUD/enable/embedding; 003 amend — probe)
    routes/admin/llm_servers.py             (004 create — the 9 endpoints)
    routes/admin/__init__.py                (004 amend if aggregation needed; 005 file)
    main.py                                 (004 amend — include the router; 005 file)
  tests/
    db/test_llm_servers.py                          (001, test-coder)
    services/test_db_import_export_llm_servers.py   (001, test-coder)
    services/test_secrets.py                        (002, test-coder)
    services/test_llm_servers.py                    (002, test-coder)
    services/test_llm_servers_probe.py              (003, test-coder)
    routes/admin/test_llm_servers.py                (004, test-coder)
frontend/
  src/types/llmServers.d.ts                              (005 create — DTOs + backend-type union)
  src/api/llmServers.ts                                  (005 create — 8 resource fns)
  src/admin/pages/LlmServersPage.tsx                     (005 create; 006 amend — wire modals)
  src/admin/pages/llmServersPageState.ts                 (005 create — list trio + actions)
  src/admin/routes.tsx                                   (005 amend — add route; 005 file)
  src/admin/App.tsx                                      (005 amend — Users|LLM Servers nav)
  src/admin/components/llm-servers/ServerFormModal.tsx   (006 create)
  src/admin/components/llm-servers/serverFormDraft.ts    (006 create)
  src/admin/components/llm-servers/ModelsModal.tsx       (006 create)
  src/admin/components/llm-servers/modelsModalDraft.ts   (006 create)
  src/admin/components/llm-servers/EmbeddingModal.tsx    (006 create)
  src/admin/components/llm-servers/embeddingModalDraft.ts (006 create)
```

`db/engine.py`, `services/db_import_export.py`, `services/llm_servers.py`,
`routes/admin/__init__.py`, `main.py`, `LlmServersPage.tsx` are each edited across
features/steps — the same role editing one file incrementally along the dependency
chain (precedent: 003's `conftest`/`main.py`, 005's `UsersPage`). Each amendment is
flagged in its step context; none is scope drift.
