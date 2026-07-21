# Outcome — 001.backend-scaffold

Intended documentation changes to apply at finalization. This scaffold is technology/structure, not a product-domain design, and `backend.md` / `system-overview.md` already describe this exact skeleton — so the deltas below are deliberately minimal. Do **not** restate `backend.md`.

## `docs/architecture/backend.md`

- **Section: DB engine / startup.** Record the **known seam**: for the greenfield scaffold, the startup lifespan runs `SQLModel.metadata.create_all` on boot (no data yet). Note that feature `003.first-run-bootstrap` (FEAT-001) will amend startup to defer table creation to a first-run wizard — so this is an intentional, temporary arrangement, not the end state.
- **Section: layer separation / health.** If it sharpens the doc, note the confirmed scaffold decisions: `GET /api/health` is **DB-readiness through all four layers** (not liveness-only), the LanceDB sidecar is **stubbed** (`db/vector.py` connect/init, unused until a vector-backed model exists), and the full authoritative dependency block is added upfront (auth deps present but unwired). These refine intent already implied by the doc; keep additions terse.
- **Section: scope / deployment.** Record that prod nginx + docker-compose are **deferred past 001** — the backend runs via the uvicorn dev server only at this stage.

## `docs/architecture/quick-reference.md` (not yet created)

- Once this feature lands, `quick-reference.md` should gain its first concrete entries: the `GET /api/health` endpoint and the `HealthResponse` DTO (`{status:"ok", db:"ready"}`). Flag for the architect to seed the file (or add these when it is first created). This is the first real endpoint + DTO in the system.

## Notes for the architect

- The JSONL import/export **mechanism** now exists with an empty `TABLE_REGISTRY`. The extension contract — "adding a persistent model = add a `to_dict`/`from_dict` codec pair + one ordered `TABLE_REGISTRY` tuple in FK order" — is worth a one-line pointer wherever the import/export section documents how models plug in.

## Observations

- Step 004: The import/export extension contract is now live — adding a persistent model = add its `to_dict`/`from_dict` codec pair plus one ordered `TABLE_REGISTRY` tuple (element shape `(zip_filename, model_class, to_dict_fn, from_dict_fn)`) in FK dependency (import) order in `backend/app/services/db_import_export.py`; the session-free db primitives in `backend/app/db/import_export_queries.py` need no change per model. Possible impact: document this under the import/export section of `docs/architecture/backend.md` (for the architect).
