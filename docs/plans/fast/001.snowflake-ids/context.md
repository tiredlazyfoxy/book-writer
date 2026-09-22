# Context — fast/001.snowflake-ids

Adopt the system-wide snowflake entity-id strategy in code, migrating the only
existing table model (`User`) from an autoincrement integer PK to an
application-generated snowflake id. This feature *implements* an already-settled
design — do not re-derive it. Ground truth: `docs/architecture/backend.md`,
sections "Conventions — entity ID strategy", "DB import/export", and
"Authentication", plus the two Decision-history entries dated 2026-07-22.

## Files involved

Source (amend/new):
- `backend/app/ids.py` — NEW cross-cutting snowflake generator utility.
- `backend/app/settings.py` — add a `node_id` setting.
- `backend/app/models/user.py` — `id` becomes an app-generated snowflake.
- `backend/app/db/users.py` — `create` no longer depends on post-insert refresh
  to learn the id.
- `backend/app/services/db_import_export.py` — user codec id handling
  (string out; string-or-int in).

Tests (new/adjust):
- `backend/tests/test_ids.py` — NEW, mirrors `backend/tests/test_settings.py`
  (root-level, synchronous, direct import).
- `backend/tests/services/test_db_import_export.py` — adjust/add codec id assertions.
- `backend/tests/db/test_users.py` — reconcile only if a stale assertion breaks;
  `assert created.id is not None` still holds under snowflake.

## Settled design facts (distilled)

- **Snowflake layout.** 64-bit, high bit 0 (always positive). 41-bit ms
  timestamp since a pinned epoch + 10-bit node id (0–1023) + 12-bit
  per-millisecond sequence (0–4095). Monotonic per-ms sequence; on sequence
  overflow within a millisecond, spin/wait to the next millisecond. Single async
  process → an in-process guard suffices; no external/cross-process locking.
- **Epoch — PINNED constant `1704067200000`** (2024-01-01T00:00:00Z, ms). Named
  module constant in `app/ids.py`. Fix-once-never-change.
- **Node id from config.** New `node_id` field on `Settings`, mirroring the
  existing `db_path` pattern exactly: default `0`,
  `validation_alias="BOOKWRITER_NODE_ID"`, typed `int`, no env prefix. Validate
  the 0–1023 range. `get_settings()` is `lru_cache`-wrapped; the generator reads
  `get_settings().node_id` at call time (consistent with the codebase; tests use
  `get_settings.cache_clear()`).
- **App-generated ids.** Ids exist *before* insert — no reliance on DB
  autoincrement or `session.refresh()` for the id. Mechanism is frozen by the
  skeleton agent; the recommended form is a model field
  `default_factory=generate_id`, with the db-layer-assigns-when-`None` variant as
  an acceptable alternative. What is LOCKED is that ids are app-generated, not
  DB-assigned.
- **Id serialization = STRING at JSON boundaries.** The export codec emits `id`
  as `str(user.id)`; the import codec accepts BOTH a JSON string and a legacy
  JSON number, parsing via `int(...)`, so pre-snowflake archives still import.
  Reason: 64-bit ids exceed JS `Number.MAX_SAFE_INTEGER` (2^53).
- **Fresh-install migration stance.** No deployed data; model-only change. No
  in-place PK data migration (`create_all` can't alter a PK, no Alembic).
  Pre-existing dev DBs are recreated/re-imported. Legacy small int ids sit far
  below time-based snowflakes, so mixed archives won't collide.

## Constraints

- No separate backend static type-check exists — import-clean is the gate.
  Backend test command: `cd backend && .venv/Scripts/python -m pytest`.
- `app/ids.py` is the *sanctioned exception* to "one `db/` module per entity":
  it is a shared, domain-agnostic helper, deliberately not one of the four layers.
- Layer discipline still holds for every touched layer: no `session` / `select()`
  / `session.add()` outside `db/`; `db/` returns model objects, not ORM rows.
