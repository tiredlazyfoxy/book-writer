# Plan — fast/001.snowflake-ids — Adopt snowflake entity ids (User migration)

## Goal

Implement the settled system-wide snowflake entity-id strategy: add a
cross-cutting `generate_id()` utility and a `node_id` setting, migrate `User`'s
PK from autoincrement to an application-generated 64-bit snowflake id, and make
the user import/export codec serialize ids as strings (accepting legacy int ids
on import).

## Source files

- `backend/app/ids.py` — NEW: snowflake generator utility (`generate_id`) and the pinned `EPOCH_MS` constant.
- `backend/app/settings.py` — AMEND: add the `node_id` field to `Settings`.
- `backend/app/models/user.py` — AMEND: `id` becomes an app-generated snowflake; update the stale autoincrement docstring.
- `backend/app/db/users.py` — AMEND: `create` persists a user whose id is already set at construction (no reliance on refresh for the id).
- `backend/app/services/db_import_export.py` — AMEND: user codec id handling (string out; string-or-int in).

## Test files

- `backend/tests/test_ids.py` — NEW: generator + node-id + sequence/ordering coverage.
- `backend/tests/services/test_db_import_export.py` — AMEND: codec id string-serialization and legacy-int import coverage.
- `backend/tests/db/test_users.py` — AMEND (only if a stale assertion breaks): confirm `create` yields a populated snowflake id.

## Interface intent

*(Prose only. The fast-skeleton agent freezes exact signatures.)*

- **`EPOCH_MS` (module constant, `app/ids.py`).** The pinned project epoch in
  milliseconds: `1704067200000` (2024-01-01T00:00:00Z UTC). A permanent constant,
  never tunable.
- **`generate_id()` (`app/ids.py`).** Returns a fresh 64-bit snowflake id as a
  Python `int`. Composes the id from: (ms since `EPOCH_MS`) shifted into the
  41-bit timestamp field, the node id (from `get_settings().node_id`) in the
  10-bit node field, and a per-millisecond sequence counter in the low 12 bits.
  High bit stays 0 (ids always positive). The sequence increments for repeated
  calls in the same millisecond; on overflow past 4095 within one millisecond it
  spins/waits until the clock advances to the next millisecond. Uses an
  in-process guard to stay monotonic and unique within the single async process.
  Reads the node id at call time (so a settings-cache clear in tests takes
  effect). No inputs; no external state beyond the module-level sequence/last-ms
  guard.
- **`Settings.node_id` (`app/settings.py`).** A new integer field on the existing
  `Settings` class, default `0`, sourced from env `BOOKWRITER_NODE_ID` via an
  explicit `validation_alias` (no env prefix), mirroring the existing `db_path`
  field exactly. Constrained to the valid node range 0–1023.
- **`User.id` (`app/models/user.py`).** The primary key becomes an
  application-generated 64-bit snowflake `int`, populated at construction (before
  insert) rather than assigned by the database. The stale "autoincrement
  (decision 6)" docstring/comment is updated to describe the snowflake id.
- **`users.create` (`app/db/users.py`).** Persists the given `User` whose `id` is
  already populated at construction; it must not depend on a post-insert
  `session.refresh()` to obtain the id. Any other refresh needs (e.g. defaulted
  timestamps) may remain. Continues to return the persisted `User`.
  `get_by_id(user_id: int)` keeps its `int` id parameter.
- **User export codec (`_user_to_dict`, `app/services/db_import_export.py`).**
  Emits the user's `id` as a JSON **string** (`str(user.id)`); all other fields
  unchanged.
- **User import codec (`_dict_to_user`, `app/services/db_import_export.py`).**
  Accepts the `id` value as **either** a JSON string **or** a legacy JSON number,
  parsing it to `int` in both cases, so pre-snowflake archives still import.

## Definition of done

- **DoD-1 [test]** `generate_id()` returns strictly positive ids (high bit 0)
  that fit in 64 bits, and a large batch of rapid successive calls are all unique.
- **DoD-2 [test]** With `BOOKWRITER_NODE_ID` set (and the settings cache cleared),
  the 10-bit node-id field decoded from a generated id equals the configured node
  id.
- **DoD-3 [test]** Successive `generate_id()` calls are monotonically
  non-decreasing and roughly time-ordered, and two calls within the same
  millisecond produce different ids (the sequence field distinguishes them).
- **DoD-4 [test]** A `User` obtained via `db.users.create` (and/or `User`
  construction) has a populated snowflake `id` — positive, in the snowflake range
  above legacy small ints — assigned without relying on DB autoincrement.
- **DoD-5 [test]** `_user_to_dict` serializes `id` as a JSON string, and feeding
  that dict back through `_dict_to_user` round-trips to the correct `int` id.
- **DoD-6 [test]** `_dict_to_user` accepts a legacy dict whose `id` is a JSON
  number (int) and imports it to the correct `int` id (back-compat).
- **DoD-7 [manual/live]** `Settings.node_id` rejects (or clamps per the frozen
  mechanism) an out-of-range value outside 0–1023; the intended range constraint
  is present.
- **DoD-8 [manual/live]** The backend package imports clean and the full backend
  suite passes: `cd backend && .venv/Scripts/python -m pytest`.

## Out of scope

- **JWT `user_id` claim serialization (int→string).** `services/auth.py`'s
  `create_token` still puts `user.id` into the token payload. Per the string
  convention a JWT payload is a JSON boundary, but token verification and any
  frontend token-decoding are **feature 004's** domain and nothing decodes the
  claim today. Defer the claim's int→string change to feature 004 (flagged here so
  004 picks it up). Do **not** touch `services/auth.py` or
  `tests/services/test_auth.py` in this feature.
- **Any API DTO / frontend `.d.ts` id typing.** No Pydantic API schema and no
  `src/types/*.d.ts` currently carries an entity id, so there is nothing to change
  on the API/frontend surface now. The string-in-DTO/`.d.ts` convention applies
  only when an id first surfaces there (a future feature).
- **In-place PK data migration.** Fresh-install stance; no data conversion seam.
- **Migrating any entity other than `User`** — it is the only table model.
